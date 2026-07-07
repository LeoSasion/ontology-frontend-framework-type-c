from __future__ import annotations

from pathlib import Path
from typing import Any

from evidence_profile_runtime.file_readers import discover_source_files, read_source_tables


def read_tables(input_paths: list[Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return read_source_tables(discover_source_files(input_paths))
