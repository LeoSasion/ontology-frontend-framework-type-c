from __future__ import annotations

import argparse
import json
import sqlite3
from typing import Any

from bi_cli_core import DUCKDB_PATH, now_iso, quote_identifier, slug, source_label, unique_key
from bi_cli_io_services import load_connectors, parse_json_object, rows_to_dicts
from bi_cli_query_view_commands import saved_view_summary
from bi_cli_schema import (
    active_workspace_id,
    ensure_navigation_modules,
    list_navigation_modules,
    list_theme_palettes,
    load_user_preferences,
    navigation_module_payload,
    open_db,
    table_columns,
)
from bi_cli_source_commands import resolve_table_registry
from connector_adapter_service import adapter_contracts
from dashboard_widget_contracts import B_DASHBOARD_FILTER_OPERATORS
from domain_pack_service import domain_pack_runtime_context
from evidence_run_store import list_source_intelligence_runs
from query_runtime import DuckDBUnavailable, SAFE_AGGREGATIONS, duckdb_status, sync_table_to_duckdb
from relationship_command_service import (
    recommend_relationships_for_connection as recommend_relationships_for_connection_service,
    relation_candidate_fields as relation_candidate_fields_service,
    relationship_name_score as relationship_name_score_service,
    sample_field_values as sample_field_values_service,
    saved_relationship_signatures as saved_relationship_signatures_service,
)
from relationship_tools import build_relationship_preview

B_INDEX_REASON_WEIGHTS = {
    "identity-key": 40,
    "event-time": 35,
    "relationship-key": 35,
    "import-unique-key": 32,
    "dashboard-filter": 28,
    "widget-dimension": 24,
    "widget-filter": 22,
    "semantic-filterable": 20,
    "semantic-groupable": 18,
    "measure": 8,
}


def recommend_relationships_for_connection(connection: sqlite3.Connection, limit: int = 12) -> list[dict[str, Any]]:
    return recommend_relationships_for_connection_service(
        connection,
        limit,
        active_workspace_id=active_workspace_id,
        table_columns=table_columns,
        quote_identifier=quote_identifier,
        build_relationship_preview=build_relationship_preview,
        relation_candidate_fields=lambda conn, registry: relation_candidate_fields_service(conn, registry, active_workspace_id=active_workspace_id, table_columns=table_columns),
        relationship_name_score=relationship_name_score_service,
        sample_field_values=lambda conn, physical_table, field, limit=300: sample_field_values_service(conn, physical_table, field, limit, quote_identifier=quote_identifier),
        saved_relationship_signatures=lambda conn: saved_relationship_signatures_service(conn, active_workspace_id=active_workspace_id),
    )

def dashboards_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        if args.dashboard:
            dashboards = rows_to_dicts(
                connection.execute(
                    "SELECT * FROM dashboards WHERE dashboard_key = ? AND workspace_id = ? ORDER BY created_at",
                    (args.dashboard, workspace_id),
                )
            )
        else:
            dashboards = rows_to_dicts(connection.execute("SELECT * FROM dashboards WHERE workspace_id = ? ORDER BY created_at", (workspace_id,)))
        widgets = rows_to_dicts(
            connection.execute(
                "SELECT * FROM dashboard_widgets WHERE workspace_id = ? ORDER BY dashboard_key, sort_order",
                (workspace_id,),
            )
        )
    return {
        "ok": True,
        "dashboards": [
            {
                **dashboard,
                "layout": json.loads(dashboard.pop("layout_json")),
                "widgets": [
                    {**widget, "config": json.loads(widget["config_json"])}
                    for widget in widgets
                    if widget["dashboard_key"] == dashboard["dashboard_key"]
                ],
            }
            for dashboard in dashboards
        ],
    }


def dashboard_layout(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    raw = row["layout_json"] if isinstance(row, sqlite3.Row) else row.get("layout_json")
    try:
        layout = json.loads(raw or "{}")
    except json.JSONDecodeError:
        layout = {"version": 1}
    if not isinstance(layout, dict):
        layout = {"version": 1}
    layout.setdefault("version", 1)
    filters = layout.get("globalFilters")
    if not isinstance(filters, list):
        layout["globalFilters"] = []
    return layout


def normalize_filter_rule(rule: dict[str, Any], index: int = 0) -> dict[str, Any]:
    operator = str(rule.get("operator") or "equals")
    if operator not in B_DASHBOARD_FILTER_OPERATORS:
        operator = "equals"
    return {
        "id": str(rule.get("id") or f"filter_{index + 1}"),
        "field": str(rule.get("field") or "").strip(),
        "operator": operator,
        "value": str(rule.get("value") or ""),
        "enabled": rule.get("enabled") is not False,
        "scope": str(rule.get("scope") or "dashboard"),
        "createdAt": str(rule.get("createdAt") or now_iso()),
        "updatedAt": str(rule.get("updatedAt") or rule.get("createdAt") or now_iso()),
    }


def dashboard_filter_fields(connection: sqlite3.Connection, dashboard: sqlite3.Row) -> list[dict[str, Any]]:
    workspace_id = active_workspace_id(connection)
    return rows_to_dicts(
        connection.execute(
            """
            SELECT field_name, role, usage, confidence
            FROM field_semantics
            WHERE table_key = ? AND workspace_id = ?
            ORDER BY
              CASE WHEN usage = 'filterable' THEN 0 WHEN usage = 'groupable' THEN 1 ELSE 2 END,
              field_name
            """,
            (dashboard["default_table_key"], workspace_id),
        )
    )


def dashboard_filters_snapshot(connection: sqlite3.Connection, dashboard_key: str) -> tuple[sqlite3.Row, dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    workspace_id = active_workspace_id(connection)
    dashboard = connection.execute(
        "SELECT * FROM dashboards WHERE dashboard_key = ? AND workspace_id = ?",
        (dashboard_key, workspace_id),
    ).fetchone()
    if not dashboard:
        raise ValueError(f"Unknown dashboard: {dashboard_key}")
    layout = dashboard_layout(dashboard)
    filters = [normalize_filter_rule(item, index) for index, item in enumerate(layout.get("globalFilters", [])) if isinstance(item, dict)]
    layout["globalFilters"] = filters
    fields = dashboard_filter_fields(connection, dashboard)
    return dashboard, layout, filters, fields


def list_filters_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        dashboard, layout, filters, fields = dashboard_filters_snapshot(connection, args.dashboard)
    return {
        "ok": True,
        "dashboard": {
            "dashboard_key": dashboard["dashboard_key"],
            "name": dashboard["name"],
            "default_table_key": dashboard["default_table_key"],
        },
        "filters": filters,
        "availableFields": fields,
        "operators": B_DASHBOARD_FILTER_OPERATORS,
        "layoutVersion": layout.get("version", 1),
    }


def filter_value_required(operator: str) -> bool:
    return operator not in {"empty", "notEmpty"}


def save_dashboard_filters(connection: sqlite3.Connection, dashboard_key: str, layout: dict[str, Any], filters: list[dict[str, Any]]) -> None:
    workspace_id = active_workspace_id(connection)
    layout["globalFilters"] = filters
    connection.execute(
        "UPDATE dashboards SET layout_json = ?, updated_at = ? WHERE dashboard_key = ? AND workspace_id = ?",
        (json.dumps(layout, ensure_ascii=False), now_iso(), dashboard_key, workspace_id),
    )


def build_dashboard_filter_add_plan(
    connection: sqlite3.Connection,
    dashboard_key: str,
    field: str,
    operator: str = "equals",
    value: str = "",
    filter_key: str = "",
    disabled: bool = False,
) -> dict[str, Any]:
    dashboard, _layout, filters, fields = dashboard_filters_snapshot(connection, dashboard_key)
    available = {item["field_name"] for item in fields}
    if field not in available:
        raise ValueError(f"Unknown dashboard field: {field}")
    if operator not in B_DASHBOARD_FILTER_OPERATORS:
        raise ValueError(f"Unsupported dashboard filter operator: {operator}")
    if filter_value_required(operator) and not str(value or "").strip():
        raise ValueError(f"Filter value is required for operator: {operator}")
    now = now_iso()
    proposed = normalize_filter_rule(
        {
            "id": filter_key or unique_key("filter"),
            "field": field,
            "operator": operator,
            "value": value or "",
            "enabled": not disabled,
            "scope": "dashboard",
            "createdAt": now,
            "updatedAt": now,
        }
    )
    return {
        "dashboard": {
            "dashboard_key": dashboard["dashboard_key"],
            "name": dashboard["name"],
            "default_table_key": dashboard["default_table_key"],
        },
        "current": None,
        "proposed": proposed,
        "filtersAfter": [*filters, proposed],
        "availableFields": fields,
    }


def execute_dashboard_filter_add_plan(connection: sqlite3.Connection, dashboard_key: str, filters_after: list[dict[str, Any]]) -> None:
    _dashboard, layout, _filters, _fields = dashboard_filters_snapshot(connection, dashboard_key)
    save_dashboard_filters(connection, dashboard_key, layout, filters_after)


def add_or_set_filter_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        if args.command == "add-filter":
            plan = build_dashboard_filter_add_plan(connection, args.dashboard, args.field, args.operator, args.value or "", "", args.disabled)
            if not args.yes:
                return {"ok": True, "dryRun": True, "requiresConfirmation": True, **plan}
            execute_dashboard_filter_add_plan(connection, args.dashboard, plan["filtersAfter"])
            connection.commit()
            return {"ok": True, "confirmed": True, "operation": args.command, "filter": plan["proposed"], "filters": plan["filtersAfter"]}
        dashboard, layout, filters, fields = dashboard_filters_snapshot(connection, args.dashboard)
        available = {field["field_name"] for field in fields}
        if args.field not in available:
            raise ValueError(f"Unknown dashboard field: {args.field}")
        if filter_value_required(args.operator) and not str(args.value or "").strip():
            raise ValueError(f"Filter value is required for operator: {args.operator}")
        now = now_iso()
        proposed = normalize_filter_rule(
            {
                "id": getattr(args, "filter", None) or unique_key("filter"),
                "field": args.field,
                "operator": args.operator,
                "value": args.value or "",
                "enabled": not args.disabled,
                "scope": "dashboard",
                "createdAt": now,
                "updatedAt": now,
            }
        )
        current = None
        next_filters: list[dict[str, Any]] = []
        replaced = False
        if args.command == "set-filter":
            if not getattr(args, "filter", None):
                raise ValueError("--filter is required for set-filter")
            for item in filters:
                if item["id"] == args.filter:
                    current = item
                    proposed["createdAt"] = item.get("createdAt", now)
                    next_filters.append(proposed)
                    replaced = True
                else:
                    next_filters.append(item)
            if not replaced:
                raise ValueError(f"Unknown filter: {args.filter}")
        else:
            next_filters = [*filters, proposed]
        if not args.yes:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "dashboard": {"dashboard_key": dashboard["dashboard_key"], "name": dashboard["name"]},
                "current": current,
                "proposed": proposed,
                "filtersAfter": next_filters,
            }
        save_dashboard_filters(connection, args.dashboard, layout, next_filters)
        connection.commit()
    return {"ok": True, "confirmed": True, "operation": args.command, "filter": proposed, "filters": next_filters}


def remove_filter_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        dashboard, layout, filters, _fields = dashboard_filters_snapshot(connection, args.dashboard)
        removed = next((item for item in filters if item["id"] == args.filter), None)
        if not removed:
            raise ValueError(f"Unknown filter: {args.filter}")
        next_filters = [item for item in filters if item["id"] != args.filter]
        if not args.yes:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "dashboard": {"dashboard_key": dashboard["dashboard_key"], "name": dashboard["name"]},
                "removed": removed,
                "filtersAfter": next_filters,
            }
        save_dashboard_filters(connection, args.dashboard, layout, next_filters)
        connection.commit()
    return {"ok": True, "confirmed": True, "operation": "remove-filter", "removed": removed, "filters": next_filters}


def clear_filters_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        dashboard, layout, filters, _fields = dashboard_filters_snapshot(connection, args.dashboard)
        if not args.yes:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "dashboard": {"dashboard_key": dashboard["dashboard_key"], "name": dashboard["name"]},
                "removedCount": len(filters),
                "filtersAfter": [],
            }
        save_dashboard_filters(connection, args.dashboard, layout, [])
        connection.commit()
    return {"ok": True, "confirmed": True, "operation": "clear-filters", "removedCount": len(filters), "filters": []}


def dashboard_filter_status(connection: sqlite3.Connection, dashboard_key: str) -> dict[str, Any]:
    dashboard, _layout, filters, fields = dashboard_filters_snapshot(connection, dashboard_key)
    available = {field["field_name"] for field in fields}
    enriched: list[dict[str, Any]] = []
    applicable: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    disabled: list[dict[str, Any]] = []
    for item in filters:
        field = str(item.get("field") or "")
        status = "disabled" if item.get("enabled") is False else "applicable"
        if field not in available:
            status = "stale"
        enriched_item = {**item, "status": status}
        enriched.append(enriched_item)
        if status == "applicable":
            applicable.append(enriched_item)
        elif status == "stale":
            stale.append(enriched_item)
        else:
            disabled.append(enriched_item)
    return {
        "ok": True,
        "dashboard": {
            "dashboard_key": dashboard["dashboard_key"],
            "name": dashboard["name"],
            "default_table_key": dashboard["default_table_key"],
        },
        "availableFields": fields,
        "filters": enriched,
        "applicableFilters": applicable,
        "staleFilters": stale,
        "disabledFilters": disabled,
    }


def remove_stale_filters_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        dashboard, layout, filters, _fields = dashboard_filters_snapshot(connection, args.dashboard)
        status = dashboard_filter_status(connection, args.dashboard)
        stale_ids = {item["id"] for item in status["staleFilters"]}
        next_filters = [item for item in filters if item["id"] not in stale_ids]
        if not args.yes:
            return {
                **status,
                "dryRun": True,
                "requiresConfirmation": True,
                "removedCount": len(stale_ids),
                "filtersAfter": next_filters,
            }
        save_dashboard_filters(connection, dashboard["dashboard_key"], layout, next_filters)
        connection.commit()
    return {
        "ok": True,
        "confirmed": True,
        "operation": "remove-stale-filters",
        "dashboard": status["dashboard"],
        "removedFilters": status["staleFilters"],
        "removedCount": len(stale_ids),
        "filters": next_filters,
    }


def add_index_reason(reasons: dict[str, set[str]], field: str, reason: str) -> None:
    if not field:
        return
    reasons.setdefault(field, set()).add(reason)


def collect_index_reasons(connection: sqlite3.Connection, table_key: str) -> dict[str, set[str]]:
    workspace_id = active_workspace_id(connection)
    reasons: dict[str, set[str]] = {}
    for row in connection.execute(
        """
        SELECT field_name, role, usage
        FROM field_semantics
        WHERE table_key = ? AND workspace_id = ?
        """,
        (table_key, workspace_id),
    ).fetchall():
        role = str(row["role"] or "")
        usage = str(row["usage"] or "")
        if role in {"identity_key", "identifier"}:
            add_index_reason(reasons, row["field_name"], "identity-key")
        if role in {"event_time", "time"}:
            add_index_reason(reasons, row["field_name"], "event-time")
        if role == "measure":
            add_index_reason(reasons, row["field_name"], "measure")
        if usage == "filterable":
            add_index_reason(reasons, row["field_name"], "semantic-filterable")
        if usage == "groupable":
            add_index_reason(reasons, row["field_name"], "semantic-groupable")
        if usage == "joinable":
            add_index_reason(reasons, row["field_name"], "relationship-key")

    for row in connection.execute(
        """
        SELECT left_table_key, right_table_key, left_field, right_field
        FROM relationships
        WHERE workspace_id = ? AND (left_table_key = ? OR right_table_key = ?)
        """,
        (workspace_id, table_key, table_key),
    ).fetchall():
        if row["left_table_key"] == table_key:
            add_index_reason(reasons, row["left_field"], "relationship-key")
        if row["right_table_key"] == table_key:
            add_index_reason(reasons, row["right_field"], "relationship-key")

    policy = connection.execute(
        "SELECT unique_fields_json FROM import_policies WHERE table_key = ? AND workspace_id = ?",
        (table_key, workspace_id),
    ).fetchone()
    if policy:
        try:
            unique_fields = json.loads(policy["unique_fields_json"] or "[]")
        except json.JSONDecodeError:
            unique_fields = []
        for field in unique_fields if isinstance(unique_fields, list) else []:
            add_index_reason(reasons, str(field), "import-unique-key")

    for dashboard in connection.execute(
        "SELECT layout_json FROM dashboards WHERE default_table_key = ? AND workspace_id = ?",
        (table_key, workspace_id),
    ).fetchall():
        layout = dashboard_layout(dashboard)
        for rule in layout.get("globalFilters", []):
            if isinstance(rule, dict):
                add_index_reason(reasons, str(rule.get("field") or ""), "dashboard-filter")

    for widget in connection.execute(
        "SELECT config_json FROM dashboard_widgets WHERE table_key = ? AND workspace_id = ?",
        (table_key, workspace_id),
    ).fetchall():
        config = parse_json_object(widget["config_json"], {})
        if not isinstance(config, dict):
            continue
        for key in ("dimension", "group", "measure"):
            add_index_reason(reasons, str(config.get(key) or ""), "widget-dimension" if key != "measure" else "measure")
        for rule in config.get("filters") if isinstance(config.get("filters"), list) else []:
            if isinstance(rule, dict):
                add_index_reason(reasons, str(rule.get("field") or ""), "widget-filter")
    return reasons


def recommend_indexes_for_table(connection: sqlite3.Connection, registry: sqlite3.Row, limit: int) -> list[dict[str, Any]]:
    physical_table = registry["physical_table"]
    columns = set(table_columns(connection, physical_table))
    reasons_by_field = collect_index_reasons(connection, registry["table_key"])
    recommendations: list[dict[str, Any]] = []
    for field, reasons in reasons_by_field.items():
        if field not in columns:
            continue
        score = sum(B_INDEX_REASON_WEIGHTS.get(reason, 0) for reason in reasons)
        if score <= 0:
            continue
        index_key = slug(f"idx_{physical_table}_{field}")[:62]
        recommendations.append(
            {
                "tableKey": registry["table_key"],
                "tableName": registry["display_name"],
                "physicalTable": physical_table,
                "field": field,
                "indexKey": index_key,
                "score": score,
                "reasons": sorted(reasons),
                "rowCount": registry["row_count"],
                "engine": "duckdb",
                "sideEffectBoundary": "dry-run-until---yes",
            }
        )
    recommendations.sort(key=lambda item: (-item["score"], str(item["field"])))
    return recommendations[:limit]


def recommend_indexes_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        if args.table:
            registries = [resolve_table_registry(connection, args.table)]
        else:
            workspace_id = active_workspace_id(connection)
            registries = connection.execute(
                "SELECT * FROM table_registry WHERE workspace_id = ? ORDER BY row_count DESC, table_key",
                (workspace_id,),
            ).fetchall()
        recommendations: list[dict[str, Any]] = []
        per_table_limit = max(1, int(args.limit or 12))
        for registry in registries:
            recommendations.extend(recommend_indexes_for_table(connection, registry, per_table_limit))
    recommendations.sort(key=lambda item: (-item["score"], -int(item.get("rowCount") or 0), str(item["tableKey"]), str(item["field"])))
    return {
        "ok": True,
        "engine": "duckdb",
        "dryRun": True,
        "recommendations": recommendations[: max(1, int(args.limit or 12))],
        "source": "recommend-indexes adapted to the workspace DuckDB runtime",
    }


def build_index_plan(connection: sqlite3.Connection, table: str, field: str, index_key: str = "") -> tuple[dict[str, Any], list[str]]:
    registry = resolve_table_registry(connection, table)
    physical_table = registry["physical_table"]
    columns = table_columns(connection, physical_table)
    if field not in columns:
        raise ValueError(f"Unknown field for index: {field}")
    recommendations = recommend_indexes_for_table(connection, registry, 100)
    recommendation = next((item for item in recommendations if item["field"] == field), None)
    resolved_index_key = slug(index_key or (recommendation or {}).get("indexKey") or f"idx_{physical_table}_{field}")[:62]
    proposed = {
        "tableKey": registry["table_key"],
        "tableName": registry["display_name"],
        "physicalTable": physical_table,
        "field": field,
        "indexKey": resolved_index_key,
        "engine": "duckdb",
        "compiledSql": f"CREATE INDEX IF NOT EXISTS {quote_identifier(resolved_index_key)} ON {quote_identifier(physical_table)} ({quote_identifier(field)})",
        "recommendation": recommendation,
    }
    return proposed, columns


def execute_index_plan(connection: sqlite3.Connection, proposed: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    try:
        import duckdb  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise DuckDBUnavailable(str(exc)) from exc
    DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(DUCKDB_PATH)) as duck_connection:
        synced_rows = sync_table_to_duckdb(connection, duck_connection, str(proposed["physicalTable"]), columns)
        duck_connection.execute(str(proposed["compiledSql"]))
    return {"ok": True, "confirmed": True, "createdIndex": proposed, "syncedRows": synced_rows}


def create_index_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        proposed, columns = build_index_plan(connection, args.table, args.field, args.index)
        if not args.yes:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "proposed": proposed}
        return execute_index_plan(connection, proposed, columns)


def workbench_command(args: argparse.Namespace) -> dict[str, Any]:
    runtime = duckdb_status(DUCKDB_PATH)
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        navigation = list_navigation_modules(connection, include_disabled=False)
        tables = rows_to_dicts(
            connection.execute(
                """
                SELECT table_key, workspace_id, display_name, source_file, row_count, column_count, created_at
                FROM table_registry
                WHERE workspace_id = ?
                ORDER BY display_name
                """,
                (workspace_id,),
            )
        )
        fields = rows_to_dicts(
            connection.execute(
                """
                SELECT workspace_id, table_key, field_name, role, usage, confidence, tags_json, usage_json, source, note, updated_at
                FROM field_semantics
                WHERE workspace_id = ?
                ORDER BY table_key, field_name
                """,
                (workspace_id,),
            )
        )
        metrics = rows_to_dicts(
            connection.execute(
                """
                SELECT metric_key, workspace_id, label, table_key, measure, aggregation, dimension, time_field, value_format,
                       filters_json, description, source, enabled, formula_text, formula_ast_json,
                       dependencies_json, metric_type, created_at, updated_at
                FROM metric_definitions
                WHERE workspace_id = ?
                ORDER BY table_key, metric_key
                """,
                (workspace_id,),
            )
        )
        formulas = rows_to_dicts(
            connection.execute(
                """
                SELECT field_key, workspace_id, table_key, name, mode, formula_text, formula_ast_json, dependencies_json,
                       value_format, description, source, enabled, created_at, updated_at
                FROM calculated_fields
                WHERE workspace_id = ?
                ORDER BY table_key, name
                """,
                (workspace_id,),
            )
        )
        relationships = rows_to_dicts(
            connection.execute(
                """
                SELECT relation_key, workspace_id, name, left_table_key, right_table_key, left_field, right_field, join_type, confidence, created_at
                FROM relationships
                WHERE workspace_id = ?
                ORDER BY relation_key
                """,
                (workspace_id,),
            )
        )
        relationship_recommendations = recommend_relationships_for_connection(connection, min(max(args.limit, 6), 12))
        import_jobs = rows_to_dicts(
            connection.execute(
                """
                SELECT job_key, workspace_id, source_file, table_key, mode, status, row_count, result_json, created_at
                FROM import_jobs
                WHERE workspace_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (workspace_id, args.limit),
            )
        )
        import_policies = rows_to_dicts(
            connection.execute(
                """
                SELECT table_key, workspace_id, unique_fields_json, conflict_rule, updated_at
                FROM import_policies
                WHERE workspace_id = ?
                ORDER BY table_key
                """,
                (workspace_id,),
            )
        )
        connectors = load_connectors(connection)
        preferences = load_user_preferences(connection)
        theme_palettes = list_theme_palettes(connection)
        saved_view_rows = connection.execute(
            """
            SELECT *
            FROM saved_views
            WHERE workspace_id = ?
            ORDER BY table_key, sort_order, created_at
            LIMIT ?
            """,
            (workspace_id, max(args.limit, 24)),
        ).fetchall()
        source_intelligence_runs = list_source_intelligence_runs(connection, workspace_id=workspace_id, limit=args.limit)
        domain_packs = domain_pack_runtime_context(connection, workspace_id)
    for table in tables:
        table["source_file"] = source_label(table["source_file"])
    for job in import_jobs:
        job["source_file"] = source_label(job["source_file"])
        job["result"] = json.loads(job.pop("result_json"))
    for policy in import_policies:
        policy["uniqueFields"] = json.loads(policy.pop("unique_fields_json"))
    saved_views = []
    with open_db() as view_connection:
        for row in saved_view_rows:
            saved_views.append(saved_view_summary(view_connection, row))
    for formula in formulas:
        formula["formulaAst"] = json.loads(formula.pop("formula_ast_json") or "{}")
        formula["dependencies"] = json.loads(formula.pop("dependencies_json") or "[]")
        formula["enabled"] = bool(formula["enabled"])
    return {
        "ok": True,
        "navigation": navigation,
        "tables": tables,
        "fields": fields,
        "metrics": metrics,
        "formulas": formulas,
        "relationships": relationships,
        "relationshipRecommendations": relationship_recommendations,
        "importJobs": import_jobs,
        "importPolicies": import_policies,
        "connectors": connectors,
        "connectorAdapters": adapter_contracts(),
        "preferences": preferences,
        "themePalettes": theme_palettes,
        "savedViews": saved_views,
        "sourceIntelligenceRuns": source_intelligence_runs,
        "domainPacks": domain_packs,
        "fieldRoles": ["identity_key", "event_time", "dimension", "measure", "status"],
        "fieldUsages": ["joinable", "filterable", "groupable", "aggregatable"],
        "safeAggregations": sorted(SAFE_AGGREGATIONS),
        "queryRuntime": runtime,
        "formulaDsl": {
            "allowedFunctions": sorted({"SAFE_DIVIDE", "SUM", "AVG", "MIN", "MAX", "COUNT", "COUNT_DISTINCT", "ABS", "ROUND", "COALESCE", "CONCAT", "IF"}),
            "fieldReference": "[field_name]",
            "acceptsSql": False,
        },
    }


def list_navigation_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        navigation = list_navigation_modules(connection, include_disabled=args.all)
    return {"ok": True, "navigation": navigation, "count": len(navigation)}


def navigation_operation_command(args: argparse.Namespace) -> dict[str, Any]:
    op = args.op
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        ensure_navigation_modules(connection)
        row = connection.execute(
            "SELECT * FROM navigation_modules WHERE module_key = ? AND workspace_id = ?",
            (args.module, workspace_id),
        ).fetchone()
        if not row:
            raise ValueError(f"Unknown navigation module: {args.module}")
        current = navigation_module_payload(row)
        proposed = dict(current)
        if op == "rename":
            name = str(args.name or "").strip()
            if not name:
                raise ValueError("Navigation module name is required.")
            proposed["name"] = name
        elif op == "move":
            proposed["sort"] = int(args.sort)
        elif op == "hide":
            proposed["enabled"] = False
        elif op == "show":
            proposed["enabled"] = True
        else:
            raise ValueError(f"Unsupported navigation operation: {op}")
        if not args.yes:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "operation": op, "currentModule": current, "proposedModule": proposed}
        now = now_iso()
        if op == "rename":
            connection.execute(
                "UPDATE navigation_modules SET name = ?, updated_at = ? WHERE module_key = ? AND workspace_id = ?",
                (proposed["name"], now, args.module, workspace_id),
            )
            if current["type"] == "table" and current["tableKey"]:
                connection.execute(
                    "UPDATE table_registry SET display_name = ? WHERE table_key = ? AND workspace_id = ?",
                    (proposed["name"], current["tableKey"], workspace_id),
                )
                connection.execute(
                    "UPDATE source_runs SET name = ? WHERE table_key = ? AND workspace_id = ?",
                    (proposed["name"], current["tableKey"], workspace_id),
                )
            if current["type"] == "dashboard" and current["dashboardKey"]:
                connection.execute(
                    "UPDATE dashboards SET name = ?, updated_at = ? WHERE dashboard_key = ? AND workspace_id = ?",
                    (proposed["name"], now, current["dashboardKey"], workspace_id),
                )
        elif op == "move":
            connection.execute(
                "UPDATE navigation_modules SET sort_order = ?, updated_at = ? WHERE module_key = ? AND workspace_id = ?",
                (proposed["sort"], now, args.module, workspace_id),
            )
        elif op in {"hide", "show"}:
            connection.execute(
                "UPDATE navigation_modules SET enabled = ?, updated_at = ? WHERE module_key = ? AND workspace_id = ?",
                (1 if proposed["enabled"] else 0, now, args.module, workspace_id),
            )
        connection.commit()
        saved = connection.execute(
            "SELECT * FROM navigation_modules WHERE module_key = ? AND workspace_id = ?",
            (args.module, workspace_id),
        ).fetchone()
    return {"ok": True, "confirmed": True, "operation": op, "navigationModule": navigation_module_payload(saved)}


