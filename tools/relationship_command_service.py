from __future__ import annotations

import argparse
import json
import re
import sqlite3
from contextlib import closing
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


def normalize_relationship_mappings(value: Any) -> list[dict[str, str]]:
    mappings: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        left_field = str(item.get("leftField") or item.get("left_field") or "").strip()
        right_field = str(item.get("rightField") or item.get("right_field") or "").strip()
        signature = (left_field, right_field)
        if not left_field or not right_field or signature in seen:
            continue
        seen.add(signature)
        mappings.append({"leftField": left_field, "rightField": right_field})
    return mappings


def relationship_mappings_from_args(args: argparse.Namespace) -> list[dict[str, str]]:
    raw_mappings: list[dict[str, str]] = []
    for raw_json in getattr(args, "map_json", []) or []:
        parsed = parse_json_object(raw_json, None)
        if not isinstance(parsed, dict):
            raise ValueError(f"Relationship mapping JSON must be an object: {raw_json}")
        raw_mappings.append(parsed)
    for raw in getattr(args, "map", []) or []:
        text = str(raw or "")
        if ":" not in text:
            raise ValueError(f"Relationship mapping must be leftField:rightField: {text}")
        left_field, right_field = text.split(":", 1)
        raw_mappings.append({"leftField": left_field, "rightField": right_field})
    left_field = str(getattr(args, "left_field", "") or "").strip()
    right_field = str(getattr(args, "right_field", "") or "").strip()
    if left_field or right_field:
        raw_mappings.insert(0, {"leftField": left_field, "rightField": right_field})
    mappings = normalize_relationship_mappings(raw_mappings)
    if not mappings:
        raise ValueError("Provide --left-field and --right-field, or one or more --map leftField:rightField values.")
    return mappings


def relationship_record_payload(value: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    payload = dict(value)
    mappings = normalize_relationship_mappings(parse_json_object(payload.get("mappings_json"), []))
    if not mappings:
        mappings = normalize_relationship_mappings(
            [{"leftField": payload.get("left_field"), "rightField": payload.get("right_field")}]
        )
    validation = parse_json_object(payload.get("validation_json"), {})
    filters = parse_json_object(payload.get("filters_json"), [])
    preaggregation = parse_json_object(payload.get("preaggregation_json"), {})
    payload["fieldMappings"] = mappings
    payload["validation"] = validation if isinstance(validation, dict) else {}
    payload["filters"] = filters if isinstance(filters, list) else []
    payload["preaggregation"] = preaggregation if isinstance(preaggregation, dict) else {}
    payload.pop("mappings_json", None)
    payload.pop("validation_json", None)
    payload.pop("filters_json", None)
    payload.pop("preaggregation_json", None)
    return payload


def relationship_validation_snapshot(preview: dict[str, Any]) -> dict[str, Any]:
    metrics = preview.get("metrics") if isinstance(preview.get("metrics"), dict) else {}
    blockers: list[str] = []
    if int(metrics.get("overlapKeys") or 0) <= 0:
        blockers.append("no-overlap")
    if float(metrics.get("confidence") or 0) < 0.55:
        blockers.append("low-confidence")
    expands = max(
        float(metrics.get("rowExpansion") or 0),
        float(metrics.get("matchedRowExpansion") or 0),
    ) > 1.000001
    # A genuine one-to-many edge is valid graph metadata; whether it is safe for
    # a particular metric is decided by the path proof. Only an expanding edge
    # with duplicate keys on both sides is intrinsically ambiguous here.
    if expands and int(metrics.get("leftDuplicateKeyGroups") or 0) > 0 and int(metrics.get("rightDuplicateKeyGroups") or 0) > 0:
        blockers.append("many-to-many-row-expansion")
    return {
        "schema": "aibi-relationship-validation/v1",
        "status": "validated" if not blockers else "review-required",
        "blockers": blockers,
        "metrics": metrics,
        "warnings": list(preview.get("warnings") or []),
        "filters": list(preview.get("filters") or []),
        "preaggregation": preview.get("preaggregation") or {},
        "validatedAt": now_iso(),
    }


def normalize_relation_field_name(value: str) -> str:
    text = re.sub(r"[\s_\-\.]+", "", str(value or "").strip().lower())
    replacements = {
        "唯一标识符": "identifier",
        "唯一标识": "identifier",
        "主键": "primarykey",
        "外键": "foreignkey",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    for suffix in ("identifier", "key", "code", "number", "no", "编号", "编码", "标识"):
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
        if any(token in text for token in ("id", "key", "code", "identifier", "编号", "编码", "标识", "主键", "外键")):
            reasons.append("name-keyword")
        if any(tag in {"identifier", "identity", "joinable", "primary-key", "foreign-key"} for tag in tags):
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
    structural_tokens = ("id", "key", "code", "identifier", "编号", "编码", "标识", "主键", "外键")
    shared = [token for token in structural_tokens if token in left_name and token in right_name]
    if shared:
        score += min(28, 10 * len(shared))
        reasons.append(f"shared-structural-token:{','.join(shared[:3])}")
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
            relationship_record_payload(row)
            for row in connection.execute(
                """
                SELECT *
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
        relation_payload = relationship_record_payload(relation)
        validation = relation_payload.get("validation") if isinstance(relation_payload.get("validation"), dict) else {}
        if validation.get("status") != "validated":
            raise ValueError(
                f"Relationship requires a current validated preview before querying: {args.relationship}"
            )
        mappings = relation_payload["fieldMappings"]
        join_type = relation["join_type"]
        saved_filters = relation_payload.get("filters") if isinstance(relation_payload.get("filters"), list) else []
        saved_preaggregation = relation_payload.get("preaggregation") if isinstance(relation_payload.get("preaggregation"), dict) else {}
    else:
        raise ValueError(
            "Relationship execution requires --relationship with a saved, currently validated relation. "
            "Use relationship-preview for unsaved mappings."
        )
    left = registry_for_table(connection, left_table_key)
    right = registry_for_table(connection, right_table_key)
    if not left or not right:
        raise ValueError("Unknown relationship table.")
    if relation:
        validation = relation_payload.get("validation") if isinstance(relation_payload.get("validation"), dict) else {}
        expected_versions = validation.get("dataVersions") if isinstance(validation.get("dataVersions"), dict) else {}
        current_versions = {
            str(left_table_key): int(left["data_version"] or 1),
            str(right_table_key): int(right["data_version"] or 1),
        }
        missing_version_tables = [key for key in current_versions if key not in expected_versions]
        if missing_version_tables:
            raise ValueError(
                "relationship-validation-missing-data-versions: "
                f"saved validation has no version evidence for {', '.join(missing_version_tables)}; "
                "preview and save the relationship again before querying."
            )
        try:
            version_mismatch = any(
                int(expected_versions.get(key)) != version for key, version in current_versions.items()
            )
        except (TypeError, ValueError):
            raise ValueError(
                "relationship-validation-invalid-data-versions: "
                "saved relationship version evidence is malformed; preview and save it again before querying."
            ) from None
        if version_mismatch:
            raise ValueError(f"Relationship validation is stale for current source versions: {args.relationship}")
    left_columns = table_columns(connection, left["physical_table"])
    right_columns = table_columns(connection, right["physical_table"])
    return {
        "relation": relationship_record_payload(relation) if relation else None,
        "leftTableKey": left_table_key,
        "rightTableKey": right_table_key,
        "leftPhysicalTable": left["physical_table"],
        "rightPhysicalTable": right["physical_table"],
        "leftColumns": left_columns,
        "rightColumns": right_columns,
        "mappings": mappings,
        "joinType": join_type,
        "savedFilters": saved_filters,
        "savedPreaggregation": saved_preaggregation,
        "validation": validation,
    }


def relationship_measure_fanout_proof(
    validation: dict[str, Any],
    measure: dict[str, Any] | None,
) -> dict[str, Any]:
    if not measure:
        return {
            "status": "not-applicable",
            "measureSide": "",
            "expansionMetric": "",
            "matchedRowExpansion": 1.0,
            "blockers": [],
        }
    side = str(measure.get("side") or "").strip().lower()
    if side not in {"left", "right"}:
        raise ValueError("relationship-measure-side-invalid: metric field must use left:field or right:field.")
    metrics = validation.get("metrics") if isinstance(validation.get("metrics"), dict) else {}
    expansion_metric = "matchedRowExpansion" if side == "left" else "reverseMatchedRowExpansion"
    if expansion_metric not in metrics:
        raise ValueError(
            "relationship-validation-missing-cardinality-evidence: "
            f"saved validation has no {expansion_metric} proof for a {side}-side measure; "
            "preview and save the relationship again before querying."
        )
    try:
        matched_row_expansion = float(metrics.get(expansion_metric))
    except (TypeError, ValueError):
        raise ValueError(
            "relationship-validation-invalid-cardinality-evidence: "
            f"saved {expansion_metric} proof is malformed; preview and save the relationship again before querying."
        ) from None
    if matched_row_expansion > 1.000001:
        raise ValueError(
            f"relationship-measure-fanout-risk:{side}: "
            f"{expansion_metric}={matched_row_expansion:g}; the join would repeat {side}-side metric rows. "
            "Use the many-side measure, or save a validated preaggregation that restores the metric grain."
        )
    return {
        "status": "safe",
        "measureSide": side,
        "expansionMetric": expansion_metric,
        "matchedRowExpansion": matched_row_expansion,
        "blockers": [],
    }


def parse_relationship_filter(raw_filter: str) -> dict[str, Any]:
    phase = "post"
    text = str(raw_filter or "")
    if text.startswith("pre:") or text.startswith("post:"):
        phase, text = text.split(":", 1)
    parts = text.split(":", 3)
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
        "phase": phase,
    }


def relationship_filters_from_args(args: argparse.Namespace) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = []
    for raw_json in getattr(args, "filter_json", []) or []:
        parsed = parse_json_object(raw_json, None)
        if not isinstance(parsed, dict):
            raise ValueError(f"Relationship filter JSON must be an object: {raw_json}")
        filters.append(parsed)
    filters.extend(parse_relationship_filter(item) for item in (getattr(args, "filter", []) or []))
    return filters


def relationship_preaggregation_from_args(args: argparse.Namespace) -> dict[str, Any] | None:
    raw = str(getattr(args, "preaggregate_json", "") or "").strip()
    if not raw:
        return None
    parsed = parse_json_object(raw, None)
    if not isinstance(parsed, dict):
        raise ValueError("Relationship preaggregation JSON must be an object.")
    return parsed


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
    aggregation = str(payload.get("aggregation") or "").strip().lower()
    groups = payload.get("groups") if isinstance(payload.get("groups"), list) else []
    group_names = [
        str(item.get("outputName") or "")
        for item in groups
        if isinstance(item, dict) and item.get("outputName")
    ]
    if not group_names and len(columns) > 1:
        group_names = [str(columns[0])]
    chart_rows = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        dimension_values = {
            name: row.get(name)
            for name in group_names
        }
        label_parts = [str(value) for value in dimension_values.values() if value is not None and str(value) != ""]
        label = " / ".join(label_parts) if label_parts else f"Row {index + 1}"
        raw_value = row.get(metric_name)
        if raw_value is None:
            value = 0.0 if aggregation in {"count", "count-distinct"} else None
        else:
            value = to_number(raw_value)
        chart_rows.append({
            "label": label,
            "value": value,
            **dimension_values,
            "dimensions": dimension_values,
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
    build_relationship_preview: Callable[..., dict[str, Any]],
    build_relationship_query: Callable[..., dict[str, Any]],
    quote_relationship_identifier: Callable[[str], str],
) -> dict[str, Any]:
    with closing(open_db()) as connection:
        # Keep validation, registry versions, physical-column discovery and the
        # compiled query on one stable SQLite snapshot. BEGIN IMMEDIATE also
        # prevents an import/replace writer from racing between proof and use.
        if connection.in_transaction:
            connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        resolved = resolve_relationship_query_inputs(
            args,
            connection,
            active_workspace_id=active_workspace_id,
            registry_for_table=registry_for_table,
            table_columns=table_columns,
        )
        group_fields = [parse_relationship_field_ref(item) for item in args.group]
        measure = parse_relationship_field_ref(args.measure) if args.measure else None
        runtime_filters = relationship_filters_from_args(args)
        runtime_preaggregation = relationship_preaggregation_from_args(args)
        filters = [*resolved["savedFilters"], *runtime_filters]
        preaggregation = runtime_preaggregation or resolved["savedPreaggregation"]
        definition_changed = bool(runtime_filters) or (
            runtime_preaggregation is not None
            and runtime_preaggregation != resolved["savedPreaggregation"]
        )
        proof_validation = resolved["validation"]
        validation_scope = "saved-relationship"
        if definition_changed:
            # Runtime filters/preaggregation change the cardinality surface that
            # the saved validation described. Recompute the exact effective
            # shape while the source-version lock is still held; never reuse a
            # safe saved proof for a different query definition.
            effective_preview = build_relationship_preview(
                connection,
                resolved["leftPhysicalTable"],
                resolved["rightPhysicalTable"],
                resolved["leftColumns"],
                resolved["rightColumns"],
                resolved["mappings"],
                join_type=resolved["joinType"],
                sample_limit=max(1, min(int(args.limit or 50), 50)),
                quote_identifier=quote_relationship_identifier,
                filters=filters,
                preaggregation=preaggregation,
            )
            proof_validation = {"metrics": effective_preview.get("metrics", {})}
            validation_scope = "effective-query-preview"
        fanout_proof = relationship_measure_fanout_proof(proof_validation, measure)
        fanout_proof["validationScope"] = validation_scope
        fanout_proof["runtimeFilterCount"] = len(runtime_filters)
        fanout_proof["runtimePreaggregationOverride"] = runtime_preaggregation is not None
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
            preaggregation=preaggregation,
            limit=args.limit,
            sort_by=args.sort_by,
            sort_direction=args.sort_direction,
            quote_identifier=quote_relationship_identifier,
        )
        payload["fanoutSafety"] = fanout_proof
    return {
        "ok": True,
        "relationship": {
            "relationKey": args.relationship or "",
            "leftTable": resolved["leftTableKey"],
            "rightTable": resolved["rightTableKey"],
            "fieldMappings": resolved["mappings"],
            "joinType": resolved["joinType"],
            "filters": payload["filters"],
            "preaggregation": payload["preaggregation"],
            "fanoutSafety": fanout_proof,
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
        relationship = relationship_record_payload(row)
        if not args.yes:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "removedRelationship": relationship}
        connection.execute(
            "DELETE FROM relationships WHERE relation_key = ? AND workspace_id = ?",
            (args.relationship, workspace_id),
        )
        connection.commit()
    return {"ok": True, "confirmed": True, "removedRelationship": relationship}


def _relationship_workspace_id(
    connection: sqlite3.Connection,
    args: argparse.Namespace,
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> str:
    workspace_id = str(getattr(args, "workspace", "") or "").strip() or active_workspace_id(connection)
    if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
        raise ValueError(f"Unknown workspace: {workspace_id}")
    return workspace_id


def _relationship_registry_for_workspace(
    connection: sqlite3.Connection,
    workspace_id: str,
    table_key: str,
) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM table_registry WHERE table_key = ? AND workspace_id = ?",
        (table_key, workspace_id),
    ).fetchone()


def relationship_preview_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    registry_for_table: Callable[[sqlite3.Connection, str], sqlite3.Row | None],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    build_relationship_preview: Callable[..., dict[str, Any]],
    quote_identifier: Callable[[str], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = _relationship_workspace_id(connection, args, active_workspace_id)
        left = _relationship_registry_for_workspace(connection, workspace_id, args.left_table)
        right = _relationship_registry_for_workspace(connection, workspace_id, args.right_table)
        if not left or not right:
            raise ValueError("Unknown relationship table.")
        left_columns = table_columns(connection, left["physical_table"])
        right_columns = table_columns(connection, right["physical_table"])
        mappings = relationship_mappings_from_args(args)
        filters = relationship_filters_from_args(args)
        preaggregation = relationship_preaggregation_from_args(args)
        preview = build_relationship_preview(
            connection,
            left["physical_table"],
            right["physical_table"],
            left_columns,
            right_columns,
            mappings,
            join_type=args.join_type,
            sample_limit=args.limit,
            quote_identifier=quote_identifier,
            filters=filters,
            preaggregation=preaggregation,
        )
    return {
        "ok": True,
        "workspaceId": workspace_id,
        "dryRun": True,
        "relationship": {
            "leftTable": args.left_table,
            "rightTable": args.right_table,
            "leftField": mappings[0]["leftField"],
            "rightField": mappings[0]["rightField"],
            "fieldMappings": mappings,
            "joinType": args.join_type,
            "overlapCount": preview["metrics"]["overlapKeys"],
            "confidence": preview["metrics"]["confidence"],
            "filters": preview["filters"],
            "preaggregation": preview["preaggregation"] or {},
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
    mappings: list[dict[str, str]] | None = None,
    filters: list[dict[str, Any]] | None = None,
    preaggregation: dict[str, Any] | None = None,
    workspace_id: str | None = None,
    *,
    registry_for_table: Callable[[sqlite3.Connection, str], sqlite3.Row | None],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    build_relationship_preview: Callable[..., dict[str, Any]],
    quote_identifier: Callable[[str], str],
) -> dict[str, Any]:
    left = (
        _relationship_registry_for_workspace(connection, workspace_id, left_table)
        if workspace_id
        else registry_for_table(connection, left_table)
    )
    right = (
        _relationship_registry_for_workspace(connection, workspace_id, right_table)
        if workspace_id
        else registry_for_table(connection, right_table)
    )
    if not left or not right:
        raise ValueError("Unknown relationship table.")
    left_columns = table_columns(connection, left["physical_table"])
    right_columns = table_columns(connection, right["physical_table"])
    normalized_mappings = normalize_relationship_mappings(
        mappings or [{"leftField": left_field, "rightField": right_field}]
    )
    if not normalized_mappings:
        raise ValueError("At least one complete relationship mapping is required.")
    preview = build_relationship_preview(
        connection,
        left["physical_table"],
        right["physical_table"],
        left_columns,
        right_columns,
        normalized_mappings,
        join_type=join_type,
        sample_limit=limit,
        quote_identifier=quote_identifier,
        filters=filters,
        preaggregation=preaggregation,
    )
    relationship = {
        "leftTable": left_table,
        "rightTable": right_table,
        "leftField": normalized_mappings[0]["leftField"],
        "rightField": normalized_mappings[0]["rightField"],
        "fieldMappings": normalized_mappings,
        "joinType": join_type,
        "overlapCount": preview["metrics"]["overlapKeys"],
        "confidence": preview["metrics"]["confidence"],
    }
    mapping_key = "_".join(f"{item['leftField']}_{item['rightField']}" for item in normalized_mappings)
    mapping_label = " + ".join(f"{item['leftField']}={item['rightField']}" for item in normalized_mappings)
    validation = relationship_validation_snapshot(preview)
    validation["dataVersions"] = {
        str(left["table_key"]): int(left["data_version"] or 1),
        str(right["table_key"]): int(right["data_version"] or 1),
    }
    relation_key = slug(f"{left_table}_{right_table}_{mapping_key}")
    proposed = {
        "relation_key": relation_key,
        "name": f"{left_table} -> {right_table} ({mapping_label})",
        "left_table_key": left_table,
        "right_table_key": right_table,
        "left_field": normalized_mappings[0]["leftField"],
        "right_field": normalized_mappings[0]["rightField"],
        "fieldMappings": normalized_mappings,
        "validation": validation,
        "join_type": join_type,
        "confidence": relationship["confidence"],
        "filters": preview["filters"],
        "preaggregation": preview["preaggregation"] or {},
    }
    return {"relationship": proposed, "relationshipPreview": preview}


def execute_relationship_save(
    connection: sqlite3.Connection,
    proposed: dict[str, Any],
    *,
    active_workspace_id: Callable[[sqlite3.Connection], str],
    workspace_id: str | None = None,
) -> dict[str, Any]:
    workspace_id = workspace_id or active_workspace_id(connection)
    timestamp = now_iso()
    connection.execute(
        """
        INSERT OR REPLACE INTO relationships(
          relation_key, workspace_id, name, left_table_key, right_table_key, left_field, right_field,
          mappings_json, filters_json, preaggregation_json, join_type, confidence, validation_json, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            proposed["relation_key"],
            workspace_id,
            proposed["name"],
            proposed["left_table_key"],
            proposed["right_table_key"],
            proposed["left_field"],
            proposed["right_field"],
            json.dumps(proposed["fieldMappings"], ensure_ascii=False),
            json.dumps(proposed["filters"], ensure_ascii=False),
            json.dumps(proposed["preaggregation"], ensure_ascii=False),
            proposed["join_type"],
            proposed["confidence"],
            json.dumps(proposed["validation"], ensure_ascii=False),
            timestamp,
            timestamp,
        ),
    )
    proposed["workspace_id"] = workspace_id
    return proposed


def relationship_save_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    build_relationship_save_plan: Callable[..., dict[str, Any]],
    execute_relationship_save: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    limit = getattr(args, "limit", 20)
    with open_db() as connection:
        workspace_id = _relationship_workspace_id(connection, args, active_workspace_id)
        mappings = relationship_mappings_from_args(args)
        filters = relationship_filters_from_args(args)
        preaggregation = relationship_preaggregation_from_args(args)
        plan = build_relationship_save_plan(
            connection,
            args.left_table,
            args.right_table,
            mappings[0]["leftField"],
            mappings[0]["rightField"],
            args.join_type,
            limit,
            mappings=mappings,
            filters=filters,
            preaggregation=preaggregation,
            workspace_id=workspace_id,
        )
        proposed = plan["relationship"]
        if not args.yes:
            return {
                "ok": True,
                "workspaceId": workspace_id,
                "dryRun": True,
                "requiresConfirmation": True,
                "relationship": proposed,
                "relationshipPreview": plan["relationshipPreview"],
            }
        saved = execute_relationship_save(connection, proposed, workspace_id=workspace_id)
        connection.commit()
    return {"ok": True, "workspaceId": workspace_id, "saved": saved, "relationshipPreview": plan["relationshipPreview"]}
