import type { Dispatch, SetStateAction } from "react";
import type { FieldConfig, MetricDefinition } from "../types";
import type { MetricMutationOptions, QueryMetricOptions } from "../sourceWorkbenchFieldMetricTypes";
import { actionResultSummary } from "../sourceWorkbenchModel";
import { Bilingual, biText } from "./Bilingual";

type SourceWorkbenchMetricDefinitionPanelProps = {
  showAdvanced: boolean;
  busy: string | null;
  selectedTableKey: string;
  selectedMetrics: MetricDefinition[];
  safeAggregations: string[];
  metricName: string;
  effectiveMetricField: string;
  metricAggregation: string;
  effectiveMetricDimension: string;
  measureFields: FieldConfig[];
  groupFields: FieldConfig[];
  semanticMetricResult: Record<string, unknown> | null;
  metricResultRows: Array<Record<string, unknown>>;
  setMetricName: Dispatch<SetStateAction<string>>;
  setMetricField: Dispatch<SetStateAction<string>>;
  setMetricAggregation: Dispatch<SetStateAction<string>>;
  setMetricDimension: Dispatch<SetStateAction<string>>;
  setSemanticMetricResult: Dispatch<SetStateAction<Record<string, unknown> | null>>;
  metricDraft: (confirm?: boolean) => MetricMutationOptions;
  runBusy: (label: string, action: () => Promise<void>) => Promise<void>;
  onInferMetrics: (options: { table?: string; confirm?: boolean }) => Promise<Record<string, unknown>>;
  onAddMetric: (options: MetricMutationOptions) => Promise<Record<string, unknown>>;
  onQueryMetric: (options: QueryMetricOptions) => Promise<Record<string, unknown>>;
};

export function SourceWorkbenchMetricDefinitionPanel({
  showAdvanced,
  busy,
  selectedTableKey,
  selectedMetrics,
  safeAggregations,
  metricName,
  effectiveMetricField,
  metricAggregation,
  effectiveMetricDimension,
  measureFields,
  groupFields,
  semanticMetricResult,
  metricResultRows,
  setMetricName,
  setMetricField,
  setMetricAggregation,
  setMetricDimension,
  setSemanticMetricResult,
  metricDraft,
  runBusy,
  onInferMetrics,
  onAddMetric,
  onQueryMetric,
}: SourceWorkbenchMetricDefinitionPanelProps) {
  return (
    <article className={showAdvanced ? "workbenchPanel advancedPanel" : "workbenchPanel advancedPanel collapsed"}>
      <div className="tileHeader">
        <h3><Bilingual zh="指标定义" en="Metric definitions" /></h3>
        <div className="buttonRow tight">
          <span>{selectedMetrics.length}</span>
          <button
            className="miniButton"
            data-testid="infer-metrics-dry-run-button"
            disabled={busy === "metrics-dry"}
            onClick={() => runBusy("metrics-dry", async () => {
              setSemanticMetricResult(await onInferMetrics({ table: selectedTableKey, confirm: false }));
            })}
            type="button"
          >
            {biText("预演推荐", "Preview")}
          </button>
          <button
            className="miniButton"
            data-testid="infer-metrics-confirm-button"
            disabled={busy === "metrics-save"}
            onClick={() => runBusy("metrics-save", async () => {
              setSemanticMetricResult(await onInferMetrics({ table: selectedTableKey, confirm: true }));
            })}
            type="button"
          >
            {biText("保存推荐", "Save")}
          </button>
        </div>
      </div>
      <div className="metricBuilder">
        <label>
          <span>{biText("指标名", "Metric name")}</span>
          <input value={metricName} onChange={(event) => setMetricName(event.target.value)} />
        </label>
        <label>
          <span>{biText("度量字段", "Measure")}</span>
          <select value={effectiveMetricField} onChange={(event) => setMetricField(event.target.value)}>
            {measureFields.length ? measureFields.map((field) => <option key={field.field_name} value={field.field_name}>{field.field_name}</option>) : <option value="*">*</option>}
          </select>
        </label>
        <label>
          <span>{biText("聚合", "Aggregation")}</span>
          <select value={metricAggregation} onChange={(event) => setMetricAggregation(event.target.value)}>
            {safeAggregations.map((agg) => <option key={agg} value={agg}>{agg}</option>)}
          </select>
        </label>
        <label>
          <span>{biText("默认分组", "Default group")}</span>
          <select value={effectiveMetricDimension} onChange={(event) => setMetricDimension(event.target.value)}>
            <option value="">{biText("不分组", "None")}</option>
            {groupFields.map((field) => <option key={field.field_name} value={field.field_name}>{field.field_name}</option>)}
          </select>
        </label>
      </div>
      <div className="buttonRow tight">
        <button className="miniButton" data-testid="add-metric-dry-run-button" disabled={busy === "metric-dry"} onClick={() => runBusy("metric-dry", async () => {
          setSemanticMetricResult(await onAddMetric(metricDraft(false)));
        })} type="button">
          {biText("预演新增", "Preview add")}
        </button>
        <button className="miniButton" data-testid="add-metric-confirm-button" disabled={busy === "metric-save"} onClick={() => runBusy("metric-save", async () => {
          setSemanticMetricResult(await onAddMetric(metricDraft(true)));
        })} type="button">
          {biText("保存指标", "Save metric")}
        </button>
        <button className="miniButton" data-testid="query-metric-button" disabled={busy === "metric-query" || !selectedMetrics.length} onClick={() => runBusy("metric-query", async () => {
          const metric = selectedMetrics[0];
          setSemanticMetricResult(await onQueryMetric({
            metric: metric.metric_key,
            group: metric.dimension ? [metric.dimension] : effectiveMetricDimension ? [effectiveMetricDimension] : undefined,
            limit: 5,
          }));
        })} type="button">
          {biText("查询首个指标", "Query first metric")}
        </button>
      </div>
      <ul className="metricList">
        {selectedMetrics.slice(0, 8).map((metric) => (
          <li key={metric.metric_key}>
            <div>
              <strong>{metric.label}</strong>
              <span>{metric.table_key} · {metric.aggregation}({metric.measure}){metric.dimension ? ` · ${metric.dimension}` : ""}</span>
            </div>
            <button className="miniButton" data-testid={`query-metric-${metric.metric_key}`} disabled={busy === `metric-query-${metric.metric_key}`} onClick={() => runBusy(`metric-query-${metric.metric_key}`, async () => {
              setSemanticMetricResult(await onQueryMetric({
                metric: metric.metric_key,
                group: metric.dimension ? [metric.dimension] : undefined,
                limit: 5,
              }));
            })} type="button">
              {biText("查询", "Query")}
            </button>
          </li>
        ))}
      </ul>
      {semanticMetricResult ? (
        <div className="resultNotice" data-testid="semantic-metric-result">
          <strong>{actionResultSummary(semanticMetricResult)}</strong>
          {metricResultRows.length ? (
            <div className="miniResultRows">
              {metricResultRows.map((row, index) => (
                <span key={`${index}-${JSON.stringify(row)}`}>{Object.values(row).slice(0, 3).join(" · ")}</span>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}
