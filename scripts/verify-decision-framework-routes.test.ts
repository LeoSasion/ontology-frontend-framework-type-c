import assert from "node:assert/strict";
import type { IncomingMessage, ServerResponse } from "node:http";
import { Readable } from "node:stream";
import test from "node:test";

import { handleDecisionFrameworkApi } from "../server/decisionFrameworkRoutes";

const FRAMEWORK = "decision_framework_1234567890abcdef1234";

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

function jsonRequest(method: string, value: Record<string, unknown>, idempotencyKey = "") {
  const request = Readable.from([JSON.stringify(value)]) as unknown as IncomingMessage;
  request.method = method;
  request.headers = {
    "content-type": "application/json",
    ...(idempotencyKey ? { "x-idempotency-key": idempotencyKey } : {}),
  };
  return request;
}

test("framework list remains bound to the active workspace and current unit", async () => {
  const capture = responseCapture();
  let cliArgs: string[] = [];
  await handleDecisionFrameworkApi({
    authorize: async () => true,
    cli: async (args) => { cliArgs = args; return { ok: true, decisionFrameworks: [] }; },
    request: { method: "GET", headers: {} } as IncomingMessage,
    response: capture.response,
    url: new URL("http://127.0.0.1/api/decision-frameworks?workspaceId=attacker&unit=unit-current&limit=8"),
  });
  assert.equal(capture.result().statusCode, 200);
  assert.deepEqual(cliArgs, ["decision-frameworks", "--limit", "8", "--unit", "unit-current"]);
});

test("draft creation forwards only the bounded framework contract", async () => {
  const capture = responseCapture();
  let cliArgs: string[] = [];
  await handleDecisionFrameworkApi({
    authorize: async () => true,
    cli: async (args) => { cliArgs = args; return { ok: true, decisionFramework: { frameworkKey: FRAMEWORK } }; },
    request: jsonRequest("POST", {
      unitKey: "unit-current",
      type: "swot",
      title: "Current evidence",
      path: "C:\\forbidden\\source.xlsx",
    }, "decision-request-001"),
    response: capture.response,
    url: new URL("http://127.0.0.1/api/decision-frameworks/create"),
  });
  assert.equal(capture.result().statusCode, 201);
  assert.deepEqual(cliArgs, [
    "decision-framework-create",
    "--unit", "unit-current",
    "--framework-type", "swot",
    "--title", "Current evidence",
    "--request-key", "decision-request-001",
  ]);
  assert.equal(cliArgs.some((item) => item.includes("forbidden")), false);
});

test("draft save forwards claims and optimistic fingerprint without a publish confirmation", async () => {
  const capture = responseCapture();
  let cliArgs: string[] = [];
  const claims = [{ claimKey: "claim-1", category: "strength", text: "fact", claimKind: "evidence_fact", evidenceRefs: [] }];
  await handleDecisionFrameworkApi({
    authorize: async () => true,
    cli: async (args) => { cliArgs = args; return { ok: true, changed: true }; },
    request: jsonRequest("PUT", { title: "Current evidence", claims, expectedContentFingerprint: "a".repeat(64) }),
    response: capture.response,
    url: new URL(`http://127.0.0.1/api/decision-frameworks/${FRAMEWORK}`),
  });
  assert.equal(capture.result().statusCode, 200);
  assert.deepEqual(cliArgs, [
    "decision-framework-save",
    "--framework", FRAMEWORK,
    "--title", "Current evidence",
    "--claims-json", JSON.stringify(claims),
    "--expected-content", "a".repeat(64),
  ]);
  assert.equal(cliArgs.includes("--yes"), false);
});

test("publication preview and confirmation preserve a single exact fingerprint boundary", async () => {
  const previewCapture = responseCapture();
  let previewArgs: string[] = [];
  await handleDecisionFrameworkApi({
    authorize: async () => true,
    cli: async (args) => { previewArgs = args; return { ok: true, requiresConfirmation: true }; },
    request: jsonRequest("POST", {}),
    response: previewCapture.response,
    url: new URL(`http://127.0.0.1/api/decision-frameworks/${FRAMEWORK}/publish`),
  });
  assert.equal(previewCapture.result().statusCode, 202);
  assert.deepEqual(previewArgs, ["decision-framework-publish", "--framework", FRAMEWORK]);

  const confirmCapture = responseCapture();
  let confirmArgs: string[] = [];
  await handleDecisionFrameworkApi({
    authorize: async () => true,
    cli: async (args) => { confirmArgs = args; return { ok: true, confirmed: true }; },
    request: jsonRequest("POST", { confirm: true, expectedPlanFingerprint: "b".repeat(64) }),
    response: confirmCapture.response,
    url: new URL(`http://127.0.0.1/api/decision-frameworks/${FRAMEWORK}/publish`),
  });
  assert.equal(confirmCapture.result().statusCode, 200);
  assert.deepEqual(confirmArgs, [
    "decision-framework-publish",
    "--framework", FRAMEWORK,
    "--yes", "--expected-plan", "b".repeat(64),
  ]);
});

test("invalid framework key and missing confirmation fingerprint fail before dispatch", async () => {
  for (const [url, body] of [
    ["http://127.0.0.1/api/decision-frameworks/%2e%2e%2fescape", {}],
    [`http://127.0.0.1/api/decision-frameworks/${FRAMEWORK}/publish`, { confirm: true }],
  ] as const) {
    const capture = responseCapture();
    let called = false;
    await handleDecisionFrameworkApi({
      authorize: async () => true,
      cli: async () => { called = true; return { ok: true }; },
      request: jsonRequest(body.confirm ? "POST" : "GET", body),
      response: capture.response,
      url: new URL(url),
    });
    assert.equal(called, false);
    assert.equal(capture.result().statusCode, 400);
  }
});
