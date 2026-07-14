from __future__ import annotations

import argparse
from typing import Any

from capability_contract_service import build_capability_contract
from workflow_stage_service import build_workflow_stage

from bi_cli_contracts import command_semantics


ENVELOPE_SCHEMA_VERSION = "aibi-bi-cli-envelope/v1"


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _artifact_from_path(label: str, value: Any) -> dict[str, Any] | None:
    if not value:
        return None
    return {"label": label, "path": str(value)}


def infer_artifacts(result: dict[str, Any]) -> list[dict[str, Any]]:
    artifacts = list(_as_list(result.get("artifacts")))
    for label, key in [
        ("database", "database"),
        ("output-dir", "outputDir"),
        ("config-export", "outputPath"),
    ]:
        artifact = _artifact_from_path(label, result.get(key))
        if artifact:
            artifacts.append(artifact)
    bundle = result.get("evidenceBundle")
    if isinstance(bundle, dict):
        for label, key in [
            ("evidence-bundle", "bundleDir"),
            ("evidence-manifest", "manifestPath"),
            ("evidence-summary", "summaryPath"),
        ]:
            artifact = _artifact_from_path(label, bundle.get(key))
            if artifact:
                artifacts.append(artifact)
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in artifacts:
        if not isinstance(item, dict):
            continue
        marker = (str(item.get("label") or ""), str(item.get("path") or item.get("value") or ""))
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(item)
    return deduped


def infer_warnings(result: dict[str, Any]) -> list[Any]:
    warnings = list(_as_list(result.get("warnings")))
    health = result.get("health")
    if isinstance(health, dict):
        for note in _as_list(health.get("notes")):
            if isinstance(note, str) and ("missing" in note.lower() or "fallback" in note.lower()):
                warnings.append(note)
    query = result.get("query")
    if isinstance(query, dict) and query.get("fallbackReason"):
        warnings.append(query["fallbackReason"])
    return warnings


def infer_evidence(result: dict[str, Any]) -> list[Any]:
    existing = result.get("evidence")
    if isinstance(existing, list):
        evidence = list(existing)
    elif existing:
        evidence = [existing]
    else:
        evidence = []
    for key in ["evidenceRefs", "evidenceFiles"]:
        evidence.extend(_as_list(result.get(key)))
    bundle = result.get("evidenceBundle")
    if isinstance(bundle, dict):
        evidence.append(
            {
                "type": "evidence-bundle",
                "bundleKey": bundle.get("bundleKey"),
                "manifestPath": bundle.get("manifestPath"),
                "summaryPath": bundle.get("summaryPath"),
            }
        )
    return evidence


def infer_suggested_next_commands(result: dict[str, Any]) -> list[Any]:
    if isinstance(result.get("suggestedNextCommands"), list):
        return result["suggestedNextCommands"]
    if isinstance(result.get("recommendedCommands"), list):
        return result["recommendedCommands"]
    next_actions = result.get("nextActions")
    if isinstance(next_actions, list):
        return next_actions
    return []


def infer_dry_run(args: argparse.Namespace, result: dict[str, Any], semantics: dict[str, Any]) -> bool:
    if "dryRun" in result:
        return bool(result.get("dryRun"))
    if bool(getattr(args, "yes", False)):
        return False
    if bool(result.get("requiresConfirmation")):
        return True
    return bool(semantics.get("dryRunByDefault") and semantics.get("requiresYes"))


def infer_requires_confirmation(args: argparse.Namespace, result: dict[str, Any], dry_run: bool, semantics: dict[str, Any]) -> bool:
    if "requiresConfirmation" in result:
        return bool(result.get("requiresConfirmation"))
    if bool(getattr(args, "yes", False)):
        return False
    if semantics.get("createsActionDraft"):
        return bool(result.get("actionDraft", {}).get("status") == "draft")
    return bool(dry_run and semantics.get("requiresYes"))


def _command_parser(parser: argparse.ArgumentParser | None, command: str) -> argparse.ArgumentParser | None:
    if parser is None:
        return None
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices.get(command)
    return None


def enrich_cli_output(result: dict[str, Any], args: argparse.Namespace, parser: argparse.ArgumentParser | None = None) -> dict[str, Any]:
    command = str(getattr(args, "command", "") or "")
    semantics = command_semantics(command, _command_parser(parser, command))
    result.setdefault("command", command)
    result.setdefault("warnings", infer_warnings(result))
    result.setdefault("artifacts", infer_artifacts(result))
    result.setdefault("evidence", infer_evidence(result))
    result.setdefault("suggestedNextCommands", infer_suggested_next_commands(result))
    dry_run = infer_dry_run(args, result, semantics)
    requires_confirmation = infer_requires_confirmation(args, result, dry_run, semantics)
    result.setdefault("dryRun", dry_run)
    result.setdefault("requiresConfirmation", requires_confirmation)
    result["envelope"] = {
        "schema": ENVELOPE_SCHEMA_VERSION,
        "command": command,
        "ok": bool(result.get("ok", False)),
        "domain": semantics.get("domain"),
        "mutationMode": semantics.get("mutationMode"),
        "dryRun": bool(result.get("dryRun")),
        "requiresConfirmation": bool(result.get("requiresConfirmation")),
        "writesEvidence": bool(semantics.get("writesEvidence")),
        "writesBusinessState": bool(semantics.get("writesBusinessState") and not result.get("dryRun")),
        "artifactCount": len(result.get("artifacts") or []),
        "evidenceCount": len(result.get("evidence") or []),
    }
    capability = build_capability_contract(command, semantics)
    result.setdefault("capability", capability)
    result.setdefault("workflowStage", build_workflow_stage(command=command, args=args, result=result, capability=capability))
    return result


def error_output(command: str, error: Exception) -> dict[str, Any]:
    result = {
        "ok": False,
        "error": str(error),
        "command": command,
        "warnings": [],
        "artifacts": [],
        "evidence": [],
        "suggestedNextCommands": [],
        "dryRun": False,
        "requiresConfirmation": False,
    }
    result["envelope"] = {
        "schema": ENVELOPE_SCHEMA_VERSION,
        "command": command,
        "ok": False,
        "domain": command_semantics(command).get("domain"),
        "mutationMode": command_semantics(command).get("mutationMode"),
        "dryRun": False,
        "requiresConfirmation": False,
        "writesEvidence": False,
        "writesBusinessState": False,
        "artifactCount": 0,
        "evidenceCount": 0,
    }
    capability = build_capability_contract(command)
    result["capability"] = capability
    result["workflowStage"] = build_workflow_stage(command=command, args={}, result=result, capability=capability)
    return result
