import { appendSourceContractExtendedChecks } from "./sourceContractsExtended.mjs";

export function appendSourceContractChecks(context) {
  const {
    checks,
    agentPanelModelSource,
    agentPanelSource,
    agentPromptGridSource,
    apiClientSource,
    apiSourceApiSource,
    appDataActionsSource,
    appSource: appEntrySource,
    appMainViewSource,
    bDashboardDrilldownSheetSource,
    bDashboardWidgetCardSource,
    biCliSource,
    biDashboardModelSource,
    biDashboardPresentationSource,
    biDashboardRuntimeSource,
    biDashboardValueModelSource,
    biDashboardWidgetFactorySource,
    businessPathBarSource,
    businessPathModelSource,
    bWidgetKitModelSource,
    bWidgetKitOverviewSource,
    bWidgetKitSource,
    bWidgetModelSource,
    byLabel,
    dashboardAdvancedWidgetWorkbenchSource,
    dashboardBusinessTaskStripSource,
    dashboardBusinessTemplatePanelSource,
    dashboardCanvasActionsSource,
    dashboardCanvasContractsSource,
    dashboardCanvasEditorOptionsSource,
    dashboardCanvasSource,
    dashboardCanvasSourceSwitchModelSource,
    dashboardCanvasStateSource,
    dashboardCanvasSummaryModelSource,
    dashboardCanvasViewModelSource,
    dashboardCanvasWidgetModelSource,
    dashboardFilterWorkbenchSource,
    dashboardOverviewStripSource,
    dashboardPageAdminPanelSource,
    dashboardRelationshipRecommendationPanelSource,
    dashboardWidgetBasicFormSource,
    dashboardWidgetEditorPanelSource,
    dashboardWidgetLifecyclePanelSource,
    dashboardWidgetLocalFilterPanelSource,
    dashboardWidgetManagePanelSource,
    dashboardWidgetStylePanelSource,
    evidenceViewModelSource,
    evidenceViewSource,
    existsSync,
    globalStylesSource,
    hasCssRule,
    homeActionDockSource,
    homeOperatingSummaryPanelSource,
    homeOverviewSource,
    homeProductIntelligencePanelSource,
    implementationStatusSource,
    inspectorControllerSource,
    inspectorPanelModelSource,
    join,
    metricSemanticRepairActionsSource,
    relationshipAutoModelGraphModelSource,
    relationshipAutoModelGraphSource,
    root,
    run,
    serverDashboardRoutesSource,
    serverSourceRoutesSource,
    sidebarAssetSectionsSource,
    sourceCoverageAllRuns,
    sourceCoverageRuns,
    sourceIntelligenceRunModelSource,
    sourceWorkbenchActionPanelSource,
    sourceWorkbenchAdvancedModulesSource,
    sourceWorkbenchDeferredModulesSource,
    sourceWorkbenchAdvancedPanelsSource,
    sourceWorkbenchAdvancedStylesSource,
    sourceWorkbenchAgentStarterSource,
    sourceWorkbenchCommandModelSource,
    sourceWorkbenchConnectorControllerSource,
    sourceWorkbenchConnectorPanelSource,
    sourceWorkbenchContractsSource,
    sourceWorkbenchDataEntryPanelSource,
    sourceWorkbenchDataManagementPanelSource,
    sourceWorkbenchDraftModelSource,
    sourceWorkbenchFieldMetricPanelSource,
    sourceWorkbenchFieldMetricTypesSource,
    sourceWorkbenchFieldSemanticPanelSource,
    sourceWorkbenchGuidanceModelSource,
    sourceWorkbenchHeaderSource,
    sourceWorkbenchImportControllerSource,
    sourceWorkbenchImportPanelSource,
    sourceWorkbenchMetricDefinitionPanelSource,
    sourceWorkbenchModelSource,
    sourceWorkbenchOperationsPanelSource,
    sourceWorkbenchQueryFormulaPanelSource,
    sourceWorkbenchReceiptModelSource,
    sourceWorkbenchRelationshipPanelSource,
    sourceWorkbenchSource,
    stylesSource,
  } = context;
  const appSource = `${appEntrySource}\n${appMainViewSource}\n${inspectorControllerSource}`;
  checks.push(
    {
        label: "workbench-surface-complete",
        ok: Boolean(
          byLabel["cli-workbench"].parsed?.tables?.length &&
          byLabel["cli-workbench"].parsed?.fields?.length &&
          byLabel["cli-workbench"].parsed?.metrics?.length &&
          byLabel["cli-workbench"].parsed?.relationshipRecommendations?.some((recommendation) => recommendation.leftTableKey === "orders" && recommendation.rightTableKey === "refunds") &&
          byLabel["cli-workbench-after-connectors"].parsed?.connectors?.some((connector) => connector.connectorKey === "verify_file_connector") &&
          byLabel["cli-workbench-after-connectors"].parsed?.preferences?.themeKey &&
          byLabel["cli-workbench-after-connectors"].parsed?.themePalettes?.some((theme) => theme.themeKey === "L1") &&
          byLabel["cli-workbench"].parsed?.savedViews?.length &&
          byLabel["cli-workbench"].parsed?.navigation?.some((module) => module.moduleKey === "table:orders") &&
          Array.isArray(byLabel["cli-workbench"].parsed?.safeAggregations),
        ),
      },
    {
        label: "source-intelligence-file-coverage-contract",
        ok: sourceCoverageRuns.some((run) =>
          run.label === "verify-validation-inputs-source-intelligence" &&
          run.fileCoverage?.sourceFileCount === run.source_count &&
          run.fileCoverage?.manifestSourceCount === run.source_count &&
          run.fileCoverage?.filesBySourceGroup?.length >= 1 &&
          run.fileCoverage?.skippedTableCount === 0 &&
          run.fileCoverage?.complete === true,
        ) &&
          sourceCoverageAllRuns.some((run) => run.label === "verify-validation-inputs-source-intelligence" && run.isInternal === true) &&
          byLabel["cli-workbench"].parsed?.sourceIntelligenceRuns?.some((run) => run.fileCoverage?.sourceFileCount === run.source_count) &&
          sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-coverage-item"') &&
          sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-coverage-groups"') &&
          !sourceWorkbenchDataEntryPanelSource.includes("filesByMonth") &&
          sourceWorkbenchDataEntryPanelSource.includes("run.isInternal") &&
          sourceWorkbenchDataEntryPanelSource.includes("系统检查") &&
          sourceWorkbenchDataEntryPanelSource.includes("fileCoverage"),
      },
    {
        label: "source-workbench-folder-profile-entry",
        ok: sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-folder-entry"') &&
          sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-custom-run-button"') &&
          sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-open-import-button"') &&
          !sourceWorkbenchDataEntryPanelSource.includes("aTestdata") &&
          !sourceWorkbenchDataEntryPanelSource.includes("样例") &&
          !sourceWorkbenchDataEntryPanelSource.includes("sample data") &&
          sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-progress"') &&
          sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-result"') &&
          sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-error"') &&
          sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-recovery"') &&
          sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-recovery-steps"') &&
          sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-recovery-business-hint"') &&
          sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-business-impact"') &&
          sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-next-step"') &&
          sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-technical-details"') &&
          sourceWorkbenchDataEntryPanelSource.includes('data-testid="source-intelligence-result-technical-details"') &&
          sourceWorkbenchCommandModelSource.includes("splitInputPaths") &&
          sourceWorkbenchSource.includes("sourceProfileOptions") &&
          sourceWorkbenchSource.includes("runSourceProfile") &&
          sourceWorkbenchDataEntryPanelSource.includes("sourceProfileSummary") &&
          sourceWorkbenchDataEntryPanelSource.includes("sourceProfileBusinessStatus") &&
          sourceWorkbenchDataEntryPanelSource.includes("sourceProfileRecovery") &&
          sourceWorkbenchDataEntryPanelSource.includes("让 Agent 看看") &&
          sourceWorkbenchDataEntryPanelSource.includes("技术错误") &&
          stylesSource.includes(".sourceProfileRecovery") &&
          stylesSource.includes(".sourceProfileRecoveryActions") &&
          stylesSource.includes(".sourceProfileBusinessHint") &&
          stylesSource.includes(".sourceProfileSuccessBody") &&
          stylesSource.includes(".sourceProfileTechnicalError") &&
          sourceWorkbenchCommandModelSource.includes("inputs: splitInputPaths(sourceProfileInputs)") &&
          apiClientSource.includes("export async function fetchJsonStrict") &&
          apiClientSource.includes("export class ApiPayloadError extends Error") &&
          apiClientSource.includes("let lastError: unknown = null") &&
          apiClientSource.includes("throw lastError") &&
          apiClientSource.includes("throw new Error(`Local API request failed for ${path}: ${message}`)") &&
          apiSourceApiSource.includes("return fetchJsonStrict<SourceIntelligenceRunResponse>(\"/api/source-intelligence/run\"") &&
          appDataActionsSource.includes("const { stayOnPage = false, inputs = [], ...sourceOptions }") &&
          appDataActionsSource.includes("const hasInputs = inputs.length > 0") &&
          appDataActionsSource.includes("请先在数据源工作台选择本地文件或文件夹") &&
          appDataActionsSource.includes("return result;") &&
          byLabel["cli-source-intelligence-validation-inputs"].parsed?.manifest?.sourceCount >= 2,
      },
    {
        label: "source-workbench-data-entry-panel-boundary",
        ok: existsSync(join(root, "src", "components", "SourceWorkbenchDataEntryPanel.tsx")) &&
          sourceWorkbenchSource.includes('import { SourceWorkbenchDataEntryPanel } from "./SourceWorkbenchDataEntryPanel"') &&
          !sourceWorkbenchDeferredModulesSource.includes("SourceWorkbenchDataEntryPanel") &&
          sourceWorkbenchSource.includes("<SourceWorkbenchDataEntryPanel") &&
          !sourceWorkbenchSource.includes('data-testid="source-intelligence-folder-entry"') &&
          !sourceWorkbenchSource.includes("const aTestdataMonths") &&
          !sourceWorkbenchSource.includes("sourceProfileBusinessStatus(sourceProfileResult)") &&
          sourceWorkbenchDataEntryPanelSource.includes("type SourceWorkbenchDataEntryPanelProps") &&
          sourceWorkbenchDataEntryPanelSource.includes('from "../sourceIntelligenceRunModel"') &&
          !sourceWorkbenchDataEntryPanelSource.includes("aTestdata0305SourceIntelligenceOptions()") &&
          !sourceWorkbenchDataEntryPanelSource.includes("type SourceIntelligenceRunOptions =") &&
          sourceWorkbenchDataEntryPanelSource.includes("sourceProfileOptions: () => SourceIntelligenceRunOptions") &&
          sourceWorkbenchDataEntryPanelSource.includes("runSourceProfile: (label: string, options: SourceIntelligenceRunOptions) => Promise<void>") &&
          sourceWorkbenchDataEntryPanelSource.includes("onAsk: (prompt: string) => Promise<void>") &&
          sourceWorkbenchDataEntryPanelSource.includes("SourceIntelligenceRunSummary") &&
          sourceWorkbenchDataEntryPanelSource.includes("sourceProfileRecovery(sourceProfileError, sourceProfileInputs)") &&
          sourceWorkbenchDataEntryPanelSource.includes("sourceIntelligenceRuns.slice(0, 4)"),
      },
    {
        label: "source-workbench-header-boundary",
        ok: existsSync(join(root, "src", "components", "SourceWorkbenchHeader.tsx")) &&
          sourceWorkbenchSource.includes('import { SourceWorkbenchHeader } from "./SourceWorkbenchHeader"') &&
          sourceWorkbenchSource.includes("<SourceWorkbenchHeader") &&
          !sourceWorkbenchSource.includes('data-testid="import-preview-button"') &&
          !sourceWorkbenchSource.includes('data-testid="source-intelligence-run-button"') &&
          sourceWorkbenchHeaderSource.includes("type SourceWorkbenchHeaderProps") &&
          !sourceWorkbenchHeaderSource.includes('data-testid="import-preview-button"') &&
          !sourceWorkbenchHeaderSource.includes('data-testid="import-dry-run-button"') &&
          !sourceWorkbenchHeaderSource.includes('data-testid="import-confirm-button"') &&
          sourceWorkbenchImportPanelSource.includes('data-testid="import-preview-button"') &&
          sourceWorkbenchImportPanelSource.includes('data-testid="import-confirmation-preview"') &&
          sourceWorkbenchImportPanelSource.includes('data-testid="import-confirmation-confirm"') &&
          !sourceWorkbenchHeaderSource.includes('data-testid="source-intelligence-run-button"') &&
          !sourceWorkbenchHeaderSource.includes("SOURCE_INTELLIGENCE_A_TESTDATA_COMMAND") &&
          !sourceWorkbenchHeaderSource.includes("aTestdata0305SourceIntelligenceOptions()") &&
          sourceWorkbenchHeaderSource.includes('aria-live="polite"') &&
          sourceWorkbenchImportPanelSource.includes('data-testid="import-operation-receipt" role="status"') &&
          sourceWorkbenchImportPanelSource.includes("导入去重规则") &&
          sourceWorkbenchActionPanelSource.includes("数据模型与管理") &&
          !sourceWorkbenchSource.includes('data-testid="source-expert-details"') &&
          sourceWorkbenchHeaderSource.includes("先导入或选择本地数据路径"),
      },
    {
        label: "source-workbench-model-boundary",
        ok: existsSync(join(root, "src", "sourceWorkbenchModel.ts")) &&
          (sourceWorkbenchSource.includes('from "../sourceWorkbenchModel"') || sourceWorkbenchSource.includes('from "./sourceWorkbenchModel"')) &&
          sourceWorkbenchSource.includes("useMemo(() => buildFieldSemanticReadiness(selectedFields)") &&
          !sourceWorkbenchSource.includes("function confidencePercent(") &&
          !sourceWorkbenchSource.includes("function sourceProfileRecovery(") &&
          !sourceWorkbenchSource.includes("function buildFieldSemanticReadiness(") &&
          !sourceWorkbenchSource.includes("function sourceProfileBusinessStatus(") &&
          sourceWorkbenchModelSource.includes("export function confidencePercent(") &&
          sourceWorkbenchModelSource.includes("export function splitInputPaths(") &&
          sourceWorkbenchModelSource.includes("export function sourceProfileSummary(") &&
          sourceWorkbenchModelSource.includes("export function sourceProfileBusinessStatus(") &&
          sourceWorkbenchModelSource.includes("export function sourceProfileRecovery(") &&
          sourceWorkbenchModelSource.includes("export function buildFieldSemanticReadiness(") &&
          sourceWorkbenchModelSource.includes("FieldConfig") &&
          sourceWorkbenchModelSource.includes('from "./components/Bilingual"') &&
          sourceWorkbenchModelSource.includes("external source folders remain untouched") &&
          sourceWorkbenchModelSource.includes("field.confidence >= 0.82"),
      },
    {
        label: "source-workbench-derived-model-boundary",
        ok: sourceWorkbenchSource.includes("buildSourceWorkbenchCollections(workbench, status, query)") &&
          sourceWorkbenchSource.includes("buildSourceWorkbenchSelection({") &&
          sourceWorkbenchSource.includes("buildSourceWorkbenchRuntimeSummary(workbench, status, query)") &&
          sourceWorkbenchImportControllerSource.includes("buildImportPreviewSummary({ preview, previewReadable, targetName })") &&
          !sourceWorkbenchSource.includes("const tables = Array.isArray(workbench.tables)") &&
          !sourceWorkbenchSource.includes("const selectedRowFormulas = rowFormulas.filter") &&
          !sourceWorkbenchSource.includes("const calculatedMeasureFields = selectedRowFormulas.map") &&
          !sourceWorkbenchSource.includes("const mergePlan = preview.mergePolicyPreview.mergePlan") &&
          sourceWorkbenchModelSource.includes("export function buildSourceWorkbenchCollections(") &&
          sourceWorkbenchModelSource.includes("export function buildSourceWorkbenchSelection(") &&
          sourceWorkbenchModelSource.includes("export function buildSourceWorkbenchRuntimeSummary(") &&
          sourceWorkbenchModelSource.includes("export function buildImportPreviewSummary("),
      },
    {
        label: "frontend-business-first-copy-boundary",
        ok: appSource.includes("BusinessPathBar") &&
          appSource.includes('from "./appLazyModules"') &&
          appSource.includes("<BusinessPathBar") &&
          appSource.includes('loadState === "ready"') &&
          appSource.includes("handleOpenBusinessStep") &&
          businessPathModelSource.includes('export type BusinessPathStepKey = "data" | "chart" | "evidence" | "confirm"') &&
          businessPathModelSource.includes("businessSectionForStep") &&
          businessPathModelSource.includes("businessStepForSection") &&
          businessPathBarSource.includes('data-testid="global-business-path"') &&
          businessPathBarSource.includes('data-testid={`business-path-${step.key}`}') &&
          businessPathBarSource.includes("每一步跳到唯一页面处理") &&
          homeOverviewSource.includes("从一条业务路径进入，不在首页重复配置") &&
          homeOverviewSource.includes("同一件事只保留一个承接页") &&
          homeActionDockSource.includes('onOpenStep("chart")') &&
          homeActionDockSource.includes("生成一个图表") &&
          homeOverviewSource.includes("<HomeOperatingSummaryPanel") &&
          homeOperatingSummaryPanelSource.includes("生成证据摘要") &&
          homeOperatingSummaryPanelSource.includes("这些问题会自动使用当前工作区和证据摘要") &&
          homeOperatingSummaryPanelSource.includes("常见问题不用配置") &&
          homeOperatingSummaryPanelSource.includes("动作边界") &&
          sourceWorkbenchHeaderSource.includes("数据入口") &&
          sourceWorkbenchHeaderSource.includes("先检查文件，再让系统生成证据摘要和看板建议") &&
          sourceWorkbenchDataEntryPanelSource.includes("证据摘要") &&
          !sourceWorkbenchDataEntryPanelSource.includes("生成样例摘要") &&
          sourceWorkbenchActionPanelSource.includes("数据模型与管理") &&
          sourceWorkbenchActionPanelSource.includes('data-testid="source-expert-toggle"') &&
          !sidebarAssetSectionsSource.includes("生成证据摘要") &&
          inspectorPanelModelSource.includes("生成摘要、创建看板") &&
          bWidgetKitSource.includes("sourceIntelligenceRuns") &&
          biDashboardWidgetFactorySource.includes("sourceIntelligenceRuns") &&
          bWidgetKitOverviewSource.includes("等待证据摘要") &&
          !sourceWorkbenchSource.includes("一键用 A 项目的 3-5 月全量表格生成画像") &&
          !sourceWorkbenchSource.includes("条可执行指标 SQL") &&
          agentPanelModelSource.includes("数据来源") &&
          agentPanelModelSource.includes("查询回执") &&
          agentPanelModelSource.includes("看板匹配") &&
          !agentPanelSource.includes("Query runtime") &&
          !agentPanelSource.includes("Ontology function"),
      },
    {
        label: "source-workbench-dashboard-next-action",
        ok: sourceWorkbenchActionPanelSource.includes('data-testid="source-dashboard-next-action"') &&
          sourceWorkbenchActionPanelSource.includes('data-testid="source-dashboard-recipe"') &&
          sourceWorkbenchActionPanelSource.includes('data-testid="source-dashboard-recipe-facts"') &&
          sourceWorkbenchActionPanelSource.includes('data-testid="source-dashboard-recipe-cards"') &&
          sourceWorkbenchActionPanelSource.includes('data-testid="source-dashboard-agent-draft"') &&
          sourceWorkbenchGuidanceModelSource.includes("dashboardRecipeCards") &&
          sourceWorkbenchGuidanceModelSource.includes("dashboardRecipeEvidenceCount") &&
          sourceWorkbenchActionPanelSource.includes("证据到看板配方") &&
          sourceWorkbenchActionPanelSource.includes("优先使用") &&
          sourceWorkbenchActionPanelSource.includes('data-testid="source-business-dashboard-preview"') &&
          sourceWorkbenchActionPanelSource.includes('data-testid="source-business-dashboard-create"') &&
          sourceWorkbenchActionPanelSource.includes('disabled={!dashboardRecipeReady || busy === "source-business-dashboard-preview"}') &&
          sourceWorkbenchActionPanelSource.includes('disabled={!dashboardRecipeReady || busy === "source-business-dashboard-create"}') &&
          sourceWorkbenchSource.includes("onBusinessDashboardOperation") &&
          sourceWorkbenchSource.includes("op: confirm ? \"create\" : \"draft\"") &&
          sourceWorkbenchSource.includes("onOpenDashboard()") &&
          stylesSource.includes(".sourceDashboardRecipe") &&
          stylesSource.includes(".sourceDashboardRecipeFacts") &&
          stylesSource.includes(".sourceDashboardRecipeCards") &&
          byLabel["cli-business-dashboard-draft"].parsed?.ok === true &&
          Boolean(byLabel["cli-business-dashboard-create-confirm"].parsed?.createdDashboardKey),
      },
    {
        label: "source-workbench-index-agent-draft-entry",
        ok: sourceWorkbenchActionPanelSource.includes('data-testid="source-index-suggestion"') &&
          sourceWorkbenchActionPanelSource.includes('data-testid="source-index-agent-draft"') &&
          sourceWorkbenchSource.includes("indexCandidateName") &&
          sourceWorkbenchModelSource.includes("const indexCandidateField = groupFields.find") &&
          sourceWorkbenchModelSource.includes("indexCandidateName: indexCandidateField?.field_name") &&
          sourceWorkbenchActionPanelSource.includes("让 Agent 起草索引") &&
          sourceWorkbenchActionPanelSource.includes("确认前不会创建 DuckDB 索引") &&
          sourceWorkbenchActionPanelSource.includes("onAsk(biText(`给 ${selectedTableKey} 的 ${indexCandidateName} 建索引来优化查询`") &&
          appSource.includes("onAsk={handleAgentCommandAsk}") &&
          stylesSource.includes(".sourceIndexSuggestion") &&
          stylesSource.includes(".sourceIndexFacts") &&
          byLabel["cli-agent-index-draft"].parsed?.requiresConfirmation === true &&
          byLabel["cli-agent-index-draft"].parsed?.actionDraft?.kind === "index.create",
      },
    {
        label: "source-workbench-agent-question-starter",
        ok: existsSync(join(root, "src", "components", "SourceWorkbenchAgentStarter.tsx")) &&
          sourceWorkbenchActionPanelSource.includes('import { SourceWorkbenchAgentStarter, type SourceAgentPrompt } from "./SourceWorkbenchAgentStarter"') &&
          sourceWorkbenchActionPanelSource.includes("<SourceWorkbenchAgentStarter") &&
          !sourceWorkbenchActionPanelSource.includes('data-testid="source-agent-question-starter"') &&
          !sourceWorkbenchActionPanelSource.includes("sourceAgentPrompts.map((item)") &&
          sourceWorkbenchAgentStarterSource.includes("export type SourceAgentPrompt") &&
          sourceWorkbenchAgentStarterSource.includes('import { AgentPromptGrid, type AgentPromptGridItem } from "./AgentPromptGrid"') &&
          sourceWorkbenchAgentStarterSource.includes("<AgentPromptGrid") &&
          sourceWorkbenchAgentStarterSource.includes('data-testid="source-agent-question-starter"') &&
          sourceWorkbenchAgentStarterSource.includes('testId="source-agent-prompt-grid"') &&
          sourceWorkbenchAgentStarterSource.includes('itemTestIdPrefix="source-agent-prompt"') &&
          sourceWorkbenchGuidanceModelSource.includes("const sourceAgentPrompts") &&
          sourceWorkbenchGuidanceModelSource.includes('"can-answer"') &&
          sourceWorkbenchGuidanceModelSource.includes('"find-gaps"') &&
          sourceWorkbenchGuidanceModelSource.includes('"draft-dashboard"') &&
          sourceWorkbenchGuidanceModelSource.includes("不要创建任何草案") &&
          sourceWorkbenchGuidanceModelSource.includes("先不要直接写入") &&
          agentPromptGridSource.includes("export type AgentPromptGridItem") &&
          agentPromptGridSource.includes("export function AgentPromptGrid") &&
          agentPromptGridSource.includes('data-testid={`${itemTestIdPrefix}-${item.key}`}') &&
          agentPromptGridSource.includes("onAsk(item.prompt)") &&
          stylesSource.includes(".sourceAgentStarter") &&
          stylesSource.includes(".agentPromptGrid") &&
          stylesSource.includes(".sourceAgentStarter .agentPromptGrid button"),
      },
    {
        label: "source-workbench-beginner-import-plan",
        ok: sourceWorkbenchActionPanelSource.includes('data-testid="beginner-import-plan"') &&
          sourceWorkbenchActionPanelSource.includes('data-testid={`beginner-plan-${item.key}`}') &&
          !sourceWorkbenchActionPanelSource.includes('data-testid="beginner-plan-check-file"') &&
          !sourceWorkbenchActionPanelSource.includes('data-testid="beginner-plan-import-data"') &&
          sourceWorkbenchActionPanelSource.includes('data-testid="beginner-plan-refresh-profile"') &&
          sourceWorkbenchActionPanelSource.includes('data-testid="beginner-evidence-guard"') &&
          sourceWorkbenchActionPanelSource.includes('data-testid="source-guide-details"') &&
          sourceWorkbenchActionPanelSource.includes("更多引导和高级建议") &&
          sourceWorkbenchImportPanelSource.includes('data-testid="import-confirmation-summary"') &&
          sourceWorkbenchImportPanelSource.includes('data-testid="import-confirmation-impact"') &&
          sourceWorkbenchImportPanelSource.includes('data-testid="import-confirmation-safety"') &&
          sourceWorkbenchImportPanelSource.includes('data-testid="import-confirmation-confirm"') &&
          sourceWorkbenchImportPanelSource.includes("{previewReadable ? (") &&
          sourceWorkbenchImportPanelSource.includes('disabled={busy === "import-confirm"}') &&
          !sourceWorkbenchActionPanelSource.includes("不可读或未预检时不能确认导入") &&
          sourceWorkbenchSource.includes("hasData && sourceProfileComplete ? (") &&
          sourceWorkbenchSource.includes('data-testid="source-evidence-details"') &&
          stylesSource.includes(".beginnerImportGuard") &&
          stylesSource.includes(".sourceGuideDetails") &&
          sourceWorkbenchImportControllerSource.includes("const previewSummary = buildImportPreviewSummary") &&
          sourceWorkbenchImportControllerSource.includes("...previewSummary") &&
          sourceWorkbenchGuidanceModelSource.includes("const recommendedPrimaryAction") &&
          /hasImportedTables\s*\?\s*sourceProfileComplete/.test(sourceWorkbenchGuidanceModelSource) &&
          sourceWorkbenchGuidanceModelSource.includes('"draft-dashboard"') &&
          sourceWorkbenchGuidanceModelSource.includes("sourceProfileComplete") &&
          sourceWorkbenchGuidanceModelSource.includes("previewReadable") &&
          sourceWorkbenchGuidanceModelSource.includes("hasImportedTables") &&
          sourceWorkbenchGuidanceModelSource.includes('measureFields[0]?.field_name ?? ""') &&
          sourceWorkbenchGuidanceModelSource.includes('groupFields[0]?.field_name ?? ""'),
      },
    {
        label: "source-workbench-guidance-model-boundary",
        ok: existsSync(join(root, "src", "sourceWorkbenchGuidanceModel.ts")) &&
          (sourceWorkbenchSource.includes('import { buildSourceWorkbenchGuidance } from "../sourceWorkbenchGuidanceModel"') || sourceWorkbenchSource.includes('from "./sourceWorkbenchGuidanceModel"')) &&
          sourceWorkbenchSource.includes("buildSourceWorkbenchGuidance({") &&
          !sourceWorkbenchSource.includes("const dashboardRecipeCards = [") &&
          !sourceWorkbenchSource.includes("const beginnerPlan = [") &&
          !sourceWorkbenchSource.includes("const sourceAgentPrompts:") &&
          !sourceWorkbenchSource.includes("const hasImportedTables = tables.length > 0") &&
          sourceWorkbenchGuidanceModelSource.includes("export function buildSourceWorkbenchGuidance(") &&
          sourceWorkbenchGuidanceModelSource.includes("export type RecommendedPrimaryAction") &&
          sourceWorkbenchGuidanceModelSource.includes("export type BeginnerPlanItem") &&
          sourceWorkbenchGuidanceModelSource.includes("export type SourceAgentPrompt") &&
          sourceWorkbenchGuidanceModelSource.includes("export type DashboardRecipeCard") &&
          sourceWorkbenchGuidanceModelSource.includes("sourceProfileRunningLabel") &&
          sourceWorkbenchGuidanceModelSource.includes("dashboardRecipeCards") &&
          sourceWorkbenchGuidanceModelSource.includes("beginnerPlan") &&
          sourceWorkbenchGuidanceModelSource.includes("sourceAgentPrompts"),
      },
    {
        label: "source-workbench-receipt-model-boundary",
        ok: existsSync(join(root, "src", "sourceWorkbenchReceiptModel.ts")) &&
          sourceWorkbenchImportControllerSource.includes('from "./sourceWorkbenchReceiptModel"') &&
          sourceWorkbenchImportControllerSource.includes("buildImportPreviewReceipt({") &&
          sourceWorkbenchImportControllerSource.includes("buildImportCommitReceipt({") &&
          sourceWorkbenchImportControllerSource.includes("buildImportPolicyReceipt({") &&
          sourceWorkbenchConnectorControllerSource.includes('from "./sourceWorkbenchReceiptModel"') &&
          sourceWorkbenchConnectorControllerSource.includes("buildConnectorSaveReceipt({") &&
          sourceWorkbenchConnectorControllerSource.includes("buildConnectorSyncReceipt(connector, confirm, result)") &&
          sourceWorkbenchConnectorControllerSource.includes("buildConnectorRemoveReceipt(connector)") &&
          !sourceWorkbenchSource.includes('title: biText("文件检查已完成"') &&
          !sourceWorkbenchSource.includes('title: confirm ? biText("导入已确认"') &&
          !sourceWorkbenchSource.includes('title: confirm ? biText("连接配置已保存"') &&
          !sourceWorkbenchSource.includes('title: confirm ? biText("同步已确认"') &&
          !sourceWorkbenchSource.includes('title: biText("连接删除已确认"') &&
          sourceWorkbenchReceiptModelSource.includes("export type WorkbenchOperationReceipt") &&
          sourceWorkbenchReceiptModelSource.includes("export function buildImportPreviewReceipt(") &&
          sourceWorkbenchReceiptModelSource.includes("export function buildImportCommitReceipt(") &&
          sourceWorkbenchReceiptModelSource.includes("export function buildImportPolicyReceipt(") &&
          sourceWorkbenchReceiptModelSource.includes("export function buildConnectorSaveReceipt(") &&
          sourceWorkbenchReceiptModelSource.includes("export function buildConnectorSyncReceipt(") &&
          sourceWorkbenchReceiptModelSource.includes("export function buildConnectorRemoveReceipt(") &&
          sourceWorkbenchReceiptModelSource.includes("外部源目录"),
      },
    {
        label: "source-workbench-command-model-boundary",
        ok: existsSync(join(root, "src", "sourceWorkbenchCommandModel.ts")) &&
          sourceWorkbenchImportControllerSource.includes('from "./sourceWorkbenchCommandModel"') &&
          sourceWorkbenchImportControllerSource.includes("buildImportOptions({") &&
          sourceWorkbenchImportControllerSource.includes("buildImportPolicyOptions({") &&
          (sourceWorkbenchSource.includes('from "../sourceWorkbenchCommandModel"') || sourceWorkbenchSource.includes('from "./sourceWorkbenchCommandModel"')) &&
          sourceWorkbenchSource.includes("buildSourceProfileOptions({") &&
          sourceWorkbenchConnectorControllerSource.includes("buildConnectorOptions({") &&
          sourceWorkbenchSource.includes("buildMetricDraft({") &&
          !sourceWorkbenchSource.includes("uniqueFields: splitCsv(uniqueFields)") &&
          !sourceWorkbenchSource.includes("inputs: splitInputPaths(sourceProfileInputs)") &&
          !sourceWorkbenchSource.includes("connector: connectorEditingKey || undefined") &&
          !sourceWorkbenchSource.includes("dimension: effectiveMetricDimension || undefined") &&
          sourceWorkbenchCommandModelSource.includes("export type ImportOptions") &&
          sourceWorkbenchCommandModelSource.includes("export type ImportPolicyOptions") &&
          sourceWorkbenchCommandModelSource.includes("export type ConnectorOptions") &&
          sourceWorkbenchCommandModelSource.includes("export type { SourceIntelligenceRunOptions }") &&
          sourceWorkbenchCommandModelSource.includes("export type MetricMutationOptions") &&
          sourceWorkbenchCommandModelSource.includes("export function buildImportOptions(") &&
          sourceWorkbenchCommandModelSource.includes("export function buildImportPolicyOptions(") &&
          sourceWorkbenchCommandModelSource.includes("export function buildSourceProfileOptions(") &&
          sourceWorkbenchCommandModelSource.includes("export function buildConnectorOptions(") &&
          sourceWorkbenchCommandModelSource.includes("export function buildMetricDraft(") &&
          sourceWorkbenchCommandModelSource.includes("splitCsv(uniqueFields)") &&
          sourceWorkbenchCommandModelSource.includes("splitCsv(connectorUniqueFields)") &&
          sourceWorkbenchCommandModelSource.includes("inputs: splitInputPaths(sourceProfileInputs)") &&
          sourceWorkbenchCommandModelSource.includes('label: sourceProfileLabel.trim() || "Source profile"'),
      },
    {
        label: "source-intelligence-run-model-boundary",
        ok: existsSync(join(root, "src", "sourceIntelligenceRunModel.ts")) &&
          sourceIntelligenceRunModelSource.includes("export type SourceIntelligenceRunRequest") &&
          sourceIntelligenceRunModelSource.includes("export type SourceIntelligenceRunResult") &&
          sourceIntelligenceRunModelSource.includes("export type SourceIntelligenceRunOptions") &&
          !sourceIntelligenceRunModelSource.includes("SOURCE_INTELLIGENCE_A_TESTDATA") &&
          !sourceIntelligenceRunModelSource.includes("aTestdata0305") &&
          apiSourceApiSource.includes('SourceIntelligenceRunRequest, SourceIntelligenceRunResponse') &&
          !appDataActionsSource.includes("aTestdata0305SourceIntelligenceRequest()") &&
          !homeOverviewSource.includes("aTestdata0305SourceIntelligenceOptions({") &&
          evidenceViewSource.includes("type { SourceIntelligenceRunOptions }") &&
          homeProductIntelligencePanelSource.includes("type { SourceIntelligenceRunOptions }") &&
          !metricSemanticRepairActionsSource.includes("aTestdata0305SourceIntelligenceOptions({") &&
          sourceWorkbenchActionPanelSource.includes('from "../sourceIntelligenceRunModel"') &&
          sourceWorkbenchDataEntryPanelSource.includes('from "../sourceIntelligenceRunModel"') &&
          !sourceWorkbenchHeaderSource.includes('from "../sourceIntelligenceRunModel"') &&
          !sourceWorkbenchGuidanceModelSource.includes("SOURCE_INTELLIGENCE_A_TESTDATA_COMMAND") &&
          !sourceWorkbenchActionPanelSource.includes("type SourceIntelligenceRunOptions =") &&
          !sourceWorkbenchDataEntryPanelSource.includes("type SourceIntelligenceRunOptions =") &&
          !metricSemanticRepairActionsSource.includes("type SourceIntelligenceOptions ="),
      },
    {
        label: "source-workbench-contracts-boundary",
        ok: existsSync(join(root, "src", "sourceWorkbenchContracts.ts")) &&
          sourceWorkbenchSource.includes('from "../sourceWorkbenchContracts"') &&
          sourceWorkbenchSource.includes("type { QueryOptions, SourceWorkbenchProps }") &&
          !sourceWorkbenchSource.includes("type SourceWorkbenchProps =") &&
          !sourceWorkbenchSource.includes("type SemanticSetOptions =") &&
          !sourceWorkbenchSource.includes("type MetricQueryOptions =") &&
          sourceWorkbenchContractsSource.includes("export type SourceWorkbenchProps") &&
          sourceWorkbenchContractsSource.includes("export type QueryOptions") &&
          sourceWorkbenchContractsSource.includes("export type FieldUpdateOptions") &&
          sourceWorkbenchContractsSource.includes("export type SemanticInferOptions") &&
          sourceWorkbenchContractsSource.includes("export type SemanticSetOptions") &&
          sourceWorkbenchContractsSource.includes("export type MetricQueryOptions") &&
          sourceWorkbenchContractsSource.includes("onSourceIntelligenceRun: (options?: SourceIntelligenceRunOptions)"),
      },
    {
        label: "source-workbench-draft-model-boundary",
        ok: existsSync(join(root, "src", "sourceWorkbenchDraftModel.ts")) &&
          (sourceWorkbenchSource.includes('from "../sourceWorkbenchDraftModel"') || sourceWorkbenchSource.includes('from "./sourceWorkbenchDraftModel"')) &&
          sourceWorkbenchSource.includes("readFieldDraft(fieldDrafts, field)") &&
          sourceWorkbenchSource.includes("applyFieldDraftPatch(current, field, patch)") &&
          sourceWorkbenchSource.includes("buildNavigationOperationOptions({") &&
          sourceWorkbenchSource.includes("managedSourceDisplayName(tables, tableKey)") &&
          !sourceWorkbenchSource.includes("fieldDrafts[`${field.table_key}.${field.field_name}`]") &&
          !sourceWorkbenchSource.includes("const key = `${field.table_key}.${field.field_name}`") &&
          !sourceWorkbenchSource.includes("moduleKey = activeNavigationModule?.moduleKey") &&
          !sourceWorkbenchSource.includes("Number(navigationSort || activeNavigationModule?.sort || 0)") &&
          !sourceWorkbenchSource.includes("tables.find((item) => item.table_key === tableKey)") &&
          sourceWorkbenchDraftModelSource.includes("export type FieldDraft") &&
          sourceWorkbenchDraftModelSource.includes("export type FieldDrafts") &&
          sourceWorkbenchDraftModelSource.includes("export type NavigationOperation") &&
          sourceWorkbenchDraftModelSource.includes("export function fieldDraftKey(") &&
          sourceWorkbenchDraftModelSource.includes("export function readFieldDraft(") &&
          sourceWorkbenchDraftModelSource.includes("export function applyFieldDraftPatch(") &&
          sourceWorkbenchDraftModelSource.includes("export function managedSourceDisplayName(") &&
          sourceWorkbenchDraftModelSource.includes("export function buildNavigationOperationOptions(") &&
          sourceWorkbenchDraftModelSource.includes("activeNavigationModule?.moduleKey ?? navigationModuleKey") &&
          sourceWorkbenchDraftModelSource.includes("Number(navigationSort || activeNavigationModule?.sort || 0)"),
      },
    {
        label: "source-workbench-action-panel-boundary",
        ok: existsSync(join(root, "src", "components", "SourceWorkbenchActionPanel.tsx")) &&
          sourceWorkbenchSource.includes('from "../sourceWorkbenchDeferredModules"') &&
          sourceWorkbenchDeferredModulesSource.includes("export const SourceWorkbenchActionPanel = lazy") &&
          sourceWorkbenchSource.includes("<SourceWorkbenchActionPanel") &&
          !sourceWorkbenchSource.includes('data-testid="source-agent-question-starter"') &&
          !sourceWorkbenchSource.includes('data-testid="source-dashboard-next-action"') &&
          !sourceWorkbenchSource.includes('data-testid="source-index-suggestion"') &&
          !sourceWorkbenchSource.includes('data-testid="beginner-import-plan"') &&
          sourceWorkbenchActionPanelSource.includes("type SourceWorkbenchActionPanelProps") &&
          sourceWorkbenchActionPanelSource.includes('type SourceAgentPrompt } from "./SourceWorkbenchAgentStarter"') &&
          sourceWorkbenchActionPanelSource.includes("type DashboardRecipeCard") &&
          sourceWorkbenchActionPanelSource.includes("RecommendedPrimaryAction") &&
          sourceWorkbenchActionPanelSource.includes("runBusinessDashboard: (confirm: boolean) => Promise<void>") &&
          sourceWorkbenchActionPanelSource.includes("runSourceProfile: (label: string, options: SourceIntelligenceRunOptions) => Promise<void>") &&
          sourceWorkbenchActionPanelSource.includes("<SourceWorkbenchAgentStarter") &&
          sourceWorkbenchActionPanelSource.includes("dashboardRecipeCards.map((card)") &&
          sourceWorkbenchActionPanelSource.includes("setShowAdvanced((current) => !current)"),
      },
    {
        label: "source-workbench-import-panel-boundary",
        ok: existsSync(join(root, "src", "components", "SourceWorkbenchImportPanel.tsx")) &&
          sourceWorkbenchSource.includes('import { SourceWorkbenchImportPanel } from "./SourceWorkbenchImportPanel"') &&
          sourceWorkbenchSource.includes("<SourceWorkbenchImportPanel") &&
          !sourceWorkbenchSource.includes('data-testid="import-confirmation-summary"') &&
          !sourceWorkbenchSource.includes('data-testid="import-operation-receipt"') &&
          sourceWorkbenchImportPanelSource.includes("type SourceWorkbenchImportPanelProps") &&
          sourceWorkbenchImportPanelSource.includes("ReturnType<typeof useSourceWorkbenchImportController>") &&
          sourceWorkbenchImportControllerSource.includes("importPolicies: ImportPolicy[]") &&
          sourceWorkbenchImportControllerSource.includes("async function runImportPreviewAction()") &&
          sourceWorkbenchImportControllerSource.includes("async function runImportCommitAction(confirm: boolean)") &&
          sourceWorkbenchImportControllerSource.includes("async function runImportPolicyAction(confirm: boolean)") &&
          sourceWorkbenchImportPanelSource.includes('data-testid="import-policy-dry-run-button"') &&
          sourceWorkbenchImportPanelSource.includes('data-testid="import-policy-confirm-button"') &&
          sourceWorkbenchImportPanelSource.includes("确认后才写入工作区") &&
          sourceWorkbenchImportPanelSource.includes("当前只做检查，不写入") &&
          sourceWorkbenchImportPanelSource.includes("View import policy and receipt") &&
          sourceWorkbenchImportPanelSource.includes("countText(importInsertRows)"),
      },
    {
        label: "b-navigation-module-workflow",
        ok: byLabel["cli-list-navigation"].parsed?.navigation?.some((module) => module.moduleKey === "table:orders" && module.type === "table") &&
          byLabel["cli-list-navigation"].parsed?.navigation?.some((module) => module.moduleKey === "dashboard:default" && module.type === "dashboard") &&
          byLabel["cli-navigation-rename-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-navigation-rename-confirm"].parsed?.navigationModule?.name === "验证导航订单" &&
          byLabel["cli-navigation-move-dry-run"].parsed?.proposedModule?.sort === 88 &&
          byLabel["cli-navigation-move-confirm"].parsed?.navigationModule?.sort === 88 &&
          byLabel["cli-navigation-hide-dry-run"].parsed?.proposedModule?.enabled === false &&
          byLabel["cli-navigation-hide-confirm"].parsed?.navigationModule?.enabled === false &&
          byLabel["cli-navigation-show-dry-run"].parsed?.currentModule?.enabled === false &&
          byLabel["cli-navigation-show-dry-run"].parsed?.proposedModule?.enabled === true &&
          byLabel["cli-navigation-show-confirm"].parsed?.navigationModule?.enabled === true &&
          byLabel["cli-navigation-move-restore"].parsed?.navigationModule?.sort === 10 &&
          byLabel["cli-navigation-rename-restore"].parsed?.navigationModule?.name === "Orders" &&
          !biCliSource.includes("enabled = 1,\n                updated_at = ?"),
      },
    {
        label: "b-query-table-and-saved-views",
        ok: byLabel["cli-query-table-detail"].parsed?.tableQuery?.filteredRows === 4 &&
          byLabel["cli-query-table-detail"].parsed?.tableQuery?.rows?.[0]?.net_sales === "1280" &&
          byLabel["cli-query-table-view"].parsed?.tableQuery?.viewKey === "view_orders_default" &&
          byLabel["cli-list-views"].parsed?.savedViews?.length >= 2 &&
          byLabel["cli-save-view-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-save-view-confirm"].parsed?.confirmed === true,
      },
    {
        label: "b-dashboard-widget-catalog-complete",
        ok: ["metric", "bar", "line", "pie", "table", "text", "slicer"].every((type) => byLabel["cli-dashboard-widget-catalog"].parsed?.widgetTypes?.includes(type)) &&
          ["table", "view", "relationship"].every((mode) => byLabel["cli-dashboard-widget-catalog"].parsed?.dataModes?.includes(mode)) &&
          byLabel["cli-dashboard-widget-catalog"].parsed?.catalog?.length === 7 &&
          byLabel["cli-dashboard-widget-catalog"].parsed?.integration?.agentPolicy?.includes("action drafts"),
      },
    {
        label: "b-dashboard-widget-write-cycle",
        ok: byLabel["cli-recommend-widgets"].parsed?.recommendations?.length >= 6 &&
          byLabel["cli-add-recommended-widgets-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-add-recommended-widgets-dry-run"].parsed?.plannedCount >= 2 &&
          byLabel["cli-add-widget-view-dry-run"].parsed?.proposedWidget?.config?.dataMode === "view" &&
          byLabel["cli-add-widget-view-confirm"].parsed?.confirmed === true &&
          byLabel["cli-add-widget-view-confirm"].parsed?.addedWidget?.widget_key === "verify_view_widget" &&
          byLabel["cli-set-widget-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-set-widget-dry-run"].parsed?.proposedWidget?.title === "验证视图组件更新" &&
          byLabel["cli-set-widget-dry-run"].parsed?.proposedWidget?.config?.subtitle === "验证配置编辑" &&
          byLabel["cli-set-widget-dry-run"].parsed?.proposedWidget?.config?.topN === 20 &&
          byLabel["cli-set-widget-dry-run"].parsed?.proposedWidget?.config?.valueFormat === "currency" &&
          byLabel["cli-set-widget-filter-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-set-widget-filter-dry-run"].parsed?.proposedWidget?.config?.filters?.[0]?.field === "channel" &&
          byLabel["cli-set-widget-filter-confirm"].parsed?.confirmed === true &&
          byLabel["cli-set-widget-clear-filter-dry-run"].parsed?.requiresConfirmation === true &&
          Array.isArray(byLabel["cli-set-widget-clear-filter-dry-run"].parsed?.proposedWidget?.config?.filters) &&
          byLabel["cli-set-widget-clear-filter-dry-run"].parsed?.proposedWidget?.config?.filters.length === 0 &&
          byLabel["cli-copy-widget-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-remove-widget-dry-run"].parsed?.requiresConfirmation === true,
      },
    {
        label: "b-dashboard-widget-style-controls",
        ok: byLabel["cli-set-widget-style-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.colorPalette === "contrast" &&
          byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.barOrientation === "horizontal" &&
          byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.rankingMode === "ranked" &&
          byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.showDataLabel === true &&
          byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.showLegend === false &&
          byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.showAxis === false &&
          byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.areaFill === true &&
          byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.pieShape === "pie" &&
          byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.slicerDisplay === "dropdown" &&
          byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.decimalPlaces === 1 &&
          byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.tableColumnLimit === 8 &&
          byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.xAxisTitle === "渠道" &&
          byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.yAxisTitle === "净销售额" &&
          byLabel["cli-set-widget-style-dry-run"].parsed?.proposedWidget?.config?.legendTitle === "渠道分类" &&
          byLabel["cli-set-widget-style-confirm"].parsed?.confirmed === true &&
          byLabel["cli-set-widget-style-confirm"].parsed?.updatedWidget?.config?.colorPalette === "contrast",
      },
    {
        label: "b-dashboard-modules-bulk-save-cycle",
        ok: byLabel["cli-save-dashboard-modules-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-save-dashboard-modules-dry-run"].parsed?.proposed?.widgetCount === 2 &&
          byLabel["cli-save-dashboard-modules-dry-run"].parsed?.proposed?.canvasWidthMode === "center" &&
          byLabel["cli-save-dashboard-modules-confirm"].parsed?.confirmed === true &&
          byLabel["cli-save-dashboard-modules-confirm"].parsed?.savedDashboardModules === 2 &&
          byLabel["cli-save-dashboard-modules-confirm"].parsed?.savedDashboardFilters === 1 &&
          byLabel["cli-save-dashboard-modules-confirm"].parsed?.dashboard?.layout?.canvasWidthMode === "center" &&
          byLabel["cli-save-dashboard-modules-confirm"].parsed?.dashboard?.widgets?.some((widget) => widget.widget_key === "verify_bulk_metric" && widget.config?.layout?.i === "verify_bulk_metric") &&
          byLabel["cli-dashboards-after-module-save"].parsed?.dashboards?.[0]?.widgets?.length === 2 &&
          byLabel["cli-dashboards-after-module-save"].parsed?.dashboards?.[0]?.layout?.globalFilters?.[0]?.field === "channel",
      },
    {
        label: "b-business-dashboard-template-cycle",
        ok: byLabel["cli-business-dashboard-draft"].parsed?.templateCount >= 5 &&
          byLabel["cli-business-dashboard-draft"].parsed?.draft?.templates?.some((template) => template.type === "slicer") &&
          byLabel["cli-business-dashboard-create-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-business-dashboard-create-dry-run"].parsed?.proposed?.widgetCount >= 5 &&
          byLabel["cli-business-dashboard-create-confirm"].parsed?.confirmed === true &&
          Boolean(byLabel["cli-business-dashboard-create-confirm"].parsed?.createdDashboardKey) &&
          byLabel["cli-business-dashboard-create-confirm"].parsed?.savedDashboardModules >= 5 &&
          byLabel["cli-business-dashboard-overwrite-dry-run"].parsed?.requiresConfirmation === true,
      },
    {
        label: "b-dashboard-relationship-widget-write-cycle",
        ok: byLabel["cli-add-relationship-widget-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-add-relationship-widget-dry-run"].parsed?.proposedWidget?.config?.dataMode === "relationship" &&
          byLabel["cli-add-relationship-widget-dry-run"].parsed?.proposedWidget?.config?.relationship?.relationKey === "orders_refunds_order_id_order_id" &&
          byLabel["cli-add-relationship-widget-confirm"].parsed?.confirmed === true &&
          byLabel["cli-add-relationship-widget-confirm"].parsed?.addedWidget?.widget_key === "verify_relationship_widget" &&
          byLabel["cli-add-relationship-widget-confirm"].parsed?.addedWidget?.config?.relationship?.leftTableKey === "orders",
      },
    {
        label: "b-relationship-recommendation-cycle",
        ok: byLabel["cli-recommend-relationships"].parsed?.dryRun === true &&
          byLabel["cli-recommend-relationships"].parsed?.recommendations?.some((recommendation) =>
            recommendation.leftTableKey === "orders" &&
            recommendation.rightTableKey === "refunds" &&
            recommendation.fieldMappings?.some((mapping) => mapping.leftField === mapping.rightField) &&
            typeof recommendation.previewMetrics?.confidence === "number"
          ),
      },
    {
        label: "b-field-semantic-metric-management",
        ok: byLabel["cli-infer-semantics-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-infer-semantics-dry-run"].parsed?.proposed >= 8 &&
          byLabel["cli-set-semantic-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-set-semantic-confirm"].parsed?.confirmed === true &&
          byLabel["cli-set-semantic-confirm"].parsed?.semantic?.field === "sku" &&
          byLabel["cli-set-semantic-confirm"].parsed?.semantic?.tags?.includes("product") &&
          byLabel["cli-list-semantics"].parsed?.semantics?.some((semantic) => semantic.field === "sku" && semantic.source === "manual") &&
          byLabel["cli-infer-metrics-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-infer-metrics-confirm"].parsed?.saved >= 4 &&
          byLabel["cli-list-metrics"].parsed?.metrics?.some((metric) => metric.metricKey === "orders_net_sales_sum" && metric.dimension === "channel") &&
          byLabel["cli-add-metric-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-add-metric-confirm"].parsed?.confirmed === true &&
          byLabel["cli-add-metric-confirm"].parsed?.savedMetric?.metricKey === "verify_avg_net_sales" &&
          byLabel["cli-query-metric"].parsed?.tableQuery?.rows?.some((row) => row.channel === "Douyin" && Number(row.sum_net_sales) === 3440),
      },
    {
        label: "b-bi-cli-bridge-core-areas",
        ok: ["source-management", "query-runtime", "saved-views", "dashboard-pages", "dashboard-widgets", "filters", "performance-indexes", "relationships", "import", "field-metric-formula", "connectors-preferences", "config-portability"].every((area) =>
          byLabel["cli-capabilities"].parsed?.capabilities?.some((capability) => capability.area === area && capability.status === "active")
        ) &&
          byLabel["cli-capabilities"].parsed?.capabilities?.some((capability) => capability.area === "dashboard-widgets" && capability.commands?.includes("add-relationship-widget") && capability.commands?.includes("save-dashboard-modules") && capability.commands?.includes("business-dashboard")) &&
          byLabel["cli-capabilities"].parsed?.capabilities?.some((capability) => capability.area === "filters" && capability.commands?.includes("remove-stale-filters")) &&
          byLabel["cli-capabilities"].parsed?.capabilities?.some((capability) => capability.area === "performance-indexes" && capability.commands?.includes("recommend-indexes") && capability.commands?.includes("create-index")) &&
          byLabel["cli-capabilities"].parsed?.capabilities?.some((capability) => capability.area === "relationships" && capability.commands?.includes("recommend-relationships") && capability.commands?.includes("query-relationship")) &&
          byLabel["cli-capabilities"].parsed?.capabilities?.some((capability) => capability.area === "import" && capability.commands?.includes("set-import-policy") && capability.commands?.includes("list-import-jobs")) &&
          byLabel["cli-capabilities"].parsed?.capabilities?.some((capability) => capability.area === "field-metric-formula" && capability.commands?.includes("infer-semantics") && capability.commands?.includes("set-semantic") && capability.commands?.includes("infer-metrics") && capability.commands?.includes("query-metric")) &&
          byLabel["cli-capabilities"].parsed?.capabilities?.some((capability) => capability.area === "connectors-preferences" && capability.commands?.includes("save-connector") && capability.commands?.includes("sync-connector") && capability.commands?.includes("preferences") && capability.commands?.includes("theme-palettes")) &&
          byLabel["cli-capabilities"].parsed?.capabilities?.some((capability) => capability.area === "config-portability" && capability.commands?.includes("validate-config") && capability.commands?.includes("export-config") && capability.commands?.includes("apply-config")) &&
          byLabel["cli-capabilities"].parsed?.source?.executionPolicy?.includes("AIBI-C commands"),
      },
  );
  appendSourceContractExtendedChecks(context);
}
