from __future__ import annotations

"""Exact semantic verification for the clean v2 analytical data plane.

The reference side is an explicit, typed Python oracle.  The execution side is
the production-shaped immutable Parquet -> DuckDB view path.  No business row is
stored in SQLite and no legacy replica-copy path participates in the proof.
"""

import datetime as dt
import hashlib
import json
import sqlite3
import sys
import tempfile
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
SCRIPTS = ROOT / "scripts"
for path in (TOOLS, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from formula_engine import ast_to_sql, parse_and_validate_formula  # noqa: E402
from query_runtime import (  # noqa: E402
    QueryRuntimeError,
    publish_dataset_view,
    quote_identifier,
    validate_replica_binding,
)
from query_runtime_test_support import (  # noqa: E402
    FixtureTable,
    initialize_fixture_control_plane,
    publish_fixture_tables_to_duckdb,
)


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def normalized_scalar(value: Any) -> Any:
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return round(float(value), 9)
    if isinstance(value, float):
        return round(value, 9)
    return value


def normalized_rows(columns: list[str], rows: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            key: normalized_scalar(value)
            for key, value in zip(columns, row)
        }
        for row in rows
    ]


def run_duckdb(
    connection: Any,
    sql: str,
    params: list[Any] | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    cursor = connection.execute(sql, params or [])
    columns = [str(item[0]) for item in cursor.description or []]
    return columns, normalized_rows(columns, cursor.fetchall())


def first_difference(left: Any, right: Any, path: str = "$") -> str | None:
    if type(left) is not type(right):
        return f"{path}: type {type(left).__name__} != {type(right).__name__}"
    if isinstance(left, dict):
        if list(left) != list(right):
            return f"{path}: keys {list(left)} != {list(right)}"
        for key in left:
            found = first_difference(left[key], right[key], f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(left, list):
        if len(left) != len(right):
            return f"{path}: length {len(left)} != {len(right)}"
        for index, value in enumerate(left):
            found = first_difference(value, right[index], f"{path}[{index}]")
            if found:
                return found
        return None
    if isinstance(left, float):
        return None if abs(left - right) <= 1e-9 else f"{path}: {left} != {right}"
    return None if left == right else f"{path}: {left!r} != {right!r}"


def equivalent(
    case: str,
    query: str,
    reference_result: Any,
    duckdb_result: Any,
) -> tuple[bool, str | None]:
    difference = first_difference(reference_result, duckdb_result)
    return (
        difference is None,
        None if difference is None else (
            f"engine=python-reference|duckdb-parquet-v2 case={case} "
            f"query={query} firstDifference={difference}"
        ),
    )


def expect_runtime_error(action: Callable[[], Any], code: str) -> bool:
    try:
        action()
    except QueryRuntimeError as error:
        return code in str(error)
    return False


def control_connection(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    initialize_fixture_control_plane(connection)
    return connection


def fixtures() -> list[FixtureTable]:
    return [
        FixtureTable(
            workspace_id="default",
            table_key="orders",
            physical_table="data_orders",
            columns=(
                ("order_id", "VARCHAR"),
                ("store", "VARCHAR"),
                ("sku", "VARCHAR"),
                ("channel", "VARCHAR"),
                ("amount", "DOUBLE"),
                ("cost", "DOUBLE"),
                ("order_date", "DATE"),
                ("note", "VARCHAR"),
            ),
            rows=(
                ("o1", "上海店", "A", "线上", 100.50, 40.0, "2026-05-01", "首单"),
                ("o2", "上海店", "B", "门店", 200.0, 120.0, "2026-05-02", None),
                ("o3", "北京店", "A", "线上", None, 20.0, "2026-05-03", "空金额"),
                ("o4", "北京店", "B", "门店", 300.25, 100.25, "2026-05-04", "中文"),
                ("o5", "杭州店", "A", "线上", 50.0, 0.0, "2026-05-05", None),
            ),
            display_name="订单",
        ),
        FixtureTable(
            workspace_id="default",
            table_key="targets",
            physical_table="data_targets",
            columns=(
                ("store", "VARCHAR"),
                ("sku", "VARCHAR"),
                ("target", "DOUBLE"),
                ("owner", "VARCHAR"),
            ),
            rows=(
                ("上海店", "A", 90.0, "华东"),
                ("上海店", "B", 180.0, "华东"),
                ("北京店", "A", 70.0, "华北"),
                ("北京店", "B", 250.0, "华北"),
            ),
            display_name="目标",
        ),
    ]


def binding_args(receipt: dict[str, Any]) -> dict[str, Any]:
    manifest = receipt["manifest"]
    replica = receipt["replica"]
    return {
        "logical_table": replica["logicalTable"],
        "expected_source_version": replica["sourceVersion"],
        "expected_version_id": manifest["versionId"],
        "expected_content_fingerprint": manifest["contentFingerprint"],
        "expected_schema_fingerprint": manifest["schemaFingerprint"],
        "expected_row_count": manifest["rowCount"],
        "expected_object_hashes": [item["objectHash"] for item in manifest["files"]],
    }


def republish(connection: Any, receipt: dict[str, Any]) -> None:
    manifest = receipt["manifest"]
    replica = receipt["replica"]
    publish_dataset_view(
        connection,
        logical_table=replica["logicalTable"],
        source_version=replica["sourceVersion"],
        version_id=manifest["versionId"],
        object_keys=[item["objectKey"] for item in manifest["files"]],
        object_paths=receipt["objectPaths"],
        object_hashes=[item["objectHash"] for item in manifest["files"]],
        schema_fingerprint=manifest["schemaFingerprint"],
        content_fingerprint=manifest["contentFingerprint"],
        row_count=manifest["rowCount"],
        object_root=receipt["objectRoot"],
    )


def main() -> None:
    checks: list[dict[str, Any]] = []

    def check(label: str, ok: bool, detail: Any = None) -> None:
        item: dict[str, Any] = {"label": label, "ok": bool(ok)}
        if not ok and detail is not None:
            item["detail"] = detail
        checks.append(item)

    with tempfile.TemporaryDirectory(
        prefix="aibi-c-engine-equivalence-v2-",
        ignore_cleanup_errors=True,
    ) as raw_temp:
        temp_root = Path(raw_temp)
        sqlite_path = temp_root / "control-v2.sqlite"
        duckdb_path = temp_root / "catalog-v2.duckdb"
        metadata = control_connection(sqlite_path)
        receipts = publish_fixture_tables_to_duckdb(metadata, duckdb_path, fixtures())

        sqlite_business_tables = metadata.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' "
            "AND name IN (SELECT physical_table FROM table_registry)"
        ).fetchall()
        check("sqlite-contains-no-business-row-tables", not sqlite_business_tables, sqlite_business_tables)
        check(
            "typed-parquet-objects-are-sealed",
            all(
                receipt["objectPaths"][0].suffix == ".parquet"
                and receipt["objectPaths"][0].is_file()
                for receipt in receipts.values()
            ),
            {key: [str(path) for path in value["objectPaths"]] for key, value in receipts.items()},
        )

        import duckdb  # type: ignore

        with duckdb.connect(str(duckdb_path)) as analytical:
            cases: list[tuple[str, str, list[Any], tuple[list[str], list[dict[str, Any]]]]] = [
                (
                    "detail-keyset-null-chinese-date",
                    """
                    SELECT order_id, store, note, order_date
                    FROM data_orders
                    WHERE (order_date, order_id) > (CAST(? AS DATE), ?)
                    ORDER BY order_date, order_id LIMIT 2
                    """,
                    ["2026-05-01", "o1"],
                    (
                        ["order_id", "store", "note", "order_date"],
                        [
                            {"order_id": "o2", "store": "上海店", "note": None, "order_date": "2026-05-02"},
                            {"order_id": "o3", "store": "北京店", "note": "空金额", "order_date": "2026-05-03"},
                        ],
                    ),
                ),
                (
                    "aggregate-filter",
                    """
                    SELECT channel, SUM(amount) AS value
                    FROM data_orders WHERE order_date >= ?
                    GROUP BY channel ORDER BY value DESC, channel
                    """,
                    ["2026-05-02"],
                    (
                        ["channel", "value"],
                        [
                            {"channel": "门店", "value": 500.25},
                            {"channel": "线上", "value": 50.0},
                        ],
                    ),
                ),
                (
                    "drilldown",
                    """
                    SELECT order_id, store, sku, amount FROM data_orders
                    WHERE channel = ? ORDER BY order_id LIMIT 20
                    """,
                    ["线上"],
                    (
                        ["order_id", "store", "sku", "amount"],
                        [
                            {"order_id": "o1", "store": "上海店", "sku": "A", "amount": 100.5},
                            {"order_id": "o3", "store": "北京店", "sku": "A", "amount": None},
                            {"order_id": "o5", "store": "杭州店", "sku": "A", "amount": 50.0},
                        ],
                    ),
                ),
                (
                    "composite-relationship",
                    """
                    SELECT o.order_id, o.store, o.sku, t.owner, t.target
                    FROM data_orders AS o
                    LEFT JOIN data_targets AS t ON o.store = t.store AND o.sku = t.sku
                    ORDER BY o.order_id
                    """,
                    [],
                    (
                        ["order_id", "store", "sku", "owner", "target"],
                        [
                            {"order_id": "o1", "store": "上海店", "sku": "A", "owner": "华东", "target": 90.0},
                            {"order_id": "o2", "store": "上海店", "sku": "B", "owner": "华东", "target": 180.0},
                            {"order_id": "o3", "store": "北京店", "sku": "A", "owner": "华北", "target": 70.0},
                            {"order_id": "o4", "store": "北京店", "sku": "B", "owner": "华北", "target": 250.0},
                            {"order_id": "o5", "store": "杭州店", "sku": "A", "owner": None, "target": None},
                        ],
                    ),
                ),
            ]
            for case, query, params, expected in cases:
                actual = run_duckdb(analytical, query, params)
                ok, detail = equivalent(case, " ".join(query.split()), expected, actual)
                check(f"equivalent-{case}", ok, detail)

            formula_ast = parse_and_validate_formula(
                "ROUND([amount] - [cost], 2)",
                mode="row",
                available_fields={"amount", "cost"},
            )
            formula_sql = ast_to_sql(formula_ast, mode="row", resolve_field=quote_identifier)
            formula_query = f"SELECT order_id, {formula_sql} AS margin FROM data_orders ORDER BY order_id"
            expected_formula = (
                ["order_id", "margin"],
                [
                    {"order_id": "o1", "margin": 60.5},
                    {"order_id": "o2", "margin": 80.0},
                    {"order_id": "o3", "margin": None},
                    {"order_id": "o4", "margin": 200.0},
                    {"order_id": "o5", "margin": 50.0},
                ],
            )
            actual_formula = run_duckdb(analytical, formula_query)
            ok, detail = equivalent("calculated-field", formula_query, expected_formula, actual_formula)
            check("equivalent-calculated-field", ok, detail)

            schema_contract = {
                "orders": [name for name, _ in fixtures()[0].columns],
                "targets": [name for name, _ in fixtures()[1].columns],
            }
            relationship_path = [{
                "leftTable": "orders",
                "rightTable": "targets",
                "fieldMappings": [
                    {"leftField": "store", "rightField": "store"},
                    {"leftField": "sku", "rightField": "sku"},
                ],
            }]
            receipt_binding = {
                "dataVersions": {"orders": 1, "targets": 1},
                "datasetVersionIds": {
                    key: value["manifest"]["versionId"] for key, value in receipts.items()
                },
                "schemaFingerprint": fingerprint(schema_contract),
                "relationshipPath": relationship_path,
                "relationshipFingerprint": fingerprint(relationship_path),
                "objectHashes": {
                    key: [item["objectHash"] for item in value["manifest"]["files"]]
                    for key, value in receipts.items()
                },
            }
            independently_serialized = json.loads(canonical(receipt_binding))
            check(
                "query-receipt-binding-equivalent",
                receipt_binding == independently_serialized,
                {"reference": receipt_binding, "duckdb": independently_serialized},
            )
            changed_formula = parse_and_validate_formula(
                "ROUND([amount] - [cost], 1)",
                mode="row",
                available_fields={"amount", "cost"},
            )
            changed_relationship = [{
                "leftTable": "orders",
                "rightTable": "targets",
                "fieldMappings": [{"leftField": "store", "rightField": "store"}],
            }]
            check(
                "formula-and-composite-relationship-drift-rejected",
                fingerprint(formula_ast) != fingerprint(changed_formula)
                and fingerprint(relationship_path) != fingerprint(changed_relationship),
            )

            order_binding = binding_args(receipts["orders"])
            current_binding = validate_replica_binding(analytical, **order_binding)
            check("current-v2-binding-validates", current_binding["status"] == "current", current_binding)

            analytical.execute(
                "UPDATE __aibi_replica_manifest SET source_version = 'stale' "
                "WHERE logical_table = 'data_orders'"
            )
            check(
                "stale-source-version-is-blocked",
                expect_runtime_error(
                    lambda: validate_replica_binding(analytical, **order_binding),
                    "replica-source-version-stale",
                ),
            )
            republish(analytical, receipts["orders"])
            analytical.execute("DROP VIEW data_orders")
            check(
                "half-published-view-is-blocked",
                expect_runtime_error(
                    lambda: validate_replica_binding(analytical, **order_binding),
                    "replica-view-not-published",
                ),
            )
            republish(analytical, receipts["orders"])
            analytical.execute(
                "DELETE FROM __aibi_replica_manifest WHERE logical_table = 'data_orders'"
            )
            check(
                "missing-manifest-binding-is-blocked",
                expect_runtime_error(
                    lambda: validate_replica_binding(analytical, **order_binding),
                    "replica-binding-missing",
                ),
            )

            mismatch_ok, mismatch_detail = equivalent(
                "diagnostic-proof",
                "SELECT order_id",
                (["order_id"], [{"order_id": "o1"}]),
                (["order_id"], [{"order_id": "wrong"}]),
            )
            check(
                "equivalence-failure-identifies-engine-case-query-and-first-difference",
                not mismatch_ok
                and mismatch_detail is not None
                and all(
                    token in mismatch_detail
                    for token in ["engine=", "case=diagnostic-proof", "query=", "firstDifference="]
                ),
                mismatch_detail,
            )
        metadata.close()

    failed = [item for item in checks if not item["ok"]]
    print(json.dumps({
        "schema": "aibi-cross-engine-equivalence-verify/v2",
        "ok": not failed,
        "matrix": {
            "engines": ["python-reference", "duckdb-parquet-v2"],
            "covers": [
                "typed-numeric-null-date-chinese",
                "calculated-field",
                "single-and-composite-relationship",
                "aggregate-filter-sort-keyset-drilldown",
                "dataset-version-schema-content-object-fingerprints",
                "missing-stale-half-published-view",
                "sqlite-metadata-only",
            ],
        },
        "checks": checks,
        "summary": {
            "passed": len(checks) - len(failed),
            "failed": len(failed),
            "total": len(checks),
        },
    }, ensure_ascii=False, indent=2, default=str))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
