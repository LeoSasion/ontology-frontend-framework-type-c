import { useCallback, useEffect, useMemo, useRef, useState, type Dispatch, type SetStateAction } from "react";
import type { FieldConfig, FormulaMutationPayload } from "./types";
import type { QueryOptions, RelationshipSaveOptions, SourceWorkbenchProps } from "./sourceWorkbenchContracts";
import { withRelationshipIdentity } from "./dashboardCanvasRelationshipModel";
import {
  buildFieldSemanticReadiness,
  buildSourceWorkbenchCollections,
  buildSourceWorkbenchRuntimeSummary,
  buildSourceWorkbenchSelection,
  resultRows,
  sourceProfileErrorMessage,
} from "./sourceWorkbenchModel";
import {
  buildMetricDraft,
  buildSourceProfileOptions,
  type MetricMutationOptions,
  type SourceIntelligenceRunOptions,
} from "./sourceWorkbenchCommandModel";
import {
  applyFieldDraftPatch,
  buildNavigationOperationOptions,
  managedSourceDisplayName,
  readFieldDraft,
  type FieldDraft,
  type FieldDrafts,
  type NavigationOperation,
} from "./sourceWorkbenchDraftModel";
import { buildSourceWorkbenchGuidance } from "./sourceWorkbenchGuidanceModel";
import { useSourceWorkbenchConnectorController } from "./useSourceWorkbenchConnectorController";
import { useSourceWorkbenchImportController } from "./useSourceWorkbenchImportController";
import { biText } from "./components/Bilingual";
import { latestUsableSourceIntelligenceRun } from "./workspaceFlowModel";

export function useSourceWorkbenchState({
  focusedTableKey,
  onTableFocus,
  status,
  preview,
  query,
  workbench,
  onPreview,
  onCommitImport,
  onPreviewFolderImport,
  onCommitFolderImport,
  onImportPolicy,
  onRemoveImportJob,
  onInspectSource,
  onRenameSource,
  onDeleteSource,
  onNavigationOperation,
  onSaveConnector,
  onSyncConnector,
  onRemoveConnector,
  onQuery,
  onInferSemantics,
  onSetSemantic,
  onInferMetrics,
  onAddMetric,
  onQueryMetric,
  onRelationshipPreview,
  onRelationshipSave,
  onFormulaPreview,
  onFormulaSave,
  onFormulaDelete,
  onSourceIntelligenceRun,
  onAsk,
}: SourceWorkbenchProps) {
  void onRemoveImportJob;
  void onInspectSource;
  void onRenameSource;
  void onDeleteSource;
  void onQuery;
  void onInferSemantics;
  void onSetSemantic;
  void onInferMetrics;
  void onAddMetric;
  void onQueryMetric;
  void onRelationshipPreview;
  void onRelationshipSave;
  void onFormulaPreview;
  void onFormulaSave;
  void onFormulaDelete;
  void onAsk;

  const {
    tables,
    fields,
    metrics,
    relationships,
    relationshipRecommendations,
    importJobs,
    importPolicies,
    connectors,
    connectorAdapters,
    rowFormulas,
    navigationModules,
    sourceIntelligenceRuns,
    fieldRoles,
    fieldUsages,
    safeAggregations,
    sourceRuns,
    queryRows,
    firstTableKey,
  } = useMemo(() => buildSourceWorkbenchCollections(workbench, status, query), [workbench, status, query]);
  const tableKeySet = useMemo(() => new Set(tables.map((table) => table.table_key)), [tables]);
  const fieldsByTable = useMemo(() => {
    const indexed = new Map<string, FieldConfig[]>();
    for (const field of fields) {
      const tableFields = indexed.get(field.table_key);
      if (tableFields) {
        tableFields.push(field);
      } else {
        indexed.set(field.table_key, [field]);
      }
    }
    return indexed;
  }, [fields]);
  const [activeTableKey, setActiveTableKeyState] = useState(firstTableKey);
  const setActiveTableKey = useCallback<Dispatch<SetStateAction<string>>>((nextValue) => {
    setActiveTableKeyState((current) => {
      const next = typeof nextValue === "function" ? nextValue(current) : nextValue;
      if (next && next !== current) onTableFocus?.(next);
      return next;
    });
  }, [onTableFocus]);
  const [managedSourceKey, setManagedSourceKey] = useState(firstTableKey);
  const [sourceRenameName, setSourceRenameName] = useState(tables[0]?.display_name ?? "");
  const [navigationModuleKey, setNavigationModuleKey] = useState(navigationModules[0]?.moduleKey ?? "");
  const activeNavigationModule = navigationModules.find((module) => module.moduleKey === navigationModuleKey) ?? navigationModules[0];
  const [navigationName, setNavigationName] = useState(activeNavigationModule?.name ?? "");
  const [navigationSort, setNavigationSort] = useState(String(activeNavigationModule?.sort ?? 110));
  const [navigationResult, setNavigationResult] = useState<Record<string, unknown> | null>(null);
  const selectedManagedSourceKey = tableKeySet.has(managedSourceKey) ? managedSourceKey : firstTableKey;
  const {
    selectedTableKey,
    selectedFields,
    selectedMetrics,
    measureFields,
    groupFields,
    selectedFormulaAssets,
  } = useMemo(() => buildSourceWorkbenchSelection({
    tables,
    fields,
    metrics,
    rowFormulas,
    activeTableKey,
    firstTableKey,
  }), [activeTableKey, fields, firstTableKey, metrics, rowFormulas, tables]);
  const fieldSemanticReadiness = useMemo(() => buildFieldSemanticReadiness(selectedFields), [selectedFields]);
  const [queryForm, setQueryForm] = useState<QueryOptions>({
    table: selectedTableKey,
    group: groupFields[0]?.field_name ?? "",
    measure: measureFields[0]?.field_name ?? "",
    aggregation: "count",
    limit: 10,
  });
  const [relationshipForm, setRelationshipForm] = useState<RelationshipSaveOptions>({
    leftTable: tables[0]?.table_key ?? "",
    rightTable: tables[1]?.table_key ?? "",
    leftField: "",
    rightField: "",
    joinType: "left",
    limit: 10,
  });
  const [formulaName, setFormulaName] = useState("");
  const [formulaExpression, setFormulaExpression] = useState("");
  const [formulaMode, setFormulaMode] = useState("aggregate");
  const [formulaMutation, setFormulaMutation] = useState<FormulaMutationPayload | null>(null);
  const [fieldDrafts, setFieldDrafts] = useState<FieldDrafts>({});
  const [metricName, setMetricName] = useState("");
  const [metricField, setMetricField] = useState(measureFields[0]?.field_name ?? "");
  const [metricAggregation, setMetricAggregation] = useState("count");
  const [metricDimension, setMetricDimension] = useState(groupFields[0]?.field_name ?? "");
  const [semanticMetricResult, setSemanticMetricResult] = useState<Record<string, unknown> | null>(null);
  const [sourceProfileInputs, setSourceProfileInputs] = useState("");
  const [sourceProfileLabel, setSourceProfileLabel] = useState(biText("证据摘要", "Source profile"));
  const [sourceProfileResult, setSourceProfileResult] = useState<Record<string, unknown> | null>(null);
  const [sourceProfileError, setSourceProfileError] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const sourceProfileInFlightRef = useRef(false);
  const sourceProfileRecoveryKeyRef = useRef("");
  const importController = useSourceWorkbenchImportController({
    preview,
    importPolicies,
    onPreview,
    onCommitImport,
    onPreviewFolderImport,
    onCommitFolderImport,
    onImportPolicy,
    onCommittedInputs: async (inputs) => {
      setSourceProfileInputs(inputs.join("\n"));
      await runSourceProfile(biText("正在生成证据", "Generating evidence"), {
        inputs,
        label: sourceProfileLabel.trim() || "Source profile",
        stayOnPage: true,
      });
    },
  });
  const connectorController = useSourceWorkbenchConnectorController({
    firstTableKey,
    tableKeySet,
    onSaveConnector,
    onSyncConnector,
    onRemoveConnector,
  });

  useEffect(() => {
    if (!activeNavigationModule) return;
    setNavigationName(activeNavigationModule.name);
    setNavigationSort(String(activeNavigationModule.sort));
  }, [activeNavigationModule?.moduleKey, activeNavigationModule?.name, activeNavigationModule?.sort]);

  useEffect(() => {
    if (!firstTableKey) return;
    const firstTableName = tables[0]?.display_name ?? firstTableKey;
    setActiveTableKeyState((current) => tableKeySet.has(current) ? current : firstTableKey);
    setManagedSourceKey((current) => tableKeySet.has(current) ? current : firstTableKey);
    setSourceRenameName((current) => current || firstTableName);
  }, [firstTableKey, tableKeySet, tables]);

  useEffect(() => {
    if (!focusedTableKey || !tableKeySet.has(focusedTableKey)) return;
    setActiveTableKeyState(focusedTableKey);
    setManagedSourceKey(focusedTableKey);
    setSourceRenameName(managedSourceDisplayName(tables, focusedTableKey));
  }, [focusedTableKey, tableKeySet, tables]);

  useEffect(() => {
    if (!tables.length || sourceIntelligenceRuns.length || busy || sourceProfileInFlightRef.current) return;
    const inputs = Array.from(new Set(importJobs
      .filter((job) => job.status === "success" && job.source_file.trim())
      .map((job) => job.source_file.trim())));
    if (!inputs.length) return;
    const recoveryKey = `${status.workspace.id}:${inputs.join("\n")}`;
    if (sourceProfileRecoveryKeyRef.current === recoveryKey) return;
    const recoveryTimer = window.setTimeout(() => {
      if (sourceProfileInFlightRef.current || sourceProfileRecoveryKeyRef.current === recoveryKey) return;
      sourceProfileRecoveryKeyRef.current = recoveryKey;
      setSourceProfileInputs(inputs.join("\n"));
      void runSourceProfile(biText("正在恢复证据生成", "Resuming evidence generation"), {
        inputs,
        label: sourceProfileLabel.trim() || "Source profile",
        stayOnPage: true,
      });
    }, 1500);
    return () => window.clearTimeout(recoveryTimer);
  }, [busy, importJobs, sourceIntelligenceRuns.length, sourceProfileLabel, status.workspace.id, tables.length]);

  useEffect(() => {
    if (!navigationModules.length) return;
    setNavigationModuleKey((current) => navigationModules.some((module) => module.moduleKey === current) ? current : navigationModules[0].moduleKey);
  }, [navigationModules]);

  useEffect(() => {
    setQueryForm((current) => ({
      ...current,
      table: tableKeySet.has(current.table ?? "") ? current.table : selectedTableKey,
      group: current.group || (groupFields[0]?.field_name ?? ""),
      measure: current.measure || (measureFields[0]?.field_name ?? ""),
      aggregation: current.aggregation || "count",
    }));
    setMetricField((current) => measureFields.some((field) => field.field_name === current) ? current : measureFields[0]?.field_name ?? "");
    setMetricDimension((current) => groupFields.some((field) => field.field_name === current) ? current : groupFields[0]?.field_name ?? "");
  }, [groupFields, measureFields, selectedTableKey, tableKeySet]);

  useEffect(() => {
    setRelationshipForm((current) => {
      const leftTable = tableKeySet.has(current.leftTable) ? current.leftTable : tables[0]?.table_key ?? "";
      const rightTable = tableKeySet.has(current.rightTable) && current.rightTable !== leftTable
        ? current.rightTable
        : tables.find((table) => table.table_key !== leftTable)?.table_key ?? "";
      const leftFields = fieldsByTable.get(leftTable) ?? [];
      const rightFields = fieldsByTable.get(rightTable) ?? [];
      const hasLeftField = leftFields.some((field) => field.field_name === current.leftField);
      const hasRightField = rightFields.some((field) => field.field_name === current.rightField);
      return withRelationshipIdentity(current, {
        leftTable,
        rightTable,
        leftField: hasLeftField ? current.leftField : leftFields[0]?.field_name ?? "",
        rightField: hasRightField ? current.rightField : rightFields[0]?.field_name ?? "",
      });
    });
  }, [fieldsByTable, tableKeySet, tables]);

  function sourceProfileOptions(): SourceIntelligenceRunOptions {
    return buildSourceProfileOptions({ sourceProfileInputs, sourceProfileLabel });
  }

  function fieldDraft(field: FieldConfig) {
    return readFieldDraft(fieldDrafts, field);
  }

  function updateFieldDraft(field: FieldConfig, patch: Partial<FieldDraft>) {
    setFieldDrafts((current) => applyFieldDraftPatch(current, field, patch));
  }

  async function runNavigationOperation(op: NavigationOperation, confirm = false) {
    const result = await onNavigationOperation(buildNavigationOperationOptions({
      activeNavigationModule,
      navigationModuleKey,
      op,
      navigationName,
      navigationSort,
      confirm,
    }));
    setNavigationResult(result);
  }

  function selectManagedSource(tableKey: string) {
    setManagedSourceKey(tableKey);
    setSourceRenameName(managedSourceDisplayName(tables, tableKey));
  }

  async function runBusy(label: string, action: () => Promise<void>) {
    setBusy(label);
    try {
      await action();
    } finally {
      setBusy(null);
    }
  }

  async function runSourceProfile(label: string, options: SourceIntelligenceRunOptions) {
    sourceProfileInFlightRef.current = true;
    setBusy(label);
    setSourceProfileResult(null);
    setSourceProfileError("");
    try {
      const result = await onSourceIntelligenceRun(options);
      setSourceProfileResult(result && typeof result === "object" ? result as Record<string, unknown> : null);
    } catch (error) {
      setSourceProfileError(sourceProfileErrorMessage(error));
    } finally {
      sourceProfileInFlightRef.current = false;
      setBusy(null);
    }
  }

  const { runtimeStatus, queryInfo, queryRuntime } = buildSourceWorkbenchRuntimeSummary(workbench, status, query);
  const effectiveMetricField = measureFields.some((field) => field.field_name === metricField) ? metricField : measureFields[0]?.field_name ?? "*";
  const effectiveMetricDimension = groupFields.some((field) => field.field_name === metricDimension) ? metricDimension : groupFields[0]?.field_name ?? "";
  const metricResultRows = resultRows(semanticMetricResult).slice(0, 5);
  const latestSourceProfile = latestUsableSourceIntelligenceRun(sourceIntelligenceRuns);
  const connectedRowCount = tables.reduce((total, table) => total + table.row_count, 0);
  const connectedFieldCount = tables.reduce((total, table) => total + table.column_count, 0);
  const guidance = buildSourceWorkbenchGuidance({
    busy,
    preview,
    tables,
    fields,
    latestSourceProfile,
  });
  const hasData = tables.length > 0 || status.counts.tables > 0;
  const showExpertWorkbench = showAdvanced;

  function metricDraft(confirm = false): MetricMutationOptions {
    return buildMetricDraft({
      metricName,
      selectedTableKey,
      effectiveMetricField,
      metricAggregation,
      effectiveMetricDimension,
      confirm,
    });
  }

  return {
    tables,
    fields,
    relationships,
    relationshipRecommendations,
    importJobs,
    connectors,
    connectorAdapters,
    navigationModules,
    sourceIntelligenceRuns,
    fieldRoles,
    fieldUsages,
    safeAggregations,
    sourceRuns,
    queryRows,
    activeNavigationModule,
    navigationModuleKey,
    navigationName,
    navigationSort,
    navigationResult,
    selectedManagedSourceKey,
    selectedTableKey,
    selectedFields,
    selectedMetrics,
    measureFields,
    groupFields,
    selectedFormulaAssets,
    fieldSemanticReadiness,
    queryForm,
    relationshipForm,
    formulaName,
    formulaExpression,
    formulaMode,
    formulaMutation,
    metricName,
    metricAggregation,
    semanticMetricResult,
    sourceProfileInputs,
    sourceProfileLabel,
    sourceProfileResult,
    sourceProfileError,
    busy,
    showAdvanced,
    importController,
    connectorController,
    runtimeStatus,
    queryInfo,
    queryRuntime,
    effectiveMetricField,
    effectiveMetricDimension,
    metricResultRows,
    latestSourceProfile,
    connectedRowCount,
    connectedFieldCount,
    ...guidance,
    hasData,
    showExpertWorkbench,
    setActiveTableKey,
    setNavigationModuleKey,
    setNavigationName,
    setNavigationSort,
    setQueryForm,
    setRelationshipForm,
    setFormulaName,
    setFormulaExpression,
    setFormulaMode,
    setFormulaMutation,
    setMetricName,
    setMetricField,
    setMetricAggregation,
    setMetricDimension,
    setSemanticMetricResult,
    setSourceProfileInputs,
    setSourceProfileLabel,
    setSourceRenameName,
    setShowAdvanced,
    fieldDraft,
    updateFieldDraft,
    runNavigationOperation,
    selectManagedSource,
    runBusy,
    runSourceProfile,
    metricDraft,
    sourceProfileOptions,
    sourceRenameName,
  };
}
