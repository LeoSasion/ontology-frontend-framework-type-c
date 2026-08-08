from __future__ import annotations

import sys
from typing import Sequence

from capability_contract_service import build_capability_contract, validate_capability_invocation
from bi_cli_contracts import command_semantics
from .parser import build_parser
from .registry import build_command_registry
from .use_cases import lifecycle as runtime


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def execute_command(
    argv: Sequence[str] | None = None,
    *,
    entrypoint: str = "cli",
    validate_capability: bool = False,
) -> dict:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    registry = build_command_registry()
    registry.validate_parser(parser)
    if validate_capability:
        command = str(getattr(args, "command", ""))
        capability = build_capability_contract(command, command_semantics(command))
        blockers = validate_capability_invocation(
            capability,
            entrypoint=entrypoint,
            confirmed=bool(getattr(args, "yes", False)),
            workspace_id=str(getattr(args, "workspace", "") or "__active__"),
        )
        if blockers:
            raise PermissionError(f"Capability invocation blocked: {', '.join(blockers)}")
    result = registry.dispatch(args, parser)
    if args.command in {"query", "ask", "semantic-query"}:
        result = runtime.attach_analysis_unit(
            result,
            open_db=runtime.open_db,
            active_workspace_id=runtime.active_workspace_id,
            now_iso=runtime.now_iso,
        )
    return runtime.enrich_cli_output(result, args, parser)


def main() -> int:
    registry_commands = build_command_registry().commands
    command = next((str(value) for value in sys.argv[1:] if str(value) in registry_commands), "")
    try:
        result = execute_command()
        command = str(result.get("command") or "")
        runtime.dump(result)
        return 0 if result.get("ok", False) else 1
    except Exception as exc:
        runtime.dump(runtime.error_output(command, exc))
        return 1
