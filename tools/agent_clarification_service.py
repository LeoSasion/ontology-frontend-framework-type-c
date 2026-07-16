from __future__ import annotations

from typing import Any


CLARIFICATION_SCHEMA = "aibi-agent-clarification/v1"


def _business_item(business_understanding: dict[str, Any] | None) -> dict[str, Any] | None:
    frame = business_understanding if isinstance(business_understanding, dict) else {}
    active = frame.get("activeClarification")
    if isinstance(active, dict) and str(active.get("question") or "").strip():
        return {
            "kind": str(active.get("kind") or "business-understanding"),
            "mention": str(active.get("mention") or active.get("slot") or "业务口径"),
            "question": str(active["question"]),
            "reason": str(active.get("reason") or "business-slot-unresolved"),
            "candidates": list(active.get("candidates") or []),
            "slot": active.get("slot"),
        }
    for item in frame.get("unresolved") or []:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question") or "").strip()
        if question:
            return {
                "kind": str(item.get("kind") or "business-understanding"),
                "mention": str(item.get("mention") or item.get("slot") or "业务口径"),
                "question": question,
                "reason": str(item.get("reason") or "business-slot-unresolved"),
                "candidates": list(item.get("candidates") or []),
                "slot": item.get("slot"),
            }
    return None


def build_agent_clarification(intent_frame: dict[str, Any], semantic_context: dict[str, Any], business_understanding: dict[str, Any] | None = None) -> dict[str, Any]:
    unresolved = semantic_context.get("sources", {}).get("unresolvedFields") or []
    field_items = [{
        "kind": "field-binding",
        "mention": str(item.get("mention") or ""),
        "question": f"“{item.get('mention') or '该字段'}”应使用哪张表中的字段？",
        "reason": str(item.get("reason") or "multiple-field-candidates"),
        "candidates": [{
            "id": candidate.get("id"), "tableKey": candidate.get("tableKey"), "tableName": candidate.get("tableName"),
            "field": candidate.get("field"), "role": candidate.get("role"), "confidence": candidate.get("confidence"),
        } for candidate in item.get("candidates") or []],
    } for item in unresolved]
    business_item = _business_item(business_understanding)
    # Ask one high-substance business question first. Field bindings remain in
    # the contract so older clients can still render their existing chooser.
    items = [business_item] if business_item else field_items
    required = bool(items)
    return {
        "schema": CLARIFICATION_SCHEMA,
        "status": "required" if required else "not-required",
        "required": required,
        "taskType": intent_frame.get("taskType"),
        "items": items,
        "fieldItems": field_items,
        "combined": False if business_item else len(items) > 1,
        "message": items[0]["question"] if business_item else ("请一次确认所有字段归属后继续分析。" if len(items) > 1 else (items[0]["question"] if items else None)),
    }
