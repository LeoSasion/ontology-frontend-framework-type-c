from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import uuid
from typing import Any, Callable


SESSION_SCHEMA = "aibi-agent-session/v1"
SNAPSHOT_SCHEMA = "aibi-agent-context-snapshot/v1"
SESSION_CONTEXT_SCHEMA = "aibi-agent-session-context/v1"
MAX_SESSION_TITLE = 120


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _load(value: Any, fallback: Any) -> Any:
    try:
        return json.loads(str(value or ""))
    except (json.JSONDecodeError, TypeError):
        return fallback


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _session_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "schema": SESSION_SCHEMA,
        "sessionKey": row["session_key"],
        "workspaceId": row["workspace_id"],
        "title": row["title"],
        "status": row["status"],
        "currentTurnKey": row["current_turn_key"],
        "parentSessionKey": row["parent_session_key"],
        "forkedFromTurnKey": row["forked_from_turn_key"],
        "runtimeProfileId": row["runtime_profile_id"],
        "contextFingerprint": row["context_fingerprint"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def _snapshot_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "schema": SNAPSHOT_SCHEMA,
        "snapshotKey": row["snapshot_key"],
        "workspaceId": row["workspace_id"],
        "sessionKey": row["session_key"],
        "throughTurnKey": row["through_turn_key"],
        "compactionLevel": int(row["compaction_level"]),
        "summary": _load(row["summary_json"], {}),
        "preservedRefs": _load(row["preserved_refs_json"], []),
        "staleRefs": _load(row["stale_refs_json"], []),
        "sourceFingerprint": row["source_fingerprint"],
        "fingerprint": row["fingerprint"],
        "createdAt": row["created_at"],
    }


def get_agent_session(connection: sqlite3.Connection, *, workspace_id: str, session_key: str) -> dict[str, Any] | None:
    row = connection.execute("SELECT * FROM agent_sessions WHERE workspace_id = ? AND session_key = ?", (workspace_id, session_key)).fetchone()
    return _session_payload(row) if row else None


def create_agent_session(connection: sqlite3.Connection, *, workspace_id: str, title: str, now: str, parent_session_key: str | None = None, forked_from_turn_key: str | None = None, runtime_profile_id: str | None = None) -> dict[str, Any]:
    clean_title = " ".join(str(title or "新分析会话").split())[:MAX_SESSION_TITLE] or "新分析会话"
    session_key = f"session-{uuid.uuid4().hex[:16]}"
    connection.execute(
        "INSERT INTO agent_sessions(session_key, workspace_id, title, status, current_turn_key, parent_session_key, forked_from_turn_key, runtime_profile_id, context_fingerprint, created_at, updated_at) VALUES(?, ?, ?, 'active', NULL, ?, ?, ?, '', ?, ?)",
        (session_key, workspace_id, clean_title, parent_session_key, forked_from_turn_key, runtime_profile_id, now, now),
    )
    row = connection.execute("SELECT * FROM agent_sessions WHERE workspace_id = ? AND session_key = ?", (workspace_id, session_key)).fetchone()
    return _session_payload(row)


def _turn_rows(connection: sqlite3.Connection, *, workspace_id: str, session_key: str) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT * FROM agent_turns WHERE workspace_id = ? AND session_key = ? ORDER BY created_at, turn_key",
        (workspace_id, session_key),
    ).fetchall()


def _reference(kind: str, key: str, fingerprint: str = "") -> dict[str, str]:
    value = {"kind": kind, "key": str(key)}
    if fingerprint:
        value["fingerprint"] = str(fingerprint)
    return value


def _preserved_references(rows: list[sqlite3.Row]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    for row in rows:
        refs.append(_reference("turn", row["turn_key"], row["context_fingerprint"]))
        result = _load(row["result_json"], {})
        plan = _load(row["plan_json"], {})
        receipt = result.get("queryPlanReceipt") if isinstance(result, dict) else None
        analysis_run = result.get("analysisRun") if isinstance(result, dict) else None
        action = result.get("actionDraft") if isinstance(result, dict) else None
        if isinstance(receipt, dict) and receipt.get("receiptKey"):
            refs.append(_reference("query-receipt", receipt["receiptKey"], receipt.get("resultBinding", {}).get("resultFingerprint", "") if isinstance(receipt.get("resultBinding"), dict) else ""))
        if isinstance(analysis_run, dict) and (analysis_run.get("run_key") or analysis_run.get("runKey")):
            refs.append(_reference("analysis-run", analysis_run.get("run_key") or analysis_run.get("runKey")))
        if isinstance(action, dict) and action.get("actionKey") and action.get("status") == "draft":
            refs.append(_reference("action-draft", action["actionKey"]))
        if plan.get("fingerprint"):
            refs.append(_reference("evidence-plan", row["turn_key"], plan["fingerprint"]))
        for skill in plan.get("skillRefs") or []:
            if isinstance(skill, dict) and skill.get("skillId"):
                refs.append(_reference("analytical-skill", f"{skill['skillId']}@{skill.get('version')}", skill.get("fingerprint", "")))
    unique: dict[tuple[str, str, str], dict[str, str]] = {}
    for ref in refs:
        unique[(ref["kind"], ref["key"], ref.get("fingerprint", ""))] = ref
    return list(unique.values())


def _stale_references(connection: sqlite3.Connection, workspace_id: str, refs: list[dict[str, str]]) -> list[dict[str, str]]:
    table_keys = {
        "turn": ("agent_turns", "turn_key"),
        "query-receipt": ("query_plan_receipts", "receipt_key"),
        "analysis-run": ("analysis_runs", "run_key"),
        "action-draft": ("action_drafts", "action_key"),
    }
    stale: list[dict[str, str]] = []
    for ref in refs:
        target = table_keys.get(ref["kind"])
        if not target:
            continue
        table, column = target
        exists = connection.execute(f"SELECT 1 FROM {table} WHERE workspace_id = ? AND {column} = ?", (workspace_id, ref["key"])).fetchone()
        if not exists:
            stale.append({**ref, "reason": "object-missing"})
    return stale


def _source_fingerprint(rows: list[sqlite3.Row]) -> str:
    return _hash([{"turnKey": row["turn_key"], "status": row["status"], "contextFingerprint": row["context_fingerprint"], "updatedAt": row["updated_at"]} for row in rows])


def build_session_context(connection: sqlite3.Connection, *, workspace_id: str, session_key: str) -> dict[str, Any]:
    session = get_agent_session(connection, workspace_id=workspace_id, session_key=session_key)
    if not session:
        raise ValueError(f"Unknown Agent Session in workspace {workspace_id}: {session_key}")
    rows = _turn_rows(connection, workspace_id=workspace_id, session_key=session_key)
    refs = _preserved_references(rows)
    if session.get("forkedFromTurnKey"):
        refs.append(_reference("turn", session["forkedFromTurnKey"]))
    stale = _stale_references(connection, workspace_id, refs)
    latest_row = connection.execute(
        "SELECT * FROM agent_context_snapshots WHERE workspace_id = ? AND session_key = ? ORDER BY created_at DESC, snapshot_key DESC LIMIT 1",
        (workspace_id, session_key),
    ).fetchone()
    latest = _snapshot_payload(latest_row) if latest_row else None
    source_fingerprint = _source_fingerprint(rows)
    unresolved = []
    blockers = []
    for row in rows:
        intent = _load(row["intent_json"], {})
        validation = _load(row["validation_json"], {})
        unresolved.extend(intent.get("unresolved") or [])
        blockers.extend(validation.get("blockers") or [])
    payload = {
        "schema": SESSION_CONTEXT_SCHEMA,
        "workspaceId": workspace_id,
        "sessionKey": session_key,
        "currentTurnKey": session.get("currentTurnKey"),
        "turnCount": len(rows),
        "preservedRefs": refs,
        "staleRefs": stale,
        "unresolved": unresolved[-20:],
        "blockers": list(dict.fromkeys(str(item) for item in blockers))[-40:],
        "latestSnapshot": latest,
        "sourceFingerprint": source_fingerprint,
        "snapshotCurrent": bool(latest and latest["sourceFingerprint"] == source_fingerprint),
        "longTermBusinessMemoryPromoted": False,
    }
    payload["fingerprint"] = _hash(payload)
    return payload


def compact_agent_session(connection: sqlite3.Connection, *, workspace_id: str, session_key: str, level: int, now: str) -> dict[str, Any]:
    if level not in {1, 2, 3, 4}:
        raise ValueError("Agent context compaction level must be 1, 2, 3, or 4.")
    context = build_session_context(connection, workspace_id=workspace_id, session_key=session_key)
    rows = _turn_rows(connection, workspace_id=workspace_id, session_key=session_key)
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[str(row["status"])] = status_counts.get(str(row["status"]), 0) + 1
    summary: dict[str, Any] = {
        "turnCount": len(rows),
        "statusCounts": status_counts,
        "unresolved": context["unresolved"],
        "blockers": context["blockers"],
        "displayTextRetained": level == 1,
        "structuredSummary": level >= 3,
        "reactiveOverflowCompaction": level == 4,
        "businessFactPromotion": "forbidden",
    }
    if level == 1:
        summary["recentTopics"] = [" ".join(str(row["prompt"]).split())[:80] for row in rows[-5:]]
    snapshot_key = f"snapshot-{uuid.uuid4().hex[:16]}"
    through_turn_key = rows[-1]["turn_key"] if rows else None
    fingerprint = _hash({"workspaceId": workspace_id, "sessionKey": session_key, "throughTurnKey": through_turn_key, "level": level, "summary": summary, "refs": context["preservedRefs"], "stale": context["staleRefs"], "sourceFingerprint": context["sourceFingerprint"]})
    connection.execute(
        "INSERT INTO agent_context_snapshots(snapshot_key, workspace_id, session_key, through_turn_key, compaction_level, summary_json, preserved_refs_json, stale_refs_json, source_fingerprint, fingerprint, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (snapshot_key, workspace_id, session_key, through_turn_key, level, _json(summary), _json(context["preservedRefs"]), _json(context["staleRefs"]), context["sourceFingerprint"], fingerprint, now),
    )
    row = connection.execute("SELECT * FROM agent_context_snapshots WHERE snapshot_key = ?", (snapshot_key,)).fetchone()
    return _snapshot_payload(row)


def agent_session_create_command(args: argparse.Namespace, *, open_db: Callable[[], sqlite3.Connection], active_workspace_id: Callable[[sqlite3.Connection], str], now_iso: Callable[[], str]) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = str(getattr(args, "workspace", "") or active_workspace_id(connection))
        if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
            raise ValueError(f"Unknown workspace: {workspace_id}")
        session = create_agent_session(connection, workspace_id=workspace_id, title=str(getattr(args, "title", "") or "新分析会话"), now=now_iso())
        connection.commit()
    return {"ok": True, "schema": "aibi-agent-session-create/v1", "session": session}


def agent_sessions_command(args: argparse.Namespace, *, open_db: Callable[[], sqlite3.Connection], active_workspace_id: Callable[[sqlite3.Connection], str]) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = str(getattr(args, "workspace", "") or active_workspace_id(connection))
        session_key = str(getattr(args, "session", "") or "").strip()
        if session_key:
            session = get_agent_session(connection, workspace_id=workspace_id, session_key=session_key)
            if not session:
                raise ValueError(f"Unknown Agent Session in workspace {workspace_id}: {session_key}")
            context = build_session_context(connection, workspace_id=workspace_id, session_key=session_key)
            snapshots = [_snapshot_payload(row) for row in connection.execute("SELECT * FROM agent_context_snapshots WHERE workspace_id = ? AND session_key = ? ORDER BY created_at DESC LIMIT ?", (workspace_id, session_key, max(1, min(int(getattr(args, "limit", 30) or 30), 200)))).fetchall()]
            return {"ok": True, "schema": "aibi-agent-session-list/v1", "session": session, "context": context, "snapshots": snapshots}
        rows = connection.execute("SELECT * FROM agent_sessions WHERE workspace_id = ? ORDER BY updated_at DESC LIMIT ?", (workspace_id, max(1, min(int(getattr(args, "limit", 30) or 30), 200)))).fetchall()
        return {"ok": True, "schema": "aibi-agent-session-list/v1", "workspaceId": workspace_id, "sessions": [_session_payload(row) for row in rows]}


def agent_session_resume_command(args: argparse.Namespace, *, open_db: Callable[[], sqlite3.Connection], active_workspace_id: Callable[[sqlite3.Connection], str]) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = str(getattr(args, "workspace", "") or active_workspace_id(connection))
        session_key = str(args.session)
        session = get_agent_session(connection, workspace_id=workspace_id, session_key=session_key)
        if not session:
            raise ValueError(f"Unknown Agent Session in workspace {workspace_id}: {session_key}")
        context = build_session_context(connection, workspace_id=workspace_id, session_key=session_key)
    return {"ok": True, "schema": "aibi-agent-session-resume/v1", "session": session, "context": context, "canResume": not bool(context["staleRefs"]), "requiresReview": bool(context["staleRefs"]), "nextCommand": f"agent-turn-run --session {session_key} <prompt>"}


def agent_session_fork_command(args: argparse.Namespace, *, open_db: Callable[[], sqlite3.Connection], active_workspace_id: Callable[[sqlite3.Connection], str], now_iso: Callable[[], str]) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = str(getattr(args, "workspace", "") or active_workspace_id(connection))
        parent_key = str(args.session)
        parent = get_agent_session(connection, workspace_id=workspace_id, session_key=parent_key)
        if not parent:
            raise ValueError(f"Unknown Agent Session in workspace {workspace_id}: {parent_key}")
        from_turn = str(getattr(args, "from_turn", "") or parent.get("currentTurnKey") or "")
        if not from_turn or not connection.execute("SELECT 1 FROM agent_turns WHERE workspace_id = ? AND session_key = ? AND turn_key = ?", (workspace_id, parent_key, from_turn)).fetchone():
            raise ValueError("Fork requires a Turn that belongs to the parent Agent Session.")
        fork = create_agent_session(connection, workspace_id=workspace_id, title=str(getattr(args, "title", "") or f"{parent['title']} · 分支"), now=now_iso(), parent_session_key=parent_key, forked_from_turn_key=from_turn, runtime_profile_id=parent.get("runtimeProfileId"))
        connection.commit()
    return {"ok": True, "schema": "aibi-agent-session-fork/v1", "parentSession": parent, "forkedSession": fork, "parentUnchanged": True}


def agent_context_compact_command(args: argparse.Namespace, *, open_db: Callable[[], sqlite3.Connection], active_workspace_id: Callable[[sqlite3.Connection], str], now_iso: Callable[[], str]) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = str(getattr(args, "workspace", "") or active_workspace_id(connection))
        snapshot = compact_agent_session(connection, workspace_id=workspace_id, session_key=str(args.session), level=int(args.level), now=now_iso())
        connection.commit()
    return {"ok": True, "schema": "aibi-agent-context-compact/v1", "snapshot": snapshot, "turnsDeleted": 0, "evidenceRefsPreserved": True, "businessFactsPromoted": False}
