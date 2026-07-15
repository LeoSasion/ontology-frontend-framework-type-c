from __future__ import annotations

from typing import Any


CLARIFICATION_SCHEMA = "aibi-agent-clarification/v1"


def build_agent_clarification(intent_frame: dict[str, Any], semantic_context: dict[str, Any]) -> dict[str, Any]:
    unresolved = semantic_context.get("sources", {}).get("unresolvedFields") or []
    items = [{
        "kind": "field-binding",
        "mention": str(item.get("mention") or ""),
        "question": f"“{item.get('mention') or '该字段'}”应使用哪张表中的字段？",
        "reason": str(item.get("reason") or "multiple-field-candidates"),
        "candidates": [{
            "id": candidate.get("id"), "tableKey": candidate.get("tableKey"), "tableName": candidate.get("tableName"),
            "field": candidate.get("field"), "role": candidate.get("role"), "confidence": candidate.get("confidence"),
        } for candidate in item.get("candidates") or []],
    } for item in unresolved]
    required = bool(items)
    return {
        "schema": CLARIFICATION_SCHEMA,
        "status": "required" if required else "not-required",
        "required": required,
        "taskType": intent_frame.get("taskType"),
        "items": items,
        "combined": len(items) > 1,
        "message": "请一次确认所有字段归属后继续分析。" if len(items) > 1 else (items[0]["question"] if items else None),
    }
