from __future__ import annotations

import sqlite3
from typing import Any, Callable


def source_intelligence_dashboard_text(analysis: dict[str, Any]) -> str:
    required_semantics = analysis.get("requiredSemantics") if isinstance(analysis.get("requiredSemantics"), list) else []
    sample = analysis.get("sample") if isinstance(analysis.get("sample"), dict) else {}
    sample_text = "；".join(f"{key}={value}" for key, value in list(sample.items())[:6]) or "暂无字段片段"
    return "\n".join(
        [
            f"分析: {analysis.get('label') or analysis.get('analysisId')}",
            f"建议图表: {analysis.get('chartType') or 'table'}",
            f"结果行数: {analysis.get('rowCount') or 0}",
            f"来源模式: {analysis.get('sourceMode') or 'unknown'}",
            f"需要语义: {', '.join(str(item) for item in required_semantics[:6]) or '已由回执推断'}",
            f"字段片段: {sample_text}",
            "证据: metric-sql-compiler.json, metric-query-results.json",
        ]
    )


def build_source_intelligence_dashboard_draft(
    connection: sqlite3.Connection,
    run: sqlite3.Row,
    candidate: dict[str, Any],
    *,
    dashboard_name: str,
    limit: int,
    preferred_table_key: Callable[[sqlite3.Connection, str | None], str],
    template_widget_layout: Callable[[str, int], dict[str, Any]],
    slug: Callable[[Any], str],
) -> dict[str, Any]:
    run_key = str(run["run_key"])
    run_label = str(run["label"])
    analyses = [item for item in candidate.get("analyses", []) if isinstance(item, dict)][: max(1, min(limit, 8))]
    evidence_files = [str(item) for item in candidate.get("evidenceFiles", []) if item]
    evidence_refs = [f"source-intelligence:{run_key}", *evidence_files]
    default_table_key = preferred_table_key(connection, None)
    widgets: list[dict[str, Any]] = []
    layout: list[dict[str, Any]] = []

    summary_id = "source_intelligence_summary"
    summary_layout = {"i": summary_id, **template_widget_layout("text", 0)}
    layout.append(summary_layout)
    widgets.append(
        {
            "id": summary_id,
            "type": "text",
            "title": "真实表格证据摘要",
            "subtitle": f"{run_label} · {run_key}",
            "textContent": "\n".join(
                [
                    "本看板草案来自 Source Intelligence 回执，不直接复制外部源文件。",
                    f"文件: {candidate.get('sourceCount') or run['source_count']}；表: {candidate.get('tableCount') or run['table_count']}",
                    f"指标 SQL: {candidate.get('executableMetricCount') or run['metric_sql_executable_count']}/{candidate.get('plannedMetricCount') or run['metric_sql_plan_count']} 可执行",
                    f"候选分析: {len(analyses)}",
                    "确认后写入的是可编辑的通用看板组件；原始证据仍指向 sourceRun 和 JSON 回执。",
                ]
            ),
            "sourceAction": "source-intelligence-dashboard-candidate",
            "sourceRunKey": run_key,
            "sourceRunLabel": run_label,
            "evidenceRefs": evidence_refs,
            "layout": summary_layout,
        }
    )

    for index, analysis in enumerate(analyses, start=1):
        analysis_id = str(analysis.get("analysisId") or index)
        widget_id = f"source_intelligence_{slug(analysis_id) or index}"
        widget_layout = {"i": widget_id, **template_widget_layout("text", index)}
        layout.append(widget_layout)
        widgets.append(
            {
                "id": widget_id,
                "type": "text",
                "title": str(analysis.get("label") or analysis.get("analysisId") or f"指标候选 {index}"),
                "subtitle": f"{analysis.get('chartType') or 'table'} · {analysis.get('sourceMode') or 'source intelligence'}",
                "textContent": source_intelligence_dashboard_text(analysis),
                "sourceAction": "source-intelligence-dashboard-candidate",
                "sourceRunKey": run_key,
                "sourceRunLabel": run_label,
                "analysisId": analysis_id,
                "chartTypeHint": str(analysis.get("chartType") or ""),
                "sourceMode": str(analysis.get("sourceMode") or ""),
                "requiredSemantics": analysis.get("requiredSemantics") if isinstance(analysis.get("requiredSemantics"), list) else [],
                "sample": analysis.get("sample") if isinstance(analysis.get("sample"), dict) else {},
                "evidenceRefs": evidence_refs,
                "layout": widget_layout,
            }
        )

    return {
        "source": "source-intelligence-dashboard-candidate",
        "sourceRunKey": run_key,
        "sourceRunLabel": run_label,
        "dashboardName": dashboard_name or str(candidate.get("title") or "Source Intelligence 候选看板"),
        "defaultTableKey": default_table_key,
        "templateCount": len(widgets),
        "widgetCount": len(widgets),
        "categories": [{"category": "Source Intelligence 证据组件", "count": len(widgets)}],
        "widgets": widgets,
        "layout": layout,
        "previewWidgets": [
            {
                "id": widget.get("id"),
                "type": widget.get("type"),
                "title": widget.get("title"),
                "sourceRunKey": run_key,
                "analysisId": widget.get("analysisId"),
                "chartTypeHint": widget.get("chartTypeHint"),
            }
            for widget in widgets
        ],
        "evidence": evidence_refs,
        "dashboardCandidate": candidate,
        "confirmationSummary": {
            "zh": f"确认后将基于 {run_label} 创建 {len(widgets)} 个证据组件，源文件仍只读。",
            "en": f"After confirmation, AIBI will create {len(widgets)} evidence widgets from {run_label}; source files remain read-only.",
        },
    }
