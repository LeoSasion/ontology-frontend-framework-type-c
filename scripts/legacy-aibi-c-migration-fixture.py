from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def create_sqlite(path: Path, version: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE legacy_aibi_c_receipt(product TEXT NOT NULL, value TEXT NOT NULL)")
        connection.execute(
            "INSERT INTO legacy_aibi_c_receipt(product, value) VALUES(?, ?)",
            ("AIBI-C", "preserve-me"),
        )
        if version == 1:
            connection.execute(
                "CREATE TABLE workspaces(id TEXT PRIMARY KEY, name TEXT NOT NULL, current_source_run_id TEXT, created_at TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO workspaces(id, name, current_source_run_id, created_at) VALUES('workspace-red', '红色工作区', NULL, '2026-07-14T00:00:00Z')"
            )
            connection.execute("CREATE TABLE system_flags(key TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL)")
            connection.execute(
                "INSERT INTO system_flags(key, value, updated_at) VALUES('active_workspace_id', 'workspace-red', '2026-07-14T00:00:00Z')"
            )
            connection.execute(
                """
                CREATE TABLE data_connectors(
                  connector_key TEXT PRIMARY KEY,
                  name TEXT NOT NULL,
                  connector_type TEXT NOT NULL,
                  provider TEXT NOT NULL,
                  status TEXT NOT NULL,
                  config_json TEXT NOT NULL,
                  schedule_json TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  last_sync_at TEXT,
                  last_sync_status TEXT,
                  last_sync_result_json TEXT
                )
                """
            )
            connection.execute(
                """
                INSERT INTO data_connectors(
                  connector_key, name, connector_type, provider, status,
                  config_json, schedule_json, created_at, updated_at
                ) VALUES('legacy-file', 'Legacy file connector', 'file', 'local', 'ready', '{}', '{}', '2026-07-14T00:00:00Z', '2026-07-14T00:00:00Z')
                """
            )
        connection.execute(f"PRAGMA user_version = {version}")


def create_duckdb(path: Path, version: int) -> None:
    import duckdb  # type: ignore

    path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(path)) as connection:
        connection.execute("CREATE TABLE legacy_aibi_c_rows(product VARCHAR, value VARCHAR)")
        connection.execute("INSERT INTO legacy_aibi_c_rows VALUES ('AIBI-C', 'preserve-me')")
        if version > 0:
            connection.execute(
                'CREATE TABLE "__aibi_schema_metadata" (key VARCHAR PRIMARY KEY, value VARCHAR NOT NULL)'
            )
            connection.execute(
                'INSERT INTO "__aibi_schema_metadata" VALUES (?, ?)',
                ["schema_version", str(version)],
            )


def inspect_fixture(sqlite_path: Path, duckdb_path: Path) -> dict[str, object]:
    import duckdb  # type: ignore

    with sqlite3.connect(sqlite_path) as connection:
        sqlite_row = connection.execute("SELECT product, value FROM legacy_aibi_c_receipt").fetchone()
        sqlite_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        connector_exists = connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name = 'data_connectors'"
        ).fetchone()[0]
        connector_row = connection.execute(
            "SELECT workspace_id, connector_key, name FROM data_connectors"
        ).fetchone() if connector_exists and "workspace_id" in {
            row[1] for row in connection.execute("PRAGMA table_info(data_connectors)").fetchall()
        } else None
        connector_pk = [
            row[1]
            for row in sorted(
                connection.execute("PRAGMA table_info(data_connectors)").fetchall(),
                key=lambda row: row[5],
            )
            if row[5] > 0
        ] if connector_exists else []
        semantic_review_tables = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN ('knowledge_sources', 'semantic_patch_proposals') ORDER BY name"
            ).fetchall()
        ]
        semantic_review_indexes = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND name LIKE 'idx_semantic_patch_%' ORDER BY name"
            ).fetchall()
        ]
        plan_memory_tables = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN ('confirmed_plan_memories', 'recall_receipts') ORDER BY name"
            ).fetchall()
        ]
        plan_memory_indexes = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND (name LIKE 'idx_confirmed_plan_%' OR name LIKE 'idx_recall_receipts_%') ORDER BY name"
            ).fetchall()
        ]
        plan_quality_tables = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'plan_quality_scorecards' ORDER BY name"
            ).fetchall()
        ]
        plan_quality_indexes = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index' AND name LIKE 'idx_plan_quality_%' ORDER BY name"
            ).fetchall()
        ]
    with duckdb.connect(str(duckdb_path), read_only=True) as connection:
        duckdb_row = connection.execute("SELECT product, value FROM legacy_aibi_c_rows").fetchone()
        metadata = connection.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '__aibi_schema_metadata'"
        ).fetchone()[0]
        duckdb_version = int(connection.execute(
            'SELECT value FROM "__aibi_schema_metadata" WHERE key = ?', ["schema_version"]
        ).fetchone()[0]) if metadata else 0
    return {
        "sqliteRow": list(sqlite_row) if sqlite_row else None,
        "sqliteVersion": sqlite_version,
        "connectorRow": list(connector_row) if connector_row else None,
        "connectorPrimaryKey": connector_pk,
        "semanticReviewTables": semantic_review_tables,
        "semanticReviewIndexes": semantic_review_indexes,
        "planMemoryTables": plan_memory_tables,
        "planMemoryIndexes": plan_memory_indexes,
        "planQualityTables": plan_quality_tables,
        "planQualityIndexes": plan_quality_indexes,
        "duckdbRow": list(duckdb_row) if duckdb_row else None,
        "duckdbVersion": duckdb_version,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["legacy", "future", "inspect"])
    parser.add_argument("--sqlite", required=True)
    parser.add_argument("--duckdb", required=True)
    args = parser.parse_args()
    sqlite_path = Path(args.sqlite).resolve()
    duckdb_path = Path(args.duckdb).resolve()
    if args.command == "legacy":
        create_sqlite(sqlite_path, 1)
        create_duckdb(duckdb_path, 0)
        payload = inspect_fixture(sqlite_path, duckdb_path)
    elif args.command == "future":
        create_sqlite(sqlite_path, 99)
        create_duckdb(duckdb_path, 99)
        payload = inspect_fixture(sqlite_path, duckdb_path)
    else:
        payload = inspect_fixture(sqlite_path, duckdb_path)
    print(json.dumps({"ok": True, **payload}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
