from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
from contextlib import closing
from typing import Any, Callable

from analysis_snapshot_service import (
    analysis_snapshot_consumer_state,
    get_analysis_snapshot,
)
from analysis_unit_service import get_analysis_unit
from query_plan_receipt_service import get_query_receipt, query_receipt_binding_fingerprint


METRIC_MONITOR_SCHEMA = "aibi-metric-monitor/v1"
METRIC_MONITOR_PLAN_SCHEMA = "aibi-metric-monitor-plan/v1"
METRIC_MONITOR_EVALUATION_SCHEMA = "aibi-metric-monitor-evaluation/v1"
METRIC_MONITOR_TRACE_SCHEMA = "aibi-metric-monitor-trace/v1"
METRIC_MONITOR_CAPABILITY_VERSION = "metric-monitor/v1"
CADENCES = {"manual", "daily", "weekly", "monthly"}
COMPARISON_STRATEGIES = {"absolute-change", "percent-change"}
DIRECTIONS = {"increase", "decrease", "absolute"}


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _json(value: Any) -> str:
    return json.dumps(_canonical(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_json(value: Any, fallback: Any) -> Any:
    try:
        parsed = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback
    return parsed


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _snapshot_integrity(
    connection: sqlite3.Connection,
    workspace_id: str,
    snapshot: dict[str, Any] | None,
    *,
    require_current: bool,
) -> tuple[dict[str, Any] | None, list[str]]:
    blockers: list[str] = []
    if not snapshot:
        return None, ["metric-monitor-snapshot-missing"]
    if str(snapshot.get("storedStatus") or "") == "deleted":
        blockers.append("metric-monitor-snapshot-deleted")
    content = snapshot.get("content") if isinstance(snapshot.get("content"), dict) else {}
    if _fingerprint(content) != str(snapshot.get("contentHash") or ""):
        blockers.append("metric-monitor-snapshot-content-drifted")
    binding = snapshot.get("binding") if isinstance(snapshot.get("binding"), dict) else {}
    unit = get_analysis_unit(connection, workspace_id, str(snapshot.get("unitKey") or ""))
    if not unit:
        blockers.append("metric-monitor-unit-missing")
    else:
        if str(binding.get("unitDefinitionFingerprint") or "") != str(unit.get("definitionFingerprint") or ""):
            blockers.append("metric-monitor-unit-definition-mismatch")
        if str(binding.get("resultFingerprint") or "") != str(unit.get("resultFingerprint") or ""):
            blockers.append("metric-monitor-unit-result-mismatch")
        receipt = get_query_receipt(connection, workspace_id, str(unit.get("queryReceiptKey") or ""))
        if not receipt:
            blockers.append("metric-monitor-receipt-missing")
        elif str(binding.get("receiptBindingFingerprint") or "") != query_receipt_binding_fingerprint(receipt):
            blockers.append("metric-monitor-receipt-binding-mismatch")
    if require_current:
        current_state = analysis_snapshot_consumer_state(connection, workspace_id, snapshot)
        if current_state.get("status") != "current":
            blockers.extend(str(item) for item in current_state.get("blockers") or ["metric-monitor-current-snapshot-stale"])
    return unit, list(dict.fromkeys(blockers))


def _metric_value(snapshot: dict[str, Any], configured_metric: str = "") -> tuple[str, float | None, list[str]]:
    blockers: list[str] = []
    content = snapshot.get("content") if isinstance(snapshot.get("content"), dict) else {}
    unit = content.get("unit") if isinstance(content.get("unit"), dict) else {}
    rows = unit.get("rows") if isinstance(unit.get("rows"), list) else []
    shape = unit.get("shape") if isinstance(unit.get("shape"), dict) else {}
    if len(rows) != 1 or not isinstance(rows[0], dict):
        return configured_metric, None, ["metric-monitor-requires-one-scalar-row"]
    metric = str(configured_metric or shape.get("measureColumn") or "").strip()
    if not metric:
        dimensions = {str(item) for item in shape.get("dimensionColumns") or []}
        candidates = [
            str(key) for key, value in rows[0].items()
            if str(key) not in dimensions and _finite_number(value) is not None
        ]
        if len(candidates) == 1:
            metric = candidates[0]
        else:
            blockers.append("metric-monitor-measure-is-ambiguous")
    value = _finite_number(rows[0].get(metric)) if metric else None
    if value is None:
        blockers.append("metric-monitor-value-missing-or-nonnumeric")
    return metric, value, blockers


def _compatibility_blockers(baseline: dict[str, Any], current: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if str(baseline.get("semanticFingerprint") or "") != str(current.get("semanticFingerprint") or ""):
        blockers.append("metric-monitor-semantic-definition-drifted")
    baseline_binding = baseline.get("binding") if isinstance(baseline.get("binding"), dict) else {}
    current_binding = current.get("binding") if isinstance(current.get("binding"), dict) else {}
    baseline_source = baseline_binding.get("source") if isinstance(baseline_binding.get("source"), dict) else {}
    current_source = current_binding.get("source") if isinstance(current_binding.get("source"), dict) else {}
    stable_checks = (
        ("tableKeys", "metric-monitor-source-identity-drifted"),
        ("relationshipPathFingerprint", "metric-monitor-relationship-path-drifted"),
    )
    for key, blocker in stable_checks:
        if _canonical(baseline_source.get(key)) != _canonical(current_source.get(key)):
            blockers.append(blocker)
    if str(baseline_binding.get("domainPackFingerprint") or "") != str(current_binding.get("domainPackFingerprint") or ""):
        blockers.append("metric-monitor-domain-pack-drifted")
    return blockers


def _monitor_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "schema": METRIC_MONITOR_SCHEMA,
        "monitorKey": row["monitor_key"],
        "workspaceId": row["workspace_id"],
        "parentMonitorKey": row["parent_monitor_key"],
        "operation": row["operation"],
        "status": row["status"],
        "label": row["label"],
        "metric": row["metric_key"],
        "cadence": row["cadence"],
        "comparisonStrategy": row["comparison_strategy"],
        "direction": row["direction"],
        "threshold": _finite_number(row["threshold_value"]),
        "thresholdSource": row["threshold_source"],
        "warningRatio": float(row["warning_ratio"]),
        "semanticFingerprint": row["semantic_fingerprint"],
        "baselineSnapshotKey": row["baseline_snapshot_key"],
        "latestSnapshotKey": row["latest_snapshot_key"],
        "latestEvaluationKey": row["latest_evaluation_key"],
        "latestStatus": row["latest_status"],
        "capabilityVersion": row["capability_version"],
        "definitionFingerprint": row["definition_fingerprint"],
        "inputFingerprint": row["input_fingerprint"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "deletedAt": row["deleted_at"],
        "notificationsSent": 0,
        "businessSystemWrites": 0,
        "backgroundSchedulerEnabled": False,
    }


def _evaluation_row(row: sqlite3.Row) -> dict[str, Any]:
    trace = _load_json(row["trace_json"], {})
    return {
        "schema": METRIC_MONITOR_EVALUATION_SCHEMA,
        "evaluationKey": row["evaluation_key"],
        "workspaceId": row["workspace_id"],
        "monitorKey": row["monitor_key"],
        "sequence": int(row["evaluation_sequence"]),
        "status": row["status"],
        "baselineSnapshotKey": row["baseline_snapshot_key"],
        "currentSnapshotKey": row["current_snapshot_key"],
        "baselineValue": _finite_number(row["baseline_value"]),
        "currentValue": _finite_number(row["current_value"]),
        "absoluteChange": _finite_number(row["absolute_change"]),
        "percentChange": _finite_number(row["percent_change"]),
        "threshold": _finite_number(row["threshold_value"]),
        "thresholdSource": row["threshold_source"],
        "blockers": _load_json(row["blockers_json"], []),
        "trace": trace,
        "traceFingerprint": row["trace_fingerprint"],
        "createdAt": row["created_at"],
        "providerUsed": False,
        "notificationsSent": 0,
        "businessSystemWrites": 0,
        "businessRowsExposed": 0,
    }


def get_metric_monitor(connection: sqlite3.Connection, workspace_id: str, monitor_key: str) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM metric_monitors WHERE workspace_id = ? AND monitor_key = ?",
        (workspace_id, monitor_key),
    ).fetchone()
    return _monitor_row(row) if row else None


def _definition(args: argparse.Namespace, snapshot: dict[str, Any]) -> dict[str, Any]:
    metric, value, blockers = _metric_value(snapshot, str(getattr(args, "metric", "") or ""))
    if blockers or value is None:
        raise ValueError("Metric Monitor baseline must be one numeric scalar: " + ", ".join(blockers))
    cadence = str(getattr(args, "cadence", "manual") or "manual")
    strategy = str(getattr(args, "strategy", "absolute-change") or "absolute-change")
    direction = str(getattr(args, "direction", "absolute") or "absolute")
    if cadence not in CADENCES or strategy not in COMPARISON_STRATEGIES or direction not in DIRECTIONS:
        raise ValueError("Unsupported Metric Monitor cadence, comparison strategy, or direction.")
    threshold_raw = getattr(args, "threshold", None)
    threshold = _finite_number(threshold_raw) if threshold_raw is not None else None
    if threshold is not None and threshold < 0:
        raise ValueError("Metric Monitor threshold must be non-negative.")
    threshold_source = "user" if threshold is not None else "none"
    warning_ratio = _finite_number(getattr(args, "warning_ratio", 0.8))
    if warning_ratio is None or warning_ratio <= 0 or warning_ratio >= 1:
        raise ValueError("warning-ratio must be greater than 0 and less than 1.")
    label = str(getattr(args, "label", "") or "").strip()
    if not label:
        raise ValueError("Metric Monitor label is required.")
    return {
        "label": label,
        "metric": metric,
        "cadence": cadence,
        "comparisonStrategy": strategy,
        "direction": direction,
        "threshold": threshold,
        "thresholdSource": threshold_source,
        "warningRatio": warning_ratio,
        "baselineSnapshotKey": snapshot.get("snapshotKey"),
        "baselineValueFingerprint": _fingerprint({"metric": metric, "value": value}),
        "semanticFingerprint": snapshot.get("semanticFingerprint"),
        "capabilityVersion": METRIC_MONITOR_CAPABILITY_VERSION,
    }


def _monitor_plan(operation: str, workspace_id: str, definition: dict[str, Any], parent_key: str | None) -> dict[str, Any]:
    requested = {
        "operation": operation,
        "workspaceId": workspace_id,
        "parentMonitorKey": parent_key,
        "definition": definition,
    }
    input_fingerprint = _fingerprint({"schema": METRIC_MONITOR_PLAN_SCHEMA, **requested})
    return {
        "schema": METRIC_MONITOR_PLAN_SCHEMA,
        "status": "waiting-confirmation",
        "operation": operation,
        "workspaceId": workspace_id,
        "monitorKey": f"metric_monitor_{input_fingerprint[:20]}",
        "inputFingerprint": input_fingerprint,
        "definitionFingerprint": _fingerprint(definition),
        "planFingerprint": _fingerprint({"schema": METRIC_MONITOR_PLAN_SCHEMA, "inputFingerprint": input_fingerprint}),
        "writesBusinessState": True,
        "notificationsPlanned": 0,
        "businessSystemWritesPlanned": 0,
    }


def _require_expected(args: argparse.Namespace, plan: dict[str, Any]) -> None:
    if str(getattr(args, "expected_plan", "") or "") != str(plan.get("planFingerprint") or ""):
        raise ValueError("Confirmation requires --expected-plan from the dry-run receipt.")


def _create_like(
    args: argparse.Namespace,
    *,
    operation: str,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    with closing(open_db()) as connection:
        if connection.in_transaction:
            connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        workspace_id = active_workspace_id(connection)
        snapshot = get_analysis_snapshot(connection, workspace_id, str(args.snapshot), include_content=True)
        _, blockers = _snapshot_integrity(connection, workspace_id, snapshot, require_current=True)
        if blockers:
            raise ValueError("Metric Monitor definition requires a current intact baseline Snapshot: " + ", ".join(blockers))
        assert snapshot is not None
        parent_key = str(getattr(args, "monitor", "") or "").strip() or None
        parent = get_metric_monitor(connection, workspace_id, parent_key) if parent_key else None
        if operation == "create" and parent_key:
            raise ValueError("Create does not accept a parent Monitor; use replace.")
        if operation == "replace" and (not parent or parent.get("status") == "deleted"):
            raise ValueError("Replace requires an active parent Monitor in the current workspace.")
        definition = _definition(args, snapshot)
        plan = _monitor_plan(operation, workspace_id, definition, parent_key)
        existing = get_metric_monitor(connection, workspace_id, str(plan["monitorKey"]))
        plan["alreadyExists"] = existing is not None and existing.get("status") != "deleted"
        if operation == "replace" and parent and parent.get("status") != "active" and not existing:
            raise ValueError("A replaced Metric Monitor can only replay its exact existing replacement; create from the active child for a new definition.")
        if not bool(getattr(args, "yes", False)):
            connection.rollback()
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "workspaceId": workspace_id, "metricMonitorPlan": plan}
        _require_expected(args, plan)
        if existing:
            if existing.get("status") == "deleted":
                raise ValueError("The exact Monitor definition was deleted; change its label before creating another immutable definition.")
            connection.rollback()
            return {"ok": True, "confirmed": True, "changed": False, "workspaceId": workspace_id, "metricMonitorPlan": plan, "metricMonitor": existing}
        timestamp = now_iso()
        connection.execute(
            """
            INSERT INTO metric_monitors(
              monitor_key, workspace_id, parent_monitor_key, operation, status, label,
              metric_key, cadence, comparison_strategy, direction, threshold_value,
              threshold_source, warning_ratio, semantic_fingerprint, baseline_snapshot_key, latest_snapshot_key,
              latest_evaluation_key, latest_status, capability_version,
              definition_fingerprint, input_fingerprint, created_at, updated_at, deleted_at
            ) VALUES(?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, 'not-run', ?, ?, ?, ?, ?, NULL)
            """,
            (
                plan["monitorKey"], workspace_id, parent_key, operation, definition["label"], definition["metric"],
                definition["cadence"], definition["comparisonStrategy"], definition["direction"], definition["threshold"],
                definition["thresholdSource"], definition["warningRatio"], definition["semanticFingerprint"], definition["baselineSnapshotKey"],
                definition["capabilityVersion"], plan["definitionFingerprint"], plan["inputFingerprint"], timestamp, timestamp,
            ),
        )
        if parent_key:
            connection.execute(
                "UPDATE metric_monitors SET status = 'replaced', updated_at = ? WHERE workspace_id = ? AND monitor_key = ?",
                (timestamp, workspace_id, parent_key),
            )
        connection.commit()
        created = get_metric_monitor(connection, workspace_id, str(plan["monitorKey"]))
        return {"ok": True, "confirmed": True, "changed": True, "workspaceId": workspace_id, "metricMonitorPlan": plan, "metricMonitor": created}


def metric_monitor_create_command(args: argparse.Namespace, **dependencies: Any) -> dict[str, Any]:
    return _create_like(args, operation="create", **dependencies)


def metric_monitor_replace_command(args: argparse.Namespace, **dependencies: Any) -> dict[str, Any]:
    return _create_like(args, operation="replace", **dependencies)


def metric_monitor_delete_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    with closing(open_db()) as connection:
        if connection.in_transaction:
            connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        workspace_id = active_workspace_id(connection)
        monitor = get_metric_monitor(connection, workspace_id, str(args.monitor))
        if not monitor:
            raise ValueError("Unknown Metric Monitor in the active workspace.")
        plan_input = {
            "operation": "delete",
            "workspaceId": workspace_id,
            "monitorKey": monitor["monitorKey"],
            "definitionFingerprint": monitor["definitionFingerprint"],
            "alreadyDeleted": monitor["status"] == "deleted",
        }
        plan = {
            "schema": METRIC_MONITOR_PLAN_SCHEMA,
            **plan_input,
            "status": "waiting-confirmation",
            "planFingerprint": _fingerprint({"schema": METRIC_MONITOR_PLAN_SCHEMA, **plan_input}),
            "writesBusinessState": True,
            "notificationsPlanned": 0,
            "businessSystemWritesPlanned": 0,
        }
        if not bool(getattr(args, "yes", False)):
            connection.rollback()
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "workspaceId": workspace_id, "metricMonitorPlan": plan}
        _require_expected(args, plan)
        if monitor["status"] == "deleted":
            connection.rollback()
            return {"ok": True, "confirmed": True, "changed": False, "workspaceId": workspace_id, "metricMonitorPlan": plan, "metricMonitor": monitor}
        timestamp = now_iso()
        connection.execute(
            "UPDATE metric_monitors SET status = 'deleted', updated_at = ?, deleted_at = ? WHERE workspace_id = ? AND monitor_key = ?",
            (timestamp, timestamp, workspace_id, monitor["monitorKey"]),
        )
        connection.commit()
        return {"ok": True, "confirmed": True, "changed": True, "workspaceId": workspace_id, "metricMonitorPlan": plan, "metricMonitor": get_metric_monitor(connection, workspace_id, monitor["monitorKey"])}


def _score(strategy: str, direction: str, absolute_change: float, percent_change: float | None) -> float | None:
    value = absolute_change if strategy == "absolute-change" else percent_change
    if value is None:
        return None
    if direction == "increase":
        return value
    if direction == "decrease":
        return -value
    return abs(value)


def metric_monitor_run_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    with closing(open_db()) as connection:
        if connection.in_transaction:
            connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        workspace_id = active_workspace_id(connection)
        monitor = get_metric_monitor(connection, workspace_id, str(args.monitor))
        if not monitor or monitor.get("status") != "active":
            raise ValueError("Metric Monitor run requires an active definition in the current workspace.")
        previous_count = int(connection.execute(
            "SELECT COUNT(*) FROM metric_monitor_evaluations WHERE workspace_id = ? AND monitor_key = ?",
            (workspace_id, monitor["monitorKey"]),
        ).fetchone()[0])
        baseline = get_analysis_snapshot(connection, workspace_id, str(monitor["baselineSnapshotKey"]), include_content=True)
        _, baseline_blockers = _snapshot_integrity(connection, workspace_id, baseline, require_current=False)
        current_key = str(getattr(args, "snapshot", "") or "").strip()
        if previous_count == 0:
            current_key = str(monitor["baselineSnapshotKey"])
        elif not current_key:
            raise ValueError("Subsequent Metric Monitor runs require --snapshot for the current compatible Snapshot.")
        current = get_analysis_snapshot(connection, workspace_id, current_key, include_content=True)
        _, current_blockers = _snapshot_integrity(connection, workspace_id, current, require_current=previous_count > 0)
        blockers = [*baseline_blockers, *current_blockers]
        baseline_value: float | None = None
        current_value: float | None = None
        metric = str(monitor["metric"])
        if baseline:
            baseline_metric, baseline_value, metric_blockers = _metric_value(baseline, metric)
            blockers.extend(metric_blockers)
            if baseline_metric != metric:
                blockers.append("metric-monitor-baseline-metric-drifted")
        if current:
            current_metric, current_value, metric_blockers = _metric_value(current, metric)
            blockers.extend(metric_blockers)
            if current_metric != metric:
                blockers.append("metric-monitor-current-metric-drifted")
        if baseline and current and previous_count > 0:
            blockers.extend(_compatibility_blockers(baseline, current))
        absolute_change = None if baseline_value is None or current_value is None else current_value - baseline_value
        percent_change = None
        if absolute_change is not None:
            if baseline_value == 0:
                if monitor["comparisonStrategy"] == "percent-change":
                    blockers.append("metric-monitor-percent-baseline-is-zero")
            else:
                percent_change = absolute_change / abs(baseline_value) * 100.0
        blockers = list(dict.fromkeys(str(item) for item in blockers if str(item).strip()))
        threshold = monitor["threshold"]
        score = _score(str(monitor["comparisonStrategy"]), str(monitor["direction"]), absolute_change or 0.0, percent_change)
        if blockers:
            status = "blocked"
        elif previous_count == 0:
            status = "baseline"
        elif threshold is None:
            status = "normal"
        elif score is not None and score >= threshold:
            status = "breached"
        elif score is not None and score >= threshold * float(monitor["warningRatio"]):
            status = "warning"
        else:
            status = "normal"
        sequence = previous_count + 1
        trace = {
            "schema": METRIC_MONITOR_TRACE_SCHEMA,
            "capabilityVersion": monitor["capabilityVersion"],
            "monitorKey": monitor["monitorKey"],
            "sequence": sequence,
            "definitionFingerprint": monitor["definitionFingerprint"],
            "baseline": {
                "snapshotKey": monitor["baselineSnapshotKey"],
                "semanticFingerprint": baseline.get("semanticFingerprint") if baseline else None,
                "contentHash": baseline.get("contentHash") if baseline else None,
            },
            "current": {
                "snapshotKey": current_key,
                "semanticFingerprint": current.get("semanticFingerprint") if current else None,
                "contentHash": current.get("contentHash") if current else None,
            },
            "comparison": {
                "strategy": monitor["comparisonStrategy"],
                "direction": monitor["direction"],
                "threshold": threshold,
                "thresholdSource": monitor["thresholdSource"],
                "warningRatio": monitor["warningRatio"],
                "score": score,
            },
            "status": status,
            "blockers": blockers,
            "notificationsSent": 0,
            "businessSystemWrites": 0,
            "providerUsed": False,
        }
        trace_fingerprint = _fingerprint(trace)
        evaluation_key = f"metric_evaluation_{_fingerprint({'monitor': monitor['monitorKey'], 'sequence': sequence, 'trace': trace_fingerprint})[:20]}"
        timestamp = now_iso()
        connection.execute(
            """
            INSERT INTO metric_monitor_evaluations(
              evaluation_key, workspace_id, monitor_key, evaluation_sequence, status,
              baseline_snapshot_key, current_snapshot_key, baseline_value, current_value,
              absolute_change, percent_change, threshold_value, threshold_source,
              blockers_json, trace_json, trace_fingerprint, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evaluation_key, workspace_id, monitor["monitorKey"], sequence, status,
                monitor["baselineSnapshotKey"], current_key, baseline_value, current_value,
                absolute_change, percent_change, threshold, monitor["thresholdSource"],
                _json(blockers), _json(trace), trace_fingerprint, timestamp,
            ),
        )
        connection.execute(
            """
            UPDATE metric_monitors
            SET latest_snapshot_key = ?, latest_evaluation_key = ?, latest_status = ?, updated_at = ?
            WHERE workspace_id = ? AND monitor_key = ?
            """,
            (current_key, evaluation_key, status, timestamp, workspace_id, monitor["monitorKey"]),
        )
        connection.commit()
        row = connection.execute(
            "SELECT * FROM metric_monitor_evaluations WHERE workspace_id = ? AND evaluation_key = ?",
            (workspace_id, evaluation_key),
        ).fetchone()
        evaluation = _evaluation_row(row)
        return {
            "ok": True,
            "workspaceId": workspace_id,
            "writesEvidence": True,
            "writesBusinessState": False,
            "metricMonitor": get_metric_monitor(connection, workspace_id, monitor["monitorKey"]),
            "metricMonitorEvaluation": evaluation,
            "evidence": [
                {"type": "metricMonitorTrace", "traceFingerprint": trace_fingerprint, "evaluationKey": evaluation_key},
                {"type": "analysisSnapshot", "snapshotKey": monitor["baselineSnapshotKey"], "role": "baseline"},
                {"type": "analysisSnapshot", "snapshotKey": current_key, "role": "current"},
            ],
            "nextAction": "Inspect blockers and create a compatible current Snapshot." if status == "blocked" else "Review the local evidence trace; no notification or business action was sent.",
        }


def metric_monitors_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with closing(open_db()) as connection:
        workspace_id = active_workspace_id(connection)
        monitor_key = str(getattr(args, "monitor", "") or "").strip()
        requested_limit = max(1, min(int(getattr(args, "limit", 30) or 30), 100))
        if monitor_key:
            monitor = get_metric_monitor(connection, workspace_id, monitor_key)
            if not monitor:
                raise ValueError("Unknown Metric Monitor in the active workspace.")
            rows = connection.execute(
                "SELECT * FROM metric_monitor_evaluations WHERE workspace_id = ? AND monitor_key = ? ORDER BY evaluation_sequence DESC LIMIT ?",
                (workspace_id, monitor_key, requested_limit),
            ).fetchall()
            return {"ok": True, "workspaceId": workspace_id, "metricMonitor": monitor, "metricMonitorEvaluations": [_evaluation_row(row) for row in rows]}
        status = str(getattr(args, "status", "") or "").strip()
        params: list[Any] = [workspace_id]
        where = "workspace_id = ?"
        if status:
            where += " AND status = ?"
            params.append(status)
        params.append(requested_limit)
        rows = connection.execute(
            f"SELECT * FROM metric_monitors WHERE {where} ORDER BY created_at DESC LIMIT ?",
            tuple(params),
        ).fetchall()
        return {
            "ok": True,
            "schema": "aibi-metric-monitors/v1",
            "workspaceId": workspace_id,
            "metricMonitors": [_monitor_row(row) for row in rows],
            "count": len(rows),
            "notificationsSent": 0,
            "businessSystemWrites": 0,
            "backgroundSchedulerEnabled": False,
        }
