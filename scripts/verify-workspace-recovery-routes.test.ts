import assert from "node:assert/strict";
import type { IncomingMessage, ServerResponse } from "node:http";
import { Readable } from "node:stream";
import test from "node:test";

import { handleWorkspaceRecoveryApi } from "../server/workspaceRecoveryRoutes";

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

function jsonRequest(value: Record<string, unknown>, idempotencyKey = "") {
  const request = Readable.from([JSON.stringify(value)]) as unknown as IncomingMessage;
  request.method = "POST";
  request.headers = {
    "content-type": "application/json",
    ...(idempotencyKey ? { "x-idempotency-key": idempotencyKey } : {}),
  };
  return request;
}

test("Recovery list is bounded and workspace-scoped", async () => {
  const capture = responseCapture();
  let cliArgs: string[] = [];
  const handled = await handleWorkspaceRecoveryApi({
    authorize: async () => true,
    cli: async (args) => {
      cliArgs = args;
      return { ok: true, workspaceId: "workspace-a", recoveryPoints: [] };
    },
    request: { method: "GET", headers: {} } as IncomingMessage,
    response: capture.response,
    url: new URL("http://127.0.0.1/api/workspace-recovery?workspaceId=attacker&limit=8&verify=true"),
  });
  assert.equal(handled, true);
  assert.equal(capture.result().statusCode, 200);
  assert.deepEqual(cliArgs, ["workspace-recovery-list", "--limit", "8", "--verify"]);
});

test("Recovery inspect rejects path traversal before CLI dispatch", async () => {
  const capture = responseCapture();
  let called = false;
  const handled = await handleWorkspaceRecoveryApi({
    authorize: async () => true,
    cli: async () => {
      called = true;
      return { ok: true };
    },
    request: { method: "GET", headers: {} } as IncomingMessage,
    response: capture.response,
    url: new URL("http://127.0.0.1/api/workspace-recovery/%2e%2e%2fescape?workspaceId=workspace-a"),
  });
  assert.equal(handled, true);
  assert.equal(called, false);
  assert.equal(capture.result().statusCode, 400);
  assert.equal(capture.result().body.code, "RECOVERY_POINT_KEY_INVALID");
});

test("Recovery comparison is read-only and precedes generic inspect routing", async () => {
  const capture = responseCapture();
  let cliArgs: string[] = [];
  const handled = await handleWorkspaceRecoveryApi({
    authorize: async (capability) => capability === "workspace-recovery:read",
    cli: async (args) => { cliArgs = args; return { ok: true, schema: "aibi-workspace-recovery-comparison/v1", exposesBusinessRows: false }; },
    request: { method: "GET", headers: {} } as IncomingMessage,
    response: capture.response,
    url: new URL("http://127.0.0.1/api/workspace-recovery/rp_1234567890abcdef12345678/compare"),
  });
  assert.equal(handled, true);
  assert.equal(capture.result().statusCode, 200);
  assert.deepEqual(cliArgs, ["workspace-recovery-compare", "--recovery-point", "rp_1234567890abcdef12345678"]);
});

test("Recovery create preview forwards only bounded contract fields", async () => {
  const capture = responseCapture();
  let cliArgs: string[] = [];
  const handled = await handleWorkspaceRecoveryApi({
    authorize: async () => true,
    cli: async (args) => {
      cliArgs = args;
      return { ok: true, dryRun: true, requiresConfirmation: true, workspaceId: "workspace-a" };
    },
    request: jsonRequest({
      workspaceId: "workspace-a",
      reason: "Before replacement",
      path: "C:\\forbidden\\arbitrary-path",
    }, "request-create-1"),
    response: capture.response,
    url: new URL("http://127.0.0.1/api/workspace-recovery/create"),
  });
  assert.equal(handled, true);
  assert.equal(capture.result().statusCode, 202);
  assert.deepEqual(cliArgs, [
    "workspace-recovery-create",
    "--reason", "Before replacement",
    "--request-key", "request-create-1",
  ]);
  assert.equal(cliArgs.some((item) => item.includes("forbidden")), false);
});

test("Recovery restore confirmation forwards the exact preview fingerprint", async () => {
  const capture = responseCapture();
  let cliArgs: string[] = [];
  const fingerprint = "a".repeat(64);
  const handled = await handleWorkspaceRecoveryApi({
    authorize: async () => true,
    cli: async (args) => {
      cliArgs = args;
      return { ok: true, confirmed: true, workspaceId: "workspace-a" };
    },
    request: jsonRequest({
      workspaceId: "workspace-a",
      recoveryPointKey: "rp_1234567890abcdef12345678",
      requestKey: "restore-1",
      confirm: true,
      expectedPlanFingerprint: fingerprint,
    }),
    response: capture.response,
    url: new URL("http://127.0.0.1/api/workspace-recovery/restore"),
  });
  assert.equal(handled, true);
  assert.equal(capture.result().statusCode, 200);
  assert.deepEqual(cliArgs, [
    "workspace-recovery-restore",
    "--recovery-point", "rp_1234567890abcdef12345678",
    "--request-key", "restore-1",
    "--yes", "--expected-plan", fingerprint,
  ]);
});

test("Confirmed recovery mutation without a plan fingerprint is rejected", async () => {
  const capture = responseCapture();
  let called = false;
  const handled = await handleWorkspaceRecoveryApi({
    authorize: async () => true,
    cli: async () => {
      called = true;
      return { ok: true };
    },
    request: jsonRequest({
      workspaceId: "workspace-a",
      recoveryPointKey: "rp_1234567890abcdef12345678",
      requestKey: "delete-1",
      confirm: true,
    }),
    response: capture.response,
    url: new URL("http://127.0.0.1/api/workspace-recovery/delete"),
  });
  assert.equal(handled, true);
  assert.equal(called, false);
  assert.equal(capture.result().statusCode, 400);
  assert.equal(capture.result().body.code, "RECOVERY_PLAN_REQUIRED");
});

test("Mutation requires an idempotency key", async () => {
  const capture = responseCapture();
  let called = false;
  await handleWorkspaceRecoveryApi({
    authorize: async () => true,
    cli: async () => {
      called = true;
      return { ok: true };
    },
    request: jsonRequest({ workspaceId: "workspace-a", reason: "test" }),
    response: capture.response,
    url: new URL("http://127.0.0.1/api/workspace-recovery/create"),
  });
  assert.equal(called, false);
  assert.equal(capture.result().statusCode, 400);
  assert.equal(capture.result().body.code, "RECOVERY_REQUEST_KEY_REQUIRED");
});
