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

export type RelationshipFieldMapping = { leftField: string; rightField: string };

function normalizedRelationshipMappings(
  fieldMappings: RelationshipFieldMapping[] | undefined,
  leftField = "",
  rightField = "",
) {
  const explicitMappings = (fieldMappings ?? [])
    .map((mapping) => ({
      leftField: mapping.leftField.trim(),
      rightField: mapping.rightField.trim(),
    }))
    .filter((mapping) => mapping.leftField && mapping.rightField);
  const fallbackMapping = leftField.trim() && rightField.trim()
    ? [{ leftField: leftField.trim(), rightField: rightField.trim() }]
    : [];
  const mappings = explicitMappings.length ? explicitMappings : fallbackMapping;
  return Array.from(
    new Map(mappings.map((mapping) => [`${mapping.leftField}\u0000${mapping.rightField}`, mapping])).values(),
  ).sort((left, right) =>
    left.leftField.localeCompare(right.leftField) || left.rightField.localeCompare(right.rightField),
  );
}

export function canonicalRelationshipIdentity({
  leftTable,
  rightTable,
  fieldMappings,
  leftField = "",
  rightField = "",
}: {
  leftTable: string;
  rightTable: string;
  fieldMappings?: RelationshipFieldMapping[];
  leftField?: string;
  rightField?: string;
}) {
  return JSON.stringify([
    leftTable.trim(),
    rightTable.trim(),
    normalizedRelationshipMappings(fieldMappings, leftField, rightField)
      .map((mapping) => [mapping.leftField, mapping.rightField]),
  ]);
}

export function relationshipPrimaryMapping(recommendation: RelationshipRecommendation) {
  return recommendation.fieldMappings?.[0] ?? null;
}

export function relationshipRecommendationKey(recommendation: RelationshipRecommendation) {
  return canonicalRelationshipIdentity({
    leftTable: recommendation.leftTableKey,
    rightTable: recommendation.rightTableKey,
    fieldMappings: recommendation.fieldMappings,
  });
}

export function relationshipRecordKey(relationship: RelationshipRecord) {
  return canonicalRelationshipIdentity({
    leftTable: relationship.left_table_key,
    rightTable: relationship.right_table_key,
    fieldMappings: relationship.fieldMappings,
    leftField: relationship.left_field,
    rightField: relationship.right_field,
  });
}

export function relationshipSavePayloadKey(payload: RelationshipSavePayload) {
  return canonicalRelationshipIdentity({
    leftTable: payload.leftTable,
    rightTable: payload.rightTable,
    fieldMappings: payload.fieldMappings,
    leftField: payload.leftField,
    rightField: payload.rightField,
  });
}

export function relationshipRequestScopeKey(workspaceId: string, payload: RelationshipSavePayload) {
  return JSON.stringify([
    workspaceId,
    relationshipSavePayloadKey(payload),
    payload.joinType ?? "left",
    payload.limit ?? 20,
    payload.filters ?? [],
    payload.preaggregation ?? null,
  ]);
}

export function withRelationshipIdentity<T extends RelationshipSavePayload>(
  current: T,
  patch: Partial<Pick<T, "leftTable" | "rightTable" | "leftField" | "rightField" | "fieldMappings" | "joinType" | "limit" | "confirm">>,
): T {
  const endpointChanged = (["leftTable", "rightTable", "leftField", "rightField"] as const)
    .some((key) => Object.prototype.hasOwnProperty.call(patch, key) && patch[key] !== current[key]);
  const next = {
    ...current,
    ...patch,
    ...(endpointChanged && !Object.prototype.hasOwnProperty.call(patch, "fieldMappings")
      ? { fieldMappings: undefined }
      : {}),
  } as T;
  if (relationshipSavePayloadKey(current) === relationshipSavePayloadKey(next)) return next;
  return {
    ...next,
    filters: undefined,
    preaggregation: undefined,
  };
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
