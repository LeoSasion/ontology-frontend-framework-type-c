from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
from collections import namedtuple
from contextlib import closing
from pathlib import Path
from typing import Any
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from workspace_recovery_service import (  # noqa: E402
    DUCKDB_ARTIFACT,
    SQLITE_ARTIFACT,
    WorkspaceRecoveryError,
    WorkspaceRecoveryService,
    _ensure_root,
    _workspace_bucket,
    unfinished_recovery_fences,
)
from dataset_version_store import active_dataset_version, file_sha256, resolve_object_key  # noqa: E402
from query_runtime_test_support import FixtureTable, publish_fixture_tables_to_duckdb  # noqa: E402


checks: list[dict[str, Any]] = []


def check(label: str, ok: bool, detail: Any = None) -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": None if ok else detail})


def expect_error(label: str, code: str, action: Any) -> WorkspaceRecoveryError | None:
    try:
        action()
    except WorkspaceRecoveryError as error:
        check(label, error.code == code, {"expected": code, "actual": error.code, "message": str(error)})
        return error
    except Exception as error:  # pragma: no cover - reported as failed evidence
        check(label, False, {"expected": code, "actual": type(error).__name__, "message": str(error)})
        return None
    check(label, False, {"expected": code, "actual": "no-error"})
    return None


def build_sqlite(path: Path) -> None:
    with closing(sqlite3.connect(path)) as connection:
        connection.executescript(
            """
            PRAGMA user_version = 18;
            CREATE TABLE workspaces(
              id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              current_source_run_id TEXT,
              created_at TEXT NOT NULL
            );
            CREATE TABLE system_flags(key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE global_settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE table_registry(
              table_key TEXT NOT NULL,
              workspace_id TEXT NOT NULL,
              display_name TEXT NOT NULL,
              physical_table TEXT NOT NULL,
              source_file TEXT NOT NULL,
              row_count INTEGER NOT NULL,
              column_count INTEGER NOT NULL,
              data_version INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              active_version_id TEXT NOT NULL DEFAULT '',
              schema_json TEXT NOT NULL DEFAULT '[]',
              schema_fingerprint TEXT NOT NULL DEFAULT '',
              content_fingerprint TEXT NOT NULL DEFAULT '',
              PRIMARY KEY(workspace_id, table_key)
            );
            CREATE TABLE dataset_versions(
              version_id TEXT PRIMARY KEY,
              workspace_id TEXT NOT NULL,
              table_key TEXT NOT NULL,
              row_count INTEGER NOT NULL,
              column_count INTEGER NOT NULL,
              schema_json TEXT NOT NULL,
              schema_fingerprint TEXT NOT NULL,
              content_fingerprint TEXT NOT NULL,
              source_file TEXT NOT NULL,
              created_at TEXT NOT NULL,
              UNIQUE(workspace_id, table_key, content_fingerprint)
            );
            CREATE TABLE dataset_version_files(
              version_id TEXT NOT NULL,
              ordinal INTEGER NOT NULL,
              object_key TEXT NOT NULL,
              object_hash TEXT NOT NULL,
              row_count INTEGER NOT NULL,
              byte_size INTEGER NOT NULL,
              PRIMARY KEY(version_id, ordinal)
            );
            CREATE TABLE source_runs(
              id TEXT NOT NULL,
              workspace_id TEXT NOT NULL,
              table_key TEXT NOT NULL,
              status TEXT NOT NULL,
              created_at TEXT NOT NULL,
              PRIMARY KEY(workspace_id, id)
            );
            CREATE TABLE dashboards(
              workspace_id TEXT NOT NULL,
              dashboard_key TEXT NOT NULL,
              name TEXT NOT NULL,
              PRIMARY KEY(workspace_id, dashboard_key)
            );
            CREATE TABLE relationships(
              workspace_id TEXT NOT NULL,
              relation_key TEXT NOT NULL,
              validation_json TEXT NOT NULL,
              PRIMARY KEY(workspace_id, relation_key)
            );
            CREATE TABLE query_plan_receipts(
              workspace_id TEXT NOT NULL,
              receipt_key TEXT NOT NULL,
              status TEXT NOT NULL,
              source_run_id TEXT NOT NULL,
              freshness TEXT NOT NULL,
              PRIMARY KEY(workspace_id, receipt_key)
            );
            CREATE TABLE reviewed_publications(workspace_id TEXT NOT NULL, publication_key TEXT NOT NULL, status TEXT NOT NULL, PRIMARY KEY(workspace_id, publication_key));
            CREATE TABLE evidence_ledger_entries(workspace_id TEXT NOT NULL, publication_key TEXT NOT NULL, sequence INTEGER NOT NULL, entry_hash TEXT NOT NULL, PRIMARY KEY(workspace_id, publication_key, sequence));
            CREATE TABLE analysis_jobs(workspace_id TEXT NOT NULL, job_key TEXT NOT NULL, status TEXT NOT NULL, PRIMARY KEY(workspace_id, job_key));
            CREATE TABLE analysis_job_events(workspace_id TEXT NOT NULL, job_key TEXT NOT NULL, event_sequence INTEGER NOT NULL, status TEXT NOT NULL, PRIMARY KEY(workspace_id, job_key, event_sequence));
            CREATE TABLE source_activation_journals(workspace_id TEXT NOT NULL, journal_key TEXT NOT NULL, job_key TEXT NOT NULL, phase TEXT NOT NULL, PRIMARY KEY(workspace_id, journal_key));
            CREATE TABLE import_workspace_leases(workspace_id TEXT PRIMARY KEY, job_key TEXT NOT NULL, lease_token TEXT NOT NULL, active INTEGER NOT NULL);
            INSERT INTO workspaces VALUES('workspace-a', 'Workspace A', 'run-a-1', '2026-08-13T00:00:00+00:00');
            INSERT INTO workspaces VALUES('workspace-b', 'Workspace B', 'run-b-1', '2026-08-13T00:00:00+00:00');
            INSERT INTO system_flags VALUES('active_workspace_id', 'workspace-a', '2026-08-13T00:00:00+00:00');
            INSERT INTO global_settings VALUES('unscoped', 'must-not-enter-workspace-artifact');
            INSERT INTO table_registry(
              table_key, workspace_id, display_name, physical_table, source_file,
              row_count, column_count, data_version, created_at, updated_at
            ) VALUES('orders', 'workspace-a', 'Orders', 'data_workspace_a', 'typed-fixture', 2, 2, 1, '2026-08-13T00:00:00+00:00', '2026-08-13T00:00:00+00:00');
            INSERT INTO table_registry(
              table_key, workspace_id, display_name, physical_table, source_file,
              row_count, column_count, data_version, created_at, updated_at
            ) VALUES('ledger', 'workspace-b', 'Ledger', 'data_workspace_b', 'typed-fixture', 1, 2, 1, '2026-08-13T00:00:00+00:00', '2026-08-13T00:00:00+00:00');
            INSERT INTO source_runs VALUES('run-a-1', 'workspace-a', 'orders', 'ready', '2026-08-13T00:00:00+00:00');
            INSERT INTO source_runs VALUES('run-a-history', 'workspace-a', 'orders', 'ready', '2026-08-12T00:00:00+00:00');
            INSERT INTO source_runs VALUES('run-b-1', 'workspace-b', 'ledger', 'ready', '2026-08-13T00:00:00+00:00');
            INSERT INTO dashboards VALUES('workspace-a', 'dashboard-a', 'Original A');
            INSERT INTO dashboards VALUES('workspace-b', 'dashboard-b', 'Original B');
            INSERT INTO relationships VALUES('workspace-a', 'relationship-a', '{"status":"validated"}');
            INSERT INTO relationships VALUES('workspace-b', 'relationship-b', '{"status":"validated"}');
            INSERT INTO query_plan_receipts VALUES('workspace-a', 'receipt-a', 'executed', 'run-a-1', 'current');
            INSERT INTO query_plan_receipts VALUES('workspace-b', 'receipt-b', 'executed', 'run-b-1', 'current');
            """
        )
        connection.commit()


def mutate_workspace_a(sqlite_path: Path, duckdb_path: Path, *, suffix: str, amount: float) -> None:
    with closing(sqlite3.connect(sqlite_path)) as connection:
        connection.execute("UPDATE workspaces SET current_source_run_id = ? WHERE id = 'workspace-a'", (f"run-a-{suffix}",))
        connection.execute(
            "INSERT INTO source_runs VALUES(?, 'workspace-a', 'orders', 'ready', ?)",
            (f"run-a-{suffix}", f"2026-08-13T00:0{suffix}:00+00:00"),
        )
        connection.execute("UPDATE dashboards SET name = ? WHERE workspace_id = 'workspace-a'", (f"Changed A {suffix}",))
        connection.execute("UPDATE relationships SET validation_json = ? WHERE workspace_id = 'workspace-a'", (json.dumps({"status": f"changed-{suffix}"}),))
        connection.execute(
            "INSERT OR REPLACE INTO query_plan_receipts VALUES('workspace-a', ?, 'executed', ?, 'stale')",
            (f"receipt-a-{suffix}", f"run-a-{suffix}"),
        )
        connection.commit()
    with closing(sqlite3.connect(sqlite_path)) as connection:
        connection.row_factory = sqlite3.Row
        publish_fixture_tables_to_duckdb(
            connection,
            duckdb_path,
            [FixtureTable(
                workspace_id="workspace-a",
                table_key="orders",
                physical_table="data_workspace_a",
                columns=(("workspace_id", "VARCHAR"), ("amount", "DOUBLE")),
                rows=(("changed-customer", amount),),
                data_version=int(suffix),
                display_name="Orders",
            )],
            reset=False,
        )


with tempfile.TemporaryDirectory(prefix="aibi-c-workspace-recovery-") as temporary:
    temp = Path(temporary)
    sqlite_path = temp / "runtime.sqlite"
    duckdb_path = temp / "runtime.duckdb"
    recovery_root = temp / "workspace-recovery"
    os.environ["AIBI_DATASET_OBJECT_ROOT"] = str(temp / "runtime-dataset-objects-v2")
    build_sqlite(sqlite_path)
    with closing(sqlite3.connect(sqlite_path)) as fixture_connection:
        fixture_connection.row_factory = sqlite3.Row
        publish_fixture_tables_to_duckdb(
            fixture_connection,
            duckdb_path,
            [FixtureTable(
                workspace_id="workspace-a",
                table_key="orders",
                physical_table="data_workspace_a",
                columns=(("workspace_id", "VARCHAR"), ("amount", "DOUBLE")),
                rows=(("historical-customer", 5.0),),
                data_version=0,
                display_name="Orders",
            )],
            reset=True,
        )
        publish_fixture_tables_to_duckdb(
            fixture_connection,
            duckdb_path,
            [
                FixtureTable(
                    workspace_id="workspace-a",
                    table_key="orders",
                    physical_table="data_workspace_a",
                    columns=(("workspace_id", "VARCHAR"), ("amount", "DOUBLE")),
                    rows=(("customer-east", 10.0), ("customer-west", 20.0)),
                    display_name="Orders",
                ),
                FixtureTable(
                    workspace_id="workspace-b",
                    table_key="ledger",
                    physical_table="data_workspace_b",
                    columns=(("workspace_id", "VARCHAR"), ("amount", "DOUBLE")),
                    rows=(("workspace-a", 99.0),),
                    display_name="Ledger",
                ),
            ],
            reset=True,
        )

    def open_db() -> sqlite3.Connection:
        connection = sqlite3.connect(sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection

    service = WorkspaceRecoveryService(
        open_db=open_db,
        sqlite_path=sqlite_path,
        duckdb_path=duckdb_path,
        recovery_root=recovery_root,
    )

    before_a = service._state("workspace-a")
    before_b = service._state("workspace-b")
    with closing(open_db()) as connection:
        baseline_dataset_version = active_dataset_version(connection, "workspace-a", "orders")
    baseline_version_id = str((baseline_dataset_version or {}).get("versionId") or "")
    preview = service.create("workspace-a", "Baseline before replacement", "create-baseline")
    check("create-is-dry-run-first", preview.get("dryRun") is True and preview.get("requiresConfirmation") is True and not recovery_root.exists(), preview)
    point_key = str(preview["recoveryPlan"]["recoveryPointKey"])
    created = service.create(
        "workspace-a",
        "Baseline before replacement",
        "create-baseline",
        confirm=True,
        expected_plan_fingerprint=str(preview["recoveryPlan"]["planFingerprint"]),
    )
    point = created["recoveryPoint"]
    check("confirmed-create-publishes-ready-verified-point", created.get("changed") is True and point.get("status") == "ready" and point.get("verified") is True, created)
    with closing(open_db()) as connection:
        # A recovery point may contain an in-flight job, but restore must never
        # resurrect it over later terminal/audit state.
        connection.execute("INSERT INTO analysis_jobs VALUES('workspace-a', 'job-after-point', 'succeeded')")
        connection.execute("INSERT INTO analysis_job_events VALUES('workspace-a', 'job-after-point', 1, 'succeeded')")
        connection.execute("INSERT INTO import_workspace_leases VALUES('workspace-a', 'job-after-point', 'released-token', 0)")
        connection.execute("INSERT INTO reviewed_publications VALUES('workspace-a', 'publication-after-point', 'current')")
        connection.execute("INSERT INTO evidence_ledger_entries VALUES('workspace-a', 'publication-after-point', 1, ?)", ("a" * 64,))
        connection.execute("INSERT INTO query_plan_receipts VALUES('workspace-a', 'receipt-after-point', 'executed', 'run-a-1', 'current')")
        connection.execute("INSERT INTO source_activation_journals VALUES('workspace-a', 'activation-after-point', 'job-after-point', 'finalized')")
        connection.commit()
    replay = service.create(
        "workspace-a",
        "Baseline before replacement",
        "create-baseline",
        confirm=True,
        expected_plan_fingerprint=str(preview["recoveryPlan"]["planFingerprint"]),
    )
    check("create-request-key-is-idempotent", replay.get("changed") is False and replay.get("idempotentReplay") is True and replay.get("recoveryPoint", {}).get("recoveryPointKey") == point_key, replay)
    conflicting_preview = service.create("workspace-a", "Different intent", "create-baseline")
    expect_error(
        "same-request-key-with-different-input-is-rejected",
        "RECOVERY_REQUEST_KEY_CONFLICT",
        lambda: service.create(
            "workspace-a",
            "Different intent",
            "create-baseline",
            confirm=True,
            expected_plan_fingerprint=str(conflicting_preview["recoveryPlan"]["planFingerprint"]),
        ),
    )
    stale_preview = service.create("workspace-a", "Stale preview", "create-stale-preview")
    with closing(open_db()) as connection:
        connection.execute("UPDATE dashboards SET name = 'Transient change' WHERE workspace_id = 'workspace-a'")
        connection.commit()
    expect_error(
        "workspace-drift-invalidates-create-preview",
        "RECOVERY_PLAN_STALE",
        lambda: service.create(
            "workspace-a",
            "Stale preview",
            "create-stale-preview",
            confirm=True,
            expected_plan_fingerprint=str(stale_preview["recoveryPlan"]["planFingerprint"]),
        ),
    )
    with closing(open_db()) as connection:
        connection.execute("UPDATE dashboards SET name = 'Original A' WHERE workspace_id = 'workspace-a'")
        connection.commit()
    point_dir = recovery_root / _workspace_bucket("workspace-a") / point_key
    with closing(sqlite3.connect(point_dir / SQLITE_ARTIFACT)) as snapshot:
        snapshot_workspaces = [row[0] for row in snapshot.execute("SELECT id FROM workspaces ORDER BY id")]
        snapshot_binding = snapshot.execute(
            "SELECT table_key, active_version_id FROM table_registry ORDER BY table_key"
        ).fetchall()
        snapshot_versions = snapshot.execute(
            "SELECT version_id FROM dataset_versions WHERE workspace_id = 'workspace-a' ORDER BY version_id"
        ).fetchall()
        snapshot_files = snapshot.execute(
            "SELECT version_id, object_key, object_hash FROM dataset_version_files ORDER BY version_id, ordinal"
        ).fetchall()
        snapshot_lineage = snapshot.execute(
            "SELECT id FROM source_runs WHERE workspace_id = 'workspace-a' ORDER BY id"
        ).fetchall()
        other_dashboard = snapshot.execute("SELECT COUNT(*) FROM dashboards WHERE workspace_id = 'workspace-b'").fetchone()[0]
        other_physical = snapshot.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='data_workspace_b'").fetchone()
        target_physical = snapshot.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='data_workspace_a'").fetchone()
        global_rows = snapshot.execute("SELECT COUNT(*) FROM global_settings").fetchone()[0]
    check(
        "sqlite-artifact-is-workspace-isolated-and-contains-only-dataset-pointers",
        snapshot_workspaces == ["workspace-a"]
        and len(snapshot_binding) == 1
        and snapshot_binding[0][0] == "orders"
        and bool(snapshot_binding[0][1])
        and [row[0] for row in snapshot_versions] == [baseline_version_id]
        and len(snapshot_files) == 1
        and snapshot_files[0][0] == baseline_version_id
        and bool(snapshot_files[0][1])
        and bool(snapshot_files[0][2])
        and [row[0] for row in snapshot_lineage] == ["run-a-1"]
        and other_dashboard == 0
        and other_physical is None
        and target_physical is None
        and global_rows == 0,
        {
            "workspaces": snapshot_workspaces,
            "binding": snapshot_binding,
            "versions": snapshot_versions,
            "files": snapshot_files,
            "lineage": snapshot_lineage,
            "otherDashboard": other_dashboard,
            "otherPhysical": other_physical,
            "targetPhysical": target_physical,
            "globalRows": global_rows,
        },
    )
    import duckdb  # type: ignore
    with duckdb.connect(str(point_dir / DUCKDB_ARTIFACT), read_only=True) as snapshot_duck:
        dataset_manifest = snapshot_duck.execute(
            "SELECT logical_table, version_id FROM __aibi_replica_manifest ORDER BY logical_table"
        ).fetchall()
        point_object_keys = json.loads(snapshot_duck.execute(
            "SELECT object_keys_json FROM __aibi_replica_manifest ORDER BY logical_table LIMIT 1"
        ).fetchone()[0])
        snapshot_rows = snapshot_duck.execute(
            "SELECT workspace_id, amount FROM data_workspace_a ORDER BY amount"
        ).fetchall()
        other_duck = snapshot_duck.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'data_workspace_b'").fetchone()
    check(
        "duckdb-artifact-only-contains-workspace-dataset-view",
        len(dataset_manifest) == 1
        and dataset_manifest[0][0] == "data_workspace_a"
        and bool(dataset_manifest[0][1])
        and snapshot_rows == [("customer-east", 10.0), ("customer-west", 20.0)]
        and other_duck is None,
        {"manifest": dataset_manifest, "rows": snapshot_rows, "other": other_duck},
    )
    point_object = resolve_object_key(str(point_object_keys[0]))
    hidden_object = point_object.with_name(point_object.name + ".missing")
    os.replace(point_object, hidden_object)
    try:
        expect_error(
            "missing-parquet-object-invalidates-recovery-point",
            "RECOVERY_DATASET_OBJECT_INTEGRITY_FAILED",
            lambda: service.inspect("workspace-a", point_key, verify=True),
        )
    finally:
        os.replace(hidden_object, point_object)

    listing = service.list("workspace-a", limit=5, verify=True)
    check("list-is-bounded-and-verified", listing.get("count") == 1 and listing.get("health") == "ready" and listing.get("recoveryPoints", [])[0].get("verified") is True, listing)
    check("public-contract-exposes-no-absolute-path", str(temp) not in json.dumps(listing, ensure_ascii=False), listing)
    cross_listing = service.list("workspace-b")
    check("other-workspace-does-not-list-the-point", cross_listing.get("count") == 0, cross_listing)
    expect_error("cross-workspace-point-lookup-is-blocked", "RECOVERY_POINT_NOT_FOUND", lambda: service.inspect("workspace-b", point_key))
    expect_error("path-traversal-key-is-blocked", "RECOVERY_POINT_KEY_INVALID", lambda: service.inspect("workspace-a", "../../escape"))
    with patch("workspace_recovery_service.Path.is_symlink", return_value=True):
        expect_error("symlink-root-is-blocked", "RECOVERY_SYMLINK_BLOCKED", lambda: _ensure_root(recovery_root, create=False))

    mutate_workspace_a(sqlite_path, duckdb_path, suffix="2", amount=200.0)
    with closing(open_db()) as connection:
        connection.execute("DELETE FROM dataset_version_files WHERE version_id = ?", (baseline_version_id,))
        connection.execute("DELETE FROM dataset_versions WHERE version_id = ?", (baseline_version_id,))
        connection.execute(
            "DELETE FROM source_runs WHERE workspace_id = 'workspace-a' AND id IN ('run-a-1', 'run-a-history')"
        )
        connection.commit()
    changed_a = service._state("workspace-a")
    check("fixture-mutates-the-target-workspace", changed_a["fingerprint"] != before_a["fingerprint"], changed_a)
    comparison = service.compare("workspace-a", point_key)
    changed_tables = [item for item in comparison.get("changes", []) if item.get("change") != "unchanged"]
    check(
        "comparison-verifies-the-point-and-exposes-only-table-version-impact",
        comparison.get("schema") == "aibi-workspace-recovery-comparison/v1"
        and comparison.get("verified") is True
        and comparison.get("exposesBusinessRows") is False
        and comparison.get("changedCount") == 1
        and changed_tables == [{"tableKey": "orders", "change": "version-change", "currentDataVersion": 2, "targetDataVersion": 1}],
        comparison,
    )
    check("comparison-exposes-no-local-path-or-business-row", str(temp) not in json.dumps(comparison, ensure_ascii=False) and "changed-customer" not in json.dumps(comparison, ensure_ascii=False), comparison)
    restore_preview = service.restore("workspace-a", point_key, "restore-baseline")
    check("restore-preview-declares-safety-point", restore_preview["recoveryPlan"]["requiresSafetyPoint"] is True and restore_preview.get("dryRun") is True, restore_preview)
    restored = service.restore(
        "workspace-a",
        point_key,
        "restore-baseline",
        confirm=True,
        expected_plan_fingerprint=str(restore_preview["recoveryPlan"]["planFingerprint"]),
    )
    after_restore_a = service._state("workspace-a")
    after_restore_b = service._state("workspace-b")
    with closing(open_db()) as connection:
        dashboard_name = connection.execute("SELECT name FROM dashboards WHERE workspace_id = 'workspace-a'").fetchone()[0]
        relationship = connection.execute("SELECT validation_json FROM relationships WHERE workspace_id = 'workspace-a'").fetchone()[0]
        freshness_rows = connection.execute(
            "SELECT receipt_key, source_run_id, freshness FROM query_plan_receipts WHERE workspace_id = 'workspace-a' ORDER BY receipt_key"
        ).fetchall()
        restored_active_version = active_dataset_version(connection, "workspace-a", "orders")
        restored_source_runs = connection.execute(
            "SELECT id FROM source_runs WHERE workspace_id = 'workspace-a' ORDER BY id"
        ).fetchall()
        restored_workspace_run = connection.execute(
            "SELECT current_source_run_id FROM workspaces WHERE id = 'workspace-a'"
        ).fetchone()[0]
    restored_files = list((restored_active_version or {}).get("files") or [])
    restored_object = resolve_object_key(str(restored_files[0]["objectKey"])) if restored_files else None
    with duckdb.connect(str(duckdb_path), read_only=True) as connection:
        restored_rows = connection.execute(
            "SELECT workspace_id, amount FROM data_workspace_a ORDER BY amount"
        ).fetchall()
    check(
        "restore-rehydrates-source-relationship-dashboard-and-query-freshness",
        restored.get("confirmed") is True
        and restored.get("safetyRecoveryPoint", {}).get("status") == "ready"
        and after_restore_a["fingerprint"] == before_a["fingerprint"]
        and dashboard_name == "Original A"
        and json.loads(relationship)["status"] == "validated"
        and ("receipt-a", "run-a-1", "current") in [tuple(item) for item in freshness_rows]
        and ("receipt-a-2", "run-a-2", "stale") in [tuple(item) for item in freshness_rows]
        and (restored_active_version or {}).get("versionId") == baseline_version_id
        and len(restored_files) == 1
        and restored_object is not None
        and restored_object.is_file()
        and file_sha256(restored_object) == restored_files[0]["objectHash"]
        and restored_workspace_run == "run-a-1"
        and [row[0] for row in restored_source_runs] == ["run-a-1", "run-a-2"]
        and restored_rows == [("customer-east", 10.0), ("customer-west", 20.0)],
        {
            "restored": restored,
            "dashboard": dashboard_name,
            "relationship": relationship,
            "freshness": [tuple(item) for item in freshness_rows],
            "activeVersion": restored_active_version,
            "sourceRuns": [tuple(item) for item in restored_source_runs],
            "rows": restored_rows,
        },
    )
    check("restore-does-not-change-other-workspace", after_restore_b["fingerprint"] == before_b["fingerprint"], {"before": before_b, "after": after_restore_b})
    restore_replay = service.restore(
        "workspace-a",
        point_key,
        "restore-baseline",
        confirm=True,
        expected_plan_fingerprint=str(restore_preview["recoveryPlan"]["planFingerprint"]),
    )
    check("restore-request-key-is-idempotent", restore_replay.get("changed") is False and restore_replay.get("idempotentReplay") is True, restore_replay)
    with closing(open_db()) as connection:
        preserved = {
            "publication": connection.execute("SELECT status FROM reviewed_publications WHERE workspace_id = 'workspace-a' AND publication_key = 'publication-after-point'").fetchone(),
            "ledger": connection.execute("SELECT entry_hash FROM evidence_ledger_entries WHERE workspace_id = 'workspace-a' AND publication_key = 'publication-after-point'").fetchone(),
            "receipt": connection.execute("SELECT status FROM query_plan_receipts WHERE workspace_id = 'workspace-a' AND receipt_key = 'receipt-after-point'").fetchone(),
            "job": connection.execute("SELECT status FROM analysis_jobs WHERE workspace_id = 'workspace-a' AND job_key = 'job-after-point'").fetchone(),
            "events": connection.execute("SELECT COUNT(*) FROM analysis_job_events WHERE workspace_id = 'workspace-a' AND job_key = 'job-after-point'").fetchone(),
            "activation": connection.execute("SELECT phase FROM source_activation_journals WHERE workspace_id = 'workspace-a' AND journal_key = 'activation-after-point'").fetchone(),
            "lease": connection.execute("SELECT active FROM import_workspace_leases WHERE workspace_id = 'workspace-a'").fetchone(),
        }
    check(
        "restore-preserves-append-only-evidence-and-runtime-control-state",
        preserved["publication"] is not None
        and preserved["ledger"] is not None
        and preserved["receipt"] is not None
        and preserved["job"] is not None and preserved["job"][0] == "succeeded"
        and preserved["events"] is not None and int(preserved["events"][0]) == 1
        and preserved["activation"] is not None and preserved["activation"][0] == "finalized"
        and preserved["lease"] is not None and int(preserved["lease"][0]) == 0,
        preserved,
    )

    mutate_workspace_a(sqlite_path, duckdb_path, suffix="3", amount=300.0)
    with closing(open_db()) as connection:
        republished_version = active_dataset_version(connection, "workspace-a", "orders")
    republished_files = list((republished_version or {}).get("files") or [])
    republished_object = resolve_object_key(str(republished_files[0]["objectKey"])) if republished_files else None
    check(
        "restored-version-catalog-supports-subsequent-dataset-republish",
        (republished_version or {}).get("versionId") != baseline_version_id
        and len(republished_files) == 1
        and republished_object is not None
        and republished_object.is_file()
        and file_sha256(republished_object) == republished_files[0]["objectHash"],
        republished_version,
    )
    before_interrupted_restore = service._state("workspace-a")
    interrupted_preview = service.restore("workspace-a", point_key, "restore-interrupted")
    interrupted_error = expect_error(
        "interrupted-restore-applies-safety-point",
        "RECOVERY_RESTORE_ROLLED_BACK",
        lambda: service.restore(
            "workspace-a",
            point_key,
            "restore-interrupted",
            confirm=True,
            expected_plan_fingerprint=str(interrupted_preview["recoveryPlan"]["planFingerprint"]),
            fail_at="after_duckdb_restore",
        ),
    )
    after_interrupted_restore = service._state("workspace-a")
    check(
        "failed-restore-preserves-pre-restore-state-and-recovery-action",
        interrupted_error is not None
        and bool(interrupted_error.recovery_action)
        and after_interrupted_restore["fingerprint"] == before_interrupted_restore["fingerprint"],
        {"before": before_interrupted_restore, "after": after_interrupted_restore, "action": interrupted_error.recovery_action if interrupted_error else ""},
    )

    mutate_workspace_a(sqlite_path, duckdb_path, suffix="4", amount=400.0)
    response_loss_preview = service.restore("workspace-a", point_key, "restore-response-loss")
    try:
        service.restore(
            "workspace-a",
            point_key,
            "restore-response-loss",
            confirm=True,
            expected_plan_fingerprint=str(response_loss_preview["recoveryPlan"]["planFingerprint"]),
            fail_at="after_applied_journal",
        )
        check("applied-restore-response-loss-is-injected", False, "no error")
    except RuntimeError:
        fenced_before_reconcile = unfinished_recovery_fences(recovery_root)
        reconciled_response_loss = service.reconcile_unfinished_restores()
        response_loss_replay = service.restore(
            "workspace-a",
            point_key,
            "restore-response-loss",
            confirm=True,
            expected_plan_fingerprint=str(response_loss_preview["recoveryPlan"]["planFingerprint"]),
        )
        check(
            "applied-restore-response-loss-repairs-receipt",
            bool(fenced_before_reconcile)
            and reconciled_response_loss.get("ok") is True
            and response_loss_replay.get("idempotentReplay") is True
            and response_loss_replay.get("changed") is False
            and service._state("workspace-a")["fingerprint"] == before_a["fingerprint"]
            and not unfinished_recovery_fences(recovery_root),
            {"fences": fenced_before_reconcile, "reconcile": reconciled_response_loss, "replay": response_loss_replay},
        )

    interrupted_create_preview = service.create("workspace-a", "Interrupted create", "create-interrupted")
    try:
        service.create(
            "workspace-a",
            "Interrupted create",
            "create-interrupted",
            confirm=True,
            expected_plan_fingerprint=str(interrupted_create_preview["recoveryPlan"]["planFingerprint"]),
            fail_at="before_publish",
        )
        check("interrupted-create-is-rejected", False, "no error")
    except RuntimeError:
        workspace_root = recovery_root / _workspace_bucket("workspace-a")
        staging = [item.name for item in workspace_root.iterdir() if item.name.startswith(".staging-")]
        check("interrupted-create-removes-unpublished-staging", not staging, staging)

    low_space_preview = service.create("workspace-a", "Low space", "create-low-space")
    DiskUsage = namedtuple("DiskUsage", "total used free")
    with patch("workspace_recovery_service.shutil.disk_usage", return_value=DiskUsage(100, 99, 1)):
        expect_error(
            "insufficient-disk-space-fails-before-artifact-write",
            "RECOVERY_DISK_SPACE_INSUFFICIENT",
            lambda: service.create(
                "workspace-a",
                "Low space",
                "create-low-space",
                confirm=True,
                expected_plan_fingerprint=str(low_space_preview["recoveryPlan"]["planFingerprint"]),
            ),
        )

    corrupt_preview = service.create("workspace-a", "Corruption fixture", "create-corrupt")
    corrupt_created = service.create(
        "workspace-a",
        "Corruption fixture",
        "create-corrupt",
        confirm=True,
        expected_plan_fingerprint=str(corrupt_preview["recoveryPlan"]["planFingerprint"]),
    )
    corrupt_key = str(corrupt_created["recoveryPoint"]["recoveryPointKey"])
    corrupt_file = recovery_root / _workspace_bucket("workspace-a") / corrupt_key / SQLITE_ARTIFACT
    with corrupt_file.open("ab") as handle:
        handle.write(b"tamper")
    expect_error("artifact-sha256-mismatch-blocks-restore", "RECOVERY_ARTIFACT_HASH_MISMATCH", lambda: service.inspect("workspace-a", corrupt_key, verify=True))

    manifest_preview = service.create("workspace-a", "Manifest corruption fixture", "create-manifest-corrupt")
    manifest_created = service.create(
        "workspace-a",
        "Manifest corruption fixture",
        "create-manifest-corrupt",
        confirm=True,
        expected_plan_fingerprint=str(manifest_preview["recoveryPlan"]["planFingerprint"]),
    )
    manifest_key = str(manifest_created["recoveryPoint"]["recoveryPointKey"])
    manifest_path = recovery_root / _workspace_bucket("workspace-a") / manifest_key / "manifest.json"
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_payload["reason"] = "tampered"
    manifest_path.write_text(json.dumps(manifest_payload), encoding="utf-8")
    expect_error("manifest-content-tamper-is-blocked", "RECOVERY_MANIFEST_HASH_MISMATCH", lambda: service.inspect("workspace-a", manifest_key, verify=True))

    delete_crash_preview = service.create("workspace-a", "Delete crash fixture", "create-delete-crash")
    delete_crash_created = service.create(
        "workspace-a",
        "Delete crash fixture",
        "create-delete-crash",
        confirm=True,
        expected_plan_fingerprint=str(delete_crash_preview["recoveryPlan"]["planFingerprint"]),
    )
    delete_crash_key = str(delete_crash_created["recoveryPoint"]["recoveryPointKey"])
    delete_crash_plan = service.delete("workspace-a", delete_crash_key, "delete-crash")
    try:
        service.delete(
            "workspace-a",
            delete_crash_key,
            "delete-crash",
            confirm=True,
            expected_plan_fingerprint=str(delete_crash_plan["recoveryPlan"]["planFingerprint"]),
            fail_at="after_delete_rename",
        )
        check("delete-tombstone-crash-is-injected", False, "no error")
    except RuntimeError:
        delete_reconcile = service.reconcile_unfinished_restores()
        delete_crash_replay = service.delete(
            "workspace-a",
            delete_crash_key,
            "delete-crash",
            confirm=True,
            expected_plan_fingerprint=str(delete_crash_plan["recoveryPlan"]["planFingerprint"]),
        )
        workspace_recovery_root = recovery_root / _workspace_bucket("workspace-a")
        delete_tombstones = [path.name for path in workspace_recovery_root.iterdir() if path.name.startswith(".deleting-")]
        check(
            "prepared-delete-crash-finishes-deterministically",
            delete_reconcile.get("ok") is True
            and delete_crash_replay.get("idempotentReplay") is True
            and delete_crash_replay.get("changed") is False
            and not delete_tombstones,
            {"reconcile": delete_reconcile, "replay": delete_crash_replay, "tombstones": delete_tombstones},
        )

    delete_preview = service.delete("workspace-a", point_key, "delete-baseline")
    deleted = service.delete(
        "workspace-a",
        point_key,
        "delete-baseline",
        confirm=True,
        expected_plan_fingerprint=str(delete_preview["recoveryPlan"]["planFingerprint"]),
    )
    delete_replay = service.delete(
        "workspace-a",
        point_key,
        "delete-baseline",
        confirm=True,
        expected_plan_fingerprint=str(delete_preview["recoveryPlan"]["planFingerprint"]),
    )
    check(
        "delete-is-dry-run-confirmed-and-idempotent",
        deleted.get("changed") is True and delete_replay.get("changed") is False and delete_replay.get("idempotentReplay") is True,
        {"deleted": deleted, "replay": delete_replay},
    )

    journal_path = next((recovery_root / _workspace_bucket("workspace-a") / ".operations").glob("journal_*.json"))
    journal_payload = json.loads(journal_path.read_text(encoding="utf-8"))
    journal_payload["safetyRecoveryPointKey"] = "rp_" + "0" * 24
    journal_path.write_text(json.dumps(journal_payload), encoding="utf-8")
    expect_error(
        "recovery-journal-content-tamper-is-blocked",
        "RECOVERY_JOURNAL_INTEGRITY_FAILED",
        lambda: unfinished_recovery_fences(recovery_root),
    )


failed = [item for item in checks if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-workspace-recovery-verify/v1",
    "generatedBy": "scripts/verify-workspace-recovery.py",
    "checks": checks,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
