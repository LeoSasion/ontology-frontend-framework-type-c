from __future__ import annotations

import json
from typing import Any, Callable

from query_runtime import cursor_rows


QuoteIdentifier = Callable[[str], str]
MAX_RELATIONSHIP_SAMPLE_ROWS = 500


def _preview_text_expression(alias: str, field: str, quote_identifier: QuoteIdentifier) -> str:
    return f"COALESCE(TRIM(CAST({alias}.{quote_identifier(field)} AS VARCHAR)), '')"


def _preview_numeric_expression(alias: str, field: str, quote_identifier: QuoteIdentifier) -> str:
    text = _preview_text_expression(alias, field, quote_identifier)
    return f"COALESCE(TRY_CAST(NULLIF(REPLACE({text}, ',', ''), '') AS DOUBLE), 0)"


def _preview_filter_sql(
    filters: list[dict[str, Any]],
    alias: str,
    quote_identifier: QuoteIdentifier,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    for item in filters:
        text = _preview_text_expression(alias, str(item["field"]), quote_identifier)
        numeric = _preview_numeric_expression(alias, str(item["field"]), quote_identifier)
        operator = str(item["operator"])
        value = item.get("value", "")
        if operator == "empty":
            clauses.append(f"{text} = ''")
        elif operator == "notEmpty":
            clauses.append(f"{text} <> ''")
        elif operator == "equals":
            clauses.append(f"{text} = ?")
            params.append(str(value))
        elif operator == "notEquals":
            clauses.append(f"{text} <> ?")
            params.append(str(value))
        elif operator == "contains":
            clauses.append(f"{text} LIKE '%' || ? || '%'")
            params.append(str(value))
        elif operator == "in":
            values = parse_filter_values(value)
            if values:
                clauses.append(f"{text} IN ({', '.join('?' for _ in values)})")
                params.extend(values)
        elif operator == "between":
            start, end = parse_range_values(value)
            if start:
                clauses.append(f"{numeric} >= ?")
                params.append(numeric_value(start))
            if end:
                clauses.append(f"{numeric} <= ?")
                params.append(numeric_value(end))
        else:
            comparison = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[operator]
            clauses.append(f"{numeric} {comparison} ?")
            params.append(numeric_value(value))
    return " AND ".join(clauses) or "TRUE", params


def _key_expressions(
    alias: str,
    mappings: list[dict[str, str]],
    side: str,
    quote_identifier: QuoteIdentifier,
) -> list[str]:
    field_key = "leftField" if side == "left" else "rightField"
    return [
        f"NULLIF({_preview_text_expression(alias, mapping[field_key], quote_identifier)}, '')"
        for mapping in mappings
    ]


def _projected_columns(
    alias: str,
    columns: list[str],
    quote_identifier: QuoteIdentifier,
) -> str:
    return ", ".join(
        f"{alias}.{quote_identifier(column)} AS {quote_identifier(column)}"
        for column in columns
    )


def _preaggregate_sql(
    source_name: str,
    config: dict[str, Any],
    quote_identifier: QuoteIdentifier,
) -> str:
    group_fields = list(config["groupFields"])
    select_parts = [f"r.{quote_identifier(field)} AS {quote_identifier(field)}" for field in group_fields]
    for item in config["measures"]:
        field = str(item["field"])
        aggregation = str(item["aggregation"])
        text = _preview_text_expression("r", field, quote_identifier)
        numeric = _preview_numeric_expression("r", field, quote_identifier)
        if aggregation == "count":
            expression = "COUNT(*)"
        elif aggregation == "count-distinct":
            expression = f"COUNT(DISTINCT NULLIF({text}, ''))"
        else:
            expression = f"{aggregation.upper()}({numeric})"
        select_parts.append(f"{expression} AS {quote_identifier(field)}")
    group_sql = ", ".join(f"r.{quote_identifier(field)}" for field in group_fields)
    return (
        f"SELECT {', '.join(select_parts)} FROM {source_name} AS r "
        f"GROUP BY {group_sql}"
    )


def build_relationship_preview(
    connection: Any,
    left_table_name: str,
    right_table_name: str,
    left_columns: list[str],
    right_columns: list[str],
    mappings: list[dict[str, str]],
    *,
    join_type: str,
    sample_limit: int,
    quote_identifier: QuoteIdentifier,
    filters: list[dict[str, Any]] | None = None,
    preaggregation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if join_type not in {"left", "inner"}:
        raise ValueError("关系预览只支持 left 或 inner。")
    if not mappings:
        raise ValueError("至少需要一组关联字段。")
    for mapping in mappings:
        if mapping["leftField"] not in left_columns:
            raise ValueError(f"左表字段不存在：{mapping['leftField']}")
        if mapping["rightField"] not in right_columns:
            raise ValueError(f"右表字段不存在：{mapping['rightField']}")

    normalized_filters = [
        item
        for item in (
            normalize_relationship_filter(filter_rule, left_columns, right_columns)
            for filter_rule in (filters or [])
        )
        if item is not None
    ]
    normalized_preaggregation = normalize_relationship_preaggregation(preaggregation, right_columns, mappings)
    left_pre = [item for item in normalized_filters if item["phase"] == "pre" and item["side"] == "left"]
    right_pre = [item for item in normalized_filters if item["phase"] == "pre" and item["side"] == "right"]
    left_predicate, left_params = _preview_filter_sql(left_pre, "l", quote_identifier)
    right_predicate, right_params = _preview_filter_sql(right_pre, "r", quote_identifier)
    left_needed = list(dict.fromkeys([
        *[item["leftField"] for item in mappings],
        *left_columns[:8],
    ]))
    right_needed = list(dict.fromkeys([
        *[item["rightField"] for item in mappings],
        *right_columns[:8],
        *(
            [*normalized_preaggregation["groupFields"], *[item["field"] for item in normalized_preaggregation["measures"]]]
            if normalized_preaggregation
            else []
        ),
    ]))
    left_projection = _projected_columns("l", left_needed, quote_identifier)
    right_projection = _projected_columns("r", right_needed, quote_identifier)
    right_effective_name = "right_effective" if normalized_preaggregation else "right_filtered"
    right_effective_cte = (
        ", right_effective AS MATERIALIZED ("
        + _preaggregate_sql("right_filtered", normalized_preaggregation, quote_identifier)
        + ")"
        if normalized_preaggregation
        else ""
    )
    left_key_exprs = _key_expressions("l", mappings, "left", quote_identifier)
    right_key_exprs = _key_expressions("r", mappings, "right", quote_identifier)
    left_key_select = ", ".join(
        f"{expression} AS {quote_identifier(f'__key_{index}')}"
        for index, expression in enumerate(left_key_exprs)
    )
    right_key_select = ", ".join(
        f"{expression} AS {quote_identifier(f'__key_{index}')}"
        for index, expression in enumerate(right_key_exprs)
    )
    left_usable = " AND ".join(f"{expression} IS NOT NULL" for expression in left_key_exprs)
    right_usable = " AND ".join(f"{expression} IS NOT NULL" for expression in right_key_exprs)
    key_names = [quote_identifier(f"__key_{index}") for index in range(len(mappings))]
    key_join = " AND ".join(f"l.{name} = r.{name}" for name in key_names)
    safe_sample_limit = max(1, min(int(sample_limit or 1), MAX_RELATIONSHIP_SAMPLE_ROWS))
    effective_right_columns = set(
        [*normalized_preaggregation["groupFields"], *[item["field"] for item in normalized_preaggregation["measures"]]]
        if normalized_preaggregation
        else right_columns
    )
    sample_select = [
        *[
            f"l.{quote_identifier(column)} AS {quote_identifier(f'left.{column}')}"
            for column in left_columns[:8]
        ],
        *[
            (
                f"r.{quote_identifier(column)}"
                if column in effective_right_columns
                else "NULL"
            ) + f" AS {quote_identifier(f'right.{column}')}"
            for column in right_columns[:8]
        ],
    ]
    representative_columns = [column for column in right_needed if column in effective_right_columns]
    representative_order = "hash(" + ", ".join(
        f"COALESCE(CAST(r.{quote_identifier(column)} AS VARCHAR), '')"
        for column in representative_columns
    ) + ")"
    right_representatives = ", ".join(
        f"first(r.{quote_identifier(column)} ORDER BY {representative_order}) AS {quote_identifier(column)}"
        for column in representative_columns
    )
    right_sample_select = f"{right_key_select}, {right_representatives}" if right_representatives else right_key_select
    sampled_key_join = " AND ".join(
        f"{right_key_exprs[index]} = k.{key_names[index]}"
        for index in range(len(key_names))
    )
    preview_key_join = " AND ".join(f"l.{name} = r.{name}" for name in key_names)
    sample_join = "JOIN" if join_type == "inner" else "LEFT JOIN"
    metric_sql = f"""
        WITH
        left_filtered AS MATERIALIZED (
          SELECT {left_projection}
          FROM {quote_identifier(left_table_name)} AS l
          WHERE {left_predicate}
        ),
        right_filtered AS MATERIALIZED (
          SELECT {right_projection}
          FROM {quote_identifier(right_table_name)} AS r
          WHERE {right_predicate}
        )
        {right_effective_cte},
        left_key_counts AS (
          SELECT {left_key_select}, COUNT(*)::BIGINT AS row_count
          FROM left_filtered AS l
          WHERE {left_usable}
          GROUP BY {', '.join(left_key_exprs)}
        ),
        right_key_counts AS (
          SELECT {right_key_select}, COUNT(*)::BIGINT AS row_count
          FROM {right_effective_name} AS r
          WHERE {right_usable}
          GROUP BY {', '.join(right_key_exprs)}
        ),
        matched AS (
          SELECT l.row_count AS left_count, r.row_count AS right_count
          FROM left_key_counts AS l
          JOIN right_key_counts AS r ON {key_join}
        ),
        matched_ranked AS (
          SELECT *,
            ROW_NUMBER() OVER (ORDER BY right_count) AS right_rank,
            ROW_NUMBER() OVER (ORDER BY left_count) AS left_rank,
            COUNT(*) OVER () AS overlap_count
          FROM matched
        ),
        matched_summary AS (
          SELECT
            COUNT(*)::BIGINT AS overlap_keys,
            COALESCE(SUM(left_count), 0)::BIGINT AS matched_left_rows,
            COALESCE(SUM(right_count), 0)::BIGINT AS matched_right_rows,
            COALESCE(SUM(left_count * right_count), 0)::BIGINT AS joined_rows,
            COALESCE(MAX(right_count), 0)::BIGINT AS max_right_rows_per_key,
            COALESCE(MAX(left_count), 0)::BIGINT AS max_left_rows_per_key,
            COALESCE(MAX(CASE WHEN right_rank = CAST(FLOOR(overlap_count * 0.95) AS BIGINT) + 1 THEN right_count END), 0)::BIGINT AS p95_right_rows_per_key,
            COALESCE(MAX(CASE WHEN left_rank = CAST(FLOOR(overlap_count * 0.95) AS BIGINT) + 1 THEN left_count END), 0)::BIGINT AS p95_left_rows_per_key
          FROM matched_ranked
        ),
        left_sample AS MATERIALIZED (
          SELECT l.*, {left_key_select}
          FROM left_filtered AS l
          WHERE {left_usable}
          LIMIT ?
        ),
        sample_keys AS (
          SELECT DISTINCT {', '.join(key_names)}
          FROM left_sample
        ),
        right_sample AS MATERIALIZED (
          SELECT {right_sample_select}
          FROM {right_effective_name} AS r
          JOIN sample_keys AS k ON {sampled_key_join}
          WHERE {right_usable}
          GROUP BY {', '.join(right_key_exprs)}
        ),
        preview_rows AS (
          SELECT 1 AS __sample_present, {', '.join(sample_select)}
          FROM left_sample AS l
          {sample_join} right_sample AS r ON {preview_key_join}
        ),
        metric_values AS (
          SELECT
            (SELECT COUNT(*) FROM {quote_identifier(left_table_name)})::BIGINT AS left_rows_before_filters,
            (SELECT COUNT(*) FROM {quote_identifier(right_table_name)})::BIGINT AS right_rows_before_filters,
            (SELECT COUNT(*) FROM left_filtered)::BIGINT AS left_rows,
            (SELECT COUNT(*) FROM {right_effective_name})::BIGINT AS right_rows,
            (SELECT COUNT(*) FROM left_key_counts)::BIGINT AS left_distinct_keys,
            (SELECT COUNT(*) FROM right_key_counts)::BIGINT AS right_distinct_keys,
            (SELECT COUNT(*) FROM left_key_counts WHERE row_count > 1)::BIGINT AS left_duplicate_key_groups,
            (SELECT COUNT(*) FROM right_key_counts WHERE row_count > 1)::BIGINT AS right_duplicate_key_groups,
            (SELECT COUNT(*) FROM left_filtered) - COALESCE((SELECT SUM(row_count) FROM left_key_counts), 0) AS left_empty_key_rows,
            (SELECT COUNT(*) FROM {right_effective_name}) - COALESCE((SELECT SUM(row_count) FROM right_key_counts), 0) AS right_empty_key_rows,
            matched_summary.*
          FROM matched_summary
        )
        SELECT metric_values.*, preview_rows.*
        FROM metric_values
        LEFT JOIN preview_rows ON TRUE
    """
    combined_rows = cursor_rows(connection.execute(
        metric_sql,
        [*left_params, *right_params, safe_sample_limit],
    ))
    metric_row = combined_rows[0]
    sample_rows = [
        {key: value for key, value in row.items() if key.startswith(("left.", "right."))}
        for row in combined_rows
        if row.get("__sample_present") is not None
    ]
    left_rows = int(metric_row["left_rows"] or 0)
    right_rows = int(metric_row["right_rows"] or 0)
    left_distinct_keys = int(metric_row["left_distinct_keys"] or 0)
    right_distinct_keys = int(metric_row["right_distinct_keys"] or 0)
    overlap_keys = int(metric_row["overlap_keys"] or 0)
    matched_left_rows = int(metric_row["matched_left_rows"] or 0)
    matched_right_rows = int(metric_row["matched_right_rows"] or 0)
    unmatched_left_rows = left_rows - matched_left_rows
    unmatched_right_rows = right_rows - matched_right_rows
    joined_rows = int(metric_row["joined_rows"] or 0)
    output_rows = joined_rows + (unmatched_left_rows if join_type == "left" else 0)
    reverse_output_rows = joined_rows + (unmatched_right_rows if join_type == "left" else 0)
    row_expansion = output_rows / max(1, left_rows)
    reverse_row_expansion = reverse_output_rows / max(1, right_rows)
    matched_row_expansion = joined_rows / max(1, matched_left_rows)
    reverse_matched_row_expansion = joined_rows / max(1, matched_right_rows)
    confidence = overlap_keys / max(1, min(left_distinct_keys, right_distinct_keys))

    return {
        "joinType": join_type,
        "mappings": mappings,
        "filters": normalized_filters,
        "preaggregation": normalized_preaggregation,
        "metrics": {
            "leftRowsBeforeFilters": int(metric_row["left_rows_before_filters"] or 0),
            "rightRowsBeforeFilters": int(metric_row["right_rows_before_filters"] or 0),
            "leftRows": left_rows,
            "rightRows": right_rows,
            "leftDistinctKeys": left_distinct_keys,
            "rightDistinctKeys": right_distinct_keys,
            "overlapKeys": overlap_keys,
            "matchedLeftRows": matched_left_rows,
            "matchedRightRows": matched_right_rows,
            "unmatchedLeftRows": unmatched_left_rows,
            "unmatchedRightRows": unmatched_right_rows,
            "joinedRows": joined_rows,
            "outputRows": output_rows,
            "rowExpansion": round(row_expansion, 4),
            "matchedRowExpansion": round(matched_row_expansion, 4),
            "reverseOutputRows": reverse_output_rows,
            "reverseRowExpansion": round(reverse_row_expansion, 4),
            "reverseMatchedRowExpansion": round(reverse_matched_row_expansion, 4),
            "maxRightRowsPerKey": int(metric_row["max_right_rows_per_key"] or 0),
            "p95RightRowsPerKey": int(metric_row["p95_right_rows_per_key"] or 0),
            "maxLeftRowsPerKey": int(metric_row["max_left_rows_per_key"] or 0),
            "p95LeftRowsPerKey": int(metric_row["p95_left_rows_per_key"] or 0),
            "leftDuplicateKeyGroups": int(metric_row["left_duplicate_key_groups"] or 0),
            "rightDuplicateKeyGroups": int(metric_row["right_duplicate_key_groups"] or 0),
            "leftEmptyKeyRows": int(metric_row["left_empty_key_rows"] or 0),
            "rightEmptyKeyRows": int(metric_row["right_empty_key_rows"] or 0),
            "confidence": round(confidence, 4),
        },
        "warnings": [
            *(
                ["左键存在重复组，关系可能放大明细行。"]
                if int(metric_row["left_duplicate_key_groups"] or 0)
                else []
            ),
            *(
                ["右键存在重复组，lookup 关系可能不稳定。"]
                if int(metric_row["right_duplicate_key_groups"] or 0)
                else []
            ),
            *(
                ["存在左表未匹配行，跨表指标需要标记覆盖率。"]
                if unmatched_left_rows
                else []
            ),
            *(
                ["存在右表未匹配行；反向遍历或右表指标可能遗漏迟到维度数据。"]
                if unmatched_right_rows
                else []
            ),
            *(
                [f"连接输出为左表的 {row_expansion:.2f} 倍，汇总前必须按目标粒度去重。"]
                if row_expansion > 1
                else []
            ),
        ],
        "rows": sample_rows,
    }


VALID_RELATION_AGGREGATIONS = {"count", "count-distinct", "sum", "avg", "min", "max"}
FILTER_OPERATOR_ALIASES = {
    "=": "equals",
    "equals": "equals",
    "!=": "notEquals",
    "notEquals": "notEquals",
    "not-equals": "notEquals",
    "contains": "contains",
    "in": "in",
    "between": "between",
    "gt": "gt",
    "gte": "gte",
    "lt": "lt",
    "lte": "lte",
    "empty": "empty",
    "notEmpty": "notEmpty",
    "not-empty": "notEmpty",
}
SIDE_ALIASES = {
    "left": "left",
    "l": "left",
    "左": "left",
    "左表": "left",
    "right": "right",
    "r": "right",
    "右": "right",
    "右表": "right",
}


def side_to_alias(side: str) -> str:
    normalized = SIDE_ALIASES.get(str(side).strip().lower())
    if normalized == "left":
        return "l"
    if normalized == "right":
        return "r"
    raise ValueError(f"字段来源必须是 left/right 或 左表/右表：{side}")


def side_label(alias: str) -> str:
    return "左表" if alias == "l" else "右表"


def qualified(alias: str, column: str, quote_identifier: QuoteIdentifier) -> str:
    return f"{alias}.{quote_identifier(column)}"


def parse_relationship_field_ref(raw: str) -> dict[str, str]:
    text = str(raw).strip()
    if not text:
        raise ValueError("字段引用不能为空")
    for separator in (":", ".", "："):
        if separator in text:
            side, field = [part.strip() for part in text.split(separator, 1)]
            return {"side": SIDE_ALIASES.get(side.lower(), side), "field": field}
    raise ValueError(f"字段引用格式错误：{raw}，应为 left:字段 或 right:字段")


def normalize_query_field(
    field_ref: dict[str, Any],
    left_columns: list[str],
    right_columns: list[str],
    label: str,
) -> dict[str, str]:
    if not isinstance(field_ref, dict):
        raise ValueError(f"{label}格式错误")
    alias = side_to_alias(str(field_ref.get("side", "")))
    field = str(field_ref.get("field", "")).strip()
    columns = left_columns if alias == "l" else right_columns
    if field not in columns:
        raise ValueError(f"{label}不存在：{side_label(alias)}.{field}")
    return {
        "side": "left" if alias == "l" else "right",
        "alias": alias,
        "field": field,
        "outputName": f"{side_label(alias)}.{field}",
    }


def numeric_expr(alias: str, field: str, quote_identifier: QuoteIdentifier) -> str:
    column = qualified(alias, field, quote_identifier)
    return f"CAST(NULLIF(REPLACE(TRIM(CAST({column} AS TEXT)), ',', ''), '') AS REAL)"


def parse_filter_values(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if str(item).strip()]
        except Exception:
            pass
    return [item.strip() for item in text.replace("，", ",").split(",") if item.strip()]


def parse_range_values(value: Any) -> tuple[str, str]:
    values = parse_filter_values(value)
    return (values[0] if len(values) >= 1 else "", values[1] if len(values) >= 2 else "")


def normalize_filter_operator(operator: str) -> str:
    normalized = FILTER_OPERATOR_ALIASES.get(str(operator or "").strip())
    if not normalized:
        raise ValueError(f"不支持的筛选操作符：{operator}")
    return normalized


def normalize_relationship_filter(
    filter_rule: dict[str, Any],
    left_columns: list[str],
    right_columns: list[str],
) -> dict[str, Any] | None:
    if not isinstance(filter_rule, dict):
        raise ValueError("筛选条件格式错误")
    if filter_rule.get("enabled", True) is False:
        return None
    field = str(filter_rule.get("field", "")).strip()
    if not field:
        return None
    phase = str(filter_rule.get("phase") or "post").strip().lower()
    if phase not in {"pre", "post"}:
        raise ValueError(f"筛选阶段必须是 pre 或 post：{phase}")
    operator = normalize_filter_operator(str(filter_rule.get("operator", "contains")))
    raw_side = str(filter_rule.get("side", "")).strip()
    if raw_side:
        alias = side_to_alias(raw_side)
        columns = left_columns if alias == "l" else right_columns
        if field not in columns:
            raise ValueError(f"筛选字段不存在：{side_label(alias)}.{field}")
    elif field in left_columns:
        alias = "l"
    elif field in right_columns:
        alias = "r"
    else:
        return None
    return {
        "alias": alias,
        "side": "left" if alias == "l" else "right",
        "field": field,
        "operator": operator,
        "value": filter_rule.get("value", ""),
        "phase": phase,
    }


def numeric_value(value: Any) -> float:
    try:
        return float(str(value or "0").replace(",", "").strip() or "0")
    except ValueError:
        return 0.0


VALID_PREAGGREGATIONS = {"count", "count-distinct", "sum", "avg", "min", "max"}


def normalize_relationship_preaggregation(
    value: dict[str, Any] | None,
    right_columns: list[str],
    mappings: list[dict[str, str]],
) -> dict[str, Any] | None:
    if not isinstance(value, dict) or not value:
        return None
    side = str(value.get("side") or "right").strip().lower()
    if side != "right":
        raise ValueError("当前只支持右表连接前预聚合。")
    group_fields = list(dict.fromkeys(str(item).strip() for item in value.get("groupFields", []) if str(item).strip()))
    mapping_fields = [item["rightField"] for item in mappings]
    if any(field not in right_columns for field in group_fields):
        raise ValueError("右表预聚合分组字段不存在。")
    if any(field not in group_fields for field in mapping_fields):
        raise ValueError("右表预聚合必须包含完整关系键。")
    measures: list[dict[str, str]] = []
    seen_fields: set[str] = set()
    for item in value.get("measures", []):
        if not isinstance(item, dict):
            continue
        field = str(item.get("field") or "").strip()
        aggregation = str(item.get("aggregation") or "sum").strip().lower()
        if not field or field in seen_fields:
            continue
        if field not in right_columns:
            raise ValueError(f"右表预聚合指标字段不存在：{field}")
        if aggregation not in VALID_PREAGGREGATIONS:
            raise ValueError(f"不支持的右表预聚合方式：{aggregation}")
        if field in group_fields:
            raise ValueError(f"右表预聚合字段不能同时作为分组和指标：{field}")
        seen_fields.add(field)
        measures.append({"field": field, "aggregation": aggregation})
    if not measures:
        raise ValueError("右表预聚合至少需要一个指标字段。")
    return {"side": "right", "groupFields": group_fields, "measures": measures}


def build_relationship_filter_sql(
    filters: list[dict[str, Any]] | None,
    left_columns: list[str],
    right_columns: list[str],
    quote_identifier: QuoteIdentifier,
) -> tuple[str, list[Any], list[dict[str, Any]]]:
    clauses: list[str] = []
    params: list[Any] = []
    applied_filters: list[dict[str, Any]] = []
    for filter_rule in filters or []:
        normalized = normalize_relationship_filter(filter_rule, left_columns, right_columns)
        if normalized is None:
            continue
        alias = normalized["alias"]
        field = normalized["field"]
        operator = normalized["operator"]
        value = normalized["value"]
        column_sql = qualified(alias, field, quote_identifier)
        if operator == "empty":
            clauses.append(f"({column_sql} IS NULL OR {column_sql} = '')")
        elif operator == "notEmpty":
            clauses.append(f"({column_sql} IS NOT NULL AND {column_sql} <> '')")
        elif operator == "equals":
            clauses.append(f"{column_sql} = ?")
            params.append(str(value))
        elif operator == "notEquals":
            clauses.append(f"{column_sql} <> ?")
            params.append(str(value))
        elif operator == "contains":
            clauses.append(f"{column_sql} LIKE ?")
            params.append(f"%{value}%")
        elif operator == "in":
            values = parse_filter_values(value)
            if not values:
                continue
            clauses.append(f"{column_sql} IN ({', '.join('?' for _ in values)})")
            params.extend(values)
        elif operator == "between":
            start, end = parse_range_values(value)
            if not start and not end:
                continue
            if start:
                clauses.append(f"{numeric_expr(alias, field, quote_identifier)} >= ?")
                params.append(start)
            if end:
                clauses.append(f"{numeric_expr(alias, field, quote_identifier)} <= ?")
                params.append(end)
        else:
            expression = numeric_expr(alias, field, quote_identifier)
            if operator == "gt":
                clauses.append(f"{expression} > ?")
            elif operator == "gte":
                clauses.append(f"{expression} >= ?")
            elif operator == "lt":
                clauses.append(f"{expression} < ?")
            else:
                clauses.append(f"{expression} <= ?")
            params.append(str(value))
        applied_filters.append({
            "phase": normalized["phase"],
            "side": normalized["side"],
            "field": field,
            "operator": operator,
            "value": value,
        })
    if not clauses:
        return "", [], applied_filters
    return " WHERE " + " AND ".join(clauses), params, applied_filters


def build_relation_condition_sql(mappings: list[dict[str, str]], quote_identifier: QuoteIdentifier) -> str:
    return " AND ".join(
        f"{qualified('l', item['leftField'], quote_identifier)} = {qualified('r', item['rightField'], quote_identifier)}"
        for item in mappings
    )


def relationship_query_row_to_dict(row: dict[str, Any], metric_name: str) -> dict[str, Any]:
    payload = {key: "" if value is None else value for key, value in row.items()}
    if metric_name in row:
        # Dimensions retain their legacy empty-string display contract, while
        # aggregate NULL must remain distinguishable from a verified zero.
        payload[metric_name] = row[metric_name]
    return payload


def build_relationship_query(
    connection: Any,
    left_table_name: str,
    right_table_name: str,
    left_columns: list[str],
    right_columns: list[str],
    mappings: list[dict[str, str]],
    *,
    group_fields: list[dict[str, Any]] | None = None,
    measure: dict[str, Any] | None = None,
    aggregation: str = "count",
    join_type: str = "left",
    filters: list[dict[str, Any]] | None = None,
    preaggregation: dict[str, Any] | None = None,
    deduplicate_left: bool = False,
    limit: int = 50,
    sort_by: str = "metric",
    sort_direction: str = "desc",
    quote_identifier: QuoteIdentifier,
) -> dict[str, Any]:
    if join_type not in {"left", "inner"}:
        raise ValueError("关系查询只支持 left 或 inner。")
    if aggregation not in VALID_RELATION_AGGREGATIONS:
        raise ValueError(f"不支持的聚合方式：{aggregation}")
    if sort_by not in {"metric", "dimension"}:
        raise ValueError(f"不支持的排序依据：{sort_by}")
    if sort_direction not in {"asc", "desc"}:
        raise ValueError(f"不支持的排序方向：{sort_direction}")
    if not mappings:
        raise ValueError("至少需要一组关联字段。")
    for mapping in mappings:
        if mapping["leftField"] not in left_columns:
            raise ValueError(f"左表字段不存在：{mapping['leftField']}")
        if mapping["rightField"] not in right_columns:
            raise ValueError(f"右表字段不存在：{mapping['rightField']}")

    normalized_filters = [
        item
        for item in (
            normalize_relationship_filter(filter_rule, left_columns, right_columns)
            for filter_rule in (filters or [])
        )
        if item is not None
    ]
    normalized_preaggregation = normalize_relationship_preaggregation(preaggregation, right_columns, mappings)
    effective_right_columns = (
        [*normalized_preaggregation["groupFields"], *[item["field"] for item in normalized_preaggregation["measures"]]]
        if normalized_preaggregation
        else right_columns
    )
    condition_sql = build_relation_condition_sql(mappings, quote_identifier)
    sql_join_type = "JOIN" if join_type == "inner" else "LEFT JOIN"
    safe_limit = max(1, min(int(limit or 50), 10000))
    normalized_groups = [
        normalize_query_field(item, left_columns, effective_right_columns, "分组字段")
        for item in (group_fields or [])
    ]
    select_parts = [
        f"{qualified(item['alias'], item['field'], quote_identifier)} AS {quote_identifier(item['outputName'])}"
        for item in normalized_groups
    ]
    group_sql = ""
    if normalized_groups:
        group_sql = " GROUP BY " + ", ".join(qualified(item["alias"], item["field"], quote_identifier) for item in normalized_groups)
    left_pre_filters = [item for item in normalized_filters if item["phase"] == "pre" and item["side"] == "left"]
    right_pre_filters = [item for item in normalized_filters if item["phase"] == "pre" and item["side"] == "right"]
    remaining_filters = [item for item in normalized_filters if item not in [*left_pre_filters, *right_pre_filters]]
    left_pre_where, left_pre_params, left_pre_applied = build_relationship_filter_sql(
        left_pre_filters,
        left_columns,
        right_columns,
        quote_identifier,
    )
    right_pre_where, right_pre_params, right_pre_applied = build_relationship_filter_sql(
        right_pre_filters,
        left_columns,
        right_columns,
        quote_identifier,
    )
    where_sql, filter_params, applied_filters = build_relationship_filter_sql(
        remaining_filters,
        left_columns,
        effective_right_columns,
        quote_identifier,
    )

    normalized_measure = None
    if aggregation == "count":
        metric_sql = "COUNT(*)"
        metric_name = "记录数"
    else:
        if not measure:
            raise ValueError(f"{aggregation} 聚合需要指定指标字段")
        normalized_measure = normalize_query_field(measure, left_columns, effective_right_columns, "指标字段")
        metric_name = f"{aggregation}_{normalized_measure['outputName']}"
        field_sql = qualified(normalized_measure["alias"], normalized_measure["field"], quote_identifier)
        numeric_sql = numeric_expr(normalized_measure["alias"], normalized_measure["field"], quote_identifier)
        if aggregation == "count-distinct":
            metric_sql = f"COUNT(DISTINCT {field_sql})"
        elif aggregation == "sum":
            metric_sql = f"SUM({numeric_sql})"
        elif aggregation == "avg":
            metric_sql = f"AVG({numeric_sql})"
        elif aggregation == "min":
            metric_sql = f"MIN({numeric_sql})"
        else:
            metric_sql = f"MAX({numeric_sql})"
    select_parts.append(f"{metric_sql} AS {quote_identifier(metric_name)}")
    order_field = normalized_groups[0]["outputName"] if sort_by == "dimension" and normalized_groups else metric_name
    order_sql = f" ORDER BY {quote_identifier(order_field)} {sort_direction.upper()}"
    right_source_sql = quote_identifier(right_table_name)
    if normalized_preaggregation:
        select_parts_right = [qualified("r", field, quote_identifier) for field in normalized_preaggregation["groupFields"]]
        for item in normalized_preaggregation["measures"]:
            field_sql = qualified("r", item["field"], quote_identifier)
            numeric_sql = numeric_expr("r", item["field"], quote_identifier)
            preaggregation_name = item["aggregation"]
            if preaggregation_name == "count":
                expression = "COUNT(*)"
            elif preaggregation_name == "count-distinct":
                expression = f"COUNT(DISTINCT {field_sql})"
            else:
                expression = f"{preaggregation_name.upper()}({numeric_sql})"
            select_parts_right.append(f"{expression} AS {quote_identifier(item['field'])}")
        group_right_sql = ", ".join(qualified("r", field, quote_identifier) for field in normalized_preaggregation["groupFields"])
        right_source_sql = (
            f"(SELECT {', '.join(select_parts_right)} FROM {quote_identifier(right_table_name)} AS r"
            f"{right_pre_where} GROUP BY {group_right_sql})"
        )
    elif right_pre_where:
        right_source_sql = f"(SELECT * FROM {quote_identifier(right_table_name)} AS r{right_pre_where})"
    left_source_sql = quote_identifier(left_table_name)
    if deduplicate_left:
        left_source_fields = list(dict.fromkeys([
            *[item["leftField"] for item in mappings],
            *[item["field"] for item in normalized_groups if item["side"] == "left"],
        ]))
        left_select_sql = ", ".join(qualified("l", field, quote_identifier) for field in left_source_fields)
        left_source_sql = (
            f"(SELECT {left_select_sql} FROM {quote_identifier(left_table_name)} AS l"
            f"{left_pre_where} GROUP BY {left_select_sql})"
        )
    elif left_pre_where:
        left_source_sql = f"(SELECT * FROM {quote_identifier(left_table_name)} AS l{left_pre_where})"
    sql = (
        f"SELECT {', '.join(select_parts)} "
        f"FROM {left_source_sql} AS l "
        f"{sql_join_type} {right_source_sql} AS r "
        f"ON {condition_sql}"
        f"{where_sql}{group_sql}{order_sql} LIMIT ?"
    )
    query_params = (*left_pre_params, *right_pre_params, *filter_params, safe_limit)
    rows = cursor_rows(connection.execute(sql, query_params))
    columns = [item["outputName"] for item in normalized_groups] + [metric_name]
    return {
        "leftTable": left_table_name,
        "rightTable": right_table_name,
        "joinType": join_type,
        "fieldMappings": mappings,
        "groups": [{"side": item["side"], "field": item["field"], "outputName": item["outputName"]} for item in normalized_groups],
        "measure": (
            {"side": normalized_measure["side"], "field": normalized_measure["field"], "outputName": normalized_measure["outputName"]}
            if normalized_measure
            else None
        ),
        "aggregation": aggregation,
        "filters": [*left_pre_applied, *right_pre_applied, *applied_filters],
        "preaggregation": normalized_preaggregation,
        "leftDeduplicated": deduplicate_left,
        "sortBy": sort_by,
        "sortDirection": sort_direction,
        "metricName": metric_name,
        "columns": columns,
        "rows": [relationship_query_row_to_dict(row, metric_name) for row in rows],
        "compiledSql": sql,
        "_compiledParams": list(query_params),
        "sqlShape": {
            "leftTable": left_table_name,
            "rightTable": right_table_name,
            "joinType": join_type,
            "groups": [item["outputName"] for item in normalized_groups],
            "measure": normalized_measure["outputName"] if normalized_measure else "",
            "aggregation": aggregation,
            "filters": [*left_pre_applied, *right_pre_applied, *applied_filters],
            "preaggregation": normalized_preaggregation,
            "leftDeduplicated": deduplicate_left,
            "limit": safe_limit,
        },
    }
