import type { RelationshipSaveOptions } from "../dashboardCanvasContracts";
import { relationshipMappingLabel } from "../dashboardCanvasRelationshipModel";
import {
  buildRelationshipAutoModelGraphViewModel,
  relationshipSaveOptions,
  topRelationshipNodeFields,
} from "../relationshipAutoModelGraphModel";
import { confidencePercent } from "../sourceWorkbenchModel";
import type { FieldConfig, RelationshipRecommendation, RelationshipRecord, WorkbenchTable } from "../types";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";

type RelationshipAutoModelGraphProps = {
  busy: string | null;
  fields: FieldConfig[];
  onApplyRecommendation: (recommendation: RelationshipRecommendation) => void;
  onRelationshipPreview: (options: RelationshipSaveOptions) => Promise<void>;
  onRelationshipSave: (options: RelationshipSaveOptions) => Promise<void>;
  relationships: RelationshipRecord[];
  relationshipForm: RelationshipSaveOptions;
  relationshipRecommendations: RelationshipRecommendation[];
  runBusy: (label: string, action: () => Promise<void>) => Promise<void>;
  tables: WorkbenchTable[];
};

export function RelationshipAutoModelGraph({
  busy,
  fields,
  onApplyRecommendation,
  onRelationshipPreview,
  onRelationshipSave,
  relationships,
  relationshipForm,
  relationshipRecommendations,
  runBusy,
  tables,
}: RelationshipAutoModelGraphProps) {
  const {
    bestOptions,
    bestRecommendation,
    candidateCount,
    graphEdges,
    savedCount,
  } = buildRelationshipAutoModelGraphViewModel({
    relationshipForm,
    relationshipRecommendations,
    relationships,
    tables,
  });

  function runRecommendationPreview(recommendation: RelationshipRecommendation, label: string) {
    const options = relationshipSaveOptions(recommendation, relationshipForm);
    if (!options) return;
    onApplyRecommendation(recommendation);
    void runBusy(label, () => onRelationshipPreview(options));
  }

  function runRecommendationSave(recommendation: RelationshipRecommendation, label: string, confirm: boolean) {
    const options = relationshipSaveOptions(recommendation, relationshipForm);
    if (!options) return;
    onApplyRecommendation(recommendation);
    void runBusy(label, () => onRelationshipSave({ ...options, confirm }));
  }

  return (
    <article className="workbenchPanel widePanel relationshipAutoGraph" data-testid="relationship-auto-graph">
      <div className="relationshipGraphHeader">
        <div>
          <span className="statusPill">{biText("AI 自动连线", "AI auto-linking")}</span>
          <h3><Bilingual zh="可视化关系建模" en="Visual relationship modeling" /></h3>
          <p>
            {biText(
              "优先用字段语义、样本重叠和已保存关系自动连线；用户只需要预演或确认，手动选字段放在高级编辑里。",
              "Uses field semantics, sample overlap, and saved links first; users preview or confirm while manual fields stay in advanced editing.",
            )}
          </p>
        </div>
        <div className="relationshipGraphStats" aria-label={biText("关系建模摘要", "Relationship modeling summary")}>
          <div><strong>{candidateCount}</strong><span>{biText("候选", "candidates")}</span></div>
          <div><strong>{savedCount}</strong><span>{biText("已保存", "saved")}</span></div>
          <div><strong>{bestRecommendation ? confidencePercent(bestRecommendation.confidence ?? 0) : "0%"}</strong><span>{biText("最佳匹配", "best match")}</span></div>
        </div>
      </div>

      <div className="relationshipGraphPrimaryActions">
        <button
          className="miniButton"
          data-testid="relationship-graph-best-apply"
          disabled={!bestRecommendation}
          onClick={() => bestRecommendation && onApplyRecommendation(bestRecommendation)}
          type="button"
        >
          <Icon name="agent" /> {biText("套用最佳连线", "Use best link")}
        </button>
        <button
          className="miniButton"
          data-testid="relationship-graph-best-preview"
          disabled={!bestRecommendation || !bestOptions || busy === "relationship-auto-preview"}
          onClick={() => bestRecommendation && runRecommendationPreview(bestRecommendation, "relationship-auto-preview")}
          type="button"
        >
          <Icon name="query" /> {biText("预演最佳连线", "Preview best link")}
        </button>
        <button
          className="primaryButton compactAction"
          data-testid="relationship-graph-best-confirm"
          disabled={!bestRecommendation || !bestOptions || bestRecommendation.existing || busy === "relationship-auto-save"}
          onClick={() => bestRecommendation && runRecommendationSave(bestRecommendation, "relationship-auto-save", true)}
          type="button"
        >
          <Icon name="check" /> {bestRecommendation?.existing ? biText("已保存", "Saved") : biText("确认保存", "Confirm save")}
        </button>
      </div>

      {graphEdges.length ? (
        <div className="relationshipGraphCanvas" data-testid="relationship-graph-canvas">
          {graphEdges.map((edge, index) => {
            const leftFields = topRelationshipNodeFields(fields, edge.leftTableKey, edge.leftField);
            const rightFields = topRelationshipNodeFields(fields, edge.rightTableKey, edge.rightField);
            const disabled = !edge.recommendation;
            return (
              <button
                className={`relationshipGraphEdgeRow ${edge.existing ? "saved" : "recommended"}`}
                data-testid="relationship-graph-edge"
                disabled={disabled}
                key={edge.key}
                onClick={() => edge.recommendation && onApplyRecommendation(edge.recommendation)}
                type="button"
              >
                <span className="relationshipGraphNode">
                  <strong>{edge.leftTableName}</strong>
                  <small>{edge.leftTableKey}</small>
                  <span className="relationshipGraphFieldList">
                    {leftFields.map((field) => (
                      <em className={field === edge.leftField ? "active" : ""} key={field}>{field}</em>
                    ))}
                  </span>
                </span>
                <span className="relationshipGraphConnector" aria-hidden="true">
                  <svg viewBox="0 0 160 34" preserveAspectRatio="none">
                    <path d="M6 17 C48 3 112 31 154 17" />
                    <circle cx="6" cy="17" r="3" />
                    <circle cx="154" cy="17" r="3" />
                  </svg>
                  <span>{edge.leftField} = {edge.rightField}</span>
                </span>
                <span className="relationshipGraphNode">
                  <strong>{edge.rightTableName}</strong>
                  <small>{edge.rightTableKey}</small>
                  <span className="relationshipGraphFieldList">
                    {rightFields.map((field) => (
                      <em className={field === edge.rightField ? "active" : ""} key={field}>{field}</em>
                    ))}
                  </span>
                </span>
                <span className="relationshipGraphScore">
                  <strong>{confidencePercent(edge.confidence)}</strong>
                  <span>{edge.existing ? biText("已保存", "Saved") : biText("AI 推荐", "AI suggested")}</span>
                  <small>{edge.reason}</small>
                </span>
                <span className="relationshipGraphIndex">{index + 1}</span>
              </button>
            );
          })}
        </div>
      ) : (
        <div className="relationshipGraphEmpty" data-testid="relationship-graph-empty">
          <strong>{biText("还没有可连线的表", "No linkable tables yet")}</strong>
          <span>{biText("先导入两张以上表，或运行 Source Intelligence 让系统识别可连接字段。", "Import at least two tables or run Source Intelligence so the system can detect linkable fields.")}</span>
        </div>
      )}

      <div className="relationshipGraphFooter">
        <span>{biText("点击任意 AI 推荐边会自动填入高级字段；保存前仍会走 dry-run/确认保护。", "Click any AI edge to fill advanced fields; saving still uses dry-run and confirmation protection.")}</span>
        {bestRecommendation ? (
          <span>{relationshipMappingLabel(bestRecommendation)}</span>
        ) : null}
      </div>
    </article>
  );
}
