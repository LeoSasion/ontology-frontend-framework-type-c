from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from bi_cli_core import ROOT, slug


def default_source_intelligence_output_dir(label: str) -> Path:
    return ROOT / "data" / "validation" / slug(label)


def read_json_file(path: Path, default: Any | None = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {} if default is None else default


def dashboard_chart_type_for_result(result: dict[str, Any]) -> str:
    rows = result.get("rows") if isinstance(result.get("rows"), list) else []
    sample = rows[0] if rows and isinstance(rows[0], dict) else {}
    keys = [str(key) for key in sample.keys()]
    if any("month" in key or "date" in key or "日期" in key or "月份" in key for key in keys):
        return "line"
    if any("reason" in key or "原因" in key or "category" in key or "分类" in key for key in keys):
        return "bar"
    return "table"


def compact_sample_row(row: dict[str, Any], limit: int = 4) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, value in row.items():
        if len(compact) >= limit:
            break
        if isinstance(value, (str, int, float)) or value is None:
            compact[str(key)] = value
    return compact


def build_source_intelligence_dashboard_candidate(output_dir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    metric_results = read_json_file(output_dir / str(manifest.get("outputs", {}).get("metricQueryResults") or "metric-query-results.json"), {"results": []})
    metric_plans = read_json_file(output_dir / str(manifest.get("outputs", {}).get("metricSqlCompiler") or "metric-sql-compiler.json"), {"plans": []})
    result_items = metric_results.get("results") if isinstance(metric_results, dict) else []
    plan_items = metric_plans.get("plans") if isinstance(metric_plans, dict) else []
    plans_by_id = {
        str(plan.get("analysisId")): plan
        for plan in plan_items
        if isinstance(plan, dict) and plan.get("analysisId")
    }
    executed = [
        item for item in result_items
        if isinstance(item, dict) and item.get("status") == "executed" and int(item.get("rowCount") or 0) > 0
    ]
    analyses: list[dict[str, Any]] = []
    for item in executed[:4]:
        analysis_id = str(item.get("analysisId") or "")
        plan = plans_by_id.get(analysis_id, {})
        rows = item.get("rows") if isinstance(item.get("rows"), list) else []
        sample = rows[0] if rows and isinstance(rows[0], dict) else {}
        analyses.append(
            {
                "analysisId": analysis_id,
                "label": str(item.get("label") or plan.get("label") or analysis_id),
                "status": str(item.get("status") or ""),
                "sourceMode": str(item.get("sourceMode") or plan.get("sourceMode") or ""),
                "rowCount": int(item.get("rowCount") or 0),
                "chartType": dashboard_chart_type_for_result(item),
                "requiredSemantics": [str(value) for value in plan.get("requiredSemantics", [])[:8]] if isinstance(plan.get("requiredSemantics"), list) else [],
                "sample": compact_sample_row(sample),
            }
        )
    return {
        "status": "ready" if analyses else "needs-confirmation",
        "title": "Source Intelligence 候选看板",
        "source": "source-intelligence-receipts",
        "analysisCount": len(analyses),
        "executableMetricCount": int(manifest.get("metricSqlExecutableCount") or len(executed)),
        "plannedMetricCount": int(manifest.get("metricSqlPlanCount") or 0),
        "sourceCount": int(manifest.get("sourceCount") or 0),
        "tableCount": int(manifest.get("tableCount") or 0),
        "analyses": analyses,
        "widgets": [
            {
                "type": analysis["chartType"],
                "title": analysis["label"],
                "analysisId": analysis["analysisId"],
                "sourceMode": analysis["sourceMode"],
            }
            for analysis in analyses
        ],
        "evidenceFiles": [
            "source-profile-generic.json",
            "semantic-field-candidates.json",
            "relationship-discovery.json",
            "metric-sql-compiler.json",
            "metric-query-results.json",
            "analysis-requirement-catalog.json",
        ],
    }


def source_intelligence_file_coverage(row: dict[str, Any]) -> dict[str, Any]:
    manifest = json.loads(row.pop("manifest_json", "{}") or "{}")
    output_dir = Path(row.get("output_dir") or "")
    source_profile_file = manifest.get("outputs", {}).get("sourceProfile") or "source-profile-generic.json"
    source_profile_path = output_dir / str(source_profile_file)
    source_files: list[str] = []
    skipped_tables: list[dict[str, Any]] = []
    if source_profile_path.exists():
        try:
            source_profile = json.loads(source_profile_path.read_text(encoding="utf-8"))
            source_files = [str(item) for item in source_profile.get("sourceFiles", []) if item]
            skipped_tables = [item for item in source_profile.get("skippedTables", []) if isinstance(item, dict)]
        except (OSError, json.JSONDecodeError):
            source_files = []
            skipped_tables = []
    source_group_counts: dict[str, int] = {}
    for source_file in source_files:
        normalized = source_file.replace("\\", "/")
        parts = [part for part in normalized.split("/") if part]
        source_group = parts[-2] if len(parts) >= 2 else "source"
        source_group_counts[source_group] = source_group_counts.get(source_group, 0) + 1
    manifest_source_count = int(manifest.get("sourceCount") or row.get("source_count") or 0)
    skipped_table_count = int(manifest.get("skippedTableCount") or len(skipped_tables))
    return {
        "sourceProfilePath": str(source_profile_path),
        "sourceFiles": source_files[:24],
        "sourceFileCount": len(source_files),
        "manifestSourceCount": manifest_source_count,
        "filesBySourceGroup": [{"group": group, "count": count} for group, count in sorted(source_group_counts.items())],
        "skippedTableCount": skipped_table_count,
        "skippedTables": skipped_tables[:8],
        "complete": len(source_files) == manifest_source_count and skipped_table_count == 0,
        "dashboardCandidate": build_source_intelligence_dashboard_candidate(output_dir, manifest),
    }
