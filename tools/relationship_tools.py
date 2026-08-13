from __future__ import annotations

import json
from typing import Any, Callable

from query_runtime import cursor_rows


QuoteIdentifier = Callable[[str], str]


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def relationship_key(row: dict[str, Any], mappings: list[dict[str, str]], side: str) -> str | None:
    field_key = "leftField" if side == "left" else "rightField"
    values = [clean(row.get(mapping[field_key], "")) for mapping in mappings]
    # A composite key is only usable when every component is present. Treating
    # partially empty keys as values lets unrelated rows match on the remaining
    # empty components and creates false fan-out evidence.
    if not values or any(value == "" for value in values):
        return None
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"))


def rows_for_table(connection: Any, table_name: str, columns: list[str], quote_identifier: QuoteIdentifier) -> list[dict[str, Any]]:
    select_sql = ", ".join(quote_identifier(column) for column in columns)
    return cursor_rows(connection.execute(f"SELECT {select_sql} FROM {quote_identifier(table_name)}"))


def key_stats(rows: list[dict[str, Any]], mappings: list[dict[str, str]], side: str) -> dict[str, Any]:
    counts: dict[str, int] = {}
    empty_rows = 0
    for row in rows:
        key = relationship_key(row, mappings, side)
        if key is None:
            empty_rows += 1
            continue
        counts[key] = counts.get(key, 0) + 1
    duplicate_groups = sum(1 for count in counts.values() if count > 1)
    duplicate_rows = sum(count - 1 for count in counts.values() if count > 1)
    return {
        "rows": len(rows),
        "distinctKeys": len(counts),
        "emptyKeyRows": empty_rows,
        "duplicateKeyGroups": duplicate_groups,
        "duplicateRows": duplicate_rows,
        "counts": counts,
    }


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

    raw_left_rows = rows_for_table(connection, left_table_name, left_columns, quote_identifier)
    raw_right_rows = rows_for_table(connection, right_table_name, right_columns, quote_identifier)
    normalized_filters = [
        item
        for item in (
            normalize_relationship_filter(filter_rule, left_columns, right_columns)
            for filter_rule in (filters or [])
        )
        if item is not None
    ]
    left_rows = [
        row for row in raw_left_rows
        if all(
            relationship_filter_matches(row, item)
            for item in normalized_filters
            if item["phase"] == "pre" and item["side"] == "left"
        )
    ]
    right_rows = [
        row for row in raw_right_rows
        if all(
            relationship_filter_matches(row, item)
            for item in normalized_filters
            if item["phase"] == "pre" and item["side"] == "right"
        )
    ]
    normalized_preaggregation = normalize_relationship_preaggregation(preaggregation, right_columns, mappings)
    if normalized_preaggregation:
        right_rows = preaggregate_relationship_rows(right_rows, normalized_preaggregation)
    left_stats = key_stats(left_rows, mappings, "left")
    right_stats = key_stats(right_rows, mappings, "right")
    left_keys = set(left_stats["counts"].keys())
    right_keys = set(right_stats["counts"].keys())
    overlap = left_keys & right_keys
    matched_left_rows = sum(left_stats["counts"][key] for key in overlap)
    matched_right_rows = sum(right_stats["counts"][key] for key in overlap)
    unmatched_left_rows = len(left_rows) - matched_left_rows
    unmatched_right_rows = len(right_rows) - matched_right_rows
    joined_rows = sum(left_stats["counts"][key] * right_stats["counts"][key] for key in overlap)
    output_rows = joined_rows + (unmatched_left_rows if join_type == "left" else 0)
    row_expansion = output_rows / max(1, len(left_rows))
    reverse_output_rows = joined_rows + (unmatched_right_rows if join_type == "left" else 0)
    reverse_row_expansion = reverse_output_rows / max(1, len(right_rows))
    matched_row_expansion = joined_rows / max(1, matched_left_rows)
    reverse_matched_row_expansion = joined_rows / max(1, matched_right_rows)
    right_fanouts = sorted(right_stats["counts"].get(key, 0) for key in overlap)
    left_fanouts = sorted(left_stats["counts"].get(key, 0) for key in overlap)
    right_p95_index = max(0, min(len(right_fanouts) - 1, int(len(right_fanouts) * 0.95))) if right_fanouts else 0
    left_p95_index = max(0, min(len(left_fanouts) - 1, int(len(left_fanouts) * 0.95))) if left_fanouts else 0
    confidence = len(overlap) / max(1, min(len(left_keys), len(right_keys)))

    right_by_key: dict[str, dict[str, Any]] = {}
    for row in right_rows:
        key = relationship_key(row, mappings, "right")
        if key and key not in right_by_key:
            right_by_key[key] = row
    sample_rows: list[dict[str, Any]] = []
    for left_row in left_rows:
        key = relationship_key(left_row, mappings, "left")
        if not key:
            continue
        right_row = right_by_key.get(key)
        if not right_row and join_type == "inner":
            continue
        merged = {
            **{f"left.{column}": left_row.get(column) for column in left_columns[:8]},
            **({f"right.{column}": right_row.get(column) for column in right_columns[:8]} if right_row else {}),
        }
        sample_rows.append(merged)
        if len(sample_rows) >= sample_limit:
            break

    return {
        "joinType": join_type,
        "mappings": mappings,
        "filters": normalized_filters,
        "preaggregation": normalized_preaggregation,
        "metrics": {
            "leftRowsBeforeFilters": len(raw_left_rows),
            "rightRowsBeforeFilters": len(raw_right_rows),
            "leftRows": len(left_rows),
            "rightRows": len(right_rows),
            "leftDistinctKeys": len(left_keys),
            "rightDistinctKeys": len(right_keys),
            "overlapKeys": len(overlap),
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
            "maxRightRowsPerKey": max(right_fanouts, default=0),
            "p95RightRowsPerKey": right_fanouts[right_p95_index] if right_fanouts else 0,
            "maxLeftRowsPerKey": max(left_fanouts, default=0),
            "p95LeftRowsPerKey": left_fanouts[left_p95_index] if left_fanouts else 0,
            "leftDuplicateKeyGroups": left_stats["duplicateKeyGroups"],
            "rightDuplicateKeyGroups": right_stats["duplicateKeyGroups"],
            "leftEmptyKeyRows": left_stats["emptyKeyRows"],
            "rightEmptyKeyRows": right_stats["emptyKeyRows"],
            "confidence": round(confidence, 4),
        },
        "warnings": [
            *(
                ["左键存在重复组，关系可能放大明细行。"]
                if left_stats["duplicateKeyGroups"]
                else []
            ),
            *(
                ["右键存在重复组，lookup 关系可能不稳定。"]
                if right_stats["duplicateKeyGroups"]
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


def relationship_filter_matches(row: dict[str, Any], filter_rule: dict[str, Any]) -> bool:
    value = row.get(filter_rule["field"])
    text = clean(value)
    operator = filter_rule["operator"]
    expected = filter_rule.get("value", "")
    if operator == "empty":
        return text == ""
    if operator == "notEmpty":
        return text != ""
    if operator == "equals":
        return text == str(expected)
    if operator == "notEquals":
        return text != str(expected)
    if operator == "contains":
        return str(expected) in text
    if operator == "in":
        return text in parse_filter_values(expected)
    if operator == "between":
        start, end = parse_range_values(expected)
        number = numeric_value(value)
        return (not start or number >= numeric_value(start)) and (not end or number <= numeric_value(end))
    number = numeric_value(value)
    target = numeric_value(expected)
    if operator == "gt":
        return number > target
    if operator == "gte":
        return number >= target
    if operator == "lt":
        return number < target
    return number <= target


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


def preaggregate_relationship_rows(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    group_fields = config["groupFields"]
    for row in rows:
        key = tuple(clean(row.get(field)) for field in group_fields)
        grouped.setdefault(key, []).append(row)
    result: list[dict[str, Any]] = []
    for key, members in grouped.items():
        output = {field: key[index] for index, field in enumerate(group_fields)}
        for measure in config["measures"]:
            field = measure["field"]
            aggregation = measure["aggregation"]
            values = [numeric_value(member.get(field)) for member in members]
            if aggregation == "count":
                output[field] = len(members)
            elif aggregation == "count-distinct":
                output[field] = len({clean(member.get(field)) for member in members if clean(member.get(field))})
            elif aggregation == "sum":
                output[field] = sum(values)
            elif aggregation == "avg":
                output[field] = sum(values) / max(1, len(values))
            elif aggregation == "min":
                output[field] = min(values) if values else 0
            else:
                output[field] = max(values) if values else 0
        result.append(output)
    return result


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
