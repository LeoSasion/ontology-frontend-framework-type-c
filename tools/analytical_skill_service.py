from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Callable

from agent_evidence_plan_service import AGENT_CAPABILITIES
from bi_cli_core import ROOT


SKILL_SCHEMA = "aibi-analytical-skill/v1"
RUNTIME_SCHEMA = "aibi-analytical-skill-runtime/v1"
CATALOG_SCHEMA = "aibi-analytical-skill-catalog/v1"
SKILL_ROOT = ROOT / "analytical-skills"
SKILL_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
STEP_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
ALLOWED_TASK_TYPES = {"overview", "comparison", "trend", "composition", "ranking", "anomaly", "reconciliation", "diagnosis"}
ALLOWED_ROLES = {"measure", "dimension", "time", "identity", "attribute"}
ALLOWED_CONFIRMATION_MODES = {"read-only", "draft-confirmation"}
ALLOWED_SKILL_KINDS = {"analysis", "understanding"}
ALLOWED_BUSINESS_SIGNALS = {
    "underspecified-question", "ratio-request", "distinct-count-request", "business-term-match",
    "time-comparison", "diagnosis-request", "comparison-request", "cross-table-request",
    "unresolved-field", "relationship-ambiguity", "executable-plan", "data-quality-risk",
    "artifact-request",
    "missing-measure",
    "funnel-request", "cohort-retention-request", "anomaly-triage-request",
    "segment-contribution-request", "driver-investigation-request", "dashboard-decision-request",
    "forecast-readiness-request",
}
ALLOWED_INTENT_SLOTS = {
    "decision-goal", "metric-concept", "measure", "dimension", "time-scope", "time-field",
    "comparison-baseline", "numerator", "denominator", "entity-key", "population", "grain",
    "field-binding", "term-definition", "business-rule", "relationship-path", "source-profile",
    "output-purpose", "filter-semantics", "status-meaning", "unit", "null-policy",
    "funnel-stages", "stage-order", "cohort-entry-event", "retention-event", "cohort-period",
    "anomaly-threshold", "contribution-total", "driver-candidates", "dashboard-audience",
    "review-cadence", "forecast-horizon", "forecast-cutoff",
}
ALLOWED_SEMANTIC_GUARDS = {
    "no-silent-proxy", "no-implicit-denominator", "current-context", "field-provenance",
    "verified-relationship-path", "relationship-proof-when-needed", "grain-explicit",
    "time-window-complete", "receipt-before-claim", "result-invariants", "facts-before-hypotheses",
    "no-permission-escalation",
    "ordered-stages", "same-entity-population", "cohort-window-complete",
    "right-censoring-explicit", "comparable-baseline", "additive-contribution",
    "no-causal-overclaim", "dashboard-evidence-only",
}
CURRENT_SKILL_CONTRACTS = {
    "aibi-agent-intent-frame/v1", "aibi-business-understanding-frame/v1",
    "aibi-semantic-context-bundle/v1", "aibi-semantic-query-plan/v1",
    "aibi-agent-evidence-plan/v1", "aibi-query-plan-receipt/v1",
    "aibi-analysis-method-plan/v1",
}
ALLOWED_KEYS = {
    "schema", "skillId", "version", "displayName", "description", "taskTypes", "requiredRoles",
    "requiredDomainPacks", "allowedCapabilities", "stepTemplate", "requiredEvidence", "blockingRules",
    "outputSchema", "confirmationMode", "resourceLimits", "skillKind", "triggerSignals", "slotRules",
    "semanticGuards", "compatibleContracts",
}
FORBIDDEN_KEYS = {"code", "command", "commands", "script", "sql", "url", "uri", "endpoint", "executable", "interpreter", "tool", "tools"}
FORBIDDEN_TEXT = re.compile(
    r"(?:https?://|file://|\b(?:python|javascript|node|bash|powershell|cmd\.exe|subprocess|eval|exec)\b|\bselect\b.{0,80}\bfrom\b|\binsert\s+into\b|\bdelete\s+from\b|\bupdate\b.{0,80}\bset\b)",
    re.IGNORECASE | re.DOTALL,
)
MAX_MANIFEST_BYTES = 64 * 1024


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _localized(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"Analytical Skill {field} must contain zh and en text.")
    result = {key: str(value.get(key) or "").strip() for key in ("zh", "en")}
    if not all(result.values()):
        raise ValueError(f"Analytical Skill {field} must contain non-empty zh and en text.")
    return result


def _bounded_strings(value: Any, field: str, *, allowed: set[str] | None = None, maximum: int = 32) -> list[str]:
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError(f"Analytical Skill {field} must be a bounded list.")
    result = [str(item or "").strip() for item in value]
    if any(not item for item in result) or len(result) != len(set(result)):
        raise ValueError(f"Analytical Skill {field} contains empty or duplicate values.")
    if allowed is not None and any(item not in allowed for item in result):
        unknown = sorted(set(result) - allowed)
        raise ValueError(f"Analytical Skill {field} contains unsupported values: {', '.join(unknown)}")
    return result


def _reject_executable_content(value: Any, path: str = "manifest") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).strip().casefold()
            if normalized in FORBIDDEN_KEYS:
                raise ValueError(f"Analytical Skill contains forbidden executable field: {path}.{key}")
            _reject_executable_content(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_executable_content(item, f"{path}[{index}]")
    elif isinstance(value, str) and FORBIDDEN_TEXT.search(value):
        raise ValueError(f"Analytical Skill contains forbidden executable or external content: {path}")


def _slot_rules(value: Any) -> list[dict[str, list[str]]]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 16:
        raise ValueError("Analytical Skill slotRules must be a bounded list.")
    result: list[dict[str, list[str]]] = []
    for index, rule in enumerate(value):
        if not isinstance(rule, dict) or set(rule) != {"whenAny", "requireAll"}:
            raise ValueError(f"Analytical Skill slotRules[{index}] must contain only whenAny and requireAll.")
        when_any = _bounded_strings(rule.get("whenAny"), f"slotRules[{index}].whenAny", allowed=ALLOWED_BUSINESS_SIGNALS, maximum=12)
        require_all = _bounded_strings(rule.get("requireAll"), f"slotRules[{index}].requireAll", allowed=ALLOWED_INTENT_SLOTS, maximum=16)
        if not when_any or not require_all:
            raise ValueError(f"Analytical Skill slotRules[{index}] must declare at least one signal and slot.")
        result.append({"whenAny": when_any, "requireAll": require_all})
    return result


def validate_analytical_skill_manifest(raw: Any, *, source_type: str = "external") -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Analytical Skill manifest must be an object.")
    if len(_canonical(raw).encode("utf-8")) > MAX_MANIFEST_BYTES:
        raise ValueError(f"Analytical Skill manifest exceeds {MAX_MANIFEST_BYTES} bytes.")
    unknown_keys = sorted(set(raw) - ALLOWED_KEYS)
    if unknown_keys:
        raise ValueError(f"Analytical Skill contains unsupported fields: {', '.join(unknown_keys)}")
    _reject_executable_content(raw)
    if raw.get("schema") != SKILL_SCHEMA:
        raise ValueError(f"Analytical Skill schema must be {SKILL_SCHEMA}.")
    skill_id = str(raw.get("skillId") or "").strip()
    version = str(raw.get("version") or "").strip()
    if not SKILL_ID_PATTERN.fullmatch(skill_id):
        raise ValueError("Analytical Skill skillId must be a lowercase kebab-case identifier.")
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError("Analytical Skill version must use x.y.z.")
    skill_kind = str(raw.get("skillKind") or "analysis").strip()
    if skill_kind not in ALLOWED_SKILL_KINDS:
        raise ValueError("Analytical Skill skillKind is unsupported.")
    tasks = _bounded_strings(raw.get("taskTypes"), "taskTypes", allowed=ALLOWED_TASK_TYPES, maximum=8)
    if not tasks:
        raise ValueError("Analytical Skill must declare at least one task type.")
    roles = _bounded_strings(raw.get("requiredRoles"), "requiredRoles", allowed=ALLOWED_ROLES, maximum=5)
    packs = _bounded_strings(raw.get("requiredDomainPacks"), "requiredDomainPacks", maximum=16)
    if any(not SKILL_ID_PATTERN.fullmatch(item) for item in packs):
        raise ValueError("Analytical Skill requiredDomainPacks contains an invalid id.")
    capabilities = _bounded_strings(raw.get("allowedCapabilities"), "allowedCapabilities", allowed=set(AGENT_CAPABILITIES), maximum=16)
    if not capabilities:
        raise ValueError("Analytical Skill must declare at least one registered capability.")
    steps = _bounded_strings(raw.get("stepTemplate"), "stepTemplate", maximum=24)
    if not steps or any(not STEP_PATTERN.fullmatch(item) for item in steps):
        raise ValueError("Analytical Skill stepTemplate must contain declarative kebab-case step ids.")
    required_evidence = _bounded_strings(raw.get("requiredEvidence"), "requiredEvidence", maximum=24)
    blockers = _bounded_strings(raw.get("blockingRules"), "blockingRules", maximum=24)
    trigger_signals = _bounded_strings(
        raw.get("triggerSignals") or [],
        "triggerSignals",
        allowed=ALLOWED_BUSINESS_SIGNALS,
        maximum=16,
    )
    slot_rules = _slot_rules(raw.get("slotRules"))
    semantic_guards = _bounded_strings(
        raw.get("semanticGuards") or [],
        "semanticGuards",
        allowed=ALLOWED_SEMANTIC_GUARDS,
        maximum=16,
    )
    compatible_contracts = _bounded_strings(
        raw.get("compatibleContracts") or sorted(CURRENT_SKILL_CONTRACTS),
        "compatibleContracts",
        allowed=CURRENT_SKILL_CONTRACTS,
        maximum=len(CURRENT_SKILL_CONTRACTS),
    )
    if skill_kind == "understanding" and not trigger_signals:
        raise ValueError("An understanding skill must declare at least one trigger signal.")
    output_schema = str(raw.get("outputSchema") or "").strip()
    if not output_schema.startswith("aibi-") or not output_schema.endswith("/v1"):
        raise ValueError("Analytical Skill outputSchema must reference a versioned AIBI-C schema.")
    confirmation_mode = str(raw.get("confirmationMode") or "").strip()
    if confirmation_mode not in ALLOWED_CONFIRMATION_MODES:
        raise ValueError("Analytical Skill confirmationMode is unsupported.")
    limits = raw.get("resourceLimits")
    if not isinstance(limits, dict) or set(limits) != {"maxSteps", "maxRows"}:
        raise ValueError("Analytical Skill resourceLimits must declare only maxSteps and maxRows.")
    max_steps, max_rows = int(limits.get("maxSteps") or 0), int(limits.get("maxRows") or 0)
    if not (1 <= max_steps <= 32 and 1 <= max_rows <= 2_000):
        raise ValueError("Analytical Skill resource limits exceed the fixed safety bounds.")
    manifest = {
        "schema": SKILL_SCHEMA,
        "skillId": skill_id,
        "version": version,
        "displayName": _localized(raw.get("displayName"), "displayName"),
        "description": _localized(raw.get("description"), "description"),
        "skillKind": skill_kind,
        "taskTypes": tasks,
        "requiredRoles": roles,
        "requiredDomainPacks": packs,
        "allowedCapabilities": capabilities,
        "stepTemplate": steps,
        "requiredEvidence": required_evidence,
        "blockingRules": blockers,
        "triggerSignals": trigger_signals,
        "slotRules": slot_rules,
        "semanticGuards": semantic_guards,
        "compatibleContracts": compatible_contracts,
        "outputSchema": output_schema,
        "confirmationMode": confirmation_mode,
        "resourceLimits": {"maxSteps": max_steps, "maxRows": max_rows},
        "sourceType": source_type,
    }
    # Preserve the material identity of legacy v1 manifests. Installation stores
    # the normalized manifest, so merely seeing the optional keys is insufficient:
    # their default values must round-trip without changing an existing
    # skillId@version fingerprint. Only non-default extension semantics opt into
    # the extended identity material.
    uses_skill_extensions = (
        skill_kind != "analysis"
        or bool(trigger_signals)
        or bool(slot_rules)
        or bool(semantic_guards)
        or compatible_contracts != sorted(CURRENT_SKILL_CONTRACTS)
    )
    fingerprint_material = manifest if uses_skill_extensions else {
        key: manifest[key]
        for key in (
            "schema", "skillId", "version", "displayName", "description", "taskTypes",
            "requiredRoles", "requiredDomainPacks", "allowedCapabilities", "stepTemplate",
            "requiredEvidence", "blockingRules", "outputSchema", "confirmationMode",
            "resourceLimits", "sourceType",
        )
    }
    manifest["fingerprint"] = _fingerprint(fingerprint_material)
    return manifest


def _read_manifest(path_value: str) -> tuple[dict[str, Any], Path]:
    candidate = Path(path_value).expanduser()
    candidate = candidate if candidate.is_absolute() else ROOT / candidate
    resolved = candidate.resolve()
    forbidden = {"aibi-a", "aibi-b", "aibi-d", "aibi-e", "aibi项目杂交"}.intersection(part.casefold() for part in resolved.parts)
    if forbidden:
        raise ValueError(f"Analytical Skill manifest crosses a forbidden AIBI repository boundary: {sorted(forbidden)[0]}")
    if resolved.suffix.casefold() != ".json" or not resolved.is_file() or resolved.is_symlink():
        raise ValueError("Analytical Skill manifest must be one regular JSON file.")
    if resolved.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError(f"Analytical Skill manifest exceeds {MAX_MANIFEST_BYTES} bytes.")
    return validate_analytical_skill_manifest(json.loads(resolved.read_text(encoding="utf-8"))), resolved


def builtin_analytical_skills() -> list[dict[str, Any]]:
    manifests: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in sorted(SKILL_ROOT.glob("*.json")) if SKILL_ROOT.is_dir() else []:
        manifest = validate_analytical_skill_manifest(json.loads(path.read_text(encoding="utf-8")), source_type="builtin")
        if manifest["skillId"] in seen:
            raise ValueError(f"Duplicate built-in Analytical Skill id: {manifest['skillId']}")
        seen.add(manifest["skillId"])
        manifests.append(manifest)
    return manifests


def _external_skills(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute("SELECT skill_id, version, manifest_json, fingerprint FROM analytical_skills ORDER BY skill_id").fetchall()
    manifests: list[dict[str, Any]] = []
    for row in rows:
        manifest = validate_analytical_skill_manifest(json.loads(str(row["manifest_json"])), source_type="external")
        if str(row["skill_id"]) != manifest["skillId"] or str(row["version"]) != manifest["version"]:
            raise ValueError(f"Persisted Analytical Skill identity does not match its manifest: {row['skill_id']}")
        if str(row["fingerprint"]) != manifest["fingerprint"]:
            raise RuntimeError(f"Persisted Analytical Skill fingerprint drifted: {row['skill_id']}@{row['version']}")
        manifests.append(manifest)
    return manifests


def analytical_skill_runtime_context(connection: sqlite3.Connection, workspace_id: str) -> dict[str, Any]:
    builtins = builtin_analytical_skills()
    external = _external_skills(connection)
    builtin_ids = {item["skillId"] for item in builtins}
    if builtin_ids.intersection(item["skillId"] for item in external):
        raise ValueError("An external Analytical Skill conflicts with a built-in id.")
    rows = connection.execute(
        "SELECT skill_id, version, enabled, enabled_at, updated_at FROM workspace_analytical_skills WHERE workspace_id = ? ORDER BY skill_id",
        (workspace_id,),
    ).fetchall()
    state = {str(row["skill_id"]): dict(row) for row in rows}
    available: list[dict[str, Any]] = []
    enabled: list[dict[str, Any]] = []
    for manifest in [*builtins, *external]:
        row = state.get(manifest["skillId"])
        default_enabled = manifest["sourceType"] == "builtin"
        is_enabled = (bool(row["enabled"]) if row else default_enabled) and (not row or row["version"] == manifest["version"])
        item = {**manifest, "enabled": is_enabled, "configuredVersion": row["version"] if row else None, "enabledAt": row["enabled_at"] if row else None, "updatedAt": row["updated_at"] if row else None}
        available.append(item)
        if is_enabled:
            enabled.append({key: item[key] for key in (
                "skillId", "version", "fingerprint", "skillKind", "taskTypes", "requiredRoles",
                "requiredDomainPacks", "allowedCapabilities", "stepTemplate", "requiredEvidence",
                "blockingRules", "triggerSignals", "slotRules", "semanticGuards", "compatibleContracts",
                "outputSchema", "confirmationMode", "resourceLimits", "sourceType",
            )})
    material = [{"skillId": item["skillId"], "version": item["version"], "fingerprint": item["fingerprint"]} for item in enabled]
    return {"schema": RUNTIME_SCHEMA, "workspaceId": workspace_id, "enabledAnalyticalSkills": enabled, "availableAnalyticalSkills": available, "fingerprint": _fingerprint(material)}


def match_analytical_skills(
    runtime: dict[str, Any],
    *,
    task_type: str,
    roles: list[str],
    enabled_domain_packs: list[str],
    requested_skill_id: str = "",
    business_signals: list[str] | None = None,
    intent_slots: dict[str, Any] | None = None,
) -> dict[str, Any]:
    role_set, pack_set = set(roles), set(enabled_domain_packs)
    signal_set = set(business_signals or [])
    slot_state = intent_slots or {}
    candidates: list[dict[str, Any]] = []
    supporting: list[dict[str, Any]] = []
    for skill in runtime.get("enabledAnalyticalSkills") or []:
        if task_type not in skill["taskTypes"]:
            continue
        trigger_signals = set(skill.get("triggerSignals") or [])
        active_signals = sorted(trigger_signals & signal_set)
        explicitly_requested = bool(requested_skill_id and skill["skillId"] == requested_skill_id)
        if skill.get("skillKind", "analysis") == "analysis" and trigger_signals and not active_signals and not explicitly_requested:
            continue
        missing_roles = sorted(set(skill["requiredRoles"]) - role_set)
        missing_packs = sorted(set(skill["requiredDomainPacks"]) - pack_set)
        active_rules = [
            rule for rule in skill.get("slotRules") or []
            if set(rule.get("whenAny") or []) & signal_set or explicitly_requested
        ]
        required_slots = sorted({slot for rule in active_rules for slot in rule.get("requireAll") or []})
        missing_slots = [
            slot for slot in required_slots
            if not isinstance(slot_state.get(slot), dict) or slot_state[slot].get("status") != "resolved"
        ]
        if skill.get("skillKind", "analysis") == "understanding":
            if not active_signals:
                continue
            status = "ready" if not missing_roles and not missing_packs and not missing_slots else "blocked"
            supporting.append({
                "skillId": skill["skillId"], "version": skill["version"], "fingerprint": skill["fingerprint"],
                "skillKind": "understanding", "status": status, "activeSignals": active_signals,
                "requiredSlots": required_slots, "missingSlots": missing_slots,
                "missingRoles": missing_roles, "missingDomainPacks": missing_packs,
                "allowedCapabilities": skill["allowedCapabilities"], "stepTemplate": skill["stepTemplate"],
                "requiredEvidence": skill["requiredEvidence"], "blockingRules": skill["blockingRules"],
                "semanticGuards": skill.get("semanticGuards") or [],
                "compatibleContracts": skill.get("compatibleContracts") or [],
                "outputSchema": skill["outputSchema"], "confirmationMode": skill["confirmationMode"],
                "resourceLimits": skill["resourceLimits"],
            })
            continue
        if requested_skill_id and skill["skillId"] != requested_skill_id:
            continue
        status = "ready" if not missing_roles and not missing_packs and not missing_slots else "blocked"
        candidates.append({
            "skillId": skill["skillId"], "version": skill["version"], "fingerprint": skill["fingerprint"],
            "skillKind": "analysis",
            "status": status, "activeSignals": active_signals, "requiredSlots": required_slots,
            "missingSlots": missing_slots, "missingRoles": missing_roles, "missingDomainPacks": missing_packs,
            "selectionEvidence": {
                "signalSpecificity": (len(active_signals) / len(trigger_signals)) if trigger_signals else 0,
                "matchedSignalCount": len(active_signals),
                "taskSpecificity": 1 / len(skill["taskTypes"]),
                "requiredRoleCount": len(skill["requiredRoles"]),
                "matchedRoleCount": len(set(skill["requiredRoles"]) & role_set),
                "requiredSlotCount": len(required_slots),
            },
            "allowedCapabilities": skill["allowedCapabilities"], "stepTemplate": skill["stepTemplate"],
            "requiredEvidence": skill["requiredEvidence"], "blockingRules": skill["blockingRules"],
            "semanticGuards": skill.get("semanticGuards") or [],
            "compatibleContracts": skill.get("compatibleContracts") or [],
            "outputSchema": skill["outputSchema"], "confirmationMode": skill["confirmationMode"], "resourceLimits": skill["resourceLimits"],
        })
    def selection_key(item: dict[str, Any]) -> tuple[Any, ...]:
        evidence = item["selectionEvidence"]
        return (
            not bool(item.get("activeSignals")),
            -float(evidence.get("signalSpecificity") or 0),
            -int(evidence.get("matchedSignalCount") or 0),
            item["status"] != "ready",
            len(item["missingRoles"]) + len(item["missingDomainPacks"]) + len(item.get("missingSlots") or []),
            -float(evidence["taskSpecificity"]),
            -int(evidence["matchedRoleCount"]),
            -int(evidence["requiredRoleCount"]),
        )

    candidates.sort(key=lambda item: (*selection_key(item), item["skillId"]))
    best = candidates[0] if candidates else None
    tied = [item for item in candidates if best and selection_key(item) == selection_key(best)]
    selected = best if requested_skill_id or len(tied) <= 1 else None
    match_status = selected["status"] if selected else "needs-selection" if tied else "not-matched"
    supporting.sort(key=lambda item: (item["status"] != "ready", item["skillId"]))
    supporting_ready = [item for item in supporting if item["status"] == "ready"]
    supporting_blocked = [item for item in supporting if item["status"] == "blocked"]
    return {
        "schema": "aibi-analytical-skill-match/v1", "taskType": task_type, "roles": sorted(role_set),
        "enabledDomainPacks": sorted(pack_set), "requestedSkillId": requested_skill_id or None,
        "status": match_status, "selected": selected, "candidates": candidates,
        "businessSignals": sorted(signal_set), "intentSlots": slot_state,
        "supporting": supporting, "supportingReady": supporting_ready, "supportingBlocked": supporting_blocked,
        "selectionRequired": match_status == "needs-selection",
        "runtimeFingerprint": runtime.get("fingerprint"),
        "fingerprint": _fingerprint({
            "taskType": task_type, "roles": sorted(role_set), "packs": sorted(pack_set),
            "signals": sorted(signal_set), "slots": slot_state, "candidates": candidates, "supporting": supporting,
        }),
    }


def analytical_roles_from_intent_frame(intent_frame: dict[str, Any]) -> list[str]:
    roles: set[str] = set()
    for key, fallback in (("measureConcepts", "measure"), ("dimensionConcepts", "dimension"), ("otherConcepts", "attribute")):
        for item in intent_frame.get(key) or []:
            raw = str(item.get("role") or fallback)
            if raw in {"event_time", "time"}:
                roles.add("time")
            elif raw in {"identity_key", "identity"}:
                roles.add("identity")
            elif raw in {"dimension", "status"}:
                roles.add("dimension")
            elif raw == "measure":
                roles.add("measure")
            else:
                roles.add("attribute")
    return sorted(roles)


def analytical_skills_command(args: argparse.Namespace, *, open_db: Callable[[], sqlite3.Connection], active_workspace_id: Callable[[sqlite3.Connection], str]) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = str(getattr(args, "workspace", "") or active_workspace_id(connection))
        return {"ok": True, "catalogSchema": CATALOG_SCHEMA, **analytical_skill_runtime_context(connection, workspace_id)}


def analytical_skill_lint_command(args: argparse.Namespace) -> dict[str, Any]:
    manifest, path = _read_manifest(str(args.manifest))
    return {"ok": True, "schema": "aibi-analytical-skill-lint/v1", "valid": True, "manifestPath": str(path), "manifest": manifest}


def analytical_skill_install_command(args: argparse.Namespace, *, open_db: Callable[[], sqlite3.Connection], now_iso: Callable[[], str]) -> dict[str, Any]:
    manifest, path = _read_manifest(str(args.manifest))
    if manifest["skillId"] in {item["skillId"] for item in builtin_analytical_skills()}:
        raise ValueError("External Analytical Skill cannot replace a built-in skill.")
    with open_db() as connection:
        existing = connection.execute("SELECT version, fingerprint FROM analytical_skills WHERE skill_id = ?", (manifest["skillId"],)).fetchone()
        change = {"operation": "install" if not existing else "upgrade", "skillId": manifest["skillId"], "fromVersion": existing["version"] if existing else None, "toVersion": manifest["version"], "fingerprint": manifest["fingerprint"], "manifestPath": str(path)}
        if not bool(getattr(args, "yes", False)):
            return {"ok": True, "schema": "aibi-analytical-skill-lifecycle/v1", "dryRun": True, "requiresConfirmation": True, "change": change}
        now = now_iso()
        connection.execute(
            "INSERT INTO analytical_skills(skill_id, version, manifest_json, fingerprint, source_type, installed_at, updated_at) VALUES(?, ?, ?, ?, 'external', ?, ?) ON CONFLICT(skill_id) DO UPDATE SET version=excluded.version, manifest_json=excluded.manifest_json, fingerprint=excluded.fingerprint, updated_at=excluded.updated_at",
            (manifest["skillId"], manifest["version"], _canonical({key: value for key, value in manifest.items() if key not in {"fingerprint", "sourceType"}}), manifest["fingerprint"], now, now),
        )
        connection.execute("UPDATE workspace_analytical_skills SET version = ?, updated_at = ? WHERE skill_id = ?", (manifest["version"], now, manifest["skillId"]))
        connection.commit()
    return {"ok": True, "schema": "aibi-analytical-skill-lifecycle/v1", "confirmed": True, "change": change, "updatedAt": now}


def analytical_skill_uninstall_command(args: argparse.Namespace, *, open_db: Callable[[], sqlite3.Connection], now_iso: Callable[[], str]) -> dict[str, Any]:
    skill_id = str(args.skill).strip()
    with open_db() as connection:
        row = connection.execute("SELECT version, fingerprint FROM analytical_skills WHERE skill_id = ?", (skill_id,)).fetchone()
        if not row:
            raise ValueError(f"Unknown external Analytical Skill: {skill_id}")
        change = {"operation": "uninstall", "skillId": skill_id, "fromVersion": row["version"], "fingerprint": row["fingerprint"]}
        if not bool(getattr(args, "yes", False)):
            return {"ok": True, "schema": "aibi-analytical-skill-lifecycle/v1", "dryRun": True, "requiresConfirmation": True, "change": change}
        connection.execute("DELETE FROM workspace_analytical_skills WHERE skill_id = ?", (skill_id,))
        connection.execute("DELETE FROM analytical_skills WHERE skill_id = ?", (skill_id,))
        connection.commit()
    return {"ok": True, "schema": "aibi-analytical-skill-lifecycle/v1", "confirmed": True, "change": change, "updatedAt": now_iso()}


def analytical_skill_set_command(args: argparse.Namespace, *, open_db: Callable[[], sqlite3.Connection], active_workspace_id: Callable[[sqlite3.Connection], str], now_iso: Callable[[], str]) -> dict[str, Any]:
    skill_id, enabled = str(args.skill).strip(), str(args.state) == "enabled"
    with open_db() as connection:
        workspace_id = str(getattr(args, "workspace", "") or active_workspace_id(connection))
        runtime = analytical_skill_runtime_context(connection, workspace_id)
        manifest = next((item for item in runtime["availableAnalyticalSkills"] if item["skillId"] == skill_id), None)
        if not manifest:
            raise ValueError(f"Unknown Analytical Skill: {skill_id}")
        change = {"operation": "configure", "workspaceId": workspace_id, "skillId": skill_id, "version": manifest["version"], "fromState": "enabled" if manifest["enabled"] else "disabled", "toState": str(args.state)}
        if not bool(getattr(args, "yes", False)):
            return {"ok": True, "schema": "aibi-analytical-skill-configuration/v1", "dryRun": True, "requiresConfirmation": True, "change": change}
        now = now_iso()
        connection.execute(
            "INSERT INTO workspace_analytical_skills(workspace_id, skill_id, version, enabled, enabled_at, updated_at) VALUES(?, ?, ?, ?, ?, ?) ON CONFLICT(workspace_id, skill_id) DO UPDATE SET version=excluded.version, enabled=excluded.enabled, enabled_at=excluded.enabled_at, updated_at=excluded.updated_at",
            (workspace_id, skill_id, manifest["version"], int(enabled), now if enabled else None, now),
        )
        connection.commit()
        updated = analytical_skill_runtime_context(connection, workspace_id)
    return {"ok": True, "schema": "aibi-analytical-skill-configuration/v1", "confirmed": True, "change": change, "runtime": updated}


def analytical_skill_match_command(args: argparse.Namespace, *, open_db: Callable[[], sqlite3.Connection], active_workspace_id: Callable[[sqlite3.Connection], str]) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = str(getattr(args, "workspace", "") or active_workspace_id(connection))
        runtime = analytical_skill_runtime_context(connection, workspace_id)
    match = match_analytical_skills(runtime, task_type=str(args.task_type), roles=list(getattr(args, "role", []) or []), enabled_domain_packs=list(getattr(args, "domain_pack", []) or []), requested_skill_id=str(getattr(args, "skill", "") or ""))
    return {"ok": True, "workspaceId": workspace_id, "runtime": runtime, "match": match}
