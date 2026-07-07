import { writeFileSync } from "node:fs";
import { join } from "node:path";

export function writeCostMonitorFixtures(verifyDataDir) {
  const verifyFundsPath = join(verifyDataDir, "cost-monitor-funds.csv");
  const verifyPolicyPath = join(verifyDataDir, "cost-monitor-policy.csv");

  writeFileSync(
    verifyFundsPath,
    [
      "动账时间,动账方向,动账金额,动账场景,备注,平台服务费,佣金,站外推广费,招商服务费,订单实付应结,实际平台补贴_运费,实际平台补贴,其他平台补贴,以旧换新抵扣,政府补贴平台垫资,实际达人补贴,实际抖音支付补贴,实际抖音月付营销补贴,银行补贴,订单退款,达人ID",
      "2026-03-03,入账,1200,订单结算,, -12,-3,0,-1,1100,10,20,0,0,0,0,0,0,0,-30,15826892886764",
      "2026-04-08,出账,300,提现,,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,",
      "2026-05-12,出账,18,消费者赔付,,0,0,0,0,0,0,0,0,0,0,0,0,0,0,-18,",
      "2026-05-20,出账,6,抖音月付联合贴息,签到领现金,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,",
    ].join("\n"),
    "utf8",
  );

  writeFileSync(
    verifyPolicyPath,
    [
      "投保单号,订单编号,下单时间,动账时间,动账流水号,保险名称,支付保费,备注",
      "P-1,O-1,2026-05-01,2026-05-01,F-1,运费险,8.8,verify",
      "P-2,O-2,2026-05-02,2026-05-02,F-2,运费险,6.6,verify",
    ].join("\n"),
    "utf8",
  );

  return { verifyFundsPath, verifyPolicyPath };
}
