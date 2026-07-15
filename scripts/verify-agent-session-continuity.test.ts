import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { useAppAgentActions } from "../src/useAppAgentActions";
import type { AgentAskResult } from "../src/types";

class CountingStorage implements Storage {
  private readonly values = new Map<string, string>();
  readonly writes: Array<{ key: string; value: string }> = [];

  get length() {
    return this.values.size;
  }

  clear() {
    this.values.clear();
  }

  getItem(key: string) {
    return this.values.get(key) ?? null;
  }

  key(index: number) {
    return Array.from(this.values.keys())[index] ?? null;
  }

  removeItem(key: string) {
    this.values.delete(key);
  }

  setItem(key: string, value: string) {
    this.values.set(key, value);
    this.writes.push({ key, value });
  }
}

function agentResult(sessionKey: string): AgentAskResult {
  return {
    ok: true,
    workspaceId: "workspace-session-test",
    llm: { configured: false, mode: "deterministic-fallback" },
    matched: {
      table: null,
      tableSelectionConfidence: "none",
      dashboard: null,
      dashboardSelectionConfidence: "none",
    },
    plan: [],
    recommendedCommands: [],
    requiresConfirmation: false,
    actionDraft: { actionKey: "", kind: "read-only", status: "read-only" },
    agentSession: {
      schema: "aibi-agent-session/v1",
      sessionKey,
      workspaceId: "workspace-session-test",
      title: "Session continuity test",
      status: "active",
      contextFingerprint: "a".repeat(64),
      createdAt: "2026-07-15T00:00:00Z",
      updatedAt: "2026-07-15T00:00:00Z",
    },
  } as unknown as AgentAskResult;
}

function jsonResponse(payload: unknown) {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

test("normal, branch, and read-only Agent asks continue one durable session without duplicate writes", async () => {
  const originalFetch = globalThis.fetch;
  const originalWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
  const storage = new CountingStorage();
  const agentRequests: Array<{ path: string; body: Record<string, unknown> }> = [];
  const askSessions = ["session-normal", "session-branch"];
  let askIndex = 0;

  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: {
      localStorage: storage,
      location: { hostname: "test.invalid", port: "" },
    },
  });
  globalThis.fetch = (async (input, init) => {
    const path = String(input);
    if (path === "/api/actions?limit=12") {
      return jsonResponse({ ok: true, actionDrafts: [] });
    }
    if (path === "/api/agent/ask") {
      const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
      agentRequests.push({ path, body });
      return jsonResponse(agentResult(askSessions[askIndex++] ?? "session-unexpected"));
    }
    if (path === "/api/agent/explain") {
      const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
      agentRequests.push({ path, body });
      return jsonResponse(agentResult("session-read-only"));
    }
    throw new Error(`Unexpected request: ${path}`);
  }) as typeof fetch;

  try {
    let actions!: ReturnType<typeof useAppAgentActions>;
    const navigations: unknown[] = [];
    const agentResults: AgentAskResult[] = [];
    const noop = () => undefined;
    function Harness() {
      actions = useAppAgentActions({
        activeWorkspaceId: "workspace-session-test",
        setActionDrafts: noop,
        setActiveDashboardKey: noop,
        setAgent: (value) => {
          if (typeof value !== "function") agentResults.push(value);
        },
        setDashboards: noop,
        setLastActionResult: noop,
        navigateTo: (target) => navigations.push(target),
        setStatus: noop,
        setWorkbench: noop,
      });
      return null;
    }
    renderToStaticMarkup(createElement(Harness));

    await actions.handleAsk("first question");
    await actions.handleAskBranch("branch question", "turn-parent", "branch-a");
    await actions.handleAskReadOnly("read-only question");

    assert.equal(agentResults.length, 3);
    assert.deepEqual(agentRequests.map((request) => request.path), [
      "/api/agent/ask",
      "/api/agent/ask",
      "/api/agent/explain",
    ]);
    assert.equal(agentRequests[0]?.body.sessionKey, undefined);
    assert.equal(agentRequests[1]?.body.sessionKey, "session-normal");
    assert.equal(agentRequests[1]?.body.parentRunKey, "turn-parent");
    assert.equal(agentRequests[1]?.body.branchLabel, "branch-a");
    assert.equal(agentRequests[2]?.body.sessionKey, "session-branch");
    assert.deepEqual(storage.writes, [
      { key: "aibi.agentSession.workspace-session-test", value: "session-normal" },
      { key: "aibi.agentSession.workspace-session-test", value: "session-branch" },
      { key: "aibi.agentSession.workspace-session-test", value: "session-read-only" },
    ]);
    assert.deepEqual(navigations, [{ section: "agent", actionKey: "", tableKey: undefined, dashboardKey: undefined }]);
  } finally {
    globalThis.fetch = originalFetch;
    if (originalWindow) Object.defineProperty(globalThis, "window", originalWindow);
    else Reflect.deleteProperty(globalThis, "window");
  }
});

test("a deleted persisted session is cleared and retried once as a fresh session", async () => {
  const originalFetch = globalThis.fetch;
  const originalWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
  const storage = new CountingStorage();
  const storageKey = "aibi.agentSession.workspace-session-test";
  storage.setItem(storageKey, "session-deleted");
  storage.writes.length = 0;
  const bodies: Record<string, unknown>[] = [];

  Object.defineProperty(globalThis, "window", {
    configurable: true,
    value: {
      localStorage: storage,
      location: { hostname: "test.invalid", port: "" },
    },
  });
  globalThis.fetch = (async (input, init) => {
    const path = String(input);
    if (path === "/api/actions?limit=12") return jsonResponse({ ok: true, actionDrafts: [] });
    if (path !== "/api/agent/ask") throw new Error(`Unexpected request: ${path}`);
    const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    bodies.push(body);
    if (bodies.length === 1) {
      return jsonResponse({
        ok: false,
        error: "Unknown Agent Session in workspace workspace-session-test: session-deleted",
      });
    }
    return jsonResponse(agentResult("session-recovered"));
  }) as typeof fetch;

  try {
    let actions!: ReturnType<typeof useAppAgentActions>;
    const agentResults: AgentAskResult[] = [];
    const actionErrors: Array<Record<string, unknown> | null> = [];
    const noop = () => undefined;
    function Harness() {
      actions = useAppAgentActions({
        activeWorkspaceId: "workspace-session-test",
        setActionDrafts: noop,
        setActiveDashboardKey: noop,
        setAgent: (value) => {
          if (typeof value !== "function") agentResults.push(value);
        },
        setDashboards: noop,
        setLastActionResult: (value) => {
          if (typeof value !== "function") actionErrors.push(value);
        },
        navigateTo: noop,
        setStatus: noop,
        setWorkbench: noop,
      });
      return null;
    }
    renderToStaticMarkup(createElement(Harness));

    const result = await actions.handleAsk("recover this session");

    assert.equal(result?.agentSession?.sessionKey, "session-recovered");
    assert.deepEqual(bodies.map((body) => body.sessionKey), ["session-deleted", undefined]);
    assert.deepEqual(storage.writes, [
      { key: storageKey, value: "" },
      { key: storageKey, value: "session-recovered" },
    ]);
    assert.equal(agentResults.length, 1);
    assert.equal(actionErrors.length, 0);
  } finally {
    globalThis.fetch = originalFetch;
    if (originalWindow) Object.defineProperty(globalThis, "window", originalWindow);
    else Reflect.deleteProperty(globalThis, "window");
  }
});

test("disabled browser storage degrades to a non-persistent request without breaking render or ask", async () => {
  const originalFetch = globalThis.fetch;
  const originalWindow = Object.getOwnPropertyDescriptor(globalThis, "window");
  const blockedWindow = { location: { hostname: "test.invalid", port: "" } } as Window & typeof globalThis;
  Object.defineProperty(blockedWindow, "localStorage", {
    configurable: true,
    get() {
      throw new DOMException("Browser storage is disabled", "SecurityError");
    },
  });
  Object.defineProperty(globalThis, "window", { configurable: true, value: blockedWindow });
  globalThis.fetch = (async (input) => {
    const path = String(input);
    if (path === "/api/actions?limit=12") return jsonResponse({ ok: true, actionDrafts: [] });
    if (path === "/api/agent/ask") return jsonResponse(agentResult("session-storage-disabled"));
    throw new Error(`Unexpected request: ${path}`);
  }) as typeof fetch;

  try {
    let actions!: ReturnType<typeof useAppAgentActions>;
    const agentResults: AgentAskResult[] = [];
    const actionErrors: Array<Record<string, unknown> | null> = [];
    const noop = () => undefined;
    function Harness() {
      actions = useAppAgentActions({
        activeWorkspaceId: "workspace-session-test",
        setActionDrafts: noop,
        setActiveDashboardKey: noop,
        setAgent: (value) => {
          if (typeof value !== "function") agentResults.push(value);
        },
        setDashboards: noop,
        setLastActionResult: (value) => {
          if (typeof value !== "function") actionErrors.push(value);
        },
        navigateTo: noop,
        setStatus: noop,
        setWorkbench: noop,
      });
      return null;
    }

    assert.doesNotThrow(() => renderToStaticMarkup(createElement(Harness)));
    const result = await actions.handleAsk("ask without browser storage");

    assert.equal(result?.agentSession?.sessionKey, "session-storage-disabled");
    assert.equal(agentResults.length, 1);
    assert.equal(actionErrors.length, 0);
  } finally {
    globalThis.fetch = originalFetch;
    if (originalWindow) Object.defineProperty(globalThis, "window", originalWindow);
    else Reflect.deleteProperty(globalThis, "window");
  }
});
