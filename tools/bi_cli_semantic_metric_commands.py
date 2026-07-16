from __future__ import annotations

import argparse
import json
import re
import sqlite3
from typing import Any

from bi_cli_core import now_iso, parse_csv_list, quote_identifier
from bi_cli_io_services import parse_json_object, rows_to_dicts
from bi_cli_schema import active_workspace_id, open_db, table_columns
from bi_cli_source_commands import resolve_table_registry
from metric_formula_command_service import (
    add_metric_command as add_metric_command_service,
    build_metric_add_plan as build_metric_add_plan_service,
    metric_filters_from_cli as metric_filters_from_cli_service,
    metric_key_for as metric_key_for_service,
    metric_row_to_payload as metric_row_to_payload_service,
    upsert_metric_definition as upsert_metric_definition_service,
)
from query_runtime import SAFE_AGGREGATIONS

def normalize_semantic_role(role: str) -> str:
    text = str(role or "").strip()
    return {
        "time": "event_time",
        "identifier": "identity_key",
        "text": "dimension",
    }.get(text, text or "dimension")


def semantic_usage_object(role: str, usage: str = "") -> dict[str, bool]:
    normalized_role = normalize_semantic_role(role)
    base = {
        "filterable": normalized_role in {"event_time", "dimension", "status", "identity_key"},
        "sortable": normalized_role in {"event_time", "measure", "identity_key"},
        "groupable": normalized_role in {"event_time", "dimension", "status", "identity_key"},
        "aggregatable": normalized_role == "measure",
        "joinable": normalized_role == "identity_key",
        "uniqueKeyCandidate": normalized_role == "identity_key",
        "defaultAnalysisField": normalized_role in {"event_time", "dimension", "measure"},
    }
    usage_text = str(usage or "")
    if usage_text:
        for token in re.split(r"[,，]", usage_text):
            item = token.strip()
            if not item:
                continue
            enabled = not item.startswith(("no-", "not-"))
            key = re.sub(r"^(no-|not-)", "", item)
            if key in base:
                base[key] = enabled
    return base


def primary_usage_from_object(usage: dict[str, Any], role: str) -> str:
    if usage.get("aggregatable"):
        return "aggregatable"
    if usage.get("joinable"):
        return "joinable"
    if usage.get("groupable"):
        return "groupable"
    if usage.get("filterable"):
        return "filterable"
    normalized_role = normalize_semantic_role(role)
    if normalized_role == "measure":
        return "aggregatable"
    if normalized_role == "identity_key":
        return "joinable"
    return "filterable"


def infer_field_semantic_hybrid(connection: sqlite3.Connection, registry: sqlite3.Row, field: str) -> dict[str, Any]:
    table_key = registry["table_key"]
    physical_table = registry["physical_table"]
    text = field.lower()
    non_empty_rows = connection.execute(
        f"""
        SELECT {quote_identifier(field)} AS value
        FROM {quote_identifier(physical_table)}
        WHERE {quote_identifier(field)} IS NOT NULL
          AND TRIM(CAST({quote_identifier(field)} AS TEXT)) <> ''
        LIMIT 80
        """
    ).fetchall()
    numeric = 0
    for row in non_empty_rows:
        try:
            float(str(row["value"]).replace(",", "").replace("%", "").strip())
            numeric += 1
        except ValueError:
            pass
    numeric_ratio = numeric / len(non_empty_rows) if non_empty_rows else 0.0
    total_rows = int(registry["row_count"] or 0)
    distinct_ratio = 0.0
    if total_rows > 0:
        distinct_count = connection.execute(
            f"SELECT COUNT(DISTINCT {quote_identifier(field)}) FROM {quote_identifier(physical_table)}"
        ).fetchone()[0]
        distinct_ratio = min(1.0, float(distinct_count or 0) / total_rows)

    tags: list[str] = []
    role = "dimension"
    confidence = 0.58
    usage_hint = ""
    if field == "__canonical_date":
        role = "event_time"
        tags.extend(["time", "system"])
        confidence = 0.91
    elif field.startswith("__source_"):
        role = "dimension"
        tags.extend(["source-metadata", "system"])
        confidence = 0.82
        usage_hint = "filterable,no-groupable"
    elif any(token in text for token in ("电话", "手机号", "联系方式", "联系人电话", "mobile", "phone", "tel")):
        role = "dimension"
        tags.append("contact")
        confidence = 0.74
        usage_hint = "filterable,no-groupable"
    elif any(token in text for token in ("date", "time", "日期", "时间", "月份", "年月")):
        role = "event_time"
        tags.append("time")
        confidence = 0.9
    elif any(token in text for token in ("id", "key", "code", "identifier", "编号", "编码", "标识", "主键", "外键")):
        role = "identity_key"
        tags.append("identifier")
        confidence = 0.86 if distinct_ratio < 0.85 else 0.92
    elif any(token in text for token in ("status", "状态", "是否", "标记")):
        role = "status"
        tags.append("status")
        confidence = 0.82
    elif (
        any(token in text for token in ("amount", "value", "total", "score", "rate", "金额", "数值", "合计", "得分", "比例"))
        and not any(token in text for token in ("方式", "原因", "类型", "状态", "名称", "姓名", "备注", "标签", "方向", "场景"))
    ) or (numeric_ratio >= 0.9 and distinct_ratio < 0.75):
        role = "measure"
        tags.append("amount" if numeric_ratio >= 0.5 else "numeric")
        confidence = 0.86
    elif any(token in text for token in ("qty", "quantity", "count", "数量", "件数", "次数")):
        role = "measure"
        tags.append("quantity")
        confidence = 0.8
    elif any(token in text for token in ("category", "type", "group", "class", "source", "name", "label", "description", "分类", "类别", "类型", "分组", "来源", "地区", "方式", "原因", "名称", "备注", "标签", "方向", "场景")):
        role = "dimension"
        tags.append("category")
        confidence = 0.76
    if role in {"dimension", "status"} and distinct_ratio > 0.75:
        tags.append("high-cardinality")
        confidence = min(confidence, 0.68)
    usage_obj = semantic_usage_object(role, usage_hint)
    return {
        "tableKey": table_key,
        "tableName": registry["display_name"],
        "field": field,
        "role": role,
        "usage": usage_obj,
        "primaryUsage": primary_usage_from_object(usage_obj, role),
        "tags": sorted(set(tags)),
        "confidence": round(confidence, 2),
        "source": "auto",
        "note": "",
    }


def upsert_semantic_config(connection: sqlite3.Connection, item: dict[str, Any], overwrite_manual: bool = False) -> bool:
    workspace_id = active_workspace_id(connection)
    table_key = str(item["tableKey"])
    field = str(item["field"])
    role = normalize_semantic_role(str(item["role"]))
    usage_obj = item.get("usage") if isinstance(item.get("usage"), dict) else semantic_usage_object(role, str(item.get("primaryUsage") or ""))
    primary_usage = primary_usage_from_object(usage_obj, role)
    current = connection.execute(
        "SELECT source FROM field_semantics WHERE table_key = ? AND field_name = ? AND workspace_id = ?",
        (table_key, field, workspace_id),
    ).fetchone()
    if current:
        current_source = str(current["source"] or "")
        if current_source == "reviewed" or (current_source == "manual" and not overwrite_manual):
            return False
    connection.execute(
        """
        INSERT INTO field_semantics(workspace_id, table_key, field_name, role, usage, confidence, tags_json, usage_json, source, note, updated_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(workspace_id, table_key, field_name) DO UPDATE SET
          role = excluded.role,
          usage = excluded.usage,
          confidence = excluded.confidence,
          tags_json = excluded.tags_json,
          usage_json = excluded.usage_json,
          source = excluded.source,
          note = excluded.note,
          updated_at = excluded.updated_at
        """,
        (
            workspace_id,
            table_key,
            field,
            role,
            primary_usage,
            float(item.get("confidence") or 0),
            json.dumps(item.get("tags") if isinstance(item.get("tags"), list) else [], ensure_ascii=False),
            json.dumps(usage_obj, ensure_ascii=False),
            str(item.get("source") or "auto"),
            str(item.get("note") or ""),
            now_iso(),
        ),
    )
    return True


def infer_semantics_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        registries = [resolve_table_registry(connection, args.table)] if args.table else connection.execute("SELECT * FROM table_registry WHERE workspace_id = ? ORDER BY display_name", (workspace_id,)).fetchall()
        proposals: list[dict[str, Any]] = []
        written = 0
        for registry in registries:
            for field in table_columns(connection, registry["physical_table"]):
                proposals.append(infer_field_semantic_hybrid(connection, registry, field))
        if args.yes:
            for item in proposals:
                if upsert_semantic_config(connection, item, overwrite_manual=args.overwrite_manual):
                    written += 1
            connection.commit()
    return {
        "ok": True,
        "dryRun": not args.yes,
        "requiresConfirmation": not args.yes,
        "proposed": len(proposals),
        "written": written,
        "semantics": proposals,
        "source": "infer-semantics adapted to workspace field_semantics",
    }


def semantic_row_to_payload(row: sqlite3.Row, table_name: str | None = None) -> dict[str, Any]:
    usage_obj = parse_json_object(row["usage_json"], {})
    if not usage_obj:
        usage_obj = semantic_usage_object(str(row["role"]), str(row["usage"]))
    return {
        "tableKey": row["table_key"],
        "tableName": table_name or row["table_key"],
        "field": row["field_name"],
        "role": row["role"],
        "primaryUsage": row["usage"],
        "usage": usage_obj,
        "tags": parse_json_object(row["tags_json"], []),
        "confidence": float(row["confidence"] or 0),
        "source": row["source"],
        "note": row["note"],
        "updatedAt": row["updated_at"],
    }


def list_semantics_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        params: list[Any] = [workspace_id]
        where = "WHERE f.workspace_id = ?"
        if args.table:
            registry = resolve_table_registry(connection, args.table)
            where += " AND f.table_key = ?"
            params.append(registry["table_key"])
        rows = connection.execute(
            f"""
            SELECT f.*, COALESCE(t.display_name, f.table_key) AS table_name
            FROM field_semantics f
            LEFT JOIN table_registry t ON t.table_key = f.table_key AND t.workspace_id = f.workspace_id
            {where}
            ORDER BY f.table_key, f.field_name
            """,
            params,
        ).fetchall()
    semantics = [semantic_row_to_payload(row, row["table_name"]) for row in rows]
    return {"ok": True, "semantics": semantics, "count": len(semantics)}


def set_semantic_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        proposed = build_semantic_set_plan(connection, args.table, args.field, args.role, args.usage or [], args.tag or [], args.confidence, args.note or "")
        if not args.yes:
            current = connection.execute(
                "SELECT * FROM field_semantics WHERE table_key = ? AND field_name = ? AND workspace_id = ?",
                (proposed["tableKey"], proposed["field"], active_workspace_id(connection)),
            ).fetchone()
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "current": semantic_row_to_payload(current, proposed["tableName"]) if current else None,
                "proposed": proposed,
            }
        execute_semantic_set_plan(connection, proposed)
        connection.commit()
    return {"ok": True, "confirmed": True, "semantic": proposed}


def build_semantic_set_plan(
    connection: sqlite3.Connection,
    table: str,
    field: str,
    role: str,
    usages: list[str] | tuple[str, ...] | None = None,
    tags_arg: list[str] | tuple[str, ...] | None = None,
    confidence: float = 1.0,
    note: str = "",
) -> dict[str, Any]:
    registry = resolve_table_registry(connection, table)
    columns = table_columns(connection, registry["physical_table"])
    if field not in columns:
        raise ValueError(f"Unknown field: {field}")
    tags: list[str] = []
    for value in tags_arg or []:
        tags.extend(parse_csv_list(str(value)))
    usage_obj = semantic_usage_object(role, ",".join(str(value) for value in (usages or [])))
    normalized_role = normalize_semantic_role(role)
    return {
        "tableKey": registry["table_key"],
        "tableName": registry["display_name"],
        "field": field,
        "role": normalized_role,
        "usage": usage_obj,
        "primaryUsage": primary_usage_from_object(usage_obj, normalized_role),
        "tags": sorted(set(tags)),
        "confidence": max(0.0, min(1.0, float(confidence))),
        "source": "manual",
        "note": note,
    }


def execute_semantic_set_plan(connection: sqlite3.Connection, proposed: dict[str, Any]) -> dict[str, Any]:
    upsert_semantic_config(connection, proposed, overwrite_manual=True)
    return proposed


def metric_key_for(table_key: str, label: str, measure: str, aggregation: str) -> str:
    return metric_key_for_service(table_key, label, measure, aggregation)


def metric_row_to_payload(row: sqlite3.Row, table_name: str | None = None) -> dict[str, Any]:
    return metric_row_to_payload_service(row, table_name)


def infer_metrics_for_table(connection: sqlite3.Connection, registry: sqlite3.Row) -> list[dict[str, Any]]:
    table_key = registry["table_key"]
    workspace_id = active_workspace_id(connection)
    fields = rows_to_dicts(
        connection.execute(
            """
            SELECT field_name, role, usage
            FROM field_semantics
            WHERE table_key = ? AND workspace_id = ?
            ORDER BY field_name
            """,
            (table_key, workspace_id),
        )
    )
    if not fields:
        for field in table_columns(connection, registry["physical_table"]):
            upsert_semantic_config(connection, infer_field_semantic_hybrid(connection, registry, field))
        fields = rows_to_dicts(
            connection.execute(
                """
                SELECT field_name, role, usage
                FROM field_semantics
                WHERE table_key = ? AND workspace_id = ?
                ORDER BY field_name
                """,
                (table_key, workspace_id),
            )
        )
    dimensions = [
        field["field_name"]
        for field in fields
        if not str(field["field_name"]).startswith("__")
        and (field["role"] in {"dimension", "status"} or field["usage"] == "groupable")
    ]
    time_fields = [field["field_name"] for field in fields if field["role"] == "event_time"]
    default_dimension = dimensions[0] if dimensions else None
    metrics: list[dict[str, Any]] = []
    for field in fields:
        if str(field["field_name"]).startswith("__"):
            continue
        if field["role"] != "measure" and field["usage"] != "aggregatable":
            continue
        label = f"{field['field_name']} 合计"
        metrics.append({
            "metricKey": f"{table_key}_{field['field_name']}_sum",
            "label": label,
            "tableKey": table_key,
            "measure": field["field_name"],
            "aggregation": "sum",
            "dimension": default_dimension,
            "timeField": time_fields[0] if time_fields else None,
            "valueFormat": "auto",
            "filters": [],
            "description": "Auto-inferred from field semantics.",
            "source": "auto",
        })
    count_label = "记录数"
    metrics.append({
        "metricKey": f"{table_key}_row_count",
        "label": count_label,
        "tableKey": table_key,
        "measure": "*",
        "aggregation": "count",
        "dimension": default_dimension,
        "timeField": time_fields[0] if time_fields else None,
        "valueFormat": "compact",
        "filters": [],
        "description": "Auto-inferred row count metric.",
        "source": "auto",
    })
    return metrics


def cleanup_stale_auto_metrics(connection: sqlite3.Connection, registries: list[sqlite3.Row], workspace_id: str) -> int:
    removed = 0
    for registry in registries:
        cursor = connection.execute(
            """
            DELETE FROM metric_definitions
            WHERE workspace_id = ?
              AND table_key = ?
              AND source = 'auto'
              AND measure <> '*'
              AND (
                substr(measure, 1, 2) = '__'
                OR NOT EXISTS (
                  SELECT 1
                  FROM field_semantics f
                  WHERE f.workspace_id = metric_definitions.workspace_id
                    AND f.table_key = metric_definitions.table_key
                    AND f.field_name = metric_definitions.measure
                    AND (f.role = 'measure' OR f.usage = 'aggregatable')
                )
              )
            """,
            (workspace_id, registry["table_key"]),
        )
        removed += max(cursor.rowcount, 0)
    return removed


def upsert_metric_definition(connection: sqlite3.Connection, metric: dict[str, Any]) -> dict[str, Any]:
    return upsert_metric_definition_service(
        connection,
        metric,
        resolve_table_registry=resolve_table_registry,
        table_columns=table_columns,
        active_workspace_id=active_workspace_id,
        now_iso=now_iso,
        safe_aggregations=SAFE_AGGREGATIONS,
    )


def infer_metrics_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        registries = [resolve_table_registry(connection, args.table)] if args.table else connection.execute("SELECT * FROM table_registry WHERE workspace_id = ? ORDER BY display_name", (workspace_id,)).fetchall()
        proposals: list[dict[str, Any]] = []
        saved: list[dict[str, Any]] = []
        removed_stale = 0
        for registry in registries:
            proposals.extend(infer_metrics_for_table(connection, registry))
        if args.yes:
            removed_stale = cleanup_stale_auto_metrics(connection, registries, workspace_id)
            for metric in proposals:
                saved.append(upsert_metric_definition(connection, metric))
            connection.commit()
    return {
        "ok": True,
        "dryRun": not args.yes,
        "requiresConfirmation": not args.yes,
        "proposed": len(proposals),
        "saved": len(saved),
        "removedStaleAutoMetrics": removed_stale,
        "metrics": saved if args.yes else proposals,
        "source": "infer-metrics adapted to workspace metric_definitions",
    }


def list_metrics_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        params: list[Any] = [workspace_id]
        clauses: list[str] = ["m.workspace_id = ?"]
        if args.table:
            registry = resolve_table_registry(connection, args.table)
            clauses.append("m.table_key = ?")
            params.append(registry["table_key"])
        if not args.all:
            clauses.append("m.enabled = 1")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = connection.execute(
            f"""
            SELECT m.*, COALESCE(t.display_name, m.table_key) AS table_name
            FROM metric_definitions m
            LEFT JOIN table_registry t ON t.table_key = m.table_key AND t.workspace_id = m.workspace_id
            {where}
            ORDER BY m.table_key, m.metric_key
            """,
            params,
        ).fetchall()
    metrics = [metric_row_to_payload(row, row["table_name"]) for row in rows]
    return {"ok": True, "metrics": metrics, "count": len(metrics)}


def metric_filters_from_cli(raw_filters: list[str]) -> list[dict[str, Any]]:
    return metric_filters_from_cli_service(raw_filters)


def build_metric_add_plan(
    connection: sqlite3.Connection,
    table_key: str,
    label: str,
    measure: str,
    aggregation: str,
    dimension: str = "",
    time_field: str = "",
    filters: list[dict[str, Any]] | None = None,
    value_format: str = "auto",
    description: str = "",
    metric_key: str = "",
) -> dict[str, Any]:
    return build_metric_add_plan_service(
        connection,
        table_key,
        label,
        measure,
        aggregation,
        dimension,
        time_field,
        filters,
        value_format,
        description,
        metric_key,
        resolve_table_registry=resolve_table_registry,
        table_columns=table_columns,
        safe_aggregations=SAFE_AGGREGATIONS,
    )


def execute_metric_add_plan(connection: sqlite3.Connection, proposed: dict[str, Any]) -> dict[str, Any]:
    return upsert_metric_definition(connection, proposed)


def add_metric_command(args: argparse.Namespace) -> dict[str, Any]:
    return add_metric_command_service(
        args,
        open_db=open_db,
        metric_filters_from_cli=metric_filters_from_cli,
        build_metric_add_plan=build_metric_add_plan,
        execute_metric_add_plan=execute_metric_add_plan,
    )


