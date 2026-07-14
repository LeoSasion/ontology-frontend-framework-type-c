from __future__ import annotations

import json
import re
import sqlite3
from collections import deque
from typing import Any, Callable


PLAN_SCHEMA = "aibi-semantic-query-plan/v1"
BLOCKING_STATUSES = {"needs-clarification", "needs-relationship", "needs-validation"}


def normalize_semantic_text(value: Any) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(value or "").casefold())


def _unitless_alias(value: str) -> str:
    return re.sub(r"(?:人民币|百分比|万元|亿元|元|个|件|次|人|天|小时|率)$", "", value)


def _candidate_aliases(candidate: dict[str, Any]) -> list[str]:
    aliases: list[str] = []
    for raw in [candidate.get("field"), *(candidate.get("aliases") or [])]:
        normalized = normalize_semantic_text(raw)
        for alias in [normalized, _unitless_alias(normalized)]:
            if len(alias) >= 2 and alias not in aliases:
                aliases.append(alias)
    return aliases


def resolve_field_candidates(
    prompt: str,
    field_catalog: list[dict[str, Any]],
    *,
    selected_table_key: str = "",
) -> dict[str, Any]:
    prompt_text = normalize_semantic_text(prompt)
    matched: dict[str, list[dict[str, Any]]] = {}
    for candidate in field_catalog:
        mentions = [alias for alias in _candidate_aliases(candidate) if alias in prompt_text]
        if not mentions:
            continue
        mention = max(mentions, key=lambda item: (len(item), item))
        matched.setdefault(mention, []).append(
            {
                "id": str(candidate.get("id") or ""),
                "tableKey": str(candidate.get("tableKey") or ""),
                "tableName": str(candidate.get("tableName") or ""),
                "field": str(candidate.get("field") or ""),
                "role": str(candidate.get("role") or "unknown"),
                "aggregation": str(candidate.get("aggregation") or ""),
                "confidence": round(float(candidate.get("confidence") or 0), 4),
                "source": str(candidate.get("source") or "schema"),
                "matchedAlias": mention,
            }
        )

    bindings: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    selected_by_id: dict[str, dict[str, Any]] = {}
    for mention, rows in sorted(matched.items(), key=lambda item: (-len(item[0]), item[0])):
        deduped = {row["id"]: row for row in rows if row["id"]}
        candidates = sorted(
            deduped.values(),
            key=lambda item: (-item["confidence"], item["tableName"], item["field"]),
        )
        explicitly_named_tables = [
            item
            for item in candidates
            if len(normalize_semantic_text(item["tableName"])) >= 2
            and normalize_semantic_text(item["tableName"]) in prompt_text
        ]
        explicitly_bound_tables = [
            item
            for item in candidates
            if len(normalize_semantic_text(item["tableName"])) >= 2
            and any(
                pattern in prompt_text
                for pattern in (
                    f"{normalize_semantic_text(item['tableName'])}的{mention}",
                    f"{normalize_semantic_text(item['tableName'])}{mention}",
                )
            )
        ]
        selected_table_candidates = [
            item for item in candidates if selected_table_key and item["tableKey"] == selected_table_key
        ]
        narrowed = explicitly_bound_tables or explicitly_named_tables or selected_table_candidates or candidates
        unique_tables = {item["tableKey"] for item in narrowed}
        status = "resolved" if len(narrowed) == 1 else "ambiguous"
        if len(narrowed) > 1 and len(unique_tables) == 1:
            status = "ambiguous"
        selected = narrowed[0] if status == "resolved" else None
        binding = {
            "mention": mention,
            "status": status,
            "selected": selected,
            "candidates": narrowed[:6],
            "reason": (
                "explicit-table-field"
                if explicitly_bound_tables and selected
                else ("explicit-table"
                if explicitly_named_tables and selected
                else (
                    "selected-object-context"
                    if selected_table_candidates and selected
                    else ("single-candidate" if selected else "multiple-field-candidates")
                ))
            ),
        }
        bindings.append(binding)
        if selected:
            selected_by_id[selected["id"]] = selected
        else:
            unresolved.append(binding)

    if not bindings:
        status = "missing"
    elif unresolved:
        status = "needs-clarification"
    else:
        status = "resolved"
    return {
        "status": status,
        "bindings": bindings,
        "selected": list(selected_by_id.values()),
        "unresolved": unresolved,
    }


def _relationship_risk(relationship: dict[str, Any], direction: str) -> dict[str, Any]:
    confidence = max(0.0, min(1.0, float(relationship.get("confidence") or 0)))
    mappings = [item for item in relationship.get("fieldMappings") or [] if isinstance(item, dict)]
    risks: list[str] = []
    if not mappings or any(not item.get("leftField") or not item.get("rightField") for item in mappings):
        risks.append("missing-field-mapping")
    if confidence < 0.55:
        risks.append("low-confidence-relationship")
    validation_status = str(relationship.get("validationStatus") or "")
    if validation_status != "validated":
        risks.append("stale-relationship" if validation_status == "stale" else "relationship-not-validated")
    expected_versions = relationship.get("dataVersions") if isinstance(relationship.get("dataVersions"), dict) else {}
    current_versions = relationship.get("currentDataVersions") if isinstance(relationship.get("currentDataVersions"), dict) else {}
    if expected_versions and current_versions and any(
        int(expected_versions.get(key) or 0) != int(version or 0)
        for key, version in current_versions.items()
    ):
        risks.append("relationship-version-mismatch")
    join_type = str(relationship.get("joinType") or "left")
    if direction == "reverse" and join_type != "inner":
        risks.append("reverse-left-join")
    if relationship.get("rowExpansion") is None:
        risks.append("missing-row-expansion-evidence")
    elif float(relationship.get("rowExpansion") or 0) > 1.000001:
        risks.append("row-expansion")
    return {
        "safeForPlanning": not risks,
        "risks": risks,
        "confidence": round(confidence, 4),
        "requiresCurrentPreview": True,
        "composite": len(mappings) > 1,
    }


def find_relationship_paths(
    relationships: list[dict[str, Any]],
    start_table: str,
    target_table: str,
    *,
    max_hops: int = 3,
    limit: int = 5,
) -> list[dict[str, Any]]:
    if not start_table or not target_table:
        return []
    if start_table == target_table:
        return [{"tables": [start_table], "hops": [], "safeForPlanning": True, "risks": []}]
    graph: dict[str, list[dict[str, Any]]] = {}
    for relationship in relationships:
        left = str(relationship.get("leftTableKey") or "")
        right = str(relationship.get("rightTableKey") or "")
        if not left or not right:
            continue
        graph.setdefault(left, []).append({"target": right, "direction": "forward", "relationship": relationship})
        graph.setdefault(right, []).append({"target": left, "direction": "reverse", "relationship": relationship})

    queue = deque([(start_table, [start_table], [])])
    paths: list[dict[str, Any]] = []
    while queue and len(paths) < limit:
        current, visited, hops = queue.popleft()
        if len(hops) >= max_hops:
            continue
        for edge in graph.get(current, []):
            target = edge["target"]
            if target in visited:
                continue
            relationship = edge["relationship"]
            risk = _relationship_risk(relationship, edge["direction"])
            hop = {
                "relationKey": str(relationship.get("relationKey") or ""),
                "relationshipLeftTable": str(relationship.get("leftTableKey") or ""),
                "relationshipRightTable": str(relationship.get("rightTableKey") or ""),
                "fromTable": current,
                "toTable": target,
                "direction": edge["direction"],
                "joinType": str(relationship.get("joinType") or "left"),
                "fieldMappings": relationship.get("fieldMappings") or [],
                "filters": relationship.get("filters") or [],
                "preaggregation": relationship.get("preaggregation") or {},
                "validationStatus": relationship.get("validationStatus") or "",
                "dataVersions": relationship.get("dataVersions") or {},
                "currentDataVersions": relationship.get("currentDataVersions") or {},
                "relationshipUpdatedAt": relationship.get("updatedAt") or "",
                "risk": risk,
            }
            next_hops = [*hops, hop]
            next_visited = [*visited, target]
            if target == target_table:
                risks = list(dict.fromkeys(
                    item
                    for path_hop in next_hops
                    for item in path_hop["risk"]["risks"]
                ))
                paths.append(
                    {
                        "tables": next_visited,
                        "hops": next_hops,
                        "safeForPlanning": not risks,
                        "risks": risks,
                    }
                )
            else:
                queue.append((target, next_visited, next_hops))
    return sorted(paths, key=lambda item: (not item["safeForPlanning"], len(item["hops"]), len(item["risks"])))


def build_semantic_query_plan(
    prompt: str,
    field_catalog: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    *,
    selected_table_key: str = "",
) -> dict[str, Any]:
    field_resolution = resolve_field_candidates(
        prompt,
        field_catalog,
        selected_table_key=selected_table_key,
    )
    selected = field_resolution["selected"]
    resolved_tables = list(dict.fromkeys(str(item.get("tableKey") or "") for item in selected if item.get("tableKey")))
    required_tables = list(dict.fromkeys([selected_table_key, *resolved_tables]))
    required_tables = [item for item in required_tables if item]
    root_table = selected_table_key or (required_tables[0] if required_tables else "")
    targets: list[dict[str, Any]] = []
    for target_table in required_tables:
        if not root_table or target_table == root_table:
            continue
        paths = find_relationship_paths(relationships, root_table, target_table)
        targets.append(
            {
                "targetTable": target_table,
                "paths": paths,
                "selectedPath": paths[0] if paths else None,
            }
        )

    path_missing = any(not item["paths"] for item in targets)
    path_unsafe = any(item["selectedPath"] and not item["selectedPath"]["safeForPlanning"] for item in targets)
    if field_resolution["status"] == "missing":
        status = "not-applicable"
    elif field_resolution["status"] != "resolved":
        status = "needs-clarification"
    elif path_missing:
        status = "needs-relationship"
    elif path_unsafe:
        status = "needs-validation"
    else:
        status = "ready"
    return {
        "schema": PLAN_SCHEMA,
        "status": status,
        "autoExecutable": False,
        "fieldResolution": field_resolution,
        "grain": {
            "dimensions": [item for item in selected if item.get("role") in {"dimension", "event_time", "status"}],
            "measures": [item for item in selected if item.get("role") == "measure"],
            "otherFields": [item for item in selected if item.get("role") not in {"dimension", "event_time", "status", "measure"}],
            "tables": required_tables,
        },
        "joinPlan": {
            "rootTable": root_table,
            "requiredTables": required_tables,
            "targets": targets,
            "maxHops": 3,
        },
        "executionBoundary": "planning-only; saved relationships are candidates; current preview and whitelist query are still required",
    }


def _quote_identifier(value: str) -> str:
    return f'"{str(value).replace(chr(34), chr(34) * 2)}"'


def build_workspace_semantic_plan(
    connection: sqlite3.Connection,
    workspace_id: str,
    prompt: str,
    *,
    selected_table_key: str = "",
    table_columns: Callable[[sqlite3.Connection, str], list[str]] | None = None,
) -> dict[str, Any]:
    registries = connection.execute(
        "SELECT table_key, display_name, physical_table, data_version FROM table_registry WHERE workspace_id = ? ORDER BY table_key",
        (workspace_id,),
    ).fetchall()
    semantics = connection.execute(
        "SELECT table_key, field_name, role, confidence FROM field_semantics WHERE workspace_id = ?",
        (workspace_id,),
    ).fetchall()
    semantic_map = {(str(row["table_key"]), str(row["field_name"])): dict(row) for row in semantics}
    metrics = connection.execute(
        "SELECT table_key, label, measure, aggregation, dimension, time_field FROM metric_definitions WHERE workspace_id = ?",
        (workspace_id,),
    ).fetchall()
    aliases_by_field: dict[tuple[str, str], list[str]] = {}
    aggregations_by_field: dict[tuple[str, str], list[str]] = {}
    for metric in metrics:
        table_key = str(metric["table_key"])
        if metric["measure"]:
            aliases_by_field.setdefault((table_key, str(metric["measure"])), []).append(str(metric["label"]))
            aggregations_by_field.setdefault((table_key, str(metric["measure"])), []).append(str(metric["aggregation"]))

    field_catalog: list[dict[str, Any]] = []
    for registry in registries:
        table_key = str(registry["table_key"])
        physical_table = str(registry["physical_table"])
        if table_columns:
            columns = table_columns(connection, physical_table)
        else:
            columns = [str(row[1]) for row in connection.execute(f"PRAGMA table_info({_quote_identifier(physical_table)})")]
        for field_name in columns:
            if field_name.startswith("__"):
                continue
            semantic = semantic_map.get((table_key, field_name), {})
            field_catalog.append(
                {
                    "id": f"{table_key}:{field_name}",
                    "tableKey": table_key,
                    "tableName": str(registry["display_name"]),
                    "field": field_name,
                    "role": str(semantic.get("role") or "unknown"),
                    "confidence": float(semantic.get("confidence") or 0),
                    "source": "workspace-semantic" if semantic else "schema",
                    "aliases": aliases_by_field.get((table_key, field_name), []),
                    "aggregation": next(iter(dict.fromkeys(aggregations_by_field.get((table_key, field_name), []))), ""),
                }
            )

    relationship_rows = connection.execute(
        """
        SELECT relation_key, left_table_key, right_table_key, left_field, right_field,
               mappings_json, filters_json, preaggregation_json, join_type, confidence, validation_json, updated_at
        FROM relationships
        WHERE workspace_id = ?
        ORDER BY relation_key
        """,
        (workspace_id,),
    ).fetchall()
    relationships = []
    current_versions = {str(row["table_key"]): int(row["data_version"] or 1) for row in registries}
    for row in relationship_rows:
        try:
            mappings = json.loads(str(row["mappings_json"] or "[]"))
        except json.JSONDecodeError:
            mappings = []
        if not isinstance(mappings, list) or not mappings:
            mappings = [{"leftField": str(row["left_field"]), "rightField": str(row["right_field"])}]
        try:
            validation = json.loads(str(row["validation_json"] or "{}"))
        except json.JSONDecodeError:
            validation = {}
        validation_metrics = validation.get("metrics") if isinstance(validation, dict) and isinstance(validation.get("metrics"), dict) else {}
        try:
            filters = json.loads(str(row["filters_json"] or "[]"))
        except json.JSONDecodeError:
            filters = []
        try:
            preaggregation = json.loads(str(row["preaggregation_json"] or "{}"))
        except json.JSONDecodeError:
            preaggregation = {}
        relation_versions = {
            str(row["left_table_key"]): current_versions.get(str(row["left_table_key"]), 0),
            str(row["right_table_key"]): current_versions.get(str(row["right_table_key"]), 0),
        }
        relationships.append({
            "relationKey": str(row["relation_key"]),
            "leftTableKey": str(row["left_table_key"]),
            "rightTableKey": str(row["right_table_key"]),
            "fieldMappings": mappings,
            "joinType": str(row["join_type"] or "left"),
            "confidence": float(row["confidence"] or 0),
            "rowExpansion": validation_metrics.get("rowExpansion"),
            "filters": filters if isinstance(filters, list) else [],
            "preaggregation": preaggregation if isinstance(preaggregation, dict) else {},
            "validationStatus": str(validation.get("status") or "") if isinstance(validation, dict) else "",
            "dataVersions": validation.get("dataVersions") if isinstance(validation, dict) and isinstance(validation.get("dataVersions"), dict) else {},
            "currentDataVersions": relation_versions,
            "updatedAt": str(row["updated_at"] or ""),
        })
    return build_semantic_query_plan(
        prompt,
        field_catalog,
        relationships,
        selected_table_key=selected_table_key,
    )
