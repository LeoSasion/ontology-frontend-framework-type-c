from __future__ import annotations

import re
from typing import Any


INTENT_SCHEMA = "aibi-agent-intent-frame/v1"
TASK_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("reconciliation", ("对账", "核对", "一致", "reconcile", "reconciliation")),
    ("diagnosis", ("为什么", "原因", "诊断", "驱动", "why", "diagnose", "driver")),
    ("anomaly", ("异常", "离群", "突增", "突降", "anomaly", "outlier", "spike", "drop")),
    ("ranking", ("排名", "排行", "最高", "最低", "top ", "bottom ", "rank")),
    ("composition", ("构成", "占比", "份额", "结构", "composition", "share", "mix")),
    ("trend", ("趋势", "走势", "同比", "环比", "按月", "按周", "按日", "trend", "over time", "mom", "yoy")),
    ("comparison", ("比较", "对比", "差异", "相比", "versus", " vs ", "compare", "difference")),
)


def _compact(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _selected_fields(semantic_plan: dict[str, Any], roles: set[str]) -> list[dict[str, Any]]:
    selected = semantic_plan.get("fieldResolution", {}).get("selected") or []
    return [{
        "concept": str(item.get("matchedAlias") or item.get("field") or ""),
        "field": str(item.get("field") or ""),
        "tableKey": str(item.get("tableKey") or ""),
        "role": str(item.get("role") or "unknown"),
        "source": str(item.get("source") or "schema"),
        "confidence": round(float(item.get("confidence") or 0), 4),
    } for item in selected if str(item.get("role") or "") in roles]


def _task_type(prompt: str) -> tuple[str, float, str]:
    compact = _compact(prompt).casefold()
    normalized = f" {compact} "
    for task_type, patterns in TASK_PATTERNS:
        if task_type == "ranking" and re.search(
            r"前\s*(?:\d+|[一二三四五六七八九十百]+|几|n)\s*(?:名|个|条|位|组)?",
            compact,
            re.IGNORECASE,
        ):
            return task_type, 0.96, "lexical:ranked-prefix"
        matched = next((pattern for pattern in patterns if pattern.casefold() in normalized), None)
        if matched:
            return task_type, 0.96, f"lexical:{matched.strip()}"
    return "overview", 0.72, "default-safe-overview"


def _requested_output(prompt: str) -> str:
    lower = prompt.casefold()
    for output, tokens in (
        ("export", ("导出", "export", "下载")),
        ("dashboard-draft", ("看板", "仪表盘", "dashboard")),
        ("chart-draft", ("图表", "折线图", "柱状图", "饼图", "chart")),
        ("evidence", ("证据", "回执", "evidence", "receipt")),
    ):
        if any(token in lower for token in tokens):
            return output
    return "answer"


def _time_scope(prompt: str) -> dict[str, Any] | None:
    for pattern in (
        r"(?P<year>20\d{2})[-/.年](?P<month>0?[1-9]|1[0-2])(?:月)?",
        r"(?P<year>20\d{2})年",
        r"(?P<relative>今天|昨日|昨天|本周|上周|本月|上月|今年|去年|today|yesterday|this week|last week|this month|last month|this year|last year)",
    ):
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            return {"expression": match.group(0), "parts": {key: value for key, value in match.groupdict().items() if value}}
    return None


def _filters(prompt: str) -> list[dict[str, str]]:
    matches = re.finditer(r"([\u4e00-\u9fffA-Za-z_][\u4e00-\u9fffA-Za-z0-9_ .-]{0,30}?)\s*(=|等于|为|是|contains?|equals?)\s*([\u4e00-\u9fffA-Za-z0-9_.@\-]+)", prompt, re.IGNORECASE)
    return [{"fieldExpression": _compact(match.group(1)), "operator": match.group(2), "value": match.group(3)} for match in matches][:12]


def _comparisons(prompt: str) -> list[str]:
    lower = prompt.casefold()
    result: list[str] = []
    for key, tokens in {
        "year-over-year": ("同比", "yoy", "year over year"),
        "period-over-period": ("环比", "mom", "wow", "period over period"),
        "explicit-groups": ("对比", "比较", "相比", " versus ", " vs ", "compare"),
    }.items():
        if any(token in lower for token in tokens):
            result.append(key)
    return result


def _dimension_is_filter_only(
    prompt: str,
    dimension: dict[str, Any],
    filters: list[dict[str, str]],
) -> bool:
    normalized_prompt = _compact(prompt).casefold()
    aliases = {
        _compact(dimension.get("concept")).casefold(),
        _compact(dimension.get("field")).casefold(),
        _compact(f"{dimension.get('tableKey')}.{dimension.get('field')}").casefold(),
    }
    aliases.discard("")
    filter_expressions = [_compact(item.get("fieldExpression")).casefold() for item in filters]
    participates_in_filter = any(
        alias == expression or alias in expression or expression in alias
        for alias in aliases
        for expression in filter_expressions
        if expression
    )
    if not participates_in_filter:
        return False
    return max((normalized_prompt.count(alias) for alias in aliases), default=0) <= 1


def build_business_intent_frame(prompt: str, *, semantic_plan: dict[str, Any] | None = None, evidence_refs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    plan = semantic_plan if isinstance(semantic_plan, dict) else {}
    task_type, task_confidence, task_reason = _task_type(prompt)
    measures = _selected_fields(plan, {"measure"})
    dimensions = _selected_fields(plan, {"dimension", "event_time", "status"})
    other_fields = _selected_fields(plan, {"identity_key", "identity", "attribute", "unknown"})
    filters = _filters(prompt)
    unresolved = [{
        "kind": "field-binding",
        "mention": str(item.get("mention") or ""),
        "reason": str(item.get("reason") or "multiple-field-candidates"),
        "candidateCount": len(item.get("candidates") or []),
    } for item in plan.get("fieldResolution", {}).get("unresolved") or []]
    time_scope = _time_scope(prompt)
    grain_fields = [
        f"{item['tableKey']}.{item['field']}"
        for item in dimensions
        if item["field"] and not _dimension_is_filter_only(prompt, item, filters)
    ]
    output = _requested_output(prompt)
    return {
        "schema": INTENT_SCHEMA,
        "taskType": task_type,
        "decisionGoal": None,
        "measureConcepts": measures,
        "dimensionConcepts": dimensions,
        "otherConcepts": other_fields,
        "timeScope": time_scope,
        "filters": filters,
        "comparisons": _comparisons(prompt),
        "requestedOutput": output,
        "grainExpectation": {"fields": grain_fields, "description": " + ".join(grain_fields) if grain_fields else "aggregate-result"},
        "constraints": {"readOnlyAnalysis": output in {"answer", "evidence"}},
        "unresolved": unresolved,
        "evidenceRefs": list(evidence_refs or []),
        "confidence": {
            "taskType": task_confidence,
            "fieldBindings": round(min([float(item.get("confidence") or 0) for item in [*measures, *dimensions, *other_fields]] or [0.0]), 4),
            "timeScope": 0.95 if time_scope else 0.0,
            "requestedOutput": 0.98,
        },
        "resolution": {"taskTypeReason": task_reason, "providerRequired": False, "silentDisambiguation": False},
    }
