import { spawnSync } from "node:child_process";

const nodeCommand = process.execPath;
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

function runNode(label, scriptPath, scriptArgs = []) {
  runCommand(label, nodeCommand, [scriptPath, ...scriptArgs]);
}

function runPowerShell(label, scriptPath) {
  runCommand(label, powershellCommand, ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", scriptPath]);
}

runNode("TypeScript build", "node_modules/typescript/bin/tsc", ["-p", "tsconfig.json"]);
runNode("Vite production build", "node_modules/vite/bin/vite.js", ["build"]);
runNode("core verification", "scripts/verify.mjs");
runNode("BI CLI Agent contract", "scripts/verify-bi-cli-agent-contract.mjs");
runNode("AI one-chart reliability", "scripts/verify-ai-chart-reliability.mjs");
runNode("workspace landing flow", "node_modules/tsx/dist/cli.mjs", ["scripts/verify-workspace-flow.ts"]);
runNode("local backup and restore", "scripts/verify-local-backup.mjs");
runNode("production readiness", "scripts/verify-production-readiness.mjs");
runPowerShell("start local services", "scripts/start-local.ps1");
runPowerShell("health check", "scripts/local-health.ps1");
runNode("server security runtime", "scripts/verify-server-runtime-security.mjs");

if (skipUi) {
  console.log("\n[preflight] UI verification skipped by --skip-ui.");
} else {
  runNode("UI flow verification", "scripts/verify-ui-flow.mjs");
  runNode("UI visual verification", "scripts/verify-ui-visual.mjs");
  runNode("empty workspace verification", "scripts/verify-ui-empty-workspace.mjs");
  runNode("real import verification", "scripts/verify-ui-real-import.mjs");
  runPowerShell("final health check", "scripts/local-health.ps1");
}

if (stopAfter) {
  runPowerShell("stop local services", "scripts/stop-local.ps1");
}

console.log("\n[preflight] AIBI-C is ready.");
