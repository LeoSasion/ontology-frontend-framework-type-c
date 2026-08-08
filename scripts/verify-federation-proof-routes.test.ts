import assert from "node:assert/strict";
import type { IncomingMessage, ServerResponse } from "node:http";
import { Readable } from "node:stream";
import test from "node:test";

import { handleSourceApi } from "../server/sourceRoutes";

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

test("federation proof route forwards only declarative bounded inputs", async () => {
  const capture = responseCapture();
  let cliArgs: string[] = [];
  const handled = await handleSourceApi({
    cli: async (args) => { cliArgs = args; return { ok: true, status: "provable" }; },
    request: jsonRequest({
      connectors: ["source-a", "source-b"],
      projections: { "source-a": ["id"], "source-b": ["id", "value"] },
      relationships: ["relation-ab"],
      grain: "entity",
      entityKey: "source_a.id",
      filters: [{ connectorKey: "source-b", field: "value", operator: "gte" }],
      budget: { maxSources: 2, maxProjectedFields: 8, maxRelationships: 1, maxFilters: 1 },
      workspaceId: "must-not-be-forwarded",
      sql: "select * from forbidden",
    }),
    response: capture.response,
    url: new URL("http://127.0.0.1/api/connectors/federation-proof"),
  });
  assert.equal(handled, true);
  assert.equal(capture.result().statusCode, 200);
  assert.deepEqual(cliArgs, [
    "federation-proof",
    "--connectors", "source-a,source-b",
    "--projections", JSON.stringify({ "source-a": ["id"], "source-b": ["id", "value"] }),
    "--relationships", "relation-ab",
    "--grain", "entity",
    "--entity-key", "source_a.id",
    "--filters", JSON.stringify([{ connectorKey: "source-b", field: "value", operator: "gte" }]),
    "--max-sources", "2",
    "--max-fields", "8",
    "--max-relationships", "1",
    "--max-filters", "1",
  ]);
  assert.equal(cliArgs.includes("--workspace"), false);
  assert.equal(cliArgs.some((item) => item.includes("select *")), false);
});
