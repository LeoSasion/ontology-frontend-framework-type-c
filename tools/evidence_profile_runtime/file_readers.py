from __future__ import annotations

import hashlib
import warnings
from pathlib import Path
from typing import Any

import pandas as pd

from evidence_profile_runtime.table_preparation import prepare_table_frame, table_key_for

SUPPORTED_SUFFIXES = {".csv", ".xls", ".xlsx"}
CSV_ENCODINGS = ("utf-8-sig", "utf-8", "gb18030", "gbk", "big5", "latin1")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_source_files(input_paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for input_path in input_paths:
        path = Path(input_path)
        if path.is_dir():
            for candidate in path.rglob("*"):
                if candidate.is_file() and candidate.suffix.lower() in SUPPORTED_SUFFIXES:
                    files.append(candidate)
        elif path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            files.append(path)
    return sorted({item.resolve() for item in files}, key=lambda item: str(item).lower())


def read_csv_table(path: Path) -> tuple[pd.DataFrame, str]:
    last_error: Exception | None = None
    for encoding in CSV_ENCODINGS:
        try:
            frame = pd.read_csv(path, encoding=encoding, sep=None, engine="python")
            return prepare_table_frame(frame), encoding
        except Exception as error:  # pragma: no cover - fallback chain is data dependent
            last_error = error
    if last_error:
        raw = path.read_text(encoding="latin1", errors="replace").splitlines()
        rows = [line.split(",") for line in raw if line.strip()]
        if rows:
            header, body = rows[0], rows[1:]
            return prepare_table_frame(pd.DataFrame(body, columns=header)), "latin1-manual"
    return pd.DataFrame({"raw_line": []}), "unreadable-placeholder"


def read_excel_tables(path: Path) -> list[tuple[str, pd.DataFrame, str]]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            workbook = pd.read_excel(path, sheet_name=None)
    except Exception:
        return [("Sheet1", pd.DataFrame({"raw_file": [path.name]}), "excel-placeholder")]
    tables: list[tuple[str, pd.DataFrame, str]] = []
    for sheet_name, frame in workbook.items():
        tables.append((str(sheet_name), prepare_table_frame(frame), "excel"))
    if not tables:
        tables.append(("Sheet1", pd.DataFrame({"raw_file": [path.name]}), "excel-empty-placeholder"))
    return tables


def read_source_tables(files: list[Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    tables: list[dict[str, Any]] = []
    warnings_list: list[dict[str, Any]] = []
    used_keys: set[str] = set()
    for path in files:
        try:
            digest = sha256_file(path)
            if path.suffix.lower() == ".csv":
                frame, reader = read_csv_table(path)
                tables.append({
                    "tableKey": table_key_for(path, None, used_keys),
                    "tableLabel": path.stem,
                    "sourcePath": str(path.resolve()),
                    "sheetName": None,
                    "reader": reader,
                    "sha256": digest,
                    "frame": frame,
                })
            else:
                for sheet_name, frame, reader in read_excel_tables(path):
                    tables.append({
                        "tableKey": table_key_for(path, sheet_name, used_keys),
                        "tableLabel": f"{path.stem} / {sheet_name}",
                        "sourcePath": str(path.resolve()),
                        "sheetName": sheet_name,
                        "reader": reader,
                        "sha256": digest,
                        "frame": frame,
                    })
        except Exception as error:
            warnings_list.append({"sourcePath": str(path.resolve()), "warning": str(error)})
            frame = pd.DataFrame({"raw_file": [path.name]})
            tables.append({
                "tableKey": table_key_for(path, None, used_keys),
                "tableLabel": path.stem,
                "sourcePath": str(path.resolve()),
                "sheetName": None,
                "reader": "error-placeholder",
                "sha256": "",
                "frame": frame,
            })
    return tables, warnings_list
