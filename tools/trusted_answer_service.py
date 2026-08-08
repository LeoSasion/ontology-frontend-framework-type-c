from __future__ import annotations

import re
import sqlite3
from typing import Any

from bi_cli_core import DUCKDB_PATH
from bi_cli_schema import active_workspace_id, table_columns
from bi_cli_source_commands import resolve_table_registry
from apparel_analytics_service import execute_apparel_method
from query_runtime import DuckDBUnavailable, quote_identifier, run_duckdb_aggregate_query, run_sqlite_aggregate_query
from trusted_query_service import build_execution_coverage, build_trusted_query_intent, trusted_result_state


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


def _normalize_match_text(value: str) -> str:
    return re.sub(r"[\s_\-./]+", "", str(value or "")).casefold()


def aggregation_from_metric_prompt(prompt: str, measure: str) -> str:
    lower = prompt.lower()
    if any(token in prompt for token in ["平均", "均值"]) or any(token in lower for token in ["avg", "average", "mean"]):
        return "avg"
    if any(token in prompt for token in ["最大", "最高"]) or "max" in lower:
        return "max"
    if any(token in prompt for token in ["最小", "最低"]) or "min" in lower:
        return "min"
    if any(token in prompt for token in ["去重", "唯一"]) or "distinct" in lower:
        return "count-distinct"
    if any(token in prompt for token in ["记录数", "行数", "条数"]) or "count" in lower or measure == "*":
        return "count"
    return "sum"


def select_metric_field_from_prompt(
    connection: sqlite3.Connection,
    table_key: str,
    prompt: str,
) -> tuple[str, str]:
    registry = resolve_table_registry(connection, table_key)
    columns = table_columns(connection, registry["physical_table"])
    normalized_prompt = _normalize_match_text(prompt)
    workspace_id = active_workspace_id(connection)
    semantic_rows = connection.execute(
        """
        SELECT field_name, role, confidence
        FROM field_semantics
        WHERE table_key = ? AND workspace_id = ?
        ORDER BY confidence DESC, field_name
        """,
        (table_key, workspace_id),
    ).fetchall()
    semantic_roles = {str(row["field_name"] or ""): str(row["role"] or "") for row in semantic_rows}
    explicit_columns = [column for column in columns if _normalize_match_text(column) in normalized_prompt]
    for column in explicit_columns:
        if semantic_roles.get(column) == "measure":
            return column, "explicit"
    for column in explicit_columns:
        if semantic_roles.get(column) not in {"dimension", "status", "identity_key", "event_time"}:
            return column, "explicit"
    for row in semantic_rows:
        field = str(row["field_name"] or "")
        if row["role"] == "measure" and field in columns:
            return field, "fallback"
    return "*", "fallback"


def select_metric_dimension_from_prompt(
    connection: sqlite3.Connection,
    table_key: str,
    prompt: str,
    measure: str,
) -> tuple[str, str]:
    registry = resolve_table_registry(connection, table_key)
    columns = table_columns(connection, registry["physical_table"])
    normalized_prompt = _normalize_match_text(prompt)
    dimension_intent = any(token in prompt for token in ["按", "分组", "拆分", "维度"]) or any(token in prompt.lower() for token in [" by ", "group", "segment"])
    if not dimension_intent:
        return "", "none"
    workspace_id = active_workspace_id(connection)
    semantic_rows = connection.execute(
        """
        SELECT field_name, role, usage, confidence
        FROM field_semantics
        WHERE table_key = ? AND workspace_id = ?
        ORDER BY confidence DESC, field_name
        """,
        (table_key, workspace_id),
    ).fetchall()
    semantic_roles = {str(row["field_name"] or ""): str(row["role"] or "") for row in semantic_rows}
    dimension_tail = prompt
    tail_match = re.search(r"(?:按|按照|分组|拆分|by|group by)\s*([\u4e00-\u9fffA-Za-z0-9_\- ]{1,48})", prompt, re.IGNORECASE)
    if tail_match:
        dimension_tail = tail_match.group(1)
    normalized_tail = _normalize_match_text(dimension_tail)
    for column in columns:
        if column != measure and _normalize_match_text(column) in normalized_tail:
            return column, "explicit"
    for column in columns:
        if column != measure and _normalize_match_text(column) in normalized_prompt and semantic_roles.get(column) in {"dimension", "status", "identity_key", "event_time"}:
            return column, "explicit"
    for row in semantic_rows:
        field = str(row["field_name"] or "")
        if field and field != measure and row["role"] in {"dimension", "status", "identity_key"} and field in columns:
            return field, "fallback"
    return "", "missing"


def _answer_table_columns(
    connection: sqlite3.Connection,
    table_key: str,
    workspace_id: str,
) -> tuple[sqlite3.Row | None, list[str]]:
    registry = connection.execute(
        "SELECT * FROM table_registry WHERE table_key = ? AND workspace_id = ?",
        (table_key, workspace_id),
    ).fetchone()
    if not registry:
        return None, []
    columns = [row["name"] for row in connection.execute(f"PRAGMA table_info({quote_identifier(registry['physical_table'])})")]
    return registry, columns


def _safe_answer_aggregate(
    connection: sqlite3.Connection,
    table_key: str,
    *,
    group: str | None,
    measure: str,
    aggregation: str,
    limit: int,
    workspace_id: str,
    filters: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str | None]:
    registry, columns = _answer_table_columns(connection, table_key, workspace_id)
    if not registry:
        return None, [], f"Unknown table: {table_key}"
    if group and group not in columns:
        return None, [], f"Unknown group field: {group}"
    if measure != "*" and measure not in columns:
        return None, [], f"Unknown measure field: {measure}"
    unknown_filter_fields = [str(item.get("field") or "") for item in filters if str(item.get("field") or "") not in columns]
    if unknown_filter_fields:
        return None, [], f"Unknown filter fields: {', '.join(unknown_filter_fields)}"
    try:
        runtime = run_duckdb_aggregate_query(
            sqlite_connection=connection,
            duckdb_path=DUCKDB_PATH,
            physical_table=registry["physical_table"],
            columns=columns,
            group=group,
            measure=measure,
            aggregation=aggregation,
            limit=limit,
            filters=filters,
            source_version=f"{registry['workspace_id']}:{registry['table_key']}:{int(registry['data_version'] or 1)}:{int(registry['row_count'] or 0)}",
        )
        fallback_reason = None
    except DuckDBUnavailable as exc:
        runtime = run_sqlite_aggregate_query(
            sqlite_connection=connection,
            physical_table=registry["physical_table"],
            group=group,
            measure=measure,
            aggregation=aggregation,
            limit=limit,
            filters=filters,
        )
        fallback_reason = str(exc)
    rows = runtime.pop("rows")
    return runtime, rows, fallback_reason


def _current_source_run_ref(source_run_binding: dict[str, Any] | None) -> dict[str, Any] | None:
    binding = source_run_binding if isinstance(source_run_binding, dict) else {}
    source_run = binding.get("sourceRun") if isinstance(binding.get("sourceRun"), dict) else None
    if binding.get("matchesCurrent") is not True or source_run is None:
        return None
    return dict(source_run)


def _metric_ref(
    connection: sqlite3.Connection,
    table_key: str,
    measure: str,
    aggregation: str,
    dimension: str | None,
    workspace_id: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT metric_key, label, table_key, measure, aggregation, dimension, value_format
        FROM metric_definitions
        WHERE table_key = ? AND workspace_id = ? AND measure = ? AND aggregation = ?
          AND COALESCE(dimension, '') = COALESCE(?, '')
        ORDER BY created_at DESC LIMIT 1
        """,
        (table_key, workspace_id, measure, aggregation, dimension),
    ).fetchone()
    return dict(row) if row else None


def _blocked_answer(
    *,
    title_zh: str,
    title_en: str,
    summary_zh: str,
    summary_en: str,
    query: dict[str, Any],
    evidence_refs: list[dict[str, Any]],
    next_zh: str,
    next_en: str,
) -> dict[str, Any]:
    return {
        "kind": "trusted-query-blocked",
        "resultState": "blocked",
        "title": localized_value(title_zh, title_en),
        "summary": localized_value(summary_zh, summary_en),
        "confidence": "blocked",
        "metrics": [],
        "rows": [],
        "query": query,
        "evidenceRefs": evidence_refs,
        "nextActions": [localized_value(next_zh, next_en)],
    }


def build_trusted_answer_card(
    connection: sqlite3.Connection,
    prompt: str,
    selected_table: dict[str, Any] | None,
    widget_action: dict[str, Any] | None = None,
    workspace_id: str | None = None,
    intent_frame: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_workspace_id = workspace_id or active_workspace_id(connection)
    if not selected_table:
        return {
            "kind": "gap",
            "resultState": "blocked",
            "title": localized_value("还没有可分析的数据表", "No analyzable table yet"),
            "summary": localized_value("请先导入本地文件或选择当前工作区中的数据源。", "Import a local file or select a source in the current workspace first."),
            "confidence": "missing",
            "metrics": [],
            "rows": [],
            "evidenceRefs": [],
            "nextActions": [localized_value("导入本地文件或文件夹", "Import a local file or folder")],
        }
    table_key = str(selected_table["table_key"])
    registry, columns = _answer_table_columns(connection, table_key, resolved_workspace_id)
    if not registry:
        return build_trusted_answer_card(connection, prompt, None, widget_action, resolved_workspace_id, intent_frame)

    options = widget_action.get("options") if isinstance(widget_action, dict) else None
    if isinstance(options, dict):
        measure = str(options.get("measure") or "*")
        dimension = str(options.get("dimension") or "") or None
        aggregation = str(options.get("aggregation") or ("count" if measure == "*" else "sum"))
        measure_confidence = "widget"
        dimension_confidence = "widget" if dimension else "none"
        title = localized_value("图表草案数据预览", "Chart draft data preview")
        intent = "chart_preview"
    else:
        measure, measure_confidence = select_metric_field_from_prompt(connection, table_key, prompt)
        selected_dimension, dimension_confidence = select_metric_dimension_from_prompt(connection, table_key, prompt, measure)
        dimension = selected_dimension if dimension_confidence in {"explicit", "recommended"} else None
        aggregation = aggregation_from_metric_prompt(prompt, measure)
        if measure_confidence not in {"explicit", "recommended"} and selected_dimension and dimension_confidence == "explicit":
            measure, aggregation, dimension = "*", "count", selected_dimension
            intent = "dimension_overview"
        elif measure_confidence in {"explicit", "recommended"}:
            intent = "field_analysis"
        else:
            measure, aggregation, dimension = "*", "count", None
            intent = "data_overview"
        title = (
            localized_value(f"{measure} 按 {dimension} 分析", f"{measure} by {dimension}") if measure != "*" and dimension
            else localized_value(f"{measure} 概览", f"{measure} overview") if measure != "*"
            else localized_value(f"按 {dimension} 查看记录", f"Rows by {dimension}") if dimension
            else localized_value("当前数据概览", "Current data overview")
        )

    typed_intent = build_trusted_query_intent(
        connection,
        workspace_id=resolved_workspace_id,
        prompt=prompt,
        table_key=table_key,
        columns=columns,
        intent_frame=intent_frame,
        measure=measure,
        measure_confidence=measure_confidence,
        dimension=dimension,
        dimension_confidence=dimension_confidence,
        suggested_aggregation=aggregation,
        # The deterministic query result is executed even when its consumer is
        # a pending chart write. The Action Draft owns the draft state; the
        # Query Receipt must remain reusable as executed/current evidence.
        result_state="executed",
    )
    aggregation = str(typed_intent["aggregation"]["function"])
    base_query = {
        "table": table_key,
        "group": dimension,
        "measure": measure,
        "aggregation": aggregation,
        "filters": list(typed_intent.get("filters") or []),
        "typedIntent": typed_intent,
        "sourceRunBinding": typed_intent.get("sourceRunBinding"),
    }
    if typed_intent.get("blockers"):
        coverage = build_execution_coverage(typed_intent, runtime=None, result_rows=[], result_state="blocked")
        query = {**base_query, "runtime": None, "executionCoverage": coverage, "resultState": "blocked", "sqlIntent": "whitelist aggregate query; execution blocked before SQL"}
        blocker_text = ", ".join(str(item) for item in coverage["blockers"])
        return _blocked_answer(
            title_zh="可信查询已阻断",
            title_en="Trusted query blocked",
            summary_zh=f"为避免输出错误经营数字，本次查询未执行：{blocker_text}。",
            summary_en=f"The query was not executed to avoid an unsupported business number: {blocker_text}.",
            query=query,
            evidence_refs=[
                {"type": "currentSourceRunBinding", **typed_intent["sourceRunBinding"]},
                {"type": "queryExecutionCoverage", "complete": False, "blockers": coverage["blockers"]},
            ],
            next_zh="明确指标、聚合、粒度与筛选后重试",
            next_en="Resolve the measure, aggregation, grain, and filters before retrying",
        )

    apparel_method_result = execute_apparel_method(
        connection,
        registry=registry,
        columns=columns,
        query_intent=typed_intent,
    )
    if apparel_method_result is not None:
        runtime = apparel_method_result["runtime"]
        rows = list(apparel_method_result.get("rows") or [])
        fallback_reason = None
        if apparel_method_result.get("blockers"):
            typed_intent = {
                **typed_intent,
                "blockers": [*list(typed_intent.get("blockers") or []), *list(apparel_method_result["blockers"])],
                "blockerDetails": [*list(typed_intent.get("blockerDetails") or []), *list(apparel_method_result["blockers"])],
                "ready": False,
            }
            base_query["typedIntent"] = typed_intent
    else:
        runtime, rows, fallback_reason = _safe_answer_aggregate(
            connection,
            table_key,
            group=dimension,
            measure=measure,
            aggregation=aggregation,
            limit=int(typed_intent.get("limit", {}).get("count") or 5),
            workspace_id=resolved_workspace_id,
            filters=list(typed_intent.get("filters") or []),
        )
    if runtime is None:
        return _blocked_answer(
            title_zh="可信查询字段不可执行",
            title_en="Trusted query fields are not executable",
            summary_zh=f"当前表缺少查询所需字段：{measure} / {dimension or '-'}。",
            summary_en=f"The current table is missing fields required by the query: {measure} / {dimension or '-'}.",
            query={**base_query, "runtime": None, "resultState": "blocked"},
            evidence_refs=[{"type": "table", "tableKey": table_key}],
            next_zh="运行 Source Intelligence 或设置字段语义",
            next_en="Run Source Intelligence or set field semantics",
        )
    result_state, coverage = trusted_result_state(typed_intent, runtime=runtime, result_rows=rows)
    query = {
        **base_query,
        "runtime": runtime,
        "fallbackReason": fallback_reason,
        "executionCoverage": coverage,
        "resultState": result_state,
        "sqlIntent": "whitelist aggregate query; no user SQL accepted",
    }
    if apparel_method_result is not None:
        query["apparelMethodResult"] = apparel_method_result
    if result_state == "blocked":
        blocker_text = ", ".join(str(item) for item in coverage["blockers"])
        return _blocked_answer(
            title_zh="可信查询没有可发布结果",
            title_en="Trusted query has no publishable result",
            summary_zh=f"查询未形成可支撑经营结论的结果：{blocker_text}。",
            summary_en=f"The query did not produce evidence that can support a business conclusion: {blocker_text}.",
            query=query,
            evidence_refs=[
                {"type": "currentSourceRunBinding", **typed_intent["sourceRunBinding"]},
                {"type": "queryRuntime", "engine": runtime.get("engine"), "compiledSql": runtime.get("compiledSql"), "fallbackReason": fallback_reason},
                {"type": "queryExecutionCoverage", "complete": False, "blockers": coverage["blockers"]},
            ],
            next_zh="检查筛选范围和 current sourceRun 后重试",
            next_en="Review filters and the current sourceRun before retrying",
        )

    top_row = rows[0] if rows else {}
    total_value = sum(float(row.get("value") or 0) for row in rows) if dimension else float(top_row.get("value") or 0)
    top_label = str(top_row.get("label", "")) if dimension else ""
    top_value = float(top_row.get("value") or 0) if rows else 0.0
    top_share = top_value / total_value if total_value else 0.0
    metric_label = localized_value("记录数", "Rows") if measure == "*" else localized_value(measure, measure)
    summary = (
        localized_value(
            f"{top_label} 排名第一，{metric_label['zh']} {format_answer_number(top_value)}，占当前前 {len(rows)} 项合计 {top_share:.1%}。",
            f"{top_label} ranks first with {metric_label['en']} {format_answer_number(top_value)}, {top_share:.1%} of the top {len(rows)} total.",
        ) if dimension and rows else localized_value(
            f"当前 {metric_label['zh']} 为 {format_answer_number(top_value)}。",
            f"Current {metric_label['en']} is {format_answer_number(top_value)}.",
        )
    )
    method = str(typed_intent.get("method") or "overview")
    method_evidence = apparel_method_result.get("evidence") if isinstance(apparel_method_result, dict) else {}
    if method == "concentration" and isinstance(method_evidence, dict):
        summary = localized_value(
            f"前 {method_evidence.get('actualEntityPercent', 0):.1%} 的 {dimension} 贡献 {method_evidence.get('headContribution', 0):.1%}；并列边界已保留。",
            f"The top {method_evidence.get('actualEntityPercent', 0):.1%} of {dimension} contributes {method_evidence.get('headContribution', 0):.1%}; boundary ties are preserved.",
        )
        title = localized_value("头部集中度", "Head concentration")
    elif method == "pareto" and isinstance(method_evidence, dict):
        summary = localized_value(
            f"前 {method_evidence.get('actualEntityPercent', 0):.1%} 的 {dimension} 贡献 {method_evidence.get('headContribution', 0):.1%}；达到 80% 需要 {method_evidence.get('entityPercentToReach80', 0):.1%} 的实体。",
            f"The top {method_evidence.get('actualEntityPercent', 0):.1%} of {dimension} contributes {method_evidence.get('headContribution', 0):.1%}; reaching 80% requires {method_evidence.get('entityPercentToReach80', 0):.1%} of entities.",
        )
        title = localized_value("Pareto / 二八验证", "Pareto / 80-20 proof")
    elif method == "decile" and isinstance(method_evidence, dict):
        summary = localized_value(
            f"已按实体数量形成 {method_evidence.get('groupCount', 0)} 个十分位组，并在并列值处保持同组。",
            f"Created {method_evidence.get('groupCount', 0)} entity-count decile groups while keeping tied values together.",
        )
        title = localized_value("实体数量十分位", "Entity-count deciles")
    evidence_refs: list[dict[str, Any]] = [
        {"type": "currentSourceRunBinding", **typed_intent["sourceRunBinding"]},
        {"type": "queryExecutionCoverage", "complete": coverage["complete"], "rowCount": coverage["rowCount"]},
        {"type": "queryRuntime", "engine": runtime.get("engine"), "compiledSql": runtime.get("compiledSql"), "fallbackReason": fallback_reason},
        {"type": "ontologyFunction", "id": intent},
    ]
    if apparel_method_result is not None:
        evidence_refs.append({
            "type": "apparelMethodResult",
            "schema": apparel_method_result["schema"],
            "method": apparel_method_result["method"],
            "populationRowCount": apparel_method_result["populationRowCount"],
            "evidence": apparel_method_result["evidence"],
        })
    source_ref = _current_source_run_ref(typed_intent.get("sourceRunBinding"))
    if source_ref:
        evidence_refs.insert(0, {"type": "sourceRun", **source_ref})
    metric = _metric_ref(connection, table_key, measure, aggregation, dimension, resolved_workspace_id)
    if metric:
        evidence_refs.insert(1, {"type": "metricDefinition", **metric})
    return {
        "kind": intent,
        "resultState": result_state,
        "title": title,
        "summary": summary,
        "confidence": "query-runtime",
        "metrics": [
            {"label": metric_label, "value": format_answer_number(top_value), "rawValue": top_value, "unit": "rows" if measure == "*" else "value"},
            {"label": localized_value("样本行数", "Source rows"), "value": format_answer_number(registry["row_count"]), "rawValue": registry["row_count"], "unit": "rows"},
        ] + (
            [{"label": localized_value("头部贡献", "Head contribution"), "value": f"{float(method_evidence.get('headContribution') or 0):.1%}", "rawValue": float(method_evidence.get("headContribution") or 0), "unit": "ratio"}]
            if method in {"concentration", "pareto"} and isinstance(method_evidence, dict)
            else []
        ),
        "rows": rows,
        "query": query,
        "evidenceRefs": evidence_refs,
        "nextActions": [
            localized_value("审阅图表草案后再确认写入", "Review the chart draft before confirming the write") if widget_action
            else localized_value("指定业务字段后继续下钻", "Specify business fields to continue the analysis"),
            localized_value("打开证据查看查询口径", "Open evidence to inspect the query definition"),
        ],
    }
