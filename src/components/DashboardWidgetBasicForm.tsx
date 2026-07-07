import type { Dispatch, SetStateAction } from "react";
import type { FieldConfig, SavedView, WorkbenchTable } from "../types";
import type { WidgetDraft } from "../dashboardCanvasWidgetModel";
import { biText } from "./Bilingual";

type DashboardWidgetBasicFormProps = {
  aggregations: string[];
  draftDimensions: FieldConfig[];
  draftMeasures: FieldConfig[];
  draftViews: SavedView[];
  editableTables: WorkbenchTable[];
  setWidgetDraft: Dispatch<SetStateAction<WidgetDraft>>;
  valueFormats: string[];
  widgetDraft: WidgetDraft;
  widgetTypes: string[];
};

export function DashboardWidgetBasicForm({
  aggregations,
  draftDimensions,
  draftMeasures,
  draftViews,
  editableTables,
  setWidgetDraft,
  valueFormats,
  widgetDraft,
  widgetTypes,
}: DashboardWidgetBasicFormProps) {
  return (
    <>
      <div className="widgetEditorGrid" data-testid="widget-basic-form">
        <label>
          <span>{biText("标题", "Title")}</span>
          <input value={widgetDraft.title} onChange={(event) => setWidgetDraft((draft) => ({ ...draft, title: event.target.value }))} />
        </label>
        <label>
          <span>{biText("呈现方式", "Display as")}</span>
          <select value={widgetDraft.type} onChange={(event) => setWidgetDraft((draft) => ({ ...draft, type: event.target.value }))}>
            {widgetTypes.map((type) => <option key={type} value={type}>{type}</option>)}
          </select>
        </label>
        <label>
          <span>{biText("数据范围", "Data scope")}</span>
          <select value={widgetDraft.table} onChange={(event) => setWidgetDraft((draft) => ({ ...draft, table: event.target.value, view: "" }))}>
            {editableTables.map((table) => <option key={table.table_key} value={table.table_key}>{table.display_name}</option>)}
          </select>
        </label>
        <label>
          <span>{biText("使用视图", "Saved view")}</span>
          <select value={widgetDraft.view} onChange={(event) => setWidgetDraft((draft) => ({ ...draft, view: event.target.value }))}>
            <option value="">{biText("直接使用数据源", "Use source directly")}</option>
            {draftViews.map((view) => <option key={view.view_key} value={view.view_key}>{view.name}</option>)}
          </select>
        </label>
        <label>
          <span>{biText("分组字段", "Group field")}</span>
          <select value={widgetDraft.dimension} onChange={(event) => setWidgetDraft((draft) => ({ ...draft, dimension: event.target.value }))}>
            <option value="">{biText("无", "None")}</option>
            {draftDimensions.map((field) => <option key={field.field_name} value={field.field_name}>{field.field_name}</option>)}
          </select>
        </label>
        <label>
          <span>{biText("计算字段", "Value field")}</span>
          <select value={widgetDraft.measure} onChange={(event) => setWidgetDraft((draft) => ({ ...draft, measure: event.target.value }))}>
            <option value="">{biText("记录数", "Row count")}</option>
            {draftMeasures.map((field) => <option key={field.field_name} value={field.field_name}>{field.field_name}</option>)}
          </select>
        </label>
        <label>
          <span>{biText("计算方式", "Calculation")}</span>
          <select value={widgetDraft.aggregation} onChange={(event) => setWidgetDraft((draft) => ({ ...draft, aggregation: event.target.value }))}>
            {aggregations.map((aggregation) => <option key={aggregation} value={aggregation}>{aggregation}</option>)}
          </select>
        </label>
        <label>
          <span>{biText("显示数量", "Show count")}</span>
          <input value={widgetDraft.topN} onChange={(event) => setWidgetDraft((draft) => ({ ...draft, topN: event.target.value }))} />
        </label>
        <label>
          <span>{biText("数字格式", "Number format")}</span>
          <select value={widgetDraft.valueFormat} onChange={(event) => setWidgetDraft((draft) => ({ ...draft, valueFormat: event.target.value }))}>
            {valueFormats.map((format) => <option key={format} value={format}>{format}</option>)}
          </select>
        </label>
        <label>
          <span>{biText("副标题", "Subtitle")}</span>
          <input value={widgetDraft.subtitle} onChange={(event) => setWidgetDraft((draft) => ({ ...draft, subtitle: event.target.value }))} />
        </label>
      </div>
      {widgetDraft.type === "text" ? (
        <label className="widgetTextEditor">
          <span>{biText("文本内容", "Text content")}</span>
          <textarea value={widgetDraft.textContent} onChange={(event) => setWidgetDraft((draft) => ({ ...draft, textContent: event.target.value }))} />
        </label>
      ) : null}
    </>
  );
}
