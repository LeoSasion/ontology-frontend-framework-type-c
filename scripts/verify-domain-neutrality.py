from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CHECKS: list[dict[str, Any]] = []
FORBIDDEN_CORE_TERMS = {
    "order_id", "refund_id", "paid_gmv", "net_sales", "refund_amount",
    "cost_amount", "inventory_qty", "channel", "sku", "shop",
}


def check(label: str, ok: bool, detail: Any = None) -> None:
    CHECKS.append({"label": label, "ok": bool(ok), "detail": None if ok else detail})


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
        payload = json.loads(completed.stdout.strip() or "{}")
    except json.JSONDecodeError:
        payload = {"ok": False, "stdout": completed.stdout, "stderr": completed.stderr}
    payload["processExitCode"] = completed.returncode
    return payload


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


with tempfile.TemporaryDirectory(prefix="aibi-c-neutrality-") as temp_dir_value:
    temp_dir = Path(temp_dir_value)
    env = os.environ.copy()
    env["AIBI_HYBRID_DB_PATH"] = str(temp_dir / "metadata.sqlite")
    env["AIBI_HYBRID_DUCKDB_PATH"] = str(temp_dir / "analytics.duckdb")
    env["AIBI_EVIDENCE_BUNDLE_ROOT"] = str(temp_dir / "evidence")
    env["PYTHONIOENCODING"] = "utf-8"

    neutral_csv = temp_dir / "sensor-observations.csv"
    neutral_csv.write_text(
        "sensor_id,observed_at,region,temperature,vibration,state\n"
        "S-01,2026-07-01T08:00:00Z,north,22.4,0.12,normal\n"
        "S-02,2026-07-01T08:05:00Z,south,28.1,0.31,review\n"
        "S-03,2026-07-01T08:10:00Z,north,24.8,0.18,normal\n",
        encoding="utf-8",
    )
    commerce_csv = temp_dir / "commerce.csv"
    commerce_csv.write_text(
        "order_id,channel,paid_gmv,refund_amount,paid_at\n"
        "O-1,alpha,120,0,2026-07-01\n"
        "O-2,beta,80,10,2026-07-02\n",
        encoding="utf-8",
    )

    check("runtime-initializes", run(["status"], env).get("ok") is True)
    neutral_import = run([
        "import-commit", str(neutral_csv), "--table", "sensor_observations",
        "--name", "Sensor observations", "--mode", "create", "--yes",
    ], env)
    check("neutral-source-imports", neutral_import.get("committed") is True, neutral_import)

    neutral_output = temp_dir / "neutral-profile"
    neutral_run = run([
        "source-intelligence", str(neutral_csv), "--output-dir", str(neutral_output),
        "--label", "neutral-sensor-domain",
    ], env)
    neutral_manifest = neutral_run.get("manifest") if isinstance(neutral_run.get("manifest"), dict) else {}
    neutral_fields = read_json(neutral_output / "semantic-field-candidates.json").get("fields", [])
    neutral_semantics = {
        str(item.get("semantic"))
        for item in neutral_fields
        if isinstance(item, dict) and item.get("semantic")
    }
    check(
        "core-starts-with-no-domain-knowledge",
        neutral_manifest.get("enabledDomainPacks") == [] and not (neutral_semantics & FORBIDDEN_CORE_TERMS),
        {"semantics": sorted(neutral_semantics), "enabled": neutral_manifest.get("enabledDomainPacks")},
    )
    fingerprint_keys = ["sourceFingerprint", "workspaceSchemaFingerprint", "workspaceDataFingerprint", "domainPackFingerprint"]
    check(
        "source-run-captures-all-fingerprint-layers",
        all(isinstance(neutral_manifest.get(key), str) and len(neutral_manifest[key]) == 64 for key in fingerprint_keys),
        {key: neutral_manifest.get(key) for key in fingerprint_keys},
    )
    neutral_catalog = run(["dashboard-widget-catalog"], env)
    neutral_draft = run(["business-dashboard", "--op", "draft", "--table", "sensor_observations"], env)
    check(
        "neutral-runtime-does-not-expose-erp-library",
        "erpUnitLibrary" not in neutral_catalog
        and "erpUnitLibrary" not in (neutral_draft.get("draft") or {})
        and (neutral_draft.get("draft") or {}).get("templateKey") == "business",
        {"catalogKeys": sorted(neutral_catalog), "draft": neutral_draft.get("draft")},
    )
    disabled_erp_catalog = run(["erp-unit-library", "--summary"], env)
    disabled_erp_draft = run([
        "business-dashboard", "--op", "draft", "--template", "erp-units",
        "--table", "sensor_observations",
    ], env)
    check(
        "disabled-pack-blocks-direct-erp-entry-points",
        disabled_erp_catalog.get("available") is False
        and disabled_erp_catalog.get("reason") == "domain-pack-not-enabled"
        and disabled_erp_draft.get("ok") is False
        and disabled_erp_draft.get("processExitCode") != 0
        and "not enabled" in str(disabled_erp_draft.get("error") or ""),
        {"catalog": disabled_erp_catalog, "dashboard": disabled_erp_draft},
    )

    neutral_query = run([
        "query", "--table", "sensor_observations", "--group", "region",
        "--measure", "temperature", "--agg", "avg", "--request", "Average temperature by region",
    ], env)
    receipt = neutral_query.get("queryPlanReceipt") if isinstance(neutral_query.get("queryPlanReceipt"), dict) else {}
    check(
        "query-receipt-binds-data-and-pack-fingerprints",
        len(str((receipt.get("source") or {}).get("dataFingerprint") or "")) == 64
        and len(str(receipt.get("domainPackFingerprint") or "")) == 64
        and receipt.get("domainPacks") == [],
        receipt,
    )

    enabled_platform = run(["domain-pack-set", "--pack", "platform-commerce", "--state", "enabled", "--yes"], env)
    check("platform-pack-enables-explicitly", enabled_platform.get("confirmed") is True, enabled_platform)
    stale_runs = run(["source-intelligence-runs", "--limit", "5"], env)
    prior_run = next((
        item for item in stale_runs.get("sourceIntelligenceRuns", [])
        if isinstance(item, dict) and item.get("run_key") == neutral_run.get("runKey")
    ), {})
    check(
        "pack-change-invalidates-prior-planning-evidence",
        prior_run.get("freshness", {}).get("status") == "stale"
        and "domainPacks" in prior_run.get("freshness", {}).get("mismatches", [])
        and prior_run.get("fileCoverage", {}).get("complete") is False,
        prior_run,
    )

    commerce_import = run([
        "import-commit", str(commerce_csv), "--table", "commerce_events",
        "--name", "Commerce events", "--mode", "create", "--yes",
    ], env)
    check("pack-fixture-imports", commerce_import.get("committed") is True, commerce_import)
    commerce_output = temp_dir / "commerce-profile"
    commerce_run = run([
        "source-intelligence", str(commerce_csv), "--output-dir", str(commerce_output),
        "--label", "platform-pack-enabled",
    ], env)
    commerce_manifest = commerce_run.get("manifest") if isinstance(commerce_run.get("manifest"), dict) else {}
    commerce_fields = read_json(commerce_output / "semantic-field-candidates.json").get("fields", [])
    commerce_semantics = {
        str(item.get("semantic"))
        for item in commerce_fields
        if isinstance(item, dict) and item.get("semantic")
    }
    check(
        "enabled-pack-contributes-domain-semantics",
        any(item.get("packId") == "platform-commerce" for item in commerce_manifest.get("enabledDomainPacks", []) if isinstance(item, dict))
        and {"order_id", "paid_gmv", "refund_amount"}.issubset(commerce_semantics),
        {"semantics": sorted(commerce_semantics), "enabled": commerce_manifest.get("enabledDomainPacks")},
    )

    erp_default = run([
        "domain-pack-set", "--workspace", "default", "--pack", "erp-units", "--state", "enabled", "--yes",
    ], env)
    isolated = run(["workspace-create", "--name", "Isolated neutral", "--yes"], env)
    isolated_id = str((isolated.get("created") or {}).get("id") or "")
    isolated_import = run([
        "import-commit", str(neutral_csv), "--table", "sensor_observations",
        "--name", "Isolated sensors", "--mode", "create", "--yes",
    ], env)
    default_selected = run(["workspace-select", "default", "--yes"], env)
    explicit_isolated_ask = run(["ask", "--workspace", isolated_id, "请基于当前表创建 ERP 分析看板草案"], env)
    isolated_selected = run(["workspace-select", isolated_id, "--yes"], env)
    isolated_actions = run(["action-drafts", "--all", "--limit", "10"], env)
    isolated_action_key = str((explicit_isolated_ask.get("actionDraft") or {}).get("actionKey") or "")
    isolated_action = next((
        item for item in isolated_actions.get("actionDrafts", [])
        if isinstance(item, dict) and item.get("action_key") == isolated_action_key
    ), {})
    isolated_draft = ((isolated_action.get("payload") or {}).get("dashboardDraft") or {})
    isolated_context = explicit_isolated_ask.get("domainPacks") or {}
    check(
        "explicit-workspace-never-inherits-default-pack-state",
        erp_default.get("confirmed") is True
        and bool(isolated_id)
        and isolated_import.get("committed") is True
        and default_selected.get("confirmed") is True
        and isolated_selected.get("confirmed") is True
        and isolated_context.get("enabledDomainPacks") == []
        and isolated_draft.get("templateKey") != "erp-units"
        and isolated_draft.get("defaultTableKey") == "sensor_observations",
        {
            "workspace": isolated_id,
            "context": isolated_context,
            "draft": isolated_draft,
            "actionKey": isolated_action_key,
            "actions": isolated_actions,
            "askSummary": {
                "ok": explicit_isolated_ask.get("ok"),
                "processExitCode": explicit_isolated_ask.get("processExitCode"),
                "error": explicit_isolated_ask.get("error"),
                "actionDraft": explicit_isolated_ask.get("actionDraft"),
                "domainPacks": explicit_isolated_ask.get("domainPacks"),
            },
            "defaultSelected": default_selected,
            "isolatedSelected": isolated_selected,
        },
    )

failed = [item for item in CHECKS if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-domain-neutrality-verify/v1",
    "generatedBy": "scripts/verify-domain-neutrality.py",
    "checks": CHECKS,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
