export function appendCoreContractChecks(context) {
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
    biCliCoreSource,
    biCliEnvelopeSource,
    biCliEvidenceBundlesSource,
    biCliSource,
    businessDashboardServiceSource,
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
    inspectorControllerSource,
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
    verifyFixturesSource,
    verifyProductUxContractsSource,
    verifyRuntimeSource,
    verifySource,
    verifySourceCatalogSource,
    verifySourceContractsSource,
    verifyUiRealImportSource,
    workspaceCommandServiceSource,
  } = context;
  const appSource = `${appEntrySource}\n${appMainViewSource}\n${inspectorControllerSource}`;
  checks.push(
    {
        label: "native-bi-cli-agent-contract-boundary",
        ok: existsSync(join(root, "tools", "bi_cli_contracts.py")) &&
          existsSync(join(root, "tools", "bi_cli_envelope.py")) &&
          existsSync(join(root, "tools", "bi_cli_evidence_bundles.py")) &&
          existsSync(join(root, "scripts", "verify-bi-cli-agent-contract.mjs")) &&
          biCliSource.includes("from bi_cli_contracts import") &&
          biCliSource.includes("from bi_cli_envelope import enrich_cli_output, error_output") &&
          biCliSource.includes("from bi_cli_evidence_bundles import artifact_ref, write_evidence_bundle") &&
          biCliSource.includes("def cli_contract_command(") &&
          biCliSource.includes("def list_commands_command(") &&
          biCliContractsSource.includes("CONTRACT_SCHEMA_VERSION = \"aibi-bi-cli-contract/v1\"") &&
          biCliContractsSource.includes("def build_cli_contract(") &&
          biCliEnvelopeSource.includes("ENVELOPE_SCHEMA_VERSION = \"aibi-bi-cli-envelope/v1\"") &&
          biCliEnvelopeSource.includes("def enrich_cli_output(") &&
          biCliEvidenceBundlesSource.includes("EVIDENCE_BUNDLE_SCHEMA = \"aibi-evidence-bundle/v1\"") &&
          biCliEvidenceBundlesSource.includes("def write_evidence_bundle(") &&
          verifyBiCliAgentContractSource.includes("preview-import-evidence-bundle") &&
          biCliContractDocSource.includes("# BI CLI Contract") &&
          biCliContractDocSource.includes("`source-intelligence`") &&
          byLabel["cli-contract"].parsed?.contract?.schema === "aibi-bi-cli-contract/v1" &&
          byLabel["cli-contract"].parsed?.contract?.commandCount >= 70 &&
          byLabel["cli-contract-markdown-output"].parsed?.outputPath &&
          existsSync(byLabel["cli-contract-markdown-output"].parsed.outputPath) &&
          byLabel["cli-list-dashboard-write-commands"].parsed?.commands?.some((command) => command.name === "business-dashboard" && command.writesEvidence === true) &&
          byLabel["cli-status"].parsed?.envelope?.schema === "aibi-bi-cli-envelope/v1" &&
          byLabel["cli-status"].parsed?.artifacts?.some((artifact) => artifact.label === "database") &&
          byLabel["cli-preview-import"].parsed?.evidenceBundle?.schema === "aibi-evidence-bundle/v1" &&
          existsSync(byLabel["cli-preview-import"].parsed?.evidenceBundle?.manifestPath ?? "") &&
          byLabel["cli-business-dashboard-draft"].parsed?.requiresConfirmation === false &&
          byLabel["cli-business-dashboard-draft"].parsed?.evidenceBundle?.schema === "aibi-evidence-bundle/v1" &&
          byLabel["cli-source-intelligence-validation-inputs"].parsed?.evidenceBundle?.schema === "aibi-evidence-bundle/v1",
      },
    {
        label: "agent-prompt-resolution-boundary",
        ok: existsSync(join(root, "tools", "agent_prompt_resolution.py")) &&
          biCliSource.includes("from agent_prompt_resolution import (") &&
          !biCliSource.includes("def prompt_mentions_widget_add(") &&
          !biCliSource.includes("def prompt_mentions_dashboard_filter(") &&
          !biCliSource.includes("def prompt_mentions_view_save(") &&
          !biCliSource.includes("def dashboard_operation_from_prompt(") &&
          agentPromptResolutionSource.includes("class AgentPromptIntents") &&
          agentPromptResolutionSource.includes("def resolve_agent_prompt_intents(") &&
          agentPromptResolutionSource.includes("def select_agent_table(") &&
          agentPromptResolutionSource.includes("def should_create_agent_draft(") &&
          agentPromptResolutionSource.includes("def build_agent_action_payload(") &&
          agentPromptResolutionSource.includes("def agent_action_kind(") &&
          agentPromptResolutionSource.includes("def agent_action_evidence(") &&
          byLabel["cli-agent-widget-draft"].parsed?.actionDraft?.kind === "dashboard.widget.add" &&
          byLabel["cli-agent-dashboard-filter-draft"].parsed?.actionDraft?.kind === "dashboard.filter.add",
      },
    {
        label: "agent-action-confirmation-boundary",
        ok: existsSync(join(root, "tools", "agent_action_confirmations.py")) &&
          biCliSource.includes("from agent_action_confirmations import (") &&
          !biCliSource.includes("UPDATE action_drafts SET status = 'confirmed'") &&
          !biCliSource.includes("UPDATE action_drafts SET status = 'rejected'") &&
          !agentActionConfirmationsSource.includes("UPDATE action_drafts SET status") &&
          agentActionConfirmationsSource.includes("def confirm_dry_run_response(") &&
          agentActionConfirmationsSource.includes("def reject_dry_run_response(") &&
          agentActionConfirmationsSource.includes("from agent_action_draft_store import mark_action_confirmed, mark_action_rejected") &&
          agentActionConfirmationsSource.includes("def confirmed_response(") &&
          agentActionConfirmationsSource.includes("def rejected_response(") &&
          byLabel["cli-agent-confirm-widget"].parsed?.confirmed === true &&
          byLabel["cli-agent-confirm-dashboard-filter"].parsed?.confirmed === true &&
          byLabel["cli-agent-reject-dashboard"].parsed?.decision === "reject",
      },
    {
        label: "agent-action-draft-store-boundary",
        ok: existsSync(join(root, "tools", "agent_action_draft_store.py")) &&
          biCliSource.includes("from agent_action_draft_store import") &&
          biCliSource.includes("create_action_draft(") &&
          biCliSource.includes("get_action_draft(") &&
          biCliSource.includes("list_action_drafts(") &&
          biCliSource.includes("count_pending_action_drafts(") &&
          biCliSource.includes("action_draft_payload(") &&
          !biCliSource.includes("INSERT INTO action_drafts(action_key, workspace_id, kind, label, status, payload_json, evidence_json, created_at)") &&
          !biCliSource.includes("SELECT * FROM action_drafts") &&
          !biCliSource.includes("SELECT COUNT(*) FROM action_drafts WHERE status = 'draft'") &&
          agentActionDraftStoreSource.includes("def create_action_draft(") &&
          agentActionDraftStoreSource.includes("def get_action_draft(") &&
          agentActionDraftStoreSource.includes("def action_draft_payload(") &&
          agentActionDraftStoreSource.includes("def list_action_drafts(") &&
          agentActionDraftStoreSource.includes("def count_pending_action_drafts(") &&
          agentActionDraftStoreSource.includes("def mark_action_confirmed(") &&
          agentActionDraftStoreSource.includes("def mark_action_rejected(") &&
          byLabel["cli-agent-widget-draft"].parsed?.requiresConfirmation === true &&
          byLabel["cli-source-dashboard-draft"].parsed?.requiresConfirmation === true &&
          byLabel["cli-agent-action-drafts-after-widget-confirm"].parsed?.pendingCount >= 0 &&
          byLabel["cli-source-dashboard-action-drafts-after-confirm"].parsed?.pendingCount >= 0,
      },
    {
        label: "agent-confirm-execution-handlers-phase1-boundary",
        ok: existsSync(join(root, "tools", "agent_confirm_execution_handlers.py")) &&
          biCliSource.includes("from agent_confirm_execution_handlers import (") &&
          biCliSource.includes("return handle_index_create_confirmation(") &&
          biCliSource.includes("return handle_relationship_save_confirmation(") &&
          biCliSource.includes("return handle_import_commit_confirmation(") &&
          agentConfirmExecutionHandlersSource.includes("def handle_index_create_confirmation(") &&
          agentConfirmExecutionHandlersSource.includes("def handle_relationship_save_confirmation(") &&
          agentConfirmExecutionHandlersSource.includes("def handle_import_commit_confirmation(") &&
          agentConfirmExecutionHandlersSource.includes("build_index_plan: Callable") &&
          agentConfirmExecutionHandlersSource.includes("build_relationship_save_plan: Callable") &&
          agentConfirmExecutionHandlersSource.includes("build_import_preview: Callable") &&
          byLabel["cli-agent-confirm-index"].parsed?.confirmed === true &&
          byLabel["cli-agent-confirm-relationship"].parsed?.confirmed === true &&
          byLabel["cli-agent-confirm-import"].parsed?.confirmed === true,
      },
    {
        label: "agent-confirm-execution-handlers-phase2-boundary",
        ok: existsSync(join(root, "tools", "agent_confirm_execution_handlers.py")) &&
          biCliSource.includes("return handle_formula_save_confirmation(") &&
          biCliSource.includes("return handle_view_save_confirmation(") &&
          biCliSource.includes("return handle_metric_add_confirmation(") &&
          biCliSource.includes("return handle_semantic_set_confirmation(") &&
          agentConfirmExecutionHandlersSource.includes("def handle_formula_save_confirmation(") &&
          agentConfirmExecutionHandlersSource.includes("def handle_view_save_confirmation(") &&
          agentConfirmExecutionHandlersSource.includes("def handle_metric_add_confirmation(") &&
          agentConfirmExecutionHandlersSource.includes("def handle_semantic_set_confirmation(") &&
          agentConfirmExecutionHandlersSource.includes("build_formula_save_plan: Callable") &&
          agentConfirmExecutionHandlersSource.includes("build_save_view_plan: Callable") &&
          agentConfirmExecutionHandlersSource.includes("build_metric_add_plan: Callable") &&
          agentConfirmExecutionHandlersSource.includes("build_semantic_set_plan: Callable") &&
          byLabel["cli-agent-confirm-formula"].parsed?.confirmed === true &&
          byLabel["cli-agent-confirm-view"].parsed?.confirmed === true &&
          byLabel["cli-agent-confirm-metric"].parsed?.confirmed === true &&
          byLabel["cli-agent-confirm-semantic"].parsed?.confirmed === true,
      },
    {
        label: "agent-confirm-execution-handlers-phase3-boundary",
        ok: existsSync(join(root, "tools", "agent_confirm_execution_handlers.py")) &&
          biCliSource.includes("return handle_dashboard_widget_add_confirmation(") &&
          biCliSource.includes("return handle_dashboard_filter_add_confirmation(") &&
          biCliSource.includes("return handle_dashboard_operation_confirmation(") &&
          biCliSource.includes("return handle_dashboard_create_confirmation(") &&
          agentConfirmExecutionHandlersSource.includes("def handle_dashboard_widget_add_confirmation(") &&
          agentConfirmExecutionHandlersSource.includes("def handle_dashboard_filter_add_confirmation(") &&
          agentConfirmExecutionHandlersSource.includes("def handle_dashboard_operation_confirmation(") &&
          agentConfirmExecutionHandlersSource.includes("def handle_dashboard_create_confirmation(") &&
          agentConfirmExecutionHandlersSource.includes("build_widget_proposal: Callable") &&
          agentConfirmExecutionHandlersSource.includes("build_dashboard_filter_add_plan: Callable") &&
          agentConfirmExecutionHandlersSource.includes("build_dashboard_operation_plan: Callable") &&
          agentConfirmExecutionHandlersSource.includes("build_agent_dashboard_create_draft: Callable") &&
          byLabel["cli-agent-confirm-widget"].parsed?.confirmed === true &&
          byLabel["cli-agent-confirm-dashboard-filter"].parsed?.confirmed === true &&
          byLabel["cli-agent-confirm-dashboard-copy"].parsed?.confirmed === true &&
          byLabel["cli-agent-confirm-dashboard-rename"].parsed?.confirmed === true &&
          byLabel["cli-agent-confirm-dashboard-delete"].parsed?.confirmed === true &&
          byLabel["cli-agent-confirm-dashboard"].parsed?.confirmed === true,
      },
    {
        label: "agent-recommended-commands-boundary",
        ok: existsSync(join(root, "tools", "agent_recommended_commands.py")) &&
          biCliSource.includes("from agent_recommended_commands import build_agent_recommended_commands") &&
          biCliSource.includes("recommended = build_agent_recommended_commands(") &&
          !biCliSource.includes("recommended.append(") &&
          agentRecommendedCommandsSource.includes("def build_agent_recommended_commands(") &&
          agentRecommendedCommandsSource.includes("python tools/bi_cli.py --json status") &&
          agentRecommendedCommandsSource.includes("python tools/bi_cli.py --json add-widget") &&
          agentRecommendedCommandsSource.includes("python tools/bi_cli.py --json add-filter") &&
          agentRecommendedCommandsSource.includes("python tools/bi_cli.py --json save-view") &&
          byLabel["cli-agent-widget-draft"].parsed?.recommendedCommands?.some((command) => command.includes("add-widget")) &&
          byLabel["cli-agent-dashboard-filter-draft"].parsed?.recommendedCommands?.some((command) => command.includes("add-filter")) &&
          readOnlyAgentCheck.parsed?.recommendedCommands?.some((command) => command.includes("--json query")),
      },
    {
        label: "saved-view-query-service-boundary",
        ok: existsSync(join(root, "tools", "saved_view_query_service.py")) &&
          biCliSource.includes("from saved_view_query_service import (") &&
          biCliSource.includes("query_table_command_service(") &&
          biCliSource.includes("save_view_command_service(") &&
          biCliSource.includes("copy_view_command_service(") &&
          biCliSource.includes("delete_view_command_service(") &&
          biCliSource.includes("build_save_view_plan_service(") &&
          biCliSource.includes("execute_save_view_plan_service(") &&
          !biCliSource.includes("def table_query_payload_from_args(") &&
          !biCliSource.includes("def view_row_to_dict(") &&
          !biCliSource.includes("SELECT * FROM saved_views WHERE view_key = ? AND table_key = ? AND workspace_id = ?") &&
          !biCliSource.includes("DELETE FROM saved_views WHERE view_key = ? AND workspace_id = ?") &&
          savedViewQueryServiceSource.includes("def table_query_payload_from_args(") &&
          savedViewQueryServiceSource.includes("def query_table_command(") &&
          savedViewQueryServiceSource.includes("def build_save_view_plan(") &&
          savedViewQueryServiceSource.includes("def execute_save_view_plan(") &&
          savedViewQueryServiceSource.includes("def copy_view_command(") &&
          savedViewQueryServiceSource.includes("def delete_view_command(") &&
          byLabel["cli-save-view-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-save-view-confirm"].parsed?.confirmed === true,
      },
    {
        label: "metric-formula-command-service-boundary",
        ok: existsSync(join(root, "tools", "metric_formula_command_service.py")) &&
          biCliSource.includes("from metric_formula_command_service import (") &&
          biCliSource.includes("add_metric_command_service(") &&
          biCliSource.includes("query_metric_command_service(") &&
          biCliSource.includes("formula_preview_command_service(") &&
          biCliSource.includes("save_formula_command_service(") &&
          biCliSource.includes("delete_formula_command_service(") &&
          metricFormulaCommandServiceSource.includes("def add_metric_command(") &&
          metricFormulaCommandServiceSource.includes("def query_metric_command(") &&
          metricFormulaCommandServiceSource.includes("def formula_preview_command(") &&
          metricFormulaCommandServiceSource.includes("def save_formula_command(") &&
          metricFormulaCommandServiceSource.includes("def delete_formula_command(") &&
          metricFormulaCommandServiceSource.includes("def metric_key_for(") &&
          metricFormulaCommandServiceSource.includes("def metric_row_to_payload(") &&
          metricFormulaCommandServiceSource.includes("def upsert_metric_definition(") &&
          metricFormulaCommandServiceSource.includes("def build_metric_add_plan(") &&
          metricFormulaCommandServiceSource.includes("def formula_key_for(") &&
          metricFormulaCommandServiceSource.includes("def calculated_field_row_to_payload(") &&
          metricFormulaCommandServiceSource.includes("def calculated_field_usage(") &&
          metricFormulaCommandServiceSource.includes("def compile_formula_for_table(") &&
          metricFormulaCommandServiceSource.includes("def build_formula_save_plan(") &&
          metricFormulaCommandServiceSource.includes("def execute_formula_save_plan(") &&
          metricFormulaCommandServiceSource.includes("def build_formula_metric_query(") &&
          !biCliSource.includes("INSERT INTO metric_definitions(") &&
          !biCliSource.includes("INSERT INTO calculated_fields(") &&
          !biCliSource.includes("\"sqlite-formula-metric\"") &&
          byLabel["cli-add-metric-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-query-metric"].parsed?.tableQuery?.rows?.some((row) => row.channel === "Douyin" && Number(row.sum_net_sales) === 3440) &&
          byLabel["cli-formula-preview"].parsed?.compiledSql?.includes("CASE WHEN") &&
          byLabel["cli-save-formula-confirm"].parsed?.confirmed === true &&
          byLabel["cli-delete-formula-confirm"].parsed?.confirmed === true,
      },
    {
        label: "connector-command-service-boundary",
        ok: existsSync(join(root, "tools", "connector_command_service.py")) &&
          biCliSource.includes("from connector_command_service import (") &&
          biCliSource.includes("list_connectors_command_service(") &&
          biCliSource.includes("save_connector_command_service(") &&
          biCliSource.includes("sync_connector_command_service(") &&
          biCliSource.includes("remove_connector_command_service(") &&
          connectorCommandServiceSource.includes("VALID_CONNECTOR_TYPES") &&
          connectorCommandServiceSource.includes("def connector_row_to_dict(") &&
          connectorCommandServiceSource.includes("def load_connectors(") &&
          connectorCommandServiceSource.includes("def connector_by_key_or_name(") &&
          connectorCommandServiceSource.includes("def list_connectors_command(") &&
          connectorCommandServiceSource.includes("def save_connector_command(") &&
          connectorCommandServiceSource.includes("def sync_connector_command(") &&
          connectorCommandServiceSource.includes("def remove_connector_command(") &&
          connectorCommandServiceSource.includes("INSERT OR REPLACE INTO data_connectors(") &&
          connectorCommandServiceSource.includes("DELETE FROM data_connectors WHERE connector_key = ?") &&
          connectorCommandServiceSource.includes("last_sync_status = 'blocked'") &&
          connectorCommandServiceSource.includes("last_sync_status = 'success'") &&
          !biCliSource.includes("INSERT OR REPLACE INTO data_connectors(") &&
          !biCliSource.includes("DELETE FROM data_connectors WHERE connector_key = ?") &&
          byLabel["cli-save-connector-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-save-connector-confirm"].parsed?.confirmed === true &&
          byLabel["cli-sync-connector-confirm"].parsed?.connectorSync?.importResult?.tableKey === "orders" &&
          byLabel["cli-sync-external-connector-blocked"].parsed?.blocked === true &&
          byLabel["cli-remove-connector-dry-run"].parsed?.requiresConfirmation === true,
      },
    {
        label: "import-job-command-service-boundary",
        ok: existsSync(join(root, "tools", "import_job_command_service.py")) &&
          biCliSource.includes("from import_job_command_service import (") &&
          biCliSource.includes("set_import_policy_command_service(") &&
          biCliSource.includes("list_import_jobs_command_service(") &&
          biCliSource.includes("remove_import_job_command_service(") &&
          importJobCommandServiceSource.includes("def set_import_policy_command(") &&
          importJobCommandServiceSource.includes("def list_import_jobs_command(") &&
          importJobCommandServiceSource.includes("def remove_import_job_command(") &&
          importJobCommandServiceSource.includes("INSERT OR REPLACE INTO import_policies(table_key, workspace_id, unique_fields_json, conflict_rule, updated_at)") &&
          importJobCommandServiceSource.includes("DELETE FROM import_jobs WHERE job_key = ? AND workspace_id = ?") &&
          !biCliSource.includes("INSERT OR REPLACE INTO import_policies(table_key, workspace_id, unique_fields_json, conflict_rule, updated_at)") &&
          !biCliSource.includes("DELETE FROM import_jobs WHERE job_key = ? AND workspace_id = ?") &&
          byLabel["cli-set-import-policy-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-set-import-policy-confirm"].parsed?.confirmed === true &&
          byLabel["cli-list-import-jobs"].parsed?.importJobs?.some((job) => job.table_key === "orders" && job.status === "success") &&
          byLabel["cli-remove-import-job-dry-run"].parsed?.requiresConfirmation === true,
      },
    {
        label: "import-command-service-boundary",
        ok: existsSync(join(root, "tools", "import_command_service.py")) &&
          biCliSource.includes("from import_command_service import (") &&
          biCliSource.includes("build_import_preview_service(") &&
          biCliSource.includes("preview_import_command_service(") &&
          biCliSource.includes("execute_import_commit_service(") &&
          biCliSource.includes("import_commit_command_service(") &&
          importCommandServiceSource.includes("def build_import_preview(") &&
          importCommandServiceSource.includes("def preview_import_command(") &&
          importCommandServiceSource.includes("def build_folder_import_plan(") &&
          importCommandServiceSource.includes("def preview_import_folder_command(") &&
          importCommandServiceSource.includes("def import_folder_command(") &&
          importCommandServiceSource.includes("def execute_import_commit(") &&
          importCommandServiceSource.includes("def import_commit_command(") &&
          importCommandServiceSource.includes("\"matchType\": \"exactOrder\"") &&
          importCommandServiceSource.includes("\"sourcePipelineContract\": source_pipeline_contract()") &&
          importCommandServiceSource.includes("\"mergePolicyPreview\"") &&
          importCommandServiceSource.includes("merge_import_into_table(") &&
          importCommandServiceSource.includes("import_csv_as_table(") &&
          importCommandServiceSource.includes("upsert_navigation_module(") &&
          importCommandServiceSource.includes("recommendedCommand") &&
          !biCliSource.includes("\"matchType\": \"exactOrder\"") &&
          byLabel["cli-preview-import"].parsed?.sourcePipelineContract?.stages?.length > 0 &&
          byLabel["cli-preview-import"].parsed?.mergePolicyPreview?.mergePlan?.incomingRows &&
          byLabel["cli-preview-import-folder"].parsed?.fileCount >= 2 &&
          byLabel["cli-preview-import-folder"].parsed?.tableCount >= 2 &&
          byLabel["cli-preview-import-folder"].parsed?.items?.length === byLabel["cli-preview-import-folder"].parsed?.fileCount &&
          byLabel["cli-preview-import-folder"].parsed?.groups?.length === byLabel["cli-preview-import-folder"].parsed?.tableCount &&
          byLabel["cli-import-folder-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-import-folder-dry-run"].parsed?.willWrite === false &&
          byLabel["cli-import-delete-source-validation-input"].parsed?.committed === true &&
          byLabel["cli-import-delete-source-validation-input"].parsed?.result?.tableKey === "verify_delete_source" &&
          byLabel["cli-agent-confirm-import"].parsed?.confirmed === true,
      },
    {
        label: "import-table-writer-service-boundary",
        ok: existsSync(join(root, "tools", "import_table_writer_service.py")) &&
          biCliSource.includes("from import_table_writer_service import (") &&
          biCliSource.includes("import_csv_as_table_service(") &&
          biCliSource.includes("merge_import_into_table_service(") &&
          biCliSource.includes("update_table_metadata_after_write_service(") &&
          biCliSource.includes("create_metrics_for_profile_service(") &&
          importTableWriterServiceSource.includes("def import_csv_as_table(") &&
          importTableWriterServiceSource.includes("def merge_import_into_table(") &&
          importTableWriterServiceSource.includes("def update_table_metadata_after_write(") &&
          importTableWriterServiceSource.includes("def create_metrics_for_profile(") &&
          importTableWriterServiceSource.includes("def should_create_metric_for_measure(") &&
          importTableWriterServiceSource.includes("def default_metric_dimension(") &&
          importTableWriterServiceSource.includes('not text.startswith("__")') &&
          importTableWriterServiceSource.includes("CREATE TABLE") &&
          importTableWriterServiceSource.includes("INSERT OR REPLACE INTO table_registry(") &&
          importTableWriterServiceSource.includes("INSERT OR REPLACE INTO source_runs(") &&
          importTableWriterServiceSource.includes("INSERT OR REPLACE INTO field_semantics(") &&
          importTableWriterServiceSource.includes("INSERT OR REPLACE INTO import_jobs(") &&
          importTableWriterServiceSource.includes("existing_rows_by_unique_key(") &&
          importTableWriterServiceSource.includes("\"writeSummary\"") &&
          importTableWriterServiceSource.includes("导入文件字段与目标表不匹配") &&
          byLabel["cli-import-delete-source-validation-input"].parsed?.committed === true &&
          byLabel["cli-import-delete-source-validation-input"].parsed?.result?.sourceRunId &&
          byLabel["cli-sync-connector-confirm"].parsed?.connectorSync?.importResult?.writeSummary?.rowCountAfter === 10 &&
          byLabel["cli-agent-confirm-import"].parsed?.importResult?.sourceRunId,
      },
    {
        label: "ui-real-import-folder-flow",
        ok: verifyUiRealImportSource.includes("const importFolder =") &&
          verifyUiRealImportSource.includes("const importTarget = existsSync(importFolder)") &&
          verifyUiRealImportSource.includes('data-testid="folder-import-preview-button"') &&
          verifyUiRealImportSource.includes('data-testid="folder-import-plan"') &&
          verifyUiRealImportSource.includes('data-testid="folder-import-confirm-button"') &&
          apiSourceApiSource.includes("function normalizeFolderImportPlan(") &&
          apiSourceApiSource.includes("Array.isArray(plan.groups) ? plan.groups : []") &&
          verifyUiRealImportSource.includes("api-folder-import-real-tables-merged") &&
          verifyUiRealImportSource.includes('rowCountsByName["保单明细"] === 426') &&
          verifyUiRealImportSource.includes('rowCountsByName["售后单"] === 1393') &&
          verifyUiRealImportSource.includes('rowCountsByName["订单"] === 2351') &&
          verifyUiRealImportSource.includes('rowCountsByName["资金"] === 1376') &&
          productAcceptanceMatrixDocSource.includes("real local folder when present or a real file as fallback"),
      },
    {
        label: "relationship-command-service-boundary",
        ok: existsSync(join(root, "tools", "relationship_command_service.py")) &&
          biCliSource.includes("from relationship_command_service import (") &&
          biCliSource.includes("list_relationships_command_service(") &&
          biCliSource.includes("query_relationship_command_service(") &&
          biCliSource.includes("relationship_preview_command_service(") &&
          biCliSource.includes("relationship_save_command_service(") &&
          biCliSource.includes("remove_relationship_command_service(") &&
          relationshipCommandServiceSource.includes("def list_relationships_command(") &&
          relationshipCommandServiceSource.includes("def normalize_relation_field_name(") &&
          relationshipCommandServiceSource.includes("def relation_candidate_fields(") &&
          relationshipCommandServiceSource.includes("def relationship_name_score(") &&
          relationshipCommandServiceSource.includes("def sample_field_values(") &&
          relationshipCommandServiceSource.includes("def saved_relationship_signatures(") &&
          relationshipCommandServiceSource.includes("def recommend_relationships_for_connection(") &&
          relationshipCommandServiceSource.includes("def recommend_relationships_command(") &&
          relationshipCommandServiceSource.includes("def resolve_relationship_query_inputs(") &&
          relationshipCommandServiceSource.includes("def parse_relationship_filter(") &&
          relationshipCommandServiceSource.includes("def relationship_rows_for_chart(") &&
          relationshipCommandServiceSource.includes("def query_relationship_command(") &&
          relationshipCommandServiceSource.includes("def remove_relationship_command(") &&
          relationshipCommandServiceSource.includes("def relationship_preview_command(") &&
          relationshipCommandServiceSource.includes("def build_relationship_save_plan(") &&
          relationshipCommandServiceSource.includes("def execute_relationship_save(") &&
          relationshipCommandServiceSource.includes("def relationship_save_command(") &&
          relationshipCommandServiceSource.includes("INSERT OR REPLACE INTO relationships(relation_key, workspace_id, name, left_table_key, right_table_key, left_field, right_field, join_type, confidence, created_at)") &&
          relationshipCommandServiceSource.includes("DELETE FROM relationships WHERE relation_key = ? AND workspace_id = ?") &&
          relationshipCommandServiceSource.includes("relationship whitelist join") &&
          relationshipCommandServiceSource.includes("sample-overlap:") &&
          relationshipCommandServiceSource.includes("shared-business-token:") &&
          relationshipCommandServiceSource.includes("actual_confidence < 0.55") &&
          relationshipCommandServiceSource.includes("min_distinct_keys < 3") &&
          relationshipCommandServiceSource.includes("join_multiplier > 5") &&
          biCliSource.includes("recommend_relationships_for_connection_service(") &&
          biCliSource.includes("recommend_relationships_command_service(") &&
          !biCliSource.includes("INSERT OR REPLACE INTO relationships(relation_key, workspace_id, name, left_table_key, right_table_key, left_field, right_field, join_type, confidence, created_at)") &&
          !biCliSource.includes("DELETE FROM relationships WHERE relation_key = ? AND workspace_id = ?") &&
          !biCliSource.includes("sample-overlap:") &&
          !biCliSource.includes("shared-business-token:") &&
          byLabel["cli-relationship-preview"].parsed?.relationshipPreview?.metrics?.confidence >= 0.8 &&
          byLabel["cli-relationship-save-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-list-relationships"].parsed?.relationships?.some((relationship) => relationship.relation_key === "orders_refunds_order_id_order_id") &&
          byLabel["cli-query-relationship"].parsed?.relationshipQuery?.joinType === "left" &&
          byLabel["cli-remove-relationship-dry-run"].parsed?.requiresConfirmation === true,
      },
    {
        label: "source-evidence-engine-renamed",
        ok: existsSync(join(root, "tools", "evidence_profile_runtime", "table_reading.py")) &&
          existsSync(join(root, "tools", "source_evidence_engine.py")) &&
          !existsSync(join(root, "tools", "source_intelligence")) &&
          !existsSync(join(root, "tools", "profile_generic_sources_duckdb.py")),
      },
    {
        label: "semantic-inference-production-guards",
        ok: biCliSource.includes("field == \"__canonical_date\"") &&
          biCliSource.includes("field.startswith(\"__source_\")") &&
          biCliSource.includes("\"filterable,no-groupable\"") &&
          biCliSource.includes("\"联系方式\"") &&
          biCliSource.includes("\"流水号\"") &&
          biCliSource.includes("\"分成\"") &&
          biCliSource.includes('str(field["field_name"]).startswith("__")') &&
          biCliSource.includes("def cleanup_stale_auto_metrics(") &&
          biCliSource.includes("removedStaleAutoMetrics") &&
          biCliSource.includes("source = 'auto'") &&
          biCliSource.includes("substr(measure, 1, 2) = '__'") &&
          biCliSource.includes('not str(field["field_name"]).startswith("__")') &&
          biCliSource.includes("not str(field).startswith(\"__\")") &&
          semanticTextSource.includes("\"contact_phone\"") &&
          semanticTextSource.includes("\"source_metadata\"") &&
          semanticTextSource.includes("ATTRIBUTE_SEMANTICS") &&
          semanticTextSource.includes("semantic.startswith(\"field_\") and inferred_type == \"number\" and unique_ratio > 0.75"),
      },
    {
        label: "source-intelligence-receipts-boundary",
        ok: existsSync(join(root, "tools", "evidence_receipts.py")) &&
          biCliSource.includes("from evidence_receipts import (") &&
          !biCliSource.includes("def build_source_intelligence_dashboard_candidate(") &&
          !biCliSource.includes("def source_intelligence_file_coverage(") &&
          !biCliSource.includes("def dashboard_chart_type_for_result(") &&
          sourceIntelligenceReceiptsSource.includes("def build_source_intelligence_dashboard_candidate(") &&
          sourceIntelligenceReceiptsSource.includes("def source_intelligence_file_coverage(") &&
          sourceIntelligenceReceiptsSource.includes("source-intelligence-receipts") &&
          sourceIntelligenceReceiptsSource.includes("metric-query-results.json") &&
          sourceIntelligenceReceiptsSource.includes("metric-sql-compiler.json"),
      },
    {
        label: "source-intelligence-run-store-boundary",
        ok: existsSync(join(root, "tools", "evidence_run_store.py")) &&
          biCliSource.includes("from evidence_run_store import (") &&
          biCliSource.includes("save_source_intelligence_run(") &&
          biCliSource.includes("list_source_intelligence_runs(") &&
          biCliSource.includes("include_internal=args.all") &&
          biCliSource.includes('source_intelligence_runs.add_argument("--all", action="store_true")') &&
          biCliSource.includes("count_source_intelligence_runs(") &&
          biCliSource.includes("latest_source_intelligence_summary(") &&
          biCliSource.includes("latest_source_intelligence_run(") &&
          biCliSource.includes("source_intelligence_run_manifest(") &&
          !biCliSource.includes("INSERT INTO source_intelligence_runs(") &&
          !biCliSource.includes("FROM source_intelligence_runs\n") &&
          sourceIntelligenceRunStoreSource.includes("def save_source_intelligence_run(") &&
          sourceIntelligenceRunStoreSource.includes("def list_source_intelligence_runs(") &&
          sourceIntelligenceRunStoreSource.includes("include_internal: bool = False") &&
          sourceIntelligenceRunStoreSource.includes('item["isInternal"] = internal_source_intelligence_run(item)') &&
          sourceIntelligenceRunStoreSource.includes("business_runs = [item for item in runs if not item[\"isInternal\"]]") &&
          sourceIntelligenceRunStoreSource.includes("def get_source_intelligence_run(") &&
          sourceIntelligenceRunStoreSource.includes("def latest_source_intelligence_run(") &&
          sourceIntelligenceRunStoreSource.includes("def latest_source_intelligence_run(connection: sqlite3.Connection, *, workspace_id: str, include_internal: bool = False)") &&
          sourceIntelligenceRunStoreSource.includes("return next((row for row in rows if not internal_source_intelligence_run(dict(row))), rows[0])") &&
          sourceIntelligenceRunStoreSource.includes("def latest_source_intelligence_summary(") &&
          sourceIntelligenceRunStoreSource.includes("include_internal: bool = False") &&
          sourceIntelligenceRunStoreSource.includes("def internal_source_intelligence_run(") &&
          sourceIntelligenceRunStoreSource.includes("manifestInputRoots") &&
          sourceIntelligenceRunStoreSource.includes("LIMIT 200") &&
          sourceIntelligenceRunStoreSource.includes("def source_intelligence_run_manifest(") &&
          sourceIntelligenceRunStoreSource.includes("def count_source_intelligence_runs(") &&
          byLabel["cli-source-intelligence-validation-inputs"].parsed?.runKey &&
          byLabel["cli-source-intelligence-runs-after-validation-input"].parsed?.sourceIntelligenceRuns?.some((run) =>
            run.run_key === byLabel["cli-source-intelligence-validation-inputs"].parsed?.runKey &&
            run.fileCoverage?.dashboardCandidate?.source === "source-intelligence-receipts"
          ),
      },
    {
        label: "source-intelligence-dashboard-draft-action-boundary",
        ok: byLabel["cli-source-dashboard-draft"].parsed?.requiresConfirmation === true &&
          byLabel["cli-source-dashboard-draft"].parsed?.actionDraft?.kind === "dashboard.create" &&
          byLabel["cli-source-dashboard-draft"].parsed?.source === "source-intelligence-dashboard-candidate" &&
          byLabel["cli-source-dashboard-draft"].parsed?.dashboardDraft?.source === "source-intelligence-dashboard-candidate" &&
          byLabel["cli-source-dashboard-draft"].parsed?.dashboardDraft?.widgets?.length >= 2 &&
          byLabel["cli-source-dashboard-draft"].parsed?.dashboardDraft?.widgets?.every((widget) =>
            widget.type === "text" &&
            widget.sourceRunKey &&
            widget.evidenceRefs?.some((ref) => String(ref).startsWith("source-intelligence:"))
          ) &&
          byLabel["cli-source-dashboard-confirm-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-source-dashboard-confirm-dry-run"].parsed?.dashboardDraft?.source === "source-intelligence-dashboard-candidate" &&
          byLabel["cli-source-dashboard-confirm"].parsed?.confirmed === true &&
          byLabel["cli-source-dashboard-after-confirm"].parsed?.dashboards?.some((dashboard) =>
            dashboard.dashboard_key === byLabel["cli-source-dashboard-confirm"].parsed?.createdDashboardKey &&
            dashboard.widgets?.some((widget) =>
              widget.widget_type === "text" &&
              widget.config?.sourceRunKey === byLabel["cli-source-dashboard-draft"].parsed?.sourceRunKey &&
              widget.config?.evidenceRefs?.some((ref) => String(ref).startsWith("source-intelligence:"))
            )
          ) &&
          !byLabel["cli-source-dashboard-action-drafts-after-confirm"].parsed?.actionDrafts?.some((draft) =>
            draft.action_key === byLabel["cli-source-dashboard-draft"].parsed?.actionDraft?.actionKey
          ) &&
          biCliSource.includes("def source_intelligence_dashboard_draft_command(") &&
          biCliSource.includes("from evidence_dashboard_drafts import build_source_intelligence_dashboard_draft") &&
          !biCliSource.includes("def build_source_intelligence_dashboard_draft(") &&
          !biCliSource.includes("def source_intelligence_dashboard_text(") &&
          sourceIntelligenceDashboardDraftsSource.includes("def build_source_intelligence_dashboard_draft(") &&
          sourceIntelligenceDashboardDraftsSource.includes("def source_intelligence_dashboard_text(") &&
          sourceIntelligenceDashboardDraftsSource.includes("preferred_table_key: Callable") &&
          sourceIntelligenceDashboardDraftsSource.includes("template_widget_layout: Callable") &&
          biCliSource.includes('source_dashboard_draft = sub.add_parser("source-dashboard-draft")') &&
          serverSourceRoutesSource.includes("/api/source-intelligence/dashboard-draft") &&
          apiSourceApiSource.includes("createSourceDashboardDraft") &&
          appMainViewSource.includes("onBusinessDashboardOperation={handleBusinessDashboardOperation}") &&
          appDataActionsSource.includes("const handleSourceDashboardDraft = useCallback") &&
          !homeOverviewSource.includes("onSourceDashboardDraft({") &&
          dashboardWidgetContractsSource.includes('"sourceRunKey"') &&
          dashboardModuleOrchestrationSource.includes('("sourceRunKey", "sourceRunKey")'),
      },
    {
        label: "dashboard-widget-contract-boundary",
        ok: existsSync(join(root, "tools", "dashboard_widget_contracts.py")) &&
          biCliSource.includes("from dashboard_widget_contracts import (") &&
          !biCliSource.includes("def widget_config_from_options(") &&
          !biCliSource.includes("def widget_style_options_from_args(") &&
          !biCliSource.includes("B_DASHBOARD_WIDGET_CATALOG = [") &&
          dashboardWidgetContractsSource.includes("B_DASHBOARD_WIDGET_CATALOG = [") &&
          dashboardWidgetContractsSource.includes("def build_dashboard_widget_catalog_payload(") &&
          dashboardWidgetContractsSource.includes("def widget_config_from_options(") &&
          dashboardWidgetContractsSource.includes("def widget_style_options_from_args(") &&
          dashboardWidgetContractsSource.includes("B_WIDGET_TYPES") &&
          dashboardWidgetContractsSource.includes("B_DASHBOARD_FILTER_OPERATORS"),
      },
    {
        label: "dashboard-widget-write-primitive-boundary",
        ok: existsSync(join(root, "tools", "dashboard_widget_operations.py")) &&
          biCliSource.includes("from dashboard_widget_operations import (") &&
          !biCliSource.includes("def insert_dashboard_widget(") &&
          dashboardWidgetOperationsSource.includes("def dashboard_widget_key_exists(") &&
          dashboardWidgetOperationsSource.includes("def resolve_dashboard_widget_key(") &&
          dashboardWidgetOperationsSource.includes("def next_dashboard_widget_sort_order(") &&
          dashboardWidgetOperationsSource.includes("def insert_dashboard_widget(") &&
          dashboardWidgetOperationsSource.includes("Dashboard widget insert requires workspace_id") &&
          byLabel["cli-save-dashboard-modules-dry-run"].parsed?.proposedWidgets?.every((widget) => widget.workspace_id),
      },
    {
        label: "dashboard-widget-proposal-service-boundary",
        ok: existsSync(join(root, "tools", "dashboard_widget_proposal_service.py")) &&
          biCliSource.includes("from dashboard_widget_proposal_service import (") &&
          biCliSource.includes("build_dashboard_widget_proposal_service(") &&
          biCliSource.includes("build_dashboard_relationship_widget_proposal_service(") &&
          !biCliSource.includes("raise ValueError(f\"Unsupported widget type: {widget_type}\")") &&
          !biCliSource.includes("raise ValueError(f\"Unsupported relationship widget type: {widget_type}\")") &&
          !biCliSource.includes("Relationship references an unavailable table.") &&
          dashboardWidgetProposalServiceSource.includes("def build_dashboard_widget_proposal(") &&
          dashboardWidgetProposalServiceSource.includes("def build_dashboard_relationship_widget_proposal(") &&
          dashboardWidgetProposalServiceSource.includes("widget_config_from_options") &&
          dashboardWidgetProposalServiceSource.includes("resolve_dashboard_widget_key") &&
          dashboardWidgetProposalServiceSource.includes("next_dashboard_widget_sort_order") &&
          byLabel["cli-add-widget-view-dry-run"].parsed?.proposedWidget?.config?.dataMode === "view" &&
          byLabel["cli-add-relationship-widget-dry-run"].parsed?.proposedWidget?.config?.dataMode === "relationship",
      },
    {
        label: "dashboard-widget-command-service-boundary",
        ok: existsSync(join(root, "tools", "dashboard_widget_command_service.py")) &&
          biCliSource.includes("from dashboard_widget_command_service import (") &&
          biCliSource.includes("add_recommended_dashboard_widgets_service(") &&
          biCliSource.includes("add_dashboard_widget_service(") &&
          biCliSource.includes("add_dashboard_relationship_widget_service(") &&
          biCliSource.includes("set_dashboard_widget_service(") &&
          biCliSource.includes("copy_dashboard_widget_service(") &&
          biCliSource.includes("remove_dashboard_widget_service(") &&
          !biCliSource.includes("same type/title/source already exists") &&
          !biCliSource.includes("SELECT * FROM dashboard_widgets WHERE widget_key = ? AND workspace_id = ?") &&
          dashboardWidgetCommandServiceSource.includes("def add_recommended_dashboard_widgets(") &&
          dashboardWidgetCommandServiceSource.includes("def add_dashboard_widget(") &&
          dashboardWidgetCommandServiceSource.includes("def add_dashboard_relationship_widget(") &&
          dashboardWidgetCommandServiceSource.includes("def set_dashboard_widget(") &&
          dashboardWidgetCommandServiceSource.includes("def copy_dashboard_widget(") &&
          dashboardWidgetCommandServiceSource.includes("def remove_dashboard_widget(") &&
          dashboardWidgetCommandServiceSource.includes("same type/title/source already exists") &&
          dashboardWidgetCommandServiceSource.includes("UPDATE dashboard_widgets") &&
          dashboardWidgetCommandServiceSource.includes("DELETE FROM dashboard_widgets WHERE widget_key = ? AND workspace_id = ?") &&
          byLabel["cli-add-recommended-widgets-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-add-widget-view-confirm"].parsed?.confirmed === true &&
          byLabel["cli-set-widget-style-confirm"].parsed?.confirmed === true &&
          byLabel["cli-copy-widget-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-remove-widget-dry-run"].parsed?.requiresConfirmation === true,
      },
    {
        label: "business-dashboard-service-boundary",
        ok: existsSync(join(root, "tools", "business_dashboard_service.py")) &&
          biCliSource.includes("from business_dashboard_service import (") &&
          biCliSource.includes("build_business_analysis_templates_service(") &&
          biCliSource.includes("build_business_dashboard_payload_service(") &&
          biCliSource.includes("write_business_dashboard_service(") &&
          biCliSource.includes("run_business_dashboard_command_service(") &&
          biCliSource.includes("build_agent_dashboard_create_draft_service(") &&
          !biCliSource.includes("def add_template(") &&
          !biCliSource.includes("经营复盘结论") &&
          !biCliSource.includes("No business dashboard templates are available for current sources.") &&
          businessDashboardServiceSource.includes("def template_widget_layout(") &&
          businessDashboardServiceSource.includes("def table_template_fields(") &&
          businessDashboardServiceSource.includes("def build_business_analysis_templates(") &&
          businessDashboardServiceSource.includes("def build_cost_monitor_templates(") &&
          businessDashboardServiceSource.includes("def build_business_dashboard_payload(") &&
          businessDashboardServiceSource.includes("def write_business_dashboard(") &&
          businessDashboardServiceSource.includes("def run_business_dashboard_command(") &&
          businessDashboardServiceSource.includes("def build_agent_dashboard_create_draft(") &&
          businessDashboardServiceSource.includes("COST_MONITOR_NET_FORMULA") &&
          businessDashboardServiceSource.includes("namespaced_dashboard_widget_id") &&
          businessDashboardServiceSource.includes("save_dashboard_with_widgets") &&
          byLabel["cli-business-dashboard-draft"].parsed?.templateCount >= 5 &&
          byLabel["cli-business-dashboard-create-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-business-dashboard-create-confirm"].parsed?.confirmed === true &&
          byLabel["cli-cost-monitor-dashboard-draft"].parsed?.draft?.templateKey === "cost-monitor" &&
          byLabel["cli-cost-monitor-dashboard-draft"].parsed?.templateCount >= 20 &&
          byLabel["cli-cost-monitor-dashboard-draft"].parsed?.draft?.widgets?.some((widget) => widget.title === "动账净额月度趋势") &&
          byLabel["cli-cost-monitor-dashboard-create-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-agent-confirm-dashboard-dry-run"].parsed?.proposedDashboard?.source === "business-dashboard",
      },
    {
        label: "erp-dashboard-unit-library",
        ok: existsSync(join(root, "tools", "erp_dashboard_unit_library.py")) &&
          existsSync(join(root, "scripts", "verify-erp-unit-library.mjs")) &&
          packageJson.scripts["verify:erp-units"] === "node scripts/verify-erp-unit-library.mjs" &&
          biCliSource.includes("from erp_dashboard_unit_library import (") &&
          biCliSource.includes('sub.add_parser("erp-unit-library")') &&
          biCliSource.includes('choices=["business", "cost-monitor", ERP_UNIT_LIBRARY_TEMPLATE_KEY]') &&
          businessDashboardServiceSource.includes("prompt_prefers_erp_unit_library(prompt)") &&
          businessDashboardServiceSource.includes("build_erp_dashboard_unit_templates(") &&
          erpDashboardUnitLibrarySource.includes('ERP_UNIT_LIBRARY_TEMPLATE_KEY = "erp-units"') &&
          erpDashboardUnitLibrarySource.includes("PUBLIC_ERP_REFERENCES") &&
          erpDashboardUnitLibrarySource.includes("ERP_DASHBOARD_UNITS") &&
          erpDashboardUnitLibrarySource.includes("ERP_FIELD_GROUP_LABELS") &&
          erpDashboardUnitLibrarySource.includes("def _unavailable_unit_hints(") &&
          erpDashboardUnitLibrarySource.includes("prompt_prefers_erp_unit_library") &&
          erpDashboardUnitLibrarySource.includes("not a fixed ERP dashboard template") &&
          businessDashboardServiceSource.includes('"erpUnitLibrary": erp_unit_library') &&
          businessDashboardServiceSource.includes('"erp-unit-library"') &&
          byLabel["cli-dashboard-widget-catalog"].parsed?.erpUnitLibrary?.unitCount >= 150 &&
          byLabel["cli-dashboard-widget-catalog"].parsed?.erpUnitLibrary?.referenceCount >= 45 &&
          byLabel["cli-erp-unit-library-summary"].parsed?.catalog?.fieldAliasGroupCount >= 240 &&
          byLabel["cli-erp-unit-library-selection"].parsed?.selection?.erpUnitLibrary?.selectedUnitCount > 0 &&
          byLabel["cli-erp-unit-library-selection"].parsed?.selection?.erpUnitLibrary?.unavailableUnitCount >= 0 &&
          Array.isArray(byLabel["cli-erp-unit-library-selection"].parsed?.selection?.erpUnitLibrary?.omittedUnitHints) &&
          byLabel["cli-business-dashboard-erp-units-draft"].parsed?.draft?.templateKey === "erp-units" &&
          byLabel["cli-business-dashboard-erp-units-draft"].parsed?.draft?.erpUnitLibrary?.selectedUnitCount > 0 &&
          Array.isArray(byLabel["cli-business-dashboard-erp-units-draft"].parsed?.draft?.erpUnitLibrary?.categoryCoverage) &&
          byLabel["cli-business-dashboard-erp-units-draft"].parsed?.draft?.widgets?.some((widget) => widget.erpUnitKey && widget.matchedFields) &&
          byLabel["cli-agent-erp-dashboard-draft"].parsed?.requiresConfirmation === true &&
          byLabel["cli-agent-erp-dashboard-draft"].parsed?.actionDraft?.kind === "dashboard.create" &&
          byLabel["cli-agent-action-drafts-before-confirm"].parsed?.actionDrafts?.some((draft) =>
            draft.action_key === byLabel["cli-agent-erp-dashboard-draft"].parsed?.actionDraft?.actionKey &&
            draft.payload?.dashboardDraft?.templateKey === "erp-units" &&
            draft.payload?.dashboardDraft?.erpUnitLibrary?.selectedUnitCount > 0 &&
            Array.isArray(draft.payload?.dashboardDraft?.erpUnitLibrary?.omittedUnitHints) &&
            Array.isArray(draft.payload?.dashboardDraft?.erpUnitLibrary?.categoryCoverage)
          ),
      },
    {
        label: "dashboard-module-orchestration-boundary",
        ok: existsSync(join(root, "tools", "dashboard_module_orchestration.py")) &&
          biCliSource.includes("from dashboard_module_orchestration import dashboard_module_widget_from_payload") &&
          !biCliSource.includes("def dashboard_module_widget_from_payload(") &&
          !biCliSource.includes("def namespaced_dashboard_widget_id(") &&
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
          biCliSource.includes("from dashboard_save_transactions import dashboard_snapshot, save_dashboard_with_widgets") &&
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
          biCliSource.includes("from bi_cli_core import (") &&
          !biCliSource.includes("def quote_identifier(name: str)") &&
          !biCliSource.includes("def source_label(path: Path | str)") &&
          biCliCoreSource.includes("def quote_identifier(name: str)") &&
          biCliCoreSource.includes("def source_label(path: Path | str)") &&
          biCliCoreSource.includes("A_PROJECT_ROOT") &&
          biCliCoreSource.includes("B_PROJECT_ROOT"),
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
        label: "verify-fixture-writer-boundary",
        ok: verifySource.includes('from "./verify/fixtures.mjs"') &&
          verifySource.includes("writeCostMonitorFixtures(verifyDataDir)") &&
          !verifySource.includes("write" + "FileSync(") &&
          verifyFixturesSource.includes("export function writeCostMonitorFixtures(verifyDataDir)") &&
          verifyFixturesSource.includes("cost-monitor-funds.csv") &&
          verifyFixturesSource.includes("cost-monitor-policy.csv") &&
          verifyFixturesSource.includes("write" + "FileSync("),
      },
    {
        label: "source-pipeline-rich-contract",
        ok: Array.isArray(byLabel["cli-preview-import"].parsed?.sourcePipelineContract?.stages) &&
          byLabel["cli-preview-import"].parsed.sourcePipelineContract.stages.every((stage) => stage.id && stage.outputEvidence) &&
          Array.isArray(byLabel["cli-preview-import"].parsed.sourcePipelineContract.domainPackRuntime?.semanticHints),
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
          biCliSource.includes("from source_read_model_service import (") &&
          biCliSource.includes("list_tables_command_service(") &&
          biCliSource.includes("inspect_table_command_service(") &&
          sourceReadModelServiceSource.includes("def list_tables_command(") &&
          sourceReadModelServiceSource.includes("def inspect_table_command(") &&
          sourceReadModelServiceSource.includes("SELECT table_key, workspace_id, display_name, physical_table, source_file, row_count, column_count, created_at") &&
          sourceReadModelServiceSource.includes("SELECT field_name, role, usage, confidence") &&
          sourceReadModelServiceSource.includes("SELECT metric_key, label, measure, aggregation, dimension, time_field, value_format") &&
          sourceReadModelServiceSource.includes("SELECT view_key, name, tag_name, is_default, sort_order, created_by, agent_managed") &&
          sourceReadModelServiceSource.includes("SELECT relation_key, name, left_table_key, right_table_key, left_field, right_field, join_type, confidence") &&
          sourceReadModelServiceSource.includes("SELECT job_key, workspace_id, source_file, mode, status, row_count, created_at") &&
          sourceReadModelServiceSource.includes("\"fieldConfig\"") &&
          sourceReadModelServiceSource.includes("\"importJobs\"") &&
          sourceReadModelServiceSource.includes("\"connectors\"") &&
          !biCliSource.includes("SELECT field_name, role, usage, confidence\n                FROM field_semantics") &&
          !biCliSource.includes("SELECT job_key, workspace_id, source_file, mode, status, row_count, created_at\n                FROM import_jobs") &&
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
          biCliSource.includes("from source_management_command_service import (") &&
          biCliSource.includes("rename_source_command_service(") &&
          biCliSource.includes("remaining_table_key_after_delete_service(") &&
          biCliSource.includes("build_delete_source_plan_service(") &&
          biCliSource.includes("delete_source_command_service(") &&
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
          !biCliSource.includes("\"affectedRelationshipKeys\": relation_keys") &&
          !biCliSource.includes("config[\"targetTableKey\"] = \"\"") &&
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
          !biCliSource.includes("from seed_orchestration_service import (") &&
          !biCliSource.includes("from seed_default_objects_service import (") &&
          !biCliSource.includes("ensure_seed_data(") &&
          !biCliSource.includes("ensure_default_import_policies(") &&
          !biCliSource.includes("create_default_views(connection)") &&
          !biCliSource.includes(retiredSeedEnvName) &&
          !biCliCoreSource.includes("FIXTURE_DIR") &&
          !importTableWriterServiceSource.includes('mode == "seed"') &&
          !sourceManagementCommandServiceSource.includes("seed_repair_disabled") &&
          verifySource.includes("verify-bootstrap-import-orders") &&
          verifyBiCliAgentContractSource.includes("verify-contract-bootstrap-import-orders") &&
          (biCliSource.match(/def table_columns\(/g) ?? []).length === 1 &&
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
          byLabel["cli-sync-connector-dry-run"].parsed?.proposedSync?.sourceExists === true &&
          byLabel["cli-sync-connector-confirm"].parsed?.confirmed === true &&
          byLabel["cli-sync-connector-confirm"].parsed?.connectorSync?.importResult?.tableKey === "orders" &&
          byLabel["cli-sync-external-connector-blocked"].parsed?.blocked === true &&
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
          indexHtmlSource.includes("readThemeFromWorkbench") &&
          indexHtmlSource.includes('request.open("GET", "/api/workbench?limit=1", false)') &&
          indexHtmlSource.includes("fallbackDarkTheme") &&
          indexHtmlSource.includes('window.matchMedia("(prefers-color-scheme: dark)")') &&
          indexHtmlSource.includes("root.dataset.themeMode = mode") &&
          indexHtmlSource.includes("root.style.colorScheme = mode") &&
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
          biCliSource.includes("from preferences_theme_command_service import (") &&
          biCliSource.includes("normalize_user_preferences_service(") &&
          biCliSource.includes("normalize_theme_tokens_service(") &&
          biCliSource.includes("normalize_theme_palette_service(") &&
          biCliSource.includes("validate_theme_palette_payload_service(") &&
          biCliSource.includes("ensure_default_preferences_and_themes_service(") &&
          biCliSource.includes("load_user_preferences_service(") &&
          biCliSource.includes("save_user_preferences_service(") &&
          biCliSource.includes("list_theme_palettes_service(") &&
          biCliSource.includes("upsert_theme_palette_service(") &&
          biCliSource.includes("delete_theme_palette_service(") &&
          biCliSource.includes("preferences_payload_service(") &&
          biCliSource.includes("preferences_command_service(") &&
          biCliSource.includes("theme_palettes_command_service(") &&
          !biCliSource.includes("DEFAULT_USER_PREFERENCES =") &&
          !biCliSource.includes("DEFAULT_THEME_PALETTES =") &&
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
          biCliSource.includes("from config_command_service import (") &&
          biCliSource.includes("redact_secret_value_service(") &&
          biCliSource.includes("restore_redacted_value_service(") &&
          biCliSource.includes("config_row_for_export_service(") &&
          biCliSource.includes("prepare_config_rows_for_restore_service(") &&
          biCliSource.includes("export_metadata_config_service(") &&
          biCliSource.includes("restore_config_rows_service(") &&
          biCliSource.includes("validate_metadata_config_service(") &&
          biCliSource.includes("validate_config_command_service(") &&
          biCliSource.includes("export_config_command_service(") &&
          biCliSource.includes("apply_config_command_service(") &&
          !biCliSource.includes("CONFIG_TABLES =") &&
          !biCliSource.includes("CONFIG_KIND =") &&
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
          biCliSource.includes("from workspace_command_service import (") &&
          biCliSource.includes("get_system_flag_service(") &&
          biCliSource.includes("set_system_flag_service(") &&
          biCliSource.includes("active_workspace_id_service(") &&
          biCliSource.includes("workspace_records_service(") &&
          biCliSource.includes("workspace_create_command_service(") &&
          biCliSource.includes("workspace_select_command_service(") &&
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
          biCliSource.includes("workspace_delete_command_service(") &&
          biCliSource.includes('workspace_delete = sub.add_parser("workspace-delete")') &&
          byLabel["cli-workspace-create-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-workspace-create-confirm"].parsed?.created?.id === "verify_workspace" &&
          byLabel["cli-workspace-select-dry-run"].parsed?.currentWorkspaceId === "default" &&
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
