from __future__ import annotations

import argparse
import contextlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from metric_contract_service import (
    metric_contract_preview_command,
    metric_contract_publish_command,
    metric_contract_replay_command,
    metric_contracts_command,
)


def ns(**values):
    defaults = {
        "workspace": "", "metric": "sales", "request_key": "metric-contract-test", "label": "Sales contract",
        "population": "Paid orders", "grain": "workspace-total", "unit": "CNY", "null_policy": "exclude",
        "dedup_key": "order_id", "direction": "increase", "owner": "finance", "scenario_json": [],
        "expected_plan": "", "yes": False, "contract": "", "limit": 50,
    }
    defaults.update(values)
    return argparse.Namespace(**defaults)


def setup(path: Path):
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE workspaces(id TEXT PRIMARY KEY);
        CREATE TABLE system_flags(flag_key TEXT PRIMARY KEY, flag_value TEXT);
        CREATE TABLE table_registry(table_key TEXT,workspace_id TEXT,display_name TEXT,physical_table TEXT,source_file TEXT,row_count INTEGER,column_count INTEGER,created_at TEXT,data_version INTEGER,updated_at TEXT,PRIMARY KEY(workspace_id,table_key));
        CREATE TABLE metric_definitions(metric_key TEXT,workspace_id TEXT,label TEXT,table_key TEXT,measure TEXT,aggregation TEXT,dimension TEXT,time_field TEXT,value_format TEXT,created_at TEXT,filters_json TEXT,description TEXT,source TEXT,enabled INTEGER,updated_at TEXT,formula_text TEXT,formula_ast_json TEXT,dependencies_json TEXT,metric_type TEXT,PRIMARY KEY(workspace_id,metric_key));
        CREATE TABLE metric_contract_versions(contract_key TEXT,workspace_id TEXT,metric_key TEXT,version INTEGER,request_key TEXT,label TEXT,status TEXT,definition_json TEXT,definition_fingerprint TEXT,binding_json TEXT,binding_fingerprint TEXT,scenarios_json TEXT,plan_fingerprint TEXT,published_at TEXT,PRIMARY KEY(workspace_id,contract_key),UNIQUE(workspace_id,metric_key,version),UNIQUE(workspace_id,request_key));
        CREATE TABLE metric_contract_events(event_sequence INTEGER PRIMARY KEY AUTOINCREMENT,workspace_id TEXT,contract_key TEXT,event_type TEXT,payload_json TEXT,created_at TEXT);
        """
    )
    for workspace in ["default", "other"]:
        connection.execute("INSERT INTO workspaces VALUES(?)", (workspace,))
        connection.execute("INSERT INTO table_registry VALUES(?,?,?,?,?,?,?,?,?,?)", ("orders", workspace, "Orders", f"table_{workspace}", "", 2, 2, "t0", 1, "t0"))
        connection.execute("INSERT INTO metric_definitions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("sales", workspace, "Sales", "orders", "amount", "sum", "", "", "currency", "t0", "[]", "", "manual", 1, "t0", "", "{}", "[]", "basic"))
    connection.execute("INSERT INTO system_flags VALUES('active_workspace_id','default')")
    connection.commit()
    connection.close()


def main():
    checks = []
    check = lambda label, ok: checks.append({"label": label, "ok": bool(ok)})
    with tempfile.TemporaryDirectory(prefix="aibi-metric-contract-") as root:
        db = Path(root) / "runtime.sqlite"
        setup(db)

        def open_db():
            connection = sqlite3.connect(db)
            connection.row_factory = sqlite3.Row
            return connection

        def active(connection):
            return str(connection.execute("SELECT flag_value FROM system_flags WHERE flag_key='active_workspace_id'").fetchone()[0])

        state = {"default": 120.0, "other": 900.0}
        seen_filters = []
        seen_workspaces = []

        def query(args):
            seen_filters.extend(args.filter)
            seen_workspaces.append(args.workspace)
            return {"ok": True, "rows": [{"sales": state[args.workspace]}]}

        scenario = json.dumps({"name": "VIP customers", "filters": [{"field": "email", "operator": "eq", "value": "alice@example.com"}], "limit": 20})
        preview_args = ns(scenario_json=[scenario])
        with contextlib.closing(sqlite3.connect(db)) as inspection:
            before = inspection.execute("SELECT COUNT(*) FROM metric_contract_versions").fetchone()[0]
        preview = metric_contract_preview_command(preview_args, open_db=open_db, active_workspace_id=active, query_metric=query)
        plan = preview["metricContractPlan"]
        with contextlib.closing(sqlite3.connect(db)) as inspection:
            after = inspection.execute("SELECT COUNT(*) FROM metric_contract_versions").fetchone()[0]
        check("preview-is-read-only-and-versioned", preview["dryRun"] and plan["schema"].endswith("/v2") and before == after == 0)
        check("contract-defines-population-grain-unit-null-dedup-and-owner", set(plan["definition"]["contract"]) >= {"population", "grain", "unit", "nullPolicy", "dedupKey", "direction", "owner"})
        serialized = json.dumps(preview, ensure_ascii=False)
        check("scenario-values-are-redacted-but-bound", "alice@example.com" not in serialized and len(plan["scenarios"][0]["filters"][0]["valueFingerprint"]) == 64 and seen_filters[-1].endswith("alice@example.com"))
        wrong = False
        try:
            metric_contract_publish_command(ns(scenario_json=[scenario], expected_plan="b" * 64, yes=True), open_db=open_db, active_workspace_id=active, query_metric=query, now_iso=lambda: "t1")
        except ValueError:
            wrong = True
        check("publish-rejects-wrong-preview-fingerprint", wrong)
        published = metric_contract_publish_command(ns(scenario_json=[scenario], expected_plan=plan["planFingerprint"], yes=True), open_db=open_db, active_workspace_id=active, query_metric=query, now_iso=lambda: "t1")
        contract = published["metricContract"]
        check("publish-freezes-version-one-and-baseline", published["changed"] and contract["version"] == 1 and contract["scenarios"][0]["baseline"]["scalar"] == 120.0)
        with contextlib.closing(open_db()) as connection:
            connection.execute("UPDATE system_flags SET flag_value='other' WHERE flag_key='active_workspace_id'")
            connection.commit()
        isolated_replay = metric_contract_replay_command(ns(workspace="default", contract=contract["contractKey"]), open_db=open_db, active_workspace_id=active, query_metric=query)
        check("scenario-replay-honors-explicit-workspace-after-active-switch", isolated_replay["status"] == "passed" and seen_workspaces[-1] == "default")
        other_preview = metric_contract_preview_command(ns(workspace="other", request_key="metric-contract-other", scenario_json=[scenario]), open_db=open_db, active_workspace_id=active, query_metric=query)
        check("preview-baseline-is-bound-to-target-workspace", other_preview["metricContractPlan"]["scenarios"][0]["baseline"]["scalar"] == 900.0 and seen_workspaces[-1] == "other")
        with contextlib.closing(open_db()) as connection:
            connection.execute("UPDATE system_flags SET flag_value='default' WHERE flag_key='active_workspace_id'")
            connection.commit()
        replayed = metric_contract_publish_command(ns(scenario_json=[scenario], expected_plan=plan["planFingerprint"], yes=True), open_db=open_db, active_workspace_id=active, query_metric=query, now_iso=lambda: "t2")
        check("publish-response-loss-replay-is-idempotent", replayed["changed"] is False and replayed["idempotentReplay"] is True)
        listed = metric_contracts_command(ns(metric="sales"), open_db=open_db, active_workspace_id=active)
        check("list-is-workspace-and-metric-scoped", listed["count"] == 1 and listed["metricContracts"][0]["workspaceId"] == "default")
        passed = metric_contract_replay_command(ns(contract=contract["contractKey"]), open_db=open_db, active_workspace_id=active, query_metric=query)
        check("unchanged-scenario-replay-passes", passed["status"] == "passed" and passed["summary"]["passed"] == 1)
        state["default"] = 135.0
        changed = metric_contract_replay_command(ns(contract=contract["contractKey"]), open_db=open_db, active_workspace_id=active, query_metric=query)
        check("scenario-replay-explains-numeric-delta", changed["status"] == "changed" and changed["comparisons"][0]["scalarDelta"] == 15.0)
        with contextlib.closing(open_db()) as connection:
            connection.execute("UPDATE metric_definitions SET aggregation='avg' WHERE workspace_id='default' AND metric_key='sales'")
            connection.commit()
        stale = metric_contract_replay_command(ns(contract=contract["contractKey"]), open_db=open_db, active_workspace_id=active, query_metric=query)
        check("definition-drift-is-explicitly-attributed", stale["freshness"]["definitionCurrent"] is False and stale["attribution"] == "definition-changed")
        with contextlib.closing(open_db()) as connection:
            connection.execute("UPDATE metric_definitions SET aggregation='sum' WHERE workspace_id='default' AND metric_key='sales'")
            connection.execute("UPDATE table_registry SET data_version=2,row_count=3 WHERE workspace_id='default' AND table_key='orders'")
            connection.commit()
        data_changed = metric_contract_replay_command(ns(contract=contract["contractKey"]), open_db=open_db, active_workspace_id=active, query_metric=query)
        check("data-drift-is-separated-from-definition-drift", data_changed["freshness"]["definitionCurrent"] and not data_changed["freshness"]["bindingCurrent"] and data_changed["attribution"] == "data-changed")
        other = metric_contracts_command(ns(workspace="other", metric="sales"), open_db=open_db, active_workspace_id=active)
        check("contracts-are-workspace-isolated", other["count"] == 0)
        check("public-contract-never-exposes-request-key", "requestKey" not in json.dumps(contract))

    failed = [item for item in checks if not item["ok"]]
    print(json.dumps({"ok": not failed, "schema": "aibi-metric-contract-v2-verify/v1", "checks": checks, "failedChecks": failed}, ensure_ascii=False, indent=2))
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
