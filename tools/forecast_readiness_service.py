from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sqlite3
import statistics
from contextlib import closing
from datetime import datetime, timezone
from typing import Any, Callable

from analysis_unit_service import analysis_unit_consumer_state, get_analysis_unit


FORECAST_READINESS_SCHEMA = "aibi-forecast-readiness/v1"
POLICY_VERSION = "forecast-readiness-policy/v1"
MINIMUM_HISTORY = 24
MAX_HORIZON = 24
MAX_MISSING_INTERVAL_RATE = 0.10
MAX_INTERVAL_CV = 0.15
MIN_VALUE_COMPLETENESS = 0.98
MAX_LEVEL_SHIFT_SCORE = 3.0
MAX_EXTREME_JUMP_RATE = 0.10


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        result = float(value)
        return result if math.isfinite(result) else None
    if isinstance(value, str) and re.fullmatch(r"[-+]?\d+(?:\.\d+)?", value.strip()):
        result = float(value)
        return result if math.isfinite(result) else None
    return None


def _timestamp(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    quarter = re.fullmatch(r"(\d{4})\s*[-/]?\s*[Qq]([1-4])", text)
    if quarter:
        parsed = datetime(int(quarter.group(1)), (int(quarter.group(2)) - 1) * 3 + 1, 1)
        return parsed.replace(tzinfo=timezone.utc).timestamp()
    chinese_month = re.fullmatch(r"(\d{4})年(\d{1,2})月", text)
    if chinese_month:
        parsed = datetime(int(chinese_month.group(1)), int(chinese_month.group(2)), 1)
        return parsed.replace(tzinfo=timezone.utc).timestamp()
    candidate = text.replace("/", "-")
    if re.fullmatch(r"\d{4}-\d{1,2}", candidate):
        candidate += "-01"
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.timestamp()


def _gate(key: str, passed: bool, summary: str, *, metrics: dict[str, Any] | None = None, blockers: list[str] | None = None) -> dict[str, Any]:
    return {
        "key": key,
        "status": "passed" if passed else "blocked",
        "summary": summary,
        "metrics": metrics or {},
        "blockers": [] if passed else list(dict.fromkeys(blockers or [f"forecast-{key}-gate-failed"])),
    }


def _cadence_label(interval_days: float | None) -> str:
    if interval_days is None:
        return "unknown"
    if interval_days <= 1.5:
        return "daily"
    if interval_days <= 8.5:
        return "weekly"
    if interval_days <= 35:
        return "monthly"
    if interval_days <= 100:
        return "quarterly"
    if interval_days <= 370:
        return "yearly"
    return "irregular"


def _stability(values: list[float]) -> dict[str, float]:
    if not values:
        return {"levelShiftScore": 0.0, "extremeJumpRate": 0.0}
    segment = max(1, len(values) // 3)
    first = values[:segment]
    last = values[-segment:]
    mean = statistics.fmean(values)
    scale = max(statistics.pstdev(values), abs(mean) * 0.01, 1e-9)
    shift = abs(statistics.fmean(last) - statistics.fmean(first)) / scale
    if len(values) < 2:
        jump_rate = 0.0
    else:
        differences = [values[index] - values[index - 1] for index in range(1, len(values))]
        median_difference = statistics.median(differences)
        deviations = [abs(item - median_difference) for item in differences]
        mad = statistics.median(deviations)
        if mad <= 1e-12:
            jump_rate = 0.0
        else:
            jump_rate = sum(abs(item - median_difference) > 6 * mad for item in differences) / len(differences)
    return {"levelShiftScore": round(shift, 6), "extremeJumpRate": round(jump_rate, 6)}


def assess_forecast_readiness(
    unit: dict[str, Any],
    *,
    freshness: dict[str, Any],
    horizon: int,
    declared_cutoff: Any = None,
) -> dict[str, Any]:
    if not 1 <= int(horizon) <= MAX_HORIZON:
        raise ValueError(f"forecast horizon must be between 1 and {MAX_HORIZON}")
    horizon = int(horizon)
    shape = unit.get("shape") if isinstance(unit.get("shape"), dict) else {}
    rows = unit.get("rows") if isinstance(unit.get("rows"), list) else []
    dimension = str(shape.get("dimensionColumn") or "")
    measure = str(shape.get("measureColumn") or "")
    dimension_columns = [str(item) for item in shape.get("dimensionColumns") or [] if str(item)]

    parsed_points: list[tuple[float, float | None]] = []
    unparseable_time_count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        timestamp = _timestamp(row.get(dimension)) if dimension else None
        if timestamp is None:
            unparseable_time_count += 1
            continue
        parsed_points.append((timestamp, _number(row.get(measure)) if measure else None))
    parsed_points.sort(key=lambda item: item[0])
    timestamps = [item[0] for item in parsed_points]
    unique_timestamps = sorted(set(timestamps))
    duplicate_time_count = max(0, len(timestamps) - len(unique_timestamps))
    values = [item[1] for item in parsed_points if item[1] is not None]
    completeness = len(values) / len(parsed_points) if parsed_points else 0.0

    intervals_days = [
        (unique_timestamps[index] - unique_timestamps[index - 1]) / 86400
        for index in range(1, len(unique_timestamps))
        if unique_timestamps[index] > unique_timestamps[index - 1]
    ]
    median_interval = statistics.median(intervals_days) if intervals_days else None
    interval_cv = (
        statistics.pstdev(intervals_days) / median_interval
        if median_interval and len(intervals_days) > 1
        else 0.0 if median_interval else None
    )
    estimated_missing = 0
    if median_interval:
        estimated_missing = sum(max(0, round(interval / median_interval) - 1) for interval in intervals_days)
    missing_interval_rate = estimated_missing / (len(unique_timestamps) + estimated_missing) if unique_timestamps else 1.0
    stability = _stability([float(value) for value in values])
    single_series = len(dimension_columns) <= 1
    max_supported_horizon = min(MAX_HORIZON, max(0, len(unique_timestamps) // 4))
    cutoff_timestamp = unique_timestamps[-1] if unique_timestamps else None
    declared_cutoff_timestamp = _timestamp(declared_cutoff) if declared_cutoff not in (None, "") else None
    cutoff_tolerance_seconds = max(86400, (median_interval or 0) * 86400 * 0.5)
    cutoff_matches = declared_cutoff in (None, "") or (
        cutoff_timestamp is not None
        and declared_cutoff_timestamp is not None
        and abs(declared_cutoff_timestamp - cutoff_timestamp) <= cutoff_tolerance_seconds
    )

    source_ok = bool(freshness.get("usable")) and str(unit.get("status") or "") == "ready"
    sample_ok = len(unique_timestamps) >= MINIMUM_HISTORY and horizon <= max_supported_horizon
    cadence_ok = (
        bool(shape.get("temporalDimension"))
        and bool(dimension)
        and unparseable_time_count == 0
        and duplicate_time_count == 0
        and median_interval is not None
        and interval_cv is not None
        and interval_cv <= MAX_INTERVAL_CV
        and missing_interval_rate <= MAX_MISSING_INTERVAL_RATE
    )
    stability_ok = (
        bool(measure)
        and completeness >= MIN_VALUE_COMPLETENESS
        and stability["levelShiftScore"] <= MAX_LEVEL_SHIFT_SCORE
        and stability["extremeJumpRate"] <= MAX_EXTREME_JUMP_RATE
    )
    assumptions_ok = single_series and bool(unique_timestamps) and horizon > 0 and cutoff_matches
    leakage_ok = True
    explainability_ok = bool(values) and len(unique_timestamps) >= 2

    gates = [
        _gate("source", source_ok, "Analysis Unit and its receipt/source bindings are current.", metrics={"usable": bool(freshness.get("usable")), "unitStatus": unit.get("status")}, blockers=list(freshness.get("blockers") or ["forecast-analysis-unit-not-current"])),
        _gate("sample", sample_ok, "History and horizon stay inside the fixed evaluation budget.", metrics={"observationCount": len(unique_timestamps), "minimumHistory": MINIMUM_HISTORY, "horizon": horizon, "maxSupportedHorizon": max_supported_horizon}, blockers=["forecast-history-too-short" if len(unique_timestamps) < MINIMUM_HISTORY else "forecast-horizon-exceeds-history-budget"]),
        _gate("cadence", cadence_ok, "Time points are unique, parseable, regular, and sufficiently complete.", metrics={"cadence": _cadence_label(median_interval), "medianIntervalDays": round(median_interval, 6) if median_interval is not None else None, "intervalCv": round(interval_cv, 6) if interval_cv is not None else None, "estimatedMissingIntervals": estimated_missing, "missingIntervalRate": round(missing_interval_rate, 6), "unparseableTimeCount": unparseable_time_count, "duplicateTimeCount": duplicate_time_count}, blockers=[item for condition, item in ((not shape.get("temporalDimension"), "forecast-temporal-dimension-required"), (unparseable_time_count > 0, "forecast-time-values-unparseable"), (duplicate_time_count > 0, "forecast-duplicate-time-points"), (interval_cv is None or interval_cv > MAX_INTERVAL_CV, "forecast-cadence-irregular"), (missing_interval_rate > MAX_MISSING_INTERVAL_RATE, "forecast-time-gaps-exceed-budget")) if condition]),
        _gate("stability", stability_ok, "Value completeness, level shift, and extreme jumps stay inside conservative limits.", metrics={"valueCompleteness": round(completeness, 6), **stability, "minimumValueCompleteness": MIN_VALUE_COMPLETENESS, "maxLevelShiftScore": MAX_LEVEL_SHIFT_SCORE, "maxExtremeJumpRate": MAX_EXTREME_JUMP_RATE}, blockers=[item for condition, item in ((not measure, "forecast-numeric-measure-required"), (completeness < MIN_VALUE_COMPLETENESS, "forecast-values-incomplete"), (stability["levelShiftScore"] > MAX_LEVEL_SHIFT_SCORE, "forecast-level-shift-exceeds-budget"), (stability["extremeJumpRate"] > MAX_EXTREME_JUMP_RATE, "forecast-extreme-jumps-exceed-budget")) if condition]),
        _gate("leakage", leakage_ok, "Evaluation is restricted to target lags with rolling-origin splits and no future features.", metrics={"featurePolicy": "target-lags-only", "evaluationPolicy": "rolling-origin", "futureFeatureCount": 0}, blockers=["forecast-single-series-required"]),
        _gate("assumptions", assumptions_ok, "Single-series scope, inferred cadence, current cutoff, and horizon are explicit.", metrics={"singleSeries": single_series, "cadence": _cadence_label(median_interval), "cutoff": datetime.fromtimestamp(cutoff_timestamp, timezone.utc).date().isoformat() if cutoff_timestamp is not None else None, "cutoffSource": "explicit-business-definition" if declared_cutoff not in (None, "") else "unit-latest-point", "declaredCutoffMatches": cutoff_matches, "horizon": horizon}, blockers=[item for condition, item in ((not single_series, "forecast-single-series-required"), (not unique_timestamps, "forecast-cutoff-unavailable"), (not cutoff_matches, "forecast-declared-cutoff-not-current")) if condition]),
        _gate("explainability", explainability_ok, "A deterministic last-value baseline and lag-based diagnostics are available.", metrics={"baselines": ["last-value"] if explainability_ok else [], "explanationPolicy": "baseline-and-lag-diagnostics"}, blockers=["forecast-baseline-unavailable"]),
    ]
    blockers = list(dict.fromkeys(blocker for gate in gates for blocker in gate["blockers"]))
    status = "ready-for-evaluation" if not blockers else "blocked"
    material = {
        "schema": FORECAST_READINESS_SCHEMA,
        "policyVersion": POLICY_VERSION,
        "workspaceId": unit.get("workspaceId"),
        "unitKey": unit.get("unitKey"),
        "queryReceiptKey": unit.get("queryReceiptKey"),
        "definitionFingerprint": unit.get("definitionFingerprint"),
        "resultFingerprint": unit.get("resultFingerprint"),
        "horizon": horizon,
        "status": status,
        "gates": gates,
        "blockers": blockers,
        "canGenerateForecast": False,
        "forecastGenerated": False,
        "providerUsed": False,
        "rawBusinessRowsExposed": 0,
        "nextAction": "create-bounded-backtest-plan" if status == "ready-for-evaluation" else "repair-readiness-gaps",
    }
    return {**material, "fingerprint": _fingerprint(material)}


def forecast_readiness_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with closing(open_db()) as connection:
        workspace_id = active_workspace_id(connection)
        unit = get_analysis_unit(connection, workspace_id, str(args.unit))
        if not unit:
            raise ValueError(f"Unknown Analysis Unit in active workspace: {args.unit}")
        freshness = analysis_unit_consumer_state(connection, workspace_id, unit)
        readiness = assess_forecast_readiness(unit, freshness=freshness, horizon=int(args.horizon))
    return {
        "ok": True,
        "readyForEvaluation": readiness["status"] == "ready-for-evaluation",
        "forecastReadiness": readiness,
    }
