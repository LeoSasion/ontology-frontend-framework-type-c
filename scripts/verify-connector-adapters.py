from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VERIFY_DIR = Path(tempfile.mkdtemp(prefix="aibi-connector-adapter-"))
DB_PATH = VERIFY_DIR / "runtime.sqlite"
SOURCE_PATH = VERIFY_DIR / "connector-source.csv"
SECRET_VALUE = "M11_LITERAL_SECRET_MUST_NEVER_ESCAPE"
ENV = {
    **os.environ,
    "AIBI_HYBRID_DB_PATH": str(DB_PATH),
    "AIBI_HYBRID_DUCKDB_PATH": str(VERIFY_DIR / "runtime.duckdb"),
    "AIBI_EVIDENCE_BUNDLE_ROOT": str(VERIFY_DIR / "evidence"),
    "AIBI_TEST_CONNECTOR_SECRET": SECRET_VALUE,
    "PYTHONIOENCODING": "utf-8",
}
checks: list[dict[str, Any]] = []


def check(label: str, ok: bool, detail: Any = None) -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": detail})


def run(label: str, arguments: list[str], expected_status: int = 0) -> dict[str, Any]:
    completed = subprocess.run(
        ["python", "tools/bi_cli.py", "--json", *arguments],
        cwd=ROOT,
        env=ENV,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    try:
        parsed = json.loads(completed.stdout.strip())
    except json.JSONDecodeError:
        parsed = None
    status_ok = completed.returncode == expected_status
    payload_ok = expected_status != 0 or bool(parsed and parsed.get("ok") is True)
    check(label, status_ok and payload_ok, {
        "status": completed.returncode,
        "stderr": completed.stderr[-800:],
        "stdout": completed.stdout[-800:] if not (status_ok and payload_ok) else "",
    })
    return {"status": completed.returncode, "parsed": parsed, "stderr": completed.stderr, "stdout": completed.stdout}


def connector_state() -> list[tuple[Any, ...]]:
    with sqlite3.connect(DB_PATH) as connection:
        return connection.execute(
            "SELECT workspace_id, connector_key, config_json, last_sync_at, last_sync_status, last_sync_result_json FROM data_connectors ORDER BY workspace_id, connector_key"
        ).fetchall()


def table_count() -> int:
    with sqlite3.connect(DB_PATH) as connection:
        return int(connection.execute("SELECT COUNT(*) FROM table_registry").fetchone()[0])


try:
    SOURCE_PATH.write_text(
        "order_id,channel,amount\n"
        "o-1,Direct,12.5\n"
        "o-2,Partner,9\n"
        "o-3,Direct,20\n",
        encoding="utf-8",
    )

    adapters = run("adapter-contracts", ["list-connector-adapters"])["parsed"] or {}
    adapter_rows = adapters.get("adapters") or []
    local_adapter = next((item for item in adapter_rows if item.get("connectorType") == "file"), {})
    unavailable = [item for item in adapter_rows if item.get("connectorType") in {"api", "erp", "database"}]
    check(
        "adapter-permissions-are-explicit-and-networkless",
        local_adapter.get("available") is True
        and local_adapter.get("operations") == ["metadata-discovery", "bounded-preview", "sync-plan"]
        and local_adapter.get("permissions", {}).get("network") == "none"
        and local_adapter.get("permissions", {}).get("arbitrarySql") is False
        and all(item.get("available") is False and item.get("permissions", {}).get("network") == "none" for item in unavailable),
        adapter_rows,
    )

    save_preview = run("file-connector-save-preview", [
        "save-connector", "--name", "M11 Local", "--type", "file", "--status", "active",
        "--endpoint", str(SOURCE_PATH), "--target-table", "m11_orders",
    ])["parsed"] or {}
    check(
        "connector-save-remains-dry-run-confirm",
        save_preview.get("dryRun") is True
        and save_preview.get("requiresConfirmation") is True
        and not save_preview.get("proposed", {}).get("config", {}).get("credentialConfigured"),
    )
    saved = run("file-connector-save-confirm", [
        "save-connector", "--name", "M11 Local", "--type", "file", "--status", "active",
        "--endpoint", str(SOURCE_PATH), "--target-table", "m11_orders", "--yes",
    ])["parsed"] or {}
    connector_key = str(saved.get("savedConnector") or "")
    check("connector-created", bool(connector_key))

    isolated_workspace = run("create-isolated-workspace", ["workspace-create", "--name", "M11 Isolated", "--yes"])["parsed"] or {}
    isolated_workspace_id = str((isolated_workspace.get("created") or {}).get("id") or "")
    isolated_list_before = run("connector-hidden-in-other-workspace", ["list-connectors"])["parsed"] or {}
    isolated_saved = run("same-connector-key-allowed-in-other-workspace", [
        "save-connector", "--name", "M11 Local", "--type", "file", "--status", "active",
        "--endpoint", str(SOURCE_PATH), "--target-table", "isolated_orders", "--yes",
    ])["parsed"] or {}
    with sqlite3.connect(DB_PATH) as connection:
        same_key_rows = int(connection.execute(
            "SELECT COUNT(*) FROM data_connectors WHERE connector_key = ?",
            (connector_key,),
        ).fetchone()[0])
    run("return-to-default-workspace", ["workspace-select", "default", "--yes"])
    default_list = run("default-workspace-connector-visible", ["list-connectors"])["parsed"] or {}
    check(
        "connectors-are-workspace-isolated",
        bool(isolated_workspace_id)
        and isolated_list_before.get("count") == 0
        and isolated_saved.get("savedConnector") == connector_key
        and same_key_rows == 2
        and default_list.get("count") == 1
        and default_list.get("connectors", [])[0].get("workspaceId") == "default",
        {"isolatedWorkspace": isolated_workspace_id, "sameKeyRows": same_key_rows, "defaultCount": default_list.get("count")},
    )

    before_read_only = connector_state()
    discovered = run("metadata-discovery", ["discover-connector", "--connector", connector_key])["parsed"] or {}
    previewed = run("bounded-preview", ["preview-connector", "--connector", connector_key, "--limit", "2"])["parsed"] or {}
    planned = run("sync-plan", ["plan-connector-sync", "--connector", connector_key])["parsed"] or {}
    sync_preview = run("legacy-sync-now-reuses-plan", ["sync-connector", "--connector", connector_key])["parsed"] or {}
    after_read_only = connector_state()

    adapter_payload_text = json.dumps([discovered, previewed, planned, sync_preview], ensure_ascii=False)
    check(
        "metadata-discovery-is-fingerprinted-and-path-redacted",
        discovered.get("operation") == "metadata-discovery"
        and discovered.get("metadata", {}).get("resource", {}).get("label") == SOURCE_PATH.name
        and len(str(discovered.get("metadata", {}).get("resource", {}).get("sha256") or "")) == 64
        and str(VERIFY_DIR) not in adapter_payload_text,
    )
    check(
        "preview-is-bounded-and-scalar",
        previewed.get("operation") == "bounded-preview"
        and previewed.get("preview", {}).get("returnedRows") == 2
        and previewed.get("preview", {}).get("truncated") is True
        and previewed.get("preview", {}).get("columns") == ["order_id", "channel", "amount"],
        previewed.get("preview"),
    )
    check(
        "sync-plan-is-read-only-and-confirmation-bound",
        planned.get("operation") == "sync-plan"
        and planned.get("dryRun") is True
        and planned.get("requiresConfirmation") is True
        and planned.get("sideEffects", {}).get("businessDatabaseWrite") is False
        and planned.get("syncPlan", {}).get("writeBoundary", {}).get("requiresConfirmation") is True
        and sync_preview.get("planFingerprint") == planned.get("planFingerprint"),
    )
    check("adapter-read-operations-do-not-write-connector-state", before_read_only == after_read_only)

    before_tables = table_count()
    confirmed_sync = run("confirmed-sync", ["sync-connector", "--connector", connector_key, "--yes"])["parsed"] or {}
    check(
        "confirmed-sync-reuses-reviewed-adapter-plan",
        confirmed_sync.get("confirmed") is True
        and confirmed_sync.get("connectorSync", {}).get("adapter", {}).get("planFingerprint") == planned.get("planFingerprint")
        and table_count() == before_tables + 1,
        confirmed_sync.get("connectorSync"),
    )

    literal_secret = run("literal-credential-rejected", [
        "save-connector", "--name", "Unsafe Literal", "--type", "api", "--endpoint", "https://example.invalid",
        "--credential-ref", SECRET_VALUE, "--yes",
    ], expected_status=1)
    check("literal-credential-is-not-persisted-or-returned", SECRET_VALUE not in json.dumps(connector_state(), ensure_ascii=False) and SECRET_VALUE not in literal_secret["stdout"])

    api_saved = run("env-reference-registration", [
        "save-connector", "--name", "Disabled API", "--type", "api", "--endpoint", "https://example.invalid/data",
        "--credential-ref", "env:AIBI_TEST_CONNECTOR_SECRET", "--yes",
    ])["parsed"] or {}
    api_key = str(api_saved.get("savedConnector") or "")
    public_list = run("credential-redacted-list", ["list-connectors"])["parsed"] or {}
    public_text = json.dumps(public_list, ensure_ascii=False)
    check(
        "credential-value-and-reference-stay-server-side",
        api_key
        and SECRET_VALUE not in public_text
        and "env:AIBI_TEST_CONNECTOR_SECRET" not in public_text
        and any(item.get("connectorKey") == api_key and item.get("config", {}).get("credentialConfigured") is True for item in public_list.get("connectors") or []),
    )
    before_api_block = connector_state()
    api_block = run("unavailable-api-adapter-blocked", ["discover-connector", "--connector", api_key], expected_status=1)["parsed"] or {}
    after_api_block = connector_state()
    check(
        "unavailable-adapter-grants-no-network-or-write-authority",
        api_block.get("blocked") is True
        and api_block.get("adapter", {}).get("permissions", {}).get("network") == "none"
        and api_block.get("sideEffects", {}).get("businessDatabaseWrite") is False
        and before_api_block == after_api_block,
    )

    forbidden_dir = VERIFY_DIR / "AIBI-D"
    forbidden_dir.mkdir()
    forbidden_file = forbidden_dir / "forbidden.csv"
    forbidden_file.write_text("id,value\n1,2\n", encoding="utf-8")
    cross_repo = run("cross-repository-path-blocked", [
        "save-connector", "--name", "Cross Repo", "--type", "file", "--endpoint", str(forbidden_file), "--yes",
    ], expected_status=1)
    check(
        "cross-repository-path-rejected-before-persist",
        "forbidden AIBI repository boundary" in json.dumps(cross_repo.get("parsed") or {}, ensure_ascii=False)
        and not any(row[1] == "cross_repo" for row in connector_state()),
    )

    unauthorized = run("arbitrary-query-argument-rejected", [
        "preview-connector", "--connector", connector_key, "--query", "SELECT * FROM secrets",
    ], expected_status=2)
    check("adapter-surface-has-no-arbitrary-query-argument", "unrecognized arguments" in unauthorized["stderr"])

    contract_envelope = run("cli-contract", ["cli-contract"])["parsed"] or {}
    contract = contract_envelope.get("contract") or {}
    command_contracts = {item.get("name"): item for item in contract.get("commands") or []}
    adapter_commands = ["list-connector-adapters", "discover-connector", "preview-connector", "plan-connector-sync"]
    check(
        "adapter-capabilities-are-read-only",
        contract.get("commandCount") == 111
        and all(
            command_contracts.get(command, {}).get("mutationMode") == "read-only"
            and command_contracts.get(command, {}).get("writesBusinessState") is False
            and command_contracts.get(command, {}).get("writesEvidence") is False
            for command in adapter_commands
        ),
        {command: command_contracts.get(command) for command in adapter_commands},
    )
finally:
    failed = [item for item in checks if not item["ok"]]
    print(json.dumps({
        "ok": not failed,
        "schema": "aibi-connector-adapter-verify/v1",
        "generatedBy": "scripts/verify-connector-adapters.py",
        "checks": checks,
        "failedChecks": failed,
    }, ensure_ascii=False, indent=2))
    shutil.rmtree(VERIFY_DIR, ignore_errors=True)

if any(not item["ok"] for item in checks):
    raise SystemExit(1)
