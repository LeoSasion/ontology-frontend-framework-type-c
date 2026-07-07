from __future__ import annotations

import argparse
import json
import sqlite3
from typing import Any, Callable

from bi_cli_core import now_iso, quote_identifier, source_label


def rename_source_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    resolve_table_registry: Callable[[sqlite3.Connection, str], sqlite3.Row],
) -> dict[str, Any]:
    next_name = str(args.name or "").strip()
    if not next_name:
        raise ValueError("New source name is required.")
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        registry = resolve_table_registry(connection, args.source)
        duplicate = connection.execute(
            """
            SELECT table_key, display_name
            FROM table_registry
            WHERE display_name = ? AND table_key <> ? AND workspace_id = ?
            """,
            (next_name, registry["table_key"], workspace_id),
        ).fetchone()
        if duplicate:
            raise ValueError(f"Source name already exists: {next_name}")
        proposed = {
            "tableKey": registry["table_key"],
            "oldName": registry["display_name"],
            "name": next_name,
        }
        if not args.yes:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "proposed": proposed}
        connection.execute(
            "UPDATE table_registry SET display_name = ? WHERE table_key = ? AND workspace_id = ?",
            (next_name, registry["table_key"], workspace_id),
        )
        connection.execute(
            "UPDATE source_runs SET name = ? WHERE table_key = ? AND workspace_id = ?",
            (next_name, registry["table_key"], workspace_id),
        )
        connection.execute(
            """
            UPDATE navigation_modules
            SET name = ?, updated_at = ?
            WHERE module_type = 'table' AND table_key = ? AND workspace_id = ?
            """,
            (next_name, now_iso(), registry["table_key"], workspace_id),
        )
        connection.commit()
    return {"ok": True, "confirmed": True, "renamedSource": proposed}


def remaining_table_key_after_delete(
    connection: sqlite3.Connection,
    deleted_table_key: str,
    *,
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> str:
    workspace_id = active_workspace_id(connection)
    row = connection.execute(
        """
        SELECT table_key
        FROM table_registry
        WHERE table_key <> ? AND workspace_id = ?
        ORDER BY row_count DESC, display_name
        LIMIT 1
        """,
        (deleted_table_key, workspace_id),
    ).fetchone()
    return row["table_key"] if row else ""


def build_delete_source_plan(
    connection: sqlite3.Connection,
    registry: sqlite3.Row,
    *,
    active_workspace_id: Callable[[sqlite3.Connection], str],
    rows_to_dicts: Callable[[Any], list[dict[str, Any]]],
    load_connectors: Callable[[sqlite3.Connection], list[dict[str, Any]]],
    remaining_table_key_after_delete: Callable[[sqlite3.Connection, str], str],
) -> dict[str, Any]:
    workspace_id = active_workspace_id(connection)
    table_key = registry["table_key"]
    relation_keys = [
        row["relation_key"]
        for row in connection.execute(
            "SELECT relation_key FROM relationships WHERE workspace_id = ? AND (left_table_key = ? OR right_table_key = ?)",
            (workspace_id, table_key, table_key),
        )
    ]
    relation_like_clauses = " OR ".join("config_json LIKE ?" for _ in relation_keys)
    relation_like_params = [f"%{relation_key}%" for relation_key in relation_keys]
    widget_where = "table_key = ?"
    widget_params: list[Any] = [table_key]
    if relation_like_clauses:
        widget_where = f"({widget_where} OR {relation_like_clauses})"
        widget_params.extend(relation_like_params)
    affected_widgets = rows_to_dicts(
        connection.execute(
            f"""
            SELECT w.widget_key, w.dashboard_key, w.widget_type, w.title, w.table_key
            FROM dashboard_widgets w
            JOIN dashboards d ON d.dashboard_key = w.dashboard_key AND d.workspace_id = w.workspace_id
            WHERE d.workspace_id = ? AND {widget_where.replace('config_json', 'w.config_json').replace('table_key', 'w.table_key')}
            ORDER BY w.dashboard_key, w.sort_order
            """,
            tuple([workspace_id, *widget_params]),
        )
    )
    affected_dashboards = rows_to_dicts(
        connection.execute(
            """
            SELECT dashboard_key, name, default_table_key
            FROM dashboards
            WHERE default_table_key = ? AND workspace_id = ?
            ORDER BY dashboard_key
            """,
            (table_key, workspace_id),
        )
    )
    connectors = [
        connector for connector in load_connectors(connection)
        if str(connector.get("config", {}).get("targetTableKey") or "") == table_key
    ]
    return {
        "source": {
            "tableKey": table_key,
            "name": registry["display_name"],
            "physicalTable": registry["physical_table"],
            "sourceFile": source_label(registry["source_file"]),
            "rows": registry["row_count"],
            "columns": registry["column_count"],
        },
        "impact": {
            "sourceRuns": connection.execute("SELECT COUNT(*) FROM source_runs WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id)).fetchone()[0],
            "fieldConfigs": connection.execute("SELECT COUNT(*) FROM field_semantics WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id)).fetchone()[0],
            "metrics": connection.execute("SELECT COUNT(*) FROM metric_definitions WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id)).fetchone()[0],
            "views": connection.execute("SELECT COUNT(*) FROM saved_views WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id)).fetchone()[0],
            "importPolicies": connection.execute("SELECT COUNT(*) FROM import_policies WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id)).fetchone()[0],
            "importJobs": connection.execute("SELECT COUNT(*) FROM import_jobs WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id)).fetchone()[0],
            "relationships": len(relation_keys),
            "dashboardWidgets": len(affected_widgets),
            "dashboardDefaults": len(affected_dashboards),
            "connectors": len(connectors),
        },
        "affectedWidgets": affected_widgets,
        "affectedDashboards": affected_dashboards,
        "affectedRelationshipKeys": relation_keys,
        "affectedConnectors": connectors,
        "nextDefaultTableKey": remaining_table_key_after_delete(connection, table_key),
    }


def delete_source_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    resolve_table_registry: Callable[[sqlite3.Connection, str], sqlite3.Row],
    build_delete_source_plan: Callable[[sqlite3.Connection, sqlite3.Row], dict[str, Any]],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        registry = resolve_table_registry(connection, args.source)
        table_key = registry["table_key"]
        plan = build_delete_source_plan(connection, registry)
        if not args.yes:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, **plan}
        connection.execute(f"DROP TABLE IF EXISTS {quote_identifier(registry['physical_table'])}")
        connection.execute("DELETE FROM table_registry WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id))
        connection.execute("DELETE FROM source_runs WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id))
        connection.execute("DELETE FROM field_semantics WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id))
        connection.execute("DELETE FROM metric_definitions WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id))
        connection.execute("DELETE FROM saved_views WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id))
        connection.execute("DELETE FROM import_policies WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id))
        connection.execute("DELETE FROM import_jobs WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id))
        connection.execute("DELETE FROM navigation_modules WHERE module_type = 'table' AND table_key = ? AND workspace_id = ?", (table_key, workspace_id))
        connection.execute("DELETE FROM relationships WHERE workspace_id = ? AND (left_table_key = ? OR right_table_key = ?)", (workspace_id, table_key, table_key))
        widget_keys = [item["widget_key"] for item in plan["affectedWidgets"]]
        for widget_key in widget_keys:
            connection.execute("DELETE FROM dashboard_widgets WHERE widget_key = ? AND workspace_id = ?", (widget_key, workspace_id))
        for dashboard in plan["affectedDashboards"]:
            layout_row = connection.execute(
                "SELECT layout_json FROM dashboards WHERE dashboard_key = ? AND workspace_id = ?",
                (dashboard["dashboard_key"], workspace_id),
            ).fetchone()
            layout = json.loads(layout_row["layout_json"]) if layout_row else {}
            if isinstance(layout, dict):
                layout["globalFilters"] = []
            connection.execute(
                """
                UPDATE dashboards
                SET default_table_key = ?, layout_json = ?, updated_at = ?
                WHERE dashboard_key = ? AND workspace_id = ?
                """,
                (plan["nextDefaultTableKey"] or None, json.dumps(layout, ensure_ascii=False), now_iso(), dashboard["dashboard_key"], workspace_id),
            )
        for connector in plan["affectedConnectors"]:
            config = dict(connector["config"])
            config["targetTableKey"] = ""
            connection.execute(
                """
                UPDATE data_connectors
                SET status = 'paused', config_json = ?, updated_at = ?
                WHERE connector_key = ?
                """,
                (json.dumps(config, ensure_ascii=False), now_iso(), connector["connectorKey"]),
            )
        replacement = plan["nextDefaultTableKey"] or None
        connection.execute(
            """
            UPDATE workspaces
            SET current_source_run_id = (
            SELECT id FROM source_runs
              WHERE table_key = ?
              ORDER BY created_at DESC
              LIMIT 1
            )
            WHERE id = ?
            """,
            (replacement, active_workspace_id(connection)),
        )
        connection.commit()
    return {"ok": True, "confirmed": True, "deletedSource": table_key, **plan}
