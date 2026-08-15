import type { DashboardPayload, EvidenceFocus, QueryResult, WorkbenchPayload } from "../types";
import type { BusinessPathStepKey } from "../businessPathModel";
import type {
  BusinessDashboardOptions,
  DashboardFilterOperationOptions,
  DashboardModuleSaveOptions,
  DashboardOperationOptions,
  DashboardWidgetOperationOptions,
  RelationshipSaveOptions,
} from "../dashboardCanvasContracts";
import { filterOperators, normalizeDashboardFilters, operatorLabel } from "../dashboardCanvasFilterModel";
import { buildDashboardCanvasViewModel } from "../dashboardCanvasViewModel";
import { buildProductActivation } from "../productActivationModel";
import { useDashboardCanvasActions } from "../useDashboardCanvasActions";
import { useDashboardCanvasState } from "../useDashboardCanvasState";
import { BiDashboardWidgetKit } from "../dashboardWidgetModules";
import { ObjectMissingState } from "./ObjectMissingState";
import {
  DashboardAdvancedWidgetWorkbench,
  DashboardBeginnerEditor,
  DashboardContractBoundaryPanel,
  DashboardDeferredBoundary,
  DashboardFilterWorkbench,
  DashboardPageAdminPanel,
} from "../dashboardDeferredModules";
import { DashboardBusinessTaskStrip } from "./DashboardBusinessTaskStrip";
import { DashboardOverviewStrip } from "./DashboardOverviewStrip";
import { Bilingual, biText, translateName } from "./Bilingual";
import { ProductActivationPanel } from "./ProductActivationPanel";

type DashboardCanvasProps = {
  dashboards: DashboardPayload;
  focusedTableKey?: string;
  query: QueryResult;
  workbench: WorkbenchPayload;
  activeDashboardKey: string;
  onDashboardSelect: (dashboardKey: string) => void;
  onAgentDraft: () => void;
  onAsk: (prompt: string) => Promise<void>;
  onOpenEvidence: (focus: EvidenceFocus) => void;
  onDashboardOperation: (options: DashboardOperationOptions) => Promise<void>;
  onDashboardFilterOperation: (options: DashboardFilterOperationOptions) => Promise<void>;
  onDashboardModulesSave: (options: DashboardModuleSaveOptions) => Promise<Record<string, unknown>>;
  onBusinessDashboardOperation: (options: BusinessDashboardOptions) => Promise<Record<string, unknown>>;
  onRelationshipSave: (options: RelationshipSaveOptions) => Promise<Record<string, unknown>>;
  onDashboardWidgetOperation: (options: DashboardWidgetOperationOptions) => Promise<Record<string, unknown>>;
  onOpenBusinessStep: (step: BusinessPathStepKey) => void;
};

export function DashboardCanvas({ dashboards, focusedTableKey, query, workbench, activeDashboardKey, onDashboardSelect, onAgentDraft, onAsk, onOpenEvidence, onDashboardOperation, onDashboardFilterOperation, onDashboardModulesSave, onBusinessDashboardOperation, onRelationshipSave, onDashboardWidgetOperation, onOpenBusinessStep }: DashboardCanvasProps) {
  const dashboardPages = Array.isArray(dashboards.dashboards) ? dashboards.dashboards : [];
  const requestedDashboard = dashboardPages.find((item) => item.dashboard_key === activeDashboardKey);
  const requestedDashboardMissing = activeDashboardKey !== "default" && !requestedDashboard;
  const dashboard = requestedDashboard ?? dashboardPages[0] ?? {
    dashboard_key: "fallback",
    name: biText("尚未创建看板", "No dashboard yet"),
    workspace_id: "default",
    default_table_key: focusedTableKey || query.query?.table || workbench.tables[0]?.table_key || "",
    created_by: "fallback",
    agent_managed: 0,
    layout: { version: 1 },
    widgets: [],
  };
  const dashboardWidgets = Array.isArray(dashboard.widgets) ? dashboard.widgets : [];
  const dashboardFilters = normalizeDashboardFilters(dashboard.layout);
  const activation = buildProductActivation({ workbench, dashboardCount: dashboardPages.length });
  const savedViews = Array.isArray(workbench.savedViews) ? workbench.savedViews : [];
  const savedRelationships = Array.isArray(workbench.relationships) ? workbench.relationships : [];
  const relationshipRecommendations = Array.isArray(workbench.relationshipRecommendations) ? workbench.relationshipRecommendations : [];
  const erpPackEnabled = Boolean(workbench.domainPacks?.enabledDomainPacks.some((pack) => pack.packId === "erp-units"));
  const editableTables = Array.isArray(workbench.tables) ? workbench.tables : [];
  const activeTable = editableTables.find((table) => table.table_key === (focusedTableKey || dashboard.default_table_key))
    ?? editableTables.find((table) => table.table_key === dashboard.default_table_key)
    ?? editableTables[0];
  const {
    advancedEditorMounted,
    availableFilterFields,
    canvasWidthMode,
    contractPanelMounted,
    draftFields,
    draftMeasures,
    draftDimensions,
    draftName,
    draftViews,
    filterField,
    filterOperator,
    filterValue,
    guidedEditorMounted,
    moveWidget,
    orderedWidgets,
    selectedRelationship,
    selectedRelationshipKey,
    selectedViewKey,
    selectedWidget,
    setCanvasWidthMode,
    setAdvancedEditorMounted,
    setContractPanelMounted,
    setDraftName,
    setFilterField,
    setFilterOperator,
    setFilterValue,
    setGuidedEditorMounted,
    setSelectedRelationshipKey,
    setSelectedViewKey,
    setSelectedWidgetKey,
    setSourceSwitchTableKey,
    setWidgetDraft,
    setWidgetFilterField,
    setWidgetFilterOperator,
    setWidgetFilterValue,
    sourceSwitchTable,
    sourceSwitchTableKey,
    usableViews,
    widgetDraft,
    widgetFilterField,
    widgetFilterOperator,
    widgetFilterValue,
    widgetFilters,
  } = useDashboardCanvasState({
    dashboard,
    dashboardWidgets,
    editableTables,
    fields: workbench.fields,
    savedViews,
    savedRelationships,
  });
  const {
    busy,
    runBusinessTemplate,
    runDashboardAsk,
    runDashboardOperation,
    runFilterOperation,
    runModuleSave,
    runRelationshipSave,
    runSourceSwitch,
    runWidgetOperation,
    widgetPlan,
    widgetSettingsPayload,
  } = useDashboardCanvasActions({
    canvasWidthMode,
    dashboard,
    draftName,
    fields: workbench.fields,
    filters: dashboardFilters,
    onAsk,
    onBusinessDashboardOperation,
    onDashboardFilterOperation,
    onDashboardModulesSave,
    onDashboardOperation,
    onDashboardWidgetOperation,
    onRelationshipSave,
    selectedWidgetKey: selectedWidget?.widget_key,
    sourceSwitchTableKey,
    widgetDraft,
    widgets: orderedWidgets,
  });

  const {
    businessCategories,
    businessDraft,
    businessTemplateCount,
    dashboardCreatedBy,
    dashboardEditBoundary,
    dashboardEvidenceFocus,
    dashboardHealthDetail,
    dashboardHealthItems,
    dashboardHealthTitle,
    dashboardHealthTone,
    dashboardIsAgentManaged,
    dashboardSourceLabel,
    dashboardSummary,
    latestRun,
    moduleSaveResult,
    nextWidgetFilters,
    plannedWidgets,
    sourceSwitchChanged,
    sourceSwitchView,
  } = buildDashboardCanvasViewModel({
    dashboard,
    filters: dashboardFilters,
    query,
    sourceSwitchTableKey,
    widgetFilterField,
    widgetFilterOperator,
    widgetFilterValue,
    widgetFilters,
    widgetPlan,
    widgets: orderedWidgets,
    workbench,
  });

  function openDashboardEvidence() {
    onOpenEvidence(dashboardEvidenceFocus);
  }

  if (editableTables.length === 0) {
    return (
      <section className="mainPanel" aria-labelledby="dashboard-title">
        <div className="panelHeader">
          <div>
            <p className="kicker">{biText("结果", "Results")}</p>
            <h2 id="dashboard-title">
              <Bilingual zh="先导入数据，才能生成图表" en="Import data before creating charts" />
            </h2>
            <p className="panelLead">
              <Bilingual
                zh="当前工作区没有可用数据表。完成导入后，可以让 AI 创建单图或基于证据生成分析看板草案。"
                en="This workspace has no usable tables. After import, AI can create one chart or draft an evidence-backed analysis dashboard."
              />
            </p>
          </div>
        </div>
        <ProductActivationPanel
          activation={activation}
          currentStep="chart"
          onOpenStep={onOpenBusinessStep}
          testId="dashboard-product-activation"
          title={biText("先接入数据，再生成图表", "Connect data before creating charts")}
        />
      </section>
    );
  }

  if (requestedDashboardMissing) {
    return (
      <ObjectMissingState
        badge={biText("看板不可用", "Dashboard unavailable")}
        detail={biText(`地址中的看板「${activeDashboardKey}」没有被替换成其他看板。请选择一个现有看板，或创建新看板。`, `The dashboard “${activeDashboardKey}” in the URL was not replaced with another board. Choose an existing board or create a new one.`)}
        testId="dashboard-not-found"
        title={biText("这个看板不存在或已被删除", "This dashboard is missing or was deleted")}
      >
        {dashboardPages[0] ? <button className="primaryButton" onClick={() => onDashboardSelect(dashboardPages[0].dashboard_key)} type="button">{biText("打开现有看板", "Open an existing dashboard")}</button> : null}
        <button className="secondaryButton" onClick={onAgentDraft} type="button">{biText("创建看板草案", "Create a dashboard draft")}</button>
      </ObjectMissingState>
    );
  }

  return (
    <section className="mainPanel" aria-labelledby="dashboard-title">
      <div className="panelHeader">
        <div>
          <p className="kicker">{biText("结果", "Results")}</p>
          <h2 id="dashboard-title">
            <Bilingual {...translateName(dashboard.name)} />
          </h2>
        </div>
      </div>

      <div className="dashboardGrid">
        {dashboardWidgets.length ? (
          <DashboardDeferredBoundary>
            <BiDashboardWidgetKit dashboard={{ ...dashboard, widgets: orderedWidgets }} dashboards={dashboards} onOpenEvidence={onOpenEvidence} query={query} workbench={workbench} />
          </DashboardDeferredBoundary>
        ) : (
          <section className="bDashboardKit wide dashboardWidgetEmptyState" data-testid="dashboard-widget-empty-state">
            <strong><Bilingual zh="还没有图表" en="No charts yet" /></strong>
            <span><Bilingual zh="描述一个业务问题，AI 会先起草带口径和证据的单图。" en="Describe a business question and AI will draft one chart with scope and evidence." /></span>
          </section>
        )}

        <DashboardBusinessTaskStrip
          busy={busy}
          compact={dashboardWidgets.length > 0}
          dashboardName={dashboard.name}
          hasDashboard={dashboardPages.length > 0}
          tableKey={activeTable?.table_key ?? ""}
          tableName={activeTable?.display_name ?? ""}
          onAsk={runDashboardAsk}
          onOpenEvidence={openDashboardEvidence}
        />

        <details className="progressiveDetails dashboardProgressiveDetails dashboardMoreDetails" data-testid="dashboard-more-details">
          <summary><Bilingual zh="更多设置与证据" en="More settings and evidence" /></summary>
          <div className="progressiveDetailsBody single dashboardMoreBody">
            <button className="miniButton" data-testid="dashboard-more-evidence" onClick={openDashboardEvidence} type="button">
              <Bilingual zh="查看当前看板证据" en="Review current dashboard evidence" />
            </button>

        <details className="progressiveDetails dashboardProgressiveDetails dashboardResultContextDetails" data-testid="dashboard-result-context-details">
          <summary><Bilingual zh="查看结果来源、口径和验收信息" en="View result source, scope, and acceptance" /></summary>
          <div className="progressiveDetailsBody single">
            <DashboardOverviewStrip
              dashboardCreatedBy={dashboardCreatedBy}
              dashboardEditBoundary={dashboardEditBoundary}
              dashboardFiltersCount={dashboardFilters.length}
              dashboardIsAgentManaged={dashboardIsAgentManaged}
              dashboardSourceLabel={dashboardSourceLabel}
              dashboardSummary={dashboardSummary}
              dashboardWidgetsCount={dashboardWidgets.length}
              onOpenEvidence={openDashboardEvidence}
            />
          </div>
        </details>

        <details
          className="progressiveDetails dashboardProgressiveDetails"
          data-testid="dashboard-guided-edit-details"
          onToggle={(event) => {
            if (event.currentTarget.open) setGuidedEditorMounted(true);
          }}
        >
          <summary><Bilingual zh="调整图表、筛选和数据来源" en="Adjust charts, filters, and data source" /></summary>
          {guidedEditorMounted ? (
          <DashboardDeferredBoundary>
            <div className="progressiveDetailsBody dashboardProgressiveGrid">
            <DashboardFilterWorkbench
              availableFilterFields={availableFilterFields}
              busy={busy}
              dashboardFilters={dashboardFilters}
              dashboardKey={dashboard.dashboard_key}
              filterField={filterField}
              filterOperator={filterOperator}
              filterOperators={filterOperators}
              filterValue={filterValue}
              onFilterFieldChange={setFilterField}
              onFilterOperation={runFilterOperation}
              onFilterOperatorChange={setFilterOperator}
              onFilterValueChange={setFilterValue}
              operatorLabel={operatorLabel}
            />

            <DashboardBeginnerEditor
              busy={busy}
              defaultTableKey={dashboard.default_table_key}
              editableTables={editableTables}
              filters={dashboardFilters}
              hasModuleSaveResult={Boolean(moduleSaveResult)}
              hasPendingPreview={widgetPlan?.requiresConfirmation === true}
              healthDetail={dashboardHealthDetail}
              healthItems={dashboardHealthItems}
              healthTitle={dashboardHealthTitle}
              healthTone={dashboardHealthTone}
              latestRun={latestRun}
              onAgentDraft={onAgentDraft}
              onPreviewTemplate={() => runBusinessTemplate("business-template-preview", { op: "draft", table: dashboard.default_table_key, limit: 10 })}
              onRecommendWidgets={() => runWidgetOperation("recommend-widgets", { op: "recommend", table: dashboard.default_table_key, limit: 7 })}
              onSaveDashboard={() => runModuleSave(true)}
              onSourceSwitch={runSourceSwitch}
              onSourceSwitchTableChange={setSourceSwitchTableKey}
              plannedWidgetCount={plannedWidgets.length}
              selectedWidget={selectedWidget}
              sourceSwitchChanged={sourceSwitchChanged}
              sourceSwitchTable={sourceSwitchTable}
              sourceSwitchTableKey={sourceSwitchTableKey}
              sourceSwitchView={sourceSwitchView}
              widgets={dashboardWidgets}
            />
            </div>
          </DashboardDeferredBoundary>
          ) : null}
        </details>

        <details
          className="progressiveDetails dashboardProgressiveDetails"
          data-testid="dashboard-advanced-edit-details"
          onToggle={(event) => {
            if (event.currentTarget.open) setAdvancedEditorMounted(true);
          }}
        >
          <summary><Bilingual zh="高级组件和页面管理" en="Advanced widgets and page management" /></summary>
          {advancedEditorMounted ? (
          <DashboardDeferredBoundary>
            <div className="progressiveDetailsBody dashboardProgressiveGrid">
            <DashboardAdvancedWidgetWorkbench
              busy={busy}
              businessCategories={businessCategories}
              businessDraft={businessDraft}
              businessTemplateCount={businessTemplateCount}
              erpPackEnabled={erpPackEnabled}
              canvasWidthMode={canvasWidthMode}
              dashboardFilters={dashboardFilters}
              dashboardKey={dashboard.dashboard_key}
              dashboardWidgets={orderedWidgets}
              defaultTableKey={dashboard.default_table_key}
              draftDimensions={draftDimensions}
              draftFields={draftFields}
              draftMeasures={draftMeasures}
              draftViews={draftViews}
              editableTables={editableTables}
              filterOperators={filterOperators}
              moduleSaveResult={moduleSaveResult}
              nextWidgetFilters={nextWidgetFilters}
              onBusinessTemplate={runBusinessTemplate}
              onCanvasWidthModeChange={setCanvasWidthMode}
              onModuleSave={runModuleSave}
              onMoveWidget={moveWidget}
              onRelationshipSave={runRelationshipSave}
              onSelectedRelationshipChange={setSelectedRelationshipKey}
              onSelectedViewChange={setSelectedViewKey}
              onSelectWidget={setSelectedWidgetKey}
              onWidgetOperation={runWidgetOperation}
              operatorLabel={operatorLabel}
              plannedWidgets={plannedWidgets}
              relationshipRecommendations={relationshipRecommendations}
              safeAggregations={workbench.safeAggregations}
              savedDashboardKey={widgetPlan?.savedDashboardKey}
              savedDashboardModules={widgetPlan?.savedDashboardModules}
              savedRelationships={savedRelationships}
              savedTemplateCount={widgetPlan?.templateCount}
              selectedRelationship={selectedRelationship}
              selectedRelationshipKey={selectedRelationshipKey}
              selectedViewKey={selectedViewKey}
              selectedWidget={selectedWidget}
              setWidgetDraft={setWidgetDraft}
              setWidgetFilterField={setWidgetFilterField}
              setWidgetFilterOperator={setWidgetFilterOperator}
              setWidgetFilterValue={setWidgetFilterValue}
              usableViews={usableViews}
              widgetDraft={widgetDraft}
              widgetFilterField={widgetFilterField}
              widgetFilterOperator={widgetFilterOperator}
              widgetFilterValue={widgetFilterValue}
              widgetFilters={widgetFilters}
              widgetPlanRequiresConfirmation={widgetPlan?.requiresConfirmation === true}
              widgetSettingsPayload={widgetSettingsPayload}
            />

            <DashboardPageAdminPanel
              busy={busy}
              dashboard={dashboard}
              dashboardPages={dashboardPages}
              draftName={draftName}
              onDashboardOperation={runDashboardOperation}
              onDashboardSelect={onDashboardSelect}
              setDraftName={setDraftName}
            />
            </div>
          </DashboardDeferredBoundary>
          ) : null}
        </details>

        <details
          className="progressiveDetails dashboardProgressiveDetails"
          data-testid="dashboard-contract-details"
          onToggle={(event) => {
            if (event.currentTarget.open) setContractPanelMounted(true);
          }}
        >
          <summary><Bilingual zh="查看动作边界和组件合同" en="View action boundaries and widget contracts" /></summary>
          {contractPanelMounted ? (
            <DashboardDeferredBoundary>
              <div className="progressiveDetailsBody single">
                <DashboardContractBoundaryPanel widgets={dashboardWidgets} />
              </div>
            </DashboardDeferredBoundary>
          ) : null}
        </details>
          </div>
        </details>
      </div>
    </section>
  );
}
