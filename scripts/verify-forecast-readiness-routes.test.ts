import assert from "node:assert/strict";
import test from "node:test";
import type { IncomingMessage, ServerResponse } from "node:http";

import { handleAnalysisUnitApi } from "../server/analysisUnitRoutes";

async function requestForecastReadiness(query: string, result: Record<string, unknown>) {
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
    url: new URL(`http://127.0.0.1/api/forecast-readiness${query}`),
  });
  return {
    handled,
    statusCode,
    body: JSON.parse(responseBody) as Record<string, unknown>,
    cliArgs,
  };
}

test("a valid blocked readiness assessment is an observable HTTP 200 diagnostic", async () => {
  const result = await requestForecastReadiness("?unit=unit-current&horizon=6", {
    ok: true,
    readyForEvaluation: false,
    forecastReadiness: { schema: "aibi-forecast-readiness/v1", status: "blocked", blockers: ["forecast-history-too-short"] },
  });

  assert.equal(result.handled, true);
  assert.equal(result.statusCode, 200);
  assert.equal(result.body.readyForEvaluation, false);
  assert.deepEqual(result.cliArgs, ["forecast-readiness", "--unit", "unit-current", "--horizon", "6"]);
});

test("a missing Analysis Unit is rejected before CLI dispatch", async () => {
  const result = await requestForecastReadiness("?horizon=3", { ok: true });

  assert.equal(result.handled, true);
  assert.equal(result.statusCode, 400);
  assert.match(String(result.body.error), /unit is required/i);
  assert.deepEqual(result.cliArgs, []);
});
