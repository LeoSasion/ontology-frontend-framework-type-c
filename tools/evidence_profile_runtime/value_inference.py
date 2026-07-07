from __future__ import annotations

from typing import Any
import warnings

import pandas as pd


def to_number(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    cleaned = (
        text.replace(",", "")
        .replace("，", "")
        .replace("¥", "")
        .replace("￥", "")
        .replace("%", "")
        .replace("元", "")
    )
    try:
        return float(cleaned)
    except ValueError:
        return None


def numeric_series(series: pd.Series) -> pd.Series:
    return series.map(to_number)


def datetime_series(series: pd.Series) -> pd.Series:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return pd.to_datetime(series, errors="coerce")


def looks_like_datetime(series: pd.Series) -> bool:
    sample = series.dropna().astype(str).head(80)
    if sample.empty:
        return False
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        parsed = pd.to_datetime(sample, errors="coerce")
    return float(parsed.notna().mean()) >= 0.55


def infer_value_type(series: pd.Series) -> str:
    non_null = series.dropna()
    if non_null.empty:
        return "empty"
    numbers = numeric_series(non_null)
    if float(numbers.notna().mean()) >= 0.75:
        return "number"
    if looks_like_datetime(non_null):
        return "datetime"
    return "text"


def sample_values(series: pd.Series, limit: int = 8) -> list[Any]:
    values: list[Any] = []
    for value in series.dropna().head(200):
        text = str(value)
        if text not in values:
            values.append(text)
        if len(values) >= limit:
            break
    return values


def value_profile(series: pd.Series) -> dict[str, Any]:
    row_count = int(len(series))
    non_null_count = int(series.notna().sum())
    unique_count = int(series.dropna().astype(str).nunique())
    inferred_type = infer_value_type(series)
    numeric = numeric_series(series)
    stats: dict[str, Any] = {
        "type": inferred_type,
        "rowCount": row_count,
        "nonNullCount": non_null_count,
        "nullRate": round(1 - non_null_count / max(1, row_count), 4),
        "uniqueCount": unique_count,
        "uniqueRatio": round(unique_count / max(1, non_null_count), 4),
        "samples": sample_values(series),
    }
    if inferred_type == "number":
        valid = numeric.dropna()
        stats["numeric"] = {
            "min": float(valid.min()) if not valid.empty else None,
            "max": float(valid.max()) if not valid.empty else None,
            "sum": float(valid.sum()) if not valid.empty else 0.0,
            "mean": float(valid.mean()) if not valid.empty else None,
        }
    if inferred_type == "datetime":
        dates = datetime_series(series).dropna()
        stats["datetime"] = {
            "min": dates.min().isoformat() if not dates.empty else None,
            "max": dates.max().isoformat() if not dates.empty else None,
        }
    return stats


def infer_sensitivity(field_name: str, samples: list[Any]) -> str:
    lower = field_name.lower()
    if any(token in lower for token in ["phone", "mobile", "手机号", "电话", "地址", "address"]):
        return "personal"
    sample_text = " ".join(str(item) for item in samples[:5])
    if "@" in sample_text:
        return "personal"
    return "normal"


def currency_stats(series: pd.Series) -> dict[str, Any]:
    numeric = numeric_series(series).dropna()
    return {"sum": float(numeric.sum()) if not numeric.empty else 0.0, "count": int(numeric.count())}


def date_stats(series: pd.Series) -> dict[str, Any]:
    dates = datetime_series(series).dropna()
    return {
        "count": int(dates.count()),
        "min": dates.min().isoformat() if not dates.empty else None,
        "max": dates.max().isoformat() if not dates.empty else None,
    }
