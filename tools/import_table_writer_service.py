from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Callable

from bi_cli_core import now_iso, quote_identifier, slug, source_label, unique_key
from import_policy import (
    existing_rows_by_unique_key,
    normalize_records_for_columns,
    preview_merge_plan,
    record_unique_key,
    sanitize_unique_fields,
)


def should_create_metric_for_measure(measure: str) -> bool:
    text = str(measure or "").strip()
    return bool(text) and not text.startswith("__")


def default_metric_dimension(profile: dict[str, Any]) -> str | None:
    return next((dimension for dimension in profile["dimensions"] if not str(dimension).startswith("__")), None)


def create_metrics_for_profile(
    connection: sqlite3.Connection,
    table_key: str,
    profile: dict[str, Any],
    *,
    workspace_id: str,
) -> None:
    dimension = default_metric_dimension(profile)
    time_field = next((field["field"] for field in profile["fields"] if field["role"] == "event_time"), None)
    allowed_measures = [measure for measure in profile["measures"] if should_create_metric_for_measure(measure)]
    for measure in allowed_measures[:4]:
        metric_key = f"{table_key}_{slug(measure)}_sum"
        connection.execute(
            """
            INSERT OR REPLACE INTO metric_definitions(metric_key, workspace_id, label, table_key, measure, aggregation, dimension, time_field, value_format, created_at)
            VALUES(?, ?, ?, ?, ?, 'sum', ?, ?, 'auto', ?)
            """,
            (metric_key, workspace_id, f"{measure} 合计", table_key, measure, dimension, time_field, now_iso()),
        )
    connection.execute(
        """
        INSERT OR REPLACE INTO metric_definitions(metric_key, workspace_id, label, table_key, measure, aggregation, dimension, time_field, value_format, created_at)
        VALUES(?, ?, ?, ?, '*', 'count', ?, ?, 'compact', ?)
        """,
        (f"{table_key}_row_count", workspace_id, "记录数", table_key, dimension, time_field, now_iso()),
    )


def import_csv_as_table(
    connection: sqlite3.Connection,
    path: Path,
    *,
    table_key: str | None = None,
    display_name: str | None = None,
    mode: str = "create",
    read_table_file: Callable[[Path], tuple[list[str], list[dict[str, Any]]]],
    profile_rows: Callable[[list[str], list[dict[str, Any]]], dict[str, Any]],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    physical_table_for_workspace: Callable[[str, str], str],
    upsert_navigation_module: Callable[..., None],
) -> dict[str, Any]:
    headers, rows = read_table_file(path)
    if not headers:
        raise ValueError(f"No headers found in {path}")
    table_key = table_key or slug(path.stem)
    display_name = display_name or path.stem
    workspace_id = active_workspace_id(connection)
    physical_table = physical_table_for_workspace(workspace_id, table_key)
    profile = profile_rows(headers, rows)

    connection.execute(f"DROP TABLE IF EXISTS {quote_identifier(physical_table)}")
    column_sql = ", ".join(f"{quote_identifier(header)} TEXT" for header in headers)
    connection.execute(f"CREATE TABLE {quote_identifier(physical_table)} ({column_sql})")
    placeholders = ", ".join("?" for _ in headers)
    insert_sql = f"INSERT INTO {quote_identifier(physical_table)} ({', '.join(quote_identifier(h) for h in headers)}) VALUES ({placeholders})"
    connection.executemany(insert_sql, [[str(row.get(header, "")) for header in headers] for row in rows])

    display_source = source_label(path)
    connection.execute(
        """
        INSERT OR REPLACE INTO table_registry(table_key, workspace_id, display_name, physical_table, source_file, row_count, column_count, created_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (table_key, workspace_id, display_name, physical_table, display_source, len(rows), len(headers), now_iso()),
    )
    source_run_id = unique_key(f"source_run_{table_key}")
    evidence = [
        "source-profile",
        "field-semantics",
        "metric-sql-plan",
        "query-runtime",
        "dashboard-ready",
    ]
    connection.execute(
        """
        INSERT OR REPLACE INTO source_runs(id, workspace_id, table_key, name, status, source_file, row_count, column_count, profile_json, evidence_json, created_at)
        VALUES(?, ?, ?, ?, 'ready', ?, ?, ?, ?, ?, ?)
        """,
        (source_run_id, workspace_id, table_key, display_name, display_source, len(rows), len(headers), json.dumps(profile, ensure_ascii=False), json.dumps(evidence, ensure_ascii=False), now_iso()),
    )
    for field in profile["fields"]:
        connection.execute(
            """
            INSERT OR REPLACE INTO field_semantics(workspace_id, table_key, field_name, role, usage, confidence)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (workspace_id, table_key, field["field"], field["role"], field["usage"], field["confidence"]),
        )
    create_metrics_for_profile(connection, table_key, profile, workspace_id=workspace_id)
    upsert_navigation_module(
        connection,
        module_key=f"table:{table_key}",
        name=display_name,
        module_type="table",
        table_key=table_key,
        created_by="manual",
        agent_managed=1,
    )
    connection.execute("UPDATE workspaces SET current_source_run_id = ? WHERE id = ?", (source_run_id, workspace_id))
    connection.execute(
        """
        INSERT OR REPLACE INTO import_jobs(job_key, workspace_id, source_file, table_key, mode, status, row_count, result_json, created_at)
        VALUES(?, ?, ?, ?, ?, 'success', ?, ?, ?)
        """,
        (unique_key(f"import_{table_key}"), workspace_id, display_source, table_key, mode, len(rows), json.dumps({"profile": profile}, ensure_ascii=False), now_iso()),
    )
    return {
        "tableKey": table_key,
        "displayName": display_name,
        "sourceRunId": source_run_id,
        "profile": profile,
    }


def update_table_metadata_after_write(
    connection: sqlite3.Connection,
    *,
    table_key: str,
    display_name: str,
    source_file: str,
    physical_table: str,
    row_count: int,
    column_count: int,
    profile: dict[str, Any],
    mode: str,
    result: dict[str, Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> str:
    workspace_id = active_workspace_id(connection)
    connection.execute(
        """
        INSERT OR REPLACE INTO table_registry(table_key, workspace_id, display_name, physical_table, source_file, row_count, column_count, created_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (table_key, workspace_id, display_name, physical_table, source_file, row_count, column_count, now_iso()),
    )
    source_run_id = unique_key(f"source_run_{table_key}")
    evidence = [
        "source-profile-generic.json",
        "semantic-field-candidates.json",
        "relationship-discovery.json",
        "metric-sql-compiler.json",
        "metric-query-results.json",
    ]
    connection.execute(
        """
        INSERT OR REPLACE INTO source_runs(id, workspace_id, table_key, name, status, source_file, row_count, column_count, profile_json, evidence_json, created_at)
        VALUES(?, ?, ?, ?, 'ready', ?, ?, ?, ?, ?, ?)
        """,
        (source_run_id, workspace_id, table_key, display_name, source_file, row_count, column_count, json.dumps(profile, ensure_ascii=False), json.dumps(evidence, ensure_ascii=False), now_iso()),
    )
    for field in profile["fields"]:
        connection.execute(
            """
            INSERT OR REPLACE INTO field_semantics(workspace_id, table_key, field_name, role, usage, confidence)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (workspace_id, table_key, field["field"], field["role"], field["usage"], field["confidence"]),
        )
    create_metrics_for_profile(connection, table_key, profile, workspace_id=workspace_id)
    connection.execute("UPDATE workspaces SET current_source_run_id = ? WHERE id = ?", (source_run_id, workspace_id))
    connection.execute(
        """
        INSERT OR REPLACE INTO import_jobs(job_key, workspace_id, source_file, table_key, mode, status, row_count, result_json, created_at)
        VALUES(?, ?, ?, ?, ?, 'success', ?, ?, ?)
        """,
        (unique_key(f"import_{table_key}"), workspace_id, source_file, table_key, mode, row_count, json.dumps(result, ensure_ascii=False), now_iso()),
    )
    return source_run_id


def merge_import_into_table(
    connection: sqlite3.Connection,
    path: Path,
    *,
    table_key: str,
    unique_fields: list[str],
    conflict_rule: str,
    display_name: str | None = None,
    registry_for_table: Callable[[sqlite3.Connection, str], sqlite3.Row | None],
    read_table_file: Callable[[Path], tuple[list[str], list[dict[str, Any]]]],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    profile_rows: Callable[[list[str], list[dict[str, Any]]], dict[str, Any]],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    registry = registry_for_table(connection, table_key)
    if not registry:
        raise ValueError(f"Unknown table for merge: {table_key}")
    headers, raw_rows = read_table_file(path)
    physical_table = registry["physical_table"]
    existing_columns = table_columns(connection, physical_table)
    if set(headers) != set(existing_columns):
        raise ValueError("导入文件字段与目标表不匹配，已取消合并。")
    columns = [column for column in existing_columns if column in headers]
    selected_unique_fields = sanitize_unique_fields(unique_fields, columns, allow_empty=False)
    records = normalize_records_for_columns(raw_rows, columns)
    plan = preview_merge_plan(connection, physical_table, columns, records, selected_unique_fields, conflict_rule, quote_identifier)
    existing_map = existing_rows_by_unique_key(connection, physical_table, columns, records, selected_unique_fields, quote_identifier)
    insert_columns_sql = ", ".join(quote_identifier(column) for column in columns)
    placeholders = ", ".join("?" for _ in columns)
    insert_sql = f"INSERT INTO {quote_identifier(physical_table)} ({insert_columns_sql}) VALUES ({placeholders})"
    update_columns = [column for column in columns if column not in selected_unique_fields]
    update_sql = (
        f"UPDATE {quote_identifier(physical_table)} SET "
        + ", ".join(f"{quote_identifier(column)} = ?" for column in update_columns)
        + " WHERE rowid = ?"
    ) if update_columns else ""
    inserted = 0
    updated = 0
    skipped = 0
    seen_keys: set[str] = set()
    for record in records:
        key = record_unique_key(record, selected_unique_fields)
        if key is None or key in seen_keys:
            skipped += 1
            continue
        seen_keys.add(key)
        existing = existing_map.get(key)
        if existing:
            if conflict_rule == "skip-existing":
                skipped += 1
                continue
            if conflict_rule == "fill-empty":
                changed_columns = [
                    column
                    for column in update_columns
                    if str(existing.get(column) or "").strip() == "" and str(record.get(column) or "").strip() != ""
                ]
                if not changed_columns:
                    skipped += 1
                    continue
                set_sql = ", ".join(f"{quote_identifier(column)} = ?" for column in changed_columns)
                connection.execute(
                    f"UPDATE {quote_identifier(physical_table)} SET {set_sql} WHERE rowid = ?",
                    [record.get(column, "") for column in changed_columns] + [existing["_rowid"]],
                )
            elif update_sql:
                connection.execute(update_sql, [record.get(column, "") for column in update_columns] + [existing["_rowid"]])
            updated += 1
        else:
            connection.execute(insert_sql, [record.get(column, "") for column in columns])
            inserted += 1
    row_count = connection.execute(f"SELECT COUNT(*) FROM {quote_identifier(physical_table)}").fetchone()[0]
    profile = profile_rows(columns, [dict(row) for row in connection.execute(f"SELECT {insert_columns_sql} FROM {quote_identifier(physical_table)}")])
    result = {
        "tableKey": table_key,
        "displayName": display_name or registry["display_name"],
        "sourceRunId": "",
        "profile": profile,
        "mergePlan": plan,
        "writeSummary": {
            "insertedRows": inserted,
            "updatedRows": updated,
            "skippedRows": skipped,
            "rowCountAfter": row_count,
            "uniqueFields": selected_unique_fields,
            "conflictRule": conflict_rule,
        },
    }
    source_run_id = update_table_metadata_after_write(
        connection,
        table_key=table_key,
        display_name=display_name or registry["display_name"],
        source_file=source_label(path),
        physical_table=physical_table,
        row_count=row_count,
        column_count=len(columns),
        profile=profile,
        mode="merge",
        result=result,
        active_workspace_id=active_workspace_id,
    )
    result["sourceRunId"] = source_run_id
    return result
