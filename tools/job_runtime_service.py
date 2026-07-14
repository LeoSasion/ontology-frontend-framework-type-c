from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from typing import Any, Callable, Iterable


JOB_SCHEMA = "aibi-analysis-job/v1"
JOB_EVENT_SCHEMA = "aibi-analysis-job-event/v1"

STATUS_CREATED = "created"
STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_CANCEL_REQUESTED = "cancel_requested"
STATUS_CANCELED = "canceled"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"

TERMINAL_STATUSES = frozenset({STATUS_CANCELED, STATUS_SUCCEEDED, STATUS_FAILED})
ACTIVE_STATUSES = frozenset({STATUS_CREATED, STATUS_QUEUED, STATUS_RUNNING, STATUS_CANCEL_REQUESTED})
ALL_STATUSES = ACTIVE_STATUSES | TERMINAL_STATUSES

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    STATUS_CREATED: frozenset({STATUS_QUEUED, STATUS_CANCELED, STATUS_FAILED}),
    STATUS_QUEUED: frozenset({STATUS_RUNNING, STATUS_CANCELED, STATUS_FAILED}),
    STATUS_RUNNING: frozenset({STATUS_CANCEL_REQUESTED, STATUS_SUCCEEDED, STATUS_FAILED}),
    STATUS_CANCEL_REQUESTED: frozenset({STATUS_CANCELED, STATUS_FAILED}),
    STATUS_CANCELED: frozenset(),
    STATUS_SUCCEEDED: frozenset(),
    STATUS_FAILED: frozenset(),
}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_json(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def input_fingerprint(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _job_key() -> str:
    return f"job_{uuid.uuid4().hex[:20]}"


def _job_row(connection: sqlite3.Connection, workspace_id: str, job_key: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM analysis_jobs WHERE workspace_id = ? AND job_key = ?",
        (workspace_id, job_key),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown analysis job in active workspace: {job_key}")
    return row


def job_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "schema": JOB_SCHEMA,
        "jobKey": row["job_key"],
        "workspaceId": row["workspace_id"],
        "parentJobKey": row["parent_job_key"],
        "kind": row["kind"],
        "capabilityId": row["capability_id"] or f"job.{row['kind']}",
        "label": row["label"],
        "status": row["status"],
        "progress": int(row["progress"]),
        "stage": row["stage"],
        "cancelRequested": bool(row["cancel_requested"]),
        "inputFingerprint": row["input_fingerprint"],
        "input": _load_json(row["input_json"], {}),
        "result": _load_json(row["result_json"], None),
        "error": _load_json(row["error_json"], None),
        "artifactRefs": _load_json(row["artifact_refs_json"], []),
        "evidenceRefs": _load_json(row["evidence_refs_json"], []),
        "queryReceiptKey": row["query_receipt_key"],
        "analysisRunKey": row["analysis_run_key"],
        "sourceRunId": row["source_run_id"],
        "createdAt": row["created_at"],
        "queuedAt": row["queued_at"],
        "startedAt": row["started_at"],
        "updatedAt": row["updated_at"],
        "finishedAt": row["finished_at"],
    }


def event_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "schema": JOB_EVENT_SCHEMA,
        "sequence": int(row["event_sequence"]),
        "workspaceId": row["workspace_id"],
        "jobKey": row["job_key"],
        "type": row["event_type"],
        "status": row["status"],
        "progress": int(row["progress"]),
        "stage": row["stage"],
        "message": row["message"],
        "payload": _load_json(row["payload_json"], {}),
        "createdAt": row["created_at"],
    }


def _append_event(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    job_key: str,
    event_type: str,
    status: str,
    progress: int,
    stage: str,
    message: str,
    payload: dict[str, Any] | None,
    created_at: str,
) -> dict[str, Any]:
    cursor = connection.execute(
        """
        INSERT INTO analysis_job_events(
          workspace_id, job_key, event_type, status, progress, stage,
          message, payload_json, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            workspace_id,
            job_key,
            event_type,
            status,
            progress,
            stage,
            message,
            _json(payload or {}),
            created_at,
        ),
    )
    row = connection.execute(
        "SELECT * FROM analysis_job_events WHERE event_sequence = ?",
        (cursor.lastrowid,),
    ).fetchone()
    return event_payload(row)


def create_job(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    kind: str,
    label: str,
    input_value: dict[str, Any] | None,
    now_iso: Callable[[], str],
    parent_job_key: str | None = None,
    query_receipt_key: str | None = None,
    analysis_run_key: str | None = None,
    source_run_id: str | None = None,
    capability_id: str | None = None,
) -> dict[str, Any]:
    kind = str(kind or "").strip()
    label = str(label or "").strip()
    if not kind:
        raise ValueError("Job kind is required.")
    if not label:
        raise ValueError("Job label is required.")
    if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
        raise ValueError(f"Unknown workspace: {workspace_id}")
    if parent_job_key:
        _job_row(connection, workspace_id, parent_job_key)
    timestamp = now_iso()
    job_key = _job_key()
    input_payload = input_value or {}
    connection.execute(
        """
        INSERT INTO analysis_jobs(
          job_key, workspace_id, parent_job_key, kind, capability_id, label, status, progress,
          stage, cancel_requested, input_fingerprint, input_json, result_json,
          error_json, artifact_refs_json, evidence_refs_json, query_receipt_key,
          analysis_run_key, source_run_id, created_at, queued_at, started_at,
          updated_at, finished_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, 0, ?, 0, ?, ?, 'null', 'null', '[]', '[]', ?, ?, ?, ?, NULL, NULL, ?, NULL)
        """,
        (
            job_key,
            workspace_id,
            parent_job_key,
            kind,
            str(capability_id or f"job.{kind}"),
            label,
            STATUS_CREATED,
            "created",
            input_fingerprint(input_payload),
            _json(input_payload),
            query_receipt_key,
            analysis_run_key,
            source_run_id,
            timestamp,
            timestamp,
        ),
    )
    _append_event(
        connection,
        workspace_id=workspace_id,
        job_key=job_key,
        event_type="job_created",
        status=STATUS_CREATED,
        progress=0,
        stage="created",
        message=label,
        payload={"kind": kind, "parentJobKey": parent_job_key},
        created_at=timestamp,
    )
    return job_payload(_job_row(connection, workspace_id, job_key))


def transition_job(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    job_key: str,
    status: str,
    now_iso: Callable[[], str],
    progress: int | None = None,
    stage: str | None = None,
    message: str = "",
    result: Any = None,
    error: dict[str, Any] | None = None,
    artifact_refs: list[dict[str, Any]] | None = None,
    evidence_refs: list[dict[str, Any]] | None = None,
    query_receipt_key: str | None = None,
    analysis_run_key: str | None = None,
    source_run_id: str | None = None,
    event_type: str | None = None,
) -> dict[str, Any]:
    if status not in ALL_STATUSES:
        raise ValueError(f"Unknown job status: {status}")
    row = _job_row(connection, workspace_id, job_key)
    current_status = str(row["status"])
    if status == current_status:
        return job_payload(row)
    if status not in ALLOWED_TRANSITIONS.get(current_status, frozenset()):
        raise ValueError(f"Invalid job transition: {current_status} -> {status}")
    current_progress = int(row["progress"])
    next_progress = current_progress if progress is None else max(0, min(100, int(progress)))
    if next_progress < current_progress:
        raise ValueError("Job progress cannot move backwards.")
    if status == STATUS_SUCCEEDED:
        next_progress = 100
    elif next_progress >= 100:
        next_progress = 99
    next_stage = str(stage or row["stage"] or status).strip() or status
    timestamp = now_iso()
    queued_at = timestamp if status == STATUS_QUEUED and not row["queued_at"] else row["queued_at"]
    started_at = timestamp if status == STATUS_RUNNING and not row["started_at"] else row["started_at"]
    finished_at = timestamp if status in TERMINAL_STATUSES else row["finished_at"]
    cancel_requested = 1 if status == STATUS_CANCEL_REQUESTED else int(row["cancel_requested"])
    if status in TERMINAL_STATUSES:
        cancel_requested = 0
    result_json = _json(result) if status == STATUS_SUCCEEDED else row["result_json"]
    error_json = _json(error) if error is not None else row["error_json"]
    artifact_json = _json(artifact_refs) if artifact_refs is not None else row["artifact_refs_json"]
    evidence_json = _json(evidence_refs) if evidence_refs is not None else row["evidence_refs_json"]
    next_query_receipt_key = query_receipt_key if query_receipt_key is not None else row["query_receipt_key"]
    next_analysis_run_key = analysis_run_key if analysis_run_key is not None else row["analysis_run_key"]
    next_source_run_id = source_run_id if source_run_id is not None else row["source_run_id"]
    connection.execute(
        """
        UPDATE analysis_jobs
        SET status = ?, progress = ?, stage = ?, cancel_requested = ?, result_json = ?,
            error_json = ?, artifact_refs_json = ?, evidence_refs_json = ?, query_receipt_key = ?,
            analysis_run_key = ?, source_run_id = ?, queued_at = ?, started_at = ?,
            updated_at = ?, finished_at = ?
        WHERE workspace_id = ? AND job_key = ?
        """,
        (
            status,
            next_progress,
            next_stage,
            cancel_requested,
            result_json,
            error_json,
            artifact_json,
            evidence_json,
            next_query_receipt_key,
            next_analysis_run_key,
            next_source_run_id,
            queued_at,
            started_at,
            timestamp,
            finished_at,
            workspace_id,
            job_key,
        ),
    )
    _append_event(
        connection,
        workspace_id=workspace_id,
        job_key=job_key,
        event_type=event_type or f"job_{status}",
        status=status,
        progress=next_progress,
        stage=next_stage,
        message=message,
        payload={"fromStatus": current_status, "toStatus": status},
        created_at=timestamp,
    )
    return job_payload(_job_row(connection, workspace_id, job_key))


def update_job_progress(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    job_key: str,
    progress: int,
    stage: str,
    message: str,
    now_iso: Callable[[], str],
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = _job_row(connection, workspace_id, job_key)
    if row["status"] != STATUS_RUNNING:
        raise ValueError("Only running jobs can report progress.")
    current_progress = int(row["progress"])
    next_progress = max(0, min(99, int(progress)))
    if next_progress < current_progress:
        raise ValueError("Job progress cannot move backwards.")
    next_stage = str(stage or row["stage"]).strip() or str(row["stage"])
    timestamp = now_iso()
    connection.execute(
        """
        UPDATE analysis_jobs
        SET progress = ?, stage = ?, updated_at = ?
        WHERE workspace_id = ? AND job_key = ?
        """,
        (next_progress, next_stage, timestamp, workspace_id, job_key),
    )
    _append_event(
        connection,
        workspace_id=workspace_id,
        job_key=job_key,
        event_type="job_progress",
        status=STATUS_RUNNING,
        progress=next_progress,
        stage=next_stage,
        message=message,
        payload=payload,
        created_at=timestamp,
    )
    return job_payload(_job_row(connection, workspace_id, job_key))


def request_job_cancel(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    job_key: str,
    now_iso: Callable[[], str],
    reason: str = "user-requested",
) -> dict[str, Any]:
    row = _job_row(connection, workspace_id, job_key)
    status = str(row["status"])
    if status in TERMINAL_STATUSES or status == STATUS_CANCEL_REQUESTED:
        return job_payload(row)
    target = STATUS_CANCEL_REQUESTED if status == STATUS_RUNNING else STATUS_CANCELED
    return transition_job(
        connection,
        workspace_id=workspace_id,
        job_key=job_key,
        status=target,
        stage="cancel",
        message=reason,
        error={"code": "job-canceled", "reason": reason} if target == STATUS_CANCELED else None,
        event_type="job_cancel_requested" if target == STATUS_CANCEL_REQUESTED else "job_canceled",
        now_iso=now_iso,
    )


def recover_interrupted_jobs(
    connection: sqlite3.Connection,
    *,
    now_iso: Callable[[], str],
    workspace_id: str | None = None,
) -> list[dict[str, Any]]:
    params: list[Any] = []
    where = "status IN (?, ?, ?)"
    params.extend([STATUS_QUEUED, STATUS_RUNNING, STATUS_CANCEL_REQUESTED])
    if workspace_id:
        where += " AND workspace_id = ?"
        params.append(workspace_id)
    rows = connection.execute(
        f"SELECT workspace_id, job_key, status FROM analysis_jobs WHERE {where} ORDER BY created_at, job_key",
        tuple(params),
    ).fetchall()
    recovered: list[dict[str, Any]] = []
    for row in rows:
        canceling = row["status"] == STATUS_CANCEL_REQUESTED
        recovered.append(transition_job(
            connection,
            workspace_id=row["workspace_id"],
            job_key=row["job_key"],
            status=STATUS_CANCELED if canceling else STATUS_FAILED,
            stage="recovery",
            message="Local runtime restarted before the job reached a terminal state.",
            error={
                "code": "runtime-restarted",
                "retryable": not canceling,
                "previousStatus": row["status"],
            },
            event_type="job_recovered",
            now_iso=now_iso,
        ))
    return recovered


def list_jobs(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    statuses: Iterable[str] = (),
    limit: int = 50,
) -> list[dict[str, Any]]:
    requested = [str(status) for status in statuses if str(status) in ALL_STATUSES]
    params: list[Any] = [workspace_id]
    where = "workspace_id = ?"
    if requested:
        placeholders = ",".join("?" for _ in requested)
        where += f" AND status IN ({placeholders})"
        params.extend(requested)
    params.append(max(1, min(int(limit), 200)))
    rows = connection.execute(
        f"SELECT * FROM analysis_jobs WHERE {where} ORDER BY created_at DESC, job_key DESC LIMIT ?",
        tuple(params),
    ).fetchall()
    return [job_payload(row) for row in rows]


def list_job_events(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    job_key: str | None = None,
    after_sequence: int = 0,
    limit: int = 200,
) -> list[dict[str, Any]]:
    params: list[Any] = [workspace_id, max(0, int(after_sequence))]
    where = "workspace_id = ? AND event_sequence > ?"
    if job_key:
        _job_row(connection, workspace_id, job_key)
        where += " AND job_key = ?"
        params.append(job_key)
    params.append(max(1, min(int(limit), 500)))
    rows = connection.execute(
        f"SELECT * FROM analysis_job_events WHERE {where} ORDER BY event_sequence LIMIT ?",
        tuple(params),
    ).fetchall()
    return [event_payload(row) for row in rows]


def get_job(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    job_key: str,
    event_limit: int = 200,
) -> dict[str, Any]:
    payload = job_payload(_job_row(connection, workspace_id, job_key))
    payload["events"] = list_job_events(
        connection,
        workspace_id=workspace_id,
        job_key=job_key,
        limit=event_limit,
    )
    return payload
