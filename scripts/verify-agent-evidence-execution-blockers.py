from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from agent_evidence_plan_service import (  # noqa: E402
    build_evidence_plan,
    finalize_evidence_plan,
    public_turn_events,
    verify_evidence_plan,
)
from aibi_runtime.use_cases.agent_interaction import merge_receipt_unresolved_with_execution_blockers  # noqa: E402


checks: list[dict[str, object]] = []


def check(label: str, ok: bool, detail: object = None) -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": None if ok else detail})


def base_answer() -> dict[str, object]:
    field_provenance = {
        "type": "fieldProvenance",
        "tableKey": "orders",
        "field": "amount",
        "role": "measure",
        "source": "fixture-semantic",
    }
    return {
        "workspaceId": "default",
        "intentFrame": {
            "schema": "aibi-agent-intent-frame/v1",
            "decisionGoal": "按关系路径汇总 amount",
            "unresolved": [],
            "evidenceRefs": [field_provenance],
        },
        "semanticPlan": {
            "status": "ready",
            "fieldResolution": {
                "selected": [{
                    "tableKey": "orders",
                    "field": "amount",
                    "role": "measure",
                    "source": "fixture-semantic",
                }],
            },
        },
        "semanticContext": {
            "schema": "aibi-semantic-context-bundle/v1",
            "stale": False,
            "fingerprint": "c" * 64,
        },
        "actionDraft": {"status": "read-only"},
        "answerCard": {"evidenceRefs": []},
    }


proofs = [
    {
        "hopIndex": 0,
        "relationKey": "orders-items",
        "fromTable": "orders",
        "toTable": "items",
        "proofStatus": "verified",
        "blockers": [],
        "dataVersions": {
            "expected": {"orders": 1, "items": 1},
            "current": {"orders": 1, "items": 1},
            "matches": True,
        },
        "proofFingerprint": "a" * 64,
    },
    {
        "hopIndex": 1,
        "relationKey": "items-products",
        "fromTable": "items",
        "toTable": "products",
        "proofStatus": "verified",
        "blockers": [],
        "dataVersions": {
            "expected": {"items": 1, "products": 1},
            "current": {"items": 1, "products": 1},
            "matches": True,
        },
        "proofFingerprint": "b" * 64,
    },
]
relationships = [
    {"relationKey": item["relationKey"], "fromTable": item["fromTable"], "toTable": item["toTable"]}
    for item in proofs
]

blocked_answer = base_answer()
blocked_execution = {
    "status": "blocked",
    "rootTable": "orders",
    "relationships": relationships,
    "blockers": ["two-hop-preaggregation-not-yet-supported"],
}
blocked_answer["executionPlan"] = blocked_execution
blocked_answer["queryPlanReceipt"] = {
    "schema": "aibi-query-plan-receipt/v1",
    "receiptKey": "receipt-blocked",
    "status": "blocked",
    "source": {"dataFingerprint": "d" * 64},
    "domainPackFingerprint": "k" * 64,
    "selection": {
        "executionPlan": blocked_execution,
        "relationshipPathProof": proofs,
        "joins": relationships,
    },
    "unresolved": [],
}

blocked_plan = build_evidence_plan(workspace_id="default", turn_key="turn-blocked-execution", answer=blocked_answer)
blocked_query_step = next(step for step in blocked_plan["steps"] if step["capabilityId"] == "agent.query.execute")
check("blocked-execution-blocks-plan", blocked_plan["status"] == "blocked", blocked_plan["status"])
check("blocked-execution-blocks-query-step", blocked_query_step["status"] == "blocked", blocked_query_step)
check(
    "blocked-execution-reasons-are-preserved",
    blocked_query_step["blockers"] == ["query-not-executed", "two-hop-preaggregation-not-yet-supported"],
    blocked_query_step["blockers"],
)
proof_requirements = [item for item in blocked_query_step["requiredEvidence"] if item.startswith("relationship-path-proof:")]
check("every-hop-is-required-evidence", len(proof_requirements) == 2, blocked_query_step["requiredEvidence"])
proof_refs = [item for item in blocked_query_step["evidenceRefs"] if item.get("type") == "relationshipPathProof"]
check("every-hop-is-an-evidence-reference", len(proof_refs) == 2, blocked_query_step["evidenceRefs"])

blocked_validation = verify_evidence_plan(blocked_plan, blocked_answer)
check("blocked-execution-blocks-completion-validation", blocked_validation["status"] == "blocked", blocked_validation)
check(
    "blocked-completion-remains-safe-to-present",
    blocked_validation["safeToPresent"] is True,
    blocked_validation,
)
check(
    "completion-validation-cites-execution-blocker",
    "query:two-hop-preaggregation-not-yet-supported" in blocked_validation["blockers"],
    blocked_validation["blockers"],
)
blocked_final = finalize_evidence_plan(blocked_plan, blocked_validation)
blocked_validation_step = next(step for step in blocked_final["steps"] if step["capabilityId"] == "agent.completion.verify")
check("final-plan-remains-blocked", blocked_final["status"] == "blocked", blocked_final["status"])
check("completion-step-remains-blocked", blocked_validation_step["status"] == "blocked", blocked_validation_step)
blocked_events = public_turn_events(blocked_final, blocked_validation)
check(
    "public-turn-ends-as-blocked",
    blocked_events[-1]["eventType"] == "turn-blocked" and blocked_events[-1]["summary"] == "Agent 回合已阻断",
    blocked_events[-1],
)

ready_answer = base_answer()
ready_execution = {"status": "ready", "rootTable": "orders", "relationships": relationships, "blockers": []}
ready_answer["executionPlan"] = ready_execution
ready_answer["queryPlanReceipt"] = {
    "schema": "aibi-query-plan-receipt/v1",
    "receiptKey": "receipt-ready",
    "status": "executed",
    "source": {"dataFingerprint": "e" * 64},
    "domainPackFingerprint": "k" * 64,
    "selection": {
        "executionPlan": ready_execution,
        "relationshipPathProof": proofs,
        "joins": relationships,
    },
    "unresolved": [],
}
ready_plan = build_evidence_plan(workspace_id="default", turn_key="turn-ready-execution", answer=ready_answer)
ready_query_step = next(step for step in ready_plan["steps"] if step["capabilityId"] == "agent.query.execute")
ready_validation = verify_evidence_plan(ready_plan, ready_answer)
ready_final = finalize_evidence_plan(ready_plan, ready_validation)
ready_validation_step = next(step for step in ready_final["steps"] if step["capabilityId"] == "agent.completion.verify")
check("ready-execution-completes-plan", ready_plan["status"] == "ready", ready_plan["status"])
check("ready-execution-completes-query-step", ready_query_step["status"] == "completed", ready_query_step)
check("ready-execution-completes-validation", ready_validation["status"] == "completed", ready_validation)
check("ready-execution-completes-final-plan", ready_final["status"] == "completed", ready_final["status"])
check("ready-execution-completes-validation-step", ready_validation_step["status"] == "completed", ready_validation_step)

strict_proof_variants = [
    (
        "planned",
        [{**proofs[0], "proofStatus": "planned", "proofFingerprint": "1" * 64}, proofs[1]],
        "hop-1:relationship-proof-not-verified:planned",
    ),
    (
        "blocked",
        [{
            **proofs[0],
            "proofStatus": "blocked",
            "blockers": ["fan-out-after-measure-grain"],
            "proofFingerprint": "2" * 64,
        }, proofs[1]],
        "hop-1:relationship-proof-blocked:fan-out-after-measure-grain",
    ),
    (
        "version-mismatch",
        [{
            **proofs[0],
            "dataVersions": {
                "expected": {"orders": 1, "items": 1},
                "current": {"orders": 1, "items": 2},
                "matches": False,
            },
            "proofFingerprint": "3" * 64,
        }, proofs[1]],
        "hop-1:relationship-data-version-not-current",
    ),
]
for variant_name, variant_proofs, expected_blocker in strict_proof_variants:
    variant_answer = base_answer()
    variant_answer["executionPlan"] = ready_execution
    variant_answer["queryPlanReceipt"] = {
        "schema": "aibi-query-plan-receipt/v1",
        "receiptKey": f"receipt-{variant_name}",
        "status": "executed",
        "source": {"dataFingerprint": "9" * 64, "tableKeys": ["orders", "items", "products"]},
        "domainPackFingerprint": "k" * 64,
        "selection": {
            "executionPlan": ready_execution,
            "relationshipPathProof": variant_proofs,
            "joins": relationships,
        },
        "unresolved": [],
    }
    variant_plan = build_evidence_plan(
        workspace_id="default",
        turn_key=f"turn-{variant_name}-proof",
        answer=variant_answer,
    )
    variant_query_step = next(
        step for step in variant_plan["steps"] if step["capabilityId"] == "agent.query.execute"
    )
    variant_validation = verify_evidence_plan(variant_plan, variant_answer)
    check(f"{variant_name}-proof-blocks-plan", variant_plan["status"] == "blocked", variant_plan)
    check(
        f"{variant_name}-proof-blocker-is-preserved",
        expected_blocker in variant_query_step["blockers"],
        variant_query_step,
    )
    check(
        f"{variant_name}-proof-blocks-completion",
        variant_validation["status"] == "blocked"
        and f"query:{expected_blocker}" in variant_validation["blockers"],
        variant_validation,
    )

missing_proof_answer = base_answer()
missing_proof_answer["executionPlan"] = ready_execution
missing_proof_answer["queryPlanReceipt"] = {
    "schema": "aibi-query-plan-receipt/v1",
    "receiptKey": "receipt-missing-proof",
    "status": "executed",
    "source": {"dataFingerprint": "f" * 64, "tableKeys": ["orders", "items", "products"]},
    "domainPackFingerprint": "k" * 64,
    "selection": {"executionPlan": ready_execution, "joins": relationships},
    "unresolved": [],
}
missing_proof_plan = build_evidence_plan(
    workspace_id="default",
    turn_key="turn-missing-proof",
    answer=missing_proof_answer,
)
missing_proof_query_step = next(
    step for step in missing_proof_plan["steps"] if step["capabilityId"] == "agent.query.execute"
)
missing_proof_validation = verify_evidence_plan(missing_proof_plan, missing_proof_answer)
check("missing-proof-blocks-plan", missing_proof_plan["status"] == "blocked", missing_proof_plan["status"])
check("missing-proof-blocks-query-step", missing_proof_query_step["status"] == "blocked", missing_proof_query_step)
check(
    "missing-proof-has-generic-required-evidence",
    "relationship-path-proof" in missing_proof_query_step["requiredEvidence"],
    missing_proof_query_step["requiredEvidence"],
)
check(
    "missing-proof-blocks-validation",
    missing_proof_validation["status"] == "blocked"
    and "query:missing-relationship-path-proof" in missing_proof_validation["blockers"],
    missing_proof_validation,
)

ask_receipt_unresolved = merge_receipt_unresolved_with_execution_blockers(
    [{"type": "semantic-plan", "status": "ready"}, "existing-runtime-blocker"],
    {
        "status": "blocked",
        "blockers": [
            "existing-runtime-blocker",
            "functional-dependency-not-proven:orders.order_id->orders.channel",
        ],
    },
)
check(
    "ask-blocked-receipt-preserves-execution-plan-blockers",
    "functional-dependency-not-proven:orders.order_id->orders.channel" in ask_receipt_unresolved,
    ask_receipt_unresolved,
)
check(
    "ask-blocked-receipt-deduplicates-existing-blockers",
    ask_receipt_unresolved.count("existing-runtime-blocker") == 1,
    ask_receipt_unresolved,
)

failed = [item for item in checks if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-agent-evidence-execution-blockers-verify/v1",
    "checks": checks,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
