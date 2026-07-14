from __future__ import annotations

import argparse
import sqlite3
from typing import Any, Callable

from job_runtime_service import (
    ACTIVE_STATUSES,
    STATUS_CANCELED,
    STATUS_CANCEL_REQUESTED,
    STATUS_RUNNING,
    TERMINAL_STATUSES,
    get_job,
    job_payload,
    list_job_events,
    list_jobs,
    recover_interrupted_jobs,
    request_job_cancel,
)


def jobs_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        job_key = str(getattr(args, "job", "") or "").strip()
        if job_key:
            return {
                "ok": True,
                "job": get_job(
                    connection,
                    workspace_id=workspace_id,
                    job_key=job_key,
                    event_limit=getattr(args, "event_limit", 200),
                ),
            }
        jobs = list_jobs(
            connection,
            workspace_id=workspace_id,
            statuses=getattr(args, "status", []) or [],
            limit=getattr(args, "limit", 50),
        )
        events = list_job_events(
            connection,
            workspace_id=workspace_id,
            after_sequence=getattr(args, "events_after", 0),
            limit=getattr(args, "event_limit", 200),
        ) if getattr(args, "include_events", False) else []
    return {
        "ok": True,
        "jobs": jobs,
        "events": events,
        "count": len(jobs),
        "activeCount": sum(1 for job in jobs if job["status"] in ACTIVE_STATUSES),
        "lastEventSequence": events[-1]["sequence"] if events else int(getattr(args, "events_after", 0)),
    }


def job_cancel_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    job_key = str(getattr(args, "job", "") or "").strip()
    if not job_key:
        raise ValueError("Job key is required.")
    reason = str(getattr(args, "reason", "") or "user-requested").strip() or "user-requested"
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        current = get_job(connection, workspace_id=workspace_id, job_key=job_key, event_limit=20)
        if current["status"] in TERMINAL_STATUSES or current["status"] == STATUS_CANCEL_REQUESTED:
            return {
                "ok": True,
                "dryRun": False,
                "requiresConfirmation": False,
                "changed": False,
                "job": current,
            }
        target_status = STATUS_CANCEL_REQUESTED if current["status"] == STATUS_RUNNING else STATUS_CANCELED
        if not getattr(args, "yes", False):
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "current": current,
                "proposed": {
                    "jobKey": job_key,
                    "status": target_status,
                    "reason": reason,
                },
            }
        job = request_job_cancel(
            connection,
            workspace_id=workspace_id,
            job_key=job_key,
            reason=reason,
            now_iso=now_iso,
        )
        connection.commit()
    return {
        "ok": True,
        "confirmed": True,
        "changed": True,
        "job": job,
    }


def job_recover_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = None if getattr(args, "all", False) else active_workspace_id(connection)
        params: list[Any] = list(ACTIVE_STATUSES - {"created"})
        placeholders = ",".join("?" for _ in params)
        where = f"status IN ({placeholders})"
        if workspace_id:
            where += " AND workspace_id = ?"
            params.append(workspace_id)
        candidates = [
            job_payload(row)
            for row in connection.execute(
                f"SELECT * FROM analysis_jobs WHERE {where} ORDER BY created_at, job_key",
                tuple(params),
            ).fetchall()
        ]
        if not getattr(args, "yes", False):
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": bool(candidates),
                "scope": "all-workspaces" if workspace_id is None else workspace_id,
                "candidates": candidates,
                "count": len(candidates),
            }
        recovered = recover_interrupted_jobs(
            connection,
            workspace_id=workspace_id,
            now_iso=now_iso,
        )
        connection.commit()
    return {
        "ok": True,
        "confirmed": True,
        "scope": "all-workspaces" if workspace_id is None else workspace_id,
        "recovered": recovered,
        "count": len(recovered),
    }
