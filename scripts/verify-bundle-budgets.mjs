import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

const root = resolve(import.meta.dirname, "..");
const assetsDir = join(root, "dist", "assets");
const configPath = join(root, "config", "bundle-budgets.json");
const config = JSON.parse(readFileSync(configPath, "utf8"));
const assets = readdirSync(assetsDir).map((name) => ({
  name,
  bytes: statSync(join(assetsDir, name)).size,
}));

const checks = config.budgets.map((budget) => {
  const pattern = new RegExp(budget.pattern);
  const matches = assets.filter((asset) => pattern.test(asset.name));
  const largest = matches.reduce((current, asset) => asset.bytes > (current?.bytes ?? -1) ? asset : current, null);
  return {
    label: budget.label,
    ok: matches.length === 1 && largest.bytes <= budget.maxBytes,
    maxBytes: budget.maxBytes,
    matches,
  };
});
const failedChecks = checks.filter((check) => !check.ok);
const receipt = {
  ok: failedChecks.length === 0,
  schema: config.schema,
  generatedBy: "scripts/verify-bundle-budgets.mjs",
  checks,
  failedChecks,
};

console.log(JSON.stringify(receipt, null, 2));
if (failedChecks.length) process.exitCode = 1;
