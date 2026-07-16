from __future__ import annotations

import hashlib
import json
from typing import Any


CONTEXT_SCHEMA = "aibi-semantic-context-bundle/v1"


def _fingerprint(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_semantic_context_bundle(*, workspace_id: str, intent_frame: dict[str, Any], semantic_plan: dict[str, Any], selected_table: dict[str, Any] | None, table_selection_confidence: str, context_matches: dict[str, Any], recalled_queries: list[dict[str, Any]], domain_pack_context: dict[str, Any], knowledge_match: dict[str, Any] | None, analytical_skill_match: dict[str, Any] | None = None, session_context: dict[str, Any] | None = None, business_understanding: dict[str, Any] | None = None) -> dict[str, Any]:
    field_resolution = semantic_plan.get("fieldResolution", {})
    skill_sources: list[dict[str, Any]] = []
    if isinstance(analytical_skill_match, dict):
        selected_skill = analytical_skill_match.get("selected")
        if isinstance(selected_skill, dict):
            skill_sources.append(selected_skill)
        for key in ("supporting", "supportingSkills"):
            for skill in analytical_skill_match.get(key) or []:
                if isinstance(skill, dict) and skill not in skill_sources:
                    skill_sources.append(skill)
    if isinstance(business_understanding, dict):
        for skill in business_understanding.get("supportingSkills") or []:
            if isinstance(skill, dict) and skill not in skill_sources:
                skill_sources.append(skill)
    sources = {
        "table": {
            "tableKey": selected_table.get("table_key") if selected_table else None,
            "displayName": selected_table.get("display_name") if selected_table else None,
            "reason": table_selection_confidence,
        },
        "fields": [{"id": item.get("id"), "tableKey": item.get("tableKey"), "field": item.get("field"), "role": item.get("role"), "score": item.get("confidence"), "reason": item.get("source") or "semantic-plan"} for item in field_resolution.get("selected") or []],
        "unresolvedFields": [{"mention": item.get("mention"), "reason": item.get("reason"), "candidates": item.get("candidates") or []} for item in field_resolution.get("unresolved") or []],
        "terms": [{"termKey": item.get("term_key"), "name": item.get("canonical_name"), "definition": item.get("definition"), "reason": "context-term-match"} for item in context_matches.get("terms") or []],
        "rules": [{"ruleKey": item.get("rule_key"), "title": item.get("title"), "statement": item.get("statement"), "reason": "context-rule-match"} for item in context_matches.get("rules") or []],
        "confirmedQueries": [{"queryKey": item.get("query_key"), "question": item.get("question"), "score": item.get("matchScore"), "reason": "confirmed-query-recall"} for item in recalled_queries],
        "knowledgeRules": [{"packId": knowledge_match.get("packId"), "version": knowledge_match.get("packVersion"), "ruleId": knowledge_match.get("ruleId"), "title": knowledge_match.get("title"), "grain": knowledge_match.get("grain"), "reason": "enabled-domain-pack-rule"}] if knowledge_match else [],
        "domainPacks": domain_pack_context.get("enabledDomainPacks") or domain_pack_context.get("enabled") or [],
        "analyticalSkills": skill_sources,
        "session": {
            "sessionKey": session_context.get("sessionKey"),
            "currentTurnKey": session_context.get("currentTurnKey"),
            "preservedRefs": session_context.get("preservedRefs") or [],
            "staleRefs": session_context.get("staleRefs") or [],
            "unresolved": session_context.get("unresolved") or [],
            "blockers": session_context.get("blockers") or [],
            "snapshotFingerprint": (session_context.get("latestSnapshot") or {}).get("fingerprint") if isinstance(session_context.get("latestSnapshot"), dict) else None,
            "sourceFingerprint": session_context.get("sourceFingerprint"),
            "businessFactPromotion": "forbidden",
        } if isinstance(session_context, dict) else None,
    }
    missing_slots = [{"kind": item.get("kind"), "mention": item.get("mention"), "reason": item.get("reason")} for item in intent_frame.get("unresolved") or []]
    understanding = business_understanding if isinstance(business_understanding, dict) else None
    fingerprint_input = {"workspaceId": workspace_id, "intent": intent_frame, "semanticPlan": semantic_plan, "sources": sources, "businessUnderstanding": understanding}
    return {
        "schema": CONTEXT_SCHEMA,
        "workspaceId": workspace_id,
        "retrievalPolicy": {"strategy": "deterministic-first", "reranker": "disabled", "ambiguityGatePreserved": True},
        "sources": sources,
        "businessUnderstanding": understanding,
        "missingSlots": missing_slots,
        "stale": False,
        "fingerprint": _fingerprint(fingerprint_input),
    }
