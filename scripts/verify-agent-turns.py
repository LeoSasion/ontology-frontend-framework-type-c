from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_cli(env: dict[str, str], *args: str) -> tuple[int, dict]:
    completed = subprocess.run([sys.executable, "tools/bi_cli.py", "--json", *args], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {"stdout": completed.stdout, "stderr": completed.stderr}
    return completed.returncode, payload


checks: list[dict[str, object]] = []


def check(label: str, ok: bool, detail: object = "") -> None:
    checks.append({"label": label, "ok": ok, "detail": "" if ok else detail})


with tempfile.TemporaryDirectory(prefix="aibi-agent-turn-") as temp:
    env = dict(os.environ)
    env["AIBI_HYBRID_DB_PATH"] = str(Path(temp) / "metadata.sqlite")
    env["AIBI_HYBRID_DUCKDB_PATH"] = str(Path(temp) / "analytics.duckdb")
    env["PYTHONIOENCODING"] = "utf-8"
    status_code, status = run_cli(env, "status")
    schema_connection = sqlite3.connect(env["AIBI_HYBRID_DB_PATH"])
    try:
        schema_version = int(schema_connection.execute("PRAGMA user_version").fetchone()[0])
    finally:
        schema_connection.close()
    run_code, run = run_cli(env, "agent-turn-run", "--read-only", "查看本月趋势")
    turn = run.get("turn") or {}
    plan = run.get("evidencePlan") or {}
    events = run.get("events") or []
    turn_key = str(turn.get("turnKey") or "")
    list_code, listed = run_cli(env, "agent-turns", "--turn", turn_key, "--after-sequence", "0")
    cancel_code, canceled = run_cli(env, "agent-turn-cancel", turn_key)

    check("schema-v4-bootstrap", status_code == 0 and schema_version == 4, {"status": status_code, "schemaVersion": schema_version})
    check("turn-run-contract", run_code == 0 and run.get("schema") == "aibi-agent-turn-run/v1" and turn_key.startswith("turn-"), run)
    check("evidence-plan-contract", plan.get("schema") == "aibi-agent-evidence-plan/v1" and len(plan.get("fingerprint") or "") == 64, plan)
    check("registered-capabilities-only", all(step.get("capabilityId") in plan.get("registeredCapabilities", []) for step in plan.get("steps") or []), plan)
    sequences = [event.get("sequence") for event in events]
    check("strict-event-sequence", sequences == sorted(set(sequences)), events)
    check("event-lifecycle", bool(events) and events[0].get("eventType") == "accepted" and events[-1].get("eventType") in {"turn-completed", "turn-blocked"}, events)
    check("completion-verifier", run.get("validation", {}).get("safeToPresent") is True, run.get("validation"))
    check("turn-reload", list_code == 0 and listed.get("turn", {}).get("turnKey") == turn_key and len(listed.get("events") or []) == len(events), listed)
    check("terminal-cancel-idempotent", cancel_code == 0 and canceled.get("changed") is False and canceled.get("turn", {}).get("turnKey") == turn_key, canceled)

result = {"ok": all(item["ok"] for item in checks), "schema": "aibi-agent-turns-verify/v1", "checks": checks, "failedChecks": [item["label"] for item in checks if not item["ok"]]}
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result["ok"] else 1)
