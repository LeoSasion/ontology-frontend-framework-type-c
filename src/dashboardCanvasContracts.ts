export type DashboardWidgetFilterInput = {
  field: string;
  operator: string;
  value?: string;
};

export type DashboardOperationOptions = {
  op: "create" | "copy" | "rename" | "delete";
  dashboardKey?: string;
  sourceDashboardKey?: string;
  name?: string;
  table?: string;
  confirm?: boolean;
};

export type DashboardFilterOperationOptions = {
  op: "list" | "add" | "set" | "remove" | "removeStale" | "clear";
  dashboardKey: string;
  filterId?: string;
  field?: string;
  operator?: string;
  value?: string;
  disabled?: boolean;
  confirm?: boolean;
};

export type DashboardModuleSaveOptions = {
  dashboardKey: string;
  dashboardName?: string;
  defaultTableKey?: string;
  canvasWidthMode?: "stretch" | "center";
  widgets: Array<Record<string, unknown>>;
  layout: Array<Record<string, unknown>>;
  filters: Array<Record<string, unknown>>;
  confirm?: boolean;
};

export type BusinessDashboardOptions = {
  op: "draft" | "create" | "overwrite";
  dashboardKey?: string;
  name?: string;
  table?: string;
  template?: "business" | "cost-monitor" | "erp-units";
  limit?: number;
  confirm?: boolean;
};

export type RelationshipSaveOptions = {
  leftTable: string;
  rightTable: string;
  leftField: string;
  rightField: string;
  fieldMappings?: Array<{ leftField: string; rightField: string }>;
  filters?: Array<{ phase?: "pre" | "post"; side?: string; field: string; operator: string; value?: string; enabled?: boolean }>;
  preaggregation?: { side: "right"; groupFields: string[]; measures: Array<{ field: string; aggregation: string }> };
  joinType?: string;
  limit?: number;
  confirm?: boolean;
};

export type DashboardWidgetOperationOptions = {
  op: "recommend" | "addRecommended" | "add" | "addRelationship" | "set" | "copy" | "remove";
  dashboardKey?: string;
  widgetKey?: string;
  relationship?: string;
  relation?: string;
  table?: string;
  view?: string;
  type?: string;
  title?: string;
  subtitle?: string;
  group?: string;
  dimension?: string;
  measure?: string;
  aggregation?: string;
  topN?: number;
  valueFormat?: string;
  textContent?: string;
  sortBy?: string;
  sortDirection?: string;
  decimalPlaces?: number;
  tableColumnLimit?: number;
  slicerDisplay?: string;
  slicerMultiSelect?: boolean;
  slicerSearchable?: boolean;
  showLegend?: boolean;
  showAxis?: boolean;
  showDataLabel?: boolean;
  rankingMode?: string;
  colorPalette?: string;
  barOrientation?: string;
  lineSmooth?: boolean;
  areaFill?: boolean;
  pieShape?: string;
  crossFilter?: boolean;
  drillDown?: boolean;
  globalFilterTarget?: boolean;
  xAxisTitle?: string;
  yAxisTitle?: string;
  legendTitle?: string;
  filters?: DashboardWidgetFilterInput[];
  clearFilters?: boolean;
  limit?: number;
  confirm?: boolean;
};
