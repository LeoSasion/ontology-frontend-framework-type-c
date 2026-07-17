import { mkdtempSync, rmSync } from "node:fs";
import { join } from "node:path";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { multiDomainBetaFixtures, writeMultiDomainBetaFixtures } from "./multi-domain-beta-fixtures.mjs";

const root = process.cwd();
const runRoot = mkdtempSync(join(tmpdir(), "aibi-c-multi-domain-beta-"));
const fixtureRoot = join(runRoot, "fixtures");
const fixtures = writeMultiDomainBetaFixtures(fixtureRoot);
const receipts = [];

function runCli(env, args) {
  const result = spawnSync("python", ["tools/aibi_cli.py", "--json", ...args], {
    cwd: root,
    env: { ...process.env, ...env, PYTHONIOENCODING: "utf-8" },
    encoding: "utf8",
    windowsHide: true,
    maxBuffer: 32 * 1024 * 1024,
  });
  let parsed = null;
  try {
    parsed = JSON.parse(result.stdout.trim());
  } catch {
    parsed = null;
  }
  return { ok: result.status === 0 && parsed?.ok === true, status: result.status, parsed, stderr: result.stderr, stdout: result.stdout };
}

function columnNames(fixture) {
  return fixture.csv.split(/\r?\n/, 1)[0].split(",");
}

function selectedUnitKeys(draft) {
  return (draft?.templates ?? []).map((item) => item?.preset?.erpUnitKey).filter(Boolean);
}

function widgetFields(widget) {
  return [widget?.measure, widget?.dimension, widget?.group, widget?.timeField]
    .filter((value) => typeof value === "string" && value && value !== "*");
}

function check(label, ok, detail = "") {
  return { label, ok: Boolean(ok), detail: ok ? "" : detail };
}

function executeDomain(fixture, iteration) {
  const domainRoot = join(runRoot, `${fixture.key}-${iteration}`);
  const env = {
    AIBI_HYBRID_DB_PATH: join(domainRoot, "runtime.sqlite"),
    AIBI_HYBRID_DUCKDB_PATH: join(domainRoot, "runtime.duckdb"),
    AIBI_EVIDENCE_BUNDLE_ROOT: join(domainRoot, "evidence"),
  };
  const checks = [];
  const columns = columnNames(fixture);
  const tableKey = fixture.key.replace(/-/g, "_");
  const imported = runCli(env, [
    "import-commit", fixture.path,
    "--table", tableKey,
    "--name", fixture.name,
    "--mode", "create",
    "--yes",
  ]);
  checks.push(check("real-import", imported.ok, imported.parsed ?? imported.stderr));

  const generic = runCli(env, ["ask", "请概览当前数据", "--read-only"]);
  const genericText = JSON.stringify(generic.parsed?.answerCard ?? {});
  checks.push(check(
    "generic-question-does-not-use-domain-default-fields",
    generic.ok && !fixture.forbiddenForeignFields.some((field) => genericText.includes(field)),
    generic.parsed?.answerCard,
  ));

  const seedDashboard = runCli(env, [
    "business-dashboard", "--op", "create", "--table", tableKey,
    "--name", `${fixture.name}单图容器`, "--limit", "1", "--yes",
  ]);
  checks.push(check("single-chart-container-created", seedDashboard.ok && seedDashboard.parsed?.savedDashboardModules === 1, seedDashboard.parsed));

  const explicit = runCli(env, ["ask", `请用 ${fixture.measure} 按 ${fixture.dimension} 生成一个柱状图`]);
  const explicitQuery = explicit.parsed?.answerCard?.query;
  const actionKey = explicit.parsed?.actionDraft?.actionKey;
  checks.push(check(
    "explicit-single-chart-uses-requested-fields",
    explicit.ok && explicit.parsed?.requiresConfirmation === true && explicitQuery?.measure === fixture.measure && explicitQuery?.group === fixture.dimension && actionKey,
    { query: explicitQuery, actionDraft: explicit.parsed?.actionDraft },
  ));
  const explicitConfirm = actionKey ? runCli(env, ["confirm-action", actionKey, "--yes"]) : { ok: false, parsed: null };
  checks.push(check("explicit-single-chart-confirms-once", explicitConfirm.ok && explicitConfirm.parsed?.confirmed === true && (explicitConfirm.parsed?.addedWidget || explicitConfirm.parsed?.savedDashboardModules === 1), explicitConfirm.parsed));

  const packEnable = runCli(env, [
    "domain-pack-set", "--pack", "erp-units", "--state", "enabled", "--yes",
  ]);
  checks.push(check(
    "erp-domain-pack-is-explicitly-enabled",
    packEnable.ok && packEnable.parsed?.enabledDomainPacks?.some((item) => item?.packId === "erp-units"),
    packEnable.parsed ?? packEnable.stderr,
  ));

  const betaDraft = runCli(env, [
    "business-dashboard", "--op", "draft", "--table", tableKey,
    "--template", "erp-units", "--limit", "12",
  ]);
  const draft = betaDraft.parsed?.draft;
  const selected = selectedUnitKeys(draft);
  const omittedHints = draft?.erpUnitLibrary?.omittedUnitHints ?? [];
  const omittedKeys = new Set(omittedHints.map((item) => item?.key));
  const renderedFields = (draft?.widgets ?? []).flatMap(widgetFields);
  const expectedHits = fixture.expectedUnitKeys.filter((key) => selected.includes(key));
  checks.push(
    check("beta-draft-is-source-backed", betaDraft.ok && draft?.widgets?.length > 0 && draft.widgets.length === selected.length, { selected, widgetCount: draft?.widgets?.length }),
    check("domain-specific-units-are-selected", expectedHits.length >= 2, { expected: fixture.expectedUnitKeys, selected }),
    check("selected-widgets-only-use-present-fields", renderedFields.every((field) => columns.includes(field)), { columns, renderedFields }),
    check("missing-field-units-are-omitted-with-reasons", omittedHints.length > 0 && omittedHints.every((item) => item?.missingRoles?.length > 0 && item?.neededFields?.length > 0), omittedHints.slice(0, 5)),
    check("omitted-units-are-not-rendered", selected.every((key) => !omittedKeys.has(key)), { selected, omitted: [...omittedKeys].slice(0, 20) }),
    check("foreign-domain-fields-never-render", !fixture.forbiddenForeignFields.some((field) => JSON.stringify(draft?.widgets ?? []).includes(field)), fixture.forbiddenForeignFields),
  );

  const betaConfirm = runCli(env, [
    "business-dashboard", "--op", "create", "--table", tableKey,
    "--template", "erp-units", "--limit", "12", "--name", `${fixture.name} Beta`, "--yes",
  ]);
  const dashboardKey = betaConfirm.parsed?.savedDashboardKey;
  const persisted = dashboardKey ? runCli(env, ["dashboards", "--dashboard", dashboardKey]) : { ok: false, parsed: null };
  const persistedWidgets = persisted.parsed?.dashboards?.[0]?.widgets ?? [];
  checks.push(
    check("beta-dashboard-confirms-once", betaConfirm.ok && betaConfirm.parsed?.confirmed === true, betaConfirm.parsed),
    check("persisted-widget-count-matches-reviewed-draft", persisted.ok && persistedWidgets.length === draft?.widgets?.length && betaConfirm.parsed?.savedDashboardModules === draft?.widgets?.length, { persisted: persistedWidgets.length, draft: draft?.widgets?.length, saved: betaConfirm.parsed?.savedDashboardModules }),
    check("persisted-dashboard-does-not-materialize-omissions", omittedHints.every((hint) => !persistedWidgets.some((widget) => widget?.config?.erpUnitKey === hint?.key)), { persistedKeys: persistedWidgets.map((widget) => widget?.config?.erpUnitKey).filter(Boolean) }),
  );
  return {
    domain: fixture.key,
    iteration,
    columns,
    selectedUnitKeys: selected,
    omittedUnitCount: omittedHints.length,
    widgetCount: draft?.widgets?.length ?? 0,
    checks,
  };
}

try {
  for (const fixture of fixtures) {
    receipts.push(executeDomain(fixture, 1));
    receipts.push(executeDomain(fixture, 2));
  }
  for (const fixture of multiDomainBetaFixtures) {
    const runs = receipts.filter((item) => item.domain === fixture.key);
    const stable = runs.length === 2 && JSON.stringify(runs[0].selectedUnitKeys) === JSON.stringify(runs[1].selectedUnitKeys);
    for (const run of runs) run.checks.push(check("repeated-selection-is-deterministic", stable, runs.map((item) => item.selectedUnitKeys)));
  }
  const domainColumns = fixtures.map((fixture) => new Set(columnNames(fixture)));
  const overlap = [...domainColumns[0]].filter((field) => domainColumns[1].has(field));
  receipts[0]?.checks.push(check("domains-are-structurally-distinct", overlap.length <= 1, overlap));
} finally {
  rmSync(runRoot, { recursive: true, force: true });
}

const allChecks = receipts.flatMap((item) => item.checks.map((entry) => ({ domain: item.domain, iteration: item.iteration, ...entry })));
const failedChecks = allChecks.filter((item) => !item.ok);
console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-multi-domain-beta-verify/v1",
  generatedBy: "scripts/verify-multi-domain-beta.mjs",
  domainCount: new Set(receipts.map((item) => item.domain)).size,
  repeatedRunCount: receipts.length,
  receipts,
  failedChecks,
}, null, 2));
process.exit(failedChecks.length ? 1 : 0);
