from __future__ import annotations

"""Set-based Parquet writer for the AIBI-C v2 data plane.

SQLite stores control metadata only. Every create, replace, and merge prepares an
immutable Parquet dataset version for the import runtime to publish through the
single DuckDB catalogue boundary.
"""

import json
import re
import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable, Mapping

from bi_cli_core import now_iso, slug, source_label, unique_key
from dataset_version_store import (
    INTERNAL_ROW_ID,
    active_dataset_version,
    duckdb_parquet_relation,
    prepare_dataset_version,
    publish_dataset_version,
    resolve_dataset_object_paths,
    schema_columns,
)
from import_policy import preview_merge_plan_parquet, sanitize_unique_fields
from import_stage_service import create_import_stage, profile_parquet, resolve_import_stage_parquet
from relationship_command_service import relationship_record_payload


def _duckdb() -> Any:
    try:
        import duckdb  # type: ignore
    except ImportError as error:  # pragma: no cover - deployment contract
        raise RuntimeError("DuckDB is required for set-based imports.") from error
    return duckdb


def _quote_identifier(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _sql_literal(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _normalized_key(alias: str, field: str) -> str:
    return f"trim(COALESCE(CAST({alias}.{_quote_identifier(field)} AS VARCHAR), ''))"


def _safe_type(value: str) -> str:
    data_type = str(value or "VARCHAR").strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*(?:\([0-9 ,]+\))?(?:\[\])?", data_type):
        raise ValueError(f"Dataset schema contains an unsafe DuckDB type: {value}")
    return data_type


def _version_with_private_paths(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        **dict(manifest),
        "_internalObjectPaths": [str(path) for path in resolve_dataset_object_paths(manifest)],
    }


def _safe_for_persistence(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _safe_for_persistence(item)
            for key, item in value.items()
            if not str(key).startswith("_internal")
        }
    if isinstance(value, list):
        return [_safe_for_persistence(item) for item in value]
    return value


def should_create_metric_for_measure(measure: str) -> bool:
    text = str(measure or "").strip()
    return bool(text) and not text.startswith("__")


def default_metric_dimension(profile: dict[str, Any]) -> str | None:
    return next((dimension for dimension in profile.get("dimensions") or [] if not str(dimension).startswith("__")), None)


def upsert_table_registry_record(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    table_key: str,
    display_name: str,
    physical_table: str,
    source_file: str,
    row_count: int,
    column_count: int,
) -> int:
    """Update logical metadata only; activation fields switch after view publication."""

    current = connection.execute(
        "SELECT created_at, data_version FROM table_registry WHERE workspace_id = ? AND table_key = ?",
        (workspace_id, table_key),
    ).fetchone()
    timestamp = now_iso()
    created_at = str(current["created_at"]) if current else timestamp
    data_version = int(current["data_version"] or 1) + 1 if current else 1
    connection.execute(
        """
        INSERT INTO table_registry(
          table_key, workspace_id, display_name, physical_table, source_file, row_count, column_count,
          created_at, data_version, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(workspace_id, table_key) DO UPDATE SET
          display_name = excluded.display_name,
          physical_table = excluded.physical_table,
          source_file = excluded.source_file,
          row_count = excluded.row_count,
          column_count = excluded.column_count,
          data_version = excluded.data_version,
          updated_at = excluded.updated_at
        """,
        (
            table_key,
            workspace_id,
            display_name,
            physical_table,
            source_file,
            int(row_count),
            int(column_count),
            created_at,
            data_version,
            timestamp,
        ),
    )
    return data_version


def revalidate_relationships_for_table(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    table_key: str,
) -> list[dict[str, Any]]:
    """Fence relationship validation until the new DuckDB view is published."""

    relationships = connection.execute(
        """
        SELECT * FROM relationships
        WHERE workspace_id = ? AND (left_table_key = ? OR right_table_key = ?)
        ORDER BY relation_key
        """,
        (workspace_id, table_key, table_key),
    ).fetchall()
    receipts: list[dict[str, Any]] = []
    for relationship in relationships:
        payload = relationship_record_payload(relationship)
        previous = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
        blocker = "revalidation-pending-dataset-publish"
        validation = {
            **previous,
            "schema": "aibi-relationship-validation/v1",
            "status": "stale",
            "blockers": list(dict.fromkeys([*(previous.get("blockers") or []), blocker])),
            "staleReason": blocker,
            "revalidatedAfterImport": table_key,
            "validatedAt": now_iso(),
        }
        connection.execute(
            "UPDATE relationships SET validation_json = ?, updated_at = ? WHERE workspace_id = ? AND relation_key = ?",
            (json.dumps(validation, ensure_ascii=False), now_iso(), workspace_id, relationship["relation_key"]),
        )
        receipts.append({
            "relationKey": relationship["relation_key"],
            "status": "stale",
            "blockers": validation["blockers"],
        })
    return receipts


def create_metrics_for_profile(
    connection: sqlite3.Connection,
    table_key: str,
    profile: dict[str, Any],
    *,
    workspace_id: str,
) -> None:
    dimension = default_metric_dimension(profile)
    time_field = next(
        (field["field"] for field in profile.get("fields") or [] if field.get("role") == "event_time"),
        None,
    )
    allowed_measures = [
        measure for measure in profile.get("measures") or [] if should_create_metric_for_measure(measure)
    ]
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
    workspace_id: str | None = None,
) -> str:
    resolved_workspace_id = str(workspace_id or active_workspace_id(connection))
    data_version = upsert_table_registry_record(
        connection,
        workspace_id=resolved_workspace_id,
        table_key=table_key,
        display_name=display_name,
        physical_table=physical_table,
        source_file=source_file,
        row_count=row_count,
        column_count=column_count,
    )
    relationship_revalidations = revalidate_relationships_for_table(
        connection,
        workspace_id=resolved_workspace_id,
        table_key=table_key,
    )
    result["dataVersion"] = data_version
    result["relationshipRevalidations"] = relationship_revalidations
    source_run_id = unique_key(f"source_run_{table_key}")
    evidence = [
        "source-profile-parquet-v2.json",
        "semantic-field-candidates.json",
        "dataset-version-manifest.json",
        "duckdb-view-publication-pending.json",
    ]
    connection.execute(
        """
        INSERT OR REPLACE INTO source_runs(id, workspace_id, table_key, name, status, source_file, row_count, column_count, profile_json, evidence_json, created_at)
        VALUES(?, ?, ?, ?, 'ready', ?, ?, ?, ?, ?, ?)
        """,
        (
            source_run_id,
            resolved_workspace_id,
            table_key,
            display_name,
            source_file,
            int(row_count),
            int(column_count),
            json.dumps(profile, ensure_ascii=False, default=str),
            json.dumps(evidence, ensure_ascii=False),
            now_iso(),
        ),
    )
    for field in profile.get("fields") or []:
        if str(field.get("field") or "").startswith("__aibi_"):
            continue
        connection.execute(
            """
            INSERT OR REPLACE INTO field_semantics(workspace_id, table_key, field_name, role, usage, confidence)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_workspace_id,
                table_key,
                field["field"],
                field["role"],
                field["usage"],
                field["confidence"],
            ),
        )
    create_metrics_for_profile(connection, table_key, profile, workspace_id=resolved_workspace_id)
    connection.execute(
        "UPDATE workspaces SET current_source_run_id = ? WHERE id = ?",
        (source_run_id, resolved_workspace_id),
    )
    connection.execute(
        """
        INSERT OR REPLACE INTO import_jobs(job_key, workspace_id, source_file, table_key, mode, status, row_count, result_json, created_at)
        VALUES(?, ?, ?, ?, ?, 'success', ?, ?, ?)
        """,
        (
            unique_key(f"import_{table_key}"),
            resolved_workspace_id,
            source_file,
            table_key,
            mode,
            int(row_count),
            json.dumps(_safe_for_persistence(result), ensure_ascii=False, default=str),
            now_iso(),
        ),
    )
    return source_run_id


def _stage_for_write(path: Path, workspace_id: str, stage_key: str | None) -> tuple[Path, dict[str, Any]]:
    if stage_key:
        return resolve_import_stage_parquet(stage_key=stage_key, workspace_id=workspace_id)
    stage = create_import_stage(source_path=path, workspace_id=workspace_id)
    return resolve_import_stage_parquet(stage_key=str(stage["stageKey"]), workspace_id=workspace_id)


def import_csv_as_table(
    connection: sqlite3.Connection,
    path: Path,
    *,
    table_key: str | None = None,
    display_name: str | None = None,
    mode: str = "create",
    workspace_id: str | None = None,
    stage_key: str | None = None,
    active_workspace_id: Callable[[sqlite3.Connection], str],
    physical_table_for_workspace: Callable[[str, str], str],
    upsert_navigation_module: Callable[..., None],
) -> dict[str, Any]:
    resolved_workspace_id = str(workspace_id or active_workspace_id(connection))
    parquet_path, stage = _stage_for_write(Path(path), resolved_workspace_id, stage_key)
    resolved_table_key = str(table_key or slug(path.stem))
    resolved_display_name = str(display_name or path.stem)
    physical_table = physical_table_for_workspace(resolved_workspace_id, resolved_table_key)
    display_source = source_label(path)
    current = connection.execute(
        "SELECT row_count FROM table_registry WHERE workspace_id = ? AND table_key = ?",
        (resolved_workspace_id, resolved_table_key),
    ).fetchone()
    before_rows = int(current["row_count"] or 0) if current else 0
    prepared = prepare_dataset_version(
        workspace_id=resolved_workspace_id,
        table_key=resolved_table_key,
        parquet_path=parquet_path,
        schema_fields=list(stage["schemaFields"]),
        row_count=int(stage["rowCount"]),
        source_file=display_source,
    )
    published = publish_dataset_version(connection, prepared)
    dataset_version = _version_with_private_paths(published)
    profile = dict(stage["profile"])
    result: dict[str, Any] = {
        "tableKey": resolved_table_key,
        "displayName": resolved_display_name,
        "workspaceId": resolved_workspace_id,
        "mode": mode,
        "rowCount": int(stage["rowCount"]),
        "profile": profile,
        "datasetVersion": dataset_version,
        "writeSummary": {
            "beforeRows": before_rows,
            "incomingRows": int(stage["rowCount"]),
            "insertedRows": int(stage["rowCount"]),
            "updatedRows": 0,
            "skippedRows": 0,
            "afterRows": int(stage["rowCount"]),
            "writeMode": "duckdb-parquet-set-based",
        },
    }
    source_run_id = update_table_metadata_after_write(
        connection,
        table_key=resolved_table_key,
        display_name=resolved_display_name,
        source_file=display_source,
        physical_table=physical_table,
        row_count=int(stage["rowCount"]),
        column_count=int(stage["columnCount"]),
        profile=profile,
        mode=mode,
        result=result,
        active_workspace_id=active_workspace_id,
        workspace_id=resolved_workspace_id,
    )
    result["sourceRunId"] = source_run_id
    upsert_navigation_module(
        connection,
        module_key=f"table:{resolved_table_key}",
        name=resolved_display_name,
        module_type="table",
        table_key=resolved_table_key,
        created_by="manual",
        agent_managed=1,
        workspace_id=resolved_workspace_id,
    )
    return result


def _materialize_merge_parquet(
    *,
    active_paths: list[Path],
    incoming_path: Path,
    schema_fields: list[dict[str, str]],
    unique_fields: list[str],
    conflict_rule: str,
    destination: Path,
) -> None:
    columns = [str(field["name"]) for field in schema_fields]
    types = {str(field["name"]): _safe_type(str(field["type"])) for field in schema_fields}
    active_relation = duckdb_parquet_relation(active_paths)
    incoming_relation = f"read_parquet({_sql_literal(incoming_path.resolve())})"
    connection = _duckdb().connect(":memory:")
    try:
        validation_columns = []
        for index, column in enumerate(columns):
            quoted = _quote_identifier(column)
            validation_columns.append(
                "SUM(CASE WHEN "
                f"incoming.{quoted} IS NOT NULL "
                f"AND trim(CAST(incoming.{quoted} AS VARCHAR)) <> '' "
                f"AND TRY_CAST(incoming.{quoted} AS {types[column]}) IS NULL "
                f"THEN 1 ELSE 0 END)::BIGINT AS invalid_{index}"
            )
        invalid_counts = connection.execute(
            f"SELECT {', '.join(validation_columns)} FROM {incoming_relation} AS incoming"
        ).fetchone()
        invalid_fields = [
            column
            for index, column in enumerate(columns)
            if int(invalid_counts[index] or 0) > 0
        ]
        if invalid_fields:
            raise ValueError(f"Incoming values cannot be cast to the active schema: {', '.join(invalid_fields[:20])}")

        cast_columns = ", ".join(
            f"TRY_CAST(incoming.{_quote_identifier(column)} AS {types[column]}) AS {_quote_identifier(column)}"
            for column in columns
        )
        incoming_keys = [_normalized_key("incoming", field) for field in unique_fields]
        active_keys = [_normalized_key("active", field) for field in unique_fields]
        all_empty = " AND ".join(f"({value} = '')" for value in incoming_keys)
        partition = ", ".join(incoming_keys)
        match = " AND ".join(f"{left} = {right}" for left, right in zip(active_keys, incoming_keys))
        if conflict_rule == "overwrite":
            existing_columns = ", ".join(
                f"CASE WHEN incoming.{_quote_identifier(INTERNAL_ROW_ID)} IS NOT NULL "
                f"THEN incoming.{_quote_identifier(column)} ELSE active.{_quote_identifier(column)} END "
                f"AS {_quote_identifier(column)}"
                for column in columns
            )
        elif conflict_rule == "fill-empty":
            existing_columns = ", ".join(
                (
                    f"CASE WHEN {_normalized_key('active', column)} = '' "
                    f"AND {_normalized_key('incoming', column)} <> '' "
                    f"THEN incoming.{_quote_identifier(column)} ELSE active.{_quote_identifier(column)} END "
                    f"AS {_quote_identifier(column)}"
                )
                for column in columns
            )
        else:
            existing_columns = ", ".join(
                f"active.{_quote_identifier(column)} AS {_quote_identifier(column)}" for column in columns
            )
        public_columns = ", ".join(_quote_identifier(column) for column in columns)
        incoming_public = ", ".join(f"incoming.{_quote_identifier(column)}" for column in columns)
        connection.execute(
            f"""
            COPY (
              WITH incoming_cast AS (
                SELECT incoming.{_quote_identifier(INTERNAL_ROW_ID)}, {cast_columns}
                FROM {incoming_relation} AS incoming
              ), incoming_ranked AS (
                SELECT incoming.*,
                  ROW_NUMBER() OVER (
                    PARTITION BY {partition}
                    ORDER BY incoming.{_quote_identifier(INTERNAL_ROW_ID)}
                  ) AS __dedupe_rank,
                  ({all_empty}) AS __empty_key
                FROM incoming_cast AS incoming
              ), incoming_dedup AS (
                SELECT * FROM incoming_ranked WHERE NOT __empty_key AND __dedupe_rank = 1
              ), existing_output AS (
                SELECT 0 AS __bucket,
                       active.{_quote_identifier(INTERNAL_ROW_ID)} AS __source_row_id,
                       {existing_columns}
                FROM {active_relation} AS active
                LEFT JOIN incoming_dedup AS incoming ON {match}
              ), new_output AS (
                SELECT 1 AS __bucket,
                       incoming.{_quote_identifier(INTERNAL_ROW_ID)} AS __source_row_id,
                       {incoming_public}
                FROM incoming_dedup AS incoming
                LEFT JOIN {active_relation} AS active ON {match}
                WHERE active.{_quote_identifier(INTERNAL_ROW_ID)} IS NULL
              ), combined AS (
                SELECT * FROM existing_output
                UNION ALL
                SELECT * FROM new_output
              )
              SELECT
                CAST(ROW_NUMBER() OVER (ORDER BY __bucket, __source_row_id) AS BIGINT) AS {_quote_identifier(INTERNAL_ROW_ID)},
                {public_columns}
              FROM combined
              ORDER BY {_quote_identifier(INTERNAL_ROW_ID)}
            ) TO {_sql_literal(destination)}
            (FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 122880)
            """
        )
    finally:
        connection.close()


def merge_import_into_table(
    connection: sqlite3.Connection,
    path: Path,
    *,
    table_key: str,
    unique_fields: list[str],
    conflict_rule: str,
    display_name: str | None = None,
    workspace_id: str | None = None,
    stage_key: str | None = None,
    registry_for_table: Callable[..., sqlite3.Row | None],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    resolved_workspace_id = str(workspace_id or active_workspace_id(connection))
    registry = registry_for_table(connection, table_key, workspace_id=resolved_workspace_id)
    if not registry:
        raise ValueError(f"Unknown table for merge: {table_key}")
    active = active_dataset_version(connection, resolved_workspace_id, table_key)
    if active is None:
        raise ValueError("Target table has no active Parquet dataset version.")
    active_paths = resolve_dataset_object_paths(active)
    incoming_path, stage = _stage_for_write(Path(path), resolved_workspace_id, stage_key)
    existing_columns = schema_columns(active.get("schemaFields"))
    incoming_columns = [str(field["name"]) for field in stage["schemaFields"]]
    if set(incoming_columns) != set(existing_columns):
        raise ValueError("导入文件字段与目标表不匹配，已取消合并。")
    selected_unique_fields = sanitize_unique_fields(unique_fields, existing_columns, allow_empty=False)
    schema_by_name = {str(field["name"]): str(field["type"]) for field in active["schemaFields"]}
    schema_fields = [{"name": column, "type": schema_by_name[column]} for column in existing_columns]
    plan = preview_merge_plan_parquet(
        active_paths=active_paths,
        incoming_path=incoming_path,
        schema_fields=schema_fields,
        unique_fields=selected_unique_fields,
        conflict_rule=conflict_rule,
    )
    with TemporaryDirectory(prefix="aibi-merge-v2-") as temporary:
        merged_path = Path(temporary) / "merged.parquet"
        _materialize_merge_parquet(
            active_paths=active_paths,
            incoming_path=incoming_path,
            schema_fields=schema_fields,
            unique_fields=selected_unique_fields,
            conflict_rule=conflict_rule,
            destination=merged_path,
        )
        profile = profile_parquet(merged_path)
        if int(profile["rowCount"]) != int(plan["afterRowsEstimate"]):
            raise RuntimeError("Set-based merge row count does not match its preview.")
        display_source = source_label(path)
        prepared = prepare_dataset_version(
            workspace_id=resolved_workspace_id,
            table_key=table_key,
            parquet_path=merged_path,
            schema_fields=schema_fields,
            row_count=int(profile["rowCount"]),
            source_file=display_source,
        )
    published = publish_dataset_version(connection, prepared)
    dataset_version = _version_with_private_paths(published)
    resolved_display_name = str(display_name or registry["display_name"])
    result: dict[str, Any] = {
        "tableKey": table_key,
        "displayName": resolved_display_name,
        "workspaceId": resolved_workspace_id,
        "mode": "merge",
        "rowCount": int(profile["rowCount"]),
        "profile": profile,
        "datasetVersion": dataset_version,
        "uniqueFields": selected_unique_fields,
        "conflictRule": conflict_rule,
        "mergePlan": plan,
        "writeSummary": {
            "beforeRows": int(plan["beforeRows"]),
            "incomingRows": int(plan["incomingRows"]),
            "insertedRows": int(plan["insertRows"]),
            "updatedRows": int(plan["updateRows"]),
            "skippedRows": int(plan["skipRows"]),
            "afterRows": int(plan["afterRowsEstimate"]),
            "writeMode": "duckdb-parquet-set-based",
        },
    }
    source_run_id = update_table_metadata_after_write(
        connection,
        table_key=table_key,
        display_name=resolved_display_name,
        source_file=display_source,
        physical_table=str(registry["physical_table"]),
        row_count=int(profile["rowCount"]),
        column_count=len(existing_columns),
        profile=profile,
        mode="merge",
        result=result,
        active_workspace_id=active_workspace_id,
        workspace_id=resolved_workspace_id,
    )
    result["sourceRunId"] = source_run_id
    return result
