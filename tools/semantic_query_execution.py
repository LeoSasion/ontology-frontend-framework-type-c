from __future__ import annotations

import hashlib
import json
import sqlite3
import argparse
from typing import Any, Callable

from semantic_query_planner import build_workspace_semantic_plan


EXECUTION_PLAN_SCHEMA = "aibi-semantic-query-execution-plan/v1"
SAFE_AGGREGATIONS = {"count", "count-distinct", "sum", "avg", "min", "max"}


def _plan_hash(payload: dict[str, Any]) -> str:
    material = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _blocked_plan(semantic_plan: dict[str, Any], blockers: list[str]) -> dict[str, Any]:
    payload = {
        "schema": EXECUTION_PLAN_SCHEMA,
        "status": "blocked",
        "autoExecutable": False,
        "blockers": list(dict.fromkeys(blockers)),
        "semanticPlanStatus": semantic_plan.get("status"),
        "rootTable": semantic_plan.get("joinPlan", {}).get("rootTable"),
    }
    return {**payload, "planHash": _plan_hash(payload)}


def _left_groups_are_functional(
    connection: sqlite3.Connection,
    physical_table: str,
    key_fields: list[str],
    group_fields: list[str],
    quote_identifier: Callable[[str], str],
) -> bool:
    if not group_fields:
        return True
    projection = list(dict.fromkeys([*key_fields, *group_fields]))
    projection_sql = ", ".join(quote_identifier(field) for field in projection)
    keys_sql = ", ".join(quote_identifier(field) for field in key_fields)
    row = connection.execute(
        f"SELECT 1 FROM (SELECT DISTINCT {projection_sql} FROM {quote_identifier(physical_table)}) AS grain "
        f"GROUP BY {keys_sql} HAVING COUNT(*) > 1 LIMIT 1"
    ).fetchone()
    return row is None


def build_semantic_query_execution_plan(semantic_plan: dict[str, Any]) -> dict[str, Any]:
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
    targets = join_plan.get("targets") if isinstance(join_plan.get("targets"), list) else []
    if len(targets) != 1:
        blockers.append("single-target-only")
    selected_path = targets[0].get("selectedPath") if len(targets) == 1 and isinstance(targets[0], dict) else None
    hops = selected_path.get("hops") if isinstance(selected_path, dict) and isinstance(selected_path.get("hops"), list) else []
    if len(hops) not in {1, 2}:
        blockers.append("supported-hop-count-exceeded")
    relationships: list[dict[str, Any]] = []
    for hop in hops:
        if not isinstance(hop, dict):
            blockers.append("invalid-relationship-hop")
            continue
        risk = hop.get("risk") if isinstance(hop.get("risk"), dict) else {}
        if not risk.get("safeForPlanning"):
            blockers.extend(str(item) for item in risk.get("risks") or ["unsafe-relationship"])
        if str(hop.get("validationStatus") or "") != "validated":
            blockers.append("relationship-not-currently-validated")
        relationships.append({
            "relationKey": str(hop.get("relationKey") or ""),
            "leftTable": str(hop.get("relationshipLeftTable") or ""),
            "rightTable": str(hop.get("relationshipRightTable") or ""),
            "joinType": str(hop.get("joinType") or "left"),
            "direction": str(hop.get("direction") or "forward"),
            "fieldMappings": hop.get("fieldMappings") or [],
            "filters": hop.get("filters") or [],
            "preaggregation": hop.get("preaggregation") or {},
            "dataVersions": hop.get("dataVersions") or {},
            "updatedAt": str(hop.get("relationshipUpdatedAt") or ""),
        })
    if len(relationships) == 2:
        if any(item["direction"] != "forward" for item in relationships):
            blockers.append("two-hop-forward-only")
        if any(item["filters"] for item in relationships):
            blockers.append("two-hop-filters-not-yet-supported")
        if any(item["preaggregation"] for item in relationships):
            blockers.append("two-hop-preaggregation-not-yet-supported")

    path_tables = selected_path.get("tables") if isinstance(selected_path, dict) and isinstance(selected_path.get("tables"), list) else []
    supported_tables = {str(item) for item in path_tables}
    groups: list[dict[str, str]] = []
    for dimension in dimensions:
        if not isinstance(dimension, dict):
            blockers.append("invalid-dimension")
            continue
        table_key = str(dimension.get("tableKey") or "")
        field = str(dimension.get("field") or "")
        if table_key not in supported_tables or not field:
            blockers.append("dimension-outside-selected-hop")
            continue
        groups.append({"side": "left" if table_key == str(join_plan.get("rootTable") or "") else "right", "tableKey": table_key, "field": field})
    measure_table = str(measure.get("tableKey") or "")
    measure_field = str(measure.get("field") or "")
    if measure_table not in supported_tables or not measure_field:
        blockers.append("measure-outside-selected-hop")
    if blockers:
        return _blocked_plan(semantic_plan, blockers)

    payload = {
        "schema": EXECUTION_PLAN_SCHEMA,
        "status": "ready",
        "autoExecutable": True,
        "blockers": [],
        "semanticPlanStatus": "ready",
        "rootTable": str(join_plan.get("rootTable") or ""),
        "relationships": relationships,
        "groups": groups,
        "measure": {
            "side": "left" if measure_table == str(join_plan.get("rootTable") or "") else "right",
            "tableKey": measure_table,
            "field": measure_field,
            "aggregation": aggregation,
        },
        "finalGrain": [f"{item['tableKey']}.{item['field']}" for item in groups],
    }
    if len(relationships) == 1:
        payload["relationship"] = relationships[0]
    return {**payload, "planHash": _plan_hash(payload)}


def _execute_two_hop_query(
    connection: sqlite3.Connection,
    execution_plan: dict[str, Any],
    registries: dict[str, sqlite3.Row],
    *,
    limit: int,
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    quote_identifier: Callable[[str], str],
) -> tuple[dict[str, Any] | None, str | None]:
    relationships = execution_plan["relationships"]
    first, second = relationships
    table_keys = [first["leftTable"], first["rightTable"], second["rightTable"]]
    if first["rightTable"] != second["leftTable"]:
        return None, "two-hop-path-is-not-linear"
    if any(table_key not in registries for table_key in table_keys):
        return None, "relationship-table-missing-at-execution"
    physical = {key: str(registries[key]["physical_table"]) for key in table_keys}
    columns = {key: table_columns(connection, physical[key]) for key in table_keys}
    for relationship in relationships:
        for mapping in relationship["fieldMappings"]:
            if mapping.get("leftField") not in columns[relationship["leftTable"]] or mapping.get("rightField") not in columns[relationship["rightTable"]]:
                return None, "relationship-field-missing-at-execution"
    for item in [*execution_plan["groups"], execution_plan["measure"]]:
        if item["field"] not in columns[item["tableKey"]]:
            return None, "selected-field-missing-at-execution"

    root_table = table_keys[0]
    root_group_fields = [item["field"] for item in execution_plan["groups"] if item["tableKey"] == root_table]
    deduplicate_root = execution_plan["measure"]["tableKey"] != root_table
    root_key_fields = [str(item.get("leftField") or "") for item in first["fieldMappings"]]
    if deduplicate_root and not _left_groups_are_functional(
        connection,
        physical[root_table],
        root_key_fields,
        root_group_fields,
        quote_identifier,
    ):
        return None, "root-group-not-functionally-dependent-on-first-hop-key"

    alias_by_table = {table_key: f"t{index}" for index, table_key in enumerate(table_keys)}
    root_source = quote_identifier(physical[root_table])
    if deduplicate_root:
        projection = list(dict.fromkeys([*root_key_fields, *root_group_fields]))
        projection_sql = ", ".join(quote_identifier(field) for field in projection)
        root_source = f"(SELECT {projection_sql} FROM {quote_identifier(physical[root_table])} GROUP BY {projection_sql})"
    select_parts = []
    group_parts = []
    output_groups = []
    for item in execution_plan["groups"]:
        alias = alias_by_table[item["tableKey"]]
        expression = f"{alias}.{quote_identifier(item['field'])}"
        output_name = f"{item['tableKey']}.{item['field']}"
        select_parts.append(f"{expression} AS {quote_identifier(output_name)}")
        group_parts.append(expression)
        output_groups.append({"tableKey": item["tableKey"], "field": item["field"], "outputName": output_name})
    measure = execution_plan["measure"]
    measure_alias = alias_by_table[measure["tableKey"]]
    measure_column = f"{measure_alias}.{quote_identifier(measure['field'])}"
    numeric_measure = f"CAST(REPLACE(COALESCE({measure_column}, '0'), ',', '') AS REAL)"
    aggregation = measure["aggregation"]
    if aggregation == "count":
        metric_expression = "COUNT(*)"
    elif aggregation == "count-distinct":
        metric_expression = f"COUNT(DISTINCT {measure_column})"
    else:
        metric_expression = f"{aggregation.upper()}({numeric_measure})"
    metric_name = f"{aggregation}_{measure['tableKey']}.{measure['field']}"
    select_parts.append(f"{metric_expression} AS {quote_identifier(metric_name)}")

    first_condition = " AND ".join(
        f"t0.{quote_identifier(item['leftField'])} = t1.{quote_identifier(item['rightField'])}"
        for item in first["fieldMappings"]
    )
    second_condition = " AND ".join(
        f"t1.{quote_identifier(item['leftField'])} = t2.{quote_identifier(item['rightField'])}"
        for item in second["fieldMappings"]
    )
    first_join = "JOIN" if first["joinType"] == "inner" else "LEFT JOIN"
    second_join = "JOIN" if second["joinType"] == "inner" else "LEFT JOIN"
    group_sql = f" GROUP BY {', '.join(group_parts)}" if group_parts else ""
    safe_limit = max(1, min(int(limit or 50), 10000))
    sql = (
        f"SELECT {', '.join(select_parts)} FROM {root_source} AS t0 "
        f"{first_join} {quote_identifier(physical[table_keys[1]])} AS t1 ON {first_condition} "
        f"{second_join} {quote_identifier(physical[table_keys[2]])} AS t2 ON {second_condition}"
        f"{group_sql} ORDER BY {quote_identifier(metric_name)} DESC LIMIT ?"
    )
    rows = connection.execute(sql, (safe_limit,)).fetchall()
    return {
        "mode": "semantic-two-hop",
        "tables": table_keys,
        "relationships": relationships,
        "groups": output_groups,
        "measure": {"tableKey": measure["tableKey"], "field": measure["field"], "outputName": f"{measure['tableKey']}.{measure['field']}"},
        "aggregation": aggregation,
        "filters": [],
        "preaggregation": {},
        "rootDeduplicated": deduplicate_root,
        "metricName": metric_name,
        "columns": [*[item["outputName"] for item in output_groups], metric_name],
        "rows": [dict(row) for row in rows],
        "sqlShape": {"tables": table_keys, "relationshipKeys": [item["relationKey"] for item in relationships], "finalGrain": execution_plan["finalGrain"], "limit": safe_limit},
    }, None


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
) -> dict[str, Any]:
    provided_semantic_plan = semantic_plan
    fresh_semantic_plan = build_workspace_semantic_plan(
        connection,
        workspace_id,
        prompt,
        selected_table_key=selected_table_key,
        table_columns=table_columns,
    )
    semantic_plan = fresh_semantic_plan
    execution_plan = build_semantic_query_execution_plan(semantic_plan)
    if provided_semantic_plan:
        provided_execution_plan = build_semantic_query_execution_plan(provided_semantic_plan)
        if provided_execution_plan.get("planHash") != execution_plan.get("planHash"):
            execution_plan = _blocked_plan(semantic_plan, ["semantic-plan-changed-before-execution"])
            return {"ok": True, "executed": False, "semanticPlan": semantic_plan, "executionPlan": execution_plan}
    if execution_plan["status"] != "ready":
        return {"ok": True, "executed": False, "semanticPlan": semantic_plan, "executionPlan": execution_plan}

    relationships = execution_plan["relationships"]
    table_keys = list(dict.fromkeys(
        table_key
        for relationship in relationships
        for table_key in (relationship["leftTable"], relationship["rightTable"])
    ))
    placeholders = ", ".join("?" for _ in table_keys)
    registry_rows = connection.execute(
        f"SELECT * FROM table_registry WHERE workspace_id = ? AND table_key IN ({placeholders})",
        (workspace_id, *table_keys),
    ).fetchall()
    registries = {str(row["table_key"]): row for row in registry_rows}
    if len(relationships) == 2:
        query, blocker = _execute_two_hop_query(
            connection,
            execution_plan,
            registries,
            limit=limit,
            table_columns=table_columns,
            quote_identifier=quote_identifier,
        )
        if blocker or query is None:
            execution_plan = _blocked_plan(semantic_plan, [blocker or "two-hop-execution-failed"])
            return {"ok": True, "executed": False, "semanticPlan": semantic_plan, "executionPlan": execution_plan}
        return {
            "ok": True,
            "executed": True,
            "semanticPlan": semantic_plan,
            "executionPlan": execution_plan,
            "relationshipQuery": query,
            "query": {
                "table": "->".join(query["tables"]),
                "mode": "semantic-two-hop",
                "group": query["groups"][0]["field"] if query["groups"] else "",
                "measure": execution_plan["measure"]["field"],
                "groupRefs": query["groups"],
                "measureRef": query["measure"],
                "aggregation": query["aggregation"],
                "filters": [],
                "joins": relationships,
                "runtime": {
                    "engine": "sqlite",
                    "compiledSql": "semantic two-hop whitelist join",
                    "executionPlanHash": execution_plan["planHash"],
                },
            },
        }

    relationship = relationships[0]
    left = registries.get(relationship["leftTable"])
    right = registries.get(relationship["rightTable"])
    if not left or not right:
        execution_plan = _blocked_plan(semantic_plan, ["relationship-table-missing-at-execution"])
        return {"ok": True, "executed": False, "semanticPlan": semantic_plan, "executionPlan": execution_plan}

    deduplicate_left = execution_plan["measure"]["side"] == "right"
    if deduplicate_left:
        incompatible_left_post_filters = [
            item for item in relationship["filters"]
            if isinstance(item, dict) and item.get("side") == "left" and item.get("phase") != "pre"
        ]
        left_group_fields = [item["field"] for item in execution_plan["groups"] if item["side"] == "left"]
        left_key_fields = [str(item.get("leftField") or "") for item in relationship["fieldMappings"]]
        if incompatible_left_post_filters:
            execution_plan = _blocked_plan(semantic_plan, ["left-post-filter-incompatible-with-right-measure-grain"])
            return {"ok": True, "executed": False, "semanticPlan": semantic_plan, "executionPlan": execution_plan}
        if not _left_groups_are_functional(
            connection,
            str(left["physical_table"]),
            left_key_fields,
            left_group_fields,
            quote_identifier,
        ):
            execution_plan = _blocked_plan(semantic_plan, ["left-group-not-functionally-dependent-on-join-key"])
            return {"ok": True, "executed": False, "semanticPlan": semantic_plan, "executionPlan": execution_plan}

    query = build_relationship_query(
        connection,
        str(left["physical_table"]),
        str(right["physical_table"]),
        table_columns(connection, str(left["physical_table"])),
        table_columns(connection, str(right["physical_table"])),
        relationship["fieldMappings"],
        group_fields=[{"side": item["side"], "field": item["field"]} for item in execution_plan["groups"]],
        measure={"side": execution_plan["measure"]["side"], "field": execution_plan["measure"]["field"]},
        aggregation=execution_plan["measure"]["aggregation"],
        join_type=relationship["joinType"],
        filters=relationship["filters"],
        preaggregation=relationship["preaggregation"],
        deduplicate_left=deduplicate_left,
        limit=limit,
        sort_by="metric",
        sort_direction="desc",
        quote_identifier=quote_identifier,
    )
    return {
        "ok": True,
        "executed": True,
        "semanticPlan": semantic_plan,
        "executionPlan": execution_plan,
        "relationshipQuery": query,
        "query": {
            "table": f"{relationship['leftTable']}->{relationship['rightTable']}",
            "mode": "semantic-relationship",
            "group": query["groups"][0]["field"] if query["groups"] else "",
            "measure": execution_plan["measure"]["field"],
            "groupRefs": query["groups"],
            "measureRef": query["measure"],
            "aggregation": query["aggregation"],
            "filters": query["filters"],
            "joins": [relationship],
            "runtime": {
                "engine": "sqlite",
                "compiledSql": "semantic relationship whitelist join",
                "executionPlanHash": execution_plan["planHash"],
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
