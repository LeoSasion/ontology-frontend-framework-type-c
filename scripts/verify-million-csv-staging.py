from __future__ import annotations

import ctypes
import json
import os
import sys
import tempfile
from pathlib import Path
from time import perf_counter


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import duckdb  # type: ignore  # noqa: E402

from dataset_version_store import INTERNAL_ROW_ID  # noqa: E402
from import_stage_service import _write_csv_parquet  # noqa: E402


ROW_COUNT = 1_000_000
MAX_STAGE_SECONDS = 25.0
PEAK_RSS_BUDGET_BYTES = 1_500 * 1024 * 1024


def peak_rss_bytes() -> int:
    if os.name == "nt":
        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.c_ulong),
                ("PageFaultCount", ctypes.c_ulong),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        get_current_process = ctypes.windll.kernel32.GetCurrentProcess
        get_current_process.restype = ctypes.c_void_p
        process = get_current_process()
        get_process_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
        get_process_memory_info.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ProcessMemoryCounters),
            ctypes.c_ulong,
        ]
        get_process_memory_info.restype = ctypes.c_bool
        if not get_process_memory_info(process, ctypes.byref(counters), counters.cb):
            raise ctypes.WinError()
        return int(counters.PeakWorkingSetSize)
    import resource

    peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return peak if sys.platform == "darwin" else peak * 1024


with tempfile.TemporaryDirectory(prefix="aibi-million-csv-stage-") as raw_temp:
    root = Path(raw_temp)
    source = root / "million-orders.csv"
    staged = root / "million-orders.parquet"
    with duckdb.connect(":memory:") as connection:
        connection.execute(
            f"""
            COPY (
              SELECT printf('O%09d', i) AS order_id,
                     CASE i % 4 WHEN 0 THEN 'web' WHEN 1 THEN 'store' WHEN 2 THEN 'marketplace' ELSE 'partner' END AS channel,
                     CAST((i % 100000) / 100.0 AS DECIMAL(18,2)) AS amount,
                     CAST((i % 8) + 1 AS BIGINT) AS quantity,
                     DATE '2024-01-01' + CAST(i % 730 AS INTEGER) AS event_date,
                     i % 2 = 0 AS active,
                     'segment-' || CAST(i % 100 AS VARCHAR) AS note,
                     printf('%06d', i % 1000000) AS product_code,
                     1000000 + (i % 250000) AS customer_id,
                     CASE i % 4 WHEN 0 THEN 'east' WHEN 1 THEN 'south' WHEN 2 THEN 'west' ELSE 'north' END AS region,
                     CASE i % 3 WHEN 0 THEN 'CN' WHEN 1 THEN 'SG' ELSE 'JP' END AS country,
                     'city-' || CAST(i % 120 AS VARCHAR) AS city,
                     'category-' || CAST(i % 12 AS VARCHAR) AS category,
                     'subcategory-' || CAST(i % 48 AS VARCHAR) AS subcategory,
                     CAST(((i % 250000) + 100) / 100.0 AS DECIMAL(18,2)) AS unit_price,
                     CAST((i % 3000) / 10000.0 AS DECIMAL(9,4)) AS discount,
                     CAST((i % 70000) / 100.0 AS DECIMAL(18,2)) AS tax_amount,
                     CAST((i % 5000) / 100.0 AS DECIMAL(18,2)) AS shipping_amount,
                     CAST((i % 300000) / 100.0 AS DECIMAL(18,2)) AS net_amount,
                     CASE i % 3 WHEN 0 THEN 'CNY' WHEN 1 THEN 'SGD' ELSE 'JPY' END AS currency,
                     CASE i % 5 WHEN 0 THEN 'pending' WHEN 1 THEN 'paid' WHEN 2 THEN 'shipped' WHEN 3 THEN 'delivered' ELSE 'returned' END AS status,
                     CASE i % 4 WHEN 0 THEN 'card' WHEN 1 THEN 'wallet' WHEN 2 THEN 'transfer' ELSE 'cash' END AS payment_method,
                     TIMESTAMP '2024-01-01 00:00:00' + (i % 525600) * INTERVAL '1 minute' AS fulfilled_at,
                     i % 64 AS source_batch
              FROM range(1, {ROW_COUNT + 1}) AS source(i)
            ) TO ? (FORMAT CSV, HEADER true)
            """,
            [str(source)],
        )

    started = perf_counter()
    _write_csv_parquet(source, staged)
    elapsed_seconds = perf_counter() - started
    peak_rss = peak_rss_bytes()

    with duckdb.connect(":memory:") as connection:
        description = {
            str(row[0]): str(row[1]).upper()
            for row in connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(staged)]).fetchall()
        }
        row_count, distinct_rows, amount_total = connection.execute(
            f"SELECT COUNT(*), COUNT(DISTINCT {INTERNAL_ROW_ID}), SUM(amount) FROM read_parquet(?)",
            [str(staged)],
        ).fetchone()

    raw_temporaries = [path.name for path in root.glob(".*.raw.parquet")]
    checks = [
        {"label": "million-csv-rows-preserved", "ok": int(row_count) == ROW_COUNT},
        {"label": "stable-row-id-is-unique", "ok": int(distinct_rows) == ROW_COUNT},
        {
            "label": "sealed-types-are-native",
            "ok": description.get("order_id") == "VARCHAR"
            and description.get("amount", "").startswith("DECIMAL")
            and description.get("event_date") == "DATE"
            and description.get("active") == "BOOLEAN"
            and description.get("product_code") == "VARCHAR"
            and description.get("customer_id") == "VARCHAR"
            and description.get("unit_price", "").startswith("DECIMAL")
            and description.get("fulfilled_at") == "TIMESTAMP"
            and description.get("source_batch") == "BIGINT",
        },
        {"label": "numeric-aggregate-is-executable", "ok": amount_total is not None},
        {"label": "csv-stage-meets-performance-budget", "ok": elapsed_seconds <= MAX_STAGE_SECONDS},
        {"label": "csv-stage-meets-memory-budget", "ok": peak_rss <= PEAK_RSS_BUDGET_BYTES},
        {"label": "raw-parquet-temporary-is-cleaned", "ok": not raw_temporaries},
    ]
    failed = [item for item in checks if not item["ok"]]
    print(json.dumps({
        "ok": not failed,
        "schema": "aibi-million-csv-staging-verify/v1",
        "rowCount": ROW_COUNT,
        "columnCount": len(description) - 1,
        "elapsedMs": round(elapsed_seconds * 1000, 3),
        "budgetMs": int(MAX_STAGE_SECONDS * 1000),
        "peakRssBytes": peak_rss,
        "peakRssBudgetBytes": PEAK_RSS_BUDGET_BYTES,
        "sourceBytes": source.stat().st_size,
        "parquetBytes": staged.stat().st_size,
        "sealedTypes": description,
        "checks": checks,
        "failedChecks": failed,
    }, indent=2))
    raise SystemExit(1 if failed else 0)
