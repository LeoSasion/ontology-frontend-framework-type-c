from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "validation-inputs" / "orders.csv"

LOCK_HOLDER = r"""
import sys
import time
from pathlib import Path

sys.path.insert(0, sys.argv[1])
from workspace_mutation_lock_service import workspace_mutation_lock

lock_path = Path(sys.argv[2])
ready_path = Path(sys.argv[3])
with workspace_mutation_lock(lock_path, timeout_seconds=2.0):
    ready_path.write_text("locked", encoding="utf-8")
    time.sleep(float(sys.argv[4]))
"""

CREATE_WORKER = r"""
import argparse
import json
import sys

sys.path.insert(0, sys.argv[1])
from import_job_commands import _create_legacy_import_job_with_boundary, build_import_preview

result = _create_legacy_import_job_with_boundary(
    argparse.Namespace(
        workspace="default",
        import_kind="single",
        path=sys.argv[2],
        request_key="legacy-boundary-race-create",
        expected_plan=sys.argv[3],
        table="orders",
        name="Orders",
        mode="create",
        unique_fields=None,
        conflict_rule=None,
        no_recursive=False,
        limit=200,
        label="Legacy boundary race",
    ),
    build_import_preview,
)
print(json.dumps(result, ensure_ascii=False))
"""


def _wait_for(path: Path, process: subprocess.Popen[str], *, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            return
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise AssertionError(f"Lock holder exited before acquiring the boundary: {stdout}\n{stderr}")
        time.sleep(0.02)
    raise AssertionError("Timed out waiting for the restore boundary holder.")


def _payload(stdout: str, stderr: str, *, label: str, returncode: int) -> dict[str, Any]:
    try:
        value = json.loads(stdout.strip())
    except json.JSONDecodeError as error:
        raise AssertionError(f"{label} returned invalid JSON: {stderr}\n{stdout}") from error
    if returncode != 0 or value.get("ok") is not True:
        raise AssertionError(f"{label} failed: {stderr}\n{stdout}")
    return value


def main() -> int:
    checks: list[dict[str, Any]] = []

    def check(label: str, ok: object, detail: Any = None) -> None:
        checks.append({"label": label, "ok": bool(ok), "detail": detail})

    with tempfile.TemporaryDirectory(prefix="aibi-legacy-import-boundary-") as temp_dir:
        temp = Path(temp_dir)
        db_path = temp / "runtime.sqlite"
        duckdb_path = temp / "runtime.duckdb"
        lock_path = temp / ".aibi-cross-engine-writer.lock"
        env = {
            **os.environ,
            "AIBI_HYBRID_DB_PATH": str(db_path),
            "AIBI_HYBRID_DUCKDB_PATH": str(duckdb_path),
            "AIBI_EVIDENCE_BUNDLE_ROOT": str(temp / "evidence"),
            "AIBI_WORKSPACE_RECOVERY_ROOT": str(temp / "recovery"),
            "PYTHONIOENCODING": "utf-8",
        }

        def cli(*args: str) -> dict[str, Any]:
            completed = subprocess.run(
                [sys.executable, "tools/aibi_cli.py", "--json", *args],
                cwd=ROOT,
                env=env,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            return _payload(completed.stdout, completed.stderr, label="CLI", returncode=completed.returncode)

        preview = cli("preview-import", str(SOURCE), "--table", "orders")
        plan_fingerprint = str(preview.get("planFingerprint") or "")
        check("fixture-preview-has-a-frozen-plan", len(plan_fingerprint) == 64, plan_fingerprint)

        preview_ready = temp / "preview-lock-ready"
        preview_holder = subprocess.Popen(
            [sys.executable, "-c", LOCK_HOLDER, str(ROOT / "tools"), str(lock_path), str(preview_ready), "1.0"],
            cwd=ROOT,
            env=env,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _wait_for(preview_ready, preview_holder)
        preview_process = subprocess.Popen(
            [sys.executable, "tools/aibi_cli.py", "--json", "import-commit", str(SOURCE), "--table", "orders"],
            cwd=ROOT,
            env=env,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(0.2)
        check(
            "legacy-preview-cannot-cross-a-restore-exclusive-lock",
            preview_process.poll() is None and preview_holder.poll() is None,
            {"previewExit": preview_process.poll(), "holderExit": preview_holder.poll()},
        )
        preview_holder_stdout, preview_holder_stderr = preview_holder.communicate(timeout=3)
        check(
            "restore-lock-holder-exits-cleanly-after-preview-race",
            preview_holder.returncode == 0,
            {"stdout": preview_holder_stdout, "stderr": preview_holder_stderr},
        )
        preview_stdout, preview_stderr = preview_process.communicate(timeout=5)
        legacy_preview = _payload(
            preview_stdout,
            preview_stderr,
            label="legacy preview",
            returncode=int(preview_process.returncode or 0),
        )
        check(
            "legacy-preview-runs-only-after-restore-releases-the-boundary",
            legacy_preview.get("requiresConfirmation") is True
            and legacy_preview.get("planFingerprint") == plan_fingerprint,
            {
                "requiresConfirmation": legacy_preview.get("requiresConfirmation"),
                "planFingerprint": legacy_preview.get("planFingerprint"),
            },
        )

        create_ready = temp / "create-lock-ready"
        create_holder = subprocess.Popen(
            [sys.executable, "-c", LOCK_HOLDER, str(ROOT / "tools"), str(lock_path), str(create_ready), "1.0"],
            cwd=ROOT,
            env=env,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _wait_for(create_ready, create_holder)
        create_process = subprocess.Popen(
            [sys.executable, "-c", CREATE_WORKER, str(ROOT / "tools"), str(SOURCE), plan_fingerprint],
            cwd=ROOT,
            env=env,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(0.2)
        with closing(sqlite3.connect(db_path)) as connection:
            job_count_while_restore_owns_lock = int(connection.execute("SELECT COUNT(*) FROM analysis_jobs").fetchone()[0])
        check(
            "legacy-job-create-cannot-persist-through-a-restore-exclusive-lock",
            create_process.poll() is None
            and create_holder.poll() is None
            and job_count_while_restore_owns_lock == 0,
            {
                "createExit": create_process.poll(),
                "holderExit": create_holder.poll(),
                "jobCount": job_count_while_restore_owns_lock,
            },
        )
        create_holder_stdout, create_holder_stderr = create_holder.communicate(timeout=3)
        check(
            "restore-lock-holder-exits-cleanly-after-create-race",
            create_holder.returncode == 0,
            {"stdout": create_holder_stdout, "stderr": create_holder_stderr},
        )
        create_stdout, create_stderr = create_process.communicate(timeout=5)
        created = _payload(
            create_stdout,
            create_stderr,
            label="legacy create boundary",
            returncode=int(create_process.returncode or 0),
        )
        job = created.get("job") if isinstance(created.get("job"), dict) else {}
        job_key = str(job.get("jobKey") or "")
        check(
            "legacy-job-create-persists-one-queued-job-after-restore-releases",
            bool(job_key) and job.get("status") == "queued",
            {"jobKey": job_key, "status": job.get("status")},
        )
        with closing(sqlite3.connect(db_path)) as connection:
            persisted_job_count = int(connection.execute("SELECT COUNT(*) FROM analysis_jobs").fetchone()[0])
        check("legacy-job-create-persists-exactly-once", persisted_job_count == 1, persisted_job_count)

        executed = cli("import-job-run", "--workspace", "default", "--job", job_key)
        result = executed.get("result") if isinstance(executed.get("result"), dict) else {}
        check(
            "persisted-job-runs-through-the-existing-durable-activation-lifecycle",
            executed.get("job", {}).get("status") == "succeeded"
            and bool(result.get("activationJournalKey"))
            and duckdb_path.is_file(),
            {
                "status": executed.get("job", {}).get("status"),
                "activationJournalKey": result.get("activationJournalKey"),
                "duckdbExists": duckdb_path.is_file(),
            },
        )

    failed = [item for item in checks if not item["ok"]]
    print(json.dumps({
        "ok": not failed,
        "schema": "aibi-legacy-import-boundary-verify/v1",
        "generatedBy": "scripts/verify-legacy-import-boundary.py",
        "checks": checks,
        "failedChecks": failed,
    }, ensure_ascii=False, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
