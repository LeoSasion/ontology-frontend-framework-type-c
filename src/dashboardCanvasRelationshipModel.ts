import type { RelationshipRecommendation } from "./types";

export type RelationshipSavePayload = {
  leftTable: string;
  rightTable: string;
  leftField: string;
  rightField: string;
  joinType?: string;
  limit?: number;
  confirm?: boolean;
};

export function relationshipPrimaryMapping(recommendation: RelationshipRecommendation) {
  return recommendation.fieldMappings?.[0] ?? null;
}

export function relationshipRecommendationKey(recommendation: RelationshipRecommendation) {
  const mapping = relationshipPrimaryMapping(recommendation);
  return `${recommendation.leftTableKey}-${recommendation.rightTableKey}-${mapping?.leftField}-${mapping?.rightField}`;
}

export function relationshipMappingLabel(recommendation: RelationshipRecommendation) {
  const mapping = relationshipPrimaryMapping(recommendation);
  return mapping ? `${mapping.leftField} = ${mapping.rightField}` : "";
}

export function buildRelationshipSavePayload(
  recommendation: RelationshipRecommendation,
  confirm: boolean,
): RelationshipSavePayload | null {
  const mapping = relationshipPrimaryMapping(recommendation);
  if (!mapping) return null;
  return {
    leftTable: recommendation.leftTableKey,
    rightTable: recommendation.rightTableKey,
    leftField: mapping.leftField,
    rightField: mapping.rightField,
    joinType: recommendation.joinType || "left",
    limit: 20,
    confirm,
  };
}
