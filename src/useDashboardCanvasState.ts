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
  const [widgetOrder, setWidgetOrder] = useState<string[]>([]);
  const [sourceSwitchTableKey, setSourceSwitchTableKey] = useState(dashboard.default_table_key);
  const [canvasWidthMode, setCanvasWidthMode] = useState<DashboardCanvasWidthMode>(dashboard.layout?.canvasWidthMode === "center" ? "center" : "stretch");
  const [widgetFilterField, setWidgetFilterField] = useState("");
  const [widgetFilterOperator, setWidgetFilterOperator] = useState("equals");
  const [widgetFilterValue, setWidgetFilterValue] = useState("");
  const [widgetDraft, setWidgetDraft] = useState<WidgetDraft>(() => defaultWidgetDraft());
  const [guidedEditorMounted, setGuidedEditorMounted] = useState(false);
  const [advancedEditorMounted, setAdvancedEditorMounted] = useState(false);
  const [contractPanelMounted, setContractPanelMounted] = useState(false);

  const orderedWidgets = useMemo(() => {
    const byKey = new Map(dashboardWidgets.map((widget) => [widget.widget_key, widget]));
    return [
      ...widgetOrder.map((key) => byKey.get(key)).filter((widget): widget is DashboardWidget => Boolean(widget)),
      ...dashboardWidgets.filter((widget) => !widgetOrder.includes(widget.widget_key)),
    ];
  }, [dashboardWidgets, widgetOrder]);
  const selectedWidget = useMemo(
    () => orderedWidgets.find((widget) => widget.widget_key === selectedWidgetKey) ?? orderedWidgets[0],
    [orderedWidgets, selectedWidgetKey],
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
    const available = dashboardWidgets.map((widget) => widget.widget_key);
    setWidgetOrder((current) => {
      const next = [
        ...current.filter((key) => available.includes(key)),
        ...available.filter((key) => !current.includes(key)),
      ];
      return current.length === next.length && current.every((key, index) => key === next[index]) ? current : next;
    });
    setSelectedWidgetKey((current) => available.includes(current) ? current : available[0] ?? "");
  }, [dashboard.dashboard_key, dashboardWidgets]);

  function moveWidget(widgetKey: string, targetIndex: number) {
    setWidgetOrder((current) => {
      const available = dashboardWidgets.map((widget) => widget.widget_key);
      const ordered = [
        ...current.filter((key) => available.includes(key)),
        ...available.filter((key) => !current.includes(key)),
      ];
      const sourceIndex = ordered.indexOf(widgetKey);
      if (sourceIndex < 0) return ordered;
      const boundedTarget = Math.max(0, Math.min(targetIndex, ordered.length - 1));
      const next = [...ordered];
      next.splice(sourceIndex, 1);
      next.splice(boundedTarget, 0, widgetKey);
      return next;
    });
  }

  useEffect(() => {
    const widget = selectedWidget;
    if (!widget) return;
    setWidgetDraft(widgetDraftFromWidget(widget));
  }, [selectedWidget?.widget_key, selectedWidget?.title, selectedWidget?.widget_type, selectedWidget?.table_key, selectedWidget?.config]);

  useEffect(() => {
    setWidgetFilterField((current) => fieldModel.draftDimensions.some((field) => field.field_name === current) ? current : fieldModel.draftDimensions[0]?.field_name ?? fieldModel.draftFields[0]?.field_name ?? "");
  }, [fieldModel.draftDimensions, fieldModel.draftFields, selectedWidget?.widget_key]);

  return {
    advancedEditorMounted,
    contractPanelMounted,
    ...fieldModel,
    canvasWidthMode,
    draftName,
    filterField,
    filterOperator,
    filterValue,
    guidedEditorMounted,
    moveWidget,
    orderedWidgets,
    selectedRelationship,
    selectedRelationshipKey,
    selectedViewKey,
    selectedWidget,
    setCanvasWidthMode,
    setAdvancedEditorMounted,
    setContractPanelMounted,
    setDraftName,
    setFilterField,
    setFilterOperator,
    setFilterValue,
    setGuidedEditorMounted,
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
