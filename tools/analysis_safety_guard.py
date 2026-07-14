from __future__ import annotations

from typing import Any


def requires_verified_analysis_plan(prompt: str) -> bool:
    folded = prompt.casefold()
    structural_risk_terms = [
        "分子",
        "分母",
        "跨表",
        "关联后",
        "连接后",
        "平均的平均",
        "deduplicate",
        "denominator",
        "join grain",
        "after joining",
    ]
    return any(term.casefold() in folded for term in structural_risk_terms)


def build_verified_analysis_gap(prompt: str, table_key: str | None) -> dict[str, Any]:
    return {
        "kind": "clarification",
        "title": {"zh": "需要先确认复合统计口径", "en": "Confirm the compound analysis definition"},
        "summary": {
            "zh": "当前问题涉及跨表分子/分母、去重或连接粒度，但工作区还没有可执行且已验证的完整口径。为避免错误数字，本次不执行近似聚合。",
            "en": "This request needs a verified numerator, denominator, deduplication, or join grain. No approximate aggregation was executed.",
        },
        "confidence": "missing",
        "metrics": [],
        "rows": [],
        "clarification": {
            "kind": "compound-analysis-definition",
            "question": prompt,
            "required": ["分子与分母", "参与表", "连接键与粒度", "筛选和时间范围"],
        },
        "evidenceRefs": [
            {"type": "table", "tableKey": table_key} if table_key else {"type": "workspace"},
            {
                "type": "coreSafetyGuard",
                "ruleId": "compound-analysis-requires-verified-plan",
            },
        ],
        "nextActions": [
            {
                "zh": "确认分子、分母、连接键和统计粒度后再计算",
                "en": "Confirm numerator, denominator, join keys, and grain before calculation",
            }
        ],
    }
