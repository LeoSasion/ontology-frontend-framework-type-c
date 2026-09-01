export type WorkspaceRecoveryOperation = "create" | "restore" | "delete";

export interface WorkspaceRecoveryFileSummary {
  kind: "sqlite-control" | "duckdb-catalog";
  bytes: number;
  sha256: string;
}

export interface WorkspaceRecoveryPoint {
  schema: "aibi-workspace-recovery-point/v2";
  workspaceId: string;
  recoveryPointKey: string;
  createdAt: string;
  reason: string;
  status: "ready";
  contentFingerprint: string;
  workspaceStateFingerprint: string;
  sqliteSchemaVersion: number;
  duckdbSchemaVersion: number | null;
  currentSourceRunId: string | null;
  sourceVersions: Array<{ tableKey: string; dataVersion: number; updatedAt: string }>;
  files: WorkspaceRecoveryFileSummary[];
  totalBytes: number;
  verified: boolean;
}

export interface WorkspaceRecoveryPlan {
  schema: "aibi-workspace-recovery-plan/v1";
  status: "waiting-confirmation";
  operation: WorkspaceRecoveryOperation;
  workspaceId: string;
  requestKeyFingerprint: string;
  intentFingerprint: string;
  inputFingerprint: string;
  planFingerprint: string;
  currentWorkspaceStateFingerprint: string;
  recoveryPointKey: string;
  recoveryPointFingerprint: string | null;
  estimatedBytes: number;
  writesBusinessState: boolean;
  requiresSafetyPoint: boolean;
  invalidationKeys: string[];
}

export interface WorkspaceRecoveryComparison {
  ok: boolean;
  schema: "aibi-workspace-recovery-comparison/v1";
  workspaceId: string;
  recoveryPointKey: string;
  verified: boolean;
  currentWorkspaceStateFingerprint: string;
  targetWorkspaceStateFingerprint: string;
  currentSourceRunId: string | null;
  targetSourceRunId: string | null;
  changes: Array<{ tableKey: string; change: "restore" | "remove" | "version-change" | "unchanged"; currentDataVersion: number | null; targetDataVersion: number | null }>;
  changedCount: number;
  unchangedCount: number;
  summary: { restore: number; remove: number; versionChange: number };
  exposesBusinessRows: false;
}

export interface WorkspaceRecoveryPayload {
  ok: boolean;
  schema?: "aibi-workspace-recovery-points/v1";
  workspaceId: string;
  health?: "empty" | "ready" | "attention";
  recoveryPoints?: WorkspaceRecoveryPoint[];
  recoveryPoint?: WorkspaceRecoveryPoint;
  safetyRecoveryPoint?: WorkspaceRecoveryPoint;
  recoveryPlan?: WorkspaceRecoveryPlan;
  count?: number;
  invalidCount?: number;
  dryRun?: boolean;
  requiresConfirmation?: boolean;
  confirmed?: boolean;
  changed?: boolean;
  idempotentReplay?: boolean;
  verified?: boolean;
  deletedRecoveryPointKey?: string;
  invalidationKeys?: string[];
  error?: string;
  code?: string;
  recoveryAction?: string;
}
