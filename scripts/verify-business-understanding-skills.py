from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from analytical_skill_service import builtin_analytical_skills  # noqa: E402
from analysis_safety_guard import requires_verified_analysis_plan  # noqa: E402
from business_understanding_service import (  # noqa: E402
    apply_business_understanding_to_intent,
    build_business_understanding_frame,
    build_business_understanding_gap,
)


checks: list[dict[str, Any]] = []


def check(label: str, ok: bool, detail: Any = None) -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": None if ok else detail})


def intent(
    *,
    task_type: str = "overview",
    measures: list[dict[str, Any]] | None = None,
    dimensions: list[dict[str, Any]] | None = None,
    others: list[dict[str, Any]] | None = None,
    comparisons: list[str] | None = None,
    output: str = "answer",
) -> dict[str, Any]:
    return {
        "schema": "aibi-agent-intent-frame/v1",
        "taskType": task_type,
        "decisionGoal": None,
        "measureConcepts": measures or [],
        "dimensionConcepts": dimensions or [],
        "otherConcepts": others or [],
        "timeScope": None,
        "filters": [],
        "comparisons": comparisons or [],
        "requestedOutput": output,
        "grainExpectation": {"fields": [], "description": "aggregate-result"},
        "constraints": {"readOnlyAnalysis": True},
        "unresolved": [],
        "evidenceRefs": [],
        "confidence": {},
        "resolution": {"providerRequired": False, "silentDisambiguation": False},
    }


def field(table: str, name: str, role: str, alias: str | None = None) -> dict[str, Any]:
    return {
        "id": f"{table}.{name}",
        "tableKey": table,
        "tableName": table,
        "field": name,
        "role": role,
        "confidence": 0.98,
        "source": "confirmed-semantic",
        "matchedAlias": alias or name,
    }


def semantic(
    selected: list[dict[str, Any]] | None = None,
    *,
    status: str = "ready",
    unresolved: list[dict[str, Any]] | None = None,
    targets: list[dict[str, Any]] | None = None,
    comparison_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    selected_values = selected or []
    tables = list(dict.fromkeys(str(item.get("tableKey") or "") for item in selected_values if item.get("tableKey")))
    payload = {
        "schema": "aibi-semantic-query-plan/v1",
        "status": status,
        "fieldResolution": {"selected": selected_values, "unresolved": unresolved or []},
        "grain": {"tables": tables},
        "joinPlan": {
            "rootTable": tables[0] if tables else "",
            "requiredTables": tables,
            "targets": targets or [],
        },
    }
    if comparison_plan is not None:
        payload["comparisonPlan"] = comparison_plan
    return payload


builtins = builtin_analytical_skills()
runtime = {
    "schema": "aibi-analytical-skill-runtime/v1",
    "fingerprint": "r" * 64,
    "enabledAnalyticalSkills": builtins,
}
understanding_ids = {
    "business-question-framing",
    "metric-definition-resolution",
    "data-context-discovery",
    "cross-table-analysis-design",
    "change-driver-diagnosis",
    "analysis-verification",
}
check(
    "six-versioned-business-understanding-skills",
    {item["skillId"] for item in builtins if item["skillKind"] == "understanding"} == understanding_ids,
    [(item["skillId"], item["version"]) for item in builtins],
)

neutral_overview = build_business_understanding_frame(
    "概览当前数据",
    intent(),
    semantic(),
    {"terms": [], "rules": []},
    runtime,
)
check(
    "neutral-overview-does-not-demand-a-business-measure",
    neutral_overview["status"] == "ready"
    and "underspecified-question" not in neutral_overview["signals"]
    and neutral_overview["slots"]["decision-goal"]["status"] == "resolved",
    neutral_overview,
)

vague_overview = build_business_understanding_frame(
    "看看数据",
    intent(),
    semantic(),
    {"terms": [], "rules": []},
    runtime,
)
check(
    "vague-overview-still-requires-a-business-goal",
    vague_overview["status"] == "needs-clarification"
    and "underspecified-question" in vague_overview["signals"]
    and {"decision-goal", "measure"}.issubset(vague_overview["missingSlots"]),
    vague_overview,
)

region = field("sites", "region", "dimension")
unknown_measure = build_business_understanding_frame(
    "请按 region 计算风险成本指标",
    intent(dimensions=[region]),
    semantic([region]),
    {"terms": [], "rules": []},
    runtime,
)
check(
    "explicit-unknown-measure-never-falls-back-to-count",
    unknown_measure["status"] == "needs-clarification"
    and "missing-measure" in unknown_measure["signals"]
    and "measure" in unknown_measure["missingSlots"]
    and unknown_measure["activeClarification"]["slot"] == "measure",
    unknown_measure,
)

ratio_intent = intent()
ratio_plan = semantic(status="needs-clarification")
ratio = build_business_understanding_frame(
    "请计算退款率",
    ratio_intent,
    ratio_plan,
    {"terms": [], "rules": []},
    runtime,
)
ratio_again = build_business_understanding_frame(
    "请计算退款率",
    ratio_intent,
    ratio_plan,
    {"terms": [], "rules": []},
    runtime,
)
check(
    "unverified-ratio-blocks-before-proxy-aggregation",
    ratio["status"] == "needs-clarification"
    and {"numerator", "denominator", "grain"}.issubset(ratio["missingSlots"])
    and ratio["activeClarification"]["slot"] == "numerator"
    and "no-silent-proxy" in ratio["guards"],
    ratio,
)
check("business-frame-is-deterministic", ratio["fingerprint"] == ratio_again["fingerprint"], (ratio["fingerprint"], ratio_again["fingerprint"]))

for standalone_ratio_prompt in (
    "占比是多少",
    "请按渠道统计，比例是多少",
    "请给出，百分比",
    "退款订单占总订单多少%",
    "退款订单占总订单多少％",
    "退货订单占全部订单的百分之几",
):
    standalone_ratio = build_business_understanding_frame(
        standalone_ratio_prompt,
        ratio_intent,
        ratio_plan,
        {"terms": [], "rules": []},
        runtime,
    )
    check(
        f"standalone-ratio-syntax-is-blocked:{standalone_ratio_prompt}",
        "ratio-request" in standalone_ratio["signals"]
        and standalone_ratio["status"] == "needs-clarification"
        and requires_verified_analysis_plan(standalone_ratio_prompt),
        standalone_ratio,
    )

refund_count = field("orders", "refund_count", "measure", "退款订单数")
paid_count = field("orders", "paid_count", "measure", "已支付订单数")
explicit_ratio_intent = intent(measures=[
    {"concept": "退款订单数", "field": "refund_count", "tableKey": "orders", "role": "measure", "source": "confirmed-semantic", "confidence": 0.98},
    {"concept": "已支付订单数", "field": "paid_count", "tableKey": "orders", "role": "measure", "source": "confirmed-semantic", "confidence": 0.98},
])
explicit_ratio = build_business_understanding_frame(
    "计算退款率，分子用退款订单数，分母用已支付订单数，粒度为订单",
    explicit_ratio_intent,
    semantic([refund_count, paid_count]),
    {"terms": [], "rules": []},
    runtime,
)
check(
    "explicit-ratio-definition-fills-typed-slots-without-guessing",
    explicit_ratio["status"] == "ready"
    and explicit_ratio["slots"]["numerator"]["value"] == "退款订单数"
    and explicit_ratio["slots"]["denominator"]["value"] == "已支付订单数"
    and explicit_ratio["slots"]["grain"]["value"] == "订单",
    explicit_ratio,
)

knowledge = {
    "packId": "domain-example",
    "packVersion": "1.0.0",
    "ruleId": "confirmed-refund-rate",
    "title": "已确认退款率",
    "grain": "order",
    "metricDefinition": {
        "kind": "ratio",
        "metric": "已确认退款率",
        "numerator": "退款成功订单数",
        "denominator": "已支付订单数",
        "grain": "order",
    },
}
knowledge_ratio = build_business_understanding_frame(
    "请计算退款率",
    ratio_intent,
    ratio_plan,
    {"terms": [], "rules": []},
    runtime,
    knowledge_match=knowledge,
    enabled_domain_packs=["domain-example"],
)
check(
    "confirmed-domain-rule-resolves-ratio-components",
    knowledge_ratio["status"] == "ready"
    and all(knowledge_ratio["slots"][slot]["status"] == "resolved" for slot in ("numerator", "denominator", "grain"))
    and "underspecified-question" not in knowledge_ratio["signals"],
    knowledge_ratio,
)

non_ratio_knowledge = {
    "packId": "domain-example",
    "packVersion": "1.0.0",
    "ruleId": "virtual-logistics-exception",
    "title": "虚拟商品物流例外",
    "grain": "order",
}
non_ratio_knowledge_frame = build_business_understanding_frame(
    "请计算虚拟商品未发货率",
    ratio_intent,
    ratio_plan,
    {"terms": [], "rules": []},
    runtime,
    knowledge_match=non_ratio_knowledge,
    enabled_domain_packs=["domain-example"],
)
check(
    "non-ratio-domain-rule-cannot-fabricate-ratio-components",
    non_ratio_knowledge_frame["status"] == "needs-clarification"
    and {"numerator", "denominator"}.issubset(non_ratio_knowledge_frame["missingSlots"]),
    non_ratio_knowledge_frame,
)

user_id = field("users", "user_id", "identity_key", "用户")
distinct_intent = intent(others=[{"concept": "用户", "field": "user_id", "tableKey": "users", "role": "identity_key", "source": "confirmed-semantic", "confidence": 0.98}])
distinct = build_business_understanding_frame(
    "统计不重复用户数",
    distinct_intent,
    semantic([user_id]),
    {"terms": [], "rules": []},
    runtime,
)
check(
    "distinct-count-resolves-entity-key-and-grain",
    distinct["status"] == "ready"
    and distinct["slots"]["entity-key"]["value"] == "users.user_id"
    and distinct["slots"]["grain"]["value"]["distinctEntity"] == "users.user_id",
    distinct,
)

amount = field("orders", "net_sales", "measure", "成交额")
term = {
    "term_key": "term-revenue",
    "canonical_name": "成交额",
    "aliases": ["销售额"],
    "definition": "已完成订单的净销售金额",
    "scope_type": "field",
    "scope_ref": "orders.net_sales",
}
term_intent = intent(measures=[{"concept": "成交额", "field": "net_sales", "tableKey": "orders", "role": "measure", "source": "confirmed-context", "confidence": 0.98}])
term_without_rule = build_business_understanding_frame(
    "成交额是多少",
    term_intent,
    semantic([amount]),
    {"terms": [term], "rules": [{"title": "无关规则", "statement": "库存按件计算", "rule_type": "unit", "applies_to": ["inventory"]}]},
    runtime,
)
check(
    "business-term-never-borrows-unrelated-rule",
    term_without_rule["status"] == "needs-clarification" and "business-rule" in term_without_rule["missingSlots"],
    term_without_rule,
)
term_with_rule = build_business_understanding_frame(
    "成交额是多少",
    term_intent,
    semantic([amount]),
    {"terms": [term], "rules": [{"rule_key": "rule-revenue-unit", "title": "成交额单位", "statement": "成交额按元解释", "rule_type": "unit", "applies_to": ["orders"]}]},
    runtime,
)
check(
    "confirmed-term-field-and-rule-form-complete-business-context",
    term_with_rule["status"] == "ready"
    and term_with_rule["slots"]["field-binding"]["value"] == ["orders.net_sales"]
    and term_with_rule["slots"]["business-rule"]["status"] == "resolved",
    term_with_rule,
)

channel = field("orders", "channel", "dimension", "渠道")
refund_amount = field("refunds", "refund_amount", "measure", "退款金额")
path_candidate = {
    "tables": ["orders", "refunds"],
    "safeForPlanning": True,
    "risks": [],
    "hops": [{"relationKey": "orders-refunds", "fromTable": "orders", "toTable": "refunds"}],
}
cross_intent = intent(
    task_type="comparison",
    measures=[{"concept": "退款金额", "field": "refund_amount", "tableKey": "refunds", "role": "measure", "source": "confirmed-semantic", "confidence": 0.98}],
    dimensions=[{"concept": "渠道", "field": "channel", "tableKey": "orders", "role": "dimension", "source": "confirmed-semantic", "confidence": 0.98}],
)
cross_intent["grainExpectation"] = {"fields": ["orders.channel"], "description": "orders.channel"}
ambiguous_cross = build_business_understanding_frame(
    "跨表按渠道比较退款金额",
    cross_intent,
    semantic(
        [channel, refund_amount],
        status="needs-relationship",
        targets=[{"targetTable": "refunds", "paths": [path_candidate], "selectedPath": None, "requiresPathClarification": True}],
    ),
    {"terms": [], "rules": []},
    runtime,
)
check(
    "ambiguous-cross-table-path-asks-one-path-question",
    ambiguous_cross["status"] == "needs-clarification"
    and ambiguous_cross["activeClarification"]["slot"] == "relationship-path"
    and ambiguous_cross["clarification"]["askAtMostOne"] is True,
    ambiguous_cross,
)
verified_cross = build_business_understanding_frame(
    "跨表按渠道比较退款金额",
    cross_intent,
    semantic(
        [channel, refund_amount],
        targets=[{"targetTable": "refunds", "paths": [path_candidate], "selectedPath": path_candidate, "requiresPathClarification": False}],
    ),
    {"terms": [], "rules": []},
    runtime,
)
check(
    "verified-cross-table-path-carries-grain-and-guard",
    verified_cross["status"] == "ready"
    and verified_cross["slots"]["relationship-path"]["status"] == "resolved"
    and "verified-relationship-path" in verified_cross["guards"],
    verified_cross,
)

plain_comparison_intent = intent(
    task_type="comparison",
    measures=[{"concept": "成交额", "field": "net_sales", "tableKey": "orders", "role": "measure", "source": "confirmed-semantic", "confidence": 0.98}],
    dimensions=[{"concept": "渠道", "field": "channel", "tableKey": "orders", "role": "dimension", "source": "confirmed-semantic", "confidence": 0.98}],
)
plain_comparison = build_business_understanding_frame(
    "按渠道比较成交额",
    plain_comparison_intent,
    semantic([amount, channel]),
    {"terms": [], "rules": []},
    runtime,
)
check(
    "plain-comparison-does-not-activate-driver-diagnosis",
    plain_comparison["status"] == "ready"
    and "comparison-request" in plain_comparison["signals"]
    and "change-driver-diagnosis" not in {
        item["skillId"] for item in plain_comparison["supportingSkills"]
    }
    and "facts-before-hypotheses" not in plain_comparison["guards"],
    plain_comparison,
)

diagnosis_intent = intent(
    task_type="diagnosis",
    measures=[{"concept": "成交额", "field": "net_sales", "tableKey": "orders", "role": "measure", "source": "confirmed-semantic", "confidence": 0.98}],
    dimensions=[{"concept": "渠道", "field": "channel", "tableKey": "orders", "role": "dimension", "source": "confirmed-semantic", "confidence": 0.98}],
)
diagnosis = build_business_understanding_frame(
    "为什么成交额下降",
    diagnosis_intent,
    semantic([amount, channel]),
    {"terms": [], "rules": []},
    runtime,
)
check(
    "diagnosis-requires-explicit-comparison-baseline",
    diagnosis["status"] == "needs-clarification"
    and diagnosis["activeClarification"]["slot"] == "comparison-baseline"
    and "facts-before-hypotheses" in diagnosis["guards"],
    diagnosis,
)

time_comparison_intent = intent(
    task_type="comparison",
    measures=[{"concept": "成交额", "field": "net_sales", "tableKey": "orders", "role": "measure", "source": "confirmed-semantic", "confidence": 0.98}],
    dimensions=[{"concept": "日期", "field": "order_date", "tableKey": "orders", "role": "event_time", "source": "confirmed-semantic", "confidence": 0.98}],
    comparisons=["year-over-year"],
)
order_date = field("orders", "order_date", "event_time", "日期")
unverified_time_comparison = build_business_understanding_frame(
    "按 order_date 看 net_sales 同比",
    time_comparison_intent,
    semantic([amount, order_date]),
    {"terms": [], "rules": []},
    runtime,
)
check(
    "time-comparison-blocks-without-complete-window-plan",
    unverified_time_comparison["status"] == "needs-clarification"
    and {"time-scope", "comparison-baseline"}.issubset(unverified_time_comparison["missingSlots"]),
    unverified_time_comparison,
)

verified_time_comparison = build_business_understanding_frame(
    "按 order_date 看 net_sales 同比",
    time_comparison_intent,
    semantic(
        [amount, order_date],
        comparison_plan={
            "status": "ready",
            "timeField": "orders.order_date",
            "currentWindow": {"start": "2026-01-01", "end": "2026-06-30"},
            "baselineWindow": {"start": "2025-01-01", "end": "2025-06-30"},
        },
    ),
    {"terms": [], "rules": []},
    runtime,
)
check(
    "verified-comparison-plan-resolves-both-windows",
    verified_time_comparison["status"] == "ready"
    and verified_time_comparison["slots"]["comparison-baseline"]["source"] == "verified-comparison-plan",
    verified_time_comparison,
)

applied = apply_business_understanding_to_intent(ratio_intent, ratio)
gap = build_business_understanding_gap("请计算退款率", ratio, "orders")
check(
    "business-blocker-propagates-to-intent-and-safe-gap",
    any(item.get("slot") == "numerator" for item in applied["unresolved"])
    and gap["kind"] == "clarification"
    and gap["metrics"] == []
    and gap["rows"] == []
    and gap["clarification"]["kind"] == "compound-analysis-definition"
    and gap["clarification"]["businessKind"] == "business-slot"
    and gap["clarification"]["askAtMostOne"] is True,
    {"intent": applied, "gap": gap},
)

failed = [item for item in checks if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-business-understanding-skills-verify/v1",
    "checks": checks,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
