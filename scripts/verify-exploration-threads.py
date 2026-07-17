from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
from contextlib import closing
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CHECKS: list[dict[str, Any]] = []


def check(label: str, ok: bool, detail: Any = None) -> None:
    CHECKS.append({"label": label, "ok": bool(ok), "detail": None if ok else detail})


def run(arguments: list[str], env: dict[str, str], expected_status: int = 0) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "tools/aibi_cli.py", "--json", *arguments],
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout.strip() or "{}")
    except json.JSONDecodeError:
        payload = {"ok": False, "stdout": completed.stdout, "stderr": completed.stderr}
    payload["processExitCode"] = completed.returncode
    payload["expectedProcessExitCode"] = expected_status
    return payload


def answer(turn_result: dict[str, Any]) -> dict[str, Any]:
    value = turn_result.get("answer")
    return value if isinstance(value, dict) else {}


def has_forbidden_result_payload(value: Any) -> bool:
    if isinstance(value, dict):
        return any(key in {"rows", "calculation", "result_rows_json"} or has_forbidden_result_payload(item) for key, item in value.items())
    if isinstance(value, list):
        return any(has_forbidden_result_payload(item) for item in value)
    return False


with tempfile.TemporaryDirectory(prefix="aibi-c-exploration-threads-") as temp_dir:
    temp = Path(temp_dir)
    db_path = temp / "metadata.sqlite"
    env = {
        **os.environ,
        "AIBI_HYBRID_DB_PATH": str(db_path),
        "AIBI_HYBRID_DUCKDB_PATH": str(temp / "analytics.duckdb"),
        "AIBI_EVIDENCE_BUNDLE_ROOT": str(temp / "evidence"),
        "PYTHONIOENCODING": "utf-8",
    }

    initialized = run(["status"], env)
    imported = run(["import-commit", "validation-inputs/orders.csv", "--table", "orders", "--name", "Orders", "--mode", "create", "--yes"], env)
    check("schema-v14-initializes", initialized.get("ok") is True and imported.get("committed") is True)
    with closing(sqlite3.connect(db_path)) as connection:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    check("exploration-schema-is-versioned", version == 14, version)

    root = run(["agent-turn-run", "--read-only", "请用net_sales按channel生成柱状图"], env)
    root_answer = answer(root)
    root_run = root_answer.get("analysisRun") or {}
    root_unit = root_answer.get("analysisUnit") or {}
    root_session = root.get("session") or {}
    root_turn = root.get("turn") or {}
    check(
        "root-result-has-recoverable-bindings",
        root.get("ok") is True
        and root_run.get("status") == "executed"
        and root_unit.get("status") == "ready"
        and root_turn.get("status") == "completed"
        and root_session.get("sessionKey")
        and root_turn.get("turnKey"),
        {"root": root, "answer": root_answer},
    )

    create_args = [
        "exploration-thread-create",
        "--run", str(root_run.get("run_key") or ""),
        "--unit", str(root_unit.get("unitKey") or ""),
        "--session", str(root_session.get("sessionKey") or ""),
        "--turn", str(root_turn.get("turnKey") or ""),
        "--title", "渠道表现探索",
        "--label", "渠道基线",
    ]
    preview = run(create_args, env)
    plan = preview.get("explorationPlan") or {}
    check(
        "thread-create-is-dry-run-with-bounded-plan",
        preview.get("dryRun") is True
        and preview.get("requiresConfirmation") is True
        and plan.get("providerCanMutate") is False
        and plan.get("businessRowsCopied") is False
        and len(str(plan.get("planFingerprint") or "")) == 64
        and not has_forbidden_result_payload(plan),
        preview,
    )
    without_expected = run([*create_args, "--yes"], env, expected_status=1)
    wrong_expected = run([*create_args, "--yes", "--expected-plan", "wrong"], env, expected_status=1)
    check(
        "confirmation-requires-the-exact-preview-plan",
        without_expected.get("processExitCode") == 1
        and wrong_expected.get("processExitCode") == 1
        and "expected-plan" in str(without_expected.get("error") or "")
        and "changed after preview" in str(wrong_expected.get("error") or ""),
        {"missing": without_expected, "wrong": wrong_expected},
    )
    with closing(sqlite3.connect(db_path)) as connection:
        count_before = int(connection.execute("SELECT COUNT(*) FROM exploration_threads").fetchone()[0])
    check("failed-confirmation-has-no-side-effect", count_before == 0, count_before)

    created = run([*create_args, "--yes", "--expected-plan", str(plan.get("planFingerprint") or "")], env)
    thread_key = str(created.get("threadKey") or "")
    root_anchor_key = str(created.get("anchorKey") or "")
    listed = run(["exploration-threads", "--thread", thread_key], env)
    thread = listed.get("explorationThread") or {}
    root_summary = (((thread.get("resultBoard") or {}).get("items") or [{}])[0].get("anchor") or {}).get("summary") or {}
    check(
        "root-thread-persists-one-current-anchor-and-board-item",
        created.get("confirmed") is True
        and created.get("changed") is True
        and thread.get("status") == "current"
        and thread.get("currentAnchorUsable") is True
        and thread.get("anchorCount") == 1
        and (thread.get("resultBoard") or {}).get("itemCount") == 1
        and (thread.get("resultBoard") or {}).get("businessRowsCopied") is False
        and not has_forbidden_result_payload(thread),
        listed,
    )
    check(
        "result-board-uses-business-fields-not-query-aliases",
        root_summary.get("measureColumn") == "net_sales"
        and root_summary.get("dimensionColumns") == ["channel"],
        root_summary,
    )

    duplicate_preview = run(create_args, env)
    duplicate_plan = duplicate_preview.get("explorationPlan") or {}
    duplicate = run([*create_args, "--yes", "--expected-plan", str(duplicate_plan.get("planFingerprint") or "")], env)
    check("root-create-is-idempotent", duplicate_plan.get("alreadyExists") is True and duplicate.get("changed") is False, duplicate)

    branch = run([
        "agent-turn-run", "--read-only",
        "--session", str(root_session.get("sessionKey") or ""),
        "--parent-run", str(root_run.get("run_key") or ""),
        "--branch-label", "品类比较",
        "请用net_sales按category生成柱状图",
    ], env)
    branch_answer = answer(branch)
    branch_run = branch_answer.get("analysisRun") or {}
    branch_unit = branch_answer.get("analysisUnit") or {}
    branch_turn = branch.get("turn") or {}
    check(
        "executed-current-root-can-create-a-lineage-branch",
        branch.get("ok") is True
        and branch_run.get("parent_run_key") == root_run.get("run_key")
        and branch_unit.get("status") == "ready",
        branch,
    )
    add_args = [
        "exploration-anchor-add",
        "--thread", thread_key,
        "--parent-anchor", root_anchor_key,
        "--run", str(branch_run.get("run_key") or ""),
        "--unit", str(branch_unit.get("unitKey") or ""),
        "--session", str(root_session.get("sessionKey") or ""),
        "--turn", str(branch_turn.get("turnKey") or ""),
        "--label", "品类比较",
    ]
    add_preview = run(add_args, env)
    add_plan = add_preview.get("explorationPlan") or {}
    added = run([*add_args, "--yes", "--expected-plan", str(add_plan.get("planFingerprint") or "")], env)
    branch_anchor_key = str(added.get("anchorKey") or "")
    after_add = run(["exploration-threads", "--thread", thread_key], env)
    after_add_thread = after_add.get("explorationThread") or {}
    anchors = after_add_thread.get("anchors") or []
    branch_anchor = next((item for item in anchors if item.get("anchorKey") == branch_anchor_key), {})
    check(
        "child-anchor-preserves-run-receipt-unit-turn-and-parent-lineage",
        added.get("changed") is True
        and after_add_thread.get("anchorCount") == 2
        and (after_add_thread.get("resultBoard") or {}).get("itemCount") == 2
        and after_add_thread.get("currentAnchorKey") == branch_anchor_key
        and branch_anchor.get("parentAnchorKey") == root_anchor_key
        and branch_anchor.get("analysisRunKey") == branch_run.get("run_key")
        and branch_anchor.get("queryReceiptKey") == branch_run.get("query_receipt_key")
        and branch_anchor.get("analysisUnitKey") == branch_unit.get("unitKey")
        and branch_anchor.get("turnKey") == branch_turn.get("turnKey"),
        after_add,
    )

    unrelated = run(["agent-turn-run", "--read-only", "--session", str(root_session.get("sessionKey") or ""), "请再次用net_sales按channel生成柱状图"], env)
    unrelated_answer = answer(unrelated)
    unrelated_run = unrelated_answer.get("analysisRun") or {}
    unrelated_unit = unrelated_answer.get("analysisUnit") or {}
    unrelated_turn = unrelated.get("turn") or {}
    mismatched = run([
        "exploration-anchor-add", "--thread", thread_key, "--parent-anchor", root_anchor_key,
        "--run", str(unrelated_run.get("run_key") or ""), "--unit", str(unrelated_unit.get("unitKey") or ""),
        "--session", str(root_session.get("sessionKey") or ""), "--turn", str(unrelated_turn.get("turnKey") or ""),
    ], env, expected_status=1)
    after_mismatch = run(["exploration-threads", "--thread", thread_key], env)
    check(
        "unrelated-run-cannot-be-spliced-into-a-thread",
        mismatched.get("processExitCode") == 1
        and "parent does not match" in str(mismatched.get("error") or "")
        and (after_mismatch.get("explorationThread") or {}).get("anchorCount") == 2,
        mismatched,
    )

    remove_preview = run(["exploration-board-set", "--thread", thread_key, "--anchor", root_anchor_key, "--state", "removed"], env)
    remove_plan = remove_preview.get("explorationPlan") or {}
    removed = run(["exploration-board-set", "--thread", thread_key, "--anchor", root_anchor_key, "--state", "removed", "--yes", "--expected-plan", str(remove_plan.get("planFingerprint") or "")], env)
    after_remove = run(["exploration-threads", "--thread", thread_key], env)
    check(
        "board-removal-preserves-immutable-anchor-history",
        removed.get("changed") is True
        and (after_remove.get("explorationThread") or {}).get("anchorCount") == 2
        and ((after_remove.get("explorationThread") or {}).get("resultBoard") or {}).get("itemCount") == 1,
        after_remove,
    )
    pin_preview = run(["exploration-board-set", "--thread", thread_key, "--anchor", root_anchor_key, "--state", "pinned", "--position", "1"], env)
    pin_plan = pin_preview.get("explorationPlan") or {}
    pinned = run(["exploration-board-set", "--thread", thread_key, "--anchor", root_anchor_key, "--state", "pinned", "--position", "1", "--yes", "--expected-plan", str(pin_plan.get("planFingerprint") or "")], env)
    check("removed-anchor-can-be-repinned", pinned.get("changed") is True, pinned)

    workspace_create = run(["workspace-create", "--name", "Exploration isolation", "--yes"], env)
    isolated_id = str((workspace_create.get("created") or {}).get("id") or "")
    selected_isolated = run(["workspace-select", isolated_id, "--yes"], env)
    isolated_list = run(["exploration-threads"], env)
    cross_scope = run(["exploration-threads", "--thread", thread_key], env, expected_status=1)
    check(
        "thread-reads-are-bound-to-the-active-workspace",
        selected_isolated.get("ok") is True
        and isolated_list.get("count") == 0
        and cross_scope.get("processExitCode") == 1
        and "active workspace" in str(cross_scope.get("error") or ""),
        {"workspace": workspace_create, "crossScope": cross_scope},
    )

    run(["import-commit", "validation-inputs/orders.csv", "--table", "orders", "--name", "Isolated orders", "--mode", "create", "--yes"], env)
    isolated_root = run(["agent-turn-run", "--read-only", "请用net_sales按channel生成柱状图"], env)
    isolated_answer = answer(isolated_root)
    isolated_create_args = [
        "exploration-thread-create",
        "--run", str((isolated_answer.get("analysisRun") or {}).get("run_key") or ""),
        "--unit", str((isolated_answer.get("analysisUnit") or {}).get("unitKey") or ""),
        "--session", str((isolated_root.get("session") or {}).get("sessionKey") or ""),
        "--turn", str((isolated_root.get("turn") or {}).get("turnKey") or ""),
    ]
    isolated_preview = run(isolated_create_args, env)
    isolated_plan = isolated_preview.get("explorationPlan") or {}
    isolated_created = run([*isolated_create_args, "--yes", "--expected-plan", str(isolated_plan.get("planFingerprint") or "")], env)
    run(["workspace-select", "default", "--yes"], env)
    deleted_isolated = run(["workspace-delete", isolated_id, "--yes"], env)
    with closing(sqlite3.connect(db_path)) as connection:
        residual_counts = {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table} WHERE workspace_id = ?", (isolated_id,)).fetchone()[0])
            for table in ("exploration_threads", "exploration_anchors", "exploration_board_items")
        }
    check(
        "workspace-delete-removes-all-exploration-state",
        isolated_created.get("changed") is True
        and deleted_isolated.get("confirmed") is True
        and all(count == 0 for count in residual_counts.values()),
        residual_counts,
    )

    replaced = run(["import-commit", "validation-inputs/orders.csv", "--table", "orders", "--name", "Orders refreshed", "--mode", "replace", "--yes"], env)
    stale_view = run(["exploration-threads", "--thread", thread_key], env)
    stale_thread = stale_view.get("explorationThread") or {}
    stale_anchors = stale_thread.get("anchors") or []
    check(
        "source-drift-keeps-history-but-blocks-continuation-without-fallback",
        replaced.get("committed") is True
        and stale_thread.get("status") == "stale"
        and stale_thread.get("currentAnchorUsable") is False
        and stale_anchors
        and all(anchor.get("freshness", {}).get("usableForContinuation") is False for anchor in stale_anchors)
        and all(anchor.get("freshness", {}).get("staleFallbackUsed") is False for anchor in stale_anchors)
        and all(anchor.get("summary", {}).get("chartType") is None for anchor in stale_anchors),
        stale_view,
    )
    stale_branch = run([
        "agent-turn-run", "--read-only", "--session", str(root_session.get("sessionKey") or ""),
        "--parent-run", str(branch_run.get("run_key") or ""), "继续按地区比较",
    ], env, expected_status=1)
    check(
        "generic-branch-entry-also-blocks-stale-parent-receipts",
        stale_branch.get("processExitCode") == 1 and "stale parent Receipt" in str(stale_branch.get("error") or ""),
        stale_branch,
    )

    with closing(sqlite3.connect(db_path)) as connection:
        connection.execute("DELETE FROM agent_turns WHERE workspace_id = 'default' AND turn_key = ?", (branch_turn.get("turnKey"),))
        connection.commit()
    missing_turn_view = run(["exploration-threads", "--thread", thread_key], env)
    missing_branch_anchor = next(
        (item for item in (missing_turn_view.get("explorationThread") or {}).get("anchors") or [] if item.get("anchorKey") == branch_anchor_key),
        {},
    )
    check(
        "missing-turn-is-reported-without-substitution",
        missing_branch_anchor.get("freshness", {}).get("status") == "missing"
        and "agent-turn" in missing_branch_anchor.get("freshness", {}).get("missingRefs", [])
        and missing_branch_anchor.get("freshness", {}).get("staleFallbackUsed") is False,
        missing_branch_anchor,
    )


FAILED = [item for item in CHECKS if not item["ok"]]
print(json.dumps({
    "ok": not FAILED,
    "schema": "aibi-exploration-threads-verify/v1",
    "generatedBy": "scripts/verify-exploration-threads.py",
    "checks": CHECKS,
    "failedChecks": FAILED,
}, ensure_ascii=False, indent=2))
raise SystemExit(1 if FAILED else 0)
