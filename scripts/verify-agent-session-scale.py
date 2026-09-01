from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from agent_session_service import build_session_context, compact_agent_session  # noqa: E402


TURN_COUNT = 100_000
WORKSPACE_ID = "workspace-scale"
SESSION_KEY = "session-scale"


def create_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE agent_sessions (
          session_key TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, title TEXT NOT NULL,
          status TEXT NOT NULL, current_turn_key TEXT, parent_session_key TEXT,
          forked_from_turn_key TEXT, runtime_profile_id TEXT, context_fingerprint TEXT NOT NULL,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE agent_turns (
          turn_key TEXT NOT NULL, workspace_id TEXT NOT NULL, session_key TEXT,
          parent_turn_key TEXT, prompt TEXT NOT NULL, status TEXT NOT NULL,
          intent_json TEXT NOT NULL, context_json TEXT NOT NULL, plan_json TEXT NOT NULL,
          result_json TEXT NOT NULL, validation_json TEXT NOT NULL,
          context_fingerprint TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
          finished_at TEXT, PRIMARY KEY(workspace_id, turn_key)
        );
        CREATE TABLE agent_context_snapshots (
          snapshot_key TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, session_key TEXT NOT NULL,
          through_turn_key TEXT, compaction_level INTEGER NOT NULL, summary_json TEXT NOT NULL,
          preserved_refs_json TEXT NOT NULL, stale_refs_json TEXT NOT NULL,
          source_fingerprint TEXT NOT NULL, fingerprint TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE query_plan_receipts (workspace_id TEXT NOT NULL, receipt_key TEXT NOT NULL);
        CREATE TABLE analysis_runs (workspace_id TEXT NOT NULL, run_key TEXT NOT NULL);
        CREATE TABLE action_drafts (workspace_id TEXT NOT NULL, action_key TEXT NOT NULL);
        """
    )
    connection.execute(
        "INSERT INTO agent_sessions VALUES(?, ?, 'Scale session', 'active', ?, NULL, NULL, NULL, '', ?, ?)",
        (
            SESSION_KEY,
            WORKSPACE_ID,
            f"turn-{TURN_COUNT - 1:08d}",
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:00+00:00",
        ),
    )
    connection.executemany(
        "INSERT INTO agent_turns(turn_key, workspace_id, session_key, parent_turn_key, prompt, status, intent_json, context_json, plan_json, result_json, validation_json, context_fingerprint, created_at, updated_at, finished_at) VALUES(?, ?, ?, NULL, ?, 'completed', '{}', '{}', '{}', '{}', '{}', ?, ?, ?, ?)",
        (
            (
                f"turn-{index:08d}",
                WORKSPACE_ID,
                SESSION_KEY,
                f"Prompt {index}",
                f"context-{index}",
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
                "2026-01-01T00:00:00+00:00",
            )
            for index in range(TURN_COUNT)
        ),
    )
    connection.execute(
        "UPDATE agent_turns SET result_json = ? WHERE workspace_id = ? AND turn_key = ?",
        (
            json.dumps({"queryPlanReceipt": {"receiptKey": "receipt-scale"}}),
            WORKSPACE_ID,
            f"turn-{TURN_COUNT - 1:08d}",
        ),
    )
    connection.execute("INSERT INTO query_plan_receipts VALUES(?, 'receipt-scale')", (WORKSPACE_ID,))
    connection.commit()
    return connection


checks: list[dict[str, object]] = []
metrics: dict[str, object] = {}


def check(label: str, ok: bool, detail: object = "") -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": "" if ok else detail})


connection = create_connection()
try:
    first_snapshot = compact_agent_session(
        connection,
        workspace_id=WORKSPACE_ID,
        session_key=SESSION_KEY,
        level=2,
        now="2026-01-02T00:00:00+00:00",
    )
    check(
        "snapshot-bounds-turn-refs-without-dropping-evidence-refs",
        len([ref for ref in first_snapshot["preservedRefs"] if ref.get("kind") == "turn"]) <= 2_047
        and any(ref.get("kind") == "session-history" for ref in first_snapshot["preservedRefs"])
        and any(ref.get("kind") == "query-receipt" and ref.get("key") == "receipt-scale" for ref in first_snapshot["preservedRefs"]),
        len(first_snapshot["preservedRefs"]),
    )

    connection.executemany(
        "INSERT INTO agent_turns(turn_key, workspace_id, session_key, parent_turn_key, prompt, status, intent_json, context_json, plan_json, result_json, validation_json, context_fingerprint, created_at, updated_at, finished_at) VALUES(?, ?, ?, NULL, ?, 'completed', '{}', '{}', '{}', '{}', '{}', ?, ?, ?, ?)",
        (
            (
                f"turn-{index:08d}",
                WORKSPACE_ID,
                SESSION_KEY,
                f"Prompt {index}",
                f"context-{index}",
                "2026-01-02T01:00:00+00:00",
                "2026-01-02T01:00:00+00:00",
                "2026-01-02T01:00:00+00:00",
            )
            for index in range(TURN_COUNT, TURN_COUNT + 3)
        ),
    )
    connection.commit()

    statements: list[str] = []
    connection.set_trace_callback(statements.append)
    started = time.perf_counter()
    context = build_session_context(connection, workspace_id=WORKSPACE_ID, session_key=SESSION_KEY)
    elapsed = time.perf_counter() - started
    connection.set_trace_callback(None)
    selects = [statement for statement in statements if statement.lstrip().upper().startswith("SELECT")]
    metrics["incrementalSelectCount"] = len(selects)
    metrics["incrementalElapsedMs"] = round(elapsed * 1_000, 3)
    metrics["incrementalTurnsLoaded"] = context["loadedTurnCount"]
    full_turn_loads = [
        statement
        for statement in selects
        if "SELECT ROWID AS _TURN_ROWID, * FROM AGENT_TURNS" in statement.upper()
        and "ROWID >" not in statement.upper()
    ]
    check(
        "100k-session-loads-only-three-incremental-turns",
        context["turnCount"] == TURN_COUNT + 3
        and context["loadedTurnCount"] == 3
        and context["contextBuildMode"] == "snapshot-incremental"
        and not full_turn_loads,
        {"context": context, "fullTurnLoads": full_turn_loads},
    )
    check(
        "100k-session-has-bounded-query-count-and-latency",
        len(selects) <= 10 and elapsed < 2.0,
        {"selectCount": len(selects), "elapsedSeconds": elapsed, "statements": selects},
    )

    statements.clear()
    connection.set_trace_callback(statements.append)
    second_snapshot = compact_agent_session(
        connection,
        workspace_id=WORKSPACE_ID,
        session_key=SESSION_KEY,
        level=1,
        now="2026-01-03T00:00:00+00:00",
    )
    connection.set_trace_callback(None)
    compaction_turn_loads = [
        statement
        for statement in statements
        if "SELECT ROWID AS _TURN_ROWID, * FROM AGENT_TURNS" in statement.upper()
    ]
    check(
        "compaction-does-not-reload-full-turn-history",
        second_snapshot["summary"]["turnCount"] == TURN_COUNT + 3
        and len(compaction_turn_loads) == 1
        and "ROWID >" in compaction_turn_loads[0].upper(),
        compaction_turn_loads,
    )

    connection.execute(
        "DELETE FROM query_plan_receipts WHERE workspace_id = ? AND receipt_key = 'receipt-scale'",
        (WORKSPACE_ID,),
    )
    connection.commit()
    stale_context = build_session_context(connection, workspace_id=WORKSPACE_ID, session_key=SESSION_KEY)
    check(
        "snapshot-reference-staleness-remains-batched-and-visible",
        any(ref.get("kind") == "query-receipt" and ref.get("key") == "receipt-scale" for ref in stale_context["staleRefs"]),
        stale_context["staleRefs"],
    )
    connection.execute("INSERT INTO query_plan_receipts VALUES(?, 'receipt-scale')", (WORKSPACE_ID,))
    connection.commit()

    connection.execute(
        "UPDATE agent_turns SET status = 'failed', updated_at = '2026-01-04T00:00:00+00:00' WHERE workspace_id = ? AND turn_key = 'turn-00000001'",
        (WORKSPACE_ID,),
    )
    connection.commit()
    fallback = build_session_context(connection, workspace_id=WORKSPACE_ID, session_key=SESSION_KEY)
    check(
        "historical-turn-update-safely-falls-back",
        fallback["contextBuildMode"] == "full-history-fallback"
        and fallback["fallbackReason"] == "snapshot-history-updated"
        and fallback["loadedTurnCount"] == TURN_COUNT + 3
        and fallback["statusCounts"].get("failed") == 1,
        {
            "mode": fallback["contextBuildMode"],
            "reason": fallback["fallbackReason"],
            "loaded": fallback["loadedTurnCount"],
            "statuses": fallback["statusCounts"],
        },
    )
finally:
    connection.close()


failed = [item for item in checks if not item["ok"]]
print(
    json.dumps(
        {
            "ok": not failed,
            "schema": "aibi-agent-session-scale-verify/v1",
            "turnCount": TURN_COUNT,
            "metrics": metrics,
            "checks": checks,
            "failedChecks": [item["label"] for item in failed],
        },
        ensure_ascii=False,
        indent=2,
    )
)
raise SystemExit(1 if failed else 0)
