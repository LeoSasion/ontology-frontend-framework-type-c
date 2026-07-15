from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from difflib import SequenceMatcher
from typing import Any, Callable

from query_plan_receipt_service import (
    current_query_receipt_source_state,
    get_query_receipt,
    query_receipt_binding_fingerprint,
)


def _query_key(workspace_id: str, action_key: str, receipt_key: str) -> str:
    material = f"{workspace_id}\x1f{action_key}\x1f{receipt_key}"
    return f"confirmed_query_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:20]}"


def _payload(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["chartSpec"] = json.loads(item.pop("chart_spec_json"))
    item["evidenceRefs"] = json.loads(item.pop("evidence_json"))
    return item


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
        stale_count += 1
    if stale_count:
        connection.commit()
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
            UPDATE confirmed_queries
            SET status = ?, updated_at = ?, confirmed_at = ?, stale_reason = ''
            WHERE workspace_id = ? AND query_key = ?
            """,
            (target_status, timestamp, timestamp if target_status == "confirmed" else row["confirmed_at"], workspace_id, query_key),
        )
        connection.commit()
        saved = connection.execute(
            "SELECT * FROM confirmed_queries WHERE workspace_id = ? AND query_key = ?",
            (workspace_id, query_key),
        ).fetchone()
    return {"ok": True, "confirmed": True, "savedQuery": _payload(saved)}


def recall_confirmed_queries(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    prompt: str,
    table_key: str | None,
    now_iso: Callable[[], str],
    limit: int = 3,
) -> list[dict[str, Any]]:
    refresh_stale_confirmed_queries(connection, workspace_id, now_iso)
    rows = connection.execute(
        "SELECT * FROM confirmed_queries WHERE workspace_id = ? AND status = 'confirmed' ORDER BY confirmed_at DESC",
        (workspace_id,),
    ).fetchall()
    prompt_folded = prompt.casefold().strip()
    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        receipt = get_query_receipt(connection, workspace_id, row["query_receipt_key"])
        if not receipt or receipt.get("status") != "executed":
            continue
        source_state = current_query_receipt_source_state(connection, workspace_id, receipt)
        if not source_state.get("matchesReceipt") or not _stored_binding_matches_receipt(row["schema_fingerprint"], receipt):
            continue
        if table_key and row["source_table_key"] and row["source_table_key"] != table_key:
            continue
        question = str(row["question"] or "").casefold().strip()
        score = 1.0 if question == prompt_folded else SequenceMatcher(None, prompt_folded, question).ratio()
        if prompt_folded and (prompt_folded in question or question in prompt_folded):
            score = max(score, 0.85)
        if score >= 0.55:
            item = _payload(row)
            item["matchScore"] = round(score, 4)
            scored.append((score, item))
    scored.sort(key=lambda entry: (-entry[0], str(entry[1].get("confirmed_at") or "")), reverse=False)
    return [item for _score, item in scored[:limit]]
