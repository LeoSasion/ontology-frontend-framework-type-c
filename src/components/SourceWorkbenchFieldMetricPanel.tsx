import type { Dispatch, SetStateAction } from "react";
import type { FieldConfig, MetricDefinition, SourceIntelligenceRunSummary, WorkbenchTable } from "../types";
import type {
  FieldSemanticReadiness,
  MetricMutationOptions,
  QueryMetricOptions,
  SemanticInferOptions,
  SemanticSetOptions,
} from "../sourceWorkbenchFieldMetricTypes";
import { SourceWorkbenchFieldSemanticPanel } from "./SourceWorkbenchFieldSemanticPanel";
import { SourceWorkbenchMetricDefinitionPanel } from "./SourceWorkbenchMetricDefinitionPanel";

type SourceWorkbenchFieldMetricPanelProps = {
  showAdvanced: boolean;
  busy: string | null;
  tables: WorkbenchTable[];
  selectedTableKey: string;
  selectedFields: FieldConfig[];
  selectedMetrics: MetricDefinition[];
  fieldRoles: string[];
  fieldUsages: string[];
  safeAggregations: string[];
  fieldSemanticReadiness: FieldSemanticReadiness;
  latestSourceProfile?: SourceIntelligenceRunSummary;
  metricName: string;
  effectiveMetricField: string;
  metricAggregation: string;
  effectiveMetricDimension: string;
  measureFields: FieldConfig[];
  groupFields: FieldConfig[];
  semanticMetricResult: Record<string, unknown> | null;
  metricResultRows: Array<Record<string, unknown>>;
  setActiveTableKey: Dispatch<SetStateAction<string>>;
  setMetricName: Dispatch<SetStateAction<string>>;
  setMetricField: Dispatch<SetStateAction<string>>;
  setMetricAggregation: Dispatch<SetStateAction<string>>;
  setMetricDimension: Dispatch<SetStateAction<string>>;
  setSemanticMetricResult: Dispatch<SetStateAction<Record<string, unknown> | null>>;
  fieldDraft: (field: FieldConfig) => Pick<FieldConfig, "role" | "usage">;
  updateFieldDraft: (field: FieldConfig, patch: Partial<Pick<FieldConfig, "role" | "usage">>) => void;
  metricDraft: (confirm?: boolean) => MetricMutationOptions;
  runBusy: (label: string, action: () => Promise<void>) => Promise<void>;
  onAsk: (prompt: string) => Promise<void>;
  onInferSemantics: (options: SemanticInferOptions) => Promise<Record<string, unknown>>;
  onSetSemantic: (options: SemanticSetOptions) => Promise<Record<string, unknown>>;
  onInferMetrics: (options: { table?: string; confirm?: boolean }) => Promise<Record<string, unknown>>;
  onAddMetric: (options: MetricMutationOptions) => Promise<Record<string, unknown>>;
  onQueryMetric: (options: QueryMetricOptions) => Promise<Record<string, unknown>>;
};

export function SourceWorkbenchFieldMetricPanel({
  showAdvanced,
  busy,
  tables,
  selectedTableKey,
  selectedFields,
  selectedMetrics,
  fieldRoles,
  fieldUsages,
  safeAggregations,
  fieldSemanticReadiness,
  latestSourceProfile,
  metricName,
  effectiveMetricField,
  metricAggregation,
  effectiveMetricDimension,
  measureFields,
  groupFields,
  semanticMetricResult,
  metricResultRows,
  setActiveTableKey,
  setMetricName,
  setMetricField,
  setMetricAggregation,
  setMetricDimension,
  setSemanticMetricResult,
  fieldDraft,
  updateFieldDraft,
  metricDraft,
  runBusy,
  onAsk,
  onInferSemantics,
  onSetSemantic,
  onInferMetrics,
  onAddMetric,
  onQueryMetric,
}: SourceWorkbenchFieldMetricPanelProps) {
  return (
    <>
      <SourceWorkbenchFieldSemanticPanel
        busy={busy}
        fieldDraft={fieldDraft}
        fieldRoles={fieldRoles}
        fieldSemanticReadiness={fieldSemanticReadiness}
        fieldUsages={fieldUsages}
        latestSourceProfile={latestSourceProfile}
        onAsk={onAsk}
        onInferSemantics={onInferSemantics}
        onSetSemantic={onSetSemantic}
        runBusy={runBusy}
        selectedFields={selectedFields}
        selectedTableKey={selectedTableKey}
        setActiveTableKey={setActiveTableKey}
        setSemanticMetricResult={setSemanticMetricResult}
        showAdvanced={showAdvanced}
        tables={tables}
        updateFieldDraft={updateFieldDraft}
      />
      <SourceWorkbenchMetricDefinitionPanel
        busy={busy}
        effectiveMetricDimension={effectiveMetricDimension}
        effectiveMetricField={effectiveMetricField}
        groupFields={groupFields}
        measureFields={measureFields}
        metricAggregation={metricAggregation}
        metricDraft={metricDraft}
        metricName={metricName}
        metricResultRows={metricResultRows}
        onAddMetric={onAddMetric}
        onInferMetrics={onInferMetrics}
        onQueryMetric={onQueryMetric}
        runBusy={runBusy}
        safeAggregations={safeAggregations}
        selectedMetrics={selectedMetrics}
        selectedTableKey={selectedTableKey}
        semanticMetricResult={semanticMetricResult}
        setMetricAggregation={setMetricAggregation}
        setMetricDimension={setMetricDimension}
        setMetricField={setMetricField}
        setMetricName={setMetricName}
        setSemanticMetricResult={setSemanticMetricResult}
        showAdvanced={showAdvanced}
      />
    </>
  );
}
