import { useId, useMemo, useState, type KeyboardEvent } from "react";
import type { AnalysisUnit, ChartAdapter, QueryPlanReceipt } from "../typesAgent";
import { useLanguage } from "./Bilingual";
import {
  buildAgentVisualizationModel,
  tableCellText,
  type AgentVisualizationModel,
  type AgentVisualizationPoint,
} from "./agentAnswerVisualizationModel";
import "./AgentAnswerVisualization.css";

type AgentAnswerVisualizationProps = {
  analysisUnit: AnalysisUnit;
  chartAdapter: ChartAdapter;
  evidenceRefs: Array<Record<string, unknown>>;
  queryPlanReceipt: QueryPlanReceipt;
  title: string;
};

const categoryColors = [
  "var(--chart-category-1)",
  "var(--chart-category-2)",
  "var(--chart-category-3)",
  "var(--chart-category-4)",
  "var(--chart-category-5)",
  "var(--chart-category-6)",
];

function formatNumber(value: number, compact = false) {
  return new Intl.NumberFormat("zh-CN", {
    maximumFractionDigits: compact ? 1 : 2,
    notation: compact && Math.abs(value) >= 10_000 ? "compact" : "standard",
  }).format(value);
}

function formatPercent(value: number) {
  return new Intl.NumberFormat("zh-CN", { style: "percent", maximumFractionDigits: 1 }).format(value);
}

function truncateLabel(value: string, length = 12) {
  return value.length > length ? `${value.slice(0, length - 1)}…` : value;
}

function useChartKeyboard(points: AgentVisualizationPoint[], language: "zh" | "en", chartName: string) {
  const [activeIndex, setActiveIndex] = useState(0);
  const boundedIndex = Math.min(activeIndex, Math.max(0, points.length - 1));
  const activePoint = points[boundedIndex];
  const onKeyDown = (event: KeyboardEvent<SVGSVGElement>) => {
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", "Home", "End"].includes(event.key) || !points.length) return;
    event.preventDefault();
    if (event.key === "Home") setActiveIndex(0);
    else if (event.key === "End") setActiveIndex(points.length - 1);
    else {
      const delta = event.key === "ArrowLeft" || event.key === "ArrowUp" ? -1 : 1;
      setActiveIndex((current) => (current + delta + points.length) % points.length);
    }
  };
  const instruction = language === "zh" ? "使用方向键浏览数据点" : "Use arrow keys to browse data points";
  const active = activePoint ? `${activePoint.label}: ${formatNumber(activePoint.value)}` : language === "zh" ? "没有数据" : "No data";
  return { activeIndex: boundedIndex, ariaLabel: `${chartName}。${instruction}。${active}`, onKeyDown };
}

function chartText(kind: AgentVisualizationModel["kind"], isPartialPareto: boolean, language: "zh" | "en") {
  const copy = {
    metric: ["关键指标", "Key metric"],
    bar: ["经营对比", "Business comparison"],
    line: ["时间趋势", "Time trend"],
    pie: ["结构占比", "Composition"],
    table: ["可信结果表", "Trusted result table"],
    pareto: isPartialPareto ? ["Pareto 边界证据", "Pareto boundary proof"] : ["Pareto 贡献曲线", "Pareto contribution curve"],
  } as const;
  return copy[kind][language === "zh" ? 0 : 1];
}

function BarChart({ model, language }: { model: AgentVisualizationModel; language: "zh" | "en" }) {
  const points = model.points;
  const horizontal = model.sourceKind === "ranking" || points.length > 8;
  return horizontal
    ? <HorizontalBarChart language={language} points={points} />
    : <VerticalBarChart language={language} points={points} />;
}

function HorizontalBarChart({ points, language }: { points: AgentVisualizationPoint[]; language: "zh" | "en" }) {
  const keyboard = useChartKeyboard(points, language, language === "zh" ? `横向条形图，共 ${points.length} 个实体` : `Horizontal bar chart with ${points.length} entities`);
  const width = 760;
  const left = 142;
  const right = 80;
  const rowHeight = 38;
  const top = 16;
  const height = Math.max(220, top * 2 + points.length * rowHeight);
  const values = points.map((point) => point.value);
  const minimum = Math.min(0, ...values);
  const maximum = Math.max(0, ...values);
  const span = maximum - minimum || 1;
  const plotWidth = width - left - right;
  const x = (value: number) => left + ((value - minimum) / span) * plotWidth;
  const zero = x(0);
  return (
    <svg aria-label={keyboard.ariaLabel} className="agentChartSvg agentBarHorizontal" onKeyDown={keyboard.onKeyDown} role="group" tabIndex={0} viewBox={`0 0 ${width} ${height}`}>
      <line className="agentChartZero" x1={zero} x2={zero} y1={8} y2={height - 8} />
      {points.map((point, index) => {
        const end = x(point.value);
        const barX = Math.min(zero, end);
        const barWidth = Math.max(2, Math.abs(end - zero));
        const y = top + index * rowHeight + 7;
        return (
          <g aria-label={`${point.rank ? `${language === "zh" ? "第" : "Rank "}${point.rank}${language === "zh" ? "名，" : ", "}` : ""}${point.label}: ${formatNumber(point.value)}`} data-active={keyboard.activeIndex === index || undefined} data-chart-mark="bar" key={`${point.label}-${index}`} role="img">
            <text className="agentChartLabel" textAnchor="end" x={left - 12} y={y + 13}>{point.rank ? `${point.rank}. ` : ""}{truncateLabel(point.label, 16)}</text>
            <rect className="agentChartBarTrack" height={18} rx={4} width={plotWidth} x={left} y={y} />
            <rect className="agentChartBar" height={18} rx={4} width={barWidth} x={barX} y={y} />
            <text className="agentChartValue" textAnchor={point.value >= 0 ? "start" : "end"} x={point.value >= 0 ? end + 8 : end - 8} y={y + 13}>{formatNumber(point.value, true)}</text>
            <title>{point.label}: {formatNumber(point.value)}</title>
          </g>
        );
      })}
    </svg>
  );
}

function VerticalBarChart({ points, language }: { points: AgentVisualizationPoint[]; language: "zh" | "en" }) {
  const keyboard = useChartKeyboard(points, language, language === "zh" ? `柱状图，共 ${points.length} 个分类` : `Bar chart with ${points.length} categories`);
  const width = 760;
  const height = 330;
  const left = 56;
  const right = 24;
  const top = 20;
  const bottom = 58;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const values = points.map((point) => point.value);
  const minimum = Math.min(0, ...values);
  const maximum = Math.max(0, ...values);
  const span = maximum - minimum || 1;
  const y = (value: number) => top + ((maximum - value) / span) * plotHeight;
  const zero = y(0);
  const slot = plotWidth / Math.max(points.length, 1);
  const barWidth = Math.min(54, slot * 0.62);
  const ticks = Array.from({ length: 5 }, (_, index) => minimum + (span * index) / 4).reverse();
  return (
    <svg aria-label={keyboard.ariaLabel} className="agentChartSvg" onKeyDown={keyboard.onKeyDown} role="group" tabIndex={0} viewBox={`0 0 ${width} ${height}`}>
      {ticks.map((tick) => (
        <g key={tick}>
          <line className="agentChartGrid" x1={left} x2={width - right} y1={y(tick)} y2={y(tick)} />
          <text className="agentChartTick" textAnchor="end" x={left - 9} y={y(tick) + 4}>{formatNumber(tick, true)}</text>
        </g>
      ))}
      <line className="agentChartZero" x1={left} x2={width - right} y1={zero} y2={zero} />
      {points.map((point, index) => {
        const center = left + slot * index + slot / 2;
        const valueY = y(point.value);
        const rectY = Math.min(zero, valueY);
        const barHeight = Math.max(2, Math.abs(valueY - zero));
        return (
          <g aria-label={`${point.label}: ${formatNumber(point.value)}`} data-active={keyboard.activeIndex === index || undefined} data-chart-mark="bar" key={`${point.label}-${index}`} role="img">
            <rect className="agentChartBar" height={barHeight} rx={5} width={barWidth} x={center - barWidth / 2} y={rectY} />
            <text className="agentChartValue" textAnchor="middle" x={center} y={point.value >= 0 ? rectY - 8 : rectY + barHeight + 16}>{formatNumber(point.value, true)}</text>
            <text className="agentChartLabel" textAnchor="middle" x={center} y={height - 27}>{truncateLabel(point.label, 10)}</text>
            <title>{point.label}: {formatNumber(point.value)}</title>
          </g>
        );
      })}
    </svg>
  );
}

function LineChart({ points, language }: { points: AgentVisualizationPoint[]; language: "zh" | "en" }) {
  const keyboard = useChartKeyboard(points, language, language === "zh" ? `折线图，共 ${points.length} 个时间点` : `Line chart with ${points.length} time points`);
  const width = 760;
  const height = 330;
  const left = 58;
  const right = 26;
  const top = 22;
  const bottom = 54;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const values = points.map((point) => point.value);
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const padding = (rawMax - rawMin || Math.abs(rawMax) || 1) * 0.12;
  const minimum = rawMin - padding;
  const maximum = rawMax + padding;
  const y = (value: number) => top + ((maximum - value) / (maximum - minimum || 1)) * plotHeight;
  const x = (index: number) => left + (points.length === 1 ? plotWidth / 2 : (index / (points.length - 1)) * plotWidth);
  const path = points.map((point, index) => `${index ? "L" : "M"} ${x(index)} ${y(point.value)}`).join(" ");
  const ticks = Array.from({ length: 5 }, (_, index) => minimum + ((maximum - minimum) * index) / 4).reverse();
  const labelIndexes = new Set([0, Math.floor((points.length - 1) / 2), points.length - 1]);
  return (
    <svg aria-label={keyboard.ariaLabel} className="agentChartSvg" onKeyDown={keyboard.onKeyDown} role="group" tabIndex={0} viewBox={`0 0 ${width} ${height}`}>
      {ticks.map((tick) => (
        <g key={tick}>
          <line className="agentChartGrid" x1={left} x2={width - right} y1={y(tick)} y2={y(tick)} />
          <text className="agentChartTick" textAnchor="end" x={left - 9} y={y(tick) + 4}>{formatNumber(tick, true)}</text>
        </g>
      ))}
      <path className="agentChartLine" d={path} />
      {points.map((point, index) => {
        return (
        <g aria-label={`${point.label}: ${formatNumber(point.value)}`} data-active={keyboard.activeIndex === index || undefined} data-chart-mark="point" key={`${point.label}-${index}`} role="img">
          <circle className="agentChartPointHalo" cx={x(index)} cy={y(point.value)} r={9} />
          <circle className="agentChartPoint" cx={x(index)} cy={y(point.value)} r={4.5} />
          {labelIndexes.has(index) ? <text className="agentChartLabel" textAnchor={index === 0 ? "start" : index === points.length - 1 ? "end" : "middle"} x={x(index)} y={height - 23}>{truncateLabel(point.label, 14)}</text> : null}
          <title>{point.label}: {formatNumber(point.value)}</title>
        </g>
      );})}
    </svg>
  );
}

function arcPath(start: number, end: number) {
  const center = 120;
  const outer = 92;
  const inner = 58;
  const point = (angle: number, radius: number) => ({ x: center + Math.cos(angle) * radius, y: center + Math.sin(angle) * radius });
  const startOuter = point(start, outer);
  const endOuter = point(end, outer);
  const endInner = point(end, inner);
  const startInner = point(start, inner);
  const large = end - start > Math.PI ? 1 : 0;
  return `M ${startOuter.x} ${startOuter.y} A ${outer} ${outer} 0 ${large} 1 ${endOuter.x} ${endOuter.y} L ${endInner.x} ${endInner.y} A ${inner} ${inner} 0 ${large} 0 ${startInner.x} ${startInner.y} Z`;
}

function PieChart({ points, language }: { points: AgentVisualizationPoint[]; language: "zh" | "en" }) {
  const keyboard = useChartKeyboard(points, language, language === "zh" ? `环形图，共 ${points.length} 个分类` : `Donut chart with ${points.length} categories`);
  const total = points.reduce((sum, point) => sum + point.value, 0);
  let cursor = -Math.PI / 2;
  const slices = points.map((point, index) => {
    const start = cursor;
    cursor += (point.value / total) * Math.PI * 2;
    return { point, index, start, end: cursor, share: point.value / total };
  });
  return (
    <div className="agentDonutLayout">
      <svg aria-label={keyboard.ariaLabel} className="agentDonutSvg" onKeyDown={keyboard.onKeyDown} role="group" tabIndex={0} viewBox="0 0 240 240">
        {slices.map(({ point, index, start, end, share }) => (
          <path aria-label={`${point.label}: ${formatNumber(point.value)}, ${formatPercent(share)}`} d={arcPath(start, end)} data-active={keyboard.activeIndex === index || undefined} data-chart-mark="slice" fill={categoryColors[index % categoryColors.length]} key={`${point.label}-${index}`} role="img">
            <title>{point.label}: {formatNumber(point.value)} ({formatPercent(share)})</title>
          </path>
        ))}
        <text className="agentDonutCenterLabel" textAnchor="middle" x="120" y="112">{language === "zh" ? "总计" : "Total"}</text>
        <text className="agentDonutCenterValue" textAnchor="middle" x="120" y="139">{formatNumber(total, true)}</text>
      </svg>
      <ul className="agentDonutLegend" aria-label={language === "zh" ? "图例" : "Legend"}>
        {slices.map(({ point, index, share }) => (
          <li key={`${point.label}-${index}`}>
            <i style={{ background: categoryColors[index % categoryColors.length] }} />
            <span title={point.label}>{point.label}</span>
            <strong>{formatPercent(share)}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ParetoChart({ model, language }: { model: AgentVisualizationModel; language: "zh" | "en" }) {
  const points = model.points;
  const keyboard = useChartKeyboard(points, language, language === "zh" ? `Pareto 边界证据图，显示 ${points.length} 个实体` : `Pareto boundary proof with ${points.length} entities`);
  const width = 760;
  const height = 350;
  const left = 58;
  const right = 56;
  const top = 24;
  const bottom = 62;
  const plotWidth = width - left - right;
  const plotHeight = height - top - bottom;
  const maximum = Math.max(...points.map((point) => point.value), 1);
  const slot = plotWidth / Math.max(points.length, 1);
  const barWidth = Math.min(54, slot * 0.58);
  const valueY = (value: number) => top + (1 - value / maximum) * plotHeight;
  const percentY = (value: number) => top + (1 - value) * plotHeight;
  const centerX = (index: number) => left + slot * index + slot / 2;
  const path = points.map((point, index) => `${index ? "L" : "M"} ${centerX(index)} ${percentY(point.cumulativeContribution ?? 0)}`).join(" ");
  const requestedHeadPercent = model.evidence.requestedHeadPercent ?? 0.2;
  const topBoundary = model.evidence.actualEntityCount ?? Math.ceil(model.populationEntityCount * requestedHeadPercent);
  const boundaryX = topBoundary > 0 && topBoundary <= points.length ? left + slot * topBoundary : null;
  return (
    <svg aria-label={`${keyboard.ariaLabel}。${language === "zh" ? `完整全集 ${model.populationEntityCount} 个实体` : `Full population ${model.populationEntityCount} entities`}`} className="agentChartSvg" onKeyDown={keyboard.onKeyDown} role="group" tabIndex={0} viewBox={`0 0 ${width} ${height}`}>
      {[0, 0.25, 0.5, 0.75, 1].map((tick) => (
        <g key={tick}>
          <line className="agentChartGrid" x1={left} x2={width - right} y1={percentY(tick)} y2={percentY(tick)} />
          <text className="agentChartTick" textAnchor="start" x={width - right + 9} y={percentY(tick) + 4}>{formatPercent(tick)}</text>
        </g>
      ))}
      <line className="agentParetoThreshold" x1={left} x2={width - right} y1={percentY(0.8)} y2={percentY(0.8)} />
      <text className="agentParetoThresholdLabel" textAnchor="end" x={width - right - 4} y={percentY(0.8) - 7}>80%</text>
      {boundaryX ? <line className="agentParetoHeadBoundary" x1={boundaryX} x2={boundaryX} y1={top} y2={height - bottom} /> : null}
      {points.map((point, index) => {
        const barY = valueY(point.value);
        return (
          <g aria-label={`${point.rank ? `${language === "zh" ? "第" : "Rank "}${point.rank}${language === "zh" ? "名，" : ", "}` : ""}${point.label}: ${formatNumber(point.value)}, ${language === "zh" ? "累计贡献" : "cumulative contribution"} ${formatPercent(point.cumulativeContribution ?? 0)}`} data-active={keyboard.activeIndex === index || undefined} data-chart-mark="pareto-bar" key={`${point.label}-${index}`} role="img">
            <rect className="agentChartBar agentParetoBar" height={height - bottom - barY} rx={5} width={barWidth} x={centerX(index) - barWidth / 2} y={barY} />
            <text className="agentChartValue" textAnchor="middle" x={centerX(index)} y={barY - 8}>{formatNumber(point.value, true)}</text>
            <text className="agentChartLabel" textAnchor="middle" x={centerX(index)} y={height - 29}>{truncateLabel(point.label, 10)}</text>
            <title>{point.label}: {formatNumber(point.value)} · {formatPercent(point.cumulativeContribution ?? 0)}</title>
          </g>
        );
      })}
      <path className="agentParetoLine" d={path} />
      {points.map((point, index) => (
        <circle aria-label={`${point.label} ${language === "zh" ? "累计贡献" : "cumulative contribution"} ${formatPercent(point.cumulativeContribution ?? 0)}`} className="agentParetoPoint" cx={centerX(index)} cy={percentY(point.cumulativeContribution ?? 0)} data-active={keyboard.activeIndex === index || undefined} data-chart-mark="pareto-point" key={`${point.label}-point-${index}`} r={5} role="img">
          <title>{point.label}: {formatPercent(point.cumulativeContribution ?? 0)}</title>
        </circle>
      ))}
    </svg>
  );
}

function MetricVisual({ model, language }: { model: AgentVisualizationModel; language: "zh" | "en" }) {
  const point = model.points[0];
  return (
    <div aria-label={point ? `${point.label}: ${formatNumber(point.value)}` : language === "zh" ? "指标值不可用" : "Metric unavailable"} className="agentMetricVisual" data-chart-mark="metric" role="img" tabIndex={0}>
      <span>{point?.label || model.measureColumn || (language === "zh" ? "指标" : "Metric")}</span>
      <strong>{point ? formatNumber(point.value) : "—"}</strong>
      <small>{language === "zh" ? "来自当前已执行结果" : "From the current executed result"}</small>
    </div>
  );
}

function DataTable({ model, language }: { model: AgentVisualizationModel; language: "zh" | "en" }) {
  const columns = model.columns.length ? model.columns : [...new Set(model.rows.flatMap((row) => Object.keys(row)))];
  const rows = model.rows.slice(0, 50);
  return (
    <div className="agentVisualizationTableScroller">
      <table className="agentVisualizationTable">
        <caption className="srOnly">{language === "zh" ? "图表对应数据" : "Data represented by the chart"}</caption>
        <thead><tr>{columns.map((column) => <th key={column} scope="col">{column}</th>)}</tr></thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={`${model.dimensionColumn ? String(row[model.dimensionColumn] ?? index) : index}-${index}`}>
              {columns.map((column) => <td key={column}>{tableCellText(row[column])}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ParetoInsights({ model, language }: { model: AgentVisualizationModel; language: "zh" | "en" }) {
  const evidence = model.evidence;
  const requestedHeadPercent = evidence.requestedHeadPercent ?? 0.2;
  const actualHeadPercent = evidence.actualEntityPercent ?? requestedHeadPercent;
  const headLabel = language === "zh"
    ? `前 ${formatPercent(requestedHeadPercent)} 实体贡献${actualHeadPercent > requestedHeadPercent ? `（并列后实际 ${formatPercent(actualHeadPercent)}）` : ""}`
    : `Top ${formatPercent(requestedHeadPercent)} contribution${actualHeadPercent > requestedHeadPercent ? ` (${formatPercent(actualHeadPercent)} after ties)` : ""}`;
  const items = [
    evidence.headContribution !== undefined ? { label: headLabel, value: formatPercent(evidence.headContribution) } : null,
    evidence.entitiesToReach80 !== undefined ? { label: language === "zh" ? "达到 80% 需要" : "Entities to reach 80%", value: language === "zh" ? `${evidence.entitiesToReach80} 个实体` : `${evidence.entitiesToReach80} entities` } : null,
    evidence.entityPercentToReach80 !== undefined ? { label: language === "zh" ? "对应实体占比" : "Entity share", value: formatPercent(evidence.entityPercentToReach80) } : null,
  ].filter((item): item is { label: string; value: string } => Boolean(item));
  return items.length ? (
    <dl className="agentParetoInsights">
      {items.map((item) => <div key={item.label}><dt>{item.label}</dt><dd>{item.value}</dd></div>)}
    </dl>
  ) : null;
}

export function AgentAnswerVisualization({ analysisUnit, chartAdapter, evidenceRefs, queryPlanReceipt, title }: AgentAnswerVisualizationProps) {
  const { resolvedLanguage } = useLanguage();
  const titleId = useId();
  const model = useMemo(() => buildAgentVisualizationModel(analysisUnit, chartAdapter, evidenceRefs), [analysisUnit, chartAdapter, evidenceRefs]);
  const chartLabel = chartText(model.kind, model.isPartialPareto, resolvedLanguage);
  const sourceRunId = String(queryPlanReceipt.source.currentSourceRunId ?? "");
  const subtitle = model.kind === "pareto" && model.isPartialPareto
    ? resolvedLanguage === "zh"
      ? `当前只绘制 Receipt 已绑定的 ${model.points.length} 个边界实体 / 完整全集 ${model.populationEntityCount}，未补画其余实体。`
      : `Shows ${model.points.length} Receipt-bound boundary entities out of ${model.populationEntityCount}; omitted entities are not invented.`
    : resolvedLanguage === "zh"
      ? `图形与 Receipt 返回的 ${model.receiptRowCount} 行已执行结果保持同源。`
      : `The visual is projected from the same ${model.receiptRowCount} executed result rows.`;

  return (
    <figure
      aria-labelledby={titleId}
      className={`agentAnswerVisualization kind-${model.kind}`}
      data-receipt-key={queryPlanReceipt.receiptKey}
      data-result-fingerprint={analysisUnit.resultFingerprint}
      data-testid="agent-answer-visualization"
      data-visual-state="executed"
    >
      <header className="agentVisualizationHeader">
        <div>
          <span className="agentVisualizationEyebrow"><i aria-hidden="true" />{resolvedLanguage === "zh" ? "可信可视化" : "Trusted visualization"}</span>
          <h4 id={titleId}>{title}</h4>
          <p>{subtitle}</p>
        </div>
        <span className="agentVisualizationKind">{chartLabel}</span>
      </header>
      {model.kind === "pareto" ? <ParetoInsights language={resolvedLanguage} model={model} /> : null}
      <div className="agentVisualizationPlot">
        {model.kind === "pareto" ? (
          <div className="agentParetoLegend" aria-label={resolvedLanguage === "zh" ? "图例" : "Legend"}>
            <span><i className="bar" />{model.measureLabel}</span>
            <span><i className="line" />{resolvedLanguage === "zh" ? "累计贡献" : "Cumulative contribution"}</span>
            <span><i className="threshold" />{resolvedLanguage === "zh" ? "80% 阈值" : "80% threshold"}</span>
            <span><i className="boundary" />{resolvedLanguage === "zh" ? "头部并列边界" : "Tie-aware head boundary"}</span>
          </div>
        ) : null}
        {model.kind === "metric" ? <MetricVisual language={resolvedLanguage} model={model} /> : null}
        {model.kind === "bar" ? <BarChart language={resolvedLanguage} model={model} /> : null}
        {model.kind === "line" ? <LineChart language={resolvedLanguage} points={model.points} /> : null}
        {model.kind === "pie" ? <PieChart language={resolvedLanguage} points={model.points} /> : null}
        {model.kind === "pareto" ? <ParetoChart language={resolvedLanguage} model={model} /> : null}
        {model.kind === "table" ? <DataTable language={resolvedLanguage} model={model} /> : null}
      </div>
      {model.kind !== "table" ? (
        <details className="agentVisualizationData" data-testid="agent-visualization-data-table">
          <summary>{resolvedLanguage === "zh" ? `查看对应数据（${Math.min(model.rows.length, 50)} 行）` : `View source rows (${Math.min(model.rows.length, 50)})`}</summary>
          <DataTable language={resolvedLanguage} model={model} />
        </details>
      ) : null}
      <figcaption className="agentVisualizationReceipt">
        <span>{resolvedLanguage === "zh" ? "已执行 · 当前来源" : "Executed · current source"}</span>
        <span>sourceRun {sourceRunId.slice(0, 16) || "—"}</span>
        <span>Receipt {queryPlanReceipt.receiptKey.slice(0, 16)}</span>
        <span>{analysisUnit.resultFingerprint.slice(0, 12)}</span>
      </figcaption>
    </figure>
  );
}

export default AgentAnswerVisualization;
