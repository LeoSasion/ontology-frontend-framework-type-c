import type { Dispatch, SetStateAction } from "react";
import type {
  DashboardFilterRule,
  DashboardWidget,
  FieldConfig,
  RelationshipRecommendation,
  RelationshipRecord,
  SavedView,
  WorkbenchTable,
} from "../types";
import type { BusinessDashboardOptions, DashboardWidgetOperationOptions } from "../dashboardCanvasContracts";
import {
  buildWidgetToggleOptions,
  colorPalettes,
  rankingModes,
  slicerDisplays,
  valueFormats,
  widgetTypes,
} from "../dashboardCanvasEditorOptions";
import type { DashboardCanvasWidthMode, WidgetDraft } from "../dashboardCanvasWidgetModel";
import { Bilingual, biText } from "./Bilingual";
import { DashboardBusinessTemplatePanel } from "./DashboardBusinessTemplatePanel";
import { DashboardModuleSavePanel } from "./DashboardModuleSavePanel";
import { DashboardRelationshipRecommendationPanel } from "./DashboardRelationshipRecommendationPanel";
import { DashboardRelationshipWidgetPanel } from "./DashboardRelationshipWidgetPanel";
import { DashboardSavedViewPanel } from "./DashboardSavedViewPanel";
import { DashboardWidgetEditorPanel } from "./DashboardWidgetEditorPanel";
import { DashboardWidgetManagePanel } from "./DashboardWidgetManagePanel";
import { DashboardWidgetRecommendationPanel } from "./DashboardWidgetRecommendationPanel";

type DashboardAdvancedWidgetWorkbenchProps = {
  busy: string | null;
  businessCategories: Array<Record<string, unknown>>;
  businessDraft: Record<string, unknown> | null;
  businessTemplateCount: number;
  erpPackEnabled: boolean;
  canvasWidthMode: DashboardCanvasWidthMode;
  dashboardFilters: DashboardFilterRule[];
  dashboardKey: string;
  dashboardWidgets: DashboardWidget[];
  defaultTableKey: string;
  draftDimensions: FieldConfig[];
  draftFields: FieldConfig[];
  draftMeasures: FieldConfig[];
  draftViews: SavedView[];
  editableTables: WorkbenchTable[];
  filterOperators: readonly string[];
  moduleSaveResult: Record<string, unknown> | null;
  nextWidgetFilters: Array<{ field: string; operator: string; value?: string }>;
  onBusinessTemplate: (label: string, options: BusinessDashboardOptions) => void;
  onCanvasWidthModeChange: (mode: DashboardCanvasWidthMode) => void;
  onModuleSave: (confirm: boolean) => void;
  onMoveWidget: (widgetKey: string, targetIndex: number) => void;
  onRelationshipSave: (label: string, recommendation: RelationshipRecommendation, confirm: boolean) => void;
  onSelectedRelationshipChange: (relationshipKey: string) => void;
  onSelectedViewChange: (viewKey: string) => void;
  onSelectWidget: (widgetKey: string) => void;
  onWidgetOperation: (label: string, options: DashboardWidgetOperationOptions) => Promise<void>;
  operatorLabel: (operator: string) => string;
  plannedWidgets: Array<Record<string, unknown>>;
  relationshipRecommendations: RelationshipRecommendation[];
  safeAggregations: string[];
  savedDashboardKey?: unknown;
  savedDashboardModules?: unknown;
  savedRelationships: RelationshipRecord[];
  savedTemplateCount?: unknown;
  selectedRelationship: RelationshipRecord | undefined;
  selectedRelationshipKey: string;
  selectedViewKey: string;
  selectedWidget: DashboardWidget | undefined;
  setWidgetDraft: Dispatch<SetStateAction<WidgetDraft>>;
  setWidgetFilterField: (field: string) => void;
  setWidgetFilterOperator: (operator: string) => void;
  setWidgetFilterValue: (value: string) => void;
  usableViews: SavedView[];
  widgetDraft: WidgetDraft;
  widgetFilterField: string;
  widgetFilterOperator: string;
  widgetFilterValue: string;
  widgetFilters: DashboardFilterRule[];
  widgetSettingsPayload: (confirm: boolean) => DashboardWidgetOperationOptions;
  widgetPlanRequiresConfirmation: boolean;
};

export function DashboardAdvancedWidgetWorkbench({
  busy,
  businessCategories,
  businessDraft,
  businessTemplateCount,
  erpPackEnabled,
  canvasWidthMode,
  dashboardFilters,
  dashboardKey,
  dashboardWidgets,
  defaultTableKey,
  draftDimensions,
  draftFields,
  draftMeasures,
  draftViews,
  editableTables,
  filterOperators,
  moduleSaveResult,
  nextWidgetFilters,
  onBusinessTemplate,
  onCanvasWidthModeChange,
  onModuleSave,
  onMoveWidget,
  onRelationshipSave,
  onSelectedRelationshipChange,
  onSelectedViewChange,
  onSelectWidget,
  onWidgetOperation,
  operatorLabel,
  plannedWidgets,
  relationshipRecommendations,
  safeAggregations,
  savedDashboardKey,
  savedDashboardModules,
  savedRelationships,
  savedTemplateCount,
  selectedRelationship,
  selectedRelationshipKey,
  selectedViewKey,
  selectedWidget,
  setWidgetDraft,
  setWidgetFilterField,
  setWidgetFilterOperator,
  setWidgetFilterValue,
  usableViews,
  widgetDraft,
  widgetFilterField,
  widgetFilterOperator,
  widgetFilterValue,
  widgetFilters,
  widgetSettingsPayload,
  widgetPlanRequiresConfirmation,
}: DashboardAdvancedWidgetWorkbenchProps) {
  const aggregations = safeAggregations.length ? safeAggregations : ["count", "sum", "avg", "min", "max"];
  const widgetToggleOptions = buildWidgetToggleOptions(widgetDraft);

  return (
    <details className="advancedDetails dashboardWidgetWorkbench wide" data-testid="dashboard-advanced-widget-workbench">
      <summary>{biText("组件维护：推荐、样式、筛选和安全删除", "Widget maintenance: recommendations, style, filters, and safe deletion")}</summary>
      <div className="filterWorkbenchHeader">
        <div>
          <span className="storyMode"><Bilingual zh="组件工作台" en="Widget workbench" /></span>
          <h3><Bilingual zh="推荐、加入、复制和删除组件" en="Recommend, add, copy, and remove widgets" /></h3>
        </div>
        <span className="widgetCountBadge">{biText(`${dashboardWidgets.length} 个组件`, `${dashboardWidgets.length} widgets`)}</span>
      </div>

      <DashboardModuleSavePanel
        busy={busy}
        canvasWidthMode={canvasWidthMode}
        filterCount={dashboardFilters.length}
        moduleSaveResult={moduleSaveResult}
        onCanvasWidthModeChange={onCanvasWidthModeChange}
        onSave={onModuleSave}
        requiresConfirmation={widgetPlanRequiresConfirmation}
        widgetCount={dashboardWidgets.length}
      />

      <div className="widgetWorkbenchGrid">
        <DashboardBusinessTemplatePanel
          busy={busy}
          businessCategories={businessCategories}
          businessDraft={businessDraft}
          businessTemplateCount={businessTemplateCount}
          erpPackEnabled={erpPackEnabled}
          dashboardKey={dashboardKey}
          defaultTableKey={defaultTableKey}
          onBusinessTemplate={onBusinessTemplate}
          savedDashboardKey={savedDashboardKey}
          savedDashboardModules={savedDashboardModules}
          savedTemplateCount={savedTemplateCount}
        />

        <DashboardWidgetRecommendationPanel
          busy={busy}
          dashboardKey={dashboardKey}
          defaultTableKey={defaultTableKey}
          onAddRecommendedWidgets={() => onWidgetOperation("add-recommended", { op: "addRecommended", dashboardKey, table: defaultTableKey, limit: 4, confirm: true })}
          onRecommendWidgets={() => onWidgetOperation("recommend-widgets", { op: "recommend", table: defaultTableKey, limit: 7 })}
          plannedWidgets={plannedWidgets}
        />

        <DashboardSavedViewPanel
          busy={busy}
          onAddView={(view) => onWidgetOperation("add-view-widget", {
            op: "add",
            dashboardKey,
            type: "table",
            table: view.table_key,
            view: view.view_key,
            title: `${view.name} ${biText("明细", "Detail")}`,
            confirm: true,
          })}
          onSelectedViewChange={onSelectedViewChange}
          selectedViewKey={selectedViewKey}
          views={usableViews}
        />

        <DashboardRelationshipRecommendationPanel
          busy={busy}
          onRelationshipSave={onRelationshipSave}
          recommendations={relationshipRecommendations}
        />

        <DashboardRelationshipWidgetPanel
          busy={busy}
          onAddRelationshipWidget={(relationship) => onWidgetOperation("add-relationship-widget", {
            op: "addRelationship",
            dashboardKey,
            relationship: relationship.relation_key,
            type: "bar",
            title: `${relationship.name} ${biText("排行", "Ranking")}`,
            group: relationship.left_field,
            aggregation: "count",
            topN: 12,
            confirm: true,
          })}
          onSelectedRelationshipChange={onSelectedRelationshipChange}
          relationships={savedRelationships}
          selectedRelationship={selectedRelationship}
          selectedRelationshipKey={selectedRelationshipKey}
        />

        <DashboardWidgetManagePanel
          busy={busy}
          dashboardKey={dashboardKey}
          onCopyPreview={(widget) => onWidgetOperation(`copy-preview-${widget.widget_key}`, { op: "copy", widgetKey: widget.widget_key, dashboardKey, confirm: false })}
          onMoveWidget={onMoveWidget}
          onRemovePreview={(widget) => onWidgetOperation(`remove-preview-${widget.widget_key}`, { op: "remove", widgetKey: widget.widget_key, confirm: false })}
          onSelectWidget={onSelectWidget}
          selectedWidgetKey={selectedWidget?.widget_key}
          widgets={dashboardWidgets}
        />
      </div>

      <DashboardWidgetEditorPanel
        aggregations={aggregations}
        busy={busy}
        colorPalettes={colorPalettes}
        dashboardKey={dashboardKey}
        draftDimensions={draftDimensions}
        draftFields={draftFields}
        draftMeasures={draftMeasures}
        draftViews={draftViews}
        editableTables={editableTables}
        filterOperators={filterOperators}
        nextWidgetFilters={nextWidgetFilters}
        onWidgetOperation={onWidgetOperation}
        operatorLabel={operatorLabel}
        rankingModes={rankingModes}
        selectedWidget={selectedWidget}
        setWidgetDraft={setWidgetDraft}
        setWidgetFilterField={setWidgetFilterField}
        setWidgetFilterOperator={setWidgetFilterOperator}
        setWidgetFilterValue={setWidgetFilterValue}
        slicerDisplays={slicerDisplays}
        valueFormats={valueFormats}
        widgetDraft={widgetDraft}
        widgetFilterField={widgetFilterField}
        widgetFilterOperator={widgetFilterOperator}
        widgetFilterValue={widgetFilterValue}
        widgetFilters={widgetFilters}
        widgetSettingsPayload={widgetSettingsPayload}
        widgetToggleOptions={widgetToggleOptions}
        widgetTypes={widgetTypes}
      />
    </details>
  );
}
