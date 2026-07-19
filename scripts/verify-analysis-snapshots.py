from __future__ import annotations

import csv
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from analysis_snapshot_service import _semantic_fingerprint  # noqa: E402


CHECKS: list[dict[str, Any]] = []


def check(label: str, ok: bool, detail: Any = None) -> None:
    CHECKS.append({"label": label, "ok": bool(ok), "detail": None if ok else detail})


def run(env: dict[str, str], arguments: list[str], expected_status: int = 0) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "tools/aibi_cli.py", "--json", *arguments],
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout.strip() or "{}")
    except json.JSONDecodeError:
        payload = {"ok": False, "stdout": completed.stdout, "stderr": completed.stderr}
    payload["processExitCode"] = completed.returncode
    payload["expectedProcessExitCode"] = expected_status
    return payload


def confirm(env: dict[str, str], arguments: list[str], preview: dict[str, Any]) -> dict[str, Any]:
    plan = preview.get("analysisSnapshotPlan") if isinstance(preview.get("analysisSnapshotPlan"), dict) else {}
    return run(env, [*arguments, "--yes", "--expected-plan", str(plan.get("planFingerprint") or "")])


def public_has_rows(value: Any) -> bool:
    if isinstance(value, dict):
        if "rows" in value or "content" in value:
            return True
        return any(public_has_rows(item) for item in value.values())
    if isinstance(value, list):
        return any(public_has_rows(item) for item in value)
    return False


def write_series(path: Path, offset: int = 0) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["event_date", "segment", "value"])
        writer.writeheader()
        for index in range(8):
            writer.writerow({
                "event_date": f"2026-{index + 1:02d}-01",
                "segment": "alpha" if index % 2 == 0 else "beta",
                "value": 100 + offset + index,
            })


semantic_unit = {
    "kind": "comparison",
    "grain": {
        "dimensions": [{"tableKey": "dimensions", "field": "label", "resultColumn": "label"}],
        "measures": [{"field": "value", "aggregation": "sum", "resultColumn": "value"}],
        "sourceTableKeys": ["dimensions", "facts"],
        "relationshipPathFingerprint": "runtime-proof-a",
    },
    "shape": {"columns": ["label", "value"], "dimensionColumn": "label", "measureColumn": "value"},
}
semantic_receipt = {
    "selection": {
        "group": "label",
        "measure": "value",
        "aggregation": "sum",
        "filters": [],
        "joins": [{
            "relationKey": "rel-dim-fact",
            "fromTable": "dimensions",
            "toTable": "facts",
            "joinType": "left",
            "direction": "forward",
            "fieldMappings": [{"leftField": "id", "rightField": "dimension_id"}],
            "dataVersions": {"dimensions": 1, "facts": 1},
            "relationshipFingerprint": "runtime-relationship-a",
            "updatedAt": "2026-07-16T00:00:00Z",
        }],
    },
}
refreshed_semantic_unit = json.loads(json.dumps(semantic_unit))
refreshed_semantic_unit["grain"]["relationshipPathFingerprint"] = "runtime-proof-b"
refreshed_semantic_receipt = json.loads(json.dumps(semantic_receipt))
refreshed_semantic_receipt["selection"]["joins"][0].update({
    "dataVersions": {"dimensions": 2, "facts": 3},
    "relationshipFingerprint": "runtime-relationship-b",
    "updatedAt": "2026-07-16T01:00:00Z",
})
check(
    "cross-table-refresh-separates-semantic-identity-from-runtime-provenance",
    _semantic_fingerprint(semantic_unit, semantic_receipt)
    == _semantic_fingerprint(refreshed_semantic_unit, refreshed_semantic_receipt),
)


with tempfile.TemporaryDirectory(prefix="aibi-analysis-snapshots-") as temp_dir:
    temp = Path(temp_dir)
    source = temp / "series.csv"
    write_series(source)
    database = temp / "runtime.sqlite"
    env = {
        **os.environ,
        "AIBI_HYBRID_DB_PATH": str(database),
        "AIBI_HYBRID_DUCKDB_PATH": str(temp / "runtime.duckdb"),
        "AIBI_EVIDENCE_BUNDLE_ROOT": str(temp / "evidence"),
        "PYTHONIOENCODING": "utf-8",
    }

    imported = run(env, ["import-commit", str(source), "--table", "series", "--name", "Series", "--mode", "create", "--yes"])
    check("neutral-source-imports", imported.get("processExitCode") == 0 and imported.get("committed") is True, imported)
    query = run(env, ["query", "--table", "series", "--group", "segment", "--measure", "value", "--agg", "sum", "--limit", "100", "--request", "value 按 segment 汇总"])
    unit = query.get("analysisUnit") if isinstance(query.get("analysisUnit"), dict) else {}
    unit_key = str(unit.get("unitKey") or "")
    check("query-produces-current-ready-unit", query.get("processExitCode") == 0 and unit.get("status") == "ready" and unit_key, query)

    create_args = ["analysis-snapshot-create", "--unit", unit_key, "--reason", "baseline", "--row-limit", "1"]
    preview = run(env, create_args)
    plan = preview.get("analysisSnapshotPlan") if isinstance(preview.get("analysisSnapshotPlan"), dict) else {}
    check(
        "create-is-dry-run-with-exact-plan",
        preview.get("dryRun") is True
        and preview.get("requiresConfirmation") is True
        and plan.get("operation") == "create"
        and plan.get("businessRowsInResponse") == 0
        and len(str(plan.get("planFingerprint") or "")) == 64
        and not public_has_rows(preview),
        preview,
    )
    missing_plan = run(env, [*create_args, "--yes"], expected_status=1)
    check("confirmation-requires-preview-fingerprint", missing_plan.get("processExitCode") == 1 and "expected-plan" in str(missing_plan.get("error") or ""), missing_plan)
    created = confirm(env, create_args, preview)
    snapshot = created.get("analysisSnapshot") if isinstance(created.get("analysisSnapshot"), dict) else {}
    snapshot_key = str(snapshot.get("snapshotKey") or "")
    check(
        "confirmed-create-freezes-bounded-current-snapshot",
        created.get("processExitCode") == 0
        and created.get("confirmed") is True
        and created.get("changed") is True
        and snapshot.get("status") == "current"
        and snapshot.get("rowCount") == 1
        and snapshot.get("rowLimit") == 1
        and snapshot.get("freshness", {}).get("usableForPlanning") is True
        and snapshot.get("summary", {}).get("rowsIncluded") is False
        and not public_has_rows(created),
        created,
    )

    with closing(sqlite3.connect(database)) as connection:
        connection.row_factory = sqlite3.Row
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        stored = connection.execute("SELECT * FROM analysis_snapshots WHERE workspace_id = 'default' AND snapshot_key = ?", (snapshot_key,)).fetchone()
        content = json.loads(stored["content_json"] if stored else "{}")
        binding = json.loads(stored["binding_json"] if stored else "{}")
        indexes = {str(row[1]) for row in connection.execute("PRAGMA index_list(analysis_snapshots)").fetchall()}
    check(
        "schema-v15-persists-content-provenance-and-indexes",
        version == 15
        and stored is not None
        and len(content.get("unit", {}).get("rows") or []) == 1
        and binding.keys() >= {"unitKey", "queryReceiptKey", "unitDefinitionFingerprint", "resultFingerprint", "receiptBindingFingerprint", "source", "domainPackFingerprint", "workspaceManifestFingerprint"}
        and binding.get("source", {}).keys() >= {"tableKeys", "schemaFingerprint", "dataFingerprint", "relationshipPathFingerprint", "sourceFingerprint"}
        and indexes >= {"idx_analysis_snapshots_workspace_unit", "idx_analysis_snapshots_workspace_parent", "idx_analysis_snapshots_workspace_input"},
        {"version": version, "binding": binding, "indexes": sorted(indexes)},
    )

    listed = run(env, ["analysis-snapshots", "--unit", unit_key])
    listed_snapshot = (listed.get("analysisSnapshots") or [{}])[0]
    check(
        "list-is-row-free-current-and-no-fallback",
        listed.get("count") == 1
        and listed.get("businessRowsCopied") is False
        and listed.get("staleFallbackUsed") is False
        and listed_snapshot.get("status") == "current"
        and not public_has_rows(listed),
        listed,
    )

    idempotent_preview = run(env, create_args)
    idempotent = confirm(env, create_args, idempotent_preview)
    check(
        "exact-input-is-idempotent",
        idempotent_preview.get("analysisSnapshotPlan", {}).get("alreadyExists") is True
        and idempotent.get("changed") is False
        and idempotent.get("analysisSnapshot", {}).get("snapshotKey") == snapshot_key,
        idempotent,
    )

    integrity_args = ["analysis-snapshot-create", "--unit", unit_key, "--reason", "integrity-check", "--row-limit", "2"]
    integrity_preview = run(env, integrity_args)
    integrity_created = confirm(env, integrity_args, integrity_preview)
    integrity_key = str(integrity_created.get("analysisSnapshot", {}).get("snapshotKey") or "")
    with closing(sqlite3.connect(database)) as connection:
        connection.execute(
            "UPDATE analysis_snapshots SET content_json = '{\"tampered\":true}' WHERE workspace_id = 'default' AND snapshot_key = ?",
            (integrity_key,),
        )
        connection.commit()
    integrity_retry_preview = run(env, integrity_args)
    integrity_retry = confirm(env, integrity_args, integrity_retry_preview)
    check(
        "exact-input-idempotency-rejects-corrupted-stored-content",
        integrity_key
        and integrity_retry.get("processExitCode") == 1
        and "integrity checks" in str(integrity_retry.get("error") or "")
        and "content-drifted" in str(integrity_retry.get("error") or ""),
        integrity_retry,
    )

    drift_preview_args = ["analysis-snapshot-create", "--unit", unit_key, "--reason", "stale-plan"]
    drift_preview = run(env, drift_preview_args)
    write_series(source, offset=50)
    replaced_source = run(env, ["import-commit", str(source), "--table", "series", "--name", "Series", "--mode", "replace", "--yes"])
    check("source-version-replaces", replaced_source.get("processExitCode") == 0 and replaced_source.get("committed") is True, replaced_source)
    drift_confirm = confirm(env, drift_preview_args, drift_preview)
    check("source-drift-invalidates-preview-before-write", drift_confirm.get("processExitCode") == 1 and "current ready" in str(drift_confirm.get("error") or ""), drift_confirm)
    stale = run(env, ["analysis-snapshots", "--snapshot", snapshot_key])
    check(
        "source-drift-keeps-auditable-stale-history-without-fallback",
        stale.get("analysisSnapshot", {}).get("status") == "stale"
        and stale.get("analysisSnapshot", {}).get("freshness", {}).get("usableForPlanning") is False
        and stale.get("analysisSnapshot", {}).get("freshness", {}).get("staleFallbackUsed") is False
        and not public_has_rows(stale),
        stale,
    )

    refreshed_query = run(env, ["query", "--table", "series", "--group", "segment", "--measure", "value", "--agg", "sum", "--limit", "100", "--request", "value 按 segment 汇总"])
    refreshed_unit = refreshed_query.get("analysisUnit") if isinstance(refreshed_query.get("analysisUnit"), dict) else {}
    refreshed_unit_key = str(refreshed_unit.get("unitKey") or "")
    refresh_args = ["analysis-snapshot-refresh", "--snapshot", snapshot_key, "--unit", refreshed_unit_key, "--reason", "new source version", "--row-limit", "2"]
    refresh_preview = run(env, refresh_args)
    refreshed = confirm(env, refresh_args, refresh_preview)
    child = refreshed.get("analysisSnapshot") if isinstance(refreshed.get("analysisSnapshot"), dict) else {}
    check(
        "refresh-appends-compatible-child-without-overwriting-parent",
        refreshed.get("changed") is True
        and child.get("operation") == "refresh"
        and child.get("parentSnapshotKey") == snapshot_key
        and child.get("status") == "current"
        and child.get("snapshotKey") != snapshot_key,
        refreshed,
    )

    different_query = run(env, ["query", "--table", "series", "--group", "event_date", "--measure", "value", "--agg", "sum", "--limit", "100", "--request", "value 按 event_date 汇总"])
    different_unit = different_query.get("analysisUnit") if isinstance(different_query.get("analysisUnit"), dict) else {}
    different_unit_key = str(different_unit.get("unitKey") or "")
    incompatible_refresh = run(env, ["analysis-snapshot-refresh", "--snapshot", child.get("snapshotKey", ""), "--unit", different_unit_key, "--reason", "semantic change"])
    check("refresh-blocks-semantic-change", incompatible_refresh.get("processExitCode") == 1 and "use replace" in str(incompatible_refresh.get("error") or ""), incompatible_refresh)
    replace_args = ["analysis-snapshot-replace", "--snapshot", child.get("snapshotKey", ""), "--unit", different_unit_key, "--reason", "approved semantic replacement"]
    replace_preview = run(env, replace_args)
    replacement = confirm(env, replace_args, replace_preview)
    check(
        "replace-allows-explicit-semantic-change-and-preserves-lineage",
        replacement.get("changed") is True
        and replacement.get("analysisSnapshot", {}).get("operation") == "replace"
        and replacement.get("analysisSnapshot", {}).get("parentSnapshotKey") == child.get("snapshotKey")
        and replacement.get("analysisSnapshot", {}).get("semanticFingerprint") != child.get("semanticFingerprint"),
        replacement,
    )

    delete_key = str(child.get("snapshotKey") or "")
    delete_args = ["analysis-snapshot-delete", "--snapshot", delete_key]
    delete_preview = run(env, delete_args)
    deleted = confirm(env, delete_args, delete_preview)
    with closing(sqlite3.connect(database)) as connection:
        deleted_row = connection.execute("SELECT status, row_count, content_json FROM analysis_snapshots WHERE workspace_id = 'default' AND snapshot_key = ?", (delete_key,)).fetchone()
    check(
        "confirmed-delete-erases-content-and-keeps-lineage-tombstone",
        deleted.get("changed") is True
        and deleted.get("analysisSnapshot", {}).get("status") == "deleted"
        and deleted_row == ("deleted", 0, "{}")
        and not public_has_rows(deleted),
        {"deleted": deleted, "row": deleted_row},
    )

    created_workspace = run(env, ["workspace-create", "--name", "Snapshot isolation", "--yes"])
    isolated_id = str(created_workspace.get("created", {}).get("id") or "")
    isolated_list = run(env, ["analysis-snapshots"])
    check("snapshots-are-workspace-isolated", isolated_id and isolated_list.get("workspaceId") == isolated_id and isolated_list.get("count") == 0, isolated_list)
    run(env, ["workspace-select", "default", "--yes"])
    with closing(sqlite3.connect(database)) as connection:
        source_row = connection.execute("SELECT * FROM analysis_snapshots WHERE workspace_id = 'default' AND snapshot_key = ?", (snapshot_key,)).fetchone()
        columns = [row[1] for row in connection.execute("PRAGMA table_info(analysis_snapshots)").fetchall()]
        values = list(source_row) if source_row else []
        values[columns.index("workspace_id")] = isolated_id
        values[columns.index("snapshot_key")] = "analysis_snapshot_isolation_fixture"
        connection.execute(
            f"INSERT INTO analysis_snapshots({', '.join(columns)}) VALUES({', '.join('?' for _ in columns)})",
            values,
        )
        connection.commit()
    delete_workspace = run(env, ["workspace-delete", isolated_id, "--yes"])
    check(
        "workspace-delete-removes-snapshot-state",
        delete_workspace.get("deletedCounts", {}).get("analysis_snapshots") == 1,
        delete_workspace,
    )


failed = [item for item in CHECKS if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-analysis-snapshots-verify/v1",
    "generatedBy": "scripts/verify-analysis-snapshots.py",
    "checks": CHECKS,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
if failed:
    raise SystemExit(1)
