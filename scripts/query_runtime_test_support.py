from __future__ import annotations

"""Test-only builders for the v2 Parquet/DuckDB data plane.

The helpers deliberately exercise the production publication protocol:

1. write a typed Parquet object with a stable ``__aibi_row_id``;
2. seal it through :mod:`dataset_version_store`;
3. persist and activate the version in SQLite's metadata catalogue; and
4. publish a DuckDB view through :func:`query_runtime.publish_dataset_view`.

SQLite is never used as the query source. Verification fixtures must declare
typed rows explicitly and follow the same immutable v2 publication path as
production imports.
"""

import json
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from dataset_version_store import (  # noqa: E402
    activate_dataset_version,
    prepare_dataset_version,
    publish_dataset_version,
    registry_columns,
    resolve_dataset_object_paths,
)
from bi_cli_schema import initialize_schema  # noqa: E402
from query_runtime import publish_dataset_view, replica_source_version  # noqa: E402


_SAFE_TYPE = re.compile(
    r"^(?:BOOLEAN|TINYINT|SMALLINT|INTEGER|BIGINT|HUGEINT|FLOAT|DOUBLE|REAL|"
    r"DATE|TIMESTAMP|TIMESTAMP WITH TIME ZONE|VARCHAR|BLOB|UUID|"
    r"DECIMAL\([1-9][0-9]?,\s*[0-9]{1,2}\))$",
    re.IGNORECASE,
)

_FIXTURE_TIMESTAMP = "2026-07-01T00:00:00Z"


@dataclass(frozen=True)
class FixtureTable:
    workspace_id: str
    table_key: str
    physical_table: str
    columns: tuple[tuple[str, str], ...]
    rows: tuple[tuple[Any, ...], ...]
    data_version: int = 1
    display_name: str = ""
    source_file: str = "typed-fixture"


def initialize_fixture_control_plane(connection: sqlite3.Connection) -> None:
    """Build the exact clean-v18 control contract for analytical fixtures."""

    connection.row_factory = sqlite3.Row
    initialize_schema(connection)


def quote_identifier(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _sql_string(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _duckdb_type(value: str) -> str:
    normalized = " ".join(str(value or "VARCHAR").strip().upper().split())
    if not _SAFE_TYPE.fullmatch(normalized):
        raise ValueError(f"Fixture contains an unsupported DuckDB type: {value}")
    return normalized


_REQUIRED_REGISTRY_V2_COLUMNS = {
    "workspace_id",
    "table_key",
    "physical_table",
    "display_name",
    "source_file",
    "row_count",
    "column_count",
    "data_version",
    "active_version_id",
    "schema_json",
    "schema_fingerprint",
    "content_fingerprint",
}


def _require_registry_v2(connection: sqlite3.Connection) -> None:
    existing = {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(table_registry)").fetchall()
    }
    missing = sorted(_REQUIRED_REGISTRY_V2_COLUMNS - existing)
    if missing:
        raise RuntimeError(
            "Fixture metadata must use the clean v2 table_registry contract; "
            f"missing columns: {', '.join(missing)}"
        )


def fixture_table_columns(connection: sqlite3.Connection, physical_table: str) -> list[str]:
    """Read public columns from v2 registry schema metadata, never SQLite row tables."""

    _require_registry_v2(connection)
    return registry_columns(connection, physical_table)


def _write_typed_parquet(
    duck_connection: Any,
    *,
    table: FixtureTable,
    prepared_path: Path,
) -> None:
    columns = [(str(name), _duckdb_type(data_type)) for name, data_type in table.columns]
    if not columns:
        raise ValueError("Fixture table requires at least one public column.")
    if len({name for name, _ in columns}) != len(columns):
        raise ValueError("Fixture table contains duplicate columns.")
    if any(name.startswith("__aibi_") for name, _ in columns):
        raise ValueError("Fixture public columns may not use the internal namespace.")
    expected_width = len(columns)
    if any(len(row) != expected_width for row in table.rows):
        raise ValueError("Fixture row width does not match its typed schema.")

    staging = f"__aibi_fixture_{uuid4().hex}"
    definitions = ", ".join(
        f"{quote_identifier(name)} {data_type}" for name, data_type in columns
    )
    duck_connection.execute(
        f"CREATE TEMP TABLE {quote_identifier(staging)} "
        f"({quote_identifier('__aibi_row_id')} BIGINT, {definitions})"
    )
    try:
        if table.rows:
            placeholders = ", ".join("?" for _ in range(expected_width + 1))
            duck_connection.executemany(
                f"INSERT INTO {quote_identifier(staging)} VALUES ({placeholders})",
                [
                    (ordinal, *tuple(row))
                    for ordinal, row in enumerate(table.rows, start=1)
                ],
            )
        prepared_path.parent.mkdir(parents=True, exist_ok=True)
        duck_connection.execute(
            f"COPY (SELECT * FROM {quote_identifier(staging)} "
            f"ORDER BY {quote_identifier('__aibi_row_id')}) "
            f"TO {_sql_string(prepared_path.as_posix())} "
            "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 122880)"
        )
    finally:
        duck_connection.execute(f"DROP TABLE IF EXISTS {quote_identifier(staging)}")


def _upsert_registry(
    connection: sqlite3.Connection,
    *,
    table: FixtureTable,
) -> None:
    existing = connection.execute(
        "SELECT 1 FROM table_registry WHERE workspace_id = ? AND table_key = ?",
        (table.workspace_id, table.table_key),
    ).fetchone()
    if existing is None:
        columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(table_registry)").fetchall()
        }
        required = {"workspace_id", "table_key", "physical_table"}
        if not required.issubset(columns):
            raise RuntimeError("Fixture table_registry is missing its identity columns.")
        values: dict[str, Any] = {
            "workspace_id": table.workspace_id,
            "table_key": table.table_key,
            "physical_table": table.physical_table,
            "display_name": table.display_name or table.table_key,
            "source_file": table.source_file,
            "row_count": len(table.rows),
            "column_count": len(table.columns),
            "data_version": table.data_version,
            "created_at": _FIXTURE_TIMESTAMP,
            "updated_at": _FIXTURE_TIMESTAMP,
        }
        available = [(name, value) for name, value in values.items() if name in columns]
        connection.execute(
            f"INSERT INTO table_registry "
            f"({', '.join(quote_identifier(name) for name, _ in available)}) "
            f"VALUES ({', '.join('?' for _ in available)})",
            [value for _, value in available],
        )
    else:
        connection.execute(
            "UPDATE table_registry SET physical_table = ?, source_file = ?, "
            "row_count = ?, column_count = ?, data_version = ? "
            "WHERE workspace_id = ? AND table_key = ?",
            (
                table.physical_table,
                table.source_file,
                len(table.rows),
                len(table.columns),
                table.data_version,
                table.workspace_id,
                table.table_key,
            ),
        )


def _publish_table(
    connection: sqlite3.Connection,
    duck_connection: Any,
    *,
    duckdb_path: Path,
    object_root: Path,
    table: FixtureTable,
) -> dict[str, Any]:
    _upsert_registry(connection, table=table)
    prepared_path = duckdb_path.parent / f".{table.physical_table}.{uuid4().hex}.parquet"
    try:
        _write_typed_parquet(duck_connection, table=table, prepared_path=prepared_path)
        manifest = prepare_dataset_version(
            workspace_id=table.workspace_id,
            table_key=table.table_key,
            parquet_path=prepared_path,
            schema_fields=[{"name": name, "type": data_type} for name, data_type in table.columns],
            row_count=len(table.rows),
            source_file=table.source_file,
            object_root=object_root,
        )
    finally:
        prepared_path.unlink(missing_ok=True)

    publish_dataset_version(connection, manifest)
    activate_dataset_version(connection, manifest)
    connection.commit()
    registry = connection.execute(
        "SELECT * FROM table_registry WHERE workspace_id = ? AND table_key = ?",
        (table.workspace_id, table.table_key),
    ).fetchone()
    if registry is None:
        raise RuntimeError("Fixture registry activation disappeared.")
    object_paths = resolve_dataset_object_paths(manifest, root=object_root)
    replica = publish_dataset_view(
        duck_connection,
        logical_table=table.physical_table,
        source_version=replica_source_version(registry),
        version_id=str(manifest["versionId"]),
        object_keys=[str(item["objectKey"]) for item in manifest["files"]],
        object_paths=object_paths,
        object_hashes=[str(item["objectHash"]) for item in manifest["files"]],
        schema_fingerprint=str(manifest["schemaFingerprint"]),
        content_fingerprint=str(manifest["contentFingerprint"]),
        row_count=int(manifest["rowCount"]),
        object_root=object_root,
    )
    return {
        "manifest": manifest,
        "replica": replica,
        "objectPaths": object_paths,
        "objectRoot": object_root,
        "registry": dict(registry),
    }


def publish_fixture_tables_to_duckdb(
    connection: sqlite3.Connection,
    duckdb_path: Path,
    tables: Sequence[FixtureTable],
    *,
    reset: bool = True,
) -> dict[str, dict[str, Any]]:
    """Publish native typed fixtures and return their complete v2 bindings."""

    if not tables:
        raise ValueError("At least one fixture table is required.")
    connection.row_factory = sqlite3.Row
    _require_registry_v2(connection)
    connection.commit()
    duckdb_path = Path(duckdb_path).resolve()
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    object_root = duckdb_path.parent / f"{duckdb_path.stem}-dataset-objects-v2"
    if reset:
        duckdb_path.unlink(missing_ok=True)

    import duckdb  # type: ignore

    receipts: dict[str, dict[str, Any]] = {}
    with duckdb.connect(str(duckdb_path)) as duck_connection:
        for table in tables:
            receipts[table.table_key] = _publish_table(
                connection,
                duck_connection,
                duckdb_path=duckdb_path,
                object_root=object_root,
                table=table,
            )
    return receipts


def registry_binding_json(receipt: Mapping[str, Any]) -> str:
    """Stable diagnostic representation used by verification receipts."""

    manifest = receipt["manifest"]
    return json.dumps(
        {
            "versionId": manifest["versionId"],
            "schemaFingerprint": manifest["schemaFingerprint"],
            "contentFingerprint": manifest["contentFingerprint"],
            "objectHashes": [item["objectHash"] for item in manifest["files"]],
            "rowCount": manifest["rowCount"],
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
