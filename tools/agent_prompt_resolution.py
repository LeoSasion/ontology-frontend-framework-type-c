from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bi_cli_core import slug


@dataclass(frozen=True)
class AgentPromptIntents:
    wants_dashboard: bool
    wants_dashboard_create: bool
    wants_import: bool
    wants_relationship: bool
    wants_index: bool
    wants_formula: bool
    wants_view: bool
    wants_widget: bool
    wants_dashboard_filter: bool
    wants_metric: bool
    wants_semantic: bool
    dashboard_operation: str


def dashboard_operation_from_prompt(prompt: str) -> str:
    lower = prompt.lower()
    mentions_dashboard = any(token in prompt for token in ["看板", "仪表盘"]) or "dashboard" in lower
    if mentions_dashboard and (any(token in prompt for token in ["删除", "移除"]) or any(token in lower for token in ["delete", "remove"])):
        return "delete"
    if mentions_dashboard and (any(token in prompt for token in ["重命名", "改名"]) or "rename" in lower):
        return "rename"
    if mentions_dashboard and (any(token in prompt for token in ["复制", "拷贝"]) or any(token in lower for token in ["copy", "duplicate"])):
        return "copy"
    return ""


def prompt_mentions_index(prompt: str) -> bool:
    lower = prompt.lower()
    return any(token in lower for token in ["索引", "建索引", "优化查询", "查询加速", "index", "optimize query", "speed up query"])


def prompt_mentions_widget_add(prompt: str) -> bool:
    lower = prompt.lower()
    add_intent = any(token in prompt for token in ["添加", "新增", "增加", "创建", "生成", "起草", "做一个", "做个", "做成", "做", "放一个", "加一个", "加到"]) or any(
        token in lower for token in ["add", "insert", "place", "put", "create", "draft", "generate", "make"]
    )
    explicit_widget_intent = any(token in prompt for token in ["组件", "指标卡", "卡片", "折线图", "柱状图", "饼图", "表格", "筛选器"]) or any(
        token in lower for token in ["widget", "metric card", "card", "bar chart", "line chart", "pie chart", "table", "slicer"]
    )
    generic_chart_intent = "图表" in prompt or "chart" in lower
    widget_intent = explicit_widget_intent or generic_chart_intent
    return add_intent and widget_intent


def prompt_mentions_dashboard_create(prompt: str) -> bool:
    lower = prompt.lower()
    has_dashboard = any(token in prompt for token in ["看板", "仪表盘"]) or "dashboard" in lower
    if not has_dashboard:
        return False
    if any(token in prompt for token in ["看板组件", "仪表盘组件"]) or "dashboard widget" in lower:
        return False
    zh_create = bool(re.search(r"(生成|创建|新建|起草|搭建|制作).{0,20}(看板|仪表盘)", prompt)) or bool(
        re.search(r"(做一张|做一个|做个).{0,20}(看板|仪表盘)", prompt)
    )
    en_create = bool(re.search(r"\b(create|draft|generate|make|build)\b.{0,40}\bdashboard\b", lower))
    return zh_create or en_create


def prompt_mentions_dashboard_filter(prompt: str) -> bool:
    lower = prompt.lower()
    if any(token in prompt for token in ["筛选器", "切片器"]) or any(token in lower for token in ["slicer", "filter control"]):
        return False
    has_filter = any(token in prompt for token in ["筛选", "过滤", "限定", "只看"]) or any(token in lower for token in ["filter", "where", "only show"])
    has_dashboard = any(token in prompt for token in ["看板", "仪表盘"]) or "dashboard" in lower
    has_value_pattern = bool(re.search(r"[\u4e00-\u9fffA-Za-z0-9_ -]{1,40}\s*(=|等于|为|是|contains?|equals?)\s*[\u4e00-\u9fffA-Za-z0-9_.@\-]+", prompt, re.IGNORECASE))
    return has_filter and (has_dashboard or has_value_pattern)


def prompt_mentions_view_save(prompt: str) -> bool:
    lower = prompt.lower()
    return (
        any(token in prompt for token in ["保存视图", "保存成视图", "保存为视图", "保存筛选", "存成视图", "常用视图", "明细视图"])
        or (any(token in prompt for token in ["保存", "存成", "创建", "生成"]) and "视图" in prompt)
        or any(token in lower for token in ["save view", "saved view", "save this view", "create view"])
    )


def resolve_agent_prompt_intents(prompt: str) -> AgentPromptIntents:
    lower = prompt.lower()
    wants_dashboard = any(token in prompt for token in ["看板", "仪表盘"]) or "dashboard" in lower
    wants_dashboard_create = prompt_mentions_dashboard_create(prompt)
    wants_import = any(token in prompt for token in ["导入", "上传"]) or "import" in lower
    wants_relationship = any(token in prompt for token in ["关联", "关系"]) or "join" in lower
    wants_index = prompt_mentions_index(prompt)
    wants_formula = any(token in lower for token in ["formula", "calculated field", "derived field"]) or any(token in prompt for token in ["公式", "计算字段", "派生字段"])
    wants_view = prompt_mentions_view_save(prompt)
    wants_widget = prompt_mentions_widget_add(prompt)
    wants_dashboard_filter = prompt_mentions_dashboard_filter(prompt)
    wants_metric = (
        bool(re.search(r"(新增|添加|创建|定义|保存|做成).{0,64}指标", prompt))
        or bool(re.search(r"\b(add|create|define|save)\s+(a\s+|an\s+)?(metric|kpi)\b", lower))
        or "指标口径" in prompt
        or any(token in lower for token in ["metric definition", "new metric", "kpi definition"])
    ) and "指标卡" not in prompt
    wants_semantic = any(token in lower for token in ["semantic", "dimension", "measure", "metric", "identity_key", "event_time"]) or any(
        token in prompt for token in ["字段语义", "语义", "维度", "指标字段", "数值字段", "金额字段", "关联键", "主键", "唯一键", "时间字段", "日期字段", "状态字段"]
    )
    return AgentPromptIntents(
        wants_dashboard=wants_dashboard,
        wants_dashboard_create=wants_dashboard_create,
        wants_import=wants_import,
        wants_relationship=wants_relationship,
        wants_index=wants_index,
        wants_formula=wants_formula,
        wants_view=wants_view,
        wants_widget=wants_widget,
        wants_dashboard_filter=wants_dashboard_filter,
        wants_metric=wants_metric,
        wants_semantic=wants_semantic,
        dashboard_operation=dashboard_operation_from_prompt(prompt),
    )


def select_agent_table(tables: list[dict[str, Any]], prompt: str) -> tuple[dict[str, Any] | None, str]:
    selected_table = tables[0] if tables else None
    table_confidence = "fallback"
    lower = prompt.lower()
    for table in tables:
        if str(table["table_key"]).lower() in lower or str(table["display_name"]).lower() in lower:
            selected_table = table
            table_confidence = "explicit"
            break
    return selected_table, table_confidence


def should_create_agent_draft(
    *,
    intents: AgentPromptIntents,
    dashboard_confidence: str,
    dashboard_action: dict[str, Any] | None,
    widget_action: dict[str, Any] | None,
    dashboard_filter_action: dict[str, Any] | None,
    index_field: str | None,
    relationship_action: dict[str, Any] | None,
    import_file: Path | None,
    formula_action: dict[str, Any] | None,
    view_action: dict[str, Any] | None,
    metric_action: dict[str, Any] | None,
    semantic_action: dict[str, Any] | None,
    read_only: bool,
) -> bool:
    if read_only:
        return False
    dashboard_create = (
        intents.wants_dashboard_create
        and not intents.dashboard_operation
        and not widget_action
        and not dashboard_filter_action
    )
    return (
        dashboard_create
        or bool(dashboard_action)
        or bool(widget_action)
        or bool(dashboard_filter_action)
        or bool(relationship_action)
        or bool(index_field)
        or bool(import_file)
        or bool(formula_action)
        or bool(view_action)
        or bool(metric_action)
        or bool(semantic_action)
    )


def build_agent_action_payload(
    *,
    prompt: str,
    selected_dashboard: dict[str, Any] | None,
    selected_table: dict[str, Any] | None,
    widget_action: dict[str, Any] | None,
    dashboard_filter_action: dict[str, Any] | None,
    index_field: str | None,
    index_field_confidence: str,
    index_recommendation: dict[str, Any] | None,
    relationship_action: dict[str, Any] | None,
    import_file: Path | None,
    import_confidence: str,
    import_mode: str,
    formula_action: dict[str, Any] | None,
    view_action: dict[str, Any] | None,
    metric_action: dict[str, Any] | None,
    semantic_action: dict[str, Any] | None,
    dashboard_action: dict[str, Any] | None,
) -> dict[str, Any]:
    action_payload: dict[str, Any] = {
        "dashboardKey": selected_dashboard["dashboard_key"] if selected_dashboard else None,
        "tableKey": selected_table["table_key"] if selected_table else None,
        "prompt": prompt,
        "originalPrompt": prompt,
    }
    for action in [widget_action, dashboard_filter_action, relationship_action, formula_action, view_action, metric_action, semantic_action, dashboard_action]:
        if action:
            action_payload.update(action)
    if index_field:
        action_payload.update(
            {
                "field": index_field,
                "fieldSelectionConfidence": index_field_confidence,
                "recommendation": index_recommendation,
            }
        )
    if import_file:
        action_payload.update(
            {
                "filePath": str(import_file),
                "tableKey": slug(import_file.stem),
                "name": import_file.stem,
                "mode": import_mode,
                "fileSelectionConfidence": import_confidence,
            }
        )
    return action_payload


def agent_action_kind(
    *,
    intents: AgentPromptIntents,
    read_only: bool,
    index_field: str | None,
    dashboard_action: dict[str, Any] | None,
    dashboard_filter_action: dict[str, Any] | None,
    widget_action: dict[str, Any] | None,
    relationship_action: dict[str, Any] | None,
    import_file: Path | None,
    formula_action: dict[str, Any] | None,
    view_action: dict[str, Any] | None,
    metric_action: dict[str, Any] | None,
    semantic_action: dict[str, Any] | None,
) -> str:
    if read_only:
        return "analysis.explain"
    if intents.wants_index and index_field:
        return "index.create"
    if dashboard_action:
        return f"dashboard.{dashboard_action['op']}"
    if intents.wants_dashboard_filter and dashboard_filter_action:
        return "dashboard.filter.add"
    if intents.wants_widget and widget_action and not widget_action.get("dashboardKey"):
        return "dashboard.create"
    if intents.wants_widget and widget_action:
        return "dashboard.widget.add"
    if intents.wants_relationship and relationship_action:
        return "relationship.save"
    if intents.wants_import and import_file:
        return "import.commit"
    if intents.wants_formula and formula_action:
        return "formula.save"
    if intents.wants_view and view_action:
        return "view.save"
    if intents.wants_metric and metric_action:
        return "metric.add"
    if intents.wants_semantic and semantic_action:
        return "semantic.set"
    if intents.wants_dashboard:
        return "dashboard.create"
    return "analysis.plan"


def agent_action_label(action_kind: str, *, wants_dashboard: bool) -> str:
    labels = {
        "index.create": "创建 DuckDB 索引草案",
        "relationship.save": "保存关系草案",
        "import.commit": "提交导入草案",
        "formula.save": "保存公式草案",
        "view.save": "保存视图草案",
        "metric.add": "新增指标草案",
        "semantic.set": "保存字段语义草案",
        "dashboard.filter.add": "新增看板筛选草案",
        "dashboard.widget.add": "新增看板组件草案",
        "dashboard.copy": "复制看板草案",
        "dashboard.rename": "重命名看板草案",
        "dashboard.delete": "删除看板草案",
    }
    return labels.get(action_kind, "生成看板草案" if wants_dashboard else "生成分析计划")


def agent_action_evidence(action_kind: str) -> list[str]:
    evidence_by_kind = {
        "index.create": ["ontology", "field-semantics", "index-recommendation", "query-runtime", "write-boundary"],
        "relationship.save": ["ontology", "semantic-field-candidates", "relationship-discovery", "relationship-coverage-matrix", "write-boundary"],
        "import.commit": ["source-profile", "import-preview", "merge-policy-preview", "source-run-boundary", "write-boundary"],
        "formula.save": ["formula-dsl", "field-semantics", "metric-definition", "query-runtime", "write-boundary"],
        "view.save": ["saved-view-config", "table-query-whitelist", "field-semantics", "query-runtime", "write-boundary"],
        "metric.add": ["field-semantics", "metric-definition", "query-runtime", "dashboard-widget-catalog", "write-boundary"],
        "semantic.set": ["field-semantics", "source-profile", "semantic-confirmation", "metric-definition", "write-boundary"],
        "dashboard.filter.add": ["dashboard-registry", "dashboard-filters", "field-semantics", "query-runtime", "dashboardSelectionConfidence", "write-boundary"],
        "dashboard.widget.add": ["dashboard-registry", "dashboard-widget-catalog", "field-semantics", "query-runtime", "dashboardSelectionConfidence", "write-boundary"],
        "dashboard.copy": ["dashboard-registry", "dashboard-widgets", "navigation-modules", "dashboardSelectionConfidence", "write-boundary"],
        "dashboard.rename": ["dashboard-registry", "dashboard-widgets", "navigation-modules", "dashboardSelectionConfidence", "write-boundary"],
        "dashboard.delete": ["dashboard-registry", "dashboard-widgets", "navigation-modules", "dashboardSelectionConfidence", "write-boundary"],
    }
    return evidence_by_kind.get(action_kind, ["ontology", "source-profile", "query-runtime"])
