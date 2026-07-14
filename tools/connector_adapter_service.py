from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from openpyxl import load_workbook

from bi_cli_core import ROOT, source_label


ADAPTER_SCHEMA = "aibi-connector-adapter/v1"
ADAPTER_RECEIPT_SCHEMA = "aibi-connector-adapter-receipt/v1"
LOCAL_TABULAR_ADAPTER = "local-tabular/v1"
MAX_SOURCE_BYTES = 100 * 1024 * 1024
MAX_PREVIEW_ROWS = 100
MAX_PREVIEW_COLUMNS = 64
MAX_CELL_TEXT = 512
ALLOWED_FILE_SUFFIXES = {".csv", ".xlsx", ".xlsm"}
FORBIDDEN_REPOSITORY_PARTS = {
    "aibi-a",
    "aibi-b",
    "aibi-d",
    "aibi-e",
    "aibi项目杂交",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def adapter_contracts() -> list[dict[str, Any]]:
    local_contract = {
        "schema": ADAPTER_SCHEMA,
        "adapterId": LOCAL_TABULAR_ADAPTER,
        "connectorType": "file",
        "available": True,
        "operations": ["metadata-discovery", "bounded-preview", "sync-plan"],
        "permissions": {
            "filesystem": "selected-file-read-only",
            "network": "none",
            "database": "metadata-read-only",
            "arbitrarySql": False,
            "otherAibiRepositories": "forbidden",
        },
        "limits": {
            "sourceBytes": MAX_SOURCE_BYTES,
            "previewRows": MAX_PREVIEW_ROWS,
            "previewColumns": MAX_PREVIEW_COLUMNS,
            "extensions": sorted(ALLOWED_FILE_SUFFIXES),
        },
        "credentials": {"mode": "none", "valuesInReceipts": False},
        "persistence": {"performedByAdapter": False, "boundary": "sync-connector --yes"},
    }
    unavailable = []
    for connector_type in ("api", "erp", "database"):
        unavailable.append({
            "schema": ADAPTER_SCHEMA,
            "adapterId": f"{connector_type}-allowlist/unavailable",
            "connectorType": connector_type,
            "available": False,
            "operations": [],
            "permissions": {
                "filesystem": "none",
                "network": "none",
                "database": "none",
                "arbitrarySql": False,
                "otherAibiRepositories": "forbidden",
            },
            "credentials": {"mode": "server-env-reference", "valuesInReceipts": False},
            "reason": "No provider-specific allowlist adapter is installed; registration grants no execution authority.",
        })
    return [local_contract, *unavailable]


def adapter_contract_for(connector_type: str) -> dict[str, Any]:
    contract = next((item for item in adapter_contracts() if item["connectorType"] == connector_type), None)
    if not contract:
        raise ValueError(f"No adapter contract exists for connector type: {connector_type}")
    return contract


def validate_credential_reference(value: str | None) -> str:
    reference = str(value or "").strip()
    if not reference:
        return ""
    if not reference.startswith("env:"):
        raise ValueError("Connector credentials must use a server-side env:NAME reference; literal values are forbidden.")
    name = reference[4:]
    if not name or not (name[0].isalpha() or name[0] == "_") or not all(char.isalnum() or char == "_" for char in name):
        raise ValueError("Connector credential reference must match env:NAME.")
    return reference


def _candidate_path(value: str) -> Path:
    raw = Path(str(value or "").strip())
    if not str(raw):
        raise ValueError("Connector endpoint is required for the local tabular adapter.")
    return raw if raw.is_absolute() else ROOT / raw


def _reject_symlink_chain(candidate: Path) -> None:
    current = candidate
    while True:
        if current.exists() and current.is_symlink():
            raise ValueError("Connector resources cannot traverse symbolic links or junction-like links.")
        if current.parent == current:
            break
        current = current.parent


def validate_connector_resource(value: str, *, require_exists: bool = True) -> Path:
    candidate = _candidate_path(value)
    _reject_symlink_chain(candidate)
    resolved = candidate.resolve()
    lowered_parts = {part.casefold() for part in resolved.parts}
    forbidden = sorted(lowered_parts.intersection(FORBIDDEN_REPOSITORY_PARTS))
    if forbidden:
        raise ValueError(f"Connector resource belongs to a forbidden AIBI repository boundary: {forbidden[0]}")
    if resolved.suffix.casefold() not in ALLOWED_FILE_SUFFIXES:
        raise ValueError(f"Local tabular adapter accepts only: {', '.join(sorted(ALLOWED_FILE_SUFFIXES))}")
    if require_exists and not resolved.is_file():
        raise FileNotFoundError(resolved.name)
    if resolved.exists() and resolved.stat().st_size > MAX_SOURCE_BYTES:
        raise ValueError(f"Connector resource exceeds the {MAX_SOURCE_BYTES} byte adapter limit.")
    return resolved


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_scalar(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    text = str(value)
    return text if len(text) <= MAX_CELL_TEXT else f"{text[:MAX_CELL_TEXT]}…"


def _csv_preview(path: Path, limit: int) -> tuple[list[str], list[list[Any]], bool, str]:
    last_error: Exception | None = None
    for encoding in ("utf-8-sig", "gb18030"):
        try:
            with path.open("r", encoding=encoding, newline="") as handle:
                reader = csv.reader(handle)
                headers = [str(item).strip() or f"column_{index + 1}" for index, item in enumerate(next(reader, []))]
                rows: list[list[Any]] = []
                for row in reader:
                    rows.append([_safe_scalar(item) for item in row[:MAX_PREVIEW_COLUMNS]])
                    if len(rows) > limit:
                        break
                return headers[:MAX_PREVIEW_COLUMNS], rows[:limit], len(rows) > limit, "csv"
        except UnicodeDecodeError as error:
            last_error = error
    raise ValueError(f"Connector CSV encoding is unsupported: {last_error}")


def _workbook_preview(path: Path, limit: int) -> tuple[list[str], list[list[Any]], bool, str]:
    workbook = load_workbook(path, read_only=True, data_only=True, keep_links=False)
    try:
        worksheet = workbook.active
        iterator = worksheet.iter_rows(values_only=True)
        header_row = next(iterator, ())
        headers = [str(item).strip() if item is not None and str(item).strip() else f"column_{index + 1}" for index, item in enumerate(header_row)]
        rows: list[list[Any]] = []
        for row in iterator:
            rows.append([_safe_scalar(item) for item in row[:MAX_PREVIEW_COLUMNS]])
            if len(rows) > limit:
                break
        return headers[:MAX_PREVIEW_COLUMNS], rows[:limit], len(rows) > limit or worksheet.max_row > limit + 1, worksheet.title
    finally:
        workbook.close()


def bounded_tabular_preview(path: Path, limit: int) -> dict[str, Any]:
    bounded_limit = max(1, min(int(limit), MAX_PREVIEW_ROWS))
    if path.suffix.casefold() == ".csv":
        columns, rows, truncated, source_part = _csv_preview(path, bounded_limit)
    else:
        columns, rows, truncated, source_part = _workbook_preview(path, bounded_limit)
    normalized_rows = []
    for row in rows:
        normalized_rows.append({column: row[index] if index < len(row) else None for index, column in enumerate(columns)})
    return {
        "columns": columns,
        "rows": normalized_rows,
        "returnedRows": len(normalized_rows),
        "truncated": truncated,
        "sourcePart": source_part,
        "limits": {"rows": bounded_limit, "columns": MAX_PREVIEW_COLUMNS, "cellText": MAX_CELL_TEXT},
    }


def public_connector(row: Any) -> dict[str, Any]:
    raw_config = json.loads(row["config_json"] or "{}")
    public_config = {key: value for key, value in raw_config.items() if key != "credentialRef"}
    public_config["credentialConfigured"] = bool(raw_config.get("credentialRef"))
    return {
        "connectorKey": row["connector_key"],
        "workspaceId": row["workspace_id"],
        "name": row["name"],
        "type": row["connector_type"],
        "provider": row["provider"],
        "status": row["status"],
        "config": public_config,
        "schedule": json.loads(row["schedule_json"] or "{}"),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "lastSyncAt": row["last_sync_at"],
        "lastSyncStatus": row["last_sync_status"],
        "lastSyncResult": json.loads(row["last_sync_result_json"] or "null"),
    }


def _connector_identity(row: Any) -> dict[str, Any]:
    raw_config = json.loads(row["config_json"] or "{}")
    return {
        "connectorKey": row["connector_key"],
        "workspaceId": row["workspace_id"],
        "name": row["name"],
        "type": row["connector_type"],
        "provider": row["provider"],
        "status": row["status"],
        "targetTableKey": str(raw_config.get("targetTableKey") or ""),
        "credentialConfigured": bool(raw_config.get("credentialRef")),
    }


def _blocked_receipt(row: Any, operation: str) -> dict[str, Any]:
    identity = _connector_identity(row)
    contract = adapter_contract_for(identity["type"])
    return {
        "ok": False,
        "blocked": True,
        "schema": ADAPTER_RECEIPT_SCHEMA,
        "operation": operation,
        "connector": identity,
        "adapter": contract,
        "reason": contract.get("reason") or "Connector adapter is unavailable.",
        "sideEffects": {"network": False, "businessDatabaseWrite": False, "artifactWrite": False},
        "evidence": ["connector-adapter-contract", "aibi-no-external-execution-without-provider-allowlist"],
    }


def _local_context(row: Any, preview_limit: int) -> tuple[dict[str, Any], Path, dict[str, Any], dict[str, Any]]:
    identity = _connector_identity(row)
    if identity["type"] != "file":
        raise ValueError("Only file connectors can use the local tabular adapter.")
    raw_config = json.loads(row["config_json"] or "{}")
    if raw_config.get("credentialRef"):
        raise ValueError("Local file connectors cannot declare credentials.")
    path = validate_connector_resource(str(raw_config.get("endpoint") or ""))
    digest = _file_sha256(path)
    resource = {
        "label": path.name,
        "extension": path.suffix.casefold(),
        "bytes": path.stat().st_size,
        "sha256": digest,
    }
    preview = bounded_tabular_preview(path, preview_limit)
    return identity, path, resource, preview


def discover_connector(row: Any) -> dict[str, Any]:
    identity = _connector_identity(row)
    if identity["type"] != "file":
        return _blocked_receipt(row, "metadata-discovery")
    identity, _path, resource, preview = _local_context(row, 1)
    metadata = {
        "resource": resource,
        "columns": preview["columns"],
        "columnCount": len(preview["columns"]),
        "sourcePart": preview["sourcePart"],
        "hasDataRows": preview["returnedRows"] > 0,
    }
    return {
        "ok": True,
        "schema": ADAPTER_RECEIPT_SCHEMA,
        "operation": "metadata-discovery",
        "connector": identity,
        "adapter": adapter_contract_for("file"),
        "metadata": metadata,
        "receiptFingerprint": _fingerprint({"operation": "metadata-discovery", "connector": identity, "metadata": metadata}),
        "sideEffects": {"network": False, "businessDatabaseWrite": False, "artifactWrite": False},
        "evidence": ["connector-adapter-contract", "selected-file-metadata", "resource-fingerprint"],
    }


def preview_connector(row: Any, limit: int) -> dict[str, Any]:
    identity = _connector_identity(row)
    if identity["type"] != "file":
        return _blocked_receipt(row, "bounded-preview")
    identity, _path, resource, preview = _local_context(row, limit)
    payload = {"resource": resource, "preview": preview}
    return {
        "ok": True,
        "schema": ADAPTER_RECEIPT_SCHEMA,
        "operation": "bounded-preview",
        "connector": identity,
        "adapterId": LOCAL_TABULAR_ADAPTER,
        **payload,
        "receiptFingerprint": _fingerprint({"operation": "bounded-preview", "connector": identity, **payload}),
        "sideEffects": {"network": False, "businessDatabaseWrite": False, "artifactWrite": False},
        "evidence": ["connector-adapter-contract", "bounded-scalar-preview", "resource-fingerprint"],
    }


def build_sync_plan(
    row: Any,
    *,
    connection: Any,
    registry_for_table: Callable[[Any, str], Any],
    saved_import_policy: Callable[[Any, str], dict[str, Any] | None],
) -> dict[str, Any]:
    identity = _connector_identity(row)
    if identity["type"] != "file":
        return _blocked_receipt(row, "sync-plan")
    identity, path, resource, preview = _local_context(row, 5)
    raw_config = json.loads(row["config_json"] or "{}")
    target_table = str(raw_config.get("targetTableKey") or "").strip() or identity["connectorKey"]
    requested_mode = str(raw_config.get("importMode") or "auto")
    registry = registry_for_table(connection, target_table)
    resolved_mode = "merge" if requested_mode == "auto" and registry else "create" if requested_mode == "auto" else requested_mode
    unique_fields = [str(item) for item in raw_config.get("uniqueFields") or []]
    conflict_rule = str(raw_config.get("conflictRule") or "overwrite")
    if resolved_mode == "merge" and not unique_fields:
        policy = saved_import_policy(connection, target_table)
        unique_fields = [str(item) for item in (policy or {}).get("uniqueFields") or []]
        conflict_rule = str((policy or {}).get("conflictRule") or conflict_rule)
    blockers: list[str] = []
    if resolved_mode == "merge" and not unique_fields:
        blockers.append("merge-requires-unique-fields")
    plan = {
        "adapterId": LOCAL_TABULAR_ADAPTER,
        "connectorKey": identity["connectorKey"],
        "resource": resource,
        "sourcePart": preview["sourcePart"],
        "columns": preview["columns"],
        "targetTableKey": target_table,
        "requestedMode": requested_mode,
        "resolvedMode": resolved_mode,
        "uniqueFields": unique_fields,
        "conflictRule": conflict_rule,
        "blockers": blockers,
        "writeBoundary": {
            "adapterWrites": False,
            "command": "sync-connector",
            "requiresConfirmation": True,
            "confirmationFlag": "--yes",
        },
    }
    return {
        "ok": not blockers,
        "blocked": bool(blockers),
        "dryRun": True,
        "requiresConfirmation": not blockers,
        "schema": ADAPTER_RECEIPT_SCHEMA,
        "operation": "sync-plan",
        "connector": identity,
        "syncPlan": plan,
        "planFingerprint": _fingerprint(plan),
        "sideEffects": {"network": False, "businessDatabaseWrite": False, "artifactWrite": False},
        "evidence": ["connector-adapter-contract", "bounded-sync-plan", "aibi-action-confirmation-boundary"],
        "_sourcePath": path,
    }


def public_sync_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in plan.items() if key != "_sourcePath"}


def list_connector_adapters_command(_args: Any) -> dict[str, Any]:
    contracts = adapter_contracts()
    return {"ok": True, "schema": ADAPTER_SCHEMA, "adapters": contracts, "count": len(contracts)}


def _row_for(args: Any, open_db: Callable[[], Any], connector_by_key_or_name: Callable[[Any, str], Any]):
    connection = open_db()
    row = connector_by_key_or_name(connection, args.connector)
    if not row:
        connection.close()
        raise ValueError(f"Unknown connector: {args.connector}")
    return connection, row


def discover_connector_command(args: Any, *, open_db: Callable[[], Any], connector_by_key_or_name: Callable[[Any, str], Any]) -> dict[str, Any]:
    connection, row = _row_for(args, open_db, connector_by_key_or_name)
    try:
        return discover_connector(row)
    finally:
        connection.close()


def preview_connector_command(args: Any, *, open_db: Callable[[], Any], connector_by_key_or_name: Callable[[Any, str], Any]) -> dict[str, Any]:
    connection, row = _row_for(args, open_db, connector_by_key_or_name)
    try:
        return preview_connector(row, args.limit)
    finally:
        connection.close()


def plan_connector_sync_command(
    args: Any,
    *,
    open_db: Callable[[], Any],
    connector_by_key_or_name: Callable[[Any, str], Any],
    registry_for_table: Callable[[Any, str], Any],
    saved_import_policy: Callable[[Any, str], dict[str, Any] | None],
) -> dict[str, Any]:
    connection, row = _row_for(args, open_db, connector_by_key_or_name)
    try:
        return public_sync_plan(build_sync_plan(
            row,
            connection=connection,
            registry_for_table=registry_for_table,
            saved_import_policy=saved_import_policy,
        ))
    finally:
        connection.close()
