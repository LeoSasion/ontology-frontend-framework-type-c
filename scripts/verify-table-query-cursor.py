from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import duckdb  # type: ignore  # noqa: E402

import table_query_tools  # noqa: E402
from dataset_version_store import prepare_dataset_version  # noqa: E402
from query_runtime import ValidatedDuckDBQuery  # noqa: E402


def query_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "tableKey": "orders",
        "sourceVersion": "version-1",
        "expectedRowCount": 6,
        "columns": ["label", "amount"],
        "filters": [],
        "sort": [{"field": "amount", "direction": "asc"}],
        "search": "",
        "limit": 2,
    }
    payload.update(overrides)
    return payload


control = sqlite3.connect(":memory:")
control.row_factory = sqlite3.Row
control.execute(
    "CREATE TABLE table_registry("
    "workspace_id TEXT, table_key TEXT, physical_table TEXT, schema_json TEXT, updated_at TEXT)"
)
control.executemany(
    "INSERT INTO table_registry VALUES('default', ?, ?, ?, '2026-01-01T00:00:00Z')",
    [
        ("orders", "orders", '[{"name":"label","type":"VARCHAR"},{"name":"amount","type":"VARCHAR"}]'),
        ("million_rows", "million_rows", '[{"name":"label","type":"VARCHAR"},{"name":"amount","type":"INTEGER"}]'),
        ("duplicate_business_ids", "duplicate_business_ids", '[{"name":"id","type":"INTEGER"},{"name":"label","type":"VARCHAR"},{"name":"amount","type":"INTEGER"}]'),
    ],
)
duck = duckdb.connect(":memory:")
duck.execute("CREATE TABLE orders(__aibi_row_id BIGINT, id INTEGER, label VARCHAR, amount VARCHAR)")
duck.executemany(
    "INSERT INTO orders VALUES (?, ?, ?, ?)",
    [(1, 1, "one", "1"), (2, 2, "two", "2"), (3, 3, "three", "3"), (4, 4, "four", "4"), (5, 5, "five", "5"), (6, 6, "six", "6")],
)
analysis = ValidatedDuckDBQuery(
    duck,
    [{"logicalTable": "orders", "versionId": "version-1", "objectHashes": ["a" * 64], "rowCount": 6}],
)

first = table_query_tools.build_detail_query(control, analysis, "orders", ["id", "label", "amount"], query_payload())
assert [row["amount"] for row in first["rows"]] == ["1", "2"]
assert first["totalRows"] == 6 and first["filteredRows"] == 6
assert first["nextCursor"] and not first["previousCursor"]
assert "OFFSET" not in first["runtime"]["compiledSql"].upper()

second = table_query_tools.build_detail_query(
    control,
    analysis,
    "orders",
    ["id", "label", "amount"],
    query_payload(cursor=first["nextCursor"]),
)
assert [row["amount"] for row in second["rows"]] == ["3", "4"]
assert second["page"] == 2 and second["nextCursor"] and second["previousCursor"]

previous = table_query_tools.build_detail_query(
    control,
    analysis,
    "orders",
    ["id", "label", "amount"],
    query_payload(cursor=second["previousCursor"]),
)
assert [row["amount"] for row in previous["rows"]] == ["1", "2"]
assert previous["page"] == 1 and not previous["previousCursor"]

filtered = table_query_tools.build_detail_query(
    control,
    analysis,
    "orders",
    ["id", "label", "amount"],
    query_payload(filters=[{"field": "amount", "operator": "gt", "value": "2"}]),
)
assert filtered["filteredRows"] == 4
assert [row["amount"] for row in filtered["rows"]] == ["3", "4"]
assert "COUNT(*) OVER" in filtered["runtime"]["compiledSql"].upper()

try:
    table_query_tools.build_detail_query(
        control,
        analysis,
        "orders",
        ["id", "label", "amount"],
        query_payload(sourceVersion="version-2", cursor=first["nextCursor"]),
    )
except ValueError as error:
    assert str(error) == "detail-query-cursor-stale"
else:
    raise AssertionError("A cursor from another data version must be rejected")

duck.execute(
    "CREATE TABLE duplicate_business_ids("
    "__aibi_row_id BIGINT, id INTEGER, label VARCHAR, amount INTEGER)"
)
duck.executemany(
    "INSERT INTO duplicate_business_ids VALUES (?, ?, ?, ?)",
    [
        (1, 7, "row-1", 1),
        (2, 7, "row-2", 1),
        (3, 7, "row-3", 1),
        (4, 8, "row-4", 1),
        (5, 8, "row-5", 1),
        (6, 8, "row-6", 1),
    ],
)
duplicate_analysis = ValidatedDuckDBQuery(
    duck,
    [{"logicalTable": "duplicate_business_ids", "versionId": "duplicate-v1", "objectHashes": ["c" * 64], "rowCount": 6}],
)
duplicate_payload = query_payload(
    tableKey="duplicate_business_ids",
    sourceVersion="duplicate-v1",
    expectedRowCount=6,
    columns=["id", "label", "amount"],
    sort=[{"field": "amount", "direction": "asc"}],
)
seen_labels: list[str] = []
duplicate_cursor = None
while True:
    duplicate_page = table_query_tools.build_detail_query(
        control,
        duplicate_analysis,
        "duplicate_business_ids",
        ["id", "label", "amount"],
        {**duplicate_payload, **({"cursor": duplicate_cursor} if duplicate_cursor else {})},
    )
    seen_labels.extend(str(row["label"]) for row in duplicate_page["rows"])
    duplicate_cursor = duplicate_page["nextCursor"]
    if not duplicate_cursor:
        break
assert seen_labels == [f"row-{index}" for index in range(1, 7)]

with tempfile.TemporaryDirectory(prefix="aibi-c-row-id-contract-") as raw_temp:
    contract_root = Path(raw_temp)
    invalid_row_ids = {
        "duplicate": [(1, 10), (1, 20), (3, 30)],
        "gap": [(1, 10), (3, 30)],
    }
    for label, rows in invalid_row_ids.items():
        relation = f"invalid_row_ids_{label}"
        parquet_path = contract_root / f"{label}.parquet"
        duck.execute(
            f'CREATE TEMP TABLE "{relation}"(__aibi_row_id BIGINT, value INTEGER)'
        )
        duck.executemany(f'INSERT INTO "{relation}" VALUES (?, ?)', rows)
        duck.execute(
            f"COPY (SELECT * FROM \"{relation}\") TO ? (FORMAT PARQUET)",
            [str(parquet_path)],
        )
        try:
            prepare_dataset_version(
                workspace_id="default",
                table_key=f"invalid_{label}",
                parquet_path=parquet_path,
                schema_fields=[{"name": "value", "type": "INTEGER"}],
                row_count=len(rows),
                source_file="row-id-contract-fixture",
                object_root=contract_root / "objects",
            )
        except ValueError as error:
            assert "stable 1-based sequence" in str(error)
        else:
            raise AssertionError(f"{label} internal row ids must be rejected before CAS publication")

duck.execute(
    "CREATE TABLE million_rows AS "
    "SELECT i::BIGINT AS __aibi_row_id, (i % 100)::INTEGER AS id, "
    "concat('row-', i::VARCHAR) AS label, i::INTEGER AS amount "
    "FROM range(1, 1000001) AS source(i)"
)
million_analysis = ValidatedDuckDBQuery(
    duck,
    [{"logicalTable": "million_rows", "versionId": "million-v1", "objectHashes": ["b" * 64], "rowCount": 1_000_000}],
)
million_payload = {
    "tableKey": "million_rows",
    "sourceVersion": "million-v1",
    "expectedRowCount": 1_000_000,
    "columns": ["label", "amount"],
    "filters": [],
    "sort": [],
    "search": "",
    "limit": 50,
}
million_first = table_query_tools.build_detail_query(
    control,
    million_analysis,
    "million_rows",
    ["id", "label", "amount"],
    million_payload,
)
assert million_first["totalRows"] == 1_000_000
assert [row["amount"] for row in million_first["rows"][:3]] == [1, 2, 3]
assert "OFFSET" not in million_first["runtime"]["compiledSql"].upper()
million_second = table_query_tools.build_detail_query(
    control,
    million_analysis,
    "million_rows",
    ["id", "label", "amount"],
    {**million_payload, "cursor": million_first["nextCursor"]},
)
assert [row["amount"] for row in million_second["rows"][:3]] == [51, 52, 53]
million_filtered = table_query_tools.build_detail_query(
    control,
    million_analysis,
    "million_rows",
    ["id", "label", "amount"],
    {**million_payload, "filters": [{"field": "amount", "operator": "gt", "value": "999990"}]},
)
assert million_filtered["filteredRows"] == 10
assert [row["amount"] for row in million_filtered["rows"]] == list(range(999991, 1_000_001))

original_max_bytes = table_query_tools.DETAIL_RESULT_MAX_BYTES
try:
    table_query_tools.DETAIL_RESULT_MAX_BYTES = 70
    bounded = table_query_tools.build_detail_query(
        control,
        analysis,
        "orders",
        ["id", "label", "amount"],
        query_payload(limit=6),
    )
    assert bounded["truncatedByBytes"] is True
    assert bounded["rowBytes"] <= 70
    assert bounded["responseBytes"] <= table_query_tools.DETAIL_RESPONSE_MAX_BYTES
    assert bounded["nextCursor"]
finally:
    table_query_tools.DETAIL_RESULT_MAX_BYTES = original_max_bytes
    duck.close()
    control.close()

print("table-query-cursor-ok")
