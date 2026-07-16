from __future__ import annotations

import argparse
from pathlib import Path
import sqlite3
from typing import Any, Callable

from bi_cli_core import now_iso, quote_identifier, workspace_slug


WORKSPACE_SCOPED_TABLES = [
    "analysis_snapshots",
    "research_run_events",
    "research_observations",
    "research_plan_revisions",
    "research_runs",
    "exploration_board_items",
    "exploration_anchors",
    "exploration_threads",
    "plan_quality_scorecards",
    "agent_provider_evaluations",
    "workspace_agent_runtime_profiles",
    "agent_context_snapshots",
    "agent_sessions",
    "workspace_analytical_skills",
    "workspace_domain_packs",
    "semantic_patch_proposals",
    "knowledge_sources",
    "context_rules",
    "context_terms",
    "confirmed_queries",
    "confirmed_plan_memories",
    "recall_receipts",
    "agent_turn_events",
    "agent_turns",
    "analysis_job_events",
    "analysis_jobs",
    "analysis_runs",
    "analysis_units",
    "query_plan_receipts",
    "dashboard_widgets",
    "dashboards",
    "navigation_modules",
    "saved_views",
    "metric_definitions",
    "calculated_fields",
    "field_semantics",
    "relationships",
    "import_jobs",
    "import_policies",
    "data_connectors",
    "action_drafts",
    "source_intelligence_runs",
    "source_runs",
    "table_registry",
]


def get_system_flag(connection: sqlite3.Connection, key: str, default: str = "") -> str:
    row = connection.execute("SELECT value FROM system_flags WHERE key = ?", (key,)).fetchone()
    return str(row["value"]) if row else default


def set_system_flag(connection: sqlite3.Connection, key: str, value: str) -> None:
    connection.execute(
        """
        INSERT INTO system_flags(key, value, updated_at)
        VALUES(?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """,
        (key, value, now_iso()),
    )


def active_workspace_id(connection: sqlite3.Connection) -> str:
    workspace_id = get_system_flag(connection, "active_workspace_id", "default")
    if connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
        return workspace_id
    set_system_flag(connection, "active_workspace_id", "default")
    return "default"


def workspace_records(
    connection: sqlite3.Connection,
    *,
    rows_to_dicts: Callable[[Any], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    current = active_workspace_id(connection)
    rows = rows_to_dicts(connection.execute("SELECT * FROM workspaces ORDER BY created_at"))
    for row in rows:
        row["isActive"] = row["id"] == current
        enabled_rows = connection.execute(
            """
            SELECT pack_id, version
            FROM workspace_domain_packs
            WHERE workspace_id = ? AND enabled = 1
            ORDER BY pack_id
            """,
            (row["id"],),
        ).fetchall()
        row["enabledDomainPacks"] = [
            {"packId": item["pack_id"], "version": item["version"]}
            for item in enabled_rows
        ]
    return rows


def workspace_create_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
) -> dict[str, Any]:
    workspace_id = workspace_slug(args.name)
    proposed = {
        "id": workspace_id,
        "name": args.name,
        "current_source_run_id": None,
    }
    if not args.yes:
        return {
            "ok": True,
            "dryRun": True,
            "requiresConfirmation": True,
            "proposed": proposed,
        }
    with open_db() as connection:
        existing = connection.execute("SELECT id FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
        if existing:
            raise ValueError(f"Workspace already exists: {workspace_id}")
        connection.execute(
            """
            INSERT INTO workspaces(id, name, current_source_run_id, created_at)
            VALUES(?, ?, NULL, ?)
            """,
            (workspace_id, args.name, now_iso()),
        )
        set_system_flag(connection, "active_workspace_id", workspace_id)
        connection.commit()
    return {"ok": True, "confirmed": True, "created": {**proposed, "isActive": True}}


def workspace_select_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
) -> dict[str, Any]:
    with open_db() as connection:
        row = connection.execute("SELECT * FROM workspaces WHERE id = ?", (args.workspace,)).fetchone()
        if not row:
            raise ValueError(f"Unknown workspace: {args.workspace}")
        if not args.yes:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "currentWorkspaceId": active_workspace_id(connection),
                "proposed": dict(row),
            }
        set_system_flag(connection, "active_workspace_id", args.workspace)
        connection.commit()
        selected = dict(row)
        selected["isActive"] = True
    return {"ok": True, "confirmed": True, "workspace": selected}


def workspace_rename_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
) -> dict[str, Any]:
    workspace_id = str(args.workspace or "").strip()
    name = str(args.name or "").strip()
    if not workspace_id:
        raise ValueError("Workspace id is required.")
    if not name:
        raise ValueError("Workspace name is required.")
    with open_db() as connection:
        row = connection.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
        if not row:
            raise ValueError(f"Unknown workspace: {workspace_id}")
        current = dict(row)
        proposed = {**current, "name": name}
        if not args.yes:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "current": current,
                "proposed": proposed,
            }
        connection.execute("UPDATE workspaces SET name = ? WHERE id = ?", (name, workspace_id))
        connection.commit()
    return {"ok": True, "confirmed": True, "workspace": proposed}


def table_has_column(connection: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    return any(str(row["name"]) == column_name for row in connection.execute(f"PRAGMA table_info({quote_identifier(table_name)})"))


def workspace_delete_impact(connection: sqlite3.Connection, workspace_id: str) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for table_name in WORKSPACE_SCOPED_TABLES:
        if table_has_column(connection, table_name, "workspace_id"):
            counts[table_name] = int(connection.execute(
                f"SELECT COUNT(*) FROM {quote_identifier(table_name)} WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchone()[0])
    physical_tables = [
        str(row["physical_table"])
        for row in connection.execute(
            "SELECT physical_table FROM table_registry WHERE workspace_id = ? ORDER BY table_key",
            (workspace_id,),
        ).fetchall()
    ]
    return {
        "counts": counts,
        "physicalTables": physical_tables,
        "totalRows": sum(counts.values()),
    }


def drop_duckdb_tables(duckdb_path: Path | None, physical_tables: list[str]) -> list[str]:
    if not duckdb_path or not physical_tables:
        return []
    try:
        import duckdb  # type: ignore
    except Exception:
        return []
    dropped: list[str] = []
    if not duckdb_path.exists():
        return dropped
    with duckdb.connect(str(duckdb_path)) as duck_connection:
        for table_name in physical_tables:
            duck_connection.execute(f"DROP TABLE IF EXISTS {quote_identifier(table_name)}")
            dropped.append(table_name)
    return dropped


def workspace_delete_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    duckdb_path: Path | None = None,
) -> dict[str, Any]:
    workspace_id = str(args.workspace or "").strip()
    if not workspace_id:
        raise ValueError("Workspace id is required.")
    if workspace_id == "default":
        raise ValueError("Default workspace cannot be deleted.")
    with open_db() as connection:
        row = connection.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
        if not row:
            raise ValueError(f"Unknown workspace: {workspace_id}")
        current = active_workspace_id(connection)
        if workspace_id == current:
            raise ValueError("Cannot delete the active workspace; select another workspace first.")
        workspace = dict(row)
        impact = workspace_delete_impact(connection, workspace_id)
        if not args.yes:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "workspace": workspace,
                "impact": impact,
            }
        physical_tables = list(impact["physicalTables"])
        for physical_table in physical_tables:
            connection.execute(f"DROP TABLE IF EXISTS {quote_identifier(physical_table)}")
        deleted_counts: dict[str, int] = {}
        for table_name in WORKSPACE_SCOPED_TABLES:
            if table_has_column(connection, table_name, "workspace_id"):
                cursor = connection.execute(
                    f"DELETE FROM {quote_identifier(table_name)} WHERE workspace_id = ?",
                    (workspace_id,),
                )
                deleted_counts[table_name] = int(cursor.rowcount if cursor.rowcount is not None else 0)
        connection.execute("DELETE FROM workspaces WHERE id = ?", (workspace_id,))
        connection.commit()
    dropped_duckdb_tables = drop_duckdb_tables(duckdb_path, physical_tables)
    return {
        "ok": True,
        "confirmed": True,
        "deletedWorkspace": workspace,
        "deletedCounts": deleted_counts,
        "droppedPhysicalTables": physical_tables,
        "droppedDuckdbTables": dropped_duckdb_tables,
    }
