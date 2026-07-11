import { Suspense } from "react";
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
  SourceWorkbenchDataEntryPanel,
  SourceWorkbenchDataManagementPanel,
} from "../sourceWorkbenchDeferredModules";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";
import { SourceWorkbenchHeader } from "./SourceWorkbenchHeader";
import { SourceWorkbenchImportPanel } from "./SourceWorkbenchImportPanel";

type SourceWorkbenchViewProps = SourceWorkbenchProps & ReturnType<typeof useSourceWorkbenchState>;

export function SourceWorkbenchView({
  formulaPreview,
  relationshipPreview,
  onAsk,
  onOpenDashboard,
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
  indexCandidateName,
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
  businessDashboardResult,
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
  dashboardMeasureName,
  dashboardDimensionName,
  dashboardTimeName,
  dashboardRecipeReady,
  dashboardRecipeEvidenceCount,
  dashboardRecipeCards,
  recommendedPrimaryAction,
  beginnerPlan,
  sourceAgentPrompts,
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
  runBusinessDashboard,
  metricDraft,
  sourceProfileOptions,
  sourceRenameName,
}: SourceWorkbenchViewProps) {
  return (
    <section className={hasData ? "mainPanel" : "mainPanel sourceBeginnerMode"} aria-labelledby="source-workbench-title">
      <SourceWorkbenchHeader sourceProfileRunning={sourceProfileRunning} />

      <div className="workbenchGrid">
        {!hasData ? <SourceWorkbenchImportPanel {...importController} busy={busy} runBusy={runBusy} /> : null}

        {hasData && !sourceProfileComplete ? <div className="importSuccessNextStep" data-testid="import-success-next-step">
          <Icon name="check" />
          <div>
            <strong>{biText(`已接入 ${tables.length} 张数据表`, `${tables.length} data tables connected`)}</strong>
            <span>{connectedRowCount.toLocaleString()} {biText("行", "rows")} · {connectedFieldCount.toLocaleString()} {biText("字段", "fields")}</span>
            <small>{biText("下一步生成证据摘要，再创建图表。", "Next, create the evidence summary, then create a chart.")}</small>
          </div>
        </div> : null}

        {hasData && !sourceProfileComplete ? <Suspense fallback={<SourceWorkbenchAdvancedLoading />}><SourceWorkbenchDataEntryPanel
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
        /></Suspense> : null}

        {hasData && sourceProfileComplete ? (
          <Suspense fallback={<SourceWorkbenchAdvancedLoading />}><SourceWorkbenchActionPanel
            busy={busy}
            recommendedPrimaryAction={recommendedPrimaryAction}
            beginnerPlan={beginnerPlan}
            sourceProfileRunning={sourceProfileRunning}
            sourceProfileComplete={sourceProfileComplete}
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
            onOpenDashboard={onOpenDashboard}
          /></Suspense>
        ) : null}

        {hasData ? <details className="advancedDetails sourceSecondaryDetails" data-testid="source-evidence-details">
          <summary>{sourceProfileComplete ? biText("查看或更新证据摘要", "Review or refresh evidence") : biText("导入与数据资产管理", "Import and manage data assets")}</summary>
          <Suspense fallback={<SourceWorkbenchAdvancedLoading />}><div className="sourceSecondaryGrid">
            {sourceProfileComplete ? <SourceWorkbenchDataEntryPanel
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
            /> : null}
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
              onRelationshipPreview={onRelationshipPreview}
              onRelationshipSave={onRelationshipSave}
            />

            <SourceWorkbenchConnectorPanel
              {...connectorController}
              showAdvanced={showAdvanced}
              busy={busy}
              connectors={connectors}
              importJobs={importJobs}
              runBusy={runBusy}
              onRemoveImportJob={onRemoveImportJob}
            />
          </Suspense>
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
