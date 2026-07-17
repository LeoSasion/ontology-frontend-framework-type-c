import { appendAppArchitectureContractExtendedChecks } from "./appArchitectureContractsExtended.mjs";

export function appendAppArchitectureContractChecks(context) {
  const {
    checks,
    actionRecoveryModelSource,
    agentEvidenceStylesSource,
    agentPanelModelSource,
    agentPanelSource,
    apiAgentSource,
    apiClientSource,
    apiDashboardSource,
    apiModelSource,
    apiRelationshipSource,
    apiSettingsSource,
    apiSource,
    apiSourceApiSource,
    apiViewsSource,
    apiWorkspaceSource,
    appAgentActionsSource,
    appDashboardActionsSource,
    appDataActionsSource,
    appLazyModulesSource,
    appRefreshModelSource,
    appSectionsSource,
    appSettingsActionsSource,
    appSource: appEntrySource,
    appMainViewSource,
    appWorkspaceActionsSource,
    appWorkspaceModelSource,
    biCliCapabilitiesSource,
    biCliDashboardCommandsSource,
    biCliIoServicesSource,
    biCliMiscCommandsSource,
    biCliParserSource,
    biCliQueryViewCommandsSource,
    biCliRelationshipFormulaCommandsSource,
    biCliSchemaSource,
    biCliSemanticMetricCommandsSource,
    biCliSource,
    biCliSourceCommandsSource,
    biCliSystemCommandsSource,
    biCliWidgetCommandsSource,
    byLabel,
    dashboardBusinessTaskStripSource,
    dashboardCanvasSource,
    defaultThemeDataSource,
    developmentRoadmapDocSource,
    devScriptSource,
    docsReadmeSource,
    emptyWorkspaceDataSource,
    evidenceViewSource,
    existsSync,
    globalStylesSource,
    hasCssRule,
    homeOverviewSource,
    implementationStatusSource,
    join,
    metricRepairModelSource,
    metricSemanticRepairActionsSource,
    packageJson,
    prdDocSource,
    productAcceptanceMatrixDocSource,
    productActivationModelSource,
    productActivationPanelSource,
    productIntelligenceModelSource,
    productUxStandardDocSource,
    retiredSeedEnvName,
    root,
    safeValueSource,
    serverAgentRoutesSource,
    serverCliArgBuildersSource,
    serverDashboardRoutesSource,
    serverIndexSource,
    serverModelRoutesSource,
    serverQueryRoutesSource,
    serverRuntimeSource,
    serverSettingsRoutesSource,
    serverSourceRoutesSource,
    serverStaticSource,
    serverWorkspaceRoutesSource,
    settingsPanelSource,
    sidebarSource,
    sourceWorkbenchModelSource,
    sourceWorkbenchSource,
    stylesSource,
    themeSource,
    topBarSource,
    typesAgentSource,
    typesDashboardSource,
    typesDomainSource,
    typesQuerySource,
    typesSource,
    typesSourceContractsSource,
    typesSourceIntelligenceSource,
    typesWorkspaceSource,
    useQualityDoctorSource,
    verifyBiCliAgentContractSource,
    verifySource,
    verifyUiRealImportSource,
    viewWorkspaceSource,
    workspaceFlowModelSource,
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
        label: "workspace-create-atomically-activates-created-workspace",
        ok: byLabel["cli-workspace-create-confirm"].parsed?.created?.id === "verify_workspace" &&
          byLabel["cli-workspace-create-confirm"].parsed?.created?.isActive === true &&
          byLabel["cli-status-after-workspace-create"].parsed?.workspace?.id === "verify_workspace",
      },
    {
        label: "app-workspace-model-boundary",
        ok: existsSync(join(root, "src", "appWorkspaceModel.ts")) &&
          appSource.includes('from "./appWorkspaceModel"') &&
          appWorkspaceModelSource.includes("export function preferredLandingSection(") &&
          appWorkspaceModelSource.includes("export function normalizeStatus(") &&
          appWorkspaceModelSource.includes("export function normalizeQuery(") &&
          appWorkspaceModelSource.includes("export function normalizeWorkbench(") &&
          appWorkspaceModelSource.includes("export function normalizeDashboards(") &&
          appWorkspaceModelSource.includes("export function actionErrorResult(") &&
          appWorkspaceModelSource.includes("buildActionRecovery(action, error)") &&
          actionRecoveryModelSource.includes("no-sample-fallback-for-core-action") &&
          appWorkspaceModelSource.includes('from "./emptyWorkspaceData"') &&
          appWorkspaceModelSource.includes("emptyWorkbenchPayload.formulaDsl") &&
          appWorkspaceModelSource.includes('if (resolvedPendingDraftCount > 0) return "agent"') &&
          appWorkspaceModelSource.includes('return "home"') &&
          appWorkspaceModelSource.includes("void status") &&
          appWorkspaceModelSource.includes("void workbench") &&
          appWorkspaceModelSource.includes("void dashboards") &&
          !appWorkspaceModelSource.includes('return "dashboards"') &&
          !appWorkspaceModelSource.includes('return "sources"') &&
          !appSource.includes("function normalizeStatus(") &&
          !appSource.includes("function normalizeQuery(") &&
          !appSource.includes("function normalizeWorkbench(") &&
          !appSource.includes("function normalizeDashboards(") &&
          !appSource.includes("function actionErrorResult(") &&
          !appSource.includes("const connectingStatus: WorkspaceStatus"),
      },
    {
        label: "empty-workspace-data-boundary",
        ok: existsSync(join(root, "src", "emptyWorkspaceData.ts")) &&
          emptyWorkspaceDataSource.includes("export const emptyWorkspaceStatus") &&
          emptyWorkspaceDataSource.includes("export const emptyImportPreview") &&
          emptyWorkspaceDataSource.includes("export const emptyQueryResult") &&
          emptyWorkspaceDataSource.includes("export const emptyTableQuery") &&
          emptyWorkspaceDataSource.includes("export const emptyWorkbenchPayload") &&
          emptyWorkspaceDataSource.includes("export const emptyDashboardPayload") &&
          emptyWorkspaceDataSource.includes("export const emptyAgentResult") &&
          emptyWorkspaceDataSource.includes("export const emptyActionDrafts") &&
          emptyWorkspaceDataSource.includes('tables: 0') &&
          emptyWorkspaceDataSource.includes('dashboards: 0') &&
          appSource.includes('from "./emptyWorkspaceData"') &&
          apiAgentSource.includes('emptyActionDrafts') &&
          apiWorkspaceSource.includes('emptyWorkspaceStatus') &&
          apiWorkspaceSource.includes('emptyWorkbenchPayload') &&
          apiWorkspaceSource.includes('emptyDashboardPayload') &&
          apiSourceApiSource.includes('emptyImportPreview') &&
          apiModelSource.includes('emptyFormulaPreview') &&
          apiRelationshipSource.includes('emptyRelationshipPreview') &&
          !appWorkspaceModelSource.includes('from "./sampleData"') &&
          !apiWorkspaceSource.includes('from "./sampleData"') &&
          !apiAgentSource.includes('sampleActionDrafts'),
      },
    {
        label: "types-workspace-contract-boundary",
        ok: existsSync(join(root, "src", "typesWorkspace.ts")) &&
          typesSource.includes('from "./typesWorkspace"') &&
          typesSource.includes("export type { QueryRuntimeStatus, SelectionConfidence, SourceRunSummary, WorkspaceRecord, WorkspaceStatus }") &&
          typesWorkspaceSource.includes("export interface WorkspaceStatus") &&
          typesWorkspaceSource.includes("export interface WorkspaceRecord") &&
          typesWorkspaceSource.includes("export interface QueryRuntimeStatus") &&
          typesWorkspaceSource.includes("export interface SourceRunSummary") &&
          typesWorkspaceSource.includes('export type SelectionConfidence = "explicit"') &&
          !typesSource.includes("export interface WorkspaceStatus") &&
          !typesSource.includes("export interface WorkspaceRecord") &&
          !typesSource.includes("export interface QueryRuntimeStatus") &&
          !typesSource.includes("export interface SourceRunSummary"),
      },
    {
        label: "types-dashboard-contract-boundary",
        ok: existsSync(join(root, "src", "typesDashboard.ts")) &&
          typesSource.includes('from "./typesDashboard"') &&
          typesSource.includes("export type { DashboardFilterPayload, DashboardFilterRule, DashboardPage, DashboardPayload, DashboardWidget, NavigationModule }") &&
          typesDashboardSource.includes("export interface DashboardWidget") &&
          typesDashboardSource.includes("export interface DashboardFilterRule") &&
          typesDashboardSource.includes("export interface DashboardPage") &&
          typesDashboardSource.includes("export interface DashboardPayload") &&
          typesDashboardSource.includes("export interface NavigationModule") &&
          typesDashboardSource.includes("export interface DashboardFilterPayload") &&
          !typesSource.includes("export interface DashboardWidget") &&
          !typesSource.includes("export interface DashboardFilterRule") &&
          !typesSource.includes("export interface DashboardPage") &&
          !typesSource.includes("export interface DashboardPayload") &&
          !typesSource.includes("export interface NavigationModule") &&
          !typesSource.includes("export interface DashboardFilterPayload"),
      },
    {
        label: "types-source-contract-boundary",
        ok: existsSync(join(root, "src", "typesSource.ts")) &&
          existsSync(join(root, "src", "typesSourceIntelligence.ts")) &&
          typesSource.includes('from "./typesSource"') &&
          typesSource.includes("SourceIntelligenceDashboardCandidate") &&
          typesSource.includes("WorkbenchPayload") &&
          typesSourceContractsSource.includes("export interface SourceFieldProfile") &&
          typesSourceContractsSource.includes("export interface ImportPreview") &&
          typesSourceContractsSource.includes('from "./typesDomain"') &&
          typesSourceContractsSource.includes("export interface WorkbenchTable") &&
          typesSourceContractsSource.includes("export interface FieldConfig") &&
          typesSourceContractsSource.includes("export interface MetricDefinition") &&
          typesSourceContractsSource.includes("export interface FormulaDefinition") &&
          typesSourceContractsSource.includes("export interface RelationshipRecord") &&
          typesSourceContractsSource.includes("export interface SavedView") &&
          typesSourceContractsSource.includes("export interface TableQueryPayload") &&
          typesSourceContractsSource.includes('from "./typesSourceIntelligence"') &&
          typesSourceContractsSource.includes("SourceIntelligenceRunSummary") &&
          typesSourceContractsSource.includes("EvidenceFocus") &&
          typesSourceIntelligenceSource.includes("export interface SourceIntelligenceRunSummary") &&
          typesSourceIntelligenceSource.includes("export interface SourceIntelligenceDashboardCandidate") &&
          typesSourceIntelligenceSource.includes("export interface EvidenceFocus") &&
          typesSourceContractsSource.includes("export interface WorkbenchPayload") &&
          typesSourceContractsSource.includes("export interface RelationshipPreviewPayload") &&
          typesSourceContractsSource.includes("export interface FormulaPreviewPayload") &&
          typesSourceContractsSource.includes("export interface FormulaMutationPayload") &&
          !typesSource.includes("export interface SourceFieldProfile") &&
          !typesSource.includes("export interface WorkbenchPayload") &&
          !typesSource.includes("export interface ImportPreview") &&
          !typesSource.includes("export interface WorkspaceDomainPackRuntime") &&
          !typesSourceContractsSource.includes("export interface SourceIntelligenceRunSummary") &&
          !typesSourceContractsSource.includes("export interface EvidenceFocus") &&
          !typesSourceContractsSource.includes("export interface WorkspaceDomainPackRuntime"),
      },
    {
        label: "types-domain-contract-boundary",
        ok: existsSync(join(root, "src", "typesDomain.ts")) &&
          typesSourceContractsSource.includes('import type { SourcePipelineContract, WorkspaceDomainPackRuntime } from "./typesDomain"') &&
          typesSourceContractsSource.includes('} from "./typesDomain"') &&
          typesDomainSource.includes("export interface SourcePipelineStageContract") &&
          typesDomainSource.includes("export interface SourcePipelineContract") &&
          typesDomainSource.includes("export interface CoreSemanticHint") &&
          typesDomainSource.includes("export interface CoreLinkHint") &&
          typesDomainSource.includes("export interface CoreFunctionHint") &&
          typesDomainSource.includes("export interface CoreActionHint") &&
          typesDomainSource.includes("export interface WorkspaceDomainPackRuntime"),
      },
    {
        label: "types-query-agent-facade-boundary",
        ok: existsSync(join(root, "src", "typesQuery.ts")) &&
          existsSync(join(root, "src", "typesAgent.ts")) &&
          typesSource.includes('from "./typesQuery"') &&
          typesSource.includes('from "./typesAgent"') &&
          typesQuerySource.includes("export interface QueryResult") &&
          typesAgentSource.includes("export interface AgentAskResult") &&
          typesAgentSource.includes("export interface ActionDraft") &&
          typesAgentSource.includes("export interface ActionDraftPayload") &&
          typesAgentSource.includes('from "./typesSource"') &&
          typesAgentSource.includes('from "./typesWorkspace"') &&
          !typesSource.includes("export interface QueryResult") &&
          !typesSource.includes("export interface AgentAskResult") &&
          !typesSource.includes("export interface ActionDraft") &&
          !typesSource.includes("export interface ActionDraftPayload"),
      },
    {
        label: "app-data-actions-hook-boundary",
        ok: existsSync(join(root, "src", "useAppDataActions.ts")) &&
          appSource.includes('from "./useAppDataActions"') &&
          appSource.includes("useAppDataActions({") &&
          appSource.includes("activeWorkspaceId: status.workspace.id,") &&
          appMainViewSource.includes("handleRelationshipPreview,") &&
          appSource.includes("setFormulaPreview,") &&
          appSource.includes("setActionDrafts,") &&
          appSource.includes("navigateTo,") &&
          appSource.includes("handleSourceIntelligenceRun,") &&
          appDataActionsSource.includes("export function useAppDataActions(") &&
          appDataActionsSource.includes("type AppDataActionsOptions") &&
          appDataActionsSource.includes("const handleCommitImport = useCallback") &&
          appDataActionsSource.includes("const handleSourceIntelligenceRun = useCallback") &&
          appDataActionsSource.includes("const handleSourceDashboardDraft = useCallback") &&
          appDataActionsSource.includes("const handleDashboardRelationshipSave = useCallback") &&
          appDataActionsSource.includes("previewWorkspaceRelationship(activeWorkspaceId, options)") &&
          appDataActionsSource.includes("const handleSaveConnector = useCallback") &&
          appDataActionsSource.includes("const handleSaveView = useCallback") &&
          appDataActionsSource.includes("const { stayOnPage = false, inputs = [], ...sourceOptions }") &&
          appDataActionsSource.includes("const hasInputs = inputs.length > 0") &&
          appDataActionsSource.includes("const setSection = useCallback((section: AppSection) => navigateTo({ section })") &&
          appDataActionsSource.includes('navigateTo({ section: "views", viewKey: savedView?.view_key })') &&
          appDataActionsSource.includes('section: "dashboards"') &&
          appDataActionsSource.includes("allowLocked: true") &&
          appDataActionsSource.includes('section: "agent"') &&
          !appSource.includes("const handleCommitImport = useCallback") &&
          !appSource.includes("const handleSourceIntelligenceRun = useCallback") &&
          !appSource.includes("const handleSourceDashboardDraft = useCallback") &&
          !appSource.includes("const handleSaveConnector = useCallback") &&
          !appSource.includes("const handleSaveView = useCallback") &&
          !appSource.includes("commitImport(options)") &&
          !appSource.includes("runSourceIntelligence(request)"),
      },
    {
        label: "frontend-section-lazy-split-boundary",
        ok: appSource.includes("import { Suspense") &&
          appSource.includes('from "./appLazyModules"') &&
          appLazyModulesSource.includes('import { lazyWithRetry } from "./lazyWithRetry"') &&
          appLazyModulesSource.includes('const loadAppMainView = () => import("./components/AppMainView")') &&
          appLazyModulesSource.includes('const loadTopBar = () => import("./components/TopBar")') &&
          appLazyModulesSource.includes('const loadAgentPanel = () => import("./components/AgentPanel")') &&
          appLazyModulesSource.includes('const loadDashboardCanvas = () => import("./components/DashboardCanvas")') &&
          appLazyModulesSource.includes('const loadEvidenceView = () => import("./components/EvidenceView")') &&
          appLazyModulesSource.includes('const loadHomeOverview = () => import("./components/HomeOverview")') &&
          appLazyModulesSource.includes('const loadSettingsPanel = () => import("./components/SettingsPanel")') &&
          appLazyModulesSource.includes('const loadSourceWorkbench = () => import("./components/SourceWorkbench")') &&
          appLazyModulesSource.includes('const loadViewWorkspace = () => import("./components/ViewWorkspace")') &&
          appLazyModulesSource.includes("export const AgentPanel = lazyWithRetry(loadAgentPanel)") &&
          appLazyModulesSource.includes("export const AppMainView = lazyWithRetry(loadAppMainView)") &&
          appLazyModulesSource.includes("export const TopBar = lazyWithRetry(loadTopBar)") &&
          appLazyModulesSource.includes("export const DashboardCanvas = lazyWithRetry(loadDashboardCanvas)") &&
          appLazyModulesSource.includes("export const EvidenceView = lazyWithRetry(loadEvidenceView)") &&
          appLazyModulesSource.includes("export const HomeOverview = lazyWithRetry(loadHomeOverview)") &&
          appLazyModulesSource.includes("export const SettingsPanel = lazyWithRetry(loadSettingsPanel)") &&
          appLazyModulesSource.includes("export const SourceWorkbench = lazyWithRetry(loadSourceWorkbench)") &&
          appLazyModulesSource.includes("export const ViewWorkspace = lazyWithRetry(loadViewWorkspace)") &&
          appLazyModulesSource.includes("export const sectionPreloaders: Record<AppSection") &&
          appLazyModulesSource.includes("export const allSectionPreloaders") &&
          appLazyModulesSource.includes("export const topBarPreloader = loadTopBar") &&
          appLazyModulesSource.includes("export function scheduleIdlePreload") &&
          appLazyModulesSource.includes("requestIdleCallback") &&
          agentPanelSource.includes('import "./agentEvidenceWorkspace.css"') &&
          evidenceViewSource.includes('import "./agentEvidenceWorkspace.css"') &&
          agentEvidenceStylesSource.includes(".agentComposer {") &&
          agentEvidenceStylesSource.includes(".evidenceBusinessSummary {") &&
          agentEvidenceStylesSource.includes(".evidenceNarrativeCard {") &&
          hasCssRule(agentEvidenceStylesSource, ".evidenceGapPanel", "display: grid;") &&
          hasCssRule(agentEvidenceStylesSource, ".evidenceTrustChecks", "display: grid;") &&
          globalStylesSource.includes("container: main-panel / inline-size;") &&
          agentEvidenceStylesSource.includes("@container main-panel (max-width: 760px)") &&
          agentEvidenceStylesSource.includes("@container main-panel (max-width: 520px)") &&
          !globalStylesSource.includes(".agentComposer {") &&
          !globalStylesSource.includes(".evidenceBusinessSummary {") &&
          !globalStylesSource.includes(".evidenceNarrativeCard {") &&
          !globalStylesSource.includes(".evidenceGapPanel {") &&
          globalStylesSource.includes(".statusPill.compact {") &&
          hasCssRule(globalStylesSource, ".taskEvidenceRow summary", "cursor: pointer;") &&
          appLazyModulesSource.includes("export function ModuleLoadingPanel") &&
          appSource.includes("preloadModules(sectionPreloaders[section])") &&
          appSource.includes("preloadModules([...allSectionPreloaders, topBarPreloader])") &&
          appSource.includes('setLoadState("ready")') &&
          appSource.includes("data-load-state={loadState}") &&
          appLazyModulesSource.includes('import { getAppSection } from "./appSections"') &&
          appLazyModulesSource.includes('function sectionText(section: AppSection, language: "zh" | "en", field: "loading" | "loadingDetail")') &&
          !appSource.includes("lazy(loadAgentPanel)") &&
          !appSource.includes("function ModuleLoadingPanel") &&
          !appSource.includes('import { TopBar } from "./components/TopBar"') &&
          !appSource.includes('import { AgentPanel } from "./components/AgentPanel"') &&
          !appSource.includes('import { DashboardCanvas } from "./components/DashboardCanvas"') &&
          !appSource.includes('import { EvidenceView } from "./components/EvidenceView"') &&
          !appSource.includes('import { HomeOverview } from "./components/HomeOverview"') &&
          !appSource.includes('import { SettingsPanel } from "./components/SettingsPanel"') &&
          !appSource.includes('import { SourceWorkbench } from "./components/SourceWorkbench"') &&
          !appSource.includes('import { ViewWorkspace } from "./components/ViewWorkspace"') &&
          appLazyModulesSource.includes("function ModuleLoadingPanel") &&
          appLazyModulesSource.includes('data-testid="lazy-section-loading"') &&
          appLazyModulesSource.includes("const loadingFlow: AppSection[]") &&
          appLazyModulesSource.includes("function LoadingFlowRail") &&
          appLazyModulesSource.includes('data-testid={index === currentIndex ? "lazy-section-current-step" : undefined}') &&
          appLazyModulesSource.includes('data-testid="lazy-section-loading-support"') &&
          appLazyModulesSource.includes("dashboardModuleLoadingPanel") &&
          appLazyModulesSource.includes("dashboardLoadingFrame") &&
          appSectionsSource.includes("Preparing metrics, filters, widgets, and evidence entry points.") &&
          appSource.includes("<Suspense fallback={<ModuleLoadingPanel section={section} language={resolvedLanguage} />}>") &&
          !appLazyModulesSource.includes("loadAgentCommandDock") &&
          !appLazyModulesSource.includes("loadBusinessPathBar") &&
          !appLazyModulesSource.includes("loadInspectorPanel") &&
          !appSource.includes("<AgentCommandDock") &&
          !appSource.includes("<BusinessPathBar") &&
          !appSource.includes("<InspectorPanel") &&
          stylesSource.includes(".moduleLoadingPanel") &&
          stylesSource.includes(".moduleLoadingFlow") &&
          stylesSource.includes(".moduleLoadingSupport") &&
          stylesSource.includes(".dashboardLoadingGrid") &&
          stylesSource.includes(".dashboardLoadingMetric") &&
          stylesSource.includes(".dashboardLoadingChart"),
      },
    {
        label: "frontend-core-api-strict-no-sample-fallback",
        ok: apiSource.includes('from "./apiClient"') &&
          apiClientSource.includes("export class ApiPayloadError extends Error") &&
          apiClientSource.includes("payload: Record<string, unknown>") &&
          apiClientSource.includes("Local API request failed for") &&
          apiClientSource.includes("Local API returned invalid JSON") &&
          apiClientSource.includes("export function localApiCandidates(") &&
          apiClientSource.includes('window.location.port === "8686"') &&
          apiClientSource.includes("http://127.0.0.1:8787") &&
          apiViewsSource.includes('return fetchJsonStrict<QueryResult>("/api/query"') &&
          apiViewsSource.includes('return fetchJsonStrict<TableQueryPayload>("/api/query-table"') &&
          apiDashboardSource.includes('return fetchJsonStrict<Record<string, unknown>>("/api/dashboard/business-template"') &&
          apiDashboardSource.includes('return fetchJsonStrict<Record<string, unknown>>("/api/dashboard/widgets"') &&
          apiDashboardSource.includes('return fetchJsonStrict<Record<string, unknown>>("/api/dashboard/modules"') &&
          apiDashboardSource.includes('return fetchJsonStrict<Record<string, unknown>>("/api/dashboards/operation"') &&
          apiDashboardSource.includes('return fetchJsonStrict<DashboardFilterPayload>("/api/dashboards/filters"') &&
          apiAgentSource.includes('return fetchJsonStrict<AgentAskResult>("/api/agent/ask"') &&
          apiAgentSource.includes('return fetchJsonStrict<AgentAskResult>("/api/agent/explain"') &&
          appSource.includes('from "./appWorkspaceModel"') &&
          appWorkspaceModelSource.includes("export function actionErrorResult") &&
          actionRecoveryModelSource.includes("no-sample-fallback-for-core-action") &&
          appWorkspaceModelSource.includes("actionRecoveryFromError(error) ?? buildActionRecovery(action, error)") &&
          appSource.includes('setLastActionResult(actionErrorResult("initial-load", error))') &&
          appDataActionsSource.includes('setLastActionResult(actionErrorResult("query", error))') &&
          appDataActionsSource.includes('setLastActionResult(actionErrorResult("query-table", error))') &&
          appAgentActionsSource.includes('setLastActionResult(actionErrorResult("agent-ask", error))') &&
          appAgentActionsSource.includes('setLastActionResult(actionErrorResult("agent-explain", error))') &&
          appDashboardActionsSource.includes('actionErrorResult("business-dashboard", error)') &&
          appDashboardActionsSource.includes('actionErrorResult("dashboard-widget", error)') &&
          appDashboardActionsSource.includes('actionErrorResult("dashboard-modules", error)'),
      },
    {
        label: "api-domain-boundary",
        ok: apiSource.includes('export { askAgent, askAgentReadOnly, confirmAction, getActionDrafts } from "./apiAgent"') &&
          apiSource.includes('from "./apiDashboard"') &&
          apiSource.includes('from "./apiSettings"') &&
          apiSource.includes('from "./apiSource"') &&
          apiSource.includes('from "./apiViews"') &&
          apiSource.includes('export { createWorkspace, deleteWorkspace, getDashboards, getWorkbenchData, getWorkspaceStatus, renameWorkspace, selectWorkspace } from "./apiWorkspace"') &&
          apiAgentSource.includes('from "./apiClient"') &&
          apiAgentSource.includes('emptyActionDrafts') &&
          apiDashboardSource.includes('from "./apiClient"') &&
          apiDashboardSource.includes('getDashboardWidgetCatalog') &&
          apiDashboardSource.includes('dashboardWidgetOperation') &&
          apiDashboardSource.includes('dashboardFilterOperation') &&
          apiModelSource.includes('from "./apiClient"') &&
          apiModelSource.includes('updateFieldConfig') &&
          apiModelSource.includes('queryRelationship') &&
          apiModelSource.includes('previewFormula') &&
          apiModelSource.includes('recommendIndexes') &&
          apiModelSource.includes('"/api/relationships/query"') &&
          apiModelSource.includes('"/api/formulas/save"') &&
          apiSourceApiSource.includes('from "./apiClient"') &&
          apiSourceApiSource.includes('previewImportWithOptions') &&
          apiSourceApiSource.includes('runSourceIntelligence') &&
          apiSourceApiSource.includes('createSourceDashboardDraft') &&
          apiSourceApiSource.includes('"/api/import/preview"') &&
          apiSourceApiSource.includes('"/api/source-intelligence/dashboard-draft"') &&
          apiSettingsSource.includes('from "./apiClient"') &&
          apiSettingsSource.includes('"/api/preferences"') &&
          apiSettingsSource.includes('"/api/theme-palettes"') &&
          apiSettingsSource.includes('"/api/config/validate"') &&
          apiSettingsSource.includes('"/api/config/export"') &&
          apiSettingsSource.includes('"/api/config/apply"') &&
          apiViewsSource.includes('from "./apiClient"') &&
          apiViewsSource.includes('runTableQuery') &&
          apiViewsSource.includes('saveView') &&
          apiViewsSource.includes('"/api/views/save"') &&
          apiViewsSource.includes('"/api/views/delete"') &&
          apiWorkspaceSource.includes('from "./apiClient"') &&
          apiWorkspaceSource.includes("type WorkspaceEnvelope") &&
          apiWorkspaceSource.includes("export function deleteWorkspace") &&
          apiWorkspaceSource.includes("export function renameWorkspace") &&
          apiWorkspaceSource.includes('"/api/workspaces"') &&
          apiWorkspaceSource.includes('"/api/dashboards"') &&
          apiWorkspaceSource.includes('"/api/workbench?limit=12"'),
      },
    {
        label: "frontend-service-diagnostics",
        ok: topBarSource.includes("const showServiceDiagnostics = apiMode !== \"live\"") &&
          (topBarSource.includes('className="topBarStack"') || topBarSource.includes("topBarStack workbenchTopBar")) &&
          topBarSource.includes('data-testid="service-diagnostics"') &&
          topBarSource.includes('data-testid="service-diagnostics-title"') &&
          topBarSource.includes('data-testid="service-diagnostics-technical"') &&
          topBarSource.includes('data-testid="service-diagnostics-commands"') &&
          topBarSource.includes('data-testid="service-diagnostics-notes"') &&
          topBarSource.includes("启动命令和端口") &&
          topBarSource.includes("npm run local:start") &&
          topBarSource.includes("界面 8686 · API 8787") &&
          topBarSource.includes("本地数据服务尚未就绪") &&
          !topBarSource.includes("npm run api") &&
          packageJson.scripts?.dev === "node scripts/dev.mjs" &&
          packageJson.scripts?.["dev:ui"] === "vite" &&
          devScriptSource.includes("portIsOpen(8787)") &&
          devScriptSource.includes("portIsOpen(8686)") &&
          devScriptSource.includes("async function apiIsCompatible()") &&
          devScriptSource.includes('payload?.service === "aibi-hybrid-api"') &&
          devScriptSource.includes("async function uiIsCompatible()") &&
          devScriptSource.includes("<title>AIBI-C</title>") &&
          devScriptSource.includes("async function stopOwnedPortProcess") &&
          devScriptSource.includes("compatible existing service detected; reusing it.") &&
          devScriptSource.includes("port is occupied by an incompatible service") &&
          devScriptSource.includes('start("api:8787", ["run", "api"])') &&
          devScriptSource.includes('start("ui:8686", ["run", "dev:ui"])') &&
          stylesSource.includes(".topBarStack") &&
          stylesSource.includes(".serviceDiagnostics.fallback") &&
          stylesSource.includes(".serviceDiagnosticsTechnical") &&
          stylesSource.includes(".serviceDiagnosticsCommands code"),
      },
    {
        label: "frontend-home-workspace-start-guide",
        ok: homeOverviewSource.includes('className="workspaceJourney"') &&
          homeOverviewSource.includes('aria-label={biText("可信分析流程", "Trusted analysis flow")}') &&
          ["data", "evidence", "question", "review"].every((key) => homeOverviewSource.includes(`{ key: "${key}"`)) &&
          homeOverviewSource.includes('aria-current={state === "current" ? "step" : undefined}') &&
          homeOverviewSource.includes('disabled={state === "upcoming"}') &&
          homeOverviewSource.includes('data-testid="workspace-primary-task"') &&
          !homeOverviewSource.includes("HomeWorkspaceStartGuide") &&
          !homeOverviewSource.includes("buildHomeGuideSteps"),
      },
    {
        label: "frontend-home-overview-model-boundary",
        ok: !homeOverviewSource.includes('from "../homeOverviewModel"') &&
          homeOverviewSource.includes("const questionStarters = [") &&
          homeOverviewSource.includes("const hasData =") &&
          homeOverviewSource.includes("const latestUsableRun = latestUsableSourceIntelligenceRun(sourceIntelligenceRuns)") &&
          homeOverviewSource.includes("const hasCurrentEvidence = Boolean(latestUsableRun)") &&
          homeOverviewSource.includes("const hasPendingDraft =") &&
          homeOverviewSource.includes("const currentStep =") &&
          homeOverviewSource.includes("const workflowSteps = useMemo(() => [") &&
          homeOverviewSource.includes("async function submitQuestion") &&
          homeOverviewSource.includes("async function generateEvidence") &&
          !homeOverviewSource.includes("buildHomeReadiness") &&
          !homeOverviewSource.includes("buildHomeGuideSteps") &&
          !homeOverviewSource.includes("sourceDashboardCandidate"),
      },
    {
        label: "safe-value-helper-boundary",
        ok: safeValueSource.includes("export function numberValue") &&
          safeValueSource.includes("export function objectRecord") &&
          safeValueSource.includes("export function recordArray") &&
          safeValueSource.includes("export function stringValue") &&
          agentPanelModelSource.includes('from "./safeValue"') &&
          agentPanelModelSource.includes("export { objectRecord }") &&
          sourceWorkbenchModelSource.includes('from "./safeValue"') &&
          sourceWorkbenchModelSource.includes("export { numberValue }") &&
          metricRepairModelSource.includes('from "./safeValue"') &&
          !agentPanelModelSource.includes("export function objectRecord(value: unknown)") &&
          !metricRepairModelSource.includes("function numberValue(value: unknown)") &&
          !metricRepairModelSource.includes("function objectRecord(value: unknown)") &&
          !sourceWorkbenchModelSource.includes("export function numberValue(value: unknown)"),
      },
    {
        label: "retired-cost-monitor-surface-absent",
        ok: !serverDashboardRoutesSource.includes("b-cost-monitor") &&
          !serverRuntimeSource.includes("b-cost-monitor") &&
          !serverRuntimeSource.includes("readBCostMonitorValidation") &&
          !apiSource.includes("getBCostMonitorValidation") &&
          !apiDashboardSource.includes("b-cost-monitor") &&
          !biCliParserSource.includes('"cost-monitor"'),
      },
    {
        label: "server-runtime-boundary",
        ok: existsSync(join(root, "server", "serverRuntime.ts")) &&
          serverIndexSource.includes('from "./serverRuntime"') &&
          serverIndexSource.includes("const cli = (args: string[]) => runCli(root, args)") &&
          !serverIndexSource.includes('spawn("python"') &&
          !serverIndexSource.includes("function pushDashboardWidgetStyleArgs(") &&
          !serverIndexSource.includes("function numberValue(") &&
          serverRuntimeSource.includes("export function sendJson(") &&
          serverRuntimeSource.includes("function enrichedErrorBody(") &&
          serverRuntimeSource.includes("buildActionRecovery(action, error)") &&
          serverRuntimeSource.includes("response.end(JSON.stringify(enrichedErrorBody(body), null, 2))") &&
          serverIndexSource.includes("function actionForApiPath(url: URL)") &&
          serverIndexSource.includes("action: url.pathname.startsWith(\"/api/\") ? actionForApiPath(url) : \"static\"") &&
          serverRuntimeSource.includes("export function readBody(") &&
          serverRuntimeSource.includes("export function runCli(") &&
          serverRuntimeSource.includes("export function pushDashboardWidgetStyleArgs(") &&
          !serverRuntimeSource.includes("readBCostMonitorValidation"),
      },
    {
        label: "server-static-boundary",
        ok: existsSync(join(root, "server", "staticServer.ts")) &&
          serverIndexSource.includes('import { handleStatic } from "./staticServer"') &&
          serverIndexSource.includes("await handleStatic(response, url.pathname, root)") &&
          !serverIndexSource.includes("readFile(path)") &&
          !serverIndexSource.includes("extname(path)") &&
          serverStaticSource.includes("export async function handleStatic(") &&
          serverStaticSource.includes('join(root, "dist")') &&
          serverStaticSource.includes('join(dist, "index.html")') &&
          serverStaticSource.includes("readFile(path)") &&
          serverStaticSource.includes("extname(path)"),
      },
    {
        label: "server-dashboard-routes-boundary",
        ok: existsSync(join(root, "server", "dashboardRoutes.ts")) &&
          serverIndexSource.includes('import { handleDashboardApi } from "./dashboardRoutes"') &&
          serverIndexSource.includes("await handleDashboardApi({ cli, request, response, url })") &&
          !serverIndexSource.includes('url.pathname === "/api/dashboard/widget-catalog"') &&
          !serverIndexSource.includes('url.pathname === "/api/dashboards"') &&
          !serverIndexSource.includes('url.pathname === "/api/validation/b-cost-monitor"') &&
          serverDashboardRoutesSource.includes("export async function handleDashboardApi(") &&
          serverDashboardRoutesSource.includes('url.pathname === "/api/dashboard/widget-catalog"') &&
          serverDashboardRoutesSource.includes('url.pathname === "/api/dashboard/widgets"') &&
          serverDashboardRoutesSource.includes('url.pathname === "/api/dashboards/filters"') &&
          serverDashboardRoutesSource.includes('url.pathname === "/api/cli/capabilities"'),
      },
    {
        label: "server-source-routes-boundary",
        ok: existsSync(join(root, "server", "sourceRoutes.ts")) &&
          serverIndexSource.includes('import { handleSourceApi } from "./sourceRoutes"') &&
          serverIndexSource.includes("await handleSourceApi({") &&
          serverIndexSource.includes("startSourceIntelligenceJob: (body) => jobRuntime.startSourceIntelligence(body)") &&
          !serverIndexSource.includes('url.pathname === "/api/source-intelligence/run"') &&
          !serverIndexSource.includes('url.pathname === "/api/import/preview"') &&
          !serverIndexSource.includes('url.pathname === "/api/import/commit"') &&
          !serverIndexSource.includes('url.pathname === "/api/connectors"') &&
          !serverIndexSource.includes('url.pathname.startsWith("/api/source-runs/")') &&
          serverSourceRoutesSource.includes("export async function handleSourceApi(") &&
          serverSourceRoutesSource.includes('url.pathname === "/api/source-intelligence/run"') &&
          serverSourceRoutesSource.includes('url.pathname === "/api/import/commit"') &&
          serverSourceRoutesSource.includes('url.pathname === "/api/connectors"') &&
          serverSourceRoutesSource.includes('url.pathname.startsWith("/api/source-runs/")'),
      },
    {
        label: "server-settings-routes-boundary",
        ok: existsSync(join(root, "server", "settingsRoutes.ts")) &&
          serverIndexSource.includes('import { handleSettingsApi } from "./settingsRoutes"') &&
          serverIndexSource.includes("await handleSettingsApi({ cli, request, response, url })") &&
          !serverIndexSource.includes('url.pathname === "/api/preferences"') &&
          !serverIndexSource.includes('url.pathname === "/api/theme-palettes"') &&
          !serverIndexSource.includes('url.pathname === "/api/config/validate"') &&
          serverSettingsRoutesSource.includes("export async function handleSettingsApi(") &&
          serverSettingsRoutesSource.includes('url.pathname === "/api/preferences"') &&
          serverSettingsRoutesSource.includes('url.pathname === "/api/theme-palettes"') &&
          serverSettingsRoutesSource.includes('url.pathname === "/api/config/validate"') &&
          serverSettingsRoutesSource.includes('url.pathname === "/api/config/apply"'),
      },
    {
        label: "server-model-routes-boundary",
        ok: existsSync(join(root, "server", "modelRoutes.ts")) &&
          serverIndexSource.includes('import { handleModelApi } from "./modelRoutes"') &&
          serverIndexSource.includes("await handleModelApi({ cli, request, response, url })") &&
          !serverIndexSource.includes('url.pathname === "/api/relationships/preview"') &&
          !serverIndexSource.includes('url.pathname === "/api/formulas/preview"') &&
          !serverIndexSource.includes('url.pathname === "/api/indexes/recommend"') &&
          !serverIndexSource.includes('url.pathname === "/api/semantics"') &&
          !serverIndexSource.includes('url.pathname === "/api/metrics"') &&
          serverModelRoutesSource.includes("export async function handleModelApi(") &&
          serverModelRoutesSource.includes('url.pathname === "/api/relationships/query"') &&
          serverModelRoutesSource.includes('url.pathname === "/api/formulas/save"') &&
          serverModelRoutesSource.includes('url.pathname === "/api/indexes/create"') &&
          serverModelRoutesSource.includes('url.pathname === "/api/fields/update"') &&
          serverModelRoutesSource.includes('url.pathname === "/api/metrics/query"'),
      },
    {
        label: "server-query-routes-boundary",
        ok: existsSync(join(root, "server", "queryRoutes.ts")) &&
          serverIndexSource.includes('import { handleQueryApi } from "./queryRoutes"') &&
          serverIndexSource.includes("await handleQueryApi({ cli, request, response, url })") &&
          !serverIndexSource.includes('url.pathname === "/api/query"') &&
          !serverIndexSource.includes('url.pathname === "/api/query-table"') &&
          !serverIndexSource.includes('url.pathname === "/api/views/save"') &&
          serverQueryRoutesSource.includes("export async function handleQueryApi(") &&
          serverQueryRoutesSource.includes('url.pathname === "/api/query"') &&
          serverQueryRoutesSource.includes('url.pathname === "/api/query-table"') &&
          serverQueryRoutesSource.includes('url.pathname === "/api/views/save"') &&
          serverQueryRoutesSource.includes('url.pathname === "/api/views/delete"'),
      },
    {
        label: "server-cli-arg-builders-boundary",
        ok: existsSync(join(root, "server", "cliArgBuilders.ts")) &&
          serverCliArgBuildersSource.includes("export function appendCliFilters(") &&
          serverCliArgBuildersSource.includes("export function appendCliSorts(") &&
          serverQueryRoutesSource.includes('from "./cliArgBuilders"') &&
          serverDashboardRoutesSource.includes('from "./cliArgBuilders"') &&
          serverModelRoutesSource.includes('from "./cliArgBuilders"') &&
          serverModelRoutesSource.includes("export function appendRelationshipFilterArgs(") &&
          serverModelRoutesSource.includes("export function appendRelationshipPreaggregationArg(") &&
          serverModelRoutesSource.includes("appendRelationshipFilterArgs(args, body)") &&
          serverModelRoutesSource.includes("appendRelationshipPreaggregationArg(args, body)") &&
          serverDashboardRoutesSource.includes("appendCliFilters(args, body.filters)") &&
          serverQueryRoutesSource.includes("appendCliSorts(args, body.sort)") &&
          !serverQueryRoutesSource.includes("for (const filter of body.filters)") &&
          !serverQueryRoutesSource.includes("for (const sort of body.sort)") &&
          !serverDashboardRoutesSource.includes("for (const filter of body.filters)"),
      },
    {
        label: "server-agent-routes-boundary",
        ok: existsSync(join(root, "server", "agentRoutes.ts")) &&
          serverIndexSource.includes('import { handleAgentApi } from "./agentRoutes"') &&
          serverIndexSource.includes("await handleAgentApi({ cli, request, response, root, url })") &&
          !serverIndexSource.includes('url.pathname === "/api/agent/ask"') &&
          !serverIndexSource.includes('url.pathname === "/api/actions/confirm"') &&
          serverAgentRoutesSource.includes("export async function handleAgentApi(") &&
          serverAgentRoutesSource.includes('url.pathname === "/api/agent/ask"') &&
          serverAgentRoutesSource.includes('url.pathname === "/api/agent/explain"') &&
          serverAgentRoutesSource.includes('url.pathname === "/api/actions/confirm"') &&
          serverAgentRoutesSource.includes('url.pathname === "/api/actions"'),
      },
    {
        label: "api-health-status-routes",
        ok: serverWorkspaceRoutesSource.includes('url.pathname === "/api/health"') &&
          serverWorkspaceRoutesSource.includes('service: "aibi-hybrid-api"') &&
          serverWorkspaceRoutesSource.includes('url.pathname === "/api/status"') &&
          serverWorkspaceRoutesSource.includes('const status = await cli(["status"])'),
      },
    {
        label: "server-workspace-routes-boundary",
        ok: existsSync(join(root, "server", "workspaceRoutes.ts")) &&
          serverIndexSource.includes('import { handleWorkspaceApi } from "./workspaceRoutes"') &&
          serverIndexSource.includes("await handleWorkspaceApi({ cli, port, request, response, url })") &&
          !serverIndexSource.includes('url.pathname === "/api/workspaces"') &&
          !serverIndexSource.includes('url.pathname === "/api/sources"') &&
          serverWorkspaceRoutesSource.includes("export async function handleWorkspaceApi(") &&
          serverWorkspaceRoutesSource.includes('url.pathname === "/api/workspaces"') &&
          serverWorkspaceRoutesSource.includes('op === "delete"') &&
          serverWorkspaceRoutesSource.includes('"workspace-delete"') &&
          serverWorkspaceRoutesSource.includes('url.pathname === "/api/workbench"') &&
          serverWorkspaceRoutesSource.includes('url.pathname === "/api/navigation"') &&
          serverWorkspaceRoutesSource.includes('url.pathname === "/api/sources"'),
      },
  );
  appendAppArchitectureContractExtendedChecks(context);
}
