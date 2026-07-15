from __future__ import annotations

import hashlib
import json
from typing import Any


CONTEXT_SCHEMA = "aibi-semantic-context-bundle/v1"


def _fingerprint(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_semantic_context_bundle(*, workspace_id: str, intent_frame: dict[str, Any], semantic_plan: dict[str, Any], selected_table: dict[str, Any] | None, table_selection_confidence: str, context_matches: dict[str, Any], recalled_queries: list[dict[str, Any]], domain_pack_context: dict[str, Any], knowledge_match: dict[str, Any] | None) -> dict[str, Any]:
    field_resolution = semantic_plan.get("fieldResolution", {})
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
    }
    missing_slots = [{"kind": item.get("kind"), "mention": item.get("mention"), "reason": item.get("reason")} for item in intent_frame.get("unresolved") or []]
    fingerprint_input = {"workspaceId": workspace_id, "intent": intent_frame, "semanticPlan": semantic_plan, "sources": sources}
    return {
        "schema": CONTEXT_SCHEMA,
        "workspaceId": workspace_id,
        "retrievalPolicy": {"strategy": "deterministic-first", "reranker": "disabled", "ambiguityGatePreserved": True},
        "sources": sources,
        "missingSlots": missing_slots,
        "stale": False,
        "fingerprint": _fingerprint(fingerprint_input),
    }
