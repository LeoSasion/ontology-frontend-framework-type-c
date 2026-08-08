import assert from "node:assert/strict";
import type { IncomingMessage, ServerResponse } from "node:http";
import { Readable } from "node:stream";
import test from "node:test";

import { handleAnalysisUnitApi } from "../server/analysisUnitRoutes";

function responseCapture() {
  let statusCode = 0;
  let body = "";
  const response = {
    writeHead(status: number) { statusCode = status; return this; },
    end(value?: string) { body = String(value ?? ""); return this; },
  } as unknown as ServerResponse;
  return { response, result: () => ({ statusCode, body: JSON.parse(body || "{}") as Record<string, unknown> }) };
}

function jsonRequest(value: Record<string, unknown>) {
  const request = Readable.from([JSON.stringify(value)]) as unknown as IncomingMessage;
  request.method = "POST";
  request.headers = { "content-type": "application/json" };
  return request;
}

test("Metric Monitor list is a bounded active-workspace CLI read", async () => {
  const capture = responseCapture();
  let cliArgs: string[] = [];
  const handled = await handleAnalysisUnitApi({
    cli: async (args) => { cliArgs = args; return { ok: true, metricMonitors: [], count: 0 }; },
    request: { method: "GET" } as IncomingMessage,
    response: capture.response,
    url: new URL("http://127.0.0.1/api/metric-monitors?status=active&limit=12"),
  });
  assert.equal(handled, true);
  assert.equal(capture.result().statusCode, 200);
  assert.deepEqual(cliArgs, ["metric-monitors", "--status", "active", "--limit", "12"]);
});

test("Metric Monitor definition confirmation forwards explicit policy and exact fingerprint", async () => {
  const capture = responseCapture();
  let cliArgs: string[] = [];
  await handleAnalysisUnitApi({
    cli: async (args) => { cliArgs = args; return { ok: true, confirmed: true }; },
    request: jsonRequest({
      snapshotKey: "snapshot-current",
      label: "Revenue watch",
      metric: "revenue",
      cadence: "weekly",
      comparisonStrategy: "percent-change",
      direction: "decrease",
      threshold: 12.5,
      warningRatio: 0.75,
      confirm: true,
      expectedPlanFingerprint: "exact-plan",
    }),
    response: capture.response,
    url: new URL("http://127.0.0.1/api/metric-monitors/create"),
  });
  assert.equal(capture.result().statusCode, 200);
  assert.deepEqual(cliArgs, [
    "metric-monitor-create",
    "--snapshot", "snapshot-current",
    "--label", "Revenue watch",
    "--metric", "revenue",
    "--cadence", "weekly",
    "--strategy", "percent-change",
    "--direction", "decrease",
    "--warning-ratio", "0.75",
    "--threshold", "12.5",
    "--yes", "--expected-plan", "exact-plan",
  ]);
});

test("Metric Monitor run remains manual and has no implicit confirmation or schedule", async () => {
  const capture = responseCapture();
  let cliArgs: string[] = [];
  await handleAnalysisUnitApi({
    cli: async (args) => { cliArgs = args; return { ok: true, writesEvidence: true, writesBusinessState: false }; },
    request: jsonRequest({ monitorKey: "monitor-1", snapshotKey: "snapshot-2", confirm: true, expectedPlanFingerprint: "ignored" }),
    response: capture.response,
    url: new URL("http://127.0.0.1/api/metric-monitors/run"),
  });
  assert.equal(capture.result().statusCode, 200);
  assert.deepEqual(cliArgs, ["metric-monitor-run", "--monitor", "monitor-1", "--snapshot", "snapshot-2"]);
});

test("Metric Monitor mutations reject incomplete definitions before CLI dispatch", async () => {
  const capture = responseCapture();
  let called = false;
  await handleAnalysisUnitApi({
    cli: async () => { called = true; return { ok: true }; },
    request: jsonRequest({ snapshotKey: "snapshot-current" }),
    response: capture.response,
    url: new URL("http://127.0.0.1/api/metric-monitors/create"),
  });
  assert.equal(capture.result().statusCode, 400);
  assert.match(String(capture.result().body.error), /snapshot and label are required/i);
  assert.equal(called, false);
});
