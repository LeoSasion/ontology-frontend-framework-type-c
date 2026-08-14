import assert from "node:assert/strict";
import type { IncomingMessage, ServerResponse } from "node:http";
import { Readable } from "node:stream";
import test from "node:test";

import { handleExportApi } from "../server/exportRoutes";

function request(body: Record<string, unknown>) {
  const input = Readable.from([JSON.stringify(body)]) as unknown as IncomingMessage;
  input.method = "POST";
  input.headers = { "content-type": "application/json" };
  return input;
}

function capture() {
  let statusCode = 0;
  let text = "";
  const response = { writeHead(status: number) { statusCode = status; return this; }, end(value?: string) { text = String(value ?? ""); return this; } } as unknown as ServerResponse;
  return { response, result: () => ({ statusCode, body: JSON.parse(text || "{}") }) };
}

async function invoke(body: Record<string, unknown>) {
  const output = capture();
  const calls: string[][] = [];
  await handleExportApi({ cli: async (args) => { calls.push(args); return { ok: true }; }, request: request(body), response: output.response, url: new URL("http://127.0.0.1/api/exports/analysis") });
  return { calls, ...output.result() };
}

test("analysis export forwards bounded native office formats", async () => {
  const result = await invoke({ receipt: "receipt-a", unit: "unit-a", formats: ["docx", "pptx"] });
  assert.equal(result.statusCode, 200);
  assert.deepEqual(result.calls, [["export-analysis", "--receipt", "receipt-a", "--unit", "unit-a", "--format", "docx", "--format", "pptx"]]);
});

test("analysis export rejects unknown and excessive formats before CLI", async () => {
  const unknown = await invoke({ receipt: "receipt-a", unit: "unit-a", formats: ["pdf"] });
  assert.equal(unknown.statusCode, 400);
  assert.equal(unknown.calls.length, 0);
  const excessive = await invoke({ receipt: "receipt-a", unit: "unit-a", formats: ["xlsx", "docx", "pptx", "md", "xlsx"] });
  assert.equal(excessive.statusCode, 400);
  assert.equal(excessive.calls.length, 0);
});
