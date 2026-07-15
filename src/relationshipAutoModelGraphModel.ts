import type { RelationshipSaveOptions } from "./dashboardCanvasContracts";
import {
  buildRelationshipSavePayload,
  relationshipPrimaryMapping,
  relationshipRecordKey,
  relationshipRecommendationKey,
  relationshipSavePayloadKey,
} from "./dashboardCanvasRelationshipModel";
import type { FieldConfig, RelationshipRecommendation, RelationshipRecord, WorkbenchTable } from "./types";
import { biText } from "./components/Bilingual";

export type RelationshipGraphEdge = {
  confidence: number;
  coverage: number;
  existing: boolean;
  key: string;
  leftField: string;
  leftTableKey: string;
  leftTableName: string;
  reason: string;
  recommendation?: RelationshipRecommendation;
  rightField: string;
  rightTableKey: string;
  rightTableName: string;
  source: "recommended" | "saved";
};

const maxVisibleEdges = 5;
const maxNodeFields = 3;

function tableDisplayName(tables: WorkbenchTable[], tableKey: string, fallback?: string) {
  return tables.find((table) => table.table_key === tableKey)?.display_name ?? fallback ?? tableKey;
}

export function relationshipSaveOptions(recommendation: RelationshipRecommendation, current: RelationshipSaveOptions): RelationshipSaveOptions | null {
  const payload = buildRelationshipSavePayload(recommendation, false);
  if (!payload) return null;
  const preservePolicies = relationshipSavePayloadKey(current) === relationshipSavePayloadKey(payload);
  return {
    leftTable: payload.leftTable,
    rightTable: payload.rightTable,
    leftField: payload.leftField,
    rightField: payload.rightField,
    fieldMappings: payload.fieldMappings,
    filters: preservePolicies ? current.filters : undefined,
    preaggregation: preservePolicies ? current.preaggregation : undefined,
    joinType: payload.joinType ?? "left",
    limit: current.limit ?? payload.limit ?? 20,
  };
}

function recommendationToEdge(recommendation: RelationshipRecommendation, index: number): RelationshipGraphEdge | null {
  const mapping = relationshipPrimaryMapping(recommendation);
  if (!mapping) return null;
  return {
    confidence: recommendation.confidence ?? recommendation.score ?? 0,
    coverage: recommendation.overlapRatio ?? 0,
    existing: Boolean(recommendation.existing),
    key: relationshipRecommendationKey(recommendation) || `recommendation-${index}`,
    leftField: mapping.leftField,
    leftTableKey: recommendation.leftTableKey,
    leftTableName: recommendation.leftTableName || recommendation.leftTableKey,
    reason: recommendation.reasons?.slice(0, 2).join(" / ") || biText("字段语义和样本重叠匹配", "Field semantics and sample overlap matched"),
    recommendation,
    rightField: mapping.rightField,
    rightTableKey: recommendation.rightTableKey,
    rightTableName: recommendation.rightTableName || recommendation.rightTableKey,
    source: "recommended",
  };
}

function savedRelationshipToEdge(relationship: RelationshipRecord, tables: WorkbenchTable[]): RelationshipGraphEdge {
  return {
    confidence: relationship.confidence ?? 0,
    coverage: relationship.confidence ?? 0,
    existing: true,
    key: relationshipRecordKey(relationship),
    leftField: relationship.left_field,
    leftTableKey: relationship.left_table_key,
    leftTableName: tableDisplayName(tables, relationship.left_table_key),
    reason: biText("已保存，Agent 和看板可直接复用", "Saved, reusable by Agent and dashboards"),
    rightField: relationship.right_field,
    rightTableKey: relationship.right_table_key,
    rightTableName: tableDisplayName(tables, relationship.right_table_key),
    source: "saved",
  };
}

export function topRelationshipNodeFields(fields: FieldConfig[], tableKey: string, activeField: string) {
  const fieldNames = fields
    .filter((field) => field.table_key === tableKey)
    .map((field) => field.field_name);
  return Array.from(new Set([activeField, ...fieldNames])).filter(Boolean).slice(0, maxNodeFields);
}

export function buildRelationshipAutoModelGraphViewModel({
  relationshipForm,
  relationshipRecommendations,
  relationships,
  tables,
}: {
  relationshipForm: RelationshipSaveOptions;
  relationshipRecommendations: RelationshipRecommendation[];
  relationships: RelationshipRecord[];
  tables: WorkbenchTable[];
}) {
  const sortedRecommendations = [...relationshipRecommendations].sort((left, right) =>
    (right.confidence ?? right.score ?? 0) - (left.confidence ?? left.score ?? 0),
  );
  const recommendationEdges = sortedRecommendations
    .map(recommendationToEdge)
    .filter((edge): edge is RelationshipGraphEdge => Boolean(edge));
  const recommendationKeys = new Set(recommendationEdges.map((edge) => edge.key));
  const savedEdges = relationships
    .map((relationship) => savedRelationshipToEdge(relationship, tables))
    .filter((edge) => !recommendationKeys.has(edge.key));
  const graphEdges = [...recommendationEdges, ...savedEdges].slice(0, maxVisibleEdges);
  const bestRecommendation = sortedRecommendations.find((recommendation) => !recommendation.existing && relationshipPrimaryMapping(recommendation)) ??
    sortedRecommendations.find((recommendation) => relationshipPrimaryMapping(recommendation));
  const bestOptions = bestRecommendation ? relationshipSaveOptions(bestRecommendation, relationshipForm) : null;
  return {
    bestOptions,
    bestRecommendation,
    candidateCount: relationshipRecommendations.length,
    graphEdges,
    savedCount: relationships.length,
  };
}
