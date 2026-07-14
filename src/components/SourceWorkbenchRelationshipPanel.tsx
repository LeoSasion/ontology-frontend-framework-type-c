import { lazy, Suspense, useMemo, type Dispatch, type SetStateAction } from "react";
import type { FieldConfig, RelationshipPreviewPayload, RelationshipRecommendation, RelationshipRecord, WorkbenchTable } from "../types";
import type { RelationshipSaveOptions } from "../dashboardCanvasContracts";
import { relationshipRecordMappingLabel, relationshipSafetyFacts } from "../dashboardCanvasRelationshipModel";
import { confidencePercent, metricValue, numberValue } from "../sourceWorkbenchModel";
import { Bilingual, biText } from "./Bilingual";
import { RelationshipAutoModelGraph } from "./RelationshipAutoModelGraph";

const RelationshipSafetyControls = lazy(() => import("./RelationshipSafetyControls"));

type SourceWorkbenchRelationshipPanelProps = {
  showAdvanced: boolean;
  busy: string | null;
  tables: WorkbenchTable[];
  fields: FieldConfig[];
  relationships: RelationshipRecord[];
  relationshipRecommendations: RelationshipRecommendation[];
  relationshipPreview: RelationshipPreviewPayload;
  relationshipForm: RelationshipSaveOptions;
  setRelationshipForm: Dispatch<SetStateAction<RelationshipSaveOptions>>;
  runBusy: (label: string, action: () => Promise<void>) => Promise<void>;
  onRelationshipPreview: (options: RelationshipSaveOptions) => Promise<void>;
  onRelationshipSave: (options: RelationshipSaveOptions) => Promise<void>;
};

export function SourceWorkbenchRelationshipPanel({
  showAdvanced,
  busy,
  tables,
  fields,
  relationships,
  relationshipRecommendations,
  relationshipPreview,
  relationshipForm,
  setRelationshipForm,
  runBusy,
  onRelationshipPreview,
  onRelationshipSave,
}: SourceWorkbenchRelationshipPanelProps) {
  const leftFields = useMemo(
    () => fields.filter((field) => field.table_key === relationshipForm.leftTable),
    [fields, relationshipForm.leftTable],
  );
  const rightFields = useMemo(
    () => fields.filter((field) => field.table_key === relationshipForm.rightTable),
    [fields, relationshipForm.rightTable],
  );
  const matchingRelationshipRecommendation = relationshipRecommendations.find((recommendation) => {
    const mapping = recommendation.fieldMappings[0];
    return recommendation.leftTableKey === relationshipForm.leftTable &&
      recommendation.rightTableKey === relationshipForm.rightTable &&
      mapping?.leftField === relationshipForm.leftField &&
      mapping?.rightField === relationshipForm.rightField;
  }) ?? relationshipRecommendations.find((recommendation) =>
    recommendation.leftTableKey === relationshipForm.leftTable &&
    recommendation.rightTableKey === relationshipForm.rightTable,
  ) ?? relationshipRecommendations[0];
  const matchingRecommendationMapping = matchingRelationshipRecommendation?.fieldMappings[0];
  const relationshipPreviewMetrics = relationshipPreview.relationshipPreview.metrics;
  const relationshipConfidence = Number(relationshipPreviewMetrics.confidence ?? matchingRelationshipRecommendation?.confidence ?? 0);
  const relationshipUnmatchedRows = numberValue(relationshipPreviewMetrics.unmatchedLeftRows ?? matchingRelationshipRecommendation?.previewMetrics?.unmatchedLeftRows);
  const relationshipOverlapKeys = numberValue(relationshipPreviewMetrics.overlapKeys ?? matchingRelationshipRecommendation?.previewMetrics?.overlapKeys);
  const relationshipAlreadySaved = relationships.some((relationship) =>
    relationship.left_table_key === relationshipForm.leftTable &&
    relationship.right_table_key === relationshipForm.rightTable &&
    relationship.left_field === relationshipForm.leftField &&
    relationship.right_field === relationshipForm.rightField,
  );
  const relationshipDecisionState = relationshipAlreadySaved
    ? biText("已保存，可直接用于看板", "Saved, ready for dashboards")
    : relationshipConfidence >= 0.85 && relationshipUnmatchedRows === 0
      ? biText("建议保存，匹配完整", "Recommended, complete match")
      : relationshipConfidence >= 0.65
        ? biText("可预演保存，先复核少量差异", "Preview save, review the small gap")
        : biText("先预览，不建议直接保存", "Preview first, not ready to save");

  function applyRelationshipRecommendation(recommendation: RelationshipRecommendation) {
    const mapping = recommendation.fieldMappings[0];
    setRelationshipForm({
      leftTable: recommendation.leftTableKey,
      rightTable: recommendation.rightTableKey,
      leftField: mapping?.leftField ?? relationshipForm.leftField,
      rightField: mapping?.rightField ?? relationshipForm.rightField,
      fieldMappings: recommendation.fieldMappings,
      filters: relationshipForm.filters,
      preaggregation: relationshipForm.preaggregation,
      joinType: recommendation.joinType || "left",
      limit: relationshipForm.limit ?? 10,
    });
  }

  return (
    <>
      <RelationshipAutoModelGraph
        busy={busy}
        fields={fields}
        onApplyRecommendation={applyRelationshipRecommendation}
        onRelationshipPreview={onRelationshipPreview}
        onRelationshipSave={onRelationshipSave}
        relationshipForm={relationshipForm}
        relationshipRecommendations={relationshipRecommendations}
        relationships={relationships}
        runBusy={runBusy}
        tables={tables}
      />

      <article className={showAdvanced ? "workbenchPanel widePanel advancedPanel" : "workbenchPanel widePanel advancedPanel collapsed"}>
        <div className="tileHeader">
          <h3><Bilingual zh="保存业务连接" en="Save business link" /></h3>
          <div className="buttonRow tight">
            <button className="miniButton" data-testid="relationship-preview-button" disabled={busy === "relationship-preview"} onClick={() => runBusy("relationship-preview", () => onRelationshipPreview(relationshipForm))} type="button">
              {biText("预览", "Preview")}
            </button>
            <button className="miniButton" data-testid="relationship-dry-run-button" disabled={busy === "relationship-dry"} onClick={() => runBusy("relationship-dry", () => onRelationshipSave({ ...relationshipForm, confirm: false }))} type="button">
              {biText("预演保存", "Preview save")}
            </button>
            <button className="primaryButton compactAction" data-testid="relationship-confirm-button" disabled={busy === "relationship-save"} onClick={() => runBusy("relationship-save", () => onRelationshipSave({ ...relationshipForm, confirm: true }))} type="button">
              {biText("确认保存", "Confirm save")}
            </button>
          </div>
        </div>
        <details className="advancedDetails compactAdvanced relationshipTechnicalDetails" data-testid="relationship-technical-details">
          <summary>{biText("选择连接字段", "Choose link fields")}</summary>
          <div className="formGrid">
            <label>
              <span>{biText("左表", "Left table")}</span>
              <select value={relationshipForm.leftTable} onChange={(event) => setRelationshipForm((current) => ({ ...current, leftTable: event.target.value }))}>
                {tables.map((table) => <option key={table.table_key} value={table.table_key}>{table.display_name}</option>)}
              </select>
            </label>
            <label>
              <span>{biText("左字段", "Left field")}</span>
              <select value={relationshipForm.leftField} onChange={(event) => setRelationshipForm((current) => ({ ...current, leftField: event.target.value, fieldMappings: undefined }))}>
                {leftFields.map((field) => <option key={field.field_name} value={field.field_name}>{field.field_name}</option>)}
              </select>
            </label>
            <label>
              <span>{biText("右表", "Right table")}</span>
              <select value={relationshipForm.rightTable} onChange={(event) => setRelationshipForm((current) => ({ ...current, rightTable: event.target.value }))}>
                {tables.map((table) => <option key={table.table_key} value={table.table_key}>{table.display_name}</option>)}
              </select>
            </label>
            <label>
              <span>{biText("右字段", "Right field")}</span>
              <select value={relationshipForm.rightField} onChange={(event) => setRelationshipForm((current) => ({ ...current, rightField: event.target.value, fieldMappings: undefined, preaggregation: current.preaggregation ? { ...current.preaggregation, groupFields: [event.target.value] } : undefined }))}>
                {rightFields.map((field) => <option key={field.field_name} value={field.field_name}>{field.field_name}</option>)}
              </select>
            </label>
          </div>
        </details>
        <Suspense fallback={null}>
          <RelationshipSafetyControls relationshipForm={relationshipForm} rightFields={rightFields} setRelationshipForm={setRelationshipForm} />
        </Suspense>
        <div className="policyStrip">
          <div><strong>{metricValue(relationshipPreview.relationshipPreview.metrics, "overlapKeys")}</strong><span>{biText("可连接键", "linkable keys")}</span></div>
          <div><strong>{metricValue(relationshipPreview.relationshipPreview.metrics, "matchedLeftRows")}</strong><span>{biText("已匹配行", "matched rows")}</span></div>
          <div><strong>{metricValue(relationshipPreview.relationshipPreview.metrics, "unmatchedLeftRows")}</strong><span>{biText("需复核行", "rows to review")}</span></div>
          <div><strong>{confidencePercent(Number(relationshipPreview.relationshipPreview.metrics.confidence ?? 0))}</strong><span>{biText("匹配度", "match quality")}</span></div>
        </div>
        <div className="relationshipImpactPanel" data-testid="relationship-impact-panel">
          <div className="relationshipImpactHeader">
            <strong>{relationshipDecisionState}</strong>
            <span>{biText("保存关系会让看板组件、Agent 证据和受控关联查询共用这一条业务连接。", "Saving a relationship lets dashboard widgets, Agent evidence, and controlled relationship queries reuse this business link.")}</span>
          </div>
          <div className="relationshipImpactFacts">
            <span>{biText("连接对象", "Link objects")}: {relationshipForm.leftTable} &rarr; {relationshipForm.rightTable}</span>
            <span>{biText("推荐来源", "Recommendation")}: {matchingRelationshipRecommendation ? `${matchingRelationshipRecommendation.leftTableName} -> ${matchingRelationshipRecommendation.rightTableName}` : biText("暂无", "None")}</span>
            <span>{biText("影响范围", "Impact")}: {relationships.length} {biText("条已保存关系", "saved relationships")} · {relationshipOverlapKeys} {biText("个可连接键", "linkable keys")}</span>
          </div>
          {matchingRelationshipRecommendation ? (
            <div className="relationshipRecommendationCard" data-testid="relationship-recommendation-apply-card">
              <div>
                <strong>{biText("推荐业务连接", "Recommended business link")}: {matchingRelationshipRecommendation.leftTableName} &rarr; {matchingRelationshipRecommendation.rightTableName}</strong>
                <span>{biText("匹配度", "match quality")} {confidencePercent(matchingRelationshipRecommendation.confidence)} · {biText("覆盖率", "coverage")} {confidencePercent(matchingRelationshipRecommendation.overlapRatio)} · {matchingRelationshipRecommendation.reasons.slice(0, 2).join(" / ")}</span>
              </div>
              <button className="miniButton" data-testid="relationship-apply-recommendation" type="button" onClick={() => applyRelationshipRecommendation(matchingRelationshipRecommendation)}>
                {biText("套用推荐", "Use recommendation")}
              </button>
            </div>
          ) : (
            <p className="quietText">{biText("还没有可套用的关系推荐。先生成证据摘要或让 Agent 帮你找关系。", "No reusable relationship recommendation yet. Create an evidence summary or ask the Agent to find relationships.")}</p>
          )}
          {matchingRelationshipRecommendation ? (
            <details className="relationshipDiagnosticsTechnical" data-testid="relationship-diagnostics-technical">
              <summary>{biText("查看连接字段和诊断", "View link fields and diagnostics")}</summary>
              <span>{matchingRecommendationMapping?.leftField ?? relationshipForm.leftField} &rarr; {matchingRecommendationMapping?.rightField ?? relationshipForm.rightField}</span>
              <span>{biText("需复核行", "Rows to review")}: {relationshipUnmatchedRows}</span>
            </details>
          ) : null}
        </div>
        {relationshipPreview.relationshipPreview.warnings.length ? (
          <details className="advancedDetails compactAdvanced relationshipWarningDetails" data-testid="relationship-warning-details">
            <summary>{biText("查看关系预览提示", "View relationship preview notes")}</summary>
            <ul className="noteList inlineNotes">
              {relationshipPreview.relationshipPreview.warnings.map((warning) => <li key={warning}>{warning}</li>)}
            </ul>
          </details>
        ) : null}
      </article>

      <article className={showAdvanced ? "workbenchPanel advancedPanel" : "workbenchPanel advancedPanel collapsed"}>
        <div className="tileHeader">
          <h3><Bilingual zh="已保存关系" en="Saved relationships" /></h3>
          <span>{relationships.length}</span>
        </div>
        <ul className="metricList">
          {relationships.map((relationship) => (
            <li key={relationship.relation_key}>
              <strong>{relationship.left_table_key} → {relationship.right_table_key}</strong>
              <span>{relationshipRecordMappingLabel(relationship)} · {confidencePercent(relationship.confidence)}</span>
              <span>
                {biText("安全状态", "Safety")}: {relationshipSafetyFacts(relationship).status}
                {relationshipSafetyFacts(relationship).filterCount ? ` · ${biText("过滤", "filters")} ${relationshipSafetyFacts(relationship).filterCount}` : ""}
                {relationshipSafetyFacts(relationship).preaggregationMeasureCount ? ` · ${biText("预聚合", "pre-aggregations")} ${relationshipSafetyFacts(relationship).preaggregationMeasureCount}` : ""}
              </span>
            </li>
          ))}
        </ul>
      </article>
    </>
  );
}
