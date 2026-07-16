export type FederationGate = {
  status: "passed" | "blocked" | string;
  evidence: string[];
  blockers: string[];
};

export type FederationProof = {
  ok: boolean;
  schema: "aibi-federation-proof/v1" | string;
  workspaceId: string;
  status: "provable" | "blocked" | string;
  provable: boolean;
  blocked: boolean;
  blockers: string[];
  gates: Record<string, FederationGate>;
  sources: Array<{
    connectorKey: string;
    targetTableKey: string;
    adapterId: string;
    available: boolean;
    sourceCurrent: boolean;
    networkRead: boolean;
    projections: string[];
    credentialValuesExposed: false;
    businessRowsExposed: false;
  }>;
  relationships: Array<{
    relationKey: string;
    leftTableKey: string;
    rightTableKey: string;
    current: boolean;
    validationStatus: string;
  }>;
  proofFingerprint: string;
  permissions: { execution: false; materialization: false; write: false };
  sideEffects: {
    crossSourceQuery: false;
    businessRowsExposed: false;
    businessDatabaseWrite: false;
    artifactWrite: false;
    rowCopy: false;
  };
};

export type FederationProofRequest = {
  connectors: string[];
  projections: Record<string, string[]>;
  relationships: string[];
  grain: string;
  entityKey: string;
  filters?: Array<{ connectorKey: string; field: string; operator: string }>;
  budget?: {
    maxSources?: number;
    maxProjectedFields?: number;
    maxRelationships?: number;
    maxFilters?: number;
  };
};
