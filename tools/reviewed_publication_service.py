from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from typing import Any, Callable

from analysis_unit_service import analysis_unit_consumer_state, get_analysis_unit
from query_plan_receipt_service import (
    current_query_receipt_source_state,
    get_query_receipt,
    query_receipt_binding_fingerprint,
)


REVIEWED_PUBLICATION_SCHEMA = "aibi-reviewed-publication/v1"
REVIEWED_PUBLICATION_PLAN_SCHEMA = "aibi-reviewed-publication-plan/v1"
EVIDENCE_LEDGER_SCHEMA = "aibi-evidence-ledger/v1"
LEDGER_GENESIS_HASH = hashlib.sha256(b"aibi-evidence-ledger/v1:genesis").hexdigest()
NONE_SKILL_FINGERPRINT = hashlib.sha256(b"aibi-reviewed-publication:no-skill").hexdigest()
PUBLICATION_STATUSES = {"current", "stale", "integrity_failed", "deprecated"}
LEDGER_KINDS = {"publication_created", "publication_deprecated", "publication_tombstoned"}

DRIFT_REASONS = {
    "analysis-unit-changed",
    "analysis-unit-missing",
    "analysis-unit-not-current",
    "confirmed-plan-changed",
    "confirmed-plan-missing",
    "confirmed-plan-not-confirmed",
    "content-changed",
    "data-changed",
    "domain-pack-changed",
    "input-contract-changed",
    "ledger-integrity-failed",
    "query-receipt-changed",
    "query-receipt-missing",
    "query-receipt-not-executed",
    "relationship-changed",
    "schema-changed",
    "skill-changed",
    "source-changed",
    "source-run-changed",
    "workspace-manifest-changed",
}

_FORBIDDEN_CONTENT_KEYS = {
    "absolutepath",
    "connectionstring",
    "credential",
    "credentialref",
    "filepath",
    "password",
    "rawrow",
    "rawrows",
    "secret",
    "token",
}
_ABSOLUTE_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|(?<!:)//[^/\s]+/|(?<!:)\\\\[^\\\s]+\\)")
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.I)
_PHONE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
_CN_ID = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_SECRET_VALUE = re.compile(r"(?:bearer\s+[A-Za-z0-9._~+/-]+=*|(?:password|passwd|secret|token|api[_-]?key)\s*[:=]|\bsk-[A-Za-z0-9_-]{12,})", re.I)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _canonical_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def stable_json(value: Any) -> str:
    return json.dumps(_canonical_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(str(value or "[]"))
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def ensure_reviewed_publication_schema(connection: sqlite3.Connection) -> None:
    """Create the append-only publication tables until the central migration owns them."""
    statements = (
        """
        CREATE TABLE IF NOT EXISTS reviewed_publications (
          publication_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          memory_key TEXT NOT NULL,
          query_receipt_key TEXT NOT NULL,
          unit_key TEXT NOT NULL,
          title TEXT NOT NULL,
          status TEXT NOT NULL,
          content_json TEXT NOT NULL,
          content_fingerprint TEXT NOT NULL,
          input_contract_json TEXT NOT NULL,
          input_fingerprint TEXT NOT NULL,
          ledger_head_hash TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          reviewed_at TEXT NOT NULL,
          deprecated_at TEXT,
          deprecation_reason TEXT NOT NULL DEFAULT '',
          PRIMARY KEY(workspace_id, publication_key)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_reviewed_publications_workspace_status ON reviewed_publications(workspace_id, status, updated_at)",
        "CREATE INDEX IF NOT EXISTS idx_reviewed_publications_workspace_memory ON reviewed_publications(workspace_id, memory_key, updated_at)",
        """
        CREATE TABLE IF NOT EXISTS evidence_ledger_entries (
          entry_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          publication_key TEXT NOT NULL,
          sequence INTEGER NOT NULL,
          kind TEXT NOT NULL,
          payload_fingerprint TEXT NOT NULL,
          previous_hash TEXT NOT NULL,
          entry_hash TEXT NOT NULL,
          evidence_refs_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, entry_key),
          UNIQUE(workspace_id, publication_key, sequence)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_evidence_ledger_publication_sequence ON evidence_ledger_entries(workspace_id, publication_key, sequence)",
    )
    for statement in statements:
        connection.execute(statement)


def _validate_public_content(content: Any) -> dict[str, Any]:
    if not isinstance(content, dict):
        raise ValueError("Reviewed publication content must be a JSON object")
    canonical = _canonical_value(content)
    encoded = stable_json(canonical)
    if len(encoded.encode("utf-8")) > 256_000:
        raise ValueError("Reviewed publication content exceeds the 256 KB limit")

    def walk(value: Any, path: str = "content") -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                normalized = re.sub(r"[^a-z0-9]", "", str(key).casefold())
                if normalized in _FORBIDDEN_CONTENT_KEYS or any(
                    token in normalized for token in ("password", "secret", "credential", "connectionstring", "accesstoken", "refreshtoken", "rawrow", "absolutepath", "filepath")
                ):
                    raise ValueError(f"Reviewed publication content contains forbidden field: {path}.{key}")
                walk(item, f"{path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f"{path}[{index}]")
        elif isinstance(value, str):
            if _ABSOLUTE_PATH.search(value):
                raise ValueError(f"Reviewed publication content contains an absolute path at {path}")
            if _SECRET_VALUE.search(value):
                raise ValueError(f"Reviewed publication content contains a credential-like value at {path}")
            if _EMAIL.search(value) or _PHONE.search(value) or _CN_ID.search(value):
                raise ValueError(f"Reviewed publication content contains potential PII at {path}")

    walk(canonical)
    return canonical


def _validate_public_text(value: Any, *, label: str, maximum: int) -> str:
    text = str(value or "").strip()
    if not text or len(text) > maximum:
        raise ValueError(f"{label} must contain 1-{maximum} characters")
    if _ABSOLUTE_PATH.search(text) or _SECRET_VALUE.search(text):
        raise ValueError(f"{label} contains a path or credential-like value")
    if _EMAIL.search(text) or _PHONE.search(text) or _CN_ID.search(text):
        raise ValueError(f"{label} contains potential PII")
    return text


def _memory_row(connection: sqlite3.Connection, workspace_id: str, memory_key: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM confirmed_plan_memories WHERE workspace_id = ? AND memory_key = ?",
        (workspace_id, memory_key),
    ).fetchone()


def _publication_row(connection: sqlite3.Connection, workspace_id: str, publication_key: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM reviewed_publications WHERE workspace_id = ? AND publication_key = ?",
        (workspace_id, publication_key),
    ).fetchone()


def _publication_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "schema": REVIEWED_PUBLICATION_SCHEMA,
        "publicationKey": row["publication_key"],
        "workspaceId": row["workspace_id"],
        "memoryKey": row["memory_key"],
        "queryReceiptKey": row["query_receipt_key"],
        "unitKey": row["unit_key"],
        "title": row["title"],
        "status": row["status"],
        "content": _json_object(row["content_json"]),
        "contentFingerprint": row["content_fingerprint"],
        "inputContract": _json_object(row["input_contract_json"]),
        "inputFingerprint": row["input_fingerprint"],
        "ledgerHeadHash": row["ledger_head_hash"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "reviewedAt": row["reviewed_at"],
        "deprecatedAt": row["deprecated_at"],
        "deprecationReason": row["deprecation_reason"],
    }


def _ledger_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "schema": EVIDENCE_LEDGER_SCHEMA,
        "entryKey": row["entry_key"],
        "workspaceId": row["workspace_id"],
        "publicationKey": row["publication_key"],
        "sequence": int(row["sequence"]),
        "kind": row["kind"],
        "payloadFingerprint": row["payload_fingerprint"],
        "previousHash": row["previous_hash"],
        "entryHash": row["entry_hash"],
        "evidenceRefs": _json_list(row["evidence_refs_json"]),
        "createdAt": row["created_at"],
    }


def _entry_material(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": EVIDENCE_LEDGER_SCHEMA,
        "entryKey": entry["entryKey"],
        "workspaceId": entry["workspaceId"],
        "publicationKey": entry["publicationKey"],
        "sequence": int(entry["sequence"]),
        "kind": entry["kind"],
        "payloadFingerprint": entry["payloadFingerprint"],
        "previousHash": entry["previousHash"],
        "evidenceRefs": entry["evidenceRefs"],
        "createdAt": entry["createdAt"],
    }


def _validated_inputs(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    memory_key: str,
    unit_key: str,
    skill_fingerprint: str | None,
) -> tuple[sqlite3.Row, dict[str, Any], dict[str, Any], dict[str, Any]]:
    memory = _memory_row(connection, workspace_id, memory_key)
    if not memory:
        raise ValueError("Unknown Confirmed Plan Memory in the active workspace")
    if str(memory["status"] or "") != "confirmed":
        raise ValueError("Reviewed publication requires a confirmed plan memory")
    receipt_key = str(memory["query_receipt_key"] or "")
    receipt = get_query_receipt(connection, workspace_id, receipt_key)
    if not receipt or str(receipt.get("status") or "") != "executed":
        raise ValueError("Reviewed publication requires an executed Query Receipt")
    source_state = current_query_receipt_source_state(connection, workspace_id, receipt)
    if not source_state.get("matchesReceipt"):
        blockers = ", ".join(source_state.get("blockers") or ["query-receipt-drifted"])
        raise ValueError(f"Reviewed publication requires current Query Receipt evidence: {blockers}")
    binding_fingerprint = query_receipt_binding_fingerprint(receipt)
    source = receipt.get("source") if isinstance(receipt.get("source"), dict) else {}
    stored_binding = str(memory["binding_fingerprint"] or "")
    # A legacy Confirmed Plan Memory is never auto-published. An explicit review
    # may upgrade its schema-only binding after the complete current-state proof
    # above succeeds; the new publication always freezes the full binding.
    if stored_binding not in {binding_fingerprint, str(source.get("schemaFingerprint") or "")}:
        raise ValueError("Confirmed Plan Memory binding has drifted")
    unit = get_analysis_unit(connection, workspace_id, unit_key)
    if not unit:
        raise ValueError("Unknown Analysis Unit in the active workspace")
    if str(unit.get("queryReceiptKey") or "") != receipt_key:
        raise ValueError("Analysis Unit and Confirmed Plan Memory reference different Query Receipts")
    unit_state = analysis_unit_consumer_state(connection, workspace_id, unit)
    if str(unit.get("status") or "") != "ready" or not unit_state.get("usable"):
        blockers = ", ".join(unit_state.get("blockers") or ["analysis-unit-not-ready"])
        raise ValueError(f"Reviewed publication requires a current ready Analysis Unit: {blockers}")

    plan = _json_object(memory["plan_json"])
    normalized_skill = str(skill_fingerprint or "").strip() or NONE_SKILL_FINGERPRINT
    if not _SHA256.fullmatch(normalized_skill):
        raise ValueError("Skill fingerprint must be a lowercase SHA-256 value")
    contract = {
        "schema": "aibi-reviewed-publication-input/v1",
        "workspaceId": workspace_id,
        "memoryKey": memory_key,
        "planFingerprint": fingerprint(plan),
        "queryReceiptKey": receipt_key,
        "queryReceiptFingerprint": fingerprint(receipt),
        "queryReceiptBindingFingerprint": binding_fingerprint,
        "unitKey": unit_key,
        "analysisUnitDefinitionFingerprint": str(unit.get("definitionFingerprint") or ""),
        "resultFingerprint": str(unit.get("resultFingerprint") or ""),
        "sourceFingerprint": str(source.get("sourceFingerprint") or ""),
        "sourceRunId": str(source.get("currentSourceRunId") or ""),
        "dataFingerprint": str(source.get("dataFingerprint") or ""),
        "schemaFingerprint": str(source.get("schemaFingerprint") or ""),
        "relationshipFingerprint": str(source.get("relationshipPathFingerprint") or ""),
        "domainPackFingerprint": str(receipt.get("domainPackFingerprint") or ""),
        "workspaceManifestFingerprint": str((receipt.get("workspaceManifest") or {}).get("fingerprint") or "")
        if isinstance(receipt.get("workspaceManifest"), dict)
        else "",
        "skillFingerprint": normalized_skill,
    }
    return memory, receipt, unit, contract


def build_reviewed_publication_plan(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    memory_key: str,
    unit_key: str,
    title: str,
    content: dict[str, Any],
    skill_fingerprint: str | None = None,
) -> dict[str, Any]:
    normalized_title = _validate_public_text(title, label="Reviewed publication title", maximum=200)
    normalized_content = _validate_public_content(content)
    _memory, _receipt, _unit, contract = _validated_inputs(
        connection,
        workspace_id=workspace_id,
        memory_key=memory_key,
        unit_key=unit_key,
        skill_fingerprint=skill_fingerprint,
    )
    content_fingerprint = fingerprint({"title": normalized_title, "content": normalized_content})
    input_fingerprint = fingerprint(contract)
    material = {
        "schema": REVIEWED_PUBLICATION_SCHEMA,
        "workspaceId": workspace_id,
        "memoryKey": memory_key,
        "unitKey": unit_key,
        "title": normalized_title,
        "contentFingerprint": content_fingerprint,
        "inputFingerprint": input_fingerprint,
    }
    publication_key = f"reviewed_publication_{fingerprint(material)[:20]}"
    plan = {
        "schema": REVIEWED_PUBLICATION_PLAN_SCHEMA,
        "workspaceId": workspace_id,
        "publicationKey": publication_key,
        "memoryKey": memory_key,
        "queryReceiptKey": contract["queryReceiptKey"],
        "unitKey": unit_key,
        "title": normalized_title,
        "content": normalized_content,
        "contentFingerprint": content_fingerprint,
        "inputContract": contract,
        "inputFingerprint": input_fingerprint,
        "requiresConfirmation": True,
    }
    plan["planFingerprint"] = fingerprint(plan)
    return plan


def _append_ledger_entry(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    publication_key: str,
    kind: str,
    payload_fingerprint: str,
    evidence_refs: list[dict[str, Any]],
    created_at: str,
    expected_head_hash: str | None,
) -> dict[str, Any]:
    if kind not in LEDGER_KINDS:
        raise ValueError(f"Unsupported evidence ledger entry kind: {kind}")
    rows = connection.execute(
        "SELECT * FROM evidence_ledger_entries WHERE workspace_id = ? AND publication_key = ? ORDER BY sequence",
        (workspace_id, publication_key),
    ).fetchall()
    sequence = len(rows) + 1
    previous_hash = str(rows[-1]["entry_hash"]) if rows else LEDGER_GENESIS_HASH
    if expected_head_hash is not None and str(expected_head_hash) != previous_hash:
        raise ValueError("Evidence ledger head changed; refresh before appending")
    key_material = {
        "workspaceId": workspace_id,
        "publicationKey": publication_key,
        "sequence": sequence,
        "kind": kind,
        "payloadFingerprint": payload_fingerprint,
        "previousHash": previous_hash,
        "createdAt": created_at,
    }
    entry = {
        "schema": EVIDENCE_LEDGER_SCHEMA,
        "entryKey": f"ledger_entry_{fingerprint(key_material)[:20]}",
        "workspaceId": workspace_id,
        "publicationKey": publication_key,
        "sequence": sequence,
        "kind": kind,
        "payloadFingerprint": payload_fingerprint,
        "previousHash": previous_hash,
        "evidenceRefs": _canonical_value(evidence_refs),
        "createdAt": created_at,
    }
    entry["entryHash"] = fingerprint(_entry_material(entry))
    connection.execute(
        """
        INSERT INTO evidence_ledger_entries(
          entry_key, workspace_id, publication_key, sequence, kind, payload_fingerprint,
          previous_hash, entry_hash, evidence_refs_json, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entry["entryKey"],
            workspace_id,
            publication_key,
            sequence,
            kind,
            payload_fingerprint,
            previous_hash,
            entry["entryHash"],
            stable_json(entry["evidenceRefs"]),
            created_at,
        ),
    )
    return entry


def publish_reviewed_artifact(
    connection: sqlite3.Connection,
    *,
    plan: dict[str, Any],
    expected_plan_fingerprint: str,
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    if str(plan.get("schema") or "") != REVIEWED_PUBLICATION_PLAN_SCHEMA:
        raise ValueError("Unsupported reviewed publication plan schema")
    supplied_plan = {key: value for key, value in plan.items() if key != "planFingerprint"}
    actual_plan_fingerprint = fingerprint(supplied_plan)
    if str(plan.get("planFingerprint") or "") != actual_plan_fingerprint:
        raise ValueError("Reviewed publication plan content changed after preview")
    if str(expected_plan_fingerprint or "") != actual_plan_fingerprint:
        raise ValueError("Reviewed publication confirmation fingerprint does not match the preview")
    workspace_id = str(plan.get("workspaceId") or "").strip()
    memory_key = str(plan.get("memoryKey") or "").strip()
    unit_key = str(plan.get("unitKey") or "").strip()
    input_contract = plan.get("inputContract") if isinstance(plan.get("inputContract"), dict) else {}
    _memory, _receipt, _unit, current_contract = _validated_inputs(
        connection,
        workspace_id=workspace_id,
        memory_key=memory_key,
        unit_key=unit_key,
        skill_fingerprint=str(input_contract.get("skillFingerprint") or ""),
    )
    if fingerprint(current_contract) != str(plan.get("inputFingerprint") or ""):
        raise ValueError("Reviewed publication inputs drifted after preview")
    content = _validate_public_content(plan.get("content"))
    if fingerprint({"title": str(plan.get("title") or ""), "content": content}) != str(plan.get("contentFingerprint") or ""):
        raise ValueError("Reviewed publication content fingerprint changed after preview")

    publication_key = str(plan.get("publicationKey") or "").strip()
    existing = _publication_row(connection, workspace_id, publication_key)
    if existing:
        existing_payload = _publication_payload(existing)
        if (
            existing_payload["contentFingerprint"] == plan["contentFingerprint"]
            and existing_payload["inputFingerprint"] == plan["inputFingerprint"]
        ):
            ledger = verify_evidence_ledger(
                connection,
                workspace_id=workspace_id,
                publication_key=publication_key,
            )
            if not ledger["ok"]:
                raise ValueError("Cannot replay a publication with a damaged evidence ledger")
            return {"publication": existing_payload, "created": False}
        raise ValueError("Reviewed publication key conflicts with different content")
    if not connection.in_transaction:
        raise RuntimeError("Reviewed publication writes require the caller to hold BEGIN IMMEDIATE")

    timestamp = now_iso()
    connection.execute(
        """
        INSERT INTO reviewed_publications(
          publication_key, workspace_id, memory_key, query_receipt_key, unit_key, title,
          status, content_json, content_fingerprint, input_contract_json, input_fingerprint,
          ledger_head_hash, created_at, updated_at, reviewed_at, deprecated_at, deprecation_reason
        ) VALUES(?, ?, ?, ?, ?, ?, 'current', ?, ?, ?, ?, '', ?, ?, ?, NULL, '')
        """,
        (
            publication_key,
            workspace_id,
            memory_key,
            plan["queryReceiptKey"],
            unit_key,
            plan["title"],
            stable_json(content),
            plan["contentFingerprint"],
            stable_json(current_contract),
            plan["inputFingerprint"],
            timestamp,
            timestamp,
            timestamp,
        ),
    )
    evidence_refs = [
        {"type": "confirmedPlanMemory", "memoryKey": memory_key},
        {"type": "queryPlanReceipt", "receiptKey": plan["queryReceiptKey"]},
        {"type": "analysisUnit", "unitKey": unit_key},
    ]
    entry = _append_ledger_entry(
        connection,
        workspace_id=workspace_id,
        publication_key=publication_key,
        kind="publication_created",
        payload_fingerprint=fingerprint({
            "contentFingerprint": plan["contentFingerprint"],
            "inputFingerprint": plan["inputFingerprint"],
        }),
        evidence_refs=evidence_refs,
        created_at=timestamp,
        expected_head_hash=LEDGER_GENESIS_HASH,
    )
    connection.execute(
        "UPDATE reviewed_publications SET ledger_head_hash = ? WHERE workspace_id = ? AND publication_key = ?",
        (entry["entryHash"], workspace_id, publication_key),
    )
    saved = _publication_row(connection, workspace_id, publication_key)
    return {"publication": _publication_payload(saved), "ledgerEntry": entry, "created": True}


def list_evidence_ledger(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    publication_key: str,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT * FROM evidence_ledger_entries WHERE workspace_id = ? AND publication_key = ? ORDER BY sequence",
        (workspace_id, publication_key),
    ).fetchall()
    return [_ledger_payload(row) for row in rows]


def verify_evidence_ledger(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    publication_key: str,
) -> dict[str, Any]:
    publication_row = _publication_row(connection, workspace_id, publication_key)
    if not publication_row:
        return {
            "schema": "aibi-evidence-ledger-verification/v1",
            "workspaceId": workspace_id,
            "publicationKey": publication_key,
            "ok": False,
            "blockers": ["publication-missing"],
            "currentEvidence": False,
            "evidenceBlockers": ["publication-missing"],
            "entryCount": 0,
            "headHash": LEDGER_GENESIS_HASH,
        }
    publication = _publication_payload(publication_row)
    entries = list_evidence_ledger(connection, workspace_id=workspace_id, publication_key=publication_key)
    blockers: list[str] = []
    evidence_blockers: list[str] = []
    actual_content_fingerprint = fingerprint({
        "title": publication["title"],
        "content": publication["content"],
    })
    if actual_content_fingerprint != publication["contentFingerprint"]:
        blockers.append("publication-content-fingerprint-mismatch")
    if fingerprint(publication["inputContract"]) != publication["inputFingerprint"]:
        blockers.append("publication-input-fingerprint-mismatch")
    previous_hash = LEDGER_GENESIS_HASH
    for expected_sequence, entry in enumerate(entries, start=1):
        if entry["workspaceId"] != workspace_id or entry["publicationKey"] != publication_key:
            blockers.append("ledger-entry-workspace-mismatch")
        if entry["sequence"] != expected_sequence:
            blockers.append("ledger-sequence-gap")
        if entry["previousHash"] != previous_hash:
            blockers.append("ledger-previous-hash-mismatch")
        if fingerprint(_entry_material(entry)) != entry["entryHash"]:
            blockers.append("ledger-entry-hash-mismatch")
        for reference in entry["evidenceRefs"]:
            if not isinstance(reference, dict):
                blockers.append("ledger-evidence-reference-invalid")
                continue
            kind = str(reference.get("type") or "")
            if kind == "queryPlanReceipt":
                receipt = get_query_receipt(connection, workspace_id, str(reference.get("receiptKey") or ""))
                if not receipt:
                    evidence_blockers.append("ledger-query-receipt-missing")
                elif str(receipt.get("status") or "") != "executed":
                    evidence_blockers.append("ledger-query-receipt-not-executed")
                elif not current_query_receipt_source_state(connection, workspace_id, receipt).get("matchesReceipt"):
                    evidence_blockers.append("ledger-query-receipt-not-current")
            elif kind == "analysisUnit":
                unit = get_analysis_unit(connection, workspace_id, str(reference.get("unitKey") or ""))
                if not unit:
                    evidence_blockers.append("ledger-analysis-unit-missing")
                elif not analysis_unit_consumer_state(connection, workspace_id, unit).get("usable"):
                    evidence_blockers.append("ledger-analysis-unit-not-current")
            elif kind == "confirmedPlanMemory":
                memory = _memory_row(connection, workspace_id, str(reference.get("memoryKey") or ""))
                if not memory:
                    evidence_blockers.append("ledger-confirmed-plan-missing")
                elif str(memory["status"] or "") != "confirmed":
                    evidence_blockers.append("ledger-confirmed-plan-not-current")
        previous_hash = entry["entryHash"]
    if not entries:
        blockers.append("ledger-empty")
    if previous_hash != publication["ledgerHeadHash"]:
        blockers.append("ledger-head-hash-mismatch")
    if entries:
        expected_creation_payload = fingerprint({
            "contentFingerprint": publication["contentFingerprint"],
            "inputFingerprint": publication["inputFingerprint"],
        })
        if entries[0]["kind"] != "publication_created" or entries[0]["payloadFingerprint"] != expected_creation_payload:
            blockers.append("ledger-publication-payload-mismatch")
    return {
        "schema": "aibi-evidence-ledger-verification/v1",
        "workspaceId": workspace_id,
        "publicationKey": publication_key,
        "ok": not blockers,
        "blockers": list(dict.fromkeys(blockers)),
        "currentEvidence": not evidence_blockers,
        "evidenceBlockers": list(dict.fromkeys(evidence_blockers)),
        "entryCount": len(entries),
        "genesisHash": LEDGER_GENESIS_HASH,
        "headHash": previous_hash,
    }


def _drift_reason_details(
    connection: sqlite3.Connection,
    *,
    publication: dict[str, Any],
    current_skill_fingerprint: str | None,
) -> list[dict[str, Any]]:
    workspace_id = publication["workspaceId"]
    contract = publication["inputContract"]
    reasons: list[dict[str, Any]] = []

    def add(code: str, expected: Any = None, current: Any = None) -> None:
        if code not in DRIFT_REASONS:
            raise AssertionError(f"Unregistered publication drift reason: {code}")
        if not any(item["code"] == code for item in reasons):
            reasons.append({"code": code, "expected": expected, "current": current})

    current_content_fingerprint = fingerprint({"title": publication["title"], "content": publication["content"]})
    if current_content_fingerprint != publication["contentFingerprint"]:
        add("content-changed", publication["contentFingerprint"], current_content_fingerprint)
    if fingerprint(contract) != publication["inputFingerprint"]:
        add("input-contract-changed", publication["inputFingerprint"], fingerprint(contract))

    memory = _memory_row(connection, workspace_id, publication["memoryKey"])
    if not memory:
        add("confirmed-plan-missing")
    else:
        if str(memory["status"] or "") != "confirmed":
            add("confirmed-plan-not-confirmed", "confirmed", memory["status"])
        current_plan_fingerprint = fingerprint(_json_object(memory["plan_json"]))
        if current_plan_fingerprint != contract.get("planFingerprint"):
            add("confirmed-plan-changed", contract.get("planFingerprint"), current_plan_fingerprint)

    receipt = get_query_receipt(connection, workspace_id, publication["queryReceiptKey"])
    if not receipt:
        add("query-receipt-missing")
    else:
        if str(receipt.get("status") or "") != "executed":
            add("query-receipt-not-executed", "executed", receipt.get("status"))
        current_receipt_fingerprint = fingerprint(receipt)
        if current_receipt_fingerprint != contract.get("queryReceiptFingerprint"):
            add("query-receipt-changed", contract.get("queryReceiptFingerprint"), current_receipt_fingerprint)
        source_state = current_query_receipt_source_state(connection, workspace_id, receipt)
        current_contract = {
            "sourceFingerprint": source_state.get("sourceFingerprint"),
            "sourceRunId": str(source_state.get("currentSourceRunBinding", {}).get("currentSourceRunId") or ""),
            "dataFingerprint": source_state.get("dataFingerprint"),
            "schemaFingerprint": source_state.get("schemaFingerprint"),
            "relationshipFingerprint": source_state.get("relationshipPath", {}).get("fingerprint") or "",
            "domainPackFingerprint": source_state.get("domainPackFingerprint"),
            "workspaceManifestFingerprint": str(source_state.get("workspaceManifest", {}).get("fingerprint") or ""),
        }
        comparisons = {
            "sourceFingerprint": "source-changed",
            "sourceRunId": "source-run-changed",
            "dataFingerprint": "data-changed",
            "schemaFingerprint": "schema-changed",
            "relationshipFingerprint": "relationship-changed",
            "domainPackFingerprint": "domain-pack-changed",
            "workspaceManifestFingerprint": "workspace-manifest-changed",
        }
        for field, code in comparisons.items():
            if str(contract.get(field) or "") != str(current_contract.get(field) or ""):
                add(code, contract.get(field), current_contract.get(field))

    unit = get_analysis_unit(connection, workspace_id, publication["unitKey"])
    if not unit:
        add("analysis-unit-missing")
    else:
        if str(unit.get("definitionFingerprint") or "") != str(contract.get("analysisUnitDefinitionFingerprint") or ""):
            add("analysis-unit-changed", contract.get("analysisUnitDefinitionFingerprint"), unit.get("definitionFingerprint"))
        if str(unit.get("resultFingerprint") or "") != str(contract.get("resultFingerprint") or ""):
            add("analysis-unit-changed", contract.get("resultFingerprint"), unit.get("resultFingerprint"))
        unit_state = analysis_unit_consumer_state(connection, workspace_id, unit)
        if str(unit.get("status") or "") != "ready" or not unit_state.get("usable"):
            add("analysis-unit-not-current", "ready/current", unit_state.get("blockers"))

    if current_skill_fingerprint is not None:
        normalized = str(current_skill_fingerprint or "").strip() or NONE_SKILL_FINGERPRINT
        if normalized != str(contract.get("skillFingerprint") or ""):
            add("skill-changed", contract.get("skillFingerprint"), normalized)
    return reasons


def evaluate_reviewed_publication(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    publication_key: str,
    current_skill_fingerprint: str | None = None,
) -> dict[str, Any]:
    row = _publication_row(connection, workspace_id, publication_key)
    if not row:
        raise ValueError("Unknown reviewed publication in the active workspace")
    publication = _publication_payload(row)
    ledger = verify_evidence_ledger(connection, workspace_id=workspace_id, publication_key=publication_key)
    drift = _drift_reason_details(
        connection,
        publication=publication,
        current_skill_fingerprint=current_skill_fingerprint,
    )
    publication_integrity_failed = any(
        item["code"] in {"content-changed", "input-contract-changed"}
        for item in drift
    )
    if not ledger["ok"] or publication_integrity_failed:
        drift.insert(0, {"code": "ledger-integrity-failed", "expected": publication["ledgerHeadHash"], "current": ledger["headHash"]})
        effective_status = "integrity_failed"
    elif publication["status"] == "deprecated":
        effective_status = "deprecated"
    elif drift:
        effective_status = "stale"
    else:
        effective_status = "current"
    return {
        **publication,
        "status": effective_status,
        "storedStatus": publication["status"],
        "ledger": ledger,
        "drift": {
            "status": "current" if not drift else "drifted",
            "reasons": drift,
            "reasonCodes": [item["code"] for item in drift],
        },
        "canSupportCurrentDecision": effective_status == "current",
        "readOnly": True,
    }


def refresh_reviewed_publication_status(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    publication_key: str,
    now_iso: Callable[[], str],
    current_skill_fingerprint: str | None = None,
) -> dict[str, Any]:
    evaluated = evaluate_reviewed_publication(
        connection,
        workspace_id=workspace_id,
        publication_key=publication_key,
        current_skill_fingerprint=current_skill_fingerprint,
    )
    if evaluated["storedStatus"] != "deprecated":
        connection.execute(
            "UPDATE reviewed_publications SET status = ?, updated_at = ? WHERE workspace_id = ? AND publication_key = ?",
            (evaluated["status"], now_iso(), workspace_id, publication_key),
        )
    return evaluated


def deprecate_reviewed_publication(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    publication_key: str,
    expected_head_hash: str,
    reason: str,
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    row = _publication_row(connection, workspace_id, publication_key)
    if not row:
        raise ValueError("Unknown reviewed publication in the active workspace")
    publication = _publication_payload(row)
    if publication["status"] == "deprecated":
        return {"publication": publication, "deprecated": False}
    normalized_reason = _validate_public_text(reason, label="Deprecation reason", maximum=500)
    ledger = verify_evidence_ledger(connection, workspace_id=workspace_id, publication_key=publication_key)
    if not ledger["ok"]:
        raise ValueError("Cannot append to a damaged evidence ledger")
    if not connection.in_transaction:
        raise RuntimeError("Reviewed publication writes require the caller to hold BEGIN IMMEDIATE")
    timestamp = now_iso()
    entry = _append_ledger_entry(
        connection,
        workspace_id=workspace_id,
        publication_key=publication_key,
        kind="publication_deprecated",
        payload_fingerprint=fingerprint({"reason": normalized_reason, "status": "deprecated"}),
        evidence_refs=[{"type": "reviewedPublication", "publicationKey": publication_key}],
        created_at=timestamp,
        expected_head_hash=expected_head_hash,
    )
    connection.execute(
        """
        UPDATE reviewed_publications
        SET status = 'deprecated', ledger_head_hash = ?, updated_at = ?, deprecated_at = ?, deprecation_reason = ?
        WHERE workspace_id = ? AND publication_key = ?
        """,
        (entry["entryHash"], timestamp, timestamp, normalized_reason, workspace_id, publication_key),
    )
    saved = _publication_row(connection, workspace_id, publication_key)
    return {"publication": _publication_payload(saved), "ledgerEntry": entry, "deprecated": True}


def tombstone_reviewed_publication(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    publication_key: str,
    expected_head_hash: str,
    reason: str,
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    """Append a workspace-lifecycle tombstone without erasing audit history."""
    row = _publication_row(connection, workspace_id, publication_key)
    if not row:
        raise ValueError("Unknown reviewed publication in the active workspace")
    publication = _publication_payload(row)
    if publication["deprecationReason"].startswith("Tombstoned:"):
        return {"publication": publication, "tombstoned": False}
    normalized_reason = _validate_public_text(reason, label="Tombstone reason", maximum=500)
    ledger = verify_evidence_ledger(connection, workspace_id=workspace_id, publication_key=publication_key)
    if not ledger["ok"]:
        raise ValueError("Cannot append to a damaged evidence ledger")
    if not connection.in_transaction:
        raise RuntimeError("Reviewed publication writes require the caller to hold BEGIN IMMEDIATE")
    timestamp = now_iso()
    entry = _append_ledger_entry(
        connection,
        workspace_id=workspace_id,
        publication_key=publication_key,
        kind="publication_tombstoned",
        payload_fingerprint=fingerprint({"reason": normalized_reason, "status": "deprecated", "tombstone": True}),
        evidence_refs=[{"type": "reviewedPublication", "publicationKey": publication_key}],
        created_at=timestamp,
        expected_head_hash=expected_head_hash,
    )
    connection.execute(
        """
        UPDATE reviewed_publications
        SET status = 'deprecated', ledger_head_hash = ?, updated_at = ?, deprecated_at = ?, deprecation_reason = ?
        WHERE workspace_id = ? AND publication_key = ?
        """,
        (entry["entryHash"], timestamp, timestamp, f"Tombstoned: {normalized_reason}", workspace_id, publication_key),
    )
    saved = _publication_row(connection, workspace_id, publication_key)
    return {"publication": _publication_payload(saved), "ledgerEntry": entry, "tombstoned": True}


def reviewed_publication_export(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    publication_key: str,
    current_skill_fingerprint: str | None = None,
    forensic: bool = False,
) -> dict[str, Any]:
    evaluated = evaluate_reviewed_publication(
        connection,
        workspace_id=workspace_id,
        publication_key=publication_key,
        current_skill_fingerprint=current_skill_fingerprint,
    )
    if evaluated["status"] == "integrity_failed" and not forensic:
        raise ValueError("Integrity-failed publication requires an explicit forensic export")
    return {
        "schema": "aibi-reviewed-publication-export/v1",
        "workspaceId": workspace_id,
        "publication": evaluated,
        "ledgerEntries": list_evidence_ledger(
            connection,
            workspace_id=workspace_id,
            publication_key=publication_key,
        ),
        "currentDecisionBasis": evaluated["status"] == "current",
        "forensic": bool(forensic),
    }


def list_reviewed_publications(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    status: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    clauses = ["workspace_id = ?"]
    params: list[Any] = [workspace_id]
    if status:
        if status not in PUBLICATION_STATUSES:
            raise ValueError(f"Unsupported reviewed publication status: {status}")
        clauses.append("status = ?")
        params.append(status)
    params.append(max(1, min(int(limit), 200)))
    rows = connection.execute(
        f"SELECT * FROM reviewed_publications WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT ?",
        params,
    ).fetchall()
    return [_publication_payload(row) for row in rows]
