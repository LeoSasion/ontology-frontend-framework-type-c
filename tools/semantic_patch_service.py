from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Callable

from bi_cli_core import ROOT, quote_identifier


ADAPTER_SCHEMA = "aibi-knowledge-source-adapter/v1"
SOURCE_SCHEMA = "aibi-knowledge-source/v1"
PROPOSAL_SCHEMA = "aibi-semantic-patch-proposal/v1"
COLLECTION_SCHEMA = "aibi-semantic-patch-collection/v1"
MAX_SOURCE_BYTES = 512 * 1024
MAX_ENTRIES = 200
VALID_SOURCE_TYPES = {"data-dictionary", "documentation", "user-correction"}
VALID_PATCH_TYPES = {"term", "rule", "field-semantic"}
VALID_DECISIONS = {"accept", "reject"}
VALID_ROLES = {"event_time", "measure", "dimension", "identity_key", "status"}
VALID_SCOPE_TYPES = {"workspace", "source", "table", "field", "metric"}
VALID_RULE_TYPES = {"definition", "enum", "unit", "null", "default_filter", "canonical_source", "aggregation", "other"}
VALID_USAGE_KEYS = {"filterable", "sortable", "groupable", "aggregatable", "joinable", "uniqueKeyCandidate", "defaultAnalysisField"}
FORBIDDEN_KEYS = {
    "sql", "query", "code", "script", "command", "executable", "url", "uri",
    "credential", "credentials", "password", "token", "secret", "api_key", "apikey",
}
FORBIDDEN_REPOSITORY_PARTS = {"aibi-a", "aibi-b", "aibi-d", "aibi-e", "aibi项目杂交"}


ADAPTERS: tuple[dict[str, Any], ...] = (
    {
        "schema": ADAPTER_SCHEMA,
        "adapterId": "knowledge-json-v1",
        "label": "AIBI knowledge JSON",
        "extensions": [".json"],
        "inputSchema": SOURCE_SCHEMA,
        "sourceTypes": ["data-dictionary", "documentation"],
        "limits": {"maxBytes": MAX_SOURCE_BYTES, "maxEntries": MAX_ENTRIES},
        "permissions": {"network": False, "sql": False, "code": False, "rawRows": False},
    },
    {
        "schema": ADAPTER_SCHEMA,
        "adapterId": "knowledge-markdown-v1",
        "label": "Markdown with one aibi-knowledge JSON fence",
        "extensions": [".md", ".markdown"],
        "inputSchema": SOURCE_SCHEMA,
        "sourceTypes": ["data-dictionary", "documentation"],
        "limits": {"maxBytes": MAX_SOURCE_BYTES, "maxEntries": MAX_ENTRIES},
        "permissions": {"network": False, "sql": False, "code": False, "rawRows": False},
    },
    {
        "schema": ADAPTER_SCHEMA,
        "adapterId": "user-correction-v1",
        "label": "Structured user correction",
        "extensions": [],
        "inputSchema": SOURCE_SCHEMA,
        "sourceTypes": ["user-correction"],
        "limits": {"maxBytes": 0, "maxEntries": 1},
        "permissions": {"network": False, "sql": False, "code": False, "rawRows": False},
    },
)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _key(prefix: str, *parts: Any) -> str:
    return f"{prefix}_{_fingerprint([str(part) for part in parts])[:20]}"


def _json(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        parsed = json.loads(str(value or ""))
        if default is None:
            return parsed
        return parsed if isinstance(parsed, type(default)) else default
    except (json.JSONDecodeError, TypeError):
        return default


def _text(value: Any, label: str, *, required: bool = True, limit: int = 2000) -> str:
    result = str(value or "").strip()
    if required and not result:
        raise ValueError(f"{label} is required")
    if len(result) > limit:
        raise ValueError(f"{label} exceeds {limit} characters")
    if re.match(r"(?i)^\s*(https?|ftp)://", result):
        raise ValueError(f"{label} cannot contain a remote URL")
    return result


def _strings(value: Any, label: str, *, limit: int = 32, item_limit: int = 200) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{label} must be an array")
    if len(value) > limit:
        raise ValueError(f"{label} exceeds {limit} entries")
    result: list[str] = []
    for item in value:
        text = _text(item, label, required=False, limit=item_limit)
        if text and text not in result:
            result.append(text)
    return result


def _confidence(value: Any, default: float = 1.0) -> float:
    number = default if value is None or value == "" else float(value)
    if number < 0 or number > 1:
        raise ValueError("confidence must be between 0 and 1")
    return round(number, 4)


def _assert_keys(value: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ValueError(f"Unsupported {label} fields: {', '.join(unknown)}")
    forbidden = sorted(key for key in value if key.lower() in FORBIDDEN_KEYS)
    if forbidden:
        raise ValueError(f"Executable or secret-bearing {label} fields are forbidden: {', '.join(forbidden)}")


def _assert_no_forbidden_keys(value: Any, path: str = "document") -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in FORBIDDEN_KEYS:
                raise ValueError(f"Executable, remote, or secret-bearing field is forbidden: {path}.{key}")
            _assert_no_forbidden_keys(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _assert_no_forbidden_keys(item, f"{path}[{index}]")


def knowledge_source_adapters() -> list[dict[str, Any]]:
    return [json.loads(_canonical(adapter)) for adapter in ADAPTERS]


def knowledge_source_adapters_command(_: argparse.Namespace) -> dict[str, Any]:
    adapters = knowledge_source_adapters()
    return {
        "ok": True,
        "schema": "aibi-knowledge-source-adapter-collection/v1",
        "adapters": adapters,
        "count": len(adapters),
        "guardrails": {"network": False, "sql": False, "code": False, "rawRows": False},
    }


def _adapter(adapter_id: str) -> dict[str, Any]:
    for item in ADAPTERS:
        if item["adapterId"] == adapter_id:
            return item
    raise ValueError(f"Unknown knowledge source adapter: {adapter_id}")


def _safe_input_path(raw_path: str) -> Path:
    if re.match(r"(?i)^\s*(https?|ftp)://", raw_path or ""):
        raise ValueError("Remote knowledge sources are not supported")
    path = Path(raw_path)
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    lowered_parts = {part.lower() for part in path.parts}
    blocked = sorted(lowered_parts & FORBIDDEN_REPOSITORY_PARTS)
    if blocked:
        raise ValueError("Knowledge sources from another AIBI repository are forbidden")
    if not path.is_file():
        raise ValueError(f"Knowledge source file does not exist: {path.name}")
    size = path.stat().st_size
    if size > MAX_SOURCE_BYTES:
        raise ValueError(f"Knowledge source exceeds {MAX_SOURCE_BYTES} bytes")
    return path


def _read_document(path: Path, adapter_id: str) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("Knowledge source must be UTF-8 text") from error
    if adapter_id == "knowledge-json-v1":
        try:
            value = json.loads(text)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid knowledge JSON: {error.msg}") from error
    elif adapter_id == "knowledge-markdown-v1":
        matches = re.findall(r"```aibi-knowledge\s*\r?\n([\s\S]*?)\r?\n```", text, flags=re.IGNORECASE)
        if len(matches) != 1:
            raise ValueError("Markdown knowledge source must contain exactly one aibi-knowledge JSON fence")
        try:
            value = json.loads(matches[0])
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid aibi-knowledge JSON fence: {error.msg}") from error
    else:
        raise ValueError(f"Adapter cannot read files: {adapter_id}")
    if not isinstance(value, dict):
        raise ValueError("Knowledge source root must be an object")
    return value, raw


def _normalize_term(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("term entries must be objects")
    _assert_keys(value, {"termKey", "canonicalName", "aliases", "definition", "scopeType", "scopeRef", "confidence"}, "term")
    scope_type = _text(value.get("scopeType") or "workspace", "term.scopeType", limit=30)
    if scope_type not in VALID_SCOPE_TYPES:
        raise ValueError(f"Unsupported term scope: {scope_type}")
    scope_ref = _text(value.get("scopeRef"), "term.scopeRef", required=False, limit=300)
    if scope_type != "workspace" and not scope_ref:
        raise ValueError("term.scopeRef is required outside workspace scope")
    canonical_name = _text(value.get("canonicalName"), "term.canonicalName", limit=200)
    target_key = _text(value.get("termKey"), "term.termKey", required=False, limit=160) or _key("term", canonical_name, scope_type, scope_ref)
    return {
        "termKey": target_key,
        "canonicalName": canonical_name,
        "aliases": _strings(value.get("aliases") or [], "term.aliases"),
        "definition": _text(value.get("definition"), "term.definition", limit=4000),
        "scopeType": scope_type,
        "scopeRef": scope_ref,
        "confidence": _confidence(value.get("confidence"), 1.0),
    }


def _normalize_rule(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("rule entries must be objects")
    _assert_keys(value, {"ruleKey", "title", "statement", "ruleType", "appliesTo", "confidence"}, "rule")
    title = _text(value.get("title"), "rule.title", limit=300)
    rule_type = _text(value.get("ruleType") or "other", "rule.ruleType", limit=40)
    if rule_type not in VALID_RULE_TYPES:
        raise ValueError(f"Unsupported rule type: {rule_type}")
    target_key = _text(value.get("ruleKey"), "rule.ruleKey", required=False, limit=160) or _key("rule", title, rule_type)
    return {
        "ruleKey": target_key,
        "title": title,
        "statement": _text(value.get("statement"), "rule.statement", limit=5000),
        "ruleType": rule_type,
        "appliesTo": _strings(value.get("appliesTo") or [], "rule.appliesTo", item_limit=300),
        "confidence": _confidence(value.get("confidence"), 1.0),
    }


def _normalize_role(value: Any) -> str:
    role = {"time": "event_time", "identifier": "identity_key", "text": "dimension"}.get(str(value or "").strip(), str(value or "").strip())
    if role not in VALID_ROLES:
        raise ValueError(f"Unsupported field semantic role: {role}")
    return role


def _normalize_field_semantic(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("fieldSemantics entries must be objects")
    _assert_keys(value, {"tableKey", "fieldName", "role", "usage", "tags", "confidence", "note"}, "field semantic")
    role = _normalize_role(value.get("role"))
    usages = _strings(value.get("usage") or [], "fieldSemantic.usage", item_limit=80)
    invalid_usage = sorted(set(usages) - VALID_USAGE_KEYS - {f"no-{key}" for key in VALID_USAGE_KEYS})
    if invalid_usage:
        raise ValueError(f"Unsupported field semantic usage: {', '.join(invalid_usage)}")
    return {
        "tableKey": _text(value.get("tableKey"), "fieldSemantic.tableKey", limit=200),
        "fieldName": _text(value.get("fieldName"), "fieldSemantic.fieldName", limit=300),
        "role": role,
        "usage": usages,
        "tags": _strings(value.get("tags") or [], "fieldSemantic.tags", item_limit=120),
        "confidence": _confidence(value.get("confidence"), 1.0),
        "note": _text(value.get("note"), "fieldSemantic.note", required=False, limit=2000),
    }


def normalize_knowledge_document(value: dict[str, Any], *, source_type_override: str = "", source_name_override: str = "") -> dict[str, Any]:
    _assert_no_forbidden_keys(value)
    _assert_keys(value, {"schema", "source", "terms", "rules", "fieldSemantics"}, "knowledge source")
    if str(value.get("schema") or "") != SOURCE_SCHEMA:
        raise ValueError(f"Knowledge source schema must be {SOURCE_SCHEMA}")
    source = value.get("source")
    if not isinstance(source, dict):
        raise ValueError("knowledge source.source must be an object")
    _assert_keys(source, {"name", "version", "type"}, "knowledge source metadata")
    source_type = _text(source_type_override or source.get("type"), "source.type", limit=40)
    if source_type not in VALID_SOURCE_TYPES:
        raise ValueError(f"Unsupported knowledge source type: {source_type}")
    terms = value.get("terms") or []
    rules = value.get("rules") or []
    field_semantics = value.get("fieldSemantics") or []
    if not all(isinstance(items, list) for items in (terms, rules, field_semantics)):
        raise ValueError("terms, rules, and fieldSemantics must be arrays")
    if len(terms) + len(rules) + len(field_semantics) > MAX_ENTRIES:
        raise ValueError(f"Knowledge source exceeds {MAX_ENTRIES} semantic entries")
    normalized = {
        "schema": SOURCE_SCHEMA,
        "source": {
            "name": _text(source_name_override or source.get("name"), "source.name", limit=300),
            "version": _text(source.get("version") or "1", "source.version", limit=80),
            "type": source_type,
        },
        "terms": [_normalize_term(item) for item in terms],
        "rules": [_normalize_rule(item) for item in rules],
        "fieldSemantics": [_normalize_field_semantic(item) for item in field_semantics],
    }
    if not normalized["terms"] and not normalized["rules"] and not normalized["fieldSemantics"]:
        raise ValueError("Knowledge source must contain at least one semantic entry")
    return normalized


def _usage_object(role: str, usages: list[str]) -> dict[str, bool]:
    result = {
        "filterable": role in {"event_time", "dimension", "status", "identity_key"},
        "sortable": role in {"event_time", "measure", "identity_key"},
        "groupable": role in {"event_time", "dimension", "status", "identity_key"},
        "aggregatable": role == "measure",
        "joinable": role == "identity_key",
        "uniqueKeyCandidate": role == "identity_key",
        "defaultAnalysisField": role in {"event_time", "dimension", "measure"},
    }
    for item in usages:
        enabled = not item.startswith("no-")
        key = item[3:] if item.startswith("no-") else item
        if key in result:
            result[key] = enabled
    return result


def _primary_usage(usage: dict[str, bool], role: str) -> str:
    for key in ("aggregatable", "joinable", "groupable", "filterable"):
        if usage.get(key):
            return key
    return "aggregatable" if role == "measure" else "joinable" if role == "identity_key" else "filterable"


def _workspace_id(connection: sqlite3.Connection, args: argparse.Namespace, active_workspace_id: Callable[[sqlite3.Connection], str]) -> str:
    requested = str(getattr(args, "workspace", "") or "").strip()
    workspace_id = requested or active_workspace_id(connection)
    if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
        raise ValueError(f"Unknown workspace: {workspace_id}")
    return workspace_id


def _workspace_schema_fingerprint(connection: sqlite3.Connection, workspace_id: str) -> str:
    tables: list[dict[str, Any]] = []
    for row in connection.execute(
        "SELECT table_key, display_name, physical_table FROM table_registry WHERE workspace_id = ? ORDER BY table_key",
        (workspace_id,),
    ).fetchall():
        columns = [
            {"name": str(column["name"]), "type": str(column["type"] or ""), "notNull": bool(column["notnull"]), "pk": bool(column["pk"])}
            for column in connection.execute(f"PRAGMA table_info({quote_identifier(str(row['physical_table']))})").fetchall()
        ]
        tables.append({"tableKey": str(row["table_key"]), "displayName": str(row["display_name"]), "columns": columns})
    return _fingerprint({"workspaceId": workspace_id, "tables": tables})


def _semantic_row_payload(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if not row:
        return None
    role = str(row["role"])
    usage = _json(row["usage_json"] if "usage_json" in row.keys() else None, {})
    if not usage:
        usage = _usage_object(role, [str(row["usage"] or "")])
    return {
        "tableKey": str(row["table_key"]),
        "fieldName": str(row["field_name"]),
        "role": role,
        "usage": usage,
        "tags": _json(row["tags_json"] if "tags_json" in row.keys() else None, []),
        "confidence": round(float(row["confidence"] or 0), 4),
        "note": str(row["note"] if "note" in row.keys() and row["note"] is not None else ""),
    }


def _current_target(connection: sqlite3.Connection, workspace_id: str, patch_type: str, target_ref: str) -> dict[str, Any] | None:
    if patch_type == "term":
        row = connection.execute("SELECT * FROM context_terms WHERE workspace_id = ? AND term_key = ?", (workspace_id, target_ref)).fetchone()
        if not row:
            return None
        return {
            "termKey": str(row["term_key"]), "canonicalName": str(row["canonical_name"]),
            "aliases": _json(row["aliases_json"], []), "definition": str(row["definition"]),
            "scopeType": str(row["scope_type"]), "scopeRef": str(row["scope_ref"]),
            "confidence": 1.0,
        }
    if patch_type == "rule":
        row = connection.execute("SELECT * FROM context_rules WHERE workspace_id = ? AND rule_key = ?", (workspace_id, target_ref)).fetchone()
        if not row:
            return None
        return {
            "ruleKey": str(row["rule_key"]), "title": str(row["title"]), "statement": str(row["statement"]),
            "ruleType": str(row["rule_type"]), "appliesTo": _json(row["applies_to_json"], []), "confidence": 1.0,
        }
    table_key, separator, field_name = target_ref.partition(".")
    if not separator:
        return None
    row = connection.execute(
        "SELECT * FROM field_semantics WHERE workspace_id = ? AND table_key = ? AND field_name = ?",
        (workspace_id, table_key, field_name),
    ).fetchone()
    return _semantic_row_payload(row)


def _assert_field_exists(connection: sqlite3.Connection, workspace_id: str, after: dict[str, Any]) -> None:
    registry = connection.execute(
        "SELECT physical_table FROM table_registry WHERE workspace_id = ? AND table_key = ?",
        (workspace_id, after["tableKey"]),
    ).fetchone()
    if not registry:
        raise ValueError(f"Unknown table in semantic proposal: {after['tableKey']}")
    fields = {str(row["name"]) for row in connection.execute(f"PRAGMA table_info({quote_identifier(str(registry['physical_table']))})")}
    if after["fieldName"] not in fields:
        raise ValueError(f"Unknown field in semantic proposal: {after['tableKey']}.{after['fieldName']}")


def _proposal_entries(connection: sqlite3.Connection, workspace_id: str, normalized: dict[str, Any], source_key: str, source_fingerprint: str) -> list[dict[str, Any]]:
    schema_fingerprint = _workspace_schema_fingerprint(connection, workspace_id)
    entries: list[tuple[str, str, dict[str, Any], float]] = []
    for after in normalized["terms"]:
        entries.append(("term", str(after["termKey"]), after, float(after["confidence"])))
    for after in normalized["rules"]:
        entries.append(("rule", str(after["ruleKey"]), after, float(after["confidence"])))
    for after in normalized["fieldSemantics"]:
        _assert_field_exists(connection, workspace_id, after)
        target_ref = f"{after['tableKey']}.{after['fieldName']}"
        materialized = {**after, "usage": _usage_object(str(after["role"]), list(after["usage"]))}
        entries.append(("field-semantic", target_ref, materialized, float(after["confidence"])))
    proposals: list[dict[str, Any]] = []
    for patch_type, target_ref, after, confidence in entries:
        if patch_type in {"term", "rule"}:
            after = {key: value for key, value in after.items() if key != "confidence"}
        before = _current_target(connection, workspace_id, patch_type, target_ref)
        operation = "update" if before is not None else "create"
        proposal_key = _key("patch", source_key, patch_type, target_ref, _fingerprint(after))
        proposals.append({
            "schema": PROPOSAL_SCHEMA,
            "proposalKey": proposal_key,
            "workspaceId": workspace_id,
            "sourceKey": source_key,
            "patchType": patch_type,
            "operation": operation,
            "targetRef": target_ref,
            "before": before,
            "after": after,
            "evidence": {
                "schema": "aibi-semantic-patch-evidence/v1",
                "sourceKey": source_key,
                "sourceFingerprint": source_fingerprint,
                "adapterId": normalized["adapterId"],
                "rawRowsIncluded": False,
                "rawDocumentIncluded": False,
            },
            "sourceFingerprint": source_fingerprint,
            "workspaceSchemaFingerprint": schema_fingerprint,
            "targetFingerprint": _fingerprint(before),
            "confidence": confidence,
            "status": "pending",
        })
    return proposals


def _inline_document(args: argparse.Namespace) -> dict[str, Any]:
    kind = str(args.kind or "").strip()
    if kind not in VALID_PATCH_TYPES:
        raise ValueError("--kind must be term, rule, or field-semantic for a user correction")
    document: dict[str, Any] = {
        "schema": SOURCE_SCHEMA,
        "source": {"name": str(args.source_name or "User correction"), "version": "1", "type": "user-correction"},
        "terms": [], "rules": [], "fieldSemantics": [],
    }
    if kind == "term":
        document["terms"] = [{
            "termKey": str(args.term or ""), "canonicalName": str(args.name or ""),
            "aliases": list(args.alias or []), "definition": str(args.definition or ""),
            "scopeType": str(args.scope_type or "workspace"), "scopeRef": str(args.scope_ref or ""),
            "confidence": args.confidence,
        }]
    elif kind == "rule":
        document["rules"] = [{
            "ruleKey": str(args.rule or ""), "title": str(args.title or ""), "statement": str(args.statement or ""),
            "ruleType": str(args.type or "other"), "appliesTo": list(args.applies_to or []), "confidence": args.confidence,
        }]
    else:
        document["fieldSemantics"] = [{
            "tableKey": str(args.table or ""), "fieldName": str(args.field or ""), "role": str(args.role or ""),
            "usage": list(args.usage or []), "tags": list(args.tag or []), "confidence": args.confidence,
            "note": str(args.note or ""),
        }]
    return document


def semantic_patch_propose_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    input_path = str(args.input or "").strip()
    adapter_id = str(args.adapter or "auto").strip()
    locator_ref = "inline:user-correction"
    if input_path:
        if str(args.kind or "").strip():
            raise ValueError("--kind cannot be combined with --input")
        path = _safe_input_path(input_path)
        if adapter_id == "auto":
            adapter_id = "knowledge-json-v1" if path.suffix.lower() == ".json" else "knowledge-markdown-v1" if path.suffix.lower() in {".md", ".markdown"} else ""
        adapter = _adapter(adapter_id)
        if path.suffix.lower() not in adapter["extensions"]:
            raise ValueError(f"Adapter {adapter_id} does not support {path.suffix.lower()}")
        document, raw = _read_document(path, adapter_id)
        content_fingerprint = hashlib.sha256(raw).hexdigest()
        locator_ref = f"local-file:{hashlib.sha256(str(path).lower().encode('utf-8')).hexdigest()[:20]}:{path.suffix.lower()}"
    else:
        adapter_id = "user-correction-v1" if adapter_id == "auto" else adapter_id
        adapter = _adapter(adapter_id)
        if adapter_id != "user-correction-v1":
            raise ValueError("A file-backed adapter requires --input")
        document = _inline_document(args)
        content_fingerprint = _fingerprint(document)
    normalized = normalize_knowledge_document(
        document,
        source_type_override=str(args.source_type or "").strip(),
        source_name_override=str(args.source_name or "").strip(),
    )
    if normalized["source"]["type"] not in adapter["sourceTypes"]:
        raise ValueError(f"Adapter {adapter_id} does not support source type {normalized['source']['type']}")
    normalized["adapterId"] = adapter_id
    source_key = _key("knowledge", adapter_id, content_fingerprint)
    source_snapshot = {
        "schema": "aibi-knowledge-source-snapshot/v1",
        "sourceSchema": SOURCE_SCHEMA,
        "counts": {
            "terms": len(normalized["terms"]),
            "rules": len(normalized["rules"]),
            "fieldSemantics": len(normalized["fieldSemantics"]),
        },
        "rawDocumentStored": False,
        "rawRowsStored": False,
    }
    with open_db() as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        proposals = _proposal_entries(connection, workspace_id, normalized, source_key, content_fingerprint)
        preview = {
            "source": {
                "sourceKey": source_key, "workspaceId": workspace_id, "adapterId": adapter_id,
                "sourceType": normalized["source"]["type"], "name": normalized["source"]["name"],
                "version": normalized["source"]["version"], "locatorRef": locator_ref,
                "contentFingerprint": content_fingerprint, "snapshot": source_snapshot,
            },
            "proposals": proposals,
        }
        if not args.yes:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, **preview, "persisted": False}
        timestamp = now_iso()
        connection.execute(
            """
            INSERT OR IGNORE INTO knowledge_sources(
              source_key, workspace_id, adapter_id, source_type, name, source_version, locator_ref,
              content_fingerprint, snapshot_json, status, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
            """,
            (
                source_key, workspace_id, adapter_id, normalized["source"]["type"], normalized["source"]["name"],
                normalized["source"]["version"], locator_ref, content_fingerprint,
                _canonical(source_snapshot), timestamp, timestamp,
            ),
        )
        inserted = 0
        for proposal in proposals:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO semantic_patch_proposals(
                  proposal_key, workspace_id, source_key, patch_type, operation, target_ref, before_json, after_json,
                  evidence_json, source_fingerprint, workspace_schema_fingerprint, target_fingerprint,
                  confidence, status, review_json, created_at, updated_at, reviewed_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', '{}', ?, ?, NULL)
                """,
                (
                    proposal["proposalKey"], workspace_id, source_key, proposal["patchType"], proposal["operation"],
                    proposal["targetRef"], _canonical(proposal["before"]), _canonical(proposal["after"]),
                    _canonical(proposal["evidence"]), content_fingerprint, proposal["workspaceSchemaFingerprint"],
                    proposal["targetFingerprint"], proposal["confidence"], timestamp, timestamp,
                ),
            )
            inserted += max(0, int(cursor.rowcount or 0))
        connection.commit()
        persisted_rows = [
            _proposal_payload(connection, connection.execute(
                "SELECT * FROM semantic_patch_proposals WHERE workspace_id = ? AND proposal_key = ?",
                (workspace_id, proposal["proposalKey"]),
            ).fetchone())
            for proposal in proposals
        ]
    return {
        "ok": True, "confirmed": True, "persisted": True, "source": preview["source"],
        "proposals": persisted_rows, "count": len(persisted_rows), "inserted": inserted,
        "idempotentReingest": inserted == 0,
    }


def _proposal_freshness(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    mismatches: list[str] = []
    source = connection.execute(
        "SELECT content_fingerprint, status FROM knowledge_sources WHERE workspace_id = ? AND source_key = ?",
        (row["workspace_id"], row["source_key"]),
    ).fetchone()
    if not source:
        mismatches.append("knowledge-source-missing")
    elif str(source["content_fingerprint"]) != str(row["source_fingerprint"]):
        mismatches.append("knowledge-source-fingerprint-mismatch")
    elif str(source["status"]) != "active":
        mismatches.append("knowledge-source-inactive")
    current_schema = _workspace_schema_fingerprint(connection, str(row["workspace_id"]))
    if current_schema != str(row["workspace_schema_fingerprint"]):
        mismatches.append("workspace-schema-changed")
    current_target = _current_target(connection, str(row["workspace_id"]), str(row["patch_type"]), str(row["target_ref"]))
    if _fingerprint(current_target) != str(row["target_fingerprint"]):
        mismatches.append("target-changed")
    status = "current" if not mismatches else "stale"
    return {"status": status, "usableForReview": not mismatches, "mismatches": mismatches}


def _proposal_payload(connection: sqlite3.Connection, row: sqlite3.Row | None) -> dict[str, Any]:
    if not row:
        raise ValueError("Unknown semantic patch proposal")
    freshness = _proposal_freshness(connection, row) if str(row["status"]) == "pending" else {"status": "reviewed", "usableForReview": False, "mismatches": []}
    effective_status = "stale" if str(row["status"]) == "pending" and freshness["status"] == "stale" else str(row["status"])
    source = connection.execute(
        "SELECT adapter_id, source_type, name, source_version, locator_ref, content_fingerprint FROM knowledge_sources WHERE workspace_id = ? AND source_key = ?",
        (row["workspace_id"], row["source_key"]),
    ).fetchone()
    return {
        "schema": PROPOSAL_SCHEMA,
        "proposalKey": str(row["proposal_key"]), "workspaceId": str(row["workspace_id"]),
        "sourceKey": str(row["source_key"]), "patchType": str(row["patch_type"]),
        "operation": str(row["operation"]), "targetRef": str(row["target_ref"]),
        "before": _json(row["before_json"], None), "after": _json(row["after_json"], {}),
        "evidence": _json(row["evidence_json"], {}), "confidence": round(float(row["confidence"]), 4),
        "status": effective_status, "storedStatus": str(row["status"]), "freshness": freshness,
        "review": _json(row["review_json"], {}), "createdAt": str(row["created_at"]),
        "updatedAt": str(row["updated_at"]), "reviewedAt": row["reviewed_at"],
        "source": {
            "adapterId": str(source["adapter_id"]), "sourceType": str(source["source_type"]),
            "name": str(source["name"]), "version": str(source["source_version"]),
            "locatorRef": str(source["locator_ref"]), "contentFingerprint": str(source["content_fingerprint"]),
        } if source else None,
    }


def knowledge_sources_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        rows = connection.execute(
            "SELECT * FROM knowledge_sources WHERE workspace_id = ? ORDER BY created_at DESC LIMIT ?",
            (workspace_id, max(1, min(int(args.limit), 200))),
        ).fetchall()
    sources = [
        {
            "sourceKey": str(row["source_key"]), "workspaceId": str(row["workspace_id"]),
            "adapterId": str(row["adapter_id"]), "sourceType": str(row["source_type"]),
            "name": str(row["name"]), "version": str(row["source_version"]),
            "locatorRef": str(row["locator_ref"]), "contentFingerprint": str(row["content_fingerprint"]),
            "snapshot": _json(row["snapshot_json"], {}), "status": str(row["status"]),
            "createdAt": str(row["created_at"]), "updatedAt": str(row["updated_at"]),
        }
        for row in rows
    ]
    return {"ok": True, "schema": "aibi-knowledge-source-collection/v1", "workspaceId": workspace_id, "sources": sources, "count": len(sources), "rawDocumentsIncluded": False}


def semantic_patch_proposals_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        proposal_key = str(args.proposal or "").strip()
        if proposal_key:
            row = connection.execute(
                "SELECT * FROM semantic_patch_proposals WHERE workspace_id = ? AND proposal_key = ?",
                (workspace_id, proposal_key),
            ).fetchone()
            proposal = _proposal_payload(connection, row)
            return {"ok": True, "schema": COLLECTION_SCHEMA, "workspaceId": workspace_id, "proposal": proposal}
        stored_status = str(args.status or "").strip()
        params: list[Any] = [workspace_id]
        where = "WHERE workspace_id = ?"
        if stored_status and stored_status != "stale":
            where += " AND status = ?"
            params.append(stored_status)
        params.append(max(1, min(int(args.limit), 500)))
        rows = connection.execute(
            f"SELECT * FROM semantic_patch_proposals {where} ORDER BY created_at DESC, proposal_key LIMIT ?",
            params,
        ).fetchall()
        proposals = [_proposal_payload(connection, row) for row in rows]
        if stored_status == "stale":
            proposals = [proposal for proposal in proposals if proposal["status"] == "stale"]
        counts: dict[str, int] = {status: 0 for status in ("pending", "accepted", "rejected", "stale")}
        for proposal in proposals:
            counts[proposal["status"]] = counts.get(proposal["status"], 0) + 1
    return {"ok": True, "schema": COLLECTION_SCHEMA, "workspaceId": workspace_id, "proposals": proposals, "count": len(proposals), "counts": counts}


def _assert_term_conflict_free(connection: sqlite3.Connection, workspace_id: str, target_ref: str, after: dict[str, Any]) -> None:
    proposed_names = {str(after["canonicalName"]).casefold(), *(str(item).casefold() for item in after["aliases"])}
    rows = connection.execute(
        "SELECT term_key, canonical_name, aliases_json FROM context_terms WHERE workspace_id = ? AND term_key <> ? AND scope_type = ? AND scope_ref = ? AND status <> 'deprecated'",
        (workspace_id, target_ref, after["scopeType"], after["scopeRef"]),
    ).fetchall()
    for row in rows:
        current_names = {str(row["canonical_name"]).casefold(), *(str(item).casefold() for item in _json(row["aliases_json"], []))}
        if proposed_names & current_names:
            raise ValueError(f"Semantic patch conflicts with context term: {row['term_key']}")


def _apply_patch(connection: sqlite3.Connection, row: sqlite3.Row, now_iso: Callable[[], str]) -> dict[str, Any]:
    workspace_id = str(row["workspace_id"])
    patch_type = str(row["patch_type"])
    target_ref = str(row["target_ref"])
    after = _json(row["after_json"], {})
    timestamp = now_iso()
    evidence = [f"semantic-patch:{row['proposal_key']}", f"knowledge-source:{row['source_key']}"]
    if patch_type == "term":
        _assert_term_conflict_free(connection, workspace_id, target_ref, after)
        existing = connection.execute("SELECT created_at FROM context_terms WHERE workspace_id = ? AND term_key = ?", (workspace_id, target_ref)).fetchone()
        connection.execute(
            """
            INSERT INTO context_terms(term_key, workspace_id, canonical_name, aliases_json, definition, scope_type, scope_ref, status, source, evidence_json, created_at, updated_at, confirmed_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, 'confirmed', 'reviewed', ?, ?, ?, ?)
            ON CONFLICT(workspace_id, term_key) DO UPDATE SET
              canonical_name=excluded.canonical_name, aliases_json=excluded.aliases_json, definition=excluded.definition,
              scope_type=excluded.scope_type, scope_ref=excluded.scope_ref, status='confirmed', source='reviewed',
              evidence_json=excluded.evidence_json, updated_at=excluded.updated_at, confirmed_at=excluded.confirmed_at
            """,
            (target_ref, workspace_id, after["canonicalName"], _canonical(after["aliases"]), after["definition"], after["scopeType"], after["scopeRef"], _canonical(evidence), existing["created_at"] if existing else timestamp, timestamp, timestamp),
        )
    elif patch_type == "rule":
        existing = connection.execute("SELECT created_at FROM context_rules WHERE workspace_id = ? AND rule_key = ?", (workspace_id, target_ref)).fetchone()
        connection.execute(
            """
            INSERT INTO context_rules(rule_key, workspace_id, title, statement, rule_type, applies_to_json, status, source, evidence_json, created_at, updated_at, confirmed_at)
            VALUES(?, ?, ?, ?, ?, ?, 'confirmed', 'reviewed', ?, ?, ?, ?)
            ON CONFLICT(workspace_id, rule_key) DO UPDATE SET
              title=excluded.title, statement=excluded.statement, rule_type=excluded.rule_type,
              applies_to_json=excluded.applies_to_json, status='confirmed', source='reviewed',
              evidence_json=excluded.evidence_json, updated_at=excluded.updated_at, confirmed_at=excluded.confirmed_at
            """,
            (target_ref, workspace_id, after["title"], after["statement"], after["ruleType"], _canonical(after["appliesTo"]), _canonical(evidence), existing["created_at"] if existing else timestamp, timestamp, timestamp),
        )
    else:
        _assert_field_exists(connection, workspace_id, after)
        usage = after["usage"] if isinstance(after.get("usage"), dict) else _usage_object(str(after["role"]), list(after.get("usage") or []))
        connection.execute(
            """
            INSERT INTO field_semantics(workspace_id, table_key, field_name, role, usage, confidence, tags_json, usage_json, source, note, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'reviewed', ?, ?)
            ON CONFLICT(workspace_id, table_key, field_name) DO UPDATE SET
              role=excluded.role, usage=excluded.usage, confidence=excluded.confidence, tags_json=excluded.tags_json,
              usage_json=excluded.usage_json, source='reviewed', note=excluded.note, updated_at=excluded.updated_at
            """,
            (workspace_id, after["tableKey"], after["fieldName"], after["role"], _primary_usage(usage, after["role"]), float(after["confidence"]), _canonical(after["tags"]), _canonical(usage), after.get("note") or "", timestamp),
        )
    return {"patchType": patch_type, "targetRef": target_ref, "after": after, "source": "reviewed"}


def semantic_patch_review_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    decision = str(args.decision or "").strip()
    if decision not in VALID_DECISIONS:
        raise ValueError("decision must be accept or reject")
    note = _text(args.note, "review note", required=False, limit=2000)
    with open_db() as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        row = connection.execute(
            "SELECT * FROM semantic_patch_proposals WHERE workspace_id = ? AND proposal_key = ?",
            (workspace_id, str(args.proposal or "").strip()),
        ).fetchone()
        proposal = _proposal_payload(connection, row)
        if proposal["storedStatus"] != "pending":
            raise ValueError(f"Semantic patch proposal is already {proposal['storedStatus']}")
        if decision == "accept" and not proposal["freshness"]["usableForReview"]:
            raise ValueError("Semantic patch proposal is stale: " + ", ".join(proposal["freshness"]["mismatches"]))
        review = {"decision": decision, "note": note, "reviewer": "local-user", "proposalFingerprint": _fingerprint({"before": proposal["before"], "after": proposal["after"]})}
        if not args.yes:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "decision": decision, "proposal": proposal, "review": review, "applied": False}
        timestamp = now_iso()
        applied = _apply_patch(connection, row, now_iso) if decision == "accept" else None
        status = "accepted" if decision == "accept" else "rejected"
        connection.execute(
            "UPDATE semantic_patch_proposals SET status = ?, review_json = ?, updated_at = ?, reviewed_at = ? WHERE workspace_id = ? AND proposal_key = ? AND status = 'pending'",
            (status, _canonical(review), timestamp, timestamp, workspace_id, row["proposal_key"]),
        )
        connection.commit()
        saved = connection.execute(
            "SELECT * FROM semantic_patch_proposals WHERE workspace_id = ? AND proposal_key = ?",
            (workspace_id, row["proposal_key"]),
        ).fetchone()
        result = _proposal_payload(connection, saved)
    return {"ok": True, "confirmed": True, "decision": decision, "proposal": result, "applied": decision == "accept", "appliedPatch": applied}
