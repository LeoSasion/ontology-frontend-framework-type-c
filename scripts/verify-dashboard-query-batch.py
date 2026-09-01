from __future__ import annotations

import contextlib
import hashlib
import json
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import duckdb  # type: ignore  # noqa: E402

import saved_view_query_service  # noqa: E402
from saved_view_query_service import (  # noqa: E402
    BATCH_RESPONSE_MAX_BYTES,
    _finalize_batch_response,
    query_table_batch_command,
)


def response_size(value: object) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8"))


with tempfile.TemporaryDirectory(prefix="aibi-dashboard-batch-") as directory:
    root = Path(directory)
    parquet = root / "orders.parquet"
    catalog = root / "catalog.duckdb"
    with duckdb.connect(":memory:") as writer:
        writer.execute(
            "COPY (SELECT i::INTEGER AS id, CASE WHEN i % 2 = 0 THEN 'web' ELSE 'store' END AS channel, i::DOUBLE AS amount FROM range(1, 101) AS values(i)) TO ? (FORMAT PARQUET, COMPRESSION ZSTD)",
            [str(parquet)],
        )
    object_hash = hashlib.sha256(parquet.read_bytes()).hexdigest()
    content_hash = "a" * 64
    schema_hash = "b" * 64
    with duckdb.connect(str(catalog)) as writer:
        writer.execute("CREATE TABLE __aibi_schema_metadata(key VARCHAR PRIMARY KEY, value VARCHAR NOT NULL)")
        writer.execute("INSERT INTO __aibi_schema_metadata VALUES ('schema_version', '2')")
        writer.execute(
            "CREATE TABLE __aibi_replica_manifest(manifest_version INTEGER, logical_table VARCHAR PRIMARY KEY, source_version VARCHAR, version_id VARCHAR, object_keys_json VARCHAR, object_paths_json VARCHAR, object_hashes_json VARCHAR, schema_fingerprint VARCHAR, content_fingerprint VARCHAR, row_count BIGINT, published_at TIMESTAMP)"
        )
        escaped_parquet = str(parquet).replace("'", "''")
        writer.execute(f"CREATE VIEW orders AS SELECT * FROM read_parquet('{escaped_parquet}')")
        writer.execute(
            "INSERT INTO __aibi_replica_manifest VALUES (2, 'orders', 'workspace:orders:1:100', 'version-1', '[\"objects/orders\"]', ?, ?, ?, ?, 100, current_timestamp)",
            [json.dumps([str(parquet)]), json.dumps([object_hash]), schema_hash, content_hash],
        )

    control = sqlite3.connect(":memory:")
    control.row_factory = sqlite3.Row
    control.execute(
        "CREATE TABLE table_registry(workspace_id TEXT, table_key TEXT, display_name TEXT, physical_table TEXT, row_count INTEGER, column_count INTEGER, data_version INTEGER, active_version_id TEXT, schema_json TEXT, schema_fingerprint TEXT, content_fingerprint TEXT, updated_at TEXT)"
    )
    control.execute(
        "INSERT INTO table_registry VALUES ('workspace', 'orders', 'Orders', 'orders', 100, 3, 1, 'version-1', ?, ?, ?, '2026-01-01T00:00:00Z')",
        [json.dumps([{"name": "channel", "type": "VARCHAR"}, {"name": "amount", "type": "DOUBLE"}]), schema_hash, content_hash],
    )
    control.commit()

    @contextlib.contextmanager
    def open_db():
        yield control

    def resolve_view(_connection, view_key, _table_key=None, _workspace_id=None):
        raise AssertionError(f"Unexpected view lookup: {view_key}")

    def registry_for_table(connection, table_key, _workspace_id=None):
        return connection.execute("SELECT * FROM table_registry WHERE table_key = ?", (table_key,)).fetchone()

    def table_columns(_connection, _physical_table):
        return ["id", "channel", "amount"]

    def active_workspace_id(_connection):
        return "workspace"

    duckdb_opened_for_wrong_workspace = [False]
    original_open_batch = saved_view_query_service.open_batch_validated_duckdb_query

    def forbidden_open_batch(*_args, **_kwargs):
        duckdb_opened_for_wrong_workspace[0] = True
        raise AssertionError("DuckDB must not open for a non-active workspace")

    saved_view_query_service.open_batch_validated_duckdb_query = forbidden_open_batch
    try:
        query_table_batch_command(
            type("Args", (), {"plan": [json.dumps({"table": "orders"})], "workspace": "other-workspace"})(),
            open_db=open_db,
            resolve_view=resolve_view,
            registry_for_table=registry_for_table,
            table_columns=table_columns,
            active_workspace_id=active_workspace_id,
        )
    except ValueError as error:
        assert str(error) == "query-table-workspace-changed"
    else:
        raise AssertionError("A non-active workspace query must fail closed")
    finally:
        saved_view_query_service.open_batch_validated_duckdb_query = original_open_batch
    assert duckdb_opened_for_wrong_workspace[0] is False

    saved_view_query_service.DUCKDB_PATH = catalog
    plans = [
        json.dumps({"table": "orders", "mode": "aggregate", "groupFields": ["channel"], "aggregation": "count", "limit": 10}),
        json.dumps({"table": "missing", "mode": "aggregate", "aggregation": "count", "limit": 10}),
    ]
    result = query_table_batch_command(
        type("Args", (), {"plan": plans, "workspace": "workspace"})(),
        open_db=open_db,
        resolve_view=resolve_view,
        registry_for_table=registry_for_table,
        table_columns=table_columns,
        active_workspace_id=active_workspace_id,
    )
    items = result["batchQuery"]["results"]
    assert result["ok"] is True
    assert result["batchQuery"]["succeeded"] == 1 and result["batchQuery"]["failed"] == 1
    assert items[0]["ok"] is True and items[1]["errorCode"] == "Unknown table"

    control.execute("UPDATE table_registry SET active_version_id = 'version-2'")
    control.commit()
    drifted = query_table_batch_command(
        type("Args", (), {"plan": [plans[0]], "workspace": "workspace"})(),
        open_db=open_db,
        resolve_view=resolve_view,
        registry_for_table=registry_for_table,
        table_columns=table_columns,
        active_workspace_id=active_workspace_id,
    )
    assert drifted["batchQuery"]["results"][0]["errorCode"] == "replica-version-stale"

    try:
        query_table_batch_command(
            type("Args", (), {"plan": [json.dumps({"table": "orders"})] * 33, "workspace": "workspace"})(),
            open_db=open_db,
            resolve_view=resolve_view,
            registry_for_table=registry_for_table,
            table_columns=table_columns,
            active_workspace_id=active_workspace_id,
        )
    except ValueError as error:
        assert "1-32" in str(error)
    else:
        raise AssertionError("Batch command must reject more than 32 plans")

    oversized_rows = [{"value": "x" * 80_000} for _ in range(100)]
    bounded = _finalize_batch_response(
        [{"index": 0, "ok": True, "tableQuery": {"rows": oversized_rows}}],
        plan_count=1,
    )
    assert response_size(bounded) <= BATCH_RESPONSE_MAX_BYTES
    assert bounded["batchQuery"]["truncatedByBytes"] is True
    control.close()

print("dashboard-query-batch-ok")
