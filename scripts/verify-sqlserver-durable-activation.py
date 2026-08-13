from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def check(checks: list[dict[str, Any]], label: str, ok: bool, detail: Any = None) -> None:
    item: dict[str, Any] = {"label": label, "ok": bool(ok)}
    if not ok and detail is not None:
        item["detail"] = detail
    checks.append(item)


def main() -> None:
    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="aibi-c-sqlserver-durable-activation-", ignore_cleanup_errors=True) as raw_temp:
        temp_root = Path(raw_temp)
        os.environ["AIBI_HYBRID_DB_PATH"] = str(temp_root / "runtime.sqlite")
        os.environ["AIBI_HYBRID_DUCKDB_PATH"] = str(temp_root / "runtime.duckdb")
        os.environ["AIBI_EVIDENCE_BUNDLE_ROOT"] = str(temp_root / "evidence")

        from bi_cli_schema import open_db
        from import_job_commands import import_job_run_command
        from source_activation_journal_service import activation_for_job
        from sqlserver_snapshot_commands import (
            sqlserver_activate_command,
            sqlserver_activation_finalize_command,
            sqlserver_activation_status_command,
            sqlserver_catalog_command,
            sqlserver_execute_command,
            sqlserver_plan_command,
        )
        from sqlserver_snapshot_fake_driver import FakeSqlServerDriver

        policy = {
            "finance": {
                "host": "sql.finance.internal",
                "ports": [1433],
                "databases": ["analytics"],
                "allowedCidrs": ["10.20.0.0/16"],
                "requireTls": True,
            }
        }
        environment = {
            "AIBI_TEST_SQLSERVER_ACTIVATION_SECRET": json.dumps({
                "username": "readonly_activation_user",
                "password": "not-a-real-activation-secret",
            })
        }
        config = {
            "hostAlias": "finance",
            "port": 1433,
            "database": "analytics",
            "encryption": "required",
            "credentialRef": "env:AIBI_TEST_SQLSERVER_ACTIVATION_SECRET",
        }
        catalog_fixture = [{
            "schema": "dbo",
            "name": "orders",
            "type": "table",
            "rowEstimate": 3,
            "columns": [
                {"name": "order_id", "dataType": "int", "nullable": False, "ordinal": 1},
                {"name": "amount", "dataType": "decimal", "nullable": True, "ordinal": 2},
            ],
            "keyCandidates": [["order_id"]],
        }]
        driver_rows = {
            "dbo.orders": [
                {"order_id": 1, "amount": 10.5},
                {"order_id": 2, "amount": 20},
                {"order_id": 3, "amount": 30.25},
            ]
        }

        def driver() -> FakeSqlServerDriver:
            return FakeSqlServerDriver(peer="10.20.1.8", catalog=catalog_fixture, rows=driver_rows)

        def resolver(_host: str, _port: int) -> list[str]:
            return ["10.20.1.8"]

        with open_db() as connection:
            connection.execute(
                """
                INSERT INTO data_connectors(
                  connector_key, workspace_id, name, connector_type, provider, status,
                  config_json, schedule_json, created_at, updated_at
                ) VALUES(?, 'default', ?, 'sqlserver', 'mssql-readonly', 'active', ?, '{}', ?, ?)
                """,
                (
                    "finance_sql",
                    "Finance read-only",
                    json.dumps(config),
                    "2026-08-13T00:00:00Z",
                    "2026-08-13T00:00:00Z",
                ),
            )
            connection.commit()

        discovered = sqlserver_catalog_command(
            argparse.Namespace(connector="finance_sql", max_tables=8, max_columns=64, timeout=5),
            open_db=open_db,
            driver=driver(),
            policies=policy,
            environ=environment,
            resolver=resolver,
            now=lambda: "2026-08-13T00:01:00Z",
        )
        selections = [{
            "resourceKey": "dbo.orders",
            "columns": ["order_id", "amount"],
            "orderBy": ["order_id"],
            "targetTableKey": "sql_orders",
        }]
        plan = sqlserver_plan_command(
            argparse.Namespace(
                connector="finance_sql",
                catalog=discovered["catalogFingerprint"],
                request_key="sqlserver-durable-plan-1",
                selections_json=json.dumps(selections),
                budget_json=json.dumps({"maxRowsPerTable": 10, "maxBytes": 1024 * 1024, "timeoutSeconds": 5}),
            ),
            open_db=open_db,
            now=lambda: "2026-08-13T00:02:00Z",
        )
        snapshot = sqlserver_execute_command(
            argparse.Namespace(
                connector="finance_sql",
                request_key="sqlserver-durable-plan-1",
                expected_plan=plan["planFingerprint"],
                yes=True,
            ),
            open_db=open_db,
            driver=driver(),
            policies=policy,
            environ=environment,
            resolver=resolver,
            staging_root=temp_root / "sqlserver-staging",
            now=lambda: "2026-08-13T00:03:00Z",
        )
        activation_args = argparse.Namespace(
            connector="finance_sql",
            workspace="default",
            request_key="sqlserver-durable-activation-1",
            expected_plan=plan["planFingerprint"],
            expected_manifest=snapshot["manifestFingerprint"],
            yes=True,
        )
        created = sqlserver_activate_command(
            activation_args,
            open_db=open_db,
            staging_root=temp_root / "sqlserver-staging",
        )
        replayed = sqlserver_activate_command(
            activation_args,
            open_db=open_db,
            staging_root=temp_root / "sqlserver-staging",
        )
        job_key = str(created["job"]["jobKey"])
        check(
            checks,
            "sealed-snapshot-queues-one-standard-durable-import",
            created["job"]["kind"] == "import"
            and created["job"]["status"] == "queued"
            and created["job"]["input"]["tableKeys"] == ["sql_orders"]
            and replayed["replayed"] is True
            and replayed["job"]["jobKey"] == job_key,
            {"created": created, "replayed": replayed},
        )
        public_created = json.dumps(created, ensure_ascii=False)
        check(
            checks,
            "activation-receipt-exposes-no-staging-path-or-secret",
            str(temp_root) not in public_created
            and "readonly_activation_user" not in public_created
            and "not-a-real-activation-secret" not in public_created,
            created,
        )

        pending = sqlserver_activation_status_command(
            activation_args,
            open_db=open_db,
            staging_root=temp_root / "sqlserver-staging",
        )
        check(
            checks,
            "queued-import-cannot-be-called-active",
            pending["capability"] == "ready_for_snapshot"
            and pending["activation"]["status"] == "queued",
            pending,
        )

        completed = import_job_run_command(argparse.Namespace(job=job_key, workspace="default", lease_token=""))
        committed = sqlserver_activation_status_command(
            activation_args,
            open_db=open_db,
            staging_root=temp_root / "sqlserver-staging",
        )
        check(
            checks,
            "fake-driver-crosses-w1-w3-before-active",
            completed["ok"] is True
            and completed["job"]["status"] == "succeeded"
            and committed["capability"] == "active"
            and committed["activation"]["status"] == "committed"
            and committed["activation"]["phase"] == "finalized",
            {"completed": completed, "activation": committed},
        )

        finalized = sqlserver_activation_finalize_command(
            argparse.Namespace(job=job_key, workspace="default", all=False, yes=True),
            open_db=open_db,
            staging_root=temp_root / "sqlserver-staging",
            now=lambda: "2026-08-13T00:04:00Z",
        )
        finalized_replay = sqlserver_activation_finalize_command(
            argparse.Namespace(job=job_key, workspace="default", all=False, yes=True),
            open_db=open_db,
            staging_root=temp_root / "sqlserver-staging",
            now=lambda: "2026-08-13T00:05:00Z",
        )
        with open_db() as connection:
            plan_status = str(connection.execute(
                "SELECT status FROM sqlserver_snapshot_plans WHERE workspace_id = 'default' AND plan_fingerprint = ?",
                (plan["planFingerprint"],),
            ).fetchone()[0])
            activation_receipts = int(connection.execute(
                "SELECT COUNT(*) FROM sqlserver_snapshot_receipts WHERE workspace_id = 'default' AND operation = 'activate'"
            ).fetchone()[0])
            journal = activation_for_job(connection, workspace_id="default", job_key=job_key)
            row_count = int(connection.execute("SELECT COUNT(*) FROM data_sql_orders").fetchone()[0])
        check(
            checks,
            "activation-finalization-is-persistent-and-idempotent",
            finalized["ok"] is True
            and finalized_replay["ok"] is True
            and plan_status == "activated"
            and activation_receipts == 1
            and journal is not None
            and journal["phase"] == "finalized"
            and journal["outcome"] == "committed"
            and row_count == 3,
            {
                "finalized": finalized,
                "replay": finalized_replay,
                "planStatus": plan_status,
                "activationReceipts": activation_receipts,
                "journal": journal,
                "rowCount": row_count,
            },
        )

        artifact_root = next((temp_root / "sqlserver-staging").rglob(snapshot["artifactKey"]))
        (artifact_root / "unexpected.csv").write_text("unsafe\nrow\n", encoding="utf-8")
        rejected = ""
        try:
            sqlserver_activation_status_command(
                activation_args,
                open_db=open_db,
                staging_root=temp_root / "sqlserver-staging",
            )
        except Exception as error:
            rejected = getattr(error, "code", "")
        check(checks, "unsealed-extra-file-invalidates-activation-proof", rejected == "SQLSERVER_ARTIFACT_INTEGRITY_FAILED", rejected)

        startup_replay = sqlserver_activation_finalize_command(
            argparse.Namespace(job=None, workspace=None, all=True, yes=True),
            open_db=open_db,
            staging_root=temp_root / "sqlserver-staging",
            now=lambda: "2026-08-13T00:06:00Z",
        )
        check(
            checks,
            "startup-reconcile-replays-finalized-history-without-requiring-live-staging",
            startup_replay["ok"] is True
            and len(startup_replay["finalized"]) == 1
            and startup_replay["finalized"][0].get("replayed") is True,
            startup_replay,
        )

    failed = [item for item in checks if not item["ok"]]
    print(json.dumps({
        "ok": not failed,
        "schema": "aibi-sqlserver-durable-activation-verify/v1",
        "generatedBy": "scripts/verify-sqlserver-durable-activation.py",
        "fakeDriverOnly": True,
        "realSqlServerExecuted": False,
        "checks": checks,
        "failedChecks": failed,
    }, ensure_ascii=False, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
