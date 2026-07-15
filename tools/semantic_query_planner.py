from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from collections import deque
from typing import Any, Callable


PLAN_SCHEMA = "aibi-semantic-query-plan/v1"
BLOCKING_STATUSES = {"needs-clarification", "needs-relationship", "needs-validation"}
PATH_SEARCH_HARD_LIMIT = 256


def normalize_semantic_text(value: Any) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(value or "").casefold())


_RELATIONSHIP_PATH_DIRECTIVE = re.compile(
    r"(?:(?:使用|选择|use|select)\s*)?(?:关系路径|relationship\s+path)\s*[:：=]?\s*"
    r"([^\s>，,;；]+(?:\s*>\s*[^\s>，,;；]+)*)",
    re.IGNORECASE,
)
_ROOT_TABLE_DIRECTIVE = re.compile(
    r"(?:(?:使用|选择|use|select)\s*)?(?:根表|root\s+table)\s*[:：=]?\s*([^\s，,;；]+)",
    re.IGNORECASE,
)


def semantic_query_prompt_directives(prompt: str) -> dict[str, Any]:
    """Separate deterministic planning selectors from the business question."""
    raw_prompt = str(prompt or "")
    relationship_match = _RELATIONSHIP_PATH_DIRECTIVE.search(raw_prompt)
    root_match = _ROOT_TABLE_DIRECTIVE.search(raw_prompt)
    relationship_keys = [
        item.strip().rstrip("。.!！?")
        for item in (relationship_match.group(1).split(">") if relationship_match else [])
        if item.strip().rstrip("。.!！?")
    ]
    root_table = root_match.group(1).strip().rstrip("。.!！?") if root_match else ""
    spans = sorted(
        [match.span() for match in (relationship_match, root_match) if match],
        reverse=True,
    )
    base_prompt = raw_prompt
    for start, end in spans:
        base_prompt = f"{base_prompt[:start]}{base_prompt[end:]}"
    base_prompt = re.sub(r"[\s，,;；]+$", "", base_prompt).strip()
    return {
        "basePrompt": base_prompt or raw_prompt,
        "relationshipPath": relationship_keys,
        "rootTable": root_table,
    }


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
        metric_definitions = [
            definition
            for definition in candidate.get("metricDefinitions") or []
            if isinstance(definition, dict)
        ]
        matched_metric_definitions = [
            definition
            for definition in metric_definitions
            if mention in {
                normalize_semantic_text(definition.get("label")),
                _unitless_alias(normalize_semantic_text(definition.get("label"))),
            }
        ]
        source_role = str(candidate.get("role") or "unknown")
        resolved_candidates = matched_metric_definitions or [None]
        for metric_definition in resolved_candidates:
            metric_match = metric_definition is not None
            aggregation = (
                str(metric_definition.get("aggregation") or "")
                if metric_definition
                else str(candidate.get("aggregation") or "")
            )
            metric_identity = (
                f"#metric:{normalize_semantic_text(metric_definition.get('label'))}:{aggregation}"
                if metric_definition
                else ""
            )
            matched.setdefault(mention, []).append({
                "id": f"{str(candidate.get('id') or '')}{metric_identity}",
                "tableKey": str(candidate.get("tableKey") or ""),
                "tableName": str(candidate.get("tableName") or ""),
                "field": str(candidate.get("field") or ""),
                "role": "measure" if metric_match else source_role,
                "sourceRole": source_role,
                "metricMatch": metric_match,
                "metricLabel": str(metric_definition.get("label") or "") if metric_definition else "",
                "aggregation": aggregation,
                "confidence": round(float(candidate.get("confidence") or 0), 4),
                "source": str(candidate.get("source") or "schema"),
                "matchedAlias": mention,
            })

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
    required_version_tables = {
        str(relationship.get("leftTableKey") or ""),
        str(relationship.get("rightTableKey") or ""),
    } - {""}
    if not required_version_tables.issubset(expected_versions) or not required_version_tables.issubset(current_versions):
        risks.append("missing-relationship-version-evidence")
    elif any(
        int(expected_versions.get(key) or 0) != int(current_versions.get(key) or 0)
        for key in required_version_tables
    ):
        risks.append("relationship-version-mismatch")
    join_type = str(relationship.get("joinType") or "left")
    if direction == "reverse" and join_type != "inner":
        risks.append("reverse-left-join")
    validation_metrics = (
        relationship.get("validationMetrics")
        if isinstance(relationship.get("validationMetrics"), dict)
        else {}
    )
    if direction == "reverse":
        expansion = validation_metrics.get("reverseMatchedRowExpansion")
        if expansion is None:
            expansion = validation_metrics.get("reverseRowExpansion")
        if expansion is None:
            risks.append("missing-reverse-row-expansion-evidence")
    else:
        expansion = validation_metrics.get("matchedRowExpansion")
        if expansion is None:
            expansion = relationship.get("rowExpansion")
        if expansion is None:
            risks.append("missing-row-expansion-evidence")
    if (
        expansion is not None
        and float(expansion or 0) > 1.000001
        and int(validation_metrics.get("leftDuplicateKeyGroups") or 0) > 0
        and int(validation_metrics.get("rightDuplicateKeyGroups") or 0) > 0
    ):
        risks.append("many-to-many-row-expansion")
    return {
        "safeForPlanning": not risks,
        "risks": risks,
        "confidence": round(confidence, 4),
        "requiresCurrentPreview": True,
        "composite": len(mappings) > 1,
    }


def _path_semantic_signature(path: dict[str, Any]) -> tuple[Any, ...]:
    """Identify materially different joins even when they traverse the same tables."""
    hop_signatures = []
    for hop in path.get("hops") or []:
        mappings = tuple(sorted(
            (str(item.get("leftField") or ""), str(item.get("rightField") or ""))
            for item in hop.get("fieldMappings") or []
            if isinstance(item, dict)
        ))
        filters = tuple(sorted(
            json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for item in hop.get("filters") or []
            if isinstance(item, dict)
        ))
        preaggregation = json.dumps(
            hop.get("preaggregation") or {},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        hop_signatures.append((
            str(hop.get("fromTable") or ""),
            str(hop.get("toTable") or ""),
            str(hop.get("direction") or ""),
            str(hop.get("joinType") or ""),
            mappings,
            filters,
            preaggregation,
        ))
    return (tuple(str(table) for table in path.get("tables") or []), tuple(hop_signatures))


def _path_rank(path: dict[str, Any]) -> tuple[Any, ...]:
    return (
        not bool(path.get("safeForPlanning")),
        len(path.get("hops") or []),
        len(path.get("risks") or []),
    )


def _path_sort_key(path: dict[str, Any]) -> tuple[Any, ...]:
    return (
        *_path_rank(path),
        tuple(str(hop.get("relationKey") or "") for hop in path.get("hops") or []),
    )


def _relationship_path_hop(
    relationship: dict[str, Any],
    current: str,
    target: str,
    direction: str,
) -> dict[str, Any]:
    risk = _relationship_risk(relationship, direction)
    return {
        "relationKey": str(relationship.get("relationKey") or ""),
        "relationshipLeftTable": str(relationship.get("leftTableKey") or ""),
        "relationshipRightTable": str(relationship.get("rightTableKey") or ""),
        "fromTable": current,
        "toTable": target,
        "direction": direction,
        "joinType": str(relationship.get("joinType") or "left"),
        "fieldMappings": relationship.get("fieldMappings") or [],
        "filters": relationship.get("filters") or [],
        "preaggregation": relationship.get("preaggregation") or {},
        "validationStatus": relationship.get("validationStatus") or "",
        "dataVersions": relationship.get("dataVersions") or {},
        "currentDataVersions": relationship.get("currentDataVersions") or {},
        "relationshipUpdatedAt": relationship.get("updatedAt") or "",
        "relationshipFingerprint": relationship.get("relationshipFingerprint") or "",
        "validationMetrics": relationship.get("validationMetrics") or {},
        "risk": risk,
    }


def _relationship_path(tables: list[str], hops: list[dict[str, Any]]) -> dict[str, Any]:
    risks = list(dict.fromkeys(
        item
        for hop in hops
        for item in hop.get("risk", {}).get("risks", [])
    ))
    return {
        "tables": tables,
        "hops": hops,
        "safeForPlanning": not risks,
        "risks": risks,
    }


def _path_prefix(path: dict[str, Any], target_table: str) -> dict[str, Any] | None:
    tables = [str(item) for item in path.get("tables") or []]
    if target_table not in tables:
        return None
    target_index = tables.index(target_table)
    return _relationship_path(
        tables[:target_index + 1],
        list(path.get("hops") or [])[:target_index],
    )


def _deduplicate_paths(paths: list[dict[str, Any]]) -> list[dict[str, Any]]:
    distinct: dict[tuple[Any, ...], dict[str, Any]] = {}
    for path in sorted(paths, key=_path_sort_key):
        distinct.setdefault(_path_semantic_signature(path), path)
    return sorted(distinct.values(), key=_path_sort_key)


def _find_explicit_relationship_paths(
    relationships: list[dict[str, Any]],
    start_table: str,
    relationship_keys: list[str],
    *,
    max_hops: int = 3,
) -> list[dict[str, Any]]:
    """Follow the exact ordered relationKey sequence without shortest-path pruning."""
    if not start_table or not relationship_keys or len(relationship_keys) > max_hops:
        return []
    states: list[tuple[str, list[str], list[dict[str, Any]]]] = [(start_table, [start_table], [])]
    for relationship_key in relationship_keys:
        next_states: list[tuple[str, list[str], list[dict[str, Any]]]] = []
        for current, visited, hops in states:
            for relationship in relationships:
                if normalize_semantic_text(relationship.get("relationKey")) != relationship_key:
                    continue
                left = str(relationship.get("leftTableKey") or "")
                right = str(relationship.get("rightTableKey") or "")
                if current == left:
                    target, direction = right, "forward"
                elif current == right:
                    target, direction = left, "reverse"
                else:
                    continue
                if not target or target in visited:
                    continue
                next_states.append((
                    target,
                    [*visited, target],
                    [*hops, _relationship_path_hop(relationship, current, target, direction)],
                ))
        states = next_states
        if not states:
            break
    if not states or any(len(hops) != len(relationship_keys) for _, _, hops in states):
        return []
    return _deduplicate_paths([
        _relationship_path(visited, hops)
        for _, visited, hops in states
    ])


def _find_relationship_path_search(
    relationships: list[dict[str, Any]],
    start_table: str,
    target_table: str,
    *,
    max_hops: int = 3,
    limit: int = 5,
) -> dict[str, Any]:
    if not start_table or not target_table:
        return {"paths": [], "truncated": False, "limit": limit}
    if start_table == target_table:
        return {
            "paths": [{"tables": [start_table], "hops": [], "safeForPlanning": True, "risks": []}],
            "truncated": False,
            "limit": limit,
        }
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
    truncated = False
    while queue and not truncated:
        current, visited, hops = queue.popleft()
        if len(hops) >= max_hops:
            continue
        for edge in graph.get(current, []):
            target = edge["target"]
            if target in visited:
                continue
            relationship = edge["relationship"]
            hop = _relationship_path_hop(relationship, current, target, edge["direction"])
            next_hops = [*hops, hop]
            next_visited = [*visited, target]
            if target == target_table:
                paths.append(_relationship_path(next_visited, next_hops))
                if len(paths) > limit:
                    truncated = True
                    break
            else:
                queue.append((target, next_visited, next_hops))
    return {
        "paths": sorted(paths, key=_path_sort_key)[:limit],
        "truncated": truncated,
        "limit": limit,
    }


def find_relationship_paths(
    relationships: list[dict[str, Any]],
    start_table: str,
    target_table: str,
    *,
    max_hops: int = 3,
    limit: int = 5,
) -> list[dict[str, Any]]:
    return _find_relationship_path_search(
        relationships,
        start_table,
        target_table,
        max_hops=max_hops,
        limit=limit,
    )["paths"]


def build_semantic_query_plan(
    prompt: str,
    field_catalog: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
    *,
    selected_table_key: str = "",
) -> dict[str, Any]:
    directives = semantic_query_prompt_directives(prompt)
    field_prompt = str(directives["basePrompt"])
    explicit_relationship_keys = [
        normalize_semantic_text(item)
        for item in directives["relationshipPath"]
        if normalize_semantic_text(item)
    ]
    explicit_root_table = str(directives["rootTable"] or "")
    known_tables = {
        str(item.get("tableKey") or "")
        for item in field_catalog
        if str(item.get("tableKey") or "")
    }
    known_tables.update(
        str(relationship.get(key) or "")
        for relationship in relationships
        for key in ("leftTableKey", "rightTableKey")
        if str(relationship.get(key) or "")
    )
    explicit_root_invalid = bool(explicit_root_table and explicit_root_table not in known_tables)
    effective_selected_table_key = (
        explicit_root_table
        if explicit_root_table and not explicit_root_invalid
        else selected_table_key
    )
    field_resolution = resolve_field_candidates(
        field_prompt,
        field_catalog,
        selected_table_key=effective_selected_table_key,
    )
    selected = field_resolution["selected"]
    resolved_tables = list(dict.fromkeys(str(item.get("tableKey") or "") for item in selected if item.get("tableKey")))
    required_tables = list(dict.fromkeys([effective_selected_table_key, *resolved_tables]))
    required_tables = [item for item in required_tables if item]
    root_table = "" if explicit_root_invalid else effective_selected_table_key
    root_candidates: list[str] = list(required_tables) if explicit_root_invalid else []
    requires_root_clarification = explicit_root_invalid
    dimension_tables = list(dict.fromkeys(
        str(item.get("tableKey") or "")
        for item in selected
        if item.get("tableKey") and item.get("role") in {"dimension", "event_time", "status"}
    ))
    measure_tables = list(dict.fromkeys(
        str(item.get("tableKey") or "")
        for item in selected
        if item.get("tableKey") and item.get("role") == "measure"
    ))
    path_search_limit = max(
        16,
        min(PATH_SEARCH_HARD_LIMIT, len(relationships) * len(relationships) + 1),
    )
    root_search_truncated = False
    if not root_table and required_tables and not explicit_root_invalid:
        if len(measure_tables) == 1 and dimension_tables:
            required_set = set(required_tables)
            viable_safe: list[str] = []
            viable_any: list[str] = []
            for candidate in dimension_tables:
                search = _find_relationship_path_search(
                    relationships,
                    candidate,
                    measure_tables[0],
                    limit=path_search_limit,
                )
                paths = search["paths"]
                root_search_truncated = root_search_truncated or bool(search["truncated"])
                covering = [path for path in paths if required_set.issubset(set(path.get("tables") or []))]
                if covering:
                    viable_any.append(candidate)
                if any(path.get("safeForPlanning") for path in covering):
                    viable_safe.append(candidate)
            root_candidates = viable_safe or viable_any
            if root_search_truncated and len(dimension_tables) > 1:
                root_candidates = dimension_tables
                requires_root_clarification = True
            elif len(root_candidates) == 1:
                root_table = root_candidates[0]
            elif len(root_candidates) > 1:
                requires_root_clarification = True
            elif len(dimension_tables) == 1:
                root_table = dimension_tables[0]
        if not root_table and not requires_root_clarification:
            root_table = required_tables[0]

    target_tables = [item for item in required_tables if root_table and item != root_table]
    path_searches_by_target = {
        target_table: _find_relationship_path_search(
            relationships,
            root_table,
            target_table,
            limit=path_search_limit,
        )
        for target_table in target_tables
    }
    paths_by_target = {
        target_table: search["paths"]
        for target_table, search in path_searches_by_target.items()
    }
    required_set = set(required_tables)
    if len(measure_tables) == 1:
        terminal_tables = [measure_tables[0]] if measure_tables[0] != root_table else []
    else:
        terminal_tables = target_tables
    path_search_truncated_targets = [
        target_table
        for target_table in terminal_tables
        if path_searches_by_target.get(target_table, {}).get("truncated")
    ]
    path_search_truncated = bool(path_search_truncated_targets)
    path_search_incomplete = path_search_truncated and not explicit_relationship_keys
    covering_paths = _deduplicate_paths([
        path
        for target_table in terminal_tables
        for path in paths_by_target.get(target_table, [])
        if required_set.issubset(set(path.get("tables") or []))
    ])

    explicit_candidates: list[dict[str, Any]] = []
    if explicit_relationship_keys and root_table:
        explicit_candidates = [
            path
            for path in _find_explicit_relationship_paths(
                relationships,
                root_table,
                explicit_relationship_keys,
            )
            if required_set.issubset(set(path.get("tables") or []))
            and str((path.get("tables") or [""])[-1]) in terminal_tables
        ]
        for path in explicit_candidates:
            terminal_table = str((path.get("tables") or [""])[-1])
            paths_by_target[terminal_table] = _deduplicate_paths([
                *paths_by_target.get(terminal_table, []),
                path,
            ])
        explicit_candidates = _deduplicate_paths(explicit_candidates)

    selected_global_path: dict[str, Any] | None = None
    global_path_candidates: list[dict[str, Any]] = []
    global_path_ambiguous = False
    explicit_path_fully_matched = not explicit_relationship_keys
    if explicit_relationship_keys:
        explicit_path_fully_matched = bool(explicit_candidates)
        if explicit_candidates:
            global_path_candidates = explicit_candidates
            global_path_ambiguous = len(explicit_candidates) > 1
            if not global_path_ambiguous:
                selected_global_path = explicit_candidates[0]
    elif covering_paths:
        best_rank = _path_rank(covering_paths[0])
        global_path_candidates = [path for path in covering_paths if _path_rank(path) == best_rank]
        global_path_ambiguous = len(global_path_candidates) > 1
        if not global_path_ambiguous:
            selected_global_path = global_path_candidates[0]

    targets: list[dict[str, Any]] = []
    for target_table in required_tables:
        if not root_table or target_table == root_table:
            continue
        paths = paths_by_target.get(target_table, [])
        selected_path = (
            _path_prefix(selected_global_path, target_table)
            if selected_global_path and not path_search_incomplete
            else None
        )
        candidate_prefixes = _deduplicate_paths([
            prefix
            for path in global_path_candidates
            for prefix in [_path_prefix(path, target_table)]
            if prefix is not None
        ])
        requires_path_clarification = path_search_incomplete or (
            global_path_ambiguous and len(candidate_prefixes) > 1
        )
        if not selected_path and global_path_ambiguous and len(candidate_prefixes) == 1:
            selected_path = candidate_prefixes[0]
        targets.append(
            {
                "targetTable": target_table,
                "paths": paths,
                "selectedPath": None if requires_path_clarification else selected_path,
                "selectedPathReason": (
                    "explicit-relationship-path"
                    if explicit_relationship_keys and selected_path
                    else "best-safe-linear-cover"
                ),
                "requiresPathClarification": requires_path_clarification,
                "pathCandidates": (
                    candidate_prefixes
                    if requires_path_clarification and not path_search_incomplete
                    else []
                ),
                "pathSearchTruncated": bool(
                    path_searches_by_target.get(target_table, {}).get("truncated")
                ),
            }
        )

    path_missing = any(not item["paths"] for item in targets) or bool(targets and not covering_paths and not explicit_candidates)
    path_ambiguous = (
        path_search_incomplete
        or global_path_ambiguous
        or any(item.get("requiresPathClarification") for item in targets)
    )
    path_unsafe = bool(selected_global_path and not selected_global_path.get("safeForPlanning"))
    if field_resolution["status"] == "missing":
        status = "not-applicable"
    elif field_resolution["status"] != "resolved":
        status = "needs-clarification"
    elif requires_root_clarification or path_ambiguous or not explicit_path_fully_matched:
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
            "rootCandidates": root_candidates,
            "requiresRootClarification": requires_root_clarification,
            "selectedRootReason": "explicit-root-table" if explicit_root_table and not explicit_root_invalid else "resolved-from-question",
            "explicitRootInvalid": explicit_root_invalid,
            "explicitPathValid": explicit_path_fully_matched,
            "pathSearchLimit": path_search_limit,
            "pathSearchTruncated": path_search_truncated,
            "pathSearchIncomplete": path_search_incomplete,
            "pathSearchTruncatedTargets": path_search_truncated_targets,
            "rootSearchTruncated": root_search_truncated,
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
    metric_definitions_by_field: dict[tuple[str, str], list[dict[str, str]]] = {}
    for metric in metrics:
        table_key = str(metric["table_key"])
        if metric["measure"]:
            metric_definitions_by_field.setdefault((table_key, str(metric["measure"])), []).append({
                "label": str(metric["label"]),
                "aggregation": str(metric["aggregation"]),
            })

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
            field_metrics = metric_definitions_by_field.get((table_key, field_name), [])
            metric_aliases = list(dict.fromkeys(item["label"] for item in field_metrics))
            metric_aggregations = list(dict.fromkeys(item["aggregation"] for item in field_metrics))
            field_catalog.append(
                {
                    "id": f"{table_key}:{field_name}",
                    "tableKey": table_key,
                    "tableName": str(registry["display_name"]),
                    "field": field_name,
                    "role": str(semantic.get("role") or "unknown"),
                    "confidence": float(semantic.get("confidence") or 0),
                    "source": "workspace-semantic" if semantic else "schema",
                    "aliases": metric_aliases,
                    "metricAliases": metric_aliases,
                    "metricDefinitions": field_metrics,
                    "aggregation": metric_aggregations[0] if len(metric_aggregations) == 1 else "",
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
            "validationMetrics": validation_metrics,
            "filters": filters if isinstance(filters, list) else [],
            "preaggregation": preaggregation if isinstance(preaggregation, dict) else {},
            "validationStatus": str(validation.get("status") or "") if isinstance(validation, dict) else "",
            "dataVersions": validation.get("dataVersions") if isinstance(validation, dict) and isinstance(validation.get("dataVersions"), dict) else {},
            "currentDataVersions": relation_versions,
            "updatedAt": str(row["updated_at"] or ""),
        })
        relationship_material = {
            key: relationships[-1].get(key)
            for key in (
                "relationKey",
                "leftTableKey",
                "rightTableKey",
                "fieldMappings",
                "joinType",
                "filters",
                "preaggregation",
                "validationStatus",
                "dataVersions",
                "currentDataVersions",
                "updatedAt",
            )
        }
        relationships[-1]["relationshipFingerprint"] = hashlib.sha256(
            json.dumps(
                relationship_material,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
    return build_semantic_query_plan(
        prompt,
        field_catalog,
        relationships,
        selected_table_key=selected_table_key,
    )
