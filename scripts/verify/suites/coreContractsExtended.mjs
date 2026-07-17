export function appendCoreContractExtendedChecks(context) {
  const {
    checks,
    agentActionConfirmationsSource,
    agentActionDraftStoreSource,
    agentConfirmExecutionHandlersSource,
    agentPromptResolutionSource,
    agentRecommendedCommandsSource,
    apiSourceApiSource,
    appDataActionsSource,
    appSource: appEntrySource,
    appMainViewSource,
    biCliContractDocSource,
    biCliContractsSource,
    biCliCapabilitiesSource,
    biCliCoreSource,
    biCliEnvelopeSource,
    biCliEvidenceBundlesSource,
    biCliParserSource,
    biCliDashboardCommandsSource,
    biCliIoServicesSource,
    biCliQueryViewCommandsSource,
    biCliRelationshipFormulaCommandsSource,
    biCliSchemaSource,
    biCliSemanticMetricCommandsSource,
    biCliMiscCommandsSource,
    biCliSource,
    biCliSourceCommandsSource,
    biCliSystemCommandsSource,
    biCliWidgetCommandsSource,
    businessDashboardServiceSource,
    businessDashboardTemplatesSource,
    bundleBudgetConfigSource,
    byLabel,
    configCommandServiceSource,
    connectorCommandServiceSource,
    dashboardModuleOrchestrationSource,
    dashboardSaveTransactionsSource,
    dashboardWidgetCommandServiceSource,
    dashboardWidgetContractsSource,
    dashboardWidgetOperationsSource,
    dashboardWidgetProposalServiceSource,
    erpDashboardUnitLibrarySource,
    existsSync,
    homeOverviewSource,
    implementationStatusSource,
    importCommandServiceSource,
    importJobCommandServiceSource,
    importTableWriterServiceSource,
    indexHtmlSource,
    join,
    metricFormulaCommandServiceSource,
    packageJson,
    preferencesThemeCommandServiceSource,
    productAcceptanceMatrixDocSource,
    readOnlyAgentCheck,
    relationshipCommandServiceSource,
    retiredSeedEnvName,
    root,
    run,
    savedViewQueryServiceSource,
    semanticTextSource,
    serverSourceRoutesSource,
    sourceIntelligenceDashboardDraftsSource,
    sourceIntelligenceReceiptsSource,
    sourceIntelligenceRunStoreSource,
    sourceManagementCommandServiceSource,
    sourceReadModelServiceSource,
    themeSource,
    verifyBiCliAgentContractSource,
    verifyBundleBudgetsSource,
    verifyAgentWorkflowContractsSource,
    verifyAppArchitectureContractsSource,
    verifyCoreContractsSource,
    verifyDashboardViewContractsSource,
    verifyProductUxContractsSource,
    verifyRuntimeSource,
    verifySource,
    verifySourceCatalogSource,
    verifySourceContractsSource,
    verifyUiRealImportSource,
    workspaceCommandServiceSource,
  } = context;
  const appSource = `${appEntrySource}\n${appMainViewSource}`;
  const biCliRuntimeSource = [
    biCliSource,
    biCliParserSource,
    biCliSchemaSource,
    biCliIoServicesSource,
    biCliSystemCommandsSource,
    biCliSourceCommandsSource,
    biCliQueryViewCommandsSource,
    biCliDashboardCommandsSource,
    biCliWidgetCommandsSource,
    biCliSemanticMetricCommandsSource,
    biCliRelationshipFormulaCommandsSource,
    biCliCapabilitiesSource,
    biCliMiscCommandsSource,
  ].join("\n");
  checks.push(

    {
        label: "dashboard-module-orchestration-boundary",
        ok: existsSync(join(root, "tools", "dashboard_module_orchestration.py")) &&
          biCliRuntimeSource.includes("from dashboard_module_orchestration import dashboard_module_widget_from_payload") &&
          !biCliRuntimeSource.includes("def dashboard_module_widget_from_payload(") &&
          !biCliRuntimeSource.includes("def namespaced_dashboard_widget_id(") &&
          dashboardModuleOrchestrationSource.includes("def dashboard_module_widget_from_payload(") &&
          dashboardModuleOrchestrationSource.includes("def namespaced_dashboard_widget_id(") &&
          dashboardModuleOrchestrationSource.includes("preferred_table_key: Callable") &&
          dashboardModuleOrchestrationSource.includes("table_display_name: Callable") &&
          dashboardModuleOrchestrationSource.includes("workspace_id: str") &&
          byLabel["cli-save-dashboard-modules-dry-run"].parsed?.proposedWidgets?.every((widget) =>
            widget.workspace_id && widget.config?.layout,
          ),
      },
    {
        label: "dashboard-save-transaction-boundary",
        ok: existsSync(join(root, "tools", "dashboard_save_transactions.py")) &&
          biCliRuntimeSource.includes("from dashboard_save_transactions import dashboard_snapshot, save_dashboard_with_widgets") &&
          dashboardSaveTransactionsSource.includes("def upsert_dashboard_record(") &&
          dashboardSaveTransactionsSource.includes("def replace_dashboard_widgets(") &&
          dashboardSaveTransactionsSource.includes("def save_dashboard_with_widgets(") &&
          dashboardSaveTransactionsSource.includes("def dashboard_snapshot(") &&
          dashboardSaveTransactionsSource.includes("insert_dashboard_widget(connection, widget)") &&
          byLabel["cli-save-dashboard-modules-confirm"].parsed?.dashboard?.widgets?.every((widget) => widget.config),
      },
    {
        label: "bi-cli-core-boundary",
        ok: existsSync(join(root, "tools", "bi_cli_core.py")) &&
          biCliRuntimeSource.includes("from bi_cli_core import (") &&
          !biCliRuntimeSource.includes("def quote_identifier(name: str)") &&
          !biCliRuntimeSource.includes("def source_label(path: Path | str)") &&
          biCliCoreSource.includes("def quote_identifier(name: str)") &&
          biCliCoreSource.includes("def source_label(path: Path | str)") &&
          biCliCoreSource.includes('ROOT = Path(__file__).resolve().parents[1]') &&
          !biCliCoreSource.includes("A_PROJECT_ROOT") &&
          !biCliCoreSource.includes("B_PROJECT_ROOT"),
      },
    {
        label: "verify-compact-output-default",
        ok: verifySource.includes('from "./verify/runtime.mjs"') &&
          verifySource.includes("finishVerify({") &&
          verifyRuntimeSource.includes("function compactReceipt(receipt)") &&
          verifyRuntimeSource.includes("const fullOutput = process.argv.includes(\"--full\") || process.env.AIBI_VERIFY_FULL === \"1\"") &&
          verifyRuntimeSource.includes("fullReceiptPath: verifyReceiptPath") &&
          verifyRuntimeSource.includes("write" + "FileSync(verifyReceiptPath") &&
          verifyRuntimeSource.includes("fullOutput ? receipt : compactReceipt(receipt)"),
      },
    {
        label: "verify-source-catalog-boundary",
        ok: verifySource.includes('from "./verify/sourceCatalog.mjs"') &&
          verifySource.includes("readVerifySourceCatalog(root)") &&
          verifySource.includes('from "./verify/suites/coreContracts.mjs"') &&
          verifySource.includes('from "./verify/suites/sourceContracts.mjs"') &&
          verifySource.includes('from "./verify/suites/dashboardViewContracts.mjs"') &&
          verifySource.includes('from "./verify/suites/appArchitectureContracts.mjs"') &&
          verifySource.includes('from "./verify/suites/productUxContracts.mjs"') &&
          verifySource.includes('from "./verify/suites/agentWorkflowContracts.mjs"') &&
          verifyCoreContractsSource.includes("export function appendCoreContractChecks") &&
          verifySourceContractsSource.includes("export function appendSourceContractChecks") &&
          verifyDashboardViewContractsSource.includes("export function appendDashboardViewContractChecks") &&
          verifyAppArchitectureContractsSource.includes("export function appendAppArchitectureContractChecks") &&
          verifyProductUxContractsSource.includes("export function appendProductUxContractChecks") &&
          verifyAgentWorkflowContractsSource.includes("export function appendAgentWorkflowContractChecks") &&
          packageJson.scripts?.build?.includes("vite build && node scripts/verify-bundle-budgets.mjs") &&
          packageJson.scripts?.["verify:bundle-budgets"] === "node scripts/verify-bundle-budgets.mjs" &&
          bundleBudgetConfigSource.includes('"schema": "aibi-bundle-budgets/v1"') &&
          bundleBudgetConfigSource.includes('"label": "global-css"') &&
          bundleBudgetConfigSource.includes('"label": "main-js"') &&
          verifyBundleBudgetsSource.includes('generatedBy: "scripts/verify-bundle-budgets.mjs"') &&
          verifyBundleBudgetsSource.includes("readdirSync(assetsDir)") &&
          verifyBundleBudgetsSource.includes("if (failedChecks.length) process.exitCode = 1") &&
          !verifySource.includes("read" + "FileSync(") &&
          verifySourceCatalogSource.includes("const textSourceFiles = {") &&
          verifySourceCatalogSource.includes("export function readVerifySourceCatalog(root)") &&
          verifySourceCatalogSource.includes("read" + "FileSync(join(root, ...pathSegments), \"utf8\")"),
      },
    {
        label: "domain-neutrality-regression-boundary",
        ok: packageJson.scripts["verify:domain-neutrality"] === "python scripts/verify-domain-neutrality.py" &&
          packageJson.scripts.verify.includes("python scripts/verify-domain-neutrality.py") &&
          existsSync(join(root, "scripts", "verify-domain-neutrality.py")) &&
          !verifySource.includes("writeCostMonitorFixtures") &&
          !verifySource.includes("cost-monitor-funds.csv"),
      },
    {
        label: "source-pipeline-rich-contract",
        ok: Array.isArray(byLabel["cli-preview-import"].parsed?.sourcePipelineContract?.stages) &&
          byLabel["cli-preview-import"].parsed.sourcePipelineContract.stages.every((stage) => stage.id && stage.outputEvidence) &&
          Array.isArray(byLabel["cli-preview-import"].parsed.sourcePipelineContract.coreSemanticRuntime?.semanticHints),
      },
    {
        label: "import-preview-merge-plan",
        ok: Boolean(
          byLabel["cli-preview-import"].parsed?.uniqueKeyQuality?.totalRows &&
          byLabel["cli-preview-import"].parsed?.mergePolicyPreview?.mergePlan?.incomingRows,
        ),
      },
    {
        label: "b-import-policy-and-job-log",
        ok: byLabel["cli-set-import-policy-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-set-import-policy-confirm"].parsed?.confirmed === true &&
          byLabel["cli-set-import-policy-confirm"].parsed?.policy?.conflictRule === "fill-empty" &&
          byLabel["cli-list-import-jobs"].parsed?.importJobs?.some((job) => job.table_key === "orders" && job.status === "success") &&
          byLabel["cli-remove-import-job-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-preview-import"].parsed?.mergePolicyPreview?.savedPolicy?.conflictRule === "fill-empty",
      },
    {
        label: "b-source-management-write-boundary",
        ok: byLabel["cli-list-tables"].parsed?.tables?.some((table) => table.table_key === "orders") &&
          byLabel["cli-inspect-table"].parsed?.table?.table_key === "orders" &&
          byLabel["cli-inspect-table"].parsed?.fieldConfig?.length > 0 &&
          byLabel["cli-rename-source-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-rename-source-confirm"].parsed?.confirmed === true &&
          byLabel["cli-rename-source-confirm"].parsed?.renamedSource?.name === "验证退款表" &&
          byLabel["cli-import-delete-source-validation-input"].parsed?.result?.tableKey === "verify_delete_source" &&
          byLabel["cli-delete-source-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-delete-source-dry-run"].parsed?.impact?.fieldConfigs > 0 &&
          byLabel["cli-delete-source-confirm"].parsed?.confirmed === true &&
          byLabel["cli-delete-source-confirm"].parsed?.deletedSource === "verify_delete_source",
      },
    {
        label: "source-read-model-service-boundary",
        ok: existsSync(join(root, "tools", "source_read_model_service.py")) &&
          biCliRuntimeSource.includes("from source_read_model_service import (") &&
          biCliRuntimeSource.includes("list_tables_command_service(") &&
          biCliRuntimeSource.includes("inspect_table_command_service(") &&
          sourceReadModelServiceSource.includes("def list_tables_command(") &&
          sourceReadModelServiceSource.includes("def inspect_table_command(") &&
          sourceReadModelServiceSource.includes("SELECT table_key, workspace_id, display_name, physical_table, source_file, row_count, column_count, created_at") &&
          sourceReadModelServiceSource.includes("SELECT field_name, role, usage, confidence") &&
          sourceReadModelServiceSource.includes("SELECT metric_key, label, measure, aggregation, dimension, time_field, value_format") &&
          sourceReadModelServiceSource.includes("SELECT view_key, name, tag_name, is_default, sort_order, created_by, agent_managed") &&
          sourceReadModelServiceSource.includes("SELECT *") &&
          sourceReadModelServiceSource.includes("relationship_record_payload(row)") &&
          sourceReadModelServiceSource.includes("SELECT job_key, workspace_id, source_file, mode, status, row_count, created_at") &&
          sourceReadModelServiceSource.includes("\"fieldConfig\"") &&
          sourceReadModelServiceSource.includes("\"importJobs\"") &&
          sourceReadModelServiceSource.includes("\"connectors\"") &&
          !biCliRuntimeSource.includes("SELECT field_name, role, usage, confidence\n                FROM field_semantics") &&
          !biCliRuntimeSource.includes("SELECT job_key, workspace_id, source_file, mode, status, row_count, created_at\n                FROM import_jobs") &&
          byLabel["cli-list-tables"].parsed?.count >= 2 &&
          byLabel["cli-inspect-table"].parsed?.columns?.includes("order_id") &&
          byLabel["cli-inspect-table"].parsed?.metrics?.some((metric) => metric.metric_key === "orders_row_count") &&
          byLabel["cli-inspect-table"].parsed?.views?.some((view) => view.view_key === "view_orders_default") &&
          byLabel["cli-inspect-table"].parsed?.relationships?.some((relation) => relation.relation_key.includes("orders_refunds")) &&
          byLabel["cli-inspect-table"].parsed?.importJobs?.length > 0,
      },
    {
        label: "source-management-command-service-boundary",
        ok: existsSync(join(root, "tools", "source_management_command_service.py")) &&
          biCliRuntimeSource.includes("from source_management_command_service import (") &&
          biCliRuntimeSource.includes("rename_source_command_service(") &&
          biCliRuntimeSource.includes("remaining_table_key_after_delete_service(") &&
          biCliRuntimeSource.includes("build_delete_source_plan_service(") &&
          biCliRuntimeSource.includes("delete_source_command_service(") &&
          sourceManagementCommandServiceSource.includes("def rename_source_command(") &&
          sourceManagementCommandServiceSource.includes("def remaining_table_key_after_delete(") &&
          sourceManagementCommandServiceSource.includes("def build_delete_source_plan(") &&
          sourceManagementCommandServiceSource.includes("def delete_source_command(") &&
          sourceManagementCommandServiceSource.includes("UPDATE table_registry SET display_name = ? WHERE table_key = ? AND workspace_id = ?") &&
          sourceManagementCommandServiceSource.includes("DROP TABLE IF EXISTS") &&
          sourceManagementCommandServiceSource.includes("DELETE FROM table_registry WHERE table_key = ? AND workspace_id = ?") &&
          sourceManagementCommandServiceSource.includes("affectedWidgets") &&
          sourceManagementCommandServiceSource.includes("affectedConnectors") &&
          sourceManagementCommandServiceSource.includes("nextDefaultTableKey") &&
          !sourceManagementCommandServiceSource.includes("def source_was_seed_import(") &&
          !sourceManagementCommandServiceSource.includes("mode = 'seed'") &&
          !sourceManagementCommandServiceSource.includes("seed_repair_disabled") &&
          !sourceManagementCommandServiceSource.includes('"orders", "refunds"') &&
          !biCliRuntimeSource.includes("\"affectedRelationshipKeys\": relation_keys") &&
          !biCliRuntimeSource.includes("config[\"targetTableKey\"] = \"\"") &&
          byLabel["cli-rename-source-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-rename-source-confirm"].parsed?.confirmed === true &&
          byLabel["cli-delete-source-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-delete-source-dry-run"].parsed?.nextDefaultTableKey &&
          byLabel["cli-delete-source-confirm"].parsed?.confirmed === true,
      },
    {
        label: "production-empty-start-no-seed-boundary",
        ok: !existsSync(join(root, "tools", "seed_orchestration_service.py")) &&
          !existsSync(join(root, "tools", "seed_default_objects_service.py")) &&
          !biCliRuntimeSource.includes("from seed_orchestration_service import (") &&
          !biCliRuntimeSource.includes("from seed_default_objects_service import (") &&
          !biCliRuntimeSource.includes("ensure_seed_data(") &&
          !biCliRuntimeSource.includes("ensure_default_import_policies(") &&
          !biCliRuntimeSource.includes("create_default_views(connection)") &&
          !biCliRuntimeSource.includes(retiredSeedEnvName) &&
          !biCliCoreSource.includes("FIXTURE_DIR") &&
          !importTableWriterServiceSource.includes('mode == "seed"') &&
          !sourceManagementCommandServiceSource.includes("seed_repair_disabled") &&
          verifySource.includes("verify-bootstrap-import-orders") &&
          verifyBiCliAgentContractSource.includes("verify-contract-bootstrap-import-orders") &&
          (biCliRuntimeSource.match(/def table_columns\(/g) ?? []).length === 1 &&
          byLabel["cli-status"].parsed?.health?.ok === true &&
          byLabel["cli-status"].parsed?.counts?.tables === 0 &&
          byLabel["verify-bootstrap-import-orders"].parsed?.result?.tableKey === "orders" &&
          byLabel["verify-bootstrap-import-refunds"].parsed?.result?.tableKey === "refunds" &&
          byLabel["cli-list-tables"].parsed?.tables?.some((table) => table.table_key === "orders") &&
          byLabel["cli-list-tables"].parsed?.tables?.some((table) => table.table_key === "refunds"),
      },
    {
        label: "validation-bootstrap-objects-boundary",
        ok: byLabel["verify-bootstrap-relationship"].parsed?.saved?.relation_key === "orders_refunds_order_id_order_id" &&
          byLabel["verify-bootstrap-orders-view"].parsed?.savedView?.view_key === "view_orders_default" &&
          byLabel["verify-bootstrap-refunds-view"].parsed?.savedView?.view_key === "view_refunds_default" &&
          byLabel["verify-bootstrap-dashboard"].parsed?.confirmed === true &&
          byLabel["verify-bootstrap-default-dashboard"].parsed?.confirmed === true &&
          byLabel["cli-default-dashboard-bootstrap"].parsed?.dashboards?.[0]?.widgets?.length >= 1 &&
          byLabel["cli-list-views"].parsed?.savedViews?.some((view) => view.view_key === "view_orders_default" && view.name === "订单明细视图") &&
          byLabel["cli-list-views"].parsed?.savedViews?.some((view) => view.view_key === "view_refunds_default" && view.name === "退款明细视图"),
      },
    {
        label: "b-connectors-file-sync-and-boundary",
        ok: byLabel["cli-save-connector-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-save-connector-confirm"].parsed?.confirmed === true &&
          byLabel["cli-list-connectors"].parsed?.connectors?.some((connector) => connector.connectorKey === "verify_file_connector") &&
          byLabel["cli-sync-connector-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-sync-connector-dry-run"].parsed?.syncPlan?.adapterId === "local-tabular/v1" &&
          byLabel["cli-sync-connector-dry-run"].parsed?.sideEffects?.businessDatabaseWrite === false &&
          byLabel["cli-sync-connector-confirm"].parsed?.confirmed === true &&
          byLabel["cli-sync-connector-confirm"].parsed?.connectorSync?.importResult?.tableKey === "orders" &&
          byLabel["cli-sync-external-connector-blocked"].parsed?.ok === false &&
          byLabel["cli-remove-connector-dry-run"].parsed?.requiresConfirmation === true,
      },
    {
        label: "b-preferences-theme-palettes",
        ok: byLabel["cli-preferences"].parsed?.preferences?.requireDeleteNameConfirmation === true &&
          byLabel["cli-preferences"].parsed?.preferences?.themeKey &&
          byLabel["cli-preferences-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-preferences-confirm"].parsed?.confirmed === true &&
          byLabel["cli-theme-palettes"].parsed?.themePalettes?.some((theme) => theme.themeKey === "L1") &&
          byLabel["cli-theme-save-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-theme-save-confirm"].parsed?.confirmed === true &&
          byLabel["cli-theme-save-confirm"].parsed?.savedThemePalette?.themeKey === "verify_custom" &&
          byLabel["cli-theme-delete-dry-run"].parsed?.requiresConfirmation === true,
      },
    {
        label: "frontend-theme-no-flash-bootstrap",
        ok: indexHtmlSource.includes("aibiHybrid.themeSnapshot") &&
          indexHtmlSource.includes("function readStoredTheme()") &&
          indexHtmlSource.includes("var theme = readStoredTheme()") &&
          !indexHtmlSource.includes("XMLHttpRequest") &&
          !indexHtmlSource.includes("/api/workbench") &&
          indexHtmlSource.includes("fallbackDarkTheme") &&
          indexHtmlSource.includes('window.matchMedia("(prefers-color-scheme: dark)")') &&
          indexHtmlSource.includes("root.dataset.themeMode = mode") &&
          indexHtmlSource.includes("root.style.colorScheme = mode") &&
          indexHtmlSource.includes('root.style.setProperty("--bi-on-accent", onAccent)') &&
          indexHtmlSource.includes('html[data-theme-mode="dark"]') &&
          appSource.includes("hasStoredThemeSnapshot") &&
          appSource.includes("if (!status.database && hasStoredThemeSnapshot())") &&
          themeSource.includes('const themeSnapshotStorageKey = "aibiHybrid.themeSnapshot"') &&
          themeSource.includes("export function hasStoredThemeSnapshot") &&
          themeSource.includes("window.localStorage.setItem(themeSnapshotStorageKey"),
      },
    {
        label: "preferences-theme-command-service-boundary",
        ok: existsSync(join(root, "tools", "preferences_theme_command_service.py")) &&
          biCliRuntimeSource.includes("from preferences_theme_command_service import (") &&
          biCliRuntimeSource.includes("normalize_user_preferences_service(") &&
          biCliRuntimeSource.includes("normalize_theme_tokens_service(") &&
          biCliRuntimeSource.includes("normalize_theme_palette_service(") &&
          biCliRuntimeSource.includes("validate_theme_palette_payload_service(") &&
          biCliRuntimeSource.includes("ensure_default_preferences_and_themes_service(") &&
          biCliRuntimeSource.includes("load_user_preferences_service(") &&
          biCliRuntimeSource.includes("save_user_preferences_service(") &&
          biCliRuntimeSource.includes("list_theme_palettes_service(") &&
          biCliRuntimeSource.includes("upsert_theme_palette_service(") &&
          biCliRuntimeSource.includes("delete_theme_palette_service(") &&
          biCliRuntimeSource.includes("preferences_payload_service(") &&
          biCliRuntimeSource.includes("preferences_command_service(") &&
          biCliRuntimeSource.includes("theme_palettes_command_service(") &&
          !biCliRuntimeSource.includes("DEFAULT_USER_PREFERENCES =") &&
          !biCliRuntimeSource.includes("DEFAULT_THEME_PALETTES =") &&
          preferencesThemeCommandServiceSource.includes("DEFAULT_USER_PREFERENCES =") &&
          preferencesThemeCommandServiceSource.includes("DEFAULT_THEME_PALETTES =") &&
          preferencesThemeCommandServiceSource.includes("REQUIRED_THEME_TOKENS =") &&
          preferencesThemeCommandServiceSource.includes("def ensure_default_preferences_and_themes(") &&
          preferencesThemeCommandServiceSource.includes("def preferences_command(") &&
          preferencesThemeCommandServiceSource.includes("def theme_palettes_command(") &&
          preferencesThemeCommandServiceSource.includes("Built-in themes cannot be overwritten") &&
          preferencesThemeCommandServiceSource.includes("Built-in themes cannot be deleted") &&
          !preferencesThemeCommandServiceSource.includes("return {\"themeKey\": row[\"theme_key\"], \"name\": row[\"name\"]}\n    connection.commit()") &&
          byLabel["cli-preferences"].parsed?.activeTheme?.themeKey === byLabel["cli-preferences"].parsed?.preferences?.themeKey &&
          byLabel["cli-preferences-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-preferences-confirm"].parsed?.confirmed === true &&
          byLabel["cli-theme-save-dry-run"].parsed?.proposedThemePalette?.themeKey === "verify_custom" &&
          byLabel["cli-theme-save-confirm"].parsed?.savedThemePalette?.createdBy === "manual" &&
          byLabel["cli-theme-delete-dry-run"].parsed?.operation === "delete-theme",
      },
    {
        label: "b-config-portability",
        ok: byLabel["cli-validate-config"].parsed?.ok === true &&
          Array.isArray(byLabel["cli-validate-config"].parsed?.errors) &&
          byLabel["cli-validate-config"].parsed?.errors.length === 0 &&
          byLabel["cli-export-config"].parsed?.businessDataIncluded === false &&
          byLabel["cli-export-config"].parsed?.tables?.dashboards >= 1 &&
          byLabel["cli-export-config"].parsed?.tables?.data_connectors >= 1 &&
          byLabel["cli-apply-config-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-apply-config-dry-run"].parsed?.restorePlan?.dashboards >= 1,
      },
    {
        label: "config-command-service-boundary",
        ok: existsSync(join(root, "tools", "config_command_service.py")) &&
          biCliRuntimeSource.includes("from config_command_service import (") &&
          biCliRuntimeSource.includes("redact_secret_value_service(") &&
          biCliRuntimeSource.includes("restore_redacted_value_service(") &&
          biCliRuntimeSource.includes("config_row_for_export_service(") &&
          biCliRuntimeSource.includes("prepare_config_rows_for_restore_service(") &&
          biCliRuntimeSource.includes("export_metadata_config_service(") &&
          biCliRuntimeSource.includes("restore_config_rows_service(") &&
          biCliRuntimeSource.includes("validate_metadata_config_service(") &&
          biCliRuntimeSource.includes("validate_config_command_service(") &&
          biCliRuntimeSource.includes("export_config_command_service(") &&
          biCliRuntimeSource.includes("apply_config_command_service(") &&
          !biCliRuntimeSource.includes("CONFIG_TABLES =") &&
          !biCliRuntimeSource.includes("CONFIG_KIND =") &&
          configCommandServiceSource.includes("CONFIG_TABLES =") &&
          configCommandServiceSource.includes("CONFIG_KIND = \"aibi-hybrid-local-bi-config\"") &&
          configCommandServiceSource.includes("def redact_secret_value(") &&
          configCommandServiceSource.includes("def restore_redacted_value(") &&
          configCommandServiceSource.includes("def export_metadata_config(") &&
          configCommandServiceSource.includes("def restore_config_rows(") &&
          configCommandServiceSource.includes("def validate_metadata_config(") &&
          configCommandServiceSource.includes("def validate_config_command(") &&
          configCommandServiceSource.includes("def export_config_command(") &&
          configCommandServiceSource.includes("def apply_config_command(") &&
          configCommandServiceSource.includes("__AIBI_REDACTED__") &&
          configCommandServiceSource.includes("businessDataIncluded") &&
          configCommandServiceSource.includes("shutil.copy2(DB_PATH, backup_path)") &&
          configCommandServiceSource.includes("calculated_field_names_for_table=") &&
          configCommandServiceSource.includes("widget_types=") &&
          configCommandServiceSource.includes("safe_aggregations=") &&
          byLabel["cli-validate-config"].parsed?.ok === true &&
          byLabel["cli-export-config"].parsed?.kind === "aibi-hybrid-local-bi-config" &&
          byLabel["cli-export-config"].parsed?.businessDataIncluded === false &&
          byLabel["cli-export-config"].parsed?.redaction?.includes("__AIBI_REDACTED__") &&
          byLabel["cli-apply-config-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-apply-config-dry-run"].parsed?.message?.includes("business data tables are not imported"),
      },
    {
        label: "relationship-preview-coverage",
        ok: Boolean(
          byLabel["cli-relationship-preview"].parsed?.relationshipPreview?.metrics?.leftRows &&
          typeof byLabel["cli-relationship-preview"].parsed?.relationshipPreview?.metrics?.confidence === "number",
        ),
      },
    {
        label: "b-relationship-query-runtime",
        ok: byLabel["cli-list-relationships"].parsed?.relationships?.some((relationship) => relationship.relation_key === "orders_refunds_order_id_order_id") &&
          byLabel["cli-query-relationship"].parsed?.relationshipQuery?.joinType === "left" &&
          byLabel["cli-query-relationship"].parsed?.relationshipQuery?.rows?.[0]?.["左表.channel"] === "Douyin" &&
          byLabel["cli-query-relationship"].parsed?.rows?.[0]?.value === 3440 &&
          byLabel["cli-remove-relationship-dry-run"].parsed?.requiresConfirmation === true,
      },
    {
        label: "duckdb-query-runtime",
        ok: byLabel["cli-status"].parsed?.queryRuntime?.available === true &&
          byLabel["cli-query"].parsed?.query?.runtime?.engine === "duckdb" &&
          byLabel["cli-query"].parsed?.query?.runtime?.compiledSql?.includes("TRY_CAST") &&
          byLabel["cli-query"].parsed?.query?.runtime?.syncedRows > 0,
      },
    {
        label: "workspace-create-default-dry-run",
        ok: byLabel["cli-workspace-create-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-workspace-create-dry-run"].parsed?.proposed?.name === "验证工作区",
      },
    {
        label: "workspace-create-select-active",
        ok: byLabel["cli-workspace-create-confirm"].parsed?.created?.id === "verify_workspace" &&
          byLabel["cli-workspace-select-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-workspace-select-confirm"].parsed?.workspace?.id === "verify_workspace" &&
          byLabel["cli-status-after-workspace-select"].parsed?.workspace?.id === "verify_workspace" &&
          byLabel["cli-status-after-workspace-select"].parsed?.workspaces?.some((workspace) => workspace.id === "verify_workspace" && workspace.isActive === true) &&
          byLabel["cli-workspace-select-default"].parsed?.workspace?.id === "default",
      },
    {
        label: "workspace-delete-safe-lifecycle",
        ok: byLabel["cli-workspace-delete-target-create"].parsed?.created?.id === "delete_workspace_target" &&
          byLabel["cli-workspace-delete-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-workspace-delete-dry-run"].parsed?.workspace?.id === "delete_workspace_target" &&
          typeof byLabel["cli-workspace-delete-dry-run"].parsed?.impact?.totalRows === "number" &&
          byLabel["cli-workspace-delete-confirm"].parsed?.deletedWorkspace?.id === "delete_workspace_target" &&
          byLabel["cli-workspace-delete-confirm"].parsed?.confirmed === true &&
          byLabel["cli-workspace-delete-default-blocked"].ok === true &&
          String(byLabel["cli-workspace-delete-default-blocked"].parsed?.error ?? "").includes("Default workspace cannot be deleted") &&
          byLabel["cli-workspace-active-delete-target-select"].parsed?.workspace?.id === "active_delete_workspace" &&
          byLabel["cli-workspace-delete-active-blocked"].ok === true &&
          String(byLabel["cli-workspace-delete-active-blocked"].parsed?.error ?? "").includes("Cannot delete the active workspace") &&
          byLabel["cli-workspace-select-default-after-delete-check"].parsed?.workspace?.id === "default",
      },
    {
        label: "workspace-command-service-boundary",
        ok: existsSync(join(root, "tools", "workspace_command_service.py")) &&
          biCliRuntimeSource.includes("from workspace_command_service import (") &&
          biCliRuntimeSource.includes("get_system_flag_service(") &&
          biCliRuntimeSource.includes("set_system_flag_service(") &&
          biCliRuntimeSource.includes("active_workspace_id_service(") &&
          biCliRuntimeSource.includes("workspace_records_service(") &&
          biCliRuntimeSource.includes("workspace_create_command_service(") &&
          biCliRuntimeSource.includes("workspace_select_command_service(") &&
          workspaceCommandServiceSource.includes("def get_system_flag(") &&
          workspaceCommandServiceSource.includes("def set_system_flag(") &&
          workspaceCommandServiceSource.includes("def active_workspace_id(") &&
          workspaceCommandServiceSource.includes("def workspace_records(") &&
          workspaceCommandServiceSource.includes("def workspace_create_command(") &&
          workspaceCommandServiceSource.includes("def workspace_select_command(") &&
          workspaceCommandServiceSource.includes("def workspace_delete_command(") &&
          workspaceCommandServiceSource.includes("WORKSPACE_SCOPED_TABLES") &&
          workspaceCommandServiceSource.includes("DROP TABLE IF EXISTS") &&
          workspaceCommandServiceSource.includes("INSERT INTO workspaces") &&
          workspaceCommandServiceSource.includes("ON CONFLICT(key) DO UPDATE") &&
          biCliRuntimeSource.includes("workspace_delete_command_service(") &&
          biCliRuntimeSource.includes('workspace_delete = sub.add_parser("workspace-delete")') &&
          byLabel["cli-workspace-create-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-workspace-create-confirm"].parsed?.created?.id === "verify_workspace" &&
          byLabel["cli-workspace-create-confirm"].parsed?.created?.isActive === true &&
          byLabel["cli-workspace-select-dry-run"].parsed?.currentWorkspaceId === "verify_workspace" &&
          byLabel["cli-workspace-select-confirm"].parsed?.workspace?.isActive === true &&
          byLabel["cli-workspace-delete-confirm"].parsed?.deletedWorkspace?.id === "delete_workspace_target" &&
          byLabel["cli-workspace-delete-default-blocked"].ok === true &&
          byLabel["cli-workspace-delete-active-blocked"].ok === true &&
          byLabel["cli-status-after-workspace-select"].parsed?.workspaces?.some((workspace) => workspace.id === "verify_workspace" && workspace.isActive === true) &&
          byLabel["workspace-source-intelligence-action-draft-isolation"].ok === true &&
          byLabel["workspace-bi-metadata-isolation"].ok === true &&
          byLabel["workspace-same-key-physical-isolation"].ok === true,
      },
    {
        label: "workspace-chinese-name-stable-id",
        ok: byLabel["cli-workspace-create-chinese-dry-run"].parsed?.proposed?.name === "验证中文工作区" &&
          typeof byLabel["cli-workspace-create-chinese-dry-run"].parsed?.proposed?.id === "string" &&
          byLabel["cli-workspace-create-chinese-dry-run"].parsed?.proposed?.id.startsWith("workspace_") &&
          byLabel["cli-workspace-create-chinese-dry-run"].parsed?.proposed?.id !== "source",
      },
    {
        label: "source-run-detail-complete",
        ok: byLabel["cli-source-run-detail"].parsed?.sourceRun?.profile?.rowCount > 0 &&
          byLabel["cli-source-run-detail"].parsed?.fields?.length > 0 &&
          byLabel["cli-source-run-detail"].parsed?.metrics?.length > 0 &&
          Array.isArray(byLabel["cli-source-run-detail"].parsed?.sourceRun?.evidence),
      }
  );
}
