export function localApiCandidates(path: string) {
  const candidates = [path];
  if (
    path.startsWith("/api/") &&
    typeof window !== "undefined" &&
    ["localhost", "127.0.0.1"].includes(window.location.hostname) &&
    window.location.port === "8686"
  ) {
    candidates.push(`http://127.0.0.1:8787${path}`);
  }
  return candidates;
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
  for (const candidate of localApiCandidates(path)) {
    try {
      const response = await fetch(candidate, {
        ...init,
        headers: {
          "content-type": "application/json",
          ...(init?.headers ?? {}),
        },
      });
      const payload = (await response.json()) as T;
      if (!response.ok && (!payload || typeof payload !== "object" || !("ok" in payload))) {
        throw new Error(`${response.status} ${response.statusText}`);
      }
      return payload;
    } catch {
      // Try the direct API port when the Vite dev proxy is temporarily unstable on Windows.
    }
  }
  return fallback;
}

export async function fetchJsonStrict<T>(path: string, init?: RequestInit): Promise<T> {
  let lastError: unknown = null;
  for (const candidate of localApiCandidates(path)) {
    let response: Response;
    try {
      response = await fetch(candidate, {
        ...init,
        headers: {
          "content-type": "application/json",
          ...(init?.headers ?? {}),
        },
      });
    } catch (error) {
      lastError = error;
      continue;
    }
    let payload: T;
    try {
      payload = (await response.json()) as T;
    } catch {
      const text = await response.text().catch(() => "");
      throw new Error(`Local API returned invalid JSON for ${path}: ${response.status} ${response.statusText}${text ? ` - ${text.slice(0, 160)}` : ""}`);
    }
    if (!response.ok || (payload && typeof payload === "object" && "ok" in payload && payload.ok === false)) {
      const payloadRecord = payload && typeof payload === "object" && !Array.isArray(payload) ? payload as Record<string, unknown> : null;
      const error = payloadRecord && "error" in payloadRecord ? payloadRecord.error : null;
      const message = typeof error === "string" && error ? error : `${response.status} ${response.statusText}`;
      lastError = payloadRecord ? new ApiPayloadError(path, response.status, message, payloadRecord) : new Error(message);
      continue;
    }
    return payload;
  }
  if (lastError instanceof ApiPayloadError) {
    throw lastError;
  }
  const message = lastError instanceof Error && lastError.message ? lastError.message : "Local API is not reachable";
  throw new Error(`Local API request failed for ${path}: ${message}`);
}
