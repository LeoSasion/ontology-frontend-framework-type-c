from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "data" / "local"
DB_PATH = Path(os.environ.get("AIBI_HYBRID_DB_PATH", DEFAULT_DATA_DIR / "aibi_hybrid.sqlite"))
DUCKDB_PATH = Path(os.environ.get("AIBI_HYBRID_DUCKDB_PATH", DEFAULT_DATA_DIR / "aibi_hybrid.duckdb"))
A_PROJECT_ROOT = Path(os.environ.get("AIBI_PROJECT_A_PATH", r"C:\Users\Administrator\Documents\AIBI"))
B_PROJECT_ROOT = Path(os.environ.get("AIBI_PROJECT_B_PATH", r"C:\Users\Administrator\Documents\财务报表"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def unique_key(prefix: str) -> str:
    return f"{prefix}_{time.time_ns()}"


def dump(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def quote_identifier(name: str) -> str:
    value = str(name).strip()
    if not value or any(ord(ch) < 32 for ch in value):
        raise ValueError(f"Unsafe identifier: {name}")
    return '"' + value.replace('"', '""') + '"'


def quote_relationship_identifier(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def source_label(path: Path | str) -> str:
    source_path = Path(path)
    try:
        return str(source_path.relative_to(ROOT))
    except ValueError:
        return str(source_path)


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized or "source"


def workspace_slug(value: str) -> str:
    normalized = slug(value)
    if normalized != "source":
        return normalized
    digest = hashlib.sha1(value.strip().encode("utf-8")).hexdigest()[:8]
    return f"workspace_{digest}"


def parse_csv_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in re.split(r"[,，]", value) if item.strip()]
