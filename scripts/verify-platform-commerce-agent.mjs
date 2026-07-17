import { existsSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { basename, join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { writePlatformCommerceFixtures } from "./platform-commerce-fixtures.mjs";

function option(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? String(process.argv[index + 1] ?? "").trim() : "";
}

const reportDir = option("--report-dir") ? resolve(option("--report-dir")) : "";
const verifyDir = mkdtempSync(join(tmpdir(), "aibi-platform-commerce-"));
const templatesDir = join(verifyDir, "fixtures");
const validationSource = "generated:AIBI-C/scripts/platform-commerce-fixtures.mjs";
const generatedFixtures = writePlatformCommerceFixtures(templatesDir);
const env = {
  ...process.env,
  AIBI_HYBRID_DB_PATH: join(verifyDir, "runtime.sqlite"),
  AIBI_HYBRID_DUCKDB_PATH: join(verifyDir, "runtime.duckdb"),
  AIBI_EVIDENCE_BUNDLE_ROOT: join(verifyDir, "evidence"),
  PYTHONIOENCODING: "utf-8",
};

const imports = [
  ["douyin_orders_synthetic.csv", "douyin_orders", "抖音订单"],
  ["douyin_aftersales_synthetic.csv", "douyin_aftersales", "抖音售后"],
  ["douyin_logistics_synthetic.csv", "douyin_logistics", "抖音物流"],
  ["taobao_trades_synthetic.csv", "taobao_trades", "淘宝主单"],
  ["taobao_order_items_synthetic.csv", "taobao_order_items", "淘宝子单"],
  ["taobao_refunds_synthetic.csv", "taobao_refunds", "淘宝退款"],
  ["taobao_logistics_synthetic.csv", "taobao_logistics", "淘宝物流"],
  ["jushuitan_orders_versioned_synthetic.csv", "jushuitan_orders", "聚水潭订单版本"],
  ["jushuitan_order_items_synthetic.csv", "jushuitan_order_items", "聚水潭订单商品"],
  ["jushuitan_outbounds_synthetic.csv", "jushuitan_outbounds", "聚水潭销售出库"],
  ["jushuitan_aftersales_synthetic.csv", "jushuitan_aftersales", "聚水潭售后"],
  ["jushuitan_logistics_synthetic.csv", "jushuitan_logistics", "聚水潭物流"],
];

const cases = [
  {
    id: "douyin-successful-refunds",
    prompt: "只统计退款成功且退商品金额大于0的售后，退款商品金额、退款成功总额和记录数是多少？",
    expected: { 退款商品金额: 441, 退款成功总额: 447, 成功退款记录数: 4 },
  },
  {
    id: "douyin-refund-by-merchant",
    prompt: "按商家编码统计退款成功商品退款额前十名，退款率分母用已支付商品单数。",
    expected: {
      "SHOE-38退款金额": 179,
      "RED-M退款金额": 119,
      "WHITE-S退款金额": 94,
      "HAT-FREE退款金额": 49,
      "SHOE-38退款率": 1,
      "RED-M退款率": 1,
      "WHITE-S退款率": 1,
      "HAT-FREE退款率": 1,
    },
  },
  { id: "douyin-package-count", prompt: "DY-M002 有几个包裹？", expected: { 包裹数: 2 } },
  {
    id: "douyin-logistics-exception-summary",
    prompt: "找出一单多包裹和没有物流但属于虚拟商品的订单，不要把虚拟商品判异常。",
    expected: { 一单多包裹订单数: 1, 合法虚拟商品空运单: 1, 虚拟商品误判异常数: 0 },
  },
  {
    id: "douyin-virtual-logistics-exception",
    prompt: "找出没有物流但属于虚拟商品的订单，不要把虚拟商品判为未发货。",
    expected: { 合法空运单: 1, 应判未发货: 0 },
  },
  {
    id: "douyin-deduplicated-main-order-amount",
    prompt: "主单应付金额在商品明细会重复，请按主单去重并排除已关闭订单，计算有效主单金额。",
    expected: { 有效主单金额: 1200.9, 有效主单数: 7 },
  },
  {
    id: "taobao-successful-refunds",
    prompt: "status=SUCCESS 的退款金额和退款单数是多少？",
    expected: { 成功退款金额: 357, 成功退款单数: 3 },
  },
  { id: "taobao-package-count", prompt: "TB-T004 有多少条物流单？", expected: { 物流单数: 2 } },
  {
    id: "taobao-split-logistics-list",
    prompt: "列出拆单发货主订单及其运单数量。",
    expected: { 拆单主订单数: 1, "TB-T004运单数": 2 },
  },
  {
    id: "taobao-closed-order-types",
    prompt: "统计关闭订单，并区分付款前关闭和付款后退款关闭。",
    expected: { 关闭订单总数: 2, 付款前关闭: 1, 付款后关闭: 1 },
  },
  { id: "taobao-closed-order-shipping", prompt: "TB-T003 已关闭，还可以发货吗？", expected: { 可发货: 0 } },
  {
    id: "taobao-paid-nonclosed-amount",
    prompt: "已支付且未关闭主单 payment 合计是多少？",
    expected: { 已支付未关闭主单金额: 1042.9 },
  },
  {
    id: "taobao-net-after-successful-refund",
    prompt: "已支付且未关闭主单 payment 扣除成功退款后的净额是多少？",
    expected: { 已支付未关闭金额: 1042.9, 成功退款金额: 357, 退款后净额: 685.9 },
  },
  {
    id: "jushuitan-latest-platform-amount",
    prompt: "先按o_id保留最大ts版本，再统计各来源平台的实付金额，不能重复累计历史版本。",
    expected: { 抖音实付金额: 545, 淘宝实付金额: 865, 自有商城实付金额: 88, 最新订单数: 8 },
  },
  {
    id: "jushuitan-latest-order-version",
    prompt: "先按 o_id 保留最大ts版本，核对最新版本订单数、取消数、金额和历史版本重复差额。",
    expected: { 最新订单记录数: 8, 取消订单数: 1, 原始版本金额: 1774, 最新订单金额: 1498, 重复版本差额: 276 },
  },
  {
    id: "jushuitan-multi-package-threshold",
    prompt: "一单多包裹率是否超过20%？",
    expected: { 一单多包裹率: 2 / 7, 阈值: 0.2, 是否超过阈值: 1 },
  },
  {
    id: "jushuitan-warehouse-carrier-performance",
    prompt: "按仓库和物流公司统计销售出库包裹数、订单数和一单多包裹率。",
    expected: {
      "华东仓/中通快递包裹数": 2,
      "华东仓/京东快递包裹数": 1,
      "华东仓/顺丰速运包裹数": 2,
      "华南仓/圆通速递包裹数": 2,
      "华南仓/顺丰速运包裹数": 2,
      一单多包裹率: 2 / 7,
    },
  },
  {
    id: "jushuitan-outbound-packages",
    prompt: "销售出库覆盖多少订单？有多少包裹和一单多包裹订单？",
    expected: { 销售出库单数: 9, 覆盖订单数: 7, 一单多包裹订单数: 2, "JST-O002包裹数": 2, "JST-O004包裹数": 2 },
  },
  {
    id: "jushuitan-confirmed-refunds-by-merchant",
    prompt: "按商家编码关联订单商品与售后，统计已确认退款金额，并说明无法唯一归属的订单数。",
    expected: {
      "RED-M已确认退款金额": 238,
      "WHITE-S已确认退款金额": 94,
      "HAT-FREE已确认退款金额": 49,
      "SHOE-38已确认退款金额": 189,
      可归属退款总额: 570,
      无法唯一归属订单数: 0,
    },
  },
  {
    id: "jushuitan-confirmed-refunds",
    prompt: "已确认且退款金额大于0的售后有多少单，退款合计是多少？",
    expected: { 已确认退款金额: 570, 已确认退款单数: 5 },
  },
  {
    id: "jushuitan-logistics-issue-trace",
    prompt: "找出物流回传失败或待处理的订单，并显示平台线上单号so_id。",
    expected: { 物流异常记录数: 2, "Pending:JST-O002/DY-M002": 1, "Failed:JST-O005/TB-T006": 1 },
  },
  {
    id: "jushuitan-logistics-sync-status",
    prompt: "物流同步失败和待处理分别有多少条？",
    expected: { 同步失败: 1, 待处理: 1 },
  },
  {
    id: "non-metric-knowledge-rule-cannot-authorize-rate",
    prompt: "虚拟商品未发货率",
    expectedBlocked: true,
    expectedKnowledgeMatch: true,
    expected: {},
  },
  {
    id: "unsupported-refund-rate-is-blocked",
    prompt: "按月份计算跨平台净退款率，分母使用已结算商品件数，并把售后与结算宽表关联。",
    expectedBlocked: true,
    expected: {},
  },
];

function runCli(args) {
  const result = spawnSync("python", ["tools/aibi_cli.py", "--json", ...args], {
    cwd: process.cwd(),
    env,
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
  return { ok: result.status === 0 && parsed?.ok === true, status: result.status, parsed, stderr: result.stderr };
}

function metricMap(answerCard) {
  return Object.fromEntries(
    (answerCard?.metrics ?? []).map((metric) => [
      metric?.label?.zh ?? metric?.label,
      Number(Number(metric?.rawValue).toFixed(8)),
    ]),
  );
}

function numbersEqual(actual, expected) {
  return Number.isFinite(actual) && Math.abs(actual - expected) <= 1e-6;
}

function markdown(receipt) {
  const lines = [
    "# 三平台 Agent 答案准确性验证",
    "",
    `- 日期：${receipt.generatedAt.slice(0, 10)}`,
    `- 验证输入：${receipt.validationSource}`,
    `- 结果：${receipt.passed}/${receipt.total} 通过`,
    `- 知识包：${receipt.knowledgePack}`,
    "",
    "| 场景 | 规则 | 结果 | 实际指标 |",
    "| --- | --- | --- | --- |",
    ...receipt.cases.map((item) => `| ${item.id} | ${item.matchedRuleId || "安全阻断"} | ${item.ok ? "通过" : "失败"} | ${Object.entries(item.actual).map(([key, value]) => `${key}=${value}`).join("；") || "未执行近似查询"} |`),
    "",
    "## 基线问题",
    "",
    "修复前，抖音成功退款问题返回 `7`，实际应为退款商品金额 `441.00`、成功退款 `4` 条。原因是通用单表 Agent 把“记录数”覆盖成整个问题的聚合方式，并忽略了状态和金额筛选。",
    "",
    "## 能力边界",
    "",
    "- 规则只负责确定粒度、状态、去重、连接和聚合口径；答案始终从当前工作区数据执行 SQL 得出。",
    "- 不匹配表结构或问题意图时不会套用平台规则，继续走通用 Agent 的澄清与证据路径。",
    "- 资料包是合成数据与公开资料摘要，不替代平台最新接口文档。",
    "",
  ];
  return lines.join("\n");
}

const importResults = [];
const caseResults = [];
let domainPackActivation = null;

try {
  if (!existsSync(templatesDir)) throw new Error(`Platform research templates not found: ${templatesDir}`);
  const activation = runCli(["domain-pack-set", "--pack", "platform-commerce", "--state", "enabled", "--yes"]);
  domainPackActivation = activation.parsed;
  if (!activation.ok || activation.parsed?.confirmed !== true) {
    throw new Error(`Platform commerce Domain Pack activation failed: ${activation.parsed?.error ?? activation.stderr}`);
  }
  for (const [file, table, name] of imports) {
    const input = join(templatesDir, file);
    const result = existsSync(input)
      ? runCli(["import-commit", input, "--table", table, "--name", name, "--mode", "create", "--yes"])
      : { ok: false, parsed: null, stderr: `Missing ${input}` };
    importResults.push({ file, table, ok: result.ok, error: result.parsed?.error ?? result.stderr?.trim() ?? "" });
    if (!result.ok) throw new Error(`Import failed: ${file}: ${result.parsed?.error ?? result.stderr}`);
  }

  for (const testCase of cases) {
    const result = runCli(["ask", testCase.prompt, "--read-only"]);
    const actual = metricMap(result.parsed?.answerCard);
    const mismatches = Object.entries(testCase.expected)
      .filter(([label, expected]) => !numbersEqual(actual[label], expected))
      .map(([label, expected]) => ({ label, expected, actual: actual[label] }));
    const matchedRuleId = result.parsed?.agentKnowledge?.matchedRuleId ?? null;
    const receipt = result.parsed?.queryPlanReceipt;
    const businessUnderstandingStatus = result.parsed?.businessUnderstanding?.status ?? null;
    const businessUnderstandingBlockers = result.parsed?.businessUnderstanding?.blockers ?? [];
    const evidenceTypes = (result.parsed?.answerCard?.evidenceRefs ?? []).map((item) => item?.type).filter(Boolean);
    const knowledgeRuleEvidenceCount = evidenceTypes.filter((type) => type === "knowledgeRule").length;
    const ok = testCase.expectedBlocked
      ? result.ok
        && (testCase.expectedKnowledgeMatch ? matchedRuleId !== null : matchedRuleId === null)
        && result.parsed?.answerCard?.kind === "clarification"
        && receipt?.status === "blocked"
        && businessUnderstandingStatus === "needs-clarification"
        && !receipt?.runtime?.compiledSql
      : result.ok
        && matchedRuleId === testCase.id
        && mismatches.length === 0
        && businessUnderstandingStatus === "ready"
        && businessUnderstandingBlockers.length === 0
        && receipt?.status === "executed"
        && receipt?.runtime?.compiledSql
        && knowledgeRuleEvidenceCount === 1;
    caseResults.push({
      id: testCase.id,
      ok: Boolean(ok),
      prompt: testCase.prompt,
      expected: testCase.expected,
      actual,
      mismatches,
      matchedRuleId,
      queryStatus: receipt?.status ?? null,
      businessUnderstandingStatus,
      businessUnderstandingBlockers,
      compiledSql: receipt?.runtime?.compiledSql ?? null,
      evidenceTypes,
      error: result.parsed?.error ?? result.stderr?.trim() ?? "",
    });
  }

  const passed = caseResults.filter((item) => item.ok).length;
  const receipt = {
    ok: passed === caseResults.length,
    schema: "aibi-platform-commerce-agent-verify/v1",
    generatedBy: "scripts/verify-platform-commerce-agent.mjs",
    generatedAt: `${new Date().toLocaleString("sv-SE", { timeZone: "Asia/Shanghai" }).replace(" ", "T")}+08:00`,
    validationSource,
    generatedFixtures,
    knowledgePack: "knowledge/platform-commerce.v1.json",
    domainPackActivation,
    modelIndependent: true,
    baseline: {
      prompt: cases[0].prompt,
      observedBefore: { 退商品金额: 7 },
      expected: cases[0].expected,
      failure: "record-count aggregation overrode the requested sum and filters were ignored",
    },
    imports: importResults,
    domainPackActivation,
    total: caseResults.length,
    passed,
    failed: caseResults.length - passed,
    cases: caseResults,
  };
  if (reportDir) {
    mkdirSync(reportDir, { recursive: true });
    writeFileSync(join(reportDir, "receipt.json"), `${JSON.stringify(receipt, null, 2)}\n`, "utf8");
    writeFileSync(join(reportDir, "SUMMARY.md"), markdown(receipt), "utf8");
  }
  console.log(JSON.stringify(receipt, null, 2));
  if (!receipt.ok) process.exitCode = 1;
} catch (error) {
  console.error(JSON.stringify({
    ok: false,
    generatedBy: "scripts/verify-platform-commerce-agent.mjs",
    error: error instanceof Error ? error.message : String(error),
    imports: importResults,
    cases: caseResults,
  }, null, 2));
  process.exitCode = 1;
} finally {
  rmSync(verifyDir, { recursive: true, force: true });
}
