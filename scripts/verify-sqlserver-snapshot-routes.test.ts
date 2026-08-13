import assert from "node:assert/strict";
import type { IncomingMessage, ServerResponse } from "node:http";
import { Readable } from "node:stream";
import test from "node:test";

import { handleSqlServerSnapshotApi, type SqlServerSnapshotCapability } from "../server/sqlServerSnapshotRoutes";

function responseCapture() {
  let statusCode = 0;
  let body = "";
  const response = {
    writeHead(status: number) {
      statusCode = status;
      return this;
    },
    end(value?: string) {
      body = String(value ?? "");
      return this;
    },
  } as unknown as ServerResponse;
  return { response, result: () => ({ statusCode, body: JSON.parse(body || "{}") as Record<string, unknown> }) };
}

function request(method: string, value: Record<string, unknown> | string = {}, idempotencyKey = "") {
  const content = typeof value === "string" ? value : JSON.stringify(value);
  const input = Readable.from([content]) as unknown as IncomingMessage;
  input.method = method;
  input.headers = {
    "content-type": "application/json",
    ...(idempotencyKey ? { "x-idempotency-key": idempotencyKey } : {}),
  };
  return input;
}

function allowAll(seen: SqlServerSnapshotCapability[] = []) {
  return async (capability: SqlServerSnapshotCapability) => {
    seen.push(capability);
    return true;
  };
}

test("probe is authorized and accepts only a bounded connector key", async () => {
  const capture = responseCapture();
  const capabilities: SqlServerSnapshotCapability[] = [];
  let cliArgs: string[] = [];
  const handled = await handleSqlServerSnapshotApi({
    cli: async (args) => {
      cliArgs = args;
      return { ok: true, capability: "unavailable" };
    },
    authorize: allowAll(capabilities),
    request: request("GET"),
    response: capture.response,
    url: new URL("http://127.0.0.1/api/connectors/sqlserver/probe?connector=finance_readonly"),
  });
  assert.equal(handled, true);
  assert.equal(capture.result().statusCode, 200);
  assert.deepEqual(capabilities, ["connector:sqlserver:read"]);
  assert.deepEqual(cliArgs, ["sqlserver-adapter-probe", "--connector", "finance_readonly"]);
});

test("capability denial happens before a malformed body is parsed", async () => {
  const capture = responseCapture();
  let cliCalled = false;
  const handled = await handleSqlServerSnapshotApi({
    cli: async () => {
      cliCalled = true;
      return { ok: true };
    },
    authorize: async () => false,
    request: request("POST", "{not-json"),
    response: capture.response,
    url: new URL("http://127.0.0.1/api/connectors/sqlserver/snapshot"),
  });
  assert.equal(handled, true);
  assert.equal(cliCalled, false);
  assert.equal(capture.result().statusCode, 403);
  assert.equal(capture.result().body.code, "SQLSERVER_CAPABILITY_DENIED");
});

test("arbitrary SQL and credential material are rejected before CLI dispatch", async () => {
  for (const forbidden of [
    { sql: "SELECT * FROM private_rows" },
    { nested: { query: "DROP TABLE anything" } },
    { credentialRef: "env:SHOULD_STAY_SERVER_SIDE" },
    { connectionString: "Server=unsafe" },
  ]) {
    const capture = responseCapture();
    let cliCalled = false;
    await handleSqlServerSnapshotApi({
      cli: async () => {
        cliCalled = true;
        return { ok: true };
      },
      authorize: allowAll(),
      request: request("POST", { connectorKey: "finance_readonly", ...forbidden }),
      response: capture.response,
      url: new URL("http://127.0.0.1/api/connectors/sqlserver/test"),
    });
    assert.equal(cliCalled, false);
    assert.equal(capture.result().statusCode, 400);
    assert.equal(capture.result().body.code, "SQLSERVER_FORBIDDEN_INPUT_SURFACE");
  }
});

test("plan forwards only bounded reviewed structures and request identity", async () => {
  const capture = responseCapture();
  let cliArgs: string[] = [];
  const fingerprint = "a".repeat(64);
  const selections = [{
    resourceKey: "dbo.orders",
    columns: ["order_id"],
    orderBy: ["order_id"],
    targetTableKey: "sql_orders",
  }];
  const handled = await handleSqlServerSnapshotApi({
    cli: async (args) => {
      cliArgs = args;
      return { ok: true, requiresConfirmation: true };
    },
    authorize: allowAll(),
    request: request("POST", {
      connectorKey: "finance_readonly",
      catalogFingerprint: fingerprint,
      selections,
      budget: { maxRowsPerTable: 100 },
    }, "snapshot-plan-1"),
    response: capture.response,
    url: new URL("http://127.0.0.1/api/connectors/sqlserver/plan"),
  });
  assert.equal(handled, true);
  assert.equal(capture.result().statusCode, 202);
  assert.deepEqual(cliArgs, [
    "sqlserver-adapter-plan",
    "--connector", "finance_readonly",
    "--request-key", "snapshot-plan-1",
    "--catalog", fingerprint,
    "--selections-json", JSON.stringify(selections),
    "--budget-json", JSON.stringify({ maxRowsPerTable: 100 }),
  ]);
});

test("snapshot requires exact reviewed fingerprint and explicit confirmation", async () => {
  const rejected = responseCapture();
  let rejectedCli = false;
  await handleSqlServerSnapshotApi({
    cli: async () => {
      rejectedCli = true;
      return { ok: true };
    },
    authorize: allowAll(),
    request: request("POST", { connectorKey: "finance_readonly", confirm: true }, "snapshot-run-1"),
    response: rejected.response,
    url: new URL("http://127.0.0.1/api/connectors/sqlserver/snapshot"),
  });
  assert.equal(rejectedCli, false);
  assert.equal(rejected.result().statusCode, 400);
  assert.equal(rejected.result().body.code, "SQLSERVER_SNAPSHOT_CONFIRMATION_REQUIRED");

  const accepted = responseCapture();
  const fingerprint = "b".repeat(64);
  let acceptedArgs: string[] = [];
  await handleSqlServerSnapshotApi({
    cli: async (args) => {
      acceptedArgs = args;
      return { ok: true, jobKey: "job_sqlserver" };
    },
    authorize: allowAll(),
    request: request("POST", {
      connectorKey: "finance_readonly",
      requestKey: "snapshot-run-1",
      confirm: true,
      expectedPlanFingerprint: fingerprint,
    }),
    response: accepted.response,
    url: new URL("http://127.0.0.1/api/connectors/sqlserver/snapshot"),
  });
  assert.equal(accepted.result().statusCode, 200);
  assert.deepEqual(acceptedArgs, [
    "sqlserver-adapter-snapshot",
    "--connector", "finance_readonly",
    "--request-key", "snapshot-run-1",
    "--expected-plan", fingerprint,
    "--yes",
  ]);
});

test("activation queues the sealed artifact through the durable runtime", async () => {
  const capture = responseCapture();
  const capabilities: SqlServerSnapshotCapability[] = [];
  const fingerprint = "c".repeat(64);
  const manifest = "d".repeat(64);
  let activationBody: Record<string, unknown> | null = null;
  const handled = await handleSqlServerSnapshotApi({
    cli: async () => ({ ok: true }),
    startActivationJob: async (body) => {
      activationBody = body;
      return {
        ok: true,
        job: { jobKey: "job_sqlserver_activation", workspaceId: "default", status: "queued" },
      };
    },
    authorize: allowAll(capabilities),
    request: request("POST", {
      connectorKey: "finance_readonly",
      workspaceId: "default",
      requestKey: "sqlserver-activation-1",
      expectedPlanFingerprint: fingerprint,
      expectedManifestFingerprint: manifest,
      confirm: true,
    }),
    response: capture.response,
    url: new URL("http://127.0.0.1/api/connectors/sqlserver/activate"),
  });
  assert.equal(handled, true);
  assert.equal(capture.result().statusCode, 202);
  assert.deepEqual(capabilities, ["connector:sqlserver:activate"]);
  assert.deepEqual(activationBody, {
    connectorKey: "finance_readonly",
    workspaceId: "default",
    requestKey: "sqlserver-activation-1",
    expectedPlanFingerprint: fingerprint,
    expectedManifestFingerprint: manifest,
  });
});

test("activation status verifies the exact workspace plan manifest and request binding", async () => {
  const capture = responseCapture();
  const capabilities: SqlServerSnapshotCapability[] = [];
  const plan = "e".repeat(64);
  const manifest = "f".repeat(64);
  let cliArgs: string[] = [];
  const handled = await handleSqlServerSnapshotApi({
    cli: async (args) => {
      cliArgs = args;
      return { ok: true, capability: "active", activation: { status: "committed", phase: "finalized" } };
    },
    authorize: allowAll(capabilities),
    request: request("GET"),
    response: capture.response,
    url: new URL(`http://127.0.0.1/api/connectors/sqlserver/activation-status?connector=finance_readonly&workspace=default&requestKey=sqlserver-activation-1&expectedPlan=${plan}&expectedManifest=${manifest}`),
  });
  assert.equal(handled, true);
  assert.equal(capture.result().statusCode, 200);
  assert.deepEqual(capabilities, ["connector:sqlserver:read"]);
  assert.deepEqual(cliArgs, [
    "sqlserver-adapter-activation-status",
    "--connector", "finance_readonly",
    "--workspace", "default",
    "--request-key", "sqlserver-activation-1",
    "--expected-plan", plan,
    "--expected-manifest", manifest,
  ]);
});

test("unknown SQL Server namespace paths are not consumed", async () => {
  const capture = responseCapture();
  const handled = await handleSqlServerSnapshotApi({
    cli: async () => ({ ok: true }),
    authorize: allowAll(),
    request: request("POST", {}),
    response: capture.response,
    url: new URL("http://127.0.0.1/api/connectors/sqlserver/unknown"),
  });
  assert.equal(handled, false);
});
