import assert from "node:assert/strict";
import type { IncomingMessage, ServerResponse } from "node:http";
import { Readable } from "node:stream";
import test from "node:test";

import { handleModelApi } from "../server/modelRoutes";

const METRIC = "sales_metric";
const CONTRACT = "metric_contract_1234567890abcdef1234";
const PLAN = "a".repeat(64);

function request(method: string, body: Record<string, unknown> = {}) {
  const value = Readable.from([JSON.stringify(body)]) as unknown as IncomingMessage;
  value.method = method;
  value.headers = { "content-type": "application/json" };
  return value;
}

function capture() {
  let statusCode = 0;
  let body = "";
  const response = { writeHead(status: number) { statusCode = status; return this; }, end(value?: string) { body = String(value ?? ""); return this; } } as unknown as ServerResponse;
  return { response, result: () => ({ statusCode, body: JSON.parse(body || "{}") as Record<string, unknown> }) };
}

async function invoke(path: string, method: string, body: Record<string, unknown> = {}) {
  const result = capture();
  const calls: string[][] = [];
  const handled = await handleModelApi({
    cli: async (args) => { calls.push(args); return { ok: true }; },
    request: request(method, body),
    response: result.response,
    url: new URL(`http://127.0.0.1${path}`),
  });
  return { handled, calls, ...result.result() };
}

test("contract list and replay are bounded read paths", async () => {
  const list = await invoke(`/api/metric-contracts?metric=${METRIC}&limit=999`, "GET");
  assert.deepEqual(list.calls, [["metric-contracts", "--limit", "100", "--metric", METRIC]]);
  const replay = await invoke(`/api/metric-contracts/replay?contract=${CONTRACT}`, "GET");
  assert.deepEqual(replay.calls, [["metric-contract-replay", "--contract", CONTRACT]]);
});

test("preview serializes bounded scenario input", async () => {
  const scenario = { name: "All", groups: ["month"], filters: [], limit: 50 };
  const result = await invoke("/api/metric-contracts/preview", "POST", { metric: METRIC, requestKey: "contract-route", population: "Paid", scenarios: [scenario] });
  assert.deepEqual(result.calls, [["metric-contract-preview", "--metric", METRIC, "--request-key", "contract-route", "--population", "Paid", "--scenario-json", JSON.stringify(scenario)]]);
});

test("publish requires exact preview fingerprint", async () => {
  const rejected = await invoke("/api/metric-contracts/publish", "POST", { metric: METRIC, requestKey: "contract-route", confirm: true });
  assert.equal(rejected.statusCode, 400);
  assert.equal(rejected.calls.length, 0);
  const accepted = await invoke("/api/metric-contracts/publish", "POST", { metric: METRIC, requestKey: "contract-route", expectedPlanFingerprint: PLAN, confirm: true });
  assert.deepEqual(accepted.calls, [["metric-contract-publish", "--metric", METRIC, "--request-key", "contract-route", "--expected-plan", PLAN, "--yes"]]);
});

test("invalid contract keys and oversized scenarios fail before CLI", async () => {
  const invalid = await invoke("/api/metric-contracts/replay?contract=../escape", "GET");
  assert.equal(invalid.statusCode, 400);
  assert.equal(invalid.calls.length, 0);
  const oversized = await invoke("/api/metric-contracts/preview", "POST", { metric: METRIC, requestKey: "contract-route", scenarios: Array.from({ length: 13 }, (_, index) => ({ name: String(index) })) });
  assert.equal(oversized.statusCode, 400);
  assert.equal(oversized.calls.length, 0);
});
