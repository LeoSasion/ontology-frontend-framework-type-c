from __future__ import annotations

import base64
import hashlib
import json
import re
import sqlite3
from typing import Any

from bi_cli_core import json_default
from dataset_version_store import INTERNAL_ROW_ID, schema_field_types
from formula_engine import ast_to_sql, parse_and_validate_formula
from query_runtime import SAFE_AGGREGATIONS, ValidatedDuckDBQuery, cursor_rows


FILTER_OPERATORS = {"contains", "equals", "notEquals", "in", "between", "gt", "gte", "lt", "lte", "empty", "notEmpty"}
DETAIL_CURSOR_VERSION = 1
DETAIL_CURSOR_DOMAIN = "aibi-c-detail-cursor-v1"
DETAIL_RESULT_MAX_BYTES = 1_000_000
AGGREGATE_RESULT_MAX_BYTES = 512_000
DETAIL_RESPONSE_MAX_BYTES = 1_250_000
AGGREGATE_RESPONSE_MAX_BYTES = 750_000
CURSOR_MAX_BYTES = 32_768
_CURSOR_PREFIX = "__aibi_cursor_"
_FILTERED_COUNT_COLUMN = "__aibi_filtered_rows"
_NUMERIC_TYPE = re.compile(r"^(?:U?(?:TINY|SMALL|BIG|HUGE)?INT(?:EGER)?|DECIMAL(?:\(\d+(?:,\d+)?\))?|NUMERIC(?:\(\d+(?:,\d+)?\))?|REAL|FLOAT|DOUBLE)$")
_TEMPORAL_TYPE = re.compile(r"^(?:DATE|TIME(?:STAMP)?(?: WITH TIME ZONE)?|INTERVAL)$")
_STRING_TYPES = {"VARCHAR", "TEXT", "STRING", "CHAR", "BPCHAR"}


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def normalize_limit(value: Any, default: int = 50, maximum: int = 500) -> int:
    try:
        parsed = int(value if value is not None else default)
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, maximum))


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=json_default, separators=(",", ":"))


def _cursor_checksum(payload: dict[str, Any]) -> str:
    material = f"{DETAIL_CURSOR_DOMAIN}:{_canonical_json(payload)}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def encode_detail_cursor(payload: dict[str, Any]) -> str:
    envelope = {"payload": payload, "checksum": _cursor_checksum(payload)}
    encoded = base64.urlsafe_b64encode(_canonical_json(envelope).encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")


def decode_detail_cursor(raw_cursor: Any) -> dict[str, Any] | None:
    cursor = str(raw_cursor or "").strip()
    if not cursor:
        return None
    if len(cursor.encode("utf-8")) > CURSOR_MAX_BYTES:
        raise ValueError("detail-query-cursor-too-large")
    try:
        padded = cursor + ("=" * (-len(cursor) % 4))
        envelope = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except (ValueError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("detail-query-cursor-invalid") from exc
    if not isinstance(envelope, dict) or not isinstance(envelope.get("payload"), dict):
        raise ValueError("detail-query-cursor-invalid")
    payload = envelope["payload"]
    if envelope.get("checksum") != _cursor_checksum(payload):
        raise ValueError("detail-query-cursor-invalid")
    if payload.get("version") != DETAIL_CURSOR_VERSION:
        raise ValueError("detail-query-cursor-version-unsupported")
    if payload.get("direction") not in {"next", "previous"}:
        raise ValueError("detail-query-cursor-invalid")
    if not isinstance(payload.get("boundary"), list):
        raise ValueError("detail-query-cursor-invalid")
    return payload


def _query_fingerprint(
    *,
    table_key: str,
    source_version: str,
    selected_columns: list[str],
    filters: list[dict[str, Any]],
    sort: list[dict[str, str]],
    search: str,
    limit: int,
) -> str:
    contract = {
        "tableKey": table_key,
        "sourceVersion": source_version,
        "columns": selected_columns,
        "filters": filters,
        "sort": sort,
        "search": search,
        "limit": limit,
    }
    return hashlib.sha256(_canonical_json(contract).encode("utf-8")).hexdigest()


def _expected_row_count(analysis_connection: ValidatedDuckDBQuery, payload: dict[str, Any]) -> int:
    raw_count = payload.get("expectedRowCount")
    if raw_count is None and analysis_connection.replicas:
        raw_count = analysis_connection.replicas[0].get("rowCount")
    if raw_count is None:
        raise ValueError("query-manifest-row-count-required")
    return max(0, int(raw_count))


def _stable_id_column(
    analysis_connection: ValidatedDuckDBQuery,
    physical_table: str,
    _all_columns: list[str],
) -> str:
    """Return the hidden tie-breaker used by the detail keyset cursor.

    Every clean-v2 relation carries ``__aibi_row_id``. Business identifiers are
    not necessarily unique, so falling back to one can silently skip rows.
    """

    try:
        description = analysis_connection.execute(
            f"DESCRIBE SELECT * FROM {quote_identifier(physical_table)}"
        ).fetchall()
    except Exception as exc:
        raise ValueError("detail-query-stable-id-required") from exc
    available = {str(row[0]) for row in description}
    if INTERNAL_ROW_ID in available:
        return INTERNAL_ROW_ID
    raise ValueError("detail-query-stable-id-required")


def _bounded_rows(rows: list[dict[str, Any]], maximum_bytes: int) -> tuple[list[dict[str, Any]], bool, int]:
    bounded: list[dict[str, Any]] = []
    used_bytes = 2
    for row in rows:
        row_bytes = len(_canonical_json(row).encode("utf-8")) + (1 if bounded else 0)
        if used_bytes + row_bytes > maximum_bytes:
            if not bounded:
                raise ValueError("query-result-row-exceeds-byte-limit")
            return bounded, True, used_bytes
        bounded.append(row)
        used_bytes += row_bytes
    return bounded, False, used_bytes


def _finalize_response(result: dict[str, Any], maximum_bytes: int) -> dict[str, Any]:
    result["responseBytes"] = 0
    for _ in range(4):
        measured_bytes = len(_canonical_json(result).encode("utf-8"))
        if result["responseBytes"] == measured_bytes:
            break
        result["responseBytes"] = measured_bytes
    if result["responseBytes"] > maximum_bytes:
        raise ValueError("query-result-exceeds-byte-limit")
    return result


def _keyset_predicate(
    aliases: list[str],
    directions: list[str],
    boundary: list[Any],
    relation: str,
) -> tuple[str, list[Any]]:
    if len(boundary) != len(aliases):
        raise ValueError("detail-query-cursor-boundary-invalid")
    branches: list[str] = []
    params: list[Any] = []
    for index, (alias, direction, value) in enumerate(zip(aliases, directions, boundary)):
        prefix: list[str] = []
        branch_params: list[Any] = []
        for prior_alias, prior_value in zip(aliases[:index], boundary[:index]):
            prefix.append(f"{quote_identifier(prior_alias)} IS NOT DISTINCT FROM ?")
            branch_params.append(prior_value)
        expression = quote_identifier(alias)
        if relation == "next":
            if value is None:
                comparator = "FALSE"
            else:
                symbol = ">" if direction == "asc" else "<"
                comparator = f"({expression} {symbol} ? OR {expression} IS NULL)"
                branch_params.append(value)
        else:
            if value is None:
                comparator = f"{expression} IS NOT NULL"
            else:
                symbol = "<" if direction == "asc" else ">"
                comparator = f"{expression} {symbol} ?"
                branch_params.append(value)
        branches.append(f"({' AND '.join([*prefix, comparator])})")
        params.extend(branch_params)
    return f" WHERE {' OR '.join(branches)}", params


def _unique_internal_alias(base: str, reserved: set[str]) -> str:
    candidate = base
    suffix = 0
    while candidate in reserved:
        suffix += 1
        candidate = f"{base}_{suffix}"
    reserved.add(candidate)
    return candidate


def parse_csv(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in re.split(r"[,，]", str(value or "")) if item.strip()]


def normalize_columns(all_columns: list[str], raw_columns: Any) -> list[str]:
    usable = [column for column in all_columns if not column.startswith("__aibi_")]
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
        if field not in all_columns or field.startswith("__aibi_"):
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
        if field not in all_columns or field.startswith("__aibi_"):
            raise ValueError(f"Unknown sort field: {field}")
        if direction not in {"asc", "desc"}:
            raise ValueError(f"Unsupported sort direction: {direction}")
        normalized.append({"field": field, "direction": direction})
    return normalized


def numeric_expr(field: str) -> str:
    return f"CAST(NULLIF(REPLACE(TRIM(CAST({quote_identifier(field)} AS TEXT)), ',', ''), '') AS REAL)"


def _is_numeric_type(data_type: str) -> bool:
    return bool(_NUMERIC_TYPE.fullmatch(str(data_type or "").strip().upper()))


def _is_temporal_type(data_type: str) -> bool:
    return bool(_TEMPORAL_TYPE.fullmatch(str(data_type or "").strip().upper()))


def _is_string_type(data_type: str) -> bool:
    normalized = str(data_type or "").strip().upper()
    return normalized in _STRING_TYPES or normalized.startswith("VARCHAR(") or normalized.startswith("CHAR(")


def _typed_parameter(data_type: str) -> str:
    normalized = str(data_type or "").strip().upper()
    if (_is_numeric_type(normalized) or _is_temporal_type(normalized) or normalized == "BOOLEAN") and re.fullmatch(r"[A-Z0-9_(), ]+", normalized):
        return f"TRY_CAST(? AS {normalized})"
    return "?"


def _registry_field_types(connection: sqlite3.Connection, table_key: str, physical_table: str) -> dict[str, str]:
    row = connection.execute(
        "SELECT schema_json FROM table_registry WHERE table_key = ? AND physical_table = ? ORDER BY updated_at DESC LIMIT 1",
        (table_key, physical_table),
    ).fetchone()
    return schema_field_types(row["schema_json"]) if row is not None else {}


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
    fields = [column for column in raw_columns if not column.startswith("__aibi_")]
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
    raw_fields = {column for column in raw_columns if not column.startswith("__aibi_")}
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


def numeric_field_expression(
    connection: sqlite3.Connection,
    table_key: str,
    field: str,
    raw_columns: list[str],
    field_types: dict[str, str],
) -> str:
    if field in raw_columns and _is_numeric_type(field_types.get(field, "")):
        return quote_identifier(field)
    if field in raw_columns:
        return numeric_expr(field)
    return f"CAST(NULLIF(REPLACE(TRIM(CAST({field_expression(connection, table_key, field, raw_columns)} AS TEXT)), ',', ''), '') AS REAL)"


def is_numeric_analysis_field(
    control_connection: sqlite3.Connection,
    analysis_connection: ValidatedDuckDBQuery,
    physical_table: str,
    table_key: str,
    field: str,
    raw_columns: list[str],
    field_types: dict[str, str],
) -> bool:
    if field in raw_columns:
        return _is_numeric_type(field_types.get(field, ""))
    expression = field_expression(control_connection, table_key, field, raw_columns)
    description = analysis_connection.execute(
        f"DESCRIBE SELECT {expression} AS value FROM {quote_identifier(physical_table)}"
    ).fetchone()
    return bool(description) and _is_numeric_type(str(description[1]))


def filter_values(value: Any) -> list[str]:
    return parse_csv(value)


def where_sql(
    filters: list[dict[str, Any]],
    columns_for_search: list[str],
    search: Any,
    *,
    field_sql=quote_identifier,
    numeric_sql_for_field=numeric_expr,
    field_types: dict[str, str] | None = None,
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    for item in filters:
        field = str(item["field"])
        operator = str(item["operator"])
        value = item.get("value", "")
        column_sql = field_sql(field)
        data_type = str((field_types or {}).get(field) or "").upper()
        parameter_sql = _typed_parameter(data_type)
        is_string = _is_string_type(data_type)
        if operator == "contains":
            clauses.append(f"{column_sql if is_string else f'CAST({column_sql} AS TEXT)'} LIKE ?")
            params.append(f"%{value}%")
        elif operator == "equals":
            clauses.append(f"{column_sql} = {parameter_sql}" if data_type else f"CAST({column_sql} AS TEXT) = ?")
            params.append(value if data_type else str(value))
        elif operator == "notEquals":
            clauses.append(f"{column_sql} <> {parameter_sql}" if data_type else f"CAST({column_sql} AS TEXT) <> ?")
            params.append(value if data_type else str(value))
        elif operator == "in":
            values = filter_values(value)
            if values:
                placeholders = ", ".join(parameter_sql for _ in values)
                clauses.append(f"{column_sql} IN ({placeholders})" if data_type else f"CAST({column_sql} AS TEXT) IN ({placeholders})")
                params.extend(values)
        elif operator == "between":
            start, end = (filter_values(value) + ["", ""])[:2]
            comparison_sql = column_sql if _is_temporal_type(data_type) else numeric_sql_for_field(field)
            if start and end:
                clauses.append(f"{comparison_sql} BETWEEN {parameter_sql} AND {parameter_sql}")
                params.extend([start, end])
            elif start:
                clauses.append(f"{comparison_sql} >= {parameter_sql}")
                params.append(start)
            elif end:
                clauses.append(f"{comparison_sql} <= {parameter_sql}")
                params.append(end)
        elif operator in {"gt", "gte", "lt", "lte"}:
            symbol = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[operator]
            comparison_sql = column_sql if _is_temporal_type(data_type) else numeric_sql_for_field(field)
            clauses.append(f"{comparison_sql} {symbol} {parameter_sql}")
            params.append(value)
        elif operator == "empty":
            clauses.append(f"{column_sql} IS NULL" if data_type and not is_string else f"({column_sql} IS NULL OR TRIM(CAST({column_sql} AS TEXT)) = '')")
        elif operator == "notEmpty":
            clauses.append(f"{column_sql} IS NOT NULL" if data_type and not is_string else f"({column_sql} IS NOT NULL AND TRIM(CAST({column_sql} AS TEXT)) <> '')")
    keyword = str(search or "").strip()
    if keyword and columns_for_search:
        search_parts = [
            f"{field_sql(column) if _is_string_type(str((field_types or {}).get(column) or '')) else f'CAST({field_sql(column)} AS TEXT)'} LIKE ?"
            for column in columns_for_search if not column.startswith("__aibi_")
        ]
        if search_parts:
            clauses.append(f"({' OR '.join(search_parts)})")
            params.extend([f"%{keyword}%" for _ in search_parts])
    return (f" WHERE {' AND '.join(clauses)}" if clauses else "", params)


def build_detail_query(
    control_connection: sqlite3.Connection,
    analysis_connection: ValidatedDuckDBQuery,
    physical_table: str,
    all_columns: list[str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    table_key = resolve_table_key(control_connection, physical_table, payload)
    raw_columns = [column for column in all_columns if not column.startswith("__aibi_")]
    field_types = _registry_field_types(control_connection, table_key, physical_table)
    analysis_columns = analysis_field_names(control_connection, table_key, raw_columns)
    selected_columns = normalize_columns(analysis_columns, payload.get("columns"))
    filters = normalize_filters(analysis_columns, payload.get("filters", []))
    sort = normalize_sort(analysis_columns, payload.get("sort", []))
    limit = normalize_limit(payload.get("limit"), default=50)
    replica_version = analysis_connection.replicas[0].get("versionId") if analysis_connection.replicas else ""
    source_version = str(payload.get("sourceVersion") or replica_version or "").strip()
    if not source_version:
        raise ValueError("detail-query-source-version-required")
    stable_id_column = _stable_id_column(analysis_connection, physical_table, all_columns)
    field_sql = lambda field: field_expression(control_connection, table_key, field, raw_columns)
    numeric_sql_for_field = lambda field: numeric_field_expression(control_connection, table_key, field, raw_columns, field_types)
    search = str(payload.get("search") or "").strip()
    where, params = where_sql(
        filters,
        selected_columns,
        search,
        field_sql=field_sql,
        numeric_sql_for_field=numeric_sql_for_field,
        field_types=field_types,
    )
    order_terms: list[dict[str, str]] = []
    for item in sort:
        expression = (
            numeric_sql_for_field(item["field"])
            if is_numeric_analysis_field(
                control_connection,
                analysis_connection,
                physical_table,
                table_key,
                item["field"],
                raw_columns,
                field_types,
            )
            else field_sql(item["field"])
        )
        order_terms.append({"expression": expression, "direction": item["direction"]})
    order_terms.append({"expression": quote_identifier(stable_id_column), "direction": "asc"})
    reserved_aliases = set(analysis_columns)
    cursor_aliases = [
        _unique_internal_alias(f"{_CURSOR_PREFIX}{index}", reserved_aliases)
        for index in range(len(order_terms))
    ]
    filtered_count_alias = _unique_internal_alias(_FILTERED_COUNT_COLUMN, reserved_aliases)
    directions = [item["direction"] for item in order_terms]
    fingerprint = _query_fingerprint(
        table_key=table_key,
        source_version=source_version,
        selected_columns=selected_columns,
        filters=filters,
        sort=sort,
        search=search,
        limit=limit,
    )
    cursor_payload = decode_detail_cursor(payload.get("cursor"))
    if cursor_payload:
        if cursor_payload.get("sourceVersion") != source_version:
            raise ValueError("detail-query-cursor-stale")
        if cursor_payload.get("queryFingerprint") != fingerprint:
            raise ValueError("detail-query-cursor-scope-mismatch")
        if len(cursor_payload["boundary"]) != len(cursor_aliases):
            raise ValueError("detail-query-cursor-boundary-invalid")
    direction = str(cursor_payload.get("direction")) if cursor_payload else "next"
    page = max(1, int(cursor_payload.get("page") or 1)) if cursor_payload else 1
    total_rows = _expected_row_count(analysis_connection, payload)
    filtered_hint = int(cursor_payload.get("filteredRows") or 0) if cursor_payload else None
    needs_filtered_count = bool(filters or search) and cursor_payload is None
    selected_sql = [f"{field_sql(column)} AS {quote_identifier(column)}" for column in selected_columns]
    hidden_sql = [
        f"{term['expression']} AS {quote_identifier(alias)}"
        for term, alias in zip(order_terms, cursor_aliases)
    ]
    if needs_filtered_count:
        hidden_sql.append(f"COUNT(*) OVER () AS {quote_identifier(filtered_count_alias)}")
    select_sql = ", ".join([*selected_sql, *hidden_sql])
    table_sql = quote_identifier(physical_table)
    cursor_where = ""
    cursor_params: list[Any] = []
    if cursor_payload:
        cursor_where, cursor_params = _keyset_predicate(
            cursor_aliases,
            directions,
            cursor_payload["boundary"],
            direction,
        )
    if direction == "previous":
        order_sql = ", ".join(
            f"{quote_identifier(alias)} {'DESC' if item['direction'] == 'asc' else 'ASC'} NULLS FIRST"
            for item, alias in zip(order_terms, cursor_aliases)
        )
    else:
        order_sql = ", ".join(
            f"{quote_identifier(alias)} {item['direction'].upper()} NULLS LAST"
            for item, alias in zip(order_terms, cursor_aliases)
        )
    sql = (
        f"WITH {quote_identifier('__aibi_filtered')} AS ("
        f"SELECT {select_sql} FROM {table_sql}{where}"
        f") SELECT * FROM {quote_identifier('__aibi_filtered')}"
        f"{cursor_where} ORDER BY {order_sql} LIMIT ?"
    )
    query_params = [*params, *cursor_params, limit + 1]
    fetched_rows = cursor_rows(analysis_connection.execute(sql, query_params))
    has_extra = len(fetched_rows) > limit
    page_rows = fetched_rows[:limit]
    if direction == "previous":
        page_rows.reverse()
    if needs_filtered_count:
        filtered_rows = int(page_rows[0].get(filtered_count_alias) or 0) if page_rows else 0
    elif filtered_hint is not None:
        filtered_rows = filtered_hint
    else:
        filtered_rows = total_rows
    visible_with_boundaries: list[tuple[dict[str, Any], list[Any]]] = []
    for row in page_rows:
        visible = {column: row.get(column) for column in selected_columns}
        boundary = [row.get(alias) for alias in cursor_aliases]
        visible_with_boundaries.append((visible, boundary))
    bounded_visible, truncated_by_bytes, row_bytes = _bounded_rows(
        [item[0] for item in visible_with_boundaries],
        DETAIL_RESULT_MAX_BYTES,
    )
    emitted = visible_with_boundaries[:len(bounded_visible)]
    has_previous = (direction == "next" and page > 1) or (direction == "previous" and has_extra)
    has_next = (direction == "previous" and bool(cursor_payload)) or has_extra or truncated_by_bytes

    def page_cursor(edge: str, boundary: list[Any], target_page: int) -> str:
        return encode_detail_cursor({
            "version": DETAIL_CURSOR_VERSION,
            "sourceVersion": source_version,
            "queryFingerprint": fingerprint,
            "direction": edge,
            "page": target_page,
            "filteredRows": filtered_rows,
            "boundary": boundary,
        })

    previous_cursor = (
        page_cursor("previous", emitted[0][1], max(1, page - 1))
        if has_previous and emitted else None
    )
    next_cursor = (
        page_cursor("next", emitted[-1][1], page + 1)
        if has_next and emitted else None
    )
    result = {
        "mode": "detail",
        "columns": selected_columns,
        "rows": bounded_visible,
        "totalRows": total_rows,
        "filteredRows": filtered_rows,
        "limit": limit,
        "page": page,
        "pageCount": max(1, int((filtered_rows + limit - 1) / limit)),
        "nextCursor": next_cursor,
        "previousCursor": previous_cursor,
        "hasNextPage": bool(next_cursor),
        "hasPreviousPage": bool(previous_cursor),
        "sourceVersion": source_version,
        "queryFingerprint": fingerprint,
        "rowBytes": row_bytes,
        "truncatedByBytes": truncated_by_bytes,
        "filters": filters,
        "sort": sort,
        "search": search,
        "runtime": analysis_connection.runtime(compiled_sql=sql, params=query_params),
    }
    return _finalize_response(result, DETAIL_RESPONSE_MAX_BYTES)


def normalize_groups(all_columns: list[str], raw_groups: Any) -> list[str]:
    groups = parse_csv(raw_groups)
    for group in groups:
        if group not in all_columns or group.startswith("__aibi_"):
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


def build_aggregate_query(
    control_connection: sqlite3.Connection,
    analysis_connection: ValidatedDuckDBQuery,
    physical_table: str,
    all_columns: list[str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    table_key = resolve_table_key(control_connection, physical_table, payload)
    raw_columns = [column for column in all_columns if not column.startswith("__aibi_")]
    field_types = _registry_field_types(control_connection, table_key, physical_table)
    analysis_columns = analysis_field_names(control_connection, table_key, raw_columns)
    field_sql = lambda field: field_expression(control_connection, table_key, field, raw_columns)
    numeric_sql_for_field = lambda field: numeric_field_expression(control_connection, table_key, field, raw_columns, field_types)
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
        field_types=field_types,
    )
    metric_sql, metric_name = aggregate_expr(aggregation, measure, field_sql=field_sql, numeric_sql_for_field=numeric_sql_for_field)
    select_parts = [f"{field_sql(group)} AS {quote_identifier(group)}" for group in groups]
    select_parts.append(f"{metric_sql} AS {quote_identifier(metric_name)}")
    filtered_count_alias = _unique_internal_alias(_FILTERED_COUNT_COLUMN, set([*groups, metric_name]))
    if where:
        filtered_count_sql = "SUM(COUNT(*)) OVER ()" if groups else "COUNT(*)"
        select_parts.append(f"{filtered_count_sql} AS {quote_identifier(filtered_count_alias)}")
    group_sql = f" GROUP BY {', '.join(field_sql(group) for group in groups)}" if groups else ""
    order_sql = f" ORDER BY {quote_identifier(metric_name)} DESC" if groups and not sort else ""
    if sort:
        order_sql = f" ORDER BY {', '.join(f'{quote_identifier(item["field"])} {item["direction"].upper()}' for item in sort)}"
    table_sql = quote_identifier(physical_table)
    total_rows = _expected_row_count(analysis_connection, payload)
    sql = f"SELECT {', '.join(select_parts)} FROM {table_sql}{where}{group_sql}{order_sql} LIMIT ?"
    query_params = [*params, limit]
    raw_rows = cursor_rows(analysis_connection.execute(sql, query_params))
    filtered_rows = total_rows if not where else int((raw_rows[0].get(filtered_count_alias) if raw_rows else 0) or 0)
    public_rows = [
        {key: value for key, value in row.items() if key != filtered_count_alias}
        for row in raw_rows
    ]
    rows, truncated_by_bytes, row_bytes = _bounded_rows(
        public_rows,
        AGGREGATE_RESULT_MAX_BYTES,
    )
    result = {
        "mode": "aggregate",
        "columns": [*groups, metric_name],
        "rows": rows,
        "totalRows": total_rows,
        "filteredRows": filtered_rows,
        "limit": limit,
        "rowBytes": row_bytes,
        "truncatedByBytes": truncated_by_bytes,
        "groups": groups,
        "measure": measure,
        "aggregation": aggregation,
        "metricName": metric_name,
        "filters": filters,
        "sort": sort,
        "search": str(payload.get("search") or "").strip(),
        "runtime": analysis_connection.runtime(compiled_sql=sql, params=query_params),
    }
    return _finalize_response(result, AGGREGATE_RESPONSE_MAX_BYTES)


def build_table_query(
    control_connection: sqlite3.Connection,
    analysis_connection: ValidatedDuckDBQuery,
    physical_table: str,
    all_columns: list[str],
    payload: dict[str, Any],
) -> dict[str, Any]:
    mode = str(payload.get("mode") or "detail").strip().lower()
    if mode == "detail":
        return build_detail_query(control_connection, analysis_connection, physical_table, all_columns, payload)
    if mode == "aggregate":
        return build_aggregate_query(control_connection, analysis_connection, physical_table, all_columns, payload)
    raise ValueError(f"Unsupported query-table mode: {mode}")
