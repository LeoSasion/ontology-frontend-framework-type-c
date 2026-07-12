from __future__ import annotations

import json
import re
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import Any


KNOWLEDGE_PATH = Path(__file__).resolve().parents[1] / "knowledge" / "platform-commerce.v1.json"


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


@lru_cache(maxsize=1)
def platform_knowledge_pack() -> dict[str, Any]:
    return json.loads(KNOWLEDGE_PATH.read_text(encoding="utf-8"))


def _table_catalog(connection: sqlite3.Connection, workspace_id: str) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT table_key, display_name, physical_table FROM table_registry WHERE workspace_id = ? ORDER BY table_key",
        (workspace_id,),
    ).fetchall()
    catalog: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        item["fields"] = {
            str(column["name"])
            for column in connection.execute(f"PRAGMA table_info({_quote(item['physical_table'])})").fetchall()
        }
        catalog.append(item)
    return catalog


def _matches_prompt(intent: dict[str, Any], prompt: str) -> bool:
    folded = prompt.casefold()
    all_terms = [str(term).casefold() for term in intent.get("allTerms", [])]
    any_terms = [str(term).casefold() for term in intent.get("anyTerms", [])]
    exclude_terms = [str(term).casefold() for term in intent.get("excludeTerms", [])]
    if exclude_terms and any(term in folded for term in exclude_terms):
        return False
    if all_terms and not all(term in folded for term in all_terms):
        return False
    if any_terms and not any(term in folded for term in any_terms):
        return False
    entity_pattern = str(intent.get("entityPattern") or "")
    percent_pattern = str(intent.get("percentPattern") or "")
    if entity_pattern and re.search(entity_pattern, prompt, re.IGNORECASE) is None:
        return False
    return not percent_pattern or re.search(percent_pattern, prompt, re.IGNORECASE) is not None


def _resolve_roles(intent: dict[str, Any], catalog: list[dict[str, Any]]) -> dict[str, dict[str, Any]] | None:
    roles: dict[str, dict[str, Any]] = {}
    used_tables: set[str] = set()
    for requirement in intent.get("tables", []):
        role = str(requirement.get("role") or "")
        required = {str(field) for field in requirement.get("requiredFields", [])}
        match = next(
            (
                table
                for table in catalog
                if table["table_key"] not in used_tables and required.issubset(table["fields"])
            ),
            None,
        )
        if not role or not match:
            return None
        roles[role] = match
        used_tables.add(str(match["table_key"]))
    return roles


def _format_value(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.2f}"


def _compiled_sql(intent: dict[str, Any], roles: dict[str, dict[str, Any]]) -> str:
    sql = str(intent.get("sql") or "").strip()
    if not sql or ";" in sql or not re.match(r"^(SELECT|WITH)\b", sql, re.IGNORECASE):
        raise ValueError(f"Unsafe platform knowledge query: {intent.get('id')}")
    for role, table in roles.items():
        sql = sql.replace("{{" + role + "}}", _quote(str(table["physical_table"])))
    if "{{" in sql or "}}" in sql:
        raise ValueError(f"Unresolved platform knowledge table role: {intent.get('id')}")
    return sql


def match_platform_knowledge(
    connection: sqlite3.Connection,
    workspace_id: str,
    prompt: str,
) -> dict[str, Any] | None:
    pack = platform_knowledge_pack()
    catalog = _table_catalog(connection, workspace_id)
    for intent in pack.get("intents", []):
        if not _matches_prompt(intent, prompt):
            continue
        roles = _resolve_roles(intent, catalog)
        if not roles:
            continue
        entity_pattern = str(intent.get("entityPattern") or "")
        entity_match = re.search(entity_pattern, prompt, re.IGNORECASE) if entity_pattern else None
        percent_pattern = str(intent.get("percentPattern") or "")
        percent_match = re.search(percent_pattern, prompt, re.IGNORECASE) if percent_pattern else None
        return {
            "packId": pack["id"],
            "packVersion": pack["version"],
            "ruleId": intent["id"],
            "title": intent["title"],
            "grain": intent["grain"],
            "principles": pack.get("principles", []),
            "roles": roles,
            "entity": entity_match.group(0) if entity_match else None,
            "threshold": float(percent_match.group(1)) / 100 if percent_match else None,
            "sql": _compiled_sql(intent, roles),
            "source": pack.get("source", {}),
        }
    return None


def execute_platform_knowledge(
    connection: sqlite3.Connection,
    match: dict[str, Any],
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if match.get("entity"):
        params["entity"] = match["entity"]
    if match.get("threshold") is not None:
        params["threshold"] = match["threshold"]
    rows = [dict(row) for row in connection.execute(match["sql"], params).fetchall()]
    metrics = [
        {
            "label": {"zh": str(row.get("label") or "结果"), "en": str(row.get("label") or "Result")},
            "value": _format_value(row.get("value")),
            "rawValue": row.get("value"),
            "unit": "value",
        }
        for row in rows
    ]
    summary_text = "；".join(f"{item['label']['zh']} {item['value']}" for item in metrics)
    role_refs = [
        {
            "type": "table",
            "role": role,
            "tableKey": table["table_key"],
            "name": table["display_name"],
        }
        for role, table in match["roles"].items()
    ]
    primary_table = next(iter(match["roles"].values()))
    return {
        "kind": "platform_analysis",
        "title": {"zh": match["title"], "en": match["title"]},
        "summary": {"zh": summary_text, "en": summary_text},
        "confidence": "query-runtime",
        "metrics": metrics,
        "rows": rows,
        "query": {
            "table": primary_table["table_key"],
            "group": None,
            "measure": match["ruleId"],
            "aggregation": "knowledge-rule",
            "runtime": {
                "engine": "sqlite",
                "database": "metadata-store",
                "compiledSql": match["sql"],
                "parameters": params,
            },
            "filters": [],
            "joins": role_refs[1:],
            "fallbackReason": None,
            "sqlIntent": "versioned platform knowledge rule; current workspace data only",
        },
        "knowledgeRule": {
            "packId": match["packId"],
            "packVersion": match["packVersion"],
            "ruleId": match["ruleId"],
            "title": match["title"],
            "grain": match["grain"],
            "source": match["source"],
        },
        "evidenceRefs": [
            *role_refs,
            {
                "type": "knowledgeRule",
                "packId": match["packId"],
                "ruleId": match["ruleId"],
                "grain": match["grain"],
            },
            {
                "type": "queryRuntime",
                "engine": "sqlite",
                "compiledSql": match["sql"],
                "parameters": params,
            },
        ],
        "nextActions": [
            {"zh": "查看口径、粒度和查询回执", "en": "Review grain, definition, and query receipt"}
        ],
    }


def platform_knowledge_context(match: dict[str, Any] | None) -> str:
    if not match:
        return ""
    return " ".join(
        [
            f"业务规则：{match['title']}。",
            f"统计粒度：{match['grain']}。",
            *[str(item) for item in match.get("principles", [])],
        ]
    )


def requires_verified_analysis_plan(prompt: str) -> bool:
    folded = prompt.casefold()
    risk_terms = [
        "分母",
        "退款率",
        "转化率",
        "一单多包裹率",
        "跨表",
        "关联后",
        "连接后",
        "平均的平均",
    ]
    return any(term.casefold() in folded for term in risk_terms)


def build_verified_analysis_gap(prompt: str, table_key: str | None) -> dict[str, Any]:
    pack = platform_knowledge_pack()
    return {
        "kind": "clarification",
        "title": {"zh": "需要先确认复合统计口径", "en": "Confirm the compound metric definition"},
        "summary": {
            "zh": "当前问题涉及跨表分子/分母、去重或连接粒度，但工作区还没有可执行且已验证的完整口径。为避免给出错误数字，本次不执行近似聚合。",
            "en": "This request needs a verified cross-table numerator, denominator, deduplication, or join grain. No approximate aggregation was executed.",
        },
        "confidence": "missing",
        "metrics": [],
        "rows": [],
        "clarification": {
            "kind": "compound-analysis-definition",
            "question": prompt,
            "required": ["分子与分母", "主表与关联表", "连接键与粒度", "状态和时间范围"],
        },
        "evidenceRefs": [
            {"type": "table", "tableKey": table_key} if table_key else {"type": "workspace"},
            {
                "type": "knowledgeGuard",
                "packId": pack["id"],
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
