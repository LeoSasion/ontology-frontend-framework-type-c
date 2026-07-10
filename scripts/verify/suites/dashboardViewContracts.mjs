export function appendDashboardViewContractChecks(context) {
  const {
    checks,
    agentPromptGridSource,
    appSource,
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
    join,
    root,
    sourceWorkbenchActionPanelSource,
    sourceWorkbenchModelSource,
    sourceWorkbenchQueryFormulaPanelSource,
    sourceWorkbenchSource,
    stylesSource,
    topBarSource,
    viewAgentTaskStripSource,
    viewDashboardBridgePanelSource,
    viewSavedListPanelSource,
    viewWorkspaceModelSource,
    viewWorkspaceSource,
    viewWorkspaceStylesSource,
  } = context;
  checks.push(
    {
        label: "frontend-evidence-business-summary-first",
        ok: evidenceViewSource.includes("<EvidenceBusinessSummaryPanel") &&
          evidenceBusinessSummaryPanelSource.includes("data-testid=\"evidence-business-summary\"") &&
          evidenceBusinessSummaryPanelSource.includes("data-testid=\"evidence-business-summary-metrics\"") &&
          evidenceBusinessSummaryPanelSource.includes("data-testid=\"evidence-business-next-actions\"") &&
          evidenceViewSource.includes('from "../evidenceViewModel"') &&
          evidenceViewSource.includes("evidenceDecisionText") &&
          evidenceViewSource.includes("evidenceCoverageText") &&
          evidenceViewModelSource.includes("export function evidenceDecisionText") &&
          evidenceViewModelSource.includes("export function evidenceCoverageText") &&
          !evidenceViewSource.includes("function evidenceDecisionText") &&
          !evidenceViewSource.includes("function evidenceCoverageText") &&
          evidenceViewSource.includes("追溯依据") &&
          evidenceViewSource.includes("Trace basis"),
      },
    {
        label: "evidence-business-summary-panel-component-boundary",
        ok: existsSync(join(root, "src", "components", "EvidenceBusinessSummaryPanel.tsx")) &&
          evidenceViewSource.includes('import { EvidenceBusinessSummaryPanel } from "./EvidenceBusinessSummaryPanel"') &&
          evidenceViewSource.includes("<EvidenceBusinessSummaryPanel") &&
          !evidenceViewSource.includes('data-testid="evidence-business-summary"') &&
          evidenceBusinessSummaryPanelSource.includes("type EvidenceBusinessSummaryPanelProps") &&
          evidenceBusinessSummaryPanelSource.includes("businessMetrics: EvidenceBusinessMetric[]") &&
          evidenceBusinessSummaryPanelSource.includes("coverageText: string") &&
          evidenceBusinessSummaryPanelSource.includes("nextEvidenceActions.map") &&
          implementationStatusSource.includes("Evidence business summary panel component boundary"),
      },
    {
        label: "frontend-evidence-technical-details-collapsed",
        ok: evidenceViewSource.includes("证据摘要回执") &&
          evidenceViewSource.includes("可用问题") &&
          evidenceViewSource.includes("业务连接") &&
          evidenceViewSource.includes('data-testid="evidence-technical-ref-details"') &&
          evidenceViewSource.includes('data-testid="evidence-receipt-technical-details"') &&
          !evidenceViewSource.includes("<h3><Bilingual zh=\"Source Intelligence 回执\"") &&
          !evidenceViewSource.includes("可执行指标 SQL") &&
          sourceWorkbenchModelSource.includes("证据摘要生成失败") &&
          sourceWorkbenchModelSource.includes("证据摘要需要 CSV") &&
          sourceWorkbenchActionPanelSource.includes("当前证据摘要"),
      },
    {
        label: "frontend-evidence-agent-source-intelligence-business-first",
        ok: evidenceViewModelSource.includes("export function agentEvidenceBusinessLabel") &&
          evidenceViewModelSource.includes("export function agentEvidenceTechnicalText") &&
          evidenceViewModelSource.includes("export function actionBoundaryBusinessLabel") &&
          evidenceViewModelSource.includes("export function evidenceRunReadinessText") &&
          !evidenceViewSource.includes("function agentEvidenceBusinessLabel") &&
          !evidenceViewSource.includes("function agentEvidenceTechnicalText") &&
          !evidenceViewSource.includes("function actionBoundaryBusinessLabel") &&
          !evidenceViewSource.includes("function evidenceRunReadinessText") &&
          evidenceViewSource.includes('data-testid="evidence-agent-answer-business-refs"') &&
          evidenceViewSource.includes('data-testid="evidence-agent-answer-technical-refs"') &&
          evidenceViewSource.includes('data-testid={`evidence-action-boundary-technical-${action.id}`}') &&
          evidenceViewModelSource.includes("只读查询已完成") &&
          evidenceViewSource.includes("查看 Agent 证据原始引用") &&
          evidenceViewSource.includes("查看动作合同") &&
          evidenceViewModelSource.includes("可用于分析") &&
          !evidenceViewSource.includes('{String(ref.type ?? "evidence")} {String(ref.id ?? ref.metric_key ?? ref.engine ?? "")}') &&
          stylesSource.includes(".evidenceAgentTechnicalRefs") &&
          stylesSource.includes(".evidenceTechnicalList") &&
          stylesSource.includes(".evidenceActionBoundaryTechnical"),
      },
    {
        label: "frontend-evidence-action-receipt",
        ok: evidenceViewSource.includes("lastActionResult?: Record<string, unknown> | null") &&
          evidenceViewModelSource.includes("export function actionReceiptTitle") &&
          evidenceViewModelSource.includes("export function actionReceiptDetail") &&
          evidenceViewModelSource.includes("export function actionReceiptSubject") &&
          evidenceViewModelSource.includes("export function actionReceiptTechnical") &&
          !evidenceViewSource.includes("function actionReceiptTitle") &&
          !evidenceViewSource.includes("function actionReceiptDetail") &&
          !evidenceViewSource.includes("function actionReceiptSubject") &&
          !evidenceViewSource.includes("function actionReceiptTechnical") &&
          evidenceViewSource.includes('data-testid="evidence-action-receipt"') &&
          evidenceViewSource.includes('data-testid="evidence-action-receipt-title"') &&
          evidenceViewSource.includes('data-testid="evidence-action-receipt-detail"') &&
          evidenceViewSource.includes('data-testid="evidence-action-receipt-technical"') &&
          evidenceViewSource.includes("查看动作技术标识") &&
          evidenceViewSource.includes("最近动作回执") &&
          evidenceViewModelSource.includes("确认前不会写入") &&
          appSource.includes("lastActionResult={lastActionResult}") &&
          stylesSource.includes(".evidenceActionReceipt") &&
          stylesSource.includes(".evidenceActionTechnical"),
      },
    {
        label: "frontend-dashboard-beginner-editor",
        ok: dashboardBeginnerEditorSource.includes('data-testid="dashboard-beginner-editor"') &&
          dashboardBeginnerEditorSource.includes('data-testid="dashboard-beginner-recommend"') &&
          dashboardBeginnerEditorSource.includes('data-testid="dashboard-beginner-preview-template"') &&
          dashboardBeginnerEditorSource.includes('data-testid="dashboard-beginner-save"') &&
          dashboardBeginnerEditorSource.includes('data-testid="dashboard-beginner-agent"') &&
          dashboardAdvancedWidgetWorkbenchSource.includes('data-testid="dashboard-advanced-widget-workbench"') &&
          dashboardAdvancedWidgetWorkbenchSource.includes("Widget maintenance") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("组件维护") &&
          !dashboardCanvasSource.includes("高级组件工作台") &&
          dashboardCanvasSource.includes("onSaveDashboard={() => runModuleSave(true)}") &&
          dashboardCanvasSource.includes("runBusinessTemplate(\"business-template-preview\"") &&
          dashboardModuleSavePanelSource.includes("dashboardModuleSaveReceipt") &&
          dashboardModuleSavePanelSource.includes('data-testid="dashboard-modules-impact-summary"') &&
          dashboardModuleSavePanelSource.includes('data-testid="dashboard-modules-result-technical"') &&
          dashboardCanvasPlanModelSource.includes("确认前不会写入") &&
          dashboardCanvasPlanModelSource.includes("刷新后仍会保留") &&
          stylesSource.includes(".dashboardModuleSaveBusiness") &&
          stylesSource.includes(".dashboardModuleTechnicalDetails"),
      },
    {
        label: "frontend-dashboard-asset-source-strip",
        ok: dashboardOverviewStripSource.includes('data-testid="dashboard-asset-source-strip"') &&
          dashboardOverviewStripSource.includes('data-testid="dashboard-source-label"') &&
          dashboardOverviewStripSource.includes('data-testid="dashboard-source-facts"') &&
          dashboardCanvasSource.includes("dashboardCreatedBy={dashboardCreatedBy}") &&
          dashboardCanvasSource.includes("dashboardIsAgentManaged={dashboardIsAgentManaged}") &&
          dashboardCanvasReadinessModelSource.includes("Agent 生成") &&
          dashboardOverviewStripSource.includes("Editable asset, not a black-box result") &&
          dashboardCanvasReadinessModelSource.includes("agentManaged: readiness.isAgentManaged") &&
          dashboardCanvasReadinessModelSource.includes("可编辑；写入前确认") &&
          dashboardCanvasReadinessModelSource.includes("Editable; writes require approval") &&
          stylesSource.includes(".dashboardAssetSourceStrip") &&
          stylesSource.includes("width: fit-content") &&
          stylesSource.includes("justify-self: start") &&
          stylesSource.includes(".dashboardAssetSourceLead div > span") &&
          !stylesSource.includes(".dashboardAssetSourceLead span,") &&
          stylesSource.includes(".assetSourceBadge.agent"),
      },
    {
        label: "frontend-badge-fit-content-system",
        ok: dashboardBusinessTaskStripSource.includes('data-testid="dashboard-business-task-strip"') &&
          dashboardOverviewStripSource.includes('data-testid="dashboard-component-acceptance-strip"') &&
          stylesSource.includes("span.assetModeChip,") &&
          stylesSource.includes("span.storyMode,") &&
          stylesSource.includes("span.assetSourceBadge,") &&
          stylesSource.includes("span.statusBadge,") &&
          stylesSource.includes("span.settingsSandboxBadge,") &&
          stylesSource.includes("span.widgetCountBadge") &&
          stylesSource.includes("display: inline-flex;") &&
          stylesSource.includes("align-items: center;") &&
          stylesSource.includes("justify-content: center;") &&
          stylesSource.includes("justify-self: start;") &&
          stylesSource.includes("width: fit-content;") &&
          stylesSource.includes("white-space: nowrap;") &&
          implementationStatusSource.includes("Badge fit-content system"),
      },
    {
        label: "frontend-dashboard-business-task-strip",
        ok: dashboardBusinessTaskStripSource.includes('data-testid="dashboard-business-task-strip"') &&
          dashboardBusinessTaskStripSource.includes('data-testid="dashboard-task-explain"') &&
          dashboardBusinessTaskStripSource.includes('data-testid="dashboard-task-improve"') &&
          dashboardBusinessTaskStripSource.includes('data-testid="dashboard-task-evidence"') &&
          dashboardBusinessTaskStripSource.includes('data-testid="dashboard-task-template"') &&
          dashboardBusinessTaskStripSource.includes('data-testid="dashboard-beta-details"') &&
          dashboardCanvasSource.includes("function openDashboardEvidence") &&
          dashboardCanvasActionsSource.includes("async function runDashboardAsk") &&
          !dashboardCanvasSource.includes("function runDashboardAsk") &&
          dashboardBusinessTaskStripSource.includes("先说想看的一个图表") &&
          dashboardBusinessTaskStripSource.includes("高级：优化或行业看板 Beta") &&
          dashboardBusinessTaskStripSource.includes('className="advancedDetails compactAdvanced dashboardBetaDetails"') &&
          dashboardCanvasReadinessModelSource.includes("source: \"dashboard-summary\"") &&
          appSource.includes("onAsk={handleAgentCommandAsk}") &&
          stylesSource.includes(".dashboardBusinessTaskStrip") &&
          stylesSource.includes(".dashboardBusinessTasks") &&
          stylesSource.includes(".dashboardBetaDetails") &&
          stylesSource.includes("repeat(auto-fit, minmax(168px, 1fr))") &&
          !stylesSource.includes(".dashboardBusinessTasks span,\n.dashboardBusinessTasks strong,\n.dashboardBusinessTasks small {\n  display: block;\n  min-width: 0;\n  overflow-wrap: anywhere;"),
      },
    {
        label: "dashboard-business-task-strip-component-boundary",
        ok: existsSync(join(root, "src", "components", "DashboardBusinessTaskStrip.tsx")) &&
          dashboardCanvasSource.includes('from "./DashboardBusinessTaskStrip"') &&
          dashboardCanvasSource.includes("<DashboardBusinessTaskStrip") &&
          dashboardCanvasSource.includes("onAsk={runDashboardAsk}") &&
          dashboardCanvasSource.includes("onBusinessTemplate={runBusinessTemplate}") &&
          dashboardCanvasSource.includes("onOpenEvidence={openDashboardEvidence}") &&
          !dashboardCanvasSource.includes('data-testid="dashboard-task-explain"') &&
          !dashboardCanvasSource.includes('data-testid="dashboard-task-improve"') &&
          !dashboardCanvasSource.includes('data-testid="dashboard-task-template"') &&
          dashboardBusinessTaskStripSource.includes("export function DashboardBusinessTaskStrip(") &&
          dashboardBusinessTaskStripSource.includes("type DashboardBusinessTaskStripProps") &&
          dashboardBusinessTaskStripSource.includes("dashboardName: string") &&
          dashboardBusinessTaskStripSource.includes("defaultTableKey: string") &&
          dashboardBusinessTaskStripSource.includes("onBusinessTemplate") &&
          dashboardBusinessTaskStripSource.includes("经营模板") &&
          dashboardBusinessTaskStripSource.includes("Preview impact") &&
          implementationStatusSource.includes("Dashboard business task strip component boundary"),
      },
    {
        label: "dashboard-beginner-editor-component-boundary",
        ok: existsSync(join(root, "src", "components", "DashboardBeginnerEditor.tsx")) &&
          dashboardDeferredModulesSource.includes("export const DashboardBeginnerEditor = lazy") &&
          dashboardDeferredPanelsSource.includes('from "./DashboardBeginnerEditor"') &&
          dashboardCanvasSource.includes("<DashboardBeginnerEditor") &&
          dashboardCanvasSource.includes("healthItems={dashboardHealthItems}") &&
          dashboardCanvasSource.includes("sourceSwitchView={sourceSwitchView}") &&
          dashboardCanvasSource.includes("onSourceSwitch={runSourceSwitch}") &&
          dashboardCanvasSource.includes("onSourceSwitchTableChange={setSourceSwitchTableKey}") &&
          !dashboardCanvasSource.includes('data-testid="dashboard-beginner-editor"') &&
          !dashboardCanvasSource.includes('data-testid="dashboard-readiness-agent"') &&
          !dashboardCanvasSource.includes('data-testid="dashboard-source-switch-select"') &&
          !dashboardCanvasSource.includes("className=\"beginnerEditorActions\"") &&
          dashboardBeginnerEditorSource.includes("export function DashboardBeginnerEditor(") &&
          dashboardBeginnerEditorSource.includes("type DashboardBeginnerEditorProps") &&
          dashboardBeginnerEditorSource.includes("sourceSwitchView: DashboardSourceSwitchViewModel") &&
          dashboardBeginnerEditorSource.includes("healthItems: DashboardHealthItem[]") &&
          dashboardBeginnerEditorSource.includes("onSourceSwitchTableChange") &&
          dashboardBeginnerEditorSource.includes("Make the current dashboard usable first") &&
          dashboardBeginnerEditorSource.includes("Preview ready; writes still require confirmation") &&
          implementationStatusSource.includes("Dashboard beginner editor component boundary"),
      },
    {
        label: "dashboard-advanced-widget-workbench-component-boundary",
        ok: existsSync(join(root, "src", "components", "DashboardAdvancedWidgetWorkbench.tsx")) &&
          dashboardDeferredModulesSource.includes("export const DashboardAdvancedWidgetWorkbench = lazy") &&
          dashboardDeferredPanelsSource.includes('from "./DashboardAdvancedWidgetWorkbench"') &&
          dashboardCanvasSource.includes("<DashboardAdvancedWidgetWorkbench") &&
          dashboardCanvasSource.includes("dashboardWidgets={dashboardWidgets}") &&
          dashboardCanvasSource.includes("onWidgetOperation={runWidgetOperation}") &&
          dashboardCanvasSource.includes("onModuleSave={runModuleSave}") &&
          dashboardCanvasSource.includes("widgetSettingsPayload={widgetSettingsPayload}") &&
          !dashboardCanvasSource.includes('data-testid="dashboard-advanced-widget-workbench"') &&
          !dashboardCanvasSource.includes("className=\"widgetWorkbenchGrid\"") &&
          !dashboardCanvasSource.includes("<DashboardModuleSavePanel") &&
          !dashboardCanvasSource.includes("<DashboardWidgetEditorPanel") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("export function DashboardAdvancedWidgetWorkbench(") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("type DashboardAdvancedWidgetWorkbenchProps") &&
          dashboardAdvancedWidgetWorkbenchSource.includes('data-testid="dashboard-advanced-widget-workbench"') &&
          dashboardAdvancedWidgetWorkbenchSource.includes("className=\"widgetWorkbenchGrid\"") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardModuleSavePanel") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardBusinessTemplatePanel") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardWidgetRecommendationPanel") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardSavedViewPanel") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardRelationshipRecommendationPanel") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardRelationshipWidgetPanel") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardWidgetManagePanel") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardWidgetEditorPanel") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("buildWidgetToggleOptions(widgetDraft)") &&
          implementationStatusSource.includes("Dashboard advanced widget workbench component boundary"),
      },
    {
        label: "dashboard-module-save-panel-component-boundary",
        ok: existsSync(join(root, "src", "components", "DashboardModuleSavePanel.tsx")) &&
          dashboardAdvancedWidgetWorkbenchSource.includes('from "./DashboardModuleSavePanel"') &&
          dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardModuleSavePanel") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("onSave={onModuleSave}") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("onCanvasWidthModeChange={onCanvasWidthModeChange}") &&
          !dashboardCanvasSource.includes('from "./DashboardModuleSavePanel"') &&
          !dashboardCanvasSource.includes("<DashboardModuleSavePanel") &&
          !dashboardCanvasSource.includes('data-testid="dashboard-module-save-panel"') &&
          !dashboardCanvasSource.includes('data-testid="dashboard-modules-dry-run"') &&
          !dashboardCanvasSource.includes('data-testid="dashboard-modules-result-technical"') &&
          !dashboardCanvasSource.includes("dashboardModuleSaveReceipt(moduleSaveResult") &&
          dashboardModuleSavePanelSource.includes("export function DashboardModuleSavePanel(") &&
          dashboardModuleSavePanelSource.includes("type DashboardModuleSavePanelProps") &&
          dashboardModuleSavePanelSource.includes("dashboardModuleSaveReceipt(moduleSaveResult") &&
          dashboardModuleSavePanelSource.includes("onSave(false)") &&
          dashboardModuleSavePanelSource.includes("onSave(true)") &&
          dashboardModuleSavePanelSource.includes("View module receipt") &&
          implementationStatusSource.includes("Dashboard module save panel component boundary"),
      },
    {
        label: "dashboard-business-template-panel-component-boundary",
        ok: existsSync(join(root, "src", "components", "DashboardBusinessTemplatePanel.tsx")) &&
          dashboardAdvancedWidgetWorkbenchSource.includes('from "./DashboardBusinessTemplatePanel"') &&
          dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardBusinessTemplatePanel") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("onBusinessTemplate={onBusinessTemplate}") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("businessCategories={businessCategories}") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("businessTemplateCount={businessTemplateCount}") &&
          !dashboardCanvasSource.includes('from "./DashboardBusinessTemplatePanel"') &&
          !dashboardCanvasSource.includes("<DashboardBusinessTemplatePanel") &&
          !dashboardCanvasSource.includes('data-testid="business-template-panel"') &&
          !dashboardCanvasSource.includes('data-testid="business-dashboard-preview"') &&
          !dashboardCanvasSource.includes('data-testid="business-dashboard-overwrite"') &&
          !dashboardCanvasSource.includes("businessCategories.map((category)") &&
          dashboardBusinessTemplatePanelSource.includes("export function DashboardBusinessTemplatePanel(") &&
          dashboardBusinessTemplatePanelSource.includes("type DashboardBusinessTemplatePanelProps") &&
          dashboardBusinessTemplatePanelSource.includes("onBusinessTemplate(\"business-template-preview\"") &&
          dashboardBusinessTemplatePanelSource.includes("onBusinessTemplate(\"erp-unit-template-preview\"") &&
          dashboardBusinessTemplatePanelSource.includes('template: "erp-units"') &&
          dashboardBusinessTemplatePanelSource.includes('data-testid="erp-unit-dashboard-preview"') &&
          dashboardBusinessTemplatePanelSource.includes("onBusinessTemplate(\"business-template-create\"") &&
          dashboardBusinessTemplatePanelSource.includes("onBusinessTemplate(\"business-template-overwrite\"") &&
          dashboardBusinessTemplatePanelSource.includes("businessCategories.map((category)") &&
          dashboardBusinessTemplatePanelSource.includes('data-testid="erp-unit-selection-evidence"') &&
          dashboardBusinessTemplatePanelSource.includes('data-testid="erp-unit-selected-sources"') &&
          dashboardBusinessTemplatePanelSource.includes('data-testid="erp-unit-widget-preview"') &&
          dashboardBusinessTemplatePanelSource.includes('data-testid="erp-unit-omitted-hints"') &&
          dashboardBusinessTemplatePanelSource.includes('data-testid="erp-unit-missing-field-chips"') &&
          dashboardBusinessTemplatePanelSource.includes('data-testid="erp-unit-gap-unlocks"') &&
          dashboardBusinessTemplatePanelSource.includes('data-testid="erp-unit-category-coverage"') &&
          dashboardBusinessTemplatePanelSource.includes("collectNeededFieldsFromErpHints(allOmittedUnitHints)") &&
          dashboardBusinessTemplatePanelSource.includes("buildErpGapUnlocks(allOmittedUnitHints)") &&
          dashboardBusinessTemplatePanelSource.includes("neededFieldsForErpHint(hint)") &&
          erpUnitLibraryViewModelSource.includes("export function buildErpGapUnlocks") &&
          erpUnitLibraryViewModelSource.includes("export function collectNeededFieldsFromErpHints") &&
          dashboardBusinessTemplatePanelSource.includes("summarizeMatchedFields(widget.matchedFields)") &&
          dashboardBusinessTemplatePanelSource.includes("Business dashboard generated") &&
          implementationStatusSource.includes("Dashboard business template panel component boundary"),
      },
    {
        label: "dashboard-widget-recommendation-panel-component-boundary",
        ok: existsSync(join(root, "src", "components", "DashboardWidgetRecommendationPanel.tsx")) &&
          dashboardAdvancedWidgetWorkbenchSource.includes('from "./DashboardWidgetRecommendationPanel"') &&
          dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardWidgetRecommendationPanel") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("plannedWidgets={plannedWidgets}") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("onRecommendWidgets={() => onWidgetOperation(\"recommend-widgets\"") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("onAddRecommendedWidgets={() => onWidgetOperation(\"add-recommended\"") &&
          !dashboardCanvasSource.includes('from "./DashboardWidgetRecommendationPanel"') &&
          !dashboardCanvasSource.includes("<DashboardWidgetRecommendationPanel") &&
          !dashboardCanvasSource.includes('data-testid="widget-recommend-button"') &&
          !dashboardCanvasSource.includes('data-testid="widget-add-recommended-button"') &&
          !dashboardCanvasSource.includes("plannedWidgets.slice(0, 5).map") &&
          !dashboardCanvasSource.includes("点击推荐组件，系统会基于字段语义") &&
          dashboardWidgetRecommendationPanelSource.includes("export function DashboardWidgetRecommendationPanel(") &&
          dashboardWidgetRecommendationPanelSource.includes("type DashboardWidgetRecommendationPanelProps") &&
          dashboardWidgetRecommendationPanelSource.includes('data-testid="widget-recommendation-panel"') &&
          dashboardWidgetRecommendationPanelSource.includes('data-testid="widget-recommend-button"') &&
          dashboardWidgetRecommendationPanelSource.includes('data-testid="widget-add-recommended-button"') &&
          dashboardWidgetRecommendationPanelSource.includes("plannedWidgets.slice(0, 5).map") &&
          dashboardWidgetRecommendationPanelSource.includes("Use Recommend to generate widget candidates") &&
          implementationStatusSource.includes("Dashboard widget recommendation panel component boundary"),
      },
    {
        label: "dashboard-saved-view-panel-component-boundary",
        ok: existsSync(join(root, "src", "components", "DashboardSavedViewPanel.tsx")) &&
          dashboardAdvancedWidgetWorkbenchSource.includes('from "./DashboardSavedViewPanel"') &&
          dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardSavedViewPanel") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("views={usableViews}") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("selectedViewKey={selectedViewKey}") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("onSelectedViewChange={onSelectedViewChange}") &&
          dashboardAdvancedWidgetWorkbenchSource.includes('onWidgetOperation("add-view-widget"') &&
          !dashboardCanvasSource.includes('from "./DashboardSavedViewPanel"') &&
          !dashboardCanvasSource.includes("<DashboardSavedViewPanel") &&
          !dashboardCanvasSource.includes('runWidgetOperation("add-view-widget"') &&
          !dashboardCanvasSource.includes('data-testid="dashboard-saved-view-panel"') &&
          !dashboardCanvasSource.includes('data-testid="widget-add-view-button"') &&
          !dashboardCanvasSource.includes("usableViews.map((view)") &&
          !dashboardCanvasSource.includes("const selectedView = savedViews.find") &&
          dashboardSavedViewPanelSource.includes("export function DashboardSavedViewPanel(") &&
          dashboardSavedViewPanelSource.includes("type DashboardSavedViewPanelProps") &&
          dashboardSavedViewPanelSource.includes('data-testid="dashboard-saved-view-panel"') &&
          dashboardSavedViewPanelSource.includes('data-testid="widget-add-view-button"') &&
          dashboardSavedViewPanelSource.includes("views.map((view)") &&
          dashboardSavedViewPanelSource.includes("views.find((view)") &&
          dashboardSavedViewPanelSource.includes("Add view to dashboard") &&
          implementationStatusSource.includes("Dashboard saved view panel component boundary"),
      },
    {
        label: "dashboard-relationship-recommendation-panel-component-boundary",
        ok: existsSync(join(root, "src", "components", "DashboardRelationshipRecommendationPanel.tsx")) &&
          dashboardAdvancedWidgetWorkbenchSource.includes('from "./DashboardRelationshipRecommendationPanel"') &&
          dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardRelationshipRecommendationPanel") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("recommendations={relationshipRecommendations}") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("onRelationshipSave={onRelationshipSave}") &&
          !dashboardCanvasSource.includes('from "./DashboardRelationshipRecommendationPanel"') &&
          !dashboardCanvasSource.includes("<DashboardRelationshipRecommendationPanel") &&
          !dashboardCanvasSource.includes('data-testid="relationship-recommendation-panel"') &&
          !dashboardCanvasSource.includes("relationshipRecommendations.slice(0, 3).map") &&
          !dashboardCanvasSource.includes("relationshipPrimaryMapping(recommendation)") &&
          !dashboardCanvasSource.includes("relationshipRecommendationKey(recommendation)") &&
          !dashboardCanvasSource.includes("relationshipMappingLabel(recommendation)") &&
          dashboardRelationshipRecommendationPanelSource.includes("export function DashboardRelationshipRecommendationPanel(") &&
          dashboardRelationshipRecommendationPanelSource.includes("type DashboardRelationshipRecommendationPanelProps") &&
          dashboardRelationshipRecommendationPanelSource.includes('data-testid="relationship-recommendation-panel"') &&
          dashboardRelationshipRecommendationPanelSource.includes("recommendations.slice(0, 3).map") &&
          dashboardRelationshipRecommendationPanelSource.includes("relationshipPrimaryMapping(recommendation)") &&
          dashboardRelationshipRecommendationPanelSource.includes("relationshipRecommendationKey(recommendation)") &&
          dashboardRelationshipRecommendationPanelSource.includes("relationshipMappingLabel(recommendation)") &&
          dashboardRelationshipRecommendationPanelSource.includes("relationship-preview-${index}") &&
          dashboardRelationshipRecommendationPanelSource.includes("No recommended links yet") &&
          implementationStatusSource.includes("Dashboard relationship recommendation panel component boundary"),
      },
    {
        label: "dashboard-relationship-widget-panel-component-boundary",
        ok: existsSync(join(root, "src", "components", "DashboardRelationshipWidgetPanel.tsx")) &&
          dashboardAdvancedWidgetWorkbenchSource.includes('from "./DashboardRelationshipWidgetPanel"') &&
          dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardRelationshipWidgetPanel") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("relationships={savedRelationships}") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("selectedRelationship={selectedRelationship}") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("onSelectedRelationshipChange={onSelectedRelationshipChange}") &&
          dashboardAdvancedWidgetWorkbenchSource.includes('onWidgetOperation("add-relationship-widget"') &&
          !dashboardCanvasSource.includes('from "./DashboardRelationshipWidgetPanel"') &&
          !dashboardCanvasSource.includes("<DashboardRelationshipWidgetPanel") &&
          !dashboardCanvasSource.includes('runWidgetOperation("add-relationship-widget"') &&
          !dashboardCanvasSource.includes('data-testid="relationship-widget-panel"') &&
          !dashboardCanvasSource.includes('data-testid="widget-add-relationship-button"') &&
          !dashboardCanvasSource.includes("savedRelationships.map((relationship)") &&
          !dashboardCanvasSource.includes("selectedRelationship.left_table_key") &&
          dashboardRelationshipWidgetPanelSource.includes("export function DashboardRelationshipWidgetPanel(") &&
          dashboardRelationshipWidgetPanelSource.includes("type DashboardRelationshipWidgetPanelProps") &&
          dashboardRelationshipWidgetPanelSource.includes('data-testid="relationship-widget-panel"') &&
          dashboardRelationshipWidgetPanelSource.includes('data-testid="widget-add-relationship-button"') &&
          dashboardRelationshipWidgetPanelSource.includes("relationships.map((relationship)") &&
          dashboardRelationshipWidgetPanelSource.includes("onAddRelationshipWidget(selectedRelationship)") &&
          dashboardRelationshipWidgetPanelSource.includes("Create relation chart") &&
          implementationStatusSource.includes("Dashboard relationship widget panel component boundary"),
      },
    {
        label: "dashboard-widget-manage-panel-component-boundary",
        ok: existsSync(join(root, "src", "components", "DashboardWidgetManagePanel.tsx")) &&
          dashboardAdvancedWidgetWorkbenchSource.includes('from "./DashboardWidgetManagePanel"') &&
          dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardWidgetManagePanel") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("widgets={dashboardWidgets}") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("selectedWidgetKey={selectedWidget?.widget_key}") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("onSelectWidget={onSelectWidget}") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("onCopyPreview={(widget) => onWidgetOperation(`copy-preview-${widget.widget_key}`") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("onRemovePreview={(widget) => onWidgetOperation(`remove-preview-${widget.widget_key}`") &&
          !dashboardCanvasSource.includes('from "./DashboardWidgetManagePanel"') &&
          !dashboardCanvasSource.includes("<DashboardWidgetManagePanel") &&
          !dashboardCanvasSource.includes('data-testid={`widget-edit-${widget.widget_key}`}') &&
          !dashboardCanvasSource.includes('className="widgetActionPanel widgetListActionPanel"') &&
          dashboardWidgetManagePanelSource.includes("export function DashboardWidgetManagePanel(") &&
          dashboardWidgetManagePanelSource.includes("type DashboardWidgetManagePanelProps") &&
          dashboardWidgetManagePanelSource.includes('data-testid="dashboard-widget-manage-panel"') &&
          dashboardWidgetManagePanelSource.includes("widgets.map((widget)") &&
          dashboardWidgetManagePanelSource.includes('data-testid={`widget-edit-${widget.widget_key}`}') &&
          dashboardWidgetManagePanelSource.includes('data-testid={`widget-copy-preview-${widget.widget_key}`}') &&
          dashboardWidgetManagePanelSource.includes('data-testid={`widget-remove-preview-${widget.widget_key}`}') &&
          dashboardWidgetManagePanelSource.includes("onSelectWidget(widget.widget_key)") &&
          dashboardWidgetManagePanelSource.includes("onCopyPreview(widget)") &&
          dashboardWidgetManagePanelSource.includes("onRemovePreview(widget)") &&
          implementationStatusSource.includes("Dashboard widget manage panel component boundary"),
      },
    {
        label: "dashboard-widget-editor-panel-component-boundary",
        ok: existsSync(join(root, "src", "components", "DashboardWidgetEditorPanel.tsx")) &&
          dashboardAdvancedWidgetWorkbenchSource.includes('from "./DashboardWidgetEditorPanel"') &&
          dashboardAdvancedWidgetWorkbenchSource.includes("<DashboardWidgetEditorPanel") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("selectedWidget={selectedWidget}") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("widgetDraft={widgetDraft}") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("setWidgetDraft={setWidgetDraft}") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("onWidgetOperation={onWidgetOperation}") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("widgetSettingsPayload={widgetSettingsPayload}") &&
          dashboardAdvancedWidgetWorkbenchSource.includes("nextWidgetFilters={nextWidgetFilters}") &&
          !dashboardCanvasSource.includes('from "./DashboardWidgetEditorPanel"') &&
          !dashboardCanvasSource.includes("<DashboardWidgetEditorPanel") &&
          !dashboardCanvasSource.includes('data-testid="widget-editor-panel"') &&
          !dashboardCanvasSource.includes('data-testid="widget-style-panel"') &&
          !dashboardCanvasSource.includes('data-testid="widget-local-filter-panel"') &&
          !dashboardCanvasSource.includes('data-testid="widget-lifecycle-actions"') &&
          !dashboardCanvasSource.includes("setWidgetDraft((draft) => ({ ...draft, title: event.target.value }))") &&
          !dashboardCanvasSource.includes("widgetToggleOptions.map(({ key, label, checked })") &&
          dashboardWidgetEditorPanelSource.includes("export function DashboardWidgetEditorPanel(") &&
          dashboardWidgetEditorPanelSource.includes("type DashboardWidgetEditorPanelProps") &&
          dashboardWidgetEditorPanelSource.includes('from "./DashboardWidgetBasicForm"') &&
          dashboardWidgetEditorPanelSource.includes('from "./DashboardWidgetLifecyclePanel"') &&
          dashboardWidgetEditorPanelSource.includes('from "./DashboardWidgetLocalFilterPanel"') &&
          dashboardWidgetEditorPanelSource.includes('from "./DashboardWidgetStylePanel"') &&
          dashboardWidgetEditorPanelSource.includes('data-testid="widget-editor-panel"') &&
          dashboardWidgetEditorPanelSource.includes("<DashboardWidgetBasicForm") &&
          dashboardWidgetEditorPanelSource.includes("<DashboardWidgetLocalFilterPanel") &&
          dashboardWidgetEditorPanelSource.includes("<DashboardWidgetLifecyclePanel") &&
          dashboardWidgetEditorPanelSource.includes("<DashboardWidgetStylePanel") &&
          !dashboardWidgetEditorPanelSource.includes('data-testid="widget-local-filter-panel"') &&
          !dashboardWidgetEditorPanelSource.includes('data-testid="widget-lifecycle-actions"') &&
          !dashboardWidgetEditorPanelSource.includes("setWidgetDraft((draft) => ({ ...draft, title: event.target.value }))") &&
          !dashboardWidgetEditorPanelSource.includes("widgetToggleOptions.map(({ key, label, checked })") &&
          dashboardWidgetEditorPanelSource.includes("onWidgetOperation(\"set-widget-dry\", widgetSettingsPayload(false))") &&
          !dashboardWidgetEditorPanelSource.includes("onWidgetOperation(\"widget-filter-dry\"") &&
          !dashboardWidgetEditorPanelSource.includes("onWidgetOperation(\"copy-widget-dry\"") &&
          implementationStatusSource.includes("Dashboard widget editor panel component boundary"),
      },
    {
        label: "dashboard-widget-basic-form-component-boundary",
        ok: existsSync(join(root, "src", "components", "DashboardWidgetBasicForm.tsx")) &&
          dashboardWidgetEditorPanelSource.includes('from "./DashboardWidgetBasicForm"') &&
          dashboardWidgetEditorPanelSource.includes("<DashboardWidgetBasicForm") &&
          dashboardWidgetEditorPanelSource.includes("aggregations={aggregations}") &&
          dashboardWidgetEditorPanelSource.includes("draftDimensions={draftDimensions}") &&
          dashboardWidgetEditorPanelSource.includes("draftMeasures={draftMeasures}") &&
          dashboardWidgetEditorPanelSource.includes("draftViews={draftViews}") &&
          dashboardWidgetEditorPanelSource.includes("editableTables={editableTables}") &&
          dashboardWidgetEditorPanelSource.includes("valueFormats={valueFormats}") &&
          !dashboardWidgetEditorPanelSource.includes("widgetTypes.map((type)") &&
          !dashboardWidgetEditorPanelSource.includes("valueFormats.map((format)") &&
          !dashboardWidgetEditorPanelSource.includes("editableTables.map((table)") &&
          dashboardWidgetBasicFormSource.includes("export function DashboardWidgetBasicForm(") &&
          dashboardWidgetBasicFormSource.includes("type DashboardWidgetBasicFormProps") &&
          dashboardWidgetBasicFormSource.includes('data-testid="widget-basic-form"') &&
          dashboardWidgetBasicFormSource.includes("widgetTypes.map((type)") &&
          dashboardWidgetBasicFormSource.includes("editableTables.map((table)") &&
          dashboardWidgetBasicFormSource.includes("draftViews.map((view)") &&
          dashboardWidgetBasicFormSource.includes("draftDimensions.map((field)") &&
          dashboardWidgetBasicFormSource.includes("draftMeasures.map((field)") &&
          dashboardWidgetBasicFormSource.includes("valueFormats.map((format)") &&
          dashboardWidgetBasicFormSource.includes("widgetDraft.type === \"text\"") &&
          implementationStatusSource.includes("Dashboard widget basic form component boundary"),
      },
    {
        label: "dashboard-widget-style-panel-component-boundary",
        ok: existsSync(join(root, "src", "components", "DashboardWidgetStylePanel.tsx")) &&
          dashboardWidgetEditorPanelSource.includes('from "./DashboardWidgetStylePanel"') &&
          dashboardWidgetEditorPanelSource.includes("<DashboardWidgetStylePanel") &&
          dashboardWidgetEditorPanelSource.includes("colorPalettes={colorPalettes}") &&
          dashboardWidgetEditorPanelSource.includes("rankingModes={rankingModes}") &&
          dashboardWidgetEditorPanelSource.includes("slicerDisplays={slicerDisplays}") &&
          dashboardWidgetEditorPanelSource.includes("widgetToggleOptions={widgetToggleOptions}") &&
          !dashboardWidgetEditorPanelSource.includes("colorPalettes.map((palette)") &&
          !dashboardWidgetEditorPanelSource.includes("rankingModes.map((mode)") &&
          !dashboardWidgetEditorPanelSource.includes("slicerDisplays.map((display)") &&
          !dashboardWidgetEditorPanelSource.includes("widgetToggleOptions.map(({ key, label, checked })") &&
          dashboardWidgetStylePanelSource.includes("export function DashboardWidgetStylePanel(") &&
          dashboardWidgetStylePanelSource.includes("type DashboardWidgetStylePanelProps") &&
          dashboardWidgetStylePanelSource.includes('data-testid="widget-style-panel"') &&
          dashboardWidgetStylePanelSource.includes("colorPalettes.map((palette)") &&
          dashboardWidgetStylePanelSource.includes("rankingModes.map((mode)") &&
          dashboardWidgetStylePanelSource.includes("slicerDisplays.map((display)") &&
          dashboardWidgetStylePanelSource.includes("widgetToggleOptions.map(({ key, label, checked })") &&
          dashboardWidgetStylePanelSource.includes("Appearance and click behavior") &&
          implementationStatusSource.includes("Dashboard widget style panel component boundary"),
      },
    {
        label: "dashboard-widget-local-filter-panel-component-boundary",
        ok: existsSync(join(root, "src", "components", "DashboardWidgetLocalFilterPanel.tsx")) &&
          dashboardWidgetEditorPanelSource.includes('from "./DashboardWidgetLocalFilterPanel"') &&
          dashboardWidgetEditorPanelSource.includes("<DashboardWidgetLocalFilterPanel") &&
          dashboardWidgetEditorPanelSource.includes("draftFields={draftFields}") &&
          dashboardWidgetEditorPanelSource.includes("filterOperators={filterOperators}") &&
          dashboardWidgetEditorPanelSource.includes("nextWidgetFilters={nextWidgetFilters}") &&
          dashboardWidgetEditorPanelSource.includes("selectedWidgetKey={selectedWidget.widget_key}") &&
          dashboardWidgetEditorPanelSource.includes("widgetFilters={widgetFilters}") &&
          !dashboardWidgetEditorPanelSource.includes("widgetFilters.length ? widgetFilters.map") &&
          !dashboardWidgetEditorPanelSource.includes("filterOperators.map((operator)") &&
          !dashboardWidgetEditorPanelSource.includes("onWidgetOperation(\"widget-filter-dry\"") &&
          dashboardWidgetLocalFilterPanelSource.includes("export function DashboardWidgetLocalFilterPanel(") &&
          dashboardWidgetLocalFilterPanelSource.includes("type DashboardWidgetLocalFilterPanelProps") &&
          dashboardWidgetLocalFilterPanelSource.includes('data-testid="widget-local-filter-panel"') &&
          dashboardWidgetLocalFilterPanelSource.includes('data-testid="widget-filter-preview-button"') &&
          dashboardWidgetLocalFilterPanelSource.includes('data-testid="widget-filter-apply-button"') &&
          dashboardWidgetLocalFilterPanelSource.includes('data-testid="widget-filter-clear-button"') &&
          dashboardWidgetLocalFilterPanelSource.includes("widgetFilters.length ? widgetFilters.map") &&
          dashboardWidgetLocalFilterPanelSource.includes("filterOperators.map((operator)") &&
          dashboardWidgetLocalFilterPanelSource.includes("onWidgetOperation(\"widget-filter-dry\"") &&
          dashboardWidgetLocalFilterPanelSource.includes("onWidgetOperation(\"widget-filter-clear\"") &&
          implementationStatusSource.includes("Dashboard widget local filter panel component boundary"),
      },
    {
        label: "dashboard-widget-lifecycle-panel-component-boundary",
        ok: existsSync(join(root, "src", "components", "DashboardWidgetLifecyclePanel.tsx")) &&
          dashboardWidgetEditorPanelSource.includes('from "./DashboardWidgetLifecyclePanel"') &&
          dashboardWidgetEditorPanelSource.includes("<DashboardWidgetLifecyclePanel") &&
          dashboardWidgetEditorPanelSource.includes("dashboardKey={dashboardKey}") &&
          dashboardWidgetEditorPanelSource.includes("selectedWidget={selectedWidget}") &&
          !dashboardWidgetEditorPanelSource.includes('data-testid="widget-copy-preview-button"') &&
          !dashboardWidgetEditorPanelSource.includes("onWidgetOperation(\"copy-widget-dry\"") &&
          !dashboardWidgetEditorPanelSource.includes("onWidgetOperation(\"remove-widget-dry\"") &&
          dashboardWidgetLifecyclePanelSource.includes("export function DashboardWidgetLifecyclePanel(") &&
          dashboardWidgetLifecyclePanelSource.includes("type DashboardWidgetLifecyclePanelProps") &&
          dashboardWidgetLifecyclePanelSource.includes('data-testid="widget-lifecycle-actions"') &&
          dashboardWidgetLifecyclePanelSource.includes('data-testid="widget-copy-preview-button"') &&
          dashboardWidgetLifecyclePanelSource.includes('data-testid="widget-copy-confirm-button"') &&
          dashboardWidgetLifecyclePanelSource.includes('data-testid="widget-remove-preview-button"') &&
          dashboardWidgetLifecyclePanelSource.includes('data-testid="widget-remove-confirm-button"') &&
          dashboardWidgetLifecyclePanelSource.includes("onWidgetOperation(\"copy-widget-dry\"") &&
          dashboardWidgetLifecyclePanelSource.includes("onWidgetOperation(\"remove-widget-dry\"") &&
          dashboardWidgetLifecyclePanelSource.includes("Copy or delete widget") &&
          implementationStatusSource.includes("Dashboard widget lifecycle panel component boundary"),
      },
    {
        label: "dashboard-page-admin-panel-component-boundary",
        ok: existsSync(join(root, "src", "components", "DashboardPageAdminPanel.tsx")) &&
          dashboardDeferredModulesSource.includes("export const DashboardPageAdminPanel = lazy") &&
          dashboardDeferredPanelsSource.includes('from "./DashboardPageAdminPanel"') &&
          dashboardCanvasSource.includes("<DashboardPageAdminPanel") &&
          dashboardCanvasSource.includes("dashboardPages={dashboardPages}") &&
          dashboardCanvasSource.includes("draftName={draftName}") &&
          dashboardCanvasSource.includes("onDashboardOperation={runDashboardOperation}") &&
          dashboardCanvasSource.includes("onDashboardSelect={onDashboardSelect}") &&
          dashboardCanvasSource.includes("setDraftName={setDraftName}") &&
          !dashboardCanvasSource.includes('data-testid="dashboard-page-admin-panel"') &&
          !dashboardCanvasSource.includes('data-testid="dashboard-create-button"') &&
          !dashboardCanvasSource.includes("dashboardPages.map((item)") &&
          !dashboardCanvasSource.includes("setDraftName(event.target.value)") &&
          dashboardPageAdminPanelSource.includes("export function DashboardPageAdminPanel(") &&
          dashboardPageAdminPanelSource.includes("type DashboardPageAdminPanelProps") &&
          dashboardPageAdminPanelSource.includes('data-testid="dashboard-page-admin-panel"') &&
          dashboardPageAdminPanelSource.includes('data-testid="dashboard-create-button"') &&
          dashboardPageAdminPanelSource.includes('data-testid="dashboard-copy-button"') &&
          dashboardPageAdminPanelSource.includes('data-testid="dashboard-rename-button"') &&
          dashboardPageAdminPanelSource.includes('data-testid="dashboard-delete-button"') &&
          dashboardPageAdminPanelSource.includes("dashboardPages.map((item)") &&
          dashboardPageAdminPanelSource.includes("onDashboardSelect(item.dashboard_key)") &&
          dashboardPageAdminPanelSource.includes("onDashboardOperation(\"create\"") &&
          dashboardPageAdminPanelSource.includes("onDashboardOperation(\"delete\"") &&
          hasCssRule(stylesSource, ".dashboardOps", "display: grid;") &&
          stylesSource.includes("grid-template-columns: repeat(auto-fit, minmax(136px, 1fr));") &&
          stylesSource.includes(".dashboardOps > button") &&
          hasCssRule(stylesSource, ".businessTemplatePanel", "grid-column: span 2;") &&
          hasCssRule(stylesSource, ".businessTemplatePanel .dashboardOps", "grid-template-columns: repeat(3, minmax(0, 1fr));") &&
          hasCssRule(stylesSource, ".erpTemplateStats", "display: grid;", "grid-template-columns: repeat(auto-fit, minmax(104px, 1fr));") &&
          hasCssRule(stylesSource, ".erpOmittedUnitList", "display: grid;", "grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));") &&
          hasCssRule(stylesSource, ".erpUnitPreviewList", "display: grid;") &&
          hasCssRule(stylesSource, ".erpUnitPreviewList", "grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));") &&
          implementationStatusSource.includes("Dashboard page admin panel component boundary"),
      },
    {
        label: "dashboard-contract-boundary-panel-component-boundary",
        ok: existsSync(join(root, "src", "components", "DashboardContractBoundaryPanel.tsx")) &&
          dashboardDeferredModulesSource.includes("export const DashboardContractBoundaryPanel = lazy") &&
          dashboardDeferredPanelsSource.includes('from "./DashboardContractBoundaryPanel"') &&
          dashboardCanvasSource.includes("<DashboardContractBoundaryPanel") &&
          dashboardCanvasSource.includes("widgets={dashboardWidgets}") &&
          !dashboardCanvasSource.includes('data-testid="dashboard-contract-boundary-panel"') &&
          !dashboardCanvasSource.includes("查看组件合同和动作边界") &&
          !dashboardCanvasSource.includes("dashboardWidgets.map((widget)") &&
          !dashboardCanvasSource.includes("Object.entries(widget.config ?? {})") &&
          dashboardContractBoundaryPanelSource.includes("export function DashboardContractBoundaryPanel(") &&
          dashboardContractBoundaryPanelSource.includes("type DashboardContractBoundaryPanelProps") &&
          dashboardContractBoundaryPanelSource.includes('data-testid="dashboard-contract-boundary-panel"') &&
          dashboardContractBoundaryPanelSource.includes("Widget contract") &&
          dashboardContractBoundaryPanelSource.includes("Action boundary") &&
          dashboardContractBoundaryPanelSource.includes("widgets.map((widget)") &&
          dashboardContractBoundaryPanelSource.includes("Object.entries(widget.config ?? {})") &&
          dashboardContractBoundaryPanelSource.includes("Import commit, dashboard write, relationship save, index creation, external sync.") &&
          implementationStatusSource.includes("Dashboard contract boundary panel component boundary"),
      },
    {
        label: "dashboard-overview-strip-component-boundary",
        ok: existsSync(join(root, "src", "components", "DashboardOverviewStrip.tsx")) &&
          dashboardCanvasSource.includes('from "./DashboardOverviewStrip"') &&
          dashboardCanvasSource.includes("<DashboardOverviewStrip") &&
          dashboardCanvasSource.includes("dashboardSummary={dashboardSummary}") &&
          dashboardCanvasSource.includes("dashboardWidgetsCount={dashboardWidgets.length}") &&
          dashboardCanvasSource.includes("dashboardFiltersCount={dashboardFilters.length}") &&
          dashboardCanvasSource.includes("onOpenEvidence={openDashboardEvidence}") &&
          !dashboardCanvasSource.includes('data-testid="dashboard-asset-source-strip"') &&
          !dashboardCanvasSource.includes('className="dashboardStoryStrip wide"') &&
          !dashboardCanvasSource.includes('data-testid="dashboard-component-acceptance-strip"') &&
          !dashboardCanvasSource.includes("dashboardAcceptanceItems.map") &&
          dashboardOverviewStripSource.includes("export function DashboardOverviewStrip(") &&
          dashboardOverviewStripSource.includes("type DashboardOverviewStripProps") &&
          dashboardOverviewStripSource.includes('data-testid="dashboard-asset-source-strip"') &&
          dashboardOverviewStripSource.includes('className="dashboardStoryStrip wide"') &&
          dashboardOverviewStripSource.includes('data-testid="dashboard-component-acceptance-strip"') &&
          dashboardOverviewStripSource.includes("dashboardAcceptanceItems.map") &&
          dashboardOverviewStripSource.includes("dashboardSummary.topRow") &&
          dashboardOverviewStripSource.includes("dashboardWidgetsCount") &&
          dashboardOverviewStripSource.includes("dashboardFiltersCount") &&
          implementationStatusSource.includes("Dashboard overview strip component boundary"),
      },
    {
        label: "dashboard-filter-workbench-component-boundary",
        ok: existsSync(join(root, "src", "components", "DashboardFilterWorkbench.tsx")) &&
          dashboardDeferredModulesSource.includes("export const DashboardFilterWorkbench = lazy") &&
          dashboardDeferredPanelsSource.includes('from "./DashboardFilterWorkbench"') &&
          dashboardDeferredPanelsSource.includes('import "./dashboardDeferred.css"') &&
          dashboardDeferredStylesSource.includes(".dashboardFilterWorkbench {") &&
          dashboardDeferredStylesSource.includes(".widgetFilterActions {") &&
          !globalStylesSource.includes(".dashboardFilterWorkbench {") &&
          dashboardCanvasSource.includes("<DashboardFilterWorkbench") &&
          dashboardCanvasSource.includes("dashboardFilters={dashboardFilters}") &&
          dashboardCanvasSource.includes("availableFilterFields={availableFilterFields}") &&
          dashboardCanvasSource.includes("onFilterOperation={runFilterOperation}") &&
          dashboardCanvasSource.includes("operatorLabel={operatorLabel}") &&
          !dashboardCanvasSource.includes('className="dashboardFilterWorkbench wide"') &&
          !dashboardCanvasSource.includes('data-testid="dashboard-filter-preview"') &&
          !dashboardCanvasSource.includes("dashboardFilters.length ? dashboardFilters.map") &&
          !dashboardCanvasSource.includes("runFilterOperation(`remove-${filter.id}`") &&
          dashboardFilterWorkbenchSource.includes("export function DashboardFilterWorkbench(") &&
          dashboardFilterWorkbenchSource.includes("type DashboardFilterWorkbenchProps") &&
          dashboardFilterWorkbenchSource.includes('className="dashboardFilterWorkbench wide"') &&
          dashboardFilterWorkbenchSource.includes('data-testid="dashboard-filter-preview"') &&
          dashboardFilterWorkbenchSource.includes('data-testid="dashboard-filter-apply"') &&
          dashboardFilterWorkbenchSource.includes('data-testid="dashboard-filter-clear"') &&
          dashboardFilterWorkbenchSource.includes('data-testid="dashboard-filter-stale-preview"') &&
          dashboardFilterWorkbenchSource.includes('data-testid="dashboard-filter-stale-remove"') &&
          dashboardFilterWorkbenchSource.includes("dashboardFilters.length ? dashboardFilters.map") &&
          dashboardFilterWorkbenchSource.includes("filterOperators.map((operator)") &&
          dashboardFilterWorkbenchSource.includes("onFilterOperation(`remove-${filter.id}`") &&
          implementationStatusSource.includes("Dashboard filter workbench component boundary"),
      },
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
          dashboardCanvasSourceSwitchModelSource.includes("defaultTableKey: sourceSwitchTableKey") &&
          implementationStatusSource.includes("Dashboard canvas source switch model boundary"),
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
          dashboardCanvasSourceSwitchViewModelSource.includes("全局筛选需清理") &&
          implementationStatusSource.includes("Dashboard canvas source switch view model boundary"),
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
          dashboardCanvasReadinessModelSource.includes("source-intelligence:") &&
          implementationStatusSource.includes("Dashboard canvas readiness model boundary"),
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
          dashboardCanvasPlanModelSource.includes("刷新后仍会保留") &&
          implementationStatusSource.includes("Dashboard canvas plan model boundary"),
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
          dashboardCanvasSourceSwitchModelSource.includes("normalizeWidgetFilters(config.filters)") &&
          implementationStatusSource.includes("Dashboard canvas filter model boundary"),
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
          dashboardCanvasFieldModelSource.includes("draftFields.filter(isDashboardMeasureField)") &&
          implementationStatusSource.includes("Dashboard canvas field model boundary"),
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
          dashboardCanvasStateSource.includes("dashboardWidgets.find((widget) => widget.widget_key === selectedWidgetKey)") &&
          dashboardCanvasStateSource.includes("const fieldModel = useMemo(() => buildDashboardCanvasFieldModel({") &&
          dashboardCanvasStateSource.includes("setDraftName(dashboard?.name ?? \"\")") &&
          dashboardCanvasStateSource.includes("setCanvasWidthMode(dashboard.layout?.canvasWidthMode === \"center\" ? \"center\" : \"stretch\")") &&
          dashboardCanvasStateSource.includes("setSourceSwitchTableKey(dashboard.default_table_key)") &&
          dashboardCanvasStateSource.includes("setFilterField((current)") &&
          dashboardCanvasStateSource.includes("setSelectedViewKey((current)") &&
          dashboardCanvasStateSource.includes("setSelectedRelationshipKey((current)") &&
          dashboardCanvasStateSource.includes("setSelectedWidgetKey((current)") &&
          dashboardCanvasStateSource.includes("setWidgetDraft(widgetDraftFromWidget(widget))") &&
          dashboardCanvasStateSource.includes("setWidgetFilterField((current)") &&
          implementationStatusSource.includes("Dashboard canvas state hook boundary"),
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
          dashboardCanvasActionsSource.includes("return {") &&
          implementationStatusSource.includes("Dashboard canvas actions hook boundary"),
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
          dashboardCanvasActionsSource.includes("runVoidAction(label, () => onAsk(prompt))") &&
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
          dashboardCanvasActionRunnerSource.includes("setBusy(null)") &&
          implementationStatusSource.includes("Dashboard canvas action runner boundary"),
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
          dashboardCanvasRelationshipModelSource.includes("limit: 20") &&
          implementationStatusSource.includes("Dashboard canvas relationship model boundary"),
      },
    {
        label: "frontend-saved-view-evidence-click-path",
        ok: viewWorkspaceSource.includes('data-testid="view-evidence-button"') &&
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
          viewWorkspaceStylesSource.includes(".viewAgentTaskStrip {") &&
          !globalStylesSource.includes(".viewWorkspaceGrid {") &&
          stylesSource.includes(".viewAgentTaskStrip") &&
          stylesSource.includes(".agentPromptGrid") &&
          stylesSource.includes(".viewAgentTaskStrip .agentPromptGrid button"),
      },
    {
        label: "view-agent-task-strip-component-boundary",
        ok: existsSync(join(root, "src", "components", "ViewAgentTaskStrip.tsx")) &&
          viewWorkspaceSource.includes('import { ViewAgentTaskStrip } from "./ViewAgentTaskStrip"') &&
          viewWorkspaceSource.includes("<ViewAgentTaskStrip") &&
          !viewWorkspaceSource.includes('data-testid="view-agent-task-strip"') &&
          viewAgentTaskStripSource.includes("type ViewAgentTaskStripProps") &&
          viewAgentTaskStripSource.includes("viewAgentPrompts: ViewAgentPrompt[]") &&
          viewAgentTaskStripSource.includes("不用导出表格，直接问当前视图") &&
          viewAgentTaskStripSource.includes('itemTestIdPrefix="view-agent-prompt"') &&
          implementationStatusSource.includes("View Agent task strip component boundary"),
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
          viewWorkspaceSource.includes('import { ViewDashboardBridgePanel } from "./ViewDashboardBridgePanel"') &&
          viewWorkspaceSource.includes("<ViewDashboardBridgePanel") &&
          !viewWorkspaceSource.includes('data-testid="view-dashboard-bridge"') &&
          viewDashboardBridgePanelSource.includes("type ViewDashboardBridgePanelProps") &&
          viewDashboardBridgePanelSource.includes("bridgeSteps: ViewBridgeStep[]") &&
          viewDashboardBridgePanelSource.includes("openViewEvidence: () => void") &&
          viewDashboardBridgePanelSource.includes("viewCanFeedDashboard: boolean") &&
          viewDashboardBridgePanelSource.includes('data-testid="view-bridge-agent-widget"') &&
          implementationStatusSource.includes("View dashboard bridge panel component boundary"),
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
          viewSavedListPanelSource.includes("view.filterCount ?? viewFilters(view).length") &&
          implementationStatusSource.includes("View saved list panel component boundary"),
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
