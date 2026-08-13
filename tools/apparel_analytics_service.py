from __future__ import annotations

import math
import sqlite3
from pathlib import Path
from typing import Any

from bi_cli_core import DUCKDB_PATH
from query_runtime import (
    SAFE_AGGREGATIONS,
    ValidatedDuckDBQuery,
    compile_filter_sql,
    cursor_rows,
    numeric_sql,
    open_validated_duckdb_query,
    quote_identifier,
    replica_expectation,
)


APPAREL_METHOD_RESULT_SCHEMA = "aibi-apparel-commerce-method-result/v1"
EXECUTABLE_METHODS = {"ranking", "concentration", "pareto", "decile"}


def _duckdb_measure_sql(measure: str, aggregation: str) -> str:
    if aggregation not in SAFE_AGGREGATIONS:
        raise ValueError(f"Unsupported aggregation: {aggregation}")
    if aggregation == "count":
        return "COUNT(*)"
    if aggregation == "count-distinct":
        return f"COUNT(DISTINCT {quote_identifier(measure)})"
    return f"{aggregation.upper()}({numeric_sql(quote_identifier(measure))})"


def _entity_population(
    connection: ValidatedDuckDBQuery,
    *,
    physical_table: str,
    columns: list[str],
    entity_field: str,
    measure: str,
    aggregation: str,
    filters: list[dict[str, Any]],
    sort_direction: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if entity_field not in columns:
        raise ValueError(f"Unknown entity field: {entity_field}")
    if measure != "*" and measure not in columns:
        raise ValueError(f"Unknown measure field: {measure}")
    for item in filters:
        if str(item.get("field") or "") not in columns:
            raise ValueError(f"Unknown filter field: {item.get('field')}")
    where, params = compile_filter_sql(filters, dialect="duckdb")
    predicates = [f"TRIM(CAST({quote_identifier(entity_field)} AS VARCHAR)) <> ''"]
    if where:
        predicates.append(where)
    measure_sql = _duckdb_measure_sql(measure, aggregation)
    direction = "ASC" if sort_direction == "asc" else "DESC"
    sql = (
        f"SELECT CAST({quote_identifier(entity_field)} AS VARCHAR) AS label, {measure_sql} AS value "
        f"FROM {quote_identifier(physical_table)} "
        f"WHERE {' AND '.join(predicates)} "
        f"GROUP BY {quote_identifier(entity_field)} "
        f"ORDER BY value {direction}, label ASC"
    )
    rows = cursor_rows(connection.execute(sql, params))
    return {**connection.runtime(compiled_sql=sql, params=params), "populationComplete": True}, rows


def _numeric_population(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in rows:
        try:
            value = float(row.get("value"))
        except (TypeError, ValueError):
            continue
        result.append({"label": str(row.get("label") or ""), "value": value})
    return result


def _rank_rows(population: list[dict[str, Any]], limit: int, sort_direction: str) -> list[dict[str, Any]]:
    if not population:
        return []
    limited_index = min(max(1, limit), len(population)) - 1
    boundary_value = population[limited_index]["value"]
    included = (
        [row for row in population if row["value"] <= boundary_value]
        if sort_direction == "asc"
        else [row for row in population if row["value"] >= boundary_value]
    )
    ranked: list[dict[str, Any]] = []
    last_value: float | None = None
    last_rank = 0
    for index, row in enumerate(included, start=1):
        rank = last_rank if last_value is not None and row["value"] == last_value else index
        ranked.append({**row, "businessKey": row["label"], "rank": rank})
        last_value, last_rank = row["value"], rank
    return ranked


def _head_boundary(population: list[dict[str, Any]], percent: float) -> tuple[list[dict[str, Any]], int]:
    target = max(1, math.ceil(len(population) * percent))
    boundary_value = population[min(target, len(population)) - 1]["value"]
    selected = [row for row in population if row["value"] >= boundary_value]
    return selected, target


def _contribution_rows(population: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], float]:
    positive = [row for row in population if row["value"] > 0]
    total = sum(row["value"] for row in positive)
    if total <= 0:
        return [], 0.0
    cumulative = 0.0
    result: list[dict[str, Any]] = []
    for index, row in enumerate(positive, start=1):
        contribution = row["value"] / total
        cumulative += contribution
        result.append({
            **row,
            "businessKey": row["label"],
            "rank": index,
            "contribution": contribution,
            "cumulativeContribution": cumulative,
        })
    return result, total


def _concentration(population: list[dict[str, Any]], percent: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    contributions, total = _contribution_rows(population)
    if not contributions:
        return [], {"blockers": ["positive-population-total-required"]}
    selected, target_count = _head_boundary(contributions, percent)
    actual_count = len(selected)
    contribution = sum(row["contribution"] for row in selected)
    return selected, {
        "populationEntityCount": len(contributions),
        "positivePopulationTotal": total,
        "requestedHeadPercent": percent,
        "targetEntityCount": target_count,
        "actualEntityCount": actual_count,
        "actualEntityPercent": actual_count / len(contributions),
        "headContribution": contribution,
        "tieBoundaryPreserved": actual_count >= target_count,
        "blockers": [],
    }


def _pareto(population: list[dict[str, Any]], percent: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected, concentration = _concentration(population, percent)
    blockers = list(concentration.get("blockers") or [])
    if blockers:
        return [], {**concentration, "blockers": blockers}
    contributions, _total = _contribution_rows(population)
    threshold_index = next((index for index, row in enumerate(contributions) if row["cumulativeContribution"] >= 0.8), None)
    if threshold_index is None:
        return [], {**concentration, "blockers": ["pareto-80-threshold-not-reached"]}
    boundary_value = contributions[threshold_index]["value"]
    threshold_rows = [row for row in contributions if row["value"] >= boundary_value]
    evidence_rows = list({row["businessKey"]: row for row in [*selected, *threshold_rows]}.values())
    return evidence_rows, {
        **concentration,
        "entitiesToReach80": len(threshold_rows),
        "entityPercentToReach80": len(threshold_rows) / len(contributions),
        "contributionAt80Boundary": threshold_rows[-1]["cumulativeContribution"],
        "paretoClaimSupported": concentration["headContribution"] >= 0.8 and len(threshold_rows) / len(contributions) <= percent,
        "blockers": [],
    }


def _decile(population: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    contributions, total = _contribution_rows(population)
    if len(contributions) < 10:
        return [], {
            "populationEntityCount": len(contributions),
            "fallback": "concentration_only",
            "blockers": ["decile-requires-at-least-10-effective-entities"],
        }
    groups: dict[int, list[dict[str, Any]]] = {}
    last_value: float | None = None
    last_decile = 1
    for index, row in enumerate(contributions, start=1):
        proposed = min(10, max(1, math.ceil(index * 10 / len(contributions))))
        decile = last_decile if last_value is not None and row["value"] == last_value else proposed
        groups.setdefault(decile, []).append(row)
        last_value, last_decile = row["value"], decile
    result = []
    for decile in sorted(groups):
        rows = groups[decile]
        value = sum(row["value"] for row in rows)
        result.append({
            "label": f"D{decile}",
            "decile": decile,
            "entityCount": len(rows),
            "value": value,
            "contribution": value / total,
            "firstBusinessKey": rows[0]["businessKey"],
            "lastBusinessKey": rows[-1]["businessKey"],
        })
    return result, {
        "populationEntityCount": len(contributions),
        "positivePopulationTotal": total,
        "groupCount": len(result),
        "tieBoundaryPreserved": True,
        "definition": "entity-count-deciles",
        "blockers": [],
    }


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
    entity_field = str((query_intent.get("entity") or {}).get("field") or "")
    measure = str((query_intent.get("measure") or {}).get("field") or "")
    aggregation = str((query_intent.get("aggregation") or {}).get("function") or "")
    sort_direction = str((query_intent.get("sort") or {}).get("direction") or "desc")
    with open_validated_duckdb_query(duckdb_path, [replica_expectation(registry)]) as analysis_connection:
        runtime, raw_population = _entity_population(
            analysis_connection,
            physical_table=str(registry["physical_table"]),
            columns=columns,
            entity_field=entity_field,
            measure=measure,
            aggregation=aggregation,
            filters=list(query_intent.get("filters") or []),
            sort_direction=sort_direction,
        )
    population = _numeric_population(raw_population)
    blockers: list[str] = []
    evidence: dict[str, Any]
    if method == "ranking":
        rows = _rank_rows(population, int((query_intent.get("limit") or {}).get("count") or 10), sort_direction)
        evidence = {
            "populationEntityCount": len(population),
            "returnedEntityCount": len(rows),
            "tieRule": "competition-rank-and-include-boundary-ties",
            "stableBusinessKey": entity_field,
        }
    elif method == "concentration":
        rows, evidence = _concentration(population, float((query_intent.get("limit") or {}).get("percent") or 0.2))
        blockers.extend(evidence.get("blockers") or [])
    elif method == "pareto":
        rows, evidence = _pareto(population, float((query_intent.get("limit") or {}).get("percent") or 0.2))
        blockers.extend(evidence.get("blockers") or [])
    else:
        rows, evidence = _decile(population)
        blockers.extend(evidence.get("blockers") or [])
    return {
        "schema": APPAREL_METHOD_RESULT_SCHEMA,
        "method": method,
        "entityField": entity_field,
        "measure": measure,
        "aggregation": aggregation,
        "runtime": runtime,
        "populationRowCount": len(population),
        "rows": rows,
        "evidence": evidence,
        "blockers": list(dict.fromkeys(blockers)),
        "executed": not blockers and bool(rows),
    }
