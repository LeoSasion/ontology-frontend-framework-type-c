from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import time
import tracemalloc
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from apparel_analytics_service import MAX_APPAREL_EVIDENCE_ROWS, execute_apparel_method  # noqa: E402
from apparel_entity_mapping_service import _scope_snapshot, _time_snapshot  # noqa: E402
from dataset_version_store import file_sha256  # noqa: E402
from context_pack_service import workspace_schema_fingerprint  # noqa: E402
from query_runtime import (  # noqa: E402
    DATASET_MANIFEST_VERSION,
    QueryRuntimeError,
    ReplicaExpectation,
    publish_dataset_view,
    quote_identifier,
    validate_replica_bindings,
)
from relationship_tools import MAX_RELATIONSHIP_SAMPLE_ROWS, build_relationship_preview  # noqa: E402


CHECKS: list[dict[str, Any]] = []
PERFORMANCE_SECONDS = 30.0
PYTHON_MEMORY_BYTES = 32 * 1024 * 1024


def check(label: str, ok: bool, detail: Any = None) -> None:
    CHECKS.append({"label": label, "ok": bool(ok), "detail": None if ok else detail})


def fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def expect_runtime_error(label: str, action: Callable[[], Any], fragment: str) -> None:
    try:
        action()
    except QueryRuntimeError as error:
        check(label, fragment in str(error), str(error))
    else:
        check(label, False, "expected QueryRuntimeError")


class TraceConnection:
    def __init__(self, connection: Any):
        self.connection = connection
        self.statements: list[str] = []

    def execute(self, sql: str, params: Any = None) -> Any:
        self.statements.append(str(sql))
        return self.connection.execute(sql, list(params or []))


def write_parquet(connection: Any, path: Path, select_sql: str) -> None:
    escaped = path.resolve().as_posix().replace("'", "''")
    connection.execute(f"COPY ({select_sql}) TO '{escaped}' (FORMAT PARQUET, COMPRESSION ZSTD)")


def publish(
    connection: Any,
    *,
    logical_table: str,
    table_key: str,
    data_version: int,
    row_count: int,
    parquet: Path,
) -> tuple[dict[str, Any], ReplicaExpectation, dict[str, Any]]:
    object_hash = file_sha256(parquet)
    object_root = parquet.parent / "dataset-objects-v2"
    object_key = f"workspaces/default/objects/{object_hash[:2]}/{object_hash}.parquet"
    canonical_path = object_root / object_key
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(parquet, canonical_path)
    schema_hash = fingerprint(f"schema:{logical_table}")
    content_hash = fingerprint(f"content:{logical_table}:{row_count}")
    source_version = f"default:{table_key}:{data_version}:{row_count}"
    version_id = f"version-{logical_table}-{data_version}"
    receipt = publish_dataset_view(
        connection,
        logical_table=logical_table,
        source_version=source_version,
        version_id=version_id,
        object_keys=[object_key],
        object_paths=[canonical_path],
        object_hashes=[object_hash],
        schema_fingerprint=schema_hash,
        content_fingerprint=content_hash,
        row_count=row_count,
        object_root=object_root,
    )
    expectation = ReplicaExpectation(
        logical_table=logical_table,
        source_version=source_version,
        version_id=version_id,
        content_fingerprint=content_hash,
        schema_fingerprint=schema_hash,
        row_count=row_count,
        object_hashes=(object_hash,),
    )
    schema_fields = [
        {"name": str(item[0]), "type": str(item[1])}
        for item in connection.execute(f"DESCRIBE SELECT * FROM read_parquet('{canonical_path.as_posix()}')").fetchall()
        if not str(item[0]).startswith("__aibi_")
    ]
    registry = {
        "workspace_id": "default",
        "table_key": table_key,
        "physical_table": logical_table,
        "data_version": data_version,
        "row_count": row_count,
        "active_version_id": version_id,
        "content_fingerprint": content_hash,
        "schema_fingerprint": schema_hash,
        "object_hashes": [object_hash],
        "schema_json": json.dumps(schema_fields, separators=(",", ":")),
    }
    return receipt, expectation, registry


def registry_connection(registry: dict[str, Any]) -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE table_registry("
        "workspace_id TEXT, table_key TEXT, physical_table TEXT, data_version INTEGER, row_count INTEGER, "
        "active_version_id TEXT, content_fingerprint TEXT, schema_fingerprint TEXT, object_hashes TEXT, schema_json TEXT)"
    )
    connection.execute(
        "INSERT INTO table_registry VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            registry["workspace_id"], registry["table_key"], registry["physical_table"],
            registry["data_version"], registry["row_count"], registry["active_version_id"],
            registry["content_fingerprint"], registry["schema_fingerprint"],
            json.dumps(registry["object_hashes"]), registry["schema_json"],
        ),
    )
    return connection


with closing(sqlite3.connect(":memory:")) as metadata_scale:
    metadata_scale.row_factory = sqlite3.Row
    metadata_scale.executescript(
        """
        CREATE TABLE table_registry(
          workspace_id TEXT, table_key TEXT, physical_table TEXT, data_version INTEGER,
          updated_at TEXT, active_version_id TEXT, schema_json TEXT, schema_fingerprint TEXT
        );
        CREATE TABLE field_semantics(
          workspace_id TEXT, table_key TEXT, field_name TEXT, role TEXT, usage TEXT,
          confidence REAL, tags_json TEXT, usage_json TEXT, source TEXT
        );
        CREATE TABLE relationships(
          workspace_id TEXT, relation_key TEXT, left_table_key TEXT, right_table_key TEXT,
          left_field TEXT, right_field TEXT, mappings_json TEXT, filters_json TEXT,
          preaggregation_json TEXT, join_type TEXT, confidence REAL, validation_json TEXT,
          updated_at TEXT
        );
        """
    )
    table_count = 1_000
    schema_json = json.dumps([{"name": "id", "type": "BIGINT"}, {"name": "amount", "type": "DOUBLE"}])
    metadata_scale.executemany(
        "INSERT INTO table_registry VALUES('default', ?, ?, 1, 't0', ?, ?, ?)",
        [
            (f"table_{index}", f"dataset_{index}", f"version_{index}", schema_json, fingerprint(f"schema:{index}"))
            for index in range(table_count)
        ],
    )
    metadata_scale.executemany(
        "INSERT INTO field_semantics VALUES('default', ?, ?, ?, '', 1.0, '[]', '{}', 'auto')",
        [
            (f"table_{index}", field, role)
            for index in range(table_count)
            for field, role in (("id", "identity_key"), ("amount", "measure"))
        ],
    )
    metadata_scale.executemany(
        "INSERT INTO relationships VALUES('default', ?, ?, ?, 'id', 'id', '[]', '[]', '{}', 'left', 1.0, '{}', 't0')",
        [
            (f"relation_{index}", f"table_{index}", f"table_{index + 1}")
            for index in range(table_count - 1)
        ],
    )
    metadata_scale.commit()
    metadata_statements: list[str] = []
    metadata_scale.set_trace_callback(metadata_statements.append)
    metadata_started = time.perf_counter()
    metadata_fingerprint = workspace_schema_fingerprint(metadata_scale, "default")
    metadata_seconds = time.perf_counter() - metadata_started
    metadata_scale.set_trace_callback(None)
    metadata_selects = [item for item in metadata_statements if item.lstrip().upper().startswith("SELECT")]
    check(
        "thousand-table-schema-fingerprint-uses-constant-query-count",
        len(metadata_fingerprint) == 64
        and len(metadata_selects) == 3
        and metadata_seconds < 2.0,
        {"selectCount": len(metadata_selects), "seconds": metadata_seconds},
    )


with tempfile.TemporaryDirectory(prefix="aibi-query-p0-") as temp_dir:
    temp = Path(temp_dir)
    database = temp / "analytics.duckdb"
    import duckdb  # type: ignore

    left_parquet = temp / "left.parquet"
    right_parquet = temp / "right.parquet"
    apparel_parquet = temp / "apparel.parquet"
    with closing(duckdb.connect(str(database))) as writer:
        write_parquet(
            writer,
            left_parquet,
            """
            SELECT * FROM (VALUES
              (1, ' A ', 'left-1'), (2, 'A', 'left-2'), (3, 'B', 'left-3'),
              (4, NULL, 'left-empty'), (5, 'D', 'left-5')
            ) AS rows(id, relation_key, payload)
            """,
        )
        write_parquet(
            writer,
            right_parquet,
            """
            SELECT * FROM (VALUES
              (10, 'A', 10.0), (11, 'A', 11.0), (12, 'C', 12.0)
            ) AS rows(id, relation_key, amount)
            """,
        )
        write_parquet(
            writer,
            apparel_parquet,
            """
            SELECT * FROM (VALUES
              ('S01', 100.0, '抖音', DATE '2026-05-01'),
              ('S02', 90.0, '抖音', DATE '2026-05-02'),
              ('S03', 80.0, '淘宝', DATE '2026-05-03'),
              ('S04', 70.0, '淘宝', DATE '2026-05-04'),
              ('S05', 60.0, '京东', DATE '2026-05-05'),
              ('S06', 50.0, '京东', DATE '2026-05-06'),
              ('S07', 40.0, '抖音', DATE '2026-05-07'),
              ('S08', 30.0, '抖音', DATE '2026-05-08'),
              ('S09', 20.0, '淘宝', DATE '2026-05-09'),
              ('S10', 10.0, '淘宝', DATE '2026-05-10'),
              ('S11', 5.0, '京东', DATE '2026-05-11'),
              ('S12', 5.0, '京东', DATE '2026-05-12')
            ) AS rows(style_spu, sales_amount, channel, paid_at)
            """,
        )
        left_receipt, left_expectation, left_registry = publish(
            writer,
            logical_table="left_dataset",
            table_key="left",
            data_version=1,
            row_count=5,
            parquet=left_parquet,
        )
        right_receipt, right_expectation, right_registry = publish(
            writer,
            logical_table="right_dataset",
            table_key="right",
            data_version=1,
            row_count=3,
            parquet=right_parquet,
        )
        apparel_receipt, apparel_expectation, apparel_registry = publish(
            writer,
            logical_table="apparel_dataset",
            table_key="apparel",
            data_version=1,
            row_count=12,
            parquet=apparel_parquet,
        )
        check(
            "manifest-v2-publishes-direct-parquet-views",
            all(item["status"] == "published" for item in (left_receipt, right_receipt, apparel_receipt))
            and "objectPaths" not in json.dumps(left_receipt),
            left_receipt,
        )
        manifest_row = writer.execute(
            "SELECT manifest_version, object_paths_json, object_hashes_json FROM __aibi_replica_manifest WHERE logical_table='left_dataset'"
        ).fetchone()
        check(
            "manifest-keeps-private-rebuild-paths-but-public-receipt-does-not",
            int(manifest_row[0]) == DATASET_MANIFEST_VERSION
            and f"/{file_sha256(left_parquet)}.parquet" in str(manifest_row[1])
            and left_receipt["objectHashes"] == json.loads(str(manifest_row[2])),
            {"manifestVersion": manifest_row[0], "receipt": left_receipt},
        )
        object_root = temp / "dataset-objects-v2"
        left_hash = file_sha256(left_parquet)
        right_hash = file_sha256(right_parquet)
        expect_runtime_error(
            "publication-rejects-object-key-path-misbinding",
            lambda: publish_dataset_view(
                writer,
                logical_table="rejected_binding",
                source_version="default:rejected:1:5",
                version_id="version-rejected-1",
                object_keys=[f"workspaces/default/objects/{left_hash[:2]}/{left_hash}.parquet"],
                object_paths=[object_root / f"workspaces/default/objects/{right_hash[:2]}/{right_hash}.parquet"],
                object_hashes=[left_hash],
                schema_fingerprint=fingerprint("schema:rejected"),
                content_fingerprint=fingerprint("content:rejected"),
                row_count=5,
                object_root=object_root,
            ),
            "dataset-object-path-mismatch",
        )

        traced_validation = TraceConnection(writer)
        validated = validate_replica_bindings(
            traced_validation,
            [left_expectation, right_expectation, left_expectation],
        )
        validation_sql = "\n".join(traced_validation.statements).upper()
        check(
            "manifest-validation-is-one-metadata-only-batch-query",
            len(traced_validation.statements) == 1
            and "COUNT(*) FROM LEFT_DATASET" not in validation_sql
            and "COUNT(*) FROM RIGHT_DATASET" not in validation_sql
            and len(validated) == 3,
            traced_validation.statements,
        )
        check(
            "validation-payload-never-leaks-private-paths",
            str(temp.resolve()) not in json.dumps(validated, ensure_ascii=False)
            and all(item.get("objectHashes") for item in validated),
            validated,
        )
        expect_runtime_error(
            "content-drift-fails-closed-without-business-count",
            lambda: validate_replica_bindings(writer, [ReplicaExpectation(
                **{**left_expectation.__dict__, "content_fingerprint": fingerprint("drift")}
            )]),
            "content-fingerprint-drift",
        )
        expect_runtime_error(
            "object-hash-drift-fails-closed-without-business-count",
            lambda: validate_replica_bindings(writer, [ReplicaExpectation(
                **{**left_expectation.__dict__, "object_hashes": (fingerprint("drift"),)}
            )]),
            "object-hash-drift",
        )
        traced_relationship = TraceConnection(writer)
        preview = build_relationship_preview(
            traced_relationship,
            "left_dataset",
            "right_dataset",
            ["id", "relation_key", "payload"],
            ["id", "relation_key", "amount"],
            [{"leftField": "relation_key", "rightField": "relation_key"}],
            join_type="left",
            sample_limit=50,
            quote_identifier=quote_identifier,
        )
        metrics = preview["metrics"]
        check(
            "relationship-preview-small-fixture-is-exact",
            {
                "leftRowsBeforeFilters": metrics["leftRowsBeforeFilters"],
                "rightRowsBeforeFilters": metrics["rightRowsBeforeFilters"],
                "leftRows": metrics["leftRows"],
                "rightRows": metrics["rightRows"],
                "leftDistinctKeys": metrics["leftDistinctKeys"],
                "rightDistinctKeys": metrics["rightDistinctKeys"],
                "overlapKeys": metrics["overlapKeys"],
                "matchedLeftRows": metrics["matchedLeftRows"],
                "matchedRightRows": metrics["matchedRightRows"],
                "joinedRows": metrics["joinedRows"],
                "outputRows": metrics["outputRows"],
                "leftDuplicateKeyGroups": metrics["leftDuplicateKeyGroups"],
                "rightDuplicateKeyGroups": metrics["rightDuplicateKeyGroups"],
                "leftEmptyKeyRows": metrics["leftEmptyKeyRows"],
            } == {
                "leftRowsBeforeFilters": 5,
                "rightRowsBeforeFilters": 3,
                "leftRows": 5,
                "rightRows": 3,
                "leftDistinctKeys": 3,
                "rightDistinctKeys": 2,
                "overlapKeys": 1,
                "matchedLeftRows": 2,
                "matchedRightRows": 2,
                "joinedRows": 4,
                "outputRows": 7,
                "leftDuplicateKeyGroups": 1,
                "rightDuplicateKeyGroups": 1,
                "leftEmptyKeyRows": 1,
            }
            and len(preview["rows"]) == 4
            and len(traced_relationship.statements) == 1
            and "ROW_NUMBER() OVER (PARTITION BY" not in traced_relationship.statements[0].upper(),
            preview,
        )
        preaggregated = build_relationship_preview(
            writer,
            "left_dataset",
            "right_dataset",
            ["id", "relation_key", "payload"],
            ["id", "relation_key", "amount"],
            [{"leftField": "relation_key", "rightField": "relation_key"}],
            join_type="left",
            sample_limit=10,
            quote_identifier=quote_identifier,
            preaggregation={
                "side": "right",
                "groupFields": ["relation_key"],
                "measures": [{"field": "amount", "aggregation": "sum"}],
            },
        )
        check(
            "relationship-preaggregation-is-set-based-and-exact",
            preaggregated["metrics"]["rightRows"] == 2
            and preaggregated["metrics"]["rightDuplicateKeyGroups"] == 0
            and preaggregated["metrics"]["joinedRows"] == 2
            and preaggregated["metrics"]["outputRows"] == 5,
            preaggregated,
        )

        control = sqlite3.connect(":memory:")
        control.row_factory = sqlite3.Row
        control.execute("CREATE TABLE field_semantics(workspace_id TEXT, table_key TEXT, field_name TEXT, role TEXT, confidence REAL)")
        control.executemany(
            "INSERT INTO field_semantics VALUES('default','apparel',?,?,?)",
            [("paid_at", "event_time", 1.0), ("style_spu", "dimension", 1.0)],
        )
        mapping_registry = {"physical_table": "apparel_dataset", "table_key": "apparel"}
        scope_trace = TraceConnection(writer)
        scope = _scope_snapshot(scope_trace, mapping_registry, ["style_spu", "channel", "paid_at"])
        time_trace = TraceConnection(writer)
        time_snapshot = _time_snapshot(
            control,
            time_trace,
            "default",
            mapping_registry,
            ["style_spu", "channel", "paid_at"],
        )
        check(
            "apparel-scope-and-time-fields-are-batched",
            len(scope_trace.statements) == 1
            and len(time_trace.statements) == 1
            and set(scope["values"]["channel"]) == {"京东", "抖音", "淘宝"}
            and time_snapshot["windows"]["paid_at"]["parsedRows"] == 12,
            {"scope": scope, "time": time_snapshot},
        )
        control.close()

    apparel_columns = ["style_spu", "sales_amount", "channel", "paid_at"]
    common_intent = {
        "entity": {"field": "style_spu"},
        "measure": {"field": "sales_amount"},
        "aggregation": {"function": "sum"},
        "sort": {"direction": "desc"},
        "filters": [],
    }
    apparel_results: dict[str, dict[str, Any]] = {}
    for method in ("ranking", "concentration", "pareto", "decile"):
        intent = {
            **common_intent,
            "method": method,
            "limit": {"count": 3, "percent": 0.2},
        }
        with closing(registry_connection(apparel_registry)) as method_control:
            result = execute_apparel_method(
                method_control,
                registry=apparel_registry,
                columns=apparel_columns,
                query_intent=intent,
                duckdb_path=database,
            )
        apparel_results[method] = dict(result or {})
    check(
        "apparel-window-sql-small-fixtures-are-exact",
        [row["businessKey"] for row in apparel_results["ranking"]["rows"]] == ["S01", "S02", "S03"]
        and apparel_results["concentration"]["evidence"]["targetEntityCount"] == 3
        and apparel_results["concentration"]["evidence"]["actualEntityCount"] == 3
        and apparel_results["pareto"]["evidence"]["entitiesToReach80"] == 6
        and apparel_results["decile"]["evidence"]["populationEntityCount"] == 12
        and all("OVER (" in item["runtime"]["compiledSql"] for item in apparel_results.values())
        and all(len(item["rows"]) <= MAX_APPAREL_EVIDENCE_ROWS for item in apparel_results.values()),
        apparel_results,
    )

    with closing(duckdb.connect(str(database))) as writer:
        writer.execute("CREATE VIEW perf_left AS SELECT i AS id, i % 500000 AS relation_key FROM range(1000000) AS rows(i)")
        writer.execute("CREATE VIEW perf_right AS SELECT i AS id, i % 500000 AS relation_key FROM range(1000000) AS rows(i)")
        tracemalloc.start()
        started = time.perf_counter()
        million_preview = build_relationship_preview(
            writer,
            "perf_left",
            "perf_right",
            ["id", "relation_key"],
            ["id", "relation_key"],
            [{"leftField": "relation_key", "rightField": "relation_key"}],
            join_type="left",
            sample_limit=20,
            quote_identifier=quote_identifier,
        )
        relationship_seconds = time.perf_counter() - started
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        check(
            "million-row-relationship-preview-is-bounded",
            relationship_seconds < PERFORMANCE_SECONDS
            and peak < PYTHON_MEMORY_BYTES
            and million_preview["metrics"]["leftRows"] == 1_000_000
            and million_preview["metrics"]["rightRows"] == 1_000_000
            and million_preview["metrics"]["overlapKeys"] == 500_000
            and million_preview["metrics"]["joinedRows"] == 2_000_000
            and len(million_preview["rows"]) <= 20 <= MAX_RELATIONSHIP_SAMPLE_ROWS,
            {"seconds": relationship_seconds, "peakPythonBytes": peak, "metrics": million_preview["metrics"]},
        )

    perf_parquet = temp / "apparel-million.parquet"
    with closing(duckdb.connect(str(database))) as writer:
        write_parquet(
            writer,
            perf_parquet,
            "SELECT 'STYLE-' || CAST(i AS VARCHAR) AS style_spu, CAST((i % 1000) + 1 AS DOUBLE) AS sales_amount FROM range(1000000) AS rows(i)",
        )
        _receipt, _expectation, perf_registry = publish(
            writer,
            logical_table="apparel_million",
            table_key="apparel_million",
            data_version=1,
            row_count=1_000_000,
            parquet=perf_parquet,
        )
    started = time.perf_counter()
    with closing(registry_connection(perf_registry)) as perf_control:
        million_ranking = execute_apparel_method(
            perf_control,
            registry=perf_registry,
            columns=["style_spu", "sales_amount"],
            query_intent={
                "method": "ranking",
                "entity": {"field": "style_spu"},
                "measure": {"field": "sales_amount"},
                "aggregation": {"function": "sum"},
                "sort": {"direction": "desc"},
                "filters": [],
                "limit": {"count": 10},
            },
            duckdb_path=database,
        )
    apparel_seconds = time.perf_counter() - started
    check(
        "million-row-apparel-ranking-is-windowed-and-bounded",
        bool(million_ranking)
        and apparel_seconds < PERFORMANCE_SECONDS
        and million_ranking["populationRowCount"] == 1_000_000
        and len(million_ranking["rows"]) <= MAX_APPAREL_EVIDENCE_ROWS
        and million_ranking["evidence"]["outputHardLimit"] == MAX_APPAREL_EVIDENCE_ROWS,
        {"seconds": apparel_seconds, "result": million_ranking},
    )


FAILED = [item for item in CHECKS if not item["ok"]]
print(json.dumps({
    "ok": not FAILED,
    "schema": "aibi-query-algorithm-p0-verification/v1",
    "generatedBy": "scripts/verify-query-algorithm-p0.py",
    "performanceBudgetSeconds": PERFORMANCE_SECONDS,
    "pythonMemoryBudgetBytes": PYTHON_MEMORY_BYTES,
    "checks": CHECKS,
    "failedChecks": FAILED,
}, ensure_ascii=False, indent=2, default=str))
raise SystemExit(1 if FAILED else 0)
