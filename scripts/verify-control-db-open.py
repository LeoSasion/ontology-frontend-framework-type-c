from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import bi_cli_schema as schema  # noqa: E402
from dataset_version_store import assert_dataset_version_schema  # noqa: E402
from source_activation_journal_service import assert_activation_journal_schema  # noqa: E402


def main() -> int:
    checks: list[dict[str, Any]] = []

    def check(label: str, ok: Any, detail: Any = None) -> None:
        checks.append({"label": label, "ok": bool(ok), "detail": None if ok else detail})

    original_db_path = schema.DB_PATH
    original_duckdb_path = schema.DUCKDB_PATH
    with tempfile.TemporaryDirectory(prefix="aibi-control-db-open-") as temp_dir:
        root = Path(temp_dir)
        control_path = root / "control.sqlite"
        schema.DB_PATH = control_path
        schema.DUCKDB_PATH = root / "catalog.duckdb"
        try:
            started = time.perf_counter()
            with closing(schema.open_db()) as connection:
                check(
                    "empty-file-initializes-v18",
                    schema.sqlite_schema_version(connection) == schema.CURRENT_SQLITE_SCHEMA_VERSION,
                    schema.sqlite_schema_version(connection),
                )
                check(
                    "empty-file-has-complete-control-table-set",
                    {
                        str(row["name"])
                        for row in connection.execute(
                            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                        )
                    }
                    >= schema.REQUIRED_CONTROL_TABLES,
                    sorted(schema.REQUIRED_CONTROL_TABLES),
                )
                canonical_columns = dict(schema._canonical_control_columns())
                check(
                    "canonical-contract-covers-every-required-table",
                    set(canonical_columns) == schema.REQUIRED_CONTROL_TABLES
                    and all(canonical_columns.values()),
                    sorted(set(schema.REQUIRED_CONTROL_TABLES) - set(canonical_columns)),
                )
                connection.execute("PRAGMA query_only = ON")
                traced_statements: list[str] = []
                connection.set_trace_callback(traced_statements.append)
                try:
                    assert_dataset_version_schema(connection)
                    assert_activation_journal_schema(connection)
                finally:
                    connection.set_trace_callback(None)
                schema_writes = [
                    statement
                    for statement in traced_statements
                    if statement.lstrip().split(None, 1)[0].upper()
                    in {"ALTER", "CREATE", "DROP", "REINDEX"}
                ]
                check(
                    "feature-schema-guards-are-read-only",
                    not schema_writes,
                    schema_writes,
                )
            init_ms = round((time.perf_counter() - started) * 1000, 2)

            before_mtime = control_path.stat().st_mtime_ns
            original_initialize = schema.initialize_schema
            original_ensure = schema.ensure_schema
            original_duckdb_check = schema.assert_duckdb_schema_compatible
            original_navigation = schema.ensure_navigation_modules

            def forbidden(*_args: Any, **_kwargs: Any) -> None:
                raise AssertionError("legacy initialization or external storage check was invoked")

            schema.initialize_schema = forbidden
            schema.ensure_schema = forbidden
            schema.assert_duckdb_schema_compatible = forbidden
            schema.ensure_navigation_modules = forbidden
            try:
                started = time.perf_counter()
                with closing(schema.open_db()) as connection:
                    check(
                        "existing-v18-open-is-read-only",
                        schema.sqlite_schema_version(connection) == schema.CURRENT_SQLITE_SCHEMA_VERSION,
                        schema.sqlite_schema_version(connection),
                    )
                hot_open_ms = round((time.perf_counter() - started) * 1000, 2)
            except Exception as error:  # noqa: BLE001 - verification records the failure.
                check("existing-v18-open-is-read-only", False, str(error))
                hot_open_ms = None
            finally:
                schema.initialize_schema = original_initialize
                schema.ensure_schema = original_ensure
                schema.assert_duckdb_schema_compatible = original_duckdb_check
                schema.ensure_navigation_modules = original_navigation
            check(
                "existing-v18-open-does-not-write",
                control_path.stat().st_mtime_ns == before_mtime,
                {"before": before_mtime, "after": control_path.stat().st_mtime_ns},
            )

            incomplete_path = root / "incomplete.sqlite"
            with closing(sqlite3.connect(incomplete_path)) as connection:
                connection.row_factory = sqlite3.Row
                schema._initialize_schema(connection)
                connection.execute("DROP TABLE decision_frameworks")
                connection.commit()
            schema.DB_PATH = incomplete_path
            incomplete_mtime = incomplete_path.stat().st_mtime_ns
            try:
                schema.open_db().close()
            except RuntimeError as error:
                check("incomplete-v18-file-is-rejected", "missing tables" in str(error), str(error))
            else:
                check("incomplete-v18-file-is-rejected", False, "incomplete schema was accepted")
            check(
                "incomplete-v18-rejection-does-not-write",
                incomplete_path.stat().st_mtime_ns == incomplete_mtime,
                {"before": incomplete_mtime, "after": incomplete_path.stat().st_mtime_ns},
            )

            incomplete_column_path = root / "incomplete-column.sqlite"
            with closing(sqlite3.connect(incomplete_column_path)) as connection:
                connection.row_factory = sqlite3.Row
                schema._initialize_schema(connection)
                connection.execute("DROP TABLE agent_context_snapshots")
                connection.execute(
                    "CREATE TABLE agent_context_snapshots(snapshot_key TEXT PRIMARY KEY)"
                )
                connection.commit()
            schema.DB_PATH = incomplete_column_path
            incomplete_column_mtime = incomplete_column_path.stat().st_mtime_ns
            try:
                schema.open_db().close()
            except RuntimeError as error:
                check(
                    "arbitrary-missing-v18-column-is-rejected",
                    "agent_context_snapshots is missing columns" in str(error),
                    str(error),
                )
            else:
                check(
                    "arbitrary-missing-v18-column-is-rejected",
                    False,
                    "incomplete table columns were accepted",
                )
            check(
                "missing-column-rejection-does-not-write",
                incomplete_column_path.stat().st_mtime_ns == incomplete_column_mtime,
                {
                    "before": incomplete_column_mtime,
                    "after": incomplete_column_path.stat().st_mtime_ns,
                },
            )

            legacy_path = root / "legacy.sqlite"
            with closing(sqlite3.connect(legacy_path)) as connection:
                connection.execute("CREATE TABLE legacy_business_rows(value TEXT)")
                connection.execute("PRAGMA user_version = 17")
                connection.commit()
            schema.DB_PATH = legacy_path
            try:
                schema.open_db().close()
            except RuntimeError as error:
                check("legacy-file-is-rejected-without-migration", "no migration" in str(error), str(error))
            else:
                check("legacy-file-is-rejected-without-migration", False, "legacy schema was accepted")

            with closing(sqlite3.connect(":memory:")) as fixture_connection:
                schema.ensure_schema(fixture_connection)
                check(
                    "explicit-empty-fixture-can-initialize",
                    schema.assert_control_schema_invariants(fixture_connection)
                    == schema.CURRENT_SQLITE_SCHEMA_VERSION,
                    schema.sqlite_schema_version(fixture_connection),
                )

            with closing(sqlite3.connect(":memory:")) as populated_fixture:
                populated_fixture.execute("CREATE TABLE legacy_business_rows(value TEXT)")
                try:
                    schema.ensure_schema(populated_fixture)
                except RuntimeError as error:
                    check("populated-fixture-is-not-repaired", "no migration" in str(error), str(error))
                else:
                    check("populated-fixture-is-not-repaired", False, "populated fixture was repaired")
        finally:
            schema.DB_PATH = original_db_path
            schema.DUCKDB_PATH = original_duckdb_path

    failed = [item for item in checks if not item["ok"]]
    print(
        json.dumps(
            {
                "ok": not failed,
                "schema": "aibi-control-db-open-verify/v1",
                "checks": checks,
                "failedChecks": failed,
                "timingsMs": {"initialization": init_ms, "existingOpen": hot_open_ms},
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
