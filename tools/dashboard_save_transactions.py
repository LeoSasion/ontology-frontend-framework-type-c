from __future__ import annotations

import json
import sqlite3
from typing import Any

from dashboard_widget_operations import insert_dashboard_widget


def upsert_dashboard_record(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    dashboard_key: str,
    dashboard_name: str,
    default_table_key: str,
    layout: dict[str, Any],
    now: str,
    created_by: str = "manual",
    agent_managed: int = 0,
) -> None:
    dashboard = connection.execute(
        "SELECT 1 FROM dashboards WHERE dashboard_key = ? AND workspace_id = ?",
        (dashboard_key, workspace_id),
    ).fetchone()
    layout_json = json.dumps(layout, ensure_ascii=False)
    if dashboard:
        connection.execute(
            """
            UPDATE dashboards
            SET name = ?, default_table_key = ?, layout_json = ?, updated_at = ?
            WHERE dashboard_key = ? AND workspace_id = ?
            """,
            (dashboard_name, default_table_key, layout_json, now, dashboard_key, workspace_id),
        )
    else:
        connection.execute(
            """
            INSERT INTO dashboards(dashboard_key, name, workspace_id, default_table_key, layout_json, created_by, agent_managed, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (dashboard_key, dashboard_name, workspace_id, default_table_key, layout_json, created_by, agent_managed, now, now),
        )


def replace_dashboard_widgets(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    dashboard_key: str,
    widgets: list[dict[str, Any]],
) -> None:
    connection.execute(
        "DELETE FROM dashboard_widgets WHERE dashboard_key = ? AND workspace_id = ?",
        (dashboard_key, workspace_id),
    )
    for widget in widgets:
        insert_dashboard_widget(connection, widget)


def save_dashboard_with_widgets(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    dashboard_key: str,
    dashboard_name: str,
    default_table_key: str,
    layout: dict[str, Any],
    widgets: list[dict[str, Any]],
    now: str,
    created_by: str = "manual",
    agent_managed: int = 0,
) -> None:
    upsert_dashboard_record(
        connection,
        workspace_id=workspace_id,
        dashboard_key=dashboard_key,
        dashboard_name=dashboard_name,
        default_table_key=default_table_key,
        layout=layout,
        now=now,
        created_by=created_by,
        agent_managed=agent_managed,
    )
    replace_dashboard_widgets(
        connection,
        workspace_id=workspace_id,
        dashboard_key=dashboard_key,
        widgets=widgets,
    )


def dashboard_snapshot(connection: sqlite3.Connection, *, workspace_id: str, dashboard_key: str) -> dict[str, Any]:
    dashboard_row = connection.execute(
        "SELECT * FROM dashboards WHERE dashboard_key = ? AND workspace_id = ?",
        (dashboard_key, workspace_id),
    ).fetchone()
    if not dashboard_row:
        raise ValueError(f"Dashboard not found after save: {dashboard_key}")
    saved_widgets = [
        dict(row)
        for row in connection.execute(
            "SELECT * FROM dashboard_widgets WHERE dashboard_key = ? AND workspace_id = ? ORDER BY sort_order",
            (dashboard_key, workspace_id),
        ).fetchall()
    ]
    return {
        **dict(dashboard_row),
        "layout": json.loads(dashboard_row["layout_json"]),
        "widgets": [
            {**widget, "config": json.loads(str(widget.pop("config_json") or "{}"))}
            for widget in saved_widgets
        ],
    }
