import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { platformCommerceFixtures, writePlatformCommerceFixtures } from "./platform-commerce-fixtures.mjs";

function keyOf(row, fields) {
  return fields.map((field) => String(row[field] ?? "")).join("\u001f");
}

function relationshipReceipt(name, left, right, leftFields, rightFields = leftFields) {
  const rightCounts = new Map();
  for (const row of right.rows) {
    const key = keyOf(row, rightFields);
    rightCounts.set(key, (rightCounts.get(key) ?? 0) + 1);
  }
  const joinedRows = left.rows.reduce((total, row) => total + Math.max(1, rightCounts.get(keyOf(row, leftFields)) ?? 0), 0);
  return {
    name,
    mappings: leftFields.map((leftField, index) => ({ leftField, rightField: rightFields[index] })),
    leftRows: left.rows.length,
    rightRows: right.rows.length,
    joinedRows,
    rowExpansion: left.rows.length ? Number((joinedRows / left.rows.length).toFixed(6)) : 0,
  };
}

const byTable = new Map(platformCommerceFixtures.map((fixture) => [fixture.table, fixture]));
const requiredTables = [
  "douyin_orders", "douyin_aftersales", "douyin_logistics",
  "taobao_trades", "taobao_order_items", "taobao_refunds", "taobao_logistics",
  "jushuitan_orders", "jushuitan_order_items", "jushuitan_outbounds", "jushuitan_aftersales", "jushuitan_logistics",
];
const requiredFields = {
  douyin_orders: ["主订单编号", "子订单编号", "商品ID", "商家编码", "主单应付金额"],
  douyin_aftersales: ["主订单编号", "商品ID", "商家编码", "售后状态", "退商品金额"],
  taobao_trades: ["tid", "status", "payment", "pay_time"],
  taobao_refunds: ["refund_id", "tid", "oid", "status", "refund_fee"],
  jushuitan_orders: ["o_id", "status", "ts", "paid_amount", "source_platform"],
  jushuitan_outbounds: ["io_id", "o_id", "warehouse_name", "lc_name", "l_id"],
};

const output = mkdtempSync(join(tmpdir(), "aibi-c-platform-fixtures-"));
const checks = [];
try {
  const written = writePlatformCommerceFixtures(output);
  checks.push({ label: "fixture-table-set", ok: requiredTables.every((table) => byTable.has(table)), detail: requiredTables });
  checks.push({ label: "fixtures-are-generated-in-temp", ok: written.length === 12 && output.startsWith(tmpdir()), detail: output });
  for (const [table, fields] of Object.entries(requiredFields)) {
    const fixture = byTable.get(table);
    checks.push({
      label: `${table}-required-fields`,
      ok: Boolean(fixture) && fields.every((field) => fixture.columns.includes(field)),
      detail: fields,
    });
  }
  const relationships = [
    relationshipReceipt(
      "douyin-order-aftersales-composite",
      byTable.get("douyin_orders"),
      byTable.get("douyin_aftersales"),
      ["主订单编号", "商品ID", "商家编码"],
    ),
    relationshipReceipt("taobao-trade-items", byTable.get("taobao_trades"), byTable.get("taobao_order_items"), ["tid"]),
    relationshipReceipt("jst-order-outbounds", byTable.get("jushuitan_orders"), byTable.get("jushuitan_outbounds"), ["o_id"]),
  ];
  checks.push({
    label: "compound-mapping-is-preserved",
    ok: relationships[0].mappings.length === 3 && relationships[0].mappings[2].leftField === "商家编码",
    detail: relationships[0],
  });
  checks.push({
    label: "one-to-many-risk-is-observable",
    ok: relationships[1].rowExpansion > 1 && relationships[2].rowExpansion > 1,
    detail: relationships,
  });
  const failedChecks = checks.filter((check) => !check.ok);
  console.log(JSON.stringify({
    ok: failedChecks.length === 0,
    schema: "aibi-c-platform-commerce-fixtures-verify/v1",
    generatedBy: "scripts/verify-platform-commerce-fixtures.mjs",
    fixtureCount: platformCommerceFixtures.length,
    relationships,
    checks,
    failedChecks,
  }, null, 2));
  if (failedChecks.length) process.exitCode = 1;
} finally {
  rmSync(output, { recursive: true, force: true });
}
