from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from bi_cli_schema import ensure_schema  # noqa: E402
from job_runtime_service import (  # noqa: E402
    STATUS_CANCELED,
    STATUS_CANCEL_REQUESTED,
    STATUS_FAILED,
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_SUCCEEDED,
    create_job,
    get_job,
    input_fingerprint,
    list_job_events,
    list_jobs,
    recover_interrupted_jobs,
    request_job_cancel,
    transition_job,
    update_job_progress,
)


class Clock:
    def __init__(self) -> None:
        self.value = 0

    def now(self) -> str:
        self.value += 1
        return f"2026-07-14T00:00:{self.value:02d}+08:00"


def check(label: str, ok: bool, detail=None) -> dict:
    return {"label": label, "ok": bool(ok), "detail": detail}


def main() -> int:
    checks: list[dict] = []
    clock = Clock()
    with tempfile.TemporaryDirectory(prefix="aibi-c-job-runtime-") as temporary:
        database = Path(temporary) / "runtime.sqlite"
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        ensure_schema(connection)
        connection.execute(
            "INSERT INTO workspaces(id, name, current_source_run_id, created_at) VALUES('other', 'Other', NULL, ?)",
            (clock.now(),),
        )

        stable_a = input_fingerprint({"b": 2, "a": 1})
        stable_b = input_fingerprint({"a": 1, "b": 2})
        checks.append(check("canonical-input-fingerprint", stable_a == stable_b, stable_a))

        root_job = create_job(
            connection,
            workspace_id="default",
            kind="source-intelligence",
            label="Generate source evidence",
            input_value={"table": "orders", "limit": 50},
            source_run_id="source_run_orders",
            now_iso=clock.now,
        )
        queued = transition_job(
            connection,
            workspace_id="default",
            job_key=root_job["jobKey"],
            status=STATUS_QUEUED,
            stage="queue",
            now_iso=clock.now,
        )
        running = transition_job(
            connection,
            workspace_id="default",
            job_key=root_job["jobKey"],
            status=STATUS_RUNNING,
            stage="inspect",
            now_iso=clock.now,
        )
        progressed = update_job_progress(
            connection,
            workspace_id="default",
            job_key=root_job["jobKey"],
            progress=45,
            stage="profile",
            message="Fields profiled",
            payload={"fieldCount": 12},
            now_iso=clock.now,
        )
        succeeded = transition_job(
            connection,
            workspace_id="default",
            job_key=root_job["jobKey"],
            status=STATUS_SUCCEEDED,
            stage="verify",
            result={"tableCount": 1},
            artifact_refs=[{"type": "manifest", "path": "artifacts/source-manifest.json"}],
            evidence_refs=[{"type": "sourceRun", "id": "source_run_orders"}],
            now_iso=clock.now,
        )
        checks.extend([
            check("created-to-queued", queued["status"] == STATUS_QUEUED),
            check("queued-to-running", running["status"] == STATUS_RUNNING),
            check("progress-is-recorded", progressed["progress"] == 45 and progressed["stage"] == "profile"),
            check("success-is-terminal-and-complete", succeeded["status"] == STATUS_SUCCEEDED and succeeded["progress"] == 100),
            check("artifact-and-evidence-refs", len(succeeded["artifactRefs"]) == 1 and len(succeeded["evidenceRefs"]) == 1),
        ])

        invalid_transition_blocked = False
        try:
            transition_job(
                connection,
                workspace_id="default",
                job_key=root_job["jobKey"],
                status=STATUS_RUNNING,
                now_iso=clock.now,
            )
        except ValueError:
            invalid_transition_blocked = True
        checks.append(check("terminal-transition-is-blocked", invalid_transition_blocked))

        invalid_progress_blocked = False
        progress_job = create_job(
            connection,
            workspace_id="default",
            kind="relationship-validation",
            label="Validate relationships",
            input_value={},
            now_iso=clock.now,
        )
        transition_job(connection, workspace_id="default", job_key=progress_job["jobKey"], status=STATUS_QUEUED, now_iso=clock.now)
        transition_job(connection, workspace_id="default", job_key=progress_job["jobKey"], status=STATUS_RUNNING, now_iso=clock.now)
        update_job_progress(
            connection,
            workspace_id="default",
            job_key=progress_job["jobKey"],
            progress=60,
            stage="validate",
            message="Validated",
            now_iso=clock.now,
        )
        try:
            update_job_progress(
                connection,
                workspace_id="default",
                job_key=progress_job["jobKey"],
                progress=40,
                stage="validate",
                message="Backwards",
                now_iso=clock.now,
            )
        except ValueError:
            invalid_progress_blocked = True
        checks.append(check("progress-cannot-move-backwards", invalid_progress_blocked))

        cancel_job = create_job(
            connection,
            workspace_id="default",
            kind="evidence-export",
            label="Export evidence",
            input_value={},
            now_iso=clock.now,
        )
        transition_job(connection, workspace_id="default", job_key=cancel_job["jobKey"], status=STATUS_QUEUED, now_iso=clock.now)
        transition_job(connection, workspace_id="default", job_key=cancel_job["jobKey"], status=STATUS_RUNNING, now_iso=clock.now)
        cancel_requested = request_job_cancel(
            connection,
            workspace_id="default",
            job_key=cancel_job["jobKey"],
            reason="acceptance-test",
            now_iso=clock.now,
        )
        checks.append(check(
            "running-cancel-is-cooperative",
            cancel_requested["status"] == STATUS_CANCEL_REQUESTED and cancel_requested["cancelRequested"],
        ))

        recovery_job = create_job(
            connection,
            workspace_id="default",
            kind="dashboard-draft",
            label="Draft dashboard",
            input_value={},
            parent_job_key=root_job["jobKey"],
            now_iso=clock.now,
        )
        transition_job(connection, workspace_id="default", job_key=recovery_job["jobKey"], status=STATUS_QUEUED, now_iso=clock.now)
        transition_job(connection, workspace_id="default", job_key=recovery_job["jobKey"], status=STATUS_RUNNING, now_iso=clock.now)
        recovered = recover_interrupted_jobs(connection, workspace_id="default", now_iso=clock.now)
        recovered_by_key = {item["jobKey"]: item for item in recovered}
        checks.extend([
            check("running-job-recovers-as-failed", recovered_by_key[recovery_job["jobKey"]]["status"] == STATUS_FAILED),
            check("cancel-request-recovers-as-canceled", recovered_by_key[cancel_job["jobKey"]]["status"] == STATUS_CANCELED),
            check("parent-job-link-is-preserved", recovered_by_key[recovery_job["jobKey"]]["parentJobKey"] == root_job["jobKey"]),
        ])

        other_job = create_job(
            connection,
            workspace_id="other",
            kind="query",
            label="Other workspace query",
            input_value={},
            now_iso=clock.now,
        )
        default_jobs = list_jobs(connection, workspace_id="default", limit=100)
        checks.append(check(
            "workspace-isolation",
            other_job["jobKey"] not in {item["jobKey"] for item in default_jobs},
        ))

        events = list_job_events(connection, workspace_id="default", after_sequence=0, limit=500)
        sequences = [item["sequence"] for item in events]
        detail = get_job(connection, workspace_id="default", job_key=root_job["jobKey"])
        checks.extend([
            check("event-sequence-is-strictly-ordered", sequences == sorted(set(sequences))),
            check("job-detail-includes-events", len(detail["events"]) >= 5),
            check("recovery-event-is-auditable", any(item["type"] == "job_recovered" for item in events)),
        ])
        connection.commit()
        connection.close()

    failed = [item for item in checks if not item["ok"]]
    print(json.dumps({
        "ok": not failed,
        "schema": "aibi-job-runtime-verify/v1",
        "generatedBy": "scripts/verify-job-runtime.py",
        "checks": checks,
        "failedChecks": failed,
    }, ensure_ascii=False, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
