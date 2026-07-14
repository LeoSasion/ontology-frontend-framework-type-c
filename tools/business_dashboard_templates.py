from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Callable


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _field_name(field: dict[str, Any]) -> str:
    return str(field.get("fieldName") or field.get("name") or field.get("column") or "").strip()


def source_profile_table_inputs(
    connection: sqlite3.Connection,
    workspace_id: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Read the latest workspace-scoped structural profile without adding domain assumptions."""
    try:
        row = connection.execute(
            """
            SELECT output_dir, manifest_json
            FROM source_intelligence_runs
            WHERE workspace_id = ?
            ORDER BY created_at DESC, run_key DESC
            LIMIT 1
            """,
            (workspace_id,),
        ).fetchone()
    except sqlite3.Error:
        return [], {}
    if not row:
        return [], {}
    try:
        manifest = json.loads(str(row["manifest_json"] or "{}"))
    except json.JSONDecodeError:
        manifest = {}
    outputs = manifest.get("outputs") if isinstance(manifest.get("outputs"), dict) else {}
    profile_name = str(outputs.get("sourceProfile") or "source-profile-generic.json")
    profile = _read_json_file(Path(str(row["output_dir"])) / profile_name)
    tables = profile.get("tables") if isinstance(profile.get("tables"), list) else []
    table_rows: list[dict[str, Any]] = []
    fields_by_key: dict[str, dict[str, Any]] = {}
    for table in tables:
        if not isinstance(table, dict):
            continue
        table_key = str(table.get("tableKey") or table.get("table_key") or "").strip()
        if not table_key:
            continue
        raw_fields = table.get("fields") if isinstance(table.get("fields"), list) else []
        fields = [field for field in raw_fields if isinstance(field, dict) and _field_name(field)]
        columns = [_field_name(field) for field in fields]
        measures = [
            _field_name(field)
            for field in fields
            if str(field.get("usage") or "").lower() == "aggregatable"
            or str(field.get("role") or "").lower() == "measure"
            or str(field.get("type") or "").lower() in {"number", "numeric", "integer", "float"}
        ]
        dimensions = [
            _field_name(field)
            for field in fields
            if str(field.get("usage") or "").lower() in {"groupable", "filterable", "join_key"}
            or str(field.get("role") or "").lower() in {"dimension", "identity", "identity_key", "status"}
        ]
        dates = [
            _field_name(field)
            for field in fields
            if str(field.get("role") or "").lower() == "event_time"
            or str(field.get("type") or "").lower() in {"date", "datetime", "time"}
            or str(field.get("semantic") or "").lower() == "event_time"
        ]
        table_rows.append({
            "table_key": table_key,
            "display_name": str(table.get("label") or table.get("displayName") or table_key),
            "source_file": str(table.get("sourcePath") or ""),
            "row_count": int(table.get("rowCount") or 0),
            "column_count": int(table.get("columnCount") or len(columns)),
            "workspace_id": workspace_id,
            "physical_table": "",
        })
        fields_by_key[table_key] = {
            "columns": columns,
            "measures": measures,
            "dimensions": dimensions,
            "filterable": dimensions,
            "dates": dates,
            "measure": measures[0] if measures else "",
            "dimension": dimensions[0] if dimensions else (columns[0] if columns else ""),
            "date": dates[0] if dates else "",
        }
    table_rows.sort(key=lambda item: (-int(item.get("row_count") or 0), str(item.get("table_key") or "")))
    return table_rows, fields_by_key


def table_fields_by_key(
    connection: sqlite3.Connection,
    table_rows: list[dict[str, Any]],
    table_template_fields: Callable[[sqlite3.Connection, str], dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {row["table_key"]: table_template_fields(connection, row["table_key"]) for row in table_rows}
