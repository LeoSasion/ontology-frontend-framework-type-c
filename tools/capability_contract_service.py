from __future__ import annotations

import argparse
from typing import Any

from bi_cli_contracts import command_semantics


CAPABILITY_SCHEMA = "aibi-capability-contract/v1"

FILESYSTEM_READ_COMMANDS = {
    "preview-import", "import-commit", "preview-import-folder", "import-folder",
    "source-intelligence", "source-intelligence-job-create", "source-intelligence-job-run",
    "validate-config", "apply-config",
    "discover-connector", "preview-connector", "plan-connector-sync", "domain-pack-lint",
}
FILESYSTEM_WRITE_COMMANDS = {
    "source-intelligence", "source-intelligence-job-run", "export-evidence", "export-analysis", "export-config", "cli-contract",
    "domain-pack-install", "domain-pack-uninstall", "sync-connector",
}
NETWORK_READ_COMMANDS = {"discover-connector", "preview-connector", "plan-connector-sync", "sync-connector"}
OWNED_WORKER_COMMANDS = {"source-intelligence-job-run"}
JOB_SUPPORTED_COMMANDS = {"source-intelligence", "source-intelligence-job-create", "source-intelligence-job-run", "jobs", "job-cancel", "job-recover", "job-process-exit"}
AGENT_ENTRY_COMMANDS = {"ask", "confirm-action", "action-drafts", "semantic-query", "agent-turn-run", "agent-turns", "agent-turn-cancel"}


def _database_access(semantics: dict[str, Any]) -> str:
    if semantics.get("writesBusinessState"):
        return "confirmed-write"
    if semantics.get("mutationMode") in {"runtime-receipt", "evidence-receipt", "action-draft", "action-confirmation"}:
        return "scoped-write"
    return "read-only"


def build_capability_contract(command: str, semantics: dict[str, Any] | None = None) -> dict[str, Any]:
    semantics = dict(semantics or command_semantics(command))
    filesystem = "write" if command in FILESYSTEM_WRITE_COMMANDS else "read" if command in FILESYSTEM_READ_COMMANDS else "none"
    entrypoints = ["cli", "api"]
    if command in AGENT_ENTRY_COMMANDS:
        entrypoints.append("agent")
    if command in JOB_SUPPORTED_COMMANDS:
        entrypoints.append("job")
    evidence_types: list[str] = []
    if semantics.get("writesEvidence"):
        evidence_types.append("evidence-receipt")
    if semantics.get("writesBusinessState"):
        evidence_types.append("confirmation-receipt")
    if semantics.get("mutationMode") == "runtime-receipt":
        evidence_types.append("runtime-receipt")
    return {
        "schema": CAPABILITY_SCHEMA,
        "capabilityId": f"cli.{command}",
        "command": command,
        "domain": semantics.get("domain", "misc"),
        "mutationMode": semantics.get("mutationMode", "read-only"),
        "entrypoints": entrypoints,
        "permissions": {
            "database": _database_access(semantics),
            "filesystem": filesystem,
            "network": "allowlisted-read-only" if command in NETWORK_READ_COMMANDS else "none",
            "process": "owned-worker" if command in OWNED_WORKER_COMMANDS else "none",
            "workspaceScopeRequired": True,
            "otherAibiRepositories": "forbidden",
        },
        "confirmation": {
            "required": bool(semantics.get("requiresYes")),
            "mode": "dry-run-confirm" if semantics.get("requiresYes") else "none",
        },
        "job": {
            "supported": command in JOB_SUPPORTED_COMMANDS,
            "ownedWorker": command in OWNED_WORKER_COMMANDS,
            "restartPolicy": "fail-explicitly" if command in OWNED_WORKER_COMMANDS else "not-applicable",
        },
        "evidence": {
            "writes": bool(semantics.get("writesEvidence")),
            "requiredTypes": evidence_types,
            "preserveReferences": True,
        },
        "timeoutClass": "long" if command in {"source-intelligence", "source-intelligence-job-run", "import-folder"} else "short",
    }


def capability_registry(parser: argparse.ArgumentParser) -> list[dict[str, Any]]:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return [
                build_capability_contract(name, command_semantics(name, action.choices[name]))
                for name in sorted(action.choices)
            ]
    return []


def validate_capability_invocation(
    capability: dict[str, Any],
    *,
    entrypoint: str,
    confirmed: bool,
    workspace_id: str,
) -> list[str]:
    blockers: list[str] = []
    if entrypoint not in capability.get("entrypoints", []):
        blockers.append("entrypoint-not-allowed")
    if capability.get("permissions", {}).get("workspaceScopeRequired") and not str(workspace_id or "").strip():
        blockers.append("workspace-required")
    if capability.get("confirmation", {}).get("required") and confirmed:
        # Confirmed execution is allowed. Planning without confirmation remains a valid dry-run.
        pass
    return blockers
