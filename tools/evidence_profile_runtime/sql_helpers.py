from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

import pandas as pd


def quote_ident(value: object) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def json_ready(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_ready(item) for item in value]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def numeric_sql(field_name: str) -> str:
    return f"TRY_CAST({quote_ident(field_name)} AS DOUBLE)"


def datetime_sql(field_name: str) -> str:
    return f"TRY_CAST({quote_ident(field_name)} AS TIMESTAMP)"


def month_key_sql(field_name: str) -> str:
    return f"strftime({datetime_sql(field_name)}, '%Y-%m')"


def datetime_month_sql(field_name: str) -> str:
    return month_key_sql(field_name)


def ratio_sql(numerator: str, denominator: str) -> str:
    return f"CASE WHEN {denominator} = 0 THEN NULL ELSE {numerator} / {denominator} END"


def deduction_sql(left: str, right: str) -> str:
    return f"COALESCE({left}, 0) - COALESCE({right}, 0)"


def field_unit_multiplier(field_name: str) -> float:
    return 1.0


def settlement_direction_sql(field_name: str) -> str:
    return f"CASE WHEN {quote_ident(field_name)} < 0 THEN 'outflow' ELSE 'inflow' END"


def signed_settlement_amount_sql(field_name: str) -> str:
    return numeric_sql(field_name)
