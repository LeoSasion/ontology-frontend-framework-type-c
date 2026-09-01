from __future__ import annotations

import argparse
import hashlib
import re
from contextlib import closing
from pathlib import Path
import sqlite3
from typing import Any, Callable

from bi_cli_core import now_iso, quote_identifier, workspace_slug
from dataset_version_store import (
    collect_unreferenced_dataset_objects,
    dataset_object_candidates,
    delete_dataset_versions,
)
from reviewed_publication_service import tombstone_reviewed_publication, verify_evidence_ledger
from workspace_recovery_service import (
    DUCKDB_ARTIFACT,
    WorkspaceRecoveryError,
    WorkspaceRecoveryService,
    _fingerprint,
    _read_recovery_operation,
    _request_key,
    _workspace_state,
    recovery_point_duckdb_catalogs,
)


WORKSPACE_DELETE_PLAN_SCHEMA = "aibi-workspace-delete-plan/v1"
WORKSPACE_DELETE_OPERATION = "workspace-delete"
WORKSPACE_DELETE_STAGES = {"prepared", "duckdb_deleted", "sqlite_deleted", "completed", "needs_attention"}
WORKSPACE_DELETE_TOMBSTONE_REASON = "workspace deleted by confirmed workspace lifecycle"


WORKSPACE_SCOPED_TABLES = [
    "workflow_recipe_events",
    "workflow_recipes",
    "metric_contract_events",
    "metric_contract_versions",
    "semantic_release_events",
    "semantic_releases",
    "decision_framework_events",
    "decision_frameworks",
    "retrieval_evaluation_runs",
    "evidence_retrieval_receipts",
    "evidence_ledger_entries",
    "reviewed_publications",
    "source_activation_journal_events",
    "source_activation_journals",
    "import_workspace_leases",
    "sqlserver_snapshot_receipts",
    "sqlserver_snapshot_plans",
    "sqlserver_snapshot_catalogs",
    "metric_monitor_evaluations",
    "metric_monitors",
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


def _workspace_delete_publication_ledgers(connection: sqlite3.Connection, workspace_id: str) -> list[dict[str, Any]]:
    if not table_has_column(connection, "reviewed_publications", "workspace_id"):
        return []
    rows = connection.execute(
        "SELECT publication_key, ledger_head_hash FROM reviewed_publications "
        "WHERE workspace_id = ? ORDER BY publication_key",
        (workspace_id,),
    ).fetchall()
    ledgers: list[dict[str, Any]] = []
    for row in rows:
        publication_key = str(row["publication_key"])
        verification = verify_evidence_ledger(
            connection,
            workspace_id=workspace_id,
            publication_key=publication_key,
        )
        ledgers.append({
            "publicationKey": publication_key,
            "ledgerHeadHash": str(row["ledger_head_hash"] or ""),
            "entryCount": int(verification.get("entryCount") or 0),
            "verified": bool(verification.get("ok")),
            "blockers": list(verification.get("blockers") or []),
        })
    return ledgers


def _workspace_delete_plan_material(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": WORKSPACE_DELETE_PLAN_SCHEMA,
        "workspaceId": plan.get("workspaceId"),
        "workspace": plan.get("workspace"),
        "workspaceStateFingerprint": plan.get("workspaceStateFingerprint"),
        "impact": plan.get("impact"),
        "publicationLedgers": plan.get("publicationLedgers"),
        "requestKeyFingerprint": plan.get("requestKeyFingerprint"),
    }


def _validate_workspace_delete_plan(plan: dict[str, Any]) -> dict[str, Any]:
    if plan.get("schema") != WORKSPACE_DELETE_PLAN_SCHEMA:
        raise WorkspaceRecoveryError("WORKSPACE_DELETE_RECEIPT_INVALID", "Workspace delete plan schema is invalid.")
    request_fingerprint = str(plan.get("requestKeyFingerprint") or "")
    state_fingerprint = str(plan.get("workspaceStateFingerprint") or "")
    if not re.fullmatch(r"[a-f0-9]{64}", request_fingerprint) or not re.fullmatch(r"[a-f0-9]{64}", state_fingerprint):
        raise WorkspaceRecoveryError("WORKSPACE_DELETE_RECEIPT_INVALID", "Workspace delete plan fingerprints are invalid.")
    input_fingerprint = _fingerprint(_workspace_delete_plan_material(plan))
    expected_plan = _fingerprint({"schema": WORKSPACE_DELETE_PLAN_SCHEMA, "inputFingerprint": input_fingerprint})
    if input_fingerprint != str(plan.get("inputFingerprint") or "") or expected_plan != str(plan.get("planFingerprint") or ""):
        raise WorkspaceRecoveryError("WORKSPACE_DELETE_RECEIPT_INVALID", "Workspace delete plan content fingerprint is invalid.")
    return plan


def build_workspace_delete_plan(
    connection: sqlite3.Connection,
    workspace_id: str,
    request_key: str,
    *,
    duckdb_path: Path,
) -> dict[str, Any]:
    row = connection.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
    if not row:
        raise ValueError(f"Unknown workspace: {workspace_id}")
    workspace = dict(row)
    impact = workspace_delete_impact(connection, workspace_id)
    publication_ledgers = _workspace_delete_publication_ledgers(connection, workspace_id)
    plan: dict[str, Any] = {
        "schema": WORKSPACE_DELETE_PLAN_SCHEMA,
        "status": "waiting-confirmation",
        "workspaceId": workspace_id,
        "workspace": workspace,
        "workspaceStateFingerprint": _workspace_state(connection, workspace_id, duckdb_path)["fingerprint"],
        "impact": impact,
        "publicationLedgers": publication_ledgers,
        "requestKeyFingerprint": hashlib.sha256(request_key.encode("utf-8")).hexdigest(),
    }
    plan["inputFingerprint"] = _fingerprint(_workspace_delete_plan_material(plan))
    plan["planFingerprint"] = _fingerprint({
        "schema": WORKSPACE_DELETE_PLAN_SCHEMA,
        "inputFingerprint": plan["inputFingerprint"],
    })
    return plan


def _workspace_delete_result(plan: dict[str, Any], *, stage: str) -> dict[str, Any]:
    return {
        "ok": True,
        "confirmed": True,
        "changed": stage != "completed",
        "workspaceId": plan["workspaceId"],
        "deletedWorkspace": plan["workspace"],
        "impact": plan["impact"],
        "publicationLedgers": plan["publicationLedgers"],
        "deletePlan": plan,
        "lifecycleStatus": stage,
        "invalidationKeys": ["workspace-status", "workbench", "dashboards", "workspace-recovery"],
    }


def _persist_workspace_delete_receipt(
    service: WorkspaceRecoveryService,
    *,
    workspace_id: str,
    request_key: str | None,
    request_key_fingerprint: str,
    intent_fingerprint: str,
    status: str,
    result: dict[str, Any],
    receipt_path: Path | None = None,
) -> None:
    if status not in WORKSPACE_DELETE_STAGES:
        raise WorkspaceRecoveryError("WORKSPACE_DELETE_STAGE_INVALID", "Workspace delete lifecycle stage is invalid.")
    result["lifecycleStatus"] = status
    if request_key is not None:
        service._write_operation(workspace_id, WORKSPACE_DELETE_OPERATION, request_key, intent_fingerprint, status, result)
        return
    if receipt_path is None:
        raise WorkspaceRecoveryError("WORKSPACE_DELETE_RECEIPT_INVALID", "Workspace delete receipt path is missing.")
    service._write_operation_at(
        receipt_path,
        workspace_id=workspace_id,
        operation=WORKSPACE_DELETE_OPERATION,
        request_key_fingerprint=request_key_fingerprint,
        intent_fingerprint=intent_fingerprint,
        status=status,
        result=result,
    )


def _assert_workspace_delete_snapshot_matches_current(
    service: WorkspaceRecoveryService,
    workspace_id: str,
    recovery_point_key: str,
    expected_state_fingerprint: str,
) -> None:
    snapshot_duckdb = service._point_directory(workspace_id, recovery_point_key, must_exist=True) / DUCKDB_ARTIFACT
    with closing(service.open_db()) as connection:
        connection.row_factory = sqlite3.Row
        if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
            return
        current = _workspace_state(connection, workspace_id, snapshot_duckdb)
    if str(current.get("fingerprint") or "") != expected_state_fingerprint:
        raise WorkspaceRecoveryError(
            "WORKSPACE_DELETE_STATE_DRIFT",
            "Workspace changed after its audited delete recovery point was created.",
            "Run workspace-recovery-reconcile and inspect the delete receipt before retrying.",
        )


def _verify_duckdb_tables_deleted(duckdb_path: Path, physical_tables: list[str]) -> None:
    if not physical_tables:
        return
    if not duckdb_path.is_file():
        raise WorkspaceRecoveryError(
            "WORKSPACE_DELETE_DUCKDB_UNAVAILABLE",
            "DuckDB catalogue is unavailable; workspace deletion stopped before metadata removal.",
        )
    try:
        import duckdb  # type: ignore
    except Exception as error:
        raise WorkspaceRecoveryError("WORKSPACE_DELETE_DUCKDB_UNAVAILABLE", "DuckDB deletion could not be verified.") from error
    with duckdb.connect(str(duckdb_path), read_only=True) as connection:
        for table_name in physical_tables:
            relation = connection.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_schema = current_schema() AND table_name = ?",
                [table_name],
            ).fetchone()
            manifest = connection.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_schema = current_schema() "
                "AND table_name = '__aibi_replica_manifest'",
            ).fetchone()
            manifest_row = connection.execute(
                "SELECT 1 FROM __aibi_replica_manifest WHERE logical_table = ?",
                [table_name],
            ).fetchone() if manifest else None
            if relation or manifest_row:
                raise WorkspaceRecoveryError(
                    "WORKSPACE_DELETE_DUCKDB_INCOMPLETE",
                    "DuckDB workspace dataset views were not fully deleted.",
                    "Run workspace-recovery-reconcile before continuing.",
                )


def _tombstone_workspace_publications(
    connection: sqlite3.Connection,
    workspace_id: str,
) -> tuple[int, list[dict[str, Any]]]:
    ledgers = _workspace_delete_publication_ledgers(connection, workspace_id)
    damaged = [item for item in ledgers if not item["verified"]]
    if damaged:
        raise WorkspaceRecoveryError(
            "WORKSPACE_DELETE_LEDGER_INTEGRITY_FAILED",
            "Workspace deletion is blocked because an evidence ledger is damaged.",
            "Repair or export the evidence ledger before deleting the workspace.",
        )
    tombstoned = 0
    for item in ledgers:
        result = tombstone_reviewed_publication(
            connection,
            workspace_id=workspace_id,
            publication_key=str(item["publicationKey"]),
            expected_head_hash=str(item["ledgerHeadHash"]),
            reason=WORKSPACE_DELETE_TOMBSTONE_REASON,
            now_iso=now_iso,
        )
        tombstoned += int(bool(result.get("tombstoned")))
    return tombstoned, _workspace_delete_publication_ledgers(connection, workspace_id)


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
        manifest_exists = bool(duck_connection.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema = current_schema() AND table_name = '__aibi_replica_manifest'"
        ).fetchone())
        duck_connection.execute("BEGIN TRANSACTION")
        try:
            for table_name in physical_tables:
                relation = duck_connection.execute(
                    "SELECT table_type FROM information_schema.tables WHERE table_schema = current_schema() AND table_name = ?",
                    [table_name],
                ).fetchone()
                if relation and str(relation[0]) == "VIEW":
                    duck_connection.execute(f"DROP VIEW {quote_identifier(table_name)}")
                    dropped.append(table_name)
                elif relation:
                    raise WorkspaceRecoveryError(
                        "WORKSPACE_DELETE_DUCKDB_RELATION_INVALID",
                        "Dataset v2 logical relations must be DuckDB views.",
                    )
                if manifest_exists:
                    duck_connection.execute(
                        "DELETE FROM __aibi_replica_manifest WHERE logical_table = ?",
                        [table_name],
                    )
            duck_connection.execute("COMMIT")
        except Exception:
            duck_connection.execute("ROLLBACK")
            raise
    return list(dict.fromkeys(dropped))


def _delete_workspace_sqlite(
    service: WorkspaceRecoveryService,
    workspace_id: str,
) -> dict[str, int]:
    with closing(service.open_db()) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("BEGIN IMMEDIATE")
        try:
            if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
                connection.rollback()
                return {}
            deleted_counts = delete_dataset_versions(connection, workspace_id=workspace_id)
            for table_name in WORKSPACE_SCOPED_TABLES:
                if table_has_column(connection, table_name, "workspace_id"):
                    cursor = connection.execute(
                        f"DELETE FROM {quote_identifier(table_name)} WHERE workspace_id = ?",
                        (workspace_id,),
                    )
                    deleted_counts[table_name] = int(cursor.rowcount if cursor.rowcount is not None else 0)
            connection.execute("DELETE FROM workspaces WHERE id = ?", (workspace_id,))
            connection.commit()
            return deleted_counts
        except Exception:
            connection.rollback()
            raise


def _advance_workspace_delete(
    service: WorkspaceRecoveryService,
    receipt: dict[str, Any],
    *,
    request_key: str | None = None,
    receipt_path: Path | None = None,
    fail_at: str = "",
) -> dict[str, Any]:
    if receipt.get("schema") != "aibi-workspace-recovery-operation/v1" or receipt.get("operation") != WORKSPACE_DELETE_OPERATION:
        raise WorkspaceRecoveryError("WORKSPACE_DELETE_RECEIPT_INVALID", "Workspace delete receipt failed validation.")
    status = str(receipt.get("status") or "")
    result = dict(receipt.get("result") or {}) if isinstance(receipt.get("result"), dict) else {}
    plan = _validate_workspace_delete_plan(dict(result.get("deletePlan") or {}))
    workspace_id = str(plan["workspaceId"])
    request_key_fingerprint = str(receipt.get("requestKeyFingerprint") or "")
    intent_fingerprint = str(receipt.get("intentFingerprint") or "")
    if (
        not re.fullmatch(r"[a-f0-9]{64}", request_key_fingerprint)
        or request_key_fingerprint != str(plan.get("requestKeyFingerprint") or "")
        or intent_fingerprint != str(plan.get("inputFingerprint") or "")
    ):
        raise WorkspaceRecoveryError("WORKSPACE_DELETE_RECEIPT_INVALID", "Workspace delete receipt fingerprints are invalid.")
    if status == "completed":
        return {**result, "changed": False, "idempotentReplay": True}
    resumed_from_attention = False
    if status == "needs_attention":
        resume_from_status = str(result.get("resumeFromStatus") or "")
        if not resume_from_status and isinstance(result.get("deletedCounts"), dict):
            # v1 receipts written before resumeFromStatus existed still carry
            # the durable SQLite deletion result.  The state is reverified
            # below before final object garbage collection can continue.
            resume_from_status = "sqlite_deleted"
        if resume_from_status != "sqlite_deleted":
            raise WorkspaceRecoveryError(
                "WORKSPACE_DELETE_NEEDS_ATTENTION",
                "Workspace deletion requires operator attention before it can continue.",
                "Inspect the recovery point and delete receipt before retrying reconciliation.",
            )
        status = resume_from_status
        resumed_from_attention = True
    if status not in {"prepared", "duckdb_deleted", "sqlite_deleted"}:
        raise WorkspaceRecoveryError("WORKSPACE_DELETE_RECEIPT_INVALID", "Workspace delete receipt stage is invalid.")

    physical_tables = [str(item) for item in plan.get("impact", {}).get("physicalTables", [])]
    workspace_exists = False
    with closing(service.open_db()) as connection:
        connection.row_factory = sqlite3.Row
        workspace_exists = bool(connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone())
    if resumed_from_attention:
        if workspace_exists:
            raise WorkspaceRecoveryError(
                "WORKSPACE_DELETE_RESUME_STATE_INVALID",
                "Workspace delete receipt cannot resume after metadata reappeared.",
                "Inspect the recovery point and delete receipt before retrying reconciliation.",
            )
        _verify_duckdb_tables_deleted(service.duckdb_path, physical_tables)

    if status == "prepared" and workspace_exists:
        with closing(service.open_db()) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            try:
                tombstoned_count, current_ledgers = _tombstone_workspace_publications(connection, workspace_id)
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        result["tombstonedPublicationCount"] = int(result.get("tombstonedPublicationCount") or 0) + tombstoned_count
        result["tombstonedPublicationLedgers"] = current_ledgers
        _persist_workspace_delete_receipt(
            service,
            workspace_id=workspace_id,
            request_key=request_key,
            request_key_fingerprint=request_key_fingerprint,
            intent_fingerprint=intent_fingerprint,
            status="prepared",
            result=result,
            receipt_path=receipt_path,
        )
        if fail_at == "after_tombstones":
            raise RuntimeError("Injected workspace delete interruption after publication tombstones")

        safety_request_key = f"workspace-delete-safety:{request_key_fingerprint}"
        reason = f"workspace-delete-audit:{request_key_fingerprint[:24]}"
        safety_preview = service.preview_create(workspace_id, reason, safety_request_key)
        safety = service.create(
            workspace_id,
            reason,
            safety_request_key,
            confirm=True,
            expected_plan_fingerprint=str(safety_preview["recoveryPlan"]["planFingerprint"]),
        )
        recovery_point = dict(safety.get("recoveryPoint") or {})
        recovery_point_key = str(recovery_point.get("recoveryPointKey") or "")
        inspected = service.inspect(workspace_id, recovery_point_key, verify=True)
        if inspected.get("verified") is not True:
            raise WorkspaceRecoveryError("WORKSPACE_DELETE_SAFETY_POINT_INVALID", "Workspace delete safety recovery point is not verified.")
        result["auditRecoveryPoint"] = inspected["recoveryPoint"]
        _assert_workspace_delete_snapshot_matches_current(
            service,
            workspace_id,
            recovery_point_key,
            str(recovery_point.get("workspaceStateFingerprint") or ""),
        )
        with closing(service.open_db()) as connection:
            connection.row_factory = sqlite3.Row
            result["datasetObjectCandidates"] = dataset_object_candidates(
                connection,
                workspace_id=workspace_id,
            )
        _persist_workspace_delete_receipt(
            service,
            workspace_id=workspace_id,
            request_key=request_key,
            request_key_fingerprint=request_key_fingerprint,
            intent_fingerprint=intent_fingerprint,
            status="prepared",
            result=result,
            receipt_path=receipt_path,
        )
        if fail_at == "after_recovery_point":
            raise RuntimeError("Injected workspace delete interruption after safety recovery point")

    if status == "prepared":
        recovery_point = result.get("auditRecoveryPoint") if isinstance(result.get("auditRecoveryPoint"), dict) else {}
        recovery_point_key = str(recovery_point.get("recoveryPointKey") or "")
        if not recovery_point_key:
            raise WorkspaceRecoveryError("WORKSPACE_DELETE_SAFETY_POINT_MISSING", "Workspace delete safety recovery point is missing.")
        if recovery_point_key:
            service.inspect(workspace_id, recovery_point_key, verify=True)
        dropped = drop_duckdb_tables(service.duckdb_path, physical_tables)
        _verify_duckdb_tables_deleted(service.duckdb_path, physical_tables)
        result["droppedDuckdbTables"] = dropped
        _persist_workspace_delete_receipt(
            service,
            workspace_id=workspace_id,
            request_key=request_key,
            request_key_fingerprint=request_key_fingerprint,
            intent_fingerprint=intent_fingerprint,
            status="duckdb_deleted",
            result=result,
            receipt_path=receipt_path,
        )
        status = "duckdb_deleted"
        if fail_at == "after_duckdb_deleted":
            raise RuntimeError("Injected workspace delete interruption after DuckDB deletion")

    if status == "duckdb_deleted":
        _verify_duckdb_tables_deleted(service.duckdb_path, physical_tables)
        deleted_counts = _delete_workspace_sqlite(service, workspace_id)
        result["deletedCounts"] = deleted_counts
        _persist_workspace_delete_receipt(
            service,
            workspace_id=workspace_id,
            request_key=request_key,
            request_key_fingerprint=request_key_fingerprint,
            intent_fingerprint=intent_fingerprint,
            status="sqlite_deleted",
            result=result,
            receipt_path=receipt_path,
        )
        status = "sqlite_deleted"
        if fail_at == "after_sqlite_deleted":
            raise RuntimeError("Injected workspace delete interruption after SQLite deletion")

    if status == "sqlite_deleted":
        _verify_duckdb_tables_deleted(service.duckdb_path, physical_tables)
        with closing(service.open_db()) as connection:
            if connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
                raise WorkspaceRecoveryError("WORKSPACE_DELETE_SQLITE_INCOMPLETE", "Workspace metadata deletion is incomplete.")
            protected_catalogs = [
                service.duckdb_path,
                *recovery_point_duckdb_catalogs(service.recovery_root, workspace_id=workspace_id),
            ]
            result["datasetObjectGc"] = collect_unreferenced_dataset_objects(
                connection,
                candidates=[
                    dict(item)
                    for item in result.get("datasetObjectCandidates") or []
                    if isinstance(item, dict)
                ],
                duckdb_paths=protected_catalogs,
            )
        result["ok"] = True
        result["confirmed"] = True
        result["changed"] = True
        if resumed_from_attention:
            result["recoveredFromNeedsAttention"] = True
        result.pop("errorCode", None)
        result.pop("recoveryAction", None)
        result.pop("resumeFromStatus", None)
        _persist_workspace_delete_receipt(
            service,
            workspace_id=workspace_id,
            request_key=request_key,
            request_key_fingerprint=request_key_fingerprint,
            intent_fingerprint=intent_fingerprint,
            status="completed",
            result=result,
            receipt_path=receipt_path,
        )
    return result


def reconcile_workspace_delete_receipt(
    service: WorkspaceRecoveryService,
    receipt_path: Path,
) -> dict[str, Any]:
    receipt = _read_recovery_operation(receipt_path)
    return _advance_workspace_delete(service, receipt, receipt_path=receipt_path)


def mark_workspace_delete_needs_attention(
    service: WorkspaceRecoveryService,
    receipt_path: Path,
    error: Exception,
) -> dict[str, Any]:
    receipt = _read_recovery_operation(receipt_path)
    result = dict(receipt.get("result") or {}) if isinstance(receipt.get("result"), dict) else {}
    plan = _validate_workspace_delete_plan(dict(result.get("deletePlan") or {}))
    durable_status = str(receipt.get("status") or "")
    if durable_status in {"prepared", "duckdb_deleted", "sqlite_deleted"}:
        result["resumeFromStatus"] = durable_status
    elif durable_status == "needs_attention" and not result.get("resumeFromStatus") and isinstance(result.get("deletedCounts"), dict):
        result["resumeFromStatus"] = "sqlite_deleted"
    result["recoveryAction"] = "workspace-recovery-reconcile"
    result["errorCode"] = getattr(error, "code", "WORKSPACE_DELETE_RECONCILE_FAILED")
    _persist_workspace_delete_receipt(
        service,
        workspace_id=str(plan["workspaceId"]),
        request_key=None,
        request_key_fingerprint=str(receipt.get("requestKeyFingerprint") or ""),
        intent_fingerprint=str(receipt.get("intentFingerprint") or ""),
        status="needs_attention",
        result=result,
        receipt_path=receipt_path,
    )
    return result


def workspace_delete_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    sqlite_path: Path,
    duckdb_path: Path,
    recovery_root: Path,
) -> dict[str, Any]:
    workspace_id = str(args.workspace or "").strip()
    if not workspace_id:
        raise ValueError("Workspace id is required.")
    if workspace_id == "default":
        raise ValueError("Default workspace cannot be deleted.")
    request_key = str(getattr(args, "request_key", "") or "").strip()
    if request_key:
        request_key = _request_key(request_key)
    expected_plan = str(getattr(args, "expected_plan", "") or "").strip()
    if bool(getattr(args, "yes", False)) and (not request_key or not expected_plan):
        raise WorkspaceRecoveryError(
            "WORKSPACE_DELETE_CONFIRMATION_REQUIRED",
            "Confirmed workspace deletion requires both the preview requestKey and exact plan fingerprint.",
            "Preview workspace deletion with a stable requestKey, then confirm with that requestKey and plan fingerprint.",
        )
    service = WorkspaceRecoveryService(
        open_db=open_db,
        sqlite_path=sqlite_path,
        duckdb_path=duckdb_path,
        recovery_root=recovery_root,
    )

    if request_key:
        existing_receipt = service._operation_receipt(workspace_id, WORKSPACE_DELETE_OPERATION, request_key)
        if existing_receipt is not None:
            result = dict(existing_receipt.get("result") or {}) if isinstance(existing_receipt.get("result"), dict) else {}
            plan = _validate_workspace_delete_plan(dict(result.get("deletePlan") or {}))
            if expected_plan != str(plan["planFingerprint"]):
                raise WorkspaceRecoveryError(
                    "WORKSPACE_DELETE_REQUEST_KEY_CONFLICT",
                    "requestKey was already used with a different workspace delete plan.",
                    "Use the exact preview plan or generate a new requestKey.",
                )
            return _advance_workspace_delete(
                service,
                existing_receipt,
                request_key=request_key,
                fail_at=str(getattr(args, "fail_at", "") or ""),
            )

    with closing(open_db()) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
        if not row:
            raise ValueError(f"Unknown workspace: {workspace_id}")
        current = active_workspace_id(connection)
        if workspace_id == current:
            raise ValueError("Cannot delete the active workspace; select another workspace first.")
        if not request_key:
            initial_state = _workspace_state(connection, workspace_id, duckdb_path)["fingerprint"]
            request_key = f"legacy-workspace-delete:{workspace_id}:{initial_state[:24]}"
        plan = build_workspace_delete_plan(connection, workspace_id, request_key, duckdb_path=duckdb_path)
        if not args.yes:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "workspace": plan["workspace"],
                "impact": plan["impact"],
                "publicationLedgers": plan["publicationLedgers"],
                "deletePlan": plan,
            }
    if expected_plan != str(plan["planFingerprint"]):
        raise WorkspaceRecoveryError(
            "WORKSPACE_DELETE_PLAN_STALE",
            "Confirmation requires the exact fingerprint from the latest workspace delete preview.",
            "Preview workspace deletion again before confirming.",
        )
    result = _workspace_delete_result(plan, stage="prepared")
    service._write_operation(
        workspace_id,
        WORKSPACE_DELETE_OPERATION,
        request_key,
        str(plan["inputFingerprint"]),
        "prepared",
        result,
    )
    if str(getattr(args, "fail_at", "") or "") == "after_prepared":
        raise RuntimeError("Injected workspace delete interruption after prepared receipt")
    receipt = service._operation_receipt(workspace_id, WORKSPACE_DELETE_OPERATION, request_key)
    if receipt is None:
        raise WorkspaceRecoveryError("WORKSPACE_DELETE_RECEIPT_INVALID", "Workspace delete prepared receipt is missing.")
    return _advance_workspace_delete(
        service,
        receipt,
        request_key=request_key,
        fail_at=str(getattr(args, "fail_at", "") or ""),
    )
