from __future__ import annotations

import base64
import csv
import hashlib
import importlib.util
import io
import ipaddress
import json
import os
import re
import shutil
import socket
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Protocol, Sequence


ADAPTER_SCHEMA = "aibi-connector-adapter/v1"
PLAN_SCHEMA = "aibi-sqlserver-snapshot-plan/v1"
CATALOG_SCHEMA = "aibi-sqlserver-catalog/v1"
RECEIPT_SCHEMA = "aibi-sqlserver-snapshot-receipt/v1"
ADAPTER_ID = "sqlserver-snapshot/v1"

CAPABILITY_UNAVAILABLE = "unavailable"
CAPABILITY_READY_FOR_TEST = "ready_for_test"
CAPABILITY_READY_FOR_SNAPSHOT = "ready_for_snapshot"
CAPABILITY_ACTIVE = "active"

DEFAULT_BUDGET = {
    "maxTables": 8,
    "maxColumnsPerTable": 64,
    "maxRowsPerTable": 100_000,
    "maxBytes": 100 * 1024 * 1024,
    "timeoutSeconds": 60,
    "pageSize": 1_000,
}
HARD_BUDGET = {
    "maxTables": 32,
    "maxColumnsPerTable": 256,
    "maxRowsPerTable": 1_000_000,
    "maxBytes": 1024 * 1024 * 1024,
    "timeoutSeconds": 900,
    "pageSize": 10_000,
}

_ALIAS_RE = re.compile(r"[a-z][a-z0-9_-]{0,63}")
_DATABASE_RE = re.compile(r"[^\x00-\x1f\x7f]{1,128}")
_IDENTIFIER_RE = re.compile(r"[^.\x00-\x1f\x7f]{1,128}")
_TARGET_TABLE_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,127}")
_SECRET_REF_RE = re.compile(r"env:([A-Za-z_][A-Za-z0-9_]{0,127})")
_COMPARABLE_WATERMARK_TYPES = {
    "bigint", "date", "datetime", "datetime2", "datetimeoffset", "decimal", "int",
    "numeric", "real", "smallint", "smalldatetime", "time", "timestamp", "tinyint",
    "uniqueidentifier",
}
_OPERATION_LOCK = threading.Lock()


class SqlServerAdapterError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        recovery_action: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.recovery_action = recovery_action
        self.details = dict(details or {})

    def public_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"ok": False, "code": self.code, "error": str(self)}
        if self.recovery_action:
            payload["recoveryAction"] = self.recovery_action
        if self.details:
            payload["details"] = self.details
        return payload


class SqlServerSession(Protocol):
    def peer_address(self) -> str: ...

    def verify_read_only(self) -> Mapping[str, Any]: ...

    def discover_catalog(
        self,
        *,
        max_tables: int,
        max_columns_per_table: int,
        deadline: float,
        cancelled: Callable[[], bool],
    ) -> Sequence[Mapping[str, Any]]: ...

    def preview_statistics(
        self,
        resource: Mapping[str, Any],
        *,
        columns: Sequence[str],
        sample_rows: int,
        deadline: float,
        cancelled: Callable[[], bool],
    ) -> Mapping[str, Any]: ...

    def describe_resources(
        self,
        resource_keys: Sequence[str],
        *,
        max_columns_per_table: int,
        deadline: float,
        cancelled: Callable[[], bool],
    ) -> Sequence[Mapping[str, Any]]: ...

    def iter_snapshot(
        self,
        selection: Mapping[str, Any],
        *,
        max_rows: int,
        page_size: int,
        deadline: float,
        cancelled: Callable[[], bool],
    ) -> Iterator[Mapping[str, Any]]: ...

    def close(self) -> None: ...


class SqlServerDriver(Protocol):
    name: str

    def available(self) -> bool: ...

    def connect(
        self,
        *,
        host: str,
        port: int,
        database: str,
        credential: Mapping[str, str],
        timeout_seconds: int,
        encryption: str,
    ) -> SqlServerSession: ...


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def stable_fingerprint(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _validate_workspace_id(value: Any) -> str:
    workspace_id = str(value or "").strip()
    if not workspace_id or len(workspace_id) > 128 or any(ord(char) < 32 for char in workspace_id):
        raise SqlServerAdapterError("SQLSERVER_WORKSPACE_INVALID", "A valid workspaceId is required.")
    return workspace_id


def validate_credential_reference(value: Any) -> str:
    reference = str(value or "").strip()
    if not _SECRET_REF_RE.fullmatch(reference):
        raise SqlServerAdapterError(
            "SQLSERVER_SECRET_REF_REQUIRED",
            "SQL Server credentials must use a server-side env:NAME Secret Ref.",
            recovery_action="Configure a dedicated read-only credential Secret Ref.",
        )
    return reference


def _load_credential(reference: str, environ: Mapping[str, str]) -> dict[str, str]:
    name = validate_credential_reference(reference)[4:]
    raw = str(environ.get(name) or "")
    if not raw:
        raise SqlServerAdapterError(
            "SQLSERVER_SECRET_UNAVAILABLE",
            "The configured SQL Server Secret Ref is unavailable.",
            recovery_action="Configure the referenced read-only credential and retry the connection test.",
        )
    if len(raw) > 4096:
        raise SqlServerAdapterError("SQLSERVER_SECRET_FORMAT_INVALID", "The SQL Server credential payload is invalid.")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise SqlServerAdapterError(
            "SQLSERVER_SECRET_FORMAT_INVALID",
            "The SQL Server Secret Ref must contain a JSON username/password object.",
        ) from error
    if not isinstance(payload, dict):
        raise SqlServerAdapterError("SQLSERVER_SECRET_FORMAT_INVALID", "The SQL Server credential payload is invalid.")
    if set(payload) - {"username", "password"}:
        raise SqlServerAdapterError(
            "SQLSERVER_SECRET_FORMAT_INVALID",
            "The SQL Server credential payload accepts only username and password.",
        )
    username = str(payload.get("username") or "")
    password = str(payload.get("password") or "")
    if not username or not password or len(username) > 256 or len(password) > 2048:
        raise SqlServerAdapterError("SQLSERVER_SECRET_FORMAT_INVALID", "The SQL Server credential payload is invalid.")
    return {"username": username, "password": password}


def parse_target_policies(raw: str | None = None, *, environ: Mapping[str, str] | None = None) -> dict[str, dict[str, Any]]:
    environment = environ if environ is not None else os.environ
    source = raw if raw is not None else str(environment.get("AIBI_SQLSERVER_CONNECTOR_TARGETS") or "")
    if not source.strip():
        return {}
    if len(source) > 64 * 1024:
        raise SqlServerAdapterError("SQLSERVER_ALLOWLIST_INVALID", "The SQL Server target allowlist exceeds its size limit.")
    try:
        payload = json.loads(source)
    except json.JSONDecodeError as error:
        raise SqlServerAdapterError(
            "SQLSERVER_ALLOWLIST_INVALID",
            "The SQL Server target allowlist is not valid JSON.",
        ) from error
    if not isinstance(payload, dict):
        raise SqlServerAdapterError("SQLSERVER_ALLOWLIST_INVALID", "The SQL Server target allowlist must be an object.")
    if len(payload) > 64:
        raise SqlServerAdapterError("SQLSERVER_ALLOWLIST_INVALID", "The SQL Server target allowlist exceeds its target limit.")
    normalized: dict[str, dict[str, Any]] = {}
    for raw_alias, raw_policy in payload.items():
        alias = str(raw_alias).strip().casefold()
        if not _ALIAS_RE.fullmatch(alias) or not isinstance(raw_policy, dict):
            raise SqlServerAdapterError("SQLSERVER_ALLOWLIST_INVALID", "Every SQL Server allowlist entry needs a safe alias and object policy.")
        host = str(raw_policy.get("host") or "").strip()
        raw_ports = raw_policy.get("ports")
        raw_databases = raw_policy.get("databases")
        raw_cidrs = raw_policy.get("allowedCidrs")
        if not isinstance(raw_ports, list) or not isinstance(raw_databases, list) or not isinstance(raw_cidrs, list):
            raise SqlServerAdapterError("SQLSERVER_ALLOWLIST_INVALID", "SQL Server ports, databases, and allowedCidrs must be arrays.")
        try:
            ports = sorted({int(item) for item in raw_ports})
        except (TypeError, ValueError) as error:
            raise SqlServerAdapterError("SQLSERVER_ALLOWLIST_INVALID", "SQL Server allowlist ports are invalid.") from error
        databases = sorted({str(item).strip() for item in raw_databases if str(item).strip()})
        cidrs = sorted({str(item).strip() for item in raw_cidrs if str(item).strip()})
        try:
            ipaddress.ip_address(host.split("%")[0])
            valid_host = True
        except ValueError:
            valid_host = bool(re.fullmatch(r"(?=.{1,253}$)[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", host))
        if not valid_host or not ports or not databases or not cidrs or any(not _DATABASE_RE.fullmatch(item) for item in databases):
            raise SqlServerAdapterError(
                "SQLSERVER_ALLOWLIST_INVALID",
                "Each SQL Server target must define host, ports, databases, and allowedCidrs.",
            )
        if any(port < 1 or port > 65535 for port in ports):
            raise SqlServerAdapterError("SQLSERVER_ALLOWLIST_INVALID", "SQL Server allowlist ports must be between 1 and 65535.")
        try:
            networks = [ipaddress.ip_network(item, strict=False) for item in cidrs]
        except ValueError as error:
            raise SqlServerAdapterError("SQLSERVER_ALLOWLIST_INVALID", "SQL Server allowedCidrs contains an invalid network.") from error
        normalized[alias] = {
            "host": host,
            "ports": ports,
            "databases": databases,
            "allowedCidrs": [str(item) for item in networks],
            "requireTls": raw_policy.get("requireTls") is not False,
        }
    return normalized


def _public_config(config: Mapping[str, Any], *, secret_available: bool) -> dict[str, Any]:
    try:
        port = int(config.get("port") or 1433)
    except (TypeError, ValueError) as error:
        raise SqlServerAdapterError("SQLSERVER_PORT_NOT_ALLOWLISTED", "The SQL Server port is not allowlisted.") from error
    return {
        "workspaceId": _validate_workspace_id(config.get("workspaceId")),
        "hostAlias": str(config.get("hostAlias") or "").strip().casefold(),
        "port": port,
        "database": str(config.get("database") or "").strip(),
        "encryption": str(config.get("encryption") or "required").strip().casefold(),
        "credentialConfigured": secret_available,
    }


def _validate_config(config: Mapping[str, Any], policies: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], Mapping[str, Any]]:
    workspace_id = _validate_workspace_id(config.get("workspaceId"))
    alias = str(config.get("hostAlias") or "").strip().casefold()
    if not _ALIAS_RE.fullmatch(alias) or alias not in policies:
        raise SqlServerAdapterError(
            "SQLSERVER_TARGET_NOT_ALLOWLISTED",
            "The SQL Server host alias is not allowlisted.",
            recovery_action="Ask an administrator to add the target alias and approved network ranges.",
        )
    policy = policies[alias]
    try:
        port = int(config.get("port") or 1433)
    except (TypeError, ValueError) as error:
        raise SqlServerAdapterError("SQLSERVER_PORT_NOT_ALLOWLISTED", "The SQL Server port is not allowlisted.") from error
    database = str(config.get("database") or "").strip()
    encryption = str(config.get("encryption") or "required").strip().casefold()
    if port not in policy["ports"]:
        raise SqlServerAdapterError("SQLSERVER_PORT_NOT_ALLOWLISTED", "The SQL Server port is not allowlisted.")
    if not _DATABASE_RE.fullmatch(database) or database not in policy["databases"]:
        raise SqlServerAdapterError("SQLSERVER_DATABASE_NOT_ALLOWLISTED", "The SQL Server database is not allowlisted.")
    if policy.get("requireTls", True) and encryption != "required":
        raise SqlServerAdapterError("SQLSERVER_TLS_REQUIRED", "This SQL Server target requires encrypted transport.")
    credential_ref = validate_credential_reference(config.get("credentialRef"))
    return {
        "workspaceId": workspace_id,
        "hostAlias": alias,
        "host": str(policy["host"]),
        "port": port,
        "database": database,
        "encryption": encryption,
        "credentialRef": credential_ref,
    }, policy


def _default_resolver(host: str, port: int) -> list[str]:
    return sorted({str(item[4][0]).split("%")[0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)})


def resolve_network_binding(
    config: Mapping[str, Any],
    policies: Mapping[str, Mapping[str, Any]],
    *,
    resolver: Callable[[str, int], Sequence[str]] = _default_resolver,
) -> dict[str, Any]:
    normalized, policy = _validate_config(config, policies)
    try:
        raw_addresses = resolver(normalized["host"], normalized["port"])
    except OSError as error:
        raise SqlServerAdapterError("SQLSERVER_DNS_FAILED", "The allowlisted SQL Server target could not be resolved.") from error
    addresses: list[str] = []
    networks = [ipaddress.ip_network(item, strict=False) for item in policy["allowedCidrs"]]
    for raw_address in raw_addresses:
        try:
            address = ipaddress.ip_address(str(raw_address).split("%")[0])
        except ValueError as error:
            raise SqlServerAdapterError("SQLSERVER_DNS_ADDRESS_INVALID", "DNS returned an invalid SQL Server address.") from error
        if address.is_loopback or address.is_link_local or address.is_multicast or address.is_unspecified or address.is_reserved:
            raise SqlServerAdapterError("SQLSERVER_NETWORK_CLASS_BLOCKED", "DNS returned a blocked SQL Server address class.")
        if not any(address in network for network in networks):
            raise SqlServerAdapterError(
                "SQLSERVER_DNS_REBINDING_BLOCKED",
                "DNS returned an address outside the target's approved network ranges.",
            )
        addresses.append(address.compressed)
    unique_addresses = sorted(set(addresses))
    if not unique_addresses or len(unique_addresses) > 8:
        raise SqlServerAdapterError("SQLSERVER_DNS_RESULT_INVALID", "The SQL Server target must resolve to one through eight approved addresses.")
    return {
        "hostAlias": normalized["hostAlias"],
        "addresses": unique_addresses,
        "addressFingerprint": stable_fingerprint(unique_addresses),
    }


def _driver_is_available(driver: SqlServerDriver | None) -> bool:
    if driver is not None:
        try:
            return bool(driver.available())
        except Exception:
            return False
    return importlib.util.find_spec("pyodbc") is not None


def adapter_contract(
    config: Mapping[str, Any] | None = None,
    *,
    driver: SqlServerDriver | None = None,
    policies: Mapping[str, Mapping[str, Any]] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    environment = environ if environ is not None else os.environ
    target_policies = dict(policies) if policies is not None else parse_target_policies(environ=environment)
    driver_available = _driver_is_available(driver)
    reason = ""
    capability = CAPABILITY_UNAVAILABLE
    credential_configured = False
    public_config: dict[str, Any] | None = None
    if config is not None:
        try:
            normalized, _policy = _validate_config(config, target_policies)
            secret_name = normalized["credentialRef"][4:]
            credential_configured = bool(environment.get(secret_name))
            public_config = _public_config(config, secret_available=credential_configured)
        except SqlServerAdapterError as error:
            reason = str(error)
    if not driver_available:
        reason = reason or "The optional pyodbc SQL Server driver is not installed."
    elif not target_policies:
        reason = reason or "No SQL Server target allowlist is configured."
    elif config is None:
        reason = "Select an allowlisted target and configure a Secret Ref."
    elif public_config is None:
        reason = reason or "The SQL Server connector configuration is incomplete."
    elif not credential_configured:
        reason = "The configured SQL Server Secret Ref is unavailable."
    else:
        capability = CAPABILITY_READY_FOR_TEST
    return {
        "schema": ADAPTER_SCHEMA,
        "adapterId": ADAPTER_ID,
        "connectorType": "sqlserver",
        "available": capability != CAPABILITY_UNAVAILABLE,
        "capability": capability,
        "operations": ["probe"] if capability == CAPABILITY_UNAVAILABLE else ["probe", "test", "discover", "preview", "plan", "snapshot", "activate", "activation-status"],
        "permissions": {
            "network": "allowlisted-read-only",
            "database": "catalog-and-generated-select-only",
            "arbitrarySql": False,
            "concurrency": 1,
            "fallback": "none",
        },
        "limits": dict(HARD_BUDGET),
        "credentials": {"mode": "server-env-reference", "configured": credential_configured, "valuesInReceipts": False},
        "persistence": {"remoteWrites": False, "activationBoundary": "durable-import-and-source-activation-journal"},
        "config": public_config,
        "reason": reason or None,
    }


def _check_runtime(deadline: float, cancelled: Callable[[], bool]) -> None:
    if cancelled():
        raise SqlServerAdapterError("SQLSERVER_OPERATION_CANCELED", "The SQL Server operation was canceled before activation.")
    if time.monotonic() > deadline:
        raise SqlServerAdapterError("SQLSERVER_OPERATION_TIMEOUT", "The SQL Server operation exceeded its approved time budget.")


@contextmanager
def _validated_session(
    config: Mapping[str, Any],
    *,
    driver: SqlServerDriver,
    policies: Mapping[str, Mapping[str, Any]],
    resolver: Callable[[str, int], Sequence[str]],
    environ: Mapping[str, str],
    timeout_seconds: int,
    cancelled: Callable[[], bool],
):
    if not driver.available():
        raise SqlServerAdapterError("SQLSERVER_DRIVER_UNAVAILABLE", "The optional SQL Server driver is unavailable.")
    normalized, _policy = _validate_config(config, policies)
    binding_before = resolve_network_binding(config, policies, resolver=resolver)
    credential = _load_credential(normalized["credentialRef"], environ)
    deadline = time.monotonic() + timeout_seconds
    _check_runtime(deadline, cancelled)
    session: SqlServerSession | None = None
    acquired = _OPERATION_LOCK.acquire(blocking=False)
    if not acquired:
        credential.clear()
        raise SqlServerAdapterError("SQLSERVER_ADAPTER_BUSY", "Only one SQL Server adapter operation may run at a time.")
    try:
        try:
            session = driver.connect(
                host=normalized["host"],
                port=normalized["port"],
                database=normalized["database"],
                credential=credential,
                timeout_seconds=timeout_seconds,
                encryption=normalized["encryption"],
            )
        except SqlServerAdapterError:
            raise
        except Exception as error:
            raise SqlServerAdapterError(
                "SQLSERVER_CONNECTION_FAILED",
                "The SQL Server read-only connection could not be established.",
                recovery_action="Verify the allowlisted target, TLS trust, Secret Ref, and read-only account.",
            ) from error
        _check_runtime(deadline, cancelled)
        try:
            peer_address = ipaddress.ip_address(str(session.peer_address()).split("%")[0]).compressed
        except SqlServerAdapterError:
            raise
        except Exception as error:
            raise SqlServerAdapterError("SQLSERVER_PEER_ADDRESS_UNVERIFIED", "The connected SQL Server peer address could not be verified.") from error
        if peer_address not in binding_before["addresses"]:
            raise SqlServerAdapterError("SQLSERVER_PEER_ADDRESS_MISMATCH", "The connected SQL Server peer is outside the approved DNS binding.")
        binding_after = resolve_network_binding(config, policies, resolver=resolver)
        if binding_after["addressFingerprint"] != binding_before["addressFingerprint"]:
            raise SqlServerAdapterError("SQLSERVER_DNS_REBINDING_BLOCKED", "The SQL Server DNS binding changed during connection setup.")
        try:
            read_only = dict(session.verify_read_only())
        except SqlServerAdapterError:
            raise
        except Exception as error:
            raise SqlServerAdapterError("SQLSERVER_READ_ONLY_UNVERIFIED", "The SQL Server read-only permission boundary could not be verified.") from error
        if read_only.get("readOnly") is not True:
            raise SqlServerAdapterError(
                "SQLSERVER_CREDENTIAL_NOT_READ_ONLY",
                "The SQL Server credential is not restricted to the approved read-only surface.",
            )
        yield session, normalized, binding_before, deadline, read_only
    finally:
        credential.clear()
        try:
            if session is not None:
                try:
                    session.close()
                except Exception:
                    pass
        finally:
            _OPERATION_LOCK.release()


def test_connection(
    config: Mapping[str, Any],
    *,
    driver: SqlServerDriver,
    policies: Mapping[str, Mapping[str, Any]],
    resolver: Callable[[str, int], Sequence[str]] = _default_resolver,
    environ: Mapping[str, str] | None = None,
    timeout_seconds: int = 10,
    cancelled: Callable[[], bool] = lambda: False,
) -> dict[str, Any]:
    bounded_timeout = max(1, min(int(timeout_seconds), 30))
    environment = environ if environ is not None else os.environ
    with _validated_session(
        config,
        driver=driver,
        policies=policies,
        resolver=resolver,
        environ=environment,
        timeout_seconds=bounded_timeout,
        cancelled=cancelled,
    ) as (_session, _normalized, binding, _deadline, read_only):
        payload = {
            "schema": RECEIPT_SCHEMA,
            "operation": "test",
            "workspaceId": _validate_workspace_id(config.get("workspaceId")),
            "capability": CAPABILITY_READY_FOR_TEST,
            "target": _public_config(config, secret_available=True),
            "networkBindingFingerprint": binding["addressFingerprint"],
            "readOnly": {"verified": True, "evidence": sorted(str(item) for item in read_only.get("evidence") or [])},
            "sideEffects": {"remoteWrite": False, "localArtifactWrite": False},
        }
        payload["receiptFingerprint"] = stable_fingerprint(payload)
        return {"ok": True, **payload}


def _normalize_catalog(resources: Sequence[Mapping[str, Any]], *, max_tables: int, max_columns: int) -> list[dict[str, Any]]:
    if len(resources) > max_tables:
        raise SqlServerAdapterError("SQLSERVER_CATALOG_TABLE_BUDGET_EXCEEDED", "The SQL Server catalog exceeded the approved table budget.")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for resource in resources:
        schema_name = str(resource.get("schema") or "").strip()
        name = str(resource.get("name") or "").strip()
        resource_type = str(resource.get("type") or "").strip().casefold()
        if not _IDENTIFIER_RE.fullmatch(schema_name) or not _IDENTIFIER_RE.fullmatch(name) or resource_type not in {"table", "view"}:
            raise SqlServerAdapterError("SQLSERVER_CATALOG_INVALID", "SQL Server returned an invalid catalog resource.")
        resource_key = f"{schema_name}.{name}"
        if resource_key in seen:
            raise SqlServerAdapterError("SQLSERVER_CATALOG_INVALID", "SQL Server returned a duplicate catalog resource.")
        seen.add(resource_key)
        raw_columns = list(resource.get("columns") or [])
        if not raw_columns or len(raw_columns) > max_columns:
            raise SqlServerAdapterError("SQLSERVER_CATALOG_COLUMN_BUDGET_EXCEEDED", "A SQL Server resource exceeded the approved column budget.")
        columns: list[dict[str, Any]] = []
        column_names: set[str] = set()
        for index, column in enumerate(raw_columns):
            column_name = str(column.get("name") or "").strip()
            data_type = str(column.get("dataType") or "").strip().casefold()
            if not _IDENTIFIER_RE.fullmatch(column_name) or not data_type or column_name in column_names:
                raise SqlServerAdapterError("SQLSERVER_CATALOG_INVALID", "SQL Server returned an invalid catalog column.")
            column_names.add(column_name)
            columns.append({
                "name": column_name,
                "dataType": data_type,
                "nullable": bool(column.get("nullable", True)),
                "ordinal": int(column.get("ordinal") or index + 1),
            })
        key_candidates: list[list[str]] = []
        for candidate in resource.get("keyCandidates") or []:
            fields = [str(item) for item in candidate]
            if fields and len(fields) == len(set(fields)) and all(item in column_names for item in fields):
                key_candidates.append(fields)
        normalized.append({
            "resourceKey": resource_key,
            "schemaName": schema_name,
            "name": name,
            "type": resource_type,
            "columns": columns,
            "keyCandidates": sorted(key_candidates),
            "rowEstimate": max(0, int(resource.get("rowEstimate") or 0)),
        })
    return sorted(normalized, key=lambda item: item["resourceKey"])


def discover_catalog(
    config: Mapping[str, Any],
    *,
    driver: SqlServerDriver,
    policies: Mapping[str, Mapping[str, Any]],
    resolver: Callable[[str, int], Sequence[str]] = _default_resolver,
    environ: Mapping[str, str] | None = None,
    max_tables: int = DEFAULT_BUDGET["maxTables"],
    max_columns_per_table: int = DEFAULT_BUDGET["maxColumnsPerTable"],
    timeout_seconds: int = 30,
    cancelled: Callable[[], bool] = lambda: False,
) -> dict[str, Any]:
    table_limit = max(1, min(int(max_tables), HARD_BUDGET["maxTables"]))
    column_limit = max(1, min(int(max_columns_per_table), HARD_BUDGET["maxColumnsPerTable"]))
    bounded_timeout = max(1, min(int(timeout_seconds), HARD_BUDGET["timeoutSeconds"]))
    environment = environ if environ is not None else os.environ
    with _validated_session(
        config,
        driver=driver,
        policies=policies,
        resolver=resolver,
        environ=environment,
        timeout_seconds=bounded_timeout,
        cancelled=cancelled,
    ) as (session, _normalized, binding, deadline, _read_only):
        try:
            discovered = session.discover_catalog(
                max_tables=table_limit,
                max_columns_per_table=column_limit,
                deadline=deadline,
                cancelled=cancelled,
            )
        except SqlServerAdapterError:
            raise
        except Exception as error:
            raise SqlServerAdapterError("SQLSERVER_CATALOG_DISCOVERY_FAILED", "The bounded SQL Server catalog could not be read.") from error
        resources = _normalize_catalog(
            discovered,
            max_tables=table_limit,
            max_columns=column_limit,
        )
        _check_runtime(deadline, cancelled)
    catalog_body = {
        "workspaceId": _validate_workspace_id(config.get("workspaceId")),
        "target": _public_config(config, secret_available=True),
        "networkBindingFingerprint": binding["addressFingerprint"],
        "resources": resources,
        "limits": {"tables": table_limit, "columnsPerTable": column_limit},
    }
    return {
        "ok": True,
        "schema": CATALOG_SCHEMA,
        **catalog_body,
        "catalogFingerprint": stable_fingerprint(catalog_body),
        "rawRowsReturned": False,
        "sideEffects": {"remoteWrite": False, "localArtifactWrite": False},
    }


def verify_catalog(catalog: Mapping[str, Any]) -> None:
    if catalog.get("schema") != CATALOG_SCHEMA:
        raise SqlServerAdapterError("SQLSERVER_CATALOG_SCHEMA_INVALID", "The SQL Server catalog schema is invalid.")
    body = {
        "workspaceId": catalog.get("workspaceId"),
        "target": catalog.get("target"),
        "networkBindingFingerprint": catalog.get("networkBindingFingerprint"),
        "resources": catalog.get("resources"),
        "limits": catalog.get("limits"),
    }
    if catalog.get("catalogFingerprint") != stable_fingerprint(body):
        raise SqlServerAdapterError("SQLSERVER_CATALOG_FINGERPRINT_MISMATCH", "The SQL Server catalog fingerprint does not match its contents.")


def preview_statistics(
    config: Mapping[str, Any],
    catalog: Mapping[str, Any],
    resource_keys: Sequence[str],
    *,
    driver: SqlServerDriver,
    policies: Mapping[str, Mapping[str, Any]],
    resolver: Callable[[str, int], Sequence[str]] = _default_resolver,
    environ: Mapping[str, str] | None = None,
    sample_rows: int = 200,
    timeout_seconds: int = 30,
    cancelled: Callable[[], bool] = lambda: False,
) -> dict[str, Any]:
    verify_catalog(catalog)
    if (
        catalog.get("workspaceId") != _validate_workspace_id(config.get("workspaceId"))
        or catalog.get("target") != _public_config(config, secret_available=True)
    ):
        raise SqlServerAdapterError("SQLSERVER_CATALOG_SCOPE_MISMATCH", "The SQL Server catalog is not current for this target and workspace.")
    resources = {str(item.get("resourceKey")): item for item in catalog.get("resources") or []}
    selected_keys = list(dict.fromkeys(str(item) for item in resource_keys))
    if not selected_keys or any(item not in resources for item in selected_keys):
        raise SqlServerAdapterError("SQLSERVER_SELECTION_INVALID", "Preview resources must come from the current bounded catalog.")
    bounded_sample = max(1, min(int(sample_rows), 1_000))
    bounded_timeout = max(1, min(int(timeout_seconds), HARD_BUDGET["timeoutSeconds"]))
    statistics: list[dict[str, Any]] = []
    environment = environ if environ is not None else os.environ
    with _validated_session(
        config,
        driver=driver,
        policies=policies,
        resolver=resolver,
        environ=environment,
        timeout_seconds=bounded_timeout,
        cancelled=cancelled,
    ) as (session, _normalized, binding, deadline, _read_only):
        if binding["addressFingerprint"] != catalog.get("networkBindingFingerprint"):
            raise SqlServerAdapterError("SQLSERVER_CATALOG_NETWORK_DRIFT", "The SQL Server network binding changed after discovery.")
        for resource_key in selected_keys:
            _check_runtime(deadline, cancelled)
            resource = resources[resource_key]
            column_names = [str(item["name"]) for item in resource["columns"]]
            try:
                stats = dict(session.preview_statistics(
                    resource,
                    columns=column_names,
                    sample_rows=bounded_sample,
                    deadline=deadline,
                    cancelled=cancelled,
                ))
            except SqlServerAdapterError:
                raise
            except Exception as error:
                raise SqlServerAdapterError("SQLSERVER_PREVIEW_FAILED", "The bounded SQL Server statistics preview failed.") from error
            public_columns: list[dict[str, Any]] = []
            for item in stats.get("columns") or []:
                name = str(item.get("name") or "")
                if name not in column_names:
                    raise SqlServerAdapterError("SQLSERVER_PREVIEW_INVALID", "Preview statistics referenced an unknown column.")
                column = next(value for value in resource["columns"] if value["name"] == name)
                public_item = {
                    "name": name,
                    "nullCount": max(0, int(item.get("nullCount") or 0)),
                    "distinctEstimate": max(0, int(item.get("distinctEstimate") or 0)),
                }
                if column["dataType"] in _COMPARABLE_WATERMARK_TYPES:
                    public_item["min"] = _safe_scalar(item.get("min"))
                    public_item["max"] = _safe_scalar(item.get("max"))
                public_columns.append(public_item)
            statistics.append({
                "resourceKey": resource_key,
                "sampledRows": max(0, min(int(stats.get("sampledRows") or 0), bounded_sample)),
                "columns": public_columns,
            })
    return {
        "ok": True,
        "schema": RECEIPT_SCHEMA,
        "operation": "preview",
        "workspaceId": catalog.get("workspaceId"),
        "catalogFingerprint": catalog.get("catalogFingerprint"),
        "statistics": statistics,
        "rawRowsReturned": False,
        "sideEffects": {"remoteWrite": False, "localArtifactWrite": False},
    }


def _safe_scalar(value: Any) -> str | int | float | bool | None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (bytes, bytearray, memoryview)):
        return "base64:" + base64.b64encode(bytes(value)).decode("ascii")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _normalized_budget(raw: Mapping[str, Any] | None) -> dict[str, int]:
    source = dict(raw or {})
    budget: dict[str, int] = {}
    for name, default in DEFAULT_BUDGET.items():
        try:
            value = int(source.get(name) or default)
        except (TypeError, ValueError) as error:
            raise SqlServerAdapterError("SQLSERVER_BUDGET_INVALID", f"{name} must be a bounded integer.") from error
        if value < 1 or value > HARD_BUDGET[name]:
            raise SqlServerAdapterError("SQLSERVER_BUDGET_INVALID", f"{name} must be between 1 and {HARD_BUDGET[name]}.")
        budget[name] = value
    return budget


def _catalog_by_key(catalog: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(item.get("resourceKey")): item for item in catalog.get("resources") or []}


def _selection_for_plan(raw: Mapping[str, Any], resource: Mapping[str, Any], budget: Mapping[str, int]) -> dict[str, Any]:
    resource_key = str(raw.get("resourceKey") or "")
    columns = list(dict.fromkeys(str(item) for item in raw.get("columns") or []))
    available_columns = {str(item["name"]): item for item in resource.get("columns") or []}
    if not columns or len(columns) > budget["maxColumnsPerTable"] or any(item not in available_columns for item in columns):
        raise SqlServerAdapterError("SQLSERVER_SELECTION_COLUMNS_INVALID", "Selected columns must come from the current catalog and fit the budget.")
    order_by = list(dict.fromkeys(str(item) for item in raw.get("orderBy") or []))
    if not order_by or any(item not in columns for item in order_by):
        raise SqlServerAdapterError("SQLSERVER_STABLE_ORDER_REQUIRED", "Every selected resource needs an explicit stable ordering.")
    key_candidates = [list(map(str, item)) for item in resource.get("keyCandidates") or []]
    key_backed = any(order_by == candidate for candidate in key_candidates)
    if not key_backed:
        nonnullable = all(not bool(available_columns[item].get("nullable", True)) for item in order_by)
        if raw.get("stableOrderingConfirmed") is not True or not nonnullable:
            raise SqlServerAdapterError(
                "SQLSERVER_STABLE_ORDER_REQUIRED",
                "Ordering must use a primary/unique key or a confirmed non-null deterministic field set.",
            )
    watermark_payload: dict[str, Any] | None = None
    raw_watermark = raw.get("watermark")
    if raw_watermark:
        if not isinstance(raw_watermark, Mapping):
            raise SqlServerAdapterError("SQLSERVER_WATERMARK_INVALID", "The incremental watermark contract is invalid.")
        column = str(raw_watermark.get("column") or "")
        tie_breakers = list(dict.fromkeys(str(item) for item in raw_watermark.get("tieBreakers") or []))
        after_value = _safe_scalar(raw_watermark.get("after"))
        after_tie_breakers = [_safe_scalar(item) for item in raw_watermark.get("afterTieBreakers") or []]
        column_type = str(available_columns.get(column, {}).get("dataType") or "").casefold()
        if column not in columns or column_type not in _COMPARABLE_WATERMARK_TYPES:
            raise SqlServerAdapterError("SQLSERVER_WATERMARK_INVALID", "The watermark must use a selected comparable column.")
        if not tie_breakers or not any(tie_breakers == candidate for candidate in key_candidates):
            raise SqlServerAdapterError("SQLSERVER_WATERMARK_TIE_BREAKER_REQUIRED", "Incremental snapshots require a unique deterministic tie-breaker.")
        if order_by != [column, *tie_breakers]:
            raise SqlServerAdapterError("SQLSERVER_WATERMARK_ORDER_INVALID", "Incremental ordering must start with the watermark and its unique tie-breaker.")
        if after_value is not None and len(after_tie_breakers) != len(tie_breakers):
            raise SqlServerAdapterError(
                "SQLSERVER_WATERMARK_BOUNDARY_INVALID",
                "An incremental watermark boundary must include one prior value for every tie-breaker.",
            )
        watermark_payload = {
            "column": column,
            "after": after_value,
            "tieBreakers": tie_breakers,
            "afterTieBreakers": after_tie_breakers,
        }
    target_table = str(raw.get("targetTableKey") or "").strip()
    if not _TARGET_TABLE_RE.fullmatch(target_table):
        raise SqlServerAdapterError("SQLSERVER_TARGET_TABLE_INVALID", "Every snapshot selection needs a safe targetTableKey.")
    estimated_rows = int(raw.get("estimatedRows") or resource.get("rowEstimate") or 0)
    if estimated_rows > budget["maxRowsPerTable"]:
        raise SqlServerAdapterError("SQLSERVER_ROW_BUDGET_EXCEEDED", "A selected SQL Server resource exceeds the row budget.")
    return {
        "resourceKey": resource_key,
        "resourceType": resource.get("type"),
        "columns": columns,
        "orderBy": order_by,
        "orderingBasis": "catalog_unique_key" if key_backed else "user_confirmed_non_null",
        "watermark": watermark_payload,
        "targetTableKey": target_table,
        "estimatedRows": max(0, estimated_rows),
        "resourceContractFingerprint": stable_fingerprint({key: value for key, value in resource.items() if key != "rowEstimate"}),
    }


def build_snapshot_plan(
    config: Mapping[str, Any],
    catalog: Mapping[str, Any],
    selections: Sequence[Mapping[str, Any]],
    *,
    request_key: str,
    budget: Mapping[str, Any] | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    workspace_id = _validate_workspace_id(config.get("workspaceId"))
    verify_catalog(catalog)
    if catalog.get("workspaceId") != workspace_id or catalog.get("target") != _public_config(config, secret_available=True):
        raise SqlServerAdapterError("SQLSERVER_CATALOG_SCOPE_MISMATCH", "The SQL Server catalog is not current for this workspace.")
    request_key = str(request_key or "").strip()
    if not request_key or len(request_key) > 200:
        raise SqlServerAdapterError("SQLSERVER_REQUEST_KEY_INVALID", "requestKey is required and must be at most 200 characters.")
    normalized_budget = _normalized_budget(budget)
    if not selections or len(selections) > normalized_budget["maxTables"]:
        raise SqlServerAdapterError("SQLSERVER_SELECTION_TABLE_BUDGET_EXCEEDED", "The SQL Server selection exceeds the table budget.")
    resources = _catalog_by_key(catalog)
    normalized_selections: list[dict[str, Any]] = []
    target_tables: set[str] = set()
    for raw in selections:
        resource_key = str(raw.get("resourceKey") or "")
        if resource_key not in resources:
            raise SqlServerAdapterError("SQLSERVER_SELECTION_INVALID", "Selections must come from the current SQL Server catalog.")
        normalized = _selection_for_plan(raw, resources[resource_key], normalized_budget)
        if normalized["targetTableKey"] in target_tables:
            raise SqlServerAdapterError("SQLSERVER_TARGET_TABLE_CONFLICT", "Snapshot selections cannot share a target table.")
        target_tables.add(normalized["targetTableKey"])
        normalized_selections.append(normalized)
    body = {
        "schema": PLAN_SCHEMA,
        "workspaceId": workspace_id,
        "requestKey": request_key,
        "createdAt": created_at or _utc_now(),
        "capability": CAPABILITY_READY_FOR_SNAPSHOT,
        "target": _public_config(config, secret_available=True),
        "catalogFingerprint": str(catalog.get("catalogFingerprint") or ""),
        "networkBindingFingerprint": str(catalog.get("networkBindingFingerprint") or ""),
        "selections": normalized_selections,
        "budget": normalized_budget,
        "staging": {"format": "csv-utf8", "artifactKey": ""},
        "activation": {"required": True, "boundary": "durable-import-and-source-activation-journal"},
    }
    artifact_key = f"sqlsnap_{stable_fingerprint({key: value for key, value in body.items() if key != 'staging'})[:24]}"
    body["staging"]["artifactKey"] = artifact_key
    body["planFingerprint"] = stable_fingerprint(body)
    return {"ok": True, **body}


def verify_snapshot_plan(plan: Mapping[str, Any]) -> None:
    if plan.get("schema") != PLAN_SCHEMA:
        raise SqlServerAdapterError("SQLSERVER_PLAN_SCHEMA_INVALID", "The SQL Server snapshot plan schema is invalid.")
    public = {key: value for key, value in plan.items() if key not in {"ok", "planFingerprint"}}
    expected = stable_fingerprint(public)
    if str(plan.get("planFingerprint") or "") != expected:
        raise SqlServerAdapterError("SQLSERVER_PLAN_FINGERPRINT_MISMATCH", "The SQL Server snapshot plan fingerprint does not match its contents.")


def _is_link_like(path: Path) -> bool:
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def _safe_stage_paths(staging_root: Path, workspace_id: str, artifact_key: str) -> tuple[Path, Path]:
    candidate_root = staging_root.absolute()
    if candidate_root.exists() and _is_link_like(candidate_root):
        raise SqlServerAdapterError("SQLSERVER_STAGING_ROOT_INVALID", "The SQL Server staging root cannot be a symbolic link.")
    root = candidate_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    workspace_key = f"ws_{stable_fingerprint(workspace_id)[:16]}"
    workspace_candidate = root / workspace_key
    if workspace_candidate.exists() and _is_link_like(workspace_candidate):
        raise SqlServerAdapterError("SQLSERVER_STAGING_SCOPE_INVALID", "The SQL Server workspace staging directory cannot be a symbolic link.")
    workspace_root = workspace_candidate.resolve()
    if not workspace_root.is_relative_to(root):
        raise SqlServerAdapterError("SQLSERVER_STAGING_SCOPE_INVALID", "The SQL Server staging workspace is outside its owned root.")
    workspace_root.mkdir(parents=True, exist_ok=True)
    final_path = (workspace_root / artifact_key).resolve()
    temporary_path = (workspace_root / f".{artifact_key}.{uuid.uuid4().hex}.tmp").resolve()
    if not final_path.is_relative_to(workspace_root) or not temporary_path.is_relative_to(workspace_root):
        raise SqlServerAdapterError("SQLSERVER_STAGING_SCOPE_INVALID", "The SQL Server snapshot artifact escaped its workspace staging root.")
    return final_path, temporary_path


def _remove_owned_tree(path: Path, staging_root: Path) -> None:
    resolved = path.resolve()
    root = staging_root.resolve()
    if resolved.is_relative_to(root) and resolved.name.startswith(".sqlsnap_") and resolved.name.endswith(".tmp"):
        shutil.rmtree(resolved, ignore_errors=True)


def _fsync_file(path: Path) -> None:
    with path.open("r+b") as handle:
        os.fsync(handle.fileno())


def _write_manifest(path: Path, manifest: Mapping[str, Any]) -> None:
    path.write_text(stable_json(manifest), encoding="utf-8")
    _fsync_file(path)


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _csv_line(columns: Sequence[str], row: Mapping[str, Any] | None = None) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(columns), extrasaction="raise", lineterminator="\n")
    if row is None:
        writer.writeheader()
    else:
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def _existing_snapshot(final_path: Path, plan: Mapping[str, Any]) -> dict[str, Any] | None:
    manifest_path = final_path / "manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if manifest.get("planFingerprint") != plan.get("planFingerprint"):
        raise SqlServerAdapterError("SQLSERVER_ARTIFACT_CONFLICT", "The snapshot artifact key is already bound to another plan.")
    expected_manifest_fingerprint = stable_fingerprint({key: value for key, value in manifest.items() if key != "manifestFingerprint"})
    if manifest.get("manifestFingerprint") != expected_manifest_fingerprint:
        raise SqlServerAdapterError("SQLSERVER_ARTIFACT_INTEGRITY_FAILED", "The staged SQL Server manifest failed integrity verification.")
    expected_files = {"manifest.json"}
    for item in manifest.get("tables") or []:
        file_name = str(item.get("file") or "")
        if Path(file_name).name != file_name or not file_name.endswith(".csv"):
            raise SqlServerAdapterError("SQLSERVER_ARTIFACT_INTEGRITY_FAILED", "The staged SQL Server manifest contains an invalid file reference.")
        expected_files.add(file_name)
        artifact = (final_path / file_name).resolve()
        if not artifact.is_relative_to(final_path.resolve()) or not artifact.is_file() or artifact.stat().st_size != int(item.get("bytes") or -1):
            raise SqlServerAdapterError("SQLSERVER_ARTIFACT_INTEGRITY_FAILED", "A staged SQL Server snapshot file is missing or changed.")
        digest = hashlib.sha256()
        with artifact.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != item.get("sha256"):
            raise SqlServerAdapterError("SQLSERVER_ARTIFACT_INTEGRITY_FAILED", "A staged SQL Server snapshot file failed integrity verification.")
    actual_files = {item.name for item in final_path.iterdir() if item.is_file()}
    if actual_files != expected_files or any(not item.is_file() or _is_link_like(item) for item in final_path.iterdir()):
        raise SqlServerAdapterError(
            "SQLSERVER_ARTIFACT_INTEGRITY_FAILED",
            "The staged SQL Server snapshot contains files outside its sealed manifest.",
        )
    return _public_snapshot_receipt(manifest, idempotent=True)


def verified_staged_snapshot(
    plan: Mapping[str, Any],
    *,
    staging_root: Path,
    expected_manifest_fingerprint: str = "",
) -> tuple[Path, dict[str, Any]]:
    """Resolve one sealed staging artifact for internal durable-import composition."""
    verify_snapshot_plan(plan)
    workspace_id = _validate_workspace_id(plan.get("workspaceId"))
    artifact_key = str((plan.get("staging") or {}).get("artifactKey") or "")
    if not re.fullmatch(r"sqlsnap_[a-f0-9]{24}", artifact_key):
        raise SqlServerAdapterError("SQLSERVER_ARTIFACT_KEY_INVALID", "The SQL Server snapshot artifact key is invalid.")
    final_path, _temporary_path = _safe_stage_paths(Path(staging_root), workspace_id, artifact_key)
    receipt = _existing_snapshot(final_path, plan) if final_path.is_dir() else None
    if receipt is None:
        raise SqlServerAdapterError("SQLSERVER_ARTIFACT_NOT_FOUND", "The reviewed SQL Server staging artifact was not found.")
    expected_manifest = str(expected_manifest_fingerprint or "").strip()
    if expected_manifest and receipt.get("manifestFingerprint") != expected_manifest:
        raise SqlServerAdapterError(
            "SQLSERVER_MANIFEST_FINGERPRINT_MISMATCH",
            "The staged SQL Server manifest does not match the confirmed activation input.",
        )
    return final_path, receipt


def _public_snapshot_receipt(manifest: Mapping[str, Any], *, idempotent: bool = False) -> dict[str, Any]:
    return {
        "ok": True,
        "schema": RECEIPT_SCHEMA,
        "operation": "snapshot",
        "workspaceId": manifest.get("workspaceId"),
        "capability": CAPABILITY_READY_FOR_SNAPSHOT,
        "artifactKey": manifest.get("artifactKey"),
        "planFingerprint": manifest.get("planFingerprint"),
        "catalogFingerprint": manifest.get("catalogFingerprint"),
        "manifestFingerprint": manifest.get("manifestFingerprint"),
        "tables": [
            {key: item.get(key) for key in ("resourceKey", "targetTableKey", "rowCount", "bytes", "sha256", "watermarkEndFingerprint")}
            for item in manifest.get("tables") or []
        ],
        "totalRows": int(manifest.get("totalRows") or 0),
        "totalBytes": int(manifest.get("totalBytes") or 0),
        "completedAt": manifest.get("completedAt"),
        "idempotentReplay": idempotent,
        "activation": {"required": True, "status": "pending"},
        "sideEffects": {"remoteWrite": False, "localArtifactWrite": True, "businessDatabaseWrite": False},
    }


def snapshot_to_staging(
    config: Mapping[str, Any],
    plan: Mapping[str, Any],
    *,
    driver: SqlServerDriver,
    policies: Mapping[str, Mapping[str, Any]],
    staging_root: Path,
    resolver: Callable[[str, int], Sequence[str]] = _default_resolver,
    environ: Mapping[str, str] | None = None,
    cancelled: Callable[[], bool] = lambda: False,
    now: Callable[[], str] = _utc_now,
) -> dict[str, Any]:
    environment = environ if environ is not None else os.environ
    verify_snapshot_plan(plan)
    workspace_id = _validate_workspace_id(config.get("workspaceId"))
    if plan.get("workspaceId") != workspace_id:
        raise SqlServerAdapterError("SQLSERVER_PLAN_SCOPE_MISMATCH", "The SQL Server snapshot plan belongs to another workspace.")
    public_config = _public_config(config, secret_available=True)
    if plan.get("target") != public_config:
        raise SqlServerAdapterError("SQLSERVER_PLAN_TARGET_DRIFT", "The SQL Server target changed after plan confirmation.")
    artifact_key = str((plan.get("staging") or {}).get("artifactKey") or "")
    if not re.fullmatch(r"sqlsnap_[a-f0-9]{24}", artifact_key):
        raise SqlServerAdapterError("SQLSERVER_ARTIFACT_KEY_INVALID", "The SQL Server snapshot artifact key is invalid.")
    final_path, temporary_path = _safe_stage_paths(Path(staging_root), workspace_id, artifact_key)
    if final_path.exists():
        existing = _existing_snapshot(final_path, plan)
        if existing is not None:
            return existing
        raise SqlServerAdapterError("SQLSERVER_ARTIFACT_CONFLICT", "The SQL Server snapshot artifact exists but is not verifiable.")
    budget = _normalized_budget(plan.get("budget") if isinstance(plan.get("budget"), Mapping) else None)
    binding = resolve_network_binding(config, policies, resolver=resolver)
    if binding["addressFingerprint"] != plan.get("networkBindingFingerprint"):
        raise SqlServerAdapterError("SQLSERVER_PLAN_NETWORK_DRIFT", "The SQL Server network binding changed after planning.")
    temporary_path.mkdir(parents=False, exist_ok=False)
    table_receipts: list[dict[str, Any]] = []
    total_rows = 0
    total_bytes = 0
    try:
        with _validated_session(
            config,
            driver=driver,
            policies=policies,
            resolver=resolver,
            environ=environment,
            timeout_seconds=budget["timeoutSeconds"],
            cancelled=cancelled,
        ) as (session, _normalized, session_binding, deadline, _read_only):
            if session_binding["addressFingerprint"] != plan.get("networkBindingFingerprint"):
                raise SqlServerAdapterError("SQLSERVER_PLAN_NETWORK_DRIFT", "The SQL Server network binding changed before snapshot execution.")
            selections = list(plan.get("selections") or [])
            described = _normalize_catalog(
                session.describe_resources(
                    [str(item.get("resourceKey") or "") for item in selections],
                    max_columns_per_table=budget["maxColumnsPerTable"],
                    deadline=deadline,
                    cancelled=cancelled,
                ),
                max_tables=len(selections),
                max_columns=budget["maxColumnsPerTable"],
            )
            described_by_key = {item["resourceKey"]: item for item in described}
            for selection in selections:
                current_resource = described_by_key.get(str(selection.get("resourceKey") or ""))
                current_fingerprint = stable_fingerprint({key: value for key, value in (current_resource or {}).items() if key != "rowEstimate"})
                if current_resource is None or current_fingerprint != selection.get("resourceContractFingerprint"):
                    raise SqlServerAdapterError(
                        "SQLSERVER_CATALOG_DRIFT",
                        "A selected SQL Server resource changed after planning; create and confirm a fresh plan.",
                    )
            for selection in selections:
                _check_runtime(deadline, cancelled)
                columns = [str(item) for item in selection.get("columns") or []]
                target_table = str(selection.get("targetTableKey") or "")
                output_path = temporary_path / f"{target_table}.csv"
                digest = hashlib.sha256()
                row_count = 0
                watermark_end: Any = None
                with output_path.open("wb") as handle:
                    header = _csv_line(columns)
                    handle.write(header)
                    digest.update(header)
                    total_bytes += len(header)
                    if total_bytes > budget["maxBytes"]:
                        raise SqlServerAdapterError("SQLSERVER_BYTE_BUDGET_EXCEEDED", "The SQL Server snapshot exceeded the approved byte budget.")
                    for raw_row in session.iter_snapshot(
                        selection,
                        max_rows=budget["maxRowsPerTable"] + 1,
                        page_size=budget["pageSize"],
                        deadline=deadline,
                        cancelled=cancelled,
                    ):
                        _check_runtime(deadline, cancelled)
                        row_count += 1
                        if row_count > budget["maxRowsPerTable"]:
                            raise SqlServerAdapterError("SQLSERVER_ROW_BUDGET_EXCEEDED", "A SQL Server snapshot exceeded the approved row budget.")
                        if not isinstance(raw_row, Mapping) or any(str(key) not in columns for key in raw_row):
                            raise SqlServerAdapterError("SQLSERVER_SNAPSHOT_ROW_INVALID", "The SQL Server driver returned a row outside the selected schema.")
                        safe_row = {column: _safe_scalar(raw_row.get(column)) for column in columns}
                        encoded = _csv_line(columns, safe_row)
                        total_bytes += len(encoded)
                        if total_bytes > budget["maxBytes"]:
                            raise SqlServerAdapterError("SQLSERVER_BYTE_BUDGET_EXCEEDED", "The SQL Server snapshot exceeded the approved byte budget.")
                        handle.write(encoded)
                        digest.update(encoded)
                        watermark = selection.get("watermark")
                        if isinstance(watermark, Mapping):
                            watermark_end = safe_row.get(str(watermark.get("column") or ""))
                    handle.flush()
                    os.fsync(handle.fileno())
                bytes_written = output_path.stat().st_size
                total_rows += row_count
                table_receipts.append({
                    "resourceKey": selection.get("resourceKey"),
                    "targetTableKey": target_table,
                    "file": output_path.name,
                    "rowCount": row_count,
                    "bytes": bytes_written,
                    "sha256": digest.hexdigest(),
                    "watermarkEnd": watermark_end,
                    "watermarkEndFingerprint": stable_fingerprint(watermark_end) if watermark_end is not None else None,
                })
        manifest = {
            "schema": RECEIPT_SCHEMA,
            "workspaceId": workspace_id,
            "artifactKey": artifact_key,
            "planFingerprint": plan.get("planFingerprint"),
            "catalogFingerprint": plan.get("catalogFingerprint"),
            "networkBindingFingerprint": plan.get("networkBindingFingerprint"),
            "tables": table_receipts,
            "totalRows": total_rows,
            "totalBytes": total_bytes,
            "completedAt": now(),
            "activationBoundary": "durable-import-and-source-activation-journal",
        }
        manifest["manifestFingerprint"] = stable_fingerprint(manifest)
        _write_manifest(temporary_path / "manifest.json", manifest)
        _fsync_directory(temporary_path)
        os.replace(temporary_path, final_path)
        _fsync_directory(final_path.parent)
        return _public_snapshot_receipt(manifest)
    except SqlServerAdapterError:
        _remove_owned_tree(temporary_path, Path(staging_root))
        raise
    except Exception as error:
        _remove_owned_tree(temporary_path, Path(staging_root))
        raise SqlServerAdapterError(
            "SQLSERVER_SNAPSHOT_PARTIAL_FAILURE",
            "The SQL Server snapshot failed before activation; no partial artifact is publishable.",
            recovery_action="Review the connector diagnostics and retry from a fresh plan.",
            details={"completedTables": len(table_receipts)},
        ) from error


def active_capability(plan: Mapping[str, Any], snapshot_receipt: Mapping[str, Any], activation_receipt: Mapping[str, Any]) -> dict[str, Any]:
    verify_snapshot_plan(plan)
    if (
        snapshot_receipt.get("schema") != RECEIPT_SCHEMA
        or snapshot_receipt.get("operation") != "snapshot"
        or snapshot_receipt.get("planFingerprint") != plan.get("planFingerprint")
        or not re.fullmatch(r"[a-f0-9]{64}", str(snapshot_receipt.get("manifestFingerprint") or ""))
    ):
        raise SqlServerAdapterError("SQLSERVER_ACTIVATION_PLAN_MISMATCH", "The snapshot receipt does not match the activated plan.")
    journal = activation_receipt.get("journal") if isinstance(activation_receipt.get("journal"), Mapping) else activation_receipt
    committed = activation_receipt.get("committed") is True or journal.get("outcome") == "committed"
    if (
        journal.get("workspaceId") != plan.get("workspaceId")
        or journal.get("planFingerprint") != plan.get("planFingerprint")
        or journal.get("phase") != "finalized"
        or not committed
    ):
        raise SqlServerAdapterError("SQLSERVER_ACTIVATION_NOT_FINALIZED", "The durable import activation has not finalized as committed.")
    return {
        "ok": True,
        "schema": RECEIPT_SCHEMA,
        "operation": "activate",
        "workspaceId": plan.get("workspaceId"),
        "artifactKey": snapshot_receipt.get("artifactKey"),
        "planFingerprint": plan.get("planFingerprint"),
        "manifestFingerprint": snapshot_receipt.get("manifestFingerprint"),
        "capability": CAPABILITY_ACTIVE,
        "activation": {"status": "committed", "journalKey": journal.get("journalKey")},
    }
