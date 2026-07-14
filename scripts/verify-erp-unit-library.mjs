import { spawnSync } from "node:child_process";

const python = String.raw`
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


scenarios = [
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
checks = [
    {
        "label": "catalog-is-rich-and-generic",
        "ok": catalog.get("unitCount", 0) >= 150
        and catalog.get("referenceCount", 0) >= 45
        and catalog.get("fieldAliasGroupCount", 0) >= 240
        and "not a fixed" in str(catalog.get("selectionPolicy", "")),
        "detail": {
            "unitCount": catalog.get("unitCount"),
            "referenceCount": catalog.get("referenceCount"),
            "fieldAliasGroupCount": catalog.get("fieldAliasGroupCount"),
        },
    }
]
receipts = []
for scenario in scenarios:
    table = {"table_key": scenario["key"], "display_name": scenario["key"]}
    fields = {"columns": scenario["fields"]}
    payload = build_erp_dashboard_unit_templates([table], {scenario["key"]: fields}, limit=36, slug=slug)
    selected = [item.get("preset", {}).get("erpUnitKey") for item in payload.get("templates", [])]
    candidates = []
    for unit in ERP_DASHBOARD_UNITS:
        if _resolve_unit_for_table(unit, table, fields, slug):
            candidates.append(str(unit["key"]))
    candidate_hits = [key for key in scenario["expected"] if key in candidates]
    selected_hits = [key for key in scenario["expected"] if key in selected]
    scenario_checks = [
        {
            "label": "expected-units-are-candidates",
            "ok": len(candidate_hits) == len(scenario["expected"]),
            "detail": {"hits": candidate_hits, "expected": scenario["expected"]},
        },
        {
            "label": "at-least-two-expected-units-selected",
            "ok": len(selected_hits) >= min(2, len(scenario["expected"])),
            "detail": {"selectedHits": selected_hits, "selected": selected[:12]},
        },
        {
            "label": "category-coverage-includes-scenario",
            "ok": any(item.get("category") == scenario["category"] for item in payload.get("erpUnitLibrary", {}).get("categoryCoverage", [])),
            "detail": scenario["category"],
        },
    ]
    receipts.append({
        **scenario,
        "candidateUnitCount": len(candidates),
        "selectedUnitCount": len(selected),
        "checks": scenario_checks,
    })
    checks.extend({"scenario": scenario["key"], **check} for check in scenario_checks)

failed = [check for check in checks if not check["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-c-erp-unit-library-verify/v1",
    "generatedBy": "scripts/verify-erp-unit-library.mjs",
    "scenarioCount": len(scenarios),
    "catalog": catalog,
    "scenarios": receipts,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
sys.exit(0 if not failed else 1)
`;

const result = spawnSync("python", ["-c", python], {
  cwd: process.cwd(),
  encoding: "utf8",
  env: { ...process.env, PYTHONIOENCODING: "utf-8" },
  timeout: 120000,
  windowsHide: true,
  maxBuffer: 32 * 1024 * 1024,
});

if (result.stdout) process.stdout.write(result.stdout);
if (result.stderr) process.stderr.write(result.stderr);
if (result.error) throw result.error;
if (result.status !== 0) process.exitCode = result.status ?? 1;
