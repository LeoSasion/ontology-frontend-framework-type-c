from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from bi_cli_schema import (  # noqa: E402
    CURRENT_SQLITE_SCHEMA_VERSION,
    ensure_schema,
    sqlite_schema_version,
)


CURRENT_DUCKDB_SCHEMA_VERSION = 1
DUCKDB_METADATA_TABLE = "__aibi_schema_metadata"


def _sqlite_read_only(path: Path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path.resolve().as_posix()}?mode=ro", uri=True)


def inspect_sqlite(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {
            "kind": "sqlite",
            "path": str(path) if path else None,
            "exists": False,
            "version": None,
            "currentVersion": CURRENT_SQLITE_SCHEMA_VERSION,
            "compatible": True,
            "integrity": "not-present",
        }
    with _sqlite_read_only(path) as connection:
        version = sqlite_schema_version(connection)
        integrity = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
    return {
        "kind": "sqlite",
        "path": str(path.resolve()),
        "exists": True,
        "version": version,
        "currentVersion": CURRENT_SQLITE_SCHEMA_VERSION,
        "compatible": version <= CURRENT_SQLITE_SCHEMA_VERSION and integrity == "ok",
        "requiresMigration": version < CURRENT_SQLITE_SCHEMA_VERSION,
        "integrity": integrity,
    }


def _duckdb_module():
    try:
        import duckdb  # type: ignore
    except ImportError as error:
        raise RuntimeError("DuckDB runtime is unavailable; schema compatibility cannot be verified.") from error
    return duckdb


def _duckdb_version(connection: Any) -> int:
    exists = connection.execute(
        "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?",
        [DUCKDB_METADATA_TABLE],
    ).fetchone()[0]
    if not exists:
        return 0
    row = connection.execute(
        f'SELECT value FROM "{DUCKDB_METADATA_TABLE}" WHERE key = ?',
        ["schema_version"],
    ).fetchone()
    return int(row[0]) if row else 0


def inspect_duckdb(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {
            "kind": "duckdb",
            "path": str(path) if path else None,
            "exists": False,
            "version": None,
            "currentVersion": CURRENT_DUCKDB_SCHEMA_VERSION,
            "compatible": True,
            "integrity": "not-present",
        }
    duckdb = _duckdb_module()
    with duckdb.connect(str(path.resolve()), read_only=True) as connection:
        version = _duckdb_version(connection)
        connection.execute("SELECT 1").fetchone()
    return {
        "kind": "duckdb",
        "path": str(path.resolve()),
        "exists": True,
        "version": version,
        "currentVersion": CURRENT_DUCKDB_SCHEMA_VERSION,
        "compatible": version <= CURRENT_DUCKDB_SCHEMA_VERSION,
        "requiresMigration": version < CURRENT_DUCKDB_SCHEMA_VERSION,
        "integrity": "ok",
    }


def migrate_sqlite(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return inspect_sqlite(path)
    before = inspect_sqlite(path)
    if not before["compatible"]:
        raise RuntimeError(
            f"SQLite schema v{before['version']} is not compatible with runtime v{CURRENT_SQLITE_SCHEMA_VERSION}."
        )
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        ensure_schema(connection)
    finally:
        connection.close()
    after = inspect_sqlite(path)
    if not after["compatible"] or after["version"] != CURRENT_SQLITE_SCHEMA_VERSION:
        raise RuntimeError("SQLite migration validation failed.")
    return {"kind": "sqlite", "before": before, "after": after}


def migrate_duckdb(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return inspect_duckdb(path)
    before = inspect_duckdb(path)
    if not before["compatible"]:
        raise RuntimeError(
            f"DuckDB schema v{before['version']} is not compatible with runtime v{CURRENT_DUCKDB_SCHEMA_VERSION}."
        )
    duckdb = _duckdb_module()
    with duckdb.connect(str(path.resolve())) as connection:
        connection.execute(
            f'CREATE TABLE IF NOT EXISTS "{DUCKDB_METADATA_TABLE}" (key VARCHAR PRIMARY KEY, value VARCHAR NOT NULL)'
        )
        connection.execute(
            f'INSERT OR REPLACE INTO "{DUCKDB_METADATA_TABLE}" (key, value) VALUES (?, ?)',
            ["schema_version", str(CURRENT_DUCKDB_SCHEMA_VERSION)],
        )
    after = inspect_duckdb(path)
    if not after["compatible"] or after["version"] != CURRENT_DUCKDB_SCHEMA_VERSION:
        raise RuntimeError("DuckDB migration validation failed.")
    return {"kind": "duckdb", "before": before, "after": after}


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect or migrate AIBI-C local database schemas.")
    parser.add_argument("command", choices=["inspect", "migrate"])
    parser.add_argument("--sqlite")
    parser.add_argument("--duckdb")
    args = parser.parse_args()
    sqlite_path = Path(args.sqlite).resolve() if args.sqlite else None
    duckdb_path = Path(args.duckdb).resolve() if args.duckdb else None
    if args.command == "inspect":
        databases = [inspect_sqlite(sqlite_path), inspect_duckdb(duckdb_path)]
    else:
        databases = [migrate_sqlite(sqlite_path), migrate_duckdb(duckdb_path)]
    compatible = all(
        item.get("compatible", item.get("after", {}).get("compatible", False))
        for item in databases
    )
    payload = {
        "ok": compatible,
        "schema": "aibi-local-schema-migration/v1",
        "command": args.command,
        "databases": databases,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if compatible else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({
            "ok": False,
            "schema": "aibi-local-schema-migration/v1",
            "error": str(error),
        }, ensure_ascii=False, indent=2))
        raise SystemExit(1)
