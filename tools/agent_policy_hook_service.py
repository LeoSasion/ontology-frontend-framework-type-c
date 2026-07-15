from __future__ import annotations

import hashlib
import json
from typing import Any

from agent_evidence_plan_service import AGENT_CAPABILITIES


POLICY_SCHEMA = "aibi-agent-policy-hooks/v1"
POLICY_HOOKS = (
    "workspace-bound",
    "registered-capabilities-only",
    "declaration-only-skill",
    "skill-resource-limits",
    "evidence-reference-bound",
)
FORBIDDEN_DECLARATION_KEYS = {"code", "command", "commands", "script", "sql", "url", "uri", "endpoint", "executable", "interpreter", "tool", "tools"}


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _forbidden_paths(value: Any, path: str = "skill") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if str(key).casefold() in FORBIDDEN_DECLARATION_KEYS:
                found.append(child)
            found.extend(_forbidden_paths(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_forbidden_paths(item, f"{path}[{index}]"))
    return found


def evaluate_agent_policy_hooks(*, workspace_id: str, plan: dict[str, Any], skill_match: dict[str, Any] | None) -> dict[str, Any]:
    selected = skill_match.get("selected") if isinstance(skill_match, dict) and isinstance(skill_match.get("selected"), dict) else None
    plan_capabilities = [str(step.get("capabilityId") or "") for step in plan.get("steps") or []]
    skill_capabilities = list(selected.get("allowedCapabilities") or []) if selected else []
    max_steps = int(selected.get("resourceLimits", {}).get("maxSteps") or 32) if selected else 32
    forbidden = _forbidden_paths(selected) if selected else []
    evidence_refs = [str(item) for step in plan.get("steps") or [] for item in step.get("requiredEvidence") or []]
    results = {
        "workspace-bound": bool(workspace_id) and plan.get("workspaceId") == workspace_id,
        "registered-capabilities-only": all(item in AGENT_CAPABILITIES for item in [*plan_capabilities, *skill_capabilities]),
        "declaration-only-skill": not forbidden,
        "skill-resource-limits": len(plan.get("steps") or []) <= max_steps,
        "evidence-reference-bound": all(item and len(item) <= 128 for item in evidence_refs),
    }
    blockers = [hook for hook in POLICY_HOOKS if not results[hook]]
    return {
        "schema": POLICY_SCHEMA,
        "status": "passed" if not blockers else "blocked",
        "fixedHooks": list(POLICY_HOOKS),
        "results": results,
        "blockers": blockers,
        "details": {"forbiddenPaths": forbidden, "planCapabilityCount": len(plan_capabilities), "skillCapabilityCount": len(skill_capabilities), "maxSteps": max_steps},
        "fingerprint": _hash({"workspaceId": workspace_id, "plan": plan.get("fingerprint"), "selectedSkill": selected, "results": results}),
    }
