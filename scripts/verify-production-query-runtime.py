from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
sys.path.insert(0, str(TOOLS))

from query_runtime import (  # noqa: E402
    QueryRuntimeError,
    ReplicaExpectation,
    compile_filter_sql,
    duckdb_status,
    open_validated_duckdb_query,
)
from platform_analytics_knowledge import execute_platform_knowledge  # noqa: E402


checks: list[dict[str, Any]] = []


def check(label: str, ok: bool, detail: Any = "") -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": "" if ok else detail})


def error_code(action: Callable[[], Any]) -> str:
    try:
        action()
    except QueryRuntimeError as error:
        return str(error)
    return ""


def create_replica(path: Path, *, view: bool = True, physical: bool = True, manifest_rows: int = 2, physical_rows: int = 2) -> None:
    import duckdb  # type: ignore

    with duckdb.connect(str(path)) as connection:
        connection.execute(
            "CREATE TABLE __aibi_replica_manifest(logical_table VARCHAR PRIMARY KEY, source_version VARCHAR, replica_table VARCHAR, row_count BIGINT, published_at TIMESTAMP)"
        )
        if physical:
            connection.execute("CREATE TABLE __aibi_replica_fixture(label VARCHAR, value VARCHAR)")
            for index in range(physical_rows):
                connection.execute("INSERT INTO __aibi_replica_fixture VALUES (?, ?)", [f"row-{index}", str(index)])
        if view and physical:
            connection.execute("CREATE VIEW fixture AS SELECT * FROM __aibi_replica_fixture")
        connection.execute(
            "INSERT INTO __aibi_replica_manifest VALUES ('fixture', 'default:fixture:1:2', '__aibi_replica_fixture', ?, current_timestamp)",
            [manifest_rows],
        )


with tempfile.TemporaryDirectory(prefix="aibi-c-production-query-") as temp_dir:
    root = Path(temp_dir)
    missing_path = root / "missing.duckdb"
    expectation = ReplicaExpectation("fixture", "default:fixture:1:2", 2)
    status = duckdb_status(missing_path)
    check(
        "missing-database-status-is-blocked-without-fallback",
        status["queryAvailability"] == "blocked"
        and status["reasonCode"] == "replica-database-missing"
        and status["fallbackEngine"] is None,
        status,
    )
    check(
        "missing-replica-database-fails-closed",
        error_code(lambda: open_validated_duckdb_query(missing_path, [expectation]).__enter__()) == "replica-database-missing",
    )

    manifest_missing = root / "manifest-missing.duckdb"
    import duckdb  # type: ignore

    with duckdb.connect(str(manifest_missing)) as connection:
        connection.execute("CREATE TABLE fixture(label VARCHAR)")
    check(
        "missing-manifest-fails-closed",
        error_code(lambda: open_validated_duckdb_query(manifest_missing, [expectation]).__enter__()) == "replica-manifest-missing",
    )

    half_published = root / "half-published.duckdb"
    create_replica(half_published, view=False)
    check(
        "half-published-view-fails-closed",
        error_code(lambda: open_validated_duckdb_query(half_published, [expectation]).__enter__())
        == "replica-view-not-published:fixture",
    )

    physical_missing = root / "physical-missing.duckdb"
    create_replica(physical_missing, view=False, physical=False)
    check(
        "missing-physical-replica-fails-closed",
        error_code(lambda: open_validated_duckdb_query(physical_missing, [expectation]).__enter__())
        == "replica-table-missing:fixture",
    )

    stale = root / "stale.duckdb"
    create_replica(stale)
    stale_expectation = ReplicaExpectation("fixture", "default:fixture:2:2", 2)
    check(
        "stale-version-fails-closed",
        error_code(lambda: open_validated_duckdb_query(stale, [stale_expectation]).__enter__())
        == "replica-version-stale:fixture",
    )
    row_drift_expectation = ReplicaExpectation("fixture", "default:fixture:1:2", 3)
    check(
        "registry-manifest-row-drift-fails-closed",
        error_code(lambda: open_validated_duckdb_query(stale, [row_drift_expectation]).__enter__())
        == "replica-row-count-drift:fixture",
    )

    content_drift = root / "content-drift.duckdb"
    create_replica(content_drift, manifest_rows=2, physical_rows=1)
    check(
        "manifest-content-drift-fails-closed",
        error_code(lambda: open_validated_duckdb_query(content_drift, [expectation]).__enter__())
        == "replica-content-drift:fixture",
    )

    secrets = ["buyer@example.com", "token-super-secret", r"C:\private\customer-data.csv"]
    filter_sql, filter_params = compile_filter_sql(
        [
            {"field": "email", "operator": "equals", "value": secrets[0]},
            {"field": "token", "operator": "contains", "value": secrets[1]},
            {"field": "source", "operator": "not-equals", "value": secrets[2]},
        ],
        dialect="duckdb",
    )
    with open_validated_duckdb_query(stale, [expectation]) as query:
        runtime = query.runtime(compiled_sql=filter_sql, params=filter_params)
        read_rows = query.rows("SELECT label, value FROM fixture ORDER BY label")
        write_error = error_code(lambda: query.execute("CREATE TABLE forbidden_write(value INTEGER)"))
    encoded_runtime = json.dumps(runtime, ensure_ascii=False)
    check(
        "filters-are-parameterized-not-interpolated",
        filter_sql.count("?") == 3 and all(secret not in filter_sql for secret in secrets) and filter_params == secrets,
        {"sql": filter_sql, "params": filter_params},
    )
    check(
        "public-runtime-redacts-email-token-and-path",
        runtime["parameterCount"] == 3
        and len(runtime["parameterFingerprint"]) == 64
        and "params" not in runtime
        and all(secret not in encoded_runtime for secret in secrets),
        runtime,
    )
    check(
        "validated-reader-is-current-and-read-only",
        len(read_rows) == 2 and write_error == "replica-query-failed",
        {"rows": read_rows, "writeError": write_error},
    )
    platform_result = execute_platform_knowledge(
        None,  # type: ignore[arg-type] -- execution reads only the validated replica
        {
            "entity": None,
            "threshold": None,
            "sql": "SELECT 'Total' AS label, COUNT(*) AS value FROM fixture",
            "title": "Fixture total",
            "ruleId": "fixture-total",
            "grain": "fixture",
            "packId": "platform-commerce",
            "packVersion": "1.0.0",
            "source": {"type": "test"},
            "roles": {
                "fact": {
                    "workspace_id": "default",
                    "table_key": "fixture",
                    "display_name": "Fixture",
                    "physical_table": "fixture",
                    "data_version": 1,
                    "row_count": 2,
                }
            },
        },
        duckdb_path=stale,
    )
    check(
        "platform-knowledge-executes-only-on-current-replica",
        platform_result["query"]["runtime"]["engine"] == "duckdb"
        and platform_result["query"]["runtime"]["queryAvailability"] == "current"
        and int(platform_result["rows"][0]["value"]) == 2,
        platform_result,
    )


production_files = [
    "query_runtime.py",
    "table_query_tools.py",
    "saved_view_query_service.py",
    "metric_formula_command_service.py",
    "relationship_command_service.py",
    "relationship_tools.py",
    "semantic_query_execution.py",
    "platform_analytics_knowledge.py",
    "apparel_analytics_service.py",
    "apparel_entity_mapping_service.py",
    "aibi_runtime/use_cases/agent_interaction.py",
]
sources = {name: (TOOLS / name).read_text(encoding="utf-8") for name in production_files}
combined = "\n".join(sources.values())
forbidden_runtime_markers = [
    '"engine": "sqlite"',
    '"database": "metadata-store"',
    "sqlite-detail",
    "sqlite-aggregate",
    "sqlite-formula-metric",
    "run_sqlite_aggregate_query",
]
check(
    "production-query-inventory-bans-sqlite-business-results",
    all(marker not in combined for marker in forbidden_runtime_markers),
    [marker for marker in forbidden_runtime_markers if marker in combined],
)
required_routing_markers = {
    "saved_view_query_service.py": "open_validated_duckdb_query",
    "metric_formula_command_service.py": "open_validated_duckdb_query",
    "relationship_command_service.py": "open_validated_duckdb_query",
    "semantic_query_execution.py": "open_validated_duckdb_query",
    "platform_analytics_knowledge.py": "open_validated_duckdb_query",
    "apparel_analytics_service.py": "open_validated_duckdb_query",
    "apparel_entity_mapping_service.py": "open_validated_duckdb_query",
    "aibi_runtime/use_cases/agent_interaction.py": "open_validated_duckdb_query",
}
check(
    "production-business-row-consumers-use-validated-reader",
    all(marker in sources[name] for name, marker in required_routing_markers.items()),
    [name for name, marker in required_routing_markers.items() if marker not in sources[name]],
)
check(
    "query-runtime-has-no-sqlite-fallback-api",
    '"fallbackEngine": None' in sources["query_runtime.py"]
    and "run_sqlite_aggregate_query" not in sources["query_runtime.py"],
)


failed = [item for item in checks if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-production-query-runtime-verify/v1",
    "checks": checks,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
