from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from bi_cli_core import ROOT
from context_pack_service import workspace_data_fingerprint, workspace_schema_fingerprint
from domain_pack_service import domain_pack_runtime_context, domain_pack_set_fingerprint
from evidence_receipts import source_intelligence_file_coverage
from evidence_profile_runtime.file_readers import discover_source_files, read_source_tables, sha256_file


def _current_source_fingerprint(input_roots: list[Any], manifest: dict[str, Any]) -> str:
    roots = []
    for item in input_roots:
        path = Path(str(item)).expanduser()
        roots.append(path if path.is_absolute() else ROOT / path)
    files = discover_source_files(roots)
    if not files:
        return "missing"
    captured_entries = manifest.get("sourceFingerprintEntries")
    if isinstance(captured_entries, list) and captured_entries:
        resolved_entries: list[tuple[dict[str, Any], Path]] = []
        for item in captured_entries:
            if not isinstance(item, dict):
                resolved_entries = []
                break
            path = Path(str(item.get("sourcePath") or ""))
            path = path if path.is_absolute() else ROOT / path
            resolved_entries.append((item, path.resolve()))
        if resolved_entries and {path for _item, path in resolved_entries} == set(files):
            digest_by_path = {path: sha256_file(path) for path in files}
            material = [
                {
                    "tableKey": str(item.get("tableKey") or ""),
                    "sheetName": str(item.get("sheetName") or ""),
                    "sha256": digest_by_path[path],
                }
                for item, path in resolved_entries
            ]
            import hashlib

            return hashlib.sha256(
                json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
    tables, _warnings = read_source_tables(files)
    material = [
        {
            "tableKey": str(table.get("tableKey") or ""),
            "sheetName": str(table.get("sheetName") or ""),
            "sha256": str(table.get("sha256") or ""),
        }
        for table in tables
    ]
    import hashlib

    return hashlib.sha256(
        json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _run_freshness(
    connection: sqlite3.Connection,
    workspace_id: str,
    manifest: dict[str, Any],
    input_roots: list[Any] | None = None,
) -> dict[str, Any]:
    current = {
        "schema": workspace_schema_fingerprint(connection, workspace_id),
        "data": workspace_data_fingerprint(connection, workspace_id),
        "domainPacks": domain_pack_set_fingerprint(domain_pack_runtime_context(connection, workspace_id)),
        "source": _current_source_fingerprint(list(input_roots or manifest.get("inputRoots") or []), manifest),
    }
    captured = {
        "schema": str(manifest.get("workspaceSchemaFingerprint") or ""),
        "data": str(manifest.get("workspaceDataFingerprint") or ""),
        "domainPacks": str(manifest.get("domainPackFingerprint") or ""),
        "source": str(manifest.get("sourceFingerprint") or ""),
    }
    missing = [key for key, value in captured.items() if not value]
    mismatches = [key for key in current if captured.get(key) and captured[key] != current[key]]
    status = "unknown" if missing else "stale" if mismatches else "current"
    return {
        "status": status,
        "usableForPlanning": status == "current",
        "missingFingerprints": missing,
        "mismatches": mismatches,
        "captured": captured,
        "current": current,
    }


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
        manifest = json.loads(str(item.pop("manifest_json") or "{}"))
        manifest = manifest if isinstance(manifest, dict) else {}
        item["sourceFingerprint"] = str(manifest.get("sourceFingerprint") or "")
        item["enabledDomainPacks"] = list(manifest.get("enabledDomainPacks") or [])
        item["freshness"] = _run_freshness(connection, workspace_id, manifest, item["inputRoots"])
        item["fileCoverage"] = source_intelligence_file_coverage({**item, "manifest_json": json.dumps(manifest, ensure_ascii=False)})
        if not item["freshness"]["usableForPlanning"]:
            item["fileCoverage"]["complete"] = False
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


def source_intelligence_summary_payload(row: sqlite3.Row, connection: sqlite3.Connection | None = None) -> dict[str, Any]:
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
        item["sourceFingerprint"] = str(manifest.get("sourceFingerprint") or "")
        item["enabledDomainPacks"] = list(manifest.get("enabledDomainPacks") or [])
        if connection is not None:
            item["freshness"] = _run_freshness(
                connection,
                str(item.get("workspace_id") or "default"),
                manifest,
                item["inputRoots"],
            )
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
    summaries = [source_intelligence_summary_payload(row, connection) for row in rows]
    if include_internal:
        return next((item for item in summaries if item.get("freshness", {}).get("usableForPlanning")), None)
    visible = [item for item in summaries if not internal_source_intelligence_run(item)] or summaries[:1]
    return next((item for item in visible if item.get("freshness", {}).get("usableForPlanning")), None)


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
