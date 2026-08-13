export function appendSourceContractExtendedChecks(context) {
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
    homeOverviewSource,
    implementationStatusSource,
    join,
    metricSemanticRepairActionsSource,
    relationshipAutoModelGraphModelSource,
    relationshipAutoModelGraphSource,
    root,
    run,
    serverDashboardRoutesSource,
    serverSourceRoutesSource,
    serverWorkspaceRoutesSource,
    sourceCoverageAllRuns,
    sourceCoverageRuns,
    sourceIntelligenceRunModelSource,
    sourceWorkbenchActionPanelSource,
    sourceWorkbenchAdvancedModulesSource,
    sourceWorkbenchDeferredModulesSource,
    sourceWorkbenchAdvancedPanelsSource,
    sourceWorkbenchAdvancedStylesSource,
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
  const appSource = `${appEntrySource}\n${appMainViewSource}`;
  checks.push(

    {
        label: "frontend-field-semantic-readiness",
        ok: sourceWorkbenchSource.includes("buildFieldSemanticReadiness(selectedFields)") &&
          sourceWorkbenchModelSource.includes("export function buildFieldSemanticReadiness") &&
          sourceWorkbenchFieldMetricPanelSource.includes("<SourceWorkbenchFieldSemanticPanel") &&
          sourceWorkbenchFieldSemanticPanelSource.includes('data-testid="field-semantic-readiness"') &&
          sourceWorkbenchFieldSemanticPanelSource.includes('data-testid="field-semantic-readiness-cards"') &&
          sourceWorkbenchFieldSemanticPanelSource.includes('data-testid="field-semantic-ready"') &&
          sourceWorkbenchFieldSemanticPanelSource.includes('data-testid="field-semantic-relationship"') &&
          sourceWorkbenchFieldSemanticPanelSource.includes('data-testid="field-semantic-review"') &&
          sourceWorkbenchFieldSemanticPanelSource.includes('data-testid="field-semantic-agent-review"') &&
          sourceWorkbenchFieldSemanticPanelSource.includes('data-testid="field-semantic-technical-details"') &&
          sourceWorkbenchFieldSemanticPanelSource.includes("检查字段用途") &&
          sourceWorkbenchFieldSemanticPanelSource.includes("逐字段调整") &&
          !sourceWorkbenchSource.includes("semantic.set 草案") &&
          stylesSource.includes(".fieldSemanticReadiness") &&
          stylesSource.includes(".fieldSemanticCards") &&
          stylesSource.includes(".fieldSemanticCard.review") &&
          stylesSource.includes(".fieldSemanticTechnical"),
      },
    {
        label: "b-dashboard-filters-write-boundary",
        ok: byLabel["cli-filter-add-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-filter-add-confirm"].parsed?.confirmed === true &&
          byLabel["cli-filter-list"].parsed?.filters?.some((filter) => filter.field === "channel" && filter.value === "Douyin") &&
          byLabel["cli-filter-remove-stale-dry-run"].parsed?.requiresConfirmation === true &&
          Array.isArray(byLabel["cli-filter-remove-stale-dry-run"].parsed?.staleFilters) &&
          byLabel["cli-filter-clear-dry-run"].parsed?.requiresConfirmation === true,
      },
    {
        label: "b-performance-indexes-duckdb-boundary",
        ok: byLabel["cli-recommend-indexes"].parsed?.recommendations?.some((item) => item.field === "channel" && item.engine === "duckdb") &&
          byLabel["cli-create-index-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-create-index-dry-run"].parsed?.proposed?.engine === "duckdb" &&
          byLabel["cli-create-index-confirm"].parsed?.confirmed === true &&
          byLabel["cli-create-index-confirm"].parsed?.createdIndex?.field === "channel" &&
          byLabel["cli-create-index-confirm"].parsed?.createdIndex?.replicaTable?.startsWith("__aibi_replica_") &&
          Number.isInteger(byLabel["cli-create-index-confirm"].parsed?.syncedRows) &&
          byLabel["cli-create-index-confirm"].parsed?.syncedRows >= 0 &&
          ["current", "published"].includes(byLabel["cli-create-index-confirm"].parsed?.replicaStatus),
      },
    {
        label: "frontend-widget-filter-routing",
        ok: byLabel["frontend-widget-filter-model"].parsed?.ok === true &&
          byLabel["frontend-widget-filter-model"].parsed?.localRows?.[0]?.label === "Douyin" &&
          byLabel["frontend-widget-filter-model"].parsed?.globalRows?.[0]?.label === "JD",
      },
    {
        label: "frontend-slicer-cross-filter-routing",
        ok: byLabel["frontend-slicer-cross-filter-model"].parsed?.ok === true &&
          byLabel["frontend-slicer-cross-filter-model"].parsed?.emptyCount === 0 &&
          byLabel["frontend-slicer-cross-filter-model"].parsed?.slicer?.drillDown === false &&
          byLabel["frontend-slicer-cross-filter-model"].parsed?.slicer?.globalFilterTarget === true &&
          byLabel["frontend-slicer-cross-filter-model"].parsed?.filtered?.[0]?.label === "JD",
      },
    {
        label: "frontend-relationship-widget-hydration",
        ok: byLabel["frontend-relationship-widget-model"].parsed?.ok === true &&
          byLabel["frontend-relationship-widget-model"].parsed?.relationship?.relationKey === "orders_refunds_order_id_order_id",
      },
    {
        label: "frontend-b-widget-kit-all-types",
        ok: bWidgetKitSource.includes("<BiDashboardWidgetCard") &&
          !bWidgetKitSource.includes("data-testid={`b-widget-${widget.type}`}") &&
          bDashboardWidgetCardSource.includes("data-testid={`b-widget-${widget.type}`}") &&
          bWidgetKitSource.includes("<BiDashboardWidgetKitOverview") &&
          bWidgetKitOverviewSource.includes("data-testid=\"b-dashboard-read-path\"") &&
          bWidgetKitOverviewSource.includes("B_WIDGET_READING_PURPOSES") &&
          bWidgetKitModelSource.includes("export const B_WIDGET_READING_PURPOSES") &&
          bWidgetKitOverviewSource.includes("不用先学组件配置") &&
          bWidgetKitSource.includes("evidenceState") &&
          bDashboardWidgetCardSource.includes("queryRelationship") &&
          bDashboardWidgetCardSource.includes('from "../biDashboardPresentation"') &&
          biDashboardPresentationSource.includes("export function formatWidgetValue") &&
          biDashboardPresentationSource.includes("export function paletteColors") &&
          biDashboardPresentationSource.includes("export function catalogByType") &&
          biDashboardPresentationSource.includes("const paletteMap") &&
          existsSync(join(root, "src", "biDashboardValueModel.ts")) &&
          biDashboardValueModelSource.includes("export function toStringValue") &&
          biDashboardModelSource.includes('import { toStringValue } from "./biDashboardValueModel"') &&
          biDashboardWidgetFactorySource.includes('import { toStringValue } from "./biDashboardValueModel"') &&
          !biDashboardModelSource.includes("function toStringValue(") &&
          !biDashboardWidgetFactorySource.includes("function toStringValue(") &&
          !biDashboardModelSource.includes("export function formatWidgetValue") &&
          !biDashboardModelSource.includes("export function paletteColors") &&
          !biDashboardModelSource.includes("export function catalogByType") &&
          !biDashboardModelSource.includes("const paletteMap") &&
          bDashboardWidgetCardSource.includes('from "../biDashboardRuntime"') &&
          biDashboardModelSource.includes('export { buildBiDashboardWidgets } from "./biDashboardWidgetFactory"') &&
          biDashboardWidgetFactorySource.includes("export function buildBiDashboardWidgets") &&
          biDashboardWidgetFactorySource.includes("function hydrateStoredWidget") &&
          biDashboardWidgetFactorySource.includes("function baseWidget") &&
          biDashboardWidgetFactorySource.includes("function latestRunEvidence") &&
          biDashboardWidgetFactorySource.includes("return stored.sort") &&
          !biDashboardWidgetFactorySource.includes("b-widget-metric-default") &&
          !biDashboardModelSource.includes('import { safeQueryInfo } from "./biDashboardRuntime"') &&
          !biDashboardModelSource.includes("function hydrateStoredWidget") &&
          !biDashboardModelSource.includes("function relationshipForWidget") &&
          !biDashboardModelSource.includes("function baseWidget") &&
          biDashboardRuntimeSource.includes("export function aggregateWidgetRows") &&
          biDashboardRuntimeSource.includes("export function calculateWidgetMetricValue") &&
          biDashboardRuntimeSource.includes("export function applyBiDashboardFilters") &&
          biDashboardRuntimeSource.includes("export function rowsFromQuery") &&
          !biDashboardModelSource.includes("export function aggregateWidgetRows") &&
          !biDashboardModelSource.includes("export function calculateWidgetMetricValue") &&
          !biDashboardModelSource.includes("export function applyBiDashboardFilters") &&
          !biDashboardModelSource.includes("export function rowsFromQuery") &&
          bWidgetKitSource.includes("data-testid=\"b-slicer-selection-bar\"") &&
          dashboardBusinessTemplatePanelSource.includes("data-testid=\"business-template-panel\"") &&
          dashboardRelationshipRecommendationPanelSource.includes("data-testid=\"relationship-recommendation-panel\"") &&
          ["metric", "bar", "line", "pie", "table", "text", "slicer"].every((type) => bWidgetKitOverviewSource.includes(`b-read-path-${type}`) || bWidgetKitOverviewSource.includes("data-testid={`b-read-path-${item.type}`}")) &&
          ["metric", "bar", "line", "pie", "table", "text", "slicer"].every((type) => bWidgetModelSource.includes(`"${type}"`)) &&
          bWidgetModelSource.includes("B_DASHBOARD_WIDGET_CATALOG") &&
          bWidgetModelSource.includes("B_DASHBOARD_DATA_MODES") &&
          stylesSource.includes(".bReadPath") &&
          stylesSource.includes(".bReadPathSteps") &&
          stylesSource.includes(".bReadPathStep.ready") &&
          stylesSource.includes(".bPieLegend button") &&
          stylesSource.includes("min-height: 30px"),
      },
    {
        label: "frontend-relationship-impact-panel",
        ok: sourceWorkbenchRelationshipPanelSource.includes("data-testid=\"relationship-impact-panel\"") &&
          sourceWorkbenchRelationshipPanelSource.includes("data-testid=\"relationship-recommendation-apply-card\"") &&
          sourceWorkbenchRelationshipPanelSource.includes("data-testid=\"relationship-apply-recommendation\"") &&
          sourceWorkbenchRelationshipPanelSource.includes('data-testid="relationship-technical-details"') &&
          sourceWorkbenchRelationshipPanelSource.includes("applyRelationshipRecommendation") &&
          sourceWorkbenchRelationshipPanelSource.includes("relationshipDecisionState") &&
          sourceWorkbenchRelationshipPanelSource.includes("保存业务连接") &&
          sourceWorkbenchRelationshipPanelSource.includes("受控关联查询") &&
          sourceWorkbenchRelationshipPanelSource.includes("可连接键") &&
          sourceWorkbenchRelationshipPanelSource.includes("匹配度") &&
          sourceWorkbenchRelationshipPanelSource.includes('data-testid="relationship-diagnostics-technical"') &&
          sourceWorkbenchRelationshipPanelSource.includes('data-testid="relationship-warning-details"') &&
          stylesSource.includes(".relationshipImpactPanel") &&
          stylesSource.includes(".relationshipRecommendationCard") &&
          stylesSource.includes(".relationshipTechnicalDetails") &&
          stylesSource.includes(".relationshipDiagnosticsTechnical"),
      },
    {
        label: "frontend-source-advanced-business-controls",
        ok: sourceWorkbenchQueryFormulaPanelSource.includes("计算字段和指标") &&
          sourceWorkbenchQueryFormulaPanelSource.includes('data-testid="formula-technical-details"') &&
          sourceWorkbenchQueryFormulaPanelSource.includes("查看编译后的查询") &&
          sourceWorkbenchQueryFormulaPanelSource.includes("Preview save") &&
          !sourceWorkbenchSource.includes("Formula DSL") &&
          !sourceWorkbenchSource.includes("Dry-run save") &&
          !sourceWorkbenchSource.includes("Dry-run delete") &&
          stylesSource.includes(".formulaTechnicalDetails"),
      },
    {
        label: "frontend-relationship-auto-model-graph",
        ok: existsSync(join(root, "src", "components", "RelationshipAutoModelGraph.tsx")) &&
          existsSync(join(root, "src", "relationshipAutoModelGraphModel.ts")) &&
          sourceWorkbenchRelationshipPanelSource.includes('import { RelationshipAutoModelGraph } from "./RelationshipAutoModelGraph"') &&
          sourceWorkbenchRelationshipPanelSource.includes("<RelationshipAutoModelGraph") &&
          relationshipAutoModelGraphSource.includes("export function RelationshipAutoModelGraph") &&
          relationshipAutoModelGraphSource.includes('from "../relationshipAutoModelGraphModel"') &&
          relationshipAutoModelGraphSource.includes("buildRelationshipAutoModelGraphViewModel") &&
          relationshipAutoModelGraphSource.includes('data-testid="relationship-auto-graph"') &&
          relationshipAutoModelGraphSource.includes('data-testid="relationship-graph-canvas"') &&
          relationshipAutoModelGraphSource.includes('data-testid="relationship-graph-edge"') &&
          relationshipAutoModelGraphSource.includes('data-testid="relationship-graph-best-apply"') &&
          relationshipAutoModelGraphSource.includes('data-testid="relationship-graph-best-preview"') &&
          relationshipAutoModelGraphSource.includes('data-testid="relationship-graph-best-confirm"') &&
          !relationshipAutoModelGraphSource.includes("function recommendationToEdge(") &&
          relationshipAutoModelGraphModelSource.includes("export function buildRelationshipAutoModelGraphViewModel") &&
          relationshipAutoModelGraphModelSource.includes("export function relationshipSaveOptions") &&
          relationshipAutoModelGraphModelSource.includes("export function topRelationshipNodeFields") &&
          relationshipAutoModelGraphModelSource.includes("buildRelationshipSavePayload") &&
          relationshipAutoModelGraphModelSource.includes("relationshipPrimaryMapping") &&
          relationshipAutoModelGraphSource.includes("AI 自动连线") &&
          relationshipAutoModelGraphSource.includes("手动选字段放在高级编辑里") &&
          relationshipAutoModelGraphSource.includes("runBusy(label, () => onRelationshipPreview(options))") &&
          relationshipAutoModelGraphSource.includes("runBusy(label, () => onRelationshipSave({ ...options, confirm }))") &&
          sourceWorkbenchAdvancedPanelsSource.includes('import "./sourceWorkbenchAdvanced.css"') &&
          sourceWorkbenchAdvancedStylesSource.includes(".relationshipAutoGraph {") &&
          sourceWorkbenchAdvancedStylesSource.includes(".fieldSemanticReadiness {") &&
          !globalStylesSource.includes(".relationshipAutoGraph {") &&
          !globalStylesSource.includes(".fieldSemanticReadiness {") &&
          stylesSource.includes(".relationshipAutoGraph") &&
          stylesSource.includes(".relationshipGraphEdgeRow") &&
          stylesSource.includes(".relationshipGraphConnector") &&
          stylesSource.includes("container-name: relationship-model") &&
          stylesSource.includes("@container relationship-model (max-width: 820px)"),
      },
    {
        label: "frontend-source-operations-business-controls",
        ok: sourceWorkbenchOperationsPanelSource.includes("整理左侧入口") &&
          sourceWorkbenchOperationsPanelSource.includes('data-testid="navigation-technical-details"') &&
          sourceWorkbenchOperationsPanelSource.includes("页面显示和顺序") &&
          !sourceWorkbenchOperationsPanelSource.includes("调整顺序和技术目标") &&
          sourceWorkbenchOperationsPanelSource.includes("入口改动预览已生成") &&
          sourceWorkbenchConnectorPanelSource.includes("保存数据连接") &&
          sourceWorkbenchConnectorPanelSource.includes('data-testid="connector-business-lead"') &&
          sourceWorkbenchConnectorPanelSource.includes('data-testid="connector-technical-details"') &&
          sourceWorkbenchConnectorPanelSource.includes("清理导入记录") &&
          sourceWorkbenchConnectorPanelSource.includes("预览清理") &&
          sourceWorkbenchImportPanelSource.includes("Current state is preview") &&
          sourceWorkbenchConnectorControllerSource.includes("WorkbenchOperationReceipt") &&
          sourceWorkbenchImportControllerSource.includes("runImportPreviewAction") &&
          sourceWorkbenchImportControllerSource.includes("runImportCommitAction") &&
          sourceWorkbenchImportControllerSource.includes("runImportPolicyAction") &&
          sourceWorkbenchImportPanelSource.includes('testId="import-operation-receipt"') &&
          sourceWorkbenchImportPanelSource.includes('technicalTestId="import-operation-technical-details"') &&
          sourceWorkbenchImportPanelSource.includes("确认后才写入工作区") &&
          sourceWorkbenchImportPanelSource.includes("当前只做检查，不写入") &&
          sourceWorkbenchImportPanelSource.includes("View import policy and receipt") &&
          sourceWorkbenchConnectorControllerSource.includes("runConnectorSaveAction") &&
          sourceWorkbenchConnectorControllerSource.includes("runConnectorSyncAction") &&
          sourceWorkbenchConnectorControllerSource.includes("runConnectorRemoveAction") &&
          sourceWorkbenchConnectorPanelSource.includes('testId="connector-operation-receipt"') &&
          sourceWorkbenchConnectorPanelSource.includes('technicalTestId="connector-operation-technical-details"') &&
          sourceWorkbenchConnectorPanelSource.includes("同步前先由只读 Adapter 检查来源") &&
          !sourceWorkbenchSource.includes("Dry-run rename") &&
          !sourceWorkbenchSource.includes("Dry-run move") &&
          !sourceWorkbenchSource.includes("Dry-run hide") &&
          !sourceWorkbenchSource.includes("Dry-run show") &&
          !sourceWorkbenchSource.includes("Navigation dry-run ready") &&
          !sourceWorkbenchSource.includes("Current state is dry-run") &&
          stylesSource.includes(".operationReceipt") &&
          stylesSource.includes(".connectorBusinessLead") &&
          stylesSource.includes(".connectorTechnicalDetails") &&
          stylesSource.includes(".navigationTechnicalDetails") &&
          stylesSource.includes(".navigationActionGrid"),
      },
    {
        label: "source-workbench-operations-panel-boundary",
        ok: existsSync(join(root, "src", "components", "SourceWorkbenchOperationsPanel.tsx")) &&
          existsSync(join(root, "src", "components", "SourceWorkbenchDataManagementPanel.tsx")) &&
          sourceWorkbenchAdvancedModulesSource.includes("export const SourceWorkbenchOperationsPanel = lazy") &&
          sourceWorkbenchAdvancedPanelsSource.includes('from "./SourceWorkbenchOperationsPanel"') &&
          sourceWorkbenchSource.includes('from "../sourceWorkbenchDeferredModules"') &&
          sourceWorkbenchDeferredModulesSource.includes("export const SourceWorkbenchDataManagementPanel = lazy") &&
          sourceWorkbenchSource.includes("<SourceWorkbenchOperationsPanel") &&
          sourceWorkbenchSource.includes("<SourceWorkbenchDataManagementPanel") &&
          !sourceWorkbenchSource.includes('data-testid="navigation-module-workbench"') &&
          !sourceWorkbenchSource.includes('data-testid={`source-inspect-${run.table_key}`}') &&
          !sourceWorkbenchSource.includes('data-testid="source-rename-dry-run-button"') &&
          sourceWorkbenchOperationsPanelSource.includes("type SourceWorkbenchOperationsPanelProps") &&
          !sourceWorkbenchOperationsPanelSource.includes("SourceRunSummary") &&
          !sourceWorkbenchOperationsPanelSource.includes("WorkbenchTable") &&
          sourceWorkbenchOperationsPanelSource.includes('data-testid="navigation-module-workbench"') &&
          sourceWorkbenchOperationsPanelSource.includes('data-testid="navigation-rename-dry-run"') &&
          sourceWorkbenchOperationsPanelSource.includes('data-testid="navigation-rename-confirm"') &&
          sourceWorkbenchOperationsPanelSource.includes('data-testid="navigation-move-dry-run"') &&
          sourceWorkbenchOperationsPanelSource.includes('data-testid="navigation-move-confirm"') &&
          sourceWorkbenchOperationsPanelSource.includes('data-testid="navigation-hide-dry-run"') &&
          sourceWorkbenchOperationsPanelSource.includes('data-testid="navigation-hide-confirm"') &&
          sourceWorkbenchOperationsPanelSource.includes('data-testid="navigation-show-dry-run"') &&
          sourceWorkbenchOperationsPanelSource.includes('data-testid="navigation-show-confirm"') &&
          sourceWorkbenchOperationsPanelSource.includes("runNavigationOperation(\"move\", true)") &&
          sourceWorkbenchOperationsPanelSource.includes("runNavigationOperation(\"hide\", true)") &&
          sourceWorkbenchOperationsPanelSource.includes("runNavigationOperation(\"show\", true)") &&
          stylesSource.includes("grid-template-columns: repeat(4, minmax(0, 1fr));") &&
          !sourceWorkbenchOperationsPanelSource.includes('data-testid={`source-inspect-${run.table_key}`}') &&
          !sourceWorkbenchOperationsPanelSource.includes('data-testid="source-delete-dry-run-button"') &&
          sourceWorkbenchDataManagementPanelSource.includes("SourceRunSummary") &&
          sourceWorkbenchDataManagementPanelSource.includes("WorkbenchTable") &&
          sourceWorkbenchDataManagementPanelSource.includes('data-testid="source-data-management-panel"') &&
          sourceWorkbenchDataManagementPanelSource.includes('data-testid={`source-inspect-${source.key}`}') &&
          sourceWorkbenchDataManagementPanelSource.includes('data-testid={`source-select-${source.key}`}') &&
          sourceWorkbenchDataManagementPanelSource.includes('data-testid="source-rename-dry-run-button"') &&
          sourceWorkbenchDataManagementPanelSource.includes('data-testid="source-delete-dry-run-button"') &&
          sourceWorkbenchDataManagementPanelSource.includes('data-testid="source-clear-button"') &&
          sourceWorkbenchDataManagementPanelSource.includes("runClearSandbox") &&
          sourceWorkbenchDataManagementPanelSource.includes("const seen = new Set<string>()") &&
          sourceWorkbenchDataManagementPanelSource.includes("sourceRuns.flatMap") &&
          sourceWorkbenchDataManagementPanelSource.includes("selectManagedSource(event.target.value)") &&
          sourceWorkbenchDataManagementPanelSource.includes("onDeleteSource({ source: selectedManagedSourceKey, confirm: true })") &&
          serverWorkspaceRoutesSource.includes('url.pathname === "/api/sources/delete"') &&
          serverWorkspaceRoutesSource.includes('url.pathname === "/api/sources/rename"') &&
          stylesSource.includes(".sourceLifecyclePanel") &&
          stylesSource.includes(".sourceDangerZone"),
      },
    {
        label: "source-workbench-connector-panel-boundary",
        ok: existsSync(join(root, "src", "components", "SourceWorkbenchConnectorPanel.tsx")) &&
          sourceWorkbenchAdvancedModulesSource.includes("export const SourceWorkbenchConnectorPanel = lazy") &&
          sourceWorkbenchAdvancedModulesSource.includes('import("./components/SourceWorkbenchConnectorPanel")') &&
          sourceWorkbenchSource.includes("<SourceWorkbenchConnectorPanel") &&
          !sourceWorkbenchSource.includes('data-testid="connector-business-lead"') &&
          !sourceWorkbenchSource.includes('data-testid="connector-operation-receipt"') &&
          !sourceWorkbenchSource.includes('data-testid={`import-job-dry-remove-${job.job_key}`}') &&
          sourceWorkbenchConnectorPanelSource.includes("type SourceWorkbenchConnectorPanelProps") &&
          sourceWorkbenchConnectorPanelSource.includes("DataConnectorConfig") &&
          sourceWorkbenchConnectorPanelSource.includes("ImportJob") &&
          sourceWorkbenchConnectorPanelSource.includes("ReturnType<typeof useSourceWorkbenchConnectorController>") &&
          sourceWorkbenchConnectorControllerSource.includes("async function runConnectorSaveAction(confirm: boolean)") &&
          sourceWorkbenchConnectorControllerSource.includes("async function runConnectorSyncAction(connector: DataConnectorConfig, confirm: boolean)") &&
          sourceWorkbenchConnectorControllerSource.includes("async function runConnectorRemoveAction(connector: DataConnectorConfig)") &&
          sourceWorkbenchConnectorPanelSource.includes('data-testid="connector-save-dry-run-button"') &&
          sourceWorkbenchConnectorPanelSource.includes('data-testid={`connector-sync-dry-${connector.connectorKey}`}') &&
          sourceWorkbenchConnectorPanelSource.includes('data-testid={`connector-remove-${connector.connectorKey}`}') &&
          sourceWorkbenchConnectorPanelSource.includes('data-testid={`import-job-dry-remove-${job.job_key}`}') &&
          sourceWorkbenchConnectorPanelSource.includes("onRemoveImportJob({ jobKey: job.job_key, confirm: false })") &&
          sourceWorkbenchConnectorPanelSource.includes("This manages import receipts and records, not source business files"),
      },
    {
        label: "source-workbench-field-metric-panel-boundary",
        ok: existsSync(join(root, "src", "components", "SourceWorkbenchFieldMetricPanel.tsx")) &&
          existsSync(join(root, "src", "components", "SourceWorkbenchFieldSemanticPanel.tsx")) &&
          existsSync(join(root, "src", "components", "SourceWorkbenchMetricDefinitionPanel.tsx")) &&
          existsSync(join(root, "src", "sourceWorkbenchFieldMetricTypes.ts")) &&
          sourceWorkbenchAdvancedModulesSource.includes("export const SourceWorkbenchFieldMetricPanel = lazy") &&
          sourceWorkbenchAdvancedPanelsSource.includes('from "./SourceWorkbenchFieldMetricPanel"') &&
          sourceWorkbenchSource.includes("<SourceWorkbenchFieldMetricPanel") &&
          !sourceWorkbenchSource.includes('data-testid="field-semantic-readiness"') &&
          !sourceWorkbenchSource.includes('data-testid="infer-metrics-dry-run-button"') &&
          sourceWorkbenchFieldMetricPanelSource.includes("type SourceWorkbenchFieldMetricPanelProps") &&
          sourceWorkbenchFieldMetricPanelSource.includes('import { SourceWorkbenchFieldSemanticPanel } from "./SourceWorkbenchFieldSemanticPanel"') &&
          sourceWorkbenchFieldMetricPanelSource.includes('import { SourceWorkbenchMetricDefinitionPanel } from "./SourceWorkbenchMetricDefinitionPanel"') &&
          sourceWorkbenchFieldMetricPanelSource.includes("<SourceWorkbenchFieldSemanticPanel") &&
          sourceWorkbenchFieldMetricPanelSource.includes("<SourceWorkbenchMetricDefinitionPanel") &&
          !sourceWorkbenchFieldMetricPanelSource.includes('data-testid="field-semantic-readiness"') &&
          !sourceWorkbenchFieldMetricPanelSource.includes('data-testid="infer-metrics-dry-run-button"') &&
          sourceWorkbenchFieldMetricTypesSource.includes("export type FieldSemanticReadiness") &&
          sourceWorkbenchFieldMetricTypesSource.includes("export type MetricMutationOptions") &&
          sourceWorkbenchFieldMetricTypesSource.includes("export type QueryMetricOptions") &&
          sourceWorkbenchFieldMetricPanelSource.includes("fieldDraft: (field: FieldConfig)") &&
          sourceWorkbenchFieldMetricPanelSource.includes("metricDraft: (confirm?: boolean) => MetricMutationOptions") &&
          sourceWorkbenchFieldSemanticPanelSource.includes('data-testid="infer-semantics-dry-run-button"') &&
          sourceWorkbenchMetricDefinitionPanelSource.includes('data-testid="infer-metrics-dry-run-button"') &&
          sourceWorkbenchMetricDefinitionPanelSource.includes('data-testid="add-metric-confirm-button"') &&
          sourceWorkbenchMetricDefinitionPanelSource.includes('data-testid="semantic-metric-result"'),
      },
    {
        label: "source-workbench-query-formula-panel-boundary",
        ok: existsSync(join(root, "src", "components", "SourceWorkbenchQueryFormulaPanel.tsx")) &&
          sourceWorkbenchAdvancedModulesSource.includes("export const SourceWorkbenchQueryFormulaPanel = lazy") &&
          sourceWorkbenchAdvancedPanelsSource.includes('from "./SourceWorkbenchQueryFormulaPanel"') &&
          sourceWorkbenchSource.includes("<SourceWorkbenchQueryFormulaPanel") &&
          !sourceWorkbenchSource.includes('data-testid="query-run-button"') &&
          !sourceWorkbenchSource.includes('data-testid="formula-preview-button"') &&
          !sourceWorkbenchSource.includes("function formulaOptions(") &&
          !sourceWorkbenchSource.includes("function formulaAssetKey(") &&
          sourceWorkbenchQueryFormulaPanelSource.includes("type SourceWorkbenchQueryFormulaPanelProps") &&
          sourceWorkbenchQueryFormulaPanelSource.includes("type QueryOptions") &&
          sourceWorkbenchQueryFormulaPanelSource.includes("type FormulaSaveOptions") &&
          sourceWorkbenchQueryFormulaPanelSource.includes("function formulaOptions(") &&
          sourceWorkbenchQueryFormulaPanelSource.includes("function formulaAssetKey(") &&
          sourceWorkbenchQueryFormulaPanelSource.includes('data-testid="query-run-button"') &&
          sourceWorkbenchQueryFormulaPanelSource.includes('data-testid="source-query-runtime-technical"') &&
          sourceWorkbenchQueryFormulaPanelSource.includes('data-testid="formula-save-confirm-button"') &&
          sourceWorkbenchQueryFormulaPanelSource.includes('data-testid="formula-asset-list"'),
      },
    {
        label: "source-workbench-relationship-panel-boundary",
        ok: existsSync(join(root, "src", "components", "SourceWorkbenchRelationshipPanel.tsx")) &&
          sourceWorkbenchAdvancedModulesSource.includes("export const SourceWorkbenchRelationshipPanel = lazy") &&
          sourceWorkbenchAdvancedPanelsSource.includes('from "./SourceWorkbenchRelationshipPanel"') &&
          sourceWorkbenchSource.includes("<SourceWorkbenchRelationshipPanel") &&
          !sourceWorkbenchSource.includes('data-testid="relationship-preview-button"') &&
          !sourceWorkbenchSource.includes('data-testid="relationship-impact-panel"') &&
          !sourceWorkbenchSource.includes("function applyRelationshipRecommendation(") &&
          !sourceWorkbenchSource.includes("relationshipDecisionState") &&
          sourceWorkbenchRelationshipPanelSource.includes("type SourceWorkbenchRelationshipPanelProps") &&
          sourceWorkbenchRelationshipPanelSource.includes('from "../dashboardCanvasContracts"') &&
          sourceWorkbenchRelationshipPanelSource.includes("relationshipForm: RelationshipSaveOptions") &&
          sourceWorkbenchRelationshipPanelSource.includes("setRelationshipForm: Dispatch<SetStateAction<RelationshipSaveOptions>>") &&
          sourceWorkbenchRelationshipPanelSource.includes("matchingRelationshipRecommendation") &&
          sourceWorkbenchRelationshipPanelSource.includes("relationshipAlreadySaved") &&
          sourceWorkbenchRelationshipPanelSource.includes("function applyRelationshipRecommendation(") &&
          sourceWorkbenchRelationshipPanelSource.includes('data-testid="relationship-preview-button"') &&
          sourceWorkbenchRelationshipPanelSource.includes('data-testid="relationship-confirm-button"') &&
          sourceWorkbenchRelationshipPanelSource.includes('data-testid="relationship-impact-panel"') &&
          sourceWorkbenchRelationshipPanelSource.includes("已保存关系"),
      },
    {
        label: "frontend-b-widget-drilldown-workflow",
        ok: bWidgetKitSource.includes("runTableQuery") &&
          bWidgetKitSource.includes("saveView") &&
          bWidgetKitSource.includes("<BiDashboardDrilldownSheet") &&
          !bWidgetKitSource.includes("data-testid=\"b-drilldown-sheet\"") &&
          bDashboardDrilldownSheetSource.includes("export type DrilldownOperationReceipt") &&
          bDashboardDrilldownSheetSource.includes("data-testid=\"b-drilldown-sheet\"") &&
          bDashboardDrilldownSheetSource.includes("data-testid=\"b-drilldown-save-dry-run\"") &&
          bDashboardDrilldownSheetSource.includes("data-testid=\"b-drilldown-save-confirm\"") &&
          bDashboardDrilldownSheetSource.includes('data-testid="b-drilldown-operation-receipt"') &&
          bDashboardDrilldownSheetSource.includes('data-testid="b-drilldown-technical-details"') &&
          bDashboardDrilldownSheetSource.includes("可在视图页继续分析") &&
          bDashboardDrilldownSheetSource.includes("确认前不会创建视图") &&
          bDashboardDrilldownSheetSource.includes("View drilldown scope") &&
          stylesSource.includes(".bDrilldownReceipt") &&
          bDashboardWidgetCardSource.includes("onPointClick") &&
          bWidgetKitSource.includes("pointFilter"),
      },
    {
        label: "frontend-dashboard-widget-copy-remove-confirm-path",
        ok: dashboardWidgetLifecyclePanelSource.includes("data-testid=\"widget-lifecycle-actions\"") &&
          dashboardWidgetLifecyclePanelSource.includes("data-testid=\"widget-copy-preview-button\"") &&
          dashboardWidgetLifecyclePanelSource.includes("data-testid=\"widget-copy-confirm-button\"") &&
          dashboardWidgetLifecyclePanelSource.includes("data-testid=\"widget-remove-preview-button\"") &&
          dashboardWidgetLifecyclePanelSource.includes("data-testid=\"widget-remove-confirm-button\"") &&
          dashboardWidgetLifecyclePanelSource.includes("复制或删除组件") &&
          dashboardWidgetManagePanelSource.includes("data-testid={`widget-copy-preview-${widget.widget_key}`}") &&
          dashboardWidgetManagePanelSource.includes("data-testid={`widget-remove-preview-${widget.widget_key}`}") &&
          dashboardWidgetLifecyclePanelSource.includes("confirm: false") &&
          dashboardWidgetLifecyclePanelSource.includes("confirm: true") &&
          !dashboardCanvasSource.includes("预演复制") &&
          !dashboardCanvasSource.includes("预演删除") &&
          dashboardWidgetManagePanelSource.includes("预览复制") &&
          dashboardWidgetManagePanelSource.includes("预览删除") &&
          serverDashboardRoutesSource.includes("op === \"copy\"") &&
          serverDashboardRoutesSource.includes("[\"copy-widget\", \"--widget\"") &&
          serverDashboardRoutesSource.includes("op === \"remove\"") &&
          serverDashboardRoutesSource.includes("[\"remove-widget\", \"--widget\""),
      },
    {
        label: "frontend-dashboard-widget-editor-business-controls",
        ok: dashboardWidgetEditorPanelSource.includes("调整组件呈现") &&
          dashboardWidgetBasicFormSource.includes("呈现方式") &&
          dashboardWidgetBasicFormSource.includes("数据范围") &&
          dashboardWidgetBasicFormSource.includes("分组字段") &&
          dashboardWidgetBasicFormSource.includes("计算字段") &&
          dashboardWidgetBasicFormSource.includes("计算方式") &&
          dashboardWidgetBasicFormSource.includes("显示数量") &&
          dashboardWidgetStylePanelSource.includes("外观和点击行为") &&
          dashboardWidgetLocalFilterPanelSource.includes("限定这个组件的数据") &&
          dashboardWidgetEditorPanelSource.includes("预览改动") &&
          dashboardWidgetEditorPanelSource.includes("应用改动") &&
          !dashboardCanvasSource.includes("组件配置") &&
          !dashboardCanvasSource.includes("预检配置") &&
          !dashboardCanvasSource.includes("Style and interaction") &&
          stylesSource.includes(".widgetLifecycleActions summary"),
      },
    {
        label: "dashboard-canvas-widget-model-boundary",
        ok: existsSync(join(root, "src", "dashboardCanvasWidgetModel.ts")) &&
          dashboardCanvasActionsSource.includes('from "./dashboardCanvasWidgetModel"') &&
          dashboardCanvasStateSource.includes('from "./dashboardCanvasWidgetModel"') &&
          dashboardCanvasStateSource.includes("useState<WidgetDraft>(() => defaultWidgetDraft())") &&
          dashboardCanvasStateSource.includes("setWidgetDraft(widgetDraftFromWidget(widget))") &&
          dashboardCanvasActionsSource.includes("buildDashboardModulePayload({") &&
          dashboardCanvasActionsSource.includes("buildWidgetSettingsPayload({") &&
          !dashboardCanvasSource.includes('from "../dashboardCanvasWidgetModel"') &&
          !dashboardCanvasSource.includes("buildDashboardModulePayload({") &&
          !dashboardCanvasSource.includes("buildWidgetSettingsPayload({") &&
          !dashboardCanvasSource.includes("useState<WidgetDraft>(() => defaultWidgetDraft())") &&
          !dashboardCanvasSource.includes("setWidgetDraft(widgetDraftFromWidget(widget))") &&
          !dashboardCanvasSource.includes("type WidgetDraft = {") &&
          !dashboardCanvasSource.includes("type WidgetToggleKey =") &&
          !dashboardCanvasSource.includes("const parsedTopN =") &&
          !dashboardCanvasSource.includes("const parsedDecimalPlaces =") &&
          !dashboardCanvasSource.includes("const parsedTableColumnLimit =") &&
          !dashboardCanvasSource.includes("const fallbackWidth = widget.widget_type") &&
          !dashboardCanvasSource.includes("subtitle: typeof config.subtitle") &&
          dashboardCanvasWidgetModelSource.includes("export type DashboardCanvasWidthMode") &&
          dashboardCanvasWidgetModelSource.includes("export type WidgetDraft") &&
          dashboardCanvasWidgetModelSource.includes("export type WidgetToggleKey") &&
          dashboardCanvasWidgetModelSource.includes("export function defaultWidgetDraft(") &&
          dashboardCanvasWidgetModelSource.includes("export function widgetDraftFromWidget(") &&
          dashboardCanvasWidgetModelSource.includes("export function widgetDraftNumbers(") &&
          dashboardCanvasWidgetModelSource.includes("export function buildWidgetSettingsPayload(") &&
          dashboardCanvasWidgetModelSource.includes("export function moduleLayoutForWidget(") &&
          dashboardCanvasWidgetModelSource.includes("export function buildDashboardModulePayload(") &&
          dashboardCanvasSourceSwitchModelSource.includes("moduleLayoutForWidget(widget, index)") &&
          dashboardCanvasWidgetModelSource.includes("topN: boundedInteger(widgetDraft.topN, 12, 1, 500)") &&
          dashboardCanvasWidgetModelSource.includes("decimalPlaces: boundedInteger(widgetDraft.decimalPlaces, 0, 0, 4)") &&
          dashboardCanvasWidgetModelSource.includes("tableColumnLimit: boundedInteger(widgetDraft.tableColumnLimit, 6, 2, 24)"),
      },
    {
        label: "dashboard-canvas-editor-options-boundary",
        ok: existsSync(join(root, "src", "dashboardCanvasEditorOptions.ts")) &&
          dashboardAdvancedWidgetWorkbenchSource.includes('from "../dashboardCanvasEditorOptions"') &&
          dashboardAdvancedWidgetWorkbenchSource.includes("buildWidgetToggleOptions(widgetDraft)") &&
          dashboardWidgetBasicFormSource.includes("widgetTypes.map") &&
          dashboardWidgetBasicFormSource.includes("valueFormats.map") &&
          dashboardWidgetStylePanelSource.includes("colorPalettes.map") &&
          dashboardWidgetStylePanelSource.includes("rankingModes.map") &&
          dashboardWidgetStylePanelSource.includes("slicerDisplays.map") &&
          dashboardOverviewStripSource.includes("dashboardAcceptanceItems.map") &&
          !dashboardCanvasSource.includes('const widgetTypes = ["metric"') &&
          !dashboardCanvasSource.includes('const valueFormats = ["auto"') &&
          !dashboardCanvasSource.includes('const colorPalettes = ["default"') &&
          !dashboardCanvasSource.includes('from "../dashboardCanvasEditorOptions"') &&
          !dashboardCanvasSource.includes("buildWidgetToggleOptions(widgetDraft)") &&
          !dashboardCanvasSource.includes("dashboardAcceptanceItems.map") &&
          !dashboardCanvasSource.includes('const dashboardAcceptanceItems = [') &&
          !dashboardCanvasSource.includes('const widgetToggleOptions: Array<') &&
          !dashboardCanvasSource.includes('key: "showLegend", label: biText("图例"') &&
          dashboardCanvasEditorOptionsSource.includes('export const widgetTypes = ["metric", "bar", "line", "pie", "table", "text", "slicer"]') &&
          dashboardCanvasEditorOptionsSource.includes('export const valueFormats = ["auto", "plain", "compact", "currency", "percent"]') &&
          dashboardCanvasEditorOptionsSource.includes('export const colorPalettes = ["default", "fresh", "warm", "contrast", "mono"]') &&
          dashboardCanvasEditorOptionsSource.includes("export const dashboardAcceptanceItems") &&
          dashboardCanvasEditorOptionsSource.includes("export type WidgetToggleOption") &&
          dashboardCanvasEditorOptionsSource.includes("export function buildWidgetToggleOptions(") &&
          dashboardCanvasEditorOptionsSource.includes('key: "showLegend"') &&
          dashboardCanvasEditorOptionsSource.includes("多选切片") &&
          dashboardCanvasEditorOptionsSource.includes('key: "copy-delete"'),
      },
    {
        label: "dashboard-canvas-summary-model-boundary",
        ok: existsSync(join(root, "src", "dashboardCanvasSummaryModel.ts")) &&
          dashboardCanvasViewModelSource.includes('from "./dashboardCanvasSummaryModel"') &&
          dashboardCanvasViewModelSource.includes("buildDashboardSummaryModel({") &&
          dashboardCanvasSource.includes("dashboardSummary={dashboardSummary}") &&
          !dashboardCanvasSource.includes('from "../dashboardCanvasSummaryModel"') &&
          !dashboardCanvasSource.includes("buildDashboardSummaryModel({") &&
          dashboardOverviewStripSource.includes("dashboardSummary.topRow") &&
          dashboardOverviewStripSource.includes("dashboardSummary.currentScopeDetail") &&
          dashboardOverviewStripSource.includes("dashboardSummary.evidenceCoverageDetail") &&
          dashboardOverviewStripSource.includes("dashboardSummary.totalDetail") &&
          !dashboardCanvasSource.includes("const queryRows = Array.isArray(query.rows)") &&
          !dashboardCanvasSource.includes("const rankedRows = queryRows") &&
          !dashboardCanvasSource.includes("const totalValue = rankedRows.reduce") &&
          dashboardCanvasSummaryModelSource.includes("export type DashboardSummaryRow") &&
          dashboardCanvasSummaryModelSource.includes("export type DashboardSummaryModel") &&
          dashboardCanvasSummaryModelSource.includes("export function buildDashboardSummaryModel(") &&
          dashboardCanvasSummaryModelSource.includes("const rankedRows = queryRows") &&
          dashboardCanvasSummaryModelSource.includes(".map((row)") &&
          dashboardCanvasSummaryModelSource.includes("recommended group") &&
          dashboardCanvasSummaryModelSource.includes("evidenceCoverageDetail"),
      },
    {
        label: "dashboard-canvas-view-model-boundary",
        ok: existsSync(join(root, "src", "dashboardCanvasViewModel.ts")) &&
          dashboardCanvasSource.includes('from "../dashboardCanvasViewModel"') &&
          dashboardCanvasSource.includes("buildDashboardCanvasViewModel({") &&
          dashboardCanvasSource.includes("dashboardEvidenceFocus") &&
          dashboardCanvasSource.includes("onOpenEvidence(dashboardEvidenceFocus)") &&
          !dashboardCanvasSource.includes("const sourceIntelligenceRuns =") &&
          !dashboardCanvasSource.includes("const latestRun = sourceIntelligenceRuns[0]") &&
          !dashboardCanvasSource.includes("const dashboardReadiness = buildDashboardReadinessModel") &&
          !dashboardCanvasSource.includes("const sourceSwitchView = buildDashboardSourceSwitchViewModel") &&
          !dashboardCanvasSource.includes("const { plannedWidgets, moduleSaveResult") &&
          dashboardCanvasViewModelSource.includes("export function buildDashboardCanvasViewModel(") &&
          dashboardCanvasViewModelSource.includes("type DashboardCanvasViewModelOptions") &&
          dashboardCanvasViewModelSource.includes("const sourceIntelligenceRuns = Array.isArray(workbench.sourceIntelligenceRuns)") &&
          dashboardCanvasViewModelSource.includes("const latestRun = latestUsableSourceIntelligenceRun(sourceIntelligenceRuns)") &&
          dashboardCanvasViewModelSource.includes("const dashboardSummary = buildDashboardSummaryModel({") &&
          dashboardCanvasViewModelSource.includes("const widgetPlanSummary = summarizeDashboardWidgetPlan(widgetPlan)") &&
          dashboardCanvasViewModelSource.includes("const sourceSwitchAnalysis = analyzeDashboardSourceSwitch({") &&
          dashboardCanvasViewModelSource.includes("const sourceSwitchView = buildDashboardSourceSwitchViewModel(sourceSwitchAnalysis)") &&
          dashboardCanvasViewModelSource.includes("const nextWidgetFilters = buildNextWidgetFilters({") &&
          dashboardCanvasViewModelSource.includes("const dashboardReadiness = buildDashboardReadinessModel({") &&
          dashboardCanvasViewModelSource.includes("const dashboardEvidenceFocus = buildDashboardEvidenceFocus({"),
      },
    {
        label: "dashboard-canvas-contracts-boundary",
        ok: existsSync(join(root, "src", "dashboardCanvasContracts.ts")) &&
          dashboardCanvasContractsSource.includes("export type DashboardWidgetFilterInput") &&
          dashboardCanvasContractsSource.includes("export type DashboardOperationOptions") &&
          dashboardCanvasContractsSource.includes("export type DashboardFilterOperationOptions") &&
          dashboardCanvasContractsSource.includes("export type DashboardModuleSaveOptions") &&
          dashboardCanvasContractsSource.includes("export type BusinessDashboardOptions") &&
          dashboardCanvasContractsSource.includes("export type RelationshipSaveOptions") &&
          dashboardCanvasContractsSource.includes("export type DashboardWidgetOperationOptions") &&
          dashboardCanvasContractsSource.includes('op: "recommend" | "addRecommended" | "add" | "addRelationship" | "set" | "copy" | "remove"') &&
          dashboardCanvasContractsSource.includes("filters?: DashboardWidgetFilterInput[]") &&
          dashboardCanvasSource.includes('from "../dashboardCanvasContracts"') &&
          dashboardCanvasActionsSource.includes('from "./dashboardCanvasContracts"') &&
          dashboardAdvancedWidgetWorkbenchSource.includes('from "../dashboardCanvasContracts"') &&
          dashboardWidgetEditorPanelSource.includes('from "../dashboardCanvasContracts"') &&
          dashboardWidgetLocalFilterPanelSource.includes('from "../dashboardCanvasContracts"') &&
          dashboardWidgetLifecyclePanelSource.includes('from "../dashboardCanvasContracts"') &&
          dashboardPageAdminPanelSource.includes('from "../dashboardCanvasContracts"') &&
          !dashboardBusinessTaskStripSource.includes('from "../dashboardCanvasContracts"') &&
          dashboardBusinessTemplatePanelSource.includes('from "../dashboardCanvasContracts"') &&
          dashboardFilterWorkbenchSource.includes('from "../dashboardCanvasContracts"') &&
          !homeOverviewSource.includes('from "../dashboardCanvasContracts"') &&
          !sourceWorkbenchSource.includes('from "../dashboardCanvasContracts"') &&
          !sourceWorkbenchSource.includes('from "./dashboardCanvasContracts"') &&
          sourceWorkbenchContractsSource.includes('from "./dashboardCanvasContracts"') &&
          sourceWorkbenchRelationshipPanelSource.includes('from "../dashboardCanvasContracts"') &&
          !dashboardCanvasSource.includes("op: \"recommend\" | \"addRecommended\" | \"add\" | \"addRelationship\" | \"set\" | \"copy\" | \"remove\"") &&
          !dashboardCanvasActionsSource.includes("type DashboardWidgetOperationOptions =") &&
          !dashboardCanvasActionsSource.includes("type DashboardOperationOptions =") &&
          !dashboardCanvasActionsSource.includes("type BusinessDashboardOptions =") &&
          !dashboardAdvancedWidgetWorkbenchSource.includes("type WidgetOperationOptions =") &&
          !dashboardAdvancedWidgetWorkbenchSource.includes("type BusinessDashboardOptions =") &&
          !dashboardWidgetEditorPanelSource.includes("type WidgetOperationOptions =") &&
          !dashboardWidgetLocalFilterPanelSource.includes("type WidgetFilterOperation =") &&
          !dashboardWidgetLifecyclePanelSource.includes("type WidgetLifecycleOperation") &&
          !dashboardPageAdminPanelSource.includes("type DashboardOperationOptions =") &&
          !dashboardBusinessTaskStripSource.includes("type BusinessDashboardOptions =") &&
          !dashboardBusinessTemplatePanelSource.includes("type BusinessDashboardOptions =") &&
          !dashboardFilterWorkbenchSource.includes("type DashboardFilterOperation =") &&
          !homeOverviewSource.includes('onBusinessDashboardOperation: (options: { op: "draft" | "create" | "overwrite"') &&
          !sourceWorkbenchSource.includes("type RelationshipOptions =") &&
          !sourceWorkbenchSource.includes('onBusinessDashboardOperation: (options: { op: "draft" | "create" | "overwrite"') &&
          !sourceWorkbenchRelationshipPanelSource.includes("type RelationshipOptions ="),
      },
    {
        label: "frontend-dashboard-evidence-click-path",
        ok: bDashboardWidgetCardSource.includes("data-testid={`b-widget-evidence-${widget.id}`}") &&
          bDashboardWidgetCardSource.includes("Review evidence") &&
          bWidgetKitSource.includes("openWidgetEvidence") &&
          hasCssRule(stylesSource, ".bWidgetMeta button", "display: inline-flex;") &&
          stylesSource.includes("min-height: 32px;") &&
          dashboardCanvasSource.includes("onOpenEvidence={onOpenEvidence}") &&
          appSource.includes("const [evidenceFocus, setEvidenceFocus]") &&
          (appSource.includes("setSection(\"evidence\")") || appSource.includes("openSection(\"evidence\")") || appSource.includes('section: "evidence"')) &&
          evidenceViewSource.includes("data-testid=\"evidence-focus-card\"") &&
          evidenceViewSource.includes("data-testid=\"evidence-source-intelligence-summary\"") &&
          evidenceViewSource.includes('data-testid="evidence-technical-ref-details"') &&
          evidenceViewSource.includes('data-testid="evidence-receipt-technical-details"') &&
          evidenceViewSource.includes('data-testid="evidence-focus-technical-detail"') &&
          evidenceViewSource.includes("查看技术引用名") &&
          evidenceViewSource.includes("View technical reference names") &&
          evidenceViewSource.includes("查看原始本体合同") &&
          evidenceViewModelSource.includes("source-intelligence:"),
      }
  );
}
