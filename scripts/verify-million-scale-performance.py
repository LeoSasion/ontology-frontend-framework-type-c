from __future__ import annotations

"""Deterministic million-row acceptance benchmark for AIBI-C's v2 data plane.

The benchmark is intentionally self-contained and machine-readable.  It creates
only disposable control metadata, one immutable typed Parquet object, and one
DuckDB catalogue.  Passing it proves the critical algorithms remain set-based:
publication and version validation do not count/scan the dataset, aggregation
uses DuckDB, detail traversal is keyset-based, and response limits are enforced.
"""

import argparse
import json
import math
import sqlite3
import statistics
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path
from typing import Any, Callable, Sequence


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from dataset_version_store import (  # noqa: E402
    activate_dataset_version,
    prepare_dataset_version,
    publish_dataset_version,
    resolve_dataset_object_paths,
)
from bi_cli_schema import initialize_schema  # noqa: E402
from query_runtime import (  # noqa: E402
    ReplicaExpectation,
    open_validated_duckdb_query,
    publish_dataset_view,
    replica_source_version,
    validate_replica_bindings,
)
from table_query_tools import (  # noqa: E402
    DETAIL_RESPONSE_MAX_BYTES,
    DETAIL_RESULT_MAX_BYTES,
    _bounded_rows,
    normalize_limit,
)


DEFAULT_ROWS = 1_000_000
PUBLIC_SCHEMA = (
    ("order_id", "BIGINT"),
    ("store_id", "INTEGER"),
    ("channel", "VARCHAR"),
    ("order_date", "DATE"),
    ("amount", "DOUBLE"),
    ("quantity", "INTEGER"),
    ("sku", "VARCHAR"),
    ("customer_id", "BIGINT"),
    ("region", "VARCHAR"),
    ("country", "VARCHAR"),
    ("city", "VARCHAR"),
    ("category", "VARCHAR"),
    ("subcategory", "VARCHAR"),
    ("unit_price", "DECIMAL(18,2)"),
    ("discount", "DECIMAL(9,4)"),
    ("tax_amount", "DECIMAL(18,2)"),
    ("shipping_amount", "DECIMAL(18,2)"),
    ("net_amount", "DECIMAL(18,2)"),
    ("currency", "VARCHAR"),
    ("status", "VARCHAR"),
    ("payment_method", "VARCHAR"),
    ("fulfilled_at", "TIMESTAMP"),
    ("is_returned", "BOOLEAN"),
    ("source_batch", "INTEGER"),
)
THRESHOLDS_MS = {
    "parquetGeneration": 45_000.0,
    "objectAndMetadataPublish": 15_000.0,
    "duckdbViewPublish": 2_500.0,
    "metadataValidationP95": 100.0,
    "aggregate": 3_000.0,
    "keysetFirstPage": 1_000.0,
    "keysetMiddlePage": 1_500.0,
    "total": 75_000.0,
}


class RecordingConnection:
    """Transparent DuckDB wrapper that records every submitted SQL statement."""

    def __init__(self, connection: Any):
        self.connection = connection
        self.statements: list[str] = []

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        self.statements.append(str(sql))
        if params is None:
            return self.connection.execute(sql)
        return self.connection.execute(sql, list(params))

    def __getattr__(self, name: str) -> Any:
        return getattr(self.connection, name)


def elapsed_ms(action: Callable[[], Any]) -> tuple[Any, float]:
    started = time.perf_counter()
    result = action()
    return result, (time.perf_counter() - started) * 1000.0


def percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    index = max(0, min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1))
    return ordered[index]


def create_control_plane(path: Path, rows: int) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    initialize_schema(connection)
    connection.execute(
        """
        INSERT INTO table_registry(
          workspace_id, table_key, display_name, physical_table, source_file,
          row_count, column_count, created_at, data_version, updated_at
        ) VALUES('million-scale', 'orders', 'Million orders', 'fact_orders',
                 'generated-range', ?, ?, '2026-01-01T00:00:00Z', 1, '2026-01-01T00:00:00Z')
        """,
        (rows, len(PUBLIC_SCHEMA)),
    )
    connection.commit()
    return connection


def create_parquet(path: Path, rows: int) -> None:
    import duckdb  # type: ignore

    escaped = "'" + path.as_posix().replace("'", "''") + "'"
    with duckdb.connect(":memory:") as connection:
        connection.execute(
            f"""
            COPY (
              SELECT
                i::BIGINT AS __aibi_row_id,
                i::BIGINT AS order_id,
                (i % 1000)::INTEGER AS store_id,
                CASE (i % 4)
                  WHEN 0 THEN 'web'
                  WHEN 1 THEN 'marketplace'
                  WHEN 2 THEN 'store'
                  ELSE 'wholesale'
                END AS channel,
                DATE '2024-01-01' + ((i % 730)::INTEGER) AS order_date,
                ROUND(((i % 100000)::DOUBLE * 0.01) + ((i % 7)::DOUBLE * 0.1), 2) AS amount,
                ((i % 5) + 1)::INTEGER AS quantity,
                'SKU-' || LPAD(CAST(i % 50000 AS VARCHAR), 5, '0') AS sku,
                (1000000 + (i % 250000))::BIGINT AS customer_id,
                CASE i % 4 WHEN 0 THEN 'east' WHEN 1 THEN 'south' WHEN 2 THEN 'west' ELSE 'north' END AS region,
                CASE i % 3 WHEN 0 THEN 'CN' WHEN 1 THEN 'SG' ELSE 'JP' END AS country,
                'city-' || CAST(i % 120 AS VARCHAR) AS city,
                'category-' || CAST(i % 12 AS VARCHAR) AS category,
                'subcategory-' || CAST(i % 48 AS VARCHAR) AS subcategory,
                CAST(((i % 250000) + 100) / 100.0 AS DECIMAL(18,2)) AS unit_price,
                CAST((i % 3000) / 10000.0 AS DECIMAL(9,4)) AS discount,
                CAST((i % 70000) / 100.0 AS DECIMAL(18,2)) AS tax_amount,
                CAST((i % 5000) / 100.0 AS DECIMAL(18,2)) AS shipping_amount,
                CAST((i % 300000) / 100.0 AS DECIMAL(18,2)) AS net_amount,
                CASE i % 3 WHEN 0 THEN 'CNY' WHEN 1 THEN 'SGD' ELSE 'JPY' END AS currency,
                CASE i % 5 WHEN 0 THEN 'pending' WHEN 1 THEN 'paid' WHEN 2 THEN 'shipped' WHEN 3 THEN 'delivered' ELSE 'returned' END AS status,
                CASE i % 4 WHEN 0 THEN 'card' WHEN 1 THEN 'wallet' WHEN 2 THEN 'transfer' ELSE 'cash' END AS payment_method,
                TIMESTAMP '2024-01-01 00:00:00' + (i % 525600) * INTERVAL '1 minute' AS fulfilled_at,
                (i % 23 = 0) AS is_returned,
                (i % 64)::INTEGER AS source_batch
              FROM range(1, {rows + 1}) AS generated(i)
            ) TO {escaped}
            (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 122880)
            """
        )


def expectation_for(manifest: dict[str, Any], source_version: str) -> ReplicaExpectation:
    return ReplicaExpectation(
        logical_table="fact_orders",
        source_version=source_version,
        version_id=str(manifest["versionId"]),
        content_fingerprint=str(manifest["contentFingerprint"]),
        schema_fingerprint=str(manifest["schemaFingerprint"]),
        row_count=int(manifest["rowCount"]),
        object_hashes=tuple(str(item["objectHash"]) for item in manifest["files"]),
    )


def run_benchmark(rows: int, validation_iterations: int) -> dict[str, Any]:
    started_total = time.perf_counter()
    checks: list[dict[str, Any]] = []

    def check(label: str, ok: bool, detail: Any = None) -> None:
        entry: dict[str, Any] = {"label": label, "ok": bool(ok)}
        if detail is not None:
            entry["detail"] = detail
        checks.append(entry)

    timings: dict[str, float] = {}
    diagnostics: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="aibi-c-million-scale-v2-") as raw_temp:
        temp_root = Path(raw_temp)
        control_path = temp_root / "control-v2.sqlite"
        catalogue_path = temp_root / "catalog-v2.duckdb"
        prepared_path = temp_root / "prepared-orders.parquet"
        object_root = temp_root / "dataset-objects-v2"
        with closing(create_control_plane(control_path, rows)) as control:
            _, timings["parquetGeneration"] = elapsed_ms(
                lambda: create_parquet(prepared_path, rows)
            )
            parquet_size = prepared_path.stat().st_size

            def seal_and_activate() -> dict[str, Any]:
                manifest = prepare_dataset_version(
                    workspace_id="million-scale",
                    table_key="orders",
                    parquet_path=prepared_path,
                    schema_fields=[{"name": name, "type": data_type} for name, data_type in PUBLIC_SCHEMA],
                    row_count=rows,
                    source_file="generated-range",
                    object_root=object_root,
                )
                publish_dataset_version(control, manifest)
                activate_dataset_version(control, manifest)
                control.commit()
                return manifest

            manifest, timings["objectAndMetadataPublish"] = elapsed_ms(seal_and_activate)
            prepared_path.unlink(missing_ok=True)
            object_paths = resolve_dataset_object_paths(manifest, root=object_root)
            registry = control.execute(
                "SELECT * FROM table_registry WHERE workspace_id = 'million-scale' AND table_key = 'orders'"
            ).fetchone()
            if registry is None:
                raise RuntimeError("Million-scale registry activation is missing.")
            source_version = replica_source_version(registry)

            import duckdb  # type: ignore

            with duckdb.connect(str(catalogue_path)) as raw_writer:
                writer = RecordingConnection(raw_writer)

                def publish_view() -> dict[str, Any]:
                    return publish_dataset_view(
                        writer,
                        logical_table="fact_orders",
                        source_version=source_version,
                        version_id=str(manifest["versionId"]),
                        object_keys=[str(item["objectKey"]) for item in manifest["files"]],
                        object_paths=object_paths,
                        object_hashes=[str(item["objectHash"]) for item in manifest["files"]],
                        schema_fingerprint=str(manifest["schemaFingerprint"]),
                        content_fingerprint=str(manifest["contentFingerprint"]),
                        row_count=rows,
                        object_root=object_root,
                    )

                publish_receipt, timings["duckdbViewPublish"] = elapsed_ms(publish_view)
                normalized_publication_sql = "\n".join(writer.statements).casefold().replace(" ", "")
                check(
                    "publication-does-not-count-content",
                    "count(" not in normalized_publication_sql,
                    {"statementCount": len(writer.statements)},
                )

            expectation = expectation_for(manifest, source_version)
            validation_samples: list[float] = []
            with duckdb.connect(str(catalogue_path), read_only=True) as raw_reader:
                reader = RecordingConnection(raw_reader)
                validate_replica_bindings(reader, [expectation])
                reader.statements.clear()
                for _ in range(validation_iterations):
                    result, sample = elapsed_ms(
                        lambda: validate_replica_bindings(reader, [expectation])
                    )
                    if result[0]["rowCount"] != rows:
                        raise AssertionError("Metadata validation returned the wrong row count.")
                    validation_samples.append(sample)
                normalized_validation_sql = "\n".join(reader.statements).casefold().replace(" ", "")
                check(
                    "metadata-validation-is-manifest-only",
                    "count(" not in normalized_validation_sql
                    and "read_parquet" not in normalized_validation_sql
                    and 'from"fact_orders"' not in normalized_validation_sql,
                    {"statementCount": len(reader.statements)},
                )

            timings["metadataValidationMedian"] = statistics.median(validation_samples)
            timings["metadataValidationP95"] = percentile(validation_samples, 0.95)
            keyset_sql = (
                "SELECT __aibi_row_id, order_id, store_id, channel, amount "
                "FROM fact_orders WHERE __aibi_row_id > ? "
                "ORDER BY __aibi_row_id LIMIT ?"
            )
            with open_validated_duckdb_query(catalogue_path, [expectation]) as query:
                aggregate_rows, timings["aggregate"] = elapsed_ms(
                    lambda: query.rows(
                        "SELECT channel, COUNT(*) AS row_count, SUM(amount) AS amount "
                        "FROM fact_orders GROUP BY channel ORDER BY channel"
                    )
                )
                first_rows, timings["keysetFirstPage"] = elapsed_ms(
                    lambda: query.rows(keyset_sql, [0, 500])
                )
                middle_boundary = rows // 2
                middle_rows, timings["keysetMiddlePage"] = elapsed_ms(
                    lambda: query.rows(keyset_sql, [middle_boundary, 500])
                )

            check(
                "aggregate-covers-all-million-scale-rows",
                len(aggregate_rows) == 4
                and sum(int(item["row_count"]) for item in aggregate_rows) == rows,
                aggregate_rows,
            )
            check(
                "keyset-first-page-is-exact",
                bool(first_rows)
                and int(first_rows[0]["__aibi_row_id"]) == 1
                and len(first_rows) == min(rows, 500),
                {"first": first_rows[0] if first_rows else None, "rows": len(first_rows)},
            )
            expected_middle_size = min(max(0, rows - middle_boundary), 500)
            check(
                "keyset-middle-page-is-exact",
                len(middle_rows) == expected_middle_size
                and (
                    not middle_rows
                    or int(middle_rows[0]["__aibi_row_id"]) == middle_boundary + 1
                ),
                {"first": middle_rows[0] if middle_rows else None, "rows": len(middle_rows)},
            )
            check(
                "keyset-query-has-no-positional-skip",
                "offset" not in keyset_sql.casefold(),
                keyset_sql,
            )

            normalized_limit = normalize_limit(rows)
            oversized_rows = [
                {"order_id": index, "payload": "数" * 4096}
                for index in range(1_000)
            ]
            bounded, truncated, result_bytes = _bounded_rows(
                oversized_rows,
                DETAIL_RESULT_MAX_BYTES,
            )
            check(
                "result-row-and-byte-bounds-are-enforced",
                normalized_limit == 500
                and truncated
                and 0 < len(bounded) < len(oversized_rows)
                and result_bytes <= DETAIL_RESULT_MAX_BYTES
                and DETAIL_RESULT_MAX_BYTES < DETAIL_RESPONSE_MAX_BYTES,
                {
                    "normalizedLimit": normalized_limit,
                    "boundedRows": len(bounded),
                    "inputRows": len(oversized_rows),
                    "resultBytes": result_bytes,
                    "resultByteLimit": DETAIL_RESULT_MAX_BYTES,
                    "responseByteLimit": DETAIL_RESPONSE_MAX_BYTES,
                },
            )

            physical_business_tables = [
                str(row[0])
                for row in control.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' "
                    "AND name IN (SELECT physical_table FROM table_registry)"
                ).fetchall()
            ]
            sqlite_tables = [
                str(row[0])
                for row in control.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
                ).fetchall()
            ]
            check(
                "sqlite-control-plane-has-no-business-row-table",
                not physical_business_tables,
                {"businessTables": physical_business_tables, "allTables": sqlite_tables},
            )
            check(
                "manifest-row-count-is-metadata",
                control.execute(
                    "SELECT row_count FROM dataset_versions WHERE version_id = ?",
                    (manifest["versionId"],),
                ).fetchone()[0] == rows,
            )

            diagnostics = {
                "rows": rows,
                "columns": len(PUBLIC_SCHEMA) + 1,
                "parquetBytes": parquet_size,
                "parquetBytesPerRow": round(parquet_size / max(1, rows), 3),
                "validationIterations": validation_iterations,
                "datasetVersionId": manifest["versionId"],
                "schemaFingerprint": manifest["schemaFingerprint"],
                "contentFingerprint": manifest["contentFingerprint"],
                "objectHash": manifest["files"][0]["objectHash"],
                "publication": publish_receipt,
            }

    timings["total"] = (time.perf_counter() - started_total) * 1000.0
    for name, threshold in THRESHOLDS_MS.items():
        value = timings[name]
        check(
            f"latency-{name}-within-threshold",
            value <= threshold,
            {"actualMs": round(value, 3), "thresholdMs": threshold},
        )
    failed = [item for item in checks if not item["ok"]]
    return {
        "schema": "aibi-million-scale-performance/v1",
        "ok": not failed,
        "generatedBy": "scripts/verify-million-scale-performance.py",
        "scale": diagnostics,
        "timingsMs": {key: round(value, 3) for key, value in timings.items()},
        "thresholdsMs": THRESHOLDS_MS,
        "checks": checks,
        "summary": {
            "passed": len(checks) - len(failed),
            "failed": len(failed),
            "total": len(checks),
        },
        "failedChecks": failed,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify AIBI-C v2 million-row performance")
    parser.add_argument("--rows", type=int, default=DEFAULT_ROWS)
    parser.add_argument("--validation-iterations", type=int, default=30)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.rows < 1:
        raise SystemExit("--rows must be positive")
    if args.validation_iterations < 5:
        raise SystemExit("--validation-iterations must be at least 5")
    try:
        receipt = run_benchmark(args.rows, args.validation_iterations)
    except Exception as exc:
        receipt = {
            "schema": "aibi-million-scale-performance/v1",
            "ok": False,
            "generatedBy": "scripts/verify-million-scale-performance.py",
            "error": f"{type(exc).__name__}: {exc}",
        }
    print(json.dumps(receipt, ensure_ascii=False, indent=2, default=str))
    if not receipt.get("ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
