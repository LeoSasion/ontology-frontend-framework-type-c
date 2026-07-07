from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from evidence_profile_runtime.semantic_text import clean, normalized_key


def normalize_columns(columns: list[object]) -> list[str]:
    seen: dict[str, int] = {}
    normalized: list[str] = []
    for index, column in enumerate(columns, start=1):
        base = clean(column) or f"column_{index}"
        if re.match(r"^unnamed", base, flags=re.IGNORECASE):
            base = f"column_{index}"
        count = seen.get(base, 0) + 1
        seen[base] = count
        normalized.append(base if count == 1 else f"{base}_{count}")
    return normalized


def prepare_table_frame(frame: pd.DataFrame) -> pd.DataFrame:
    prepared = frame.copy()
    prepared.columns = normalize_columns(list(prepared.columns))
    prepared = prepared.dropna(axis=0, how="all").dropna(axis=1, how="all")
    if prepared.empty and not list(prepared.columns):
        prepared = pd.DataFrame({"empty_source_marker": []})
    return prepared


def table_key_for(path: Path, sheet_name: str | None, used: set[str]) -> str:
    stem = normalized_key(path.stem)
    if sheet_name:
        stem = f"{stem}_{normalized_key(sheet_name)}"
    key = stem or "source_table"
    original = key
    suffix = 2
    while key in used:
        key = f"{original}_{suffix}"
        suffix += 1
    used.add(key)
    return key


def should_skip_low_signal_table(frame: pd.DataFrame) -> bool:
    return False


def split_raw_table_sections(frame: pd.DataFrame) -> list[pd.DataFrame]:
    return [frame]
