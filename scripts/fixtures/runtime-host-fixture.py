from __future__ import annotations

import json
import os
import sys
import time


CATALOG = {
    "read": {"permissions": {"database": "read-only"}},
    "read-sleep": {"permissions": {"database": "read-only"}},
    "write": {"permissions": {"database": "read-write"}},
    "invalid": {"permissions": {"database": "read-write"}},
    "sleep": {"permissions": {"database": "read-write"}},
    "crash": {"permissions": {"database": "read-write"}},
}
reader_cache_open = False


def log_event(command: str, **detail: object) -> None:
    path = str(os.environ.get("AIBI_RUNTIME_FIXTURE_LOG") or "").strip()
    if not path:
        return
    payload = (json.dumps({
        "pid": os.getpid(),
        "role": str(os.environ.get("AIBI_RUNTIME_HOST_ROLE") or ""),
        "command": command,
        **detail,
    }) + "\n").encode("utf-8")
    flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY | getattr(os, "O_BINARY", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        # Emit one append syscall so concurrent fixture workers cannot overwrite
        # one another's evidence on Windows.
        os.write(descriptor, payload)
    finally:
        os.close(descriptor)


def send(request_id: str, result: dict[str, object]) -> None:
    print(json.dumps({"id": request_id, "transportOk": True, "result": result}), flush=True)


for raw_line in sys.stdin:
    request = json.loads(raw_line)
    request_id = str(request.get("id") or "")
    operation = str(request.get("op") or "")
    arguments = [str(item) for item in request.get("args") or []]
    if operation == "ping":
        send(request_id, {"ok": True})
        continue
    if operation == "catalog":
        send(request_id, CATALOG)
        continue
    if operation == "invalidate-readers":
        closed_connections = 1 if reader_cache_open else 0
        reader_cache_open = False
        log_event("invalidate-readers", phase="complete", closedConnections=closed_connections)
        send(request_id, {
            "ok": True,
            "schema": "aibi-runtime-reader-invalidation/v1",
            "closedConnections": closed_connections,
        })
        continue
    command = arguments[0] if arguments else ""
    tag = arguments[1] if len(arguments) > 1 else ""
    log_event(command, phase="start", tag=tag)
    if command in {"read", "read-sleep"} and os.environ.get("AIBI_RUNTIME_HOST_ROLE") == "reader":
        reader_cache_open = True
    if command == "workspace-recovery-reconcile" and os.environ.get("AIBI_RUNTIME_FIXTURE_RECONCILE_BLOCKED") == "1":
        send(request_id, {"ok": False, "needsAttention": [{"workspaceId": "fixture"}]})
        continue
    if command == "invalid":
        print("not-json", flush=True)
        continue
    if command == "sleep":
        time.sleep(0.3)
        send(request_id, {"ok": True, "command": command})
        continue
    if command == "read-sleep":
        time.sleep(0.15)
        log_event(command, phase="done", tag=tag)
        send(request_id, {"ok": True, "command": command, "tag": tag})
        continue
    if command == "crash":
        os._exit(7)
    send(request_id, {"ok": True, "command": command})
