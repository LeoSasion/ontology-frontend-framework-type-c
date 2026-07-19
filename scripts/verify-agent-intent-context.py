from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from agent_clarification_service import build_agent_clarification  # noqa: E402
from agent_intent_service import build_business_intent_frame  # noqa: E402
from analytical_skill_service import builtin_analytical_skills  # noqa: E402
from business_understanding_service import (  # noqa: E402
    apply_business_understanding_to_intent,
    build_business_understanding_frame,
    build_business_understanding_gap,
)
from semantic_context_router import build_semantic_context_bundle  # noqa: E402

checks: list[dict[str, object]] = []


def check(label: str, ok: bool, detail: object = "") -> None:
    checks.append({"label": label, "ok": ok, "detail": "" if ok else detail})


TASK_CASES = {
    "reconciliation": ["核对两张表", "做一次对账", "检查是否一致", "reconcile both tables", "reconciliation report"],
    "diagnosis": ["为什么指标下降", "诊断变化原因", "分析驱动因素", "find the driver", "why did it change"],
    "anomaly": ["找出异常记录", "检查突增", "识别离群值", "detect anomaly", "find outlier"],
    "ranking": ["前 10 名", "查看排名", "找出最高分组", "top 10 groups", "rank categories"],
    "composition": ["查看构成", "分析占比", "查看结构份额", "show the mix", "share by group"],
    "trend": ["查看趋势", "按月走势", "同比变化", "show trend", "over time"],
    "comparison": ["比较两个分组", "查看差异", "与上期相比", "compare groups", "A vs B"],
    "overview": ["概览数据", "汇总数据", "给出总体情况", "summarize data", "show overview"],
}
generated = []
for expected, prompts in TASK_CASES.items():
    for prompt in prompts:
        for suffix in ["", "，只读回答", "，给我证据", " for this workspace", "，不要写入"]:
            generated.append((expected, build_business_intent_frame(f"{prompt}{suffix}", semantic_plan={})))

check("two-hundred-deterministic-intent-cases", len(generated) == 200, len(generated))
failures = [{"expected": expected, "actual": frame["taskType"], "reason": frame["resolution"]["taskTypeReason"]} for expected, frame in generated if frame["taskType"] != expected]
check("task-type-benchmark", not failures, failures[:20])
lexical_boundary_cases = {
    "概览当前数据": "overview",
    "当前数据概览": "overview",
    "查看前10名": "ranking",
    "查看前十组": "ranking",
}
lexical_boundary_failures = [
    {"prompt": prompt, "expected": expected, "actual": build_business_intent_frame(prompt, semantic_plan={})["taskType"]}
    for prompt, expected in lexical_boundary_cases.items()
    if build_business_intent_frame(prompt, semantic_plan={})["taskType"] != expected
]
check("ranking-prefix-does-not-confuse-current-data", not lexical_boundary_failures, lexical_boundary_failures)
check("provider-independent", all(frame["resolution"]["providerRequired"] is False for _, frame in generated))
check("no-silent-disambiguation", all(frame["resolution"]["silentDisambiguation"] is False for _, frame in generated))
forecast_parameters = build_business_intent_frame(
    "检查 value 按 event_date 合计的预测准备度，预测跨度为3，评估截止为2025-12-01，粒度为月",
    semantic_plan={},
)
check(
    "forecast-method-parameters-are-not-data-filters-or-month-windows",
    forecast_parameters["filters"] == [] and forecast_parameters["timeScope"] is None,
    forecast_parameters,
)
december_scope = build_business_intent_frame("查看2025-12销售额", semantic_plan={}).get("timeScope") or {}
check("two-digit-month-is-not-truncated", december_scope.get("parts", {}).get("month") == "12", december_scope)

semantic_plan = {
    "schema": "aibi-semantic-query-plan/v1", "status": "needs-clarification",
    "fieldResolution": {
        "selected": [{"id": "orders.amount", "tableKey": "orders", "field": "amount", "role": "measure", "confidence": 0.98, "source": "manual", "matchedAlias": "金额"}],
        "unresolved": [{"mention": "status", "reason": "multiple-field-candidates", "candidates": [
            {"id": "orders.status", "tableKey": "orders", "tableName": "订单", "field": "status", "role": "status", "confidence": 0.9},
            {"id": "refunds.status", "tableKey": "refunds", "tableName": "退款", "field": "status", "role": "status", "confidence": 0.9},
        ]}],
    }, "joinPlan": {"rootTable": "orders", "targets": []},
}
frame = build_business_intent_frame("按 status 看金额趋势", semantic_plan=semantic_plan)
skill_runtime = {
    "schema": "aibi-analytical-skill-runtime/v1",
    "workspaceId": "default",
    "enabledAnalyticalSkills": builtin_analytical_skills(),
    "fingerprint": "r" * 64,
}
business_understanding = build_business_understanding_frame(
    "按 status 看金额趋势",
    frame,
    semantic_plan,
    {"terms": [], "rules": []},
    skill_runtime,
)
frame = apply_business_understanding_to_intent(frame, business_understanding)
context = build_semantic_context_bundle(
    workspace_id="default", intent_frame=frame, semantic_plan=semantic_plan,
    selected_table={"table_key": "orders", "display_name": "订单"}, table_selection_confidence="explicit",
    context_matches={"terms": [], "rules": []}, recalled_queries=[], domain_pack_context={"enabledDomainPacks": []}, knowledge_match=None,
    analytical_skill_match=business_understanding["skillMatch"], business_understanding=business_understanding,
)
clarification = build_agent_clarification(frame, context, business_understanding)
check("intent-schema", frame["schema"] == "aibi-agent-intent-frame/v1", frame)
check("measure-provenance", frame["measureConcepts"][0]["tableKey"] == "orders", frame)
check("context-schema-and-fingerprint", context["schema"] == "aibi-semantic-context-bundle/v1" and len(context["fingerprint"]) == 64, context)
check("business-understanding-is-context-bound", context["businessUnderstanding"]["fingerprint"] == business_understanding["fingerprint"] and any(item.get("skillKind") == "understanding" for item in context["sources"]["analyticalSkills"]), context)
check("deterministic-plan-with-candidate-only-hybrid-recall", context["retrievalPolicy"] == {"strategy": "deterministic-hybrid", "reranker": "bounded-structured-score", "ambiguityGatePreserved": True, "candidateOnly": True}, context)
check("business-frame-contract", business_understanding["schema"] == "aibi-business-understanding-frame/v1" and business_understanding["status"] == "needs-clarification" and business_understanding["activeClarification"]["slot"] == "field-binding", business_understanding)
check("business-gap-is-one-question-and-non-executing", build_business_understanding_gap("按 status 看金额趋势", business_understanding, "orders")["rows"] == [] and len(business_understanding["unresolved"]) >= 1, business_understanding)
check("business-unresolved-merges-into-intent", frame["businessUnderstandingRef"]["fingerprint"] == business_understanding["fingerprint"] and any(item.get("kind") == "business-slot" for item in frame["unresolved"]), frame)
check("clarification-contract", clarification["required"] is True and len(clarification["items"]) == 1 and clarification["combined"] is False, clarification)
check("business-question-precedes-compatible-field-items", clarification["items"][0]["slot"] == "field-binding" and len(clarification["fieldItems"]) == 1, clarification)
check("candidate-table-provenance", all(candidate["tableKey"] for candidate in clarification["fieldItems"][0]["candidates"]), clarification)

ratio_plan = {"schema": "aibi-semantic-query-plan/v1", "status": "ready", "fieldResolution": {"selected": [], "unresolved": []}, "joinPlan": {"rootTable": "", "targets": []}}
ratio_intent = build_business_intent_frame("请计算退款率", semantic_plan=ratio_plan)
ratio_gap = build_business_understanding_frame("请计算退款率", ratio_intent, ratio_plan, {"terms": [], "rules": []}, skill_runtime)
ratio_knowledge = build_business_understanding_frame(
    "请计算退款率", ratio_intent, ratio_plan, {"terms": [], "rules": []}, skill_runtime,
    knowledge_match={
        "packId": "platform-commerce",
        "packVersion": "1.0.0",
        "ruleId": "refund-rate",
        "title": "退款率",
        "grain": "order",
        "metricDefinition": {
            "kind": "ratio",
            "metric": "退款率",
            "numerator": "退款成功订单数",
            "denominator": "已支付订单数",
            "grain": "order",
        },
    },
    enabled_domain_packs=["platform-commerce"],
)
check("ratio-without-components-fails-closed", ratio_gap["status"] == "needs-clarification" and {"numerator", "denominator"}.issubset(ratio_gap["missingSlots"]), ratio_gap)
check(
    "explicit-domain-rule-resolves-ratio-components",
    {"numerator", "denominator", "grain"}.issubset(ratio_knowledge["resolvedSlots"])
    and any(item["skillId"] == "metric-definition-resolution" for item in ratio_knowledge["skillMatch"]["supportingReady"]),
    ratio_knowledge,
)

result = {"ok": all(item["ok"] for item in checks), "schema": "aibi-agent-intent-context-verify/v1", "caseCount": len(generated), "checks": checks}
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result["ok"] else 1)
