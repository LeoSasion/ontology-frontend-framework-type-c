from __future__ import annotations

import argparse
import sqlite3
from typing import Any

from bi_cli_core import DUCKDB_PATH, now_iso, quote_identifier
from bi_cli_io_services import analysis_columns_for_table
from bi_cli_schema import active_workspace_id, open_db, registry_for_table, table_columns, upsert_navigation_module
from bi_cli_source_commands import resolve_table_registry
from query_runtime import DuckDBUnavailable, SAFE_AGGREGATIONS, run_duckdb_aggregate_query, run_sqlite_aggregate_query
from query_plan_receipt_service import create_query_plan_receipt
from saved_view_query_service import (
    build_save_view_plan as build_save_view_plan_service,
    copy_view_command as copy_view_command_service,
    delete_view_command as delete_view_command_service,
    execute_save_view_plan as execute_save_view_plan_service,
    list_views_command as list_views_command_service,
    query_table_command as query_table_command_service,
    resolve_view as resolve_view_service,
    save_view_command as save_view_command_service,
    saved_view_summary as saved_view_summary_service,
)

def query_command(args: argparse.Namespace) -> dict[str, Any]:
    if args.agg not in SAFE_AGGREGATIONS:
        raise ValueError(f"Unsupported aggregation: {args.agg}")
    with open_db() as connection:
        registry = resolve_table_registry(connection, args.table)
        physical_table = registry["physical_table"]
        table_columns = [row["name"] for row in connection.execute(f"PRAGMA table_info({quote_identifier(physical_table)})")]
        if args.group and args.group not in table_columns:
            raise ValueError(f"Unknown group field: {args.group}")
        if args.measure != "*" and args.measure not in table_columns:
            raise ValueError(f"Unknown measure field: {args.measure}")
        try:
            runtime = run_duckdb_aggregate_query(
                sqlite_connection=connection,
                duckdb_path=DUCKDB_PATH,
                physical_table=physical_table,
                columns=table_columns,
                group=args.group,
                measure=args.measure,
                aggregation=args.agg,
                limit=args.limit,
            )
            fallback_reason = None
        except DuckDBUnavailable as exc:
            runtime = run_sqlite_aggregate_query(
                sqlite_connection=connection,
                physical_table=physical_table,
                group=args.group,
                measure=args.measure,
                aggregation=args.agg,
                limit=args.limit,
            )
            fallback_reason = str(exc)
        rows = runtime.pop("rows")
        workspace_id = active_workspace_id(connection)
        request_text = str(args.request or "").strip() or f"{args.agg} {args.measure} by {args.group or '-'} from {args.table}"
        query_receipt = create_query_plan_receipt(
            connection,
            workspace_id=workspace_id,
            request_text=request_text,
            source_table_key=args.table,
            status="executed",
            group=args.group,
            measure=args.measure,
            aggregation=args.agg,
            runtime=runtime,
            evidence_refs=[{"type": "queryRuntime", "compiledSql": runtime.get("compiledSql")}],
            result_rows=rows,
            now_iso=now_iso,
        )
        connection.commit()
    return {
        "ok": True,
        "query": {
            "table": args.table,
            "mode": "aggregate" if args.group else "metric",
            "group": args.group,
            "measure": args.measure,
            "aggregation": args.agg,
            "sqlIntent": "whitelist aggregate query; no user SQL accepted",
            "runtime": runtime,
            "fallbackReason": fallback_reason,
        },
        "queryPlanReceipt": query_receipt,
        "rows": rows,
    }


def resolve_view(connection: sqlite3.Connection, view_key: str, table_key: str | None = None) -> dict[str, Any]:
    return resolve_view_service(connection, view_key, table_key, active_workspace_id=active_workspace_id)


def saved_view_summary(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    return saved_view_summary_service(connection, row, registry_for_table=registry_for_table)


def list_views_command(args: argparse.Namespace) -> dict[str, Any]:
    return list_views_command_service(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        saved_view_summary=saved_view_summary,
    )


def query_table_command(args: argparse.Namespace) -> dict[str, Any]:
    return query_table_command_service(
        args,
        open_db=open_db,
        resolve_view=resolve_view,
        registry_for_table=registry_for_table,
        table_columns=table_columns,
    )


def build_save_view_plan(
    connection: sqlite3.Connection,
    table_key: str,
    name: str,
    config: dict[str, Any],
    view_key: str = "",
    tag_name: str = "",
    created_by: str = "user",
    agent_managed: int = 0,
) -> dict[str, Any]:
    return build_save_view_plan_service(
        connection,
        table_key,
        name,
        config,
        view_key,
        tag_name,
        created_by,
        agent_managed,
        active_workspace_id=active_workspace_id,
        registry_for_table=registry_for_table,
        table_columns=table_columns,
        analysis_columns_for_table=analysis_columns_for_table,
    )


def execute_save_view_plan(connection: sqlite3.Connection, proposed: dict[str, Any]) -> dict[str, Any]:
    return execute_save_view_plan_service(
        connection,
        proposed,
        now_iso=now_iso,
        upsert_navigation_module=upsert_navigation_module,
        saved_view_summary=saved_view_summary,
    )


def save_view_command(args: argparse.Namespace) -> dict[str, Any]:
    return save_view_command_service(
        args,
        open_db=open_db,
        build_save_view_plan=build_save_view_plan,
        execute_save_view_plan=execute_save_view_plan,
    )


def copy_view_command(args: argparse.Namespace) -> dict[str, Any]:
    return copy_view_command_service(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        resolve_view=resolve_view,
        saved_view_summary=saved_view_summary,
        now_iso=now_iso,
    )


def delete_view_command(args: argparse.Namespace) -> dict[str, Any]:
    return delete_view_command_service(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        resolve_view=resolve_view,
    )


