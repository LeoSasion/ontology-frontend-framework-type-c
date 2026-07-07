import { existsSync, mkdtempSync } from "node:fs";
import { readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";

const root = process.cwd();
const aProjectRoot = process.env.AIBI_PROJECT_A_PATH || "C:\\Users\\Administrator\\Documents\\AIBI";
const outputRoot = mkdtempSync(join(tmpdir(), "aibi-erp-unit-library-"));

const erpCases = [
  { key: "wangdian", workspace: "ADV-ERP-072-旺店通订单明细利润物流差异", expected: ["SKU", "利润", "运费", "退款"] },
  { key: "jushuitan", workspace: "ADV-ERP-072-聚水潭订单出库售后对账", expected: ["出库", "售后", "店铺", "退款"] },
  { key: "kingdee", workspace: "ADV-ERP-072-金蝶销售出库应收勾稽", expected: ["应收", "出库", "客户", "订单"] },
  { key: "procurement", workspace: "ADV-ERP-072-采购库存周转供应商履约", expected: ["采购", "库存", "供应商", "周转"] },
];

function normalizePath(value) {
  return resolve(value).replaceAll("\\", "/").toLowerCase();
}

function parseJson(stdout) {
  const raw = String(stdout ?? "");
  const start = raw.indexOf("{");
  if (start < 0) return null;
  try {
    return JSON.parse(raw.slice(start));
  } catch {
    return null;
  }
}

async function readJson(path) {
  try {
    return JSON.parse(await readFile(path, "utf8"));
  } catch {
    return null;
  }
}

function runPython(args, env, timeout = 120000) {
  return spawnSync("python", ["tools/bi_cli.py", "--json", ...args], {
    cwd: root,
    encoding: "utf8",
    env: {
      ...process.env,
      ...env,
      PYTHONIOENCODING: "utf-8",
    },
    timeout,
    windowsHide: true,
  });
}

function runPythonSnippet(source, timeout = 120000) {
  return spawnSync("python", ["-c", source], {
    cwd: root,
    encoding: "utf8",
    env: {
      ...process.env,
      PYTHONIOENCODING: "utf-8",
    },
    timeout,
    windowsHide: true,
  });
}

const publicScenarioRun = runPythonSnippet(String.raw`
import json
import re
import sys

from tools.erp_dashboard_unit_library import (
    ERP_DASHBOARD_UNITS,
    _resolve_unit_for_table,
    build_erp_dashboard_unit_templates,
    build_erp_unit_library_catalog_payload,
)


def slug(value):
    text = re.sub(r"[^0-9a-zA-Z]+", "-", str(value or "")).strip("-").lower()
    return text or "x"


public_scenarios = [
    {
        "key": "retail-pos-member",
        "category": "零售门店/POS",
        "fields": ["门店", "收银员", "导购", "支付方式", "会员编号", "会员等级", "会员积分", "订单号", "销售额", "实付", "促销金额", "优惠券金额", "日期"],
        "expected": ["store-pos-sales-rank", "cashier-performance-rank", "payment-method-mix", "promotion-discount-table", "member-value-table"],
    },
    {
        "key": "apparel-color-size",
        "category": "服装/属性矩阵",
        "fields": ["款式", "颜色", "尺码", "商品编码", "商品名称", "条码", "库存数量", "可销售库存", "仓库", "销售额", "数量"],
        "expected": ["style-color-size-stock-table", "variant-stock-rank", "style-sales-rank", "barcode-trace-table"],
    },
    {
        "key": "cold-chain-batch",
        "category": "批次效期/冷链",
        "fields": ["商品编码", "商品名称", "批次号", "生产日期", "到期日期", "剩余效期", "近效期", "库存数量", "仓库", "温度", "湿度", "冷链", "质检报告", "检验结果", "先进先出"],
        "expected": ["near-expiry-kpi", "expiry-days-rank", "fifo-batch-table", "cold-chain-environment-table", "inspection-report-table"],
    },
    {
        "key": "cross-border-profit",
        "category": "跨境利润核算",
        "fields": ["订单号", "SKU", "ASIN", "店铺", "销售额", "平台佣金", "FBA费用", "广告费", "退货费", "仓储费", "采购成本", "预估利润", "开发员", "费用分摊方式", "商品重量", "商品体积"],
        "expected": ["estimated-profit-kpi", "sku-estimated-profit-rank", "platform-fee-cost-table", "fba-fee-rank", "developer-profit-rank", "fee-allocation-table"],
    },
    {
        "key": "finance-aging",
        "category": "财务往来/账龄",
        "fields": ["客户", "账龄段", "逾期天数", "到期日", "收款计划", "客户余额", "逾期金额", "坏账风险", "凭证号", "会计科目", "部门", "项目", "现金流金额", "日期"],
        "expected": ["ar-aging-overdue-kpi", "ar-aging-rank", "ar-aging-table", "cash-flow-trend", "voucher-subject-table"],
    },
    {
        "key": "manufacturing-quality",
        "category": "制造计划/质量",
        "fields": ["生产订单", "产品", "工作中心", "计划开工日期", "计划完工日期", "实际开工日期", "实际完工日期", "在制数量", "良品数量", "不良数量", "良品率", "BOM版本", "BOM物料", "已领数量", "成本"],
        "expected": ["wip-qty-kpi", "work-center-output-rank", "plan-actual-schedule-table", "yield-rate-rank", "bom-version-slicer", "formula-cost-table"],
    },
]

catalog = build_erp_unit_library_catalog_payload(include_units=False)
receipts = []
for scenario in public_scenarios:
    table = {"table_key": scenario["key"], "display_name": scenario["key"]}
    fields = {"columns": scenario["fields"]}
    payload = build_erp_dashboard_unit_templates([table], {scenario["key"]: fields}, limit=36, slug=slug)
    selected_keys = [item.get("preset", {}).get("erpUnitKey") for item in payload.get("templates", [])]
    candidate_keys = []
    for unit in ERP_DASHBOARD_UNITS:
        resolved = _resolve_unit_for_table(unit, table, fields, slug)
        if resolved:
            candidate_keys.append(str(unit["key"]))
    expected = scenario["expected"]
    candidate_hits = [key for key in expected if key in candidate_keys]
    selected_hits = [key for key in expected if key in selected_keys]
    checks = [
        {
            "label": "expected-units-are-candidates",
            "ok": len(candidate_hits) == len(expected),
            "detail": f"hits={candidate_hits}; expected={expected}",
        },
        {
            "label": "at-least-two-expected-units-selected",
            "ok": len(selected_hits) >= min(2, len(expected)),
            "detail": f"selected_hits={selected_hits}; selected={selected_keys[:12]}",
        },
        {
            "label": "category-coverage-includes-scenario",
            "ok": any(item.get("category") == scenario["category"] for item in payload.get("erpUnitLibrary", {}).get("categoryCoverage", [])),
            "detail": scenario["category"],
        },
    ]
    receipts.append({
        **scenario,
        "candidateUnitCount": len(candidate_keys),
        "selectedUnitCount": len(selected_keys),
        "candidateHits": candidate_hits,
        "selectedHits": selected_hits,
        "checks": checks,
        "failedChecks": [check for check in checks if not check["ok"]],
    })

failed_checks = [
    {"scope": item["key"], **check}
    for item in receipts
    for check in item["failedChecks"]
]
result = {
    "ok": not failed_checks,
    "catalog": catalog,
    "scenarioCount": len(public_scenarios),
    "scenarios": receipts,
    "failedChecks": failed_checks,
}
print(json.dumps(result, ensure_ascii=False, indent=2))
sys.exit(0 if result["ok"] else 1)
`);
const publicScenarioParsed = parseJson(publicScenarioRun.stdout);

const caseReceipts = [];
for (const item of erpCases) {
  const sourcesDir = join(aProjectRoot, "workspaces", item.workspace, "sources");
  const caseOutputDir = join(outputRoot, item.key);
  const env = {
    AIBI_HYBRID_DB_PATH: join(caseOutputDir, "verify.sqlite"),
    AIBI_HYBRID_DUCKDB_PATH: join(caseOutputDir, "verify.duckdb"),
  };
  const sourceRun = runPython(["source-intelligence", sourcesDir, "--label", `verify-erp-units-${item.key}`, "--output-dir", caseOutputDir], env);
  const sourceParsed = parseJson(sourceRun.stdout);
  const manifest = sourceParsed?.manifest ?? await readJson(join(caseOutputDir, "source-intelligence-manifest.json"));
  const libraryRun = runPython(["erp-unit-library", "--select", "--summary", "--limit", "36"], env);
  const libraryParsed = parseJson(libraryRun.stdout);
  const draftRun = runPython(["business-dashboard", "--template", "erp-units", "--op", "draft", "--limit", "24"], env);
  const draftParsed = parseJson(draftRun.stdout);
  const agentRun = runPython(["ask", `基于当前 ${item.expected.join("/")} ERP 数据生成一张经营看板，让 Agent 自己选择需要的组件`], env);
  const agentParsed = parseJson(agentRun.stdout);
  const agentDraftsRun = runPython(["action-drafts", "--limit", "20"], env);
  const agentDraftsParsed = parseJson(agentDraftsRun.stdout);
  const selected = libraryParsed?.selection?.erpUnitLibrary;
  const draftLibrary = draftParsed?.draft?.erpUnitLibrary;
  const agentDashboardDraft = agentDraftsParsed?.actionDrafts?.find((draft) => draft?.action_key === agentParsed?.actionDraft?.actionKey);
  const agentDraftLibrary = agentDashboardDraft?.payload?.dashboardDraft?.erpUnitLibrary;
  const checks = [
    {
      label: "source-folder-exists",
      ok: existsSync(sourcesDir),
      detail: sourcesDir,
    },
    {
      label: "output-stays-outside-project-a",
      ok: !normalizePath(caseOutputDir).startsWith(normalizePath(aProjectRoot)),
      detail: caseOutputDir,
    },
    {
      label: "source-intelligence-ok",
      ok: sourceRun.status === 0 && sourceParsed?.ok === true && manifest?.sourceCount > 0 && manifest?.semanticConfirmationCount > 0,
      detail: `status=${sourceRun.status}; sources=${manifest?.sourceCount}; semantics=${manifest?.semanticConfirmationCount}`,
    },
    {
      label: "unit-library-rich",
      ok: libraryRun.status === 0 &&
        libraryParsed?.catalog?.unitCount >= 150 &&
        libraryParsed?.catalog?.referenceCount >= 45 &&
        libraryParsed?.catalog?.fieldAliasGroupCount >= 240 &&
        libraryParsed?.catalog?.selectionPolicy?.includes("not a fixed"),
      detail: `units=${libraryParsed?.catalog?.unitCount}; references=${libraryParsed?.catalog?.referenceCount}; aliases=${libraryParsed?.catalog?.fieldAliasGroupCount}`,
    },
    {
      label: "unit-selection-present",
      ok: selected?.selectedUnitCount > 0 &&
        selected?.candidateUnitCount >= selected?.selectedUnitCount &&
        Number.isFinite(selected?.unavailableUnitCount) &&
        Array.isArray(selected?.omittedUnitHints) &&
        selected.omittedUnitHints.every((hint) => Array.isArray(hint?.neededFields)) &&
        Array.isArray(libraryParsed?.selection?.templates) &&
        libraryParsed.selection.templates.some((unit) => unit?.preset?.matchedFields && Object.keys(unit.preset.matchedFields).length > 0),
      detail: `selected=${selected?.selectedUnitCount}; candidates=${selected?.candidateUnitCount}; unavailable=${selected?.unavailableUnitCount}`,
    },
    {
      label: "business-dashboard-erp-units-draft",
      ok: draftRun.status === 0 &&
        draftParsed?.ok === true &&
        draftParsed?.draft?.templateKey === "erp-units" &&
        draftParsed?.draft?.widgets?.length > 0 &&
        draftLibrary?.selectedUnitCount > 0 &&
        Array.isArray(draftLibrary?.categoryCoverage),
      detail: `widgets=${draftParsed?.draft?.widgets?.length}; selected=${draftLibrary?.selectedUnitCount}; gaps=${draftLibrary?.unavailableUnitCount}`,
    },
    {
      label: "agent-routes-to-erp-units-dashboard-draft",
      ok: agentRun.status === 0 &&
        agentParsed?.ok === true &&
        agentParsed?.requiresConfirmation === true &&
        agentParsed?.actionDraft?.kind === "dashboard.create" &&
        agentDraftsRun.status === 0 &&
        agentDashboardDraft?.payload?.dashboardDraft?.templateKey === "erp-units" &&
        agentDraftLibrary?.selectedUnitCount > 0 &&
        Array.isArray(agentDraftLibrary?.omittedUnitHints) &&
        Array.isArray(agentDraftLibrary?.categoryCoverage),
      detail: `status=${agentRun.status}; kind=${agentParsed?.actionDraft?.kind}; template=${agentDashboardDraft?.payload?.dashboardDraft?.templateKey}; selected=${agentDraftLibrary?.selectedUnitCount}`,
    },
  ];
  caseReceipts.push({
    ...item,
    sourcesDir,
    outputDir: caseOutputDir,
    manifest: manifest
      ? {
          sourceCount: manifest.sourceCount,
          tableCount: manifest.tableCount,
          semanticConfirmationCount: manifest.semanticConfirmationCount,
          relationshipCount: manifest.relationshipCount,
          metricSqlPlanCount: manifest.metricSqlPlanCount,
          metricSqlExecutableCount: manifest.metricSqlExecutableCount,
        }
      : null,
    selectedUnitCount: selected?.selectedUnitCount ?? 0,
    candidateUnitCount: selected?.candidateUnitCount ?? 0,
    unavailableUnitCount: selected?.unavailableUnitCount ?? 0,
    omittedUnitHintCount: selected?.omittedUnitHints?.length ?? 0,
    widgetCount: draftParsed?.draft?.widgets?.length ?? 0,
    checks,
    failedChecks: checks.filter((check) => !check.ok),
  });
}

const failedChecks = caseReceipts.flatMap((receipt) => receipt.failedChecks.map((check) => ({
  scope: receipt.key,
  workspace: receipt.workspace,
  ...check,
})));
if (publicScenarioRun.status !== 0 || publicScenarioParsed?.ok !== true) {
  failedChecks.push({
    scope: "public-erp-scenarios",
    label: "public-scenario-units",
    ok: false,
    detail: `status=${publicScenarioRun.status}; failed=${JSON.stringify(publicScenarioParsed?.failedChecks ?? [])}; stderr=${publicScenarioRun.stderr}`,
  });
}

const receipt = {
  ok: failedChecks.length === 0,
  generatedBy: "scripts/verify-erp-unit-library.mjs",
  aProjectRoot,
  outputRoot,
  publicScenarios: publicScenarioParsed,
  cases: caseReceipts,
  totals: {
    sourceCount: caseReceipts.reduce((sum, item) => sum + (item.manifest?.sourceCount ?? 0), 0),
    semanticConfirmationCount: caseReceipts.reduce((sum, item) => sum + (item.manifest?.semanticConfirmationCount ?? 0), 0),
    selectedUnitCount: caseReceipts.reduce((sum, item) => sum + item.selectedUnitCount, 0),
    candidateUnitCount: caseReceipts.reduce((sum, item) => sum + item.candidateUnitCount, 0),
    unavailableUnitCount: caseReceipts.reduce((sum, item) => sum + item.unavailableUnitCount, 0),
    omittedUnitHintCount: caseReceipts.reduce((sum, item) => sum + item.omittedUnitHintCount, 0),
    widgetCount: caseReceipts.reduce((sum, item) => sum + item.widgetCount, 0),
  },
  failedChecks,
};

console.log(JSON.stringify(receipt, null, 2));
if (!receipt.ok) process.exit(1);
