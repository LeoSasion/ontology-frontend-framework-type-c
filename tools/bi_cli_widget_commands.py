from __future__ import annotations

import argparse
import json
import sqlite3
from typing import Any

from bi_cli_capabilities import BI_CLI_CAPABILITY_MAP
from bi_cli_core import DB_PATH, now_iso, quote_identifier, slug, unique_key
from bi_cli_dashboard_commands import dashboard_layout, filter_value_required, normalize_filter_rule
from bi_cli_evidence_bundles import write_evidence_bundle
from bi_cli_io_services import parse_json_object, rows_to_dicts
from bi_cli_query_view_commands import resolve_view, saved_view_summary
from bi_cli_schema import active_workspace_id, ensure_navigation_modules, open_db, registry_for_table, table_columns
from business_dashboard_service import (
    build_agent_dashboard_create_draft as build_agent_dashboard_create_draft_service,
    build_business_analysis_templates as build_business_analysis_templates_service,
    build_business_dashboard_payload as build_business_dashboard_payload_service,
    run_business_dashboard_command as run_business_dashboard_command_service,
    source_profile_table_inputs,
    table_template_fields as table_template_fields_service,
    template_widget_layout as template_widget_layout_service,
    write_business_dashboard as write_business_dashboard_service,
)
from dashboard_module_orchestration import dashboard_module_widget_from_payload
from dashboard_save_transactions import dashboard_snapshot, save_dashboard_with_widgets
from dashboard_widget_command_service import (
    add_dashboard_relationship_widget as add_dashboard_relationship_widget_service,
    add_dashboard_widget as add_dashboard_widget_service,
    add_recommended_dashboard_widgets as add_recommended_dashboard_widgets_service,
    copy_dashboard_widget as copy_dashboard_widget_service,
    remove_dashboard_widget as remove_dashboard_widget_service,
    set_dashboard_widget as set_dashboard_widget_service,
)
from dashboard_widget_contracts import (
    B_BAR_ORIENTATIONS,
    B_COLOR_PALETTES,
    B_DASHBOARD_FILTER_OPERATORS,
    B_PIE_SHAPES,
    B_RANKING_MODES,
    B_RELATIONSHIP_WIDGET_TYPES,
    B_SLICER_DISPLAYS,
    B_SORT_BY,
    B_VALUE_FORMATS,
    B_WIDGET_TYPES,
    build_dashboard_widget_catalog_payload,
    widget_style_options_from_args,
)
from dashboard_widget_operations import insert_dashboard_widget, next_dashboard_widget_sort_order, resolve_dashboard_widget_key
from dashboard_widget_proposal_service import (
    build_dashboard_relationship_widget_proposal as build_dashboard_relationship_widget_proposal_service,
    build_dashboard_widget_proposal as build_dashboard_widget_proposal_service,
)
from erp_dashboard_unit_library import build_erp_dashboard_unit_templates, build_erp_unit_library_catalog_payload
from domain_pack_service import is_domain_pack_enabled
from evidence_run_store import latest_source_intelligence_summary
from query_runtime import SAFE_AGGREGATIONS
from relationship_command_service import (
    recommend_relationships_for_connection as recommend_relationships_for_connection_service,
    relation_candidate_fields as relation_candidate_fields_service,
    relationship_name_score as relationship_name_score_service,
    sample_field_values as sample_field_values_service,
    saved_relationship_signatures as saved_relationship_signatures_service,
)
from relationship_tools import build_relationship_preview
from saved_view_query_service import parse_query_filter


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

def dashboard_widget_catalog_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        latest_run = latest_source_intelligence_summary(connection, workspace_id=workspace_id)
        dashboard_count = connection.execute("SELECT COUNT(*) FROM dashboards WHERE workspace_id = ?", (workspace_id,)).fetchone()[0]
        dashboard_keys = [row["dashboard_key"] for row in connection.execute("SELECT dashboard_key FROM dashboards WHERE workspace_id = ?", (workspace_id,)).fetchall()]
        if dashboard_keys:
            placeholders = ", ".join("?" for _ in dashboard_keys)
            widget_count = connection.execute(
                f"SELECT COUNT(*) FROM dashboard_widgets WHERE workspace_id = ? AND dashboard_key IN ({placeholders})",
                [workspace_id, *dashboard_keys],
            ).fetchone()[0]
        else:
            widget_count = 0
        relationship_count = connection.execute("SELECT COUNT(*) FROM relationships WHERE workspace_id = ?", (workspace_id,)).fetchone()[0]
        metric_count = connection.execute("SELECT COUNT(*) FROM metric_definitions WHERE workspace_id = ?", (workspace_id,)).fetchone()[0]
        erp_units_enabled = is_domain_pack_enabled(connection, workspace_id, "erp-units", "dashboardUnits")
    payload = build_dashboard_widget_catalog_payload(
        metadata_store=DB_PATH,
        latest_source_intelligence_run=latest_run,
        workspace_counts={
            "dashboards": dashboard_count,
            "widgets": widget_count,
            "relationships": relationship_count,
            "metrics": metric_count,
        },
    )
    if erp_units_enabled:
        payload["erpUnitLibrary"] = build_erp_unit_library_catalog_payload(include_units=False)
    return payload


def field_names_by_usage(connection: sqlite3.Connection, table_key: str, usage: str) -> list[str]:
    workspace_id = active_workspace_id(connection)
    rows = connection.execute(
        """
        SELECT field_name
        FROM field_semantics
        WHERE table_key = ? AND usage = ? AND workspace_id = ?
        ORDER BY confidence DESC, field_name
        """,
        (table_key, usage, workspace_id),
    ).fetchall()
    return [row["field_name"] for row in rows]


def field_names_by_role(connection: sqlite3.Connection, table_key: str, role: str) -> list[str]:
    workspace_id = active_workspace_id(connection)
    rows = connection.execute(
        """
        SELECT field_name
        FROM field_semantics
        WHERE table_key = ? AND role = ? AND workspace_id = ?
        ORDER BY confidence DESC, field_name
        """,
        (table_key, role, workspace_id),
    ).fetchall()
    return [row["field_name"] for row in rows]


def table_display_name(connection: sqlite3.Connection, table_key: str) -> str:
    registry = registry_for_table(connection, table_key)
    return registry["display_name"] if registry else table_key


def preferred_table_key(connection: sqlite3.Connection, table_key: str | None = None) -> str:
    if table_key:
        registry = registry_for_table(connection, table_key)
        if not registry:
            raise ValueError(f"Unknown table: {table_key}")
        return table_key
    workspace_id = active_workspace_id(connection)
    row = connection.execute(
        "SELECT table_key FROM table_registry WHERE workspace_id = ? ORDER BY row_count DESC, table_key LIMIT 1",
        (workspace_id,),
    ).fetchone()
    if not row:
        raise ValueError("No source table is available.")
    return row["table_key"]


def dashboard_exists(connection: sqlite3.Connection, dashboard_key: str) -> bool:
    workspace_id = active_workspace_id(connection)
    return bool(
        connection.execute(
            "SELECT 1 FROM dashboards WHERE dashboard_key = ? AND workspace_id = ?",
            (dashboard_key, workspace_id),
        ).fetchone()
    )


def dashboard_widget_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["config"] = json.loads(item.pop("config_json") or "{}")
    return item


def first_saved_view(connection: sqlite3.Connection, table_key: str) -> dict[str, Any] | None:
    workspace_id = active_workspace_id(connection)
    row = connection.execute(
        "SELECT * FROM saved_views WHERE table_key = ? AND workspace_id = ? ORDER BY is_default DESC, sort_order, created_at LIMIT 1",
        (table_key, workspace_id),
    ).fetchone()
    return saved_view_summary(connection, row) if row else None


def widget_recommendations_for_table(connection: sqlite3.Connection, table_key: str, limit: int) -> dict[str, Any]:
    registry = registry_for_table(connection, table_key)
    if not registry:
        raise ValueError(f"Unknown table: {table_key}")
    columns = table_columns(connection, registry["physical_table"])
    measures = [field for field in field_names_by_usage(connection, table_key, "aggregatable") if field in columns]
    dimensions = [field for field in field_names_by_usage(connection, table_key, "groupable") if field in columns]
    filterable = [field for field in field_names_by_usage(connection, table_key, "filterable") if field in columns]
    dates = [field for field in field_names_by_role(connection, table_key, "event_time") if field in columns]
    identities = [field for field in field_names_by_role(connection, table_key, "identity_key") if field in columns]
    measure = measures[0] if measures else ""
    dimension = dimensions[0] if dimensions else (filterable[0] if filterable else (columns[0] if columns else ""))
    time_field = dates[0] if dates else dimension
    view = first_saved_view(connection, table_key)
    table_name = registry["display_name"]
    recommendations: list[dict[str, Any]] = []
    if measure:
        recommendations.append({
            "type": "metric",
            "title": f"{table_name} {measure}",
            "reason": "Field semantics marked this as an aggregatable measure.",
            "tableKey": table_key,
            "dimension": "",
            "measure": measure,
            "aggregation": "sum",
            "valueFormat": "auto",
            "topN": 1,
        })
    if dimension and measure:
        recommendations.append({
            "type": "bar",
            "title": f"{dimension} by {measure}",
            "reason": "Category ranking from a groupable field and primary measure.",
            "tableKey": table_key,
            "dimension": dimension,
            "measure": measure,
            "aggregation": "sum",
            "topN": 12,
        })
    if time_field and measure:
        recommendations.append({
            "type": "line",
            "title": f"{measure} trend",
            "reason": "Trend chart from event-time semantics where available.",
            "tableKey": table_key,
            "dimension": time_field,
            "measure": measure,
            "aggregation": "sum",
            "topN": 12,
        })
    if dimension and measure:
        recommendations.append({
            "type": "pie",
            "title": f"{dimension} mix",
            "reason": "Composition view for the leading groupable field.",
            "tableKey": table_key,
            "dimension": dimension,
            "measure": measure,
            "aggregation": "sum",
            "topN": 8,
        })
    if view:
        recommendations.append({
            "type": "table",
            "title": f"{view['name']} details",
            "reason": "Saved view can be placed directly on the dashboard.",
            "tableKey": table_key,
            "viewKey": view["view_key"],
            "dataMode": "view",
            "columns": view["config"].get("columns", columns[:6]),
            "aggregation": "count",
            "topN": 100,
        })
    else:
        recommendations.append({
            "type": "table",
            "title": f"{table_name} details",
            "reason": "Detail table from the source columns.",
            "tableKey": table_key,
            "columns": columns[:6],
            "aggregation": "count",
            "topN": 100,
        })
    slicer_field = filterable[0] if filterable else dimension
    if slicer_field:
        recommendations.append({
            "type": "slicer",
            "title": f"{slicer_field} filter",
            "reason": "Filterable field promoted to a canvas slicer.",
            "tableKey": table_key,
            "dimension": slicer_field,
            "aggregation": "count",
            "topN": 12,
        })
    recommendations.append({
        "type": "text",
        "title": f"{table_name} evidence note",
        "reason": "Narrative note for AIBI evidence and Agent context.",
        "tableKey": table_key,
        "textContent": f"Source table: {table_name}. Evidence is available through source intelligence, query runtime, and saved views.",
        "aggregation": "count",
    })
    return {
        "ok": True,
        "tableKey": table_key,
        "tableName": table_name,
        "fields": {
            "columns": columns,
            "measures": measures,
            "dimensions": dimensions,
            "dateDimensions": dates,
            "filterable": filterable,
            "identityKeys": identities,
        },
        "recommendations": recommendations[: max(1, min(limit, 12))],
    }


def widget_filters_from_args(raw_filters: list[str], columns: list[str]) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = []
    available = set(columns)
    for index, raw in enumerate(raw_filters):
        parsed = parse_query_filter(raw)
        field = parsed["field"]
        operator = parsed["operator"] if parsed["operator"] in B_DASHBOARD_FILTER_OPERATORS else "contains"
        value = str(parsed.get("value") or "")
        if field not in available:
            raise ValueError(f"Unknown widget filter field: {field}")
        if filter_value_required(operator) and not value.strip():
            raise ValueError(f"Filter value is required for operator: {operator}")
        filters.append(normalize_filter_rule({
            "id": unique_key("widget_filter"),
            "field": field,
            "operator": operator,
            "value": value,
            "scope": "widget",
        }, index))
    return filters


def build_widget_proposal(
    connection: sqlite3.Connection,
    dashboard_key: str,
    widget_type: str,
    options: dict[str, Any],
) -> dict[str, Any]:
    return build_dashboard_widget_proposal_service(
        connection,
        dashboard_key,
        widget_type,
        options,
        dashboard_exists=dashboard_exists,
        resolve_view=resolve_view,
        preferred_table_key=preferred_table_key,
        registry_for_table=registry_for_table,
        active_workspace_id=active_workspace_id,
        unique_key=unique_key,
        resolve_dashboard_widget_key=resolve_dashboard_widget_key,
        next_dashboard_widget_sort_order=next_dashboard_widget_sort_order,
    )


def resolve_relationship_for_widget(connection: sqlite3.Connection, relation_key: str | None = None) -> dict[str, Any]:
    workspace_id = active_workspace_id(connection)
    if relation_key:
        row = connection.execute(
            "SELECT * FROM relationships WHERE relation_key = ? AND workspace_id = ?",
            (relation_key, workspace_id),
        ).fetchone()
    else:
        row = connection.execute(
            """
            SELECT *
            FROM relationships
            WHERE workspace_id = ?
            ORDER BY confidence DESC, created_at DESC, relation_key
            LIMIT 1
            """,
            (workspace_id,),
        ).fetchone()
    if not row:
        raise ValueError("No saved relationship is available. Save a relationship before adding a relationship widget.")
    return dict(row)


def build_relationship_widget_proposal(
    connection: sqlite3.Connection,
    dashboard_key: str,
    widget_type: str,
    options: dict[str, Any],
) -> dict[str, Any]:
    return build_dashboard_relationship_widget_proposal_service(
        connection,
        dashboard_key,
        widget_type,
        options,
        safe_aggregations=SAFE_AGGREGATIONS,
        dashboard_exists=dashboard_exists,
        resolve_relationship_for_widget=resolve_relationship_for_widget,
        registry_for_table=registry_for_table,
        table_columns=table_columns,
        table_display_name=table_display_name,
        active_workspace_id=active_workspace_id,
        unique_key=unique_key,
        resolve_dashboard_widget_key=resolve_dashboard_widget_key,
        next_dashboard_widget_sort_order=next_dashboard_widget_sort_order,
    )


def recommend_widgets_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        if args.all:
            workspace_id = active_workspace_id(connection)
            tables = rows_to_dicts(
                connection.execute(
                    "SELECT table_key FROM table_registry WHERE workspace_id = ? ORDER BY display_name",
                    (workspace_id,),
                )
            )
            payloads = [widget_recommendations_for_table(connection, row["table_key"], args.limit) for row in tables]
            return {
                "ok": True,
                "mode": "all",
                "tables": payloads,
                "recommendations": [
                    {**recommendation, "tableKey": payload["tableKey"], "tableName": payload["tableName"]}
                    for payload in payloads
                    for recommendation in payload["recommendations"]
                ],
            }
        table_key = preferred_table_key(connection, args.table)
        return widget_recommendations_for_table(connection, table_key, args.limit)


def add_recommended_widgets_command(args: argparse.Namespace) -> dict[str, Any]:
    return add_recommended_dashboard_widgets_service(
        dashboard_key=args.dashboard,
        table_key=args.table,
        limit=args.limit,
        allow_duplicates=args.allow_duplicates,
        confirm=args.yes,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        preferred_table_key=preferred_table_key,
        widget_recommendations_for_table=widget_recommendations_for_table,
        build_widget_proposal=build_widget_proposal,
        insert_dashboard_widget=insert_dashboard_widget,
    )


def parse_json_array_arg(raw: str | None, label: str) -> list[Any]:
    if raw is None or raw == "":
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} must be valid JSON: {error}") from error
    if not isinstance(parsed, list):
        raise ValueError(f"{label} must be a JSON array")
    return parsed


def save_dashboard_modules_command(args: argparse.Namespace) -> dict[str, Any]:
    widgets = parse_json_array_arg(args.widgets_json, "widgets-json")
    layout_items = parse_json_array_arg(args.layout_json, "layout-json")
    filter_items = parse_json_array_arg(args.filters_json, "filters-json")
    if args.canvas_width_mode not in {"stretch", "center"}:
        raise ValueError("--canvas-width-mode must be stretch or center")
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        dashboard = connection.execute(
            "SELECT * FROM dashboards WHERE dashboard_key = ? AND workspace_id = ?",
            (args.dashboard, workspace_id),
        ).fetchone()
        default_table_key = args.default_table or (dashboard["default_table_key"] if dashboard else "")
        if default_table_key:
            default_table_key = preferred_table_key(connection, default_table_key)
        elif widgets:
            default_table_key = preferred_table_key(connection, None)
        layout_by_id = {
            str(item.get("i") or ""): item
            for item in layout_items
            if isinstance(item, dict) and str(item.get("i") or "").strip()
        }
        proposed_widgets: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for index, raw_widget in enumerate(widgets):
            if not isinstance(raw_widget, dict):
                skipped.append({"index": index, "reason": "widget is not an object"})
                continue
            try:
                proposed_widgets.append(
                    dashboard_module_widget_from_payload(
                        connection,
                        args.dashboard,
                        raw_widget,
                        index,
                        default_table_key,
                        layout_by_id,
                        workspace_id=workspace_id,
                        preferred_table_key=preferred_table_key,
                        table_display_name=table_display_name,
                        unique_key=unique_key,
                    )
                )
            except ValueError as error:
                skipped.append({"index": index, "reason": str(error)})
        filters = [
            normalize_filter_rule(item, index)
            for index, item in enumerate(filter_items)
            if isinstance(item, dict) and str(item.get("field") or "").strip()
        ]
        layout = dashboard_layout(dashboard) if dashboard else {"version": 1}
        layout["version"] = 1
        layout["grid"] = layout.get("grid") or "12-col"
        layout["widgets"] = [widget["widget_key"] for widget in proposed_widgets]
        layout["widgetLayout"] = layout_items
        layout["canvasWidthMode"] = args.canvas_width_mode
        layout["globalFilters"] = filters
        dashboard_name = args.name or (dashboard["name"] if dashboard else ("分析证据看板" if args.dashboard == "default" else args.dashboard))
        proposed = {
            "dashboardKey": args.dashboard,
            "dashboardName": dashboard_name,
            "defaultTableKey": default_table_key,
            "canvasWidthMode": args.canvas_width_mode,
            "widgetCount": len(proposed_widgets),
            "layoutCount": len(layout_items),
            "filterCount": len(filters),
            "skippedCount": len(skipped),
        }
        if not args.yes:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "proposed": proposed,
                "proposedWidgets": proposed_widgets,
                "proposedFilters": filters,
                "skippedWidgets": skipped,
            }
        now = now_iso()
        save_dashboard_with_widgets(
            connection,
            workspace_id=workspace_id,
            dashboard_key=args.dashboard,
            dashboard_name=dashboard_name,
            default_table_key=default_table_key,
            layout=layout,
            widgets=proposed_widgets,
            now=now,
        )
        connection.commit()
        ensure_navigation_modules(connection)
        saved_dashboard = dashboard_snapshot(connection, workspace_id=workspace_id, dashboard_key=args.dashboard)
    return {
        "ok": True,
        "confirmed": True,
        "savedDashboardKey": args.dashboard,
        "savedDashboardModules": len(proposed_widgets),
        "savedDashboardFilters": len(filters),
        "skippedWidgets": skipped,
        "dashboard": saved_dashboard,
    }


def template_widget_layout(widget_type: str, index: int) -> dict[str, Any]:
    return template_widget_layout_service(widget_type, index)


def table_template_fields(connection: sqlite3.Connection, table_key: str, workspace_id: str | None = None) -> dict[str, Any]:
    resolved_workspace_id = workspace_id or active_workspace_id(connection)
    registry_lookup = lambda conn, key: conn.execute(
        "SELECT * FROM table_registry WHERE table_key = ? AND workspace_id = ?",
        (key, resolved_workspace_id),
    ).fetchone()
    fields_by_usage = lambda conn, key, usage: [
        row["field_name"] for row in conn.execute(
            "SELECT field_name FROM field_semantics WHERE table_key = ? AND usage = ? AND workspace_id = ? ORDER BY confidence DESC, field_name",
            (key, usage, resolved_workspace_id),
        ).fetchall()
    ]
    fields_by_role = lambda conn, key, role: [
        row["field_name"] for row in conn.execute(
            "SELECT field_name FROM field_semantics WHERE table_key = ? AND role = ? AND workspace_id = ? ORDER BY confidence DESC, field_name",
            (key, role, resolved_workspace_id),
        ).fetchall()
    ]
    return table_template_fields_service(
        connection,
        table_key,
        registry_for_table=registry_lookup,
        table_columns=table_columns,
        field_names_by_usage=fields_by_usage,
        field_names_by_role=fields_by_role,
    )


def build_business_analysis_templates(connection: sqlite3.Connection, table_key: str | None = None, limit: int = 12, template_key: str = "business", workspace_id: str | None = None) -> dict[str, Any]:
    return build_business_analysis_templates_service(
        connection,
        table_key,
        limit,
        active_workspace_id=active_workspace_id,
        rows_to_dicts=rows_to_dicts,
        preferred_table_key=preferred_table_key,
        slug=slug,
        table_template_fields=lambda conn, key: table_template_fields(conn, key, workspace_id),
        template_key=template_key,
        workspace_id=workspace_id,
    )


def build_business_dashboard_payload(connection: sqlite3.Connection, table_key: str | None = None, limit: int = 10, template_key: str = "business", workspace_id: str | None = None) -> dict[str, Any]:
    return build_business_dashboard_payload_service(
        connection,
        table_key,
        limit,
        build_business_analysis_templates=build_business_analysis_templates,
        preferred_table_key=preferred_table_key,
        template_key=template_key,
        workspace_id=workspace_id,
    )


def write_business_dashboard(
    connection: sqlite3.Connection,
    dashboard_key: str,
    dashboard_name: str,
    default_table_key: str,
    widgets: list[dict[str, Any]],
    layout_items: list[dict[str, Any]],
) -> dict[str, Any]:
    return write_business_dashboard_service(
        connection,
        dashboard_key,
        dashboard_name,
        default_table_key,
        widgets,
        layout_items,
        active_workspace_id=active_workspace_id,
        preferred_table_key=preferred_table_key,
        table_display_name=table_display_name,
        unique_key=unique_key,
        now_iso=now_iso,
    )


def business_dashboard_command(args: argparse.Namespace) -> dict[str, Any]:
    result = run_business_dashboard_command_service(
        op=args.op,
        dashboard_key=args.dashboard,
        table_key=args.table,
        template_key=args.template,
        limit=args.limit,
        name=args.name,
        confirm=args.yes,
        open_db=open_db,
        build_business_dashboard_payload=build_business_dashboard_payload,
        active_workspace_id=active_workspace_id,
        unique_key=unique_key,
        write_business_dashboard=write_business_dashboard,
        ensure_navigation_modules=ensure_navigation_modules,
    )
    if args.op == "draft" or result.get("dryRun"):
        if args.op == "draft":
            result.setdefault("dryRun", True)
            result.setdefault("requiresConfirmation", False)
        with open_db() as connection:
            workspace_id = active_workspace_id(connection)
        draft = result.get("draft") if isinstance(result.get("draft"), dict) else {}
        result["evidenceBundle"] = write_evidence_bundle(
            command="business-dashboard",
            workspace_id=workspace_id,
            title=f"Business dashboard {args.op}: {draft.get('templateKey') or args.template}",
            status="draft" if args.op == "draft" else "dry-run",
            summary={
                "op": args.op,
                "templateKey": draft.get("templateKey") or args.template,
                "defaultTableKey": draft.get("defaultTableKey") or args.table,
                "templateCount": result.get("templateCount"),
                "widgetCount": len(draft.get("widgets") or []),
                "categoryCount": len(draft.get("categories") or []),
                "missingRequirementCount": len(draft.get("missingRequirements") or []),
            },
            payload={
                "draft": draft,
                "proposed": result.get("proposed"),
            },
        )
    return result


def erp_unit_library_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        enabled = is_domain_pack_enabled(connection, workspace_id, "erp-units", "dashboardUnits")
        if not enabled:
            return {
                "ok": True,
                "available": False,
                "packId": "erp-units",
                "reason": "domain-pack-not-enabled",
                "catalog": None,
                "selection": None,
            }
        catalog = build_erp_unit_library_catalog_payload(include_units=not args.summary)
        if not args.select:
            return {"ok": True, "available": True, "packId": "erp-units", "catalog": catalog}
        table_rows = rows_to_dicts(
            connection.execute(
                "SELECT * FROM table_registry WHERE workspace_id = ? ORDER BY row_count DESC, table_key",
                (workspace_id,),
            )
        )
        fields_by_key = {row["table_key"]: table_template_fields(connection, row["table_key"]) for row in table_rows}
        if not table_rows:
            table_rows, fields_by_key = source_profile_table_inputs(connection, workspace_id)
        preferred = ""
        if args.table:
            try:
                preferred = preferred_table_key(connection, args.table)
            except ValueError:
                if any(row.get("table_key") == args.table for row in table_rows):
                    preferred = args.table
                else:
                    raise
        selection = build_erp_dashboard_unit_templates(
            table_rows,
            fields_by_key,
            preferred_table_key_value=preferred,
            limit=args.limit,
            slug=slug,
        )
    return {
        "ok": True,
        "catalog": catalog,
        "selection": selection,
    }


def build_agent_dashboard_create_draft(
    connection: sqlite3.Connection,
    workspace_id: str,
    table_key: str | None,
    prompt: str,
    limit: int = 8,
    template_key: str = "business",
    resolved_widget: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_agent_dashboard_create_draft_service(
        connection,
        workspace_id,
        table_key,
        prompt,
        limit,
        template_key=template_key,
        resolved_widget=resolved_widget,
        build_business_dashboard_payload=build_business_dashboard_payload,
    )


def add_widget_command(args: argparse.Namespace) -> dict[str, Any]:
    options = {
        "widgetKey": args.widget,
        "tableKey": args.table,
        "viewKey": args.view,
        "title": args.title,
        "subtitle": args.subtitle,
        "dimension": args.dimension,
        "measure": args.measure,
        "aggregation": args.agg,
        "topN": args.top_n,
        "valueFormat": args.value_format,
        "textContent": args.text_content,
        **widget_style_options_from_args(args),
    }
    return add_dashboard_widget_service(
        dashboard_key=args.dashboard,
        widget_type=args.type,
        options=options,
        confirm=args.yes,
        open_db=open_db,
        build_widget_proposal=build_widget_proposal,
        insert_dashboard_widget=insert_dashboard_widget,
    )


def add_relationship_widget_command(args: argparse.Namespace) -> dict[str, Any]:
    options = {
        "widgetKey": args.widget,
        "relationship": args.relationship,
        "title": args.title,
        "subtitle": args.subtitle,
        "group": args.group,
        "measure": args.measure,
        "aggregation": args.agg,
        "topN": args.top_n,
        "valueFormat": args.value_format,
        **widget_style_options_from_args(args),
    }
    return add_dashboard_relationship_widget_service(
        dashboard_key=args.dashboard,
        widget_type=args.type,
        options=options,
        confirm=args.yes,
        open_db=open_db,
        build_relationship_widget_proposal=build_relationship_widget_proposal,
        insert_dashboard_widget=insert_dashboard_widget,
    )


def set_widget_command(args: argparse.Namespace) -> dict[str, Any]:
    return set_dashboard_widget_service(
        widget_key=args.widget,
        widget_type=args.type,
        title=args.title,
        table_key=args.table,
        view_key=args.view,
        config_updates={
            "subtitle": args.subtitle,
            "dimension": args.dimension,
            "measure": args.measure,
            "aggregation": args.agg,
            "topN": args.top_n,
            "valueFormat": args.value_format,
            "textContent": args.text_content,
        },
        style_options=widget_style_options_from_args(args),
        filter_values=args.filter,
        clear_filters=args.clear_filters,
        confirm=args.yes,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        dashboard_widget_row_to_dict=dashboard_widget_row_to_dict,
        resolve_view=resolve_view,
        preferred_table_key=preferred_table_key,
        registry_for_table=registry_for_table,
        table_columns=table_columns,
        widget_filters_from_args=widget_filters_from_args,
    )


def copy_widget_command(args: argparse.Namespace) -> dict[str, Any]:
    return copy_dashboard_widget_service(
        widget_key=args.widget,
        dashboard_key=args.dashboard,
        title=args.title,
        clear_filters=args.clear_filters,
        confirm=args.yes,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        dashboard_widget_row_to_dict=dashboard_widget_row_to_dict,
        dashboard_exists=dashboard_exists,
        unique_key=unique_key,
        next_dashboard_widget_sort_order=next_dashboard_widget_sort_order,
        insert_dashboard_widget=insert_dashboard_widget,
    )


def remove_widget_command(args: argparse.Namespace) -> dict[str, Any]:
    return remove_dashboard_widget_service(
        widget_key=args.widget,
        confirm=args.yes,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        dashboard_widget_row_to_dict=dashboard_widget_row_to_dict,
    )


