from __future__ import annotations

import json
from typing import Any, Callable


class ImportValidationError(ValueError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


QuoteIdentifier = Callable[[str], str]


def clean_cell(value: Any) -> str:
    return "" if value is None else str(value).strip()


def sanitize_unique_fields(fields: list[str], columns: list[str], allow_empty: bool = False) -> list[str]:
    column_set = set(columns)
    normalized: list[str] = []
    invalid: list[str] = []
    for field in fields:
        field_name = clean_cell(field)
        if not field_name:
            continue
        if field_name not in column_set:
            invalid.append(field_name)
            continue
        if field_name not in normalized:
            normalized.append(field_name)
    if invalid:
        raise ImportValidationError("唯一键字段不在目标表字段中。", {"invalidUniqueFields": invalid[:20]})
    if not normalized and not allow_empty:
        raise ImportValidationError("覆盖合并前需要先设置唯一键字段。")
    return normalized


def normalize_records_for_columns(records: list[dict[str, Any]], columns: list[str]) -> list[dict[str, str]]:
    return [{column: clean_cell(record.get(column, "")) for column in columns} for record in records]


def record_unique_values(record: dict[str, Any], unique_fields: list[str]) -> list[str]:
    return [clean_cell(record.get(field, "")) for field in unique_fields]


def record_unique_key(record: dict[str, Any], unique_fields: list[str]) -> str | None:
    values = record_unique_values(record, unique_fields)
    if not values or all(value == "" for value in values):
        return None
    return json.dumps(values, ensure_ascii=False, separators=(",", ":"))


def analyze_unique_key_quality(records: list[dict[str, Any]], unique_fields: list[str]) -> dict[str, Any]:
    total_rows = len(records)
    key_counts: dict[str, int] = {}
    empty_key_rows = 0
    partial_empty_key_rows = 0
    for record in records:
        values = record_unique_values(record, unique_fields)
        if not values or all(value == "" for value in values):
            empty_key_rows += 1
            continue
        if any(value == "" for value in values):
            partial_empty_key_rows += 1
        key = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
        key_counts[key] = key_counts.get(key, 0) + 1
    duplicate_key_count = sum(1 for count in key_counts.values() if count > 1)
    duplicate_rows_in_file = sum(count - 1 for count in key_counts.values() if count > 1)
    valid_key_rows = total_rows - empty_key_rows
    return {
        "totalRows": total_rows,
        "uniqueFields": unique_fields,
        "validKeyRows": valid_key_rows,
        "emptyKeyRows": empty_key_rows,
        "partialEmptyKeyRows": partial_empty_key_rows,
        "distinctKeys": len(key_counts),
        "duplicateKeyCount": duplicate_key_count,
        "duplicateRowsInFile": duplicate_rows_in_file,
    }


def dedupe_uploaded_records(records: list[dict[str, Any]], unique_fields: list[str]) -> tuple[list[dict[str, Any]], int, int]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    duplicate_rows = 0
    empty_key_rows = 0
    for record in records:
        key = record_unique_key(record, unique_fields)
        if key is None:
            empty_key_rows += 1
            continue
        if key in seen:
            duplicate_rows += 1
            continue
        seen.add(key)
        deduped.append(record)
    return deduped, duplicate_rows, empty_key_rows


def unique_field_match_clause(field: str, quote_identifier: QuoteIdentifier) -> str:
    column_sql = quote_identifier(field)
    return f"COALESCE(CAST({column_sql} AS TEXT), '') = ?"


def existing_rows_by_unique_key(
    connection: Any,
    table_name: str,
    columns: list[str],
    records: list[dict[str, Any]],
    unique_fields: list[str],
    quote_identifier: QuoteIdentifier,
) -> dict[str, dict[str, Any]]:
    if not records:
        return {}
    select_sql = ", ".join(["rowid AS _rowid", *[quote_identifier(column) for column in columns]])
    where_sql = " AND ".join(unique_field_match_clause(field, quote_identifier) for field in unique_fields)
    query = f"SELECT {select_sql} FROM {quote_identifier(table_name)} WHERE {where_sql} LIMIT 1"
    result: dict[str, dict[str, Any]] = {}
    for record in records:
        key = record_unique_key(record, unique_fields)
        if key is None or key in result:
            continue
        values = record_unique_values(record, unique_fields)
        row = connection.execute(query, values).fetchone()
        if row:
            result[key] = dict(row)
    return result


def row_has_fillable_empty_fields(columns: list[str], existing_row: dict[str, Any], record: dict[str, Any]) -> bool:
    for column in columns:
        existing = clean_cell(existing_row.get(column, ""))
        incoming = clean_cell(record.get(column, ""))
        if existing == "" and incoming != "":
            return True
    return False


def preview_merge_plan(
    connection: Any,
    table_name: str,
    columns: list[str],
    records: list[dict[str, Any]],
    unique_fields: list[str],
    conflict_rule: str,
    quote_identifier: QuoteIdentifier,
) -> dict[str, Any]:
    if conflict_rule not in {"overwrite", "fill-empty", "skip-existing"}:
        raise ImportValidationError("合并规则只支持 overwrite、fill-empty、skip-existing。")
    before_count = connection.execute(f"SELECT COUNT(*) FROM {quote_identifier(table_name)}").fetchone()[0]
    if not unique_fields:
        return {
            "beforeRows": before_count,
            "incomingRows": len(records),
            "matchedRows": 0,
            "insertRows": len(records),
            "updateRows": 0,
            "skipRows": 0,
            "emptyKeyRows": 0,
            "duplicateRowsInFile": 0,
            "afterRowsEstimate": before_count + len(records),
            "conflictRule": conflict_rule,
        }
    deduped_records, duplicate_rows, empty_key_rows = dedupe_uploaded_records(records, unique_fields)
    existing_map = existing_rows_by_unique_key(connection, table_name, columns, deduped_records, unique_fields, quote_identifier)
    matched_rows = sum(1 for record in deduped_records if (record_unique_key(record, unique_fields) or "") in existing_map)
    insert_rows = len(deduped_records) - matched_rows
    if conflict_rule == "overwrite":
        update_rows = matched_rows
        skip_rows = empty_key_rows + duplicate_rows
    elif conflict_rule == "fill-empty":
        update_rows = sum(
            1
            for record in deduped_records
            if (key := record_unique_key(record, unique_fields)) in existing_map
            and row_has_fillable_empty_fields(columns, existing_map[key], record)
        )
        skip_rows = matched_rows - update_rows + empty_key_rows + duplicate_rows
    else:
        update_rows = 0
        skip_rows = matched_rows + empty_key_rows + duplicate_rows
    return {
        "beforeRows": before_count,
        "incomingRows": len(records),
        "dedupedIncomingRows": len(deduped_records),
        "matchedRows": matched_rows,
        "insertRows": insert_rows,
        "updateRows": update_rows,
        "skipRows": skip_rows,
        "emptyKeyRows": empty_key_rows,
        "duplicateRowsInFile": duplicate_rows,
        "afterRowsEstimate": before_count + insert_rows,
        "conflictRule": conflict_rule,
    }
