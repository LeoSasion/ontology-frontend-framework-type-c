from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from semantic_query_planner import build_workspace_semantic_plan  # noqa: E402


checks: list[dict[str, Any]] = []


def check(label: str, ok: bool, detail: Any = None) -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": None if ok else detail})


connection = sqlite3.connect(":memory:")
connection.row_factory = sqlite3.Row
connection.executescript(
    """
    CREATE TABLE table_registry(
      workspace_id TEXT,
      table_key TEXT,
      display_name TEXT,
      physical_table TEXT,
      data_version INTEGER,
      schema_json TEXT NOT NULL
    );
    CREATE TABLE field_semantics(
      workspace_id TEXT,
      table_key TEXT,
      field_name TEXT,
      role TEXT,
      confidence REAL
    );
    CREATE TABLE metric_definitions(
      workspace_id TEXT,
      table_key TEXT,
      label TEXT,
      measure TEXT,
      aggregation TEXT,
      dimension TEXT,
      time_field TEXT
    );
    CREATE TABLE relationships(
      workspace_id TEXT,
      relation_key TEXT,
      left_table_key TEXT,
      right_table_key TEXT,
      left_field TEXT,
      right_field TEXT,
      mappings_json TEXT,
      filters_json TEXT,
      preaggregation_json TEXT,
      join_type TEXT,
      confidence REAL,
      validation_json TEXT,
      updated_at TEXT
    );
    CREATE TABLE business_rows(legacy_decoy TEXT);
    INSERT INTO business_rows VALUES('must-not-be-read');
    """
)
connection.execute(
    "INSERT INTO table_registry VALUES(?, ?, ?, ?, ?, ?)",
    (
        "default",
        "orders",
        "Orders",
        "business_rows",
        1,
        json.dumps({"fields": [{"name": "authoritative_field", "type": "VARCHAR"}]}),
    ),
)
connection.execute(
    "INSERT INTO field_semantics VALUES('default', 'orders', 'authoritative_field', 'dimension', 0.99)"
)
connection.commit()

statements: list[str] = []
connection.set_trace_callback(statements.append)
plan = build_workspace_semantic_plan(connection, "default", "按 authoritative_field 查看")
connection.set_trace_callback(None)
connection.close()

selected_fields = {
    str(item.get("field") or "")
    for item in plan.get("fieldResolution", {}).get("selected", [])
    if isinstance(item, dict)
}
serialized_trace = "\n".join(statements).casefold()
check(
    "semantic-planner-uses-sealed-registry-schema",
    "authoritative_field" in selected_fields,
    plan.get("fieldResolution"),
)
check(
    "semantic-planner-never-discovers-sqlite-business-table",
    "pragma table_info" not in serialized_trace and "from \"business_rows\"" not in serialized_trace,
    statements,
)
check(
    "sqlite-only-decoy-field-never-enters-plan",
    "legacy_decoy" not in json.dumps(plan, ensure_ascii=False),
    plan,
)

planner_source = (TOOLS / "semantic_query_planner.py").read_text(encoding="utf-8").casefold()
quality_source = (TOOLS / "plan_quality_service.py").read_text(encoding="utf-8").casefold()
import_policy_source = (TOOLS / "import_policy.py").read_text(encoding="utf-8").casefold()
import_command_source = (TOOLS / "import_command_service.py").read_text(encoding="utf-8").casefold()
import_writer_source = (TOOLS / "import_table_writer_service.py").read_text(encoding="utf-8").casefold()
io_service_source = (TOOLS / "bi_cli_io_services.py").read_text(encoding="utf-8").casefold()
check(
    "semantic-planner-has-no-physical-table-pragma-fallback",
    "pragma table_info" not in planner_source and "sqlite_master" not in planner_source,
)
check(
    "plan-quality-fixture-has-no-sqlite-business-row-storage",
    not any(
        token in quality_source
        for token in (
            "create table sites(",
            "create table assets(",
            "create table observations(",
            "create table other_private(",
            "insert into sites values",
            "insert into assets values",
            "insert into observations values",
            "insert into other_private values",
        )
    ),
)
check(
    "import-policy-has-no-row-at-a-time-sqlite-merge",
    not any(
        token in import_policy_source
        for token in (
            "def existing_rows_by_unique_key(",
            "def preview_merge_plan(",
            "rowid as _rowid",
            "coalesce(cast({column_sql} as text)",
        )
    )
    and "def preview_merge_plan_parquet(" in import_policy_source,
)
check(
    "import-preview-has-no-discarded-v1-dependencies",
    "del read_table_file" not in import_command_source
    and "normalize_records_for_columns:" not in import_command_source
    and "preview_merge_plan:" not in import_command_source,
)
check(
    "import-writer-exposes-only-parquet-stage-api",
    "read_import_stage:" not in import_writer_source
    and "read_table_file:" not in import_writer_source
    and "profile_rows:" not in import_writer_source
    and "preview_merge_plan_parquet(" in import_writer_source,
)
check(
    "production-import-io-has-no-materialized-row-reader",
    "def read_table_file(" not in io_service_source
    and "def profile_rows(" not in io_service_source
    and "max_test_helper_rows" not in io_service_source,
)

failed = [item for item in checks if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-clean-break-semantic-storage-verify/v1",
    "generatedBy": "scripts/verify-clean-break-semantic-storage.py",
    "checks": checks,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
