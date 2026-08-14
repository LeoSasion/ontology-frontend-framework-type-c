from __future__ import annotations

from .use_cases import data as runtime


COMMANDS = frozenset({
    'add-metric',
    'add-recommended-widgets',
    'add-relationship-widget',
    'add-widget',
    'analytical-skill-install',
    'analytical-skill-lint',
    'analytical-skill-match',
    'analytical-skill-set',
    'analytical-skill-uninstall',
    'analytical-skills',
    'apply-config',
    'business-dashboard',
    'cli-capabilities',
    'copy-widget',
    'dashboard-widget-catalog',
    'delete-source',
    'discover-connector',
    'domain-pack-install',
    'domain-pack-lint',
    'domain-pack-set',
    'domain-pack-uninstall',
    'domain-packs',
    'erp-unit-library',
    'export-config',
    'federation-proof',
    'import-commit',
    'import-folder',
    'import-job-create',
    'import-job-process-exit',
    'import-job-recover',
    'import-job-resume',
    'import-job-run',
    'infer-metrics',
    'infer-semantics',
    'inspect-table',
    'list-connector-adapters',
    'list-connectors',
    'list-import-jobs',
    'list-metrics',
    'metric-contract-preview',
    'metric-contract-publish',
    'metric-contract-replay',
    'metric-contracts',
    'list-navigation',
    'list-semantics',
    'list-tables',
    'navigation-op',
    'plan-connector-sync',
    'preferences',
    'preview-connector',
    'preview-import',
    'preview-import-folder',
    'query-metric',
    'recommend-widgets',
    'remove-connector',
    'remove-import-job',
    'remove-widget',
    'rename-source',
    'save-connector',
    'save-dashboard-modules',
    'set-import-policy',
    'set-semantic',
    'set-widget',
    'sqlserver-adapter-discover',
    'sqlserver-adapter-activate',
    'sqlserver-adapter-activation-finalize',
    'sqlserver-adapter-activation-status',
    'sqlserver-adapter-plan',
    'sqlserver-adapter-preview',
    'sqlserver-adapter-probe',
    'sqlserver-adapter-snapshot',
    'sqlserver-adapter-test',
    'source-dashboard-draft',
    'source-intelligence',
    'source-intelligence-runs',
    'source-run',
    'sync-connector',
    'theme-palettes',
    'validate-config',
    'workbench',
    'workspace-create',
    'workspace-delete',
    'workspace-rename',
    'workspace-select',
})


def dispatch(args, parser):
    if args.command == 'workspace-create':
        result = runtime.workspace_create_command(args)
    elif args.command == 'workspace-select':
        result = runtime.workspace_select_command(args)
    elif args.command == 'workspace-rename':
        result = runtime.workspace_rename_command(args)
    elif args.command == 'workspace-delete':
        result = runtime.workspace_delete_command(args)
    elif args.command == 'domain-packs':
        result = runtime.domain_packs_command(args)
    elif args.command == 'domain-pack-set':
        result = runtime.domain_pack_set_command(args)
    elif args.command == 'domain-pack-lint':
        result = runtime.domain_pack_lint_command(args)
    elif args.command == 'domain-pack-install':
        result = runtime.domain_pack_install_command(args)
    elif args.command == 'domain-pack-uninstall':
        result = runtime.domain_pack_uninstall_command(args)
    elif args.command == 'analytical-skills':
        result = runtime.analytical_skills_command(args)
    elif args.command == 'analytical-skill-lint':
        result = runtime.analytical_skill_lint_command(args)
    elif args.command == 'analytical-skill-install':
        result = runtime.analytical_skill_install_command(args)
    elif args.command == 'analytical-skill-uninstall':
        result = runtime.analytical_skill_uninstall_command(args)
    elif args.command == 'analytical-skill-set':
        result = runtime.analytical_skill_set_command(args)
    elif args.command == 'analytical-skill-match':
        result = runtime.analytical_skill_match_command(args)
    elif args.command == 'source-run':
        result = runtime.source_run_command(args)
    elif args.command == 'list-tables':
        result = runtime.list_tables_command(args)
    elif args.command == 'inspect-table':
        result = runtime.inspect_table_command(args)
    elif args.command == 'rename-source':
        result = runtime.rename_source_command(args)
    elif args.command == 'delete-source':
        result = runtime.delete_source_command(args)
    elif args.command == 'source-intelligence':
        result = runtime.source_intelligence_command(args)
    elif args.command == 'source-intelligence-runs':
        result = runtime.source_intelligence_runs_command(args)
    elif args.command == 'source-dashboard-draft':
        result = runtime.source_intelligence_dashboard_draft_command(args)
    elif args.command == 'workbench':
        result = runtime.workbench_command(args)
    elif args.command == 'list-navigation':
        result = runtime.list_navigation_command(args)
    elif args.command == 'navigation-op':
        result = runtime.navigation_operation_command(args)
    elif args.command == 'dashboard-widget-catalog':
        result = runtime.dashboard_widget_catalog_command(args)
    elif args.command == 'cli-capabilities':
        result = runtime.cli_capabilities_command(args)
    elif args.command == 'recommend-widgets':
        result = runtime.recommend_widgets_command(args)
    elif args.command == 'add-recommended-widgets':
        result = runtime.add_recommended_widgets_command(args)
    elif args.command == 'save-dashboard-modules':
        result = runtime.save_dashboard_modules_command(args)
    elif args.command == 'business-dashboard':
        result = runtime.business_dashboard_command(args)
    elif args.command == 'erp-unit-library':
        result = runtime.erp_unit_library_command(args)
    elif args.command == 'add-widget':
        result = runtime.add_widget_command(args)
    elif args.command == 'add-relationship-widget':
        result = runtime.add_relationship_widget_command(args)
    elif args.command == 'set-widget':
        result = runtime.set_widget_command(args)
    elif args.command == 'copy-widget':
        result = runtime.copy_widget_command(args)
    elif args.command == 'remove-widget':
        result = runtime.remove_widget_command(args)
    elif args.command == 'set-import-policy':
        result = runtime.set_import_policy_command(args)
    elif args.command == 'preview-import':
        result = runtime.preview_import_command(args)
    elif args.command == 'import-commit':
        result = runtime.import_commit_command(args)
    elif args.command == 'preview-import-folder':
        result = runtime.preview_import_folder_command(args)
    elif args.command == 'import-folder':
        result = runtime.import_folder_command(args)
    elif args.command == 'import-job-create':
        result = runtime.import_job_create_command(args)
    elif args.command == 'import-job-run':
        result = runtime.import_job_run_command(args)
    elif args.command == 'import-job-resume':
        result = runtime.import_job_resume_command(args)
    elif args.command == 'import-job-recover':
        result = runtime.import_job_recover_command(args)
    elif args.command == 'import-job-process-exit':
        result = runtime.import_job_process_exit_command(args)
    elif args.command == 'list-import-jobs':
        result = runtime.list_import_jobs_command(args)
    elif args.command == 'remove-import-job':
        result = runtime.remove_import_job_command(args)
    elif args.command == 'list-connectors':
        result = runtime.list_connectors_command(args)
    elif args.command == 'save-connector':
        result = runtime.save_connector_command(args)
    elif args.command == 'sync-connector':
        result = runtime.sync_connector_command(args)
    elif args.command == 'remove-connector':
        result = runtime.remove_connector_command(args)
    elif args.command == 'list-connector-adapters':
        result = runtime.list_connector_adapters_command(args)
    elif args.command == 'discover-connector':
        result = runtime.discover_connector_command(args)
    elif args.command == 'preview-connector':
        result = runtime.preview_connector_command(args)
    elif args.command == 'plan-connector-sync':
        result = runtime.plan_connector_sync_command(args)
    elif args.command == 'federation-proof':
        result = runtime.federation_proof_command(args)
    elif args.command == 'sqlserver-adapter-probe':
        result = runtime.sqlserver_capability_command(args, open_db=runtime.open_db)
    elif args.command == 'sqlserver-adapter-test':
        result = runtime.sqlserver_test_command(args, open_db=runtime.open_db)
    elif args.command == 'sqlserver-adapter-discover':
        result = runtime.sqlserver_catalog_command(args, open_db=runtime.open_db)
    elif args.command == 'sqlserver-adapter-preview':
        result = runtime.sqlserver_statistics_command(args, open_db=runtime.open_db)
    elif args.command == 'sqlserver-adapter-plan':
        result = runtime.sqlserver_plan_command(args, open_db=runtime.open_db)
    elif args.command == 'sqlserver-adapter-snapshot':
        result = runtime.sqlserver_execute_command(args, open_db=runtime.open_db)
    elif args.command == 'sqlserver-adapter-activate':
        result = runtime.sqlserver_activate_command(args, open_db=runtime.open_db)
    elif args.command == 'sqlserver-adapter-activation-status':
        result = runtime.sqlserver_activation_status_command(args, open_db=runtime.open_db)
    elif args.command == 'sqlserver-adapter-activation-finalize':
        result = runtime.sqlserver_activation_finalize_command(args, open_db=runtime.open_db)
    elif args.command == 'infer-semantics':
        result = runtime.infer_semantics_command(args)
    elif args.command == 'list-semantics':
        result = runtime.list_semantics_command(args)
    elif args.command == 'set-semantic':
        result = runtime.set_semantic_command(args)
    elif args.command == 'infer-metrics':
        result = runtime.infer_metrics_command(args)
    elif args.command == 'list-metrics':
        result = runtime.list_metrics_command(args)
    elif args.command == 'add-metric':
        result = runtime.add_metric_command(args)
    elif args.command == 'query-metric':
        result = runtime.query_metric_command(args)
    elif args.command == 'metric-contract-preview':
        result = runtime.metric_contract_preview_command(args)
    elif args.command == 'metric-contract-publish':
        result = runtime.metric_contract_publish_command(args)
    elif args.command == 'metric-contracts':
        result = runtime.metric_contracts_command(args)
    elif args.command == 'metric-contract-replay':
        result = runtime.metric_contract_replay_command(args)
    elif args.command == 'preferences':
        result = runtime.preferences_command(args)
    elif args.command == 'theme-palettes':
        result = runtime.theme_palettes_command(args)
    elif args.command == 'validate-config':
        result = runtime.validate_config_command(args)
    elif args.command == 'export-config':
        result = runtime.export_config_command(args)
    elif args.command == 'apply-config':
        result = runtime.apply_config_command(args)
    else:
        raise ValueError(f'Command is not registered in data: {args.command}')
    return result
