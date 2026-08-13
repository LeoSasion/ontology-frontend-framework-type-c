from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from bi_cli_core import DB_PATH, now_iso
from sqlserver_snapshot_adapter_service import (
    SqlServerAdapterError,
    SqlServerDriver,
    adapter_contract,
    build_snapshot_plan,
    discover_catalog,
    parse_target_policies,
    preview_statistics,
    snapshot_to_staging,
    stable_fingerprint,
    test_connection,
    validate_credential_reference,
    verified_staged_snapshot,
    verify_catalog,
    verify_snapshot_plan,
)
from workspace_command_service import active_workspace_id


REAL_DRIVER_ENABLE_ENV = "AIBI_SQLSERVER_REAL_ENABLED"
ACTIVATION_REQUEST_PREFIX = "sqlserver-activate:"
METADATA_TABLES = (
    "sqlserver_snapshot_catalogs",
    "sqlserver_snapshot_plans",
    "sqlserver_snapshot_receipts",
)
SQLSERVER_SNAPSHOT_METADATA_DDL = """
CREATE TABLE IF NOT EXISTS sqlserver_snapshot_catalogs (
  workspace_id TEXT NOT NULL,
  connector_key TEXT NOT NULL,
  catalog_fingerprint TEXT NOT NULL,
  network_binding_fingerprint TEXT NOT NULL,
  catalog_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(workspace_id, connector_key, catalog_fingerprint),
  FOREIGN KEY(workspace_id, connector_key)
    REFERENCES data_connectors(workspace_id, connector_key) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_sqlserver_catalog_workspace_created
  ON sqlserver_snapshot_catalogs(workspace_id, connector_key, created_at DESC);

CREATE TABLE IF NOT EXISTS sqlserver_snapshot_plans (
  workspace_id TEXT NOT NULL,
  connector_key TEXT NOT NULL,
  plan_fingerprint TEXT NOT NULL,
  request_key TEXT NOT NULL,
  input_fingerprint TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('planned', 'staged', 'activated', 'failed')),
  artifact_key TEXT,
  plan_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  PRIMARY KEY(workspace_id, plan_fingerprint),
  UNIQUE(workspace_id, connector_key, request_key),
  FOREIGN KEY(workspace_id, connector_key)
    REFERENCES data_connectors(workspace_id, connector_key) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_sqlserver_plan_workspace_status
  ON sqlserver_snapshot_plans(workspace_id, connector_key, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS sqlserver_snapshot_receipts (
  workspace_id TEXT NOT NULL,
  connector_key TEXT NOT NULL,
  receipt_fingerprint TEXT NOT NULL,
  plan_fingerprint TEXT NOT NULL,
  operation TEXT NOT NULL CHECK(operation IN ('snapshot', 'activate')),
  artifact_key TEXT,
  receipt_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY(workspace_id, receipt_fingerprint),
  UNIQUE(workspace_id, connector_key, plan_fingerprint, operation),
  FOREIGN KEY(workspace_id, plan_fingerprint)
    REFERENCES sqlserver_snapshot_plans(workspace_id, plan_fingerprint) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_sqlserver_receipt_workspace_plan
  ON sqlserver_snapshot_receipts(workspace_id, connector_key, plan_fingerprint, created_at DESC);
"""

_FINGERPRINT_RE = re.compile(r"[a-f0-9]{64}")
_CONNECTOR_KEY_RE = re.compile(r"[A-Za-z0-9_-]{1,64}")
_FORBIDDEN_CONFIG_KEYS = {
    "connectionstring", "endpoint", "password", "pwd", "secret", "token", "username", "uid",
}


class _UnavailableDriver:
    name = "sqlserver-disabled/v1"

    def available(self) -> bool:
        return False

    def connect(self, **_kwargs: Any):  # pragma: no cover - guarded before invocation
        raise SqlServerAdapterError(
            "SQLSERVER_DRIVER_NOT_EXPLICITLY_ENABLED",
            f"Real SQL Server access requires {REAL_DRIVER_ENABLE_ENV}=1.",
        )


def _environment(environ: Mapping[str, str] | None) -> Mapping[str, str]:
    return environ if environ is not None else os.environ


def _real_driver(environment: Mapping[str, str], *, for_probe: bool) -> SqlServerDriver:
    if environment.get(REAL_DRIVER_ENABLE_ENV) != "1":
        if for_probe:
            return _UnavailableDriver()
        raise SqlServerAdapterError(
            "SQLSERVER_DRIVER_NOT_EXPLICITLY_ENABLED",
            f"Real SQL Server access requires {REAL_DRIVER_ENABLE_ENV}=1.",
            recovery_action="Enable the optional driver only after reviewing the target allowlist and read-only credential.",
        )
    try:
        from sqlserver_snapshot_pyodbc_driver import PyodbcSqlServerDriver

        return PyodbcSqlServerDriver()
    except SqlServerAdapterError:
        raise
    except Exception as error:
        raise SqlServerAdapterError(
            "SQLSERVER_DRIVER_UNAVAILABLE",
            "The explicitly enabled SQL Server driver is unavailable; it will not be installed automatically.",
        ) from error


def _driver(
    supplied: SqlServerDriver | None,
    environment: Mapping[str, str],
    *,
    for_probe: bool = False,
) -> SqlServerDriver:
    return supplied if supplied is not None else _real_driver(environment, for_probe=for_probe)


def _policies(
    supplied: Mapping[str, Mapping[str, Any]] | None,
    environment: Mapping[str, str],
) -> Mapping[str, Mapping[str, Any]]:
    return supplied if supplied is not None else parse_target_policies(environ=environment)


def _json_object(value: Any, *, label: str, max_bytes: int) -> dict[str, Any]:
    if isinstance(value, dict):
        result = dict(value)
    else:
        raw = str(value or "").strip()
        if not raw or len(raw.encode("utf-8")) > max_bytes:
            raise SqlServerAdapterError("SQLSERVER_INPUT_INVALID", f"{label} must be a bounded JSON object.")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as error:
            raise SqlServerAdapterError("SQLSERVER_INPUT_INVALID", f"{label} must be valid JSON.") from error
        if not isinstance(parsed, dict):
            raise SqlServerAdapterError("SQLSERVER_INPUT_INVALID", f"{label} must be a JSON object.")
        result = parsed
    if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > max_bytes:
        raise SqlServerAdapterError("SQLSERVER_INPUT_INVALID", f"{label} exceeds its size limit.")
    return result


def _json_list(value: Any, *, label: str, max_bytes: int, max_items: int) -> list[dict[str, Any]]:
    if isinstance(value, list):
        parsed = value
    else:
        raw = str(value or "").strip()
        if not raw or len(raw.encode("utf-8")) > max_bytes:
            raise SqlServerAdapterError("SQLSERVER_INPUT_INVALID", f"{label} must be a bounded JSON array.")
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as error:
            raise SqlServerAdapterError("SQLSERVER_INPUT_INVALID", f"{label} must be valid JSON.") from error
    if not isinstance(parsed, list) or not parsed or len(parsed) > max_items or any(not isinstance(item, dict) for item in parsed):
        raise SqlServerAdapterError("SQLSERVER_INPUT_INVALID", f"{label} must contain one through {max_items} objects.")
    if len(json.dumps(parsed, ensure_ascii=False).encode("utf-8")) > max_bytes:
        raise SqlServerAdapterError("SQLSERVER_INPUT_INVALID", f"{label} exceeds its size limit.")
    return [dict(item) for item in parsed]


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int, label: str) -> int:
    try:
        result = int(value if value not in (None, "") else default)
    except (TypeError, ValueError) as error:
        raise SqlServerAdapterError("SQLSERVER_INPUT_INVALID", f"{label} must be a bounded integer.") from error
    if result < minimum or result > maximum:
        raise SqlServerAdapterError("SQLSERVER_INPUT_INVALID", f"{label} must be between {minimum} and {maximum}.")
    return result


def _connector_key(args: argparse.Namespace, *, required: bool = True) -> str:
    value = str(getattr(args, "connector", "") or "").strip()
    if not value and not required:
        return ""
    if not _CONNECTOR_KEY_RE.fullmatch(value):
        raise SqlServerAdapterError("SQLSERVER_CONNECTOR_KEY_INVALID", "A valid SQL Server connector key is required.")
    return value


def _assert_metadata_schema(connection: sqlite3.Connection) -> None:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN (?, ?, ?)",
        METADATA_TABLES,
    ).fetchall()
    present = {str(row[0]) for row in rows}
    missing = sorted(set(METADATA_TABLES) - present)
    if missing:
        raise SqlServerAdapterError(
            "SQLSERVER_METADATA_SCHEMA_UNAVAILABLE",
            "SQL Server snapshot metadata tables require a guarded central schema migration.",
            recovery_action="Apply the reviewed AIBI-C schema migration before using catalog, plan, or execute.",
            details={"missingTables": missing},
        )


def _active_workspace(connection: sqlite3.Connection) -> str:
    workspace_id = str(active_workspace_id(connection) or "").strip()
    if not workspace_id:
        raise SqlServerAdapterError("SQLSERVER_WORKSPACE_UNAVAILABLE", "An active workspace is required.")
    return workspace_id


def _connector_row(
    connection: sqlite3.Connection,
    connector_key: str,
    *,
    require_active: bool,
) -> tuple[str, sqlite3.Row]:
    workspace_id = _active_workspace(connection)
    row = connection.execute(
        """
        SELECT connector_key, workspace_id, name, connector_type, provider, status, config_json
        FROM data_connectors
        WHERE workspace_id = ? AND connector_key = ?
        """,
        (workspace_id, connector_key),
    ).fetchone()
    if row is None:
        raise SqlServerAdapterError("SQLSERVER_CONNECTOR_NOT_FOUND", "The SQL Server connector was not found in the active workspace.")
    if str(row["connector_type"]).casefold() != "sqlserver":
        raise SqlServerAdapterError("SQLSERVER_CONNECTOR_TYPE_INVALID", "The selected connector is not a SQL Server snapshot connector.")
    if require_active and str(row["status"]).casefold() != "active":
        raise SqlServerAdapterError("SQLSERVER_CONNECTOR_NOT_ACTIVE", "The SQL Server connector must be active before a remote read.")
    return workspace_id, row


def _adapter_config(workspace_id: str, row: sqlite3.Row) -> dict[str, Any]:
    raw_text = str(row["config_json"] or "")
    if not raw_text or len(raw_text.encode("utf-8")) > 16 * 1024:
        raise SqlServerAdapterError("SQLSERVER_CONNECTOR_CONFIG_INVALID", "The SQL Server connector configuration is missing or too large.")
    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise SqlServerAdapterError("SQLSERVER_CONNECTOR_CONFIG_INVALID", "The SQL Server connector configuration is invalid JSON.") from error
    if not isinstance(raw, dict):
        raise SqlServerAdapterError("SQLSERVER_CONNECTOR_CONFIG_INVALID", "The SQL Server connector configuration must be an object.")
    forbidden = sorted(str(key) for key in raw if str(key).casefold() in _FORBIDDEN_CONFIG_KEYS)
    if forbidden:
        raise SqlServerAdapterError(
            "SQLSERVER_CONNECTOR_SECRET_SURFACE_FORBIDDEN",
            "SQL Server connector configuration contains a forbidden credential or connection-string field.",
        )
    credential_ref = validate_credential_reference(raw.get("credentialRef"))
    return {
        "workspaceId": workspace_id,
        "hostAlias": str(raw.get("hostAlias") or "").strip().casefold(),
        "port": raw.get("port") or 1433,
        "database": str(raw.get("database") or "").strip(),
        "encryption": str(raw.get("encryption") or "required").strip().casefold(),
        "credentialRef": credential_ref,
    }


def _connector_context(
    connection: sqlite3.Connection,
    connector_key: str,
    *,
    require_active: bool,
) -> tuple[str, sqlite3.Row, dict[str, Any]]:
    workspace_id, row = _connector_row(connection, connector_key, require_active=require_active)
    return workspace_id, row, _adapter_config(workspace_id, row)


def _connector_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "connectorKey": str(row["connector_key"]),
        "name": str(row["name"]),
        "type": "sqlserver",
        "provider": str(row["provider"]),
        "status": str(row["status"]),
    }


def _catalog_row(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    connector_key: str,
    catalog_fingerprint: str,
) -> dict[str, Any]:
    if not _FINGERPRINT_RE.fullmatch(catalog_fingerprint):
        raise SqlServerAdapterError("SQLSERVER_CATALOG_FINGERPRINT_INVALID", "A valid catalog fingerprint is required.")
    row = connection.execute(
        """
        SELECT catalog_json FROM sqlserver_snapshot_catalogs
        WHERE workspace_id = ? AND connector_key = ? AND catalog_fingerprint = ?
        """,
        (workspace_id, connector_key, catalog_fingerprint),
    ).fetchone()
    if row is None:
        raise SqlServerAdapterError("SQLSERVER_CATALOG_NOT_FOUND", "The reviewed SQL Server catalog was not found in this workspace.")
    try:
        catalog = json.loads(str(row[0]))
    except json.JSONDecodeError as error:
        raise SqlServerAdapterError("SQLSERVER_CATALOG_INTEGRITY_FAILED", "The persisted SQL Server catalog is unreadable.") from error
    if not isinstance(catalog, dict):
        raise SqlServerAdapterError("SQLSERVER_CATALOG_INTEGRITY_FAILED", "The persisted SQL Server catalog is invalid.")
    verify_catalog(catalog)
    return catalog


def _persist_catalog(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    connector_key: str,
    catalog: Mapping[str, Any],
    created_at: str,
) -> None:
    verify_catalog(catalog)
    payload = json.dumps(catalog, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if any(key in payload for key in ('"credentialRef"', '"password"', '"connectionString"', '"rows"')):
        raise SqlServerAdapterError("SQLSERVER_METADATA_SECRET_BLOCKED", "Unsafe SQL Server catalog content was blocked before persistence.")
    connection.execute(
        """
        INSERT OR IGNORE INTO sqlserver_snapshot_catalogs(
          workspace_id, connector_key, catalog_fingerprint, network_binding_fingerprint, catalog_json, created_at
        ) VALUES(?, ?, ?, ?, ?, ?)
        """,
        (
            workspace_id,
            connector_key,
            str(catalog["catalogFingerprint"]),
            str(catalog["networkBindingFingerprint"]),
            payload,
            created_at,
        ),
    )


def _plan_input_fingerprint(
    *,
    connector_key: str,
    config: Mapping[str, Any],
    catalog_fingerprint: str,
    selections: Sequence[Mapping[str, Any]],
    budget: Mapping[str, Any],
) -> str:
    public_config = {key: value for key, value in config.items() if key != "credentialRef"}
    public_config["credentialConfigured"] = True
    return stable_fingerprint({
        "connectorKey": connector_key,
        "config": public_config,
        "catalogFingerprint": catalog_fingerprint,
        "selections": list(selections),
        "budget": dict(budget),
    })


def _persist_plan(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    connector_key: str,
    request_key: str,
    input_fingerprint: str,
    plan: Mapping[str, Any],
    timestamp: str,
) -> None:
    verify_snapshot_plan(plan)
    payload = json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if any(key in payload for key in ('"credentialRef"', '"password"', '"connectionString"', '"rows"')):
        raise SqlServerAdapterError("SQLSERVER_METADATA_SECRET_BLOCKED", "Unsafe SQL Server plan content was blocked before persistence.")
    connection.execute(
        """
        INSERT INTO sqlserver_snapshot_plans(
          workspace_id, connector_key, plan_fingerprint, request_key, input_fingerprint,
          status, artifact_key, plan_json, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, 'planned', NULL, ?, ?, ?)
        """,
        (
            workspace_id,
            connector_key,
            str(plan["planFingerprint"]),
            request_key,
            input_fingerprint,
            payload,
            timestamp,
            timestamp,
        ),
    )


def _stored_plan(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    connector_key: str,
    request_key: str,
) -> tuple[sqlite3.Row, dict[str, Any]] | None:
    row = connection.execute(
        """
        SELECT * FROM sqlserver_snapshot_plans
        WHERE workspace_id = ? AND connector_key = ? AND request_key = ?
        """,
        (workspace_id, connector_key, request_key),
    ).fetchone()
    if row is None:
        return None
    try:
        plan = json.loads(str(row["plan_json"]))
    except json.JSONDecodeError as error:
        raise SqlServerAdapterError("SQLSERVER_PLAN_INTEGRITY_FAILED", "The persisted SQL Server snapshot plan is unreadable.") from error
    if not isinstance(plan, dict):
        raise SqlServerAdapterError("SQLSERVER_PLAN_INTEGRITY_FAILED", "The persisted SQL Server snapshot plan is invalid.")
    verify_snapshot_plan(plan)
    if plan.get("planFingerprint") != row["plan_fingerprint"]:
        raise SqlServerAdapterError("SQLSERVER_PLAN_INTEGRITY_FAILED", "The persisted SQL Server snapshot plan fingerprint is inconsistent.")
    return row, plan


def _stored_plan_by_fingerprint(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    connector_key: str,
    plan_fingerprint: str,
) -> tuple[sqlite3.Row, dict[str, Any]]:
    if not _FINGERPRINT_RE.fullmatch(plan_fingerprint):
        raise SqlServerAdapterError("SQLSERVER_PLAN_FINGERPRINT_INVALID", "A valid SQL Server plan fingerprint is required.")
    row = connection.execute(
        """
        SELECT * FROM sqlserver_snapshot_plans
        WHERE workspace_id = ? AND connector_key = ? AND plan_fingerprint = ?
        """,
        (workspace_id, connector_key, plan_fingerprint),
    ).fetchone()
    if row is None:
        raise SqlServerAdapterError("SQLSERVER_PLAN_NOT_FOUND", "The reviewed SQL Server snapshot plan was not found.")
    try:
        plan = json.loads(str(row["plan_json"]))
    except json.JSONDecodeError as error:
        raise SqlServerAdapterError("SQLSERVER_PLAN_INTEGRITY_FAILED", "The persisted SQL Server snapshot plan is unreadable.") from error
    if not isinstance(plan, dict):
        raise SqlServerAdapterError("SQLSERVER_PLAN_INTEGRITY_FAILED", "The persisted SQL Server snapshot plan is invalid.")
    verify_snapshot_plan(plan)
    if plan.get("planFingerprint") != plan_fingerprint:
        raise SqlServerAdapterError("SQLSERVER_PLAN_INTEGRITY_FAILED", "The persisted SQL Server plan fingerprint is inconsistent.")
    return row, plan


def _stored_snapshot_receipt(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    connector_key: str,
    plan_fingerprint: str,
) -> dict[str, Any]:
    row = connection.execute(
        """
        SELECT receipt_json FROM sqlserver_snapshot_receipts
        WHERE workspace_id = ? AND connector_key = ? AND plan_fingerprint = ? AND operation = 'snapshot'
        """,
        (workspace_id, connector_key, plan_fingerprint),
    ).fetchone()
    if row is None:
        raise SqlServerAdapterError("SQLSERVER_SNAPSHOT_RECEIPT_NOT_FOUND", "The SQL Server plan has no sealed staging receipt.")
    try:
        receipt = json.loads(str(row[0]))
    except json.JSONDecodeError as error:
        raise SqlServerAdapterError("SQLSERVER_RECEIPT_INTEGRITY_FAILED", "The persisted SQL Server snapshot receipt is unreadable.") from error
    if (
        not isinstance(receipt, dict)
        or receipt.get("operation") != "snapshot"
        or receipt.get("planFingerprint") != plan_fingerprint
        or not _FINGERPRINT_RE.fullmatch(str(receipt.get("manifestFingerprint") or ""))
    ):
        raise SqlServerAdapterError("SQLSERVER_RECEIPT_INTEGRITY_FAILED", "The persisted SQL Server snapshot receipt is invalid.")
    return receipt


def _stored_activation_receipt(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    connector_key: str,
    plan_fingerprint: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT receipt_fingerprint, receipt_json FROM sqlserver_snapshot_receipts
        WHERE workspace_id = ? AND connector_key = ? AND plan_fingerprint = ? AND operation = 'activate'
        """,
        (workspace_id, connector_key, plan_fingerprint),
    ).fetchone()
    if row is None:
        return None
    try:
        receipt = json.loads(str(row["receipt_json"]))
    except json.JSONDecodeError as error:
        raise SqlServerAdapterError("SQLSERVER_RECEIPT_INTEGRITY_FAILED", "The persisted SQL Server activation receipt is unreadable.") from error
    if (
        not isinstance(receipt, dict)
        or receipt.get("schema") != "aibi-sqlserver-snapshot-receipt/v1"
        or receipt.get("operation") != "activate"
        or receipt.get("workspaceId") != workspace_id
        or receipt.get("connectorKey") != connector_key
        or receipt.get("planFingerprint") != plan_fingerprint
        or receipt.get("capability") != "active"
        or stable_fingerprint(receipt) != str(row["receipt_fingerprint"])
    ):
        raise SqlServerAdapterError("SQLSERVER_RECEIPT_INTEGRITY_FAILED", "The persisted SQL Server activation receipt is invalid.")
    return receipt


def _activation_import_request_key(*, workspace_id: str, connector_key: str, request_key: str) -> str:
    return ACTIVATION_REQUEST_PREFIX + stable_fingerprint({
        "schema": "aibi-sqlserver-activation-request/v1",
        "workspaceId": workspace_id,
        "connectorKey": connector_key,
        "requestKey": request_key,
    })


def _activation_request_key(args: argparse.Namespace) -> str:
    value = str(getattr(args, "request_key", "") or "").strip()
    if not value or len(value) > 160:
        raise SqlServerAdapterError("SQLSERVER_ACTIVATION_REQUEST_KEY_INVALID", "Activation requestKey is required and must be at most 160 characters.")
    return value


def _activation_context(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    staging_root: Path,
) -> tuple[str, sqlite3.Row, dict[str, Any], sqlite3.Row, dict[str, Any], dict[str, Any], Path]:
    connector_key = _connector_key(args)
    expected_plan = str(getattr(args, "expected_plan", "") or "").strip()
    expected_manifest = str(getattr(args, "expected_manifest", "") or "").strip()
    if not _FINGERPRINT_RE.fullmatch(expected_plan) or not _FINGERPRINT_RE.fullmatch(expected_manifest):
        raise SqlServerAdapterError(
            "SQLSERVER_ACTIVATION_BINDING_REQUIRED",
            "Activation requires the exact reviewed plan and sealed manifest fingerprints.",
        )
    with open_db() as connection:
        _assert_metadata_schema(connection)
        workspace_id, connector_row, _config = _connector_context(connection, connector_key, require_active=True)
        requested_workspace = str(getattr(args, "workspace", "") or "").strip()
        if requested_workspace and requested_workspace != workspace_id:
            raise SqlServerAdapterError("SQLSERVER_WORKSPACE_SCOPE_MISMATCH", "The SQL Server activation belongs to another active workspace.")
        plan_row, plan = _stored_plan_by_fingerprint(
            connection,
            workspace_id=workspace_id,
            connector_key=connector_key,
            plan_fingerprint=expected_plan,
        )
        if str(plan_row["status"]) not in {"staged", "activated"}:
            raise SqlServerAdapterError("SQLSERVER_SNAPSHOT_NOT_STAGED", "The reviewed SQL Server plan has not produced a sealed staging artifact.")
        receipt = _stored_snapshot_receipt(
            connection,
            workspace_id=workspace_id,
            connector_key=connector_key,
            plan_fingerprint=expected_plan,
        )
    if receipt.get("manifestFingerprint") != expected_manifest:
        raise SqlServerAdapterError(
            "SQLSERVER_MANIFEST_FINGERPRINT_MISMATCH",
            "The staged SQL Server manifest does not match the confirmed activation input.",
        )
    artifact_path, verified_receipt = verified_staged_snapshot(
        plan,
        staging_root=staging_root,
        expected_manifest_fingerprint=expected_manifest,
    )
    if (
        verified_receipt.get("artifactKey") != receipt.get("artifactKey")
        or verified_receipt.get("manifestFingerprint") != receipt.get("manifestFingerprint")
    ):
        raise SqlServerAdapterError("SQLSERVER_RECEIPT_INTEGRITY_FAILED", "The sealed staging artifact no longer matches its persisted receipt.")
    return workspace_id, connector_row, plan, plan_row, receipt, verified_receipt, artifact_path


def _persist_snapshot_receipt(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    connector_key: str,
    plan: Mapping[str, Any],
    receipt: Mapping[str, Any],
    timestamp: str,
) -> str:
    payload = json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if any(key in payload for key in ('"credentialRef"', '"password"', '"connectionString"', '"rows"')):
        raise SqlServerAdapterError("SQLSERVER_METADATA_SECRET_BLOCKED", "Unsafe SQL Server receipt content was blocked before persistence.")
    receipt_fingerprint = stable_fingerprint(receipt)
    connection.execute(
        """
        INSERT INTO sqlserver_snapshot_receipts(
          workspace_id, connector_key, receipt_fingerprint, plan_fingerprint,
          operation, artifact_key, receipt_json, created_at
        ) VALUES(?, ?, ?, ?, 'snapshot', ?, ?, ?)
        ON CONFLICT(workspace_id, connector_key, plan_fingerprint, operation) DO NOTHING
        """,
        (
            workspace_id,
            connector_key,
            receipt_fingerprint,
            str(plan["planFingerprint"]),
            str(receipt.get("artifactKey") or ""),
            payload,
            timestamp,
        ),
    )
    connection.execute(
        """
        UPDATE sqlserver_snapshot_plans
        SET status = 'staged', artifact_key = ?, updated_at = ?
        WHERE workspace_id = ? AND connector_key = ? AND plan_fingerprint = ?
        """,
        (
            str(receipt.get("artifactKey") or ""),
            timestamp,
            workspace_id,
            connector_key,
            str(plan["planFingerprint"]),
        ),
    )
    stored = connection.execute(
        """
        SELECT receipt_fingerprint FROM sqlserver_snapshot_receipts
        WHERE workspace_id = ? AND connector_key = ? AND plan_fingerprint = ? AND operation = 'snapshot'
        """,
        (workspace_id, connector_key, str(plan["planFingerprint"])),
    ).fetchone()
    if stored is None:
        raise SqlServerAdapterError("SQLSERVER_RECEIPT_PERSIST_FAILED", "The SQL Server snapshot receipt was not persisted.")
    return str(stored[0])


def sqlserver_capability_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    driver: SqlServerDriver | None = None,
    policies: Mapping[str, Mapping[str, Any]] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    environment = _environment(environ)
    connector_key = _connector_key(args, required=False)
    driver_reason: str | None = None
    try:
        resolved_driver = _driver(driver, environment, for_probe=True)
    except SqlServerAdapterError as error:
        # Capability discovery must stay usable when the explicitly requested
        # optional runtime is absent.  Network operations still fail closed.
        resolved_driver = _UnavailableDriver()
        driver_reason = str(error)
    resolved_policies = _policies(policies, environment)
    if not connector_key:
        contract = adapter_contract(None, driver=resolved_driver, policies=resolved_policies, environ=environment)
        if driver_reason:
            contract["reason"] = driver_reason
        elif driver is None and environment.get(REAL_DRIVER_ENABLE_ENV) != "1":
            contract["reason"] = f"Real SQL Server access is disabled until {REAL_DRIVER_ENABLE_ENV}=1."
        return {"ok": True, "operation": "capability", "adapter": contract}
    with open_db() as connection:
        _workspace_id, row, config = _connector_context(connection, connector_key, require_active=False)
    contract = adapter_contract(config, driver=resolved_driver, policies=resolved_policies, environ=environment)
    if str(row["status"]).casefold() != "active":
        contract.update({
            "available": False,
            "capability": "unavailable",
            "operations": ["probe"],
            "reason": "The saved SQL Server connector is not active.",
        })
    elif driver_reason:
        contract["reason"] = driver_reason
    elif driver is None and environment.get(REAL_DRIVER_ENABLE_ENV) != "1":
        contract["reason"] = f"Real SQL Server access is disabled until {REAL_DRIVER_ENABLE_ENV}=1."
    return {"ok": True, "operation": "capability", "connector": _connector_public(row), "adapter": contract}


def sqlserver_test_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    driver: SqlServerDriver | None = None,
    policies: Mapping[str, Mapping[str, Any]] | None = None,
    resolver: Callable[[str, int], Sequence[str]] | None = None,
    environ: Mapping[str, str] | None = None,
    cancelled: Callable[[], bool] = lambda: False,
) -> dict[str, Any]:
    environment = _environment(environ)
    connector_key = _connector_key(args)
    with open_db() as connection:
        _workspace_id, row, config = _connector_context(connection, connector_key, require_active=True)
    options: dict[str, Any] = {
        "driver": _driver(driver, environment),
        "policies": _policies(policies, environment),
        "environ": environment,
        "timeout_seconds": _bounded_int(getattr(args, "timeout", None), default=10, minimum=1, maximum=30, label="timeout"),
        "cancelled": cancelled,
    }
    if resolver is not None:
        options["resolver"] = resolver
    receipt = test_connection(config, **options)
    return {**receipt, "connector": _connector_public(row)}


def sqlserver_catalog_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    driver: SqlServerDriver | None = None,
    policies: Mapping[str, Mapping[str, Any]] | None = None,
    resolver: Callable[[str, int], Sequence[str]] | None = None,
    environ: Mapping[str, str] | None = None,
    cancelled: Callable[[], bool] = lambda: False,
    now: Callable[[], str] = now_iso,
) -> dict[str, Any]:
    environment = _environment(environ)
    connector_key = _connector_key(args)
    with open_db() as connection:
        _assert_metadata_schema(connection)
        workspace_id, row, config = _connector_context(connection, connector_key, require_active=True)
    options: dict[str, Any] = {
        "driver": _driver(driver, environment),
        "policies": _policies(policies, environment),
        "environ": environment,
        "max_tables": _bounded_int(getattr(args, "max_tables", None), default=8, minimum=1, maximum=32, label="maxTables"),
        "max_columns_per_table": _bounded_int(getattr(args, "max_columns", None), default=64, minimum=1, maximum=256, label="maxColumns"),
        "timeout_seconds": _bounded_int(getattr(args, "timeout", None), default=30, minimum=1, maximum=900, label="timeout"),
        "cancelled": cancelled,
    }
    if resolver is not None:
        options["resolver"] = resolver
    catalog = discover_catalog(config, **options)
    with open_db() as connection:
        _assert_metadata_schema(connection)
        current_workspace, _current_row, current_config = _connector_context(connection, connector_key, require_active=True)
        if current_workspace != workspace_id or {key: value for key, value in current_config.items() if key != "credentialRef"} != {key: value for key, value in config.items() if key != "credentialRef"}:
            raise SqlServerAdapterError("SQLSERVER_CONNECTOR_DRIFT", "The SQL Server connector changed during catalog discovery.")
        _persist_catalog(connection, workspace_id=workspace_id, connector_key=connector_key, catalog=catalog, created_at=now())
        connection.commit()
    return {**catalog, "connector": _connector_public(row), "persistedMetadata": True}


def sqlserver_statistics_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    driver: SqlServerDriver | None = None,
    policies: Mapping[str, Mapping[str, Any]] | None = None,
    resolver: Callable[[str, int], Sequence[str]] | None = None,
    environ: Mapping[str, str] | None = None,
    cancelled: Callable[[], bool] = lambda: False,
) -> dict[str, Any]:
    environment = _environment(environ)
    connector_key = _connector_key(args)
    catalog_fingerprint = str(getattr(args, "catalog", "") or "").strip()
    resources = [item.strip() for item in str(getattr(args, "resources", "") or "").split(",") if item.strip()]
    if not resources or len(resources) > 32:
        raise SqlServerAdapterError("SQLSERVER_SELECTION_INVALID", "One through 32 current catalog resources are required.")
    with open_db() as connection:
        _assert_metadata_schema(connection)
        workspace_id, row, config = _connector_context(connection, connector_key, require_active=True)
        catalog = _catalog_row(
            connection,
            workspace_id=workspace_id,
            connector_key=connector_key,
            catalog_fingerprint=catalog_fingerprint,
        )
    options: dict[str, Any] = {
        "driver": _driver(driver, environment),
        "policies": _policies(policies, environment),
        "environ": environment,
        "sample_rows": _bounded_int(getattr(args, "sample_rows", None), default=200, minimum=1, maximum=1000, label="sampleRows"),
        "timeout_seconds": _bounded_int(getattr(args, "timeout", None), default=30, minimum=1, maximum=900, label="timeout"),
        "cancelled": cancelled,
    }
    if resolver is not None:
        options["resolver"] = resolver
    receipt = preview_statistics(config, catalog, resources, **options)
    return {**receipt, "connector": _connector_public(row), "persistedMetadata": False}


def sqlserver_plan_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    now: Callable[[], str] = now_iso,
) -> dict[str, Any]:
    connector_key = _connector_key(args)
    catalog_fingerprint = str(getattr(args, "catalog", "") or "").strip()
    request_key = str(getattr(args, "request_key", "") or "").strip()
    if not request_key or len(request_key) > 200:
        raise SqlServerAdapterError("SQLSERVER_REQUEST_KEY_INVALID", "requestKey is required and must be at most 200 characters.")
    selections = _json_list(getattr(args, "selections_json", ""), label="selections", max_bytes=20_000, max_items=32)
    budget = _json_object(getattr(args, "budget_json", "{}"), label="budget", max_bytes=2_000)
    with open_db() as connection:
        _assert_metadata_schema(connection)
        workspace_id, _row, config = _connector_context(connection, connector_key, require_active=True)
        catalog = _catalog_row(
            connection,
            workspace_id=workspace_id,
            connector_key=connector_key,
            catalog_fingerprint=catalog_fingerprint,
        )
        input_fingerprint = _plan_input_fingerprint(
            connector_key=connector_key,
            config=config,
            catalog_fingerprint=catalog_fingerprint,
            selections=selections,
            budget=budget,
        )
        existing = _stored_plan(
            connection,
            workspace_id=workspace_id,
            connector_key=connector_key,
            request_key=request_key,
        )
        if existing is not None:
            row, plan = existing
            if str(row["input_fingerprint"]) != input_fingerprint:
                raise SqlServerAdapterError(
                    "SQLSERVER_REQUEST_KEY_CONFLICT",
                    "The requestKey is already bound to a different SQL Server snapshot input.",
                )
            return {**plan, "idempotentReplay": True, "status": str(row["status"]), "artifactKey": row["artifact_key"]}
        timestamp = now()
        plan = build_snapshot_plan(
            config,
            catalog,
            selections,
            request_key=request_key,
            budget=budget,
            created_at=timestamp,
        )
        _persist_plan(
            connection,
            workspace_id=workspace_id,
            connector_key=connector_key,
            request_key=request_key,
            input_fingerprint=input_fingerprint,
            plan=plan,
            timestamp=timestamp,
        )
        connection.commit()
    return {**plan, "idempotentReplay": False, "status": "planned"}


def sqlserver_execute_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    driver: SqlServerDriver | None = None,
    policies: Mapping[str, Mapping[str, Any]] | None = None,
    resolver: Callable[[str, int], Sequence[str]] | None = None,
    environ: Mapping[str, str] | None = None,
    staging_root: Path | None = None,
    cancelled: Callable[[], bool] = lambda: False,
    now: Callable[[], str] = now_iso,
) -> dict[str, Any]:
    if getattr(args, "yes", False) is not True:
        raise SqlServerAdapterError(
            "SQLSERVER_SNAPSHOT_CONFIRMATION_REQUIRED",
            "Snapshot execution requires explicit confirmation and the exact reviewed plan fingerprint.",
        )
    connector_key = _connector_key(args)
    request_key = str(getattr(args, "request_key", "") or "").strip()
    expected_plan = str(getattr(args, "expected_plan", "") or "").strip()
    if not request_key or len(request_key) > 200 or not _FINGERPRINT_RE.fullmatch(expected_plan):
        raise SqlServerAdapterError(
            "SQLSERVER_SNAPSHOT_CONFIRMATION_REQUIRED",
            "Snapshot execution requires requestKey and the exact reviewed plan fingerprint.",
        )
    with open_db() as connection:
        _assert_metadata_schema(connection)
        workspace_id, row, config = _connector_context(connection, connector_key, require_active=True)
        stored = _stored_plan(
            connection,
            workspace_id=workspace_id,
            connector_key=connector_key,
            request_key=request_key,
        )
        if stored is None:
            raise SqlServerAdapterError("SQLSERVER_PLAN_NOT_FOUND", "The reviewed SQL Server snapshot plan was not found.")
        plan_row, plan = stored
        if plan.get("planFingerprint") != expected_plan:
            raise SqlServerAdapterError("SQLSERVER_PLAN_FINGERPRINT_MISMATCH", "The confirmed SQL Server plan fingerprint does not match.")
    environment = _environment(environ)
    options: dict[str, Any] = {
        "driver": _driver(driver, environment),
        "policies": _policies(policies, environment),
        "staging_root": Path(staging_root) if staging_root is not None else DB_PATH.parent / "sqlserver-staging",
        "environ": environment,
        "cancelled": cancelled,
        "now": now,
    }
    if resolver is not None:
        options["resolver"] = resolver
    receipt = snapshot_to_staging(config, plan, **options)
    timestamp = now()
    with open_db() as connection:
        _assert_metadata_schema(connection)
        current_workspace, _current_row, current_config = _connector_context(connection, connector_key, require_active=True)
        if current_workspace != workspace_id or current_config != config:
            raise SqlServerAdapterError("SQLSERVER_CONNECTOR_DRIFT", "The SQL Server connector changed during snapshot execution.")
        current = _stored_plan(
            connection,
            workspace_id=workspace_id,
            connector_key=connector_key,
            request_key=request_key,
        )
        if current is None or current[1].get("planFingerprint") != expected_plan:
            raise SqlServerAdapterError("SQLSERVER_PLAN_DRIFT", "The SQL Server snapshot plan changed during execution.")
        receipt_fingerprint = _persist_snapshot_receipt(
            connection,
            workspace_id=workspace_id,
            connector_key=connector_key,
            plan=plan,
            receipt=receipt,
            timestamp=timestamp,
        )
        connection.commit()
    return {
        **receipt,
        "connector": _connector_public(row),
        "receiptFingerprint": receipt_fingerprint,
        "durableImportRequired": True,
        "activationJournalRequired": True,
        "previousStatus": str(plan_row["status"]),
    }


def _default_folder_import_preview(args: argparse.Namespace) -> dict[str, Any]:
    from bi_cli_source_commands import preview_import_folder_command

    return preview_import_folder_command(args)


def _default_import_job_create(args: argparse.Namespace) -> dict[str, Any]:
    from import_job_commands import import_job_create_command

    return import_job_create_command(args)


def _validate_activation_import_plan(
    import_plan: Mapping[str, Any],
    *,
    workspace_id: str,
    snapshot_receipt: Mapping[str, Any],
) -> None:
    expected_tables = sorted(
        str(item.get("targetTableKey") or "")
        for item in snapshot_receipt.get("tables") or []
        if isinstance(item, Mapping)
    )
    actual_tables = sorted(
        str(item.get("tableKey") or "")
        for item in import_plan.get("items") or []
        if isinstance(item, Mapping)
    )
    if (
        import_plan.get("readyToCommit") is not True
        or str(import_plan.get("workspaceId") or "") != workspace_id
        or int(import_plan.get("fileCount") or 0) != len(expected_tables)
        or actual_tables != expected_tables
        or not _FINGERPRINT_RE.fullmatch(str(import_plan.get("planFingerprint") or ""))
    ):
        raise SqlServerAdapterError(
            "SQLSERVER_DURABLE_IMPORT_PLAN_INVALID",
            "The sealed SQL Server artifact did not produce the expected workspace-bound durable import plan.",
            details={"blockers": list(import_plan.get("blockers") or [])[:20]},
        )


def _activation_job_binding(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    job_key: str,
    artifact_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    from job_runtime_service import get_job, job_input

    job = get_job(connection, workspace_id=workspace_id, job_key=job_key, event_limit=100)
    stored_input = job_input(connection, workspace_id=workspace_id, job_key=job_key)
    public_input = stored_input.get("public") if isinstance(stored_input.get("public"), dict) else {}
    private_input = stored_input.get("private") if isinstance(stored_input.get("private"), dict) else {}
    try:
        bound_path = Path(str(private_input.get("path") or "")).resolve()
    except (OSError, RuntimeError) as error:
        raise SqlServerAdapterError("SQLSERVER_ACTIVATION_JOB_BINDING_INVALID", "The durable import has an invalid private artifact binding.") from error
    if (
        str(job.get("kind") or "") != "import"
        or str(job.get("workspaceId") or "") != workspace_id
        or str(private_input.get("workspaceId") or "") != workspace_id
        or str(private_input.get("importKind") or "") != "folder"
        or private_input.get("recursive") is not False
        or bound_path != artifact_path.resolve()
        or str(public_input.get("sourceName") or "") != artifact_path.name
        or str(private_input.get("expectedPlan") or "") != str(public_input.get("planFingerprint") or "")
        or not _FINGERPRINT_RE.fullmatch(str(public_input.get("planFingerprint") or ""))
    ):
        raise SqlServerAdapterError(
            "SQLSERVER_ACTIVATION_JOB_BINDING_INVALID",
            "The durable import job is not bound to the sealed SQL Server staging artifact.",
        )
    return job, public_input, private_input


def _committed_activation_receipt(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    connector_key: str,
    plan: Mapping[str, Any],
    snapshot_receipt: Mapping[str, Any],
    job: Mapping[str, Any],
    import_plan_fingerprint: str,
) -> dict[str, Any] | None:
    from source_activation_journal_service import activation_for_job

    if str(job.get("status") or "") != "succeeded":
        return None
    result = job.get("result") if isinstance(job.get("result"), Mapping) else {}
    journal = activation_for_job(connection, workspace_id=workspace_id, job_key=str(job.get("jobKey") or ""))
    workspace = connection.execute(
        "SELECT current_source_run_id FROM workspaces WHERE id = ?",
        (workspace_id,),
    ).fetchone()
    current_source_run_id = str(workspace[0] or "") if workspace is not None else ""
    if (
        result.get("committed") is not True
        or journal is None
        or journal.get("workspaceId") != workspace_id
        or journal.get("jobKey") != job.get("jobKey")
        or journal.get("planFingerprint") != import_plan_fingerprint
        or journal.get("phase") != "finalized"
        or journal.get("outcome") != "committed"
        or result.get("activationJournalKey") != journal.get("journalKey")
        or result.get("sourceRunId") != journal.get("targetSourceRunId")
        or current_source_run_id != str(journal.get("targetSourceRunId") or "")
    ):
        return None
    return {
        "ok": True,
        "schema": "aibi-sqlserver-snapshot-receipt/v1",
        "operation": "activate",
        "workspaceId": workspace_id,
        "connectorKey": connector_key,
        "artifactKey": snapshot_receipt.get("artifactKey"),
        "planFingerprint": plan.get("planFingerprint"),
        "manifestFingerprint": snapshot_receipt.get("manifestFingerprint"),
        "importPlanFingerprint": import_plan_fingerprint,
        "capability": "active",
        "durableImport": {
            "jobKey": job.get("jobKey"),
            "status": "succeeded",
            "sourceRunId": result.get("sourceRunId"),
        },
        "activation": {
            "status": "committed",
            "journalKey": journal.get("journalKey"),
            "phase": "finalized",
        },
    }


def _persist_activation_receipt(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    connector_key: str,
    plan_fingerprint: str,
    receipt: Mapping[str, Any],
    timestamp: str,
) -> dict[str, Any]:
    payload = json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if any(key in payload for key in ('"credentialRef"', '"password"', '"connectionString"', '"path"', '"rows"')):
        raise SqlServerAdapterError("SQLSERVER_METADATA_SECRET_BLOCKED", "Unsafe SQL Server activation content was blocked before persistence.")
    receipt_fingerprint = stable_fingerprint(receipt)
    connection.execute(
        """
        INSERT INTO sqlserver_snapshot_receipts(
          workspace_id, connector_key, receipt_fingerprint, plan_fingerprint,
          operation, artifact_key, receipt_json, created_at
        ) VALUES(?, ?, ?, ?, 'activate', ?, ?, ?)
        ON CONFLICT(workspace_id, connector_key, plan_fingerprint, operation) DO NOTHING
        """,
        (
            workspace_id,
            connector_key,
            receipt_fingerprint,
            plan_fingerprint,
            str(receipt.get("artifactKey") or ""),
            payload,
            timestamp,
        ),
    )
    connection.execute(
        """
        UPDATE sqlserver_snapshot_plans
        SET status = 'activated', updated_at = ?
        WHERE workspace_id = ? AND connector_key = ? AND plan_fingerprint = ?
        """,
        (timestamp, workspace_id, connector_key, plan_fingerprint),
    )
    row = connection.execute(
        """
        SELECT receipt_json FROM sqlserver_snapshot_receipts
        WHERE workspace_id = ? AND connector_key = ? AND plan_fingerprint = ? AND operation = 'activate'
        """,
        (workspace_id, connector_key, plan_fingerprint),
    ).fetchone()
    if row is None:
        raise SqlServerAdapterError("SQLSERVER_ACTIVATION_RECEIPT_PERSIST_FAILED", "The SQL Server activation receipt was not persisted.")
    stored = json.loads(str(row[0]))
    if not isinstance(stored, dict):
        raise SqlServerAdapterError("SQLSERVER_RECEIPT_INTEGRITY_FAILED", "The persisted SQL Server activation receipt is invalid.")
    return stored


def sqlserver_activate_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    staging_root: Path | None = None,
    preview_folder: Callable[[argparse.Namespace], dict[str, Any]] = _default_folder_import_preview,
    create_import_job: Callable[[argparse.Namespace], dict[str, Any]] = _default_import_job_create,
) -> dict[str, Any]:
    if getattr(args, "yes", False) is not True:
        raise SqlServerAdapterError(
            "SQLSERVER_ACTIVATION_CONFIRMATION_REQUIRED",
            "Activation requires explicit confirmation of the reviewed plan and sealed manifest.",
        )
    request_key = _activation_request_key(args)
    root = Path(staging_root) if staging_root is not None else DB_PATH.parent / "sqlserver-staging"
    workspace_id, connector_row, plan, _plan_row, snapshot_receipt, verified_receipt, artifact_path = _activation_context(
        args,
        open_db=open_db,
        staging_root=root,
    )
    preview_args = argparse.Namespace(
        workspace=workspace_id,
        path=str(artifact_path),
        limit=max(1, min(len(verified_receipt.get("tables") or []), 32)),
        no_recursive=True,
        unique_fields=None,
        conflict_rule=None,
    )
    import_plan = preview_folder(preview_args)
    _validate_activation_import_plan(
        import_plan,
        workspace_id=workspace_id,
        snapshot_receipt=verified_receipt,
    )
    import_request_key = _activation_import_request_key(
        workspace_id=workspace_id,
        connector_key=str(connector_row["connector_key"]),
        request_key=request_key,
    )
    created = create_import_job(argparse.Namespace(
        workspace=workspace_id,
        import_kind="folder",
        path=str(artifact_path),
        request_key=import_request_key,
        expected_plan=str(import_plan["planFingerprint"]),
        table=None,
        name=None,
        mode="create",
        unique_fields=None,
        conflict_rule=None,
        no_recursive=True,
        limit=max(1, min(len(verified_receipt.get("tables") or []), 32)),
        label=f"SQL Server snapshot activation: {connector_row['name']}",
    ))
    job = created.get("job") if isinstance(created.get("job"), dict) else None
    if created.get("ok") is not True or job is None:
        raise SqlServerAdapterError("SQLSERVER_DURABLE_IMPORT_REJECTED", "The standard durable import runtime rejected the sealed SQL Server artifact.")
    return {
        "ok": True,
        "operation": "activate",
        "accepted": True,
        "replayed": created.get("replayed") is True,
        "workspaceId": workspace_id,
        "connector": _connector_public(connector_row),
        "artifactKey": snapshot_receipt.get("artifactKey"),
        "planFingerprint": plan.get("planFingerprint"),
        "manifestFingerprint": snapshot_receipt.get("manifestFingerprint"),
        "importPlanFingerprint": import_plan.get("planFingerprint"),
        "capability": "ready_for_snapshot",
        "job": job,
        "activation": {
            "status": str(job.get("status") or "queued"),
            "journalRequired": True,
        },
    }


def sqlserver_activation_status_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    staging_root: Path | None = None,
) -> dict[str, Any]:
    request_key = _activation_request_key(args)
    root = Path(staging_root) if staging_root is not None else DB_PATH.parent / "sqlserver-staging"
    workspace_id, connector_row, plan, _plan_row, snapshot_receipt, _verified_receipt, artifact_path = _activation_context(
        args,
        open_db=open_db,
        staging_root=root,
    )
    import_request_key = _activation_import_request_key(
        workspace_id=workspace_id,
        connector_key=str(connector_row["connector_key"]),
        request_key=request_key,
    )
    with open_db() as connection:
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(analysis_jobs)").fetchall()}
        job_row = None if "request_key" not in columns else connection.execute(
            """
            SELECT job_key FROM analysis_jobs
            WHERE workspace_id = ? AND kind = 'import' AND request_key = ?
            """,
            (workspace_id, import_request_key),
        ).fetchone()
        if job_row is None:
            return {
                "ok": True,
                "operation": "activation-status",
                "workspaceId": workspace_id,
                "connector": _connector_public(connector_row),
                "artifactKey": snapshot_receipt.get("artifactKey"),
                "planFingerprint": plan.get("planFingerprint"),
                "manifestFingerprint": snapshot_receipt.get("manifestFingerprint"),
                "capability": "ready_for_snapshot",
                "activation": {"status": "not_started", "journalRequired": True},
            }
        job, public_input, _private_input = _activation_job_binding(
            connection,
            workspace_id=workspace_id,
            job_key=str(job_row["job_key"]),
            artifact_path=artifact_path,
        )
        active = _committed_activation_receipt(
            connection,
            workspace_id=workspace_id,
            connector_key=str(connector_row["connector_key"]),
            plan=plan,
            snapshot_receipt=snapshot_receipt,
            job=job,
            import_plan_fingerprint=str(public_input.get("planFingerprint") or ""),
        )
    if active is not None:
        return {**active, "job": job}
    return {
        "ok": True,
        "operation": "activation-status",
        "workspaceId": workspace_id,
        "connector": _connector_public(connector_row),
        "artifactKey": snapshot_receipt.get("artifactKey"),
        "planFingerprint": plan.get("planFingerprint"),
        "manifestFingerprint": snapshot_receipt.get("manifestFingerprint"),
        "importPlanFingerprint": public_input.get("planFingerprint"),
        "capability": "ready_for_snapshot",
        "job": job,
        "activation": {
            "status": "finalization_pending" if str(job.get("status") or "") == "succeeded" else str(job.get("status") or "unknown"),
            "journalRequired": True,
        },
    }


def _finalize_activation_job(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    job_key: str,
    staging_root: Path,
    now: Callable[[], str],
) -> dict[str, Any]:
    from job_runtime_service import get_job, job_input

    job = get_job(connection, workspace_id=workspace_id, job_key=job_key, event_limit=100)
    request_row = connection.execute(
        "SELECT request_key FROM analysis_jobs WHERE workspace_id = ? AND job_key = ?",
        (workspace_id, job_key),
    ).fetchone()
    request_key = str(request_row[0] or "") if request_row is not None else ""
    if not request_key.startswith(ACTIVATION_REQUEST_PREFIX):
        return {"ok": True, "skipped": True, "jobKey": job_key, "reason": "not-sqlserver-activation"}
    stored_input = job_input(connection, workspace_id=workspace_id, job_key=job_key)
    private_input = stored_input.get("private") if isinstance(stored_input.get("private"), dict) else {}
    artifact_path = Path(str(private_input.get("path") or "")).resolve()
    rows = connection.execute(
        """
        SELECT connector_key, plan_fingerprint, plan_json, status FROM sqlserver_snapshot_plans
        WHERE workspace_id = ? AND artifact_key = ?
        """,
        (workspace_id, artifact_path.name),
    ).fetchall()
    if len(rows) != 1:
        raise SqlServerAdapterError("SQLSERVER_ACTIVATION_PLAN_NOT_FOUND", "The durable import is not bound to one staged SQL Server plan.")
    plan = json.loads(str(rows[0]["plan_json"]))
    if not isinstance(plan, dict):
        raise SqlServerAdapterError("SQLSERVER_PLAN_INTEGRITY_FAILED", "The persisted SQL Server snapshot plan is invalid.")
    verify_snapshot_plan(plan)
    connector_key = str(rows[0]["connector_key"])
    snapshot_receipt = _stored_snapshot_receipt(
        connection,
        workspace_id=workspace_id,
        connector_key=connector_key,
        plan_fingerprint=str(rows[0]["plan_fingerprint"]),
    )
    stored_activation = _stored_activation_receipt(
        connection,
        workspace_id=workspace_id,
        connector_key=connector_key,
        plan_fingerprint=str(rows[0]["plan_fingerprint"]),
    )
    if stored_activation is not None:
        try:
            artifact_path.relative_to(staging_root.resolve())
        except ValueError as error:
            raise SqlServerAdapterError(
                "SQLSERVER_ACTIVATION_JOB_BINDING_INVALID",
                "The durable import artifact is outside the owned SQL Server staging root.",
            ) from error
        if artifact_path.name != str(snapshot_receipt.get("artifactKey") or ""):
            raise SqlServerAdapterError(
                "SQLSERVER_ACTIVATION_JOB_BINDING_INVALID",
                "The durable import artifact key does not match the sealed SQL Server snapshot.",
            )
        replay_job, public_input, _private_input = _activation_job_binding(
            connection,
            workspace_id=workspace_id,
            job_key=job_key,
            artifact_path=artifact_path,
        )
        durable_import = stored_activation.get("durableImport") if isinstance(stored_activation.get("durableImport"), Mapping) else {}
        activation = stored_activation.get("activation") if isinstance(stored_activation.get("activation"), Mapping) else {}
        if (
            str(rows[0]["status"]) != "activated"
            or str(replay_job.get("status") or "") != "succeeded"
            or stored_activation.get("artifactKey") != snapshot_receipt.get("artifactKey")
            or stored_activation.get("manifestFingerprint") != snapshot_receipt.get("manifestFingerprint")
            or stored_activation.get("importPlanFingerprint") != public_input.get("planFingerprint")
            or durable_import.get("jobKey") != job_key
            or durable_import.get("status") != "succeeded"
            or activation.get("status") != "committed"
            or activation.get("phase") != "finalized"
        ):
            raise SqlServerAdapterError("SQLSERVER_RECEIPT_INTEGRITY_FAILED", "The persisted SQL Server activation receipt is inconsistent with its durable import binding.")
        return {
            "ok": True,
            "skipped": True,
            "replayed": True,
            "jobKey": job_key,
            "reason": "already-finalized",
            "activation": stored_activation,
        }
    verified_path, _verified_receipt = verified_staged_snapshot(
        plan,
        staging_root=staging_root,
        expected_manifest_fingerprint=str(snapshot_receipt.get("manifestFingerprint") or ""),
    )
    job, public_input, _private_input = _activation_job_binding(
        connection,
        workspace_id=workspace_id,
        job_key=job_key,
        artifact_path=verified_path,
    )
    if str(job.get("status") or "") != "succeeded":
        return {"ok": True, "skipped": True, "jobKey": job_key, "reason": f"job-{job.get('status')}"}
    receipt = _committed_activation_receipt(
        connection,
        workspace_id=workspace_id,
        connector_key=connector_key,
        plan=plan,
        snapshot_receipt=snapshot_receipt,
        job=job,
        import_plan_fingerprint=str(public_input.get("planFingerprint") or ""),
    )
    if receipt is None:
        raise SqlServerAdapterError("SQLSERVER_ACTIVATION_NOT_FINALIZED", "The durable import Journal has not finalized as committed.")
    stored = _persist_activation_receipt(
        connection,
        workspace_id=workspace_id,
        connector_key=connector_key,
        plan_fingerprint=str(plan["planFingerprint"]),
        receipt=receipt,
        timestamp=now(),
    )
    return {"ok": True, "skipped": False, "jobKey": job_key, "activation": stored}


def sqlserver_activation_finalize_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    staging_root: Path | None = None,
    now: Callable[[], str] = now_iso,
) -> dict[str, Any]:
    if getattr(args, "yes", False) is not True:
        raise SqlServerAdapterError("SQLSERVER_ACTIVATION_CONFIRMATION_REQUIRED", "Activation finalization requires explicit confirmation.")
    root = Path(staging_root) if staging_root is not None else DB_PATH.parent / "sqlserver-staging"
    requested_job = str(getattr(args, "job", "") or "").strip()
    all_jobs = getattr(args, "all", False) is True
    if bool(requested_job) == all_jobs:
        raise SqlServerAdapterError("SQLSERVER_ACTIVATION_FINALIZE_INPUT_INVALID", "Provide exactly one job key or --all.")
    with open_db() as connection:
        _assert_metadata_schema(connection)
        if all_jobs:
            rows = connection.execute(
                """
                SELECT workspace_id, job_key FROM analysis_jobs
                WHERE kind = 'import' AND request_key LIKE ?
                ORDER BY created_at, job_key
                """,
                (f"{ACTIVATION_REQUEST_PREFIX}%",),
            ).fetchall()
        else:
            workspace_id = str(getattr(args, "workspace", "") or "").strip() or _active_workspace(connection)
            rows = connection.execute(
                "SELECT workspace_id, job_key FROM analysis_jobs WHERE workspace_id = ? AND job_key = ?",
                (workspace_id, requested_job),
            ).fetchall()
            if not rows:
                raise SqlServerAdapterError("SQLSERVER_ACTIVATION_JOB_NOT_FOUND", "The durable import job was not found in the requested workspace.")
        finalized: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []
        for row in rows:
            try:
                finalized.append(_finalize_activation_job(
                    connection,
                    workspace_id=str(row["workspace_id"]),
                    job_key=str(row["job_key"]),
                    staging_root=root,
                    now=now,
                ))
            except SqlServerAdapterError as error:
                failed.append({"jobKey": str(row["job_key"]), "code": error.code, "error": str(error)})
        if failed:
            connection.rollback()
        else:
            connection.commit()
    return {
        "ok": not failed,
        "operation": "activation-finalize",
        "finalized": finalized,
        "failed": failed,
    }
