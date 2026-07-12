export function appendDashboardViewContractExtendedChecks(context) {
  const {
    checks,
    agentPromptGridSource,
    appSource: appEntrySource,
    appMainViewSource,
    appWorkspaceModelSource,
    byLabel,
    dashboardAdvancedWidgetWorkbenchSource,
    dashboardBeginnerEditorSource,
    dashboardBusinessTaskStripSource,
    dashboardBusinessTemplatePanelSource,
    dashboardCanvasActionRunnerSource,
    dashboardCanvasActionsSource,
    dashboardCanvasFieldModelSource,
    dashboardCanvasFilterModelSource,
    dashboardCanvasPlanModelSource,
    dashboardCanvasReadinessModelSource,
    dashboardCanvasRelationshipModelSource,
    dashboardCanvasSource,
    dashboardCanvasSourceSwitchModelSource,
    dashboardCanvasSourceSwitchViewModelSource,
    dashboardCanvasStateSource,
    dashboardCanvasViewModelSource,
    dashboardContractBoundaryPanelSource,
    dashboardDeferredModulesSource,
    dashboardWidgetModulesSource,
    dashboardDeferredPanelsSource,
    dashboardDeferredStylesSource,
    dashboardFilterWorkbenchSource,
    dashboardModuleSavePanelSource,
    dashboardOverviewStripSource,
    dashboardPageAdminPanelSource,
    dashboardRelationshipRecommendationPanelSource,
    dashboardRelationshipWidgetPanelSource,
    dashboardSavedViewPanelSource,
    dashboardWidgetBasicFormSource,
    dashboardWidgetEditorPanelSource,
    dashboardWidgetLifecyclePanelSource,
    dashboardWidgetLocalFilterPanelSource,
    dashboardWidgetManagePanelSource,
    dashboardWidgetRecommendationPanelSource,
    dashboardWidgetStylePanelSource,
    erpUnitLibraryViewModelSource,
    evidenceBusinessSummaryPanelSource,
    evidenceViewModelSource,
    evidenceViewSource,
    existsSync,
    globalStylesSource,
    hasCssRule,
    implementationStatusSource,
    inspectorControllerSource,
    join,
    root,
    sourceWorkbenchActionPanelSource,
    sourceWorkbenchModelSource,
    sourceWorkbenchQueryFormulaPanelSource,
    sourceWorkbenchSource,
    stylesSource,
    topBarSource,
    viewAgentTaskStripSource,
    viewAgentTaskStripStylesSource,
    viewDashboardBridgePanelSource,
    viewDashboardBridgePanelStylesSource,
    viewSavedListPanelSource,
    viewWorkspaceModelSource,
    viewWorkspaceSource,
    viewWorkspaceStylesSource,
  } = context;
  const appSource = `${appEntrySource}\n${appMainViewSource}\n${inspectorControllerSource}`;
  checks.push(

    {
        label: "frontend-dashboard-source-switch-preview",
        ok: dashboardBeginnerEditorSource.includes('data-testid="dashboard-source-switch-panel"') &&
          dashboardBeginnerEditorSource.includes('data-testid="dashboard-source-switch-select"') &&
          dashboardBeginnerEditorSource.includes('data-testid="dashboard-source-switch-preview"') &&
          dashboardBeginnerEditorSource.includes('data-testid="dashboard-source-switch-confirm"') &&
          dashboardBeginnerEditorSource.includes('data-testid="dashboard-source-switch-impact"') &&
          dashboardBeginnerEditorSource.includes('data-testid="dashboard-source-switch-stale-list"') &&
          dashboardCanvasViewModelSource.includes("sourceSwitchAnalysis") &&
          dashboardBeginnerEditorSource.includes("sourceSwitchView.impactItems.map") &&
          dashboardBeginnerEditorSource.includes("sourceSwitchView.staleItems.map") &&
          dashboardCanvasActionsSource.includes("sourceSwitchModulePayload") &&
          dashboardCanvasActionsSource.includes("buildSourceSwitchModulePayload({") &&
          dashboardBeginnerEditorSource.includes("onSourceSwitch(false)") &&
          byLabel["cli-dashboard-source-switch-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-dashboard-source-switch-dry-run"].parsed?.proposed?.defaultTableKey === "refunds",
      },
    {
        label: "dashboard-canvas-source-switch-model-boundary",
        ok: existsSync(join(root, "src", "dashboardCanvasSourceSwitchModel.ts")) &&
          dashboardCanvasViewModelSource.includes('from "./dashboardCanvasSourceSwitchModel"') &&
          dashboardCanvasActionsSource.includes('from "./dashboardCanvasSourceSwitchModel"') &&
          dashboardCanvasViewModelSource.includes("analyzeDashboardSourceSwitch({") &&
          !dashboardCanvasSource.includes('from "../dashboardCanvasSourceSwitchModel"') &&
          !dashboardCanvasSource.includes("analyzeDashboardSourceSwitch({") &&
          dashboardCanvasActionsSource.includes("buildSourceSwitchModulePayload({") &&
          !dashboardCanvasSource.includes("buildSourceSwitchModulePayload({") &&
          !dashboardCanvasSource.includes("sourceSwitchTargetFields") &&
          !dashboardCanvasSource.includes("sourceSwitchTargetFieldNames") &&
          !dashboardCanvasSource.includes("sourceSwitchValidFilters") &&
          !dashboardCanvasSource.includes("function cleanedWidgetForSourceSwitch(") &&
          !dashboardCanvasSource.includes("const localFilters = normalizeDashboardFilters({ globalFilters: Array.isArray(config.filters)") &&
          dashboardCanvasSourceSwitchModelSource.includes("export type SourceSwitchStaleWidgetRef") &&
          dashboardCanvasSourceSwitchModelSource.includes("export type SourceSwitchAnalysis") &&
          dashboardCanvasSourceSwitchModelSource.includes('import { normalizeWidgetFilters } from "./dashboardCanvasFilterModel"') &&
          dashboardCanvasSourceSwitchModelSource.includes("normalizeWidgetFilters(config.filters)") &&
          !dashboardCanvasSourceSwitchModelSource.includes("function normalizeWidgetConfigFilters(") &&
          dashboardCanvasSourceSwitchModelSource.includes("export function analyzeDashboardSourceSwitch(") &&
          dashboardCanvasSourceSwitchModelSource.includes("export function cleanedWidgetForSourceSwitch(") &&
          dashboardCanvasSourceSwitchModelSource.includes("export function buildSourceSwitchModulePayload(") &&
          dashboardCanvasSourceSwitchModelSource.includes('["dimension", "group", "measure", "timeField"]') &&
          dashboardCanvasSourceSwitchModelSource.includes("filterCleanup.length + staleWidgetRefs.length") &&
          dashboardCanvasSourceSwitchModelSource.includes("defaultTableKey: sourceSwitchTableKey"),
      },
    {
        label: "dashboard-canvas-source-switch-view-model-boundary",
        ok: existsSync(join(root, "src", "dashboardCanvasSourceSwitchViewModel.ts")) &&
          dashboardCanvasViewModelSource.includes('from "./dashboardCanvasSourceSwitchViewModel"') &&
          dashboardCanvasViewModelSource.includes("buildDashboardSourceSwitchViewModel(sourceSwitchAnalysis)") &&
          dashboardCanvasViewModelSource.includes("sourceSwitchView.changed") &&
          dashboardCanvasViewModelSource.includes("sourceSwitchView.cleanupCount") &&
          !dashboardCanvasSource.includes('from "../dashboardCanvasSourceSwitchViewModel"') &&
          !dashboardCanvasSource.includes("buildDashboardSourceSwitchViewModel(sourceSwitchAnalysis)") &&
          dashboardBeginnerEditorSource.includes("sourceSwitchView.impactItems.map") &&
          dashboardBeginnerEditorSource.includes("sourceSwitchView.showStaleList") &&
          dashboardBeginnerEditorSource.includes("sourceSwitchView.staleItems.map") &&
          !dashboardCanvasSource.includes("const sourceSwitchImpactedWidgets =") &&
          !dashboardCanvasSource.includes("const sourceSwitchFilterCleanup =") &&
          !dashboardCanvasSource.includes("const sourceSwitchStaleWidgetRefs =") &&
          !dashboardCanvasSource.includes("sourceSwitchFilterCleanup.slice(") &&
          !dashboardCanvasSource.includes("sourceSwitchStaleWidgetRefs.slice(") &&
          !dashboardCanvasSource.includes("widgets follow default source") &&
          !dashboardCanvasSource.includes("全局筛选需清理") &&
          dashboardCanvasSourceSwitchViewModelSource.includes("export type SourceSwitchViewItem") &&
          dashboardCanvasSourceSwitchViewModelSource.includes("export type DashboardSourceSwitchViewModel") &&
          dashboardCanvasSourceSwitchViewModelSource.includes("export function buildDashboardSourceSwitchViewModel(") &&
          dashboardCanvasSourceSwitchViewModelSource.includes("showStaleList: analysis.changed && analysis.cleanupCount > 0") &&
          dashboardCanvasSourceSwitchViewModelSource.includes("impactItems: [") &&
          dashboardCanvasSourceSwitchViewModelSource.includes("staleItems: [") &&
          dashboardCanvasSourceSwitchViewModelSource.includes("analysis.filterCleanup.slice(0, 3)") &&
          dashboardCanvasSourceSwitchViewModelSource.includes("analysis.staleWidgetRefs.slice(0, 4)") &&
          dashboardCanvasSourceSwitchViewModelSource.includes("widgets follow default source") &&
          dashboardCanvasSourceSwitchViewModelSource.includes("全局筛选需清理"),
      },
    {
        label: "dashboard-canvas-readiness-model-boundary",
        ok: existsSync(join(root, "src", "dashboardCanvasReadinessModel.ts")) &&
          dashboardCanvasViewModelSource.includes('from "./dashboardCanvasReadinessModel"') &&
          dashboardCanvasViewModelSource.includes("buildDashboardReadinessModel({") &&
          dashboardCanvasViewModelSource.includes("buildDashboardEvidenceFocus({") &&
          !dashboardCanvasSource.includes('from "../dashboardCanvasReadinessModel"') &&
          !dashboardCanvasSource.includes("buildDashboardReadinessModel({") &&
          !dashboardCanvasSource.includes("buildDashboardEvidenceFocus({") &&
          !dashboardCanvasSource.includes('const dashboardCreatedBy = String(dashboard.created_by || "manual")') &&
          !dashboardCanvasSource.includes("const dashboardHealthItems = [") &&
          !dashboardCanvasSource.includes('source: "dashboard-summary",') &&
          dashboardCanvasReadinessModelSource.includes("export type DashboardHealthTone") &&
          dashboardCanvasReadinessModelSource.includes("export function buildDashboardReadinessModel(") &&
          dashboardCanvasReadinessModelSource.includes("export function buildDashboardEvidenceFocus(") &&
          dashboardCanvasReadinessModelSource.includes("Agent 生成") &&
          dashboardOverviewStripSource.includes("Editable asset, not a black-box result") &&
          dashboardCanvasReadinessModelSource.includes("source-intelligence:"),
      },
    {
        label: "dashboard-canvas-plan-model-boundary",
        ok: existsSync(join(root, "src", "dashboardCanvasPlanModel.ts")) &&
          dashboardCanvasViewModelSource.includes('from "./dashboardCanvasPlanModel"') &&
          dashboardCanvasViewModelSource.includes("summarizeDashboardWidgetPlan(widgetPlan)") &&
          !dashboardCanvasSource.includes('from "../dashboardCanvasPlanModel"') &&
          !dashboardCanvasSource.includes("summarizeDashboardWidgetPlan(widgetPlan)") &&
          dashboardModuleSavePanelSource.includes("dashboardModuleSaveReceipt(moduleSaveResult") &&
          !dashboardCanvasSource.includes("function moduleResultNumber(") &&
          !dashboardCanvasSource.includes("const plannedWidgets = Array.isArray(widgetPlan?.plannedWidgets)") &&
          !dashboardCanvasSource.includes("const businessTemplateCount = typeof widgetPlan?.templateCount") &&
          !dashboardCanvasSource.includes("预演完成，确认前不会写入") &&
          dashboardCanvasPlanModelSource.includes("export type DashboardWidgetPlanSummary") &&
          dashboardCanvasPlanModelSource.includes("export type DashboardModuleSaveReceipt") &&
          dashboardCanvasPlanModelSource.includes("function moduleResultNumber(") &&
          dashboardCanvasPlanModelSource.includes("export function summarizeDashboardWidgetPlan(") &&
          dashboardCanvasPlanModelSource.includes("export function dashboardModuleSaveReceipt(") &&
          dashboardCanvasPlanModelSource.includes("savedDashboardModules") &&
          dashboardCanvasPlanModelSource.includes("确认前不会写入") &&
          dashboardCanvasPlanModelSource.includes("刷新后仍会保留"),
      },
    {
        label: "dashboard-canvas-filter-model-boundary",
        ok: existsSync(join(root, "src", "dashboardCanvasFilterModel.ts")) &&
          dashboardCanvasSource.includes('from "../dashboardCanvasFilterModel"') &&
          dashboardCanvasStateSource.includes('from "./dashboardCanvasFilterModel"') &&
          dashboardCanvasSource.includes("normalizeDashboardFilters(dashboard.layout)") &&
          dashboardCanvasStateSource.includes("normalizeWidgetFilters(selectedWidget.config?.filters)") &&
          dashboardCanvasViewModelSource.includes("buildNextWidgetFilters({") &&
          !dashboardCanvasSource.includes("buildNextWidgetFilters({") &&
          dashboardCanvasSource.includes("filterOperators={filterOperators}") &&
          dashboardCanvasSource.includes("operatorLabel={operatorLabel}") &&
          !dashboardCanvasSource.includes("function normalizeDashboardFilters(") &&
          !dashboardCanvasSource.includes("function operatorLabel(") &&
          !dashboardCanvasSource.includes('const filterOperators = ["contains"') &&
          !dashboardCanvasSource.includes("...widgetFilters.map((filter) => ({ field: filter.field") &&
          dashboardFilterWorkbenchSource.includes("filterOperators.map") &&
          dashboardFilterWorkbenchSource.includes("operatorLabel(filter.operator)") &&
          dashboardCanvasFilterModelSource.includes("export const filterOperators") &&
          dashboardCanvasFilterModelSource.includes("export function normalizeDashboardFilterList(") &&
          dashboardCanvasFilterModelSource.includes("export function normalizeDashboardFilters(") &&
          dashboardCanvasFilterModelSource.includes("export function normalizeWidgetFilters(") &&
          dashboardCanvasFilterModelSource.includes("export function buildNextWidgetFilters(") &&
          dashboardCanvasFilterModelSource.includes("export function operatorLabel(") &&
          dashboardCanvasFilterModelSource.includes("scope = \"dashboard\"") &&
          dashboardCanvasFilterModelSource.includes("normalizeDashboardFilterList(value, \"widget\")") &&
          dashboardCanvasSourceSwitchModelSource.includes("normalizeWidgetFilters(config.filters)"),
      },
    {
        label: "dashboard-canvas-field-model-boundary",
        ok: existsSync(join(root, "src", "dashboardCanvasFieldModel.ts")) &&
          dashboardCanvasStateSource.includes('from "./dashboardCanvasFieldModel"') &&
          dashboardCanvasStateSource.includes("buildDashboardCanvasFieldModel({") &&
          dashboardCanvasSource.includes("availableFilterFields") &&
          dashboardCanvasSource.includes("usableViews") &&
          dashboardCanvasSource.includes("draftDimensions") &&
          dashboardCanvasSource.includes("draftMeasures") &&
          dashboardCanvasSource.includes("draftViews") &&
          !dashboardCanvasSource.includes('from "../dashboardCanvasFieldModel"') &&
          !dashboardCanvasSource.includes("buildDashboardCanvasFieldModel({") &&
          !dashboardCanvasSource.includes("const tableFields = workbench.fields.filter(") &&
          !dashboardCanvasSource.includes("const filterableFields = tableFields.filter(") &&
          !dashboardCanvasSource.includes("const currentTableViews = savedViews.filter(") &&
          !dashboardCanvasSource.includes("const draftFields = workbench.fields.filter(") &&
          !dashboardCanvasSource.includes("const draftDimensions = draftFields.filter((field)") &&
          !dashboardCanvasSource.includes("const draftMeasures = draftFields.filter((field)") &&
          !dashboardCanvasSource.includes("const draftViews = savedViews.filter(") &&
          dashboardCanvasFieldModelSource.includes("export type DashboardCanvasFieldModel") &&
          dashboardCanvasFieldModelSource.includes("export function isDashboardDimensionField(") &&
          dashboardCanvasFieldModelSource.includes("export function isDashboardMeasureField(") &&
          dashboardCanvasFieldModelSource.includes("export function buildDashboardCanvasFieldModel(") &&
          dashboardCanvasFieldModelSource.includes("availableFilterFields = filterableFields.length ? filterableFields : tableFields") &&
          dashboardCanvasFieldModelSource.includes("usableViews = currentTableViews.length ? currentTableViews : savedViews") &&
          dashboardCanvasFieldModelSource.includes("draftFields.filter(isDashboardDimensionField)") &&
          dashboardCanvasFieldModelSource.includes("draftFields.filter(isDashboardMeasureField)"),
      },
    {
        label: "dashboard-canvas-state-hook-boundary",
        ok: existsSync(join(root, "src", "useDashboardCanvasState.ts")) &&
          dashboardCanvasSource.includes('from "../useDashboardCanvasState"') &&
          dashboardCanvasSource.includes("useDashboardCanvasState({") &&
          dashboardCanvasSource.includes("savedRelationships,") &&
          !dashboardCanvasSource.includes('from "react"') &&
          !dashboardCanvasSource.includes("useEffect(() =>") &&
          !dashboardCanvasSource.includes("const [draftName, setDraftName]") &&
          !dashboardCanvasSource.includes("const [selectedWidgetKey, setSelectedWidgetKey]") &&
          !dashboardCanvasSource.includes("const selectedWidget = dashboardWidgets.find") &&
          dashboardCanvasStateSource.includes("export function useDashboardCanvasState(") &&
          dashboardCanvasStateSource.includes("type DashboardCanvasStateOptions") &&
          dashboardCanvasStateSource.includes("const [draftName, setDraftName] = useState") &&
          dashboardCanvasStateSource.includes("const [selectedWidgetKey, setSelectedWidgetKey] = useState") &&
          dashboardCanvasStateSource.includes("const selectedWidget = useMemo(") &&
          dashboardCanvasStateSource.includes("orderedWidgets.find((widget) => widget.widget_key === selectedWidgetKey)") &&
          dashboardCanvasStateSource.includes("const fieldModel = useMemo(() => buildDashboardCanvasFieldModel({") &&
          dashboardCanvasStateSource.includes("setDraftName(dashboard?.name ?? \"\")") &&
          dashboardCanvasStateSource.includes("setCanvasWidthMode(dashboard.layout?.canvasWidthMode === \"center\" ? \"center\" : \"stretch\")") &&
          dashboardCanvasStateSource.includes("setSourceSwitchTableKey(dashboard.default_table_key)") &&
          dashboardCanvasStateSource.includes("setFilterField((current)") &&
          dashboardCanvasStateSource.includes("setSelectedViewKey((current)") &&
          dashboardCanvasStateSource.includes("setSelectedRelationshipKey((current)") &&
          dashboardCanvasStateSource.includes("setSelectedWidgetKey((current)") &&
          dashboardCanvasStateSource.includes("setWidgetDraft(widgetDraftFromWidget(widget))") &&
          dashboardCanvasStateSource.includes("setWidgetFilterField((current)"),
      },
    {
        label: "dashboard-canvas-actions-hook-boundary",
        ok: existsSync(join(root, "src", "useDashboardCanvasActions.ts")) &&
          dashboardCanvasSource.includes('from "../useDashboardCanvasActions"') &&
          dashboardCanvasSource.includes("useDashboardCanvasActions({") &&
          dashboardCanvasSource.includes("onDashboardWidgetOperation,") &&
          dashboardCanvasSource.includes("selectedWidgetKey: selectedWidget?.widget_key") &&
          !dashboardCanvasSource.includes("async function runDashboardOperation") &&
          !dashboardCanvasSource.includes("function dashboardModulePayload") &&
          !dashboardCanvasSource.includes("function sourceSwitchModulePayload") &&
          !dashboardCanvasSource.includes("const widgetSettingsPayload = (confirm: boolean)") &&
          !dashboardCanvasSource.includes("buildRelationshipSavePayload(recommendation, confirm)") &&
          dashboardCanvasActionsSource.includes("export function useDashboardCanvasActions(") &&
          dashboardCanvasActionsSource.includes("type DashboardCanvasActionsOptions") &&
          dashboardCanvasActionsSource.includes("async function runDashboardOperation(") &&
          dashboardCanvasActionsSource.includes("async function runFilterOperation(") &&
          dashboardCanvasActionsSource.includes("async function runWidgetOperation(") &&
          dashboardCanvasActionsSource.includes("function dashboardModulePayload(") &&
          dashboardCanvasActionsSource.includes("function sourceSwitchModulePayload(") &&
          dashboardCanvasActionsSource.includes("async function runModuleSave(") &&
          dashboardCanvasActionsSource.includes("async function runSourceSwitch(") &&
          dashboardCanvasActionsSource.includes("async function runBusinessTemplate(") &&
          dashboardCanvasActionsSource.includes("async function runDashboardAsk(") &&
          dashboardCanvasActionsSource.includes("async function runRelationshipSave(") &&
          dashboardCanvasActionsSource.includes("const widgetSettingsPayload = (confirm: boolean)") &&
          dashboardCanvasActionsSource.includes("return {"),
      },
    {
        label: "dashboard-canvas-action-runner-boundary",
        ok: existsSync(join(root, "src", "useDashboardCanvasActionRunner.ts")) &&
          dashboardCanvasActionsSource.includes('from "./useDashboardCanvasActionRunner"') &&
          dashboardCanvasActionsSource.includes("useDashboardCanvasActionRunner()") &&
          dashboardCanvasActionsSource.includes("runVoidAction(label, () => onDashboardOperation(options))") &&
          dashboardCanvasActionsSource.includes("runVoidAction(label, () => onDashboardFilterOperation(options))") &&
          dashboardCanvasActionsSource.includes("runPlanAction(label, () => onDashboardWidgetOperation(options))") &&
          dashboardCanvasActionsSource.includes("runPlanAction(label, () => onDashboardModulesSave(dashboardModulePayload(confirm)))") &&
          dashboardCanvasActionsSource.includes("runPlanAction(label, () => onDashboardModulesSave(sourceSwitchModulePayload(confirm)))") &&
          dashboardCanvasActionsSource.includes("runPlanAction(label, () => onBusinessDashboardOperation(options))") &&
          dashboardCanvasActionsSource.includes("function singleChartAgentPrompt(") &&
          dashboardCanvasActionsSource.includes("matchedField?.table_key || dashboard.default_table_key") &&
          dashboardCanvasActionsSource.includes('label === "dashboard-task-explain"') &&
          dashboardCanvasActionsSource.includes("runVoidAction(label, () => onAsk(routedPrompt))") &&
          dashboardCanvasActionsSource.includes("runPlanAction(label, () => onRelationshipSave(payload))") &&
          !dashboardCanvasSource.includes('from "../useDashboardCanvasActionRunner"') &&
          !dashboardCanvasSource.includes("useDashboardCanvasActionRunner()") &&
          !dashboardCanvasSource.includes("runVoidAction(label") &&
          !dashboardCanvasSource.includes("runPlanAction(label") &&
          !dashboardCanvasSource.includes("const [busy, setBusy] = useState") &&
          !dashboardCanvasSource.includes("const [widgetPlan, setWidgetPlan] = useState") &&
          !dashboardCanvasSource.includes("setBusy(label);") &&
          !dashboardCanvasSource.includes("setWidgetPlan(result);") &&
          dashboardCanvasActionRunnerSource.includes("export function useDashboardCanvasActionRunner(") &&
          dashboardCanvasActionRunnerSource.includes("const [busy, setBusy] = useState<string | null>(null)") &&
          dashboardCanvasActionRunnerSource.includes("const [widgetPlan, setWidgetPlan] = useState<PlanResult | null>(null)") &&
          dashboardCanvasActionRunnerSource.includes("async function runVoidAction(") &&
          dashboardCanvasActionRunnerSource.includes("async function runPlanAction(") &&
          dashboardCanvasActionRunnerSource.includes("setWidgetPlan(result)") &&
          dashboardCanvasActionRunnerSource.includes("setBusy(null)"),
      },
    {
        label: "dashboard-canvas-relationship-model-boundary",
        ok: existsSync(join(root, "src", "dashboardCanvasRelationshipModel.ts")) &&
          dashboardCanvasActionsSource.includes('from "./dashboardCanvasRelationshipModel"') &&
          dashboardCanvasActionsSource.includes("buildRelationshipSavePayload(recommendation, confirm)") &&
          dashboardCanvasActionsSource.includes("if (!payload) return") &&
          !dashboardCanvasSource.includes('from "../dashboardCanvasRelationshipModel"') &&
          !dashboardCanvasSource.includes("buildRelationshipSavePayload(recommendation, confirm)") &&
          !dashboardCanvasSource.includes("if (!payload) return") &&
          !dashboardCanvasSource.includes("relationshipPrimaryMapping(recommendation)") &&
          !dashboardCanvasSource.includes("relationshipRecommendationKey(recommendation)") &&
          !dashboardCanvasSource.includes("relationshipMappingLabel(recommendation)") &&
          dashboardRelationshipRecommendationPanelSource.includes("relationshipPrimaryMapping(recommendation)") &&
          dashboardRelationshipRecommendationPanelSource.includes("relationshipRecommendationKey(recommendation)") &&
          dashboardRelationshipRecommendationPanelSource.includes("relationshipMappingLabel(recommendation)") &&
          !dashboardCanvasSource.includes("const mapping = recommendation.fieldMappings?.[0]") &&
          !dashboardCanvasSource.includes("leftTable: recommendation.leftTableKey") &&
          !dashboardCanvasSource.includes("joinType: recommendation.joinType || \"left\"") &&
          !dashboardCanvasSource.includes("limit: 20") &&
          dashboardCanvasRelationshipModelSource.includes("export type RelationshipSavePayload") &&
          dashboardCanvasRelationshipModelSource.includes("export function relationshipPrimaryMapping(") &&
          dashboardCanvasRelationshipModelSource.includes("export function relationshipRecommendationKey(") &&
          dashboardCanvasRelationshipModelSource.includes("export function relationshipMappingLabel(") &&
          dashboardCanvasRelationshipModelSource.includes("export function buildRelationshipSavePayload(") &&
          dashboardCanvasRelationshipModelSource.includes("recommendation.fieldMappings?.[0] ?? null") &&
          dashboardCanvasRelationshipModelSource.includes("joinType: recommendation.joinType || \"left\"") &&
          dashboardCanvasRelationshipModelSource.includes("limit: 20"),
      },
    {
        label: "frontend-saved-view-evidence-click-path",
        ok: viewWorkspaceSource.includes('data-testid="view-evidence-button"') &&
          viewWorkspaceSource.includes('data-testid="view-empty-state"') &&
          viewWorkspaceSource.includes("onOpenSources: () => void") &&
          viewWorkspaceSource.includes("const pageCount = Math.max(1") &&
          viewWorkspaceSource.includes('source: "saved-view"') &&
          viewWorkspaceSource.includes('"saved-view-config"') &&
          viewWorkspaceSource.includes('"table-query-contract"') &&
          viewWorkspaceSource.includes("source-intelligence:") &&
          appSource.includes("onOpenEvidence={handleOpenEvidence}") &&
          evidenceViewSource.includes("focus?.viewKey") &&
          evidenceViewSource.includes("data-testid=\"evidence-focus-detail\"") &&
          evidenceViewModelSource.includes("保存视图口径") &&
          evidenceViewModelSource.includes("Detail query receipt"),
      },
    {
        label: "frontend-view-agent-task-strip",
        ok: viewAgentTaskStripSource.includes('data-testid="view-agent-task-strip"') &&
          viewAgentTaskStripSource.includes('import { AgentPromptGrid } from "./AgentPromptGrid"') &&
          viewAgentTaskStripSource.includes("<AgentPromptGrid") &&
          viewAgentTaskStripSource.includes('testId="view-agent-prompt-grid"') &&
          viewAgentTaskStripSource.includes('itemTestIdPrefix="view-agent-prompt"') &&
          viewWorkspaceSource.includes("buildViewAgentPrompts") &&
          viewWorkspaceModelSource.includes("export function buildViewAgentPrompts") &&
          viewWorkspaceModelSource.includes('"explain"') &&
          viewWorkspaceModelSource.includes('"find-anomaly"') &&
          viewWorkspaceModelSource.includes('"dashboard-widget"') &&
          viewWorkspaceModelSource.includes("不要创建待确认修改") &&
          viewWorkspaceModelSource.includes("不要直接修改数据") &&
          viewWorkspaceModelSource.includes("先不要直接写入") &&
          agentPromptGridSource.includes("onAsk(item.prompt)") &&
          appSource.includes("onAsk={handleAgentCommandAsk}") &&
          viewWorkspaceSource.includes('import "./viewWorkspace.css"') &&
          viewWorkspaceStylesSource.includes(".viewWorkspaceGrid {") &&
          viewAgentTaskStripSource.includes('import "./viewAgentTaskStrip.css"') &&
          viewAgentTaskStripStylesSource.includes(".viewAgentTaskStrip {") &&
          !globalStylesSource.includes(".viewWorkspaceGrid {") &&
          stylesSource.includes(".viewAgentTaskStrip") &&
          stylesSource.includes(".agentPromptGrid") &&
          stylesSource.includes(".viewAgentTaskStrip .agentPromptGrid button"),
      },
    {
        label: "view-agent-task-strip-component-boundary",
        ok: existsSync(join(root, "src", "components", "ViewAgentTaskStrip.tsx")) &&
          viewWorkspaceSource.includes('import("./ViewAgentTaskStrip")') &&
          viewWorkspaceSource.includes("const ViewAgentTaskStrip = lazy(loadViewAgentTaskStrip)") &&
          viewWorkspaceSource.includes("setAgentTaskMounted(true)") &&
          viewWorkspaceSource.includes("<ViewAgentTaskStrip") &&
          !viewWorkspaceSource.includes('data-testid="view-agent-task-strip"') &&
          viewAgentTaskStripSource.includes("type ViewAgentTaskStripProps") &&
          viewAgentTaskStripSource.includes("viewAgentPrompts: ViewAgentPrompt[]") &&
          viewAgentTaskStripSource.includes("不用导出表格，直接问当前视图") &&
          viewAgentTaskStripSource.includes('itemTestIdPrefix="view-agent-prompt"'),
      },
    {
        label: "frontend-saved-view-dashboard-bridge",
        ok: viewWorkspaceSource.includes("<ViewDashboardBridgePanel") &&
          viewDashboardBridgePanelSource.includes('data-testid="view-dashboard-bridge"') &&
          viewDashboardBridgePanelSource.includes('data-testid="view-dashboard-bridge-facts"') &&
          viewDashboardBridgePanelSource.includes('data-testid="view-dashboard-bridge-steps"') &&
          viewDashboardBridgePanelSource.includes('data-testid={`view-bridge-step-${step.key}`}') &&
          viewDashboardBridgePanelSource.includes('data-testid="view-bridge-evidence"') &&
          viewDashboardBridgePanelSource.includes('data-testid="view-bridge-agent-widget"') &&
          viewWorkspaceSource.includes("viewCanFeedDashboard") &&
          viewWorkspaceSource.includes("bridgeEvidenceCount") &&
          viewWorkspaceSource.includes("bridgeFilterScopeCount") &&
          viewWorkspaceSource.includes("viewReadinessLabel") &&
          viewWorkspaceSource.includes("viewScopeScore") &&
          viewWorkspaceSource.includes("ViewOperationReceipt") &&
          viewWorkspaceSource.includes('from "../viewWorkspaceModel"') &&
          viewWorkspaceSource.includes("buildViewBridgeSteps") &&
          viewWorkspaceModelSource.includes("export type ViewOperationReceipt") &&
          viewWorkspaceModelSource.includes("export function viewColumns") &&
          viewWorkspaceModelSource.includes("export function viewFilters") &&
          viewWorkspaceModelSource.includes("export function viewSort") &&
          viewWorkspaceModelSource.includes("export function viewSearch") &&
          viewWorkspaceModelSource.includes("export function viewName") &&
          viewWorkspaceModelSource.includes("export function buildViewBridgeSteps") &&
          !viewWorkspaceSource.includes("function viewColumns(") &&
          !viewWorkspaceSource.includes("function viewFilters(") &&
          !viewWorkspaceSource.includes("function viewSort(") &&
          !viewWorkspaceSource.includes("function viewSearch(") &&
          !viewWorkspaceSource.includes("function viewName(") &&
          viewWorkspaceSource.includes("runViewQueryAction") &&
          viewWorkspaceSource.includes("runSaveCurrentSearch") &&
          viewWorkspaceSource.includes("runCopyView") &&
          viewWorkspaceSource.includes("runDeleteView") &&
          viewWorkspaceSource.includes('data-testid="view-operation-receipt"') &&
          viewWorkspaceSource.includes('data-testid="view-operation-technical-details"') &&
          viewWorkspaceSource.includes("View scope and paging") &&
          viewWorkspaceSource.includes("视图已切换并刷新") &&
          viewWorkspaceSource.includes("当前搜索已保存到视图") &&
          viewWorkspaceModelSource.includes("固定视图口径") &&
          viewWorkspaceModelSource.includes("Refresh rows") &&
          viewWorkspaceModelSource.includes("Agent creates a pending change only") &&
          viewDashboardBridgePanelSource.includes("生成一个待确认的看板组件") &&
          viewDashboardBridgePanelSource.includes("不要直接写入") &&
          viewWorkspaceSource.includes('data-testid="view-query-diagnostics"') &&
          viewWorkspaceSource.includes('data-testid="view-query-technical-details"') &&
          stylesSource.includes(".viewOperationReceipt") &&
          viewWorkspaceSource.includes("看板来源") &&
          !viewWorkspaceSource.includes('<span>{biText("执行", "runtime")}</span>') &&
          stylesSource.includes(".viewBridgePanel") &&
          stylesSource.includes(".viewBridgeFacts") &&
          stylesSource.includes(".viewBridgeSteps") &&
          stylesSource.includes(".viewBridgeStep.ready") &&
          stylesSource.includes(".viewBridgeActions"),
      },
    {
        label: "view-dashboard-bridge-panel-component-boundary",
        ok: existsSync(join(root, "src", "components", "ViewDashboardBridgePanel.tsx")) &&
          viewWorkspaceSource.includes('import("./ViewDashboardBridgePanel")') &&
          viewWorkspaceSource.includes("const ViewDashboardBridgePanel = lazy(loadViewDashboardBridgePanel)") &&
          viewWorkspaceSource.includes("setDashboardBridgeMounted(true)") &&
          viewWorkspaceSource.includes("<ViewDashboardBridgePanel") &&
          !viewWorkspaceSource.includes('data-testid="view-dashboard-bridge"') &&
          viewDashboardBridgePanelSource.includes("type ViewDashboardBridgePanelProps") &&
          viewDashboardBridgePanelSource.includes("bridgeSteps: ViewBridgeStep[]") &&
          viewDashboardBridgePanelSource.includes("openViewEvidence: () => void") &&
          viewDashboardBridgePanelSource.includes("viewCanFeedDashboard: boolean") &&
          viewDashboardBridgePanelSource.includes('import "./viewDashboardBridgePanel.css"') &&
          viewDashboardBridgePanelStylesSource.includes(".viewBridgePanel {") &&
          viewDashboardBridgePanelSource.includes('data-testid="view-bridge-agent-widget"'),
      },
    {
        label: "view-saved-list-panel-component-boundary",
        ok: existsSync(join(root, "src", "components", "ViewSavedListPanel.tsx")) &&
          viewWorkspaceSource.includes('import { ViewSavedListPanel } from "./ViewSavedListPanel"') &&
          viewWorkspaceSource.includes("<ViewSavedListPanel") &&
          !viewWorkspaceSource.includes('<aside className="viewListPanel">') &&
          viewSavedListPanelSource.includes("type ViewSavedListPanelProps") &&
          viewSavedListPanelSource.includes('className="viewListPanel"') &&
          viewSavedListPanelSource.includes('className={view.view_key === activeView?.view_key ? "viewRow active" : "viewRow"}') &&
          viewSavedListPanelSource.includes("view.columnCount ?? viewColumns(view).length") &&
          viewSavedListPanelSource.includes("view.filterCount ?? viewFilters(view).length"),
      },
    {
        label: "frontend-query-workbench-diagnostics-simplified",
        ok: sourceWorkbenchQueryFormulaPanelSource.includes('data-testid="source-query-runtime-technical"') &&
          sourceWorkbenchQueryFormulaPanelSource.includes("结果可刷新") &&
          sourceWorkbenchQueryFormulaPanelSource.includes("等待连接") &&
          sourceWorkbenchQueryFormulaPanelSource.includes("查看取数诊断") &&
          sourceWorkbenchQueryFormulaPanelSource.includes("已切换到备用查询") &&
          !sourceWorkbenchSource.includes("Fell back to SQLite") &&
          viewWorkspaceSource.includes('data-testid="view-query-diagnostics"') &&
          viewWorkspaceSource.includes("查看分页、执行引擎和查询口径") &&
          viewWorkspaceSource.includes("查看生成查询"),
      },
    {
        label: "frontend-loading-state-not-fallback-sample",
        ok: appSource.includes('type ApiMode') &&
          appSource.includes('from "./appWorkspaceModel"') &&
          appWorkspaceModelSource.includes('export type ApiMode = "loading" | "live" | "fallback"') &&
          appWorkspaceModelSource.includes("export const connectingStatus: WorkspaceStatus") &&
          appWorkspaceModelSource.includes('notes: ["Connecting to local data service..."]') &&
          appSource.includes('apiMode === "loading" ? connectingStatus : status') &&
          topBarSource.includes('apiMode === "loading"') &&
          topBarSource.includes('biText("正在连接", "Connecting")'),
      }
  );
}
