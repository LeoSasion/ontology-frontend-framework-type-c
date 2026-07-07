from __future__ import annotations

import json
import sqlite3
from typing import Any

from evidence_receipts import source_intelligence_file_coverage


def save_source_intelligence_run(
    connection: sqlite3.Connection,
    *,
    run_key: str,
    workspace_id: str,
    label: str,
    input_roots: list[str],
    output_dir: str,
    manifest: dict[str, Any],
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO source_intelligence_runs(
          run_key, workspace_id, label, status, input_roots_json, output_dir, source_count, table_count,
          field_candidate_count, relationship_count, metric_sql_plan_count,
          metric_sql_executable_count, manifest_json, created_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_key,
            workspace_id,
            label,
            str(manifest.get("status") or "ready"),
            json.dumps(input_roots, ensure_ascii=False),
            output_dir,
            int(manifest.get("sourceCount") or 0),
            int(manifest.get("tableCount") or 0),
            int(manifest.get("fieldCandidateCount") or 0),
            int(manifest.get("relationshipCount") or 0),
            int(manifest.get("metricSqlPlanCount") or 0),
            int(manifest.get("metricSqlExecutableCount") or 0),
            json.dumps(manifest, ensure_ascii=False),
            created_at,
        ),
    )


def list_source_intelligence_runs(connection: sqlite3.Connection, *, workspace_id: str, limit: int, include_internal: bool = False) -> list[dict[str, Any]]:
    scan_limit = max(limit * 5, 50) if not include_internal else limit
    rows = connection.execute(
        """
        SELECT run_key, workspace_id, label, status, input_roots_json, output_dir, source_count, table_count,
               field_candidate_count, relationship_count, metric_sql_plan_count,
               metric_sql_executable_count, manifest_json, created_at
        FROM source_intelligence_runs
        WHERE workspace_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (workspace_id, scan_limit),
    ).fetchall()
    runs: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["inputRoots"] = json.loads(item.pop("input_roots_json"))
        item["fileCoverage"] = source_intelligence_file_coverage(item)
        item["isInternal"] = internal_source_intelligence_run(item)
        runs.append(item)
    if include_internal:
        return runs[:limit]
    business_runs = [item for item in runs if not item["isInternal"]]
    visible_runs = business_runs if business_runs else runs[:1]
    return visible_runs[:limit]


def get_source_intelligence_run(connection: sqlite3.Connection, *, workspace_id: str, run_key: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT *
        FROM source_intelligence_runs
        WHERE run_key = ? AND workspace_id = ?
        """,
        (run_key, workspace_id),
    ).fetchone()


def latest_source_intelligence_run(connection: sqlite3.Connection, *, workspace_id: str, include_internal: bool = False) -> sqlite3.Row | None:
    rows = connection.execute(
        """
        SELECT *
        FROM source_intelligence_runs
        WHERE workspace_id = ?
        ORDER BY created_at DESC
        LIMIT 200
        """,
        (workspace_id,),
    ).fetchall()
    if not rows:
        return None
    if include_internal:
        return rows[0]
    return next((row for row in rows if not internal_source_intelligence_run(dict(row))), rows[0])


def internal_source_intelligence_run(row: dict[str, Any]) -> bool:
    label = str(row.get("label") or "").lower()
    output_dir = str(row.get("output_dir") or "").replace("\\", "/").lower()
    if label.startswith(("verify-", "inspect-", "workspace-isolation-")):
        return True
    return any(token in output_dir for token in ["tmp-inspect", "aibi-hybrid-verify", "workspace-isolation"])


def source_intelligence_summary_payload(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    try:
        item["inputRoots"] = json.loads(str(item.pop("input_roots_json") or "[]"))
    except json.JSONDecodeError:
        item["inputRoots"] = []
    try:
        manifest = json.loads(str(item.pop("manifest_json") or "{}"))
    except json.JSONDecodeError:
        manifest = {}
    if isinstance(manifest, dict):
        item["manifestInputRoots"] = manifest.get("inputRoots") if isinstance(manifest.get("inputRoots"), list) else []
    return item


def latest_source_intelligence_summary(connection: sqlite3.Connection, *, workspace_id: str, include_internal: bool = False) -> dict[str, Any] | None:
    rows = connection.execute(
        """
        SELECT run_key, workspace_id, label, status, input_roots_json, output_dir, source_count, table_count,
               field_candidate_count, relationship_count, metric_sql_plan_count,
               metric_sql_executable_count, manifest_json, created_at
        FROM source_intelligence_runs
        WHERE workspace_id = ?
        ORDER BY created_at DESC
        LIMIT 200
        """,
        (workspace_id,),
    ).fetchall()
    if not rows:
        return None
    summaries = [source_intelligence_summary_payload(row) for row in rows]
    if include_internal:
        return summaries[0]
    return next((item for item in summaries if not internal_source_intelligence_run(item)), summaries[0])


def source_intelligence_run_manifest(run: sqlite3.Row) -> dict[str, Any]:
    manifest = json.loads(run["manifest_json"]) if run["manifest_json"] else {}
    return manifest if isinstance(manifest, dict) else {}


def count_source_intelligence_runs(connection: sqlite3.Connection, *, workspace_id: str) -> int:
    return int(
        connection.execute(
            "SELECT COUNT(*) FROM source_intelligence_runs WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()[0]
    )
