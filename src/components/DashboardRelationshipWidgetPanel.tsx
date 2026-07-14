import type { RelationshipRecord } from "../types";
import { relationshipRecordMappingLabel, relationshipSafetyFacts } from "../dashboardCanvasRelationshipModel";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";

type DashboardRelationshipWidgetPanelProps = {
  busy: string | null;
  onAddRelationshipWidget: (relationship: RelationshipRecord) => void;
  onSelectedRelationshipChange: (relationshipKey: string) => void;
  relationships: RelationshipRecord[];
  selectedRelationship: RelationshipRecord | undefined;
  selectedRelationshipKey: string;
};

export function DashboardRelationshipWidgetPanel({
  busy,
  onAddRelationshipWidget,
  onSelectedRelationshipChange,
  relationships,
  selectedRelationship,
  selectedRelationshipKey,
}: DashboardRelationshipWidgetPanelProps) {
  return (
    <article className="widgetActionPanel" data-testid="relationship-widget-panel">
      <div className="tileHeader compact">
        <h3><Bilingual zh="关系组件" en="Relationship widget" /></h3>
        <span>{biText(`${relationships.length} 条关系`, `${relationships.length} links`)}</span>
      </div>
      <label className="fullWidthLabel">
        <span>{biText("已保存关系", "Saved relationship")}</span>
        <select value={selectedRelationshipKey} onChange={(event) => onSelectedRelationshipChange(event.target.value)}>
          {relationships.map((relationship) => (
            <option key={relationship.relation_key} value={relationship.relation_key}>
              {relationship.name} · {Math.round((relationship.confidence ?? 0) * 100)}%
            </option>
          ))}
        </select>
      </label>
      {selectedRelationship ? (
        <div className="relationshipWidgetHint">
          <strong>{selectedRelationship.left_table_key} → {selectedRelationship.right_table_key}</strong>
          <span>{relationshipRecordMappingLabel(selectedRelationship)}</span>
          <span>
            {biText("安全状态", "Safety")}: {relationshipSafetyFacts(selectedRelationship).status}
            {relationshipSafetyFacts(selectedRelationship).filterCount ? ` · ${biText("过滤", "filters")} ${relationshipSafetyFacts(selectedRelationship).filterCount}` : ""}
            {relationshipSafetyFacts(selectedRelationship).preaggregationMeasureCount ? ` · ${biText("预聚合", "pre-aggregations")} ${relationshipSafetyFacts(selectedRelationship).preaggregationMeasureCount}` : ""}
          </span>
        </div>
      ) : (
        <p className="emptyFilterHint"><Bilingual zh="先在数据源关系里保存一条关系，再放入看板。" en="Save a source relationship first, then place it on the dashboard." /></p>
      )}
      <button
        className="primaryButton fullWidthButton"
        data-testid="widget-add-relationship-button"
        disabled={!selectedRelationship || busy === "add-relationship-widget"}
        onClick={() => selectedRelationship && onAddRelationshipWidget(selectedRelationship)}
        type="button"
      >
        <Icon name="dashboard" />
        <Bilingual zh="生成关系图表" en="Create relation chart" />
      </button>
    </article>
  );
}
