import { useEffect, useMemo, useState } from "react";
import { queryRelationship, runTableQuery } from "../api";
import {
  type BiDashboardDatum,
  type BiDashboardFilterRule,
  type BiDashboardWidget,
} from "../biDashboardModel";
import { catalogByType, formatWidgetValue, paletteColors } from "../biDashboardPresentation";
import { aggregateWidgetRows, calculateWidgetMetricValue } from "../biDashboardRuntime";
import type { QueryResult, TableQueryPayload } from "../types";
import { Bilingual, biText } from "./Bilingual";
import type { DrilldownPointFilter } from "./BiDashboardDrilldownSheet";

export type SlicerSelections = Record<string, string[]>;

type BiDashboardWidgetCardProps = {
  widget: BiDashboardWidget;
  query: QueryResult;
  dashboardFilters: BiDashboardFilterRule[];
  slicerSelections: SlicerSelections;
  onDrillDown: (widget: BiDashboardWidget, pointFilter?: DrilldownPointFilter) => void;
  onOpenEvidence: (widget: BiDashboardWidget) => void;
  onSlicerChange: (widget: BiDashboardWidget, value: string) => void;
};

export function BiDashboardWidgetCard({
  widget,
  query,
  dashboardFilters,
  slicerSelections,
  onDrillDown,
  onOpenEvidence,
  onSlicerChange,
}: BiDashboardWidgetCardProps) {
  const [relationshipQuery, setRelationshipQuery] = useState<QueryResult | null>(null);
  const [widgetQuery, setWidgetQuery] = useState<QueryResult | null>(null);
  const [widgetQueryState, setWidgetQueryState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const slicerField = widget.dimension || "label";
  const filtersForWidget = useMemo(() => widget.type === "slicer"
    ? dashboardFilters.filter((filter) => filter.field !== slicerField)
    : dashboardFilters, [dashboardFilters, slicerField, widget.type]);
  const widgetQueryRequest = useMemo(() => {
    if (widget.dataMode === "relationship" || (!widget.tableKey && !widget.viewKey)) return null;
    const groupFields = widget.dimension && widget.dimension !== "label" ? [widget.dimension] : [];
    const filters = [...filtersForWidget, ...widget.filters].map((filter) => ({
      field: filter.field,
      operator: filter.operator,
      value: filter.value,
    }));
    return {
      table: widget.viewKey ? undefined : widget.tableKey,
      view: widget.viewKey || undefined,
      mode: "aggregate" as const,
      groupFields,
      measure: widget.aggregation === "count" ? undefined : widget.measure || undefined,
      aggregation: widget.aggregation,
      filters,
      sort: widget.sortBy === "dimension" && groupFields.length
        ? [{ field: groupFields[0], direction: widget.sortDirection }]
        : undefined,
      limit: Math.max(widget.topN, 50),
    };
  }, [filtersForWidget, widget.aggregation, widget.dataMode, widget.dimension, widget.filters, widget.measure, widget.sortBy, widget.sortDirection, widget.tableKey, widget.topN, widget.viewKey]);

  useEffect(() => {
    if (widget.dataMode !== "relationship" || !widget.relationship) {
      setRelationshipQuery(null);
      return;
    }
    let cancelled = false;
    const group = widget.relationship.groupFields[0];
    const measure = widget.relationship.measure;
    const filters = [...filtersForWidget, ...widget.filters].map((filter) => ({
      field: filter.field,
      operator: filter.operator,
      value: filter.value,
    }));
    void queryRelationship({
      relationship: widget.relationship.relationKey,
      leftTable: widget.relationship.leftTableKey,
      rightTable: widget.relationship.rightTableKey,
      leftField: widget.relationship.fieldMappings[0]?.leftField,
      rightField: widget.relationship.fieldMappings[0]?.rightField,
      group: group ? `${group.side}:${group.field}` : undefined,
      measure: measure ? `${measure.side}:${measure.field}` : undefined,
      aggregation: widget.relationship.aggregation ?? widget.aggregation,
      filters,
      limit: widget.topN,
      sortBy: widget.sortBy,
      sortDirection: widget.sortDirection,
    }).then((result) => {
      if (!cancelled) setRelationshipQuery(result);
    });
    return () => {
      cancelled = true;
    };
  }, [filtersForWidget, widget]);

  useEffect(() => {
    if (!widgetQueryRequest) {
      setWidgetQuery(null);
      setWidgetQueryState("idle");
      return;
    }
    let cancelled = false;
    setWidgetQueryState("loading");
    setWidgetQuery(null);
    void runTableQuery(widgetQueryRequest).then((result) => {
      if (cancelled) return;
      setWidgetQuery(tableQueryToQueryResult(result, widget));
      setWidgetQueryState(result.ok ? "ready" : "error");
    }).catch(() => {
      if (!cancelled) setWidgetQueryState("error");
    });
    return () => {
      cancelled = true;
    };
  }, [widget, widgetQueryRequest]);

  const sourceQuery = widget.dataMode === "relationship" && relationshipQuery?.ok
    ? relationshipQuery
    : widgetQueryRequest
      ? widgetQuery ?? emptyWidgetQuery(widget)
      : query;
  const renderWidget = widgetQueryRequest ? { ...widget, filters: [] } : widget;
  const rows = aggregateWidgetRows(renderWidget, sourceQuery, widget.dataMode === "relationship" || widgetQueryRequest ? [] : filtersForWidget);
  const className = `bWidgetCard ${widget.type}-widget`;
  const pointField = widget.dimension || sourceQuery.query?.group || "label";
  const handlePoint = (row: BiDashboardDatum) => onDrillDown(widget, { field: pointField, value: row.label });

  return (
    <section className={className} data-testid={`b-widget-${widget.type}`}>
      <WidgetHeader onDrillDown={() => onDrillDown(widget)} onOpenEvidence={() => onOpenEvidence(widget)} widget={widget} />
      {widgetQueryRequest && widgetQueryState !== "ready" ? (
        <WidgetDataState state={widgetQueryState} />
      ) : (
        <>
          {widget.type === "metric" ? <MetricWidget dashboardFilters={widget.dataMode === "relationship" || widgetQueryRequest ? [] : filtersForWidget} query={sourceQuery} widget={renderWidget} /> : null}
          {widget.type === "bar" ? <BarWidget onPointClick={handlePoint} rows={rows} widget={renderWidget} /> : null}
          {widget.type === "line" ? <LineWidget rows={rows} widget={renderWidget} /> : null}
          {widget.type === "pie" ? <PieWidget onPointClick={handlePoint} rows={rows} widget={renderWidget} /> : null}
          {widget.type === "table" ? <TableWidget rows={rows} widget={renderWidget} /> : null}
          {widget.type === "text" ? <TextWidget widget={widget} /> : null}
          {widget.type === "slicer" ? (
            <SlicerWidget
              onPointClick={handlePoint}
              onSlicerChange={onSlicerChange}
              rows={rows}
              selectedValues={slicerSelections[slicerField] ?? []}
              widget={renderWidget}
            />
          ) : null}
        </>
      )}
    </section>
  );
}

function emptyWidgetQuery(widget: BiDashboardWidget): QueryResult {
  return {
    ok: true,
    query: {
      table: widget.tableKey ?? "",
      mode: "aggregate",
      group: widget.dimension,
      measure: widget.measure ?? "value",
      aggregation: widget.aggregation,
      sqlIntent: "Waiting for widget query runtime",
    },
    rows: [],
  };
}

function tableQueryToQueryResult(result: TableQueryPayload, widget: BiDashboardWidget): QueryResult {
  const tableQuery = result.tableQuery;
  const columns = Array.isArray(tableQuery?.columns) ? tableQuery.columns : [];
  const groupField = widget.dimension && widget.dimension !== "label" && columns.includes(widget.dimension) ? widget.dimension : "";
  const valueColumn = columns.find((column) => column.startsWith(`${widget.aggregation}_`)) ?? columns[columns.length - 1] ?? "";
  return {
    ok: result.ok,
    query: {
      table: tableQuery?.tableKey ?? widget.tableKey ?? "",
      mode: "aggregate",
      group: groupField || undefined,
      measure: (widget.measure ?? valueColumn) || "value",
      aggregation: widget.aggregation,
      sqlIntent: tableQuery?.sqlIntent ?? "Widget aggregate query",
      runtime: tableQuery?.runtime ? {
        engine: tableQuery.runtime.engine,
        database: "",
        compiledSql: tableQuery.runtime.compiledSql,
      } : undefined,
    },
    rows: (Array.isArray(tableQuery?.rows) ? tableQuery.rows : []).map((raw, index) => {
      const fallbackValue = Object.values(raw)[Object.values(raw).length - 1] ?? 0;
      const rawValue = valueColumn ? raw[valueColumn] ?? fallbackValue : fallbackValue;
      const rawLabel = groupField ? raw[groupField] : (widget.measure ?? valueColumn) || `Result ${index + 1}`;
      return { label: String(rawLabel ?? `Result ${index + 1}`), value: rawValue as number | string | null };
    }),
  };
}

function WidgetDataState({ state }: { state: "idle" | "loading" | "ready" | "error" }) {
  return (
    <div className="bWidgetDataState" data-testid={`b-widget-data-${state}`}>
      <strong>{state === "error" ? biText("结果暂不可用", "Result unavailable") : biText("正在读取真实数据", "Reading live data")}</strong>
      <span>{state === "error" ? biText("请检查字段口径或重新生成证据摘要。", "Check field bindings or regenerate the evidence summary.") : biText("不会用默认数字替代查询结果。", "No default number is shown before the query returns.")}</span>
    </div>
  );
}

function WidgetHeader({ widget, onDrillDown, onOpenEvidence }: { widget: BiDashboardWidget; onDrillDown: () => void; onOpenEvidence: () => void }) {
  const catalog = catalogByType(widget.type);
  return (
    <header className="bWidgetHead">
      <div>
        <span className="bWidgetTypeChip">
          <Bilingual {...catalog.label} />
        </span>
        <h4>{widget.title}</h4>
        {widget.subtitle ? <p>{widget.subtitle}</p> : null}
      </div>
      <div className="bWidgetMeta">
        {widget.filters.length ? <span>{biText(`${widget.filters.length} 筛选`, `${widget.filters.length} filters`)}</span> : null}
        {widget.evidence.length ? (
          <button className="bEvidenceButton" data-testid={`b-widget-evidence-${widget.id}`} onClick={onOpenEvidence} type="button">
            {biText("查看证据", "Review evidence")}
          </button>
        ) : null}
        {widget.drillDown ? (
          <button data-testid={`b-drilldown-open-${widget.id}`} onClick={onDrillDown} type="button">
            {biText("明细", "Detail")}
          </button>
        ) : null}
      </div>
    </header>
  );
}

function MetricWidget({ widget, query, dashboardFilters }: { widget: BiDashboardWidget; query: QueryResult; dashboardFilters: BiDashboardFilterRule[] }) {
  const value = calculateWidgetMetricValue(widget, query, dashboardFilters);
  const aggregationLabel = aggregationText(widget.aggregation);
  return (
    <>
      <strong className="bMetricValue">{formatWidgetValue(value, widget)}</strong>
      <footer className="bMetricFoot">
        <span>{aggregationLabel}</span>
        <em>{prettyMeasure(widget.measure ?? query.query?.measure)}</em>
      </footer>
    </>
  );
}

function BarWidget({ widget, rows, onPointClick }: { widget: BiDashboardWidget; rows: BiDashboardDatum[]; onPointClick: (row: BiDashboardDatum) => void }) {
  const max = Math.max(...rows.map((row) => Math.abs(row.value)), 1);
  return (
    <div className={widget.barOrientation === "horizontal" ? "bBarChart horizontal" : "bBarChart vertical"}>
      {rows.map((row, index) => {
        const height = `${Math.max(8, (Math.abs(row.value) / max) * 100)}%`;
        const width = `${Math.max(8, (Math.abs(row.value) / max) * 100)}%`;
        return (
          <button aria-label={biText(`${row.label}，${formatWidgetValue(row.value, widget)}，查看明细`, `${row.label}, ${formatWidgetValue(row.value, widget)}, view details`)} className="bBarItem" key={`${row.label}-${index}`} onClick={() => onPointClick(row)} type="button">
            <span>{widget.rankingMode === "ranked" ? `${index + 1}. ${row.label}` : row.label}</span>
            <div className="bBarTrack">
              <div className="bBarFill" style={widget.barOrientation === "horizontal" ? { width } : { height }} />
            </div>
            {widget.showDataLabel ? <em>{formatWidgetValue(row.value, widget)}</em> : null}
          </button>
        );
      })}
    </div>
  );
}

function LineWidget({ widget, rows }: { widget: BiDashboardWidget; rows: BiDashboardDatum[] }) {
  const points = linePoints(rows);
  const color = paletteColors(widget.colorPalette)[0];
  const area = `${points} 100,100 0,100`;
  return (
    <div className="bLineWrap">
      <span className="srOnly">
        {biText("折线图数据：", "Line chart data: ")}
        {rows.map((row) => `${row.label} ${formatWidgetValue(row.value, widget)}`).join("；")}
      </span>
      <svg className="bLineSvg" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {widget.areaFill ? <polygon points={area} fill={color} opacity="0.12" /> : null}
        <polyline points={points} fill="none" stroke={color} strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" />
      </svg>
      <div className="bLineAxis">
        <span>{rows[0]?.label ?? ""}</span>
        <span>{rows[rows.length - 1]?.label ?? ""}</span>
      </div>
    </div>
  );
}

function PieWidget({ widget, rows, onPointClick }: { widget: BiDashboardWidget; rows: BiDashboardDatum[]; onPointClick: (row: BiDashboardDatum) => void }) {
  const colors = paletteColors(widget.colorPalette);
  const total = rows.reduce((sum, row) => sum + Math.max(0, row.value), 0) || 1;
  let cursor = 0;
  const gradient = rows.map((row, index) => {
    const start = cursor;
    const size = (Math.max(0, row.value) / total) * 100;
    cursor += size;
    return `${colors[index % colors.length]} ${start}% ${cursor}%`;
  }).join(", ");
  return (
    <div className="bPieWrap">
      <div className={widget.pieShape === "pie" ? "bPieChart pie" : "bPieChart donut"} style={{ background: `conic-gradient(${gradient})` }} />
      <div className="bPieLegend">
        {rows.slice(0, 5).map((row, index) => (
          <button aria-label={biText(`${row.label}，${formatWidgetValue(row.value, widget)}，查看明细`, `${row.label}, ${formatWidgetValue(row.value, widget)}, view details`)} key={`${row.label}-${index}`} onClick={() => onPointClick(row)} type="button">
            <i style={{ background: colors[index % colors.length] }} />
            <span>{row.label}</span>
            <small>{formatWidgetValue(row.value, widget)}</small>
          </button>
        ))}
      </div>
    </div>
  );
}

function TableWidget({ widget, rows }: { widget: BiDashboardWidget; rows: BiDashboardDatum[] }) {
  return (
    <div className="bTableWrap">
      <table>
        <thead>
          <tr>
            <th>{biText("维度", "Dimension")}</th>
            <th>{biText("数值", "Value")}</th>
            <th>{biText("排名", "Rank")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.slice(0, widget.tableColumnLimit).map((row, index) => (
            <tr key={`${row.label}-${index}`}>
              <td>{row.label}</td>
              <td>{formatWidgetValue(row.value, widget)}</td>
              <td>{index + 1}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TextWidget({ widget }: { widget: BiDashboardWidget }) {
  return (
    <div className="bTextBlock">
      <p>{widget.textContent}</p>
      <div className="bEvidenceChips">
        {widget.evidence.slice(0, 5).map((item) => (
          <span key={item}>{item}</span>
        ))}
      </div>
    </div>
  );
}

function SlicerWidget({
  widget,
  rows,
  selectedValues,
  onSlicerChange,
}: {
  widget: BiDashboardWidget;
  rows: BiDashboardDatum[];
  selectedValues: string[];
  onPointClick: (row: BiDashboardDatum) => void;
  onSlicerChange: (widget: BiDashboardWidget, value: string) => void;
}) {
  const labels = [...new Set(rows.map((row) => row.label))].slice(0, 8);
  if (widget.slicerDisplay === "dropdown") {
    return (
      <div className="bSlicerDropdown">
        <select
          aria-label={biText(`${widget.title} 筛选`, `${widget.title} filter`)}
          data-testid={`b-slicer-select-${widget.id}`}
          value={selectedValues[0] ?? ""}
          onChange={(event) => {
            if (event.target.value) onSlicerChange(widget, event.target.value);
          }}
        >
          <option value="">{biText("全部", "All")}</option>
          {labels.map((label) => <option key={label}>{label}</option>)}
        </select>
        {selectedValues.length ? <small>{biText("已联动其他组件", "Linked to other widgets")}</small> : null}
      </div>
    );
  }
  if (widget.slicerDisplay === "range") {
    const values = rows.map((row) => row.value);
    return (
      <div className="bSlicerRange">
        <label>
          <span>{biText("最小", "Min")}</span>
          <input readOnly value={Math.min(...values, 0)} />
        </label>
        <label>
          <span>{biText("最大", "Max")}</span>
          <input readOnly value={Math.max(...values, 0)} />
        </label>
      </div>
    );
  }
  return (
    <div className="bSlicerOptions">
      {labels.map((label, index) => (
        <button
          className={selectedValues.includes(label) ? "active" : ""}
          data-testid={`b-slicer-option-${widget.id}-${index}`}
          key={label}
          onClick={() => {
            onSlicerChange(widget, label);
          }}
          type="button"
        >
          <span>{label}</span>
          <em>{selectedValues.includes(label) ? biText("已选", "Selected") : biText("筛选", "Filter")}</em>
        </button>
      ))}
      {!labels.length ? <p>{biText("暂无可筛选项", "No slicer options")}</p> : null}
    </div>
  );
}

function linePoints(rows: BiDashboardDatum[]): string {
  if (!rows.length) return "0,50 100,50";
  const values = rows.map((row) => row.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1, max - min);
  return rows.map((row, index) => {
    const x = rows.length === 1 ? 50 : (index / (rows.length - 1)) * 100;
    const y = 88 - ((row.value - min) / span) * 76;
    return `${x.toFixed(2)},${y.toFixed(2)}`;
  }).join(" ");
}

function aggregationText(value: BiDashboardWidget["aggregation"]) {
  const labels: Record<BiDashboardWidget["aggregation"], string> = {
    count: biText("计数", "Count"),
    sum: biText("合计", "Total"),
    avg: biText("平均", "Average"),
    max: biText("最高", "Max"),
    min: biText("最低", "Min"),
  };
  return labels[value] ?? value;
}

function prettyMeasure(value?: string) {
  if (!value) return biText("指标", "Measure");
  const labels: Record<string, string> = {
    quantity: biText("数量", "Quantity"),
    value: biText("数值", "Value"),
  };
  return labels[value] ?? value.replace(/_/g, " ");
}
