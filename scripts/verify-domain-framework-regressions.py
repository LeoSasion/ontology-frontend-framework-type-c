from __future__ import annotations

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
    CHECKS.append({"label": label, "ok": bool(ok), "detail": detail})


def run(arguments: list[str], env: dict[str, str]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "tools/bi_cli.py", "--json", *arguments],
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {"ok": False, "stdout": completed.stdout, "stderr": completed.stderr}
    payload["processExitCode"] = completed.returncode
    return payload


with tempfile.TemporaryDirectory(prefix="aibi-c-domain-regressions-") as temp_dir:
    temp = Path(temp_dir)
    source = temp / "source.csv"
    source.write_text("id,value\n1,10\n2,20\n", encoding="utf-8")
    env = {
        **os.environ,
        "AIBI_HYBRID_DB_PATH": str(temp / "metadata.sqlite"),
        "AIBI_HYBRID_DUCKDB_PATH": str(temp / "analytics.duckdb"),
        "AIBI_EVIDENCE_BUNDLE_ROOT": str(temp / "evidence"),
        "PYTHONIOENCODING": "utf-8",
    }
    created = run(["source-intelligence", "--label", "freshness-v1", "--output-dir", str(temp / "run-v1"), str(source)], env)
    current = run(["source-intelligence-runs", "--limit", "5"], env)
    source.write_text("id,value\n1,999\n2,20\n", encoding="utf-8")
    modified = run(["source-intelligence-runs", "--limit", "5"], env)
    modified_run = (modified.get("sourceIntelligenceRuns") or [{}])[0]
    check(
        "source-content-change-invalidates-evidence-run",
        created.get("ok") is True
        and (current.get("sourceIntelligenceRuns") or [{}])[0].get("freshness", {}).get("status") == "current"
        and modified_run.get("freshness", {}).get("status") == "stale"
        and "source" in modified_run.get("freshness", {}).get("mismatches", []),
        modified_run.get("freshness"),
    )
    source.unlink()
    deleted = run(["source-intelligence-runs", "--limit", "5"], env)
    deleted_run = (deleted.get("sourceIntelligenceRuns") or [{}])[0]
    check(
        "source-deletion-invalidates-evidence-run",
        deleted_run.get("freshness", {}).get("current", {}).get("source") == "missing"
        and deleted_run.get("freshness", {}).get("usableForPlanning") is False,
        deleted_run.get("freshness"),
    )

    source.write_text("id,value\n1,10\n2,20\n", encoding="utf-8")
    rerun = run(["source-intelligence", "--label", "freshness-v2", "--output-dir", str(temp / "run-v2"), str(source)], env)
    enabled = run(["domain-pack-set", "--pack", "platform-commerce", "--state", "enabled", "--yes"], env)
    doctor = run(["quality-doctor"], env)
    check(
        "stale-runs-never-feed-current-repair-guidance",
        rerun.get("ok") is True
        and enabled.get("confirmed") is True
        and doctor.get("latestSourceIntelligenceRun") is None
        and doctor.get("metricSql", {}).get("planned") == 0,
        {"latest": doctor.get("latestSourceIntelligenceRun"), "metricSql": doctor.get("metricSql")},
    )

    exported_path = temp / "config.json"
    exported = run(["export-config", str(exported_path)], env)
    run(["domain-pack-set", "--pack", "platform-commerce", "--state", "disabled", "--yes"], env)
    apply_preview = run(["apply-config", str(exported_path)], env)
    applied = run(["apply-config", str(exported_path), "--yes"], env)
    restored = run(["domain-packs"], env)
    exported_payload = json.loads(exported_path.read_text(encoding="utf-8")) if exported_path.is_file() else {}
    check(
        "domain-pack-state-is-config-portable",
        exported.get("ok") is True
        and "workspace_domain_packs" in (exported_payload.get("tables") or {})
        and apply_preview.get("requiresConfirmation") is True
        and applied.get("confirmed") is True
        and (restored.get("enabledDomainPacks") or [{}])[0].get("packId") == "platform-commerce",
        {"exportedTables": sorted((exported_payload.get("tables") or {}).keys()), "restored": restored.get("enabledDomainPacks")},
    )


sys.path.insert(0, str(ROOT / "tools"))
from agent_confirm_execution_handlers import handle_dashboard_create_confirmation  # noqa: E402


captured: list[tuple[Any, ...]] = []


def fallback_builder(*args: Any) -> dict[str, Any]:
    captured.append(args)
    return {
        "dashboardName": "Legacy draft",
        "defaultTableKey": "orders",
        "widgets": [],
        "layout": [],
        "widgetCount": 0,
        "templateCount": 0,
    }


with sqlite3.connect(":memory:") as connection:
    legacy_preview = handle_dashboard_create_confirmation(
        connection,
        {"action_key": "legacy", "status": "pending"},  # type: ignore[arg-type]
        {"tableKey": "orders", "prompt": "创建看板"},
        action_key="legacy",
        yes=False,
        confirmed_at="2026-07-15T00:00:00Z",
        workspace_id="workspace-legacy",
        unique_key=lambda prefix: prefix,
        build_agent_dashboard_create_draft=fallback_builder,
        write_business_dashboard=lambda *_args: {},
        upsert_navigation_module=lambda *_args, **_kwargs: None,
    )
check(
    "legacy-dashboard-fallback-preserves-workspace-id",
    legacy_preview.get("requiresConfirmation") is True
    and len(captured) == 1
    and captured[0][1:] == ("workspace-legacy", "orders", "创建看板", 8),
    [list(item[1:]) for item in captured],
)


failed = [item for item in CHECKS if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-domain-framework-regressions/v1",
    "generatedBy": "scripts/verify-domain-framework-regressions.py",
    "checks": CHECKS,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
