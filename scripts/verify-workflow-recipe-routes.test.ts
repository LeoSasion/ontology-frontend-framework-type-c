import assert from "node:assert/strict";
import type { IncomingMessage, ServerResponse } from "node:http";
import { Readable } from "node:stream";
import test from "node:test";

import { handleWorkflowApi } from "../server/workflowRoutes";

const PLAN = "a".repeat(64);
const RECIPE = "recipe_1234567890abcdef1234";

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
  const handled = await handleWorkflowApi({
    cli: async (args) => { calls.push(args); return { ok: true, workflowRecipePlan: { planFingerprint: PLAN } }; },
    request: request(method, body), response: output.response, url: new URL(`http://127.0.0.1${path}`),
  });
  return { handled, calls, ...output.result() };
}

test("recipe preview and publish keep the exact binding", async () => {
  const input = { requestKey: "workflow-route-v1", name: "Safe change", stages: [{ command: "status", input: {} }] };
  const preview = await invoke("/api/workflow/recipes/preview", "POST", input);
  assert.deepEqual(preview.calls[0], ["workflow-recipe-preview", "--request-key", "workflow-route-v1", "--name", "Safe change", "--stage-json", JSON.stringify(input.stages[0])]);
  const rejected = await invoke("/api/workflow/recipes/publish", "POST", { ...input, confirm: true });
  assert.equal(rejected.statusCode, 400);
  assert.equal(rejected.calls.length, 0);
  const confirmed = await invoke("/api/workflow/recipes/publish", "POST", { ...input, confirm: true, expectedPlanFingerprint: PLAN });
  assert.equal(confirmed.calls[0].includes("--yes"), true);
  assert.equal(confirmed.calls[0].includes(PLAN), true);
});

test("recipe planning is bounded and never accepts an invalid key", async () => {
  const invalid = await invoke("/api/workflow/recipes/plan", "POST", { recipeKey: "../escape", bindings: {} });
  assert.equal(invalid.statusCode, 400);
  assert.equal(invalid.calls.length, 0);
  const planned = await invoke("/api/workflow/recipes/plan", "POST", { recipeKey: RECIPE, bindings: { reason: "safe" } });
  assert.deepEqual(planned.calls, [["workflow-recipe-plan", "--recipe", RECIPE, "--bindings-json", JSON.stringify({ reason: "safe" })]]);
});

test("recipe list is bounded", async () => {
  const listed = await invoke("/api/workflow/recipes?limit=999", "GET");
  assert.deepEqual(listed.calls, [["workflow-recipes", "--limit", "100"]]);
});
