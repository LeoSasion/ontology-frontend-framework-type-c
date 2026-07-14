from __future__ import annotations

import argparse
import hashlib
import json
from typing import Any

from capability_contract_service import build_capability_contract


WORKFLOW_STAGE_SCHEMA = "aibi-workflow-stage/v1"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def safe_argument_payload(args: argparse.Namespace | dict[str, Any] | None) -> dict[str, Any]:
    values = vars(args) if isinstance(args, argparse.Namespace) else dict(args or {})
    hidden = {"json", "command", "yes"}
    return {key: value for key, value in sorted(values.items()) if key not in hidden and value not in (None, "", [], {})}


def build_workflow_stage(
    *,
    command: str,
    args: argparse.Namespace | dict[str, Any] | None,
    result: dict[str, Any] | None,
    capability: dict[str, Any] | None = None,
    sequence: int = 1,
    status: str | None = None,
) -> dict[str, Any]:
    capability = capability or build_capability_contract(command)
    result = dict(result or {})
    evidence = list(result.get("evidence") or [])
    artifacts = list(result.get("artifacts") or [])
    if status is None:
        status = "failed" if result.get("ok") is False else "waiting-confirmation" if result.get("requiresConfirmation") else "completed"
    input_value = safe_argument_payload(args)
    evidence_material = {"evidence": evidence, "artifacts": artifacts}
    return {
        "schema": WORKFLOW_STAGE_SCHEMA,
        "stageKey": f"stage-{sequence:03d}-{command}",
        "sequence": max(1, int(sequence)),
        "kind": str(capability.get("domain") or "misc"),
        "capabilityId": capability["capabilityId"],
        "command": command,
        "status": status,
        "inputFingerprint": _hash(input_value),
        "input": input_value,
        "evidenceFingerprint": _hash(evidence_material),
        "evidenceRefs": evidence,
        "artifactRefs": artifacts,
        "requiresConfirmation": bool(result.get("requiresConfirmation")),
        "error": result.get("error") if status == "failed" else None,
        "recovery": {
            "safeState": "no-unconfirmed-write" if status in {"failed", "waiting-confirmation"} else "completed",
            "suggestedNext": list(result.get("suggestedNextCommands") or []),
        },
    }
