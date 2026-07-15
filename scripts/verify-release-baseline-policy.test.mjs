import assert from "node:assert/strict";
import { readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import test from "node:test";
import {
  evaluateReleaseBaselineSamples,
  nearestRankPercentile,
  needsTailConfirmation,
} from "./verify-release-baseline.mjs";

const budgets = { p50BudgetMs: 1500, p95BudgetMs: 3500 };
const tempBaselineDirectories = () => readdirSync(tmpdir()).filter((name) => name.startsWith("aibi-c-release-baseline-")).sort();

test("the observed GitHub Runner jitter stays inside the split steady-state and tail budgets", () => {
  const observed = [848.3, 897, 876, 2691.3, 1843.7, 1219.3, 1196.9];
  const result = evaluateReleaseBaselineSamples(observed, budgets);
  assert.equal(result.ok, true);
  assert.equal(result.p50Ms, 1196.9);
  assert.equal(result.p95Ms, 2691.3);
  assert.equal(result.steadyStatePassed, true);
  assert.equal(result.tailPassed, true);
});

test("a steady-state regression fails immediately and is never diluted with extra samples", () => {
  const result = evaluateReleaseBaselineSamples([1600, 1610, 1620, 1630, 1640, 1650, 1660, 1670, 1680], budgets);
  assert.equal(result.steadyStatePassed, false);
  assert.equal(result.ok, false);
  assert.equal(needsTailConfirmation(result, 9), false);
});

test("one initial tail outlier triggers confirmation and one outlier among twenty does not define p95", () => {
  const initial = [900, 910, 920, 930, 940, 950, 960, 970, 4100];
  const initialResult = evaluateReleaseBaselineSamples(initial, budgets);
  assert.equal(initialResult.steadyStatePassed, true);
  assert.equal(initialResult.tailPassed, false);
  assert.equal(needsTailConfirmation(initialResult, initial.length), true);

  const confirmed = [...initial, 980, 990, 1000, 1010, 1020, 1030, 1040, 1050, 1060, 1070, 1080];
  const confirmedResult = evaluateReleaseBaselineSamples(confirmed, budgets);
  assert.equal(confirmedResult.p95Ms, 1080);
  assert.equal(confirmedResult.tailOverBudgetCount, 1);
  assert.equal(confirmedResult.ok, true);
});

test("two tail outliers among twenty still fail the nearest-rank p95 gate", () => {
  const samples = [
    900, 910, 920, 930, 940, 950, 960, 970, 980, 990,
    1000, 1010, 1020, 1030, 1040, 1050, 1060, 1070, 4100, 4300,
  ];
  const result = evaluateReleaseBaselineSamples(samples, budgets);
  assert.equal(nearestRankPercentile(samples, 0.95), 4100);
  assert.equal(result.steadyStatePassed, true);
  assert.equal(result.tailOverBudgetCount, 2);
  assert.equal(result.tailPassed, false);
  assert.equal(result.ok, false);
});

test("an invalid budget emits a structured failure without creating a temporary runtime", () => {
  const before = tempBaselineDirectories();
  const result = spawnSync(process.execPath, [fileURLToPath(new URL("./verify-release-baseline.mjs", import.meta.url))], {
    env: { ...process.env, AIBI_QUERY_P50_BUDGET_MS: "invalid-release-budget" },
    encoding: "utf8",
    windowsHide: true,
  });
  const after = tempBaselineDirectories();
  assert.equal(result.status, 1);
  assert.equal(result.stdout, "");
  const receipt = JSON.parse(result.stderr.trim());
  assert.equal(receipt.ok, false);
  assert.equal(receipt.schema, "aibi-release-baseline/v1");
  assert.match(receipt.error, /AIBI_QUERY_P50_BUDGET_MS must be a positive number/);
  assert.deepEqual(after, before);
});
