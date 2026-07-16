from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from typing import Any

from connector_adapter_service import discover_connector
from relationship_command_service import relationship_record_payload


SCHEMA = "aibi-federation-proof/v1"
ALLOWED_FILTER_OPERATORS = {
    "eq", "ne", "gt", "gte", "lt", "lte", "in", "not-in",
    "is-null", "not-null", "contains", "starts-with", "ends-with",
}
SAFE_REF = re.compile(r"^[^\s;`'\"\\]{1,256}$")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _json_arg(value: Any, expected: type, label: str) -> Any:
    if isinstance(value, expected):
        return value
    try:
        parsed = json.loads(str(value or ""))
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} must be valid JSON.") from error
    if not isinstance(parsed, expected):
        raise ValueError(f"{label} must be a JSON {expected.__name__}.")
    return parsed


def _csv(value: Any) -> list[str]:
    return [str(item).strip() for item in str(value or "").split(",") if str(item).strip()]


def _gate(status: bool, evidence: list[str], blockers: list[str]) -> dict[str, Any]:
    return {"status": "passed" if status else "blocked", "evidence": evidence, "blockers": blockers}


def _connector_rows(connection: sqlite3.Connection, workspace_id: str, keys: list[str]) -> dict[str, sqlite3.Row]:
    rows: dict[str, sqlite3.Row] = {}
    for key in keys:
        row = connection.execute(
            "SELECT * FROM data_connectors WHERE workspace_id = ? AND connector_key = ?",
            (workspace_id, key),
        ).fetchone()
        if row is not None:
            rows[key] = row
    return rows


def _semantic_rows(connection: sqlite3.Connection, workspace_id: str, table_key: str) -> dict[str, dict[str, Any]]:
    return {
        str(row["field_name"]): dict(row)
        for row in connection.execute(
            "SELECT * FROM field_semantics WHERE workspace_id = ? AND table_key = ?",
            (workspace_id, table_key),
        ).fetchall()
    }


def _connected(selected_tables: set[str], relationships: list[dict[str, Any]]) -> bool:
    if not selected_tables:
        return False
    graph = {table: set() for table in selected_tables}
    for relationship in relationships:
        left = str(relationship.get("leftTableKey") or relationship.get("left_table_key") or "")
        right = str(relationship.get("rightTableKey") or relationship.get("right_table_key") or "")
        if left in graph and right in graph:
            graph[left].add(right)
            graph[right].add(left)
    pending = [next(iter(selected_tables))]
    visited: set[str] = set()
    while pending:
        table = pending.pop()
        if table in visited:
            continue
        visited.add(table)
        pending.extend(graph[table] - visited)
    return visited == selected_tables


def federation_proof_command(args: Any, *, open_db: Any, active_workspace_id: Any) -> dict[str, Any]:
    connector_keys = _csv(args.connectors)
    relationship_keys = _csv(args.relationships)
    projections_raw = _json_arg(args.projections, dict, "--projections")
    filters_raw = _json_arg(args.filters, list, "--filters")
    projections = {
        str(key): list(dict.fromkeys(str(field).strip() for field in fields if str(field).strip()))
        for key, fields in projections_raw.items()
        if isinstance(fields, list)
    }
    filters = [item for item in filters_raw if isinstance(item, dict)]
    grain = str(args.grain or "").strip()
    entity_key = str(args.entity_key or "").strip()
    budget = {
        "maxSources": max(1, min(int(args.max_sources), 4)),
        "maxProjectedFields": max(1, min(int(args.max_fields), 128)),
        "maxRelationships": max(0, min(int(args.max_relationships), 16)),
        "maxFilters": max(0, min(int(args.max_filters), 32)),
    }

    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        rows = _connector_rows(connection, workspace_id, connector_keys)
        source_blockers: list[str] = []
        projection_blockers: list[str] = []
        semantic_blockers: list[str] = []
        freshness_blockers: list[str] = []
        sources: list[dict[str, Any]] = []
        target_by_connector: dict[str, str] = {}
        semantic_by_table: dict[str, dict[str, dict[str, Any]]] = {}

        if not 2 <= len(connector_keys) <= 4:
            source_blockers.append("source-count-must-be-between-2-and-4")
        if len(connector_keys) != len(set(connector_keys)):
            source_blockers.append("connector-keys-must-be-unique")
        for projection_key, projection_value in projections_raw.items():
            if str(projection_key) not in connector_keys:
                projection_blockers.append(f"projection-connector-not-selected:{projection_key}")
            if not isinstance(projection_value, list):
                projection_blockers.append(f"projection-must-be-field-list:{projection_key}")

        for connector_key in connector_keys:
            row = rows.get(connector_key)
            if row is None:
                source_blockers.append(f"unknown-connector:{connector_key}")
                projection_blockers.append(f"projection-cannot-be-verified:{connector_key}")
                semantic_blockers.append(f"semantics-cannot-be-verified:{connector_key}")
                freshness_blockers.append(f"source-fingerprint-unavailable:{connector_key}")
                continue
            config = json.loads(row["config_json"] or "{}")
            target_table = str(config.get("targetTableKey") or "").strip()
            target_by_connector[connector_key] = target_table
            registry = connection.execute(
                "SELECT * FROM table_registry WHERE workspace_id = ? AND table_key = ?",
                (workspace_id, target_table),
            ).fetchone() if target_table else None
            semantic_by_table[target_table] = _semantic_rows(connection, workspace_id, target_table) if registry else {}
            prerequisites_ok = True
            if row["status"] != "active":
                source_blockers.append(f"connector-not-active:{connector_key}")
                prerequisites_ok = False
            if not target_table or registry is None:
                source_blockers.append(f"target-table-not-synced:{connector_key}")
                prerequisites_ok = False
            if row["last_sync_status"] != "success":
                source_blockers.append(f"last-sync-not-successful:{connector_key}")
                prerequisites_ok = False
            discovery: dict[str, Any]
            if prerequisites_ok:
                try:
                    discovery = discover_connector(row)
                except Exception as error:  # Adapter failures are proof blockers, not partial authority.
                    discovery = {
                        "ok": False,
                        "reason": str(error),
                        "sideEffects": {"network": row["connector_type"] == "api"},
                    }
            else:
                discovery = {"ok": False, "reason": "connector-prerequisites-not-current", "sideEffects": {"network": False}}
            adapter = discovery.get("adapter") if isinstance(discovery.get("adapter"), dict) else {}
            metadata = discovery.get("metadata") if isinstance(discovery.get("metadata"), dict) else {}
            resource = metadata.get("resource") if isinstance(metadata.get("resource"), dict) else {}
            columns = [str(item) for item in metadata.get("columns") or []]
            requested_fields = projections.get(connector_key, [])
            missing_fields = [field for field in requested_fields if field not in columns]
            missing_semantics = [field for field in requested_fields if field not in semantic_by_table.get(target_table, {})]
            if prerequisites_ok and (discovery.get("ok") is not True or adapter.get("available") is not True):
                source_blockers.append(f"adapter-unavailable:{connector_key}")
            if not requested_fields:
                projection_blockers.append(f"projection-required:{connector_key}")
            projection_blockers.extend(f"unknown-projected-field:{connector_key}:{field}" for field in missing_fields)
            semantic_blockers.extend(f"missing-field-semantic:{target_table}:{field}" for field in missing_semantics)

            last_result = json.loads(row["last_sync_result_json"] or "{}")
            last_adapter = last_result.get("adapter") if isinstance(last_result.get("adapter"), dict) else {}
            current_resource_fingerprint = str(resource.get("sha256") or "")
            synced_resource_fingerprint = str(last_adapter.get("resourceFingerprint") or "")
            comparable = row["connector_type"] in {"file", "database"}
            source_current = bool(prerequisites_ok and comparable and current_resource_fingerprint and current_resource_fingerprint == synced_resource_fingerprint)
            if not prerequisites_ok:
                freshness_blockers.append(f"source-fingerprint-unavailable:{connector_key}")
            elif not source_current:
                freshness_blockers.append(
                    f"source-fingerprint-{'changed' if comparable else 'not-comparable'}:{connector_key}"
                )

            sources.append({
                "connectorKey": connector_key,
                "targetTableKey": target_table,
                "adapterId": str(adapter.get("adapterId") or ""),
                "available": discovery.get("ok") is True and adapter.get("available") is True,
                "status": str(row["status"]),
                "syncStatus": str(row["last_sync_status"] or "never"),
                "dataVersion": int(registry["data_version"]) if registry else None,
                "columns": columns,
                "projections": requested_fields,
                "semanticFields": sorted(field for field in requested_fields if field in semantic_by_table.get(target_table, {})),
                "metadataFingerprint": str(discovery.get("receiptFingerprint") or ""),
                "resourceFingerprint": current_resource_fingerprint,
                "sourceCurrent": source_current,
                "networkRead": bool((discovery.get("sideEffects") or {}).get("network")) if isinstance(discovery.get("sideEffects"), dict) else False,
                "credentialValuesExposed": False,
                "businessRowsExposed": False,
            })

        relationships: list[dict[str, Any]] = []
        relationship_blockers: list[str] = []
        type_blockers: list[str] = []
        selected_tables = {table for table in target_by_connector.values() if table}
        if len(relationship_keys) != len(set(relationship_keys)):
            relationship_blockers.append("relationship-keys-must-be-unique")
        for relation_key in relationship_keys:
            row = connection.execute(
                "SELECT * FROM relationships WHERE workspace_id = ? AND relation_key = ?",
                (workspace_id, relation_key),
            ).fetchone()
            if row is None:
                relationship_blockers.append(f"unknown-relationship:{relation_key}")
                type_blockers.append(f"relationship-type-compatibility-unverified:{relation_key}")
                freshness_blockers.append(f"relationship-version-unavailable:{relation_key}")
                continue
            payload = relationship_record_payload(row)
            left = str(payload.get("left_table_key") or "")
            right = str(payload.get("right_table_key") or "")
            validation = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
            versions = validation.get("dataVersions") if isinstance(validation.get("dataVersions"), dict) else {}
            current_versions = {
                table: int(connection.execute(
                    "SELECT data_version FROM table_registry WHERE workspace_id = ? AND table_key = ?",
                    (workspace_id, table),
                ).fetchone()[0])
                for table in (left, right)
                if connection.execute(
                    "SELECT 1 FROM table_registry WHERE workspace_id = ? AND table_key = ?",
                    (workspace_id, table),
                ).fetchone()
            }
            current = bool(
                validation.get("status") == "validated"
                and not (validation.get("blockers") or [])
                and all(int(versions.get(table, -1)) == version for table, version in current_versions.items())
                and len(current_versions) == 2
            )
            endpoints_selected = left in selected_tables and right in selected_tables
            if not endpoints_selected:
                relationship_blockers.append(f"relationship-outside-selected-sources:{relation_key}")
            if not current:
                relationship_blockers.append(f"relationship-not-current:{relation_key}")
                freshness_blockers.append(f"relationship-version-stale:{relation_key}")
            mappings = payload.get("fieldMappings") if isinstance(payload.get("fieldMappings"), list) else []
            if not mappings:
                type_blockers.append(f"relationship-has-no-field-mapping:{relation_key}")
            if validation.get("status") != "validated":
                type_blockers.append(f"relationship-type-compatibility-unverified:{relation_key}")
            relationships.append({
                "relationKey": relation_key,
                "leftTableKey": left,
                "rightTableKey": right,
                "joinType": str(payload.get("join_type") or ""),
                "fieldMappings": mappings,
                "validationStatus": str(validation.get("status") or "missing"),
                "current": current,
                "dataVersions": current_versions,
            })

        if len(selected_tables) != len(connector_keys):
            relationship_blockers.append("each-source-requires-a-distinct-target-table")
        if len(connector_keys) >= 2 and not relationship_keys:
            relationship_blockers.append("relationship-path-required")
        if relationships and not _connected(selected_tables, relationships):
            relationship_blockers.append("relationship-path-not-connected")

        entity_blockers: list[str] = []
        if "." not in entity_key or not SAFE_REF.fullmatch(entity_key):
            entity_blockers.append("entity-key-must-be-table.field")
            entity_table, entity_field = "", ""
        else:
            entity_table, entity_field = entity_key.rsplit(".", 1)
            semantic = semantic_by_table.get(entity_table, {}).get(entity_field, {})
            if entity_table not in selected_tables:
                entity_blockers.append("entity-key-table-not-selected")
            if str(semantic.get("role") or "") not in {"identity_key", "identifier"}:
                entity_blockers.append("entity-key-semantic-is-not-identifier")

        grain_blockers: list[str] = []
        if not grain or not SAFE_REF.fullmatch(grain):
            grain_blockers.append("safe-explicit-grain-required")
        elif grain not in selected_tables and grain != entity_key:
            grain_blockers.append("grain-must-reference-selected-table-or-entity-key")
        elif entity_table and grain not in {entity_table, entity_key}:
            grain_blockers.append("entity-key-does-not-match-grain")
        filter_blockers: list[str] = []
        normalized_filters: list[dict[str, str]] = []
        if len(filters) != len(filters_raw):
            filter_blockers.append("filters-must-be-objects")
        for item in filters:
            connector_key = str(item.get("connectorKey") or "").strip()
            field = str(item.get("field") or "").strip()
            operator = str(item.get("operator") or "").strip().lower()
            source = next((entry for entry in sources if entry["connectorKey"] == connector_key), None)
            if source is None:
                filter_blockers.append(f"filter-connector-not-selected:{connector_key}")
            elif field not in source["columns"]:
                filter_blockers.append(f"filter-field-not-found:{connector_key}:{field}")
            if operator not in ALLOWED_FILTER_OPERATORS:
                filter_blockers.append(f"filter-operator-not-allowlisted:{operator or 'missing'}")
            normalized_filters.append({"connectorKey": connector_key, "field": field, "operator": operator})

        budget_blockers: list[str] = []
        projected_count = sum(len(fields) for fields in projections.values())
        if len(connector_keys) > budget["maxSources"]:
            budget_blockers.append("source-budget-exceeded")
        if projected_count > budget["maxProjectedFields"]:
            budget_blockers.append("projection-budget-exceeded")
        if len(relationship_keys) > budget["maxRelationships"]:
            budget_blockers.append("relationship-budget-exceeded")
        if len(filters) > budget["maxFilters"]:
            budget_blockers.append("filter-budget-exceeded")

        gates = {
            "sourceAvailability": _gate(not source_blockers, ["adapter-metadata-discovery", "active-connector", "synced-target-table"], source_blockers),
            "fieldProjection": _gate(not projection_blockers, ["adapter-column-catalog"], projection_blockers),
            "semanticCoverage": _gate(not semantic_blockers, ["workspace-field-semantics"], semantic_blockers),
            "typeCompatibility": _gate(not type_blockers, ["validated-relationship-preview"], type_blockers),
            "entityKeys": _gate(not entity_blockers, ["identifier-semantic"], entity_blockers),
            "relationshipPath": _gate(not relationship_blockers, ["workspace-validated-relationships", "connected-source-graph"], relationship_blockers),
            "grain": _gate(not grain_blockers, ["explicit-safe-grain"], grain_blockers),
            "filterPushdown": _gate(not filter_blockers, ["declarative-filter-allowlist"], filter_blockers),
            "budget": _gate(not budget_blockers, ["bounded-federation-budget"], budget_blockers),
            "freshness": _gate(not freshness_blockers, ["source-resource-fingerprint", "relationship-data-versions"], freshness_blockers),
        }
        blockers = list(dict.fromkeys(blocker for gate in gates.values() for blocker in gate["blockers"]))
        status = "provable" if not blockers else "blocked"
        plan = {
            "sourceOrder": connector_keys,
            "projections": projections,
            "relationshipKeys": relationship_keys,
            "grain": grain,
            "entityKey": entity_key,
            "filters": normalized_filters,
            "budget": budget,
        }
        proof_material = {
            "workspaceId": workspace_id,
            "status": status,
            "sources": sources,
            "relationships": relationships,
            "gates": gates,
            "plan": plan,
        }
        return {
            "ok": True,
            "schema": SCHEMA,
            "workspaceId": workspace_id,
            "status": status,
            "provable": status == "provable",
            "blocked": status == "blocked",
            "blockers": blockers,
            "sources": sources,
            "relationships": relationships,
            "gates": gates,
            "plan": plan,
            "proofFingerprint": _fingerprint(proof_material),
            "permissions": {"execution": False, "materialization": False, "write": False},
            "sideEffects": {
                "networkRead": any(bool(source.get("networkRead")) for source in sources),
                "crossSourceQuery": False,
                "businessRowsExposed": False,
                "businessDatabaseWrite": False,
                "artifactWrite": False,
                "rowCopy": False,
            },
            "evidence": ["connector-adapter-receipts", "field-semantics", "validated-relationship-path", "bounded-proof-plan"],
        }
