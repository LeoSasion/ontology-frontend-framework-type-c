from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from agent_evidence_plan_service import build_evidence_plan  # noqa: E402
from agent_policy_hook_service import evaluate_agent_policy_hooks  # noqa: E402
from analytical_skill_service import builtin_analytical_skills, match_analytical_skills  # noqa: E402
from business_understanding_service import build_business_understanding_frame  # noqa: E402


checks: list[dict[str, Any]] = []


def check(label: str, ok: bool, detail: Any = None) -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": None if ok else detail})


builtins = builtin_analytical_skills()
runtime = {
    "schema": "aibi-analytical-skill-runtime/v1",
    "fingerprint": "r" * 64,
    "enabledAnalyticalSkills": builtins,
}
method_cases = (
    ("funnel-analysis", "funnel-request", "overview", "请做漏斗分析"),
    ("cohort-retention-analysis", "cohort-retention-request", "overview", "请做队列留存分析"),
    ("business-anomaly-triage", "anomaly-triage-request", "anomaly", "请做异常排查"),
    ("segment-contribution", "segment-contribution-request", "composition", "请做分群贡献分析"),
    ("driver-investigation", "driver-investigation-request", "diagnosis", "请做驱动因素调查"),
    ("dashboard-decision-design", "dashboard-decision-request", "overview", "请设计决策看板"),
)
method_ids = {item[0] for item in method_cases}
catalog_methods = {item["skillId"] for item in builtins if item.get("outputSchema") == "aibi-analysis-method-plan/v1"}
check("six-method-skills-are-versioned-builtins", catalog_methods == method_ids, sorted(catalog_methods))
check(
    "method-skills-are-declarative-and-bounded",
    all(
        item.get("triggerSignals")
        and item.get("slotRules")
        and item.get("semanticGuards")
        and item.get("stepTemplate")
        and int(item.get("resourceLimits", {}).get("maxSteps") or 0) <= 32
        and int(item.get("resourceLimits", {}).get("maxRows") or 0) <= 2000
        for item in builtins if item["skillId"] in method_ids
    ),
    [item for item in builtins if item["skillId"] in method_ids],
)

generic = match_analytical_skills(
    runtime,
    task_type="overview",
    roles=["measure"],
    enabled_domain_packs=[],
    business_signals=[],
    intent_slots={},
)
check(
    "specialized-methods-never-steal-a-generic-overview",
    generic.get("selected", {}).get("skillId") == "overview"
    and not method_ids.intersection(item["skillId"] for item in generic.get("candidates") or []),
    generic,
)

for skill_id, signal, task_type, _ in method_cases:
    matched = match_analytical_skills(
        runtime,
        task_type=task_type,
        roles=[],
        enabled_domain_packs=[],
        business_signals=[signal],
        intent_slots={},
    )
    selected = matched.get("selected") or {}
    check(
        f"specialized-signal-selects:{skill_id}",
        selected.get("skillId") == skill_id
        and selected.get("status") == "blocked"
        and selected.get("activeSignals") == [signal]
        and bool(selected.get("missingSlots"))
        and matched.get("selectionRequired") is False,
        matched,
    )


def intent_frame(task_type: str, *, output: str = "answer") -> dict[str, Any]:
    return {
        "schema": "aibi-agent-intent-frame/v1",
        "taskType": task_type,
        "decisionGoal": None,
        "measureConcepts": [],
        "dimensionConcepts": [],
        "otherConcepts": [],
        "timeScope": None,
        "filters": [],
        "comparisons": [],
        "requestedOutput": output,
        "grainExpectation": {"fields": [], "description": "aggregate-result"},
        "constraints": {"readOnlyAnalysis": True},
        "unresolved": [],
        "evidenceRefs": [],
        "confidence": {},
        "resolution": {"providerRequired": False, "silentDisambiguation": False},
    }


empty_semantic = {
    "schema": "aibi-semantic-query-plan/v1",
    "status": "needs-clarification",
    "fieldResolution": {"selected": [], "unresolved": []},
    "grain": {"tables": []},
    "joinPlan": {"rootTable": "", "requiredTables": [], "targets": []},
}
for skill_id, signal, task_type, prompt in method_cases:
    frame = build_business_understanding_frame(
        prompt,
        intent_frame(task_type, output="dashboard-draft" if skill_id == "dashboard-decision-design" else "answer"),
        empty_semantic,
        {"terms": [], "rules": []},
        runtime,
    )
    method_plan = frame.get("methodPlan") or {}
    check(
        f"incomplete-method-asks-one-high-value-question:{skill_id}",
        signal in frame.get("signals", [])
        and frame.get("status") == "needs-clarification"
        and frame.get("skillMatch", {}).get("selected", {}).get("skillId") == skill_id
        and method_plan.get("schema") == "aibi-analysis-method-plan/v1"
        and method_plan.get("status") == "blocked"
        and len(frame.get("clarification", {}).get("items") or []) >= 1
        and frame.get("clarification", {}).get("askAtMostOne") is True
        and frame.get("activeClarification") == frame.get("clarification", {}).get("items", [None])[0],
        frame,
    )

identity = {
    "id": "events.user_id", "tableKey": "events", "tableName": "Events", "field": "user_id",
    "role": "identity_key", "confidence": 0.99, "source": "confirmed-semantic", "matchedAlias": "user_id",
}
event_time = {
    "id": "events.event_at", "tableKey": "events", "tableName": "Events", "field": "event_at",
    "role": "event_time", "confidence": 0.99, "source": "confirmed-semantic", "matchedAlias": "event_at",
}
complete_intent = intent_frame("overview")
complete_intent["otherConcepts"] = [{"concept": "user_id", "field": "user_id", "tableKey": "events", "role": "identity_key", "source": "confirmed-semantic", "confidence": 0.99}]
complete_intent["dimensionConcepts"] = [{"concept": "event_at", "field": "event_at", "tableKey": "events", "role": "event_time", "source": "confirmed-semantic", "confidence": 0.99}]
complete_intent["timeScope"] = {"expression": "本月", "parts": {"relative": "本月"}}
complete_intent["grainExpectation"] = {"fields": ["events.user_id"], "description": "events.user_id"}
complete_semantic = {
    "schema": "aibi-semantic-query-plan/v1",
    "status": "ready",
    "fieldResolution": {"selected": [identity, event_time], "unresolved": []},
    "grain": {"tables": ["events"]},
    "joinPlan": {"rootTable": "events", "requiredTables": ["events"], "targets": []},
}
complete_funnel = build_business_understanding_frame(
    "漏斗分析，阶段为访问 > 注册 > 激活，实体键为 user_id，统计范围为全部用户，时间字段为 event_at，本月，粒度为用户",
    complete_intent,
    complete_semantic,
    {"terms": [], "rules": []},
    runtime,
)
complete_method = complete_funnel.get("methodPlan") or {}
check(
    "complete-funnel-produces-ready-immutable-method-plan",
    complete_funnel.get("status") == "ready"
    and complete_method.get("status") == "ready"
    and complete_method.get("skillId") == "funnel-analysis"
    and complete_method.get("resolvedSlots", {}).keys() >= {"funnel-stages", "stage-order", "entity-key", "population", "time-scope", "time-field", "grain"}
    and len(str(complete_method.get("fingerprint") or "")) == 64,
    complete_funnel,
)

answer = {
    "intentFrame": complete_intent,
    "businessUnderstanding": complete_funnel,
    "analyticalSkillMatch": complete_funnel.get("skillMatch"),
    "semanticContext": {"schema": "aibi-semantic-context-bundle/v1", "stale": False, "fingerprint": "c" * 64},
    "semanticPlan": complete_semantic,
    "answerCard": {"kind": "clarification", "metrics": [], "rows": [], "evidenceRefs": []},
}
evidence_plan = build_evidence_plan(workspace_id="default", turn_key="turn-method-plan", answer=answer)
method_step = next((step for step in evidence_plan.get("steps") or [] if step.get("kind") == "analysis-method"), {})
policy = evaluate_agent_policy_hooks(workspace_id="default", plan=evidence_plan, skill_match=complete_funnel.get("skillMatch"))
check(
    "method-plan-enters-evidence-plan-and-fixed-policy-hooks",
    method_step.get("outputSchema") == "aibi-analysis-method-plan/v1"
    and method_step.get("status") == "completed"
    and method_step.get("dependsOn") == ["step-002-context"]
    and policy.get("status") == "passed",
    {"step": method_step, "policy": policy},
)
restricted_match = json.loads(json.dumps(complete_funnel.get("skillMatch")))
restricted_match["selected"]["allowedCapabilities"] = [
    capability for capability in restricted_match["selected"]["allowedCapabilities"]
    if capability != "agent.answer.compose"
]
restricted_policy = evaluate_agent_policy_hooks(workspace_id="default", plan=evidence_plan, skill_match=restricted_match)
check(
    "method-skill-capability-intersection-cannot-be-bypassed",
    restricted_policy.get("status") == "blocked"
    and "skill-no-permission-escalation" in (restricted_policy.get("blockers") or [])
    and restricted_policy.get("details", {}).get("methodCapabilityIntersection") is False,
    restricted_policy,
)

failed = [item for item in checks if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-second-batch-analysis-skills-verify/v1",
    "checks": checks,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
