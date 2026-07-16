#!/usr/bin/env python
from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Iterable

from bi_cli_parser import build_parser
from aibi_contracts import core_semantic_runtime as build_core_semantic_runtime
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
from agent_intent_service import build_business_intent_frame
from business_understanding_service import (
    apply_business_understanding_to_intent,
    build_business_understanding_frame,
    build_business_understanding_gap,
)
from semantic_context_router import build_semantic_context_bundle
from agent_clarification_service import build_agent_clarification
from agent_recommended_commands import build_agent_recommended_commands
from bi_cli_core import (
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
from capability_contract_service import capability_registry
from bi_cli_envelope import enrich_cli_output, error_output
from bi_cli_evidence_bundles import artifact_ref, write_evidence_bundle
from context_pack_service import context_pack_command, context_rule_command, context_term_command, contextualized_prompt, matched_context
from semantic_patch_service import (
    knowledge_source_adapters_command,
    knowledge_sources_command,
    semantic_patch_proposals_command,
    semantic_patch_propose_command,
    semantic_patch_review_command,
)
from analysis_safety_guard import build_verified_analysis_gap, requires_verified_analysis_plan
from domain_pack_service import domain_pack_runtime_context, is_domain_pack_enabled
from analytical_skill_service import analytical_skill_runtime_context
from platform_analytics_knowledge import (
    execute_platform_knowledge,
    match_platform_knowledge,
    platform_knowledge_context,
    platform_knowledge_pack,
)
from query_plan_receipt_service import create_query_plan_receipt, get_query_receipt, query_receipts_command
from semantic_query_planner import BLOCKING_STATUSES, build_workspace_semantic_plan, semantic_query_prompt_directives
from semantic_query_execution import execute_workspace_semantic_query
from evidence_export_service import export_evidence_command
from analysis_export_service import export_analysis_command
from confirmed_query_service import (
    confirm_query_command,
    confirmed_plans_command,
    confirmed_queries_command,
    create_confirmed_query_candidate,
    recall_confirmed_plans,
    recall_receipts_command,
)
from analysis_run_service import analysis_runs_command, create_analysis_run, validate_branch_parent
from exploration_thread_service import (
    exploration_anchor_add_command,
    exploration_board_set_command,
    exploration_thread_create_command,
    exploration_threads_command,
)
from limited_research_run_service import (
    research_run_create_command,
    research_run_finalize_command,
    research_run_observe_command,
    research_run_revise_command,
    research_runs_command,
)
from analysis_unit_service import (
    analysis_unit_build_command,
    analysis_unit_verify_command,
    analysis_units_command,
    attach_analysis_unit,
    chart_adapt_command,
)
from analysis_snapshot_service import (
    analysis_snapshot_create_command,
    analysis_snapshot_delete_command,
    analysis_snapshot_refresh_command,
    analysis_snapshot_replace_command,
    analysis_snapshots_command,
)
from metric_monitor_service import (
    metric_monitor_create_command,
    metric_monitor_delete_command,
    metric_monitor_replace_command,
    metric_monitor_run_command,
    metric_monitors_command,
)
from forecast_readiness_service import forecast_readiness_command
from job_command_service import job_cancel_command, job_recover_command, jobs_command
from source_intelligence_job_service import (
    job_process_exit_command,
    source_intelligence_job_create_command,
    source_intelligence_job_run_command,
)
from workflow_command_service import capability_contracts_command, context_budget_command, workflow_plan_command
from agent_turn_service import agent_turns_command, cancel_agent_turn_command, run_agent_turn_command
from agent_session_service import agent_context_compact_command, agent_session_create_command, agent_session_fork_command, agent_session_resume_command, agent_sessions_command
from agent_runtime_profile_service import agent_provider_evaluation_record_command, agent_provider_evaluations_command, agent_runtime_profile_set_command, agent_runtime_profiles_command
from plan_quality_service import business_expression_cases_command, plan_quality_evaluate_command, plan_quality_scorecards_command
from restricted_workflow_graph_service import agent_workflow_graph_command, restricted_workflow_operators_command, restricted_workflow_validate_command
from workspace_manifest_service import business_field_profiles_command, runtime_catalog_command, workspace_manifest_command, workspace_planning_binding
from bi_cli_schema import (
    active_workspace_id,
    all_available_fields,
    delete_theme_palette,
    ensure_default_preferences_and_themes,
    ensure_navigation_modules,
    ensure_schema,
    get_system_flag,
    list_navigation_modules,
    list_theme_palettes,
    load_user_preferences,
    navigation_module_payload,
    normalize_theme_palette,
    normalize_theme_tokens,
    normalize_user_preferences,
    open_db,
    physical_table_for_workspace,
    registry_for_table,
    save_user_preferences,
    set_system_flag,
    table_columns,
    table_exists,
    upsert_navigation_module,
    upsert_theme_palette,
    validate_theme_palette_payload,
    workspace_records,
)
from bi_cli_io_services import (
    analysis_columns_for_table,
    apply_config_command,
    calculated_field_names_for_table,
    config_row_for_export,
    connector_by_key_or_name,
    connector_row_to_dict,
    coerce_value,
    create_metrics_for_profile,
    export_config_command,
    export_metadata_config,
    import_csv_as_table,
    infer_role,
    load_connectors,
    merge_import_into_table,
    metric_sql_doctor_from_run,
    normalize_connector_key,
    normalize_connector_status,
    normalize_connector_type,
    parse_json_object,
    prepare_config_rows_for_restore,
    profile_rows,
    read_json_artifact,
    read_table_file,
    redact_secret_value,
    resolve_connector_endpoint,
    restore_config_rows,
    restore_redacted_value,
    rows_to_dicts,
    saved_import_policy,
    update_table_metadata_after_write,
    validate_config_command,
    validate_metadata_config,
)
from bi_cli_system_commands import (
    analytical_skill_install_command,
    analytical_skill_lint_command,
    analytical_skill_match_command,
    analytical_skill_set_command,
    analytical_skill_uninstall_command,
    analytical_skills_command,
    cli_contract_command,
    domain_pack_install_command,
    domain_pack_lint_command,
    domain_pack_set_command,
    domain_pack_uninstall_command,
    domain_packs_command,
    list_commands_command,
    quality_doctor_command,
    status_command,
    workspace_create_command,
    workspace_delete_command,
    workspace_rename_command,
    workspace_select_command,
)
from bi_cli_source_commands import (
    build_delete_source_plan,
    build_import_preview,
    delete_source_command,
    discover_connector_command,
    federation_proof_command,
    execute_import_commit,
    import_commit_command,
    import_folder_command,
    inspect_table_command,
    list_connectors_command,
    list_connector_adapters_command,
    list_import_jobs_command,
    list_tables_command,
    preferences_command,
    preferences_payload,
    preview_import_command,
    preview_import_folder_command,
    preview_connector_command,
    remaining_table_key_after_delete,
    remove_connector_command,
    remove_import_job_command,
    rename_source_command,
    resolve_table_registry,
    save_connector_command,
    set_import_policy_command,
    source_intelligence_command,
    source_intelligence_runs_command,
    source_run_command,
    plan_connector_sync_command,
    sync_connector_command,
    theme_palettes_command,
)
from bi_cli_query_view_commands import (
    build_save_view_plan,
    copy_view_command,
    delete_view_command,
    execute_save_view_plan,
    list_views_command,
    query_command,
    query_table_command,
    resolve_view,
    save_view_command,
    saved_view_summary,
)
from bi_cli_dashboard_commands import (
    add_or_set_filter_command,
    build_dashboard_filter_add_plan,
    build_index_plan,
    clear_filters_command,
    create_index_command,
    dashboard_filter_fields,
    dashboard_filter_status,
    dashboard_filters_snapshot,
    dashboard_layout,
    dashboards_command,
    execute_dashboard_filter_add_plan,
    execute_index_plan,
    filter_value_required,
    list_filters_command,
    list_navigation_command,
    navigation_operation_command,
    normalize_filter_rule,
    recommend_indexes_command,
    recommend_indexes_for_table,
    remove_filter_command,
    remove_stale_filters_command,
    save_dashboard_filters,
    workbench_command,
)
from bi_cli_widget_commands import (
    add_recommended_widgets_command,
    add_relationship_widget_command,
    add_widget_command,
    build_agent_dashboard_create_draft,
    build_business_analysis_templates,
    build_business_dashboard_payload,
    build_relationship_widget_proposal,
    build_widget_proposal,
    business_dashboard_command,
    copy_widget_command,
    dashboard_exists,
    dashboard_widget_catalog_command,
    dashboard_widget_row_to_dict,
    erp_unit_library_command,
    field_names_by_role,
    field_names_by_usage,
    first_saved_view,
    parse_json_array_arg,
    preferred_table_key,
    recommend_widgets_command,
    remove_widget_command,
    resolve_relationship_for_widget,
    save_dashboard_modules_command,
    set_widget_command,
    table_display_name,
    table_template_fields,
    template_widget_layout,
    widget_filters_from_args,
    widget_recommendations_for_table,
    write_business_dashboard,
)
from bi_cli_misc_commands import cli_capabilities_command, update_field_command
from bi_cli_semantic_metric_commands import (
    add_metric_command,
    build_metric_add_plan,
    build_semantic_set_plan,
    cleanup_stale_auto_metrics,
    execute_metric_add_plan,
    execute_semantic_set_plan,
    infer_field_semantic_hybrid,
    infer_metrics_command,
    infer_metrics_for_table,
    infer_semantics_command,
    list_metrics_command,
    list_semantics_command,
    metric_filters_from_cli,
    metric_key_for,
    metric_row_to_payload,
    normalize_semantic_role,
    primary_usage_from_object,
    semantic_row_to_payload,
    semantic_usage_object,
    set_semantic_command,
    upsert_metric_definition,
    upsert_semantic_config,
)
from bi_cli_relationship_formula_commands import (
    action_drafts_command,
    build_dashboard_operation_plan,
    build_formula_metric_query,
    build_formula_save_plan,
    build_relationship_save_plan,
    calculated_field_row_to_payload,
    calculated_field_usage,
    compile_formula_for_table,
    dashboard_operation_command,
    delete_formula_command,
    execute_dashboard_operation_plan,
    execute_formula_save_plan,
    execute_relationship_save,
    formula_key_for,
    formula_preview_command,
    list_formulas_command,
    list_relationships_command,
    normalize_relation_field_name,
    parse_relationship_filter,
    query_metric_command,
    query_relationship_command,
    recommend_relationships_command,
    recommend_relationships_for_connection,
    relation_candidate_fields,
    relationship_name_score,
    relationship_preview_command,
    relationship_rows_for_chart,
    relationship_save_command,
    remove_relationship_command,
    resolve_relationship_query_inputs,
    sample_field_values,
    save_formula_command,
    saved_relationship_signatures,
    to_number,
)
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
    SAFE_AGGREGATIONS,
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


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def source_intelligence_dashboard_draft_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = str(getattr(args, "workspace", "") or active_workspace_id(connection))
        if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
            raise ValueError(f"Unknown workspace: {workspace_id}")
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


def source_pipeline_contract() -> dict[str, Any]:
    return build_source_pipeline_contract()


def core_semantic_runtime() -> dict[str, Any]:
    return build_core_semantic_runtime()


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
    workspace_id = active_workspace_id(connection)
    semantic_roles = {
        str(row["field_name"]): str(row["role"] or "")
        for row in connection.execute(
            "SELECT field_name, role FROM field_semantics WHERE table_key = ? AND workspace_id = ?",
            (table_key, workspace_id),
        ).fetchall()
    }
    for column in columns:
        normalized_column = normalize_match_text(column)
        if normalized_column and normalized_column in normalized_prompt and semantic_roles.get(column) in {"dimension", "status", "event_time", "identity_key"}:
            return column
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
    lower = prompt.lower()
    explicit_expression = extract_formula_expression_from_prompt(prompt)
    name = "Agent 公式指标"
    expression = explicit_expression
    confidence = "explicit" if explicit_expression else "missing"
    if explicit_expression:
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
    if any(token in prompt for token in ["记录数", "行数", "条数"]) or "count" in lower or measure == "*":
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


def widget_candidate_fields(
    connection: sqlite3.Connection,
    table_key: str,
    roles: list[str],
    limit: int = 5,
    allow_untyped_fallback: bool = True,
) -> list[str]:
    candidates: list[str] = []
    for role in roles:
        for field in field_names_by_role(connection, table_key, role):
            if field and not str(field).startswith("__") and field not in candidates:
                candidates.append(field)
            if len(candidates) >= limit:
                return candidates
    if candidates or not allow_untyped_fallback:
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
    candidate_measures = widget_candidate_fields(connection, table_key, ["measure"], 5, allow_untyped_fallback=False)
    candidate_dimensions = widget_candidate_fields(connection, table_key, ["event_time", "dimension", "status"], 5, allow_untyped_fallback=False)
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
    if selected_dashboard and dashboard_confidence not in {"explicit", "fallback"}:
        return None, "missing"
    dashboard_key = str(selected_dashboard["dashboard_key"]) if selected_dashboard else ""
    table_key = str(selected_table["table_key"]) if selected_table else ""
    if table_confidence != "explicit" and selected_dashboard and selected_dashboard.get("default_table_key"):
        table_key = str(selected_dashboard["default_table_key"])
    if not table_key:
        return None, "missing"
    widget_type, widget_type_confidence = widget_type_from_prompt(prompt)
    measure, measure_confidence = select_metric_field_from_prompt(connection, table_key, prompt)
    dimension, dimension_confidence = select_metric_dimension_from_prompt(connection, table_key, prompt, measure)
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
    proposed = None
    if dashboard_key:
        try:
            proposed = build_widget_proposal(connection, dashboard_key, widget_type, options)
        except ValueError:
            return None, "missing"
    return {
        "dashboardKey": dashboard_key,
        "widgetType": widget_type,
        "tableKey": table_key,
        "title": title,
        "measure": measure,
        "dimension": dimension,
        "aggregation": aggregation,
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


def answer_table_columns(connection: sqlite3.Connection, table_key: str, workspace_id: str | None = None) -> tuple[sqlite3.Row | None, list[str]]:
    registry = connection.execute(
        "SELECT * FROM table_registry WHERE table_key = ? AND workspace_id = ?",
        (table_key, workspace_id or active_workspace_id(connection)),
    ).fetchone()
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
    workspace_id: str | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]], str | None]:
    registry, columns = answer_table_columns(connection, table_key, workspace_id)
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


def latest_source_run_ref(connection: sqlite3.Connection, table_key: str, workspace_id: str | None = None) -> dict[str, Any] | None:
    workspace_id = workspace_id or active_workspace_id(connection)
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


def metric_ref(connection: sqlite3.Connection, table_key: str, measure: str, aggregation: str, dimension: str | None, workspace_id: str | None = None) -> dict[str, Any] | None:
    workspace_id = workspace_id or active_workspace_id(connection)
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
        localized_value("指定一个数值字段，例如：用数值字段做柱状图", "Specify a numeric field, for example: build a bar chart with a numeric field"),
        localized_value("需要分组时，请明确写出要使用的分类、时间或状态字段", "For grouping, name the category, time, or status field explicitly"),
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
    widget_action: dict[str, Any] | None = None,
    workspace_id: str | None = None,
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
    table_key = selected_table["table_key"]
    registry, _columns = answer_table_columns(connection, table_key, workspace_id)
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

    options = widget_action.get("options") if isinstance(widget_action, dict) else None
    if isinstance(options, dict):
        measure = str(options.get("measure") or "*")
        dimension = str(options.get("dimension") or "") or None
        aggregation = str(options.get("aggregation") or ("count" if measure == "*" else "sum"))
        title = localized_value("图表草案数据预览", "Chart draft data preview")
        intent = "chart_preview"
    else:
        selected_measure, measure_confidence = select_metric_field_from_prompt(connection, table_key, prompt)
        selected_dimension, dimension_confidence = select_metric_dimension_from_prompt(connection, table_key, prompt, selected_measure)
        requested_aggregation = aggregation_from_metric_prompt(prompt, selected_measure)
        if measure_confidence in {"explicit", "recommended"}:
            measure = selected_measure
            aggregation = requested_aggregation
            dimension = selected_dimension if dimension_confidence in {"explicit", "recommended"} else None
            intent = "field_analysis"
        elif selected_dimension and dimension_confidence == "explicit":
            measure = "*"
            aggregation = "count"
            dimension = selected_dimension
            intent = "dimension_overview"
        else:
            measure = "*"
            aggregation = "count"
            dimension = None
            intent = "data_overview"
        if measure != "*" and dimension:
            title = localized_value(f"{measure} 按 {dimension} 分析", f"{measure} by {dimension}")
        elif measure != "*":
            title = localized_value(f"{measure} 概览", f"{measure} overview")
        elif dimension:
            title = localized_value(f"按 {dimension} 查看记录", f"Rows by {dimension}")
        else:
            title = localized_value("当前数据概览", "Current data overview")

    summary_metric_label = localized_value("记录数", "Rows") if measure == "*" else localized_value(measure, measure)
    runtime, rows, fallback_reason = safe_answer_aggregate(
        connection,
        table_key,
        group=dimension,
        measure=measure,
        aggregation=aggregation,
        limit=5,
        workspace_id=workspace_id,
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
    source_ref = latest_source_run_ref(connection, table_key, workspace_id)
    if source_ref:
        evidence_refs.insert(0, {"type": "sourceRun", **source_ref})
    metric = metric_ref(connection, table_key, measure, aggregation, dimension, workspace_id)
    if metric:
        evidence_refs.insert(1, {"type": "metricDefinition", **metric})

    next_actions = [
        localized_value("审阅图表草案后再确认写入", "Review the chart draft before confirming the write")
        if widget_action
        else localized_value("指定业务字段后继续下钻", "Specify business fields to continue the analysis"),
        localized_value("打开证据查看查询口径", "Open evidence to inspect the query definition"),
    ]

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
                "unit": "rows" if measure == "*" else "value",
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


def merge_receipt_unresolved_with_execution_blockers(
    unresolved: Any,
    execution_plan: Any,
) -> list[Any]:
    """Preserve runtime execution blockers in an Agent query Receipt."""
    result = list(unresolved) if isinstance(unresolved, list) else ([] if unresolved is None else [unresolved])
    plan = execution_plan if isinstance(execution_plan, dict) else {}
    blockers = plan.get("blockers") or []
    if not isinstance(blockers, list):
        blockers = [blockers]
    for blocker in blockers:
        if blocker is not None and blocker not in result:
            result.append(blocker)
    return result


def ask_command(args: argparse.Namespace) -> dict[str, Any]:
    prompt = args.prompt
    business_prompt = str(semantic_query_prompt_directives(prompt)["basePrompt"])
    read_only = getattr(args, "read_only", False)
    intents = resolve_agent_prompt_intents(business_prompt)
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
    with closing(open_db()) as connection:
        if connection.in_transaction:
            connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        workspace_id = str(getattr(args, "workspace", "") or active_workspace_id(connection))
        if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
            raise ValueError(f"Unknown workspace: {workspace_id}")
        parent_run_key = str(getattr(args, "parent_run", "") or "").strip()
        if parent_run_key:
            validate_branch_parent(connection, workspace_id, parent_run_key)
        tables = rows_to_dicts(connection.execute("SELECT table_key, display_name FROM table_registry WHERE workspace_id = ? ORDER BY table_key", (workspace_id,)))
        dashboards = rows_to_dicts(
            connection.execute(
                "SELECT dashboard_key, name, default_table_key FROM dashboards WHERE workspace_id = ? ORDER BY dashboard_key",
                (workspace_id,),
            )
        )
        selected_table, table_confidence = select_agent_table(tables, business_prompt)
        active_domain_pack_context = domain_pack_runtime_context(connection, workspace_id)
        platform_pack_enabled = is_domain_pack_enabled(
            connection,
            workspace_id,
            "platform-commerce",
            "agentKnowledge",
        )
        platform_match = match_platform_knowledge(connection, workspace_id, business_prompt) if platform_pack_enabled else None
        verified_analysis_gap = platform_match is None and requires_verified_analysis_plan(business_prompt)
        if platform_match:
            primary_table_key = str(next(iter(platform_match["roles"].values()))["table_key"])
            selected_table = next((table for table in tables if table["table_key"] == primary_table_key), selected_table)
            table_confidence = "knowledge-rule"
        context_matches = matched_context(
            connection,
            workspace_id,
            business_prompt,
            selected_table["table_key"] if selected_table else None,
        )
        resolution_prompt = " ".join(
            [
                contextualized_prompt(business_prompt, context_matches),
                platform_knowledge_context(platform_match),
            ]
        ).strip()
        selected_dashboard, dashboard_confidence = select_dashboard(
            dashboards,
            business_prompt,
            intents.wants_dashboard or intents.wants_widget,
        )
        semantic_selected_table_key = (
            str(selected_table["table_key"])
            if selected_table and table_confidence in {"explicit", "knowledge-rule"}
            else (
                str(selected_dashboard.get("default_table_key") or "")
                if selected_dashboard and dashboard_confidence == "explicit"
                else ""
            )
        )
        semantic_plan = build_workspace_semantic_plan(
            connection,
            workspace_id,
            prompt,
            selected_table_key=semantic_selected_table_key,
            table_columns=table_columns,
        )
        intent_frame = build_business_intent_frame(business_prompt, semantic_plan=semantic_plan)
        analytical_skill_runtime = analytical_skill_runtime_context(connection, workspace_id)
        business_understanding = build_business_understanding_frame(
            business_prompt,
            intent_frame,
            semantic_plan,
            context_matches,
            analytical_skill_runtime,
            knowledge_match=platform_match,
            enabled_domain_packs=[
                str(item.get("packId") or "")
                for item in active_domain_pack_context.get("enabledDomainPacks") or []
            ],
        )
        intent_frame = apply_business_understanding_to_intent(intent_frame, business_understanding)
        analytical_skill_match = (
            business_understanding.get("skillMatch")
            if isinstance(business_understanding.get("skillMatch"), dict)
            else {}
        )
        workspace_manifest_ref = workspace_planning_binding(connection, workspace_id)
        recall_result = recall_confirmed_plans(
            connection,
            workspace_id=workspace_id,
            prompt=business_prompt,
            explicit_table_key=semantic_selected_table_key or None,
            semantic_plan=semantic_plan,
            context_matches=context_matches,
            planning_binding=workspace_manifest_ref,
            now_iso=now_iso,
        )
        recalled_plans = list(recall_result.get("candidates") or [])
        recall_receipt = recall_result.get("receipt") if isinstance(recall_result.get("receipt"), dict) else None
        recalled_queries = [
            {
                "query_key": item.get("queryKey"),
                "query_receipt_key": item.get("queryReceiptKey"),
                "question": item.get("question"),
                "matchScore": item.get("matchScore"),
                "planMemoryKey": item.get("memoryKey"),
                "matchChannels": item.get("matchChannels") or {},
            }
            for item in recalled_plans
        ]
        semantic_context = build_semantic_context_bundle(
            workspace_id=workspace_id,
            intent_frame=intent_frame,
            semantic_plan=semantic_plan,
            selected_table=selected_table,
            table_selection_confidence=table_confidence,
            context_matches=context_matches,
            recalled_queries=recalled_queries,
            domain_pack_context=active_domain_pack_context,
            knowledge_match=platform_match,
            analytical_skill_match=analytical_skill_match,
            session_context=getattr(args, "session_context", None),
            business_understanding=business_understanding,
            workspace_manifest_ref=workspace_manifest_ref,
            recalled_plans=recalled_plans,
            recall_receipt=recall_receipt,
        )
        clarification = build_agent_clarification(intent_frame, semantic_context, business_understanding)
        business_understanding_blocked = (
            str(business_understanding.get("status") or "ready") == "needs-clarification"
            or bool(business_understanding.get("blockers"))
        )
        semantic_execution = None
        semantic_targets = semantic_plan.get("joinPlan", {}).get("targets") or []
        if platform_match is None and not business_understanding_blocked and semantic_plan["status"] == "ready" and semantic_targets:
            semantic_execution = execute_workspace_semantic_query(
                connection,
                workspace_id,
                prompt,
                selected_table_key=semantic_selected_table_key,
                limit=50,
                table_columns=table_columns,
                quote_identifier=quote_relationship_identifier,
                build_relationship_query=build_relationship_query,
                semantic_plan=semantic_plan,
                intent_frame=intent_frame,
            )
        semantic_execution_blocked = bool(semantic_execution and not semantic_execution.get("executed"))
        semantic_blocked = (
            semantic_plan["status"] in BLOCKING_STATUSES
            or semantic_execution_blocked
        ) and platform_match is None
        single_chart_dashboard_create = intents.wants_widget and selected_dashboard is None
        dashboard_action = None
        dashboard_action_confidence = "missing"
        if intents.wants_dashboard:
            dashboard_action, dashboard_action_confidence = resolve_prompt_dashboard_operation(connection, selected_dashboard, dashboard_confidence, resolution_prompt)
        widget_action = None
        widget_confidence = "missing"
        if intents.wants_widget and not dashboard_action:
            widget_action, widget_confidence = resolve_prompt_widget_action(connection, selected_dashboard, dashboard_confidence, selected_table, table_confidence, resolution_prompt)
        widget_clarification = isinstance(widget_action, dict) and widget_action.get("needsClarification") is True
        actionable_widget_action = None if widget_clarification else widget_action
        dashboard_filter_action = None
        dashboard_filter_confidence = "missing"
        if intents.wants_dashboard_filter and not dashboard_action and not actionable_widget_action:
            dashboard_filter_action, dashboard_filter_confidence = resolve_prompt_dashboard_filter_action(connection, selected_dashboard, dashboard_confidence, resolution_prompt)
        index_field = None
        index_field_confidence = "missing"
        index_recommendation = None
        if intents.wants_index and selected_table:
            index_field, index_field_confidence, index_recommendation = select_index_field(connection, selected_table["table_key"], resolution_prompt)
        relationship_action = None
        relationship_confidence = "missing"
        if intents.wants_relationship:
            relationship_action, relationship_confidence = select_relationship_action(connection, tables, business_prompt)
        import_file = None
        import_confidence = "missing"
        import_mode = "create"
        if intents.wants_import:
            import_file, import_confidence = resolve_prompt_import_file(business_prompt)
            import_mode = import_mode_from_prompt(business_prompt)
        formula_action = None
        formula_confidence = "missing"
        if intents.wants_formula:
            formula_action, formula_confidence = resolve_prompt_formula_action(connection, selected_table, resolution_prompt)
        view_action = None
        view_confidence = "missing"
        if intents.wants_view and not intents.wants_formula:
            view_action, view_confidence = resolve_prompt_view_action(connection, selected_table, resolution_prompt)
        metric_action = None
        metric_confidence = "missing"
        if intents.wants_metric and not intents.wants_formula and not view_action:
            metric_action, metric_confidence = resolve_prompt_metric_action(connection, selected_table, resolution_prompt)
        semantic_action = None
        semantic_confidence = "missing"
        if intents.wants_semantic and not metric_action and not view_action and not actionable_widget_action and not dashboard_filter_action:
            semantic_action, semantic_confidence = resolve_prompt_semantic_action(connection, selected_table, resolution_prompt)
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
        if verified_analysis_gap:
            should_create_draft = False
        if semantic_blocked or business_understanding_blocked:
            should_create_draft = False
        action_payload = build_agent_action_payload(
            prompt=business_prompt,
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
            dashboard_create_draft = build_agent_dashboard_create_draft(
                connection,
                workspace_id,
                action_payload.get("tableKey"),
                resolution_prompt,
                1 if single_chart_dashboard_create else 8,
                resolved_widget=actionable_widget_action if single_chart_dashboard_create else None,
            )
            action_payload.update(
                {
                    "dashboardKey": "",
                    "dashboardName": dashboard_create_draft["dashboardName"],
                    "defaultTableKey": dashboard_create_draft["defaultTableKey"],
                    "dashboardDraft": dashboard_create_draft,
                }
            )
        if should_create_draft:
            action_label = "生成单图表草案" if single_chart_dashboard_create else agent_action_label(action_kind, wants_dashboard=intents.wants_dashboard)
            action_evidence = agent_action_evidence(action_kind)
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
        answer_card = (
            build_agent_answer_card(connection, resolution_prompt, None, None, workspace_id)
            if selected_table is None
            else (
                build_business_understanding_gap(
                    business_prompt,
                    business_understanding,
                    selected_table["table_key"],
                )
                if business_understanding_blocked
                else (
                    execute_platform_knowledge(connection, platform_match)
                    if platform_match
                    else (
                        build_verified_analysis_gap(business_prompt, selected_table["table_key"])
                        if verified_analysis_gap
                        else build_agent_answer_card(connection, resolution_prompt, selected_table, actionable_widget_action, workspace_id)
                    )
                )
            )
        )
        if semantic_execution and semantic_execution.get("executed"):
            relationship_query = semantic_execution["relationshipQuery"]
            semantic_rows = relationship_rows_for_chart_service(relationship_query)
            execution_measure = semantic_execution["executionPlan"]["measure"]
            metric_name = f"{execution_measure['aggregation']}({execution_measure['field']})"
            top_row = semantic_rows[0] if semantic_rows else {}
            top_raw_value = top_row.get("value")
            top_value = None if top_raw_value is None else float(top_raw_value)
            top_label = str(top_row.get("label") or "")
            if top_value is None:
                summary = localized_value(
                    f"{top_label or '当前结果'} 的 {metric_name} 暂无可聚合数据；结果来自已验证关系与固定执行计划。",
                    f"{top_label or 'Current result'} has no data to aggregate for {metric_name}; the result comes from a validated relationship and fixed execution plan.",
                )
                display_value = "无数据 / No data"
            else:
                summary = localized_value(
                    f"{top_label or '当前结果'} 的 {metric_name} 为 {format_answer_number(top_value)}；结果来自已验证关系与固定执行计划。",
                    f"{top_label or 'Current result'} has {metric_name} {format_answer_number(top_value)} from a validated relationship and fixed execution plan.",
                )
                display_value = format_answer_number(top_value)
            answer_card = {
                "kind": "semantic-relationship-analysis",
                "title": localized_value("受控跨表分析", "Controlled cross-table analysis"),
                "summary": summary,
                "confidence": "validated-execution-plan",
                "metrics": [{
                    "label": localized_value(metric_name, metric_name),
                    "value": display_value,
                    "rawValue": top_value,
                    "unit": "value",
                }],
                "rows": semantic_rows,
                "query": semantic_execution["query"],
                "executionPlan": semantic_execution["executionPlan"],
                "evidenceRefs": [
                    {"type": "queryRuntime", **semantic_execution["query"]["runtime"]},
                    {"type": "semanticQueryPlan", "status": semantic_plan["status"]},
                    {"type": "semanticExecutionPlan", "planHash": semantic_execution["executionPlan"]["planHash"]},
                    {
                        "type": "relationshipPathProof",
                        "status": semantic_execution.get("relationshipPathProof", {}).get("status"),
                        "fingerprint": semantic_execution.get("relationshipPathProof", {}).get("fingerprint"),
                        "hopCount": len(semantic_execution.get("relationshipPathProof", {}).get("hopProofs") or []),
                    },
                    *[
                        {"type": "relationship", "relationKey": relationship["relationKey"]}
                        for relationship in semantic_execution["executionPlan"].get("relationships", [])
                    ],
                ],
                "nextActions": [localized_value("打开证据核对字段、粒度和关系版本", "Open evidence to review fields, grain, and relationship versions")],
            }
        if semantic_blocked and not business_understanding_blocked:
            semantic_unresolved = semantic_plan["fieldResolution"].get("unresolved") or []
            execution_blockers = semantic_execution.get("executionPlan", {}).get("blockers") if semantic_execution else []
            status_summary = {
                "needs-clarification": "检测到多个字段候选，请先明确数据表或业务口径。",
                "needs-relationship": "所需字段分布在多张表，但当前工作区没有可审阅的已保存关系路径。",
                "needs-validation": "已找到关系路径，但至少一跳置信度或方向未通过规划门槛。",
            }.get(
                str(semantic_plan["status"]),
                f"语义计划已形成，但受控执行仍被阻断：{', '.join(execution_blockers or ['execution-plan-blocked'])}。",
            )
            answer_card = {
                "kind": "clarification",
                "title": {"zh": "需要确认字段或跨表路径", "en": "Field or join path needs review"},
                "summary": {"zh": status_summary, "en": "The semantic query plan is blocked until its field or relationship gap is resolved."},
                "confidence": "blocked",
                "metrics": [],
                "rows": [],
                "clarification": {
                    "kind": "semantic-execution-plan" if semantic_execution_blocked else "semantic-plan",
                    "status": "blocked" if semantic_execution_blocked else semantic_plan["status"],
                    "bindings": semantic_unresolved,
                },
                "executionPlan": semantic_execution.get("executionPlan") if semantic_execution else None,
                "evidenceRefs": [{"type": "semanticQueryPlan", "status": semantic_plan["status"]}],
                "nextActions": [
                    {"zh": "选择明确的数据表与字段，或先预览并保存可靠关系。", "en": "Choose an explicit table and field, or preview and save a reliable relationship first."}
                ],
            }
        elif widget_clarification and not business_understanding_blocked and isinstance(widget_action, dict):
            answer_card = build_widget_clarification_answer_card(widget_action)
        context_refs = [
            {"type": "contextTerm", "termKey": item["term_key"], "name": item["canonical_name"]}
            for item in context_matches["terms"]
        ] + [
            {"type": "contextRule", "ruleKey": item["rule_key"], "title": item["title"]}
            for item in context_matches["rules"]
        ]
        if recall_receipt:
            context_refs.append({
                "type": "recallReceipt",
                "receiptKey": recall_receipt["receiptKey"],
                "status": recall_receipt["status"],
                "candidateOnly": True,
            })
        if platform_match:
            context_refs.append(
                {
                    "type": "knowledgeRule",
                    "packId": platform_match["packId"],
                    "ruleId": platform_match["ruleId"],
                    "title": platform_match["title"],
                }
            )
        if context_refs:
            evidence_refs = list(answer_card.get("evidenceRefs", []))
            def evidence_key(item: dict[str, Any]) -> str:
                if item.get("type") == "knowledgeRule":
                    return f"knowledgeRule:{item.get('packId')}:{item.get('ruleId')}"
                return json.dumps(item, ensure_ascii=False, sort_keys=True)

            evidence_keys = {evidence_key(item) for item in evidence_refs}
            for item in context_refs:
                key = evidence_key(item)
                if key not in evidence_keys:
                    evidence_refs.append(item)
                    evidence_keys.add(key)
            answer_card["evidenceRefs"] = evidence_refs
        answer_query = answer_card.get("query") if isinstance(answer_card.get("query"), dict) else None
        if business_understanding_blocked:
            receipt_unresolved = []
            answer_clarification = answer_card.get("clarification")
            if (
                isinstance(answer_clarification, dict)
                and answer_clarification.get("kind") == "compound-analysis-definition"
            ):
                # Preserve the established receipt-level compound-metric blocker
                # while the richer Business Understanding slots explain exactly
                # which parts of the definition are still missing.
                receipt_unresolved.append({
                    "kind": "compound-analysis-definition",
                    "mention": str(answer_clarification.get("originalQuestion") or prompt),
                    "reason": "missing-verified-business-definition",
                    "required": list(answer_clarification.get("required") or []),
                })
            receipt_unresolved.extend(list(business_understanding.get("unresolved") or []))
            if not receipt_unresolved:
                receipt_unresolved = (
                    list(business_understanding.get("blockers") or [])
                    or (
                        [clarification["items"][0]]
                        if clarification.get("items")
                        else [answer_card.get("summary")]
                    )
                )
        else:
            receipt_unresolved = (
                semantic_plan["fieldResolution"].get("unresolved")
                or [
                    {
                        "type": "semantic-plan",
                        "status": semantic_plan["status"],
                        "joinPlan": semantic_plan["joinPlan"],
                    }
                ]
                if semantic_blocked
                else ([] if answer_query else [answer_card.get("clarification") or answer_card.get("summary")])
            )
        if semantic_execution_blocked:
            receipt_unresolved = merge_receipt_unresolved_with_execution_blockers(
                receipt_unresolved,
                semantic_execution.get("executionPlan"),
            )
        query_receipt = create_query_plan_receipt(
            connection,
            workspace_id=workspace_id,
            request_text=prompt,
            source_table_key=str(answer_query.get("table")) if answer_query and answer_query.get("table") else (selected_table["table_key"] if selected_table else None),
            source_table_keys=(
                list(semantic_execution.get("executionPlan", {}).get("pathTables") or [])
                if semantic_execution
                else (list(answer_query.get("tables") or []) if answer_query else None)
            ),
            relationship_path_proof=(
                semantic_execution.get("relationshipPathProof")
                if semantic_execution
                else None
            ),
            status="executed" if not business_understanding_blocked and not semantic_blocked and answer_query and isinstance(answer_query.get("runtime"), dict) else "blocked",
            group=str(answer_query.get("group")) if answer_query and answer_query.get("group") else None,
            groups=list(answer_query.get("groupRefs") or []) if answer_query else [],
            measure=str(answer_query.get("measure")) if answer_query and answer_query.get("measure") else None,
            aggregation=str(answer_query.get("aggregation")) if answer_query and answer_query.get("aggregation") else None,
            filters=list(answer_query.get("filters") or []) if answer_query else [],
            joins=list(answer_query.get("joins") or []) if answer_query else [],
            semantic_plan=semantic_plan,
            execution_plan=semantic_execution.get("executionPlan") if semantic_execution else None,
            knowledge_rule=answer_card.get("knowledgeRule") if isinstance(answer_card.get("knowledgeRule"), dict) else None,
            runtime=answer_query.get("runtime") if answer_query else None,
            evidence_refs=list(answer_card.get("evidenceRefs", [])),
            unresolved=receipt_unresolved,
            context_refs=context_refs,
            domain_packs=active_domain_pack_context["enabledDomainPacks"],
            action_key=action_key if should_create_draft else None,
            result_rows=list(answer_card.get("rows") or []),
            now_iso=now_iso,
            workspace_manifest=workspace_manifest_ref,
        )
        answer_card["queryPlanReceipt"] = query_receipt
        analysis_run = create_analysis_run(
            connection,
            workspace_id=workspace_id,
            question=prompt,
            status="pending_confirmation" if should_create_draft else query_receipt["status"],
            query_receipt_key=query_receipt["receiptKey"],
            action_key=action_key if should_create_draft else None,
            result={
                "kind": answer_card.get("kind"),
                "title": answer_card.get("title"),
                "summary": answer_card.get("summary"),
                "selection": query_receipt.get("selection"),
                "unresolved": query_receipt.get("unresolved"),
            },
            parent_run_key=parent_run_key or None,
            branch_label=str(getattr(args, "branch_label", "") or "").strip() or None,
            now_iso=now_iso,
        )
        if should_create_draft:
            stored_action = get_action_draft(connection, action_key=action_key, workspace_id=workspace_id)
            if stored_action:
                stored_payload = action_draft_payload(stored_action)
                stored_payload["queryReceiptKey"] = query_receipt["receiptKey"]
                stored_payload["analysisRunKey"] = analysis_run["run_key"]
                connection.execute(
                    "UPDATE action_drafts SET payload_json = ? WHERE workspace_id = ? AND action_key = ?",
                    (json.dumps(stored_payload, ensure_ascii=False), workspace_id, action_key),
                )
        connection.commit()
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
        "workspaceId": workspace_id,
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
        "queryPlanReceipt": query_receipt,
        "semanticPlan": semantic_plan,
        "executionPlan": semantic_execution.get("executionPlan") if semantic_execution else None,
        "analysisRun": analysis_run,
        "intentFrame": intent_frame,
        "semanticContext": semantic_context,
        "businessUnderstanding": business_understanding,
        "analyticalSkillMatch": analytical_skill_match,
        "analyticalSkills": analytical_skill_runtime,
        "clarification": clarification,
        "context": {
            "matchedTermCount": len(context_matches["terms"]),
            "matchedRuleCount": len(context_matches["rules"]),
            "terms": [
                {"termKey": item["term_key"], "name": item["canonical_name"], "definition": item["definition"]}
                for item in context_matches["terms"]
            ],
            "rules": [
                {"ruleKey": item["rule_key"], "title": item["title"], "statement": item["statement"]}
                for item in context_matches["rules"]
            ],
            "confirmedQueries": [
                {"queryKey": item["query_key"], "question": item["question"], "matchScore": item["matchScore"]}
                for item in recalled_queries
            ],
            "confirmedPlans": [
                {
                    "memoryKey": item.get("memoryKey"),
                    "queryKey": item.get("queryKey"),
                    "question": item.get("question"),
                    "matchScore": item.get("matchScore"),
                    "matchChannels": item.get("matchChannels") or {},
                    "canAuthorizeSelection": False,
                }
                for item in recalled_plans
            ],
            "recallReceipt": recall_receipt,
            "knowledgeRules": [
                {
                    "packId": platform_match["packId"],
                    "ruleId": platform_match["ruleId"],
                    "title": platform_match["title"],
                    "grain": platform_match["grain"],
                }
            ] if platform_match else [],
        },
        "agentKnowledge": {
            "packId": platform_match["packId"] if platform_match else None,
            "version": platform_match["packVersion"] if platform_match else None,
            "matchedRuleId": platform_match["ruleId"] if platform_match else None,
            "modelIndependent": True,
        },
        "domainPacks": active_domain_pack_context,
        "recommendedCommands": recommended,
        "requiresConfirmation": should_create_draft,
        "actionDraft": {
            "actionKey": action_key,
            "kind": action_kind,
            "status": "draft" if should_create_draft else "read-only",
        },
        "ontology": ontology,
        "coreSemanticRuntime": core_semantic_runtime(),
        "sourcePipelineContract": source_pipeline_contract(),
    }


def confirm_action_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = str(getattr(args, "workspace", "") or active_workspace_id(connection))
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
            result = handle_dashboard_widget_add_confirmation(
                connection,
                action,
                payload,
                action_key=args.action_key,
                yes=args.yes,
                confirmed_at=now_iso(),
                build_widget_proposal=build_widget_proposal,
                insert_dashboard_widget=insert_dashboard_widget,
            )
            if args.yes and result.get("confirmed") is True and isinstance(result.get("addedWidget"), dict):
                candidate = create_confirmed_query_candidate(
                    connection,
                    workspace_id=workspace_id,
                    action_key=args.action_key,
                    action_payload=payload,
                    added_widget=result["addedWidget"],
                    now_iso=now_iso,
                )
                if candidate:
                    connection.commit()
                    result["confirmedQueryCandidate"] = candidate
            return result
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
            result = handle_dashboard_create_confirmation(
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
            dashboard_draft = payload.get("dashboardDraft") if isinstance(payload.get("dashboardDraft"), dict) else {}
            draft_widgets = dashboard_draft.get("widgets") if isinstance(dashboard_draft.get("widgets"), list) else []
            if (
                args.yes
                and result.get("confirmed") is True
                and dashboard_draft.get("source") == "single-chart"
                and len(draft_widgets) == 1
                and isinstance(draft_widgets[0], dict)
            ):
                candidate = create_confirmed_query_candidate(
                    connection,
                    workspace_id=workspace_id,
                    action_key=args.action_key,
                    action_payload=payload,
                    added_widget=draft_widgets[0],
                    now_iso=now_iso,
                )
                if candidate:
                    connection.commit()
                    result["confirmedQueryCandidate"] = candidate
            return result
        if not args.yes:
            return confirm_dry_run_response(action, payload)
        mark_action_confirmed(connection, args.action_key, now_iso())
        connection.commit()
    return confirmed_response(args.action_key)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        if args.command == "cli-contract":
            result = cli_contract_command(args, parser)
        elif args.command == "list-commands":
            result = list_commands_command(args, parser)
        elif args.command == "capability-contracts":
            result = capability_contracts_command(args, parser)
        elif args.command == "workflow-plan":
            result = workflow_plan_command(args, parser)
        elif args.command == "context-budget":
            result = context_budget_command(args)
        elif args.command == "restricted-workflow-operators":
            result = restricted_workflow_operators_command(args)
        elif args.command == "restricted-workflow-validate":
            result = restricted_workflow_validate_command(args)
        elif args.command == "agent-workflow-graph":
            result = agent_workflow_graph_command(args, open_db=open_db, active_workspace_id=active_workspace_id)
        elif args.command == "agent-turn-run":
            result = run_agent_turn_command(
                args,
                ask_runner=ask_command,
                answer_enricher=lambda answer: attach_analysis_unit(
                    answer,
                    open_db=open_db,
                    active_workspace_id=active_workspace_id,
                    now_iso=now_iso,
                ),
                open_db=open_db,
                active_workspace_id=active_workspace_id,
                now_iso=now_iso,
            )
        elif args.command == "agent-turns":
            result = agent_turns_command(args, open_db=open_db, active_workspace_id=active_workspace_id)
        elif args.command == "agent-turn-cancel":
            result = cancel_agent_turn_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "agent-session-create":
            result = agent_session_create_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "agent-sessions":
            result = agent_sessions_command(args, open_db=open_db, active_workspace_id=active_workspace_id)
        elif args.command == "agent-session-resume":
            result = agent_session_resume_command(args, open_db=open_db, active_workspace_id=active_workspace_id)
        elif args.command == "agent-session-fork":
            result = agent_session_fork_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "agent-context-compact":
            result = agent_context_compact_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "agent-runtime-profiles":
            result = agent_runtime_profiles_command(args, open_db=open_db, active_workspace_id=active_workspace_id)
        elif args.command == "agent-runtime-profile-set":
            result = agent_runtime_profile_set_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "agent-provider-evaluations":
            result = agent_provider_evaluations_command(args, open_db=open_db, active_workspace_id=active_workspace_id)
        elif args.command == "agent-provider-evaluation-record":
            result = agent_provider_evaluation_record_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "business-expression-cases":
            result = business_expression_cases_command(args)
        elif args.command == "plan-quality-evaluate":
            result = plan_quality_evaluate_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "plan-quality-scorecards":
            result = plan_quality_scorecards_command(args, open_db=open_db, active_workspace_id=active_workspace_id)
        elif args.command == "status":
            result = status_command(args)
        elif args.command == "workspace-manifest":
            result = workspace_manifest_command(
                args,
                command_capabilities=capability_registry(parser),
                open_db=open_db,
                active_workspace_id=active_workspace_id,
            )
        elif args.command == "runtime-catalog":
            result = runtime_catalog_command(
                args,
                command_capabilities=capability_registry(parser),
                open_db=open_db,
                active_workspace_id=active_workspace_id,
            )
        elif args.command == "business-field-profiles":
            result = business_field_profiles_command(
                args,
                open_db=open_db,
                active_workspace_id=active_workspace_id,
            )
        elif args.command == "quality-doctor":
            result = quality_doctor_command(args)
        elif args.command == "context-pack":
            result = context_pack_command(args, open_db=open_db, active_workspace_id=active_workspace_id)
        elif args.command == "context-term":
            result = context_term_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "context-rule":
            result = context_rule_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "knowledge-source-adapters":
            result = knowledge_source_adapters_command(args)
        elif args.command == "knowledge-sources":
            result = knowledge_sources_command(args, open_db=open_db, active_workspace_id=active_workspace_id)
        elif args.command == "semantic-patch-propose":
            result = semantic_patch_propose_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "semantic-patch-proposals":
            result = semantic_patch_proposals_command(args, open_db=open_db, active_workspace_id=active_workspace_id)
        elif args.command == "semantic-patch-review":
            result = semantic_patch_review_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "query-receipts":
            result = query_receipts_command(args, open_db=open_db, active_workspace_id=active_workspace_id)
        elif args.command == "export-evidence":
            result = export_evidence_command(args, open_db=open_db, active_workspace_id=active_workspace_id, root=ROOT, now_iso=now_iso)
        elif args.command == "export-analysis":
            result = export_analysis_command(args, open_db=open_db, active_workspace_id=active_workspace_id, root=ROOT)
        elif args.command == "confirmed-queries":
            result = confirmed_queries_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "confirmed-plans":
            result = confirmed_plans_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "recall-receipts":
            result = recall_receipts_command(args, open_db=open_db, active_workspace_id=active_workspace_id)
        elif args.command == "confirm-query":
            result = confirm_query_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "analysis-runs":
            result = analysis_runs_command(args, open_db=open_db, active_workspace_id=active_workspace_id)
        elif args.command == "exploration-threads":
            result = exploration_threads_command(args, open_db=open_db, active_workspace_id=active_workspace_id)
        elif args.command == "exploration-thread-create":
            result = exploration_thread_create_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "exploration-anchor-add":
            result = exploration_anchor_add_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "exploration-board-set":
            result = exploration_board_set_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "research-runs":
            result = research_runs_command(args, open_db=open_db, active_workspace_id=active_workspace_id)
        elif args.command == "research-run-create":
            result = research_run_create_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "research-run-revise":
            result = research_run_revise_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "research-run-observe":
            result = research_run_observe_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "research-run-finalize":
            result = research_run_finalize_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "analysis-unit-build":
            result = analysis_unit_build_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "analysis-units":
            result = analysis_units_command(args, open_db=open_db, active_workspace_id=active_workspace_id)
        elif args.command == "analysis-snapshots":
            result = analysis_snapshots_command(args, open_db=open_db, active_workspace_id=active_workspace_id)
        elif args.command == "analysis-snapshot-create":
            result = analysis_snapshot_create_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "analysis-snapshot-refresh":
            result = analysis_snapshot_refresh_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "analysis-snapshot-replace":
            result = analysis_snapshot_replace_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "analysis-snapshot-delete":
            result = analysis_snapshot_delete_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "metric-monitors":
            result = metric_monitors_command(args, open_db=open_db, active_workspace_id=active_workspace_id)
        elif args.command == "metric-monitor-create":
            result = metric_monitor_create_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "metric-monitor-replace":
            result = metric_monitor_replace_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "metric-monitor-delete":
            result = metric_monitor_delete_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "metric-monitor-run":
            result = metric_monitor_run_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "analysis-unit-verify":
            result = analysis_unit_verify_command(args, open_db=open_db, active_workspace_id=active_workspace_id)
        elif args.command == "forecast-readiness":
            result = forecast_readiness_command(args, open_db=open_db, active_workspace_id=active_workspace_id)
        elif args.command == "chart-adapt":
            result = chart_adapt_command(args, open_db=open_db, active_workspace_id=active_workspace_id)
        elif args.command == "jobs":
            result = jobs_command(args, open_db=open_db, active_workspace_id=active_workspace_id)
        elif args.command == "job-cancel":
            result = job_cancel_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "job-recover":
            result = job_recover_command(args, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        elif args.command == "source-intelligence-job-create":
            result = source_intelligence_job_create_command(
                args,
                open_db=open_db,
                active_workspace_id=active_workspace_id,
                now_iso=now_iso,
            )
        elif args.command == "source-intelligence-job-run":
            result = source_intelligence_job_run_command(
                args,
                source_intelligence_command=source_intelligence_command,
                open_db=open_db,
                active_workspace_id=active_workspace_id,
                now_iso=now_iso,
            )
        elif args.command == "job-process-exit":
            result = job_process_exit_command(
                args,
                open_db=open_db,
                active_workspace_id=active_workspace_id,
                now_iso=now_iso,
            )
        elif args.command == "workspace-create":
            result = workspace_create_command(args)
        elif args.command == "workspace-select":
            result = workspace_select_command(args)
        elif args.command == "workspace-rename":
            result = workspace_rename_command(args)
        elif args.command == "workspace-delete":
            result = workspace_delete_command(args)
        elif args.command == "domain-packs":
            result = domain_packs_command(args)
        elif args.command == "domain-pack-set":
            result = domain_pack_set_command(args)
        elif args.command == "domain-pack-lint":
            result = domain_pack_lint_command(args)
        elif args.command == "domain-pack-install":
            result = domain_pack_install_command(args)
        elif args.command == "domain-pack-uninstall":
            result = domain_pack_uninstall_command(args)
        elif args.command == "analytical-skills":
            result = analytical_skills_command(args)
        elif args.command == "analytical-skill-lint":
            result = analytical_skill_lint_command(args)
        elif args.command == "analytical-skill-install":
            result = analytical_skill_install_command(args)
        elif args.command == "analytical-skill-uninstall":
            result = analytical_skill_uninstall_command(args)
        elif args.command == "analytical-skill-set":
            result = analytical_skill_set_command(args)
        elif args.command == "analytical-skill-match":
            result = analytical_skill_match_command(args)
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
        elif args.command == "cli-capabilities":
            result = cli_capabilities_command(args)
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
        elif args.command == "list-connector-adapters":
            result = list_connector_adapters_command(args)
        elif args.command == "discover-connector":
            result = discover_connector_command(args)
        elif args.command == "preview-connector":
            result = preview_connector_command(args)
        elif args.command == "plan-connector-sync":
            result = plan_connector_sync_command(args)
        elif args.command == "federation-proof":
            result = federation_proof_command(args)
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
        elif args.command == "semantic-query":
            args.prompt = " ".join(args.prompt)
            with closing(open_db()) as connection:
                if connection.in_transaction:
                    connection.commit()
                connection.execute("BEGIN IMMEDIATE")
                workspace_id = active_workspace_id(connection)
                result = execute_workspace_semantic_query(
                    connection,
                    workspace_id,
                    str(args.prompt),
                    selected_table_key=str(getattr(args, "table", "") or ""),
                    limit=int(getattr(args, "limit", 50) or 50),
                    table_columns=table_columns,
                    quote_identifier=quote_relationship_identifier,
                    build_relationship_query=build_relationship_query,
                )
                result["workspaceId"] = workspace_id
                execution_plan = result.get("executionPlan") if isinstance(result.get("executionPlan"), dict) else {}
                query = result.get("query") if isinstance(result.get("query"), dict) else {}
                relationship_query = result.get("relationshipQuery") if isinstance(result.get("relationshipQuery"), dict) else {}
                result_rows = relationship_rows_for_chart_service(relationship_query) if result.get("executed") else []
                receipt = create_query_plan_receipt(
                    connection,
                    workspace_id=workspace_id,
                    request_text=str(args.prompt),
                    source_table_key=str(execution_plan.get("rootTable") or getattr(args, "table", "") or "") or None,
                    source_table_keys=list(execution_plan.get("pathTables") or query.get("tables") or []),
                    relationship_path_proof=result.get("relationshipPathProof"),
                    status="executed" if result.get("executed") else "blocked",
                    group=str(query.get("group") or "") or None,
                    groups=list(query.get("groupRefs") or []),
                    measure=str(query.get("measure") or "") or None,
                    aggregation=str(query.get("aggregation") or "") or None,
                    filters=list(query.get("filters") or []),
                    joins=list(query.get("joins") or []),
                    semantic_plan=result.get("semanticPlan"),
                    execution_plan=execution_plan,
                    runtime=query.get("runtime") if isinstance(query.get("runtime"), dict) else None,
                    evidence_refs=[{
                        "type": "relationshipPathProof",
                        "fingerprint": result.get("relationshipPathProof", {}).get("fingerprint"),
                    }] if isinstance(result.get("relationshipPathProof"), dict) else [],
                    unresolved=list(execution_plan.get("blockers") or []),
                    result_rows=result_rows,
                    now_iso=now_iso,
                )
                connection.commit()
            result["queryPlanReceipt"] = receipt
            result["rows"] = result_rows
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
            result = attach_analysis_unit(
                ask_command(args),
                open_db=open_db,
                active_workspace_id=active_workspace_id,
                now_iso=now_iso,
            )
        elif args.command == "confirm-action":
            result = confirm_action_command(args)
            if not result.get("workspaceId"):
                with open_db() as connection:
                    result["workspaceId"] = str(getattr(args, "workspace", "") or active_workspace_id(connection))
        elif args.command == "action-drafts":
            result = action_drafts_command(args)
        else:
            raise ValueError(f"Unknown command: {args.command}")
        if args.command in {"query", "ask", "semantic-query"}:
            result = attach_analysis_unit(result, open_db=open_db, active_workspace_id=active_workspace_id, now_iso=now_iso)
        result = enrich_cli_output(result, args, parser)
        dump(result)
        return 0 if result.get("ok", False) else 1
    except Exception as exc:
        dump(error_output(str(getattr(args, "command", "")), exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
