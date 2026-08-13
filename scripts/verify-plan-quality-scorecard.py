from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CHECKS: list[dict[str, Any]] = []


def check(label: str, ok: bool, detail: Any = None) -> None:
    CHECKS.append({"label": label, "ok": bool(ok), "detail": None if ok else detail})


def run(arguments: list[str], env: dict[str, str], expected: int = 0) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "tools/aibi_cli.py", "--json", *arguments],
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout.strip() or "{}")
    except json.JSONDecodeError:
        payload = {"ok": False, "stdout": completed.stdout, "stderr": completed.stderr}
    payload["processExitCode"] = completed.returncode
    payload["expectedExitCode"] = expected
    return payload


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


with tempfile.TemporaryDirectory(prefix="aibi-plan-quality-", ignore_cleanup_errors=True) as temp_value:
    temp_dir = Path(temp_value)
    sqlite_path = temp_dir / "runtime.sqlite"
    env = {
        **os.environ,
        "AIBI_HYBRID_DB_PATH": str(sqlite_path),
        "AIBI_HYBRID_DUCKDB_PATH": str(temp_dir / "runtime.duckdb"),
        "AIBI_WORKSPACE_RECOVERY_ROOT": str(temp_dir / "workspace-recovery"),
        "PYTHONIOENCODING": "utf-8",
    }

    status = run(["status"], env)
    schema_version = ((status.get("schemaVersions") or {}).get("sqlite") or {}).get("current")
    if schema_version is None:
        schema_version = (status.get("runtime") or {}).get("sqliteSchemaVersion")
    with sqlite3.connect(sqlite_path) as connection:
        pragma_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        tables = {str(row[0]) for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    check("schema-v16-plan-quality-store-boots", status.get("ok") is True and pragma_version == 16 and "plan_quality_scorecards" in tables, {"status": status, "pragma": pragma_version})

    cases = run(["business-expression-cases"], env)
    case_items = cases.get("cases") or []
    categories = {str(item.get("category")) for item in case_items if isinstance(item, dict)}
    serialized_cases = json.dumps(case_items, ensure_ascii=False).casefold()
    check(
        "case-catalog-is-bounded-versioned-and-non-executable",
        cases.get("ok") is True
        and cases.get("bounded") is True
        and cases.get("executableContentAllowed") is False
        and cases.get("caseCount") == 15
        and all(item.get("schema") == "aibi-business-expression-case/v1" and len(str(item.get("fingerprint") or "")) == 64 for item in case_items)
        and not any(token in serialized_cases for token in ('"sql"', '"code"', '"url"', '"tool"', 'c:\\users\\')),
        cases,
    )
    check(
        "case-catalog-covers-required-business-expression-classes",
        {"synonym", "same-name", "ratio", "distinct-entity", "status", "time", "cross-table", "pack-isolation"}.issubset(categories),
        sorted(categories),
    )

    before = digest(sqlite_path)
    cases_again = run(["business-expression-cases"], env)
    after = digest(sqlite_path)
    check("case-catalog-read-does-not-write-runtime", cases_again.get("fingerprint") == cases.get("fingerprint") and before == after, {"before": before, "after": after})

    evaluation = run(["plan-quality-evaluate"], env)
    scorecard = evaluation.get("scorecard") or {}
    metrics = scorecard.get("metrics") or {}
    check(
        "deterministic-scorecard-meets-every-release-gate",
        evaluation.get("ok") is True
        and evaluation.get("status") == "passed"
        and scorecard.get("releaseReady") is True
        and all((scorecard.get("thresholdChecks") or {}).values())
        and all((scorecard.get("zeroToleranceChecks") or {}).values())
        and all((scorecard.get("invarianceChecks") or {}).values())
        and metrics.get("coreSlotAccuracy") >= 0.95
        and metrics.get("fieldBindingPrecision") >= 0.98
        and metrics.get("safeClarificationRate") >= 0.90
        and metrics.get("evidenceCoverage") == 1.0
        and metrics.get("replayConsistency") == 1.0,
        evaluation,
    )
    check(
        "evaluation-keeps-provider-data-and-business-state-outside-boundary",
        evaluation.get("deterministicAuthority") is True
        and evaluation.get("providerUsed") is False
        and evaluation.get("businessRowsRead") == 0
        and evaluation.get("businessStateWrites") == 0
        and all(metrics.get(key) == 0 for key in ("silentDisambiguationCount", "permissionEscalationCount", "crossWorkspaceLeakCount", "domainPackLeakCount")),
        evaluation,
    )
    serialized_scorecard = json.dumps(scorecard, ensure_ascii=False).casefold()
    check(
        "persisted-scorecard-is-redacted-and-has-no-business-expression-or-row-payload",
        not any(token in serialized_scorecard for token in ('"expression"', '"rows"', '"rawrows"', '"prompt"', 'apikey', 'c:\\users\\')),
        serialized_scorecard[:1200],
    )

    listed = run(["plan-quality-scorecards", "--limit", "5"], env)
    latest = listed.get("latestCurrent") or {}
    check(
        "current-scorecard-is-listable-and-release-usable",
        listed.get("count") == 1
        and latest.get("scorecardKey") == scorecard.get("scorecardKey")
        and latest.get("current") is True
        and latest.get("usableForRelease") is True,
        listed,
    )
    with sqlite3.connect(sqlite_path) as connection:
        before_list = connection.execute("SELECT COUNT(*), MAX(created_at) FROM plan_quality_scorecards").fetchone()
    run(["plan-quality-scorecards", "--limit", "5"], env)
    with sqlite3.connect(sqlite_path) as connection:
        after_list = connection.execute("SELECT COUNT(*), MAX(created_at) FROM plan_quality_scorecards").fetchone()
    check("scorecard-list-is-read-only", before_list == after_list, {"before": before_list, "after": after_list})

    created = run(["workspace-create", "--name", "quality-isolation", "--yes"], env)
    isolated_id = str((created.get("created") or {}).get("id") or "")
    isolated = run(["plan-quality-scorecards", "--workspace", isolated_id, "--limit", "5"], env)
    check("scorecards-are-workspace-isolated", bool(isolated_id) and isolated.get("count") == 0 and isolated.get("workspaceId") == isolated_id, {"created": created, "isolated": isolated})

    isolated_evaluation = run(["plan-quality-evaluate", "--workspace", isolated_id], env)
    selected_default = run(["workspace-select", "default", "--yes"], env)
    delete_request_key = "plan-quality-isolated-workspace-delete"
    delete_preview = run([
        "workspace-delete", isolated_id,
        "--request-key", delete_request_key,
    ], env)
    deleted = run([
        "workspace-delete", isolated_id,
        "--request-key", delete_request_key,
        "--expected-plan", str((delete_preview.get("deletePlan") or {}).get("planFingerprint") or ""),
        "--yes",
    ], env)
    with sqlite3.connect(sqlite_path) as connection:
        orphan_count = int(connection.execute("SELECT COUNT(*) FROM plan_quality_scorecards WHERE workspace_id = ?", (isolated_id,)).fetchone()[0])
    check(
        "workspace-delete-removes-plan-quality-evidence",
        isolated_evaluation.get("ok") is True
        and (selected_default.get("workspace") or {}).get("id") == "default"
        and deleted.get("confirmed") is True
        and orphan_count == 0,
        {"evaluation": isolated_evaluation, "selectedDefault": selected_default, "deleted": deleted, "orphanCount": orphan_count},
    )

    with sqlite3.connect(sqlite_path) as connection:
        connection.execute("UPDATE plan_quality_scorecards SET runtime_fingerprint = ? WHERE workspace_id = 'default'", ("0" * 64,))
        connection.commit()
    stale = run(["plan-quality-scorecards", "--limit", "5"], env)
    stale_item = (stale.get("scorecards") or [{}])[0]
    check(
        "runtime-drift-never-falls-back-to-stale-release-input",
        stale_item.get("current") is False
        and stale_item.get("usableForRelease") is False
        and "runtimeFingerprint" in ((stale_item.get("freshness") or {}).get("mismatches") or [])
        and stale.get("latestCurrent") is None,
        stale,
    )

    contract = run(["cli-contract"], env)
    commands = ((contract.get("contract") or {}).get("commands") or [])
    by_name = {item.get("name"): item for item in commands if isinstance(item, dict)}
    check(
        "cli-contract-separates-read-only-catalogs-from-runtime-evaluation-write",
        by_name.get("business-expression-cases", {}).get("mutationMode") == "read-only"
        and by_name.get("plan-quality-scorecards", {}).get("mutationMode") == "read-only"
        and by_name.get("plan-quality-evaluate", {}).get("mutationMode") == "runtime-receipt"
        and by_name.get("plan-quality-evaluate", {}).get("requiresYes") is False,
        {name: by_name.get(name) for name in ("business-expression-cases", "plan-quality-scorecards", "plan-quality-evaluate")},
    )


failed = [item for item in CHECKS if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-plan-quality-scorecard-verify/v1",
    "generatedBy": "scripts/verify-plan-quality-scorecard.py",
    "checks": CHECKS,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
