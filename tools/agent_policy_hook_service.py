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
    "skill-declarations-valid",
    "skill-compatible-contracts",
    "skill-no-permission-escalation",
    "skill-resource-limits",
    "evidence-reference-bound",
)
FORBIDDEN_DECLARATION_KEYS = {"code", "command", "commands", "script", "sql", "url", "uri", "endpoint", "executable", "interpreter", "tool", "tools"}
KNOWN_SKILL_CONTRACTS = {
    "aibi-agent-intent-frame/v1",
    "aibi-business-understanding-frame/v1",
    "aibi-semantic-context-bundle/v1",
    "aibi-semantic-query-plan/v1",
    "aibi-agent-evidence-plan/v1",
    "aibi-query-plan-receipt/v1",
    "aibi-agent-answer/v1",
    "aibi-analysis-method-plan/v1",
}


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


def _matched_skills(skill_match: dict[str, Any] | None) -> list[dict[str, Any]]:
    match = skill_match if isinstance(skill_match, dict) else {}
    result: list[dict[str, Any]] = []
    selected = match.get("selected")
    if isinstance(selected, dict):
        result.append(selected)
    for key in ("supporting", "supportingSkills"):
        values = match.get(key)
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict):
                continue
            identity = (item.get("skillId"), item.get("version"))
            if not any((existing.get("skillId"), existing.get("version")) == identity for existing in result):
                result.append(item)
    return result


def _skill_check(skill: dict[str, Any]) -> dict[str, Any]:
    capabilities = [str(item) for item in skill.get("allowedCapabilities") or []]
    limits = skill.get("resourceLimits") if isinstance(skill.get("resourceLimits"), dict) else {}
    contracts = [str(item) for item in skill.get("compatibleContracts") or []]
    # Optional fields remain optional for persisted v1 matches created before
    # business-understanding skills existed. If declared, they are enforced.
    declaration_valid = bool(skill.get("skillId") and skill.get("version")) and (
        not skill.get("skillKind") or skill.get("skillKind") in {"analysis", "understanding"}
    ) and (not skill.get("schema") or skill.get("schema") == "aibi-analytical-skill/v1") and (
        not skill.get("fingerprint") or len(str(skill.get("fingerprint"))) == 64
    )
    contracts_valid = not contracts or all(item in KNOWN_SKILL_CONTRACTS for item in contracts)
    resources_valid = (
        not limits
        or 1 <= int(limits.get("maxSteps") or 0) <= 32
        and 1 <= int(limits.get("maxRows") or 0) <= 2_000
    )
    return {
        "skillId": skill.get("skillId"),
        "skillKind": skill.get("skillKind") or "legacy",
        "declarationValid": declaration_valid,
        "capabilitiesValid": all(item in AGENT_CAPABILITIES for item in capabilities),
        "resourcesValid": resources_valid,
        "compatibleContractsValid": contracts_valid,
        "compatibleContracts": contracts,
    }


def evaluate_agent_policy_hooks(*, workspace_id: str, plan: dict[str, Any], skill_match: dict[str, Any] | None) -> dict[str, Any]:
    skills = _matched_skills(skill_match)
    selected = skills[0] if skills else None
    plan_capabilities = [str(step.get("capabilityId") or "") for step in plan.get("steps") or []]
    skill_capabilities = [str(item) for skill in skills for item in skill.get("allowedCapabilities") or []]
    max_steps = int(selected.get("resourceLimits", {}).get("maxSteps") or 32) if selected else 32
    forbidden = [path for index, skill in enumerate(skills) for path in _forbidden_paths(skill, f"skills[{index}]")]
    skill_checks = [_skill_check(skill) for skill in skills]
    evidence_refs = [str(item) for step in plan.get("steps") or [] for item in step.get("requiredEvidence") or []]
    mutation_modes_match = all(
        step.get("capabilityId") in AGENT_CAPABILITIES
        and step.get("mutationMode") == AGENT_CAPABILITIES[step.get("capabilityId")]
        for step in plan.get("steps") or []
    )
    method_capability_intersection = (
        not selected
        or selected.get("outputSchema") != "aibi-analysis-method-plan/v1"
        or set(plan_capabilities).issubset(set(str(item) for item in selected.get("allowedCapabilities") or []))
    )
    results = {
        "workspace-bound": bool(workspace_id) and plan.get("workspaceId") == workspace_id,
        "registered-capabilities-only": all(item in AGENT_CAPABILITIES for item in [*plan_capabilities, *skill_capabilities]),
        "declaration-only-skill": not forbidden,
        "skill-declarations-valid": all(item["declarationValid"] for item in skill_checks),
        "skill-compatible-contracts": all(item["compatibleContractsValid"] for item in skill_checks),
        "skill-no-permission-escalation": mutation_modes_match and method_capability_intersection and all(item["capabilitiesValid"] for item in skill_checks),
        "skill-resource-limits": len(plan.get("steps") or []) <= max_steps and all(item["resourcesValid"] for item in skill_checks),
        "evidence-reference-bound": all(item and len(item) <= 128 for item in evidence_refs),
    }
    blockers = [hook for hook in POLICY_HOOKS if not results[hook]]
    return {
        "schema": POLICY_SCHEMA,
        "status": "passed" if not blockers else "blocked",
        "fixedHooks": list(POLICY_HOOKS),
        "results": results,
        "blockers": blockers,
        "details": {"forbiddenPaths": forbidden, "planCapabilityCount": len(plan_capabilities), "skillCapabilityCount": len(skill_capabilities), "methodCapabilityIntersection": method_capability_intersection, "skillCount": len(skills), "maxSteps": max_steps, "skillChecks": skill_checks},
        "fingerprint": _hash({"workspaceId": workspace_id, "plan": plan.get("fingerprint"), "skills": skills, "results": results}),
    }
