from __future__ import annotations

import hashlib
import json
import re
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


def _unique_strings(*values: Any) -> list[str]:
    result: list[str] = []
    for value in values:
        items = value if isinstance(value, (list, tuple)) else ([] if value is None else [value])
        for item in items:
            text = str(item or "").strip()
            if text and text not in result:
                result.append(text)
    return result


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set, dict)):
        return bool(value)
    return True


def _valid_fingerprint(value: Any) -> bool:
    return bool(re.fullmatch(r"[0-9a-f]{64}", str(value or "").strip().casefold()))


def _resolved_slot(slots: dict[str, Any], name: str) -> dict[str, Any]:
    slot = _record(slots.get(name))
    return slot if slot.get("status") == "resolved" and _nonempty(slot.get("value")) else {}


def _canonical_evidence_name(value: Any) -> str:
    text = re.sub(r"[^0-9a-z]+", "-", str(value or "").strip().casefold()).strip("-")
    aliases = {
        "businessunderstanding": "business-understanding",
        "cardinalityprofile": "cardinality-profile",
        "comparisonbaseline": "comparison-baseline",
        "driverbreakdown": "driver-breakdown",
        "fieldprofile": "field-profile",
        "fieldprovenance": "field-provenance",
        "graindefinition": "grain-definition",
        "metricdefinition": "metric-definition",
        "promptintent": "prompt-intent",
        "queryplanreceipt": "query-plan-receipt",
        "relationshippathproof": "relationship-path-proof",
        "resolvedbusinessslots": "resolved-business-slots",
        "sourcefingerprint": "source-fingerprint",
        "sourceintelligencerun": "source-intelligence-run",
    }
    return aliases.get(text.replace("-", ""), text)


def _field_provenance_refs(answer: dict[str, Any]) -> list[dict[str, Any]]:
    intent_frame = _record(answer.get("intentFrame"))
    business_understanding = _record(answer.get("businessUnderstanding"))
    candidates: list[Any] = [
        *list(intent_frame.get("evidenceRefs") or []),
        *list(business_understanding.get("evidenceRefs") or []),
    ]
    for slot in _record(business_understanding.get("slots")).values():
        if isinstance(slot, dict):
            candidates.extend(list(slot.get("evidenceRefs") or []))
    selected = _record(answer.get("semanticPlan")).get("fieldResolution")
    for field in list(_record(selected).get("selected") or []):
        if isinstance(field, dict):
            candidates.append({"type": "fieldProvenance", **field})
    refs: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in candidates:
        if not isinstance(item, dict) or _canonical_evidence_name(item.get("type")) != "field-provenance":
            continue
        table_key = str(item.get("tableKey") or "").strip()
        field = str(item.get("field") or "").strip()
        source = str(item.get("source") or "").strip()
        if not table_key or not field or not source:
            continue
        identity = (table_key, field, source)
        if identity not in seen:
            seen.add(identity)
            refs.append(item)
    return refs


def _answer_claims_results(answer: dict[str, Any]) -> bool:
    answer_card = _record(answer.get("answerCard"))
    analysis_unit = _record(answer.get("analysisUnit"))
    return bool(answer_card.get("metrics") or answer_card.get("rows") or analysis_unit.get("status") == "ready")


def _cross_table_context(answer: dict[str, Any], receipt: dict[str, Any], execution_plan: dict[str, Any]) -> bool:
    if _is_cross_table_query(receipt, execution_plan):
        return True
    required_tables = _record(_record(answer.get("semanticPlan")).get("joinPlan")).get("requiredTables")
    return isinstance(required_tables, list) and len(required_tables) > 1


def _collect_evidence(answer: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Build evidence only from validated answer structures, never plan declarations."""
    inventory: dict[str, list[dict[str, Any]]] = {}

    def add(name: str, ref: dict[str, Any]) -> None:
        canonical = _canonical_evidence_name(name)
        inventory.setdefault(canonical, []).append(ref)

    intent_frame = _record(answer.get("intentFrame"))
    business_understanding = _record(answer.get("businessUnderstanding"))
    semantic_context = _record(answer.get("semanticContext"))
    semantic_plan = _record(answer.get("semanticPlan"))
    slots = _record(business_understanding.get("slots"))
    receipt = _record(answer.get("queryPlanReceipt"))
    execution_plan = _execution_plan(answer, receipt)

    if intent_frame.get("schema") == "aibi-agent-intent-frame/v1" and _nonempty(intent_frame.get("decisionGoal")):
        add("prompt-intent", {"schema": intent_frame.get("schema"), "decisionGoal": intent_frame.get("decisionGoal")})
    resolved_slots = sorted(name for name, value in slots.items() if _resolved_slot(slots, name))
    if (
        business_understanding.get("schema") == "aibi-business-understanding-frame/v1"
        and business_understanding.get("status") == "ready"
        and not business_understanding.get("missingSlots")
        and resolved_slots
    ):
        add("resolved-business-slots", {"slots": resolved_slots, "fingerprint": business_understanding.get("fingerprint")})

    for ref in _field_provenance_refs(answer):
        add("field-provenance", ref)

    grain = _resolved_slot(slots, "grain")
    if grain:
        add("grain-definition", {"slot": "grain", "value": grain.get("value"), "source": grain.get("source")})

    signals = set(str(item) for item in business_understanding.get("signals") or [])
    metric_slots = ["metric-concept", "numerator", "denominator", "grain"] if "ratio-request" in signals else ["metric-concept", "entity-key", "grain"] if "distinct-count-request" in signals else []
    if metric_slots and all(_resolved_slot(slots, name) for name in metric_slots):
        add("metric-definition", {
            "kind": "ratio" if "ratio-request" in signals else "distinct-count",
            "slots": {name: _resolved_slot(slots, name).get("value") for name in metric_slots},
        })

    source_profile = _resolved_slot(slots, "source-profile")
    if source_profile and list(source_profile.get("evidenceRefs") or []):
        add("field-profile", {"value": source_profile.get("value"), "evidenceRefs": source_profile.get("evidenceRefs")})

    source = _record(receipt.get("source"))
    source_fingerprint = source.get("sourceFingerprint") or source.get("dataFingerprint") or semantic_context.get("dataFingerprint")
    if _valid_fingerprint(source_fingerprint):
        add("source-fingerprint", {"fingerprint": source_fingerprint})

    if receipt.get("schema") == "aibi-query-plan-receipt/v1" and receipt.get("status") == "executed" and _nonempty(receipt.get("receiptKey")):
        add("query-plan-receipt", {"receiptKey": receipt.get("receiptKey"), "status": "executed"})

    proofs = _relationship_path_proofs(receipt)
    cross_table = _cross_table_context(answer, receipt, execution_plan)
    relationship_validation = validate_relationship_path_proof(
        proofs,
        cross_table=cross_table,
        expected_relationships=_expected_relationships(receipt, execution_plan),
    )
    if cross_table and relationship_validation.get("proven") is True:
        for index, proof in enumerate(proofs):
            fingerprint = str(proof.get("proofFingerprint") or "")
            hop_index = int(proof.get("hopIndex") if isinstance(proof.get("hopIndex"), int) else index)
            ref = {"hopIndex": hop_index, "proofFingerprint": fingerprint, "relationKey": proof.get("relationKey")}
            add("relationship-path-proof", ref)
            if fingerprint:
                add(f"relationship-path-proof:{hop_index}:{fingerprint[:20]}", ref)
        if proofs and all(isinstance(proof.get("cardinalityProof"), dict) and bool(proof.get("cardinalityProof")) for proof in proofs):
            add("cardinality-profile", {"hopCount": len(proofs), "proofFingerprints": [proof.get("proofFingerprint") for proof in proofs]})

    comparison_plan = _record(semantic_plan.get("comparisonPlan"))
    if comparison_plan.get("status") == "ready" and _nonempty(comparison_plan.get("currentWindow")) and _nonempty(comparison_plan.get("baselineWindow")):
        add("comparison-baseline", {
            "currentWindow": comparison_plan.get("currentWindow"),
            "baselineWindow": comparison_plan.get("baselineWindow"),
            "timeField": comparison_plan.get("timeField"),
        })
    elif (comparison_slot := _resolved_slot(slots, "comparison-baseline")):
        add("comparison-baseline", {
            "value": comparison_slot.get("value"),
            "source": comparison_slot.get("source"),
        })

    driver_breakdown = _record(answer.get("driverBreakdown"))
    if driver_breakdown.get("status") == "ready" and driver_breakdown.get("evidenceRefs"):
        add("driver-breakdown", {"fingerprint": driver_breakdown.get("fingerprint"), "evidenceRefs": driver_breakdown.get("evidenceRefs")})

    source_intelligence = _record(answer.get("sourceIntelligenceRun"))
    if source_intelligence.get("usableForPlanning") is True and _valid_fingerprint(source_intelligence.get("fingerprint")):
        add("source-intelligence-run", {"fingerprint": source_intelligence.get("fingerprint")})
    return inventory


def _business_step_evidence_refs(answer: dict[str, Any], business_understanding: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    if business_understanding.get("fingerprint"):
        refs.append({"type": "businessUnderstanding", "fingerprint": business_understanding.get("fingerprint")})
    refs.extend(item for item in business_understanding.get("evidenceRefs") or [] if isinstance(item, dict))
    for name, values in _collect_evidence(answer).items():
        if name.startswith("relationship-path-proof:"):
            continue
        for value in values:
            refs.append({"type": name, **value})
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ref in refs:
        identity = _hash(ref)
        if identity not in seen:
            seen.add(identity)
            unique.append(ref)
    return unique


def _validate_required_evidence(plan: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any]:
    inventory = _collect_evidence(answer)
    results: list[dict[str, Any]] = []
    blockers: list[str] = []
    plan_executable = plan.get("status") != "blocked"
    for step in plan.get("steps") or []:
        if not isinstance(step, dict):
            continue
        required = _unique_strings(step.get("requiredEvidence"))
        # A blocked plan is intentionally allowed to omit evidence it is
        # asking the user or runtime to supply. Completed claims are not.
        enforce = plan_executable and step.get("status") == "completed"
        for requirement in required:
            canonical = _canonical_evidence_name(requirement)
            satisfied = bool(inventory.get(canonical)) if enforce else None
            results.append({
                "stepKey": step.get("stepKey"),
                "requirement": requirement,
                "canonicalRequirement": canonical,
                "status": "passed" if satisfied is True else "missing" if satisfied is False else "skipped-blocked-step",
                "evidenceCount": len(inventory.get(canonical) or []),
            })
            if satisfied is False:
                blockers.append(f"evidence:{step.get('stepKey')}:missing:{requirement}")
    return {
        "status": "passed" if not blockers else "failed",
        "results": results,
        "availableEvidence": sorted(inventory),
        "blockers": blockers,
    }


def _validate_semantic_guards(
    plan: dict[str, Any],
    answer: dict[str, Any],
    *,
    policy_hooks: dict[str, Any],
) -> dict[str, Any]:
    inventory = _collect_evidence(answer)
    business_understanding = _record(answer.get("businessUnderstanding"))
    intent_frame = _record(answer.get("intentFrame"))
    semantic_context = _record(answer.get("semanticContext"))
    receipt = _record(answer.get("queryPlanReceipt"))
    execution_plan = _execution_plan(answer, receipt)
    slots = _record(business_understanding.get("slots"))
    cross_table = _cross_table_context(answer, receipt, execution_plan)
    relationship_validation = validate_relationship_path_proof(
        _relationship_path_proofs(receipt),
        cross_table=cross_table,
        expected_relationships=_expected_relationships(receipt, execution_plan),
    )
    claims_results = _answer_claims_results(answer)
    result_binding = _record(receipt.get("resultBinding"))
    analysis_unit = _record(answer.get("analysisUnit"))
    unit_validation = _record(analysis_unit.get("validation"))
    receipt_invariants = (
        receipt.get("status") == "executed"
        and _valid_fingerprint(result_binding.get("resultFingerprint"))
        and isinstance(result_binding.get("rowCount"), int)
    )
    unit_invariants = not analysis_unit or (
        analysis_unit.get("status") == "ready"
        and unit_validation.get("status") in {"ready", "passed"}
        and not unit_validation.get("blockers")
        and all(bool(value) for value in _record(unit_validation.get("checks")).values())
        and analysis_unit.get("queryReceiptKey") == receipt.get("receiptKey")
        and analysis_unit.get("resultFingerprint") == result_binding.get("resultFingerprint")
    )
    resolution = _record(intent_frame.get("resolution"))
    proxy_sources = {
        str(slot.get("source") or "").strip().casefold()
        for slot in slots.values()
        if isinstance(slot, dict)
        and any(token in str(slot.get("source") or "").strip().casefold() for token in ("proxy", "fallback", "implicit"))
    }
    signals = {str(item) for item in business_understanding.get("signals") or []}
    method_plan = _record(business_understanding.get("methodPlan"))
    answer_text = json.dumps(_record(answer.get("answerCard")), ensure_ascii=False, sort_keys=True).casefold()
    causal_overclaim = bool(re.search(
        r"(?:证明.{0,24}(?:导致|引起)|(?:导致|引起).{0,24}的原因|\b(?:proves?|caused by|causes?)\b)",
        answer_text,
        re.IGNORECASE,
    ))
    guard_values = {
        "current-context": semantic_context.get("stale") is False and _valid_fingerprint(semantic_context.get("fingerprint")),
        "no-silent-proxy": (
            business_understanding.get("status") in {None, "ready"}
            and not business_understanding.get("blockers")
            and not business_understanding.get("missingSlots")
            and resolution.get("silentDisambiguation") is not True
            and not proxy_sources
        ),
        "no-implicit-denominator": (
            "ratio-request" not in set(str(item) for item in business_understanding.get("signals") or [])
            or bool(_resolved_slot(slots, "numerator") and _resolved_slot(slots, "denominator"))
        ),
        "field-provenance": bool(inventory.get("field-provenance")),
        "verified-relationship-path": not cross_table or relationship_validation.get("proven") is True,
        "relationship-proof-when-needed": not cross_table or relationship_validation.get("proven") is True,
        "grain-explicit": bool(inventory.get("grain-definition")),
        "time-window-complete": bool(inventory.get("comparison-baseline")),
        "facts-before-hypotheses": bool(inventory.get("driver-breakdown") and inventory.get("query-plan-receipt")),
        "receipt-before-claim": not claims_results or bool(inventory.get("query-plan-receipt")),
        "result-invariants": not claims_results or bool(receipt_invariants and unit_invariants),
        "no-permission-escalation": (
            policy_hooks.get("status") == "passed"
            and _record(plan.get("workflowExecution")).get("providerCanWrite") is False
            and _record(plan.get("workflowExecution")).get("reviewerCapabilitySubmissionCount") == 0
            and _record(plan.get("workflowExecution")).get("reviewerToolCallCount") == 0
        ),
        "ordered-stages": bool(
            _resolved_slot(slots, "funnel-stages")
            and _resolved_slot(slots, "stage-order")
        ),
        "same-entity-population": bool(
            _resolved_slot(slots, "entity-key")
            and ("funnel-request" not in signals or _resolved_slot(slots, "population"))
        ),
        "cohort-window-complete": all(_resolved_slot(slots, name) for name in (
            "cohort-entry-event", "retention-event", "cohort-period", "time-scope", "time-field",
        )),
        "right-censoring-explicit": bool(
            _resolved_slot(slots, "cohort-period") and _resolved_slot(slots, "time-scope")
        ),
        "comparable-baseline": bool(_resolved_slot(slots, "comparison-baseline")),
        "additive-contribution": all(_resolved_slot(slots, name) for name in (
            "contribution-total", "dimension", "grain",
        )),
        "no-causal-overclaim": not causal_overclaim,
        "dashboard-evidence-only": bool(
            method_plan.get("skillId") == "dashboard-decision-design"
            and method_plan.get("status") == "ready"
            and _resolved_slot(slots, "measure")
            and _resolved_slot(slots, "dimension")
            and _resolved_slot(slots, "time-scope")
        ),
    }
    results: list[dict[str, Any]] = []
    blockers: list[str] = []
    plan_executable = plan.get("status") != "blocked"
    for step in plan.get("steps") or []:
        if not isinstance(step, dict):
            continue
        guards = _unique_strings(step.get("guards"))
        enforce = plan_executable and step.get("status") == "completed"
        for guard in guards:
            canonical = _canonical_evidence_name(guard)
            satisfied = guard_values.get(canonical, False) if enforce else None
            results.append({
                "stepKey": step.get("stepKey"),
                "guard": guard,
                "status": "passed" if satisfied is True else "failed" if satisfied is False else "skipped-blocked-step",
                "supported": canonical in guard_values,
            })
            if satisfied is False:
                reason = "unsupported" if canonical not in guard_values else "failed"
                blockers.append(f"guard:{step.get('stepKey')}:{reason}:{guard}")
    return {"status": "passed" if not blockers else "failed", "results": results, "blockers": blockers}


def _matched_skills(skill_match: dict[str, Any]) -> list[dict[str, Any]]:
    skills: list[dict[str, Any]] = []
    primary = skill_match.get("selected")
    if isinstance(primary, dict):
        skills.append({**primary, "skillKind": str(primary.get("skillKind") or "analysis")})
    supporting_values = [skill_match.get("supporting"), skill_match.get("supportingSkills")]
    for values in supporting_values:
        for item in values or [] if isinstance(values, list) else []:
            if not isinstance(item, dict):
                continue
            normalized = {**item, "skillKind": str(item.get("skillKind") or "understanding")}
            identity = (normalized.get("skillId"), normalized.get("version"))
            if not any((existing.get("skillId"), existing.get("version")) == identity for existing in skills):
                skills.append(normalized)
    return skills


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


def _step(*, key: str, kind: str, capability_id: str, depends_on: list[str], input_refs: list[str], required_evidence: list[str], output_schema: str, status: str = "completed", blockers: list[Any] | None = None, artifact_refs: list[Any] | None = None, evidence_refs: list[Any] | None = None, guards: list[Any] | None = None, declared_blocking_rules: list[Any] | None = None) -> dict[str, Any]:
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
        "completionChecks": _unique_strings("workspace-bound", "schema-valid", "evidence-complete", guards),
        "guards": _unique_strings(guards),
        "declaredBlockingRules": _unique_strings(declared_blocking_rules),
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
    business_understanding = _record(answer.get("businessUnderstanding"))
    method_plan = _record(business_understanding.get("methodPlan"))
    skill_match = _record(business_understanding.get("skillMatch")) or _record(answer.get("analyticalSkillMatch"))
    matched_skills = _matched_skills(skill_match)
    supporting_skills = [skill for skill in matched_skills if skill.get("skillKind") == "understanding"]
    business_status = str(business_understanding.get("status") or "ready")
    business_blockers = _normalize_blockers(business_understanding.get("blockers"))
    if business_status == "needs-clarification" and not business_blockers:
        business_blockers = ["business-understanding-needs-clarification"]
    business_required_evidence = _unique_strings(
        business_understanding.get("requiredEvidence"),
        *(skill.get("requiredEvidence") for skill in supporting_skills),
    )
    business_guards = _unique_strings(
        business_understanding.get("guards"),
        *(skill.get("semanticGuards") for skill in supporting_skills),
    )
    business_rules = _unique_strings(*(skill.get("blockingRules") for skill in supporting_skills))
    receipt_record = receipt or {}
    execution_plan = _execution_plan(answer, receipt_record)
    relationship_path_proofs = _relationship_path_proofs(receipt_record)
    query_blockers = _query_blockers(receipt_record, execution_plan, relationship_path_proofs)
    relationship_required, relationship_evidence_refs = _relationship_proof_evidence(relationship_path_proofs)
    plan_blockers = [*business_blockers, *semantic_blockers, *query_blockers]
    steps = [
        _step(key="step-001-intent", kind="intent", capability_id="agent.intent.resolve", depends_on=[], input_refs=["turn.prompt"], required_evidence=[], output_schema="aibi-agent-intent-frame/v1"),
        _step(
            key="step-002-business-understanding",
            kind="business-understanding",
            capability_id="agent.context.route",
            depends_on=["step-001-intent"],
            input_refs=["turn.prompt", "turn.intentFrame", "answer.businessUnderstanding"],
            required_evidence=business_required_evidence,
            output_schema="aibi-business-understanding-frame/v1",
            status="blocked" if business_blockers else "completed",
            blockers=business_blockers,
            guards=business_guards,
            declared_blocking_rules=business_rules,
            evidence_refs=_business_step_evidence_refs(answer, business_understanding),
        ),
        _step(key="step-002-context", kind="context", capability_id="agent.context.route", depends_on=["step-002-business-understanding"], input_refs=["turn.intentFrame", "answer.businessUnderstanding"], required_evidence=[], output_schema="aibi-semantic-context-bundle/v1"),
    ]
    semantic_dep = "step-002-context"
    if method_plan:
        method_missing = _unique_strings(method_plan.get("missingSlots"))
        method_blockers = [f"method-slot · {item} · required-by-method-skill" for item in method_missing]
        steps.append(_step(
            key="step-002-method",
            kind="analysis-method",
            capability_id="agent.semantic.plan",
            depends_on=[semantic_dep],
            input_refs=["answer.businessUnderstanding.methodPlan", "turn.semanticContext"],
            required_evidence=_unique_strings(method_plan.get("requiredEvidence")),
            output_schema="aibi-analysis-method-plan/v1",
            status="blocked" if method_plan.get("status") == "blocked" or method_blockers else "completed",
            blockers=method_blockers,
            guards=_unique_strings(method_plan.get("semanticGuards")),
            evidence_refs=_business_step_evidence_refs(answer, business_understanding),
        ))
        semantic_dep = "step-002-method"
    steps.append(_step(
            key="step-003-semantic",
            kind="semantic",
            capability_id="agent.semantic.plan",
            depends_on=[semantic_dep],
            input_refs=["turn.semanticContext"],
            required_evidence=["field-provenance"] if semantic_status == "ready" else [],
            output_schema="aibi-semantic-query-plan/v1",
            status="blocked" if business_blockers or semantic_blockers else "completed",
            blockers=[*business_blockers, *semantic_blockers],
        ))
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
    skill_refs: list[dict[str, Any]] = []
    for skill in matched_skills:
        reference = {
            "skillId": skill.get("skillId"),
            "version": skill.get("version"),
            "fingerprint": skill.get("fingerprint"),
            "status": skill.get("status"),
            "skillKind": skill.get("skillKind"),
        }
        for key in (
            "activeSignals",
            "requiredSlots",
            "missingSlots",
            "allowedCapabilities",
            "semanticGuards",
            "compatibleContracts",
            "missingRoles",
            "missingDomainPacks",
            "selectionEvidence",
        ):
            if key in skill:
                reference[key] = skill.get(key)
        skill_refs.append(reference)
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
        "businessUnderstandingSchema": not answer.get("businessUnderstanding") or (
            isinstance(answer.get("businessUnderstanding"), dict)
            and answer.get("businessUnderstanding", {}).get("schema") == "aibi-business-understanding-frame/v1"
        ),
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
        skill_match=(
            answer.get("businessUnderstanding", {}).get("skillMatch")
            if isinstance(answer.get("businessUnderstanding"), dict) and isinstance(answer.get("businessUnderstanding", {}).get("skillMatch"), dict)
            else answer.get("analyticalSkillMatch") if isinstance(answer.get("analyticalSkillMatch"), dict) else None
        ),
    )
    if policy_hooks["status"] != "passed":
        blockers.extend(f"policy:{item}" for item in policy_hooks["blockers"])
    evidence_validation = _validate_required_evidence(plan, answer)
    semantic_guard_validation = _validate_semantic_guards(plan, answer, policy_hooks=policy_hooks)
    checks["requiredEvidenceSatisfied"] = evidence_validation["status"] == "passed"
    checks["semanticGuardsSatisfied"] = semantic_guard_validation["status"] == "passed"
    blockers.extend(evidence_validation["blockers"])
    blockers.extend(semantic_guard_validation["blockers"])
    semantic_status = str(answer.get("semanticPlan", {}).get("status") or "not-applicable")
    unresolved = list(answer.get("intentFrame", {}).get("unresolved") or [])
    receipt = _record(answer.get("queryPlanReceipt"))
    execution_plan = _execution_plan(answer, receipt)
    query_blockers = _query_blockers(receipt, execution_plan, _relationship_path_proofs(receipt))
    business_understanding = _record(answer.get("businessUnderstanding"))
    business_status = str(business_understanding.get("status") or "ready")
    business_blockers = _normalize_blockers(business_understanding.get("blockers"))
    outcome = "blocked" if business_status == "needs-clarification" or business_blockers or semantic_status not in {"ready", "not-applicable"} or unresolved or query_blockers else "completed"
    if outcome == "blocked":
        blockers.extend([f"business:{business_status}"] if business_status == "needs-clarification" else [])
        blockers.extend(f"business:{item}" for item in business_blockers)
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
        "evidenceValidation": evidence_validation,
        "semanticGuardValidation": semantic_guard_validation,
        "fingerprint": _hash({
            "plan": plan.get("fingerprint"),
            "checks": checks,
            "blockers": blockers,
            "evidenceValidation": evidence_validation,
            "semanticGuardValidation": semantic_guard_validation,
        }),
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
        {"eventType": "business-understanding-ready", "stepKey": "step-002-business-understanding", "status": next((str(step.get("status")) for step in plan.get("steps") or [] if step.get("stepKey") == "step-002-business-understanding"), "completed"), "summary": "业务口径已检查"},
        {"eventType": "context-ready", "stepKey": "step-002-context", "status": "completed", "summary": "语义上下文已绑定"},
        {"eventType": "plan-ready", "stepKey": None, "status": str(plan.get("status") or "ready"), "summary": "证据计划已生成"},
    ]
    for step in plan.get("steps") or []:
        if step.get("stepKey") in {"step-001-intent", "step-002-business-understanding", "step-002-context", "step-090-verify", "step-100-answer"}:
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
