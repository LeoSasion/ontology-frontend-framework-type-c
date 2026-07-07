from __future__ import annotations

import json
import sqlite3
from typing import Any, Callable


def dashboard_widget_key_exists(connection: sqlite3.Connection, widget_key: str, workspace_id: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM dashboard_widgets WHERE widget_key = ? AND workspace_id = ?",
        (widget_key, workspace_id),
    ).fetchone() is not None


def resolve_dashboard_widget_key(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    requested_key: str,
    fallback_prefix: str,
    unique_key: Callable[[str], str],
) -> str:
    widget_key = requested_key or unique_key(fallback_prefix)
    if dashboard_widget_key_exists(connection, widget_key, workspace_id):
        return unique_key(fallback_prefix)
    return widget_key


def next_dashboard_widget_sort_order(connection: sqlite3.Connection, dashboard_key: str, workspace_id: str) -> int:
    return int(
        connection.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 10 FROM dashboard_widgets WHERE dashboard_key = ? AND workspace_id = ?",
            (dashboard_key, workspace_id),
        ).fetchone()[0]
    )


def insert_dashboard_widget(connection: sqlite3.Connection, proposed: dict[str, Any]) -> None:
    workspace_id = str(proposed.get("workspace_id") or "").strip()
    if not workspace_id:
        raise ValueError("Dashboard widget insert requires workspace_id")
    connection.execute(
        """
        INSERT INTO dashboard_widgets(widget_key, workspace_id, dashboard_key, widget_type, title, table_key, config_json, sort_order)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            proposed["widget_key"],
            workspace_id,
            proposed["dashboard_key"],
            proposed["widget_type"],
            proposed["title"],
            proposed["table_key"],
            json.dumps(proposed["config"], ensure_ascii=False),
            proposed["sort_order"],
        ),
    )
