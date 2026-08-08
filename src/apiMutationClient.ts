const STORAGE_KEY = "aibi.pendingMutations.v1";
type PendingMutationMap = Record<string, string>;

function pendingMutationMap(): PendingMutationMap {
  if (typeof window === "undefined") return {};
  try {
    const value = JSON.parse(window.sessionStorage.getItem(STORAGE_KEY) ?? "{}") as unknown;
    return value && typeof value === "object" && !Array.isArray(value) ? value as PendingMutationMap : {};
  } catch {
    return {};
  }
}

function fingerprint(path: string, init?: RequestInit) {
  const value = `${String(init?.method ?? "GET").toUpperCase()}\n${path}\n${typeof init?.body === "string" ? init.body : ""}`;
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `v1:${(hash >>> 0).toString(16)}`;
}

function store(pending: PendingMutationMap) {
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(pending));
  } catch {
    // Browser storage is optional; server-side idempotency still protects this request.
  }
}

function idempotencyKey(path: string, init?: RequestInit) {
  if (typeof window === "undefined") return "";
  const key = fingerprint(path, init);
  const pending = pendingMutationMap();
  if (pending[key]) return pending[key];
  pending[key] = crypto.randomUUID();
  store(pending);
  return pending[key];
}

let runtimeTokenPromise: Promise<string> | null = null;

async function runtimeToken() {
  if (typeof window === "undefined") return "";
  runtimeTokenPromise ??= fetch("/api/runtime-session", {
    headers: { accept: "application/json" },
    cache: "no-store",
    credentials: "same-origin",
  }).then(async (response) => {
    const payload = await response.json() as { ok?: boolean; token?: string };
    if (!response.ok || payload.ok !== true || !payload.token) throw new Error("Local runtime session could not be established");
    return payload.token;
  }).catch((error) => {
    runtimeTokenPromise = null;
    throw error;
  });
  return runtimeTokenPromise;
}

export async function prepareMutationHeaders(headers: Headers, path: string, init?: RequestInit) {
  headers.set("x-requested-with", "aibi-web");
  headers.set("x-aibi-envelope-version", "aibi-command/v1");
  const key = idempotencyKey(path, init);
  if (key) headers.set("x-idempotency-key", key);
  const token = await runtimeToken();
  if (token) headers.set("x-aibi-runtime-token", token);
}

export function clearPendingMutation(path: string, init?: RequestInit) {
  if (typeof window === "undefined") return;
  const key = fingerprint(path, init);
  const pending = pendingMutationMap();
  if (!pending[key]) return;
  delete pending[key];
  store(pending);
}
