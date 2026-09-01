import assert from "node:assert/strict";
import type { IncomingMessage, ServerResponse } from "node:http";
import { Readable } from "node:stream";
import test from "node:test";

import { handleQueryApi } from "../server/queryRoutes";

test("query-table forwards opaque cursors and never dispatches offsets", async () => {
  const request = Readable.from([JSON.stringify({
    workspaceId: "workspace-a",
    table: "orders",
    mode: "detail",
    cursor: "opaque-cursor",
    offset: 1_000_000,
    limit: 50,
  })]) as unknown as IncomingMessage;
  request.method = "POST";
  request.headers = { "content-type": "application/json" };
  let cliArgs: string[] = [];
  let statusCode = 0;
  const response = {
    writeHead(status: number) {
      statusCode = status;
      return this;
    },
    end() {
      return this;
    },
  } as unknown as ServerResponse;

  const handled = await handleQueryApi({
    cli: async (args) => {
      cliArgs = args;
      return {
        ok: true,
        tableQuery: {
          workspaceId: "workspace-a",
          tableKey: "orders",
        },
      };
    },
    request,
    response,
    url: new URL("http://127.0.0.1/api/query-table"),
  });

  assert.equal(handled, true);
  assert.equal(statusCode, 200);
  assert.deepEqual(cliArgs, [
    "query-table",
    "--workspace", "workspace-a",
    "--table", "orders",
    "--mode", "detail",
    "--cursor", "opaque-cursor",
    "--limit", "50",
  ]);
  assert.equal(cliArgs.includes("--offset"), false);
});

test("query-table rejects a result when the active workspace changed during execution", async () => {
  const request = Readable.from([JSON.stringify({ workspaceId: "workspace-a", table: "orders" })]) as unknown as IncomingMessage;
  request.method = "POST";
  request.headers = { "content-type": "application/json" };
  let statusCode = 0;
  let responseBody = "";
  const response = {
    writeHead(status: number) {
      statusCode = status;
      return this;
    },
    end(value?: string) {
      responseBody = value ?? "";
      return this;
    },
  } as unknown as ServerResponse;
  await handleQueryApi({
    cli: async () => ({
      ok: true,
      tableQuery: { workspaceId: "workspace-b", tableKey: "orders" },
    }),
    request,
    response,
    url: new URL("http://127.0.0.1/api/query-table"),
  });
  assert.equal(statusCode, 409);
  assert.match(responseBody, /query-table-workspace-changed/);
});
