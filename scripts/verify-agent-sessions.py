from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def run_cli(env: dict[str, str], *args: str) -> tuple[int, dict]:
    completed = subprocess.run([sys.executable, "tools/bi_cli.py", "--json", *args], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=90)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {"stdout": completed.stdout, "stderr": completed.stderr}
    return completed.returncode, payload


checks: list[dict[str, object]] = []


def check(label: str, ok: bool, detail: object = "") -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": "" if ok else detail})


with tempfile.TemporaryDirectory(prefix="aibi-agent-session-") as temp:
    root = Path(temp)
    env = dict(os.environ)
    env["AIBI_HYBRID_DB_PATH"] = str(root / "metadata.sqlite")
    env["AIBI_HYBRID_DUCKDB_PATH"] = str(root / "analytics.duckdb")
    env["PYTHONIOENCODING"] = "utf-8"
    status_code, _ = run_cli(env, "status")
    create_code, created = run_cli(env, "agent-session-create", "--title", "可恢复分析")
    session_key = str((created.get("session") or {}).get("sessionKey") or "")
    first_code, first = run_cli(env, "agent-turn-run", "--workspace", "default", "--session", session_key, "--read-only", "查看本月趋势")
    first_turn = str((first.get("turn") or {}).get("turnKey") or "")
    second_code, second = run_cli(env, "agent-turn-run", "--workspace", "default", "--session", session_key, "--read-only", "再比较上月")
    second_turn = str((second.get("turn") or {}).get("turnKey") or "")
    inspect_code, inspected = run_cli(env, "agent-sessions", "--workspace", "default", "--session", session_key)
    refs_before = (inspected.get("context") or {}).get("preservedRefs") or []

    compactions: list[dict] = []
    compaction_codes: list[int] = []
    for level in range(1, 5):
        code, payload = run_cli(env, "agent-context-compact", "--workspace", "default", "--session", session_key, "--level", str(level))
        compaction_codes.append(code)
        compactions.append(payload)
    resume_code, resumed = run_cli(env, "agent-session-resume", "--workspace", "default", session_key)
    parent_before = resumed.get("session") or {}
    fork_code, forked = run_cli(env, "agent-session-fork", "--workspace", "default", session_key, "--from-turn", first_turn, "--title", "趋势分支")
    fork_session = str((forked.get("forkedSession") or {}).get("sessionKey") or "")
    fork_turn_code, fork_turn = run_cli(env, "agent-turn-run", "--workspace", "default", "--session", fork_session, "--read-only", "只看异常")
    parent_after_code, parent_after_payload = run_cli(env, "agent-session-resume", "--workspace", "default", session_key)
    parent_after = parent_after_payload.get("session") or {}

    workspace_code, workspace = run_cli(env, "workspace-create", "--name", "Session Isolation", "--yes")
    isolated_workspace = str((workspace.get("created") or workspace.get("workspace") or {}).get("id") or "")
    cross_code, cross = run_cli(env, "agent-sessions", "--workspace", isolated_workspace, "--session", session_key)

    receipt_ref = next((item for item in refs_before if item.get("kind") == "query-receipt"), {})
    receipt_key = str(receipt_ref.get("key") or "")
    connection = sqlite3.connect(env["AIBI_HYBRID_DB_PATH"])
    try:
        schema_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        turn_count_before = int(connection.execute("SELECT COUNT(*) FROM agent_turns WHERE workspace_id = 'default' AND session_key = ?", (session_key,)).fetchone()[0])
        snapshot_count = int(connection.execute("SELECT COUNT(*) FROM agent_context_snapshots WHERE workspace_id = 'default' AND session_key = ?", (session_key,)).fetchone()[0])
        if receipt_key:
            connection.execute("DELETE FROM query_plan_receipts WHERE workspace_id = 'default' AND receipt_key = ?", (receipt_key,))
            connection.commit()
    finally:
        connection.close()

    stale_resume_code, stale_resume = run_cli(env, "agent-session-resume", "--workspace", "default", session_key)
    blocked_continue_code, blocked_continue = run_cli(env, "agent-turn-run", "--workspace", "default", "--session", session_key, "--read-only", "继续分析")
    reviewed_continue_code, reviewed_continue = run_cli(env, "agent-turn-run", "--workspace", "default", "--session", session_key, "--review-stale-context", "--read-only", "已核对失效对象后继续")

    connection = sqlite3.connect(env["AIBI_HYBRID_DB_PATH"])
    try:
        turn_count_after = int(connection.execute("SELECT COUNT(*) FROM agent_turns WHERE workspace_id = 'default' AND session_key = ?", (session_key,)).fetchone()[0])
    finally:
        connection.close()

    snapshots = [(item.get("snapshot") or {}) for item in compactions]
    ref_counts = [len(item.get("preservedRefs") or []) for item in snapshots]
    check("schema-v12-bootstrap", status_code == 0 and schema_version == 12, schema_version)
    check("session-create-contract", create_code == 0 and session_key.startswith("session-"), created)
    check("same-session-turn-chain", first_code == 0 and second_code == 0 and (first.get("turn") or {}).get("sessionKey") == session_key and (second.get("turn") or {}).get("parentTurnKey") == first_turn, second)
    check("restart-safe-session-inspection", inspect_code == 0 and (inspected.get("context") or {}).get("turnCount") == 2 and len((inspected.get("context") or {}).get("fingerprint") or "") == 64, inspected)
    check("four-level-compaction-contract", all(code == 0 for code in compaction_codes) and [item.get("compactionLevel") for item in snapshots] == [1, 2, 3, 4], compactions)
    check("compaction-preserves-evidence-refs", len(set(ref_counts)) == 1 and ref_counts[0] == len(refs_before) and all(item.get("turnsDeleted") == 0 and item.get("evidenceRefsPreserved") is True and item.get("businessFactsPromoted") is False for item in compactions), compactions)
    check("latest-snapshot-is-current", resume_code == 0 and resumed.get("canResume") is True and (resumed.get("context") or {}).get("snapshotCurrent") is True and snapshot_count == 4, resumed)
    check("fork-does-not-mutate-parent", fork_code == 0 and fork_session.startswith("session-") and forked.get("parentUnchanged") is True and parent_after_code == 0 and parent_before.get("currentTurnKey") == parent_after.get("currentTurnKey") == second_turn, {"fork": forked, "before": parent_before, "after": parent_after})
    check("fork-first-turn-binds-parent-turn", fork_turn_code == 0 and (fork_turn.get("turn") or {}).get("sessionKey") == fork_session and (fork_turn.get("turn") or {}).get("parentTurnKey") == first_turn, fork_turn)
    check("cross-workspace-session-hidden", workspace_code == 0 and isolated_workspace and cross_code != 0 and cross.get("ok") is False, cross)
    check("deleted-object-surfaces-before-resume", receipt_key and stale_resume_code == 0 and stale_resume.get("requiresReview") is True and any(item.get("key") == receipt_key for item in (stale_resume.get("context") or {}).get("staleRefs") or []), stale_resume)
    check("stale-context-blocks-silent-continuation", blocked_continue_code != 0 and blocked_continue.get("ok") is False, blocked_continue)
    check("explicit-stale-review-allows-new-turn", reviewed_continue_code == 0 and (reviewed_continue.get("turn") or {}).get("sessionKey") == session_key and turn_count_after == turn_count_before + 1, reviewed_continue)
    check("session-context-never-promotes-business-facts", all((payload.get("sessionContext") or {}).get("longTermBusinessMemoryPromoted") is False for payload in (first, second, reviewed_continue)), {"first": first.get("sessionContext"), "second": second.get("sessionContext"), "reviewed": reviewed_continue.get("sessionContext")})

failed = [item for item in checks if not item["ok"]]
print(json.dumps({"ok": not failed, "schema": "aibi-agent-sessions-verify/v1", "checks": checks, "failedChecks": failed}, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
