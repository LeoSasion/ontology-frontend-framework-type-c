import { spawn } from "node:child_process";
import { existsSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, join } from "node:path";
import net from "node:net";

const windowsChromeCandidates = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
];

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function waitForExit(child, timeoutMs = 2000) {
  if (child.exitCode !== null || child.signalCode !== null) {
    return Promise.resolve();
  }

  return new Promise((resolve) => {
    const timeout = setTimeout(resolve, timeoutMs);
    child.once("exit", () => {
      clearTimeout(timeout);
      resolve();
    });
  });
}

async function removeDirectoryWithRetry(directoryPath, attempts = 8) {
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      rmSync(directoryPath, { recursive: true, force: true });
      return;
    } catch (error) {
      if (attempt === attempts) throw error;
      await sleep(150 * attempt);
    }
  }
}

function getFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      const port = typeof address === "object" && address ? address.port : 0;
      server.close(() => resolve(port));
    });
  });
}

export function findChromeExecutable() {
  const explicit = process.env.AIBI_CHROME_PATH;
  if (explicit && existsSync(explicit)) return explicit;
  if (process.platform === "win32") {
    const match = windowsChromeCandidates.find((candidate) => existsSync(candidate));
    if (match) return match;
  }
  const fallback = process.platform === "darwin" ? "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" : "/usr/bin/google-chrome";
  return existsSync(fallback) ? fallback : null;
}

async function waitForJson(url, timeoutMs = 10000) {
  const startedAt = Date.now();
  let lastError = "";
  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await fetch(url);
      if (response.ok) return await response.json();
      lastError = `${response.status} ${response.statusText}`;
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }
    await sleep(120);
  }
  throw new Error(`Chrome debugger did not become ready at ${url}: ${lastError}`);
}

class CdpClient {
  constructor(webSocketUrl) {
    this.webSocketUrl = webSocketUrl;
    this.socket = null;
    this.nextId = 1;
    this.pending = new Map();
    this.events = [];
  }

  connect(timeoutMs = 10000) {
    return new Promise((resolve, reject) => {
      const socket = new WebSocket(this.webSocketUrl);
      this.socket = socket;
      const timeout = setTimeout(() => {
        reject(new Error(`Timed out connecting to ${this.webSocketUrl}`));
      }, timeoutMs);
      socket.addEventListener("open", () => {
        clearTimeout(timeout);
        resolve();
      });
      socket.addEventListener("message", (message) => {
        const raw = typeof message.data === "string" ? message.data : Buffer.from(message.data).toString("utf8");
        const payload = JSON.parse(raw);
        if (payload.id && this.pending.has(payload.id)) {
          const { resolve: resolvePending, reject: rejectPending, timeout: pendingTimeout } = this.pending.get(payload.id);
          clearTimeout(pendingTimeout);
          this.pending.delete(payload.id);
          if (payload.error) {
            rejectPending(new Error(`${payload.error.message}${payload.error.data ? `: ${payload.error.data}` : ""}`));
          } else {
            resolvePending(payload.result ?? {});
          }
          return;
        }
        if (payload.method) this.events.push(payload);
      });
      socket.addEventListener("error", () => {
        clearTimeout(timeout);
        reject(new Error(`Failed to connect to ${this.webSocketUrl}`));
      });
      socket.addEventListener("close", () => {
        for (const { reject: rejectPending, timeout: pendingTimeout } of this.pending.values()) {
          clearTimeout(pendingTimeout);
          rejectPending(new Error("Chrome debugger socket closed"));
        }
        this.pending.clear();
      });
    });
  }

  send(method, params = {}, timeoutMs = 10000) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return Promise.reject(new Error("Chrome debugger socket is not open"));
    }
    const id = this.nextId++;
    const message = JSON.stringify({ id, method, params });
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Timed out waiting for ${method}`));
      }, timeoutMs);
      this.pending.set(id, { resolve, reject, timeout });
      this.socket.send(message);
    });
  }

  close() {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.close();
    }
  }

  consoleIssues() {
    const consoleItems = this.events
      .filter((event) => event.method === "Runtime.consoleAPICalled")
      .map((event) => ({
        level: event.params?.type,
        text: (event.params?.args ?? []).map((arg) => arg.value ?? arg.description ?? "").join(" "),
      }))
      .filter((event) => ["error", "warning", "warn"].includes(String(event.level).toLowerCase()));
    const exceptionItems = this.events
      .filter((event) => event.method === "Runtime.exceptionThrown")
      .map((event) => ({
        level: "exception",
        text: event.params?.exceptionDetails?.exception?.description ?? event.params?.exceptionDetails?.text ?? "Runtime exception",
      }));
    const logItems = this.events
      .filter((event) => event.method === "Log.entryAdded")
      .map((event) => ({
        level: event.params?.entry?.level ?? "log",
        text: event.params?.entry?.text ?? "",
      }));
    return [...consoleItems, ...exceptionItems, ...logItems]
      .filter((event) => !/vite|react devtools/i.test(event.text));
  }
}

async function launchChromeAttempt(chromePath) {
  const port = await getFreePort();
  const profileDir = join(tmpdir(), `aibi-ui-chrome-profile-${Date.now()}-${Math.random().toString(16).slice(2)}`);
  mkdirSync(profileDir, { recursive: true });
  const child = spawn(chromePath, [
    "--headless=new",
    "--disable-gpu",
    "--no-sandbox",
    "--no-first-run",
    "--disable-background-networking",
    "--disable-dev-shm-usage",
    "--run-all-compositor-stages-before-draw",
    `--remote-debugging-address=127.0.0.1`,
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profileDir}`,
    "about:blank",
  ], {
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });
  let stderr = "";
  child.stderr.on("data", (chunk) => {
    stderr += chunk.toString();
  });

  try {
    await waitForJson(`http://127.0.0.1:${port}/json/version`, 15000);
    const targets = await waitForJson(`http://127.0.0.1:${port}/json/list`);
    const pageTarget = Array.isArray(targets) ? targets.find((target) => target.type === "page" && target.webSocketDebuggerUrl) : null;
    if (!pageTarget) {
      throw new Error("Chrome page debugger target was not found.");
    }
    const client = new CdpClient(pageTarget.webSocketDebuggerUrl);
    await client.connect();
    await client.send("Page.enable");
    await client.send("Runtime.enable");
    await client.send("Log.enable").catch(() => {});
    await client.send("Page.addScriptToEvaluateOnNewDocument", {
      source: 'window.localStorage.setItem("aibiHybrid.languageMode", "en");',
    });
    return {
      chromePath,
      chromeName: basename(chromePath),
      client,
      profileDir,
      stderr: () => stderr,
      async close() {
        client.close();
        if (!child.killed) child.kill();
        await waitForExit(child);
        await removeDirectoryWithRetry(profileDir);
      },
    };
  } catch (error) {
    if (!child.killed) child.kill();
    await waitForExit(child);
    await removeDirectoryWithRetry(profileDir);
    const detail = stderr.trim();
    throw new Error(`${error instanceof Error ? error.message : String(error)}${detail ? `\n${detail}` : ""}`);
  }
}

export async function launchChrome(attempts = 3) {
  const chromePath = findChromeExecutable();
  if (!chromePath) {
    throw new Error("Chrome or Edge executable was not found. Set AIBI_CHROME_PATH to run UI verification.");
  }
  let lastError = null;
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      return await launchChromeAttempt(chromePath);
    } catch (error) {
      lastError = error;
      if (attempt < attempts) await sleep(250 * attempt);
    }
  }
  throw new Error(`Chrome UI verification failed after ${attempts} attempts: ${lastError instanceof Error ? lastError.message : String(lastError)}`);
}

export function expressionFor(fn, arg) {
  return `(${fn.toString()})(${JSON.stringify(arg)})`;
}

export async function evaluate(client, fn, arg, timeoutMs = 10000) {
  const result = await client.send("Runtime.evaluate", {
    expression: expressionFor(fn, arg),
    awaitPromise: true,
    returnByValue: true,
    timeout: timeoutMs,
  }, timeoutMs + 1000);
  if (result.exceptionDetails) {
    const detail = result.exceptionDetails.exception?.description ?? result.exceptionDetails.text ?? "unknown exception";
    throw new Error(detail);
  }
  return result.result?.value;
}

export async function setViewport(client, viewport) {
  await client.send("Emulation.setDeviceMetricsOverride", {
    width: viewport.width,
    height: viewport.height,
    deviceScaleFactor: 1,
    mobile: false,
  });
}

export async function navigate(client, url) {
  const startedAt = client.events.length;
  const loadEvent = new Promise((resolve) => {
    const timeout = setTimeout(() => resolve({ ok: false, reason: "load timeout" }), 8000);
    const check = () => {
      const loaded = client.events.slice(startedAt).some((event) => event.method === "Page.loadEventFired");
      if (loaded) {
        clearTimeout(timeout);
        resolve({ ok: true });
        return;
      }
      setTimeout(check, 50);
    };
    check();
  });
  await client.send("Page.navigate", { url });
  await loadEvent;
}

export async function waitFor(client, fn, arg, { timeoutMs = 15000, intervalMs = 200 } = {}) {
  const startedAt = Date.now();
  let lastValue = null;
  let lastError = null;
  while (Date.now() - startedAt < timeoutMs) {
    try {
      lastValue = await evaluate(client, fn, arg, Math.min(3000, intervalMs + 2500));
      if (lastValue?.ok) return lastValue;
    } catch (error) {
      lastError = error;
    }
    await sleep(intervalMs);
  }
  if (lastError && !lastValue) throw lastError;
  return lastValue ?? { ok: false, error: "condition timed out" };
}

export async function captureScreenshot(client, filePath) {
  const result = await client.send("Page.captureScreenshot", {
    format: "png",
    fromSurface: true,
  }, 15000);
  const bytes = Buffer.from(result.data, "base64");
  writeFileSync(filePath, bytes);
  return { path: filePath, bytes: bytes.length };
}

export async function click(client, selector) {
  return evaluate(client, (targetSelector) => {
    const element = document.querySelector(targetSelector);
    if (!element) return { ok: false, error: `missing ${targetSelector}` };
    element.click();
    return { ok: true };
  }, selector);
}

export async function getAppReadyState(client, sectionTestId) {
  return evaluate(client, (testId) => {
    const text = document.body?.innerText || "";
    const hasSection = testId ? Boolean(document.querySelector(`[data-testid="${testId}"]`)) : true;
    const hasErrorBoundary = Boolean(document.querySelector(".appFallback, .fallbackPanel")) || text.includes("界面需要恢复");
    const hasFrameworkOverlay = Boolean(document.querySelector("vite-error-overlay, .vite-error-overlay"));
    const hasServiceDiagnostics = Boolean(document.querySelector('[data-testid="service-diagnostics"]'));
    return {
      ok: Boolean(document.querySelector(".appShell")) &&
        hasSection &&
        !hasServiceDiagnostics &&
        !hasErrorBoundary &&
        !hasFrameworkOverlay,
      title: document.title,
      url: location.href,
      connected: !hasServiceDiagnostics,
      hasShell: Boolean(document.querySelector(".appShell")),
      hasSection,
      hasErrorBoundary,
      hasFrameworkOverlay,
      hasServiceDiagnostics,
      workspace: document.querySelector("#workspace-switcher")?.value || "",
    };
  }, sectionTestId);
}

export async function waitForAppReady(client, sectionTestId, timeoutMs = 20000) {
  return waitFor(client, (testId) => {
    const text = document.body?.innerText || "";
    const hasSection = testId ? Boolean(document.querySelector(`[data-testid="${testId}"]`)) : true;
    const hasErrorBoundary = Boolean(document.querySelector(".appFallback, .fallbackPanel")) || text.includes("界面需要恢复");
    const hasFrameworkOverlay = Boolean(document.querySelector("vite-error-overlay, .vite-error-overlay"));
    const hasServiceDiagnostics = Boolean(document.querySelector('[data-testid="service-diagnostics"]'));
    return {
      ok: Boolean(document.querySelector(".appShell")) &&
        hasSection &&
        !hasServiceDiagnostics &&
        !hasErrorBoundary &&
        !hasFrameworkOverlay,
      title: document.title,
      url: location.href,
      connected: !hasServiceDiagnostics,
      hasShell: Boolean(document.querySelector(".appShell")),
      hasSection,
      hasErrorBoundary,
      hasFrameworkOverlay,
      hasServiceDiagnostics,
      workspace: document.querySelector("#workspace-switcher")?.value || "",
    };
  }, sectionTestId, { timeoutMs, intervalMs: 250 });
}

export function check(label, ok, details = {}) {
  return { label, ok: Boolean(ok), ...details };
}

export function finishReceipt(receipt) {
  const failedChecks = receipt.checks.filter((item) => !item.ok);
  return {
    ...receipt,
    ok: failedChecks.length === 0,
    failedChecks,
  };
}
