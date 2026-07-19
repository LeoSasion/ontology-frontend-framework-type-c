import { fetchJson, fetchJsonStrict } from "./apiClient";
import { emptyImportPreview } from "./emptyWorkspaceData";
import type { SourceIntelligenceRunRequest, SourceIntelligenceRunResponse } from "./sourceIntelligenceRunModel";
import type { FolderImportPlan, ImportPreview } from "./types";

const emptyFolderImportPlan: FolderImportPlan = {
  ok: true,
  dryRun: true,
  path: "",
  fileCount: 0,
  tableCount: 0,
  willWrite: false,
  items: [],
  groups: [],
};

function normalizeFolderImportPlan(value: FolderImportPlan | Record<string, unknown>, requestedPath = ""): FolderImportPlan {
  const plan = value as Partial<FolderImportPlan>;
  return {
    ok: Boolean(plan.ok),
    dryRun: plan.dryRun,
    requiresConfirmation: plan.requiresConfirmation,
    committed: plan.committed,
    path: String(plan.path ?? requestedPath),
    fileCount: Number(plan.fileCount ?? 0),
    tableCount: Number(plan.tableCount ?? 0),
    willWrite: Boolean(plan.willWrite),
    planFingerprint: plan.planFingerprint,
    blockers: Array.isArray(plan.blockers) ? plan.blockers : [],
    readyToCommit: plan.readyToCommit === true,
    sourceRunId: plan.sourceRunId,
    items: Array.isArray(plan.items) ? plan.items : [],
    groups: Array.isArray(plan.groups) ? plan.groups : [],
    results: Array.isArray(plan.results) ? plan.results : undefined,
  };
}

export function previewImport(filePath = "") {
  return fetchJson<ImportPreview>("/api/import/preview", emptyImportPreview, {
    method: "POST",
    body: JSON.stringify({ filePath }),
  });
}

export function previewImportWithOptions(options: {
  filePath: string;
  table?: string;
  uniqueFields?: string[];
  conflictRule?: string;
}) {
  return fetchJson<ImportPreview>("/api/import/preview", emptyImportPreview, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function setImportPolicy(options: {
  table: string;
  uniqueFields: string[];
  conflictRule?: string;
  confirm?: boolean;
}) {
  return fetchJson<Record<string, unknown>>("/api/import/policy", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function listImportJobs(options: {
  table?: string;
  status?: string;
  search?: string;
  limit?: number;
} = {}) {
  const params = new URLSearchParams();
  if (options.table) params.set("table", options.table);
  if (options.status) params.set("status", options.status);
  if (options.search) params.set("search", options.search);
  if (options.limit) params.set("limit", String(options.limit));
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return fetchJson<Record<string, unknown>>(`/api/import/jobs${suffix}`, { ok: false });
}

export function removeImportJob(options: { jobKey: string; confirm?: boolean }) {
  return fetchJson<Record<string, unknown>>("/api/import/jobs/remove", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function commitImport(options: {
  filePath: string;
  table?: string;
  name?: string;
  mode?: string;
  uniqueFields?: string[];
  conflictRule?: string;
  confirm?: boolean;
}) {
  return fetchJson<Record<string, unknown>>("/api/import/commit", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function previewFolderImport(options: {
  path: string;
  limit?: number;
  recursive?: boolean;
  uniqueFields?: string[];
  conflictRule?: string;
}) {
  return fetchJson<FolderImportPlan>("/api/import/folder/preview", emptyFolderImportPlan, {
    method: "POST",
    body: JSON.stringify(options),
  }).then((result) => normalizeFolderImportPlan(result, options.path));
}

export function commitFolderImport(options: {
  path: string;
  limit?: number;
  recursive?: boolean;
  uniqueFields?: string[];
  conflictRule?: string;
  expectedPlan?: string;
  confirm?: boolean;
}) {
  return fetchJson<FolderImportPlan>("/api/import/folder/commit", emptyFolderImportPlan, {
    method: "POST",
    body: JSON.stringify(options),
  }).then((result) => normalizeFolderImportPlan(result, options.path));
}

export function listConnectors(options: {
  type?: string;
  status?: string;
  search?: string;
} = {}) {
  const params = new URLSearchParams();
  if (options.type) params.set("type", options.type);
  if (options.status) params.set("status", options.status);
  if (options.search) params.set("search", options.search);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  return fetchJson<Record<string, unknown>>(`/api/connectors${suffix}`, { ok: false });
}

export function saveConnector(options: {
  connector?: string;
  name: string;
  type?: string;
  provider?: string;
  status?: string;
  endpoint?: string;
  resource?: string;
  credentialRef?: string;
  pageParam?: string;
  pageSizeParam?: string;
  pageSize?: number;
  maxPages?: number;
  importMode?: string;
  targetTable?: string;
  uniqueFields?: string[];
  conflictRule?: string;
  schedule?: string;
  notes?: string;
  confirm?: boolean;
}) {
  return fetchJson<Record<string, unknown>>("/api/connectors", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function syncConnector(options: { connector: string; allowPaused?: boolean; confirm?: boolean }) {
  return fetchJson<Record<string, unknown>>("/api/connectors/sync", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function removeConnector(options: { connector: string; confirm?: boolean }) {
  return fetchJson<Record<string, unknown>>("/api/connectors/remove", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function navigationOperation(options: {
  moduleKey: string;
  op: "rename" | "move" | "hide" | "show";
  name?: string;
  sort?: number;
  confirm?: boolean;
}) {
  return fetchJson<Record<string, unknown>>("/api/navigation/operation", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function listSources() {
  return fetchJson<Record<string, unknown>>("/api/sources", { ok: false });
}

export function inspectSource(table: string) {
  const params = new URLSearchParams({ table });
  return fetchJson<Record<string, unknown>>(`/api/sources/inspect?${params.toString()}`, { ok: false });
}

export function renameSource(options: { source: string; name: string; confirm?: boolean }) {
  return fetchJson<Record<string, unknown>>("/api/sources/rename", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function deleteSource(options: { source: string; confirm?: boolean }) {
  return fetchJson<Record<string, unknown>>("/api/sources/delete", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function runSourceIntelligence(options: SourceIntelligenceRunRequest) {
  return fetchJsonStrict<SourceIntelligenceRunResponse>("/api/source-intelligence/run", {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function createSourceDashboardDraft(options: {
  runKey?: string;
  name?: string;
  limit?: number;
}) {
  return fetchJsonStrict<Record<string, unknown>>("/api/source-intelligence/dashboard-draft", {
    method: "POST",
    body: JSON.stringify(options),
  });
}
