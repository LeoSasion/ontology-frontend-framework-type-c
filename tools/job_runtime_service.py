from __future__ import annotations

import hashlib
import json
import re
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
STATUS_NEEDS_ATTENTION = "needs_attention"

TERMINAL_STATUSES = frozenset({STATUS_CANCELED, STATUS_SUCCEEDED, STATUS_FAILED})
ACTIVE_STATUSES = frozenset({
    STATUS_CREATED,
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_CANCEL_REQUESTED,
    STATUS_NEEDS_ATTENTION,
})
ALL_STATUSES = ACTIVE_STATUSES | TERMINAL_STATUSES

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    STATUS_CREATED: frozenset({STATUS_QUEUED, STATUS_CANCELED, STATUS_FAILED, STATUS_NEEDS_ATTENTION}),
    STATUS_QUEUED: frozenset({STATUS_RUNNING, STATUS_CANCELED, STATUS_FAILED, STATUS_NEEDS_ATTENTION}),
    STATUS_RUNNING: frozenset({STATUS_CANCEL_REQUESTED, STATUS_SUCCEEDED, STATUS_FAILED, STATUS_NEEDS_ATTENTION}),
    STATUS_CANCEL_REQUESTED: frozenset({STATUS_CANCELED, STATUS_SUCCEEDED, STATUS_FAILED, STATUS_NEEDS_ATTENTION}),
    STATUS_NEEDS_ATTENTION: frozenset({STATUS_QUEUED, STATUS_CANCELED, STATUS_SUCCEEDED, STATUS_FAILED}),
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


_PUBLIC_WINDOWS_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\[^\\\s]+\\)[^\s\"'<>|]*")
_PUBLIC_UNIX_PATH = re.compile(r"(?<![\w:])/(?:Users|home|tmp|var|private|opt|root|mnt|etc)(?:/[^\s\"'<>|]*)?", re.I)
_PUBLIC_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.I)
_PUBLIC_SECRET = re.compile(
    r"(?:bearer\s+[A-Za-z0-9._~+/-]+=*|\bsk-[A-Za-z0-9_-]{12,}|"
    r"(?:password|passwd|secret|token|api[_-]?key)\s*[:=]\s*[^\s,;]+)",
    re.I,
)
_PUBLIC_SECRET_KEYS = frozenset({
    "authorization",
    "credential",
    "credentials",
    "password",
    "passwd",
    "secret",
    "token",
    "apikey",
    "api_key",
    "accesskey",
    "access_key",
})


def _sanitize_public_text(value: str) -> str:
    text = _PUBLIC_WINDOWS_PATH.sub("[local-path]", value)
    text = _PUBLIC_UNIX_PATH.sub("[local-path]", text)
    text = _PUBLIC_EMAIL.sub("[email]", text)
    return _PUBLIC_SECRET.sub("[secret]", text)


def sanitize_public_value(value: Any, *, key: str = "") -> Any:
    """Redact diagnostics at the DTO boundary while keeping stored evidence intact."""
    normalized_key = key.replace("-", "_").lower()
    if normalized_key in _PUBLIC_SECRET_KEYS:
        return "[redacted]"
    if normalized_key in {"requestkey", "request_key"}:
        return hashlib.sha256(str(value).encode("utf-8")).hexdigest() if value not in (None, "") else None
    if isinstance(value, dict):
        return {
            str(child_key): sanitize_public_value(child_value, key=str(child_key))
            for child_key, child_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize_public_value(item) for item in value]
    if isinstance(value, str):
        return _sanitize_public_text(value)
    return value


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
    keys = set(row.keys())
    kind = str(row["kind"])
    stored_input = _load_json(row["input_json"], {})
    public_input = (
        stored_input.get("public", {})
        if kind == "import" and isinstance(stored_input, dict) and isinstance(stored_input.get("public"), dict)
        else stored_input
    )
    payload = {
        "schema": "aibi-import-job/v1" if kind == "import" else JOB_SCHEMA,
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
        "input": sanitize_public_value(public_input),
        "result": sanitize_public_value(_load_json(row["result_json"], None)),
        "error": sanitize_public_value(_load_json(row["error_json"], None)),
        "artifactRefs": sanitize_public_value(_load_json(row["artifact_refs_json"], [])),
        "evidenceRefs": sanitize_public_value(_load_json(row["evidence_refs_json"], [])),
        "queryReceiptKey": row["query_receipt_key"],
        "analysisRunKey": row["analysis_run_key"],
        "sourceRunId": row["source_run_id"],
        "createdAt": row["created_at"],
        "queuedAt": row["queued_at"],
        "startedAt": row["started_at"],
        "updatedAt": row["updated_at"],
        "finishedAt": row["finished_at"],
    }
    if "request_key" in keys and row["request_key"]:
        payload["requestKeyFingerprint"] = hashlib.sha256(str(row["request_key"]).encode("utf-8")).hexdigest()
    return payload


def job_input(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    job_key: str,
) -> dict[str, Any]:
    """Return the private worker input. Never serialize this value into an API receipt."""
    value = _load_json(_job_row(connection, workspace_id, job_key)["input_json"], {})
    return value if isinstance(value, dict) else {}


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
        "message": _sanitize_public_text(str(row["message"] or "")),
        "payload": sanitize_public_value(_load_json(row["payload_json"], {})),
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
    request_key: str | None = None,
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
    fingerprint = input_fingerprint(input_payload)
    normalized_request_key = str(request_key or "").strip()
    if normalized_request_key and not 1 <= len(normalized_request_key) <= 200:
        raise ValueError("requestKey must contain between 1 and 200 characters.")
    has_request_key = "request_key" in {
        str(row[1]) for row in connection.execute("PRAGMA table_info(analysis_jobs)").fetchall()
    }
    if normalized_request_key and not has_request_key:
        raise RuntimeError("analysis_jobs.request_key is not initialized.")
    if normalized_request_key:
        existing = connection.execute(
            "SELECT * FROM analysis_jobs WHERE workspace_id = ? AND kind = ? AND request_key = ?",
            (workspace_id, kind, normalized_request_key),
        ).fetchone()
        if existing is not None:
            if str(existing["input_fingerprint"]) != fingerprint:
                raise ValueError("requestKey is already bound to different job input.")
            return job_payload(existing)
    columns = """
          job_key, workspace_id, parent_job_key, kind, capability_id, label, status, progress,
          stage, cancel_requested, input_fingerprint, input_json, result_json,
          error_json, artifact_refs_json, evidence_refs_json, query_receipt_key,
          analysis_run_key, source_run_id, created_at, queued_at, started_at,
          updated_at, finished_at
    """
    values = "?, ?, ?, ?, ?, ?, ?, 0, ?, 0, ?, ?, 'null', 'null', '[]', '[]', ?, ?, ?, ?, NULL, NULL, ?, NULL"
    params: list[Any] = [
        job_key,
        workspace_id,
        parent_job_key,
        kind,
        str(capability_id or f"job.{kind}"),
        label,
        STATUS_CREATED,
        "created",
        fingerprint,
        _json(input_payload),
        query_receipt_key,
        analysis_run_key,
        source_run_id,
        timestamp,
        timestamp,
    ]
    if has_request_key:
        columns += ", request_key"
        values += ", ?"
        params.append(normalized_request_key)
    connection.execute(
        f"INSERT INTO analysis_jobs({columns}) VALUES({values})",
        tuple(params),
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
    expected_status: str | None = None,
) -> dict[str, Any]:
    if status not in ALL_STATUSES:
        raise ValueError(f"Unknown job status: {status}")
    row = _job_row(connection, workspace_id, job_key)
    current_status = str(row["status"])
    if expected_status is not None and current_status != expected_status:
        raise ValueError(f"Job state claim failed: expected {expected_status}, found {current_status}")
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
    if status in TERMINAL_STATUSES or status in {STATUS_QUEUED, STATUS_NEEDS_ATTENTION}:
        cancel_requested = 0
    result_json = _json(result) if status == STATUS_SUCCEEDED else row["result_json"]
    error_json = _json(error) if error is not None else row["error_json"]
    artifact_json = _json(artifact_refs) if artifact_refs is not None else row["artifact_refs_json"]
    evidence_json = _json(evidence_refs) if evidence_refs is not None else row["evidence_refs_json"]
    next_query_receipt_key = query_receipt_key if query_receipt_key is not None else row["query_receipt_key"]
    next_analysis_run_key = analysis_run_key if analysis_run_key is not None else row["analysis_run_key"]
    next_source_run_id = source_run_id if source_run_id is not None else row["source_run_id"]
    where = "workspace_id = ? AND job_key = ?"
    if expected_status is not None:
        where += " AND status = ?"
    parameters = [
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
    ]
    if expected_status is not None:
        parameters.append(expected_status)
    cursor = connection.execute(
        """
        UPDATE analysis_jobs
        SET status = ?, progress = ?, stage = ?, cancel_requested = ?, result_json = ?,
            error_json = ?, artifact_refs_json = ?, evidence_refs_json = ?, query_receipt_key = ?,
            analysis_run_key = ?, source_run_id = ?, queued_at = ?, started_at = ?,
            updated_at = ?, finished_at = ?
        WHERE """ + where,
        tuple(parameters),
    )
    if cursor.rowcount != 1:
        raise ValueError("Job state changed before the worker claim could be committed.")
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
    where += " AND kind <> 'import'"
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
