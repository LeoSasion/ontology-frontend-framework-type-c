import assert from "node:assert/strict";
import test from "node:test";

import type { TableQueryOptions } from "../src/apiViews";
import {
  invalidateTableQueryCache,
  resetTableQueryRuntime,
  subscribeTableQuery,
  tableQueryCacheStats,
  tableQueryFingerprint,
} from "../src/dashboardWidgetQueryRuntime";
import type { TableQueryPayload } from "../src/types";
import { shouldCommitTableQueryResult } from "../src/tableQueryRequestGuard";

const WORKSPACE_A = "workspace-a";
const WORKSPACE_B = "workspace-b";

function scope(workspaceId: string, generation = "generation-1") {
  return { workspaceId, generation };
}

function payload(versionId: string, tableKey = "orders", workspaceId = WORKSPACE_A): TableQueryPayload {
  return {
    ok: true,
    tableQuery: {
      workspaceId,
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

test("dashboard query cache coalesces, reuses settled results, and invalidates exact scoped fingerprints", async () => {
  resetTableQueryRuntime();
  const options: TableQueryOptions = {
    table: "orders",
    mode: "aggregate",
    filters: [{ value: "paid", operator: "equals", field: "status" }],
    limit: 50,
  };
  const sameOptionsDifferentKeyOrder: TableQueryOptions = {
    limit: 50,
    filters: [{ field: "status", operator: "equals", value: "paid" }],
    mode: "aggregate",
    table: "orders",
  };
  assert.equal(
    tableQueryFingerprint(scope(WORKSPACE_A), options),
    tableQueryFingerprint(scope(WORKSPACE_A), sameOptionsDifferentKeyOrder),
  );
  assert.notEqual(
    tableQueryFingerprint(scope(WORKSPACE_A), options),
    tableQueryFingerprint(scope(WORKSPACE_B), options),
  );

  let calls = 0;
  const runner = async (workspaceId: string) => {
    calls += 1;
    return payload("v1", "orders", workspaceId);
  };
  const first = subscribeTableQuery(scope(WORKSPACE_A), options, runner);
  const shared = subscribeTableQuery(scope(WORKSPACE_A), sameOptionsDifferentKeyOrder, runner);
  assert.equal(first.promise, shared.promise);
  await first.promise;
  first.release();
  shared.release();
  assert.equal(calls, 1);

  const cached = subscribeTableQuery(scope(WORKSPACE_A), options, runner);
  await cached.promise;
  cached.release();
  assert.equal(calls, 1);
  assert.deepEqual(tableQueryCacheStats(), { active: 0, settled: 1 });

  invalidateTableQueryCache({ workspaceId: WORKSPACE_A, options });
  const refreshed = subscribeTableQuery(scope(WORKSPACE_A), options, runner);
  await refreshed.promise;
  refreshed.release();
  assert.equal(calls, 2);
});

test("switching A to B aborts A in-flight work and never reuses A cache for the same table", async () => {
  resetTableQueryRuntime();
  const options: TableQueryOptions = { table: "orders", mode: "aggregate" };
  let finishWorkspaceA!: (result: TableQueryPayload) => void;
  let callsA = 0;
  let callsB = 0;
  const workspaceA = subscribeTableQuery(scope(WORKSPACE_A), options, async () => {
    callsA += 1;
    return new Promise<TableQueryPayload>((resolve) => { finishWorkspaceA = resolve; });
  });
  await Promise.resolve();

  const workspaceB = subscribeTableQuery(scope(WORKSPACE_B), options, async () => {
    callsB += 1;
    return payload("v-b", "orders", WORKSPACE_B);
  });
  await assert.rejects(workspaceA.promise, (error: unknown) => error instanceof Error && error.name === "AbortError");
  await workspaceB.promise;
  workspaceA.release();
  workspaceB.release();
  finishWorkspaceA(payload("v-a", "orders", WORKSPACE_A));
  await Promise.resolve();

  const cachedB = subscribeTableQuery(scope(WORKSPACE_B), options, async () => {
    callsB += 1;
    return payload("unexpected", "orders", WORKSPACE_B);
  });
  const cachedResult = await cachedB.promise;
  cachedB.release();
  assert.equal(cachedResult.tableQuery.runtime?.replicas?.[0]?.versionId, "v-b");
  assert.equal(callsA, 1);
  assert.equal(callsB, 1);
});

test("a direct A query cannot commit after the UI switches to B without starting another query", () => {
  assert.equal(shouldCommitTableQueryResult({
    requestId: 7,
    currentRequestId: 7,
    expectedWorkspaceId: WORKSPACE_A,
    activeWorkspaceId: WORKSPACE_B,
    aborted: false,
  }), false);
  assert.equal(shouldCommitTableQueryResult({
    requestId: 7,
    currentRequestId: 7,
    expectedWorkspaceId: WORKSPACE_A,
    activeWorkspaceId: WORKSPACE_A,
    aborted: true,
  }), false);
});

test("workspace-mismatched query results fail closed and never enter the settled cache", async () => {
  resetTableQueryRuntime();
  const subscription = subscribeTableQuery(
    scope(WORKSPACE_B),
    { table: "orders", mode: "aggregate" },
    async () => payload("v-a", "orders", WORKSPACE_A),
  );
  await assert.rejects(
    subscription.promise,
    (error: unknown) => error instanceof Error && error.name === "TableQueryWorkspaceMismatchError",
  );
  subscription.release();
  assert.deepEqual(tableQueryCacheStats(), { active: 0, settled: 0 });
});

test("source activation invalidates only its workspace table and dependent views", async () => {
  resetTableQueryRuntime();
  let ordersCalls = 0;
  let customersCalls = 0;
  const ordersOptions: TableQueryOptions = { view: "orders-view", mode: "aggregate" };
  const customersOptions: TableQueryOptions = { table: "customers", mode: "aggregate" };
  const orders = subscribeTableQuery(scope(WORKSPACE_A), ordersOptions, async () => {
    ordersCalls += 1;
    return { ...payload("orders-v1", "orders", WORKSPACE_A), tableQuery: { ...payload("orders-v1", "orders", WORKSPACE_A).tableQuery, viewKey: "orders-view" } };
  });
  const customers = subscribeTableQuery(scope(WORKSPACE_A), customersOptions, async () => {
    customersCalls += 1;
    return payload("customers-v1", "customers", WORKSPACE_A);
  });
  await Promise.all([orders.promise, customers.promise]);
  orders.release();
  customers.release();

  invalidateTableQueryCache({ workspaceId: WORKSPACE_A, table: "orders", views: ["orders-view"] });
  const refreshedOrders = subscribeTableQuery(scope(WORKSPACE_A), ordersOptions, async () => {
    ordersCalls += 1;
    return { ...payload("orders-v2", "orders", WORKSPACE_A), tableQuery: { ...payload("orders-v2", "orders", WORKSPACE_A).tableQuery, viewKey: "orders-view" } };
  });
  const cachedCustomers = subscribeTableQuery(scope(WORKSPACE_A), customersOptions, async () => {
    customersCalls += 1;
    return payload("unexpected", "customers", WORKSPACE_A);
  });
  await Promise.all([refreshedOrders.promise, cachedCustomers.promise]);
  refreshedOrders.release();
  cachedCustomers.release();
  assert.equal(ordersCalls, 2);
  assert.equal(customersCalls, 1);
});

test("a workbench data-version generation change bypasses the five-second settled cache", async () => {
  resetTableQueryRuntime();
  const options: TableQueryOptions = { table: "orders", mode: "aggregate" };
  let calls = 0;
  const first = subscribeTableQuery(scope(WORKSPACE_A, "orders:1"), options, async () => {
    calls += 1;
    return payload("v1");
  });
  await first.promise;
  first.release();
  const second = subscribeTableQuery(scope(WORKSPACE_A, "orders:2"), options, async () => {
    calls += 1;
    return payload("v2");
  });
  const result = await second.promise;
  second.release();
  assert.equal(calls, 2);
  assert.equal(result.tableQuery.runtime?.replicas?.[0]?.versionId, "v2");
});

test("a slow old replica result is rejected after a newer version was already observed", async () => {
  resetTableQueryRuntime();
  let resolveSlow!: (result: TableQueryPayload) => void;
  const slow = subscribeTableQuery(
    scope(WORKSPACE_A, "orders:1"),
    { table: "orders", mode: "aggregate", search: "slow" },
    async () => new Promise<TableQueryPayload>((resolve) => { resolveSlow = resolve; }),
  );
  await Promise.resolve();
  const fast = subscribeTableQuery(
    scope(WORKSPACE_A, "orders:2"),
    { table: "orders", mode: "aggregate", search: "fast" },
    async () => payload("v2"),
  );
  await fast.promise;
  fast.release();
  resolveSlow(payload("v1"));
  await assert.rejects(slow.promise, (error: unknown) => error instanceof Error && error.name === "AbortError");
  slow.release();
});

test("a newly observed replica version evicts older results only for the same workspace table", async () => {
  resetTableQueryRuntime();
  const firstOptions: TableQueryOptions = { table: "orders", mode: "aggregate", search: "first" };
  const secondOptions: TableQueryOptions = { table: "orders", mode: "aggregate", search: "second" };
  const first = subscribeTableQuery(scope(WORKSPACE_A), firstOptions, async () => payload("v1"));
  await first.promise;
  first.release();
  const second = subscribeTableQuery(scope(WORKSPACE_A), secondOptions, async () => payload("v2"));
  await second.promise;
  second.release();
  assert.deepEqual(tableQueryCacheStats(), { active: 0, settled: 1 });
});

test("settled cache remains bounded by its LRU capacity", async () => {
  resetTableQueryRuntime();
  for (let index = 0; index < 70; index += 1) {
    const subscription = subscribeTableQuery(
      scope(WORKSPACE_A),
      { table: `table-${index}`, mode: "aggregate" },
      async () => payload("v1", `table-${index}`),
    );
    await subscription.promise;
    subscription.release();
  }
  assert.deepEqual(tableQueryCacheStats(), { active: 0, settled: 64 });
});
