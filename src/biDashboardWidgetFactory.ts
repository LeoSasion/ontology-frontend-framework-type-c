import {
  B_DASHBOARD_COLOR_PALETTES,
  B_DASHBOARD_DATA_MODES,
  B_DASHBOARD_VALUE_FORMATS,
  B_DASHBOARD_WIDGET_TYPES,
  normalizeBiDashboardFilters,
  type BiDashboardAggregation,
  type BiDashboardColorPalette,
  type BiDashboardDataMode,
  type BiDashboardSlicerDisplay,
  type BiDashboardValueFormat,
  type BiDashboardWidget,
  type BiDashboardWidgetRelationshipQuery,
  type BiDashboardWidgetType,
} from "./biDashboardModel";
import { toStringValue } from "./biDashboardValueModel";
import type { DashboardPage, DashboardPayload, QueryResult, WorkbenchPayload } from "./types";
import { latestUsableSourceIntelligenceRun } from "./workspaceFlowModel";

function normalizeType(value: unknown): BiDashboardWidgetType {
  const type = String(value ?? "").trim().toLowerCase();
  if (type === "kpi") return "metric";
  if (type === "trend") return "line";
  if (type === "donut") return "pie";
  if (type === "filter") return "slicer";
  return B_DASHBOARD_WIDGET_TYPES.includes(type as BiDashboardWidgetType) ? type as BiDashboardWidgetType : "bar";
}

function normalizeAggregation(value: unknown): BiDashboardAggregation {
  const aggregation = String(value ?? "").trim().toLowerCase();
  return ["count", "sum", "avg", "max", "min"].includes(aggregation) ? aggregation as BiDashboardAggregation : "sum";
}

function normalizeValueFormat(value: unknown): BiDashboardValueFormat {
  const format = String(value ?? "").trim().toLowerCase();
  return B_DASHBOARD_VALUE_FORMATS.includes(format as BiDashboardValueFormat) ? format as BiDashboardValueFormat : "auto";
}

function normalizeColorPalette(value: unknown): BiDashboardColorPalette {
  const palette = String(value ?? "").trim().toLowerCase();
  return B_DASHBOARD_COLOR_PALETTES.includes(palette as BiDashboardColorPalette) ? palette as BiDashboardColorPalette : "default";
}

function clampInteger(value: unknown, fallback: number, min: number, max: number): number {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(min, Math.min(max, Math.round(parsed)));
}

function latestRunEvidence(workbench: WorkbenchPayload): string[] {
  const sourceIntelligenceRuns = Array.isArray(workbench.sourceIntelligenceRuns) ? workbench.sourceIntelligenceRuns : [];
  const latestRun = latestUsableSourceIntelligenceRun(sourceIntelligenceRuns);
  const base = ["query-runtime", "dashboard-widget-contract", "b-bi-cli-compatible"];
  if (!latestRun) return base;
  return [
    ...base,
    `source-intelligence:${latestRun.run_key}`,
    `source-count:${latestRun.source_count}`,
    `metric-sql:${latestRun.metric_sql_executable_count}/${latestRun.metric_sql_plan_count}`,
  ];
}

function normalizeRelationship(value: unknown): BiDashboardWidgetRelationshipQuery | undefined {
  if (!value || typeof value !== "object") return undefined;
  const item = value as Record<string, unknown>;
  const leftTableKey = toStringValue(item.leftTableKey);
  const rightTableKey = toStringValue(item.rightTableKey);
  const rawMappings = Array.isArray(item.fieldMappings) ? item.fieldMappings : [];
  const fieldMappings = rawMappings
    .filter((mapping): mapping is Record<string, unknown> => Boolean(mapping) && typeof mapping === "object")
    .map((mapping) => ({
      leftField: toStringValue(mapping.leftField),
      rightField: toStringValue(mapping.rightField),
    }))
    .filter((mapping) => mapping.leftField && mapping.rightField);
  if (!leftTableKey || !rightTableKey || !fieldMappings.length) return undefined;
  const rawGroups = Array.isArray(item.groupFields) ? item.groupFields : [];
  const groupFields = rawGroups
    .filter((group): group is Record<string, unknown> => Boolean(group) && typeof group === "object")
    .map((group) => ({
      side: group.side === "right" ? "right" as const : "left" as const,
      field: toStringValue(group.field),
    }))
    .filter((group) => group.field);
  const measure = item.measure && typeof item.measure === "object"
    ? {
        side: (item.measure as Record<string, unknown>).side === "right" ? "right" as const : "left" as const,
        field: toStringValue((item.measure as Record<string, unknown>).field),
      }
    : null;
  return {
    relationKey: toStringValue(item.relationKey),
    leftTableKey,
    rightTableKey,
    fieldMappings,
    joinType: toStringValue(item.joinType, "left"),
    groupFields,
    measure: measure?.field ? measure : null,
    aggregation: normalizeAggregation(item.aggregation),
  };
}

function baseWidget(args: {
  id: string;
  type: BiDashboardWidgetType;
  title: string;
  subtitle?: string;
  tableKey?: string;
  dataMode?: BiDashboardDataMode;
  relationship?: BiDashboardWidgetRelationshipQuery;
  evidence: string[];
  overrides?: Partial<BiDashboardWidget>;
}): BiDashboardWidget {
  return {
    id: args.id,
    type: args.type,
    title: args.title,
    subtitle: args.subtitle,
    tableKey: args.tableKey,
    dataMode: args.dataMode ?? "table",
    relationship: args.relationship,
    aggregation: "sum",
    sortBy: "metric",
    sortDirection: "desc",
    topN: 12,
    valueFormat: "auto",
    decimalPlaces: 2,
    tableColumnLimit: 6,
    slicerDisplay: "list",
    slicerMultiSelect: false,
    slicerSearchable: true,
    filters: [],
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
    evidence: args.evidence,
    ...args.overrides,
  };
}

function hydrateStoredWidget(widget: DashboardPage["widgets"][number], evidence: string[]): BiDashboardWidget {
  const config = widget.config ?? {};
  const type = normalizeType(widget.widget_type);
  const dataMode = toStringValue(config.dataMode, "table") as BiDashboardDataMode;
  const relationship = normalizeRelationship(config.relationship);
  return baseWidget({
    id: widget.widget_key,
    type,
    title: widget.title,
    tableKey: widget.table_key,
    dataMode: B_DASHBOARD_DATA_MODES.includes(dataMode) ? dataMode : "table",
    relationship,
    evidence: relationship?.relationKey ? [...evidence, `relationship:${relationship.relationKey}`] : evidence,
    overrides: {
      subtitle: toStringValue(config.subtitle),
      viewKey: toStringValue(config.viewKey),
      textContent: toStringValue(config.textContent),
      dimension: toStringValue(config.dimension, toStringValue(config.group)),
      measure: toStringValue(config.measure, "value"),
      aggregation: normalizeAggregation(config.aggregation ?? config.agg),
      topN: clampInteger(config.topN, 12, 1, 500),
      valueFormat: normalizeValueFormat(config.valueFormat),
      decimalPlaces: clampInteger(config.decimalPlaces, 2, 0, 4),
      tableColumnLimit: clampInteger(config.tableColumnLimit, 6, 2, 24),
      colorPalette: normalizeColorPalette(config.colorPalette),
      barOrientation: config.barOrientation === "horizontal" ? "horizontal" : "vertical",
      pieShape: config.pieShape === "pie" ? "pie" : "donut",
      slicerDisplay: ["dropdown", "range"].includes(String(config.slicerDisplay)) ? config.slicerDisplay as BiDashboardSlicerDisplay : "list",
      slicerMultiSelect: config.slicerMultiSelect === true,
      slicerSearchable: config.slicerSearchable !== false,
      filters: normalizeBiDashboardFilters(config.filters),
      showLegend: config.showLegend !== false,
      showAxis: config.showAxis !== false,
      showDataLabel: config.showDataLabel === true,
      rankingMode: config.rankingMode === "ranked" ? "ranked" : "standard",
      xAxisTitle: toStringValue(config.xAxisTitle),
      yAxisTitle: toStringValue(config.yAxisTitle),
      legendTitle: toStringValue(config.legendTitle),
      lineSmooth: config.lineSmooth !== false,
      areaFill: config.areaFill === true,
      crossFilter: config.crossFilter !== false,
      drillDown: type === "slicer" ? false : config.drillDown !== false,
      globalFilterTarget: config.globalFilterTarget === true,
    },
  });
}

export function buildBiDashboardWidgets(args: {
  dashboard: DashboardPage;
  dashboards: DashboardPayload;
  query: QueryResult;
  workbench: WorkbenchPayload;
}): BiDashboardWidget[] {
  const evidence = latestRunEvidence(args.workbench);
  const stored = Array.isArray(args.dashboard.widgets) ? args.dashboard.widgets.map((widget) => hydrateStoredWidget(widget, evidence)) : [];
  return stored.sort((left, right) => B_DASHBOARD_WIDGET_TYPES.indexOf(left.type) - B_DASHBOARD_WIDGET_TYPES.indexOf(right.type));
}
