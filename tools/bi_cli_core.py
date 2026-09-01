from __future__ import annotations

import base64
import hashlib
import itertools
import json
import os
import re
import time
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = ROOT / "data" / "local"
# Storage generation 2 is intentionally a clean break.  Keeping new defaults
# prevents an older mixed SQLite/DuckDB data plane from being opened or
# rewritten implicitly; operators may still bind isolated test paths through
# the existing environment variables.
DB_PATH = Path(os.environ.get("AIBI_HYBRID_DB_PATH", DEFAULT_DATA_DIR / "aibi_control_v2.sqlite"))
DUCKDB_PATH = Path(os.environ.get("AIBI_HYBRID_DUCKDB_PATH", DEFAULT_DATA_DIR / "aibi_catalog_v2.duckdb"))
_UNIQUE_COUNTER = itertools.count()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def unique_key(prefix: str) -> str:
    return f"{prefix}_{time.time_ns()}_{os.getpid()}_{next(_UNIQUE_COUNTER)}"


def json_default(value: Any) -> Any:
    """Encode values returned by typed analytical queries as JSON scalars."""

    if isinstance(value, (datetime, date, datetime_time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        # Keep decimal precision at the protocol boundary instead of silently
        # converting a potentially large value to a binary floating point.
        return format(value, "f")
    if isinstance(value, timedelta):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "base64:" + base64.b64encode(bytes(value)).decode("ascii")
    if isinstance(value, (Path, UUID)):
        return str(value)
    return str(value)


def dump(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=json_default))


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
