from __future__ import annotations

import csv
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


def run(env: dict[str, str], arguments: list[str], expected_status: int = 0) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "tools/aibi_cli.py", "--json", *arguments],
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
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


def confirm(env: dict[str, str], arguments: list[str], preview: dict[str, Any], plan_key: str) -> dict[str, Any]:
    plan = preview.get(plan_key) if isinstance(preview.get(plan_key), dict) else {}
    return run(env, [*arguments, "--yes", "--expected-plan", str(plan.get("planFingerprint") or "")])


def write_values(path: Path, values: list[int]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["period", "value"])
        writer.writeheader()
        for index, value in enumerate(values, start=1):
            writer.writerow({"period": f"2026-{index:02d}", "value": value})


def snapshot_for_query(env: dict[str, str], *, aggregation: str, reason: str, parent: str = "", operation: str = "create") -> tuple[dict[str, Any], dict[str, Any]]:
    query = run(env, ["query", "--table", "metrics", "--measure", "value", "--agg", aggregation, "--limit", "100", "--request", f"value {aggregation}"])
    unit_key = str(query.get("analysisUnit", {}).get("unitKey") or "")
    command = f"analysis-snapshot-{operation}"
    args = [command]
    if parent:
        args.extend(["--snapshot", parent])
    args.extend(["--unit", unit_key, "--reason", reason, "--row-limit", "1"])
    preview = run(env, args)
    created = confirm(env, args, preview, "analysisSnapshotPlan")
    return query, created


with tempfile.TemporaryDirectory(prefix="aibi-metric-monitor-", ignore_cleanup_errors=True) as temp_dir:
    temp = Path(temp_dir)
    source = temp / "metrics.csv"
    database = temp / "runtime.sqlite"
    write_values(source, [100, 110])
    env = {
        **os.environ,
        "AIBI_HYBRID_DB_PATH": str(database),
        "AIBI_HYBRID_DUCKDB_PATH": str(temp / "runtime.duckdb"),
        "AIBI_WORKSPACE_RECOVERY_ROOT": str(temp / "workspace-recovery"),
        "AIBI_EVIDENCE_BUNDLE_ROOT": str(temp / "evidence"),
        "PYTHONIOENCODING": "utf-8",
    }

    imported = run(env, ["import-commit", str(source), "--table", "metrics", "--name", "Metrics", "--mode", "create", "--yes"])
    check("neutral-source-imports", imported.get("committed") is True and imported.get("processExitCode") == 0, imported)
    baseline_query, baseline_created = snapshot_for_query(env, aggregation="sum", reason="monitor-baseline")
    baseline = baseline_created.get("analysisSnapshot", {})
    baseline_key = str(baseline.get("snapshotKey") or "")
    check("scalar-current-baseline-snapshot-exists", baseline_query.get("analysisUnit", {}).get("status") == "ready" and baseline.get("status") == "current" and baseline.get("rowCount") == 1, baseline_created)

    create_args = [
        "metric-monitor-create", "--snapshot", baseline_key, "--label", "Revenue watch",
        "--cadence", "weekly", "--strategy", "absolute-change", "--direction", "increase",
        "--threshold", "10", "--warning-ratio", "0.8",
    ]
    preview = run(env, create_args)
    plan = preview.get("metricMonitorPlan", {})
    check(
        "definition-create-is-dry-run-and-exact-plan-bound",
        preview.get("dryRun") is True
        and preview.get("requiresConfirmation") is True
        and plan.get("operation") == "create"
        and plan.get("notificationsPlanned") == 0
        and plan.get("businessSystemWritesPlanned") == 0
        and len(str(plan.get("planFingerprint") or "")) == 64,
        preview,
    )
    missing_plan = run(env, [*create_args, "--yes"], expected_status=1)
    check("definition-confirmation-requires-preview-fingerprint", missing_plan.get("processExitCode") == 1 and "expected-plan" in str(missing_plan.get("error") or ""), missing_plan)
    created = confirm(env, create_args, preview, "metricMonitorPlan")
    monitor = created.get("metricMonitor", {})
    monitor_key = str(monitor.get("monitorKey") or "")
    check(
        "confirmed-definition-binds-metric-cadence-threshold-and-capability",
        created.get("confirmed") is True
        and created.get("changed") is True
        and monitor.get("metric") == "value"
        and monitor.get("cadence") == "weekly"
        and monitor.get("threshold") == 10
        and monitor.get("thresholdSource") == "user"
        and monitor.get("semanticFingerprint") == baseline.get("semanticFingerprint")
        and monitor.get("capabilityVersion") == "metric-monitor/v1"
        and monitor.get("backgroundSchedulerEnabled") is False,
        created,
    )

    repeat_preview = run(env, create_args)
    repeated = confirm(env, create_args, repeat_preview, "metricMonitorPlan")
    check("exact-definition-is-idempotent", repeat_preview.get("metricMonitorPlan", {}).get("alreadyExists") is True and repeated.get("changed") is False and repeated.get("metricMonitor", {}).get("monitorKey") == monitor_key, repeated)

    baseline_run = run(env, ["metric-monitor-run", "--monitor", monitor_key])
    baseline_evaluation = baseline_run.get("metricMonitorEvaluation", {})
    check(
        "first-run-only-establishes-baseline",
        baseline_run.get("writesEvidence") is True
        and baseline_run.get("writesBusinessState") is False
        and baseline_evaluation.get("status") == "baseline"
        and baseline_evaluation.get("sequence") == 1
        and baseline_evaluation.get("notificationsSent") == 0
        and baseline_evaluation.get("businessSystemWrites") == 0
        and baseline_evaluation.get("providerUsed") is False,
        baseline_run,
    )

    write_values(source, [150, 170])
    replaced_source = run(env, ["import-commit", str(source), "--table", "metrics", "--name", "Metrics", "--mode", "replace", "--yes"])
    check("new-data-version-imports", replaced_source.get("committed") is True, replaced_source)
    current_query, current_created = snapshot_for_query(env, aggregation="sum", reason="monitor-current", parent=baseline_key, operation="refresh")
    current = current_created.get("analysisSnapshot", {})
    current_key = str(current.get("snapshotKey") or "")
    check("same-semantics-current-snapshot-refreshes", current_query.get("analysisUnit", {}).get("status") == "ready" and current.get("status") == "current" and current.get("semanticFingerprint") == baseline.get("semanticFingerprint"), current_created)
    stale_baseline = run(env, ["analysis-snapshots", "--snapshot", baseline_key])
    check("baseline-is-historical-not-current-planning-input", stale_baseline.get("analysisSnapshot", {}).get("status") == "stale" and stale_baseline.get("analysisSnapshot", {}).get("freshness", {}).get("usableForPlanning") is False, stale_baseline)

    breached = run(env, ["metric-monitor-run", "--monitor", monitor_key, "--snapshot", current_key])
    breached_evaluation = breached.get("metricMonitorEvaluation", {})
    check(
        "compatible-historical-baseline-and-current-snapshot-produce-breached-trace",
        breached.get("processExitCode") == 0
        and breached_evaluation.get("status") == "breached"
        and breached_evaluation.get("absoluteChange") == 110
        and breached_evaluation.get("blockers") == []
        and breached_evaluation.get("trace", {}).get("notificationsSent") == 0
        and breached_evaluation.get("trace", {}).get("businessSystemWrites") == 0
        and len(breached.get("evidence") or []) == 3
        and len(str(breached_evaluation.get("traceFingerprint") or "")) == 64,
        breached,
    )

    incompatible_query, incompatible_created = snapshot_for_query(env, aggregation="avg", reason="semantic-change", parent=current_key, operation="replace")
    incompatible_key = str(incompatible_created.get("analysisSnapshot", {}).get("snapshotKey") or "")
    blocked = run(env, ["metric-monitor-run", "--monitor", monitor_key, "--snapshot", incompatible_key])
    blocked_evaluation = blocked.get("metricMonitorEvaluation", {})
    check(
        "semantic-drift-records-blocked-evaluation-without-business-action",
        incompatible_query.get("analysisUnit", {}).get("status") == "ready"
        and blocked.get("processExitCode") == 0
        and blocked_evaluation.get("status") == "blocked"
        and "metric-monitor-semantic-definition-drifted" in blocked_evaluation.get("blockers", [])
        and blocked_evaluation.get("notificationsSent") == 0
        and blocked_evaluation.get("businessSystemWrites") == 0,
        blocked,
    )

    no_threshold_args = ["metric-monitor-create", "--snapshot", current_key, "--label", "Track only"]
    no_threshold_preview = run(env, no_threshold_args)
    no_threshold_created = confirm(env, no_threshold_args, no_threshold_preview, "metricMonitorPlan")
    no_threshold_monitor = no_threshold_created.get("metricMonitor", {})
    no_threshold_key = str(no_threshold_monitor.get("monitorKey") or "")
    run(env, ["metric-monitor-run", "--monitor", no_threshold_key])
    no_threshold_evaluation = run(env, ["metric-monitor-run", "--monitor", no_threshold_key, "--snapshot", current_key]).get("metricMonitorEvaluation", {})
    check("missing-threshold-only-reports-change-without-alert", no_threshold_monitor.get("threshold") is None and no_threshold_monitor.get("thresholdSource") == "none" and no_threshold_evaluation.get("status") == "normal", no_threshold_evaluation)

    listed = run(env, ["metric-monitors", "--monitor", monitor_key, "--limit", "10"])
    evaluations = listed.get("metricMonitorEvaluations") or []
    check(
        "monitor-and-replayable-evaluations-are-listable-in-workspace",
        listed.get("metricMonitor", {}).get("monitorKey") == monitor_key
        and [item.get("sequence") for item in evaluations] == [3, 2, 1]
        and all(item.get("businessRowsExposed") == 0 for item in evaluations),
        listed,
    )

    replace_args = ["metric-monitor-replace", "--monitor", monitor_key, "--snapshot", current_key, "--label", "Revenue watch v2", "--threshold", "20"]
    replacement_preview = run(env, replace_args)
    replacement = confirm(env, replace_args, replacement_preview, "metricMonitorPlan")
    replacement_key = str(replacement.get("metricMonitor", {}).get("monitorKey") or "")
    old_monitor = run(env, ["metric-monitors", "--monitor", monitor_key]).get("metricMonitor", {})
    check("replacement-is-immutable-child-and-retires-parent", replacement_key and replacement_key != monitor_key and replacement.get("metricMonitor", {}).get("parentMonitorKey") == monitor_key and old_monitor.get("status") == "replaced", replacement)

    delete_args = ["metric-monitor-delete", "--monitor", replacement_key]
    delete_preview = run(env, delete_args)
    deleted = confirm(env, delete_args, delete_preview, "metricMonitorPlan")
    check("delete-preserves-monitor-tombstone-and-evaluation-history", deleted.get("metricMonitor", {}).get("status") == "deleted" and deleted.get("changed") is True, deleted)

    with closing(sqlite3.connect(database)) as connection:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        tables = {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        indexes = {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        trace_count = int(connection.execute("SELECT COUNT(*) FROM metric_monitor_evaluations WHERE workspace_id = 'default' AND monitor_key = ?", (monitor_key,)).fetchone()[0])
    check(
        "schema-v16-persists-monitor-definitions-and-replayable-traces",
        version == 16
        and {"metric_monitors", "metric_monitor_evaluations"}.issubset(tables)
        and {"idx_metric_monitors_workspace_status", "idx_metric_monitors_workspace_input", "idx_metric_monitor_evaluations_workspace_monitor"}.issubset(indexes)
        and trace_count == 3,
        {"version": version, "tables": sorted(tables), "indexes": sorted(indexes), "traceCount": trace_count},
    )

    workspace_create = run(env, ["workspace-create", "--name", "isolated-monitor", "--yes"])
    isolated_id = str(workspace_create.get("created", {}).get("id") or "")
    run(env, ["workspace-select", isolated_id, "--yes"])
    isolated = run(env, ["metric-monitors"])
    check("monitor-definitions-and-traces-are-workspace-isolated", isolated.get("count") == 0 and isolated.get("metricMonitors") == [], isolated)
    run(env, ["workspace-select", "default", "--yes"])
    delete_request_key = "metric-monitor-isolated-workspace-delete"
    delete_preview = run(env, [
        "workspace-delete", isolated_id,
        "--request-key", delete_request_key,
    ])
    workspace_delete = run(env, [
        "workspace-delete", isolated_id,
        "--request-key", delete_request_key,
        "--expected-plan", str((delete_preview.get("deletePlan") or {}).get("planFingerprint") or ""),
        "--yes",
    ])
    check("workspace-delete-covers-monitor-tables", workspace_delete.get("deletedCounts", {}).get("metric_monitors") == 0 and workspace_delete.get("deletedCounts", {}).get("metric_monitor_evaluations") == 0, workspace_delete)


failed = [item for item in CHECKS if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-metric-monitor-verify/v1",
    "generatedBy": "scripts/verify-metric-monitors.py",
    "checks": CHECKS,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
