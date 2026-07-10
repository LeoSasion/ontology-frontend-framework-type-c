import { useEffect, useMemo, useState } from "react";
import type { DataConnectorConfig, FieldConfig, FormulaMutationPayload } from "../types";
import type { RelationshipSaveOptions } from "../dashboardCanvasContracts";
import type { QueryOptions, SourceWorkbenchProps } from "../sourceWorkbenchContracts";
import {
  buildFieldSemanticReadiness,
  buildSourceWorkbenchCollections,
  buildSourceWorkbenchRuntimeSummary,
  buildSourceWorkbenchSelection,
  resultRows,
  sourceProfileErrorMessage,
} from "../sourceWorkbenchModel";
import {
  buildConnectorOptions,
  buildMetricDraft,
  buildSourceProfileOptions,
  type ConnectorOptions,
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
import { buildConnectorRemoveReceipt, buildConnectorSaveReceipt, buildConnectorSyncReceipt, type WorkbenchOperationReceipt } from "../sourceWorkbenchReceiptModel";
import { buildProductActivation } from "../productActivationModel";
import { useSourceWorkbenchImportController } from "../useSourceWorkbenchImportController";
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
  const [connectorOperationReceipt, setConnectorOperationReceipt] = useState<WorkbenchOperationReceipt | null>(null);
  const [sourceProfileInputs, setSourceProfileInputs] = useState("");
  const [sourceProfileLabel, setSourceProfileLabel] = useState(biText("证据摘要", "Source profile"));
  const [sourceProfileResult, setSourceProfileResult] = useState<Record<string, unknown> | null>(null);
  const [sourceProfileError, setSourceProfileError] = useState("");
  const [businessDashboardResult, setBusinessDashboardResult] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const importController = useSourceWorkbenchImportController({
    preview,
    importPolicies,
    onPreview,
    onCommitImport,
    onPreviewFolderImport,
    onCommitFolderImport,
    onImportPolicy,
  });

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
          {...importController}
          busy={busy}
          runBusy={runBusy}
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
