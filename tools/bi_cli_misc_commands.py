from __future__ import annotations

import argparse
from typing import Any

from bi_cli_capabilities import BI_CLI_CAPABILITY_MAP
from bi_cli_core import DB_PATH, DUCKDB_PATH
from bi_cli_schema import active_workspace_id, open_db, registry_for_table, table_columns

def cli_capabilities_command(args: argparse.Namespace) -> dict[str, Any]:
    active = [item for item in BI_CLI_CAPABILITY_MAP if item["status"] in {"active", "contract-active"}]
    pending = [item for item in BI_CLI_CAPABILITY_MAP if item["status"] == "pending"]
    return {
        "ok": True,
        "source": {
            "project": "AIBI-C",
            "entrypoint": "python tools/bi_cli.py --json <command>",
            "executionPolicy": "Execute only AIBI-C commands against the active AIBI-C workspace with existing read and confirmation boundaries.",
        },
        "target": {
            "project": "AIBI-C",
            "entrypoint": "python tools/bi_cli.py --json <command>",
            "metadataStore": str(DB_PATH),
            "duckdbRuntime": str(DUCKDB_PATH),
        },
        "summary": {
            "activeAreas": len(active),
            "pendingAreas": len(pending),
            "capabilityAreas": len(BI_CLI_CAPABILITY_MAP),
        },
        "capabilities": BI_CLI_CAPABILITY_MAP,
        "guardrails": [
            "No command reads another project working tree or database.",
            "Import commit, dashboard write, relationship save, index creation, delete, overwrite, and external sync require dry-run or explicit confirmation.",
            "Dashboard widget generation uses the shared widget catalog instead of ad hoc frontend-only shapes.",
        ],
    }


def update_field_command(args: argparse.Namespace) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        registry = registry_for_table(connection, args.table)
        if not registry:
            raise ValueError(f"Unknown table: {args.table}")
        columns = table_columns(connection, registry["physical_table"])
        if args.field not in columns:
            raise ValueError(f"Unknown field: {args.field}")
        current = connection.execute(
            "SELECT table_key, field_name, role, usage, confidence FROM field_semantics WHERE table_key = ? AND field_name = ? AND workspace_id = ?",
            (args.table, args.field, workspace_id),
        ).fetchone()
        confidence = max(0.0, min(1.0, float(args.confidence)))
        proposed = {
            "table_key": args.table,
            "field_name": args.field,
            "role": args.role,
            "usage": args.usage,
            "confidence": confidence,
        }
        if not args.yes:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "current": dict(current) if current else None,
                "proposed": proposed,
            }
        connection.execute(
            """
            INSERT OR REPLACE INTO field_semantics(workspace_id, table_key, field_name, role, usage, confidence)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (workspace_id, args.table, args.field, args.role, args.usage, confidence),
        )
        connection.commit()
    return {"ok": True, "updated": proposed}


