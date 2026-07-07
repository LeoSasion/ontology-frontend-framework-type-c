from __future__ import annotations

import re
import sqlite3
from typing import Any

from formula_engine import ast_to_sql, parse_and_validate_formula


SAFE_AGGREGATIONS = {"count", "count-distinct", "sum", "avg", "min", "max"}
FILTER_OPERATORS = {"contains", "equals", "notEquals", "in", "between", "gt", "gte", "lt", "lte", "empty", "notEmpty"}


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def normalize_limit(value: Any, default: int = 50, maximum: int = 500) -> int:
    try:
        parsed = int(value if value is not None else default)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, maximum))


def normalize_offset(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def parse_csv(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in re.split(r"[,，]", str(value or "")) if item.strip()]


def normalize_columns(all_columns: list[str], raw_columns: Any) -> list[str]:
    usable = [column for column in all_columns if column != "id"]
    if raw_columns is None:
        return usable[:12]
    selected = []
    for column in parse_csv(raw_columns):
        if column not in usable:
            raise ValueError(f"Unknown column: {column}")
        if column not in selected:
            selected.append(column)
    return selected or usable[:12]


def normalize_filters(all_columns: list[str], raw_filters: Any) -> list[dict[str, Any]]:
    if raw_filters is None:
        return []
    if not isinstance(raw_filters, list):
        raise ValueError("filters must be an array")
    normalized = []
    for item in raw_filters:
        if not isinstance(item, dict):
            raise ValueError("filter must be an object")
        if item.get("enabled", True) is False:
            continue
        field = str(item.get("field") or "").strip()
        operator = str(item.get("operator") or "contains").strip()
        if not field:
            continue
        if field not in all_columns or field == "id":
            raise ValueError(f"Unknown filter field: {field}")
        if operator not in FILTER_OPERATORS:
            raise ValueError(f"Unsupported filter operator: {operator}")
        normalized.append({"field": field, "operator": operator, "value": item.get("value", "")})
    return normalized


def normalize_sort(all_columns: list[str], raw_sort: Any) -> list[dict[str, str]]:
    if raw_sort in (None, ""):
        return []
    if isinstance(raw_sort, dict):
        raw_sort = [raw_sort]
    if isinstance(raw_sort, str):
        field, _, direction = raw_sort.partition(":")
        raw_sort = [{"field": field, "direction": direction or "asc"}]
    if not isinstance(raw_sort, list):
        raise ValueError("sort must be an array")
    normalized = []
    for item in raw_sort:
        if not isinstance(item, dict):
            raise ValueError("sort item must be an object")
        field = str(item.get("field") or "").strip()
        direction = str(item.get("direction") or "asc").strip().lower()
        if not field:
            continue
        if field not in all_columns or field == "id":
            raise ValueError(f"Unknown sort field: {field}")
        if direction not in {"asc", "desc"}:
            raise ValueError(f"Unsupported sort direction: {direction}")
        normalized.append({"field": field, "direction": direction})
    return normalized


def numeric_expr(field: str) -> str:
    return f"CAST(NULLIF(REPLACE(TRIM(CAST({quote_identifier(field)} AS TEXT)), ',', ''), '') AS REAL)"


def is_numeric_column(connection: sqlite3.Connection, physical_table: str, field: str) -> bool:
    rows = connection.execute(
        f"""
        SELECT {quote_identifier(field)} AS value
        FROM {quote_identifier(physical_table)}
        WHERE {quote_identifier(field)} IS NOT NULL
          AND TRIM(CAST({quote_identifier(field)} AS TEXT)) <> ''
        LIMIT 80
        """
    ).fetchall()
    if not rows:
        return False
    numeric_count = 0
    for row in rows:
        text = str(row["value"]).strip().replace(",", "").replace("%", "")
        try:
            float(text)
        except ValueError:
            continue
        numeric_count += 1
    return numeric_count == len(rows)


def resolve_table_key(connection: sqlite3.Connection, physical_table: str, payload: dict[str, Any]) -> str:
    table_key = str(payload.get("tableKey") or payload.get("table_key") or "").strip()
    if table_key:
        return table_key
    row = connection.execute(
        "SELECT table_key FROM table_registry WHERE physical_table = ? LIMIT 1",
        (physical_table,),
    ).fetchone()
    return str(row["table_key"]) if row else physical_table


def calculated_field_rows(connection: sqlite3.Connection, table_key: str, enabled_only: bool = True) -> list[sqlite3.Row]:
    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'calculated_fields'"
    ).fetchone()
    if not exists:
        return []
    where = "WHERE table_key = ?"
    params: list[Any] = [table_key]
    if enabled_only:
        where += " AND enabled = 1"
    return connection.execute(
        f"""
        SELECT field_key, table_key, name, mode, formula_text, value_format, enabled
        FROM calculated_fields
        {where}
        ORDER BY name
        """,
        params,
    ).fetchall()


def analysis_field_names(connection: sqlite3.Connection, table_key: str, raw_columns: list[str]) -> list[str]:
    fields = [column for column in raw_columns if column != "id"]
    for row in calculated_field_rows(connection, table_key, enabled_only=True):
        name = str(row["name"] or "")
        if str(row["mode"] or "row") == "row" and name and name not in fields:
            fields.append(name)
    return fields


def calculated_field_map(connection: sqlite3.Connection, table_key: str) -> dict[str, sqlite3.Row]:
    return {
        str(row["name"]): row
        for row in calculated_field_rows(connection, table_key, enabled_only=True)
        if str(row["mode"] or "row") == "row"
    }


def calculated_field_expression(
    connection: sqlite3.Connection,
    table_key: str,
    field: str,
    raw_columns: list[str],
    *,
    visiting: set[str] | None = None,
) -> str:
    visiting = set(visiting or set())
    if field in visiting:
        raise ValueError(f"Calculated field cycle: {table_key}.{field}")
    field_map = calculated_field_map(connection, table_key)
    row = field_map.get(field)
    if not row:
        raise ValueError(f"Unknown calculated field: {table_key}.{field}")
    visiting.add(field)
    raw_fields = {column for column in raw_columns if column != "id"}
    peer_fields = set(field_map) - {field}
    expression = str(row["formula_text"] or "").strip()
    ast = parse_and_validate_formula(expression, mode="row", available_fields=raw_fields | peer_fields)

    def resolve_field(ref: str) -> str:
        if ref in raw_fields:
            return quote_identifier(ref)
        if ref in field_map:
            return f"({calculated_field_expression(connection, table_key, ref, raw_columns, visiting=visiting)})"
        raise ValueError(f"Unknown calculated field dependency: {table_key}.{field} -> {ref}")

    sql = ast_to_sql(ast, mode="row", resolve_field=resolve_field)
    visiting.remove(field)
    return sql


def field_expression(connection: sqlite3.Connection, table_key: str, field: str, raw_columns: list[str]) -> str:
    if field in raw_columns:
        return quote_identifier(field)
    return f"({calculated_field_expression(connection, table_key, field, raw_columns)})"


def numeric_field_expression(connection: sqlite3.Connection, table_key: str, field: str, raw_columns: list[str]) -> str:
    if field in raw_columns:
        return numeric_expr(field)
    return f"CAST(NULLIF(REPLACE(TRIM(CAST({field_expression(connection, table_key, field, raw_columns)} AS TEXT)), ',', ''), '') AS REAL)"


def is_numeric_analysis_field(connection: sqlite3.Connection, physical_table: str, table_key: str, field: str, raw_columns: list[str]) -> bool:
    if field in raw_columns:
        return is_numeric_column(connection, physical_table, field)
    expression = field_expression(connection, table_key, field, raw_columns)
    rows = connection.execute(
        f"""
        SELECT {expression} AS value
        FROM {quote_identifier(physical_table)}
        WHERE {expression} IS NOT NULL
        LIMIT 80
        """
    ).fetchall()
    if not rows:
        return False
    numeric_count = 0
    for row in rows:
        text = str(row["value"]).strip().replace(",", "").replace("%", "")
        try:
            float(text)
        except ValueError:
            continue
        numeric_count += 1
    return numeric_count == len(rows)


def filter_values(value: Any) -> list[str]:
    return parse_csv(value)


def where_sql(
    filters: list[dict[str, Any]],
    columns_for_search: list[str],
    search: Any,
    *,
    field_sql=quote_identifier,
    numeric_sql_for_field=numeric_expr,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    for item in filters:
        field = str(item["field"])
        operator = str(item["operator"])
        value = item.get("value", "")
        column_sql = field_sql(field)
        if operator == "contains":
            clauses.append(f"CAST({column_sql} AS TEXT) LIKE ?")
            params.append(f"%{value}%")
        elif operator == "equals":
            clauses.append(f"CAST({column_sql} AS TEXT) = ?")
            params.append(str(value))
        elif operator == "notEquals":
            clauses.append(f"CAST({column_sql} AS TEXT) <> ?")
            params.append(str(value))
        elif operator == "in":
            values = filter_values(value)
            if values:
                clauses.append(f"CAST({column_sql} AS TEXT) IN ({', '.join('?' for _ in values)})")
                params.extend(values)
        elif operator == "between":
            start, end = (filter_values(value) + ["", ""])[:2]
            if start and end:
                clauses.append(f"{numeric_sql_for_field(field)} BETWEEN ? AND ?")
                params.extend([start, end])
            elif start:
                clauses.append(f"{numeric_sql_for_field(field)} >= ?")
                params.append(start)
            elif end:
                clauses.append(f"{numeric_sql_for_field(field)} <= ?")
                params.append(end)
        elif operator in {"gt", "gte", "lt", "lte"}:
            symbol = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[operator]
            clauses.append(f"{numeric_sql_for_field(field)} {symbol} ?")
            params.append(value)
        elif operator == "empty":
            clauses.append(f"({column_sql} IS NULL OR TRIM(CAST({column_sql} AS TEXT)) = '')")
        elif operator == "notEmpty":
            clauses.append(f"({column_sql} IS NOT NULL AND TRIM(CAST({column_sql} AS TEXT)) <> '')")
    keyword = str(search or "").strip()
    if keyword and columns_for_search:
        search_parts = [f"CAST({field_sql(column)} AS TEXT) LIKE ?" for column in columns_for_search if column != "id"]
        if search_parts:
            clauses.append(f"({' OR '.join(search_parts)})")
            params.extend([f"%{keyword}%" for _ in search_parts])
    return (f" WHERE {' AND '.join(clauses)}" if clauses else "", params)


def build_detail_query(connection: sqlite3.Connection, physical_table: str, all_columns: list[str], payload: dict[str, Any]) -> dict[str, Any]:
    table_key = resolve_table_key(connection, physical_table, payload)
    raw_columns = [column for column in all_columns if column != "id"]
    analysis_columns = analysis_field_names(connection, table_key, raw_columns)
    selected_columns = normalize_columns(analysis_columns, payload.get("columns"))
    filters = normalize_filters(analysis_columns, payload.get("filters", []))
    sort = normalize_sort(analysis_columns, payload.get("sort", []))
    limit = normalize_limit(payload.get("limit"), default=50)
    offset = normalize_offset(payload.get("offset"))
    field_sql = lambda field: field_expression(connection, table_key, field, raw_columns)
    numeric_sql_for_field = lambda field: numeric_field_expression(connection, table_key, field, raw_columns)
    where, params = where_sql(
        filters,
        selected_columns,
        payload.get("search", ""),
        field_sql=field_sql,
        numeric_sql_for_field=numeric_sql_for_field,
    )
    order_parts = []
    for item in sort:
        expression = (
            numeric_sql_for_field(item["field"])
            if is_numeric_analysis_field(connection, physical_table, table_key, item["field"], raw_columns)
            else field_sql(item["field"])
        )
        order_parts.append(f"{expression} {item['direction'].upper()}")
    order = f" ORDER BY {', '.join(order_parts)}" if order_parts else ""
    select_sql = ", ".join(f"{field_sql(column)} AS {quote_identifier(column)}" for column in selected_columns)
    table_sql = quote_identifier(physical_table)
    total_rows = int(connection.execute(f"SELECT COUNT(*) FROM {table_sql}").fetchone()[0] or 0)
    filtered_rows = int(connection.execute(f"SELECT COUNT(*) FROM {table_sql}{where}", params).fetchone()[0] or 0)
    sql = f"SELECT {select_sql} FROM {table_sql}{where}{order} LIMIT ? OFFSET ?"
    rows = [dict(row) for row in connection.execute(sql, [*params, limit, offset])]
    return {
        "mode": "detail",
        "columns": selected_columns,
        "rows": rows,
        "totalRows": total_rows,
        "filteredRows": filtered_rows,
        "limit": limit,
        "offset": offset,
        "page": int(offset / limit) + 1,
        "pageCount": max(1, int((filtered_rows + limit - 1) / limit)),
        "filters": filters,
        "sort": sort,
        "search": str(payload.get("search") or "").strip(),
        "runtime": {"engine": "sqlite-detail", "compiledSql": sql, "params": [*params, limit, offset]},
    }


def normalize_groups(all_columns: list[str], raw_groups: Any) -> list[str]:
    groups = parse_csv(raw_groups)
    for group in groups:
        if group not in all_columns or group == "id":
            raise ValueError(f"Unknown group field: {group}")
    return groups[:3]


def aggregate_expr(aggregation: str, measure: str, *, field_sql=quote_identifier, numeric_sql_for_field=numeric_expr) -> tuple[str, str]:
    if aggregation not in SAFE_AGGREGATIONS:
        raise ValueError(f"Unsupported aggregation: {aggregation}")
    if aggregation == "count":
        return "COUNT(*)", "count"
    if not measure:
        raise ValueError(f"{aggregation} requires measure")
    if aggregation == "count-distinct":
        return f"COUNT(DISTINCT {field_sql(measure)})", f"count_distinct_{measure}"
    return f"{aggregation.upper()}({numeric_sql_for_field(measure)})", f"{aggregation}_{measure}"


def build_aggregate_query(connection: sqlite3.Connection, physical_table: str, all_columns: list[str], payload: dict[str, Any]) -> dict[str, Any]:
    table_key = resolve_table_key(connection, physical_table, payload)
    raw_columns = [column for column in all_columns if column != "id"]
    analysis_columns = analysis_field_names(connection, table_key, raw_columns)
    field_sql = lambda field: field_expression(connection, table_key, field, raw_columns)
    numeric_sql_for_field = lambda field: numeric_field_expression(connection, table_key, field, raw_columns)
    groups = normalize_groups(analysis_columns, payload.get("groupFields"))
    measure = str(payload.get("measure") or "").strip()
    aggregation = str(payload.get("aggregation") or "count").strip()
    if measure and measure not in analysis_columns:
        raise ValueError(f"Unknown measure field: {measure}")
    filters = normalize_filters(analysis_columns, payload.get("filters", []))
    sort = normalize_sort([*groups, aggregate_expr(aggregation, measure, field_sql=field_sql, numeric_sql_for_field=numeric_sql_for_field)[1]], payload.get("sort", []))
    limit = normalize_limit(payload.get("limit"), default=50)
    where, params = where_sql(
        filters,
        analysis_columns,
        payload.get("search", ""),
        field_sql=field_sql,
        numeric_sql_for_field=numeric_sql_for_field,
    )
    metric_sql, metric_name = aggregate_expr(aggregation, measure, field_sql=field_sql, numeric_sql_for_field=numeric_sql_for_field)
    select_parts = [f"{field_sql(group)} AS {quote_identifier(group)}" for group in groups]
    select_parts.append(f"{metric_sql} AS {quote_identifier(metric_name)}")
    group_sql = f" GROUP BY {', '.join(field_sql(group) for group in groups)}" if groups else ""
    order_sql = f" ORDER BY {quote_identifier(metric_name)} DESC" if groups and not sort else ""
    if sort:
        order_sql = f" ORDER BY {', '.join(f'{quote_identifier(item["field"])} {item["direction"].upper()}' for item in sort)}"
    table_sql = quote_identifier(physical_table)
    total_rows = int(connection.execute(f"SELECT COUNT(*) FROM {table_sql}").fetchone()[0] or 0)
    filtered_rows = int(connection.execute(f"SELECT COUNT(*) FROM {table_sql}{where}", params).fetchone()[0] or 0)
    sql = f"SELECT {', '.join(select_parts)} FROM {table_sql}{where}{group_sql}{order_sql} LIMIT ?"
    rows = [dict(row) for row in connection.execute(sql, [*params, limit])]
    return {
        "mode": "aggregate",
        "columns": [*groups, metric_name],
        "rows": rows,
        "totalRows": total_rows,
        "filteredRows": filtered_rows,
        "limit": limit,
        "groups": groups,
        "measure": measure,
        "aggregation": aggregation,
        "metricName": metric_name,
        "filters": filters,
        "sort": sort,
        "search": str(payload.get("search") or "").strip(),
        "runtime": {"engine": "sqlite-aggregate", "compiledSql": sql, "params": [*params, limit]},
    }


def build_table_query(connection: sqlite3.Connection, physical_table: str, all_columns: list[str], payload: dict[str, Any]) -> dict[str, Any]:
    mode = str(payload.get("mode") or "detail").strip().lower()
    if mode == "detail":
        return build_detail_query(connection, physical_table, all_columns, payload)
    if mode == "aggregate":
        return build_aggregate_query(connection, physical_table, all_columns, payload)
    raise ValueError(f"Unsupported query-table mode: {mode}")
