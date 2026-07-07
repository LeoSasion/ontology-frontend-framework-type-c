from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any, Callable

from bi_cli_core import ROOT, now_iso, parse_csv_list, slug, source_label, unique_key


VALID_CONNECTOR_TYPES = {"file", "api", "erp", "database"}
VALID_CONNECTOR_STATUSES = {"draft", "active", "paused"}


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
    return {
        "connectorKey": row["connector_key"],
        "name": row["name"],
        "type": row["connector_type"],
        "provider": row["provider"],
        "status": row["status"],
        "config": json.loads(row["config_json"] or "{}"),
        "schedule": json.loads(row["schedule_json"] or "{}"),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "lastSyncAt": row["last_sync_at"],
        "lastSyncStatus": row["last_sync_status"],
        "lastSyncResult": json.loads(row["last_sync_result_json"] or "null"),
    }


def load_connectors(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT *
        FROM data_connectors
        ORDER BY updated_at DESC, name
        """
    ).fetchall()
    return [connector_row_to_dict(row) for row in rows]


def connector_by_key_or_name(connection: sqlite3.Connection, value: str) -> sqlite3.Row | None:
    return connection.execute(
        """
        SELECT *
        FROM data_connectors
        WHERE connector_key = ? OR name = ?
        """,
        (value, value),
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
    config = {
        "endpoint": str(args.endpoint or "").strip(),
        "importMode": str(args.import_mode or "auto"),
        "targetTableKey": str(args.target_table or "").strip(),
        "uniqueFields": parse_csv_list(args.unique_fields),
        "conflictRule": str(args.conflict_rule or "overwrite"),
        "notes": str(args.notes or "").strip(),
    }
    schedule = {"mode": str(args.schedule or "manual")}
    now = now_iso()
    proposed = {
        "connectorKey": connector_key,
        "name": str(args.name or connector_key).strip(),
        "type": connector_type,
        "provider": str(args.provider or "").strip(),
        "status": connector_status,
        "config": config,
        "schedule": schedule,
        "updatedAt": now,
    }
    with open_db() as connection:
        current_row = connector_by_key_or_name(connection, connector_key)
        current = connector_row_to_dict(current_row) if current_row else None
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
              connector_key, name, connector_type, provider, status, config_json,
              schedule_json, created_at, updated_at, last_sync_at, last_sync_status, last_sync_result_json
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                connector_key,
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
        connection.execute("DELETE FROM data_connectors WHERE connector_key = ?", (connector["connectorKey"],))
        connection.commit()
    return {"ok": True, "confirmed": True, "removedConnector": connector}


def sync_connector_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    read_table_file: Callable[[Path], tuple[list[str], list[dict[str, Any]]]],
    registry_for_table: Callable[[sqlite3.Connection, str], sqlite3.Row | None],
    saved_import_policy: Callable[[sqlite3.Connection, str], dict[str, Any] | None],
    merge_import_into_table: Callable[..., dict[str, Any]],
    import_csv_as_table: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
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
        config = connector["config"]
        endpoint = str(config.get("endpoint") or "").strip()
        target_table = str(config.get("targetTableKey") or "").strip() or normalize_connector_key(connector["name"])
        import_mode = str(config.get("importMode") or "auto")
        unique_fields = [str(item) for item in config.get("uniqueFields") or []]
        conflict_rule = str(config.get("conflictRule") or "overwrite")
        proposed = {
            "connectorKey": connector["connectorKey"],
            "type": connector["type"],
            "provider": connector["provider"],
            "endpoint": endpoint,
            "targetTableKey": target_table,
            "importMode": import_mode,
            "uniqueFields": unique_fields,
            "conflictRule": conflict_rule,
        }
        if connector["type"] != "file":
            result = {
                "ok": True,
                "blocked": True,
                "dryRun": not args.yes,
                "requiresConfirmation": not args.yes,
                "connector": connector,
                "proposedSync": proposed,
                "reason": "External API, ERP, and database connectors are registered but not executed by this local hybrid runtime yet.",
                "evidence": ["b-connector-config-model", "aibi-no-external-sync-without-executor-receipt"],
            }
            if args.yes:
                timestamp = now_iso()
                connection.execute(
                    """
                    UPDATE data_connectors
                    SET last_sync_at = ?, last_sync_status = 'blocked', last_sync_result_json = ?, updated_at = ?
                    WHERE connector_key = ?
                    """,
                    (timestamp, json.dumps(result, ensure_ascii=False), timestamp, connector["connectorKey"]),
                )
                connection.commit()
            return result
        source_path = resolve_connector_endpoint(endpoint)
        source_exists = source_path.exists()
        if not args.yes:
            preview = None
            if source_exists:
                headers, rows = read_table_file(source_path)
                preview = {"rowCount": len(rows), "columnCount": len(headers), "columns": headers[:12]}
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "connector": connector,
                "proposedSync": {**proposed, "sourceFile": source_label(source_path), "sourceExists": source_exists, "preview": preview},
                "evidence": ["b-file-connector", "import-preview", "aibi-action-confirmation-boundary"],
            }
        if not source_exists:
            raise FileNotFoundError(source_path)
        registry = registry_for_table(connection, target_table)
        mode = "merge" if import_mode == "auto" and registry else "create" if import_mode == "auto" else import_mode
        if mode == "merge":
            if not unique_fields:
                policy = saved_import_policy(connection, target_table)
                unique_fields = policy["uniqueFields"] if policy else []
                conflict_rule = policy["conflictRule"] if policy else conflict_rule
            import_result = merge_import_into_table(
                connection,
                source_path,
                table_key=target_table,
                unique_fields=unique_fields,
                conflict_rule=conflict_rule,
                display_name=target_table,
            )
        else:
            import_result = import_csv_as_table(
                connection,
                source_path,
                table_key=target_table,
                display_name=target_table,
                mode="connector-sync",
            )
        result = {
            "importResult": import_result,
            "syncedAt": now_iso(),
            "mode": mode,
            "evidence": ["b-file-connector", "source-profile", "field-semantics", "metric-sql-plan", "query-runtime"],
        }
        connection.execute(
            """
            UPDATE data_connectors
            SET last_sync_at = ?, last_sync_status = 'success', last_sync_result_json = ?, updated_at = ?
            WHERE connector_key = ?
            """,
            (result["syncedAt"], json.dumps(result, ensure_ascii=False), result["syncedAt"], connector["connectorKey"]),
        )
        connection.commit()
        refreshed = connector_row_to_dict(connector_by_key_or_name(connection, connector["connectorKey"]))
    return {"ok": True, "confirmed": True, "connector": refreshed, "connectorSync": result}
