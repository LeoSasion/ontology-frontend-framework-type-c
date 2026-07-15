import assert from "node:assert/strict";
import test from "node:test";
import type { IncomingMessage, ServerResponse } from "node:http";

import { handleAnalysisUnitApi } from "../server/analysisUnitRoutes";

async function requestAnalysisUnits(result: Record<string, unknown>, query = "") {
  let statusCode = 0;
  let responseBody = "";
  let cliArgs: string[] = [];
  const response = {
    writeHead(status: number) {
      statusCode = status;
      return this;
    },
    end(body?: string) {
      responseBody = String(body ?? "");
      return this;
    },
  } as unknown as ServerResponse;

  const handled = await handleAnalysisUnitApi({
    cli: async (args) => {
      cliArgs = args;
      return result;
    },
    request: { method: "GET" } as IncomingMessage,
    response,
    url: new URL(`http://127.0.0.1/api/analysis-units${query}`),
  });
  return {
    handled,
    statusCode,
    body: JSON.parse(responseBody) as Record<string, unknown>,
    cliArgs,
  };
}

test("stale Analysis Unit collections remain observable with HTTP 200", async () => {
  const result = await requestAnalysisUnits({
    ok: false,
    analysisUnits: [{ unitKey: "stale-unit", status: "blocked" }],
    count: 1,
    usableCount: 0,
    staleCount: 1,
  });

  assert.equal(result.handled, true);
  assert.equal(result.statusCode, 200);
  assert.equal(result.body.staleCount, 1);
  assert.deepEqual(result.body.analysisUnits, [{ unitKey: "stale-unit", status: "blocked" }]);
  assert.deepEqual(result.cliArgs, ["analysis-units", "--limit", "30"]);
});

test("a requested stale Analysis Unit remains a 409 conflict", async () => {
  const result = await requestAnalysisUnits({
    ok: false,
    analysisUnit: { unitKey: "stale-unit", status: "blocked" },
    freshness: { usable: false },
  }, "?unit=stale-unit");

  assert.equal(result.statusCode, 409);
  assert.deepEqual(result.cliArgs, ["analysis-units", "--unit", "stale-unit", "--limit", "30"]);
});

test("an unknown requested Analysis Unit remains a 404", async () => {
  const result = await requestAnalysisUnits({ ok: false, error: "unknown unit" }, "?unit=missing");

  assert.equal(result.statusCode, 404);
});
