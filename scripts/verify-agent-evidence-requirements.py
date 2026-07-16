from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from agent_evidence_plan_service import build_evidence_plan, verify_evidence_plan  # noqa: E402


checks: list[dict[str, Any]] = []


def check(label: str, ok: bool, detail: Any = None) -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": None if ok else detail})


def resolved(value: Any, source: str = "explicit-business-definition") -> dict[str, Any]:
    return {"status": "resolved", "value": value, "source": source, "evidenceRefs": []}


def base_answer(business: dict[str, Any]) -> dict[str, Any]:
    return {
        "workspaceId": "default",
        "intentFrame": {
            "schema": "aibi-agent-intent-frame/v1",
            "decisionGoal": "计算退款率",
            "unresolved": [],
            "resolution": {"silentDisambiguation": False},
        },
        "businessUnderstanding": {
            "schema": "aibi-business-understanding-frame/v1",
            "status": "ready",
            "signals": [],
            "slots": {"decision-goal": resolved("计算退款率", "explicit-question")},
            "missingSlots": [],
            "blockers": [],
            "requiredEvidence": [],
            "guards": [],
            "evidenceRefs": [],
            "fingerprint": "b" * 64,
            **business,
        },
        "semanticPlan": {"status": "not-applicable"},
        "semanticContext": {
            "schema": "aibi-semantic-context-bundle/v1",
            "stale": False,
            "fingerprint": "c" * 64,
        },
        "actionDraft": {"status": "read-only"},
        "answerCard": {"metrics": [], "rows": [], "evidenceRefs": []},
    }


fake_reference_answer = base_answer({
    "requiredEvidence": ["metric-definition"],
    "evidenceRefs": [{"type": "metricDefinition", "value": "unverified declaration"}],
})
fake_reference_plan = build_evidence_plan(
    workspace_id="default",
    turn_key="turn-fake-evidence-reference",
    answer=fake_reference_answer,
)
fake_reference_validation = verify_evidence_plan(fake_reference_plan, fake_reference_answer)
check(
    "plan-reference-alone-does-not-satisfy-required-evidence",
    fake_reference_validation["status"] == "failed"
    and fake_reference_validation["checks"]["requiredEvidenceSatisfied"] is False
    and "evidence:step-002-business-understanding:missing:metric-definition" in fake_reference_validation["blockers"],
    fake_reference_validation,
)


ratio_slots = {
    "decision-goal": resolved("计算退款率", "explicit-question"),
    "metric-concept": resolved("退款率"),
    "numerator": resolved("退款订单数"),
    "denominator": resolved("支付订单数"),
    "grain": resolved("订单"),
}
verified_answer = base_answer({
    "signals": ["ratio-request"],
    "slots": ratio_slots,
    "requiredEvidence": [
        "prompt-intent",
        "resolved-business-slots",
        "metric-definition",
        "grain-definition",
    ],
    "guards": [
        "current-context",
        "no-silent-proxy",
        "no-implicit-denominator",
        "grain-explicit",
        "no-permission-escalation",
    ],
})
verified_plan = build_evidence_plan(
    workspace_id="default",
    turn_key="turn-verified-business-definition",
    answer=verified_answer,
)
verified_validation = verify_evidence_plan(verified_plan, verified_answer)
business_step = next(step for step in verified_plan["steps"] if step["stepKey"] == "step-002-business-understanding")
evidence_types = {str(item.get("type")) for item in business_step["evidenceRefs"] if isinstance(item, dict)}
check(
    "structured-business-definition-satisfies-declared-evidence",
    verified_validation["status"] == "completed"
    and verified_validation["checks"]["requiredEvidenceSatisfied"] is True,
    verified_validation,
)
check(
    "business-step-exposes-derived-evidence-references",
    {"prompt-intent", "resolved-business-slots", "metric-definition", "grain-definition"}.issubset(evidence_types),
    sorted(evidence_types),
)
check(
    "known-semantic-guards-are-evaluated-not-merely-listed",
    verified_validation["checks"]["semanticGuardsSatisfied"] is True
    and all(item["status"] == "passed" for item in verified_validation["semanticGuardValidation"]["results"]),
    verified_validation["semanticGuardValidation"],
)


implicit_denominator_answer = base_answer({
    "signals": ["ratio-request"],
    "slots": {name: copy.deepcopy(value) for name, value in ratio_slots.items() if name != "denominator"},
    "guards": ["no-implicit-denominator"],
})
implicit_denominator_plan = build_evidence_plan(
    workspace_id="default",
    turn_key="turn-implicit-denominator",
    answer=implicit_denominator_answer,
)
implicit_denominator_validation = verify_evidence_plan(implicit_denominator_plan, implicit_denominator_answer)
check(
    "implicit-denominator-guard-fails-a-falsely-ready-answer",
    implicit_denominator_validation["status"] == "failed"
    and "guard:step-002-business-understanding:failed:no-implicit-denominator" in implicit_denominator_validation["blockers"],
    implicit_denominator_validation,
)


unsupported_guard_answer = base_answer({"guards": ["future-unimplemented-guard"]})
unsupported_guard_plan = build_evidence_plan(
    workspace_id="default",
    turn_key="turn-unsupported-guard",
    answer=unsupported_guard_answer,
)
unsupported_guard_validation = verify_evidence_plan(unsupported_guard_plan, unsupported_guard_answer)
check(
    "unknown-guard-fails-closed",
    unsupported_guard_validation["status"] == "failed"
    and "guard:step-002-business-understanding:unsupported:future-unimplemented-guard" in unsupported_guard_validation["blockers"],
    unsupported_guard_validation,
)


blocked_answer = base_answer({
    "status": "needs-clarification",
    "signals": ["ratio-request"],
    "slots": {name: copy.deepcopy(value) for name, value in ratio_slots.items() if name != "denominator"},
    "missingSlots": ["denominator"],
    "blockers": [{
        "kind": "business-slot",
        "slot": "denominator",
        "mention": "denominator",
        "reason": "required-by-understanding-skill",
    }],
    "requiredEvidence": ["metric-definition"],
    "guards": ["no-implicit-denominator"],
})
blocked_plan = build_evidence_plan(
    workspace_id="default",
    turn_key="turn-safe-clarification",
    answer=blocked_answer,
)
blocked_validation = verify_evidence_plan(blocked_plan, blocked_answer)
check(
    "blocked-clarification-may-omit-the-evidence-it-requests",
    blocked_validation["status"] == "blocked"
    and blocked_validation["safeToPresent"] is True
    and blocked_validation["checks"]["requiredEvidenceSatisfied"] is True
    and blocked_validation["checks"]["semanticGuardsSatisfied"] is True
    and all(item["status"] == "skipped-blocked-step" for item in blocked_validation["evidenceValidation"]["results"]),
    blocked_validation,
)


failed = [item for item in checks if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-agent-evidence-requirements-verify/v1",
    "checks": checks,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
