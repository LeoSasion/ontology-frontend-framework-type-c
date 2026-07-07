import { existsSync, mkdtempSync, readdirSync, statSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";

const root = process.cwd();
const outputRoot = mkdtempSync(join(tmpdir(), "aibi-a-adversarial-source-intelligence-"));
const aProjectRoot = process.env.AIBI_PROJECT_A_PATH || "C:\\Users\\Administrator\\Documents\\AIBI";
const experiencePath = join(aProjectRoot, "AIBI-skills", "source-intelligence-experience.md");
const erpBatchManifestPath = join(aProjectRoot, "testtemp", "sandbox-practice-assets", "batch-072-cn-erp-adversarial", "batch-manifest.json");
const erpRunSummaryPath = join(aProjectRoot, "testtemp", "sandbox-practice-assets", "_long-cycle-runs", "erp-adversarial-2026-07-05-b072", "final-summary.json");
const supportedSuffixes = new Set([".csv", ".xls", ".xlsx"]);

const adversarialCases = [
  { key: "used-car", workspace: "ADV-CN-012-二手车", risk: "object grain and refund/repair amount direction" },
  { key: "tuition-package", workspace: "ADV-CN-011-教培课包", risk: "contract object, consumption grain, and refund matching" },
  { key: "cross-border-logistics", workspace: "ADV-CN-013-跨境仓配", risk: "package/order key selection and fee attribution" },
  { key: "private-membership", workspace: "ADV-LONG-021-私域会员储值履约", risk: "cash, liability, gift benefit, and fulfillment separation" },
  { key: "erp-wangdian-profit-logistics", workspace: "ADV-ERP-072-旺店通订单明细利润物流差异", risk: "gift/refund status, SKU profit, and freight bill variance" },
  { key: "erp-jushuitan-outbound-refund", workspace: "ADV-ERP-072-聚水潭订单出库售后对账", risk: "sub-order grain, fee text extraction, refund success, and gift cost" },
  { key: "erp-kingdee-ar-reconcile", workspace: "ADV-ERP-072-金蝶销售出库应收勾稽", risk: "outbound aggregation, audited red AR, paid/unpaid AR, and gap direction" },
  { key: "erp-procurement-inventory", workspace: "ADV-ERP-072-采购库存周转供应商履约", risk: "sellable inventory, successful returns, aging threshold, and supplier risk" },
];

function normalizePath(value) {
  return resolve(value).replaceAll("\\", "/").toLowerCase();
}

function walkSupportedFiles(dir) {
  if (!existsSync(dir)) return [];
  const files = [];
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    const stats = statSync(path);
    if (stats.isDirectory()) {
      files.push(...walkSupportedFiles(path));
    } else {
      const extension = name.includes(".") ? name.slice(name.lastIndexOf(".")).toLowerCase() : "";
      if (supportedSuffixes.has(extension)) files.push(path);
    }
  }
  return files;
}

async function readJson(path) {
  try {
    return JSON.parse(await readFile(path, "utf8"));
  } catch {
    return null;
  }
}

function parseStdoutJson(stdout) {
  try {
    return JSON.parse(stdout.trim());
  } catch {
    return null;
  }
}

function runSourceIntelligence({ caseOutputDir, label, sourcesDir }) {
  return spawnSync(
    "python",
    ["tools/bi_cli.py", "--json", "source-intelligence", sourcesDir, "--label", label, "--output-dir", caseOutputDir],
    {
      cwd: root,
      encoding: "utf8",
      env: {
        ...process.env,
        AIBI_HYBRID_DB_PATH: join(caseOutputDir, "verify.sqlite"),
        AIBI_HYBRID_DUCKDB_PATH: join(caseOutputDir, "verify.duckdb"),
        PYTHONIOENCODING: "utf-8",
      },
      timeout: 120000,
      windowsHide: true,
    },
  );
}

const experienceText = existsSync(experiencePath) ? await readFile(experiencePath, "utf8") : "";
const erpBatchManifest = await readJson(erpBatchManifestPath);
const erpRunSummary = await readJson(erpRunSummaryPath);
const experienceChecks = [
  {
    label: "experience-file-exists",
    ok: existsSync(experiencePath),
    detail: experiencePath,
  },
  {
    label: "experience-keeps-workspace-boundary",
    ok: experienceText.includes("不能把其他 workspace") &&
      experienceText.includes("必须先检查当前 workspace") &&
      experienceText.includes("不能把训练资产池、测试答案或 Codex 裁判结论暴露成用户业务数据"),
    detail: "A experience rules keep training assets separate from user facts.",
  },
  {
    label: "experience-covers-adversarial-risks",
    ok: experienceText.includes("many-to-many") &&
      experienceText.includes("金额方向") &&
      experienceText.includes("不能直接明细 join 求和") &&
      experienceText.includes("需要用户确认的口径"),
    detail: "A experience rules include grain, amount direction, join, and confirmation risks.",
  },
  {
    label: "erp-batch-manifest-available",
    ok: erpBatchManifest?.batchName === "batch-072-cn-erp-adversarial" &&
      erpBatchManifest?.assetCount === 4 &&
      Array.isArray(erpBatchManifest?.assets) &&
      erpBatchManifest.assets.every((asset) => String(asset.workspace ?? "").startsWith("ADV-ERP-072-")),
    detail: erpBatchManifestPath,
  },
  {
    label: "erp-long-cycle-summary-available",
    ok: erpRunSummary?.runId === "erp-adversarial-2026-07-05-b072" &&
      erpRunSummary?.lastPassedBatch === "batch-072-cn-erp-adversarial" &&
      erpRunSummary?.sandboxAssetsPassed === 4 &&
      erpRunSummary?.businessChecksReplayed === 8 &&
      erpRunSummary?.fieldComparisonsReplayed === 17,
    detail: erpRunSummaryPath,
  },
];

const caseReceipts = [];
for (const testCase of adversarialCases) {
  const sourcesDir = join(aProjectRoot, "workspaces", testCase.workspace, "sources");
  const caseOutputDir = join(outputRoot, testCase.key);
  const expectedFiles = walkSupportedFiles(sourcesDir);
  const result = runSourceIntelligence({
    caseOutputDir,
    label: `verify-a-adversarial-${testCase.key}`,
    sourcesDir,
  });
  const parsed = parseStdoutJson(result.stdout);
  const manifest = parsed?.manifest ?? await readJson(join(caseOutputDir, "source-intelligence-manifest.json"));
  const evidenceFiles = Array.isArray(parsed?.evidenceFiles) ? parsed.evidenceFiles : [];
  const checks = [
    {
      label: "source-folder-exists",
      ok: existsSync(sourcesDir) && expectedFiles.length > 0,
      detail: `${sourcesDir}; expectedFiles=${expectedFiles.length}`,
    },
    {
      label: "output-stays-outside-project-a",
      ok: !normalizePath(caseOutputDir).startsWith(normalizePath(aProjectRoot)),
      detail: caseOutputDir,
    },
    {
      label: "command-exit-ok",
      ok: result.status === 0 && parsed?.ok === true,
      detail: result.stderr || result.stdout.slice(0, 500),
    },
    {
      label: "all-supported-sources-read",
      ok: manifest?.sourceCount === expectedFiles.length && manifest?.tableCount >= expectedFiles.length && manifest?.skippedTableCount === 0,
      detail: `expected=${expectedFiles.length}; sourceCount=${manifest?.sourceCount}; tableCount=${manifest?.tableCount}; skipped=${manifest?.skippedTableCount}`,
    },
    {
      label: "semantic-and-relationship-evidence",
      ok: manifest?.fieldCandidateCount > 0 && manifest?.semanticConfirmationCount > 0 && manifest?.relationshipCount > 0,
      detail: `fieldCandidateCount=${manifest?.fieldCandidateCount}; semanticConfirmationCount=${manifest?.semanticConfirmationCount}; relationshipCount=${manifest?.relationshipCount}`,
    },
    {
      label: "adversarial-gap-boundary",
      ok: manifest?.dataGapCount > 0 && manifest?.metricSqlPlanCount > 0 && manifest?.metricSqlExecutableCount < manifest?.metricSqlPlanCount,
      detail: `dataGapCount=${manifest?.dataGapCount}; metricSqlPlanCount=${manifest?.metricSqlPlanCount}; metricSqlExecutableCount=${manifest?.metricSqlExecutableCount}`,
    },
    {
      label: "evidence-receipts-written",
      ok: evidenceFiles.includes("source-profile-generic.json") &&
        evidenceFiles.includes("semantic-field-candidates.json") &&
        evidenceFiles.includes("relationship-discovery.json") &&
        evidenceFiles.includes("metric-sql-compiler.json") &&
        evidenceFiles.includes("metric-query-results.json"),
      detail: evidenceFiles.join(","),
    },
  ];
  caseReceipts.push({
    ...testCase,
    sourcesDir,
    outputDir: caseOutputDir,
    manifest: manifest
      ? {
          sourceCount: manifest.sourceCount,
          tableCount: manifest.tableCount,
          skippedTableCount: manifest.skippedTableCount,
          fieldCandidateCount: manifest.fieldCandidateCount,
          semanticConfirmationCount: manifest.semanticConfirmationCount,
          relationshipCount: manifest.relationshipCount,
          dataGapCount: manifest.dataGapCount,
          metricSqlPlanCount: manifest.metricSqlPlanCount,
          metricSqlExecutableCount: manifest.metricSqlExecutableCount,
        }
      : null,
    checks,
    failedChecks: checks.filter((check) => !check.ok),
  });
}

const failedChecks = [
  ...experienceChecks.filter((check) => !check.ok).map((check) => ({ scope: "experience", ...check })),
  ...caseReceipts.flatMap((receipt) => receipt.failedChecks.map((check) => ({
    scope: receipt.key,
    workspace: receipt.workspace,
    ...check,
  }))),
];

const receipt = {
  ok: failedChecks.length === 0,
  generatedBy: "scripts/verify-a-adversarial-source-intelligence.mjs",
  aProjectRoot,
  outputRoot,
  experiencePath,
  erpBatchManifestPath,
  erpRunSummaryPath,
  experienceChecks,
  cases: caseReceipts,
  failedChecks,
};

console.log(JSON.stringify(receipt, null, 2));
if (!receipt.ok) process.exit(1);
