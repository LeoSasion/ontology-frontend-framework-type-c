import { execFileSync, spawn } from "node:child_process";
import net from "node:net";

const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
const children = [];
let shuttingDown = false;

function portIsOpen(port) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host: "127.0.0.1", port });
    socket.setTimeout(500);
    socket.on("connect", () => {
      socket.destroy();
      resolve(true);
    });
    socket.on("timeout", () => {
      socket.destroy();
      resolve(false);
    });
    socket.on("error", () => resolve(false));
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForPortClosed(port, timeoutMs = 4000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (!await portIsOpen(port)) return true;
    await sleep(150);
  }
  return false;
}

async function apiIsCompatible() {
  try {
    const response = await fetch("http://127.0.0.1:8787/api/health");
    if (!response.ok) return false;
    const payload = await response.json();
    return payload?.ok === true && payload?.service === "aibi-hybrid-api";
  } catch {
    return false;
  }
}

async function uiIsCompatible() {
  try {
    const response = await fetch("http://127.0.0.1:8686/");
    if (!response.ok) return false;
    const html = await response.text();
    return html.includes("<title>AIBI Hybrid</title>");
  } catch {
    return false;
  }
}

function listeningPids(port) {
  if (process.platform !== "win32") return [];
  try {
    const output = execFileSync("powershell.exe", [
      "-NoProfile",
      "-Command",
      `Get-NetTCPConnection -LocalPort ${port} -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique`,
    ], { encoding: "utf8", windowsHide: true });
    return output.split(/\r?\n/).map((line) => Number(line.trim())).filter((pid) => Number.isInteger(pid) && pid > 0);
  } catch {
    return [];
  }
}

function commandLineForPid(pid) {
  if (process.platform !== "win32") return "";
  try {
    return execFileSync("powershell.exe", [
      "-NoProfile",
      "-Command",
      `(Get-CimInstance Win32_Process -Filter "ProcessId = ${pid}").CommandLine`,
    ], { encoding: "utf8", windowsHide: true }).trim();
  } catch {
    return "";
  }
}

async function stopOwnedPortProcess(port, label) {
  const cwd = process.cwd().toLowerCase();
  for (const pid of listeningPids(port)) {
    const commandLine = commandLineForPid(pid);
    if (!commandLine.toLowerCase().includes(cwd)) continue;
    console.log(`[${label}] stale service from this workspace detected on ${port}; restarting pid ${pid}.`);
    try {
      process.kill(pid);
    } catch (error) {
      console.error(`[${label}] failed to stop pid ${pid}: ${error instanceof Error ? error.message : String(error)}`);
      return false;
    }
  }
  return waitForPortClosed(port);
}

function start(label, args) {
  const child = spawn(npmCommand, args, {
    cwd: process.cwd(),
    env: process.env,
    shell: process.platform === "win32",
    stdio: ["inherit", "pipe", "pipe"],
    windowsHide: true,
  });
  children.push(child);
  const prefix = `[${label}]`;
  child.stdout.on("data", (chunk) => process.stdout.write(`${prefix} ${chunk}`));
  child.stderr.on("data", (chunk) => process.stderr.write(`${prefix} ${chunk}`));
  child.on("exit", (code, signal) => {
    if (shuttingDown) return;
    shuttingDown = true;
    const reason = signal ? `signal ${signal}` : `code ${code}`;
    console.error(`${prefix} exited with ${reason}; stopping dev services.`);
    stopChildren();
    process.exit(code ?? 1);
  });
}

function stopChildren() {
  for (const child of children) {
    if (!child.killed) child.kill();
  }
}

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    shuttingDown = true;
    stopChildren();
    process.exit(0);
  });
}

if (await portIsOpen(8787)) {
  if (await apiIsCompatible()) {
    console.log("[api:8787] compatible existing service detected; reusing it.");
  } else if (await stopOwnedPortProcess(8787, "api:8787")) {
    start("api:8787", ["run", "api"]);
  } else {
    console.error("[api:8787] port is occupied by an incompatible service. Stop it or free port 8787, then rerun npm run dev.");
    process.exit(1);
  }
} else {
  start("api:8787", ["run", "api"]);
}

if (await portIsOpen(8686)) {
  if (await uiIsCompatible()) {
    console.log("[ui:8686] compatible existing service detected; reusing it.");
  } else if (await stopOwnedPortProcess(8686, "ui:8686")) {
    start("ui:8686", ["run", "dev:ui"]);
  } else {
    console.error("[ui:8686] port is occupied by an incompatible service. Stop it or free port 8686, then rerun npm run dev.");
    process.exit(1);
  }
} else {
  start("ui:8686", ["run", "dev:ui"]);
}

if (!children.length) {
  console.log("[dev] API 8787 and UI 8686 are already running. Press Ctrl+C to stop waiting.");
  setInterval(() => {}, 60_000);
}
