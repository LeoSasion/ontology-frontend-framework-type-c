import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

export const multiDomainBetaFixtures = [
  {
    key: "manufacturing-quality",
    name: "制造质量执行",
    file: "manufacturing_quality.csv",
    measure: "complete_qty",
    dimension: "workshop",
    expectedUnitKeys: ["production-plan-kpi", "production-complete-kpi", "workshop-quality-rank"],
    forbiddenForeignFields: ["ar_amount", "overdue_days", "customer_balance"],
    csv: [
      "production_order_id,product,workshop,production_date,plan_qty,complete_qty,quality_pass_rate,defective_qty",
      "MO-1001,Valve-A,Assembly,2026-07-01,100,96,0.96,4",
      "MO-1002,Pump-B,Assembly,2026-07-02,80,72,0.90,8",
      "MO-1003,Valve-A,Finishing,2026-07-03,120,114,0.95,6",
      "MO-1004,Pump-B,Finishing,2026-07-04,90,81,0.90,9",
    ].join("\n") + "\n",
  },
  {
    key: "finance-aging",
    name: "财务应收账龄",
    file: "finance_aging.csv",
    measure: "overdue_amount",
    dimension: "customer",
    expectedUnitKeys: ["ar-aging-overdue-kpi", "ar-aging-rank", "ar-aging-table"],
    forbiddenForeignFields: ["plan_qty", "complete_qty", "quality_pass_rate"],
    csv: [
      "customer,age_bucket,overdue_days,due_date,customer_balance,overdue_amount,bad_debt_risk,voucher_no,account_subject,cash_flow_amount,date",
      "North Retail,0-30,12,2026-06-30,18000,6000,low,V-1001,Accounts Receivable,12000,2026-07-01",
      "East Wholesale,31-60,45,2026-05-28,26000,16000,medium,V-1002,Accounts Receivable,10000,2026-07-02",
      "South Dealer,61-90,76,2026-04-27,32000,28000,high,V-1003,Accounts Receivable,4000,2026-07-03",
      "West Outlet,90+,108,2026-03-26,15000,15000,high,V-1004,Accounts Receivable,0,2026-07-04",
    ].join("\n") + "\n",
  },
];

export function writeMultiDomainBetaFixtures(directory) {
  mkdirSync(directory, { recursive: true });
  return multiDomainBetaFixtures.map((fixture) => {
    const path = join(directory, fixture.file);
    writeFileSync(path, fixture.csv, "utf8");
    return { ...fixture, path };
  });
}
