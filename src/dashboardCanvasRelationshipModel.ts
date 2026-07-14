import type { RelationshipRecommendation, RelationshipRecord } from "./types";

export type RelationshipSavePayload = {
  leftTable: string;
  rightTable: string;
  leftField: string;
  rightField: string;
  fieldMappings?: Array<{ leftField: string; rightField: string }>;
  filters?: Array<{ phase?: "pre" | "post"; side?: string; field: string; operator: string; value?: string; enabled?: boolean }>;
  preaggregation?: { side: "right"; groupFields: string[]; measures: Array<{ field: string; aggregation: string }> };
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
  return recommendation.fieldMappings?.map((mapping) => `${mapping.leftField} = ${mapping.rightField}`).join(" + ") ?? "";
}

export function relationshipRecordMappingLabel(relationship: RelationshipRecord) {
  const mappings = relationship.fieldMappings?.length
    ? relationship.fieldMappings
    : [{ leftField: relationship.left_field, rightField: relationship.right_field }];
  return mappings.map((mapping) => `${mapping.leftField} = ${mapping.rightField}`).join(" + ");
}

export function relationshipSafetyFacts(relationship: RelationshipRecord) {
  const status = relationship.validation?.status || "unvalidated";
  const filters = relationship.filters?.filter((filter) => filter.enabled !== false) ?? [];
  const measures = relationship.preaggregation?.measures ?? [];
  return {
    status,
    filterCount: filters.length,
    preaggregationMeasureCount: measures.length,
    isQuerySafe: status === "validated",
  };
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
    fieldMappings: recommendation.fieldMappings,
    joinType: recommendation.joinType || "left",
    limit: 20,
    confirm,
  };
}
