import { fetchJsonStrict } from "./apiClient";
import type {
  SqlServerAdapterContract,
  SqlServerActivationPayload,
  SqlServerCatalog,
  SqlServerSnapshotBudget,
  SqlServerSnapshotPlan,
  SqlServerSnapshotReceipt,
  SqlServerSnapshotSelectionInput,
} from "./typesSqlServerSnapshot";

export interface SqlServerConnectorReference {
  connectorKey: string;
}
export function probeSqlServerAdapter(connectorKey?: string, signal?: AbortSignal) {
  const suffix = connectorKey ? `?connector=${encodeURIComponent(connectorKey)}` : "";
  return fetchJsonStrict<SqlServerAdapterContract>(`/api/connectors/sqlserver/probe${suffix}`, { signal });
}

export function testSqlServerConnection(input: SqlServerConnectorReference, signal?: AbortSignal) {
  return fetchJsonStrict<SqlServerSnapshotReceipt>("/api/connectors/sqlserver/test", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(input),
    signal,
  });
}

export function discoverSqlServerCatalog(input: SqlServerConnectorReference, signal?: AbortSignal) {
  return fetchJsonStrict<SqlServerCatalog>("/api/connectors/sqlserver/discover", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(input),
    signal,
  });
}

export function previewSqlServerResources(
  input: SqlServerConnectorReference & { catalogFingerprint: string; resourceKeys: string[] },
  signal?: AbortSignal,
) {
  return fetchJsonStrict<SqlServerSnapshotReceipt>("/api/connectors/sqlserver/preview", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(input),
    signal,
  });
}

export function planSqlServerSnapshot(
  input: SqlServerConnectorReference & {
    requestKey: string;
    catalogFingerprint: string;
    selections: SqlServerSnapshotSelectionInput[];
    budget?: Partial<SqlServerSnapshotBudget>;
  },
  signal?: AbortSignal,
) {
  return fetchJsonStrict<SqlServerSnapshotPlan>("/api/connectors/sqlserver/plan", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-idempotency-key": input.requestKey,
    },
    body: JSON.stringify(input),
    signal,
  });
}

export function createSqlServerSnapshot(
  input: SqlServerConnectorReference & {
    requestKey: string;
    expectedPlanFingerprint: string;
    confirm: true;
  },
  signal?: AbortSignal,
) {
  return fetchJsonStrict<SqlServerSnapshotReceipt>("/api/connectors/sqlserver/snapshot", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-idempotency-key": input.requestKey,
    },
    body: JSON.stringify(input),
    signal,
  });
}

export function activateSqlServerSnapshot(
  input: SqlServerConnectorReference & {
    workspaceId: string;
    requestKey: string;
    expectedPlanFingerprint: string;
    expectedManifestFingerprint: string;
    confirm: true;
  },
  signal?: AbortSignal,
) {
  return fetchJsonStrict<SqlServerActivationPayload>("/api/connectors/sqlserver/activate", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-idempotency-key": input.requestKey,
    },
    body: JSON.stringify(input),
    signal,
  });
}

export function fetchSqlServerActivationStatus(
  input: SqlServerConnectorReference & {
    workspaceId: string;
    requestKey: string;
    expectedPlanFingerprint: string;
    expectedManifestFingerprint: string;
  },
  signal?: AbortSignal,
) {
  const search = new URLSearchParams({
    connector: input.connectorKey,
    workspace: input.workspaceId,
    requestKey: input.requestKey,
    expectedPlan: input.expectedPlanFingerprint,
    expectedManifest: input.expectedManifestFingerprint,
  });
  return fetchJsonStrict<SqlServerActivationPayload>(`/api/connectors/sqlserver/activation-status?${search}`, { signal });
}
