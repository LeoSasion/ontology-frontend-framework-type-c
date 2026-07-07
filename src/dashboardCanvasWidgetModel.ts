import type { DashboardFilterRule, DashboardWidget } from "./types";

export type DashboardCanvasWidthMode = "stretch" | "center";

export type WidgetDraft = {
  title: string;
  subtitle: string;
  type: string;
  table: string;
  view: string;
  dimension: string;
  measure: string;
  aggregation: string;
  topN: string;
  valueFormat: string;
  textContent: string;
  sortBy: string;
  sortDirection: string;
  decimalPlaces: string;
  tableColumnLimit: string;
  slicerDisplay: string;
  slicerMultiSelect: boolean;
  slicerSearchable: boolean;
  showLegend: boolean;
  showAxis: boolean;
  showDataLabel: boolean;
  rankingMode: string;
  colorPalette: string;
  barOrientation: string;
  lineSmooth: boolean;
  areaFill: boolean;
  pieShape: string;
  crossFilter: boolean;
  drillDown: boolean;
  globalFilterTarget: boolean;
  xAxisTitle: string;
  yAxisTitle: string;
  legendTitle: string;
};

export type WidgetToggleKey =
  | "showLegend"
  | "showAxis"
  | "showDataLabel"
  | "lineSmooth"
  | "areaFill"
  | "slicerMultiSelect"
  | "slicerSearchable"
  | "crossFilter"
  | "drillDown"
  | "globalFilterTarget";

export function defaultWidgetDraft(): WidgetDraft {
  return {
    title: "",
    subtitle: "",
    type: "bar",
    table: "",
    view: "",
    dimension: "",
    measure: "",
    aggregation: "sum",
    topN: "12",
    valueFormat: "auto",
    textContent: "",
    sortBy: "metric",
    sortDirection: "desc",
    decimalPlaces: "2",
    tableColumnLimit: "6",
    slicerDisplay: "list",
    slicerMultiSelect: false,
    slicerSearchable: true,
    showLegend: true,
    showAxis: true,
    showDataLabel: false,
    rankingMode: "standard",
    colorPalette: "default",
    barOrientation: "vertical",
    lineSmooth: true,
    areaFill: false,
    pieShape: "donut",
    crossFilter: true,
    drillDown: true,
    globalFilterTarget: false,
    xAxisTitle: "",
    yAxisTitle: "",
    legendTitle: "",
  };
}

export function widgetDraftFromWidget(widget: DashboardWidget): WidgetDraft {
  const config = widget.config ?? {};
  return {
    ...defaultWidgetDraft(),
    title: widget.title,
    subtitle: typeof config.subtitle === "string" ? config.subtitle : "",
    type: widget.widget_type,
    table: widget.table_key,
    view: typeof config.viewKey === "string" ? config.viewKey : "",
    dimension: typeof config.dimension === "string" ? config.dimension : typeof config.group === "string" ? config.group : "",
    measure: typeof config.measure === "string" ? config.measure : "",
    aggregation: typeof config.aggregation === "string" ? config.aggregation : typeof config.agg === "string" ? config.agg : "sum",
    topN: String(config.topN ?? 12),
    valueFormat: typeof config.valueFormat === "string" ? config.valueFormat : "auto",
    textContent: typeof config.textContent === "string" ? config.textContent : "",
    sortBy: typeof config.sortBy === "string" ? config.sortBy : "metric",
    sortDirection: typeof config.sortDirection === "string" ? config.sortDirection : "desc",
    decimalPlaces: String(config.decimalPlaces ?? 2),
    tableColumnLimit: String(config.tableColumnLimit ?? 6),
    slicerDisplay: typeof config.slicerDisplay === "string" ? config.slicerDisplay : "list",
    slicerMultiSelect: config.slicerMultiSelect === true,
    slicerSearchable: config.slicerSearchable !== false,
    showLegend: config.showLegend !== false,
    showAxis: config.showAxis !== false,
    showDataLabel: config.showDataLabel === true,
    rankingMode: typeof config.rankingMode === "string" ? config.rankingMode : "standard",
    colorPalette: typeof config.colorPalette === "string" ? config.colorPalette : "default",
    barOrientation: config.barOrientation === "horizontal" ? "horizontal" : "vertical",
    lineSmooth: config.lineSmooth !== false,
    areaFill: config.areaFill === true,
    pieShape: config.pieShape === "pie" ? "pie" : "donut",
    crossFilter: config.crossFilter !== false,
    drillDown: config.drillDown !== false,
    globalFilterTarget: config.globalFilterTarget === true,
    xAxisTitle: typeof config.xAxisTitle === "string" ? config.xAxisTitle : "",
    yAxisTitle: typeof config.yAxisTitle === "string" ? config.yAxisTitle : "",
    legendTitle: typeof config.legendTitle === "string" ? config.legendTitle : "",
  };
}

export function boundedInteger(value: string, fallback: number, min: number, max: number) {
  return Math.max(min, Math.min(max, Number.parseInt(value, 10) || fallback));
}

export function widgetDraftNumbers(widgetDraft: WidgetDraft) {
  return {
    topN: boundedInteger(widgetDraft.topN, 12, 1, 500),
    decimalPlaces: boundedInteger(widgetDraft.decimalPlaces, 0, 0, 4),
    tableColumnLimit: boundedInteger(widgetDraft.tableColumnLimit, 6, 2, 24),
  };
}

export function buildWidgetSettingsPayload({
  selectedWidgetKey,
  widgetDraft,
  confirm,
}: {
  selectedWidgetKey?: string;
  widgetDraft: WidgetDraft;
  confirm: boolean;
}) {
  const parsed = widgetDraftNumbers(widgetDraft);
  return {
    op: "set" as const,
    widgetKey: selectedWidgetKey,
    type: widgetDraft.type,
    table: widgetDraft.table,
    view: widgetDraft.view,
    title: widgetDraft.title,
    subtitle: widgetDraft.subtitle,
    dimension: widgetDraft.dimension,
    measure: widgetDraft.measure,
    aggregation: widgetDraft.aggregation,
    topN: parsed.topN,
    valueFormat: widgetDraft.valueFormat,
    textContent: widgetDraft.textContent,
    sortBy: widgetDraft.sortBy,
    sortDirection: widgetDraft.sortDirection,
    decimalPlaces: parsed.decimalPlaces,
    tableColumnLimit: parsed.tableColumnLimit,
    slicerDisplay: widgetDraft.slicerDisplay,
    slicerMultiSelect: widgetDraft.slicerMultiSelect,
    slicerSearchable: widgetDraft.slicerSearchable,
    showLegend: widgetDraft.showLegend,
    showAxis: widgetDraft.showAxis,
    showDataLabel: widgetDraft.showDataLabel,
    rankingMode: widgetDraft.rankingMode,
    colorPalette: widgetDraft.colorPalette,
    barOrientation: widgetDraft.barOrientation,
    lineSmooth: widgetDraft.lineSmooth,
    areaFill: widgetDraft.areaFill,
    pieShape: widgetDraft.pieShape,
    crossFilter: widgetDraft.crossFilter,
    drillDown: widgetDraft.drillDown,
    globalFilterTarget: widgetDraft.globalFilterTarget,
    xAxisTitle: widgetDraft.xAxisTitle,
    yAxisTitle: widgetDraft.yAxisTitle,
    legendTitle: widgetDraft.legendTitle,
    confirm,
  };
}

export function moduleLayoutForWidget(widget: DashboardWidget, index: number): Record<string, unknown> {
  const existing = widget.config?.layout && typeof widget.config.layout === "object" ? widget.config.layout as Record<string, unknown> : {};
  const fallbackWidth = widget.widget_type === "metric" ? 3 : widget.widget_type === "table" ? 8 : 4;
  const fallbackHeight = widget.widget_type === "metric" ? 2 : widget.widget_type === "table" ? 5 : 4;
  return {
    x: (index % 3) * 4,
    y: Math.floor(index / 3) * 4,
    w: fallbackWidth,
    h: fallbackHeight,
    minW: widget.widget_type === "metric" ? 2 : 3,
    minH: widget.widget_type === "metric" ? 2 : 3,
    ...existing,
    i: widget.widget_key,
  };
}

export function buildDashboardModulePayload({
  dashboardKey,
  dashboardName,
  defaultTableKey,
  canvasWidthMode,
  widgets,
  filters,
  confirm,
}: {
  dashboardKey: string;
  dashboardName: string;
  defaultTableKey: string;
  canvasWidthMode: DashboardCanvasWidthMode;
  widgets: DashboardWidget[];
  filters: DashboardFilterRule[];
  confirm: boolean;
}) {
  const layout = widgets.map(moduleLayoutForWidget);
  return {
    dashboardKey,
    dashboardName,
    defaultTableKey,
    canvasWidthMode,
    widgets: widgets.map((widget, index) => ({
      id: widget.widget_key,
      widget_key: widget.widget_key,
      type: widget.widget_type,
      widget_type: widget.widget_type,
      title: widget.title,
      tableKey: widget.table_key,
      table_key: widget.table_key,
      ...(widget.config ?? {}),
      layout: layout[index],
    })),
    layout,
    filters: filters.map((filter) => ({ ...filter })),
    confirm,
  };
}
