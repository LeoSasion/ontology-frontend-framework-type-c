from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

from analytical_skill_service import analytical_roles_from_intent_frame, match_analytical_skills


FRAME_SCHEMA = "aibi-business-understanding-frame/v1"

RATIO_PATTERN = re.compile(
    r"(?:(?:[\u4e00-\u9fff]率)|(?:占比|比例|比率|百分比|百分之)|[%％]|\b(?:rate|ratio|percentage|percent)\b)",
    re.IGNORECASE,
)
DISTINCT_PATTERN = re.compile(
    r"(?:去重|不重复|独立(?:用户|客户|订单|商品|实体)|unique\s+(?:count|users?|customers?|orders?)|distinct\s+(?:count|users?|customers?|orders?))",
    re.IGNORECASE,
)
MISSING_MEASURE_CUE_PATTERN = re.compile(
    r"(?:指标|度量|kpi|metric|measure)",
    re.IGNORECASE,
)
CROSS_TABLE_PATTERN = re.compile(
    r"(?:跨表|关联后|连接后|两张表|多张表|join\s+grain|after\s+join(?:ing)?)",
    re.IGNORECASE,
)
ARTIFACT_OUTPUTS = {"export", "dashboard-draft", "chart-draft"}
METHOD_SIGNAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("funnel-request", re.compile(r"(?:漏斗|转化路径|阶段转化|流失路径|\bfunnel\b|drop[ -]?off)", re.IGNORECASE)),
    ("cohort-retention-request", re.compile(r"(?:队列留存|分群留存|留存分析|\bcohort\s+retention\b|\bretention\s+cohort\b)", re.IGNORECASE)),
    ("anomaly-triage-request", re.compile(r"(?:异常(?:分诊|排查|定位|影响范围)|(?:分诊|排查|定位)异常|anomaly\s+triage|triage\s+anomal)", re.IGNORECASE)),
    ("segment-contribution-request", re.compile(r"(?:分群贡献|分组贡献|结构贡献|分段贡献|segment\s+contribution|contribution\s+by)", re.IGNORECASE)),
    ("driver-investigation-request", re.compile(r"(?:驱动(?:调查|因素|分析)|影响因素|原因调查|driver\s+investigation|root\s+cause)", re.IGNORECASE)),
    ("dashboard-decision-request", re.compile(r"(?:决策看板|决策仪表盘|监控看板设计|监控仪表盘设计|decision\s+dashboard|dashboard\s+design)", re.IGNORECASE)),
)

SLOT_PRIORITY = (
    "funnel-stages", "stage-order", "cohort-entry-event", "retention-event", "entity-key",
    "time-scope", "time-field", "cohort-period", "comparison-baseline", "anomaly-threshold",
    "contribution-total", "driver-candidates", "dashboard-audience", "review-cadence",
    "numerator", "denominator", "relationship-path", "grain",
    "field-binding", "business-rule", "term-definition", "time-scope", "comparison-baseline",
    "time-field", "measure", "dimension", "decision-goal", "source-profile",
    "output-purpose", "population", "filter-semantics", "status-meaning", "unit", "null-policy",
)

SLOT_QUESTIONS: dict[str, tuple[str, str]] = {
    "decision-goal": ("这次分析要支持哪个业务决策？", "Which business decision should this analysis support?"),
    "metric-concept": ("你要衡量的业务指标具体是什么？", "Which business metric should be measured?"),
    "measure": ("这次要计算哪个核心度量？", "Which core measure should be calculated?"),
    "dimension": ("你希望按哪个业务维度拆解结果？", "Which business dimension should break down the result?"),
    "time-scope": ("这次分析覆盖哪个时间范围？", "Which time window should this analysis cover?"),
    "time-field": ("应以哪个业务时间字段作为统计时间？", "Which business time field should define the analysis window?"),
    "comparison-baseline": ("变化要与哪个基线期间或对象比较？", "Which period or cohort is the comparison baseline?"),
    "numerator": ("这个比率的分子应统计什么业务事件或实体？", "What business event or entity should form the numerator?"),
    "denominator": ("这个比率的分母应采用哪个总体？", "Which population should form the denominator?"),
    "entity-key": ("去重计数应使用哪个业务实体键？", "Which business entity key should be used for the distinct count?"),
    "population": ("这个指标适用于哪一组业务对象？", "Which business population does this metric cover?"),
    "grain": ("结果应按什么业务粒度统计，才能避免重复计数？", "At what business grain should the result be calculated to avoid double counting?"),
    "field-binding": ("这个业务概念应绑定到哪个表和字段？", "Which table and field should this business concept bind to?"),
    "term-definition": ("这个业务术语在当前工作区中的确认定义是什么？", "What is the confirmed workspace definition of this business term?"),
    "business-rule": ("这个指标应遵循哪条已确认的业务规则？", "Which confirmed business rule should govern this metric?"),
    "relationship-path": ("跨表分析应采用哪条已验证的关系路径？", "Which verified relationship path should this cross-table analysis use?"),
    "source-profile": ("需要先确认哪个数据来源或字段画像可信？", "Which source or field profile should be trusted first?"),
    "output-purpose": ("你希望最终得到回答、图表、看板草稿还是导出？", "Should the output be an answer, chart, dashboard draft, or export?"),
    "filter-semantics": ("筛选条件中的业务状态应如何解释？", "How should the business status in the filter be interpreted?"),
    "status-meaning": ("这些状态值分别代表什么业务阶段？", "What business stage does each status value represent?"),
    "unit": ("这个指标使用什么单位？", "Which unit should this metric use?"),
    "null-policy": ("空值应排除、归零还是作为独立状态？", "Should nulls be excluded, treated as zero, or kept as a separate state?"),
    "funnel-stages": ("这个漏斗包含哪些已确认的业务阶段？", "Which confirmed business stages belong in this funnel?"),
    "stage-order": ("这些漏斗阶段应按什么先后顺序计算？", "In which order should the funnel stages be evaluated?"),
    "cohort-entry-event": ("哪个业务事件定义实体进入队列？", "Which business event defines cohort entry?"),
    "retention-event": ("哪个后续事件代表实体在观察期内留存？", "Which subsequent event represents retention in the observation window?"),
    "cohort-period": ("队列应按日、周还是月划分？", "Should cohorts be grouped by day, week, or month?"),
    "anomaly-threshold": ("什么阈值或规则才算业务异常？", "Which threshold or rule defines a business anomaly?"),
    "contribution-total": ("各分群贡献需要对账到哪个总体变化？", "Which total change should segment contributions reconcile to?"),
    "driver-candidates": ("应优先核查哪些有证据来源的候选驱动维度？", "Which evidence-backed candidate driver dimensions should be investigated first?"),
    "dashboard-audience": ("这个决策看板主要供谁使用？", "Who is the primary audience for this decision dashboard?"),
    "review-cadence": ("这个看板按什么节奏复核和刷新？", "At what cadence should this dashboard be reviewed and refreshed?"),
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def _explicit_labeled_value(prompt: str, labels: tuple[str, ...]) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"(?:{label_pattern})\s*(?:为|是|用|采用|按|=|:|：)\s*([^，,。；;\n]+)",
        prompt,
        re.IGNORECASE,
    )
    return _text(match.group(1)) if match else ""


def _unique_strings(values: list[Any]) -> list[str]:
    return list(dict.fromkeys(text for item in values if (text := _text(item))))


def _ordered_values(value: str) -> list[str]:
    if not value:
        return []
    parts = re.split(r"\s*(?:→|->|=>|>|＞|然后|再到|到)\s*", value)
    return _unique_strings(parts) if len(parts) >= 2 else []


def _evidence_ref(kind: str, **values: Any) -> dict[str, Any]:
    return {"type": kind, **{key: value for key, value in values.items() if value not in (None, "", [])}}


def _resolved(value: Any, source: str, evidence_refs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"status": "resolved", "value": value, "source": source, "evidenceRefs": list(evidence_refs or [])}


def _selected_fields(semantic_plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in _list(_record(semantic_plan.get("fieldResolution")).get("selected")) if isinstance(item, dict)]


def _qualified_field(item: dict[str, Any]) -> str:
    table_key, field = _text(item.get("tableKey")), _text(item.get("field"))
    return f"{table_key}.{field}" if table_key and field else field or table_key


def _field_refs(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        _evidence_ref(
            "fieldProvenance",
            tableKey=item.get("tableKey"),
            field=item.get("field"),
            role=item.get("role"),
            source=item.get("source"),
            confidence=item.get("confidence"),
        )
        for item in items
        if _qualified_field(item)
    ]


def _term_name(term: dict[str, Any]) -> str:
    return _text(term.get("canonical_name") or term.get("canonicalName") or term.get("name"))


def _term_ref(term: dict[str, Any]) -> dict[str, Any]:
    return _evidence_ref(
        "contextTerm",
        termKey=term.get("term_key") or term.get("termKey"),
        name=_term_name(term),
        scopeType=term.get("scope_type") or term.get("scopeType"),
        scopeRef=term.get("scope_ref") or term.get("scopeRef"),
    )


def _rule_ref(rule: dict[str, Any]) -> dict[str, Any]:
    return _evidence_ref(
        "contextRule",
        ruleKey=rule.get("rule_key") or rule.get("ruleKey"),
        title=rule.get("title"),
        ruleType=rule.get("rule_type") or rule.get("ruleType"),
    )


def _knowledge_ref(knowledge_match: dict[str, Any]) -> dict[str, Any]:
    return _evidence_ref(
        "knowledgeRule",
        packId=knowledge_match.get("packId"),
        version=knowledge_match.get("packVersion"),
        ruleId=knowledge_match.get("ruleId"),
        title=knowledge_match.get("title"),
    )


def _relevant_rules(terms: list[dict[str, Any]], rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not terms:
        return []
    term_tokens: set[str] = set()
    scope_refs: set[str] = set()
    for term in terms:
        term_tokens.add(_term_name(term).casefold())
        for alias in _list(term.get("aliases")):
            term_tokens.add(_text(alias).casefold())
        scope_ref = _text(term.get("scope_ref") or term.get("scopeRef"))
        if scope_ref:
            scope_refs.update({
                scope_ref.casefold(),
                scope_ref.rsplit(".", 1)[-1].casefold(),
                scope_ref.split(".", 1)[0].casefold(),
            })
    term_tokens.discard("")
    relevant: list[dict[str, Any]] = []
    for rule in rules:
        searchable = " ".join([_text(rule.get("title")), _text(rule.get("statement"))]).casefold()
        applies = {
            _text(item).casefold()
            for item in _list(rule.get("applies_to") or rule.get("appliesTo"))
            if _text(item)
        }
        if any(token in searchable for token in term_tokens) or bool(applies & scope_refs):
            relevant.append(rule)
    return relevant


def _selected_relationship_paths(semantic_plan: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    targets = [item for item in _list(_record(semantic_plan.get("joinPlan")).get("targets")) if isinstance(item, dict)]
    selected = [item["selectedPath"] for item in targets if isinstance(item.get("selectedPath"), dict)]
    candidates = [
        path
        for target in targets
        for path in _list(target.get("pathCandidates") or target.get("paths"))
        if isinstance(path, dict)
    ]
    return selected, candidates


def _signals(
    prompt: str,
    intent_frame: dict[str, Any],
    semantic_plan: dict[str, Any],
    context_matches: dict[str, Any],
) -> list[str]:
    normalized = _text(prompt).casefold()
    field_resolution = _record(semantic_plan.get("fieldResolution"))
    join_plan = _record(semantic_plan.get("joinPlan"))
    selected = _selected_fields(semantic_plan)
    unresolved = _list(field_resolution.get("unresolved"))
    targets = _list(join_plan.get("targets"))
    task_type = _text(intent_frame.get("taskType") or "overview")
    comparisons = _list(intent_frame.get("comparisons"))
    requested_output = _text(intent_frame.get("requestedOutput") or "answer")
    result: list[str] = []
    vague_phrases = {
        "看看数据", "分析数据", "概览数据", "汇总数据", "总体情况",
        "show data", "analyze data", "data overview", "summarize data",
    }
    has_measure = bool(_list(intent_frame.get("measureConcepts")))
    explicit_overview_tokens = (
        "概览", "汇总", "总体情况", "overview", "summarize", "summary",
    )
    neutral_overview = (
        task_type == "overview"
        and requested_output not in ARTIFACT_OUTPUTS
        and any(token in normalized for token in explicit_overview_tokens)
    )
    if not has_measure and not neutral_overview and (normalized in vague_phrases or len(normalized) <= 6):
        result.append("underspecified-question")
    ratio_request = bool(RATIO_PATTERN.search(prompt))
    distinct_request = bool(DISTINCT_PATTERN.search(prompt))
    if ratio_request:
        result.append("ratio-request")
    if distinct_request:
        result.append("distinct-count-request")
    if (
        not has_measure
        and selected
        and not unresolved
        and not neutral_overview
        and not ratio_request
        and not distinct_request
        and MISSING_MEASURE_CUE_PATTERN.search(prompt)
    ):
        result.append("missing-measure")
    if _list(context_matches.get("terms")):
        result.append("business-term-match")
    if any(item in {"year-over-year", "period-over-period"} for item in comparisons):
        result.append("time-comparison")
    if task_type == "diagnosis":
        result.append("diagnosis-request")
    if task_type == "comparison" or comparisons:
        result.append("comparison-request")
    required_tables = _list(join_plan.get("requiredTables"))
    if CROSS_TABLE_PATTERN.search(prompt) or len(required_tables) > 1 or bool(targets):
        result.append("cross-table-request")
    if _text(semantic_plan.get("status")) == "needs-relationship" or any(
        isinstance(item, dict) and (item.get("requiresPathClarification") or not isinstance(item.get("selectedPath"), dict))
        for item in targets
    ):
        result.append("relationship-ambiguity")
    if unresolved or ((ratio_request or distinct_request) and not selected):
        result.append("unresolved-field")
    quality_values = [semantic_plan.get("dataQualityRisk"), semantic_plan.get("warnings"), field_resolution.get("warnings")]
    if any(value for value in quality_values):
        result.append("data-quality-risk")
    if requested_output in ARTIFACT_OUTPUTS:
        result.append("artifact-request")
    for signal, pattern in METHOD_SIGNAL_PATTERNS:
        if pattern.search(prompt):
            result.append(signal)
    if _text(semantic_plan.get("status")) == "ready" and not unresolved and selected:
        result.append("executable-plan")
    return _unique_strings(result)


def _slot_state(
    prompt: str,
    intent_frame: dict[str, Any],
    semantic_plan: dict[str, Any],
    context_matches: dict[str, Any],
    knowledge_match: dict[str, Any] | None,
    signals: list[str],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    slots: dict[str, dict[str, Any]] = {}
    selected = _selected_fields(semantic_plan)
    field_evidence = _field_refs(selected)
    measures = [item for item in selected if _text(item.get("role")) == "measure"]
    dimensions = [item for item in selected if _text(item.get("role")) in {"dimension", "status", "event_time", "time"}]
    time_fields = [item for item in selected if _text(item.get("role")) in {"event_time", "time"}]
    identities = [item for item in selected if _text(item.get("role")) in {"identity", "identity_key"}]
    terms = [item for item in _list(context_matches.get("terms")) if isinstance(item, dict)]
    all_rules = [item for item in _list(context_matches.get("rules")) if isinstance(item, dict)]
    rules = _relevant_rules(terms, all_rules)
    term_refs = [_term_ref(item) for item in terms]
    rule_refs = [_rule_ref(item) for item in rules]
    knowledge = _record(knowledge_match)
    knowledge_refs = [_knowledge_ref(knowledge)] if knowledge else []
    evidence_refs = [*field_evidence, *term_refs, *rule_refs, *knowledge_refs]
    knowledge_business = _record(knowledge.get("businessDefinition"))

    if "underspecified-question" not in signals:
        slots["decision-goal"] = _resolved(_text(prompt), "explicit-question")
    if len(measures) == 1:
        slots["measure"] = _resolved(_qualified_field(measures[0]), "semantic-field", _field_refs(measures))
    elif knowledge:
        slots["measure"] = _resolved(_text(knowledge.get("title") or knowledge.get("ruleId")), "domain-pack-rule", knowledge_refs)
    if dimensions:
        slots["dimension"] = _resolved([_qualified_field(item) for item in dimensions], "semantic-fields", _field_refs(dimensions))
    explicit_measure = _explicit_labeled_value(prompt, ("指标", "度量", "metric", "measure"))
    explicit_dimension = _explicit_labeled_value(prompt, ("维度", "拆解维度", "dimension"))
    if explicit_measure and "measure" not in slots:
        slots["measure"] = _resolved(explicit_measure, "explicit-business-definition")
    if explicit_dimension and "dimension" not in slots:
        slots["dimension"] = _resolved(explicit_dimension, "explicit-business-definition")
    time_scope = intent_frame.get("timeScope")
    if isinstance(time_scope, dict) and _text(time_scope.get("expression")):
        slots["time-scope"] = _resolved(time_scope, "explicit-time-expression")
    if len(time_fields) == 1:
        slots["time-field"] = _resolved(_qualified_field(time_fields[0]), "semantic-field", _field_refs(time_fields))
    explicit_time_field = _explicit_labeled_value(prompt, ("时间字段", "统计时间", "time field"))
    if explicit_time_field and "time-field" not in slots:
        slots["time-field"] = _resolved(explicit_time_field, "explicit-business-definition")
    comparison_plan = _record(semantic_plan.get("comparisonPlan"))
    current_window = comparison_plan.get("currentWindow")
    baseline_window = comparison_plan.get("baselineWindow")
    if comparison_plan.get("status") == "ready" and current_window and baseline_window:
        slots["time-scope"] = _resolved(current_window, "verified-comparison-plan")
        slots["comparison-baseline"] = _resolved(baseline_window, "verified-comparison-plan")
        if _text(comparison_plan.get("timeField")):
            slots["time-field"] = _resolved(_text(comparison_plan.get("timeField")), "verified-comparison-plan")
    explicit_baseline = _explicit_labeled_value(prompt, ("对比基线", "比较基线", "基线", "baseline"))
    if explicit_baseline and "comparison-baseline" not in slots:
        slots["comparison-baseline"] = _resolved(explicit_baseline, "explicit-business-definition")
    requested_output = _text(intent_frame.get("requestedOutput") or "answer")
    if requested_output:
        slots["output-purpose"] = _resolved(requested_output, "explicit-output-intent")
    filters = _list(intent_frame.get("filters"))
    if filters:
        slots["population"] = _resolved(filters, "explicit-filters")
    explicit_population = _explicit_labeled_value(prompt, ("统计范围", "总体", "population"))
    if explicit_population and "population" not in slots:
        slots["population"] = _resolved(explicit_population, "explicit-business-definition")

    grain_fields = _list(_record(intent_frame.get("grainExpectation")).get("fields"))
    if grain_fields:
        slots["grain"] = _resolved(grain_fields, "intent-grain", field_evidence)
    elif knowledge and _text(knowledge.get("grain")):
        slots["grain"] = _resolved(_text(knowledge.get("grain")), "domain-pack-rule", knowledge_refs)
    explicit_grain = _explicit_labeled_value(prompt, ("统计粒度", "粒度", "grain"))
    if explicit_grain and "grain" not in slots:
        slots["grain"] = _resolved(explicit_grain, "explicit-business-definition")

    if len(identities) == 1:
        slots["entity-key"] = _resolved(_qualified_field(identities[0]), "semantic-field", _field_refs(identities))
        if "distinct-count-request" in signals:
            slots["grain"] = _resolved(
                {
                    "groupBy": grain_fields,
                    "distinctEntity": _qualified_field(identities[0]),
                },
                "distinct-entity-grain",
                [*_field_refs(dimensions), *_field_refs(identities)],
            )
    explicit_entity = _explicit_labeled_value(prompt, ("实体键", "去重键", "用户键", "entity key"))
    if explicit_entity and "entity-key" not in slots:
        slots["entity-key"] = _resolved(explicit_entity, "explicit-business-definition")

    if "funnel-request" in signals:
        raw_stages = _explicit_labeled_value(prompt, ("漏斗阶段", "阶段", "步骤", "stages"))
        ordered_stages = _ordered_values(raw_stages)
        if raw_stages:
            stages = ordered_stages or _unique_strings(re.split(r"\s*(?:、|/|\|)\s*", raw_stages))
            if len(stages) >= 2:
                slots["funnel-stages"] = _resolved(stages, "explicit-business-definition")
        if ordered_stages:
            slots["stage-order"] = _resolved(ordered_stages, "explicit-business-definition")

    if "cohort-retention-request" in signals:
        entry_event = _explicit_labeled_value(prompt, ("入组事件", "进入事件", "首次事件", "cohort entry"))
        retention_event = _explicit_labeled_value(prompt, ("留存事件", "回访事件", "后续事件", "retention event"))
        cohort_period = _explicit_labeled_value(prompt, ("队列周期", "分群周期", "cohort period"))
        if entry_event:
            slots["cohort-entry-event"] = _resolved(entry_event, "explicit-business-definition")
        if retention_event:
            slots["retention-event"] = _resolved(retention_event, "explicit-business-definition")
        if cohort_period:
            slots["cohort-period"] = _resolved(cohort_period, "explicit-business-definition")

    if "anomaly-triage-request" in signals:
        threshold = _explicit_labeled_value(prompt, ("异常阈值", "异常标准", "阈值", "threshold"))
        if threshold:
            slots["anomaly-threshold"] = _resolved(threshold, "explicit-business-definition")

    if "segment-contribution-request" in signals:
        contribution_total = _explicit_labeled_value(prompt, ("贡献总体", "总体变化", "对账总体", "contribution total"))
        if contribution_total:
            slots["contribution-total"] = _resolved(contribution_total, "explicit-business-definition")

    if "driver-investigation-request" in signals:
        candidates = _explicit_labeled_value(prompt, ("候选驱动", "驱动维度", "候选维度", "driver candidates"))
        candidate_values = _unique_strings(re.split(r"\s*(?:、|/|\||，|,)\s*", candidates)) if candidates else []
        if not candidate_values and dimensions:
            candidate_values = [_qualified_field(item) for item in dimensions]
        if candidate_values:
            slots["driver-candidates"] = _resolved(candidate_values, "explicit-business-definition" if candidates else "semantic-fields", _field_refs(dimensions))

    if "dashboard-decision-request" in signals:
        audience = _explicit_labeled_value(prompt, ("使用者", "受众", "决策者", "audience"))
        cadence = _explicit_labeled_value(prompt, ("复核节奏", "刷新节奏", "更新频率", "cadence"))
        if audience:
            slots["dashboard-audience"] = _resolved(audience, "explicit-business-definition")
        if cadence:
            slots["review-cadence"] = _resolved(cadence, "explicit-business-definition")

    if terms:
        first = terms[0]
        slots["term-definition"] = _resolved(
            {"term": _term_name(first), "definition": _text(first.get("definition"))},
            "confirmed-context-term",
            term_refs,
        )
        scope_refs = _unique_strings([term.get("scope_ref") or term.get("scopeRef") for term in terms])
        if scope_refs:
            slots["field-binding"] = _resolved(scope_refs, "confirmed-context-scope", term_refs)
        if rules:
            slots["business-rule"] = _resolved(
                [{"title": rule.get("title"), "statement": rule.get("statement")} for rule in rules],
                "confirmed-context-rule",
                rule_refs,
            )
        for slot_name, rule_types in {
            "unit": {"unit"},
            "null-policy": {"null", "missing-value"},
            "status-meaning": {"enum", "status"},
            "filter-semantics": {"enum", "status", "filter"},
        }.items():
            matching = [rule for rule in rules if _text(rule.get("rule_type") or rule.get("ruleType")) in rule_types]
            if matching:
                slots[slot_name] = _resolved([rule.get("statement") for rule in matching], "confirmed-context-rule", [_rule_ref(item) for item in matching])

    unresolved_fields = _list(_record(semantic_plan.get("fieldResolution")).get("unresolved"))
    if selected and not unresolved_fields and "field-binding" not in slots:
        slots["field-binding"] = _resolved([_qualified_field(item) for item in selected], "semantic-fields", field_evidence)
    elif knowledge and _list(knowledge_business.get("fieldBindings")) and "field-binding" not in slots:
        slots["field-binding"] = _resolved(
            _unique_strings(_list(knowledge_business.get("fieldBindings"))),
            "domain-pack-business-definition",
            knowledge_refs,
        )
    if selected and "data-quality-risk" in signals:
        slots["source-profile"] = _resolved(
            [{"field": _qualified_field(item), "source": item.get("source"), "confidence": item.get("confidence")} for item in selected],
            "semantic-field-profile",
            field_evidence,
        )

    selected_paths, _ = _selected_relationship_paths(semantic_plan)
    safe_paths = [path for path in selected_paths if path.get("safeForPlanning") is True]
    if selected_paths and len(safe_paths) == len(selected_paths):
        path_values = [{"tables": path.get("tables") or [], "hopCount": len(_list(path.get("hops")))} for path in safe_paths]
        slots["relationship-path"] = _resolved(path_values, "verified-semantic-path", [
            _evidence_ref("relationshipPath", tables=path.get("tables") or [], fingerprint=path.get("fingerprint"))
            for path in safe_paths
        ])
    elif knowledge and "cross-table-request" in signals:
        slots["relationship-path"] = _resolved(
            {"packId": knowledge.get("packId"), "ruleId": knowledge.get("ruleId")},
            "domain-pack-rule",
            knowledge_refs,
        )

    if "ratio-request" in signals:
        concept = _text(knowledge.get("title")) if knowledge else (_term_name(terms[0]) if terms else _text(prompt))
        slots["metric-concept"] = _resolved(concept, "business-question" if not knowledge else "domain-pack-rule", knowledge_refs or term_refs)
        metric_definition = _record(knowledge.get("metricDefinition"))
        if knowledge and metric_definition.get("kind") == "ratio" and all(
            _text(metric_definition.get(key)) for key in ("metric", "numerator", "denominator", "grain")
        ):
            slots["metric-concept"] = _resolved(_text(metric_definition.get("metric")), "domain-pack-metric-definition", knowledge_refs)
            slots["numerator"] = _resolved(_text(metric_definition.get("numerator")), "domain-pack-metric-definition", knowledge_refs)
            slots["denominator"] = _resolved(_text(metric_definition.get("denominator")), "domain-pack-metric-definition", knowledge_refs)
            slots["grain"] = _resolved(_text(metric_definition.get("grain")), "domain-pack-metric-definition", knowledge_refs)
        else:
            numerator = _explicit_labeled_value(prompt, ("分子", "numerator"))
            denominator = _explicit_labeled_value(prompt, ("分母", "denominator"))
            explicit_grain = _explicit_labeled_value(prompt, ("粒度", "grain"))
            if not explicit_grain:
                grain_match = re.search(r"按\s*([^，,。；;\n]{1,24}?)\s*粒度", prompt, re.IGNORECASE)
                explicit_grain = _text(grain_match.group(1)) if grain_match else ""
            if numerator:
                slots["numerator"] = _resolved(numerator, "explicit-business-definition")
            if denominator:
                slots["denominator"] = _resolved(denominator, "explicit-business-definition")
            if explicit_grain:
                slots["grain"] = _resolved(explicit_grain, "explicit-business-definition")
    elif "distinct-count-request" in signals:
        slots["metric-concept"] = _resolved(_text(prompt), "business-question")
    elif measures:
        slots["metric-concept"] = _resolved(_qualified_field(measures[0]), "semantic-field", _field_refs(measures[:1]))
    elif terms:
        slots["metric-concept"] = _resolved(_term_name(terms[0]), "confirmed-context-term", term_refs)

    if knowledge and _text(knowledge_business.get("entityKey")):
        slots["entity-key"] = _resolved(
            _text(knowledge_business.get("entityKey")),
            "domain-pack-business-definition",
            knowledge_refs,
        )

    return slots, evidence_refs


def _clarification_for_slot(slot: str, skill_id: str, semantic_plan: dict[str, Any]) -> dict[str, Any]:
    zh, en = SLOT_QUESTIONS.get(slot, (f"请确认 {slot} 的业务定义。", f"Please confirm the business definition for {slot}."))
    candidates: list[dict[str, Any]] = []
    if slot == "field-binding":
        candidates = [
            candidate
            for item in _list(_record(semantic_plan.get("fieldResolution")).get("unresolved"))
            if isinstance(item, dict)
            for candidate in _list(item.get("candidates"))
            if isinstance(candidate, dict)
        ][:12]
    elif slot == "relationship-path":
        _, candidates = _selected_relationship_paths(semantic_plan)
        candidates = candidates[:8]
    return {
        "kind": "business-slot",
        "slot": slot,
        "mention": slot,
        "question": zh,
        "questionLocalized": {"zh": zh, "en": en},
        "reason": "required-by-understanding-skill",
        "skillId": skill_id,
        "candidates": candidates,
    }


def _analysis_method_plan(skill_match: dict[str, Any], slots: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    selected = _record(skill_match.get("selected"))
    if selected.get("skillKind") != "analysis" or selected.get("outputSchema") != "aibi-analysis-method-plan/v1":
        return None
    required_slots = _unique_strings(_list(selected.get("requiredSlots")))
    missing_slots = _unique_strings(_list(selected.get("missingSlots")))
    resolved_slots = {slot: copy.deepcopy(slots[slot]) for slot in required_slots if slot in slots}
    material = {
        "schema": "aibi-analysis-method-plan/v1",
        "skillId": selected.get("skillId"),
        "skillVersion": selected.get("version"),
        "skillFingerprint": selected.get("fingerprint"),
        "status": "blocked" if missing_slots or selected.get("status") == "blocked" else "ready",
        "activeSignals": _unique_strings(_list(selected.get("activeSignals"))),
        "steps": _unique_strings(_list(selected.get("stepTemplate"))),
        "requiredSlots": required_slots,
        "resolvedSlots": resolved_slots,
        "missingSlots": missing_slots,
        "requiredEvidence": _unique_strings(_list(selected.get("requiredEvidence"))),
        "semanticGuards": _unique_strings(_list(selected.get("semanticGuards"))),
        "allowedCapabilities": _unique_strings(_list(selected.get("allowedCapabilities"))),
        "resourceLimits": copy.deepcopy(_record(selected.get("resourceLimits"))),
    }
    return {**material, "fingerprint": _fingerprint(material)}


def build_business_understanding_frame(
    prompt: str,
    intent_frame: dict[str, Any],
    semantic_plan: dict[str, Any],
    context_matches: dict[str, Any],
    analytical_skill_runtime: dict[str, Any],
    *,
    knowledge_match: dict[str, Any] | None = None,
    enabled_domain_packs: list[str] | None = None,
) -> dict[str, Any]:
    signals = _signals(prompt, intent_frame, semantic_plan, context_matches)
    # A confirmed Domain Pack rule is itself a precise business intent. It may
    # legitimately resolve a named metric even when no physical measure field
    # appears in the generic semantic planner.
    if knowledge_match and "underspecified-question" in signals:
        signals = [item for item in signals if item != "underspecified-question"]
    if knowledge_match and not _list(_record(semantic_plan.get("fieldResolution")).get("unresolved")):
        signals = [item for item in signals if item != "unresolved-field"]
    slots, evidence_refs = _slot_state(
        prompt,
        intent_frame,
        semantic_plan,
        context_matches,
        knowledge_match,
        signals,
    )
    packs = _unique_strings([
        *(enabled_domain_packs or []),
        _record(knowledge_match).get("packId"),
    ])
    skill_match = match_analytical_skills(
        analytical_skill_runtime,
        task_type=_text(intent_frame.get("taskType") or "overview"),
        roles=analytical_roles_from_intent_frame(intent_frame),
        enabled_domain_packs=packs,
        business_signals=signals,
        intent_slots=slots,
    )
    supporting = [item for item in _list(skill_match.get("supporting")) if isinstance(item, dict)]
    selected_skill = _record(skill_match.get("selected"))
    method_plan = _analysis_method_plan(skill_match, slots)
    missing_by_slot: dict[str, str] = {}
    blockers: list[dict[str, Any]] = []
    governed_skills = [*([selected_skill] if method_plan else []), *supporting]
    for skill in governed_skills:
        for slot in _list(skill.get("missingSlots")):
            slot_name = _text(slot)
            if not slot_name:
                continue
            missing_by_slot.setdefault(slot_name, _text(skill.get("skillId")))
            blockers.append({
                "kind": "business-slot",
                "slot": slot_name,
                "mention": slot_name,
                "reason": "required-by-understanding-skill",
                "skillId": skill.get("skillId"),
            })
        for role in _list(skill.get("missingRoles")):
            blockers.append({
                "kind": "analytical-role",
                "mention": _text(role),
                "reason": "required-by-understanding-skill",
                "skillId": skill.get("skillId"),
            })
        for pack in _list(skill.get("missingDomainPacks")):
            blockers.append({
                "kind": "domain-pack",
                "mention": _text(pack),
                "reason": "required-by-understanding-skill",
                "skillId": skill.get("skillId"),
            })
    priority = {slot: index for index, slot in enumerate(SLOT_PRIORITY)}
    ordered_missing = sorted(missing_by_slot, key=lambda slot: (priority.get(slot, len(priority)), slot))
    unresolved = [_clarification_for_slot(slot, missing_by_slot[slot], semantic_plan) for slot in ordered_missing]
    active = unresolved[0] if unresolved else None
    guards = _unique_strings([guard for skill in governed_skills for guard in _list(skill.get("semanticGuards"))])
    required_evidence = _unique_strings([item for skill in governed_skills for item in _list(skill.get("requiredEvidence"))])
    status = "needs-clarification" if blockers else "ready"
    material = {
        "schema": FRAME_SCHEMA,
        "status": status,
        "signals": signals,
        "slots": slots,
        "unresolved": unresolved,
        "supportingSkills": supporting,
        "guards": guards,
        "requiredEvidence": required_evidence,
        "blockers": blockers,
        "activeClarification": active,
        "evidenceRefs": evidence_refs,
        "methodPlan": method_plan,
        "skillMatchFingerprint": skill_match.get("fingerprint"),
    }
    return {
        **material,
        "resolvedSlots": sorted(slots),
        "missingSlots": ordered_missing,
        "clarification": {"active": active, "items": unresolved, "askAtMostOne": True},
        "skillMatch": skill_match,
        "fingerprint": _fingerprint(material),
    }


def apply_business_understanding_to_intent(
    intent_frame: dict[str, Any],
    business_understanding: dict[str, Any],
) -> dict[str, Any]:
    result = copy.deepcopy(intent_frame)
    unresolved = [item for item in _list(result.get("unresolved")) if isinstance(item, dict)]
    for item in _list(business_understanding.get("unresolved")):
        if not isinstance(item, dict):
            continue
        normalized = {
            "kind": _text(item.get("kind") or "business-slot"),
            "mention": _text(item.get("mention") or item.get("slot")),
            "reason": _text(item.get("reason") or "business-slot-unresolved"),
            "candidateCount": len(_list(item.get("candidates"))),
            "slot": item.get("slot"),
        }
        identity = (normalized["kind"], normalized["mention"])
        if not any((_text(existing.get("kind")), _text(existing.get("mention"))) == identity for existing in unresolved):
            unresolved.append(normalized)
    result["unresolved"] = unresolved
    result["businessUnderstandingRef"] = {
        "schema": business_understanding.get("schema"),
        "status": business_understanding.get("status"),
        "fingerprint": business_understanding.get("fingerprint"),
    }
    result["businessSlots"] = copy.deepcopy(_record(business_understanding.get("slots")))
    result["evidenceRefs"] = [
        *_list(result.get("evidenceRefs")),
        *_list(business_understanding.get("evidenceRefs")),
    ]
    decision_goal = _record(_record(business_understanding.get("slots")).get("decision-goal"))
    if decision_goal.get("status") == "resolved":
        result["decisionGoal"] = decision_goal.get("value")
    return result


def build_business_understanding_gap(
    prompt: str,
    business_understanding: dict[str, Any],
    table_key: str | None,
) -> dict[str, Any]:
    active = _record(business_understanding.get("activeClarification"))
    question = _text(active.get("question")) or "请先确认缺失的业务口径。"
    question_localized = _record(active.get("questionLocalized"))
    skill_id = _text(active.get("skillId"))
    missing_slots = _unique_strings(_list(business_understanding.get("missingSlots")))
    clarification_kind = _text(active.get("kind") or "business-understanding")
    if skill_id == "metric-definition-resolution" and any(
        slot in {"numerator", "denominator"} for slot in missing_slots
    ):
        # Keep the established answer-card contract for compound metrics while
        # retaining the richer business slot and one-question clarification.
        clarification_kind = "compound-analysis-definition"
    return {
        "kind": "clarification",
        "title": {"zh": "需要先确认业务口径", "en": "Confirm the business definition"},
        "summary": {
            "zh": "助手已识别问题结构，但关键业务口径仍缺少可验证定义。为避免静默代用字段或给出近似数字，本次不执行分析。",
            "en": "The assistant recognized the question structure, but a material business definition is still unverified. No analysis was executed and no proxy field was substituted.",
        },
        "confidence": "missing",
        "metrics": [],
        "rows": [],
        "clarification": {
            "kind": clarification_kind,
            "businessKind": _text(active.get("kind") or "business-understanding"),
            "slot": active.get("slot"),
            "question": question,
            "questionLocalized": question_localized or {"zh": question, "en": question},
            "required": missing_slots,
            "askAtMostOne": True,
            "originalQuestion": prompt,
        },
        "evidenceRefs": [
            _evidence_ref("table", tableKey=table_key) if table_key else _evidence_ref("workspace"),
            _evidence_ref(
                "businessUnderstanding",
                fingerprint=business_understanding.get("fingerprint"),
                skillId=skill_id,
                status=business_understanding.get("status"),
            ),
            *_list(business_understanding.get("evidenceRefs")),
        ],
        "nextActions": [{
            "zh": question,
            "en": _text(question_localized.get("en")) or "Confirm the missing business definition and retry.",
        }],
    }
