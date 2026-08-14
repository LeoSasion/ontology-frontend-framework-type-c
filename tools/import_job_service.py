from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Callable

from atomic_import_plan_service import bind_single_import_plan
from job_runtime_service import (
    STATUS_CANCELED,
    STATUS_CANCEL_REQUESTED,
    STATUS_CREATED,
    STATUS_FAILED,
    STATUS_NEEDS_ATTENTION,
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_SUCCEEDED,
    TERMINAL_STATUSES,
    create_job,
    get_job,
    job_input,
    transition_job,
    update_job_progress,
)
from query_runtime import sync_table_to_duckdb
from import_stage_service import validate_import_stage_for_confirmation
from source_activation_journal_service import (
    PHASE_COMMIT_STARTED,
    PHASE_FINALIZED,
    PHASE_REPLICA_PUBLISHED,
    PHASE_SOURCE_SELECTION_COMMITTED,
    activation_for_job,
    assert_import_workspace,
    capture_replica_manifest,
    claim_import_workspace,
    cleanup_stale_replicas,
    ensure_activation_journal_schema,
    prepare_activation,
    reconcile_activation,
    release_import_workspace,
    revoke_import_workspace_leases,
    restore_replica_manifest,
    transition_activation,
    unfinished_activations,
)
from workspace_mutation_lock_service import workspace_mutation_lock
from workspace_recovery_service import unfinished_recovery_fences


JOB_KIND = "import"
IMPORT_JOB_SCHEMA = "aibi-import-job/v1"


def _workspace_id(
    connection: sqlite3.Connection,
    args: argparse.Namespace,
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> str:
    workspace_id = str(getattr(args, "workspace", "") or active_workspace_id(connection)).strip()
    if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
        raise ValueError(f"Unknown workspace: {workspace_id}")
    return workspace_id


def _reject_other_aibi_repo(path_value: str) -> Path:
    path = Path(path_value).resolve()
    parts = {part.casefold() for part in path.parts}
    forbidden = {"aibi-a", "aibi-b", "aibi-d", "aibi-e", "aibi项目杂交"}
    found = sorted(parts & forbidden)
    if found:
        raise ValueError(f"AIBI-C import job cannot reference another AIBI repository: {found[0]}")
    return path


def _safe_source_name(path: Path) -> str:
    return path.name or "local-source"


def _current_source_run_id(connection: sqlite3.Connection, workspace_id: str) -> str | None:
    row = connection.execute(
        "SELECT current_source_run_id FROM workspaces WHERE id = ?",
        (workspace_id,),
    ).fetchone()
    return (str(row["current_source_run_id"] or "") or None) if row else None


def _build_current_plan(
    connection: sqlite3.Connection,
    *,
    private_input: dict[str, Any],
    build_import_preview: Callable[..., dict[str, Any]],
    build_folder_import_plan: Callable[..., dict[str, Any]],
    read_table_file: Callable[..., Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    import_kind = str(private_input.get("importKind") or "single")
    path = _reject_other_aibi_repo(str(private_input.get("path") or ""))
    workspace_id = str(private_input.get("workspaceId") or "").strip()
    if not workspace_id or not connection.execute(
        "SELECT 1 FROM workspaces WHERE id = ?",
        (workspace_id,),
    ).fetchone():
        raise ValueError(f"Unknown workspace: {workspace_id or '<missing>'}")
    if import_kind == "single":
        preview = build_import_preview(
            connection,
            path,
            private_input.get("table") or None,
            private_input.get("uniqueFields") or None,
            private_input.get("conflictRule") or None,
            workspace_id=workspace_id,
            mode_value=private_input.get("mode") or None,
            stage_key=private_input.get("stageKey") or None,
        )
        plan = bind_single_import_plan(
            preview,
            path,
            current_source_run_id=_current_source_run_id(connection, workspace_id),
        )
        if str(plan.get("workspaceId") or "") != workspace_id:
            raise RuntimeError("Durable import plan escaped its frozen workspace.")
        return plan
    if import_kind != "folder":
        raise ValueError(f"Unsupported import job kind: {import_kind}")
    plan = build_folder_import_plan(
        connection,
        path,
        recursive=private_input.get("recursive") is not False,
        limit=int(private_input.get("limit") or 200),
        unique_fields_value=private_input.get("uniqueFields") or None,
        conflict_rule_value=private_input.get("conflictRule") or None,
        workspace_id=workspace_id,
        stage_bindings=private_input.get("stageBindings") if isinstance(private_input.get("stageBindings"), dict) else None,
        build_import_preview=build_import_preview,
        read_table_file=read_table_file,
        active_workspace_id=active_workspace_id,
    )
    if str(plan.get("workspaceId") or "") != workspace_id:
        raise RuntimeError("Durable folder import plan escaped its frozen workspace.")
    return plan


def _plan_table_keys(plan: dict[str, Any], import_kind: str) -> list[str]:
    if import_kind == "single":
        options = plan.get("commitOptions") if isinstance(plan.get("commitOptions"), dict) else {}
        value = str(options.get("table") or plan.get("suggestedTableKey") or "").strip()
        return [value] if value else []
    return sorted({
        str(item.get("tableKey") or "").strip()
        for item in plan.get("items") or []
        if isinstance(item, dict) and str(item.get("tableKey") or "").strip()
    })


def _validate_single_commit_binding(private_input: dict[str, Any], plan: dict[str, Any]) -> None:
    """Keep the eventual commit mode identical to the owner-confirmed preview."""
    if str(private_input.get("importKind") or "single") != "single":
        return
    options = plan.get("commitOptions") if isinstance(plan.get("commitOptions"), dict) else {}
    expected_mode = str(options.get("mode") or "")
    requested_mode = str(private_input.get("mode") or "")
    if expected_mode and requested_mode != expected_mode:
        raise ValueError(
            f"Import mode changed after preview; re-run preview-import for mode {requested_mode}."
        )


def _stage_bindings_from_args(args: argparse.Namespace) -> dict[str, str]:
    raw = getattr(args, "stage_bindings", "")
    if not raw:
        return {}
    if isinstance(raw, dict):
        candidate = raw
    else:
        try:
            candidate = json.loads(str(raw))
        except json.JSONDecodeError as error:
            raise ValueError("Import stage bindings must be a JSON object.") from error
    if not isinstance(candidate, dict):
        raise ValueError("Import stage bindings must be a JSON object.")
    bindings: dict[str, str] = {}
    for identity, stage_key in candidate.items():
        normalized_identity = str(identity or "").strip().replace("\\", "/")
        normalized_stage = str(stage_key or "").strip()
        if not normalized_identity or not normalized_stage.startswith("stage_"):
            raise ValueError("Import stage binding is invalid.")
        bindings[normalized_identity] = normalized_stage
    return bindings


def _public_job_input(
    *,
    import_kind: str,
    path: Path,
    plan: dict[str, Any],
    request_key: str,
) -> dict[str, Any]:
    table_keys = _plan_table_keys(plan, import_kind)
    schema_change = plan.get("schemaChange") if isinstance(plan.get("schemaChange"), dict) else None
    import_stage = plan.get("importStage") if isinstance(plan.get("importStage"), dict) else None
    return {
        "schema": IMPORT_JOB_SCHEMA,
        "workspaceId": str(plan.get("workspaceId") or ""),
        "importKind": import_kind,
        "sourceName": _safe_source_name(path),
        "fileCount": int(plan.get("fileCount") or (1 if import_kind == "single" else 0)),
        "tableCount": int(plan.get("tableCount") or len(table_keys)),
        "tableKeys": table_keys,
        "planFingerprint": str(plan.get("planFingerprint") or ""),
        "parentSourceRunId": plan.get("parentSourceRunId"),
        "schemaChange": ({
            "schema": schema_change.get("schema"),
            "targetTableKey": schema_change.get("targetTableKey"),
            "addedFieldCount": len(schema_change.get("addedFields") or []),
            "removedFieldCount": len(schema_change.get("removedFields") or []),
            "orderChanged": schema_change.get("orderChanged") is True,
            "confirmationRequired": schema_change.get("confirmationRequired") is True,
        } if schema_change else None),
        "importStage": ({
            "schema": import_stage.get("schema"),
            "stageKey": import_stage.get("stageKey"),
            "contentHash": import_stage.get("contentHash"),
            "contentFingerprint": import_stage.get("contentFingerprint"),
            "parserVersion": import_stage.get("parserVersion"),
            "rowCount": import_stage.get("rowCount"),
            "columnCount": import_stage.get("columnCount"),
            "expiresAt": import_stage.get("expiresAt"),
            "sealed": import_stage.get("sealed") is True,
        } if import_stage else None),
        "requestKeyFingerprint": hashlib.sha256(request_key.encode("utf-8")).hexdigest(),
    }


def import_job_create_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    build_import_preview: Callable[..., dict[str, Any]],
    build_folder_import_plan: Callable[..., dict[str, Any]],
    read_table_file: Callable[..., Any],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    import_kind = str(getattr(args, "import_kind", "") or "single").strip().lower()
    path = _reject_other_aibi_repo(str(getattr(args, "path", "") or ""))
    request_key = str(getattr(args, "request_key", "") or "").strip()
    if not request_key:
        raise ValueError("Import job requestKey is required.")
    expected_plan = str(getattr(args, "expected_plan", "") or "").strip()
    if not expected_plan:
        raise ValueError("Import job requires the fingerprint from the latest confirmed preview.")
    confirm_schema_change = bool(getattr(args, "confirm_schema_change", False))
    private_input = {
        "workspaceId": "",
        "importKind": import_kind,
        "path": str(path),
        "table": str(getattr(args, "table", "") or "") or None,
        "name": str(getattr(args, "name", "") or "") or None,
        "mode": str(getattr(args, "mode", "") or "create"),
        "uniqueFields": str(getattr(args, "unique_fields", "") or "") or None,
        "conflictRule": str(getattr(args, "conflict_rule", "") or "") or None,
        "recursive": not bool(getattr(args, "no_recursive", False)),
        "limit": max(1, min(int(getattr(args, "limit", 200) or 200), 200)),
        "expectedPlan": expected_plan,
        "stageKey": str(getattr(args, "stage_key", "") or "") or None,
        "stageBindings": _stage_bindings_from_args(args),
    }
    if confirm_schema_change:
        private_input["confirmSchemaChange"] = True
    with open_db() as connection:
        ensure_activation_journal_schema(connection)
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        private_input["workspaceId"] = workspace_id
        existing = connection.execute(
            """
            SELECT job_key FROM analysis_jobs
            WHERE workspace_id = ? AND kind = ? AND request_key = ?
            """,
            (workspace_id, JOB_KIND, request_key),
        ).fetchone()
        if existing is not None:
            stored = job_input(
                connection,
                workspace_id=workspace_id,
                job_key=str(existing["job_key"]),
            )
            stored_private = stored.get("private") if isinstance(stored.get("private"), dict) else None
            if (
                stored_private
                and private_input.get("stageKey") is None
                and stored_private.get("stageKey")
            ):
                private_input["stageKey"] = stored_private.get("stageKey")
            if stored_private != private_input:
                raise ValueError("requestKey is already bound to different job input.")
            return {
                "ok": True,
                "accepted": True,
                "replayed": True,
                "job": get_job(
                    connection,
                    workspace_id=workspace_id,
                    job_key=str(existing["job_key"]),
                    event_limit=200,
                ),
            }
        if private_input.get("stageKey"):
            validate_import_stage_for_confirmation(
                stage_key=str(private_input["stageKey"]),
                workspace_id=workspace_id,
            )
        for stage_key in (private_input.get("stageBindings") or {}).values():
            validate_import_stage_for_confirmation(
                stage_key=str(stage_key),
                workspace_id=workspace_id,
            )
        plan = _build_current_plan(
            connection,
            private_input=private_input,
            build_import_preview=build_import_preview,
            build_folder_import_plan=build_folder_import_plan,
            read_table_file=read_table_file,
            active_workspace_id=active_workspace_id,
        )
        planned_stage_key = str(plan.get("stageKey") or ((plan.get("importStage") or {}).get("stageKey") if isinstance(plan.get("importStage"), dict) else "") or "")
        if import_kind == "single":
            if private_input.get("stageKey") and str(private_input["stageKey"]) != planned_stage_key:
                raise ValueError("Import stage changed after preview; run the preview again.")
            private_input["stageKey"] = planned_stage_key or None
        if expected_plan != str(plan.get("planFingerprint") or ""):
            raise ValueError("Import plan changed after preview; run the preview again.")
        _validate_single_commit_binding(private_input, plan)
        schema_change = plan.get("schemaChange") if isinstance(plan.get("schemaChange"), dict) else None
        if (
            import_kind == "single"
            and schema_change
            and schema_change.get("confirmationRequired") is True
            and private_input.get("confirmSchemaChange") is not True
        ):
            raise ValueError("IMPORT_SCHEMA_CHANGE_CONFIRMATION_REQUIRED: review the field impact and confirm schema change.")
        if import_kind == "single" and plan.get("readyToCommit") is False:
            raise ValueError(f"Single-file import plan is blocked: {', '.join(plan.get('blockers') or ['owner-review-required'])}")
        if import_kind == "folder" and plan.get("readyToCommit") is not True:
            raise ValueError(f"Folder import plan is blocked: {', '.join(plan.get('blockers') or ['owner-review-required'])}")
        public_input = _public_job_input(
            import_kind=import_kind,
            path=path,
            plan=plan,
            request_key=request_key,
        )
        stored_input = {"public": public_input, "private": private_input}
        job = create_job(
            connection,
            workspace_id=workspace_id,
            kind=JOB_KIND,
            label=str(getattr(args, "label", "") or f"Import {_safe_source_name(path)}"),
            input_value=stored_input,
            capability_id="cli.import-job-run",
            source_run_id=plan.get("parentSourceRunId"),
            request_key=request_key,
            now_iso=now_iso,
        )
        replayed = job["status"] != STATUS_CREATED
        if job["status"] == STATUS_CREATED:
            job = transition_job(
                connection,
                workspace_id=workspace_id,
                job_key=job["jobKey"],
                status=STATUS_QUEUED,
                progress=0,
                stage="validate_plan",
                message="Import plan was accepted by the durable runtime.",
                now_iso=now_iso,
            )
        connection.commit()
    return {"ok": True, "accepted": True, "replayed": replayed, "job": job}


def _private_input_for_job(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    job_key: str,
) -> dict[str, Any]:
    stored = job_input(connection, workspace_id=workspace_id, job_key=job_key)
    private = stored.get("private") if isinstance(stored.get("private"), dict) else None
    if private is None:
        raise ValueError("Import job has no private execution binding.")
    return dict(private)


def _expected_manifest_intents(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    table_keys: list[str],
    plan: dict[str, Any],
    physical_table_for_workspace: Callable[[str, str], str],
) -> list[dict[str, Any]]:
    occurrence: dict[str, int] = {table_key: 0 for table_key in table_keys}
    for item in plan.get("items") or []:
        if isinstance(item, dict) and str(item.get("tableKey") or "") in occurrence:
            occurrence[str(item["tableKey"])] += 1
    intents: list[dict[str, Any]] = []
    for table_key in table_keys:
        current = connection.execute(
            "SELECT data_version FROM table_registry WHERE workspace_id = ? AND table_key = ?",
            (workspace_id, table_key),
        ).fetchone()
        current_version = int(current["data_version"] or 0) if current else 0
        increment = max(1, occurrence.get(table_key, 0))
        intents.append({
            "logicalTable": physical_table_for_workspace(workspace_id, table_key),
            "tableKey": table_key,
            "expectedDataVersion": current_version + increment,
        })
    return intents


def _publish_current_replicas(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    table_keys: list[str],
    duckdb_path: Path,
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
) -> list[dict[str, Any]]:
    try:
        import duckdb  # type: ignore
    except Exception as exc:  # pragma: no cover - environment-specific
        raise RuntimeError(f"DuckDB runtime is unavailable: {exc}") from exc
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    published: list[dict[str, Any]] = []
    with duckdb.connect(str(duckdb_path)) as duck_connection:
        for table_key in table_keys:
            registry = connection.execute(
                "SELECT * FROM table_registry WHERE workspace_id = ? AND table_key = ?",
                (workspace_id, table_key),
            ).fetchone()
            if registry is None:
                raise RuntimeError(f"Import staging did not create table registry entry: {table_key}")
            physical_table = str(registry["physical_table"])
            row_count = int(registry["row_count"] or 0)
            data_version = int(registry["data_version"] or 0)
            source_version = f"{workspace_id}:{table_key}:{data_version}:{row_count}"
            replica = sync_table_to_duckdb(
                connection,
                duck_connection,
                physical_table,
                table_columns(connection, physical_table),
                source_version=source_version,
                cleanup_stale=False,
            )
            published.append({
                "logicalTable": physical_table,
                "tableKey": table_key,
                "sourceVersion": source_version,
                "replicaTable": replica["replicaTable"],
                "rowCount": int(replica["rowCount"]),
                "dataVersion": data_version,
            })
    return published


def _public_import_result(
    *,
    import_kind: str,
    plan: dict[str, Any],
    raw_result: dict[str, Any],
    journal_key: str,
) -> dict[str, Any]:
    table_results = raw_result.get("results") if isinstance(raw_result.get("results"), list) else [raw_result]
    tables = []
    for item in table_results:
        if not isinstance(item, dict):
            continue
        profile = item.get("profile") if isinstance(item.get("profile"), dict) else {}
        tables.append({
            "tableKey": item.get("tableKey"),
            "displayName": item.get("displayName"),
            "mode": item.get("mode"),
            "rowCount": item.get("rowCount") if item.get("rowCount") is not None else profile.get("rowCount"),
            "dataVersion": item.get("dataVersion"),
            "writeSummary": item.get("writeSummary"),
            "relationshipRevalidations": item.get("relationshipRevalidations"),
        })
    return {
        "schema": IMPORT_JOB_SCHEMA,
        "workspaceId": str(raw_result.get("workspaceId") or plan.get("workspaceId") or ""),
        "committed": True,
        "importKind": import_kind,
        "planFingerprint": plan.get("planFingerprint"),
        "sourceRunId": raw_result.get("sourceRunId"),
        "fileCount": int(plan.get("fileCount") or (1 if import_kind == "single" else 0)),
        "tableCount": int(plan.get("tableCount") or len(tables)),
        "tables": tables,
        "activationJournalKey": journal_key,
    }


def _job_cancel_requested(connection: sqlite3.Connection, workspace_id: str, job_key: str) -> bool:
    return get_job(connection, workspace_id=workspace_id, job_key=job_key, event_limit=5)["status"] == STATUS_CANCEL_REQUESTED


def import_job_run_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    build_import_preview: Callable[..., dict[str, Any]],
    build_folder_import_plan: Callable[..., dict[str, Any]],
    execute_import_commit: Callable[..., dict[str, Any]],
    execute_folder_import_plan: Callable[..., dict[str, Any]],
    read_table_file: Callable[..., Any],
    physical_table_for_workspace: Callable[[str, str], str],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    duckdb_path: Path,
    mutation_lock_path: Path,
    recovery_root: Path,
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    job_key = str(getattr(args, "job", "") or "").strip()
    if not job_key:
        raise ValueError("Job key is required.")
    journal: dict[str, Any] | None = None
    committed = False
    raw_result: dict[str, Any] | None = None
    workspace_id = ""
    lease_claimed = False
    lease_token = str(getattr(args, "lease_token", "") or uuid.uuid4().hex).strip()
    lease_epoch = 0
    mutation_guard = None
    mutation_guard_entered = False

    def assert_recovery_clear() -> None:
        fences = unfinished_recovery_fences(recovery_root)
        if fences:
            workspaces = sorted({item["workspaceId"] for item in fences})
            raise PermissionError(
                "Import activation is fenced by unfinished recovery for: " + ", ".join(workspaces)
            )

    try:
        with open_db() as connection:
            ensure_activation_journal_schema(connection)
            workspace_id = _workspace_id(connection, args, active_workspace_id)
            current_job = get_job(connection, workspace_id=workspace_id, job_key=job_key, event_limit=20)
            if current_job["kind"] != JOB_KIND:
                raise ValueError(f"Job {job_key} is not an import job.")
            if current_job["status"] in TERMINAL_STATUSES:
                return {"ok": True, "changed": False, "job": current_job}
            if current_job["status"] == STATUS_NEEDS_ATTENTION:
                raise ValueError("Import job needs explicit resume before it can run again.")
            # Establish the persistent lease while briefly holding the same
            # boundary used by recovery. A restore therefore either observes
            # this lease and refuses, or completes before the claim begins.
            with workspace_mutation_lock(mutation_lock_path, timeout_seconds=30.0):
                assert_recovery_clear()
                connection.execute("BEGIN IMMEDIATE")
                claimed_epoch = claim_import_workspace(
                    connection,
                    workspace_id=workspace_id,
                    job_key=job_key,
                    lease_token=lease_token,
                    now_iso=now_iso,
                )
                if claimed_epoch is None:
                    connection.rollback()
                    return {"ok": True, "changed": False, "deferred": True, "job": current_job}
                lease_claimed = True
                lease_epoch = int(claimed_epoch)
                current_job = get_job(connection, workspace_id=workspace_id, job_key=job_key, event_limit=20)
                if current_job["status"] == STATUS_CREATED:
                    transition_job(
                        connection,
                        workspace_id=workspace_id,
                        job_key=job_key,
                        status=STATUS_QUEUED,
                        stage="validate_plan",
                        expected_status=STATUS_CREATED,
                        now_iso=now_iso,
                    )
                    current_job = get_job(connection, workspace_id=workspace_id, job_key=job_key, event_limit=20)
                current_job = transition_job(
                    connection,
                    workspace_id=workspace_id,
                    job_key=job_key,
                    status=STATUS_RUNNING,
                    progress=5,
                    stage="validate_plan",
                    message="Import worker started and is revalidating the frozen plan.",
                    expected_status=STATUS_QUEUED,
                    now_iso=now_iso,
                )
                connection.commit()

            private_input = _private_input_for_job(connection, workspace_id=workspace_id, job_key=job_key)
            if str(private_input.get("workspaceId") or "") != workspace_id:
                raise RuntimeError("Durable import job input does not belong to the requested workspace.")
            import_kind = str(private_input.get("importKind") or "single")
            plan = _build_current_plan(
                connection,
                private_input=private_input,
                build_import_preview=build_import_preview,
                build_folder_import_plan=build_folder_import_plan,
                read_table_file=read_table_file,
                active_workspace_id=active_workspace_id,
            )
            if str(plan.get("planFingerprint") or "") != str(private_input.get("expectedPlan") or ""):
                raise ValueError("Import input, plan, or parent source version drifted before execution.")
            _validate_single_commit_binding(private_input, plan)
            if import_kind == "folder" and plan.get("readyToCommit") is not True:
                raise ValueError(f"Folder import plan is blocked: {', '.join(plan.get('blockers') or ['owner-review-required'])}")
            table_keys = _plan_table_keys(plan, import_kind)
            mutation_guard = workspace_mutation_lock(mutation_lock_path, timeout_seconds=30.0)
            mutation_guard.__enter__()
            mutation_guard_entered = True
            # Recheck only after acquiring the boundary so an interrupted
            # restore cannot appear between validation and activation.
            assert_recovery_clear()
            connection.execute("BEGIN IMMEDIATE")
            assert_import_workspace(
                connection,
                workspace_id=workspace_id,
                job_key=job_key,
                lease_token=lease_token,
                lease_epoch=lease_epoch,
            )
            update_job_progress(
                connection,
                workspace_id=workspace_id,
                job_key=job_key,
                progress=15,
                stage="validate_plan",
                message="Frozen file hashes, schema decisions, and parent source version are current.",
                now_iso=now_iso,
                payload={"tableKeys": table_keys, "planFingerprint": plan["planFingerprint"]},
            )
            if _job_cancel_requested(connection, workspace_id, job_key):
                canceled = transition_job(
                    connection,
                    workspace_id=workspace_id,
                    job_key=job_key,
                    status=STATUS_CANCELED,
                    stage="canceled",
                    message="Import was canceled before the commit boundary.",
                    error={"code": "job-canceled", "reason": "cancel-requested-before-commit"},
                    now_iso=now_iso,
                )
                connection.commit()
                return {"ok": True, "job": canceled}

            intents = _expected_manifest_intents(
                connection,
                workspace_id=workspace_id,
                table_keys=table_keys,
                plan=plan,
                physical_table_for_workspace=physical_table_for_workspace,
            )
            rollback_manifest = capture_replica_manifest(
                duckdb_path,
                [str(item["logicalTable"]) for item in intents],
            )
            journal = prepare_activation(
                connection,
                workspace_id=workspace_id,
                job_key=job_key,
                plan_fingerprint=str(plan["planFingerprint"]),
                parent_source_run_id=plan.get("parentSourceRunId"),
                table_keys=table_keys,
                expected_manifest=intents,
                rollback_manifest=rollback_manifest,
                now_iso=now_iso,
            )
            update_job_progress(
                connection,
                workspace_id=workspace_id,
                job_key=job_key,
                progress=25,
                stage="stage_source",
                message="Activation rollback material was persisted.",
                now_iso=now_iso,
                payload={"activationJournalKey": journal["journalKey"]},
            )
            connection.commit()

            connection.execute("BEGIN IMMEDIATE")
            assert_import_workspace(
                connection,
                workspace_id=workspace_id,
                job_key=job_key,
                lease_token=lease_token,
                lease_epoch=lease_epoch,
            )
            if _job_cancel_requested(connection, workspace_id, job_key):
                transition_activation(
                    connection,
                    workspace_id=workspace_id,
                    journal_key=str(journal["journalKey"]),
                    phase=PHASE_FINALIZED,
                    outcome="canceled_before_commit",
                    now_iso=now_iso,
                )
                canceled = transition_job(
                    connection,
                    workspace_id=workspace_id,
                    job_key=job_key,
                    status=STATUS_CANCELED,
                    stage="canceled",
                    message="Import was canceled before the commit boundary.",
                    error={"code": "job-canceled", "reason": "cancel-requested-before-commit"},
                    now_iso=now_iso,
                )
                connection.commit()
                return {"ok": True, "job": canceled}

            journal = transition_activation(
                connection,
                workspace_id=workspace_id,
                journal_key=str(journal["journalKey"]),
                phase=PHASE_COMMIT_STARTED,
                now_iso=now_iso,
            )
            update_job_progress(
                connection,
                workspace_id=workspace_id,
                job_key=job_key,
                progress=35,
                stage="stage_source",
                message="The single-writer commit boundary has started.",
                now_iso=now_iso,
            )
            connection.commit()

            connection.execute("BEGIN IMMEDIATE")
            assert_import_workspace(
                connection,
                workspace_id=workspace_id,
                job_key=job_key,
                lease_token=lease_token,
                lease_epoch=lease_epoch,
            )
            if import_kind == "single":
                raw_result = execute_import_commit(
                    connection,
                    private_input["path"],
                    private_input.get("table"),
                    private_input.get("name"),
                    private_input.get("mode") or "create",
                    private_input.get("uniqueFields"),
                    private_input.get("conflictRule"),
                    workspace_id=workspace_id,
                    stage_key=private_input.get("stageKey") or None,
                )
            else:
                raw_result = execute_folder_import_plan(
                    connection,
                    plan,
                    workspace_id=workspace_id,
                    execute_import_commit=execute_import_commit,
                    active_workspace_id=active_workspace_id,
                )
            if str(raw_result.get("workspaceId") or "") != workspace_id:
                raise RuntimeError("Durable import commit escaped its frozen workspace.")
            target_source_run_id = str(raw_result.get("sourceRunId") or "")
            if not target_source_run_id:
                raise RuntimeError("Import staging did not create a source run.")
            connection.execute(
                "UPDATE workspaces SET current_source_run_id = ? WHERE id = ?",
                (plan.get("parentSourceRunId"), workspace_id),
            )
            update_job_progress(
                connection,
                workspace_id=workspace_id,
                job_key=job_key,
                progress=55,
                stage="publish_replica",
                message="Source rows are staged; publishing verified analysis replicas.",
                now_iso=now_iso,
            )
            expected_manifest = _publish_current_replicas(
                connection,
                workspace_id=workspace_id,
                table_keys=table_keys,
                duckdb_path=duckdb_path,
                table_columns=table_columns,
            )
            journal = transition_activation(
                connection,
                workspace_id=workspace_id,
                journal_key=str(journal["journalKey"]),
                phase=PHASE_REPLICA_PUBLISHED,
                target_source_run_id=target_source_run_id,
                expected_manifest=expected_manifest,
                now_iso=now_iso,
            )
            update_job_progress(
                connection,
                workspace_id=workspace_id,
                job_key=job_key,
                progress=75,
                stage="switch_source_run",
                message="Analysis replicas passed publication checks.",
                now_iso=now_iso,
            )
            connection.execute(
                "UPDATE workspaces SET current_source_run_id = ? WHERE id = ?",
                (target_source_run_id, workspace_id),
            )
            journal = transition_activation(
                connection,
                workspace_id=workspace_id,
                journal_key=str(journal["journalKey"]),
                phase=PHASE_SOURCE_SELECTION_COMMITTED,
                target_source_run_id=target_source_run_id,
                expected_manifest=expected_manifest,
                now_iso=now_iso,
            )
            update_job_progress(
                connection,
                workspace_id=workspace_id,
                job_key=job_key,
                progress=95,
                stage="postprocess",
                message="The current source version was switched atomically.",
                now_iso=now_iso,
            )
            result = _public_import_result(
                import_kind=import_kind,
                plan=plan,
                raw_result=raw_result,
                journal_key=str(journal["journalKey"]),
            )
            final_job = transition_job(
                connection,
                workspace_id=workspace_id,
                job_key=job_key,
                status=STATUS_SUCCEEDED,
                stage="postprocess",
                message="Import and source activation completed.",
                result=result,
                source_run_id=target_source_run_id,
                now_iso=now_iso,
            )
            connection.commit()
            committed = True

            warning = None
            try:
                cleanup_stale_replicas(duckdb_path)
            except Exception as cleanup_error:  # committed data remains authoritative
                warning = {
                    "code": "activation-cleanup-deferred",
                    "message": "Committed data is active; stale replica cleanup will be retried.",
                }
            transition_activation(
                connection,
                workspace_id=workspace_id,
                journal_key=str(journal["journalKey"]),
                phase=PHASE_FINALIZED,
                outcome="committed",
                warning=warning,
                now_iso=now_iso,
            )
            connection.commit()
            return {"ok": True, "job": final_job, "result": result, "warning": warning}
    except Exception as exc:
        if committed:
            return {
                "ok": True,
                "job": {
                    "schema": IMPORT_JOB_SCHEMA,
                    "jobKey": job_key,
                    "workspaceId": workspace_id,
                    "status": STATUS_SUCCEEDED,
                },
                "result": raw_result,
                "warning": {
                    "code": "activation-finalize-deferred",
                    "message": "The committed source is active; journal finalization requires reconciliation.",
                },
            }
        with open_db() as recovery_connection:
            ensure_activation_journal_schema(recovery_connection)
            if not workspace_id:
                workspace_id = _workspace_id(recovery_connection, args, active_workspace_id)
            current_job = get_job(recovery_connection, workspace_id=workspace_id, job_key=job_key, event_limit=20)
            if lease_claimed:
                recovery_connection.execute("BEGIN IMMEDIATE")
                try:
                    assert_import_workspace(
                        recovery_connection,
                        workspace_id=workspace_id,
                        job_key=job_key,
                        lease_token=lease_token,
                        lease_epoch=lease_epoch,
                    )
                except RuntimeError:
                    recovery_connection.rollback()
                    return {
                        "ok": False,
                        "changed": False,
                        "code": "IMPORT_WORKER_FENCED",
                        "error": "Import worker ownership was revoked; durable recovery owns reconciliation.",
                        "job": current_job,
                    }
            journal = activation_for_job(recovery_connection, workspace_id=workspace_id, job_key=job_key)
            rollback_error: Exception | None = None
            if journal and journal["phase"] != PHASE_FINALIZED:
                try:
                    restore_replica_manifest(duckdb_path, journal.get("rollbackManifest") or [])
                    journal = transition_activation(
                        recovery_connection,
                        workspace_id=workspace_id,
                        journal_key=str(journal["journalKey"]),
                        phase=PHASE_FINALIZED,
                        outcome="rolled_back",
                        warning={
                            "code": "import-execution-failed",
                            "message": "Import execution stopped before the source selection was committed.",
                        },
                        now_iso=now_iso,
                    )
                except Exception as restore_error:  # fail closed; startup reconciliation will retry
                    rollback_error = restore_error
            if current_job["status"] not in TERMINAL_STATUSES:
                if rollback_error is not None:
                    target_status = STATUS_NEEDS_ATTENTION
                    code = "activation-state-unknown"
                    recovery_action = "reconcile"
                elif current_job["status"] == STATUS_CANCEL_REQUESTED:
                    target_status = STATUS_CANCELED
                    code = "job-canceled"
                    recovery_action = None
                else:
                    target_status = STATUS_FAILED
                    code = "import-job-failed"
                    recovery_action = "re-preview"
                final_job = transition_job(
                    recovery_connection,
                    workspace_id=workspace_id,
                    job_key=job_key,
                    status=target_status,
                    stage="reconcile" if target_status == STATUS_NEEDS_ATTENTION else "failed",
                    message="Import did not reach a committed source selection.",
                    error={
                        "code": code,
                        "message": "Import execution stopped before a committed source selection.",
                        "recoveryAction": recovery_action,
                        "rollbackErrorCode": "activation-rollback-deferred" if rollback_error else None,
                    },
                    now_iso=now_iso,
                )
            else:
                final_job = current_job
            recovery_connection.commit()
        return {
            "ok": final_job["status"] == STATUS_CANCELED,
            "job": final_job,
            "error": None if final_job["status"] == STATUS_CANCELED else "Import execution did not commit a source selection.",
        }
    finally:
        if mutation_guard_entered and mutation_guard is not None:
            mutation_guard.__exit__(None, None, None)
        if lease_claimed and workspace_id:
            with open_db() as lease_connection:
                ensure_activation_journal_schema(lease_connection)
                release_import_workspace(
                    lease_connection,
                    workspace_id=workspace_id,
                    job_key=job_key,
                    lease_token=lease_token,
                    lease_epoch=lease_epoch,
                    now_iso=now_iso,
                )
                lease_connection.commit()


def import_job_resume_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    build_import_preview: Callable[..., dict[str, Any]],
    build_folder_import_plan: Callable[..., dict[str, Any]],
    read_table_file: Callable[..., Any],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    job_key = str(getattr(args, "job", "") or "").strip()
    with open_db() as connection:
        ensure_activation_journal_schema(connection)
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        current = get_job(connection, workspace_id=workspace_id, job_key=job_key, event_limit=20)
        if current["kind"] != JOB_KIND:
            raise ValueError(f"Job {job_key} is not an import job.")
        if current["status"] != STATUS_NEEDS_ATTENTION:
            raise ValueError("Only an import job that needs attention can be resumed.")
        private_input = _private_input_for_job(connection, workspace_id=workspace_id, job_key=job_key)
        plan = _build_current_plan(
            connection,
            private_input=private_input,
            build_import_preview=build_import_preview,
            build_folder_import_plan=build_folder_import_plan,
            read_table_file=read_table_file,
            active_workspace_id=active_workspace_id,
        )
        if str(plan.get("planFingerprint") or "") != str(private_input.get("expectedPlan") or ""):
            return {
                "ok": False,
                "code": "IMPORT_PLAN_DRIFTED",
                "error": "Import inputs or parent source version changed; preview and confirm a new import.",
                "recoveryAction": "re-preview",
                "job": current,
            }
        _validate_single_commit_binding(private_input, plan)
        job = transition_job(
            connection,
            workspace_id=workspace_id,
            job_key=job_key,
            status=STATUS_QUEUED,
            progress=current["progress"],
            stage="reconcile",
            message="Import inputs are current; the job is queued for an explicit retry.",
            event_type="job_resumed",
            now_iso=now_iso,
        )
        connection.commit()
    return {"ok": True, "resumed": True, "job": job}


def recover_import_jobs(
    connection: sqlite3.Connection,
    *,
    duckdb_path: Path,
    now_iso: Callable[[], str],
    workspace_id: str | None = None,
    job_key: str | None = None,
) -> list[dict[str, Any]]:
    ensure_activation_journal_schema(connection)
    reconciled: dict[tuple[str, str], dict[str, Any]] = {}
    for journal in unfinished_activations(connection, workspace_id=workspace_id):
        if job_key and str(journal["jobKey"]) != job_key:
            continue
        outcome = reconcile_activation(
            connection,
            journal=journal,
            duckdb_path=duckdb_path,
            now_iso=now_iso,
        )
        reconciled[(str(journal["workspaceId"]), str(journal["jobKey"]))] = outcome

    params: list[Any] = [JOB_KIND, STATUS_QUEUED, STATUS_RUNNING, STATUS_CANCEL_REQUESTED, STATUS_NEEDS_ATTENTION]
    where = "kind = ? AND status IN (?, ?, ?, ?)"
    if workspace_id:
        where += " AND workspace_id = ?"
        params.append(workspace_id)
    if job_key:
        where += " AND job_key = ?"
        params.append(job_key)
    rows = connection.execute(
        f"SELECT workspace_id, job_key, status FROM analysis_jobs WHERE {where} ORDER BY created_at, job_key",
        tuple(params),
    ).fetchall()
    recovered: list[dict[str, Any]] = []
    for row in rows:
        item_workspace = str(row["workspace_id"])
        item_job = str(row["job_key"])
        outcome = reconciled.get((item_workspace, item_job))
        current = get_job(connection, workspace_id=item_workspace, job_key=item_job, event_limit=20)
        if current["status"] in TERMINAL_STATUSES:
            recovered.append(current)
            continue
        if outcome and outcome.get("committed") is True:
            target_status = STATUS_SUCCEEDED
            error = None
            result = current.get("result") or {
                "schema": IMPORT_JOB_SCHEMA,
                "committed": True,
                "sourceRunId": (outcome.get("journal") or {}).get("targetSourceRunId"),
                "activationJournalKey": (outcome.get("journal") or {}).get("journalKey"),
                "reconciled": True,
            }
        elif current["status"] == STATUS_CANCEL_REQUESTED:
            target_status = STATUS_CANCELED
            error = {"code": "job-canceled", "reason": "runtime-restarted"}
            result = None
        else:
            target_status = STATUS_NEEDS_ATTENTION
            error = {
                "code": "runtime-restarted",
                "retryable": True,
                "recoveryAction": "resume" if not outcome or outcome.get("action") != "blocked" else "reconcile",
                "previousStatus": current["status"],
                "reconcileCode": outcome.get("code") if outcome else None,
            }
            result = None
        recovered.append(transition_job(
            connection,
            workspace_id=item_workspace,
            job_key=item_job,
            status=target_status,
            stage="reconcile",
            message="The durable import was reconciled after local runtime restart.",
            result=result,
            error=error,
            event_type="import_job_recovered",
            now_iso=now_iso,
        ))
    return recovered


def import_job_recover_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    duckdb_path: Path,
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = None if getattr(args, "all", False) else _workspace_id(connection, args, active_workspace_id)
        connection.execute("BEGIN IMMEDIATE")
        revoked = revoke_import_workspace_leases(connection, workspace_id=workspace_id, now_iso=now_iso)
        recovered = recover_import_jobs(
            connection,
            workspace_id=workspace_id,
            duckdb_path=duckdb_path,
            now_iso=now_iso,
        )
        connection.commit()
    blocked = [
        item for item in recovered
        if item.get("status") == STATUS_NEEDS_ATTENTION
        and isinstance(item.get("error"), dict)
        and item["error"].get("recoveryAction") == "reconcile"
    ]
    return {
        "ok": not blocked,
        "scope": "all-workspaces" if workspace_id is None else workspace_id,
        "revokedLeases": revoked,
        "recovered": recovered,
        "count": len(recovered),
        "needsAttention": blocked,
    }


def import_job_process_exit_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    duckdb_path: Path,
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    job_key = str(getattr(args, "job", "") or "").strip()
    lease_token = str(getattr(args, "lease_token", "") or "").strip()
    if not lease_token:
        raise ValueError("Import worker process-exit reconciliation requires its lease token.")
    with open_db() as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        ensure_activation_journal_schema(connection)
        connection.execute("BEGIN IMMEDIATE")
        owner_row = connection.execute(
            """
            SELECT active FROM import_workspace_leases
            WHERE workspace_id = ? AND job_key = ? AND lease_token = ?
            """,
            (workspace_id, job_key, lease_token),
        ).fetchone()
        revoked = revoke_import_workspace_leases(
            connection,
            workspace_id=workspace_id,
            job_key=job_key,
            lease_token=lease_token,
            now_iso=now_iso,
        )
        # A late exit from a superseded worker must never reconcile state now
        # owned by a newer lease token for the same durable job.
        recovered = recover_import_jobs(
            connection,
            workspace_id=workspace_id,
            job_key=job_key,
            duckdb_path=duckdb_path,
            now_iso=now_iso,
        ) if owner_row is not None else []
        job = get_job(connection, workspace_id=workspace_id, job_key=job_key, event_limit=50)
        unfinished = activation_for_job(connection, workspace_id=workspace_id, job_key=job_key)
        connection.commit()
    safe_to_drain = owner_row is not None and job["status"] in TERMINAL_STATUSES and (
        unfinished is None or unfinished.get("phase") == PHASE_FINALIZED
    )
    return {
        "ok": safe_to_drain,
        "changed": any(item["jobKey"] == job_key for item in recovered),
        "leaseRevoked": bool(revoked),
        "leaseMatched": owner_row is not None,
        "safeToDrain": safe_to_drain,
        "code": None if safe_to_drain else "IMPORT_RECONCILIATION_BLOCKED",
        "recoveryAction": None if safe_to_drain else "reconcile",
        "job": job,
    }
