import type { RelationshipRecommendation } from "../types";
import {
  relationshipMappingLabel,
  relationshipPrimaryMapping,
  relationshipRecommendationKey,
} from "../dashboardCanvasRelationshipModel";
import { Bilingual, biText } from "./Bilingual";

type DashboardRelationshipRecommendationPanelProps = {
  busy: string | null;
  onRelationshipSave: (label: string, recommendation: RelationshipRecommendation, confirm: boolean) => void;
  recommendations: RelationshipRecommendation[];
};

export function DashboardRelationshipRecommendationPanel({
  busy,
  onRelationshipSave,
  recommendations,
}: DashboardRelationshipRecommendationPanelProps) {
  return (
    <article className="widgetActionPanel" data-testid="relationship-recommendation-panel">
      <div className="tileHeader compact">
        <h3><Bilingual zh="推荐关系" en="Recommended links" /></h3>
        <span>{biText(`${recommendations.length} 条候选`, `${recommendations.length} candidates`)}</span>
      </div>
      {recommendations.length ? (
        <div className="recommendationStack">
          {recommendations.slice(0, 3).map((recommendation, index) => {
            const mapping = relationshipPrimaryMapping(recommendation);
            return (
              <div className="relationshipWidgetHint recommendationItem" key={relationshipRecommendationKey(recommendation)}>
                <strong>{recommendation.leftTableName || recommendation.leftTableKey} → {recommendation.rightTableName || recommendation.rightTableKey}</strong>
                <span>{mapping ? relationshipMappingLabel(recommendation) : biText("缺少字段映射", "Missing field mapping")}</span>
                <small>{Math.round((recommendation.confidence ?? 0) * 100)}% · {recommendation.reasons?.slice(0, 2).join(" / ")}</small>
                <div className="inlineActionRow">
                  <button
                    className="miniButton"
                    disabled={!mapping || busy === `relationship-preview-${index}`}
                    onClick={() => onRelationshipSave(`relationship-preview-${index}`, recommendation, false)}
                    type="button"
                  >
                    {biText("预演", "Preview")}
                  </button>
                  <button
                    className="miniButton"
                    disabled={!mapping || recommendation.existing || busy === `relationship-save-${index}`}
                    onClick={() => onRelationshipSave(`relationship-save-${index}`, recommendation, true)}
                    type="button"
                  >
                    {recommendation.existing ? biText("已保存", "Saved") : biText("保存", "Save")}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="emptyFilterHint"><Bilingual zh="暂无可推荐关系。导入更多表或先运行字段语义推断后再试。" en="No recommended links yet. Import more tables or infer field semantics first." /></p>
      )}
    </article>
  );
}
