from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from formula_engine import ast_to_sql, parse_and_validate_formula
from query_runtime import QueryRuntimeError, quote_identifier, sync_table_to_duckdb, validate_replica_binding


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def fingerprint(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def normalized_rows(columns: list[str], rows: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        values = dict(row) if isinstance(row, sqlite3.Row) else dict(zip(columns, row))
        normalized.append({
            key: round(float(value), 9) if isinstance(value, float) else value
            for key, value in values.items()
        })
    return normalized


def run_sqlite(connection: sqlite3.Connection, sql: str, params: list[Any] | None = None) -> tuple[list[str], list[dict[str, Any]]]:
    cursor = connection.execute(sql, params or [])
    columns = [str(item[0]) for item in cursor.description or []]
    return columns, normalized_rows(columns, cursor.fetchall())


def run_duckdb(connection: Any, sql: str, params: list[Any] | None = None) -> tuple[list[str], list[dict[str, Any]]]:
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


def equivalent(case: str, query: str, sqlite_result: Any, duckdb_result: Any) -> tuple[bool, str | None]:
    difference = first_difference(sqlite_result, duckdb_result)
    return (
        difference is None,
        None if difference is None else f"engine=sqlite|duckdb case={case} query={query} firstDifference={difference}",
    )


def expect_runtime_error(action: Callable[[], Any], code: str) -> bool:
    try:
        action()
    except QueryRuntimeError as error:
        return code in str(error)
    return False


def main() -> None:
    checks: list[dict[str, Any]] = []

    def check(label: str, ok: bool, detail: Any = None) -> None:
        item: dict[str, Any] = {"label": label, "ok": bool(ok)}
        if not ok and detail is not None:
            item["detail"] = detail
        checks.append(item)

    with tempfile.TemporaryDirectory(prefix="aibi-c-engine-equivalence-") as raw_temp:
        temp_root = Path(raw_temp)
        sqlite_path = temp_root / "matrix.sqlite"
        duckdb_path = temp_root / "matrix.duckdb"
        sqlite_connection = sqlite3.connect(sqlite_path)
        sqlite_connection.row_factory = sqlite3.Row
        sqlite_connection.executescript(
            """
            CREATE TABLE data_orders(
              order_id TEXT, store TEXT, sku TEXT, channel TEXT,
              amount TEXT, cost TEXT, order_date TEXT, note TEXT
            );
            CREATE TABLE data_targets(store TEXT, sku TEXT, target TEXT, owner TEXT);
            """
        )
        sqlite_connection.executemany(
            "INSERT INTO data_orders VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
            [
                ("o1", "上海店", "A", "线上", "100.50", "40", "2026-05-01", "首单"),
                ("o2", "上海店", "B", "门店", "200", "120", "2026-05-02", None),
                ("o3", "北京店", "A", "线上", "", "20", "2026-05-03", "空金额"),
                ("o4", "北京店", "B", "门店", "300.25", "100.25", "2026-05-04", "中文"),
                ("o5", "杭州店", "A", "线上", "50", "0", "2026-05-05", None),
            ],
        )
        sqlite_connection.executemany(
            "INSERT INTO data_targets VALUES(?, ?, ?, ?)",
            [
                ("上海店", "A", "90", "华东"),
                ("上海店", "B", "180", "华东"),
                ("北京店", "A", "70", "华北"),
                ("北京店", "B", "250", "华北"),
            ],
        )
        sqlite_connection.commit()

        import duckdb  # type: ignore
        with duckdb.connect(str(duckdb_path)) as duck_connection:
            order_replica = sync_table_to_duckdb(
                sqlite_connection,
                duck_connection,
                "data_orders",
                ["order_id", "store", "sku", "channel", "amount", "cost", "order_date", "note"],
                source_version="default:orders:1:5",
            )
            target_replica = sync_table_to_duckdb(
                sqlite_connection,
                duck_connection,
                "data_targets",
                ["store", "sku", "target", "owner"],
                source_version="default:targets:1:4",
            )

            cases = [
                (
                    "detail-sort-page-null-chinese-date",
                    "SELECT order_id, store, note, order_date FROM data_orders ORDER BY order_date, order_id LIMIT 2 OFFSET 1",
                    [],
                ),
                (
                    "aggregate-filter",
                    "SELECT channel, SUM(CAST(NULLIF(amount, '') AS REAL)) AS value FROM data_orders WHERE order_date >= ? GROUP BY channel ORDER BY value DESC, channel",
                    ["2026-05-02"],
                ),
                (
                    "drilldown",
                    "SELECT order_id, store, sku, amount FROM data_orders WHERE channel = ? ORDER BY store, sku LIMIT 20 OFFSET 0",
                    ["线上"],
                ),
                (
                    "composite-relationship",
                    """
                    SELECT o.order_id, o.store, o.sku, t.owner, CAST(NULLIF(t.target, '') AS REAL) AS target
                    FROM data_orders AS o
                    LEFT JOIN data_targets AS t ON o.store = t.store AND o.sku = t.sku
                    ORDER BY o.order_id
                    """,
                    [],
                ),
            ]
            for case, query, params in cases:
                sqlite_result = run_sqlite(sqlite_connection, query, params)
                duckdb_result = run_duckdb(duck_connection, query, params)
                ok, detail = equivalent(case, " ".join(query.split()), sqlite_result, duckdb_result)
                check(f"equivalent-{case}", ok, detail)

            formula_ast = parse_and_validate_formula(
                "ROUND([amount] - [cost], 2)",
                mode="row",
                available_fields={"amount", "cost"},
            )
            formula_sql = ast_to_sql(formula_ast, mode="row", resolve_field=quote_identifier)
            formula_query = f"SELECT order_id, {formula_sql} AS margin FROM data_orders ORDER BY order_id"
            sqlite_formula = run_sqlite(sqlite_connection, formula_query)
            duckdb_formula = run_duckdb(duck_connection, formula_query)
            ok, detail = equivalent("calculated-field", formula_query, sqlite_formula, duckdb_formula)
            check("equivalent-calculated-field", ok, detail)

            schema_contract = {
                "orders": ["order_id", "store", "sku", "channel", "amount", "cost", "order_date", "note"],
                "targets": ["store", "sku", "target", "owner"],
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
                "schemaFingerprint": fingerprint(schema_contract),
                "relationshipPath": relationship_path,
                "relationshipFingerprint": fingerprint(relationship_path),
                "replicas": {
                    "orders": order_replica["replicaTable"],
                    "targets": target_replica["replicaTable"],
                },
            }
            sqlite_receipt = {"engine": "sqlite", "binding": receipt_binding}
            duckdb_receipt = {"engine": "duckdb", "binding": dict(receipt_binding)}
            check(
                "query-receipt-binding-equivalent",
                sqlite_receipt["binding"] == duckdb_receipt["binding"],
                {"sqlite": sqlite_receipt, "duckdb": duckdb_receipt},
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

            current_binding = validate_replica_binding(
                duck_connection,
                logical_table="data_orders",
                expected_source_version="default:orders:1:5",
                expected_row_count=5,
            )
            check("current-replica-binding-validates", current_binding["status"] == "current", current_binding)
            duck_connection.execute(
                "UPDATE __aibi_replica_manifest SET source_version = 'default:orders:0:5' WHERE logical_table = 'data_orders'"
            )
            check(
                "old-replica-version-is-blocked",
                expect_runtime_error(
                    lambda: validate_replica_binding(
                        duck_connection,
                        logical_table="data_orders",
                        expected_source_version="default:orders:1:5",
                        expected_row_count=5,
                    ),
                    "replica-version-stale",
                ),
            )
            duck_connection.execute(
                "UPDATE __aibi_replica_manifest SET source_version = 'default:orders:1:5' WHERE logical_table = 'data_orders'"
            )
            duck_connection.execute("DROP VIEW data_orders")
            check(
                "half-published-replica-is-blocked",
                expect_runtime_error(
                    lambda: validate_replica_binding(
                        duck_connection,
                        logical_table="data_orders",
                        expected_source_version="default:orders:1:5",
                        expected_row_count=5,
                    ),
                    "replica-view-not-published",
                ),
            )
            duck_connection.execute(
                f"CREATE VIEW data_orders AS SELECT * FROM {quote_identifier(str(order_replica['replicaTable']))}"
            )
            duck_connection.execute("DELETE FROM __aibi_replica_manifest WHERE logical_table = 'data_orders'")
            check(
                "missing-replica-manifest-binding-is-blocked",
                expect_runtime_error(
                    lambda: validate_replica_binding(
                        duck_connection,
                        logical_table="data_orders",
                        expected_source_version="default:orders:1:5",
                        expected_row_count=5,
                    ),
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
                and all(token in mismatch_detail for token in ["engine=", "case=diagnostic-proof", "query=", "firstDifference="]),
                mismatch_detail,
            )
        sqlite_connection.close()

    failed = [item for item in checks if not item["ok"]]
    print(json.dumps({
        "schema": "aibi-cross-engine-equivalence-verify/v1",
        "ok": not failed,
        "matrix": {
            "engines": ["sqlite", "duckdb"],
            "covers": [
                "numeric-null-date-chinese",
                "calculated-field",
                "single-and-composite-relationship",
                "aggregate-filter-sort-pagination-drilldown",
                "data-version-schema-fingerprint-relationship-path",
                "missing-stale-half-published-replica",
            ],
        },
        "checks": checks,
        "summary": {"passed": len(checks) - len(failed), "failed": len(failed), "total": len(checks)},
    }, ensure_ascii=False, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
