from __future__ import annotations

import argparse
import json
import sqlite3
from typing import Any, Callable

from bi_cli_core import now_iso, parse_csv_list, source_label


def set_import_policy_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    registry_for_table: Callable[[sqlite3.Connection, str], sqlite3.Row | None],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    sanitize_unique_fields: Callable[..., list[str]],
    saved_import_policy: Callable[[sqlite3.Connection, str], dict[str, Any] | None],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        registry = registry_for_table(connection, args.table)
        if not registry:
            raise ValueError(f"Unknown table: {args.table}")
        columns = table_columns(connection, registry["physical_table"])
        unique_fields = sanitize_unique_fields(parse_csv_list(args.unique_fields), columns, allow_empty=False)
        proposed = {
            "tableKey": args.table,
            "uniqueFields": unique_fields,
            "conflictRule": args.conflict_rule,
            "updatedAt": now_iso(),
        }
        current = saved_import_policy(connection, args.table)
        if not args.yes:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "current": current, "proposed": proposed}
        connection.execute(
            """
            INSERT OR REPLACE INTO import_policies(table_key, workspace_id, unique_fields_json, conflict_rule, updated_at)
            VALUES(?, ?, ?, ?, ?)
            """,
            (args.table, workspace_id, json.dumps(unique_fields, ensure_ascii=False), args.conflict_rule, proposed["updatedAt"]),
        )
        connection.commit()
    return {"ok": True, "confirmed": True, "policy": proposed}


def list_import_jobs_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    clauses: list[str] = []
    params: list[Any] = []
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        clauses.append("workspace_id = ?")
        params.append(workspace_id)
        if args.table:
            clauses.append("table_key = ?")
            params.append(args.table)
        if args.status:
            clauses.append("status = ?")
            params.append(args.status)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = [
            dict(row)
            for row in connection.execute(
                f"""
                SELECT job_key, workspace_id, source_file, table_key, mode, status, row_count, result_json, created_at
                FROM import_jobs
                {where_sql}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (*params, args.limit),
            ).fetchall()
        ]
    jobs = []
    keyword = str(args.search or "").strip().lower()
    for row in rows:
        result = json.loads(row.pop("result_json"))
        job = {**row, "source_file": source_label(row["source_file"]), "result": result}
        if keyword:
            haystack = json.dumps(job, ensure_ascii=False).lower()
            if keyword not in haystack:
                continue
        jobs.append(job)
    return {"ok": True, "importJobs": jobs, "count": len(jobs)}


def remove_import_job_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        row = connection.execute(
            """
            SELECT job_key, workspace_id, source_file, table_key, mode, status, row_count, result_json, created_at
            FROM import_jobs
            WHERE job_key = ? AND workspace_id = ?
            """,
            (args.job, workspace_id),
        ).fetchone()
        if not row:
            raise ValueError(f"Unknown import job: {args.job}")
        job = dict(row)
        job["result"] = json.loads(job.pop("result_json"))
        if not args.yes:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "removedJob": job,
                "message": "Only the import job log will be removed; source tables are not deleted.",
            }
        connection.execute("DELETE FROM import_jobs WHERE job_key = ? AND workspace_id = ?", (args.job, workspace_id))
        connection.commit()
    return {"ok": True, "confirmed": True, "removedJob": job}
