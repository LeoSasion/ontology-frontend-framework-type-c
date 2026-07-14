import { appendCoreContractExtendedChecks } from "./coreContractsExtended.mjs";

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
        label: "native-bi-cli-agent-contract-boundary",
        ok: existsSync(join(root, "tools", "bi_cli_contracts.py")) &&
          existsSync(join(root, "tools", "bi_cli_envelope.py")) &&
          existsSync(join(root, "tools", "bi_cli_evidence_bundles.py")) &&
          existsSync(join(root, "scripts", "verify-bi-cli-agent-contract.mjs")) &&
          biCliRuntimeSource.includes("from bi_cli_contracts import") &&
          biCliRuntimeSource.includes("from bi_cli_envelope import enrich_cli_output, error_output") &&
          biCliRuntimeSource.includes("from bi_cli_evidence_bundles import artifact_ref, write_evidence_bundle") &&
          biCliRuntimeSource.includes("def cli_contract_command(") &&
          biCliRuntimeSource.includes("def list_commands_command(") &&
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
          biCliRuntimeSource.includes("from agent_prompt_resolution import (") &&
          !biCliRuntimeSource.includes("def prompt_mentions_widget_add(") &&
          !biCliRuntimeSource.includes("def prompt_mentions_dashboard_filter(") &&
          !biCliRuntimeSource.includes("def prompt_mentions_view_save(") &&
          !biCliRuntimeSource.includes("def dashboard_operation_from_prompt(") &&
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
          biCliRuntimeSource.includes("from agent_action_confirmations import (") &&
          !biCliRuntimeSource.includes("UPDATE action_drafts SET status = 'confirmed'") &&
          !biCliRuntimeSource.includes("UPDATE action_drafts SET status = 'rejected'") &&
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
          biCliRuntimeSource.includes("from agent_action_draft_store import") &&
          biCliRuntimeSource.includes("create_action_draft(") &&
          biCliRuntimeSource.includes("get_action_draft(") &&
          biCliRuntimeSource.includes("list_action_drafts(") &&
          biCliRuntimeSource.includes("count_pending_action_drafts(") &&
          biCliRuntimeSource.includes("action_draft_payload(") &&
          !biCliRuntimeSource.includes("INSERT INTO action_drafts(action_key, workspace_id, kind, label, status, payload_json, evidence_json, created_at)") &&
          !biCliRuntimeSource.includes("SELECT * FROM action_drafts") &&
          !biCliRuntimeSource.includes("SELECT COUNT(*) FROM action_drafts WHERE status = 'draft'") &&
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
          biCliRuntimeSource.includes("from agent_confirm_execution_handlers import (") &&
          biCliRuntimeSource.includes("return handle_index_create_confirmation(") &&
          biCliRuntimeSource.includes("return handle_relationship_save_confirmation(") &&
          biCliRuntimeSource.includes("return handle_import_commit_confirmation(") &&
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
          biCliRuntimeSource.includes("return handle_formula_save_confirmation(") &&
          biCliRuntimeSource.includes("return handle_view_save_confirmation(") &&
          biCliRuntimeSource.includes("return handle_metric_add_confirmation(") &&
          biCliRuntimeSource.includes("return handle_semantic_set_confirmation(") &&
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
          biCliRuntimeSource.includes("handle_dashboard_widget_add_confirmation(") &&
          biCliRuntimeSource.includes("create_confirmed_query_candidate(") &&
          biCliRuntimeSource.includes("return handle_dashboard_filter_add_confirmation(") &&
          biCliRuntimeSource.includes("return handle_dashboard_operation_confirmation(") &&
          biCliRuntimeSource.includes("handle_dashboard_create_confirmation(") &&
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
          biCliRuntimeSource.includes("from agent_recommended_commands import build_agent_recommended_commands") &&
          biCliRuntimeSource.includes("recommended = build_agent_recommended_commands(") &&
          !biCliRuntimeSource.includes("recommended.append(") &&
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
          biCliRuntimeSource.includes("from saved_view_query_service import (") &&
          biCliRuntimeSource.includes("query_table_command_service(") &&
          biCliRuntimeSource.includes("save_view_command_service(") &&
          biCliRuntimeSource.includes("copy_view_command_service(") &&
          biCliRuntimeSource.includes("delete_view_command_service(") &&
          biCliRuntimeSource.includes("build_save_view_plan_service(") &&
          biCliRuntimeSource.includes("execute_save_view_plan_service(") &&
          !biCliRuntimeSource.includes("def table_query_payload_from_args(") &&
          !biCliRuntimeSource.includes("def view_row_to_dict(") &&
          !biCliRuntimeSource.includes("SELECT * FROM saved_views WHERE view_key = ? AND table_key = ? AND workspace_id = ?") &&
          !biCliRuntimeSource.includes("DELETE FROM saved_views WHERE view_key = ? AND workspace_id = ?") &&
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
          biCliRuntimeSource.includes("from metric_formula_command_service import (") &&
          biCliRuntimeSource.includes("add_metric_command_service(") &&
          biCliRuntimeSource.includes("query_metric_command_service(") &&
          biCliRuntimeSource.includes("formula_preview_command_service(") &&
          biCliRuntimeSource.includes("save_formula_command_service(") &&
          biCliRuntimeSource.includes("delete_formula_command_service(") &&
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
          !biCliRuntimeSource.includes("INSERT INTO metric_definitions(") &&
          !biCliRuntimeSource.includes("INSERT INTO calculated_fields(") &&
          !biCliRuntimeSource.includes("\"sqlite-formula-metric\"") &&
          byLabel["cli-add-metric-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-query-metric"].parsed?.tableQuery?.rows?.some((row) => row.channel === "Douyin" && Number(row.sum_net_sales) === 3440) &&
          byLabel["cli-formula-preview"].parsed?.compiledSql?.includes("CASE WHEN") &&
          byLabel["cli-save-formula-confirm"].parsed?.confirmed === true &&
          byLabel["cli-delete-formula-confirm"].parsed?.confirmed === true,
      },
    {
        label: "connector-command-service-boundary",
        ok: existsSync(join(root, "tools", "connector_command_service.py")) &&
          biCliRuntimeSource.includes("from connector_command_service import (") &&
          biCliRuntimeSource.includes("list_connectors_command_service(") &&
          biCliRuntimeSource.includes("save_connector_command_service(") &&
          biCliRuntimeSource.includes("sync_connector_command_service(") &&
          biCliRuntimeSource.includes("remove_connector_command_service(") &&
          connectorCommandServiceSource.includes("VALID_CONNECTOR_TYPES") &&
          connectorCommandServiceSource.includes("def connector_row_to_dict(") &&
          connectorCommandServiceSource.includes("def load_connectors(") &&
          connectorCommandServiceSource.includes("def connector_by_key_or_name(") &&
          connectorCommandServiceSource.includes("def list_connectors_command(") &&
          connectorCommandServiceSource.includes("def save_connector_command(") &&
          connectorCommandServiceSource.includes("def sync_connector_command(") &&
          connectorCommandServiceSource.includes("def remove_connector_command(") &&
          connectorCommandServiceSource.includes("INSERT OR REPLACE INTO data_connectors(") &&
          connectorCommandServiceSource.includes("DELETE FROM data_connectors WHERE connector_key = ? AND workspace_id = ?") &&
          connectorCommandServiceSource.includes("build_sync_plan(") &&
          connectorCommandServiceSource.includes("public_sync_plan(") &&
          connectorCommandServiceSource.includes("last_sync_status = 'success'") &&
          !biCliRuntimeSource.includes("INSERT OR REPLACE INTO data_connectors(") &&
          !biCliRuntimeSource.includes("DELETE FROM data_connectors WHERE connector_key = ?") &&
          byLabel["cli-save-connector-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-save-connector-confirm"].parsed?.confirmed === true &&
          byLabel["cli-sync-connector-confirm"].parsed?.connectorSync?.importResult?.tableKey === "orders" &&
          byLabel["cli-sync-external-connector-blocked"].parsed?.ok === false &&
          byLabel["cli-remove-connector-dry-run"].parsed?.requiresConfirmation === true,
      },
    {
        label: "import-job-command-service-boundary",
        ok: existsSync(join(root, "tools", "import_job_command_service.py")) &&
          biCliRuntimeSource.includes("from import_job_command_service import (") &&
          biCliRuntimeSource.includes("set_import_policy_command_service(") &&
          biCliRuntimeSource.includes("list_import_jobs_command_service(") &&
          biCliRuntimeSource.includes("remove_import_job_command_service(") &&
          importJobCommandServiceSource.includes("def set_import_policy_command(") &&
          importJobCommandServiceSource.includes("def list_import_jobs_command(") &&
          importJobCommandServiceSource.includes("def remove_import_job_command(") &&
          importJobCommandServiceSource.includes("INSERT OR REPLACE INTO import_policies(table_key, workspace_id, unique_fields_json, conflict_rule, updated_at)") &&
          importJobCommandServiceSource.includes("DELETE FROM import_jobs WHERE job_key = ? AND workspace_id = ?") &&
          !biCliRuntimeSource.includes("INSERT OR REPLACE INTO import_policies(table_key, workspace_id, unique_fields_json, conflict_rule, updated_at)") &&
          !biCliRuntimeSource.includes("DELETE FROM import_jobs WHERE job_key = ? AND workspace_id = ?") &&
          byLabel["cli-set-import-policy-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-set-import-policy-confirm"].parsed?.confirmed === true &&
          byLabel["cli-list-import-jobs"].parsed?.importJobs?.some((job) => job.table_key === "orders" && job.status === "success") &&
          byLabel["cli-remove-import-job-dry-run"].parsed?.requiresConfirmation === true,
      },
    {
        label: "import-command-service-boundary",
        ok: existsSync(join(root, "tools", "import_command_service.py")) &&
          biCliRuntimeSource.includes("from import_command_service import (") &&
          biCliRuntimeSource.includes("build_import_preview_service(") &&
          biCliRuntimeSource.includes("preview_import_command_service(") &&
          biCliRuntimeSource.includes("execute_import_commit_service(") &&
          biCliRuntimeSource.includes("import_commit_command_service(") &&
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
          !biCliRuntimeSource.includes("\"matchType\": \"exactOrder\"") &&
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
          biCliRuntimeSource.includes("from import_table_writer_service import (") &&
          biCliRuntimeSource.includes("import_csv_as_table_service(") &&
          biCliRuntimeSource.includes("merge_import_into_table_service(") &&
          biCliRuntimeSource.includes("update_table_metadata_after_write_service(") &&
          biCliRuntimeSource.includes("create_metrics_for_profile_service(") &&
          importTableWriterServiceSource.includes("def import_csv_as_table(") &&
          importTableWriterServiceSource.includes("def merge_import_into_table(") &&
          importTableWriterServiceSource.includes("def update_table_metadata_after_write(") &&
          importTableWriterServiceSource.includes("def create_metrics_for_profile(") &&
          importTableWriterServiceSource.includes("def should_create_metric_for_measure(") &&
          importTableWriterServiceSource.includes("def default_metric_dimension(") &&
          importTableWriterServiceSource.includes('not text.startswith("__")') &&
          importTableWriterServiceSource.includes("CREATE TABLE") &&
          importTableWriterServiceSource.includes("def upsert_table_registry_record(") &&
          importTableWriterServiceSource.includes("ON CONFLICT(workspace_id, table_key) DO UPDATE SET") &&
          importTableWriterServiceSource.includes("def revalidate_relationships_for_table(") &&
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
        label: "ui-real-import-generic-single-chart-flow",
        ok: verifyUiRealImportSource.includes("const configuredPath =") &&
          verifyUiRealImportSource.includes("const detectedMode =") &&
          verifyUiRealImportSource.includes("real-import-uses-production-data") &&
          verifyUiRealImportSource.includes("real-import-domain-declared") &&
          verifyUiRealImportSource.includes('data-testid="folder-import-preview-button"') &&
          verifyUiRealImportSource.includes('data-testid="folder-import-plan"') &&
          verifyUiRealImportSource.includes('data-testid="folder-import-confirm-button"') &&
          apiSourceApiSource.includes("function normalizeFolderImportPlan(") &&
          apiSourceApiSource.includes("Array.isArray(plan.groups) ? plan.groups : []") &&
          verifyUiRealImportSource.includes("api-known-financial-folder-deduplicated") &&
          verifyUiRealImportSource.includes("automatic source intelligence count") &&
          verifyUiRealImportSource.includes("ui-import-continues-to-evidence-automatically") &&
          verifyUiRealImportSource.includes("ui-manual-evidence-path-is-secondary") &&
          verifyUiRealImportSource.includes('rowCountsByName["保单明细"] === 426') &&
          verifyUiRealImportSource.includes('rowCountsByName["售后单"] === 1393') &&
          verifyUiRealImportSource.includes('rowCountsByName["订单"] === 2351') &&
          verifyUiRealImportSource.includes('rowCountsByName["资金"] === 1376') &&
          verifyUiRealImportSource.includes("ui-first-chart-prompt-is-empty-by-default") &&
          verifyUiRealImportSource.includes("api-single-chart-dashboard-created") &&
          productAcceptanceMatrixDocSource.includes("external real file or folder"),
      },
    {
        label: "relationship-command-service-boundary",
        ok: existsSync(join(root, "tools", "relationship_command_service.py")) &&
          biCliRuntimeSource.includes("from relationship_command_service import (") &&
          biCliRuntimeSource.includes("list_relationships_command_service(") &&
          biCliRuntimeSource.includes("query_relationship_command_service(") &&
          biCliRuntimeSource.includes("relationship_preview_command_service(") &&
          biCliRuntimeSource.includes("relationship_save_command_service(") &&
          biCliRuntimeSource.includes("remove_relationship_command_service(") &&
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
          relationshipCommandServiceSource.includes("mappings_json, filters_json, preaggregation_json, join_type, confidence, validation_json, created_at, updated_at") &&
          relationshipCommandServiceSource.includes("def relationship_record_payload(") &&
          relationshipCommandServiceSource.includes("def relationship_validation_snapshot(") &&
          relationshipCommandServiceSource.includes("DELETE FROM relationships WHERE relation_key = ? AND workspace_id = ?") &&
          relationshipCommandServiceSource.includes("relationship whitelist join") &&
          relationshipCommandServiceSource.includes("sample-overlap:") &&
          relationshipCommandServiceSource.includes("shared-business-token:") &&
          relationshipCommandServiceSource.includes("actual_confidence < 0.55") &&
          relationshipCommandServiceSource.includes("min_distinct_keys < 3") &&
          relationshipCommandServiceSource.includes("join_multiplier > 5") &&
          biCliRuntimeSource.includes("recommend_relationships_for_connection_service(") &&
          biCliRuntimeSource.includes("recommend_relationships_command_service(") &&
          !biCliRuntimeSource.includes("mappings_json, filters_json, preaggregation_json, join_type, confidence, validation_json, created_at, updated_at") &&
          !biCliRuntimeSource.includes("DELETE FROM relationships WHERE relation_key = ? AND workspace_id = ?") &&
          !biCliRuntimeSource.includes("sample-overlap:") &&
          !biCliRuntimeSource.includes("shared-business-token:") &&
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
        ok: biCliRuntimeSource.includes("field == \"__canonical_date\"") &&
          biCliRuntimeSource.includes("field.startswith(\"__source_\")") &&
          biCliRuntimeSource.includes("\"filterable,no-groupable\"") &&
          biCliRuntimeSource.includes("\"联系方式\"") &&
          biCliRuntimeSource.includes("\"流水号\"") &&
          biCliRuntimeSource.includes("\"分成\"") &&
          biCliRuntimeSource.includes('str(field["field_name"]).startswith("__")') &&
          biCliRuntimeSource.includes("def cleanup_stale_auto_metrics(") &&
          biCliRuntimeSource.includes("removedStaleAutoMetrics") &&
          biCliRuntimeSource.includes("source = 'auto'") &&
          biCliRuntimeSource.includes("substr(measure, 1, 2) = '__'") &&
          biCliRuntimeSource.includes('not str(field["field_name"]).startswith("__")') &&
          biCliRuntimeSource.includes("not str(field).startswith(\"__\")") &&
          semanticTextSource.includes("\"contact_phone\"") &&
          semanticTextSource.includes("\"source_metadata\"") &&
          semanticTextSource.includes("ATTRIBUTE_SEMANTICS") &&
          semanticTextSource.includes("semantic.startswith(\"field_\") and inferred_type == \"number\" and unique_ratio > 0.75"),
      },
    {
        label: "source-intelligence-receipts-boundary",
        ok: existsSync(join(root, "tools", "evidence_receipts.py")) &&
          biCliRuntimeSource.includes("from evidence_receipts import (") &&
          !biCliRuntimeSource.includes("def build_source_intelligence_dashboard_candidate(") &&
          !biCliRuntimeSource.includes("def source_intelligence_file_coverage(") &&
          !biCliRuntimeSource.includes("def dashboard_chart_type_for_result(") &&
          sourceIntelligenceReceiptsSource.includes("def build_source_intelligence_dashboard_candidate(") &&
          sourceIntelligenceReceiptsSource.includes("def source_intelligence_file_coverage(") &&
          sourceIntelligenceReceiptsSource.includes("source-intelligence-receipts") &&
          sourceIntelligenceReceiptsSource.includes("metric-query-results.json") &&
          sourceIntelligenceReceiptsSource.includes("metric-sql-compiler.json"),
      },
    {
        label: "source-intelligence-run-store-boundary",
        ok: existsSync(join(root, "tools", "evidence_run_store.py")) &&
          biCliRuntimeSource.includes("from evidence_run_store import (") &&
          biCliRuntimeSource.includes("save_source_intelligence_run(") &&
          biCliRuntimeSource.includes("list_source_intelligence_runs(") &&
          biCliRuntimeSource.includes("include_internal=args.all") &&
          biCliRuntimeSource.includes('source_intelligence_runs.add_argument("--all", action="store_true")') &&
          biCliRuntimeSource.includes("count_source_intelligence_runs(") &&
          biCliRuntimeSource.includes("latest_source_intelligence_summary(") &&
          biCliRuntimeSource.includes("latest_source_intelligence_run(") &&
          biCliRuntimeSource.includes("source_intelligence_run_manifest(") &&
          !biCliRuntimeSource.includes("INSERT INTO source_intelligence_runs(") &&
          !biCliRuntimeSource.includes("FROM source_intelligence_runs\n") &&
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
          biCliRuntimeSource.includes("def source_intelligence_dashboard_draft_command(") &&
          biCliRuntimeSource.includes("from evidence_dashboard_drafts import build_source_intelligence_dashboard_draft") &&
          !biCliRuntimeSource.includes("def build_source_intelligence_dashboard_draft(") &&
          !biCliRuntimeSource.includes("def source_intelligence_dashboard_text(") &&
          sourceIntelligenceDashboardDraftsSource.includes("def build_source_intelligence_dashboard_draft(") &&
          sourceIntelligenceDashboardDraftsSource.includes("def source_intelligence_dashboard_text(") &&
          sourceIntelligenceDashboardDraftsSource.includes("preferred_table_key: Callable") &&
          sourceIntelligenceDashboardDraftsSource.includes("template_widget_layout: Callable") &&
          biCliRuntimeSource.includes('source_dashboard_draft = sub.add_parser("source-dashboard-draft")') &&
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
          biCliRuntimeSource.includes("from dashboard_widget_contracts import (") &&
          !biCliRuntimeSource.includes("def widget_config_from_options(") &&
          !biCliRuntimeSource.includes("def widget_style_options_from_args(") &&
          !biCliRuntimeSource.includes("B_DASHBOARD_WIDGET_CATALOG = [") &&
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
          biCliRuntimeSource.includes("from dashboard_widget_operations import (") &&
          !biCliRuntimeSource.includes("def insert_dashboard_widget(") &&
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
          biCliRuntimeSource.includes("from dashboard_widget_proposal_service import (") &&
          biCliRuntimeSource.includes("build_dashboard_widget_proposal_service(") &&
          biCliRuntimeSource.includes("build_dashboard_relationship_widget_proposal_service(") &&
          !biCliRuntimeSource.includes("raise ValueError(f\"Unsupported widget type: {widget_type}\")") &&
          !biCliRuntimeSource.includes("raise ValueError(f\"Unsupported relationship widget type: {widget_type}\")") &&
          !biCliRuntimeSource.includes("Relationship references an unavailable table.") &&
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
          biCliRuntimeSource.includes("from dashboard_widget_command_service import (") &&
          biCliRuntimeSource.includes("add_recommended_dashboard_widgets_service(") &&
          biCliRuntimeSource.includes("add_dashboard_widget_service(") &&
          biCliRuntimeSource.includes("add_dashboard_relationship_widget_service(") &&
          biCliRuntimeSource.includes("set_dashboard_widget_service(") &&
          biCliRuntimeSource.includes("copy_dashboard_widget_service(") &&
          biCliRuntimeSource.includes("remove_dashboard_widget_service(") &&
          !biCliRuntimeSource.includes("same type/title/source already exists") &&
          !biCliRuntimeSource.includes("SELECT * FROM dashboard_widgets WHERE widget_key = ? AND workspace_id = ?") &&
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
          biCliRuntimeSource.includes("from business_dashboard_service import (") &&
          biCliRuntimeSource.includes("build_business_analysis_templates_service(") &&
          biCliRuntimeSource.includes("build_business_dashboard_payload_service(") &&
          biCliRuntimeSource.includes("write_business_dashboard_service(") &&
          biCliRuntimeSource.includes("run_business_dashboard_command_service(") &&
          biCliRuntimeSource.includes("build_agent_dashboard_create_draft_service(") &&
          !biCliRuntimeSource.includes("def add_template(") &&
          !biCliRuntimeSource.includes("经营复盘结论") &&
          !biCliRuntimeSource.includes("No business dashboard templates are available for current sources.") &&
          businessDashboardServiceSource.includes("def template_widget_layout(") &&
          businessDashboardServiceSource.includes("def table_template_fields(") &&
          businessDashboardServiceSource.includes("def build_business_analysis_templates(") &&
          businessDashboardServiceSource.includes("def build_business_dashboard_payload(") &&
          businessDashboardServiceSource.includes("def write_business_dashboard(") &&
          businessDashboardServiceSource.includes("def run_business_dashboard_command(") &&
          businessDashboardServiceSource.includes("def build_agent_dashboard_create_draft(") &&
          businessDashboardServiceSource.includes("from business_dashboard_templates import (") &&
          businessDashboardTemplatesSource.includes("def source_profile_table_inputs(") &&
          businessDashboardTemplatesSource.includes("def table_fields_by_key(") &&
          businessDashboardTemplatesSource.includes("def build_cost_monitor_templates(") &&
          businessDashboardTemplatesSource.includes("COST_MONITOR_NET_FORMULA") &&
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
          biCliRuntimeSource.includes("from erp_dashboard_unit_library import (") &&
          biCliRuntimeSource.includes('sub.add_parser("erp-unit-library")') &&
          biCliRuntimeSource.includes('choices=["business", "cost-monitor", ERP_UNIT_LIBRARY_TEMPLATE_KEY]') &&
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
  );
  appendCoreContractExtendedChecks(context);
}
