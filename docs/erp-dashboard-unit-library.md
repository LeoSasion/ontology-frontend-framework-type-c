# ERP Dashboard Unit Library

Last updated: 2026-07-05

## Purpose

This project should not ship a fixed ERP dashboard template. The ERP path is a selectable unit library: public ERP field/report patterns are broken into small metric, chart, table, slicer, and evidence units; Agent scores the current table fields and renders only the units that have enough evidence.

The goal is to support real Chinese ERP/export workbooks where each company names fields differently. A table that looks like 旺店通 order detail may need SKU profit, freight variance, refund status, and order drilldown. A table that looks like 金蝶 sales execution may need outbound, receivable, invoice, customer, and write-off checks. A procurement/inventory table may need supplier delivery, stock aging, safety stock, and turnover risk. The UI should let Agent choose the right combination instead of forcing users through a template picker.

## Public References

The current library uses these public examples as field/report inspiration:

| Source | Covered Signals | Link |
| --- | --- | --- |
| 聚水潭销售出库查询 | sales outbound, custom return fields, freight, combined SKUs, after-sales id | https://open.jushuitan.com/document/2227.html |
| 聚水潭售后退货退款查询 | after-sales order, refund amount, actual refund formula, freight/payment relationship | https://open.jushuitan.com/document/15.html |
| 旺店通开放接口目录 | order query, sales outbound, invoice, platform bill, logistics sync, stock sync | https://open.wangdian.cn/qjb/open/apidoc |
| 旺店通销售出库单明细 | SKU/spec code, sell price, cost price, gifts, refund status, shared freight | https://open.wangdian.cn/open/apidoc/doc?path=stockout_order_query_trade.php |
| 金蝶云星空销售订单执行明细表 | sales order, delivery, outbound, receivable, invoice, receipt/write-off | https://help.open.kingdee.com/dokuwiki_std/doku.php?id=%E9%94%80%E5%94%AE%E8%AE%A2%E5%8D%95%E6%89%A7%E8%A1%8C%E6%98%8E%E7%BB%86%E8%A1%A8 |
| 金蝶云星空销售出库汇总表 | material/customer grouping, outbound, receivable, inventory accounting | https://help.open.kingdee.com/dokuwiki_std/doku.php?id=%E9%94%80%E5%94%AE%E5%87%BA%E5%BA%93%E6%B1%87%E6%80%BB%E6%8A%A5%E8%A1%A8 |
| 金蝶云星空采购订单执行明细表 | purchase order, arrival, stock-in, return material, supplier | https://help.open.kingdee.com/dokuwiki/doku.php?id=%E9%87%87%E8%B4%AD%E8%AE%A2%E5%8D%95%E6%89%A7%E8%A1%8C%E6%98%8E%E7%BB%86%E8%A1%A8 |
| 金蝶云星空生产订单执行明细表 | production order, product, workshop, planned quantity, stock-in, achievement | https://help.open.kingdee.com/dokuwiki/doku.php?id=%E7%94%9F%E4%BA%A7%E8%AE%A2%E5%8D%95%E6%89%A7%E8%A1%8C%E6%98%8E%E7%BB%86%E8%A1%A8 |
| 用友 U8 进销存公开示例 | inventory status, turnover, purchase cost/efficiency, sales performance | https://www.jiandaoyun.com/blog/article/848452/ |
| 网上管家婆进销存 | inventory warning, shelf life, SKU distribution, price/cost allocation, AR/AP, profit | https://www.wsgjp.com.cn/Products/Jxc.aspx |
| 赛狐经营看板 | store/country/currency filters, comprehensive analysis, profit, operations, market insight, FBA sellable stock | https://www.sellfox.com/help/features/business-dashboard |
| 积加即时看板 | instant sales view, country/store/product dimensions, order quantity, sales amount, average price, stock, drilldown | https://help.jijiaerp.com/docs/ji-shi-kan-ban-xin |
| 网上管家婆智能补货 | sellable stock, stock floor/ceiling, daily sales, planned sales days, reorder quantity, MOQ | https://helpnew.wsgjp.com/-/tags/%E7%BD%91%E5%BA%97ERP%E4%BC%81%E4%B8%9A%E7%89%88?_page=2 |
| 管家婆云 App | profit statement, boss key data, hot products, customer arrears, inventory alerts, multi-dimensional sales analysis | https://apps.apple.com/tz/app/%E7%AE%A1%E5%AE%B6%E5%A9%86%E4%BA%91app-%E8%BF%9B%E9%94%80%E5%BA%93%E5%AD%98%E7%AE%A1%E7%90%86erp%E8%BD%AF%E4%BB%B6/id1474912464 |
| 万里牛产品拆解 | daily dashboard, store profile, product profile, realtime screen, sales/purchase/inventory/AR/AP/performance statistics | https://www.woshipm.com/evaluating/5271289.html |
| 聚水潭 SaaS ERP 服务 | order, purchase, finance, warehouse, distribution, customer, inventory, report, after-sales modules | https://www.ssme.sh.gov.cn/public/product%21serviceDetail.do?productId=2c91c29384560dd401845bc64dad261b |
| 聚水潭胜途 | logistics reconciliation, report fields, picking path, cross-border issue handling | https://www.jushuitan.com/product/shengtu.html |
| 金蝶云星空生产齐套分析单 | production order, prepared quantity, expected kit quantity, inventory kit quantity, issued quantity | https://help.open.kingdee.com/dokuwiki_std/doku.php?id=%E7%94%9F%E4%BA%A7%E9%BD%90%E5%A5%97%E5%88%86%E6%9E%90%E5%8D%95 |
| 金蝶云星空采购订单 | purchase organization, supplier, material, units, price list, source list, delivery conditions | https://help.open.kingdee.com/dokuwiki/doku.php?id=%E9%87%87%E8%B4%AD%E8%AE%A2%E5%8D%95 |
| 金蝶云星空采购入库单 | pricing unit, pricing quantity, purchase quantity, reconciliation status, stock-in document ids | https://help.open.kingdee.com/dokuwiki/doku.php?id=%E9%87%87%E8%B4%AD%E5%85%A5%E5%BA%93%E5%8D%95 |
| 用友 YonSuite 物料齐套 | material kitting, production order picking, planned picking, batch picking | https://www.yonsuite.com/infoNew/224041850264.html |
| 旺店通功能模块 | order, after-sales, purchase, inventory control, data statistics, split/merge orders, safety stock | https://www.wangdian.cn/ask/2120/ |
| 网上管家婆库存状况 | stock status, serial stock, package stock, cost method, estimated cost, sellable stock, cost anomaly | https://helpnew.wsgjp.com/-/tags/%E7%BD%91%E5%BA%97ERP%E6%97%97%E8%88%B0%E7%89%88?_page=5 |
| 网上管家婆网店 ERP | order sync, smart order review, stock floor/ceiling alerts, nearest warehouse, AR/AP, supplier reconciliation | https://www.wsgjp.com.cn/Products/Erp.aspx |
| 领星利润报表 | profit report, platform income/expense/tax, Summary reconciliation, taxable gross profit | https://www.lingxing.com/help/article/ProfitStatementnew |
| 领星 ERP 功能价值 | profit, settlement, payment collection, cost allocation, inventory loss, transfer status, SKU payment | https://www.lingxing.com/help/article/WhatisLINGXINGERP |
| 赛狐报告中心 | Amazon original reports, inventory/sales/payment/returns/removal reports, scheduled report tasks | https://www.sellfox.com/help/features/report-center |
| 赛狐应收报表 | receivables, delivery fee, commission, settlement cycle, reserve amount, received amount, cash planning | https://www.sellfox.com/help/features/accounts-receivable-report |
| 积加销售利润分析 | store/site/product dimensions, parent/sub ASIN, MSKU, order fee report reconciliation loop | https://help.jijiaerp.com/docs/CsdBvZ96 |
| 马帮采购价更新订单成本 | purchase price, order cost price, purchase order, related orders, profit report field checks | https://help.mabangerp.com/kbzx/nested/details?id=4252&resource_id=1 |
| 万里牛开放对接 | order chain, shipping callback, after-sales order, inventory change, unified stock management | https://open.hupun.com/guide/erp-djcj |
| 鼎捷易飞制造模块 | BOM, work order, material kitting, process reporting, defect data, quality analysis, delivery rate | https://www.digiwin.com/t.php/p/15087.html |
| 畅捷通 T+Cloud 连接器 | inventory/sales/outbound queries, finance analysis, production, multi-store operations | https://hiflow.tencent.com/document/applications/chanjet-tcloud/ |
| 用友系报表优化资产 | customer balance, supplier balance, inventory in/out summary, sales/purchase/inventory reports | https://developer.yonyou.com/cloud/integrationAsset/assetDetail/1710582566748131329 |
| 金蝶云星空应收款管理 | AR summary/detail, aging analysis, due-debt table, customer statement, bad-debt risk | https://help.open.kingdee.com/dokuwiki_std/doku.php?id=%E5%BA%94%E6%94%B6%E6%AC%BE%E7%AE%A1%E7%90%86 |
| 金蝶管易云全渠道库存 | all-channel inventory, goods management, supply-chain response, order and warehouse operations | https://www.guanyiyun.com/ |
| 金蝶管易云 WMS 案例 | multi-warehouse, multi-owner, bin location, barcode scanning, stock accuracy, order verification | https://www.yun88.com/product/1191.html |
| 店小秘亚马逊利润核算 | order amount, FBA fee, ad spend, return fee, storage fee, store/SKU/developer profit dimensions | https://www.dianxiaomi.com/blog/article/241 |
| 店小秘订单预估利润 | estimated profit, order amount, platform commission, purchase cost, estimated freight, profit rate | https://help.dianxiaomi.com/pre/getContent.htm?id=839 |
| 店小秘仓库成本 | stockout price, warehouse SKU unit cost, package/order/tracking lookup, purchase cost proof | https://help.dianxiaomi.com/pre/getContent.htm?id=474 |
| 网上管家婆行业特性 | color/size, batch/expiry, serial number, purchase stock-in, sales stock-out, stock status | https://help.wsgjp.com/5e03/e630/5be3 |
| 金蝶进销存现代案例 | AI forecast, dynamic replenishment, stock health, multi-warehouse collaboration, decision screen | https://www.kingdee.com/resources/articles/1436035275061409953 |
| 梦想云服装鞋帽 | style/color/size, barcode, inventory statistics, AR/AP, capital movement statements | https://www.mxyun.com/industry/fzxm |
| 简道云医药效期 | production date, valid date, expiry warning, FIFO, expiry management report, batch traceability | https://www.jiandaoyun.com/news/article/6842b00c6544d8159cd626e9 |
| 管家婆食品制造案例 | BOM, material consumption, loss rate, limited material issue, batch/expiry, finished-goods cost | https://www.cqgrasp.com/anlicczz/237.html |
| 用友 YonSuite 服装尺码颜色 | size/color/style management, stock status, dead stock and stockout control | https://www.yonsuite.com/infoNew/2250606784999.html |
| 帆软制造报表案例 | production plan achievement, supplier performance, inventory distribution, line progress, quality alert | https://www.finereport.com/blog/article/68c13e25d2527e0eb7bb7dd1 |

## Implemented Shape

- `tools/erp_dashboard_unit_library.py` owns the public references, field alias groups, selectable ERP units, scoring, and catalog payload.
- The unit catalog currently exposes 167 units across 29 categories: sales/order, outbound/logistics, after-sales/refund, profit/cost, receivable/reconciliation, purchase/supplier, inventory/turnover, inventory/replenishment, cross-border/store, boss view, advertising/operations, production/manufacturing, interaction/evidence, sales execution/payment collection, purchase execution/payables, production kitting/workshop, inventory cost/batches, cross-border finance/platform, after-sales quality/service, distribution/store/member, report/data governance, retail POS/member, apparel attribute matrix, batch/expiry/cold chain, warehouse/WMS, forecast/replenishment, cross-border profit accounting, finance aging, and manufacturing plan/quality.
- Field aliases currently cover 252 groups, including the older order/SKU/store/customer/supplier/inventory/profit/ad groups plus sales execution chain fields, purchase execution and payment fields, production kitting/material issue fields, workshop quality fields, inventory cost-method and batch-expiry fields, cross-border platform income/expense/tax/settlement fields, report task fields, after-sales reason/type fields, distribution/member/route fields, logistics weight/tracking fields, POS/payment/member fields, apparel style/color/size/barcode fields, WMS bin/owner/count/transfer fields, financial aging/voucher/cash-flow fields, and manufacturing work-center/BOM/yield/cold-chain fields.
- `business-dashboard --template erp-units` uses the selected units to create a confirmable dashboard draft with evidence references.
- Agent prompts that mention ERP, 电商, 聚水潭, 旺店通, 金蝶, 用友, 管家婆, 赛狐, 积加, 万里牛, 鼎捷, 订单, 出库, 售后, 退款, 采购, 库存, 应收, 应付, 回款, 对账, 供应商, 生产, 制造, 齐套, 工单, 车间, 跨境, 店铺, 补货, 广告, 老板, 进销存 and related English terms automatically prefer the ERP unit library.
- The dashboard UI exposes an `ERP 单元 / ERP units` preview entry from the business-template panel. The preview now shows how many units were selected, which public references matched, which fields were used, which units were omitted because fields are missing, deduplicated fields to add next, unlock-next category priorities, and which widgets would render before the user confirms a write.
- The Agent task packet now carries the same `erpUnitLibrary` explanation when a natural-language dashboard draft prefers ERP units. Users can ask from the floating/global Agent, see selected categories, omitted directions, suggested fields to add, unlock-next business categories, and public reference sources, then confirm the write only after reviewing the draft.

## Selection Rule

Agent does not render all units. It follows this flow:

1. Read the active workspace table registry and field metadata.
2. Match field names against public ERP aliases and unit-required roles.
3. Drop units whose required measure/dimension fields are missing.
4. Score remaining units by required fields, optional fields, and signal matches.
5. Generate only the top evidence-backed units as dashboard widgets.
6. Return `omittedUnitHints`, `unavailableUnitCount`, and category coverage so the UI can explain what data is needed for the units that were not rendered; the frontend deduplicates `neededFields` into suggested-field chips and groups omitted units by category so users can see what business directions a follow-up import would unlock.
7. Preserve `erpUnitKey`, matched fields, source ids, and evidence refs in the widget payload.

This means a sales/outbound workbook will not get manufacturing cards, and a procurement/inventory workbook will not be forced into an order-sales-only dashboard.

## Verification

Use these commands:

```powershell
python tools/bi_cli.py --json erp-unit-library --summary
python tools/bi_cli.py --json erp-unit-library --select --summary --table orders --limit 24
python tools/bi_cli.py --json business-dashboard --template erp-units --op draft --limit 24
npm run verify:erp-units
```

`npm run verify:erp-units` validates the ERP unit catalog, source evidence flow, selected units, dashboard drafts, and Agent confirmable `dashboard.create` drafts. It also runs six public-case synthetic field scenarios: retail POS/member, apparel style-color-size, cold-chain batch/expiry, cross-border profit accounting, finance aging, and manufacturing plan/quality. Verification output stays in local temp paths or ignored runtime data.
