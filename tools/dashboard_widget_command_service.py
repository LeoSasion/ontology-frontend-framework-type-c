from __future__ import annotations

import json
import sqlite3
from typing import Any, Callable


def add_recommended_dashboard_widgets(
    *,
    dashboard_key: str,
    table_key: str | None,
    limit: int,
    allow_duplicates: bool,
    confirm: bool,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    preferred_table_key: Callable[[sqlite3.Connection, str | None], str],
    widget_recommendations_for_table: Callable[[sqlite3.Connection, str, int], dict[str, Any]],
    build_widget_proposal: Callable[[sqlite3.Connection, str, str, dict[str, Any]], dict[str, Any]],
    insert_dashboard_widget: Callable[[sqlite3.Connection, dict[str, Any]], None],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        resolved_table_key = preferred_table_key(connection, table_key)
        payload = widget_recommendations_for_table(connection, resolved_table_key, limit)
        existing = {
            (row["widget_type"], row["title"], row["table_key"])
            for row in connection.execute(
                "SELECT widget_type, title, table_key FROM dashboard_widgets WHERE dashboard_key = ? AND workspace_id = ?",
                (dashboard_key, workspace_id),
            ).fetchall()
        }
        planned: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for recommendation in payload["recommendations"]:
            signature = (recommendation["type"], recommendation["title"], resolved_table_key)
            if signature in existing and not allow_duplicates:
                skipped.append({**recommendation, "reason": "same type/title/source already exists"})
                continue
            proposal = build_widget_proposal(connection, dashboard_key, recommendation["type"], recommendation)
            proposal["sort_order"] = proposal["sort_order"] + len(planned) * 10
            planned.append(proposal)
        if not confirm:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "dashboardKey": dashboard_key,
                "tableKey": resolved_table_key,
                "plannedCount": len(planned),
                "skippedCount": len(skipped),
                "plannedWidgets": planned,
                "skippedWidgets": skipped,
            }
        for item in planned:
            insert_dashboard_widget(connection, item)
        connection.commit()
    return {
        "ok": True,
        "confirmed": True,
        "dashboardKey": dashboard_key,
        "tableKey": resolved_table_key,
        "addedCount": len(planned),
        "widgets": planned,
        "skippedCount": len(skipped),
    }


def add_dashboard_widget(
    *,
    dashboard_key: str,
    widget_type: str,
    options: dict[str, Any],
    confirm: bool,
    open_db: Callable[[], Any],
    build_widget_proposal: Callable[[sqlite3.Connection, str, str, dict[str, Any]], dict[str, Any]],
    insert_dashboard_widget: Callable[[sqlite3.Connection, dict[str, Any]], None],
) -> dict[str, Any]:
    with open_db() as connection:
        proposal = build_widget_proposal(connection, dashboard_key, widget_type, options)
        if not confirm:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "proposedWidget": proposal}
        insert_dashboard_widget(connection, proposal)
        connection.commit()
    return {"ok": True, "confirmed": True, "addedWidget": proposal}


def add_dashboard_relationship_widget(
    *,
    dashboard_key: str,
    widget_type: str,
    options: dict[str, Any],
    confirm: bool,
    open_db: Callable[[], Any],
    build_relationship_widget_proposal: Callable[[sqlite3.Connection, str, str, dict[str, Any]], dict[str, Any]],
    insert_dashboard_widget: Callable[[sqlite3.Connection, dict[str, Any]], None],
) -> dict[str, Any]:
    with open_db() as connection:
        proposal = build_relationship_widget_proposal(connection, dashboard_key, widget_type, options)
        if not confirm:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "proposedWidget": proposal,
                "relationship": proposal["relationship"],
            }
        insert_dashboard_widget(connection, proposal)
        connection.commit()
    return {"ok": True, "confirmed": True, "addedWidget": proposal, "relationship": proposal["relationship"]}


def set_dashboard_widget(
    *,
    widget_key: str,
    widget_type: str | None,
    title: str | None,
    table_key: str | None,
    view_key: str | None,
    config_updates: dict[str, Any],
    style_options: dict[str, Any],
    filter_values: list[str],
    clear_filters: bool,
    confirm: bool,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    dashboard_widget_row_to_dict: Callable[[sqlite3.Row], dict[str, Any]],
    resolve_view: Callable[[sqlite3.Connection, str], dict[str, Any]],
    preferred_table_key: Callable[[sqlite3.Connection, str | None], str],
    registry_for_table: Callable[[sqlite3.Connection, str], sqlite3.Row | None],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    widget_filters_from_args: Callable[[list[str], list[str]], list[dict[str, Any]]],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        row = connection.execute(
            "SELECT * FROM dashboard_widgets WHERE widget_key = ? AND workspace_id = ?",
            (widget_key, workspace_id),
        ).fetchone()
        if not row:
            raise ValueError(f"Unknown widget: {widget_key}")
        current = dashboard_widget_row_to_dict(row)
        config = dict(current["config"] if isinstance(current["config"], dict) else {})
        next_type = widget_type or current["widget_type"]
        next_table_key = current["table_key"]
        if view_key:
            view = resolve_view(connection, view_key)
            next_table_key = view["table_key"]
            config["dataMode"] = "view"
            config["viewKey"] = view["view_key"]
            config["subtitle"] = view["name"]
            config["columns"] = view["config"].get("columns", config.get("columns", []))
        elif table_key:
            next_table_key = preferred_table_key(connection, table_key)
            config["dataMode"] = "table"
            config.pop("viewKey", None)
        if clear_filters and filter_values:
            raise ValueError("--clear-filters and --filter cannot be used together")
        registry = registry_for_table(connection, next_table_key) if next_table_key else None
        columns = table_columns(connection, registry["physical_table"]) if registry else []
        for key, value in config_updates.items():
            if value is not None:
                config[key] = value
        for key, value in style_options.items():
            config[key] = value
        if clear_filters:
            config["filters"] = []
        elif filter_values:
            config["filters"] = widget_filters_from_args(filter_values, columns)
        proposed = {
            **current,
            "widget_type": next_type,
            "title": title if title is not None else current["title"],
            "table_key": next_table_key,
            "config": config,
        }
        if not confirm:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "currentWidget": current, "proposedWidget": proposed}
        connection.execute(
            """
            UPDATE dashboard_widgets
            SET widget_type = ?, title = ?, table_key = ?, config_json = ?
            WHERE widget_key = ? AND workspace_id = ?
            """,
            (next_type, proposed["title"], next_table_key, json.dumps(config, ensure_ascii=False), widget_key, workspace_id),
        )
        connection.commit()
    return {"ok": True, "confirmed": True, "updatedWidget": proposed}


def copy_dashboard_widget(
    *,
    widget_key: str,
    dashboard_key: str | None,
    title: str | None,
    clear_filters: bool,
    confirm: bool,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    dashboard_widget_row_to_dict: Callable[[sqlite3.Row], dict[str, Any]],
    dashboard_exists: Callable[[sqlite3.Connection, str], bool],
    unique_key: Callable[[str], str],
    next_dashboard_widget_sort_order: Callable[[sqlite3.Connection, str, str], int],
    insert_dashboard_widget: Callable[[sqlite3.Connection, dict[str, Any]], None],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        row = connection.execute(
            "SELECT * FROM dashboard_widgets WHERE widget_key = ? AND workspace_id = ?",
            (widget_key, workspace_id),
        ).fetchone()
        if not row:
            raise ValueError(f"Unknown widget: {widget_key}")
        source = dashboard_widget_row_to_dict(row)
        config = dict(source["config"] if isinstance(source["config"], dict) else {})
        if clear_filters:
            config["filters"] = []
        target_dashboard = dashboard_key or source["dashboard_key"]
        if not dashboard_exists(connection, target_dashboard):
            raise ValueError(f"Unknown dashboard: {target_dashboard}")
        proposed = {
            **source,
            "widget_key": unique_key(f"widget_{source['widget_type']}_copy"),
            "dashboard_key": target_dashboard,
            "title": title or f"{source['title']} Copy",
            "config": config,
            "sort_order": next_dashboard_widget_sort_order(connection, target_dashboard, workspace_id),
        }
        if not confirm:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "sourceWidget": source, "proposedWidget": proposed}
        insert_dashboard_widget(connection, proposed)
        connection.commit()
    return {"ok": True, "confirmed": True, "copiedWidget": proposed, "sourceWidgetKey": widget_key}


def remove_dashboard_widget(
    *,
    widget_key: str,
    confirm: bool,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    dashboard_widget_row_to_dict: Callable[[sqlite3.Row], dict[str, Any]],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        row = connection.execute(
            "SELECT * FROM dashboard_widgets WHERE widget_key = ? AND workspace_id = ?",
            (widget_key, workspace_id),
        ).fetchone()
        if not row:
            raise ValueError(f"Unknown widget: {widget_key}")
        source = dashboard_widget_row_to_dict(row)
        if not confirm:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "removedWidget": source}
        connection.execute("DELETE FROM dashboard_widgets WHERE widget_key = ? AND workspace_id = ?", (widget_key, workspace_id))
        connection.commit()
    return {"ok": True, "confirmed": True, "removedWidget": source}
