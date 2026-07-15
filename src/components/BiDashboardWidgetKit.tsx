import { useEffect, useMemo, useState } from "react";
import { runTableQuery, saveView } from "../api";
import {
  buildBiDashboardWidgets,
  normalizeBiDashboardFilters,
  type BiDashboardFilterRule,
  type BiDashboardWidget,
} from "../biDashboardModel";
import type { DashboardPage, DashboardPayload, EvidenceFocus, QueryResult, TableQueryPayload, WorkbenchPayload } from "../types";
import { latestUsableSourceIntelligenceRun } from "../workspaceFlowModel";
import { biText } from "./Bilingual";
import { BiDashboardDrilldownSheet, type DrilldownOperationReceipt, type DrilldownPointFilter, type DrilldownState } from "./BiDashboardDrilldownSheet";
import { BiDashboardWidgetCard, type SlicerSelections } from "./BiDashboardWidgetCard";
import { BiDashboardWidgetKitOverview } from "./BiDashboardWidgetKitOverview";

type BiDashboardWidgetKitProps = {
  dashboard: DashboardPage;
  dashboards: DashboardPayload;
  query: QueryResult;
  workbench: WorkbenchPayload;
  onOpenEvidence?: (focus: EvidenceFocus) => void;
};

export function BiDashboardWidgetKit({ dashboard, dashboards, query, workbench, onOpenEvidence }: BiDashboardWidgetKitProps) {
  const widgets = useMemo(() => buildBiDashboardWidgets({ dashboard, dashboards, query, workbench }), [dashboard, dashboards, query, workbench]);
  const widgetTypeSet = useMemo(() => new Set(widgets.map((widget) => widget.type)), [widgets]);
  const sourceIntelligenceRuns = Array.isArray(workbench.sourceIntelligenceRuns) ? workbench.sourceIntelligenceRuns : [];
  const latestRun = latestUsableSourceIntelligenceRun(sourceIntelligenceRuns);
  const evidenceState = latestRun
    ? biText(`证据来自 ${latestRun.label}`, `Evidence from ${latestRun.label}`)
    : biText("先生成证据摘要，证据会自动挂到结果卡片上", "Create an evidence summary first; evidence will attach to result cards automatically");
  const dashboardFilters = useMemo(() => normalizeBiDashboardFilters(dashboard.layout?.globalFilters), [dashboard.layout?.globalFilters]);
  const [drilldown, setDrilldown] = useState<DrilldownState | null>(null);
  const [drilldownSearch, setDrilldownSearch] = useState("");
  const [drilldownResult, setDrilldownResult] = useState<TableQueryPayload | null>(null);
  const [drilldownBusy, setDrilldownBusy] = useState(false);
  const [drilldownSaveResult, setDrilldownSaveResult] = useState<Record<string, unknown> | null>(null);
  const [drilldownReceipt, setDrilldownReceipt] = useState<DrilldownOperationReceipt | null>(null);
  const [slicerSelections, setSlicerSelections] = useState<SlicerSelections>({});
  const slicerFilters = useMemo(() => Object.entries(slicerSelections)
    .filter(([, values]) => values.length)
    .map(([field, values], index): BiDashboardFilterRule => ({
      id: `slicer-${field}-${index}`,
      field,
      operator: values.length > 1 ? "in" : "equals",
      value: values.join(","),
      enabled: true,
    })), [slicerSelections]);
  const effectiveDashboardFilters = useMemo(() => [...dashboardFilters, ...slicerFilters], [dashboardFilters, slicerFilters]);
  const drilldownRequest = useMemo(() => {
    if (!drilldown) return null;
    const widget = drilldown.widget;
    const savedView = widget.viewKey ? workbench.savedViews.find((view) => view.view_key === widget.viewKey) : undefined;
    const table = savedView?.table_key || widget.relationship?.leftTableKey || widget.tableKey || dashboard.default_table_key;
    if (!table) return null;
    const tableFields = workbench.fields.filter((field) => field.table_key === table).map((field) => field.field_name);
    const viewColumns = Array.isArray(savedView?.config?.columns) ? savedView.config.columns.map(String) : [];
    const columns = (viewColumns.length ? viewColumns : tableFields).filter(Boolean).slice(0, Math.max(6, widget.tableColumnLimit || 6));
    const columnSet = new Set(columns.length ? columns : tableFields);
    const filters = [...effectiveDashboardFilters, ...widget.filters]
      .filter((filter) => columnSet.has(filter.field))
      .map((filter) => ({ field: filter.field, operator: filter.operator, value: filter.value }));
    if (drilldown.pointFilter && columnSet.has(drilldown.pointFilter.field)) {
      filters.push({ field: drilldown.pointFilter.field, operator: "equals", value: drilldown.pointFilter.value });
    }
    const sortField = columns.includes(widget.dimension ?? "") ? widget.dimension : columns[0];
    return {
      table,
      view: savedView?.view_key,
      mode: "detail" as const,
      columns,
      filters,
      search: drilldownSearch,
      sort: sortField ? [{ field: sortField, direction: widget.sortDirection }] : [],
      limit: 25,
    };
  }, [dashboard.default_table_key, drilldown, drilldownSearch, effectiveDashboardFilters, workbench.fields, workbench.savedViews]);

  useEffect(() => {
    setSlicerSelections({});
  }, [dashboard.dashboard_key]);

  useEffect(() => {
    if (!drilldownRequest) {
      setDrilldownResult(null);
      return;
    }
    let cancelled = false;
    setDrilldownBusy(true);
    void runTableQuery(drilldownRequest).then((result) => {
      if (!cancelled) setDrilldownResult(result);
    }).finally(() => {
      if (!cancelled) setDrilldownBusy(false);
    });
    return () => {
      cancelled = true;
    };
  }, [drilldownRequest]);

  async function saveDrilldownAsView(confirm: boolean) {
    if (!drilldown || !drilldownRequest) return;
    const viewTitle = `${drilldown.widget.title} ${biText("下钻明细", "drilldown detail")}`;
    const result = await saveView({
      table: drilldownRequest.table,
      name: viewTitle,
      tag: biText("看板下钻", "Dashboard drilldown"),
      mode: "detail",
      columns: drilldownRequest.columns,
      filters: drilldownRequest.filters,
      sort: drilldownRequest.sort,
      search: drilldownRequest.search,
      agent: false,
      confirm,
    });
    setDrilldownSaveResult(result);
    setDrilldownReceipt({
      title: confirm ? biText("下钻视图已保存", "Drilldown view saved") : biText("下钻视图保存已预演", "Drilldown view save previewed"),
      detail: confirm
        ? biText(`「${viewTitle}」会保留当前点位、筛选、搜索和排序，后续可在视图页继续翻页和问 Agent。`, `"${viewTitle}" keeps the current point, filters, search, and sort for paging and Agent questions in Views.`)
        : biText("这次只预演保存，不会创建视图；先确认明细行和筛选口径是否正确。", "This only previews saving and does not create a view. Confirm detail rows and filter scope first."),
      nextStep: confirm ? biText("下一步到视图页复核明细，或把这个视图用于新的看板组件。", "Next, review rows in Views or use this view in a new dashboard widget.") : biText("确认行级证据无误后再保存视图。", "Save the view after row-level evidence looks right."),
      technical: `table=${drilldownRequest.table}; view=${drilldownRequest.view ?? "-"}; columns=${drilldownRequest.columns.join(",")}; filters=${drilldownRequest.filters.length}; sort=${drilldownRequest.sort.length}; limit=${drilldownRequest.limit}; confirm=${confirm}`,
      tone: confirm ? "ok" : "warn",
    });
  }

  function openWidgetDrilldown(widget: BiDashboardWidget, pointFilter?: DrilldownPointFilter) {
    if (!widget.drillDown || widget.type === "text" || widget.type === "slicer" && !pointFilter) return;
    setDrilldown({ widget, pointFilter });
    setDrilldownSaveResult(null);
    setDrilldownReceipt(null);
  }

  function openWidgetEvidence(widget: BiDashboardWidget) {
    onOpenEvidence?.({
      source: "dashboard-widget",
      title: widget.title,
      subtitle: biText("看板组件证据", "Dashboard widget evidence"),
      refs: widget.evidence,
      dashboardKey: dashboard.dashboard_key,
      tableKey: widget.tableKey || dashboard.default_table_key,
      widgetType: widget.type,
      detail: {
        dashboardName: dashboard.name,
        dataMode: widget.dataMode,
        dimension: widget.dimension,
        measure: widget.measure,
        aggregation: widget.aggregation,
        filters: widget.filters,
        relationship: widget.relationship,
      },
    });
  }

  function updateSlicerSelection(widget: BiDashboardWidget, value: string) {
    const field = widget.dimension || "label";
    setSlicerSelections((current) => {
      const existing = current[field] ?? [];
      const nextValues = widget.slicerMultiSelect
        ? existing.includes(value)
          ? existing.filter((item) => item !== value)
          : [...existing, value]
        : existing.includes(value)
          ? []
          : [value];
      const next = { ...current };
      if (nextValues.length) next[field] = nextValues;
      else delete next[field];
      return next;
    });
  }

  function clearSlicerSelection(field?: string) {
    setSlicerSelections((current) => {
      if (!field) return {};
      const next = { ...current };
      delete next[field];
      return next;
    });
  }

  return (
    <article className="bDashboardKit wide" aria-labelledby="b-dashboard-kit-title">
      <BiDashboardWidgetKitOverview
        dashboard={dashboard}
        evidenceState={evidenceState}
        latestRun={latestRun}
        onOpenEvidence={onOpenEvidence}
        widgetTypeSet={widgetTypeSet}
      />

      {slicerFilters.length ? (
        <div className="bSlicerSelectionBar" data-testid="b-slicer-selection-bar">
          <span>{biText("当前切片", "Active slicers")}</span>
          {slicerFilters.map((filter) => (
            <button key={filter.id} onClick={() => clearSlicerSelection(filter.field)} type="button">
              <strong>{filter.field}</strong>
              <em>{filter.value}</em>
            </button>
          ))}
          <button className="clearAll" onClick={() => clearSlicerSelection()} type="button">{biText("清空", "Clear")}</button>
        </div>
      ) : null}

      <div className={`bWidgetGrid${widgets.length === 1 && widgets[0]?.type === "metric" ? " singleMetric" : ""}`}>
        {widgets.map((widget) => (
          <BiDashboardWidgetCard
            dashboardFilters={effectiveDashboardFilters}
            key={widget.id}
            onDrillDown={openWidgetDrilldown}
            onOpenEvidence={openWidgetEvidence}
            onSlicerChange={updateSlicerSelection}
            query={query}
            slicerSelections={slicerSelections}
            widget={widget}
          />
        ))}
      </div>
      {drilldown ? (
        <BiDashboardDrilldownSheet
          drilldown={drilldown}
          drilldownBusy={drilldownBusy}
          drilldownReceipt={drilldownReceipt}
          drilldownRequest={drilldownRequest}
          drilldownResult={drilldownResult}
          drilldownSaveResult={drilldownSaveResult}
          drilldownSearch={drilldownSearch}
          onClose={() => setDrilldown(null)}
          onSaveView={saveDrilldownAsView}
          onSearchChange={setDrilldownSearch}
        />
      ) : null}
    </article>
  );
}
