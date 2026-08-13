from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
checks: list[dict[str, Any]] = []


def check(label: str, ok: bool, detail: Any = "") -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": "" if ok else detail})


def cli(env: dict[str, str], *args: str) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, str(TOOLS / "aibi_cli.py"), "--json", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    payload: dict[str, Any] = {}
    text = (result.stdout or "").strip()
    if text:
        try:
            value = json.loads(text)
            payload = value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            pass
    return {
        "status": result.returncode,
        "payload": payload,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


with tempfile.TemporaryDirectory(prefix="aibi-c-direct-relationship-") as temp_dir:
    temp_root = Path(temp_dir)
    database = temp_root / "runtime.sqlite"
    customers_csv = temp_root / "customers.csv"
    orders_csv = temp_root / "orders.csv"
    customers_csv.write_text(
        "customer_id,region,quota\nC1,North,100\nC2,South,200\n",
        encoding="utf-8",
    )
    orders_csv.write_text(
        "order_id,customer_id,amount\nO1,C1,10\nO2,C1,20\nO3,C2,5\n",
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "AIBI_HYBRID_DB_PATH": str(database),
        "AIBI_HYBRID_DUCKDB_PATH": str(temp_root / "runtime.duckdb"),
        "AIBI_EVIDENCE_BUNDLE_ROOT": str(temp_root / "evidence"),
        "PYTHONIOENCODING": "utf-8",
    }
    relation_key = "customers_orders_customer_id_customer_id"
    initialize = cli(env, "status")
    import_customers = cli(
        env,
        "import-commit",
        str(customers_csv),
        "--table",
        "customers",
        "--name",
        "Customers",
        "--mode",
        "create",
        "--yes",
    )
    import_orders = cli(
        env,
        "import-commit",
        str(orders_csv),
        "--table",
        "orders",
        "--name",
        "Orders",
        "--mode",
        "create",
        "--yes",
    )
    saved = cli(
        env,
        "relationship-save",
        "--left-table",
        "customers",
        "--right-table",
        "orders",
        "--map",
        "customer_id:customer_id",
        "--join-type",
        "left",
        "--yes",
    )
    check(
        "one-to-many-relationship-is-valid-graph-metadata",
        initialize["status"] == 0
        and import_customers["status"] == 0
        and import_orders["status"] == 0
        and saved["status"] == 0
        and saved["payload"].get("saved", {}).get("validation", {}).get("status") == "validated",
        saved,
    )

    one_side = cli(
        env,
        "query-relationship",
        "--relationship",
        relation_key,
        "--group",
        "left:region",
        "--measure",
        "left:quota",
        "--agg",
        "sum",
    )
    one_side_error = json.dumps(one_side, ensure_ascii=False)
    check(
        "one-side-measure-fanout-fails-closed",
        one_side["status"] != 0 and "relationship-measure-fanout-risk:left" in one_side_error,
        one_side,
    )

    many_side = cli(
        env,
        "query-relationship",
        "--relationship",
        relation_key,
        "--group",
        "left:region",
        "--measure",
        "right:amount",
        "--agg",
        "sum",
        "--sort-by",
        "dimension",
        "--sort-direction",
        "asc",
    )
    relationship_query = many_side["payload"].get("relationshipQuery", {})
    metric_name = relationship_query.get("metricName")
    values = {
        row.get("左表.region"): row.get(metric_name)
        for row in relationship_query.get("rows", [])
        if isinstance(row, dict)
    }
    fanout_safety = relationship_query.get("fanoutSafety", {})
    check(
        "many-side-measure-executes-with-cardinality-proof",
        many_side["status"] == 0
        and fanout_safety.get("status") == "safe"
        and fanout_safety.get("measureSide") == "right"
        and float(fanout_safety.get("matchedRowExpansion", 0)) == 1
        and float(values.get("North", 0)) == 30
        and float(values.get("South", 0)) == 5,
        many_side,
    )

    filtered_many_side = cli(
        env,
        "query-relationship",
        "--relationship",
        relation_key,
        "--group",
        "left:region",
        "--measure",
        "right:amount",
        "--agg",
        "sum",
        "--filter",
        "right:amount:gt:10",
    )
    filtered_proof = filtered_many_side["payload"].get("relationshipQuery", {}).get("fanoutSafety", {})
    check(
        "runtime-filter-gets-effective-query-cardinality-proof",
        filtered_many_side["status"] == 0
        and filtered_proof.get("status") == "safe"
        and filtered_proof.get("validationScope") == "effective-query-preview"
        and filtered_proof.get("runtimeFilterCount") == 1,
        filtered_many_side,
    )

    safe_preaggregation = json.dumps(
        {
            "side": "right",
            "groupFields": ["customer_id"],
            "measures": [{"field": "amount", "aggregation": "sum"}],
        },
        separators=(",", ":"),
    )
    saved_preaggregated = cli(
        env,
        "relationship-save",
        "--left-table",
        "customers",
        "--right-table",
        "orders",
        "--map",
        "customer_id:customer_id",
        "--join-type",
        "left",
        "--preaggregate-json",
        safe_preaggregation,
        "--yes",
    )
    safe_one_side = cli(
        env,
        "query-relationship",
        "--relationship",
        relation_key,
        "--group",
        "left:region",
        "--measure",
        "left:quota",
        "--agg",
        "sum",
        "--sort-by",
        "dimension",
        "--sort-direction",
        "asc",
    )
    safe_query = safe_one_side["payload"].get("relationshipQuery", {})
    safe_metric = safe_query.get("metricName")
    safe_values = {
        row.get("左表.region"): row.get(safe_metric)
        for row in safe_query.get("rows", [])
        if isinstance(row, dict)
    }
    check(
        "saved-preaggregation-can-prove-one-side-measure-safe",
        saved_preaggregated["status"] == 0
        and safe_one_side["status"] == 0
        and safe_query.get("fanoutSafety", {}).get("validationScope") == "saved-relationship"
        and float(safe_values.get("North", 0)) == 100
        and float(safe_values.get("South", 0)) == 200,
        {"saved": saved_preaggregated, "query": safe_one_side},
    )

    unsafe_preaggregation = json.dumps(
        {
            "side": "right",
            "groupFields": ["customer_id", "order_id"],
            "measures": [{"field": "amount", "aggregation": "sum"}],
        },
        separators=(",", ":"),
    )
    unsafe_override = cli(
        env,
        "query-relationship",
        "--relationship",
        relation_key,
        "--group",
        "left:region",
        "--measure",
        "left:quota",
        "--agg",
        "sum",
        "--preaggregate-json",
        unsafe_preaggregation,
    )
    unsafe_override_error = json.dumps(unsafe_override, ensure_ascii=False)
    check(
        "runtime-preaggregation-cannot-reuse-safe-saved-fanout-proof",
        unsafe_override["status"] != 0
        and "relationship-measure-fanout-risk:left" in unsafe_override_error,
        unsafe_override,
    )

    connection = sqlite3.connect(database)
    row = connection.execute(
        "SELECT validation_json FROM relationships WHERE workspace_id = 'default' AND relation_key = ?",
        (relation_key,),
    ).fetchone()
    validation = json.loads(row[0]) if row else {}
    validation.pop("dataVersions", None)
    connection.execute(
        "UPDATE relationships SET validation_json = ? WHERE workspace_id = 'default' AND relation_key = ?",
        (json.dumps(validation, ensure_ascii=False), relation_key),
    )
    connection.commit()
    connection.close()
    missing_versions = cli(
        env,
        "query-relationship",
        "--relationship",
        relation_key,
        "--measure",
        "right:amount",
        "--agg",
        "sum",
    )
    missing_versions_error = json.dumps(missing_versions, ensure_ascii=False)
    check(
        "validated-status-without-data-versions-fails-closed",
        missing_versions["status"] != 0
        and "relationship-validation-missing-data-versions" in missing_versions_error,
        missing_versions,
    )

    restored = cli(
        env,
        "relationship-save",
        "--left-table",
        "customers",
        "--right-table",
        "orders",
        "--map",
        "customer_id:customer_id",
        "--join-type",
        "left",
        "--yes",
    )
    check(
        "repreview-restores-current-version-evidence",
        restored["status"] == 0
        and set(restored["payload"].get("saved", {}).get("validation", {}).get("dataVersions", {}))
        == {"customers", "orders"},
        restored,
    )

    os.environ.update({key: value for key, value in env.items() if key.startswith("AIBI_")})
    sys.path.insert(0, str(TOOLS))
    import bi_cli_relationship_formula_commands as relationship_commands  # noqa: E402

    original_builder = relationship_commands.build_relationship_query
    builder_saw_validated_replica = False
    competing_writer_started = False

    def transaction_probe(connection: Any, *args: Any, **kwargs: Any) -> dict[str, Any]:
        global builder_saw_validated_replica, competing_writer_started
        builder_saw_validated_replica = bool(getattr(connection, "replicas", []))
        competing = sqlite3.connect(database, timeout=0)
        try:
            competing.execute("BEGIN IMMEDIATE")
            competing_writer_started = True
            competing.rollback()
        except sqlite3.OperationalError:
            competing_writer_started = False
        finally:
            competing.close()
        return original_builder(connection, *args, **kwargs)

    relationship_commands.build_relationship_query = transaction_probe
    try:
        payload = relationship_commands.query_relationship_command(
            argparse.Namespace(
                relationship=relation_key,
                group=["left:region"],
                measure="right:amount",
                agg="sum",
                filter=[],
                filter_json=[],
                preaggregate_json="",
                limit=50,
                sort_by="dimension",
                sort_direction="asc",
            )
        )
    finally:
        relationship_commands.build_relationship_query = original_builder
    check(
        "relationship-query-uses-validated-replica-without-sqlite-writer-lock",
        builder_saw_validated_replica
        and competing_writer_started
        and payload.get("ok") is True
        and payload.get("query", {}).get("runtime", {}).get("engine") == "duckdb",
        {
            "builderSawValidatedReplica": builder_saw_validated_replica,
            "competingWriterStarted": competing_writer_started,
            "payload": payload,
        },
    )
    after = sqlite3.connect(database, timeout=0)
    try:
        after.execute("BEGIN IMMEDIATE")
        released = True
        after.rollback()
    except sqlite3.OperationalError:
        released = False
    finally:
        after.close()
    check("transaction-lock-releases-after-query", released, released)


failed = [item for item in checks if not item["ok"]]
print(
    json.dumps(
        {
            "ok": not failed,
            "schema": "aibi-query-relationship-safety-verify/v1",
            "checks": checks,
            "failedChecks": failed,
        },
        ensure_ascii=False,
        indent=2,
    )
)
raise SystemExit(0 if not failed else 1)
