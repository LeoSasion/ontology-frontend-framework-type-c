import assert from "node:assert/strict";
import { copyFileSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { spawn, spawnSync } from "node:child_process";
import { runPreflightLifecycle } from "./preflight-lifecycle.mjs";

function executeScenario({ preExisting = false, listeners = [], ownershipKnown = true, stopAfter = false, failAt = "" } = {}) {
  const events = [];
  const logs = [];
  const fail = (label) => {
    if (label === failAt) throw new Error(`simulated:${label}`);
  };
  let receipt = null;
  let error = null;
  try {
    receipt = runPreflightLifecycle({
      args: stopAfter ? ["--stop-after", "--skip-ui"] : ["--skip-ui"],
      inspectLocalServices: () => {
        events.push("probe");
        return { healthy: preExisting, listeners, ownershipKnown };
      },
      runNpmScript: (label, scriptName) => {
        events.push(`npm:${scriptName}`);
        fail(label);
      },
      runPowerShell: (label, scriptPath) => {
        events.push(`ps:${scriptPath}:${label}`);
        fail(label);
      },
      log: (message) => logs.push(message),
    });
  } catch (caught) {
    error = caught;
  }
  return { error, events, logs, receipt };
}

const startedAndStopped = executeScenario({ stopAfter: true });
assert.equal(startedAndStopped.error, null);
assert.deepEqual(startedAndStopped.receipt.services, {
  preExisting: false,
  startedByPreflight: true,
  stoppedByPreflight: true,
});
assert.equal(startedAndStopped.events.at(-1), "ps:scripts/stop-local.ps1:stop local services");

const failureCleanup = executeScenario({ failAt: "server security runtime" });
assert.match(failureCleanup.error?.message ?? "", /simulated:server security runtime/);
assert.equal(failureCleanup.events.at(-1), "ps:scripts/stop-local.ps1:clean up local services after failure");

const startFailureCleanup = executeScenario({ failAt: "start local services" });
assert.match(startFailureCleanup.error?.message ?? "", /simulated:start local services/);
assert.equal(startFailureCleanup.events.at(-1), "ps:scripts/stop-local.ps1:clean up local services after failure");

const preservedSuccess = executeScenario({ preExisting: true, stopAfter: true });
assert.equal(preservedSuccess.error, null);
assert.deepEqual(preservedSuccess.receipt.services, {
  preExisting: true,
  startedByPreflight: false,
  stoppedByPreflight: false,
});
assert.equal(preservedSuccess.events.some((event) => event.includes("start-local.ps1")), false);
assert.equal(preservedSuccess.events.some((event) => event.includes("stop-local.ps1")), false);
assert.equal(preservedSuccess.logs.some((message) => message.includes("did not stop services")), true);

const preservedFailure = executeScenario({ preExisting: true, stopAfter: true, failAt: "server security runtime" });
assert.match(preservedFailure.error?.message ?? "", /simulated:server security runtime/);
assert.equal(preservedFailure.events.some((event) => event.includes("stop-local.ps1")), false);

const partialServices = executeScenario({ listeners: [{ port: 8787, processId: 101 }] });
assert.match(partialServices.error?.message ?? "", /partially or incompatibly occupied/);
assert.equal(partialServices.events.some((event) => event.includes("start-local.ps1")), false);
assert.equal(partialServices.events.some((event) => event.includes("stop-local.ps1")), false);

const unknownOwnership = executeScenario({ ownershipKnown: false });
assert.match(unknownOwnership.error?.message ?? "", /ownership could not be inspected/);
assert.equal(unknownOwnership.events.some((event) => event.includes("start-local.ps1")), false);
assert.equal(unknownOwnership.events.some((event) => event.includes("stop-local.ps1")), false);

const leavesOwnedServicesOnSuccessByDefault = executeScenario();
assert.equal(leavesOwnedServicesOnSuccessByDefault.error, null);
assert.deepEqual(leavesOwnedServicesOnSuccessByDefault.receipt.services, {
  preExisting: false,
  startedByPreflight: true,
  stoppedByPreflight: false,
});

const preflightSource = readFileSync(new URL("./preflight.mjs", import.meta.url), "utf8");
const startLocalSource = readFileSync(new URL("./start-local.ps1", import.meta.url), "utf8");
const localHealthSource = readFileSync(new URL("./local-health.ps1", import.meta.url), "utf8");
const stopLocalSource = readFileSync(new URL("./stop-local.ps1", import.meta.url), "utf8");
const ciWorkflowSource = readFileSync(new URL("../.github/workflows/ci.yml", import.meta.url), "utf8");
const packageJson = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
assert.match(preflightSource, /runPreflightLifecycle\(\{/);
assert.match(preflightSource, /inspectLocalServices/);
assert.doesNotMatch(preflightSource, /process\.exit\(/);
assert.match(packageJson.scripts.verify, /verify:preflight-lifecycle/);
assert.match(startLocalSource, /aibi-local-launcher\/v1/);
assert.match(startLocalSource, /--aibi-local-owner=\$ownerToken/);
assert.match(startLocalSource, /Stop-Process -Id \$process\.Id -Force -ErrorAction SilentlyContinue/);
assert.match(startLocalSource, /-Attempts 1/);
assert.match(localHealthSource, /\[int\]\$Attempts = 5/);
assert.match(localHealthSource, /for \(\$attempt = 1; \$attempt -le \$Attempts; \$attempt \+= 1\)/);
assert.match(localHealthSource, /-TimeoutSec \$RequestTimeoutSeconds/);
assert.match(ciWorkflowSource, /timeout-minutes:\s+60/);
assert.match(stopLocalSource, /\$launcherOwned = \$launcherCommand\.Contains\(\$ownerMarker\)/);
assert.match(stopLocalSource, /repositoryRoot/);
assert.match(stopLocalSource, /if \(\$launcher -and \$launcherOwned\)/);

let legacyPidBehavior = "not-applicable";
if (process.platform === "win32") {
  const fixtureRoot = mkdtempSync(join(resolve(import.meta.dirname, ".."), ".aibi-preflight-legacy-pid-"));
  const fixtureScripts = join(fixtureRoot, "scripts");
  const fixtureLogs = join(fixtureRoot, "logs");
  const fixtureStopScript = join(fixtureScripts, "stop-local.ps1");
  const fixturePidFile = join(fixtureLogs, "aibi-local.pid");
  let ownedHelper = null;
  let unrelatedHelper = null;
  const processExists = (pid) => spawnSync("powershell.exe", ["-NoProfile", "-Command", `if (Get-Process -Id ${pid} -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }`], { windowsHide: true }).status === 0;
  const processCommandLine = (pid) => spawnSync("powershell.exe", ["-NoProfile", "-Command", `(Get-CimInstance Win32_Process -Filter "ProcessId = ${pid}").CommandLine`], { encoding: "utf8", windowsHide: true }).stdout.trim();
  const waitForProcessExit = (pid, timeoutMs = 3000) => {
    const deadline = Date.now() + timeoutMs;
    const waitBuffer = new Int32Array(new SharedArrayBuffer(4));
    while (Date.now() < deadline) {
      if (!processExists(pid)) return true;
      Atomics.wait(waitBuffer, 0, 0, 50);
    }
    return !processExists(pid);
  };
  const stopHelper = (pid) => spawnSync("powershell.exe", ["-NoProfile", "-Command", `Stop-Process -Id ${pid} -Force -ErrorAction SilentlyContinue`], { windowsHide: true });
  try {
    mkdirSync(fixtureScripts, { recursive: true });
    mkdirSync(fixtureLogs, { recursive: true });
    copyFileSync(new URL("./stop-local.ps1", import.meta.url), fixtureStopScript);
    const escapedStopScript = fixtureStopScript.replaceAll("'", "''");
    const fixtureRepositoryMarker = spawnSync("powershell.exe", ["-NoProfile", "-Command", `$scriptDir = Split-Path -Parent '${escapedStopScript}'; (Resolve-Path (Join-Path $scriptDir '..')).Path`], { encoding: "utf8", windowsHide: true }).stdout.trim();
    const escapedRepositoryMarker = fixtureRepositoryMarker.replaceAll("'", "''");
    ownedHelper = spawn("powershell.exe", ["-NoProfile", "-Command", `$null = '${escapedRepositoryMarker}'; Start-Sleep -Seconds 60`], { stdio: "ignore", windowsHide: true });
    unrelatedHelper = spawn("powershell.exe", ["-NoProfile", "-Command", "Start-Sleep -Seconds 60"], { stdio: "ignore", windowsHide: true });
    spawnSync("powershell.exe", ["-NoProfile", "-Command", "Start-Sleep -Milliseconds 250"], { windowsHide: true });
    assert.equal(processExists(ownedHelper.pid), true);
    assert.equal(processExists(unrelatedHelper.pid), true);
    const ownedCommandLine = processCommandLine(ownedHelper.pid);
    assert.equal(ownedCommandLine.toLowerCase().replaceAll("/", "\\").includes(fixtureRepositoryMarker.toLowerCase().replaceAll("/", "\\")), true, ownedCommandLine);

    writeFileSync(fixturePidFile, String(ownedHelper.pid), "utf8");
    const ownedStop = spawnSync("powershell.exe", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", fixtureStopScript, "-ApiPort", "61991", "-UiPort", "61992"], { encoding: "utf8", windowsHide: true });
    assert.equal(ownedStop.status, 0, ownedStop.stderr || ownedStop.stdout);
    assert.equal(waitForProcessExit(ownedHelper.pid), true, `legacy PID owned by the fixture repository must be stopped: ${ownedStop.stdout}`);

    writeFileSync(fixturePidFile, String(unrelatedHelper.pid), "utf8");
    const unrelatedStop = spawnSync("powershell.exe", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", fixtureStopScript, "-ApiPort", "61991", "-UiPort", "61992"], { encoding: "utf8", windowsHide: true });
    assert.equal(unrelatedStop.status, 0, unrelatedStop.stderr || unrelatedStop.stdout);
    assert.equal(processExists(unrelatedHelper.pid), true, "reused legacy PID outside the fixture repository must be preserved");
    assert.match(unrelatedStop.stdout, /failed ownership verification/);
    legacyPidBehavior = "owned-stopped-unrelated-preserved";
  } finally {
    if (ownedHelper?.pid) stopHelper(ownedHelper.pid);
    if (unrelatedHelper?.pid) stopHelper(unrelatedHelper.pid);
    rmSync(fixtureRoot, { recursive: true, force: true });
  }
}

console.log(JSON.stringify({
  ok: true,
  schema: "aibi-preflight-lifecycle-verify/v1",
  checks: [
    "successful --stop-after stops services started by this preflight",
    "post-start failure cleans services started by this preflight",
    "start failure triggers owned cleanup",
    "pre-existing healthy services survive successful --stop-after",
    "pre-existing healthy services survive failed verification",
    "partial or incompatible pre-existing listeners are never modified",
    "unknown ownership blocks lifecycle mutation",
    "launcher PID cleanup requires a repository-scoped ownership token",
    "standalone health checks retry transient API or UI timeouts within a bounded budget",
    "the CI job budget retains headroom for post-verify service and browser gates",
    `legacy PID compatibility is safe: ${legacyPidBehavior}`,
    "successful default preflight retains its services",
    "real preflight entrypoint delegates to the tested lifecycle without eager process exit",
    "main verification includes the lifecycle regression",
  ],
}, null, 2));
