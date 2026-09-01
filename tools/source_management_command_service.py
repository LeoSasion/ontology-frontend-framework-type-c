from __future__ import annotations

import argparse
import json
import sqlite3
from typing import Any, Callable

from bi_cli_core import DUCKDB_PATH, ROOT, now_iso, source_label
from dataset_version_store import (
    canonical_fingerprint,
    collect_unreferenced_dataset_objects,
    dataset_object_candidates,
    delete_dataset_versions,
)
from source_activation_journal_service import (
    PHASE_COMMIT_STARTED,
    PHASE_FINALIZED,
    PHASE_REPLICA_PUBLISHED,
    PHASE_SOURCE_SELECTION_COMMITTED,
    capture_replica_manifest,
    activation_for_job,
    prepare_activation,
    reconcile_activation,
    replica_manifest_matches,
    restore_replica_manifest,
    transition_activation,
)
from workspace_recovery_service import configured_recovery_root, recovery_point_duckdb_catalogs


def _reconcile_interrupted_source_delete(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    job_key: str,
) -> dict[str, Any] | None:
    """Return the data plane to one journaled state before surfacing a delete failure."""

    connection.rollback()
    current = activation_for_job(connection, workspace_id=workspace_id, job_key=job_key)
    if current is None:
        return None
    outcome = reconcile_activation(
        connection,
        journal=current,
        duckdb_path=DUCKDB_PATH,
        now_iso=now_iso,
    )
    connection.commit()
    return outcome


def rename_source_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    resolve_table_registry: Callable[[sqlite3.Connection, str], sqlite3.Row],
) -> dict[str, Any]:
    next_name = str(args.name or "").strip()
    if not next_name:
        raise ValueError("New source name is required.")
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        registry = resolve_table_registry(connection, args.source)
        duplicate = connection.execute(
            """
            SELECT table_key, display_name
            FROM table_registry
            WHERE display_name = ? AND table_key <> ? AND workspace_id = ?
            """,
            (next_name, registry["table_key"], workspace_id),
        ).fetchone()
        if duplicate:
            raise ValueError(f"Source name already exists: {next_name}")
        proposed = {
            "tableKey": registry["table_key"],
            "oldName": registry["display_name"],
            "name": next_name,
        }
        if not args.yes:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "proposed": proposed}
        connection.execute(
            "UPDATE table_registry SET display_name = ? WHERE table_key = ? AND workspace_id = ?",
            (next_name, registry["table_key"], workspace_id),
        )
        connection.execute(
            "UPDATE source_runs SET name = ? WHERE table_key = ? AND workspace_id = ?",
            (next_name, registry["table_key"], workspace_id),
        )
        connection.execute(
            """
            UPDATE navigation_modules
            SET name = ?, updated_at = ?
            WHERE module_type = 'table' AND table_key = ? AND workspace_id = ?
            """,
            (next_name, now_iso(), registry["table_key"], workspace_id),
        )
        connection.commit()
    return {"ok": True, "confirmed": True, "renamedSource": proposed}


def remaining_table_key_after_delete(
    connection: sqlite3.Connection,
    deleted_table_key: str,
    *,
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> str:
    workspace_id = active_workspace_id(connection)
    row = connection.execute(
        """
        SELECT table_key
        FROM table_registry
        WHERE table_key <> ? AND workspace_id = ?
        ORDER BY row_count DESC, display_name
        LIMIT 1
        """,
        (deleted_table_key, workspace_id),
    ).fetchone()
    return row["table_key"] if row else ""


def build_delete_source_plan(
    connection: sqlite3.Connection,
    registry: sqlite3.Row,
    *,
    active_workspace_id: Callable[[sqlite3.Connection], str],
    rows_to_dicts: Callable[[Any], list[dict[str, Any]]],
    load_connectors: Callable[[sqlite3.Connection], list[dict[str, Any]]],
    remaining_table_key_after_delete: Callable[[sqlite3.Connection, str], str],
) -> dict[str, Any]:
    workspace_id = active_workspace_id(connection)
    table_key = registry["table_key"]
    relation_keys = [
        row["relation_key"]
        for row in connection.execute(
            "SELECT relation_key FROM relationships WHERE workspace_id = ? AND (left_table_key = ? OR right_table_key = ?)",
            (workspace_id, table_key, table_key),
        )
    ]
    relation_like_clauses = " OR ".join("config_json LIKE ?" for _ in relation_keys)
    relation_like_params = [f"%{relation_key}%" for relation_key in relation_keys]
    widget_where = "table_key = ?"
    widget_params: list[Any] = [table_key]
    if relation_like_clauses:
        widget_where = f"({widget_where} OR {relation_like_clauses})"
        widget_params.extend(relation_like_params)
    affected_widgets = rows_to_dicts(
        connection.execute(
            f"""
            SELECT w.widget_key, w.dashboard_key, w.widget_type, w.title, w.table_key
            FROM dashboard_widgets w
            JOIN dashboards d ON d.dashboard_key = w.dashboard_key AND d.workspace_id = w.workspace_id
            WHERE d.workspace_id = ? AND {widget_where.replace('config_json', 'w.config_json').replace('table_key', 'w.table_key')}
            ORDER BY w.dashboard_key, w.sort_order
            """,
            tuple([workspace_id, *widget_params]),
        )
    )
    affected_dashboards = rows_to_dicts(
        connection.execute(
            """
            SELECT dashboard_key, name, default_table_key
            FROM dashboards
            WHERE default_table_key = ? AND workspace_id = ?
            ORDER BY dashboard_key
            """,
            (table_key, workspace_id),
        )
    )
    connectors = [
        connector for connector in load_connectors(connection)
        if str(connector.get("config", {}).get("targetTableKey") or "") == table_key
    ]
    return {
        "source": {
            "tableKey": table_key,
            "name": registry["display_name"],
            "physicalTable": registry["physical_table"],
            "sourceFile": source_label(registry["source_file"]),
            "rows": registry["row_count"],
            "columns": registry["column_count"],
        },
        "impact": {
            "sourceRuns": connection.execute("SELECT COUNT(*) FROM source_runs WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id)).fetchone()[0],
            "fieldConfigs": connection.execute("SELECT COUNT(*) FROM field_semantics WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id)).fetchone()[0],
            "metrics": connection.execute("SELECT COUNT(*) FROM metric_definitions WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id)).fetchone()[0],
            "views": connection.execute("SELECT COUNT(*) FROM saved_views WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id)).fetchone()[0],
            "importPolicies": connection.execute("SELECT COUNT(*) FROM import_policies WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id)).fetchone()[0],
            "importJobs": connection.execute("SELECT COUNT(*) FROM import_jobs WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id)).fetchone()[0],
            "relationships": len(relation_keys),
            "dashboardWidgets": len(affected_widgets),
            "dashboardDefaults": len(affected_dashboards),
            "connectors": len(connectors),
        },
        "affectedWidgets": affected_widgets,
        "affectedDashboards": affected_dashboards,
        "affectedRelationshipKeys": relation_keys,
        "affectedConnectors": connectors,
        "nextDefaultTableKey": remaining_table_key_after_delete(connection, table_key),
    }


def delete_source_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    resolve_table_registry: Callable[[sqlite3.Connection, str], sqlite3.Row],
    build_delete_source_plan: Callable[[sqlite3.Connection, sqlite3.Row], dict[str, Any]],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        registry = resolve_table_registry(connection, args.source)
        table_key = str(registry["table_key"])
        physical_table = str(registry["physical_table"])
        plan = build_delete_source_plan(connection, registry)
        if not args.yes:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, **plan}
        workspace = connection.execute(
            "SELECT current_source_run_id FROM workspaces WHERE id = ?",
            (workspace_id,),
        ).fetchone()
        if not DUCKDB_PATH.is_file():
            raise RuntimeError("Dataset v2 DuckDB catalogue is unavailable; source deletion was not started.")
        parent_source_run_id = str(workspace["current_source_run_id"] or "") or None
        candidates = dataset_object_candidates(connection, workspace_id=workspace_id, table_keys=[table_key])
        protected_catalogs = [
            DUCKDB_PATH,
            *recovery_point_duckdb_catalogs(configured_recovery_root(ROOT), workspace_id=workspace_id),
        ]
        rollback_manifest = capture_replica_manifest(DUCKDB_PATH, [physical_table])
        expected_manifest = [{
            "logicalTable": physical_table,
            "present": False,
            "gcCandidates": candidates,
        }]
        delete_fingerprint = canonical_fingerprint({
            "workspaceId": workspace_id,
            "tableKey": table_key,
            "physicalTable": physical_table,
            "activeVersionId": str(registry["active_version_id"] or ""),
            "contentFingerprint": str(registry["content_fingerprint"] or ""),
        })
        journal = prepare_activation(
            connection,
            workspace_id=workspace_id,
            job_key=f"source-delete-v2:{delete_fingerprint[:24]}",
            plan_fingerprint=delete_fingerprint,
            parent_source_run_id=parent_source_run_id,
            table_keys=[table_key],
            expected_manifest=expected_manifest,
            rollback_manifest=rollback_manifest,
            now_iso=now_iso,
        )
        journal_job_key = str(journal["jobKey"])
        connection.commit()
        journal = transition_activation(
            connection,
            workspace_id=workspace_id,
            journal_key=str(journal["journalKey"]),
            phase=PHASE_COMMIT_STARTED,
            now_iso=now_iso,
        )
        connection.commit()
        try:
            restore_replica_manifest(DUCKDB_PATH, expected_manifest)
            if not replica_manifest_matches(DUCKDB_PATH, expected_manifest):
                raise RuntimeError("Dataset v2 catalogue deactivation could not be verified.")
            journal = transition_activation(
                connection,
                workspace_id=workspace_id,
                journal_key=str(journal["journalKey"]),
                phase=PHASE_REPLICA_PUBLISHED,
                expected_manifest=expected_manifest,
                now_iso=now_iso,
            )
            connection.commit()
            if str(getattr(args, "fail_at", "") or "") == "after_replica_published":
                raise RuntimeError("Injected source delete interruption after replica publication")
        except Exception:
            _reconcile_interrupted_source_delete(
                connection,
                workspace_id=workspace_id,
                job_key=journal_job_key,
            )
            raise
        connection.execute("BEGIN IMMEDIATE")
        try:
            version_deletes = delete_dataset_versions(connection, workspace_id=workspace_id, table_keys=[table_key])
            connection.execute("DELETE FROM table_registry WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id))
            connection.execute("DELETE FROM source_runs WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id))
            connection.execute("DELETE FROM field_semantics WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id))
            connection.execute("DELETE FROM metric_definitions WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id))
            connection.execute("DELETE FROM saved_views WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id))
            connection.execute("DELETE FROM import_policies WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id))
            connection.execute("DELETE FROM import_jobs WHERE table_key = ? AND workspace_id = ?", (table_key, workspace_id))
            connection.execute("DELETE FROM navigation_modules WHERE module_type = 'table' AND table_key = ? AND workspace_id = ?", (table_key, workspace_id))
            connection.execute("DELETE FROM relationships WHERE workspace_id = ? AND (left_table_key = ? OR right_table_key = ?)", (workspace_id, table_key, table_key))
            widget_keys = [item["widget_key"] for item in plan["affectedWidgets"]]
            for widget_key in widget_keys:
                connection.execute("DELETE FROM dashboard_widgets WHERE widget_key = ? AND workspace_id = ?", (widget_key, workspace_id))
            for dashboard in plan["affectedDashboards"]:
                layout_row = connection.execute(
                    "SELECT layout_json FROM dashboards WHERE dashboard_key = ? AND workspace_id = ?",
                    (dashboard["dashboard_key"], workspace_id),
                ).fetchone()
                layout = json.loads(layout_row["layout_json"]) if layout_row else {}
                if isinstance(layout, dict):
                    layout["globalFilters"] = []
                connection.execute(
                    """
                    UPDATE dashboards
                    SET default_table_key = ?, layout_json = ?, updated_at = ?
                    WHERE dashboard_key = ? AND workspace_id = ?
                    """,
                    (plan["nextDefaultTableKey"] or None, json.dumps(layout, ensure_ascii=False), now_iso(), dashboard["dashboard_key"], workspace_id),
                )
            for connector in plan["affectedConnectors"]:
                config = dict(connector["config"])
                config["targetTableKey"] = ""
                connection.execute(
                    """
                    UPDATE data_connectors
                    SET status = 'paused', config_json = ?, updated_at = ?
                    WHERE connector_key = ? AND workspace_id = ?
                    """,
                    (json.dumps(config, ensure_ascii=False), now_iso(), connector["connectorKey"], workspace_id),
                )
            replacement = plan["nextDefaultTableKey"] or None
            connection.execute(
                """
                UPDATE workspaces
                SET current_source_run_id = (
                SELECT id FROM source_runs
                  WHERE table_key = ?
                  ORDER BY created_at DESC
                  LIMIT 1
                )
                WHERE id = ?
                """,
                (replacement, workspace_id),
            )
            journal = transition_activation(
                connection,
                workspace_id=workspace_id,
                journal_key=str(journal["journalKey"]),
                phase=PHASE_SOURCE_SELECTION_COMMITTED,
                expected_manifest=expected_manifest,
                now_iso=now_iso,
            )
            connection.commit()
        except Exception:
            _reconcile_interrupted_source_delete(
                connection,
                workspace_id=workspace_id,
                job_key=journal_job_key,
            )
            raise
        try:
            gc_result = collect_unreferenced_dataset_objects(
                connection,
                candidates=candidates,
                duckdb_paths=protected_catalogs,
            )
            transition_activation(
                connection,
                workspace_id=workspace_id,
                journal_key=str(journal["journalKey"]),
                phase=PHASE_FINALIZED,
                outcome="committed",
                warning={"datasetObjectGc": gc_result},
                event_type="source_delete_committed",
                now_iso=now_iso,
            )
            connection.commit()
        except Exception:
            outcome = _reconcile_interrupted_source_delete(
                connection,
                workspace_id=workspace_id,
                job_key=journal_job_key,
            )
            if not outcome or outcome.get("committed") is not True:
                raise
            gc_result = dict(outcome.get("datasetObjectGc") or {})
    return {
        "ok": True,
        "confirmed": True,
        "deletedSource": table_key,
        "deletedDatasetVersions": version_deletes,
        "datasetObjectGc": gc_result,
        **plan,
    }
