from __future__ import annotations

import argparse
import json
import re
import sqlite3
from contextlib import closing
from typing import Any, Callable

from analysis_unit_service import analysis_unit_consumer_state, get_analysis_unit
from query_plan_receipt_service import get_query_receipt, query_receipt_binding_fingerprint
from reviewed_publication_service import (
    build_reviewed_publication_plan,
    ensure_reviewed_publication_schema,
    evaluate_reviewed_publication,
    fingerprint,
    publish_reviewed_artifact,
    stable_json,
)


DECISION_FRAMEWORK_SCHEMA = "aibi-decision-framework/v1"
DECISION_FRAMEWORK_PLAN_SCHEMA = "aibi-decision-framework-publication-plan/v1"
DECISION_FRAMEWORK_EXPORT_SCHEMA = "aibi-decision-framework-export/v1"
FRAMEWORK_TYPES = {"swot", "process"}
CLAIM_KINDS = {"evidence_fact", "user_judgment", "hypothesis"}
STORED_STATUSES = {"draft", "published"}
MAX_CLAIMS = 40
MAX_CLAIM_TEXT = 2_000
MAX_TITLE = 200
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_KEY = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")
_PATH_OR_SECRET = re.compile(
    r"(?:[A-Za-z]:[\\/]|(?<!:)//[^/\s]+/|(?<!:)\\\\[^\\\s]+\\|"
    r"bearer\s+[A-Za-z0-9._~+/-]+=*|(?:password|passwd|secret|token|api[_-]?key)\s*[:=]|"
    r"\bsk-[A-Za-z0-9_-]{12,})",
    re.I,
)

_STRUCTURES = {
    "swot": (
        ("strength", "优势", "Strengths"),
        ("weakness", "劣势", "Weaknesses"),
        ("opportunity", "机会", "Opportunities"),
        ("threat", "威胁", "Threats"),
    ),
    "process": (
        ("input", "输入", "Input"),
        ("observation", "观察", "Observation"),
        ("decision", "决策", "Decision"),
    ),
}


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


def _safe_text(value: Any, *, label: str, maximum: int, required: bool = True) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise ValueError(f"{label} is required")
    if len(text) > maximum:
        raise ValueError(f"{label} must be at most {maximum} characters")
    if text and _PATH_OR_SECRET.search(text):
        raise ValueError(f"{label} contains a path or credential-like value")
    return text


def _framework_type(value: Any) -> str:
    normalized = str(value or "").strip().casefold()
    if normalized not in FRAMEWORK_TYPES:
        raise ValueError(f"Unsupported decision framework type: {value}")
    return normalized


def _structure(framework_type: str) -> dict[str, Any]:
    return {
        "schema": "aibi-decision-framework-structure/v1",
        "type": framework_type,
        "sections": [
            {"key": key, "label": {"zh": zh, "en": en}, "claimKeys": []}
            for key, zh, en in _STRUCTURES[framework_type]
        ],
    }


def ensure_decision_framework_schema(connection: sqlite3.Connection) -> None:
    # Framework publication is deliberately an adapter over the reviewed
    # publication boundary. Keep its schema available without creating a
    # second publication or ledger implementation.
    ensure_reviewed_publication_schema(connection)
    statements = (
        """
        CREATE TABLE IF NOT EXISTS decision_frameworks (
          framework_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          request_key TEXT NOT NULL,
          creation_fingerprint TEXT NOT NULL,
          unit_key TEXT NOT NULL,
          query_receipt_key TEXT NOT NULL,
          memory_key TEXT NOT NULL,
          framework_type TEXT NOT NULL,
          title TEXT NOT NULL,
          status TEXT NOT NULL,
          structure_json TEXT NOT NULL,
          claims_json TEXT NOT NULL,
          evidence_binding_json TEXT NOT NULL,
          evidence_fingerprint TEXT NOT NULL,
          content_fingerprint TEXT NOT NULL,
          revision INTEGER NOT NULL,
          publication_key TEXT NOT NULL DEFAULT '',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          published_at TEXT,
          PRIMARY KEY(workspace_id, framework_key),
          UNIQUE(workspace_id, request_key)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_decision_frameworks_workspace_unit ON decision_frameworks(workspace_id, unit_key, updated_at)",
        "CREATE INDEX IF NOT EXISTS idx_decision_frameworks_workspace_status ON decision_frameworks(workspace_id, status, updated_at)",
    )
    for statement in statements:
        connection.execute(statement)


def _current_evidence(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    unit_key: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    unit = get_analysis_unit(connection, workspace_id, unit_key)
    if not unit:
        raise ValueError("Unknown Analysis Unit in the active workspace")
    receipt_key = str(unit.get("queryReceiptKey") or "")
    receipt = get_query_receipt(connection, workspace_id, receipt_key) if receipt_key else None
    if not receipt or str(receipt.get("status") or "") != "executed":
        raise ValueError("Decision framework evidence requires an executed Query Receipt")
    state = analysis_unit_consumer_state(connection, workspace_id, unit)
    if str(unit.get("status") or "") != "ready" or not state.get("usable"):
        blockers = ", ".join(state.get("blockers") or ["analysis-unit-not-current"])
        raise ValueError(f"Decision framework evidence requires a current ready Analysis Unit: {blockers}")
    source = receipt.get("source") if isinstance(receipt.get("source"), dict) else {}
    if str(source.get("workspaceId") or "") != workspace_id:
        raise ValueError("Decision framework evidence belongs to another workspace")
    binding = {
        "schema": "aibi-decision-framework-evidence-binding/v1",
        "workspaceId": workspace_id,
        "unitKey": unit_key,
        "unitDefinitionFingerprint": str(unit.get("definitionFingerprint") or ""),
        "resultFingerprint": str(unit.get("resultFingerprint") or ""),
        "queryReceiptKey": receipt_key,
        "queryReceiptBindingFingerprint": query_receipt_binding_fingerprint(receipt),
        "sourceRunId": str(source.get("currentSourceRunId") or ""),
        "sourceFingerprint": str(source.get("sourceFingerprint") or ""),
        "dataFingerprint": str(source.get("dataFingerprint") or ""),
        "schemaFingerprint": str(source.get("schemaFingerprint") or ""),
        "relationshipFingerprint": str(source.get("relationshipPathFingerprint") or ""),
        "domainPackFingerprint": str(receipt.get("domainPackFingerprint") or ""),
    }
    binding["fingerprint"] = fingerprint(binding)
    return unit, receipt, binding


def _memory_key(connection: sqlite3.Connection, workspace_id: str, receipt_key: str) -> str:
    row = connection.execute(
        """
        SELECT memory_key FROM confirmed_plan_memories
        WHERE workspace_id = ? AND query_receipt_key = ? AND status = 'confirmed'
        ORDER BY confirmed_at DESC, updated_at DESC LIMIT 1
        """,
        (workspace_id, receipt_key),
    ).fetchone()
    return str(row["memory_key"] or "") if row else ""


def _evidence_refs(binding: dict[str, Any]) -> list[dict[str, Any]]:
    return [{
        "type": "queryPlanReceipt",
        "receiptKey": binding["queryReceiptKey"],
        "unitKey": binding["unitKey"],
        "resultFingerprint": binding["resultFingerprint"],
    }]


def _number(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return format(value, ".12g")
    return str(value)


def _candidate_texts(unit: dict[str, Any]) -> list[str]:
    calculation = unit.get("calculation") if isinstance(unit.get("calculation"), dict) else {}
    shape = unit.get("shape") if isinstance(unit.get("shape"), dict) else {}
    grain = unit.get("grain") if isinstance(unit.get("grain"), dict) else {}
    measures = grain.get("measures") if isinstance(grain.get("measures"), list) else []
    measure_binding = measures[0] if measures and isinstance(measures[0], dict) else {}
    measure = str(measure_binding.get("field") or shape.get("measureColumn") or unit.get("title") or "value")
    kind = str(unit.get("kind") or "")
    values: list[str] = []
    if kind == "metric" and calculation.get("value") is not None:
        values.append(f"{measure} = {_number(calculation.get('value'))}")
    elif kind == "comparison":
        for label, item in (("max", calculation.get("maximum")), ("min", calculation.get("minimum"))):
            if isinstance(item, dict) and item.get("value") is not None:
                bilingual_label = "最大值 / maximum" if label == "max" else "最小值 / minimum"
                values.append(f"{measure} · {bilingual_label}: {item.get('label')} = {_number(item.get('value'))}")
    elif kind == "trend":
        first, last = calculation.get("first"), calculation.get("last")
        if isinstance(first, dict) and isinstance(last, dict):
            values.append(
                f"{measure}: {first.get('label')} {_number(first.get('value'))} → "
                f"{last.get('label')} {_number(last.get('value'))}; Δ {_number(calculation.get('absoluteChange'))}"
            )
    elif kind == "composition" and calculation.get("total") is not None:
        values.append(f"{measure} · 合计 / total = {_number(calculation.get('total'))}")
        shares = calculation.get("shares") if isinstance(calculation.get("shares"), list) else []
        if shares:
            largest = max(
                (item for item in shares if isinstance(item, dict) and item.get("share") is not None),
                key=lambda item: float(item["share"]),
                default=None,
            )
            if largest:
                values.append(
                    f"{measure} · 最大已观察占比 / largest observed share: {largest.get('label')} = "
                    f"{_number(float(largest['share']) * 100)}%"
                )
    elif kind == "ranking":
        ranks = calculation.get("ranks") if isinstance(calculation.get("ranks"), list) else []
        for item in ranks[:3]:
            if isinstance(item, dict):
                values.append(f"{measure} #{item.get('rank')}: {item.get('label')} = {_number(item.get('value'))}")
    elif kind == "anomaly":
        values.append(f"{measure} · 已观察点 / observed points = {_number(calculation.get('pointCount'))}")
        anomalies = calculation.get("anomalies") if isinstance(calculation.get("anomalies"), list) else []
        values.append(f"{measure} |z-score| ≥ 2 observed points = {len(anomalies)}")
    return [value for value in values if value.strip()][:5]


def _claim_fingerprint(claim: dict[str, Any]) -> str:
    material = {
        "claimKey": claim["claimKey"],
        "category": claim["category"],
        "text": claim["text"],
        "claimKind": claim["claimKind"],
        "evidenceRefs": claim["evidenceRefs"],
        "author": claim["author"],
        "status": claim["status"],
        "verificationRequirement": claim.get("verificationRequirement", ""),
    }
    return fingerprint(material)


def _candidate_claims(unit: dict[str, Any], binding: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    for index, text in enumerate(_candidate_texts(unit)):
        key_material = {"binding": binding["fingerprint"], "index": index, "text": text}
        claim = {
            "claimKey": f"claim_{fingerprint(key_material)[:20]}",
            "category": "unassigned",
            "text": text,
            "claimKind": "evidence_fact",
            "evidenceRefs": _evidence_refs(binding),
            "author": "system-evidence-candidate",
            "status": "candidate",
            "verificationRequirement": "",
        }
        claim["contentFingerprint"] = _claim_fingerprint(claim)
        candidates.append(claim)
    return candidates


def _normalize_evidence_fact_refs(value: Any, binding: dict[str, Any]) -> list[dict[str, Any]]:
    refs = value if isinstance(value, list) else []
    matching = [
        item for item in refs
        if isinstance(item, dict)
        and str(item.get("type") or "") == "queryPlanReceipt"
        and str(item.get("receiptKey") or "") == binding["queryReceiptKey"]
        and str(item.get("unitKey") or "") == binding["unitKey"]
        and str(item.get("resultFingerprint") or "") == binding["resultFingerprint"]
    ]
    if not matching:
        raise ValueError("evidence_fact requires the current executed Query Receipt and Analysis Unit binding")
    return _evidence_refs(binding)


def _normalize_claims(
    claims: Any,
    *,
    framework_key: str,
    framework_type: str,
    binding: dict[str, Any],
    allowed_evidence_texts: set[str],
) -> list[dict[str, Any]]:
    if not isinstance(claims, list):
        raise ValueError("Decision framework claims must be a JSON array")
    if len(claims) > MAX_CLAIMS:
        raise ValueError(f"Decision framework supports at most {MAX_CLAIMS} claims")
    categories = {item[0] for item in _STRUCTURES[framework_type]}
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(claims):
        if not isinstance(raw, dict):
            raise ValueError("Each decision framework claim must be a JSON object")
        kind = str(raw.get("claimKind") or "").strip()
        if kind not in CLAIM_KINDS:
            raise ValueError(f"Unsupported decision claim kind: {kind}")
        category = str(raw.get("category") or "").strip()
        if category not in categories:
            raise ValueError(f"Unsupported {framework_type} claim category: {category}")
        text = _safe_text(raw.get("text"), label="Decision claim text", maximum=MAX_CLAIM_TEXT)
        supplied_key = str(raw.get("claimKey") or "").strip()
        if supplied_key and not _SAFE_KEY.fullmatch(supplied_key):
            raise ValueError("Decision claim key contains unsupported characters")
        claim_key = supplied_key or f"claim_{fingerprint({'frameworkKey': framework_key, 'index': index, 'text': text})[:20]}"
        if claim_key in seen:
            raise ValueError("Decision claim keys must be unique")
        seen.add(claim_key)
        verification = _safe_text(
            raw.get("verificationRequirement"),
            label="Hypothesis verification requirement",
            maximum=1_000,
            required=kind == "hypothesis",
        )
        if kind == "evidence_fact":
            if text not in allowed_evidence_texts:
                raise ValueError("evidence_fact text must match a current generated evidence candidate")
            evidence_refs = _normalize_evidence_fact_refs(raw.get("evidenceRefs"), binding)
            author = "system-evidence-candidate" if raw.get("author") == "system-evidence-candidate" else "local-user"
            status = "supported"
            verification = ""
        elif kind == "user_judgment":
            evidence_refs = []
            author = "local-user"
            status = "user_asserted"
            verification = ""
        else:
            evidence_refs = []
            author = "local-user"
            status = "needs_validation"
        claim = {
            "claimKey": claim_key,
            "category": category,
            "text": text,
            "claimKind": kind,
            "evidenceRefs": evidence_refs,
            "author": author,
            "status": status,
            "verificationRequirement": verification,
        }
        claim["contentFingerprint"] = _claim_fingerprint(claim)
        normalized.append(claim)
    return normalized


def _structure_with_claims(framework_type: str, claims: list[dict[str, Any]]) -> dict[str, Any]:
    structure = _structure(framework_type)
    by_category: dict[str, list[str]] = {item[0]: [] for item in _STRUCTURES[framework_type]}
    for claim in claims:
        by_category[claim["category"]].append(claim["claimKey"])
    for section in structure["sections"]:
        section["claimKeys"] = by_category[section["key"]]
    return structure


def _content_fingerprint(
    *,
    framework_key: str,
    framework_type: str,
    title: str,
    unit_key: str,
    structure: dict[str, Any],
    claims: list[dict[str, Any]],
    evidence_fingerprint: str,
) -> str:
    return fingerprint({
        "schema": DECISION_FRAMEWORK_SCHEMA,
        "frameworkKey": framework_key,
        "type": framework_type,
        "title": title,
        "unitKey": unit_key,
        "structure": structure,
        "claims": claims,
        "evidenceFingerprint": evidence_fingerprint,
    })


def _row(connection: sqlite3.Connection, workspace_id: str, framework_key: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM decision_frameworks WHERE workspace_id = ? AND framework_key = ?",
        (workspace_id, framework_key),
    ).fetchone()


def _publication_summary(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    publication_key: str,
) -> dict[str, Any] | None:
    if not publication_key:
        return None
    try:
        publication = evaluate_reviewed_publication(
            connection,
            workspace_id=workspace_id,
            publication_key=publication_key,
        )
    except ValueError as error:
        return {
            "publicationKey": publication_key,
            "status": "integrity_failed",
            "canSupportCurrentDecision": False,
            "drift": {"status": "drifted", "reasonCodes": ["publication-missing"], "reasons": []},
            "error": str(error),
        }
    return {
        "publicationKey": publication["publicationKey"],
        "status": publication["status"],
        "contentFingerprint": publication["contentFingerprint"],
        "inputFingerprint": publication["inputFingerprint"],
        "ledgerHeadHash": publication["ledgerHeadHash"],
        "canSupportCurrentDecision": publication["canSupportCurrentDecision"],
        "drift": publication["drift"],
    }


def _unload_stale_facts(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            **claim,
            "text": "",
            "status": "stale",
            "numberUnloaded": True,
            "staleLabel": "Evidence changed; refresh the framework before viewing this fact.",
        }
        if claim.get("claimKind") == "evidence_fact"
        else claim
        for claim in claims
    ]


def _row_payload(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    workspace_id = str(row["workspace_id"])
    claims = [item for item in _json_list(row["claims_json"]) if isinstance(item, dict)]
    structure = _json_object(row["structure_json"])
    stored_binding = _json_object(row["evidence_binding_json"])
    blockers: list[str] = []
    integrity_failed = False
    stored_binding_material = {key: value for key, value in stored_binding.items() if key != "fingerprint"}
    if (
        fingerprint(stored_binding_material) != str(stored_binding.get("fingerprint") or "")
        or str(stored_binding.get("fingerprint") or "") != str(row["evidence_fingerprint"])
    ):
        blockers.append("framework-evidence-binding-integrity-failed")
        integrity_failed = True
    expected_content_fingerprint = _content_fingerprint(
        framework_key=str(row["framework_key"]),
        framework_type=str(row["framework_type"]),
        title=str(row["title"]),
        unit_key=str(row["unit_key"]),
        structure=structure,
        claims=claims,
        evidence_fingerprint=str(row["evidence_fingerprint"]),
    )
    if expected_content_fingerprint != str(row["content_fingerprint"]):
        blockers.append("framework-content-integrity-failed")
        integrity_failed = True
    current_binding: dict[str, Any] | None = None
    try:
        unit, _receipt, current_binding = _current_evidence(
            connection,
            workspace_id=workspace_id,
            unit_key=str(row["unit_key"]),
        )
        if current_binding["fingerprint"] != str(row["evidence_fingerprint"]):
            blockers.append("framework-evidence-binding-drifted")
    except ValueError as error:
        unit = None
        blockers.append(str(error))
    publication = _publication_summary(
        connection,
        workspace_id=workspace_id,
        publication_key=str(row["publication_key"] or ""),
    )
    if publication and publication.get("status") != "current":
        blockers.extend(publication.get("drift", {}).get("reasonCodes") or ["publication-not-current"])
    current = not blockers
    stored_status = str(row["status"])
    if integrity_failed or (publication and publication.get("status") == "integrity_failed"):
        effective_status = "integrity_failed"
    elif publication and publication.get("status") == "deprecated":
        effective_status = "deprecated"
    elif not current:
        effective_status = "stale"
    else:
        effective_status = stored_status
    visible_claims = claims if current else _unload_stale_facts(claims)
    candidates = _candidate_claims(unit, current_binding) if current and stored_status == "draft" and unit and current_binding else []
    facts = sum(1 for claim in claims if claim.get("claimKind") == "evidence_fact")
    return {
        "schema": DECISION_FRAMEWORK_SCHEMA,
        "frameworkKey": row["framework_key"],
        "workspaceId": workspace_id,
        "unitKey": row["unit_key"],
        "queryReceiptKey": row["query_receipt_key"],
        "memoryKey": row["memory_key"],
        "type": row["framework_type"],
        "title": row["title"],
        "status": effective_status,
        "storedStatus": stored_status,
        "structure": structure,
        "claims": visible_claims,
        "evidenceCandidates": candidates,
        "evidenceBinding": stored_binding,
        "evidenceFingerprint": row["evidence_fingerprint"],
        "contentFingerprint": row["content_fingerprint"],
        "revision": int(row["revision"]),
        "publicationKey": row["publication_key"] or None,
        "publication": publication,
        "freshness": {
            "status": "current" if current else "stale",
            "current": current,
            "blockers": list(dict.fromkeys(blockers)),
            "evidenceFactsUnloaded": not current and facts > 0,
        },
        "claimCounts": {
            "evidenceFact": facts,
            "userJudgment": sum(1 for claim in claims if claim.get("claimKind") == "user_judgment"),
            "hypothesis": sum(1 for claim in claims if claim.get("claimKind") == "hypothesis"),
        },
        "canEdit": current and stored_status == "draft",
        "canPublish": current and stored_status == "draft" and bool(row["memory_key"]) and facts > 0,
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "publishedAt": row["published_at"],
    }


def get_decision_framework(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    framework_key: str,
) -> dict[str, Any] | None:
    ensure_decision_framework_schema(connection)
    row = _row(connection, workspace_id, framework_key)
    return _row_payload(connection, row) if row else None


def list_decision_frameworks(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    unit_key: str | None = None,
    limit: int = 30,
) -> list[dict[str, Any]]:
    ensure_decision_framework_schema(connection)
    clauses = ["workspace_id = ?"]
    params: list[Any] = [workspace_id]
    if unit_key:
        clauses.append("unit_key = ?")
        params.append(unit_key)
    params.append(max(1, min(int(limit), 100)))
    rows = connection.execute(
        f"SELECT * FROM decision_frameworks WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT ?",
        params,
    ).fetchall()
    summaries = []
    for row in rows:
        payload = _row_payload(connection, row)
        summaries.append({
            key: value for key, value in payload.items()
            if key not in {"claims", "evidenceCandidates", "structure", "evidenceBinding"}
        })
    return summaries


def create_decision_framework_draft(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    unit_key: str,
    framework_type: str,
    title: str,
    request_key: str,
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    ensure_decision_framework_schema(connection)
    if not connection.in_transaction:
        raise RuntimeError("Decision framework writes require the caller to hold BEGIN IMMEDIATE")
    normalized_type = _framework_type(framework_type)
    normalized_title = _safe_text(title, label="Decision framework title", maximum=MAX_TITLE)
    normalized_request = str(request_key or "").strip()
    if not 8 <= len(normalized_request) <= 160 or not _SAFE_KEY.fullmatch(normalized_request):
        raise ValueError("Decision framework requestKey must contain 8-160 safe characters")
    unit, _receipt, binding = _current_evidence(
        connection,
        workspace_id=workspace_id,
        unit_key=unit_key,
    )
    creation_fingerprint = fingerprint({
        "workspaceId": workspace_id,
        "unitKey": unit_key,
        "type": normalized_type,
        "title": normalized_title,
    })
    existing = connection.execute(
        "SELECT * FROM decision_frameworks WHERE workspace_id = ? AND request_key = ?",
        (workspace_id, normalized_request),
    ).fetchone()
    if existing:
        if str(existing["creation_fingerprint"]) != creation_fingerprint:
            raise ValueError("Decision framework requestKey conflicts with different input")
        return _row_payload(connection, existing)
    framework_key = f"decision_framework_{fingerprint({'workspaceId': workspace_id, 'requestKey': normalized_request})[:20]}"
    structure = _structure(normalized_type)
    claims: list[dict[str, Any]] = []
    content_fingerprint = _content_fingerprint(
        framework_key=framework_key,
        framework_type=normalized_type,
        title=normalized_title,
        unit_key=unit_key,
        structure=structure,
        claims=claims,
        evidence_fingerprint=binding["fingerprint"],
    )
    timestamp = now_iso()
    memory_key = _memory_key(connection, workspace_id, binding["queryReceiptKey"])
    connection.execute(
        """
        INSERT INTO decision_frameworks(
          framework_key, workspace_id, request_key, creation_fingerprint, unit_key,
          query_receipt_key, memory_key, framework_type, title, status, structure_json,
          claims_json, evidence_binding_json, evidence_fingerprint, content_fingerprint,
          revision, publication_key, created_at, updated_at, published_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', ?, '[]', ?, ?, ?, 1, '', ?, ?, NULL)
        """,
        (
            framework_key,
            workspace_id,
            normalized_request,
            creation_fingerprint,
            unit_key,
            binding["queryReceiptKey"],
            memory_key,
            normalized_type,
            normalized_title,
            stable_json(structure),
            stable_json(binding),
            binding["fingerprint"],
            content_fingerprint,
            timestamp,
            timestamp,
        ),
    )
    return _row_payload(connection, _row(connection, workspace_id, framework_key))


def save_decision_framework_draft(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    framework_key: str,
    title: str,
    claims: Any,
    expected_content_fingerprint: str,
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    ensure_decision_framework_schema(connection)
    if not connection.in_transaction:
        raise RuntimeError("Decision framework writes require the caller to hold BEGIN IMMEDIATE")
    row = _row(connection, workspace_id, framework_key)
    if not row:
        raise ValueError("Unknown decision framework in the active workspace")
    if str(row["status"]) != "draft":
        raise ValueError("Published decision frameworks are immutable; create a new draft")
    if str(expected_content_fingerprint or "") != str(row["content_fingerprint"]):
        raise ValueError("Decision framework changed; reload before saving")
    unit, _receipt, binding = _current_evidence(
        connection,
        workspace_id=workspace_id,
        unit_key=str(row["unit_key"]),
    )
    if binding["fingerprint"] != str(row["evidence_fingerprint"]):
        raise ValueError("Decision framework evidence drifted; create a new draft from current evidence")
    normalized_title = _safe_text(title, label="Decision framework title", maximum=MAX_TITLE)
    normalized_claims = _normalize_claims(
        claims,
        framework_key=framework_key,
        framework_type=str(row["framework_type"]),
        binding=binding,
        allowed_evidence_texts=set(_candidate_texts(unit)),
    )
    structure = _structure_with_claims(str(row["framework_type"]), normalized_claims)
    content_fingerprint = _content_fingerprint(
        framework_key=framework_key,
        framework_type=str(row["framework_type"]),
        title=normalized_title,
        unit_key=str(row["unit_key"]),
        structure=structure,
        claims=normalized_claims,
        evidence_fingerprint=binding["fingerprint"],
    )
    changed = content_fingerprint != str(row["content_fingerprint"])
    if changed:
        connection.execute(
            """
            UPDATE decision_frameworks
            SET title = ?, structure_json = ?, claims_json = ?, content_fingerprint = ?,
                revision = revision + 1, updated_at = ?
            WHERE workspace_id = ? AND framework_key = ?
            """,
            (
                normalized_title,
                stable_json(structure),
                stable_json(normalized_claims),
                content_fingerprint,
                now_iso(),
                workspace_id,
                framework_key,
            ),
        )
    payload = _row_payload(connection, _row(connection, workspace_id, framework_key))
    return {**payload, "changed": changed}


def _publication_content(framework: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifactType": "decision-framework",
        "framework": {
            "schema": DECISION_FRAMEWORK_SCHEMA,
            "frameworkKey": framework["frameworkKey"],
            "type": framework["type"],
            "title": framework["title"],
            "unitKey": framework["unitKey"],
            "queryReceiptKey": framework["queryReceiptKey"],
            "structure": framework["structure"],
            "claims": framework["claims"],
            "contentFingerprint": framework["contentFingerprint"],
        },
    }


def build_decision_framework_publication_plan(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    framework_key: str,
) -> dict[str, Any]:
    framework = get_decision_framework(
        connection,
        workspace_id=workspace_id,
        framework_key=framework_key,
    )
    if not framework:
        raise ValueError("Unknown decision framework in the active workspace")
    if framework["status"] not in {"draft", "published"} or not framework["freshness"]["current"]:
        raise ValueError("Only a current decision framework can be published")
    if not framework["claimCounts"]["evidenceFact"]:
        raise ValueError("Decision framework publication requires at least one current evidence_fact")
    if not framework["memoryKey"]:
        raise ValueError("Decision framework publication requires an explicitly Confirmed Plan Memory")
    reviewed_plan = build_reviewed_publication_plan(
        connection,
        workspace_id=workspace_id,
        memory_key=framework["memoryKey"],
        unit_key=framework["unitKey"],
        title=framework["title"],
        content=_publication_content(framework),
    )
    plan = {
        "schema": DECISION_FRAMEWORK_PLAN_SCHEMA,
        "workspaceId": workspace_id,
        "frameworkKey": framework_key,
        "frameworkContentFingerprint": framework["contentFingerprint"],
        "reviewedPublicationPlan": reviewed_plan,
        "requiresConfirmation": True,
    }
    plan["planFingerprint"] = fingerprint(plan)
    return plan


def publish_decision_framework(
    connection: sqlite3.Connection,
    *,
    plan: dict[str, Any],
    expected_plan_fingerprint: str,
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    if not connection.in_transaction:
        raise RuntimeError("Decision framework publication requires the caller to hold BEGIN IMMEDIATE")
    if str(plan.get("schema") or "") != DECISION_FRAMEWORK_PLAN_SCHEMA:
        raise ValueError("Unsupported decision framework publication plan schema")
    actual = fingerprint({key: value for key, value in plan.items() if key != "planFingerprint"})
    if str(plan.get("planFingerprint") or "") != actual:
        raise ValueError("Decision framework publication plan changed after preview")
    if str(expected_plan_fingerprint or "") != actual:
        raise ValueError("Decision framework confirmation fingerprint does not match the preview")
    workspace_id = str(plan.get("workspaceId") or "")
    framework_key = str(plan.get("frameworkKey") or "")
    current_plan = build_decision_framework_publication_plan(
        connection,
        workspace_id=workspace_id,
        framework_key=framework_key,
    )
    if current_plan["planFingerprint"] != actual:
        raise ValueError("Decision framework content or evidence drifted after preview")
    reviewed_plan = plan.get("reviewedPublicationPlan") if isinstance(plan.get("reviewedPublicationPlan"), dict) else {}
    published = publish_reviewed_artifact(
        connection,
        plan=reviewed_plan,
        expected_plan_fingerprint=str(reviewed_plan.get("planFingerprint") or ""),
        now_iso=now_iso,
    )
    publication = published["publication"]
    timestamp = now_iso()
    connection.execute(
        """
        UPDATE decision_frameworks
        SET status = 'published', publication_key = ?, published_at = COALESCE(published_at, ?), updated_at = ?
        WHERE workspace_id = ? AND framework_key = ?
        """,
        (publication["publicationKey"], timestamp, timestamp, workspace_id, framework_key),
    )
    return {
        "framework": _row_payload(connection, _row(connection, workspace_id, framework_key)),
        "publication": publication,
        "ledgerEntry": published.get("ledgerEntry"),
        "created": published.get("created", False),
    }


def export_decision_framework(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    framework_key: str,
) -> dict[str, Any]:
    framework = get_decision_framework(connection, workspace_id=workspace_id, framework_key=framework_key)
    if not framework:
        raise ValueError("Unknown decision framework in the active workspace")
    publication = framework.get("publication")
    return {
        "schema": DECISION_FRAMEWORK_EXPORT_SCHEMA,
        "workspaceId": workspace_id,
        "framework": framework,
        "publication": publication,
        "currentDecisionBasis": bool(
            framework.get("status") == "published"
            and publication
            and publication.get("canSupportCurrentDecision") is True
        ),
        "staleEvidenceFactsUnloaded": bool(framework.get("freshness", {}).get("evidenceFactsUnloaded")),
    }


def _parse_claims(value: str) -> list[Any]:
    try:
        parsed = json.loads(str(value or "[]"))
    except json.JSONDecodeError as error:
        raise ValueError("claims-json must be a JSON array") from error
    if not isinstance(parsed, list):
        raise ValueError("claims-json must be a JSON array")
    return parsed


def decision_framework_create_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    with closing(open_db()) as connection:
        if connection.in_transaction:
            connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        workspace_id = active_workspace_id(connection)
        framework = create_decision_framework_draft(
            connection,
            workspace_id=workspace_id,
            unit_key=args.unit,
            framework_type=args.framework_type,
            title=args.title,
            request_key=args.request_key,
            now_iso=now_iso,
        )
        connection.commit()
    return {"ok": True, "decisionFramework": framework}


def decision_framework_save_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    claims = _parse_claims(args.claims_json)
    with closing(open_db()) as connection:
        if connection.in_transaction:
            connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        workspace_id = active_workspace_id(connection)
        framework = save_decision_framework_draft(
            connection,
            workspace_id=workspace_id,
            framework_key=args.framework,
            title=args.title,
            claims=claims,
            expected_content_fingerprint=args.expected_content,
            now_iso=now_iso,
        )
        connection.commit()
    return {"ok": True, "decisionFramework": framework, "changed": framework.get("changed", False)}


def decision_frameworks_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with closing(open_db()) as connection:
        workspace_id = active_workspace_id(connection)
        if args.framework:
            framework = get_decision_framework(
                connection,
                workspace_id=workspace_id,
                framework_key=args.framework,
            )
            if not framework:
                raise ValueError("Unknown decision framework in the active workspace")
            return {"ok": True, "decisionFramework": framework}
        frameworks = list_decision_frameworks(
            connection,
            workspace_id=workspace_id,
            unit_key=args.unit or None,
            limit=args.limit,
        )
    return {"ok": True, "decisionFrameworks": frameworks, "count": len(frameworks)}


def decision_framework_publish_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    with closing(open_db()) as connection:
        if args.yes:
            if connection.in_transaction:
                connection.commit()
            connection.execute("BEGIN IMMEDIATE")
        workspace_id = active_workspace_id(connection)
        plan = build_decision_framework_publication_plan(
            connection,
            workspace_id=workspace_id,
            framework_key=args.framework,
        )
        if not args.yes:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "decisionFrameworkPlan": plan}
        result = publish_decision_framework(
            connection,
            plan=plan,
            expected_plan_fingerprint=args.expected_plan,
            now_iso=now_iso,
        )
        connection.commit()
    return {"ok": True, "confirmed": True, **result}


def decision_framework_export_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with closing(open_db()) as connection:
        workspace_id = active_workspace_id(connection)
        exported = export_decision_framework(
            connection,
            workspace_id=workspace_id,
            framework_key=args.framework,
        )
    return {"ok": True, "decisionFrameworkExport": exported}
