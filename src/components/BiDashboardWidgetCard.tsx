import { useEffect, useMemo, useState } from "react";
import { queryRelationship } from "../api";
import {
  type BiDashboardDatum,
  type BiDashboardFilterRule,
  type BiDashboardWidget,
} from "../biDashboardModel";
import { catalogByType, formatWidgetValue, paletteColors } from "../biDashboardPresentation";
import { aggregateWidgetRows, calculateWidgetMetricValue } from "../biDashboardRuntime";
import type { QueryResult } from "../types";
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
  const slicerField = widget.dimension || "label";
  const filtersForWidget = useMemo(() => widget.type === "slicer"
    ? dashboardFilters.filter((filter) => filter.field !== slicerField)
    : dashboardFilters, [dashboardFilters, slicerField, widget.type]);

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

  const sourceQuery = widget.dataMode === "relationship" && relationshipQuery?.ok ? relationshipQuery : query;
  const rows = aggregateWidgetRows(widget, sourceQuery, widget.dataMode === "relationship" ? [] : filtersForWidget);
  const className = `bWidgetCard ${widget.type}-widget`;
  const pointField = widget.dimension || sourceQuery.query?.group || "label";
  const handlePoint = (row: BiDashboardDatum) => onDrillDown(widget, { field: pointField, value: row.label });

  return (
    <section className={className} data-testid={`b-widget-${widget.type}`}>
      <WidgetHeader onDrillDown={() => onDrillDown(widget)} onOpenEvidence={() => onOpenEvidence(widget)} widget={widget} />
      {widget.type === "metric" ? <MetricWidget dashboardFilters={widget.dataMode === "relationship" ? [] : filtersForWidget} query={sourceQuery} widget={widget} /> : null}
      {widget.type === "bar" ? <BarWidget onPointClick={handlePoint} rows={rows} widget={widget} /> : null}
      {widget.type === "line" ? <LineWidget rows={rows} widget={widget} /> : null}
      {widget.type === "pie" ? <PieWidget onPointClick={handlePoint} rows={rows} widget={widget} /> : null}
      {widget.type === "table" ? <TableWidget rows={rows} widget={widget} /> : null}
      {widget.type === "text" ? <TextWidget widget={widget} /> : null}
      {widget.type === "slicer" ? (
        <SlicerWidget
          onPointClick={handlePoint}
          onSlicerChange={onSlicerChange}
          rows={rows}
          selectedValues={slicerSelections[slicerField] ?? []}
          widget={widget}
        />
      ) : null}
    </section>
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
          <button className="bBarItem" key={`${row.label}-${index}`} onClick={() => onPointClick(row)} type="button">
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
          <button key={`${row.label}-${index}`} onClick={() => onPointClick(row)} type="button">
            <i style={{ background: colors[index % colors.length] }} />
            {row.label}
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
    net_sales: biText("净销售额", "Net sales"),
    refund_amount: biText("退款金额", "Refund amount"),
    quantity: biText("数量", "Quantity"),
    value: biText("数值", "Value"),
  };
  return labels[value] ?? value.replace(/_/g, " ");
}
