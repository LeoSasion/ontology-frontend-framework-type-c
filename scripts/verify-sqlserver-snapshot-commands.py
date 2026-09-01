from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

import duckdb


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from sqlserver_snapshot_adapter_service import SqlServerAdapterError  # noqa: E402
from sqlserver_snapshot_commands import (  # noqa: E402
    METADATA_TABLES,
    REAL_DRIVER_ENABLE_ENV,
    SQLSERVER_SNAPSHOT_METADATA_DDL,
    sqlserver_capability_command,
    sqlserver_catalog_command,
    sqlserver_execute_command,
    sqlserver_plan_command,
    sqlserver_statistics_command,
    sqlserver_test_command,
)
from sqlserver_snapshot_fake_driver import FakeSqlServerDriver  # noqa: E402


checks: list[dict[str, Any]] = []


def check(label: str, ok: bool, evidence: Any = None) -> None:
    checks.append({"label": label, "ok": bool(ok), "evidence": evidence})


def parquet_contains(path: Path, column: str, expected: str) -> bool:
    connection = duckdb.connect(":memory:")
    try:
        return bool(connection.execute(
            f'SELECT count(*) > 0 FROM read_parquet(?) WHERE "{column}" = ?',
            [str(path), expected],
        ).fetchone()[0])
    finally:
        connection.close()


def expect_error(label: str, code: str, action: Callable[[], Any]) -> SqlServerAdapterError | None:
    try:
        action()
    except SqlServerAdapterError as error:
        check(label, error.code == code, error.public_payload())
        return error
    except Exception as error:  # pragma: no cover - diagnostic path
        check(label, False, {"unexpected": type(error).__name__, "error": str(error)})
        return None
    check(label, False, {"error": "operation unexpectedly succeeded"})
    return None


def args(**values: Any) -> argparse.Namespace:
    return argparse.Namespace(**values)


POLICIES = {
    "finance": {
        "host": "sql.finance.internal",
        "ports": [1433],
        "databases": ["analytics"],
        "allowedCidrs": ["10.20.0.0/16"],
        "requireTls": True,
    }
}
SAFE_CONFIG = {
    "hostAlias": "finance",
    "port": 1433,
    "database": "analytics",
    "encryption": "required",
    "credentialRef": "env:AIBI_TEST_SQLSERVER_COMMAND_SECRET",
}
ENV = {
    "AIBI_TEST_SQLSERVER_COMMAND_SECRET": json.dumps({
        "username": "readonly_command_user",
        "password": "not-a-real-command-secret",
    }),
}
CATALOG = [
    {
        "schema": "dbo",
        "name": "orders",
        "type": "table",
        "rowEstimate": 3,
        "columns": [
            {"name": "order_id", "dataType": "int", "nullable": False, "ordinal": 1},
            {"name": "changed_at", "dataType": "datetime2", "nullable": False, "ordinal": 2},
            {"name": "amount", "dataType": "decimal", "nullable": True, "ordinal": 3},
            {"name": "customer_note", "dataType": "nvarchar", "nullable": True, "ordinal": 4},
        ],
        "keyCandidates": [["order_id"]],
    }
]
BUSINESS_ROWS = {
    "dbo.orders": [
        {"order_id": 1, "changed_at": "2026-08-01T00:00:00", "amount": 10, "customer_note": "VerySecretCustomerName"},
        {"order_id": 2, "changed_at": "2026-08-02T00:00:00", "amount": 20, "customer_note": "AnotherPrivateCustomer"},
        {"order_id": 3, "changed_at": "2026-08-03T00:00:00", "amount": 30, "customer_note": "ThirdPrivateCustomer"},
    ]
}


def resolver(_host: str, _port: int) -> list[str]:
    return ["10.20.1.8"]


def fake_driver(**overrides: Any) -> FakeSqlServerDriver:
    return FakeSqlServerDriver(
        peer="10.20.1.8",
        catalog=overrides.pop("catalog", CATALOG),
        rows=overrides.pop("rows", BUSINESS_ROWS),
        **overrides,
    )


VERIFY_ROOT = Path(tempfile.mkdtemp(prefix="aibi-c-sqlserver-commands-"))
DB_PATH = VERIFY_ROOT / "metadata.sqlite"
STAGING_ROOT = VERIFY_ROOT / "staging"


def open_db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def metadata_payload_text(connection: sqlite3.Connection) -> str:
    """Return values owned by this facade, excluding source connector storage."""
    values: list[str] = []
    for table in METADATA_TABLES:
        for row in connection.execute(f"SELECT * FROM {table}").fetchall():
            values.extend(str(value) for value in row if value is not None)
    return " ".join(values)


def install_fixture(*, metadata: bool = True) -> None:
    with open_db() as connection:
        connection.executescript(
            """
            CREATE TABLE system_flags (
              key TEXT PRIMARY KEY,
              value TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE workspaces (
              id TEXT PRIMARY KEY
            );
            CREATE TABLE data_connectors (
              connector_key TEXT NOT NULL,
              workspace_id TEXT NOT NULL,
              name TEXT NOT NULL,
              connector_type TEXT NOT NULL,
              provider TEXT NOT NULL,
              status TEXT NOT NULL,
              config_json TEXT NOT NULL,
              schedule_json TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              last_sync_at TEXT,
              last_sync_status TEXT,
              last_sync_result_json TEXT,
              PRIMARY KEY(workspace_id, connector_key)
            );
            INSERT INTO workspaces(id) VALUES('default'), ('other');
            INSERT INTO system_flags(key, value, updated_at)
            VALUES('active_workspace_id', 'default', '2026-08-13T00:00:00Z');
            """
        )
        if metadata:
            connection.executescript(SQLSERVER_SNAPSHOT_METADATA_DDL)
        for workspace_id, connector_key, status, config in [
            ("default", "finance_sql", "active", SAFE_CONFIG),
            ("default", "paused_sql", "paused", SAFE_CONFIG),
            ("default", "unsafe_sql", "active", {**SAFE_CONFIG, "password": "must-not-be-read"}),
            ("other", "other_sql", "active", SAFE_CONFIG),
        ]:
            connection.execute(
                """
                INSERT INTO data_connectors(
                  connector_key, workspace_id, name, connector_type, provider, status,
                  config_json, schedule_json, created_at, updated_at
                ) VALUES(?, ?, ?, 'sqlserver', 'mssql-readonly', ?, ?, '{}', ?, ?)
                """,
                (connector_key, workspace_id, connector_key, status, json.dumps(config), "2026-08-13T00:00:00Z", "2026-08-13T00:00:00Z"),
            )
        connection.commit()


try:
    install_fixture()

    injected = fake_driver()
    capability = sqlserver_capability_command(
        args(connector="finance_sql"),
        open_db=open_db,
        driver=injected,
        policies=POLICIES,
        environ=ENV,
    )
    capability_text = json.dumps(capability, ensure_ascii=False)
    check(
        "capability-parses-only-public-connector-config",
        capability["adapter"]["capability"] == "ready_for_test"
        and capability["connector"]["connectorKey"] == "finance_sql"
        and "credentialRef" not in capability_text
        and "readonly_command_user" not in capability_text
        and "not-a-real-command-secret" not in capability_text,
        capability,
    )

    disabled = sqlserver_capability_command(
        args(connector="finance_sql"),
        open_db=open_db,
        policies=POLICIES,
        environ=ENV,
    )
    check(
        "real-driver-is-unavailable-until-explicitly-enabled",
        disabled["adapter"]["capability"] == "unavailable"
        and REAL_DRIVER_ENABLE_ENV in str(disabled["adapter"]["reason"]),
        disabled["adapter"],
    )
    with patch(
        "sqlserver_snapshot_commands._real_driver",
        side_effect=SqlServerAdapterError(
            "SQLSERVER_DRIVER_UNAVAILABLE",
            "The explicitly enabled optional driver is unavailable.",
        ),
    ):
        missing_optional_runtime = sqlserver_capability_command(
            args(connector="finance_sql"),
            open_db=open_db,
            policies=POLICIES,
            environ={**ENV, REAL_DRIVER_ENABLE_ENV: "1"},
        )
    check(
        "capability-stays-readable-when-explicit-optional-runtime-is-missing",
        missing_optional_runtime["adapter"]["capability"] == "unavailable"
        and missing_optional_runtime["adapter"]["available"] is False
        and "optional driver is unavailable" in str(missing_optional_runtime["adapter"]["reason"]),
        missing_optional_runtime["adapter"],
    )
    expect_error(
        "network-command-without-injected-or-enabled-driver-is-blocked",
        "SQLSERVER_DRIVER_NOT_EXPLICITLY_ENABLED",
        lambda: sqlserver_test_command(
            args(connector="finance_sql", timeout=5),
            open_db=open_db,
            policies=POLICIES,
            environ=ENV,
            resolver=resolver,
        ),
    )

    unsafe_driver = fake_driver()
    expect_error(
        "plaintext-secret-config-is-blocked-before-driver-access",
        "SQLSERVER_CONNECTOR_SECRET_SURFACE_FORBIDDEN",
        lambda: sqlserver_test_command(
            args(connector="unsafe_sql", timeout=5),
            open_db=open_db,
            driver=unsafe_driver,
            policies=POLICIES,
            environ=ENV,
            resolver=resolver,
        ),
    )
    check("unsafe-config-never-opens-driver", unsafe_driver.connect_count == 0)
    paused = sqlserver_capability_command(
        args(connector="paused_sql"),
        open_db=open_db,
        driver=fake_driver(),
        policies=POLICIES,
        environ=ENV,
    )
    check("paused-connector-is-visible-but-not-actionable", paused["adapter"]["capability"] == "unavailable", paused)
    expect_error(
        "active-workspace-hides-other-workspace-connector",
        "SQLSERVER_CONNECTOR_NOT_FOUND",
        lambda: sqlserver_capability_command(
            args(connector="other_sql"),
            open_db=open_db,
            driver=fake_driver(),
            policies=POLICIES,
            environ=ENV,
        ),
    )

    tested = sqlserver_test_command(
        args(connector="finance_sql", timeout=5),
        open_db=open_db,
        driver=fake_driver(),
        policies=POLICIES,
        environ=ENV,
        resolver=resolver,
    )
    check("test-command-is-read-only-and-secret-free", tested["operation"] == "test" and tested["sideEffects"]["remoteWrite"] is False, tested)

    discovered = sqlserver_catalog_command(
        args(connector="finance_sql", max_tables=8, max_columns=64, timeout=5),
        open_db=open_db,
        driver=fake_driver(),
        policies=POLICIES,
        environ=ENV,
        resolver=resolver,
        now=lambda: "2026-08-13T00:01:00Z",
    )
    catalog_fingerprint = str(discovered["catalogFingerprint"])
    with open_db() as connection:
        catalog_count = int(connection.execute("SELECT COUNT(*) FROM sqlserver_snapshot_catalogs").fetchone()[0])
        database_text_after_catalog = metadata_payload_text(connection)
    check(
        "catalog-persists-metadata-only",
        catalog_count == 1
        and discovered["persistedMetadata"] is True
        and "VerySecretCustomerName" not in database_text_after_catalog
        and "readonly_command_user" not in database_text_after_catalog
        and "not-a-real-command-secret" not in database_text_after_catalog
        and "credentialRef" not in database_text_after_catalog,
        {"catalogCount": catalog_count},
    )

    statistics = sqlserver_statistics_command(
        args(connector="finance_sql", catalog=catalog_fingerprint, resources="dbo.orders", sample_rows=20, timeout=5),
        open_db=open_db,
        driver=fake_driver(),
        policies=POLICIES,
        environ=ENV,
        resolver=resolver,
    )
    with open_db() as connection:
        receipt_count_before_execute = int(connection.execute("SELECT COUNT(*) FROM sqlserver_snapshot_receipts").fetchone()[0])
    check(
        "statistics-are-returned-but-never-persisted",
        statistics["operation"] == "preview"
        and statistics["persistedMetadata"] is False
        and statistics["rawRowsReturned"] is False
        and receipt_count_before_execute == 0,
        statistics,
    )

    selections = [{
        "resourceKey": "dbo.orders",
        "columns": ["order_id", "changed_at", "amount", "customer_note"],
        "orderBy": ["order_id"],
        "targetTableKey": "sql_orders",
    }]
    plan_args = args(
        connector="finance_sql",
        catalog=catalog_fingerprint,
        request_key="sqlserver-command-plan-1",
        selections_json=json.dumps(selections),
        budget_json=json.dumps({"maxRowsPerTable": 10, "maxBytes": 1024 * 1024, "timeoutSeconds": 5}),
    )
    plan = sqlserver_plan_command(plan_args, open_db=open_db, now=lambda: "2026-08-13T00:02:00Z")
    replay_plan = sqlserver_plan_command(plan_args, open_db=open_db, now=lambda: "2026-08-13T00:09:00Z")
    check(
        "plan-request-is-durable-and-idempotent",
        plan["idempotentReplay"] is False
        and replay_plan["idempotentReplay"] is True
        and replay_plan["planFingerprint"] == plan["planFingerprint"]
        and replay_plan["createdAt"] == "2026-08-13T00:02:00Z",
        {"plan": plan["planFingerprint"], "replay": replay_plan["planFingerprint"]},
    )
    expect_error(
        "same-request-key-with-different-input-conflicts",
        "SQLSERVER_REQUEST_KEY_CONFLICT",
        lambda: sqlserver_plan_command(
            args(
                connector="finance_sql",
                catalog=catalog_fingerprint,
                request_key="sqlserver-command-plan-1",
                selections_json=json.dumps([{**selections[0], "targetTableKey": "different_target"}]),
                budget_json="{}",
            ),
            open_db=open_db,
        ),
    )

    execute_args = args(
        connector="finance_sql",
        request_key="sqlserver-command-plan-1",
        expected_plan=plan["planFingerprint"],
        yes=True,
    )
    expect_error(
        "execute-requires-explicit-confirmation",
        "SQLSERVER_SNAPSHOT_CONFIRMATION_REQUIRED",
        lambda: sqlserver_execute_command(
            args(**{**vars(execute_args), "yes": False}),
            open_db=open_db,
            driver=fake_driver(),
            policies=POLICIES,
            environ=ENV,
            resolver=resolver,
            staging_root=STAGING_ROOT,
        ),
    )
    expect_error(
        "execute-requires-exact-plan-fingerprint",
        "SQLSERVER_PLAN_FINGERPRINT_MISMATCH",
        lambda: sqlserver_execute_command(
            args(**{**vars(execute_args), "expected_plan": "f" * 64}),
            open_db=open_db,
            driver=fake_driver(),
            policies=POLICIES,
            environ=ENV,
            resolver=resolver,
            staging_root=STAGING_ROOT,
        ),
    )

    executed = sqlserver_execute_command(
        execute_args,
        open_db=open_db,
        driver=fake_driver(),
        policies=POLICIES,
        environ=ENV,
        resolver=resolver,
        staging_root=STAGING_ROOT,
        now=lambda: "2026-08-13T00:03:00Z",
    )
    replay_execute = sqlserver_execute_command(
        execute_args,
        open_db=open_db,
        driver=fake_driver(),
        policies=POLICIES,
        environ=ENV,
        resolver=resolver,
        staging_root=STAGING_ROOT,
        now=lambda: "2026-08-13T00:04:00Z",
    )
    with open_db() as connection:
        metadata_counts = {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in METADATA_TABLES
        }
        database_text = metadata_payload_text(connection)
        stored_plan_status = str(connection.execute("SELECT status FROM sqlserver_snapshot_plans").fetchone()[0])
    check(
        "execute-stages-once-and-persists-only-safe-receipt-metadata",
        executed["durableImportRequired"] is True
        and executed["activationJournalRequired"] is True
        and replay_execute["idempotentReplay"] is True
        and replay_execute["receiptFingerprint"] == executed["receiptFingerprint"]
        and metadata_counts == {
            "sqlserver_snapshot_catalogs": 1,
            "sqlserver_snapshot_plans": 1,
            "sqlserver_snapshot_receipts": 1,
        }
        and stored_plan_status == "staged"
        and "VerySecretCustomerName" not in database_text
        and "AnotherPrivateCustomer" not in database_text
        and "readonly_command_user" not in database_text
        and "not-a-real-command-secret" not in database_text
        and "credentialRef" not in database_text,
        {"counts": metadata_counts, "status": stored_plan_status, "receipt": executed["receiptFingerprint"]},
    )
    check(
        "business-rows-exist-only-in-owned-staging-artifact",
        any(parquet_contains(path, "customer_note", "VerySecretCustomerName") for path in STAGING_ROOT.rglob("*.parquet")),
    )

    missing_db = VERIFY_ROOT / "missing-schema.sqlite"

    def open_missing_db() -> sqlite3.Connection:
        connection = sqlite3.connect(missing_db)
        connection.row_factory = sqlite3.Row
        return connection

    with open_missing_db() as connection:
        connection.executescript(
            """
            CREATE TABLE system_flags(key TEXT PRIMARY KEY, value TEXT, updated_at TEXT);
            CREATE TABLE workspaces(id TEXT PRIMARY KEY);
            CREATE TABLE data_connectors(
              connector_key TEXT, workspace_id TEXT, name TEXT, connector_type TEXT, provider TEXT,
              status TEXT, config_json TEXT, schedule_json TEXT, created_at TEXT, updated_at TEXT,
              last_sync_at TEXT, last_sync_status TEXT, last_sync_result_json TEXT,
              PRIMARY KEY(workspace_id, connector_key)
            );
            INSERT INTO workspaces VALUES('default');
            INSERT INTO system_flags VALUES('active_workspace_id', 'default', 'now');
            """
        )
        connection.execute(
            "INSERT INTO data_connectors VALUES(?, 'default', ?, 'sqlserver', 'mssql-readonly', 'active', ?, '{}', 'now', 'now', NULL, NULL, NULL)",
            ("finance_sql", "finance_sql", json.dumps(SAFE_CONFIG)),
        )
        connection.commit()
    schema_driver = fake_driver()
    expect_error(
        "missing-central-schema-fails-before-network",
        "SQLSERVER_METADATA_SCHEMA_UNAVAILABLE",
        lambda: sqlserver_catalog_command(
            args(connector="finance_sql", max_tables=8, max_columns=64, timeout=5),
            open_db=open_missing_db,
            driver=schema_driver,
            policies=POLICIES,
            environ=ENV,
            resolver=resolver,
        ),
    )
    check("missing-schema-does-not-open-driver", schema_driver.connect_count == 0)

    source = (TOOLS / "sqlserver_snapshot_commands.py").read_text(encoding="utf-8")
    check(
        "facade-has-no-driver-install-or-arbitrary-sql-surface",
        "pip install" not in source.casefold()
        and "subprocess" not in source.casefold()
        and "--query" not in source.casefold()
        and "--sql" not in source.casefold(),
    )
finally:
    shutil.rmtree(VERIFY_ROOT, ignore_errors=True)

failed = [item for item in checks if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-sqlserver-snapshot-commands-verify/v1",
    "generatedBy": "scripts/verify-sqlserver-snapshot-commands.py",
    "checks": checks,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
if failed:
    raise SystemExit(1)
