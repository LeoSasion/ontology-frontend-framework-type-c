import { toStringValue } from "./biDashboardValueModel";

export type BiDashboardWidgetType = "metric" | "bar" | "line" | "pie" | "table" | "text" | "slicer";
export type BiDashboardDataMode = "table" | "view" | "relationship";
export type BiDashboardFilterOperator = "contains" | "equals" | "in" | "between" | "notEquals" | "gt" | "gte" | "lt" | "lte" | "empty" | "notEmpty";
export type BiDashboardValueFormat = "auto" | "plain" | "compact" | "currency" | "percent";
export type BiDashboardSlicerDisplay = "list" | "dropdown" | "range";
export type BiDashboardColorPalette = "default" | "fresh" | "warm" | "contrast" | "mono";
export type BiDashboardBarOrientation = "vertical" | "horizontal";
export type BiDashboardPieShape = "donut" | "pie";
export type BiDashboardAggregation = "count" | "sum" | "avg" | "max" | "min";

export interface BiDashboardFilterRule {
  id: string;
  field: string;
  operator: BiDashboardFilterOperator;
  value: string;
  enabled: boolean;
}

export interface BiDashboardWidgetRelationshipQuery {
  relationKey?: string;
  leftTableKey: string;
  rightTableKey: string;
  fieldMappings: Array<{ leftField: string; rightField: string }>;
  joinType: "left" | "inner" | "lookup" | string;
  groupFields: Array<{ side: "left" | "right"; field: string }>;
  measure?: { side: "left" | "right"; field: string } | null;
  aggregation: BiDashboardAggregation | "count-distinct";
}

export interface BiDashboardWidget {
  id: string;
  type: BiDashboardWidgetType;
  title: string;
  subtitle?: string;
  textContent?: string;
  tableKey?: string;
  viewKey?: string;
  dataMode: BiDashboardDataMode;
  relationship?: BiDashboardWidgetRelationshipQuery;
  dimension?: string;
  measure?: string;
  aggregation: BiDashboardAggregation;
  sortBy: "metric" | "dimension";
  sortDirection: "asc" | "desc";
  topN: number;
  valueFormat: BiDashboardValueFormat;
  decimalPlaces: number;
  tableColumnLimit: number;
  slicerDisplay: BiDashboardSlicerDisplay;
  slicerMultiSelect: boolean;
  slicerSearchable: boolean;
  filters: BiDashboardFilterRule[];
  showLegend: boolean;
  showAxis: boolean;
  showDataLabel: boolean;
  rankingMode: "standard" | "ranked";
  xAxisTitle?: string;
  yAxisTitle?: string;
  legendTitle?: string;
  colorPalette: BiDashboardColorPalette;
  barOrientation: BiDashboardBarOrientation;
  lineSmooth: boolean;
  areaFill: boolean;
  pieShape: BiDashboardPieShape;
  crossFilter: boolean;
  drillDown: boolean;
  globalFilterTarget: boolean;
  evidence: string[];
}

export interface BiDashboardDatum {
  label: string;
  value: number;
  raw: Record<string, unknown>;
}

export interface BiDashboardWidgetCatalogItem {
  type: BiDashboardWidgetType;
  label: {
    zh: string;
    en: string;
  };
  description: {
    zh: string;
    en: string;
  };
  dataModes: BiDashboardDataMode[];
  supports: string[];
  defaultLayout: {
    w: number;
    h: number;
    minW: number;
    minH: number;
  };
}

export const B_DASHBOARD_WIDGET_TYPES: BiDashboardWidgetType[] = ["metric", "bar", "line", "pie", "table", "text", "slicer"];
export const B_DASHBOARD_DATA_MODES: BiDashboardDataMode[] = ["table", "view", "relationship"];
export const B_DASHBOARD_VALUE_FORMATS: BiDashboardValueFormat[] = ["auto", "plain", "compact", "currency", "percent"];
export const B_DASHBOARD_COLOR_PALETTES: BiDashboardColorPalette[] = ["default", "fresh", "warm", "contrast", "mono"];
export const B_DASHBOARD_FILTER_OPERATORS: BiDashboardFilterOperator[] = ["contains", "equals", "in", "between", "notEquals", "gt", "gte", "lt", "lte", "empty", "notEmpty"];

export const B_DASHBOARD_WIDGET_CATALOG: BiDashboardWidgetCatalogItem[] = [
  {
    type: "metric",
    label: { zh: "指标卡", en: "Metric" },
    description: { zh: "核心指标和汇总值", en: "Core KPI and aggregate value" },
    dataModes: ["table", "view", "relationship"],
    supports: ["aggregation", "valueFormat", "filters", "crossFilter", "drillDown"],
    defaultLayout: { w: 3, h: 4, minW: 2, minH: 4 },
  },
  {
    type: "bar",
    label: { zh: "柱状图", en: "Bar" },
    description: { zh: "分类对比和排行", en: "Category comparison and ranking" },
    dataModes: ["table", "view", "relationship"],
    supports: ["orientation", "rankingMode", "palette", "legend", "axis", "filters"],
    defaultLayout: { w: 6, h: 7, minW: 4, minH: 5 },
  },
  {
    type: "line",
    label: { zh: "折线图", en: "Line" },
    description: { zh: "趋势和波动", en: "Trend and movement" },
    dataModes: ["table", "view", "relationship"],
    supports: ["timeGrain", "lineSmooth", "areaFill", "palette", "axis", "filters"],
    defaultLayout: { w: 6, h: 7, minW: 4, minH: 5 },
  },
  {
    type: "pie",
    label: { zh: "环形图", en: "Pie" },
    description: { zh: "构成占比分析", en: "Composition analysis" },
    dataModes: ["table", "view", "relationship"],
    supports: ["pieShape", "palette", "legend", "dataLabel", "filters"],
    defaultLayout: { w: 6, h: 7, minW: 4, minH: 5 },
  },
  {
    type: "table",
    label: { zh: "明细表", en: "Table" },
    description: { zh: "筛选后的明细数据", en: "Filtered detail data" },
    dataModes: ["table", "view", "relationship"],
    supports: ["columns", "pagination", "filters", "drillDown"],
    defaultLayout: { w: 8, h: 8, minW: 5, minH: 6 },
  },
  {
    type: "text",
    label: { zh: "文本", en: "Text" },
    description: { zh: "结论、说明和备注", en: "Narrative note and annotation" },
    dataModes: ["table"],
    supports: ["textContent", "evidence"],
    defaultLayout: { w: 4, h: 4, minW: 3, minH: 3 },
  },
  {
    type: "slicer",
    label: { zh: "切片器", en: "Slicer" },
    description: { zh: "画布内筛选控件", en: "Canvas filter control" },
    dataModes: ["table", "view"],
    supports: ["list", "dropdown", "range", "multiSelect", "search"],
    defaultLayout: { w: 4, h: 5, minW: 3, minH: 4 },
  },
];

export function normalizeBiDashboardFilters(value: unknown): BiDashboardFilterRule[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
    .map((item, index) => {
      const operator = B_DASHBOARD_FILTER_OPERATORS.includes(item.operator as BiDashboardFilterOperator)
        ? item.operator as BiDashboardFilterOperator
        : "contains";
      return {
        id: toStringValue(item.id, `filter-${index + 1}`),
        field: toStringValue(item.field),
        operator,
        value: toStringValue(item.value),
        enabled: item.enabled !== false,
      };
    })
    .filter((item) => item.field);
}

export { buildBiDashboardWidgets } from "./biDashboardWidgetFactory";
