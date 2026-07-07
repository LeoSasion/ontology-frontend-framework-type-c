import { splitCsv, splitInputPaths } from "./sourceWorkbenchModel";
import { biText } from "./components/Bilingual";
import type { SourceIntelligenceRunOptions } from "./sourceIntelligenceRunModel";

export type { SourceIntelligenceRunOptions } from "./sourceIntelligenceRunModel";

export type ImportOptions = {
  filePath: string;
  table?: string;
  name?: string;
  mode?: string;
  uniqueFields?: string[];
  conflictRule?: string;
  confirm?: boolean;
};

export type ImportPolicyOptions = {
  table: string;
  uniqueFields: string[];
  conflictRule?: string;
  confirm?: boolean;
};

export type ConnectorOptions = {
  connector?: string;
  name: string;
  type?: string;
  provider?: string;
  status?: string;
  endpoint?: string;
  importMode?: string;
  targetTable?: string;
  uniqueFields?: string[];
  conflictRule?: string;
  schedule?: string;
  notes?: string;
  confirm?: boolean;
};

export type MetricMutationOptions = {
  id?: string;
  name: string;
  table: string;
  field?: string;
  aggregation?: string;
  dimension?: string;
  timeField?: string;
  filters?: Array<{ field: string; operator: string; value?: string }>;
  valueFormat?: string;
  description?: string;
  confirm?: boolean;
};

export function buildImportOptions({
  filePath,
  targetTable,
  targetName,
  importMode,
  uniqueFields,
  conflictRule,
  confirm = false,
}: {
  filePath: string;
  targetTable: string;
  targetName: string;
  importMode: string;
  uniqueFields: string;
  conflictRule: string;
  confirm?: boolean;
}): ImportOptions {
  return {
    filePath,
    table: targetTable.trim() || undefined,
    name: targetName.trim() || undefined,
    mode: importMode,
    uniqueFields: splitCsv(uniqueFields),
    conflictRule,
    confirm,
  };
}

export function buildImportPolicyOptions({
  targetTable,
  uniqueFields,
  conflictRule,
  confirm = false,
}: {
  targetTable: string;
  uniqueFields: string;
  conflictRule: string;
  confirm?: boolean;
}): ImportPolicyOptions {
  return {
    table: targetTable,
    uniqueFields: splitCsv(uniqueFields),
    conflictRule,
    confirm,
  };
}

export function buildSourceProfileOptions({
  sourceProfileInputs,
  sourceProfileLabel,
}: {
  sourceProfileInputs: string;
  sourceProfileLabel: string;
}): SourceIntelligenceRunOptions {
  return {
    inputs: splitInputPaths(sourceProfileInputs),
    label: sourceProfileLabel.trim() || "Source profile",
  };
}

export function buildConnectorOptions({
  connectorEditingKey,
  connectorName,
  connectorType,
  connectorProvider,
  connectorStatus,
  connectorEndpoint,
  connectorImportMode,
  connectorTargetTable,
  connectorUniqueFields,
  connectorConflictRule,
  connectorNotes,
  confirm = false,
}: {
  connectorEditingKey: string;
  connectorName: string;
  connectorType: string;
  connectorProvider: string;
  connectorStatus: string;
  connectorEndpoint: string;
  connectorImportMode: string;
  connectorTargetTable: string;
  connectorUniqueFields: string;
  connectorConflictRule: string;
  connectorNotes: string;
  confirm?: boolean;
}): ConnectorOptions {
  return {
    connector: connectorEditingKey || undefined,
    name: connectorName,
    type: connectorType,
    provider: connectorProvider,
    status: connectorStatus,
    endpoint: connectorEndpoint,
    importMode: connectorImportMode,
    targetTable: connectorTargetTable,
    uniqueFields: splitCsv(connectorUniqueFields),
    conflictRule: connectorConflictRule,
    schedule: "manual",
    notes: connectorNotes,
    confirm,
  };
}

export function buildMetricDraft({
  confirm = false,
  metricName,
  selectedTableKey,
  effectiveMetricField,
  metricAggregation,
  effectiveMetricDimension,
}: {
  confirm?: boolean;
  metricName: string;
  selectedTableKey: string;
  effectiveMetricField: string;
  metricAggregation: string;
  effectiveMetricDimension: string;
}): MetricMutationOptions {
  return {
    name: metricName,
    table: selectedTableKey,
    field: effectiveMetricField,
    aggregation: metricAggregation,
    dimension: effectiveMetricDimension || undefined,
    valueFormat: "auto",
    description: biText("从数据源工作台保存的自定义指标", "Custom metric saved from source workbench"),
    confirm,
  };
}
