from __future__ import annotations

import json
import sys
from typing import Any

from aibi_runtime.dispatch import execute_command
from aibi_runtime.parser import build_parser
from aibi_runtime.registry import build_command_registry
from aibi_runtime.use_cases import lifecycle as runtime
from capability_contract_service import capability_registry


MAX_REQUEST_BYTES = 512 * 1024
MAX_ARGUMENTS = 256
MAX_ARGUMENT_BYTES = 16 * 1024


def _reply(value: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _validated_args(value: Any) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_ARGUMENTS:
        raise ValueError("Runtime Host args must be a bounded array")
    args = [str(item) for item in value]
    if any(len(item.encode("utf-8")) > MAX_ARGUMENT_BYTES for item in args):
        raise ValueError("Runtime Host argument exceeds the size limit")
    return args


def main() -> int:
    parser = build_parser()
    registry = build_command_registry()
    registry.validate_parser(parser)
    catalog = {item["command"]: item for item in capability_registry(parser)}
    for raw_line in sys.stdin.buffer:
        if len(raw_line) > MAX_REQUEST_BYTES:
            _reply({"id": "", "transportOk": False, "error": "Runtime Host request exceeds the size limit"})
            continue
        request_id = ""
        command = ""
        try:
            envelope = json.loads(raw_line.decode("utf-8"))
            if not isinstance(envelope, dict):
                raise ValueError("Runtime Host envelope must be an object")
            request_id = str(envelope.get("id") or "")
            operation = str(envelope.get("op") or "run")
            if operation == "ping":
                _reply({"id": request_id, "transportOk": True, "result": {"ok": True, "schema": "aibi-runtime-host/v1"}})
                continue
            if operation == "catalog":
                _reply({"id": request_id, "transportOk": True, "result": catalog})
                continue
            args = _validated_args(envelope.get("args"))
            command = args[0] if args else ""
            result = execute_command(args, entrypoint="api", validate_capability=True)
            trace_id = str(envelope.get("traceId") or "")[:100]
            if trace_id and isinstance(result, dict):
                result["runtimeTrace"] = {
                    "schema": "aibi-runtime-trace/v1",
                    "traceId": trace_id,
                    "entrypoint": "api",
                    "command": command,
                }
            _reply({"id": request_id, "transportOk": True, "result": result})
        except BaseException as exc:
            try:
                error = runtime.error_output(command, exc)
            except BaseException:
                error = {"ok": False, "command": command, "error": str(exc)}
            _reply({"id": request_id, "transportOk": True, "result": error})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
