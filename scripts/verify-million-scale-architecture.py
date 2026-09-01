from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def main() -> int:
    checks: list[dict[str, object]] = []

    def check(label: str, condition: bool, detail: object = None) -> None:
        checks.append({"label": label, "ok": bool(condition), "detail": detail if not condition else None})

    core = source("tools/bi_cli_core.py")
    query_runtime = source("tools/query_runtime.py")
    stage = source("tools/import_stage_service.py")
    writer = source("tools/import_table_writer_service.py")
    table_query = source("tools/table_query_tools.py")
    sqlserver_snapshot = source("tools/sqlserver_snapshot_adapter_service.py")
    package = json.loads(source("package.json"))
    version_store_path = ROOT / "tools" / "dataset_version_store.py"
    version_store = version_store_path.read_text(encoding="utf-8") if version_store_path.exists() else ""

    check(
        "storage-generation-2-defaults-are-isolated",
        "aibi_control_v2.sqlite" in core and "aibi_catalog_v2.duckdb" in core,
    )
    check(
        "query-validation-does-not-scan-replica-content",
        "physical_count" not in query_runtime
        and "view_count" not in query_runtime
        and "SELECT COUNT(*) FROM {quote_identifier(replica_table)}" not in query_runtime,
    )
    check(
        "dataset-publication-validates-cas-binding",
        "resolve_object_key(object_key" in query_runtime
        and "dataset-object-path-mismatch" in query_runtime
        and "file_sha256(canonical_path)" in query_runtime,
    )
    check(
        "sqlite-to-duckdb-row-copy-is-removed",
        "def sqlite_rows(" not in query_runtime and "def sync_table_to_duckdb(" not in query_runtime,
    )
    check(
        "import-stage-is-parquet-not-sqlite",
        ".sqlite" not in stage and "sqlite3" not in stage and ".parquet" in stage,
    )
    check(
        "business-writer-is-set-based",
        "executemany(" not in writer and "WHERE rowid" not in writer and "DROP TABLE IF EXISTS {quote_identifier(physical_table)}" not in writer,
    )
    check(
        "detail-pagination-has-no-offset-sql",
        " OFFSET " not in table_query.upper(),
    )
    check(
        "query-hot-path-uses-sealed-types",
        "LIMIT 80" not in table_query
        and "def is_numeric_column(" not in table_query
        and "SELECT COUNT(*) FROM {table_sql}{where}" not in table_query,
    )
    check(
        "sqlserver-snapshot-is-batched-parquet",
        "iter_snapshot_batches" in sqlserver_snapshot
        and "FORMAT PARQUET" in sqlserver_snapshot
        and "writerow" not in sqlserver_snapshot
        and "import csv" not in sqlserver_snapshot,
    )
    check(
        "version-store-is-immutable-and-columnar",
        bool(version_store)
        and "dataset_versions" in version_store
        and "dataset_version_files" in version_store
        and "parquet" in version_store.casefold()
        and "content_fingerprint" in version_store,
    )
    check(
        "legacy-storage-migration-is-removed",
        not (ROOT / "scripts" / "migrate-local-data.mjs").exists()
        and not (ROOT / "scripts" / "verify-local-migration.mjs").exists()
        and "migrate:local" not in package.get("scripts", {})
        and "verify:migration" not in package.get("scripts", {}),
    )

    failed = [item for item in checks if not item["ok"]]
    print(json.dumps({
        "ok": not failed,
        "schema": "aibi-million-scale-architecture-verify/v1",
        "generatedBy": "scripts/verify-million-scale-architecture.py",
        "checks": [{"label": item["label"], "ok": item["ok"]} for item in checks],
        "failedChecks": failed,
    }, ensure_ascii=False, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
