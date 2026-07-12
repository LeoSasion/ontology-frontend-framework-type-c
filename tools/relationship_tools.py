from __future__ import annotations

import json
from typing import Any, Callable


QuoteIdentifier = Callable[[str], str]


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def relationship_key(row: dict[str, Any], mappings: list[dict[str, str]], side: str) -> str | None:
    field_key = "leftField" if side == "left" else "rightField"
    values = [clean(row.get(mapping[field_key], "")) for mapping in mappings]
    if not values or all(value == "" for value in values):
        return None
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"))


def rows_for_table(connection: Any, table_name: str, columns: list[str], quote_identifier: QuoteIdentifier) -> list[dict[str, Any]]:
    select_sql = ", ".join(quote_identifier(column) for column in columns)
    return [dict(row) for row in connection.execute(f"SELECT {select_sql} FROM {quote_identifier(table_name)}")]


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

    left_rows = rows_for_table(connection, left_table_name, left_columns, quote_identifier)
    right_rows = rows_for_table(connection, right_table_name, right_columns, quote_identifier)
    left_stats = key_stats(left_rows, mappings, "left")
    right_stats = key_stats(right_rows, mappings, "right")
    left_keys = set(left_stats["counts"].keys())
    right_keys = set(right_stats["counts"].keys())
    overlap = left_keys & right_keys
    matched_left_rows = sum(left_stats["counts"][key] for key in overlap)
    unmatched_left_rows = len(left_rows) - matched_left_rows
    joined_rows = sum(left_stats["counts"][key] * right_stats["counts"][key] for key in overlap)
    output_rows = joined_rows + (unmatched_left_rows if join_type == "left" else 0)
    row_expansion = output_rows / max(1, len(left_rows))
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
        "metrics": {
            "leftRows": len(left_rows),
            "rightRows": len(right_rows),
            "leftDistinctKeys": len(left_keys),
            "rightDistinctKeys": len(right_keys),
            "overlapKeys": len(overlap),
            "matchedLeftRows": matched_left_rows,
            "unmatchedLeftRows": unmatched_left_rows,
            "joinedRows": joined_rows,
            "outputRows": output_rows,
            "rowExpansion": round(row_expansion, 4),
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
    return f"CAST(REPLACE(COALESCE({qualified(alias, field, quote_identifier)}, '0'), ',', '') AS REAL)"


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
    }


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
        applied_filters.append({"side": normalized["side"], "field": field, "operator": operator, "value": value})
    if not clauses:
        return "", [], applied_filters
    return " WHERE " + " AND ".join(clauses), params, applied_filters


def build_relation_condition_sql(mappings: list[dict[str, str]], quote_identifier: QuoteIdentifier) -> str:
    return " AND ".join(
        f"{qualified('l', item['leftField'], quote_identifier)} = {qualified('r', item['rightField'], quote_identifier)}"
        for item in mappings
    )


def sqlite_row_to_dict(row: Any) -> dict[str, Any]:
    if hasattr(row, "keys"):
        return {key: "" if row[key] is None else row[key] for key in row.keys()}
    return dict(row)


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

    condition_sql = build_relation_condition_sql(mappings, quote_identifier)
    sql_join_type = "JOIN" if join_type == "inner" else "LEFT JOIN"
    safe_limit = max(1, min(int(limit or 50), 10000))
    normalized_groups = [
        normalize_query_field(item, left_columns, right_columns, "分组字段")
        for item in (group_fields or [])
    ]
    select_parts = [
        f"{qualified(item['alias'], item['field'], quote_identifier)} AS {quote_identifier(item['outputName'])}"
        for item in normalized_groups
    ]
    group_sql = ""
    if normalized_groups:
        group_sql = " GROUP BY " + ", ".join(qualified(item["alias"], item["field"], quote_identifier) for item in normalized_groups)
    where_sql, filter_params, applied_filters = build_relationship_filter_sql(filters, left_columns, right_columns, quote_identifier)

    normalized_measure = None
    if aggregation == "count":
        metric_sql = "COUNT(*)"
        metric_name = "记录数"
    else:
        if not measure:
            raise ValueError(f"{aggregation} 聚合需要指定指标字段")
        normalized_measure = normalize_query_field(measure, left_columns, right_columns, "指标字段")
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
    sql = (
        f"SELECT {', '.join(select_parts)} "
        f"FROM {quote_identifier(left_table_name)} AS l "
        f"{sql_join_type} {quote_identifier(right_table_name)} AS r "
        f"ON {condition_sql}"
        f"{where_sql}{group_sql}{order_sql} LIMIT ?"
    )
    rows = connection.execute(sql, (*filter_params, safe_limit)).fetchall()
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
        "filters": applied_filters,
        "sortBy": sort_by,
        "sortDirection": sort_direction,
        "metricName": metric_name,
        "columns": columns,
        "rows": [sqlite_row_to_dict(row) for row in rows],
        "sqlShape": {
            "leftTable": left_table_name,
            "rightTable": right_table_name,
            "joinType": join_type,
            "groups": [item["outputName"] for item in normalized_groups],
            "measure": normalized_measure["outputName"] if normalized_measure else "",
            "aggregation": aggregation,
            "filters": applied_filters,
            "limit": safe_limit,
        },
    }
