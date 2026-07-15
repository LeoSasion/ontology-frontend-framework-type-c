from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable

from bi_cli_core import DB_PATH, DEFAULT_DATA_DIR, ROOT, now_iso, quote_identifier
from bi_cli_schema import table_exists
from preferences_theme_command_service import list_theme_palettes, load_user_preferences


CONFIG_TABLES = [
    "navigation_modules",
    "field_semantics",
    "metric_definitions",
    "calculated_fields",
    "relationships",
    "dashboards",
    "dashboard_widgets",
    "saved_views",
    "import_policies",
    "data_connectors",
    "user_preferences",
    "theme_palettes",
    "analytical_skills",
    "workspace_analytical_skills",
    "workspace_domain_packs",
    "workspace_agent_runtime_profiles",
    "action_drafts",
]

CONFIG_KIND = "aibi-hybrid-local-bi-config"


def table_columns(connection: sqlite3.Connection, physical_table: str) -> list[str]:
    return [row["name"] for row in connection.execute(f"PRAGMA table_info({quote_identifier(physical_table)})")]


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


def redact_secret_value(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            lower_key = str(key).lower()
            if any(token in lower_key for token in ("secret", "password", "token", "api_key", "apikey", "accesskey", "credential")):
                redacted[key] = "__AIBI_REDACTED__" if item else item
            else:
                redacted[key] = redact_secret_value(item)
        return redacted
    if isinstance(value, list):
        return [redact_secret_value(item) for item in value]
    return value


def restore_redacted_value(imported: Any, existing: Any) -> Any:
    if imported == "__AIBI_REDACTED__":
        return existing
    if isinstance(imported, dict) and isinstance(existing, dict):
        return {key: restore_redacted_value(value, existing.get(key)) for key, value in imported.items()}
    if isinstance(imported, list) and isinstance(existing, list):
        return [restore_redacted_value(value, existing[index] if index < len(existing) else None) for index, value in enumerate(imported)]
    return imported


def config_row_for_export(table_name: str, row: sqlite3.Row) -> dict[str, Any]:
    payload = dict(row)
    if table_name == "data_connectors":
        for column in ("config_json", "schedule_json", "last_sync_result_json"):
            if column in payload and payload[column]:
                payload[column] = json.dumps(redact_secret_value(parse_json_object(payload[column])), ensure_ascii=False, separators=(",", ":"))
    return payload


def prepare_config_rows_for_restore(connection: sqlite3.Connection, table_name: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if table_name != "data_connectors" or not rows or not table_exists(connection, table_name):
        return rows
    existing_rows = connection.execute(
        "SELECT workspace_id, connector_key, config_json, schedule_json, last_sync_result_json FROM data_connectors"
    ).fetchall()
    existing_by_key = {
        (str(row["workspace_id"]), str(row["connector_key"])): dict(row)
        for row in existing_rows
    }
    prepared: list[dict[str, Any]] = []
    for row in rows:
        next_row = dict(row)
        existing = existing_by_key.get(
            (
                str(next_row.get("workspace_id") or "default"),
                str(next_row.get("connector_key") or ""),
            ),
            {},
        )
        for column in ("config_json", "schedule_json", "last_sync_result_json"):
            if column not in next_row:
                continue
            imported_payload = parse_json_object(next_row.get(column))
            existing_payload = parse_json_object(existing.get(column))
            next_row[column] = json.dumps(restore_redacted_value(imported_payload, existing_payload), ensure_ascii=False, separators=(",", ":"))
        prepared.append(next_row)
    return prepared


def export_metadata_config(connection: sqlite3.Connection) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schemaVersion": 1,
        "kind": CONFIG_KIND,
        "exportedAt": now_iso(),
        "source": "workspace metadata export model",
        "businessDataIncluded": False,
        "tables": {},
    }
    for table_name in CONFIG_TABLES:
        if not table_exists(connection, table_name):
            payload["tables"][table_name] = []
            continue
        rows = connection.execute(f"SELECT * FROM {quote_identifier(table_name)}").fetchall()
        payload["tables"][table_name] = [config_row_for_export(table_name, row) for row in rows]
    return payload


def restore_config_rows(connection: sqlite3.Connection, table_name: str, rows: list[dict[str, Any]]) -> int:
    if table_name not in CONFIG_TABLES:
        raise ValueError(f"Unsupported config table: {table_name}")
    if not table_exists(connection, table_name):
        raise ValueError(f"Missing config table: {table_name}")
    rows = prepare_config_rows_for_restore(connection, table_name, rows)
    connection.execute(f"DELETE FROM {quote_identifier(table_name)}")
    if not rows:
        return 0
    columns = table_columns(connection, table_name)
    insert_columns = [column for column in columns if any(column in row for row in rows)]
    if not insert_columns:
        return 0
    sql = (
        f"INSERT INTO {quote_identifier(table_name)} "
        f"({', '.join(quote_identifier(column) for column in insert_columns)}) "
        f"VALUES ({', '.join('?' for _ in insert_columns)})"
    )
    connection.executemany(sql, [[row.get(column) for column in insert_columns] for row in rows])
    return len(rows)


def validate_metadata_config(
    connection: sqlite3.Connection,
    *,
    calculated_field_names_for_table: Callable[[sqlite3.Connection, str], set[str]],
    safe_aggregations: Iterable[str],
    widget_types: Iterable[str],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    safe_aggregation_set = set(safe_aggregations)
    widget_type_set = set(widget_types)
    for table_name in CONFIG_TABLES:
        if not table_exists(connection, table_name):
            errors.append(f"Missing config table: {table_name}")

    registry = {row["table_key"]: dict(row) for row in connection.execute("SELECT table_key, physical_table FROM table_registry").fetchall()}
    dashboard_keys_for_navigation = {
        (row["workspace_id"], row["dashboard_key"])
        for row in connection.execute("SELECT workspace_id, dashboard_key FROM dashboards").fetchall()
    }
    column_cache: dict[str, set[str]] = {}

    def columns_for(table_key: str) -> set[str]:
        if table_key in column_cache:
            return column_cache[table_key]
        row = registry.get(table_key)
        if not row:
            column_cache[table_key] = set()
            return set()
        column_cache[table_key] = set(table_columns(connection, row["physical_table"])) | calculated_field_names_for_table(connection, table_key)
        return column_cache[table_key]

    for row in connection.execute("SELECT table_key, field_name FROM field_semantics").fetchall():
        table_key = str(row["table_key"])
        field_name = str(row["field_name"])
        if table_key not in registry:
            errors.append(f"Field config references missing table: {table_key}.{field_name}")
        elif field_name not in columns_for(table_key):
            errors.append(f"Field config references missing field: {table_key}.{field_name}")

    for row in connection.execute("SELECT module_key, workspace_id, module_type, table_key, dashboard_key FROM navigation_modules WHERE enabled = 1").fetchall():
        module_key = str(row["module_key"])
        module_type = str(row["module_type"])
        if module_type == "table" and str(row["table_key"] or "") not in registry:
            errors.append(f"Navigation module references missing table: {module_key} -> {row['table_key']}")
        elif module_type == "dashboard" and (str(row["workspace_id"]), str(row["dashboard_key"] or "")) not in dashboard_keys_for_navigation:
            errors.append(f"Navigation module references missing dashboard: {module_key} -> {row['dashboard_key']}")
        elif module_type not in {"table", "dashboard", "view"}:
            warnings.append(f"Navigation module type is not standard: {module_key} -> {module_type}")

    for row in connection.execute("SELECT metric_key, table_key, measure, dimension, time_field, aggregation FROM metric_definitions").fetchall():
        metric_key = str(row["metric_key"])
        table_key = str(row["table_key"])
        columns = columns_for(table_key)
        if table_key not in registry:
            errors.append(f"Metric references missing table: {metric_key} -> {table_key}")
            continue
        if row["aggregation"] not in safe_aggregation_set and row["aggregation"] != "formula":
            errors.append(f"Metric uses unsupported aggregation: {metric_key} -> {row['aggregation']}")
        for field in (row["measure"], row["dimension"], row["time_field"]):
            field_text = str(field or "")
            if field_text and field_text != "*" and field_text not in columns:
                errors.append(f"Metric references missing field: {metric_key}.{field_text}")

    for row in connection.execute("SELECT field_key, table_key, dependencies_json FROM calculated_fields").fetchall():
        field_key = str(row["field_key"])
        table_key = str(row["table_key"])
        if table_key not in registry:
            errors.append(f"Formula references missing table: {field_key} -> {table_key}")
            continue
        columns = columns_for(table_key)
        for field in parse_json_object(row["dependencies_json"], []):
            if field not in columns:
                errors.append(f"Formula references missing field: {field_key}.{field}")

    for row in connection.execute("SELECT relation_key, left_table_key, right_table_key, left_field, right_field, join_type FROM relationships").fetchall():
        relation_key = str(row["relation_key"])
        if row["join_type"] not in {"left", "inner", "lookup"}:
            errors.append(f"Relationship uses unsupported join type: {relation_key} -> {row['join_type']}")
        for side, table_key, field in (("left", row["left_table_key"], row["left_field"]), ("right", row["right_table_key"], row["right_field"])):
            table_key = str(table_key)
            field = str(field)
            if table_key not in registry:
                errors.append(f"Relationship {side} table missing: {relation_key} -> {table_key}")
            elif field not in columns_for(table_key):
                errors.append(f"Relationship {side} field missing: {relation_key}.{field}")

    dashboard_keys = {
        (row["workspace_id"], row["dashboard_key"])
        for row in connection.execute("SELECT workspace_id, dashboard_key FROM dashboards").fetchall()
    }
    view_keys = {row["view_key"] for row in connection.execute("SELECT view_key FROM saved_views").fetchall()}
    relation_keys = {row["relation_key"] for row in connection.execute("SELECT relation_key FROM relationships").fetchall()}

    for row in connection.execute("SELECT dashboard_key, default_table_key FROM dashboards").fetchall():
        table_key = str(row["default_table_key"] or "")
        if table_key and table_key not in registry:
            errors.append(f"Dashboard default table missing: {row['dashboard_key']} -> {table_key}")

    for row in connection.execute("SELECT view_key, table_key, config_json FROM saved_views").fetchall():
        view_key = str(row["view_key"])
        table_key = str(row["table_key"])
        if table_key not in registry:
            errors.append(f"View references missing table: {view_key} -> {table_key}")
            continue
        columns = columns_for(table_key)
        config = parse_json_object(row["config_json"])
        for column in config.get("columns") or []:
            if str(column) not in columns:
                errors.append(f"View references missing column: {view_key}.{column}")
        for item in (config.get("filters") or []) + (config.get("sort") or []):
            if isinstance(item, dict):
                field = str(item.get("field") or "")
                if field and field not in columns:
                    errors.append(f"View references missing filter/sort field: {view_key}.{field}")

    for row in connection.execute("SELECT widget_key, workspace_id, dashboard_key, widget_type, table_key, config_json FROM dashboard_widgets").fetchall():
        widget_key = str(row["widget_key"])
        workspace_id = str(row["workspace_id"])
        dashboard_key = str(row["dashboard_key"])
        table_key = str(row["table_key"] or "")
        config = parse_json_object(row["config_json"])
        if (workspace_id, dashboard_key) not in dashboard_keys:
            errors.append(f"Widget references missing dashboard: {widget_key} -> {dashboard_key}")
        if row["widget_type"] not in widget_type_set:
            errors.append(f"Widget type unsupported: {widget_key} -> {row['widget_type']}")
        data_mode = str(config.get("dataMode") or ("view" if config.get("viewKey") else "table"))
        if data_mode == "view":
            view_key = str(config.get("viewKey") or "")
            if view_key and view_key not in view_keys:
                errors.append(f"Widget references missing view: {widget_key} -> {view_key}")
        elif data_mode == "relationship":
            relation_key = str((config.get("relationship") or {}).get("relationKey") or "")
            if relation_key and relation_key not in relation_keys:
                errors.append(f"Widget references missing relationship: {widget_key} -> {relation_key}")
        elif table_key and table_key not in registry:
            errors.append(f"Widget references missing table: {widget_key} -> {table_key}")
        if table_key and table_key in registry:
            columns = columns_for(table_key)
            for field in (config.get("dimension"), config.get("measure")):
                field_text = str(field or "")
                if field_text and field_text != "*" and field_text not in columns:
                    errors.append(f"Widget references missing field: {widget_key}.{field_text}")

    for row in connection.execute("SELECT table_key, unique_fields_json FROM import_policies").fetchall():
        table_key = str(row["table_key"])
        if table_key not in registry:
            errors.append(f"Import policy references missing table: {table_key}")
            continue
        for field in parse_json_object(row["unique_fields_json"], []):
            if str(field) not in columns_for(table_key):
                errors.append(f"Import policy references missing unique field: {table_key}.{field}")

    for row in connection.execute("SELECT connector_key, config_json FROM data_connectors").fetchall():
        config = parse_json_object(row["config_json"])
        target_table = str(config.get("targetTableKey") or "")
        if target_table and target_table not in registry:
            warnings.append(f"Connector target table not imported yet: {row['connector_key']} -> {target_table}")

    preferences = load_user_preferences(connection)
    theme_keys = {theme["themeKey"] for theme in list_theme_palettes(connection)}
    if preferences.get("themeKey") not in theme_keys:
        warnings.append(f"Active theme is missing or disabled: {preferences.get('themeKey')}")

    return errors, warnings


def validate_config_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    calculated_field_names_for_table: Callable[[sqlite3.Connection, str], set[str]],
    safe_aggregations: Iterable[str],
    widget_types: Iterable[str],
) -> dict[str, Any]:
    with open_db() as connection:
        errors, warnings = validate_metadata_config(
            connection,
            calculated_field_names_for_table=calculated_field_names_for_table,
            safe_aggregations=safe_aggregations,
            widget_types=widget_types,
        )
        table_counts = {
            table_name: connection.execute(f"SELECT COUNT(*) FROM {quote_identifier(table_name)}").fetchone()[0]
            for table_name in CONFIG_TABLES
            if table_exists(connection, table_name)
        }
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "tableCounts": table_counts,
        "source": "workspace metadata validation model",
    }


def export_config_command(args: argparse.Namespace, *, open_db: Callable[[], Any]) -> dict[str, Any]:
    with open_db() as connection:
        payload = export_metadata_config(connection)
    output = Path(args.output) if args.output else DEFAULT_DATA_DIR / "config_exports" / f"aibi_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    if not output.is_absolute():
        output = ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "exported": str(output),
        "kind": payload["kind"],
        "businessDataIncluded": False,
        "tables": {table_name: len(rows) for table_name, rows in payload["tables"].items()},
        "redaction": "connector secret-like values are replaced with __AIBI_REDACTED__",
    }


def apply_config_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    calculated_field_names_for_table: Callable[[sqlite3.Connection, str], set[str]],
    safe_aggregations: Iterable[str],
    widget_types: Iterable[str],
) -> dict[str, Any]:
    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("tables"), dict):
        raise ValueError("Invalid config file: missing tables object.")
    unknown_tables = sorted(set(payload["tables"].keys()) - set(CONFIG_TABLES))
    restore_plan: dict[str, int] = {}
    for table_name in CONFIG_TABLES:
        rows = payload["tables"].get(table_name, [])
        if not isinstance(rows, list):
            raise ValueError(f"Config table payload must be a list: {table_name}")
        restore_plan[table_name] = len(rows)
    if not args.yes:
        return {
            "ok": True,
            "dryRun": True,
            "requiresConfirmation": True,
            "input": str(input_path),
            "restorePlan": restore_plan,
            "unknownTablesIgnored": unknown_tables,
            "message": "Applying config overwrites metadata config tables only; business data tables are not imported.",
        }

    backup_path = DB_PATH.with_suffix(DB_PATH.suffix + f".bak_config_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    backup_created = False
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        shutil.copy2(DB_PATH, backup_path)
        backup_created = True
    restored: dict[str, int] = {}
    with open_db() as connection:
        try:
            connection.execute("BEGIN")
            for table_name in CONFIG_TABLES:
                restored[table_name] = restore_config_rows(connection, table_name, payload["tables"].get(table_name, []))
            errors, warnings = validate_metadata_config(
                connection,
                calculated_field_names_for_table=calculated_field_names_for_table,
                safe_aggregations=safe_aggregations,
                widget_types=widget_types,
            )
            if errors:
                raise ValueError("Restored config failed validation: " + "; ".join(errors[:5]))
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return {
        "ok": True,
        "confirmed": True,
        "input": str(input_path),
        "backup": str(backup_path) if backup_created else None,
        "restored": restored,
        "unknownTablesIgnored": unknown_tables,
        "warnings": warnings,
    }
