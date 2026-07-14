from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path
from typing import Any, Callable

from job_runtime_service import (
    STATUS_CANCELED,
    STATUS_CANCEL_REQUESTED,
    STATUS_CREATED,
    STATUS_FAILED,
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_SUCCEEDED,
    TERMINAL_STATUSES,
    create_job,
    get_job,
    transition_job,
    update_job_progress,
)

JOB_KIND = "source-intelligence"


def _reject_other_aibi_repo(path_value: str) -> None:
    parts = {part.lower() for part in Path(path_value).resolve().parts}
    forbidden = {"aibi-a", "aibi-b", "aibi-d", "aibi-e", "aibi项目杂交"}
    found = sorted(parts & forbidden)
    if found:
        raise ValueError(f"AIBI-C job input cannot reference another AIBI repository: {found[0]}")


def _workspace_id(
    connection: sqlite3.Connection,
    args: argparse.Namespace,
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> str:
    workspace_id = str(getattr(args, "workspace", "") or active_workspace_id(connection)).strip()
    if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
        raise ValueError(f"Unknown workspace: {workspace_id}")
    return workspace_id


def source_intelligence_job_create_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    inputs = [str(Path(item)) for item in (getattr(args, "inputs", []) or []) if str(item).strip()]
    if not inputs:
        raise ValueError("Source Intelligence job requires at least one input path.")
    for item in inputs:
        _reject_other_aibi_repo(item)
    output_dir = str(getattr(args, "output_dir", "") or "").strip()
    if output_dir:
        _reject_other_aibi_repo(output_dir)
    label = str(getattr(args, "label", "") or "source-intelligence-run").strip()
    input_value = {
        "inputs": inputs,
        "label": label,
        "outputDir": output_dir or None,
    }
    with open_db() as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        job = create_job(
            connection,
            workspace_id=workspace_id,
            kind=JOB_KIND,
            label=label,
            input_value=input_value,
            capability_id="cli.source-intelligence-job-run",
            now_iso=now_iso,
        )
        job = transition_job(
            connection,
            workspace_id=workspace_id,
            job_key=job["jobKey"],
            status=STATUS_QUEUED,
            progress=0,
            stage="queued",
            message="Source Intelligence job accepted by the local runtime.",
            now_iso=now_iso,
        )
        connection.commit()
    return {"ok": True, "accepted": True, "job": job}


def _artifact_refs(result: dict[str, Any]) -> list[dict[str, Any]]:
    output_dir = Path(str(result.get("outputDir") or ""))
    refs = []
    for name in result.get("evidenceFiles") or []:
        refs.append({"kind": "json", "label": str(name), "path": str(output_dir / str(name))})
    return refs


def _evidence_refs(result: dict[str, Any]) -> list[dict[str, Any]]:
    bundle = result.get("evidenceBundle")
    if not isinstance(bundle, dict):
        return []
    path = bundle.get("manifestPath") or bundle.get("bundleDir") or bundle.get("path") or bundle.get("bundlePath")
    return [{"kind": "evidence-bundle", "label": "Source Intelligence evidence", "path": str(path)}] if path else []


def source_intelligence_job_run_command(
    args: argparse.Namespace,
    *,
    source_intelligence_command: Callable[[argparse.Namespace], dict[str, Any]],
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    job_key = str(getattr(args, "job", "") or "").strip()
    if not job_key:
        raise ValueError("Job key is required.")
    with open_db() as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        job = get_job(connection, workspace_id=workspace_id, job_key=job_key, event_limit=20)
        if job["kind"] != JOB_KIND:
            raise ValueError(f"Job {job_key} is not a {JOB_KIND} job.")
        if job["status"] in TERMINAL_STATUSES:
            return {"ok": True, "changed": False, "job": job}
        if job["status"] == STATUS_CREATED:
            transition_job(
                connection,
                workspace_id=workspace_id,
                job_key=job_key,
                status=STATUS_QUEUED,
                stage="queued",
                now_iso=now_iso,
            )
        job = transition_job(
            connection,
            workspace_id=workspace_id,
            job_key=job_key,
            status=STATUS_RUNNING,
            progress=5,
            stage="source-discovery",
            message="Source Intelligence worker started.",
            now_iso=now_iso,
        )
        connection.commit()

    input_value = job.get("input") or {}
    run_args = argparse.Namespace(
        inputs=list(input_value.get("inputs") or []),
        label=input_value.get("label") or job["label"],
        output_dir=input_value.get("outputDir") or None,
        workspace=workspace_id,
    )
    try:
        with open_db() as connection:
            update_job_progress(
                connection,
                workspace_id=workspace_id,
                job_key=job_key,
                progress=15,
                stage="source-profiling",
                message="Profiling sources and inferring analytical structure.",
                now_iso=now_iso,
            )
            connection.commit()
        result = source_intelligence_command(run_args)
        with open_db() as connection:
            current = get_job(connection, workspace_id=workspace_id, job_key=job_key, event_limit=20)
            if current["status"] == STATUS_CANCEL_REQUESTED:
                final = transition_job(
                    connection,
                    workspace_id=workspace_id,
                    job_key=job_key,
                    status=STATUS_CANCELED,
                    stage="canceled",
                    message="Cancellation was observed before result publication.",
                    error={"code": "job-canceled", "reason": "cancel-requested"},
                    now_iso=now_iso,
                )
            else:
                final = transition_job(
                    connection,
                    workspace_id=workspace_id,
                    job_key=job_key,
                    status=STATUS_SUCCEEDED,
                    stage="completed",
                    message="Source Intelligence evidence was persisted.",
                    result=result,
                    artifact_refs=_artifact_refs(result),
                    evidence_refs=_evidence_refs(result),
                    source_run_id=str(result.get("runKey") or "") or None,
                    now_iso=now_iso,
                )
            connection.commit()
        return {"ok": True, "job": final, "result": result if final["status"] == STATUS_SUCCEEDED else None}
    except Exception as exc:
        with open_db() as connection:
            current = get_job(connection, workspace_id=workspace_id, job_key=job_key, event_limit=20)
            if current["status"] not in TERMINAL_STATUSES:
                target = STATUS_CANCELED if current["status"] == STATUS_CANCEL_REQUESTED else STATUS_FAILED
                final = transition_job(
                    connection,
                    workspace_id=workspace_id,
                    job_key=job_key,
                    status=target,
                    stage="canceled" if target == STATUS_CANCELED else "failed",
                    message="Source Intelligence worker did not complete.",
                    error={
                        "code": "job-canceled" if target == STATUS_CANCELED else "source-intelligence-failed",
                        "message": str(exc),
                        "type": type(exc).__name__,
                        "retryable": target == STATUS_FAILED,
                    },
                    now_iso=now_iso,
                )
                connection.commit()
            else:
                final = current
        return {
            "ok": final["status"] == STATUS_CANCELED,
            "job": final,
            "error": None if final["status"] == STATUS_CANCELED else str(exc),
        }


def job_process_exit_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    job_key = str(getattr(args, "job", "") or "").strip()
    with open_db() as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        current = get_job(connection, workspace_id=workspace_id, job_key=job_key, event_limit=20)
        if current["status"] in TERMINAL_STATUSES:
            return {"ok": True, "changed": False, "job": current}
        canceled = current["status"] == STATUS_CANCEL_REQUESTED
        final = transition_job(
            connection,
            workspace_id=workspace_id,
            job_key=job_key,
            status=STATUS_CANCELED if canceled else STATUS_FAILED,
            stage="canceled" if canceled else "worker-exit",
            message="The registered worker process exited before persisting a terminal result.",
            error={
                "code": "job-canceled" if canceled else "worker-exited",
                "exitCode": getattr(args, "exit_code", None),
                "signal": str(getattr(args, "signal", "") or "") or None,
                "retryable": not canceled,
            },
            event_type="job_worker_exit",
            now_iso=now_iso,
        )
        connection.commit()
    return {"ok": True, "changed": True, "job": final}
