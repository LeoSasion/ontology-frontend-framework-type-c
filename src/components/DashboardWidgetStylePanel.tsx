import type { Dispatch, SetStateAction } from "react";
import type { WidgetDraft } from "../dashboardCanvasWidgetModel";
import type { WidgetToggleOption } from "../dashboardCanvasEditorOptions";
import { biText } from "./Bilingual";

type DashboardWidgetStylePanelProps = {
  colorPalettes: string[];
  rankingModes: string[];
  setWidgetDraft: Dispatch<SetStateAction<WidgetDraft>>;
  slicerDisplays: string[];
  widgetDraft: WidgetDraft;
  widgetToggleOptions: WidgetToggleOption[];
};

export function DashboardWidgetStylePanel({
  colorPalettes,
  rankingModes,
  setWidgetDraft,
  slicerDisplays,
  widgetDraft,
  widgetToggleOptions,
}: DashboardWidgetStylePanelProps) {
  return (
    <details className="widgetStylePanel" data-testid="widget-style-panel">
      <summary>{biText("外观和点击行为", "Appearance and click behavior")}</summary>
      <div className="widgetEditorGrid styleGrid">
        <label>
          <span>{biText("配色", "Palette")}</span>
          <select value={widgetDraft.colorPalette} onChange={(event) => setWidgetDraft((draft) => ({ ...draft, colorPalette: event.target.value }))}>
            {colorPalettes.map((palette) => <option key={palette} value={palette}>{palette}</option>)}
          </select>
        </label>
        <label>
          <span>{biText("排序依据", "Sort by")}</span>
          <select value={widgetDraft.sortBy} onChange={(event) => setWidgetDraft((draft) => ({ ...draft, sortBy: event.target.value }))}>
            <option value="metric">{biText("指标值", "Metric")}</option>
            <option value="dimension">{biText("维度名", "Dimension")}</option>
          </select>
        </label>
        <label>
          <span>{biText("排序方向", "Sort direction")}</span>
          <select value={widgetDraft.sortDirection} onChange={(event) => setWidgetDraft((draft) => ({ ...draft, sortDirection: event.target.value }))}>
            <option value="desc">{biText("降序", "Descending")}</option>
            <option value="asc">{biText("升序", "Ascending")}</option>
          </select>
        </label>
        <label>
          <span>{biText("小数位", "Decimals")}</span>
          <input value={widgetDraft.decimalPlaces} onChange={(event) => setWidgetDraft((draft) => ({ ...draft, decimalPlaces: event.target.value }))} />
        </label>
        <label>
          <span>{biText("表格行数", "Table rows")}</span>
          <input value={widgetDraft.tableColumnLimit} onChange={(event) => setWidgetDraft((draft) => ({ ...draft, tableColumnLimit: event.target.value }))} />
        </label>
        <label>
          <span>{biText("柱图方向", "Bar orientation")}</span>
          <select value={widgetDraft.barOrientation} onChange={(event) => setWidgetDraft((draft) => ({ ...draft, barOrientation: event.target.value }))}>
            <option value="vertical">{biText("纵向", "Vertical")}</option>
            <option value="horizontal">{biText("横向", "Horizontal")}</option>
          </select>
        </label>
        <label>
          <span>{biText("饼图形态", "Pie shape")}</span>
          <select value={widgetDraft.pieShape} onChange={(event) => setWidgetDraft((draft) => ({ ...draft, pieShape: event.target.value }))}>
            <option value="donut">{biText("环形", "Donut")}</option>
            <option value="pie">{biText("饼图", "Pie")}</option>
          </select>
        </label>
        <label>
          <span>{biText("排行模式", "Ranking")}</span>
          <select value={widgetDraft.rankingMode} onChange={(event) => setWidgetDraft((draft) => ({ ...draft, rankingMode: event.target.value }))}>
            {rankingModes.map((mode) => <option key={mode} value={mode}>{mode}</option>)}
          </select>
        </label>
        <label>
          <span>{biText("切片器", "Slicer")}</span>
          <select value={widgetDraft.slicerDisplay} onChange={(event) => setWidgetDraft((draft) => ({ ...draft, slicerDisplay: event.target.value }))}>
            {slicerDisplays.map((display) => <option key={display} value={display}>{display}</option>)}
          </select>
        </label>
        <label>
          <span>{biText("X 轴标题", "X axis title")}</span>
          <input value={widgetDraft.xAxisTitle} onChange={(event) => setWidgetDraft((draft) => ({ ...draft, xAxisTitle: event.target.value }))} />
        </label>
        <label>
          <span>{biText("Y 轴标题", "Y axis title")}</span>
          <input value={widgetDraft.yAxisTitle} onChange={(event) => setWidgetDraft((draft) => ({ ...draft, yAxisTitle: event.target.value }))} />
        </label>
        <label>
          <span>{biText("图例标题", "Legend title")}</span>
          <input value={widgetDraft.legendTitle} onChange={(event) => setWidgetDraft((draft) => ({ ...draft, legendTitle: event.target.value }))} />
        </label>
      </div>
      <div className="widgetToggleGrid">
        {widgetToggleOptions.map(({ key, label, checked }) => (
          <label className="toggleOption" key={key}>
            <input
              checked={checked}
              onChange={(event) => setWidgetDraft((draft) => ({ ...draft, [key]: event.target.checked }))}
              type="checkbox"
            />
            <span>{label}</span>
          </label>
        ))}
      </div>
    </details>
  );
}
