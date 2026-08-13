from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from bi_cli_schema import ensure_schema  # noqa: E402
from reviewed_publication_service import (  # noqa: E402
    LEDGER_GENESIS_HASH,
    _append_ledger_entry,
    fingerprint,
    stable_json,
)
from workspace_command_service import workspace_delete_command  # noqa: E402
from workspace_recovery_service import (  # noqa: E402
    SQLITE_ARTIFACT,
    WorkspaceRecoveryError,
    WorkspaceRecoveryService,
    _workspace_bucket,
    _workspace_state,
    unfinished_recovery_fences,
)


NOW = "2026-08-13T12:00:00+00:00"
TARGET = "delete-target"
OTHER = "delete-control"
checks: list[dict[str, Any]] = []


def check(label: str, ok: bool, detail: Any = None) -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": None if ok else detail})


def expect_error(label: str, code: str, action: Any) -> None:
    try:
        action()
    except WorkspaceRecoveryError as error:
        check(label, error.code == code, {"expected": code, "actual": error.code, "message": str(error)})
    except Exception as error:
        check(label, False, {"expected": code, "actual": type(error).__name__, "message": str(error)})
    else:
        check(label, False, {"expected": code, "actual": "no-error"})


def add_publication(connection: sqlite3.Connection, workspace_id: str, publication_key: str) -> None:
    title = "Reviewed workspace evidence"
    content: dict[str, Any] = {"summary": "Reviewed before workspace lifecycle deletion."}
    input_contract: dict[str, Any] = {}
    content_fingerprint = fingerprint({"title": title, "content": content})
    input_fingerprint = fingerprint(input_contract)
    connection.execute("BEGIN IMMEDIATE")
    connection.execute(
        """
        INSERT INTO reviewed_publications(
          publication_key, workspace_id, memory_key, query_receipt_key, unit_key, title,
          status, content_json, content_fingerprint, input_contract_json, input_fingerprint,
          ledger_head_hash, created_at, updated_at, reviewed_at, deprecated_at, deprecation_reason
        ) VALUES(?, ?, 'memory-fixture', 'receipt-fixture', 'unit-fixture', ?, 'current', ?, ?, ?, ?, '', ?, ?, ?, NULL, '')
        """,
        (
            publication_key,
            workspace_id,
            title,
            stable_json(content),
            content_fingerprint,
            stable_json(input_contract),
            input_fingerprint,
            NOW,
            NOW,
            NOW,
        ),
    )
    entry = _append_ledger_entry(
        connection,
        workspace_id=workspace_id,
        publication_key=publication_key,
        kind="publication_created",
        payload_fingerprint=fingerprint({
            "contentFingerprint": content_fingerprint,
            "inputFingerprint": input_fingerprint,
        }),
        evidence_refs=[],
        created_at=NOW,
        expected_head_hash=LEDGER_GENESIS_HASH,
    )
    connection.execute(
        "UPDATE reviewed_publications SET ledger_head_hash = ? WHERE workspace_id = ? AND publication_key = ?",
        (entry["entryHash"], workspace_id, publication_key),
    )
    connection.commit()


class Fixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=False)
        self.sqlite_path = root / "runtime.sqlite"
        self.duckdb_path = root / "runtime.duckdb"
        self.recovery_root = root / "workspace-recovery"
        self._build_sqlite()
        self._build_duckdb()
        self.service = WorkspaceRecoveryService(
            open_db=self.open_db,
            sqlite_path=self.sqlite_path,
            duckdb_path=self.duckdb_path,
            recovery_root=self.recovery_root,
        )

    def open_db(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _build_sqlite(self) -> None:
        with closing(sqlite3.connect(self.sqlite_path)) as connection:
            connection.row_factory = sqlite3.Row
            ensure_schema(connection)
            connection.execute("UPDATE system_flags SET value = 'default' WHERE key = 'active_workspace_id'")
            connection.execute(
                "INSERT INTO workspaces(id, name, current_source_run_id, created_at) VALUES(?, ?, NULL, ?)",
                (TARGET, "Delete Target", NOW),
            )
            connection.execute(
                "INSERT INTO workspaces(id, name, current_source_run_id, created_at) VALUES(?, ?, NULL, ?)",
                (OTHER, "Delete Control", NOW),
            )
            connection.execute("CREATE TABLE target_physical(order_id TEXT PRIMARY KEY, amount REAL)")
            connection.execute("INSERT INTO target_physical VALUES('t-1', 10), ('t-2', 20)")
            connection.execute("CREATE TABLE control_physical(order_id TEXT PRIMARY KEY, amount REAL)")
            connection.execute("INSERT INTO control_physical VALUES('c-1', 99)")
            connection.execute(
                """
                INSERT INTO table_registry(
                  table_key, workspace_id, display_name, physical_table, source_file,
                  row_count, column_count, created_at, data_version, updated_at
                ) VALUES('orders', ?, 'Orders', 'target_physical', 'redacted', 2, 2, ?, 1, ?)
                """,
                (TARGET, NOW, NOW),
            )
            connection.execute(
                """
                INSERT INTO table_registry(
                  table_key, workspace_id, display_name, physical_table, source_file,
                  row_count, column_count, created_at, data_version, updated_at
                ) VALUES('orders', ?, 'Orders', 'control_physical', 'redacted', 1, 2, ?, 1, ?)
                """,
                (OTHER, NOW, NOW),
            )
            connection.commit()
            add_publication(connection, TARGET, "publication-delete-audit")

    def _build_duckdb(self) -> None:
        import duckdb  # type: ignore

        with duckdb.connect(str(self.duckdb_path)) as connection:
            connection.execute("CREATE TABLE __aibi_schema_metadata(key VARCHAR PRIMARY KEY, value VARCHAR NOT NULL)")
            connection.execute("INSERT INTO __aibi_schema_metadata VALUES ('schema_version', '1')")
            connection.execute(
                "CREATE TABLE __aibi_replica_manifest("
                "logical_table VARCHAR PRIMARY KEY, source_version VARCHAR NOT NULL, replica_table VARCHAR NOT NULL, "
                "row_count BIGINT NOT NULL, published_at VARCHAR NOT NULL)"
            )
            connection.execute("CREATE TABLE target_replica(order_id VARCHAR, amount DOUBLE)")
            connection.execute("INSERT INTO target_replica VALUES ('t-1', 10), ('t-2', 20)")
            connection.execute("CREATE VIEW target_physical AS SELECT * FROM target_replica")
            connection.execute("INSERT INTO __aibi_replica_manifest VALUES ('target_physical', '1', 'target_replica', 2, ?)", [NOW])
            connection.execute("CREATE TABLE control_replica(order_id VARCHAR, amount DOUBLE)")
            connection.execute("INSERT INTO control_replica VALUES ('c-1', 99)")
            connection.execute("CREATE VIEW control_physical AS SELECT * FROM control_replica")
            connection.execute("INSERT INTO __aibi_replica_manifest VALUES ('control_physical', '1', 'control_replica', 1, ?)", [NOW])

    def args(self, *, request_key: str, yes: bool = False, expected_plan: str = "", fail_at: str = "") -> argparse.Namespace:
        return argparse.Namespace(
            workspace=TARGET,
            request_key=request_key,
            expected_plan=expected_plan,
            yes=yes,
            fail_at=fail_at,
        )

    def command(self, args: argparse.Namespace) -> dict[str, Any]:
        return workspace_delete_command(
            args,
            open_db=self.open_db,
            sqlite_path=self.sqlite_path,
            duckdb_path=self.duckdb_path,
            recovery_root=self.recovery_root,
        )

    def state(self, workspace_id: str) -> str:
        with closing(self.open_db()) as connection:
            return str(_workspace_state(connection, workspace_id, self.duckdb_path)["fingerprint"])


def run_success_case(root: Path) -> None:
    fixture = Fixture(root)
    before_target = fixture.state(TARGET)
    before_other = fixture.state(OTHER)
    with closing(fixture.open_db()) as connection:
        publication_before = dict(connection.execute(
            "SELECT status, deprecation_reason, ledger_head_hash FROM reviewed_publications WHERE workspace_id = ?",
            (TARGET,),
        ).fetchone())
        ledger_count_before = int(connection.execute(
            "SELECT COUNT(*) FROM evidence_ledger_entries WHERE workspace_id = ?",
            (TARGET,),
        ).fetchone()[0])
    preview = fixture.command(fixture.args(request_key="delete-success"))
    plan_fingerprint = str(preview["deletePlan"]["planFingerprint"])
    expect_error(
        "workspace-delete-confirm-requires-request-key",
        "WORKSPACE_DELETE_CONFIRMATION_REQUIRED",
        lambda: fixture.command(fixture.args(request_key="", yes=True, expected_plan=plan_fingerprint)),
    )
    expect_error(
        "workspace-delete-confirm-requires-exact-plan",
        "WORKSPACE_DELETE_CONFIRMATION_REQUIRED",
        lambda: fixture.command(fixture.args(request_key="delete-success", yes=True)),
    )
    with closing(fixture.open_db()) as connection:
        publication_after_preview = dict(connection.execute(
            "SELECT status, deprecation_reason, ledger_head_hash FROM reviewed_publications WHERE workspace_id = ?",
            (TARGET,),
        ).fetchone())
        ledger_count_after_preview = int(connection.execute(
            "SELECT COUNT(*) FROM evidence_ledger_entries WHERE workspace_id = ?",
            (TARGET,),
        ).fetchone()[0])
    check(
        "workspace-delete-dry-run-is-zero-write",
        preview.get("dryRun") is True
        and preview.get("requiresConfirmation") is True
        and fixture.state(TARGET) == before_target
        and publication_after_preview == publication_before
        and ledger_count_after_preview == ledger_count_before
        and not fixture.recovery_root.exists(),
        preview,
    )
    confirmed = fixture.command(fixture.args(request_key="delete-success", yes=True, expected_plan=plan_fingerprint))
    recovery_point_key = str(confirmed.get("auditRecoveryPoint", {}).get("recoveryPointKey") or "")
    snapshot = fixture.recovery_root / _workspace_bucket(TARGET) / recovery_point_key / SQLITE_ARTIFACT
    with closing(sqlite3.connect(snapshot)) as connection:
        tombstone_events = int(connection.execute(
            "SELECT COUNT(*) FROM evidence_ledger_entries WHERE workspace_id = ? AND kind = 'publication_tombstoned'",
            (TARGET,),
        ).fetchone()[0])
        snapshot_reason = str(connection.execute(
            "SELECT deprecation_reason FROM reviewed_publications WHERE workspace_id = ?",
            (TARGET,),
        ).fetchone()[0])
        snapshot_workspaces = [str(row[0]) for row in connection.execute("SELECT id FROM workspaces ORDER BY id")]
    with closing(fixture.open_db()) as connection:
        target_exists = bool(connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (TARGET,)).fetchone())
    replay = fixture.command(fixture.args(request_key="delete-success", yes=True, expected_plan=plan_fingerprint))
    check(
        "workspace-delete-tombstones-once-and-snapshots-audit",
        confirmed.get("lifecycleStatus") == "completed"
        and confirmed.get("tombstonedPublicationCount") == 1
        and tombstone_events == 1
        and snapshot_reason.startswith("Tombstoned:")
        and snapshot_workspaces == [TARGET]
        and not target_exists,
        {"confirmed": confirmed, "snapshotReason": snapshot_reason, "snapshotWorkspaces": snapshot_workspaces},
    )
    check(
        "workspace-delete-same-key-replays-after-workspace-row-is-gone",
        replay.get("idempotentReplay") is True and replay.get("changed") is False and replay.get("lifecycleStatus") == "completed",
        replay,
    )
    check(
        "workspace-delete-preserves-other-workspace-fingerprint",
        fixture.state(OTHER) == before_other,
        {"before": before_other, "after": fixture.state(OTHER)},
    )
    expect_error(
        "workspace-delete-same-key-rejects-different-plan",
        "WORKSPACE_DELETE_REQUEST_KEY_CONFLICT",
        lambda: fixture.command(fixture.args(request_key="delete-success", yes=True, expected_plan="0" * 64)),
    )


def run_bad_ledger_case(root: Path) -> None:
    fixture = Fixture(root)
    with closing(fixture.open_db()) as connection:
        connection.execute(
            "UPDATE evidence_ledger_entries SET entry_hash = ? WHERE workspace_id = ? AND sequence = 1",
            ("f" * 64, TARGET),
        )
        connection.commit()
    preview = fixture.command(fixture.args(request_key="delete-bad-ledger"))
    before_other = fixture.state(OTHER)
    expect_error(
        "workspace-delete-damaged-ledger-fails-closed",
        "WORKSPACE_DELETE_LEDGER_INTEGRITY_FAILED",
        lambda: fixture.command(fixture.args(
            request_key="delete-bad-ledger",
            yes=True,
            expected_plan=str(preview["deletePlan"]["planFingerprint"]),
        )),
    )
    with closing(fixture.open_db()) as connection:
        target_exists = bool(connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (TARGET,)).fetchone())
        tombstone_count = int(connection.execute(
            "SELECT COUNT(*) FROM evidence_ledger_entries WHERE workspace_id = ? AND kind = 'publication_tombstoned'",
            (TARGET,),
        ).fetchone()[0])
    check(
        "workspace-delete-damaged-ledger-performs-zero-business-delete",
        target_exists and tombstone_count == 0 and fixture.state(OTHER) == before_other,
        {"targetExists": target_exists, "tombstoneCount": tombstone_count},
    )
    reconciliation = fixture.service.reconcile_unfinished_restores()
    fences = unfinished_recovery_fences(fixture.recovery_root)
    check(
        "workspace-delete-needs-attention-remains-fail-closed",
        reconciliation.get("ok") is False
        and any(item.get("status") == "workspace_delete_needs_attention" for item in reconciliation.get("needsAttention", []))
        and any(item.get("workspaceId") == TARGET and item.get("status") == "needs_attention" for item in fences),
        {"reconciliation": reconciliation, "fences": fences},
    )


def run_reconcile_case(root: Path, fail_at: str) -> None:
    fixture = Fixture(root)
    request_key = f"delete-reconcile-{fail_at}"
    preview = fixture.command(fixture.args(request_key=request_key))
    try:
        fixture.command(fixture.args(
            request_key=request_key,
            yes=True,
            expected_plan=str(preview["deletePlan"]["planFingerprint"]),
            fail_at=fail_at,
        ))
    except RuntimeError:
        pass
    else:
        check(f"workspace-delete-{fail_at}-injects-interruption", False, "operation unexpectedly completed")
        return
    reconciled = fixture.service.reconcile_unfinished_restores()
    replay = fixture.command(fixture.args(
        request_key=request_key,
        yes=True,
        expected_plan=str(preview["deletePlan"]["planFingerprint"]),
    ))
    with closing(fixture.open_db()) as connection:
        target_exists = bool(connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (TARGET,)).fetchone())
    check(
        f"workspace-delete-{fail_at}-startup-reconcile-completes",
        reconciled.get("ok") is True
        and not target_exists
        and replay.get("idempotentReplay") is True
        and replay.get("lifecycleStatus") == "completed",
        {"reconciled": reconciled, "replay": replay},
    )


with tempfile.TemporaryDirectory(prefix="aibi-workspace-delete-audit-") as temporary:
    base = Path(temporary)
    run_success_case(base / "success")
    run_bad_ledger_case(base / "bad-ledger")
    for index, fail_at in enumerate(("after_prepared", "after_duckdb_deleted", "after_sqlite_deleted"), start=1):
        run_reconcile_case(base / f"reconcile-{index}", fail_at)


failed = [item for item in checks if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "generatedBy": "scripts/verify-workspace-delete-audit.py",
    "checks": checks,
    "summary": {"passed": len(checks) - len(failed), "failed": len(failed), "total": len(checks)},
}, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
