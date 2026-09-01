from __future__ import annotations

import argparse
import json
import sqlite3
from typing import Any

from agent_action_draft_store import list_action_drafts
from bi_cli_core import now_iso, quote_identifier, quote_relationship_identifier, unique_key
from bi_cli_io_services import rows_to_dicts
from bi_cli_schema import active_workspace_id, all_available_fields, open_db, registry_for_table, table_columns, upsert_navigation_module
from bi_cli_semantic_metric_commands import metric_filters_from_cli, metric_row_to_payload
from bi_cli_source_commands import resolve_table_registry
from bi_cli_widget_commands import preferred_table_key
from formula_engine import FormulaError, ast_dependencies, ast_to_sql, parse_and_validate_formula
from metric_formula_command_service import (
    build_formula_metric_query as build_formula_metric_query_service,
    build_formula_save_plan as build_formula_save_plan_service,
    calculated_field_row_to_payload as calculated_field_row_to_payload_service,
    calculated_field_usage as calculated_field_usage_service,
    compile_formula_for_table as compile_formula_for_table_service,
    delete_formula_command as delete_formula_command_service,
    execute_formula_save_plan as execute_formula_save_plan_service,
    formula_key_for as formula_key_for_service,
    formula_preview_command as formula_preview_command_service,
    query_metric_command as query_metric_command_service,
    save_formula_command as save_formula_command_service,
)
from relationship_command_service import (
    build_relationship_save_plan as build_relationship_save_plan_service,
    execute_relationship_save as execute_relationship_save_service,
    list_relationships_command as list_relationships_command_service,
    normalize_relation_field_name as normalize_relation_field_name_service,
    parse_relationship_filter as parse_relationship_filter_service,
    query_relationship_command as query_relationship_command_service,
    recommend_relationships_command as recommend_relationships_command_service,
    recommend_relationships_for_connection as recommend_relationships_for_connection_service,
    relation_candidate_fields as relation_candidate_fields_service,
    relationship_preview_command as relationship_preview_command_service,
    relationship_name_score as relationship_name_score_service,
    relationship_rows_for_chart as relationship_rows_for_chart_service,
    relationship_save_command as relationship_save_command_service,
    remove_relationship_command as remove_relationship_command_service,
    resolve_relationship_query_inputs as resolve_relationship_query_inputs_service,
    saved_relationship_signatures as saved_relationship_signatures_service,
    to_number as relationship_to_number_service,
)
from relationship_tools import build_relationship_preview, build_relationship_query, parse_relationship_field_ref
from saved_view_query_service import parse_query_sort
from table_query_tools import build_table_query, normalize_filters, where_sql

def query_metric_command(args: argparse.Namespace) -> dict[str, Any]:
    return query_metric_command_service(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        metric_row_to_payload=metric_row_to_payload,
        build_formula_metric_query=build_formula_metric_query,
        table_columns=table_columns,
        metric_filters_from_cli=metric_filters_from_cli,
        parse_query_sort=parse_query_sort,
        build_table_query=build_table_query,
    )


def normalize_relation_field_name(value: str) -> str:
    return normalize_relation_field_name_service(value)


def relation_candidate_fields(connection: sqlite3.Connection, registry: sqlite3.Row) -> list[dict[str, Any]]:
    return relation_candidate_fields_service(
        connection,
        registry,
        active_workspace_id=active_workspace_id,
        table_columns=table_columns,
    )


def relationship_name_score(left_field: str, right_field: str) -> tuple[int, list[str]]:
    return relationship_name_score_service(left_field, right_field)


def saved_relationship_signatures(connection: sqlite3.Connection) -> set[tuple[str, str, str, str]]:
    return saved_relationship_signatures_service(connection, active_workspace_id=active_workspace_id)


def recommend_relationships_for_connection(connection: sqlite3.Connection, limit: int = 12) -> list[dict[str, Any]]:
    return recommend_relationships_for_connection_service(
        connection,
        limit,
        active_workspace_id=active_workspace_id,
        table_columns=table_columns,
        quote_identifier=quote_identifier,
        build_relationship_preview=build_relationship_preview,
        relation_candidate_fields=relation_candidate_fields,
        relationship_name_score=relationship_name_score,
        saved_relationship_signatures=saved_relationship_signatures,
    )


def recommend_relationships_command(args: argparse.Namespace) -> dict[str, Any]:
    return recommend_relationships_command_service(
        args,
        open_db=open_db,
        recommend_relationships_for_connection=recommend_relationships_for_connection,
    )


def action_drafts_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        result = list_action_drafts(connection, workspace_id=workspace_id, limit=args.limit, include_all=args.all)
    return {"ok": True, **result}


def list_relationships_command(args: argparse.Namespace) -> dict[str, Any]:
    return list_relationships_command_service(args, open_db=open_db, active_workspace_id=active_workspace_id)


def resolve_relationship_query_inputs(args: argparse.Namespace, connection: sqlite3.Connection) -> dict[str, Any]:
    return resolve_relationship_query_inputs_service(
        args,
        connection,
        active_workspace_id=active_workspace_id,
        registry_for_table=registry_for_table,
        table_columns=table_columns,
    )


def parse_relationship_filter(raw_filter: str) -> dict[str, Any]:
    return parse_relationship_filter_service(raw_filter)


def to_number(value: Any) -> float:
    return relationship_to_number_service(value)


def relationship_rows_for_chart(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return relationship_rows_for_chart_service(payload)


def query_relationship_command(args: argparse.Namespace) -> dict[str, Any]:
    return query_relationship_command_service(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        registry_for_table=registry_for_table,
        table_columns=table_columns,
        parse_relationship_field_ref=parse_relationship_field_ref,
        build_relationship_preview=build_relationship_preview,
        build_relationship_query=build_relationship_query,
        quote_relationship_identifier=quote_relationship_identifier,
    )


def remove_relationship_command(args: argparse.Namespace) -> dict[str, Any]:
    return remove_relationship_command_service(args, open_db=open_db, active_workspace_id=active_workspace_id)


def relationship_preview_command(args: argparse.Namespace) -> dict[str, Any]:
    return relationship_preview_command_service(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        registry_for_table=registry_for_table,
        table_columns=table_columns,
        build_relationship_preview=build_relationship_preview,
        quote_identifier=quote_identifier,
    )


def build_relationship_save_plan(
    connection: sqlite3.Connection,
    left_table: str,
    right_table: str,
    left_field: str,
    right_field: str,
    join_type: str = "left",
    limit: int = 20,
    mappings: list[dict[str, str]] | None = None,
    filters: list[dict[str, Any]] | None = None,
    preaggregation: dict[str, Any] | None = None,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    return build_relationship_save_plan_service(
        connection,
        left_table,
        right_table,
        left_field,
        right_field,
        join_type,
        limit,
        mappings=mappings,
        filters=filters,
        preaggregation=preaggregation,
        workspace_id=workspace_id,
        registry_for_table=registry_for_table,
        table_columns=table_columns,
        build_relationship_preview=build_relationship_preview,
        quote_identifier=quote_identifier,
    )


def execute_relationship_save(
    connection: sqlite3.Connection,
    proposed: dict[str, Any],
    *,
    workspace_id: str | None = None,
) -> dict[str, Any]:
    return execute_relationship_save_service(
        connection,
        proposed,
        active_workspace_id=active_workspace_id,
        workspace_id=workspace_id,
    )


def relationship_save_command(args: argparse.Namespace) -> dict[str, Any]:
    return relationship_save_command_service(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        build_relationship_save_plan=build_relationship_save_plan,
        execute_relationship_save=execute_relationship_save,
    )

def formula_preview_command(args: argparse.Namespace) -> dict[str, Any]:
    return formula_preview_command_service(
        args,
        open_db=open_db,
        all_available_fields=all_available_fields,
        parse_and_validate_formula=parse_and_validate_formula,
        ast_dependencies=ast_dependencies,
        ast_to_sql=ast_to_sql,
        quote_identifier=quote_identifier,
        formula_error_type=FormulaError,
    )


def formula_key_for(table_key: str, name: str, mode: str) -> str:
    return formula_key_for_service(table_key, name, mode)


def calculated_field_row_to_payload(row: sqlite3.Row) -> dict[str, Any]:
    return calculated_field_row_to_payload_service(row)


def calculated_field_usage(connection: sqlite3.Connection, table_key: str, field_name: str, field_key: str = "") -> list[dict[str, str]]:
    return calculated_field_usage_service(
        connection,
        table_key,
        field_name,
        field_key,
        active_workspace_id=active_workspace_id,
    )


def compile_formula_for_table(connection: sqlite3.Connection, table_key: str, expression: str, mode: str) -> dict[str, Any]:
    return compile_formula_for_table_service(
        connection,
        table_key,
        expression,
        mode,
        resolve_table_registry=resolve_table_registry,
        table_columns=table_columns,
        parse_and_validate_formula=parse_and_validate_formula,
        ast_dependencies=ast_dependencies,
        ast_to_sql=ast_to_sql,
        quote_identifier=quote_identifier,
    )


def list_formulas_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        params: list[Any] = [workspace_id]
        clauses: list[str] = ["workspace_id = ?"]
        if args.table:
            registry = resolve_table_registry(connection, args.table)
            clauses.append("table_key = ?")
            params.append(registry["table_key"])
        if not args.all:
            clauses.append("enabled = 1")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        row_formulas = [
            calculated_field_row_to_payload(row)
            for row in connection.execute(
                f"""
                SELECT *
                FROM calculated_fields
                {where}
                ORDER BY table_key, name
                """,
                params,
            ).fetchall()
        ]
        metric_rows = connection.execute(
            f"""
            SELECT m.*, COALESCE(t.display_name, m.table_key) AS table_name
            FROM metric_definitions m
            LEFT JOIN table_registry t
              ON t.table_key = m.table_key
             AND t.workspace_id = m.workspace_id
            WHERE {" AND ".join([clause.replace("workspace_id", "m.workspace_id").replace("table_key", "m.table_key") for clause in clauses])}
            ORDER BY m.table_key, m.metric_key
            """,
            params,
        ).fetchall()
        metric_formulas = [
            metric_row_to_payload(row, row["table_name"])
            for row in metric_rows
            if row["metric_type"] == "formula" or row["formula_text"]
        ]
    return {"ok": True, "formulas": row_formulas, "metricFormulas": metric_formulas, "count": len(row_formulas) + len(metric_formulas)}


def save_formula_command(args: argparse.Namespace) -> dict[str, Any]:
    return save_formula_command_service(
        args,
        open_db=open_db,
        build_formula_save_plan=build_formula_save_plan,
        execute_formula_save_plan=execute_formula_save_plan,
    )


def build_formula_save_plan(
    connection: sqlite3.Connection,
    table: str,
    name: str,
    expression: str,
    mode: str = "aggregate",
    dimension: str = "",
    time_field: str = "",
    value_format: str = "auto",
    description: str = "",
    formula_key: str = "",
) -> dict[str, Any]:
    return build_formula_save_plan_service(
        connection,
        table,
        name,
        expression,
        mode,
        dimension,
        time_field,
        value_format,
        description,
        formula_key,
        compile_formula_for_table=compile_formula_for_table,
    )


def execute_formula_save_plan(connection: sqlite3.Connection, proposed: dict[str, Any]) -> dict[str, Any]:
    return execute_formula_save_plan_service(
        connection,
        proposed,
        active_workspace_id=active_workspace_id,
        now_iso=now_iso,
    )


def delete_formula_command(args: argparse.Namespace) -> dict[str, Any]:
    return delete_formula_command_service(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        calculated_field_row_to_payload=calculated_field_row_to_payload,
        metric_row_to_payload=metric_row_to_payload,
        calculated_field_usage=calculated_field_usage,
    )


def build_formula_metric_query(
    connection: sqlite3.Connection,
    analysis_connection: Any,
    row: sqlite3.Row,
    args: argparse.Namespace,
) -> dict[str, Any]:
    return build_formula_metric_query_service(
        connection,
        analysis_connection,
        row,
        args,
        table_columns=table_columns,
        normalize_filters=normalize_filters,
        where_sql=where_sql,
        parse_and_validate_formula=parse_and_validate_formula,
        ast_to_sql=ast_to_sql,
        quote_identifier=quote_identifier,
    )


def build_dashboard_operation_plan(
    connection: sqlite3.Connection,
    op: str,
    dashboard_key: str = "",
    name: str = "",
    table_key: str = "",
    source_dashboard_key: str = "",
) -> dict[str, Any]:
    source = None
    workspace_id = active_workspace_id(connection)
    if dashboard_key:
        source = connection.execute(
            "SELECT * FROM dashboards WHERE dashboard_key = ? AND workspace_id = ?",
            (dashboard_key, workspace_id),
        ).fetchone()
    if op in {"copy", "rename", "delete"} and not source:
        raise ValueError(f"Unknown dashboard: {dashboard_key}")
    if op in {"create", "copy", "rename"} and not name:
        raise ValueError("Dashboard name is required.")
    if table_key:
        resolved_table_key = table_key
    elif source:
        resolved_table_key = source["default_table_key"]
    elif op == "create":
        resolved_table_key = ""
    else:
        resolved_table_key = preferred_table_key(connection, None)
    return {
        "op": op,
        "dashboardKey": dashboard_key,
        "name": name,
        "sourceDashboardKey": source_dashboard_key or dashboard_key,
        "defaultTableKey": resolved_table_key,
        "sourceDashboardName": source["name"] if source else "",
    }


def execute_dashboard_operation_plan(connection: sqlite3.Connection, proposed: dict[str, Any], created_by: str = "user", agent_managed: int = 0) -> dict[str, Any]:
    op = str(proposed.get("op") or "")
    now = now_iso()
    dashboard_key = str(proposed.get("dashboardKey") or "")
    name = str(proposed.get("name") or "")
    table_key = str(proposed.get("defaultTableKey") or "")
    if op in {"create", "copy", "rename"} and not name:
        raise ValueError("Dashboard name is required.")

    navigation_created_by = "agent" if created_by == "agent" else "manual"
    workspace_id = active_workspace_id(connection)
    source = connection.execute(
        "SELECT * FROM dashboards WHERE dashboard_key = ? AND workspace_id = ?",
        (dashboard_key, workspace_id),
    ).fetchone() if dashboard_key else None
    if op in {"copy", "rename", "delete"} and not source:
        raise ValueError(f"Unknown dashboard: {dashboard_key}")

    if op == "create":
        dashboard_key = unique_key("dashboard")
        layout = {"version": 1, "grid": "12-col", "widgets": [], "globalFilters": []}
        connection.execute(
            """
            INSERT INTO dashboards(dashboard_key, name, workspace_id, default_table_key, layout_json, created_by, agent_managed, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (dashboard_key, name, workspace_id, table_key or None, json.dumps(layout, ensure_ascii=False), created_by, agent_managed, now, now),
        )
        upsert_navigation_module(
            connection,
            module_key=f"dashboard:{dashboard_key}",
            name=name,
            module_type="dashboard",
            dashboard_key=dashboard_key,
            created_by=navigation_created_by,
            agent_managed=agent_managed,
        )
        result = {"dashboardKey": dashboard_key}
    elif op == "copy":
        dashboard_key = unique_key("dashboard")
        layout = json.loads(source["layout_json"])
        layout["copiedFrom"] = source["dashboard_key"]
        connection.execute(
            """
            INSERT INTO dashboards(dashboard_key, name, workspace_id, default_table_key, layout_json, created_by, agent_managed, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (dashboard_key, name, workspace_id, source["default_table_key"], json.dumps(layout, ensure_ascii=False), created_by, agent_managed, now, now),
        )
        widgets = rows_to_dicts(
            connection.execute(
                "SELECT * FROM dashboard_widgets WHERE dashboard_key = ? AND workspace_id = ? ORDER BY sort_order",
                (source["dashboard_key"], workspace_id),
            )
        )
        for widget in widgets:
            connection.execute(
                """
                INSERT INTO dashboard_widgets(widget_key, workspace_id, dashboard_key, widget_type, title, table_key, config_json, sort_order)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (unique_key("widget"), workspace_id, dashboard_key, widget["widget_type"], widget["title"], widget["table_key"], widget["config_json"], widget["sort_order"]),
            )
        upsert_navigation_module(
            connection,
            module_key=f"dashboard:{dashboard_key}",
            name=name,
            module_type="dashboard",
            dashboard_key=dashboard_key,
            created_by=navigation_created_by,
            agent_managed=agent_managed,
        )
        result = {"dashboardKey": dashboard_key}
    elif op == "rename":
        connection.execute(
            "UPDATE dashboards SET name = ?, updated_at = ? WHERE dashboard_key = ? AND workspace_id = ?",
            (name, now, dashboard_key, workspace_id),
        )
        connection.execute(
            """
            UPDATE navigation_modules
            SET name = ?, updated_at = ?
            WHERE module_type = 'dashboard' AND dashboard_key = ? AND workspace_id = ?
            """,
            (name, now, dashboard_key, workspace_id),
        )
        result = {"dashboardKey": dashboard_key}
    elif op == "delete":
        dashboard_count = connection.execute(
            "SELECT COUNT(*) FROM dashboards WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()[0]
        if dashboard_count <= 1:
            raise ValueError("Cannot delete the only dashboard.")
        connection.execute(
            "DELETE FROM dashboard_widgets WHERE dashboard_key = ? AND workspace_id = ?",
            (dashboard_key, workspace_id),
        )
        connection.execute(
            "DELETE FROM dashboards WHERE dashboard_key = ? AND workspace_id = ?",
            (dashboard_key, workspace_id),
        )
        connection.execute(
            "DELETE FROM navigation_modules WHERE module_type = 'dashboard' AND dashboard_key = ? AND workspace_id = ?",
            (dashboard_key, workspace_id),
        )
        result = {"dashboardKey": dashboard_key}
    else:
        raise ValueError(f"Unsupported dashboard operation: {op}")
    return result


def dashboard_operation_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        proposed = build_dashboard_operation_plan(connection, args.op, args.dashboard or "", args.name or "", args.table or "", args.source or "")
        if not args.yes:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "proposed": proposed}
        result = execute_dashboard_operation_plan(connection, proposed)
        connection.commit()
    return {"ok": True, "confirmed": True, "operation": args.op, **result}


