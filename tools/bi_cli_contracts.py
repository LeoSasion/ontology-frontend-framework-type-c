from __future__ import annotations

import argparse
from argparse import Action
from typing import Any


CONTRACT_SCHEMA_VERSION = "aibi-bi-cli-contract/v1"


COMMAND_DOMAINS: dict[str, str] = {
    "status": "system",
    "workspace-manifest": "workspace",
    "runtime-catalog": "workspace",
    "business-field-profiles": "semantic",
    "quality-doctor": "system",
    "context-pack": "context",
    "context-term": "context",
    "context-rule": "context",
    "knowledge-source-adapters": "context",
    "knowledge-sources": "context",
    "semantic-patch-propose": "semantic",
    "semantic-patch-proposals": "semantic",
    "semantic-patch-review": "semantic",
    "query-receipts": "evidence",
    "export-evidence": "evidence",
    "export-analysis": "evidence",
    "confirmed-queries": "context",
    "confirmed-plans": "context",
    "recall-receipts": "evidence",
    "confirm-query": "context",
    "analysis-runs": "evidence",
    "exploration-threads": "analysis",
    "exploration-thread-create": "analysis",
    "exploration-anchor-add": "analysis",
    "exploration-board-set": "analysis",
    "research-runs": "analysis",
    "research-run-create": "analysis",
    "research-run-revise": "analysis",
    "research-run-observe": "analysis",
    "research-run-finalize": "analysis",
    "analysis-unit-build": "analysis",
    "analysis-units": "analysis",
    "analysis-snapshots": "analysis",
    "analysis-snapshot-create": "analysis",
    "analysis-snapshot-refresh": "analysis",
    "analysis-snapshot-replace": "analysis",
    "analysis-snapshot-delete": "analysis",
    "metric-monitors": "analysis",
    "metric-monitor-create": "analysis",
    "metric-monitor-replace": "analysis",
    "metric-monitor-delete": "analysis",
    "metric-monitor-run": "analysis",
    "analysis-unit-verify": "analysis",
    "forecast-readiness": "analysis",
    "chart-adapt": "analysis",
    "decision-frameworks": "analysis",
    "decision-framework-create": "analysis",
    "decision-framework-save": "analysis",
    "decision-framework-publish": "analysis",
    "decision-framework-export": "analysis",
    "reviewed-publication-plan": "analysis",
    "reviewed-publication-publish": "analysis",
    "reviewed-publications": "analysis",
    "reviewed-publication-deprecate": "analysis",
    "reviewed-publication-export": "analysis",
    "evidence-retrieval-status": "analysis",
    "evidence-retrieval-receipts": "analysis",
    "evidence-retrieval-evaluate": "analysis",
    "jobs": "job",
    "job-cancel": "job",
    "job-recover": "job",
    "source-intelligence-job-create": "job",
    "source-intelligence-job-run": "job",
    "job-process-exit": "job",
    "import-job-create": "job",
    "import-job-run": "job",
    "import-job-resume": "job",
    "import-job-recover": "job",
    "import-job-process-exit": "job",
    "cli-contract": "system",
    "list-commands": "system",
    "capability-contracts": "system",
    "workflow-plan": "workflow",
    "context-budget": "context",
    "restricted-workflow-operators": "workflow",
    "restricted-workflow-validate": "workflow",
    "agent-workflow-graph": "workflow",
    "agent-turn-run": "agent",
    "agent-turns": "agent",
    "agent-turn-cancel": "agent",
    "agent-session-create": "agent",
    "agent-sessions": "agent",
    "agent-session-resume": "agent",
    "agent-session-fork": "agent",
    "agent-context-compact": "agent",
    "agent-runtime-profiles": "agent",
    "agent-runtime-profile-set": "agent",
    "agent-provider-evaluations": "agent",
    "agent-provider-evaluation-record": "agent",
    "business-expression-cases": "agent",
    "plan-quality-evaluate": "agent",
    "plan-quality-scorecards": "agent",
    "workspace-create": "workspace",
    "workspace-select": "workspace",
    "workspace-rename": "workspace",
    "workspace-delete": "workspace",
    "workspace-recovery-list": "workspace-recovery",
    "workspace-recovery-reconcile": "workspace-recovery",
    "workspace-recovery-inspect": "workspace-recovery",
    "workspace-recovery-create": "workspace-recovery",
    "workspace-recovery-restore": "workspace-recovery",
    "workspace-recovery-delete": "workspace-recovery",
    "domain-packs": "domain-pack",
    "domain-pack-set": "domain-pack",
    "domain-pack-lint": "domain-pack",
    "domain-pack-install": "domain-pack",
    "domain-pack-uninstall": "domain-pack",
    "analytical-skills": "analytical-skill",
    "analytical-skill-lint": "analytical-skill",
    "analytical-skill-install": "analytical-skill",
    "analytical-skill-uninstall": "analytical-skill",
    "analytical-skill-set": "analytical-skill",
    "analytical-skill-match": "analytical-skill",
    "source-run": "source",
    "list-tables": "source",
    "inspect-table": "source",
    "rename-source": "source",
    "delete-source": "source",
    "source-intelligence": "evidence",
    "source-intelligence-runs": "evidence",
    "source-dashboard-draft": "evidence",
    "workbench": "workbench",
    "list-navigation": "navigation",
    "navigation-op": "navigation",
    "dashboard-widget-catalog": "dashboard",
    "cli-capabilities": "system",
    "recommend-widgets": "dashboard",
    "add-recommended-widgets": "dashboard",
    "save-dashboard-modules": "dashboard",
    "business-dashboard": "dashboard",
    "erp-unit-library": "dashboard",
    "add-widget": "dashboard",
    "add-relationship-widget": "dashboard",
    "set-widget": "dashboard",
    "copy-widget": "dashboard",
    "remove-widget": "dashboard",
    "set-import-policy": "import",
    "preview-import": "import",
    "import-commit": "import",
    "preview-import-folder": "import",
    "import-folder": "import",
    "list-import-jobs": "import",
    "remove-import-job": "import",
    "list-connectors": "connector",
    "save-connector": "connector",
    "sync-connector": "connector",
    "sqlserver-adapter-probe": "connector",
    "sqlserver-adapter-activate": "connector",
    "sqlserver-adapter-activation-finalize": "connector",
    "sqlserver-adapter-activation-status": "connector",
    "sqlserver-adapter-test": "connector",
    "sqlserver-adapter-discover": "connector",
    "sqlserver-adapter-preview": "connector",
    "sqlserver-adapter-plan": "connector",
    "sqlserver-adapter-snapshot": "connector",
    "remove-connector": "connector",
    "list-connector-adapters": "connector",
    "discover-connector": "connector",
    "preview-connector": "connector",
    "plan-connector-sync": "connector",
    "federation-proof": "connector",
    "infer-semantics": "semantic",
    "list-semantics": "semantic",
    "set-semantic": "semantic",
    "infer-metrics": "metric",
    "list-metrics": "metric",
    "add-metric": "metric",
    "list-formulas": "formula",
    "save-formula": "formula",
    "delete-formula": "formula",
    "query-metric": "query",
    "preferences": "settings",
    "theme-palettes": "settings",
    "validate-config": "config",
    "export-config": "config",
    "apply-config": "config",
    "query": "query",
    "query-table": "query",
    "list-views": "view",
    "save-view": "view",
    "copy-view": "view",
    "delete-view": "view",
    "dashboards": "dashboard",
    "list-filters": "dashboard",
    "add-filter": "dashboard",
    "set-filter": "dashboard",
    "remove-filter": "dashboard",
    "remove-stale-filters": "dashboard",
    "clear-filters": "dashboard",
    "recommend-indexes": "performance",
    "create-index": "performance",
    "dashboard-op": "dashboard",
    "field-update": "semantic",
    "relationship-preview": "relationship",
    "relationship-save": "relationship",
    "recommend-relationships": "relationship",
    "list-relationships": "relationship",
    "remove-relationship": "relationship",
    "query-relationship": "relationship",
    "semantic-query": "query",
    "formula-preview": "formula",
    "ask": "agent",
    "confirm-action": "agent",
    "action-drafts": "agent",
}

ACTION_DRAFT_COMMANDS = {"ask", "source-dashboard-draft"}
EVIDENCE_WRITING_COMMANDS = {
    "source-intelligence",
    "source-intelligence-job-run",
    "import-job-create",
    "import-job-run",
    "import-job-resume",
    "import-job-recover",
    "import-job-process-exit",
    "preview-import",
    "preview-import-folder",
    "business-dashboard",
    "export-evidence",
    "analysis-unit-build",
    "query",
    "semantic-query",
    "metric-monitor-run",
    "decision-framework-publish",
    "reviewed-publication-publish",
    "reviewed-publication-deprecate",
    "evidence-retrieval-evaluate",
    "sqlserver-adapter-snapshot",
    "sqlserver-adapter-activate",
    "sqlserver-adapter-activation-finalize",
}
IMMEDIATE_RUNTIME_WRITES = {
    "source-intelligence",
    "source-intelligence-job-create",
    "source-intelligence-job-run",
    "job-process-exit",
    "export-config",
    "cli-contract",
    "export-analysis",
    "agent-turn-run",
    "agent-turn-cancel",
    "agent-session-create",
    "agent-session-fork",
    "agent-context-compact",
    "agent-runtime-profile-set",
    "agent-provider-evaluation-record",
    "plan-quality-evaluate",
    "metric-monitor-run",
    "decision-framework-create",
    "decision-framework-save",
    "workspace-recovery-reconcile",
    "sqlserver-adapter-discover",
    "sqlserver-adapter-plan",
}
CONFIRMATION_COMMANDS = {"confirm-action"}
STATIC_DRY_RUN_CONFIRM_COMMANDS = {
    "exploration-thread-create",
    "exploration-anchor-add",
    "exploration-board-set",
    "research-run-create",
    "research-run-revise",
    "research-run-observe",
    "research-run-finalize",
    "analysis-snapshot-create",
    "analysis-snapshot-refresh",
    "analysis-snapshot-replace",
    "analysis-snapshot-delete",
    "metric-monitor-create",
    "metric-monitor-replace",
    "metric-monitor-delete",
    "decision-framework-publish",
    "reviewed-publication-publish",
    "reviewed-publication-deprecate",
    "sqlserver-adapter-snapshot",
    "sqlserver-adapter-activate",
    "sqlserver-adapter-activation-finalize",
    "workspace-recovery-create",
    "workspace-recovery-restore",
    "workspace-recovery-delete",
    "workspace-delete",
    "sync-connector",
}


def _subparser_action(parser: argparse.ArgumentParser) -> argparse._SubParsersAction | None:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _action_default(action: Action) -> Any:
    default = action.default
    if default is argparse.SUPPRESS:
        return None
    if isinstance(default, (str, int, float, bool)) or default is None:
        return default
    if isinstance(default, list):
        return list(default)
    return str(default)


def _action_type_name(action: Action) -> str | None:
    if action.type is None:
        return None
    return getattr(action.type, "__name__", str(action.type))


def _argument_contract(action: Action) -> dict[str, Any] | None:
    if action.dest == "help":
        return None
    flags = list(action.option_strings)
    return {
        "name": action.dest,
        "kind": "option" if flags else "positional",
        "flags": flags,
        "required": bool(getattr(action, "required", False)) if flags else True,
        "nargs": action.nargs,
        "choices": list(action.choices) if action.choices is not None else None,
        "default": _action_default(action),
        "type": _action_type_name(action),
        "action": action.__class__.__name__,
        "help": getattr(action, "help", None),
    }


def command_semantics(command: str, parser: argparse.ArgumentParser | None = None) -> dict[str, Any]:
    arguments = []
    if parser is not None:
        arguments = [item for item in (_argument_contract(action) for action in parser._actions) if item]
    has_yes = any("--yes" in item["flags"] for item in arguments) or command in STATIC_DRY_RUN_CONFIRM_COMMANDS
    has_output = any("--output" in item["flags"] for item in arguments)
    creates_action_draft = command in ACTION_DRAFT_COMMANDS
    writes_evidence = command in EVIDENCE_WRITING_COMMANDS
    if command in CONFIRMATION_COMMANDS:
        mutation_mode = "action-confirmation"
    elif has_yes:
        mutation_mode = "dry-run-confirm"
    elif creates_action_draft:
        mutation_mode = "action-draft"
    elif writes_evidence:
        mutation_mode = "evidence-receipt"
    elif command in IMMEDIATE_RUNTIME_WRITES and has_output:
        mutation_mode = "artifact-export"
    elif command in IMMEDIATE_RUNTIME_WRITES:
        mutation_mode = "runtime-receipt"
    else:
        mutation_mode = "read-only"
    return {
        "domain": COMMAND_DOMAINS.get(command, "misc"),
        "mutationMode": mutation_mode,
        "readOnlyByDefault": mutation_mode == "read-only",
        "dryRunByDefault": mutation_mode in {"dry-run-confirm", "action-draft"},
        "requiresYes": has_yes,
        "createsActionDraft": creates_action_draft,
        "writesEvidence": writes_evidence,
        "writesBusinessState": has_yes and command not in {"confirm-action"},
        "writesArtifacts": has_output or writes_evidence or command in IMMEDIATE_RUNTIME_WRITES,
    }


def build_cli_contract(parser: argparse.ArgumentParser) -> dict[str, Any]:
    subparser_action = _subparser_action(parser)
    commands: list[dict[str, Any]] = []
    if subparser_action is not None:
        for name in sorted(subparser_action.choices):
            command_parser = subparser_action.choices[name]
            arguments = [item for item in (_argument_contract(action) for action in command_parser._actions) if item]
            semantics = command_semantics(name, command_parser)
            commands.append(
                {
                    "name": name,
                    "description": command_parser.description or getattr(command_parser, "help", "") or "",
                    "usage": command_parser.format_usage().strip(),
                    "arguments": arguments,
                    **semantics,
                }
            )
    domains: dict[str, int] = {}
    mutation_modes: dict[str, int] = {}
    for command in commands:
        domains[str(command["domain"])] = domains.get(str(command["domain"]), 0) + 1
        mutation_modes[str(command["mutationMode"])] = mutation_modes.get(str(command["mutationMode"]), 0) + 1
    return {
        "ok": True,
        "schema": CONTRACT_SCHEMA_VERSION,
        "generatedBy": "tools/bi_cli_contracts.py",
        "entrypoint": "python tools/aibi_cli.py --json <command>",
        "commandCount": len(commands),
        "domains": domains,
        "mutationModes": mutation_modes,
        "commands": commands,
    }


def command_contract_by_name(contract: dict[str, Any], command_name: str) -> dict[str, Any] | None:
    commands = contract.get("commands") if isinstance(contract.get("commands"), list) else []
    return next((command for command in commands if command.get("name") == command_name), None)


def filter_commands(
    contract: dict[str, Any],
    *,
    domain: str | None = None,
    mutation_mode: str | None = None,
    writes: bool | None = None,
) -> list[dict[str, Any]]:
    commands = contract.get("commands") if isinstance(contract.get("commands"), list) else []
    filtered: list[dict[str, Any]] = []
    for command in commands:
        if domain and command.get("domain") != domain:
            continue
        if mutation_mode and command.get("mutationMode") != mutation_mode:
            continue
        writes_anything = bool(command.get("writesBusinessState") or command.get("writesEvidence") or command.get("writesArtifacts"))
        if writes is not None and writes_anything != writes:
            continue
        filtered.append(command)
    return filtered


def contract_to_markdown(contract: dict[str, Any]) -> str:
    commands = contract.get("commands") if isinstance(contract.get("commands"), list) else []
    lines = [
        "# BI CLI Contract",
        "",
        f"Schema: `{contract.get('schema')}`",
        f"Entrypoint: `{contract.get('entrypoint')}`",
        f"Command count: `{contract.get('commandCount')}`",
        "",
        "This file is generated from the live argparse surface. Keep `tools/aibi_cli.py` as the source of truth and regenerate this document after changing CLI commands.",
        "",
        "## Summary",
        "",
        "| Domain | Commands |",
        "|---|---:|",
    ]
    for domain, count in sorted((contract.get("domains") or {}).items()):
        lines.append(f"| `{domain}` | {count} |")
    lines.extend(
        [
            "",
            "| Mutation mode | Commands |",
            "|---|---:|",
        ]
    )
    for mode, count in sorted((contract.get("mutationModes") or {}).items()):
        lines.append(f"| `{mode}` | {count} |")
    lines.extend(
        [
            "",
            "## Commands",
            "",
            "| Command | Domain | Mutation | Confirmation | Evidence | Key arguments |",
            "|---|---|---|---|---|---|",
        ]
    )
    for command in commands:
        args = command.get("arguments") if isinstance(command.get("arguments"), list) else []
        key_args = []
        for arg in args:
            flags = arg.get("flags") if isinstance(arg.get("flags"), list) else []
            if flags:
                key_args.append("/".join(flags))
            else:
                key_args.append(str(arg.get("name")))
        if len(key_args) > 8:
            key_args = key_args[:8] + ["..."]
        lines.append(
            "| `{name}` | `{domain}` | `{mutation}` | `{confirmation}` | `{evidence}` | {args} |".format(
                name=command.get("name"),
                domain=command.get("domain"),
                mutation=command.get("mutationMode"),
                confirmation="yes" if command.get("requiresYes") or command.get("createsActionDraft") else "no",
                evidence="yes" if command.get("writesEvidence") else "no",
                args=", ".join(f"`{item}`" for item in key_args) or "-",
            )
        )
    return "\n".join(lines) + "\n"
