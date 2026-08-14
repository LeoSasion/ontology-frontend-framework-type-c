import assert from "node:assert/strict";
import type { IncomingMessage, ServerResponse } from "node:http";
import { Readable } from "node:stream";
import test from "node:test";

import { handleSettingsApi } from "../server/settingsRoutes";

const PATCH = "patch_1234567890abcdef1234";
const RELEASE = "release_1234567890abcdef1234";
const PLAN = "a".repeat(64);

function request(method: string, body: Record<string, unknown> = {}) {
  const input = Readable.from([JSON.stringify(body)]) as unknown as IncomingMessage;
  input.method = method;
  input.headers = { "content-type": "application/json" };
  return input;
}

function capture() {
  let statusCode = 0;
  let body = "";
  const response = {
    writeHead(status: number) { statusCode = status; return this; },
    end(value?: string) { body = String(value ?? ""); return this; },
  } as unknown as ServerResponse;
  return { response, result: () => ({ statusCode, body: JSON.parse(body || "{}") as Record<string, unknown> }) };
}

async function invoke(path: string, method: string, body: Record<string, unknown> = {}) {
  const result = capture();
  const calls: string[][] = [];
  const handled = await handleSettingsApi({
    cli: async (args) => { calls.push(args); return { ok: true, releasePlan: { planFingerprint: PLAN } }; },
    request: request(method, body),
    response: result.response,
    url: new URL(`http://127.0.0.1${path}`),
  });
  return { handled, calls, ...result.result() };
}

test("release list stays bounded and read-only", async () => {
  const result = await invoke("/api/semantic-releases?limit=999", "GET");
  assert.equal(result.handled, true);
  assert.deepEqual(result.calls, [["semantic-releases", "--limit", "100"]]);
  assert.equal(result.statusCode, 200);
});

test("publish requires exact preview binding", async () => {
  const rejected = await invoke("/api/semantic-releases/publish", "POST", { requestKey: "release-route", proposalKeys: [PATCH], confirm: true });
  assert.equal(rejected.statusCode, 400);
  assert.equal(rejected.calls.length, 0);

  const accepted = await invoke("/api/semantic-releases/publish", "POST", { requestKey: "release-route", label: "Release", proposalKeys: [PATCH], expectedPlanFingerprint: PLAN, confirm: true });
  assert.deepEqual(accepted.calls, [["semantic-release-publish", "--request-key", "release-route", "--label", "Release", "--expected-plan", PLAN, "--yes", "--proposal", PATCH]]);
});

test("rollback is a preview-confirm pair", async () => {
  const preview = await invoke("/api/semantic-releases/rollback", "POST", { requestKey: "rollback-route", releaseKey: RELEASE });
  assert.deepEqual(preview.calls, [["semantic-release-rollback", "--release", RELEASE, "--request-key", "rollback-route"]]);

  const confirm = await invoke("/api/semantic-releases/rollback", "POST", { requestKey: "rollback-route", releaseKey: RELEASE, expectedPlanFingerprint: PLAN, confirm: true });
  assert.deepEqual(confirm.calls, [["semantic-release-rollback", "--release", RELEASE, "--request-key", "rollback-route", "--expected-plan", PLAN, "--yes"]]);
});

test("invalid proposal and release keys fail before CLI", async () => {
  const preview = await invoke("/api/semantic-releases/preview", "POST", { requestKey: "release-route", proposalKeys: ["../escape"] });
  assert.equal(preview.statusCode, 400);
  assert.equal(preview.calls.length, 0);

  const rollback = await invoke("/api/semantic-releases/rollback", "POST", { requestKey: "rollback-route", releaseKey: "%" });
  assert.equal(rollback.statusCode, 400);
  assert.equal(rollback.calls.length, 0);
});
