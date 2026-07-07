import type { Dispatch, SetStateAction } from "react";
import type { DashboardFilterRule, DashboardWidget, FieldConfig, SavedView, WorkbenchTable } from "../types";
import type { DashboardWidgetOperationOptions } from "../dashboardCanvasContracts";
import type { WidgetDraft } from "../dashboardCanvasWidgetModel";
import type { WidgetToggleOption } from "../dashboardCanvasEditorOptions";
import { Bilingual, biText } from "./Bilingual";
import { DashboardWidgetBasicForm } from "./DashboardWidgetBasicForm";
import { DashboardWidgetLifecyclePanel } from "./DashboardWidgetLifecyclePanel";
import { DashboardWidgetLocalFilterPanel } from "./DashboardWidgetLocalFilterPanel";
import { DashboardWidgetStylePanel } from "./DashboardWidgetStylePanel";
import { Icon } from "./Icons";

type DashboardWidgetEditorPanelProps = {
  aggregations: string[];
  busy: string | null;
  colorPalettes: string[];
  dashboardKey: string;
  draftDimensions: FieldConfig[];
  draftFields: FieldConfig[];
  draftMeasures: FieldConfig[];
  draftViews: SavedView[];
  editableTables: WorkbenchTable[];
  filterOperators: readonly string[];
  nextWidgetFilters: Array<{ field: string; operator: string; value?: string }>;
  onWidgetOperation: (label: string, options: DashboardWidgetOperationOptions) => Promise<void>;
  operatorLabel: (operator: string) => string;
  rankingModes: string[];
  selectedWidget: DashboardWidget | undefined;
  setWidgetDraft: Dispatch<SetStateAction<WidgetDraft>>;
  setWidgetFilterField: (field: string) => void;
  setWidgetFilterOperator: (operator: string) => void;
  setWidgetFilterValue: (value: string) => void;
  slicerDisplays: string[];
  valueFormats: string[];
  widgetDraft: WidgetDraft;
  widgetFilterField: string;
  widgetFilterOperator: string;
  widgetFilterValue: string;
  widgetFilters: DashboardFilterRule[];
  widgetSettingsPayload: (confirm: boolean) => DashboardWidgetOperationOptions;
  widgetToggleOptions: WidgetToggleOption[];
  widgetTypes: string[];
};

export function DashboardWidgetEditorPanel({
  aggregations,
  busy,
  colorPalettes,
  dashboardKey,
  draftDimensions,
  draftFields,
  draftMeasures,
  draftViews,
  editableTables,
  filterOperators,
  nextWidgetFilters,
  onWidgetOperation,
  operatorLabel,
  rankingModes,
  selectedWidget,
  setWidgetDraft,
  setWidgetFilterField,
  setWidgetFilterOperator,
  setWidgetFilterValue,
  slicerDisplays,
  valueFormats,
  widgetDraft,
  widgetFilterField,
  widgetFilterOperator,
  widgetFilterValue,
  widgetFilters,
  widgetSettingsPayload,
  widgetToggleOptions,
  widgetTypes,
}: DashboardWidgetEditorPanelProps) {
  return (
    <article className="widgetEditorPanel" data-testid="widget-editor-panel">
      <div className="tileHeader compact">
        <h3><Bilingual zh="调整组件呈现" en="Tune widget presentation" /></h3>
        <span>{selectedWidget?.widget_key ?? biText("未选择", "None selected")}</span>
      </div>
      {selectedWidget ? (
        <>
          <DashboardWidgetBasicForm
            aggregations={aggregations}
            draftDimensions={draftDimensions}
            draftMeasures={draftMeasures}
            draftViews={draftViews}
            editableTables={editableTables}
            setWidgetDraft={setWidgetDraft}
            valueFormats={valueFormats}
            widgetDraft={widgetDraft}
            widgetTypes={widgetTypes}
          />
          <DashboardWidgetStylePanel
            colorPalettes={colorPalettes}
            rankingModes={rankingModes}
            setWidgetDraft={setWidgetDraft}
            slicerDisplays={slicerDisplays}
            widgetDraft={widgetDraft}
            widgetToggleOptions={widgetToggleOptions}
          />
          <DashboardWidgetLocalFilterPanel
            busy={busy}
            draftFields={draftFields}
            filterOperators={filterOperators}
            nextWidgetFilters={nextWidgetFilters}
            onWidgetOperation={onWidgetOperation}
            operatorLabel={operatorLabel}
            selectedWidgetKey={selectedWidget.widget_key}
            setWidgetFilterField={setWidgetFilterField}
            setWidgetFilterOperator={setWidgetFilterOperator}
            setWidgetFilterValue={setWidgetFilterValue}
            widgetFilterField={widgetFilterField}
            widgetFilterOperator={widgetFilterOperator}
            widgetFilterValue={widgetFilterValue}
            widgetFilters={widgetFilters}
          />
          <div className="widgetEditorActions">
            <button
              className="secondaryButton"
              data-testid="widget-settings-preview-button"
              disabled={busy === "set-widget-dry"}
              onClick={() => onWidgetOperation("set-widget-dry", widgetSettingsPayload(false))}
              type="button"
            >
              <Icon name="evidence" />
              <Bilingual zh="预览改动" en="Preview changes" />
            </button>
            <button
              className="primaryButton"
              data-testid="widget-settings-apply-button"
              disabled={busy === "set-widget"}
              onClick={() => onWidgetOperation("set-widget", widgetSettingsPayload(true))}
              type="button"
            >
              <Icon name="check" />
              <Bilingual zh="应用改动" en="Apply changes" />
            </button>
          </div>
          <DashboardWidgetLifecyclePanel
            busy={busy}
            dashboardKey={dashboardKey}
            onWidgetOperation={onWidgetOperation}
            selectedWidget={selectedWidget}
          />
        </>
      ) : (
        <p className="emptyFilterHint"><Bilingual zh="当前看板暂无组件。先添加推荐组件或把视图加入看板。" en="No widget on this dashboard yet. Add recommendations or place a saved view first." /></p>
      )}
    </article>
  );
}
