from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Callable

from agent_action_confirmations import confirm_dry_run_response, confirmed_response, mark_action_confirmed
from atomic_import_plan_service import bind_single_import_plan


def handle_index_create_confirmation(
    connection: sqlite3.Connection,
    action: sqlite3.Row,
    payload: dict[str, Any],
    *,
    action_key: str,
    yes: bool,
    confirmed_at: str,
    build_index_plan: Callable[[sqlite3.Connection, str, str, str], tuple[dict[str, Any], list[str]]],
    execute_index_plan: Callable[[sqlite3.Connection, dict[str, Any], list[str]], dict[str, Any]],
) -> dict[str, Any]:
    table_key = str(payload.get("tableKey") or "")
    field = str(payload.get("field", ""))
    index_key = str(payload.get("indexKey", ""))
    if not table_key:
        raise ValueError("Index action draft is missing a table")
    if not field:
        raise ValueError("Index action draft is missing a field")
    proposed, columns = build_index_plan(connection, table_key, field, index_key)
    if not yes:
        return confirm_dry_run_response(action, payload, proposedExecution=proposed)
    execution = execute_index_plan(connection, proposed, columns)
    mark_action_confirmed(connection, action_key, confirmed_at)
    connection.commit()
    return confirmed_response(
        action_key,
        createdIndex=execution.get("createdIndex"),
        syncedRows=execution.get("syncedRows"),
    )


def handle_relationship_save_confirmation(
    connection: sqlite3.Connection,
    action: sqlite3.Row,
    payload: dict[str, Any],
    *,
    action_key: str,
    yes: bool,
    confirmed_at: str,
    build_relationship_save_plan: Callable[[sqlite3.Connection, str, str, str, str, str, int], dict[str, Any]],
    execute_relationship_save: Callable[[sqlite3.Connection, dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    left_table = str(payload.get("leftTable", ""))
    right_table = str(payload.get("rightTable", ""))
    left_field = str(payload.get("leftField", ""))
    right_field = str(payload.get("rightField", ""))
    join_type = str(payload.get("joinType", "left") or "left")
    if not all([left_table, right_table, left_field, right_field]):
        raise ValueError("Relationship action draft is missing table or field targets")
    plan = build_relationship_save_plan(connection, left_table, right_table, left_field, right_field, join_type, 20)
    if not yes:
        return confirm_dry_run_response(
            action,
            payload,
            relationship=plan["relationship"],
            relationshipPreview=plan["relationshipPreview"],
        )
    saved = execute_relationship_save(connection, plan["relationship"])
    mark_action_confirmed(connection, action_key, confirmed_at)
    connection.commit()
    return confirmed_response(action_key, savedRelationship=saved, relationshipPreview=plan["relationshipPreview"])


def handle_import_commit_confirmation(
    connection: sqlite3.Connection,
    action: sqlite3.Row,
    payload: dict[str, Any],
    *,
    action_key: str,
    yes: bool,
    confirmed_at: str,
    build_import_preview: Callable[..., dict[str, Any]],
    execute_import_commit: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    file_path = str(payload.get("filePath", ""))
    table_key = str(payload.get("tableKey", "")) or None
    name = str(payload.get("name", "")) or None
    mode = str(payload.get("mode", "create") or "create")
    unique_fields = payload.get("uniqueFields")
    unique_fields_value = ",".join(str(item) for item in unique_fields) if isinstance(unique_fields, list) else (str(unique_fields) if isinstance(unique_fields, str) else None)
    conflict_rule = payload.get("conflictRule")
    conflict_rule_value = str(conflict_rule) if isinstance(conflict_rule, str) else None
    if not file_path:
        raise ValueError("Import action draft is missing filePath")
    workspace_id = str(action["workspace_id"])
    preview = build_import_preview(
        connection,
        file_path,
        table_key,
        unique_fields_value,
        conflict_rule_value,
        workspace_id=workspace_id,
    )
    if str(preview.get("workspaceId") or "") != workspace_id:
        raise RuntimeError("Import action preview escaped the draft workspace.")
    workspace = connection.execute(
        "SELECT current_source_run_id FROM workspaces WHERE id = ?",
        (workspace_id,),
    ).fetchone()
    bound_preview = bind_single_import_plan(
        preview,
        Path(file_path),
        current_source_run_id=str(workspace["current_source_run_id"] or "") if workspace else None,
    )
    if not yes:
        payload["expectedPlan"] = bound_preview["planFingerprint"]
        payload["mode"] = str((bound_preview.get("commitOptions") or {}).get("mode") or mode)
        connection.execute(
            "UPDATE action_drafts SET payload_json = ? WHERE workspace_id = ? AND action_key = ?",
            (json.dumps(payload, ensure_ascii=False), workspace_id, action_key),
        )
        connection.commit()
        return confirm_dry_run_response(action, payload, importPreview=bound_preview)
    expected_plan = str(payload.get("expectedPlan") or "")
    if not expected_plan:
        raise ValueError("Import draft must be previewed again before confirmation")
    if expected_plan != str(bound_preview.get("planFingerprint") or ""):
        raise ValueError("Import file or workspace version changed after preview; preview the draft again")
    expected_mode = str((bound_preview.get("commitOptions") or {}).get("mode") or "")
    if mode != expected_mode:
        raise ValueError("Import mode changed after preview; create a new preview")
    result = execute_import_commit(
        connection,
        file_path,
        table_key,
        name,
        mode,
        unique_fields_value,
        conflict_rule_value,
        workspace_id=workspace_id,
    )
    if str(result.get("workspaceId") or "") != workspace_id:
        raise RuntimeError("Import action commit escaped the draft workspace.")
    mark_action_confirmed(connection, action_key, confirmed_at)
    connection.commit()
    return confirmed_response(action_key, importResult=result)


def handle_formula_save_confirmation(
    connection: sqlite3.Connection,
    action: sqlite3.Row,
    payload: dict[str, Any],
    *,
    action_key: str,
    yes: bool,
    confirmed_at: str,
    build_formula_save_plan: Callable[[sqlite3.Connection, str, str, str, str, str, str, str, str, str], dict[str, Any]],
    execute_formula_save_plan: Callable[[sqlite3.Connection, dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    table_key = str(payload.get("tableKey", ""))
    name = str(payload.get("name", ""))
    expression = str(payload.get("formulaText", ""))
    mode = str(payload.get("mode", "aggregate") or "aggregate")
    dimension = str(payload.get("dimension", "") or "")
    time_field = str(payload.get("timeField", "") or "")
    value_format = str(payload.get("valueFormat", "auto") or "auto")
    description = str(payload.get("description", "") or "")
    formula_key = str(payload.get("formulaKey", "") or "")
    if not all([table_key, name, expression]):
        raise ValueError("Formula action draft is missing table, name, or expression")
    proposed = build_formula_save_plan(connection, table_key, name, expression, mode, dimension, time_field, value_format, description, formula_key)
    if not yes:
        return confirm_dry_run_response(action, payload, proposedFormula=proposed)
    saved = execute_formula_save_plan(connection, proposed)
    mark_action_confirmed(connection, action_key, confirmed_at)
    connection.commit()
    return confirmed_response(action_key, savedFormula=saved)


def handle_view_save_confirmation(
    connection: sqlite3.Connection,
    action: sqlite3.Row,
    payload: dict[str, Any],
    *,
    action_key: str,
    yes: bool,
    confirmed_at: str,
    build_save_view_plan: Callable[[sqlite3.Connection, str, str, dict[str, Any], str, str, str, int], dict[str, Any]],
    execute_save_view_plan: Callable[[sqlite3.Connection, dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    table_key = str(payload.get("table_key") or payload.get("tableKey") or "")
    name = str(payload.get("name", ""))
    view_key = str(payload.get("view_key") or payload.get("viewKey") or "")
    tag_name = str(payload.get("tag_name") or payload.get("tagName") or "Agent 保存的筛选口径")
    config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
    if not all([table_key, name]):
        raise ValueError("View action draft is missing table or name")
    proposed = build_save_view_plan(connection, table_key, name, config, view_key, tag_name, "agent", 1)
    if not yes:
        return confirm_dry_run_response(action, payload, proposedView=proposed)
    saved = execute_save_view_plan(connection, proposed)
    mark_action_confirmed(connection, action_key, confirmed_at)
    connection.commit()
    return confirmed_response(action_key, savedView=saved)


def handle_metric_add_confirmation(
    connection: sqlite3.Connection,
    action: sqlite3.Row,
    payload: dict[str, Any],
    *,
    action_key: str,
    yes: bool,
    confirmed_at: str,
    build_metric_add_plan: Callable[[sqlite3.Connection, str, str, str, str, str, str, list[Any], str, str, str], dict[str, Any]],
    execute_metric_add_plan: Callable[[sqlite3.Connection, dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    table_key = str(payload.get("tableKey", ""))
    label = str(payload.get("label") or payload.get("name") or "")
    measure = str(payload.get("measure", "") or "*")
    aggregation = str(payload.get("aggregation", "count") or "count")
    dimension = str(payload.get("dimension", "") or "")
    time_field = str(payload.get("timeField", "") or "")
    value_format = str(payload.get("valueFormat", "auto") or "auto")
    description = str(payload.get("description", "") or "")
    metric_key = str(payload.get("metricKey", "") or "")
    filters = payload.get("filters") if isinstance(payload.get("filters"), list) else []
    if not all([table_key, label, measure, aggregation]):
        raise ValueError("Metric action draft is missing table, label, measure, or aggregation")
    proposed = build_metric_add_plan(connection, table_key, label, measure, aggregation, dimension, time_field, filters, value_format, description, metric_key)
    if not yes:
        return confirm_dry_run_response(action, payload, proposedMetric=proposed)
    saved = execute_metric_add_plan(connection, proposed)
    mark_action_confirmed(connection, action_key, confirmed_at)
    connection.commit()
    return confirmed_response(action_key, savedMetric=saved)


def handle_semantic_set_confirmation(
    connection: sqlite3.Connection,
    action: sqlite3.Row,
    payload: dict[str, Any],
    *,
    action_key: str,
    yes: bool,
    confirmed_at: str,
    workspace_id: str,
    build_semantic_set_plan: Callable[[sqlite3.Connection, str, str, str, list[str], list[str], float, str], dict[str, Any]],
    execute_semantic_set_plan: Callable[[sqlite3.Connection, dict[str, Any]], dict[str, Any]],
    semantic_row_to_payload: Callable[[sqlite3.Row, str], dict[str, Any]],
) -> dict[str, Any]:
    table_key = str(payload.get("tableKey", ""))
    field = str(payload.get("field", ""))
    role = str(payload.get("role", ""))
    usage = payload.get("usage")
    tags = payload.get("tags")
    confidence = float(payload.get("confidence") or 1.0)
    note = str(payload.get("note", ""))
    if not all([table_key, field, role]):
        raise ValueError("Semantic action draft is missing table, field, or role")
    usage_keys = [key for key, enabled in usage.items() if enabled] if isinstance(usage, dict) else []
    tag_values = [str(item) for item in tags] if isinstance(tags, list) else []
    proposed = build_semantic_set_plan(connection, table_key, field, role, usage_keys, tag_values, confidence, note)
    current = connection.execute(
        """
        SELECT *
        FROM field_semantics
        WHERE table_key = ? AND field_name = ? AND workspace_id = ?
        """,
        (proposed["tableKey"], proposed["field"], workspace_id),
    ).fetchone()
    if not yes:
        return confirm_dry_run_response(
            action,
            payload,
            current=semantic_row_to_payload(current, proposed["tableName"]) if current else None,
            proposedSemantic=proposed,
        )
    saved = execute_semantic_set_plan(connection, proposed)
    mark_action_confirmed(connection, action_key, confirmed_at)
    connection.commit()
    return confirmed_response(action_key, semantic=saved)


def handle_dashboard_widget_add_confirmation(
    connection: sqlite3.Connection,
    action: sqlite3.Row,
    payload: dict[str, Any],
    *,
    action_key: str,
    yes: bool,
    confirmed_at: str,
    build_widget_proposal: Callable[[sqlite3.Connection, str, str, dict[str, Any]], dict[str, Any]],
    insert_dashboard_widget: Callable[[sqlite3.Connection, dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    dashboard_key = str(payload.get("dashboardKey", "") or "")
    widget_type = str(payload.get("widgetType", "") or "")
    options = dict(payload.get("options")) if isinstance(payload.get("options"), dict) else {}
    if not all([dashboard_key, widget_type]):
        raise ValueError("Widget action draft is missing dashboardKey or widgetType")
    if payload.get("tableKey") and not options.get("tableKey"):
        options["tableKey"] = payload["tableKey"]
    if payload.get("title") and not options.get("title"):
        options["title"] = payload["title"]
    proposed = build_widget_proposal(connection, dashboard_key, widget_type, options)
    if not yes:
        return confirm_dry_run_response(action, payload, proposedWidget=proposed)
    insert_dashboard_widget(connection, proposed)
    mark_action_confirmed(connection, action_key, confirmed_at)
    connection.commit()
    return confirmed_response(action_key, addedWidget=proposed)


def handle_dashboard_filter_add_confirmation(
    connection: sqlite3.Connection,
    action: sqlite3.Row,
    payload: dict[str, Any],
    *,
    action_key: str,
    yes: bool,
    confirmed_at: str,
    build_dashboard_filter_add_plan: Callable[[sqlite3.Connection, str, str, str, str, str, bool], dict[str, Any]],
    execute_dashboard_filter_add_plan: Callable[[sqlite3.Connection, str, list[dict[str, Any]]], None],
) -> dict[str, Any]:
    dashboard_key = str(payload.get("dashboardKey", "") or "")
    field = str(payload.get("field", "") or "")
    operator = str(payload.get("operator", "equals") or "equals")
    value = str(payload.get("value", "") or "")
    filter_key = str(payload.get("filterKey", "") or "")
    disabled = bool(payload.get("disabled") is True)
    if not all([dashboard_key, field, operator]):
        raise ValueError("Dashboard filter action draft is missing dashboardKey, field, or operator")
    plan = build_dashboard_filter_add_plan(connection, dashboard_key, field, operator, value, filter_key, disabled)
    if not yes:
        return confirm_dry_run_response(
            action,
            payload,
            proposedFilter=plan["proposed"],
            filtersAfter=plan["filtersAfter"],
        )
    execute_dashboard_filter_add_plan(connection, dashboard_key, plan["filtersAfter"])
    mark_action_confirmed(connection, action_key, confirmed_at)
    connection.commit()
    return confirmed_response(action_key, filter=plan["proposed"], filters=plan["filtersAfter"])


def handle_dashboard_operation_confirmation(
    connection: sqlite3.Connection,
    action: sqlite3.Row,
    payload: dict[str, Any],
    *,
    action_key: str,
    yes: bool,
    confirmed_at: str,
    build_dashboard_operation_plan: Callable[[sqlite3.Connection, str, str, str, str, str], dict[str, Any]],
    execute_dashboard_operation_plan: Callable[[sqlite3.Connection, dict[str, Any], str, int], dict[str, Any]],
) -> dict[str, Any]:
    op = str(payload.get("op") or action["kind"].split(".")[-1])
    dashboard_key = str(payload.get("dashboardKey", "") or "")
    name = str(payload.get("name", "") or "")
    table_key = str(payload.get("defaultTableKey") or payload.get("tableKey") or "")
    source_dashboard_key = str(payload.get("sourceDashboardKey") or dashboard_key)
    if not dashboard_key:
        raise ValueError("Dashboard action draft is missing dashboardKey")
    proposed = build_dashboard_operation_plan(connection, op, dashboard_key, name, table_key, source_dashboard_key)
    if not yes:
        return confirm_dry_run_response(action, payload, proposedDashboardOperation=proposed)
    result = execute_dashboard_operation_plan(connection, proposed, "agent", 1)
    mark_action_confirmed(connection, action_key, confirmed_at)
    connection.commit()
    return confirmed_response(action_key, operation=op, **result)


def handle_dashboard_create_confirmation(
    connection: sqlite3.Connection,
    action: sqlite3.Row,
    payload: dict[str, Any],
    *,
    action_key: str,
    yes: bool,
    confirmed_at: str,
    workspace_id: str,
    unique_key: Callable[[str], str],
    build_agent_dashboard_create_draft: Callable[[sqlite3.Connection, str, str | None, str, int], dict[str, Any]],
    write_business_dashboard: Callable[[sqlite3.Connection, str, str, str, list[dict[str, Any]], list[dict[str, Any]]], dict[str, Any]],
    upsert_navigation_module: Callable[..., dict[str, Any] | None],
) -> dict[str, Any]:
    draft = payload.get("dashboardDraft") if isinstance(payload.get("dashboardDraft"), dict) else {}
    if not draft or not isinstance(draft.get("widgets"), list):
        draft = build_agent_dashboard_create_draft(
            connection,
            workspace_id,
            str(payload.get("tableKey") or "") or None,
            str(payload.get("prompt", "")),
            8,
        )
    proposed_dashboard = {
        "op": "create",
        "dashboardName": draft.get("dashboardName") or payload.get("dashboardName") or "Agent 分析看板",
        "defaultTableKey": draft.get("defaultTableKey") or payload.get("tableKey"),
        "templateCount": draft.get("templateCount", 0),
        "widgetCount": draft.get("widgetCount", len(draft.get("widgets", []))),
        "categories": draft.get("categories", []),
        "source": draft.get("source", "business-dashboard"),
    }
    if not yes:
        return confirm_dry_run_response(
            action,
            payload,
            proposedDashboard=proposed_dashboard,
            dashboardDraft=draft,
        )
    dashboard_key = unique_key("agent")
    saved = write_business_dashboard(
        connection,
        dashboard_key,
        str(proposed_dashboard["dashboardName"]),
        str(proposed_dashboard["defaultTableKey"]),
        draft.get("widgets", []),
        draft.get("layout", []),
    )
    connection.execute(
        "UPDATE dashboards SET created_by = 'agent', agent_managed = 1 WHERE dashboard_key = ? AND workspace_id = ?",
        (dashboard_key, workspace_id),
    )
    upsert_navigation_module(
        connection,
        module_key=f"dashboard:{dashboard_key}",
        name=str(proposed_dashboard["dashboardName"]),
        module_type="dashboard",
        dashboard_key=dashboard_key,
        created_by="agent",
        agent_managed=1,
    )
    mark_action_confirmed(connection, action_key, confirmed_at)
    connection.commit()
    return confirmed_response(action_key, createdDashboardKey=dashboard_key, **saved)
