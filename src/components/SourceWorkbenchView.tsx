import { Suspense, useEffect, useRef, useState } from "react";
import { relationshipRequestScopeKey } from "../dashboardCanvasRelationshipModel";
import { emptyRelationshipPreview } from "../emptyWorkspaceData";
import { invalidateRelationshipRequests } from "../relationshipRequestGuard";
import type { SourceWorkbenchProps } from "../sourceWorkbenchContracts";
import type { useSourceWorkbenchState } from "../useSourceWorkbenchState";
import {
  SourceWorkbenchAdvancedLoading,
  SourceWorkbenchConnectorPanel,
  SourceWorkbenchFieldMetricPanel,
  SourceWorkbenchOperationsPanel,
  SourceWorkbenchQueryFormulaPanel,
  SourceWorkbenchRelationshipPanel,
} from "../sourceWorkbenchAdvancedModules";
import {
  SourceWorkbenchActionPanel,
  SourceWorkbenchDataManagementPanel,
} from "../sourceWorkbenchDeferredModules";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";
import { SourceWorkbenchHeader } from "./SourceWorkbenchHeader";
import { SourceWorkbenchDataEntryPanel } from "./SourceWorkbenchDataEntryPanel";
import { SourceWorkbenchImportPanel } from "./SourceWorkbenchImportPanel";
import { SourceJobRuntimePanel } from "./SourceJobRuntimePanel";

type SourceWorkbenchViewProps = SourceWorkbenchProps & ReturnType<typeof useSourceWorkbenchState>;

export function SourceWorkbenchView({
  formulaPreview,
  status,
  onAsk,
  onOpenAnalysis,
  onInspectSource,
  onRenameSource,
  onDeleteSource,
  onRemoveImportJob,
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
  sourceProfileComplete,
  sourceProfileRunning,
  sourceProfileRunningLabel,
  recommendedPrimaryAction,
  beginnerPlan,
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
}: SourceWorkbenchViewProps) {
  const [relationshipPreview, setRelationshipPreview] = useState(emptyRelationshipPreview);
  const relationshipScope = relationshipRequestScopeKey(status.workspace.id, relationshipForm);
  const relationshipScopeRef = useRef(relationshipScope);

  useEffect(() => {
    if (relationshipScopeRef.current !== relationshipScope) {
      relationshipScopeRef.current = relationshipScope;
      invalidateRelationshipRequests();
    }
    setRelationshipPreview(emptyRelationshipPreview);
  }, [relationshipScope]);

  async function runRelationshipPreview(options: Parameters<typeof onRelationshipPreview>[0]) {
    const requestScope = relationshipRequestScopeKey(status.workspace.id, options);
    relationshipScopeRef.current = requestScope;
    const result = await onRelationshipPreview(options);
    if (result && relationshipScopeRef.current === requestScope) setRelationshipPreview(result);
  }

  async function runRelationshipSave(options: Parameters<typeof onRelationshipSave>[0]) {
    const requestScope = relationshipRequestScopeKey(status.workspace.id, options);
    relationshipScopeRef.current = requestScope;
    const result = await onRelationshipSave(options);
    if (result && relationshipScopeRef.current === requestScope) setRelationshipPreview(result);
  }

  return (
    <section className={hasData ? "mainPanel" : "mainPanel sourceBeginnerMode"} aria-labelledby="source-workbench-title">
      <SourceWorkbenchHeader sourceProfileRunning={sourceProfileRunning} />

      <div className="workbenchGrid">
        {!hasData ? <SourceWorkbenchImportPanel {...importController} busy={busy} runBusy={runBusy} /> : null}

        {hasData ? <SourceJobRuntimePanel /> : null}

        {hasData && !sourceProfileComplete ? <div className="importSuccessNextStep" data-testid="import-success-next-step">
          <Icon name={sourceProfileError || sourceProfileRunning ? "evidence" : "check"} />
          <div>
            <strong>{sourceProfileError
              ? biText("数据已导入，证据生成失败", "Data imported; evidence generation failed")
              : sourceProfileRunning
                ? biText("数据已导入，正在生成证据", "Data imported; generating evidence")
                : biText(`已接入 ${tables.length} 张数据表`, `${tables.length} data tables connected`)}</strong>
            <span>{connectedRowCount.toLocaleString()} {biText("行", "rows")} · {connectedFieldCount.toLocaleString()} {biText("字段", "fields")}</span>
            <small>{sourceProfileError || biText("系统会沿用本次导入来源，无需再次填写路径。", "The imported source is reused; no path needs to be entered again.")}</small>
            {sourceProfileError && sourceProfileInputs.trim() ? <button
              className="secondaryButton compactAction"
              disabled={sourceProfileRunning}
              onClick={() => runSourceProfile(biText("正在重试证据", "Retrying evidence"), sourceProfileOptions())}
              type="button"
            >
              {biText("按本次来源重试", "Retry this source")}
            </button> : null}
          </div>
        </div> : null}

        {hasData ? (
          <Suspense fallback={<SourceWorkbenchAdvancedLoading />}><SourceWorkbenchActionPanel
            recommendedPrimaryAction={recommendedPrimaryAction}
            beginnerPlan={beginnerPlan}
            sourceProfileRunning={sourceProfileRunning}
            sourceProfileComplete={sourceProfileComplete}
            latestSourceProfile={latestSourceProfile}
            showAdvanced={showAdvanced}
            setShowAdvanced={setShowAdvanced}
            sourceProfileOptions={sourceProfileOptions}
            runSourceProfile={runSourceProfile}
            onOpenAnalysis={onOpenAnalysis}
          /></Suspense>
        ) : null}

        {hasData ? <details className="advancedDetails sourceSecondaryDetails" data-testid="source-evidence-details">
          <summary>{biText("重新生成、补充证据或管理数据", "Regenerate or supplement evidence, or manage data")}</summary>
          <Suspense fallback={<SourceWorkbenchAdvancedLoading />}><div className="sourceSecondaryGrid">
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
            <SourceWorkbenchImportPanel {...importController} busy={busy} runBusy={runBusy} />
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
          </div></Suspense>
        </details> : null}

        {showExpertWorkbench ? (
          <Suspense fallback={<SourceWorkbenchAdvancedLoading />}>
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
              onRelationshipPreview={runRelationshipPreview}
              onRelationshipSave={runRelationshipSave}
            />

            <SourceWorkbenchConnectorPanel
              {...connectorController}
              showAdvanced={showAdvanced}
              busy={busy}
              connectors={connectors}
              connectorAdapters={connectorAdapters}
              importJobs={importJobs}
              runBusy={runBusy}
              onRemoveImportJob={onRemoveImportJob}
            />
          </Suspense>
        ) : null}
      </div>
    </section>
  );
}
