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
    preflightLifecycleSource,
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
        ok: (homeOverviewSource.match(/data-testid="workspace-primary-task"/g) ?? []).length === 1 &&
          homeOverviewSource.includes("const currentStep = !hasData ? 0 : !hasCurrentEvidence ? 1 : hasPendingDraft ? 3 : 2") &&
          homeOverviewSource.includes('className="workspaceTaskEmpty"') &&
          homeOverviewSource.includes('className="workspaceQuestionTask"') &&
          homeOverviewSource.includes("async function generateEvidence()") &&
          homeOverviewSource.includes("async function submitQuestion(event: FormEvent<HTMLFormElement>)") &&
          homeOverviewSource.includes('onOpenSection("agent")') &&
          homeOverviewSource.includes('className="workspaceSecondaryActions"') &&
          !homeOverviewSource.includes("ProductActivationPanel") &&
          !homeOverviewSource.includes("HomeActionDock") &&
          !homeOverviewSource.includes("HomeOperatingSummaryPanel") &&
          !homeOverviewSource.includes("HomeDetailedPathPanel") &&
          !homeOverviewSource.includes('data-testid="home-action-dock"'),
      },
    {
        label: "frontend-no-data-onboarding-ux-boundary",
        ok: homeOverviewSource.includes("const hasData = status.counts.tables > 0 || workbench.tables.length > 0") &&
          homeOverviewSource.includes("{!hasData ? (") &&
          homeOverviewSource.includes("先接入一份真实数据") &&
          homeOverviewSource.includes("系统会先预检，不会直接写入") &&
          homeOverviewSource.includes('onClick={() => onOpenSection("sources")}') &&
          homeOverviewSource.includes(") : !hasCurrentEvidence ? (") &&
          homeOverviewSource.includes("生成证据摘要，再开始提问") &&
          homeOverviewSource.includes('disabled={busy === "profile"}') &&
          workspaceFlowModelSource.includes("export function buildWorkspaceFlow") &&
          workspaceFlowModelSource.includes("export function resolveSectionForFlow") &&
          appSource.includes("const workspaceFlow = useMemo(() => buildWorkspaceFlow") &&
          appSource.includes("resolveSectionForFlow(section, workspaceFlow)") &&
          sidebarSource.includes("isSectionLockedByFlow") &&
          sourceWorkbenchStateSource.includes("const hasData = tables.length > 0 || status.counts.tables > 0") &&
          sourceWorkbenchStateSource.includes("const showExpertWorkbench = showAdvanced") &&
          sourceWorkbenchStateSource.includes("if (!focusedTableKey || !tableKeySet.has(focusedTableKey)) return") &&
          sourceWorkbenchActionPanelSource.includes('data-testid="source-expert-toggle"') &&
          agentPanelSource.includes("onOpenSources: () => void") &&
          agentPanelSource.includes('data-testid="agent-no-data-route"') &&
          settingsPanelSource.includes('data-testid="settings-sandbox-details"') &&
          settingsPanelSource.includes('data-testid="settings-config-portability-details"') &&
          !settingsPanelSource.includes('data-testid="settings-acceptance-details"') &&
          !appSource.includes("<BusinessPathBar") &&
          !appSource.includes("<AgentCommandDock") &&
          !homeOverviewSource.includes("ProductActivationPanel"),
      },
    {
        label: "product-ux-acceptance-documentation-boundary",
        ok: productUxStandardDocSource.includes("## 首次成功流程") &&
          productUxStandardDocSource.includes("## 对象归属与路由") &&
          productUxStandardDocSource.includes("## 确认与删除") &&
          productUxStandardDocSource.includes("product-acceptance-matrix.md") &&
          productAcceptanceMatrixDocSource.includes("空工作区") &&
          productAcceptanceMatrixDocSource.includes("创建单图") &&
          productAcceptanceMatrixDocSource.includes("删除来源或对象") &&
          productAcceptanceMatrixDocSource.includes("生产无演示数据") &&
          productAcceptanceMatrixDocSource.includes("validation-inputs") &&
          docsReadmeSource.includes("product-acceptance-matrix.md") &&
          prdDocSource.includes("## 需求事实归属") &&
          !prdDocSource.includes("source-intelligence fixtures") &&
          implementationStatusSource.includes("“工作区”只显示当前必要任务"),
      },
    {
        label: "frontend-production-copy-and-current-roadmap-contract",
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
          developmentRoadmapDocSource.includes("## 不变的主流程") &&
          developmentRoadmapDocSource.includes("## 当前队列") &&
          !developmentRoadmapDocSource.includes("第二个独立业务领域验收") &&
          !developmentRoadmapDocSource.includes("### 2. 带证据导出") &&
          implementationStatusSource.includes("| Analysis Unit 与图表适配 | 稳定初版 |") &&
          implementationStatusSource.includes("| Connector Adapter | 稳定受控 |") &&
          !developmentRoadmapDocSource.includes("### 1. 可验证 Analysis Unit 与 Chart Adapter") &&
          !developmentRoadmapDocSource.includes("Query Receipt 驱动的 Excel/报告导出") &&
          !developmentRoadmapDocSource.includes("P0-D：确定性 Plan Quality Scorecard") &&
          !developmentRoadmapDocSource.includes("P0-C：证据绑定的混合语义召回") &&
          !developmentRoadmapDocSource.includes("P1-A：") &&
          implementationStatusSource.includes("| 探索线程与结果板 | 稳定初版 |") &&
          !developmentRoadmapDocSource.includes("P1-B：第二批通用分析 Skills") &&
          developmentRoadmapDocSource.includes("P1-C：有限 Research Run") &&
          developmentRoadmapDocSource.includes("P2：只在本地可信边界内增加 forecast readiness") &&
          !developmentRoadmapDocSource.includes("当前没有已批准但尚未交付的主项") &&
          !developmentRoadmapDocSource.includes("| P1 | 业务理解与首批 Skills |") &&
          implementationStatusSource.includes("| 业务理解与分析 Skills | 稳定初版 |") &&
          implementationStatusSource.includes("aibi-analysis-method-plan/v1") &&
          implementationStatusSource.includes("| 计划质量评测 | 稳定初版 |") &&
          developmentRoadmapDocSource.includes("## 暂不开发") &&
          !developmentRoadmapDocSource.includes("npm run preflight"),
      },
    {
        label: "preflight-delegates-to-stable-verification-entrypoints",
        ok: packageJson.scripts?.preflight === "node scripts/preflight.mjs" &&
          preflightSource.includes("runPreflightLifecycle({") &&
          preflightLifecycleSource.includes('["production build and bundle budgets", "build"]') &&
          preflightLifecycleSource.includes('["core, CLI, and AI verification", "verify"]') &&
          preflightLifecycleSource.includes('["workspace landing flow", "verify:workspace-flow"]') &&
          preflightLifecycleSource.includes('runNpmScript("complete UI verification", "verify:ui")') &&
          !preflightSource.includes("node_modules/typescript") &&
          !preflightSource.includes("scripts/verify-ui-flow.mjs") &&
          !preflightLifecycleSource.includes("scripts/verify-ui-flow.mjs"),
      },
    {
        label: "home-detailed-path-panel-boundary",
        ok: !homeOverviewSource.includes('import { HomeDetailedPathPanel } from "./HomeDetailedPathPanel"') &&
          !homeOverviewSource.includes("<HomeDetailedPathPanel") &&
          !homeOverviewSource.includes("runDashboardTemplate") &&
          homeOverviewSource.includes('className="workspaceSecondaryActions"') &&
          homeOverviewSource.includes("<details>") &&
          homeOverviewSource.includes("高级工具") &&
          homeOverviewSource.includes('onOpenSection("views")') &&
          homeOverviewSource.includes('onOpenSection("settings")'),
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
          appWorkspaceModelSource.includes('if (resolvedPendingDraftCount > 0) return "agent"') &&
          appWorkspaceModelSource.includes('return "home"') &&
          !appWorkspaceModelSource.includes('return "dashboards"') &&
          !appWorkspaceModelSource.includes('return "sources"') &&
          appSource.includes("explicitInitialSectionRef") &&
          appSource.includes("autoLandingAppliedRef") &&
          appSource.includes('import { refreshStatusDashboardsWorkbenchDrafts } from "./appRefreshModel"') &&
          appRefreshModelSource.includes("export async function refreshStatusDashboardsWorkbenchDrafts") &&
          appSource.includes("setSection(preferredLandingSection(surface.status, surface.workbench, surface.dashboards, surface.actionDrafts.length))") &&
          appNavigationModelSource.includes('if (section === "home" || section === "settings") return {}') &&
          appSource.includes("navigationContextForSection(resolvedSection, mergedContext)") &&
          appSource.includes("navigationContextForSection(section, {") &&
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
          appAgentActionsSource.includes('from "./agentActionNavigationModel"') &&
          appAgentActionsSource.includes("const target = confirmedActionNavigationTarget(actionKey, result, draft)") &&
          appAgentActionsSource.includes("navigateTo(target)") &&
          appAgentActionsSource.includes('section: "agent"') &&
          appAgentActionsSource.includes("actionKey: nextAgent.actionDraft?.actionKey") &&
          !appAgentActionsSource.includes("dashboardKey: typeof result.createdDashboardKey") &&
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
          productUxStandardDocSource.includes("创建空看板只创建看板容器") &&
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
        ok: sidebarSource.includes('id="workspace-switcher"') &&
          sidebarSource.includes('aria-label={biText("选择工作区", "Select workspace")}') &&
          sidebarSource.includes("workspaces.map((workspace) =>") &&
          sidebarSource.includes("onWorkspaceCreate") &&
          sidebarSource.includes("onWorkspaceSelect") &&
          sidebarSource.includes("onWorkspaceDelete") &&
          sidebarSource.includes("onWorkspaceRename") &&
          sidebarSource.includes('className="sidebarWorkspaceManager"') &&
          sidebarSource.includes("async function createWorkspace()") &&
          sidebarSource.includes("async function renameWorkspace()") &&
          sidebarSource.includes("async function previewWorkspaceDelete()") &&
          sidebarSource.includes("async function confirmWorkspaceDelete()") &&
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
        ok: !sidebarSource.includes("SidebarWorkspaceCard") &&
          !sidebarSource.includes('import("./SidebarWorkspaceCard")') &&
          sidebarSource.includes('className="sidebarWorkspaceControl"') &&
          sidebarSource.includes('id="workspace-switcher"') &&
          sidebarSource.includes('<details className="sidebarWorkspaceManager">') &&
          sidebarSource.includes('className="sidebarWorkspaceManagerBody"') &&
          sidebarSource.includes('className="sidebarDeletePreview"') &&
          sidebarSource.includes("deletePreview.requiresConfirmation !== true") &&
          !sidebarSource.includes("window.confirm"),
      },
    {
        label: "ui-flow-visible-production-state-boundary",
        ok: verifyUiFlowSource.includes("const isVisible = (element)") &&
          verifyUiFlowSource.includes('element.closest("details:not([open])")') &&
          verifyUiFlowSource.includes('visibleCount(\'[data-testid="source-coverage-item"]\')') &&
          verifyUiFlowSource.includes('visible("source-next-analysis") || visible("beginner-plan-refresh-profile")') &&
          verifyUiFlowSource.includes("const dashboardList = Array.isArray(dashboards.dashboards)") &&
          verifyUiFlowSource.includes("Array.isArray(dashboards.dashboards) && dashboardCount >= 0"),
      },
    {
        label: "sidebar-asset-sections-component-boundary",
        ok: !sidebarSource.includes('from "../sidebarAssetModules"') &&
          !sidebarSource.includes("SidebarAssetSections") &&
          !sidebarSource.includes("assetSectionsMounted") &&
          sidebarSource.includes('className="workspaceNav"') &&
          sidebarSource.includes("primarySections.map((sectionKey) =>") &&
          sidebarSource.includes('className="sidebarAdvancedNav"') &&
          sidebarSource.includes('activeSection === "views"') &&
          sidebarSource.includes('className="sidebarFooter"') &&
          !sidebarSource.includes("source-assets-title") &&
          !sidebarSource.includes("dashboard-assets-title"),
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
          appSectionsSource.includes('zh: "工作区"') &&
          appSectionsSource.includes('zh: "数据"') &&
          appSectionsSource.includes('zh: "分析"') &&
          appSectionsSource.includes('zh: "看板"') &&
          sidebarSource.includes('const primarySections: AppSection[] = ["home", "sources", "agent", "dashboards", "evidence"]') &&
          sidebarSource.includes('className="sidebarAdvancedNav"') &&
          sidebarSource.includes('activeSection === "views"') &&
          topBarSource.includes("getAppSection(activeSection)") &&
          appLazyModulesSource.includes("getAppSection(section)") &&
          appNavigationModelSource.includes("isAppSection(sectionParam) ? sectionParam : \"home\"") &&
          appNavigationModelSource.includes('if (section === "home" || section === "settings") return {}'),
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
        ok: homeOverviewSource.includes("const hasPendingDraft = agent.requiresConfirmation === true || (status.counts.actionDrafts ?? 0) > 0") &&
          homeOverviewSource.includes(") : hasPendingDraft ? (") &&
          homeOverviewSource.includes('data-testid="workspace-review-draft"') &&
          homeOverviewSource.includes("核对等待确认的修改") &&
          homeOverviewSource.indexOf('data-testid="workspace-review-draft"') < homeOverviewSource.indexOf('data-testid="workspace-question-form"') &&
          homeOverviewSource.includes('onClick={() => onOpenSection("agent")}'),
      },
    {
        label: "frontend-home-dashboard-preview-visible",
        ok: !homeOverviewSource.includes("const [dashboardPlan, setDashboardPlan]") &&
          !homeOverviewSource.includes("runDashboardTemplate") &&
          !homeOverviewSource.includes("runBusinessDashboardOperation") &&
          homeOverviewSource.includes("const hasDashboard = status.counts.dashboards > 0") &&
          homeOverviewSource.includes('{hasDashboard && hasCurrentEvidence ? <button data-testid="workspace-open-board"') &&
          homeOverviewSource.includes('onClick={() => onOpenSection("dashboards")}') &&
          homeOverviewSource.includes("打开最近看板"),
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
        ok: !homeOverviewSource.includes("buildScenarioPacks") &&
          !homeOverviewSource.includes("buildDataQualityDoctor") &&
          !homeOverviewSource.includes("buildSandboxComparison") &&
          !homeOverviewSource.includes("buildMetricRepairPlan") &&
          !homeOverviewSource.includes("HomeScenarioPacksPanel") &&
          !homeOverviewSource.includes("HomeProductIntelligencePanel") &&
          !homeOverviewSource.includes("useQualityDoctor") &&
          !homeOverviewSource.includes("runScenarioPrompt") &&
          !homeOverviewSource.includes("previewScenarioTemplate") &&
          sourceWorkbenchActionPanelSource.includes('data-testid="source-expert-toggle"') &&
          sourceWorkbenchActionPanelSource.includes("数据模型与管理") &&
          settingsPanelSource.includes('data-testid="settings-sandbox-details"'),
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
          metricRepairModelSource.includes("const coreSemanticAliases") &&
          metricRepairModelSource.includes("SemanticBindingDraft") &&
          metricRepairModelSource.includes("EvidenceGapItem") &&
          metricRepairModelSource.includes("rerunInputs") &&
          metricRepairModelSource.includes("benefitSummary") &&
          metricRepairModelSource.includes("manifestInputRoots") &&
          metricRepairModelSource.includes("knownSemanticIds") &&
          metricRepairModelSource.includes("enabledManifestContributions") &&
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
          (
            byLabel["cli-quality-doctor"].parsed?.latestSourceIntelligenceRun === null
              ? byLabel["cli-quality-doctor"].parsed?.metricSql?.planned === 0 &&
                byLabel["cli-quality-doctor"].parsed?.metricSql?.executable === 0
              : Array.isArray(byLabel["cli-quality-doctor"].parsed?.latestSourceIntelligenceRun?.inputRoots) &&
                Array.isArray(byLabel["cli-quality-doctor"].parsed?.metricSql?.missingSemantics) &&
                Array.isArray(byLabel["cli-quality-doctor"].parsed?.metricSql?.failedSamples) &&
                Array.isArray(byLabel["cli-quality-doctor"].parsed?.metricSql?.semanticBindingDrafts) &&
                byLabel["cli-quality-doctor"].parsed?.metricSql?.repairDraft?.kind === "metric-sql.repair" &&
                Array.isArray(byLabel["cli-quality-doctor"].parsed?.metricSql?.repairDraft?.semanticBindingDrafts)
          ),
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
