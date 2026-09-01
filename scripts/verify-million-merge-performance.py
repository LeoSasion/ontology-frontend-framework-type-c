from __future__ import annotations

"""Million-on-million set-based merge acceptance benchmark."""

import ast
import ctypes
import inspect
import json
import os
import sys
import tempfile
import textwrap
from pathlib import Path
from time import perf_counter


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import duckdb  # type: ignore  # noqa: E402

from dataset_version_store import INTERNAL_ROW_ID  # noqa: E402
from import_policy import preview_merge_plan_parquet  # noqa: E402
from import_table_writer_service import _materialize_merge_parquet  # noqa: E402


ROW_COUNT = 1_000_000
MERGE_BUDGET_SECONDS = 90.0
PEAK_RSS_BUDGET_BYTES = 1_500 * 1024 * 1024
SCHEMA_FIELDS = [
    {"name": "order_id", "type": "BIGINT"},
    {"name": "store_id", "type": "INTEGER"},
    {"name": "channel", "type": "VARCHAR"},
    {"name": "order_date", "type": "DATE"},
    {"name": "amount", "type": "DECIMAL(18,2)"},
    {"name": "quantity", "type": "INTEGER"},
    {"name": "sku", "type": "VARCHAR"},
    {"name": "customer_id", "type": "BIGINT"},
    {"name": "region", "type": "VARCHAR"},
    {"name": "status", "type": "VARCHAR"},
    {"name": "fulfilled_at", "type": "TIMESTAMP"},
    {"name": "is_returned", "type": "BOOLEAN"},
]


def sql_literal(path: Path) -> str:
    return "'" + path.resolve().as_posix().replace("'", "''") + "'"


def write_fixture(path: Path, *, first_order_id: int, incoming: bool) -> None:
    amount_multiplier = 2 if incoming else 1
    with duckdb.connect(":memory:") as connection:
        connection.execute(
            f"""
            COPY (
              SELECT
                i::BIGINT AS {INTERNAL_ROW_ID},
                ({first_order_id} + i - 1)::BIGINT AS order_id,
                (i % 1000)::INTEGER AS store_id,
                CASE i % 4 WHEN 0 THEN 'web' WHEN 1 THEN 'store' WHEN 2 THEN 'marketplace' ELSE 'partner' END AS channel,
                DATE '2024-01-01' + (i % 730)::INTEGER AS order_date,
                CAST((({first_order_id} + i - 1) * {amount_multiplier}) / 100.0 AS DECIMAL(18,2)) AS amount,
                ((i % 8) + 1)::INTEGER AS quantity,
                'SKU-' || LPAD(CAST(i % 50000 AS VARCHAR), 5, '0') AS sku,
                (1000000 + (i % 250000))::BIGINT AS customer_id,
                CASE i % 4 WHEN 0 THEN 'east' WHEN 1 THEN 'south' WHEN 2 THEN 'west' ELSE 'north' END AS region,
                CASE i % 5 WHEN 0 THEN 'pending' WHEN 1 THEN 'paid' WHEN 2 THEN 'shipped' WHEN 3 THEN 'delivered' ELSE 'returned' END AS status,
                TIMESTAMP '2024-01-01 00:00:00' + (i % 525600) * INTERVAL '1 minute' AS fulfilled_at,
                (i % 23 = 0) AS is_returned
              FROM range(1, {ROW_COUNT + 1}) AS generated(i)
            ) TO {sql_literal(path)}
            (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 122880)
            """
        )


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
        ok = get_process_memory_info(
            process,
            ctypes.byref(counters),
            counters.cb,
        )
        if not ok:
            raise ctypes.WinError()
        return int(counters.PeakWorkingSetSize)
    import resource

    peak = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return peak if sys.platform == "darwin" else peak * 1024


def execute_in_loop_guard() -> dict[str, int | bool]:
    tree = ast.parse(textwrap.dedent(inspect.getsource(_materialize_merge_parquet)))
    execute_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
    ]
    loop_executes = 0
    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.While)):
            continue
        loop_executes += sum(
            1
            for child in ast.walk(node)
            if isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr == "execute"
        )
    return {"executeCalls": len(execute_calls), "executeCallsInsideLoops": loop_executes, "ok": loop_executes == 0}


def verify_target_schema_key_cast(root: Path) -> dict[str, object]:
    active = root / "cast-active.parquet"
    incoming = root / "cast-incoming.parquet"
    merged = root / "cast-merged.parquet"
    schema_fields = [
        {"name": "business_key", "type": "DECIMAL(10,2)"},
        {"name": "value", "type": "VARCHAR"},
    ]
    with duckdb.connect(":memory:") as connection:
        connection.execute(
            f"COPY (SELECT 1::BIGINT AS {INTERNAL_ROW_ID}, 1.00::DECIMAL(10,2) AS business_key, "
            f"'active'::VARCHAR AS value) TO {sql_literal(active)} (FORMAT PARQUET)"
        )
        connection.execute(
            f"COPY (SELECT 1::BIGINT AS {INTERNAL_ROW_ID}, 1.0::DOUBLE AS business_key, "
            f"'incoming'::VARCHAR AS value) TO {sql_literal(incoming)} (FORMAT PARQUET)"
        )
    preview = preview_merge_plan_parquet(
        active_paths=[active],
        incoming_path=incoming,
        schema_fields=schema_fields,
        unique_fields=["business_key"],
        conflict_rule="overwrite",
    )
    _materialize_merge_parquet(
        active_paths=[active],
        incoming_path=incoming,
        schema_fields=schema_fields,
        unique_fields=["business_key"],
        conflict_rule="overwrite",
        destination=merged,
    )
    with duckdb.connect(":memory:") as connection:
        rows = connection.execute(
            f"SELECT COUNT(*), MAX(value) FROM read_parquet({sql_literal(merged)})"
        ).fetchone()
    return {
        "preview": preview,
        "outputRows": int(rows[0]),
        "outputValue": str(rows[1]),
        "ok": preview.get("matchedRows") == 1
        and preview.get("insertRows") == 0
        and preview.get("afterRowsEstimate") == 1
        and int(rows[0]) == 1
        and str(rows[1]) == "incoming",
    }


def verify_empty_key_preview(root: Path) -> dict[str, object]:
    active = root / "empty-key-active.parquet"
    incoming = root / "empty-key-incoming.parquet"
    schema_fields = [
        {"name": "business_key", "type": "VARCHAR"},
        {"name": "value", "type": "VARCHAR"},
    ]
    with duckdb.connect(":memory:") as connection:
        connection.execute(
            f"COPY (SELECT 1::BIGINT AS {INTERNAL_ROW_ID}, 'x'::VARCHAR AS business_key, "
            f"'active'::VARCHAR AS value) TO {sql_literal(active)} (FORMAT PARQUET)"
        )
        connection.execute(
            f"COPY (SELECT 1::BIGINT AS {INTERNAL_ROW_ID}, ''::VARCHAR AS business_key, "
            f"'incoming'::VARCHAR AS value) TO {sql_literal(incoming)} (FORMAT PARQUET)"
        )
    preview = preview_merge_plan_parquet(
        active_paths=[active],
        incoming_path=incoming,
        schema_fields=schema_fields,
        unique_fields=["business_key"],
        conflict_rule="overwrite",
    )
    return {
        "preview": preview,
        "ok": preview.get("dedupedIncomingRows") == 0
        and preview.get("emptyKeyRows") == 1
        and preview.get("matchedRows") == 0
        and preview.get("insertRows") == 0
        and preview.get("afterRowsEstimate") == 1,
    }


with tempfile.TemporaryDirectory(prefix="aibi-million-merge-") as raw_temp:
    root = Path(raw_temp)
    active = root / "active.parquet"
    incoming = root / "incoming.parquet"
    merged = root / "merged.parquet"
    write_fixture(active, first_order_id=1, incoming=False)
    write_fixture(incoming, first_order_id=500_001, incoming=True)

    peak_before = peak_rss_bytes()
    started = perf_counter()
    preview = preview_merge_plan_parquet(
        active_paths=[active],
        incoming_path=incoming,
        schema_fields=SCHEMA_FIELDS,
        unique_fields=["order_id"],
        conflict_rule="overwrite",
    )
    _materialize_merge_parquet(
        active_paths=[active],
        incoming_path=incoming,
        schema_fields=SCHEMA_FIELDS,
        unique_fields=["order_id"],
        conflict_rule="overwrite",
        destination=merged,
    )
    elapsed_seconds = perf_counter() - started
    peak_after = peak_rss_bytes()

    with duckdb.connect(":memory:") as connection:
        row_count, distinct_ids, overlap_amount, inserted_amount = connection.execute(
            f"""
            SELECT COUNT(*), COUNT(DISTINCT {INTERNAL_ROW_ID}),
                   MAX(CASE WHEN order_id = 750000 THEN amount END),
                   MAX(CASE WHEN order_id = 1250000 THEN amount END)
            FROM read_parquet({sql_literal(merged)})
            """
        ).fetchone()

    loop_guard = execute_in_loop_guard()
    target_schema_key_cast = verify_target_schema_key_cast(root)
    empty_key_preview = verify_empty_key_preview(root)
    peak_rss = max(peak_before, peak_after)
    checks = [
        {
            "label": "preview-counts-million-on-million-merge",
            "ok": preview.get("beforeRows") == ROW_COUNT
            and preview.get("incomingRows") == ROW_COUNT
            and preview.get("matchedRows") == 500_000
            and preview.get("insertRows") == 500_000
            and preview.get("afterRowsEstimate") == 1_500_000,
        },
        {"label": "merged-output-row-count-is-exact", "ok": int(row_count) == 1_500_000},
        {"label": "merged-output-row-id-is-unique", "ok": int(distinct_ids) == 1_500_000},
        {
            "label": "overwrite-and-insert-values-are-exact",
            "ok": str(overlap_amount) == "15000.00" and str(inserted_amount) == "25000.00",
        },
        {
            "label": "schema-validation-has-no-execute-inside-column-loop",
            "ok": bool(loop_guard["ok"]),
        },
        {
            "label": "preview-and-materialization-share-target-schema-key-casts",
            "ok": bool(target_schema_key_cast["ok"]),
        },
        {
            "label": "all-empty-unique-keys-do-not-create-synthetic-inserts",
            "ok": bool(empty_key_preview["ok"]),
        },
        {"label": "merge-meets-latency-budget", "ok": elapsed_seconds <= MERGE_BUDGET_SECONDS},
        {"label": "merge-process-peak-rss-is-bounded", "ok": peak_rss <= PEAK_RSS_BUDGET_BYTES},
    ]
    failed = [item for item in checks if not item["ok"]]
    print(json.dumps({
        "ok": not failed,
        "schema": "aibi-million-merge-performance/v1",
        "activeRows": ROW_COUNT,
        "incomingRows": ROW_COUNT,
        "outputRows": int(row_count),
        "columnCount": len(SCHEMA_FIELDS),
        "elapsedMs": round(elapsed_seconds * 1000, 3),
        "budgetMs": int(MERGE_BUDGET_SECONDS * 1000),
        "peakRssBytes": peak_rss,
        "peakRssBudgetBytes": PEAK_RSS_BUDGET_BYTES,
        "activeParquetBytes": active.stat().st_size,
        "incomingParquetBytes": incoming.stat().st_size,
        "mergedParquetBytes": merged.stat().st_size,
        "preview": preview,
        "targetSchemaKeyCast": target_schema_key_cast,
        "emptyKeyPreview": empty_key_preview,
        "algorithmGuard": loop_guard,
        "checks": checks,
        "failedChecks": failed,
    }, indent=2, default=str))
    raise SystemExit(1 if failed else 0)
