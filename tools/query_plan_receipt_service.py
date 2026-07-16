from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from typing import Any, Callable

from context_pack_service import workspace_data_fingerprint, workspace_schema_fingerprint
from domain_pack_service import domain_pack_runtime_context, domain_pack_set_fingerprint


def _receipt_key(workspace_id: str, request_text: str, created_at: str) -> str:
    material = f"{workspace_id}\x1f{request_text}\x1f{created_at}"
    return f"query_receipt_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:20]}"


def _canonical_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonical_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_canonical_value(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _result_fingerprint(rows: list[Any]) -> str:
    material = json.dumps(_canonical_value(_result_projection(rows)), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _result_projection(rows: list[Any]) -> list[dict[str, Any]]:
    return [
        {str(key): _canonical_value(value) for key, value in row.items() if not isinstance(value, (dict, list, tuple, set))}
        for row in rows
        if isinstance(row, dict)
    ]


def _fingerprint(value: Any) -> str:
    material = json.dumps(_canonical_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _normalize_relationship_path_proof(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict) and isinstance(value.get("hopProofs"), list):
        raw_items = value["hopProofs"]
    elif isinstance(value, dict) and isinstance(value.get("hops"), list):
        raw_items = value["hops"]
    elif isinstance(value, dict) and isinstance(value.get("relationshipPathProof"), (dict, list)):
        return _normalize_relationship_path_proof(value["relationshipPathProof"])
    elif isinstance(value, dict):
        raw_items = [value]
    elif isinstance(value, list):
        raw_items = value
    else:
        raw_items = []

    normalized: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        canonical = _canonical_value(item)
        if not isinstance(canonical, dict):
            continue
        canonical.pop("proofFingerprint", None)
        canonical.pop("hopIndex", None)
        normalized.append(canonical)

    result: list[dict[str, Any]] = []
    for index, item in enumerate(normalized):
        proof = {
            "schema": str(item.get("schema") or "aibi-relationship-hop-proof/v1"),
            "hopIndex": index,
            **{key: value for key, value in item.items() if key != "schema"},
        }
        proof["proofFingerprint"] = _fingerprint(proof)
        result.append(proof)
    return result


def _proof_blockers(value: Any) -> list[str]:
    items = value if isinstance(value, (list, tuple)) else ([] if value is None else [value])
    result: list[str] = []
    for item in items:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(
                item.get("reason")
                or item.get("code")
                or item.get("message")
                or item.get("kind")
                or ""
            ).strip()
            if not text:
                text = json.dumps(_canonical_value(item), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        elif item is None:
            text = ""
        else:
            text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result


def _relationship_identity(value: Any) -> dict[str, str]:
    item = value if isinstance(value, dict) else {}
    return {
        "relationKey": str(item.get("relationKey") or item.get("relation_key") or "").strip(),
        "fromTable": str(
            item.get("fromTable")
            or item.get("leftTable")
            or item.get("leftTableKey")
            or item.get("relationshipLeftTable")
            or ""
        ).strip(),
        "toTable": str(
            item.get("toTable")
            or item.get("rightTable")
            or item.get("rightTableKey")
            or item.get("relationshipRightTable")
            or ""
        ).strip(),
    }


def validate_relationship_path_proof(
    value: Any,
    *,
    cross_table: bool,
    expected_relationships: list[Any] | None = None,
) -> dict[str, Any]:
    """Validate the execution proof contract shared by receipts and Agent evidence."""
    proofs = _normalize_relationship_path_proof(value)
    expected = [item for item in expected_relationships or [] if isinstance(item, dict)]
    if not cross_table:
        return {
            "required": False,
            "proven": True,
            "hopCount": len(proofs),
            "expectedHopCount": len(expected),
            "blockers": [],
        }

    blockers: list[str] = []
    if not proofs:
        blockers.append("missing-relationship-path-proof")
    if expected and len(proofs) != len(expected):
        blockers.append(f"relationship-path-proof-hop-count-mismatch:{len(proofs)}:{len(expected)}")

    for index, proof in enumerate(proofs):
        hop = index + 1
        status = str(proof.get("proofStatus") or "missing").strip().casefold()
        if status != "verified":
            blockers.append(f"hop-{hop}:relationship-proof-not-verified:{status or 'missing'}")
        for blocker in _proof_blockers(proof.get("blockers")):
            blockers.append(f"hop-{hop}:relationship-proof-blocked:{blocker}")
        data_versions = proof.get("dataVersions") if isinstance(proof.get("dataVersions"), dict) else {}
        if data_versions.get("matches") is not True:
            blockers.append(f"hop-{hop}:relationship-data-version-not-current")
        if index < len(expected):
            actual_identity = _relationship_identity(proof)
            expected_identity = _relationship_identity(expected[index])
            if any(
                expected_identity[key] and actual_identity[key] != expected_identity[key]
                for key in expected_identity
            ):
                blockers.append(f"hop-{hop}:relationship-proof-identity-mismatch")

    blockers = list(dict.fromkeys(blockers))
    return {
        "required": True,
        "proven": not blockers,
        "hopCount": len(proofs),
        "expectedHopCount": len(expected),
        "blockers": blockers,
    }


def _derived_relationship_path_proof(
    semantic_plan: dict[str, Any] | None,
    execution_plan: dict[str, Any] | None,
    joins: list[Any],
) -> list[dict[str, Any]]:
    execution = execution_plan if isinstance(execution_plan, dict) else {}
    execution_proof = execution.get("relationshipPathProof")
    normalized_execution_proof = _normalize_relationship_path_proof(execution_proof)
    if normalized_execution_proof:
        return normalized_execution_proof

    semantic = semantic_plan if isinstance(semantic_plan, dict) else {}
    targets = semantic.get("joinPlan", {}).get("targets") if isinstance(semantic.get("joinPlan"), dict) else []
    semantic_hops: list[Any] = []
    for target in targets if isinstance(targets, list) else []:
        selected_path = target.get("selectedPath") if isinstance(target, dict) else None
        if isinstance(selected_path, dict) and isinstance(selected_path.get("hops"), list):
            semantic_hops.extend(selected_path["hops"])
    if semantic_hops:
        return _normalize_relationship_path_proof(semantic_hops)

    relationships = execution.get("relationships") if isinstance(execution.get("relationships"), list) else []
    if not relationships and isinstance(execution.get("relationship"), dict):
        relationships = [execution["relationship"]]
    return _normalize_relationship_path_proof(relationships or joins)


def _append_table_key(target: list[str], value: Any) -> None:
    table_key = str(value or "").strip()
    if table_key and table_key not in target:
        target.append(table_key)


def _source_table_keys(
    *,
    source_table_key: str | None,
    source_table_keys: list[str] | None,
    semantic_plan: dict[str, Any] | None,
    execution_plan: dict[str, Any] | None,
    relationship_path_proof: list[dict[str, Any]],
) -> list[str]:
    result: list[str] = []
    if source_table_keys:
        for table_key in source_table_keys:
            _append_table_key(result, table_key)
        return result

    semantic = semantic_plan if isinstance(semantic_plan, dict) else {}
    join_plan = semantic.get("joinPlan") if isinstance(semantic.get("joinPlan"), dict) else {}
    grain = semantic.get("grain") if isinstance(semantic.get("grain"), dict) else {}
    _append_table_key(result, join_plan.get("rootTable"))
    for table_key in grain.get("tables") if isinstance(grain.get("tables"), list) else []:
        _append_table_key(result, table_key)

    execution = execution_plan if isinstance(execution_plan, dict) else {}
    _append_table_key(result, execution.get("rootTable"))
    for proof in relationship_path_proof:
        for key in (
            "fromTable",
            "toTable",
            "leftTable",
            "rightTable",
            "leftTableKey",
            "rightTableKey",
            "left_table_key",
            "right_table_key",
            "relationshipLeftTable",
            "relationshipRightTable",
        ):
            _append_table_key(result, proof.get(key))

    if not result:
        _append_table_key(result, source_table_key)
    return result


def _source_table_entry(connection: sqlite3.Connection, workspace_id: str, table_key: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT data_version FROM table_registry WHERE workspace_id = ? AND table_key = ?",
        (workspace_id, table_key),
    ).fetchone()
    return {
        "tableKey": table_key,
        "registered": row is not None,
        "dataVersion": int(row[0] or 1) if row else None,
        "schemaFingerprint": workspace_schema_fingerprint(connection, workspace_id, table_key),
        "dataFingerprint": workspace_data_fingerprint(connection, workspace_id, table_key),
    }


def _combined_source_fingerprint(
    *,
    schema: str,
    workspace_id: str,
    entries: list[dict[str, Any]],
    field: str,
) -> str:
    if len(entries) == 1:
        return str(entries[0][field])
    return _fingerprint({
        "schema": schema,
        "workspaceId": workspace_id,
        "tables": [
            {"tableKey": entry["tableKey"], field: entry[field]}
            for entry in sorted(entries, key=lambda item: str(item["tableKey"]))
        ],
    })


def query_receipt_binding_fingerprint(receipt: dict[str, Any]) -> str:
    """Fingerprint only the immutable provenance captured by a Query Receipt."""
    source = receipt.get("source") if isinstance(receipt.get("source"), dict) else {}
    table_keys = [str(item) for item in source.get("tableKeys") or [] if str(item).strip()]
    if not table_keys and source.get("tableKey"):
        table_keys = [str(source["tableKey"])]
    return _fingerprint({
        "schema": "aibi-query-receipt-binding/v1",
        "workspaceId": source.get("workspaceId"),
        "tableKeys": sorted(dict.fromkeys(table_keys)),
        "schemaFingerprint": source.get("schemaFingerprint"),
        "dataFingerprint": source.get("dataFingerprint"),
        "relationshipPathFingerprint": source.get("relationshipPathFingerprint"),
        "sourceFingerprint": source.get("sourceFingerprint"),
        "domainPackFingerprint": receipt.get("domainPackFingerprint"),
    })


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(str(value or "[]"))
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _knowledge_rule_authority(knowledge_rule: Any, domain_packs: Any) -> bool:
    """Bind fixed cross-table knowledge SQL to its enabled Domain Pack, not a fake saved join."""
    rule = knowledge_rule if isinstance(knowledge_rule, dict) else {}
    pack_id = str(rule.get("packId") or "").strip()
    rule_id = str(rule.get("ruleId") or "").strip()
    pack_version = str(rule.get("packVersion") or rule.get("version") or "").strip()
    if not pack_id or not rule_id or not pack_version:
        return False
    for pack in domain_packs if isinstance(domain_packs, list) else []:
        if not isinstance(pack, dict) or str(pack.get("packId") or "").strip() != pack_id:
            continue
        enabled_version = str(pack.get("version") or "").strip()
        enabled_fingerprint = str(pack.get("fingerprint") or "").strip()
        if enabled_version and enabled_fingerprint and pack_version == enabled_version:
            return True
    return False


def _current_relationship_entry(
    connection: sqlite3.Connection,
    workspace_id: str,
    proof: dict[str, Any],
) -> dict[str, Any]:
    relation_key = str(proof.get("relationKey") or "").strip()
    if not relation_key:
        return {
            "relationKey": "",
            "registered": False,
            "matchesReceipt": False,
            "blockers": ["relationship-proof-missing-relation-key"],
        }
    row = connection.execute(
        """
        SELECT relation_key, left_table_key, right_table_key, left_field, right_field,
               mappings_json, filters_json, preaggregation_json, join_type,
               validation_json, updated_at
        FROM relationships
        WHERE workspace_id = ? AND relation_key = ?
        """,
        (workspace_id, relation_key),
    ).fetchone()
    if not row:
        return {
            "relationKey": relation_key,
            "registered": False,
            "matchesReceipt": False,
            "blockers": ["relationship-not-registered"],
        }

    left_table = str(row["left_table_key"] or "")
    right_table = str(row["right_table_key"] or "")
    mappings = _json_list(row["mappings_json"])
    if not mappings:
        mappings = [{"leftField": str(row["left_field"] or ""), "rightField": str(row["right_field"] or "")}]
    filters = _json_list(row["filters_json"])
    preaggregation = _json_object(row["preaggregation_json"])
    validation = _json_object(row["validation_json"])
    expected_versions = (
        validation.get("dataVersions")
        if isinstance(validation.get("dataVersions"), dict)
        else {}
    )
    version_rows = connection.execute(
        """
        SELECT table_key, data_version
        FROM table_registry
        WHERE workspace_id = ? AND table_key IN (?, ?)
        """,
        (workspace_id, left_table, right_table),
    ).fetchall()
    registered_versions = {str(item["table_key"]): int(item["data_version"] or 1) for item in version_rows}
    current_versions = {
        left_table: registered_versions.get(left_table, 0),
        right_table: registered_versions.get(right_table, 0),
    }
    relationship_material = {
        "relationKey": relation_key,
        "leftTableKey": left_table,
        "rightTableKey": right_table,
        "fieldMappings": mappings,
        "joinType": str(row["join_type"] or "left"),
        "filters": filters,
        "preaggregation": preaggregation,
        "validationStatus": str(validation.get("status") or ""),
        "dataVersions": expected_versions,
        "currentDataVersions": current_versions,
        "updatedAt": str(row["updated_at"] or ""),
    }
    relationship_fingerprint = _fingerprint(relationship_material)
    proof_versions = proof.get("dataVersions") if isinstance(proof.get("dataVersions"), dict) else {}
    proof_expected = proof_versions.get("expected") if isinstance(proof_versions.get("expected"), dict) else {}
    proof_current = proof_versions.get("current") if isinstance(proof_versions.get("current"), dict) else {}
    direction = str(proof.get("direction") or "forward")
    expected_from = right_table if direction == "reverse" else left_table
    expected_to = left_table if direction == "reverse" else right_table
    blockers: list[str] = []
    if str(proof.get("fromTable") or "") != expected_from or str(proof.get("toTable") or "") != expected_to:
        blockers.append("relationship-endpoints-changed")
    if str(validation.get("status") or "") != "validated":
        blockers.append("relationship-not-currently-validated")
    if proof_expected != expected_versions:
        blockers.append("relationship-validated-version-baseline-changed")
    if proof_current != current_versions or proof_versions.get("matches") is not True:
        blockers.append("relationship-data-version-drifted")
    if any(int(expected_versions.get(key) or 0) != int(current_versions.get(key) or 0) for key in current_versions):
        blockers.append("relationship-validation-is-stale")
    if not proof.get("relationshipFingerprint"):
        blockers.append("relationship-proof-missing-fingerprint")
    elif str(proof.get("relationshipFingerprint")) != relationship_fingerprint:
        blockers.append("relationship-definition-drifted")
    blockers = list(dict.fromkeys(blockers))
    return {
        "relationKey": relation_key,
        "registered": True,
        "leftTableKey": left_table,
        "rightTableKey": right_table,
        "relationshipFingerprint": relationship_fingerprint,
        "dataVersions": {"expected": expected_versions, "current": current_versions},
        "validationStatus": str(validation.get("status") or ""),
        "matchesReceipt": not blockers,
        "blockers": blockers,
    }


def current_query_receipt_source_state(
    connection: sqlite3.Connection,
    workspace_id: str,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    source = receipt.get("source") if isinstance(receipt.get("source"), dict) else {}
    table_keys = [str(item) for item in source.get("tableKeys") or [] if str(item).strip()]
    if not table_keys and source.get("tableKey"):
        table_keys = [str(source["tableKey"])]
    table_keys = list(dict.fromkeys(table_keys))
    entries = [_source_table_entry(connection, workspace_id, table_key) for table_key in table_keys]
    if entries:
        schema_fingerprint = _combined_source_fingerprint(
            schema="aibi-combined-schema-fingerprint/v1",
            workspace_id=workspace_id,
            entries=entries,
            field="schemaFingerprint",
        )
        data_fingerprint = _combined_source_fingerprint(
            schema="aibi-combined-data-fingerprint/v1",
            workspace_id=workspace_id,
            entries=entries,
            field="dataFingerprint",
        )
    else:
        schema_fingerprint = workspace_schema_fingerprint(connection, workspace_id, None)
        data_fingerprint = workspace_data_fingerprint(connection, workspace_id, None)
    selection = receipt.get("selection") if isinstance(receipt.get("selection"), dict) else {}
    relationship_proofs = _normalize_relationship_path_proof(selection.get("relationshipPathProof"))
    knowledge_rule = selection.get("knowledgeRule") if isinstance(selection.get("knowledgeRule"), dict) else None
    knowledge_rule_authority = _knowledge_rule_authority(knowledge_rule, receipt.get("domainPacks"))
    execution_plan = selection.get("executionPlan") if isinstance(selection.get("executionPlan"), dict) else {}
    execution_relationships = (
        execution_plan.get("relationships")
        if isinstance(execution_plan.get("relationships"), list)
        else []
    )
    if not execution_relationships and isinstance(execution_plan.get("relationship"), dict):
        execution_relationships = [execution_plan["relationship"]]
    joins = selection.get("joins") if isinstance(selection.get("joins"), list) else []
    cross_table = len(table_keys) > 1 or bool(execution_relationships) or bool(joins) or bool(relationship_proofs)
    relationship_path_required = cross_table and (not knowledge_rule_authority or bool(relationship_proofs))
    expected_relationships = (execution_relationships or joins) if relationship_path_required else []
    stored_proof_validation = validate_relationship_path_proof(
        relationship_proofs,
        cross_table=relationship_path_required,
        expected_relationships=expected_relationships,
    )
    relationship_entries = [
        _current_relationship_entry(connection, workspace_id, proof)
        for proof in relationship_proofs
    ]
    relationship_blockers = list(stored_proof_validation.get("blockers") or [])
    if knowledge_rule and not knowledge_rule_authority:
        relationship_blockers.append("knowledge-rule-authority-invalid")
    current_relationship_path_fingerprint = _fingerprint(relationship_proofs) if relationship_proofs else None
    if current_relationship_path_fingerprint != source.get("relationshipPathFingerprint"):
        relationship_blockers.append("relationship-path-proof-fingerprint-mismatch")
    relationship_blockers.extend(
        f"hop-{index + 1}:{blocker}"
        for index, entry in enumerate(relationship_entries)
        for blocker in entry.get("blockers") or []
    )
    relationship_blockers = list(dict.fromkeys(relationship_blockers))
    relationship_path_matches = not relationship_blockers
    current_domain_packs = list(
        domain_pack_runtime_context(connection, workspace_id).get("enabledDomainPacks") or []
    )
    current_domain_pack_fingerprint = domain_pack_set_fingerprint(
        {"enabledDomainPacks": current_domain_packs}
    )
    receipt_domain_pack_fingerprint = str(receipt.get("domainPackFingerprint") or "")
    domain_pack_matches = current_domain_pack_fingerprint == receipt_domain_pack_fingerprint
    from workspace_manifest_service import workspace_planning_binding

    current_workspace_manifest = workspace_planning_binding(connection, workspace_id)
    stored_workspace_manifest = receipt.get("workspaceManifest") if isinstance(receipt.get("workspaceManifest"), dict) else None
    workspace_manifest_matches = (
        stored_workspace_manifest is None
        or (
            str(stored_workspace_manifest.get("workspaceId") or "") == workspace_id
            and str(stored_workspace_manifest.get("fingerprint") or "") == current_workspace_manifest["fingerprint"]
        )
    )
    source_fingerprint = _fingerprint({
        "workspaceId": workspace_id,
        "tableKeys": sorted(table_keys),
        "schemaFingerprint": schema_fingerprint,
        "dataFingerprint": data_fingerprint,
        "relationshipPathFingerprint": current_relationship_path_fingerprint,
    })
    stored_source_fingerprint = str(source.get("sourceFingerprint") or "")
    source_fingerprint_matches = not stored_source_fingerprint or source_fingerprint == stored_source_fingerprint
    workspace_matches = str(source.get("workspaceId") or "") == workspace_id
    source_tables_match = (
        workspace_matches
        and bool(table_keys or str(receipt.get("status") or "") != "executed")
        and schema_fingerprint == str(source.get("schemaFingerprint") or "")
        and data_fingerprint == str(source.get("dataFingerprint") or "")
        and source_fingerprint_matches
        and all(entry["registered"] for entry in entries)
    )
    blockers: list[str] = []
    if not source_tables_match:
        blockers.append("query-receipt-source-drifted")
    if not relationship_path_matches:
        blockers.append("query-receipt-relationship-path-drifted")
    if not domain_pack_matches:
        blockers.append("query-receipt-domain-pack-drifted")
    if not workspace_manifest_matches:
        blockers.append("query-receipt-workspace-manifest-drifted")
    return {
        "tableKeys": table_keys,
        "tables": entries,
        "schemaFingerprint": schema_fingerprint,
        "dataFingerprint": data_fingerprint,
        "sourceFingerprint": source_fingerprint,
        "sourceFingerprintMatchesReceipt": source_fingerprint_matches,
        "workspaceMatchesReceipt": workspace_matches,
        "sourceTablesMatch": source_tables_match,
        "relationshipPath": {
            "required": relationship_path_required,
            "authority": "domain-pack-knowledge-rule" if knowledge_rule_authority and not relationship_proofs else "saved-relationship-path" if cross_table else "single-source",
            "knowledgeRuleBound": knowledge_rule_authority,
            "matchesReceipt": relationship_path_matches,
            "fingerprint": current_relationship_path_fingerprint,
            "validation": stored_proof_validation,
            "relationships": relationship_entries,
            "blockers": relationship_blockers,
        },
        "domainPacks": current_domain_packs,
        "domainPackFingerprint": current_domain_pack_fingerprint,
        "domainPackMatchesReceipt": domain_pack_matches,
        "workspaceManifest": current_workspace_manifest,
        "workspaceManifestBound": stored_workspace_manifest is not None,
        "workspaceManifestMatchesReceipt": workspace_manifest_matches,
        "receiptBindingFingerprint": query_receipt_binding_fingerprint(receipt),
        "blockers": blockers,
        "matchesReceipt": source_tables_match and relationship_path_matches and domain_pack_matches and workspace_manifest_matches,
    }


def create_query_plan_receipt(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    request_text: str,
    source_table_key: str | None,
    status: str,
    source_table_keys: list[str] | None = None,
    relationship_path_proof: list[dict[str, Any]] | dict[str, Any] | None = None,
    group: str | None = None,
    groups: list[Any] | None = None,
    measure: str | None = None,
    aggregation: str | None = None,
    filters: list[Any] | None = None,
    joins: list[Any] | None = None,
    semantic_plan: dict[str, Any] | None = None,
    execution_plan: dict[str, Any] | None = None,
    knowledge_rule: dict[str, Any] | None = None,
    runtime: dict[str, Any] | None = None,
    evidence_refs: list[Any] | None = None,
    unresolved: list[Any] | None = None,
    context_refs: list[Any] | None = None,
    domain_packs: list[dict[str, Any]] | None = None,
    action_key: str | None = None,
    result_rows: list[Any] | None = None,
    now_iso: Callable[[], str],
    workspace_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    created_at = now_iso()
    receipt_key = _receipt_key(workspace_id, request_text, created_at)
    runtime = runtime if isinstance(runtime, dict) else {}
    evidence_refs = list(evidence_refs or [])
    context_refs = list(context_refs or [])
    if domain_packs is None:
        domain_packs = list(domain_pack_runtime_context(connection, workspace_id).get("enabledDomainPacks") or [])
    else:
        domain_packs = list(domain_packs)
    domain_pack_fingerprint = domain_pack_set_fingerprint({"enabledDomainPacks": domain_packs})
    if workspace_manifest is None:
        from workspace_manifest_service import workspace_planning_binding

        workspace_manifest = workspace_planning_binding(connection, workspace_id)
    elif str(workspace_manifest.get("workspaceId") or "") != workspace_id:
        raise ValueError("Workspace Manifest binding does not belong to the receipt workspace")
    else:
        workspace_manifest = dict(workspace_manifest)
    unresolved = list(unresolved or [])
    filters = list(filters or [])
    groups = list(groups or [])
    joins = list(joins or [])
    knowledge_rule_authority = _knowledge_rule_authority(knowledge_rule, domain_packs)
    normalized_relationship_path_proof = _normalize_relationship_path_proof(relationship_path_proof)
    if not normalized_relationship_path_proof and not knowledge_rule_authority:
        normalized_relationship_path_proof = _derived_relationship_path_proof(semantic_plan, execution_plan, joins)
    normalized_source_table_keys = _source_table_keys(
        source_table_key=source_table_key,
        source_table_keys=source_table_keys,
        semantic_plan=semantic_plan,
        execution_plan=execution_plan,
        relationship_path_proof=normalized_relationship_path_proof,
    )
    source_entries = [
        _source_table_entry(connection, workspace_id, table_key)
        for table_key in normalized_source_table_keys
    ]
    if source_entries:
        schema_fingerprint = _combined_source_fingerprint(
            schema="aibi-combined-schema-fingerprint/v1",
            workspace_id=workspace_id,
            entries=source_entries,
            field="schemaFingerprint",
        )
        data_fingerprint = _combined_source_fingerprint(
            schema="aibi-combined-data-fingerprint/v1",
            workspace_id=workspace_id,
            entries=source_entries,
            field="dataFingerprint",
        )
    else:
        schema_fingerprint = workspace_schema_fingerprint(connection, workspace_id, None)
        data_fingerprint = workspace_data_fingerprint(connection, workspace_id, None)
    relationship_path_fingerprint = (
        _fingerprint(normalized_relationship_path_proof)
        if normalized_relationship_path_proof
        else None
    )
    source_fingerprint = _fingerprint({
        "workspaceId": workspace_id,
        "tableKeys": sorted(normalized_source_table_keys),
        "schemaFingerprint": schema_fingerprint,
        "dataFingerprint": data_fingerprint,
        "relationshipPathFingerprint": relationship_path_fingerprint,
    })
    execution_relationships = (
        execution_plan.get("relationships")
        if isinstance(execution_plan, dict) and isinstance(execution_plan.get("relationships"), list)
        else []
    )
    cross_table_query = (
        len(normalized_source_table_keys) > 1
        or bool(joins)
        or bool(execution_relationships)
        or (isinstance(execution_plan, dict) and isinstance(execution_plan.get("relationship"), dict))
    )
    single_execution_relationship = (
        execution_plan.get("relationship")
        if isinstance(execution_plan, dict) and isinstance(execution_plan.get("relationship"), dict)
        else None
    )
    relationship_path_required = cross_table_query and (not knowledge_rule_authority or bool(normalized_relationship_path_proof))
    expected_relationships = (
        execution_relationships or ([single_execution_relationship] if single_execution_relationship else joins)
    ) if relationship_path_required else []
    relationship_proof_validation = validate_relationship_path_proof(
        normalized_relationship_path_proof,
        cross_table=relationship_path_required,
        expected_relationships=expected_relationships,
    )
    semantic_root = (
        str(semantic_plan.get("joinPlan", {}).get("rootTable") or "")
        if isinstance(semantic_plan, dict) and isinstance(semantic_plan.get("joinPlan"), dict)
        else ""
    )
    legacy_source_table_key = str(source_table_key or "").strip()
    primary_source_table_key = next(
        (
            item
            for item in (semantic_root, legacy_source_table_key, *normalized_source_table_keys)
            if item and item in normalized_source_table_keys
        ),
        None,
    )
    result_binding = None
    if isinstance(result_rows, list):
        projected_rows = _result_projection(result_rows)
        result_binding = {
            "resultFingerprint": _result_fingerprint(result_rows),
            "rowCount": len(projected_rows),
            "columns": sorted({str(key) for row in projected_rows for key in row}),
            "projection": "scalar-result-fields-only",
            "snapshotStored": False,
        }
    plan = {
        "schema": "aibi-query-plan-receipt/v1",
        "receiptKey": receipt_key,
        "request": request_text,
        "status": status,
        "source": {
            "workspaceId": workspace_id,
            "tableKey": primary_source_table_key,
            "tableKeys": normalized_source_table_keys,
            "tables": source_entries,
            "schemaFingerprint": schema_fingerprint,
            "dataFingerprint": data_fingerprint,
            "relationshipPathFingerprint": relationship_path_fingerprint,
            "sourceFingerprint": source_fingerprint,
        },
        "selection": {
            "group": group,
            "groups": groups,
            "measure": measure,
            "aggregation": aggregation,
            "filters": filters,
            "joins": joins,
            "relationshipPathProof": normalized_relationship_path_proof,
            "semanticPlan": semantic_plan if isinstance(semantic_plan, dict) else None,
            "executionPlan": execution_plan if isinstance(execution_plan, dict) else None,
            "knowledgeRule": knowledge_rule,
        },
        "runtime": {
            "engine": runtime.get("engine"),
            "database": runtime.get("database"),
            "compiledSql": runtime.get("compiledSql"),
            "executionPlanHash": runtime.get("executionPlanHash"),
            "sqlIntent": "whitelist aggregate query; no user SQL accepted",
        },
        "validation": {
            "whitelistOnly": True,
            "sourceReadOnly": True,
            "executed": status == "executed",
            "blocked": status == "blocked",
            "sourceTablesRegistered": all(entry["registered"] for entry in source_entries),
            "relationshipPathProven": relationship_proof_validation["proven"],
            "relationshipPathRequired": relationship_path_required,
            "relationshipAuthority": "domain-pack-knowledge-rule" if knowledge_rule_authority and not normalized_relationship_path_proof else "saved-relationship-path" if cross_table_query else "single-source",
            "knowledgeRuleBound": knowledge_rule_authority,
        },
        "resultBinding": result_binding,
        "contextRefs": context_refs,
        "domainPacks": domain_packs,
        "domainPackFingerprint": domain_pack_fingerprint,
        "workspaceManifest": workspace_manifest,
        "evidenceRefs": evidence_refs,
        "unresolved": unresolved,
        "actionKey": action_key,
        "createdAt": created_at,
    }
    connection.execute(
        """
        INSERT INTO query_plan_receipts(
          receipt_key, workspace_id, request_text, status, source_table_key, schema_fingerprint,
          plan_json, evidence_json, action_key, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            receipt_key,
            workspace_id,
            request_text,
            status,
            primary_source_table_key,
            schema_fingerprint,
            json.dumps(plan, ensure_ascii=False),
            json.dumps(evidence_refs, ensure_ascii=False),
            action_key,
            created_at,
            created_at,
        ),
    )
    return plan


def query_receipt_payload(row: sqlite3.Row) -> dict[str, Any]:
    plan = json.loads(row["plan_json"])
    if not isinstance(plan, dict):
        plan = {}
    return plan


def get_query_receipt(connection: sqlite3.Connection, workspace_id: str, receipt_key: str) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM query_plan_receipts WHERE workspace_id = ? AND receipt_key = ?",
        (workspace_id, receipt_key),
    ).fetchone()
    return query_receipt_payload(row) if row else None


def query_receipts_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        if args.receipt:
            receipt = get_query_receipt(connection, workspace_id, args.receipt)
            if not receipt:
                raise ValueError(f"Unknown query receipt in active workspace: {args.receipt}")
            return {"ok": True, "queryReceipt": receipt}
        rows = connection.execute(
            """
            SELECT * FROM query_plan_receipts
            WHERE workspace_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (workspace_id, max(1, min(int(args.limit), 200))),
        ).fetchall()
        receipts = [query_receipt_payload(row) for row in rows]
    return {"ok": True, "queryReceipts": receipts, "count": len(receipts)}
