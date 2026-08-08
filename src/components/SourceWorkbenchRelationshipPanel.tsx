import { lazy, Suspense, useMemo, type Dispatch, type SetStateAction } from "react";
import type { FieldConfig, RelationshipPreviewPayload, RelationshipRecommendation, RelationshipRecord, WorkbenchTable } from "../types";
import type { RelationshipSaveOptions } from "../dashboardCanvasContracts";
import {
  relationshipMappingLabel,
  relationshipRecordKey,
  relationshipRecordMappingLabel,
  relationshipRecommendationKey,
  relationshipSafetyFacts,
  relationshipSavePayloadKey,
  withRelationshipIdentity,
} from "../dashboardCanvasRelationshipModel";
import { relationshipSaveOptions } from "../relationshipAutoModelGraphModel";
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
  const relationshipFormKey = relationshipSavePayloadKey(relationshipForm);
  const matchingRelationshipRecommendation = relationshipRecommendations.find((recommendation) =>
    relationshipRecommendationKey(recommendation) === relationshipFormKey,
  );
  const suggestedRelationshipRecommendation = matchingRelationshipRecommendation ?? relationshipRecommendations.find((recommendation) =>
    recommendation.leftTableKey === relationshipForm.leftTable &&
    recommendation.rightTableKey === relationshipForm.rightTable,
  ) ?? relationshipRecommendations[0];
  const relationshipPreviewMetrics = relationshipPreview.relationshipPreview.metrics;
  const relationshipConfidence = Number(relationshipPreviewMetrics.confidence ?? matchingRelationshipRecommendation?.confidence ?? 0);
  const relationshipUnmatchedRows = numberValue(relationshipPreviewMetrics.unmatchedLeftRows ?? matchingRelationshipRecommendation?.previewMetrics?.unmatchedLeftRows);
  const relationshipOverlapKeys = numberValue(relationshipPreviewMetrics.overlapKeys ?? matchingRelationshipRecommendation?.previewMetrics?.overlapKeys);
  const relationshipAlreadySaved = relationships.some((relationship) => relationshipRecordKey(relationship) === relationshipFormKey);
  const relationshipBusy = Boolean(busy?.startsWith("relationship"));
  const relationshipIdentityComplete = Boolean(
    tables.length >= 2
    && relationshipForm.leftTable
    && relationshipForm.rightTable
    && relationshipForm.leftTable !== relationshipForm.rightTable
    && relationshipForm.leftField
    && relationshipForm.rightField,
  );
  const relationshipControlsDisabled = relationshipBusy || !relationshipIdentityComplete;
  const relationshipBusyText = relationshipBusy
    ? busy?.includes("dry")
      ? biText("正在预演保存业务连接", "Previewing the relationship save")
      : busy?.includes("save")
        ? biText("正在保存业务连接", "Saving the business relationship")
        : biText("正在预览业务连接", "Previewing the business relationship")
    : "";
  const relationshipDecisionState = relationshipAlreadySaved
    ? biText("已保存，可直接用于看板", "Saved, ready for dashboards")
    : relationshipConfidence >= 0.85 && relationshipUnmatchedRows === 0
      ? biText("建议保存，匹配完整", "Recommended, complete match")
      : relationshipConfidence >= 0.65
        ? biText("可预演保存，先复核少量差异", "Preview save, review the small gap")
        : biText("先预览，不建议直接保存", "Preview first, not ready to save");

  function applyRelationshipRecommendation(recommendation: RelationshipRecommendation) {
    setRelationshipForm((current) => relationshipSaveOptions(recommendation, current) ?? current);
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

      <article aria-busy={relationshipBusy} className={showAdvanced ? "workbenchPanel widePanel advancedPanel" : "workbenchPanel widePanel advancedPanel collapsed"}>
        <div className="tileHeader">
          <h3><Bilingual zh="保存业务连接" en="Save business link" /></h3>
          <div className="buttonRow tight">
            <button className="miniButton" data-testid="relationship-preview-button" disabled={relationshipControlsDisabled} onClick={() => runBusy("relationship-preview", () => onRelationshipPreview(relationshipForm))} type="button">
              {biText("预览", "Preview")}
            </button>
            <button className="miniButton" data-testid="relationship-dry-run-button" disabled={relationshipControlsDisabled} onClick={() => runBusy("relationship-dry", () => onRelationshipSave({ ...relationshipForm, confirm: false }))} type="button">
              {biText("预演保存", "Preview save")}
            </button>
            <button className="primaryButton compactAction" data-testid="relationship-confirm-button" disabled={relationshipControlsDisabled} onClick={() => runBusy("relationship-save", () => onRelationshipSave({ ...relationshipForm, confirm: true }))} type="button">
              {biText("确认保存", "Confirm save")}
            </button>
          </div>
        </div>
        {relationshipBusyText ? <span aria-live="polite" className="quietText" role="status">{relationshipBusyText}</span> : null}
        {!relationshipIdentityComplete ? (
          <p className="emptyFilterHint" data-testid="relationship-modeling-unavailable" role="status">
            {tables.length < 2
              ? biText("至少接入两张数据表后，才能建立业务连接和配置连接安全策略。", "Connect at least two data tables before creating a business link or configuring its safety policy.")
              : biText("请先为左右数据表选择有效的连接字段。", "Choose valid link fields for both data tables first.")}
          </p>
        ) : null}
        <details className="advancedDetails compactAdvanced relationshipTechnicalDetails" data-testid="relationship-technical-details">
          <summary>{biText("选择连接字段", "Choose link fields")}</summary>
          <div className="formGrid">
            <label>
              <span>{biText("左表", "Left table")}</span>
              <select disabled={relationshipBusy} value={relationshipForm.leftTable} onChange={(event) => setRelationshipForm((current) => withRelationshipIdentity(current, { leftTable: event.target.value }))}>
                {tables.map((table) => <option key={table.table_key} value={table.table_key}>{table.display_name}</option>)}
              </select>
            </label>
            <label>
              <span>{biText("左字段", "Left field")}</span>
              <select disabled={relationshipBusy} value={relationshipForm.leftField} onChange={(event) => setRelationshipForm((current) => withRelationshipIdentity(current, { leftField: event.target.value }))}>
                {leftFields.map((field) => <option key={field.field_name} value={field.field_name}>{field.field_name}</option>)}
              </select>
            </label>
            <label>
              <span>{biText("右表", "Right table")}</span>
              <select disabled={relationshipBusy} value={relationshipForm.rightTable} onChange={(event) => setRelationshipForm((current) => withRelationshipIdentity(current, { rightTable: event.target.value }))}>
                {tables.map((table) => <option key={table.table_key} value={table.table_key}>{table.display_name}</option>)}
              </select>
            </label>
            <label>
              <span>{biText("右字段", "Right field")}</span>
              <select disabled={relationshipBusy} value={relationshipForm.rightField} onChange={(event) => setRelationshipForm((current) => withRelationshipIdentity(current, { rightField: event.target.value }))}>
                {rightFields.map((field) => <option key={field.field_name} value={field.field_name}>{field.field_name}</option>)}
              </select>
            </label>
          </div>
        </details>
        <Suspense fallback={null}>
          <RelationshipSafetyControls disabled={relationshipControlsDisabled} relationshipForm={relationshipForm} rightFields={rightFields} setRelationshipForm={setRelationshipForm} />
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
            <span>{biText("推荐来源", "Recommendation")}: {suggestedRelationshipRecommendation ? `${suggestedRelationshipRecommendation.leftTableName} -> ${suggestedRelationshipRecommendation.rightTableName}` : biText("暂无", "None")}</span>
            <span>{biText("影响范围", "Impact")}: {relationships.length} {biText("条已保存关系", "saved relationships")} · {relationshipOverlapKeys} {biText("个可连接键", "linkable keys")}</span>
          </div>
          {suggestedRelationshipRecommendation ? (
            <div className="relationshipRecommendationCard" data-testid="relationship-recommendation-apply-card">
              <div>
                <strong>{biText("推荐业务连接", "Recommended business link")}: {suggestedRelationshipRecommendation.leftTableName} &rarr; {suggestedRelationshipRecommendation.rightTableName}</strong>
                <span>{biText("匹配度", "match quality")} {confidencePercent(suggestedRelationshipRecommendation.confidence)} · {biText("覆盖率", "coverage")} {confidencePercent(suggestedRelationshipRecommendation.overlapRatio)} · {suggestedRelationshipRecommendation.reasons.slice(0, 2).join(" / ")}</span>
              </div>
              <button className="miniButton" data-testid="relationship-apply-recommendation" disabled={relationshipBusy} type="button" onClick={() => applyRelationshipRecommendation(suggestedRelationshipRecommendation)}>
                {biText("套用推荐", "Use recommendation")}
              </button>
            </div>
          ) : (
            <p className="quietText">{biText("还没有可套用的关系推荐。先生成证据摘要或让 Agent 帮你找关系。", "No reusable relationship recommendation yet. Create an evidence summary or ask the Agent to find relationships.")}</p>
          )}
          {suggestedRelationshipRecommendation ? (
            <details className="relationshipDiagnosticsTechnical" data-testid="relationship-diagnostics-technical">
              <summary>{biText("查看连接字段和诊断", "View link fields and diagnostics")}</summary>
              <span>{relationshipMappingLabel(suggestedRelationshipRecommendation)}</span>
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
