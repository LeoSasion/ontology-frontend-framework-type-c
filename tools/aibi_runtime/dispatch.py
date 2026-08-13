from __future__ import annotations

import sys
from typing import Sequence

from capability_contract_service import build_capability_contract, validate_capability_invocation
from bi_cli_contracts import command_semantics
from bi_cli_core import DB_PATH, ROOT
from workspace_mutation_lock_service import workspace_mutation_lock, workspace_read_lock
from workspace_recovery_service import configured_recovery_root, unfinished_recovery_fences
from .parser import build_parser
from .registry import build_command_registry
from .use_cases import lifecycle as runtime


CROSS_ENGINE_WRITE_COMMANDS = frozenset({
    "create-index",
    "import-commit",
    "import-folder",
    "import-job-recover",
    "import-job-process-exit",
    "sqlserver-adapter-snapshot",
    "sync-connector",
    "workspace-delete",
    "workspace-recovery-create",
    "workspace-recovery-delete",
    "workspace-recovery-reconcile",
    "workspace-recovery-restore",
})

# Import workers acquire the same boundary themselves only after their frozen
# plan has been revalidated. This keeps create/cancel control-plane writes
# available while a worker is doing read-only preparation.
INTERNALLY_LOCKED_COMMANDS = frozenset({"import-commit", "import-folder", "import-job-run", "sync-connector"})

# These commands expose only runtime/recovery metadata and are the bounded
# escape hatch used to diagnose or repair a persistent recovery fence.
RECOVERY_FENCE_ALLOWED_COMMANDS = frozenset({
    "capability-contracts",
    "list-commands",
    "status",
    "workspace-recovery-inspect",
    "workspace-recovery-list",
    "workspace-recovery-reconcile",
})


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
    command = str(getattr(args, "command", ""))
    capability = build_capability_contract(command, command_semantics(command))
    if validate_capability:
        blockers = validate_capability_invocation(
            capability,
            entrypoint=entrypoint,
            confirmed=bool(getattr(args, "yes", False)),
            workspace_id=str(getattr(args, "workspace", "") or "__active__"),
        )
        if blockers:
            raise PermissionError(f"Capability invocation blocked: {', '.join(blockers)}")
    writes_database = capability.get("permissions", {}).get("database") != "read-only"
    requires_exclusive_boundary = writes_database or command in CROSS_ENGINE_WRITE_COMMANDS
    lock_path = DB_PATH.parent / ".aibi-cross-engine-writer.lock"

    def assert_recovery_allows_command() -> None:
        if command not in RECOVERY_FENCE_ALLOWED_COMMANDS:
            fences = unfinished_recovery_fences(configured_recovery_root(ROOT))
            if fences:
                workspaces = sorted({item["workspaceId"] for item in fences})
                raise PermissionError(
                    "Workspace access is fenced by unfinished recovery for: " + ", ".join(workspaces)
                )

    if command in INTERNALLY_LOCKED_COMMANDS:
        # The service performs a short claim under the exclusive lock, then
        # reacquires it for the activation journal + SQLite/DuckDB commit.
        result = registry.dispatch(args, parser)
    elif requires_exclusive_boundary:
        with workspace_mutation_lock(lock_path):
            # Check only after ownership is established. Otherwise a restore
            # can create a journal between the check and the write (TOCTOU).
            assert_recovery_allows_command()
            result = registry.dispatch(args, parser)
    else:
        with workspace_read_lock(lock_path):
            # Shared readers cannot overlap recovery's exclusive writer and
            # remain fail-closed if a prior restore was interrupted.
            assert_recovery_allows_command()
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
