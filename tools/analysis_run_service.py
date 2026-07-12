from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from typing import Any, Callable


def _run_key(workspace_id: str, question: str, created_at: str, parent_run_key: str | None) -> str:
    material = f"{workspace_id}\x1f{question}\x1f{created_at}\x1f{parent_run_key or ''}"
    return f"analysis_run_{hashlib.sha256(material.encode('utf-8')).hexdigest()[:20]}"


def _payload(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["result"] = json.loads(item.pop("result_json"))
    return item


def validate_branch_parent(connection: sqlite3.Connection, workspace_id: str, parent_run_key: str) -> dict[str, Any]:
    row = connection.execute(
        "SELECT * FROM analysis_runs WHERE workspace_id = ? AND run_key = ?",
        (workspace_id, parent_run_key),
    ).fetchone()
    if not row:
        raise ValueError(f"Unknown analysis run in active workspace: {parent_run_key}")
    parent = _payload(row)
    if parent["status"] != "confirmed":
        raise ValueError("Analysis branches are available only after the parent chart is confirmed")
    return parent


def create_analysis_run(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    question: str,
    status: str,
    query_receipt_key: str,
    action_key: str | None,
    result: dict[str, Any],
    parent_run_key: str | None,
    branch_label: str | None,
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    if parent_run_key:
        validate_branch_parent(connection, workspace_id, parent_run_key)
    timestamp = now_iso()
    run_key = _run_key(workspace_id, question, timestamp, parent_run_key)
    connection.execute(
        """
        INSERT INTO analysis_runs(
          run_key, workspace_id, parent_run_key, branch_label, question, status,
          query_receipt_key, action_key, result_json, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_key, workspace_id, parent_run_key, str(branch_label or "").strip(), question, status,
            query_receipt_key, action_key, json.dumps(result, ensure_ascii=False), timestamp, timestamp,
        ),
    )
    row = connection.execute(
        "SELECT * FROM analysis_runs WHERE workspace_id = ? AND run_key = ?",
        (workspace_id, run_key),
    ).fetchone()
    return _payload(row)


def analysis_runs_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        if args.run:
            row = connection.execute(
                "SELECT * FROM analysis_runs WHERE workspace_id = ? AND run_key = ?",
                (workspace_id, args.run),
            ).fetchone()
            if not row:
                raise ValueError(f"Unknown analysis run in active workspace: {args.run}")
            run = _payload(row)
            children = [
                _payload(item)
                for item in connection.execute(
                    "SELECT * FROM analysis_runs WHERE workspace_id = ? AND parent_run_key = ? ORDER BY created_at",
                    (workspace_id, args.run),
                ).fetchall()
            ]
            return {"ok": True, "analysisRun": run, "branches": children}
        rows = connection.execute(
            "SELECT * FROM analysis_runs WHERE workspace_id = ? ORDER BY created_at DESC LIMIT ?",
            (workspace_id, max(1, min(int(args.limit), 200))),
        ).fetchall()
        runs = [_payload(row) for row in rows]
    return {"ok": True, "analysisRuns": runs, "count": len(runs)}
