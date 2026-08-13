from __future__ import annotations

"""Thin CLI composition layer for the durable import application service."""

import argparse
import hashlib
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from atomic_import_plan_service import bind_single_import_plan
from bi_cli_core import DB_PATH, DUCKDB_PATH, ROOT, now_iso
from bi_cli_io_services import read_table_file
from bi_cli_schema import active_workspace_id, open_db, physical_table_for_workspace, table_columns
from bi_cli_source_commands import (
    build_import_preview,
    execute_import_commit,
    preview_import_command,
    preview_import_folder_command,
)
from import_command_service import build_folder_import_plan, execute_folder_import_plan
from import_job_service import (
    import_job_create_command as create_import_job,
    import_job_process_exit_command as reconcile_import_job_process_exit,
    import_job_recover_command as recover_import_jobs,
    import_job_resume_command as resume_import_job,
    import_job_run_command as run_import_job,
)
from workspace_mutation_lock_service import (
    WorkspaceMutationBusyError,
    workspace_mutation_lock,
    workspace_read_lock,
)
from workspace_recovery_service import configured_recovery_root, unfinished_recovery_fences


LEGACY_IMPORT_REQUEST_SCHEMA = "aibi-legacy-import-request/v1"
LEGACY_IMPORT_LOCK_PATH = DB_PATH.parent / ".aibi-cross-engine-writer.lock"


def _assert_legacy_recovery_clear() -> None:
    fences = unfinished_recovery_fences(configured_recovery_root(ROOT))
    if fences:
        workspaces = sorted({item["workspaceId"] for item in fences})
        raise PermissionError(
            "Import is fenced by unfinished recovery for: " + ", ".join(workspaces)
        )


@contextmanager
def legacy_import_preview_boundary() -> Iterator[None]:
    """Keep compatibility previews behind recovery's shared read boundary."""
    with workspace_read_lock(LEGACY_IMPORT_LOCK_PATH):
        _assert_legacy_recovery_clear()
        yield


@contextmanager
def _legacy_import_create_boundary() -> Iterator[None]:
    """Persist only the queued job while briefly owning the writer boundary."""
    with workspace_mutation_lock(LEGACY_IMPORT_LOCK_PATH):
        _assert_legacy_recovery_clear()
        yield


def _create_import_job_with_preview(args, preview_builder):
    return create_import_job(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        build_import_preview=preview_builder,
        build_folder_import_plan=build_folder_import_plan,
        read_table_file=read_table_file,
        now_iso=now_iso,
    )


def _create_legacy_import_job_with_boundary(args, preview_builder):
    with _legacy_import_create_boundary():
        return _create_import_job_with_preview(args, preview_builder)


def import_job_create_command(args):
    return _create_import_job_with_preview(args, build_import_preview)


def _run_import_job_with_preview(args, preview_builder):
    return run_import_job(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        build_import_preview=preview_builder,
        build_folder_import_plan=build_folder_import_plan,
        execute_import_commit=execute_import_commit,
        execute_folder_import_plan=execute_folder_import_plan,
        read_table_file=read_table_file,
        physical_table_for_workspace=physical_table_for_workspace,
        table_columns=table_columns,
        duckdb_path=DUCKDB_PATH,
        mutation_lock_path=DB_PATH.parent / ".aibi-cross-engine-writer.lock",
        recovery_root=configured_recovery_root(ROOT),
        now_iso=now_iso,
    )


def import_job_run_command(args):
    return _run_import_job_with_preview(args, build_import_preview)


def import_job_resume_command(args):
    return resume_import_job(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        build_import_preview=build_import_preview,
        build_folder_import_plan=build_folder_import_plan,
        read_table_file=read_table_file,
        now_iso=now_iso,
    )


def import_job_recover_command(args):
    return recover_import_jobs(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        duckdb_path=DUCKDB_PATH,
        now_iso=now_iso,
    )


def import_job_process_exit_command(args):
    return reconcile_import_job_process_exit(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        duckdb_path=DUCKDB_PATH,
        now_iso=now_iso,
    )


def _legacy_import_workspace(args: argparse.Namespace) -> str:
    requested = str(getattr(args, "workspace", "") or "").strip()
    with legacy_import_preview_boundary():
        with open_db() as connection:
            workspace_id = requested or active_workspace_id(connection)
            if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
                raise ValueError(f"Unknown workspace: {workspace_id}")
    return workspace_id


def _legacy_import_request_key(
    args: argparse.Namespace,
    *,
    workspace_id: str,
    import_kind: str,
    expected_plan: str,
) -> str:
    """Bind legacy retries to the exact confirmed input without exposing its path."""
    path_value = getattr(args, "file", None) if import_kind == "single" else getattr(args, "path", None)
    path = Path(str(path_value or "")).resolve()
    material = {
        "schema": LEGACY_IMPORT_REQUEST_SCHEMA,
        "workspaceId": workspace_id,
        "importKind": import_kind,
        "path": path.as_posix(),
        "expectedPlan": expected_plan,
        "table": str(getattr(args, "table", "") or ""),
        "name": str(getattr(args, "name", "") or ""),
        "mode": str(getattr(args, "mode", "") or "create"),
        "uniqueFields": str(getattr(args, "unique_fields", "") or ""),
        "conflictRule": str(getattr(args, "conflict_rule", "") or ""),
        "recursive": not bool(getattr(args, "no_recursive", False)),
        "limit": max(1, min(int(getattr(args, "limit", 200) or 200), 200)),
    }
    canonical = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"legacy-import:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"


def _run_legacy_import_job(
    args: argparse.Namespace,
    *,
    import_kind: str,
    plan: dict,
    preview_builder=build_import_preview,
    execution_mode: str | None = None,
) -> tuple[dict, dict]:
    expected_plan = str(getattr(args, "expected_plan", "") or "").strip()
    current_plan = str(plan.get("planFingerprint") or "").strip()
    if import_kind == "folder" and not expected_plan:
        raise ValueError("Atomic folder import requires --expected-plan from the latest preview.")
    if import_kind == "single" and getattr(args, "require_plan", False) and not expected_plan:
        raise ValueError("Single-file import requires the plan fingerprint from the latest preview.")
    frozen_plan = expected_plan or current_plan
    if not frozen_plan:
        raise ValueError("Import preview did not produce a plan fingerprint.")

    requested_workspace = str(getattr(args, "workspace", "") or "").strip()
    plan_workspace = str(plan.get("workspaceId") or "").strip()
    if requested_workspace and plan_workspace and requested_workspace != plan_workspace:
        raise RuntimeError("Legacy import plan does not belong to the requested workspace.")
    workspace_id = plan_workspace or _legacy_import_workspace(args)
    if not workspace_id:
        raise RuntimeError("Legacy import plan did not bind a workspace.")
    request_key = _legacy_import_request_key(
        args,
        workspace_id=workspace_id,
        import_kind=import_kind,
        expected_plan=frozen_plan,
    )
    path_value = getattr(args, "file", None) if import_kind == "single" else getattr(args, "path", None)
    created = _create_legacy_import_job_with_boundary(argparse.Namespace(
        workspace=workspace_id,
        import_kind=import_kind,
        path=str(path_value or ""),
        request_key=request_key,
        expected_plan=frozen_plan,
        table=getattr(args, "table", None),
        name=getattr(args, "name", None),
        mode=str(execution_mode or getattr(args, "mode", "") or "create"),
        unique_fields=getattr(args, "unique_fields", None),
        conflict_rule=getattr(args, "conflict_rule", None),
        no_recursive=bool(getattr(args, "no_recursive", False)),
        limit=max(1, min(int(getattr(args, "limit", 200) or 200), 200)),
        label=f"Legacy confirmed import: {Path(str(path_value or '')).name or 'local-source'}",
    ), preview_builder)
    job = created.get("job") if isinstance(created.get("job"), dict) else {}
    job_key = str(job.get("jobKey") or "")
    if not job_key:
        raise RuntimeError("Durable import did not return a job key.")
    execution = _run_import_job_with_preview(argparse.Namespace(
        workspace=workspace_id,
        job=job_key,
        lease_token=None,
    ), preview_builder)
    final_job = execution.get("job") if isinstance(execution.get("job"), dict) else job
    public_result = execution.get("result") if isinstance(execution.get("result"), dict) else final_job.get("result")
    if execution.get("ok") is not True or str(final_job.get("status") or "") != "succeeded" or not isinstance(public_result, dict):
        error = execution.get("error") or final_job.get("error") or "Durable import did not succeed."
        raise RuntimeError(str(error))
    return final_job, public_result


def legacy_import_commit_command(args: argparse.Namespace) -> dict:
    """Run the confirmed legacy single-file command through W1/W3."""
    workspace_id = _legacy_import_workspace(args)
    with legacy_import_preview_boundary():
        plan = preview_import_command(argparse.Namespace(
            workspace=workspace_id,
            file=args.file,
            table=getattr(args, "table", None),
            unique_fields=getattr(args, "unique_fields", None),
            conflict_rule=getattr(args, "conflict_rule", None),
        ))
    preview_builder = build_import_preview
    execution_mode = str(getattr(args, "mode", "") or "create")
    expected_plan = str(getattr(args, "expected_plan", "") or "").strip()
    # Before durable imports existed, unbound create/replace both performed a
    # full table replacement. Preserve that exact legacy behavior by freezing
    # a create plan, while leaving explicit preview fingerprints untouched.
    if not expected_plan and execution_mode in {"create", "replace"} and isinstance(plan.get("matchedTable"), dict):
        def replacement_preview_builder(*preview_args, **preview_kwargs):
            preview = build_import_preview(*preview_args, **preview_kwargs)
            merge_preview = preview.get("mergePolicyPreview") if isinstance(preview.get("mergePolicyPreview"), dict) else {}
            return {
                **preview,
                "matchedTable": None,
                "mergePolicyPreview": {**merge_preview, "mode": "create"},
            }

        preview_builder = replacement_preview_builder
        execution_mode = "create"
        with legacy_import_preview_boundary():
            with open_db() as connection:
                workspace = connection.execute(
                    "SELECT current_source_run_id FROM workspaces WHERE id = ?",
                    (workspace_id,),
                ).fetchone()
                if workspace is None:
                    raise ValueError(f"Unknown workspace: {workspace_id}")
                replacement_preview = preview_builder(
                    connection,
                    args.file,
                    getattr(args, "table", None),
                    getattr(args, "unique_fields", None),
                    getattr(args, "conflict_rule", None),
                    workspace_id=workspace_id,
                )
                if str(replacement_preview.get("workspaceId") or "") != workspace_id:
                    raise RuntimeError("Legacy replacement preview escaped the requested workspace.")
                plan = bind_single_import_plan(
                    replacement_preview,
                    Path(args.file),
                    current_source_run_id=str(workspace["current_source_run_id"] or "") or None,
                )
    final_job, public_result = _run_legacy_import_job(
        args,
        import_kind="single",
        plan=plan,
        preview_builder=preview_builder,
        execution_mode=execution_mode,
    )
    tables = public_result.get("tables") if isinstance(public_result.get("tables"), list) else []
    table = dict(tables[0]) if tables and isinstance(tables[0], dict) else {}
    table["sourceRunId"] = public_result.get("sourceRunId")
    table["mode"] = str(getattr(args, "mode", "") or table.get("mode") or "create")
    source_run = None
    try:
        with legacy_import_preview_boundary():
            with open_db() as connection:
                source_run = connection.execute(
                    "SELECT profile_json FROM source_runs WHERE workspace_id = ? AND id = ?",
                    (str(final_job.get("workspaceId") or ""), str(public_result.get("sourceRunId") or "")),
                ).fetchone()
    except (PermissionError, WorkspaceMutationBusyError):
        # The durable commit is already authoritative. A recovery operation
        # that starts afterward may defer this compatibility-only profile read
        # but must not turn a committed import into a reported failure.
        source_run = None
    table["profile"] = json.loads(str(source_run["profile_json"])) if source_run and source_run["profile_json"] else {
        "rowCount": table.get("rowCount")
    }
    return {
        "ok": True,
        "committed": True,
        "planFingerprint": public_result.get("planFingerprint"),
        "result": table,
        "activationJournalKey": public_result.get("activationJournalKey"),
        "durableJob": final_job,
    }


def legacy_import_folder_command(args: argparse.Namespace) -> dict:
    """Run the confirmed legacy folder command through W1/W3."""
    workspace_id = _legacy_import_workspace(args)
    with legacy_import_preview_boundary():
        plan = preview_import_folder_command(argparse.Namespace(
            workspace=workspace_id,
            path=args.path,
            limit=max(1, min(int(getattr(args, "limit", 200) or 200), 200)),
            no_recursive=bool(getattr(args, "no_recursive", False)),
            unique_fields=getattr(args, "unique_fields", None),
            conflict_rule=getattr(args, "conflict_rule", None),
        ))
    final_job, public_result = _run_legacy_import_job(args, import_kind="folder", plan=plan)
    tables = public_result.get("tables") if isinstance(public_result.get("tables"), list) else []
    return {
        "ok": True,
        "committed": True,
        "path": str(Path(args.path).resolve()),
        "fileCount": public_result.get("fileCount"),
        "tableCount": public_result.get("tableCount"),
        "items": plan.get("items") or [],
        "groups": plan.get("groups") or [],
        "results": tables,
        "sourceRunId": public_result.get("sourceRunId"),
        "planFingerprint": public_result.get("planFingerprint"),
        "activationJournalKey": public_result.get("activationJournalKey"),
        "atomic": True,
        "durableJob": final_job,
    }
