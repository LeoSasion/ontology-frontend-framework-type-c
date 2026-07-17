export function appendProductUxContractChecks(context) {
  const {
    checks,
    actionRecoveryModelSource,
    agentAnswerCardSource,
    agentCanAnswerPanelSource,
    agentContextPlanPanelSource,
    agentEvidenceAuditPanelsSource,
    agentPanelModelSource,
    agentPanelSource,
    agentPendingChangesPanelSource,
    agentPromptComposerSource,
    agentTaskPacketSource,
    appChromeStylesSource,
    appLazyModulesSource,
    appAgentActionsSource,
    appDataActionsSource,
    appSource: appEntrySource,
    appMainViewSource,
    appRefreshModelSource,
    appWorkspaceModelSource,
    biCliSource,
    bWidgetKitModelSource,
    bWidgetKitOverviewSource,
    bWidgetKitSource,
    byLabel,
    dashboardBeginnerEditorSource,
    dashboardCanvasEditorOptionsSource,
    dashboardCanvasReadinessModelSource,
    dashboardCanvasSource,
    dashboardOverviewStripSource,
    evidenceNumberExplainerPanelSource,
    evidenceViewModelSource,
    evidenceViewSource,
    existsSync,
    globalStylesSource,
    homeOverviewSource,
    implementationStatusSource,
    join,
    metricSemanticRepairActionsSource,
    packageJson,
    readmeSource,
    root,
    settingsConfigPortabilityPanelSource,
    settingsPanelSource,
    settingsPanelStylesSource,
    settingsSandboxBoundaryPanelSource,
    settingsThemePreferencePanelSource,
    sourceIntelligenceRunModelSource,
    sourceWorkbenchDeferredModulesSource,
    sourceWorkbenchViewSource,
    sourceWorkbenchActionPanelSource,
    stylesSource,
    typesAgentSource,
  } = context;
  const appSource = `${appEntrySource}\n${appMainViewSource}`;
  checks.push(
    {
        label: "agent-business-surface-hides-technical-identifiers-and-raw-floats",
        ok: agentAnswerCardSource.includes("formatBusinessValue(metric.value)") &&
          agentAnswerCardSource.includes("formatBusinessValue(row.value)") &&
          !agentAnswerCardSource.includes('String(row.value ?? "-")') &&
          agentPanelSource.includes("businessIdentifier(sourceRunRef?.name") &&
          agentPanelSource.includes("businessPromptText(resultRequest, workbench)") &&
          agentPanelModelSource.includes('value === "query-runtime"') &&
          agentPendingChangesPanelSource.includes("resolveDraftTarget(currentDraft)") &&
          agentPanelModelSource.includes('value === "chart_preview"') &&
          evidenceViewModelSource.includes("businessIdentifier(ref.id") &&
          evidenceViewSource.includes("可直接回答（共识别"),
      },
    {
        label: "workspace-refresh-publishes-only-consistent-surfaces",
        ok: appRefreshModelSource.includes("function workspaceSurfaceIsConsistent") &&
          appRefreshModelSource.includes("async function readConsistentWorkspaceSurface") &&
          appRefreshModelSource.includes("status.counts.tables === workbench.tables.length") &&
          appRefreshModelSource.includes("throw new Error(\"Workspace data is still synchronizing"),
      },
    {
        label: "agent-first-screen-keeps-one-visible-approval-path",
        ok: agentPanelSource.indexOf("<AgentPendingChangesPanel") > -1 &&
          agentPanelSource.indexOf("<AgentPendingChangesPanel") < agentPanelSource.indexOf('data-testid="agent-trust-analysis-details"') &&
          !agentPanelSource.includes('data-testid="agent-task-packet-details" open={pendingDrafts.length > 0}') &&
          agentPendingChangesPanelSource.includes('data-testid="agent-current-draft-confirm"') &&
          agentPendingChangesPanelSource.includes('data-testid="agent-current-draft-summary"') &&
          agentPendingChangesPanelSource.includes("agentDraftStickyActions") &&
          agentTaskPacketSource.includes("agentTaskPacketTechnical"),
      },
    {
        label: "responsive-shell-uses-current-two-column-layout",
        ok: appChromeStylesSource.includes("@media (max-width: 980px)") &&
          appChromeStylesSource.includes("grid-template-columns: 212px minmax(0, 1fr)") &&
          appChromeStylesSource.includes("@media (max-width: 720px)") &&
          appChromeStylesSource.includes("grid-template-columns: minmax(0, 1fr)") &&
          appChromeStylesSource.includes(".workspaceSidebar"),
      },
    {
        label: "deferred-ui-recovers-without-global-page-failure",
        ok: appLazyModulesSource.includes("lazyWithRetry") &&
          sourceWorkbenchDeferredModulesSource.includes("lazyWithRetry") &&
          !sourceWorkbenchDeferredModulesSource.includes("loadDataEntryPanel") &&
          sourceWorkbenchViewSource.includes('import { SourceWorkbenchDataEntryPanel } from "./SourceWorkbenchDataEntryPanel"'),
      },
    {
        label: "frontend-inspector-selected-context",
        ok: !appEntrySource.includes("<InspectorPanel") &&
          !appEntrySource.includes("<InspectorContextPanel") &&
          appEntrySource.includes("const [navigationContext, setNavigationContext]") &&
          appEntrySource.includes("navigationContextForSection(resolvedSection, mergedContext)") &&
          appEntrySource.includes("setNavigationContext(navigationContextFromTarget(resolvedTarget))") &&
          appSource.includes("evidenceFocus={evidenceFocus}") &&
          appSource.includes("focusedTableKey={focusedTable?.table_key") &&
          appSource.includes("activeDashboardKey={activeDashboardKey}") &&
          appSource.includes("activeViewKey={activeViewKey}") &&
          appEntrySource.includes("const handleOpenEvidence = useCallback") &&
          appEntrySource.includes('section: "evidence"') &&
          appMainViewSource.includes("onOpenEvidence={onOpenEvidence}") &&
          appMainViewSource.includes('navigateTo({ section: "agent", tableKey: evidenceFocus?.tableKey'),
      },
    {
        label: "frontend-collapsible-inspector",
        ok: !appEntrySource.includes("useInspectorController") &&
          !appEntrySource.includes("<InspectorPanel") &&
          !appEntrySource.includes("data-inspector-state") &&
          !appEntrySource.includes("onCollapseInspector") &&
          !appEntrySource.includes("onExpandInspector") &&
          !appLazyModulesSource.includes("loadInspectorPanel") &&
          !appLazyModulesSource.includes("inspectorPreloader") &&
          appEntrySource.includes('<main className="contentShell">') &&
          appEntrySource.includes("<AppMainView"),
      },
    {
        label: "frontend-inspector-friendly-action-error",
        ok: !appEntrySource.includes("<InspectorPanel") &&
          actionRecoveryModelSource.includes("export function buildActionRecovery") &&
          actionRecoveryModelSource.includes("query-table") &&
          actionRecoveryModelSource.includes("dashboard-recovery") &&
          actionRecoveryModelSource.includes("source-recovery") &&
          actionRecoveryModelSource.includes("export function actionRecoveryFromError") &&
          appWorkspaceModelSource.includes('import { actionRecoveryFromError, buildActionRecovery } from "./actionRecoveryModel"') &&
          appWorkspaceModelSource.includes("actionRecoveryFromError(error) ?? buildActionRecovery(action, error)") &&
          appWorkspaceModelSource.includes("targetSection: recovery.targetSection") &&
          appWorkspaceModelSource.includes("recovery,") &&
          agentPanelSource.includes("lastActionResult: Record<string, unknown> | null") &&
          agentPanelSource.includes("const activeActionResult =") &&
          agentPendingChangesPanelSource.includes("actionResultHeadline(activeActionResult)") &&
          agentPendingChangesPanelSource.includes("actionResultDetail(activeActionResult, currentDraft)") &&
          agentPendingChangesPanelSource.includes('data-testid="agent-action-result"') &&
          agentPendingChangesPanelSource.includes('<details className="advancedDetails compactAdvanced agentActionTechnical"') &&
          appDataActionsSource.includes('action: "source-intelligence"') &&
          appDataActionsSource.includes("throw error"),
      },
    {
        label: "frontend-evidence-number-explainer",
        ok: evidenceViewSource.includes("buildEvidenceNarrative(focus, agent, workbench)") &&
          evidenceViewSource.includes("<EvidenceNumberExplainerPanel") &&
          evidenceNumberExplainerPanelSource.includes('data-testid="evidence-number-explainer"') &&
          evidenceNumberExplainerPanelSource.includes('data-testid="evidence-calculation-steps"') &&
          evidenceNumberExplainerPanelSource.includes('data-testid="evidence-trust-checks"') &&
          evidenceNumberExplainerPanelSource.includes("数字说明书") &&
          stylesSource.includes(".evidenceNarrativeCard") &&
          stylesSource.includes(".evidenceNarrativeSteps") &&
          stylesSource.includes(".evidenceTrustChecks"),
      },
    {
        label: "evidence-number-explainer-panel-component-boundary",
        ok: existsSync(join(root, "src", "components", "EvidenceNumberExplainerPanel.tsx")) &&
          evidenceViewSource.includes('const EvidenceNumberExplainerPanel = lazyWithRetry(() => import("./EvidenceNumberExplainerPanel")') &&
          evidenceViewSource.includes("<EvidenceNumberExplainerPanel") &&
          !evidenceViewSource.includes('data-testid="evidence-number-explainer"') &&
          evidenceNumberExplainerPanelSource.includes('import type { EvidenceNarrative } from "../productIntelligenceModel"') &&
          evidenceNumberExplainerPanelSource.includes("type EvidenceNumberExplainerPanelProps") &&
          !evidenceNumberExplainerPanelSource.includes("type EvidenceNarrativeStep") &&
          !evidenceNumberExplainerPanelSource.includes("type EvidenceNarrative =") &&
          evidenceNumberExplainerPanelSource.includes("evidenceNarrative.calculationSteps.map"),
      },
    {
        label: "frontend-agent-dock-beginner-task-entry",
        ok: !appSource.includes("<AgentCommandDock") &&
          !appLazyModulesSource.includes("loadAgentCommandDock") &&
          !appLazyModulesSource.includes("agentDockPreloader") &&
          appEntrySource.includes('onOpenAgent={() => openSection("agent")}') &&
          appMainViewSource.includes('if (section === "agent")') &&
          appMainViewSource.includes("<AgentPanel") &&
          appMainViewSource.includes("onOpenSources={() => openSection(\"sources\")}") &&
          agentPanelSource.includes("<AgentPromptComposer") &&
          agentPanelSource.includes("<AgentPendingChangesPanel") &&
          appAgentActionsSource.includes("targetSection?: AppSection") &&
          appAgentActionsSource.includes("if (nextAgent?.requiresConfirmation)") &&
          appAgentActionsSource.includes('section: targetSection ?? "agent"') &&
          appAgentActionsSource.includes("tableKey: nextAgent?.matched.table?.table_key"),
      },
    {
        label: "frontend-dashboard-readiness-panel",
        ok: dashboardBeginnerEditorSource.includes("data-testid=\"dashboard-readiness-panel\"") &&
          dashboardBeginnerEditorSource.includes("data-testid=\"dashboard-readiness-facts\"") &&
          !dashboardBeginnerEditorSource.includes("data-testid=\"dashboard-readiness-agent\"") &&
          !dashboardBeginnerEditorSource.includes("data-testid=\"dashboard-readiness-recommend\"") &&
          !dashboardBeginnerEditorSource.includes("data-testid=\"dashboard-readiness-evidence\"") &&
          dashboardCanvasSource.includes("dashboardHealthTitle") &&
          dashboardCanvasSource.includes("dashboardHealthItems") &&
          dashboardCanvasReadinessModelSource.includes("Add evidence profiling") &&
          stylesSource.includes(".dashboardReadinessPanel") &&
          stylesSource.includes(".dashboardReadinessFacts") &&
          !stylesSource.includes(".dashboardReadinessActions"),
      },
    {
        label: "frontend-import-to-dashboard-wizard",
        ok: !sourceWorkbenchActionPanelSource.includes('data-testid="import-to-dashboard-wizard"') &&
          !sourceWorkbenchActionPanelSource.includes("这些文件是什么业务？") &&
          !sourceWorkbenchActionPanelSource.includes("证据摘要是否完整？") &&
          !sourceWorkbenchActionPanelSource.includes("source-agent-import-guide") &&
          sourceWorkbenchActionPanelSource.includes('data-testid="beginner-import-plan"') &&
          sourceWorkbenchActionPanelSource.includes('data-testid="beginner-plan-refresh-profile"') &&
          sourceWorkbenchActionPanelSource.includes('data-testid="beginner-evidence-guard"') &&
          sourceWorkbenchActionPanelSource.includes('data-testid="source-next-analysis"') &&
          sourceWorkbenchActionPanelSource.includes('<details className="sourceGuideDetails" data-testid="source-guide-details">') &&
          sourceWorkbenchActionPanelSource.includes("生成证据摘要后再进入分析与看板。") &&
          sourceWorkbenchActionPanelSource.includes("数据模型与管理"),
      },
    {
        label: "frontend-settings-sandbox-boundary",
        ok: settingsSandboxBoundaryPanelSource.includes("const settingsSandboxItems") &&
          settingsSandboxBoundaryPanelSource.includes("data-testid=\"settings-sandbox-boundary\"") &&
          settingsSandboxBoundaryPanelSource.includes("data-testid=\"settings-sandbox-grid\"") &&
          settingsSandboxBoundaryPanelSource.includes("data-testid={`settings-sandbox-${item.key}`}") &&
          settingsSandboxBoundaryPanelSource.includes("外部源目录只读") &&
          settingsSandboxBoundaryPanelSource.includes("业务数据不导出") &&
          settingsSandboxBoundaryPanelSource.includes("写入先预演，再确认") &&
          settingsSandboxBoundaryPanelSource.includes("手动资产默认受保护") &&
          settingsSandboxBoundaryPanelSource.includes("onRunConfigAction(\"validate-config\", onValidateConfig)") &&
          settingsSandboxBoundaryPanelSource.includes("onRunConfigAction(\"export-config\", onExportConfig)") &&
          stylesSource.includes(".settingsSandboxCard") &&
          stylesSource.includes(".settingsSandboxGrid") &&
          stylesSource.includes(".settingsSandboxBadge.warn"),
      },
    {
        label: "settings-sandbox-boundary-panel-component",
        ok: existsSync(join(root, "src", "components", "SettingsSandboxBoundaryPanel.tsx")) &&
          settingsPanelSource.includes('import { SettingsSandboxBoundaryPanel } from "./SettingsSandboxBoundaryPanel"') &&
          settingsPanelSource.includes("<SettingsSandboxBoundaryPanel") &&
          !settingsPanelSource.includes("const settingsSandboxItems") &&
          !settingsPanelSource.includes('data-testid="settings-sandbox-boundary"') &&
          settingsSandboxBoundaryPanelSource.includes("type SettingsSandboxBoundaryPanelProps") &&
          settingsSandboxBoundaryPanelSource.includes("draftPreferences: UserPreferencesConfig"),
      },
    {
        label: "settings-theme-preference-panel-component-boundary",
        ok: existsSync(join(root, "src", "components", "SettingsThemePreferencePanel.tsx")) &&
          settingsPanelSource.includes('import { SettingsThemePreferencePanel, ThemeSwatches } from "./SettingsThemePreferencePanel"') &&
          settingsPanelSource.includes("<SettingsThemePreferencePanel") &&
          settingsPanelSource.includes('import "./settingsPanel.css"') &&
          settingsPanelStylesSource.includes(".settingsPanel {") &&
          settingsPanelStylesSource.includes(".configRestoreForm {") &&
          !globalStylesSource.includes(".settingsPanel {") &&
          !settingsPanelSource.includes('className="themePaletteGrid"') &&
          !settingsPanelSource.includes('className="preferenceList"') &&
          settingsThemePreferencePanelSource.includes("type SettingsThemePreferencePanelProps") &&
          settingsThemePreferencePanelSource.includes("export function ThemeSwatches") &&
          settingsThemePreferencePanelSource.includes('data-testid="settings-theme-palette-panel"') &&
          settingsThemePreferencePanelSource.includes('data-testid="settings-preference-switch-panel"') &&
          settingsThemePreferencePanelSource.includes("onPreferenceToggle(row.key, event.target.checked)") &&
          settingsThemePreferencePanelSource.includes("themeIsSystem(theme)"),
      },
    {
        label: "frontend-settings-friendly-config-result",
        ok: settingsPanelSource.includes("import { SettingsConfigPortabilityPanel }") &&
          settingsPanelSource.includes("<SettingsConfigPortabilityPanel") &&
          settingsPanelSource.includes("onRunConfigAction={runConfigAction}") &&
          settingsConfigPortabilityPanelSource.includes("function configResultMessage") &&
          settingsConfigPortabilityPanelSource.includes("function friendlyConfigWarning") &&
          settingsConfigPortabilityPanelSource.includes("const configMigrationSteps") &&
          settingsConfigPortabilityPanelSource.includes("const configMigrationScopes") &&
          settingsConfigPortabilityPanelSource.includes("data-testid=\"settings-config-safety-plan\"") &&
          settingsConfigPortabilityPanelSource.includes("data-testid=\"settings-config-migration-steps\"") &&
          settingsConfigPortabilityPanelSource.includes("data-testid=\"settings-config-migration-scope\"") &&
          settingsConfigPortabilityPanelSource.includes("data-testid=\"settings-config-friendly-result\"") &&
          settingsConfigPortabilityPanelSource.includes("data-testid=\"settings-config-result-facts\"") &&
          settingsConfigPortabilityPanelSource.includes("data-testid=\"settings-config-result-technical\"") &&
          settingsConfigPortabilityPanelSource.includes("data-testid=\"settings-config-restore-guard\"") &&
          settingsConfigPortabilityPanelSource.includes("data-testid=\"settings-config-restore-actions\"") &&
          settingsConfigPortabilityPanelSource.includes("配置可以迁移，业务数据和密钥不跟着走") &&
          settingsConfigPortabilityPanelSource.includes("恢复配置时必须先预览影响") &&
          settingsConfigPortabilityPanelSource.includes("检查当前设置") &&
          settingsConfigPortabilityPanelSource.includes("备份工作区设置") &&
          settingsConfigPortabilityPanelSource.includes("检查恢复影响") &&
          settingsConfigPortabilityPanelSource.includes("可以继续使用，有待同步项") &&
          settingsConfigPortabilityPanelSource.includes("连接器 ${connectorMatch[1]} 还没有同步成数据表 ${connectorMatch[2]}") &&
          settingsConfigPortabilityPanelSource.includes("查看配置检查明细") &&
          !settingsConfigPortabilityPanelSource.includes("Dry-run restore") &&
          stylesSource.includes(".configSafetyPlan") &&
          stylesSource.includes(".configMigrationSteps") &&
          stylesSource.includes(".configMigrationScope") &&
          stylesSource.includes(".configResultHeader") &&
          stylesSource.includes(".configResultFacts") &&
          stylesSource.includes(".configResultDetails"),
      },
    {
        label: "settings-acceptance-evidence-panel-component-boundary",
        ok: !settingsPanelSource.includes('import { SettingsAcceptanceEvidencePanel } from "./SettingsAcceptanceEvidencePanel"') &&
          !settingsPanelSource.includes("<SettingsAcceptanceEvidencePanel") &&
          !settingsPanelSource.includes("const closureItems") &&
          !settingsPanelSource.includes('data-testid="settings-closure-workbench"') &&
          !settingsPanelSource.includes('className="settingsEvidenceList"') &&
          settingsPanelSource.includes("<SettingsSandboxBoundaryPanel") &&
          settingsPanelSource.includes("<SettingsConfigPortabilityPanel") &&
          settingsPanelSource.includes("<SettingsThemePreferencePanel"),
      },
    {
        label: "frontend-no-sample-debug-entry",
        ok: !existsSync(join(root, "src", "components", "HomeRealDataValidationPanel.tsx")) &&
          !homeOverviewSource.includes("runATestdataDebugChain") &&
          !homeOverviewSource.includes("HomeRealDataValidationPanel") &&
          !homeOverviewSource.includes("A testdata") &&
          !homeOverviewSource.includes("onSourceDashboardDraft({") &&
          !appDataActionsSource.includes("aTestdata0305") &&
          !sourceIntelligenceRunModelSource.includes("aTestdata0305") &&
          !metricSemanticRepairActionsSource.includes("debug sample") &&
          appDataActionsSource.includes("请先在数据源工作台选择本地文件或文件夹"),
      },
    {
        label: "frontend-b-widget-acceptance-gallery",
        ok: bWidgetKitOverviewSource.includes('from "../biDashboardWidgetKitModel"') &&
          bWidgetKitModelSource.includes("export const B_WIDGET_ACCEPTANCE_ITEMS") &&
          dashboardCanvasEditorOptionsSource.includes("export const dashboardAcceptanceItems") &&
          dashboardOverviewStripSource.includes('data-testid="dashboard-component-acceptance-strip"') &&
          dashboardOverviewStripSource.includes('data-testid="dashboard-component-acceptance-items"') &&
          dashboardOverviewStripSource.includes("data-testid={`dashboard-component-acceptance-${item.key}`}") &&
          dashboardOverviewStripSource.includes("dashboardComponentAcceptanceDetails") &&
          dashboardOverviewStripSource.includes("expand when needed") &&
          stylesSource.includes(".dashboardComponentAcceptanceStrip.compactAcceptance") &&
          stylesSource.includes(".dashboardComponentAcceptanceDetails summary") &&
          stylesSource.includes(".dashboardComponentAcceptanceDetails:not([open]) .dashboardComponentAcceptanceItems") &&
          bWidgetKitSource.includes("<BiDashboardWidgetKitOverview") &&
          bWidgetKitOverviewSource.includes('data-testid="b-widget-acceptance-gallery"') &&
          bWidgetKitOverviewSource.includes('data-testid="b-widget-acceptance-grid"') &&
          bWidgetKitOverviewSource.includes("data-testid={`b-widget-acceptance-${item.key}`}") &&
          bWidgetKitOverviewSource.includes("data-testid={`b-widget-acceptance-technical-${item.key}`}") &&
          bWidgetKitOverviewSource.includes('data-testid="b-widget-catalog-technical-details"') &&
          ["看总量", "看排行", "看趋势", "查明细", "快速筛选", "跨表分析", "追到原始记录", "维护组件", "调整呈现"].every((label) => bWidgetKitModelSource.includes(label)) &&
          bWidgetKitOverviewSource.includes("用户会做的事都集中可测") &&
          bWidgetKitOverviewSource.includes("查看组件目录和命令证据") &&
          ["metric", "bar", "line", "pie", "table", "text", "slicer", "relationship", "filter", "drilldown", "copy-delete", "style"].every((key) => bWidgetKitModelSource.includes(`key: "${key}"`)) &&
          bWidgetKitOverviewSource.includes("dashboard-widget-gallery") &&
          bWidgetKitOverviewSource.includes("dashboardSelectionConfidence") &&
          stylesSource.includes(".dashboardComponentAcceptanceStrip") &&
          stylesSource.includes(".dashboardComponentAcceptanceItems") &&
          stylesSource.includes(".bWidgetAcceptanceGallery") &&
          stylesSource.includes(".bWidgetAcceptanceGrid") &&
          stylesSource.includes(".bWidgetAcceptanceItem.ready") &&
          stylesSource.includes(".bWidgetAcceptanceTechnical"),
      },
    {
        label: "implementation-status-handoff",
        ok: implementationStatusSource.includes("# AIBI-C 实现状态") &&
          implementationStatusSource.includes("## 当前发布边界") &&
          implementationStatusSource.includes("## 能力状态") &&
          implementationStatusSource.includes("## 已知限制") &&
          implementationStatusSource.includes("## 架构归属") &&
          implementationStatusSource.includes("npm run verify") &&
          implementationStatusSource.includes("python tools/aibi_cli.py --json status") &&
          implementationStatusSource.includes("single-user and local-only"),
      },
    {
        label: "frontend-agent-panel-action-draft-lifecycle",
        ok: agentPanelSource.includes("actionDrafts: ActionDraft[]") &&
          agentPanelSource.includes('from "../agentPanelModel"') &&
          agentPanelModelSource.includes("export function actionKindText") &&
          agentPanelModelSource.includes("export function actionTarget") &&
          agentPanelSource.includes("lastActionResult: Record<string, unknown> | null") &&
          agentPanelSource.includes("onRejectAction") &&
          agentPanelSource.includes("<AgentPendingChangesPanel") &&
          agentPendingChangesPanelSource.includes("data-testid=\"agent-draft-queue\"") &&
          agentPendingChangesPanelSource.includes("data-testid=\"agent-draft-queue-item\"") &&
          agentPendingChangesPanelSource.includes("const otherDrafts = pendingDrafts.filter") &&
          agentPendingChangesPanelSource.includes("data-testid=\"agent-current-draft-reject\"") &&
          agentPendingChangesPanelSource.includes("data-testid={`agent-draft-reject-${draft.action_key}`}") &&
          agentPendingChangesPanelSource.includes("onConfirmDryRun(draft.action_key)") &&
          agentPanelSource.includes("onConfirmAction: (actionKey: string, draft?: ActionDraft) => Promise<void>") &&
          agentPendingChangesPanelSource.includes("onConfirmAction: (actionKey: string, draft?: ActionDraft) => Promise<void>") &&
          agentPendingChangesPanelSource.includes("onConfirmAction(activeActionKey, currentDraft)") &&
          agentPendingChangesPanelSource.includes("onConfirmAction(draft.action_key, draft)") &&
          agentPendingChangesPanelSource.includes("onRejectAction(draft.action_key)") &&
          appAgentActionsSource.includes('import { confirmedActionNavigationTarget } from "./agentActionNavigationModel"') &&
          appAgentActionsSource.includes("const handleConfirmAction = useCallback(async (actionKey: string, draft?: ActionDraft)") &&
          appAgentActionsSource.includes("confirmedActionNavigationTarget(actionKey, result, draft)") &&
          appAgentActionsSource.includes("navigateTo(target)") &&
          agentPanelSource.includes("currentDraftIsPending") &&
          agentPanelModelSource.includes("dashboard.copy") &&
          agentPanelModelSource.includes("dashboard.rename") &&
          agentPanelModelSource.includes("dashboard.delete") &&
          agentPanelModelSource.includes("dashboard.widget.add") &&
          agentPanelModelSource.includes("dashboard.filter.add") &&
          agentPanelModelSource.includes("index.create") &&
          agentPanelModelSource.includes("relationship.save") &&
          agentPanelModelSource.includes("import.commit") &&
          agentPanelModelSource.includes("formula.save") &&
          agentPanelModelSource.includes("view.save") &&
          agentPanelModelSource.includes("metric.add") &&
          agentPanelModelSource.includes("semantic.set") &&
          agentPanelModelSource.includes("filePath") &&
          agentPanelModelSource.includes("formulaText") &&
          agentPanelModelSource.includes("Add metric") &&
          agentPanelModelSource.includes("Add dashboard widget") &&
          agentPanelModelSource.includes("Add dashboard filter") &&
          agentPanelModelSource.includes("leftTable") &&
          agentPanelModelSource.includes("Create query index") &&
          appSource.includes("lastActionResult={lastActionResult}"),
      },
    {
        label: "frontend-agent-dry-run-result-feedback",
        ok: agentPanelModelSource.includes("export function resultActionKey") &&
          agentPanelModelSource.includes("export function actionResultHeadline") &&
          agentPanelModelSource.includes("export function actionResultDetail") &&
          agentPanelSource.includes("const activeActionResult = activeActionKey && resultActionKey(lastActionResult) === activeActionKey ? lastActionResult : null") &&
          agentPendingChangesPanelSource.includes('data-testid="agent-action-result"') &&
          agentPendingChangesPanelSource.includes('data-testid="agent-action-result-headline"') &&
          agentPendingChangesPanelSource.includes('data-testid="agent-action-result-detail"') &&
          agentPanelModelSource.includes("预演完成") &&
          agentPanelModelSource.includes("确认前不会写入") &&
          stylesSource.includes(".agentActionResult") &&
          appSource.includes("lastActionResult={lastActionResult}"),
      },
    {
        label: "frontend-agent-draft-impact-summary",
        ok: agentPanelModelSource.includes("export function actionImpactGroup") &&
          agentPanelSource.includes("const draftImpactItems") &&
          agentPanelSource.includes("const riskyDraftCount") &&
          agentPendingChangesPanelSource.includes("data-testid=\"agent-draft-impact-summary\"") &&
          agentPendingChangesPanelSource.includes("data-testid=\"agent-draft-impact-grid\"") &&
          agentPendingChangesPanelSource.includes("data-testid={`agent-draft-impact-${item.key}`}") &&
          agentPanelSource.includes(".filter((item) => item.count > 0)") &&
          ["data", "dashboard", "model", "workspace"].every((key) => agentPanelSource.includes(`key: "${key}"`)) &&
          agentPendingChangesPanelSource.includes("Review impact before approval") &&
          stylesSource.includes(".agentDraftImpactSummary") &&
          stylesSource.includes(".agentDraftImpactGrid") &&
          agentPendingChangesPanelSource.includes("otherDrafts.map((draft)"),
      },
    {
        label: "frontend-agent-task-packet-business-summary",
        ok: agentPanelSource.includes("<AgentTaskPacket") &&
          agentTaskPacketSource.includes("data-testid=\"agent-task-packet\"") &&
          agentTaskPacketSource.includes("data-testid=\"agent-task-packet-target\"") &&
          agentTaskPacketSource.includes("data-testid=\"agent-task-packet-risk\"") &&
          agentTaskPacketSource.includes("data-testid=\"agent-task-packet-evidence\"") &&
          agentPanelModelSource.includes("export function actionRiskText") &&
          agentPanelModelSource.includes("export function actionEvidenceChips") &&
          agentPanelModelSource.includes("export function dashboardCreateDraft") &&
          agentPanelModelSource.includes("export function draftDashboardLabel") &&
          agentTaskPacketSource.includes("data-testid=\"agent-dashboard-draft-preview\"") &&
          agentTaskPacketSource.includes("data-testid=\"agent-dashboard-draft-widget\"") &&
          agentTaskPacketSource.includes("data-testid=\"agent-erp-unit-summary\"") &&
          agentTaskPacketSource.includes("data-testid=\"agent-erp-gap-list\"") &&
          agentTaskPacketSource.includes("data-testid=\"agent-erp-missing-field-chips\"") &&
          agentTaskPacketSource.includes("data-testid=\"agent-erp-gap-unlocks\"") &&
          agentTaskPacketSource.includes("data-testid=\"agent-erp-category-coverage\"") &&
          agentTaskPacketSource.includes("data-testid=\"agent-erp-source-list\"") &&
          agentTaskPacketSource.includes("collectNeededFieldsFromErpHints(allErpGaps, 8)") &&
          agentTaskPacketSource.includes("buildErpGapUnlocks(allErpGaps, 3)") &&
          agentTaskPacketSource.includes("neededFieldsForErpHint(gap)") &&
          agentPanelModelSource.includes('"erp-unit-library": biText("ERP 单元", "ERP units")') &&
          agentPanelModelSource.includes("previewWidgets") &&
          agentPanelSource.includes("const currentDraft = pendingDrafts.find") &&
          agentPanelSource.includes("?? pendingDrafts[0]") &&
          agentPanelSource.includes("activeDashboardConfidence") &&
          agentPanelSource.includes("activeBoundaryBlocked") &&
          agentContextPlanPanelSource.includes("Change queued") &&
          agentContextPlanPanelSource.includes("current task packet has a change awaiting approval") &&
          agentTaskPacketSource.includes("actionTarget(currentDraft)") &&
          agentPanelModelSource.includes("dashboardSelectionConfidence") &&
          agentPanelModelSource.includes("Model change: affects future analysis only after confirmation.") &&
          agentPendingChangesPanelSource.includes('data-testid="agent-current-draft-next-step"') &&
          agentPendingChangesPanelSource.includes("actionNextStepText(currentDraft)") &&
          byLabel["cli-agent-widget-draft"].parsed?.requiresConfirmation === true &&
          byLabel["cli-agent-widget-draft"].parsed?.actionDraft?.kind === "dashboard.widget.add" &&
          byLabel["cli-agent-widget-draft"].parsed?.matched?.dashboardSelectionConfidence === "explicit",
      },
    {
        label: "frontend-agent-panel-pending-change-language",
        ok: agentPendingChangesPanelSource.includes("待确认修改") &&
          agentContextPlanPanelSource.includes("有待确认修改") &&
          agentContextPlanPanelSource.includes("Change requires approval") &&
          agentPendingChangesPanelSource.includes('data-testid="agent-action-technical-details"') &&
          agentPanelSource.includes('data-testid="agent-recommended-command-details"') &&
          agentPendingChangesPanelSource.includes('data-testid={`agent-draft-queue-technical-${draft.action_key}`}') &&
          agentPendingChangesPanelSource.includes("查看动作技术详情") &&
          agentPanelSource.includes("查看技术命令") &&
          agentPendingChangesPanelSource.includes("查看证据和编号") &&
          !agentPanelSource.includes("<h3><Bilingual zh=\"动作草案\"") &&
          !agentPanelSource.includes("<h3><Bilingual zh=\"推荐命令\"") &&
          stylesSource.includes(".agentActionTechnical") &&
          stylesSource.includes(".agentRecommendedCommands") &&
          stylesSource.includes(".agentDraftQueueTechnical"),
      },
    {
        label: "frontend-agent-answer-card",
        ok: agentPanelSource.includes("<AgentAnswerCard") &&
          agentAnswerCardSource.includes("data-testid=\"agent-answer-card\"") &&
          agentAnswerCardSource.includes("data-testid=\"agent-answer-rows\"") &&
          agentAnswerCardSource.includes("data-testid=\"agent-clarification-choices\"") &&
          agentAnswerCardSource.includes("data-testid=\"agent-clarification-measure\"") &&
          agentAnswerCardSource.includes("data-testid=\"agent-clarification-dimension\"") &&
          agentAnswerCardSource.includes("candidatePrompt(\"measure\", field)") &&
          agentPanelSource.includes("onAskCandidate={(candidatePrompt)") &&
          typesAgentSource.includes("clarification?:") &&
          biCliSource.includes("\"clarification\": {") &&
          agentAnswerCardSource.includes("answerCard: NonNullable<AgentAskResult") &&
          agentPanelSource.includes("type AnswerEvidenceStep") &&
          agentPanelSource.includes("const answerEvidenceSteps: AnswerEvidenceStep[]") &&
          agentAnswerCardSource.includes("data-testid=\"agent-answer-evidence-route\"") &&
          agentAnswerCardSource.includes("data-testid=\"agent-answer-evidence-steps\"") &&
          agentAnswerCardSource.includes("data-testid={`agent-answer-evidence-route-${item.key}`}") &&
          agentPanelSource.includes('key: "source"') &&
          agentPanelSource.includes('key: "metric"') &&
          agentPanelSource.includes('key: "runtime"') &&
          agentPanelSource.includes('key: "boundary"') &&
          agentAnswerCardSource.includes("先看结论，再追到数据、口径和查询回执") &&
          agentAnswerCardSource.includes("Read the answer first, then trace source, metric, and query receipt") &&
          agentAnswerCardSource.includes('data-testid="agent-answer-runtime-technical"') &&
          agentPanelModelSource.includes("只读查询已完成") &&
          agentAnswerCardSource.includes("查看查询回执技术信息") &&
          agentPanelSource.includes("受控查询") &&
          agentAnswerCardSource.includes("Business answer") &&
          agentAnswerCardSource.includes("evidenceRefText") &&
          agentPanelModelSource.includes("Query receipt") &&
          agentPanelModelSource.includes("Business rule") &&
          stylesSource.includes(".agentAnswerEvidenceRoute") &&
          stylesSource.includes(".agentAnswerEvidenceSteps") &&
          stylesSource.includes(".agentAnswerRuntimeTechnical") &&
          stylesSource.includes(".agentClarificationChoices") &&
          stylesSource.includes(".agentClarificationChipGrid"),
      },
    {
        label: "frontend-agent-can-answer-suggestions",
        ok: agentPanelSource.includes("workbench: WorkbenchPayload") &&
          agentPanelSource.includes("<AgentCanAnswerPanel") &&
          agentCanAnswerPanelSource.includes("data-testid=\"agent-can-answer-panel\"") &&
          agentCanAnswerPanelSource.includes("data-testid=\"agent-can-answer-suggestions\"") &&
          agentCanAnswerPanelSource.includes("data-testid={`agent-can-answer-${item.key}`}") &&
          agentPanelSource.includes("sourceRunPrompt(latestRun)") &&
          agentPanelSource.includes("metricPrompt(topMetric)") &&
          agentPanelSource.includes("viewPrompt(topView)") &&
          agentPanelSource.includes("topRelationship") &&
          agentCanAnswerPanelSource.includes("onAskSuggestion(item.prompt)") &&
          agentCanAnswerPanelSource.includes("Start from evidence, not configuration") &&
          appSource.includes("workbench={workbench}") &&
          byLabel["cli-agent-ask"].parsed?.ok === true,
      },
    {
        label: "frontend-agent-checked-evidence-summary",
        ok: agentPanelSource.includes("type CheckedItem") &&
          agentPanelModelSource.includes("export type CheckedItem") &&
          agentPanelSource.includes("const checkedItems: CheckedItem[]") &&
          agentPanelSource.includes("<AgentEvidenceAuditPanels") &&
          agentEvidenceAuditPanelsSource.includes('data-testid="agent-checked-panel"') &&
          agentEvidenceAuditPanelsSource.includes('data-testid="agent-checked-grid"') &&
          agentEvidenceAuditPanelsSource.includes('data-testid={`agent-checked-${item.key}`}') &&
          agentPanelSource.includes('key: "source-intelligence"') &&
          agentPanelSource.includes('key: "metric"') &&
          agentPanelSource.includes('key: "runtime"') &&
          agentPanelSource.includes('key: "dashboard"') &&
          agentPanelSource.includes("queryRuntimeRef") &&
          agentEvidenceAuditPanelsSource.includes("What this response checked") &&
          stylesSource.includes(".agentCheckedPanel") &&
          stylesSource.includes(".agentCheckedGrid"),
      },
    {
        label: "agent-llm-provider-audit",
        ok: byLabel["cli-agent-ask"].parsed?.llm?.audit?.serverSideOnly === true &&
          byLabel["cli-agent-ask"].parsed?.llm?.audit?.secretExposed === false &&
          byLabel["cli-agent-ask"].parsed?.llm?.audit?.contextBoundary === "active-workspace-sourceRun-workbench" &&
          ["provider", "deterministic-fallback"].includes(byLabel["cli-agent-ask"].parsed?.llm?.audit?.mode) &&
          !JSON.stringify(byLabel["cli-agent-ask"].parsed?.llm ?? {}).includes("DEEPSEEK_API_KEY=") &&
          biCliSource.includes('"secretExposed": False') &&
          biCliSource.includes('"serverSideOnly": True') &&
          typesAgentSource.includes("audit?: {") &&
          agentPanelSource.includes("<AgentEvidenceAuditPanels") &&
          agentEvidenceAuditPanelsSource.includes('data-testid="agent-llm-audit-panel"') &&
          agentEvidenceAuditPanelsSource.includes('data-testid="agent-llm-audit-technical"') &&
          agentEvidenceAuditPanelsSource.includes('data-testid="agent-llm-audit-grid"') &&
          agentEvidenceAuditPanelsSource.includes('data-testid={`agent-llm-audit-${item.key}`}') &&
          agentPanelSource.includes("llmAuditItems") &&
          agentPanelSource.includes("secretExposed") &&
          agentEvidenceAuditPanelsSource.includes("当前由本地规则和工作区证据生成回答") &&
          agentEvidenceAuditPanelsSource.includes("View model runtime detail") &&
          agentEvidenceAuditPanelsSource.includes("The DeepSeek key is used only server-side") &&
          stylesSource.includes(".agentLlmAuditPanel") &&
          stylesSource.includes(".agentLlmAuditTechnical") &&
          stylesSource.includes(".agentLlmAuditGrid"),
      },
    {
        label: "frontend-agent-target-boundary-confidence",
        ok: agentContextPlanPanelSource.includes("data-testid=\"agent-target-boundary\"") &&
          agentContextPlanPanelSource.includes("data-testid=\"agent-dashboard-confidence\"") &&
          agentContextPlanPanelSource.includes("confidenceText") &&
          agentPanelSource.includes("blockedDashboardWrite") &&
          agentContextPlanPanelSource.includes("没有明确命中目标看板") &&
          agentContextPlanPanelSource.includes("No target dashboard was matched") &&
          byLabel["cli-agent-missing-dashboard"].parsed?.matched?.dashboardSelectionConfidence === "missing" &&
          byLabel["cli-agent-missing-dashboard"].parsed?.requiresConfirmation === false &&
          byLabel["cli-agent-missing-dashboard"].parsed?.actionDraft?.actionKey === "read_only_plan" &&
          byLabel["cli-agent-widget-draft"].parsed?.matched?.dashboardSelectionConfidence === "explicit" &&
          byLabel["cli-agent-widget-draft"].parsed?.requiresConfirmation === true,
      },
    {
        label: "agent-context-plan-panel-boundary",
        ok: existsSync(join(root, "src", "components", "AgentContextPlanPanel.tsx")) &&
          agentPanelSource.includes('import { AgentContextPlanPanel } from "./AgentContextPlanPanel"') &&
          agentPanelSource.includes("<AgentContextPlanPanel") &&
          !agentPanelSource.includes('data-testid="agent-target-boundary"') &&
          agentContextPlanPanelSource.includes("type AgentContextPlanPanelProps") &&
          agentContextPlanPanelSource.includes("activeDashboardConfidence: SelectionConfidence | \"draft\"") &&
          agentContextPlanPanelSource.includes("匹配上下文") &&
          agentContextPlanPanelSource.includes("计划"),
      },
    {
        label: "agent-prompt-composer-component-boundary",
        ok: existsSync(join(root, "src", "components", "AgentPromptComposer.tsx")) &&
          agentPanelSource.includes('import { AgentPromptComposer } from "./AgentPromptComposer"') &&
          agentPanelSource.includes("<AgentPromptComposer") &&
          !agentPanelSource.includes('className="agentComposer"') &&
          !agentPanelSource.includes('aria-label={biText("Agent 提问", "Agent prompt")}') &&
          agentPromptComposerSource.includes("type AgentPromptComposerProps") &&
          agentPromptComposerSource.includes('data-testid="agent-prompt-composer"') &&
          agentPromptComposerSource.includes('aria-label={biText("Agent 提问", "Agent prompt")}') &&
          agentPromptComposerSource.includes("setPromptTouched(true)") &&
          agentPromptComposerSource.includes("isAsking ? biText(\"规划中\", \"Planning\") : biText(\"提问\", \"Ask\")"),
      },
    {
        label: "write-ops-default-dry-run",
        ok: byLabel["cli-field-update-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-relationship-save-dry-run"].parsed?.requiresConfirmation === true &&
          byLabel["cli-dashboard-op-dry-run"].parsed?.requiresConfirmation === true,
      }
  );
}
