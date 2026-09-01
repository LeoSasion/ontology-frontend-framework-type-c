from __future__ import annotations

import argparse
import json
import sqlite3
from typing import Any, Callable

from bi_cli_core import DUCKDB_PATH, parse_csv_list, unique_key
from query_runtime import (
    ValidatedDuckDBQuery,
    open_batch_validated_duckdb_query,
    open_validated_duckdb_query,
    replica_expectation,
)
from table_query_tools import build_table_query


BATCH_MAX_PLANS = 32
BATCH_RESPONSE_MAX_BYTES = 4 * 1_048_576


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
    workspace_id: str | None = None,
) -> dict[str, Any]:
    resolved_workspace_id = str(workspace_id or active_workspace_id(connection))
    if table_key:
        row = connection.execute(
            "SELECT * FROM saved_views WHERE view_key = ? AND table_key = ? AND workspace_id = ?",
            (view_key, table_key, resolved_workspace_id),
        ).fetchone()
    else:
        row = connection.execute(
            "SELECT * FROM saved_views WHERE view_key = ? AND workspace_id = ?",
            (view_key, resolved_workspace_id),
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
        "cursor": args.cursor,
        "limit": args.limit,
        "groupFields": args.group,
        "measure": args.measure,
        "aggregation": args.agg,
    }


def table_query_payload_from_plan(plan: dict[str, Any], table_key: str, view: dict[str, Any] | None = None) -> dict[str, Any]:
    """Translate one JSON batch plan without constructing an argparse namespace."""
    view_config = view["config"] if view and isinstance(view.get("config"), dict) else {}
    mode = str(plan.get("mode") or view_config.get("mode") or "detail")
    raw_columns = plan.get("columns") if "columns" in plan else view_config.get("columns")
    raw_filters = plan.get("filters") if "filters" in plan else []
    base_filters = view_config.get("filters") if isinstance(view_config.get("filters"), list) else []
    raw_sort = plan.get("sort") if "sort" in plan else view_config.get("sort")
    return {
        "tableKey": table_key,
        "mode": mode,
        "columns": raw_columns,
        "filters": [*base_filters, *(raw_filters if isinstance(raw_filters, list) else [])],
        "sort": raw_sort if isinstance(raw_sort, (list, dict, str)) else [],
        "search": plan.get("search") if "search" in plan else view_config.get("search", ""),
        "cursor": plan.get("cursor"),
        "limit": plan.get("limit"),
        "groupFields": plan.get("groupFields"),
        "measure": plan.get("measure"),
        "aggregation": plan.get("aggregation"),
    }


def _batch_item_error(error: Exception) -> dict[str, Any]:
    message = str(error).strip() or "query-table-batch-item-failed"
    return {
        "ok": False,
        "errorCode": message.split(":", 1)[0][:120],
        "error": message[:240],
    }


def _batch_response_bytes(payload: dict[str, Any]) -> int:
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8"))


def _finalize_batch_response(
    results: list[dict[str, Any]],
    *,
    plan_count: int,
) -> dict[str, Any]:
    """Keep the batch response below one hard byte budget deterministically."""
    batch: dict[str, Any] = {
        "schema": "aibi-query-table-batch/v1",
        "planCount": plan_count,
        "succeeded": sum(1 for item in results if item.get("ok") is True),
        "failed": sum(1 for item in results if item.get("ok") is not True),
        "truncatedByBytes": False,
        "responseBytes": 0,
        "results": results,
    }
    response: dict[str, Any] = {"ok": True, "batchQuery": batch}
    def settle_response_bytes() -> int:
        for _ in range(8):
            measured = _batch_response_bytes(response)
            if int(batch["responseBytes"]) == measured:
                return measured
            batch["responseBytes"] = measured
        return _batch_response_bytes(response)

    settle_response_bytes()
    if int(batch["responseBytes"]) > BATCH_RESPONSE_MAX_BYTES:
        batch["truncatedByBytes"] = True
        # Preserve the earliest results first; replace oversized successes with
        # bounded item errors so later widgets remain independently addressable.
        for index in range(len(results) - 1, -1, -1):
            item = results[index]
            if item.get("ok") is not True:
                continue
            item.clear()
            item.update({
                "index": index,
                "ok": False,
                "errorCode": "query-table-batch-response-byte-limit",
                "error": "Result omitted by the batch response byte limit",
            })
            batch["succeeded"] = sum(1 for candidate in results if candidate.get("ok") is True)
            batch["failed"] = plan_count - int(batch["succeeded"])
            batch["responseBytes"] = 0
            settle_response_bytes()
            if int(batch["responseBytes"]) <= BATCH_RESPONSE_MAX_BYTES:
                break
        if int(batch["responseBytes"]) > BATCH_RESPONSE_MAX_BYTES:
            # Error strings are already bounded; this branch is defensive in
            # case a future envelope field grows beyond the hard contract.
            batch["results"] = [
                {"index": index, "ok": False, "errorCode": "query-table-batch-response-byte-limit"}
                for index in range(plan_count)
            ]
            batch["succeeded"] = 0
            batch["failed"] = plan_count
            batch["responseBytes"] = 0
            settle_response_bytes()
    return response


def query_table_batch_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    resolve_view: Callable[[sqlite3.Connection, str, str | None, str | None], dict[str, Any]],
    registry_for_table: Callable[[sqlite3.Connection, str, str | None], sqlite3.Row | None],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    """Execute up to 32 table queries against one validated DuckDB snapshot."""
    raw_plans = list(getattr(args, "plan", []) or [])
    if not raw_plans or len(raw_plans) > BATCH_MAX_PLANS:
        raise ValueError(f"query-table-batch requires 1-{BATCH_MAX_PLANS} plans")
    plans: list[dict[str, Any]] = []
    for raw in raw_plans:
        try:
            parsed = json.loads(str(raw))
        except (TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError("query-table-batch plan must be valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("query-table-batch plan must be an object")
        plans.append(parsed)

    prepared: list[dict[str, Any]] = []
    results: list[dict[str, Any] | None] = [None] * len(plans)
    expectations = []
    workspace_id = str(getattr(args, "workspace", "") or "").strip()
    if not workspace_id:
        raise ValueError("query-table-workspace-required")
    with open_db() as connection:
        if active_workspace_id(connection) != workspace_id:
            raise ValueError("query-table-workspace-changed")
        for index, plan in enumerate(plans):
            try:
                view_key = str(plan.get("view") or "").strip()
                table_key = str(plan.get("table") or "").strip()
                view = resolve_view(connection, view_key, table_key or None, workspace_id) if view_key else None
                table_key = str(view["table_key"] if view else table_key).strip()
                if not table_key:
                    raise ValueError("query-table requires table or view")
                registry = registry_for_table(connection, table_key, workspace_id)
                if not registry:
                    raise ValueError(f"Unknown table: {table_key}")
                columns = table_columns(connection, registry["physical_table"])
                expectation = replica_expectation(registry)
                payload = table_query_payload_from_plan(plan, table_key, view)
                payload["sourceVersion"] = expectation.version_id
                payload["expectedRowCount"] = expectation.row_count
                prepared.append({
                    "index": index,
                    "physicalTable": str(registry["physical_table"]),
                    "tableKey": table_key,
                    "registry": registry,
                    "columns": columns,
                    "payload": payload,
                    "view": view,
                    "expectation": expectation,
                })
                expectations.append(expectation)
            except Exception as error:
                results[index] = {"index": index, **_batch_item_error(error)}

        if expectations:
            try:
                with open_batch_validated_duckdb_query(DUCKDB_PATH, expectations) as (analysis_connection, validation_errors):
                    validated_by_table = {
                        str(item["logicalTable"]): dict(item)
                        for item in analysis_connection.replicas
                    }
                    for item in prepared:
                        index = int(item["index"])
                        physical_table = str(item["physicalTable"])
                        validation_error = validation_errors.get(physical_table)
                        if validation_error:
                            results[index] = {
                                "index": index,
                                "ok": False,
                                "errorCode": validation_error.split(":", 1)[0][:120],
                                "error": validation_error[:240],
                            }
                            continue
                        replica = validated_by_table.get(physical_table)
                        if replica is None:
                            results[index] = {
                                "index": index,
                                "ok": False,
                                "errorCode": "replica-binding-missing",
                                "error": f"replica-binding-missing:{physical_table}",
                            }
                            continue
                        try:
                            item_connection = ValidatedDuckDBQuery(analysis_connection.connection, [replica])
                            query_result = build_table_query(
                                connection,
                                item_connection,
                                physical_table,
                                item["columns"],
                                item["payload"],
                            )
                            query_result["tableKey"] = item["tableKey"]
                            query_result["workspaceId"] = str(item["registry"]["workspace_id"])
                            query_result["tableName"] = item["registry"]["display_name"]
                            query_result["sqlIntent"] = "Whitelist table query; no user SQL accepted"
                            view = item["view"]
                            if view:
                                query_result["viewKey"] = view["view_key"]
                                query_result["viewName"] = view["name"]
                            results[index] = {"index": index, "ok": True, "tableQuery": query_result}
                        except Exception as error:
                            results[index] = {"index": index, **_batch_item_error(error)}
            except Exception as error:
                # Reader-open/manifest errors affect every prepared item, but
                # plans that failed control-plane resolution remain isolated.
                for item in prepared:
                    index = int(item["index"])
                    if results[index] is None:
                        results[index] = {"index": index, **_batch_item_error(error)}

    final_results = [item if item is not None else {
        "index": index,
        "ok": False,
        "errorCode": "query-table-batch-item-missing",
        "error": "Batch query did not produce an item result",
    } for index, item in enumerate(results)]
    return _finalize_batch_response(final_results, plan_count=len(plans))


def query_table_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    resolve_view: Callable[[sqlite3.Connection, str, str | None, str | None], dict[str, Any]],
    registry_for_table: Callable[[sqlite3.Connection, str, str | None], sqlite3.Row | None],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    workspace_id = str(getattr(args, "workspace", "") or "").strip()
    if not workspace_id:
        raise ValueError("query-table-workspace-required")
    with open_db() as connection:
        if active_workspace_id(connection) != workspace_id:
            raise ValueError("query-table-workspace-changed")
        view = resolve_view(connection, args.view, args.table, workspace_id) if args.view else None
        table_key = view["table_key"] if view else args.table
        if not table_key:
            raise ValueError("query-table requires --table or --view")
        registry = registry_for_table(connection, table_key, workspace_id)
        if not registry:
            raise ValueError(f"Unknown table: {table_key}")
        columns = table_columns(connection, registry["physical_table"])
        expectation = replica_expectation(registry)
        payload = table_query_payload_from_args(args, table_key, view)
        payload["sourceVersion"] = expectation.version_id
        payload["expectedRowCount"] = expectation.row_count
        with open_validated_duckdb_query(DUCKDB_PATH, [expectation]) as analysis_connection:
            result = build_table_query(
                connection,
                analysis_connection,
                registry["physical_table"],
                columns,
                payload,
            )
        result["tableKey"] = table_key
        result["workspaceId"] = str(registry["workspace_id"])
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
        "limit": 5,
        "groupFields": [],
        "measure": "",
        "aggregation": "count",
    }
    expectation = replica_expectation(registry)
    preview_payload["sourceVersion"] = expectation.version_id
    preview_payload["expectedRowCount"] = expectation.row_count
    with open_validated_duckdb_query(DUCKDB_PATH, [expectation]) as analysis_connection:
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
