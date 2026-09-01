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
STALE_REFERENCE_BATCH_SIZE = 800
MAX_SNAPSHOT_TURN_REFERENCES = 2_048


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


def _turn_rows(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    session_key: str,
    after_rowid: int | None = None,
) -> list[sqlite3.Row]:
    if after_rowid is not None:
        return connection.execute(
            "SELECT rowid AS _turn_rowid, * FROM agent_turns WHERE workspace_id = ? AND session_key = ? AND rowid > ? ORDER BY rowid",
            (workspace_id, session_key, after_rowid),
        ).fetchall()
    return connection.execute(
        "SELECT rowid AS _turn_rowid, * FROM agent_turns WHERE workspace_id = ? AND session_key = ? ORDER BY rowid",
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


def _merge_references(*groups: list[dict[str, str]]) -> list[dict[str, str]]:
    unique: dict[tuple[str, str, str], dict[str, str]] = {}
    for refs in groups:
        for ref in refs:
            if not isinstance(ref, dict) or not ref.get("kind") or not ref.get("key"):
                continue
            normalized = _reference(str(ref["kind"]), str(ref["key"]), str(ref.get("fingerprint") or ""))
            unique[(normalized["kind"], normalized["key"], normalized.get("fingerprint", ""))] = normalized
    return list(unique.values())


def _snapshot_references(
    refs: list[dict[str, str]],
    stale: list[dict[str, str]],
    through_turn_key: str | None,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    turn_refs = [ref for ref in refs if ref.get("kind") == "turn"]
    evidence_refs = [ref for ref in refs if ref.get("kind") not in {"turn", "session-history"}]
    previous_history = [str(ref.get("fingerprint") or "") for ref in refs if ref.get("kind") == "session-history"]
    if len(turn_refs) <= MAX_SNAPSHOT_TURN_REFERENCES and not previous_history:
        return refs, stale
    history_ref = _reference(
        "session-history",
        str(through_turn_key or "empty"),
        _hash({"previousHistory": previous_history, "turnReferenceCount": len(turn_refs), "turnReferences": turn_refs}),
    )
    turn_priority = _merge_references(
        [ref for ref in stale if ref.get("kind") == "turn"],
        [_reference("turn", through_turn_key)] if through_turn_key else [],
        list(reversed(turn_refs)),
    )
    retained_turns = list(reversed(turn_priority[: MAX_SNAPSHOT_TURN_REFERENCES - 1]))
    retained = _merge_references(evidence_refs, retained_turns, [history_ref])
    retained_keys = {(ref["kind"], ref["key"], ref.get("fingerprint", "")) for ref in retained}
    retained_stale = [
        ref
        for ref in stale
        if (str(ref.get("kind")), str(ref.get("key")), str(ref.get("fingerprint") or "")) in retained_keys
    ]
    return retained, retained_stale


def _stale_references(connection: sqlite3.Connection, workspace_id: str, refs: list[dict[str, str]]) -> list[dict[str, str]]:
    table_keys = {
        "turn": ("agent_turns", "turn_key"),
        "query-receipt": ("query_plan_receipts", "receipt_key"),
        "analysis-run": ("analysis_runs", "run_key"),
        "action-draft": ("action_drafts", "action_key"),
    }
    existing_by_kind: dict[str, set[str]] = {}
    for kind, (table, column) in table_keys.items():
        keys = sorted({str(ref["key"]) for ref in refs if ref.get("kind") == kind})
        if not keys:
            continue
        existing: set[str] = set()
        for start in range(0, len(keys), STALE_REFERENCE_BATCH_SIZE):
            batch = keys[start : start + STALE_REFERENCE_BATCH_SIZE]
            placeholders = ", ".join("?" for _ in batch)
            existing.update(
                str(row[0])
                for row in connection.execute(
                    f"SELECT {column} FROM {table} WHERE workspace_id = ? AND {column} IN ({placeholders})",
                    (workspace_id, *batch),
                ).fetchall()
            )
        existing_by_kind[kind] = existing
    return [
        {**ref, "reason": "object-missing"}
        for ref in refs
        if ref.get("kind") in table_keys
        and str(ref["key"]) not in existing_by_kind.get(str(ref["kind"]), set())
    ]


def _source_fingerprint(rows: list[sqlite3.Row]) -> str:
    return _hash([{"turnKey": row["turn_key"], "status": row["status"], "contextFingerprint": row["context_fingerprint"], "updatedAt": row["updated_at"]} for row in rows])


def _incremental_source_fingerprint(base_fingerprint: str, rows: list[sqlite3.Row]) -> str:
    if not rows:
        return base_fingerprint
    return _hash(
        {
            "baseSnapshotFingerprint": base_fingerprint,
            "turns": [
                {
                    "turnKey": row["turn_key"],
                    "status": row["status"],
                    "contextFingerprint": row["context_fingerprint"],
                    "updatedAt": row["updated_at"],
                }
                for row in rows
            ],
        }
    )


def _snapshot_watermark(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    session_key: str,
    snapshot: dict[str, Any],
) -> tuple[int | None, str]:
    summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), dict) else {}
    expected_count = summary.get("turnCount")
    status_counts = summary.get("statusCounts")
    if not isinstance(expected_count, int) or expected_count < 0 or not isinstance(status_counts, dict):
        return None, "snapshot-summary-incomplete"
    through_turn_key = str(snapshot.get("throughTurnKey") or "")
    if expected_count == 0:
        return (0, "") if not through_turn_key else (None, "empty-snapshot-has-watermark")
    if not through_turn_key:
        return None, "snapshot-watermark-missing"
    row = connection.execute(
        "SELECT rowid FROM agent_turns WHERE workspace_id = ? AND session_key = ? AND turn_key = ?",
        (workspace_id, session_key, through_turn_key),
    ).fetchone()
    if not row:
        return None, "snapshot-watermark-turn-missing"
    watermark = int(row[0])
    stored_rowid = summary.get("throughTurnRowId")
    if stored_rowid is not None and int(stored_rowid) != watermark:
        return None, "snapshot-watermark-rowid-changed"
    prefix = connection.execute(
        "SELECT COUNT(*), MAX(updated_at) FROM agent_turns WHERE workspace_id = ? AND session_key = ? AND rowid <= ?",
        (workspace_id, session_key, watermark),
    ).fetchone()
    if int(prefix[0]) != expected_count:
        return None, "snapshot-history-count-changed"
    if str(prefix[1] or "") > str(snapshot.get("createdAt") or ""):
        return None, "snapshot-history-updated"
    return watermark, ""


def build_session_context(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    session_key: str,
) -> dict[str, Any]:
    session = get_agent_session(connection, workspace_id=workspace_id, session_key=session_key)
    if not session:
        raise ValueError(f"Unknown Agent Session in workspace {workspace_id}: {session_key}")
    latest_row = connection.execute(
        "SELECT * FROM agent_context_snapshots WHERE workspace_id = ? AND session_key = ? ORDER BY created_at DESC, snapshot_key DESC LIMIT 1",
        (workspace_id, session_key),
    ).fetchone()
    latest = _snapshot_payload(latest_row) if latest_row else None
    watermark: int | None = None
    fallback_reason = "snapshot-missing"
    if latest:
        watermark, fallback_reason = _snapshot_watermark(
            connection,
            workspace_id=workspace_id,
            session_key=session_key,
            snapshot=latest,
        )
    incremental = watermark is not None
    rows = _turn_rows(
        connection,
        workspace_id=workspace_id,
        session_key=session_key,
        after_rowid=watermark if incremental else None,
    )
    base_summary = latest.get("summary", {}) if incremental and latest else {}
    base_refs = latest.get("preservedRefs", []) if incremental and latest else []
    refs = _merge_references(base_refs, _preserved_references(rows))
    if session.get("forkedFromTurnKey"):
        refs = _merge_references(refs, [_reference("turn", session["forkedFromTurnKey"])])
    stale = _stale_references(connection, workspace_id, refs)
    source_fingerprint = (
        _incremental_source_fingerprint(str(latest.get("sourceFingerprint") or ""), rows)
        if incremental and latest
        else _source_fingerprint(rows)
    )
    unresolved = list(base_summary.get("unresolved") or [])
    blockers = list(base_summary.get("blockers") or [])
    status_counts = {
        str(status): int(count)
        for status, count in (base_summary.get("statusCounts") or {}).items()
        if isinstance(count, int) and count >= 0
    }
    for row in rows:
        intent = _load(row["intent_json"], {})
        validation = _load(row["validation_json"], {})
        unresolved.extend(intent.get("unresolved") or [])
        blockers.extend(validation.get("blockers") or [])
        status = str(row["status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    base_turn_count = int(base_summary.get("turnCount") or 0) if incremental else 0
    through_turn_key = str(rows[-1]["turn_key"]) if rows else ""
    if not through_turn_key and incremental and latest:
        through_turn_key = str(latest.get("throughTurnKey") or "")
    through_turn_rowid = int(rows[-1]["_turn_rowid"]) if rows else int(watermark or 0)
    payload = {
        "schema": SESSION_CONTEXT_SCHEMA,
        "workspaceId": workspace_id,
        "sessionKey": session_key,
        "currentTurnKey": session.get("currentTurnKey"),
        "turnCount": base_turn_count + len(rows),
        "statusCounts": status_counts,
        "throughTurnKey": through_turn_key or None,
        "throughTurnRowId": through_turn_rowid,
        "preservedRefs": refs,
        "staleRefs": stale,
        "unresolved": unresolved[-20:],
        "blockers": list(dict.fromkeys(str(item) for item in blockers))[-40:],
        "latestSnapshot": latest,
        "sourceFingerprint": source_fingerprint,
        "snapshotCurrent": bool(incremental and latest and not rows and latest["sourceFingerprint"] == source_fingerprint),
        "contextBuildMode": "snapshot-incremental" if incremental else "full-history-fallback",
        "loadedTurnCount": len(rows),
        "fallbackReason": None if incremental else fallback_reason,
        "longTermBusinessMemoryPromoted": False,
    }
    payload["fingerprint"] = _hash(payload)
    return payload


def compact_agent_session(connection: sqlite3.Connection, *, workspace_id: str, session_key: str, level: int, now: str) -> dict[str, Any]:
    if level not in {1, 2, 3, 4}:
        raise ValueError("Agent context compaction level must be 1, 2, 3, or 4.")
    context = build_session_context(connection, workspace_id=workspace_id, session_key=session_key)
    summary: dict[str, Any] = {
        "turnCount": context["turnCount"],
        "statusCounts": context["statusCounts"],
        "throughTurnRowId": context["throughTurnRowId"],
        "unresolved": context["unresolved"],
        "blockers": context["blockers"],
        "displayTextRetained": level == 1,
        "structuredSummary": level >= 3,
        "reactiveOverflowCompaction": level == 4,
        "businessFactPromotion": "forbidden",
    }
    if level == 1:
        recent_rows = connection.execute(
            "SELECT prompt FROM agent_turns WHERE workspace_id = ? AND session_key = ? ORDER BY rowid DESC LIMIT 5",
            (workspace_id, session_key),
        ).fetchall()
        summary["recentTopics"] = [" ".join(str(row["prompt"]).split())[:80] for row in reversed(recent_rows)]
    snapshot_key = f"snapshot-{uuid.uuid4().hex[:16]}"
    through_turn_key = context["throughTurnKey"]
    snapshot_refs, snapshot_stale = _snapshot_references(context["preservedRefs"], context["staleRefs"], through_turn_key)
    fingerprint = _hash({"workspaceId": workspace_id, "sessionKey": session_key, "throughTurnKey": through_turn_key, "level": level, "summary": summary, "refs": snapshot_refs, "stale": snapshot_stale, "sourceFingerprint": context["sourceFingerprint"]})
    connection.execute(
        "INSERT INTO agent_context_snapshots(snapshot_key, workspace_id, session_key, through_turn_key, compaction_level, summary_json, preserved_refs_json, stale_refs_json, source_fingerprint, fingerprint, created_at) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (snapshot_key, workspace_id, session_key, through_turn_key, level, _json(summary), _json(snapshot_refs), _json(snapshot_stale), context["sourceFingerprint"], fingerprint, now),
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
