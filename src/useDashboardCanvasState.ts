import { useEffect, useMemo, useState } from "react";
import type {
  DashboardPage,
  DashboardWidget,
  FieldConfig,
  RelationshipRecord,
  SavedView,
  WorkbenchTable,
} from "./types";
import { buildDashboardCanvasFieldModel } from "./dashboardCanvasFieldModel";
import { normalizeWidgetFilters } from "./dashboardCanvasFilterModel";
import {
  defaultWidgetDraft,
  widgetDraftFromWidget,
  type DashboardCanvasWidthMode,
  type WidgetDraft,
} from "./dashboardCanvasWidgetModel";

type DashboardCanvasStateOptions = {
  dashboard: DashboardPage;
  dashboardWidgets: DashboardWidget[];
  editableTables: WorkbenchTable[];
  fields: FieldConfig[];
  savedRelationships: RelationshipRecord[];
  savedViews: SavedView[];
};

export function useDashboardCanvasState({
  dashboard,
  dashboardWidgets,
  editableTables,
  fields,
  savedRelationships,
  savedViews,
}: DashboardCanvasStateOptions) {
  const [draftName, setDraftName] = useState(dashboard?.name ?? "");
  const [filterField, setFilterField] = useState("");
  const [filterOperator, setFilterOperator] = useState("equals");
  const [filterValue, setFilterValue] = useState("");
  const [selectedViewKey, setSelectedViewKey] = useState("");
  const [selectedRelationshipKey, setSelectedRelationshipKey] = useState("");
  const [selectedWidgetKey, setSelectedWidgetKey] = useState("");
  const [sourceSwitchTableKey, setSourceSwitchTableKey] = useState(dashboard.default_table_key);
  const [canvasWidthMode, setCanvasWidthMode] = useState<DashboardCanvasWidthMode>(dashboard.layout?.canvasWidthMode === "center" ? "center" : "stretch");
  const [widgetFilterField, setWidgetFilterField] = useState("");
  const [widgetFilterOperator, setWidgetFilterOperator] = useState("equals");
  const [widgetFilterValue, setWidgetFilterValue] = useState("");
  const [widgetDraft, setWidgetDraft] = useState<WidgetDraft>(() => defaultWidgetDraft());

  const selectedWidget = useMemo(
    () => dashboardWidgets.find((widget) => widget.widget_key === selectedWidgetKey) ?? dashboardWidgets[0],
    [dashboardWidgets, selectedWidgetKey],
  );
  const selectedRelationship = useMemo(
    () => savedRelationships.find((relationship) => relationship.relation_key === selectedRelationshipKey) ?? savedRelationships[0],
    [savedRelationships, selectedRelationshipKey],
  );
  const sourceSwitchTable = useMemo(
    () => editableTables.find((table) => table.table_key === sourceSwitchTableKey),
    [editableTables, sourceSwitchTableKey],
  );
  const fieldModel = useMemo(() => buildDashboardCanvasFieldModel({
    fields,
    savedViews,
    dashboardTableKey: dashboard.default_table_key,
    draftTableKey: widgetDraft.table || dashboard.default_table_key,
  }), [dashboard.default_table_key, fields, savedViews, widgetDraft.table]);
  const widgetFilters = useMemo(
    () => selectedWidget ? normalizeWidgetFilters(selectedWidget.config?.filters) : [],
    [selectedWidget],
  );

  useEffect(() => {
    setDraftName(dashboard?.name ?? "");
  }, [dashboard?.dashboard_key, dashboard?.name]);

  useEffect(() => {
    setCanvasWidthMode(dashboard.layout?.canvasWidthMode === "center" ? "center" : "stretch");
  }, [dashboard.dashboard_key, dashboard.layout?.canvasWidthMode]);

  useEffect(() => {
    setSourceSwitchTableKey(dashboard.default_table_key);
  }, [dashboard.dashboard_key, dashboard.default_table_key]);

  useEffect(() => {
    setFilterField((current) => fieldModel.availableFilterFields.some((field) => field.field_name === current) ? current : fieldModel.availableFilterFields[0]?.field_name ?? "");
  }, [fieldModel.availableFilterFields, dashboard.dashboard_key]);

  useEffect(() => {
    setSelectedViewKey((current) => fieldModel.usableViews.some((view) => view.view_key === current) ? current : fieldModel.usableViews[0]?.view_key ?? "");
  }, [dashboard.dashboard_key, fieldModel.usableViews]);

  useEffect(() => {
    setSelectedRelationshipKey((current) => savedRelationships.some((relationship) => relationship.relation_key === current) ? current : savedRelationships[0]?.relation_key ?? "");
  }, [dashboard.dashboard_key, savedRelationships]);

  useEffect(() => {
    setSelectedWidgetKey((current) => dashboardWidgets.some((widget) => widget.widget_key === current) ? current : dashboardWidgets[0]?.widget_key ?? "");
  }, [dashboard.dashboard_key, dashboardWidgets]);

  useEffect(() => {
    const widget = selectedWidget;
    if (!widget) return;
    setWidgetDraft(widgetDraftFromWidget(widget));
  }, [selectedWidget?.widget_key, selectedWidget?.title, selectedWidget?.widget_type, selectedWidget?.table_key, selectedWidget?.config]);

  useEffect(() => {
    setWidgetFilterField((current) => fieldModel.draftDimensions.some((field) => field.field_name === current) ? current : fieldModel.draftDimensions[0]?.field_name ?? fieldModel.draftFields[0]?.field_name ?? "");
  }, [fieldModel.draftDimensions, fieldModel.draftFields, selectedWidget?.widget_key]);

  return {
    ...fieldModel,
    canvasWidthMode,
    draftName,
    filterField,
    filterOperator,
    filterValue,
    selectedRelationship,
    selectedRelationshipKey,
    selectedViewKey,
    selectedWidget,
    setCanvasWidthMode,
    setDraftName,
    setFilterField,
    setFilterOperator,
    setFilterValue,
    setSelectedRelationshipKey,
    setSelectedViewKey,
    setSelectedWidgetKey,
    setSourceSwitchTableKey,
    setWidgetDraft,
    setWidgetFilterField,
    setWidgetFilterOperator,
    setWidgetFilterValue,
    sourceSwitchTable,
    sourceSwitchTableKey,
    widgetDraft,
    widgetFilterField,
    widgetFilterOperator,
    widgetFilterValue,
    widgetFilters,
  };
}
