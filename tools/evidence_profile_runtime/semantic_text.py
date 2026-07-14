from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any

IDENTITY_HYPHEN_VARIANTS = "-‐‑‒–—―－"
IDENTITY_NORMALIZATION_POLICY = "trim, lowercase, normalize unicode width, and collapse whitespace/hyphen variants"

SEMANTIC_ALIASES: dict[str, list[str]] = {
    "identifier": ["id", "key", "code", "identifier", "编号", "编码", "标识", "唯一键"],
    "numeric_value": ["value", "amount", "total", "score", "rate", "数值", "金额", "合计", "得分", "比例"],
    "quantity": ["quantity", "qty", "count", "数量", "件数", "人数", "次数"],
    "category": ["category", "type", "group", "class", "类别", "类型", "分组", "分类"],
    "status": ["status", "state", "stage", "状态", "阶段", "结果"],
    "event_time": ["date", "time", "month", "event_time", "日期", "时间", "月份", "期间"],
    "text": ["name", "title", "description", "label", "名称", "标题", "描述", "标签"],
    "source_metadata": ["__source_file", "__source_month", "__source_order", "source_file", "source_month"],
}

IDENTITY_SEMANTICS = {"identifier"}
MEASURE_SEMANTICS = {"numeric_value", "quantity"}
TIME_SEMANTICS = {"event_time"}
DIMENSION_SEMANTICS = {"category", "status"}
ATTRIBUTE_SEMANTICS = {"text", "source_metadata"}


def semantic_catalog_for_runtime(domain_pack_context: dict[str, Any] | None = None) -> dict[str, Any]:
    aliases = {semantic: list(values) for semantic, values in SEMANTIC_ALIASES.items()}
    role_sets = {
        "identity": set(IDENTITY_SEMANTICS),
        "measure": set(MEASURE_SEMANTICS),
        "time": set(TIME_SEMANTICS),
        "dimension": set(DIMENSION_SEMANTICS),
        "attribute": set(ATTRIBUTE_SEMANTICS),
    }
    blocked_requirements: list[dict[str, Any]] = []
    enabled_ids = {
        str(item.get("packId"))
        for item in (domain_pack_context or {}).get("enabledDomainPacks", [])
        if isinstance(item, dict)
    }
    for manifest in (domain_pack_context or {}).get("availableDomainPacks", []):
        if not isinstance(manifest, dict) or manifest.get("packId") not in enabled_ids:
            continue
        contributions = manifest.get("contributions") if isinstance(manifest.get("contributions"), dict) else {}
        for semantic, values in (contributions.get("semanticAliases") or {}).items():
            aliases.setdefault(str(semantic), [])
            aliases[str(semantic)] = sorted(set([*aliases[str(semantic)], *[str(value) for value in values]]))
        for role, values in (contributions.get("semanticRoles") or {}).items():
            role_sets.setdefault(str(role), set()).update(str(value) for value in values)
        source_intelligence = contributions.get("sourceIntelligence") if isinstance(contributions.get("sourceIntelligence"), dict) else {}
        for requirement in source_intelligence.get("blockedRequirements") or []:
            if isinstance(requirement, dict):
                blocked_requirements.append(dict(requirement))
    return {
        "aliases": aliases,
        "roles": role_sets,
        "blockedRequirements": blocked_requirements,
        "enabledDomainPackIds": sorted(enabled_ids),
    }


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


def semantic_alias_tokens(semantic: str, semantic_aliases: dict[str, list[str]] | None = None) -> set[str]:
    tokens: set[str] = set()
    for alias in (semantic_aliases or SEMANTIC_ALIASES).get(semantic, []):
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


def infer_semantic(
    field_name: str,
    table_label: str = "",
    semantic_aliases: dict[str, list[str]] | None = None,
) -> tuple[str, float, str]:
    haystack = f"{field_name} {table_label}"
    normalized = normalize_text(haystack)
    best_semantic = ""
    best_score = 0.0
    best_alias = ""
    for semantic, aliases in (semantic_aliases or SEMANTIC_ALIASES).items():
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


def semantic_role(
    semantic: str,
    inferred_type: str,
    unique_ratio: float,
    role_sets: dict[str, set[str]] | None = None,
) -> tuple[str, str]:
    roles = role_sets or {
        "identity": IDENTITY_SEMANTICS,
        "measure": MEASURE_SEMANTICS,
        "time": TIME_SEMANTICS,
        "dimension": DIMENSION_SEMANTICS,
        "attribute": ATTRIBUTE_SEMANTICS,
    }
    if semantic in roles["identity"]:
        return "identity", "join_key"
    if semantic in roles["time"] or inferred_type == "datetime":
        return "event_time", "time_filter"
    if semantic in roles["attribute"]:
        return "attribute", "descriptive"
    if semantic.startswith("field_") and inferred_type == "number" and unique_ratio > 0.75:
        return "attribute", "descriptive"
    if semantic in roles["measure"] or inferred_type == "number":
        return "measure", "aggregatable"
    if semantic in roles["dimension"] or unique_ratio <= 0.6:
        return "dimension", "groupable"
    return "attribute", "descriptive"
