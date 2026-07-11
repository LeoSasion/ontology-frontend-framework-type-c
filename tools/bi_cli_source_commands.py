from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from aibi_contracts import source_pipeline_contract
from bi_cli_core import DUCKDB_PATH, now_iso, quote_identifier, source_label, unique_key
from bi_cli_evidence_bundles import artifact_ref, write_evidence_bundle
from bi_cli_io_services import (
    import_csv_as_table,
    load_connectors,
    merge_import_into_table,
    profile_rows,
    read_table_file,
    rows_to_dicts,
    saved_import_policy,
)
from bi_cli_schema import active_workspace_id, open_db, registry_for_table, table_columns, upsert_navigation_module
from connector_command_service import (
    list_connectors_command as list_connectors_command_service,
    remove_connector_command as remove_connector_command_service,
    save_connector_command as save_connector_command_service,
    sync_connector_command as sync_connector_command_service,
)
from evidence_receipts import (
    build_source_intelligence_dashboard_candidate,
    default_source_intelligence_output_dir,
)
from evidence_run_store import (
    list_source_intelligence_runs,
    save_source_intelligence_run,
)
from import_command_service import (
    build_import_preview as build_import_preview_service,
    execute_import_commit as execute_import_commit_service,
    import_folder_command as import_folder_command_service,
    import_commit_command as import_commit_command_service,
    preview_import_folder_command as preview_import_folder_command_service,
    preview_import_command as preview_import_command_service,
)
from import_job_command_service import (
    list_import_jobs_command as list_import_jobs_command_service,
    remove_import_job_command as remove_import_job_command_service,
    set_import_policy_command as set_import_policy_command_service,
)
from import_policy import (
    analyze_unique_key_quality,
    normalize_records_for_columns,
    preview_merge_plan,
    sanitize_unique_fields,
)
from preferences_theme_command_service import (
    preferences_command as preferences_command_service,
    preferences_payload as preferences_payload_service,
    theme_palettes_command as theme_palettes_command_service,
)
from query_runtime import duckdb_status
from source_management_command_service import (
    build_delete_source_plan as build_delete_source_plan_service,
    delete_source_command as delete_source_command_service,
    remaining_table_key_after_delete as remaining_table_key_after_delete_service,
    rename_source_command as rename_source_command_service,
)
from source_read_model_service import (
    inspect_table_command as inspect_table_command_service,
    list_tables_command as list_tables_command_service,
)

def source_run_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        row = connection.execute(
            """
            SELECT *
            FROM source_runs
            WHERE id = ? AND workspace_id = ?
            """,
            (args.source_run_id, workspace_id),
        ).fetchone()
        if not row:
            return {"ok": False, "error": f"Unknown source run: {args.source_run_id}", "sourceRun": None}
        source_run = dict(row)
        source_run["source_file"] = source_label(source_run["source_file"])
        source_run["profile"] = json.loads(source_run.pop("profile_json"))
        source_run["evidence"] = json.loads(source_run.pop("evidence_json"))
        table_key = source_run["table_key"]
        table = connection.execute(
            """
            SELECT table_key, display_name, source_file, row_count, column_count, created_at
            FROM table_registry
            WHERE table_key = ? AND workspace_id = ?
            """,
            (table_key, workspace_id),
        ).fetchone()
        fields = rows_to_dicts(
            connection.execute(
                """
                SELECT table_key, field_name, role, usage, confidence
                FROM field_semantics
                WHERE table_key = ? AND workspace_id = ?
                ORDER BY field_name
                """,
                (table_key, workspace_id),
            )
        )
        metrics = rows_to_dicts(
            connection.execute(
                """
                SELECT metric_key, label, table_key, measure, aggregation, dimension, time_field, value_format, created_at
                FROM metric_definitions
                WHERE table_key = ? AND workspace_id = ?
                ORDER BY metric_key
                """,
                (table_key, workspace_id),
            )
        )
        relationships = rows_to_dicts(
            connection.execute(
                """
                SELECT relation_key, name, left_table_key, right_table_key, left_field, right_field, join_type, confidence, created_at
                FROM relationships
                WHERE workspace_id = ? AND (left_table_key = ? OR right_table_key = ?)
                ORDER BY relation_key
                """,
                (workspace_id, table_key, table_key),
            )
        )
    table_payload = dict(table) if table else None
    if table_payload:
        table_payload["source_file"] = source_label(table_payload["source_file"])
    return {
        "ok": True,
        "sourceRun": source_run,
        "table": table_payload,
        "fields": fields,
        "metrics": metrics,
        "relationships": relationships,
        "queryRuntime": duckdb_status(DUCKDB_PATH),
    }


def resolve_table_registry(connection: sqlite3.Connection, table_ref: str) -> sqlite3.Row:
    value = str(table_ref or "").strip()
    if not value:
        raise ValueError("Table reference is required.")
    workspace_id = active_workspace_id(connection)
    row = connection.execute(
        """
        SELECT *
        FROM table_registry
        WHERE workspace_id = ? AND (table_key = ? OR display_name = ?)
        ORDER BY CASE WHEN table_key = ? THEN 0 ELSE 1 END
        LIMIT 1
        """,
        (workspace_id, value, value, value),
    ).fetchone()
    if not row:
        raise ValueError(f"Unknown table/source: {table_ref}")
    return row


def list_tables_command(args: argparse.Namespace) -> dict[str, Any]:
    return list_tables_command_service(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        rows_to_dicts=rows_to_dicts,
    )


def inspect_table_command(args: argparse.Namespace) -> dict[str, Any]:
    return inspect_table_command_service(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        resolve_table_registry=resolve_table_registry,
        table_columns=table_columns,
        rows_to_dicts=rows_to_dicts,
        saved_import_policy=saved_import_policy,
        load_connectors=load_connectors,
    )


def rename_source_command(args: argparse.Namespace) -> dict[str, Any]:
    return rename_source_command_service(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        resolve_table_registry=resolve_table_registry,
    )


def remaining_table_key_after_delete(connection: sqlite3.Connection, deleted_table_key: str) -> str:
    return remaining_table_key_after_delete_service(
        connection,
        deleted_table_key,
        active_workspace_id=active_workspace_id,
    )


def build_delete_source_plan(connection: sqlite3.Connection, registry: sqlite3.Row) -> dict[str, Any]:
    return build_delete_source_plan_service(
        connection,
        registry,
        active_workspace_id=active_workspace_id,
        rows_to_dicts=rows_to_dicts,
        load_connectors=load_connectors,
        remaining_table_key_after_delete=remaining_table_key_after_delete,
    )


def delete_source_command(args: argparse.Namespace) -> dict[str, Any]:
    return delete_source_command_service(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        resolve_table_registry=resolve_table_registry,
        build_delete_source_plan=build_delete_source_plan,
    )


def source_intelligence_runs_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        runs = list_source_intelligence_runs(connection, workspace_id=workspace_id, limit=args.limit, include_internal=args.all)
    return {"ok": True, "sourceIntelligenceRuns": runs}


def source_intelligence_command(args: argparse.Namespace) -> dict[str, Any]:
    from source_evidence_engine import source_intelligence

    inputs = [Path(item) for item in (args.inputs or [])]
    label = args.label or "source-intelligence-run"
    if not inputs:
        raise ValueError("Source Intelligence requires imported source paths; import data first or pass one or more input paths.")
    output_dir = Path(args.output_dir) if args.output_dir else default_source_intelligence_output_dir(label)
    manifest = source_intelligence(inputs, output_dir, None)
    run_key = unique_key("source_intelligence")
    created_at = now_iso()
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        save_source_intelligence_run(
            connection,
            run_key=run_key,
            workspace_id=workspace_id,
            label=label,
            input_roots=[str(path) for path in inputs],
            output_dir=str(output_dir),
            manifest=manifest,
            created_at=created_at,
        )
        connection.commit()
    dashboard_candidate = build_source_intelligence_dashboard_candidate(output_dir, manifest)
    evidence_files = sorted(path.name for path in output_dir.glob("*.json"))
    evidence_bundle = write_evidence_bundle(
        command="source-intelligence",
        workspace_id=workspace_id,
        title=f"Source Intelligence: {label}",
        status=str(manifest.get("status") or "ready"),
        summary={
            "runKey": run_key,
            "label": label,
            "sourceCount": manifest.get("sourceCount"),
            "tableCount": manifest.get("tableCount"),
            "relationshipCount": manifest.get("relationshipCount"),
            "metricSqlPlanCount": manifest.get("metricSqlPlanCount"),
            "metricSqlExecutableCount": manifest.get("metricSqlExecutableCount"),
            "dashboardCandidateStatus": dashboard_candidate.get("status"),
        },
        payload={
            "manifest": manifest,
            "dashboardCandidate": dashboard_candidate,
            "evidenceFiles": evidence_files,
        },
        artifacts=[artifact_ref(name, output_dir / name, kind="json") for name in evidence_files],
        bundle_dir=output_dir / "evidence-bundle",
    )
    return {
        "ok": True,
        "runKey": run_key,
        "label": label,
        "outputDir": str(output_dir),
        "manifest": manifest,
        "dashboardCandidate": dashboard_candidate,
        "evidenceFiles": evidence_files,
        "evidenceBundle": evidence_bundle,
    }



def set_import_policy_command(args: argparse.Namespace) -> dict[str, Any]:
    return set_import_policy_command_service(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        registry_for_table=registry_for_table,
        table_columns=table_columns,
        sanitize_unique_fields=sanitize_unique_fields,
        saved_import_policy=saved_import_policy,
    )


def list_import_jobs_command(args: argparse.Namespace) -> dict[str, Any]:
    return list_import_jobs_command_service(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
    )


def remove_import_job_command(args: argparse.Namespace) -> dict[str, Any]:
    return remove_import_job_command_service(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
    )


def list_connectors_command(args: argparse.Namespace) -> dict[str, Any]:
    return list_connectors_command_service(args, open_db=open_db)


def save_connector_command(args: argparse.Namespace) -> dict[str, Any]:
    return save_connector_command_service(args, open_db=open_db)


def remove_connector_command(args: argparse.Namespace) -> dict[str, Any]:
    return remove_connector_command_service(args, open_db=open_db)


def sync_connector_command(args: argparse.Namespace) -> dict[str, Any]:
    return sync_connector_command_service(
        args,
        open_db=open_db,
        read_table_file=read_table_file,
        registry_for_table=registry_for_table,
        saved_import_policy=saved_import_policy,
        merge_import_into_table=merge_import_into_table,
        import_csv_as_table=import_csv_as_table,
    )


def preferences_payload(connection: sqlite3.Connection) -> dict[str, Any]:
    return preferences_payload_service(connection)


def preferences_command(args: argparse.Namespace) -> dict[str, Any]:
    return preferences_command_service(args, open_db=open_db)


def theme_palettes_command(args: argparse.Namespace) -> dict[str, Any]:
    return theme_palettes_command_service(args, open_db=open_db)


def build_import_preview(
    connection: sqlite3.Connection,
    file: str | Path,
    table: str | None = None,
    unique_fields_value: str | None = None,
    conflict_rule_value: str | None = None,
) -> dict[str, Any]:
    return build_import_preview_service(
        connection,
        file,
        table,
        unique_fields_value,
        conflict_rule_value,
        read_table_file=read_table_file,
        profile_rows=profile_rows,
        normalize_records_for_columns=normalize_records_for_columns,
        analyze_unique_key_quality=analyze_unique_key_quality,
        active_workspace_id=active_workspace_id,
        saved_import_policy=saved_import_policy,
        table_columns=table_columns,
        registry_for_table=registry_for_table,
        preview_merge_plan=preview_merge_plan,
        sanitize_unique_fields=sanitize_unique_fields,
        quote_identifier=quote_identifier,
        source_pipeline_contract=source_pipeline_contract,
    )


def preview_import_command(args: argparse.Namespace) -> dict[str, Any]:
    result = preview_import_command_service(args, open_db=open_db, build_import_preview=build_import_preview)
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
    result["evidenceBundle"] = write_evidence_bundle(
        command="preview-import",
        workspace_id=workspace_id,
        title=f"Import preview: {result.get('file') or args.file}",
        status="dry-run",
        summary={
            "file": result.get("file"),
            "suggestedTableKey": result.get("suggestedTableKey"),
            "matchCount": len(result.get("matches") or []),
            "mergeMode": result.get("mergePolicyPreview", {}).get("mode") if isinstance(result.get("mergePolicyPreview"), dict) else None,
            "willWrite": result.get("mergePolicyPreview", {}).get("willWrite") if isinstance(result.get("mergePolicyPreview"), dict) else False,
        },
        payload={
            "profile": result.get("profile"),
            "uniqueKeyQuality": result.get("uniqueKeyQuality"),
            "mergePolicyPreview": result.get("mergePolicyPreview"),
            "sourcePipelineContract": result.get("sourcePipelineContract"),
        },
        artifacts=[artifact_ref("source-file", args.file, kind="source")],
    )
    return result


def execute_import_commit(
    connection: sqlite3.Connection,
    file: str | Path,
    table: str | None = None,
    name: str | None = None,
    mode: str = "create",
    unique_fields_value: str | None = None,
    conflict_rule_value: str | None = None,
) -> dict[str, Any]:
    return execute_import_commit_service(
        connection,
        file,
        table,
        name,
        mode,
        unique_fields_value,
        conflict_rule_value,
        build_import_preview=build_import_preview,
        merge_import_into_table=merge_import_into_table,
        import_csv_as_table=import_csv_as_table,
        upsert_navigation_module=upsert_navigation_module,
    )


def import_commit_command(args: argparse.Namespace) -> dict[str, Any]:
    return import_commit_command_service(
        args,
        open_db=open_db,
        build_import_preview=build_import_preview,
        execute_import_commit=execute_import_commit,
    )


def preview_import_folder_command(args: argparse.Namespace) -> dict[str, Any]:
    return preview_import_folder_command_service(args, open_db=open_db, build_import_preview=build_import_preview)


def import_folder_command(args: argparse.Namespace) -> dict[str, Any]:
    return import_folder_command_service(
        args,
        open_db=open_db,
        build_import_preview=build_import_preview,
        execute_import_commit=execute_import_commit,
    )


