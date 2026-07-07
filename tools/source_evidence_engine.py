from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from evidence_profile_runtime.domain_pack_runtime import (
    DEFAULT_DOMAIN_PACK_RUNTIME,
    SOURCE_PIPELINE_CONTRACT,
    load_domain_pack_runtime,
)
from evidence_profile_runtime.file_readers import discover_source_files, read_source_tables
from evidence_profile_runtime.semantic_text import (
    DIMENSION_SEMANTICS,
    IDENTITY_SEMANTICS,
    MEASURE_SEMANTICS,
    TIME_SEMANTICS,
    infer_semantic,
    normalize_identity_value,
    normalized_key,
    semantic_role,
    token_overlap_score,
)
from evidence_profile_runtime.sql_helpers import json_ready, quote_ident
from evidence_profile_runtime.value_inference import datetime_series, infer_sensitivity, numeric_series, value_profile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "validation" / "source-intelligence"

OUTPUTS = {
    "sourceProfile": "source-profile-generic.json",
    "semanticFieldCandidates": "semantic-field-candidates.json",
    "relationshipDiscovery": "relationship-discovery.json",
    "dataGapDiagnostics": "data-gap-diagnostics.json",
    "metricSqlCompiler": "metric-sql-compiler.json",
    "metricQueryResults": "metric-query-results.json",
    "sourceReadinessDiagnostics": "source-readiness-diagnostics.json",
    "analysisRequirementCatalog": "analysis-requirement-catalog.json",
    "sourceQualityDiagnostics": "source-quality-diagnostics.json",
    "semanticConfirmationDraft": "semantic-confirmation-draft.json",
    "relationshipCoverageMatrix": "relationship-coverage-matrix.json",
    "userConfirmations": "source-user-confirmations.json",
}


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path.resolve())


def timed(stage_timings: dict[str, int], name: str, callback: Callable[[], Any]) -> Any:
    started = time.perf_counter()
    value = callback()
    stage_timings[name] = int((time.perf_counter() - started) * 1000)
    return value


def table_public_payload(table: dict[str, Any], fields: list[dict[str, Any]]) -> dict[str, Any]:
    frame: pd.DataFrame = table["frame"]
    return {
        "tableKey": table["tableKey"],
        "label": table["tableLabel"],
        "sourcePath": table["sourcePath"],
        "sheetName": table.get("sheetName"),
        "reader": table.get("reader"),
        "sha256": table.get("sha256"),
        "rowCount": int(len(frame)),
        "columnCount": int(len(frame.columns)),
        "fields": [
            {
                "fieldName": field["fieldName"],
                "semantic": field["semantic"],
                "role": field["role"],
                "usage": field["usage"],
                "type": field["type"],
                "confidence": field["confidence"],
                "samples": field["samples"][:5],
            }
            for field in fields
        ],
    }


def profile_tables(tables: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    table_profiles: list[dict[str, Any]] = []
    field_candidates: list[dict[str, Any]] = []
    for table in tables:
        frame: pd.DataFrame = table["frame"]
        table_fields: list[dict[str, Any]] = []
        for column in frame.columns:
            series = frame[column]
            stats = value_profile(series)
            semantic, confidence, reason = infer_semantic(str(column), str(table["tableLabel"]))
            role, usage = semantic_role(semantic, str(stats["type"]), float(stats["uniqueRatio"]))
            field = {
                "tableKey": table["tableKey"],
                "tableLabel": table["tableLabel"],
                "sourcePath": table["sourcePath"],
                "sheetName": table.get("sheetName"),
                "fieldName": str(column),
                "normalizedName": normalized_key(column),
                "semantic": semantic,
                "confidence": confidence,
                "reason": reason,
                "role": role,
                "usage": usage,
                "type": stats["type"],
                "rowCount": stats["rowCount"],
                "nonNullCount": stats["nonNullCount"],
                "nullRate": stats["nullRate"],
                "uniqueCount": stats["uniqueCount"],
                "uniqueRatio": stats["uniqueRatio"],
                "samples": stats["samples"],
                "stats": stats,
                "sensitivity": infer_sensitivity(str(column), stats["samples"]),
                "status": "needs-confirmation" if confidence < 0.82 else "suggested",
            }
            table_fields.append(field)
            field_candidates.append(field)
        table_profiles.append(table_public_payload(table, table_fields))
    return table_profiles, field_candidates


def field_values(table: dict[str, Any], field_name: str, limit: int = 400) -> set[str]:
    frame: pd.DataFrame = table["frame"]
    if field_name not in frame.columns:
        return set()
    values: set[str] = set()
    for value in frame[field_name].dropna().head(limit):
        normalized = normalize_identity_value(value)
        if normalized:
            values.add(normalized)
    return values


def discover_relationships(tables: list[dict[str, Any]], fields: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tables_by_key = {table["tableKey"]: table for table in tables}
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for field in fields:
        semantic = str(field["semantic"])
        normalized = str(field["normalizedName"])
        if semantic in IDENTITY_SEMANTICS:
            groups[f"semantic:{semantic}"].append(field)
        if any(token in normalized for token in ["id", "key", "no", "code", "号", "单", "编码"]):
            groups[f"name:{normalized}"].append(field)

    relationships: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for group_key, group_fields in groups.items():
        ordered = sorted(group_fields, key=lambda item: (item["tableKey"], item["fieldName"]))
        for left_index, left in enumerate(ordered):
            for right in ordered[left_index + 1 :]:
                if left["tableKey"] == right["tableKey"]:
                    continue
                key_tuple = (left["tableKey"], left["fieldName"], right["tableKey"], right["fieldName"])
                reverse_tuple = (right["tableKey"], right["fieldName"], left["tableKey"], left["fieldName"])
                if key_tuple in seen or reverse_tuple in seen:
                    continue
                seen.add(key_tuple)
                left_values = field_values(tables_by_key[left["tableKey"]], left["fieldName"])
                right_values = field_values(tables_by_key[right["tableKey"]], right["fieldName"])
                overlap = left_values & right_values
                left_coverage = len(overlap) / max(1, len(left_values))
                right_coverage = len(overlap) / max(1, len(right_values))
                name_score = token_overlap_score(left["fieldName"], right["fieldName"])
                semantic_match = left["semantic"] == right["semantic"] and not str(left["semantic"]).startswith("field_")
                confidence = max(left_coverage, right_coverage, name_score, 0.62 if semantic_match else 0.0)
                if confidence < 0.32:
                    continue
                relation_key = normalized_key(f"{left['tableKey']}_{right['tableKey']}_{left['fieldName']}_{right['fieldName']}")
                relationships.append(
                    {
                        "relationKey": relation_key,
                        "left": {"tableKey": left["tableKey"], "fieldName": left["fieldName"], "semantic": left["semantic"]},
                        "right": {"tableKey": right["tableKey"], "fieldName": right["fieldName"], "semantic": right["semantic"]},
                        "semantic": left["semantic"] if semantic_match else group_key.split(":", 1)[-1],
                        "confidence": round(min(0.99, confidence), 3),
                        "overlapCount": len(overlap),
                        "leftCoverage": round(left_coverage, 4),
                        "rightCoverage": round(right_coverage, 4),
                        "reason": f"{group_key}; sample overlap={len(overlap)}",
                        "status": "suggested" if confidence >= 0.72 else "needs-confirmation",
                    }
                )
    if not relationships and len(tables) > 1:
        fields_by_table = fields_for_table(fields)
        table_keys = [table["tableKey"] for table in tables]
        for left_key, right_key in zip(table_keys, table_keys[1:]):
            left_options = fields_by_table.get(left_key, [])
            right_options = fields_by_table.get(right_key, [])
            left = first_field(left_options, IDENTITY_SEMANTICS, None) or first_field(left_options, DIMENSION_SEMANTICS, None) or (left_options[0] if left_options else None)
            right = first_field(right_options, IDENTITY_SEMANTICS, None) or first_field(right_options, DIMENSION_SEMANTICS, None) or (right_options[0] if right_options else None)
            if not left or not right:
                continue
            relationships.append(
                {
                    "relationKey": normalized_key(f"{left_key}_{right_key}_review_link"),
                    "left": {"tableKey": left["tableKey"], "fieldName": left["fieldName"], "semantic": left["semantic"]},
                    "right": {"tableKey": right["tableKey"], "fieldName": right["fieldName"], "semantic": right["semantic"]},
                    "semantic": "review_required",
                    "confidence": 0.34,
                    "overlapCount": 0,
                    "leftCoverage": 0.0,
                    "rightCoverage": 0.0,
                    "reason": "fallback candidate so reviewers can inspect cross-table grain; not executable without confirmation",
                    "status": "needs-confirmation",
                }
            )
    return sorted(relationships, key=lambda item: (-item["confidence"], item["relationKey"]))[:800]


def first_field(fields: list[dict[str, Any]], semantics: set[str] | None = None, role: str | None = None) -> dict[str, Any] | None:
    for field in fields:
        if semantics and field["semantic"] not in semantics:
            continue
        if role and field["role"] != role:
            continue
        return field
    return None


def fields_for_table(fields: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for field in fields:
        grouped[field["tableKey"]].append(field)
    return grouped


def build_executable_plan(plan_id: str, label: str, table: dict[str, Any], *, operation: str, fields: dict[str, str], required: list[str]) -> dict[str, Any]:
    table_key = table["tableKey"]
    select_hint = ", ".join(quote_ident(value) for value in fields.values())
    return {
        "analysisId": plan_id,
        "label": label,
        "tableKey": table_key,
        "sourceMode": "real_sample",
        "requiredSemantics": required,
        "missingSemantics": [],
        "missingRealSemantics": [],
        "weakOrMissingRelationships": [],
        "executable": True,
        "status": "planned",
        "operation": operation,
        "fields": fields,
        "sql": f"-- generated evidence query\nSELECT {select_hint or '*'} FROM {quote_ident(table_key)}",
        "agentInstruction": "Executable evidence query generated from detected field semantics.",
    }


def blocked_plan(plan_id: str, label: str, required: list[str], available: set[str]) -> dict[str, Any]:
    missing = [semantic for semantic in required if semantic not in available]
    return {
        "analysisId": plan_id,
        "label": label,
        "tableKey": None,
        "sourceMode": "blocked_until_confirmed",
        "requiredSemantics": required,
        "missingSemantics": missing or ["verified_relationship"],
        "missingRealSemantics": missing,
        "weakOrMissingRelationships": ["cross_table_grain_confirmation"],
        "executable": False,
        "status": "blocked",
        "operation": "blocked",
        "fields": {},
        "sql": "",
        "agentInstruction": "Keep this analysis in evidence gaps until missing semantics and join grain are confirmed.",
    }


def build_metric_plans(tables: list[dict[str, Any]], fields: list[dict[str, Any]], relationships: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = fields_for_table(fields)
    plans: list[dict[str, Any]] = []
    for table in tables:
        table_key = table["tableKey"]
        local_fields = grouped.get(table_key, [])
        date_field = first_field(local_fields, TIME_SEMANTICS, None)
        measure_fields = [
            field for field in local_fields
            if field["semantic"] in MEASURE_SEMANTICS or field["role"] == "measure"
        ][:4]
        dimension_fields = [
            field for field in local_fields
            if field["semantic"] in DIMENSION_SEMANTICS or field["role"] in {"dimension", "identity"}
        ][:3]

        plans.append(build_executable_plan(
            f"{table_key}_row_count",
            f"{table['tableLabel']} 行数",
            table,
            operation="row_count",
            fields={},
            required=[],
        ))
        for measure in measure_fields:
            plans.append(build_executable_plan(
                f"{table_key}_{normalized_key(measure['fieldName'])}_total",
                f"{table['tableLabel']} {measure['fieldName']} 汇总",
                table,
                operation="sum",
                fields={"measure": measure["fieldName"]},
                required=[measure["semantic"]],
            ))
            if date_field:
                plans.append(build_executable_plan(
                    f"{table_key}_{normalized_key(measure['fieldName'])}_monthly",
                    f"{table['tableLabel']} {measure['fieldName']} 月趋势",
                    table,
                    operation="monthly_sum",
                    fields={"date": date_field["fieldName"], "measure": measure["fieldName"]},
                    required=[date_field["semantic"], measure["semantic"]],
                ))
            for dimension in dimension_fields[:2]:
                plans.append(build_executable_plan(
                    f"{table_key}_{normalized_key(dimension['fieldName'])}_{normalized_key(measure['fieldName'])}_breakdown",
                    f"{table['tableLabel']} 按{dimension['fieldName']}拆分{measure['fieldName']}",
                    table,
                    operation="breakdown_sum",
                    fields={"dimension": dimension["fieldName"], "measure": measure["fieldName"]},
                    required=[dimension["semantic"], measure["semantic"]],
                ))

    available_semantics = {str(field["semantic"]) for field in fields}
    blocked_requirements = [
        ("net_sales_reconciliation", "净销售对账", ["paid_gmv", "refund_amount", "order_id"]),
        ("gross_margin", "毛利测算", ["paid_gmv", "cost_amount", "sku"]),
        ("refund_rate", "退款率", ["paid_gmv", "refund_amount"]),
        ("inventory_turnover", "库存周转", ["inventory_qty", "paid_gmv", "sku"]),
        ("supplier_fulfillment", "供应商履约", ["supplier", "inventory_qty", "paid_at"]),
        ("cross_table_profit", "跨表利润归因", ["paid_gmv", "cost_amount", "verified_relationship"]),
    ]
    for plan_id, label, required in blocked_requirements:
        plan = blocked_plan(plan_id, label, required, available_semantics)
        if relationships and plan_id != "cross_table_profit" and not plan["missingRealSemantics"]:
            continue
        plans.append(plan)
    return plans


def execute_plan(plan: dict[str, Any], tables_by_key: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not plan.get("executable"):
        return {
            "analysisId": plan["analysisId"],
            "label": plan["label"],
            "status": "blocked",
            "sourceMode": plan.get("sourceMode"),
            "rowCount": 0,
            "rows": [],
            "reason": plan.get("agentInstruction"),
        }
    table = tables_by_key.get(str(plan.get("tableKey")))
    frame: pd.DataFrame | None = table.get("frame") if table else None
    if frame is None:
        return {"analysisId": plan["analysisId"], "label": plan["label"], "status": "failed", "sourceMode": "real_sample", "rowCount": 0, "rows": [], "error": "missing table"}
    fields = plan.get("fields") or {}
    try:
        operation = plan.get("operation")
        if operation == "row_count":
            rows = [{"table": plan.get("tableKey"), "row_count": int(len(frame))}]
        elif operation == "sum":
            measure = str(fields["measure"])
            rows = [{measure: float(numeric_series(frame[measure]).fillna(0).sum())}]
        elif operation == "monthly_sum":
            date_field = str(fields["date"])
            measure = str(fields["measure"])
            temp = pd.DataFrame({
                "business_month": datetime_series(frame[date_field]).dt.strftime("%Y-%m"),
                measure: numeric_series(frame[measure]).fillna(0),
            }).dropna(subset=["business_month"])
            grouped = temp.groupby("business_month", dropna=False)[measure].sum().reset_index().head(24)
            rows = grouped.to_dict(orient="records")
        elif operation == "breakdown_sum":
            dimension = str(fields["dimension"])
            measure = str(fields["measure"])
            temp = pd.DataFrame({
                dimension: frame[dimension].astype(str).fillna(""),
                measure: numeric_series(frame[measure]).fillna(0),
            })
            grouped = temp.groupby(dimension, dropna=False)[measure].sum().sort_values(ascending=False).reset_index().head(20)
            rows = grouped.to_dict(orient="records")
        else:
            rows = []
        return {
            "analysisId": plan["analysisId"],
            "label": plan["label"],
            "status": "executed" if rows else "empty_result",
            "sourceMode": plan.get("sourceMode"),
            "rowCount": len(rows),
            "rows": json_ready(rows),
        }
    except Exception as error:
        return {
            "analysisId": plan["analysisId"],
            "label": plan["label"],
            "status": "failed",
            "sourceMode": plan.get("sourceMode"),
            "rowCount": 0,
            "rows": [],
            "error": str(error),
        }


def execute_metric_sql(metric_plans: list[dict[str, Any]], tables: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tables_by_key = {table["tableKey"]: table for table in tables}
    return [execute_plan(plan, tables_by_key) for plan in metric_plans]


def build_data_gaps(fields: list[dict[str, Any]], relationships: list[dict[str, Any]], plans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    low_confidence = [field for field in fields if float(field["confidence"]) < 0.62][:20]
    for field in low_confidence:
        gaps.append({
            "type": "semantic_confirmation",
            "severity": "medium",
            "tableKey": field["tableKey"],
            "fieldName": field["fieldName"],
            "semantic": field["semantic"],
            "message": "Field semantic needs user confirmation before formal metrics.",
        })
    for plan in plans:
        if not plan.get("executable"):
            gaps.append({
                "type": "metric_blocked",
                "severity": "high",
                "analysisId": plan["analysisId"],
                "missingSemantics": plan.get("missingSemantics", []),
                "message": plan.get("agentInstruction"),
            })
    if not relationships:
        gaps.append({
            "type": "relationship_missing",
            "severity": "medium",
            "message": "No cross-table relationship candidate reached the evidence threshold.",
        })
    return gaps


def build_semantic_confirmation_draft(fields: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    confirmations = [
        {
            "tableKey": field["tableKey"],
            "fieldName": field["fieldName"],
            "suggestedSemantic": field["semantic"],
            "confidence": field["confidence"],
            "reason": field["reason"],
            "status": "needs-confirmation" if float(field["confidence"]) < 0.82 else "suggested",
        }
        for field in fields
    ]
    return {
        "version": 2,
        "generatedAt": generated_at,
        "summary": {
            "candidateCount": len(confirmations),
            "needsConfirmationCount": len([item for item in confirmations if item["status"] == "needs-confirmation"]),
        },
        "confirmations": confirmations,
    }


def build_relationship_coverage_matrix(relationships: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    keys = [
        {
            "relationKey": reln["relationKey"],
            "semantic": reln.get("semantic"),
            "left": reln["left"],
            "right": reln["right"],
            "overlapCount": reln["overlapCount"],
            "leftCoverage": reln["leftCoverage"],
            "rightCoverage": reln["rightCoverage"],
            "confidence": reln["confidence"],
        }
        for reln in relationships
    ]
    return {"version": 2, "generatedAt": generated_at, "keys": keys}


def build_source_quality_diagnostics(table_profiles: list[dict[str, Any]], relationships: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    tables = []
    for table in table_profiles:
        review_fields = [field for field in table.get("fields", []) if field.get("confidence", 1) < 0.62 or field.get("nullRate", 0) > 0.5]
        tables.append({
            "tableKey": table["tableKey"],
            "rowCount": table["rowCount"],
            "columnCount": table["columnCount"],
            "needsReview": bool(review_fields),
            "reviewFieldCount": len(review_fields),
        })
    return {
        "version": 2,
        "generatedAt": generated_at,
        "summary": {
            "tableCount": len(tables),
            "needsReviewTableCount": len([table for table in tables if table["needsReview"]]),
            "schemaDriftIssueCount": 0,
            "relationshipCandidateCount": len(relationships),
        },
        "tables": tables,
    }


def build_analysis_requirement_catalog(plans: list[dict[str, Any]], results: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    result_by_id = {str(item.get("analysisId")): item for item in results}
    requirements = []
    for plan in plans:
        result = result_by_id.get(str(plan.get("analysisId")), {})
        requirements.append({
            "analysisId": plan["analysisId"],
            "label": plan["label"],
            "executable": bool(plan.get("executable")),
            "status": result.get("status") or plan.get("status"),
            "sourceMode": plan.get("sourceMode"),
            "requiredSemantics": plan.get("requiredSemantics", []),
            "missingSemantics": plan.get("missingSemantics", []),
            "rowCount": result.get("rowCount", 0),
        })
    executable_count = len([item for item in requirements if item["executable"]])
    missing_count = sum(len(item["missingSemantics"]) for item in requirements)
    return {
        "version": 2,
        "generatedAt": generated_at,
        "summary": {
            "analysisCount": len(requirements),
            "executableCount": executable_count,
            "missingDataRequestCount": missing_count,
        },
        "requirements": requirements,
    }


def build_source_readiness_diagnostics(plans: list[dict[str, Any]], gaps: list[dict[str, Any]], generated_at: str) -> dict[str, Any]:
    readiness = [
        {
            "analysisId": plan["analysisId"],
            "label": plan["label"],
            "ready": bool(plan.get("executable")),
            "missingSemantics": plan.get("missingSemantics", []),
            "nextAction": "run_query" if plan.get("executable") else "confirm_semantics_or_relationships",
        }
        for plan in plans
    ]
    return {
        "version": 2,
        "generatedAt": generated_at,
        "summary": {
            "analysisCount": len(readiness),
            "readyCount": len([item for item in readiness if item["ready"]]),
            "gapCount": len(gaps),
        },
        "analysisReadiness": readiness,
    }


def empty_user_confirmation_state() -> dict[str, Any]:
    return {
        "summary": {
            "semanticApprovedCount": 0,
            "semanticRejectedCount": 0,
            "relationshipApprovedCount": 0,
            "relationshipRejectedCount": 0,
            "lastConfirmedAt": None,
        }
    }


def source_intelligence(input_paths: list[Path], output_dir: Path, domain_pack_runtime_path: Path | None = None) -> dict[str, Any]:
    stage_timings: dict[str, int] = {}
    files = timed(stage_timings, "discover_files_ms", lambda: discover_source_files(input_paths))
    if not files:
        raise SystemExit("No CSV/XLSX sources found")
    output_dir.mkdir(parents=True, exist_ok=True)
    domain_pack_runtime, source_pipeline_contract = load_domain_pack_runtime(
        domain_pack_runtime_path,
        default_runtime_file=DEFAULT_DOMAIN_PACK_RUNTIME,
    )
    tables, reader_warnings = timed(stage_timings, "read_sources_ms", lambda: read_source_tables(files))
    table_profiles, field_candidates = timed(stage_timings, "profile_sources_ms", lambda: profile_tables(tables))
    relationships = timed(stage_timings, "discover_relationships_ms", lambda: discover_relationships(tables, field_candidates))
    metric_sql_plans = timed(stage_timings, "compile_metric_sql_ms", lambda: build_metric_plans(tables, field_candidates, relationships))
    metric_query_results = timed(stage_timings, "execute_metric_sql_ms", lambda: execute_metric_sql(metric_sql_plans, tables))
    data_gaps = timed(stage_timings, "diagnostics_ms", lambda: build_data_gaps(field_candidates, relationships, metric_sql_plans))
    generated_at = now_iso()

    semantic_confirmation_draft = build_semantic_confirmation_draft(field_candidates, generated_at)
    relationship_coverage_matrix = build_relationship_coverage_matrix(relationships, generated_at)
    source_quality_diagnostics = build_source_quality_diagnostics(table_profiles, relationships, generated_at)
    analysis_requirement_catalog = build_analysis_requirement_catalog(metric_sql_plans, metric_query_results, generated_at)
    source_readiness_diagnostics = build_source_readiness_diagnostics(metric_sql_plans, data_gaps, generated_at)
    executable_count = len([plan for plan in metric_sql_plans if plan.get("executable")])
    user_confirmations = empty_user_confirmation_state()

    manifest = {
        "version": 2,
        "status": "ready",
        "generatedAt": generated_at,
        "generatedBy": "tools/source_evidence_engine.py",
        "engine": "aibi-hybrid-compact-python+pandas",
        "inputRoots": [rel(Path(path)) for path in input_paths],
        "sourceCount": len(files),
        "tableCount": len(table_profiles),
        "skippedTableCount": 0,
        "fieldCandidateCount": len(field_candidates),
        "derivedFieldCount": 0,
        "relationshipCount": len(relationships),
        "dataGapCount": len(data_gaps),
        "metricSqlPlanCount": len(metric_sql_plans),
        "metricSqlExecutableCount": executable_count,
        "sourceReadinessDiagnosticCount": len(source_readiness_diagnostics["analysisReadiness"]),
        "analysisRequirementCount": analysis_requirement_catalog["summary"]["analysisCount"],
        "analysisRequirementExecutableCount": analysis_requirement_catalog["summary"]["executableCount"],
        "analysisRequirementMissingDataRequestCount": analysis_requirement_catalog["summary"]["missingDataRequestCount"],
        "sourceQualityTableCount": source_quality_diagnostics["summary"]["tableCount"],
        "sourceQualityReviewTableCount": source_quality_diagnostics["summary"]["needsReviewTableCount"],
        "sourceQualitySchemaDriftIssueCount": source_quality_diagnostics["summary"]["schemaDriftIssueCount"],
        "semanticConfirmationCount": len(semantic_confirmation_draft["confirmations"]),
        "relationshipCoverageKeyCount": len(relationship_coverage_matrix["keys"]),
        "userConfirmationSummary": user_confirmations["summary"],
        "stageTimingsMs": stage_timings,
        "domainPackRuntime": domain_pack_runtime,
        "sourcePipelineContract": source_pipeline_contract,
        "outputs": OUTPUTS,
        "principles": [
            "Source folders are scanned read-only; generated evidence stays in this project.",
            "Heuristic semantics remain reviewable until a user confirms important business bindings.",
            "Cross-table metrics require relationship evidence and grain confirmation.",
        ],
        "readerWarnings": reader_warnings,
    }

    source_profile_payload = {
        "version": 2,
        "generatedAt": generated_at,
        "domainPackRuntime": domain_pack_runtime,
        "sourcePipelineContract": source_pipeline_contract,
        "tables": table_profiles,
        "skippedTables": [],
        "sourceFiles": [str(path.resolve()) for path in files],
        "readerWarnings": reader_warnings,
    }
    field_payload = {
        "version": 2,
        "generatedAt": generated_at,
        "pipelineStage": "semantic_scorer",
        "fields": field_candidates,
    }
    relationship_payload = {
        "version": 2,
        "generatedAt": generated_at,
        "pipelineStage": "relationship_discovery",
        "relationships": relationships,
    }
    gap_payload = {"version": 2, "generatedAt": generated_at, "pipelineStage": "diagnostics", "diagnostics": data_gaps}
    metric_sql_payload = {
        "version": 2,
        "generatedAt": generated_at,
        "engine": "pandas evidence runtime",
        "pipelineStage": "metric_compiler",
        "guardrails": {
            "readOnly": True,
            "blockedStatements": ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "TRUNCATE"],
            "userConfirmationPolicy": "blocked plans stay in evidence gaps until semantics and grain are confirmed",
        },
        "plans": metric_sql_plans,
    }
    metric_results_payload = {
        "version": 2,
        "generatedAt": generated_at,
        "engine": "pandas evidence runtime",
        "pipelineStage": "query_runtime",
        "results": metric_query_results,
    }
    payloads = {
        OUTPUTS["sourceProfile"]: source_profile_payload,
        OUTPUTS["semanticFieldCandidates"]: field_payload,
        OUTPUTS["relationshipDiscovery"]: relationship_payload,
        OUTPUTS["dataGapDiagnostics"]: gap_payload,
        OUTPUTS["metricSqlCompiler"]: metric_sql_payload,
        OUTPUTS["metricQueryResults"]: metric_results_payload,
        OUTPUTS["sourceReadinessDiagnostics"]: source_readiness_diagnostics,
        OUTPUTS["analysisRequirementCatalog"]: analysis_requirement_catalog,
        OUTPUTS["sourceQualityDiagnostics"]: source_quality_diagnostics,
        OUTPUTS["semanticConfirmationDraft"]: semantic_confirmation_draft,
        OUTPUTS["relationshipCoverageMatrix"]: relationship_coverage_matrix,
        OUTPUTS["sourceProfile"].replace("source-profile-generic.json", "source-intelligence-manifest.json"): manifest,
    }
    for name, payload in payloads.items():
        (output_dir / name).write_text(json.dumps(json_ready(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Profile CSV/XLSX sources and write AIBI Hybrid evidence receipts.")
    parser.add_argument("inputs", nargs="*", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--domain-pack-runtime", type=Path)
    args = parser.parse_args()
    if not args.inputs:
        parser.error("At least one source path is required.")
    inputs = args.inputs
    manifest = source_intelligence(inputs, args.output_dir, args.domain_pack_runtime)
    print(json.dumps(json_ready(manifest), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
