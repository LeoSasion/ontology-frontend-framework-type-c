#!/usr/bin/env python
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
import sys
import time
import zipfile
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree

from aibi_contracts import domain_pack_runtime as build_domain_pack_runtime
from aibi_contracts import source_pipeline_contract as build_source_pipeline_contract
from agent_action_confirmations import (
    confirm_dry_run_response,
    confirmed_response,
    reject_dry_run_response,
    rejected_response,
)
from agent_action_draft_store import action_draft_payload, count_pending_action_drafts, create_action_draft, get_action_draft, list_action_drafts, mark_action_confirmed, mark_action_rejected
from agent_confirm_execution_handlers import (
    handle_dashboard_create_confirmation,
    handle_dashboard_filter_add_confirmation,
    handle_dashboard_operation_confirmation,
    handle_dashboard_widget_add_confirmation,
    handle_formula_save_confirmation,
    handle_import_commit_confirmation,
    handle_index_create_confirmation,
    handle_metric_add_confirmation,
    handle_relationship_save_confirmation,
    handle_semantic_set_confirmation,
    handle_view_save_confirmation,
)
from agent_prompt_resolution import (
    agent_action_evidence,
    agent_action_kind,
    agent_action_label,
    build_agent_action_payload,
    dashboard_operation_from_prompt,
    resolve_agent_prompt_intents,
    select_agent_table,
    should_create_agent_draft,
)
from agent_recommended_commands import build_agent_recommended_commands
from bi_cli_core import (
    B_PROJECT_ROOT,
    DB_PATH,
    DUCKDB_PATH,
    ROOT,
    dump,
    now_iso,
    parse_csv_list,
    quote_identifier,
    quote_relationship_identifier,
    slug,
    source_label,
    unique_key,
)
from bi_cli_contracts import build_cli_contract, command_contract_by_name, contract_to_markdown, filter_commands
from bi_cli_envelope import enrich_cli_output, error_output
from bi_cli_evidence_bundles import artifact_ref, write_evidence_bundle
from business_dashboard_service import (
    build_agent_dashboard_create_draft as build_agent_dashboard_create_draft_service,
    build_business_analysis_templates as build_business_analysis_templates_service,
    build_business_dashboard_payload as build_business_dashboard_payload_service,
    run_business_dashboard_command as run_business_dashboard_command_service,
    source_profile_table_inputs,
    table_template_fields as table_template_fields_service,
    template_widget_layout as template_widget_layout_service,
    write_business_dashboard as write_business_dashboard_service,
)
from connector_command_service import (
    VALID_CONNECTOR_STATUSES,
    VALID_CONNECTOR_TYPES,
    connector_by_key_or_name as connector_by_key_or_name_service,
    connector_row_to_dict as connector_row_to_dict_service,
    list_connectors_command as list_connectors_command_service,
    load_connectors as load_connectors_service,
    normalize_connector_key as normalize_connector_key_service,
    normalize_connector_status as normalize_connector_status_service,
    normalize_connector_type as normalize_connector_type_service,
    remove_connector_command as remove_connector_command_service,
    resolve_connector_endpoint as resolve_connector_endpoint_service,
    save_connector_command as save_connector_command_service,
    sync_connector_command as sync_connector_command_service,
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
from dashboard_widget_contracts import (
    B_BAR_ORIENTATIONS,
    B_COLOR_PALETTES,
    B_DASHBOARD_FILTER_OPERATORS,
    B_PIE_SHAPES,
    B_RANKING_MODES,
    B_RELATIONSHIP_WIDGET_TYPES,
    B_SLICER_DISPLAYS,
    B_SORT_BY,
    B_VALUE_FORMATS,
    B_WIDGET_TYPES,
    build_dashboard_widget_catalog_payload,
    widget_style_options_from_args,
)
from dashboard_module_orchestration import dashboard_module_widget_from_payload
from dashboard_save_transactions import dashboard_snapshot, save_dashboard_with_widgets
from dashboard_widget_command_service import (
    add_dashboard_relationship_widget as add_dashboard_relationship_widget_service,
    add_dashboard_widget as add_dashboard_widget_service,
    add_recommended_dashboard_widgets as add_recommended_dashboard_widgets_service,
    copy_dashboard_widget as copy_dashboard_widget_service,
    remove_dashboard_widget as remove_dashboard_widget_service,
    set_dashboard_widget as set_dashboard_widget_service,
)
from dashboard_widget_operations import (
    insert_dashboard_widget,
    next_dashboard_widget_sort_order,
    resolve_dashboard_widget_key,
)
from dashboard_widget_proposal_service import (
    build_dashboard_relationship_widget_proposal as build_dashboard_relationship_widget_proposal_service,
    build_dashboard_widget_proposal as build_dashboard_widget_proposal_service,
)
from erp_dashboard_unit_library import (
    ERP_UNIT_LIBRARY_TEMPLATE_KEY,
    build_erp_dashboard_unit_templates,
    build_erp_unit_library_catalog_payload,
)
from formula_engine import FormulaError, ast_dependencies, ast_to_sql, parse_and_validate_formula
from import_policy import (
    analyze_unique_key_quality,
    existing_rows_by_unique_key,
    normalize_records_for_columns,
    preview_merge_plan,
    record_unique_key,
    sanitize_unique_fields,
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
from import_table_writer_service import (
    create_metrics_for_profile as create_metrics_for_profile_service,
    import_csv_as_table as import_csv_as_table_service,
    merge_import_into_table as merge_import_into_table_service,
    update_table_metadata_after_write as update_table_metadata_after_write_service,
)
from metric_formula_command_service import (
    add_metric_command as add_metric_command_service,
    build_formula_metric_query as build_formula_metric_query_service,
    build_formula_save_plan as build_formula_save_plan_service,
    build_metric_add_plan as build_metric_add_plan_service,
    calculated_field_row_to_payload as calculated_field_row_to_payload_service,
    calculated_field_usage as calculated_field_usage_service,
    delete_formula_command as delete_formula_command_service,
    execute_formula_save_plan as execute_formula_save_plan_service,
    formula_key_for as formula_key_for_service,
    formula_preview_command as formula_preview_command_service,
    metric_filters_from_cli as metric_filters_from_cli_service,
    metric_key_for as metric_key_for_service,
    metric_row_to_payload as metric_row_to_payload_service,
    query_metric_command as query_metric_command_service,
    save_formula_command as save_formula_command_service,
    upsert_metric_definition as upsert_metric_definition_service,
    compile_formula_for_table as compile_formula_for_table_service,
)
from preferences_theme_command_service import (
    delete_theme_palette as delete_theme_palette_service,
    ensure_default_preferences_and_themes as ensure_default_preferences_and_themes_service,
    list_theme_palettes as list_theme_palettes_service,
    load_user_preferences as load_user_preferences_service,
    normalize_theme_palette as normalize_theme_palette_service,
    normalize_theme_tokens as normalize_theme_tokens_service,
    normalize_user_preferences as normalize_user_preferences_service,
    preferences_command as preferences_command_service,
    preferences_payload as preferences_payload_service,
    save_user_preferences as save_user_preferences_service,
    theme_palettes_command as theme_palettes_command_service,
    upsert_theme_palette as upsert_theme_palette_service,
    validate_theme_palette_payload as validate_theme_palette_payload_service,
)
from query_runtime import (
    DuckDBUnavailable,
    duckdb_status,
    run_duckdb_aggregate_query,
    run_sqlite_aggregate_query,
    sync_table_to_duckdb,
)
from relationship_command_service import (
    build_relationship_save_plan as build_relationship_save_plan_service,
    execute_relationship_save as execute_relationship_save_service,
    list_relationships_command as list_relationships_command_service,
    normalize_relation_field_name as normalize_relation_field_name_service,
    parse_relationship_filter as parse_relationship_filter_service,
    query_relationship_command as query_relationship_command_service,
    recommend_relationships_command as recommend_relationships_command_service,
    recommend_relationships_for_connection as recommend_relationships_for_connection_service,
    relation_candidate_fields as relation_candidate_fields_service,
    relationship_preview_command as relationship_preview_command_service,
    relationship_name_score as relationship_name_score_service,
    relationship_rows_for_chart as relationship_rows_for_chart_service,
    relationship_save_command as relationship_save_command_service,
    remove_relationship_command as remove_relationship_command_service,
    resolve_relationship_query_inputs as resolve_relationship_query_inputs_service,
    sample_field_values as sample_field_values_service,
    saved_relationship_signatures as saved_relationship_signatures_service,
    to_number as relationship_to_number_service,
)
from relationship_tools import build_relationship_preview, build_relationship_query, parse_relationship_field_ref
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
from saved_view_query_service import (
    build_save_view_plan as build_save_view_plan_service,
    copy_view_command as copy_view_command_service,
    delete_view_command as delete_view_command_service,
    execute_save_view_plan as execute_save_view_plan_service,
    list_from_value,
    list_views_command as list_views_command_service,
    parse_query_filter,
    parse_query_sort,
    query_table_command as query_table_command_service,
    resolve_view as resolve_view_service,
    save_view_command as save_view_command_service,
    saved_view_summary as saved_view_summary_service,
)
from workspace_command_service import (
    active_workspace_id as active_workspace_id_service,
    get_system_flag as get_system_flag_service,
    set_system_flag as set_system_flag_service,
    workspace_create_command as workspace_create_command_service,
    workspace_delete_command as workspace_delete_command_service,
    workspace_records as workspace_records_service,
    workspace_rename_command as workspace_rename_command_service,
    workspace_select_command as workspace_select_command_service,
)
from evidence_dashboard_drafts import build_source_intelligence_dashboard_draft
from evidence_receipts import (
    build_source_intelligence_dashboard_candidate,
    default_source_intelligence_output_dir,
)
from evidence_run_store import (
    count_source_intelligence_runs,
    get_source_intelligence_run,
    latest_source_intelligence_summary,
    latest_source_intelligence_run,
    list_source_intelligence_runs,
    save_source_intelligence_run,
    source_intelligence_run_manifest,
)
from table_query_tools import build_table_query, normalize_filters, where_sql


SAFE_AGGREGATIONS = {"count", "count-distinct", "sum", "avg", "min", "max"}
B_INDEX_REASON_WEIGHTS = {
    "identity-key": 40,
    "event-time": 35,
    "relationship-key": 35,
    "import-unique-key": 32,
    "dashboard-filter": 28,
    "widget-dimension": 24,
    "widget-filter": 22,
    "semantic-filterable": 20,
    "semantic-groupable": 18,
    "measure": 8,
}
B_BI_CLI_CAPABILITY_MAP = [
    {
        "area": "source-management",
        "bCommands": ["list-tables", "inspect-table", "rename-source", "delete-source"],
        "hybridCommands": ["list-tables", "inspect-table", "rename-source", "delete-source", "list-navigation", "navigation-op", "workbench"],
        "integration": "mapped-to-hybrid-table-registry-source-run-and-config-cleanup",
        "status": "active",
    },
    {
        "area": "query-runtime",
        "bCommands": ["query", "query-table"],
        "hybridCommands": ["query", "query-table"],
        "integration": "mapped-to-duckdb-whitelist-and-b-style-table-query",
        "status": "active",
    },
    {
        "area": "saved-views",
        "bCommands": ["list-views", "copy-view", "create-table-view", "update-table-view", "delete-table-view"],
        "hybridCommands": ["list-views", "save-view", "copy-view", "delete-view"],
        "integration": "mapped-to-hybrid-sqlite-saved-views-and-query-table",
        "status": "active",
    },
    {
        "area": "dashboard-pages",
        "bCommands": ["list-dashboards", "add-dashboard", "copy-dashboard", "rename-dashboard", "remove-dashboard", "set-dashboard-source"],
        "hybridCommands": ["dashboards", "dashboard-op"],
        "integration": "mapped-to-hybrid-sqlite-metadata",
        "status": "active",
    },
    {
        "area": "dashboard-widgets",
        "bCommands": ["recommend-widgets", "add-recommended-widgets", "add-widget", "add-relationship-widget", "set-widget", "copy-widget", "remove-widget", "saveDashboardModules", "businessDashboardTemplates"],
        "hybridCommands": ["dashboard-widget-catalog", "recommend-widgets", "add-recommended-widgets", "add-widget", "add-relationship-widget", "set-widget", "copy-widget", "remove-widget", "save-dashboard-modules", "business-dashboard", "dashboard-op", "ask"],
        "integration": "mapped-to-hybrid-sqlite-dashboard-widgets-layout-bulk-module-save-business-dashboard-templates-and-erp-unit-library-with-dry-run-boundary",
        "status": "active",
    },
    {
        "area": "filters",
        "bCommands": ["list-filters", "add-filter", "set-filter", "remove-filter", "remove-stale-filters", "clear-filters"],
        "hybridCommands": ["list-filters", "add-filter", "set-filter", "remove-filter", "remove-stale-filters", "clear-filters", "dashboard-widget-catalog"],
        "integration": "mapped-to-dashboard-layout-global-filters-with-confirmed-writes",
        "status": "active",
    },
    {
        "area": "performance-indexes",
        "bCommands": ["recommend-indexes", "create-index"],
        "hybridCommands": ["recommend-indexes", "create-index", "query", "query-table"],
        "integration": "mapped-to-duckdb-local-index-suggestions-and-confirmed-create-index",
        "status": "active",
    },
    {
        "area": "relationships",
        "bCommands": ["recommend-relationships", "list-relationships", "add-relationship", "remove-relationship", "preview-relationship", "query-relationship"],
        "hybridCommands": ["recommend-relationships", "list-relationships", "relationship-preview", "relationship-save", "remove-relationship", "query-relationship"],
        "integration": "mapped-to-hybrid-relationship-recommend-preview-save-query-and-confirmed-remove",
        "status": "active",
    },
    {
        "area": "import",
        "bCommands": ["set-import-policy", "preview-import", "list-import-jobs", "remove-import-job", "import-file"],
        "hybridCommands": ["set-import-policy", "preview-import", "import-commit", "preview-import-folder", "import-folder", "list-import-jobs", "remove-import-job"],
        "integration": "mapped-to-import-policy-folder-plan-job-log-and-confirmed-commit",
        "status": "active",
    },
    {
        "area": "field-metric-formula",
        "bCommands": ["set-field-config", "infer-semantics", "list-semantics", "set-semantic", "infer-metrics", "list-metrics", "add-metric", "query-metric", "ensure-calculated-fields"],
        "hybridCommands": ["field-update", "infer-semantics", "list-semantics", "set-semantic", "infer-metrics", "list-metrics", "add-metric", "query-metric", "formula-preview", "save-formula", "list-formulas", "delete-formula", "workbench"],
        "integration": "mapped-to-field-semantics-tags-usage-metric-definitions-saved-metric-query-and-formula-dsl",
        "status": "active",
    },
    {
        "area": "connectors-preferences",
        "bCommands": ["list-connectors", "save-connector", "sync-connector", "delete-connector", "preferences", "theme-palettes"],
        "hybridCommands": ["list-connectors", "save-connector", "sync-connector", "remove-connector", "preferences", "theme-palettes", "workbench"],
        "integration": "mapped-to-hybrid-connector-registry-file-sync-preferences-theme-palettes-and-confirmed-delete",
        "status": "active",
    },
    {
        "area": "config-portability",
        "bCommands": ["validate-config", "export-config", "apply-config"],
        "hybridCommands": ["validate-config", "export-config", "apply-config"],
        "integration": "mapped-to-redacted-metadata-config-export-dry-run-apply-and-sqlite-backup",
        "status": "active",
    },
]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def table_columns(connection: sqlite3.Connection, physical_table: str) -> list[str]:
    return [row["name"] for row in connection.execute(f"PRAGMA table_info({quote_identifier(physical_table)})")]


def ensure_column(connection: sqlite3.Connection, table_name: str, column_name: str, definition: str) -> None:
    if column_name not in table_columns(connection, table_name):
        connection.execute(f"ALTER TABLE {quote_identifier(table_name)} ADD COLUMN {quote_identifier(column_name)} {definition}")


def primary_key_columns(connection: sqlite3.Connection, table_name: str) -> list[str]:
    rows = connection.execute(f"PRAGMA table_info({quote_identifier(table_name)})").fetchall()
    return [row["name"] for row in sorted((row for row in rows if int(row["pk"] or 0)), key=lambda row: int(row["pk"]))]


def has_unique_index(connection: sqlite3.Connection, table_name: str, columns: list[str]) -> bool:
    expected = list(columns)
    for index_row in connection.execute(f"PRAGMA index_list({quote_identifier(table_name)})").fetchall():
        if not int(index_row["unique"] or 0):
            continue
        index_name = str(index_row["name"])
        actual = [row["name"] for row in connection.execute(f"PRAGMA index_info({quote_identifier(index_name)})").fetchall()]
        if actual == expected:
            return True
    return False


def rebuild_table(connection: sqlite3.Connection, table_name: str, create_sql: str) -> None:
    legacy_name = f"{table_name}_legacy_{int(time.time() * 1000)}"
    existing_columns = table_columns(connection, table_name)
    connection.execute(f"ALTER TABLE {quote_identifier(table_name)} RENAME TO {quote_identifier(legacy_name)}")
    connection.execute(create_sql)
    next_columns = table_columns(connection, table_name)
    common_columns = [column for column in next_columns if column in existing_columns]
    if common_columns:
        column_sql = ", ".join(quote_identifier(column) for column in common_columns)
        connection.execute(
            f"INSERT OR IGNORE INTO {quote_identifier(table_name)} ({column_sql}) "
            f"SELECT {column_sql} FROM {quote_identifier(legacy_name)}"
        )
    connection.execute(f"DROP TABLE {quote_identifier(legacy_name)}")


def migrate_workspace_scoped_constraints(connection: sqlite3.Connection) -> None:
    desired_tables = {
        "table_registry": (
            ["workspace_id", "table_key"],
            """
            CREATE TABLE table_registry (
              table_key TEXT NOT NULL,
              workspace_id TEXT NOT NULL DEFAULT 'default',
              display_name TEXT NOT NULL,
              physical_table TEXT NOT NULL,
              source_file TEXT NOT NULL,
              row_count INTEGER NOT NULL,
              column_count INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              PRIMARY KEY(workspace_id, table_key)
            )
            """,
        ),
        "navigation_modules": (
            ["workspace_id", "module_key"],
            """
            CREATE TABLE navigation_modules (
              module_key TEXT NOT NULL,
              workspace_id TEXT NOT NULL DEFAULT 'default',
              name TEXT NOT NULL,
              module_type TEXT NOT NULL,
              table_key TEXT,
              dashboard_key TEXT,
              sort_order INTEGER NOT NULL,
              created_by TEXT NOT NULL,
              agent_managed INTEGER NOT NULL,
              enabled INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              PRIMARY KEY(workspace_id, module_key)
            )
            """,
        ),
        "metric_definitions": (
            ["workspace_id", "metric_key"],
            """
            CREATE TABLE metric_definitions (
              metric_key TEXT NOT NULL,
              workspace_id TEXT NOT NULL DEFAULT 'default',
              label TEXT NOT NULL,
              table_key TEXT NOT NULL,
              measure TEXT NOT NULL,
              aggregation TEXT NOT NULL,
              dimension TEXT,
              time_field TEXT,
              value_format TEXT NOT NULL,
              created_at TEXT NOT NULL,
              filters_json TEXT NOT NULL DEFAULT '[]',
              description TEXT NOT NULL DEFAULT '',
              source TEXT NOT NULL DEFAULT 'auto',
              enabled INTEGER NOT NULL DEFAULT 1,
              updated_at TEXT NOT NULL DEFAULT '',
              formula_text TEXT NOT NULL DEFAULT '',
              formula_ast_json TEXT NOT NULL DEFAULT '{}',
              dependencies_json TEXT NOT NULL DEFAULT '[]',
              metric_type TEXT NOT NULL DEFAULT 'basic',
              PRIMARY KEY(workspace_id, metric_key)
            )
            """,
        ),
        "calculated_fields": (
            ["workspace_id", "field_key"],
            """
            CREATE TABLE calculated_fields (
              field_key TEXT NOT NULL,
              workspace_id TEXT NOT NULL DEFAULT 'default',
              table_key TEXT NOT NULL,
              name TEXT NOT NULL,
              mode TEXT NOT NULL,
              formula_text TEXT NOT NULL,
              formula_ast_json TEXT NOT NULL,
              dependencies_json TEXT NOT NULL,
              value_format TEXT NOT NULL,
              description TEXT NOT NULL,
              source TEXT NOT NULL,
              enabled INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              PRIMARY KEY(workspace_id, field_key)
            )
            """,
        ),
        "relationships": (
            ["workspace_id", "relation_key"],
            """
            CREATE TABLE relationships (
              relation_key TEXT NOT NULL,
              workspace_id TEXT NOT NULL DEFAULT 'default',
              name TEXT NOT NULL,
              left_table_key TEXT NOT NULL,
              right_table_key TEXT NOT NULL,
              left_field TEXT NOT NULL,
              right_field TEXT NOT NULL,
              join_type TEXT NOT NULL,
              confidence REAL NOT NULL,
              created_at TEXT NOT NULL,
              PRIMARY KEY(workspace_id, relation_key)
            )
            """,
        ),
        "import_policies": (
            ["workspace_id", "table_key"],
            """
            CREATE TABLE import_policies (
              table_key TEXT NOT NULL,
              workspace_id TEXT NOT NULL DEFAULT 'default',
              unique_fields_json TEXT NOT NULL,
              conflict_rule TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              PRIMARY KEY(workspace_id, table_key)
            )
            """,
        ),
        "saved_views": (
            ["workspace_id", "view_key"],
            """
            CREATE TABLE saved_views (
              view_key TEXT NOT NULL,
              workspace_id TEXT NOT NULL,
              name TEXT NOT NULL,
              tag_name TEXT NOT NULL,
              table_key TEXT NOT NULL,
              config_json TEXT NOT NULL,
              is_default INTEGER NOT NULL,
              sort_order INTEGER NOT NULL,
              created_by TEXT NOT NULL,
              agent_managed INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              PRIMARY KEY(workspace_id, view_key)
            )
            """,
        ),
        "dashboards": (
            ["workspace_id", "dashboard_key"],
            """
            CREATE TABLE dashboards (
              dashboard_key TEXT NOT NULL,
              name TEXT NOT NULL,
              workspace_id TEXT NOT NULL DEFAULT 'default',
              default_table_key TEXT,
              layout_json TEXT NOT NULL,
              created_by TEXT NOT NULL,
              agent_managed INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              PRIMARY KEY(workspace_id, dashboard_key)
            )
            """,
        ),
        "dashboard_widgets": (
            ["workspace_id", "widget_key"],
            """
            CREATE TABLE dashboard_widgets (
              widget_key TEXT NOT NULL,
              workspace_id TEXT NOT NULL DEFAULT 'default',
              dashboard_key TEXT NOT NULL,
              widget_type TEXT NOT NULL,
              title TEXT NOT NULL,
              table_key TEXT,
              config_json TEXT NOT NULL,
              sort_order INTEGER NOT NULL,
              PRIMARY KEY(workspace_id, widget_key)
            )
            """,
        ),
    }
    for table_name, (pk_columns, create_sql) in desired_tables.items():
        if primary_key_columns(connection, table_name) != pk_columns:
            rebuild_table(connection, table_name, create_sql)
    if not has_unique_index(connection, "field_semantics", ["workspace_id", "table_key", "field_name"]):
        rebuild_table(
            connection,
            "field_semantics",
            """
            CREATE TABLE field_semantics (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              workspace_id TEXT NOT NULL DEFAULT 'default',
              table_key TEXT NOT NULL,
              field_name TEXT NOT NULL,
              role TEXT NOT NULL,
              usage TEXT NOT NULL,
              confidence REAL NOT NULL,
              tags_json TEXT NOT NULL DEFAULT '[]',
              usage_json TEXT NOT NULL DEFAULT '{}',
              source TEXT NOT NULL DEFAULT 'auto',
              note TEXT NOT NULL DEFAULT '',
              updated_at TEXT NOT NULL DEFAULT '',
              UNIQUE(workspace_id, table_key, field_name)
            )
            """,
        )


def physical_table_for_workspace(workspace_id: str, table_key: str) -> str:
    if workspace_id == "default":
        return f"data_{table_key}"
    return f"data_{slug(workspace_id)[:28]}_{slug(table_key)[:48]}"[:96]


def registry_for_table(connection: sqlite3.Connection, table_key: str) -> sqlite3.Row | None:
    return connection.execute("SELECT * FROM table_registry WHERE table_key = ? AND workspace_id = ?", (table_key, active_workspace_id(connection))).fetchone()


def all_available_fields(connection: sqlite3.Connection, table_key: str | None = None) -> set[str]:
    fields: set[str] = set()
    workspace_id = active_workspace_id(connection)
    params: tuple[Any, ...] = (table_key, workspace_id) if table_key else (workspace_id,)
    where = "WHERE table_key = ? AND workspace_id = ?" if table_key else "WHERE workspace_id = ?"
    for row in connection.execute(f"SELECT physical_table FROM table_registry {where}", params):
        fields.update(table_columns(connection, row["physical_table"]))
    for row in connection.execute("SELECT label, measure FROM metric_definitions WHERE workspace_id = ?", (workspace_id,)):
        fields.add(str(row["label"]))
        if row["measure"] and row["measure"] != "*":
            fields.add(str(row["measure"]))
    if table_exists(connection, "calculated_fields"):
        calc_where = "WHERE table_key = ? AND workspace_id = ? AND enabled = 1" if table_key else "WHERE workspace_id = ? AND enabled = 1"
        for row in connection.execute(f"SELECT name FROM calculated_fields {calc_where}", params):
            fields.add(str(row["name"]))
    return fields


def open_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    ensure_schema(connection)
    ensure_navigation_modules(connection)
    return connection


def get_system_flag(connection: sqlite3.Connection, key: str, default: str = "") -> str:
    return get_system_flag_service(connection, key, default)


def set_system_flag(connection: sqlite3.Connection, key: str, value: str) -> None:
    set_system_flag_service(connection, key, value)


def active_workspace_id(connection: sqlite3.Connection) -> str:
    return active_workspace_id_service(connection)


def workspace_records(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    return workspace_records_service(connection, rows_to_dicts=rows_to_dicts)


def ensure_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS workspaces (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          current_source_run_id TEXT,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS system_flags (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS table_registry (
          table_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          display_name TEXT NOT NULL,
          physical_table TEXT NOT NULL,
          source_file TEXT NOT NULL,
          row_count INTEGER NOT NULL,
          column_count INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, table_key)
        );
        CREATE TABLE IF NOT EXISTS navigation_modules (
          module_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          name TEXT NOT NULL,
          module_type TEXT NOT NULL,
          table_key TEXT,
          dashboard_key TEXT,
          sort_order INTEGER NOT NULL,
          created_by TEXT NOT NULL,
          agent_managed INTEGER NOT NULL,
          enabled INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, module_key)
        );
        CREATE TABLE IF NOT EXISTS source_runs (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL,
          table_key TEXT NOT NULL,
          name TEXT NOT NULL,
          status TEXT NOT NULL,
          source_file TEXT NOT NULL,
          row_count INTEGER NOT NULL,
          column_count INTEGER NOT NULL,
          profile_json TEXT NOT NULL,
          evidence_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS field_semantics (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          table_key TEXT NOT NULL,
          field_name TEXT NOT NULL,
          role TEXT NOT NULL,
          usage TEXT NOT NULL,
          confidence REAL NOT NULL,
          UNIQUE(workspace_id, table_key, field_name)
        );
        CREATE TABLE IF NOT EXISTS metric_definitions (
          metric_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          label TEXT NOT NULL,
          table_key TEXT NOT NULL,
          measure TEXT NOT NULL,
          aggregation TEXT NOT NULL,
          dimension TEXT,
          time_field TEXT,
          value_format TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, metric_key)
        );
        CREATE TABLE IF NOT EXISTS calculated_fields (
          field_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          table_key TEXT NOT NULL,
          name TEXT NOT NULL,
          mode TEXT NOT NULL,
          formula_text TEXT NOT NULL,
          formula_ast_json TEXT NOT NULL,
          dependencies_json TEXT NOT NULL,
          value_format TEXT NOT NULL,
          description TEXT NOT NULL,
          source TEXT NOT NULL,
          enabled INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, field_key)
        );
        CREATE TABLE IF NOT EXISTS relationships (
          relation_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          name TEXT NOT NULL,
          left_table_key TEXT NOT NULL,
          right_table_key TEXT NOT NULL,
          left_field TEXT NOT NULL,
          right_field TEXT NOT NULL,
          join_type TEXT NOT NULL,
          confidence REAL NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, relation_key)
        );
        CREATE TABLE IF NOT EXISTS dashboards (
          dashboard_key TEXT NOT NULL,
          name TEXT NOT NULL,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          default_table_key TEXT,
          layout_json TEXT NOT NULL,
          created_by TEXT NOT NULL,
          agent_managed INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, dashboard_key)
        );
        CREATE TABLE IF NOT EXISTS dashboard_widgets (
          widget_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          dashboard_key TEXT NOT NULL,
          widget_type TEXT NOT NULL,
          title TEXT NOT NULL,
          table_key TEXT,
          config_json TEXT NOT NULL,
          sort_order INTEGER NOT NULL,
          PRIMARY KEY(workspace_id, widget_key)
        );
        CREATE TABLE IF NOT EXISTS saved_views (
          view_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          name TEXT NOT NULL,
          tag_name TEXT NOT NULL,
          table_key TEXT NOT NULL,
          config_json TEXT NOT NULL,
          is_default INTEGER NOT NULL,
          sort_order INTEGER NOT NULL,
          created_by TEXT NOT NULL,
          agent_managed INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, view_key)
        );
        CREATE TABLE IF NOT EXISTS import_jobs (
          job_key TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          source_file TEXT NOT NULL,
          table_key TEXT,
          mode TEXT NOT NULL,
          status TEXT NOT NULL,
          row_count INTEGER NOT NULL,
          result_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS import_policies (
          table_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          unique_fields_json TEXT NOT NULL,
          conflict_rule TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, table_key)
        );
        CREATE TABLE IF NOT EXISTS data_connectors (
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
        );
        CREATE TABLE IF NOT EXISTS user_preferences (
          preference_key TEXT PRIMARY KEY,
          preferences_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS theme_palettes (
          theme_key TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          mode TEXT NOT NULL,
          tokens_json TEXT NOT NULL,
          enabled INTEGER NOT NULL,
          sort_order INTEGER NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS action_drafts (
          action_key TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          kind TEXT NOT NULL,
          label TEXT NOT NULL,
          status TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          evidence_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          confirmed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS source_intelligence_runs (
          run_key TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          label TEXT NOT NULL,
          status TEXT NOT NULL,
          input_roots_json TEXT NOT NULL,
          output_dir TEXT NOT NULL,
          source_count INTEGER NOT NULL,
          table_count INTEGER NOT NULL,
          field_candidate_count INTEGER NOT NULL,
          relationship_count INTEGER NOT NULL,
          metric_sql_plan_count INTEGER NOT NULL,
          metric_sql_executable_count INTEGER NOT NULL,
          manifest_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        """
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO workspaces(id, name, current_source_run_id, created_at)
        VALUES('default', 'AIBI Hybrid Workspace', NULL, ?)
        """,
        (now_iso(),),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO system_flags(key, value, updated_at)
        VALUES('active_workspace_id', 'default', ?)
        """,
        (now_iso(),),
    )
    connection.execute(
        """
        UPDATE action_drafts
        SET status = 'read-only-legacy'
        WHERE kind = 'analysis.plan' AND status = 'draft'
        """
    )
    ensure_column(connection, "field_semantics", "tags_json", "TEXT NOT NULL DEFAULT '[]'")
    ensure_column(connection, "table_registry", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    ensure_column(connection, "field_semantics", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    ensure_column(connection, "field_semantics", "usage_json", "TEXT NOT NULL DEFAULT '{}'")
    ensure_column(connection, "field_semantics", "source", "TEXT NOT NULL DEFAULT 'auto'")
    ensure_column(connection, "field_semantics", "note", "TEXT NOT NULL DEFAULT ''")
    ensure_column(connection, "field_semantics", "updated_at", "TEXT NOT NULL DEFAULT ''")
    ensure_column(connection, "metric_definitions", "filters_json", "TEXT NOT NULL DEFAULT '[]'")
    ensure_column(connection, "metric_definitions", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    ensure_column(connection, "metric_definitions", "description", "TEXT NOT NULL DEFAULT ''")
    ensure_column(connection, "metric_definitions", "source", "TEXT NOT NULL DEFAULT 'auto'")
    ensure_column(connection, "metric_definitions", "enabled", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(connection, "metric_definitions", "updated_at", "TEXT NOT NULL DEFAULT ''")
    ensure_column(connection, "metric_definitions", "formula_text", "TEXT NOT NULL DEFAULT ''")
    ensure_column(connection, "metric_definitions", "formula_ast_json", "TEXT NOT NULL DEFAULT '{}'")
    ensure_column(connection, "metric_definitions", "dependencies_json", "TEXT NOT NULL DEFAULT '[]'")
    ensure_column(connection, "metric_definitions", "metric_type", "TEXT NOT NULL DEFAULT 'basic'")
    ensure_column(connection, "calculated_fields", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    ensure_column(connection, "relationships", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    ensure_column(connection, "navigation_modules", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    ensure_column(connection, "dashboards", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    ensure_column(connection, "dashboard_widgets", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    ensure_column(connection, "import_jobs", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    ensure_column(connection, "import_policies", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    ensure_column(connection, "action_drafts", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    ensure_column(connection, "source_intelligence_runs", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    migrate_workspace_scoped_constraints(connection)
    ensure_default_preferences_and_themes(connection)


def normalize_user_preferences(value: Any) -> dict[str, Any]:
    return normalize_user_preferences_service(value)


def normalize_theme_tokens(value: Any) -> dict[str, str]:
    return normalize_theme_tokens_service(value)


def normalize_theme_palette(value: dict[str, Any]) -> dict[str, Any]:
    return normalize_theme_palette_service(value)


def validate_theme_palette_payload(value: dict[str, Any]) -> dict[str, Any]:
    return validate_theme_palette_payload_service(value)


def ensure_default_preferences_and_themes(connection: sqlite3.Connection) -> None:
    ensure_default_preferences_and_themes_service(connection)


def load_user_preferences(connection: sqlite3.Connection) -> dict[str, Any]:
    return load_user_preferences_service(connection)


def save_user_preferences(connection: sqlite3.Connection, preferences: dict[str, Any]) -> dict[str, Any]:
    return save_user_preferences_service(connection, preferences)


def list_theme_palettes(connection: sqlite3.Connection, enabled_only: bool = True) -> list[dict[str, Any]]:
    return list_theme_palettes_service(connection, enabled_only=enabled_only)


def upsert_theme_palette(connection: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    return upsert_theme_palette_service(connection, payload)


def delete_theme_palette(connection: sqlite3.Connection, theme_key: str) -> dict[str, Any]:
    return delete_theme_palette_service(connection, theme_key)


def navigation_module_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "moduleKey": row["module_key"],
        "name": row["name"],
        "type": row["module_type"],
        "tableKey": row["table_key"] or "",
        "dashboardKey": row["dashboard_key"] or "",
        "sort": int(row["sort_order"] or 0),
        "createdBy": row["created_by"] or "system",
        "agentManaged": bool(row["agent_managed"]),
        "enabled": bool(row["enabled"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def next_navigation_sort(connection: sqlite3.Connection, module_type: str) -> int:
    base = {"table": 100, "view": 400, "dashboard": 700}.get(module_type, 900)
    workspace_id = active_workspace_id(connection)
    row = connection.execute(
        """
        SELECT COALESCE(MAX(sort_order), ?) AS max_sort
        FROM navigation_modules
        WHERE module_type = ? AND workspace_id = ?
        """,
        (base, module_type, workspace_id),
    ).fetchone()
    return int(row["max_sort"] or base) + 10


def upsert_navigation_module(
    connection: sqlite3.Connection,
    *,
    module_key: str,
    name: str,
    module_type: str,
    table_key: str = "",
    dashboard_key: str = "",
    created_by: str = "system",
    agent_managed: int = 1,
) -> None:
    now = now_iso()
    workspace_id = active_workspace_id(connection)
    existing = connection.execute(
        "SELECT * FROM navigation_modules WHERE module_key = ? AND workspace_id = ?",
        (module_key, workspace_id),
    ).fetchone()
    if existing:
        connection.execute(
            """
            UPDATE navigation_modules
            SET table_key = ?,
                dashboard_key = ?,
                updated_at = ?
            WHERE module_key = ? AND workspace_id = ?
            """,
            (table_key or None, dashboard_key or None, now, module_key, workspace_id),
        )
        return
    connection.execute(
        """
        INSERT INTO navigation_modules(
          module_key, workspace_id, name, module_type, table_key, dashboard_key, sort_order,
          created_by, agent_managed, enabled, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """,
        (
            module_key,
            workspace_id,
            name,
            module_type,
            table_key or None,
            dashboard_key or None,
            next_navigation_sort(connection, module_type),
            created_by,
            int(agent_managed),
            now,
            now,
        ),
    )


def ensure_navigation_modules(connection: sqlite3.Connection) -> None:
    workspace_id = active_workspace_id(connection)
    for row in connection.execute(
        "SELECT table_key, display_name FROM table_registry WHERE workspace_id = ? ORDER BY display_name",
        (workspace_id,),
    ).fetchall():
        upsert_navigation_module(
            connection,
            module_key=f"table:{row['table_key']}",
            name=row["display_name"],
            module_type="table",
            table_key=row["table_key"],
            created_by="system",
            agent_managed=1,
        )
    for row in connection.execute(
        "SELECT dashboard_key, name FROM dashboards WHERE workspace_id = ? ORDER BY created_at",
        (workspace_id,),
    ).fetchall():
        upsert_navigation_module(
            connection,
            module_key=f"dashboard:{row['dashboard_key']}",
            name=row["name"],
            module_type="dashboard",
            dashboard_key=row["dashboard_key"],
            created_by="system",
            agent_managed=1,
        )


def list_navigation_modules(connection: sqlite3.Connection, include_disabled: bool = False) -> list[dict[str, Any]]:
    ensure_navigation_modules(connection)
    workspace_id = active_workspace_id(connection)
    enabled_clause = "" if include_disabled else "AND n.enabled = 1"
    rows = connection.execute(
        f"""
        SELECT n.*
        FROM navigation_modules n
        LEFT JOIN table_registry t
          ON t.table_key = n.table_key
         AND t.workspace_id = ?
        LEFT JOIN dashboards d
          ON d.dashboard_key = n.dashboard_key
         AND d.workspace_id = ?
        WHERE n.workspace_id = ?
          AND (
          (n.module_type = 'table' AND t.table_key IS NOT NULL)
          OR (n.module_type = 'dashboard' AND d.dashboard_key IS NOT NULL)
          OR n.module_type = 'view'
        )
        {enabled_clause}
        ORDER BY sort_order, module_type, name
        """,
        (workspace_id, workspace_id, workspace_id),
    ).fetchall()
    return [navigation_module_payload(row) for row in rows]


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
    registry = registry_for_table(connection, table_key)
    if not registry:
        raise ValueError(f"Unknown table for merge: {table_key}")
    headers, raw_rows = read_table_file(path)
    physical_table = registry["physical_table"]
    existing_columns = table_columns(connection, physical_table)
    if set(headers) != set(existing_columns):
        raise ValueError("导入文件字段与目标表不匹配，已取消合并。")
    columns = [column for column in existing_columns if column in headers]
    selected_unique_fields = sanitize_unique_fields(unique_fields, columns, allow_empty=False)
    records = normalize_records_for_columns(raw_rows, columns)
    plan = preview_merge_plan(connection, physical_table, columns, records, selected_unique_fields, conflict_rule, quote_identifier)
    existing_map = existing_rows_by_unique_key(connection, physical_table, columns, records, selected_unique_fields, quote_identifier)
    insert_columns_sql = ", ".join(quote_identifier(column) for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    insert_sql = f"INSERT INTO {quote_identifier(physical_table)} ({insert_columns_sql}) VALUES ({placeholders})"
    update_columns = [column for column in columns if column not in selected_unique_fields]
    update_sql = (
        f"UPDATE {quote_identifier(physical_table)} SET "
        + ", ".join(f"{quote_identifier(column)} = ?" for column in update_columns)
        + " WHERE rowid = ?"
    ) if update_columns else ""
    inserted = 0
    updated = 0
    skipped = 0
    seen_keys: set[str] = set()
    for record in records:
        key = record_unique_key(record, selected_unique_fields)
        if key is None or key in seen_keys:
            skipped += 1
            continue
        seen_keys.add(key)
        existing = existing_map.get(key)
        if existing:
            if conflict_rule == "skip-existing":
                skipped += 1
                continue
            if conflict_rule == "fill-empty":
                changed_columns = [
                    column
                    for column in update_columns
                    if str(existing.get(column) or "").strip() == "" and str(record.get(column) or "").strip() != ""
                ]
                if not changed_columns:
                    skipped += 1
                    continue
                set_sql = ", ".join(f"{quote_identifier(column)} = ?" for column in changed_columns)
                connection.execute(
                    f"UPDATE {quote_identifier(physical_table)} SET {set_sql} WHERE rowid = ?",
                    [record.get(column, "") for column in changed_columns] + [existing["_rowid"]],
                )
            elif update_sql:
                connection.execute(update_sql, [record.get(column, "") for column in update_columns] + [existing["_rowid"]])
            updated += 1
        else:
            connection.execute(insert_sql, [record.get(column, "") for column in columns])
            inserted += 1
    row_count = connection.execute(f"SELECT COUNT(*) FROM {quote_identifier(physical_table)}").fetchone()[0]
    profile = profile_rows(columns, [dict(row) for row in connection.execute(f"SELECT {insert_columns_sql} FROM {quote_identifier(physical_table)}")])
    result = {
        "tableKey": table_key,
        "displayName": display_name or registry["display_name"],
        "sourceRunId": "",
        "profile": profile,
        "mergePlan": plan,
        "writeSummary": {
            "insertedRows": inserted,
            "updatedRows": updated,
            "skippedRows": skipped,
            "rowCountAfter": row_count,
            "uniqueFields": selected_unique_fields,
            "conflictRule": conflict_rule,
        },
    }
    source_run_id = update_table_metadata_after_write(
        connection,
        table_key=table_key,
        display_name=display_name or registry["display_name"],
        source_file=source_label(path),
        physical_table=physical_table,
        row_count=row_count,
        column_count=len(columns),
        profile=profile,
        mode="merge",
        result=result,
    )
    result["sourceRunId"] = source_run_id
    return result


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


def cli_contract_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> dict[str, Any]:
    contract = build_cli_contract(parser)
    if args.command_name:
        command_contract = command_contract_by_name(contract, args.command_name)
        if not command_contract:
            raise ValueError(f"Unknown CLI command in contract: {args.command_name}")
        domains = {str(command_contract["domain"]): 1}
        mutation_modes = {str(command_contract["mutationMode"]): 1}
        contract = {
            **contract,
            "commands": [command_contract],
            "commandCount": 1,
            "domains": domains,
            "mutationModes": mutation_modes,
        }
    output_path = Path(args.output) if args.output else None
    if args.format == "markdown":
        markdown = contract_to_markdown(contract)
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(markdown, encoding="utf-8")
        return {
            "ok": True,
            "format": "markdown",
            "contract": {
                "schema": contract["schema"],
                "commandCount": contract["commandCount"],
                "domains": contract["domains"],
                "mutationModes": contract["mutationModes"],
            },
            "markdown": markdown if not output_path else "",
            "outputPath": str(output_path) if output_path else "",
        }
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "ok": True,
        "format": "json",
        "contract": contract,
        "outputPath": str(output_path) if output_path else "",
    }


def list_commands_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> dict[str, Any]:
    contract = build_cli_contract(parser)
    writes_filter = None
    if args.writes == "yes":
        writes_filter = True
    elif args.writes == "no":
        writes_filter = False
    commands = filter_commands(
        contract,
        domain=args.domain,
        mutation_mode=args.mutation_mode,
        writes=writes_filter,
    )
    return {
        "ok": True,
        "schema": contract["schema"],
        "commandCount": len(commands),
        "commands": [
            {
                "name": command["name"],
                "domain": command["domain"],
                "mutationMode": command["mutationMode"],
                "dryRunByDefault": command["dryRunByDefault"],
                "requiresYes": command["requiresYes"],
                "createsActionDraft": command["createsActionDraft"],
                "writesEvidence": command["writesEvidence"],
                "writesBusinessState": command["writesBusinessState"],
            }
            for command in commands
        ],
    }


def status_command(args: argparse.Namespace) -> dict[str, Any]:
    runtime = duckdb_status(DUCKDB_PATH)
    with open_db() as connection:
        active_id = active_workspace_id(connection)
        workspaces = workspace_records(connection)
        counts = {
            "tables": connection.execute("SELECT COUNT(*) FROM table_registry WHERE workspace_id = ?", (active_id,)).fetchone()[0],
            "sourceRuns": connection.execute("SELECT COUNT(*) FROM source_runs WHERE workspace_id = ?", (active_id,)).fetchone()[0],
            "fields": connection.execute("SELECT COUNT(*) FROM field_semantics WHERE workspace_id = ?", (active_id,)).fetchone()[0],
            "metrics": connection.execute("SELECT COUNT(*) FROM metric_definitions WHERE workspace_id = ?", (active_id,)).fetchone()[0],
            "relationships": connection.execute("SELECT COUNT(*) FROM relationships WHERE workspace_id = ?", (active_id,)).fetchone()[0],
            "dashboards": connection.execute("SELECT COUNT(*) FROM dashboards WHERE workspace_id = ?", (active_id,)).fetchone()[0],
            "actionDrafts": count_pending_action_drafts(connection, workspace_id=active_id),
            "sourceIntelligenceRuns": count_source_intelligence_runs(connection, workspace_id=active_id),
            "connectors": connection.execute("SELECT COUNT(*) FROM data_connectors").fetchone()[0],
        }
        workspace = dict(connection.execute("SELECT * FROM workspaces WHERE id = ?", (active_id,)).fetchone())
        workspace["isActive"] = True
        source_runs = rows_to_dicts(
            connection.execute(
                """
                SELECT id, table_key, name, status, row_count, column_count, source_file
                FROM source_runs
                WHERE workspace_id = ?
                ORDER BY created_at DESC
                LIMIT 5
                """,
                (active_id,),
            )
        )
        for run in source_runs:
            run["source_file"] = source_label(run["source_file"])
        return {
            "ok": True,
            "workspace": workspace,
            "workspaces": workspaces,
            "database": str(DB_PATH),
            "queryRuntime": runtime,
            "counts": counts,
            "sourceRuns": source_runs,
            "health": {
                "ok": True,
                "notes": [
                    "No bundled data is loaded by default; import local files to begin analysis.",
                    (
                        "DuckDB query runtime is available."
                        if runtime["available"]
                        else "DuckDB package is missing; whitelist queries use SQLite fallback until requirements are installed."
                    ),
                ],
            },
        }


def quality_doctor_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        counts = {
            "tables": connection.execute("SELECT COUNT(*) FROM table_registry WHERE workspace_id = ?", (workspace_id,)).fetchone()[0],
            "sourceRuns": connection.execute("SELECT COUNT(*) FROM source_runs WHERE workspace_id = ?", (workspace_id,)).fetchone()[0],
            "fields": connection.execute("SELECT COUNT(*) FROM field_semantics WHERE workspace_id = ?", (workspace_id,)).fetchone()[0],
            "metrics": connection.execute("SELECT COUNT(*) FROM metric_definitions WHERE workspace_id = ?", (workspace_id,)).fetchone()[0],
            "relationships": connection.execute("SELECT COUNT(*) FROM relationships WHERE workspace_id = ?", (workspace_id,)).fetchone()[0],
            "dashboards": connection.execute("SELECT COUNT(*) FROM dashboards WHERE workspace_id = ?", (workspace_id,)).fetchone()[0],
            "actionDrafts": count_pending_action_drafts(connection, workspace_id=workspace_id),
            "sourceIntelligenceRuns": count_source_intelligence_runs(connection, workspace_id=workspace_id),
        }
        latest_run = latest_source_intelligence_summary(connection, workspace_id=workspace_id)
        low_confidence_fields = rows_to_dicts(
            connection.execute(
                """
                SELECT table_key, field_name, role, usage, confidence
                FROM field_semantics
                WHERE workspace_id = ? AND confidence < 0.65
                ORDER BY confidence ASC, table_key, field_name
                LIMIT 8
                """,
                (workspace_id,),
            )
        )
        recent_runs = rows_to_dicts(
            connection.execute(
                """
                SELECT table_key, name, status, row_count, column_count, source_file
                FROM source_runs
                WHERE workspace_id = ?
                ORDER BY created_at DESC
                LIMIT 6
                """,
                (workspace_id,),
            )
        )
    for run in recent_runs:
        run["source_file"] = source_label(run["source_file"])

    latest_run = latest_run or {}
    source_intelligence_tables = int(latest_run.get("table_count") or 0)
    metric_sql_diagnostic = metric_sql_doctor_from_run(latest_run) if latest_run else {}
    metric_sql_plans = int(metric_sql_diagnostic.get("planned") or latest_run.get("metric_sql_plan_count") or 0)
    executable_metric_sql = int(metric_sql_diagnostic.get("executable") or latest_run.get("metric_sql_executable_count") or 0)
    metric_sql_rate = executable_metric_sql / max(1, metric_sql_plans)
    missing_semantic_summary = metric_sql_diagnostic.get("missingSemantics") if isinstance(metric_sql_diagnostic.get("missingSemantics"), list) else []
    relationship_needed = counts["tables"] > 1 and counts["relationships"] == 0

    score_parts = [
        100 if counts["tables"] > 0 else 35,
        100 if counts["fields"] >= max(1, counts["tables"] * 3) else 55,
        100 if counts["metrics"] > 0 else 50,
        100 if counts["dashboards"] > 0 else 55,
        100 if source_intelligence_tables >= counts["tables"] and counts["tables"] > 0 else 60,
        round(metric_sql_rate * 100) if metric_sql_plans else 60,
        100 if not low_confidence_fields else 70,
        100 if not relationship_needed else 65,
    ]
    score = round(sum(score_parts) / len(score_parts))
    tone = "ok" if score >= 85 else "warn" if score >= 65 else "risk"

    issues: list[dict[str, Any]] = []
    if counts["tables"] == 0:
        issues.append({
            "key": "no-table",
            "tone": "risk",
            "title": "还没有可分析的数据表",
            "detail": "先导入文件，或运行验证链路。",
            "action": "导入数据",
        })
    if counts["metrics"] == 0:
        issues.append({
            "key": "no-metric",
            "tone": "warn",
            "title": "缺少业务指标",
            "detail": "看板可以展示表格，但自然语言回答和趋势判断会变弱。",
            "action": "生成指标",
        })
    if relationship_needed:
        issues.append({
            "key": "missing-relationship",
            "tone": "warn",
            "title": "多表尚未建立关系",
            "detail": "跨表组件、筛选联动和下钻解释需要至少一条可确认关系。",
            "action": "推荐关系",
        })
    if latest_run and source_intelligence_tables < counts["tables"]:
        issues.append({
            "key": "source-intelligence-stale",
            "tone": "warn",
            "title": "Source Intelligence 可能落后于当前表",
            "detail": f"最新扫描覆盖 {source_intelligence_tables} 张表，当前工作区有 {counts['tables']} 张表。",
            "action": "重新扫描",
        })
    if metric_sql_plans and metric_sql_rate < 0.8:
        issues.append({
            "key": "metric-sql-coverage",
            "tone": "warn",
            "title": "部分指标 SQL 还不能执行",
            "detail": (
                f"{executable_metric_sql}/{metric_sql_plans} 个指标 SQL 可执行。"
                f"优先确认 {', '.join(str(item.get('semantic')) for item in missing_semantic_summary[:3] if isinstance(item, dict)) or '字段语义'}。"
            ),
            "action": "修复指标",
            "repairDraft": metric_sql_diagnostic.get("repairDraft"),
        })
    if low_confidence_fields:
        issues.append({
            "key": "low-confidence-fields",
            "tone": "warn",
            "title": "存在低置信字段语义",
            "detail": "字段用途不稳定会影响指标推荐、筛选和 Agent 解释。",
            "action": "确认字段",
            "examples": low_confidence_fields,
        })
    if not issues:
        issues.append({
            "key": "ready",
            "tone": "ok",
            "title": "数据链路可用于看板和 Agent",
            "detail": "表、字段、指标、Source Intelligence 和看板基础资产已经形成闭环。",
            "action": "继续分析",
        })

    return {
        "ok": True,
        "source": "hybrid-quality-doctor",
        "workspaceId": workspace_id,
        "score": score,
        "tone": tone,
        "summary": "数据链路健康" if tone == "ok" else "存在可优化的数据链路问题",
        "counts": counts,
        "latestSourceIntelligenceRun": latest_run or None,
        "metricSql": {
            "planned": metric_sql_plans,
            "executable": executable_metric_sql,
            "rate": metric_sql_rate,
            **metric_sql_diagnostic,
        },
        "issues": issues,
        "recentSourceRuns": recent_runs,
        "nextActions": [
            "导入数据",
            "运行 Source Intelligence",
            "生成或确认指标",
            "预演看板",
            "让 Agent 解释证据",
        ],
    }


def workspace_create_command(args: argparse.Namespace) -> dict[str, Any]:
    return workspace_create_command_service(args, open_db=open_db)


def workspace_select_command(args: argparse.Namespace) -> dict[str, Any]:
    return workspace_select_command_service(args, open_db=open_db)


def workspace_rename_command(args: argparse.Namespace) -> dict[str, Any]:
    return workspace_rename_command_service(args, open_db=open_db)


def workspace_delete_command(args: argparse.Namespace) -> dict[str, Any]:
    return workspace_delete_command_service(args, open_db=open_db, duckdb_path=DUCKDB_PATH)


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


def source_intelligence_dashboard_draft_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        run = get_source_intelligence_run(connection, workspace_id=workspace_id, run_key=args.run) if args.run else latest_source_intelligence_run(connection, workspace_id=workspace_id)
        if not run:
            raise ValueError("No source intelligence run is available for dashboard draft creation")
        manifest = source_intelligence_run_manifest(run)
        candidate = build_source_intelligence_dashboard_candidate(Path(run["output_dir"]), manifest)
        analyses = candidate.get("analyses") if isinstance(candidate.get("analyses"), list) else []
        if not analyses:
            raise ValueError(f"Source intelligence run has no executable dashboard candidate: {run['run_key']}")
        dashboard_draft = build_source_intelligence_dashboard_draft(
            connection,
            run,
            candidate,
            dashboard_name=args.name or str(candidate.get("title") or "Source Intelligence 候选看板"),
            limit=args.limit,
            preferred_table_key=preferred_table_key,
            template_widget_layout=template_widget_layout,
            slug=slug,
        )
        action_key = unique_key("draft")
        payload = {
            "prompt": f"Create dashboard from source intelligence run {run['run_key']}",
            "dashboardKey": "",
            "dashboardName": dashboard_draft["dashboardName"],
            "defaultTableKey": dashboard_draft["defaultTableKey"],
            "tableKey": dashboard_draft["defaultTableKey"],
            "sourceRunKey": dashboard_draft["sourceRunKey"],
            "dashboardDraft": dashboard_draft,
            "dashboardCandidate": candidate,
        }
        evidence = dashboard_draft["evidence"]
        action_draft = create_action_draft(
            connection,
            action_key=action_key,
            workspace_id=workspace_id,
            kind="dashboard.create",
            label="Source Intelligence 看板草案",
            payload=payload,
            evidence=evidence,
            created_at=now_iso(),
        )
        connection.commit()
    return {
        "ok": True,
        "dryRun": True,
        "requiresConfirmation": True,
        "source": "source-intelligence-dashboard-candidate",
        "sourceRunKey": dashboard_draft["sourceRunKey"],
        "actionDraft": action_draft,
        "dashboardDraft": dashboard_draft,
        "dashboardCandidate": candidate,
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


def query_command(args: argparse.Namespace) -> dict[str, Any]:
    if args.agg not in SAFE_AGGREGATIONS:
        raise ValueError(f"Unsupported aggregation: {args.agg}")
    with open_db() as connection:
        registry = resolve_table_registry(connection, args.table)
        physical_table = registry["physical_table"]
        table_columns = [row["name"] for row in connection.execute(f"PRAGMA table_info({quote_identifier(physical_table)})")]
        if args.group and args.group not in table_columns:
            raise ValueError(f"Unknown group field: {args.group}")
        if args.measure != "*" and args.measure not in table_columns:
            raise ValueError(f"Unknown measure field: {args.measure}")
        try:
            runtime = run_duckdb_aggregate_query(
                sqlite_connection=connection,
                duckdb_path=DUCKDB_PATH,
                physical_table=physical_table,
                columns=table_columns,
                group=args.group,
                measure=args.measure,
                aggregation=args.agg,
                limit=args.limit,
            )
            fallback_reason = None
        except DuckDBUnavailable as exc:
            runtime = run_sqlite_aggregate_query(
                sqlite_connection=connection,
                physical_table=physical_table,
                group=args.group,
                measure=args.measure,
                aggregation=args.agg,
                limit=args.limit,
            )
            fallback_reason = str(exc)
        rows = runtime.pop("rows")
    return {
        "ok": True,
        "query": {
            "table": args.table,
            "mode": "aggregate" if args.group else "metric",
            "group": args.group,
            "measure": args.measure,
            "aggregation": args.agg,
            "sqlIntent": "whitelist aggregate query; no user SQL accepted",
            "runtime": runtime,
            "fallbackReason": fallback_reason,
        },
        "rows": rows,
    }


def resolve_view(connection: sqlite3.Connection, view_key: str, table_key: str | None = None) -> dict[str, Any]:
    return resolve_view_service(connection, view_key, table_key, active_workspace_id=active_workspace_id)


def saved_view_summary(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    return saved_view_summary_service(connection, row, registry_for_table=registry_for_table)


def list_views_command(args: argparse.Namespace) -> dict[str, Any]:
    return list_views_command_service(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        saved_view_summary=saved_view_summary,
    )


def query_table_command(args: argparse.Namespace) -> dict[str, Any]:
    return query_table_command_service(
        args,
        open_db=open_db,
        resolve_view=resolve_view,
        registry_for_table=registry_for_table,
        table_columns=table_columns,
    )


def build_save_view_plan(
    connection: sqlite3.Connection,
    table_key: str,
    name: str,
    config: dict[str, Any],
    view_key: str = "",
    tag_name: str = "",
    created_by: str = "user",
    agent_managed: int = 0,
) -> dict[str, Any]:
    return build_save_view_plan_service(
        connection,
        table_key,
        name,
        config,
        view_key,
        tag_name,
        created_by,
        agent_managed,
        active_workspace_id=active_workspace_id,
        registry_for_table=registry_for_table,
        table_columns=table_columns,
        analysis_columns_for_table=analysis_columns_for_table,
    )


def execute_save_view_plan(connection: sqlite3.Connection, proposed: dict[str, Any]) -> dict[str, Any]:
    return execute_save_view_plan_service(
        connection,
        proposed,
        now_iso=now_iso,
        upsert_navigation_module=upsert_navigation_module,
        saved_view_summary=saved_view_summary,
    )


def save_view_command(args: argparse.Namespace) -> dict[str, Any]:
    return save_view_command_service(
        args,
        open_db=open_db,
        build_save_view_plan=build_save_view_plan,
        execute_save_view_plan=execute_save_view_plan,
    )


def copy_view_command(args: argparse.Namespace) -> dict[str, Any]:
    return copy_view_command_service(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        resolve_view=resolve_view,
        saved_view_summary=saved_view_summary,
        now_iso=now_iso,
    )


def delete_view_command(args: argparse.Namespace) -> dict[str, Any]:
    return delete_view_command_service(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        resolve_view=resolve_view,
    )


def dashboards_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        if args.dashboard:
            dashboards = rows_to_dicts(
                connection.execute(
                    "SELECT * FROM dashboards WHERE dashboard_key = ? AND workspace_id = ? ORDER BY created_at",
                    (args.dashboard, workspace_id),
                )
            )
        else:
            dashboards = rows_to_dicts(connection.execute("SELECT * FROM dashboards WHERE workspace_id = ? ORDER BY created_at", (workspace_id,)))
        widgets = rows_to_dicts(
            connection.execute(
                "SELECT * FROM dashboard_widgets WHERE workspace_id = ? ORDER BY dashboard_key, sort_order",
                (workspace_id,),
            )
        )
    return {
        "ok": True,
        "dashboards": [
            {
                **dashboard,
                "layout": json.loads(dashboard.pop("layout_json")),
                "widgets": [
                    {**widget, "config": json.loads(widget["config_json"])}
                    for widget in widgets
                    if widget["dashboard_key"] == dashboard["dashboard_key"]
                ],
            }
            for dashboard in dashboards
        ],
    }


def dashboard_layout(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    raw = row["layout_json"] if isinstance(row, sqlite3.Row) else row.get("layout_json")
    try:
        layout = json.loads(raw or "{}")
    except json.JSONDecodeError:
        layout = {"version": 1}
    if not isinstance(layout, dict):
        layout = {"version": 1}
    layout.setdefault("version", 1)
    filters = layout.get("globalFilters")
    if not isinstance(filters, list):
        layout["globalFilters"] = []
    return layout


def normalize_filter_rule(rule: dict[str, Any], index: int = 0) -> dict[str, Any]:
    operator = str(rule.get("operator") or "equals")
    if operator not in B_DASHBOARD_FILTER_OPERATORS:
        operator = "equals"
    return {
        "id": str(rule.get("id") or f"filter_{index + 1}"),
        "field": str(rule.get("field") or "").strip(),
        "operator": operator,
        "value": str(rule.get("value") or ""),
        "enabled": rule.get("enabled") is not False,
        "scope": str(rule.get("scope") or "dashboard"),
        "createdAt": str(rule.get("createdAt") or now_iso()),
        "updatedAt": str(rule.get("updatedAt") or rule.get("createdAt") or now_iso()),
    }


def dashboard_filter_fields(connection: sqlite3.Connection, dashboard: sqlite3.Row) -> list[dict[str, Any]]:
    workspace_id = active_workspace_id(connection)
    return rows_to_dicts(
        connection.execute(
            """
            SELECT field_name, role, usage, confidence
            FROM field_semantics
            WHERE table_key = ? AND workspace_id = ?
            ORDER BY
              CASE WHEN usage = 'filterable' THEN 0 WHEN usage = 'groupable' THEN 1 ELSE 2 END,
              field_name
            """,
            (dashboard["default_table_key"], workspace_id),
        )
    )


def dashboard_filters_snapshot(connection: sqlite3.Connection, dashboard_key: str) -> tuple[sqlite3.Row, dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    workspace_id = active_workspace_id(connection)
    dashboard = connection.execute(
        "SELECT * FROM dashboards WHERE dashboard_key = ? AND workspace_id = ?",
        (dashboard_key, workspace_id),
    ).fetchone()
    if not dashboard:
        raise ValueError(f"Unknown dashboard: {dashboard_key}")
    layout = dashboard_layout(dashboard)
    filters = [normalize_filter_rule(item, index) for index, item in enumerate(layout.get("globalFilters", [])) if isinstance(item, dict)]
    layout["globalFilters"] = filters
    fields = dashboard_filter_fields(connection, dashboard)
    return dashboard, layout, filters, fields


def list_filters_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        dashboard, layout, filters, fields = dashboard_filters_snapshot(connection, args.dashboard)
    return {
        "ok": True,
        "dashboard": {
            "dashboard_key": dashboard["dashboard_key"],
            "name": dashboard["name"],
            "default_table_key": dashboard["default_table_key"],
        },
        "filters": filters,
        "availableFields": fields,
        "operators": B_DASHBOARD_FILTER_OPERATORS,
        "layoutVersion": layout.get("version", 1),
    }


def filter_value_required(operator: str) -> bool:
    return operator not in {"empty", "notEmpty"}


def save_dashboard_filters(connection: sqlite3.Connection, dashboard_key: str, layout: dict[str, Any], filters: list[dict[str, Any]]) -> None:
    workspace_id = active_workspace_id(connection)
    layout["globalFilters"] = filters
    connection.execute(
        "UPDATE dashboards SET layout_json = ?, updated_at = ? WHERE dashboard_key = ? AND workspace_id = ?",
        (json.dumps(layout, ensure_ascii=False), now_iso(), dashboard_key, workspace_id),
    )


def build_dashboard_filter_add_plan(
    connection: sqlite3.Connection,
    dashboard_key: str,
    field: str,
    operator: str = "equals",
    value: str = "",
    filter_key: str = "",
    disabled: bool = False,
) -> dict[str, Any]:
    dashboard, _layout, filters, fields = dashboard_filters_snapshot(connection, dashboard_key)
    available = {item["field_name"] for item in fields}
    if field not in available:
        raise ValueError(f"Unknown dashboard field: {field}")
    if operator not in B_DASHBOARD_FILTER_OPERATORS:
        raise ValueError(f"Unsupported dashboard filter operator: {operator}")
    if filter_value_required(operator) and not str(value or "").strip():
        raise ValueError(f"Filter value is required for operator: {operator}")
    now = now_iso()
    proposed = normalize_filter_rule(
        {
            "id": filter_key or unique_key("filter"),
            "field": field,
            "operator": operator,
            "value": value or "",
            "enabled": not disabled,
            "scope": "dashboard",
            "createdAt": now,
            "updatedAt": now,
        }
    )
    return {
        "dashboard": {
            "dashboard_key": dashboard["dashboard_key"],
            "name": dashboard["name"],
            "default_table_key": dashboard["default_table_key"],
        },
        "current": None,
        "proposed": proposed,
        "filtersAfter": [*filters, proposed],
        "availableFields": fields,
    }


def execute_dashboard_filter_add_plan(connection: sqlite3.Connection, dashboard_key: str, filters_after: list[dict[str, Any]]) -> None:
    _dashboard, layout, _filters, _fields = dashboard_filters_snapshot(connection, dashboard_key)
    save_dashboard_filters(connection, dashboard_key, layout, filters_after)


def add_or_set_filter_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        if args.command == "add-filter":
            plan = build_dashboard_filter_add_plan(connection, args.dashboard, args.field, args.operator, args.value or "", "", args.disabled)
            if not args.yes:
                return {"ok": True, "dryRun": True, "requiresConfirmation": True, **plan}
            execute_dashboard_filter_add_plan(connection, args.dashboard, plan["filtersAfter"])
            connection.commit()
            return {"ok": True, "confirmed": True, "operation": args.command, "filter": plan["proposed"], "filters": plan["filtersAfter"]}
        dashboard, layout, filters, fields = dashboard_filters_snapshot(connection, args.dashboard)
        available = {field["field_name"] for field in fields}
        if args.field not in available:
            raise ValueError(f"Unknown dashboard field: {args.field}")
        if filter_value_required(args.operator) and not str(args.value or "").strip():
            raise ValueError(f"Filter value is required for operator: {args.operator}")
        now = now_iso()
        proposed = normalize_filter_rule(
            {
                "id": getattr(args, "filter", None) or unique_key("filter"),
                "field": args.field,
                "operator": args.operator,
                "value": args.value or "",
                "enabled": not args.disabled,
                "scope": "dashboard",
                "createdAt": now,
                "updatedAt": now,
            }
        )
        current = None
        next_filters: list[dict[str, Any]] = []
        replaced = False
        if args.command == "set-filter":
            if not getattr(args, "filter", None):
                raise ValueError("--filter is required for set-filter")
            for item in filters:
                if item["id"] == args.filter:
                    current = item
                    proposed["createdAt"] = item.get("createdAt", now)
                    next_filters.append(proposed)
                    replaced = True
                else:
                    next_filters.append(item)
            if not replaced:
                raise ValueError(f"Unknown filter: {args.filter}")
        else:
            next_filters = [*filters, proposed]
        if not args.yes:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "dashboard": {"dashboard_key": dashboard["dashboard_key"], "name": dashboard["name"]},
                "current": current,
                "proposed": proposed,
                "filtersAfter": next_filters,
            }
        save_dashboard_filters(connection, args.dashboard, layout, next_filters)
        connection.commit()
    return {"ok": True, "confirmed": True, "operation": args.command, "filter": proposed, "filters": next_filters}


def remove_filter_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        dashboard, layout, filters, _fields = dashboard_filters_snapshot(connection, args.dashboard)
        removed = next((item for item in filters if item["id"] == args.filter), None)
        if not removed:
            raise ValueError(f"Unknown filter: {args.filter}")
        next_filters = [item for item in filters if item["id"] != args.filter]
        if not args.yes:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "dashboard": {"dashboard_key": dashboard["dashboard_key"], "name": dashboard["name"]},
                "removed": removed,
                "filtersAfter": next_filters,
            }
        save_dashboard_filters(connection, args.dashboard, layout, next_filters)
        connection.commit()
    return {"ok": True, "confirmed": True, "operation": "remove-filter", "removed": removed, "filters": next_filters}


def clear_filters_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        dashboard, layout, filters, _fields = dashboard_filters_snapshot(connection, args.dashboard)
        if not args.yes:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "dashboard": {"dashboard_key": dashboard["dashboard_key"], "name": dashboard["name"]},
                "removedCount": len(filters),
                "filtersAfter": [],
            }
        save_dashboard_filters(connection, args.dashboard, layout, [])
        connection.commit()
    return {"ok": True, "confirmed": True, "operation": "clear-filters", "removedCount": len(filters), "filters": []}


def dashboard_filter_status(connection: sqlite3.Connection, dashboard_key: str) -> dict[str, Any]:
    dashboard, _layout, filters, fields = dashboard_filters_snapshot(connection, dashboard_key)
    available = {field["field_name"] for field in fields}
    enriched: list[dict[str, Any]] = []
    applicable: list[dict[str, Any]] = []
    stale: list[dict[str, Any]] = []
    disabled: list[dict[str, Any]] = []
    for item in filters:
        field = str(item.get("field") or "")
        status = "disabled" if item.get("enabled") is False else "applicable"
        if field not in available:
            status = "stale"
        enriched_item = {**item, "status": status}
        enriched.append(enriched_item)
        if status == "applicable":
            applicable.append(enriched_item)
        elif status == "stale":
            stale.append(enriched_item)
        else:
            disabled.append(enriched_item)
    return {
        "ok": True,
        "dashboard": {
            "dashboard_key": dashboard["dashboard_key"],
            "name": dashboard["name"],
            "default_table_key": dashboard["default_table_key"],
        },
        "availableFields": fields,
        "filters": enriched,
        "applicableFilters": applicable,
        "staleFilters": stale,
        "disabledFilters": disabled,
    }


def remove_stale_filters_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        dashboard, layout, filters, _fields = dashboard_filters_snapshot(connection, args.dashboard)
        status = dashboard_filter_status(connection, args.dashboard)
        stale_ids = {item["id"] for item in status["staleFilters"]}
        next_filters = [item for item in filters if item["id"] not in stale_ids]
        if not args.yes:
            return {
                **status,
                "dryRun": True,
                "requiresConfirmation": True,
                "removedCount": len(stale_ids),
                "filtersAfter": next_filters,
            }
        save_dashboard_filters(connection, dashboard["dashboard_key"], layout, next_filters)
        connection.commit()
    return {
        "ok": True,
        "confirmed": True,
        "operation": "remove-stale-filters",
        "dashboard": status["dashboard"],
        "removedFilters": status["staleFilters"],
        "removedCount": len(stale_ids),
        "filters": next_filters,
    }


def add_index_reason(reasons: dict[str, set[str]], field: str, reason: str) -> None:
    if not field:
        return
    reasons.setdefault(field, set()).add(reason)


def collect_index_reasons(connection: sqlite3.Connection, table_key: str) -> dict[str, set[str]]:
    workspace_id = active_workspace_id(connection)
    reasons: dict[str, set[str]] = {}
    for row in connection.execute(
        """
        SELECT field_name, role, usage
        FROM field_semantics
        WHERE table_key = ? AND workspace_id = ?
        """,
        (table_key, workspace_id),
    ).fetchall():
        role = str(row["role"] or "")
        usage = str(row["usage"] or "")
        if role in {"identity_key", "identifier"}:
            add_index_reason(reasons, row["field_name"], "identity-key")
        if role in {"event_time", "time"}:
            add_index_reason(reasons, row["field_name"], "event-time")
        if role == "measure":
            add_index_reason(reasons, row["field_name"], "measure")
        if usage == "filterable":
            add_index_reason(reasons, row["field_name"], "semantic-filterable")
        if usage == "groupable":
            add_index_reason(reasons, row["field_name"], "semantic-groupable")
        if usage == "joinable":
            add_index_reason(reasons, row["field_name"], "relationship-key")

    for row in connection.execute(
        """
        SELECT left_table_key, right_table_key, left_field, right_field
        FROM relationships
        WHERE workspace_id = ? AND (left_table_key = ? OR right_table_key = ?)
        """,
        (workspace_id, table_key, table_key),
    ).fetchall():
        if row["left_table_key"] == table_key:
            add_index_reason(reasons, row["left_field"], "relationship-key")
        if row["right_table_key"] == table_key:
            add_index_reason(reasons, row["right_field"], "relationship-key")

    policy = connection.execute(
        "SELECT unique_fields_json FROM import_policies WHERE table_key = ? AND workspace_id = ?",
        (table_key, workspace_id),
    ).fetchone()
    if policy:
        try:
            unique_fields = json.loads(policy["unique_fields_json"] or "[]")
        except json.JSONDecodeError:
            unique_fields = []
        for field in unique_fields if isinstance(unique_fields, list) else []:
            add_index_reason(reasons, str(field), "import-unique-key")

    for dashboard in connection.execute(
        "SELECT layout_json FROM dashboards WHERE default_table_key = ? AND workspace_id = ?",
        (table_key, workspace_id),
    ).fetchall():
        layout = dashboard_layout(dashboard)
        for rule in layout.get("globalFilters", []):
            if isinstance(rule, dict):
                add_index_reason(reasons, str(rule.get("field") or ""), "dashboard-filter")

    for widget in connection.execute(
        "SELECT config_json FROM dashboard_widgets WHERE table_key = ? AND workspace_id = ?",
        (table_key, workspace_id),
    ).fetchall():
        config = parse_json_object(widget["config_json"], {})
        if not isinstance(config, dict):
            continue
        for key in ("dimension", "group", "measure"):
            add_index_reason(reasons, str(config.get(key) or ""), "widget-dimension" if key != "measure" else "measure")
        for rule in config.get("filters") if isinstance(config.get("filters"), list) else []:
            if isinstance(rule, dict):
                add_index_reason(reasons, str(rule.get("field") or ""), "widget-filter")
    return reasons


def recommend_indexes_for_table(connection: sqlite3.Connection, registry: sqlite3.Row, limit: int) -> list[dict[str, Any]]:
    physical_table = registry["physical_table"]
    columns = set(table_columns(connection, physical_table))
    reasons_by_field = collect_index_reasons(connection, registry["table_key"])
    recommendations: list[dict[str, Any]] = []
    for field, reasons in reasons_by_field.items():
        if field not in columns:
            continue
        score = sum(B_INDEX_REASON_WEIGHTS.get(reason, 0) for reason in reasons)
        if score <= 0:
            continue
        index_key = slug(f"idx_{physical_table}_{field}")[:62]
        recommendations.append(
            {
                "tableKey": registry["table_key"],
                "tableName": registry["display_name"],
                "physicalTable": physical_table,
                "field": field,
                "indexKey": index_key,
                "score": score,
                "reasons": sorted(reasons),
                "rowCount": registry["row_count"],
                "engine": "duckdb",
                "sideEffectBoundary": "dry-run-until---yes",
            }
        )
    recommendations.sort(key=lambda item: (-item["score"], str(item["field"])))
    return recommendations[:limit]


def recommend_indexes_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        if args.table:
            registries = [resolve_table_registry(connection, args.table)]
        else:
            workspace_id = active_workspace_id(connection)
            registries = connection.execute(
                "SELECT * FROM table_registry WHERE workspace_id = ? ORDER BY row_count DESC, table_key",
                (workspace_id,),
            ).fetchall()
        recommendations: list[dict[str, Any]] = []
        per_table_limit = max(1, int(args.limit or 12))
        for registry in registries:
            recommendations.extend(recommend_indexes_for_table(connection, registry, per_table_limit))
    recommendations.sort(key=lambda item: (-item["score"], -int(item.get("rowCount") or 0), str(item["tableKey"]), str(item["field"])))
    return {
        "ok": True,
        "engine": "duckdb",
        "dryRun": True,
        "recommendations": recommendations[: max(1, int(args.limit or 12))],
        "source": "recommend-indexes adapted to the workspace DuckDB runtime",
    }


def build_index_plan(connection: sqlite3.Connection, table: str, field: str, index_key: str = "") -> tuple[dict[str, Any], list[str]]:
    registry = resolve_table_registry(connection, table)
    physical_table = registry["physical_table"]
    columns = table_columns(connection, physical_table)
    if field not in columns:
        raise ValueError(f"Unknown field for index: {field}")
    recommendations = recommend_indexes_for_table(connection, registry, 100)
    recommendation = next((item for item in recommendations if item["field"] == field), None)
    resolved_index_key = slug(index_key or (recommendation or {}).get("indexKey") or f"idx_{physical_table}_{field}")[:62]
    proposed = {
        "tableKey": registry["table_key"],
        "tableName": registry["display_name"],
        "physicalTable": physical_table,
        "field": field,
        "indexKey": resolved_index_key,
        "engine": "duckdb",
        "compiledSql": f"CREATE INDEX IF NOT EXISTS {quote_identifier(resolved_index_key)} ON {quote_identifier(physical_table)} ({quote_identifier(field)})",
        "recommendation": recommendation,
    }
    return proposed, columns


def execute_index_plan(connection: sqlite3.Connection, proposed: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    try:
        import duckdb  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise DuckDBUnavailable(str(exc)) from exc
    DUCKDB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(DUCKDB_PATH)) as duck_connection:
        synced_rows = sync_table_to_duckdb(connection, duck_connection, str(proposed["physicalTable"]), columns)
        duck_connection.execute(str(proposed["compiledSql"]))
    return {"ok": True, "confirmed": True, "createdIndex": proposed, "syncedRows": synced_rows}


def create_index_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        proposed, columns = build_index_plan(connection, args.table, args.field, args.index)
        if not args.yes:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "proposed": proposed}
        return execute_index_plan(connection, proposed, columns)


def workbench_command(args: argparse.Namespace) -> dict[str, Any]:
    runtime = duckdb_status(DUCKDB_PATH)
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        navigation = list_navigation_modules(connection, include_disabled=False)
        tables = rows_to_dicts(
            connection.execute(
                """
                SELECT table_key, workspace_id, display_name, source_file, row_count, column_count, created_at
                FROM table_registry
                WHERE workspace_id = ?
                ORDER BY display_name
                """,
                (workspace_id,),
            )
        )
        fields = rows_to_dicts(
            connection.execute(
                """
                SELECT workspace_id, table_key, field_name, role, usage, confidence, tags_json, usage_json, source, note, updated_at
                FROM field_semantics
                WHERE workspace_id = ?
                ORDER BY table_key, field_name
                """,
                (workspace_id,),
            )
        )
        metrics = rows_to_dicts(
            connection.execute(
                """
                SELECT metric_key, workspace_id, label, table_key, measure, aggregation, dimension, time_field, value_format,
                       filters_json, description, source, enabled, formula_text, formula_ast_json,
                       dependencies_json, metric_type, created_at, updated_at
                FROM metric_definitions
                WHERE workspace_id = ?
                ORDER BY table_key, metric_key
                """,
                (workspace_id,),
            )
        )
        formulas = rows_to_dicts(
            connection.execute(
                """
                SELECT field_key, workspace_id, table_key, name, mode, formula_text, formula_ast_json, dependencies_json,
                       value_format, description, source, enabled, created_at, updated_at
                FROM calculated_fields
                WHERE workspace_id = ?
                ORDER BY table_key, name
                """,
                (workspace_id,),
            )
        )
        relationships = rows_to_dicts(
            connection.execute(
                """
                SELECT relation_key, workspace_id, name, left_table_key, right_table_key, left_field, right_field, join_type, confidence, created_at
                FROM relationships
                WHERE workspace_id = ?
                ORDER BY relation_key
                """,
                (workspace_id,),
            )
        )
        relationship_recommendations = recommend_relationships_for_connection(connection, min(max(args.limit, 6), 12))
        import_jobs = rows_to_dicts(
            connection.execute(
                """
                SELECT job_key, workspace_id, source_file, table_key, mode, status, row_count, result_json, created_at
                FROM import_jobs
                WHERE workspace_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (workspace_id, args.limit),
            )
        )
        import_policies = rows_to_dicts(
            connection.execute(
                """
                SELECT table_key, workspace_id, unique_fields_json, conflict_rule, updated_at
                FROM import_policies
                WHERE workspace_id = ?
                ORDER BY table_key
                """,
                (workspace_id,),
            )
        )
        connectors = load_connectors(connection)
        preferences = load_user_preferences(connection)
        theme_palettes = list_theme_palettes(connection)
        saved_view_rows = connection.execute(
            """
            SELECT *
            FROM saved_views
            WHERE workspace_id = ?
            ORDER BY table_key, sort_order, created_at
            LIMIT ?
            """,
            (workspace_id, max(args.limit, 24)),
        ).fetchall()
        source_intelligence_runs = list_source_intelligence_runs(connection, workspace_id=workspace_id, limit=args.limit)
    for table in tables:
        table["source_file"] = source_label(table["source_file"])
    for job in import_jobs:
        job["source_file"] = source_label(job["source_file"])
        job["result"] = json.loads(job.pop("result_json"))
    for policy in import_policies:
        policy["uniqueFields"] = json.loads(policy.pop("unique_fields_json"))
    saved_views = []
    with open_db() as view_connection:
        for row in saved_view_rows:
            saved_views.append(saved_view_summary(view_connection, row))
    for formula in formulas:
        formula["formulaAst"] = json.loads(formula.pop("formula_ast_json") or "{}")
        formula["dependencies"] = json.loads(formula.pop("dependencies_json") or "[]")
        formula["enabled"] = bool(formula["enabled"])
    return {
        "ok": True,
        "navigation": navigation,
        "tables": tables,
        "fields": fields,
        "metrics": metrics,
        "formulas": formulas,
        "relationships": relationships,
        "relationshipRecommendations": relationship_recommendations,
        "importJobs": import_jobs,
        "importPolicies": import_policies,
        "connectors": connectors,
        "preferences": preferences,
        "themePalettes": theme_palettes,
        "savedViews": saved_views,
        "sourceIntelligenceRuns": source_intelligence_runs,
        "fieldRoles": ["identity_key", "event_time", "dimension", "measure", "status"],
        "fieldUsages": ["joinable", "filterable", "groupable", "aggregatable"],
        "safeAggregations": sorted(SAFE_AGGREGATIONS),
        "queryRuntime": runtime,
        "formulaDsl": {
            "allowedFunctions": sorted({"SAFE_DIVIDE", "SUM", "AVG", "MIN", "MAX", "COUNT", "COUNT_DISTINCT", "ABS", "ROUND", "COALESCE", "CONCAT", "IF"}),
            "fieldReference": "[field_name]",
            "acceptsSql": False,
        },
    }


def list_navigation_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        navigation = list_navigation_modules(connection, include_disabled=args.all)
    return {"ok": True, "navigation": navigation, "count": len(navigation)}


def navigation_operation_command(args: argparse.Namespace) -> dict[str, Any]:
    op = args.op
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        ensure_navigation_modules(connection)
        row = connection.execute(
            "SELECT * FROM navigation_modules WHERE module_key = ? AND workspace_id = ?",
            (args.module, workspace_id),
        ).fetchone()
        if not row:
            raise ValueError(f"Unknown navigation module: {args.module}")
        current = navigation_module_payload(row)
        proposed = dict(current)
        if op == "rename":
            name = str(args.name or "").strip()
            if not name:
                raise ValueError("Navigation module name is required.")
            proposed["name"] = name
        elif op == "move":
            proposed["sort"] = int(args.sort)
        elif op == "hide":
            proposed["enabled"] = False
        elif op == "show":
            proposed["enabled"] = True
        else:
            raise ValueError(f"Unsupported navigation operation: {op}")
        if not args.yes:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "operation": op, "currentModule": current, "proposedModule": proposed}
        now = now_iso()
        if op == "rename":
            connection.execute(
                "UPDATE navigation_modules SET name = ?, updated_at = ? WHERE module_key = ? AND workspace_id = ?",
                (proposed["name"], now, args.module, workspace_id),
            )
            if current["type"] == "table" and current["tableKey"]:
                connection.execute(
                    "UPDATE table_registry SET display_name = ? WHERE table_key = ? AND workspace_id = ?",
                    (proposed["name"], current["tableKey"], workspace_id),
                )
                connection.execute(
                    "UPDATE source_runs SET name = ? WHERE table_key = ? AND workspace_id = ?",
                    (proposed["name"], current["tableKey"], workspace_id),
                )
            if current["type"] == "dashboard" and current["dashboardKey"]:
                connection.execute(
                    "UPDATE dashboards SET name = ?, updated_at = ? WHERE dashboard_key = ? AND workspace_id = ?",
                    (proposed["name"], now, current["dashboardKey"], workspace_id),
                )
        elif op == "move":
            connection.execute(
                "UPDATE navigation_modules SET sort_order = ?, updated_at = ? WHERE module_key = ? AND workspace_id = ?",
                (proposed["sort"], now, args.module, workspace_id),
            )
        elif op in {"hide", "show"}:
            connection.execute(
                "UPDATE navigation_modules SET enabled = ?, updated_at = ? WHERE module_key = ? AND workspace_id = ?",
                (1 if proposed["enabled"] else 0, now, args.module, workspace_id),
            )
        connection.commit()
        saved = connection.execute(
            "SELECT * FROM navigation_modules WHERE module_key = ? AND workspace_id = ?",
            (args.module, workspace_id),
        ).fetchone()
    return {"ok": True, "confirmed": True, "operation": op, "navigationModule": navigation_module_payload(saved)}


def dashboard_widget_catalog_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        latest_run = latest_source_intelligence_summary(connection, workspace_id=workspace_id)
        dashboard_count = connection.execute("SELECT COUNT(*) FROM dashboards WHERE workspace_id = ?", (workspace_id,)).fetchone()[0]
        dashboard_keys = [row["dashboard_key"] for row in connection.execute("SELECT dashboard_key FROM dashboards WHERE workspace_id = ?", (workspace_id,)).fetchall()]
        if dashboard_keys:
            placeholders = ", ".join("?" for _ in dashboard_keys)
            widget_count = connection.execute(
                f"SELECT COUNT(*) FROM dashboard_widgets WHERE workspace_id = ? AND dashboard_key IN ({placeholders})",
                [workspace_id, *dashboard_keys],
            ).fetchone()[0]
        else:
            widget_count = 0
        relationship_count = connection.execute("SELECT COUNT(*) FROM relationships WHERE workspace_id = ?", (workspace_id,)).fetchone()[0]
        metric_count = connection.execute("SELECT COUNT(*) FROM metric_definitions WHERE workspace_id = ?", (workspace_id,)).fetchone()[0]
    payload = build_dashboard_widget_catalog_payload(
        b_project_root=B_PROJECT_ROOT,
        metadata_store=DB_PATH,
        latest_source_intelligence_run=latest_run,
        workspace_counts={
            "dashboards": dashboard_count,
            "widgets": widget_count,
            "relationships": relationship_count,
            "metrics": metric_count,
        },
    )
    payload["erpUnitLibrary"] = build_erp_unit_library_catalog_payload(include_units=False)
    return payload


def field_names_by_usage(connection: sqlite3.Connection, table_key: str, usage: str) -> list[str]:
    workspace_id = active_workspace_id(connection)
    rows = connection.execute(
        """
        SELECT field_name
        FROM field_semantics
        WHERE table_key = ? AND usage = ? AND workspace_id = ?
        ORDER BY confidence DESC, field_name
        """,
        (table_key, usage, workspace_id),
    ).fetchall()
    return [row["field_name"] for row in rows]


def field_names_by_role(connection: sqlite3.Connection, table_key: str, role: str) -> list[str]:
    workspace_id = active_workspace_id(connection)
    rows = connection.execute(
        """
        SELECT field_name
        FROM field_semantics
        WHERE table_key = ? AND role = ? AND workspace_id = ?
        ORDER BY confidence DESC, field_name
        """,
        (table_key, role, workspace_id),
    ).fetchall()
    return [row["field_name"] for row in rows]


def table_display_name(connection: sqlite3.Connection, table_key: str) -> str:
    registry = registry_for_table(connection, table_key)
    return registry["display_name"] if registry else table_key


def preferred_table_key(connection: sqlite3.Connection, table_key: str | None = None) -> str:
    if table_key:
        registry = registry_for_table(connection, table_key)
        if not registry:
            raise ValueError(f"Unknown table: {table_key}")
        return table_key
    workspace_id = active_workspace_id(connection)
    row = connection.execute(
        "SELECT table_key FROM table_registry WHERE workspace_id = ? ORDER BY row_count DESC, table_key LIMIT 1",
        (workspace_id,),
    ).fetchone()
    if not row:
        raise ValueError("No source table is available.")
    return row["table_key"]


def dashboard_exists(connection: sqlite3.Connection, dashboard_key: str) -> bool:
    workspace_id = active_workspace_id(connection)
    return bool(
        connection.execute(
            "SELECT 1 FROM dashboards WHERE dashboard_key = ? AND workspace_id = ?",
            (dashboard_key, workspace_id),
        ).fetchone()
    )


def dashboard_widget_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["config"] = json.loads(item.pop("config_json") or "{}")
    return item


def first_saved_view(connection: sqlite3.Connection, table_key: str) -> dict[str, Any] | None:
    workspace_id = active_workspace_id(connection)
    row = connection.execute(
        "SELECT * FROM saved_views WHERE table_key = ? AND workspace_id = ? ORDER BY is_default DESC, sort_order, created_at LIMIT 1",
        (table_key, workspace_id),
    ).fetchone()
    return saved_view_summary(connection, row) if row else None


def widget_recommendations_for_table(connection: sqlite3.Connection, table_key: str, limit: int) -> dict[str, Any]:
    registry = registry_for_table(connection, table_key)
    if not registry:
        raise ValueError(f"Unknown table: {table_key}")
    columns = table_columns(connection, registry["physical_table"])
    measures = [field for field in field_names_by_usage(connection, table_key, "aggregatable") if field in columns]
    dimensions = [field for field in field_names_by_usage(connection, table_key, "groupable") if field in columns]
    filterable = [field for field in field_names_by_usage(connection, table_key, "filterable") if field in columns]
    dates = [field for field in field_names_by_role(connection, table_key, "event_time") if field in columns]
    identities = [field for field in field_names_by_role(connection, table_key, "identity_key") if field in columns]
    measure = measures[0] if measures else ""
    dimension = dimensions[0] if dimensions else (filterable[0] if filterable else (columns[0] if columns else ""))
    time_field = dates[0] if dates else dimension
    view = first_saved_view(connection, table_key)
    table_name = registry["display_name"]
    recommendations: list[dict[str, Any]] = []
    if measure:
        recommendations.append({
            "type": "metric",
            "title": f"{table_name} {measure}",
            "reason": "Field semantics marked this as an aggregatable measure.",
            "tableKey": table_key,
            "dimension": "",
            "measure": measure,
            "aggregation": "sum",
            "valueFormat": "auto",
            "topN": 1,
        })
    if dimension and measure:
        recommendations.append({
            "type": "bar",
            "title": f"{dimension} by {measure}",
            "reason": "Category ranking from a groupable field and primary measure.",
            "tableKey": table_key,
            "dimension": dimension,
            "measure": measure,
            "aggregation": "sum",
            "topN": 12,
        })
    if time_field and measure:
        recommendations.append({
            "type": "line",
            "title": f"{measure} trend",
            "reason": "Trend chart from event-time semantics where available.",
            "tableKey": table_key,
            "dimension": time_field,
            "measure": measure,
            "aggregation": "sum",
            "topN": 12,
        })
    if dimension and measure:
        recommendations.append({
            "type": "pie",
            "title": f"{dimension} mix",
            "reason": "Composition view for the leading groupable field.",
            "tableKey": table_key,
            "dimension": dimension,
            "measure": measure,
            "aggregation": "sum",
            "topN": 8,
        })
    if view:
        recommendations.append({
            "type": "table",
            "title": f"{view['name']} details",
            "reason": "Saved view can be placed directly on the dashboard.",
            "tableKey": table_key,
            "viewKey": view["view_key"],
            "dataMode": "view",
            "columns": view["config"].get("columns", columns[:6]),
            "aggregation": "count",
            "topN": 100,
        })
    else:
        recommendations.append({
            "type": "table",
            "title": f"{table_name} details",
            "reason": "Detail table from the source columns.",
            "tableKey": table_key,
            "columns": columns[:6],
            "aggregation": "count",
            "topN": 100,
        })
    slicer_field = filterable[0] if filterable else dimension
    if slicer_field:
        recommendations.append({
            "type": "slicer",
            "title": f"{slicer_field} filter",
            "reason": "Filterable field promoted to a canvas slicer.",
            "tableKey": table_key,
            "dimension": slicer_field,
            "aggregation": "count",
            "topN": 12,
        })
    recommendations.append({
        "type": "text",
        "title": f"{table_name} evidence note",
        "reason": "Narrative note for AIBI evidence and Agent context.",
        "tableKey": table_key,
        "textContent": f"Source table: {table_name}. Evidence is available through source intelligence, query runtime, and saved views.",
        "aggregation": "count",
    })
    return {
        "ok": True,
        "tableKey": table_key,
        "tableName": table_name,
        "fields": {
            "columns": columns,
            "measures": measures,
            "dimensions": dimensions,
            "dateDimensions": dates,
            "filterable": filterable,
            "identityKeys": identities,
        },
        "recommendations": recommendations[: max(1, min(limit, 12))],
    }


def widget_filters_from_args(raw_filters: list[str], columns: list[str]) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = []
    available = set(columns)
    for index, raw in enumerate(raw_filters):
        parsed = parse_query_filter(raw)
        field = parsed["field"]
        operator = parsed["operator"] if parsed["operator"] in B_DASHBOARD_FILTER_OPERATORS else "contains"
        value = str(parsed.get("value") or "")
        if field not in available:
            raise ValueError(f"Unknown widget filter field: {field}")
        if filter_value_required(operator) and not value.strip():
            raise ValueError(f"Filter value is required for operator: {operator}")
        filters.append(normalize_filter_rule({
            "id": unique_key("widget_filter"),
            "field": field,
            "operator": operator,
            "value": value,
            "scope": "widget",
        }, index))
    return filters


def build_widget_proposal(
    connection: sqlite3.Connection,
    dashboard_key: str,
    widget_type: str,
    options: dict[str, Any],
) -> dict[str, Any]:
    return build_dashboard_widget_proposal_service(
        connection,
        dashboard_key,
        widget_type,
        options,
        dashboard_exists=dashboard_exists,
        resolve_view=resolve_view,
        preferred_table_key=preferred_table_key,
        registry_for_table=registry_for_table,
        active_workspace_id=active_workspace_id,
        unique_key=unique_key,
        resolve_dashboard_widget_key=resolve_dashboard_widget_key,
        next_dashboard_widget_sort_order=next_dashboard_widget_sort_order,
    )


def resolve_relationship_for_widget(connection: sqlite3.Connection, relation_key: str | None = None) -> dict[str, Any]:
    workspace_id = active_workspace_id(connection)
    if relation_key:
        row = connection.execute(
            "SELECT * FROM relationships WHERE relation_key = ? AND workspace_id = ?",
            (relation_key, workspace_id),
        ).fetchone()
    else:
        row = connection.execute(
            """
            SELECT *
            FROM relationships
            WHERE workspace_id = ?
            ORDER BY confidence DESC, created_at DESC, relation_key
            LIMIT 1
            """,
            (workspace_id,),
        ).fetchone()
    if not row:
        raise ValueError("No saved relationship is available. Save a relationship before adding a relationship widget.")
    return dict(row)


def build_relationship_widget_proposal(
    connection: sqlite3.Connection,
    dashboard_key: str,
    widget_type: str,
    options: dict[str, Any],
) -> dict[str, Any]:
    return build_dashboard_relationship_widget_proposal_service(
        connection,
        dashboard_key,
        widget_type,
        options,
        safe_aggregations=SAFE_AGGREGATIONS,
        dashboard_exists=dashboard_exists,
        resolve_relationship_for_widget=resolve_relationship_for_widget,
        registry_for_table=registry_for_table,
        table_columns=table_columns,
        table_display_name=table_display_name,
        active_workspace_id=active_workspace_id,
        unique_key=unique_key,
        resolve_dashboard_widget_key=resolve_dashboard_widget_key,
        next_dashboard_widget_sort_order=next_dashboard_widget_sort_order,
    )


def recommend_widgets_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        if args.all:
            workspace_id = active_workspace_id(connection)
            tables = rows_to_dicts(
                connection.execute(
                    "SELECT table_key FROM table_registry WHERE workspace_id = ? ORDER BY display_name",
                    (workspace_id,),
                )
            )
            payloads = [widget_recommendations_for_table(connection, row["table_key"], args.limit) for row in tables]
            return {
                "ok": True,
                "mode": "all",
                "tables": payloads,
                "recommendations": [
                    {**recommendation, "tableKey": payload["tableKey"], "tableName": payload["tableName"]}
                    for payload in payloads
                    for recommendation in payload["recommendations"]
                ],
            }
        table_key = preferred_table_key(connection, args.table)
        return widget_recommendations_for_table(connection, table_key, args.limit)


def add_recommended_widgets_command(args: argparse.Namespace) -> dict[str, Any]:
    return add_recommended_dashboard_widgets_service(
        dashboard_key=args.dashboard,
        table_key=args.table,
        limit=args.limit,
        allow_duplicates=args.allow_duplicates,
        confirm=args.yes,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        preferred_table_key=preferred_table_key,
        widget_recommendations_for_table=widget_recommendations_for_table,
        build_widget_proposal=build_widget_proposal,
        insert_dashboard_widget=insert_dashboard_widget,
    )


def parse_json_array_arg(raw: str | None, label: str) -> list[Any]:
    if raw is None or raw == "":
        return []
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} must be valid JSON: {error}") from error
    if not isinstance(parsed, list):
        raise ValueError(f"{label} must be a JSON array")
    return parsed


def save_dashboard_modules_command(args: argparse.Namespace) -> dict[str, Any]:
    widgets = parse_json_array_arg(args.widgets_json, "widgets-json")
    layout_items = parse_json_array_arg(args.layout_json, "layout-json")
    filter_items = parse_json_array_arg(args.filters_json, "filters-json")
    if args.canvas_width_mode not in {"stretch", "center"}:
        raise ValueError("--canvas-width-mode must be stretch or center")
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        dashboard = connection.execute(
            "SELECT * FROM dashboards WHERE dashboard_key = ? AND workspace_id = ?",
            (args.dashboard, workspace_id),
        ).fetchone()
        default_table_key = args.default_table or (dashboard["default_table_key"] if dashboard else "")
        if default_table_key:
            default_table_key = preferred_table_key(connection, default_table_key)
        elif widgets:
            default_table_key = preferred_table_key(connection, None)
        layout_by_id = {
            str(item.get("i") or ""): item
            for item in layout_items
            if isinstance(item, dict) and str(item.get("i") or "").strip()
        }
        proposed_widgets: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for index, raw_widget in enumerate(widgets):
            if not isinstance(raw_widget, dict):
                skipped.append({"index": index, "reason": "widget is not an object"})
                continue
            try:
                proposed_widgets.append(
                    dashboard_module_widget_from_payload(
                        connection,
                        args.dashboard,
                        raw_widget,
                        index,
                        default_table_key,
                        layout_by_id,
                        workspace_id=workspace_id,
                        preferred_table_key=preferred_table_key,
                        table_display_name=table_display_name,
                        unique_key=unique_key,
                    )
                )
            except ValueError as error:
                skipped.append({"index": index, "reason": str(error)})
        filters = [
            normalize_filter_rule(item, index)
            for index, item in enumerate(filter_items)
            if isinstance(item, dict) and str(item.get("field") or "").strip()
        ]
        layout = dashboard_layout(dashboard) if dashboard else {"version": 1}
        layout["version"] = 1
        layout["grid"] = layout.get("grid") or "12-col"
        layout["widgets"] = [widget["widget_key"] for widget in proposed_widgets]
        layout["widgetLayout"] = layout_items
        layout["canvasWidthMode"] = args.canvas_width_mode
        layout["globalFilters"] = filters
        dashboard_name = args.name or (dashboard["name"] if dashboard else ("经营证据看板" if args.dashboard == "default" else args.dashboard))
        proposed = {
            "dashboardKey": args.dashboard,
            "dashboardName": dashboard_name,
            "defaultTableKey": default_table_key,
            "canvasWidthMode": args.canvas_width_mode,
            "widgetCount": len(proposed_widgets),
            "layoutCount": len(layout_items),
            "filterCount": len(filters),
            "skippedCount": len(skipped),
        }
        if not args.yes:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "proposed": proposed,
                "proposedWidgets": proposed_widgets,
                "proposedFilters": filters,
                "skippedWidgets": skipped,
            }
        now = now_iso()
        save_dashboard_with_widgets(
            connection,
            workspace_id=workspace_id,
            dashboard_key=args.dashboard,
            dashboard_name=dashboard_name,
            default_table_key=default_table_key,
            layout=layout,
            widgets=proposed_widgets,
            now=now,
        )
        connection.commit()
        ensure_navigation_modules(connection)
        saved_dashboard = dashboard_snapshot(connection, workspace_id=workspace_id, dashboard_key=args.dashboard)
    return {
        "ok": True,
        "confirmed": True,
        "savedDashboardKey": args.dashboard,
        "savedDashboardModules": len(proposed_widgets),
        "savedDashboardFilters": len(filters),
        "skippedWidgets": skipped,
        "dashboard": saved_dashboard,
    }


def template_widget_layout(widget_type: str, index: int) -> dict[str, Any]:
    return template_widget_layout_service(widget_type, index)


def table_template_fields(connection: sqlite3.Connection, table_key: str) -> dict[str, Any]:
    return table_template_fields_service(
        connection,
        table_key,
        registry_for_table=registry_for_table,
        table_columns=table_columns,
        field_names_by_usage=field_names_by_usage,
        field_names_by_role=field_names_by_role,
    )


def build_business_analysis_templates(connection: sqlite3.Connection, table_key: str | None = None, limit: int = 12, template_key: str = "business") -> dict[str, Any]:
    return build_business_analysis_templates_service(
        connection,
        table_key,
        limit,
        active_workspace_id=active_workspace_id,
        rows_to_dicts=rows_to_dicts,
        preferred_table_key=preferred_table_key,
        slug=slug,
        table_template_fields=table_template_fields,
        template_key=template_key,
    )


def build_business_dashboard_payload(connection: sqlite3.Connection, table_key: str | None = None, limit: int = 10, template_key: str = "business") -> dict[str, Any]:
    return build_business_dashboard_payload_service(
        connection,
        table_key,
        limit,
        build_business_analysis_templates=build_business_analysis_templates,
        preferred_table_key=preferred_table_key,
        template_key=template_key,
    )


def write_business_dashboard(
    connection: sqlite3.Connection,
    dashboard_key: str,
    dashboard_name: str,
    default_table_key: str,
    widgets: list[dict[str, Any]],
    layout_items: list[dict[str, Any]],
) -> dict[str, Any]:
    return write_business_dashboard_service(
        connection,
        dashboard_key,
        dashboard_name,
        default_table_key,
        widgets,
        layout_items,
        active_workspace_id=active_workspace_id,
        preferred_table_key=preferred_table_key,
        table_display_name=table_display_name,
        unique_key=unique_key,
        now_iso=now_iso,
    )


def business_dashboard_command(args: argparse.Namespace) -> dict[str, Any]:
    result = run_business_dashboard_command_service(
        op=args.op,
        dashboard_key=args.dashboard,
        table_key=args.table,
        template_key=args.template,
        limit=args.limit,
        name=args.name,
        confirm=args.yes,
        open_db=open_db,
        build_business_dashboard_payload=build_business_dashboard_payload,
        active_workspace_id=active_workspace_id,
        unique_key=unique_key,
        write_business_dashboard=write_business_dashboard,
        ensure_navigation_modules=ensure_navigation_modules,
    )
    if args.op == "draft" or result.get("dryRun"):
        if args.op == "draft":
            result.setdefault("dryRun", True)
            result.setdefault("requiresConfirmation", False)
        with open_db() as connection:
            workspace_id = active_workspace_id(connection)
        draft = result.get("draft") if isinstance(result.get("draft"), dict) else {}
        result["evidenceBundle"] = write_evidence_bundle(
            command="business-dashboard",
            workspace_id=workspace_id,
            title=f"Business dashboard {args.op}: {draft.get('templateKey') or args.template}",
            status="draft" if args.op == "draft" else "dry-run",
            summary={
                "op": args.op,
                "templateKey": draft.get("templateKey") or args.template,
                "defaultTableKey": draft.get("defaultTableKey") or args.table,
                "templateCount": result.get("templateCount"),
                "widgetCount": len(draft.get("widgets") or []),
                "categoryCount": len(draft.get("categories") or []),
                "missingRequirementCount": len(draft.get("missingRequirements") or []),
            },
            payload={
                "draft": draft,
                "proposed": result.get("proposed"),
            },
        )
    return result


def erp_unit_library_command(args: argparse.Namespace) -> dict[str, Any]:
    catalog = build_erp_unit_library_catalog_payload(include_units=not args.summary)
    if not args.select:
        return {"ok": True, "catalog": catalog}
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        table_rows = rows_to_dicts(
            connection.execute(
                "SELECT * FROM table_registry WHERE workspace_id = ? ORDER BY row_count DESC, table_key",
                (workspace_id,),
            )
        )
        fields_by_key = {row["table_key"]: table_template_fields(connection, row["table_key"]) for row in table_rows}
        if not table_rows:
            table_rows, fields_by_key = source_profile_table_inputs(connection, workspace_id)
        preferred = ""
        if args.table:
            try:
                preferred = preferred_table_key(connection, args.table)
            except ValueError:
                if any(row.get("table_key") == args.table for row in table_rows):
                    preferred = args.table
                else:
                    raise
        selection = build_erp_dashboard_unit_templates(
            table_rows,
            fields_by_key,
            preferred_table_key_value=preferred,
            limit=args.limit,
            slug=slug,
        )
    return {
        "ok": True,
        "catalog": catalog,
        "selection": selection,
    }


def build_agent_dashboard_create_draft(connection: sqlite3.Connection, table_key: str | None, prompt: str, limit: int = 8, template_key: str = "business") -> dict[str, Any]:
    return build_agent_dashboard_create_draft_service(
        connection,
        table_key,
        prompt,
        limit,
        template_key=template_key,
        build_business_dashboard_payload=build_business_dashboard_payload,
    )


def add_widget_command(args: argparse.Namespace) -> dict[str, Any]:
    options = {
        "widgetKey": args.widget,
        "tableKey": args.table,
        "viewKey": args.view,
        "title": args.title,
        "subtitle": args.subtitle,
        "dimension": args.dimension,
        "measure": args.measure,
        "aggregation": args.agg,
        "topN": args.top_n,
        "valueFormat": args.value_format,
        "textContent": args.text_content,
        **widget_style_options_from_args(args),
    }
    return add_dashboard_widget_service(
        dashboard_key=args.dashboard,
        widget_type=args.type,
        options=options,
        confirm=args.yes,
        open_db=open_db,
        build_widget_proposal=build_widget_proposal,
        insert_dashboard_widget=insert_dashboard_widget,
    )


def add_relationship_widget_command(args: argparse.Namespace) -> dict[str, Any]:
    options = {
        "widgetKey": args.widget,
        "relationship": args.relationship,
        "title": args.title,
        "subtitle": args.subtitle,
        "group": args.group,
        "measure": args.measure,
        "aggregation": args.agg,
        "topN": args.top_n,
        "valueFormat": args.value_format,
        **widget_style_options_from_args(args),
    }
    return add_dashboard_relationship_widget_service(
        dashboard_key=args.dashboard,
        widget_type=args.type,
        options=options,
        confirm=args.yes,
        open_db=open_db,
        build_relationship_widget_proposal=build_relationship_widget_proposal,
        insert_dashboard_widget=insert_dashboard_widget,
    )


def set_widget_command(args: argparse.Namespace) -> dict[str, Any]:
    return set_dashboard_widget_service(
        widget_key=args.widget,
        widget_type=args.type,
        title=args.title,
        table_key=args.table,
        view_key=args.view,
        config_updates={
            "subtitle": args.subtitle,
            "dimension": args.dimension,
            "measure": args.measure,
            "aggregation": args.agg,
            "topN": args.top_n,
            "valueFormat": args.value_format,
            "textContent": args.text_content,
        },
        style_options=widget_style_options_from_args(args),
        filter_values=args.filter,
        clear_filters=args.clear_filters,
        confirm=args.yes,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        dashboard_widget_row_to_dict=dashboard_widget_row_to_dict,
        resolve_view=resolve_view,
        preferred_table_key=preferred_table_key,
        registry_for_table=registry_for_table,
        table_columns=table_columns,
        widget_filters_from_args=widget_filters_from_args,
    )


def copy_widget_command(args: argparse.Namespace) -> dict[str, Any]:
    return copy_dashboard_widget_service(
        widget_key=args.widget,
        dashboard_key=args.dashboard,
        title=args.title,
        clear_filters=args.clear_filters,
        confirm=args.yes,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        dashboard_widget_row_to_dict=dashboard_widget_row_to_dict,
        dashboard_exists=dashboard_exists,
        unique_key=unique_key,
        next_dashboard_widget_sort_order=next_dashboard_widget_sort_order,
        insert_dashboard_widget=insert_dashboard_widget,
    )


def remove_widget_command(args: argparse.Namespace) -> dict[str, Any]:
    return remove_dashboard_widget_service(
        widget_key=args.widget,
        confirm=args.yes,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        dashboard_widget_row_to_dict=dashboard_widget_row_to_dict,
    )


def b_cli_capabilities_command(args: argparse.Namespace) -> dict[str, Any]:
    active = [item for item in B_BI_CLI_CAPABILITY_MAP if item["status"] in {"active", "contract-active"}]
    pending = [item for item in B_BI_CLI_CAPABILITY_MAP if item["status"] == "pending"]
    return {
        "ok": True,
        "source": {
            "project": "External BI reference",
            "path": str(B_PROJECT_ROOT),
            "entrypoint": str(B_PROJECT_ROOT / "bi_cli.py"),
            "filesReadOnly": True,
            "executionPolicy": "Do not execute external BI CLIs or mutate external databases from this app; map supported commands into the current workspace.",
        },
        "target": {
            "project": "AIBI Hybrid",
            "entrypoint": "python tools/bi_cli.py --json <command>",
            "metadataStore": str(DB_PATH),
            "duckdbRuntime": str(DUCKDB_PATH),
        },
        "summary": {
            "activeAreas": len(active),
            "pendingAreas": len(pending),
            "capabilityAreas": len(B_BI_CLI_CAPABILITY_MAP),
        },
        "capabilities": B_BI_CLI_CAPABILITY_MAP,
        "guardrails": [
            "External source directories are read-only references.",
            "Import commit, dashboard write, relationship save, index creation, delete, overwrite, and external sync require dry-run or explicit confirmation.",
            "Dashboard widget generation uses the shared widget catalog instead of ad hoc frontend-only shapes.",
        ],
    }


def update_field_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        registry = registry_for_table(connection, args.table)
        if not registry:
            raise ValueError(f"Unknown table: {args.table}")
        columns = table_columns(connection, registry["physical_table"])
        if args.field not in columns:
            raise ValueError(f"Unknown field: {args.field}")
        current = connection.execute(
            "SELECT table_key, field_name, role, usage, confidence FROM field_semantics WHERE table_key = ? AND field_name = ? AND workspace_id = ?",
            (args.table, args.field, workspace_id),
        ).fetchone()
        confidence = max(0.0, min(1.0, float(args.confidence)))
        proposed = {
            "table_key": args.table,
            "field_name": args.field,
            "role": args.role,
            "usage": args.usage,
            "confidence": confidence,
        }
        if not args.yes:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "current": dict(current) if current else None,
                "proposed": proposed,
            }
        connection.execute(
            """
            INSERT OR REPLACE INTO field_semantics(workspace_id, table_key, field_name, role, usage, confidence)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (workspace_id, args.table, args.field, args.role, args.usage, confidence),
        )
        connection.commit()
    return {"ok": True, "updated": proposed}


def normalize_semantic_role(role: str) -> str:
    text = str(role or "").strip()
    return {
        "time": "event_time",
        "identifier": "identity_key",
        "text": "dimension",
    }.get(text, text or "dimension")


def semantic_usage_object(role: str, usage: str = "") -> dict[str, bool]:
    normalized_role = normalize_semantic_role(role)
    base = {
        "filterable": normalized_role in {"event_time", "dimension", "status", "identity_key"},
        "sortable": normalized_role in {"event_time", "measure", "identity_key"},
        "groupable": normalized_role in {"event_time", "dimension", "status", "identity_key"},
        "aggregatable": normalized_role == "measure",
        "joinable": normalized_role == "identity_key",
        "uniqueKeyCandidate": normalized_role == "identity_key",
        "defaultAnalysisField": normalized_role in {"event_time", "dimension", "measure"},
    }
    usage_text = str(usage or "")
    if usage_text:
        for token in re.split(r"[,，]", usage_text):
            item = token.strip()
            if not item:
                continue
            enabled = not item.startswith(("no-", "not-"))
            key = re.sub(r"^(no-|not-)", "", item)
            if key in base:
                base[key] = enabled
    return base


def primary_usage_from_object(usage: dict[str, Any], role: str) -> str:
    if usage.get("aggregatable"):
        return "aggregatable"
    if usage.get("joinable"):
        return "joinable"
    if usage.get("groupable"):
        return "groupable"
    if usage.get("filterable"):
        return "filterable"
    normalized_role = normalize_semantic_role(role)
    if normalized_role == "measure":
        return "aggregatable"
    if normalized_role == "identity_key":
        return "joinable"
    return "filterable"


def infer_field_semantic_hybrid(connection: sqlite3.Connection, registry: sqlite3.Row, field: str) -> dict[str, Any]:
    table_key = registry["table_key"]
    physical_table = registry["physical_table"]
    text = field.lower()
    non_empty_rows = connection.execute(
        f"""
        SELECT {quote_identifier(field)} AS value
        FROM {quote_identifier(physical_table)}
        WHERE {quote_identifier(field)} IS NOT NULL
          AND TRIM(CAST({quote_identifier(field)} AS TEXT)) <> ''
        LIMIT 80
        """
    ).fetchall()
    numeric = 0
    for row in non_empty_rows:
        try:
            float(str(row["value"]).replace(",", "").replace("%", "").strip())
            numeric += 1
        except ValueError:
            pass
    numeric_ratio = numeric / len(non_empty_rows) if non_empty_rows else 0.0
    total_rows = int(registry["row_count"] or 0)
    distinct_ratio = 0.0
    if total_rows > 0:
        distinct_count = connection.execute(
            f"SELECT COUNT(DISTINCT {quote_identifier(field)}) FROM {quote_identifier(physical_table)}"
        ).fetchone()[0]
        distinct_ratio = min(1.0, float(distinct_count or 0) / total_rows)

    tags: list[str] = []
    role = "dimension"
    confidence = 0.58
    usage_hint = ""
    if field == "__canonical_date":
        role = "event_time"
        tags.extend(["time", "system"])
        confidence = 0.91
    elif field.startswith("__source_"):
        role = "dimension"
        tags.extend(["source-metadata", "system"])
        confidence = 0.82
        usage_hint = "filterable,no-groupable"
    elif any(token in text for token in ("电话", "手机号", "联系方式", "联系人电话", "mobile", "phone", "tel")):
        role = "dimension"
        tags.append("contact")
        confidence = 0.74
        usage_hint = "filterable,no-groupable"
    elif any(token in text for token in ("date", "time", "日期", "时间", "月份", "年月")):
        role = "event_time"
        tags.append("time")
        confidence = 0.9
    elif any(token in text for token in ("id", "编号", "单号", "编码", "流水号", "交易号", "sku", "sn")):
        role = "identity_key"
        tags.append("identifier")
        confidence = 0.86 if distinct_ratio < 0.85 else 0.92
    elif any(token in text for token in ("status", "状态", "是否", "标记")):
        role = "status"
        tags.append("status")
        confidence = 0.82
    elif (
        any(token in text for token in ("amount", "sales", "price", "cost", "fee", "gmv", "金额", "销售", "收入", "成本", "退款", "价格", "价", "优惠", "补贴", "佣金", "分成", "服务费", "运费", "税费", "实付", "应结", "动账", "抵扣", "支出"))
        and not any(token in text for token in ("方式", "原因", "类型", "状态", "名称", "姓名", "备注", "标签", "账户", "主体", "方向", "场景"))
    ) or (numeric_ratio >= 0.9 and distinct_ratio < 0.75):
        role = "measure"
        tags.append("amount" if numeric_ratio >= 0.5 else "numeric")
        confidence = 0.86
    elif any(token in text for token in ("qty", "quantity", "count", "数量", "件数", "单量")):
        role = "measure"
        tags.append("quantity")
        confidence = 0.8
    elif any(token in text for token in ("channel", "shop", "category", "type", "source", "name", "渠道", "店", "类目", "分类", "类型", "来源", "地区", "方式", "原因", "名称", "姓名", "备注", "标签", "账户", "主体", "方向", "场景")):
        role = "dimension"
        tags.append("category")
        confidence = 0.76
    if role in {"dimension", "status"} and distinct_ratio > 0.75:
        tags.append("high-cardinality")
        confidence = min(confidence, 0.68)
    usage_obj = semantic_usage_object(role, usage_hint)
    return {
        "tableKey": table_key,
        "tableName": registry["display_name"],
        "field": field,
        "role": role,
        "usage": usage_obj,
        "primaryUsage": primary_usage_from_object(usage_obj, role),
        "tags": sorted(set(tags)),
        "confidence": round(confidence, 2),
        "source": "auto",
        "note": "",
    }


def upsert_semantic_config(connection: sqlite3.Connection, item: dict[str, Any], overwrite_manual: bool = False) -> bool:
    workspace_id = active_workspace_id(connection)
    table_key = str(item["tableKey"])
    field = str(item["field"])
    role = normalize_semantic_role(str(item["role"]))
    usage_obj = item.get("usage") if isinstance(item.get("usage"), dict) else semantic_usage_object(role, str(item.get("primaryUsage") or ""))
    primary_usage = primary_usage_from_object(usage_obj, role)
    current = connection.execute(
        "SELECT source FROM field_semantics WHERE table_key = ? AND field_name = ? AND workspace_id = ?",
        (table_key, field, workspace_id),
    ).fetchone()
    if current and str(current["source"] or "") == "manual" and not overwrite_manual:
        return False
    connection.execute(
        """
        INSERT INTO field_semantics(workspace_id, table_key, field_name, role, usage, confidence, tags_json, usage_json, source, note, updated_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(workspace_id, table_key, field_name) DO UPDATE SET
          role = excluded.role,
          usage = excluded.usage,
          confidence = excluded.confidence,
          tags_json = excluded.tags_json,
          usage_json = excluded.usage_json,
          source = excluded.source,
          note = excluded.note,
          updated_at = excluded.updated_at
        """,
        (
            workspace_id,
            table_key,
            field,
            role,
            primary_usage,
            float(item.get("confidence") or 0),
            json.dumps(item.get("tags") if isinstance(item.get("tags"), list) else [], ensure_ascii=False),
            json.dumps(usage_obj, ensure_ascii=False),
            str(item.get("source") or "auto"),
            str(item.get("note") or ""),
            now_iso(),
        ),
    )
    return True


def infer_semantics_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        registries = [resolve_table_registry(connection, args.table)] if args.table else connection.execute("SELECT * FROM table_registry WHERE workspace_id = ? ORDER BY display_name", (workspace_id,)).fetchall()
        proposals: list[dict[str, Any]] = []
        written = 0
        for registry in registries:
            for field in table_columns(connection, registry["physical_table"]):
                proposals.append(infer_field_semantic_hybrid(connection, registry, field))
        if args.yes:
            for item in proposals:
                if upsert_semantic_config(connection, item, overwrite_manual=args.overwrite_manual):
                    written += 1
            connection.commit()
    return {
        "ok": True,
        "dryRun": not args.yes,
        "requiresConfirmation": not args.yes,
        "proposed": len(proposals),
        "written": written,
        "semantics": proposals,
        "source": "infer-semantics adapted to workspace field_semantics",
    }


def semantic_row_to_payload(row: sqlite3.Row, table_name: str | None = None) -> dict[str, Any]:
    usage_obj = parse_json_object(row["usage_json"], {})
    if not usage_obj:
        usage_obj = semantic_usage_object(str(row["role"]), str(row["usage"]))
    return {
        "tableKey": row["table_key"],
        "tableName": table_name or row["table_key"],
        "field": row["field_name"],
        "role": row["role"],
        "primaryUsage": row["usage"],
        "usage": usage_obj,
        "tags": parse_json_object(row["tags_json"], []),
        "confidence": float(row["confidence"] or 0),
        "source": row["source"],
        "note": row["note"],
        "updatedAt": row["updated_at"],
    }


def list_semantics_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        params: list[Any] = [workspace_id]
        where = "WHERE f.workspace_id = ?"
        if args.table:
            registry = resolve_table_registry(connection, args.table)
            where += " AND f.table_key = ?"
            params.append(registry["table_key"])
        rows = connection.execute(
            f"""
            SELECT f.*, COALESCE(t.display_name, f.table_key) AS table_name
            FROM field_semantics f
            LEFT JOIN table_registry t ON t.table_key = f.table_key AND t.workspace_id = f.workspace_id
            {where}
            ORDER BY f.table_key, f.field_name
            """,
            params,
        ).fetchall()
    semantics = [semantic_row_to_payload(row, row["table_name"]) for row in rows]
    return {"ok": True, "semantics": semantics, "count": len(semantics)}


def set_semantic_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        proposed = build_semantic_set_plan(connection, args.table, args.field, args.role, args.usage or [], args.tag or [], args.confidence, args.note or "")
        if not args.yes:
            current = connection.execute(
                "SELECT * FROM field_semantics WHERE table_key = ? AND field_name = ? AND workspace_id = ?",
                (proposed["tableKey"], proposed["field"], active_workspace_id(connection)),
            ).fetchone()
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "current": semantic_row_to_payload(current, proposed["tableName"]) if current else None,
                "proposed": proposed,
            }
        execute_semantic_set_plan(connection, proposed)
        connection.commit()
    return {"ok": True, "confirmed": True, "semantic": proposed}


def build_semantic_set_plan(
    connection: sqlite3.Connection,
    table: str,
    field: str,
    role: str,
    usages: list[str] | tuple[str, ...] | None = None,
    tags_arg: list[str] | tuple[str, ...] | None = None,
    confidence: float = 1.0,
    note: str = "",
) -> dict[str, Any]:
    registry = resolve_table_registry(connection, table)
    columns = table_columns(connection, registry["physical_table"])
    if field not in columns:
        raise ValueError(f"Unknown field: {field}")
    tags: list[str] = []
    for value in tags_arg or []:
        tags.extend(parse_csv_list(str(value)))
    usage_obj = semantic_usage_object(role, ",".join(str(value) for value in (usages or [])))
    normalized_role = normalize_semantic_role(role)
    return {
        "tableKey": registry["table_key"],
        "tableName": registry["display_name"],
        "field": field,
        "role": normalized_role,
        "usage": usage_obj,
        "primaryUsage": primary_usage_from_object(usage_obj, normalized_role),
        "tags": sorted(set(tags)),
        "confidence": max(0.0, min(1.0, float(confidence))),
        "source": "manual",
        "note": note,
    }


def execute_semantic_set_plan(connection: sqlite3.Connection, proposed: dict[str, Any]) -> dict[str, Any]:
    upsert_semantic_config(connection, proposed, overwrite_manual=True)
    return proposed


def metric_key_for(table_key: str, label: str, measure: str, aggregation: str) -> str:
    return metric_key_for_service(table_key, label, measure, aggregation)


def metric_row_to_payload(row: sqlite3.Row, table_name: str | None = None) -> dict[str, Any]:
    return metric_row_to_payload_service(row, table_name)


def infer_metrics_for_table(connection: sqlite3.Connection, registry: sqlite3.Row) -> list[dict[str, Any]]:
    table_key = registry["table_key"]
    workspace_id = active_workspace_id(connection)
    fields = rows_to_dicts(
        connection.execute(
            """
            SELECT field_name, role, usage
            FROM field_semantics
            WHERE table_key = ? AND workspace_id = ?
            ORDER BY field_name
            """,
            (table_key, workspace_id),
        )
    )
    if not fields:
        for field in table_columns(connection, registry["physical_table"]):
            upsert_semantic_config(connection, infer_field_semantic_hybrid(connection, registry, field))
        fields = rows_to_dicts(
            connection.execute(
                """
                SELECT field_name, role, usage
                FROM field_semantics
                WHERE table_key = ? AND workspace_id = ?
                ORDER BY field_name
                """,
                (table_key, workspace_id),
            )
        )
    dimensions = [
        field["field_name"]
        for field in fields
        if not str(field["field_name"]).startswith("__")
        and (field["role"] in {"dimension", "status"} or field["usage"] == "groupable")
    ]
    time_fields = [field["field_name"] for field in fields if field["role"] == "event_time"]
    default_dimension = next((candidate for candidate in ("channel", "shop", "category", "status", "sku") if candidate in dimensions), dimensions[0] if dimensions else None)
    metrics: list[dict[str, Any]] = []
    for field in fields:
        if str(field["field_name"]).startswith("__"):
            continue
        if field["role"] != "measure" and field["usage"] != "aggregatable":
            continue
        label = f"{field['field_name']} 合计"
        metrics.append({
            "metricKey": f"{table_key}_{field['field_name']}_sum",
            "label": label,
            "tableKey": table_key,
            "measure": field["field_name"],
            "aggregation": "sum",
            "dimension": default_dimension,
            "timeField": time_fields[0] if time_fields else None,
            "valueFormat": "auto",
            "filters": [],
            "description": "Auto-inferred from field semantics.",
            "source": "auto",
        })
    count_label = "记录数"
    metrics.append({
        "metricKey": f"{table_key}_row_count",
        "label": count_label,
        "tableKey": table_key,
        "measure": "*",
        "aggregation": "count",
        "dimension": default_dimension,
        "timeField": time_fields[0] if time_fields else None,
        "valueFormat": "compact",
        "filters": [],
        "description": "Auto-inferred row count metric.",
        "source": "auto",
    })
    return metrics


def cleanup_stale_auto_metrics(connection: sqlite3.Connection, registries: list[sqlite3.Row], workspace_id: str) -> int:
    removed = 0
    for registry in registries:
        cursor = connection.execute(
            """
            DELETE FROM metric_definitions
            WHERE workspace_id = ?
              AND table_key = ?
              AND source = 'auto'
              AND measure <> '*'
              AND (
                substr(measure, 1, 2) = '__'
                OR NOT EXISTS (
                  SELECT 1
                  FROM field_semantics f
                  WHERE f.workspace_id = metric_definitions.workspace_id
                    AND f.table_key = metric_definitions.table_key
                    AND f.field_name = metric_definitions.measure
                    AND (f.role = 'measure' OR f.usage = 'aggregatable')
                )
              )
            """,
            (workspace_id, registry["table_key"]),
        )
        removed += max(cursor.rowcount, 0)
    return removed


def upsert_metric_definition(connection: sqlite3.Connection, metric: dict[str, Any]) -> dict[str, Any]:
    return upsert_metric_definition_service(
        connection,
        metric,
        resolve_table_registry=resolve_table_registry,
        table_columns=table_columns,
        active_workspace_id=active_workspace_id,
        now_iso=now_iso,
        safe_aggregations=SAFE_AGGREGATIONS,
    )


def infer_metrics_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        registries = [resolve_table_registry(connection, args.table)] if args.table else connection.execute("SELECT * FROM table_registry WHERE workspace_id = ? ORDER BY display_name", (workspace_id,)).fetchall()
        proposals: list[dict[str, Any]] = []
        saved: list[dict[str, Any]] = []
        removed_stale = 0
        for registry in registries:
            proposals.extend(infer_metrics_for_table(connection, registry))
        if args.yes:
            removed_stale = cleanup_stale_auto_metrics(connection, registries, workspace_id)
            for metric in proposals:
                saved.append(upsert_metric_definition(connection, metric))
            connection.commit()
    return {
        "ok": True,
        "dryRun": not args.yes,
        "requiresConfirmation": not args.yes,
        "proposed": len(proposals),
        "saved": len(saved),
        "removedStaleAutoMetrics": removed_stale,
        "metrics": saved if args.yes else proposals,
        "source": "infer-metrics adapted to workspace metric_definitions",
    }


def list_metrics_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        params: list[Any] = [workspace_id]
        clauses: list[str] = ["m.workspace_id = ?"]
        if args.table:
            registry = resolve_table_registry(connection, args.table)
            clauses.append("m.table_key = ?")
            params.append(registry["table_key"])
        if not args.all:
            clauses.append("m.enabled = 1")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = connection.execute(
            f"""
            SELECT m.*, COALESCE(t.display_name, m.table_key) AS table_name
            FROM metric_definitions m
            LEFT JOIN table_registry t ON t.table_key = m.table_key AND t.workspace_id = m.workspace_id
            {where}
            ORDER BY m.table_key, m.metric_key
            """,
            params,
        ).fetchall()
    metrics = [metric_row_to_payload(row, row["table_name"]) for row in rows]
    return {"ok": True, "metrics": metrics, "count": len(metrics)}


def metric_filters_from_cli(raw_filters: list[str]) -> list[dict[str, Any]]:
    return metric_filters_from_cli_service(raw_filters)


def build_metric_add_plan(
    connection: sqlite3.Connection,
    table_key: str,
    label: str,
    measure: str,
    aggregation: str,
    dimension: str = "",
    time_field: str = "",
    filters: list[dict[str, Any]] | None = None,
    value_format: str = "auto",
    description: str = "",
    metric_key: str = "",
) -> dict[str, Any]:
    return build_metric_add_plan_service(
        connection,
        table_key,
        label,
        measure,
        aggregation,
        dimension,
        time_field,
        filters,
        value_format,
        description,
        metric_key,
        resolve_table_registry=resolve_table_registry,
        table_columns=table_columns,
        safe_aggregations=SAFE_AGGREGATIONS,
    )


def execute_metric_add_plan(connection: sqlite3.Connection, proposed: dict[str, Any]) -> dict[str, Any]:
    return upsert_metric_definition(connection, proposed)


def add_metric_command(args: argparse.Namespace) -> dict[str, Any]:
    return add_metric_command_service(
        args,
        open_db=open_db,
        metric_filters_from_cli=metric_filters_from_cli,
        build_metric_add_plan=build_metric_add_plan,
        execute_metric_add_plan=execute_metric_add_plan,
    )


def query_metric_command(args: argparse.Namespace) -> dict[str, Any]:
    return query_metric_command_service(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        metric_row_to_payload=metric_row_to_payload,
        build_formula_metric_query=build_formula_metric_query,
        table_columns=table_columns,
        metric_filters_from_cli=metric_filters_from_cli,
        parse_query_sort=parse_query_sort,
        build_table_query=build_table_query,
    )


def normalize_relation_field_name(value: str) -> str:
    return normalize_relation_field_name_service(value)


def relation_candidate_fields(connection: sqlite3.Connection, registry: sqlite3.Row) -> list[dict[str, Any]]:
    return relation_candidate_fields_service(
        connection,
        registry,
        active_workspace_id=active_workspace_id,
        table_columns=table_columns,
    )


def relationship_name_score(left_field: str, right_field: str) -> tuple[int, list[str]]:
    return relationship_name_score_service(left_field, right_field)


def sample_field_values(connection: sqlite3.Connection, physical_table: str, field: str, limit: int = 300) -> set[str]:
    return sample_field_values_service(connection, physical_table, field, limit, quote_identifier=quote_identifier)


def saved_relationship_signatures(connection: sqlite3.Connection) -> set[tuple[str, str, str, str]]:
    return saved_relationship_signatures_service(connection, active_workspace_id=active_workspace_id)


def recommend_relationships_for_connection(connection: sqlite3.Connection, limit: int = 12) -> list[dict[str, Any]]:
    return recommend_relationships_for_connection_service(
        connection,
        limit,
        active_workspace_id=active_workspace_id,
        table_columns=table_columns,
        quote_identifier=quote_identifier,
        build_relationship_preview=build_relationship_preview,
        relation_candidate_fields=relation_candidate_fields,
        relationship_name_score=relationship_name_score,
        sample_field_values=sample_field_values,
        saved_relationship_signatures=saved_relationship_signatures,
    )


def recommend_relationships_command(args: argparse.Namespace) -> dict[str, Any]:
    return recommend_relationships_command_service(
        args,
        open_db=open_db,
        recommend_relationships_for_connection=recommend_relationships_for_connection,
    )


def action_drafts_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        result = list_action_drafts(connection, workspace_id=workspace_id, limit=args.limit, include_all=args.all)
    return {"ok": True, **result}


def list_relationships_command(args: argparse.Namespace) -> dict[str, Any]:
    return list_relationships_command_service(args, open_db=open_db, active_workspace_id=active_workspace_id)


def resolve_relationship_query_inputs(args: argparse.Namespace, connection: sqlite3.Connection) -> dict[str, Any]:
    return resolve_relationship_query_inputs_service(
        args,
        connection,
        active_workspace_id=active_workspace_id,
        registry_for_table=registry_for_table,
        table_columns=table_columns,
    )


def parse_relationship_filter(raw_filter: str) -> dict[str, Any]:
    return parse_relationship_filter_service(raw_filter)


def to_number(value: Any) -> float:
    return relationship_to_number_service(value)


def relationship_rows_for_chart(payload: dict[str, Any]) -> list[dict[str, Any]]:
    return relationship_rows_for_chart_service(payload)


def query_relationship_command(args: argparse.Namespace) -> dict[str, Any]:
    return query_relationship_command_service(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        registry_for_table=registry_for_table,
        table_columns=table_columns,
        parse_relationship_field_ref=parse_relationship_field_ref,
        build_relationship_query=build_relationship_query,
        quote_relationship_identifier=quote_relationship_identifier,
    )


def remove_relationship_command(args: argparse.Namespace) -> dict[str, Any]:
    return remove_relationship_command_service(args, open_db=open_db, active_workspace_id=active_workspace_id)


def relationship_preview_command(args: argparse.Namespace) -> dict[str, Any]:
    return relationship_preview_command_service(
        args,
        open_db=open_db,
        registry_for_table=registry_for_table,
        table_columns=table_columns,
        build_relationship_preview=build_relationship_preview,
        quote_identifier=quote_identifier,
    )


def build_relationship_save_plan(
    connection: sqlite3.Connection,
    left_table: str,
    right_table: str,
    left_field: str,
    right_field: str,
    join_type: str = "left",
    limit: int = 20,
) -> dict[str, Any]:
    return build_relationship_save_plan_service(
        connection,
        left_table,
        right_table,
        left_field,
        right_field,
        join_type,
        limit,
        registry_for_table=registry_for_table,
        table_columns=table_columns,
        build_relationship_preview=build_relationship_preview,
        quote_identifier=quote_identifier,
    )


def execute_relationship_save(connection: sqlite3.Connection, proposed: dict[str, Any]) -> dict[str, Any]:
    return execute_relationship_save_service(connection, proposed, active_workspace_id=active_workspace_id)


def relationship_save_command(args: argparse.Namespace) -> dict[str, Any]:
    return relationship_save_command_service(
        args,
        open_db=open_db,
        build_relationship_save_plan=build_relationship_save_plan,
        execute_relationship_save=execute_relationship_save,
    )

def formula_preview_command(args: argparse.Namespace) -> dict[str, Any]:
    return formula_preview_command_service(
        args,
        open_db=open_db,
        all_available_fields=all_available_fields,
        parse_and_validate_formula=parse_and_validate_formula,
        ast_dependencies=ast_dependencies,
        ast_to_sql=ast_to_sql,
        quote_identifier=quote_identifier,
        formula_error_type=FormulaError,
    )


def formula_key_for(table_key: str, name: str, mode: str) -> str:
    return formula_key_for_service(table_key, name, mode)


def calculated_field_row_to_payload(row: sqlite3.Row) -> dict[str, Any]:
    return calculated_field_row_to_payload_service(row)


def calculated_field_usage(connection: sqlite3.Connection, table_key: str, field_name: str, field_key: str = "") -> list[dict[str, str]]:
    return calculated_field_usage_service(
        connection,
        table_key,
        field_name,
        field_key,
        active_workspace_id=active_workspace_id,
    )


def compile_formula_for_table(connection: sqlite3.Connection, table_key: str, expression: str, mode: str) -> dict[str, Any]:
    return compile_formula_for_table_service(
        connection,
        table_key,
        expression,
        mode,
        resolve_table_registry=resolve_table_registry,
        table_columns=table_columns,
        parse_and_validate_formula=parse_and_validate_formula,
        ast_dependencies=ast_dependencies,
        ast_to_sql=ast_to_sql,
        quote_identifier=quote_identifier,
    )


def list_formulas_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        params: list[Any] = [workspace_id]
        clauses: list[str] = ["workspace_id = ?"]
        if args.table:
            registry = resolve_table_registry(connection, args.table)
            clauses.append("table_key = ?")
            params.append(registry["table_key"])
        if not args.all:
            clauses.append("enabled = 1")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        row_formulas = [
            calculated_field_row_to_payload(row)
            for row in connection.execute(
                f"""
                SELECT *
                FROM calculated_fields
                {where}
                ORDER BY table_key, name
                """,
                params,
            ).fetchall()
        ]
        metric_rows = connection.execute(
            f"""
            SELECT m.*, COALESCE(t.display_name, m.table_key) AS table_name
            FROM metric_definitions m
            LEFT JOIN table_registry t
              ON t.table_key = m.table_key
             AND t.workspace_id = m.workspace_id
            WHERE {" AND ".join([clause.replace("workspace_id", "m.workspace_id").replace("table_key", "m.table_key") for clause in clauses])}
            ORDER BY m.table_key, m.metric_key
            """,
            params,
        ).fetchall()
        metric_formulas = [
            metric_row_to_payload(row, row["table_name"])
            for row in metric_rows
            if row["metric_type"] == "formula" or row["formula_text"]
        ]
    return {"ok": True, "formulas": row_formulas, "metricFormulas": metric_formulas, "count": len(row_formulas) + len(metric_formulas)}


def save_formula_command(args: argparse.Namespace) -> dict[str, Any]:
    return save_formula_command_service(
        args,
        open_db=open_db,
        build_formula_save_plan=build_formula_save_plan,
        execute_formula_save_plan=execute_formula_save_plan,
    )


def build_formula_save_plan(
    connection: sqlite3.Connection,
    table: str,
    name: str,
    expression: str,
    mode: str = "aggregate",
    dimension: str = "",
    time_field: str = "",
    value_format: str = "auto",
    description: str = "",
    formula_key: str = "",
) -> dict[str, Any]:
    return build_formula_save_plan_service(
        connection,
        table,
        name,
        expression,
        mode,
        dimension,
        time_field,
        value_format,
        description,
        formula_key,
        compile_formula_for_table=compile_formula_for_table,
    )


def execute_formula_save_plan(connection: sqlite3.Connection, proposed: dict[str, Any]) -> dict[str, Any]:
    return execute_formula_save_plan_service(
        connection,
        proposed,
        active_workspace_id=active_workspace_id,
        now_iso=now_iso,
    )


def delete_formula_command(args: argparse.Namespace) -> dict[str, Any]:
    return delete_formula_command_service(
        args,
        open_db=open_db,
        active_workspace_id=active_workspace_id,
        calculated_field_row_to_payload=calculated_field_row_to_payload,
        metric_row_to_payload=metric_row_to_payload,
        calculated_field_usage=calculated_field_usage,
    )


def build_formula_metric_query(connection: sqlite3.Connection, row: sqlite3.Row, args: argparse.Namespace) -> dict[str, Any]:
    return build_formula_metric_query_service(
        connection,
        row,
        args,
        table_columns=table_columns,
        normalize_filters=normalize_filters,
        where_sql=where_sql,
        parse_and_validate_formula=parse_and_validate_formula,
        ast_to_sql=ast_to_sql,
        quote_identifier=quote_identifier,
    )


def build_dashboard_operation_plan(
    connection: sqlite3.Connection,
    op: str,
    dashboard_key: str = "",
    name: str = "",
    table_key: str = "",
    source_dashboard_key: str = "",
) -> dict[str, Any]:
    source = None
    workspace_id = active_workspace_id(connection)
    if dashboard_key:
        source = connection.execute(
            "SELECT * FROM dashboards WHERE dashboard_key = ? AND workspace_id = ?",
            (dashboard_key, workspace_id),
        ).fetchone()
    if op in {"copy", "rename", "delete"} and not source:
        raise ValueError(f"Unknown dashboard: {dashboard_key}")
    if op in {"create", "copy", "rename"} and not name:
        raise ValueError("Dashboard name is required.")
    if table_key:
        resolved_table_key = table_key
    elif source:
        resolved_table_key = source["default_table_key"]
    elif op == "create":
        resolved_table_key = ""
    else:
        resolved_table_key = preferred_table_key(connection, None)
    return {
        "op": op,
        "dashboardKey": dashboard_key,
        "name": name,
        "sourceDashboardKey": source_dashboard_key or dashboard_key,
        "defaultTableKey": resolved_table_key,
        "sourceDashboardName": source["name"] if source else "",
    }


def execute_dashboard_operation_plan(connection: sqlite3.Connection, proposed: dict[str, Any], created_by: str = "user", agent_managed: int = 0) -> dict[str, Any]:
    op = str(proposed.get("op") or "")
    now = now_iso()
    dashboard_key = str(proposed.get("dashboardKey") or "")
    name = str(proposed.get("name") or "")
    table_key = str(proposed.get("defaultTableKey") or "")
    if op in {"create", "copy", "rename"} and not name:
        raise ValueError("Dashboard name is required.")

    navigation_created_by = "agent" if created_by == "agent" else "manual"
    workspace_id = active_workspace_id(connection)
    source = connection.execute(
        "SELECT * FROM dashboards WHERE dashboard_key = ? AND workspace_id = ?",
        (dashboard_key, workspace_id),
    ).fetchone() if dashboard_key else None
    if op in {"copy", "rename", "delete"} and not source:
        raise ValueError(f"Unknown dashboard: {dashboard_key}")

    if op == "create":
        dashboard_key = unique_key("dashboard")
        layout = {"version": 1, "grid": "12-col", "widgets": [], "globalFilters": []}
        connection.execute(
            """
            INSERT INTO dashboards(dashboard_key, name, workspace_id, default_table_key, layout_json, created_by, agent_managed, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (dashboard_key, name, workspace_id, table_key or None, json.dumps(layout, ensure_ascii=False), created_by, agent_managed, now, now),
        )
        upsert_navigation_module(
            connection,
            module_key=f"dashboard:{dashboard_key}",
            name=name,
            module_type="dashboard",
            dashboard_key=dashboard_key,
            created_by=navigation_created_by,
            agent_managed=agent_managed,
        )
        result = {"dashboardKey": dashboard_key}
    elif op == "copy":
        dashboard_key = unique_key("dashboard")
        layout = json.loads(source["layout_json"])
        layout["copiedFrom"] = source["dashboard_key"]
        connection.execute(
            """
            INSERT INTO dashboards(dashboard_key, name, workspace_id, default_table_key, layout_json, created_by, agent_managed, created_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (dashboard_key, name, workspace_id, source["default_table_key"], json.dumps(layout, ensure_ascii=False), created_by, agent_managed, now, now),
        )
        widgets = rows_to_dicts(
            connection.execute(
                "SELECT * FROM dashboard_widgets WHERE dashboard_key = ? AND workspace_id = ? ORDER BY sort_order",
                (source["dashboard_key"], workspace_id),
            )
        )
        for widget in widgets:
            connection.execute(
                """
                INSERT INTO dashboard_widgets(widget_key, workspace_id, dashboard_key, widget_type, title, table_key, config_json, sort_order)
                VALUES(?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (unique_key("widget"), workspace_id, dashboard_key, widget["widget_type"], widget["title"], widget["table_key"], widget["config_json"], widget["sort_order"]),
            )
        upsert_navigation_module(
            connection,
            module_key=f"dashboard:{dashboard_key}",
            name=name,
            module_type="dashboard",
            dashboard_key=dashboard_key,
            created_by=navigation_created_by,
            agent_managed=agent_managed,
        )
        result = {"dashboardKey": dashboard_key}
    elif op == "rename":
        connection.execute(
            "UPDATE dashboards SET name = ?, updated_at = ? WHERE dashboard_key = ? AND workspace_id = ?",
            (name, now, dashboard_key, workspace_id),
        )
        connection.execute(
            """
            UPDATE navigation_modules
            SET name = ?, updated_at = ?
            WHERE module_type = 'dashboard' AND dashboard_key = ? AND workspace_id = ?
            """,
            (name, now, dashboard_key, workspace_id),
        )
        result = {"dashboardKey": dashboard_key}
    elif op == "delete":
        dashboard_count = connection.execute(
            "SELECT COUNT(*) FROM dashboards WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()[0]
        if dashboard_count <= 1:
            raise ValueError("Cannot delete the only dashboard.")
        connection.execute(
            "DELETE FROM dashboard_widgets WHERE dashboard_key = ? AND workspace_id = ?",
            (dashboard_key, workspace_id),
        )
        connection.execute(
            "DELETE FROM dashboards WHERE dashboard_key = ? AND workspace_id = ?",
            (dashboard_key, workspace_id),
        )
        connection.execute(
            "DELETE FROM navigation_modules WHERE module_type = 'dashboard' AND dashboard_key = ? AND workspace_id = ?",
            (dashboard_key, workspace_id),
        )
        result = {"dashboardKey": dashboard_key}
    else:
        raise ValueError(f"Unsupported dashboard operation: {op}")
    return result


def dashboard_operation_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        proposed = build_dashboard_operation_plan(connection, args.op, args.dashboard or "", args.name or "", args.table or "", args.source or "")
        if not args.yes:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "proposed": proposed}
        result = execute_dashboard_operation_plan(connection, proposed)
        connection.commit()
    return {"ok": True, "confirmed": True, "operation": args.op, **result}


def source_pipeline_contract() -> dict[str, Any]:
    return build_source_pipeline_contract()


def domain_pack_runtime() -> dict[str, Any]:
    return build_domain_pack_runtime()


def ontology_snapshot(connection: sqlite3.Connection) -> dict[str, Any]:
    workspace_id = active_workspace_id(connection)
    tables = rows_to_dicts(
        connection.execute(
            "SELECT table_key, display_name, row_count, column_count FROM table_registry WHERE workspace_id = ? ORDER BY table_key",
            (workspace_id,),
        )
    )
    metrics = rows_to_dicts(
        connection.execute(
            """
            SELECT metric_key, label, table_key, measure, aggregation, dimension
            FROM metric_definitions
            WHERE workspace_id = ?
            ORDER BY metric_key
            LIMIT 12
            """,
            (workspace_id,),
        )
    )
    relationships = rows_to_dicts(
        connection.execute(
            """
            SELECT relation_key, name, left_table_key, right_table_key, left_field, right_field, confidence
            FROM relationships
            WHERE workspace_id = ?
            ORDER BY relation_key
            """,
            (workspace_id,),
        )
    )
    return {
        "version": 1,
        "objects": tables,
        "functions": metrics,
        "links": relationships,
        "actions": ["dashboard.create", "dashboard.copy", "dashboard.rename", "dashboard.delete", "dashboard.widget.add", "dashboard.filter.add", "import.commit", "relationship.save", "index.create", "formula.save", "view.save", "metric.add", "semantic.set"],
        "evidenceFiles": ["source-profile", "field-semantics", "metric-sql-plan", "query-runtime"],
    }


def normalize_match_text(value: str) -> str:
    return re.sub(r"[\s_\\/\-:：，,。.!！?？'\"“”‘’]+", "", value.lower())


def dashboard_mention_candidates(prompt: str) -> list[str]:
    candidates: list[str] = []
    for match in re.finditer(r"([\u4e00-\u9fffA-Za-z0-9_ -]{1,32}(?:仪表盘|看板|dashboard))", prompt, re.IGNORECASE):
        if prompt[match.end():].lstrip().startswith("组件"):
            continue
        candidate = match.group(1).strip()
        candidate = re.sub(r"^(在|给|向|把|为|往|到|请|帮我|增加|新增|添加|创建|生成|新建|做|一个|一张)+", "", candidate).strip()
        candidate = re.sub(r"^(?:(?:please|help me|add|insert|create|generate|build|draft|new|make|a|an|the|one)\s+)+", "", candidate, flags=re.IGNORECASE).strip()
        generic_dashboard_mentions = {
            "dashboard",
            "business dashboard",
            "executive dashboard",
            "operating dashboard",
            "operation dashboard",
            "analysis dashboard",
            "analytics dashboard",
            "仪表盘",
            "看板",
            "经营看板",
            "经营仪表盘",
        }
        if candidate and candidate.lower() not in generic_dashboard_mentions:
            candidates.append(candidate)
    return candidates


def select_dashboard(dashboards: list[dict[str, Any]], prompt: str, wants_dashboard: bool) -> tuple[dict[str, Any] | None, str]:
    normalized_prompt = normalize_match_text(prompt)
    default_aliases = ["默认看板", "默认仪表盘", "defaultdashboard", "default"]
    if any(alias in normalized_prompt for alias in default_aliases):
        default_dashboard = next((dashboard for dashboard in dashboards if str(dashboard.get("dashboard_key") or "") == "default"), None)
        if default_dashboard:
            return default_dashboard, "explicit"
    for dashboard in dashboards:
        keys = [
            str(dashboard.get("dashboard_key") or ""),
            str(dashboard.get("name") or ""),
        ]
        if any(key and normalize_match_text(key) in normalized_prompt for key in keys):
            return dashboard, "explicit"
    mentions = dashboard_mention_candidates(prompt)
    if mentions and wants_dashboard:
        return None, "missing"
    return (dashboards[0] if dashboards and wants_dashboard else None), ("fallback" if dashboards and wants_dashboard else "missing")


def dashboard_operation_name_from_prompt(prompt: str, op: str, current_name: str = "") -> str:
    if op == "delete":
        return ""
    patterns = [
        r"(?:复制|拷贝|重命名|改名).{0,48}(?:为|成|叫|命名为)\s*([\u4e00-\u9fffA-Za-z0-9_ -]{2,36})",
        r"(?:copy|duplicate|rename).{0,80}\b(?:as|to|named)\s+([A-Za-z0-9_ -]{2,40})",
    ]
    for pattern in patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            value = match.group(1).strip(" ，,。.!！?？")
            if value:
                return value
    if op == "copy" and current_name:
        return f"{current_name} 副本"
    return ""


def resolve_prompt_dashboard_operation(
    connection: sqlite3.Connection,
    selected_dashboard: dict[str, Any] | None,
    dashboard_confidence: str,
    prompt: str,
) -> tuple[dict[str, Any] | None, str]:
    op = dashboard_operation_from_prompt(prompt)
    if not op or not selected_dashboard:
        return None, "missing"
    if op in {"rename", "delete"} and dashboard_confidence != "explicit":
        return None, "missing"
    name = dashboard_operation_name_from_prompt(prompt, op, str(selected_dashboard.get("name") or ""))
    if op in {"copy", "rename"} and not name:
        return None, "missing"
    try:
        proposed = build_dashboard_operation_plan(
            connection,
            op,
            str(selected_dashboard["dashboard_key"]),
            name,
            str(selected_dashboard.get("default_table_key") or ""),
            str(selected_dashboard["dashboard_key"]),
        )
    except ValueError:
        return None, "missing"
    proposed["dashboardSelectionConfidence"] = dashboard_confidence
    return proposed, dashboard_confidence


def select_index_field(connection: sqlite3.Connection, table_key: str, prompt: str) -> tuple[str | None, str, dict[str, Any] | None]:
    registry = resolve_table_registry(connection, table_key)
    columns = table_columns(connection, registry["physical_table"])
    normalized_prompt = normalize_match_text(prompt)
    for column in columns:
        if normalize_match_text(column) in normalized_prompt:
            recommendations = recommend_indexes_for_table(connection, registry, 100)
            recommendation = next((item for item in recommendations if item["field"] == column), None)
            return column, "explicit", recommendation
    recommendations = recommend_indexes_for_table(connection, registry, 12)
    if recommendations:
        return str(recommendations[0]["field"]), "recommended", recommendations[0]
    return (columns[0] if columns else None), "fallback", None


def table_is_mentioned(table: dict[str, Any], prompt: str) -> bool:
    normalized_prompt = normalize_match_text(prompt)
    keys = [str(table.get("table_key") or ""), str(table.get("display_name") or "")]
    return any(key and normalize_match_text(key) in normalized_prompt for key in keys)


def recommendation_matches_tables(recommendation: dict[str, Any], left_table: str, right_table: str) -> bool:
    return (
        recommendation.get("leftTableKey") == left_table
        and recommendation.get("rightTableKey") == right_table
    ) or (
        recommendation.get("leftTableKey") == right_table
        and recommendation.get("rightTableKey") == left_table
    )


def select_relationship_action(connection: sqlite3.Connection, tables: list[dict[str, Any]], prompt: str) -> tuple[dict[str, Any] | None, str]:
    recommendations = recommend_relationships_for_connection(connection, 12)
    mentioned_tables = [table for table in tables if table_is_mentioned(table, prompt)]
    normalized_prompt = normalize_match_text(prompt)
    if len(mentioned_tables) >= 2:
        left_table = str(mentioned_tables[0]["table_key"])
        right_table = str(mentioned_tables[1]["table_key"])
        left_registry = resolve_table_registry(connection, left_table)
        right_registry = resolve_table_registry(connection, right_table)
        left_columns = table_columns(connection, left_registry["physical_table"])
        right_columns = table_columns(connection, right_registry["physical_table"])
        common_columns = [column for column in left_columns if column in right_columns]
        explicit_common = next((column for column in common_columns if normalize_match_text(column) in normalized_prompt), None)
        matching_recommendation = next(
            (
                item for item in recommendations
                if recommendation_matches_tables(item, left_table, right_table)
                and (
                    not explicit_common
                    or any(
                        isinstance(mapping, dict)
                        and str(mapping.get("leftField") or "") == explicit_common
                        and str(mapping.get("rightField") or "") == explicit_common
                        for mapping in item.get("fieldMappings") or []
                    )
                )
            ),
            None,
        )
        if explicit_common:
            return {
                "leftTable": left_table,
                "rightTable": right_table,
                "leftField": explicit_common,
                "rightField": explicit_common,
                "joinType": str((matching_recommendation or {}).get("joinType") or "left"),
                "recommendation": matching_recommendation,
            }, "explicit"
        if matching_recommendation:
            mapping = (matching_recommendation.get("fieldMappings") or [{}])[0]
            if isinstance(mapping, dict):
                left_field = str(mapping.get("leftField") or "")
                right_field = str(mapping.get("rightField") or "")
                for candidate in matching_recommendation.get("fieldMappings") or []:
                    if not isinstance(candidate, dict):
                        continue
                    candidate_left = str(candidate.get("leftField") or "")
                    candidate_right = str(candidate.get("rightField") or "")
                    if candidate_left and normalize_match_text(candidate_left) in normalized_prompt:
                        left_field = candidate_left
                        right_field = candidate_right or candidate_left
                        break
                if left_field and right_field:
                    return {
                        "leftTable": left_table,
                        "rightTable": right_table,
                        "leftField": left_field,
                        "rightField": right_field,
                        "joinType": str(matching_recommendation.get("joinType") or "left"),
                        "recommendation": matching_recommendation,
                    }, "explicit"
        selected_field = common_columns[0] if common_columns else ""
        if selected_field:
            return {
                "leftTable": left_table,
                "rightTable": right_table,
                "leftField": selected_field,
                "rightField": selected_field,
                "joinType": "left",
                "recommendation": matching_recommendation,
            }, "explicit"
    if recommendations:
        recommendation = recommendations[0]
        mapping = (recommendation.get("fieldMappings") or [{}])[0]
        if isinstance(mapping, dict):
            return {
                "leftTable": str(recommendation.get("leftTableKey") or ""),
                "rightTable": str(recommendation.get("rightTableKey") or ""),
                "leftField": str(mapping.get("leftField") or ""),
                "rightField": str(mapping.get("rightField") or ""),
                "joinType": str(recommendation.get("joinType") or "left"),
                "recommendation": recommendation,
            }, "recommended"
    return None, "missing"


IMPORT_FILE_PATTERN = re.compile(r"(?:[A-Za-z]:[^\s\"'<>|]+\.(?:csv|tsv|xlsx|xls)|[A-Za-z0-9_.\-\\/\\u4e00-\\u9fff]+\.(?:csv|tsv|xlsx|xls))", re.IGNORECASE)


def resolve_prompt_import_file(prompt: str) -> tuple[Path | None, str]:
    candidates: list[str] = []
    for match in IMPORT_FILE_PATTERN.finditer(prompt):
        candidates.append(match.group(0).strip("，。,.；;：:）)]}"))
    for candidate in candidates:
        path = Path(candidate)
        possible_paths = [path]
        if not path.is_absolute():
            possible_paths = [ROOT / path]
        for possible_path in possible_paths:
            if possible_path.exists() and possible_path.is_file():
                return possible_path.resolve(), "explicit"
    return None, "missing"


def import_mode_from_prompt(prompt: str) -> str:
    lower = prompt.lower()
    if any(token in lower for token in ["merge", "合并", "追加", "更新已有", "upsert"]):
        return "merge"
    if any(token in lower for token in ["replace", "替换", "覆盖表"]):
        return "replace"
    return "create"


FORMULA_FUNCTION_PATTERN = re.compile(r"\b(SAFE_DIVIDE|SUM|AVG|MIN|MAX|COUNT|COUNT_DISTINCT|ABS|ROUND|COALESCE|CONCAT|IF)\s*\(", re.IGNORECASE)


def extract_formula_expression_from_prompt(prompt: str) -> str:
    match = FORMULA_FUNCTION_PATTERN.search(prompt)
    if not match:
        return ""
    start = match.start()
    depth = 0
    opened = False
    end = start
    for index, char in enumerate(prompt[start:], start=start):
        if char == "(":
            depth += 1
            opened = True
        elif char == ")":
            depth -= 1
            if opened and depth == 0:
                end = index + 1
                break
    if end <= start:
        return ""
    return prompt[start:end].strip("，。,.；;：: ")


def default_formula_dimension(connection: sqlite3.Connection, table_key: str, prompt: str) -> str:
    registry = resolve_table_registry(connection, table_key)
    columns = table_columns(connection, registry["physical_table"])
    normalized_prompt = normalize_match_text(prompt)
    for column in columns:
        normalized_column = normalize_match_text(column)
        if normalized_column and normalized_column in normalized_prompt and column not in {"net_sales", "quantity", "order_id"}:
            return column
    for candidate in ("channel", "shop", "category", "status"):
        if candidate in columns:
            return candidate
    return ""


def resolve_prompt_formula_action(
    connection: sqlite3.Connection,
    selected_table: dict[str, Any] | None,
    prompt: str,
) -> tuple[dict[str, Any] | None, str]:
    if not selected_table:
        return None, "missing"
    table_key = str(selected_table["table_key"])
    registry = resolve_table_registry(connection, table_key)
    columns = set(table_columns(connection, registry["physical_table"]))
    lower = prompt.lower()
    explicit_expression = extract_formula_expression_from_prompt(prompt)
    name = "Agent 公式指标"
    expression = explicit_expression
    confidence = "explicit" if explicit_expression else "recommended"
    if any(token in prompt for token in ["客单价", "平均订单"]) or "aov" in lower:
        if {"net_sales", "order_id"}.issubset(columns):
            name = "客单价"
            expression = "SAFE_DIVIDE(SUM([net_sales]), COUNT_DISTINCT([order_id]))"
            confidence = "recommended"
    elif any(token in prompt for token in ["销售单价", "件单价", "每件", "单价"]):
        if {"net_sales", "quantity"}.issubset(columns):
            name = "销售单价"
            expression = "SAFE_DIVIDE(SUM([net_sales]), SUM([quantity]))"
            confidence = "recommended"
    elif explicit_expression:
        label_match = re.search(r"(?:保存|创建|新增|定义|add|save)?\s*([\u4e00-\u9fffA-Za-z0-9_\- ]{2,24})\s*(?:公式|formula|指标)", prompt, re.IGNORECASE)
        if label_match:
            name = label_match.group(1).strip() or name
    if not expression:
        return None, "missing"
    try:
        proposed = build_formula_save_plan(
            connection,
            table_key,
            name,
            expression,
            "row" if any(token in lower for token in ["row", "行级", "计算字段"]) else "aggregate",
            default_formula_dimension(connection, table_key, prompt),
            "",
            "auto",
            f"Agent draft from prompt: {prompt[:120]}",
            "",
        )
    except (FormulaError, ValueError):
        return None, "missing"
    return proposed, confidence


def aggregation_from_metric_prompt(prompt: str, measure: str) -> str:
    lower = prompt.lower()
    if any(token in prompt for token in ["平均", "均值"]) or any(token in lower for token in ["avg", "average", "mean"]):
        return "avg"
    if any(token in prompt for token in ["最大", "最高"]) or "max" in lower:
        return "max"
    if any(token in prompt for token in ["最小", "最低"]) or "min" in lower:
        return "min"
    if any(token in prompt for token in ["去重", "唯一"]) or "distinct" in lower:
        return "count-distinct"
    if any(token in prompt for token in ["记录数", "订单数", "笔数"]) or "count" in lower or measure == "*":
        return "count"
    return "sum"


def select_metric_field_from_prompt(connection: sqlite3.Connection, table_key: str, prompt: str) -> tuple[str, str]:
    registry = resolve_table_registry(connection, table_key)
    columns = table_columns(connection, registry["physical_table"])
    normalized_prompt = normalize_match_text(prompt)
    workspace_id = active_workspace_id(connection)
    semantic_rows = rows_to_dicts(
        connection.execute(
            """
            SELECT field_name, role, confidence
            FROM field_semantics
            WHERE table_key = ? AND workspace_id = ?
            ORDER BY confidence DESC, field_name
            """,
            (table_key, workspace_id),
        )
    )
    semantic_roles = {str(row.get("field_name") or ""): str(row.get("role") or "") for row in semantic_rows}
    explicit_columns = [column for column in columns if normalize_match_text(column) in normalized_prompt]
    for column in explicit_columns:
        if semantic_roles.get(column) == "measure":
            return column, "explicit"
    preferred: list[tuple[list[str], str]] = [
        (["净销售", "销售额", "收入", "revenue", "sales", "net sales"], "net_sales"),
        (["退款", "退款额", "refund"], "refund_amount"),
        (["数量", "件数", "销量", "quantity", "units"], "quantity"),
        (["成本", "cost"], "cost"),
    ]
    for tokens, field in preferred:
        if field in columns and (any(token in prompt for token in tokens) or any(token in prompt.lower() for token in tokens)):
            return field, "recommended"
    for column in explicit_columns:
        if semantic_roles.get(column) not in {"dimension", "status", "identity_key", "event_time"}:
            return column, "explicit"
    for row in semantic_rows:
        if row.get("role") == "measure" and str(row.get("field_name") or "") in columns:
            return str(row["field_name"]), "fallback"
    return "*", "fallback"


def select_metric_dimension_from_prompt(connection: sqlite3.Connection, table_key: str, prompt: str, measure: str) -> tuple[str, str]:
    registry = resolve_table_registry(connection, table_key)
    columns = table_columns(connection, registry["physical_table"])
    normalized_prompt = normalize_match_text(prompt)
    dimension_intent = any(token in prompt for token in ["按", "分组", "拆分", "维度"]) or any(token in prompt.lower() for token in [" by ", "group", "segment"])
    if not dimension_intent:
        return "", "none"
    workspace_id = active_workspace_id(connection)
    semantic_rows = rows_to_dicts(
        connection.execute(
            """
            SELECT field_name, role, usage, confidence
            FROM field_semantics
            WHERE table_key = ? AND workspace_id = ?
            ORDER BY confidence DESC, field_name
            """,
            (table_key, workspace_id),
        )
    )
    semantic_roles = {str(row.get("field_name") or ""): str(row.get("role") or "") for row in semantic_rows}
    dimension_tail = prompt
    tail_match = re.search(r"(?:按|按照|分组|拆分|by|group by)\s*([\u4e00-\u9fffA-Za-z0-9_\- ]{1,48})", prompt, re.IGNORECASE)
    if tail_match:
        dimension_tail = tail_match.group(1)
    normalized_tail = normalize_match_text(dimension_tail)
    for column in columns:
        if column != measure and normalize_match_text(column) in normalized_tail:
            return column, "explicit"
    for column in columns:
        if column == measure:
            continue
        if normalize_match_text(column) in normalized_prompt and semantic_roles.get(column) in {"dimension", "status", "identity_key", "event_time"}:
            return column, "explicit"
    if "channel" in columns and (dimension_intent or any(token in prompt for token in ["渠道", "channel"])):
        return "channel", "recommended"
    for row in semantic_rows:
        field = str(row.get("field_name") or "")
        if field and field != measure and row.get("role") in {"dimension", "status", "identity_key"} and field in columns:
            return field, "fallback"
    return "", "missing"


def metric_label_from_prompt(prompt: str, measure: str, aggregation: str) -> str:
    label_match = re.search(r"(?:新增|添加|创建|定义|保存|做成|add|create|define|save)\s*([\u4e00-\u9fffA-Za-z0-9_\- ]{2,32})\s*(?:指标|metric|kpi)", prompt, re.IGNORECASE)
    if label_match:
        label = label_match.group(1).strip(" ，,。.")
        label = re.sub(r"^(一个|一项|the|a|an)\s*", "", label, flags=re.IGNORECASE).strip()
        if label and label not in {"指标", "metric", "kpi"}:
            return label
    aggregation_label = {
        "sum": "合计",
        "avg": "平均值",
        "count": "计数",
        "count-distinct": "去重计数",
        "max": "最大值",
        "min": "最小值",
    }.get(aggregation, aggregation)
    return f"{measure} {aggregation_label}" if measure != "*" else f"记录数 {aggregation_label}"


def resolve_prompt_metric_action(
    connection: sqlite3.Connection,
    selected_table: dict[str, Any] | None,
    prompt: str,
) -> tuple[dict[str, Any] | None, str]:
    if not selected_table:
        return None, "missing"
    table_key = str(selected_table["table_key"])
    measure, measure_confidence = select_metric_field_from_prompt(connection, table_key, prompt)
    aggregation = aggregation_from_metric_prompt(prompt, measure)
    dimension, dimension_confidence = select_metric_dimension_from_prompt(connection, table_key, prompt, measure)
    label = metric_label_from_prompt(prompt, measure, aggregation)
    try:
        proposed = build_metric_add_plan(
            connection,
            table_key,
            label,
            measure,
            aggregation,
            dimension,
            "",
            [],
            "auto",
            f"Agent metric draft from prompt: {prompt[:120]}",
            "",
        )
    except ValueError:
        return None, "missing"
    proposed["measureSelectionConfidence"] = measure_confidence
    proposed["dimensionSelectionConfidence"] = dimension_confidence
    return proposed, "explicit" if measure_confidence == "explicit" else "recommended"


def widget_type_from_prompt(prompt: str) -> tuple[str, str]:
    lower = prompt.lower()
    if any(token in prompt for token in ["指标卡", "卡片", "指标组件"]) or any(token in lower for token in ["metric card", "kpi card"]):
        return "metric", "explicit"
    if any(token in prompt for token in ["折线图", "趋势图", "趋势"]) or any(token in lower for token in ["line chart", "trend"]):
        return "line", "explicit"
    if any(token in prompt for token in ["饼图", "环图", "占比"]) or any(token in lower for token in ["pie chart", "donut"]):
        return "pie", "explicit"
    if any(token in prompt for token in ["表格", "明细表"]) or any(token in lower for token in ["table", "detail grid"]):
        return "table", "explicit"
    if any(token in prompt for token in ["筛选器", "切片器", "筛选组件"]) or any(token in lower for token in ["slicer", "filter control"]):
        return "slicer", "explicit"
    if any(token in prompt for token in ["柱状图", "条形图", "排行", "排名"]) or any(token in lower for token in ["bar chart", "ranking"]):
        return "bar", "explicit"
    return "bar", "recommended"


def widget_title_from_prompt(prompt: str, widget_type: str, measure: str, dimension: str) -> str:
    patterns = [
        r"(?:标题|命名为|叫)\s*([\u4e00-\u9fffA-Za-z0-9_ -]{2,36})",
        r"(?:title|named)\s+([A-Za-z0-9_ -]{2,40})",
    ]
    for pattern in patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            value = match.group(1).strip(" ，,。.!！?？")
            if value:
                return value
    if widget_type == "metric":
        return f"{measure if measure != '*' else '记录数'} 指标卡"
    if widget_type in {"bar", "pie"} and measure and dimension:
        return f"{dimension} by {measure}"
    if widget_type == "line" and measure:
        return f"{measure} trend"
    if widget_type == "table":
        return "明细表"
    if widget_type == "slicer":
        return f"{dimension or '字段'} 筛选器"
    return f"{measure or dimension or '分析'} 图表"


def widget_candidate_fields(connection: sqlite3.Connection, table_key: str, roles: list[str], limit: int = 5) -> list[str]:
    candidates: list[str] = []
    for role in roles:
        for field in field_names_by_role(connection, table_key, role):
            if field and not str(field).startswith("__") and field not in candidates:
                candidates.append(field)
            if len(candidates) >= limit:
                return candidates
    registry = resolve_table_registry(connection, table_key)
    for field in table_columns(connection, registry["physical_table"]):
        if field and not str(field).startswith("__") and field not in candidates:
            candidates.append(field)
        if len(candidates) >= limit:
            break
    return candidates


def build_widget_clarification_action(
    connection: sqlite3.Connection,
    dashboard_key: str,
    table_key: str,
    widget_type: str,
    measure: str,
    dimension: str,
    widget_type_confidence: str,
    measure_confidence: str,
    dimension_confidence: str,
) -> dict[str, Any]:
    candidate_measures = widget_candidate_fields(connection, table_key, ["measure"], 5)
    candidate_dimensions = widget_candidate_fields(connection, table_key, ["event_time", "dimension", "status", "identity_key"], 5)
    return {
        "needsClarification": True,
        "dashboardKey": dashboard_key,
        "widgetType": widget_type,
        "tableKey": table_key,
        "measure": measure,
        "dimension": dimension,
        "question": localized_value(
            "我还不能确定这个图表应该用哪个指标和维度。请指定一个指标，必要时再指定按什么分组。",
            "I cannot safely determine the chart measure and dimension yet. Specify a measure, and optionally a grouping dimension.",
        ),
        "candidateMeasures": candidate_measures,
        "candidateDimensions": candidate_dimensions,
        "widgetTypeSelectionConfidence": widget_type_confidence,
        "measureSelectionConfidence": measure_confidence,
        "dimensionSelectionConfidence": dimension_confidence,
    }


def widget_needs_clarification(widget_type: str, widget_type_confidence: str, measure_confidence: str, dimension_confidence: str) -> bool:
    if widget_type_confidence != "explicit":
        return True
    if measure_confidence in {"fallback", "missing"}:
        return True
    if widget_type in {"bar", "pie", "line", "slicer"} and dimension_confidence in {"fallback", "missing", "none"}:
        return True
    return False


def resolve_prompt_widget_action(
    connection: sqlite3.Connection,
    selected_dashboard: dict[str, Any] | None,
    dashboard_confidence: str,
    selected_table: dict[str, Any] | None,
    table_confidence: str,
    prompt: str,
) -> tuple[dict[str, Any] | None, str]:
    if not selected_dashboard or dashboard_confidence not in {"explicit", "fallback"}:
        return None, "missing"
    dashboard_key = str(selected_dashboard["dashboard_key"])
    table_key = str(selected_table["table_key"]) if selected_table else ""
    if table_confidence != "explicit" and selected_dashboard.get("default_table_key"):
        table_key = str(selected_dashboard["default_table_key"])
    if not table_key:
        return None, "missing"
    widget_type, widget_type_confidence = widget_type_from_prompt(prompt)
    measure, measure_confidence = select_metric_field_from_prompt(connection, table_key, prompt)
    dimension, dimension_confidence = select_metric_dimension_from_prompt(connection, table_key, prompt, measure)
    if widget_type in {"bar", "pie", "slicer"} and not dimension:
        dimension, dimension_confidence = select_metric_dimension_from_prompt(connection, table_key, f"{prompt} 按 channel", measure)
    if widget_type == "line" and not dimension:
        date_fields = [field for field in field_names_by_role(connection, table_key, "event_time")]
        if date_fields:
            dimension, dimension_confidence = date_fields[0], "recommended"
    aggregation = aggregation_from_metric_prompt(prompt, measure)
    if widget_needs_clarification(widget_type, widget_type_confidence, measure_confidence, dimension_confidence):
        return build_widget_clarification_action(
            connection,
            dashboard_key,
            table_key,
            widget_type,
            measure,
            dimension,
            widget_type_confidence,
            measure_confidence,
            dimension_confidence,
        ), "missing"
    if widget_type in {"table", "slicer", "text"} and not any(token in prompt.lower() for token in SAFE_AGGREGATIONS):
        aggregation = "count"
    title = widget_title_from_prompt(prompt, widget_type, measure, dimension)
    options: dict[str, Any] = {
        "tableKey": table_key,
        "title": title,
        "dimension": "" if widget_type == "metric" else dimension,
        "measure": measure,
        "aggregation": aggregation,
        "topN": 1 if widget_type == "metric" else (100 if widget_type == "table" else 12),
        "valueFormat": "auto",
        "sourceAction": "agent.widget.add",
    }
    if widget_type == "table":
        registry = resolve_table_registry(connection, table_key)
        options["columns"] = table_columns(connection, registry["physical_table"])[:6]
    try:
        proposed = build_widget_proposal(connection, dashboard_key, widget_type, options)
    except ValueError:
        return None, "missing"
    return {
        "dashboardKey": dashboard_key,
        "widgetType": widget_type,
        "tableKey": table_key,
        "title": title,
        "options": options,
        "proposedWidget": proposed,
        "widgetTypeSelectionConfidence": widget_type_confidence,
        "measureSelectionConfidence": measure_confidence,
        "dimensionSelectionConfidence": dimension_confidence,
    }, "explicit" if widget_type_confidence == "explicit" else "recommended"


def filter_operator_from_prompt(prompt: str) -> tuple[str, str]:
    lower = prompt.lower()
    if any(token in prompt for token in ["包含", "含有"]) or "contains" in lower:
        return "contains", "explicit"
    if any(token in prompt for token in ["不等于", "不是", "排除"]) or any(token in lower for token in ["not equals", "not equal", "!="]):
        return "notEquals", "explicit"
    if any(token in prompt for token in ["大于等于", "不少于"]) or ">=" in lower:
        return "gte", "explicit"
    if any(token in prompt for token in ["小于等于", "不超过"]) or "<=" in lower:
        return "lte", "explicit"
    if any(token in prompt for token in ["大于", "超过"]) or ">" in lower:
        return "gt", "explicit"
    if any(token in prompt for token in ["小于", "低于"]) or "<" in lower:
        return "lt", "explicit"
    if any(token in prompt for token in ["为空", "空值"]) or " is empty" in lower:
        return "empty", "explicit"
    if any(token in prompt for token in ["不为空", "非空"]) or "not empty" in lower:
        return "notEmpty", "explicit"
    return "equals", "fallback"


def select_dashboard_filter_field(connection: sqlite3.Connection, dashboard_key: str, prompt: str) -> tuple[str, str]:
    dashboard, _layout, _filters, fields = dashboard_filters_snapshot(connection, dashboard_key)
    available = [str(item.get("field_name") or "") for item in fields if item.get("field_name")]
    normalized_prompt = normalize_match_text(prompt)
    for field in available:
        if normalize_match_text(field) in normalized_prompt:
            return field, "explicit"
    if "channel" in available and any(token in prompt.lower() for token in ["channel", "douyin", "tmall", "jd"]) or ("channel" in available and "渠道" in prompt):
        return "channel", "recommended"
    for item in fields:
        if item.get("usage") == "filterable":
            return str(item["field_name"]), "fallback"
    return (available[0] if available else ""), "missing"


def dashboard_filter_value_from_prompt(connection: sqlite3.Connection, dashboard_key: str, field: str, operator: str, prompt: str) -> tuple[str, str]:
    if not filter_value_required(operator):
        return "", "none"
    escaped = re.escape(field)
    patterns = [
        rf"{escaped}\s*(?:=|等于|为|是|equals?)\s*([\u4e00-\u9fffA-Za-z0-9_.@\-]+)",
        rf"{escaped}\s*(?:包含|含有|contains?)\s*([\u4e00-\u9fffA-Za-z0-9_.@\-]+)",
        rf"(?:只看|筛选|过滤|限定).{{0,24}}{escaped}.{{0,12}}([\u4e00-\u9fffA-Za-z0-9_.@\-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            value = match.group(1).strip(" ，,。.!！?？")
            if value and normalize_match_text(value) != normalize_match_text(field):
                return value, "explicit"
    dashboard, _layout, _filters, _fields = dashboard_filters_snapshot(connection, dashboard_key)
    registry = registry_for_table(connection, str(dashboard["default_table_key"] or ""))
    if registry:
        rows = connection.execute(
            f"SELECT DISTINCT {quote_identifier(field)} AS value FROM {quote_identifier(registry['physical_table'])} WHERE {quote_identifier(field)} IS NOT NULL LIMIT 50"
        ).fetchall()
        normalized_prompt = normalize_match_text(prompt)
        for row in rows:
            value = str(row["value"])
            if value and normalize_match_text(value) in normalized_prompt:
                return value, "recommended"
    return "", "missing"


def resolve_prompt_dashboard_filter_action(
    connection: sqlite3.Connection,
    selected_dashboard: dict[str, Any] | None,
    dashboard_confidence: str,
    prompt: str,
) -> tuple[dict[str, Any] | None, str]:
    if not selected_dashboard or dashboard_confidence != "explicit":
        return None, "missing"
    dashboard_key = str(selected_dashboard["dashboard_key"])
    field, field_confidence = select_dashboard_filter_field(connection, dashboard_key, prompt)
    operator, operator_confidence = filter_operator_from_prompt(prompt)
    value, value_confidence = dashboard_filter_value_from_prompt(connection, dashboard_key, field, operator, prompt) if field else ("", "missing")
    if not field or (filter_value_required(operator) and not value):
        return None, "missing"
    try:
        plan = build_dashboard_filter_add_plan(connection, dashboard_key, field, operator, value)
    except ValueError:
        return None, "missing"
    return {
        "dashboardKey": dashboard_key,
        "field": field,
        "operator": operator,
        "value": value,
        "filter": plan["proposed"],
        "filtersAfter": plan["filtersAfter"],
        "fieldSelectionConfidence": field_confidence,
        "operatorSelectionConfidence": operator_confidence,
        "valueSelectionConfidence": value_confidence,
    }, "explicit" if field_confidence == "explicit" and value_confidence in {"explicit", "recommended"} else "recommended"


def semantic_role_from_prompt(prompt: str) -> tuple[str, str]:
    lower = prompt.lower()
    if any(token in prompt for token in ["关联键", "主键", "唯一键", "身份键", "连接键"]) or any(token in lower for token in ["identity_key", "identifier", "join key", "primary key"]):
        return "identity_key", "explicit"
    if any(token in prompt for token in ["时间字段", "日期字段", "事件时间", "日期", "时间"]) or any(token in lower for token in ["event_time", "date field", "time field"]):
        return "event_time", "explicit"
    if any(token in prompt for token in ["指标字段", "数值字段", "金额字段", "度量", "指标", "可聚合"]) or any(token in lower for token in ["measure", "metric", "aggregatable"]):
        return "measure", "explicit"
    if any(token in prompt for token in ["状态字段", "状态"]) or "status" in lower:
        return "status", "explicit"
    if any(token in prompt for token in ["维度", "分类", "分组", "可分组"]) or any(token in lower for token in ["dimension", "groupable"]):
        return "dimension", "explicit"
    return "dimension", "missing"


def semantic_usage_tokens_for_role(role: str, prompt: str) -> list[str]:
    lower = prompt.lower()
    usages: list[str] = []
    if any(token in prompt for token in ["可筛选", "筛选"]) or "filter" in lower:
        usages.append("filterable")
    if any(token in prompt for token in ["可排序", "排序"]) or "sort" in lower:
        usages.append("sortable")
    if any(token in prompt for token in ["可分组", "分组"]) or "group" in lower:
        usages.append("groupable")
    if any(token in prompt for token in ["可聚合", "聚合"]) or "aggregate" in lower:
        usages.append("aggregatable")
    if any(token in prompt for token in ["可关联", "关联键", "连接键"]) or "join" in lower:
        usages.append("joinable")
    if not usages:
        default_usage = primary_usage_from_object(semantic_usage_object(role), role)
        usages.append(default_usage)
    return sorted(set(usages))


def select_semantic_field(connection: sqlite3.Connection, table_key: str, prompt: str) -> tuple[str, str]:
    registry = resolve_table_registry(connection, table_key)
    columns = table_columns(connection, registry["physical_table"])
    normalized_prompt = normalize_match_text(prompt)
    for column in columns:
        if normalize_match_text(column) in normalized_prompt:
            return column, "explicit"
    workspace_id = active_workspace_id(connection)
    rows = rows_to_dicts(
        connection.execute(
            """
            SELECT field_name, role
            FROM field_semantics
            WHERE table_key = ? AND workspace_id = ?
            ORDER BY confidence DESC, field_name
            """,
            (table_key, workspace_id),
        )
    )
    role, role_confidence = semantic_role_from_prompt(prompt)
    if role_confidence != "missing":
        for row in rows:
            if row.get("role") == normalize_semantic_role(role):
                return str(row["field_name"]), "recommended"
    return "", "missing"


def resolve_prompt_semantic_action(
    connection: sqlite3.Connection,
    selected_table: dict[str, Any] | None,
    prompt: str,
) -> tuple[dict[str, Any] | None, str]:
    if not selected_table:
        return None, "missing"
    table_key = str(selected_table["table_key"])
    field, field_confidence = select_semantic_field(connection, table_key, prompt)
    role, role_confidence = semantic_role_from_prompt(prompt)
    if not field or role_confidence == "missing":
        return None, "missing"
    try:
        proposed = build_semantic_set_plan(
            connection,
            table_key,
            field,
            role,
            semantic_usage_tokens_for_role(role, prompt),
            [],
            1.0 if field_confidence == "explicit" and role_confidence == "explicit" else 0.86,
            f"Agent semantic draft from prompt: {prompt[:120]}",
        )
    except ValueError:
        return None, "missing"
    proposed["fieldSelectionConfidence"] = field_confidence
    proposed["roleSelectionConfidence"] = role_confidence
    return proposed, field_confidence if role_confidence == "explicit" else "missing"


def view_name_from_prompt(prompt: str, table_name: str) -> str:
    patterns = [
        r"(?:保存为|保存成|存成|命名为|叫|名称为)\s*([\u4e00-\u9fffA-Za-z0-9_ -]{2,40})",
        r"(?:save|create).{0,80}\b(?:as|named)\s+([A-Za-z0-9_ -]{2,40})",
    ]
    for pattern in patterns:
        match = re.search(pattern, prompt, re.IGNORECASE)
        if match:
            value = match.group(1).strip(" ，,。.!！?？")
            if value:
                return value
    if any(token in prompt for token in ["退款", "售后"]):
        return "退款明细视图"
    if any(token in prompt for token in ["渠道", "channel"]):
        return "渠道明细视图"
    return f"{table_name} 常用视图"


def view_config_from_prompt(connection: sqlite3.Connection, table_key: str, prompt: str) -> tuple[dict[str, Any], str]:
    registry = resolve_table_registry(connection, table_key)
    columns = table_columns(connection, registry["physical_table"])
    normalized_prompt = normalize_match_text(prompt)
    workspace_id = active_workspace_id(connection)
    default_view = connection.execute(
        "SELECT config_json FROM saved_views WHERE table_key = ? AND workspace_id = ? ORDER BY is_default DESC, sort_order, created_at LIMIT 1",
        (table_key, workspace_id),
    ).fetchone()
    default_config = parse_json_object(default_view["config_json"], {}) if default_view else {}
    selected_columns = list_from_value(default_config.get("columns")) or columns[:6]
    explicit_columns = [column for column in columns if normalize_match_text(column) in normalized_prompt]
    if explicit_columns:
        selected_columns = explicit_columns[:8]
    filters: list[dict[str, Any]] = []
    for column in columns:
        escaped = re.escape(column)
        match = re.search(rf"{escaped}\s*(?:=|等于|为|是|equals?)\s*([\u4e00-\u9fffA-Za-z0-9_.@\-]+)", prompt, re.IGNORECASE)
        if match:
            filters.append({"field": column, "operator": "equals", "value": match.group(1).strip(" ，,。.!！?？")})
            continue
        contains_match = re.search(rf"{escaped}\s*(?:包含|含有|contains?)\s*([\u4e00-\u9fffA-Za-z0-9_.@\-]+)", prompt, re.IGNORECASE)
        if contains_match:
            filters.append({"field": column, "operator": "contains", "value": contains_match.group(1).strip(" ，,。.!！?？")})
    sort: list[dict[str, str]] = []
    sort_match = re.search(r"(?:按|按照|by)\s*([\u4e00-\u9fffA-Za-z0-9_\- ]{1,40})\s*(?:排序|升序|降序|倒序|sort|order)?", prompt, re.IGNORECASE)
    if sort_match:
        sort_text = normalize_match_text(sort_match.group(1))
        for column in columns:
            if normalize_match_text(column) in sort_text:
                direction = "desc" if any(token in prompt.lower() for token in ["desc", "descending"]) or any(token in prompt for token in ["降序", "倒序", "最新", "最高"]) else "asc"
                sort.append({"field": column, "direction": direction})
                break
    if not sort:
        sort = [item for item in (default_config.get("sort") or []) if isinstance(item, dict)]
    return {
        "mode": "detail",
        "columns": selected_columns,
        "filters": filters,
        "sort": sort,
        "search": "",
    }, "explicit" if filters or explicit_columns or sort_match else "fallback"


def resolve_prompt_view_action(
    connection: sqlite3.Connection,
    selected_table: dict[str, Any] | None,
    prompt: str,
) -> tuple[dict[str, Any] | None, str]:
    if not selected_table:
        return None, "missing"
    table_key = str(selected_table["table_key"])
    table_name = str(selected_table.get("display_name") or table_key)
    config, confidence = view_config_from_prompt(connection, table_key, prompt)
    name = view_name_from_prompt(prompt, table_name)
    try:
        proposed = build_save_view_plan(
            connection,
            table_key,
            name,
            config,
            "",
            "Agent 保存的筛选口径",
            "agent",
            1,
        )
    except ValueError:
        return None, "missing"
    proposed["viewSelectionConfidence"] = confidence
    return proposed, confidence


def localized_value(zh: str, en: str) -> dict[str, str]:
    return {"zh": zh, "en": en}


def format_answer_number(value: Any) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number) >= 10000:
        return f"{number / 10000:.2f}w"
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.2f}"


def answer_table_columns(connection: sqlite3.Connection, table_key: str) -> tuple[sqlite3.Row | None, list[str]]:
    registry = registry_for_table(connection, table_key)
    if not registry:
        return None, []
    columns = [row["name"] for row in connection.execute(f"PRAGMA table_info({quote_identifier(registry['physical_table'])})")]
    return registry, columns


def safe_answer_aggregate(
    connection: sqlite3.Connection,
    table_key: str,
    *,
    group: str | None,
    measure: str,
    aggregation: str,
    limit: int = 5,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str | None]:
    registry, columns = answer_table_columns(connection, table_key)
    if not registry:
        return None, [], f"Unknown table: {table_key}"
    if group and group not in columns:
        return None, [], f"Unknown group field: {group}"
    if measure != "*" and measure not in columns:
        return None, [], f"Unknown measure field: {measure}"
    try:
        runtime = run_duckdb_aggregate_query(
            sqlite_connection=connection,
            duckdb_path=DUCKDB_PATH,
            physical_table=registry["physical_table"],
            columns=columns,
            group=group,
            measure=measure,
            aggregation=aggregation,
            limit=limit,
        )
        fallback_reason = None
    except DuckDBUnavailable as exc:
        runtime = run_sqlite_aggregate_query(
            sqlite_connection=connection,
            physical_table=registry["physical_table"],
            group=group,
            measure=measure,
            aggregation=aggregation,
            limit=limit,
        )
        fallback_reason = str(exc)
    rows = runtime.pop("rows")
    return runtime, rows, fallback_reason


def latest_source_run_ref(connection: sqlite3.Connection, table_key: str) -> dict[str, Any] | None:
    workspace_id = active_workspace_id(connection)
    row = connection.execute(
        """
        SELECT id, table_key, name, source_file, row_count, column_count, created_at
        FROM source_runs
        WHERE table_key = ? AND workspace_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (table_key, workspace_id),
    ).fetchone()
    return dict(row) if row else None


def metric_ref(connection: sqlite3.Connection, table_key: str, measure: str, aggregation: str, dimension: str | None) -> dict[str, Any] | None:
    workspace_id = active_workspace_id(connection)
    row = connection.execute(
        """
        SELECT metric_key, label, table_key, measure, aggregation, dimension, value_format
        FROM metric_definitions
        WHERE table_key = ?
          AND workspace_id = ?
          AND measure = ?
          AND aggregation = ?
          AND COALESCE(dimension, '') = COALESCE(?, '')
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (table_key, workspace_id, measure, aggregation, dimension),
    ).fetchone()
    return dict(row) if row else None


def build_widget_clarification_answer_card(widget_action: dict[str, Any]) -> dict[str, Any]:
    candidate_measures = [str(item) for item in widget_action.get("candidateMeasures", []) if item]
    candidate_dimensions = [str(item) for item in widget_action.get("candidateDimensions", []) if item]
    measure_hint = candidate_measures[0] if candidate_measures else ""
    dimension_hint = candidate_dimensions[0] if candidate_dimensions else ""
    next_actions = [
        localized_value("指定指标，例如：用支付金额做柱状图", "Specify a measure, for example: build a bar chart with paid amount"),
        localized_value("需要分组时补一句：按月份、渠道或状态分组", "If grouping is needed, add: group by month, channel, or status"),
    ]
    if measure_hint and dimension_hint:
        next_actions.insert(0, localized_value(
            f"可以说：用 {measure_hint} 按 {dimension_hint} 做图表",
            f"You can say: build a chart with {measure_hint} by {dimension_hint}",
        ))
    return {
        "kind": "clarification",
        "title": localized_value("先确认图表字段", "Confirm chart fields first"),
        "summary": widget_action.get("question") or localized_value(
            "我还不能确定要使用的指标或维度，因此不会先创建图表草案。",
            "I cannot safely determine the measure or dimension yet, so no chart draft was created.",
        ),
        "confidence": "missing",
        "metrics": [],
        "rows": [
            {"role": "measure", "field": field} for field in candidate_measures
        ] + [
            {"role": "dimension", "field": field} for field in candidate_dimensions
        ],
        "clarification": {
            "kind": "widget-fields",
            "widgetType": widget_action.get("widgetType"),
            "tableKey": widget_action.get("tableKey"),
            "dashboardKey": widget_action.get("dashboardKey"),
            "candidateMeasures": candidate_measures,
            "candidateDimensions": candidate_dimensions,
        },
        "evidenceRefs": [
            {"type": "table", "tableKey": widget_action.get("tableKey")},
            {"type": "dashboard", "dashboardKey": widget_action.get("dashboardKey")},
        ],
        "nextActions": next_actions,
    }


def build_agent_answer_card(
    connection: sqlite3.Connection,
    prompt: str,
    selected_table: dict[str, Any] | None,
) -> dict[str, Any]:
    if not selected_table:
        return {
            "kind": "gap",
            "title": localized_value("还没有可分析的数据表", "No analyzable table yet"),
            "summary": localized_value("请先导入本地文件或选择当前工作区中的数据源。", "Import a local file or select a source in the current workspace first."),
            "confidence": "missing",
            "metrics": [],
            "rows": [],
            "evidenceRefs": [],
            "nextActions": [localized_value("导入本地文件或文件夹", "Import a local file or folder")],
        }
    lower = prompt.lower()
    prompt_wants_refund = any(token in lower for token in ["refund", "return", "after sale"]) or any(token in prompt for token in ["退款", "售后", "退货"])
    prompt_wants_channel = any(token in lower for token in ["channel", "best", "performing", "contributed"]) or any(token in prompt for token in ["渠道", "最好", "贡献", "来源"])
    table_key = selected_table["table_key"]
    registry, columns = answer_table_columns(connection, table_key)
    if not registry:
        return {
            "kind": "gap",
            "title": localized_value("还没有可分析的数据表", "No analyzable table yet"),
            "summary": localized_value("请先导入本地文件或选择当前工作区中的数据源。", "Import a local file or select a source in the current workspace first."),
            "confidence": "missing",
            "metrics": [],
            "rows": [],
            "evidenceRefs": [],
            "nextActions": [localized_value("导入本地文件或文件夹", "Import a local file or folder")],
        }

    if prompt_wants_refund and "refund_amount" in columns:
        measure = "refund_amount"
        dimension = "channel" if "channel" in columns else None
        title = localized_value("退款压力来自哪里", "Where refund pressure comes from")
        summary_metric_label = localized_value("退款金额", "Refund amount")
        intent = "refund_pressure"
    elif ("net_sales" in columns or selected_table) and ("net_sales" in columns):
        measure = "net_sales"
        dimension = "channel" if prompt_wants_channel and "channel" in columns else ("channel" if "channel" in columns else None)
        title = localized_value("渠道销售表现", "Channel sales performance")
        summary_metric_label = localized_value("净销售额", "Net sales")
        intent = "sales_by_channel" if dimension else "sales_total"
    else:
        measure = "*"
        dimension = "channel" if prompt_wants_channel and "channel" in columns else None
        title = localized_value("当前数据概览", "Current data overview")
        summary_metric_label = localized_value("记录数", "Rows")
        intent = "table_overview"

    aggregation = "count" if measure == "*" else "sum"
    runtime, rows, fallback_reason = safe_answer_aggregate(
        connection,
        table_key,
        group=dimension,
        measure=measure,
        aggregation=aggregation,
        limit=5,
    )
    if runtime is None:
        return {
            "kind": "gap",
            "title": title,
            "summary": localized_value(
                f"当前表缺少可用于回答该问题的字段：{measure} / {dimension or '-'}。",
                f"The current table is missing fields needed for this answer: {measure} / {dimension or '-'}.",
            ),
            "confidence": "missing",
            "metrics": [],
            "rows": [],
            "evidenceRefs": [{"type": "table", "tableKey": table_key}],
            "nextActions": [localized_value("运行 Source Intelligence 或设置字段语义", "Run Source Intelligence or set field semantics")],
        }

    top_row = rows[0] if rows else {}
    total_value = sum(float(row.get("value") or 0) for row in rows) if dimension else float(top_row.get("value") or 0)
    top_label = str(top_row.get("label", "")) if dimension else ""
    top_value = float(top_row.get("value") or 0) if rows else 0.0
    top_share = (top_value / total_value) if total_value else 0.0
    if dimension and rows:
        summary = localized_value(
            f"{top_label} 排名第一，{summary_metric_label['zh']} {format_answer_number(top_value)}，占当前前 {len(rows)} 项合计 {top_share:.1%}。",
            f"{top_label} ranks first with {summary_metric_label['en']} {format_answer_number(top_value)}, {top_share:.1%} of the top {len(rows)} total.",
        )
    else:
        summary = localized_value(
            f"当前 {summary_metric_label['zh']} 为 {format_answer_number(top_value)}。",
            f"Current {summary_metric_label['en']} is {format_answer_number(top_value)}.",
        )

    evidence_refs: list[dict[str, Any]] = [
        {"type": "queryRuntime", "engine": runtime.get("engine"), "compiledSql": runtime.get("compiledSql"), "fallbackReason": fallback_reason},
        {"type": "ontologyFunction", "id": intent},
    ]
    source_ref = latest_source_run_ref(connection, table_key)
    if source_ref:
        evidence_refs.insert(0, {"type": "sourceRun", **source_ref})
    metric = metric_ref(connection, table_key, measure, aggregation, dimension)
    if metric:
        evidence_refs.insert(1, {"type": "metricDefinition", **metric})

    next_actions = [
        localized_value("打开看板查看图表和筛选", "Open the dashboard to inspect charts and filters"),
        localized_value("需要写入时先生成草案再确认", "For writes, create a draft first and confirm it"),
    ]
    if prompt_wants_refund:
        next_actions.insert(0, localized_value("按渠道或 SKU 下钻退款压力", "Drill into refund pressure by channel or SKU"))

    return {
        "kind": intent,
        "title": title,
        "summary": summary,
        "confidence": "query-runtime",
        "metrics": [
            {
                "label": summary_metric_label,
                "value": format_answer_number(top_value),
                "rawValue": top_value,
                "unit": "rows" if measure == "*" else "amount",
            },
            {
                "label": localized_value("样本行数", "Source rows"),
                "value": format_answer_number(registry["row_count"]),
                "rawValue": registry["row_count"],
                "unit": "rows",
            },
        ],
        "rows": rows,
        "query": {
            "table": table_key,
            "group": dimension,
            "measure": measure,
            "aggregation": aggregation,
            "runtime": runtime,
            "fallbackReason": fallback_reason,
            "sqlIntent": "whitelist aggregate query; no user SQL accepted",
        },
        "evidenceRefs": evidence_refs,
        "nextActions": next_actions,
    }


def ask_command(args: argparse.Namespace) -> dict[str, Any]:
    prompt = args.prompt
    read_only = getattr(args, "read_only", False)
    intents = resolve_agent_prompt_intents(prompt)
    deepseek_configured = bool(os.environ.get("DEEPSEEK_API_KEY"))
    llm_audit = {
        "provider": "deepseek" if deepseek_configured else "deterministic",
        "configured": deepseek_configured,
        "mode": "provider" if deepseek_configured else "deterministic-fallback",
        "serverSideOnly": True,
        "secretExposed": False,
        "contextBoundary": "active-workspace-sourceRun-workbench",
        "fallbackReason": None if deepseek_configured else "DEEPSEEK_API_KEY is not configured; deterministic fallback answered from local BI evidence.",
        "regressionStatus": "provider-ready" if deepseek_configured else "provider-skipped",
    }
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        tables = rows_to_dicts(connection.execute("SELECT table_key, display_name FROM table_registry WHERE workspace_id = ? ORDER BY table_key", (workspace_id,)))
        dashboards = rows_to_dicts(
            connection.execute(
                "SELECT dashboard_key, name, default_table_key FROM dashboards WHERE workspace_id = ? ORDER BY dashboard_key",
                (workspace_id,),
            )
        )
        selected_table, table_confidence = select_agent_table(tables, prompt)
        selected_dashboard, dashboard_confidence = select_dashboard(dashboards, prompt, intents.wants_dashboard or intents.wants_widget)
        dashboard_action = None
        dashboard_action_confidence = "missing"
        if intents.wants_dashboard:
            dashboard_action, dashboard_action_confidence = resolve_prompt_dashboard_operation(connection, selected_dashboard, dashboard_confidence, prompt)
        widget_action = None
        widget_confidence = "missing"
        if intents.wants_widget and not dashboard_action:
            widget_action, widget_confidence = resolve_prompt_widget_action(connection, selected_dashboard, dashboard_confidence, selected_table, table_confidence, prompt)
        widget_clarification = isinstance(widget_action, dict) and widget_action.get("needsClarification") is True
        actionable_widget_action = None if widget_clarification else widget_action
        dashboard_filter_action = None
        dashboard_filter_confidence = "missing"
        if intents.wants_dashboard_filter and not dashboard_action and not actionable_widget_action:
            dashboard_filter_action, dashboard_filter_confidence = resolve_prompt_dashboard_filter_action(connection, selected_dashboard, dashboard_confidence, prompt)
        index_field = None
        index_field_confidence = "missing"
        index_recommendation = None
        if intents.wants_index and selected_table:
            index_field, index_field_confidence, index_recommendation = select_index_field(connection, selected_table["table_key"], prompt)
        relationship_action = None
        relationship_confidence = "missing"
        if intents.wants_relationship:
            relationship_action, relationship_confidence = select_relationship_action(connection, tables, prompt)
        import_file = None
        import_confidence = "missing"
        import_mode = "create"
        if intents.wants_import:
            import_file, import_confidence = resolve_prompt_import_file(prompt)
            import_mode = import_mode_from_prompt(prompt)
        formula_action = None
        formula_confidence = "missing"
        if intents.wants_formula:
            formula_action, formula_confidence = resolve_prompt_formula_action(connection, selected_table, prompt)
        view_action = None
        view_confidence = "missing"
        if intents.wants_view and not intents.wants_formula:
            view_action, view_confidence = resolve_prompt_view_action(connection, selected_table, prompt)
        metric_action = None
        metric_confidence = "missing"
        if intents.wants_metric and not intents.wants_formula and not view_action:
            metric_action, metric_confidence = resolve_prompt_metric_action(connection, selected_table, prompt)
        semantic_action = None
        semantic_confidence = "missing"
        if intents.wants_semantic and not metric_action and not view_action and not actionable_widget_action and not dashboard_filter_action:
            semantic_action, semantic_confidence = resolve_prompt_semantic_action(connection, selected_table, prompt)
        should_create_draft = should_create_agent_draft(
            intents=intents,
            dashboard_confidence=dashboard_confidence,
            dashboard_action=dashboard_action,
            widget_action=actionable_widget_action,
            dashboard_filter_action=dashboard_filter_action,
            index_field=index_field,
            relationship_action=relationship_action,
            import_file=import_file,
            formula_action=formula_action,
            view_action=view_action,
            metric_action=metric_action,
            semantic_action=semantic_action,
            read_only=read_only,
        )
        action_payload = build_agent_action_payload(
            prompt=prompt,
            selected_dashboard=selected_dashboard,
            selected_table=selected_table,
            widget_action=actionable_widget_action,
            dashboard_filter_action=dashboard_filter_action,
            index_field=index_field,
            index_field_confidence=index_field_confidence,
            index_recommendation=index_recommendation,
            relationship_action=relationship_action,
            import_file=import_file,
            import_confidence=import_confidence,
            import_mode=import_mode,
            formula_action=formula_action,
            view_action=view_action,
            metric_action=metric_action,
            semantic_action=semantic_action,
            dashboard_action=dashboard_action,
        )
        action_key = unique_key("draft") if should_create_draft else "read_only_plan"
        action_kind = agent_action_kind(
            intents=intents,
            read_only=read_only,
            index_field=index_field,
            dashboard_action=dashboard_action,
            dashboard_filter_action=dashboard_filter_action,
            widget_action=actionable_widget_action,
            relationship_action=relationship_action,
            import_file=import_file,
            formula_action=formula_action,
            view_action=view_action,
            metric_action=metric_action,
            semantic_action=semantic_action,
        )
        if should_create_draft and action_kind == "dashboard.create":
            dashboard_create_draft = build_agent_dashboard_create_draft(connection, action_payload.get("tableKey"), prompt, 8)
            action_payload.update(
                {
                    "dashboardKey": "",
                    "dashboardName": dashboard_create_draft["dashboardName"],
                    "defaultTableKey": dashboard_create_draft["defaultTableKey"],
                    "dashboardDraft": dashboard_create_draft,
                }
            )
        if should_create_draft:
            action_label = agent_action_label(action_kind, wants_dashboard=intents.wants_dashboard)
            action_evidence = agent_action_evidence(action_kind)
            workspace_id = active_workspace_id(connection)
            create_action_draft(
                connection,
                action_key=action_key,
                workspace_id=workspace_id,
                kind=action_kind,
                label=action_label,
                payload=action_payload,
                evidence=action_evidence,
                created_at=now_iso(),
            )
            connection.commit()
        answer_card = build_agent_answer_card(connection, prompt, selected_table)
        if widget_clarification and isinstance(widget_action, dict):
            answer_card = build_widget_clarification_answer_card(widget_action)
        ontology = ontology_snapshot(connection)
    recommended = build_agent_recommended_commands(
        answer_card=answer_card,
        selected_table=selected_table,
        selected_dashboard=selected_dashboard,
        intents=intents,
        read_only=read_only,
        import_file=import_file,
        relationship_action=relationship_action,
        dashboard_filter_action=dashboard_filter_action,
        widget_action=actionable_widget_action,
        dashboard_action=dashboard_action,
        index_field=index_field,
        formula_action=formula_action,
        view_action=view_action,
        metric_action=metric_action,
        semantic_action=semantic_action,
    )
    return {
        "ok": True,
        "llm": {
            "configured": deepseek_configured,
            "mode": llm_audit["mode"],
            "audit": llm_audit,
        },
        "matched": {
            "table": selected_table,
            "tableSelectionConfidence": table_confidence,
            "dashboard": selected_dashboard,
            "dashboardSelectionConfidence": dashboard_confidence,
            "indexField": index_field,
            "indexFieldSelectionConfidence": index_field_confidence,
            "relationship": relationship_action,
            "relationshipSelectionConfidence": relationship_confidence,
            "importFile": str(import_file) if import_file else None,
            "importFileSelectionConfidence": import_confidence,
            "formula": formula_action,
            "formulaSelectionConfidence": formula_confidence,
            "view": view_action,
            "viewSelectionConfidence": view_confidence,
            "metric": metric_action,
            "metricSelectionConfidence": metric_confidence,
            "widget": widget_action,
            "widgetSelectionConfidence": widget_confidence,
            "dashboardFilter": dashboard_filter_action,
            "dashboardFilterSelectionConfidence": dashboard_filter_confidence,
            "dashboardOperation": dashboard_action,
            "dashboardOperationSelectionConfidence": dashboard_action_confidence,
            "semantic": semantic_action,
            "semanticSelectionConfidence": semantic_confidence,
        },
        "plan": [
            "确认当前 workspace 与 sourceRun 边界。 / Confirm the current workspace and sourceRun boundaries.",
            "只使用 Source Intelligence、Domain Pack、Ontology 和白名单 query runtime 形成答案。 / Use only Source Intelligence, Domain Pack, Ontology, and whitelist query runtime to form the answer.",
            "这次请求走只读解释通道，不创建 action draft。 / This request uses a read-only explanation channel and creates no action draft."
            if read_only
            else (
                "把会写入的 BI 操作保存为 action draft，等待确认。 / Save BI write operations as action drafts until confirmed."
                if should_create_draft
                else "字段选择不够确定时先给出澄清，不创建 action draft。 / Ask for clarification when field selection is uncertain and create no action draft."
            ),
        ],
        "answerCard": answer_card,
        "recommendedCommands": recommended,
        "requiresConfirmation": should_create_draft,
        "actionDraft": {
            "actionKey": action_key,
            "kind": action_kind,
            "status": "draft" if should_create_draft else "read-only",
        },
        "ontology": ontology,
        "domainPackRuntime": domain_pack_runtime(),
        "sourcePipelineContract": source_pipeline_contract(),
    }


def confirm_action_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        action = get_action_draft(connection, action_key=args.action_key, workspace_id=workspace_id)
        if not action:
            raise ValueError(f"Unknown action draft in active workspace {workspace_id}: {args.action_key}")
        payload = action_draft_payload(action)
        if args.reject:
            if not args.yes:
                return reject_dry_run_response(action, payload)
            mark_action_rejected(connection, args.action_key, now_iso())
            connection.commit()
            return rejected_response(args.action_key)
        if action["kind"] == "index.create":
            return handle_index_create_confirmation(
                connection,
                action,
                payload,
                action_key=args.action_key,
                yes=args.yes,
                confirmed_at=now_iso(),
                build_index_plan=build_index_plan,
                execute_index_plan=execute_index_plan,
            )
        if action["kind"] == "relationship.save":
            return handle_relationship_save_confirmation(
                connection,
                action,
                payload,
                action_key=args.action_key,
                yes=args.yes,
                confirmed_at=now_iso(),
                build_relationship_save_plan=build_relationship_save_plan,
                execute_relationship_save=execute_relationship_save,
            )
        if action["kind"] == "import.commit":
            return handle_import_commit_confirmation(
                connection,
                action,
                payload,
                action_key=args.action_key,
                yes=args.yes,
                confirmed_at=now_iso(),
                build_import_preview=build_import_preview,
                execute_import_commit=execute_import_commit,
            )
        if action["kind"] == "formula.save":
            return handle_formula_save_confirmation(
                connection,
                action,
                payload,
                action_key=args.action_key,
                yes=args.yes,
                confirmed_at=now_iso(),
                build_formula_save_plan=build_formula_save_plan,
                execute_formula_save_plan=execute_formula_save_plan,
            )
        if action["kind"] == "view.save":
            return handle_view_save_confirmation(
                connection,
                action,
                payload,
                action_key=args.action_key,
                yes=args.yes,
                confirmed_at=now_iso(),
                build_save_view_plan=build_save_view_plan,
                execute_save_view_plan=execute_save_view_plan,
            )
        if action["kind"] == "metric.add":
            return handle_metric_add_confirmation(
                connection,
                action,
                payload,
                action_key=args.action_key,
                yes=args.yes,
                confirmed_at=now_iso(),
                build_metric_add_plan=build_metric_add_plan,
                execute_metric_add_plan=execute_metric_add_plan,
            )
        if action["kind"] == "semantic.set":
            return handle_semantic_set_confirmation(
                connection,
                action,
                payload,
                action_key=args.action_key,
                yes=args.yes,
                confirmed_at=now_iso(),
                workspace_id=workspace_id,
                build_semantic_set_plan=build_semantic_set_plan,
                execute_semantic_set_plan=execute_semantic_set_plan,
                semantic_row_to_payload=semantic_row_to_payload,
            )
        if action["kind"] == "dashboard.widget.add":
            return handle_dashboard_widget_add_confirmation(
                connection,
                action,
                payload,
                action_key=args.action_key,
                yes=args.yes,
                confirmed_at=now_iso(),
                build_widget_proposal=build_widget_proposal,
                insert_dashboard_widget=insert_dashboard_widget,
            )
        if action["kind"] == "dashboard.filter.add":
            return handle_dashboard_filter_add_confirmation(
                connection,
                action,
                payload,
                action_key=args.action_key,
                yes=args.yes,
                confirmed_at=now_iso(),
                build_dashboard_filter_add_plan=build_dashboard_filter_add_plan,
                execute_dashboard_filter_add_plan=execute_dashboard_filter_add_plan,
            )
        if action["kind"] in {"dashboard.copy", "dashboard.rename", "dashboard.delete"}:
            return handle_dashboard_operation_confirmation(
                connection,
                action,
                payload,
                action_key=args.action_key,
                yes=args.yes,
                confirmed_at=now_iso(),
                build_dashboard_operation_plan=build_dashboard_operation_plan,
                execute_dashboard_operation_plan=execute_dashboard_operation_plan,
            )
        if action["kind"] == "dashboard.create":
            return handle_dashboard_create_confirmation(
                connection,
                action,
                payload,
                action_key=args.action_key,
                yes=args.yes,
                confirmed_at=now_iso(),
                workspace_id=workspace_id,
                unique_key=unique_key,
                build_agent_dashboard_create_draft=build_agent_dashboard_create_draft,
                write_business_dashboard=write_business_dashboard,
                upsert_navigation_module=upsert_navigation_module,
            )
        if not args.yes:
            return confirm_dry_run_response(action, payload)
        mark_action_confirmed(connection, args.action_key, now_iso())
        connection.commit()
    return confirmed_response(args.action_key)


def add_widget_style_arguments(command_parser: argparse.ArgumentParser) -> None:
    command_parser.add_argument("--sort-by", choices=B_SORT_BY)
    command_parser.add_argument("--sort-direction", choices=["asc", "desc"])
    command_parser.add_argument("--decimal-places", type=int)
    command_parser.add_argument("--table-column-limit", type=int)
    command_parser.add_argument("--slicer-display", choices=B_SLICER_DISPLAYS)
    command_parser.add_argument("--ranking-mode", choices=B_RANKING_MODES)
    command_parser.add_argument("--color-palette", choices=B_COLOR_PALETTES)
    command_parser.add_argument("--bar-orientation", choices=B_BAR_ORIENTATIONS)
    command_parser.add_argument("--pie-shape", choices=B_PIE_SHAPES)
    command_parser.add_argument("--x-axis-title")
    command_parser.add_argument("--y-axis-title")
    command_parser.add_argument("--legend-title")
    for enabled_flag, disabled_flag, dest in [
        ("--slicer-multi-select", "--single-select", "slicer_multi_select"),
        ("--slicer-searchable", "--no-slicer-search", "slicer_searchable"),
        ("--show-legend", "--hide-legend", "show_legend"),
        ("--show-axis", "--hide-axis", "show_axis"),
        ("--show-data-label", "--hide-data-label", "show_data_label"),
        ("--line-smooth", "--line-straight", "line_smooth"),
        ("--area-fill", "--no-area-fill", "area_fill"),
        ("--cross-filter", "--no-cross-filter", "cross_filter"),
        ("--drill-down", "--no-drill-down", "drill_down"),
        ("--global-filter-target", "--no-global-filter-target", "global_filter_target"),
    ]:
        group = command_parser.add_mutually_exclusive_group()
        group.add_argument(enabled_flag, dest=dest, action="store_true", default=None)
        group.add_argument(disabled_flag, dest=dest, action="store_false")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AIBI Hybrid local BI CLI")
    parser.add_argument("--json", action="store_true", help="Output JSON. Kept for compatibility; JSON is always used.")
    sub = parser.add_subparsers(dest="command", required=True)

    cli_contract = sub.add_parser("cli-contract")
    cli_contract.add_argument("--format", choices=["json", "markdown"], default="json")
    cli_contract.add_argument("--output", default="")
    cli_contract.add_argument("--command", dest="command_name", default="")

    list_commands = sub.add_parser("list-commands")
    list_commands.add_argument("--domain")
    list_commands.add_argument("--mutation-mode")
    list_commands.add_argument("--writes", choices=["yes", "no", "any"], default="any")

    sub.add_parser("status")
    sub.add_parser("quality-doctor")

    workspace_create = sub.add_parser("workspace-create")
    workspace_create.add_argument("--name", required=True)
    workspace_create.add_argument("--yes", action="store_true")

    workspace_select = sub.add_parser("workspace-select")
    workspace_select.add_argument("workspace")
    workspace_select.add_argument("--yes", action="store_true")

    workspace_rename = sub.add_parser("workspace-rename")
    workspace_rename.add_argument("workspace")
    workspace_rename.add_argument("--name", required=True)
    workspace_rename.add_argument("--yes", action="store_true")

    workspace_delete = sub.add_parser("workspace-delete")
    workspace_delete.add_argument("workspace")
    workspace_delete.add_argument("--yes", action="store_true")

    source_run = sub.add_parser("source-run")
    source_run.add_argument("source_run_id")

    sub.add_parser("list-tables")

    inspect_table = sub.add_parser("inspect-table")
    inspect_table.add_argument("table")

    rename_source = sub.add_parser("rename-source")
    rename_source.add_argument("source")
    rename_source.add_argument("--name", required=True)
    rename_source.add_argument("--yes", action="store_true")

    delete_source = sub.add_parser("delete-source")
    delete_source.add_argument("source")
    delete_source.add_argument("--yes", action="store_true")

    source_intelligence_run = sub.add_parser("source-intelligence")
    source_intelligence_run.add_argument("inputs", nargs="*")
    source_intelligence_run.add_argument("--output-dir")
    source_intelligence_run.add_argument("--label")

    source_intelligence_runs = sub.add_parser("source-intelligence-runs")
    source_intelligence_runs.add_argument("--limit", type=int, default=10)
    source_intelligence_runs.add_argument("--all", action="store_true")

    source_dashboard_draft = sub.add_parser("source-dashboard-draft")
    source_dashboard_draft.add_argument("--run", default="")
    source_dashboard_draft.add_argument("--name", default="")
    source_dashboard_draft.add_argument("--limit", type=int, default=4)

    workbench = sub.add_parser("workbench")
    workbench.add_argument("--limit", type=int, default=12)

    list_navigation = sub.add_parser("list-navigation")
    list_navigation.add_argument("--all", action="store_true")

    navigation_op = sub.add_parser("navigation-op")
    navigation_op.add_argument("--module", required=True)
    navigation_op.add_argument("--op", required=True, choices=["rename", "move", "hide", "show"])
    navigation_op.add_argument("--name", default="")
    navigation_op.add_argument("--sort", type=int, default=0)
    navigation_op.add_argument("--yes", action="store_true")

    sub.add_parser("dashboard-widget-catalog")
    sub.add_parser("b-cli-capabilities")

    recommend_widgets = sub.add_parser("recommend-widgets")
    recommend_widgets.add_argument("--table")
    recommend_widgets.add_argument("--all", action="store_true")
    recommend_widgets.add_argument("--limit", type=int, default=7)

    add_recommended_widgets = sub.add_parser("add-recommended-widgets")
    add_recommended_widgets.add_argument("--dashboard", default="default")
    add_recommended_widgets.add_argument("--table")
    add_recommended_widgets.add_argument("--limit", type=int, default=4)
    add_recommended_widgets.add_argument("--allow-duplicates", action="store_true")
    add_recommended_widgets.add_argument("--yes", action="store_true")

    save_dashboard_modules = sub.add_parser("save-dashboard-modules")
    save_dashboard_modules.add_argument("--dashboard", default="default")
    save_dashboard_modules.add_argument("--name", default="")
    save_dashboard_modules.add_argument("--default-table", default="")
    save_dashboard_modules.add_argument("--canvas-width-mode", default="stretch", choices=["stretch", "center"])
    save_dashboard_modules.add_argument("--widgets-json", default="[]")
    save_dashboard_modules.add_argument("--layout-json", default="[]")
    save_dashboard_modules.add_argument("--filters-json", default="[]")
    save_dashboard_modules.add_argument("--yes", action="store_true")

    business_dashboard = sub.add_parser("business-dashboard")
    business_dashboard.add_argument("--op", default="draft", choices=["draft", "create", "overwrite"])
    business_dashboard.add_argument("--dashboard", default="default")
    business_dashboard.add_argument("--name", default="")
    business_dashboard.add_argument("--table")
    business_dashboard.add_argument("--template", default="business", choices=["business", "cost-monitor", ERP_UNIT_LIBRARY_TEMPLATE_KEY])
    business_dashboard.add_argument("--limit", type=int, default=10)
    business_dashboard.add_argument("--yes", action="store_true")

    erp_unit_library = sub.add_parser("erp-unit-library")
    erp_unit_library.add_argument("--table")
    erp_unit_library.add_argument("--limit", type=int, default=24)
    erp_unit_library.add_argument("--select", action="store_true")
    erp_unit_library.add_argument("--summary", action="store_true")

    add_widget = sub.add_parser("add-widget")
    add_widget.add_argument("--dashboard", default="default")
    add_widget.add_argument("--widget")
    add_widget.add_argument("--type", default="bar", choices=B_WIDGET_TYPES)
    add_widget.add_argument("--table")
    add_widget.add_argument("--view")
    add_widget.add_argument("--title")
    add_widget.add_argument("--subtitle")
    add_widget.add_argument("--dimension")
    add_widget.add_argument("--measure")
    add_widget.add_argument("--agg", choices=sorted(SAFE_AGGREGATIONS))
    add_widget.add_argument("--top-n", type=int, default=12)
    add_widget.add_argument("--value-format", default="auto", choices=B_VALUE_FORMATS)
    add_widget.add_argument("--text-content")
    add_widget_style_arguments(add_widget)
    add_widget.add_argument("--yes", action="store_true")

    add_relationship_widget = sub.add_parser("add-relationship-widget")
    add_relationship_widget.add_argument("--dashboard", default="default")
    add_relationship_widget.add_argument("--widget")
    add_relationship_widget.add_argument("--relationship", default="")
    add_relationship_widget.add_argument("--type", default="bar", choices=B_RELATIONSHIP_WIDGET_TYPES)
    add_relationship_widget.add_argument("--title")
    add_relationship_widget.add_argument("--subtitle")
    add_relationship_widget.add_argument("--group")
    add_relationship_widget.add_argument("--measure")
    add_relationship_widget.add_argument("--agg", default="count", choices=sorted(SAFE_AGGREGATIONS))
    add_relationship_widget.add_argument("--top-n", type=int, default=12)
    add_relationship_widget.add_argument("--value-format", default="auto", choices=B_VALUE_FORMATS)
    add_widget_style_arguments(add_relationship_widget)
    add_relationship_widget.add_argument("--yes", action="store_true")

    set_widget = sub.add_parser("set-widget")
    set_widget.add_argument("--widget", required=True)
    set_widget.add_argument("--type", choices=B_WIDGET_TYPES)
    set_widget.add_argument("--table")
    set_widget.add_argument("--view")
    set_widget.add_argument("--title")
    set_widget.add_argument("--subtitle")
    set_widget.add_argument("--dimension")
    set_widget.add_argument("--measure")
    set_widget.add_argument("--agg", choices=sorted(SAFE_AGGREGATIONS))
    set_widget.add_argument("--top-n", type=int)
    set_widget.add_argument("--value-format", choices=B_VALUE_FORMATS)
    set_widget.add_argument("--text-content")
    add_widget_style_arguments(set_widget)
    set_widget.add_argument("--filter", action="append", default=[])
    set_widget.add_argument("--clear-filters", action="store_true")
    set_widget.add_argument("--yes", action="store_true")

    copy_widget = sub.add_parser("copy-widget")
    copy_widget.add_argument("--widget", required=True)
    copy_widget.add_argument("--dashboard")
    copy_widget.add_argument("--title")
    copy_widget.add_argument("--clear-filters", action="store_true")
    copy_widget.add_argument("--yes", action="store_true")

    remove_widget = sub.add_parser("remove-widget")
    remove_widget.add_argument("--widget", required=True)
    remove_widget.add_argument("--yes", action="store_true")

    set_import_policy = sub.add_parser("set-import-policy")
    set_import_policy.add_argument("--table", required=True)
    set_import_policy.add_argument("--unique-fields", required=True)
    set_import_policy.add_argument("--conflict-rule", default="overwrite", choices=["overwrite", "fill-empty", "skip-existing"])
    set_import_policy.add_argument("--yes", action="store_true")

    preview = sub.add_parser("preview-import")
    preview.add_argument("file")
    preview.add_argument("--table")
    preview.add_argument("--unique-fields")
    preview.add_argument("--conflict-rule", choices=["overwrite", "fill-empty", "skip-existing"])

    commit = sub.add_parser("import-commit")
    commit.add_argument("file")
    commit.add_argument("--table")
    commit.add_argument("--name")
    commit.add_argument("--mode", default="create", choices=["create", "merge", "replace"])
    commit.add_argument("--unique-fields")
    commit.add_argument("--conflict-rule", choices=["overwrite", "fill-empty", "skip-existing"])
    commit.add_argument("--yes", action="store_true")

    preview_folder = sub.add_parser("preview-import-folder")
    preview_folder.add_argument("path")
    preview_folder.add_argument("--limit", type=int, default=200)
    preview_folder.add_argument("--no-recursive", action="store_true")

    import_folder = sub.add_parser("import-folder")
    import_folder.add_argument("path")
    import_folder.add_argument("--limit", type=int, default=200)
    import_folder.add_argument("--no-recursive", action="store_true")
    import_folder.add_argument("--yes", action="store_true")

    list_import_jobs = sub.add_parser("list-import-jobs")
    list_import_jobs.add_argument("--table")
    list_import_jobs.add_argument("--status")
    list_import_jobs.add_argument("--search")
    list_import_jobs.add_argument("--limit", type=int, default=20)

    remove_import_job = sub.add_parser("remove-import-job")
    remove_import_job.add_argument("--job", required=True)
    remove_import_job.add_argument("--yes", action="store_true")

    list_connectors = sub.add_parser("list-connectors")
    list_connectors.add_argument("--type", choices=sorted(VALID_CONNECTOR_TYPES))
    list_connectors.add_argument("--status", choices=sorted(VALID_CONNECTOR_STATUSES))
    list_connectors.add_argument("--search")

    save_connector = sub.add_parser("save-connector")
    save_connector.add_argument("--connector")
    save_connector.add_argument("--name", required=True)
    save_connector.add_argument("--type", default="file", choices=sorted(VALID_CONNECTOR_TYPES))
    save_connector.add_argument("--provider", default="")
    save_connector.add_argument("--status", default="draft", choices=sorted(VALID_CONNECTOR_STATUSES))
    save_connector.add_argument("--endpoint", default="")
    save_connector.add_argument("--import-mode", default="auto", choices=["auto", "create", "replace", "merge"])
    save_connector.add_argument("--target-table", default="")
    save_connector.add_argument("--unique-fields", default="")
    save_connector.add_argument("--conflict-rule", default="overwrite", choices=["overwrite", "fill-empty", "skip-existing"])
    save_connector.add_argument("--schedule", default="manual")
    save_connector.add_argument("--notes", default="")
    save_connector.add_argument("--yes", action="store_true")

    sync_connector = sub.add_parser("sync-connector")
    sync_connector.add_argument("--connector", required=True)
    sync_connector.add_argument("--allow-paused", action="store_true")
    sync_connector.add_argument("--yes", action="store_true")

    remove_connector = sub.add_parser("remove-connector")
    remove_connector.add_argument("--connector", required=True)
    remove_connector.add_argument("--yes", action="store_true")

    infer_semantics = sub.add_parser("infer-semantics")
    infer_semantics.add_argument("--table", default="")
    infer_semantics.add_argument("--overwrite-manual", action="store_true")
    infer_semantics.add_argument("--yes", action="store_true")

    list_semantics = sub.add_parser("list-semantics")
    list_semantics.add_argument("--table", default="")

    set_semantic = sub.add_parser("set-semantic")
    set_semantic.add_argument("table")
    set_semantic.add_argument("field")
    set_semantic.add_argument("--role", required=True, choices=["event_time", "time", "measure", "dimension", "identity_key", "identifier", "status", "text"])
    set_semantic.add_argument("--tag", action="append", default=[])
    set_semantic.add_argument("--usage", action="append", default=[])
    set_semantic.add_argument("--confidence", type=float, default=1.0)
    set_semantic.add_argument("--note", default="")
    set_semantic.add_argument("--yes", action="store_true")

    infer_metrics = sub.add_parser("infer-metrics")
    infer_metrics.add_argument("--table", default="")
    infer_metrics.add_argument("--yes", action="store_true")

    list_metrics = sub.add_parser("list-metrics")
    list_metrics.add_argument("--table", default="")
    list_metrics.add_argument("--all", action="store_true")

    add_metric = sub.add_parser("add-metric")
    add_metric.add_argument("--id", default="")
    add_metric.add_argument("--name", required=True)
    add_metric.add_argument("--table", required=True)
    add_metric.add_argument("--field", default="*")
    add_metric.add_argument("--agg", default="count", choices=sorted(SAFE_AGGREGATIONS))
    add_metric.add_argument("--dimension", default="")
    add_metric.add_argument("--time-field", default="")
    add_metric.add_argument("--filter", action="append", default=[])
    add_metric.add_argument("--value-format", default="auto", choices=B_VALUE_FORMATS)
    add_metric.add_argument("--description", default="")
    add_metric.add_argument("--yes", action="store_true")

    list_formulas = sub.add_parser("list-formulas")
    list_formulas.add_argument("--table", default="")
    list_formulas.add_argument("--all", action="store_true")

    save_formula = sub.add_parser("save-formula")
    save_formula.add_argument("--id", default="")
    save_formula.add_argument("--name", required=True)
    save_formula.add_argument("--table", required=True)
    save_formula.add_argument("--expression", required=True)
    save_formula.add_argument("--mode", default="aggregate", choices=["row", "aggregate"])
    save_formula.add_argument("--dimension", default="")
    save_formula.add_argument("--time-field", default="")
    save_formula.add_argument("--value-format", default="auto", choices=B_VALUE_FORMATS)
    save_formula.add_argument("--description", default="")
    save_formula.add_argument("--yes", action="store_true")

    delete_formula = sub.add_parser("delete-formula")
    delete_formula.add_argument("formula")
    delete_formula.add_argument("--yes", action="store_true")

    query_metric = sub.add_parser("query-metric")
    query_metric.add_argument("metric")
    query_metric.add_argument("--group", action="append", default=[])
    query_metric.add_argument("--filter", action="append", default=[])
    query_metric.add_argument("--sort", default="")
    query_metric.add_argument("--limit", type=int, default=50)

    preferences = sub.add_parser("preferences")
    preferences.add_argument("--theme-key")
    preferences.add_argument("--require-delete-name-confirmation", choices=["true", "false"])
    preferences.add_argument("--auto-save-dashboard-on-switch", choices=["true", "false"])
    preferences.add_argument("--agent-can-manage-generated-assets", choices=["true", "false"])
    preferences.add_argument("--agent-can-manage-manual-assets", choices=["true", "false"])
    preferences.add_argument("--yes", action="store_true")

    theme_palettes = sub.add_parser("theme-palettes")
    theme_palettes.add_argument("--action", default="list", choices=["list", "save", "upsert", "delete"])
    theme_palettes.add_argument("--theme-key")
    theme_palettes.add_argument("--name", default="")
    theme_palettes.add_argument("--mode", default="light", choices=["light", "dark"])
    theme_palettes.add_argument("--tokens-json", default="")
    theme_palettes.add_argument("--sort", type=int, default=0)
    theme_palettes.add_argument("--yes", action="store_true")

    sub.add_parser("validate-config")

    export_config = sub.add_parser("export-config")
    export_config.add_argument("output", nargs="?")

    apply_config = sub.add_parser("apply-config")
    apply_config.add_argument("input")
    apply_config.add_argument("--yes", action="store_true")

    query = sub.add_parser("query")
    query.add_argument("--table", required=True)
    query.add_argument("--group")
    query.add_argument("--measure", default="*")
    query.add_argument("--agg", default="count")
    query.add_argument("--limit", type=int, default=20)

    query_table = sub.add_parser("query-table")
    query_table.add_argument("--table")
    query_table.add_argument("--view")
    query_table.add_argument("--mode", default="detail", choices=["detail", "aggregate"])
    query_table.add_argument("--column", action="append")
    query_table.add_argument("--filter", action="append", default=[])
    query_table.add_argument("--sort", action="append", default=[])
    query_table.add_argument("--search")
    query_table.add_argument("--offset", type=int, default=0)
    query_table.add_argument("--limit", type=int, default=50)
    query_table.add_argument("--group", action="append", default=[])
    query_table.add_argument("--measure", default="")
    query_table.add_argument("--agg", default="count", choices=sorted(SAFE_AGGREGATIONS))

    list_views = sub.add_parser("list-views")
    list_views.add_argument("--table")

    save_view = sub.add_parser("save-view")
    save_view.add_argument("--view")
    save_view.add_argument("--table", required=True)
    save_view.add_argument("--name", required=True)
    save_view.add_argument("--tag")
    save_view.add_argument("--mode", default="detail", choices=["detail", "aggregate"])
    save_view.add_argument("--columns", default="")
    save_view.add_argument("--filter", action="append", default=[])
    save_view.add_argument("--sort", action="append", default=[])
    save_view.add_argument("--search", default="")
    save_view.add_argument("--agent", action="store_true")
    save_view.add_argument("--yes", action="store_true")

    copy_view = sub.add_parser("copy-view")
    copy_view.add_argument("--view", required=True)
    copy_view.add_argument("--name")
    copy_view.add_argument("--tag")
    copy_view.add_argument("--yes", action="store_true")

    delete_view = sub.add_parser("delete-view")
    delete_view.add_argument("--view", required=True)
    delete_view.add_argument("--yes", action="store_true")

    dashboards = sub.add_parser("dashboards")
    dashboards.add_argument("--dashboard")

    list_filters = sub.add_parser("list-filters")
    list_filters.add_argument("--dashboard", default="default")

    add_filter = sub.add_parser("add-filter")
    add_filter.add_argument("--dashboard", default="default")
    add_filter.add_argument("--field", required=True)
    add_filter.add_argument("--operator", default="equals", choices=B_DASHBOARD_FILTER_OPERATORS)
    add_filter.add_argument("--value", default="")
    add_filter.add_argument("--disabled", action="store_true")
    add_filter.add_argument("--yes", action="store_true")

    set_filter = sub.add_parser("set-filter")
    set_filter.add_argument("--dashboard", default="default")
    set_filter.add_argument("--filter", required=True)
    set_filter.add_argument("--field", required=True)
    set_filter.add_argument("--operator", default="equals", choices=B_DASHBOARD_FILTER_OPERATORS)
    set_filter.add_argument("--value", default="")
    set_filter.add_argument("--disabled", action="store_true")
    set_filter.add_argument("--yes", action="store_true")

    remove_filter = sub.add_parser("remove-filter")
    remove_filter.add_argument("--dashboard", default="default")
    remove_filter.add_argument("--filter", required=True)
    remove_filter.add_argument("--yes", action="store_true")

    remove_stale_filters = sub.add_parser("remove-stale-filters")
    remove_stale_filters.add_argument("--dashboard", default="default")
    remove_stale_filters.add_argument("--yes", action="store_true")

    clear_filters = sub.add_parser("clear-filters")
    clear_filters.add_argument("--dashboard", default="default")
    clear_filters.add_argument("--yes", action="store_true")

    recommend_indexes = sub.add_parser("recommend-indexes")
    recommend_indexes.add_argument("--table")
    recommend_indexes.add_argument("--limit", type=int, default=12)

    create_index = sub.add_parser("create-index")
    create_index.add_argument("--table", required=True)
    create_index.add_argument("--field", required=True)
    create_index.add_argument("--index", default="")
    create_index.add_argument("--yes", action="store_true")

    dashboard_op = sub.add_parser("dashboard-op")
    dashboard_op.add_argument("--op", required=True, choices=["create", "copy", "rename", "delete"])
    dashboard_op.add_argument("--dashboard")
    dashboard_op.add_argument("--source")
    dashboard_op.add_argument("--name")
    dashboard_op.add_argument("--table")
    dashboard_op.add_argument("--yes", action="store_true")

    field_update = sub.add_parser("field-update")
    field_update.add_argument("--table", required=True)
    field_update.add_argument("--field", required=True)
    field_update.add_argument("--role", required=True, choices=["identity_key", "event_time", "dimension", "measure", "status"])
    field_update.add_argument("--usage", required=True, choices=["joinable", "filterable", "groupable", "aggregatable"])
    field_update.add_argument("--confidence", type=float, default=0.9)
    field_update.add_argument("--yes", action="store_true")

    relationship = sub.add_parser("relationship-preview")
    relationship.add_argument("--left-table", required=True)
    relationship.add_argument("--right-table", required=True)
    relationship.add_argument("--left-field", required=True)
    relationship.add_argument("--right-field", required=True)
    relationship.add_argument("--join-type", default="left", choices=["left", "inner"])
    relationship.add_argument("--limit", type=int, default=20)

    relationship_save = sub.add_parser("relationship-save")
    relationship_save.add_argument("--left-table", required=True)
    relationship_save.add_argument("--right-table", required=True)
    relationship_save.add_argument("--left-field", required=True)
    relationship_save.add_argument("--right-field", required=True)
    relationship_save.add_argument("--join-type", default="left", choices=["left", "inner"])
    relationship_save.add_argument("--limit", type=int, default=20)
    relationship_save.add_argument("--yes", action="store_true")

    recommend_relationships = sub.add_parser("recommend-relationships")
    recommend_relationships.add_argument("--limit", type=int, default=12)

    list_relationships = sub.add_parser("list-relationships")

    remove_relationship = sub.add_parser("remove-relationship")
    remove_relationship.add_argument("--relationship", required=True)
    remove_relationship.add_argument("--yes", action="store_true")

    query_relationship = sub.add_parser("query-relationship")
    query_relationship.add_argument("--relationship", default="")
    query_relationship.add_argument("--left-table")
    query_relationship.add_argument("--right-table")
    query_relationship.add_argument("--left-field")
    query_relationship.add_argument("--right-field")
    query_relationship.add_argument("--join-type", default="left", choices=["left", "inner"])
    query_relationship.add_argument("--group", action="append", default=[])
    query_relationship.add_argument("--measure", default="")
    query_relationship.add_argument("--agg", default="count", choices=sorted(SAFE_AGGREGATIONS))
    query_relationship.add_argument("--filter", action="append", default=[])
    query_relationship.add_argument("--limit", type=int, default=50)
    query_relationship.add_argument("--sort-by", default="metric", choices=["metric", "dimension"])
    query_relationship.add_argument("--sort-direction", default="desc", choices=["asc", "desc"])

    formula = sub.add_parser("formula-preview")
    formula.add_argument("expression")
    formula.add_argument("--table")
    formula.add_argument("--mode", default="aggregate", choices=["row", "aggregate"])

    ask = sub.add_parser("ask")
    ask.add_argument("--read-only", action="store_true")
    ask.add_argument("prompt", nargs="+")

    confirm = sub.add_parser("confirm-action")
    confirm.add_argument("action_key")
    confirm.add_argument("--reject", action="store_true")
    confirm.add_argument("--yes", action="store_true")

    drafts = sub.add_parser("action-drafts")
    drafts.add_argument("--limit", type=int, default=12)
    drafts.add_argument("--all", action="store_true")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "cli-contract":
            result = cli_contract_command(args, parser)
        elif args.command == "list-commands":
            result = list_commands_command(args, parser)
        elif args.command == "status":
            result = status_command(args)
        elif args.command == "quality-doctor":
            result = quality_doctor_command(args)
        elif args.command == "workspace-create":
            result = workspace_create_command(args)
        elif args.command == "workspace-select":
            result = workspace_select_command(args)
        elif args.command == "workspace-rename":
            result = workspace_rename_command(args)
        elif args.command == "workspace-delete":
            result = workspace_delete_command(args)
        elif args.command == "source-run":
            result = source_run_command(args)
        elif args.command == "list-tables":
            result = list_tables_command(args)
        elif args.command == "inspect-table":
            result = inspect_table_command(args)
        elif args.command == "rename-source":
            result = rename_source_command(args)
        elif args.command == "delete-source":
            result = delete_source_command(args)
        elif args.command == "source-intelligence":
            result = source_intelligence_command(args)
        elif args.command == "source-intelligence-runs":
            result = source_intelligence_runs_command(args)
        elif args.command == "source-dashboard-draft":
            result = source_intelligence_dashboard_draft_command(args)
        elif args.command == "workbench":
            result = workbench_command(args)
        elif args.command == "list-navigation":
            result = list_navigation_command(args)
        elif args.command == "navigation-op":
            result = navigation_operation_command(args)
        elif args.command == "dashboard-widget-catalog":
            result = dashboard_widget_catalog_command(args)
        elif args.command == "b-cli-capabilities":
            result = b_cli_capabilities_command(args)
        elif args.command == "recommend-widgets":
            result = recommend_widgets_command(args)
        elif args.command == "add-recommended-widgets":
            result = add_recommended_widgets_command(args)
        elif args.command == "save-dashboard-modules":
            result = save_dashboard_modules_command(args)
        elif args.command == "business-dashboard":
            result = business_dashboard_command(args)
        elif args.command == "erp-unit-library":
            result = erp_unit_library_command(args)
        elif args.command == "add-widget":
            result = add_widget_command(args)
        elif args.command == "add-relationship-widget":
            result = add_relationship_widget_command(args)
        elif args.command == "set-widget":
            result = set_widget_command(args)
        elif args.command == "copy-widget":
            result = copy_widget_command(args)
        elif args.command == "remove-widget":
            result = remove_widget_command(args)
        elif args.command == "set-import-policy":
            result = set_import_policy_command(args)
        elif args.command == "preview-import":
            result = preview_import_command(args)
        elif args.command == "import-commit":
            result = import_commit_command(args)
        elif args.command == "preview-import-folder":
            result = preview_import_folder_command(args)
        elif args.command == "import-folder":
            result = import_folder_command(args)
        elif args.command == "list-import-jobs":
            result = list_import_jobs_command(args)
        elif args.command == "remove-import-job":
            result = remove_import_job_command(args)
        elif args.command == "list-connectors":
            result = list_connectors_command(args)
        elif args.command == "save-connector":
            result = save_connector_command(args)
        elif args.command == "sync-connector":
            result = sync_connector_command(args)
        elif args.command == "remove-connector":
            result = remove_connector_command(args)
        elif args.command == "infer-semantics":
            result = infer_semantics_command(args)
        elif args.command == "list-semantics":
            result = list_semantics_command(args)
        elif args.command == "set-semantic":
            result = set_semantic_command(args)
        elif args.command == "infer-metrics":
            result = infer_metrics_command(args)
        elif args.command == "list-metrics":
            result = list_metrics_command(args)
        elif args.command == "add-metric":
            result = add_metric_command(args)
        elif args.command == "query-metric":
            result = query_metric_command(args)
        elif args.command == "preferences":
            result = preferences_command(args)
        elif args.command == "theme-palettes":
            result = theme_palettes_command(args)
        elif args.command == "validate-config":
            result = validate_config_command(args)
        elif args.command == "export-config":
            result = export_config_command(args)
        elif args.command == "apply-config":
            result = apply_config_command(args)
        elif args.command == "query":
            result = query_command(args)
        elif args.command == "query-table":
            result = query_table_command(args)
        elif args.command == "list-views":
            result = list_views_command(args)
        elif args.command == "save-view":
            result = save_view_command(args)
        elif args.command == "copy-view":
            result = copy_view_command(args)
        elif args.command == "delete-view":
            result = delete_view_command(args)
        elif args.command == "dashboards":
            result = dashboards_command(args)
        elif args.command == "list-filters":
            result = list_filters_command(args)
        elif args.command in {"add-filter", "set-filter"}:
            result = add_or_set_filter_command(args)
        elif args.command == "remove-filter":
            result = remove_filter_command(args)
        elif args.command == "remove-stale-filters":
            result = remove_stale_filters_command(args)
        elif args.command == "clear-filters":
            result = clear_filters_command(args)
        elif args.command == "recommend-indexes":
            result = recommend_indexes_command(args)
        elif args.command == "create-index":
            result = create_index_command(args)
        elif args.command == "dashboard-op":
            result = dashboard_operation_command(args)
        elif args.command == "field-update":
            result = update_field_command(args)
        elif args.command == "relationship-preview":
            result = relationship_preview_command(args)
        elif args.command == "relationship-save":
            result = relationship_save_command(args)
        elif args.command == "recommend-relationships":
            result = recommend_relationships_command(args)
        elif args.command == "list-relationships":
            result = list_relationships_command(args)
        elif args.command == "remove-relationship":
            result = remove_relationship_command(args)
        elif args.command == "query-relationship":
            result = query_relationship_command(args)
        elif args.command == "formula-preview":
            result = formula_preview_command(args)
        elif args.command == "list-formulas":
            result = list_formulas_command(args)
        elif args.command == "save-formula":
            result = save_formula_command(args)
        elif args.command == "delete-formula":
            result = delete_formula_command(args)
        elif args.command == "ask":
            args.prompt = " ".join(args.prompt)
            result = ask_command(args)
        elif args.command == "confirm-action":
            result = confirm_action_command(args)
        elif args.command == "action-drafts":
            result = action_drafts_command(args)
        else:
            raise ValueError(f"Unknown command: {args.command}")
        result = enrich_cli_output(result, args, parser)
        dump(result)
        return 0 if result.get("ok", False) else 1
    except Exception as exc:
        dump(error_output(str(getattr(args, "command", "")), exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
