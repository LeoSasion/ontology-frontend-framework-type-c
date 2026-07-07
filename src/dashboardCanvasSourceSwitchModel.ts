import type { DashboardFilterRule, DashboardWidget, FieldConfig } from "./types";
import { moduleLayoutForWidget, type DashboardCanvasWidthMode } from "./dashboardCanvasWidgetModel";
import { normalizeWidgetFilters } from "./dashboardCanvasFilterModel";

export type SourceSwitchStaleWidgetRef = {
  widgetKey: string;
  title: string;
  field: string;
  kind: string;
};

export type SourceSwitchAnalysis = {
  targetFields: FieldConfig[];
  targetFieldNames: Set<string>;
  targetDimensions: FieldConfig[];
  targetMeasures: FieldConfig[];
  fallbackDimension: string;
  fallbackMeasure: string;
  impactedWidgets: DashboardWidget[];
  filterCleanup: DashboardFilterRule[];
  validFilters: DashboardFilterRule[];
  staleWidgetRefs: SourceSwitchStaleWidgetRef[];
  changed: boolean;
  cleanupCount: number;
};

export function analyzeDashboardSourceSwitch({
  fields,
  widgets,
  filters,
  defaultTableKey,
  sourceSwitchTableKey,
}: {
  fields: FieldConfig[];
  widgets: DashboardWidget[];
  filters: DashboardFilterRule[];
  defaultTableKey: string;
  sourceSwitchTableKey: string;
}): SourceSwitchAnalysis {
  const targetFields = fields.filter((field) => field.table_key === sourceSwitchTableKey);
  const targetFieldNames = new Set(targetFields.map((field) => field.field_name));
  const targetDimensions = targetFields.filter((field) => ["groupable", "filterable"].includes(field.usage) || ["dimension", "event_time", "status", "identity_key"].includes(field.role));
  const targetMeasures = targetFields.filter((field) => field.usage === "aggregatable" || field.role === "measure");
  const fallbackDimension = targetDimensions[0]?.field_name ?? targetFields[0]?.field_name ?? "";
  const fallbackMeasure = targetMeasures[0]?.field_name ?? targetFields[0]?.field_name ?? "";
  const impactedWidgets = widgets.filter((widget) => widget.table_key === defaultTableKey);
  const filterCleanup = targetFieldNames.size
    ? filters.filter((filter) => !targetFieldNames.has(filter.field))
    : filters;
  const validFilters = targetFieldNames.size
    ? filters.filter((filter) => targetFieldNames.has(filter.field))
    : [];
  const staleWidgetRefs = impactedWidgets.flatMap((widget) => {
    const config = widget.config ?? {};
    const refs = ["dimension", "group", "measure", "timeField"]
      .map((key) => ({ key, value: typeof config[key] === "string" ? String(config[key]) : "" }))
      .filter((ref) => ref.value && ref.value !== "*" && targetFieldNames.size > 0 && !targetFieldNames.has(ref.value));
    const localFilters = normalizeWidgetFilters(config.filters)
      .filter((filter) => targetFieldNames.size === 0 || !targetFieldNames.has(filter.field))
      .map((filter) => ({ key: "filter", value: filter.field }));
    return [...refs, ...localFilters].map((ref) => ({
      widgetKey: widget.widget_key,
      title: widget.title,
      field: ref.value,
      kind: ref.key,
    }));
  });
  return {
    targetFields,
    targetFieldNames,
    targetDimensions,
    targetMeasures,
    fallbackDimension,
    fallbackMeasure,
    impactedWidgets,
    filterCleanup,
    validFilters,
    staleWidgetRefs,
    changed: sourceSwitchTableKey !== defaultTableKey,
    cleanupCount: filterCleanup.length + staleWidgetRefs.length,
  };
}

export function cleanedWidgetForSourceSwitch({
  widget,
  index,
  defaultTableKey,
  sourceSwitchTableKey,
  targetFieldNames,
  fallbackDimension,
  fallbackMeasure,
}: {
  widget: DashboardWidget;
  index: number;
  defaultTableKey: string;
  sourceSwitchTableKey: string;
  targetFieldNames: Set<string>;
  fallbackDimension: string;
  fallbackMeasure: string;
}) {
  const layout = moduleLayoutForWidget(widget, index);
  const config = { ...(widget.config ?? {}) };
  if (widget.table_key === defaultTableKey) {
    (["dimension", "group", "timeField"] as const).forEach((key) => {
      const value = typeof config[key] === "string" ? String(config[key]) : "";
      if (value && targetFieldNames.size > 0 && !targetFieldNames.has(value)) {
        if (fallbackDimension) {
          config[key] = fallbackDimension;
        } else {
          delete config[key];
        }
      }
    });
    const measureValue = typeof config.measure === "string" ? String(config.measure) : "";
    if (measureValue && measureValue !== "*" && targetFieldNames.size > 0 && !targetFieldNames.has(measureValue)) {
      if (fallbackMeasure) {
        config.measure = fallbackMeasure;
      } else {
        delete config.measure;
      }
    }
    const localFilters = normalizeWidgetFilters(config.filters);
    config.filters = targetFieldNames.size
      ? localFilters.filter((filter) => targetFieldNames.has(filter.field)).map((filter) => ({ ...filter }))
      : [];
  }
  const nextTableKey = widget.table_key === defaultTableKey ? sourceSwitchTableKey : widget.table_key;
  return {
    id: widget.widget_key,
    widget_key: widget.widget_key,
    type: widget.widget_type,
    widget_type: widget.widget_type,
    title: widget.title,
    tableKey: nextTableKey,
    table_key: nextTableKey,
    ...config,
    layout,
  };
}

export function buildSourceSwitchModulePayload({
  dashboardKey,
  dashboardName,
  defaultTableKey,
  sourceSwitchTableKey,
  canvasWidthMode,
  widgets,
  filters,
  fields,
  confirm,
}: {
  dashboardKey: string;
  dashboardName: string;
  defaultTableKey: string;
  sourceSwitchTableKey: string;
  canvasWidthMode: DashboardCanvasWidthMode;
  widgets: DashboardWidget[];
  filters: DashboardFilterRule[];
  fields: FieldConfig[];
  confirm: boolean;
}) {
  const analysis = analyzeDashboardSourceSwitch({ fields, widgets, filters, defaultTableKey, sourceSwitchTableKey });
  const layout = widgets.map(moduleLayoutForWidget);
  return {
    dashboardKey,
    dashboardName,
    defaultTableKey: sourceSwitchTableKey,
    canvasWidthMode,
    widgets: widgets.map((widget, index) => cleanedWidgetForSourceSwitch({
      widget,
      index,
      defaultTableKey,
      sourceSwitchTableKey,
      targetFieldNames: analysis.targetFieldNames,
      fallbackDimension: analysis.fallbackDimension,
      fallbackMeasure: analysis.fallbackMeasure,
    })),
    layout,
    filters: analysis.validFilters.map((filter) => ({ ...filter })),
    confirm,
  };
}
