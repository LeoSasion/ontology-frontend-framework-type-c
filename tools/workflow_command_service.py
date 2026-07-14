from __future__ import annotations

import argparse
import json
from typing import Any

from bi_cli_contracts import command_semantics
from capability_contract_service import (
    build_capability_contract,
    capability_registry,
    validate_capability_invocation,
)
from context_budget_service import compact_context_segments
from workflow_stage_service import build_workflow_stage


def _command_parser(parser: argparse.ArgumentParser, command: str) -> argparse.ArgumentParser | None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices.get(command)
    return None


def capability_contracts_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> dict[str, Any]:
    registry = capability_registry(parser)
    command = str(getattr(args, "command_name", "") or "").strip()
    domain = str(getattr(args, "domain", "") or "").strip()
    if command:
        registry = [item for item in registry if item["command"] == command]
        if not registry:
            raise ValueError(f"Unknown capability command: {command}")
    if domain:
        registry = [item for item in registry if item["domain"] == domain]
    return {
        "ok": True,
        "schema": "aibi-capability-registry/v1",
        "capabilities": registry,
        "count": len(registry),
        "guardrails": {
            "unknownCapability": "blocked",
            "otherAibiRepositories": "forbidden",
            "unconfirmedWrite": "dry-run-or-action-draft",
            "arbitrarySql": "forbidden",
        },
    }


def workflow_plan_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> dict[str, Any]:
    target = str(args.target_command or "").strip()
    target_parser = _command_parser(parser, target)
    if target_parser is None:
        raise ValueError(f"Unknown workflow capability: {target}")
    try:
        input_value = json.loads(str(args.input_json or "{}"))
    except json.JSONDecodeError as exc:
        raise ValueError("input-json must be a JSON object") from exc
    if not isinstance(input_value, dict):
        raise ValueError("input-json must be a JSON object")
    semantics = command_semantics(target, target_parser)
    capability = build_capability_contract(target, semantics)
    blockers = validate_capability_invocation(
        capability,
        entrypoint=str(args.entrypoint or "cli"),
        confirmed=bool(args.confirmed),
        workspace_id=str(args.workspace or ""),
    )
    result = {
        "ok": not blockers,
        "requiresConfirmation": bool(capability["confirmation"]["required"] and not args.confirmed),
        "evidence": [{"type": "capability-contract", "capabilityId": capability["capabilityId"]}],
        "error": ", ".join(blockers) if blockers else None,
    }
    stage = build_workflow_stage(
        command=target,
        args=input_value,
        result=result,
        capability=capability,
        status="blocked" if blockers else "waiting-confirmation" if result["requiresConfirmation"] else "planned",
    )
    stage["entrypoint"] = str(args.entrypoint or "cli")
    stage["workspaceId"] = str(args.workspace or "")
    stage["blockers"] = blockers
    return {
        "ok": not blockers,
        "schema": "aibi-workflow-plan/v1",
        "targetCapability": capability,
        "stage": stage,
        "blockers": blockers,
    }


def context_budget_command(args: argparse.Namespace) -> dict[str, Any]:
    try:
        segments = json.loads(str(args.segments_json or "[]"))
    except json.JSONDecodeError as exc:
        raise ValueError("segments-json must be a JSON array") from exc
    if not isinstance(segments, list) or not all(isinstance(item, dict) for item in segments):
        raise ValueError("segments-json must be a JSON array of objects")
    budget = compact_context_segments(segments, int(args.max_chars))
    return {"ok": budget["status"] != "blocked", "contextBudget": budget}
