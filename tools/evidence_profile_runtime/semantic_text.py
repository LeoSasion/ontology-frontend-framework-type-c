from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

IDENTITY_HYPHEN_VARIANTS = "-‐‑‒–—―－"
IDENTITY_NORMALIZATION_POLICY = "trim, lowercase, normalize unicode width, and collapse whitespace/hyphen variants"

SEMANTIC_ALIASES: dict[str, list[str]] = {
    "order_id": ["order_id", "orderid", "订单号", "子订单", "主订单", "交易单号", "订单编号", "单据编号", "单号"],
    "refund_id": ["refund_id", "售后单", "退款单", "退货单", "售后编号"],
    "transaction_id": ["流水", "流水号", "transaction", "payment_id", "settlement_id", "资金流水"],
    "sku": ["sku", "商家编码", "商品编码", "规格编码", "货品编号"],
    "product_id": ["商品id", "产品id", "货品id", "product_id", "item_id", "goods_id"],
    "customer_id": ["customer", "member", "会员", "客户", "买家", "用户id", "客户id"],
    "supplier": ["supplier", "供应商", "厂家", "供货商"],
    "warehouse": ["warehouse", "仓库", "仓", "库房"],
    "channel": ["channel", "平台", "渠道", "店铺", "shop", "store", "来源"],
    "category": ["category", "类目", "分类", "品类", "品类名称"],
    "status": ["status", "状态", "订单状态", "退款状态", "审核状态"],
    "contact_phone": ["电话", "手机号", "联系方式", "mobile", "phone", "tel"],
    "person_name": ["联系人", "联系人姓名", "姓名", "收货人", "买家姓名"],
    "source_metadata": ["__source_file", "__source_month", "__source_order", "source_file", "source_month"],
    "paid_at": ["paid_at", "pay_time", "付款时间", "支付时间", "下单时间", "订单日期", "order_date", "date", "日期", "时间"],
    "refund_at": ["refund_at", "售后时间", "退款时间", "申请时间", "退货时间"],
    "paid_gmv": ["gross_sales", "gmv", "支付金额", "实付", "应付", "应结", "订单金额", "商品总价", "销售额", "成交金额", "销售金额"],
    "net_sales": ["net_sales", "净销售", "净额", "收入", "实际收入", "结算收入"],
    "refund_amount": ["refund_amount", "退款金额", "退货金额", "售后金额", "退款", "售后应退", "退回金额"],
    "cost_amount": ["cost", "成本", "商品成本", "采购金额", "采购价", "费用", "运费", "物流费", "支出", "服务费", "税费"],
    "settlement_amount": ["settlement", "结算", "入账", "出账", "动账", "账户金额", "收支金额", "补贴", "佣金", "分成", "抵扣", "优惠"],
    "quantity": ["quantity", "qty", "数量", "件数", "库存数", "出库数量", "入库数量"],
    "inventory_qty": ["inventory", "库存", "可售", "在库", "结存", "库存数量"],
}

IDENTITY_SEMANTICS = {"order_id", "refund_id", "transaction_id", "sku", "product_id", "customer_id", "supplier", "warehouse"}
MEASURE_SEMANTICS = {"paid_gmv", "net_sales", "refund_amount", "cost_amount", "settlement_amount", "quantity", "inventory_qty"}
TIME_SEMANTICS = {"paid_at", "refund_at"}
DIMENSION_SEMANTICS = {"channel", "category", "status", "supplier", "warehouse", "sku", "product_id", "customer_id"}
ATTRIBUTE_SEMANTICS = {"contact_phone", "person_name", "source_metadata"}


def clean(value: object) -> str:
    if value is None:
        return ""
    text = str(value).replace("\ufeff", "").strip()
    return re.sub(r"\s+", " ", text)


def normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", clean(value)).lower()
    for hyphen in IDENTITY_HYPHEN_VARIANTS:
        text = text.replace(hyphen, "-")
    return re.sub(r"[\s_./\\:：;；,，()（）\[\]【】]+", "", text)


def normalized_key(value: object) -> str:
    text = unicodedata.normalize("NFKC", clean(value)).lower()
    text = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_") or "field"


def normalize_identity_value(value: object) -> str:
    text = normalize_text(value)
    return text.replace("-", "")


def expand_tokens(value: object) -> list[str]:
    text = unicodedata.normalize("NFKC", clean(value)).lower()
    words = re.findall(r"[0-9a-zA-Z]+|[\u4e00-\u9fff]+", text)
    tokens: list[str] = []
    for word in words:
        tokens.append(word)
        if len(word) > 2 and re.search(r"[\u4e00-\u9fff]", word):
            tokens.extend(word[index : index + 2] for index in range(len(word) - 1))
    return sorted(set(tokens))


def identifier_tokens(value: object) -> set[str]:
    return set(expand_tokens(value))


def semantic_alias_tokens(semantic: str) -> set[str]:
    tokens: set[str] = set()
    for alias in SEMANTIC_ALIASES.get(semantic, []):
        tokens.update(expand_tokens(alias))
        tokens.add(normalize_text(alias))
    return tokens


def token_overlap_score(left: object, right: object) -> float:
    left_tokens = identifier_tokens(left)
    right_tokens = identifier_tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))


def alias_matches_field(alias: str, field_name: str) -> bool:
    alias_norm = normalize_text(alias)
    field_norm = normalize_text(field_name)
    return bool(alias_norm and (alias_norm in field_norm or field_norm in alias_norm))


def infer_semantic(field_name: str, table_label: str = "") -> tuple[str, float, str]:
    haystack = f"{field_name} {table_label}"
    normalized = normalize_text(haystack)
    best_semantic = ""
    best_score = 0.0
    best_alias = ""
    for semantic, aliases in SEMANTIC_ALIASES.items():
        for alias in aliases:
            alias_norm = normalize_text(alias)
            if not alias_norm:
                continue
            if alias_norm in normalized:
                score = min(0.98, 0.72 + min(len(alias_norm), 10) / 40)
            else:
                score = SequenceMatcher(None, alias_norm, normalize_text(field_name)).ratio() * 0.72
            if score > best_score:
                best_semantic, best_score, best_alias = semantic, score, alias
    if best_score >= 0.52:
        return best_semantic, round(best_score, 3), f"matched alias `{best_alias}`"
    return f"field_{normalized_key(field_name)}", 0.35, "generic field fallback"


def semantic_role(semantic: str, inferred_type: str, unique_ratio: float) -> tuple[str, str]:
    if semantic in IDENTITY_SEMANTICS:
        return "identity", "join_key"
    if semantic in TIME_SEMANTICS or inferred_type == "datetime":
        return "event_time", "time_filter"
    if semantic in ATTRIBUTE_SEMANTICS:
        return "attribute", "descriptive"
    if semantic.startswith("field_") and inferred_type == "number" and unique_ratio > 0.75:
        return "attribute", "descriptive"
    if semantic in MEASURE_SEMANTICS or inferred_type == "number":
        return "measure", "aggregatable"
    if semantic in DIMENSION_SEMANTICS or unique_ratio <= 0.6:
        return "dimension", "groupable"
    return "attribute", "descriptive"
