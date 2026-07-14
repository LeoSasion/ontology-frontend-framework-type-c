from __future__ import annotations

import re
from typing import Any, Callable


ERP_UNIT_LIBRARY_TEMPLATE_KEY = "erp-units"

PUBLIC_ERP_REFERENCES: list[dict[str, Any]] = [
    {
        "id": "jst-sales-outbound",
        "vendor": "聚水潭",
        "domain": "电商 ERP",
        "title": "销售出库查询",
        "url": "https://open.jushuitan.com/document/2227.html",
        "signals": ["销售出库单", "自定义返回字段", "运费", "组合装", "售后单号"],
    },
    {
        "id": "jst-refund",
        "vendor": "聚水潭",
        "domain": "电商 ERP",
        "title": "售后退货退款查询",
        "url": "https://open.jushuitan.com/document/15.html",
        "signals": ["售后单", "退款金额", "实退金额", "退货金额", "运费"],
    },
    {
        "id": "wdt-api-index",
        "vendor": "旺店通",
        "domain": "电商 ERP",
        "title": "订单、库存、物流、账款开放接口",
        "url": "https://open.wangdian.cn/qjb/open/apidoc",
        "signals": ["订单查询", "销售出库", "发票", "平台账单", "物流同步", "库存同步"],
    },
    {
        "id": "wdt-stockout-detail",
        "vendor": "旺店通",
        "domain": "电商 ERP",
        "title": "销售出库单明细字段",
        "url": "https://open.wangdian.cn/open/apidoc/doc?path=stockout_order_query_trade.php",
        "signals": ["商家编码", "销售价", "成本价", "赠品", "退款状态", "邮费分摊"],
    },
    {
        "id": "kingdee-sales-order-execution",
        "vendor": "金蝶云星空",
        "domain": "通用 ERP",
        "title": "销售订单执行明细表",
        "url": "https://help.open.kingdee.com/dokuwiki_std/doku.php?id=%E9%94%80%E5%94%AE%E8%AE%A2%E5%8D%95%E6%89%A7%E8%A1%8C%E6%98%8E%E7%BB%86%E8%A1%A8",
        "signals": ["销售订单", "发货", "出库", "应收", "开票", "收款"],
    },
    {
        "id": "kingdee-sales-outbound-summary",
        "vendor": "金蝶云星空",
        "domain": "通用 ERP",
        "title": "销售出库汇总表",
        "url": "https://help.open.kingdee.com/dokuwiki_std/doku.php?id=%E9%94%80%E5%94%AE%E5%87%BA%E5%BA%93%E6%B1%87%E6%80%BB%E6%8A%A5%E8%A1%A8",
        "signals": ["物料分组", "客户分组", "出库", "应收", "存货核算"],
    },
    {
        "id": "kingdee-purchase-execution",
        "vendor": "金蝶云星空",
        "domain": "供应链 ERP",
        "title": "采购订单执行明细表",
        "url": "https://help.open.kingdee.com/dokuwiki/doku.php?id=%E9%87%87%E8%B4%AD%E8%AE%A2%E5%8D%95%E6%89%A7%E8%A1%8C%E6%98%8E%E7%BB%86%E8%A1%A8",
        "signals": ["采购订单", "到货", "入库", "退料", "供应商"],
    },
    {
        "id": "kingdee-production-execution",
        "vendor": "金蝶云星空",
        "domain": "制造 ERP",
        "title": "生产订单执行明细表",
        "url": "https://help.open.kingdee.com/dokuwiki/doku.php?id=%E7%94%9F%E4%BA%A7%E8%AE%A2%E5%8D%95%E6%89%A7%E8%A1%8C%E6%98%8E%E7%BB%86%E8%A1%A8",
        "signals": ["生产订单", "产品", "车间", "计划数量", "入库数量", "达成率"],
    },
    {
        "id": "yonyou-u8-inventory-report",
        "vendor": "用友 U8",
        "domain": "进销存 ERP",
        "title": "库存、采购、销售报表分析",
        "url": "https://www.jiandaoyun.com/blog/article/848452/",
        "signals": ["库存状态", "库存周转率", "采购成本", "采购效率", "销售业绩"],
    },
    {
        "id": "wsgjp-jxc",
        "vendor": "网上管家婆",
        "domain": "中小企业进销存",
        "title": "进销存、库存预警、利润和经营报表",
        "url": "https://www.wsgjp.com.cn/Products/Jxc.aspx",
        "signals": ["采购价格", "费用分摊", "库存预警", "保质期", "利润表", "进销存变动"],
    },
    {
        "id": "sellfox-business-dashboard",
        "vendor": "赛狐",
        "domain": "跨境电商 ERP",
        "title": "经营看板、利润分析、运营分析和库存管理",
        "url": "https://www.sellfox.com/help/features/business-dashboard",
        "signals": ["店铺综合分析", "利润分析", "运营分析", "市场洞察", "库存管理", "FBA可售"],
    },
    {
        "id": "jijia-instant-dashboard",
        "vendor": "积加 ERP",
        "domain": "跨境电商 ERP",
        "title": "即时看板",
        "url": "https://help.jijiaerp.com/docs/ji-shi-kan-ban-xin",
        "signals": ["国家", "店铺", "订单销量", "销售额", "单价", "库存", "销售趋势", "下钻溯源"],
    },
    {
        "id": "wsgjp-replenishment",
        "vendor": "网上管家婆",
        "domain": "中小企业进销存",
        "title": "智能补货管理",
        "url": "https://helpnew.wsgjp.com/-/tags/%E7%BD%91%E5%BA%97ERP%E4%BC%81%E4%B8%9A%E7%89%88?_page=2",
        "signals": ["库存上下限", "可销售库存", "日均销量", "计划销售天数", "起订量", "生成补货单"],
    },
    {
        "id": "guanjia-cloud-app",
        "vendor": "管家婆云",
        "domain": "中小微企业进销存",
        "title": "利润表、老板关键数据、热销商品和销售分析",
        "url": "https://apps.apple.com/tz/app/%E7%AE%A1%E5%AE%B6%E5%A9%86%E4%BA%91app-%E8%BF%9B%E9%94%80%E5%BA%93%E5%AD%98%E7%AE%A1%E7%90%86erp%E8%BD%AF%E4%BB%B6/id1474912464",
        "signals": ["客户欠款", "库存报警", "利润表", "老板关键数据", "热销商品", "多维度销售分析"],
    },
    {
        "id": "wanliniu-bi-review",
        "vendor": "万里牛",
        "domain": "电商 ERP",
        "title": "每日看板、店铺画像、商品画像和实时大屏",
        "url": "https://www.woshipm.com/evaluating/5271289.html",
        "signals": ["销售", "采购", "库存", "应收应付", "绩效统计", "每日看板", "店铺画像", "商品画像"],
    },
]

PUBLIC_ERP_REFERENCES.extend([
    {
        "id": "jst-saas-erp-service",
        "vendor": "聚水潭",
        "domain": "电商 SaaS ERP",
        "title": "订单、商品、采购、财务、仓储、分销、客户、库存、报表和售后模块",
        "url": "https://www.ssme.sh.gov.cn/public/product%21serviceDetail.do?productId=2c91c29384560dd401845bc64dad261b",
        "signals": ["订单管理", "采购管理", "财务管理", "仓储管理", "分销管理", "客户管理", "库存管理", "报表管理", "售后管理"],
    },
    {
        "id": "jst-shengtu-logistics-report",
        "vendor": "聚水潭胜途",
        "domain": "跨境电商 ERP",
        "title": "物流对账、报表字段、拣货路径和问题处理",
        "url": "https://www.jushuitan.com/product/shengtu.html",
        "signals": ["物流对账", "报表字段", "拣货路径", "问题处理", "跨境"],
    },
    {
        "id": "kingdee-production-kitting",
        "vendor": "金蝶云星空",
        "domain": "制造 ERP",
        "title": "生产齐套分析单",
        "url": "https://help.open.kingdee.com/dokuwiki_std/doku.php?id=%E7%94%9F%E4%BA%A7%E9%BD%90%E5%A5%97%E5%88%86%E6%9E%90%E5%8D%95",
        "signals": ["生产订单", "计划开工", "计划完工", "已备料数量", "预计齐套数量", "库存齐套数量", "应发数量", "已领数量", "可领数量"],
    },
    {
        "id": "kingdee-purchase-order",
        "vendor": "金蝶云星空",
        "domain": "供应链 ERP",
        "title": "采购订单",
        "url": "https://help.open.kingdee.com/dokuwiki/doku.php?id=%E9%87%87%E8%B4%AD%E8%AE%A2%E5%8D%95",
        "signals": ["采购组织", "采购组", "供应商", "物料", "单位", "价目表", "货源清单", "交货条件"],
    },
    {
        "id": "kingdee-purchase-stockin",
        "vendor": "金蝶云星空",
        "domain": "供应链 ERP",
        "title": "采购入库单",
        "url": "https://help.open.kingdee.com/dokuwiki/doku.php?id=%E9%87%87%E8%B4%AD%E5%85%A5%E5%BA%93%E5%8D%95",
        "signals": ["计价单位", "计价数量", "采购数量", "对账中", "当前对账单号", "历史对账单号", "成本权重"],
    },
    {
        "id": "yonsuite-material-kitting",
        "vendor": "用友 YonSuite",
        "domain": "制造 ERP",
        "title": "物料齐套分析与多方式生产领料",
        "url": "https://www.yonsuite.com/infoNew/224041850264.html",
        "signals": ["物料齐套分析", "生产订单领料", "生产计划预领料", "批量领料", "生产所需物料数量"],
    },
    {
        "id": "wdt-module-overview",
        "vendor": "旺店通",
        "domain": "电商 ERP",
        "title": "订单、售后、采购、库存和数据统计模块",
        "url": "https://www.wangdian.cn/ask/2120/",
        "signals": ["订单管理", "售后管理", "采购管理", "库存管控", "数据统计", "智能拆分合并订单", "警戒库存"],
    },
    {
        "id": "wsgjp-stock-status-help",
        "vendor": "网上管家婆",
        "domain": "网店 ERP",
        "title": "库存状况查询、成本算法和入库成本异常",
        "url": "https://helpnew.wsgjp.com/-/tags/%E7%BD%91%E5%BA%97ERP%E6%97%97%E8%88%B0%E7%89%88?_page=5",
        "signals": ["库存状况", "商品库存", "序列号库存", "套餐库存", "成本算法", "预估成本均价", "可销售库存", "入库成本异常"],
    },
    {
        "id": "wsgjp-webstore-erp",
        "vendor": "网上管家婆",
        "domain": "网店 ERP",
        "title": "订单处理、多仓库存、应收应付和业务报表",
        "url": "https://www.wsgjp.com.cn/Products/Erp.aspx",
        "signals": ["订单同步", "智能审单", "库存上下限预警", "就近仓库", "应收应付", "物流运费", "供应商对账", "业务报表"],
    },
    {
        "id": "lingxing-profit-report",
        "vendor": "领星 ERP",
        "domain": "跨境电商 ERP",
        "title": "利润报表和 Summary 对账",
        "url": "https://www.lingxing.com/help/article/ProfitStatementnew",
        "signals": ["利润报表", "平台收入", "支出", "税费", "Summary总账单", "含税毛利润", "市场税", "销售税", "混合网络费"],
    },
    {
        "id": "lingxing-erp-value",
        "vendor": "领星 ERP",
        "domain": "跨境电商 ERP",
        "title": "利润、结算、回款、成本和库存损耗看板",
        "url": "https://www.lingxing.com/help/article/WhatisLINGXINGERP",
        "signals": ["利润报表", "先进先出", "移动加权", "费用分摊", "货损", "延迟结算", "店铺回款", "转账状态", "SKU回款"],
    },
    {
        "id": "sellfox-report-center",
        "vendor": "赛狐",
        "domain": "跨境电商 ERP",
        "title": "多店铺报告中心",
        "url": "https://www.sellfox.com/help/features/report-center",
        "signals": ["亚马逊原报告", "库存报告", "销量报告", "付款报告", "退货报告", "移除报告", "定时任务", "利润报表导出"],
    },
    {
        "id": "sellfox-ar-report",
        "vendor": "赛狐",
        "domain": "跨境电商 ERP",
        "title": "应收报表和回款安全",
        "url": "https://www.sellfox.com/help/features/accounts-receivable-report",
        "signals": ["应收报表", "配送费", "佣金", "结算周期", "预留金额", "实收", "资金规划"],
    },
    {
        "id": "jijia-sales-profit-analysis",
        "vendor": "积加 ERP",
        "domain": "跨境电商 ERP",
        "title": "销售利润分析和订单费用报表闭环",
        "url": "https://help.jijiaerp.com/docs/CsdBvZ96",
        "signals": ["店铺", "站点", "商品种类", "父ASIN", "子ASIN", "MSKU", "订单费用报表", "查询筛选条件"],
    },
    {
        "id": "mabang-cost-update",
        "vendor": "马帮 ERP",
        "domain": "跨境电商 ERP",
        "title": "采购价更新关联订单成本价",
        "url": "https://help.mabangerp.com/kbzx/nested/details?id=4252&resource_id=1",
        "signals": ["采购价", "订单成本价", "采购单", "关联订单", "利润报表", "字段说明"],
    },
    {
        "id": "wanliniu-open-order-stock",
        "vendor": "万里牛",
        "domain": "电商 ERP",
        "title": "订单、售后、库存和物流信息回传",
        "url": "https://open.hupun.com/guide/erp-djcj",
        "signals": ["订单链路", "发货信息回传", "售后单", "库存数据", "库存变更", "统一管理"],
    },
    {
        "id": "digiwin-manufacturing-modules",
        "vendor": "鼎捷易飞",
        "domain": "制造 ERP",
        "title": "生产、采购、销售、库存和财务管理模块",
        "url": "https://www.digiwin.com/t.php/p/15087.html",
        "signals": ["BOM", "工单", "物料齐套", "工序报工", "不良数据", "质量分析", "订单交付率"],
    },
])

PUBLIC_ERP_REFERENCES.extend([
    {
        "id": "chanjet-tcloud-connector",
        "vendor": "畅捷通 T+Cloud",
        "domain": "小微企业云 ERP",
        "title": "库存、销售和出库信息查询同步",
        "url": "https://hiflow.tencent.com/document/applications/chanjet-tcloud/",
        "signals": ["库存信息", "销售信息", "出库信息", "财务分析", "多门店经营", "生产管理"],
    },
    {
        "id": "yonyou-report-optimization",
        "vendor": "用友系产品",
        "domain": "报表资产包",
        "title": "库存、销售、采购报表优化",
        "url": "https://developer.yonyou.com/cloud/integrationAsset/assetDetail/1710582566748131329",
        "signals": ["客户余额表", "供应商余额表", "存货出入库汇总表", "库存", "销售", "采购"],
    },
    {
        "id": "kingdee-ar-management",
        "vendor": "金蝶云星空",
        "domain": "财务 ERP",
        "title": "应收款管理、账龄和对账报表",
        "url": "https://help.open.kingdee.com/dokuwiki_std/doku.php?id=%E5%BA%94%E6%94%B6%E6%AC%BE%E7%AE%A1%E7%90%86",
        "signals": ["应收款汇总表", "应收款明细表", "账龄分析表", "到期债权表", "客户对账单", "坏账风险"],
    },
    {
        "id": "guanyiyun-omni-inventory",
        "vendor": "金蝶管易云",
        "domain": "品牌电商 ERP",
        "title": "全渠道库存、商品管理和供应链提速",
        "url": "https://www.guanyiyun.com/",
        "signals": ["全渠道库存", "商品管理", "供应链", "复购率", "订单管理", "仓配"],
    },
    {
        "id": "guanyiyun-wms-case",
        "vendor": "金蝶管易云 WMS",
        "domain": "仓储 ERP",
        "title": "多仓、多货主、条码和库存准确率案例",
        "url": "https://www.yun88.com/product/1191.html",
        "signals": ["多仓库", "多货主", "库位", "条码扫描", "库存准确率", "订单核销"],
    },
    {
        "id": "dianxiaomi-amazon-profit",
        "vendor": "店小秘 ERP",
        "domain": "跨境电商 ERP",
        "title": "亚马逊利润核算六维分析",
        "url": "https://www.dianxiaomi.com/blog/article/241",
        "signals": ["订单金额", "FBA费用", "广告费", "退货费", "仓储费", "店铺", "SKU", "开发员"],
    },
    {
        "id": "dianxiaomi-estimated-profit",
        "vendor": "店小秘 ERP",
        "domain": "跨境电商 ERP",
        "title": "订单预估利润公式",
        "url": "https://help.dianxiaomi.com/pre/getContent.htm?id=839",
        "signals": ["预估利润", "订单总金额", "平台佣金", "采购成本", "预估运费", "利润率"],
    },
    {
        "id": "dianxiaomi-warehouse-cost",
        "vendor": "店小秘 ERP",
        "domain": "跨境电商 ERP",
        "title": "出库价、仓库清单单价和采购成本",
        "url": "https://help.dianxiaomi.com/pre/getContent.htm?id=474",
        "signals": ["仓库清单单价", "商品SKU出库价", "采购成本", "出库记录", "包裹号", "运单号"],
    },
    {
        "id": "wsgjp-industry-config",
        "vendor": "网上管家婆",
        "domain": "行业进销存",
        "title": "颜色尺码、批次效期和序列号行业特性",
        "url": "https://help.wsgjp.com/5e03/e630/5be3",
        "signals": ["颜色", "尺码", "保质期", "批次", "序列号", "进货入库单", "销售出库单", "库存状况表"],
    },
    {
        "id": "kingdee-jxc-modern-cases",
        "vendor": "金蝶",
        "domain": "进销存/零售 ERP",
        "title": "AI预测、多仓协同、库存健康和数据大屏案例",
        "url": "https://www.kingdee.com/resources/articles/1436035275061409953",
        "signals": ["需求预测", "动态补货", "库存健康", "多仓协同", "库存周转率", "订单履约率", "热销SKU"],
    },
    {
        "id": "mxyun-apparel-jxc",
        "vendor": "梦想云",
        "domain": "服装鞋帽进销存",
        "title": "款式、颜色尺码、库存报表和资金往来",
        "url": "https://www.mxyun.com/industry/fzxm",
        "signals": ["款式", "颜色", "尺码", "条码", "库存统计报表", "往来对账", "资金明细"],
    },
    {
        "id": "jiandaoyun-pharma-expiry",
        "vendor": "简道云",
        "domain": "医药/批次效期 ERP",
        "title": "药品批次追溯、效期预警和 FIFO",
        "url": "https://www.jiandaoyun.com/news/article/6842b00c6544d8159cd626e9",
        "signals": ["生产日期", "有效期", "效期预警", "先进先出", "效期管理报表", "批次追溯"],
    },
    {
        "id": "wsgjp-food-manufacturing-case",
        "vendor": "管家婆工贸 ERP",
        "domain": "食品制造 ERP",
        "title": "食品 BOM、限额领料、批次保质期和成本核算案例",
        "url": "https://www.cqgrasp.com/anlicczz/237.html",
        "signals": ["BOM", "材料耗用量", "损耗率", "限额领料", "批次", "保质期", "成品成本"],
    },
    {
        "id": "yonsuite-apparel-color-size",
        "vendor": "用友 YonSuite",
        "domain": "服装行业 ERP",
        "title": "尺码颜色管理与库存精准控制",
        "url": "https://www.yonsuite.com/infoNew/2250606784999.html",
        "signals": ["尺码", "颜色", "款式", "库存状态", "库存积压", "断货"],
    },
    {
        "id": "finereport-manufacturing-dashboard",
        "vendor": "帆软报表",
        "domain": "制造 ERP 报表",
        "title": "生产计划达成、供应商绩效、库存分布和质量异常驾驶舱",
        "url": "https://www.finereport.com/blog/article/68c13e25d2527e0eb7bb7dd1",
        "signals": ["生产计划达成率", "供应商绩效", "库存分布", "生产线订单进度", "质量异常预警"],
    },
])


ERP_FIELD_ALIASES: dict[str, list[str]] = {
    "order_id": ["订单号", "平台订单号", "线上单号", "原始单号", "内部单号", "trade_id", "tid", "so_id", "o_id", "order_no", "src_tid"],
    "sub_order_id": ["子订单", "子单", "明细主键", "出库明细主键", "rec_id", "sale_order_id", "src_oid"],
    "sku": ["sku", "商家编码", "规格编码", "规格码", "商品编码", "货品编号", "物料编码", "存货编码", "spec_no", "spec_code", "goods_no", "item_code", "material_code"],
    "product": ["商品名称", "货品名称", "物料名称", "产品", "品名", "规格名称", "goods_name", "spec_name", "material_name", "product_name"],
    "brand": ["品牌", "品牌名称", "brand", "brand_name"],
    "store": ["店铺", "店铺名称", "门店", "店铺编号", "shop", "shop_name", "store", "store_name"],
    "country": ["国家", "国家地区", "站点", "销售国家", "marketplace", "market", "country", "region"],
    "currency": ["币种", "结算币别", "币别", "currency", "currency_code"],
    "platform": ["平台", "渠道", "来源平台", "销售平台", "platform", "channel", "src_order_type"],
    "customer": ["客户", "客户名称", "购买方", "客商", "往来单位", "customer", "customer_name", "buyer", "buyer_name"],
    "supplier": ["供应商", "供应商名称", "供货商", "supplier", "supplier_name", "vendor"],
    "salesperson": ["业务员", "销售员", "跟单员", "员工", "employee", "salesperson", "sales_rep", "operator"],
    "warehouse": ["仓库", "仓库名称", "仓库编号", "warehouse", "warehouse_no", "warehouse_name", "wms"],
    "date": ["日期", "时间", "创建时间", "修改时间", "下单时间", "业务日期", "单据日期", "created", "modified", "created_at", "date", "order_date"],
    "outbound_date": ["出库时间", "发货时间", "审核时间", "出库单审核时间", "stock_check_time", "io_date", "send_date"],
    "purchase_date": ["采购日期", "下单日期", "到货日期", "入库日期", "收料日期", "purchase_date", "arrival_date", "stockin_date"],
    "production_date": ["生产日期", "计划开工", "计划完工", "实际完工", "完工日期", "workshop_date", "finish_date", "production_date"],
    "quantity": ["数量", "货品数量", "商品数量", "出库数量", "入库数量", "采购数量", "销售数量", "goods_count", "num", "qty", "quantity"],
    "sales_amount": ["销售额", "销售金额", "销售价", "成交金额", "总货款", "货款", "销售收入", "净销售额", "销售净额", "gmv", "revenue", "net_sales", "gross_sales", "sell_price", "total_amount", "sales_amount"],
    "average_price": ["平均售价", "客单价", "单价", "均价", "avg_price", "average_price", "unit_price", "price"],
    "paid_amount": ["实付", "已支付金额", "支付金额", "订单实付", "分摊后合计应收", "收款金额", "paid", "paid_amount", "pay_amount", "share_amount", "payment_amount", "actual_paid"],
    "cost_amount": ["成本", "成本价", "成本金额", "出库成本", "采购成本", "cost", "cost_price", "cost_amount"],
    "purchase_cost": ["采购成本", "采购成本金额", "采购货品成本", "purchase_cost", "procurement_cost"],
    "first_leg_cost": ["头程费用", "头程成本", "头程运费", "first_leg_cost", "inbound_freight"],
    "profit_amount": ["利润", "毛利", "净利润", "贡献", "净贡献", "profit", "gross_profit", "net_profit", "contribution"],
    "gross_margin_rate": ["毛利率", "利润率", "净利率", "gross_margin_rate", "profit_rate", "margin_rate"],
    "freight_amount": ["运费", "邮费", "邮资", "邮费分摊", "物流费", "快递费", "freight", "f_freight", "post_cost", "share_post"],
    "freight_gap": ["运费差异", "物流差异", "邮资差异", "freight_gap", "post_gap"],
    "refund_amount": ["退款", "退款金额", "实退金额", "退货金额", "订单退款", "refund", "refund_amount", "refund_payment"],
    "refund_status": ["退款状态", "售后状态", "shop_status", "refund_status", "status"],
    "gift_type": ["赠品", "赠品类型", "gift", "gift_type"],
    "invoice_amount": ["发票", "开票金额", "发票金额", "invoice", "invoice_amount"],
    "ar_amount": ["应收", "应收金额", "价税合计", "未收款", "未核销", "ar", "ar_amount", "receivable", "uncollected"],
    "ap_amount": ["应付", "应付金额", "未付款", "ap", "payable"],
    "purchase_amount": ["采购金额", "采购额", "采购货款", "采购价税合计", "采购含税金额", "采购未税金额", "purchase_amount", "purchase_total", "po_amount"],
    "stock_qty": ["库存", "库存数量", "可售库存", "现存量", "结存数量", "stock", "stock_qty", "inventory_qty", "sellable_qty"],
    "available_stock": ["可用库存", "可销售库存", "可售", "FBA可售", "available_stock", "sellable_stock", "fba_sellable"],
    "locked_stock": ["锁定库存", "订单锁定", "预留库存", "locked_stock", "reserved_stock"],
    "stock_amount": ["库存金额", "库存成本", "库存资本", "存货金额", "stock_amount", "inventory_amount", "capital"],
    "age_days": ["库龄", "库存天数", "周转天数", "age_days", "stock_age", "turnover_days"],
    "sellable_days": ["可销售天数", "预计可销售天数", "库存可售天数", "sellable_days", "days_of_supply"],
    "safety_stock": ["安全库存", "警戒库存", "库存预警", "safe_stock", "safety_stock"],
    "min_stock": ["库存下限", "安全库存下限", "min_stock", "stock_floor"],
    "max_stock": ["库存上限", "安全库存上限", "max_stock", "stock_ceiling"],
    "replenishment_qty": ["补货数量", "建议补货量", "采购建议量", "replenishment_qty", "reorder_qty"],
    "moq": ["起订量", "最小起订量", "moq", "min_order_qty"],
    "shelf_life": ["保质期", "效期", "到期日期", "shelf_life", "expire_date", "expiry"],
    "ad_spend": ["广告费", "广告花费", "推广费", "投放费用", "ad_spend", "advertising_cost", "promotion_cost"],
    "ad_sales": ["广告销售额", "推广销售额", "广告订单销售额", "ad_sales", "attributed_sales"],
    "ad_clicks": ["点击量", "广告点击", "clicks", "ad_clicks"],
    "ad_impressions": ["曝光量", "展示量", "impressions", "ad_impressions"],
    "acos": ["ACOS", "广告成本销售比", "acos"],
    "roas": ["ROAS", "广告投入产出比", "roas"],
    "conversion_rate": ["转化率", "CVR", "conversion_rate"],
    "delay_days": ["延迟", "延期", "逾期", "到货延迟", "入库延迟", "delay_days", "late_days"],
    "defective_qty": ["不良", "次品", "缺陷", "退料数量", "defective", "defective_qty", "reject_qty"],
    "plan_qty": ["计划数量", "计划产量", "需求数量", "plan_qty", "planned_qty"],
    "complete_qty": ["完工数量", "入库数量", "实际数量", "完成数量", "completed_qty", "finish_qty", "stockin_qty"],
    "achievement_rate": ["达成率", "完成率", "履约率", "achievement", "completion_rate", "fulfillment_rate"],
    "workshop": ["车间", "生产线", "工厂", "workshop", "factory", "line"],
    "bill_status": ["状态", "单据状态", "审核状态", "关闭状态", "status", "bill_status"],
}

ERP_FIELD_GROUP_LABELS: dict[str, str] = {
    "order_id": "订单号",
    "sub_order_id": "子订单号",
    "sku": "SKU/物料编码",
    "product": "商品/物料名称",
    "brand": "品牌",
    "store": "店铺/门店",
    "country": "国家/站点",
    "currency": "币种",
    "platform": "平台/渠道",
    "customer": "客户",
    "supplier": "供应商",
    "salesperson": "业务员/员工",
    "warehouse": "仓库",
    "date": "业务日期",
    "outbound_date": "出库/发货日期",
    "purchase_date": "采购/入库日期",
    "production_date": "生产日期",
    "quantity": "数量",
    "sales_amount": "销售金额",
    "average_price": "平均售价/单价",
    "paid_amount": "实付/收款金额",
    "cost_amount": "成本金额",
    "purchase_cost": "采购成本",
    "first_leg_cost": "头程费用",
    "profit_amount": "利润/毛利",
    "gross_margin_rate": "毛利率",
    "freight_amount": "运费",
    "freight_gap": "运费差异",
    "refund_amount": "退款金额",
    "refund_status": "退款/售后状态",
    "gift_type": "赠品标识",
    "invoice_amount": "开票金额",
    "ar_amount": "应收金额",
    "ap_amount": "应付金额",
    "purchase_amount": "采购金额",
    "stock_qty": "库存数量",
    "available_stock": "可用/可售库存",
    "locked_stock": "锁定/预留库存",
    "stock_amount": "库存金额",
    "age_days": "库龄/周转天数",
    "sellable_days": "可销售天数",
    "safety_stock": "安全库存",
    "min_stock": "库存下限",
    "max_stock": "库存上限",
    "replenishment_qty": "建议补货量",
    "moq": "起订量",
    "shelf_life": "保质期/效期",
    "ad_spend": "广告/推广费用",
    "ad_sales": "广告销售额",
    "ad_clicks": "广告点击",
    "ad_impressions": "广告曝光",
    "acos": "ACOS",
    "roas": "ROAS",
    "conversion_rate": "转化率",
    "delay_days": "延迟/逾期天数",
    "defective_qty": "不良/退料数量",
    "plan_qty": "计划数量",
    "complete_qty": "完工/入库数量",
    "achievement_rate": "达成率",
    "workshop": "车间/生产线",
    "bill_status": "单据状态",
}

ERP_FIELD_ALIASES.update({
    "order_amount": ["订单金额", "订货金额", "价税合计", "order_amount", "tax_included_amount"],
    "ordered_qty": ["订货数量", "订单数量", "下单数量", "ordered_qty", "order_qty"],
    "delivery_qty": ["发货通知数量", "发货数量", "通知发货数量", "delivery_qty", "ship_notice_qty"],
    "delivery_amount": ["发货通知金额", "发货金额", "delivery_amount", "ship_notice_amount"],
    "outbound_qty": ["已出库数量", "出库数量", "发出数量", "outbound_qty", "shipped_qty", "stockout_qty"],
    "outbound_amount": ["已出库金额", "出库金额", "outbound_amount", "stockout_amount"],
    "return_qty": ["退货数量", "销售退货数量", "退料数量", "实退数量", "return_qty", "returned_qty"],
    "return_amount": ["退货金额", "销售退货金额", "退料金额", "return_amount", "returned_amount"],
    "settlement_amount": ["结算金额", "已结算金额", "已核销金额", "settled_amount", "settlement_amount"],
    "receipt_amount": ["收款金额", "回款金额", "实收金额", "receipt_amount", "received_payment_amount"],
    "prepayment_amount": ["预收金额", "预付金额", "预留金额", "prepayment_amount", "advance_amount"],
    "writeoff_amount": ["冲销金额", "特殊冲销金额", "核销金额", "writeoff_amount", "offset_amount"],
    "unfulfilled_qty": ["未执行数量", "未发货数量", "未出库数量", "未入库数量", "欠交数量", "unfulfilled_qty", "pending_qty"],
    "fulfillment_gap_amount": ["未执行金额", "未出库金额", "未入库金额", "欠交金额", "fulfillment_gap_amount"],
    "close_status": ["关闭状态", "整单关闭状态", "行关闭状态", "close_status", "closed_status"],
    "line_status": ["行状态", "行业务关闭状态", "line_status", "line_close_status"],
    "settlement_status": ["结算状态", "回款状态", "转账状态", "settlement_status", "transfer_status"],
    "report_type": ["报表类型", "报告类型", "report_type", "statement_type"],
    "report_status": ["报告状态", "报表状态", "任务状态", "report_status", "task_status"],
    "report_generated_at": ["报告生成时间", "报表生成时间", "生成时间", "report_generated_at", "generated_at"],
    "report_period": ["报告期间", "报表期间", "请求时间范围", "统计期间", "report_period", "period"],
    "report_name": ["报告名称", "报表名称", "report_name", "statement_name"],
    "purchase_order_id": ["采购订单号", "采购订单编号", "PO号", "po_no", "purchase_order_id"],
    "purchase_org": ["采购组织", "采购部门", "采购组", "purchase_org", "purchase_department"],
    "purchaser": ["采购员", "采购负责人", "buyer_user", "purchaser", "buyer"],
    "received_qty": ["收料数量", "实收数量", "到货数量", "received_qty", "arrival_qty"],
    "received_amount": ["收料金额", "到货金额", "received_amount", "arrival_amount"],
    "stockin_qty": ["入库数量", "采购入库数量", "stockin_qty", "warehouse_in_qty"],
    "stockin_amount": ["入库金额", "采购入库金额", "stockin_amount", "warehouse_in_amount"],
    "material_return_qty": ["退料数量", "采购退料数量", "退供数量", "material_return_qty"],
    "material_return_amount": ["退料金额", "采购退料金额", "material_return_amount"],
    "payment_amount": ["付款金额", "已付款金额", "付款核销金额", "payment_amount"],
    "prepaid_amount": ["预付金额", "预付款金额", "prepaid_amount"],
    "special_writeoff_amount": ["特殊冲销金额", "结算调整金额", "special_writeoff_amount"],
    "receipt_doc_id": ["收料单号", "收料单据编号", "receipt_doc_id"],
    "stockin_doc_id": ["入库单号", "入库单据编号", "stockin_doc_id"],
    "invoice_id": ["发票号", "发票单号", "开票单号", "invoice_id"],
    "payment_id": ["付款单号", "收款单号", "payment_id", "receipt_id"],
    "production_order_id": ["生产订单", "生产订单号", "工单号", "work_order_no", "production_order_id"],
    "prepared_qty": ["已备料数量", "备料数量", "prepared_qty"],
    "analysis_qty": ["分析数量", "齐套分析数量", "analysis_qty"],
    "expected_kit_qty": ["预计齐套数量", "可齐套数量", "expected_kit_qty"],
    "inventory_kit_qty": ["库存齐套数量", "库存加在途材料齐套数量", "inventory_kit_qty"],
    "issued_qty": ["已领数量", "已发数量", "issued_qty"],
    "overissued_qty": ["超发数量", "超领数量", "overissued_qty"],
    "issuable_qty": ["可领数量", "可发数量", "issuable_qty"],
    "shortage_qty": ["欠料数量", "缺料数量", "短缺数量", "shortage_qty", "missing_qty"],
    "bom_material": ["子项材料", "BOM物料", "材料编码", "材料名称", "bom_material", "component_material"],
    "process": ["工序", "工艺路线", "process", "routing"],
    "work_hours": ["工时", "标准工时", "实际工时", "work_hours", "labor_hours"],
    "scrap_qty": ["报废数量", "损耗数量", "scrap_qty"],
    "quality_pass_rate": ["合格率", "一次合格率", "良率", "quality_pass_rate", "pass_rate"],
    "rework_qty": ["返工数量", "返修数量", "rework_qty"],
    "inspection_result": ["质检结果", "检验结果", "inspection_result"],
    "serial_stock_qty": ["序列号库存", "一品一码库存", "serial_stock_qty"],
    "package_stock_qty": ["套餐库存", "组合装库存", "package_stock_qty", "bundle_stock_qty"],
    "cost_method": ["成本算法", "计价方式", "成本计价方式", "cost_method"],
    "estimated_unit_cost": ["预估成本均价", "成本均价", "estimated_unit_cost"],
    "reference_cost": ["参考成本", "参考成本价", "reference_cost"],
    "estimated_stock_amount": ["预估库存金额", "库存成本金额", "estimated_stock_amount"],
    "reference_sales_amount": ["参考销售总价", "预设售价总额", "reference_sales_amount"],
    "reference_margin_rate": ["参考毛利率", "预估毛利率", "reference_margin_rate"],
    "cost_anomaly_flag": ["入库成本异常", "成本异常", "异常成本", "cost_anomaly_flag"],
    "batch_no": ["批次号", "生产批号", "批号", "batch_no", "lot_no"],
    "expiry_date": ["到期日期", "失效日期", "有效期至", "expiry_date"],
    "remaining_shelf_life": ["剩余效期", "过期天数", "remaining_shelf_life"],
    "daily_sales": ["日均销量", "日均销售", "daily_sales"],
    "planned_sales_days": ["计划销售天数", "planned_sales_days"],
    "platform_income": ["平台收入", "收入", "平台回款", "platform_income"],
    "platform_expense": ["平台支出", "支出", "费用支出", "platform_expense"],
    "platform_tax": ["平台税费", "税费", "platform_tax"],
    "transaction_amount": ["交易金额", "交易明细金额", "动账金额", "transaction_amount"],
    "summary_statement_amount": ["Summary总账单金额", "总账单金额", "summary_statement_amount"],
    "marketplace_tax": ["市场税", "marketplace_tax"],
    "sales_tax": ["销售税", "sales_tax"],
    "sales_tax_refund": ["销售税退款额", "sales_tax_refund"],
    "marketplace_tax_refund": ["市场税退款额", "marketplace_tax_refund"],
    "mixed_network_fee": ["混合网络费", "mixed_network_fee"],
    "storage_fee": ["仓储费", "月仓储费", "storage_fee"],
    "long_term_storage_fee": ["长期仓储费", "long_term_storage_fee"],
    "reimbursement_amount": ["赔偿金额", "赔偿数量", "reimbursement_amount"],
    "removal_fee": ["移除费用", "移除费", "removal_fee"],
    "inventory_adjustment_amount": ["库存调整金额", "库存差异金额", "货损金额", "inventory_adjustment_amount"],
    "settlement_date": ["结算日期", "回款日期", "预计回款时间", "settlement_date"],
    "expected_payment_date": ["预计回款时间", "预测回款时间", "expected_payment_date"],
    "listing": ["Listing", "链接", "listing"],
    "asin": ["ASIN", "子ASIN", "asin"],
    "msku": ["MSKU", "卖家SKU", "msku"],
    "parent_asin": ["父ASIN", "parent_asin"],
    "sales_volume": ["销量", "订单销量", "销售量", "sales_volume"],
    "order_count": ["订单数", "订单量", "order_count"],
    "return_reason": ["退货原因", "售后原因", "退款原因", "return_reason"],
    "exchange_amount": ["换货金额", "exchange_amount"],
    "after_sales_type": ["售后类型", "退换货类型", "after_sales_type"],
    "review_score": ["评分", "评价分", "review_score"],
    "customer_complaint_count": ["客诉数量", "投诉数量", "customer_complaint_count"],
    "distributor": ["分销商", "经销商", "分销商编号", "distributor"],
    "member_level": ["会员等级", "客户等级", "member_level"],
    "vip_customer": ["VIP客户", "重点客户", "vip_customer"],
    "visit_count": ["拜访次数", "巡店次数", "visit_count"],
    "route": ["拜访路线", "配送路线", "route"],
    "province": ["省", "省份", "receiver_state", "province"],
    "city": ["市", "城市", "receiver_city", "city"],
    "logistics_company": ["快递公司", "物流公司", "承运商", "logistics_company", "lc_id"],
    "tracking_no": ["快递单号", "物流单号", "运单号", "tracking_no"],
    "weight": ["预估重量", "重量", "weight"],
    "actual_weight": ["实称重量", "实际重量", "actual_weight", "f_weight"],
    "package_count": ["包裹数", "箱数", "package_count"],
    "capacity": ["产能", "产线产能", "capacity"],
    "machine": ["设备", "机台", "machine"],
    "equipment_status": ["设备状态", "equipment_status"],
    "schedule_priority": ["优先级", "排程优先级", "schedule_priority"],
    "on_time_delivery_rate": ["准时交付率", "订单准时交付率", "on_time_delivery_rate"],
    "stockout_risk": ["断货风险", "缺货风险", "stockout_risk"],
})

ERP_FIELD_GROUP_LABELS.update({
    "order_amount": "订单金额",
    "ordered_qty": "订货/订单数量",
    "delivery_qty": "发货通知数量",
    "delivery_amount": "发货通知金额",
    "outbound_qty": "已出库数量",
    "outbound_amount": "已出库金额",
    "return_qty": "退货/退料数量",
    "return_amount": "退货/退料金额",
    "settlement_amount": "结算/核销金额",
    "receipt_amount": "收款/回款金额",
    "prepayment_amount": "预收/预付金额",
    "writeoff_amount": "冲销/核销金额",
    "unfulfilled_qty": "未执行/欠交数量",
    "fulfillment_gap_amount": "未执行/欠交金额",
    "close_status": "关闭状态",
    "line_status": "行状态",
    "settlement_status": "结算/转账状态",
    "report_type": "报告类型",
    "report_status": "报告状态",
    "report_generated_at": "报告生成时间",
    "report_period": "报告期间",
    "report_name": "报告名称",
    "purchase_order_id": "采购订单号",
    "purchase_org": "采购组织/部门",
    "purchaser": "采购员",
    "received_qty": "收料/到货数量",
    "received_amount": "收料/到货金额",
    "stockin_qty": "入库数量",
    "stockin_amount": "入库金额",
    "material_return_qty": "退料数量",
    "material_return_amount": "退料金额",
    "payment_amount": "付款金额",
    "prepaid_amount": "预付款金额",
    "special_writeoff_amount": "特殊冲销/调整金额",
    "receipt_doc_id": "收料单号",
    "stockin_doc_id": "入库单号",
    "invoice_id": "发票单号",
    "payment_id": "付款/收款单号",
    "production_order_id": "生产订单/工单",
    "prepared_qty": "已备料数量",
    "analysis_qty": "齐套分析数量",
    "expected_kit_qty": "预计齐套数量",
    "inventory_kit_qty": "库存齐套数量",
    "issued_qty": "已领/已发数量",
    "overissued_qty": "超发/超领数量",
    "issuable_qty": "可领/可发数量",
    "shortage_qty": "欠料/缺料数量",
    "bom_material": "BOM 子项材料",
    "process": "工序/工艺路线",
    "work_hours": "工时",
    "scrap_qty": "报废/损耗数量",
    "quality_pass_rate": "质量合格率",
    "rework_qty": "返工/返修数量",
    "inspection_result": "质检结果",
    "serial_stock_qty": "序列号库存",
    "package_stock_qty": "套餐/组合装库存",
    "cost_method": "成本算法/计价方式",
    "estimated_unit_cost": "预估成本均价",
    "reference_cost": "参考成本",
    "estimated_stock_amount": "预估库存金额",
    "reference_sales_amount": "参考销售总价",
    "reference_margin_rate": "参考毛利率",
    "cost_anomaly_flag": "入库成本异常",
    "batch_no": "批次号",
    "expiry_date": "到期日期",
    "remaining_shelf_life": "剩余效期/过期天数",
    "daily_sales": "日均销量",
    "planned_sales_days": "计划销售天数",
    "platform_income": "平台收入",
    "platform_expense": "平台支出",
    "platform_tax": "平台税费",
    "transaction_amount": "交易/动账金额",
    "summary_statement_amount": "Summary 总账单金额",
    "marketplace_tax": "市场税",
    "sales_tax": "销售税",
    "sales_tax_refund": "销售税退款额",
    "marketplace_tax_refund": "市场税退款额",
    "mixed_network_fee": "混合网络费",
    "storage_fee": "仓储费",
    "long_term_storage_fee": "长期仓储费",
    "reimbursement_amount": "赔偿金额",
    "removal_fee": "移除费用",
    "inventory_adjustment_amount": "库存调整/货损金额",
    "settlement_date": "结算/回款日期",
    "expected_payment_date": "预计回款时间",
    "listing": "Listing",
    "asin": "ASIN",
    "msku": "MSKU",
    "parent_asin": "父 ASIN",
    "sales_volume": "销量",
    "order_count": "订单数",
    "return_reason": "退货/售后原因",
    "exchange_amount": "换货金额",
    "after_sales_type": "售后类型",
    "review_score": "评价分",
    "customer_complaint_count": "客诉数量",
    "distributor": "分销商",
    "member_level": "会员等级",
    "vip_customer": "重点客户",
    "visit_count": "拜访/巡店次数",
    "route": "路线",
    "province": "省份",
    "city": "城市",
    "logistics_company": "快递/物流公司",
    "tracking_no": "快递/物流单号",
    "weight": "预估重量",
    "actual_weight": "实称重量",
    "package_count": "包裹/箱数",
    "capacity": "产能",
    "machine": "设备/机台",
    "equipment_status": "设备状态",
    "schedule_priority": "排程优先级",
    "on_time_delivery_rate": "准时交付率",
    "stockout_risk": "断货风险",
})

ERP_FIELD_ALIASES.update({
    "color": ["颜色", "颜色名称", "色号", "color", "color_name"],
    "size": ["尺码", "规格尺码", "尺码名称", "size", "size_name"],
    "style": ["款式", "款号", "款式编号", "style", "style_no", "style_code"],
    "model": ["型号", "规格型号", "model", "model_no"],
    "barcode": ["条码", "商品条码", "箱码", "二维码", "barcode", "bar_code"],
    "unit": ["单位", "基本单位", "计量单位", "销售单位", "unit", "uom"],
    "unit_conversion": ["单位换算", "换算率", "换算比例", "unit_conversion", "conversion_rate"],
    "retail_price": ["零售价", "吊牌价", "建议零售价", "retail_price", "list_price"],
    "wholesale_price": ["批发价", "批发价格", "wholesale_price"],
    "tax_rate": ["税率", "销项税率", "进项税率", "tax_rate", "vat_rate"],
    "tax_amount": ["税额", "销项税额", "进项税额", "tax_amount", "vat_amount"],
    "discount_amount": ["折扣", "折扣金额", "优惠金额", "discount", "discount_amount"],
    "promotion_amount": ["促销金额", "促销优惠", "活动优惠", "promotion_amount"],
    "coupon_amount": ["优惠券金额", "券金额", "coupon_amount"],
    "payment_method": ["支付方式", "结算方式", "收款方式", "payment_method", "pay_type"],
    "cashier": ["收银员", "收款员", "cashier"],
    "shop_guide": ["导购", "店员", "shop_guide", "guide"],
    "terminal": ["收银机", "POS机", "终端", "terminal", "pos_terminal"],
    "member_id": ["会员编号", "会员ID", "会员卡号", "member_id", "vip_id"],
    "member_points": ["会员积分", "积分", "member_points", "points"],
    "stock_transfer_qty": ["调拨数量", "移库数量", "transfer_qty", "stock_transfer_qty"],
    "inventory_count_qty": ["盘点数量", "实盘数量", "count_qty", "inventory_count_qty"],
    "inventory_gain_qty": ["盘盈数量", "盘盈", "inventory_gain_qty"],
    "inventory_loss_qty": ["盘亏数量", "盘亏", "inventory_loss_qty"],
    "stock_diff_qty": ["库存差异数量", "账实差异", "差异数量", "stock_diff_qty"],
    "inventory_turnover_rate": ["库存周转率", "周转率", "inventory_turnover_rate", "turnover_rate"],
    "slow_moving_flag": ["滞销", "呆滞", "慢动销", "slow_moving_flag", "dead_stock_flag"],
    "forecast_qty": ["预测销量", "预测需求", "forecast_qty", "demand_forecast_qty"],
    "recommended_purchase_qty": ["推荐采购量", "建议采购量", "recommended_purchase_qty"],
    "platform_commission": ["平台佣金", "佣金", "commission", "platform_commission"],
    "fba_fee": ["FBA费用", "FBA配送费", "配送费", "fba_fee", "fulfillment_fee"],
    "refund_fee": ["退货费", "退款手续费", "refund_fee", "return_fee"],
    "estimated_profit": ["预估利润", "预计利润", "estimated_profit"],
    "profit_rate": ["利润率", "预估利润率", "profit_rate"],
    "developer": ["开发员", "产品开发员", "developer", "product_developer"],
    "fee_allocation_method": ["费用分摊方式", "分摊方式", "allocation_method", "fee_allocation_method"],
    "labor_cost": ["人工成本", "人力成本", "labor_cost"],
    "utilities_cost": ["水电费", "能耗费用", "utilities_cost", "energy_cost"],
    "sku_weight": ["商品重量", "SKU重量", "净重", "sku_weight", "net_weight"],
    "sku_volume": ["商品体积", "SKU体积", "体积", "sku_volume", "volume"],
    "parcel_no": ["包裹号", "包裹编号", "parcel_no", "package_no"],
    "bin_location": ["库位", "货位", "仓位", "bin_location", "location_code"],
    "owner": ["货主", "货主名称", "owner", "owner_name"],
    "customer_balance": ["客户余额", "客户欠款", "客户应收余额", "customer_balance"],
    "supplier_balance": ["供应商余额", "供应商欠款", "供应商应付余额", "supplier_balance"],
    "aging_bucket": ["账龄段", "账龄区间", "aging_bucket"],
    "aging_days": ["账龄天数", "逾期天数", "aging_days", "overdue_days"],
    "overdue_amount": ["逾期金额", "到期未收金额", "overdue_amount"],
    "bad_debt_risk": ["坏账风险", "坏账预测", "bad_debt_risk"],
    "due_date": ["到期日", "应收日期", "应付日期", "due_date"],
    "collection_plan": ["收款计划", "回款计划", "collection_plan"],
    "voucher_id": ["凭证号", "凭证编号", "voucher_id", "voucher_no"],
    "account_subject": ["科目", "会计科目", "account_subject", "account_code"],
    "department": ["部门", "业务部门", "department", "dept"],
    "project": ["项目", "项目名称", "project", "project_name"],
    "cash_account": ["现金账户", "账户", "cash_account"],
    "bank_account": ["银行账户", "账号", "bank_account"],
    "income_amount": ["收入金额", "收支收入", "income_amount"],
    "expense_amount": ["费用金额", "支出金额", "expense_amount"],
    "cash_flow_amount": ["现金流金额", "资金流水金额", "cash_flow_amount"],
    "bom_version": ["BOM版本", "配方版本", "bom_version", "recipe_version"],
    "work_center": ["工作中心", "产线", "work_center"],
    "planned_start_date": ["计划开工日期", "计划开始时间", "planned_start_date"],
    "planned_finish_date": ["计划完工日期", "计划结束时间", "planned_finish_date"],
    "actual_start_date": ["实际开工日期", "实际开始时间", "actual_start_date"],
    "actual_finish_date": ["实际完工日期", "实际结束时间", "actual_finish_date"],
    "wip_qty": ["在制数量", "在制品数量", "wip_qty"],
    "good_qty": ["良品数量", "合格数量", "good_qty"],
    "bad_qty": ["不良数量", "坏品数量", "bad_qty"],
    "yield_rate": ["良品率", "产出率", "yield_rate"],
    "outsourced_qty": ["委外数量", "外协数量", "outsourced_qty"],
    "inspection_report": ["检验报告", "质检报告", "inspection_report"],
    "temperature": ["温度", "仓库温度", "冷链温度", "temperature"],
    "humidity": ["湿度", "仓库湿度", "humidity"],
    "cold_chain_flag": ["冷链", "冷藏标识", "cold_chain_flag"],
    "near_expiry_flag": ["近效期", "临期", "near_expiry_flag"],
    "fifo_batch_order": ["先进先出", "近期先出", "批次出库顺序", "fifo_batch_order"],
})

ERP_FIELD_GROUP_LABELS.update({
    "color": "颜色",
    "size": "尺码",
    "style": "款式",
    "model": "型号",
    "barcode": "条码",
    "unit": "计量单位",
    "unit_conversion": "单位换算",
    "retail_price": "零售价",
    "wholesale_price": "批发价",
    "tax_rate": "税率",
    "tax_amount": "税额",
    "discount_amount": "折扣金额",
    "promotion_amount": "促销金额",
    "coupon_amount": "优惠券金额",
    "payment_method": "支付/结算方式",
    "cashier": "收银员",
    "shop_guide": "导购/店员",
    "terminal": "POS 终端",
    "member_id": "会员编号",
    "member_points": "会员积分",
    "stock_transfer_qty": "调拨数量",
    "inventory_count_qty": "盘点数量",
    "inventory_gain_qty": "盘盈数量",
    "inventory_loss_qty": "盘亏数量",
    "stock_diff_qty": "库存差异数量",
    "inventory_turnover_rate": "库存周转率",
    "slow_moving_flag": "滞销/呆滞标识",
    "forecast_qty": "预测需求/销量",
    "recommended_purchase_qty": "推荐采购量",
    "platform_commission": "平台佣金",
    "fba_fee": "FBA/配送费",
    "refund_fee": "退货/退款费用",
    "estimated_profit": "预估利润",
    "profit_rate": "利润率",
    "developer": "开发员",
    "fee_allocation_method": "费用分摊方式",
    "labor_cost": "人工成本",
    "utilities_cost": "水电/能耗费用",
    "sku_weight": "商品重量",
    "sku_volume": "商品体积",
    "parcel_no": "包裹号",
    "bin_location": "库位/货位",
    "owner": "货主",
    "customer_balance": "客户余额/欠款",
    "supplier_balance": "供应商余额/欠款",
    "aging_bucket": "账龄段",
    "aging_days": "账龄/逾期天数",
    "overdue_amount": "逾期金额",
    "bad_debt_risk": "坏账风险",
    "due_date": "到期日",
    "collection_plan": "收款计划",
    "voucher_id": "凭证号",
    "account_subject": "会计科目",
    "department": "部门",
    "project": "项目",
    "cash_account": "现金账户",
    "bank_account": "银行账户",
    "income_amount": "收入金额",
    "expense_amount": "支出金额",
    "cash_flow_amount": "现金流金额",
    "bom_version": "BOM/配方版本",
    "work_center": "工作中心",
    "planned_start_date": "计划开工日期",
    "planned_finish_date": "计划完工日期",
    "actual_start_date": "实际开工日期",
    "actual_finish_date": "实际完工日期",
    "wip_qty": "在制数量",
    "good_qty": "良品数量",
    "bad_qty": "不良数量",
    "yield_rate": "良品率",
    "outsourced_qty": "委外数量",
    "inspection_report": "检验报告",
    "temperature": "温度",
    "humidity": "湿度",
    "cold_chain_flag": "冷链标识",
    "near_expiry_flag": "近效期标识",
    "fifo_batch_order": "FIFO 批次顺序",
})


def _unit(
    key: str,
    category: str,
    widget_type: str,
    title: str,
    reason: str,
    sources: list[str],
    required: dict[str, list[str]] | None = None,
    optional: dict[str, list[str]] | None = None,
    signals: list[str] | None = None,
    anchors: list[str] | None = None,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "category": category,
        "type": widget_type,
        "title": title,
        "reason": reason,
        "sources": sources,
        "required": required or {},
        "optional": optional or {},
        "signals": signals or [],
        "anchors": anchors or [],
        "options": options or {},
    }


ERP_DASHBOARD_UNITS: list[dict[str, Any]] = [
    _unit("sales-paid-kpi", "订单/销售", "metric", "实付销售额", "先确认真实成交规模，优先使用已支付或分摊应收字段。", ["jst-sales-outbound", "wdt-stockout-detail"], {"measure": ["paid_amount", "sales_amount"]}, {"date": ["date", "outbound_date"]}, options={"aggregation": "sum", "valueFormat": "currency"}),
    _unit("sales-trend", "订单/销售", "line", "销售趋势", "按下单、出库或业务日期观察销售波动。", ["kingdee-sales-order-execution", "yonyou-u8-inventory-report"], {"measure": ["paid_amount", "sales_amount"], "dimension": ["date", "outbound_date"]}, {"filter": ["platform", "store"]}, options={"aggregation": "sum", "valueFormat": "currency", "areaFill": True, "colorPalette": "fresh", "sortDirection": "asc", "topN": 24}),
    _unit("store-sales-rank", "订单/销售", "bar", "店铺销售排行", "多店铺或多渠道先看贡献集中度。", ["jst-sales-outbound", "wdt-api-index"], {"measure": ["paid_amount", "sales_amount"], "dimension": ["store", "platform"]}, {"date": ["date"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "rankingMode": "ranked", "topN": 12}),
    _unit("sku-sales-rank", "订单/销售", "bar", "SKU 销售排行", "把商品、物料或 SKU 作为经营拆解入口。", ["wdt-stockout-detail", "kingdee-sales-outbound-summary"], {"measure": ["paid_amount", "sales_amount"], "dimension": ["sku", "product"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "rankingMode": "ranked", "topN": 15}),
    _unit("customer-sales-rank", "订单/销售", "bar", "客户销售排行", "适合批发、制造和分销场景检查客户集中度。", ["kingdee-sales-order-execution"], {"measure": ["paid_amount", "sales_amount"], "dimension": ["customer"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 12}),
    _unit("channel-mix", "订单/销售", "pie", "渠道构成", "按平台、渠道、店铺看销售占比，避免只看总数。", ["wdt-api-index", "jst-sales-outbound"], {"measure": ["paid_amount", "sales_amount"], "dimension": ["platform", "store"]}, options={"aggregation": "sum", "valueFormat": "currency", "pieShape": "donut", "showDataLabel": True, "topN": 8}),
    _unit("order-detail-table", "订单/销售", "table", "订单明细核查", "保留订单、子单、SKU、金额、状态，方便回查异常。", ["wdt-stockout-detail", "kingdee-sales-order-execution"], {}, {"order": ["order_id"], "subOrder": ["sub_order_id"], "sku": ["sku"], "product": ["product"], "amount": ["paid_amount", "sales_amount"], "status": ["bill_status", "refund_status"]}, signals=["order_id", "sku", "paid_amount"], options={"aggregation": "count", "tableColumnLimit": 8, "topN": 100}),
    _unit("outbound-amount-kpi", "出库/物流", "metric", "销售出库金额", "聚合销售出库或发货后的业务金额，适合与应收勾稽。", ["jst-sales-outbound", "kingdee-sales-outbound-summary"], {"measure": ["paid_amount", "sales_amount"]}, {"date": ["outbound_date"]}, options={"aggregation": "sum", "valueFormat": "currency"}),
    _unit("outbound-trend", "出库/物流", "line", "出库趋势", "按出库审核或发货时间看履约节奏。", ["jst-sales-outbound", "wdt-stockout-detail"], {"measure": ["quantity", "paid_amount", "sales_amount"], "dimension": ["outbound_date", "date"]}, options={"aggregation": "sum", "valueFormat": "compact", "areaFill": True, "topN": 24}),
    _unit("warehouse-outbound-rank", "出库/物流", "bar", "仓库出库排行", "多仓发货先看仓库压力和贡献。", ["wdt-api-index", "jst-sales-outbound"], {"measure": ["quantity", "paid_amount", "sales_amount"], "dimension": ["warehouse"]}, options={"aggregation": "sum", "valueFormat": "compact", "barOrientation": "horizontal", "topN": 12}),
    _unit("freight-kpi", "出库/物流", "metric", "运费合计", "用于快递、邮资或平台运费对账。", ["jst-sales-outbound", "wdt-stockout-detail"], {"measure": ["freight_amount"]}, {"dimension": ["date", "outbound_date"]}, options={"aggregation": "sum", "valueFormat": "currency"}),
    _unit("freight-gap-rank", "出库/物流", "bar", "运费差异排行", "优先定位物流费用差异最大的订单、快递或店铺。", ["wdt-stockout-detail"], {"measure": ["freight_gap", "freight_amount"], "dimension": ["order_id", "store", "warehouse"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 12}),
    _unit("logistics-detail-table", "出库/物流", "table", "物流出库明细", "把物流单号、重量、邮资、仓库和 SKU 放在同一张核查表。", ["wdt-stockout-detail", "wdt-api-index"], {}, {"order": ["order_id"], "sku": ["sku"], "warehouse": ["warehouse"], "freight": ["freight_amount"], "qty": ["quantity"], "date": ["outbound_date"]}, signals=["order_id", "freight_amount", "warehouse"], options={"aggregation": "count", "tableColumnLimit": 8, "topN": 100}),
    _unit("refund-kpi", "售后/退款", "metric", "退款金额", "退货退款先看实退或订单退款金额。", ["jst-refund", "wdt-stockout-detail"], {"measure": ["refund_amount"]}, {"date": ["date"]}, options={"aggregation": "sum", "valueFormat": "currency"}),
    _unit("refund-status-slicer", "售后/退款", "slicer", "退款状态筛选", "把售后状态做成切片器，避免成功退款、申请退款混在一起。", ["jst-refund", "wdt-stockout-detail"], {"dimension": ["refund_status"]}, options={"aggregation": "count", "slicerMultiSelect": True, "globalFilterTarget": True, "drillDown": False}),
    _unit("refund-status-mix", "售后/退款", "pie", "售后状态构成", "退款成功、等待退货、关闭等状态需要分开看。", ["jst-refund", "wdt-stockout-detail"], {"dimension": ["refund_status"], "measure": ["refund_amount", "quantity"]}, options={"aggregation": "sum", "valueFormat": "currency", "pieShape": "donut", "showDataLabel": True}),
    _unit("refund-sku-rank", "售后/退款", "bar", "SKU 退款排行", "识别退款集中商品，辅助质量、描述和物流复盘。", ["jst-refund", "wdt-stockout-detail"], {"measure": ["refund_amount"], "dimension": ["sku", "product"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 12}),
    _unit("gift-cost-risk", "售后/退款", "table", "赠品与退款风险明细", "赠品没有收入但可能有成本，退款状态也会影响利润口径。", ["wdt-stockout-detail"], {}, {"gift": ["gift_type"], "refund": ["refund_status"], "sku": ["sku"], "amount": ["paid_amount", "sales_amount"], "cost": ["cost_amount"]}, signals=["gift_type", "refund_status", "sku"], options={"aggregation": "count", "tableColumnLimit": 8, "topN": 100}),
    _unit("profit-kpi", "利润/费用", "metric", "利润/毛利", "如果源表已有利润或毛利字段，优先作为经营结果卡。", ["wdt-stockout-detail", "wsgjp-jxc"], {"measure": ["profit_amount"]}, {"dimension": ["date"]}, options={"aggregation": "sum", "valueFormat": "currency"}),
    _unit("sku-profit-rank", "利润/费用", "bar", "SKU 利润排行", "旺店通类订单明细常用 SKU、成本、售价、退款状态综合看毛利。", ["wdt-stockout-detail"], {"measure": ["profit_amount", "sales_amount"], "dimension": ["sku", "product"]}, {"cost": ["cost_amount"], "refund": ["refund_status"], "gift": ["gift_type"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "rankingMode": "ranked", "topN": 15}),
    _unit("cost-rank", "利润/费用", "bar", "成本费用排行", "采购成本、物流费、平台费用或商品成本先按对象排行。", ["wsgjp-jxc", "wdt-stockout-detail"], {"measure": ["cost_amount", "freight_amount"], "dimension": ["sku", "product", "store", "supplier"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 12}),
    _unit("ar-kpi", "应收/对账", "metric", "应收金额", "金蝶类销售执行报表需要把应收与出库、开票、收款分开。", ["kingdee-sales-order-execution", "kingdee-sales-outbound-summary"], {"measure": ["ar_amount"]}, {"date": ["date"]}, options={"aggregation": "sum", "valueFormat": "currency"}),
    _unit("ar-customer-rank", "应收/对账", "bar", "客户应收排行", "按客户定位应收余额或未收款风险。", ["kingdee-sales-order-execution"], {"measure": ["ar_amount"], "dimension": ["customer"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 12}),
    _unit("invoice-ar-gap", "应收/对账", "table", "出库-应收-开票勾稽明细", "同一订单可能拆批出库或红字冲销，先保留订单级证据。", ["kingdee-sales-order-execution", "kingdee-sales-outbound-summary"], {}, {"order": ["order_id"], "customer": ["customer"], "outbound": ["sales_amount", "paid_amount"], "ar": ["ar_amount"], "invoice": ["invoice_amount"], "date": ["date"]}, signals=["order_id", "ar_amount", "invoice_amount"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("purchase-amount-kpi", "采购/供应商", "metric", "采购金额", "采购订单执行先看采购规模。", ["kingdee-purchase-execution", "yonyou-u8-inventory-report"], {"measure": ["purchase_amount", "cost_amount", "ap_amount"]}, {"date": ["purchase_date", "date"], "supplier": ["supplier"]}, options={"aggregation": "sum", "valueFormat": "currency"}),
    _unit("supplier-purchase-rank", "采购/供应商", "bar", "供应商采购排行", "按供应商看采购额、入库量或成本集中度。", ["kingdee-purchase-execution"], {"measure": ["cost_amount", "quantity", "ap_amount"], "dimension": ["supplier"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 12}),
    _unit("supplier-delay-rank", "采购/供应商", "bar", "供应商交付延迟排行", "把到货、入库、延期和供应商放在一起看履约风险。", ["kingdee-purchase-execution"], {"measure": ["delay_days"], "dimension": ["supplier"]}, {"defect": ["defective_qty"]}, options={"aggregation": "sum", "valueFormat": "plain", "barOrientation": "horizontal", "topN": 12}),
    _unit("purchase-execution-table", "采购/供应商", "table", "采购执行明细", "采购订单、到货、入库、退料和供应商需要同屏核查。", ["kingdee-purchase-execution"], {}, {"supplier": ["supplier"], "order": ["order_id"], "date": ["purchase_date"], "qty": ["quantity"], "amount": ["cost_amount", "ap_amount"], "delay": ["delay_days"], "defect": ["defective_qty"]}, signals=["supplier", "quantity", "purchase_date"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("inventory-qty-kpi", "库存/周转", "metric", "库存数量", "先确认当前可售、现存或结存数量。", ["yonyou-u8-inventory-report", "wsgjp-jxc"], {"measure": ["stock_qty"]}, options={"aggregation": "sum", "valueFormat": "compact"}),
    _unit("inventory-capital-kpi", "库存/周转", "metric", "库存金额", "库存积压和资金占用先看金额。", ["wsgjp-jxc", "yonyou-u8-inventory-report"], {"measure": ["stock_amount", "cost_amount"]}, options={"aggregation": "sum", "valueFormat": "currency"}),
    _unit("sku-stock-rank", "库存/周转", "bar", "SKU 库存排行", "按 SKU 或物料定位库存集中度。", ["wsgjp-jxc"], {"measure": ["stock_qty", "stock_amount"], "dimension": ["sku", "product"]}, options={"aggregation": "sum", "valueFormat": "compact", "barOrientation": "horizontal", "topN": 15}),
    _unit("slow-moving-capital", "库存/周转", "bar", "滞销资金排行", "库龄或周转天数结合库存金额，定位慢动销占用。", ["yonyou-u8-inventory-report", "wsgjp-jxc"], {"measure": ["stock_amount", "stock_qty"], "dimension": ["sku", "product"]}, {"age": ["age_days"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 12}),
    _unit("warehouse-stock-mix", "库存/周转", "pie", "仓库库存构成", "多仓库存需要先看分布，防止局部缺货或积压。", ["wsgjp-jxc", "wdt-api-index"], {"measure": ["stock_qty", "stock_amount"], "dimension": ["warehouse"]}, options={"aggregation": "sum", "valueFormat": "compact", "pieShape": "donut", "showDataLabel": True, "topN": 8}),
    _unit("stock-warning-table", "库存/周转", "table", "库存预警明细", "安全库存、库龄、保质期和现存量适合做明细核查。", ["wsgjp-jxc"], {}, {"sku": ["sku"], "product": ["product"], "stock": ["stock_qty"], "safety": ["safety_stock"], "age": ["age_days"], "shelf": ["shelf_life"], "warehouse": ["warehouse"]}, signals=["stock_qty", "sku", "safety_stock"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("sellable-stock-kpi", "库存/补货", "metric", "可销售库存", "跨境和多仓场景先确认真正可售的库存，而不是账面总库存。", ["sellfox-business-dashboard", "wdt-api-index", "wsgjp-replenishment"], {"measure": ["available_stock", "stock_qty"]}, options={"aggregation": "sum", "valueFormat": "compact"}),
    _unit("locked-stock-kpi", "库存/补货", "metric", "锁定/预留库存", "订单预留或库存同步会影响可售量，需要和现存量分开看。", ["wdt-api-index", "kingdee-sales-order-execution"], {"measure": ["locked_stock"]}, options={"aggregation": "sum", "valueFormat": "compact"}),
    _unit("sellable-days-rank", "库存/补货", "bar", "可销售天数排行", "按商品或仓库找出快断货和长时间占库存的对象。", ["wsgjp-replenishment", "sellfox-business-dashboard"], {"measure": ["sellable_days", "age_days"], "dimension": ["sku", "product", "warehouse"]}, options={"aggregation": "avg", "valueFormat": "compact", "barOrientation": "horizontal", "topN": 15}),
    _unit("replenishment-qty-rank", "库存/补货", "bar", "建议补货量排行", "把智能补货的建议数量变成优先级列表，减少人工翻表。", ["wsgjp-replenishment", "jijia-instant-dashboard"], {"measure": ["replenishment_qty"], "dimension": ["sku", "product", "supplier", "warehouse"]}, {"moq": ["moq"]}, options={"aggregation": "sum", "valueFormat": "compact", "barOrientation": "horizontal", "topN": 15}),
    _unit("stock-boundary-table", "库存/补货", "table", "补货策略核查", "核查库存上下限、可售库存、日均销售和起订量，适合补货前复核。", ["wsgjp-replenishment"], {}, {"sku": ["sku"], "product": ["product"], "stock": ["available_stock", "stock_qty"], "min": ["min_stock"], "max": ["max_stock"], "replenishment": ["replenishment_qty"], "moq": ["moq"], "days": ["sellable_days"]}, signals=["available_stock", "replenishment_qty", "min_stock"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("country-sales-mix", "跨境/店铺", "pie", "国家/站点销售构成", "跨境经营先看国家、站点或币种结构，避免只看合计。", ["sellfox-business-dashboard", "jijia-instant-dashboard"], {"measure": ["paid_amount", "sales_amount"], "dimension": ["country", "currency"]}, options={"aggregation": "sum", "valueFormat": "currency", "pieShape": "donut", "showDataLabel": True, "topN": 10}),
    _unit("store-country-sales-rank", "跨境/店铺", "bar", "店铺/国家销售排行", "把店铺和站点作为经营入口，适合多店铺复盘。", ["sellfox-business-dashboard", "jijia-instant-dashboard", "wanliniu-bi-review"], {"measure": ["paid_amount", "sales_amount"], "dimension": ["store", "country", "platform"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "rankingMode": "ranked", "topN": 15}),
    _unit("avg-price-kpi", "跨境/店铺", "metric", "平均售价", "即时看板常用来解释销量变化背后的价格变化。", ["jijia-instant-dashboard", "sellfox-business-dashboard"], {"measure": ["average_price"]}, options={"aggregation": "avg", "valueFormat": "currency"}),
    _unit("avg-price-trend", "跨境/店铺", "line", "平均售价趋势", "观察价格波动是否解释销售额或销量变化。", ["jijia-instant-dashboard"], {"measure": ["average_price"], "dimension": ["date", "outbound_date"]}, {"filter": ["store", "country"]}, options={"aggregation": "avg", "valueFormat": "currency", "areaFill": False, "topN": 24, "sortDirection": "asc"}),
    _unit("hot-product-rank", "老板视角", "bar", "热销商品排行", "老板看板先用商品销量或销售额找到主力商品。", ["guanjia-cloud-app", "wanliniu-bi-review"], {"measure": ["quantity", "paid_amount", "sales_amount"], "dimension": ["sku", "product"]}, options={"aggregation": "sum", "valueFormat": "compact", "barOrientation": "horizontal", "rankingMode": "ranked", "topN": 15}),
    _unit("boss-key-data-note", "老板视角", "text", "老板关键数据说明", "把销售、利润、库存、欠款和补货说明留在首屏，方便非专业用户读看板。", ["guanjia-cloud-app", "wanliniu-bi-review"], {}, {"sales": ["paid_amount", "sales_amount"], "profit": ["profit_amount"], "stock": ["stock_qty", "available_stock"], "ar": ["ar_amount"], "replenishment": ["replenishment_qty"]}, signals=["sales_amount", "stock_qty", "ar_amount"]),
    _unit("salesperson-performance-rank", "老板视角", "bar", "业务员业绩排行", "适合分销、批发和传统进销存场景，用于业绩和回款复盘。", ["guanjia-cloud-app", "wanliniu-bi-review"], {"measure": ["paid_amount", "sales_amount", "profit_amount"], "dimension": ["salesperson"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 12}),
    _unit("gross-margin-rate-kpi", "利润/费用", "metric", "毛利率", "利润分析需要同时看金额和比率，防止高销售额掩盖低利润。", ["sellfox-business-dashboard", "guanjia-cloud-app"], {"measure": ["gross_margin_rate"]}, options={"aggregation": "avg", "valueFormat": "percent"}),
    _unit("purchase-cost-kpi", "利润/费用", "metric", "采购成本", "跨境和进销存看板需要把采购成本从其他成本中拆出来。", ["sellfox-business-dashboard", "kingdee-purchase-execution"], {"measure": ["purchase_cost", "cost_amount"]}, options={"aggregation": "sum", "valueFormat": "currency"}),
    _unit("first-leg-cost-kpi", "利润/费用", "metric", "头程费用", "跨境店铺利润分析要单独披露头程费用，避免毛利失真。", ["sellfox-business-dashboard"], {"measure": ["first_leg_cost"]}, options={"aggregation": "sum", "valueFormat": "currency"}),
    _unit("cost-profit-waterfall-table", "利润/费用", "table", "利润费用核查", "把销售额、采购成本、头程、运费、退款和毛利放在同一张核查表。", ["sellfox-business-dashboard", "jst-sales-outbound", "wdt-stockout-detail"], {}, {"order": ["order_id"], "store": ["store"], "sales": ["paid_amount", "sales_amount"], "purchaseCost": ["purchase_cost", "cost_amount"], "firstLeg": ["first_leg_cost"], "freight": ["freight_amount"], "refund": ["refund_amount"], "profit": ["profit_amount", "gross_margin_rate"]}, signals=["sales_amount", "cost_amount", "profit_amount"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("ad-spend-kpi", "广告/投放", "metric", "广告花费", "运营分析里先看投放费用规模，再看产出和转化。", ["sellfox-business-dashboard", "jijia-instant-dashboard"], {"measure": ["ad_spend"]}, options={"aggregation": "sum", "valueFormat": "currency"}),
    _unit("ad-sales-kpi", "广告/投放", "metric", "广告销售额", "把广告归因销售额从总销售里拆出来，辅助判断投放贡献。", ["sellfox-business-dashboard"], {"measure": ["ad_sales"]}, options={"aggregation": "sum", "valueFormat": "currency"}),
    _unit("ad-roas-kpi", "广告/投放", "metric", "ROAS", "投放回报率比单看花费更适合判断效率。", ["sellfox-business-dashboard"], {"measure": ["roas"]}, options={"aggregation": "avg", "valueFormat": "compact"}),
    _unit("ad-acos-kpi", "广告/投放", "metric", "ACOS", "跨境运营常用 ACOS 判断广告成本压力。", ["sellfox-business-dashboard"], {"measure": ["acos"]}, options={"aggregation": "avg", "valueFormat": "percent"}),
    _unit("ad-performance-trend", "广告/投放", "line", "广告表现趋势", "按日期观察广告花费、广告销售额或 ROAS 的变化。", ["sellfox-business-dashboard"], {"measure": ["ad_spend", "ad_sales", "roas", "acos"], "dimension": ["date"]}, options={"aggregation": "sum", "valueFormat": "compact", "areaFill": True, "topN": 24, "sortDirection": "asc"}),
    _unit("ad-click-conversion-rank", "广告/投放", "bar", "点击转化排行", "用点击、曝光或转化率定位投放效率差异。", ["sellfox-business-dashboard"], {"measure": ["conversion_rate", "ad_clicks", "ad_impressions"], "dimension": ["sku", "product", "store", "platform"]}, options={"aggregation": "avg", "valueFormat": "compact", "barOrientation": "horizontal", "topN": 15}),
    _unit("ap-supplier-rank", "应收/对账", "bar", "供应商应付排行", "应付和供应商采购放在一起看，避免只关注销售侧。", ["wanliniu-bi-review", "kingdee-purchase-execution"], {"measure": ["ap_amount"], "dimension": ["supplier"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 12}),
    _unit("ar-aging-rank", "应收/对账", "bar", "客户应收账龄排行", "客户欠款不仅看金额，还要结合账龄或周转天数。", ["guanjia-cloud-app", "kingdee-sales-order-execution"], {"measure": ["ar_amount"], "dimension": ["customer"]}, {"age": ["age_days"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 12}),
    _unit("production-plan-kpi", "生产/制造", "metric", "计划生产数量", "生产订单执行先确认计划产量。", ["kingdee-production-execution"], {"measure": ["plan_qty"]}, {"date": ["production_date"]}, options={"aggregation": "sum", "valueFormat": "compact"}),
    _unit("production-complete-kpi", "生产/制造", "metric", "完工入库数量", "完工或入库数量是生产达成的基础读数。", ["kingdee-production-execution"], {"measure": ["complete_qty"]}, {"date": ["production_date"]}, options={"aggregation": "sum", "valueFormat": "compact"}),
    _unit("production-achievement-rank", "生产/制造", "bar", "生产达成率排行", "按产品、车间或订单看计划达成差异。", ["kingdee-production-execution"], {"measure": ["achievement_rate", "complete_qty"], "dimension": ["product", "workshop", "order_id"]}, options={"aggregation": "avg", "valueFormat": "percent", "barOrientation": "horizontal", "topN": 12}),
    _unit("workshop-production-rank", "生产/制造", "bar", "车间产出排行", "车间维度适合看制造履约和产出压力。", ["kingdee-production-execution"], {"measure": ["complete_qty", "plan_qty"], "dimension": ["workshop"]}, options={"aggregation": "sum", "valueFormat": "compact", "barOrientation": "horizontal", "topN": 12}),
    _unit("production-execution-table", "生产/制造", "table", "生产订单执行明细", "生产订单、产品、车间、计划数量、完工数量和达成率需要一张核查表。", ["kingdee-production-execution"], {}, {"order": ["order_id"], "product": ["product"], "workshop": ["workshop"], "plan": ["plan_qty"], "complete": ["complete_qty"], "rate": ["achievement_rate"], "date": ["production_date"]}, signals=["plan_qty", "complete_qty", "product"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("erp-status-slicer", "交互/证据", "slicer", "单据状态筛选", "ERP 单据常有审核、关闭、退款、执行状态，应作为全局切片器。", ["kingdee-sales-order-execution", "wdt-stockout-detail"], {"dimension": ["bill_status", "refund_status"]}, options={"aggregation": "count", "slicerMultiSelect": True, "globalFilterTarget": True, "drillDown": False}),
    _unit("erp-entity-slicer", "交互/证据", "slicer", "业务对象筛选", "按店铺、客户、供应商、仓库或平台快速缩小问题范围。", ["wdt-api-index", "kingdee-purchase-execution", "wsgjp-jxc"], {"dimension": ["store", "customer", "supplier", "warehouse", "platform"]}, options={"aggregation": "count", "slicerMultiSelect": True, "globalFilterTarget": True, "drillDown": False, "topN": 20}),
    _unit("erp-evidence-note", "交互/证据", "text", "ERP 看板口径说明", "把公开 ERP 字段来源、匹配字段和风险边界放在看板首屏。", [item["id"] for item in PUBLIC_ERP_REFERENCES], {}, {}, signals=["order_id", "sku", "paid_amount", "stock_qty", "supplier", "ar_amount"], options={"crossFilter": False, "drillDown": False}),
]

ERP_DASHBOARD_UNITS.extend([
    _unit("sales-execution-chain-table", "销售执行/回款", "table", "销售订单执行链路", "把订单、发货、出库、退货、应收、开票、收款放在同一张链路核查表。", ["kingdee-sales-order-execution"], {}, {"order": ["order_id"], "product": ["sku", "product"], "ordered": ["ordered_qty", "quantity"], "delivery": ["delivery_qty"], "outbound": ["outbound_qty", "outbound_amount"], "return": ["return_qty", "return_amount"], "ar": ["ar_amount"], "invoice": ["invoice_amount"], "settlement": ["settlement_amount"], "receipt": ["receipt_amount"]}, signals=["order_id", "outbound_qty", "ar_amount", "invoice_amount"], options={"aggregation": "count", "tableColumnLimit": 10, "topN": 100}),
    _unit("sales-unfulfilled-rank", "销售执行/回款", "bar", "未执行订单排行", "销售执行表里未发货、未出库或欠交数量最容易形成交付风险。", ["kingdee-sales-order-execution", "digiwin-manufacturing-modules"], {"measure": ["unfulfilled_qty", "fulfillment_gap_amount"], "dimension": ["customer", "product", "order_id"]}, {"status": ["close_status", "line_status"]}, options={"aggregation": "sum", "valueFormat": "compact", "barOrientation": "horizontal", "topN": 15}),
    _unit("delivery-outbound-gap-table", "销售执行/回款", "table", "发货出库差异明细", "发货通知和实际出库不一致时，先保留订单、物料、数量和状态证据。", ["kingdee-sales-order-execution"], {}, {"order": ["order_id"], "sku": ["sku"], "product": ["product"], "delivery": ["delivery_qty", "delivery_amount"], "outbound": ["outbound_qty", "outbound_amount"], "status": ["bill_status", "line_status", "close_status"], "date": ["date", "outbound_date"]}, signals=["delivery_qty", "outbound_qty", "order_id"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("return-execution-rank", "销售执行/回款", "bar", "销售退货排行", "把销售退货数量或金额按客户、商品、订单拆开，便于定位履约或质量问题。", ["kingdee-sales-order-execution", "jst-refund"], {"measure": ["return_amount", "return_qty", "refund_amount"], "dimension": ["customer", "sku", "product", "order_id"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 15}),
    _unit("settlement-receipt-kpi", "销售执行/回款", "metric", "已结算/已回款金额", "应收链路里收款和核销后的结算金额比订单金额更接近财务确认口径。", ["kingdee-sales-order-execution", "lingxing-erp-value", "sellfox-ar-report"], {"measure": ["settlement_amount", "receipt_amount", "platform_income"]}, {"date": ["settlement_date", "date"]}, options={"aggregation": "sum", "valueFormat": "currency"}),
    _unit("prepayment-writeoff-table", "销售执行/回款", "table", "预收与冲销核查", "预收、特殊冲销和已结算金额需要单独披露，避免回款解释混乱。", ["kingdee-sales-order-execution"], {}, {"order": ["order_id"], "customer": ["customer"], "prepay": ["prepayment_amount"], "writeoff": ["writeoff_amount"], "settlement": ["settlement_amount"], "receipt": ["receipt_amount"], "status": ["settlement_status", "bill_status"]}, signals=["prepayment_amount", "writeoff_amount", "settlement_amount"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("settlement-status-slicer", "销售执行/回款", "slicer", "结算状态筛选", "把已结算、未结算、转账中、长期未转账等状态做成全局入口。", ["lingxing-erp-value", "sellfox-ar-report"], {"dimension": ["settlement_status", "transfer_status"]}, options={"aggregation": "count", "slicerMultiSelect": True, "globalFilterTarget": True, "drillDown": False, "topN": 20}),
    _unit("customer-receipt-risk-rank", "销售执行/回款", "bar", "客户回款风险排行", "按客户聚合未结算、未收款或账龄字段，给销售和财务共同处理。", ["kingdee-sales-order-execution", "sellfox-ar-report"], {"measure": ["ar_amount", "unfulfilled_qty", "age_days"], "dimension": ["customer"]}, {"status": ["settlement_status"], "receipt": ["receipt_amount"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 12}),
    _unit("purchase-execution-chain-table", "采购执行/应付", "table", "采购订单执行链路", "采购从订单、收料、入库、退料、应付、开票、付款到特殊冲销需要同屏核查。", ["kingdee-purchase-execution"], {}, {"po": ["purchase_order_id", "order_id"], "supplier": ["supplier"], "sku": ["sku", "product"], "ordered": ["ordered_qty", "quantity"], "received": ["received_qty", "received_amount"], "stockin": ["stockin_qty", "stockin_amount"], "return": ["material_return_qty", "material_return_amount"], "ap": ["ap_amount"], "invoice": ["invoice_amount"], "payment": ["payment_amount"]}, signals=["supplier", "received_qty", "stockin_qty", "ap_amount"], options={"aggregation": "count", "tableColumnLimit": 10, "topN": 100}),
    _unit("purchase-stockin-progress-rank", "采购执行/应付", "bar", "供应商入库进度排行", "用收料或入库数量观察供应商交付，适合采购跟催。", ["kingdee-purchase-execution", "kingdee-purchase-stockin"], {"measure": ["stockin_qty", "received_qty"], "dimension": ["supplier", "purchaser"]}, {"date": ["purchase_date"]}, options={"aggregation": "sum", "valueFormat": "compact", "barOrientation": "horizontal", "topN": 15}),
    _unit("purchase-return-material-rank", "采购执行/应付", "bar", "采购退料排行", "退料数量或金额能暴露供应商质量、规格和到货异常。", ["kingdee-purchase-execution"], {"measure": ["material_return_amount", "material_return_qty", "defective_qty"], "dimension": ["supplier", "sku", "product"]}, anchors=["supplier", "purchase_order_id", "purchaser", "purchase_date", "received_qty", "stockin_qty"], options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 15}),
    _unit("payable-payment-kpi", "采购执行/应付", "metric", "已付/应付金额", "采购财务链路先看应付、付款和预付款规模。", ["kingdee-purchase-execution", "wsgjp-webstore-erp"], {"measure": ["payment_amount", "ap_amount", "prepaid_amount"]}, {"date": ["purchase_date"]}, options={"aggregation": "sum", "valueFormat": "currency"}),
    _unit("purchase-payment-reconcile-table", "采购执行/应付", "table", "应付付款勾稽明细", "把应付单、发票、付款、预付和特殊冲销放在采购订单下核对。", ["kingdee-purchase-execution"], {}, {"po": ["purchase_order_id", "order_id"], "supplier": ["supplier"], "ap": ["ap_amount"], "invoice": ["invoice_amount"], "payment": ["payment_amount"], "prepaid": ["prepaid_amount"], "writeoff": ["special_writeoff_amount", "writeoff_amount"], "status": ["bill_status", "settlement_status"]}, signals=["ap_amount", "payment_amount", "supplier"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("purchaser-performance-rank", "采购执行/应付", "bar", "采购员执行排行", "按采购员看采购金额、入库数量或延期，帮助采购负责人分配跟催。", ["kingdee-purchase-execution"], {"measure": ["purchase_amount", "stockin_qty", "delay_days"], "dimension": ["purchaser"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 12}),
    _unit("purchase-status-slicer", "采购执行/应付", "slicer", "采购状态筛选", "采购执行需要按未完成、已完成、关闭、未审核等状态快速筛选。", ["kingdee-purchase-execution"], {"dimension": ["line_status", "bill_status", "close_status"], "scope": ["supplier", "purchase_order_id", "purchaser"]}, options={"aggregation": "count", "slicerMultiSelect": True, "globalFilterTarget": True, "drillDown": False}),
    _unit("purchase-price-rank", "采购执行/应付", "bar", "采购单价排行", "价格异常常发生在供应商、物料或采购员维度，先用单价/采购成本排行。", ["kingdee-purchase-order", "mabang-cost-update"], {"measure": ["average_price", "purchase_cost", "purchase_amount"], "dimension": ["supplier", "sku", "product"]}, options={"aggregation": "avg", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 15}),
    _unit("kitting-ready-kpi", "生产齐套/车间", "metric", "齐套可投产数量", "生产启动前优先确认预计齐套或库存齐套数量。", ["kingdee-production-kitting", "yonsuite-material-kitting"], {"measure": ["expected_kit_qty", "inventory_kit_qty"]}, {"date": ["production_date"]}, options={"aggregation": "sum", "valueFormat": "compact"}),
    _unit("material-shortage-rank", "生产齐套/车间", "bar", "欠料风险排行", "以生产订单、产品或子项材料定位缺料风险，减少人工逐张工单排查。", ["kingdee-production-kitting", "yonsuite-material-kitting"], {"measure": ["shortage_qty", "unfulfilled_qty"], "dimension": ["production_order_id", "product", "bom_material"]}, {"priority": ["schedule_priority"]}, options={"aggregation": "sum", "valueFormat": "compact", "barOrientation": "horizontal", "topN": 15}),
    _unit("prepared-vs-plan-table", "生产齐套/车间", "table", "备料与计划核查", "把计划数量、已备料、分析数量和齐套数量放在一起，判断能否开工。", ["kingdee-production-kitting"], {}, {"order": ["production_order_id", "order_id"], "product": ["product"], "plan": ["plan_qty"], "prepared": ["prepared_qty"], "analysis": ["analysis_qty"], "expected": ["expected_kit_qty"], "inventory": ["inventory_kit_qty"], "start": ["production_date"]}, signals=["production_order_id", "prepared_qty", "expected_kit_qty"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("material-issue-table", "生产齐套/车间", "table", "领料发料明细", "子项材料的应发、已领、可领、超发是齐套分析和车间领料的关键证据。", ["kingdee-production-kitting", "digiwin-manufacturing-modules"], {}, {"order": ["production_order_id"], "material": ["bom_material", "sku"], "required": ["plan_qty", "analysis_qty"], "issued": ["issued_qty"], "issuable": ["issuable_qty"], "over": ["overissued_qty"], "shortage": ["shortage_qty"]}, signals=["bom_material", "issued_qty", "issuable_qty"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("overissued-material-rank", "生产齐套/车间", "bar", "超发材料排行", "超发会影响库存准确性和成本核算，先按材料或工单排行。", ["kingdee-production-kitting"], {"measure": ["overissued_qty"], "dimension": ["bom_material", "production_order_id", "workshop"]}, options={"aggregation": "sum", "valueFormat": "compact", "barOrientation": "horizontal", "topN": 15}),
    _unit("workshop-quality-rank", "生产齐套/车间", "bar", "车间质量排行", "把合格率、报废、返工和不良按车间或工序拆开。", ["digiwin-manufacturing-modules", "kingdee-production-execution"], {"measure": ["quality_pass_rate", "scrap_qty", "rework_qty", "defective_qty"], "dimension": ["workshop", "process"]}, options={"aggregation": "avg", "valueFormat": "percent", "barOrientation": "horizontal", "topN": 12}),
    _unit("production-on-time-rank", "生产齐套/车间", "bar", "准时交付排行", "制造看板应把订单准时交付率或延期按产品、车间和客户展示。", ["digiwin-manufacturing-modules", "yonsuite-material-kitting"], {"measure": ["on_time_delivery_rate", "delay_days"], "dimension": ["workshop", "product", "customer"]}, options={"aggregation": "avg", "valueFormat": "percent", "barOrientation": "horizontal", "topN": 12}),
    _unit("machine-status-slicer", "生产齐套/车间", "slicer", "设备状态筛选", "设备状态和排程优先级会影响工单能否按时完成，应作为制造看板切片器。", ["digiwin-manufacturing-modules"], {"dimension": ["equipment_status", "machine", "schedule_priority"]}, options={"aggregation": "count", "slicerMultiSelect": True, "globalFilterTarget": True, "drillDown": False}),
    _unit("inventory-cost-method-slicer", "库存成本/批次", "slicer", "成本算法筛选", "全仓成本、移动加权、个别计价等算法会改变库存金额解读。", ["wsgjp-stock-status-help"], {"dimension": ["cost_method"]}, options={"aggregation": "count", "slicerMultiSelect": True, "globalFilterTarget": True, "drillDown": False}),
    _unit("estimated-stock-amount-kpi", "库存成本/批次", "metric", "预估库存金额", "网上管家婆类库存状况表常用库存数量乘预估成本均价来估算库存资金。", ["wsgjp-stock-status-help"], {"measure": ["estimated_stock_amount", "stock_amount"]}, options={"aggregation": "sum", "valueFormat": "currency"}),
    _unit("reference-margin-rate-kpi", "库存成本/批次", "metric", "参考毛利率", "用参考销售总价和预估库存金额解释库存商品的潜在毛利。", ["wsgjp-stock-status-help"], {"measure": ["reference_margin_rate", "gross_margin_rate"]}, options={"aggregation": "avg", "valueFormat": "percent"}),
    _unit("cost-anomaly-table", "库存成本/批次", "table", "入库成本异常明细", "销售退货、换货、报溢等非指定成本入库容易按 0 成本入库，需要可追溯明细。", ["wsgjp-stock-status-help"], {}, {"sku": ["sku"], "product": ["product"], "warehouse": ["warehouse"], "cost": ["estimated_unit_cost", "reference_cost", "cost_amount"], "flag": ["cost_anomaly_flag"], "stock": ["stock_qty"], "date": ["purchase_date", "date"]}, signals=["cost_anomaly_flag", "estimated_unit_cost", "sku"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("batch-expiry-risk-table", "库存成本/批次", "table", "批次效期风险明细", "食品、母婴、医药和快消库存需要批次、生产日期、到期日期和剩余效期。", ["wsgjp-stock-status-help", "guanjia-cloud-app"], {}, {"sku": ["sku"], "product": ["product"], "batch": ["batch_no"], "stock": ["stock_qty"], "production": ["production_date"], "expiry": ["expiry_date", "shelf_life"], "remaining": ["remaining_shelf_life"], "warehouse": ["warehouse"]}, signals=["batch_no", "expiry_date", "stock_qty"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("serial-stock-kpi", "库存成本/批次", "metric", "序列号库存", "一品一码或高价值商品需要单独确认序列号库存规模。", ["wsgjp-stock-status-help"], {"measure": ["serial_stock_qty"]}, options={"aggregation": "sum", "valueFormat": "compact"}),
    _unit("package-stock-kpi", "库存成本/批次", "metric", "套餐/组合装库存", "组合装商品和套装库存不能简单等同单品库存。", ["wsgjp-stock-status-help", "jst-sales-outbound"], {"measure": ["package_stock_qty"]}, options={"aggregation": "sum", "valueFormat": "compact"}),
    _unit("stockout-risk-rank", "库存成本/批次", "bar", "断货风险排行", "结合可售天数、断货风险、库存下限和日均销量，给补货动作排序。", ["wsgjp-replenishment", "lingxing-erp-value"], {"measure": ["stockout_risk", "sellable_days", "daily_sales"], "dimension": ["sku", "product", "warehouse"]}, options={"aggregation": "avg", "valueFormat": "compact", "barOrientation": "horizontal", "topN": 15}),
    _unit("daily-sales-supply-table", "库存成本/批次", "table", "日均销量与可售天数", "补货前把日均销量、计划销售天数、可售库存和建议补货量放一起复核。", ["wsgjp-replenishment"], {}, {"sku": ["sku"], "product": ["product"], "daily": ["daily_sales"], "days": ["sellable_days", "planned_sales_days"], "stock": ["available_stock", "stock_qty"], "replenishment": ["replenishment_qty"], "moq": ["moq"]}, signals=["daily_sales", "sellable_days", "replenishment_qty"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("platform-income-expense-table", "跨境财务/平台", "table", "平台收入支出税费核对", "领星利润报表建议按平台收入、支出、税费总额核对，而不是只盯单字段。", ["lingxing-profit-report", "sellfox-report-center"], {}, {"store": ["store"], "period": ["report_period", "date"], "income": ["platform_income"], "expense": ["platform_expense"], "tax": ["platform_tax"], "summary": ["summary_statement_amount"], "transaction": ["transaction_amount"], "currency": ["currency"]}, signals=["platform_income", "platform_expense", "platform_tax"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("platform-tax-kpi", "跨境财务/平台", "metric", "平台税费", "市场税、销售税及其退款会影响含税毛利，需要单独成为指标。", ["lingxing-profit-report"], {"measure": ["platform_tax", "marketplace_tax", "sales_tax"]}, options={"aggregation": "sum", "valueFormat": "currency"}),
    _unit("tax-refund-table", "跨境财务/平台", "table", "税费退款影响明细", "含税毛利需要把销售税退款额、市场税退款额和混合网络费纳入解释。", ["lingxing-profit-report"], {}, {"store": ["store"], "sku": ["sku", "asin", "msku"], "salesTax": ["sales_tax"], "salesTaxRefund": ["sales_tax_refund"], "marketTax": ["marketplace_tax"], "marketTaxRefund": ["marketplace_tax_refund"], "networkFee": ["mixed_network_fee"], "profit": ["profit_amount"]}, signals=["sales_tax", "marketplace_tax", "mixed_network_fee"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("delayed-settlement-table", "跨境财务/平台", "table", "延迟结算订单明细", "跨境平台存在延迟结算，订单利润和回款时间要分开看。", ["lingxing-erp-value", "sellfox-ar-report"], {}, {"order": ["order_id"], "store": ["store"], "sku": ["sku", "asin", "msku"], "amount": ["paid_amount", "platform_income"], "settlement": ["settlement_status"], "expected": ["expected_payment_date"], "date": ["settlement_date", "date"]}, signals=["settlement_status", "expected_payment_date", "order_id"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("storage-fee-kpi", "跨境财务/平台", "metric", "仓储费用", "月仓储费和长期仓储费经常解释库存利润差异。", ["sellfox-report-center", "lingxing-erp-value"], {"measure": ["storage_fee", "long_term_storage_fee"]}, options={"aggregation": "sum", "valueFormat": "currency"}),
    _unit("storage-fee-rank", "跨境财务/平台", "bar", "SKU 仓储费排行", "按 SKU、ASIN 或店铺定位仓储费压力。", ["sellfox-report-center", "lingxing-erp-value"], {"measure": ["storage_fee", "long_term_storage_fee"], "dimension": ["sku", "asin", "store"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 15}),
    _unit("reimbursement-kpi", "跨境财务/平台", "metric", "平台赔偿金额", "赔偿金额会影响利润核对和库存差异解释。", ["sellfox-report-center", "lingxing-erp-value"], {"measure": ["reimbursement_amount"]}, options={"aggregation": "sum", "valueFormat": "currency"}),
    _unit("inventory-adjustment-loss-rank", "跨境财务/平台", "bar", "库存调整/货损排行", "库存调整、移除和货损应单独从利润里拆出来。", ["lingxing-erp-value", "sellfox-report-center"], {"measure": ["inventory_adjustment_amount", "removal_fee"], "dimension": ["sku", "asin", "warehouse", "store"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 15}),
    _unit("listing-profit-rank", "跨境财务/平台", "bar", "Listing 利润排行", "跨境利润分析常按父 ASIN、子 ASIN、MSKU 和 Listing 下钻。", ["jijia-sales-profit-analysis", "lingxing-erp-value"], {"measure": ["profit_amount", "sales_amount"], "dimension": ["parent_asin", "asin", "msku", "listing"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 15}),
    _unit("asin-ad-efficiency-table", "跨境财务/平台", "table", "ASIN 广告效率明细", "把广告花费、销售额、ACOS、ROAS、点击曝光和 Listing 放在同一张表里。", ["sellfox-business-dashboard", "jijia-sales-profit-analysis"], {}, {"asin": ["asin", "msku", "listing"], "store": ["store"], "spend": ["ad_spend"], "adSales": ["ad_sales"], "acos": ["acos"], "roas": ["roas"], "clicks": ["ad_clicks"], "impressions": ["ad_impressions"], "cvr": ["conversion_rate"]}, signals=["asin", "ad_spend", "acos"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("return-reason-rank", "售后质量/服务", "bar", "退货原因排行", "退货原因比退款金额更能指导商品质量、页面描述和物流改进。", ["jst-refund", "wdt-module-overview", "wanliniu-open-order-stock"], {"measure": ["refund_amount", "return_qty", "order_count"], "dimension": ["return_reason", "after_sales_type"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 15}),
    _unit("after-sales-type-slicer", "售后质量/服务", "slicer", "售后类型筛选", "退货、退款、换货、补发等售后类型需要作为跨组件筛选入口。", ["jst-refund", "wanliniu-open-order-stock"], {"dimension": ["after_sales_type", "refund_status"]}, options={"aggregation": "count", "slicerMultiSelect": True, "globalFilterTarget": True, "drillDown": False}),
    _unit("after-sales-quality-table", "售后质量/服务", "table", "售后质量核查", "售后单要带订单、SKU、原因、状态、退款、换货和入库回传字段。", ["jst-refund", "wanliniu-open-order-stock"], {}, {"order": ["order_id"], "sku": ["sku"], "product": ["product"], "type": ["after_sales_type"], "reason": ["return_reason"], "refund": ["refund_amount"], "exchange": ["exchange_amount"], "status": ["refund_status"], "stockin": ["stockin_qty"]}, signals=["after_sales_type", "return_reason", "refund_amount"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("exchange-amount-kpi", "售后质量/服务", "metric", "换货金额", "换货金额会影响实退金额和售后责任判断。", ["jst-refund"], {"measure": ["exchange_amount"]}, options={"aggregation": "sum", "valueFormat": "currency"}),
    _unit("complaint-rank", "售后质量/服务", "bar", "客诉排行", "按商品、店铺、客户或原因聚合客诉数量，辅助服务改进。", ["wdt-module-overview", "guanjia-cloud-app"], {"measure": ["customer_complaint_count"], "dimension": ["sku", "product", "store", "customer", "return_reason"]}, options={"aggregation": "sum", "valueFormat": "compact", "barOrientation": "horizontal", "topN": 15}),
    _unit("review-score-kpi", "售后质量/服务", "metric", "评价分", "评价分适合和退款、客诉、退货原因一起解释售后质量。", ["wdt-module-overview"], {"measure": ["review_score"]}, options={"aggregation": "avg", "valueFormat": "compact"}),
    _unit("distributor-sales-rank", "分销/门店/会员", "bar", "分销商销售排行", "分销商、经销商或供销平台需要独立看销售贡献和回款风险。", ["jst-saas-erp-service", "wsgjp-webstore-erp"], {"measure": ["paid_amount", "sales_amount", "ar_amount"], "dimension": ["distributor"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 15}),
    _unit("member-level-sales-mix", "分销/门店/会员", "pie", "会员等级销售构成", "零售和门店场景需要按会员等级看消费结构。", ["guanjia-cloud-app"], {"measure": ["paid_amount", "sales_amount", "order_count"], "dimension": ["member_level"]}, options={"aggregation": "sum", "valueFormat": "currency", "pieShape": "donut", "showDataLabel": True, "topN": 8}),
    _unit("region-sales-rank", "分销/门店/会员", "bar", "区域销售排行", "按省市或国家地区看销售贡献，适合全渠道和跨境复盘。", ["jst-sales-outbound", "guanjia-cloud-app"], {"measure": ["paid_amount", "sales_amount"], "dimension": ["province", "city", "country"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 15}),
    _unit("visit-route-table", "分销/门店/会员", "table", "巡店拜访明细", "门店或渠道业务需要把客户、路线、拜访次数和销售结果关联起来。", ["guanjia-cloud-app"], {}, {"customer": ["customer"], "salesperson": ["salesperson"], "route": ["route"], "visits": ["visit_count"], "sales": ["paid_amount", "sales_amount"], "ar": ["ar_amount"], "date": ["date"]}, signals=["visit_count", "route", "customer"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("vip-ar-risk-table", "分销/门店/会员", "table", "重点客户欠款明细", "重点客户的应收和回款需要比普通客户更容易被看见。", ["guanjia-cloud-app", "kingdee-sales-order-execution"], {}, {"customer": ["customer", "vip_customer"], "level": ["member_level"], "sales": ["paid_amount", "sales_amount"], "ar": ["ar_amount"], "age": ["age_days"], "receipt": ["receipt_amount"], "salesperson": ["salesperson"]}, signals=["vip_customer", "ar_amount", "customer"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("logistics-weight-gap-table", "出库/物流", "table", "预估实称重量核查", "预估重量和实称重量差异常常解释运费差异。", ["jst-sales-outbound", "jst-shengtu-logistics-report"], {}, {"order": ["order_id"], "tracking": ["tracking_no"], "company": ["logistics_company"], "warehouse": ["warehouse"], "weight": ["weight"], "actual": ["actual_weight"], "freight": ["freight_amount", "freight_gap"], "package": ["package_count"]}, signals=["weight", "actual_weight", "freight_amount"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("logistics-company-cost-rank", "出库/物流", "bar", "快递公司费用排行", "按快递公司或承运商看运费，帮助物流对账和服务商谈判。", ["jst-shengtu-logistics-report", "wdt-stockout-detail"], {"measure": ["freight_amount", "freight_gap"], "dimension": ["logistics_company"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 12}),
    _unit("report-type-slicer", "报告/数据治理", "slicer", "报告类型筛选", "报告中心的库存、销量、付款、退货、移除等报告应作为数据治理入口。", ["sellfox-report-center"], {"dimension": ["report_type"]}, options={"aggregation": "count", "slicerMultiSelect": True, "globalFilterTarget": True, "drillDown": False}),
    _unit("report-status-kpi", "报告/数据治理", "metric", "报告任务数", "定时任务、报告生成和导出状态需要可见，避免数据源过期还在分析。", ["sellfox-report-center"], {"measure": ["order_count", "quantity"], "dimension": ["report_status"]}, {"type": ["report_type"]}, options={"aggregation": "count", "valueFormat": "compact"}),
    _unit("report-freshness-table", "报告/数据治理", "table", "报告新鲜度核查", "把报告类型、期间、生成时间和状态列出，帮助 Agent 判断数据是否足够新。", ["sellfox-report-center"], {}, {"name": ["report_name"], "type": ["report_type"], "period": ["report_period"], "generated": ["report_generated_at"], "status": ["report_status"], "store": ["store"]}, signals=["report_type", "report_generated_at", "report_status"], options={"aggregation": "count", "tableColumnLimit": 8, "topN": 100}),
])

ERP_DASHBOARD_UNITS.extend([
    _unit("store-pos-sales-rank", "零售门店/POS", "bar", "门店 POS 销售排行", "连锁门店先按门店、收银终端或导购看销售贡献。", ["guanjia-cloud-app", "kingdee-jxc-modern-cases", "chanjet-tcloud-connector"], {"measure": ["paid_amount", "sales_amount"], "dimension": ["store", "terminal", "shop_guide"]}, {"payment": ["payment_method"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 15}),
    _unit("cashier-performance-rank", "零售门店/POS", "bar", "收银员业绩排行", "收银员、导购和 POS 终端维度能解释门店执行差异。", ["guanjia-cloud-app"], {"measure": ["paid_amount", "sales_amount", "order_count"], "dimension": ["cashier", "shop_guide", "terminal"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 12}),
    _unit("payment-method-mix", "零售门店/POS", "pie", "支付方式构成", "现金、刷卡、微信、支付宝或平台支付的构成会影响对账入口。", ["guanjia-cloud-app", "chanjet-tcloud-connector"], {"measure": ["paid_amount", "sales_amount"], "dimension": ["payment_method"]}, options={"aggregation": "sum", "valueFormat": "currency", "pieShape": "donut", "showDataLabel": True, "topN": 8}),
    _unit("promotion-discount-table", "零售门店/POS", "table", "促销折扣核查", "促销、优惠券、折扣和实付金额需要放在一张明细里，避免把营销效果误当销售增长。", ["kingdee-jxc-modern-cases", "guanjia-cloud-app"], {}, {"order": ["order_id"], "store": ["store"], "member": ["member_id", "member_level"], "sales": ["sales_amount"], "discount": ["discount_amount"], "promotion": ["promotion_amount"], "coupon": ["coupon_amount"], "paid": ["paid_amount"]}, signals=["discount_amount", "paid_amount", "store"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("member-value-table", "零售门店/POS", "table", "会员消费核查", "会员编号、等级、积分、门店和实付金额同屏，适合会员经营复盘。", ["guanjia-cloud-app", "kingdee-jxc-modern-cases"], {}, {"member": ["member_id"], "level": ["member_level"], "points": ["member_points"], "store": ["store"], "sales": ["paid_amount", "sales_amount"], "orders": ["order_count"], "guide": ["shop_guide"]}, signals=["member_id", "member_level", "paid_amount"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("style-color-size-stock-table", "服装/属性矩阵", "table", "款色码库存矩阵", "服装鞋帽要把款式、颜色、尺码、条码、库存和可售量组合成核查入口。", ["wsgjp-industry-config", "mxyun-apparel-jxc", "yonsuite-apparel-color-size"], {}, {"style": ["style"], "color": ["color"], "size": ["size"], "sku": ["sku"], "barcode": ["barcode"], "stock": ["stock_qty", "available_stock"], "warehouse": ["warehouse"]}, signals=["style", "color", "size"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("variant-stock-rank", "服装/属性矩阵", "bar", "款色码库存排行", "按款式、颜色或尺码查看库存集中度，避免单品合计掩盖断码。", ["wsgjp-industry-config", "mxyun-apparel-jxc"], {"measure": ["stock_qty", "available_stock"], "dimension": ["style", "color", "size"]}, options={"aggregation": "sum", "valueFormat": "compact", "barOrientation": "horizontal", "topN": 15}),
    _unit("style-sales-rank", "服装/属性矩阵", "bar", "款式销售排行", "服装类商品先看款式贡献，再下钻颜色尺码。", ["mxyun-apparel-jxc", "yonsuite-apparel-color-size"], {"measure": ["paid_amount", "sales_amount", "quantity"], "dimension": ["style"]}, {"color": ["color"], "size": ["size"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 15}),
    _unit("barcode-trace-table", "服装/属性矩阵", "table", "条码商品追踪", "条码、SKU、款色码和仓库要能快速回查到库存、出入库和销售。", ["wsgjp-industry-config", "mxyun-apparel-jxc"], {}, {"barcode": ["barcode"], "sku": ["sku"], "product": ["product"], "style": ["style"], "color": ["color"], "size": ["size"], "stock": ["stock_qty"], "sales": ["sales_amount", "quantity"]}, signals=["barcode", "sku", "stock_qty"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("near-expiry-kpi", "批次效期/冷链", "metric", "近效期库存", "食品、母婴和医药库存要把近效期或剩余效期提前暴露。", ["wsgjp-industry-config", "jiandaoyun-pharma-expiry", "wsgjp-food-manufacturing-case"], {"measure": ["remaining_shelf_life", "stock_qty"], "dimension": ["near_expiry_flag"]}, options={"aggregation": "count", "valueFormat": "compact"}),
    _unit("expiry-days-rank", "批次效期/冷链", "bar", "临期批次排行", "按商品、批次或仓库查看剩余效期，支持先进先出和促销清库。", ["wsgjp-industry-config", "jiandaoyun-pharma-expiry"], {"measure": ["remaining_shelf_life", "stock_qty"], "dimension": ["sku", "product", "batch_no", "warehouse"]}, options={"aggregation": "avg", "valueFormat": "compact", "barOrientation": "horizontal", "topN": 15}),
    _unit("fifo-batch-table", "批次效期/冷链", "table", "FIFO 批次出库核查", "先进先出、近期先出和批次出库顺序必须和库存效期一起看。", ["wsgjp-industry-config", "jiandaoyun-pharma-expiry"], {}, {"sku": ["sku"], "batch": ["batch_no"], "fifo": ["fifo_batch_order"], "production": ["production_date"], "expiry": ["expiry_date"], "stock": ["stock_qty"], "outbound": ["outbound_qty"], "warehouse": ["warehouse"]}, signals=["batch_no", "fifo_batch_order", "expiry_date"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("cold-chain-environment-table", "批次效期/冷链", "table", "冷链环境核查", "冷链药品、食品和美妆需要温湿度、批次、仓库和效期证据。", ["jiandaoyun-pharma-expiry", "kingdee-jxc-modern-cases"], {}, {"sku": ["sku"], "batch": ["batch_no"], "warehouse": ["warehouse"], "temperature": ["temperature"], "humidity": ["humidity"], "coldChain": ["cold_chain_flag"], "expiry": ["expiry_date"], "inspection": ["inspection_report"]}, signals=["temperature", "humidity", "batch_no"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("inspection-report-table", "批次效期/冷链", "table", "质检报告核查", "批次、质检报告、检验结果和库存批次应关联，方便质量追溯。", ["jiandaoyun-pharma-expiry", "digiwin-manufacturing-modules"], {}, {"batch": ["batch_no"], "sku": ["sku"], "report": ["inspection_report"], "result": ["inspection_result"], "good": ["good_qty"], "bad": ["bad_qty", "defective_qty"], "expiry": ["expiry_date"]}, signals=["inspection_report", "inspection_result", "batch_no"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("bin-location-stock-rank", "仓储/WMS", "bar", "库位库存排行", "仓储场景需要按库位、货主或仓库看库存分布和拣货压力。", ["guanyiyun-wms-case", "wsgjp-industry-config"], {"measure": ["stock_qty", "available_stock"], "dimension": ["bin_location", "warehouse", "owner"]}, options={"aggregation": "sum", "valueFormat": "compact", "barOrientation": "horizontal", "topN": 15}),
    _unit("inventory-count-diff-table", "仓储/WMS", "table", "盘点差异明细", "盘点数量、账面库存、盘盈盘亏和差异数量要同屏追踪。", ["guanyiyun-wms-case", "kingdee-jxc-modern-cases"], {}, {"sku": ["sku"], "product": ["product"], "warehouse": ["warehouse"], "location": ["bin_location"], "book": ["stock_qty"], "count": ["inventory_count_qty"], "gain": ["inventory_gain_qty"], "loss": ["inventory_loss_qty"], "diff": ["stock_diff_qty"]}, signals=["inventory_count_qty", "stock_diff_qty", "warehouse"], options={"aggregation": "count", "tableColumnLimit": 10, "topN": 100}),
    _unit("stock-transfer-rank", "仓储/WMS", "bar", "调拨数量排行", "多仓协同下，调拨数量能解释缺货、跨店补货和区域库存不均。", ["kingdee-jxc-modern-cases", "chanjet-tcloud-connector"], {"measure": ["stock_transfer_qty"], "dimension": ["warehouse", "store", "province", "city"]}, options={"aggregation": "sum", "valueFormat": "compact", "barOrientation": "horizontal", "topN": 15}),
    _unit("owner-stock-table", "仓储/WMS", "table", "多货主库存核查", "多货主、多仓和库位需要避免库存混用，先保留货主级证据。", ["guanyiyun-wms-case"], {}, {"owner": ["owner"], "warehouse": ["warehouse"], "location": ["bin_location"], "sku": ["sku"], "product": ["product"], "stock": ["stock_qty"], "available": ["available_stock"], "locked": ["locked_stock"]}, signals=["owner", "warehouse", "stock_qty"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("inventory-turnover-rate-kpi", "仓储/WMS", "metric", "库存周转率", "库存周转率是进销存升级后最常用的库存健康指标。", ["kingdee-jxc-modern-cases", "yonyou-u8-inventory-report"], {"measure": ["inventory_turnover_rate"]}, options={"aggregation": "avg", "valueFormat": "percent"}),
    _unit("slow-moving-stock-rank", "仓储/WMS", "bar", "呆滞库存排行", "库存健康诊断需要按商品、仓库或库位定位滞销和慢动销。", ["kingdee-jxc-modern-cases"], {"measure": ["stock_amount", "stock_qty", "age_days"], "dimension": ["sku", "product", "warehouse", "bin_location"]}, {"flag": ["slow_moving_flag"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 15}),
    _unit("demand-forecast-kpi", "预测/智能补货", "metric", "预测需求", "AI 预测和动态补货场景先展示预测需求或预测销量。", ["kingdee-jxc-modern-cases", "wsgjp-replenishment"], {"measure": ["forecast_qty"]}, options={"aggregation": "sum", "valueFormat": "compact"}),
    _unit("forecast-vs-sales-table", "预测/智能补货", "table", "预测与实销核查", "预测需求、实际销量、日均销量和建议采购量需要一起复盘。", ["kingdee-jxc-modern-cases", "wsgjp-replenishment"], {}, {"sku": ["sku"], "product": ["product"], "forecast": ["forecast_qty"], "sales": ["sales_volume", "quantity"], "daily": ["daily_sales"], "stock": ["available_stock", "stock_qty"], "recommended": ["recommended_purchase_qty", "replenishment_qty"]}, signals=["forecast_qty", "sales_volume", "recommended_purchase_qty"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("recommended-purchase-rank", "预测/智能补货", "bar", "推荐采购排行", "动态补货应按推荐采购量、可售库存和起订量排序，而不是人工翻表。", ["kingdee-jxc-modern-cases", "wsgjp-replenishment"], {"measure": ["recommended_purchase_qty", "replenishment_qty"], "dimension": ["sku", "product", "supplier", "warehouse"]}, {"moq": ["moq"], "forecast": ["forecast_qty"]}, options={"aggregation": "sum", "valueFormat": "compact", "barOrientation": "horizontal", "topN": 15}),
    _unit("estimated-profit-kpi", "跨境利润核算", "metric", "预估利润", "跨境 ERP 要把订单利润先从销售额里拆出来。", ["dianxiaomi-amazon-profit", "dianxiaomi-estimated-profit"], {"measure": ["estimated_profit", "profit_amount"]}, options={"aggregation": "sum", "valueFormat": "currency"}),
    _unit("sku-estimated-profit-rank", "跨境利润核算", "bar", "SKU 预估利润排行", "店小秘类利润核算常按 SKU、订单+SKU、库存 SKU 查赚钱对象。", ["dianxiaomi-amazon-profit", "dianxiaomi-estimated-profit"], {"measure": ["estimated_profit", "profit_amount"], "dimension": ["sku", "msku", "asin", "product"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 15}),
    _unit("platform-fee-cost-table", "跨境利润核算", "table", "平台费用核算明细", "订单金额、平台佣金、FBA、广告、退货、仓储和采购成本要合并解释利润。", ["dianxiaomi-amazon-profit", "dianxiaomi-estimated-profit", "dianxiaomi-warehouse-cost"], {}, {"order": ["order_id"], "sku": ["sku", "msku", "asin"], "sales": ["sales_amount", "paid_amount"], "commission": ["platform_commission"], "fba": ["fba_fee"], "ad": ["ad_spend"], "refundFee": ["refund_fee"], "storage": ["storage_fee"], "purchaseCost": ["purchase_cost", "cost_amount"], "profit": ["estimated_profit", "profit_amount"]}, signals=["platform_commission", "fba_fee", "estimated_profit"], options={"aggregation": "count", "tableColumnLimit": 10, "topN": 100}),
    _unit("fba-fee-rank", "跨境利润核算", "bar", "FBA/配送费排行", "FBA费用、配送费和退货费常解释利润低于预期。", ["dianxiaomi-amazon-profit", "sellfox-ar-report"], {"measure": ["fba_fee", "refund_fee", "freight_amount"], "dimension": ["sku", "asin", "store"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 15}),
    _unit("developer-profit-rank", "跨境利润核算", "bar", "开发员利润排行", "跨境商品开发员维度能帮助判断选品质量和利润贡献。", ["dianxiaomi-amazon-profit"], {"measure": ["estimated_profit", "profit_amount", "sales_amount"], "dimension": ["developer"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 12}),
    _unit("fee-allocation-table", "跨境利润核算", "table", "费用分摊核查", "水电、人力、仓储等费用需要按 SKU 销量、销售额、体积或重量分摊。", ["dianxiaomi-amazon-profit"], {}, {"sku": ["sku", "asin"], "method": ["fee_allocation_method"], "labor": ["labor_cost"], "utilities": ["utilities_cost"], "weight": ["sku_weight"], "volume": ["sku_volume"], "sales": ["sales_amount"], "profit": ["estimated_profit", "profit_amount"]}, signals=["fee_allocation_method", "labor_cost", "sku"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("ar-aging-overdue-kpi", "财务往来/账龄", "metric", "逾期应收金额", "应收风险先看逾期金额或坏账风险，不只看销售额。", ["kingdee-ar-management", "yonyou-report-optimization"], {"measure": ["overdue_amount", "ar_amount"]}, {"date": ["due_date"]}, options={"aggregation": "sum", "valueFormat": "currency"}),
    _unit("ar-aging-rank", "财务往来/账龄", "bar", "客户账龄排行", "账龄段、逾期天数和客户余额适合作为财务追款入口。", ["kingdee-ar-management", "yonyou-report-optimization"], {"measure": ["overdue_amount", "customer_balance", "ar_amount", "aging_days"], "dimension": ["customer", "aging_bucket"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 15}),
    _unit("ar-aging-table", "财务往来/账龄", "table", "应收账龄明细", "客户、账龄段、到期日、收款计划、逾期金额和坏账风险要连在一起。", ["kingdee-ar-management"], {}, {"customer": ["customer"], "bucket": ["aging_bucket"], "days": ["aging_days"], "due": ["due_date"], "plan": ["collection_plan"], "balance": ["customer_balance", "ar_amount"], "overdue": ["overdue_amount"], "risk": ["bad_debt_risk"]}, signals=["aging_bucket", "overdue_amount", "customer"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("supplier-balance-rank", "财务往来/账龄", "bar", "供应商余额排行", "采购应付和供应商余额表需要支持付款优先级排序。", ["yonyou-report-optimization", "wsgjp-webstore-erp"], {"measure": ["supplier_balance", "ap_amount", "payment_amount"], "dimension": ["supplier"]}, options={"aggregation": "sum", "valueFormat": "currency", "barOrientation": "horizontal", "topN": 15}),
    _unit("cash-flow-trend", "财务往来/账龄", "line", "资金流水趋势", "现金账户、银行账户、收入支出和现金流金额适合做财务总览趋势。", ["guanjia-cloud-app", "chanjet-tcloud-connector"], {"measure": ["cash_flow_amount", "income_amount", "expense_amount"], "dimension": ["date", "settlement_date"]}, {"account": ["cash_account", "bank_account"]}, options={"aggregation": "sum", "valueFormat": "currency", "areaFill": True, "sortDirection": "asc", "topN": 24}),
    _unit("voucher-subject-table", "财务往来/账龄", "table", "凭证科目核查", "业务单据到凭证、科目、部门和项目的链路要能回查。", ["kingdee-ar-management", "chanjet-tcloud-connector"], {}, {"voucher": ["voucher_id"], "subject": ["account_subject"], "department": ["department"], "project": ["project"], "income": ["income_amount"], "expense": ["expense_amount"], "cash": ["cash_flow_amount"], "date": ["date"]}, signals=["voucher_id", "account_subject", "cash_flow_amount"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
    _unit("wip-qty-kpi", "制造计划/质量", "metric", "在制数量", "制造看板应区分在制、良品、不良和完工数量。", ["digiwin-manufacturing-modules", "finereport-manufacturing-dashboard"], {"measure": ["wip_qty"]}, options={"aggregation": "sum", "valueFormat": "compact"}),
    _unit("work-center-output-rank", "制造计划/质量", "bar", "工作中心产出排行", "按工作中心或产线查看产出、在制和工时，定位瓶颈。", ["digiwin-manufacturing-modules", "finereport-manufacturing-dashboard"], {"measure": ["complete_qty", "good_qty", "wip_qty", "work_hours"], "dimension": ["work_center", "workshop", "machine"]}, options={"aggregation": "sum", "valueFormat": "compact", "barOrientation": "horizontal", "topN": 15}),
    _unit("plan-actual-schedule-table", "制造计划/质量", "table", "计划实际进度核查", "计划开完工、实际开完工、在制和延期要放在同一张进度表。", ["digiwin-manufacturing-modules", "finereport-manufacturing-dashboard"], {}, {"order": ["production_order_id"], "product": ["product"], "workCenter": ["work_center"], "plannedStart": ["planned_start_date"], "plannedFinish": ["planned_finish_date"], "actualStart": ["actual_start_date"], "actualFinish": ["actual_finish_date"], "wip": ["wip_qty"], "delay": ["delay_days"]}, signals=["planned_start_date", "actual_finish_date", "production_order_id"], options={"aggregation": "count", "tableColumnLimit": 10, "topN": 100}),
    _unit("yield-rate-rank", "制造计划/质量", "bar", "良品率排行", "良品率、合格率、不良数量和返工数量应该按车间、工序或设备定位。", ["digiwin-manufacturing-modules", "finereport-manufacturing-dashboard"], {"measure": ["yield_rate", "quality_pass_rate", "bad_qty", "rework_qty"], "dimension": ["work_center", "process", "machine"]}, options={"aggregation": "avg", "valueFormat": "percent", "barOrientation": "horizontal", "topN": 15}),
    _unit("outsourcing-progress-rank", "制造计划/质量", "bar", "委外进度排行", "委外数量、入库和延期需要和供应商/工作中心并排查看。", ["digiwin-manufacturing-modules", "kingdee-purchase-execution"], {"measure": ["outsourced_qty", "stockin_qty", "delay_days"], "dimension": ["supplier", "work_center", "product"]}, options={"aggregation": "sum", "valueFormat": "compact", "barOrientation": "horizontal", "topN": 12}),
    _unit("bom-version-slicer", "制造计划/质量", "slicer", "BOM/配方版本筛选", "食品、离散制造和服装样式都需要按 BOM 或配方版本筛选成本和质量。", ["wsgjp-food-manufacturing-case", "digiwin-manufacturing-modules"], {"dimension": ["bom_version"]}, options={"aggregation": "count", "slicerMultiSelect": True, "globalFilterTarget": True, "drillDown": False}),
    _unit("formula-cost-table", "制造计划/质量", "table", "配方成本核查", "食品制造案例里材料耗用、损耗、限额领料和成品成本是成本核算核心。", ["wsgjp-food-manufacturing-case"], {}, {"bom": ["bom_version"], "material": ["bom_material"], "issued": ["issued_qty"], "scrap": ["scrap_qty"], "loss": ["inventory_loss_qty"], "labor": ["labor_cost"], "utilities": ["utilities_cost"], "cost": ["cost_amount", "purchase_cost"]}, signals=["bom_version", "issued_qty", "cost_amount"], options={"aggregation": "count", "tableColumnLimit": 9, "topN": 100}),
])


def _normalize(value: Any) -> str:
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(value or "").strip().lower())


def _is_short_ascii_token(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9]+", value)) and len(value) < 4


def _is_ambiguous_ascii_field_token(value: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9]+", value)) and value in {
        "amount",
        "code",
        "cost",
        "customer",
        "date",
        "id",
        "name",
        "no",
        "order",
        "ordercode",
        "orderid",
        "orderno",
        "price",
        "qty",
        "quantity",
        "sales",
        "status",
        "stock",
        "time",
        "type",
    }


def _aliases(group_names: list[str]) -> list[str]:
    values: list[str] = []
    for group in group_names:
        values.extend(ERP_FIELD_ALIASES.get(group, [group]))
    return values


def _find_field(columns: list[str], groups: list[str]) -> tuple[str, int]:
    best_field = ""
    best_score = 0
    for field in columns:
        normalized_field = _normalize(field)
        if not normalized_field:
            continue
        for alias in _aliases(groups):
            normalized_alias = _normalize(alias)
            if not normalized_alias:
                continue
            score = 0
            if normalized_field == normalized_alias:
                score = 120
            elif not _is_short_ascii_token(normalized_alias) and normalized_alias in normalized_field:
                score = 90 + min(len(normalized_alias), 20)
            elif normalized_field in normalized_alias and len(normalized_field) >= 2 and not _is_ambiguous_ascii_field_token(normalized_field):
                score = 65 + min(len(normalized_field), 20)
            if score > best_score:
                best_score = score
                best_field = field
    return best_field, best_score


def _signal_matches(columns: list[str], groups: list[str]) -> dict[str, str]:
    matches: dict[str, str] = {}
    for group in groups:
        field, score = _find_field(columns, [group])
        if score:
            matches[group] = field
    return matches


def _column_order(columns: list[str], matched_fields: dict[str, str], fallback_limit: int = 8) -> list[str]:
    ordered: list[str] = []
    for field in matched_fields.values():
        if field and field in columns and field not in ordered:
            ordered.append(field)
    for field in columns:
        if field not in ordered:
            ordered.append(field)
        if len(ordered) >= fallback_limit:
            break
    return ordered[:fallback_limit]


def _reference_map() -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in PUBLIC_ERP_REFERENCES}


def _field_group_label(group: str) -> str:
    return ERP_FIELD_GROUP_LABELS.get(group, group)


def _missing_required_roles(unit: dict[str, Any], columns: list[str]) -> list[dict[str, Any]]:
    missing: list[dict[str, Any]] = []
    for role, groups in unit.get("required", {}).items():
        field, _score = _find_field(columns, groups)
        if field:
            continue
        missing.append({
            "role": role,
            "groups": groups,
            "labels": [_field_group_label(group) for group in groups],
        })
    return missing


def _unavailable_unit_hints(
    table_rows: list[dict[str, Any]],
    fields_by_key: dict[str, dict[str, Any]],
    candidate_unit_keys: set[str],
    *,
    preferred_table_key_value: str = "",
    limit: int = 8,
) -> list[dict[str, Any]]:
    table_scope = [
        table
        for table in table_rows
        if not preferred_table_key_value or str(table.get("table_key", "")) == preferred_table_key_value
    ]
    hints: list[dict[str, Any]] = []
    for unit in ERP_DASHBOARD_UNITS:
        unit_key = str(unit["key"])
        if unit_key in candidate_unit_keys or not unit.get("required"):
            continue
        best_missing: list[dict[str, Any]] = []
        best_table_key = ""
        for table in table_scope:
            table_key = str(table.get("table_key", ""))
            columns = [str(item) for item in fields_by_key.get(table_key, {}).get("columns", []) if str(item).strip()]
            if not columns:
                continue
            missing = _missing_required_roles(unit, columns)
            if not best_missing or len(missing) < len(best_missing):
                best_missing = missing
                best_table_key = table_key
        if not best_missing:
            continue
        hints.append({
            "key": unit_key,
            "title": unit["title"],
            "category": unit["category"],
            "type": unit["type"],
            "tableKey": best_table_key,
            "missingRoles": best_missing[:3],
            "neededFields": sorted({label for item in best_missing for label in item.get("labels", [])})[:5],
            "reason": "Required ERP fields were not found in the current table scope.",
        })
    hints.sort(key=lambda item: (str(item["category"]), str(item["title"])))
    return hints[:limit]


def _category_coverage(
    selected: list[dict[str, Any]],
    templates: list[dict[str, Any]],
    unavailable_hints: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    categories = sorted({str(item["category"]) for item in ERP_DASHBOARD_UNITS})
    selected_by_category: dict[str, int] = {}
    candidate_by_category: dict[str, int] = {}
    unavailable_by_category: dict[str, int] = {}
    for item in selected:
        category = str(item.get("category", ""))
        selected_by_category[category] = selected_by_category.get(category, 0) + 1
    for item in templates:
        category = str(item.get("category", ""))
        candidate_by_category[category] = candidate_by_category.get(category, 0) + 1
    for item in unavailable_hints:
        category = str(item.get("category", ""))
        unavailable_by_category[category] = unavailable_by_category.get(category, 0) + 1
    return [
        {
            "category": category,
            "selected": selected_by_category.get(category, 0),
            "candidates": candidate_by_category.get(category, 0),
            "unavailable": unavailable_by_category.get(category, 0),
        }
        for category in categories
        if selected_by_category.get(category, 0) or candidate_by_category.get(category, 0) or unavailable_by_category.get(category, 0)
    ]


def _resolve_unit_for_table(unit: dict[str, Any], table: dict[str, Any], fields: dict[str, Any], slug: Callable[[str], str]) -> dict[str, Any] | None:
    columns = [str(item) for item in fields.get("columns", []) if str(item).strip()]
    if not columns:
        return None

    matched: dict[str, str] = {}
    score = 0
    anchors = unit.get("anchors", [])
    if anchors:
        anchor_field, anchor_score = _find_field(columns, anchors)
        if not anchor_field:
            return None
        matched["anchor"] = anchor_field
        score += anchor_score + 40
    for role, groups in unit.get("required", {}).items():
        field, field_score = _find_field(columns, groups)
        if not field:
            return None
        matched[role] = field
        score += field_score + 100

    signals = unit.get("signals", [])
    signal_matches = _signal_matches(columns, signals)
    if signals and len(signal_matches) < min(2, len(signals)) and not unit.get("required"):
        return None
    score += len(signal_matches) * 30
    matched.update({f"signal:{key}": value for key, value in signal_matches.items()})

    for role, groups in unit.get("optional", {}).items():
        field, field_score = _find_field(columns, groups)
        if field:
            matched[role] = field
            score += field_score // 2

    widget_type = str(unit["type"])
    options = dict(unit.get("options", {}))
    if matched.get("dimension") and not options.get("dimension"):
        options["dimension"] = matched["dimension"]
    if matched.get("date") and widget_type == "line":
        options["dimension"] = matched["date"]
    if matched.get("measure") and not options.get("measure"):
        options["measure"] = matched["measure"]
    if matched.get("filter") and widget_type == "slicer" and not options.get("dimension"):
        options["dimension"] = matched["filter"]
    if widget_type == "table":
        options["columns"] = _column_order(columns, matched, int(options.get("tableColumnLimit") or 8))
    if widget_type == "text":
        reference_titles = []
        references = _reference_map()
        for source_id in unit["sources"][:6]:
            source = references.get(source_id)
            if source:
                reference_titles.append(f"{source['vendor']}：{source['title']}")
        options["textContent"] = "\n".join(
            [
                "本卡片来自公开 ERP 字段/报表单元库，不是固定模板。",
                f"命中字段: {', '.join(sorted(set(matched.values()))) or '按当前表结构保留为说明卡'}",
                f"参考来源: {'；'.join(reference_titles)}",
                "Agent 会按当前表字段命中率选择需要渲染的看板单元；缺字段的单元不会强行生成。",
            ]
        )
    if widget_type in {"metric", "bar", "line", "pie"} and not options.get("measure"):
        return None
    if widget_type in {"bar", "line", "pie", "slicer"} and not options.get("dimension"):
        return None

    source_refs = [f"erp-unit-library:{source_id}" for source_id in unit["sources"]]
    table_key = str(table.get("table_key", ""))
    display_name = str(table.get("display_name") or table_key)
    unit_id = f"erp_{slug(table_key)}_{slug(str(unit['key']))}"
    return {
        "id": unit_id,
        "category": unit["category"],
        "type": widget_type,
        "title": unit["title"],
        "reason": unit["reason"],
        "tableKey": table_key,
        "tableName": display_name,
        "score": score,
        "sourceIds": unit["sources"],
        "matchedFields": matched,
        "preset": {
            "type": widget_type,
            "title": unit["title"],
            "tableKey": table_key,
            "subtitle": f"{unit['category']} · {display_name}",
            "erpUnitKey": unit["key"],
            "erpUnitScore": score,
            "erpUnitSources": unit["sources"],
            "matchedFields": matched,
            "evidenceRefs": source_refs,
            **options,
        },
    }


def build_erp_dashboard_unit_templates(
    table_rows: list[dict[str, Any]],
    fields_by_key: dict[str, dict[str, Any]],
    *,
    preferred_table_key_value: str = "",
    limit: int = 24,
    slug: Callable[[str], str],
) -> dict[str, Any]:
    templates: list[dict[str, Any]] = []
    for table in table_rows:
        table_key = str(table.get("table_key", ""))
        if preferred_table_key_value and table_key != preferred_table_key_value:
            continue
        fields = fields_by_key.get(table_key, {})
        for unit in ERP_DASHBOARD_UNITS:
            resolved = _resolve_unit_for_table(unit, table, fields, slug)
            if resolved:
                templates.append(resolved)

    templates.sort(key=lambda item: (-int(item.get("score", 0)), str(item.get("category", "")), str(item.get("id", ""))))
    selected = templates[: max(1, min(limit, 36))]
    selected_unit_keys = {str(item.get("preset", {}).get("erpUnitKey") or "") for item in selected if isinstance(item.get("preset"), dict)}
    candidate_unit_keys = {str(item.get("preset", {}).get("erpUnitKey") or "") for item in templates if isinstance(item.get("preset"), dict)}
    unavailable_hints = _unavailable_unit_hints(
        table_rows,
        fields_by_key,
        candidate_unit_keys,
        preferred_table_key_value=preferred_table_key_value,
    )
    not_selected_count = len({key for key in candidate_unit_keys if key and key not in selected_unit_keys})
    categories: dict[str, int] = {}
    source_ids: set[str] = set()
    for template in selected:
        categories[str(template["category"])] = categories.get(str(template["category"]), 0) + 1
        source_ids.update(str(item) for item in template.get("sourceIds", []))
    reference_by_id = _reference_map()
    return {
        "templates": selected,
        "categories": [{"category": key, "count": value} for key, value in categories.items()],
        "tableCount": len(table_rows),
        "templateKey": ERP_UNIT_LIBRARY_TEMPLATE_KEY,
        "defaultTableKey": selected[0]["tableKey"] if selected else (preferred_table_key_value or (table_rows[0]["table_key"] if table_rows else "")),
        "erpUnitLibrary": {
            "mode": "agent-selected-units",
            "availableUnitCount": len(ERP_DASHBOARD_UNITS),
            "selectedUnitCount": len(selected),
            "candidateUnitCount": len(templates),
            "notSelectedUnitCount": not_selected_count,
            "unavailableUnitCount": max(0, len(ERP_DASHBOARD_UNITS) - len(candidate_unit_keys)),
            "omittedUnitHints": unavailable_hints,
            "categoryCoverage": _category_coverage(selected, templates, unavailable_hints),
            "referenceCount": len(PUBLIC_ERP_REFERENCES),
            "selectedSourceIds": sorted(source_ids),
            "selectedSources": [reference_by_id[source_id] for source_id in sorted(source_ids) if source_id in reference_by_id],
            "selectionPolicy": "Score current table fields against public ERP field/report unit aliases; render only units with enough evidence.",
        },
    }


def build_erp_unit_library_catalog_payload(*, include_units: bool = True) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "templateKey": ERP_UNIT_LIBRARY_TEMPLATE_KEY,
        "referenceCount": len(PUBLIC_ERP_REFERENCES),
        "unitCount": len(ERP_DASHBOARD_UNITS),
        "categoryCount": len({item["category"] for item in ERP_DASHBOARD_UNITS}),
        "references": PUBLIC_ERP_REFERENCES,
        "fieldAliasGroupCount": len(ERP_FIELD_ALIASES),
        "selectionPolicy": "Agent selects dashboard units from matched fields, not a fixed ERP dashboard template.",
    }
    if include_units:
        payload["units"] = [
            {
                "key": item["key"],
                "category": item["category"],
                "type": item["type"],
                "title": item["title"],
                "required": item["required"],
                "optional": item["optional"],
                "anchors": item.get("anchors", []),
                "sources": item["sources"],
            }
            for item in ERP_DASHBOARD_UNITS
        ]
    return payload


def prompt_prefers_erp_unit_library(prompt: str) -> bool:
    lower = prompt.lower()
    return any(token in prompt for token in [
        "ERP",
        "电商",
        "聚水潭",
        "旺店通",
        "金蝶",
        "用友",
        "畅捷通",
        "管易云",
        "管家婆",
        "赛狐",
        "积加",
        "领星",
        "马帮",
        "万里牛",
        "鼎捷",
        "店小秘",
        "订单",
        "出库",
        "售后",
        "退款",
        "采购",
        "库存",
        "应收",
        "应付",
        "回款",
        "结算",
        "对账",
        "账龄",
        "供应商",
        "生产",
        "制造",
        "齐套",
        "工单",
        "车间",
        "领料",
        "发料",
        "跨境",
        "店铺",
        "分销",
        "会员",
        "补货",
        "广告",
        "亚马逊",
        "FBA",
        "预估利润",
        "平台佣金",
        "开发员",
        "账龄",
        "逾期",
        "坏账",
        "门店",
        "收银",
        "POS",
        "尺码",
        "颜色",
        "款式",
        "条码",
        "调拨",
        "盘点",
        "库位",
        "冷链",
        "质检",
        "良品",
        "预测",
        "利润",
        "报表",
        "报告",
        "税费",
        "仓储费",
        "货损",
        "效期",
        "批次",
        "老板",
        "进销存",
    ]) or any(token in lower for token in ["erp", "wms", "oms", "mes", "mrp", "pos", "sku", "asin", "msku", "fba", "bom", "fifo", "inventory", "purchase", "receivable", "payable", "settlement", "replenishment", "stockout", "marketplace", "kitting", "workorder", "profit", "commission", "warehouse"])
