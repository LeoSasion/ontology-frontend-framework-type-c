from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable

from bi_cli_schema import (
    active_workspace_id,
    open_db,
    physical_table_for_workspace,
    registry_for_table,
    table_columns,
    table_exists,
    upsert_navigation_module,
)
from config_command_service import (
    apply_config_command as apply_config_command_service,
    config_row_for_export as config_row_for_export_service,
    export_config_command as export_config_command_service,
    export_metadata_config as export_metadata_config_service,
    prepare_config_rows_for_restore as prepare_config_rows_for_restore_service,
    redact_secret_value as redact_secret_value_service,
    restore_config_rows as restore_config_rows_service,
    restore_redacted_value as restore_redacted_value_service,
    validate_config_command as validate_config_command_service,
    validate_metadata_config as validate_metadata_config_service,
)
from connector_command_service import (
    connector_by_key_or_name as connector_by_key_or_name_service,
    connector_row_to_dict as connector_row_to_dict_service,
    load_connectors as load_connectors_service,
    normalize_connector_key as normalize_connector_key_service,
    normalize_connector_status as normalize_connector_status_service,
    normalize_connector_type as normalize_connector_type_service,
    resolve_connector_endpoint as resolve_connector_endpoint_service,
)
from dashboard_widget_contracts import B_WIDGET_TYPES
from import_table_writer_service import (
    create_metrics_for_profile as create_metrics_for_profile_service,
    import_csv_as_table as import_csv_as_table_service,
    merge_import_into_table as merge_import_into_table_service,
    update_table_metadata_after_write as update_table_metadata_after_write_service,
)
from query_runtime import SAFE_AGGREGATIONS

def import_csv_as_table(
    connection: sqlite3.Connection,
    path: Path,
    *,
    table_key: str | None = None,
    display_name: str | None = None,
    mode: str = "create",
    workspace_id: str | None = None,
    stage_key: str | None = None,
) -> dict[str, Any]:
    return import_csv_as_table_service(
        connection,
        path,
        table_key=table_key,
        display_name=display_name,
        mode=mode,
        workspace_id=workspace_id,
        stage_key=stage_key,
        active_workspace_id=active_workspace_id,
        physical_table_for_workspace=physical_table_for_workspace,
        upsert_navigation_module=upsert_navigation_module,
    )


def saved_import_policy(
    connection: sqlite3.Connection,
    table_key: str,
    workspace_id: str | None = None,
) -> dict[str, Any] | None:
    resolved_workspace_id = str(workspace_id or active_workspace_id(connection))
    row = connection.execute(
        "SELECT * FROM import_policies WHERE table_key = ? AND workspace_id = ?",
        (table_key, resolved_workspace_id),
    ).fetchone()
    if not row:
        return None
    return {
        "tableKey": row["table_key"],
        "uniqueFields": json.loads(row["unique_fields_json"]),
        "conflictRule": row["conflict_rule"],
        "updatedAt": row["updated_at"],
    }


def normalize_connector_key(value: str) -> str:
    return normalize_connector_key_service(value)


def normalize_connector_type(value: str | None) -> str:
    return normalize_connector_type_service(value)


def normalize_connector_status(value: str | None) -> str:
    return normalize_connector_status_service(value)


def connector_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return connector_row_to_dict_service(row)


def load_connectors(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    return load_connectors_service(connection)


def connector_by_key_or_name(connection: sqlite3.Connection, value: str) -> sqlite3.Row | None:
    return connector_by_key_or_name_service(connection, value)


def resolve_connector_endpoint(value: str) -> Path:
    return resolve_connector_endpoint_service(value)


def update_table_metadata_after_write(
    connection: sqlite3.Connection,
    *,
    table_key: str,
    display_name: str,
    source_file: str,
    physical_table: str,
    row_count: int,
    column_count: int,
    profile: dict[str, Any],
    mode: str,
    result: dict[str, Any],
    workspace_id: str | None = None,
) -> str:
    return update_table_metadata_after_write_service(
        connection,
        table_key=table_key,
        display_name=display_name,
        source_file=source_file,
        physical_table=physical_table,
        row_count=row_count,
        column_count=column_count,
        profile=profile,
        mode=mode,
        result=result,
        active_workspace_id=active_workspace_id,
        workspace_id=workspace_id,
    )


def merge_import_into_table(
    connection: sqlite3.Connection,
    path: Path,
    *,
    table_key: str,
    unique_fields: list[str],
    conflict_rule: str,
    display_name: str | None = None,
    workspace_id: str | None = None,
    stage_key: str | None = None,
) -> dict[str, Any]:
    return merge_import_into_table_service(
        connection,
        path,
        table_key=table_key,
        unique_fields=unique_fields,
        conflict_rule=conflict_rule,
        display_name=display_name,
        workspace_id=workspace_id,
        stage_key=stage_key,
        registry_for_table=registry_for_table,
        active_workspace_id=active_workspace_id,
    )

def create_metrics_for_profile(connection: sqlite3.Connection, table_key: str, profile: dict[str, Any], workspace_id: str | None = None) -> None:
    create_metrics_for_profile_service(
        connection,
        table_key,
        profile,
        workspace_id=workspace_id or active_workspace_id(connection),
    )


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def parse_json_object(value: Any, default: Any | None = None) -> Any:
    if default is None:
        default = {}
    if isinstance(value, (dict, list)):
        return value
    if value is None:
        return default
    try:
        return json.loads(str(value) or "{}")
    except json.JSONDecodeError:
        return default


def read_json_artifact(path: Path, default: Any | None = None) -> Any:
    if default is None:
        default = {}
    try:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return default


def metric_sql_doctor_from_run(run: dict[str, Any]) -> dict[str, Any]:
    output_dir = Path(str(run.get("output_dir") or ""))
    compiler = read_json_artifact(output_dir / "metric-sql-compiler.json", {"plans": []})
    query_results = read_json_artifact(output_dir / "metric-query-results.json", {"results": []})
    plans = compiler.get("plans") if isinstance(compiler, dict) else []
    results = query_results.get("results") if isinstance(query_results, dict) else []
    plan_items = [item for item in plans if isinstance(item, dict)]
    result_items = [item for item in results if isinstance(item, dict)]
    result_by_id = {str(item.get("analysisId")): item for item in result_items if item.get("analysisId")}

    status_counts: dict[str, int] = {}
    missing_semantics: dict[str, int] = {}
    missing_real_semantics: dict[str, int] = {}
    failed_samples: list[dict[str, Any]] = []
    executable_samples: list[dict[str, Any]] = []
    for plan in plan_items:
        analysis_id = str(plan.get("analysisId") or "")
        result = result_by_id.get(analysis_id, {})
        status = str(result.get("status") or plan.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
        for semantic in plan.get("missingSemantics") or []:
            key = str(semantic)
            missing_semantics[key] = missing_semantics.get(key, 0) + 1
        for semantic in plan.get("missingRealSemantics") or []:
            key = str(semantic)
            missing_real_semantics[key] = missing_real_semantics.get(key, 0) + 1
        sample = {
            "analysisId": analysis_id,
            "label": plan.get("label") or result.get("label") or analysis_id,
            "status": status,
            "sourceMode": plan.get("sourceMode"),
            "requiredSemantics": plan.get("requiredSemantics") or [],
            "missingSemantics": plan.get("missingSemantics") or [],
            "missingRealSemantics": plan.get("missingRealSemantics") or [],
            "weakOrMissingRelationships": plan.get("weakOrMissingRelationships") or [],
            "reason": result.get("reason") or result.get("error") or plan.get("agentInstruction") or "",
            "agentInstruction": plan.get("agentInstruction") or "",
        }
        if plan.get("executable") and status in {"executed", "empty_result"}:
            if len(executable_samples) < 5:
                executable_samples.append({
                    "analysisId": analysis_id,
                    "label": sample["label"],
                    "status": status,
                    "rowCount": result.get("rowCount") or 0,
                    "sourceMode": plan.get("sourceMode"),
                })
        elif len(failed_samples) < 8:
            failed_samples.append(sample)

    missing_semantic_items = [
        {"semantic": semantic, "count": count}
        for semantic, count in sorted(missing_semantics.items(), key=lambda item: (-item[1], item[0]))
    ][:8]
    missing_real_semantic_items = [
        {"semantic": semantic, "count": count}
        for semantic, count in sorted(missing_real_semantics.items(), key=lambda item: (-item[1], item[0]))
    ][:8]
    semantic_binding_drafts = [
        {
            "semantic": item["semantic"],
            "impactCount": item["count"],
            "status": "needs-field-confirmation",
            "dryRun": True,
            "actionType": "confirm-field-semantic",
            "note": "仅生成确认草案，不写入字段配置或指标 SQL。",
        }
        for item in missing_semantic_items[:6]
    ]
    planned = len(plan_items) or int(run.get("metric_sql_plan_count") or 0)
    executable = len([item for item in plan_items if item.get("executable")]) or int(run.get("metric_sql_executable_count") or 0)
    blocked = max(0, planned - executable)
    repair_draft = {
        "kind": "metric-sql.repair",
        "dryRun": True,
        "title": "指标 SQL 修复草案",
        "summary": (
            f"{blocked} 个指标问题缺少可执行 SQL；优先确认 "
            f"{'、'.join(item['semantic'] for item in missing_semantic_items[:3]) or '字段语义'}。"
        ),
        "steps": [
            "确认缺失语义对应的真实字段，不直接覆盖原表。",
            "补齐字段语义后重新运行 Source Intelligence。",
            "只把可执行 SQL 推入看板候选，未执行问题继续留在证据缺口中。",
        ],
        "semanticBindingDrafts": semantic_binding_drafts,
        "confirmRequired": True,
        "safeCommand": "python tools/aibi_cli.py --json source-intelligence <source-path> --label repair-metric-sql",
    }
    return {
        "artifactDir": str(output_dir) if str(output_dir) else "",
        "compilerArtifact": "metric-sql-compiler.json",
        "queryResultArtifact": "metric-query-results.json",
        "planned": planned,
        "executable": executable,
        "blocked": blocked,
        "rate": executable / max(1, planned),
        "statusCounts": status_counts,
        "missingSemantics": missing_semantic_items,
        "missingRealSemantics": missing_real_semantic_items,
        "semanticBindingDrafts": semantic_binding_drafts,
        "failedSamples": failed_samples,
        "executableSamples": executable_samples,
        "repairDraft": repair_draft,
    }


def json_contains_string(value: Any, needle: str) -> bool:
    if not needle:
        return False
    if isinstance(value, str):
        return value == needle
    if isinstance(value, dict):
        return any(json_contains_string(item, needle) for item in value.values())
    if isinstance(value, list):
        return any(json_contains_string(item, needle) for item in value)
    return False


def calculated_field_names_for_table(connection: sqlite3.Connection, table_key: str) -> set[str]:
    if not table_exists(connection, "calculated_fields"):
        return set()
    rows = connection.execute(
        "SELECT name FROM calculated_fields WHERE table_key = ? AND mode = 'row' AND enabled = 1",
        (table_key,),
    ).fetchall()
    return {str(row["name"]) for row in rows if str(row["name"] or "")}


def analysis_columns_for_table(connection: sqlite3.Connection, table_key: str) -> set[str]:
    registry = registry_for_table(connection, table_key)
    if not registry:
        return set()
    return set(table_columns(connection, registry["physical_table"])) | calculated_field_names_for_table(connection, table_key)


def redact_secret_value(value: Any) -> Any:
    return redact_secret_value_service(value)


def restore_redacted_value(imported: Any, existing: Any) -> Any:
    return restore_redacted_value_service(imported, existing)


def config_row_for_export(table_name: str, row: sqlite3.Row) -> dict[str, Any]:
    return config_row_for_export_service(table_name, row)


def prepare_config_rows_for_restore(connection: sqlite3.Connection, table_name: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return prepare_config_rows_for_restore_service(connection, table_name, rows)


def export_metadata_config(connection: sqlite3.Connection) -> dict[str, Any]:
    return export_metadata_config_service(connection)


def restore_config_rows(connection: sqlite3.Connection, table_name: str, rows: list[dict[str, Any]]) -> int:
    return restore_config_rows_service(connection, table_name, rows)


def validate_metadata_config(connection: sqlite3.Connection) -> tuple[list[str], list[str]]:
    return validate_metadata_config_service(
        connection,
        calculated_field_names_for_table=calculated_field_names_for_table,
        safe_aggregations=SAFE_AGGREGATIONS,
        widget_types=B_WIDGET_TYPES,
    )


def validate_config_command(args: argparse.Namespace) -> dict[str, Any]:
    return validate_config_command_service(
        args,
        open_db=open_db,
        calculated_field_names_for_table=calculated_field_names_for_table,
        safe_aggregations=SAFE_AGGREGATIONS,
        widget_types=B_WIDGET_TYPES,
    )


def export_config_command(args: argparse.Namespace) -> dict[str, Any]:
    return export_config_command_service(args, open_db=open_db)


def apply_config_command(args: argparse.Namespace) -> dict[str, Any]:
    return apply_config_command_service(
        args,
        open_db=open_db,
        calculated_field_names_for_table=calculated_field_names_for_table,
        safe_aggregations=SAFE_AGGREGATIONS,
        widget_types=B_WIDGET_TYPES,
    )


