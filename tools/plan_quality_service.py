from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid
from typing import Any, Callable

from agent_intent_service import build_business_intent_frame
from analytical_skill_service import builtin_analytical_skills
from bi_cli_core import ROOT
from business_understanding_service import apply_business_understanding_to_intent, build_business_understanding_frame
from semantic_query_execution import build_semantic_query_execution_plan
from semantic_query_planner import build_workspace_semantic_plan


CASE_SCHEMA = "aibi-business-expression-case/v1"
CASE_SET_SCHEMA = "aibi-business-expression-case-set/v1"
EVALUATION_SCHEMA = "aibi-plan-quality-evaluation/v1"
SCORECARD_SCHEMA = "aibi-plan-quality-scorecard/v1"
POLICY_SCHEMA = "aibi-plan-quality-policy/v1"
CASE_SET_ID = "core-business-expression-v1"
FIXTURE_WORKSPACE = "fixture-core"
OTHER_WORKSPACE = "fixture-other"

THRESHOLDS = {
    "coreSlotAccuracy": 0.95,
    "fieldBindingPrecision": 0.98,
    "safeClarificationRate": 0.90,
    "evidenceCoverage": 1.0,
    "replayConsistency": 1.0,
}
ZERO_TOLERANCE = (
    "silentDisambiguationCount",
    "permissionEscalationCount",
    "crossWorkspaceLeakCount",
    "domainPackLeakCount",
)
RUNTIME_FILES = (
    "tools/agent_intent_service.py",
    "tools/analytical_skill_service.py",
    "tools/business_understanding_service.py",
    "tools/semantic_query_planner.py",
    "tools/semantic_query_execution.py",
)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _case(
    case_id: str,
    category: str,
    zh: str,
    en: str,
    *,
    expected: dict[str, Any],
    packs: list[str] | None = None,
    fixture_variant: str = "complete",
    invariance_group: str = "",
) -> dict[str, Any]:
    payload = {
        "schema": CASE_SCHEMA,
        "caseId": case_id,
        "caseVersion": "1.0.0",
        "category": category,
        "expression": {"zh": zh, "en": en},
        "fixtureRef": "neutral-operations-v1",
        "fixtureVariant": fixture_variant,
        "domainPackScope": sorted(packs or []),
        "invarianceGroup": invariance_group or None,
        "expected": expected,
    }
    return {**payload, "fingerprint": _fingerprint(payload)}


def business_expression_cases() -> list[dict[str, Any]]:
    return [
        _case(
            "synonym-metric-zh", "synonym", "按 region 看平均能耗", "Average energy by region",
            expected={
                "planStatus": ["ready"],
                "selectedFields": ["observations.energy_kwh", "sites.region"],
                "requiredSignals": ["cross-table-request", "executable-plan"],
                "slotStates": {"measure": "resolved", "dimension": "resolved", "relationship-path": "resolved"},
                "pathHopCount": 2,
            },
        ),
        _case(
            "synonym-metric-en", "synonym", "按 region 查看 total energy", "Show total energy by region",
            expected={
                "planStatus": ["ready"],
                "selectedFields": ["observations.energy_kwh", "sites.region"],
                "requiredSignals": ["cross-table-request", "executable-plan"],
                "slotStates": {"measure": "resolved", "dimension": "resolved", "relationship-path": "resolved"},
                "pathHopCount": 2,
            },
        ),
        _case(
            "same-name-status", "same-name", "查看 status", "Show status",
            expected={
                "planStatus": ["needs-clarification"],
                "selectedFields": [],
                "unresolvedMentions": ["status"],
                "requiredSignals": ["unresolved-field"],
                "clarificationSlot": "field-binding",
                "slotStates": {"field-binding": "missing"},
            },
        ),
        _case(
            "same-name-explicit", "same-name", "按 assets.status 查看设备数", "Show distinct assets by assets.status",
            expected={
                "planStatus": ["ready"],
                "selectedFields": ["assets.asset_id", "assets.status"],
                "requiredSignals": ["executable-plan"],
                "slotStates": {"measure": "resolved", "dimension": "resolved"},
            },
        ),
        _case(
            "ratio-unverified", "ratio", "计算告警率", "Calculate alert rate",
            expected={
                "planStatus": ["not-applicable"],
                "businessStatus": "needs-clarification",
                "selectedFields": [],
                "requiredSignals": ["ratio-request"],
                "clarificationSlot": "numerator",
                "slotStates": {"numerator": "missing", "denominator": "missing"},
            },
        ),
        _case(
            "distinct-entity", "distinct-entity", "按 region 查看设备数，按 assets.asset_id 去重", "Distinct asset count by region",
            expected={
                "planStatus": ["ready"],
                "selectedFields": ["assets.asset_id", "sites.region"],
                "requiredSignals": ["distinct-count-request", "cross-table-request", "executable-plan"],
                "slotStates": {"entity-key": "resolved", "grain": "resolved", "relationship-path": "resolved"},
                "pathHopCount": 1,
            },
        ),
        _case(
            "status-filter-scope", "status", "按 assets.status 查看设备数", "Asset count grouped by asset status",
            expected={
                "planStatus": ["ready"],
                "selectedFields": ["assets.asset_id", "assets.status"],
                "requiredSignals": ["executable-plan"],
                "slotStates": {"dimension": "resolved", "measure": "resolved"},
            },
        ),
        _case(
            "time-baseline-required", "time", "按 observed_at 查看总能耗同比", "Total energy year over year by observed_at",
            expected={
                "planStatus": ["ready"],
                "businessStatus": "needs-clarification",
                "selectedFields": ["observations.energy_kwh", "observations.observed_at"],
                "requiredSignals": ["time-comparison"],
                "clarificationSlot": "time-scope",
                "slotStates": {"time-field": "resolved", "time-scope": "missing", "comparison-baseline": "missing"},
            },
        ),
        _case(
            "cross-table-two-hop", "cross-table", "按 region 查看平均温度", "Average temperature by region",
            expected={
                "planStatus": ["ready"],
                "selectedFields": ["observations.temperature", "sites.region"],
                "requiredSignals": ["cross-table-request", "executable-plan"],
                "slotStates": {"relationship-path": "resolved", "grain": "resolved"},
                "pathHopCount": 2,
            },
        ),
        _case(
            "cross-table-missing-path", "cross-table", "按 region 查看平均温度", "Average temperature by region without a path",
            fixture_variant="missing-terminal-path",
            expected={
                "planStatus": ["needs-relationship"],
                "selectedFields": ["observations.temperature", "sites.region"],
                "requiredSignals": ["cross-table-request", "relationship-ambiguity"],
                "clarificationSlot": "relationship-path",
                "slotStates": {"relationship-path": "missing"},
            },
        ),
        _case(
            "cross-table-unsafe-path", "cross-table", "按 region 查看平均温度", "Average temperature by region with an unsafe path",
            fixture_variant="unsafe-terminal-path",
            expected={
                "planStatus": ["needs-validation"],
                "selectedFields": ["observations.temperature", "sites.region"],
                "requiredSignals": ["cross-table-request"],
                "businessStatus": "needs-clarification",
                "clarificationSlot": "relationship-path",
                "slotStates": {"relationship-path": "missing"},
            },
        ),
        _case(
            "pack-neutral-core", "pack-isolation", "按 region 查看平均温度", "Average temperature by region in Core",
            packs=[], invariance_group="neutral-temperature",
            expected={
                "planStatus": ["ready"],
                "selectedFields": ["observations.temperature", "sites.region"],
                "requiredSignals": ["cross-table-request", "executable-plan"],
                "slotStates": {"measure": "resolved", "dimension": "resolved"},
                "pathHopCount": 2,
            },
        ),
        _case(
            "pack-neutral-commerce-enabled", "pack-isolation", "按 region 查看平均温度", "Average temperature by region with an unrelated pack enabled",
            packs=["platform-commerce"], invariance_group="neutral-temperature",
            expected={
                "planStatus": ["ready"],
                "selectedFields": ["observations.temperature", "sites.region"],
                "requiredSignals": ["cross-table-request", "executable-plan"],
                "slotStates": {"measure": "resolved", "dimension": "resolved"},
                "pathHopCount": 2,
            },
        ),
        _case(
            "unknown-measure-no-proxy", "unknown-field", "按 region 查看不存在指标", "Show an unknown measure by region",
            expected={
                "planStatus": ["ready"],
                "selectedFields": ["sites.region"],
                "requiredSignals": ["missing-measure"],
                "businessStatus": "needs-clarification",
                "clarificationSlot": "measure",
                "slotStates": {"measure": "missing"},
                "executionStatus": "blocked",
            },
        ),
        _case(
            "cross-workspace-field-hidden", "workspace-isolation", "查看 secret_measure", "Show a field that exists only in another workspace",
            expected={
                "planStatus": ["not-applicable"],
                "selectedFields": [],
                "requiredSignals": [],
            },
        ),
    ]


def _runtime_fingerprint() -> str:
    file_hashes = []
    for relative in RUNTIME_FILES:
        path = ROOT / relative
        file_hashes.append({"file": relative, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    skills = [
        {"skillId": item["skillId"], "version": item["version"], "fingerprint": item["fingerprint"]}
        for item in builtin_analytical_skills()
    ]
    return _fingerprint({"files": file_hashes, "skills": skills})


def _policy() -> dict[str, Any]:
    payload = {
        "schema": POLICY_SCHEMA,
        "version": 1,
        "thresholds": THRESHOLDS,
        "zeroTolerance": list(ZERO_TOLERANCE),
        "providerAllowed": False,
        "businessRowsAllowed": False,
        "writesBusinessState": False,
    }
    return {**payload, "fingerprint": _fingerprint(payload)}


def _case_set() -> dict[str, Any]:
    cases = business_expression_cases()
    material = [{"caseId": item["caseId"], "fingerprint": item["fingerprint"]} for item in cases]
    return {
        "schema": CASE_SET_SCHEMA,
        "caseSetId": CASE_SET_ID,
        "caseCount": len(cases),
        "categories": sorted({str(item["category"]) for item in cases}),
        "fingerprint": _fingerprint(material),
        "cases": cases,
    }


def _fixture_connection(variant: str) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE table_registry(workspace_id TEXT, table_key TEXT, display_name TEXT, physical_table TEXT, data_version INTEGER, schema_json TEXT NOT NULL, updated_at TEXT DEFAULT '');
        CREATE TABLE field_semantics(workspace_id TEXT, table_key TEXT, field_name TEXT, role TEXT, confidence REAL, usage TEXT DEFAULT '', tags_json TEXT DEFAULT '[]', usage_json TEXT DEFAULT '{}', source TEXT DEFAULT 'confirmed');
        CREATE TABLE metric_definitions(workspace_id TEXT, table_key TEXT, label TEXT, measure TEXT, aggregation TEXT, dimension TEXT, time_field TEXT);
        CREATE TABLE relationships(workspace_id TEXT, relation_key TEXT, left_table_key TEXT, right_table_key TEXT, left_field TEXT, right_field TEXT, mappings_json TEXT DEFAULT '[]', join_type TEXT, confidence REAL, validation_json TEXT DEFAULT '{}', filters_json TEXT DEFAULT '[]', preaggregation_json TEXT DEFAULT '{}', updated_at TEXT DEFAULT '');
        """
    )
    connection.executemany(
        "INSERT INTO table_registry(workspace_id,table_key,display_name,physical_table,data_version,schema_json) VALUES(?,?,?,?,1,?)",
        [
            (FIXTURE_WORKSPACE, "sites", "Sites", "sites", json.dumps({"fields": [
                {"name": "site_id", "type": "VARCHAR"},
                {"name": "region", "type": "VARCHAR"},
                {"name": "status", "type": "VARCHAR"},
                {"name": "opened_at", "type": "DATE"},
            ]}, sort_keys=True)),
            (FIXTURE_WORKSPACE, "assets", "Assets", "assets", json.dumps({"fields": [
                {"name": "asset_id", "type": "VARCHAR"},
                {"name": "site_id", "type": "VARCHAR"},
                {"name": "status", "type": "VARCHAR"},
                {"name": "asset_type", "type": "VARCHAR"},
            ]}, sort_keys=True)),
            (FIXTURE_WORKSPACE, "observations", "Observations", "observations", json.dumps({"fields": [
                {"name": "observation_id", "type": "VARCHAR"},
                {"name": "asset_id", "type": "VARCHAR"},
                {"name": "observed_at", "type": "DATE"},
                {"name": "energy_kwh", "type": "DOUBLE"},
                {"name": "alert_flag", "type": "BIGINT"},
                {"name": "temperature", "type": "DOUBLE"},
            ]}, sort_keys=True)),
            (OTHER_WORKSPACE, "other_private", "Other private", "other_private", json.dumps({"fields": [
                {"name": "secret_measure", "type": "DOUBLE"},
            ]}, sort_keys=True)),
        ],
    )
    semantics = [
        ("sites", "site_id", "identity_key"), ("sites", "region", "dimension"),
        ("sites", "status", "status"), ("sites", "opened_at", "event_time"),
        ("assets", "asset_id", "identity_key"), ("assets", "site_id", "identity_key"),
        ("assets", "status", "status"), ("assets", "asset_type", "dimension"),
        ("observations", "observation_id", "identity_key"), ("observations", "asset_id", "identity_key"),
        ("observations", "observed_at", "event_time"), ("observations", "energy_kwh", "measure"),
        ("observations", "alert_flag", "status"), ("observations", "temperature", "measure"),
    ]
    connection.executemany(
        "INSERT INTO field_semantics(workspace_id,table_key,field_name,role,confidence) VALUES(?,?,?,?,?)",
        [(FIXTURE_WORKSPACE, table, field, role, 0.99) for table, field, role in semantics]
        + [(OTHER_WORKSPACE, "other_private", "secret_measure", "measure", 0.99)],
    )
    connection.executemany(
        "INSERT INTO metric_definitions(workspace_id,table_key,label,measure,aggregation,dimension,time_field) VALUES(?,?,?,?,?,?,?)",
        [
            (FIXTURE_WORKSPACE, "sites", "站点数", "site_id", "count-distinct", "region", "opened_at"),
            (FIXTURE_WORKSPACE, "assets", "设备数", "asset_id", "count-distinct", "asset_type", None),
            (FIXTURE_WORKSPACE, "observations", "平均能耗", "energy_kwh", "avg", None, "observed_at"),
            (FIXTURE_WORKSPACE, "observations", "total energy", "energy_kwh", "sum", None, "observed_at"),
            (FIXTURE_WORKSPACE, "observations", "总能耗", "energy_kwh", "sum", None, "observed_at"),
            (FIXTURE_WORKSPACE, "observations", "平均温度", "temperature", "avg", None, "observed_at"),
        ],
    )
    terminal_confidence = 0.2 if variant == "unsafe-terminal-path" else 0.99
    relationships = [
        (
            FIXTURE_WORKSPACE, "sites-assets", "sites", "assets", "site_id", "site_id",
            '[{"leftField":"site_id","rightField":"site_id"}]', "inner", 0.99,
            '{"status":"validated","dataVersions":{"sites":1,"assets":1},"metrics":{"rowExpansion":1,"reverseRowExpansion":1}}',
            "[]", "{}", "2026-07-16T00:00:00Z",
        ),
    ]
    if variant != "missing-terminal-path":
        relationships.append((
            FIXTURE_WORKSPACE, "assets-observations", "assets", "observations", "asset_id", "asset_id",
            '[{"leftField":"asset_id","rightField":"asset_id"}]', "inner", terminal_confidence,
            '{"status":"validated","dataVersions":{"assets":1,"observations":1},"metrics":{"rowExpansion":1,"reverseRowExpansion":1}}',
            "[]", "{}", "2026-07-16T00:00:00Z",
        ))
    connection.executemany(
        "INSERT INTO relationships(workspace_id,relation_key,left_table_key,right_table_key,left_field,right_field,mappings_json,join_type,confidence,validation_json,filters_json,preaggregation_json,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        relationships,
    )
    return connection


def _analytical_runtime() -> dict[str, Any]:
    skills = builtin_analytical_skills()
    return {
        "schema": "aibi-analytical-skill-runtime/v1",
        "workspaceId": FIXTURE_WORKSPACE,
        "enabledAnalyticalSkills": skills,
        "fingerprint": _fingerprint([
            {"skillId": item["skillId"], "version": item["version"], "fingerprint": item["fingerprint"]}
            for item in skills
        ]),
    }


def _selected_fields(plan: dict[str, Any]) -> list[str]:
    return sorted({
        f"{item.get('tableKey')}.{item.get('field')}"
        for item in plan.get("fieldResolution", {}).get("selected", [])
        if isinstance(item, dict) and item.get("tableKey") and item.get("field")
    })


def _unresolved_mentions(plan: dict[str, Any]) -> list[str]:
    return sorted({
        str(item.get("mention") or "")
        for item in plan.get("fieldResolution", {}).get("unresolved", [])
        if isinstance(item, dict) and item.get("mention")
    })


def _path_hop_count(plan: dict[str, Any]) -> int:
    targets = plan.get("joinPlan", {}).get("targets", [])
    selected = [item.get("selectedPath") for item in targets if isinstance(item, dict) and isinstance(item.get("selectedPath"), dict)]
    return max((len(item.get("hops") or []) for item in selected), default=0)


def _planning_snapshot(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "semanticPlan": result["semanticPlan"],
        "intentFrame": result["intentFrame"],
        "businessUnderstanding": result["businessUnderstanding"],
        "executionPlan": result["executionPlan"],
    }


def _invariance_snapshot(result: dict[str, Any]) -> dict[str, Any]:
    understanding = result["businessUnderstanding"]
    intent = result["intentFrame"]
    return {
        "semanticPlan": result["semanticPlan"],
        "intent": {
            key: intent.get(key)
            for key in ("taskType", "measureConcepts", "dimensionConcepts", "otherConcepts", "timeScope", "filters", "comparisons", "grainExpectation", "unresolved")
        },
        "businessUnderstanding": {
            key: understanding.get(key)
            for key in ("status", "signals", "slots", "missingSlots", "activeClarification", "guards", "requiredEvidence")
        },
        "executionPlan": result["executionPlan"],
    }


def _run_pipeline(case: dict[str, Any]) -> dict[str, Any]:
    connection = _fixture_connection(str(case.get("fixtureVariant") or "complete"))
    try:
        expression = str(case["expression"]["zh"])
        semantic_plan = build_workspace_semantic_plan(connection, FIXTURE_WORKSPACE, expression)
        intent_frame = build_business_intent_frame(expression, semantic_plan=semantic_plan)
        business_understanding = build_business_understanding_frame(
            expression,
            intent_frame,
            semantic_plan,
            {"terms": [], "rules": []},
            _analytical_runtime(),
            enabled_domain_packs=list(case.get("domainPackScope") or []),
        )
        enriched_intent = apply_business_understanding_to_intent(intent_frame, business_understanding)
        execution_plan = build_semantic_query_execution_plan(semantic_plan, intent_frame=enriched_intent)
        return {
            "semanticPlan": semantic_plan,
            "intentFrame": enriched_intent,
            "businessUnderstanding": business_understanding,
            "executionPlan": execution_plan,
            "selectedFields": _selected_fields(semantic_plan),
            "unresolvedMentions": _unresolved_mentions(semantic_plan),
            "pathHopCount": _path_hop_count(semantic_plan),
        }
    finally:
        connection.close()


def _slot_state(understanding: dict[str, Any], slot: str) -> str:
    value = understanding.get("slots", {}).get(slot)
    if isinstance(value, dict) and value.get("status") == "resolved":
        return "resolved"
    if slot in set(understanding.get("missingSlots") or []):
        return "missing"
    return "absent"


def _field_evidence_coverage(result: dict[str, Any], expected_fields: set[str]) -> tuple[int, int]:
    if not expected_fields:
        return 0, 0
    evidence = {
        f"{item.get('tableKey')}.{item.get('field')}"
        for item in result["businessUnderstanding"].get("evidenceRefs", [])
        if isinstance(item, dict) and item.get("tableKey") and item.get("field")
    }
    selected = set(result["selectedFields"])
    covered = len(expected_fields.intersection(selected).intersection(evidence))
    return covered, len(expected_fields)


def _evaluate_case(case: dict[str, Any]) -> dict[str, Any]:
    expected = dict(case.get("expected") or {})
    try:
        first = _run_pipeline(case)
        second = _run_pipeline(case)
        replay_matches = _fingerprint(_planning_snapshot(first)) == _fingerprint(_planning_snapshot(second))
        selected = set(first["selectedFields"])
        expected_fields = set(expected.get("selectedFields") or [])
        checks: dict[str, bool] = {
            "planStatus": str(first["semanticPlan"].get("status")) in set(expected.get("planStatus") or []),
            "fieldBindings": selected == expected_fields,
            "unresolvedMentions": set(expected.get("unresolvedMentions") or []).issubset(set(first["unresolvedMentions"])),
            "businessSignals": set(expected.get("requiredSignals") or []).issubset(set(first["businessUnderstanding"].get("signals") or [])),
            "replayConsistency": replay_matches,
            "semanticPlanCannotAutoExecute": first["semanticPlan"].get("autoExecutable") is False,
            "providerNotRequired": first["intentFrame"].get("resolution", {}).get("providerRequired") is False,
            "workspaceIsolation": all(item.split(".", 1)[0] in {"sites", "assets", "observations"} for item in selected),
            "domainPackScope": sorted(first["businessUnderstanding"].get("skillMatch", {}).get("enabledDomainPacks") or []) == sorted(case.get("domainPackScope") or []),
        }
        if expected.get("businessStatus"):
            checks["businessStatus"] = first["businessUnderstanding"].get("status") == expected["businessStatus"]
        if expected.get("clarificationSlot"):
            active = first["businessUnderstanding"].get("activeClarification") or {}
            checks["safeClarification"] = (
                active.get("slot") == expected["clarificationSlot"]
                and first["businessUnderstanding"].get("clarification", {}).get("askAtMostOne") is True
            )
        if "pathHopCount" in expected:
            checks["pathHopCount"] = first["pathHopCount"] == int(expected["pathHopCount"])
        if expected.get("executionStatus"):
            checks["executionStatus"] = first["executionPlan"].get("status") == expected["executionStatus"]
        slot_checks = {
            slot: _slot_state(first["businessUnderstanding"], slot) == state
            for slot, state in dict(expected.get("slotStates") or {}).items()
        }
        checks.update({f"slot:{slot}": value for slot, value in slot_checks.items()})
        evidence_covered, evidence_total = _field_evidence_coverage(first, expected_fields)
        checks["evidenceCoverage"] = evidence_covered == evidence_total
        silent_disambiguation = int(
            bool(expected.get("unresolvedMentions"))
            and first["semanticPlan"].get("status") == "ready"
        )
        permission_escalation = int(
            first["semanticPlan"].get("autoExecutable") is not False
            or first["intentFrame"].get("resolution", {}).get("providerRequired") is not False
        )
        workspace_leak = int(not checks["workspaceIsolation"])
        pack_leak = int(not checks["domainPackScope"])
        return {
            "caseId": case["caseId"],
            "caseFingerprint": case["fingerprint"],
            "category": case["category"],
            "domainPackScope": case.get("domainPackScope") or [],
            "status": "passed" if all(checks.values()) else "failed",
            "planStatus": first["semanticPlan"].get("status"),
            "businessStatus": first["businessUnderstanding"].get("status"),
            "executionStatus": first["executionPlan"].get("status"),
            "selectedFields": first["selectedFields"],
            "activeClarificationSlot": (first["businessUnderstanding"].get("activeClarification") or {}).get("slot"),
            "checks": checks,
            "counts": {
                "slotCorrect": sum(1 for value in slot_checks.values() if value),
                "slotTotal": len(slot_checks),
                "fieldCorrect": len(selected.intersection(expected_fields)),
                "fieldTotal": max(len(selected), len(expected_fields)) if (selected or expected_fields) else 0,
                "evidenceCovered": evidence_covered,
                "evidenceTotal": evidence_total,
                "clarificationCorrect": int(checks.get("safeClarification", False)),
                "clarificationTotal": int(bool(expected.get("clarificationSlot"))),
                "replayCorrect": int(replay_matches),
                "replayTotal": 1,
                "silentDisambiguationCount": silent_disambiguation,
                "permissionEscalationCount": permission_escalation,
                "crossWorkspaceLeakCount": workspace_leak,
                "domainPackLeakCount": pack_leak,
            },
            "planningFingerprint": _fingerprint(_planning_snapshot(first)),
            "invarianceFingerprint": _fingerprint(_invariance_snapshot(first)),
            "error": None,
        }
    except Exception as error:  # The scorecard must retain terminal failure evidence.
        return {
            "caseId": case["caseId"],
            "caseFingerprint": case["fingerprint"],
            "category": case["category"],
            "domainPackScope": case.get("domainPackScope") or [],
            "status": "failed",
            "planStatus": "failed",
            "businessStatus": "failed",
            "executionStatus": "failed",
            "selectedFields": [],
            "activeClarificationSlot": None,
            "checks": {"pipelineCompleted": False},
            "counts": {
                "slotCorrect": 0,
                "slotTotal": len(dict(case.get("expected", {}).get("slotStates") or {})),
                "fieldCorrect": 0,
                "fieldTotal": len(case.get("expected", {}).get("selectedFields") or []),
                "evidenceCovered": 0,
                "evidenceTotal": len(case.get("expected", {}).get("selectedFields") or []),
                "clarificationCorrect": 0,
                "clarificationTotal": int(bool(case.get("expected", {}).get("clarificationSlot"))),
                "replayCorrect": 0,
                "replayTotal": 1,
                "silentDisambiguationCount": 0,
                "permissionEscalationCount": 0,
                "crossWorkspaceLeakCount": 0,
                "domainPackLeakCount": 0,
            },
            "planningFingerprint": "",
            "invarianceFingerprint": "",
            "error": f"{error.__class__.__name__}: {str(error)[:320]}",
        }


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 4) if denominator else 1.0


def evaluate_plan_quality() -> dict[str, Any]:
    case_set = _case_set()
    policy = _policy()
    results = [_evaluate_case(case) for case in case_set["cases"]]
    totals = {
        key: sum(int(item["counts"].get(key) or 0) for item in results)
        for key in {
            "slotCorrect", "slotTotal", "fieldCorrect", "fieldTotal", "evidenceCovered", "evidenceTotal",
            "clarificationCorrect", "clarificationTotal", "replayCorrect", "replayTotal", *ZERO_TOLERANCE,
        }
    }
    metrics = {
        "coreSlotAccuracy": _ratio(totals["slotCorrect"], totals["slotTotal"]),
        "fieldBindingPrecision": _ratio(totals["fieldCorrect"], totals["fieldTotal"]),
        "safeClarificationRate": _ratio(totals["clarificationCorrect"], totals["clarificationTotal"]),
        "evidenceCoverage": _ratio(totals["evidenceCovered"], totals["evidenceTotal"]),
        "replayConsistency": _ratio(totals["replayCorrect"], totals["replayTotal"]),
        **{key: totals[key] for key in ZERO_TOLERANCE},
        "casePassRate": _ratio(sum(1 for item in results if item["status"] == "passed"), len(results)),
    }
    threshold_checks = {key: float(metrics[key]) >= threshold for key, threshold in THRESHOLDS.items()}
    zero_checks = {key: int(metrics[key]) == 0 for key in ZERO_TOLERANCE}
    invariance_checks: dict[str, bool] = {}
    groups = sorted({str(case.get("invarianceGroup")) for case in case_set["cases"] if case.get("invarianceGroup")})
    for group in groups:
        group_ids = {case["caseId"] for case in case_set["cases"] if case.get("invarianceGroup") == group}
        fingerprints = {item["invarianceFingerprint"] for item in results if item["caseId"] in group_ids}
        invariance_checks[group] = len(fingerprints) == 1 and "" not in fingerprints
    release_ready = all(threshold_checks.values()) and all(zero_checks.values()) and all(invariance_checks.values()) and all(item["status"] == "passed" for item in results)
    runtime_fingerprint = _runtime_fingerprint()
    scorecard_material = {
        "schema": SCORECARD_SCHEMA,
        "caseSetId": case_set["caseSetId"],
        "caseSetFingerprint": case_set["fingerprint"],
        "policyFingerprint": policy["fingerprint"],
        "runtimeFingerprint": runtime_fingerprint,
        "metrics": metrics,
        "thresholdChecks": threshold_checks,
        "zeroToleranceChecks": zero_checks,
        "invarianceChecks": invariance_checks,
        "releaseReady": release_ready,
        "caseResults": results,
    }
    return {
        "schema": EVALUATION_SCHEMA,
        "status": "passed" if release_ready else "failed",
        "deterministicAuthority": True,
        "providerUsed": False,
        "businessRowsRead": 0,
        "businessStateWrites": 0,
        "caseSet": {key: case_set[key] for key in ("schema", "caseSetId", "caseCount", "categories", "fingerprint")},
        "policy": policy,
        "scorecard": {**scorecard_material, "fingerprint": _fingerprint(scorecard_material)},
    }


def business_expression_cases_command(_args: argparse.Namespace) -> dict[str, Any]:
    case_set = _case_set()
    return {"ok": True, **case_set, "bounded": True, "executableContentAllowed": False}


def _workspace_id(connection: sqlite3.Connection, args: argparse.Namespace, active_workspace_id: Callable[[sqlite3.Connection], str]) -> str:
    requested = str(getattr(args, "workspace", "") or "").strip()
    workspace_id = requested or active_workspace_id(connection)
    exists = connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
    if not exists:
        raise ValueError(f"Unknown workspace: {workspace_id}")
    return workspace_id


def plan_quality_evaluate_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    evaluation = evaluate_plan_quality()
    with open_db() as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        scorecard_key = f"plan_quality_{uuid.uuid4().hex[:20]}"
        created_at = now_iso()
        scorecard = {
            **evaluation["scorecard"],
            "scorecardKey": scorecard_key,
            "workspaceId": workspace_id,
            "status": evaluation["status"],
            "createdAt": created_at,
        }
        connection.execute(
            """
            INSERT INTO plan_quality_scorecards(
              scorecard_key, workspace_id, status, case_set_id, case_set_fingerprint,
              policy_fingerprint, runtime_fingerprint, scorecard_json, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scorecard_key, workspace_id, evaluation["status"], evaluation["caseSet"]["caseSetId"],
                evaluation["caseSet"]["fingerprint"], evaluation["policy"]["fingerprint"],
                evaluation["scorecard"]["runtimeFingerprint"], _canonical(scorecard), created_at,
            ),
        )
        connection.commit()
    return {
        "ok": True,
        "schema": EVALUATION_SCHEMA,
        "workspaceId": workspace_id,
        "status": evaluation["status"],
        "deterministicAuthority": True,
        "providerUsed": False,
        "businessRowsRead": 0,
        "businessStateWrites": 0,
        "scorecard": scorecard,
    }


def plan_quality_scorecards_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    current = {
        "caseSetFingerprint": _case_set()["fingerprint"],
        "policyFingerprint": _policy()["fingerprint"],
        "runtimeFingerprint": _runtime_fingerprint(),
    }
    with open_db() as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        limit = max(1, min(int(getattr(args, "limit", 20) or 20), 100))
        rows = connection.execute(
            "SELECT * FROM plan_quality_scorecards WHERE workspace_id = ? ORDER BY created_at DESC, scorecard_key DESC LIMIT ?",
            (workspace_id, limit),
        ).fetchall()
    scorecards = []
    for row in rows:
        item = json.loads(str(row["scorecard_json"] or "{}"))
        mismatches = [
            key for key, value in current.items()
            if str(row[{"caseSetFingerprint": "case_set_fingerprint", "policyFingerprint": "policy_fingerprint", "runtimeFingerprint": "runtime_fingerprint"}[key]]) != value
        ]
        is_current = not mismatches
        scorecards.append({
            **item,
            "current": is_current,
            "usableForRelease": bool(is_current and row["status"] == "passed" and item.get("releaseReady") is True),
            "freshness": {"status": "current" if is_current else "stale", "mismatches": mismatches, "current": current},
        })
    return {
        "ok": True,
        "schema": "aibi-plan-quality-scorecard-collection/v1",
        "workspaceId": workspace_id,
        "count": len(scorecards),
        "currentBindings": current,
        "scorecards": scorecards,
        "latestCurrent": next((item for item in scorecards if item["current"]), None),
    }
