"""Agent interaction application use cases.

This module owns prompt resolution, grounded answers, action drafts, and
confirmed action execution. It has no CLI process-entry responsibility.
"""

from __future__ import annotations
import argparse
from contextlib import closing
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any
from aibi_contracts import core_semantic_runtime as build_core_semantic_runtime
from aibi_contracts import source_pipeline_contract as build_source_pipeline_contract
from agent_action_confirmations import (
    confirm_dry_run_response,
    confirmed_response,
    reject_dry_run_response,
    rejected_response,
)
from agent_action_draft_store import (
    action_draft_payload,
    create_action_draft,
    get_action_draft,
    mark_action_confirmed,
    mark_action_rejected,
)
from agent_confirm_execution_handlers import (
    handle_dashboard_create_confirmation,
    handle_dashboard_filter_add_confirmation,
    handle_dashboard_operation_confirmation,
    handle_dashboard_widget_add_confirmation,
    handle_formula_save_confirmation,
    handle_import_commit_confirmation,
    handle_index_create_confirmation,
    handle_metric_add_confirmation,
    handle_relationship_save_confirmation,
    handle_semantic_set_confirmation,
    handle_view_save_confirmation,
)
from agent_prompt_resolution import (
    agent_action_evidence,
    agent_action_kind,
    agent_action_label,
    build_agent_action_payload,
    dashboard_operation_from_prompt,
    resolve_agent_prompt_intents,
    select_agent_table,
    should_create_agent_draft,
)
from agent_intent_service import build_business_intent_frame
from business_understanding_service import (
    apply_business_understanding_to_intent,
    build_business_understanding_frame,
    build_business_understanding_gap,
)
from semantic_context_router import build_semantic_context_bundle
from agent_clarification_service import build_agent_clarification
from agent_recommended_commands import build_agent_recommended_commands
from bi_cli_core import (
    DUCKDB_PATH,
    ROOT,
    now_iso,
    quote_identifier,
    quote_relationship_identifier,
    slug,
    unique_key,
)
from query_runtime import cursor_rows, open_validated_duckdb_query, replica_expectation
from context_pack_service import contextualized_prompt, matched_context
from analysis_safety_guard import build_verified_analysis_gap, requires_verified_analysis_plan
from domain_pack_service import domain_pack_runtime_context, is_domain_pack_enabled
from analytical_skill_service import analytical_skill_runtime_context
from platform_analytics_knowledge import (
    execute_platform_knowledge,
    match_platform_knowledge,
    platform_knowledge_context,
)
from query_plan_receipt_service import create_query_plan_receipt
from trusted_answer_service import (
    aggregation_from_metric_prompt,
    build_trusted_answer_card,
    select_metric_dimension_from_prompt,
    select_metric_field_from_prompt,
)
from trusted_query_service import build_semantic_query_contract, current_source_run_binding
from semantic_query_planner import BLOCKING_STATUSES, build_workspace_semantic_plan, semantic_query_prompt_directives
from semantic_query_execution import execute_workspace_semantic_query
from confirmed_query_service import create_confirmed_query_candidate, recall_confirmed_plans
from analysis_run_service import create_analysis_run, validate_branch_parent
from workspace_manifest_service import workspace_planning_binding
from bi_cli_schema import (
    active_workspace_id,
    open_db,
    registry_for_table,
    table_columns,
    upsert_navigation_module,
)
from bi_cli_io_services import parse_json_object, rows_to_dicts
from bi_cli_source_commands import build_import_preview, execute_import_commit, resolve_table_registry
from bi_cli_query_view_commands import build_save_view_plan, execute_save_view_plan
from bi_cli_dashboard_commands import (
    build_dashboard_filter_add_plan,
    build_index_plan,
    dashboard_filters_snapshot,
    execute_dashboard_filter_add_plan,
    execute_index_plan,
    filter_value_required,
    recommend_indexes_for_table,
)
from bi_cli_widget_commands import (
    build_agent_dashboard_create_draft,
    build_widget_proposal,
    field_names_by_role,
    preferred_table_key,
    template_widget_layout,
    write_business_dashboard,
)
from bi_cli_semantic_metric_commands import (
    build_metric_add_plan,
    build_semantic_set_plan,
    execute_metric_add_plan,
    execute_semantic_set_plan,
    normalize_semantic_role,
    primary_usage_from_object,
    semantic_row_to_payload,
    semantic_usage_object,
)
from bi_cli_relationship_formula_commands import (
    build_dashboard_operation_plan,
    build_formula_save_plan,
    build_relationship_save_plan,
    execute_dashboard_operation_plan,
    execute_formula_save_plan,
    execute_relationship_save,
    recommend_relationships_for_connection,
)
from dashboard_widget_operations import insert_dashboard_widget
from formula_engine import FormulaError
from query_runtime import SAFE_AGGREGATIONS
from relationship_command_service import relationship_rows_for_chart as relationship_rows_for_chart_service
from relationship_tools import build_relationship_query
from saved_view_query_service import list_from_value
from evidence_dashboard_drafts import build_source_intelligence_dashboard_draft
from evidence_receipts import build_source_intelligence_dashboard_candidate
from evidence_run_store import (
    get_source_intelligence_run,
    latest_source_intelligence_run,
    source_intelligence_run_manifest,
)


def source_intelligence_dashboard_draft_command(args: argparse.Namespace) -> dict[str, Any]:
    with closing(open_db()) as connection:
        workspace_id = str(getattr(args, "workspace", "") or active_workspace_id(connection))
        if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
            raise ValueError(f"Unknown workspace: {workspace_id}")
        run = get_source_intelligence_run(connection, workspace_id=workspace_id, run_key=args.run) if args.run else latest_source_intelligence_run(connection, workspace_id=workspace_id)
        if not run:
            raise ValueError("No source intelligence run is available for dashboard draft creation")
        manifest = source_intelligence_run_manifest(run)
        candidate = build_source_intelligence_dashboard_candidate(Path(run["output_dir"]), manifest)
        analyses = candidate.get("analyses") if isinstance(candidate.get("analyses"), list) else []
        if not analyses:
            raise ValueError(f"Source intelligence run has no executable dashboard candidate: {run['run_key']}")
        dashboard_draft = build_source_intelligence_dashboard_draft(
            connection,
            run,
            candidate,
            dashboard_name=args.name or str(candidate.get("title") or "Source Intelligence 候选看板"),
            limit=args.limit,
            preferred_table_key=preferred_table_key,
            template_widget_layout=template_widget_layout,
            slug=slug,
        )
        action_key = unique_key("draft")
        payload = {
            "prompt": f"Create dashboard from source intelligence run {run['run_key']}",
            "dashboardKey": "",
            "dashboardName": dashboard_draft["dashboardName"],
            "defaultTableKey": dashboard_draft["defaultTableKey"],
            "tableKey": dashboard_draft["defaultTableKey"],
            "sourceRunKey": dashboard_draft["sourceRunKey"],
            "dashboardDraft": dashboard_draft,
            "dashboardCandidate": candidate,
        }
        evidence = dashboard_draft["evidence"]
        action_draft = create_action_draft(
            connection,
            action_key=action_key,
            workspace_id=workspace_id,
            kind="dashboard.create",
            label="Source Intelligence 看板草案",
            payload=payload,
            evidence=evidence,
            created_at=now_iso(),
        )
        connection.commit()
    return {
        "ok": True,
        "dryRun": True,
        "requiresConfirmation": True,
        "source": "source-intelligence-dashboard-candidate",
        "sourceRunKey": dashboard_draft["sourceRunKey"],
        "actionDraft": action_draft,
        "dashboardDraft": dashboard_draft,
        "dashboardCandidate": candidate,
    }


def source_pipeline_contract() -> dict[str, Any]:
    return build_source_pipeline_contract()


def core_semantic_runtime() -> dict[str, Any]:
    return build_core_semantic_runtime()


def ontology_snapshot(connection: sqlite3.Connection) -> dict[str, Any]:
    workspace_id = active_workspace_id(connection)
    tables = rows_to_dicts(
        connection.execute(
            "SELECT table_key, display_name, row_count, column_count FROM table_registry WHERE workspace_id = ? ORDER BY table_key",
            (workspace_id,),
        )
    )
    metrics = rows_to_dicts(
        connection.execute(
            """
            SELECT metric_key, label, table_key, measure, aggregation, dimension
            FROM metric_definitions
            WHERE workspace_id = ?
            ORDER BY metric_key
            LIMIT 12
            """,
            (workspace_id,),
        )
    )
    relationships = rows_to_dicts(
        connection.execute(
            """
            SELECT relation_key, name, left_table_key, right_table_key, left_field, right_field, confidence
            FROM relationships
            WHERE workspace_id = ?
            ORDER BY relation_key
            """,
            (workspace_id,),
        )
    )
    return {
        "version": 1,
        "objects": tables,
        "functions": metrics,
        "links": relationships,
        "actions": ["dashboard.create", "dashboard.copy", "dashboard.rename", "dashboard.delete", "dashboard.widget.add", "dashboard.filter.add", "import.commit", "relationship.save", "index.create", "formula.save", "view.save", "metric.add", "semantic.set"],
        "evidenceFiles": ["source-profile", "field-semantics", "metric-sql-plan", "query-runtime"],
    }


def normalize_match_text(value: str) -> str:
    return re.sub(r"[\s_\\/\-:：，,。.!！?？'\"“”‘’]+", "", value.lower())


def dashboard_mention_candidates(prompt: str) -> list[str]:
    candidates: list[str] = []
    for match in re.finditer(r"([\u4e00-\u9fffA-Za-z0-9_ -]{1,32}(?:仪表盘|看板|dashboard))", prompt, re.IGNORECASE):
        if prompt[match.end():].lstrip().startswith("组件"):
            continue
        candidate = match.group(1).strip()
        candidate = re.sub(r"^(在|给|向|把|为|往|到|请|帮我|增加|新增|添加|创建|生成|新建|做|一个|一张)+", "", candidate).strip()
        candidate = re.sub(r"^(?:(?:please|help me|add|insert|create|generate|build|draft|new|make|a|an|the|one)\s+)+", "", candidate, flags=re.IGNORECASE).strip()
        generic_dashboard_mentions = {
            "dashboard",
            "business dashboard",
            "executive dashboard",
            "operating dashboard",
            "operation dashboard",
            "analysis dashboard",
            "analytics dashboard",
            "仪表盘",
            "看板",
            "经营看板",
            "经营仪表盘",
        }
        if candidate and candidate.lower() not in generic_dashboard_mentions:
            candidates.append(candidate)
    return candidates


def select_dashboard(dashboards: list[dict[str, Any]], prompt: str, wants_dashboard: bool) -> tuple[dict[str, Any] | None, str]:
    normalized_prompt = normalize_match_text(prompt)
    default_aliases = ["默认看板", "默认仪表盘", "defaultdashboard", "default"]
    if any(alias in normalized_prompt for alias in default_aliases):
        default_dashboard = next((dashboard for dashboard in dashboards if str(dashboard.get("dashboard_key") or "") == "default"), None)
        if default_dashboard:
            return default_dashboard, "explicit"
    for dashboard in dashboards:
        keys = [
            str(dashboard.get("dashboard_key") or ""),
            str(dashboard.get("name") or ""),
        ]
        if any(key and normalize_match_text(key) in normalized_prompt for key in keys):
            return dashboard, "explicit"
    mentions = dashboard_mention_candidates(prompt)
    if mentions and wants_dashboard:
        return None, "missing"
    return (dashboards[0] if dashboards and wants_dashboard else None), ("fallback" if dashboards and wants_dashboard else "missing")


def dashboard_operation_name_from_prompt(prompt: str, op: str, current_name: str = "") -> str:
    if op == "delete":
        return ""
    patterns = [
        r"(?:复制|拷贝|重命名|改名).{0,48}(?:为|成|叫|命名为)\s*([\u4e00-\u9fffA-Za-z0-9_ -]{2,36})",
        r"(?:copy|duplicate|rename).{0,80}\b(?:as|to|named)\s+([A-Za-z0-9_ -]{2,40})",
    ]
    for pattern in patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            value = match.group(1).strip(" ，,。.!！?？")
            if value:
                return value
    if op == "copy" and current_name:
        return f"{current_name} 副本"
    return ""


def resolve_prompt_dashboard_operation(
    connection: sqlite3.Connection,
    selected_dashboard: dict[str, Any] | None,
    dashboard_confidence: str,
    prompt: str,
) -> tuple[dict[str, Any] | None, str]:
    op = dashboard_operation_from_prompt(prompt)
    if not op or not selected_dashboard:
        return None, "missing"
    if op in {"rename", "delete"} and dashboard_confidence != "explicit":
        return None, "missing"
    name = dashboard_operation_name_from_prompt(prompt, op, str(selected_dashboard.get("name") or ""))
    if op in {"copy", "rename"} and not name:
        return None, "missing"
    try:
        proposed = build_dashboard_operation_plan(
            connection,
            op,
            str(selected_dashboard["dashboard_key"]),
            name,
            str(selected_dashboard.get("default_table_key") or ""),
            str(selected_dashboard["dashboard_key"]),
        )
    except ValueError:
        return None, "missing"
    proposed["dashboardSelectionConfidence"] = dashboard_confidence
    return proposed, dashboard_confidence


def select_index_field(connection: sqlite3.Connection, table_key: str, prompt: str) -> tuple[str | None, str, dict[str, Any] | None]:
    registry = resolve_table_registry(connection, table_key)
    columns = table_columns(connection, registry["physical_table"])
    normalized_prompt = normalize_match_text(prompt)
    for column in columns:
        if normalize_match_text(column) in normalized_prompt:
            recommendations = recommend_indexes_for_table(connection, registry, 100)
            recommendation = next((item for item in recommendations if item["field"] == column), None)
            return column, "explicit", recommendation
    recommendations = recommend_indexes_for_table(connection, registry, 12)
    if recommendations:
        return str(recommendations[0]["field"]), "recommended", recommendations[0]
    return (columns[0] if columns else None), "fallback", None


def table_is_mentioned(table: dict[str, Any], prompt: str) -> bool:
    normalized_prompt = normalize_match_text(prompt)
    keys = [str(table.get("table_key") or ""), str(table.get("display_name") or "")]
    return any(key and normalize_match_text(key) in normalized_prompt for key in keys)


def recommendation_matches_tables(recommendation: dict[str, Any], left_table: str, right_table: str) -> bool:
    return (
        recommendation.get("leftTableKey") == left_table
        and recommendation.get("rightTableKey") == right_table
    ) or (
        recommendation.get("leftTableKey") == right_table
        and recommendation.get("rightTableKey") == left_table
    )


def select_relationship_action(connection: sqlite3.Connection, tables: list[dict[str, Any]], prompt: str) -> tuple[dict[str, Any] | None, str]:
    recommendations = recommend_relationships_for_connection(connection, 12)
    mentioned_tables = [table for table in tables if table_is_mentioned(table, prompt)]
    normalized_prompt = normalize_match_text(prompt)
    if len(mentioned_tables) >= 2:
        left_table = str(mentioned_tables[0]["table_key"])
        right_table = str(mentioned_tables[1]["table_key"])
        left_registry = resolve_table_registry(connection, left_table)
        right_registry = resolve_table_registry(connection, right_table)
        left_columns = table_columns(connection, left_registry["physical_table"])
        right_columns = table_columns(connection, right_registry["physical_table"])
        common_columns = [column for column in left_columns if column in right_columns]
        explicit_common = next((column for column in common_columns if normalize_match_text(column) in normalized_prompt), None)
        matching_recommendation = next(
            (
                item for item in recommendations
                if recommendation_matches_tables(item, left_table, right_table)
                and (
                    not explicit_common
                    or any(
                        isinstance(mapping, dict)
                        and str(mapping.get("leftField") or "") == explicit_common
                        and str(mapping.get("rightField") or "") == explicit_common
                        for mapping in item.get("fieldMappings") or []
                    )
                )
            ),
            None,
        )
        if explicit_common:
            return {
                "leftTable": left_table,
                "rightTable": right_table,
                "leftField": explicit_common,
                "rightField": explicit_common,
                "joinType": str((matching_recommendation or {}).get("joinType") or "left"),
                "recommendation": matching_recommendation,
            }, "explicit"
        if matching_recommendation:
            mapping = (matching_recommendation.get("fieldMappings") or [{}])[0]
            if isinstance(mapping, dict):
                left_field = str(mapping.get("leftField") or "")
                right_field = str(mapping.get("rightField") or "")
                for candidate in matching_recommendation.get("fieldMappings") or []:
                    if not isinstance(candidate, dict):
                        continue
                    candidate_left = str(candidate.get("leftField") or "")
                    candidate_right = str(candidate.get("rightField") or "")
                    if candidate_left and normalize_match_text(candidate_left) in normalized_prompt:
                        left_field = candidate_left
                        right_field = candidate_right or candidate_left
                        break
                if left_field and right_field:
                    return {
                        "leftTable": left_table,
                        "rightTable": right_table,
                        "leftField": left_field,
                        "rightField": right_field,
                        "joinType": str(matching_recommendation.get("joinType") or "left"),
                        "recommendation": matching_recommendation,
                    }, "explicit"
        selected_field = common_columns[0] if common_columns else ""
        if selected_field:
            return {
                "leftTable": left_table,
                "rightTable": right_table,
                "leftField": selected_field,
                "rightField": selected_field,
                "joinType": "left",
                "recommendation": matching_recommendation,
            }, "explicit"
    if recommendations:
        recommendation = recommendations[0]
        mapping = (recommendation.get("fieldMappings") or [{}])[0]
        if isinstance(mapping, dict):
            return {
                "leftTable": str(recommendation.get("leftTableKey") or ""),
                "rightTable": str(recommendation.get("rightTableKey") or ""),
                "leftField": str(mapping.get("leftField") or ""),
                "rightField": str(mapping.get("rightField") or ""),
                "joinType": str(recommendation.get("joinType") or "left"),
                "recommendation": recommendation,
            }, "recommended"
    return None, "missing"


IMPORT_FILE_PATTERN = re.compile(r"(?:[A-Za-z]:[^\s\"'<>|]+\.(?:csv|tsv|xlsx|xls)|[A-Za-z0-9_.\-\\/\\u4e00-\\u9fff]+\.(?:csv|tsv|xlsx|xls))", re.IGNORECASE)


def resolve_prompt_import_file(prompt: str) -> tuple[Path | None, str]:
    candidates: list[str] = []
    for match in IMPORT_FILE_PATTERN.finditer(prompt):
        candidates.append(match.group(0).strip("，。,.；;：:）)]}"))
    for candidate in candidates:
        path = Path(candidate)
        possible_paths = [path]
        if not path.is_absolute():
            possible_paths = [ROOT / path]
        for possible_path in possible_paths:
            if possible_path.exists() and possible_path.is_file():
                return possible_path.resolve(), "explicit"
    return None, "missing"


def import_mode_from_prompt(prompt: str) -> str:
    lower = prompt.lower()
    if any(token in lower for token in ["merge", "合并", "追加", "更新已有", "upsert"]):
        return "merge"
    if any(token in lower for token in ["replace", "替换", "覆盖表"]):
        return "replace"
    return "create"


FORMULA_FUNCTION_PATTERN = re.compile(r"\b(SAFE_DIVIDE|SUM|AVG|MIN|MAX|COUNT|COUNT_DISTINCT|ABS|ROUND|COALESCE|CONCAT|IF)\s*\(", re.IGNORECASE)


def extract_formula_expression_from_prompt(prompt: str) -> str:
    match = FORMULA_FUNCTION_PATTERN.search(prompt)
    if not match:
        return ""
    start = match.start()
    depth = 0
    opened = False
    end = start
    for index, char in enumerate(prompt[start:], start=start):
        if char == "(":
            depth += 1
            opened = True
        elif char == ")":
            depth -= 1
            if opened and depth == 0:
                end = index + 1
                break
    if end <= start:
        return ""
    return prompt[start:end].strip("，。,.；;：: ")


def default_formula_dimension(connection: sqlite3.Connection, table_key: str, prompt: str) -> str:
    registry = resolve_table_registry(connection, table_key)
    columns = table_columns(connection, registry["physical_table"])
    normalized_prompt = normalize_match_text(prompt)
    workspace_id = active_workspace_id(connection)
    semantic_roles = {
        str(row["field_name"]): str(row["role"] or "")
        for row in connection.execute(
            "SELECT field_name, role FROM field_semantics WHERE table_key = ? AND workspace_id = ?",
            (table_key, workspace_id),
        ).fetchall()
    }
    for column in columns:
        normalized_column = normalize_match_text(column)
        if normalized_column and normalized_column in normalized_prompt and semantic_roles.get(column) in {"dimension", "status", "event_time", "identity_key"}:
            return column
    return ""


def resolve_prompt_formula_action(
    connection: sqlite3.Connection,
    selected_table: dict[str, Any] | None,
    prompt: str,
) -> tuple[dict[str, Any] | None, str]:
    if not selected_table:
        return None, "missing"
    table_key = str(selected_table["table_key"])
    registry = resolve_table_registry(connection, table_key)
    lower = prompt.lower()
    explicit_expression = extract_formula_expression_from_prompt(prompt)
    name = "Agent 公式指标"
    expression = explicit_expression
    confidence = "explicit" if explicit_expression else "missing"
    if explicit_expression:
        label_match = re.search(r"(?:保存|创建|新增|定义|add|save)?\s*([\u4e00-\u9fffA-Za-z0-9_\- ]{2,24})\s*(?:公式|formula|指标)", prompt, re.IGNORECASE)
        if label_match:
            name = label_match.group(1).strip() or name
    if not expression:
        return None, "missing"
    try:
        proposed = build_formula_save_plan(
            connection,
            table_key,
            name,
            expression,
            "row" if any(token in lower for token in ["row", "行级", "计算字段"]) else "aggregate",
            default_formula_dimension(connection, table_key, prompt),
            "",
            "auto",
            f"Agent draft from prompt: {prompt[:120]}",
            "",
        )
    except (FormulaError, ValueError):
        return None, "missing"
    return proposed, confidence


def metric_label_from_prompt(prompt: str, measure: str, aggregation: str) -> str:
    label_match = re.search(r"(?:新增|添加|创建|定义|保存|做成|add|create|define|save)\s*([\u4e00-\u9fffA-Za-z0-9_\- ]{2,32})\s*(?:指标|metric|kpi)", prompt, re.IGNORECASE)
    if label_match:
        label = label_match.group(1).strip(" ，,。.")
        label = re.sub(r"^(一个|一项|the|a|an)\s*", "", label, flags=re.IGNORECASE).strip()
        if label and label not in {"指标", "metric", "kpi"}:
            return label
    aggregation_label = {
        "sum": "合计",
        "avg": "平均值",
        "count": "计数",
        "count-distinct": "去重计数",
        "max": "最大值",
        "min": "最小值",
    }.get(aggregation, aggregation)
    return f"{measure} {aggregation_label}" if measure != "*" else f"记录数 {aggregation_label}"


def resolve_prompt_metric_action(
    connection: sqlite3.Connection,
    selected_table: dict[str, Any] | None,
    prompt: str,
) -> tuple[dict[str, Any] | None, str]:
    if not selected_table:
        return None, "missing"
    table_key = str(selected_table["table_key"])
    measure, measure_confidence = select_metric_field_from_prompt(connection, table_key, prompt)
    aggregation = aggregation_from_metric_prompt(prompt, measure)
    dimension, dimension_confidence = select_metric_dimension_from_prompt(connection, table_key, prompt, measure)
    label = metric_label_from_prompt(prompt, measure, aggregation)
    try:
        proposed = build_metric_add_plan(
            connection,
            table_key,
            label,
            measure,
            aggregation,
            dimension,
            "",
            [],
            "auto",
            f"Agent metric draft from prompt: {prompt[:120]}",
            "",
        )
    except ValueError:
        return None, "missing"
    proposed["measureSelectionConfidence"] = measure_confidence
    proposed["dimensionSelectionConfidence"] = dimension_confidence
    return proposed, "explicit" if measure_confidence == "explicit" else "recommended"


def widget_type_from_prompt(prompt: str) -> tuple[str, str]:
    lower = prompt.lower()
    if any(token in prompt for token in ["指标卡", "卡片", "指标组件"]) or any(token in lower for token in ["metric card", "kpi card"]):
        return "metric", "explicit"
    if any(token in prompt for token in ["折线图", "趋势图", "趋势"]) or any(token in lower for token in ["line chart", "trend"]):
        return "line", "explicit"
    if any(token in prompt for token in ["饼图", "环图", "占比"]) or any(token in lower for token in ["pie chart", "donut"]):
        return "pie", "explicit"
    if any(token in prompt for token in ["表格", "明细表"]) or any(token in lower for token in ["table", "detail grid"]):
        return "table", "explicit"
    if any(token in prompt for token in ["筛选器", "切片器", "筛选组件"]) or any(token in lower for token in ["slicer", "filter control"]):
        return "slicer", "explicit"
    if any(token in prompt for token in ["柱状图", "条形图", "排行", "排名"]) or any(token in lower for token in ["bar chart", "ranking"]):
        return "bar", "explicit"
    return "bar", "recommended"


def widget_title_from_prompt(prompt: str, widget_type: str, measure: str, dimension: str) -> str:
    patterns = [
        r"(?:标题|命名为|叫)\s*([\u4e00-\u9fffA-Za-z0-9_ -]{2,36})",
        r"(?:title|named)\s+([A-Za-z0-9_ -]{2,40})",
    ]
    for pattern in patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            value = match.group(1).strip(" ，,。.!！?？")
            if value:
                return value
    if widget_type == "metric":
        return f"{measure if measure != '*' else '记录数'} 指标卡"
    if widget_type in {"bar", "pie"} and measure and dimension:
        return f"{dimension} by {measure}"
    if widget_type == "line" and measure:
        return f"{measure} trend"
    if widget_type == "table":
        return "明细表"
    if widget_type == "slicer":
        return f"{dimension or '字段'} 筛选器"
    return f"{measure or dimension or '分析'} 图表"


def widget_candidate_fields(
    connection: sqlite3.Connection,
    table_key: str,
    roles: list[str],
    limit: int = 5,
    allow_untyped_fallback: bool = True,
) -> list[str]:
    candidates: list[str] = []
    for role in roles:
        for field in field_names_by_role(connection, table_key, role):
            if field and not str(field).startswith("__") and field not in candidates:
                candidates.append(field)
            if len(candidates) >= limit:
                return candidates
    if candidates or not allow_untyped_fallback:
        return candidates
    registry = resolve_table_registry(connection, table_key)
    for field in table_columns(connection, registry["physical_table"]):
        if field and not str(field).startswith("__") and field not in candidates:
            candidates.append(field)
        if len(candidates) >= limit:
            break
    return candidates


def build_widget_clarification_action(
    connection: sqlite3.Connection,
    dashboard_key: str,
    table_key: str,
    widget_type: str,
    measure: str,
    dimension: str,
    widget_type_confidence: str,
    measure_confidence: str,
    dimension_confidence: str,
) -> dict[str, Any]:
    candidate_measures = widget_candidate_fields(connection, table_key, ["measure"], 5, allow_untyped_fallback=False)
    candidate_dimensions = widget_candidate_fields(connection, table_key, ["event_time", "dimension", "status"], 5, allow_untyped_fallback=False)
    return {
        "needsClarification": True,
        "dashboardKey": dashboard_key,
        "widgetType": widget_type,
        "tableKey": table_key,
        "measure": measure,
        "dimension": dimension,
        "question": localized_value(
            "我还不能确定这个图表应该用哪个指标和维度。请指定一个指标，必要时再指定按什么分组。",
            "I cannot safely determine the chart measure and dimension yet. Specify a measure, and optionally a grouping dimension.",
        ),
        "candidateMeasures": candidate_measures,
        "candidateDimensions": candidate_dimensions,
        "widgetTypeSelectionConfidence": widget_type_confidence,
        "measureSelectionConfidence": measure_confidence,
        "dimensionSelectionConfidence": dimension_confidence,
    }


def widget_needs_clarification(widget_type: str, widget_type_confidence: str, measure_confidence: str, dimension_confidence: str) -> bool:
    if widget_type_confidence != "explicit":
        return True
    if measure_confidence in {"fallback", "missing"}:
        return True
    if widget_type in {"bar", "pie", "line", "slicer"} and dimension_confidence in {"fallback", "missing", "none"}:
        return True
    return False


def resolve_prompt_widget_action(
    connection: sqlite3.Connection,
    selected_dashboard: dict[str, Any] | None,
    dashboard_confidence: str,
    selected_table: dict[str, Any] | None,
    table_confidence: str,
    prompt: str,
) -> tuple[dict[str, Any] | None, str]:
    if selected_dashboard and dashboard_confidence not in {"explicit", "fallback"}:
        return None, "missing"
    dashboard_key = str(selected_dashboard["dashboard_key"]) if selected_dashboard else ""
    table_key = str(selected_table["table_key"]) if selected_table else ""
    if table_confidence != "explicit" and selected_dashboard and selected_dashboard.get("default_table_key"):
        table_key = str(selected_dashboard["default_table_key"])
    if not table_key:
        return None, "missing"
    widget_type, widget_type_confidence = widget_type_from_prompt(prompt)
    measure, measure_confidence = select_metric_field_from_prompt(connection, table_key, prompt)
    dimension, dimension_confidence = select_metric_dimension_from_prompt(connection, table_key, prompt, measure)
    if widget_type == "line" and not dimension:
        date_fields = [field for field in field_names_by_role(connection, table_key, "event_time")]
        if date_fields:
            dimension, dimension_confidence = date_fields[0], "recommended"
    aggregation = aggregation_from_metric_prompt(prompt, measure)
    if widget_needs_clarification(widget_type, widget_type_confidence, measure_confidence, dimension_confidence):
        return build_widget_clarification_action(
            connection,
            dashboard_key,
            table_key,
            widget_type,
            measure,
            dimension,
            widget_type_confidence,
            measure_confidence,
            dimension_confidence,
        ), "missing"
    if widget_type in {"table", "slicer", "text"} and not any(token in prompt.lower() for token in SAFE_AGGREGATIONS):
        aggregation = "count"
    title = widget_title_from_prompt(prompt, widget_type, measure, dimension)
    options: dict[str, Any] = {
        "tableKey": table_key,
        "title": title,
        "dimension": "" if widget_type == "metric" else dimension,
        "measure": measure,
        "aggregation": aggregation,
        "topN": 1 if widget_type == "metric" else (100 if widget_type == "table" else 12),
        "valueFormat": "auto",
        "sourceAction": "agent.widget.add",
    }
    if widget_type == "table":
        registry = resolve_table_registry(connection, table_key)
        options["columns"] = table_columns(connection, registry["physical_table"])[:6]
    proposed = None
    if dashboard_key:
        try:
            proposed = build_widget_proposal(connection, dashboard_key, widget_type, options)
        except ValueError:
            return None, "missing"
    return {
        "dashboardKey": dashboard_key,
        "widgetType": widget_type,
        "tableKey": table_key,
        "title": title,
        "measure": measure,
        "dimension": dimension,
        "aggregation": aggregation,
        "options": options,
        "proposedWidget": proposed,
        "widgetTypeSelectionConfidence": widget_type_confidence,
        "measureSelectionConfidence": measure_confidence,
        "dimensionSelectionConfidence": dimension_confidence,
    }, "explicit" if widget_type_confidence == "explicit" else "recommended"


def filter_operator_from_prompt(prompt: str) -> tuple[str, str]:
    lower = prompt.lower()
    if any(token in prompt for token in ["包含", "含有"]) or "contains" in lower:
        return "contains", "explicit"
    if any(token in prompt for token in ["不等于", "不是", "排除"]) or any(token in lower for token in ["not equals", "not equal", "!="]):
        return "notEquals", "explicit"
    if any(token in prompt for token in ["大于等于", "不少于"]) or ">=" in lower:
        return "gte", "explicit"
    if any(token in prompt for token in ["小于等于", "不超过"]) or "<=" in lower:
        return "lte", "explicit"
    if any(token in prompt for token in ["大于", "超过"]) or ">" in lower:
        return "gt", "explicit"
    if any(token in prompt for token in ["小于", "低于"]) or "<" in lower:
        return "lt", "explicit"
    if any(token in prompt for token in ["为空", "空值"]) or " is empty" in lower:
        return "empty", "explicit"
    if any(token in prompt for token in ["不为空", "非空"]) or "not empty" in lower:
        return "notEmpty", "explicit"
    return "equals", "fallback"


def select_dashboard_filter_field(connection: sqlite3.Connection, dashboard_key: str, prompt: str) -> tuple[str, str]:
    dashboard, _layout, _filters, fields = dashboard_filters_snapshot(connection, dashboard_key)
    available = [str(item.get("field_name") or "") for item in fields if item.get("field_name")]
    normalized_prompt = normalize_match_text(prompt)
    for field in available:
        if normalize_match_text(field) in normalized_prompt:
            return field, "explicit"
    for item in fields:
        if item.get("usage") == "filterable":
            return str(item["field_name"]), "fallback"
    return (available[0] if available else ""), "missing"


def dashboard_filter_value_from_prompt(connection: sqlite3.Connection, dashboard_key: str, field: str, operator: str, prompt: str) -> tuple[str, str]:
    if not filter_value_required(operator):
        return "", "none"
    escaped = re.escape(field)
    patterns = [
        rf"{escaped}\s*(?:=|等于|为|是|equals?)\s*([\u4e00-\u9fffA-Za-z0-9_.@\-]+)",
        rf"{escaped}\s*(?:包含|含有|contains?)\s*([\u4e00-\u9fffA-Za-z0-9_.@\-]+)",
        rf"(?:只看|筛选|过滤|限定).{{0,24}}{escaped}.{{0,12}}([\u4e00-\u9fffA-Za-z0-9_.@\-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            value = match.group(1).strip(" ，,。.!！?？")
            if value and normalize_match_text(value) != normalize_match_text(field):
                return value, "explicit"
    dashboard, _layout, _filters, _fields = dashboard_filters_snapshot(connection, dashboard_key)
    registry = registry_for_table(connection, str(dashboard["default_table_key"] or ""))
    if registry:
        with open_validated_duckdb_query(DUCKDB_PATH, [replica_expectation(registry)]) as analysis_connection:
            rows = cursor_rows(analysis_connection.execute(
                f"SELECT DISTINCT {quote_identifier(field)} AS value FROM {quote_identifier(registry['physical_table'])} WHERE {quote_identifier(field)} IS NOT NULL LIMIT 50"
            ))
        normalized_prompt = normalize_match_text(prompt)
        for row in rows:
            value = str(row["value"])
            if value and normalize_match_text(value) in normalized_prompt:
                return value, "recommended"
    return "", "missing"


def resolve_prompt_dashboard_filter_action(
    connection: sqlite3.Connection,
    selected_dashboard: dict[str, Any] | None,
    dashboard_confidence: str,
    prompt: str,
) -> tuple[dict[str, Any] | None, str]:
    if not selected_dashboard or dashboard_confidence != "explicit":
        return None, "missing"
    dashboard_key = str(selected_dashboard["dashboard_key"])
    field, field_confidence = select_dashboard_filter_field(connection, dashboard_key, prompt)
    operator, operator_confidence = filter_operator_from_prompt(prompt)
    value, value_confidence = dashboard_filter_value_from_prompt(connection, dashboard_key, field, operator, prompt) if field else ("", "missing")
    if not field or (filter_value_required(operator) and not value):
        return None, "missing"
    try:
        plan = build_dashboard_filter_add_plan(connection, dashboard_key, field, operator, value)
    except ValueError:
        return None, "missing"
    return {
        "dashboardKey": dashboard_key,
        "field": field,
        "operator": operator,
        "value": value,
        "filter": plan["proposed"],
        "filtersAfter": plan["filtersAfter"],
        "fieldSelectionConfidence": field_confidence,
        "operatorSelectionConfidence": operator_confidence,
        "valueSelectionConfidence": value_confidence,
    }, "explicit" if field_confidence == "explicit" and value_confidence in {"explicit", "recommended"} else "recommended"


def semantic_role_from_prompt(prompt: str) -> tuple[str, str]:
    lower = prompt.lower()
    if any(token in prompt for token in ["关联键", "主键", "唯一键", "身份键", "连接键"]) or any(token in lower for token in ["identity_key", "identifier", "join key", "primary key"]):
        return "identity_key", "explicit"
    if any(token in prompt for token in ["时间字段", "日期字段", "事件时间", "日期", "时间"]) or any(token in lower for token in ["event_time", "date field", "time field"]):
        return "event_time", "explicit"
    if any(token in prompt for token in ["指标字段", "数值字段", "金额字段", "度量", "指标", "可聚合"]) or any(token in lower for token in ["measure", "metric", "aggregatable"]):
        return "measure", "explicit"
    if any(token in prompt for token in ["状态字段", "状态"]) or "status" in lower:
        return "status", "explicit"
    if any(token in prompt for token in ["维度", "分类", "分组", "可分组"]) or any(token in lower for token in ["dimension", "groupable"]):
        return "dimension", "explicit"
    return "dimension", "missing"


def semantic_usage_tokens_for_role(role: str, prompt: str) -> list[str]:
    lower = prompt.lower()
    usages: list[str] = []
    if any(token in prompt for token in ["可筛选", "筛选"]) or "filter" in lower:
        usages.append("filterable")
    if any(token in prompt for token in ["可排序", "排序"]) or "sort" in lower:
        usages.append("sortable")
    if any(token in prompt for token in ["可分组", "分组"]) or "group" in lower:
        usages.append("groupable")
    if any(token in prompt for token in ["可聚合", "聚合"]) or "aggregate" in lower:
        usages.append("aggregatable")
    if any(token in prompt for token in ["可关联", "关联键", "连接键"]) or "join" in lower:
        usages.append("joinable")
    if not usages:
        default_usage = primary_usage_from_object(semantic_usage_object(role), role)
        usages.append(default_usage)
    return sorted(set(usages))


def select_semantic_field(connection: sqlite3.Connection, table_key: str, prompt: str) -> tuple[str, str]:
    registry = resolve_table_registry(connection, table_key)
    columns = table_columns(connection, registry["physical_table"])
    normalized_prompt = normalize_match_text(prompt)
    for column in columns:
        if normalize_match_text(column) in normalized_prompt:
            return column, "explicit"
    workspace_id = active_workspace_id(connection)
    rows = rows_to_dicts(
        connection.execute(
            """
            SELECT field_name, role
            FROM field_semantics
            WHERE table_key = ? AND workspace_id = ?
            ORDER BY confidence DESC, field_name
            """,
            (table_key, workspace_id),
        )
    )
    role, role_confidence = semantic_role_from_prompt(prompt)
    if role_confidence != "missing":
        for row in rows:
            if row.get("role") == normalize_semantic_role(role):
                return str(row["field_name"]), "recommended"
    return "", "missing"


def resolve_prompt_semantic_action(
    connection: sqlite3.Connection,
    selected_table: dict[str, Any] | None,
    prompt: str,
) -> tuple[dict[str, Any] | None, str]:
    if not selected_table:
        return None, "missing"
    table_key = str(selected_table["table_key"])
    field, field_confidence = select_semantic_field(connection, table_key, prompt)
    role, role_confidence = semantic_role_from_prompt(prompt)
    if not field or role_confidence == "missing":
        return None, "missing"
    try:
        proposed = build_semantic_set_plan(
            connection,
            table_key,
            field,
            role,
            semantic_usage_tokens_for_role(role, prompt),
            [],
            1.0 if field_confidence == "explicit" and role_confidence == "explicit" else 0.86,
            f"Agent semantic draft from prompt: {prompt[:120]}",
        )
    except ValueError:
        return None, "missing"
    proposed["fieldSelectionConfidence"] = field_confidence
    proposed["roleSelectionConfidence"] = role_confidence
    return proposed, field_confidence if role_confidence == "explicit" else "missing"


def view_name_from_prompt(prompt: str, table_name: str) -> str:
    patterns = [
        r"(?:保存为|保存成|存成|命名为|叫|名称为)\s*([\u4e00-\u9fffA-Za-z0-9_ -]{2,40})",
        r"(?:save|create).{0,80}\b(?:as|named)\s+([A-Za-z0-9_ -]{2,40})",
    ]
    for pattern in patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            value = match.group(1).strip(" ，,。.!！?？")
            if value:
                return value
    return f"{table_name} 常用视图"


def view_config_from_prompt(connection: sqlite3.Connection, table_key: str, prompt: str) -> tuple[dict[str, Any], str]:
    registry = resolve_table_registry(connection, table_key)
    columns = table_columns(connection, registry["physical_table"])
    normalized_prompt = normalize_match_text(prompt)
    workspace_id = active_workspace_id(connection)
    default_view = connection.execute(
        "SELECT config_json FROM saved_views WHERE table_key = ? AND workspace_id = ? ORDER BY is_default DESC, sort_order, created_at LIMIT 1",
        (table_key, workspace_id),
    ).fetchone()
    default_config = parse_json_object(default_view["config_json"], {}) if default_view else {}
    selected_columns = list_from_value(default_config.get("columns")) or columns[:6]
    explicit_columns = [column for column in columns if normalize_match_text(column) in normalized_prompt]
    if explicit_columns:
        selected_columns = explicit_columns[:8]
    filters: list[dict[str, Any]] = []
    for column in columns:
        escaped = re.escape(column)
        match = re.search(rf"{escaped}\s*(?:=|等于|为|是|equals?)\s*([\u4e00-\u9fffA-Za-z0-9_.@\-]+)", prompt, re.IGNORECASE)
        if match:
            filters.append({"field": column, "operator": "equals", "value": match.group(1).strip(" ，,。.!！?？")})
            continue
        contains_match = re.search(rf"{escaped}\s*(?:包含|含有|contains?)\s*([\u4e00-\u9fffA-Za-z0-9_.@\-]+)", prompt, re.IGNORECASE)
        if contains_match:
            filters.append({"field": column, "operator": "contains", "value": contains_match.group(1).strip(" ，,。.!！?？")})
    sort: list[dict[str, str]] = []
    sort_match = re.search(r"(?:按|按照|by)\s*([\u4e00-\u9fffA-Za-z0-9_\- ]{1,40})\s*(?:排序|升序|降序|倒序|sort|order)?", prompt, re.IGNORECASE)
    if sort_match:
        sort_text = normalize_match_text(sort_match.group(1))
        for column in columns:
            if normalize_match_text(column) in sort_text:
                direction = "desc" if any(token in prompt.lower() for token in ["desc", "descending"]) or any(token in prompt for token in ["降序", "倒序", "最新", "最高"]) else "asc"
                sort.append({"field": column, "direction": direction})
                break
    if not sort:
        sort = [item for item in (default_config.get("sort") or []) if isinstance(item, dict)]
    return {
        "mode": "detail",
        "columns": selected_columns,
        "filters": filters,
        "sort": sort,
        "search": "",
    }, "explicit" if filters or explicit_columns or sort_match else "fallback"


def resolve_prompt_view_action(
    connection: sqlite3.Connection,
    selected_table: dict[str, Any] | None,
    prompt: str,
) -> tuple[dict[str, Any] | None, str]:
    if not selected_table:
        return None, "missing"
    table_key = str(selected_table["table_key"])
    table_name = str(selected_table.get("display_name") or table_key)
    config, confidence = view_config_from_prompt(connection, table_key, prompt)
    name = view_name_from_prompt(prompt, table_name)
    try:
        proposed = build_save_view_plan(
            connection,
            table_key,
            name,
            config,
            "",
            "Agent 保存的筛选口径",
            "agent",
            1,
        )
    except ValueError:
        return None, "missing"
    proposed["viewSelectionConfidence"] = confidence
    return proposed, confidence


def localized_value(zh: str, en: str) -> dict[str, str]:
    return {"zh": zh, "en": en}


def format_answer_number(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number) >= 10000:
        return f"{number / 10000:.2f}w"
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.2f}"


def build_widget_clarification_answer_card(widget_action: dict[str, Any]) -> dict[str, Any]:
    candidate_measures = [str(item) for item in widget_action.get("candidateMeasures", []) if item]
    candidate_dimensions = [str(item) for item in widget_action.get("candidateDimensions", []) if item]
    measure_hint = candidate_measures[0] if candidate_measures else ""
    dimension_hint = candidate_dimensions[0] if candidate_dimensions else ""
    next_actions = [
        localized_value("指定一个数值字段，例如：用数值字段做柱状图", "Specify a numeric field, for example: build a bar chart with a numeric field"),
        localized_value("需要分组时，请明确写出要使用的分类、时间或状态字段", "For grouping, name the category, time, or status field explicitly"),
    ]
    if measure_hint and dimension_hint:
        next_actions.insert(0, localized_value(
            f"可以说：用 {measure_hint} 按 {dimension_hint} 做图表",
            f"You can say: build a chart with {measure_hint} by {dimension_hint}",
        ))
    return {
        "kind": "clarification",
        "title": localized_value("先确认图表字段", "Confirm chart fields first"),
        "summary": widget_action.get("question") or localized_value(
            "我还不能确定要使用的指标或维度，因此不会先创建图表草案。",
            "I cannot safely determine the measure or dimension yet, so no chart draft was created.",
        ),
        "confidence": "missing",
        "metrics": [],
        "rows": [
            {"role": "measure", "field": field} for field in candidate_measures
        ] + [
            {"role": "dimension", "field": field} for field in candidate_dimensions
        ],
        "clarification": {
            "kind": "widget-fields",
            "widgetType": widget_action.get("widgetType"),
            "tableKey": widget_action.get("tableKey"),
            "dashboardKey": widget_action.get("dashboardKey"),
            "candidateMeasures": candidate_measures,
            "candidateDimensions": candidate_dimensions,
        },
        "evidenceRefs": [
            {"type": "table", "tableKey": widget_action.get("tableKey")},
            {"type": "dashboard", "dashboardKey": widget_action.get("dashboardKey")},
        ],
        "nextActions": next_actions,
    }


def build_agent_answer_card(
    connection: sqlite3.Connection,
    prompt: str,
    selected_table: dict[str, Any] | None,
    widget_action: dict[str, Any] | None = None,
    workspace_id: str | None = None,
    intent_frame: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return build_trusted_answer_card(
        connection, prompt, selected_table, widget_action, workspace_id, intent_frame
    )


def merge_receipt_unresolved_with_execution_blockers(
    unresolved: Any,
    execution_plan: Any,
) -> list[Any]:
    """Preserve runtime execution blockers in an Agent query Receipt."""
    result = list(unresolved) if isinstance(unresolved, list) else ([] if unresolved is None else [unresolved])
    plan = execution_plan if isinstance(execution_plan, dict) else {}
    blockers = plan.get("blockers") or []
    if not isinstance(blockers, list):
        blockers = [blockers]
    for blocker in blockers:
        if blocker is not None and blocker not in result:
            result.append(blocker)
    return result


def ask_command(args: argparse.Namespace) -> dict[str, Any]:
    prompt = args.prompt
    business_prompt = str(semantic_query_prompt_directives(prompt)["basePrompt"])
    read_only = getattr(args, "read_only", False)
    intents = resolve_agent_prompt_intents(business_prompt)
    deepseek_configured = bool(os.environ.get("DEEPSEEK_API_KEY"))
    llm_audit = {
        "provider": "deepseek" if deepseek_configured else "deterministic",
        "configured": deepseek_configured,
        "mode": "provider" if deepseek_configured else "deterministic-fallback",
        "serverSideOnly": True,
        "secretExposed": False,
        "contextBoundary": "active-workspace-sourceRun-workbench",
        "fallbackReason": None if deepseek_configured else "DEEPSEEK_API_KEY is not configured; deterministic fallback answered from local BI evidence.",
        "regressionStatus": "provider-ready" if deepseek_configured else "provider-skipped",
    }
    with closing(open_db()) as connection:
        if connection.in_transaction:
            connection.commit()
        workspace_id = str(getattr(args, "workspace", "") or active_workspace_id(connection))
        if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
            raise ValueError(f"Unknown workspace: {workspace_id}")
        parent_run_key = str(getattr(args, "parent_run", "") or "").strip()
        if parent_run_key:
            validate_branch_parent(connection, workspace_id, parent_run_key)
        tables = rows_to_dicts(connection.execute("SELECT table_key, display_name FROM table_registry WHERE workspace_id = ? ORDER BY table_key", (workspace_id,)))
        dashboards = rows_to_dicts(
            connection.execute(
                "SELECT dashboard_key, name, default_table_key FROM dashboards WHERE workspace_id = ? ORDER BY dashboard_key",
                (workspace_id,),
            )
        )
        selected_table, table_confidence = select_agent_table(tables, business_prompt)
        active_domain_pack_context = domain_pack_runtime_context(connection, workspace_id)
        platform_pack_enabled = is_domain_pack_enabled(
            connection,
            workspace_id,
            "platform-commerce",
            "agentKnowledge",
        )
        platform_match = match_platform_knowledge(connection, workspace_id, business_prompt) if platform_pack_enabled else None
        verified_analysis_gap = platform_match is None and requires_verified_analysis_plan(business_prompt)
        if platform_match:
            primary_table_key = str(next(iter(platform_match["roles"].values()))["table_key"])
            selected_table = next((table for table in tables if table["table_key"] == primary_table_key), selected_table)
            table_confidence = "knowledge-rule"
        context_matches = matched_context(
            connection,
            workspace_id,
            business_prompt,
            selected_table["table_key"] if selected_table else None,
        )
        resolution_prompt = " ".join(
            [
                contextualized_prompt(business_prompt, context_matches),
                platform_knowledge_context(platform_match),
            ]
        ).strip()
        selected_dashboard, dashboard_confidence = select_dashboard(
            dashboards,
            business_prompt,
            intents.wants_dashboard or intents.wants_widget,
        )
        semantic_selected_table_key = (
            str(selected_table["table_key"])
            if selected_table and table_confidence in {"explicit", "knowledge-rule"}
            else (
                str(selected_dashboard.get("default_table_key") or "")
                if selected_dashboard and dashboard_confidence == "explicit"
                else ""
            )
        )
        semantic_plan = build_workspace_semantic_plan(
            connection,
            workspace_id,
            prompt,
            selected_table_key=semantic_selected_table_key,
            table_columns=table_columns,
        )
        intent_frame = build_business_intent_frame(business_prompt, semantic_plan=semantic_plan)
        analytical_skill_runtime = analytical_skill_runtime_context(connection, workspace_id)
        business_understanding = build_business_understanding_frame(
            business_prompt,
            intent_frame,
            semantic_plan,
            context_matches,
            analytical_skill_runtime,
            knowledge_match=platform_match,
            enabled_domain_packs=[
                str(item.get("packId") or "")
                for item in active_domain_pack_context.get("enabledDomainPacks") or []
            ],
        )
        intent_frame = apply_business_understanding_to_intent(intent_frame, business_understanding)
        analytical_skill_match = (
            business_understanding.get("skillMatch")
            if isinstance(business_understanding.get("skillMatch"), dict)
            else {}
        )
        workspace_manifest_ref = workspace_planning_binding(connection, workspace_id)
        recall_result = recall_confirmed_plans(
            connection,
            workspace_id=workspace_id,
            prompt=business_prompt,
            explicit_table_key=semantic_selected_table_key or None,
            semantic_plan=semantic_plan,
            context_matches=context_matches,
            planning_binding=workspace_manifest_ref,
            now_iso=now_iso,
        )
        recalled_plans = list(recall_result.get("candidates") or [])
        recall_receipt = recall_result.get("receipt") if isinstance(recall_result.get("receipt"), dict) else None
        recalled_queries = [
            {
                "query_key": item.get("queryKey"),
                "query_receipt_key": item.get("queryReceiptKey"),
                "question": item.get("question"),
                "matchScore": item.get("matchScore"),
                "planMemoryKey": item.get("memoryKey"),
                "matchChannels": item.get("matchChannels") or {},
            }
            for item in recalled_plans
        ]
        semantic_context = build_semantic_context_bundle(
            workspace_id=workspace_id,
            intent_frame=intent_frame,
            semantic_plan=semantic_plan,
            selected_table=selected_table,
            table_selection_confidence=table_confidence,
            context_matches=context_matches,
            recalled_queries=recalled_queries,
            domain_pack_context=active_domain_pack_context,
            knowledge_match=platform_match,
            analytical_skill_match=analytical_skill_match,
            session_context=getattr(args, "session_context", None),
            business_understanding=business_understanding,
            workspace_manifest_ref=workspace_manifest_ref,
            recalled_plans=recalled_plans,
            recall_receipt=recall_receipt,
        )
        clarification = build_agent_clarification(intent_frame, semantic_context, business_understanding)
        business_understanding_blocked = (
            str(business_understanding.get("status") or "ready") == "needs-clarification"
            or bool(business_understanding.get("blockers"))
        )
        semantic_execution = None
        semantic_targets = semantic_plan.get("joinPlan", {}).get("targets") or []
        if platform_match is None and not business_understanding_blocked and semantic_plan["status"] == "ready" and semantic_targets:
            semantic_execution = execute_workspace_semantic_query(
                connection,
                workspace_id,
                prompt,
                selected_table_key=semantic_selected_table_key,
                limit=50,
                table_columns=table_columns,
                quote_identifier=quote_relationship_identifier,
                build_relationship_query=build_relationship_query,
                semantic_plan=semantic_plan,
                intent_frame=intent_frame,
            )
        semantic_execution_blocked = bool(semantic_execution and not semantic_execution.get("executed"))
        semantic_blocked = (
            semantic_plan["status"] in BLOCKING_STATUSES
            or semantic_execution_blocked
        ) and platform_match is None
        single_chart_dashboard_create = intents.wants_widget and selected_dashboard is None
        dashboard_action = None
        dashboard_action_confidence = "missing"
        if intents.wants_dashboard:
            dashboard_action, dashboard_action_confidence = resolve_prompt_dashboard_operation(connection, selected_dashboard, dashboard_confidence, resolution_prompt)
        widget_action = None
        widget_confidence = "missing"
        if intents.wants_widget and not dashboard_action:
            widget_action, widget_confidence = resolve_prompt_widget_action(connection, selected_dashboard, dashboard_confidence, selected_table, table_confidence, resolution_prompt)
        widget_clarification = isinstance(widget_action, dict) and widget_action.get("needsClarification") is True
        actionable_widget_action = None if widget_clarification else widget_action
        dashboard_filter_action = None
        dashboard_filter_confidence = "missing"
        if intents.wants_dashboard_filter and not dashboard_action and not actionable_widget_action:
            dashboard_filter_action, dashboard_filter_confidence = resolve_prompt_dashboard_filter_action(connection, selected_dashboard, dashboard_confidence, resolution_prompt)
        index_field = None
        index_field_confidence = "missing"
        index_recommendation = None
        if intents.wants_index and selected_table:
            index_field, index_field_confidence, index_recommendation = select_index_field(connection, selected_table["table_key"], resolution_prompt)
        relationship_action = None
        relationship_confidence = "missing"
        if intents.wants_relationship:
            relationship_action, relationship_confidence = select_relationship_action(connection, tables, business_prompt)
        import_file = None
        import_confidence = "missing"
        import_mode = "create"
        if intents.wants_import:
            import_file, import_confidence = resolve_prompt_import_file(business_prompt)
            import_mode = import_mode_from_prompt(business_prompt)
        formula_action = None
        formula_confidence = "missing"
        if intents.wants_formula:
            formula_action, formula_confidence = resolve_prompt_formula_action(connection, selected_table, resolution_prompt)
        view_action = None
        view_confidence = "missing"
        if intents.wants_view and not intents.wants_formula:
            view_action, view_confidence = resolve_prompt_view_action(connection, selected_table, resolution_prompt)
        metric_action = None
        metric_confidence = "missing"
        if intents.wants_metric and not intents.wants_formula and not view_action:
            metric_action, metric_confidence = resolve_prompt_metric_action(connection, selected_table, resolution_prompt)
        semantic_action = None
        semantic_confidence = "missing"
        if intents.wants_semantic and not metric_action and not view_action and not actionable_widget_action and not dashboard_filter_action:
            semantic_action, semantic_confidence = resolve_prompt_semantic_action(connection, selected_table, resolution_prompt)
        should_create_draft = should_create_agent_draft(
            intents=intents,
            dashboard_confidence=dashboard_confidence,
            dashboard_action=dashboard_action,
            widget_action=actionable_widget_action,
            dashboard_filter_action=dashboard_filter_action,
            index_field=index_field,
            relationship_action=relationship_action,
            import_file=import_file,
            formula_action=formula_action,
            view_action=view_action,
            metric_action=metric_action,
            semantic_action=semantic_action,
            read_only=read_only,
        )
        if verified_analysis_gap:
            should_create_draft = False
        if semantic_blocked or business_understanding_blocked:
            should_create_draft = False
        action_payload = build_agent_action_payload(
            prompt=business_prompt,
            selected_dashboard=selected_dashboard,
            selected_table=selected_table,
            widget_action=actionable_widget_action,
            dashboard_filter_action=dashboard_filter_action,
            index_field=index_field,
            index_field_confidence=index_field_confidence,
            index_recommendation=index_recommendation,
            relationship_action=relationship_action,
            import_file=import_file,
            import_confidence=import_confidence,
            import_mode=import_mode,
            formula_action=formula_action,
            view_action=view_action,
            metric_action=metric_action,
            semantic_action=semantic_action,
            dashboard_action=dashboard_action,
        )
        action_key = unique_key("draft") if should_create_draft else "read_only_plan"
        action_kind = agent_action_kind(
            intents=intents,
            read_only=read_only,
            index_field=index_field,
            dashboard_action=dashboard_action,
            dashboard_filter_action=dashboard_filter_action,
            widget_action=actionable_widget_action,
            relationship_action=relationship_action,
            import_file=import_file,
            formula_action=formula_action,
            view_action=view_action,
            metric_action=metric_action,
            semantic_action=semantic_action,
        )
        if should_create_draft and action_kind == "dashboard.create":
            dashboard_create_draft = build_agent_dashboard_create_draft(
                connection,
                workspace_id,
                action_payload.get("tableKey"),
                resolution_prompt,
                1 if single_chart_dashboard_create else 8,
                resolved_widget=actionable_widget_action if single_chart_dashboard_create else None,
            )
            action_payload.update(
                {
                    "dashboardKey": "",
                    "dashboardName": dashboard_create_draft["dashboardName"],
                    "defaultTableKey": dashboard_create_draft["defaultTableKey"],
                    "dashboardDraft": dashboard_create_draft,
                }
            )
        action_label = None
        action_evidence: list[dict[str, Any]] = []
        if should_create_draft:
            action_label = "生成单图表草案" if single_chart_dashboard_create else agent_action_label(action_kind, wants_dashboard=intents.wants_dashboard)
            action_evidence = agent_action_evidence(action_kind)
        answer_card = (
            build_agent_answer_card(connection, resolution_prompt, None, None, workspace_id, intent_frame)
            if selected_table is None
            else (
                build_business_understanding_gap(
                    business_prompt,
                    business_understanding,
                    selected_table["table_key"],
                )
                if business_understanding_blocked
                else (
                    execute_platform_knowledge(connection, platform_match)
                    if platform_match
                    else (
                        build_verified_analysis_gap(business_prompt, selected_table["table_key"])
                        if verified_analysis_gap
                        else build_agent_answer_card(connection, resolution_prompt, selected_table, actionable_widget_action, workspace_id, intent_frame)
                    )
                )
            )
        )
        if semantic_execution and semantic_execution.get("executed"):
            relationship_query = semantic_execution["relationshipQuery"]
            semantic_rows = relationship_rows_for_chart_service(relationship_query)
            semantic_runtime = semantic_execution["query"]["runtime"]
            semantic_typed_intent, semantic_coverage = build_semantic_query_contract(
                connection,
                workspace_id=workspace_id,
                intent_frame=intent_frame,
                execution_plan=semantic_execution["executionPlan"],
                relationship_query=relationship_query,
                runtime=semantic_runtime,
                result_rows=semantic_rows,
            )
            semantic_execution["query"] = {
                **semantic_execution["query"],
                "typedIntent": semantic_typed_intent,
                "executionCoverage": semantic_coverage,
                "sourceRunBinding": semantic_typed_intent["sourceRunBinding"],
                "resultState": semantic_coverage["resultState"],
            }
            execution_measure = semantic_execution["executionPlan"]["measure"]
            metric_name = f"{execution_measure['aggregation']}({execution_measure['field']})"
            top_row = semantic_rows[0] if semantic_rows else {}
            top_raw_value = top_row.get("value")
            top_value = None if top_raw_value is None else float(top_raw_value)
            top_label = str(top_row.get("label") or "")
            if top_value is None:
                summary = localized_value(
                    f"{top_label or '当前结果'} 的 {metric_name} 暂无可聚合数据；结果来自已验证关系与固定执行计划。",
                    f"{top_label or 'Current result'} has no data to aggregate for {metric_name}; the result comes from a validated relationship and fixed execution plan.",
                )
                display_value = "无数据 / No data"
            else:
                summary = localized_value(
                    f"{top_label or '当前结果'} 的 {metric_name} 为 {format_answer_number(top_value)}；结果来自已验证关系与固定执行计划。",
                    f"{top_label or 'Current result'} has {metric_name} {format_answer_number(top_value)} from a validated relationship and fixed execution plan.",
                )
                display_value = format_answer_number(top_value)
            answer_card = {
                "kind": "semantic-relationship-analysis",
                "title": localized_value("受控跨表分析", "Controlled cross-table analysis"),
                "summary": summary,
                "confidence": "validated-execution-plan",
                "metrics": [{
                    "label": localized_value(metric_name, metric_name),
                    "value": display_value,
                    "rawValue": top_value,
                    "unit": "value",
                }],
                "rows": semantic_rows,
                "query": semantic_execution["query"],
                "executionPlan": semantic_execution["executionPlan"],
                "evidenceRefs": [
                    {"type": "queryRuntime", **semantic_execution["query"]["runtime"]},
                    {"type": "semanticQueryPlan", "status": semantic_plan["status"]},
                    {"type": "semanticExecutionPlan", "planHash": semantic_execution["executionPlan"]["planHash"]},
                    {
                        "type": "relationshipPathProof",
                        "status": semantic_execution.get("relationshipPathProof", {}).get("status"),
                        "fingerprint": semantic_execution.get("relationshipPathProof", {}).get("fingerprint"),
                        "hopCount": len(semantic_execution.get("relationshipPathProof", {}).get("hopProofs") or []),
                    },
                    *[
                        {"type": "relationship", "relationKey": relationship["relationKey"]}
                        for relationship in semantic_execution["executionPlan"].get("relationships", [])
                    ],
                ],
                "nextActions": [localized_value("打开证据核对字段、粒度和关系版本", "Open evidence to review fields, grain, and relationship versions")],
            }
        if semantic_blocked and not business_understanding_blocked:
            semantic_unresolved = semantic_plan["fieldResolution"].get("unresolved") or []
            execution_blockers = semantic_execution.get("executionPlan", {}).get("blockers") if semantic_execution else []
            status_summary = {
                "needs-clarification": "检测到多个字段候选，请先明确数据表或业务口径。",
                "needs-relationship": "所需字段分布在多张表，但当前工作区没有可审阅的已保存关系路径。",
                "needs-validation": "已找到关系路径，但至少一跳置信度或方向未通过规划门槛。",
            }.get(
                str(semantic_plan["status"]),
                f"语义计划已形成，但受控执行仍被阻断：{', '.join(execution_blockers or ['execution-plan-blocked'])}。",
            )
            answer_card = {
                "kind": "clarification",
                "title": {"zh": "需要确认字段或跨表路径", "en": "Field or join path needs review"},
                "summary": {"zh": status_summary, "en": "The semantic query plan is blocked until its field or relationship gap is resolved."},
                "confidence": "blocked",
                "metrics": [],
                "rows": [],
                "clarification": {
                    "kind": "semantic-execution-plan" if semantic_execution_blocked else "semantic-plan",
                    "status": "blocked" if semantic_execution_blocked else semantic_plan["status"],
                    "bindings": semantic_unresolved,
                },
                "executionPlan": semantic_execution.get("executionPlan") if semantic_execution else None,
                "evidenceRefs": [{"type": "semanticQueryPlan", "status": semantic_plan["status"]}],
                "nextActions": [
                    {"zh": "选择明确的数据表与字段，或先预览并保存可靠关系。", "en": "Choose an explicit table and field, or preview and save a reliable relationship first."}
                ],
            }
        elif widget_clarification and not business_understanding_blocked and isinstance(widget_action, dict):
            answer_card = build_widget_clarification_answer_card(widget_action)
        context_refs = [
            {"type": "contextTerm", "termKey": item["term_key"], "name": item["canonical_name"]}
            for item in context_matches["terms"]
        ] + [
            {"type": "contextRule", "ruleKey": item["rule_key"], "title": item["title"]}
            for item in context_matches["rules"]
        ]
        if recall_receipt:
            context_refs.append({
                "type": "recallReceipt",
                "receiptKey": recall_receipt["receiptKey"],
                "status": recall_receipt["status"],
                "candidateOnly": True,
            })
        if platform_match:
            context_refs.append(
                {
                    "type": "knowledgeRule",
                    "packId": platform_match["packId"],
                    "ruleId": platform_match["ruleId"],
                    "title": platform_match["title"],
                }
            )
        if context_refs:
            evidence_refs = list(answer_card.get("evidenceRefs", []))
            def evidence_key(item: dict[str, Any]) -> str:
                if item.get("type") == "knowledgeRule":
                    return f"knowledgeRule:{item.get('packId')}:{item.get('ruleId')}"
                return json.dumps(item, ensure_ascii=False, sort_keys=True)

            evidence_keys = {evidence_key(item) for item in evidence_refs}
            for item in context_refs:
                key = evidence_key(item)
                if key not in evidence_keys:
                    evidence_refs.append(item)
                    evidence_keys.add(key)
            answer_card["evidenceRefs"] = evidence_refs
        answer_query = answer_card.get("query") if isinstance(answer_card.get("query"), dict) else None
        receipt_source_table_keys = (
            list(semantic_execution.get("executionPlan", {}).get("pathTables") or [])
            if semantic_execution
            else (list(answer_query.get("tables") or []) if answer_query else [])
        )
        if not receipt_source_table_keys and selected_table:
            receipt_source_table_keys = [str(selected_table["table_key"])]
        receipt_source_binding = current_source_run_binding(connection, workspace_id, receipt_source_table_keys)
        answer_result_state = str(
            answer_card.get("resultState")
            or (answer_query.get("resultState") if answer_query else "")
            or (
                "executed"
                if not business_understanding_blocked and not semantic_blocked and answer_query and isinstance(answer_query.get("runtime"), dict)
                else "blocked"
            )
        )
        if answer_result_state == "executed" and receipt_source_binding.get("matchesCurrent") is not True:
            answer_result_state = "blocked"
            blocked_query = dict(answer_query or {})
            blocked_query.update({
                "resultState": "blocked",
                "sourceRunBinding": receipt_source_binding,
            })
            answer_card = {
                "kind": "trusted-query-blocked",
                "resultState": "blocked",
                "title": localized_value("当前数据批次不匹配", "Current source run does not match"),
                "summary": localized_value(
                    "查询涉及的数据表不属于当前 workspace 的 current sourceRun，因此不会发布经营数字。",
                    "The query tables are not bound to the current sourceRun, so no business number is published.",
                ),
                "confidence": "blocked",
                "metrics": [],
                "rows": [],
                "query": blocked_query,
                "evidenceRefs": [
                    {"type": "currentSourceRunBinding", **receipt_source_binding},
                    *list(answer_card.get("evidenceRefs") or []),
                ],
                "nextActions": [localized_value("切换到包含这些表的 current sourceRun 后重试", "Switch to a current sourceRun containing these tables and retry")],
            }
            answer_query = blocked_query
        if business_understanding_blocked:
            receipt_unresolved = []
            answer_clarification = answer_card.get("clarification")
            if (
                isinstance(answer_clarification, dict)
                and answer_clarification.get("kind") == "compound-analysis-definition"
            ):
                # Preserve the established receipt-level compound-metric blocker
                # while the richer Business Understanding slots explain exactly
                # which parts of the definition are still missing.
                receipt_unresolved.append({
                    "kind": "compound-analysis-definition",
                    "mention": str(answer_clarification.get("originalQuestion") or prompt),
                    "reason": "missing-verified-business-definition",
                    "required": list(answer_clarification.get("required") or []),
                })
            receipt_unresolved.extend(list(business_understanding.get("unresolved") or []))
            if not receipt_unresolved:
                receipt_unresolved = (
                    list(business_understanding.get("blockers") or [])
                    or (
                        [clarification["items"][0]]
                        if clarification.get("items")
                        else [answer_card.get("summary")]
                    )
                )
        else:
            receipt_unresolved = (
                semantic_plan["fieldResolution"].get("unresolved")
                or [
                    {
                        "type": "semantic-plan",
                        "status": semantic_plan["status"],
                        "joinPlan": semantic_plan["joinPlan"],
                    }
                ]
                if semantic_blocked
                else ([] if answer_query else [answer_card.get("clarification") or answer_card.get("summary")])
            )
        if semantic_execution_blocked:
            receipt_unresolved = merge_receipt_unresolved_with_execution_blockers(
                receipt_unresolved,
                semantic_execution.get("executionPlan"),
            )
        # Expensive planning and analytical reads complete before the short write
        # transaction. Revalidate the source binding after acquiring the writer
        # lock so stale analysis can never be persisted as current evidence.
        if connection.in_transaction:
            connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        revalidated_source_binding = current_source_run_binding(connection, workspace_id, receipt_source_table_keys)
        if revalidated_source_binding != receipt_source_binding:
            connection.rollback()
            raise RuntimeError("Workspace source version changed during Agent planning; retry the request.")
        if should_create_draft:
            create_action_draft(
                connection,
                action_key=action_key,
                workspace_id=workspace_id,
                kind=action_kind,
                label=str(action_label or agent_action_label(action_kind, wants_dashboard=intents.wants_dashboard)),
                payload=action_payload,
                evidence=action_evidence,
                created_at=now_iso(),
            )
        query_receipt = create_query_plan_receipt(
            connection,
            workspace_id=workspace_id,
            request_text=prompt,
            source_table_key=str(answer_query.get("table")) if answer_query and answer_query.get("table") else (selected_table["table_key"] if selected_table else None),
            source_table_keys=receipt_source_table_keys,
            relationship_path_proof=(
                semantic_execution.get("relationshipPathProof")
                if semantic_execution
                else None
            ),
            status=answer_result_state,
            group=str(answer_query.get("group")) if answer_query and answer_query.get("group") else None,
            groups=list(answer_query.get("groupRefs") or []) if answer_query else [],
            measure=str(answer_query.get("measure")) if answer_query and answer_query.get("measure") else None,
            aggregation=str(answer_query.get("aggregation")) if answer_query and answer_query.get("aggregation") else None,
            filters=list(answer_query.get("filters") or []) if answer_query else [],
            joins=list(answer_query.get("joins") or []) if answer_query else [],
            semantic_plan=semantic_plan,
            execution_plan=semantic_execution.get("executionPlan") if semantic_execution else None,
            knowledge_rule=answer_card.get("knowledgeRule") if isinstance(answer_card.get("knowledgeRule"), dict) else None,
            runtime=answer_query.get("runtime") if answer_query else None,
            evidence_refs=list(answer_card.get("evidenceRefs", [])),
            unresolved=receipt_unresolved,
            context_refs=context_refs,
            domain_packs=active_domain_pack_context["enabledDomainPacks"],
            action_key=action_key if should_create_draft else None,
            result_rows=list(answer_card.get("rows") or []),
            now_iso=now_iso,
            workspace_manifest=workspace_manifest_ref,
            query_intent=answer_query.get("typedIntent") if answer_query else None,
            execution_coverage=answer_query.get("executionCoverage") if answer_query else None,
            result_state=answer_result_state,
            source_run_binding=receipt_source_binding,
        )
        answer_card["queryPlanReceipt"] = query_receipt
        analysis_run = create_analysis_run(
            connection,
            workspace_id=workspace_id,
            question=prompt,
            status="pending_confirmation" if should_create_draft else query_receipt["status"],
            query_receipt_key=query_receipt["receiptKey"],
            action_key=action_key if should_create_draft else None,
            result={
                "kind": answer_card.get("kind"),
                "title": answer_card.get("title"),
                "summary": answer_card.get("summary"),
                "selection": query_receipt.get("selection"),
                "unresolved": query_receipt.get("unresolved"),
            },
            parent_run_key=parent_run_key or None,
            branch_label=str(getattr(args, "branch_label", "") or "").strip() or None,
            now_iso=now_iso,
        )
        if should_create_draft:
            stored_action = get_action_draft(connection, action_key=action_key, workspace_id=workspace_id)
            if stored_action:
                stored_payload = action_draft_payload(stored_action)
                stored_payload["queryReceiptKey"] = query_receipt["receiptKey"]
                stored_payload["analysisRunKey"] = analysis_run["run_key"]
                connection.execute(
                    "UPDATE action_drafts SET payload_json = ? WHERE workspace_id = ? AND action_key = ?",
                    (json.dumps(stored_payload, ensure_ascii=False), workspace_id, action_key),
                )
        connection.commit()
        ontology = ontology_snapshot(connection)
    recommended = build_agent_recommended_commands(
        answer_card=answer_card,
        selected_table=selected_table,
        selected_dashboard=selected_dashboard,
        intents=intents,
        read_only=read_only,
        import_file=import_file,
        relationship_action=relationship_action,
        dashboard_filter_action=dashboard_filter_action,
        widget_action=actionable_widget_action,
        dashboard_action=dashboard_action,
        index_field=index_field,
        formula_action=formula_action,
        view_action=view_action,
        metric_action=metric_action,
        semantic_action=semantic_action,
    )
    return {
        "ok": True,
        "workspaceId": workspace_id,
        "llm": {
            "configured": deepseek_configured,
            "mode": llm_audit["mode"],
            "audit": llm_audit,
        },
        "matched": {
            "table": selected_table,
            "tableSelectionConfidence": table_confidence,
            "dashboard": selected_dashboard,
            "dashboardSelectionConfidence": dashboard_confidence,
            "indexField": index_field,
            "indexFieldSelectionConfidence": index_field_confidence,
            "relationship": relationship_action,
            "relationshipSelectionConfidence": relationship_confidence,
            "importFile": str(import_file) if import_file else None,
            "importFileSelectionConfidence": import_confidence,
            "formula": formula_action,
            "formulaSelectionConfidence": formula_confidence,
            "view": view_action,
            "viewSelectionConfidence": view_confidence,
            "metric": metric_action,
            "metricSelectionConfidence": metric_confidence,
            "widget": widget_action,
            "widgetSelectionConfidence": widget_confidence,
            "dashboardFilter": dashboard_filter_action,
            "dashboardFilterSelectionConfidence": dashboard_filter_confidence,
            "dashboardOperation": dashboard_action,
            "dashboardOperationSelectionConfidence": dashboard_action_confidence,
            "semantic": semantic_action,
            "semanticSelectionConfidence": semantic_confidence,
        },
        "plan": [
            "确认当前 workspace 与 sourceRun 边界。 / Confirm the current workspace and sourceRun boundaries.",
            "只使用 Source Intelligence、Domain Pack、Ontology 和白名单 query runtime 形成答案。 / Use only Source Intelligence, Domain Pack, Ontology, and whitelist query runtime to form the answer.",
            "这次请求走只读解释通道，不创建 action draft。 / This request uses a read-only explanation channel and creates no action draft."
            if read_only
            else (
                "把会写入的 BI 操作保存为 action draft，等待确认。 / Save BI write operations as action drafts until confirmed."
                if should_create_draft
                else "字段选择不够确定时先给出澄清，不创建 action draft。 / Ask for clarification when field selection is uncertain and create no action draft."
            ),
        ],
        "answerCard": answer_card,
        "queryPlanReceipt": query_receipt,
        "semanticPlan": semantic_plan,
        "executionPlan": semantic_execution.get("executionPlan") if semantic_execution else None,
        "analysisRun": analysis_run,
        "intentFrame": intent_frame,
        "semanticContext": semantic_context,
        "businessUnderstanding": business_understanding,
        "analyticalSkillMatch": analytical_skill_match,
        "analyticalSkills": analytical_skill_runtime,
        "clarification": clarification,
        "context": {
            "matchedTermCount": len(context_matches["terms"]),
            "matchedRuleCount": len(context_matches["rules"]),
            "terms": [
                {"termKey": item["term_key"], "name": item["canonical_name"], "definition": item["definition"]}
                for item in context_matches["terms"]
            ],
            "rules": [
                {"ruleKey": item["rule_key"], "title": item["title"], "statement": item["statement"]}
                for item in context_matches["rules"]
            ],
            "confirmedQueries": [
                {"queryKey": item["query_key"], "question": item["question"], "matchScore": item["matchScore"]}
                for item in recalled_queries
            ],
            "confirmedPlans": [
                {
                    "memoryKey": item.get("memoryKey"),
                    "queryKey": item.get("queryKey"),
                    "question": item.get("question"),
                    "matchScore": item.get("matchScore"),
                    "matchChannels": item.get("matchChannels") or {},
                    "canAuthorizeSelection": False,
                }
                for item in recalled_plans
            ],
            "recallReceipt": recall_receipt,
            "knowledgeRules": [
                {
                    "packId": platform_match["packId"],
                    "ruleId": platform_match["ruleId"],
                    "title": platform_match["title"],
                    "grain": platform_match["grain"],
                }
            ] if platform_match else [],
        },
        "agentKnowledge": {
            "packId": platform_match["packId"] if platform_match else None,
            "version": platform_match["packVersion"] if platform_match else None,
            "matchedRuleId": platform_match["ruleId"] if platform_match else None,
            "modelIndependent": True,
        },
        "domainPacks": active_domain_pack_context,
        "recommendedCommands": recommended,
        "requiresConfirmation": should_create_draft,
        "actionDraft": {
            "actionKey": action_key,
            "kind": action_kind,
            "status": "draft" if should_create_draft else "read-only",
        },
        "ontology": ontology,
        "coreSemanticRuntime": core_semantic_runtime(),
        "sourcePipelineContract": source_pipeline_contract(),
    }


def confirm_action_command(args: argparse.Namespace) -> dict[str, Any]:
    with closing(open_db()) as connection:
        workspace_id = str(getattr(args, "workspace", "") or active_workspace_id(connection))
        action = get_action_draft(connection, action_key=args.action_key, workspace_id=workspace_id)
        if not action:
            raise ValueError(f"Unknown action draft in active workspace {workspace_id}: {args.action_key}")
        payload = action_draft_payload(action)
        if args.reject:
            if not args.yes:
                return reject_dry_run_response(action, payload)
            mark_action_rejected(connection, args.action_key, now_iso())
            connection.commit()
            return rejected_response(args.action_key)
        if action["kind"] == "index.create":
            return handle_index_create_confirmation(
                connection,
                action,
                payload,
                action_key=args.action_key,
                yes=args.yes,
                confirmed_at=now_iso(),
                build_index_plan=build_index_plan,
                execute_index_plan=execute_index_plan,
            )
        if action["kind"] == "relationship.save":
            return handle_relationship_save_confirmation(
                connection,
                action,
                payload,
                action_key=args.action_key,
                yes=args.yes,
                confirmed_at=now_iso(),
                build_relationship_save_plan=build_relationship_save_plan,
                execute_relationship_save=execute_relationship_save,
            )
        if action["kind"] == "import.commit":
            return handle_import_commit_confirmation(
                connection,
                action,
                payload,
                action_key=args.action_key,
                yes=args.yes,
                confirmed_at=now_iso(),
                build_import_preview=build_import_preview,
                execute_import_commit=execute_import_commit,
            )
        if action["kind"] == "formula.save":
            return handle_formula_save_confirmation(
                connection,
                action,
                payload,
                action_key=args.action_key,
                yes=args.yes,
                confirmed_at=now_iso(),
                build_formula_save_plan=build_formula_save_plan,
                execute_formula_save_plan=execute_formula_save_plan,
            )
        if action["kind"] == "view.save":
            return handle_view_save_confirmation(
                connection,
                action,
                payload,
                action_key=args.action_key,
                yes=args.yes,
                confirmed_at=now_iso(),
                build_save_view_plan=build_save_view_plan,
                execute_save_view_plan=execute_save_view_plan,
            )
        if action["kind"] == "metric.add":
            return handle_metric_add_confirmation(
                connection,
                action,
                payload,
                action_key=args.action_key,
                yes=args.yes,
                confirmed_at=now_iso(),
                build_metric_add_plan=build_metric_add_plan,
                execute_metric_add_plan=execute_metric_add_plan,
            )
        if action["kind"] == "semantic.set":
            return handle_semantic_set_confirmation(
                connection,
                action,
                payload,
                action_key=args.action_key,
                yes=args.yes,
                confirmed_at=now_iso(),
                workspace_id=workspace_id,
                build_semantic_set_plan=build_semantic_set_plan,
                execute_semantic_set_plan=execute_semantic_set_plan,
                semantic_row_to_payload=semantic_row_to_payload,
            )
        if action["kind"] == "dashboard.widget.add":
            candidate = None
            if args.yes:
                dashboard_key = str(payload.get("dashboardKey", "") or "")
                widget_type = str(payload.get("widgetType", "") or "")
                options = dict(payload.get("options")) if isinstance(payload.get("options"), dict) else {}
                if payload.get("tableKey") and not options.get("tableKey"):
                    options["tableKey"] = payload["tableKey"]
                if payload.get("title") and not options.get("title"):
                    options["title"] = payload["title"]
                proposed_widget = build_widget_proposal(connection, dashboard_key, widget_type, options)
                candidate = create_confirmed_query_candidate(
                    connection,
                    workspace_id=workspace_id,
                    action_key=args.action_key,
                    action_payload=payload,
                    added_widget=proposed_widget,
                    now_iso=now_iso,
                )
                if not candidate:
                    raise ValueError(
                        "Chart confirmation requires an executed Query Receipt bound to the current sourceRun"
                    )
            result = handle_dashboard_widget_add_confirmation(
                connection,
                action,
                payload,
                action_key=args.action_key,
                yes=args.yes,
                confirmed_at=now_iso(),
                build_widget_proposal=build_widget_proposal,
                insert_dashboard_widget=insert_dashboard_widget,
            )
            if candidate and result.get("confirmed") is True:
                result["confirmedQueryCandidate"] = candidate
            return result
        if action["kind"] == "dashboard.filter.add":
            return handle_dashboard_filter_add_confirmation(
                connection,
                action,
                payload,
                action_key=args.action_key,
                yes=args.yes,
                confirmed_at=now_iso(),
                build_dashboard_filter_add_plan=build_dashboard_filter_add_plan,
                execute_dashboard_filter_add_plan=execute_dashboard_filter_add_plan,
            )
        if action["kind"] in {"dashboard.copy", "dashboard.rename", "dashboard.delete"}:
            return handle_dashboard_operation_confirmation(
                connection,
                action,
                payload,
                action_key=args.action_key,
                yes=args.yes,
                confirmed_at=now_iso(),
                build_dashboard_operation_plan=build_dashboard_operation_plan,
                execute_dashboard_operation_plan=execute_dashboard_operation_plan,
            )
        if action["kind"] == "dashboard.create":
            dashboard_draft = payload.get("dashboardDraft") if isinstance(payload.get("dashboardDraft"), dict) else {}
            draft_widgets = dashboard_draft.get("widgets") if isinstance(dashboard_draft.get("widgets"), list) else []
            single_chart_confirmation = (
                args.yes
                and dashboard_draft.get("source") == "single-chart"
                and len(draft_widgets) == 1
                and isinstance(draft_widgets[0], dict)
            )
            candidate = None
            if single_chart_confirmation:
                candidate = create_confirmed_query_candidate(
                    connection,
                    workspace_id=workspace_id,
                    action_key=args.action_key,
                    action_payload=payload,
                    added_widget=draft_widgets[0],
                    now_iso=now_iso,
                )
                if not candidate:
                    raise ValueError(
                        "Chart confirmation requires an executed Query Receipt bound to the current sourceRun"
                    )
            result = handle_dashboard_create_confirmation(
                connection,
                action,
                payload,
                action_key=args.action_key,
                yes=args.yes,
                confirmed_at=now_iso(),
                workspace_id=workspace_id,
                unique_key=unique_key,
                build_agent_dashboard_create_draft=build_agent_dashboard_create_draft,
                write_business_dashboard=write_business_dashboard,
                upsert_navigation_module=upsert_navigation_module,
            )
            if candidate and result.get("confirmed") is True:
                result["confirmedQueryCandidate"] = candidate
            return result
        if not args.yes:
            return confirm_dry_run_response(action, payload)
        mark_action_confirmed(connection, args.action_key, now_iso())
        connection.commit()
    return confirmed_response(args.action_key)
