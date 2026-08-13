import type { AnalysisJob, AnalysisJobStatus } from "./typesJobs";

export type SqlServerAdapterCapability =
  | "unavailable"
  | "ready_for_test"
  | "ready_for_snapshot"
  | "active";

export interface SqlServerPublicTarget {
  workspaceId: string;
  hostAlias: string;
  port: number;
  database: string;
  encryption: "required" | string;
  credentialConfigured: boolean;
}

export interface SqlServerAdapterContract {
  schema: "aibi-connector-adapter/v1";
  adapterId: "sqlserver-snapshot/v1";
  connectorType: "sqlserver";
  available: boolean;
  capability: SqlServerAdapterCapability;
  operations: Array<"probe" | "test" | "discover" | "preview" | "plan" | "snapshot" | "activate" | "activation-status">;
  permissions: {
    network: "allowlisted-read-only";
    database: "catalog-and-generated-select-only";
    arbitrarySql: false;
    concurrency: 1;
    fallback: "none";
  };
  credentials: {
    mode: "server-env-reference";
    configured: boolean;
    valuesInReceipts: false;
  };
  config?: SqlServerPublicTarget | null;
  reason?: string | null;
}

export interface SqlServerCatalogColumn {
  name: string;
  dataType: string;
  nullable: boolean;
  ordinal: number;
}

export interface SqlServerCatalogResource {
  resourceKey: string;
  schemaName: string;
  name: string;
  type: "table" | "view";
  columns: SqlServerCatalogColumn[];
  keyCandidates: string[][];
  rowEstimate: number;
}

export interface SqlServerCatalog {
  ok: true;
  schema: "aibi-sqlserver-catalog/v1";
  workspaceId: string;
  target: SqlServerPublicTarget;
  networkBindingFingerprint: string;
  catalogFingerprint: string;
  resources: SqlServerCatalogResource[];
  rawRowsReturned: false;
}

export interface SqlServerWatermarkSelection {
  column: string;
  after?: string | number | null;
  tieBreakers: string[];
  afterTieBreakers?: Array<string | number | null>;
}

export interface SqlServerSnapshotSelectionInput {
  resourceKey: string;
  columns: string[];
  orderBy: string[];
  stableOrderingConfirmed?: boolean;
  watermark?: SqlServerWatermarkSelection | null;
  targetTableKey: string;
  estimatedRows?: number;
}

export interface SqlServerSnapshotBudget {
  maxTables: number;
  maxColumnsPerTable: number;
  maxRowsPerTable: number;
  maxBytes: number;
  timeoutSeconds: number;
  pageSize: number;
}

export interface SqlServerSnapshotPlan {
  ok: true;
  schema: "aibi-sqlserver-snapshot-plan/v1";
  workspaceId: string;
  requestKey: string;
  createdAt: string;
  capability: "ready_for_snapshot";
  target: SqlServerPublicTarget;
  catalogFingerprint: string;
  networkBindingFingerprint: string;
  selections: Array<SqlServerSnapshotSelectionInput & {
    orderingBasis: "catalog_unique_key" | "user_confirmed_non_null";
  }>;
  budget: SqlServerSnapshotBudget;
  staging: { format: "csv-utf8"; artifactKey: string };
  activation: { required: true; boundary: "durable-import-and-source-activation-journal" };
  planFingerprint: string;
}

export interface SqlServerSnapshotReceipt {
  ok: true;
  schema: "aibi-sqlserver-snapshot-receipt/v1";
  operation: "test" | "preview" | "snapshot" | "activate";
  workspaceId: string;
  capability: SqlServerAdapterCapability;
  artifactKey?: string;
  planFingerprint?: string;
  catalogFingerprint?: string;
  manifestFingerprint?: string;
  totalRows?: number;
  totalBytes?: number;
  idempotentReplay?: boolean;
  activation?: { required?: boolean; status: "pending" | "committed"; journalKey?: string };
}

export type SqlServerActivationStatus =
  | "not_started"
  | "finalization_pending"
  | "committed"
  | AnalysisJobStatus;

export interface SqlServerActivationPayload {
  ok: true;
  operation: "activate" | "activation-status";
  workspaceId: string;
  connector?: { connectorKey: string; name: string; type: "sqlserver"; provider: string; status: string };
  artifactKey: string;
  planFingerprint: string;
  manifestFingerprint: string;
  importPlanFingerprint?: string;
  capability: SqlServerAdapterCapability;
  accepted?: boolean;
  replayed?: boolean;
  job?: AnalysisJob;
  activation: {
    status: SqlServerActivationStatus;
    journalRequired?: boolean;
    journalKey?: string;
    phase?: "finalized";
  };
}

export interface SqlServerAdapterErrorPayload {
  ok: false;
  code: string;
  error: string;
  recoveryAction?: string;
}

export type SqlServerAdapterResult<T> = T | SqlServerAdapterErrorPayload;
