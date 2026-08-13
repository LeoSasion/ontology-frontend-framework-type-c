import assert from "node:assert/strict";
import type { IncomingMessage, ServerResponse } from "node:http";
import { Readable } from "node:stream";
import test from "node:test";

import { handleWorkspaceApi } from "../server/workspaceRoutes";

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

function jsonRequest(value: Record<string, unknown>) {
  const request = Readable.from([JSON.stringify(value)]) as unknown as IncomingMessage;
  request.method = "POST";
  request.headers = { "content-type": "application/json" };
  return request;
}

test("confirmed workspace deletion requires both preview bindings before CLI dispatch", async () => {
  for (const body of [
    { op: "delete", workspaceId: "workspace-a", confirm: true, expectedPlan: "a".repeat(64) },
    { op: "delete", workspaceId: "workspace-a", confirm: true, requestKey: "delete-workspace-a" },
  ]) {
    const capture = responseCapture();
    let called = false;
    const handled = await handleWorkspaceApi({
      cli: async () => { called = true; return { ok: true }; },
      port: 8787,
      request: jsonRequest(body),
      response: capture.response,
      url: new URL("http://127.0.0.1/api/workspaces"),
    });
    assert.equal(handled, true);
    assert.equal(called, false);
    assert.equal(capture.result().statusCode, 400);
    assert.equal(capture.result().body.code, "WORKSPACE_DELETE_CONFIRMATION_REQUIRED");
  }
});

test("confirmed workspace deletion forwards the exact request and plan bindings", async () => {
  const capture = responseCapture();
  const calls: string[][] = [];
  const fingerprint = "b".repeat(64);
  await handleWorkspaceApi({
    cli: async (args) => { calls.push(args); return { ok: true, confirmed: true }; },
    port: 8787,
    request: jsonRequest({
      op: "delete",
      workspaceId: "workspace-a",
      confirm: true,
      requestKey: "delete-workspace-a",
      expectedPlan: fingerprint,
    }),
    response: capture.response,
    url: new URL("http://127.0.0.1/api/workspaces"),
  });
  assert.deepEqual(calls, [[
    "workspace-delete",
    "workspace-a",
    "--request-key",
    "delete-workspace-a",
    "--expected-plan",
    fingerprint,
    "--yes",
  ]]);
  assert.equal(capture.result().statusCode, 200);
});
