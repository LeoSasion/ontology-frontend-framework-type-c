from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Callable

from agent_intent_service import build_business_intent_frame
from bi_cli_core import DUCKDB_PATH
from query_runtime import cursor_rows, open_validated_duckdb_query, replica_expectation
from relationship_tools import (
    normalize_relationship_filter,
    normalize_relationship_preaggregation,
    parse_filter_values,
    parse_range_values,
)
from semantic_query_planner import build_workspace_semantic_plan, normalize_semantic_text


EXECUTION_PLAN_SCHEMA = "aibi-semantic-query-execution-plan/v1"
PATH_PROOF_SCHEMA = "aibi-relationship-path-proof/v1"
SAFE_AGGREGATIONS = {"count", "count-distinct", "sum", "avg", "min", "max"}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _plan_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def _blocked_plan(semantic_plan: dict[str, Any], blockers: list[str]) -> dict[str, Any]:
    payload = {
        "schema": EXECUTION_PLAN_SCHEMA,
        "status": "blocked",
        "autoExecutable": False,
        "blockers": list(dict.fromkeys(str(item) for item in blockers if item)),
        "semanticPlanStatus": semantic_plan.get("status"),
        "rootTable": semantic_plan.get("joinPlan", {}).get("rootTable"),
    }
    return {**payload, "planHash": _plan_hash(payload)}


def _runtime_blocked_plan(
    execution_plan: dict[str, Any],
    blockers: list[str],
    path_proof: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = dict(execution_plan)
    result["status"] = "blocked"
    result["autoExecutable"] = False
    result["blockers"] = list(dict.fromkeys(str(item) for item in blockers if item))
    if path_proof:
        result["relationshipPathProof"] = path_proof
    return result


def _select_linear_path(join_plan: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    targets = [item for item in join_plan.get("targets") or [] if isinstance(item, dict)]
    selected_paths = [
        item.get("selectedPath")
        for item in targets
        if isinstance(item.get("selectedPath"), dict)
    ]
    if not selected_paths:
        return None, ["relationship-path-required"]
    ordered = sorted(
        selected_paths,
        key=lambda path: (
            -len(path.get("hops") or []),
            tuple(str(hop.get("relationKey") or "") for hop in path.get("hops") or []),
        ),
    )
    required_tables = {str(item) for item in join_plan.get("requiredTables") or [] if item}
    for candidate in ordered:
        candidate_tables = {str(item) for item in candidate.get("tables") or [] if item}
        if required_tables.issubset(candidate_tables):
            return candidate, []
    return None, ["non-linear-relationship-tree-not-supported"]


def _normalized_relationship(hop: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    blockers: list[str] = []
    direction = str(hop.get("direction") or "forward")
    left_table = str(hop.get("relationshipLeftTable") or "")
    right_table = str(hop.get("relationshipRightTable") or "")
    from_table = str(hop.get("fromTable") or "")
    to_table = str(hop.get("toTable") or "")
    if direction not in {"forward", "reverse"}:
        blockers.append("invalid-relationship-direction")
    if not left_table or not right_table or not from_table or not to_table:
        blockers.append("relationship-table-missing")
    join_type = str(hop.get("joinType") or "left")
    if join_type not in {"left", "inner"}:
        blockers.append("unsupported-relationship-join-type")
    if direction == "reverse" and join_type != "inner":
        blockers.append("reverse-left-join")

    original_mappings = [item for item in hop.get("fieldMappings") or [] if isinstance(item, dict)]
    traversal_mappings: list[dict[str, str]] = []
    for item in original_mappings:
        left_field = str(item.get("leftField") or "")
        right_field = str(item.get("rightField") or "")
        if not left_field or not right_field:
            blockers.append("missing-field-mapping")
            continue
        traversal_mappings.append({
            "fromField": left_field if direction == "forward" else right_field,
            "toField": right_field if direction == "forward" else left_field,
            "leftField": left_field,
            "rightField": right_field,
        })
    if not traversal_mappings:
        blockers.append("missing-field-mapping")
    risk = hop.get("risk") if isinstance(hop.get("risk"), dict) else {}
    if not risk.get("safeForPlanning"):
        blockers.extend(str(item) for item in risk.get("risks") or ["unsafe-relationship"])
    if str(hop.get("validationStatus") or "") != "validated":
        blockers.append("relationship-not-currently-validated")

    raw_filters = [item for item in hop.get("filters") or [] if isinstance(item, dict)]
    filters = []
    for item in raw_filters:
        side = str(item.get("side") or "").lower()
        table_key = left_table if side == "left" else right_table if side == "right" else ""
        filters.append({**item, "tableKey": table_key})
    preaggregation = hop.get("preaggregation") if isinstance(hop.get("preaggregation"), dict) else {}
    normalized = {
        "relationKey": str(hop.get("relationKey") or ""),
        "leftTable": left_table,
        "rightTable": right_table,
        "fromTable": from_table,
        "toTable": to_table,
        "joinType": join_type,
        "direction": direction,
        "fieldMappings": original_mappings,
        "traversalMappings": traversal_mappings,
        "filters": filters,
        "preaggregation": ({**preaggregation, "tableKey": right_table} if preaggregation else {}),
        "dataVersions": hop.get("dataVersions") or {},
        "currentDataVersions": hop.get("currentDataVersions") or {},
        "updatedAt": str(hop.get("relationshipUpdatedAt") or ""),
        "relationshipFingerprint": str(hop.get("relationshipFingerprint") or ""),
        "validationMetrics": hop.get("validationMetrics") or {},
    }
    return (normalized if not blockers else None), blockers


def _intent_query_filters(
    intent_frame: dict[str, Any] | None,
    semantic_plan: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    frame = intent_frame if isinstance(intent_frame, dict) else {}
    selected = [
        item
        for item in semantic_plan.get("fieldResolution", {}).get("selected") or []
        if isinstance(item, dict)
    ]
    result: list[dict[str, Any]] = []
    blockers: list[str] = []
    operator_map = {
        "=": "equals",
        "等于": "equals",
        "为": "equals",
        "是": "equals",
        "equal": "equals",
        "equals": "equals",
        "contain": "contains",
        "contains": "contains",
    }
    for raw in frame.get("filters") or []:
        if not isinstance(raw, dict):
            continue
        expression = normalize_semantic_text(raw.get("fieldExpression"))
        candidates = []
        for item in selected:
            aliases = {
                normalize_semantic_text(item.get("field")),
                normalize_semantic_text(item.get("matchedAlias")),
            }
            aliases.discard("")
            if any(alias == expression or alias in expression for alias in aliases):
                candidates.append(item)
        unique = {
            (str(item.get("tableKey") or ""), str(item.get("field") or "")): item
            for item in candidates
            if item.get("tableKey") and item.get("field")
        }
        if len(unique) != 1:
            blockers.append(f"request-filter-field-unresolved:{raw.get('fieldExpression') or ''}")
            continue
        item = next(iter(unique.values()))
        operator = operator_map.get(str(raw.get("operator") or "").casefold())
        if not operator:
            blockers.append(f"request-filter-operator-unsupported:{raw.get('operator') or ''}")
            continue
        result.append({
            "source": "request",
            "phase": "pre",
            "tableKey": str(item.get("tableKey") or ""),
            "field": str(item.get("field") or ""),
            "operator": operator,
            "value": raw.get("value", ""),
        })

    time_scope = frame.get("timeScope") if isinstance(frame.get("timeScope"), dict) else None
    if time_scope:
        time_fields = [item for item in selected if str(item.get("role") or "") == "event_time"]
        if len(time_fields) != 1:
            blockers.append("time-scope-field-unresolved")
        else:
            expression = str(time_scope.get("expression") or "")
            match = re.search(r"(?P<year>20\d{2})[-/.年](?P<month>0?[1-9]|1[0-2])", expression)
            year_match = re.search(r"(?P<year>20\d{2})", expression)
            if match:
                value = f"{match.group('year')}-{int(match.group('month')):02d}"
            elif year_match:
                value = year_match.group("year")
            else:
                blockers.append("relative-time-scope-requires-explicit-boundary")
                value = ""
            if value:
                item = time_fields[0]
                result.append({
                    "source": "request-time-scope",
                    "phase": "pre",
                    "tableKey": str(item.get("tableKey") or ""),
                    "field": str(item.get("field") or ""),
                    "operator": "contains",
                    "value": value,
                })
    deduped = {_canonical(item): item for item in result}
    return list(deduped.values()), list(dict.fromkeys(blockers))


def build_semantic_query_execution_plan(
    semantic_plan: dict[str, Any],
    *,
    intent_frame: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blockers: list[str] = []
    if semantic_plan.get("status") != "ready":
        blockers.append(f"semantic-plan-{semantic_plan.get('status') or 'missing'}")
    grain = semantic_plan.get("grain") if isinstance(semantic_plan.get("grain"), dict) else {}
    dimensions = grain.get("dimensions") if isinstance(grain.get("dimensions"), list) else []
    measures = grain.get("measures") if isinstance(grain.get("measures"), list) else []
    if len(measures) != 1:
        blockers.append("exactly-one-measure-required")
    measure = measures[0] if len(measures) == 1 and isinstance(measures[0], dict) else {}
    aggregation = str(measure.get("aggregation") or "")
    if aggregation not in SAFE_AGGREGATIONS:
        blockers.append("missing-or-unsafe-aggregation")

    join_plan = semantic_plan.get("joinPlan") if isinstance(semantic_plan.get("joinPlan"), dict) else {}
    selected_path, path_blockers = _select_linear_path(join_plan)
    blockers.extend(path_blockers)
    hops = selected_path.get("hops") if isinstance(selected_path, dict) and isinstance(selected_path.get("hops"), list) else []
    if len(hops) not in {1, 2, 3}:
        blockers.append("supported-hop-count-exceeded")
    relationships: list[dict[str, Any]] = []
    for hop in hops:
        if not isinstance(hop, dict):
            blockers.append("invalid-relationship-hop")
            continue
        relationship, hop_blockers = _normalized_relationship(hop)
        blockers.extend(hop_blockers)
        if relationship:
            relationships.append(relationship)

    path_tables = [str(item) for item in (selected_path.get("tables") if isinstance(selected_path, dict) else []) or []]
    supported_tables = set(path_tables)
    request_filters, request_filter_blockers = _intent_query_filters(intent_frame, semantic_plan)
    blockers.extend(request_filter_blockers)
    explicit_grain_fields = {
        str(item)
        for item in (
            intent_frame.get("grainExpectation", {}).get("fields", [])
            if isinstance(intent_frame, dict) and isinstance(intent_frame.get("grainExpectation"), dict)
            else []
        )
    }
    filter_only_fields = {
        (str(item.get("tableKey") or ""), str(item.get("field") or ""))
        for item in request_filters
        if f"{item.get('tableKey')}.{item.get('field')}" not in explicit_grain_fields
    }
    groups: list[dict[str, str]] = []
    for dimension in dimensions:
        if not isinstance(dimension, dict):
            blockers.append("invalid-dimension")
            continue
        table_key = str(dimension.get("tableKey") or "")
        field = str(dimension.get("field") or "")
        if table_key not in supported_tables or not field:
            blockers.append("dimension-outside-selected-path")
            continue
        if (table_key, field) in filter_only_fields:
            continue
        groups.append({"tableKey": table_key, "field": field})
    measure_table = str(measure.get("tableKey") or "")
    measure_field = str(measure.get("field") or "")
    if measure_table not in supported_tables or not measure_field:
        blockers.append("measure-outside-selected-path")
    elif path_tables and measure_table != path_tables[-1]:
        blockers.append("measure-must-be-on-terminal-path-table")

    if blockers:
        return _blocked_plan(semantic_plan, blockers)

    hop_proofs = []
    for index, relationship in enumerate(relationships):
        expected_versions = relationship.get("dataVersions") or {}
        current_versions = relationship.get("currentDataVersions") or {}
        version_match = all(
            int(expected_versions.get(table_key) or 0) == int(current_versions.get(table_key) or 0)
            for table_key in {relationship["leftTable"], relationship["rightTable"]}
        )
        hop_proofs.append({
            "ordinal": index + 1,
            "relationKey": relationship["relationKey"],
            "fromTable": relationship["fromTable"],
            "toTable": relationship["toTable"],
            "direction": relationship["direction"],
            "joinType": relationship["joinType"],
            "fieldMappings": relationship["fieldMappings"],
            "traversalMappings": relationship["traversalMappings"],
            "inputGrain": [f"{relationship['fromTable']}.{item['fromField']}" for item in relationship["traversalMappings"]],
            "outputGrain": [f"{relationship['toTable']}.{item['toField']}" for item in relationship["traversalMappings"]],
            "filters": relationship["filters"],
            "preaggregation": relationship["preaggregation"],
            "relationshipFingerprint": relationship["relationshipFingerprint"],
            "dataVersions": {
                "expected": expected_versions,
                "current": current_versions,
                "matches": version_match,
            },
            "validationMetrics": relationship["validationMetrics"],
            "proofStatus": "planned",
            "blockers": [],
            "warnings": [],
        })
    path_proof = {
        "schema": PATH_PROOF_SCHEMA,
        "status": "planned",
        "rootTable": str(join_plan.get("rootTable") or ""),
        "tables": path_tables,
        "finalGrain": [f"{item['tableKey']}.{item['field']}" for item in groups],
        "hopProofs": hop_proofs,
        "blockers": [],
        "warnings": [],
    }
    payload = {
        "schema": EXECUTION_PLAN_SCHEMA,
        "status": "ready",
        "autoExecutable": True,
        "blockers": [],
        "semanticPlanStatus": "ready",
        "rootTable": str(join_plan.get("rootTable") or ""),
        "pathTables": path_tables,
        "relationships": relationships,
        "groups": groups,
        "measure": {
            "tableKey": measure_table,
            "field": measure_field,
            "aggregation": aggregation,
        },
        "requestFilters": request_filters,
        "finalGrain": path_proof["finalGrain"],
        "relationshipPathProof": path_proof,
    }
    if len(relationships) == 1:
        payload["relationship"] = relationships[0]
    return {**payload, "planHash": _plan_hash(payload)}


def _filter_clause(
    rule: dict[str, Any],
    alias: str,
    quote_identifier: Callable[[str], str],
) -> tuple[str, list[Any]]:
    column = f"{alias}.{quote_identifier(str(rule['field']))}"
    operator = str(rule.get("operator") or "equals")
    value = rule.get("value", "")
    if operator == "empty":
        return f"({column} IS NULL OR {column} = '')", []
    if operator == "notEmpty":
        return f"({column} IS NOT NULL AND {column} <> '')", []
    if operator == "equals":
        return f"{column} = ?", [str(value)]
    if operator == "notEquals":
        return f"{column} <> ?", [str(value)]
    if operator == "contains":
        return f"{column} LIKE ?", [f"%{value}%"]
    if operator == "in":
        values = parse_filter_values(value)
        if not values:
            return "", []
        return f"{column} IN ({', '.join('?' for _ in values)})", values
    numeric = _numeric_expression(alias, str(rule["field"]), quote_identifier)
    if operator == "between":
        start, end = parse_range_values(value)
        clauses = []
        params: list[Any] = []
        if start:
            clauses.append(f"{numeric} >= ?")
            params.append(start)
        if end:
            clauses.append(f"{numeric} <= ?")
            params.append(end)
        return " AND ".join(clauses), params
    symbol = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}.get(operator)
    if not symbol:
        raise ValueError(f"unsupported-filter-operator:{operator}")
    return f"{numeric} {symbol} ?", [str(value)]


def _where_clause(
    rules: list[dict[str, Any]],
    alias: str,
    quote_identifier: Callable[[str], str],
) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    for rule in rules:
        clause, values = _filter_clause(rule, alias, quote_identifier)
        if clause:
            clauses.append(clause)
            params.extend(values)
    return (" WHERE " + " AND ".join(clauses) if clauses else ""), params


def _numeric_expression(alias: str, field: str, quote_identifier: Callable[[str], str]) -> str:
    column = f"{alias}.{quote_identifier(field)}"
    return f"CAST(NULLIF(REPLACE(TRIM(CAST({column} AS TEXT)), ',', ''), '') AS REAL)"


def _measure_rollup_contract(
    measure: dict[str, Any],
    preaggregation: dict[str, Any] | None,
) -> tuple[str, dict[str, Any], list[str]]:
    requested = str(measure.get("aggregation") or "")
    table_key = str(measure.get("tableKey") or "")
    field = str(measure.get("field") or "")
    proof = {
        "status": "not-required",
        "tableKey": table_key,
        "field": field,
        "requestedAggregation": requested,
        "partialAggregation": None,
        "rollupAggregation": requested,
    }
    if not preaggregation:
        return requested, proof, []
    candidates = [
        item for item in preaggregation.get("measures") or []
        if isinstance(item, dict) and str(item.get("field") or "") == field
    ]
    if len(candidates) != 1:
        return requested, {**proof, "status": "blocked"}, [f"preaggregation-measure-missing:{table_key}:{field}"]
    partial = str(candidates[0].get("aggregation") or "")
    proof["partialAggregation"] = partial
    if partial != requested:
        return requested, {**proof, "status": "blocked"}, [
            f"preaggregation-aggregation-mismatch:{table_key}:{field}:{partial}->{requested}"
        ]
    if partial in {"avg", "count-distinct"}:
        return requested, {**proof, "status": "blocked"}, [
            f"preaggregation-non-rollup-safe:{table_key}:{field}:{partial}"
        ]
    rollup = "sum" if partial == "count" else partial
    return rollup, {
        **proof,
        "status": "verified",
        "rollupAggregation": rollup,
    }, []


def _build_base_source(
    physical_table: str,
    columns: list[str],
    filters: list[dict[str, Any]],
    preaggregation: dict[str, Any] | None,
    *,
    quote_identifier: Callable[[str], str],
) -> tuple[str, list[Any], list[str]]:
    where_sql, params = _where_clause(filters, "s", quote_identifier)
    table_sql = quote_identifier(physical_table)
    if not preaggregation:
        if not where_sql:
            return table_sql, [], columns
        return f"(SELECT * FROM {table_sql} AS s{where_sql})", params, columns

    group_fields = list(preaggregation["groupFields"])
    select_parts = [
        f"s.{quote_identifier(field)} AS {quote_identifier(field)}"
        for field in group_fields
    ]
    for item in preaggregation["measures"]:
        field = str(item["field"])
        aggregation = str(item["aggregation"])
        field_sql = f"s.{quote_identifier(field)}"
        if aggregation == "count":
            expression = "COUNT(*)"
        elif aggregation == "count-distinct":
            expression = f"COUNT(DISTINCT {field_sql})"
        else:
            expression = f"{aggregation.upper()}({_numeric_expression('s', field, quote_identifier)})"
        select_parts.append(f"{expression} AS {quote_identifier(field)}")
    group_sql = ", ".join(f"s.{quote_identifier(field)}" for field in group_fields)
    source = (
        f"(SELECT {', '.join(select_parts)} FROM {table_sql} AS s"
        f"{where_sql} GROUP BY {group_sql})"
    )
    return source, params, [*group_fields, *[str(item["field"]) for item in preaggregation["measures"]]]


def _deduplicated_source(
    source: str,
    params: list[Any],
    fields: list[str],
    *,
    quote_identifier: Callable[[str], str],
) -> tuple[str, list[Any]]:
    projection = ", ".join(f"q.{quote_identifier(field)}" for field in fields)
    return f"(SELECT {projection} FROM {source} AS q GROUP BY {projection})", list(params)


def _complete_key_clause(
    alias: str,
    fields: list[str],
    quote_identifier: Callable[[str], str],
) -> str:
    return " AND ".join(
        f"{alias}.{quote_identifier(field)} IS NOT NULL AND "
        f"TRIM(CAST({alias}.{quote_identifier(field)} AS TEXT)) <> ''"
        for field in fields
    ) or "1 = 1"


def _join_condition(
    from_alias: str,
    to_alias: str,
    mappings: list[dict[str, str]],
    quote_identifier: Callable[[str], str],
) -> str:
    pairs = []
    for item in mappings:
        from_column = f"{from_alias}.{quote_identifier(item['fromField'])}"
        to_column = f"{to_alias}.{quote_identifier(item['toField'])}"
        pairs.extend([
            f"{from_column} IS NOT NULL",
            f"TRIM(CAST({from_column} AS TEXT)) <> ''",
            f"{to_column} IS NOT NULL",
            f"TRIM(CAST({to_column} AS TEXT)) <> ''",
            f"{from_column} = {to_column}",
        ])
    return " AND ".join(pairs)


def _count(connection: sqlite3.Connection, sql: str, params: list[Any]) -> int:
    row = connection.execute(sql, tuple(params)).fetchone()
    return int(row[0] or 0) if row else 0


def _function_dependency_proof(
    connection: sqlite3.Connection,
    source: str,
    params: list[Any],
    determinant: list[str],
    dependents: list[str],
    *,
    quote_identifier: Callable[[str], str],
) -> dict[str, Any]:
    determinant = list(dict.fromkeys(field for field in determinant if field))
    dependents = list(dict.fromkeys(field for field in dependents if field and field not in determinant))
    if not dependents:
        return {"status": "proven", "determinant": determinant, "dependents": [], "violations": 0}
    projection = list(dict.fromkeys([*determinant, *dependents]))
    projection_sql = ", ".join(f"q.{quote_identifier(field)}" for field in projection)
    determinant_sql = ", ".join(quote_identifier(field) for field in determinant)
    complete = _complete_key_clause("q", determinant, quote_identifier)
    sql = (
        f"SELECT COUNT(*) FROM ("
        f"SELECT 1 FROM (SELECT DISTINCT {projection_sql} FROM {source} AS q WHERE {complete}) AS fd "
        f"GROUP BY {determinant_sql} HAVING COUNT(*) > 1"
        f") AS violations"
    )
    violations = _count(connection, sql, params)
    return {
        "status": "proven" if violations == 0 else "violated",
        "determinant": determinant,
        "dependents": dependents,
        "violations": violations,
    }


def _pair_proof(
    connection: sqlite3.Connection,
    from_source: str,
    from_params: list[Any],
    to_source: str,
    to_params: list[Any],
    mappings: list[dict[str, str]],
    *,
    quote_identifier: Callable[[str], str],
) -> dict[str, Any]:
    condition = _join_condition("f", "t", mappings, quote_identifier)
    from_rows = _count(connection, f"SELECT COUNT(*) FROM {from_source} AS f", from_params)
    to_rows = _count(connection, f"SELECT COUNT(*) FROM {to_source} AS t", to_params)
    matched_from = _count(
        connection,
        f"SELECT COUNT(*) FROM {from_source} AS f WHERE EXISTS (SELECT 1 FROM {to_source} AS t WHERE {condition})",
        [*from_params, *to_params],
    )
    matched_to = _count(
        connection,
        f"SELECT COUNT(*) FROM {to_source} AS t WHERE EXISTS (SELECT 1 FROM {from_source} AS f WHERE {condition})",
        [*to_params, *from_params],
    )
    joined = _count(
        connection,
        f"SELECT COUNT(*) FROM {from_source} AS f JOIN {to_source} AS t ON {condition}",
        [*from_params, *to_params],
    )
    incomplete_from = _count(
        connection,
        f"SELECT COUNT(*) FROM {from_source} AS f WHERE NOT ({_complete_key_clause('f', [item['fromField'] for item in mappings], quote_identifier)})",
        from_params,
    )
    incomplete_to = _count(
        connection,
        f"SELECT COUNT(*) FROM {to_source} AS t WHERE NOT ({_complete_key_clause('t', [item['toField'] for item in mappings], quote_identifier)})",
        to_params,
    )
    return {
        "fromRows": from_rows,
        "toRows": to_rows,
        "matchedFromRows": matched_from,
        "matchedToRows": matched_to,
        "unmatchedFromRows": max(0, from_rows - matched_from),
        "unmatchedToRows": max(0, to_rows - matched_to),
        "joinedRows": joined,
        "matchedRowExpansion": round(joined / max(1, matched_from), 6),
        "reverseMatchedRowExpansion": round(joined / max(1, matched_to), 6),
        "incompleteFromKeyRows": incomplete_from,
        "incompleteToKeyRows": incomplete_to,
    }


def _terminal_reachability_proof(
    connection: sqlite3.Connection,
    tables: list[str],
    relationships: list[dict[str, Any]],
    base_sources: dict[str, dict[str, Any]],
    measure_index: int,
    *,
    quote_identifier: Callable[[str], str],
) -> dict[str, Any]:
    """Prove that every in-scope terminal fact is reachable from the path root."""
    if measure_index <= 0:
        return {
            "status": "not-required",
            "terminalRows": 0,
            "reachableRows": 0,
            "unreachableRows": 0,
        }

    terminal_table = tables[measure_index]
    terminal_source = base_sources[terminal_table]["relationshipScopeSql"]
    terminal_params = list(base_sources[terminal_table]["relationshipScopeParams"])
    terminal_rows = _count(connection, f"SELECT COUNT(*) FROM {terminal_source} AS m", terminal_params)

    root_table = tables[0]
    prefix_sql = f"{base_sources[root_table]['structuralScopeSql']} AS r0"
    prefix_params = list(base_sources[root_table]["structuralScopeParams"])
    for index in range(max(0, measure_index - 1)):
        relationship = relationships[index]
        next_table = relationship["toTable"]
        condition = _join_condition(
            f"r{index}",
            f"r{index + 1}",
            relationship["traversalMappings"],
            quote_identifier,
        )
        prefix_sql += (
            f" JOIN {base_sources[next_table]['structuralScopeSql']} AS r{index + 1}"
            f" ON {condition}"
        )
        prefix_params.extend(base_sources[next_table]["structuralScopeParams"])

    final_relationship = relationships[measure_index - 1]
    final_condition = _join_condition(
        f"r{measure_index - 1}",
        "m",
        final_relationship["traversalMappings"],
        quote_identifier,
    )
    reachable_rows = _count(
        connection,
        (
            f"SELECT COUNT(*) FROM {terminal_source} AS m "
            f"WHERE EXISTS (SELECT 1 FROM {prefix_sql} WHERE {final_condition})"
        ),
        [*terminal_params, *prefix_params],
    )
    unreachable_rows = max(0, terminal_rows - reachable_rows)
    return {
        "status": "proven" if unreachable_rows == 0 else "violated",
        "terminalTable": terminal_table,
        "terminalRows": terminal_rows,
        "reachableRows": reachable_rows,
        "unreachableRows": unreachable_rows,
    }


def _runtime_sources_and_proof(
    connection: Any,
    execution_plan: dict[str, Any],
    registries: dict[str, sqlite3.Row],
    *,
    columns_by_table: dict[str, list[str]],
    quote_identifier: Callable[[str], str],
) -> tuple[dict[str, dict[str, Any]], dict[str, Any], list[str]]:
    tables = execution_plan["pathTables"]
    relationships = execution_plan["relationships"]
    groups = execution_plan["groups"]
    measure = execution_plan["measure"]
    path_proof = json.loads(json.dumps(execution_plan["relationshipPathProof"], ensure_ascii=False))
    blockers: list[str] = []
    warnings: list[str] = []

    physical_by_table: dict[str, str] = {}
    for table_key in tables:
        registry = registries.get(table_key)
        if not registry:
            blockers.append(f"relationship-table-missing-at-execution:{table_key}")
            continue
        physical = str(registry["physical_table"])
        physical_by_table[table_key] = physical
        if table_key not in columns_by_table:
            blockers.append(f"relationship-columns-missing-at-execution:{table_key}")
    if blockers:
        path_proof.update({"status": "blocked", "blockers": blockers})
        return {}, path_proof, blockers

    for index, relationship in enumerate(relationships):
        required_version_tables = {relationship["leftTable"], relationship["rightTable"]}
        expected_versions = relationship.get("dataVersions") if isinstance(relationship.get("dataVersions"), dict) else {}
        current_versions = {
            table_key: int(registries[table_key]["data_version"] or 1)
            for table_key in required_version_tables
        }
        hop_blockers: list[str] = []
        if not required_version_tables.issubset(expected_versions):
            hop_blockers.append("missing-relationship-version-evidence")
            versions_match = False
        else:
            try:
                versions_match = all(
                    int(expected_versions.get(table_key) or 0) == current_versions[table_key]
                    for table_key in required_version_tables
                )
            except (TypeError, ValueError):
                versions_match = False
            if not versions_match:
                hop_blockers.append("relationship-version-mismatch")
        hop_proof = path_proof["hopProofs"][index]
        hop_proof["dataVersions"] = {
            "expected": expected_versions,
            "current": current_versions,
            "matches": versions_match,
        }
        if hop_blockers:
            hop_proof["proofStatus"] = "blocked"
            hop_proof["blockers"] = list(dict.fromkeys([*hop_proof.get("blockers", []), *hop_blockers]))
            blockers.extend(f"hop-{index + 1}:{item}" for item in hop_blockers)
    if blockers:
        path_proof.update({"status": "blocked", "blockers": list(dict.fromkeys(blockers))})
        return {}, path_proof, list(dict.fromkeys(blockers))

    normalized_filters: list[dict[str, Any]] = []
    preaggregations: dict[str, dict[str, Any]] = {}
    for relationship in relationships:
        left_columns = columns_by_table[relationship["leftTable"]]
        right_columns = columns_by_table[relationship["rightTable"]]
        for raw in relationship["filters"]:
            try:
                normalized = normalize_relationship_filter(raw, left_columns, right_columns)
            except ValueError as error:
                blockers.append(str(error))
                continue
            if normalized:
                table_key = relationship["leftTable"] if normalized["side"] == "left" else relationship["rightTable"]
                normalized_filters.append({
                    "source": "relationship",
                    "relationKey": relationship["relationKey"],
                    "tableKey": table_key,
                    "phase": normalized["phase"],
                    "field": normalized["field"],
                    "operator": normalized["operator"],
                    "value": normalized.get("value", ""),
                })
        if relationship["preaggregation"]:
            try:
                normalized_preaggregation = normalize_relationship_preaggregation(
                    relationship["preaggregation"],
                    right_columns,
                    relationship["fieldMappings"],
                )
            except ValueError as error:
                blockers.append(str(error))
                continue
            if normalized_preaggregation:
                table_key = relationship["rightTable"]
                existing = preaggregations.get(table_key)
                if existing and _canonical(existing) != _canonical(normalized_preaggregation):
                    blockers.append(f"conflicting-preaggregation:{table_key}")
                else:
                    preaggregations[table_key] = normalized_preaggregation
    normalized_filters.extend(execution_plan.get("requestFilters") or [])
    normalized_filters = list({_canonical(item): item for item in normalized_filters}.values())

    measure_rollup_aggregation, measure_rollup_proof, rollup_blockers = _measure_rollup_contract(
        measure,
        preaggregations.get(measure["tableKey"]),
    )
    blockers.extend(rollup_blockers)
    path_proof["measureRollupProof"] = measure_rollup_proof

    required_fields: dict[str, list[str]] = {table_key: [] for table_key in tables}
    for relationship in relationships:
        required_fields[relationship["fromTable"]].extend(item["fromField"] for item in relationship["traversalMappings"])
        required_fields[relationship["toTable"]].extend(item["toField"] for item in relationship["traversalMappings"])
    for item in groups:
        required_fields[item["tableKey"]].append(item["field"])
    required_fields[measure["tableKey"]].append(measure["field"])
    for item in normalized_filters:
        if item.get("tableKey") in required_fields and item.get("phase") != "pre":
            required_fields[item["tableKey"]].append(str(item.get("field") or ""))
    required_fields = {
        table_key: list(dict.fromkeys(field for field in fields if field))
        for table_key, fields in required_fields.items()
    }

    base_sources: dict[str, dict[str, Any]] = {}
    for table_key in tables:
        missing = [field for field in required_fields[table_key] if field not in columns_by_table[table_key]]
        if missing:
            blockers.append(f"selected-field-missing-at-execution:{table_key}:{','.join(missing)}")
            continue
        pre_filters = [
            item for item in normalized_filters
            if item.get("tableKey") == table_key and item.get("phase") == "pre"
        ]
        source, params, effective_columns = _build_base_source(
            physical_by_table[table_key],
            columns_by_table[table_key],
            pre_filters,
            preaggregations.get(table_key),
            quote_identifier=quote_identifier,
        )
        relationship_scope_filters = [
            item for item in pre_filters if item.get("source") == "relationship"
        ]
        scope_source, scope_params, _ = _build_base_source(
            physical_by_table[table_key],
            columns_by_table[table_key],
            relationship_scope_filters,
            preaggregations.get(table_key),
            quote_identifier=quote_identifier,
        )
        structural_source, structural_params, _ = _build_base_source(
            physical_by_table[table_key],
            columns_by_table[table_key],
            [],
            preaggregations.get(table_key),
            quote_identifier=quote_identifier,
        )
        row_presence_field = ""
        if (
            table_key == measure["tableKey"]
            and measure["aggregation"] == "count"
            and not preaggregations.get(table_key)
        ):
            row_presence_field = "__aibi_semantic_fact_present"
            while row_presence_field in columns_by_table[table_key]:
                row_presence_field += "_"
            marker = quote_identifier(row_presence_field)
            source = f"(SELECT q.*, 1 AS {marker} FROM {source} AS q)"
            scope_source = f"(SELECT q.*, 1 AS {marker} FROM {scope_source} AS q)"
            structural_source = f"(SELECT q.*, 1 AS {marker} FROM {structural_source} AS q)"
            effective_columns = [*effective_columns, row_presence_field]
        unavailable = [field for field in required_fields[table_key] if field not in effective_columns]
        if unavailable:
            blockers.append(f"preaggregation-drops-required-field:{table_key}:{','.join(unavailable)}")
        base_sources[table_key] = {
            "sql": source,
            "params": params,
            "columns": effective_columns,
            "preFilters": pre_filters,
            "preaggregation": preaggregations.get(table_key),
            "relationshipScopeSql": scope_source,
            "relationshipScopeParams": scope_params,
            "structuralScopeSql": structural_source,
            "structuralScopeParams": structural_params,
            "rowPresenceField": row_presence_field,
            "measureRollupAggregation": measure_rollup_aggregation if table_key == measure["tableKey"] else None,
        }
    if blockers:
        path_proof.update({"status": "blocked", "blockers": list(dict.fromkeys(blockers))})
        return {}, path_proof, list(dict.fromkeys(blockers))

    table_fd_proofs: dict[str, dict[str, Any]] = {}
    measure_index = tables.index(measure["tableKey"])
    for index, table_key in enumerate(tables[:-1]):
        outgoing = relationships[index]
        determinant = [item["fromField"] for item in outgoing["traversalMappings"]]
        incoming = [] if index == 0 else [item["toField"] for item in relationships[index - 1]["traversalMappings"]]
        group_fields = [item["field"] for item in groups if item["tableKey"] == table_key]
        post_filter_fields = [
            str(item.get("field") or "")
            for item in normalized_filters
            if item.get("tableKey") == table_key and item.get("phase") != "pre"
        ]
        proof = _function_dependency_proof(
            connection,
            base_sources[table_key]["sql"],
            base_sources[table_key]["params"],
            determinant,
            [*incoming, *group_fields, *post_filter_fields],
            quote_identifier=quote_identifier,
        )
        table_fd_proofs[table_key] = proof
        if proof["status"] != "proven" and index < measure_index:
            blockers.append(f"path-key-not-functionally-dependent:{table_key}")
            if index == 0:
                blockers.append(
                    "left-group-not-functionally-dependent-on-join-key"
                    if len(relationships) == 1
                    else "root-group-not-functionally-dependent-on-first-hop-key"
                )

    sources = dict(base_sources)
    deduplicated_tables: list[str] = []
    for index, table_key in enumerate(tables):
        if index >= measure_index:
            continue
        fields = required_fields[table_key]
        source, params = _deduplicated_source(
            base_sources[table_key]["sql"],
            base_sources[table_key]["params"],
            fields,
            quote_identifier=quote_identifier,
        )
        sources[table_key] = {**base_sources[table_key], "sql": source, "params": params, "deduplicated": True}
        deduplicated_tables.append(table_key)

    prefix_sql = f"{sources[tables[0]]['sql']} AS t0"
    prefix_params = list(sources[tables[0]]["params"])
    input_rows = _count(connection, f"SELECT COUNT(*) FROM {prefix_sql}", prefix_params)
    for index, relationship in enumerate(relationships):
        from_table = relationship["fromTable"]
        to_table = relationship["toTable"]
        pair = _pair_proof(
            connection,
            base_sources[from_table]["sql"],
            base_sources[from_table]["params"],
            base_sources[to_table]["sql"],
            base_sources[to_table]["params"],
            relationship["traversalMappings"],
            quote_identifier=quote_identifier,
        )
        join_keyword = "JOIN" if relationship["joinType"] == "inner" else "LEFT JOIN"
        condition = _join_condition(f"t{index}", f"t{index + 1}", relationship["traversalMappings"], quote_identifier)
        prefix_sql = (
            f"{prefix_sql} {join_keyword} {sources[to_table]['sql']} AS t{index + 1} ON {condition}"
        )
        prefix_params.extend(sources[to_table]["params"])
        output_rows = _count(connection, f"SELECT COUNT(*) FROM {prefix_sql}", prefix_params)
        hop_blockers: list[str] = []
        hop_warnings: list[str] = []
        if pair["incompleteFromKeyRows"]:
            hop_warnings.append("incomplete-from-key-rows-excluded")
        if pair["incompleteToKeyRows"]:
            hop_warnings.append("incomplete-to-key-rows-excluded")
        if pair["unmatchedFromRows"]:
            hop_warnings.append("unmatched-input-rows")
        if pair["unmatchedToRows"]:
            hop_warnings.append("unmatched-target-rows")
        if pair["matchedRowExpansion"] > 1.000001 and measure_index < index + 1:
            hop_blockers.append("fan-out-after-measure-grain")
        scope_exclusion_proof = None
        if index + 1 == measure_index and pair["unmatchedToRows"]:
            scope_exclusion_proof = _pair_proof(
                connection,
                base_sources[from_table]["relationshipScopeSql"],
                base_sources[from_table]["relationshipScopeParams"],
                base_sources[to_table]["sql"],
                base_sources[to_table]["params"],
                relationship["traversalMappings"],
                quote_identifier=quote_identifier,
            )
            if scope_exclusion_proof["unmatchedToRows"] == 0:
                hop_warnings.append("target-rows-proven-outside-request-filter-scope")
            else:
                hop_blockers.append("late-dimension-measure-rows-unmatched")
        if table_fd_proofs.get(from_table, {}).get("status") == "violated":
            hop_blockers.append("path-key-function-dependency-violated")
        blockers.extend(f"hop-{index + 1}:{item}" for item in hop_blockers)
        warnings.extend(f"hop-{index + 1}:{item}" for item in hop_warnings)
        hop_proof = path_proof["hopProofs"][index]
        hop_proof.update({
            "inputRows": input_rows,
            "outputRows": output_rows,
            "rowExpansion": round(output_rows / max(1, input_rows), 6),
            "cardinalityProof": pair,
            "scopeExclusionProof": scope_exclusion_proof,
            "functionDependencyProof": table_fd_proofs.get(from_table, {
                "status": "not-required", "determinant": [], "dependents": [], "violations": 0,
            }),
            "filterProof": {
                "status": "applied" if any(item.get("tableKey") in {from_table, to_table} for item in normalized_filters) else "not-required",
                "filters": [item for item in normalized_filters if item.get("tableKey") in {from_table, to_table}],
            },
            "preaggregationProof": {
                "status": "applied" if to_table in preaggregations or from_table in preaggregations else "not-required",
                "tables": {
                    table_key: config
                    for table_key, config in preaggregations.items()
                    if table_key in {from_table, to_table}
                },
            },
            "proofStatus": "blocked" if hop_blockers else "verified",
            "blockers": hop_blockers,
            "warnings": hop_warnings,
        })
        input_rows = output_rows

    terminal_reachability_proof = _terminal_reachability_proof(
        connection,
        tables,
        relationships,
        base_sources,
        measure_index,
        quote_identifier=quote_identifier,
    )
    path_proof["terminalReachabilityProof"] = terminal_reachability_proof
    if terminal_reachability_proof["status"] == "violated":
        reachability_blocker = f"hop-{measure_index}:terminal-measure-rows-unreachable-from-root"
        blockers.append(reachability_blocker)
        terminal_hop = path_proof["hopProofs"][measure_index - 1]
        terminal_hop["proofStatus"] = "blocked"
        terminal_hop["blockers"] = list(dict.fromkeys([
            *terminal_hop.get("blockers", []),
            "terminal-measure-rows-unreachable-from-root",
        ]))

    path_proof.update({
        "status": "blocked" if blockers else "verified",
        "blockers": list(dict.fromkeys(blockers)),
        "warnings": list(dict.fromkeys(warnings)),
        "deduplicatedTables": deduplicated_tables,
    })
    proof_material = {key: value for key, value in path_proof.items() if key != "fingerprint"}
    path_proof["fingerprint"] = _plan_hash(proof_material)
    return sources, path_proof, list(dict.fromkeys(blockers))


def _execute_path_query(
    connection: sqlite3.Connection,
    execution_plan: dict[str, Any],
    sources: dict[str, dict[str, Any]],
    path_proof: dict[str, Any],
    *,
    limit: int,
    quote_identifier: Callable[[str], str],
) -> dict[str, Any]:
    tables = execution_plan["pathTables"]
    relationships = execution_plan["relationships"]
    alias_by_table = {table_key: f"t{index}" for index, table_key in enumerate(tables)}
    from_sql = f"{sources[tables[0]]['sql']} AS t0"
    params = list(sources[tables[0]]["params"])
    for index, relationship in enumerate(relationships):
        to_table = relationship["toTable"]
        join_keyword = "JOIN" if relationship["joinType"] == "inner" else "LEFT JOIN"
        condition = _join_condition(f"t{index}", f"t{index + 1}", relationship["traversalMappings"], quote_identifier)
        from_sql += f" {join_keyword} {sources[to_table]['sql']} AS t{index + 1} ON {condition}"
        params.extend(sources[to_table]["params"])

    select_parts: list[str] = []
    group_parts: list[str] = []
    output_groups: list[dict[str, str]] = []
    one_hop = len(relationships) == 1
    relationship = relationships[0] if one_hop else None
    for item in execution_plan["groups"]:
        alias = alias_by_table[item["tableKey"]]
        expression = f"{alias}.{quote_identifier(item['field'])}"
        if one_hop and relationship:
            side = "左表" if item["tableKey"] == relationship["leftTable"] else "右表"
            output_name = f"{side}.{item['field']}"
        else:
            output_name = f"{item['tableKey']}.{item['field']}"
        select_parts.append(f"{expression} AS {quote_identifier(output_name)}")
        group_parts.append(expression)
        output_groups.append({"tableKey": item["tableKey"], "field": item["field"], "outputName": output_name})

    measure = execution_plan["measure"]
    measure_alias = alias_by_table[measure["tableKey"]]
    measure_column = f"{measure_alias}.{quote_identifier(measure['field'])}"
    aggregation = measure["aggregation"]
    rollup_aggregation = str(sources[measure["tableKey"]].get("measureRollupAggregation") or aggregation)
    if rollup_aggregation == "count":
        row_presence_field = str(sources[measure["tableKey"]].get("rowPresenceField") or "")
        metric_expression = (
            f"COUNT({measure_alias}.{quote_identifier(row_presence_field)})"
            if row_presence_field
            else f"COUNT({measure_column})"
        )
    elif rollup_aggregation == "count-distinct":
        metric_expression = f"COUNT(DISTINCT {measure_column})"
    elif aggregation == "count" and rollup_aggregation == "sum":
        metric_expression = f"COALESCE(SUM({_numeric_expression(measure_alias, measure['field'], quote_identifier)}), 0)"
    else:
        metric_expression = f"{rollup_aggregation.upper()}({_numeric_expression(measure_alias, measure['field'], quote_identifier)})"
    metric_name = f"{aggregation}_{measure['tableKey']}.{measure['field']}"
    select_parts.append(f"{metric_expression} AS {quote_identifier(metric_name)}")

    post_filters = []
    for relationship_item in relationships:
        for item in relationship_item["filters"]:
            if str(item.get("phase") or "post") != "pre" and item.get("tableKey"):
                post_filters.append(item)
    post_filters = list({_canonical(item): item for item in post_filters}.values())
    post_clauses = []
    post_params: list[Any] = []
    for item in post_filters:
        clause, values = _filter_clause(item, alias_by_table[str(item["tableKey"])], quote_identifier)
        if clause:
            post_clauses.append(clause)
            post_params.extend(values)
    where_sql = " WHERE " + " AND ".join(post_clauses) if post_clauses else ""
    group_sql = " GROUP BY " + ", ".join(group_parts) if group_parts else ""
    safe_limit = max(1, min(int(limit or 50), 10000))
    sql = (
        f"SELECT {', '.join(select_parts)} FROM {from_sql}"
        f"{where_sql}{group_sql} ORDER BY {quote_identifier(metric_name)} DESC LIMIT ?"
    )
    query_params = (*params, *post_params, safe_limit)
    rows = cursor_rows(connection.execute(sql, query_params))
    mode = "semantic-relationship" if len(relationships) == 1 else f"semantic-{len(relationships)}-hop"
    return {
        "mode": mode,
        "tables": tables,
        "relationships": relationships,
        "groups": output_groups,
        "measure": {
            "tableKey": measure["tableKey"],
            "field": measure["field"],
            "outputName": f"{measure['tableKey']}.{measure['field']}",
        },
        "aggregation": aggregation,
        "rollupAggregation": rollup_aggregation,
        "filters": [
            *execution_plan.get("requestFilters", []),
            *[item for relationship_item in relationships for item in relationship_item["filters"]],
        ],
        "preaggregations": {
            relationship_item["rightTable"]: relationship_item["preaggregation"]
            for relationship_item in relationships
            if relationship_item["preaggregation"]
        },
        "rootDeduplicated": tables[0] in path_proof.get("deduplicatedTables", []),
        "deduplicatedTables": path_proof.get("deduplicatedTables", []),
        "relationshipPathProof": path_proof,
        "metricName": metric_name,
        "columns": [*[item["outputName"] for item in output_groups], metric_name],
        "rows": rows,
        "compiledSql": sql,
        "_compiledParams": list(query_params),
        "sqlShape": {
            "tables": tables,
            "relationshipKeys": [item["relationKey"] for item in relationships],
            "finalGrain": execution_plan["finalGrain"],
            "pathProofFingerprint": path_proof.get("fingerprint"),
            "limit": safe_limit,
        },
    }


def execute_workspace_semantic_query(
    connection: sqlite3.Connection,
    workspace_id: str,
    prompt: str,
    *,
    selected_table_key: str = "",
    limit: int = 50,
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    quote_identifier: Callable[[str], str],
    build_relationship_query: Callable[..., dict[str, Any]],
    semantic_plan: dict[str, Any] | None = None,
    intent_frame: dict[str, Any] | None = None,
    duckdb_path: Path = DUCKDB_PATH,
) -> dict[str, Any]:
    # build_relationship_query remains in the signature for CLI/API compatibility;
    # all relationship-path execution now goes through the same N-hop compiler.
    del build_relationship_query
    provided_semantic_plan = semantic_plan
    fresh_semantic_plan = build_workspace_semantic_plan(
        connection,
        workspace_id,
        prompt,
        selected_table_key=selected_table_key,
        table_columns=table_columns,
    )
    semantic_plan = fresh_semantic_plan
    resolved_intent = intent_frame or build_business_intent_frame(prompt, semantic_plan=semantic_plan)
    execution_plan = build_semantic_query_execution_plan(semantic_plan, intent_frame=resolved_intent)
    if provided_semantic_plan:
        provided_execution_plan = build_semantic_query_execution_plan(provided_semantic_plan, intent_frame=resolved_intent)
        if provided_execution_plan.get("planHash") != execution_plan.get("planHash"):
            execution_plan = _blocked_plan(semantic_plan, ["semantic-plan-changed-before-execution"])
            return {"ok": True, "executed": False, "semanticPlan": semantic_plan, "executionPlan": execution_plan}
    if execution_plan["status"] != "ready":
        return {"ok": True, "executed": False, "semanticPlan": semantic_plan, "executionPlan": execution_plan}

    table_keys = execution_plan["pathTables"]
    placeholders = ", ".join("?" for _ in table_keys)
    registry_rows = connection.execute(
        f"SELECT * FROM table_registry WHERE workspace_id = ? AND table_key IN ({placeholders})",
        (workspace_id, *table_keys),
    ).fetchall()
    registries = {str(row["table_key"]): row for row in registry_rows}
    missing_registry_tables = [table_key for table_key in table_keys if table_key not in registries]
    if missing_registry_tables:
        blockers = [f"relationship-table-missing-at-execution:{table_key}" for table_key in missing_registry_tables]
        path_proof = dict(execution_plan.get("relationshipPathProof") or {})
        path_proof.update({"status": "blocked", "blockers": blockers})
        execution_plan = _runtime_blocked_plan(execution_plan, blockers, path_proof)
        return {"ok": True, "executed": False, "semanticPlan": semantic_plan, "executionPlan": execution_plan}
    columns_by_table = {
        table_key: table_columns(connection, str(registry["physical_table"]))
        for table_key, registry in registries.items()
    }
    expectations = [replica_expectation(registries[table_key]) for table_key in table_keys if table_key in registries]
    with open_validated_duckdb_query(duckdb_path, expectations) as analysis_connection:
        try:
            sources, path_proof, blockers = _runtime_sources_and_proof(
                analysis_connection,
                execution_plan,
                registries,
                columns_by_table=columns_by_table,
                quote_identifier=quote_identifier,
            )
        except (ValueError, KeyError) as error:
            path_proof = dict(execution_plan.get("relationshipPathProof") or {})
            path_proof.update({"status": "blocked", "blockers": [f"path-proof-failed:{error}"]})
            blockers = [f"path-proof-failed:{error}"]
            sources = {}
        if blockers:
            execution_plan = _runtime_blocked_plan(execution_plan, blockers, path_proof)
            return {"ok": True, "executed": False, "semanticPlan": semantic_plan, "executionPlan": execution_plan}

        query = _execute_path_query(
            analysis_connection,
            execution_plan,
            sources,
            path_proof,
            limit=limit,
            quote_identifier=quote_identifier,
        )
        query_runtime = analysis_connection.runtime(
            compiled_sql=str(query.get("compiledSql") or "semantic whitelist join"),
            params=query.pop("_compiledParams", []),
        )
    execution_plan = {**execution_plan, "relationshipPathProof": path_proof}
    relationships = execution_plan["relationships"]
    return {
        "ok": True,
        "executed": True,
        "semanticPlan": semantic_plan,
        "executionPlan": execution_plan,
        "relationshipPathProof": path_proof,
        "relationshipQuery": query,
        "query": {
            "table": "->".join(query["tables"]),
            "tables": query["tables"],
            "mode": query["mode"],
            "group": query["groups"][0]["field"] if query["groups"] else "",
            "measure": execution_plan["measure"]["field"],
            "groupRefs": query["groups"],
            "measureRef": query["measure"],
            "aggregation": query["aggregation"],
            "filters": query["filters"],
            "joins": relationships,
            "relationshipPathProof": path_proof,
            "runtime": {
                **query_runtime,
                "executionPlanHash": execution_plan["planHash"],
                "pathProofFingerprint": path_proof.get("fingerprint"),
            },
        },
    }


def semantic_query_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    quote_identifier: Callable[[str], str],
    build_relationship_query: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    with open_db() as connection:
        return execute_workspace_semantic_query(
            connection,
            active_workspace_id(connection),
            str(args.prompt),
            selected_table_key=str(getattr(args, "table", "") or ""),
            limit=int(getattr(args, "limit", 50) or 50),
            table_columns=table_columns,
            quote_identifier=quote_identifier,
            build_relationship_query=build_relationship_query,
        )
