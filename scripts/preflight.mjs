import { spawnSync } from "node:child_process";

const npmCommand = process.platform === "win32" ? process.env.ComSpec ?? "cmd.exe" : "npm";
const npmPrefixArgs = process.platform === "win32" ? ["/d", "/s", "/c", "npm"] : [];
const powershellCommand = process.platform === "win32" ? "powershell.exe" : "pwsh";
const args = new Set(process.argv.slice(2));
const skipUi = args.has("--skip-ui");
const stopAfter = args.has("--stop-after");

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
    process.exit(result.status ?? 1);
  }
  console.log(`[preflight] ${label} passed in ${seconds}s.`);
}

function runNpmScript(label, scriptName) {
  runCommand(label, npmCommand, [...npmPrefixArgs, "run", scriptName]);
}

function runPowerShell(label, scriptPath) {
  runCommand(label, powershellCommand, ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", scriptPath]);
}

runNpmScript("production build and bundle budgets", "build");
runNpmScript("core, CLI, and AI verification", "verify");
runNpmScript("workspace landing flow", "verify:workspace-flow");
runNpmScript("local backup and restore", "verify:backup");
runNpmScript("local schema migration and rollback", "verify:migration");
runNpmScript("multi-domain Beta repeatability", "verify:multi-domain-beta");
runNpmScript("local query release baseline", "verify:release-baseline");
runNpmScript("production readiness", "verify:production");
runPowerShell("start local services", "scripts/start-local.ps1");
runPowerShell("health check", "scripts/local-health.ps1");
runNpmScript("server security runtime", "verify:security-runtime");

if (skipUi) {
  console.log("\n[preflight] UI verification skipped by --skip-ui.");
} else {
  runNpmScript("complete UI verification", "verify:ui");
  runPowerShell("final health check", "scripts/local-health.ps1");
}

if (stopAfter) {
  runPowerShell("stop local services", "scripts/stop-local.ps1");
}

console.log("\n[preflight] AIBI-C is ready.");
