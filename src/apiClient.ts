const SAFE_FALLBACK_METHODS = new Set(["GET", "HEAD"]);
const MUTATION_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function requestMethod(init?: RequestInit) {
  return String(init?.method ?? "GET").toUpperCase();
}

function isMutation(init?: RequestInit) {
  return MUTATION_METHODS.has(requestMethod(init));
}

export function localApiCandidates(path: string, init?: RequestInit) {
  const candidates = [path];
  if (
    SAFE_FALLBACK_METHODS.has(requestMethod(init)) &&
    path.startsWith("/api/") &&
    typeof window !== "undefined" &&
    ["localhost", "127.0.0.1"].includes(window.location.hostname) &&
    window.location.port === "8686"
  ) {
    candidates.push(`http://127.0.0.1:8787${path}`);
  }
  return candidates;
}

async function requestHeaders(path: string, init?: RequestInit) {
  const headers = new Headers(init?.headers);
  headers.set("content-type", "application/json");
  if (isMutation(init)) {
    const { prepareMutationHeaders } = await import("./apiMutationClient");
    await prepareMutationHeaders(headers, path, init);
  }
  return headers;
}

export class ApiPayloadError extends Error {
  payload: Record<string, unknown>;
  path: string;
  status: number;

  constructor(path: string, status: number, message: string, payload: Record<string, unknown>) {
    super(message);
    this.name = "ApiPayloadError";
    this.path = path;
    this.status = status;
    this.payload = payload;
  }
}

export async function fetchJson<T>(path: string, fallback: T, init?: RequestInit): Promise<T> {
  if (isMutation(init)) return fetchJsonStrict<T>(path, init);
  for (const candidate of localApiCandidates(path, init)) {
    try {
      const response = await fetch(candidate, {
        ...init,
        headers: await requestHeaders(path, init),
      });
      const payload = (await response.json()) as T;
      if (!response.ok || (payload && typeof payload === "object" && "ok" in payload && payload.ok === false)) throw new Error(`${response.status} ${response.statusText}`);
      return payload;
    } catch {
      // Try the direct API port when the Vite dev proxy is temporarily unstable on Windows.
    }
  }
  return fallback;
}

export async function fetchJsonStrict<T>(path: string, init?: RequestInit): Promise<T> {
  let lastError: unknown = null;
  const headers = await requestHeaders(path, init);
  for (const candidate of localApiCandidates(path, init)) {
    let response: Response;
    try {
      response = await fetch(candidate, {
        ...init,
        headers,
      });
    } catch (error) {
      lastError = error;
      continue;
    }
    let payload: T;
    const responseCopy = response.clone();
    try {
      payload = (await response.json()) as T;
    } catch {
      const text = await responseCopy.text().catch(() => "");
      throw new Error(`Local API returned invalid JSON for ${path}: ${response.status} ${response.statusText}${text ? ` - ${text.slice(0, 160)}` : ""}`);
    }
    if (isMutation(init)) {
      const { clearPendingMutation } = await import("./apiMutationClient");
      clearPendingMutation(path, init);
    }
    if (!response.ok || (payload && typeof payload === "object" && "ok" in payload && payload.ok === false)) {
      const payloadRecord = payload && typeof payload === "object" && !Array.isArray(payload) ? payload as Record<string, unknown> : null;
      const error = payloadRecord && "error" in payloadRecord ? payloadRecord.error : null;
      const message = typeof error === "string" && error ? error : `${response.status} ${response.statusText}`;
      throw payloadRecord ? new ApiPayloadError(path, response.status, message, payloadRecord) : new Error(message);
    }
    return payload;
  }
  if (lastError instanceof ApiPayloadError) {
    throw lastError;
  }
  const message = lastError instanceof Error && lastError.message ? lastError.message : "Local API is not reachable";
  throw new Error(`Local API request failed for ${path}: ${message}`);
}
