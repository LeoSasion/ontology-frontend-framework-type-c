from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import zipfile
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree

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

def read_csv(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]
        return list(reader.fieldnames or []), rows


def read_xlsx(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    with zipfile.ZipFile(path) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            shared_root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            for item in shared_root.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"):
                shared_strings.append(item.text or "")
        sheet_name = next(name for name in archive.namelist() if name.startswith("xl/worksheets/sheet"))
        root = ElementTree.fromstring(archive.read(sheet_name))
        ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        raw_rows: list[list[str]] = []
        for row in root.findall(f".//{ns}row"):
            values: list[str] = []
            current_col = 0
            for cell in row.findall(f"{ns}c"):
                ref = cell.attrib.get("r", "")
                col_letters = re.sub(r"\d+", "", ref)
                if col_letters:
                    target_col = 0
                    for char in col_letters:
                        target_col = target_col * 26 + (ord(char.upper()) - 64)
                    while current_col < target_col - 1:
                        values.append("")
                        current_col += 1
                value_node = cell.find(f"{ns}v")
                text = value_node.text if value_node is not None else ""
                if cell.attrib.get("t") == "s" and text.isdigit():
                    text = shared_strings[int(text)] if int(text) < len(shared_strings) else text
                values.append(text or "")
                current_col += 1
            raw_rows.append(values)
    headers = [value.strip() or f"column_{index + 1}" for index, value in enumerate(raw_rows[0])] if raw_rows else []
    rows = [dict(zip(headers, row + [""] * max(0, len(headers) - len(row)))) for row in raw_rows[1:]]
    return headers, rows


def read_table_file(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    if path.suffix.lower() == ".csv":
        return read_csv(path)
    if path.suffix.lower() in {".xlsx", ".xlsm"}:
        return read_xlsx(path)
    raise ValueError(f"Unsupported source file: {path}")


def coerce_value(value: Any) -> Any:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    numeric = text.replace(",", "")
    try:
        if re.match(r"^-?\d+(\.\d+)?$", numeric):
            return float(numeric) if "." in numeric else int(numeric)
    except ValueError:
        pass
    return text


def infer_role(field: str, sample_values: Iterable[Any]) -> tuple[str, str, float]:
    name = field.lower()
    values = [str(value).strip() for value in sample_values if str(value).strip()]
    numeric_count = 0
    for value in values[:30]:
        try:
            float(value.replace(",", ""))
            numeric_count += 1
        except ValueError:
            continue
    if "date" in name or "time" in name or "日期" in field or "时间" in field:
        return "event_time", "filterable", 0.91
    if "id" in name or "编号" in field or field.endswith("号"):
        return "identity_key", "joinable", 0.86
    if any(token in name for token in ["amount", "sales", "revenue", "cost", "quantity"]) or any(token in field for token in ["金额", "销售", "收入", "成本", "数量"]):
        return "measure", "aggregatable", 0.88
    if "status" in name or "状态" in field:
        return "status", "filterable", 0.84
    if values and numeric_count / max(1, len(values[:30])) > 0.8:
        return "measure", "aggregatable", 0.78
    return "dimension", "groupable", 0.74


def profile_rows(headers: list[str], rows: list[dict[str, Any]]) -> dict[str, Any]:
    fields = []
    for field in headers:
        values = [row.get(field, "") for row in rows]
        role, usage, confidence = infer_role(field, values)
        non_empty = sum(1 for value in values if str(value).strip())
        unique_count = len({str(value).strip() for value in values if str(value).strip()})
        fields.append(
            {
                "field": field,
                "role": role,
                "usage": usage,
                "confidence": confidence,
                "nonEmpty": non_empty,
                "uniqueCount": unique_count,
                "sampleValues": [str(value) for value in values[:5]],
            }
        )
    measures = [field["field"] for field in fields if field["role"] == "measure"]
    dimensions = [field["field"] for field in fields if field["role"] in {"dimension", "status"}]
    identity_keys = [field["field"] for field in fields if field["role"] == "identity_key"]
    return {
        "rowCount": len(rows),
        "columnCount": len(headers),
        "fields": fields,
        "measures": measures,
        "dimensions": dimensions,
        "identityKeys": identity_keys,
        "warnings": [] if rows else ["Source has no data rows."],
    }


def import_csv_as_table(
    connection: sqlite3.Connection,
    path: Path,
    *,
    table_key: str | None = None,
    display_name: str | None = None,
    mode: str = "create",
) -> dict[str, Any]:
    return import_csv_as_table_service(
        connection,
        path,
        table_key=table_key,
        display_name=display_name,
        mode=mode,
        read_table_file=read_table_file,
        profile_rows=profile_rows,
        active_workspace_id=active_workspace_id,
        physical_table_for_workspace=physical_table_for_workspace,
        upsert_navigation_module=upsert_navigation_module,
    )


def saved_import_policy(connection: sqlite3.Connection, table_key: str) -> dict[str, Any] | None:
    workspace_id = active_workspace_id(connection)
    row = connection.execute(
        "SELECT * FROM import_policies WHERE table_key = ? AND workspace_id = ?",
        (table_key, workspace_id),
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
    )


def merge_import_into_table(
    connection: sqlite3.Connection,
    path: Path,
    *,
    table_key: str,
    unique_fields: list[str],
    conflict_rule: str,
    display_name: str | None = None,
) -> dict[str, Any]:
    return merge_import_into_table_service(
        connection,
        path,
        table_key=table_key,
        unique_fields=unique_fields,
        conflict_rule=conflict_rule,
        display_name=display_name,
        registry_for_table=registry_for_table,
        read_table_file=read_table_file,
        table_columns=table_columns,
        profile_rows=profile_rows,
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
        "safeCommand": "python tools/bi_cli.py --json source-intelligence <source-path> --label repair-metric-sql",
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


