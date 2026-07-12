export function appendAppArchitectureContractExtendedChecks(context) {
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
    appNavigationModelSource,
    appRefreshModelSource,
    appSectionsSource,
    appSettingsActionsSource,
    appSource: appEntrySource,
    appMainViewSource,
    appWorkspaceActionsSource,
    appWorkspaceModelSource,
    bCostMonitorComparison,
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
    preflightSource,
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
    sidebarAssetModulesSource,
    sidebarSource,
    sidebarWorkspaceCardSource,
    sourceWorkbenchModelSource,
    sourceWorkbenchActionPanelSource,
    sourceWorkbenchSource,
    sourceWorkbenchStateSource,
    sourceWorkbenchViewSource,
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
    verifyUiFlowSource,
    verifyUiRealImportSource,
    viewWorkspaceSource,
    workspaceFlowModelSource,
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
          productActivationPanelSource.includes("const step = activation.primaryStep") &&
          productActivationPanelSource.includes('data-testid={`product-activation-step-${step.key}`}') &&
          !productActivationPanelSource.includes("activation.steps.map") &&
          sourceWorkbenchStateSource.includes("const hasData = tables.length > 0 || status.counts.tables > 0") &&
          sourceWorkbenchStateSource.includes("const showExpertWorkbench = showAdvanced") &&
          sourceWorkbenchStateSource.includes("if (!focusedTableKey || !tableKeySet.has(focusedTableKey)) return") &&
          !sourceWorkbenchSource.includes("ProductActivationPanel") &&
          sourceWorkbenchViewSource.includes("onOpenDashboard={onOpenDashboard}") &&
          !sourceWorkbenchViewSource.includes('data-testid="source-no-data-guide"') &&
          sourceWorkbenchActionPanelSource.includes('data-testid="source-expert-toggle"') &&
          !sourceWorkbenchViewSource.includes('data-testid="source-expert-details"') &&
          dashboardCanvasSource.includes("onOpenBusinessStep: (step: BusinessPathStepKey) => void") &&
          dashboardCanvasSource.includes('testId="dashboard-product-activation"') &&
          !dashboardCanvasSource.includes('data-testid="dashboard-no-data-route"') &&
          evidenceViewSource.includes('data-testid="evidence-next-action"') &&
          !evidenceViewSource.includes("ProductActivationPanel") &&
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
          evidenceViewSource.includes('data-testid="evidence-open-sources"') &&
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
          developmentRoadmapDocSource.includes("## 先记住一条主流程") &&
          developmentRoadmapDocSource.includes("## 当前队列") &&
          !developmentRoadmapDocSource.includes("第二个独立业务领域验收") &&
          !developmentRoadmapDocSource.includes("### 2. 带证据导出") &&
          developmentRoadmapDocSource.includes("本地升级与回滚") &&
          developmentRoadmapDocSource.includes("整套行业看板 Beta 晋级条件") &&
          developmentRoadmapDocSource.includes("## 明确暂时不做") &&
          !developmentRoadmapDocSource.includes("已完成") &&
          !developmentRoadmapDocSource.includes("npm run"),
      },
    {
        label: "preflight-delegates-to-stable-verification-entrypoints",
        ok: packageJson.scripts?.preflight === "node scripts/preflight.mjs" &&
          preflightSource.includes('runNpmScript("production build and bundle budgets", "build")') &&
          preflightSource.includes('runNpmScript("core, CLI, and AI verification", "verify")') &&
          preflightSource.includes('runNpmScript("workspace landing flow", "verify:workspace-flow")') &&
          preflightSource.includes('runNpmScript("complete UI verification", "verify:ui")') &&
          !preflightSource.includes("node_modules/typescript") &&
          !preflightSource.includes("scripts/verify-ui-flow.mjs"),
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
        ok: appSource.includes("readNavigationTarget(window.location.search)") &&
          appSource.includes("window.addEventListener(\"popstate\", handlePopState)") &&
          appSectionsSource.includes("export function isAppSection") &&
          appNavigationModelSource.includes("export function readNavigationTarget") &&
          appNavigationModelSource.includes("isAppSection(sectionParam) ? sectionParam : \"home\"") &&
          appNavigationModelSource.includes("export function writeNavigationUrl") &&
          appNavigationModelSource.includes('tableKey: "table"') &&
          appNavigationModelSource.includes('dashboardKey: "dashboard"') &&
          appNavigationModelSource.includes('viewKey: "view"') &&
          appSource.includes('from "./appWorkspaceModel"') &&
          appWorkspaceModelSource.includes("export function preferredLandingSection") &&
          appWorkspaceModelSource.includes("if (hasDashboard) return \"dashboards\"") &&
          appWorkspaceModelSource.includes("if (hasSource) return \"sources\"") &&
          appSource.includes("explicitInitialSectionRef") &&
          appSource.includes("autoLandingAppliedRef") &&
          appSource.includes('import { refreshStatusDashboardsWorkbenchDrafts } from "./appRefreshModel"') &&
          appRefreshModelSource.includes("export async function refreshStatusDashboardsWorkbenchDrafts") &&
          appSource.includes("setSection(preferredLandingSection(surface.status, surface.workbench, surface.dashboards, surface.actionDrafts.length))") &&
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
          appSource.includes("navigateTo,") &&
          appAgentActionsSource.includes("export function useAppAgentActions(") &&
          appAgentActionsSource.includes("type AppAgentActionsOptions") &&
          appAgentActionsSource.includes("const handleAsk = useCallback") &&
          appAgentActionsSource.includes("const handleAskReadOnly = useCallback") &&
          appAgentActionsSource.includes("const handleConfirmAction = useCallback") &&
          appAgentActionsSource.includes("const handleRejectAction = useCallback") &&
          appAgentActionsSource.includes("confirmAction(actionKey, true, true, activeWorkspaceId)") &&
          appAgentActionsSource.includes("nextAgent.workspaceId !== activeWorkspaceId") &&
          appAgentActionsSource.includes("result.workspaceId !== activeWorkspaceId") &&
          appAgentActionsSource.includes('section: "dashboards"') &&
          appAgentActionsSource.includes('section: "agent"') &&
          appAgentActionsSource.includes("actionKey: nextAgent.actionDraft?.actionKey") &&
          appAgentActionsSource.includes("dashboardKey: typeof result.createdDashboardKey") &&
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
          !biCliRuntimeSource.includes(retiredSeedEnvName) &&
          !verifySource.includes(retiredSeedEnvName) &&
          !verifyBiCliAgentContractSource.includes(retiredSeedEnvName) &&
          !existsSync(join(root, "tools", "seed_orchestration_service.py")) &&
          !existsSync(join(root, "tools", "seed_default_objects_service.py")) &&
          emptyWorkspaceDataSource.includes("export const emptyWorkspaceStatus") &&
          !("verify:a-testdata" in packageJson.scripts) &&
          !existsSync(join(root, "scripts", "verify-a-testdata-source-intelligence.mjs")) &&
          !biCliRuntimeSource.includes("A_TESTDATA_03_05_DIRS") &&
          !biCliRuntimeSource.includes("--a-testdata-03-05") &&
          /elif op == "create":\s*resolved_table_key = ""/.test(biCliRuntimeSource) &&
          biCliRuntimeSource.includes('table_key = str(proposed.get("defaultTableKey") or "")') &&
          biCliRuntimeSource.includes('layout = {"version": 1, "grid": "12-col", "widgets": [], "globalFilters": []}') &&
          !biCliRuntimeSource.includes('("bar", "渠道净销售"') &&
          !biCliRuntimeSource.includes('("table", "订单明细"') &&
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
          appWorkspaceActionsSource.includes("deleteWorkspace(workspaceId, confirm)") &&
          appWorkspaceActionsSource.includes("renameWorkspace(workspaceId, nextName, false)") &&
          appWorkspaceActionsSource.includes("const handleWorkspaceDelete = useCallback") &&
          appWorkspaceActionsSource.includes("reloadWorkspaceSurface"),
      },
    {
        label: "sidebar-workspace-card-component-boundary",
        ok: existsSync(join(root, "src", "components", "SidebarWorkspaceCard.tsx")) &&
          sidebarSource.includes('const SidebarWorkspaceCard = lazy(() => import("./SidebarWorkspaceCard"))') &&
          sidebarSource.includes("<SidebarWorkspaceCard") &&
          !sidebarSource.includes('data-testid="workspace-switcher"') &&
          sidebarWorkspaceCardSource.includes("type SidebarWorkspaceCardProps") &&
          sidebarWorkspaceCardSource.includes("createWorkspaceFromInput: () => Promise<Record<string, unknown> | void>") &&
          sidebarWorkspaceCardSource.includes("selectWorkspaceFromInput: (workspaceId: string) => Promise<void>") &&
          sidebarWorkspaceCardSource.includes("deleteWorkspaceFromInput: (workspaceId: string, confirm?: boolean)") &&
          sidebarWorkspaceCardSource.includes('data-testid="workspace-delete-list"') &&
          sidebarWorkspaceCardSource.includes("deletableWorkspaces") &&
          !sidebarWorkspaceCardSource.includes("window.confirm") &&
          sidebarWorkspaceCardSource.includes('data-testid="workspace-delete-preview"') &&
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
        label: "ui-flow-visible-production-state-boundary",
        ok: verifyUiFlowSource.includes("const isVisible = (element)") &&
          verifyUiFlowSource.includes('element.closest("details:not([open])")') &&
          verifyUiFlowSource.includes('visibleCount(\'[data-testid="source-coverage-item"]\')') &&
          verifyUiFlowSource.includes('visible("source-next-dashboard") || visible("source-dashboard-next-action")') &&
          verifyUiFlowSource.includes("const dashboardList = Array.isArray(dashboards.dashboards)") &&
          verifyUiFlowSource.includes("Array.isArray(dashboards.dashboards) && dashboardCount >= 0"),
      },
    {
        label: "sidebar-asset-sections-component-boundary",
        ok: existsSync(join(root, "src", "components", "SidebarAssetSections.tsx")) &&
          sidebarSource.includes('from "../sidebarAssetModules"') &&
          sidebarAssetModulesSource.includes("export const SidebarAssetSections = lazy") &&
          sidebarSource.includes("<SidebarAssetSections") &&
          sidebarSource.includes("assetSectionsMounted ? <Suspense") &&
          !sidebarSource.includes('aria-labelledby="source-assets-title"') &&
          !sidebarSource.includes('aria-labelledby="dashboard-assets-title"') &&
          sidebarAssetSectionsSource.includes("type SidebarAssetSectionsProps") &&
          sidebarAssetSectionsSource.includes('aria-labelledby="source-assets-title"') &&
          sidebarAssetSectionsSource.includes('aria-labelledby="dashboard-assets-title"') &&
          sidebarAssetSectionsSource.includes('aria-labelledby="agent-assets-title"') &&
          sidebarAssetSectionsSource.includes('aria-labelledby="evidence-assets-title"') &&
          sidebarAssetSectionsSource.includes("全局提问与确认") &&
          sidebarAssetSectionsSource.includes("右下角都可以直接提问") &&
          !sidebarAssetSectionsSource.includes('aria-labelledby="start-assets-title"') &&
          !sidebarAssetSectionsSource.includes("可执行指标") &&
          !sidebarAssetSectionsSource.includes("homeNextSection") &&
          !sidebarAssetSectionsSource.includes("primaryAssetRow") &&
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
          appNavigationModelSource.includes("isAppSection(sectionParam) ? sectionParam : \"home\""),
      },
    {
        label: "frontend-desktop-shell-fluid-width",
        ok: stylesSource.includes("--shell-asset-width: clamp(280px, 17vw, 324px)") &&
          stylesSource.includes("--shell-inspector-width: clamp(300px, 18vw, 340px)") &&
          stylesSource.includes("grid-template-columns: var(--shell-rail-width) var(--shell-asset-width) minmax(0, 1fr) var(--shell-inspector-width)") &&
          stylesSource.includes("grid-template-columns: var(--shell-rail-width) var(--shell-asset-width) minmax(0, 1fr) var(--shell-inspector-collapsed-width)") &&
          stylesSource.includes("@media (min-width: 761px) and (max-width: 1040px)") &&
          stylesSource.includes("grid-template-columns: var(--shell-rail-width) minmax(0, 1fr) var(--shell-inspector-collapsed-width)") &&
          stylesSource.includes("grid-column: 2;") &&
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
        ok: biCliRuntimeSource.includes("def quality_doctor_command(") &&
          biCliRuntimeSource.includes("def metric_sql_doctor_from_run(") &&
          biCliRuntimeSource.includes("metric-sql-compiler.json") &&
          biCliRuntimeSource.includes("metric-query-results.json") &&
          biCliRuntimeSource.includes('sub.add_parser("quality-doctor")') &&
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
