import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

function csvCell(value) {
  const text = String(value ?? "");
  return /[",\r\n]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function csv(columns, rows) {
  return `${[
    columns.map(csvCell).join(","),
    ...rows.map((row) => columns.map((column) => csvCell(row[column])).join(",")),
  ].join("\n")}\n`;
}

export const platformCommerceFixtures = [
  {
    file: "douyin_orders_synthetic.csv",
    table: "douyin_orders",
    name: "抖音订单",
    columns: ["主订单编号", "子订单编号", "商品ID", "商家编码", "支付时间", "订单状态", "主单应付金额"],
    rows: [
      ["DY-M001", "DY-S001", "P-RED", "RED-M", "2026-06-01 10:00:00", "已支付", 200],
      ["DY-M002", "DY-S002", "P-SHOE", "SHOE-38", "2026-06-01 11:00:00", "已支付", 300],
      ["DY-M003", "DY-S003", "P-WHITE", "WHITE-S", "2026-06-02 09:00:00", "已完成", 150],
      ["DY-M004", "DY-S004", "P-HAT", "HAT-FREE", "2026-06-02 12:00:00", "已完成", 100],
      ["DY-M005", "DY-S005-A", "P-OTHER-A", "OTHER-A", "2026-06-03 08:00:00", "已支付", 125.5],
      ["DY-M005", "DY-S005-B", "P-OTHER-B", "OTHER-B", "2026-06-03 08:00:00", "已支付", 125.5],
      ["DY-M006", "DY-S006", "P-OTHER-C", "OTHER-C", "2026-06-03 13:00:00", "已完成", 200.4],
      ["DY-M007", "DY-S007", "P-VIRTUAL", "OTHER-D", "2026-06-04 10:00:00", "已支付", 125],
      ["DY-M008", "DY-S008", "P-CLOSED", "OTHER-E", "", "已关闭", 99],
    ],
  },
  {
    file: "douyin_aftersales_synthetic.csv",
    table: "douyin_aftersales",
    name: "抖音售后",
    columns: ["售后单号", "主订单编号", "商品ID", "商家编码", "售后状态", "退商品金额", "退运费金额", "退税费金额"],
    rows: [
      ["DY-A001", "DY-M002", "P-SHOE", "SHOE-38", "退款成功", 179, 1, 0],
      ["DY-A002", "DY-M001", "P-RED", "RED-M", "退款成功", 119, 2, 0],
      ["DY-A003", "DY-M003", "P-WHITE", "WHITE-S", "退款成功", 94, 1, 1],
      ["DY-A004", "DY-M004", "P-HAT", "HAT-FREE", "退款成功", 49, 1, 0],
      ["DY-A005", "DY-M006", "P-OTHER-C", "OTHER-C", "退款处理中", 80, 0, 0],
    ],
  },
  {
    file: "douyin_logistics_synthetic.csv",
    table: "douyin_logistics",
    name: "抖音物流",
    columns: ["主订单编号", "子订单编号", "物流单号", "物流状态", "物流类型"],
    rows: [
      ["DY-M001", "DY-S001", "DY-L001", "已签收", "普通物流"],
      ["DY-M002", "DY-S002", "DY-L002-A", "运输中", "普通物流"],
      ["DY-M002", "DY-S002", "DY-L002-B", "运输中", "普通物流"],
      ["DY-M003", "DY-S003", "", "无需物流", "虚拟商品"],
      ["DY-M004", "DY-S004", "DY-L004", "已签收", "普通物流"],
    ],
  },
  {
    file: "taobao_trades_synthetic.csv",
    table: "taobao_trades",
    name: "淘宝主单",
    columns: ["tid", "status", "payment", "pay_time"],
    rows: [
      ["TB-T001", "WAIT_SELLER_SEND_GOODS", 300, "2026-06-01 10:00:00"],
      ["TB-T002", "TRADE_FINISHED", 242.9, "2026-06-01 11:00:00"],
      ["TB-T003", "TRADE_CLOSED_BY_TAOBAO", 100, ""],
      ["TB-T004", "WAIT_BUYER_CONFIRM_GOODS", 500, "2026-06-02 12:00:00"],
      ["TB-T005", "TRADE_CLOSED", 200, "2026-06-03 09:00:00"],
    ],
  },
  {
    file: "taobao_order_items_synthetic.csv",
    table: "taobao_order_items",
    name: "淘宝子单",
    columns: ["tid", "oid", "outer_iid", "num", "price"],
    rows: [
      ["TB-T001", "TB-O001", "SKU-A", 1, 300],
      ["TB-T002", "TB-O002", "SKU-B", 1, 242.9],
      ["TB-T003", "TB-O003", "SKU-C", 1, 100],
      ["TB-T004", "TB-O004", "SKU-D", 1, 250],
      ["TB-T004", "TB-O005", "SKU-E", 1, 250],
      ["TB-T005", "TB-O006", "SKU-F", 1, 200],
    ],
  },
  {
    file: "taobao_refunds_synthetic.csv",
    table: "taobao_refunds",
    name: "淘宝退款",
    columns: ["refund_id", "tid", "oid", "status", "refund_fee"],
    rows: [
      ["TB-R001", "TB-T001", "TB-O001", "SUCCESS", 100],
      ["TB-R002", "TB-T002", "TB-O002", "SUCCESS", 119],
      ["TB-R003", "TB-T004", "TB-O004", "SUCCESS", 138],
      ["TB-R004", "TB-T005", "TB-O006", "WAIT_SELLER_AGREE", 50],
    ],
  },
  {
    file: "taobao_logistics_synthetic.csv",
    table: "taobao_logistics",
    name: "淘宝物流",
    columns: ["tid", "order_code", "out_sid", "is_split"],
    rows: [
      ["TB-T001", "TB-L001", "SF001", 0],
      ["TB-T002", "TB-L002", "YT002", 0],
      ["TB-T004", "TB-L004-A", "ZT004A", 1],
      ["TB-T004", "TB-L004-B", "ZT004B", 1],
    ],
  },
  {
    file: "jushuitan_orders_versioned_synthetic.csv",
    table: "jushuitan_orders",
    name: "聚水潭订单版本",
    columns: ["o_id", "status", "ts", "paid_amount", "source_platform"],
    rows: [
      ["JST-O001", "Paid", 1, 100, "抖音"],
      ["JST-O001", "Paid", 2, 200, "抖音"],
      ["JST-O002", "Paid", 2, 345, "抖音"],
      ["JST-O003", "Completed", 2, 300, "淘宝"],
      ["JST-O004", "Paid", 1, 176, "淘宝"],
      ["JST-O004", "Paid", 2, 250, "淘宝"],
      ["JST-O005", "Completed", 2, 315, "淘宝"],
      ["JST-O006", "Paid", 2, 88, "自有商城"],
      ["JST-O007", "Paid", 2, 0, "自有商城"],
      ["JST-O008", "Cancelled", 2, 0, "抖音"],
    ],
  },
  {
    file: "jushuitan_order_items_synthetic.csv",
    table: "jushuitan_order_items",
    name: "聚水潭订单商品",
    columns: ["o_id", "outer_sku_id", "refund_qty"],
    rows: [
      ["JST-O001", "RED-M", 1],
      ["JST-O002", "RED-M", 1],
      ["JST-O003", "WHITE-S", 1],
      ["JST-O004", "HAT-FREE", 1],
      ["JST-O005", "SHOE-38", 1],
      ["JST-O006", "OTHER", 0],
    ],
  },
  {
    file: "jushuitan_outbounds_synthetic.csv",
    table: "jushuitan_outbounds",
    name: "聚水潭销售出库",
    columns: ["io_id", "o_id", "warehouse_name", "lc_name", "l_id", "package_no"],
    rows: [
      ["IO-001", "JST-O001", "华东仓", "中通快递", "L-001", "PKG-001"],
      ["IO-002-A", "JST-O002", "华东仓", "中通快递", "L-002-A", "PKG-002-A"],
      ["IO-002-B", "JST-O002", "华东仓", "京东快递", "L-002-B", "PKG-002-B"],
      ["IO-003", "JST-O003", "华东仓", "顺丰速运", "L-003", "PKG-003"],
      ["IO-004-A", "JST-O004", "华东仓", "顺丰速运", "L-004-A", "PKG-004-A"],
      ["IO-004-B", "JST-O004", "华南仓", "圆通速递", "L-004-B", "PKG-004-B"],
      ["IO-005", "JST-O005", "华南仓", "圆通速递", "L-005", "PKG-005"],
      ["IO-006", "JST-O006", "华南仓", "顺丰速运", "L-006", "PKG-006"],
      ["IO-007", "JST-O007", "华南仓", "顺丰速运", "L-007", "PKG-007"],
    ],
  },
  {
    file: "jushuitan_aftersales_synthetic.csv",
    table: "jushuitan_aftersales",
    name: "聚水潭售后",
    columns: ["as_id", "o_id", "status", "actual_refund"],
    rows: [
      ["AS-001", "JST-O001", "Confirmed", 119],
      ["AS-002", "JST-O002", "Confirmed", 119],
      ["AS-003", "JST-O003", "Confirmed", 94],
      ["AS-004", "JST-O004", "Confirmed", 49],
      ["AS-005", "JST-O005", "Confirmed", 189],
      ["AS-006", "JST-O006", "Rejected", 30],
    ],
  },
  {
    file: "jushuitan_logistics_synthetic.csv",
    table: "jushuitan_logistics",
    name: "聚水潭物流",
    columns: ["o_id", "so_id", "l_id", "sync_status"],
    rows: [
      ["JST-O001", "DY-M001", "L-001", "Success"],
      ["JST-O002", "DY-M002", "L-002", "Pending"],
      ["JST-O003", "TB-T003", "L-003", "Success"],
      ["JST-O004", "TB-T004", "L-004", "Success"],
      ["JST-O005", "TB-T006", "L-005", "Failed"],
    ],
  },
].map((fixture) => ({
  ...fixture,
  rows: fixture.rows.map((values) => Object.fromEntries(fixture.columns.map((column, index) => [column, values[index]]))),
}));

export function writePlatformCommerceFixtures(directory) {
  mkdirSync(directory, { recursive: true });
  for (const fixture of platformCommerceFixtures) {
    writeFileSync(join(directory, fixture.file), csv(fixture.columns, fixture.rows), "utf8");
  }
  return platformCommerceFixtures.map((fixture) => ({
    file: fixture.file,
    table: fixture.table,
    name: fixture.name,
    rows: fixture.rows.length,
    columns: fixture.columns.length,
  }));
}
