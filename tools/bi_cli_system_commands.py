from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from agent_action_draft_store import count_pending_action_drafts
from bi_cli_contracts import build_cli_contract, command_contract_by_name, contract_to_markdown, filter_commands
from bi_cli_core import DB_PATH, DUCKDB_PATH, source_label
from bi_cli_io_services import metric_sql_doctor_from_run, rows_to_dicts
from bi_cli_schema import active_workspace_id, open_db, workspace_records
from evidence_run_store import count_source_intelligence_runs, latest_source_intelligence_summary
from query_runtime import duckdb_status
from workspace_command_service import (
    workspace_create_command as workspace_create_command_service,
    workspace_delete_command as workspace_delete_command_service,
    workspace_rename_command as workspace_rename_command_service,
    workspace_select_command as workspace_select_command_service,
)

def cli_contract_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> dict[str, Any]:
    contract = build_cli_contract(parser)
    if args.command_name:
        command_contract = command_contract_by_name(contract, args.command_name)
        if not command_contract:
            raise ValueError(f"Unknown CLI command in contract: {args.command_name}")
        domains = {str(command_contract["domain"]): 1}
        mutation_modes = {str(command_contract["mutationMode"]): 1}
        contract = {
            **contract,
            "commands": [command_contract],
            "commandCount": 1,
            "domains": domains,
            "mutationModes": mutation_modes,
        }
    output_path = Path(args.output) if args.output else None
    if args.format == "markdown":
        markdown = contract_to_markdown(contract)
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(markdown, encoding="utf-8")
        return {
            "ok": True,
            "format": "markdown",
            "contract": {
                "schema": contract["schema"],
                "commandCount": contract["commandCount"],
                "domains": contract["domains"],
                "mutationModes": contract["mutationModes"],
            },
            "markdown": markdown if not output_path else "",
            "outputPath": str(output_path) if output_path else "",
        }
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "format": "json",
        "contract": contract,
        "outputPath": str(output_path) if output_path else "",
    }


def list_commands_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> dict[str, Any]:
    contract = build_cli_contract(parser)
    writes_filter = None
    if args.writes == "yes":
        writes_filter = True
    elif args.writes == "no":
        writes_filter = False
    commands = filter_commands(
        contract,
        domain=args.domain,
        mutation_mode=args.mutation_mode,
        writes=writes_filter,
    )
    return {
        "ok": True,
        "schema": contract["schema"],
        "commandCount": len(commands),
        "commands": [
            {
                "name": command["name"],
                "domain": command["domain"],
                "mutationMode": command["mutationMode"],
                "dryRunByDefault": command["dryRunByDefault"],
                "requiresYes": command["requiresYes"],
                "createsActionDraft": command["createsActionDraft"],
                "writesEvidence": command["writesEvidence"],
                "writesBusinessState": command["writesBusinessState"],
            }
            for command in commands
        ],
    }


def status_command(args: argparse.Namespace) -> dict[str, Any]:
    runtime = duckdb_status(DUCKDB_PATH)
    with open_db() as connection:
        active_id = active_workspace_id(connection)
        workspaces = workspace_records(connection)
        counts = {
            "tables": connection.execute("SELECT COUNT(*) FROM table_registry WHERE workspace_id = ?", (active_id,)).fetchone()[0],
            "sourceRuns": connection.execute("SELECT COUNT(*) FROM source_runs WHERE workspace_id = ?", (active_id,)).fetchone()[0],
            "fields": connection.execute("SELECT COUNT(*) FROM field_semantics WHERE workspace_id = ?", (active_id,)).fetchone()[0],
            "metrics": connection.execute("SELECT COUNT(*) FROM metric_definitions WHERE workspace_id = ?", (active_id,)).fetchone()[0],
            "relationships": connection.execute("SELECT COUNT(*) FROM relationships WHERE workspace_id = ?", (active_id,)).fetchone()[0],
            "dashboards": connection.execute("SELECT COUNT(*) FROM dashboards WHERE workspace_id = ?", (active_id,)).fetchone()[0],
            "actionDrafts": count_pending_action_drafts(connection, workspace_id=active_id),
            "sourceIntelligenceRuns": count_source_intelligence_runs(connection, workspace_id=active_id),
            "connectors": connection.execute("SELECT COUNT(*) FROM data_connectors").fetchone()[0],
        }
        workspace = dict(connection.execute("SELECT * FROM workspaces WHERE id = ?", (active_id,)).fetchone())
        workspace["isActive"] = True
        source_runs = rows_to_dicts(
            connection.execute(
                """
                SELECT id, table_key, name, status, row_count, column_count, source_file
                FROM source_runs
                WHERE workspace_id = ?
                ORDER BY created_at DESC
                LIMIT 5
                """,
                (active_id,),
            )
        )
        for run in source_runs:
            run["source_file"] = source_label(run["source_file"])
        return {
            "ok": True,
            "workspace": workspace,
            "workspaces": workspaces,
            "database": str(DB_PATH),
            "queryRuntime": runtime,
            "counts": counts,
            "sourceRuns": source_runs,
            "health": {
                "ok": True,
                "notes": [
                    "No bundled data is loaded by default; import local files to begin analysis.",
                    (
                        "DuckDB query runtime is available."
                        if runtime["available"]
                        else "DuckDB package is missing; whitelist queries use SQLite fallback until requirements are installed."
                    ),
                ],
            },
        }


def quality_doctor_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        counts = {
            "tables": connection.execute("SELECT COUNT(*) FROM table_registry WHERE workspace_id = ?", (workspace_id,)).fetchone()[0],
            "sourceRuns": connection.execute("SELECT COUNT(*) FROM source_runs WHERE workspace_id = ?", (workspace_id,)).fetchone()[0],
            "fields": connection.execute("SELECT COUNT(*) FROM field_semantics WHERE workspace_id = ?", (workspace_id,)).fetchone()[0],
            "metrics": connection.execute("SELECT COUNT(*) FROM metric_definitions WHERE workspace_id = ?", (workspace_id,)).fetchone()[0],
            "relationships": connection.execute("SELECT COUNT(*) FROM relationships WHERE workspace_id = ?", (workspace_id,)).fetchone()[0],
            "dashboards": connection.execute("SELECT COUNT(*) FROM dashboards WHERE workspace_id = ?", (workspace_id,)).fetchone()[0],
            "actionDrafts": count_pending_action_drafts(connection, workspace_id=workspace_id),
            "sourceIntelligenceRuns": count_source_intelligence_runs(connection, workspace_id=workspace_id),
        }
        latest_run = latest_source_intelligence_summary(connection, workspace_id=workspace_id)
        low_confidence_fields = rows_to_dicts(
            connection.execute(
                """
                SELECT table_key, field_name, role, usage, confidence
                FROM field_semantics
                WHERE workspace_id = ? AND confidence < 0.65
                ORDER BY confidence ASC, table_key, field_name
                LIMIT 8
                """,
                (workspace_id,),
            )
        )
        recent_runs = rows_to_dicts(
            connection.execute(
                """
                SELECT table_key, name, status, row_count, column_count, source_file
                FROM source_runs
                WHERE workspace_id = ?
                ORDER BY created_at DESC
                LIMIT 6
                """,
                (workspace_id,),
            )
        )
    for run in recent_runs:
        run["source_file"] = source_label(run["source_file"])

    latest_run = latest_run or {}
    source_intelligence_tables = int(latest_run.get("table_count") or 0)
    metric_sql_diagnostic = metric_sql_doctor_from_run(latest_run) if latest_run else {}
    metric_sql_plans = int(metric_sql_diagnostic.get("planned") or latest_run.get("metric_sql_plan_count") or 0)
    executable_metric_sql = int(metric_sql_diagnostic.get("executable") or latest_run.get("metric_sql_executable_count") or 0)
    metric_sql_rate = executable_metric_sql / max(1, metric_sql_plans)
    missing_semantic_summary = metric_sql_diagnostic.get("missingSemantics") if isinstance(metric_sql_diagnostic.get("missingSemantics"), list) else []
    relationship_needed = counts["tables"] > 1 and counts["relationships"] == 0

    score_parts = [
        100 if counts["tables"] > 0 else 35,
        100 if counts["fields"] >= max(1, counts["tables"] * 3) else 55,
        100 if counts["metrics"] > 0 else 50,
        100 if counts["dashboards"] > 0 else 55,
        100 if source_intelligence_tables >= counts["tables"] and counts["tables"] > 0 else 60,
        round(metric_sql_rate * 100) if metric_sql_plans else 60,
        100 if not low_confidence_fields else 70,
        100 if not relationship_needed else 65,
    ]
    score = round(sum(score_parts) / len(score_parts))
    tone = "ok" if score >= 85 else "warn" if score >= 65 else "risk"

    issues: list[dict[str, Any]] = []
    if counts["tables"] == 0:
        issues.append({
            "key": "no-table",
            "tone": "risk",
            "title": "还没有可分析的数据表",
            "detail": "先导入文件，或运行验证链路。",
            "action": "导入数据",
        })
    if counts["metrics"] == 0:
        issues.append({
            "key": "no-metric",
            "tone": "warn",
            "title": "缺少业务指标",
            "detail": "看板可以展示表格，但自然语言回答和趋势判断会变弱。",
            "action": "生成指标",
        })
    if relationship_needed:
        issues.append({
            "key": "missing-relationship",
            "tone": "warn",
            "title": "多表尚未建立关系",
            "detail": "跨表组件、筛选联动和下钻解释需要至少一条可确认关系。",
            "action": "推荐关系",
        })
    if latest_run and source_intelligence_tables < counts["tables"]:
        issues.append({
            "key": "source-intelligence-stale",
            "tone": "warn",
            "title": "Source Intelligence 可能落后于当前表",
            "detail": f"最新扫描覆盖 {source_intelligence_tables} 张表，当前工作区有 {counts['tables']} 张表。",
            "action": "重新扫描",
        })
    if metric_sql_plans and metric_sql_rate < 0.8:
        issues.append({
            "key": "metric-sql-coverage",
            "tone": "warn",
            "title": "部分指标 SQL 还不能执行",
            "detail": (
                f"{executable_metric_sql}/{metric_sql_plans} 个指标 SQL 可执行。"
                f"优先确认 {', '.join(str(item.get('semantic')) for item in missing_semantic_summary[:3] if isinstance(item, dict)) or '字段语义'}。"
            ),
            "action": "修复指标",
            "repairDraft": metric_sql_diagnostic.get("repairDraft"),
        })
    if low_confidence_fields:
        issues.append({
            "key": "low-confidence-fields",
            "tone": "warn",
            "title": "存在低置信字段语义",
            "detail": "字段用途不稳定会影响指标推荐、筛选和 Agent 解释。",
            "action": "确认字段",
            "examples": low_confidence_fields,
        })
    if not issues:
        issues.append({
            "key": "ready",
            "tone": "ok",
            "title": "数据链路可用于看板和 Agent",
            "detail": "表、字段、指标、Source Intelligence 和看板基础资产已经形成闭环。",
            "action": "继续分析",
        })

    return {
        "ok": True,
        "source": "hybrid-quality-doctor",
        "workspaceId": workspace_id,
        "score": score,
        "tone": tone,
        "summary": "数据链路健康" if tone == "ok" else "存在可优化的数据链路问题",
        "counts": counts,
        "latestSourceIntelligenceRun": latest_run or None,
        "metricSql": {
            "planned": metric_sql_plans,
            "executable": executable_metric_sql,
            "rate": metric_sql_rate,
            **metric_sql_diagnostic,
        },
        "issues": issues,
        "recentSourceRuns": recent_runs,
        "nextActions": [
            "导入数据",
            "运行 Source Intelligence",
            "生成或确认指标",
            "预演看板",
            "让 Agent 解释证据",
        ],
    }


def workspace_create_command(args: argparse.Namespace) -> dict[str, Any]:
    return workspace_create_command_service(args, open_db=open_db)


def workspace_select_command(args: argparse.Namespace) -> dict[str, Any]:
    return workspace_select_command_service(args, open_db=open_db)


def workspace_rename_command(args: argparse.Namespace) -> dict[str, Any]:
    return workspace_rename_command_service(args, open_db=open_db)


def workspace_delete_command(args: argparse.Namespace) -> dict[str, Any]:
    return workspace_delete_command_service(args, open_db=open_db, duckdb_path=DUCKDB_PATH)

