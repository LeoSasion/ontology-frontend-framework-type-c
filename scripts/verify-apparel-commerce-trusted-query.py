from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from query_runtime_test_support import publish_sqlite_fixture_to_duckdb  # noqa: E402


checks: list[dict[str, object]] = []
TEST_TMP_ROOT = ROOT / "tmp" / "verify-trusted-apparel"
TEST_TMP_ROOT.mkdir(parents=True, exist_ok=True)


def check(label: str, ok: bool, detail: object = "") -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": "" if ok else detail})


def setup_query_fixture(connection: sqlite3.Connection) -> None:
    from bi_cli_schema import ensure_schema

    ensure_schema(connection)
    connection.execute('CREATE TABLE "fixture_orders" ("style_spu" TEXT, "merchant_sku" TEXT, "sales_amount" TEXT, "channel" TEXT, "paid_at" TEXT)')
    rows = [
        (f"SPU-{index:02d}", f"SKU-{index:02d}-M", str(1300 - index * 70), "抖音" if index <= 10 else "天猫", f"2026-05-{index:02d} 12:00:00")
        for index in range(1, 13)
    ]
    connection.executemany('INSERT INTO "fixture_orders" VALUES(?, ?, ?, ?, ?)', rows)
    connection.execute(
        """
        INSERT INTO table_registry(table_key, workspace_id, display_name, physical_table, source_file, row_count, column_count, created_at, data_version, updated_at)
        VALUES('orders', 'default', '订单', 'fixture_orders', 'fixture.csv', 12, 5, '2026-07-19', 1, '2026-07-19')
        """
    )
    for field, role in (
        ("style_spu", "identity_key"),
        ("merchant_sku", "identity_key"),
        ("sales_amount", "measure"),
        ("channel", "dimension"),
        ("paid_at", "event_time"),
    ):
        connection.execute(
            "INSERT INTO field_semantics(workspace_id, table_key, field_name, role, usage, confidence) VALUES('default', 'orders', ?, ?, 'verified', 1)",
            (field, role),
        )
    connection.execute(
        """
        INSERT INTO metric_definitions(metric_key, workspace_id, label, table_key, measure, aggregation, dimension, time_field, value_format, created_at)
        VALUES('sales_by_style', 'default', '款式销售额', 'orders', 'sales_amount', 'sum', 'style_spu', 'paid_at', 'currency', '2026-07-19')
        """
    )
    connection.execute(
        """
        INSERT INTO source_runs(id, workspace_id, table_key, name, status, source_file, row_count, column_count, profile_json, evidence_json, created_at)
        VALUES('batch-current', 'default', '__batch__', '当前批次', 'ready', 'fixture', 12, 5, '{}', '[]', '2026-07-19')
        """
    )
    connection.execute(
        "INSERT INTO source_run_tables(source_run_id, workspace_id, table_key, data_version, row_count, created_at) VALUES('batch-current', 'default', 'orders', 1, 12, '2026-07-19')"
    )
    connection.execute("UPDATE workspaces SET current_source_run_id = 'batch-current' WHERE id = 'default'")


def typed_intent(
    connection: sqlite3.Connection,
    prompt: str,
    *,
    filters: list[dict[str, str]] | None = None,
    time_scope: dict[str, object] | None = None,
):
    from trusted_query_service import build_trusted_query_intent

    return build_trusted_query_intent(
        connection,
        workspace_id="default",
        prompt=prompt,
        table_key="orders",
        columns=["style_spu", "merchant_sku", "sales_amount", "channel", "paid_at"],
        intent_frame={
            "taskType": "ranking",
            "filters": filters or [],
            "timeScope": time_scope,
        },
        measure="sales_amount",
        measure_confidence="explicit",
        dimension="style_spu",
        dimension_confidence="explicit",
        suggested_aggregation="sum",
    )


with tempfile.TemporaryDirectory(prefix="query-", dir=TEST_TMP_ROOT) as temp_dir:
    metadata_path = Path(temp_dir) / "trusted.sqlite"
    connection = sqlite3.connect(metadata_path)
    connection.row_factory = sqlite3.Row
    setup_query_fixture(connection)

    ranking_intent = typed_intent(
        connection,
        "sales_amount 合计按 style_spu 排行前3名，channel=抖音，2026年5月",
        filters=[{"fieldExpression": "channel", "operator": "=", "value": "抖音"}],
        time_scope={"expression": "2026年5月", "parts": {"year": "2026", "month": "5"}},
    )
    check("typed-intent-binds-current-source-run", ranking_intent["ready"] and ranking_intent["sourceRunId"] == "batch-current", ranking_intent)
    check("filter-and-time-are-resolved-before-execution", len(ranking_intent["filters"]) == 3 and ranking_intent["timeRange"]["field"] == "paid_at", ranking_intent["filters"])
    from trusted_answer_service import _current_source_run_ref

    current_source_ref = _current_source_run_ref(ranking_intent["sourceRunBinding"])
    check(
        "answer-source-evidence-uses-current-batch-run",
        bool(current_source_ref and current_source_ref["id"] == "batch-current" and current_source_ref["table_key"] == "__batch__"),
        current_source_ref,
    )

    from apparel_analytics_service import execute_apparel_method

    registry = connection.execute("SELECT * FROM table_registry WHERE workspace_id = 'default' AND table_key = 'orders'").fetchone()
    query_duckdb_path = Path(temp_dir) / "trusted.duckdb"
    publish_sqlite_fixture_to_duckdb(connection, query_duckdb_path)
    ranking_result = execute_apparel_method(connection, registry=registry, columns=["style_spu", "merchant_sku", "sales_amount", "channel", "paid_at"], query_intent=ranking_intent, duckdb_path=query_duckdb_path)
    check("ranking-executes-with-stable-key-and-tie-rule", bool(ranking_result and ranking_result["executed"] and ranking_result["rows"][0]["businessKey"] and ranking_result["evidence"]["tieRule"]), ranking_result)
    check("filter-and-time-are-pushed-to-sql", "channel" in ranking_result["runtime"]["compiledSql"] and "paid_at" in ranking_result["runtime"]["compiledSql"], ranking_result["runtime"])

    concentration_intent = typed_intent(connection, "sales_amount 合计按 style_spu 前20%集中度")
    concentration_result = execute_apparel_method(connection, registry=registry, columns=["style_spu", "merchant_sku", "sales_amount", "channel", "paid_at"], query_intent=concentration_intent, duckdb_path=query_duckdb_path)
    check("top-percent-is-not-top-n", concentration_intent["limit"]["percent"] == 0.2 and concentration_intent["limit"]["count"] is None, concentration_intent["limit"])
    check("concentration-uses-complete-positive-population", bool(concentration_result and concentration_result["runtime"]["populationComplete"] and concentration_result["evidence"]["positivePopulationTotal"] > 0), concentration_result)

    pareto_intent = typed_intent(connection, "sales_amount 合计按 style_spu 做 Pareto 二八分析")
    pareto_result = execute_apparel_method(connection, registry=registry, columns=["style_spu", "merchant_sku", "sales_amount", "channel", "paid_at"], query_intent=pareto_intent, duckdb_path=query_duckdb_path)
    check("pareto-answers-both-required-questions", bool(pareto_result and "headContribution" in pareto_result["evidence"] and "entityPercentToReach80" in pareto_result["evidence"]), pareto_result)

    decile_intent = typed_intent(connection, "sales_amount 合计按 style_spu 做十分位")
    decile_result = execute_apparel_method(connection, registry=registry, columns=["style_spu", "merchant_sku", "sales_amount", "channel", "paid_at"], query_intent=decile_intent, duckdb_path=query_duckdb_path)
    check("decile-executes-only-with-sufficient-population", bool(decile_result and decile_result["executed"] and decile_result["evidence"]["populationEntityCount"] >= 10), decile_result)

    ambiguous = typed_intent(connection, "sales_amount 按 style_spu 排行")
    connection.execute("DELETE FROM metric_definitions WHERE metric_key = 'sales_by_style'")
    ambiguous = typed_intent(connection, "sales_amount 按 style_spu 排行")
    check("unresolved-aggregation-fails-closed", "aggregation-not-explicitly-resolved" in ambiguous["blockers"], ambiguous["blockers"])

    abc_intent = typed_intent(connection, "sales_amount 合计按 style_spu 做 ABC 分级")
    role_intent = typed_intent(connection, "sales_amount 合计按 style_spu 判断爆款和滞销款")
    check("abc-is-closed-in-v1", any("method-closed-in-v1:abc" in item for item in abc_intent["blockers"]), abc_intent["blockers"])
    check("business-roles-are-closed-in-v1", any("method-closed-in-v1:business-role" in item for item in role_intent["blockers"]), role_intent["blockers"])

    connection.execute("UPDATE workspaces SET current_source_run_id = NULL WHERE id = 'default'")
    stale_intent = typed_intent(connection, "sales_amount 合计按 style_spu 排行")
    check("missing-current-source-run-fails-closed", "current-source-run-missing" in stale_intent["blockers"], stale_intent["blockers"])
    connection.close()


with tempfile.TemporaryDirectory(prefix="import-", dir=TEST_TMP_ROOT) as temp_dir:
    root = Path(temp_dir)
    source_dir = root / "sources"
    source_dir.mkdir()
    (source_dir / "orders-2026-05.csv").write_text("order_id,amount\nA-1,10\nA-2,20\n", encoding="utf-8")
    (source_dir / "orders-2026-06.csv").write_text("order_id,amount\nA-2,25\nA-3,30\n", encoding="utf-8")
    os.environ["AIBI_HYBRID_DB_PATH"] = str(root / "atomic.sqlite")
    os.environ["AIBI_HYBRID_DUCKDB_PATH"] = str(root / "atomic.duckdb")

    # The query fixture imported schema modules already, so exercise the atomic
    # planner directly here and verify the commit boundary through its canonical
    # plan material. CLI end-to-end coverage runs in the repository gate below.
    from atomic_import_plan_service import enrich_atomic_import_plan
    from bi_cli_io_services import read_table_file

    base_items = []
    for path in sorted(source_dir.glob("*.csv")):
        headers, rows = read_table_file(path)
        base_items.append({
            "file": path.name,
            "absolutePath": str(path),
            "tableKey": "orders",
            "displayName": "orders",
            "mode": "create" if not base_items else "merge",
            "rowCount": len(rows),
            "columnCount": len(headers),
            "uniqueFields": ["order_id"],
            "keyAuthority": "owner_confirmed",
            "_preview": {
                "profile": {"fields": []},
                "uniqueKeyQuality": {"emptyKeyRows": 0, "partialEmptyKeyRows": 0, "duplicateRowsInFile": 0},
                "mergePolicyPreview": {"conflictRule": "overwrite", "savedPolicy": {"uniqueFields": ["order_id"]}},
            },
        })
    base_plan = {
        "ok": True,
        "dryRun": True,
        "requiresConfirmation": False,
        "path": str(source_dir),
        "fileCount": 2,
        "tableCount": 1,
        "items": base_items,
        "groups": [{
            "tableKey": "orders",
            "displayName": "orders",
            "fileCount": 2,
            "rowCount": 4,
            "columnCount": 2,
            "uniqueFields": ["order_id"],
            "modes": ["create", "merge"],
            "files": [item["file"] for item in base_items],
            "willMerge": True,
        }],
        "willWrite": False,
    }
    atomic_plan = enrich_atomic_import_plan(base_plan, read_table_file=read_table_file, current_source_run_id="parent-run")
    check("atomic-plan-is-owner-confirmed-and-committable", atomic_plan["readyToCommit"] and atomic_plan["groups"][0]["keyDecision"]["authority"] == "owner_confirmed", atomic_plan["blockers"])
    check("atomic-plan-captures-cross-file-duplicates", atomic_plan["groups"][0]["crossFileKeyQuality"]["duplicateRowsAcrossFiles"] == 1, atomic_plan["groups"][0]["crossFileKeyQuality"])
    old_fingerprint = atomic_plan["planFingerprint"]
    (source_dir / "orders-2026-06.csv").write_text("order_id,amount\nA-2,25\nA-3,31\n", encoding="utf-8")
    changed_plan = enrich_atomic_import_plan(base_plan, read_table_file=read_table_file, current_source_run_id="parent-run")
    check("content-change-invalidates-plan-fingerprint", changed_plan["planFingerprint"] != old_fingerprint, {"before": old_fingerprint, "after": changed_plan["planFingerprint"]})

    cli_env = os.environ.copy()
    cli_env["AIBI_HYBRID_DB_PATH"] = str(root / "cli-atomic.sqlite")
    cli_env["AIBI_HYBRID_DUCKDB_PATH"] = str(root / "cli-atomic.duckdb")
    cli_env["PYTHONIOENCODING"] = "utf-8"

    def cli(*args: str) -> tuple[int, dict[str, object]]:
        completed = subprocess.run(
            [sys.executable, "tools/aibi_cli.py", "--json", *args],
            cwd=ROOT,
            env=cli_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        try:
            payload = json.loads(completed.stdout or completed.stderr or "{}")
        except json.JSONDecodeError:
            payload = {"stdout": completed.stdout, "stderr": completed.stderr}
        return completed.returncode, payload

    preview_code, cli_preview = cli(
        "preview-import-folder", str(source_dir), "--unique-fields", "order_id", "--conflict-rule", "overwrite"
    )
    check("cli-atomic-preview-is-ready", preview_code == 0 and cli_preview.get("readyToCommit") is True and bool(cli_preview.get("planFingerprint")), cli_preview)
    missing_plan_code, _missing_plan = cli(
        "import-folder", str(source_dir), "--unique-fields", "order_id", "--conflict-rule", "overwrite", "--yes"
    )
    check("cli-atomic-commit-requires-preview-fingerprint", missing_plan_code != 0, missing_plan_code)
    commit_code, cli_commit = cli(
        "import-folder",
        str(source_dir),
        "--unique-fields",
        "order_id",
        "--conflict-rule",
        "overwrite",
        "--expected-plan",
        str(cli_preview.get("planFingerprint") or ""),
        "--yes",
    )
    check("cli-atomic-folder-commit-succeeds", commit_code == 0 and cli_commit.get("atomic") is True and bool(cli_commit.get("sourceRunId")), cli_commit)
    cli_db = sqlite3.connect(cli_env["AIBI_HYBRID_DB_PATH"])
    cli_db.row_factory = sqlite3.Row
    current = cli_db.execute("SELECT current_source_run_id FROM workspaces WHERE id = 'default'").fetchone()
    mapped = cli_db.execute("SELECT table_key FROM source_run_tables WHERE source_run_id = ? ORDER BY table_key", (current["current_source_run_id"],)).fetchall()
    check("atomic-current-source-run-switches-once-to-batch", current["current_source_run_id"] == cli_commit.get("sourceRunId") and [row["table_key"] for row in mapped] == ["orders"], {"current": dict(current), "mapped": [dict(row) for row in mapped]})
    previous_current = current["current_source_run_id"]
    cli_db.close()

    repreview_code, repreview = cli(
        "preview-import-folder", str(source_dir), "--unique-fields", "order_id", "--conflict-rule", "overwrite"
    )
    (source_dir / "orders-2026-06.csv").write_text("order_id,amount\nA-2,26\nA-3,31\n", encoding="utf-8")
    drift_code, _drift = cli(
        "import-folder",
        str(source_dir),
        "--unique-fields",
        "order_id",
        "--conflict-rule",
        "overwrite",
        "--expected-plan",
        str(repreview.get("planFingerprint") or ""),
        "--yes",
    )
    drift_db = sqlite3.connect(cli_env["AIBI_HYBRID_DB_PATH"])
    drift_current = drift_db.execute("SELECT current_source_run_id FROM workspaces WHERE id = 'default'").fetchone()[0]
    drift_db.close()
    check("fingerprint-drift-blocks-before-current-run-change", repreview_code == 0 and drift_code != 0 and drift_current == previous_current, {"preview": repreview, "driftCode": drift_code, "current": drift_current})


with tempfile.TemporaryDirectory(prefix="proof-", dir=TEST_TMP_ROOT) as temp_dir:
    from apparel_entity_mapping_service import build_apparel_entity_mapping_proof, classify_apparel_field
    from bi_cli_schema import ensure_schema
    from relationship_tools import build_relationship_preview
    from bi_cli_core import quote_identifier

    proof_connection = sqlite3.connect(Path(temp_dir) / "proof.sqlite")
    proof_connection.row_factory = sqlite3.Row
    ensure_schema(proof_connection)
    proof_connection.execute(
        "INSERT INTO workspace_domain_packs(workspace_id, pack_id, version, enabled, enabled_at, updated_at) "
        "VALUES('default', 'platform-commerce', '1.0.0', 1, '2026-07-19', '2026-07-19')"
    )
    for table_key in ("orders", "inventory"):
        physical = f"proof_{table_key}"
        proof_connection.execute(f'CREATE TABLE "{physical}" ("style_spu" TEXT, "shop" TEXT, "event_at" TEXT)')
        proof_connection.executemany(f'INSERT INTO "{physical}" VALUES(?, ?, ?)', [("SPU-1", "抖音", "2026-05-01"), ("SPU-2", "抖音", "2026-05-02")])
        proof_connection.execute(
            "INSERT INTO table_registry(table_key, workspace_id, display_name, physical_table, source_file, row_count, column_count, created_at, data_version, updated_at) VALUES(?, 'default', ?, ?, 'fixture', 2, 3, '2026-07-19', 1, '2026-07-19')",
            (table_key, table_key, physical),
        )
        proof_connection.execute("INSERT INTO field_semantics(workspace_id, table_key, field_name, role, usage, confidence) VALUES('default', ?, 'event_at', 'event_time', 'verified', 1)", (table_key,))
    proof_connection.execute("INSERT INTO source_runs(id, workspace_id, table_key, name, status, source_file, row_count, column_count, profile_json, evidence_json, created_at) VALUES('proof-batch', 'default', '__batch__', 'proof', 'ready', 'fixture', 4, 6, '{}', '[]', '2026-07-19')")
    for table_key in ("orders", "inventory"):
        proof_connection.execute("INSERT INTO source_run_tables(source_run_id, workspace_id, table_key, data_version, row_count, created_at) VALUES('proof-batch', 'default', ?, 1, 2, '2026-07-19')", (table_key,))
    proof_connection.execute("UPDATE workspaces SET current_source_run_id = 'proof-batch' WHERE id = 'default'")
    proof_duckdb_path = Path(temp_dir) / "proof.duckdb"
    publish_sqlite_fixture_to_duckdb(proof_connection, proof_duckdb_path)
    relationship_preview = build_relationship_preview(
        proof_connection,
        "proof_orders",
        "proof_inventory",
        ["style_spu", "shop", "event_at"],
        ["style_spu", "shop", "event_at"],
        [{"leftField": "style_spu", "rightField": "style_spu"}],
        join_type="left",
        sample_limit=5,
        quote_identifier=quote_identifier,
    )
    proof = build_apparel_entity_mapping_proof(
        proof_connection,
        workspace_id="default",
        left_table_key="orders",
        right_table_key="inventory",
        mappings=[{"leftField": "style_spu", "rightField": "style_spu"}],
        relationship_preview=relationship_preview,
        duckdb_path=proof_duckdb_path,
    )
    check("apparel-mapping-proof-validates-values-grain-time-scope-and-source-run", proof["status"] == "validated" and proof["cardinality"] == "one-to-one" and proof["proofFingerprint"], proof)
    check("generic-sku-is-explicitly-ambiguous", classify_apparel_field("SKU")["ambiguous"] is True, classify_apparel_field("SKU"))
    check("color-is-an-attribute-not-a-sku-entity", classify_apparel_field("颜色")["attributeOf"] == "merchant_sku", classify_apparel_field("颜色"))
    proof_connection.close()


failed = [item for item in checks if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-apparel-commerce-trusted-query-verify/v1",
    "generatedBy": "scripts/verify-apparel-commerce-trusted-query.py",
    "checks": checks,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
