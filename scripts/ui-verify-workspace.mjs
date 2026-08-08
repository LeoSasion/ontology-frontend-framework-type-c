import { randomUUID } from "node:crypto";

export const apiBaseUrl = process.env.AIBI_API_BASE_URL ?? "http://127.0.0.1:8787";

export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function fetchJson(path, options = {}) {
  let lastError = null;
  const attempts = 8;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    try {
      const response = await fetch(`${apiBaseUrl}${path}`, options);
      const payload = await response.json().catch(() => ({ ok: false, error: `Non-JSON response from ${path}` }));
      if (!response.ok || payload?.ok === false) {
        const detail = payload?.error
          ?? (Array.isArray(payload?.blockers) && payload.blockers.length ? payload.blockers.join(", ") : null)
          ?? JSON.stringify(payload);
        const error = new Error(`${path}: ${detail} (${response.status} ${response.statusText})`);
        error.httpStatus = response.status;
        throw error;
      }
      return payload;
    } catch (error) {
      lastError = error;
      if (Number(error?.httpStatus ?? 0) > 0 && Number(error.httpStatus) < 500) throw error;
      if (attempt < attempts - 1) await sleep(250 * (attempt + 1));
    }
  }
  throw lastError;
}

export async function postJson(path, body) {
  return fetchJson(path, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "x-idempotency-key": `ui-verify-${randomUUID()}`,
    },
    body: JSON.stringify(body),
  });
}

export async function getStatus() {
  return fetchJson("/api/status");
}

export async function getWorkbench() {
  return fetchJson("/api/workbench");
}

export async function getDashboards() {
  return fetchJson("/api/dashboards");
}

export async function getActions(limit = 12) {
  return fetchJson(`/api/actions?limit=${limit}`);
}

function workspaceIdFromCreate(result, name) {
  const created = result?.created && typeof result.created === "object" ? result.created : null;
  const workspace = result?.workspace && typeof result.workspace === "object" ? result.workspace : null;
  const proposed = result?.proposed && typeof result.proposed === "object" ? result.proposed : null;
  return String(created?.id ?? workspace?.id ?? proposed?.id ?? name);
}

async function selectWorkspace(workspaceId) {
  if (!workspaceId) return null;
  return postJson("/api/workspaces", { op: "select", workspaceId, confirm: true });
}

async function deleteWorkspace(workspaceId) {
  if (!workspaceId) return null;
  return postJson("/api/workspaces", { op: "delete", workspaceId, confirm: true });
}

export function zeroCounts(counts = {}) {
  const keys = ["tables", "sourceRuns", "fields", "metrics", "relationships", "dashboards", "actionDrafts", "sourceIntelligenceRuns", "connectors"];
  return keys.every((key) => Number(counts[key] ?? 0) === 0);
}

export async function waitForApi(checkFn, { timeoutMs = 30000, intervalMs = 500, label = "api condition" } = {}) {
  const startedAt = Date.now();
  let lastValue = null;
  let lastError = null;
  while (Date.now() - startedAt < timeoutMs) {
    try {
      lastValue = await checkFn();
      if (lastValue?.ok) return lastValue;
    } catch (error) {
      lastError = error;
    }
    await sleep(intervalMs);
  }
  if (lastError && !lastValue) throw lastError;
  throw new Error(`${label} timed out: ${JSON.stringify(lastValue)}`);
}

export async function withTemporaryWorkspace(prefix, callback) {
  const originalStatus = await getStatus();
  const originalWorkspace = originalStatus.workspace;
  const name = `${prefix}_${Date.now()}_${Math.random().toString(16).slice(2, 8)}`;
  const lifecycle = {
    originalWorkspace,
    temporaryWorkspace: { id: "", name },
    cleanup: [],
  };
  let callbackError = null;
  let result;

  const createResult = await postJson("/api/workspaces", { op: "create", name, confirm: true });
  const temporaryWorkspaceId = workspaceIdFromCreate(createResult, name);
  lifecycle.temporaryWorkspace.id = temporaryWorkspaceId;
  lifecycle.createResult = createResult;
  lifecycle.selectTemporaryResult = await selectWorkspace(temporaryWorkspaceId);

  try {
    result = await callback({ temporaryWorkspaceId, temporaryWorkspaceName: name, originalWorkspace, lifecycle });
  } catch (error) {
    callbackError = error;
  }

  try {
    if (originalWorkspace?.id) {
      lifecycle.cleanup.push({ step: "select-original-before-delete", result: await selectWorkspace(originalWorkspace.id) });
    }
  } catch (error) {
    lifecycle.cleanup.push({ step: "select-original-before-delete", ok: false, error: error instanceof Error ? error.message : String(error) });
  }

  try {
    lifecycle.cleanup.push({ step: "delete-temporary", result: await deleteWorkspace(temporaryWorkspaceId) });
  } catch (error) {
    lifecycle.cleanup.push({ step: "delete-temporary", ok: false, error: error instanceof Error ? error.message : String(error) });
  }

  try {
    if (originalWorkspace?.id) {
      lifecycle.cleanup.push({ step: "select-original-after-delete", result: await selectWorkspace(originalWorkspace.id) });
    }
  } catch (error) {
    lifecycle.cleanup.push({ step: "select-original-after-delete", ok: false, error: error instanceof Error ? error.message : String(error) });
  }

  const cleanupFailures = lifecycle.cleanup.filter((item) => item.ok === false || item.result?.ok === false);
  if (callbackError) {
    callbackError.lifecycle = lifecycle;
    throw callbackError;
  }
  if (cleanupFailures.length) {
    const error = new Error(`Temporary workspace cleanup failed: ${cleanupFailures.map((item) => item.step).join(", ")}`);
    error.lifecycle = lifecycle;
    throw error;
  }
  return { ...result, lifecycle };
}
