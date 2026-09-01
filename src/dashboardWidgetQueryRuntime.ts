import {
  assertTableQueryBatchWorkspace,
  assertTableQueryWorkspace,
  runTableQuery,
  runTableQueryBatch,
  type TableQueryBatchPayload,
  type TableQueryOptions,
} from "./apiViews";
import type { TableQueryPayload } from "./types";

type TableQueryRunner = (
  workspaceId: string,
  options: TableQueryOptions,
  signal?: AbortSignal,
) => Promise<TableQueryPayload>;
export type TableQueryBatchRunner = (
  workspaceId: string,
  plans: TableQueryOptions[],
  signal?: AbortSignal,
) => Promise<TableQueryBatchPayload>;
type ActiveTableQuery = {
  controller: AbortController;
  generation: string;
  invalidated: boolean;
  options: TableQueryOptions;
  promise: Promise<TableQueryPayload>;
  reject?: (error: unknown) => void;
  subscribers: number;
  workspaceId: string;
  batch?: BatchExecution;
};
type PendingBatchEntry = ActiveTableQuery & {
  key: string;
  startedAt: number;
  resolve: (result: TableQueryPayload) => void;
  reject: (error: unknown) => void;
};
type BatchExecution = { controller: AbortController; entries: PendingBatchEntry[] };
type SettledTableQuery = {
  generation: string;
  options: TableQueryOptions;
  result: TableQueryPayload;
  expiresAt: number;
  sourceScope: string;
  tableKey: string;
  versionKey: string;
  viewKey: string;
  workspaceId: string;
};

export type TableQueryCacheInvalidation = {
  workspaceId: string;
  table?: string;
  views?: string[];
  options?: TableQueryOptions;
};

export type TableQueryCacheScope = {
  workspaceId: string;
  generation: string;
};

const SETTLED_TTL_MS = 5_000;
const SETTLED_MAX_ENTRIES = 64;
const BATCH_MAX_PLANS = 32;
const activeTableQueries = new Map<string, ActiveTableQuery>();
const settledTableQueries = new Map<string, SettledTableQuery>();
const latestVersionByScope = new Map<string, { versionKey: string; observedAt: number }>();
const pendingBatchEntries = new Map<string, PendingBatchEntry>();
let batchFlushScheduled = false;
let activeTableQueryWorkspaceId = "";
let queryStartSequence = 0;

function requiredWorkspaceId(workspaceId: string) {
  const normalized = workspaceId.trim();
  if (!normalized) throw new Error("A workspace is required for table query caching");
  return normalized;
}

function canonicalize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(canonicalize);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>)
        .filter(([, item]) => item !== undefined)
        .sort(([left], [right]) => left.localeCompare(right))
        .map(([key, item]) => [key, canonicalize(item)]),
    );
  }
  return value;
}

function normalizedScope(scope: TableQueryCacheScope) {
  return { workspaceId: requiredWorkspaceId(scope.workspaceId), generation: String(scope.generation ?? "") };
}

export function tableQueryFingerprint(scope: TableQueryCacheScope, options: TableQueryOptions) {
  return JSON.stringify(canonicalize({ ...normalizedScope(scope), query: options }));
}

function sourceScopeKey(workspaceId: string, tableKey: string) {
  return `${workspaceId}\u0000${tableKey}`;
}

function resultVersionKey(result: TableQueryPayload) {
  const replicas = result.tableQuery.runtime?.replicas ?? [];
  if (replicas.length) {
    return replicas
      .map((replica) => [
        replica.logicalTable ?? "",
        replica.versionId ?? "",
        replica.contentFingerprint ?? "",
        ...(replica.objectHashes ?? []),
      ].join(":"))
      .sort()
      .join("|");
  }
  return result.tableQuery.sourceVersion ?? "";
}

function resultSourceScope(workspaceId: string, options: TableQueryOptions, result: TableQueryPayload) {
  const tableKey = result.tableQuery.tableKey || options.table || `view:${options.view ?? "unknown"}`;
  return sourceScopeKey(workspaceId, tableKey);
}

function evictExpired(now = Date.now()) {
  for (const [key, entry] of settledTableQueries) {
    if (entry.expiresAt <= now) settledTableQueries.delete(key);
  }
}

function storeSettledResult(
  key: string,
  workspaceId: string,
  generation: string,
  options: TableQueryOptions,
  result: TableQueryPayload,
  startedAt: number,
) {
  assertTableQueryWorkspace(result, workspaceId);
  const versionKey = resultVersionKey(result);
  if (!versionKey) return true;
  const sourceScope = resultSourceScope(workspaceId, options, result);
  const latest = latestVersionByScope.get(sourceScope);
  if (latest && latest.versionKey !== versionKey) {
    if (latest.observedAt > startedAt) return false;
    for (const [candidateKey, entry] of settledTableQueries) {
      if (entry.sourceScope === sourceScope && entry.versionKey !== versionKey) settledTableQueries.delete(candidateKey);
    }
  }
  latestVersionByScope.set(sourceScope, { versionKey, observedAt: startedAt });
  settledTableQueries.delete(key);
  settledTableQueries.set(key, {
    result,
    generation,
    options,
    sourceScope,
    tableKey: result.tableQuery.tableKey,
    versionKey,
    viewKey: result.tableQuery.viewKey ?? options.view ?? "",
    workspaceId,
    expiresAt: Date.now() + SETTLED_TTL_MS,
  });
  while (settledTableQueries.size > SETTLED_MAX_ENTRIES) {
    const oldestKey = settledTableQueries.keys().next().value;
    if (typeof oldestKey !== "string") break;
    settledTableQueries.delete(oldestKey);
  }
  return true;
}

function settledResult(key: string) {
  evictExpired();
  const entry = settledTableQueries.get(key);
  if (!entry) return undefined;
  settledTableQueries.delete(key);
  settledTableQueries.set(key, entry);
  return entry.result;
}

function abortError(message = "Table query subscription was released before execution") {
  const error = new Error(message);
  error.name = "AbortError";
  return error;
}

function abortable<T>(operation: Promise<T>, signal: AbortSignal) {
  if (signal.aborted) return Promise.reject<T>(abortError());
  return new Promise<T>((resolve, reject) => {
    const onAbort = () => reject(abortError());
    signal.addEventListener("abort", onAbort, { once: true });
    operation.then(resolve, reject).finally(() => signal.removeEventListener("abort", onAbort));
  });
}

function abortAllActiveQueries(message: string) {
  const error = abortError(message);
  const executions = new Set<BatchExecution>();
  for (const entry of activeTableQueries.values()) {
    entry.invalidated = true;
    entry.controller.abort();
    entry.reject?.(error);
    if (entry.batch) executions.add(entry.batch);
  }
  for (const entry of pendingBatchEntries.values()) entry.reject(error);
  for (const execution of executions) execution.controller.abort();
  activeTableQueries.clear();
  pendingBatchEntries.clear();
}

export function resetTableQueryRuntime() {
  abortAllActiveQueries("The active workspace changed before the table query completed");
  settledTableQueries.clear();
  latestVersionByScope.clear();
  activeTableQueryWorkspaceId = "";
}

export function activateTableQueryWorkspace(workspaceId: string) {
  const nextWorkspaceId = requiredWorkspaceId(workspaceId);
  if (activeTableQueryWorkspaceId === nextWorkspaceId) return;
  abortAllActiveQueries("The active workspace changed before the table query completed");
  settledTableQueries.clear();
  latestVersionByScope.clear();
  activeTableQueryWorkspaceId = nextWorkspaceId;
}

function activeMatchesInvalidation(entry: ActiveTableQuery, invalidation: TableQueryCacheInvalidation) {
  if (entry.workspaceId !== invalidation.workspaceId) return false;
  if (invalidation.options) {
    return JSON.stringify(canonicalize(entry.options)) === JSON.stringify(canonicalize(invalidation.options));
  }
  const views = new Set((invalidation.views ?? []).filter(Boolean));
  if (invalidation.table || views.size) {
    return entry.options.table === invalidation.table || Boolean(entry.options.view && views.has(entry.options.view));
  }
  return true;
}

function settledMatchesInvalidation(entry: SettledTableQuery, invalidation: TableQueryCacheInvalidation) {
  if (entry.workspaceId !== invalidation.workspaceId) return false;
  if (invalidation.options) {
    return JSON.stringify(canonicalize(entry.options)) === JSON.stringify(canonicalize(invalidation.options));
  }
  const views = new Set((invalidation.views ?? []).filter(Boolean));
  if (invalidation.table || views.size) {
    return entry.tableKey === invalidation.table || Boolean(entry.viewKey && views.has(entry.viewKey));
  }
  return true;
}

export function invalidateTableQueryCache(invalidation: TableQueryCacheInvalidation) {
  const workspaceId = requiredWorkspaceId(invalidation.workspaceId);
  const normalized = { ...invalidation, workspaceId };
  const affectedBatchExecutions = new Set<BatchExecution>();
  for (const [key, entry] of settledTableQueries) {
    if (settledMatchesInvalidation(entry, normalized)) settledTableQueries.delete(key);
  }
  if (normalized.table) latestVersionByScope.delete(sourceScopeKey(workspaceId, normalized.table));
  else if (!normalized.views?.length && !normalized.options) {
    for (const key of latestVersionByScope.keys()) {
      if (key.startsWith(`${workspaceId}\u0000`)) latestVersionByScope.delete(key);
    }
  }
  for (const [key, entry] of activeTableQueries) {
    if (!activeMatchesInvalidation(entry, normalized)) continue;
    entry.invalidated = true;
    activeTableQueries.delete(key);
    const error = abortError("The table query was invalidated by a newer source version");
    const pending = pendingBatchEntries.get(key);
    if (pending) pendingBatchEntries.delete(key);
    entry.reject?.(error);
    if (entry.batch) affectedBatchExecutions.add(entry.batch);
    else entry.controller.abort();
  }
  for (const execution of affectedBatchExecutions) {
    if (execution.entries.every((entry) => entry.invalidated || entry.subscribers <= 0)) {
      execution.controller.abort();
    }
  }
}

export function tableQueryCacheStats() {
  evictExpired();
  return { active: activeTableQueries.size, settled: settledTableQueries.size };
}

function batchItemError(item: { errorCode?: string; error?: string }) {
  const error = new Error(item.error || item.errorCode || "query-table-batch-item-failed");
  if (item.errorCode) error.name = item.errorCode;
  return error;
}

function executeBatch(entries: PendingBatchEntry[], batchRunner: TableQueryBatchRunner) {
  if (!entries.length) return;
  const workspaceId = entries[0].workspaceId;
  const execution: BatchExecution = { controller: new AbortController(), entries };
  entries.forEach((entry) => { entry.batch = execution; });
  void Promise.resolve()
    .then(() => batchRunner(workspaceId, entries.map((entry) => entry.options), execution.controller.signal))
    .then((payload) => {
      assertTableQueryBatchWorkspace(payload, workspaceId, entries.length);
      const byIndex = new Map(payload.batchQuery.results.map((item) => [item.index, item]));
      entries.forEach((entry, index) => {
        if (entry.invalidated) {
          entry.reject(abortError("The table query was invalidated before its batch completed"));
          return;
        }
        const item = byIndex.get(index);
        if (!item || !item.ok || !item.tableQuery) {
          entry.reject(batchItemError(item ?? { errorCode: "query-table-batch-item-missing" }));
          return;
        }
        const result = assertTableQueryWorkspace({ ok: true, tableQuery: item.tableQuery }, entry.workspaceId);
        if (!storeSettledResult(entry.key, entry.workspaceId, entry.generation, entry.options, result, entry.startedAt)) {
          entry.reject(abortError("A newer source version completed before this table query"));
          return;
        }
        entry.resolve(result);
      });
    })
    .catch((error) => entries.forEach((entry) => entry.reject(error)))
    .finally(() => {
      entries.forEach((entry) => {
        if (entry.batch === execution) entry.batch = undefined;
        if (activeTableQueries.get(entry.key)?.promise === entry.promise) activeTableQueries.delete(entry.key);
      });
    });
}

function flushPendingBatch(batchRunner: TableQueryBatchRunner) {
  batchFlushScheduled = false;
  const entries = [...pendingBatchEntries.values()];
  pendingBatchEntries.clear();
  const grouped = new Map<string, PendingBatchEntry[]>();
  for (const entry of entries) {
    if (entry.invalidated || entry.subscribers <= 0 || activeTableQueries.get(entry.key) !== entry) {
      entry.reject(abortError());
      continue;
    }
    const group = grouped.get(entry.workspaceId) ?? [];
    group.push(entry);
    grouped.set(entry.workspaceId, group);
  }
  for (const group of grouped.values()) {
    for (let index = 0; index < group.length; index += BATCH_MAX_PLANS) {
      executeBatch(group.slice(index, index + BATCH_MAX_PLANS), batchRunner);
    }
  }
}

function scheduleBatch(entry: PendingBatchEntry, batchRunner: TableQueryBatchRunner) {
  pendingBatchEntries.set(entry.key, entry);
  if (batchFlushScheduled) return;
  batchFlushScheduled = true;
  queueMicrotask(() => flushPendingBatch(batchRunner));
}

export function subscribeTableQuery(
  scope: TableQueryCacheScope,
  options: TableQueryOptions,
  runner: TableQueryRunner = runTableQuery,
  batchRunner: TableQueryBatchRunner = runTableQueryBatch,
) {
  const { workspaceId: expectedWorkspaceId, generation } = normalizedScope(scope);
  if (activeTableQueryWorkspaceId !== expectedWorkspaceId) activateTableQueryWorkspace(expectedWorkspaceId);
  const key = tableQueryFingerprint({ workspaceId: expectedWorkspaceId, generation }, options);
  const cached = settledResult(key);
  if (cached) return { promise: Promise.resolve(cached), release() {} };

  let entry = activeTableQueries.get(key);
  if (!entry) {
    const controller = new AbortController();
    const startedAt = ++queryStartSequence;
    let resolveResult!: (result: TableQueryPayload) => void;
    let rejectResult!: (error: unknown) => void;
    if (runner === runTableQuery) {
      const promise = new Promise<TableQueryPayload>((resolve, reject) => {
        resolveResult = resolve;
        rejectResult = reject;
      });
      entry = {
        controller,
        generation,
        invalidated: false,
        options,
        promise,
        reject: rejectResult,
        subscribers: 0,
        workspaceId: expectedWorkspaceId,
      };
      activeTableQueries.set(key, entry);
      const pendingEntry = Object.assign(entry, { key, startedAt, resolve: resolveResult, reject: rejectResult }) as PendingBatchEntry;
      scheduleBatch(pendingEntry, batchRunner);
    } else {
      let ownedEntry: ActiveTableQuery | undefined;
      const operation = Promise.resolve().then(() => runner(expectedWorkspaceId, options, controller.signal));
      const promise = abortable(operation, controller.signal)
        .then((result) => {
          if (ownedEntry?.invalidated) throw abortError("The table query was invalidated before completion");
          const validated = assertTableQueryWorkspace(result, expectedWorkspaceId);
          if (!storeSettledResult(key, expectedWorkspaceId, generation, options, validated, startedAt)) {
            throw abortError("A newer source version completed before this table query");
          }
          return validated;
        })
        .finally(() => {
          if (activeTableQueries.get(key)?.promise === promise) activeTableQueries.delete(key);
        });
      ownedEntry = {
        controller,
        generation,
        invalidated: false,
        options,
        promise,
        subscribers: 0,
        workspaceId: expectedWorkspaceId,
      };
      entry = ownedEntry;
      activeTableQueries.set(key, entry);
    }
  }

  entry.subscribers += 1;
  let released = false;
  return {
    promise: entry.promise,
    release() {
      if (released) return;
      released = true;
      entry!.subscribers -= 1;
      if (entry!.subscribers === 0 && activeTableQueries.get(key) === entry) {
        entry!.invalidated = true;
        activeTableQueries.delete(key);
        const pending = pendingBatchEntries.get(key);
        if (pending) {
          pendingBatchEntries.delete(key);
          pending.reject(abortError());
        } else if (entry!.batch) {
          entry!.reject?.(abortError());
          if (entry!.batch.entries.every((candidate) => candidate.subscribers === 0 || candidate.invalidated)) {
            entry!.batch.controller.abort();
          }
        } else {
          entry!.controller.abort();
        }
      }
    },
  };
}
