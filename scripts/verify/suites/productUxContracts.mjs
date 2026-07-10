export function appendProductUxContractChecks(context) {
  const {
    checks,
    actionRecoveryModelSource,
    agentAnswerCardSource,
    agentCanAnswerPanelSource,
    agentCommandDockSource,
    agentContextPlanPanelSource,
    agentEvidenceAuditPanelsSource,
    agentPanelModelSource,
    agentPanelSource,
    agentPendingChangesPanelSource,
    agentPromptComposerSource,
    agentPromptRoutingSource,
    agentTaskPacketSource,
    appAgentActionsSource,
    appDataActionsSource,
    appSource: appEntrySource,
    appMainViewSource,
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
    evidenceViewSource,
    existsSync,
    globalStylesSource,
    homeOverviewSource,
    implementationStatusSource,
    inspectorControllerSource,
    inspectorContextPanelSource,
    inspectorEvidenceDetailsSource,
    inspectorPanelModelSource,
    inspectorPanelSource,
    inspectorTaskQueuePanelSource,
    join,
    metricSemanticRepairActionsSource,
    packageJson,
    readmeSource,
    root,
    settingsAcceptanceEvidencePanelSource,
    settingsConfigPortabilityPanelSource,
    settingsPanelSource,
    settingsPanelStylesSource,
    settingsSandboxBoundaryPanelSource,
    settingsThemePreferencePanelSource,
    sourceIntelligenceRunModelSource,
    sourceWorkbenchActionPanelSource,
    stylesSource,
    typesAgentSource,
    verifyAAdversarialSource,
  } = context;
  const appSource = `${appEntrySource}\n${appMainViewSource}\n${inspectorControllerSource}`;
  const inspectorFeatureSource = `${inspectorPanelSource}\n${inspectorContextPanelSource}\n${inspectorTaskQueuePanelSource}\n${inspectorEvidenceDetailsSource}`;
  checks.push(
    {
        label: "frontend-inspector-selected-context",
        ok: inspectorPanelSource.includes("activeSection: AppSection") &&
          inspectorPanelSource.includes("evidenceFocus?: EvidenceFocus | null") &&
          inspectorPanelSource.includes('import { InspectorContextPanel } from "./InspectorContextPanel"') &&
          inspectorPanelSource.includes("<InspectorContextPanel") &&
          inspectorContextPanelSource.includes("data-testid=\"inspector-selected-context\"") &&
          inspectorContextPanelSource.includes("data-testid=\"inspector-selected-context-chips\"") &&
          inspectorContextPanelSource.includes("data-testid=\"inspector-open-evidence\"") &&
          inspectorContextPanelSource.includes("sectionContext(activeSection") &&
          inspectorPanelModelSource.includes("export function drawerActionsForSection") &&
          inspectorPanelModelSource.includes("export function sectionContext") &&
          inspectorContextPanelSource.includes("drawerActionsForSection(activeSection)") &&
          inspectorPanelModelSource.includes("检查摘要") &&
          inspectorPanelModelSource.includes("改看板") &&
          appSource.includes("activeSection={section}") &&
          appSource.includes("evidenceFocus={evidenceFocus}") &&
          appSource.includes("activeDashboardName={activeDashboardName}") &&
          appSource.includes("activeViewName={activeViewName}") &&
          appEntrySource.includes("onOpenEvidence={inspector.openEvidence}") &&
          inspectorControllerSource.includes('openSection("evidence")') &&
          appSource.includes("const activeDashboardName ="),
      },
    {
        label: "frontend-collapsible-inspector",
        ok: inspectorControllerSource.includes("inspectorPreferenceStorageKey") &&
          inspectorControllerSource.includes("initialInspectorPreference") &&
          inspectorControllerSource.includes("export function useInspectorController") &&
          inspectorControllerSource.includes("window.localStorage.setItem") &&
          appEntrySource.includes("const inspector = useInspectorController(openSection)") &&
          appEntrySource.includes("data-inspector-state={inspector.expanded ? \"expanded\" : \"collapsed\"}") &&
          appEntrySource.includes("inspectorCollapsed={!inspector.expanded}") &&
          appEntrySource.includes("onCollapseInspector={inspector.collapse}") &&
          appEntrySource.includes("onExpandInspector={inspector.expand}") &&
          appEntrySource.includes("onPinInspectorToggle={inspector.togglePinned}") &&
          inspectorPanelSource.includes("inspectorCollapsed: boolean") &&
          inspectorPanelSource.includes("inspectorPinned: boolean") &&
          inspectorPanelSource.includes("data-testid=\"inspector-expand\"") &&
          inspectorPanelSource.includes("data-testid=\"inspector-collapse\"") &&
          inspectorPanelSource.includes("data-testid=\"inspector-pin\"") &&
          inspectorPanelSource.includes("data-testid=\"inspector-mini-evidence\"") &&
          inspectorPanelSource.includes("data-testid=\"inspector-mini-tasks\"") &&
          inspectorPanelSource.includes("data-testid=\"inspector-mini-safety\"") &&
          stylesSource.includes('.appShell[data-inspector-state="collapsed"]') &&
          stylesSource.includes(".inspectorCollapsed") &&
          stylesSource.includes(".inspectorMiniButton"),
      },
    {
        label: "frontend-inspector-friendly-action-error",
        ok: inspectorPanelSource.includes('import { InspectorTaskQueuePanel } from "./InspectorTaskQueuePanel"') &&
          inspectorPanelSource.includes("<InspectorTaskQueuePanel") &&
          inspectorTaskQueuePanelSource.includes("actionResultSummary(lastActionResult)") &&
          inspectorTaskQueuePanelSource.includes("import { actionKindLabel, actionNextStep, actionResultSummary, payloadTarget }") &&
          actionRecoveryModelSource.includes("export function buildActionRecovery") &&
          actionRecoveryModelSource.includes("query-table") &&
          actionRecoveryModelSource.includes("dashboard-recovery") &&
          actionRecoveryModelSource.includes("source-recovery") &&
          actionRecoveryModelSource.includes("export function actionRecoveryFromError") &&
          appWorkspaceModelSource.includes('import { actionRecoveryFromError, buildActionRecovery } from "./actionRecoveryModel"') &&
          appWorkspaceModelSource.includes("actionRecoveryFromError(error) ?? buildActionRecovery(action, error)") &&
          appWorkspaceModelSource.includes("targetSection: recovery.targetSection") &&
          appWorkspaceModelSource.includes("recovery,") &&
          inspectorPanelModelSource.includes('import { actionRecoveryFromResult } from "./actionRecoveryModel"') &&
          inspectorPanelModelSource.includes("const recovery = actionRecoveryFromResult(result)") &&
          inspectorPanelModelSource.includes("steps: recovery.steps") &&
          inspectorPanelModelSource.includes("targetSection: recovery.targetSection") &&
          inspectorPanelModelSource.includes("function friendlyActionError") &&
          inspectorPanelModelSource.includes("No analyzable CSV/XLSX spreadsheet was found") &&
          inspectorPanelModelSource.includes("证据摘要没有完成") &&
          inspectorTaskQueuePanelSource.includes('data-testid="last-action-recovery-steps"') &&
          inspectorTaskQueuePanelSource.includes('data-testid="last-action-recovery-open-section"') &&
          inspectorTaskQueuePanelSource.includes("getAppSection(latestSummary.targetSection)") &&
          inspectorTaskQueuePanelSource.includes("onOpenSection(latestSummary.targetSection!)") &&
          inspectorTaskQueuePanelSource.includes("visibleActionSafeState") &&
          inspectorControllerSource.includes("const openAndExpand = useCallback") &&
          appEntrySource.includes("onOpenSection={inspector.openAndExpand}") &&
          inspectorTaskQueuePanelSource.includes("data-testid=\"last-action-technical\"") &&
          inspectorTaskQueuePanelSource.includes("visibleActionSummary ${latestSummary.tone}") &&
          inspectorTaskQueuePanelSource.includes("查看错误原文") &&
          appDataActionsSource.includes('action: "source-intelligence"') &&
          appDataActionsSource.includes("throw error") &&
          stylesSource.includes(".visibleActionSummary.failed") &&
          stylesSource.includes(".visibleActionSummaryBody") &&
          stylesSource.includes(".visibleActionSafeState") &&
          stylesSource.includes(".visibleActionRecoverySteps") &&
          stylesSource.includes(".visibleActionRecoveryAction") &&
          stylesSource.includes(".visibleActionTechnical"),
      },
    {
        label: "frontend-inspector-action-queue-business-first",
        ok: inspectorPanelModelSource.includes("export function actionNextStep") &&
          inspectorPanelModelSource.includes("export function payloadTarget") &&
          inspectorPanelModelSource.includes("export function actionKindLabel") &&
          inspectorTaskQueuePanelSource.includes("actionNextStep(draft)") &&
          inspectorTaskQueuePanelSource.includes("payloadTarget(draft)") &&
          inspectorTaskQueuePanelSource.includes("actionKindLabel(draft.kind)") &&
          inspectorTaskQueuePanelSource.includes('data-testid="action-queue-next-step"') &&
          inspectorTaskQueuePanelSource.includes('data-testid={`action-queue-technical-${draft.action_key}`}') &&
          inspectorTaskQueuePanelSource.includes("查看证据和编号") &&
          inspectorTaskQueuePanelSource.includes("查看错误原文") &&
          inspectorTaskQueuePanelSource.includes("证据线索") &&
          !inspectorTaskQueuePanelSource.includes("evidence refs`)") &&
          stylesSource.includes(".taskNextStep") &&
          stylesSource.includes(".taskEvidenceRow summary"),
      },
    {
        label: "frontend-object-inspector-v2",
        ok: inspectorContextPanelSource.includes("buildObjectInspectorModel({ activeSection") &&
          inspectorContextPanelSource.includes('data-testid="object-inspector-lens"') &&
          inspectorContextPanelSource.includes('data-testid="object-inspector-facts"') &&
          inspectorContextPanelSource.includes('data-testid="object-inspector-editor-slots"') &&
          inspectorContextPanelSource.includes("objectModel.primaryAction") &&
          inspectorPanelSource.includes('import { InspectorEvidenceDetails } from "./InspectorEvidenceDetails"') &&
          inspectorPanelSource.includes("<InspectorEvidenceDetails") &&
          inspectorEvidenceDetailsSource.includes('<details className="contextReservePanel">') &&
          inspectorEvidenceDetailsSource.includes("扩展能力") &&
          inspectorFeatureSource.includes('data-testid="action-queue"') &&
          stylesSource.includes(".objectInspectorLens") &&
          stylesSource.includes(".objectInspectorFacts") &&
          stylesSource.includes(".objectInspectorSlots") &&
          stylesSource.includes(".contextReservePanel summary"),
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
          evidenceViewSource.includes('import { EvidenceNumberExplainerPanel } from "./EvidenceNumberExplainerPanel"') &&
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
        ok: agentCommandDockSource.includes("data-testid=\"agent-command-dock\"") &&
          !appSource.includes('section !== "agent"') &&
          appSource.includes("<AgentCommandDock") &&
          agentCommandDockSource.includes('data-testid="floating-agent-button"') &&
          agentCommandDockSource.includes('data-testid="floating-agent-panel"') &&
          agentCommandDockSource.includes('setAssistantOpen(true)') &&
          agentCommandDockSource.includes('setAssistantOpen(false)') &&
          agentCommandDockSource.includes('aria-label={biText("全局 AI 助手"') &&
          agentCommandDockSource.includes('getAppSection(activeSection)') &&
          agentCommandDockSource.includes('import { resolveAgentPromptRoute, type AgentPromptRoute } from "../agentPromptRouting"') &&
          agentCommandDockSource.includes("const [routeHint, setRouteHint] = useState<AgentPromptRoute | null>(null)") &&
          agentCommandDockSource.includes("const route = resolveAgentPromptRoute(normalizedPrompt, status)") &&
          agentCommandDockSource.includes("onOpenSection(route.section)") &&
          agentCommandDockSource.includes("await onAsk(normalizedPrompt, route.section)") &&
          agentCommandDockSource.includes('data-testid="agent-route-hint"') &&
          agentPromptRoutingSource.includes("export function resolveAgentPromptRoute") &&
          agentPromptRoutingSource.includes('section: "sources"') &&
          agentPromptRoutingSource.includes('section: "views"') &&
          agentPromptRoutingSource.includes('section: "dashboards"') &&
          agentPromptRoutingSource.includes('section: "evidence"') &&
          agentPromptRoutingSource.includes('section: "settings"') &&
          appAgentActionsSource.includes("targetSection?: AppSection") &&
          appAgentActionsSource.includes("if (nextAgent?.requiresConfirmation)") &&
          appAgentActionsSource.includes('setSection(targetSection ?? "agent")') &&
          agentCommandDockSource.includes("aria-busy={busy}") &&
          agentCommandDockSource.includes("data-testid=\"agent-task-strip\"") &&
          agentCommandDockSource.includes("data-testid=\"agent-task-sources\"") &&
          agentCommandDockSource.includes("data-testid=\"agent-task-dashboard\"") &&
          /data-testid="agent-task-dashboard"\s+disabled=\{busy\}/.test(agentCommandDockSource) &&
          agentCommandDockSource.includes("data-testid=\"agent-task-evidence\"") &&
          /data-testid="agent-task-ask"\s+disabled=\{busy\}/.test(agentCommandDockSource) &&
          agentCommandDockSource.includes("data-testid=\"agent-decision-lane\"") &&
          agentCommandDockSource.includes("data-testid={`agent-decision-${item.key}`}") &&
          agentCommandDockSource.includes("data-testid={`agent-decision-${item.key}`} disabled={busy}") &&
          /disabled=\{busy\}\s+key=\{item\.(key|zh)\}/.test(agentCommandDockSource) &&
          agentCommandDockSource.includes("Can answer") &&
          agentCommandDockSource.includes("Review needed") &&
          agentCommandDockSource.includes("Missing data") &&
          agentCommandDockSource.includes("sourceIntelligenceCount") &&
          agentCommandDockSource.includes("hasEvidenceProfile") &&
          agentCommandDockSource.includes("onOpenSection(\"sources\")") &&
          agentCommandDockSource.includes("onOpenSection(\"evidence\")") &&
          agentCommandDockSource.includes("根据当前字段和证据起草一个最合适的图表，先不要直接写入") &&
          stylesSource.includes(".agentCommandDock.floating") &&
          stylesSource.includes(".agentFloatButton") &&
          stylesSource.includes(".agentFloatPanel") &&
          stylesSource.includes(".agentRouteHint") &&
          stylesSource.includes('.appShell[data-inspector-state="expanded"] .agentCommandDock.floating') &&
          stylesSource.includes(".agentDockDecisionLane") &&
          stylesSource.includes(".agentDockShortcuts button") &&
          stylesSource.includes("min-height: 34px"),
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
        ok: sourceWorkbenchActionPanelSource.includes('data-testid="import-to-dashboard-wizard"') &&
          sourceWorkbenchActionPanelSource.includes('<details className="sourceGuideDetails"') &&
          sourceWorkbenchActionPanelSource.includes("这些文件是什么业务？") &&
          sourceWorkbenchActionPanelSource.includes("证据摘要是否完整？") &&
          sourceWorkbenchActionPanelSource.includes("先看什么问题？") &&
          sourceWorkbenchActionPanelSource.includes("source-agent-import-guide") &&
          !sourceWorkbenchActionPanelSource.includes("beginner-plan-import-data") &&
          sourceWorkbenchActionPanelSource.includes('disabled={!dashboardRecipeReady || busy === "source-business-dashboard-create"}') &&
          stylesSource.includes(".importToDashboardWizard") &&
          stylesSource.includes(".wizardQuestionGrid") &&
          stylesSource.includes(".wizardActions"),
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
        label: "frontend-settings-closure-workbench",
        ok: settingsAcceptanceEvidencePanelSource.includes("const closureItems") &&
          settingsAcceptanceEvidencePanelSource.includes('data-testid="settings-closure-workbench"') &&
          settingsAcceptanceEvidencePanelSource.includes('data-testid="settings-closure-lead"') &&
          settingsAcceptanceEvidencePanelSource.includes('data-testid="settings-closure-grid"') &&
          settingsAcceptanceEvidencePanelSource.includes('data-testid={`settings-closure-${item.key}`}') &&
          settingsAcceptanceEvidencePanelSource.includes("刷新不白屏") &&
          settingsAcceptanceEvidencePanelSource.includes("本地 BI 操作已并入当前工作区") &&
          settingsAcceptanceEvidencePanelSource.includes("空工作区只引导导入") &&
          settingsAcceptanceEvidencePanelSource.includes("看板阅读和编辑动作集中可验收") &&
          settingsAcceptanceEvidencePanelSource.includes("新手路径已收敛") &&
          settingsAcceptanceEvidencePanelSource.includes("docs/implementation-status.md") &&
          settingsAcceptanceEvidencePanelSource.includes("python tools/bi_cli.py --json b-cli-capabilities") &&
          settingsAcceptanceEvidencePanelSource.includes('data-testid={`settings-closure-technical-${item.key}`}') &&
          settingsAcceptanceEvidencePanelSource.includes("empty-workspace-data-boundary") &&
          settingsAcceptanceEvidencePanelSource.includes("frontend-b-widget-acceptance-gallery") &&
          stylesSource.includes(".closureWorkbenchCard") &&
          stylesSource.includes(".closureGrid") &&
          stylesSource.includes(".closureItem.ok") &&
          stylesSource.includes(".closureTechnical"),
      },
    {
        label: "settings-acceptance-evidence-panel-component-boundary",
        ok: existsSync(join(root, "src", "components", "SettingsAcceptanceEvidencePanel.tsx")) &&
          settingsPanelSource.includes('import { SettingsAcceptanceEvidencePanel } from "./SettingsAcceptanceEvidencePanel"') &&
          settingsPanelSource.includes("<SettingsAcceptanceEvidencePanel") &&
          !settingsPanelSource.includes("const closureItems") &&
          !settingsPanelSource.includes('data-testid="settings-closure-workbench"') &&
          !settingsPanelSource.includes('className="settingsEvidenceList"') &&
          settingsAcceptanceEvidencePanelSource.includes("export function SettingsAcceptanceEvidencePanel") &&
          settingsAcceptanceEvidencePanelSource.includes('className="settingsEvidenceList"') &&
          settingsAcceptanceEvidencePanelSource.includes('data-testid="settings-closure-workbench"'),
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
        label: "a-adversarial-source-intelligence-harness",
        ok: packageJson.scripts["verify:a-adversarial"] === "node scripts/verify-a-adversarial-source-intelligence.mjs" &&
          existsSync(join(root, "scripts", "verify-a-adversarial-source-intelligence.mjs")) &&
          verifyAAdversarialSource.includes("AIBI-skills") &&
          verifyAAdversarialSource.includes("source-intelligence-experience.md") &&
          verifyAAdversarialSource.includes("ADV-CN-012-二手车") &&
          verifyAAdversarialSource.includes("ADV-CN-011-教培课包") &&
          verifyAAdversarialSource.includes("ADV-CN-013-跨境仓配") &&
          verifyAAdversarialSource.includes("ADV-LONG-021-私域会员储值履约") &&
          verifyAAdversarialSource.includes("ADV-ERP-072-旺店通订单明细利润物流差异") &&
          verifyAAdversarialSource.includes("ADV-ERP-072-聚水潭订单出库售后对账") &&
          verifyAAdversarialSource.includes("ADV-ERP-072-金蝶销售出库应收勾稽") &&
          verifyAAdversarialSource.includes("ADV-ERP-072-采购库存周转供应商履约") &&
          verifyAAdversarialSource.includes("batch-072-cn-erp-adversarial") &&
          verifyAAdversarialSource.includes("erp-adversarial-2026-07-05-b072") &&
          verifyAAdversarialSource.includes("erp-batch-manifest-available") &&
          verifyAAdversarialSource.includes("erp-long-cycle-summary-available") &&
          verifyAAdversarialSource.includes("experience-keeps-workspace-boundary") &&
          verifyAAdversarialSource.includes("adversarial-gap-boundary") &&
          verifyAAdversarialSource.includes("metricSqlExecutableCount < manifest?.metricSqlPlanCount") &&
          verifyAAdversarialSource.includes("output-stays-outside-project-a") &&
          readmeSource.includes("npm run verify"),
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
        ok: implementationStatusSource.includes("# AIBI-C Implementation Status") &&
          implementationStatusSource.includes("## Current Release Boundary") &&
          implementationStatusSource.includes("## Capability Status") &&
          implementationStatusSource.includes("## Known Limitations") &&
          implementationStatusSource.includes("## Architecture Ownership") &&
          implementationStatusSource.includes("npm run verify") &&
          implementationStatusSource.includes("python tools/bi_cli.py --json status") &&
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
          agentPendingChangesPanelSource.includes("data-testid=\"agent-draft-queue-empty\"") &&
          agentPendingChangesPanelSource.includes("data-testid=\"agent-current-draft-reject\"") &&
          agentPendingChangesPanelSource.includes("data-testid={`agent-draft-reject-${draft.action_key}`}") &&
          agentPendingChangesPanelSource.includes("onConfirmDryRun(draft.action_key)") &&
          agentPendingChangesPanelSource.includes("onConfirmAction(draft.action_key)") &&
          agentPendingChangesPanelSource.includes("onRejectAction(draft.action_key)") &&
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
          agentPendingChangesPanelSource.includes("data-testid=\"agent-draft-next-review\"") &&
          ["data", "dashboard", "model", "workspace"].every((key) => agentPanelSource.includes(`key: "${key}"`)) &&
          agentPendingChangesPanelSource.includes("Review impact before approval") &&
          stylesSource.includes(".agentDraftImpactSummary") &&
          stylesSource.includes(".agentDraftImpactGrid") &&
          stylesSource.includes(".agentDraftNextReview"),
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
