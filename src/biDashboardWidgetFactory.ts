import { biText } from "./components/Bilingual";
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
import { safeQueryInfo } from "./biDashboardRuntime";
import { toStringValue } from "./biDashboardValueModel";
import type { DashboardPage, DashboardPayload, QueryResult, WorkbenchPayload } from "./types";

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
  const latestRun = sourceIntelligenceRuns[0];
  const base = ["query-runtime", "dashboard-widget-contract", "b-bi-cli-compatible"];
  if (!latestRun) return base;
  return [
    ...base,
    `source-intelligence:${latestRun.run_key}`,
    `source-count:${latestRun.source_count}`,
    `metric-sql:${latestRun.metric_sql_executable_count}/${latestRun.metric_sql_plan_count}`,
  ];
}

function relationshipForWidget(workbench: WorkbenchPayload): BiDashboardWidgetRelationshipQuery | undefined {
  const relation = Array.isArray(workbench.relationships) ? workbench.relationships[0] : undefined;
  if (!relation) return undefined;
  return {
    relationKey: relation.relation_key,
    leftTableKey: relation.left_table_key,
    rightTableKey: relation.right_table_key,
    fieldMappings: [{ leftField: relation.left_field, rightField: relation.right_field }],
    joinType: relation.join_type,
    groupFields: [{ side: "left", field: relation.left_field }],
    measure: null,
    aggregation: "count",
  };
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
      dimension: toStringValue(config.dimension, toStringValue(config.group, "label")),
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
  const queryInfo = safeQueryInfo(args.query);
  const tables = Array.isArray(args.workbench.tables) ? args.workbench.tables : [];
  const metrics = Array.isArray(args.workbench.metrics) ? args.workbench.metrics : [];
  const sourceIntelligenceRuns = Array.isArray(args.workbench.sourceIntelligenceRuns) ? args.workbench.sourceIntelligenceRuns : [];
  const tableKey = args.dashboard.default_table_key || queryInfo.table || tables[0]?.table_key || "unknown_table";
  const relation = relationshipForWidget(args.workbench);
  const latestRun = sourceIntelligenceRuns[0];
  const stored = Array.isArray(args.dashboard.widgets) ? args.dashboard.widgets.map((widget) => hydrateStoredWidget(widget, evidence)) : [];
  const types = new Set(stored.map((widget) => widget.type));
  const queryMeasure = queryInfo.measure || metrics[0]?.measure || "value";
  const queryGroup = queryInfo.group || metrics[0]?.dimension || "label";
  const defaults: Record<BiDashboardWidgetType, BiDashboardWidget> = {
    metric: baseWidget({
      id: "b-widget-metric-default",
      type: "metric",
      title: biText("净销售指标", "Net sales metric"),
      subtitle: biText("当前汇总", "Current total"),
      tableKey,
      evidence,
      overrides: { measure: queryMeasure, aggregation: "sum", valueFormat: "compact" },
    }),
    bar: baseWidget({
      id: "b-widget-bar-default",
      type: "bar",
      title: biText("分类排行", "Category ranking"),
      subtitle: queryGroup,
      tableKey,
      evidence,
      overrides: { dimension: queryGroup, measure: queryMeasure, aggregation: "sum", barOrientation: "horizontal", rankingMode: "ranked" },
    }),
    line: baseWidget({
      id: "b-widget-line-default",
      type: "line",
      title: biText("趋势检查", "Trend check"),
      subtitle: biText("按当前结果顺序", "Current result order"),
      tableKey,
      evidence,
      overrides: { dimension: queryGroup, measure: queryMeasure, lineSmooth: true, areaFill: true, colorPalette: "fresh" },
    }),
    pie: baseWidget({
      id: "b-widget-pie-default",
      type: "pie",
      title: biText("构成占比", "Composition share"),
      subtitle: queryGroup,
      tableKey,
      evidence,
      overrides: { dimension: queryGroup, measure: queryMeasure, pieShape: "donut", colorPalette: "contrast", showDataLabel: true },
    }),
    table: baseWidget({
      id: "b-widget-table-default",
      type: "table",
      title: biText("明细表", "Detail table"),
      subtitle: tableKey,
      tableKey,
      evidence,
      overrides: { tableColumnLimit: 6, drillDown: true },
    }),
    text: baseWidget({
      id: "b-widget-text-default",
      type: "text",
      title: biText("证据摘要", "Evidence summary"),
      subtitle: latestRun ? latestRun.label : biText("等待数据画像", "Waiting for profiling"),
      tableKey,
      evidence,
      overrides: {
        textContent: latestRun
          ? biText(
            `已读取 ${latestRun.source_count} 个文件，识别 ${latestRun.table_count} 张表，并验证 ${latestRun.metric_sql_executable_count}/${latestRun.metric_sql_plan_count} 个指标计划可执行。`,
            `${latestRun.source_count} files read, ${latestRun.table_count} tables detected, and ${latestRun.metric_sql_executable_count}/${latestRun.metric_sql_plan_count} metric plans verified as executable.`,
          )
          : biText("更新数据画像后，这里会显示本次分析的证据摘要。", "Refresh the data profile to show the evidence summary for this analysis."),
        crossFilter: false,
        drillDown: false,
      },
    }),
    slicer: baseWidget({
      id: "b-widget-slicer-default",
      type: "slicer",
      title: biText("局部筛选", "Local filter"),
      subtitle: queryGroup,
      tableKey,
      evidence,
      overrides: { dimension: "label", slicerDisplay: "list", slicerMultiSelect: true, globalFilterTarget: true, drillDown: false },
    }),
  };
  if (relation && !stored.some((widget) => widget.dataMode === "relationship")) {
    defaults.bar = {
      ...defaults.bar,
      id: "b-widget-relationship-default",
      title: "关系预览排行",
      subtitle: `${relation.leftTableKey} -> ${relation.rightTableKey}`,
      dataMode: "relationship",
      relationship: relation,
      evidence: [...evidence, `relationship:${relation.leftTableKey}:${relation.rightTableKey}`],
    };
  }
  const completed = [...stored];
  for (const type of B_DASHBOARD_WIDGET_TYPES) {
    if (!types.has(type)) completed.push(defaults[type]);
  }
  return completed.sort((left, right) => B_DASHBOARD_WIDGET_TYPES.indexOf(left.type) - B_DASHBOARD_WIDGET_TYPES.indexOf(right.type));
}
