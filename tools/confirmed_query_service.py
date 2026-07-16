from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from contextlib import closing
from difflib import SequenceMatcher
from typing import Any, Callable

from query_plan_receipt_service import (
    current_query_receipt_source_state,
    get_query_receipt,
    query_receipt_binding_fingerprint,
)


RECALL_POLICY_SCHEMA = "aibi-hybrid-recall-policy/v1"
RECALL_RECEIPT_SCHEMA = "aibi-recall-receipt/v1"
CONFIRMED_PLAN_SCHEMA = "aibi-confirmed-plan-memory/v1"
RECALL_THRESHOLD = 0.55
AMBIGUITY_MARGIN = 0.03


def _query_key(workspace_id: str, action_key: str, receipt_key: str) -> str:
    material = f"{workspace_id}\x1f{action_key}\x1f{receipt_key}"
    return f"confirmed_query_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:20]}"


def _payload(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["chartSpec"] = json.loads(item.pop("chart_spec_json"))
    item["evidenceRefs"] = json.loads(item.pop("evidence_json"))
    return item


def _json_value(value: Any, fallback: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        parsed = json.loads(str(value or ""))
    except (TypeError, json.JSONDecodeError):
        return fallback
    return parsed if isinstance(parsed, type(fallback)) else fallback


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _memory_key(query_key: str) -> str:
    suffix = query_key.removeprefix("confirmed_query_")
    return f"plan_memory_{suffix}"


def _plan_signature(receipt: dict[str, Any]) -> dict[str, Any]:
    source = receipt.get("source") if isinstance(receipt.get("source"), dict) else {}
    selection = receipt.get("selection") if isinstance(receipt.get("selection"), dict) else {}
    semantic = selection.get("semanticPlan") if isinstance(selection.get("semanticPlan"), dict) else {}
    resolution = semantic.get("fieldResolution") if isinstance(semantic.get("fieldResolution"), dict) else {}
    selected = resolution.get("selected") if isinstance(resolution.get("selected"), list) else []
    fields = sorted({
        f"{str(item.get('tableKey') or '').strip()}.{str(item.get('field') or '').strip()}".strip(".")
        for item in selected
        if isinstance(item, dict) and str(item.get("field") or "").strip()
    })
    tables = source.get("tableKeys") if isinstance(source.get("tableKeys"), list) else []
    if not tables and source.get("tableKey"):
        tables = [source.get("tableKey")]
    groups = selection.get("groups") if isinstance(selection.get("groups"), list) else []
    if not groups and selection.get("group"):
        groups = [selection.get("group")]
    knowledge = selection.get("knowledgeRule") if isinstance(selection.get("knowledgeRule"), dict) else {}
    return {
        "tables": sorted({str(value).strip() for value in tables if str(value).strip()}),
        "fields": fields,
        "measure": str(selection.get("measure") or "").strip(),
        "groups": sorted({str(value).strip() for value in groups if str(value).strip()}),
        "aggregation": str(selection.get("aggregation") or "").strip().lower(),
        "knowledgeRule": ":".join(
            value for value in [str(knowledge.get("packId") or "").strip(), str(knowledge.get("ruleId") or "").strip()] if value
        ),
    }


def _memory_payload(row: sqlite3.Row, receipt: dict[str, Any] | None = None) -> dict[str, Any]:
    item = dict(row)
    plan = _json_value(item.pop("plan_json"), {})
    stored_signature = _json_value(item.pop("signature_json"), {})
    signature = stored_signature or (_plan_signature(receipt) if receipt else {})
    evidence = _json_value(item.pop("evidence_json"), [])
    return {
        "schema": CONFIRMED_PLAN_SCHEMA,
        "memoryKey": item["memory_key"],
        "workspaceId": item["workspace_id"],
        "queryKey": item["query_key"],
        "queryReceiptKey": item["query_receipt_key"],
        "question": item["question"],
        "status": item["status"],
        "plan": plan,
        "signature": signature,
        "planFingerprint": _fingerprint(plan),
        "bindingFingerprint": item["binding_fingerprint"],
        "evidenceRefs": evidence,
        "createdAt": item["created_at"],
        "updatedAt": item["updated_at"],
        "confirmedAt": item["confirmed_at"],
        "staleReason": item["stale_reason"],
    }


def _upsert_confirmed_plan_memory(
    connection: sqlite3.Connection,
    *,
    query: dict[str, Any],
    receipt: dict[str, Any],
    status: str,
    timestamp: str,
) -> dict[str, Any]:
    plan = receipt.get("selection") if isinstance(receipt.get("selection"), dict) else {}
    signature = _plan_signature(receipt)
    evidence = list(query.get("evidenceRefs") or []) + [
        {"type": "confirmedQuery", "queryKey": query["query_key"]},
        {"type": "queryPlanReceipt", "receiptKey": query["query_receipt_key"]},
    ]
    memory_key = _memory_key(str(query["query_key"]))
    connection.execute(
        """
        INSERT INTO confirmed_plan_memories(
          memory_key, workspace_id, query_key, query_receipt_key, question, status,
          plan_json, signature_json, binding_fingerprint, evidence_json,
          created_at, updated_at, confirmed_at, stale_reason
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '')
        ON CONFLICT(workspace_id, memory_key) DO UPDATE SET
          query_receipt_key = excluded.query_receipt_key,
          question = excluded.question,
          status = excluded.status,
          plan_json = excluded.plan_json,
          signature_json = excluded.signature_json,
          binding_fingerprint = excluded.binding_fingerprint,
          evidence_json = excluded.evidence_json,
          updated_at = excluded.updated_at,
          confirmed_at = excluded.confirmed_at,
          stale_reason = ''
        """,
        (
            memory_key,
            query["workspace_id"],
            query["query_key"],
            query["query_receipt_key"],
            query["question"],
            status,
            _canonical_json(plan),
            _canonical_json(signature),
            query_receipt_binding_fingerprint(receipt),
            _canonical_json(evidence),
            query.get("created_at") or timestamp,
            timestamp,
            timestamp if status == "confirmed" else query.get("confirmed_at"),
        ),
    )
    row = connection.execute(
        "SELECT * FROM confirmed_plan_memories WHERE workspace_id = ? AND memory_key = ?",
        (query["workspace_id"], memory_key),
    ).fetchone()
    return _memory_payload(row, receipt)


def _text_features(value: str) -> tuple[set[str], set[str]]:
    folded = str(value or "").casefold()
    words = set(re.findall(r"[a-z0-9_]+", folded))
    cjk = "".join(re.findall(r"[\u3400-\u9fff]", folded))
    grams = {cjk[index:index + 2] for index in range(max(0, len(cjk) - 1))}
    if len(cjk) == 1:
        grams.add(cjk)
    return words, grams


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _signature_values(signature: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for key in ("tables", "fields", "groups"):
        for value in signature.get(key) or []:
            if str(value).strip():
                values.add(f"{key}:{str(value).strip().casefold()}")
    for key in ("measure", "aggregation", "knowledgeRule"):
        value = str(signature.get(key) or "").strip().casefold()
        if value:
            values.add(f"{key}:{value}")
    return values


def _current_signature(semantic_plan: dict[str, Any] | None, explicit_table_key: str | None) -> dict[str, Any]:
    semantic = semantic_plan if isinstance(semantic_plan, dict) else {}
    resolution = semantic.get("fieldResolution") if isinstance(semantic.get("fieldResolution"), dict) else {}
    selected = resolution.get("selected") if isinstance(resolution.get("selected"), list) else []
    result = {
        "tables": sorted({
            str(item.get("tableKey") or "").strip()
            for item in selected
            if isinstance(item, dict) and str(item.get("tableKey") or "").strip()
        }),
        "fields": sorted({
            f"{str(item.get('tableKey') or '').strip()}.{str(item.get('field') or '').strip()}".strip(".")
            for item in selected
            if isinstance(item, dict) and str(item.get("field") or "").strip()
        }),
        "measure": "",
        "groups": [],
        "aggregation": "",
        "knowledgeRule": "",
    }
    if explicit_table_key and explicit_table_key not in result["tables"]:
        result["tables"].append(explicit_table_key)
        result["tables"].sort()
    for item in selected:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "")
        field = str(item.get("field") or "").strip()
        if role == "measure" and field and not result["measure"]:
            result["measure"] = field
        if role == "dimension" and field:
            result["groups"].append(field)
    result["groups"] = sorted(set(result["groups"]))
    return result


def _recall_receipt_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "schema": RECALL_RECEIPT_SCHEMA,
        "receiptKey": row["receipt_key"],
        "workspaceId": row["workspace_id"],
        "requestHash": row["request_hash"],
        "status": row["status"],
        "policy": _json_value(row["policy_json"], {}),
        "candidates": _json_value(row["candidates_json"], []),
        "returnedCandidates": _json_value(row["returned_json"], []),
        "planningBindingFingerprint": row["planning_binding_fingerprint"],
        "createdAt": row["created_at"],
    }


def _stored_binding_matches_receipt(stored: Any, receipt: dict[str, Any]) -> bool:
    stored_value = str(stored or "")
    source = receipt.get("source") if isinstance(receipt.get("source"), dict) else {}
    return stored_value in {
        query_receipt_binding_fingerprint(receipt),
        # Compatibility for candidates confirmed before the full binding contract.
        str(source.get("schemaFingerprint") or ""),
    }


def create_confirmed_query_candidate(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    action_key: str,
    action_payload: dict[str, Any],
    added_widget: dict[str, Any],
    now_iso: Callable[[], str],
) -> dict[str, Any] | None:
    receipt_key = str(action_payload.get("queryReceiptKey") or "").strip()
    if not receipt_key:
        return None
    receipt = get_query_receipt(connection, workspace_id, receipt_key)
    if not receipt or receipt.get("status") != "executed":
        return None
    source_state = current_query_receipt_source_state(connection, workspace_id, receipt)
    if not source_state.get("matchesReceipt"):
        return None
    source = receipt.get("source") if isinstance(receipt.get("source"), dict) else {}
    table_key = str(source.get("tableKey") or action_payload.get("tableKey") or "").strip()
    query_key = _query_key(workspace_id, action_key, receipt_key)
    timestamp = now_iso()
    evidence_refs = [
        {"type": "queryPlanReceipt", "receiptKey": receipt_key},
        {"type": "confirmedAction", "actionKey": action_key},
    ]
    question = str(action_payload.get("prompt") or receipt.get("request") or "").strip()
    fingerprint = query_receipt_binding_fingerprint(receipt)
    existing_rows = connection.execute(
        """
        SELECT * FROM confirmed_queries
        WHERE workspace_id = ? AND source_table_key = ? AND status IN ('candidate', 'confirmed')
        ORDER BY CASE status WHEN 'confirmed' THEN 0 ELSE 1 END, updated_at DESC
        """,
        (workspace_id, table_key),
    ).fetchall()
    existing = next((row for row in existing_rows if str(row["question"] or "").strip().casefold() == question.casefold()), None)
    if existing and existing["status"] == "confirmed" and _stored_binding_matches_receipt(existing["schema_fingerprint"], receipt):
        return _payload(existing)
    if existing and existing["status"] == "candidate":
        connection.execute(
            """
            UPDATE confirmed_queries
            SET query_receipt_key = ?, schema_fingerprint = ?, chart_spec_json = ?, evidence_json = ?,
                originating_action_key = ?, updated_at = ?, stale_reason = ''
            WHERE workspace_id = ? AND query_key = ?
            """,
            (
                receipt_key,
                fingerprint,
                json.dumps(added_widget, ensure_ascii=False),
                json.dumps(evidence_refs, ensure_ascii=False),
                action_key,
                timestamp,
                workspace_id,
                existing["query_key"],
            ),
        )
        refreshed = connection.execute(
            "SELECT * FROM confirmed_queries WHERE workspace_id = ? AND query_key = ?",
            (workspace_id, existing["query_key"]),
        ).fetchone()
        return _payload(refreshed) if refreshed else None
    connection.execute(
        """
        INSERT OR IGNORE INTO confirmed_queries(
          query_key, workspace_id, question, status, query_receipt_key, source_table_key,
          schema_fingerprint, chart_spec_json, evidence_json, originating_action_key,
          created_at, updated_at, confirmed_at, stale_reason
        ) VALUES(?, ?, ?, 'candidate', ?, ?, ?, ?, ?, ?, ?, ?, NULL, '')
        """,
        (
            query_key,
            workspace_id,
            question,
            receipt_key,
            table_key,
            fingerprint,
            json.dumps(added_widget, ensure_ascii=False),
            json.dumps(evidence_refs, ensure_ascii=False),
            action_key,
            timestamp,
            timestamp,
        ),
    )
    row = connection.execute(
        "SELECT * FROM confirmed_queries WHERE workspace_id = ? AND query_key = ?",
        (workspace_id, query_key),
    ).fetchone()
    return _payload(row) if row else None


def refresh_stale_confirmed_queries(connection: sqlite3.Connection, workspace_id: str, now_iso: Callable[[], str]) -> int:
    rows = connection.execute(
        "SELECT query_key, query_receipt_key, source_table_key, schema_fingerprint FROM confirmed_queries WHERE workspace_id = ? AND status = 'confirmed'",
        (workspace_id,),
    ).fetchall()
    stale_count = 0
    for row in rows:
        receipt = get_query_receipt(connection, workspace_id, row["query_receipt_key"])
        source_state = current_query_receipt_source_state(connection, workspace_id, receipt) if receipt else None
        if (
            receipt
            and receipt.get("status") == "executed"
            and source_state
            and source_state.get("matchesReceipt")
            and _stored_binding_matches_receipt(row["schema_fingerprint"], receipt)
        ):
            continue
        connection.execute(
            """
            UPDATE confirmed_queries
            SET status = 'stale', stale_reason = 'Query Receipt source, Domain Pack, or relationship path changed', updated_at = ?
            WHERE workspace_id = ? AND query_key = ?
            """,
            (now_iso(), workspace_id, row["query_key"]),
        )
        connection.execute(
            """
            UPDATE confirmed_plan_memories
            SET status = 'stale', stale_reason = 'Plan evidence binding changed', updated_at = ?
            WHERE workspace_id = ? AND query_key = ? AND status = 'confirmed'
            """,
            (now_iso(), workspace_id, row["query_key"]),
        )
        stale_count += 1
    return stale_count


def confirmed_queries_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        stale_count = refresh_stale_confirmed_queries(connection, workspace_id, now_iso)
        params: list[Any] = [workspace_id]
        where = "workspace_id = ?"
        if args.status:
            where += " AND status = ?"
            params.append(args.status)
        params.append(max(1, min(int(args.limit), 200)))
        rows = connection.execute(
            f"SELECT * FROM confirmed_queries WHERE {where} ORDER BY created_at DESC LIMIT ?",
            tuple(params),
        ).fetchall()
        queries = [_payload(row) for row in rows]
    return {"ok": True, "confirmedQueries": queries, "count": len(queries), "staleCount": stale_count}


def confirm_query_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    query_key = str(args.query or "").strip()
    target_status = str(args.status or "confirmed").strip()
    if target_status not in {"confirmed", "deprecated"}:
        raise ValueError(f"Unsupported confirmed query status: {target_status}")
    with closing(open_db()) as connection:
        if connection.in_transaction:
            connection.commit()
        # Confirmation promotes a freshness decision into durable memory. Keep
        # the proof and the status update in one stable snapshot so a source
        # writer cannot race between them.
        connection.execute("BEGIN IMMEDIATE")
        workspace_id = active_workspace_id(connection)
        row = connection.execute(
            "SELECT * FROM confirmed_queries WHERE workspace_id = ? AND query_key = ?",
            (workspace_id, query_key),
        ).fetchone()
        if not row:
            raise ValueError(f"Unknown confirmed query candidate: {query_key}")
        item = _payload(row)
        receipt = get_query_receipt(connection, workspace_id, item["query_receipt_key"])
        if not receipt or receipt.get("status") != "executed":
            raise ValueError("Only executed query receipts can become confirmed queries")
        source_state = current_query_receipt_source_state(connection, workspace_id, receipt)
        binding_current = (
            source_state.get("matchesReceipt")
            and _stored_binding_matches_receipt(item["schema_fingerprint"], receipt)
        )
        if target_status == "confirmed" and not binding_current:
            return {
                "ok": False,
                "requiresConfirmation": False,
                "query": item,
                "error": "Query candidate is stale because its source, Domain Pack, or relationship path changed",
            }
        proposal = {**item, "targetStatus": target_status}
        if not args.yes:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "proposal": proposal}
        timestamp = now_iso()
        if target_status == "confirmed":
            connection.execute(
                """
                UPDATE confirmed_queries
                SET status = 'deprecated', updated_at = ?, stale_reason = 'Superseded by a newer confirmation'
                WHERE workspace_id = ? AND query_key <> ? AND source_table_key = ?
                  AND status IN ('candidate', 'confirmed') AND lower(trim(question)) = lower(trim(?))
                """,
                (timestamp, workspace_id, query_key, item["source_table_key"], item["question"]),
            )
            connection.execute(
                """
                UPDATE confirmed_plan_memories
                SET status = 'deprecated', updated_at = ?, stale_reason = 'Superseded by a newer confirmation'
                WHERE workspace_id = ? AND query_key <> ? AND status = 'confirmed'
                  AND lower(trim(question)) = lower(trim(?))
                """,
                (timestamp, workspace_id, query_key, item["question"]),
            )
        connection.execute(
            """
            UPDATE confirmed_queries
            SET status = ?, updated_at = ?, confirmed_at = ?, stale_reason = ''
            WHERE workspace_id = ? AND query_key = ?
            """,
            (target_status, timestamp, timestamp if target_status == "confirmed" else row["confirmed_at"], workspace_id, query_key),
        )
        saved_query_row = connection.execute(
            "SELECT * FROM confirmed_queries WHERE workspace_id = ? AND query_key = ?",
            (workspace_id, query_key),
        ).fetchone()
        saved_query = _payload(saved_query_row)
        existing_memory = connection.execute(
            "SELECT * FROM confirmed_plan_memories WHERE workspace_id = ? AND query_key = ?",
            (workspace_id, query_key),
        ).fetchone()
        plan_memory = None
        if target_status == "confirmed":
            plan_memory = _upsert_confirmed_plan_memory(
                connection,
                query=saved_query,
                receipt=receipt,
                status=target_status,
                timestamp=timestamp,
            )
        elif existing_memory:
            connection.execute(
                """
                UPDATE confirmed_plan_memories
                SET status = 'deprecated', updated_at = ?, stale_reason = ''
                WHERE workspace_id = ? AND query_key = ?
                """,
                (timestamp, workspace_id, query_key),
            )
            updated_memory = connection.execute(
                "SELECT * FROM confirmed_plan_memories WHERE workspace_id = ? AND query_key = ?",
                (workspace_id, query_key),
            ).fetchone()
            plan_memory = _memory_payload(updated_memory, receipt)
        connection.commit()
        saved = connection.execute(
            "SELECT * FROM confirmed_queries WHERE workspace_id = ? AND query_key = ?",
            (workspace_id, query_key),
        ).fetchone()
    return {"ok": True, "confirmed": True, "savedQuery": _payload(saved), "confirmedPlanMemory": plan_memory}


def confirmed_plans_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        params: list[Any] = [workspace_id]
        where = "workspace_id = ?"
        if args.status:
            where += " AND status = ?"
            params.append(args.status)
        params.append(max(1, min(int(args.limit), 200)))
        rows = connection.execute(
            f"SELECT * FROM confirmed_plan_memories WHERE {where} ORDER BY updated_at DESC LIMIT ?",
            tuple(params),
        ).fetchall()
        memories = []
        for row in rows:
            receipt = get_query_receipt(connection, workspace_id, row["query_receipt_key"])
            memory = _memory_payload(row, receipt)
            source_state = current_query_receipt_source_state(connection, workspace_id, receipt) if receipt else None
            if (
                memory["status"] == "confirmed"
                and (
                    not receipt
                    or receipt.get("status") != "executed"
                    or not source_state
                    or not source_state.get("matchesReceipt")
                    or not _stored_binding_matches_receipt(memory["bindingFingerprint"], receipt)
                )
            ):
                memory["status"] = "stale"
                memory["staleReason"] = "Plan evidence binding changed"
            memories.append(memory)
    return {"ok": True, "workspaceId": workspace_id, "confirmedPlans": memories, "count": len(memories)}


def recall_receipts_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        params: list[Any] = [workspace_id]
        where = "workspace_id = ?"
        if args.receipt:
            where += " AND receipt_key = ?"
            params.append(str(args.receipt))
        params.append(max(1, min(int(args.limit), 200)))
        rows = connection.execute(
            f"SELECT * FROM recall_receipts WHERE {where} ORDER BY created_at DESC LIMIT ?",
            tuple(params),
        ).fetchall()
        receipts = [_recall_receipt_payload(row) for row in rows]
    return {"ok": True, "workspaceId": workspace_id, "recallReceipts": receipts, "count": len(receipts)}


def recall_confirmed_plans(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    prompt: str,
    explicit_table_key: str | None,
    semantic_plan: dict[str, Any] | None,
    context_matches: dict[str, Any] | None,
    planning_binding: dict[str, Any] | None,
    now_iso: Callable[[], str],
    limit: int = 3,
    persist_receipt: bool = True,
) -> dict[str, Any]:
    stale_count = refresh_stale_confirmed_queries(connection, workspace_id, now_iso)
    rows = connection.execute(
        "SELECT * FROM confirmed_plan_memories WHERE workspace_id = ? AND status = 'confirmed' ORDER BY confirmed_at DESC",
        (workspace_id,),
    ).fetchall()
    prompt_folded = prompt.casefold().strip()
    prompt_words, prompt_grams = _text_features(prompt)
    for term in (context_matches or {}).get("terms") or []:
        if not isinstance(term, dict):
            continue
        for value in [term.get("canonical_name"), *(term.get("aliases") or [])]:
            words, grams = _text_features(str(value or ""))
            prompt_words.update(words)
            prompt_grams.update(grams)
    current_signature = _current_signature(semantic_plan, explicit_table_key)
    current_values = _signature_values(current_signature)
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        receipt = get_query_receipt(connection, workspace_id, row["query_receipt_key"])
        if not receipt or receipt.get("status") != "executed":
            continue
        source_state = current_query_receipt_source_state(connection, workspace_id, receipt)
        if not source_state.get("matchesReceipt") or not _stored_binding_matches_receipt(row["binding_fingerprint"], receipt):
            continue
        memory = _memory_payload(row, receipt)
        memory_tables = set(memory["signature"].get("tables") or [])
        if explicit_table_key and memory_tables and explicit_table_key not in memory_tables:
            continue
        question = str(row["question"] or "").casefold().strip()
        memory_words, memory_grams = _text_features(question)
        memory_words.update(str(value).casefold() for value in memory["signature"].get("fields") or [])
        memory_words.update(str(value).casefold() for value in memory["signature"].get("groups") or [])
        if memory["signature"].get("measure"):
            memory_words.add(str(memory["signature"]["measure"]).casefold())
        sequence_score = 1.0 if question == prompt_folded else SequenceMatcher(None, prompt_folded, question).ratio()
        lexical_score = max(sequence_score, _jaccard(prompt_words, memory_words))
        if prompt_folded and (prompt_folded in question or question in prompt_folded):
            lexical_score = max(lexical_score, 0.85)
        gram_score = _jaccard(prompt_grams, memory_grams)
        memory_values = _signature_values(memory["signature"])
        structured_score = _jaccard(current_values, memory_values)
        active_weights = [("lexical", 0.5, lexical_score), ("character", 0.2, gram_score)]
        if current_values:
            active_weights.append(("structured", 0.3, structured_score))
        weight_total = sum(weight for _name, weight, _value in active_weights)
        score = sum(weight * value for _name, weight, value in active_weights) / weight_total
        if question == prompt_folded:
            score = 1.0
        candidate = {
            **memory,
            "matchScore": round(score, 4),
            "matchChannels": {
                "lexical": round(lexical_score, 4),
                "characterNgram": round(gram_score, 4),
                "structuredPlan": round(structured_score, 4),
                "freshness": 1.0,
            },
            "reasonCodes": [
                name for name, value in [
                    ("lexical-question", lexical_score),
                    ("multilingual-character-overlap", gram_score),
                    ("structured-plan-overlap", structured_score),
                ] if value > 0
            ] + ["current-evidence-binding", "candidate-only"],
            "canAuthorizeSelection": False,
            "canBypassAmbiguity": False,
        }
        scored.append((score, candidate))
    scored.sort(key=lambda entry: (-entry[0], str(entry[1].get("confirmedAt") or "")))
    inspected = [item for _score, item in scored[:8]]
    returned = [item for score, item in scored if score >= RECALL_THRESHOLD][:max(1, min(int(limit), 10))]
    ambiguous = (
        len(returned) > 1
        and abs(float(returned[0]["matchScore"]) - float(returned[1]["matchScore"])) <= AMBIGUITY_MARGIN
        and returned[0]["planFingerprint"] != returned[1]["planFingerprint"]
    )
    status = "ambiguous-candidates" if ambiguous else "candidates" if returned else "no-match"
    policy = {
        "schema": RECALL_POLICY_SCHEMA,
        "strategy": "deterministic-hybrid",
        "channels": ["lexical-question", "multilingual-character-overlap", "structured-plan-overlap", "evidence-freshness"],
        "threshold": RECALL_THRESHOLD,
        "ambiguityMargin": AMBIGUITY_MARGIN,
        "adoption": "candidate-only",
        "canBypassFieldAmbiguity": False,
        "canBypassRelationshipValidation": False,
        "canAuthorizeExecution": False,
    }
    timestamp = now_iso()
    planning_binding_fingerprint = str((planning_binding or {}).get("fingerprint") or "")
    request_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    receipt_material = {
        "workspaceId": workspace_id,
        "requestHash": request_hash,
        "planningBindingFingerprint": planning_binding_fingerprint,
        "policy": policy,
        "candidates": [{"memoryKey": item["memoryKey"], "score": item["matchScore"]} for item in inspected],
        "createdAt": timestamp,
    }
    receipt_key = f"recall_receipt_{_fingerprint(receipt_material)[:20]}"
    receipt_payload = {
        "schema": RECALL_RECEIPT_SCHEMA,
        "receiptKey": receipt_key,
        "workspaceId": workspace_id,
        "requestHash": request_hash,
        "status": status,
        "policy": policy,
        "candidates": inspected,
        "returnedCandidates": returned,
        "planningBindingFingerprint": planning_binding_fingerprint,
        "staleExcludedCount": stale_count,
        "createdAt": timestamp,
    }
    if persist_receipt:
        connection.execute(
            """
            INSERT OR REPLACE INTO recall_receipts(
              receipt_key, workspace_id, request_hash, status, policy_json,
              candidates_json, returned_json, planning_binding_fingerprint, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt_key,
                workspace_id,
                request_hash,
                status,
                _canonical_json(policy),
                _canonical_json(inspected),
                _canonical_json(returned),
                planning_binding_fingerprint,
                timestamp,
            ),
        )
    return {"candidates": returned, "receipt": receipt_payload}


def recall_confirmed_queries(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    prompt: str,
    table_key: str | None,
    now_iso: Callable[[], str],
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Compatibility facade for direct callers; it never persists a Recall Receipt."""
    result = recall_confirmed_plans(
        connection,
        workspace_id=workspace_id,
        prompt=prompt,
        explicit_table_key=table_key,
        semantic_plan=None,
        context_matches=None,
        planning_binding=None,
        now_iso=now_iso,
        limit=limit,
        persist_receipt=False,
    )
    candidates = []
    for memory in result["candidates"]:
        candidates.append({
            "query_key": memory["queryKey"],
            "query_receipt_key": memory["queryReceiptKey"],
            "question": memory["question"],
            "matchScore": memory["matchScore"],
            "planMemoryKey": memory["memoryKey"],
            "matchChannels": memory["matchChannels"],
        })
    return candidates
