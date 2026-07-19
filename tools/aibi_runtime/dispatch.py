from __future__ import annotations

import sys

from .parser import build_parser
from .registry import build_command_registry
from .use_cases import lifecycle as runtime


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        registry = build_command_registry()
        registry.validate_parser(parser)
        result = registry.dispatch(args, parser)
        if args.command in {"query", "ask", "semantic-query"}:
            result = runtime.attach_analysis_unit(
                result,
                open_db=runtime.open_db,
                active_workspace_id=runtime.active_workspace_id,
                now_iso=runtime.now_iso,
            )
        result = runtime.enrich_cli_output(result, args, parser)
        runtime.dump(result)
        return 0 if result.get("ok", False) else 1
    except Exception as exc:
        runtime.dump(runtime.error_output(str(getattr(args, "command", "")), exc))
        return 1
