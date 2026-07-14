from __future__ import annotations

import hashlib
import json
from typing import Any


CONTEXT_BUDGET_SCHEMA = "aibi-context-budget/v1"
PRIORITY_ORDER = {"critical": 0, "evidence": 1, "supporting": 2, "diagnostic": 3}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def compact_context_segments(segments: list[dict[str, Any]], max_chars: int) -> dict[str, Any]:
    max_chars = max(256, int(max_chars))
    normalized: list[dict[str, Any]] = []
    for index, segment in enumerate(segments):
        segment_id = str(segment.get("id") or f"segment-{index + 1}")
        priority = str(segment.get("priority") or "supporting")
        if priority not in PRIORITY_ORDER:
            raise ValueError(f"Unsupported context priority: {priority}")
        normalized.append({
            "id": segment_id,
            "priority": priority,
            "required": bool(segment.get("required")) or priority in {"critical", "evidence"},
            "content": segment.get("content"),
            "evidenceRefs": sorted({str(item) for item in segment.get("evidenceRefs", []) if str(item).strip()}),
            "index": index,
        })
    ordered = sorted(normalized, key=lambda item: (0 if item["required"] else 1, PRIORITY_ORDER[item["priority"]], item["index"]))
    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    used = 0
    for item in ordered:
        size = len(_canonical(item["content"]))
        candidate = {key: value for key, value in item.items() if key != "index"}
        candidate["chars"] = size
        if item["required"] or used + size <= max_chars:
            kept.append(candidate)
            used += size
        else:
            dropped.append(candidate)
    required_overflow = sum(item["chars"] for item in kept if item["required"]) > max_chars
    all_required_refs = sorted({ref for item in normalized if item["required"] for ref in item["evidenceRefs"]})
    kept_refs = sorted({ref for item in kept for ref in item["evidenceRefs"]})
    missing_required_refs = sorted(set(all_required_refs) - set(kept_refs))
    status = "blocked" if required_overflow or missing_required_refs else "compacted" if dropped else "within-budget"
    compacted = [{key: value for key, value in item.items() if key not in {"chars", "required"}} for item in kept]
    return {
        "schema": CONTEXT_BUDGET_SCHEMA,
        "status": status,
        "maxChars": max_chars,
        "originalChars": sum(len(_canonical(item["content"])) for item in normalized),
        "retainedChars": used,
        "originalFingerprint": _hash([{key: value for key, value in item.items() if key != "index"} for item in normalized]),
        "retainedFingerprint": _hash(compacted),
        "keptIds": [item["id"] for item in kept],
        "droppedIds": [item["id"] for item in dropped],
        "requiredEvidenceRefs": all_required_refs,
        "missingRequiredEvidenceRefs": missing_required_refs,
        "blockers": [item for item, active in [
            ("required-context-exceeds-budget", required_overflow),
            ("required-evidence-reference-dropped", bool(missing_required_refs)),
        ] if active],
        "segments": compacted,
    }
