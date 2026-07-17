from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import analysis_unit_service as analysis_unit_service_module  # noqa: E402
import confirmed_query_service as confirmed_query_service_module  # noqa: E402
import domain_pack_service as domain_pack_service_module  # noqa: E402
from analysis_unit_service import analysis_unit_build_command  # noqa: E402
from confirmed_query_service import (  # noqa: E402
    confirm_query_command,
    create_confirmed_query_candidate,
    recall_confirmed_queries,
)
from query_plan_receipt_service import (  # noqa: E402
    create_query_plan_receipt,
    current_query_receipt_source_state,
    get_query_receipt,
)


checks: list[dict[str, Any]] = []


def check(label: str, ok: Any, detail: Any = None) -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": detail if not ok else None})


def cli(env: dict[str, str], *args: str) -> tuple[int, dict[str, Any]]:
    completed = subprocess.run(
        [sys.executable, "tools/aibi_cli.py", "--json", *args],
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
        payload = {"stdout": completed.stdout[-1600:], "stderr": completed.stderr[-1600:]}
    return completed.returncode, payload


def connection_for(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def candidate_for(
    database: Path,
    receipt_key: str,
    *,
    action_key: str,
    prompt: str,
) -> dict[str, Any] | None:
    connection = connection_for(database)
    try:
        candidate = create_confirmed_query_candidate(
            connection,
            workspace_id="default",
            action_key=action_key,
            action_payload={"queryReceiptKey": receipt_key, "prompt": prompt, "tableKey": "regions"},
            added_widget={"widget_type": "bar", "table_key": "regions"},
            now_iso=lambda: "2026-07-16T12:00:00Z",
        )
        connection.commit()
        return candidate
    finally:
        connection.close()


def receipt_state(database: Path, receipt_key: str) -> dict[str, Any]:
    connection = connection_for(database)
    try:
        receipt = get_query_receipt(connection, "default", receipt_key)
        if not receipt:
            return {"matchesReceipt": False, "blockers": ["missing-query-receipt"]}
        return current_query_receipt_source_state(connection, "default", receipt)
    finally:
        connection.close()


def knowledge_artifact_drift_states(
    database: Path,
    receipt_key: str,
    temp_root: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    mirror_root = temp_root / "domain-pack-artifact-drift"
    mirror_manifest = mirror_root / "domain-packs" / "platform-commerce.v1.json"
    mirror_knowledge = mirror_root / "knowledge" / "platform-commerce.v1.json"
    mirror_manifest.parent.mkdir(parents=True, exist_ok=True)
    mirror_knowledge.parent.mkdir(parents=True, exist_ok=True)
    mirror_manifest.write_bytes((ROOT / "domain-packs" / "platform-commerce.v1.json").read_bytes())
    mirror_knowledge.write_bytes((ROOT / "knowledge" / "platform-commerce.v1.json").read_bytes())
    original_root = domain_pack_service_module.ROOT
    original_pack_root = domain_pack_service_module.PACK_ROOT
    try:
        domain_pack_service_module.ROOT = mirror_root
        domain_pack_service_module.PACK_ROOT = mirror_manifest.parent
        baseline = receipt_state(database, receipt_key)
        mirror_knowledge.write_bytes(mirror_knowledge.read_bytes() + b"\n")
        drifted = receipt_state(database, receipt_key)
        return baseline, drifted
    finally:
        domain_pack_service_module.ROOT = original_root
        domain_pack_service_module.PACK_ROOT = original_pack_root


def recalled(database: Path, prompt: str) -> list[dict[str, Any]]:
    connection = connection_for(database)
    try:
        return recall_confirmed_queries(
            connection,
            workspace_id="default",
            prompt=prompt,
            table_key=None,
            now_iso=lambda: "2026-07-16T12:30:00Z",
        )
    finally:
        connection.close()


def competing_writer_probe(database: Path) -> dict[str, Any]:
    connection = sqlite3.connect(database, timeout=0.05)
    try:
        connection.execute("PRAGMA busy_timeout = 50")
        connection.execute("BEGIN IMMEDIATE")
        connection.rollback()
        return {"locked": False, "acquired": True, "error": ""}
    except sqlite3.OperationalError as exc:
        return {
            "locked": "locked" in str(exc).casefold(),
            "acquired": False,
            "error": str(exc),
        }
    finally:
        connection.close()


with tempfile.TemporaryDirectory(prefix="aibi-c-receipt-freshness-p2-") as temporary:
    temp_root = Path(temporary)
    database = temp_root / "runtime.sqlite"
    env = {
        **os.environ,
        "AIBI_HYBRID_DB_PATH": str(database),
        "AIBI_HYBRID_DUCKDB_PATH": str(temp_root / "runtime.duckdb"),
        "AIBI_EVIDENCE_BUNDLE_ROOT": str(temp_root / "evidence"),
        "PYTHONIOENCODING": "utf-8",
    }
    regions = temp_root / "regions.csv"
    facts = temp_root / "facts.csv"
    regions.write_text("region_id,region_name\nr1,North\nr2,South\n", encoding="utf-8")
    facts.write_text("fact_id,region_id,amount\nf1,r1,10\nf2,r2,20\n", encoding="utf-8")

    for table, path in (("regions", regions), ("facts", facts)):
        status, payload = cli(env, "import-commit", str(path), "--table", table, "--name", table, "--mode", "create", "--yes")
        check(f"import-{table}", status == 0 and payload.get("ok") is True, payload)
    status, payload = cli(
        env,
        "relationship-save",
        "--left-table", "regions",
        "--right-table", "facts",
        "--left-field", "region_id",
        "--right-field", "region_id",
        "--join-type", "left",
        "--yes",
    )
    check("save-relationship", status == 0 and payload.get("saved", {}).get("validation", {}).get("status") == "validated", payload)

    status, first = cli(env, "semantic-query", "按 region_name 汇总 amount", "--table", "regions")
    first_receipt = first.get("queryPlanReceipt") or {}
    first_unit = first.get("analysisUnit") or {}
    first_receipt_key = str(first_receipt.get("receiptKey") or "")
    first_unit_key = str(first_unit.get("unitKey") or "")
    check(
        "baseline-multi-source-receipt-is-current",
        status == 0
        and first.get("executed") is True
        and first_receipt.get("source", {}).get("tableKeys") == ["regions", "facts"]
        and receipt_state(database, first_receipt_key).get("matchesReceipt") is True,
        first,
    )

    changed_facts = temp_root / "facts-changed.csv"
    changed_facts.write_text("fact_id,region_id,amount\nf1,r1,11\nf2,r2,20\nf3,r1,5\n", encoding="utf-8")
    status, payload = cli(env, "import-commit", str(changed_facts), "--table", "facts", "--name", "facts", "--mode", "replace", "--yes")
    check("replace-terminal-source", status == 0 and payload.get("committed") is True, payload)
    source_state = receipt_state(database, first_receipt_key)
    check(
        "source-replace-invalidates-complete-receipt-binding",
        source_state.get("matchesReceipt") is False
        and source_state.get("sourceTablesMatch") is False
        and "query-receipt-source-drifted" in source_state.get("blockers", []),
        source_state,
    )
    status, stale_build = cli(
        env,
        "analysis-unit-build",
        "--receipt", first_receipt_key,
        "--kind", "comparison",
        "--rows-json", json.dumps(first.get("rows") or [], ensure_ascii=False),
    )
    check("source-drift-blocks-analysis-unit-build", status != 0 and "drifted Query Receipt" in str(stale_build.get("error") or ""), stale_build)
    status, stale_list = cli(env, "analysis-units", "--unit", first_unit_key)
    check(
        "source-drift-blocks-analysis-unit-detail",
        status != 0
        and stale_list.get("analysisUnit", {}).get("status") == "blocked"
        and stale_list.get("freshness", {}).get("usable") is False,
        stale_list,
    )
    status, stale_verify = cli(env, "analysis-unit-verify", "--unit", first_unit_key)
    check("source-drift-blocks-analysis-unit-verify", status != 0 and stale_verify.get("sourceCurrent") is False, stale_verify)
    status, stale_chart = cli(env, "chart-adapt", "--unit", first_unit_key)
    check("source-drift-blocks-chart-adapter", status != 0 and stale_chart.get("chartAdapter", {}).get("status") == "blocked", stale_chart)
    source_stale_archive = temp_root / "source-stale.zip"
    status, stale_export = cli(
        env,
        "export-analysis",
        "--receipt", first_receipt_key,
        "--unit", first_unit_key,
        "--output", str(source_stale_archive),
    )
    check("source-drift-blocks-export-before-write", status != 0 and not source_stale_archive.exists(), stale_export)
    check(
        "stale-receipt-cannot-be-rebaselined-as-confirmed-query-candidate",
        candidate_for(database, first_receipt_key, action_key="source-stale", prompt="source stale memory") is None,
    )

    # Revalidate the relationship after the source replacement and create a fresh receipt.
    status, payload = cli(
        env,
        "relationship-save",
        "--left-table", "regions",
        "--right-table", "facts",
        "--left-field", "region_id",
        "--right-field", "region_id",
        "--join-type", "left",
        "--yes",
    )
    check("revalidate-relationship-after-source-replace", status == 0 and payload.get("ok") is True, payload)
    status, second = cli(env, "semantic-query", "按 region_name 汇总 amount", "--table", "regions")
    second_receipt_key = str(second.get("queryPlanReceipt", {}).get("receiptKey") or "")
    second_unit_key = str(second.get("analysisUnit", {}).get("unitKey") or "")
    check("fresh-receipt-after-revalidation", status == 0 and receipt_state(database, second_receipt_key).get("matchesReceipt") is True, second)
    domain_memory = candidate_for(database, second_receipt_key, action_key="domain-current", prompt="domain pack memory")
    check("current-multi-source-receipt-can-create-candidate", bool(domain_memory and domain_memory.get("status") == "candidate"), domain_memory)
    status, promoted = cli(env, "confirm-query", "--query", str((domain_memory or {}).get("query_key") or "missing"), "--yes")
    check("current-multi-source-candidate-can-be-confirmed", status == 0 and promoted.get("savedQuery", {}).get("status") == "confirmed", promoted)

    status, pack_enabled = cli(env, "domain-pack-set", "--pack", "platform-commerce", "--state", "enabled", "--yes")
    check("enable-domain-pack", status == 0 and pack_enabled.get("ok") is True, pack_enabled)

    connection = connection_for(database)
    try:
        knowledge_receipt = create_query_plan_receipt(
            connection,
            workspace_id="default",
            request_text="fixed domain rule over two sources",
            source_table_key="regions",
            source_table_keys=["regions", "facts"],
            status="executed",
            joins=[{"role": "facts", "table_key": "facts"}],
            knowledge_rule={"packId": "platform-commerce", "packVersion": "1.0.0", "ruleId": "fixture-rule"},
            runtime={"engine": "sqlite", "database": "metadata-store", "compiledSql": "fixed-rule-fixture"},
            evidence_refs=[{"type": "knowledgeRule", "packId": "platform-commerce", "ruleId": "fixture-rule"}],
            domain_packs=pack_enabled.get("enabledDomainPacks") or [],
            result_rows=[{"label": "value", "value": 30}],
            now_iso=lambda: "2026-07-16T12:35:00Z",
        )
        manual_missing_proof_receipt = create_query_plan_receipt(
            connection,
            workspace_id="default",
            request_text="manual cross source without saved proof",
            source_table_key="regions",
            source_table_keys=["regions", "facts"],
            status="executed",
            joins=[{"leftTableKey": "regions", "rightTableKey": "facts", "leftField": "region_id", "rightField": "region_id"}],
            runtime={"engine": "sqlite", "database": "metadata-store", "compiledSql": "manual-fixture"},
            domain_packs=pack_enabled.get("enabledDomainPacks") or [],
            result_rows=[{"label": "value", "value": 30}],
            now_iso=lambda: "2026-07-16T12:36:00Z",
        )
        versionless_knowledge_receipt = create_query_plan_receipt(
            connection,
            workspace_id="default",
            request_text="unversioned knowledge rule cannot authorize a cross-source query",
            source_table_key="regions",
            source_table_keys=["regions", "facts"],
            status="executed",
            joins=[{"role": "facts", "table_key": "facts"}],
            knowledge_rule={"packId": "platform-commerce", "ruleId": "fixture-rule"},
            runtime={"engine": "sqlite", "database": "metadata-store", "compiledSql": "invalid-rule-fixture"},
            domain_packs=pack_enabled.get("enabledDomainPacks") or [],
            result_rows=[{"label": "value", "value": 30}],
            now_iso=lambda: "2026-07-16T12:37:00Z",
        )
        connection.commit()
    finally:
        connection.close()
    knowledge_state = receipt_state(database, knowledge_receipt["receiptKey"])
    manual_missing_proof_state = receipt_state(database, manual_missing_proof_receipt["receiptKey"])
    versionless_knowledge_state = receipt_state(database, versionless_knowledge_receipt["receiptKey"])
    check(
        "fixed-knowledge-rule-uses-domain-pack-authority-without-fake-relationship-proof",
        knowledge_receipt.get("validation", {}).get("relationshipAuthority") == "domain-pack-knowledge-rule"
        and knowledge_receipt.get("validation", {}).get("relationshipPathRequired") is False
        and knowledge_receipt.get("selection", {}).get("relationshipPathProof") == []
        and knowledge_state.get("matchesReceipt") is True
        and knowledge_state.get("relationshipPath", {}).get("knowledgeRuleBound") is True,
        {"receipt": knowledge_receipt, "state": knowledge_state},
    )
    status, knowledge_unit = cli(
        env,
        "analysis-unit-build",
        "--receipt", knowledge_receipt["receiptKey"],
        "--kind", "metric",
        "--rows-json", json.dumps([{"label": "value", "value": 30}], ensure_ascii=False),
    )
    check("knowledge-rule-receipt-remains-usable-by-analysis-unit", status == 0 and knowledge_unit.get("analysisUnit", {}).get("status") == "ready", knowledge_unit)
    artifact_baseline_state, artifact_drifted_state = knowledge_artifact_drift_states(
        database,
        knowledge_receipt["receiptKey"],
        temp_root,
    )
    check(
        "knowledge-artifact-content-change-invalidates-old-receipt",
        artifact_baseline_state.get("matchesReceipt") is True
        and artifact_drifted_state.get("matchesReceipt") is False
        and artifact_drifted_state.get("domainPackMatchesReceipt") is False
        and "query-receipt-domain-pack-drifted" in artifact_drifted_state.get("blockers", []),
        {"baseline": artifact_baseline_state, "drifted": artifact_drifted_state},
    )
    check(
        "manual-cross-table-query-still-requires-saved-relationship-proof",
        manual_missing_proof_receipt.get("validation", {}).get("relationshipPathRequired") is True
        and manual_missing_proof_state.get("matchesReceipt") is False
        and manual_missing_proof_state.get("relationshipPath", {}).get("matchesReceipt") is False
        and "query-receipt-relationship-path-drifted" in manual_missing_proof_state.get("blockers", []),
        {"receipt": manual_missing_proof_receipt, "state": manual_missing_proof_state},
    )
    check(
        "versionless-knowledge-rule-cannot-bypass-relationship-proof",
        versionless_knowledge_receipt.get("validation", {}).get("knowledgeRuleBound") is False
        and versionless_knowledge_receipt.get("validation", {}).get("relationshipPathRequired") is True
        and versionless_knowledge_state.get("matchesReceipt") is False
        and "query-receipt-relationship-path-drifted" in versionless_knowledge_state.get("blockers", []),
        {"receipt": versionless_knowledge_receipt, "state": versionless_knowledge_state},
    )
    domain_state = receipt_state(database, second_receipt_key)
    check(
        "domain-pack-toggle-invalidates-receipt",
        domain_state.get("matchesReceipt") is False
        and domain_state.get("domainPackMatchesReceipt") is False
        and "query-receipt-domain-pack-drifted" in domain_state.get("blockers", []),
        domain_state,
    )
    status, domain_unit = cli(env, "analysis-units", "--unit", second_unit_key)
    check("domain-pack-drift-blocks-analysis-unit-detail", status != 0 and domain_unit.get("freshness", {}).get("usable") is False, domain_unit)
    check("domain-pack-drift-excludes-confirmed-query-recall", recalled(database, "domain pack memory") == [])

    status, pack_disabled = cli(env, "domain-pack-set", "--pack", "platform-commerce", "--state", "disabled", "--yes")
    check("restore-neutral-domain-pack-set", status == 0 and pack_disabled.get("ok") is True, pack_disabled)
    status, third = cli(env, "semantic-query", "按 region_name 汇总 amount", "--table", "regions")
    third_receipt_key = str(third.get("queryPlanReceipt", {}).get("receiptKey") or "")
    third_unit_key = str(third.get("analysisUnit", {}).get("unitKey") or "")
    check("fresh-receipt-before-relationship-drift", status == 0 and receipt_state(database, third_receipt_key).get("matchesReceipt") is True, third)
    remembered = candidate_for(database, third_receipt_key, action_key="relationship-confirmed", prompt="relationship path memory")
    pending = candidate_for(database, third_receipt_key, action_key="relationship-pending", prompt="relationship pending memory")
    status, remembered_confirm = cli(env, "confirm-query", "--query", str((remembered or {}).get("query_key") or "missing"), "--yes")
    check("confirm-query-before-relationship-drift", status == 0 and remembered_confirm.get("savedQuery", {}).get("status") == "confirmed", remembered_confirm)
    check("second-current-candidate-created", bool(pending and pending.get("status") == "candidate"), pending)

    analysis_transaction_probe: dict[str, Any] = {"called": False}
    original_analysis_freshness = analysis_unit_service_module.current_query_receipt_source_state

    def analysis_freshness_probe(
        connection: sqlite3.Connection,
        workspace_id: str,
        receipt: dict[str, Any],
    ) -> dict[str, Any]:
        state = original_analysis_freshness(connection, workspace_id, receipt)
        analysis_transaction_probe.update({
            "called": True,
            "guardInTransaction": connection.in_transaction,
            "competingWriter": competing_writer_probe(database),
        })
        return state

    analysis_unit_service_module.current_query_receipt_source_state = analysis_freshness_probe
    try:
        analysis_build = analysis_unit_build_command(
            SimpleNamespace(
                receipt=third_receipt_key,
                rows_json=json.dumps(third.get("rows") or [], ensure_ascii=False),
                kind="auto",
                title="",
                preferred_chart="",
            ),
            open_db=lambda: connection_for(database),
            active_workspace_id=lambda _connection: "default",
            now_iso=lambda: "2026-07-16T12:40:00Z",
        )
    finally:
        analysis_unit_service_module.current_query_receipt_source_state = original_analysis_freshness
    check(
        "analysis-unit-build-holds-immediate-lock-from-freshness-proof-through-write",
        analysis_build.get("ok") is True
        and analysis_transaction_probe.get("called") is True
        and analysis_transaction_probe.get("guardInTransaction") is True
        and analysis_transaction_probe.get("competingWriter", {}).get("locked") is True,
        {"result": analysis_build, "probe": analysis_transaction_probe},
    )

    transaction_candidate = candidate_for(
        database,
        third_receipt_key,
        action_key="transaction-confirm",
        prompt="transaction freshness memory",
    )
    confirmation_transaction_probe: dict[str, Any] = {"called": False}
    original_confirmation_freshness = confirmed_query_service_module.current_query_receipt_source_state

    def confirmation_freshness_probe(
        connection: sqlite3.Connection,
        workspace_id: str,
        receipt: dict[str, Any],
    ) -> dict[str, Any]:
        state = original_confirmation_freshness(connection, workspace_id, receipt)
        confirmation_transaction_probe.update({
            "called": True,
            "guardInTransaction": connection.in_transaction,
            "competingWriter": competing_writer_probe(database),
        })
        return state

    confirmed_query_service_module.current_query_receipt_source_state = confirmation_freshness_probe
    try:
        transaction_confirmation = confirm_query_command(
            SimpleNamespace(
                query=str((transaction_candidate or {}).get("query_key") or "missing"),
                status="confirmed",
                yes=True,
            ),
            open_db=lambda: connection_for(database),
            active_workspace_id=lambda _connection: "default",
            now_iso=lambda: "2026-07-16T12:45:00Z",
        )
    finally:
        confirmed_query_service_module.current_query_receipt_source_state = original_confirmation_freshness
    check(
        "confirm-query-holds-immediate-lock-from-freshness-proof-through-write",
        transaction_confirmation.get("savedQuery", {}).get("status") == "confirmed"
        and confirmation_transaction_probe.get("called") is True
        and confirmation_transaction_probe.get("guardInTransaction") is True
        and confirmation_transaction_probe.get("competingWriter", {}).get("locked") is True,
        {"result": transaction_confirmation, "probe": confirmation_transaction_probe},
    )
    released_lock = competing_writer_probe(database)
    check(
        "freshness-consumer-transactions-release-lock-after-commit",
        released_lock.get("acquired") is True and released_lock.get("locked") is False,
        released_lock,
    )

    connection = connection_for(database)
    try:
        connection.execute(
            "UPDATE relationships SET join_type = 'inner', updated_at = '2026-07-16T13:00:00Z' WHERE workspace_id = 'default'"
        )
        connection.commit()
    finally:
        connection.close()
    relationship_state = receipt_state(database, third_receipt_key)
    check(
        "relationship-definition-drift-invalidates-path-proof",
        relationship_state.get("matchesReceipt") is False
        and relationship_state.get("relationshipPath", {}).get("matchesReceipt") is False
        and any("relationship-definition-drifted" in blocker for blocker in relationship_state.get("relationshipPath", {}).get("blockers", [])),
        relationship_state,
    )
    status, relationship_confirm = cli(env, "confirm-query", "--query", str((pending or {}).get("query_key") or "missing"), "--yes")
    check(
        "relationship-drift-blocks-candidate-confirmation",
        status != 0 and relationship_confirm.get("ok") is False and "relationship path" in str(relationship_confirm.get("error") or ""),
        relationship_confirm,
    )
    check("relationship-drift-excludes-confirmed-query-recall", recalled(database, "relationship path memory") == [])
    status, relationship_chart = cli(env, "chart-adapt", "--unit", third_unit_key)
    check(
        "relationship-drift-blocks-chart-adapter",
        status != 0
        and relationship_chart.get("chartAdapter", {}).get("status") == "blocked"
        and any("relationship" in blocker for blocker in relationship_chart.get("chartAdapter", {}).get("blockers", [])),
        relationship_chart,
    )
    relationship_stale_archive = temp_root / "relationship-stale.zip"
    status, relationship_export = cli(
        env,
        "export-analysis",
        "--receipt", third_receipt_key,
        "--unit", third_unit_key,
        "--output", str(relationship_stale_archive),
    )
    check("relationship-drift-blocks-export-before-write", status != 0 and not relationship_stale_archive.exists(), relationship_export)


failed = [item for item in checks if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-receipt-freshness-p2-verify/v1",
    "generatedBy": "scripts/verify-receipt-freshness-p2.py",
    "checks": [{"label": item["label"], "ok": item["ok"]} for item in checks],
    "failedChecks": failed,
}, ensure_ascii=False, indent=2, default=str))
raise SystemExit(1 if failed else 0)
