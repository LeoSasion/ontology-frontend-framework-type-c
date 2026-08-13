from __future__ import annotations

import argparse
import json
import sqlite3
from typing import Any, Callable

from bi_cli_core import DUCKDB_PATH, parse_csv_list, unique_key
from query_runtime import open_validated_duckdb_query, replica_expectation
from table_query_tools import build_table_query


def parse_query_filter(raw: str) -> dict[str, Any]:
    field, sep, rest = str(raw or "").partition(":")
    if not sep:
        raise ValueError("Filter format must be field:operator:value")
    operator, _sep, value = rest.partition(":")
    return {"field": field.strip(), "operator": operator.strip() or "contains", "value": value}


def list_from_value(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return parse_csv_list(str(value or ""))


def parse_query_sort(raw: str) -> dict[str, str]:
    field, _sep, direction = str(raw or "").partition(":")
    return {"field": field.strip(), "direction": direction.strip().lower() or "asc"}


def view_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    view = dict(row)
    view["config"] = json.loads(view.pop("config_json"))
    view["is_default"] = bool(view["is_default"])
    view["agent_managed"] = bool(view["agent_managed"])
    return view


def resolve_view(
    connection: sqlite3.Connection,
    view_key: str,
    table_key: str | None = None,
    *,
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    workspace_id = active_workspace_id(connection)
    if table_key:
        row = connection.execute(
            "SELECT * FROM saved_views WHERE view_key = ? AND table_key = ? AND workspace_id = ?",
            (view_key, table_key, workspace_id),
        ).fetchone()
    else:
        row = connection.execute(
            "SELECT * FROM saved_views WHERE view_key = ? AND workspace_id = ?",
            (view_key, workspace_id),
        ).fetchone()
    if not row:
        raise ValueError(f"Unknown saved view: {view_key}")
    return view_row_to_dict(row)


def saved_view_summary(
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    registry_for_table: Callable[[sqlite3.Connection, str], sqlite3.Row | None],
) -> dict[str, Any]:
    view = view_row_to_dict(row)
    registry = registry_for_table(connection, view["table_key"])
    config = view["config"] if isinstance(view["config"], dict) else {}
    columns = list_from_value(config.get("columns")) if "columns" in config else []
    filters = config.get("filters") if isinstance(config.get("filters"), list) else []
    sort = config.get("sort") if isinstance(config.get("sort"), list) else []
    return {
        "view_key": view["view_key"],
        "name": view["name"],
        "tag_name": view["tag_name"],
        "table_key": view["table_key"],
        "table_name": registry["display_name"] if registry else view["table_key"],
        "config": config,
        "is_default": view["is_default"],
        "sort_order": view["sort_order"],
        "created_by": view["created_by"],
        "agent_managed": view["agent_managed"],
        "created_at": view["created_at"],
        "updated_at": view["updated_at"],
        "columnCount": len(columns),
        "filterCount": len(filters),
        "sortCount": len(sort),
        "search": str(config.get("search") or ""),
    }


def list_views_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    saved_view_summary: Callable[[sqlite3.Connection, sqlite3.Row], dict[str, Any]],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        if args.table:
            rows = connection.execute(
                "SELECT * FROM saved_views WHERE table_key = ? AND workspace_id = ? ORDER BY sort_order, created_at",
                (args.table, workspace_id),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM saved_views WHERE workspace_id = ? ORDER BY table_key, sort_order, created_at",
                (workspace_id,),
            ).fetchall()
        views = [saved_view_summary(connection, row) for row in rows]
    return {"ok": True, "savedViews": views}


def table_query_payload_from_args(args: argparse.Namespace, table_key: str, view: dict[str, Any] | None = None) -> dict[str, Any]:
    view_config = view["config"] if view and isinstance(view.get("config"), dict) else {}
    mode = args.mode or str(view_config.get("mode") or "detail")
    columns = args.column or view_config.get("columns")
    filters = [*(view_config.get("filters") if isinstance(view_config.get("filters"), list) else []), *[parse_query_filter(item) for item in args.filter]]
    sort = [parse_query_sort(item) for item in args.sort] or (view_config.get("sort") if isinstance(view_config.get("sort"), list) else [])
    return {
        "tableKey": table_key,
        "mode": mode,
        "columns": columns,
        "filters": filters,
        "sort": sort,
        "search": args.search if args.search is not None else view_config.get("search", ""),
        "offset": args.offset,
        "limit": args.limit,
        "groupFields": args.group,
        "measure": args.measure,
        "aggregation": args.agg,
    }


def query_table_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    resolve_view: Callable[[sqlite3.Connection, str, str | None], dict[str, Any]],
    registry_for_table: Callable[[sqlite3.Connection, str], sqlite3.Row | None],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
) -> dict[str, Any]:
    with open_db() as connection:
        view = resolve_view(connection, args.view, args.table) if args.view else None
        table_key = view["table_key"] if view else args.table
        if not table_key:
            raise ValueError("query-table requires --table or --view")
        registry = registry_for_table(connection, table_key)
        if not registry:
            raise ValueError(f"Unknown table: {table_key}")
        columns = table_columns(connection, registry["physical_table"])
        with open_validated_duckdb_query(DUCKDB_PATH, [replica_expectation(registry)]) as analysis_connection:
            result = build_table_query(
                connection,
                analysis_connection,
                registry["physical_table"],
                columns,
                table_query_payload_from_args(args, table_key, view),
            )
        result["tableKey"] = table_key
        result["tableName"] = registry["display_name"]
        result["sqlIntent"] = "Whitelist table query; no user SQL accepted"
        if view:
            result["viewKey"] = view["view_key"]
            result["viewName"] = view["name"]
    return {"ok": True, "tableQuery": result}


def view_config_from_args(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "mode": args.mode,
        "columns": list_from_value(args.columns),
        "filters": [parse_query_filter(item) for item in args.filter],
        "sort": [parse_query_sort(item) for item in args.sort],
        "search": args.search or "",
    }


def normalize_view_config(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": str(config.get("mode") or "detail"),
        "columns": list_from_value(config.get("columns")),
        "filters": [item for item in (config.get("filters") or []) if isinstance(item, dict)],
        "sort": [item for item in (config.get("sort") or []) if isinstance(item, dict)],
        "search": str(config.get("search") or ""),
    }


def build_save_view_plan(
    connection: sqlite3.Connection,
    table_key: str,
    name: str,
    config: dict[str, Any],
    view_key: str = "",
    tag_name: str = "",
    created_by: str = "user",
    agent_managed: int = 0,
    *,
    active_workspace_id: Callable[[sqlite3.Connection], str],
    registry_for_table: Callable[[sqlite3.Connection, str], sqlite3.Row | None],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    analysis_columns_for_table: Callable[[sqlite3.Connection, str], set[str]],
) -> dict[str, Any]:
    registry = registry_for_table(connection, table_key)
    if not registry:
        raise ValueError(f"Unknown table: {table_key}")
    columns = table_columns(connection, registry["physical_table"])
    analysis_columns = analysis_columns_for_table(connection, table_key)
    normalized = normalize_view_config(config)
    if not normalized["columns"]:
        normalized["columns"] = columns[:6]
    referenced: list[str] = []
    referenced.extend(str(column) for column in normalized["columns"])
    referenced.extend(str(item.get("field") or "") for item in normalized["filters"])
    referenced.extend(str(item.get("field") or "") for item in normalized["sort"])
    missing = sorted({field for field in referenced if field and field not in analysis_columns})
    if missing:
        raise ValueError(f"Saved view references missing fields: {', '.join(missing)}")
    preview_payload = {
        "tableKey": table_key,
        "mode": normalized["mode"],
        "columns": normalized["columns"],
        "filters": normalized["filters"],
        "sort": normalized["sort"],
        "search": normalized["search"],
        "offset": 0,
        "limit": 5,
        "groupFields": [],
        "measure": "",
        "aggregation": "count",
    }
    with open_validated_duckdb_query(DUCKDB_PATH, [replica_expectation(registry)]) as analysis_connection:
        preview = build_table_query(
            connection,
            analysis_connection,
            registry["physical_table"],
            columns,
            preview_payload,
        )
    return {
        "view_key": view_key or unique_key("view"),
        "workspace_id": active_workspace_id(connection),
        "name": name,
        "tag_name": tag_name or "保存的筛选口径",
        "table_key": table_key,
        "table_name": registry["display_name"],
        "config": normalized,
        "created_by": created_by,
        "agent_managed": bool(agent_managed),
        "preview": {
            "mode": preview.get("mode"),
            "rowCount": len(preview.get("rows") or []),
            "columns": preview.get("columns") or normalized["columns"],
            "filters": normalized["filters"],
            "sort": normalized["sort"],
        },
    }


def execute_save_view_plan(
    connection: sqlite3.Connection,
    proposed: dict[str, Any],
    *,
    now_iso: Callable[[], str],
    upsert_navigation_module: Callable[..., Any],
    saved_view_summary: Callable[[sqlite3.Connection, sqlite3.Row], dict[str, Any]],
) -> dict[str, Any]:
    now = now_iso()
    config = proposed["config"]
    existing = connection.execute(
        "SELECT * FROM saved_views WHERE view_key = ? AND workspace_id = ?",
        (proposed["view_key"], proposed["workspace_id"]),
    ).fetchone()
    if existing:
        connection.execute(
            """
            UPDATE saved_views
            SET name = ?, tag_name = ?, table_key = ?, config_json = ?, created_by = ?, agent_managed = ?, updated_at = ?
            WHERE view_key = ? AND workspace_id = ?
            """,
            (
                proposed["name"],
                proposed["tag_name"],
                proposed["table_key"],
                json.dumps(config, ensure_ascii=False),
                proposed["created_by"],
                1 if proposed["agent_managed"] else 0,
                now,
                proposed["view_key"],
                proposed["workspace_id"],
            ),
        )
    else:
        sort_order = connection.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 10 FROM saved_views WHERE table_key = ? AND workspace_id = ?",
            (proposed["table_key"], proposed["workspace_id"]),
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO saved_views(
              view_key, workspace_id, name, tag_name, table_key, config_json, is_default,
              sort_order, created_by, agent_managed, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?)
            """,
            (
                proposed["view_key"],
                proposed["workspace_id"],
                proposed["name"],
                proposed["tag_name"],
                proposed["table_key"],
                json.dumps(config, ensure_ascii=False),
                sort_order,
                proposed["created_by"],
                1 if proposed["agent_managed"] else 0,
                now,
                now,
            ),
        )
    upsert_navigation_module(
        connection,
        module_key=f"view:{proposed['view_key']}",
        name=proposed["name"],
        module_type="view",
        table_key=proposed["table_key"],
        created_by=proposed["created_by"],
        agent_managed=1 if proposed["agent_managed"] else 0,
    )
    row = connection.execute(
        "SELECT * FROM saved_views WHERE view_key = ? AND workspace_id = ?",
        (proposed["view_key"], proposed["workspace_id"]),
    ).fetchone()
    return saved_view_summary(connection, row)


def save_view_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    build_save_view_plan: Callable[[sqlite3.Connection, str, str, dict[str, Any], str, str, str, int], dict[str, Any]],
    execute_save_view_plan: Callable[[sqlite3.Connection, dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    with open_db() as connection:
        proposed = build_save_view_plan(
            connection,
            args.table,
            args.name,
            view_config_from_args(args),
            args.view or "",
            args.tag or "保存的筛选口径",
            "agent" if args.agent else "user",
            1 if args.agent else 0,
        )
        if not args.yes:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "proposed": proposed}
        saved_view = execute_save_view_plan(connection, proposed)
        connection.commit()
    return {"ok": True, "confirmed": True, "savedView": saved_view}


def copy_view_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    resolve_view: Callable[[sqlite3.Connection, str], dict[str, Any]],
    saved_view_summary: Callable[[sqlite3.Connection, sqlite3.Row], dict[str, Any]],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    with open_db() as connection:
        source = resolve_view(connection, args.view)
        proposed = {
            "view_key": unique_key("view"),
            "source_view_key": source["view_key"],
            "name": args.name or f"{source['name']} Copy",
            "tag_name": args.tag if args.tag is not None else source["tag_name"],
            "table_key": source["table_key"],
            "config": source["config"],
        }
        if not args.yes:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "proposed": proposed}
        now = now_iso()
        workspace_id = active_workspace_id(connection)
        sort_order = connection.execute(
            "SELECT COALESCE(MAX(sort_order), 0) + 10 FROM saved_views WHERE table_key = ? AND workspace_id = ?",
            (source["table_key"], workspace_id),
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO saved_views(
              view_key, workspace_id, name, tag_name, table_key, config_json, is_default,
              sort_order, created_by, agent_managed, created_at, updated_at
            )
            VALUES(?, ?, ?, ?, ?, ?, 0, ?, 'user', 0, ?, ?)
            """,
            (
                proposed["view_key"],
                workspace_id,
                proposed["name"],
                proposed["tag_name"],
                proposed["table_key"],
                json.dumps(proposed["config"], ensure_ascii=False),
                sort_order,
                now,
                now,
            ),
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM saved_views WHERE view_key = ? AND workspace_id = ?",
            (proposed["view_key"], workspace_id),
        ).fetchone()
        saved_view = saved_view_summary(connection, row)
    return {"ok": True, "confirmed": True, "sourceViewKey": source["view_key"], "savedView": saved_view}


def delete_view_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    resolve_view: Callable[[sqlite3.Connection, str], dict[str, Any]],
) -> dict[str, Any]:
    with open_db() as connection:
        source = resolve_view(connection, args.view)
        workspace_id = active_workspace_id(connection)
        view_count = connection.execute(
            "SELECT COUNT(*) FROM saved_views WHERE table_key = ? AND workspace_id = ?",
            (source["table_key"], workspace_id),
        ).fetchone()[0]
        if view_count <= 1:
            raise ValueError("Cannot delete the only view for a table")
        if not args.yes:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "proposed": {"deleteViewKey": source["view_key"], "name": source["name"]}}
        connection.execute(
            "DELETE FROM saved_views WHERE view_key = ? AND workspace_id = ?",
            (source["view_key"], workspace_id),
        )
        connection.commit()
    return {"ok": True, "confirmed": True, "deletedViewKey": source["view_key"]}
