export function appendAppArchitectureContractChecks(context) {
  const {
    checks,
    actionRecoveryModelSource,
    agentCommandDockSource,
    agentEvidenceStylesSource,
    agentPanelModelSource,
    agentPanelSource,
    apiAgentSource,
    apiClientSource,
    apiDashboardSource,
    apiModelSource,
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
    bCostMonitorComparison,
    biCliSource,
    businessPathBarSource,
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
    homeActionDockSource,
    homeDetailedPathPanelSource,
    homeOperatingSummaryPanelSource,
    homeOverviewModelSource,
    homeOverviewSource,
    homeProductIntelligencePanelSource,
    homeScenarioPacksPanelSource,
    homeWorkspaceStartGuideSource,
    implementationStatusSource,
    inspectorControllerSource,
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
    sidebarAssetSectionsSource,
    sidebarSource,
    sidebarWorkspaceCardSource,
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
  const appSource = `${appEntrySource}\n${appMainViewSource}\n${inspectorControllerSource}`;
  checks.push(
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
          appWorkspaceModelSource.includes("return \"dashboards\"") &&
          appWorkspaceModelSource.includes("return \"sources\"") &&
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
          apiModelSource.includes('emptyRelationshipPreview') &&
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
          !typesSource.includes("export interface DomainPackRuntime") &&
          !typesSourceContractsSource.includes("export interface SourceIntelligenceRunSummary") &&
          !typesSourceContractsSource.includes("export interface EvidenceFocus") &&
          !typesSourceContractsSource.includes("export interface DomainPackRuntime"),
      },
    {
        label: "types-domain-contract-boundary",
        ok: existsSync(join(root, "src", "typesDomain.ts")) &&
          typesSourceContractsSource.includes('import type { SourcePipelineContract } from "./typesDomain"') &&
          typesSourceContractsSource.includes('} from "./typesDomain"') &&
          typesDomainSource.includes("export interface SourcePipelineStageContract") &&
          typesDomainSource.includes("export interface SourcePipelineContract") &&
          typesDomainSource.includes("export interface DomainSemanticHint") &&
          typesDomainSource.includes("export interface DomainLinkHint") &&
          typesDomainSource.includes("export interface DomainFunctionHint") &&
          typesDomainSource.includes("export interface DomainActionHint") &&
          typesDomainSource.includes("export interface DomainPackRuntime"),
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
          appSource.includes("setRelationshipPreview,") &&
          appSource.includes("setFormulaPreview,") &&
          appSource.includes("setActionDrafts,") &&
          appSource.includes("handleSourceIntelligenceRun,") &&
          appDataActionsSource.includes("export function useAppDataActions(") &&
          appDataActionsSource.includes("type AppDataActionsOptions") &&
          appDataActionsSource.includes("const handleCommitImport = useCallback") &&
          appDataActionsSource.includes("const handleSourceIntelligenceRun = useCallback") &&
          appDataActionsSource.includes("const handleSourceDashboardDraft = useCallback") &&
          appDataActionsSource.includes("const handleDashboardRelationshipSave = useCallback") &&
          appDataActionsSource.includes("const handleSaveConnector = useCallback") &&
          appDataActionsSource.includes("const handleSaveView = useCallback") &&
          appDataActionsSource.includes("const { stayOnPage = false, ...sourceOptions }") &&
          appDataActionsSource.includes("const hasInputs = Array.isArray(sourceOptions.inputs) && sourceOptions.inputs.length > 0") &&
          appDataActionsSource.includes("setSection(\"sources\")") &&
          appDataActionsSource.includes("setSection(\"views\")") &&
          appDataActionsSource.includes("setSection(\"agent\")") &&
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
          appLazyModulesSource.includes("import { lazy } from \"react\"") &&
          appLazyModulesSource.includes('const loadAgentPanel = () => import("./components/AgentPanel")') &&
          appLazyModulesSource.includes('const loadDashboardCanvas = () => import("./components/DashboardCanvas")') &&
          appLazyModulesSource.includes('const loadEvidenceView = () => import("./components/EvidenceView")') &&
          appLazyModulesSource.includes('const loadHomeOverview = () => import("./components/HomeOverview")') &&
          appLazyModulesSource.includes('const loadInspectorPanel = () => import("./components/InspectorPanel")') &&
          appLazyModulesSource.includes('const loadSettingsPanel = () => import("./components/SettingsPanel")') &&
          appLazyModulesSource.includes('const loadSourceWorkbench = () => import("./components/SourceWorkbench")') &&
          appLazyModulesSource.includes('const loadViewWorkspace = () => import("./components/ViewWorkspace")') &&
          appLazyModulesSource.includes("export const AgentPanel = lazy(loadAgentPanel)") &&
          appLazyModulesSource.includes("export const DashboardCanvas = lazy(loadDashboardCanvas)") &&
          appLazyModulesSource.includes("export const EvidenceView = lazy(loadEvidenceView)") &&
          appLazyModulesSource.includes("export const HomeOverview = lazy(loadHomeOverview)") &&
          appLazyModulesSource.includes("export const InspectorPanel = lazy(loadInspectorPanel)") &&
          appLazyModulesSource.includes("export const SettingsPanel = lazy(loadSettingsPanel)") &&
          appLazyModulesSource.includes("export const SourceWorkbench = lazy(loadSourceWorkbench)") &&
          appLazyModulesSource.includes("export const ViewWorkspace = lazy(loadViewWorkspace)") &&
          appLazyModulesSource.includes("export const sectionPreloaders: Record<AppSection") &&
          appLazyModulesSource.includes("export function scheduleIdlePreload") &&
          appLazyModulesSource.includes("requestIdleCallback") &&
          agentPanelSource.includes('import "./agentEvidenceWorkspace.css"') &&
          evidenceViewSource.includes('import "./agentEvidenceWorkspace.css"') &&
          agentEvidenceStylesSource.includes(".agentComposer {") &&
          agentEvidenceStylesSource.includes(".evidenceBusinessSummary {") &&
          agentEvidenceStylesSource.includes(".evidenceNarrativeCard {") &&
          agentEvidenceStylesSource.includes(".evidenceGapPanel {") &&
          agentEvidenceStylesSource.includes(".evidenceTrustChecks {") &&
          globalStylesSource.includes("container: main-panel / inline-size;") &&
          agentEvidenceStylesSource.includes("@container main-panel (max-width: 760px)") &&
          agentEvidenceStylesSource.includes("@container main-panel (max-width: 520px)") &&
          !globalStylesSource.includes(".agentComposer {") &&
          !globalStylesSource.includes(".evidenceBusinessSummary {") &&
          !globalStylesSource.includes(".evidenceNarrativeCard {") &&
          !globalStylesSource.includes(".evidenceGapPanel {") &&
          globalStylesSource.includes(".statusPill.compact {") &&
          globalStylesSource.includes(".taskEvidenceRow summary {") &&
          appLazyModulesSource.includes("export function ModuleLoadingPanel") &&
          appLazyModulesSource.includes("export function InspectorLoadingPanel") &&
          appSource.includes("preloadModules(sectionPreloaders[section])") &&
          appSource.includes("preloadModules([...allSectionPreloaders, inspectorPreloader])") &&
          appLazyModulesSource.includes('import { getAppSection } from "./appSections"') &&
          appLazyModulesSource.includes('function sectionText(section: AppSection, language: "zh" | "en", field: "loading" | "loadingDetail")') &&
          !appSource.includes("lazy(loadAgentPanel)") &&
          !appSource.includes("function ModuleLoadingPanel") &&
          !appSource.includes('import { AgentPanel } from "./components/AgentPanel"') &&
          !appSource.includes('import { DashboardCanvas } from "./components/DashboardCanvas"') &&
          !appSource.includes('import { EvidenceView } from "./components/EvidenceView"') &&
          !appSource.includes('import { HomeOverview } from "./components/HomeOverview"') &&
          !appSource.includes('import { InspectorPanel } from "./components/InspectorPanel"') &&
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
          appLazyModulesSource.includes("function InspectorLoadingPanel") &&
          appLazyModulesSource.includes('data-testid="lazy-inspector-loading"') &&
          appLazyModulesSource.includes("inspectorLoadingStack") &&
          appSource.includes("<Suspense fallback={<ModuleLoadingPanel section={section} language={resolvedLanguage} />}>") &&
          appSource.includes("<Suspense fallback={<InspectorLoadingPanel language={resolvedLanguage} />}>") &&
          stylesSource.includes(".moduleLoadingPanel") &&
          stylesSource.includes(".moduleLoadingFlow") &&
          stylesSource.includes(".moduleLoadingSupport") &&
          stylesSource.includes(".dashboardLoadingGrid") &&
          stylesSource.includes(".dashboardLoadingMetric") &&
          stylesSource.includes(".dashboardLoadingChart") &&
          stylesSource.includes(".inspectorLoadingPanel") &&
          stylesSource.includes(".inspectorLoadingStack"),
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
          topBarSource.includes("查看启动命令和端口") &&
          topBarSource.includes("npm run dev") &&
          topBarSource.includes("npm run api") &&
          topBarSource.includes("前端 8686 · API 8787") &&
          topBarSource.includes("等待导入数据") &&
          topBarSource.includes("没有可用数据表") &&
          packageJson.scripts?.dev === "node scripts/dev.mjs" &&
          packageJson.scripts?.["dev:ui"]?.includes("--port 8686") &&
          devScriptSource.includes("portIsOpen(8787)") &&
          devScriptSource.includes("portIsOpen(8686)") &&
          devScriptSource.includes("async function apiIsCompatible()") &&
          devScriptSource.includes('payload?.service === "aibi-hybrid-api"') &&
          devScriptSource.includes("async function uiIsCompatible()") &&
          devScriptSource.includes("<title>AIBI Hybrid</title>") &&
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
        ok: homeOverviewSource.includes("<HomeWorkspaceStartGuide") &&
          homeWorkspaceStartGuideSource.includes("data-testid=\"workspace-start-guide\"") &&
          homeWorkspaceStartGuideSource.includes("data-testid=\"workspace-start-guide-primary\"") &&
          homeWorkspaceStartGuideSource.includes("data-testid={`workspace-guide-step-${step.key}`}") &&
          homeWorkspaceStartGuideSource.includes("data-testid=\"workspace-start-guide-boundary\"") &&
          homeWorkspaceStartGuideSource.includes("Follow the business path before learning configuration") &&
          homeOverviewSource.includes("buildHomeGuideSteps({") &&
          ["source", "profile", "dashboard", "ask"].every((key) => homeOverviewModelSource.includes(`key: "${key}"`)) &&
          homeWorkspaceStartGuideSource.includes("Imports, deletes, overwrites, relationship saves, and dashboard writes become drafts or previews before execution."),
      },
    {
        label: "frontend-home-overview-model-boundary",
        ok: homeOverviewSource.includes('from "../homeOverviewModel"') &&
          homeOverviewModelSource.includes("export function buildStarterQuestions") &&
          homeOverviewModelSource.includes("export type GuideStep") &&
          homeOverviewModelSource.includes("export function buildHomeReadiness") &&
          homeOverviewModelSource.includes("export function buildHomeGuideSteps") &&
          homeOverviewModelSource.includes("export function sourceDashboardCandidate") &&
          homeOverviewModelSource.includes('from "./safeValue"') &&
          homeOverviewModelSource.includes("export { numberValue, objectRecord, recordArray, stringValue }") &&
          homeOverviewModelSource.includes("SourceIntelligenceDashboardCandidate") &&
          homeOverviewSource.includes("buildHomeReadiness({") &&
          homeOverviewSource.includes("buildHomeGuideSteps({") &&
          !homeOverviewSource.includes("function sourceDashboardCandidate(") &&
          !homeOverviewSource.includes("const starterQuestions = [") &&
          !homeOverviewSource.includes("const guideSteps = useMemo<GuideStep[]>"),
      },
    {
        label: "safe-value-helper-boundary",
        ok: safeValueSource.includes("export function numberValue") &&
          safeValueSource.includes("export function objectRecord") &&
          safeValueSource.includes("export function recordArray") &&
          safeValueSource.includes("export function stringValue") &&
          homeOverviewModelSource.includes('from "./safeValue"') &&
          agentPanelModelSource.includes('from "./safeValue"') &&
          agentPanelModelSource.includes("export { objectRecord }") &&
          sourceWorkbenchModelSource.includes('from "./safeValue"') &&
          sourceWorkbenchModelSource.includes("export { numberValue }") &&
          metricRepairModelSource.includes('from "./safeValue"') &&
          !homeOverviewModelSource.includes("export function numberValue(value: unknown)") &&
          !homeOverviewModelSource.includes("export function objectRecord(value: unknown)") &&
          !agentPanelModelSource.includes("export function objectRecord(value: unknown)") &&
          !metricRepairModelSource.includes("function numberValue(value: unknown)") &&
          !metricRepairModelSource.includes("function objectRecord(value: unknown)") &&
          !sourceWorkbenchModelSource.includes("export function numberValue(value: unknown)"),
      },
    {
        label: "b-cost-monitor-comparison-artifact",
        ok: bCostMonitorComparison === null ||
          (bCostMonitorComparison?.dashboard?.key === "xlsx_cost_monitor_20260609" &&
            bCostMonitorComparison?.dashboard?.widgetCount === 23 &&
            bCostMonitorComparison?.sources?.length === 10 &&
            Object.values(bCostMonitorComparison?.rowCounts ?? {}).length === 4 &&
            Object.values(bCostMonitorComparison?.rowCounts ?? {}).every((row) => row.dbRows === row.sourceRows && row.dbColumns === row.sourceColumns) &&
            bCostMonitorComparison?.widgets?.filter((widget) => widget.chartType !== "text").length === 22 &&
            bCostMonitorComparison?.widgets?.filter((widget) => widget.chartType !== "text").every((widget) => widget.matches === true) &&
            bCostMonitorComparison?.formulaDefinitions?.["动账净额"]?.includes("出账") &&
            bCostMonitorComparison?.formulaDefinitions?.["收入"]?.includes("订单实付应结")),
      },
    {
        label: "api-b-cost-monitor-validation-route",
        ok: serverDashboardRoutesSource.includes('url.pathname === "/api/validation/b-cost-monitor"') &&
          serverDashboardRoutesSource.includes("readBCostMonitorValidation(root)") &&
          serverRuntimeSource.includes("b-cost-monitor-comparison.json") &&
          serverRuntimeSource.includes("matchedNonTextWidgets") &&
          apiSource.includes("getBCostMonitorValidation") &&
          apiDashboardSource.includes('"/api/validation/b-cost-monitor"'),
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
          serverRuntimeSource.includes("export async function readBCostMonitorValidation("),
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
          serverIndexSource.includes("await handleDashboardApi({ cli, request, response, root, url })") &&
          !serverIndexSource.includes('url.pathname === "/api/dashboard/widget-catalog"') &&
          !serverIndexSource.includes('url.pathname === "/api/dashboards"') &&
          !serverIndexSource.includes('url.pathname === "/api/validation/b-cost-monitor"') &&
          serverDashboardRoutesSource.includes("export async function handleDashboardApi(") &&
          serverDashboardRoutesSource.includes('url.pathname === "/api/dashboard/widget-catalog"') &&
          serverDashboardRoutesSource.includes('url.pathname === "/api/dashboard/widgets"') &&
          serverDashboardRoutesSource.includes('url.pathname === "/api/dashboards/filters"') &&
          serverDashboardRoutesSource.includes('url.pathname === "/api/b-cli/capabilities"'),
      },
    {
        label: "server-source-routes-boundary",
        ok: existsSync(join(root, "server", "sourceRoutes.ts")) &&
          serverIndexSource.includes('import { handleSourceApi } from "./sourceRoutes"') &&
          serverIndexSource.includes("await handleSourceApi({ cli, request, response, url })") &&
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
        label: "server-agent-routes-boundary",
        ok: existsSync(join(root, "server", "agentRoutes.ts")) &&
          serverIndexSource.includes('import { handleAgentApi } from "./agentRoutes"') &&
          serverIndexSource.includes("await handleAgentApi({ cli, request, response, url })") &&
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
    {
        label: "frontend-home-four-action-import-proof",
        ok: homeOverviewSource.includes("<ProductActivationPanel") &&
          homeOverviewSource.includes('data-testid="home-shortcut-details"') &&
          homeOverviewSource.includes("<HomeActionDock") &&
          homeOverviewSource.includes("<HomeOperatingSummaryPanel") &&
          homeOperatingSummaryPanelSource.includes('className="quickQuestionBox"') &&
          homeOperatingSummaryPanelSource.includes('className="operatingSummaryGrid"') &&
          homeOperatingSummaryPanelSource.includes('className="trustGrid"') &&
          homeOperatingSummaryPanelSource.includes("buildStarterQuestions(latestRun)") &&
          !homeOverviewSource.includes('className="quickQuestionBox"') &&
          !homeOverviewSource.includes('className="operatingSummaryGrid"') &&
          homeActionDockSource.includes('data-testid="home-action-dock"') &&
          homeActionDockSource.includes('data-testid="home-action-import"') &&
          homeActionDockSource.includes('data-testid="home-action-cost-monitor"') &&
          homeActionDockSource.includes('data-testid="home-action-ask"') &&
          homeActionDockSource.includes('data-testid="home-action-confirm"') &&
          !homeOverviewSource.includes("HomeRealDataValidationPanel") &&
          !homeOverviewSource.includes("getBCostMonitorValidation") &&
          !homeOverviewSource.includes("matchedNonTextWidgets") &&
          productActivationPanelSource.includes('testId = "product-activation-panel"') &&
          productActivationPanelSource.includes('data-testid="product-activation-primary"') &&
          productActivationModelSource.includes("export function buildProductActivation") &&
          stylesSource.includes(".homeActionDock") &&
          stylesSource.includes(".productActivationPanel") &&
          stylesSource.includes(".homeActionCard.primary") &&
          homeOverviewSource.includes("<HomeDetailedPathPanel") &&
          homeDetailedPathPanelSource.includes('data-testid="home-detailed-path"'),
      },
    {
        label: "frontend-no-data-onboarding-ux-boundary",
        ok: homeOverviewSource.includes("<ProductActivationPanel") &&
          homeOverviewSource.includes("buildProductActivation({") &&
          homeOverviewSource.includes("useQualityDoctor(hasData, workbench)") &&
          /if \(!enabled\) \{\s*setResult\(null\);\s*return;\s*\}/.test(useQualityDoctorSource) &&
          /\{hasData \? \(\s*<>/.test(homeOverviewSource) &&
          !homeOverviewSource.includes('data-testid="home-first-run-focus"') &&
          homeOverviewSource.includes("homeBetaDetails") &&
          homeOverviewSource.includes('data-testid="home-secondary-path-details"') &&
          homeOverviewSource.includes('data-testid="home-detailed-path-details"') &&
          homeOverviewSource.includes('data-testid="home-operating-summary-details"') &&
          homeActionDockSource.includes('className={hasData ? "homeActionDock" : "homeActionDock firstRun"}') &&
          homeActionDockSource.includes('disabled={!hasData}') &&
          productActivationModelSource.includes('ProductActivationStepKey = "connect" | "profile" | "chart" | "evidence" | "confirm"') &&
          productActivationModelSource.includes("const activeStepKey: ProductActivationStepKey = flow.activeStage") &&
          workspaceFlowModelSource.includes("export function buildWorkspaceFlow") &&
          workspaceFlowModelSource.includes("export function isBusinessStepLockedByFlow") &&
          workspaceFlowModelSource.includes("export function resolveSectionForFlow") &&
          appSource.includes("const workspaceFlow = useMemo(() => buildWorkspaceFlow") &&
          appSource.includes("resolveSectionForFlow(section, workspaceFlow)") &&
          sidebarSource.includes("isSectionLockedByFlow") &&
          businessPathBarSource.includes("isBusinessStepLockedByFlow") &&
          productActivationModelSource.includes("Charts and evidence appear only after a real import") &&
          productActivationModelSource.includes("full industry boards remain beta") &&
          productActivationPanelSource.includes('data-testid={`product-activation-step-${step.key}`}') &&
          sourceWorkbenchSource.includes("const hasData = tables.length > 0 || status.counts.tables > 0") &&
          sourceWorkbenchSource.includes("const showExpertWorkbench = showAdvanced") &&
          sourceWorkbenchSource.includes('testId="source-product-activation"') &&
          sourceWorkbenchSource.includes("onOpenBusinessStep") &&
          !sourceWorkbenchSource.includes('data-testid="source-no-data-guide"') &&
          sourceWorkbenchSource.includes('data-testid="source-expert-details"') &&
          dashboardCanvasSource.includes("onOpenBusinessStep: (step: BusinessPathStepKey) => void") &&
          dashboardCanvasSource.includes('testId="dashboard-product-activation"') &&
          !dashboardCanvasSource.includes('data-testid="dashboard-no-data-route"') &&
          dashboardCanvasSource.includes('data-testid="dashboard-guided-edit-details"') &&
          dashboardCanvasSource.includes('data-testid="dashboard-advanced-edit-details"') &&
          dashboardCanvasSource.includes('data-testid="dashboard-contract-details"') &&
          agentPanelSource.includes("onOpenSources: () => void") &&
          agentPanelSource.includes('data-testid="agent-no-data-route"') &&
          agentPanelSource.includes('data-testid="agent-suggestion-details"') &&
          agentPanelSource.includes('data-testid="agent-evidence-audit-details"') &&
          agentPanelSource.includes('data-testid="agent-task-packet-details"') &&
          evidenceViewSource.includes("onOpenBusinessStep: (step: BusinessPathStepKey) => void") &&
          evidenceViewSource.includes("useQualityDoctor(hasData, workbench)") &&
          /if \(!enabled\) \{\s*setResult\(null\);\s*return;\s*\}/.test(useQualityDoctorSource) &&
          evidenceViewSource.includes('testId="evidence-product-activation"') &&
          !evidenceViewSource.includes('data-testid="evidence-no-data-route"') &&
          evidenceViewSource.includes('data-testid="evidence-explanation-details"') &&
          evidenceViewSource.includes('data-testid="evidence-receipts-details"') &&
          viewWorkspaceSource.includes('data-testid="view-dashboard-bridge-details"') &&
          viewWorkspaceSource.includes('data-testid="view-agent-task-details"') &&
          viewWorkspaceSource.includes('data-testid="view-manage-details"') &&
          settingsPanelSource.includes('data-testid="settings-sandbox-details"') &&
          settingsPanelSource.includes('data-testid="settings-acceptance-details"') &&
          settingsPanelSource.includes('data-testid="settings-config-portability-details"') &&
          sidebarWorkspaceCardSource.includes('<details className="workspaceManageDetails">') &&
          sidebarAssetSectionsSource.includes('data-testid="sidebar-source-asset-details"') &&
          sidebarAssetSectionsSource.includes('data-testid="sidebar-dashboard-asset-details"') &&
          sidebarAssetSectionsSource.includes('data-testid="sidebar-evidence-asset-details"') &&
          businessPathBarSource.includes('className={compact ? "businessPathBar compact" : "businessPathBar"}') &&
          agentCommandDockSource.includes("const shouldMinimize = !hasTables && !assistantOpen && activeSection !== \"agent\"") &&
          agentCommandDockSource.includes("onboardingMinimized") &&
          !stylesSource.includes(".firstRunFocusPanel") &&
          !stylesSource.includes(".sourceNoDataGuide") &&
          stylesSource.includes(".productActivationSteps") &&
          stylesSource.includes(".productActivationFactGrid") &&
          stylesSource.includes(".sourceBeginnerMode .workbenchGrid") &&
          stylesSource.includes(".noDataRoutePanel") &&
          stylesSource.includes(".workspaceManageDetails") &&
          stylesSource.includes(".workspaceManageDetails:not([open]) > :not(summary)") &&
          stylesSource.includes(".progressiveDetails") &&
          stylesSource.includes(".dashboardProgressiveGrid") &&
          stylesSource.includes(".evidenceProgressiveGrid") &&
          stylesSource.includes(".sidebarAssetDetails") &&
          stylesSource.includes(".homeIntelligenceGrid") &&
          stylesSource.includes(".sandboxCompareFacts") &&
          stylesSource.includes(".sandboxVersionHints") &&
          stylesSource.includes(".businessPathBar.compact") &&
          stylesSource.includes(".agentCommandDock.onboardingMinimized"),
      },
    {
        label: "product-ux-acceptance-documentation-boundary",
        ok: productUxStandardDocSource.includes("## First Success Flow Standard") &&
          productUxStandardDocSource.includes("## Object Ownership Matrix") &&
          productUxStandardDocSource.includes("## Delete And Rollback Standard") &&
          productUxStandardDocSource.includes("docs/product-acceptance-matrix.md") &&
          productAcceptanceMatrixDocSource.includes("Empty workspace") &&
          productAcceptanceMatrixDocSource.includes("Create one chart") &&
          productAcceptanceMatrixDocSource.includes("Delete source or object") &&
          productAcceptanceMatrixDocSource.includes("Production no-demo boundary") &&
          productAcceptanceMatrixDocSource.includes("validation-inputs") &&
          docsReadmeSource.includes("product-acceptance-matrix.md") &&
          prdDocSource.includes("## Requirement Ownership") &&
          !prdDocSource.includes("source-intelligence fixtures") &&
          implementationStatusSource.includes("Product activation shows only the current necessary step"),
      },
    {
        label: "frontend-production-copy-no-example-placeholders",
        ok: productAcceptanceMatrixDocSource.includes("- `npm run preflight`") &&
          dashboardCanvasSource.includes('name: biText("未命名看板", "Untitled dashboard")') &&
          !dashboardCanvasSource.includes("临时看板") &&
          !dashboardCanvasSource.includes("Temporary dashboard") &&
          dashboardBusinessTaskStripSource.includes("描述指标、维度、时间范围或想比较的对象") &&
          dashboardBusinessTaskStripSource.includes("Describe the metric, dimension, time range, or comparison") &&
          !dashboardBusinessTaskStripSource.includes("例如：") &&
          !dashboardBusinessTaskStripSource.includes("Example:") &&
          agentCommandDockSource.includes("输入你想分析的问题或要生成的图表") &&
          agentCommandDockSource.includes("Enter the question to analyze or chart to create") &&
          !agentCommandDockSource.includes("直接问：") &&
          !agentCommandDockSource.includes("Ask: which channel") &&
          docsReadmeSource.includes("development-roadmap.md") &&
          docsReadmeSource.includes("`npm run preflight` 是本地交付前总入口") &&
          prdDocSource.includes("`npm run preflight` 通过，作为本地交付前总入口") &&
          developmentRoadmapDocSource.includes("## Delivered Baseline") &&
          developmentRoadmapDocSource.includes("## Current Development Order") &&
          developmentRoadmapDocSource.includes("Generalization acceptance") &&
          developmentRoadmapDocSource.includes("Brand and release identity") &&
          developmentRoadmapDocSource.includes("Use `npm run preflight` as the final local acceptance gate"),
      },
    {
        label: "home-detailed-path-panel-boundary",
        ok: existsSync(join(root, "src", "components", "HomeDetailedPathPanel.tsx")) &&
          homeOverviewSource.includes('import { HomeDetailedPathPanel } from "./HomeDetailedPathPanel"') &&
          homeOverviewSource.includes("<HomeDetailedPathPanel") &&
          !homeOverviewSource.includes('data-testid="home-detailed-path"') &&
          homeDetailedPathPanelSource.includes("type HomeDetailedPathPanelProps") &&
          homeDetailedPathPanelSource.includes("runDashboardTemplate: (confirm: boolean) => Promise<void>") &&
          homeDetailedPathPanelSource.includes("onSourceIntelligenceRun: () => Promise<Record<string, unknown> | void>") &&
          homeDetailedPathPanelSource.includes("查看更多数据源、通用看板和 Agent 路径") &&
          homeDetailedPathPanelSource.includes("预览看板草案") &&
          homeDetailedPathPanelSource.includes("帮我生成经营看板并说明证据"),
      },
    {
        label: "frontend-state-driven-landing",
        ok: appSource.includes("function sectionFromUrl(): AppSection | null") &&
          appSource.includes('import { isAppSection } from "./appSections"') &&
          appSectionsSource.includes("export function isAppSection") &&
          appSource.includes("return isAppSection(section) ? section : null") &&
          appSource.includes("return sectionFromUrl() ?? \"home\"") &&
          appSource.includes('from "./appWorkspaceModel"') &&
          appWorkspaceModelSource.includes("export function preferredLandingSection") &&
          appWorkspaceModelSource.includes("if (hasDashboard) return \"dashboards\"") &&
          appWorkspaceModelSource.includes("if (hasSource) return \"sources\"") &&
          appSource.includes("explicitInitialSectionRef") &&
          appSource.includes("autoLandingAppliedRef") &&
          appSource.includes('import { refreshStatusDashboardsWorkbenchDrafts } from "./appRefreshModel"') &&
          appRefreshModelSource.includes("export async function refreshStatusDashboardsWorkbenchDrafts") &&
          appSource.includes("setSection(preferredLandingSection(surface.status, surface.workbench, surface.dashboards))") &&
          !appSource.includes("setSection(\"home\");"),
      },
    {
        label: "app-agent-actions-hook-boundary",
        ok: existsSync(join(root, "src", "useAppAgentActions.ts")) &&
          appSource.includes('from "./useAppAgentActions"') &&
          appSource.includes("useAppAgentActions({") &&
          appSource.includes("setAgent,") &&
          appSource.includes("handleAgentCommandAsk,") &&
          appSource.includes("handleConfirmAction,") &&
          appAgentActionsSource.includes("export function useAppAgentActions(") &&
          appAgentActionsSource.includes("type AppAgentActionsOptions") &&
          appAgentActionsSource.includes("const handleAsk = useCallback") &&
          appAgentActionsSource.includes("const handleAskReadOnly = useCallback") &&
          appAgentActionsSource.includes("const handleConfirmAction = useCallback") &&
          appAgentActionsSource.includes("const handleRejectAction = useCallback") &&
          appAgentActionsSource.includes("confirmAction(actionKey, true, true)") &&
          appAgentActionsSource.includes("setSection(\"dashboards\")") &&
          appAgentActionsSource.includes("setSection(\"agent\")") &&
          !appSource.includes("const handleAsk = useCallback") &&
          !appSource.includes("const handleConfirmAction = useCallback") &&
          !appSource.includes("const handleRejectAction = useCallback"),
      },
    {
        label: "app-settings-actions-hook-boundary",
        ok: existsSync(join(root, "src", "useAppSettingsActions.ts")) &&
          appSource.includes('from "./useAppSettingsActions"') &&
          appSource.includes("useAppSettingsActions({") &&
          appSource.includes("handleSavePreferences,") &&
          appSource.includes("handleApplyConfig,") &&
          appSettingsActionsSource.includes("export function useAppSettingsActions") &&
          appSettingsActionsSource.includes("type AppSettingsActionsOptions") &&
          appSettingsActionsSource.includes("const handleSavePreferences = useCallback") &&
          appSettingsActionsSource.includes("const handleSaveThemePalette = useCallback") &&
          appSettingsActionsSource.includes("const handleValidateConfig = useCallback") &&
          appSettingsActionsSource.includes("const handleExportConfig = useCallback") &&
          appSettingsActionsSource.includes("const handleApplyConfig = useCallback") &&
          appSettingsActionsSource.includes("setSection(\"settings\")") &&
          appSettingsActionsSource.includes("refreshStatusWorkbenchDashboards()") &&
          appRefreshModelSource.includes("export async function refreshStatusWorkbenchDashboards") &&
          !appSource.includes("const handleSavePreferences = useCallback") &&
          !appSource.includes("const handleApplyConfig = useCallback"),
      },
    {
        label: "no-sample-runtime-domain-boundary",
        ok: !existsSync(join(root, "src", "sampleAgentData.ts")) &&
          !existsSync(join(root, "src", "sampleThemeData.ts")) &&
          existsSync(join(root, "src", "defaultThemeData.ts")) &&
          !existsSync(join(root, "src", "sampleData.ts")) &&
          !existsSync(join(root, "src", "sampleWorkspaceData.ts")) &&
          !existsSync(join(root, "src", "sampleWorkspaceQueryData.ts")) &&
          defaultThemeDataSource.includes("export const defaultUserPreferences") &&
          defaultThemeDataSource.includes("export const defaultThemePalettes") &&
          themeSource.includes('from "./defaultThemeData"') &&
          !biCliSource.includes(retiredSeedEnvName) &&
          !verifySource.includes(retiredSeedEnvName) &&
          !verifyBiCliAgentContractSource.includes(retiredSeedEnvName) &&
          !existsSync(join(root, "tools", "seed_orchestration_service.py")) &&
          !existsSync(join(root, "tools", "seed_default_objects_service.py")) &&
          emptyWorkspaceDataSource.includes("export const emptyWorkspaceStatus") &&
          !("verify:a-testdata" in packageJson.scripts) &&
          !existsSync(join(root, "scripts", "verify-a-testdata-source-intelligence.mjs")) &&
          !biCliSource.includes("A_TESTDATA_03_05_DIRS") &&
          !biCliSource.includes("--a-testdata-03-05") &&
          /elif op == "create":\s*resolved_table_key = ""/.test(biCliSource) &&
          biCliSource.includes('table_key = str(proposed.get("defaultTableKey") or "")') &&
          biCliSource.includes('layout = {"version": 1, "grid": "12-col", "widgets": [], "globalFilters": []}') &&
          !biCliSource.includes('("bar", "渠道净销售"') &&
          !biCliSource.includes('("table", "订单明细"') &&
          productUxStandardDocSource.includes("Creating an empty dashboard creates only the dashboard container") &&
          byLabel["cli-source-intelligence-no-input-blocked"].ok === true &&
          String(byLabel["cli-source-intelligence-no-input-blocked"].parsed?.error ?? "").includes("requires imported source paths"),
      },
    {
        label: "frontend-dashboard-status-refresh-after-writes",
        ok: appSource.includes('from "./useAppDashboardActions"') &&
          appSource.includes("useAppDashboardActions({") &&
          appSource.includes("setActiveDashboardKey,") &&
          appSource.includes("handleBusinessDashboardOperation") &&
          appSource.includes("handleDashboardModulesSave") &&
          appSource.includes("handleDashboardOperation") &&
          !appSource.includes("const handleDashboardOperation = useCallback") &&
          !appSource.includes("const handleDashboardModulesSave = useCallback") &&
          appDashboardActionsSource.includes("export function useAppDashboardActions") &&
          appDashboardActionsSource.includes("type AppDashboardActionsOptions") &&
          appDashboardActionsSource.includes("refreshStatusAndDashboards()") &&
          appDashboardActionsSource.includes("refreshStatusWorkbenchDashboards()") &&
          appRefreshModelSource.includes("export async function refreshStatusAndDashboards") &&
          appRefreshModelSource.includes("export async function refreshStatusWorkbenchDashboards") &&
          appRefreshModelSource.includes("normalizeStatus(status)") &&
          appRefreshModelSource.includes("normalizeDashboards(dashboards)") &&
          appRefreshModelSource.includes("normalizeWorkbench(workbench)") &&
          appDashboardActionsSource.includes("actionErrorResult(\"business-dashboard\", error)"),
      },
    {
        label: "frontend-workspace-switcher",
        ok: sidebarWorkspaceCardSource.includes('data-testid="workspace-switcher"') &&
          sidebarSource.includes("onWorkspaceCreate") &&
          sidebarSource.includes("onWorkspaceSelect") &&
          sidebarSource.includes("onWorkspaceDelete") &&
          sidebarSource.includes("selectWorkspaceFromInput") &&
          sidebarSource.includes("createWorkspaceFromInput") &&
          sidebarSource.includes("deleteWorkspaceFromInput") &&
          appSource.includes('from "./useAppWorkspaceActions"') &&
          appSource.includes("useAppWorkspaceActions({") &&
          appWorkspaceActionsSource.includes("createWorkspace(name, false)") &&
          appWorkspaceActionsSource.includes("selectWorkspace(workspaceId, true)") &&
          appWorkspaceActionsSource.includes("deleteWorkspace(workspaceId, false)") &&
          appWorkspaceActionsSource.includes("renameWorkspace(workspaceId, nextName, false)") &&
          appWorkspaceActionsSource.includes("const handleWorkspaceDelete = useCallback") &&
          appWorkspaceActionsSource.includes("reloadWorkspaceSurface"),
      },
    {
        label: "sidebar-workspace-card-component-boundary",
        ok: existsSync(join(root, "src", "components", "SidebarWorkspaceCard.tsx")) &&
          sidebarSource.includes('import { SidebarWorkspaceCard } from "./SidebarWorkspaceCard"') &&
          sidebarSource.includes("<SidebarWorkspaceCard") &&
          !sidebarSource.includes('data-testid="workspace-switcher"') &&
          sidebarWorkspaceCardSource.includes("type SidebarWorkspaceCardProps") &&
          sidebarWorkspaceCardSource.includes("createWorkspaceFromInput: () => Promise<void>") &&
          sidebarWorkspaceCardSource.includes("selectWorkspaceFromInput: (workspaceId: string) => Promise<void>") &&
          sidebarWorkspaceCardSource.includes("deleteWorkspaceFromInput: (workspaceId: string) => Promise<void>") &&
          sidebarWorkspaceCardSource.includes('data-testid="workspace-delete-list"') &&
          sidebarWorkspaceCardSource.includes("deletableWorkspaces") &&
          sidebarWorkspaceCardSource.includes("window.confirm") &&
          sidebarWorkspaceCardSource.includes("工作区沙盒") &&
          sidebarWorkspaceCardSource.includes("写入类动作仍必须先生成草案并确认") &&
          sidebarWorkspaceCardSource.includes('title={currentWorkspace.name}') &&
          hasCssRule(stylesSource, ".assetPanel", "overflow-x: hidden;", "overflow-y: auto;") &&
          hasCssRule(stylesSource, ".assetSectionTitle strong", "text-overflow: ellipsis;", "white-space: nowrap;") &&
          verifyUiRealImportSource.includes("ui-real-import-no-asset-panel-x-overflow") &&
          verifyUiRealImportSource.includes("ui-evidence-${evidenceViewport.key}-narrow-grid-collapses") &&
          verifyUiRealImportSource.includes("real-import-evidence-${evidenceViewport.key}.png"),
      },
    {
        label: "sidebar-asset-sections-component-boundary",
        ok: existsSync(join(root, "src", "components", "SidebarAssetSections.tsx")) &&
          sidebarSource.includes('import { SidebarAssetSections } from "./SidebarAssetSections"') &&
          sidebarSource.includes("<SidebarAssetSections") &&
          !sidebarSource.includes('aria-labelledby="source-assets-title"') &&
          !sidebarSource.includes('aria-labelledby="dashboard-assets-title"') &&
          sidebarAssetSectionsSource.includes("type SidebarAssetSectionsProps") &&
          sidebarAssetSectionsSource.includes('aria-labelledby="source-assets-title"') &&
          sidebarAssetSectionsSource.includes('aria-labelledby="dashboard-assets-title"') &&
          sidebarAssetSectionsSource.includes('aria-labelledby="agent-assets-title"') &&
          sidebarAssetSectionsSource.includes('aria-labelledby="evidence-assets-title"') &&
          sidebarAssetSectionsSource.includes("全局提问与确认") &&
          sidebarAssetSectionsSource.includes("右下角都可以直接提问") &&
          !sidebarAssetSectionsSource.includes("promptStack") &&
          !sidebarAssetSectionsSource.includes("用自然语言改看板") &&
          sidebarAssetSectionsSource.includes('aria-labelledby="settings-assets-title"'),
      },
    {
        label: "frontend-app-section-model-boundary",
        ok: existsSync(join(root, "src", "appSections.ts")) &&
          appSectionsSource.includes('export type AppSection = "home" | "sources" | "views" | "dashboards" | "agent" | "evidence" | "settings"') &&
          appSectionsSource.includes("export const appSections: Record<AppSection, AppSectionMeta>") &&
          appSectionsSource.includes("export const primaryAppSections") &&
          appSectionsSource.includes("export function getAppSection") &&
          appSectionsSource.includes("export function isAppSection") &&
          sidebarSource.includes('from "../appSections"') &&
          sidebarSource.includes("primaryAppSections.map") &&
          sidebarSource.includes("utilityAppSections.map") &&
          topBarSource.includes("getAppSection(activeSection)") &&
          appLazyModulesSource.includes("getAppSection(section)") &&
          appSource.includes("isAppSection(section) ? section : null"),
      },
    {
        label: "frontend-desktop-shell-fluid-width",
        ok: stylesSource.includes("--shell-asset-width: clamp(280px, 17vw, 324px)") &&
          stylesSource.includes("--shell-inspector-width: clamp(300px, 18vw, 340px)") &&
          stylesSource.includes("grid-template-columns: var(--shell-rail-width) var(--shell-asset-width) minmax(0, 1fr) var(--shell-inspector-width)") &&
          stylesSource.includes("grid-template-columns: var(--shell-rail-width) var(--shell-asset-width) minmax(0, 1fr) var(--shell-inspector-collapsed-width)") &&
          stylesSource.includes("height: 100dvh") &&
          stylesSource.includes("overflow: hidden") &&
          !stylesSource.includes("--desktop-width") &&
          !stylesSource.includes("min-width: var(--desktop-width)") &&
          !stylesSource.includes("width: max(100vw"),
      },
    {
        label: "frontend-sidebar-dashboard-asset-typing",
        ok: sidebarAssetSectionsSource.includes("resolveDashboardAsset(item: NavigationModule | DashboardPage") &&
          sidebarAssetSectionsSource.includes("type DashboardAsset") &&
          sidebarAssetSectionsSource.includes('import type { ActionDraft, AgentAskResult, DashboardPage, DashboardPayload, NavigationModule') &&
          sidebarAssetSectionsSource.includes("const asset = resolveDashboardAsset(item, dashboardPages)") &&
          !sidebarAssetSectionsSource.includes("as any") &&
          !sidebarSource.includes("as any"),
      },
    {
        label: "frontend-home-draft-state-requires-confirmation",
        ok: homeOverviewSource.includes('agent.requiresConfirmation && agent.actionDraft?.status === "draft"'),
      },
    {
        label: "frontend-home-dashboard-preview-visible",
        ok: homeOverviewSource.includes("const [dashboardPlan, setDashboardPlan]") &&
          homeOverviewSource.includes("setDashboardPlan(result)") &&
          homeDetailedPathPanelSource.includes('data-testid="home-dashboard-preview-result"') &&
          homeDetailedPathPanelSource.includes('data-testid="home-dashboard-preview-confirm"') &&
          homeDetailedPathPanelSource.includes('data-testid="home-dashboard-preview-open"') &&
          homeDetailedPathPanelSource.includes("runDashboardTemplate(false)") &&
          homeDetailedPathPanelSource.includes("runDashboardTemplate(true)") &&
          homeOverviewSource.includes("op: confirm ? \"create\" : \"draft\"") &&
          !homeOverviewSource.includes("runBusinessDashboardOperation({ op: \"create\""),
      },
    {
        label: "frontend-product-intelligence-model",
        ok: productIntelligenceModelSource.includes("export function buildScenarioPacks") &&
          productIntelligenceModelSource.includes("export function buildDataQualityDoctor") &&
          productIntelligenceModelSource.includes("export function buildObjectInspectorModel") &&
          productIntelligenceModelSource.includes("export function buildEvidenceNarrative") &&
          productIntelligenceModelSource.includes("export function buildSandboxComparison") &&
          productIntelligenceModelSource.includes('candidate?.status !== "ready"') &&
          productIntelligenceModelSource.includes('item.status === "executed"') &&
          productIntelligenceModelSource.includes("return []"),
      },
    {
        label: "frontend-home-scenario-quality-sandbox-panels",
        ok: homeOverviewSource.includes("buildScenarioPacks(status, workbench)") &&
          homeOverviewSource.includes("buildDataQualityDoctor(status, workbench") &&
          homeOverviewSource.includes("buildSandboxComparison(status, workbench)") &&
          homeOverviewSource.includes("buildMetricRepairPlan(qualityDoctorResult, workbench)") &&
          homeOverviewSource.includes("<HomeScenarioPacksPanel") &&
          homeOverviewSource.includes("<HomeProductIntelligencePanel") &&
          homeScenarioPacksPanelSource.includes('data-testid="home-scenario-packs"') &&
          homeScenarioPacksPanelSource.includes('data-testid={`scenario-pack-${pack.key}`}') &&
          homeProductIntelligencePanelSource.includes('data-testid="home-product-intelligence"') &&
          homeProductIntelligencePanelSource.includes('data-testid="home-data-quality-doctor"') &&
          homeProductIntelligencePanelSource.includes('data-testid="home-quality-metric-sql"') &&
          homeProductIntelligencePanelSource.includes('data-testid="home-quality-missing-semantics"') &&
          homeProductIntelligencePanelSource.includes('data-testid="home-quality-repair-draft"') &&
          homeProductIntelligencePanelSource.includes('data-testid="home-quality-failed-metrics"') &&
          homeProductIntelligencePanelSource.includes('data-testid="home-metric-repair-wizard"') &&
          homeProductIntelligencePanelSource.includes('actionsTestId="home-semantic-binding-drafts"') &&
          homeProductIntelligencePanelSource.includes('loopTestId="home-semantic-confirm-loop"') &&
          homeProductIntelligencePanelSource.includes("onSetSemantic={onSetSemantic}") &&
          homeProductIntelligencePanelSource.includes("onSourceIntelligenceRun={onSourceIntelligenceRun}") &&
          homeOverviewSource.includes("useQualityDoctor(hasData, workbench)") &&
          useQualityDoctorSource.includes("getQualityDoctor()") &&
          homeProductIntelligencePanelSource.includes('data-testid="home-sandbox-compare"') &&
          homeOverviewSource.includes("runScenarioPrompt") &&
          homeOverviewSource.includes("previewScenarioTemplate") &&
          stylesSource.includes(".scenarioPackPanel") &&
          stylesSource.includes(".qualityDoctorPanel") &&
          stylesSource.includes(".qualityDoctorMetricSql") &&
          stylesSource.includes(".metricSemanticChips") &&
          stylesSource.includes(".metricRepairDraft") &&
          stylesSource.includes(".metricRepairWizard") &&
          stylesSource.includes(".semanticBindingDrafts") &&
          stylesSource.includes(".semanticRepairLoop") &&
          stylesSource.includes(".semanticBindingActions") &&
          stylesSource.includes(".semanticRepairResult") &&
          stylesSource.includes(".metricFailureSamples") &&
          stylesSource.includes(".sandboxComparePanel"),
      },
    {
        label: "frontend-semantic-confirm-loop-component",
        ok: metricSemanticRepairActionsSource.includes("export function MetricSemanticRepairActions") &&
          metricSemanticRepairActionsSource.includes("runSemanticAction") &&
          metricSemanticRepairActionsSource.includes("rerunSourceIntelligence") &&
          metricSemanticRepairActionsSource.includes("confirm,") &&
          metricSemanticRepairActionsSource.includes("stayOnPage: true") &&
          metricSemanticRepairActionsSource.includes("onSetSemantic({") &&
          metricSemanticRepairActionsSource.includes("if (!plan.rerunInputs.length)") &&
          metricSemanticRepairActionsSource.includes("请先在数据源工作台导入本地文件或文件夹") &&
          metricSemanticRepairActionsSource.includes("onSourceIntelligenceRun({ inputs: plan.rerunInputs") &&
          metricSemanticRepairActionsSource.includes("data-testid={loopTestId}") &&
          metricSemanticRepairActionsSource.includes("data-testid={actionsTestId}") &&
          metricSemanticRepairActionsSource.includes("semanticBindingActions") &&
          metricSemanticRepairActionsSource.includes("semanticRepairFooter") &&
          metricSemanticRepairActionsSource.includes("snapshotFromResult") &&
          !metricSemanticRepairActionsSource.includes("debug sample") &&
          metricSemanticRepairActionsSource.includes("previewedSemantics") &&
          metricSemanticRepairActionsSource.includes("draft.requiresPreview") &&
          metricSemanticRepairActionsSource.includes('data-testid={`${loopTestId}-benefit`}') &&
          metricSemanticRepairActionsSource.includes('data-testid={`${loopTestId}-comparison`}') &&
          metricSemanticRepairActionsSource.includes("semanticBindingRisk") &&
          metricSemanticRepairActionsSource.includes("预演") &&
          metricSemanticRepairActionsSource.includes("先预演") &&
          metricSemanticRepairActionsSource.includes("确认") &&
          metricSemanticRepairActionsSource.includes("重跑画像"),
      },
    {
        label: "frontend-semantic-confirm-app-wiring",
        ok: appSource.includes("onSetSemantic={handleSetSemantic}") &&
          appSource.includes("onSourceIntelligenceRun={handleSourceIntelligenceRun}") &&
          evidenceViewSource.includes("onSetSemantic:") &&
          evidenceViewSource.includes("onSourceIntelligenceRun:") &&
          evidenceViewSource.includes('loopTestId="evidence-semantic-confirm-loop"') &&
          appDataActionsSource.includes("stayOnPage = false") &&
          appDataActionsSource.includes("const { stayOnPage = false, ...semanticOptions } = options") &&
          appDataActionsSource.includes("setSemantic(semanticOptions)") &&
          appDataActionsSource.includes('if (!stayOnPage) setSection("sources")'),
      },
    {
        label: "frontend-metric-repair-model",
        ok: metricRepairModelSource.includes("export function buildMetricRepairPlan") &&
          metricRepairModelSource.includes("const semanticAliases") &&
          metricRepairModelSource.includes("SemanticBindingDraft") &&
          metricRepairModelSource.includes("EvidenceGapItem") &&
          metricRepairModelSource.includes("rerunInputs") &&
          metricRepairModelSource.includes("benefitSummary") &&
          metricRepairModelSource.includes("manifestInputRoots") &&
          metricRepairModelSource.includes("semanticRiskTerms") &&
          metricRepairModelSource.includes("riskForSemantic") &&
          metricRepairModelSource.includes("riskConfidenceCap") &&
          metricRepairModelSource.includes("preview-required") &&
          metricRepairModelSource.includes("needs-human-confirmation") &&
          metricRepairModelSource.includes("待选择字段"),
      },
    {
        label: "frontend-evidence-gap-panel",
        ok: evidenceViewSource.includes("buildMetricRepairPlan(qualityDoctorResult, workbench)") &&
          evidenceViewSource.includes("useQualityDoctor(hasData, workbench)") &&
          useQualityDoctorSource.includes("getQualityDoctor()") &&
          evidenceViewSource.includes('data-testid="evidence-gap-panel"') &&
          evidenceViewSource.includes('actionsTestId="evidence-gap-semantic-actions"') &&
          evidenceViewSource.includes('data-testid="evidence-gap-items"') &&
          evidenceViewSource.includes("MetricSemanticRepairActions") &&
          stylesSource.includes(".evidenceGapPanel") &&
          stylesSource.includes(".evidenceGapItems"),
      },
    {
        label: "quality-doctor-cli-api",
        ok: biCliSource.includes("def quality_doctor_command(") &&
          biCliSource.includes("def metric_sql_doctor_from_run(") &&
          biCliSource.includes("metric-sql-compiler.json") &&
          biCliSource.includes("metric-query-results.json") &&
          biCliSource.includes('sub.add_parser("quality-doctor")') &&
          biCliSource.includes('elif args.command == "quality-doctor"') &&
          serverWorkspaceRoutesSource.includes('url.pathname === "/api/quality/doctor"') &&
          serverWorkspaceRoutesSource.includes('cli(["quality-doctor"])') &&
          apiSource.includes("export function getQualityDoctor()") &&
          apiSource.includes('"/api/quality/doctor"') &&
          byLabel["cli-quality-doctor"].parsed?.source === "hybrid-quality-doctor" &&
          Array.isArray(byLabel["cli-quality-doctor"].parsed?.issues) &&
          byLabel["cli-quality-doctor"].parsed?.metricSql?.planned >= 0 &&
          byLabel["cli-quality-doctor"].parsed?.metricSql?.blocked >= 0 &&
          Array.isArray(byLabel["cli-quality-doctor"].parsed?.latestSourceIntelligenceRun?.inputRoots) &&
          Array.isArray(byLabel["cli-quality-doctor"].parsed?.metricSql?.missingSemantics) &&
          Array.isArray(byLabel["cli-quality-doctor"].parsed?.metricSql?.failedSamples) &&
          Array.isArray(byLabel["cli-quality-doctor"].parsed?.metricSql?.semanticBindingDrafts) &&
          byLabel["cli-quality-doctor"].parsed?.metricSql?.repairDraft?.kind === "metric-sql.repair" &&
          Array.isArray(byLabel["cli-quality-doctor"].parsed?.metricSql?.repairDraft?.semanticBindingDrafts),
      },
    {
        label: "frontend-initial-agent-readonly",
        ok: appSource.includes("setAgent(emptyAgentResult)") &&
          appSource.includes("setPreview(emptyImportPreview)") &&
          appSource.includes("setQuery(emptyQueryResult)") &&
          appSource.includes("setTableQuery(emptyTableQuery)") &&
          !appSource.includes("askAgent(\"先告诉我当前工作区能回答什么，不要创建任何草案\")") &&
          !appSource.includes("askAgent(\"生成经营分析计划\")"),
      }
  );
}
