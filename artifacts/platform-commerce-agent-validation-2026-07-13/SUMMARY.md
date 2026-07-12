# 三平台 Agent 答案准确性验证

- 日期：2026-07-13
- 资料：C:\Users\Administrator\Documents\AIBI-B\data\platform-research
- 结果：23/23 通过
- 知识包：knowledge/platform-commerce.v1.json

| 场景 | 规则 | 结果 | 实际指标 |
| --- | --- | --- | --- |
| douyin-successful-refunds | douyin-successful-refunds | 通过 | 退款商品金额=441；退款运费=6；退款税费=0；成功退款记录数=4；退款成功总额=447 |
| douyin-refund-by-merchant | douyin-refund-by-merchant | 通过 | SHOE-38退款金额=179；RED-M退款金额=119；WHITE-S退款金额=94；HAT-FREE退款金额=49；SHOE-38已支付商品单数=1；RED-M已支付商品单数=1；WHITE-S已支付商品单数=1；HAT-FREE已支付商品单数=1；SHOE-38退款率=1；RED-M退款率=1；WHITE-S退款率=1；HAT-FREE退款率=1 |
| douyin-package-count | douyin-package-count | 通过 | 包裹数=2 |
| douyin-logistics-exception-summary | douyin-logistics-exception-summary | 通过 | 一单多包裹订单数=1；合法虚拟商品空运单=1；虚拟商品误判异常数=0 |
| douyin-virtual-logistics-exception | douyin-virtual-logistics-exception | 通过 | 合法空运单=1；应判未发货=0 |
| douyin-deduplicated-main-order-amount | douyin-deduplicated-main-order-amount | 通过 | 有效主单金额=1200.9；有效主单数=7 |
| taobao-successful-refunds | taobao-successful-refunds | 通过 | 成功退款金额=357；成功退款单数=3 |
| taobao-package-count | taobao-package-count | 通过 | 物流单数=2 |
| taobao-split-logistics-list | taobao-split-logistics-list | 通过 | 拆单主订单数=1；TB-T004运单数=2 |
| taobao-closed-order-types | taobao-closed-order-types | 通过 | 关闭订单总数=2；付款前关闭=1；付款后关闭=1 |
| taobao-closed-order-shipping | taobao-closed-order-shipping | 通过 | 可发货=0 |
| taobao-paid-nonclosed-amount | taobao-paid-nonclosed-amount | 通过 | 已支付未关闭主单金额=1042.9 |
| taobao-net-after-successful-refund | taobao-net-after-successful-refund | 通过 | 已支付未关闭金额=1042.9；成功退款金额=357；退款后净额=685.9 |
| jushuitan-latest-platform-amount | jushuitan-latest-platform-amount | 通过 | 抖音实付金额=545；淘宝实付金额=865；自有商城实付金额=88；最新订单数=8 |
| jushuitan-latest-order-version | jushuitan-latest-order-version | 通过 | 最新订单记录数=8；取消订单数=1；原始版本金额=1774；最新订单金额=1498；重复版本差额=276 |
| jushuitan-multi-package-threshold | jushuitan-multi-package-threshold | 通过 | 一单多包裹率=0.28571429；阈值=0.2；是否超过阈值=1 |
| jushuitan-warehouse-carrier-performance | jushuitan-warehouse-carrier-performance | 通过 | 华东仓/中通快递包裹数=2；华东仓/京东快递包裹数=1；华东仓/顺丰速运包裹数=2；华南仓/圆通速递包裹数=2；华南仓/顺丰速运包裹数=2；华东仓/中通快递订单数=1；华东仓/京东快递订单数=1；华东仓/顺丰速运订单数=2；华南仓/圆通速递订单数=1；华南仓/顺丰速运订单数=2；一单多包裹率=0.28571429 |
| jushuitan-outbound-packages | jushuitan-outbound-packages | 通过 | 销售出库单数=9；覆盖订单数=7；一单多包裹订单数=2；JST-O002包裹数=2；JST-O004包裹数=2 |
| jushuitan-confirmed-refunds-by-merchant | jushuitan-confirmed-refunds-by-merchant | 通过 | HAT-FREE已确认退款金额=49；RED-M已确认退款金额=238；SHOE-38已确认退款金额=189；WHITE-S已确认退款金额=94；可归属退款总额=570；无法唯一归属订单数=0 |
| jushuitan-confirmed-refunds | jushuitan-confirmed-refunds | 通过 | 已确认退款金额=570；已确认退款单数=5 |
| jushuitan-logistics-issue-trace | jushuitan-logistics-issue-trace | 通过 | 物流异常记录数=2；Pending:JST-O002/DY-M002=1；Failed:JST-O005/TB-T006=1 |
| jushuitan-logistics-sync-status | jushuitan-logistics-sync-status | 通过 | 同步失败=1；待处理=1 |
| unsupported-refund-rate-is-blocked | 安全阻断 | 通过 | 未执行近似查询 |

## 基线问题

修复前，抖音成功退款问题返回 `7`，实际应为退款商品金额 `441.00`、成功退款 `4` 条。原因是通用单表 Agent 把“记录数”覆盖成整个问题的聚合方式，并忽略了状态和金额筛选。

## 能力边界

- 规则只负责确定粒度、状态、去重、连接和聚合口径；答案始终从当前工作区数据执行 SQL 得出。
- 不匹配表结构或问题意图时不会套用平台规则，继续走通用 Agent 的澄清与证据路径。
- 资料包是合成数据与公开资料摘要，不替代平台最新接口文档。
