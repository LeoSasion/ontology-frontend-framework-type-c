from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from typing import Any, Callable

from context_pack_service import workspace_data_fingerprint, workspace_schema_fingerprint
from domain_pack_service import domain_pack_set_fingerprint


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


def create_query_plan_receipt(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    request_text: str,
    source_table_key: str | None,
    status: str,
    group: str | None = None,
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
) -> dict[str, Any]:
    created_at = now_iso()
    receipt_key = _receipt_key(workspace_id, request_text, created_at)
    schema_fingerprint = workspace_schema_fingerprint(connection, workspace_id, source_table_key)
    data_fingerprint = workspace_data_fingerprint(connection, workspace_id, source_table_key)
    runtime = runtime if isinstance(runtime, dict) else {}
    evidence_refs = list(evidence_refs or [])
    context_refs = list(context_refs or [])
    domain_packs = list(domain_packs or [])
    domain_pack_fingerprint = domain_pack_set_fingerprint({"enabledDomainPacks": domain_packs})
    unresolved = list(unresolved or [])
    filters = list(filters or [])
    joins = list(joins or [])
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
            "tableKey": source_table_key,
            "schemaFingerprint": schema_fingerprint,
            "dataFingerprint": data_fingerprint,
        },
        "selection": {
            "group": group,
            "measure": measure,
            "aggregation": aggregation,
            "filters": filters,
            "joins": joins,
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
        },
        "resultBinding": result_binding,
        "contextRefs": context_refs,
        "domainPacks": domain_packs,
        "domainPackFingerprint": domain_pack_fingerprint,
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
            source_table_key,
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
