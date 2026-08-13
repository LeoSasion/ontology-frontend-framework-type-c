"""Data-management application use cases."""

from bi_cli_dashboard_commands import list_navigation_command, navigation_operation_command, workbench_command
from bi_cli_io_services import apply_config_command, export_config_command, validate_config_command
from bi_cli_misc_commands import cli_capabilities_command
from bi_cli_relationship_formula_commands import query_metric_command
from bi_cli_schema import open_db
from bi_cli_semantic_metric_commands import (
    add_metric_command,
    infer_metrics_command,
    infer_semantics_command,
    list_metrics_command,
    list_semantics_command,
    set_semantic_command,
)
from bi_cli_source_commands import (
    delete_source_command,
    discover_connector_command,
    federation_proof_command,
    import_commit_command,
    import_folder_command,
    inspect_table_command,
    list_connector_adapters_command,
    list_connectors_command,
    list_import_jobs_command,
    list_tables_command,
    plan_connector_sync_command,
    preferences_command,
    preview_connector_command,
    preview_import_command,
    preview_import_folder_command,
    remove_connector_command,
    remove_import_job_command,
    rename_source_command,
    save_connector_command,
    set_import_policy_command,
    source_intelligence_command,
    source_intelligence_runs_command,
    source_run_command,
    sync_connector_command,
    theme_palettes_command,
)
from bi_cli_system_commands import (
    analytical_skill_install_command,
    analytical_skill_lint_command,
    analytical_skill_match_command,
    analytical_skill_set_command,
    analytical_skill_uninstall_command,
    analytical_skills_command,
    domain_pack_install_command,
    domain_pack_lint_command,
    domain_pack_set_command,
    domain_pack_uninstall_command,
    domain_packs_command,
    workspace_create_command,
    workspace_delete_command,
    workspace_rename_command,
    workspace_select_command,
)
from bi_cli_widget_commands import (
    add_recommended_widgets_command,
    add_relationship_widget_command,
    add_widget_command,
    business_dashboard_command,
    copy_widget_command,
    dashboard_widget_catalog_command,
    erp_unit_library_command,
    recommend_widgets_command,
    remove_widget_command,
    save_dashboard_modules_command,
    set_widget_command,
)
from import_job_commands import (
    import_job_create_command,
    import_job_process_exit_command,
    import_job_recover_command,
    import_job_resume_command,
    import_job_run_command,
)
from sqlserver_snapshot_commands import (
    sqlserver_activate_command,
    sqlserver_activation_finalize_command,
    sqlserver_activation_status_command,
    sqlserver_capability_command,
    sqlserver_catalog_command,
    sqlserver_execute_command,
    sqlserver_plan_command,
    sqlserver_statistics_command,
    sqlserver_test_command,
)

from .agent_interaction import source_intelligence_dashboard_draft_command
