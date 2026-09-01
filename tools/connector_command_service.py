from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import tempfile
from pathlib import Path
from typing import Any, Callable

from bi_cli_core import DB_PATH, ROOT, now_iso, parse_csv_list, slug, source_label, unique_key
from connector_adapter_service import (
    build_sync_plan,
    public_connector,
    public_sync_plan,
    validate_connector_resource,
    validate_credential_reference,
    validate_http_connector_registration,
    validate_sqlite_connector_registration,
)
from workspace_command_service import active_workspace_id
from workspace_mutation_lock_service import WorkspaceMutationBusyError, workspace_mutation_lock, workspace_read_lock
from workspace_recovery_service import configured_recovery_root, unfinished_recovery_fences


VALID_CONNECTOR_TYPES = {"file", "api", "erp", "database", "sqlserver"}
VALID_CONNECTOR_STATUSES = {"draft", "active", "paused"}
CONNECTOR_SYNC_LOCK_PATH = DB_PATH.parent / ".aibi-cross-engine-writer.lock"


def _assert_connector_sync_recovery_clear() -> None:
    fences = unfinished_recovery_fences(configured_recovery_root(ROOT))
    if fences:
        workspaces = sorted({str(item["workspaceId"]) for item in fences})
        raise PermissionError(
            "Connector sync is fenced by unfinished recovery for: " + ", ".join(workspaces)
        )


def normalize_connector_key(value: str) -> str:
    normalized = slug(value)
    return normalized[:64] or unique_key("connector")


def normalize_connector_type(value: str | None) -> str:
    item = str(value or "file").strip().lower()
    return item if item in VALID_CONNECTOR_TYPES else "file"


def normalize_connector_status(value: str | None) -> str:
    item = str(value or "draft").strip().lower()
    return item if item in VALID_CONNECTOR_STATUSES else "draft"


def connector_row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return public_connector(row)


def load_connectors(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    workspace_id = active_workspace_id(connection)
    rows = connection.execute(
        """
        SELECT *
        FROM data_connectors
        WHERE workspace_id = ?
        ORDER BY updated_at DESC, name
        """,
        (workspace_id,),
    ).fetchall()
    return [connector_row_to_dict(row) for row in rows]


def connector_by_key_or_name(connection: sqlite3.Connection, value: str) -> sqlite3.Row | None:
    workspace_id = active_workspace_id(connection)
    return connection.execute(
        """
        SELECT *
        FROM data_connectors
        WHERE workspace_id = ? AND (connector_key = ? OR name = ?)
        """,
        (workspace_id, value, value),
    ).fetchone()


def resolve_connector_endpoint(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def list_connectors_command(args: argparse.Namespace, *, open_db: Callable[[], Any]) -> dict[str, Any]:
    with open_db() as connection:
        connectors = load_connectors(connection)
    if args.type:
        connectors = [item for item in connectors if item["type"] == args.type]
    if args.status:
        connectors = [item for item in connectors if item["status"] == args.status]
    keyword = str(args.search or "").strip().lower()
    if keyword:
        connectors = [
            item for item in connectors
            if keyword in json.dumps(item, ensure_ascii=False).lower()
        ]
    return {"ok": True, "connectors": connectors, "count": len(connectors)}


def save_connector_command(args: argparse.Namespace, *, open_db: Callable[[], Any]) -> dict[str, Any]:
    connector_key = normalize_connector_key(args.connector or args.name)
    connector_type = normalize_connector_type(args.type)
    connector_status = normalize_connector_status(args.status)
    endpoint = str(args.endpoint or "").strip()
    resource = str(getattr(args, "resource", "") or "").strip()
    credential_reference = validate_credential_reference(getattr(args, "credential_ref", None))
    if connector_type == "file":
        if credential_reference:
            raise ValueError("Local file connectors cannot declare credentials.")
        if endpoint:
            validate_connector_resource(endpoint, require_exists=False)
    if connector_type == "api":
        validate_http_connector_registration(endpoint)
    if connector_type == "database" and credential_reference:
        raise ValueError("SQLite database connectors cannot declare credentials.")
    if connector_type == "database":
        validate_sqlite_connector_registration(endpoint, resource)
    config = {
        "endpoint": endpoint,
        "resource": resource,
        "pageParam": str(getattr(args, "page_param", "") or "").strip(),
        "pageSizeParam": str(getattr(args, "page_size_param", "") or "").strip(),
        "pageSize": max(1, min(int(getattr(args, "page_size", 100) or 100), 1000)),
        "maxPages": max(1, min(int(getattr(args, "max_pages", 1) or 1), 10)),
        "importMode": str(args.import_mode or "auto"),
        "targetTableKey": str(args.target_table or "").strip(),
        "uniqueFields": parse_csv_list(args.unique_fields),
        "conflictRule": str(args.conflict_rule or "overwrite"),
        "notes": str(args.notes or "").strip(),
        "credentialRef": credential_reference,
    }
    if connector_type == "sqlserver":
        host_alias = endpoint.strip().casefold()
        database = resource.strip()
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,62}", host_alias):
            raise ValueError("SQL Server host alias must be a bounded server-owned allowlist key.")
        if not database or len(database) > 128 or any(ord(char) < 32 for char in database):
            raise ValueError("SQL Server database must be a bounded catalog name.")
        port = max(1, min(int(getattr(args, "port", 1433) or 1433), 65535))
        encryption = str(getattr(args, "encryption", "required") or "required").strip().lower()
        if encryption != "required":
            raise ValueError("SQL Server connectors require encrypted transport.")
        config = {
            "hostAlias": host_alias,
            "port": port,
            "database": database,
            "encryption": encryption,
            "credentialRef": credential_reference,
        }
    schedule = {"mode": str(args.schedule or "manual")}
    now = now_iso()
    proposed = {
        "connectorKey": connector_key,
        "name": str(args.name or connector_key).strip(),
        "type": connector_type,
        "provider": str(args.provider or "").strip(),
        "status": connector_status,
        "config": {
            **{key: value for key, value in config.items() if key != "credentialRef"},
            "credentialConfigured": bool(credential_reference),
        },
        "schedule": schedule,
        "updatedAt": now,
    }
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        current_row = connector_by_key_or_name(connection, connector_key)
        current = connector_row_to_dict(current_row) if current_row else None
        if current_row and not credential_reference:
            current_raw_config = json.loads(current_row["config_json"] or "{}")
            if current_raw_config.get("credentialRef"):
                config["credentialRef"] = current_raw_config["credentialRef"]
                proposed["config"]["credentialConfigured"] = True
        if not args.yes:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "current": current,
                "proposed": proposed,
                "evidence": ["b-connector-config-model", "aibi-action-confirmation-boundary"],
            }
        created_at = current["createdAt"] if current else now
        connection.execute(
            """
            INSERT OR REPLACE INTO data_connectors(
              connector_key, workspace_id, name, connector_type, provider, status, config_json,
              schedule_json, created_at, updated_at, last_sync_at, last_sync_status, last_sync_result_json
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                connector_key,
                workspace_id,
                proposed["name"],
                connector_type,
                proposed["provider"],
                connector_status,
                json.dumps(config, ensure_ascii=False),
                json.dumps(schedule, ensure_ascii=False),
                created_at,
                now,
                current["lastSyncAt"] if current else None,
                current["lastSyncStatus"] if current else None,
                json.dumps(current["lastSyncResult"], ensure_ascii=False) if current else None,
            ),
        )
        connection.commit()
        saved_row = connector_by_key_or_name(connection, connector_key)
    return {"ok": True, "confirmed": True, "savedConnector": connector_key, "connector": connector_row_to_dict(saved_row)}


def remove_connector_command(args: argparse.Namespace, *, open_db: Callable[[], Any]) -> dict[str, Any]:
    with open_db() as connection:
        row = connector_by_key_or_name(connection, args.connector)
        if not row:
            raise ValueError(f"Unknown connector: {args.connector}")
        connector = connector_row_to_dict(row)
        if not args.yes:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "removedConnector": connector,
                "message": "Only connector configuration will be removed; imported tables and source files are not deleted.",
            }
        connection.execute(
            "DELETE FROM data_connectors WHERE connector_key = ? AND workspace_id = ?",
            (connector["connectorKey"], connector["workspaceId"]),
        )
        connection.commit()
    return {"ok": True, "confirmed": True, "removedConnector": connector}


def sync_connector_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    registry_for_table: Callable[[sqlite3.Connection, str], sqlite3.Row | None],
    saved_import_policy: Callable[[sqlite3.Connection, str], dict[str, Any] | None],
) -> dict[str, Any]:
    # The dispatcher intentionally leaves this facade unlocked. Planning owns
    # a shared boundary; the actual data change delegates to Durable Import,
    # which acquires its own short exclusive claim and activation boundaries.
    # This prevents a connector sync from advancing SQLite without publishing
    # the matching DuckDB replica.
    with workspace_read_lock(CONNECTOR_SYNC_LOCK_PATH):
        _assert_connector_sync_recovery_clear()
        with open_db() as connection:
            row = connector_by_key_or_name(connection, args.connector)
            if not row:
                raise ValueError(f"Unknown connector: {args.connector}")
            connector = connector_row_to_dict(row)
            if connector["status"] == "paused" and not args.allow_paused:
                return {
                    "ok": False,
                    "blocked": True,
                    "connector": connector,
                    "reason": "Connector is paused. Pass --allow-paused after review to sync it.",
                }
            config = json.loads(row["config_json"] or "{}")
            target_table = str(config.get("targetTableKey") or "").strip() or normalize_connector_key(connector["name"])
            import_mode = str(config.get("importMode") or "auto")
            unique_fields = [str(item) for item in config.get("uniqueFields") or []]
            conflict_rule = str(config.get("conflictRule") or "overwrite")
            adapter_plan = build_sync_plan(
                row,
                connection=connection,
                registry_for_table=registry_for_table,
                saved_import_policy=saved_import_policy,
            )
            public_plan = public_sync_plan(adapter_plan)
            if adapter_plan.get("blocked") or not args.yes:
                return public_plan
            registry = registry_for_table(connection, target_table)
            mode = "merge" if import_mode == "auto" and registry else "create" if import_mode == "auto" else import_mode
            if mode == "merge" and not unique_fields:
                policy = saved_import_policy(connection, target_table)
                unique_fields = policy["uniqueFields"] if policy else []
                conflict_rule = policy["conflictRule"] if policy else conflict_rule
            source_path = adapter_plan.get("_sourcePath")
            staged_rows = adapter_plan.get("_rows")
            staged_columns = adapter_plan.get("syncPlan", {}).get("columns")

    temporary_source: Path | None = None
    if source_path is None:
        if not isinstance(staged_rows, list) or not isinstance(staged_columns, list) or not staged_columns:
            raise ValueError("Connector adapter did not produce a bounded tabular snapshot.")
        handle = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", prefix="aibi-c-connector-", delete=False, encoding="utf-8-sig", newline=""
        )
        try:
            writer = csv.DictWriter(handle, fieldnames=[str(item) for item in staged_columns], extrasaction="ignore")
            writer.writeheader()
            for item in staged_rows:
                writer.writerow(item if isinstance(item, dict) else {})
        finally:
            handle.close()
        temporary_source = Path(handle.name)
        source_path = temporary_source

    from import_job_commands import direct_import_commit_command

    durable_mode = "create" if mode == "replace" else mode
    try:
        durable = direct_import_commit_command(argparse.Namespace(
            workspace=str(connector["workspaceId"]),
            file=str(source_path),
            table=target_table,
            name=target_table,
            mode=durable_mode,
            unique_fields=",".join(unique_fields),
            conflict_rule=conflict_rule,
            expected_plan=None,
            require_plan=False,
            yes=True,
        ))
    finally:
        if temporary_source is not None:
            temporary_source.unlink(missing_ok=True)

    import_result = durable.get("result") if isinstance(durable.get("result"), dict) else {}
    result = {
        "importResult": import_result,
        "syncedAt": now_iso(),
        "mode": mode,
        "activationJournalKey": durable.get("activationJournalKey"),
        "durableJob": durable.get("durableJob"),
        "adapter": {
            "adapterId": adapter_plan["syncPlan"]["adapterId"],
            "planFingerprint": adapter_plan["planFingerprint"],
            "resourceFingerprint": adapter_plan["syncPlan"]["resource"]["sha256"],
        },
        "evidence": [f"connector-adapter:{adapter_plan['syncPlan']['adapterId']}", "source-profile", "field-semantics", "metric-sql-plan", "query-runtime"],
    }
    refreshed = connector
    try:
        with workspace_mutation_lock(CONNECTOR_SYNC_LOCK_PATH):
            _assert_connector_sync_recovery_clear()
            with open_db() as connection:
                connection.execute(
                    """
                    UPDATE data_connectors
                    SET last_sync_at = ?, last_sync_status = 'success', last_sync_result_json = ?, updated_at = ?
                    WHERE connector_key = ? AND workspace_id = ?
                    """,
                    (result["syncedAt"], json.dumps(result, ensure_ascii=False), result["syncedAt"], connector["connectorKey"], connector["workspaceId"]),
                )
                connection.commit()
                refreshed_row = connector_by_key_or_name(connection, connector["connectorKey"])
                if refreshed_row:
                    refreshed = connector_row_to_dict(refreshed_row)
    except (PermissionError, WorkspaceMutationBusyError) as exc:
        # The activation receipt is authoritative even if a recovery begins in
        # the narrow post-commit metadata window. Report the deferred cosmetic
        # status update without turning a committed import into failure.
        result["connectorStatusUpdate"] = {"status": "deferred", "reason": str(exc)}
    return {"ok": True, "confirmed": True, "connector": refreshed, "connectorSync": result}
