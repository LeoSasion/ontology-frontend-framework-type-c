from __future__ import annotations

import sqlite3
from typing import Any, Callable

from dashboard_widget_contracts import B_RELATIONSHIP_WIDGET_TYPES, B_WIDGET_TYPES, widget_config_from_options


def build_dashboard_widget_proposal(
    connection: sqlite3.Connection,
    dashboard_key: str,
    widget_type: str,
    options: dict[str, Any],
    *,
    dashboard_exists: Callable[[sqlite3.Connection, str], bool],
    resolve_view: Callable[[sqlite3.Connection, str], sqlite3.Row],
    preferred_table_key: Callable[[sqlite3.Connection, str | None], str],
    registry_for_table: Callable[[sqlite3.Connection, str], sqlite3.Row | None],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    unique_key: Callable[[str], str],
    resolve_dashboard_widget_key: Callable[..., str],
    next_dashboard_widget_sort_order: Callable[[sqlite3.Connection, str, str], int],
) -> dict[str, Any]:
    if widget_type not in B_WIDGET_TYPES:
        raise ValueError(f"Unsupported widget type: {widget_type}")
    if not dashboard_exists(connection, dashboard_key):
        raise ValueError(f"Unknown dashboard: {dashboard_key}")
    view_key = str(options.get("viewKey") or "")
    view = resolve_view(connection, view_key) if view_key else None
    table_key = view["table_key"] if view else preferred_table_key(connection, str(options.get("tableKey") or "") or None)
    registry = registry_for_table(connection, table_key)
    table_name = registry["display_name"] if registry else table_key
    config = widget_config_from_options({**options, "type": widget_type, "tableKey": table_key, "tableName": table_name})
    if view:
        config["dataMode"] = "view"
        config["viewKey"] = view["view_key"]
        config.setdefault("columns", view["config"].get("columns", []))
        config["subtitle"] = view["name"]
    workspace_id = active_workspace_id(connection)
    widget_key = resolve_dashboard_widget_key(
        connection,
        workspace_id=workspace_id,
        requested_key=str(options.get("widgetKey") or ""),
        fallback_prefix=f"widget_{widget_type}",
        unique_key=unique_key,
    )
    sort_order = next_dashboard_widget_sort_order(connection, dashboard_key, workspace_id)
    return {
        "widget_key": widget_key,
        "workspace_id": workspace_id,
        "dashboard_key": dashboard_key,
        "widget_type": widget_type,
        "title": str(options.get("title") or f"{table_name} {widget_type}"),
        "table_key": table_key,
        "config": config,
        "sort_order": sort_order,
    }


def build_dashboard_relationship_widget_proposal(
    connection: sqlite3.Connection,
    dashboard_key: str,
    widget_type: str,
    options: dict[str, Any],
    *,
    safe_aggregations: set[str],
    dashboard_exists: Callable[[sqlite3.Connection, str], bool],
    resolve_relationship_for_widget: Callable[[sqlite3.Connection, str | None], sqlite3.Row],
    registry_for_table: Callable[[sqlite3.Connection, str], sqlite3.Row | None],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    table_display_name: Callable[[sqlite3.Connection, str], str],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    unique_key: Callable[[str], str],
    resolve_dashboard_widget_key: Callable[..., str],
    next_dashboard_widget_sort_order: Callable[[sqlite3.Connection, str, str], int],
) -> dict[str, Any]:
    if widget_type not in B_RELATIONSHIP_WIDGET_TYPES:
        raise ValueError(f"Unsupported relationship widget type: {widget_type}")
    if not dashboard_exists(connection, dashboard_key):
        raise ValueError(f"Unknown dashboard: {dashboard_key}")
    relation = resolve_relationship_for_widget(connection, str(options.get("relationship") or "") or None)
    left_table_key = relation["left_table_key"]
    right_table_key = relation["right_table_key"]
    left_registry = registry_for_table(connection, left_table_key)
    right_registry = registry_for_table(connection, right_table_key)
    if not left_registry or not right_registry:
        raise ValueError("Relationship references an unavailable table.")
    left_columns = table_columns(connection, left_registry["physical_table"])
    right_columns = table_columns(connection, right_registry["physical_table"])
    group_field = str(options.get("group") or options.get("dimension") or relation["left_field"] or "")
    measure_field = str(options.get("measure") or "")
    if group_field and group_field not in left_columns and group_field not in right_columns:
        raise ValueError(f"Unknown relationship group field: {group_field}")
    if measure_field and measure_field not in left_columns and measure_field not in right_columns:
        raise ValueError(f"Unknown relationship measure field: {measure_field}")
    aggregation = str(options.get("aggregation") or options.get("agg") or "count")
    if aggregation not in safe_aggregations:
        raise ValueError(f"Unsupported aggregation: {aggregation}")
    measure_side = "left" if measure_field in left_columns else "right"
    group_side = "left" if group_field in left_columns else "right"
    title = str(options.get("title") or f"{relation['name']} {widget_type}")
    subtitle = str(options.get("subtitle") or f"{table_display_name(connection, left_table_key)} -> {table_display_name(connection, right_table_key)}")
    config = widget_config_from_options(
        {
            **options,
            "type": widget_type,
            "tableKey": left_table_key,
            "tableName": table_display_name(connection, left_table_key),
            "dataMode": "relationship",
            "subtitle": subtitle,
            "dimension": group_field,
            "measure": measure_field,
            "aggregation": "count" if aggregation == "count-distinct" else aggregation,
        }
    )
    config["dataMode"] = "relationship"
    config["relationship"] = {
        "relationKey": relation["relation_key"],
        "leftTableKey": left_table_key,
        "rightTableKey": right_table_key,
        "fieldMappings": [{"leftField": relation["left_field"], "rightField": relation["right_field"]}],
        "joinType": relation["join_type"],
        "groupFields": ([{"side": group_side, "field": group_field}] if group_field else []),
        "measure": ({"side": measure_side, "field": measure_field} if measure_field else None),
        "aggregation": aggregation,
    }
    workspace_id = active_workspace_id(connection)
    widget_key = resolve_dashboard_widget_key(
        connection,
        workspace_id=workspace_id,
        requested_key=str(options.get("widgetKey") or ""),
        fallback_prefix=f"relation_{widget_type}",
        unique_key=unique_key,
    )
    sort_order = next_dashboard_widget_sort_order(connection, dashboard_key, workspace_id)
    return {
        "widget_key": widget_key,
        "workspace_id": workspace_id,
        "dashboard_key": dashboard_key,
        "widget_type": widget_type,
        "title": title,
        "table_key": left_table_key,
        "config": config,
        "sort_order": sort_order,
        "relationship": relation,
    }
