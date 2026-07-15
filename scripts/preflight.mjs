import { spawnSync } from "node:child_process";
import { runPreflightLifecycle } from "./preflight-lifecycle.mjs";

const npmCommand = process.platform === "win32" ? process.env.ComSpec ?? "cmd.exe" : "npm";
const npmPrefixArgs = process.platform === "win32" ? ["/d", "/s", "/c", "npm"] : [];
const powershellCommand = process.platform === "win32" ? "powershell.exe" : "pwsh";
function runCommand(label, command, commandArgs) {
  const startedAt = Date.now();
  console.log(`\n[preflight] ${label}`);
  const result = spawnSync(command, commandArgs, {
    cwd: process.cwd(),
    env: process.env,
    stdio: "inherit",
    windowsHide: true,
  });
  const seconds = ((Date.now() - startedAt) / 1000).toFixed(1);
  if (result.error || result.status !== 0) {
    if (result.error) {
      console.error(`[preflight] ${label} could not start: ${result.error.message}`);
    }
    console.error(`[preflight] ${label} failed after ${seconds}s.`);
    const error = new Error(`${label} failed after ${seconds}s.`);
    error.exitCode = result.status ?? 1;
    error.cause = result.error;
    throw error;
  }
  console.log(`[preflight] ${label} passed in ${seconds}s.`);
}

function runNpmScript(label, scriptName) {
  runCommand(label, npmCommand, [...npmPrefixArgs, "run", scriptName]);
}

function runPowerShell(label, scriptPath) {
  runCommand(label, powershellCommand, ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", scriptPath]);
}

function inspectLocalServices() {
  const healthResult = spawnSync(
    powershellCommand,
    ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "scripts/local-health.ps1", "-Json"],
    {
      cwd: process.cwd(),
      env: process.env,
      encoding: "utf8",
      windowsHide: true,
    },
  );
  let healthy = false;
  try {
    healthy = !healthResult.error && healthResult.status === 0 && JSON.parse(healthResult.stdout || "{}").ok === true;
  } catch {
    healthy = false;
  }

  const listenerProbe = spawnSync(
    powershellCommand,
    [
      "-NoProfile",
      "-Command",
      "$items = @(); foreach ($port in @(8787, 8686)) { $items += @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | ForEach-Object { [pscustomobject]@{ port = $port; processId = [int]$_.OwningProcess } }) }; [pscustomobject]@{ listeners = $items } | ConvertTo-Json -Compress -Depth 4",
    ],
    {
      cwd: process.cwd(),
      env: process.env,
      encoding: "utf8",
      windowsHide: true,
    },
  );
  if (listenerProbe.error || listenerProbe.status !== 0) {
    return { healthy, ownershipKnown: false, listeners: [] };
  }
  try {
    const parsed = JSON.parse(listenerProbe.stdout || "{}");
    const listeners = Array.isArray(parsed.listeners)
      ? parsed.listeners
      : parsed.listeners
        ? [parsed.listeners]
        : [];
    return { healthy, ownershipKnown: true, listeners };
  } catch {
    return { healthy, ownershipKnown: false, listeners: [] };
  }
}

try {
  const receipt = runPreflightLifecycle({
    args: process.argv.slice(2),
    runNpmScript,
    runPowerShell,
    inspectLocalServices,
  });
  console.log(`\n[preflight] AIBI-C is ready. ${JSON.stringify(receipt.services)}`);
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  console.error(`\n[preflight] AIBI-C is not ready: ${message}`);
  process.exitCode = Number.isInteger(error?.exitCode) ? error.exitCode : 1;
}
