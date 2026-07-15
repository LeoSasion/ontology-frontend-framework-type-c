from __future__ import annotations

import hashlib
import json
from typing import Any


PLAN_SCHEMA = "aibi-agent-evidence-plan/v1"
EVENT_SCHEMA = "aibi-agent-turn-event/v1"

AGENT_CAPABILITIES = {
    "agent.intent.resolve": "read-only",
    "agent.context.route": "read-only",
    "agent.semantic.plan": "read-only",
    "agent.query.execute": "runtime-receipt",
    "agent.action.draft": "action-draft",
    "agent.completion.verify": "read-only",
    "agent.answer.compose": "read-only",
}


def _hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _step(*, key: str, kind: str, capability_id: str, depends_on: list[str], input_refs: list[str], required_evidence: list[str], output_schema: str, status: str = "completed", blockers: list[str] | None = None, artifact_refs: list[Any] | None = None, evidence_refs: list[Any] | None = None) -> dict[str, Any]:
    mutation_mode = AGENT_CAPABILITIES[capability_id]
    input_payload = {"inputRefs": input_refs, "dependsOn": depends_on}
    output_payload = {"artifacts": artifact_refs or [], "evidence": evidence_refs or [], "status": status}
    return {
        "stepKey": key,
        "kind": kind,
        "capabilityId": capability_id,
        "dependsOn": depends_on,
        "inputRefs": input_refs,
        "inputFingerprint": _hash(input_payload),
        "requiredEvidence": required_evidence,
        "outputSchema": output_schema,
        "mutationMode": mutation_mode,
        "status": status,
        "blockers": list(blockers or []),
        "retryPolicy": {"mode": "none", "maxAttempts": 1},
        "completionChecks": ["workspace-bound", "schema-valid", "evidence-complete"],
        "artifactRefs": list(artifact_refs or []),
        "evidenceRefs": list(evidence_refs or []),
        "outputFingerprint": _hash(output_payload),
    }


def build_evidence_plan(*, workspace_id: str, turn_key: str, answer: dict[str, Any]) -> dict[str, Any]:
    semantic_plan = answer.get("semanticPlan") if isinstance(answer.get("semanticPlan"), dict) else {}
    receipt = answer.get("queryPlanReceipt") if isinstance(answer.get("queryPlanReceipt"), dict) else None
    action = answer.get("actionDraft") if isinstance(answer.get("actionDraft"), dict) else {}
    semantic_status = str(semantic_plan.get("status") or "not-applicable")
    semantic_blockers = [] if semantic_status in {"ready", "not-applicable"} else [semantic_status]
    steps = [
        _step(key="step-001-intent", kind="intent", capability_id="agent.intent.resolve", depends_on=[], input_refs=["turn.prompt"], required_evidence=[], output_schema="aibi-agent-intent-frame/v1"),
        _step(key="step-002-context", kind="context", capability_id="agent.context.route", depends_on=["step-001-intent"], input_refs=["turn.intentFrame"], required_evidence=[], output_schema="aibi-semantic-context-bundle/v1"),
        _step(key="step-003-semantic", kind="semantic", capability_id="agent.semantic.plan", depends_on=["step-002-context"], input_refs=["turn.semanticContext"], required_evidence=["field-provenance"], output_schema="aibi-semantic-query-plan/v1", status="blocked" if semantic_blockers else "completed", blockers=semantic_blockers),
    ]
    execution_dep = "step-003-semantic"
    if receipt:
        receipt_status = str(receipt.get("status") or "blocked")
        steps.append(_step(key="step-004-query", kind="query", capability_id="agent.query.execute", depends_on=[execution_dep], input_refs=["answer.semanticPlan"], required_evidence=["query-plan-receipt"], output_schema="aibi-query-plan-receipt/v1", status="completed" if receipt_status == "executed" else "blocked", blockers=[] if receipt_status == "executed" else list(receipt.get("unresolved") or ["query-not-executed"]), evidence_refs=[{"receiptKey": receipt.get("receiptKey")}]))
        execution_dep = "step-004-query"
    if action.get("status") == "draft":
        steps.append(_step(key="step-005-draft", kind="draft", capability_id="agent.action.draft", depends_on=[execution_dep], input_refs=["answer.actionDraft"], required_evidence=[], output_schema="aibi-action-draft/v1", status="waiting-confirmation", artifact_refs=[{"actionKey": action.get("actionKey")}]))
        execution_dep = "step-005-draft"
    steps.extend([
        _step(key="step-090-verify", kind="validation", capability_id="agent.completion.verify", depends_on=[execution_dep], input_refs=["turn.plan", "answer"], required_evidence=[], output_schema="aibi-agent-completion-validation/v1", status="planned"),
        _step(key="step-100-answer", kind="answer", capability_id="agent.answer.compose", depends_on=["step-090-verify"], input_refs=["answer.answerCard"], required_evidence=[], output_schema="aibi-agent-answer/v1", status="planned"),
    ])
    plan_material = {"workspaceId": workspace_id, "turnKey": turn_key, "planVersion": 1, "steps": steps}
    return {
        "schema": PLAN_SCHEMA,
        "workspaceId": workspace_id,
        "turnKey": turn_key,
        "planVersion": 1,
        "status": "blocked" if semantic_blockers else "ready",
        "steps": steps,
        "registeredCapabilities": sorted(AGENT_CAPABILITIES),
        "fingerprint": _hash(plan_material),
    }


def verify_evidence_plan(plan: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any]:
    blockers: list[str] = []
    checks = {
        "planSchema": plan.get("schema") == PLAN_SCHEMA,
        "workspaceBound": bool(plan.get("workspaceId")),
        "registeredCapabilities": all(step.get("capabilityId") in AGENT_CAPABILITIES for step in plan.get("steps") or []),
        "intentSchema": answer.get("intentFrame", {}).get("schema") == "aibi-agent-intent-frame/v1",
        "contextSchema": answer.get("semanticContext", {}).get("schema") == "aibi-semantic-context-bundle/v1",
        "contextCurrent": answer.get("semanticContext", {}).get("stale") is False,
        "contextFingerprint": len(str(answer.get("semanticContext", {}).get("fingerprint") or "")) == 64,
        "answerPresent": isinstance(answer.get("answerCard"), dict),
    }
    blockers.extend(key for key, valid in checks.items() if not valid)
    semantic_status = str(answer.get("semanticPlan", {}).get("status") or "not-applicable")
    unresolved = list(answer.get("intentFrame", {}).get("unresolved") or [])
    outcome = "blocked" if semantic_status not in {"ready", "not-applicable"} or unresolved else "completed"
    if outcome == "blocked":
        blockers.extend([f"semantic:{semantic_status}"] if semantic_status not in {"ready", "not-applicable"} else [])
        blockers.extend(f"unresolved:{item.get('mention') or item.get('kind')}" for item in unresolved)
    status = "failed" if any(not valid for valid in checks.values()) else outcome
    return {
        "schema": "aibi-agent-completion-validation/v1",
        "status": status,
        "checks": checks,
        "blockers": list(dict.fromkeys(blockers)),
        "evidenceComplete": all(checks.values()),
        "safeToPresent": status in {"completed", "blocked"},
        "fingerprint": _hash({"plan": plan.get("fingerprint"), "checks": checks, "blockers": blockers}),
    }


def finalize_evidence_plan(plan: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    finalized = json.loads(json.dumps(plan))
    for step in finalized.get("steps") or []:
        if step.get("capabilityId") == "agent.completion.verify":
            step["status"] = "completed" if validation.get("safeToPresent") else "failed"
            step["blockers"] = list(validation.get("blockers") or [])
            step["outputFingerprint"] = validation.get("fingerprint")
        if step.get("capabilityId") == "agent.answer.compose":
            step["status"] = "completed" if validation.get("safeToPresent") else "blocked"
            step["blockers"] = [] if validation.get("safeToPresent") else ["completion-validation-failed"]
    finalized["status"] = validation.get("status")
    finalized["fingerprint"] = _hash({"workspaceId": finalized.get("workspaceId"), "turnKey": finalized.get("turnKey"), "planVersion": finalized.get("planVersion"), "steps": finalized.get("steps")})
    return finalized


def public_turn_events(plan: dict[str, Any], validation: dict[str, Any]) -> list[dict[str, Any]]:
    events = [
        {"eventType": "intent-resolved", "stepKey": "step-001-intent", "status": "completed", "summary": "业务意图已解析"},
        {"eventType": "context-ready", "stepKey": "step-002-context", "status": "completed", "summary": "语义上下文已绑定"},
        {"eventType": "plan-ready", "stepKey": None, "status": str(plan.get("status") or "ready"), "summary": "证据计划已生成"},
    ]
    for step in plan.get("steps") or []:
        if step.get("stepKey") in {"step-001-intent", "step-002-context", "step-090-verify", "step-100-answer"}:
            continue
        events.append({"eventType": "step-completed" if step.get("status") == "completed" else "step-blocked" if step.get("status") == "blocked" else "approval-required", "stepKey": step.get("stepKey"), "status": step.get("status"), "summary": f"{step.get('kind')} · {step.get('status')}"})
    events.extend([
        {"eventType": "validation-completed", "stepKey": "step-090-verify", "status": validation.get("status"), "summary": "完成条件已复核"},
        {"eventType": "answer-ready", "stepKey": "step-100-answer", "status": "completed" if validation.get("safeToPresent") else "blocked", "summary": "业务答案已准备"},
        {"eventType": "turn-completed" if validation.get("status") == "completed" else "turn-blocked" if validation.get("safeToPresent") else "turn-failed", "stepKey": None, "status": validation.get("status"), "summary": "Agent 回合已完成" if validation.get("safeToPresent") else "Agent 回合失败"},
    ])
    return events
