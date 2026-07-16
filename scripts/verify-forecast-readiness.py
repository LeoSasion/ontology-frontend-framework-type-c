from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from analytical_skill_service import builtin_analytical_skills  # noqa: E402
from business_understanding_service import build_business_understanding_frame  # noqa: E402
from forecast_readiness_service import assess_forecast_readiness  # noqa: E402


checks: list[dict[str, Any]] = []


def check(label: str, ok: bool, detail: Any = None) -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": None if ok else detail})


def run_cli(env: dict[str, str], label: str, args: list[str], expected_status: int = 0) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "tools/bi_cli.py", "--json", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    try:
        parsed = json.loads(completed.stdout.strip())
    except json.JSONDecodeError:
        parsed = None
    result = {
        "label": label,
        "ok": completed.returncode == expected_status and isinstance(parsed, dict),
        "status": completed.returncode,
        "parsed": parsed,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }
    checks.append(result)
    return result


def month_rows(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["event_date", "value", "segment"])
        writer.writeheader()
        for offset in range(36):
            year = 2023 + offset // 12
            month = offset % 12 + 1
            writer.writerow({
                "event_date": f"{year:04d}-{month:02d}-01",
                "value": 100 + offset * 2,
                "segment": "alpha" if offset % 2 == 0 else "beta",
            })


def intent_frame() -> dict[str, Any]:
    return {
        "schema": "aibi-agent-intent-frame/v1",
        "taskType": "trend",
        "decisionGoal": "判断当前序列是否满足受限预测评测前置条件",
        "measureConcepts": [{"concept": "value", "field": "value", "tableKey": "series", "role": "measure", "source": "confirmed-semantic", "confidence": 0.99}],
        "dimensionConcepts": [{"concept": "event_date", "field": "event_date", "tableKey": "series", "role": "event_time", "source": "confirmed-semantic", "confidence": 0.99}],
        "otherConcepts": [],
        "timeScope": {"expression": "截至 2025-12-01", "parts": {"end": "2025-12-01"}},
        "filters": [],
        "comparisons": [],
        "requestedOutput": "answer",
        "grainExpectation": {"fields": ["series.event_date"], "description": "monthly-series"},
        "constraints": {"readOnlyAnalysis": True},
        "unresolved": [],
        "evidenceRefs": [],
        "confidence": {},
        "resolution": {"providerRequired": False, "silentDisambiguation": False},
    }


selected_fields = [
    {"id": "series.value", "tableKey": "series", "tableName": "Series", "field": "value", "role": "measure", "confidence": 0.99, "source": "confirmed-semantic", "matchedAlias": "value"},
    {"id": "series.event_date", "tableKey": "series", "tableName": "Series", "field": "event_date", "role": "event_time", "confidence": 0.99, "source": "confirmed-semantic", "matchedAlias": "event_date"},
]
semantic_plan = {
    "schema": "aibi-semantic-query-plan/v1",
    "status": "ready",
    "fieldResolution": {"selected": selected_fields, "unresolved": []},
    "grain": {"tables": ["series"]},
    "joinPlan": {"rootTable": "series", "requiredTables": ["series"], "targets": []},
}
runtime = {
    "schema": "aibi-analytical-skill-runtime/v1",
    "fingerprint": "f" * 64,
    "enabledAnalyticalSkills": builtin_analytical_skills(),
}

incomplete = build_business_understanding_frame(
    "请检查 value 按 event_date 的预测准备度",
    intent_frame(),
    semantic_plan,
    {"terms": [], "rules": []},
    runtime,
)
check(
    "forecast-request-selects-skill-and-asks-one-high-value-question",
    incomplete.get("skillMatch", {}).get("selected", {}).get("skillId") == "forecast-readiness"
    and incomplete.get("status") == "needs-clarification"
    and incomplete.get("clarification", {}).get("askAtMostOne") is True
    and len(incomplete.get("clarification", {}).get("items") or []) >= 1
    and incomplete.get("activeClarification") == incomplete.get("clarification", {}).get("items", [None])[0],
    incomplete,
)

complete = build_business_understanding_frame(
    "检查预测准备度，预测跨度为3，评估截止为2025-12-01，指标为value，时间字段为event_date，粒度为月",
    intent_frame(),
    semantic_plan,
    {"terms": [], "rules": []},
    runtime,
)
check(
    "complete-forecast-request-produces-ready-bounded-method-plan",
    complete.get("status") == "ready"
    and complete.get("methodPlan", {}).get("skillId") == "forecast-readiness"
    and complete.get("methodPlan", {}).get("status") == "ready"
    and complete.get("methodPlan", {}).get("resolvedSlots", {}).keys() >= {"measure", "time-field", "grain", "forecast-horizon", "forecast-cutoff"},
    complete,
)

with tempfile.TemporaryDirectory(prefix="aibi-forecast-readiness-") as temp_dir:
    temp = Path(temp_dir)
    source = temp / "series.csv"
    month_rows(source)
    env = {
        **os.environ,
        "AIBI_HYBRID_DB_PATH": str(temp / "runtime.sqlite"),
        "AIBI_HYBRID_DUCKDB_PATH": str(temp / "runtime.duckdb"),
        "AIBI_EVIDENCE_BUNDLE_ROOT": str(temp / "evidence"),
        "PYTHONIOENCODING": "utf-8",
    }

    run_cli(env, "import-regular-monthly-series", ["import-commit", str(source), "--table", "series", "--name", "Series", "--mode", "create", "--yes"])
    trend = run_cli(env, "build-temporal-analysis-unit", ["query", "--table", "series", "--group", "event_date", "--measure", "value", "--agg", "sum", "--limit", "100", "--request", "value 按 event_date 的趋势折线图"])
    trend_unit = (trend.get("parsed") or {}).get("analysisUnit") or {}
    unit_key = str(trend_unit.get("unitKey") or "missing")
    check(
        "temporal-query-creates-current-trend-unit",
        trend_unit.get("kind") == "trend"
        and trend_unit.get("status") == "ready"
        and trend_unit.get("shape", {}).get("temporalDimension") is True
        and len(trend_unit.get("rows") or []) == 36,
        trend.get("parsed"),
    )

    ready = run_cli(env, "assess-ready-series", ["forecast-readiness", "--unit", unit_key, "--horizon", "3"])
    readiness = (ready.get("parsed") or {}).get("forecastReadiness") or {}
    check(
        "seven-gates-admit-bounded-evaluation-without-forecast",
        (ready.get("parsed") or {}).get("ok") is True
        and (ready.get("parsed") or {}).get("readyForEvaluation") is True
        and readiness.get("schema") == "aibi-forecast-readiness/v1"
        and readiness.get("status") == "ready-for-evaluation"
        and [gate.get("key") for gate in readiness.get("gates") or []] == ["source", "sample", "cadence", "stability", "leakage", "assumptions", "explainability"]
        and all(gate.get("status") == "passed" for gate in readiness.get("gates") or [])
        and readiness.get("canGenerateForecast") is False
        and readiness.get("forecastGenerated") is False
        and readiness.get("providerUsed") is False
        and readiness.get("rawBusinessRowsExposed") == 0
        and not ({"rows", "forecast", "predictions", "futureValues"} & readiness.keys()),
        readiness,
    )
    repeated = run_cli(env, "repeat-ready-assessment", ["forecast-readiness", "--unit", unit_key, "--horizon", "3"])
    check(
        "assessment-is-deterministic",
        (repeated.get("parsed") or {}).get("forecastReadiness", {}).get("fingerprint") == readiness.get("fingerprint"),
        repeated.get("parsed"),
    )

    agent = run_cli(env, "agent-forecast-readiness", ["ask", "检查 value 按 event_date 的预测准备度，预测跨度为3，评估截止为2025-12-01，粒度为月"])
    agent_payload = agent.get("parsed") or {}
    agent_readiness = agent_payload.get("forecastReadiness") or {}
    check(
        "agent-routes-complete-request-through-same-readiness-contract",
        agent_payload.get("businessUnderstanding", {}).get("methodPlan", {}).get("skillId") == "forecast-readiness"
        and agent_payload.get("businessUnderstanding", {}).get("methodPlan", {}).get("status") == "ready"
        and agent_payload.get("analysisUnit", {}).get("kind") == "trend"
        and agent_readiness.get("schema") == "aibi-forecast-readiness/v1"
        and agent_payload.get("answerCard", {}).get("forecastReadinessRef", {}).get("fingerprint") == agent_readiness.get("fingerprint")
        and agent_readiness.get("canGenerateForecast") is False
        and not ({"rows", "forecast", "predictions", "futureValues"} & agent_readiness.keys()),
        agent_payload,
    )

    mismatched_cutoff = assess_forecast_readiness(
        trend_unit,
        freshness={"usable": True, "blockers": []},
        horizon=3,
        declared_cutoff="2025-10-01",
    )
    assumptions_gate = next((gate for gate in mismatched_cutoff.get("gates") or [] if gate.get("key") == "assumptions"), {})
    check(
        "declared-cutoff-must-match-current-unit-boundary",
        mismatched_cutoff.get("status") == "blocked"
        and assumptions_gate.get("status") == "blocked"
        and "forecast-declared-cutoff-not-current" in (assumptions_gate.get("blockers") or [])
        and next((gate for gate in mismatched_cutoff.get("gates") or [] if gate.get("key") == "leakage"), {}).get("status") == "passed",
        mismatched_cutoff,
    )

    oversized = run_cli(env, "reject-oversized-horizon", ["forecast-readiness", "--unit", unit_key, "--horizon", "12"])
    sample_gate = next((gate for gate in ((oversized.get("parsed") or {}).get("forecastReadiness") or {}).get("gates") or [] if gate.get("key") == "sample"), {})
    check(
        "history-budget-blocks-oversized-horizon",
        (oversized.get("parsed") or {}).get("ok") is True
        and (oversized.get("parsed") or {}).get("readyForEvaluation") is False
        and sample_gate.get("status") == "blocked"
        and "forecast-horizon-exceeds-history-budget" in (sample_gate.get("blockers") or []),
        oversized.get("parsed"),
    )

    comparison = run_cli(env, "build-nontemporal-unit", ["query", "--table", "series", "--group", "segment", "--measure", "value", "--agg", "sum", "--request", "value 按 segment 比较"])
    comparison_key = str(((comparison.get("parsed") or {}).get("analysisUnit") or {}).get("unitKey") or "missing")
    non_temporal = run_cli(env, "reject-nontemporal-unit", ["forecast-readiness", "--unit", comparison_key, "--horizon", "1"])
    cadence_gate = next((gate for gate in ((non_temporal.get("parsed") or {}).get("forecastReadiness") or {}).get("gates") or [] if gate.get("key") == "cadence"), {})
    check(
        "nontemporal-unit-is-explicitly-blocked",
        cadence_gate.get("status") == "blocked"
        and "forecast-temporal-dimension-required" in (cadence_gate.get("blockers") or []),
        non_temporal.get("parsed"),
    )

    run_cli(env, "replace-source-version", ["import-commit", str(source), "--table", "series", "--name", "Series refreshed", "--mode", "replace", "--yes"])
    stale = run_cli(env, "reject-stale-unit", ["forecast-readiness", "--unit", unit_key, "--horizon", "3"])
    stale_readiness = (stale.get("parsed") or {}).get("forecastReadiness") or {}
    source_gate = next((gate for gate in stale_readiness.get("gates") or [] if gate.get("key") == "source"), {})
    check(
        "source-version-drift-blocks-readiness-without-fallback",
        stale_readiness.get("status") == "blocked"
        and source_gate.get("status") == "blocked"
        and bool(source_gate.get("blockers")),
        stale.get("parsed"),
    )

failed = [item for item in checks if not item.get("ok")]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-forecast-readiness-verify/v1",
    "checks": [{"label": item.get("label"), "ok": bool(item.get("ok")), "status": item.get("status")} for item in checks],
    "failedChecks": failed,
}, ensure_ascii=False, indent=2, default=str))
raise SystemExit(1 if failed else 0)
