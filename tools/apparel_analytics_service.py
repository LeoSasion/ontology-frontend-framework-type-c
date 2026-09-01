from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from dataset_version_store import schema_columns, schema_field_types
from bi_cli_core import DUCKDB_PATH
from query_runtime import (
    SAFE_AGGREGATIONS,
    compile_filter_sql,
    cursor_rows,
    numeric_sql,
    open_validated_duckdb_query,
    quote_identifier,
    replica_expectation,
)


APPAREL_METHOD_RESULT_SCHEMA = "aibi-apparel-commerce-method-result/v1"
EXECUTABLE_METHODS = {"ranking", "concentration", "pareto", "decile"}
MAX_APPAREL_EVIDENCE_ROWS = 500


def _duckdb_measure_sql(measure: str, aggregation: str, field_types: dict[str, str]) -> str:
    if aggregation not in SAFE_AGGREGATIONS:
        raise ValueError(f"Unsupported aggregation: {aggregation}")
    if aggregation == "count":
        return "COUNT(*)"
    if aggregation == "count-distinct":
        return f"COUNT(DISTINCT {quote_identifier(measure)})"
    data_type = str(field_types.get(measure) or "").upper()
    numeric_types = ("INT", "DECIMAL", "NUMERIC", "REAL", "FLOAT", "DOUBLE")
    expression = quote_identifier(measure) if any(token in data_type for token in numeric_types) else numeric_sql(quote_identifier(measure))
    return f"{aggregation.upper()}({expression})"


def _population_ctes(
    *,
    physical_table: str,
    columns: list[str],
    entity_field: str,
    measure: str,
    aggregation: str,
    filters: list[dict[str, Any]],
    field_types: dict[str, str],
) -> tuple[str, list[Any]]:
    if entity_field not in columns:
        raise ValueError(f"Unknown entity field: {entity_field}")
    if measure != "*" and measure not in columns:
        raise ValueError(f"Unknown measure field: {measure}")
    for item in filters:
        if str(item.get("field") or "") not in columns:
            raise ValueError(f"Unknown filter field: {item.get('field')}")
    where, params = compile_filter_sql(filters, dialect="duckdb", field_types=field_types)
    predicates = [f"TRIM(CAST({quote_identifier(entity_field)} AS VARCHAR)) <> ''"]
    if where:
        predicates.append(where)
    measure_sql = _duckdb_measure_sql(measure, aggregation, field_types)
    return f"""
        entity_values AS MATERIALIZED (
          SELECT
            CAST({quote_identifier(entity_field)} AS VARCHAR) AS label,
            {measure_sql} AS value
          FROM {quote_identifier(physical_table)}
          WHERE {' AND '.join(predicates)}
          GROUP BY {quote_identifier(entity_field)}
        ),
        population AS MATERIALIZED (
          SELECT label, TRY_CAST(value AS DOUBLE) AS value
          FROM entity_values
          WHERE TRY_CAST(value AS DOUBLE) IS NOT NULL
        )
    """, params


def _bounded_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
    truncated = len(rows) > MAX_APPAREL_EVIDENCE_ROWS
    bounded = rows[:MAX_APPAREL_EVIDENCE_ROWS]
    return [
        {key: value for key, value in row.items() if not str(key).startswith("__")}
        for row in bounded
    ], truncated


def _ranking_sql(population_ctes: str, direction: str) -> str:
    return f"""
        WITH {population_ctes},
        ranked AS (
          SELECT
            label,
            value,
            RANK() OVER (ORDER BY value {direction})::BIGINT AS rank,
            COUNT(*) OVER ()::BIGINT AS __population_count
          FROM population
        )
        SELECT
          label,
          value,
          label AS {quote_identifier('businessKey')},
          rank,
          __population_count
        FROM ranked
        WHERE rank <= ?
        ORDER BY value {direction}, label ASC
        LIMIT ?
    """


def _concentration_sql(population_ctes: str) -> str:
    return f"""
        WITH {population_ctes},
        positive AS (
          SELECT
            label,
            value,
            ROW_NUMBER() OVER (ORDER BY value DESC, label ASC)::BIGINT AS rank,
            COUNT(*) OVER ()::BIGINT AS population_count,
            SUM(value) OVER () AS population_total,
            SUM(value) OVER (
              ORDER BY value DESC, label ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS cumulative_value
          FROM population
          WHERE value > 0
        ),
        stats AS (
          SELECT
            MAX(population_count)::BIGINT AS population_count,
            MAX(population_total) AS population_total,
            GREATEST(1, CAST(CEIL(MAX(population_count) * ?) AS BIGINT)) AS target_count
          FROM positive
        ),
        boundary AS (
          SELECT
            stats.*,
            (SELECT value FROM positive WHERE rank = stats.target_count) AS boundary_value
          FROM stats
          WHERE population_count > 0
        ),
        selected AS (
          SELECT
            positive.*,
            boundary.target_count,
            COUNT(*) OVER ()::BIGINT AS actual_count,
            SUM(value) OVER () / boundary.population_total AS head_contribution
          FROM positive
          CROSS JOIN boundary
          WHERE positive.value >= boundary.boundary_value
        )
        SELECT
          label,
          value,
          label AS {quote_identifier('businessKey')},
          rank,
          value / population_total AS contribution,
          cumulative_value / population_total AS {quote_identifier('cumulativeContribution')},
          population_count AS __population_count,
          population_total AS __population_total,
          target_count AS __target_count,
          actual_count AS __actual_count,
          head_contribution AS __head_contribution
        FROM selected
        ORDER BY value DESC, label ASC
        LIMIT ?
    """


def _pareto_sql(population_ctes: str) -> str:
    return f"""
        WITH {population_ctes},
        positive AS (
          SELECT
            label,
            value,
            ROW_NUMBER() OVER (ORDER BY value DESC, label ASC)::BIGINT AS rank,
            COUNT(*) OVER ()::BIGINT AS population_count,
            SUM(value) OVER () AS population_total,
            SUM(value) OVER (
              ORDER BY value DESC, label ASC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) AS cumulative_value
          FROM population
          WHERE value > 0
        ),
        stats AS (
          SELECT
            MAX(population_count)::BIGINT AS population_count,
            MAX(population_total) AS population_total,
            GREATEST(1, CAST(CEIL(MAX(population_count) * ?) AS BIGINT)) AS target_count
          FROM positive
        ),
        boundaries AS (
          SELECT
            stats.*,
            (SELECT value FROM positive WHERE rank = stats.target_count) AS head_boundary,
            (
              SELECT value FROM positive
              WHERE cumulative_value / stats.population_total >= 0.8
              ORDER BY rank LIMIT 1
            ) AS pareto_boundary
          FROM stats
          WHERE population_count > 0
        ),
        evidence_stats AS (
          SELECT
            boundaries.*,
            (SELECT COUNT(*) FROM positive WHERE value >= boundaries.head_boundary)::BIGINT AS head_count,
            (SELECT SUM(value) FROM positive WHERE value >= boundaries.head_boundary) / population_total AS head_contribution,
            (SELECT COUNT(*) FROM positive WHERE value >= boundaries.pareto_boundary)::BIGINT AS entities_to_80,
            (
              SELECT MAX(cumulative_value / population_total)
              FROM positive WHERE value >= boundaries.pareto_boundary
            ) AS contribution_at_80
          FROM boundaries
        )
        SELECT
          positive.label,
          positive.value,
          positive.label AS {quote_identifier('businessKey')},
          positive.rank,
          positive.value / evidence_stats.population_total AS contribution,
          positive.cumulative_value / evidence_stats.population_total AS {quote_identifier('cumulativeContribution')},
          evidence_stats.population_count AS __population_count,
          evidence_stats.population_total AS __population_total,
          evidence_stats.target_count AS __target_count,
          evidence_stats.head_count AS __head_count,
          evidence_stats.head_contribution AS __head_contribution,
          evidence_stats.entities_to_80 AS __entities_to_80,
          evidence_stats.contribution_at_80 AS __contribution_at_80
        FROM positive
        CROSS JOIN evidence_stats
        WHERE positive.value >= LEAST(evidence_stats.head_boundary, evidence_stats.pareto_boundary)
        ORDER BY positive.value DESC, positive.label ASC
        LIMIT ?
    """


def _decile_sql(population_ctes: str) -> str:
    return f"""
        WITH {population_ctes},
        positive AS (
          SELECT
            label,
            value,
            ROW_NUMBER() OVER (ORDER BY value DESC, label ASC)::BIGINT AS rank,
            COUNT(*) OVER ()::BIGINT AS population_count,
            SUM(value) OVER () AS population_total
          FROM population
          WHERE value > 0
        ),
        assigned AS (
          SELECT
            *,
            LEAST(10, GREATEST(1, CAST(CEIL(
              MIN(rank) OVER (PARTITION BY value) * 10.0 / population_count
            ) AS INTEGER))) AS decile
          FROM positive
        ),
        grouped AS (
          SELECT
            decile,
            COUNT(*)::BIGINT AS entity_count,
            SUM(value) AS group_value,
            ARG_MIN(label, rank) AS first_key,
            ARG_MAX(label, rank) AS last_key,
            MAX(population_count)::BIGINT AS population_count,
            MAX(population_total) AS population_total
          FROM assigned
          WHERE population_count >= 10
          GROUP BY decile
        ),
        stats AS (
          SELECT COUNT(*)::BIGINT AS population_count, COALESCE(SUM(value), 0) AS population_total
          FROM population WHERE value > 0
        )
        SELECT
          FALSE AS __summary_only,
          'D' || CAST(decile AS VARCHAR) AS label,
          decile,
          entity_count AS {quote_identifier('entityCount')},
          group_value AS value,
          group_value / population_total AS contribution,
          first_key AS {quote_identifier('firstBusinessKey')},
          last_key AS {quote_identifier('lastBusinessKey')},
          population_count AS __population_count,
          population_total AS __population_total
        FROM grouped
        UNION ALL
        SELECT
          TRUE, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
          population_count, population_total
        FROM stats
        WHERE population_count < 10
        ORDER BY __summary_only, decile
    """


def execute_apparel_method(
    connection: sqlite3.Connection,
    *,
    registry: sqlite3.Row,
    columns: list[str],
    query_intent: dict[str, Any],
    duckdb_path: Path = DUCKDB_PATH,
) -> dict[str, Any] | None:
    method = str(query_intent.get("method") or "")
    if method not in EXECUTABLE_METHODS:
        return None
    current_registry = connection.execute(
        "SELECT * FROM table_registry WHERE workspace_id = ? AND table_key = ?",
        (str(registry["workspace_id"]), str(registry["table_key"])),
    ).fetchone()
    if current_registry is None:
        raise ValueError("Dataset registry binding is unavailable.")
    registry = current_registry
    current_columns = schema_columns(registry["schema_json"])
    field_types = schema_field_types(registry["schema_json"])
    if current_columns:
        columns = current_columns
    entity_field = str((query_intent.get("entity") or {}).get("field") or "")
    measure = str((query_intent.get("measure") or {}).get("field") or "")
    aggregation = str((query_intent.get("aggregation") or {}).get("function") or "")
    sort_direction = str((query_intent.get("sort") or {}).get("direction") or "desc")
    filters = list(query_intent.get("filters") or [])
    population_ctes, filter_params = _population_ctes(
        physical_table=str(registry["physical_table"]),
        columns=columns,
        entity_field=entity_field,
        measure=measure,
        aggregation=aggregation,
        filters=filters,
        field_types=field_types,
    )
    blockers: list[str] = []
    percent = min(1.0, max(0.000001, float((query_intent.get("limit") or {}).get("percent") or 0.2)))
    if method == "ranking":
        requested_count = max(1, int((query_intent.get("limit") or {}).get("count") or 10))
        direction = "ASC" if sort_direction == "asc" else "DESC"
        sql = _ranking_sql(population_ctes, direction)
        params = [*filter_params, requested_count, MAX_APPAREL_EVIDENCE_ROWS + 1]
    elif method == "concentration":
        sql = _concentration_sql(population_ctes)
        params = [*filter_params, percent, MAX_APPAREL_EVIDENCE_ROWS + 1]
    elif method == "pareto":
        sql = _pareto_sql(population_ctes)
        params = [*filter_params, percent, MAX_APPAREL_EVIDENCE_ROWS + 1]
    else:
        sql = _decile_sql(population_ctes)
        params = filter_params
    with open_validated_duckdb_query(duckdb_path, [replica_expectation(registry)]) as analysis_connection:
        raw_rows = cursor_rows(analysis_connection.execute(sql, params))
        runtime = {
            **analysis_connection.runtime(compiled_sql=sql, params=params),
            "populationComplete": True,
        }
    summary_row = next((row for row in raw_rows if bool(row.get("__summary_only"))), None)
    result_rows = [row for row in raw_rows if not bool(row.get("__summary_only"))]
    rows, output_truncated = _bounded_rows(result_rows)
    evidence_source = result_rows[0] if result_rows else summary_row or {}
    population_count = int(evidence_source.get("__population_count") or 0)
    evidence: dict[str, Any]
    if method == "ranking":
        evidence = {
            "populationEntityCount": population_count,
            "returnedEntityCount": len(rows),
            "tieRule": "competition-rank-and-include-boundary-ties",
            "stableBusinessKey": entity_field,
            "outputHardLimit": MAX_APPAREL_EVIDENCE_ROWS,
            "outputTruncated": output_truncated,
        }
    elif method == "concentration":
        if not result_rows:
            blockers.append("positive-population-total-required")
            evidence = {"blockers": list(blockers)}
        else:
            actual_count = int(evidence_source["__actual_count"])
            evidence = {
                "populationEntityCount": population_count,
                "positivePopulationTotal": float(evidence_source["__population_total"]),
                "requestedHeadPercent": percent,
                "targetEntityCount": int(evidence_source["__target_count"]),
                "actualEntityCount": actual_count,
                "actualEntityPercent": actual_count / population_count,
                "headContribution": float(evidence_source["__head_contribution"]),
                "tieBoundaryPreserved": True,
                "outputHardLimit": MAX_APPAREL_EVIDENCE_ROWS,
                "outputTruncated": output_truncated,
                "blockers": [],
            }
    elif method == "pareto":
        if not result_rows:
            blockers.append("positive-population-total-required")
            evidence = {"blockers": list(blockers)}
        else:
            head_count = int(evidence_source["__head_count"])
            entities_to_80 = int(evidence_source["__entities_to_80"])
            head_contribution = float(evidence_source["__head_contribution"])
            entity_percent_to_80 = entities_to_80 / population_count
            evidence = {
                "populationEntityCount": population_count,
                "positivePopulationTotal": float(evidence_source["__population_total"]),
                "requestedHeadPercent": percent,
                "targetEntityCount": int(evidence_source["__target_count"]),
                "actualEntityCount": head_count,
                "actualEntityPercent": head_count / population_count,
                "headContribution": head_contribution,
                "tieBoundaryPreserved": True,
                "entitiesToReach80": entities_to_80,
                "entityPercentToReach80": entity_percent_to_80,
                "contributionAt80Boundary": float(evidence_source["__contribution_at_80"]),
                "paretoClaimSupported": head_contribution >= 0.8 and entity_percent_to_80 <= percent,
                "outputHardLimit": MAX_APPAREL_EVIDENCE_ROWS,
                "outputTruncated": output_truncated,
                "blockers": [],
            }
    else:
        if population_count < 10:
            blockers.append("decile-requires-at-least-10-effective-entities")
            evidence = {
                "populationEntityCount": population_count,
                "fallback": "concentration_only",
                "blockers": list(blockers),
            }
        else:
            evidence = {
                "populationEntityCount": population_count,
                "positivePopulationTotal": float(evidence_source["__population_total"]),
                "groupCount": len(rows),
                "tieBoundaryPreserved": True,
                "definition": "entity-count-deciles",
                "outputHardLimit": 10,
                "outputTruncated": False,
                "blockers": [],
            }
    return {
        "schema": APPAREL_METHOD_RESULT_SCHEMA,
        "method": method,
        "entityField": entity_field,
        "measure": measure,
        "aggregation": aggregation,
        "runtime": runtime,
        "populationRowCount": population_count,
        "rows": rows,
        "evidence": evidence,
        "blockers": list(dict.fromkeys(blockers)),
        "executed": not blockers and bool(rows),
    }
