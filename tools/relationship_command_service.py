from __future__ import annotations

import argparse
import json
import re
import sqlite3
from typing import Any, Callable

from bi_cli_core import now_iso, slug


def parse_json_object(value: Any, default: Any | None = None) -> Any:
    if value in (None, ""):
        return {} if default is None else default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return {} if default is None else default


def normalize_relation_field_name(value: str) -> str:
    text = re.sub(r"[\s_\-\.]+", "", str(value or "").strip().lower())
    replacements = {
        "订单编号": "orderid",
        "订单号": "orderid",
        "单号": "orderid",
        "退款单号": "refundid",
        "商品编码": "sku",
        "商家编码": "sku",
        "商品id": "sku",
        "sku编码": "sku",
        "渠道": "channel",
        "店铺": "shop",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    for suffix in ("key", "code", "number", "no", "编号", "编码", "号"):
        if text.endswith(suffix) and len(text) > len(suffix) + 2:
            text = text[: -len(suffix)]
    return text


def relation_candidate_fields(
    connection: sqlite3.Connection,
    registry: sqlite3.Row,
    *,
    active_workspace_id: Callable[[sqlite3.Connection], str],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
) -> list[dict[str, Any]]:
    columns = table_columns(connection, registry["physical_table"])
    workspace_id = active_workspace_id(connection)
    semantic_by_field = {
        row["field_name"]: dict(row)
        for row in connection.execute(
            """
            SELECT field_name, role, usage, confidence, tags_json, usage_json
            FROM field_semantics
            WHERE table_key = ? AND workspace_id = ?
            """,
            (registry["table_key"], workspace_id),
        ).fetchall()
    }
    candidates: list[dict[str, Any]] = []
    for field in columns:
        semantic = semantic_by_field.get(field, {})
        role = str(semantic.get("role") or "")
        usage = str(semantic.get("usage") or "")
        tags = parse_json_object(semantic.get("tags_json"), [])
        tags = tags if isinstance(tags, list) else []
        normalized = normalize_relation_field_name(field)
        text = field.lower()
        reasons: list[str] = []
        if role in {"identity_key", "identifier"}:
            reasons.append("identity-key")
        if usage == "joinable":
            reasons.append("semantic-joinable")
        if any(token in text for token in ("id", "key", "code", "sku", "order", "订单", "编号", "编码", "单号")):
            reasons.append("name-keyword")
        if any(tag in {"product", "talent", "order", "refund", "channel"} for tag in tags):
            reasons.append("semantic-tag")
        if reasons:
            candidates.append(
                {
                    "field": field,
                    "role": role,
                    "usage": usage,
                    "tags": tags,
                    "normalizedName": normalized,
                    "reasons": sorted(set(reasons)),
                    "confidence": float(semantic.get("confidence") or 0),
                }
            )
    return candidates


def relationship_name_score(left_field: str, right_field: str) -> tuple[int, list[str]]:
    left_name = normalize_relation_field_name(left_field)
    right_name = normalize_relation_field_name(right_field)
    score = 0
    reasons: list[str] = []
    if left_name and left_name == right_name:
        score += 72
        reasons.append("field-name-match")
    elif left_name and right_name and (left_name in right_name or right_name in left_name):
        score += 42
        reasons.append("field-name-contains")
    common_tokens = ("order", "refund", "sku", "product", "channel", "shop", "订单", "售后", "商品", "渠道", "店铺")
    shared = [token for token in common_tokens if token in left_name and token in right_name]
    if shared:
        score += min(28, 10 * len(shared))
        reasons.append(f"shared-business-token:{','.join(shared[:3])}")
    return score, reasons


def sample_field_values(
    connection: sqlite3.Connection,
    physical_table: str,
    field: str,
    limit: int = 300,
    *,
    quote_identifier: Callable[[str], str],
) -> set[str]:
    rows = connection.execute(
        f"""
        SELECT DISTINCT {quote_identifier(field)} AS value
        FROM {quote_identifier(physical_table)}
        WHERE {quote_identifier(field)} IS NOT NULL
          AND TRIM(CAST({quote_identifier(field)} AS TEXT)) <> ''
        LIMIT ?
        """,
        (max(1, int(limit)),),
    ).fetchall()
    return {str(row["value"]).strip() for row in rows if str(row["value"]).strip()}


def saved_relationship_signatures(
    connection: sqlite3.Connection,
    *,
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> set[tuple[str, str, str, str]]:
    signatures: set[tuple[str, str, str, str]] = set()
    workspace_id = active_workspace_id(connection)
    rows = connection.execute(
        """
        SELECT left_table_key, right_table_key, left_field, right_field
        FROM relationships
        WHERE workspace_id = ?
        """,
        (workspace_id,),
    ).fetchall()
    for row in rows:
        left_table = str(row["left_table_key"] or "")
        right_table = str(row["right_table_key"] or "")
        left_field = str(row["left_field"] or "")
        right_field = str(row["right_field"] or "")
        if left_table and right_table and left_field and right_field:
            signatures.add((left_table, right_table, left_field, right_field))
            signatures.add((right_table, left_table, right_field, left_field))
    return signatures


def recommend_relationships_for_connection(
    connection: sqlite3.Connection,
    limit: int = 12,
    *,
    active_workspace_id: Callable[[sqlite3.Connection], str],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    quote_identifier: Callable[[str], str],
    build_relationship_preview: Callable[..., dict[str, Any]],
    relation_candidate_fields: Callable[[sqlite3.Connection, sqlite3.Row], list[dict[str, Any]]],
    relationship_name_score: Callable[[str, str], tuple[int, list[str]]],
    sample_field_values: Callable[[sqlite3.Connection, str, str], set[str]],
    saved_relationship_signatures: Callable[[sqlite3.Connection], set[tuple[str, str, str, str]]],
) -> list[dict[str, Any]]:
    workspace_id = active_workspace_id(connection)
    registries = connection.execute(
        "SELECT * FROM table_registry WHERE workspace_id = ? ORDER BY table_key",
        (workspace_id,),
    ).fetchall()
    saved_signatures = saved_relationship_signatures(connection)
    candidates_by_table = {row["table_key"]: relation_candidate_fields(connection, row) for row in registries}
    value_cache: dict[tuple[str, str], set[str]] = {}
    recommendations: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for left_index, left in enumerate(registries):
        for right in registries[left_index + 1:]:
            left_table = left["table_key"]
            right_table = right["table_key"]
            for left_candidate in candidates_by_table.get(left_table, []):
                for right_candidate in candidates_by_table.get(right_table, []):
                    left_field = str(left_candidate["field"])
                    right_field = str(right_candidate["field"])
                    signature = (left_table, right_table, left_field, right_field)
                    if signature in seen:
                        continue
                    seen.add(signature)
                    score, reasons = relationship_name_score(left_field, right_field)
                    if left_candidate["role"] in {"identity_key", "identifier"} or right_candidate["role"] in {"identity_key", "identifier"}:
                        score += 18
                        reasons.append("identity-key")
                    if left_candidate["usage"] == "joinable" and right_candidate["usage"] == "joinable":
                        score += 18
                        reasons.append("both-joinable")
                    tag_overlap = sorted((set(left_candidate.get("tags") or []) & set(right_candidate.get("tags") or [])) - {"identifier"})
                    if tag_overlap:
                        score += min(18, 8 * len(tag_overlap))
                        reasons.append(f"tag-overlap:{','.join(tag_overlap[:3])}")
                    if score < 48:
                        continue
                    left_values = value_cache.setdefault((left["physical_table"], left_field), sample_field_values(connection, left["physical_table"], left_field))
                    right_values = value_cache.setdefault((right["physical_table"], right_field), sample_field_values(connection, right["physical_table"], right_field))
                    overlap_ratio = 0.0
                    if left_values and right_values:
                        overlap_ratio = len(left_values & right_values) / max(1, min(len(left_values), len(right_values)))
                    if overlap_ratio <= 0 and score < 78:
                        continue
                    if overlap_ratio > 0:
                        score += min(38, int(round(overlap_ratio * 38)))
                        reasons.append(f"sample-overlap:{round(overlap_ratio * 100)}%")
                    preview = build_relationship_preview(
                        connection,
                        left["physical_table"],
                        right["physical_table"],
                        table_columns(connection, left["physical_table"]),
                        table_columns(connection, right["physical_table"]),
                        [{"leftField": left_field, "rightField": right_field}],
                        join_type="left",
                        sample_limit=5,
                        quote_identifier=quote_identifier,
                    )
                    metrics = preview["metrics"]
                    actual_confidence = float(metrics.get("confidence") or 0)
                    overlap_keys = int(metrics.get("overlapKeys") or 0)
                    min_distinct_keys = min(int(metrics.get("leftDistinctKeys") or 0), int(metrics.get("rightDistinctKeys") or 0))
                    matched_left_rows = int(metrics.get("matchedLeftRows") or 0)
                    joined_rows = int(metrics.get("joinedRows") or 0)
                    join_multiplier = joined_rows / max(1, matched_left_rows)
                    if actual_confidence < 0.55 or overlap_keys <= 0 or min_distinct_keys < 3:
                        continue
                    if join_multiplier > 5:
                        continue
                    existing = signature in saved_signatures
                    recommendations.append(
                        {
                            "leftTableKey": left_table,
                            "leftTableName": left["display_name"],
                            "rightTableKey": right_table,
                            "rightTableName": right["display_name"],
                            "fieldMappings": [{"leftField": left_field, "rightField": right_field}],
                            "joinType": "left",
                            "score": score,
                            "confidence": round(min(0.99, actual_confidence + min(0.05, max(0, score - 90) / 1000)), 2),
                            "overlapRatio": round(overlap_ratio, 4),
                            "existing": existing,
                            "reasons": sorted(set(reasons)),
                            "previewMetrics": metrics,
                            "previewCommand": f"python tools/bi_cli.py --json relationship-preview --left-table {left_table} --right-table {right_table} --left-field {left_field} --right-field {right_field}",
                            "saveCommand": f"python tools/bi_cli.py --json relationship-save --left-table {left_table} --right-table {right_table} --left-field {left_field} --right-field {right_field} --yes",
                            "source": "recommend-relationships adapted to workspace relationship evidence",
                        }
                    )
    recommendations.sort(key=lambda item: (bool(item["existing"]), -float(item["confidence"]), -int(item["score"]), item["leftTableKey"], item["rightTableKey"]))
    return recommendations[: max(0, int(limit or 12))]


def recommend_relationships_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    recommend_relationships_for_connection: Callable[[sqlite3.Connection, int], list[dict[str, Any]]],
) -> dict[str, Any]:
    with open_db() as connection:
        recommendations = recommend_relationships_for_connection(connection, args.limit)
    return {
        "ok": True,
        "dryRun": True,
        "recommendations": recommendations,
        "count": len(recommendations),
        "source": "recommend-relationships integrated with workspace previews",
    }


def list_relationships_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        relationships = [
            dict(row)
            for row in connection.execute(
                """
                SELECT relation_key, workspace_id, name, left_table_key, right_table_key, left_field, right_field, join_type, confidence, created_at
                FROM relationships
                WHERE workspace_id = ?
                ORDER BY confidence DESC, created_at DESC, relation_key
                """,
                (workspace_id,),
            ).fetchall()
        ]
    return {"ok": True, "relationships": relationships}


def resolve_relationship_query_inputs(
    args: argparse.Namespace,
    connection: sqlite3.Connection,
    *,
    active_workspace_id: Callable[[sqlite3.Connection], str],
    registry_for_table: Callable[[sqlite3.Connection, str], sqlite3.Row | None],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
) -> dict[str, Any]:
    relation = None
    workspace_id = active_workspace_id(connection)
    if getattr(args, "relationship", ""):
        relation = connection.execute("SELECT * FROM relationships WHERE relation_key = ? AND workspace_id = ?", (args.relationship, workspace_id)).fetchone()
        if not relation:
            raise ValueError(f"Unknown relationship: {args.relationship}")
        left_table_key = relation["left_table_key"]
        right_table_key = relation["right_table_key"]
        left_field = relation["left_field"]
        right_field = relation["right_field"]
        join_type = relation["join_type"]
    else:
        left_table_key = args.left_table
        right_table_key = args.right_table
        left_field = args.left_field
        right_field = args.right_field
        join_type = args.join_type
        if not left_table_key or not right_table_key or not left_field or not right_field:
            raise ValueError("Use --relationship or provide --left-table, --right-table, --left-field and --right-field.")
    left = registry_for_table(connection, left_table_key)
    right = registry_for_table(connection, right_table_key)
    if not left or not right:
        raise ValueError("Unknown relationship table.")
    left_columns = table_columns(connection, left["physical_table"])
    right_columns = table_columns(connection, right["physical_table"])
    return {
        "relation": dict(relation) if relation else None,
        "leftTableKey": left_table_key,
        "rightTableKey": right_table_key,
        "leftPhysicalTable": left["physical_table"],
        "rightPhysicalTable": right["physical_table"],
        "leftColumns": left_columns,
        "rightColumns": right_columns,
        "mappings": [{"leftField": left_field, "rightField": right_field}],
        "joinType": join_type,
    }


def parse_relationship_filter(raw_filter: str) -> dict[str, Any]:
    parts = raw_filter.split(":", 3)
    if len(parts) == 4:
        side, field, operator, value = parts
    elif len(parts) == 3:
        side = ""
        field, operator, value = parts
    elif len(parts) == 2:
        side = ""
        field, operator = parts
        value = ""
    else:
        raise ValueError(f"Relationship filter must be side:field:operator:value or field:operator:value: {raw_filter}")
    return {
        "side": side.strip(),
        "field": field.strip(),
        "operator": operator.strip(),
        "value": value.strip(),
        "enabled": True,
    }


def to_number(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").replace(",", "").strip()
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def relationship_rows_for_chart(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    columns = payload.get("columns") if isinstance(payload.get("columns"), list) else []
    metric_name = str(payload.get("metricName") or (columns[-1] if columns else "value"))
    group_name = str(columns[0]) if len(columns) > 1 else ""
    chart_rows = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        label = str(row.get(group_name) if group_name else f"Row {index + 1}")
        value = row.get(metric_name, 0)
        chart_rows.append({
            "label": label,
            "value": to_number(value),
            "raw": row,
        })
    return chart_rows


def query_relationship_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    registry_for_table: Callable[[sqlite3.Connection, str], sqlite3.Row | None],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    parse_relationship_field_ref: Callable[[str], dict[str, str]],
    build_relationship_query: Callable[..., dict[str, Any]],
    quote_relationship_identifier: Callable[[str], str],
) -> dict[str, Any]:
    with open_db() as connection:
        resolved = resolve_relationship_query_inputs(
            args,
            connection,
            active_workspace_id=active_workspace_id,
            registry_for_table=registry_for_table,
            table_columns=table_columns,
        )
        group_fields = [parse_relationship_field_ref(item) for item in args.group]
        measure = parse_relationship_field_ref(args.measure) if args.measure else None
        filters = [parse_relationship_filter(item) for item in args.filter]
        payload = build_relationship_query(
            connection,
            resolved["leftPhysicalTable"],
            resolved["rightPhysicalTable"],
            resolved["leftColumns"],
            resolved["rightColumns"],
            resolved["mappings"],
            group_fields=group_fields,
            measure=measure,
            aggregation=args.agg,
            join_type=resolved["joinType"],
            filters=filters,
            limit=args.limit,
            sort_by=args.sort_by,
            sort_direction=args.sort_direction,
            quote_identifier=quote_relationship_identifier,
        )
    return {
        "ok": True,
        "relationship": {
            "relationKey": args.relationship or "",
            "leftTable": resolved["leftTableKey"],
            "rightTable": resolved["rightTableKey"],
            "fieldMappings": resolved["mappings"],
            "joinType": resolved["joinType"],
        },
        "relationshipQuery": payload,
        "query": {
            "table": f"{resolved['leftTableKey']}->{resolved['rightTableKey']}",
            "mode": "relationship",
            "group": payload["columns"][0] if len(payload["columns"]) > 1 else "",
            "measure": payload["metricName"],
            "aggregation": payload["aggregation"],
            "sqlIntent": "Whitelist relationship query; no user SQL accepted",
            "runtime": {"engine": "sqlite", "compiledSql": "relationship whitelist join"},
        },
        "rows": relationship_rows_for_chart(payload),
    }


def remove_relationship_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        row = connection.execute(
            "SELECT * FROM relationships WHERE relation_key = ? AND workspace_id = ?",
            (args.relationship, workspace_id),
        ).fetchone()
        if not row:
            raise ValueError(f"Unknown relationship: {args.relationship}")
        relationship = dict(row)
        if not args.yes:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "removedRelationship": relationship}
        connection.execute(
            "DELETE FROM relationships WHERE relation_key = ? AND workspace_id = ?",
            (args.relationship, workspace_id),
        )
        connection.commit()
    return {"ok": True, "confirmed": True, "removedRelationship": relationship}


def relationship_preview_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    registry_for_table: Callable[[sqlite3.Connection, str], sqlite3.Row | None],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    build_relationship_preview: Callable[..., dict[str, Any]],
    quote_identifier: Callable[[str], str],
) -> dict[str, Any]:
    with open_db() as connection:
        left = registry_for_table(connection, args.left_table)
        right = registry_for_table(connection, args.right_table)
        if not left or not right:
            raise ValueError("Unknown relationship table.")
        left_columns = table_columns(connection, left["physical_table"])
        right_columns = table_columns(connection, right["physical_table"])
        preview = build_relationship_preview(
            connection,
            left["physical_table"],
            right["physical_table"],
            left_columns,
            right_columns,
            [{"leftField": args.left_field, "rightField": args.right_field}],
            join_type=args.join_type,
            sample_limit=args.limit,
            quote_identifier=quote_identifier,
        )
    return {
        "ok": True,
        "dryRun": True,
        "relationship": {
            "leftTable": args.left_table,
            "rightTable": args.right_table,
            "leftField": args.left_field,
            "rightField": args.right_field,
            "joinType": args.join_type,
            "overlapCount": preview["metrics"]["overlapKeys"],
            "confidence": preview["metrics"]["confidence"],
        },
        "relationshipPreview": preview,
    }


def build_relationship_save_plan(
    connection: sqlite3.Connection,
    left_table: str,
    right_table: str,
    left_field: str,
    right_field: str,
    join_type: str = "left",
    limit: int = 20,
    *,
    registry_for_table: Callable[[sqlite3.Connection, str], sqlite3.Row | None],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    build_relationship_preview: Callable[..., dict[str, Any]],
    quote_identifier: Callable[[str], str],
) -> dict[str, Any]:
    left = registry_for_table(connection, left_table)
    right = registry_for_table(connection, right_table)
    if not left or not right:
        raise ValueError("Unknown relationship table.")
    left_columns = table_columns(connection, left["physical_table"])
    right_columns = table_columns(connection, right["physical_table"])
    preview = build_relationship_preview(
        connection,
        left["physical_table"],
        right["physical_table"],
        left_columns,
        right_columns,
        [{"leftField": left_field, "rightField": right_field}],
        join_type=join_type,
        sample_limit=limit,
        quote_identifier=quote_identifier,
    )
    relationship = {
        "leftTable": left_table,
        "rightTable": right_table,
        "leftField": left_field,
        "rightField": right_field,
        "joinType": join_type,
        "overlapCount": preview["metrics"]["overlapKeys"],
        "confidence": preview["metrics"]["confidence"],
    }
    relation_key = slug(f"{left_table}_{right_table}_{left_field}_{right_field}")
    proposed = {
        "relation_key": relation_key,
        "name": f"{left_table}.{left_field} -> {right_table}.{right_field}",
        "left_table_key": left_table,
        "right_table_key": right_table,
        "left_field": left_field,
        "right_field": right_field,
        "join_type": join_type,
        "confidence": relationship["confidence"],
    }
    return {"relationship": proposed, "relationshipPreview": preview}


def execute_relationship_save(
    connection: sqlite3.Connection,
    proposed: dict[str, Any],
    *,
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    workspace_id = active_workspace_id(connection)
    connection.execute(
        """
        INSERT OR REPLACE INTO relationships(relation_key, workspace_id, name, left_table_key, right_table_key, left_field, right_field, join_type, confidence, created_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            proposed["relation_key"],
            workspace_id,
            proposed["name"],
            proposed["left_table_key"],
            proposed["right_table_key"],
            proposed["left_field"],
            proposed["right_field"],
            proposed["join_type"],
            proposed["confidence"],
            now_iso(),
        ),
    )
    proposed["workspace_id"] = workspace_id
    return proposed


def relationship_save_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    build_relationship_save_plan: Callable[[sqlite3.Connection, str, str, str, str, str, int], dict[str, Any]],
    execute_relationship_save: Callable[[sqlite3.Connection, dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    limit = getattr(args, "limit", 20)
    with open_db() as connection:
        plan = build_relationship_save_plan(connection, args.left_table, args.right_table, args.left_field, args.right_field, args.join_type, limit)
        proposed = plan["relationship"]
        if not args.yes:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "relationship": proposed,
                "relationshipPreview": plan["relationshipPreview"],
            }
        saved = execute_relationship_save(connection, proposed)
        connection.commit()
    return {"ok": True, "saved": saved, "relationshipPreview": plan["relationshipPreview"]}
