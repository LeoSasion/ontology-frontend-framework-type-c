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

export function DashboardCanvas({ dashboards, query, workbench, activeDashboardKey, onDashboardSelect, onAgentDraft, onAsk, onOpenEvidence, onDashboardOperation, onDashboardFilterOperation, onDashboardModulesSave, onBusinessDashboardOperation, onRelationshipSave, onDashboardWidgetOperation, onOpenBusinessStep }: DashboardCanvasProps) {
  const dashboardPages = Array.isArray(dashboards.dashboards) ? dashboards.dashboards : [];
  const dashboard = dashboardPages.find((item) => item.dashboard_key === activeDashboardKey) ?? dashboardPages[0] ?? {
    dashboard_key: "fallback",
    name: biText("未命名看板", "Untitled dashboard"),
    workspace_id: "default",
    default_table_key: query.query?.table ?? "",
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
  const editableTables = Array.isArray(workbench.tables) ? workbench.tables : [];
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
    widgets: dashboardWidgets,
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
    widgets: dashboardWidgets,
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
                zh="当前工作区没有可用数据表。完成导入后，可以让 AI 一次创建一个图表，也可以使用行业看板 Beta。"
                en="This workspace has no usable tables. After import, AI can create one chart at a time or use the industry dashboard beta."
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
        <DashboardBusinessTaskStrip
          busy={busy}
          dashboardName={dashboard.name}
          hasDashboard={dashboardPages.length > 0}
          onAsk={runDashboardAsk}
          onOpenEvidence={openDashboardEvidence}
        />

        {dashboardWidgets.length ? (
          <DashboardDeferredBoundary>
            <BiDashboardWidgetKit dashboard={dashboard} dashboards={dashboards} onOpenEvidence={onOpenEvidence} query={query} workbench={workbench} />
          </DashboardDeferredBoundary>
        ) : (
          <section className="bDashboardKit wide dashboardWidgetEmptyState" data-testid="dashboard-widget-empty-state">
            <strong><Bilingual zh="还没有图表" en="No charts yet" /></strong>
            <span><Bilingual zh="描述一个业务问题，AI 会先起草带口径和证据的单图。" en="Describe a business question and AI will draft one chart with scope and evidence." /></span>
          </section>
        )}

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
              canvasWidthMode={canvasWidthMode}
              dashboardFilters={dashboardFilters}
              dashboardKey={dashboard.dashboard_key}
              dashboardWidgets={dashboardWidgets}
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
    </section>
  );
}
