from __future__ import annotations

import contextlib
import io
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

checks: list[dict[str, object]] = []


def check(label: str, ok: bool, detail: object = "") -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": "" if ok else detail})


with tempfile.TemporaryDirectory(prefix="aibi-c-semantic-transaction-") as temp_dir:
    database = str(Path(temp_dir) / "runtime.sqlite")
    os.environ["AIBI_HYBRID_DB_PATH"] = database
    os.environ["AIBI_HYBRID_DUCKDB_PATH"] = str(Path(temp_dir) / "runtime.duckdb")
    os.environ["AIBI_EVIDENCE_BUNDLE_ROOT"] = str(Path(temp_dir) / "evidence")

    import bi_cli  # noqa: E402

    writer_blocked = False

    def execution_probe(connection: sqlite3.Connection, workspace_id: str, prompt: str, **_: object) -> dict[str, object]:
        global writer_blocked
        check("semantic-execution-runs-inside-explicit-transaction", connection.in_transaction, connection.in_transaction)
        competing = sqlite3.connect(database, timeout=0)
        try:
            competing.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as error:
            writer_blocked = "locked" in str(error).casefold()
        finally:
            competing.close()
        return {
            "ok": True,
            "executed": False,
            "semanticPlan": {"schema": "aibi-semantic-query-plan/v1", "status": "needs-relationship", "joinPlan": {"rootTable": "", "targets": []}},
            "executionPlan": {"schema": "aibi-semantic-query-execution-plan/v1", "status": "blocked", "rootTable": "", "pathTables": [], "blockers": ["transaction-probe"], "planHash": "probe"},
            "query": {},
        }

    original = bi_cli.execute_workspace_semantic_query
    original_attach = bi_cli.attach_analysis_unit
    bi_cli.execute_workspace_semantic_query = execution_probe
    bi_cli.attach_analysis_unit = lambda result, **_: result
    previous_argv = sys.argv
    output = io.StringIO()
    try:
        sys.argv = ["bi_cli.py", "--json", "semantic-query", "transaction probe"]
        with contextlib.redirect_stdout(output):
            status = bi_cli.main()
    finally:
        sys.argv = previous_argv
        bi_cli.execute_workspace_semantic_query = original
        bi_cli.attach_analysis_unit = original_attach

    payload = json.loads(output.getvalue())
    check("semantic-command-completes-with-blocked-receipt", status == 0 and payload.get("queryPlanReceipt", {}).get("status") == "blocked", payload)
    check("competing-source-write-is-locked-until-receipt-commit", writer_blocked, writer_blocked)
    connection = sqlite3.connect(database)
    receipt_count = connection.execute("SELECT COUNT(*) FROM query_plan_receipts").fetchone()[0]
    connection.close()
    check("receipt-commits-in-the-same-transaction", receipt_count == 1, receipt_count)

    ask_writer_blocked = False
    ask_probe_called = False

    def ask_execution_probe(connection: sqlite3.Connection, workspace_id: str, prompt: str, **_: object) -> dict[str, object]:
        global ask_writer_blocked, ask_probe_called
        ask_probe_called = True
        check("agent-semantic-execution-runs-inside-explicit-transaction", connection.in_transaction, connection.in_transaction)
        competing = sqlite3.connect(database, timeout=0)
        try:
            competing.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as error:
            ask_writer_blocked = "locked" in str(error).casefold()
        finally:
            competing.close()
        return {
            "ok": True,
            "executed": False,
            "semanticPlan": {
                "schema": "aibi-semantic-query-plan/v1",
                "status": "ready",
                "joinPlan": {"rootTable": "root", "targets": [{"targetTable": "facts"}]},
            },
            "executionPlan": {
                "schema": "aibi-semantic-query-execution-plan/v1",
                "status": "blocked",
                "rootTable": "root",
                "pathTables": ["root", "facts"],
                "blockers": ["transaction-probe"],
                "planHash": "ask-probe",
            },
            "query": {},
        }

    verified_path = {
        "tables": ["root", "facts"],
        "safeForPlanning": True,
        "risks": [],
        "fingerprint": "p" * 64,
        "hops": [{
            "relationKey": "root-facts",
            "fromTable": "root",
            "toTable": "facts",
            "direction": "forward",
            "joinType": "inner",
            "fieldMappings": [{"leftField": "id", "rightField": "root_id"}],
            "risk": {"safeForPlanning": True, "risks": [], "confidence": 1.0},
        }],
    }
    ready_semantic_plan = {
        "schema": "aibi-semantic-query-plan/v1",
        "status": "ready",
        "fieldResolution": {
            "status": "resolved",
            "selected": [
                {"id": "root.id", "tableKey": "root", "field": "id", "role": "dimension", "confidence": 1.0, "source": "transaction-fixture", "matchedAlias": "root.id"},
                {"id": "facts.value", "tableKey": "facts", "field": "value", "role": "measure", "confidence": 1.0, "source": "transaction-fixture", "matchedAlias": "facts.value"},
            ],
            "bindings": [],
            "unresolved": [],
        },
        "grain": {
            "dimensions": [{"tableKey": "root", "field": "id", "role": "dimension"}],
            "measures": [{"tableKey": "facts", "field": "value", "role": "measure"}],
            "otherFields": [],
            "tables": ["root", "facts"],
        },
        "joinPlan": {
            "rootTable": "root",
            "requiredTables": ["root", "facts"],
            "targets": [{
                "targetTable": "facts",
                "paths": [verified_path],
                "selectedPath": verified_path,
                "requiresPathClarification": False,
            }],
        },
    }
    original_execute = bi_cli.execute_workspace_semantic_query
    original_plan = bi_cli.build_workspace_semantic_plan
    original_attach = bi_cli.attach_analysis_unit
    bi_cli.execute_workspace_semantic_query = ask_execution_probe
    bi_cli.build_workspace_semantic_plan = lambda *_args, **_kwargs: ready_semantic_plan
    bi_cli.attach_analysis_unit = lambda result, **_: result
    output = io.StringIO()
    try:
        sys.argv = ["bi_cli.py", "--json", "ask", "按 root.id 汇总 facts.value", "--read-only"]
        with contextlib.redirect_stdout(output):
            ask_status = bi_cli.main()
    finally:
        sys.argv = previous_argv
        bi_cli.execute_workspace_semantic_query = original_execute
        bi_cli.build_workspace_semantic_plan = original_plan
        bi_cli.attach_analysis_unit = original_attach

    ask_payload = json.loads(output.getvalue())
    check("agent-command-reaches-semantic-execution", ask_status == 0 and ask_probe_called, ask_payload)
    check("competing-source-write-is-locked-during-agent-execution", ask_writer_blocked, ask_writer_blocked)

failed = [item for item in checks if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-semantic-query-transaction-verify/v1",
    "checks": checks,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
raise SystemExit(0 if not failed else 1)
