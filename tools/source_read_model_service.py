from __future__ import annotations

import argparse
import sqlite3
from typing import Any, Callable

from bi_cli_core import source_label


def list_tables_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    rows_to_dicts: Callable[[Any], list[dict[str, Any]]],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        tables = rows_to_dicts(
            connection.execute(
                """
                SELECT table_key, workspace_id, display_name, physical_table, source_file, row_count, column_count, created_at
                FROM table_registry
                WHERE workspace_id = ?
                ORDER BY display_name
                """,
                (workspace_id,),
            )
        )
    for table in tables:
        table["source_file"] = source_label(table["source_file"])
        table["exists"] = True
    return {"ok": True, "tables": tables, "count": len(tables)}


def inspect_table_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    resolve_table_registry: Callable[[sqlite3.Connection, str], sqlite3.Row],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    rows_to_dicts: Callable[[Any], list[dict[str, Any]]],
    saved_import_policy: Callable[[sqlite3.Connection, str], dict[str, Any] | None],
    load_connectors: Callable[[sqlite3.Connection], list[dict[str, Any]]],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        registry = resolve_table_registry(connection, args.table)
        table_key = registry["table_key"]
        columns = table_columns(connection, registry["physical_table"])
        field_rows = rows_to_dicts(
            connection.execute(
                """
                SELECT field_name, role, usage, confidence
                FROM field_semantics
                WHERE table_key = ? AND workspace_id = ?
                ORDER BY field_name
                """,
                (table_key, workspace_id),
            )
        )
        metrics = rows_to_dicts(
            connection.execute(
                """
                SELECT metric_key, label, measure, aggregation, dimension, time_field, value_format
                FROM metric_definitions
                WHERE table_key = ? AND workspace_id = ?
                ORDER BY metric_key
                """,
                (table_key, workspace_id),
            )
        )
        views = rows_to_dicts(
            connection.execute(
                """
                SELECT view_key, name, tag_name, is_default, sort_order, created_by, agent_managed
                FROM saved_views
                WHERE table_key = ? AND workspace_id = ?
                ORDER BY sort_order, created_at
                """,
                (table_key, workspace_id),
            )
        )
        relationships = rows_to_dicts(
            connection.execute(
                """
                SELECT relation_key, name, left_table_key, right_table_key, left_field, right_field, join_type, confidence
                FROM relationships
                WHERE workspace_id = ? AND (left_table_key = ? OR right_table_key = ?)
                ORDER BY relation_key
                """,
                (workspace_id, table_key, table_key),
            )
        )
        import_policy = saved_import_policy(connection, table_key)
        import_jobs = rows_to_dicts(
            connection.execute(
                """
                SELECT job_key, workspace_id, source_file, mode, status, row_count, created_at
                FROM import_jobs
                WHERE table_key = ? AND workspace_id = ?
                ORDER BY created_at DESC
                LIMIT 8
                """,
                (table_key, workspace_id),
            )
        )
        connectors = [
            connector for connector in load_connectors(connection)
            if str(connector.get("config", {}).get("targetTableKey") or "") == table_key
        ]
    for job in import_jobs:
        job["source_file"] = source_label(job["source_file"])
    return {
        "ok": True,
        "table": {
            "table_key": registry["table_key"],
            "display_name": registry["display_name"],
            "source_file": source_label(registry["source_file"]),
            "row_count": registry["row_count"],
            "column_count": registry["column_count"],
            "created_at": registry["created_at"],
        },
        "columns": columns,
        "fieldConfig": field_rows,
        "metrics": metrics,
        "views": views,
        "relationships": relationships,
        "importPolicy": import_policy,
        "importJobs": import_jobs,
        "connectors": connectors,
    }
