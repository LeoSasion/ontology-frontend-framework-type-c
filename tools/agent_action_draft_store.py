from __future__ import annotations

import json
import sqlite3
from typing import Any


def create_action_draft(
    connection: sqlite3.Connection,
    *,
    action_key: str,
    workspace_id: str,
    kind: str,
    label: str,
    payload: dict[str, Any],
    evidence: list[Any],
    created_at: str,
) -> dict[str, Any]:
    connection.execute(
        """
        INSERT INTO action_drafts(action_key, workspace_id, kind, label, status, payload_json, evidence_json, created_at)
        VALUES(?, ?, ?, ?, 'draft', ?, ?, ?)
        """,
        (
            action_key,
            workspace_id,
            kind,
            label,
            json.dumps(payload, ensure_ascii=False),
            json.dumps(evidence, ensure_ascii=False),
            created_at,
        ),
    )
    return {
        "actionKey": action_key,
        "kind": kind,
        "status": "draft",
    }


def get_action_draft(connection: sqlite3.Connection, *, action_key: str, workspace_id: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT *
        FROM action_drafts
        WHERE action_key = ? AND workspace_id = ?
        """,
        (action_key, workspace_id),
    ).fetchone()


def action_draft_payload(action: sqlite3.Row) -> dict[str, Any]:
    payload = json.loads(action["payload_json"])
    return payload if isinstance(payload, dict) else {}


def list_action_drafts(connection: sqlite3.Connection, *, workspace_id: str, limit: int, include_all: bool = False) -> dict[str, Any]:
    status_clause = "status != 'read-only-legacy'" if include_all else "status = 'draft'"
    rows = connection.execute(
        f"""
        SELECT action_key, workspace_id, kind, label, status, payload_json, evidence_json, created_at, confirmed_at
        FROM action_drafts
        WHERE {status_clause} AND workspace_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (workspace_id, limit),
    ).fetchall()
    drafts: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        payload = json.loads(item.pop("payload_json"))
        evidence = json.loads(item.pop("evidence_json"))
        drafts.append({**item, "payload": payload, "evidence": evidence})
    pending_count = count_pending_action_drafts(connection, workspace_id=workspace_id)
    return {"actionDrafts": drafts, "pendingCount": pending_count}


def count_pending_action_drafts(connection: sqlite3.Connection, *, workspace_id: str) -> int:
    return int(
        connection.execute(
            "SELECT COUNT(*) FROM action_drafts WHERE status = 'draft' AND workspace_id = ?",
            (workspace_id,),
        ).fetchone()[0]
    )


def mark_action_confirmed(connection: sqlite3.Connection, action_key: str, confirmed_at: str) -> None:
    connection.execute(
        "UPDATE action_drafts SET status = 'confirmed', confirmed_at = ? WHERE action_key = ?",
        (confirmed_at, action_key),
    )


def mark_action_rejected(connection: sqlite3.Connection, action_key: str, confirmed_at: str) -> None:
    connection.execute(
        "UPDATE action_drafts SET status = 'rejected', confirmed_at = ? WHERE action_key = ?",
        (confirmed_at, action_key),
    )
