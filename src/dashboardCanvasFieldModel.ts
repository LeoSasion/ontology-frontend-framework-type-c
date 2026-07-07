import type { FieldConfig, SavedView } from "./types";

export type DashboardCanvasFieldModel = {
  tableFields: FieldConfig[];
  filterableFields: FieldConfig[];
  availableFilterFields: FieldConfig[];
  currentTableViews: SavedView[];
  usableViews: SavedView[];
  draftFields: FieldConfig[];
  draftDimensions: FieldConfig[];
  draftMeasures: FieldConfig[];
  draftViews: SavedView[];
};

export function isDashboardDimensionField(field: FieldConfig) {
  return ["groupable", "filterable"].includes(field.usage) || ["dimension", "event_time", "status", "identity_key"].includes(field.role);
}

export function isDashboardMeasureField(field: FieldConfig) {
  return field.usage === "aggregatable" || field.role === "measure";
}

export function buildDashboardCanvasFieldModel({
  fields,
  savedViews,
  dashboardTableKey,
  draftTableKey,
}: {
  fields: FieldConfig[];
  savedViews: SavedView[];
  dashboardTableKey: string;
  draftTableKey: string;
}): DashboardCanvasFieldModel {
  const tableFields = fields.filter((field) => field.table_key === dashboardTableKey);
  const filterableFields = tableFields.filter((field) => ["filterable", "groupable"].includes(field.usage) || ["dimension", "event_time", "status"].includes(field.role));
  const availableFilterFields = filterableFields.length ? filterableFields : tableFields;
  const currentTableViews = savedViews.filter((view) => view.table_key === dashboardTableKey);
  const usableViews = currentTableViews.length ? currentTableViews : savedViews;
  const draftFields = fields.filter((field) => field.table_key === draftTableKey);
  const draftDimensions = draftFields.filter(isDashboardDimensionField);
  const draftMeasures = draftFields.filter(isDashboardMeasureField);
  const draftViews = savedViews.filter((view) => view.table_key === draftTableKey);

  return {
    tableFields,
    filterableFields,
    availableFilterFields,
    currentTableViews,
    usableViews,
    draftFields,
    draftDimensions,
    draftMeasures,
    draftViews,
  };
}
