from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from agent_clarification_service import build_agent_clarification  # noqa: E402
from agent_intent_service import build_business_intent_frame  # noqa: E402
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
check("provider-independent", all(frame["resolution"]["providerRequired"] is False for _, frame in generated))
check("no-silent-disambiguation", all(frame["resolution"]["silentDisambiguation"] is False for _, frame in generated))

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
context = build_semantic_context_bundle(
    workspace_id="default", intent_frame=frame, semantic_plan=semantic_plan,
    selected_table={"table_key": "orders", "display_name": "订单"}, table_selection_confidence="explicit",
    context_matches={"terms": [], "rules": []}, recalled_queries=[], domain_pack_context={"enabledDomainPacks": []}, knowledge_match=None,
)
clarification = build_agent_clarification(frame, context)
check("intent-schema", frame["schema"] == "aibi-agent-intent-frame/v1", frame)
check("measure-provenance", frame["measureConcepts"][0]["tableKey"] == "orders", frame)
check("context-schema-and-fingerprint", context["schema"] == "aibi-semantic-context-bundle/v1" and len(context["fingerprint"]) == 64, context)
check("deterministic-first-router", context["retrievalPolicy"] == {"strategy": "deterministic-first", "reranker": "disabled", "ambiguityGatePreserved": True}, context)
check("clarification-contract", clarification["required"] is True and len(clarification["items"]) == 1, clarification)
check("candidate-table-provenance", all(candidate["tableKey"] for candidate in clarification["items"][0]["candidates"]), clarification)

result = {"ok": all(item["ok"] for item in checks), "schema": "aibi-agent-intent-context-verify/v1", "caseCount": len(generated), "checks": checks}
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result["ok"] else 1)
