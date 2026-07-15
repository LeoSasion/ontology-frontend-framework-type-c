from __future__ import annotations

import argparse
import json
import sqlite3
import uuid
from typing import Any, Callable

from agent_evidence_plan_service import EVENT_SCHEMA, build_evidence_plan, finalize_evidence_plan, public_turn_events, verify_evidence_plan


TURN_SCHEMA = "aibi-agent-turn/v1"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _load(value: Any, fallback: Any) -> Any:
    try:
        return json.loads(str(value or ""))
    except (json.JSONDecodeError, TypeError):
        return fallback


def _turn_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "schema": TURN_SCHEMA, "turnKey": row["turn_key"], "workspaceId": row["workspace_id"],
        "sessionKey": row["session_key"], "parentTurnKey": row["parent_turn_key"], "prompt": row["prompt"], "status": row["status"],
        "intentFrame": _load(row["intent_json"], {}), "semanticContext": _load(row["context_json"], {}),
        "evidencePlan": _load(row["plan_json"], {}), "validation": _load(row["validation_json"], {}),
        "contextFingerprint": row["context_fingerprint"], "createdAt": row["created_at"], "updatedAt": row["updated_at"], "finishedAt": row["finished_at"],
    }


def append_turn_event(connection: sqlite3.Connection, *, workspace_id: str, turn_key: str, event_type: str, status: str, summary: str, now: str, step_key: str | None = None, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    cursor = connection.execute(
        "INSERT INTO agent_turn_events(workspace_id, turn_key, step_key, event_type, status, public_summary, payload_json, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
        (workspace_id, turn_key, step_key, event_type, status, summary, _json(payload or {}), now),
    )
    return {"schema": EVENT_SCHEMA, "sequence": int(cursor.lastrowid), "workspaceId": workspace_id, "turnKey": turn_key, "stepKey": step_key, "eventType": event_type, "status": status, "summary": summary, "payload": payload or {}, "createdAt": now}


def list_turn_events(connection: sqlite3.Connection, *, workspace_id: str, turn_key: str, after_sequence: int = 0, limit: int = 500) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT * FROM agent_turn_events WHERE workspace_id = ? AND turn_key = ? AND event_sequence > ? ORDER BY event_sequence LIMIT ?",
        (workspace_id, turn_key, max(0, int(after_sequence)), max(1, min(int(limit), 1000))),
    ).fetchall()
    return [{"schema": EVENT_SCHEMA, "sequence": int(row["event_sequence"]), "workspaceId": row["workspace_id"], "turnKey": row["turn_key"], "stepKey": row["step_key"], "eventType": row["event_type"], "status": row["status"], "summary": row["public_summary"], "payload": _load(row["payload_json"], {}), "createdAt": row["created_at"]} for row in rows]


def run_agent_turn_command(args: argparse.Namespace, *, ask_runner: Callable[[argparse.Namespace], dict[str, Any]], open_db: Callable[[], sqlite3.Connection], active_workspace_id: Callable[[sqlite3.Connection], str], now_iso: Callable[[], str]) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = str(getattr(args, "workspace", "") or active_workspace_id(connection))
        if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
            raise ValueError(f"Unknown workspace: {workspace_id}")
        turn_key = f"turn-{uuid.uuid4().hex[:16]}"
        now = now_iso()
        connection.execute(
            "INSERT INTO agent_turns(turn_key, workspace_id, session_key, parent_turn_key, prompt, status, intent_json, context_json, plan_json, result_json, validation_json, context_fingerprint, created_at, updated_at, finished_at) VALUES(?, ?, NULL, ?, ?, 'running', '{}', '{}', '{}', '{}', '{}', '', ?, ?, NULL)",
            (turn_key, workspace_id, str(getattr(args, "parent_turn", "") or "") or None, str(args.prompt), now, now),
        )
        append_turn_event(connection, workspace_id=workspace_id, turn_key=turn_key, event_type="accepted", status="running", summary="Agent 回合已接受", now=now)
        connection.commit()
    ask_args = argparse.Namespace(prompt=str(args.prompt), read_only=bool(getattr(args, "read_only", False)), workspace=workspace_id, parent_run="", branch_label="")
    try:
        answer = ask_runner(ask_args)
    except Exception as error:
        with open_db() as connection:
            now = now_iso()
            validation = {"schema": "aibi-agent-completion-validation/v1", "status": "failed", "blockers": [type(error).__name__], "safeToPresent": False}
            connection.execute("UPDATE agent_turns SET status = 'failed', validation_json = ?, updated_at = ?, finished_at = ? WHERE workspace_id = ? AND turn_key = ?", (_json(validation), now, now, workspace_id, turn_key))
            append_turn_event(connection, workspace_id=workspace_id, turn_key=turn_key, event_type="turn-failed", status="failed", summary="Agent 回合执行失败", now=now, payload={"errorType": type(error).__name__})
            connection.commit()
        raise
    plan = build_evidence_plan(workspace_id=workspace_id, turn_key=turn_key, answer=answer)
    validation = verify_evidence_plan(plan, answer)
    plan = finalize_evidence_plan(plan, validation)
    status = str(validation.get("status") or "failed")
    with open_db() as connection:
        now = now_iso()
        connection.execute(
            "UPDATE agent_turns SET status = ?, intent_json = ?, context_json = ?, plan_json = ?, result_json = ?, validation_json = ?, context_fingerprint = ?, updated_at = ?, finished_at = ? WHERE workspace_id = ? AND turn_key = ?",
            (status, _json(answer.get("intentFrame") or {}), _json(answer.get("semanticContext") or {}), _json(plan), _json(answer), _json(validation), str(answer.get("semanticContext", {}).get("fingerprint") or ""), now, now, workspace_id, turn_key),
        )
        for event in public_turn_events(plan, validation):
            append_turn_event(connection, workspace_id=workspace_id, turn_key=turn_key, event_type=str(event["eventType"]), status=str(event["status"]), summary=str(event["summary"]), now=now_iso(), step_key=event.get("stepKey"), payload={"planFingerprint": plan.get("fingerprint")})
        connection.commit()
        row = connection.execute("SELECT * FROM agent_turns WHERE workspace_id = ? AND turn_key = ?", (workspace_id, turn_key)).fetchone()
        events = list_turn_events(connection, workspace_id=workspace_id, turn_key=turn_key)
    return {"ok": validation.get("safeToPresent") is True, "schema": "aibi-agent-turn-run/v1", "turn": _turn_payload(row), "evidencePlan": plan, "validation": validation, "events": events, "answer": answer}


def agent_turns_command(args: argparse.Namespace, *, open_db: Callable[[], sqlite3.Connection], active_workspace_id: Callable[[sqlite3.Connection], str]) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = str(getattr(args, "workspace", "") or active_workspace_id(connection))
        turn_key = str(getattr(args, "turn", "") or "").strip()
        if turn_key:
            row = connection.execute("SELECT * FROM agent_turns WHERE workspace_id = ? AND turn_key = ?", (workspace_id, turn_key)).fetchone()
            if not row:
                raise ValueError(f"Unknown agent turn: {turn_key}")
            events = list_turn_events(connection, workspace_id=workspace_id, turn_key=turn_key, after_sequence=int(getattr(args, "after_sequence", 0) or 0), limit=int(getattr(args, "limit", 500) or 500))
            return {"ok": True, "schema": "aibi-agent-turn-list/v1", "turn": _turn_payload(row), "events": events}
        rows = connection.execute("SELECT * FROM agent_turns WHERE workspace_id = ? ORDER BY updated_at DESC LIMIT ?", (workspace_id, max(1, min(int(getattr(args, "limit", 30) or 30), 200)))).fetchall()
        return {"ok": True, "schema": "aibi-agent-turn-list/v1", "workspaceId": workspace_id, "turns": [_turn_payload(row) for row in rows]}


def cancel_agent_turn_command(args: argparse.Namespace, *, open_db: Callable[[], sqlite3.Connection], active_workspace_id: Callable[[sqlite3.Connection], str], now_iso: Callable[[], str]) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = str(getattr(args, "workspace", "") or active_workspace_id(connection))
        turn_key = str(args.turn)
        row = connection.execute("SELECT * FROM agent_turns WHERE workspace_id = ? AND turn_key = ?", (workspace_id, turn_key)).fetchone()
        if not row:
            raise ValueError(f"Unknown agent turn: {turn_key}")
        if row["status"] in {"completed", "blocked", "failed", "canceled"}:
            return {"ok": True, "schema": "aibi-agent-turn-cancel/v1", "changed": False, "turn": _turn_payload(row)}
        now = now_iso()
        connection.execute("UPDATE agent_turns SET status = 'canceled', updated_at = ?, finished_at = ? WHERE workspace_id = ? AND turn_key = ?", (now, now, workspace_id, turn_key))
        append_turn_event(connection, workspace_id=workspace_id, turn_key=turn_key, event_type="turn-canceled", status="canceled", summary="Agent 回合已取消", now=now)
        connection.commit()
        row = connection.execute("SELECT * FROM agent_turns WHERE workspace_id = ? AND turn_key = ?", (workspace_id, turn_key)).fetchone()
        return {"ok": True, "schema": "aibi-agent-turn-cancel/v1", "changed": True, "turn": _turn_payload(row)}
