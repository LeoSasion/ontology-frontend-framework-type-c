import assert from "node:assert/strict";
import type { IncomingMessage, ServerResponse } from "node:http";
import { Readable } from "node:stream";
import test from "node:test";

import { handleQueryApi } from "../server/queryRoutes";
import {
  assertTableQueryBatchWorkspace,
  runTableQuery,
  type TableQueryBatchPayload,
  type TableQueryOptions,
} from "../src/apiViews";
import {
  invalidateTableQueryCache,
  resetTableQueryRuntime,
  subscribeTableQuery,
  tableQueryCacheStats,
} from "../src/dashboardWidgetQueryRuntime";
import type { TableQueryPayload } from "../src/types";

function tablePayload(versionId: string, tableKey: string): TableQueryPayload {
  return {
    ok: true,
    tableQuery: {
      workspaceId: "workspace-a",
      mode: "aggregate",
      tableKey,
      columns: ["value"],
      rows: [{ value: 1 }],
      totalRows: 1,
      filteredRows: 1,
      limit: 50,
      runtime: {
        engine: "duckdb",
        compiledSql: "SELECT 1",
        replicas: [{ logicalTable: tableKey, versionId, objectHashes: [`hash-${versionId}`], rowCount: 1 }],
      },
    },
  };
}

function responseRecorder() {
  let statusCode = 0;
  let body = "";
  const response = {
    writeHead(status: number) {
      statusCode = status;
      return this;
    },
    end(value?: string) {
      body = value ?? "";
      return this;
    },
  } as unknown as ServerResponse;
  return { response, get statusCode() { return statusCode; }, get body() { return body; } };
}

test("dashboard batch route forwards twenty plans in one runtime command", async () => {
  const plans = Array.from({ length: 20 }, (_, index) => ({ table: `orders_${index}`, mode: "aggregate", aggregation: "count", limit: 50 }));
  const request = Readable.from([JSON.stringify({ workspaceId: "workspace-a", plans })]) as unknown as IncomingMessage;
  request.method = "POST";
  request.headers = { "content-type": "application/json" };
  const recorded = responseRecorder();
  let cliCalls = 0;
  let cliArgs: string[] = [];
  const handled = await handleQueryApi({
    cli: async (args) => {
      cliCalls += 1;
      cliArgs = args;
      return {
        ok: true,
        batchQuery: {
          schema: "aibi-query-table-batch/v1",
          planCount: 20,
          succeeded: 20,
          failed: 0,
          responseBytes: 0,
          results: plans.map((plan, index) => ({
            index,
            ok: true,
            tableQuery: tablePayload("v1", String(plan.table)).tableQuery,
          })),
        },
      };
    },
    request,
    response: recorded.response,
    url: new URL("http://127.0.0.1/api/query-table/batch"),
  });

  assert.equal(handled, true);
  assert.equal(cliCalls, 1);
  assert.equal(recorded.statusCode, 200);
  assert.equal(cliArgs[0], "query-table-batch");
  assert.equal(cliArgs.filter((arg) => arg === "--plan").length, 20);
});

test("dashboard batch route rejects an incomplete runtime envelope", async () => {
  const plans = [{ table: "orders" }, { table: "customers" }];
  const request = Readable.from([JSON.stringify({ workspaceId: "workspace-a", plans })]) as unknown as IncomingMessage;
  request.method = "POST";
  request.headers = { "content-type": "application/json" };
  const recorded = responseRecorder();
  await handleQueryApi({
    cli: async () => ({
      ok: true,
      batchQuery: {
        schema: "aibi-query-table-batch/v1",
        planCount: 2,
        succeeded: 1,
        failed: 0,
        responseBytes: 0,
        results: [{ index: 0, ok: true, tableQuery: tablePayload("v1", "orders").tableQuery }],
      },
    }),
    request,
    response: recorded.response,
    url: new URL("http://127.0.0.1/api/query-table/batch"),
  });
  assert.equal(recorded.statusCode, 409);
  assert.match(recorded.body, /query-table-batch-contract-mismatch/);
});

test("client batch assertion rejects duplicate or incomplete result indices", () => {
  const malformed = {
    ok: true,
    batchQuery: {
      schema: "aibi-query-table-batch/v1",
      planCount: 2,
      succeeded: 2,
      failed: 0,
      responseBytes: 0,
      results: [0, 0].map((index) => ({
        index,
        ok: true,
        tableQuery: tablePayload("v1", "orders").tableQuery,
      })),
    },
  } as TableQueryBatchPayload;
  assert.throws(
    () => assertTableQueryBatchWorkspace(malformed, "workspace-a", 2),
    (error: unknown) => error instanceof Error && error.name === "TableQueryBatchContractError",
  );
});

test("dashboard batch route rejects more than thirty-two plans before the runtime", async () => {
  const plans = Array.from({ length: 33 }, () => ({ table: "orders", mode: "aggregate" }));
  const request = Readable.from([JSON.stringify({ workspaceId: "workspace-a", plans })]) as unknown as IncomingMessage;
  request.method = "POST";
  request.headers = { "content-type": "application/json" };
  const recorded = responseRecorder();
  let called = false;
  await handleQueryApi({
    cli: async () => {
      called = true;
      return { ok: true };
    },
    request,
    response: recorded.response,
    url: new URL("http://127.0.0.1/api/query-table/batch"),
  });
  assert.equal(called, false);
  assert.equal(recorded.statusCode, 400);
  assert.match(recorded.body, /query-table-batch-plan-count-invalid/);
});

test("dashboard widget subscriptions share one batch, isolate item failures, and evict stale versions", async () => {
  resetTableQueryRuntime();
  const batchCalls: TableQueryOptions[][] = [];
  let version = "v1";
  const batchRunner = async (_workspaceId: string, plans: TableQueryOptions[]): Promise<TableQueryBatchPayload> => {
    batchCalls.push(plans);
    return {
      ok: true,
      batchQuery: {
        schema: "aibi-query-table-batch/v1",
        planCount: plans.length,
        succeeded: plans.length - (plans.length > 1 ? 1 : 0),
        failed: plans.length > 1 ? 1 : 0,
        responseBytes: 0,
        results: plans.map((plan, index) => index === 1 && plans.length > 1
          ? { index, ok: false, errorCode: "replica-version-stale", error: "replica-version-stale:orders" }
          : { index, ok: true, tableQuery: tablePayload(version, String(plan.table ?? "orders")).tableQuery }),
      },
    };
  };
  const firstOptions = Array.from({ length: 20 }, (_, index) => ({
    table: "orders",
    mode: "aggregate" as const,
    groupFields: [`channel_${index}`],
  }));
  const firstSubscriptions = firstOptions.map((options) => subscribeTableQuery({ workspaceId: "workspace-a", generation: "v1" }, options, runTableQuery, batchRunner));
  const firstResults = await Promise.allSettled(firstSubscriptions.map((subscription) => subscription.promise));
  firstSubscriptions.forEach((subscription) => subscription.release());
  assert.equal(batchCalls.length, 1);
  assert.equal(batchCalls[0].length, 20);
  assert.equal(firstResults.filter((result) => result.status === "fulfilled").length, 19);
  assert.equal(firstResults.filter((result) => result.status === "rejected").length, 1);

  version = "v2";
  const refreshed = subscribeTableQuery(
    { workspaceId: "workspace-a", generation: "v2" },
    { table: "orders", mode: "aggregate", groupFields: ["fresh"] },
    runTableQuery,
    batchRunner,
  );
  await refreshed.promise;
  refreshed.release();
  assert.equal(batchCalls.length, 2);
  assert.deepEqual(tableQueryCacheStats(), { active: 0, settled: 1 });
  resetTableQueryRuntime();
});

test("dashboard batching chunks more than thirty-two widget plans without crossing the runtime limit", async () => {
  resetTableQueryRuntime();
  const batchSizes: number[] = [];
  const batchRunner = async (_workspaceId: string, plans: TableQueryOptions[]): Promise<TableQueryBatchPayload> => {
    batchSizes.push(plans.length);
    return {
      ok: true,
      batchQuery: {
        schema: "aibi-query-table-batch/v1",
        planCount: plans.length,
        succeeded: plans.length,
        failed: 0,
        responseBytes: 0,
        results: plans.map((plan, index) => ({
          index,
          ok: true,
          tableQuery: tablePayload("v1", String(plan.table)).tableQuery,
        })),
      },
    };
  };
  const subscriptions = Array.from({ length: 70 }, (_, index) => subscribeTableQuery(
    { workspaceId: "workspace-a", generation: "v1" },
    { table: `orders_${index}`, mode: "aggregate" },
    runTableQuery,
    batchRunner,
  ));
  await Promise.all(subscriptions.map((subscription) => subscription.promise));
  subscriptions.forEach((subscription) => subscription.release());
  assert.deepEqual(batchSizes, [32, 32, 6]);
  resetTableQueryRuntime();
});

test("invalidating every member aborts an already-running dashboard batch", async () => {
  resetTableQueryRuntime();
  let batchSignal: AbortSignal | undefined;
  let markStarted!: () => void;
  const started = new Promise<void>((resolve) => { markStarted = resolve; });
  const batchRunner = async (_workspaceId: string, _plans: TableQueryOptions[], signal?: AbortSignal) => {
    batchSignal = signal;
    markStarted();
    await new Promise<void>((_resolve, reject) => signal?.addEventListener("abort", () => reject(new Error("batch-aborted")), { once: true }));
    throw new Error("unreachable");
  };
  const subscriptions = ["channel", "region"].map((group) => subscribeTableQuery(
    { workspaceId: "workspace-a", generation: "v1" },
    { table: "orders", mode: "aggregate", groupFields: [group] },
    runTableQuery,
    batchRunner,
  ));

  await started;
  invalidateTableQueryCache({ workspaceId: "workspace-a", table: "orders" });
  assert.equal(batchSignal?.aborted, true);
  const results = await Promise.allSettled(subscriptions.map((subscription) => subscription.promise));
  assert.equal(results.every((result) => result.status === "rejected"), true);
  subscriptions.forEach((subscription) => subscription.release());
  resetTableQueryRuntime();
});

test("invalidating only part of a dashboard batch leaves the shared execution running", async () => {
  resetTableQueryRuntime();
  let batchSignal: AbortSignal | undefined;
  let markStarted!: () => void;
  let completeBatch!: () => void;
  const started = new Promise<void>((resolve) => { markStarted = resolve; });
  const gate = new Promise<void>((resolve) => { completeBatch = resolve; });
  const batchRunner = async (
    _workspaceId: string,
    plans: TableQueryOptions[],
    signal?: AbortSignal,
  ): Promise<TableQueryBatchPayload> => {
    batchSignal = signal;
    markStarted();
    await gate;
    return {
      ok: true,
      batchQuery: {
        schema: "aibi-query-table-batch/v1",
        planCount: plans.length,
        succeeded: plans.length,
        failed: 0,
        responseBytes: 0,
        results: plans.map((plan, index) => ({
          index,
          ok: true,
          tableQuery: tablePayload("v1", String(plan.table)).tableQuery,
        })),
      },
    };
  };
  const orders = subscribeTableQuery(
    { workspaceId: "workspace-a", generation: "v1" },
    { table: "orders", mode: "aggregate" },
    runTableQuery,
    batchRunner,
  );
  const customers = subscribeTableQuery(
    { workspaceId: "workspace-a", generation: "v1" },
    { table: "customers", mode: "aggregate" },
    runTableQuery,
    batchRunner,
  );

  await started;
  invalidateTableQueryCache({ workspaceId: "workspace-a", table: "orders" });
  assert.equal(batchSignal?.aborted, false);
  completeBatch();
  const [ordersResult, customersResult] = await Promise.allSettled([orders.promise, customers.promise]);
  assert.equal(ordersResult.status, "rejected");
  assert.equal(customersResult.status, "fulfilled");
  orders.release();
  customers.release();
  resetTableQueryRuntime();
});
