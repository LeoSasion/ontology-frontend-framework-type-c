from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from dataset_version_store import INTERNAL_ROW_ID, duckdb_parquet_relation


class ImportValidationError(ValueError):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.details = details or {}


def _duckdb() -> Any:
    try:
        import duckdb  # type: ignore
    except ImportError as error:  # pragma: no cover - deployment contract
        raise RuntimeError("DuckDB is required for set-based import policy evaluation.") from error
    return duckdb


def _duckdb_identifier(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _duckdb_literal(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _normalized_key(alias: str, field: str) -> str:
    return f"trim(COALESCE(CAST({alias}.{_duckdb_identifier(field)} AS VARCHAR), ''))"


def _safe_duckdb_type(value: str) -> str:
    data_type = str(value or "VARCHAR").strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*(?:\([0-9 ,]+\))?(?:\[\])?", data_type):
        raise ImportValidationError(f"Dataset schema contains an unsafe DuckDB type: {value}")
    return data_type


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


def analyze_unique_key_quality_parquet(
    parquet_path: str | Path,
    unique_fields: list[str],
) -> dict[str, Any]:
    """Profile key quality with bounded-memory DuckDB aggregation."""

    path = Path(parquet_path).resolve()
    relation = f"read_parquet({_duckdb_literal(path)})"
    connection = _duckdb().connect(":memory:")
    try:
        columns = {str(row[0]) for row in connection.execute(f"DESCRIBE SELECT * FROM {relation}").fetchall()}
        selected = sanitize_unique_fields(unique_fields, sorted(columns), allow_empty=True)
        total_rows = int(connection.execute(f"SELECT COUNT(*) FROM {relation}").fetchone()[0])
        if not selected:
            return {
                "totalRows": total_rows,
                "uniqueFields": [],
                "validKeyRows": 0,
                "emptyKeyRows": total_rows,
                "partialEmptyKeyRows": 0,
                "distinctKeys": 0,
                "duplicateKeyCount": 0,
                "duplicateRowsInFile": 0,
                "evaluationMode": "duckdb-set-based",
            }
        normalized = [_normalized_key("source", field) for field in selected]
        all_empty = " AND ".join(f"({value} = '')" for value in normalized)
        any_empty = " OR ".join(f"({value} = '')" for value in normalized)
        group_columns = ", ".join(normalized)
        row = connection.execute(
            f"""
            WITH keyed AS (
              SELECT {group_columns}, COUNT(*)::BIGINT AS key_count
              FROM {relation} AS source
              WHERE NOT ({all_empty})
              GROUP BY {group_columns}
            ), totals AS (
              SELECT
                COUNT(*)::BIGINT AS total_rows,
                SUM(CASE WHEN {all_empty} THEN 1 ELSE 0 END)::BIGINT AS empty_rows,
                SUM(CASE WHEN NOT ({all_empty}) AND ({any_empty}) THEN 1 ELSE 0 END)::BIGINT AS partial_rows
              FROM {relation} AS source
            )
            SELECT
              totals.total_rows,
              totals.empty_rows,
              totals.partial_rows,
              COUNT(keyed.key_count)::BIGINT AS distinct_keys,
              SUM(CASE WHEN keyed.key_count > 1 THEN 1 ELSE 0 END)::BIGINT AS duplicate_keys,
              SUM(CASE WHEN keyed.key_count > 1 THEN keyed.key_count - 1 ELSE 0 END)::BIGINT AS duplicate_rows
            FROM totals LEFT JOIN keyed ON TRUE
            GROUP BY totals.total_rows, totals.empty_rows, totals.partial_rows
            """
        ).fetchone()
        empty_rows = int(row[1] or 0)
        return {
            "totalRows": int(row[0] or 0),
            "uniqueFields": selected,
            "validKeyRows": int(row[0] or 0) - empty_rows,
            "emptyKeyRows": empty_rows,
            "partialEmptyKeyRows": int(row[2] or 0),
            "distinctKeys": int(row[3] or 0),
            "duplicateKeyCount": int(row[4] or 0),
            "duplicateRowsInFile": int(row[5] or 0),
            "evaluationMode": "duckdb-set-based",
        }
    finally:
        connection.close()


def preview_merge_plan_parquet(
    *,
    active_paths: list[str | Path],
    incoming_path: str | Path,
    schema_fields: list[dict[str, str]],
    unique_fields: list[str],
    conflict_rule: str,
) -> dict[str, Any]:
    """Calculate create/merge impact without per-row SQLite lookups."""

    if conflict_rule not in {"overwrite", "fill-empty", "skip-existing"}:
        raise ImportValidationError("合并规则只支持 overwrite、fill-empty、skip-existing。")
    columns = [str(field["name"]) for field in schema_fields]
    types = {str(field["name"]): _safe_duckdb_type(str(field["type"])) for field in schema_fields}
    selected = sanitize_unique_fields(unique_fields, columns, allow_empty=False)
    active_relation = duckdb_parquet_relation([Path(path) for path in active_paths])
    incoming_relation = f"read_parquet({_duckdb_literal(Path(incoming_path).resolve())})"
    incoming_keys = [_normalized_key("incoming", field) for field in selected]
    active_keys = [_normalized_key("active", field) for field in selected]
    all_empty = " AND ".join(f"({value} = '')" for value in incoming_keys)
    partition = ", ".join(incoming_keys)
    match = " AND ".join(f"{left} = {right}" for left, right in zip(active_keys, incoming_keys))
    fillable = " OR ".join(
        f"({_normalized_key('active', column)} = '' AND {_normalized_key('incoming', column)} <> '')"
        for column in columns
        if column not in selected
    ) or "FALSE"
    connection = _duckdb().connect(":memory:")
    try:
        validation_columns = []
        for index, column in enumerate(columns):
            quoted = _duckdb_identifier(column)
            validation_columns.append(
                "SUM(CASE WHEN "
                f"incoming.{quoted} IS NOT NULL "
                f"AND trim(CAST(incoming.{quoted} AS VARCHAR)) <> '' "
                f"AND TRY_CAST(incoming.{quoted} AS {types[column]}) IS NULL "
                f"THEN 1 ELSE 0 END)::BIGINT AS invalid_{index}"
            )
        invalid_counts = connection.execute(
            f"SELECT {', '.join(validation_columns)} FROM {incoming_relation} AS incoming"
        ).fetchone()
        invalid_fields = [
            column
            for index, column in enumerate(columns)
            if int(invalid_counts[index] or 0) > 0
        ]
        if invalid_fields:
            raise ImportValidationError(
                f"Incoming values cannot be cast to the active schema: {', '.join(invalid_fields[:20])}",
                {"invalidFields": invalid_fields[:20]},
            )

        cast_columns = ", ".join(
            f"TRY_CAST(incoming.{_duckdb_identifier(column)} AS {types[column]}) AS {_duckdb_identifier(column)}"
            for column in columns
        )
        active_quality = analyze_unique_key_quality_parquet(Path(active_paths[0]), selected) if len(active_paths) == 1 else None
        if active_quality and (
            int(active_quality.get("emptyKeyRows") or 0) > 0
            or int(active_quality.get("duplicateRowsInFile") or 0) > 0
        ):
            raise ImportValidationError(
                "目标表唯一键质量不足，无法执行确定性合并。",
                {"activeUniqueKeyQuality": active_quality},
            )
        row = connection.execute(
            f"""
            WITH incoming_cast AS (
              SELECT incoming.{_duckdb_identifier(INTERNAL_ROW_ID)}, {cast_columns}
              FROM {incoming_relation} AS incoming
            ), incoming_base AS (
              SELECT incoming.*,
                ROW_NUMBER() OVER (
                  PARTITION BY {partition}
                  ORDER BY incoming.{_duckdb_identifier(INTERNAL_ROW_ID)}
                ) AS __dedupe_rank,
                ({all_empty}) AS __empty_key
              FROM incoming_cast AS incoming
            ), incoming_dedup AS (
              SELECT * FROM incoming_base WHERE NOT __empty_key AND __dedupe_rank = 1
            ), matched AS (
              SELECT incoming.*, active.{_duckdb_identifier(INTERNAL_ROW_ID)} AS __active_row_id,
                     ({fillable}) AS __has_fillable
              FROM incoming_dedup AS incoming
              LEFT JOIN {active_relation} AS active ON {match}
            ), incoming_stats AS (
              SELECT
                COUNT(*)::BIGINT AS incoming_rows,
                SUM(CASE WHEN __empty_key THEN 1 ELSE 0 END)::BIGINT AS empty_rows,
                SUM(CASE WHEN NOT __empty_key AND __dedupe_rank > 1 THEN 1 ELSE 0 END)::BIGINT AS duplicate_rows
              FROM incoming_base
            )
            SELECT
              (SELECT COUNT(*) FROM {active_relation})::BIGINT AS before_rows,
              incoming_stats.incoming_rows,
              (SELECT COUNT(*) FROM incoming_dedup)::BIGINT AS deduped_rows,
              SUM(CASE WHEN matched.{_duckdb_identifier(INTERNAL_ROW_ID)} IS NOT NULL
                        AND matched.__active_row_id IS NOT NULL THEN 1 ELSE 0 END)::BIGINT AS matched_rows,
              SUM(CASE WHEN matched.{_duckdb_identifier(INTERNAL_ROW_ID)} IS NOT NULL
                        AND matched.__active_row_id IS NULL THEN 1 ELSE 0 END)::BIGINT AS insert_rows,
              SUM(CASE WHEN matched.{_duckdb_identifier(INTERNAL_ROW_ID)} IS NOT NULL
                        AND matched.__active_row_id IS NOT NULL
                        AND matched.__has_fillable THEN 1 ELSE 0 END)::BIGINT AS fillable_rows,
              incoming_stats.empty_rows,
              incoming_stats.duplicate_rows
            FROM incoming_stats LEFT JOIN matched ON TRUE
            GROUP BY incoming_stats.incoming_rows, incoming_stats.empty_rows, incoming_stats.duplicate_rows
            """
        ).fetchone()
    finally:
        connection.close()
    before_rows = int(row[0] or 0)
    incoming_rows = int(row[1] or 0)
    deduped_rows = int(row[2] or 0)
    matched_rows = int(row[3] or 0)
    insert_rows = int(row[4] or 0)
    fillable_rows = int(row[5] or 0)
    empty_rows = int(row[6] or 0)
    duplicate_rows = int(row[7] or 0)
    if conflict_rule == "overwrite":
        update_rows = matched_rows
        skip_rows = empty_rows + duplicate_rows
    elif conflict_rule == "fill-empty":
        update_rows = fillable_rows
        skip_rows = matched_rows - fillable_rows + empty_rows + duplicate_rows
    else:
        update_rows = 0
        skip_rows = matched_rows + empty_rows + duplicate_rows
    return {
        "beforeRows": before_rows,
        "incomingRows": incoming_rows,
        "dedupedIncomingRows": deduped_rows,
        "matchedRows": matched_rows,
        "insertRows": insert_rows,
        "updateRows": update_rows,
        "skipRows": skip_rows,
        "emptyKeyRows": empty_rows,
        "duplicateRowsInFile": duplicate_rows,
        "afterRowsEstimate": before_rows + insert_rows,
        "conflictRule": conflict_rule,
        "evaluationMode": "duckdb-set-based",
    }
