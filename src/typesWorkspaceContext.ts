export type BusinessFieldProfileStatus = "ready" | "ambiguous" | "blocked" | "stale";

export interface WorkspacePlanningBinding {
  schema: "aibi-workspace-planning-binding/v1";
  workspaceId: string;
  componentFingerprints: Record<string, string>;
  profileCount: number;
  candidateCanAuthorizeJoin: false;
  fingerprint: string;
}

export interface BusinessFieldProfile {
  schema: "aibi-business-field-profile/v1";
  profileAlgorithmVersion: string;
  fieldRef: { workspaceId: string; tableKey: string; fieldName: string };
  tableLabel: string;
  dataVersion: number;
  observedShape: {
    storageType: string;
    logicalType: string;
    rowCount: number;
    nonNullCount: number;
    nullCount: number;
    nullRate: number;
    uniqueCount: number;
    uniqueRatio: number;
    boundedSampleSize: number;
    typeEvidence: Record<string, number>;
    timeCoverage: { minimum: string; maximum: string; basis: string } | null;
  };
  semantic: {
    savedRole: string;
    savedUsage: string;
    confidence: number;
    authority: "manual-confirmed" | "saved-auto-candidate" | "import-candidate-only" | string;
    confirmedSemanticRef: string | null;
    roleCandidates: Array<{ role: string; usage: string; confidence: number; source: string; confirmed: false }>;
    statusCandidates: {
      observedDistinctCount: number;
      rawValuesWithheld: true;
      authority: "statistics-only-no-raw-values" | string;
    };
    tags: string[];
    notePresent: boolean;
    noteFingerprint: string | null;
  };
  sensitivity: {
    level: "none" | "possible" | "likely" | string;
    reasonCodes: string[];
    rawValuesExposed: false;
    outboundPolicy: string;
  };
  bindings: {
    metricKeys: string[];
    calculatedFieldKeys: string[];
    relationshipEdges: Array<{
      relationshipKey: string;
      validationStatus: string;
      otherTableKey: string;
      otherField: string;
    }>;
    grainCandidate: boolean;
  };
  freshness: {
    status: "current" | "stale" | "unknown" | string;
    sourceRunId: string | null;
    sourceRunCreatedAt: string | null;
    tableUpdatedAt: string;
    usableForPlanning: boolean;
    planningAuthority: string;
  };
  status: BusinessFieldProfileStatus;
  blockers: string[];
  warnings: string[];
  evidenceRefs: string[];
  fingerprint: string;
}

export interface BusinessFieldProfileCollection {
  ok: boolean;
  schema: "aibi-business-field-profile-collection/v1";
  workspaceId: string;
  requestScope: { tableKey: string | null; fieldName: string | null };
  profiles: BusinessFieldProfile[];
  count: number;
  fingerprint: string;
  rawSampleValuesExposed: false;
}

export interface RuntimeCatalogSummary {
  schema: "aibi-runtime-catalog/v1";
  workspaceId: string;
  tables: Array<{ tableKey: string; displayName: string; rowCount: number; columnCount: number; dataVersion: number }>;
  fields: Array<{ fieldRef: BusinessFieldProfile["fieldRef"]; profileStatus: BusinessFieldProfileStatus; sensitivity: string; usableForPlanning: boolean }>;
  metrics: Array<{ metricKey: string; label: string; tableKey: string; enabled: boolean }>;
  calculatedFields: Array<{ fieldKey: string; tableKey: string; name: string; enabled: boolean }>;
  relationships: Array<{ relationshipKey: string; validationStatus: string }>;
  domainPacks: { available: Array<{ packId: string }>; enabled: Array<{ packId: string }>; fingerprint: string };
  analyticalSkills: { available: Array<{ skillId: string }>; enabled: Array<{ skillId: string }>; fingerprint: string };
  agentRuntime: { selectedProfileId: string; businessSemanticAuthority: string; providerCanWrite: false };
  queryRuntime: { engine: string; available: boolean; fallbackEngine: string | null };
  capabilities: Array<{ capabilityId: string; command: string; domain: string; mutationMode: string }>;
  guardrails: {
    candidateCanAuthorizeJoin: false;
    providerCanWrite: false;
    arbitrarySql: string;
    arbitraryCode: string;
    otherAibiRepositories: string;
    credentialsInPayload: false;
  };
  fingerprint: string;
}

export interface WorkspaceManifestSummary {
  schema: "aibi-workspace-manifest/v1";
  workspaceId: string;
  sourceSnapshot: {
    tableCount: number;
    rowCount: number;
    fieldCount: number;
    dataFingerprint: string;
    schemaFingerprint: string;
  };
  semanticSnapshot: {
    profileStatusCounts: Record<BusinessFieldProfileStatus, number>;
    confirmedBusinessMeanings: number;
    metricCount: number;
    calculatedFieldCount: number;
    relationshipCount: number;
    validatedRelationshipCount: number;
    contextCounts: { terms: number; confirmedTerms: number; rules: number; confirmedRules: number };
  };
  runtimeSnapshot: {
    runtimeCatalogRef: { schema: string; fingerprint: string };
    planningBindingRef: { schema: string; fingerprint: string };
    selectedAgentProfileId: string;
    enabledDomainPackCount: number;
    enabledAnalyticalSkillCount: number;
    registeredCapabilityCount: number;
    providerCanWrite: false;
  };
  evidenceSnapshot: { status: string; usableForPlanning: boolean };
  planningBinding: WorkspacePlanningBinding;
  componentFingerprints: Record<string, string>;
  status: "current" | "stale" | "incomplete";
  usableForPlanning: boolean;
  blockers: string[];
  warnings: string[];
  fingerprint: string;
}
