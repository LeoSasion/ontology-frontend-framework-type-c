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
    completed = subprocess.run([sys.executable, "tools/aibi_cli.py", "--json", *args], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
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

    check("schema-v14-bootstrap", status_code == 0 and schema_version == 14, {"status": status_code, "schemaVersion": schema_version})
    check("turn-run-contract", run_code == 0 and run.get("schema") == "aibi-agent-turn-run/v1" and turn_key.startswith("turn-"), run)
    check("turn-has-durable-session", str((run.get("session") or {}).get("sessionKey") or "").startswith("session-") and turn.get("sessionKey") == (run.get("session") or {}).get("sessionKey"), run)
    check("evidence-plan-contract", plan.get("schema") == "aibi-agent-evidence-plan/v1" and len(plan.get("fingerprint") or "") == 64, plan)
    check("registered-capabilities-only", all(step.get("capabilityId") in plan.get("registeredCapabilities", []) for step in plan.get("steps") or []), plan)
    sequences = [event.get("sequence") for event in events]
    check("strict-event-sequence", sequences == sorted(set(sequences)), events)
    check("event-lifecycle", bool(events) and events[0].get("eventType") == "accepted" and events[-1].get("eventType") in {"turn-completed", "turn-blocked"}, events)
    check("completion-verifier", run.get("validation", {}).get("safeToPresent") is True, run.get("validation"))
    check("fixed-policy-hooks-pass", run.get("validation", {}).get("policyHooks", {}).get("status") == "passed", run.get("validation"))
    check("analytical-skill-bound", bool(plan.get("skillRefs")) and len(plan.get("skillRefs", [{}])[0].get("fingerprint") or "") == 64, plan)
    check("turn-reload", list_code == 0 and listed.get("turn", {}).get("turnKey") == turn_key and len(listed.get("events") or []) == len(events), listed)
    check("terminal-cancel-idempotent", cancel_code == 0 and canceled.get("changed") is False and canceled.get("turn", {}).get("turnKey") == turn_key, canceled)

    import_code, imported = run_cli(
        env,
        "import-commit",
        str(ROOT / "validation-inputs" / "orders.csv"),
        "--table",
        "orders",
        "--name",
        "Orders",
        "--mode",
        "create",
        "--yes",
    )
    grounded_code, grounded = run_cli(env, "agent-turn-run", "--read-only", "按 channel 汇总 net_sales")
    grounded_answer = grounded.get("answer") or {}
    grounded_unit = grounded_answer.get("analysisUnit") or {}
    grounded_plan = grounded.get("evidencePlan") or {}
    verify_code, unit_verification = run_cli(env, "analysis-unit-verify", "--unit", str(grounded_unit.get("unitKey") or "missing"))
    check("grounded-fixture-imported", import_code == 0 and imported.get("ok") is True, imported)
    check(
        "agent-turn-enriches-analysis-unit-before-planning",
        grounded_code == 0
        and grounded_unit.get("status") == "ready"
        and grounded_unit.get("queryReceiptKey") == (grounded_answer.get("queryPlanReceipt") or {}).get("receiptKey")
        and any(node.get("operator") == "unit" for node in (grounded_plan.get("workflowGraph") or {}).get("nodes") or []),
        grounded,
    )
    check(
        "agent-turn-analysis-unit-recalculates",
        verify_code == 0
        and unit_verification.get("unitKey") == grounded_unit.get("unitKey")
        and unit_verification.get("rowsFingerprintMatches") is True
        and unit_verification.get("calculationMatches") is True,
        unit_verification,
    )

    root_branch_code, root_branch = run_cli(env, "agent-turn-run", "请用 net_sales 按 channel 生成柱状图")
    root_branch_answer = root_branch.get("answer") or {}
    root_analysis_run = root_branch_answer.get("analysisRun") or {}
    root_analysis_run_key = str(root_analysis_run.get("run_key") or "")
    root_action_key = str((root_branch_answer.get("actionDraft") or {}).get("actionKey") or "")
    root_session_key = str((root_branch.get("session") or {}).get("sessionKey") or "")
    root_turn_key = str((root_branch.get("turn") or {}).get("turnKey") or "")
    confirm_root_code, confirm_root = run_cli(env, "confirm-action", root_action_key, "--yes")
    branch_code, branch = run_cli(
        env,
        "agent-turn-run",
        "--session",
        root_session_key,
        "--parent-run",
        root_analysis_run_key,
        "--branch-label",
        "按分类比较",
        "请用 net_sales 按 category 生成柱状图",
    )
    branch_answer = branch.get("answer") or {}
    branch_analysis_run = branch_answer.get("analysisRun") or {}
    check(
        "analysis-run-root-confirmed-before-branch",
        root_branch_code == 0
        and bool(root_analysis_run_key)
        and bool(root_action_key)
        and confirm_root_code == 0
        and confirm_root.get("confirmed") is True,
        {"root": root_branch, "confirmation": confirm_root},
    )
    check(
        "agent-turn-preserves-analysis-run-branch-contract",
        branch_code == 0
        and branch_analysis_run.get("parent_run_key") == root_analysis_run_key
        and branch_analysis_run.get("branch_label") == "按分类比较"
        and (branch.get("turn") or {}).get("parentTurnKey") == root_turn_key,
        branch,
    )

result = {"ok": all(item["ok"] for item in checks), "schema": "aibi-agent-turns-verify/v1", "checks": checks, "failedChecks": [item["label"] for item in checks if not item["ok"]]}
print(json.dumps(result, ensure_ascii=False, indent=2))
raise SystemExit(0 if result["ok"] else 1)
