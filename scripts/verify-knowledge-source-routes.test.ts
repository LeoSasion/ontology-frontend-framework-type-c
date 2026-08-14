import assert from "node:assert/strict";
import type { IncomingMessage, ServerResponse } from "node:http";
import { Readable } from "node:stream";
import test from "node:test";

import { handleSettingsApi } from "../server/settingsRoutes";

function request(method: string, body: Record<string, unknown> = {}) {
  const input = Readable.from([JSON.stringify(body)]) as unknown as IncomingMessage;
  input.method = method;
  input.headers = { "content-type": "application/json" };
  return input;
}

function capture() {
  let statusCode = 0;
  let text = "";
  const response = { writeHead(status: number) { statusCode = status; return this; }, end(value?: string) { text = String(value ?? ""); return this; } } as unknown as ServerResponse;
  return { response, result: () => ({ statusCode, body: JSON.parse(text || "{}") as Record<string, unknown> }) };
}

async function invoke(path: string, method: string, body: Record<string, unknown> = {}) {
  const output = capture();
  const calls: string[][] = [];
  const handled = await handleSettingsApi({
    cli: async (args) => { calls.push(args); return { ok: true, requiresConfirmation: !args.includes("--yes") }; },
    request: request(method, body), response: output.response, url: new URL(`http://127.0.0.1${path}`),
  });
  return { handled, calls, ...output.result() };
}

test("knowledge source preview and confirmation use the review proposal path", async () => {
  const body = { input: "C:\\knowledge\\dictionary.json", adapter: "knowledge-json-v1", sourceType: "data-dictionary", sourceName: "Finance dictionary" };
  const preview = await invoke("/api/knowledge-sources/propose", "POST", body);
  assert.equal(preview.statusCode, 202);
  assert.deepEqual(preview.calls[0], ["semantic-patch-propose", "--input", body.input, "--adapter", "knowledge-json-v1", "--source-type", "data-dictionary", "--source-name", "Finance dictionary"]);
  const confirmed = await invoke("/api/knowledge-sources/propose", "POST", { ...body, confirm: true });
  assert.equal(confirmed.calls[0].at(-1), "--yes");
});

test("unsupported adapters and source types fail before CLI", async () => {
  const adapter = await invoke("/api/knowledge-sources/propose", "POST", { input: "file.sql", adapter: "sql", sourceType: "documentation" });
  assert.equal(adapter.statusCode, 400);
  assert.equal(adapter.calls.length, 0);
  const type = await invoke("/api/knowledge-sources/propose", "POST", { input: "file.md", adapter: "auto", sourceType: "code" });
  assert.equal(type.statusCode, 400);
  assert.equal(type.calls.length, 0);
});

test("knowledge source list and adapter catalog are read only", async () => {
  const sources = await invoke("/api/knowledge-sources?limit=50", "GET");
  assert.deepEqual(sources.calls, [["knowledge-sources", "--limit", "50"]]);
  const adapters = await invoke("/api/knowledge-source-adapters", "GET");
  assert.deepEqual(adapters.calls, [["knowledge-source-adapters"]]);
});
