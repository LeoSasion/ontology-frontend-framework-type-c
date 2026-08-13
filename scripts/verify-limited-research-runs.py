from __future__ import annotations

from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CHECKS: list[dict[str, Any]] = []


def check(label: str, ok: bool, detail: Any = None) -> None:
    CHECKS.append({"label": label, "ok": bool(ok), "detail": None if ok else detail})


def run(arguments: list[str], env: dict[str, str]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "tools/aibi_cli.py", "--json", *arguments],
        cwd=ROOT, env=env, text=True, encoding="utf-8", capture_output=True, check=False,
    )
    try:
        payload = json.loads(completed.stdout.strip() or "{}")
    except json.JSONDecodeError:
        payload = {"ok": False, "stdout": completed.stdout, "stderr": completed.stderr}
    payload["processExitCode"] = completed.returncode
    return payload


def answer(turn: dict[str, Any]) -> dict[str, Any]:
    return turn.get("answer") if isinstance(turn.get("answer"), dict) else {}


def forbidden_rows(value: Any) -> bool:
    if isinstance(value, dict):
        return any(key in {"rows", "calculation", "result_rows_json", "compiledSql"} or forbidden_rows(item) for key, item in value.items())
    if isinstance(value, list):
        return any(forbidden_rows(item) for item in value)
    return False


def create_result(env: dict[str, str], prompt: str, *, parent_run: str = "", session: str = "", label: str = "") -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    turn_args = ["agent-turn-run", "--read-only"]
    if session:
        turn_args.extend(["--session", session])
    if parent_run:
        turn_args.extend(["--parent-run", parent_run, "--branch-label", label or "研究分支"])
    turn_args.append(prompt)
    turn = run(turn_args, env)
    result = answer(turn)
    return turn, result.get("analysisRun") or {}, result.get("analysisUnit") or {}


def confirm(args: list[str], plan: dict[str, Any], env: dict[str, str]) -> dict[str, Any]:
    return run([*args, "--yes", "--expected-plan", str(plan.get("planFingerprint") or "")], env)


with tempfile.TemporaryDirectory(prefix="aibi-c-limited-research-") as temp_dir:
    temp = Path(temp_dir)
    db_path = temp / "metadata.sqlite"
    env = {
        **os.environ,
        "AIBI_HYBRID_DB_PATH": str(db_path),
        "AIBI_HYBRID_DUCKDB_PATH": str(temp / "analytics.duckdb"),
        "AIBI_WORKSPACE_RECOVERY_ROOT": str(temp / "workspace-recovery"),
        "AIBI_EVIDENCE_BUNDLE_ROOT": str(temp / "evidence"),
        "PYTHONIOENCODING": "utf-8",
    }

    initialized = run(["status"], env)
    imported = run(["import-commit", "validation-inputs/orders.csv", "--table", "orders", "--name", "Orders", "--mode", "create", "--yes"], env)
    with closing(sqlite3.connect(db_path)) as connection:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        tables = {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
    check("schema-v16-initializes-research-ledger", initialized.get("ok") is True and imported.get("committed") is True and version == 16 and {"research_runs", "research_plan_revisions", "research_observations", "research_run_events"}.issubset(tables), {"version": version, "tables": sorted(tables)})

    root_turn, root_run, root_unit = create_result(env, "请将net_sales按channel合计并生成柱状图")
    session_key = str((root_turn.get("session") or {}).get("sessionKey") or "")
    thread_args = ["exploration-thread-create", "--run", str(root_run.get("run_key") or ""), "--unit", str(root_unit.get("unitKey") or ""), "--session", session_key, "--turn", str((root_turn.get("turn") or {}).get("turnKey") or ""), "--title", "有限研究", "--label", "渠道基线"]
    thread_preview = run(thread_args, env)
    thread_created = confirm(thread_args, thread_preview.get("explorationPlan") or {}, env)
    thread_key = str(thread_created.get("threadKey") or "")
    root_anchor = str(thread_created.get("anchorKey") or "")

    counter_turn, counter_run, counter_unit = create_result(env, "请将net_sales按category合计并生成柱状图", parent_run=str(root_run.get("run_key") or ""), session=session_key, label="品类反例")
    counter_args = ["exploration-anchor-add", "--thread", thread_key, "--parent-anchor", root_anchor, "--run", str(counter_run.get("run_key") or ""), "--unit", str(counter_unit.get("unitKey") or ""), "--session", session_key, "--turn", str((counter_turn.get("turn") or {}).get("turnKey") or ""), "--label", "品类反例"]
    counter_preview = run(counter_args, env)
    counter_added = confirm(counter_args, counter_preview.get("explorationPlan") or {}, env)
    counter_anchor = str(counter_added.get("anchorKey") or "")

    sensitivity_turn, sensitivity_run, sensitivity_unit = create_result(env, "请将net_sales按shop合计并生成柱状图", parent_run=str(root_run.get("run_key") or ""), session=session_key, label="门店敏感性")
    sensitivity_args = ["exploration-anchor-add", "--thread", thread_key, "--parent-anchor", root_anchor, "--run", str(sensitivity_run.get("run_key") or ""), "--unit", str(sensitivity_unit.get("unitKey") or ""), "--session", session_key, "--turn", str((sensitivity_turn.get("turn") or {}).get("turnKey") or ""), "--label", "门店敏感性"]
    sensitivity_preview = run(sensitivity_args, env)
    sensitivity_added = confirm(sensitivity_args, sensitivity_preview.get("explorationPlan") or {}, env)
    sensitivity_anchor = str(sensitivity_added.get("anchorKey") or "")
    check("three-current-anchors-support-bounded-research", all([thread_key, root_anchor, counter_anchor, sensitivity_anchor]), {"thread": thread_created, "counter": counter_added, "sensitivity": sensitivity_added})

    create_args = ["research-run-create", "--thread", thread_key, "--anchor", root_anchor, "--goal", "判断渠道差异是否在品类和门店切片下仍然成立", "--skill", "driver-investigation@1.0.0", "--hypothesis", "渠道差异具有稳定方向", "--counterexample", "按品类切片寻找方向反转", "--sensitivity", "按门店切片检查排序稳定性"]
    create_preview = run(create_args, env)
    create_plan = create_preview.get("researchPlan") or {}
    check("create-is-bounded-dry-run-with-no-business-rows", create_preview.get("dryRun") is True and create_preview.get("requiresConfirmation") is True and create_plan.get("providerCanMutate") is False and create_plan.get("businessRowsCopied") is False and not forbidden_rows(create_plan), create_preview)
    missing_expected = run([*create_args, "--yes"], env)
    check("create-confirmation-requires-preview-fingerprint", missing_expected.get("processExitCode") == 1 and "expected-plan" in str(missing_expected.get("error") or ""), missing_expected)
    created = confirm(create_args, create_plan, env)
    research = created.get("researchRun") or {}
    research_key = str(research.get("researchKey") or "")
    initial_fingerprint = str((research.get("currentRevision") or {}).get("fingerprint") or "")
    check("initial-research-run-is-current-and-finite", created.get("confirmed") is True and research.get("status") == "active" and research.get("freshness", {}).get("usableForPlanning") is True and research.get("revisionCount") == 1 and research.get("budget", {}).get("maxObservations") == 8 and not forbidden_rows(research), created)

    overflow_args = ["research-run-create", "--thread", thread_key, "--goal", "超预算"]
    for index in range(7):
        overflow_args.extend(["--hypothesis", f"H{index}"])
    overflow = run(overflow_args, env)
    check("hypothesis-budget-fails-closed", overflow.get("processExitCode") == 1 and "fixed item budget (6)" in str(overflow.get("error") or ""), overflow)

    historical_observe_args = ["research-run-observe", "--research", research_key, "--anchor", counter_anchor, "--kind", "counterexample", "--step", "counterexample-1", "--verdict", "supports", "--note", "初版计划下的反例观察", "--expected-revision", initial_fingerprint]
    historical_observe_preview = run(historical_observe_args, env)
    historical_observed = confirm(historical_observe_args, historical_observe_preview.get("researchPlan") or {}, env)
    check("current-revision-counts-its-own-observations", (historical_observed.get("researchRun") or {}).get("coverage", {}).get("counterexample") == 1, historical_observed)

    revise_args = ["research-run-revise", "--research", research_key, "--reason", "明确反例与敏感性退出条件", "--clear-hypotheses", "--expected-revision", initial_fingerprint]
    revise_preview = run(revise_args, env)
    wrong_revision = run(["research-run-revise", "--research", research_key, "--reason", "错误父版本", "--expected-revision", "wrong"], env)
    check("revision-requires-current-parent-fingerprint", wrong_revision.get("processExitCode") == 1 and "revision changed" in str(wrong_revision.get("error") or ""), wrong_revision)
    revised = confirm(revise_args, revise_preview.get("researchPlan") or {}, env)
    revised_run = revised.get("researchRun") or {}
    current_revision = revised_run.get("currentRevision") or {}
    current_fingerprint = str(current_revision.get("fingerprint") or "")
    with closing(sqlite3.connect(db_path)) as connection:
        stored_initial = connection.execute("SELECT plan_fingerprint FROM research_plan_revisions WHERE workspace_id = 'default' AND research_key = ? AND revision_number = 1", (research_key,)).fetchone()
    check("revision-appends-without-overwriting-history", revised_run.get("revisionCount") == 2 and current_revision.get("parentFingerprint") == initial_fingerprint and current_revision.get("hypotheses") == [] and current_fingerprint != initial_fingerprint and stored_initial and stored_initial[0] == initial_fingerprint, revised)
    check("superseded-revision-observations-do-not-satisfy-current-coverage", revised_run.get("observationCount") == 1 and revised_run.get("coverage", {}).get("counterexample") == 0, revised_run)

    early_finalize = run(["research-run-finalize", "--research", research_key, "--expected-revision", current_fingerprint], env)
    early_conclusion = ((early_finalize.get("researchPlan") or {}).get("proposed") or {}).get("conclusion") or {}
    check("missing-challenge-coverage-remains-inconclusive", early_finalize.get("dryRun") is True and early_conclusion.get("outcome") == "inconclusive" and set(early_conclusion.get("blockers") or []) == {"counterexample-observation-required", "sensitivity-observation-required"}, early_finalize)

    counter_observe_args = ["research-run-observe", "--research", research_key, "--anchor", counter_anchor, "--kind", "counterexample", "--step", "counterexample-1", "--verdict", "challenges", "--note", "品类切片出现方向反转", "--expected-revision", current_fingerprint]
    counter_observe_preview = run(counter_observe_args, env)
    counter_observed = confirm(counter_observe_args, counter_observe_preview.get("researchPlan") or {}, env)
    sensitivity_observe_args = ["research-run-observe", "--research", research_key, "--anchor", sensitivity_anchor, "--kind", "sensitivity", "--step", "sensitivity-1", "--verdict", "supports", "--note", "门店切片排序方向稳定", "--expected-revision", current_fingerprint]
    sensitivity_observe_preview = run(sensitivity_observe_args, env)
    sensitivity_observed = confirm(sensitivity_observe_args, sensitivity_observe_preview.get("researchPlan") or {}, env)
    observed_run = sensitivity_observed.get("researchRun") or {}
    check("counterexample-and-sensitivity-use-current-same-thread-anchors", counter_observed.get("changed") is True and sensitivity_observed.get("changed") is True and observed_run.get("coverage", {}).get("counterexample") == 1 and observed_run.get("coverage", {}).get("sensitivity") == 1 and all(item.get("freshness", {}).get("usableForPlanning") is True for item in observed_run.get("observations") or []) and not forbidden_rows(observed_run), observed_run)

    other_turn, other_run, other_unit = create_result(env, "请将quantity按channel合计并生成柱状图")
    other_args = ["exploration-thread-create", "--run", str(other_run.get("run_key") or ""), "--unit", str(other_unit.get("unitKey") or ""), "--session", str((other_turn.get("session") or {}).get("sessionKey") or ""), "--turn", str((other_turn.get("turn") or {}).get("turnKey") or "")]
    other_preview = run(other_args, env)
    other_created = confirm(other_args, other_preview.get("explorationPlan") or {}, env)
    cross_thread = run(["research-run-observe", "--research", research_key, "--anchor", str(other_created.get("anchorKey") or ""), "--kind", "counterexample", "--step", "counterexample-1", "--verdict", "supports", "--note", "跨线程证据", "--expected-revision", current_fingerprint], env)
    check("cross-thread-anchor-is-rejected", cross_thread.get("processExitCode") == 1 and "owning Exploration Thread" in str(cross_thread.get("error") or ""), cross_thread)

    finalize_args = ["research-run-finalize", "--research", research_key, "--expected-revision", current_fingerprint]
    finalize_preview = run(finalize_args, env)
    finalized = confirm(finalize_args, finalize_preview.get("researchPlan") or {}, env)
    final_run = finalized.get("researchRun") or {}
    trace = final_run.get("trace") or {}
    sequences = [event.get("sequence") for event in trace.get("events") or []]
    check("finalization-reconciles-mixed-evidence-and-unified-trace", final_run.get("storedStatus") == "completed" and final_run.get("conclusion", {}).get("outcome") == "mixed" and trace.get("eventCount") == 6 and sequences == sorted(sequences) and len(str(trace.get("fingerprint") or "")) == 64, final_run)

    idempotent_preview = run(finalize_args, env)
    idempotent_without_plan = run([*finalize_args, "--yes"], env)
    idempotent_confirmed = confirm(finalize_args, idempotent_preview.get("researchPlan") or {}, env)
    check(
        "completed-finalization-still-requires-preview-fingerprint",
        idempotent_preview.get("dryRun") is True
        and idempotent_preview.get("requiresConfirmation") is True
        and idempotent_without_plan.get("processExitCode") == 1
        and "expected-plan" in str(idempotent_without_plan.get("error") or "")
        and idempotent_confirmed.get("changed") is False
        and ((idempotent_confirmed.get("researchRun") or {}).get("trace") or {}).get("eventCount") == 6,
        {"preview": idempotent_preview, "withoutPlan": idempotent_without_plan, "confirmed": idempotent_confirmed},
    )

    isolated_created = run(["workspace-create", "--name", "Research isolation", "--yes"], env)
    isolated_id = str((isolated_created.get("created") or {}).get("id") or "")
    run(["workspace-select", isolated_id, "--yes"], env)
    isolated_list = run(["research-runs"], env)
    cross_scope = run(["research-runs", "--research", research_key], env)
    run(["workspace-select", "default", "--yes"], env)
    delete_request_key = "limited-research-isolated-workspace-delete"
    delete_preview = run([
        "workspace-delete", isolated_id,
        "--request-key", delete_request_key,
    ], env)
    deleted = run([
        "workspace-delete", isolated_id,
        "--request-key", delete_request_key,
        "--expected-plan", str((delete_preview.get("deletePlan") or {}).get("planFingerprint") or ""),
        "--yes",
    ], env)
    check("research-state-is-workspace-isolated-and-delete-aware", isolated_list.get("count") == 0 and cross_scope.get("processExitCode") == 1 and deleted.get("confirmed") is True and all(name in deleted.get("deletedCounts", {}) for name in ("research_runs", "research_plan_revisions", "research_observations", "research_run_events")), {"isolated": isolated_list, "cross": cross_scope, "deleted": deleted})

    replaced = run(["import-commit", "validation-inputs/orders.csv", "--table", "orders", "--name", "Orders refreshed", "--mode", "replace", "--yes"], env)
    stale = run(["research-runs", "--research", research_key], env).get("researchRun") or {}
    blocked_revision = run(["research-run-revise", "--research", research_key, "--reason", "stale 后继续", "--expected-revision", current_fingerprint], env)
    check("source-drift-keeps-history-but-blocks-planning-without-fallback", replaced.get("committed") is True and stale.get("status") == "blocked" and stale.get("freshness", {}).get("usableForPlanning") is False and stale.get("freshness", {}).get("staleFallbackUsed") is False and blocked_revision.get("processExitCode") == 1, {"stale": stale, "blockedRevision": blocked_revision})


FAILED = [item for item in CHECKS if not item["ok"]]
print(json.dumps({"ok": not FAILED, "schema": "aibi-limited-research-runs-verify/v1", "generatedBy": "scripts/verify-limited-research-runs.py", "checks": CHECKS, "failedChecks": FAILED}, ensure_ascii=False, indent=2))
raise SystemExit(1 if FAILED else 0)
