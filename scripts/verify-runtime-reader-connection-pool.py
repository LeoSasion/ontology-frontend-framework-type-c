from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import duckdb  # type: ignore

from query_runtime import (  # noqa: E402
    ReplicaExpectation,
    close_cached_duckdb_readers,
    open_batch_validated_duckdb_query,
    open_validated_duckdb_query,
)


class TrackingConnection:
    def __init__(self, connection: Any):
        self.connection = connection
        self.statements: list[str] = []
        self.close_count = 0

    def execute(self, sql: str, params: Any = None) -> Any:
        self.statements.append(" ".join(str(sql).strip().upper().split()))
        if params is None:
            return self.connection.execute(sql)
        return self.connection.execute(sql, params)

    def close(self) -> None:
        self.close_count += 1
        self.connection.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.connection, name)


def create_catalog(path: Path) -> tuple[ReplicaExpectation, Path]:
    source_version = "workspace:orders:1:3"
    version_id = "version-orders-1"
    schema_fingerprint = "a" * 64
    content_fingerprint = "b" * 64
    parquet_path = path.with_name("orders.parquet")
    parquet_sql = "'" + str(parquet_path).replace("'", "''") + "'"
    with duckdb.connect(":memory:") as parquet_writer:
        parquet_writer.execute(
            f"COPY (SELECT * FROM (VALUES (1::BIGINT), (2::BIGINT), (3::BIGINT)) AS source(value)) "
            f"TO {parquet_sql} (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
    object_hash = hashlib.sha256(parquet_path.read_bytes()).hexdigest()
    connection = duckdb.connect(str(path))
    try:
        connection.execute(f"CREATE VIEW data_orders AS SELECT * FROM read_parquet({parquet_sql})")
        connection.execute(
            """
            CREATE TABLE __aibi_replica_manifest (
              manifest_version INTEGER NOT NULL,
              logical_table VARCHAR PRIMARY KEY,
              source_version VARCHAR NOT NULL,
              version_id VARCHAR NOT NULL,
              object_hashes_json VARCHAR NOT NULL,
              schema_fingerprint VARCHAR NOT NULL,
              content_fingerprint VARCHAR NOT NULL,
              row_count BIGINT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO __aibi_replica_manifest VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                2,
                "data_orders",
                source_version,
                version_id,
                json.dumps([object_hash]),
                schema_fingerprint,
                content_fingerprint,
                3,
            ],
        )
    finally:
        connection.close()
    return (
        ReplicaExpectation(
            logical_table="data_orders",
            source_version=source_version,
            version_id=version_id,
            content_fingerprint=content_fingerprint,
            schema_fingerprint=schema_fingerprint,
            row_count=3,
            object_hashes=(object_hash,),
        ),
        parquet_path,
    )


def main() -> None:
    checks: list[dict[str, Any]] = []

    def check(label: str, ok: bool, detail: Any = None) -> None:
        item: dict[str, Any] = {"label": label, "ok": bool(ok)}
        if not ok and detail is not None:
            item["detail"] = detail
        checks.append(item)

    previous_role = os.environ.get("AIBI_RUNTIME_HOST_ROLE")
    original_connect = duckdb.connect
    tracked: list[TrackingConnection] = []

    def tracking_connect(*args: Any, **kwargs: Any) -> TrackingConnection:
        connection = TrackingConnection(original_connect(*args, **kwargs))
        tracked.append(connection)
        return connection

    def writer_probe(database_path: Path) -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import duckdb,sys; "
                    "connection=duckdb.connect(sys.argv[1]); "
                    "connection.execute('CREATE TABLE IF NOT EXISTS writer_probe(value INTEGER)'); "
                    "connection.close()"
                ),
                str(database_path),
            ],
            capture_output=True,
            check=False,
            timeout=10,
        )

    try:
        with tempfile.TemporaryDirectory(prefix="aibi-runtime-reader-pool-") as raw_temp:
            database_path = Path(raw_temp) / "catalog.duckdb"
            expectation, parquet_path = create_catalog(database_path)
            duckdb.connect = tracking_connect  # type: ignore[method-assign]

            os.environ["AIBI_RUNTIME_HOST_ROLE"] = "reader"
            with open_validated_duckdb_query(database_path, [expectation]) as first_query:
                first_connection = first_query.connection
                first_total = first_query.execute("SELECT SUM(value) FROM data_orders").fetchone()[0]
            with open_batch_validated_duckdb_query(database_path, [expectation]) as (second_query, errors):
                second_connection = second_query.connection
                second_total = second_query.execute("SELECT SUM(value) FROM data_orders").fetchone()[0]

            first_statements = list(first_connection.statements)
            check(
                "runtime-reader-closes-at-request-boundary",
                first_connection is not second_connection
                and first_connection.close_count == 1
                and second_connection.close_count == 1
                and len(tracked) == 2
                and first_total == 6
                and second_total == 6,
                {"connections": len(tracked), "firstTotal": first_total, "secondTotal": second_total},
            )
            check(
                "each-request-has-explicit-snapshot-and-rollback",
                sum(statement == "BEGIN TRANSACTION" for statement in first_statements) == 1
                and sum(statement == "ROLLBACK" for statement in first_statements) == 1
                and errors == {},
                first_statements,
            )

            writer_before_invalidation = writer_probe(database_path)
            closed = close_cached_duckdb_readers()
            writer_after_invalidation = writer_probe(database_path)
            check(
                "independent-writer-is-not-blocked-by-completed-reader",
                closed == 0
                and first_connection.close_count == 1
                and writer_before_invalidation.returncode == 0
                and writer_after_invalidation.returncode == 0,
                {
                    "closed": closed,
                    "closeCount": first_connection.close_count,
                    "writerBeforeInvalidation": writer_before_invalidation.returncode,
                    "writerAfterInvalidation": writer_after_invalidation.returncode,
                },
            )
            with open_validated_duckdb_query(database_path, [expectation]) as third_query:
                third_connection = third_query.connection
                third_query.execute("SELECT COUNT(*) FROM data_orders").fetchone()
            check(
                "query-after-invalidation-opens-new-reader",
                third_connection is not first_connection and len(tracked) == 3,
                {"connections": len(tracked)},
            )
            close_cached_duckdb_readers()

            os.environ.pop("AIBI_RUNTIME_HOST_ROLE", None)
            with open_validated_duckdb_query(database_path, [expectation]) as cli_first:
                cli_first_connection = cli_first.connection
            with open_validated_duckdb_query(database_path, [expectation]) as cli_second:
                cli_second_connection = cli_second.connection
            check(
                "standalone-cli-keeps-open-close-behavior",
                cli_first_connection is not cli_second_connection
                and cli_first_connection.close_count == 1
                and cli_second_connection.close_count == 1
                and len(tracked) == 5,
                {
                    "connections": len(tracked),
                    "firstCloseCount": cli_first_connection.close_count,
                    "secondCloseCount": cli_second_connection.close_count,
                },
            )
            parquet_path.unlink()
            check(
                "closed-readers-release-parquet-delete-handle",
                not parquet_path.exists(),
                str(parquet_path),
            )
    finally:
        close_cached_duckdb_readers()
        duckdb.connect = original_connect  # type: ignore[method-assign]
        if previous_role is None:
            os.environ.pop("AIBI_RUNTIME_HOST_ROLE", None)
        else:
            os.environ["AIBI_RUNTIME_HOST_ROLE"] = previous_role

    failed = [item for item in checks if not item["ok"]]
    print(json.dumps({
        "ok": not failed,
        "schema": "aibi-runtime-reader-connection-pool-verify/v1",
        "checks": checks,
        "summary": {"passed": len(checks) - len(failed), "failed": len(failed), "total": len(checks)},
    }, ensure_ascii=False, indent=2))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
