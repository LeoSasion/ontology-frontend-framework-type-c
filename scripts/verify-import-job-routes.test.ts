import assert from "node:assert/strict";
import type { IncomingMessage, ServerResponse } from "node:http";
import { Readable } from "node:stream";
import test from "node:test";

import { handleImportJobApi } from "../server/importJobRoutes";

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

function request(method = "GET") {
  const incoming = Readable.from([]) as unknown as IncomingMessage;
  incoming.method = method;
  incoming.headers = {};
  return incoming;
}

test("malformed and invalid import job paths fail closed before CLI dispatch", async () => {
  for (const pathname of ["/api/import/jobs/%", "/api/import/jobs/job_not-a-durable-key"]) {
    const capture = responseCapture();
    let called = false;
    const handled = await handleImportJobApi({
      authorize: async () => true,
      cli: async () => { called = true; return { ok: true }; },
      request: request(),
      response: capture.response,
      url: new URL(`http://127.0.0.1${pathname}`),
    });
    assert.equal(handled, true);
    assert.equal(called, false);
    assert.equal(capture.result().statusCode, 400);
    assert.equal(capture.result().body.code, "IMPORT_JOB_KEY_INVALID");
  }
});

test("a valid durable import job key reaches the read command", async () => {
  const capture = responseCapture();
  const calls: string[][] = [];
  const jobKey = `job_${"a".repeat(20)}`;
  const handled = await handleImportJobApi({
    authorize: async () => true,
    cli: async (args) => { calls.push(args); return { ok: true, job: { jobKey } }; },
    request: request(),
    response: capture.response,
    url: new URL(`http://127.0.0.1/api/import/jobs/${jobKey}`),
  });
  assert.equal(handled, true);
  assert.deepEqual(calls, [["jobs", "--job", jobKey, "--event-limit", "200"]]);
  assert.equal(capture.result().statusCode, 200);
});
