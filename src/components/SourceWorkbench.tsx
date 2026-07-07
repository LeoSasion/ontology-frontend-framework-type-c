import { useEffect, useMemo, useState } from "react";
import type { DataConnectorConfig, FieldConfig, FolderImportPlan, FormulaMutationPayload } from "../types";
import type { RelationshipSaveOptions } from "../dashboardCanvasContracts";
import type { QueryOptions, SourceWorkbenchProps } from "../sourceWorkbenchContracts";
import {
  buildFieldSemanticReadiness,
  buildImportPreviewSummary,
  buildSourceWorkbenchCollections,
  buildSourceWorkbenchRuntimeSummary,
  buildSourceWorkbenchSelection,
  resultRows,
  sourceProfileErrorMessage,
} from "../sourceWorkbenchModel";
import {
  buildConnectorOptions,
  buildImportOptions,
  buildImportPolicyOptions,
  buildMetricDraft,
  buildSourceProfileOptions,
  type ConnectorOptions,
  type ImportOptions,
  type MetricMutationOptions,
  type SourceIntelligenceRunOptions,
} from "../sourceWorkbenchCommandModel";
import {
  applyFieldDraftPatch,
  buildNavigationOperationOptions,
  managedSourceDisplayName,
  readFieldDraft,
  type FieldDraft,
  type FieldDrafts,
  type NavigationOperation,
} from "../sourceWorkbenchDraftModel";
import { buildSourceWorkbenchGuidance } from "../sourceWorkbenchGuidanceModel";
import { buildConnectorRemoveReceipt, buildConnectorSaveReceipt, buildConnectorSyncReceipt, buildImportCommitReceipt, buildImportPolicyReceipt, buildImportPreviewReceipt, type WorkbenchOperationReceipt } from "../sourceWorkbenchReceiptModel";
import { buildProductActivation } from "../productActivationModel";
import { Bilingual, biText } from "./Bilingual";
import { ProductActivationPanel } from "./ProductActivationPanel";
import { SourceWorkbenchActionPanel } from "./SourceWorkbenchActionPanel";
import { SourceWorkbenchConnectorPanel } from "./SourceWorkbenchConnectorPanel";
import { SourceWorkbenchDataManagementPanel } from "./SourceWorkbenchDataManagementPanel";
import { SourceWorkbenchDataEntryPanel } from "./SourceWorkbenchDataEntryPanel";
import { SourceWorkbenchFieldMetricPanel } from "./SourceWorkbenchFieldMetricPanel";
import { SourceWorkbenchHeader } from "./SourceWorkbenchHeader";
import { SourceWorkbenchImportPanel } from "./SourceWorkbenchImportPanel";
import { SourceWorkbenchOperationsPanel } from "./SourceWorkbenchOperationsPanel";
import { SourceWorkbenchQueryFormulaPanel } from "./SourceWorkbenchQueryFormulaPanel";
import { SourceWorkbenchRelationshipPanel } from "./SourceWorkbenchRelationshipPanel";

export function SourceWorkbench({
  status,
  preview,
  query,
  workbench,
  relationshipPreview,
  formulaPreview,
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
  onBusinessDashboardOperation,
  onAsk,
  onOpenBusinessStep,
  onOpenDashboard,
}: SourceWorkbenchProps) {
  const {
    tables,
    fields,
    metrics,
    relationships,
    relationshipRecommendations,
    importJobs,
    importPolicies,
    connectors,
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
  const [activeTableKey, setActiveTableKey] = useState(firstTableKey);
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
    indexCandidateName,
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

  const [filePath, setFilePath] = useState("");
  const [targetTable, setTargetTable] = useState("");
  const [targetName, setTargetName] = useState("");
  const [importMode, setImportMode] = useState("merge");
  const [uniqueFields, setUniqueFields] = useState("");
  const [conflictRule, setConflictRule] = useState("overwrite");
  const [folderImportPlan, setFolderImportPlan] = useState<FolderImportPlan | null>(null);
  const activeImportPolicy = importPolicies.find((policy) => policy.table_key === targetTable);
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
  const [connectorEditingKey, setConnectorEditingKey] = useState("");
  const [connectorName, setConnectorName] = useState("文件同步");
  const [connectorType, setConnectorType] = useState("file");
  const [connectorProvider, setConnectorProvider] = useState("local-file");
  const [connectorStatus, setConnectorStatus] = useState("draft");
  const [connectorEndpoint, setConnectorEndpoint] = useState("");
  const [connectorImportMode, setConnectorImportMode] = useState("auto");
  const [connectorTargetTable, setConnectorTargetTable] = useState(firstTableKey);
  const [connectorUniqueFields, setConnectorUniqueFields] = useState("");
  const [connectorConflictRule, setConnectorConflictRule] = useState("overwrite");
  const [connectorNotes, setConnectorNotes] = useState("");
  const [importOperationReceipt, setImportOperationReceipt] = useState<WorkbenchOperationReceipt | null>(null);
  const [connectorOperationReceipt, setConnectorOperationReceipt] = useState<WorkbenchOperationReceipt | null>(null);
  const [sourceProfileInputs, setSourceProfileInputs] = useState("");
  const [sourceProfileLabel, setSourceProfileLabel] = useState(biText("证据摘要", "Source profile"));
  const [sourceProfileResult, setSourceProfileResult] = useState<Record<string, unknown> | null>(null);
  const [sourceProfileError, setSourceProfileError] = useState("");
  const [businessDashboardResult, setBusinessDashboardResult] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  useEffect(() => {
    if (!activeNavigationModule) return;
    setNavigationName(activeNavigationModule.name);
    setNavigationSort(String(activeNavigationModule.sort));
  }, [activeNavigationModule?.moduleKey, activeNavigationModule?.name, activeNavigationModule?.sort]);

  useEffect(() => {
    if (!firstTableKey) return;
    const firstTableName = tables[0]?.display_name ?? firstTableKey;
    setActiveTableKey((current) => tableKeySet.has(current) ? current : firstTableKey);
    setManagedSourceKey((current) => tableKeySet.has(current) ? current : firstTableKey);
    setSourceRenameName((current) => current || firstTableName);
    setConnectorTargetTable((current) => tableKeySet.has(current) ? current : firstTableKey);
  }, [firstTableKey, tableKeySet, tables]);

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
      return {
        ...current,
        leftTable,
        rightTable,
        leftField: hasLeftField ? current.leftField : leftFields[0]?.field_name ?? "",
        rightField: hasRightField ? current.rightField : rightFields[0]?.field_name ?? "",
      };
    });
  }, [fieldsByTable, tableKeySet, tables]);

  function importOptions(confirm = false): ImportOptions {
    return buildImportOptions({
      filePath,
      targetTable,
      targetName,
      importMode,
      uniqueFields,
      conflictRule,
      confirm,
    });
  }

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

  function connectorOptions(confirm = false): ConnectorOptions {
    return buildConnectorOptions({
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
      confirm,
    });
  }

  function loadConnector(connector: DataConnectorConfig) {
    setConnectorEditingKey(connector.connectorKey);
    setConnectorName(connector.name);
    setConnectorType(connector.type || "file");
    setConnectorProvider(connector.provider || "");
    setConnectorStatus(connector.status || "draft");
    setConnectorEndpoint(String(connector.config?.endpoint ?? ""));
    setConnectorImportMode(String(connector.config?.importMode ?? "auto"));
    setConnectorTargetTable(String(connector.config?.targetTableKey ?? ""));
    setConnectorUniqueFields((connector.config?.uniqueFields ?? []).join(", "));
    setConnectorConflictRule(String(connector.config?.conflictRule ?? "overwrite"));
    setConnectorNotes(String(connector.config?.notes ?? ""));
  }

  function resetConnectorDraft() {
    setConnectorEditingKey("");
    setConnectorName("文件同步");
    setConnectorType("file");
    setConnectorProvider("local-file");
    setConnectorStatus("draft");
    setConnectorEndpoint("");
    setConnectorImportMode("auto");
    setConnectorTargetTable(firstTableKey);
    setConnectorUniqueFields("");
    setConnectorConflictRule("overwrite");
    setConnectorNotes("");
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

  async function runImportPreviewAction() {
    const result = await onPreview(importOptions(false));
    setFolderImportPlan(null);
    let receiptTargetTable = targetTable;
    let receiptImportMode = importMode;
    let receiptUniqueFields = uniqueFields;
    if (result.ok && result.matchedTable) {
      receiptTargetTable = result.matchedTable.table_key;
      receiptImportMode = "merge";
      setTargetTable(result.matchedTable.table_key);
      setTargetName(result.matchedTable.display_name);
      setImportMode("merge");
    } else if (result.ok) {
      const suggestedTable = String(result.suggestedTableKey || "").trim();
      const suggestedName = String(result.suggestedDisplayName || suggestedTable).trim();
      if (suggestedTable) {
        setTargetTable(suggestedTable);
        receiptTargetTable = suggestedTable;
      }
      if (suggestedName) setTargetName(suggestedName);
      setImportMode("create");
      receiptImportMode = "create";
    }
    if (result.ok) {
      const suggestedUniqueFields = result.mergePolicyPreview.uniqueFields;
      if (!uniqueFields.trim() && suggestedUniqueFields.length) {
        receiptUniqueFields = suggestedUniqueFields.join(", ");
        setUniqueFields(receiptUniqueFields);
      }
    }
    setImportOperationReceipt(buildImportPreviewReceipt({ filePath, targetTable: receiptTargetTable, importMode: receiptImportMode, uniqueFields: receiptUniqueFields, conflictRule }));
  }

  async function runImportCommitAction(confirm: boolean) {
    await onCommitImport(importOptions(confirm));
    setFolderImportPlan(null);
    setImportOperationReceipt(buildImportCommitReceipt({
      confirm,
      preview,
      matchedTableName,
      targetTable,
      importInsertRows,
      importUpdateRows,
      importSkipRows,
      importAfterRows,
    }));
  }

  async function runFolderImportPreviewAction() {
    const result = await onPreviewFolderImport({ path: filePath, limit: 200, recursive: true });
    setFolderImportPlan(result);
    const firstGroup = result.groups[0];
    if (firstGroup) {
      setTargetTable(firstGroup.tableKey);
      setTargetName(firstGroup.displayName);
      setImportMode(firstGroup.willMerge ? "merge" : "create");
      setUniqueFields(firstGroup.uniqueFields.join(", "));
    }
    setImportOperationReceipt({
      tone: result.fileCount > 0 ? "ok" : "warn",
      title: result.fileCount > 0
        ? biText(`发现 ${result.fileCount} 个可导入文件`, `${result.fileCount} importable files found`)
        : biText("没有发现可导入文件", "No importable files found"),
      detail: result.fileCount > 0
        ? biText(`将归并为 ${result.tableCount} 张业务表。`, `They will be grouped into ${result.tableCount} business tables.`)
        : biText("请选择包含 CSV 或 Excel 的文件夹。", "Choose a folder with CSV or Excel files."),
      nextStep: result.fileCount > 0
        ? biText("确认后按同类表合并导入，导入前不会写入。", "Confirm to merge similar files. Nothing writes before confirmation.")
        : biText("粘贴文件夹路径后重新检查。", "Paste a folder path and check again."),
      technical: result.groups.map((group) => `${group.displayName}: ${group.fileCount} files, ${group.rowCount} rows`).join("; ") || result.path,
    });
  }

  async function runFolderImportCommitAction(confirm: boolean) {
    const result = await onCommitFolderImport({ path: filePath, limit: 200, recursive: true, confirm });
    setFolderImportPlan(result);
    setImportOperationReceipt({
      tone: result.committed ? "ok" : "warn",
      title: result.committed
        ? biText("文件夹导入已完成", "Folder import completed")
        : biText("文件夹导入待确认", "Folder import needs confirmation"),
      detail: biText(`已处理 ${result.fileCount} 个文件，归并为 ${result.tableCount} 张业务表。`, `${result.fileCount} files grouped into ${result.tableCount} business tables.`),
      nextStep: result.committed
        ? biText("下一步可以让 Agent 生成单图或看板草案。", "Next, ask Agent to create a chart or dashboard draft.")
        : biText("确认后才会写入工作区。", "Confirm before writing to the workspace."),
      technical: result.groups.map((group) => `${group.displayName}: ${group.fileCount} files, ${group.rowCount} rows`).join("; ") || result.path,
    });
  }

  async function runImportPolicyAction(confirm: boolean) {
    await onImportPolicy(buildImportPolicyOptions({ targetTable, uniqueFields, conflictRule, confirm }));
    setImportOperationReceipt(buildImportPolicyReceipt({ confirm, targetTable, uniqueFields, conflictRule }));
  }

  async function runConnectorSaveAction(confirm: boolean) {
    await onSaveConnector(connectorOptions(confirm));
    setConnectorOperationReceipt(buildConnectorSaveReceipt({
      confirm,
      connectorName,
      connectorTargetTable,
      connectorEndpoint,
      connectorImportMode,
      connectorUniqueFields,
      connectorConflictRule,
    }));
  }

  async function runConnectorSyncAction(connector: DataConnectorConfig, confirm: boolean) {
    await onSyncConnector({ connector: connector.connectorKey, confirm });
    setConnectorOperationReceipt(buildConnectorSyncReceipt(connector, confirm));
  }

  async function runConnectorRemoveAction(connector: DataConnectorConfig) {
    await onRemoveConnector({ connector: connector.connectorKey, confirm: true });
    setConnectorOperationReceipt(buildConnectorRemoveReceipt(connector));
  }

  async function runSourceProfile(label: string, options: SourceIntelligenceRunOptions) {
    setBusy(label);
    setSourceProfileResult(null);
    setSourceProfileError("");
    try {
      const result = await onSourceIntelligenceRun(options);
      setSourceProfileResult(result && typeof result === "object" ? result as Record<string, unknown> : null);
    } catch (error) {
      setSourceProfileError(sourceProfileErrorMessage(error));
    } finally {
      setBusy(null);
    }
  }

  async function runBusinessDashboard(confirm: boolean) {
    const result = await onBusinessDashboardOperation({
      op: confirm ? "create" : "draft",
      table: selectedTableKey,
      limit: 10,
      confirm,
    });
    setBusinessDashboardResult(result);
    if (confirm && (typeof result.createdDashboardKey === "string" || typeof result.savedDashboardKey === "string")) {
      onOpenDashboard();
    }
  }

  const { runtimeStatus, queryInfo, queryRuntime } = buildSourceWorkbenchRuntimeSummary(workbench, status, query);
  const effectiveMetricField = measureFields.some((field) => field.field_name === metricField) ? metricField : measureFields[0]?.field_name ?? "*";
  const effectiveMetricDimension = groupFields.some((field) => field.field_name === metricDimension) ? metricDimension : groupFields[0]?.field_name ?? "";
  const metricResultRows = resultRows(semanticMetricResult).slice(0, 5);
  const latestSourceProfile = sourceIntelligenceRuns[0];
  const latestImportedSource = sourceRuns[0];
  const {
    sourceProfileComplete,
    previewReadable,
    sourceProfileRunning,
    sourceProfileRunningLabel,
    dashboardMeasureName,
    dashboardDimensionName,
    dashboardTimeName,
    dashboardRecipeReady,
    dashboardRecipeEvidenceCount,
    dashboardRecipeCards,
    recommendedPrimaryAction,
    beginnerPlan,
    sourceAgentPrompts,
  } = buildSourceWorkbenchGuidance({
    busy,
    preview,
    tables,
    fields,
    selectedFields,
    measureFields,
    groupFields,
    relationships,
    selectedMetrics,
    latestSourceProfile,
    selectedTableKey,
  });
  const {
    matchedTableName,
    importInsertRows,
    importUpdateRows,
    importSkipRows,
    importDuplicateRows,
    importEmptyKeyRows,
    importAfterRows,
    importKeyHealthy,
  } = buildImportPreviewSummary({ preview, previewReadable, targetName });
  const hasData = tables.length > 0 || status.counts.tables > 0;
  const showExpertWorkbench = showAdvanced;
  const activation = buildProductActivation({ status, workbench });
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

  return (
    <section className={hasData ? "mainPanel" : "mainPanel sourceBeginnerMode"} aria-labelledby="source-workbench-title">
      <SourceWorkbenchHeader
        sourceProfileRunning={sourceProfileRunning}
      />

      <ProductActivationPanel
        activation={activation}
        compact={hasData}
        currentStep="data"
        onOpenStep={onOpenBusinessStep}
        testId="source-product-activation"
        title={hasData ? undefined : biText("先接入一份真实数据", "Connect one real dataset first")}
      />

      <div className="workbenchGrid">
        <SourceWorkbenchDataEntryPanel
          sourceIntelligenceRuns={sourceIntelligenceRuns}
          sourceProfileInputs={sourceProfileInputs}
          sourceProfileLabel={sourceProfileLabel}
          sourceProfileResult={sourceProfileResult}
          sourceProfileError={sourceProfileError}
          sourceProfileRunning={sourceProfileRunning}
          sourceProfileRunningLabel={sourceProfileRunningLabel}
          setSourceProfileInputs={setSourceProfileInputs}
          setSourceProfileLabel={setSourceProfileLabel}
          sourceProfileOptions={sourceProfileOptions}
          runSourceProfile={runSourceProfile}
          onAsk={onAsk}
        />

        <SourceWorkbenchImportPanel
          preview={preview}
          busy={busy}
          filePath={filePath}
          targetTable={targetTable}
          targetName={targetName}
          importMode={importMode}
          uniqueFields={uniqueFields}
          conflictRule={conflictRule}
          activeImportPolicy={activeImportPolicy}
          previewReadable={previewReadable}
          matchedTableName={matchedTableName}
          importInsertRows={importInsertRows}
          importUpdateRows={importUpdateRows}
          importSkipRows={importSkipRows}
          importAfterRows={importAfterRows}
          importDuplicateRows={importDuplicateRows}
          importEmptyKeyRows={importEmptyKeyRows}
          importKeyHealthy={importKeyHealthy}
          importOperationReceipt={importOperationReceipt}
          folderImportPlan={folderImportPlan}
          setFilePath={setFilePath}
          setTargetTable={setTargetTable}
          setTargetName={setTargetName}
          setImportMode={setImportMode}
          setUniqueFields={setUniqueFields}
          setConflictRule={setConflictRule}
          runBusy={runBusy}
          runImportPreviewAction={runImportPreviewAction}
          runImportCommitAction={runImportCommitAction}
          runFolderImportPreviewAction={runFolderImportPreviewAction}
          runFolderImportCommitAction={runFolderImportCommitAction}
          runImportPolicyAction={runImportPolicyAction}
        />

        {hasData ? (
          <SourceWorkbenchDataManagementPanel
            busy={busy}
            sourceRuns={sourceRuns}
            tables={tables}
            selectedManagedSourceKey={selectedManagedSourceKey}
            sourceRenameName={sourceRenameName}
            setSourceRenameName={setSourceRenameName}
            selectManagedSource={selectManagedSource}
            runBusy={runBusy}
            onInspectSource={onInspectSource}
            onRenameSource={onRenameSource}
            onDeleteSource={onDeleteSource}
          />
        ) : null}

        {hasData ? (
          <SourceWorkbenchActionPanel
            busy={busy}
            recommendedPrimaryAction={recommendedPrimaryAction}
            beginnerPlan={beginnerPlan}
            sourceProfileRunning={sourceProfileRunning}
            sourceProfileComplete={sourceProfileComplete}
            latestImportedSource={latestImportedSource}
            latestSourceProfile={latestSourceProfile}
            relationshipsCount={relationships.length}
            selectedMetricsCount={selectedMetrics.length}
            dashboardRecipeReady={dashboardRecipeReady}
            dashboardRecipeEvidenceCount={dashboardRecipeEvidenceCount}
            dashboardRecipeCards={dashboardRecipeCards}
            businessDashboardResult={businessDashboardResult}
            selectedTableKey={selectedTableKey}
            dashboardDimensionName={dashboardDimensionName}
            dashboardMeasureName={dashboardMeasureName}
            dashboardTimeName={dashboardTimeName}
            indexCandidateName={indexCandidateName}
            showAdvanced={showAdvanced}
            setShowAdvanced={setShowAdvanced}
            sourceAgentPrompts={sourceAgentPrompts}
            runBusy={runBusy}
            sourceProfileOptions={sourceProfileOptions}
            runSourceProfile={runSourceProfile}
            runBusinessDashboard={runBusinessDashboard}
            onAsk={onAsk}
          />
        ) : null}

        {showExpertWorkbench ? (
          <>
            <SourceWorkbenchOperationsPanel
              busy={busy}
              navigationModules={navigationModules}
              activeNavigationModule={activeNavigationModule}
              navigationModuleKey={navigationModuleKey}
              navigationName={navigationName}
              navigationSort={navigationSort}
              navigationResult={navigationResult}
              setNavigationModuleKey={setNavigationModuleKey}
              setNavigationName={setNavigationName}
              setNavigationSort={setNavigationSort}
              runBusy={runBusy}
              runNavigationOperation={runNavigationOperation}
            />

            <SourceWorkbenchFieldMetricPanel
              showAdvanced={showAdvanced}
              busy={busy}
              tables={tables}
              selectedTableKey={selectedTableKey}
              selectedFields={selectedFields}
              selectedMetrics={selectedMetrics}
              fieldRoles={fieldRoles}
              fieldUsages={fieldUsages}
              safeAggregations={safeAggregations}
              fieldSemanticReadiness={fieldSemanticReadiness}
              latestSourceProfile={latestSourceProfile}
              metricName={metricName}
              effectiveMetricField={effectiveMetricField}
              metricAggregation={metricAggregation}
              effectiveMetricDimension={effectiveMetricDimension}
              measureFields={measureFields}
              groupFields={groupFields}
              semanticMetricResult={semanticMetricResult}
              metricResultRows={metricResultRows}
              setActiveTableKey={setActiveTableKey}
              setMetricName={setMetricName}
              setMetricField={setMetricField}
              setMetricAggregation={setMetricAggregation}
              setMetricDimension={setMetricDimension}
              setSemanticMetricResult={setSemanticMetricResult}
              fieldDraft={fieldDraft}
              updateFieldDraft={updateFieldDraft}
              metricDraft={metricDraft}
              runBusy={runBusy}
              onAsk={onAsk}
              onInferSemantics={onInferSemantics}
              onSetSemantic={onSetSemantic}
              onInferMetrics={onInferMetrics}
              onAddMetric={onAddMetric}
              onQueryMetric={onQueryMetric}
            />

            <SourceWorkbenchQueryFormulaPanel
              showAdvanced={showAdvanced}
              busy={busy}
              tables={tables}
              selectedTableKey={selectedTableKey}
              groupFields={groupFields}
              measureFields={measureFields}
              safeAggregations={safeAggregations}
              queryForm={queryForm}
              queryRows={queryRows}
              queryInfo={queryInfo}
              queryRuntime={queryRuntime}
              runtimeStatus={runtimeStatus}
              formulaName={formulaName}
              formulaExpression={formulaExpression}
              formulaMode={formulaMode}
              formulaPreview={formulaPreview}
              formulaMutation={formulaMutation}
              selectedFormulaAssets={selectedFormulaAssets}
              setQueryForm={setQueryForm}
              setFormulaName={setFormulaName}
              setFormulaExpression={setFormulaExpression}
              setFormulaMode={setFormulaMode}
              setFormulaMutation={setFormulaMutation}
              runBusy={runBusy}
              onQuery={onQuery}
              onFormulaPreview={onFormulaPreview}
              onFormulaSave={onFormulaSave}
              onFormulaDelete={onFormulaDelete}
            />

            <SourceWorkbenchRelationshipPanel
              showAdvanced={showAdvanced}
              busy={busy}
              tables={tables}
              fields={fields}
              relationships={relationships}
              relationshipRecommendations={relationshipRecommendations}
              relationshipPreview={relationshipPreview}
              relationshipForm={relationshipForm}
              setRelationshipForm={setRelationshipForm}
              runBusy={runBusy}
              onRelationshipPreview={onRelationshipPreview}
              onRelationshipSave={onRelationshipSave}
            />

            <SourceWorkbenchConnectorPanel
              showAdvanced={showAdvanced}
              busy={busy}
              connectors={connectors}
              importJobs={importJobs}
              connectorEditingKey={connectorEditingKey}
              connectorName={connectorName}
              connectorType={connectorType}
              connectorProvider={connectorProvider}
              connectorStatus={connectorStatus}
              connectorEndpoint={connectorEndpoint}
              connectorImportMode={connectorImportMode}
              connectorTargetTable={connectorTargetTable}
              connectorUniqueFields={connectorUniqueFields}
              connectorConflictRule={connectorConflictRule}
              connectorNotes={connectorNotes}
              connectorOperationReceipt={connectorOperationReceipt}
              setConnectorName={setConnectorName}
              setConnectorType={setConnectorType}
              setConnectorProvider={setConnectorProvider}
              setConnectorStatus={setConnectorStatus}
              setConnectorEndpoint={setConnectorEndpoint}
              setConnectorImportMode={setConnectorImportMode}
              setConnectorTargetTable={setConnectorTargetTable}
              setConnectorUniqueFields={setConnectorUniqueFields}
              setConnectorConflictRule={setConnectorConflictRule}
              setConnectorNotes={setConnectorNotes}
              resetConnectorDraft={resetConnectorDraft}
              loadConnector={loadConnector}
              runBusy={runBusy}
              runConnectorSaveAction={runConnectorSaveAction}
              runConnectorSyncAction={runConnectorSyncAction}
              runConnectorRemoveAction={runConnectorRemoveAction}
              onRemoveImportJob={onRemoveImportJob}
            />
          </>
        ) : (
          <details className="advancedDetails sourceExpertDetails" data-testid="source-expert-details">
            <summary><Bilingual zh="显示高级配置" en="Show advanced configuration" /></summary>
            <p>
              <Bilingual
                zh="表管理、字段口径、关系、公式和连接器默认收起。需要调整底层模型时再进入，不打断当前导入和生成图表路径。"
                en="Table management, metrics, relationships, formulas, and connectors stay collapsed by default. Open them only when tuning the underlying model."
              />
            </p>
            <button className="secondaryButton" onClick={() => setShowAdvanced(true)} type="button">
              <Bilingual zh="打开高级工作台" en="Open advanced workbench" />
            </button>
          </details>
        )}

      </div>
    </section>
  );
}
