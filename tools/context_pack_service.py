from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from typing import Any, Callable


VALID_CONTEXT_STATUSES = {"draft", "confirmed", "deprecated"}
VALID_SCOPE_TYPES = {"workspace", "source", "table", "field", "metric"}
VALID_RULE_TYPES = {"definition", "enum", "unit", "null", "default_filter", "canonical_source", "aggregation", "other"}


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value is None or value == "":
        return []
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return [item.strip() for item in str(value).split(",") if item.strip()]
    return parsed if isinstance(parsed, list) else []


def _normalized_strings(values: list[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        marker = text.casefold()
        if text and marker not in seen:
            seen.add(marker)
            result.append(text)
    return result


def _key(prefix: str, *values: str) -> str:
    material = "\x1f".join(str(value or "").strip().casefold() for value in values)
    return f"{prefix}_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:16]}"


def _dataset_schema(raw: Any) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(str(raw or "[]"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    columns: list[dict[str, Any]] = []
    for item in parsed if isinstance(parsed, list) else []:
        if isinstance(item, str):
            columns.append({"name": item, "type": "VARCHAR", "notnull": 0, "pk": 0})
            continue
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or item.get("field") or "")
        if not name or bool(item.get("internal")) or name.startswith("__aibi_"):
            continue
        columns.append({
            "name": name,
            "type": str(item.get("type") or item.get("physicalType") or "VARCHAR"),
            "notnull": int(bool(item.get("notNull") or item.get("notnull"))),
            "pk": 0,
        })
    return columns


def workspace_schema_fingerprint(
    connection: sqlite3.Connection,
    workspace_id: str,
    table_key: str | None = None,
) -> str:
    params: list[Any] = [workspace_id]
    where = "workspace_id = ?"
    if table_key:
        where += " AND table_key = ?"
        params.append(table_key)
    registries = connection.execute(
        f"SELECT table_key, physical_table, data_version, updated_at, active_version_id, schema_json, schema_fingerprint "
        f"FROM table_registry WHERE {where} ORDER BY table_key",
        tuple(params),
    ).fetchall()
    semantic_params: list[Any] = [workspace_id]
    semantic_where = "workspace_id = ?"
    if table_key:
        semantic_where += " AND table_key = ?"
        semantic_params.append(table_key)
    semantics_by_table: dict[str, list[dict[str, Any]]] = {}
    for row in connection.execute(
        f"""
        SELECT table_key, field_name, role, usage, confidence, tags_json, usage_json, source
        FROM field_semantics
        WHERE {semantic_where}
        ORDER BY table_key, field_name
        """,
        tuple(semantic_params),
    ).fetchall():
        semantics_by_table.setdefault(str(row["table_key"]), []).append({
            key: value for key, value in dict(row).items() if key != "table_key"
        })
    tables: list[dict[str, Any]] = []
    for registry in registries:
        columns = _dataset_schema(registry["schema_json"])
        tables.append({
            "tableKey": registry["table_key"],
            "dataVersion": int(registry["data_version"] or 1),
            "activeVersionId": str(registry["active_version_id"] or ""),
            "schemaFingerprint": str(registry["schema_fingerprint"] or ""),
            "updatedAt": str(registry["updated_at"] or ""),
            "columns": columns,
            "semantics": semantics_by_table.get(str(registry["table_key"]), []),
        })
    relationship_params: list[Any] = [workspace_id]
    relationship_where = "workspace_id = ?"
    if table_key:
        relationship_where += " AND (left_table_key = ? OR right_table_key = ?)"
        relationship_params.extend([table_key, table_key])
    relationships = [
        dict(row)
        for row in connection.execute(
            f"""
            SELECT relation_key, left_table_key, right_table_key, left_field, right_field,
                   mappings_json, filters_json, preaggregation_json, join_type, confidence,
                   validation_json, updated_at
            FROM relationships
            WHERE {relationship_where}
            ORDER BY relation_key
            """,
            tuple(relationship_params),
        ).fetchall()
    ]
    material = json.dumps({"tables": tables, "relationships": relationships}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def workspace_data_fingerprint(
    connection: sqlite3.Connection,
    workspace_id: str,
    table_key: str | None = None,
) -> str:
    params: list[Any] = [workspace_id]
    where = "workspace_id = ?"
    if table_key:
        where += " AND table_key = ?"
        params.append(table_key)
    rows = [
        {
            "tableKey": row["table_key"],
            "dataVersion": int(row["data_version"] or 1),
            "activeVersionId": str(row["active_version_id"] or ""),
            "contentFingerprint": str(row["content_fingerprint"] or ""),
            "rowCount": int(row["row_count"] or 0),
            "columnCount": int(row["column_count"] or 0),
            "updatedAt": str(row["updated_at"] or ""),
        }
        for row in connection.execute(
            f"SELECT table_key, data_version, active_version_id, content_fingerprint, row_count, column_count, updated_at "
            f"FROM table_registry WHERE {where} ORDER BY table_key",
            tuple(params),
        ).fetchall()
    ]
    material = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _scope_overlaps(left_type: str, left_ref: str, right_type: str, right_ref: str) -> bool:
    if left_type == "workspace" or right_type == "workspace":
        return True
    return left_type == right_type and left_ref.casefold() == right_ref.casefold()


def _term_conflicts(
    connection: sqlite3.Connection,
    workspace_id: str,
    term_key: str,
    canonical_name: str,
    aliases: list[str],
    scope_type: str,
    scope_ref: str,
) -> list[dict[str, Any]]:
    proposed = {canonical_name.casefold(), *(alias.casefold() for alias in aliases)}
    conflicts: list[dict[str, Any]] = []
    rows = connection.execute(
        """
        SELECT term_key, canonical_name, aliases_json, definition, scope_type, scope_ref, status
        FROM context_terms
        WHERE workspace_id = ? AND term_key != ? AND status != 'deprecated'
        """,
        (workspace_id, term_key),
    ).fetchall()
    for row in rows:
        existing = {str(row["canonical_name"]).casefold(), *(str(item).casefold() for item in _json_list(row["aliases_json"]))}
        overlap = sorted(proposed & existing)
        if overlap and _scope_overlaps(scope_type, scope_ref, row["scope_type"], row["scope_ref"]):
            conflicts.append({
                "termKey": row["term_key"],
                "canonicalName": row["canonical_name"],
                "definition": row["definition"],
                "overlap": overlap,
            })
    return conflicts


def _term_payload(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["aliases"] = _json_list(item.pop("aliases_json"))
    item["evidenceRefs"] = _json_list(item.pop("evidence_json"))
    return item


def _rule_payload(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["appliesTo"] = _json_list(item.pop("applies_to_json"))
    item["evidenceRefs"] = _json_list(item.pop("evidence_json"))
    return item


def context_pack_snapshot(connection: sqlite3.Connection, workspace_id: str) -> dict[str, Any]:
    terms = [
        _term_payload(row)
        for row in connection.execute(
            "SELECT * FROM context_terms WHERE workspace_id = ? ORDER BY status, canonical_name",
            (workspace_id,),
        ).fetchall()
    ]
    rules = [
        _rule_payload(row)
        for row in connection.execute(
            "SELECT * FROM context_rules WHERE workspace_id = ? ORDER BY status, title",
            (workspace_id,),
        ).fetchall()
    ]
    fingerprint = workspace_schema_fingerprint(connection, workspace_id)
    version_material = json.dumps({"terms": terms, "rules": rules, "schemaFingerprint": fingerprint}, ensure_ascii=False, sort_keys=True)
    version = hashlib.sha256(version_material.encode("utf-8")).hexdigest()[:16]
    return {
        "schema": "aibi-context-pack/v1",
        "workspaceId": workspace_id,
        "version": version,
        "schemaFingerprint": fingerprint,
        "counts": {
            "terms": len(terms),
            "confirmedTerms": sum(item["status"] == "confirmed" for item in terms),
            "rules": len(rules),
            "confirmedRules": sum(item["status"] == "confirmed" for item in rules),
        },
        "terms": terms,
        "rules": rules,
    }


def context_pack_command(
    _args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        pack = context_pack_snapshot(connection, workspace_id)
    return {"ok": True, "contextPack": pack}


def context_term_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    canonical_name = str(args.name or "").strip()
    definition = str(args.definition or "").strip()
    aliases = _normalized_strings(list(args.alias or []))
    scope_type = str(args.scope_type or "workspace").strip()
    scope_ref = str(args.scope_ref or "").strip()
    status = str(args.status or "draft").strip()
    source = str(args.source or "manual").strip()
    evidence_refs = _normalized_strings(list(args.evidence or []))
    if not canonical_name or not definition:
        raise ValueError("Context term name and definition are required")
    if scope_type not in VALID_SCOPE_TYPES:
        raise ValueError(f"Unsupported context scope: {scope_type}")
    if scope_type != "workspace" and not scope_ref:
        raise ValueError("scope-ref is required outside workspace scope")
    if status not in VALID_CONTEXT_STATUSES:
        raise ValueError(f"Unsupported context status: {status}")
    if status == "confirmed" and not evidence_refs:
        raise ValueError("Confirmed context terms require at least one evidence reference")
    term_key = str(args.term or "").strip() or _key("term", canonical_name, scope_type, scope_ref)
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        conflicts = _term_conflicts(connection, workspace_id, term_key, canonical_name, aliases, scope_type, scope_ref)
        proposal = {
            "termKey": term_key,
            "canonicalName": canonical_name,
            "aliases": aliases,
            "definition": definition,
            "scopeType": scope_type,
            "scopeRef": scope_ref,
            "status": status,
            "source": source,
            "evidenceRefs": evidence_refs,
            "conflicts": conflicts,
        }
        if conflicts:
            return {"ok": False, "dryRun": True, "requiresConfirmation": False, "proposal": proposal, "error": "Context term conflicts with an active term in the same scope"}
        if not args.yes:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "proposal": proposal}
        timestamp = now_iso()
        existing = connection.execute(
            "SELECT created_at FROM context_terms WHERE workspace_id = ? AND term_key = ?",
            (workspace_id, term_key),
        ).fetchone()
        created_at = existing["created_at"] if existing else timestamp
        connection.execute(
            """
            INSERT INTO context_terms(
              term_key, workspace_id, canonical_name, aliases_json, definition, scope_type, scope_ref,
              status, source, evidence_json, created_at, updated_at, confirmed_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(workspace_id, term_key) DO UPDATE SET
              canonical_name = excluded.canonical_name,
              aliases_json = excluded.aliases_json,
              definition = excluded.definition,
              scope_type = excluded.scope_type,
              scope_ref = excluded.scope_ref,
              status = excluded.status,
              source = excluded.source,
              evidence_json = excluded.evidence_json,
              updated_at = excluded.updated_at,
              confirmed_at = excluded.confirmed_at
            """,
            (
                term_key, workspace_id, canonical_name, json.dumps(aliases, ensure_ascii=False), definition,
                scope_type, scope_ref, status, source, json.dumps(evidence_refs, ensure_ascii=False),
                created_at, timestamp, timestamp if status == "confirmed" else None,
            ),
        )
        connection.commit()
        saved = connection.execute(
            "SELECT * FROM context_terms WHERE workspace_id = ? AND term_key = ?",
            (workspace_id, term_key),
        ).fetchone()
    return {"ok": True, "confirmed": True, "savedTerm": _term_payload(saved)}


def context_rule_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    title = str(args.title or "").strip()
    statement = str(args.statement or "").strip()
    rule_type = str(args.type or "other").strip()
    applies_to = _normalized_strings(list(args.applies_to or []))
    status = str(args.status or "draft").strip()
    source = str(args.source or "manual").strip()
    evidence_refs = _normalized_strings(list(args.evidence or []))
    if not title or not statement:
        raise ValueError("Context rule title and statement are required")
    if rule_type not in VALID_RULE_TYPES:
        raise ValueError(f"Unsupported context rule type: {rule_type}")
    if status not in VALID_CONTEXT_STATUSES:
        raise ValueError(f"Unsupported context status: {status}")
    if status == "confirmed" and not evidence_refs:
        raise ValueError("Confirmed context rules require at least one evidence reference")
    rule_key = str(args.rule or "").strip() or _key("rule", title, rule_type)
    proposal = {
        "ruleKey": rule_key,
        "title": title,
        "statement": statement,
        "ruleType": rule_type,
        "appliesTo": applies_to,
        "status": status,
        "source": source,
        "evidenceRefs": evidence_refs,
    }
    if not args.yes:
        return {"ok": True, "dryRun": True, "requiresConfirmation": True, "proposal": proposal}
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        timestamp = now_iso()
        existing = connection.execute(
            "SELECT created_at FROM context_rules WHERE workspace_id = ? AND rule_key = ?",
            (workspace_id, rule_key),
        ).fetchone()
        created_at = existing["created_at"] if existing else timestamp
        connection.execute(
            """
            INSERT INTO context_rules(
              rule_key, workspace_id, title, statement, rule_type, applies_to_json, status, source,
              evidence_json, created_at, updated_at, confirmed_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(workspace_id, rule_key) DO UPDATE SET
              title = excluded.title,
              statement = excluded.statement,
              rule_type = excluded.rule_type,
              applies_to_json = excluded.applies_to_json,
              status = excluded.status,
              source = excluded.source,
              evidence_json = excluded.evidence_json,
              updated_at = excluded.updated_at,
              confirmed_at = excluded.confirmed_at
            """,
            (
                rule_key, workspace_id, title, statement, rule_type, json.dumps(applies_to, ensure_ascii=False),
                status, source, json.dumps(evidence_refs, ensure_ascii=False), created_at, timestamp,
                timestamp if status == "confirmed" else None,
            ),
        )
        connection.commit()
        saved = connection.execute(
            "SELECT * FROM context_rules WHERE workspace_id = ? AND rule_key = ?",
            (workspace_id, rule_key),
        ).fetchone()
    return {"ok": True, "confirmed": True, "savedRule": _rule_payload(saved)}


def matched_context(
    connection: sqlite3.Connection,
    workspace_id: str,
    prompt: str,
    table_key: str | None,
) -> dict[str, Any]:
    prompt_folded = prompt.casefold()
    terms: list[dict[str, Any]] = []
    for row in connection.execute(
        "SELECT * FROM context_terms WHERE workspace_id = ? AND status = 'confirmed' ORDER BY canonical_name",
        (workspace_id,),
    ).fetchall():
        if row["scope_type"] == "table" and table_key and row["scope_ref"] != table_key:
            continue
        names = [row["canonical_name"], *_json_list(row["aliases_json"])]
        if any(str(name).casefold() in prompt_folded for name in names if str(name).strip()):
            terms.append(_term_payload(row))
    rules = [
        _rule_payload(row)
        for row in connection.execute(
            "SELECT * FROM context_rules WHERE workspace_id = ? AND status = 'confirmed' ORDER BY title",
            (workspace_id,),
        ).fetchall()
        if not _json_list(row["applies_to_json"]) or not table_key or table_key in _json_list(row["applies_to_json"])
    ]
    return {"terms": terms, "rules": rules}


def contextualized_prompt(prompt: str, context_matches: dict[str, Any]) -> str:
    field_refs: list[str] = []
    for term in context_matches.get("terms", []):
        if term.get("scope_type") != "field":
            continue
        scope_ref = str(term.get("scope_ref") or "").strip()
        field_name = scope_ref.rsplit(".", 1)[-1]
        if field_name and field_name not in field_refs:
            field_refs.append(field_name)
    return " ".join([prompt, *field_refs]).strip()
