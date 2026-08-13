import assert from "node:assert/strict";
import type { IncomingMessage, ServerResponse } from "node:http";
import { Readable } from "node:stream";
import test from "node:test";

import { handleReviewedPublicationApi } from "../server/reviewedPublicationRoutes";

const WORKSPACE = "default";
const PUBLICATION = "reviewed_publication_1234567890abcdef1234";
const HEAD = "a".repeat(64);

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

function request(method: string, value: Record<string, unknown> = {}) {
  const input = Readable.from([JSON.stringify(value)]) as unknown as IncomingMessage;
  input.method = method;
  input.headers = { "content-type": "application/json" };
  return input;
}

function statusPayload() {
  return { ok: true, workspace: { id: WORKSPACE } };
}

function publicationPayload(status = "current") {
  return { publicationKey: PUBLICATION, workspaceId: WORKSPACE, status };
}

test("bounded list requires viewer capability and stays bound to the active workspace", async () => {
  const capture = responseCapture();
  const calls: string[][] = [];
  const capabilities: string[] = [];
  await handleReviewedPublicationApi({
    authorize: async (capability) => { capabilities.push(capability); return true; },
    cli: async (args) => {
      calls.push(args);
      return args[0] === "status"
        ? statusPayload()
        : { ok: true, reviewedPublications: [publicationPayload()], count: 1 };
    },
    request: request("GET"),
    response: capture.response,
    url: new URL(`http://127.0.0.1/api/reviewed-publications?workspaceId=${WORKSPACE}&limit=999`),
  });
  assert.deepEqual(capabilities, ["reviewed-publication:read"]);
  assert.deepEqual(calls, [["status"], ["reviewed-publications", "--limit", "100"]]);
  assert.equal(capture.result().statusCode, 200);
  assert.equal(capture.result().body.workspaceId, WORKSPACE);
});

test("drifted filter maps the effective stale status without using the inconsistent CLI filter", async () => {
  const capture = responseCapture();
  const calls: string[][] = [];
  await handleReviewedPublicationApi({
    authorize: async () => true,
    cli: async (args) => {
      calls.push(args);
      return args[0] === "status"
        ? statusPayload()
        : { ok: true, reviewedPublications: [publicationPayload("stale"), { ...publicationPayload(), publicationKey: "reviewed_publication_aaaaaaaaaaaaaaaaaaaa" }], count: 2 };
    },
    request: request("GET"),
    response: capture.response,
    url: new URL(`http://127.0.0.1/api/reviewed-publications?workspaceId=${WORKSPACE}&status=drifted&limit=1`),
  });
  assert.deepEqual(calls, [["status"], ["reviewed-publications", "--limit", "100"]]);
  assert.equal(capture.result().body.count, 1);
  assert.equal((capture.result().body.reviewedPublications as Array<Record<string, unknown>>)[0]?.status, "stale");
});

test("inspect and safe export expose only key-scoped read commands", async () => {
  for (const [suffix, expected] of [
    ["", ["reviewed-publications", "--publication", PUBLICATION]],
    ["/export", ["reviewed-publication-export", "--publication", PUBLICATION]],
  ] as const) {
    const capture = responseCapture();
    const calls: string[][] = [];
    await handleReviewedPublicationApi({
      authorize: async () => true,
      cli: async (args) => {
        calls.push(args);
        if (args[0] === "status") return statusPayload();
        return suffix
          ? { ok: true, reviewedPublicationExport: { workspaceId: WORKSPACE, publication: publicationPayload(), ledgerEntries: [] } }
          : { ok: true, reviewedPublication: publicationPayload() };
      },
      request: request("GET"),
      response: capture.response,
      url: new URL(`http://127.0.0.1/api/reviewed-publications/${PUBLICATION}${suffix}?workspaceId=${WORKSPACE}`),
    });
    assert.deepEqual(calls, [["status"], [...expected]]);
    assert.equal(capture.result().statusCode, 200);
  }
});

test("deprecation uses owner capability and preserves preview to exact-head confirmation", async () => {
  const previewCapture = responseCapture();
  const previewCalls: string[][] = [];
  await handleReviewedPublicationApi({
    authorize: async (capability) => capability === "reviewed-publication:owner",
    cli: async (args) => {
      previewCalls.push(args);
      return args[0] === "status"
        ? statusPayload()
        : { ok: true, dryRun: true, requiresConfirmation: true, publicationKey: PUBLICATION, expectedHeadHash: HEAD };
    },
    request: request("POST", { workspaceId: WORKSPACE, reason: "superseded" }),
    response: previewCapture.response,
    url: new URL(`http://127.0.0.1/api/reviewed-publications/${PUBLICATION}/deprecate`),
  });
  assert.deepEqual(previewCalls, [
    ["status"],
    ["reviewed-publication-deprecate", "--publication", PUBLICATION, "--reason", "superseded"],
  ]);
  assert.equal(previewCapture.result().statusCode, 202);

  const confirmCapture = responseCapture();
  const confirmCalls: string[][] = [];
  await handleReviewedPublicationApi({
    authorize: async () => true,
    cli: async (args) => {
      confirmCalls.push(args);
      return args[0] === "status"
        ? statusPayload()
        : { ok: true, confirmed: true, publication: publicationPayload("deprecated") };
    },
    request: request("POST", { workspaceId: WORKSPACE, reason: "superseded", confirm: true, expectedHeadHash: HEAD }),
    response: confirmCapture.response,
    url: new URL(`http://127.0.0.1/api/reviewed-publications/${PUBLICATION}/deprecate`),
  });
  assert.deepEqual(confirmCalls, [
    ["status"],
    ["reviewed-publication-deprecate", "--publication", PUBLICATION, "--reason", "superseded", "--yes", "--expected-head", HEAD],
  ]);
  assert.equal(confirmCapture.result().statusCode, 200);
});

test("authorization happens before parsing a mutation body", async () => {
  const capture = responseCapture();
  let cliCalled = false;
  const unreadable = {
    method: "POST",
    headers: { "content-type": "text/plain" },
    on() { throw new Error("body parser must not be reached"); },
  } as unknown as IncomingMessage;
  await handleReviewedPublicationApi({
    authorize: async () => false,
    cli: async () => { cliCalled = true; return { ok: true }; },
    request: unreadable,
    response: capture.response,
    url: new URL(`http://127.0.0.1/api/reviewed-publications/${PUBLICATION}/deprecate`),
  });
  assert.equal(cliCalled, false);
  assert.equal(capture.result().statusCode, 403);
  assert.equal(capture.result().body.code, "REVIEWED_PUBLICATION_CAPABILITY_DENIED");
});

test("unsupported methods and mutation-shaped GET paths fall through without dispatch", async () => {
  for (const [method, suffix] of [["POST", ""], ["GET", `/${PUBLICATION}/deprecate`], ["POST", `/${PUBLICATION}/export`]] as const) {
    const capture = responseCapture();
    let authorized = false;
    let called = false;
    const handled = await handleReviewedPublicationApi({
      authorize: async () => { authorized = true; return true; },
      cli: async () => { called = true; return { ok: true }; },
      request: request(method),
      response: capture.response,
      url: new URL(`http://127.0.0.1/api/reviewed-publications${suffix}`),
    });
    assert.equal(handled, false);
    assert.equal(authorized, false);
    assert.equal(called, false);
  }
});

test("workspace drift, malformed keys, and missing exact heads fail closed", async () => {
  const workspaceCapture = responseCapture();
  let listCalled = false;
  await handleReviewedPublicationApi({
    authorize: async () => true,
    cli: async (args) => {
      if (args[0] !== "status") listCalled = true;
      return { ok: true, workspace: { id: "another-workspace" } };
    },
    request: request("GET"),
    response: workspaceCapture.response,
    url: new URL(`http://127.0.0.1/api/reviewed-publications?workspaceId=${WORKSPACE}`),
  });
  assert.equal(listCalled, false);
  assert.equal(workspaceCapture.result().statusCode, 409);

  for (const [url, body] of [
    [`http://127.0.0.1/api/reviewed-publications/%2e%2e%2fescape?workspaceId=${WORKSPACE}`, {}],
    [`http://127.0.0.1/api/reviewed-publications/${PUBLICATION}/deprecate`, { workspaceId: WORKSPACE, reason: "superseded", confirm: true }],
  ] as const) {
    const capture = responseCapture();
    let called = false;
    await handleReviewedPublicationApi({
      authorize: async () => true,
      cli: async () => { called = true; return { ok: true }; },
      request: request(url.endsWith("deprecate") ? "POST" : "GET", body),
      response: capture.response,
      url: new URL(url),
    });
    assert.equal(called, false);
    assert.equal(capture.result().statusCode, 400);
  }
});
