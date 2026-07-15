from __future__ import annotations

import hashlib
import json
from typing import Any

from query_plan_receipt_service import validate_relationship_path_proof


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

_BLOCKER_SUMMARY_KEYS = ("kind", "mention", "reason", "code", "message", "status")


def _hash(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _blocker_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        summary = []
        for key in _BLOCKER_SUMMARY_KEYS:
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                summary.append(item.strip())
            elif isinstance(item, (int, float, bool)):
                summary.append(str(item))
        if summary:
            return " · ".join(dict.fromkeys(summary))
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        return "unreadable-blocker"


def _normalize_blockers(values: Any) -> list[str]:
    items = values if isinstance(values, (list, tuple)) else ([] if values is None else [values])
    normalized = [_blocker_text(item) for item in items]
    return list(dict.fromkeys(item for item in normalized if item))


def _record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _execution_plan(answer: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    direct = answer.get("executionPlan")
    if isinstance(direct, dict):
        return direct
    selection = _record(receipt.get("selection"))
    stored = selection.get("executionPlan")
    return stored if isinstance(stored, dict) else {}


def _relationship_path_proofs(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    selection = _record(receipt.get("selection"))
    value = selection.get("relationshipPathProof")
    if isinstance(value, dict) and isinstance(value.get("hopProofs"), list):
        value = value["hopProofs"]
    elif isinstance(value, dict) and isinstance(value.get("hops"), list):
        value = value["hops"]
    elif isinstance(value, dict):
        value = [value]
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _is_cross_table_query(receipt: dict[str, Any], execution_plan: dict[str, Any]) -> bool:
    table_keys = _record(receipt.get("source")).get("tableKeys")
    if isinstance(table_keys, list) and len(table_keys) > 1:
        return True
    relationships = execution_plan.get("relationships")
    if isinstance(relationships, list) and relationships:
        return True
    if isinstance(execution_plan.get("relationship"), dict):
        return True
    joins = _record(receipt.get("selection")).get("joins")
    return isinstance(joins, list) and bool(joins)


def _expected_relationships(receipt: dict[str, Any], execution_plan: dict[str, Any]) -> list[dict[str, Any]]:
    relationships = execution_plan.get("relationships")
    if isinstance(relationships, list):
        result = [item for item in relationships if isinstance(item, dict)]
        if result:
            return result
    relationship = execution_plan.get("relationship")
    if isinstance(relationship, dict):
        return [relationship]
    joins = _record(receipt.get("selection")).get("joins")
    return [item for item in joins if isinstance(item, dict)] if isinstance(joins, list) else []


def _query_blockers(
    receipt: dict[str, Any],
    execution_plan: dict[str, Any],
    relationship_path_proofs: list[dict[str, Any]],
) -> list[str]:
    blockers: list[Any] = []
    if receipt:
        if str(receipt.get("status") or "blocked") != "executed":
            blockers.extend(_normalize_blockers(receipt.get("unresolved")) or ["query-not-executed"])
    elif execution_plan:
        blockers.append("missing-query-plan-receipt")
    if execution_plan and str(execution_plan.get("status") or "blocked") != "ready":
        blockers.extend(_normalize_blockers(execution_plan.get("blockers")) or ["execution-plan-blocked"])
    relationship_validation = validate_relationship_path_proof(
        relationship_path_proofs,
        cross_table=_is_cross_table_query(receipt, execution_plan),
        expected_relationships=_expected_relationships(receipt, execution_plan),
    )
    blockers.extend(relationship_validation["blockers"])
    return _normalize_blockers(blockers)


def _relationship_proof_evidence(proofs: list[dict[str, Any]]) -> tuple[list[str], list[dict[str, Any]]]:
    required: list[str] = []
    refs: list[dict[str, Any]] = []
    for index, proof in enumerate(proofs):
        fingerprint = str(proof.get("proofFingerprint") or _hash(proof))
        hop_index = int(proof.get("hopIndex") if isinstance(proof.get("hopIndex"), int) else index)
        required.append(f"relationship-path-proof:{hop_index}:{fingerprint[:20]}")
        refs.append({
            "type": "relationshipPathProof",
            "hopIndex": hop_index,
            "relationKey": proof.get("relationKey"),
            "fromTable": proof.get("fromTable") or proof.get("leftTable") or proof.get("leftTableKey") or proof.get("relationshipLeftTable"),
            "toTable": proof.get("toTable") or proof.get("rightTable") or proof.get("rightTableKey") or proof.get("relationshipRightTable"),
            "proofFingerprint": fingerprint,
        })
    return required, refs


def _step(*, key: str, kind: str, capability_id: str, depends_on: list[str], input_refs: list[str], required_evidence: list[str], output_schema: str, status: str = "completed", blockers: list[Any] | None = None, artifact_refs: list[Any] | None = None, evidence_refs: list[Any] | None = None) -> dict[str, Any]:
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
        "blockers": _normalize_blockers(blockers),
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
    receipt_record = receipt or {}
    execution_plan = _execution_plan(answer, receipt_record)
    relationship_path_proofs = _relationship_path_proofs(receipt_record)
    query_blockers = _query_blockers(receipt_record, execution_plan, relationship_path_proofs)
    relationship_required, relationship_evidence_refs = _relationship_proof_evidence(relationship_path_proofs)
    plan_blockers = [*semantic_blockers, *query_blockers]
    steps = [
        _step(key="step-001-intent", kind="intent", capability_id="agent.intent.resolve", depends_on=[], input_refs=["turn.prompt"], required_evidence=[], output_schema="aibi-agent-intent-frame/v1"),
        _step(key="step-002-context", kind="context", capability_id="agent.context.route", depends_on=["step-001-intent"], input_refs=["turn.intentFrame"], required_evidence=[], output_schema="aibi-semantic-context-bundle/v1"),
        _step(key="step-003-semantic", kind="semantic", capability_id="agent.semantic.plan", depends_on=["step-002-context"], input_refs=["turn.semanticContext"], required_evidence=["field-provenance"], output_schema="aibi-semantic-query-plan/v1", status="blocked" if semantic_blockers else "completed", blockers=semantic_blockers),
    ]
    execution_dep = "step-003-semantic"
    if receipt or execution_plan:
        receipt_status = str(receipt_record.get("status") or "missing")
        query_completed = receipt_status == "executed" and not query_blockers
        required_evidence = ["query-plan-receipt"] if receipt else []
        required_evidence.extend(relationship_required)
        if _is_cross_table_query(receipt_record, execution_plan) and not relationship_path_proofs:
            required_evidence.append("relationship-path-proof")
        query_evidence_refs = ([{"receiptKey": receipt_record.get("receiptKey")}] if receipt else []) + relationship_evidence_refs
        steps.append(_step(
            key="step-004-query",
            kind="query",
            capability_id="agent.query.execute",
            depends_on=[execution_dep],
            input_refs=["answer.semanticPlan", "answer.executionPlan", "answer.queryPlanReceipt.selection.relationshipPathProof"],
            required_evidence=required_evidence,
            output_schema="aibi-query-plan-receipt/v1",
            status="completed" if query_completed else "blocked",
            blockers=[] if query_completed else query_blockers,
            evidence_refs=query_evidence_refs,
        ))
        execution_dep = "step-004-query"
    if action.get("status") == "draft":
        steps.append(_step(key="step-005-draft", kind="draft", capability_id="agent.action.draft", depends_on=[execution_dep], input_refs=["answer.actionDraft"], required_evidence=[], output_schema="aibi-action-draft/v1", status="waiting-confirmation", artifact_refs=[{"actionKey": action.get("actionKey")}]))
        execution_dep = "step-005-draft"
    steps.extend([
        _step(key="step-090-verify", kind="validation", capability_id="agent.completion.verify", depends_on=[execution_dep], input_refs=["turn.plan", "answer"], required_evidence=[], output_schema="aibi-agent-completion-validation/v1", status="planned"),
        _step(key="step-100-answer", kind="answer", capability_id="agent.answer.compose", depends_on=["step-090-verify"], input_refs=["answer.answerCard"], required_evidence=[], output_schema="aibi-agent-answer/v1", status="planned"),
    ])
    skill_match = answer.get("analyticalSkillMatch") if isinstance(answer.get("analyticalSkillMatch"), dict) else {}
    selected_skill = skill_match.get("selected") if isinstance(skill_match.get("selected"), dict) else None
    skill_refs = [{"skillId": selected_skill.get("skillId"), "version": selected_skill.get("version"), "fingerprint": selected_skill.get("fingerprint"), "status": selected_skill.get("status")}] if selected_skill else []
    plan_material = {"workspaceId": workspace_id, "turnKey": turn_key, "planVersion": 1, "steps": steps, "skillRefs": skill_refs}
    base_plan = {
        "schema": PLAN_SCHEMA,
        "workspaceId": workspace_id,
        "turnKey": turn_key,
        "planVersion": 1,
        "status": "blocked" if plan_blockers else "ready",
        "steps": steps,
        "skillRefs": skill_refs,
        "registeredCapabilities": sorted(AGENT_CAPABILITIES),
        "fingerprint": _hash(plan_material),
    }
    from restricted_workflow_graph_service import bind_restricted_workflow
    return bind_restricted_workflow(plan=base_plan, answer=answer)


def verify_evidence_plan(plan: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any]:
    from agent_policy_hook_service import evaluate_agent_policy_hooks
    from restricted_workflow_graph_service import GRAPH_SCHEMA, EXECUTION_SCHEMA, validate_restricted_workflow_graph

    blockers: list[str] = []
    workflow_graph = plan.get("workflowGraph") if isinstance(plan.get("workflowGraph"), dict) else {}
    workflow_execution = plan.get("workflowExecution") if isinstance(plan.get("workflowExecution"), dict) else {}
    workflow_validation = validate_restricted_workflow_graph(workflow_graph) if workflow_graph else {"status": "blocked", "blockers": ["missing-workflow-graph"]}
    checks = {
        "planSchema": plan.get("schema") == PLAN_SCHEMA,
        "workspaceBound": bool(plan.get("workspaceId")),
        "registeredCapabilities": all(step.get("capabilityId") in AGENT_CAPABILITIES for step in plan.get("steps") or []),
        "intentSchema": answer.get("intentFrame", {}).get("schema") == "aibi-agent-intent-frame/v1",
        "contextSchema": answer.get("semanticContext", {}).get("schema") == "aibi-semantic-context-bundle/v1",
        "contextCurrent": answer.get("semanticContext", {}).get("stale") is False,
        "contextFingerprint": len(str(answer.get("semanticContext", {}).get("fingerprint") or "")) == 64,
        "answerPresent": isinstance(answer.get("answerCard"), dict),
        "workflowGraphSchema": workflow_graph.get("schema") == GRAPH_SCHEMA,
        "workflowGraphValid": workflow_validation.get("status") == "passed",
        "workflowExecutionSchema": workflow_execution.get("schema") == EXECUTION_SCHEMA,
        "workflowJoinValid": workflow_execution.get("join", {}).get("status") == "passed",
        "reviewerAuthorityContained": workflow_execution.get("reviewerCapabilitySubmissionCount") == 0 and workflow_execution.get("reviewerToolCallCount") == 0,
        "parallelReadOnlyReview": bool(workflow_execution.get("parallelReadOnlyGroups")),
    }
    blockers.extend(key for key, valid in checks.items() if not valid)
    policy_hooks = evaluate_agent_policy_hooks(
        workspace_id=str(plan.get("workspaceId") or ""),
        plan=plan,
        skill_match=answer.get("analyticalSkillMatch") if isinstance(answer.get("analyticalSkillMatch"), dict) else None,
    )
    if policy_hooks["status"] != "passed":
        blockers.extend(f"policy:{item}" for item in policy_hooks["blockers"])
    semantic_status = str(answer.get("semanticPlan", {}).get("status") or "not-applicable")
    unresolved = list(answer.get("intentFrame", {}).get("unresolved") or [])
    receipt = _record(answer.get("queryPlanReceipt"))
    execution_plan = _execution_plan(answer, receipt)
    query_blockers = _query_blockers(receipt, execution_plan, _relationship_path_proofs(receipt))
    outcome = "blocked" if semantic_status not in {"ready", "not-applicable"} or unresolved or query_blockers else "completed"
    if outcome == "blocked":
        blockers.extend([f"semantic:{semantic_status}"] if semantic_status not in {"ready", "not-applicable"} else [])
        blockers.extend(f"unresolved:{item.get('mention') or item.get('kind')}" for item in unresolved)
        blockers.extend(f"query:{item}" for item in query_blockers)
    status = "failed" if any(not valid for valid in checks.values()) else "blocked" if policy_hooks["status"] != "passed" else outcome
    return {
        "schema": "aibi-agent-completion-validation/v1",
        "status": status,
        "checks": checks,
        "blockers": list(dict.fromkeys(blockers)),
        "evidenceComplete": all(checks.values()),
        "safeToPresent": status in {"completed", "blocked"},
        "policyHooks": policy_hooks,
        "workflowValidation": workflow_validation,
        "workflowExecution": workflow_execution,
        "fingerprint": _hash({"plan": plan.get("fingerprint"), "checks": checks, "blockers": blockers}),
    }


def finalize_evidence_plan(plan: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    finalized = json.loads(json.dumps(plan))
    validation_status = str(validation.get("status") or "failed")
    for step in finalized.get("steps") or []:
        if step.get("capabilityId") == "agent.completion.verify":
            step["status"] = "completed" if validation_status == "completed" else "blocked" if validation_status == "blocked" and validation.get("safeToPresent") else "failed"
            step["blockers"] = _normalize_blockers(validation.get("blockers"))
            step["outputFingerprint"] = validation.get("fingerprint")
        if step.get("capabilityId") == "agent.answer.compose":
            step["status"] = "completed" if validation.get("safeToPresent") else "blocked"
            step["blockers"] = [] if validation.get("safeToPresent") else ["completion-validation-failed"]
    finalized["status"] = validation_status
    finalized["fingerprint"] = _hash({"workspaceId": finalized.get("workspaceId"), "turnKey": finalized.get("turnKey"), "planVersion": finalized.get("planVersion"), "steps": finalized.get("steps"), "workflowGraph": finalized.get("workflowGraph"), "workflowExecution": finalized.get("workflowExecution")})
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
    for event in plan.get("workflowExecution", {}).get("events") or []:
        events.append({"eventType": event.get("eventType"), "stepKey": event.get("nodeKey"), "status": event.get("status"), "summary": f"{event.get('role')} · {event.get('status')}"})
    events.extend([
        {"eventType": "validation-completed", "stepKey": "step-090-verify", "status": validation.get("status"), "summary": "完成条件已复核"},
        {"eventType": "answer-ready", "stepKey": "step-100-answer", "status": "completed" if validation.get("safeToPresent") else "blocked", "summary": "业务答案已准备"},
        {"eventType": "turn-completed" if validation.get("status") == "completed" else "turn-blocked" if validation.get("safeToPresent") else "turn-failed", "stepKey": None, "status": validation.get("status"), "summary": "Agent 回合已完成" if validation.get("status") == "completed" else "Agent 回合已阻断" if validation.get("safeToPresent") else "Agent 回合失败"},
    ])
    return events
