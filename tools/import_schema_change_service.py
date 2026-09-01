from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

from dataset_version_store import schema_columns


SCHEMA_CHANGE_SCHEMA = "aibi-import-schema-change/v1"


def _quote_identifier(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone() is not None


def _table_columns(connection: sqlite3.Connection, table_name: str) -> list[str]:
    return [
        str(row[1])
        for row in connection.execute(f"PRAGMA table_info({_quote_identifier(table_name)})")
    ]


def _json_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return value


def _fingerprint(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _referenced_removed_fields(value: Any, removed_fields: set[str]) -> set[str]:
    value = _json_value(value)
    if isinstance(value, dict):
        found: set[str] = set()
        for item in value.values():
            found.update(_referenced_removed_fields(item, removed_fields))
        return found
    if isinstance(value, (list, tuple)):
        found = set()
        for item in value:
            found.update(_referenced_removed_fields(item, removed_fields))
        return found
    if isinstance(value, str):
        exact = value.strip()
        found = {field for field in removed_fields if exact == field or f"[{field}]" in value}
        return found
    return set()


def _impact_rows(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    table_name: str,
    table_key: str,
    key_column: str,
    label_column: str,
    direct_columns: tuple[str, ...],
    json_columns: tuple[str, ...],
    removed_fields: set[str],
) -> list[dict[str, Any]]:
    if not removed_fields or not _table_exists(connection, table_name):
        return []
    columns = set(_table_columns(connection, table_name))
    if not {"workspace_id", key_column}.issubset(columns):
        return []
    where = "workspace_id = ?"
    params: list[Any] = [workspace_id]
    if "table_key" in columns:
        where += " AND table_key = ?"
        params.append(table_key)
    rows = connection.execute(
        f"SELECT * FROM {_quote_identifier(table_name)} WHERE {where} ORDER BY {_quote_identifier(key_column)}",
        params,
    ).fetchall()
    impacts: list[dict[str, Any]] = []
    for row in rows:
        references: set[str] = set()
        for column in direct_columns:
            if column in columns and str(row[column] or "") in removed_fields:
                references.add(str(row[column]))
        for column in json_columns:
            if column in columns:
                references.update(_referenced_removed_fields(row[column], removed_fields))
        if not references:
            continue
        impacts.append({
            "key": str(row[key_column]),
            "label": str(row[label_column] or row[key_column]) if label_column in columns else str(row[key_column]),
            "fields": sorted(references),
        })
    return impacts


def _relationship_impacts(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    table_key: str,
    removed_fields: set[str],
) -> list[dict[str, Any]]:
    if not removed_fields or not _table_exists(connection, "relationships"):
        return []
    rows = connection.execute(
        """
        SELECT * FROM relationships
        WHERE workspace_id = ? AND (left_table_key = ? OR right_table_key = ?)
        ORDER BY relation_key
        """,
        (workspace_id, table_key, table_key),
    ).fetchall()
    impacts: list[dict[str, Any]] = []
    for row in rows:
        references: set[str] = set()
        if str(row["left_table_key"]) == table_key and str(row["left_field"] or "") in removed_fields:
            references.add(str(row["left_field"]))
        if str(row["right_table_key"]) == table_key and str(row["right_field"] or "") in removed_fields:
            references.add(str(row["right_field"]))
        for column in ("mappings_json", "filters_json", "preaggregation_json"):
            if column in row.keys():
                references.update(_referenced_removed_fields(row[column], removed_fields))
        if references:
            impacts.append({
                "key": str(row["relation_key"]),
                "label": str(row["name"] or row["relation_key"]),
                "fields": sorted(references),
            })
    return impacts


def build_import_schema_change_preview(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    table_key: str,
    incoming_fields: list[str],
) -> dict[str, Any] | None:
    registry = connection.execute(
        "SELECT table_key, display_name, physical_table, schema_json FROM table_registry WHERE workspace_id = ? AND table_key = ?",
        (workspace_id, table_key),
    ).fetchone()
    if registry is None:
        return None
    current_fields = schema_columns(registry["schema_json"])
    incoming = [str(field) for field in incoming_fields]
    current_set = set(current_fields)
    incoming_set = set(incoming)
    added_fields = [field for field in incoming if field not in current_set]
    removed_fields = [field for field in current_fields if field not in incoming_set]
    retained_fields = [field for field in incoming if field in current_set]
    order_changed = not added_fields and not removed_fields and incoming != current_fields
    removed = set(removed_fields)

    impacts = {
        "relationships": _relationship_impacts(
            connection,
            workspace_id=workspace_id,
            table_key=table_key,
            removed_fields=removed,
        ),
        "metrics": _impact_rows(
            connection,
            workspace_id=workspace_id,
            table_name="metric_definitions",
            table_key=table_key,
            key_column="metric_key",
            label_column="label",
            direct_columns=("measure", "dimension", "time_field"),
            json_columns=("filters_json", "dependencies_json", "formula_ast_json"),
            removed_fields=removed,
        ),
        "calculatedFields": _impact_rows(
            connection,
            workspace_id=workspace_id,
            table_name="calculated_fields",
            table_key=table_key,
            key_column="field_key",
            label_column="name",
            direct_columns=(),
            json_columns=("dependencies_json", "formula_ast_json", "formula_text"),
            removed_fields=removed,
        ),
        "savedViews": _impact_rows(
            connection,
            workspace_id=workspace_id,
            table_name="saved_views",
            table_key=table_key,
            key_column="view_key",
            label_column="name",
            direct_columns=(),
            json_columns=("config_json",),
            removed_fields=removed,
        ),
        "dashboardWidgets": _impact_rows(
            connection,
            workspace_id=workspace_id,
            table_name="dashboard_widgets",
            table_key=table_key,
            key_column="widget_key",
            label_column="title",
            direct_columns=(),
            json_columns=("config_json",),
            removed_fields=removed,
        ),
    }
    semantic_fields = set()
    if removed and _table_exists(connection, "field_semantics"):
        semantic_fields = {
            str(row[0])
            for row in connection.execute(
                "SELECT field_name FROM field_semantics WHERE workspace_id = ? AND table_key = ?",
                (workspace_id, table_key),
            )
            if str(row[0]) in removed
        }
    field_semantics = [
        {"key": field, "label": field, "fields": [field]}
        for field in removed_fields
        if field in semantic_fields
    ]
    impacts["fieldSemantics"] = field_semantics
    total_dependencies = sum(len(items) for items in impacts.values())
    return {
        "schema": SCHEMA_CHANGE_SCHEMA,
        "kind": "replace-schema",
        "targetTableKey": table_key,
        "targetDisplayName": str(registry["display_name"] or table_key),
        "currentFields": current_fields,
        "incomingFields": incoming,
        "addedFields": added_fields,
        "removedFields": removed_fields,
        "retainedFields": retained_fields,
        "orderChanged": order_changed,
        "confirmationRequired": bool(added_fields or removed_fields or order_changed),
        "impact": {
            **impacts,
            "totalDependencies": total_dependencies,
            "truncated": False,
            "fingerprint": _fingerprint(impacts),
        },
    }
