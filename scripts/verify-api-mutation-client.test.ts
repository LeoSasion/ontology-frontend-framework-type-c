import assert from "node:assert/strict";
import test from "node:test";
import { fetchJsonStrict } from "../src/apiClient";

test("mutation retry keeps its idempotency key until a valid response is parsed", async () => {
  const originalFetch = globalThis.fetch;
  const originalWindow = globalThis.window;
  const storage = new Map<string, string>();
  const mutationKeys: string[] = [];
  let mutationResponseCount = 0;

  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: {
      location: { hostname: "127.0.0.1", port: "4173" },
      sessionStorage: {
        getItem: (key: string) => storage.get(key) ?? null,
        setItem: (key: string, value: string) => storage.set(key, value),
      },
    },
  });

  globalThis.fetch = async (input, init) => {
    if (String(input) === "/api/runtime-session") {
      return Response.json({ ok: true, token: "test-runtime-token" });
    }
    mutationKeys.push(new Headers(init?.headers).get("x-idempotency-key") ?? "");
    mutationResponseCount += 1;
    if (mutationResponseCount === 1) {
      return new Response("{truncated", {
        status: 200,
        headers: { "content-type": "application/json" },
      });
    }
    return Response.json({ ok: true });
  };

  const path = "/api/test-mutation";
  const init: RequestInit = {
    method: "POST",
    body: JSON.stringify({ value: 1 }),
  };

  try {
    await assert.rejects(fetchJsonStrict(path, init), /invalid JSON/);
    await fetchJsonStrict(path, init);
    await fetchJsonStrict(path, init);
    assert.equal(mutationKeys.length, 3);
    assert.ok(mutationKeys[0]);
    assert.equal(mutationKeys[1], mutationKeys[0]);
    assert.notEqual(mutationKeys[2], mutationKeys[1]);
  } finally {
    globalThis.fetch = originalFetch;
    Object.defineProperty(globalThis, "window", {
      configurable: true,
      value: originalWindow,
    });
  }
});
