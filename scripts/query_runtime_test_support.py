from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from query_runtime import replica_source_version, sync_table_to_duckdb  # noqa: E402


def publish_sqlite_fixture_to_duckdb(connection: sqlite3.Connection, duckdb_path: Path) -> None:
    """Test-only writer: publish simplified SQLite fixtures through the real replica protocol."""
    registry_columns = [str(row[1]) for row in connection.execute("PRAGMA table_info(table_registry)")]
    if "row_count" not in registry_columns:
        connection.execute("ALTER TABLE table_registry ADD COLUMN row_count INTEGER NOT NULL DEFAULT 0")
    registries = connection.execute("SELECT * FROM table_registry ORDER BY table_key").fetchall()
    for registry in registries:
        physical_table = str(registry["physical_table"])
        row_count = int(connection.execute(f'SELECT COUNT(*) FROM "{physical_table}"').fetchone()[0] or 0)
        connection.execute(
            "UPDATE table_registry SET row_count = ? WHERE workspace_id = ? AND table_key = ?",
            (row_count, registry["workspace_id"], registry["table_key"]),
        )
    connection.commit()
    if duckdb_path.exists():
        duckdb_path.unlink()
    import duckdb  # type: ignore

    with duckdb.connect(str(duckdb_path)) as duck_connection:
        for registry in connection.execute("SELECT * FROM table_registry ORDER BY table_key").fetchall():
            physical_table = str(registry["physical_table"])
            columns = [str(row[1]) for row in connection.execute(f'PRAGMA table_info("{physical_table}")')]
            sync_table_to_duckdb(
                connection,
                duck_connection,
                physical_table,
                columns,
                source_version=replica_source_version(registry),
                cleanup_stale=False,
            )
