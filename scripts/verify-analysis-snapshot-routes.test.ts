import assert from "node:assert/strict";
import { Readable } from "node:stream";
import test from "node:test";
import type { IncomingMessage, ServerResponse } from "node:http";

import { handleAnalysisUnitApi } from "../server/analysisUnitRoutes";

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
  return request;
}

test("Snapshot list is routed as a bounded active-workspace CLI read", async () => {
  const capture = responseCapture();
  let cliArgs: string[] = [];
  const handled = await handleAnalysisUnitApi({
    cli: async (args) => {
      cliArgs = args;
      return { ok: true, analysisSnapshots: [], count: 0 };
    },
    request: { method: "GET" } as IncomingMessage,
    response: capture.response,
    url: new URL("http://127.0.0.1/api/analysis-snapshots?unit=unit-current&status=current&limit=12"),
  });
  assert.equal(handled, true);
  assert.equal(capture.result().statusCode, 200);
  assert.deepEqual(cliArgs, ["analysis-snapshots", "--unit", "unit-current", "--status", "current", "--limit", "12"]);
});

test("Snapshot confirmation forwards the exact preview fingerprint", async () => {
  const capture = responseCapture();
  let cliArgs: string[] = [];
  const handled = await handleAnalysisUnitApi({
    cli: async (args) => {
      cliArgs = args;
      return { ok: true, confirmed: true, changed: true };
    },
    request: jsonRequest({
      snapshotKey: "snapshot-parent",
      unitKey: "unit-current",
      reason: "new source version",
      rowLimit: 80,
      confirm: true,
      expectedPlanFingerprint: "plan-fingerprint",
    }),
    response: capture.response,
    url: new URL("http://127.0.0.1/api/analysis-snapshots/refresh"),
  });
  assert.equal(handled, true);
  assert.equal(capture.result().statusCode, 200);
  assert.deepEqual(cliArgs, [
    "analysis-snapshot-refresh",
    "--snapshot", "snapshot-parent",
    "--unit", "unit-current",
    "--reason", "new source version",
    "--row-limit", "80",
    "--yes", "--expected-plan", "plan-fingerprint",
  ]);
});

test("Snapshot mutations reject incomplete input before CLI dispatch", async () => {
  const capture = responseCapture();
  let called = false;
  const handled = await handleAnalysisUnitApi({
    cli: async () => {
      called = true;
      return { ok: true };
    },
    request: jsonRequest({ unitKey: "unit-current", reason: "missing parent" }),
    response: capture.response,
    url: new URL("http://127.0.0.1/api/analysis-snapshots/replace"),
  });
  assert.equal(handled, true);
  assert.equal(capture.result().statusCode, 400);
  assert.match(String(capture.result().body.error), /snapshot is required/i);
  assert.equal(called, false);
});
