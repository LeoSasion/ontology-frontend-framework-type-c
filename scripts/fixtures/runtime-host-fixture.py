from __future__ import annotations

import json
import os
import sys
import time


CATALOG = {
    "read": {"permissions": {"database": "read-only"}},
    "write": {"permissions": {"database": "read-write"}},
    "invalid": {"permissions": {"database": "read-write"}},
    "sleep": {"permissions": {"database": "read-write"}},
    "crash": {"permissions": {"database": "read-write"}},
}


def log_event(command: str) -> None:
    path = str(os.environ.get("AIBI_RUNTIME_FIXTURE_LOG") or "").strip()
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps({"pid": os.getpid(), "command": command}) + "\n")
        handle.flush()


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
    command = arguments[0] if arguments else ""
    log_event(command)
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
    if command == "crash":
        os._exit(7)
    send(request_id, {"ok": True, "command": command})
