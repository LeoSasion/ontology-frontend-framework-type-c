from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import stat
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from dataset_version_store import (
    collect_unreferenced_dataset_objects,
    duckdb_manifest_object_references,
    file_sha256,
    resolve_object_key,
    verify_duckdb_manifest_objects,
)


RECOVERY_POINT_SCHEMA = "aibi-workspace-recovery-point/v2"
RECOVERY_PLAN_SCHEMA = "aibi-workspace-recovery-plan/v1"
RECOVERY_COLLECTION_SCHEMA = "aibi-workspace-recovery-points/v1"
RECOVERY_OPERATION_SCHEMA = "aibi-workspace-recovery-operation/v1"
RECOVERY_JOURNAL_SCHEMA = "aibi-workspace-recovery-journal/v1"
RECOVERY_COMPARISON_SCHEMA = "aibi-workspace-recovery-comparison/v1"

# Point-in-time recovery changes current business configuration and physical
# source data only. Evidence, append-only ledgers, source history, durable-job
# control state, and future workspace-scoped tables are preserved by default.
# A positive allowlist makes a newly added audit table non-restorable unless a
# later schema review explicitly proves otherwise.
RESTORABLE_WORKSPACE_TABLES = frozenset({
    "calculated_fields",
    "context_rules",
    "context_terms",
    "dashboard_widgets",
    "dashboards",
    "data_connectors",
    "field_semantics",
    "import_policies",
    "knowledge_sources",
    "metric_definitions",
    "metric_monitors",
    "navigation_modules",
    "relationships",
    "saved_views",
    "table_registry",
    "workspace_agent_runtime_profiles",
    "workspace_analytical_skills",
    "workspace_domain_packs",
})
RECOVERY_KEY_PATTERN = re.compile(r"^rp_[a-f0-9]{24}$")
WORKSPACE_BUCKET_PATTERN = re.compile(r"^workspace_[a-f0-9]{24}$")
MAX_REQUEST_KEY_LENGTH = 200
MAX_REASON_LENGTH = 500
MIN_FREE_BYTES = 8 * 1024 * 1024
SQLITE_ARTIFACT = "workspace.sqlite"
DUCKDB_ARTIFACT = "analytics.duckdb"
MANIFEST_FILE = "manifest.json"


class WorkspaceRecoveryError(ValueError):
    def __init__(self, code: str, message: str, recovery_action: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.recovery_action = recovery_action


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonical_value(value[key]) for key in sorted(value, key=str)}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, bytes):
        return {"$bytes": value.hex()}
    if isinstance(value, float):
        if math.isnan(value):
            return {"$float": "nan"}
        if math.isinf(value):
            return {"$float": "infinity" if value > 0 else "-infinity"}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(_canonical_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _quote_identifier(value: str) -> str:
    name = str(value)
    if not name or any(ord(character) < 32 for character in name):
        raise WorkspaceRecoveryError("RECOVERY_UNSAFE_IDENTIFIER", "Recovery data contains an unsafe database identifier.")
    return '"' + name.replace('"', '""') + '"'


def _quote_duckdb_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _required_text(value: Any, label: str, maximum: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise WorkspaceRecoveryError("RECOVERY_INPUT_REQUIRED", f"{label} is required.")
    if len(text) > maximum or any(ord(character) < 32 for character in text):
        raise WorkspaceRecoveryError("RECOVERY_INPUT_INVALID", f"{label} is invalid or exceeds {maximum} characters.")
    return text


def _workspace_id(value: Any) -> str:
    return _required_text(value, "workspaceId", 200)


def _request_key(value: Any) -> str:
    return _required_text(value, "requestKey", MAX_REQUEST_KEY_LENGTH)


def _reason(value: Any) -> str:
    return _required_text(value, "reason", MAX_REASON_LENGTH)


def _recovery_key(value: Any) -> str:
    key = str(value or "").strip()
    if not RECOVERY_KEY_PATTERN.fullmatch(key):
        raise WorkspaceRecoveryError("RECOVERY_POINT_KEY_INVALID", "Recovery point key is invalid.")
    return key


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _lexists(path: Path) -> bool:
    return os.path.lexists(os.fspath(path))


def _assert_not_symlink(path: Path, *, label: str) -> None:
    is_junction = getattr(os.path, "isjunction", lambda _value: False)
    if _lexists(path) and (path.is_symlink() or bool(is_junction(path))):
        raise WorkspaceRecoveryError("RECOVERY_SYMLINK_BLOCKED", f"{label} must not be a symbolic link.")


def _ensure_root(root: Path, *, create: bool) -> Path:
    resolved = _absolute(root)
    if _lexists(resolved):
        _assert_not_symlink(resolved, label="Recovery root")
        if not resolved.is_dir():
            raise WorkspaceRecoveryError("RECOVERY_ROOT_INVALID", "Recovery root is not a directory.")
    elif create:
        parent = resolved.parent
        while not _lexists(parent) and parent != parent.parent:
            parent = parent.parent
        _assert_not_symlink(parent, label="Recovery root parent")
        resolved.mkdir(parents=True, exist_ok=True)
        _assert_not_symlink(resolved, label="Recovery root")
    return resolved


def _safe_child(root: Path, *parts: str, must_exist: bool = False) -> Path:
    base = _absolute(root)
    candidate = _absolute(base.joinpath(*parts))
    try:
        within = os.path.commonpath((os.fspath(base), os.fspath(candidate))) == os.fspath(base)
    except ValueError:
        within = False
    if not within or candidate == base:
        raise WorkspaceRecoveryError("RECOVERY_PATH_TRAVERSAL_BLOCKED", "Recovery artifact path escapes its configured root.")
    relative_parts = candidate.relative_to(base).parts
    current = base
    _assert_not_symlink(current, label="Recovery root")
    for part in relative_parts:
        if part in {"", ".", ".."} or "/" in part or "\\" in part:
            raise WorkspaceRecoveryError("RECOVERY_PATH_TRAVERSAL_BLOCKED", "Recovery artifact path is invalid.")
        current = current / part
        _assert_not_symlink(current, label="Recovery artifact")
    if must_exist and not candidate.exists():
        raise WorkspaceRecoveryError("RECOVERY_POINT_NOT_FOUND", "Recovery point does not exist in the current workspace.")
    return candidate


def _assert_regular_file(path: Path) -> os.stat_result:
    _assert_not_symlink(path, label="Recovery artifact")
    try:
        metadata = path.lstat()
    except FileNotFoundError as error:
        raise WorkspaceRecoveryError("RECOVERY_ARTIFACT_MISSING", "Recovery point is missing a required artifact.") from error
    if not stat.S_ISREG(metadata.st_mode):
        raise WorkspaceRecoveryError("RECOVERY_ARTIFACT_INVALID", "Recovery artifact must be a regular file.")
    if metadata.st_nlink != 1:
        raise WorkspaceRecoveryError("RECOVERY_HARDLINK_BLOCKED", "Recovery artifact hard links are not allowed.")
    return metadata


def _fsync_file(path: Path) -> None:
    with path.open("r+b") as handle:
        os.fsync(handle.fileno())


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(os.fspath(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        # Windows does not support fsync for every directory handle. Each file is
        # still flushed before the same-volume atomic rename.
        pass
    finally:
        os.close(descriptor)


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _assert_not_symlink(path.parent, label="Recovery metadata directory")
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _read_json_file(path: Path) -> dict[str, Any]:
    _assert_regular_file(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise WorkspaceRecoveryError("RECOVERY_MANIFEST_INVALID", "Recovery manifest is unreadable or invalid JSON.") from error
    if not isinstance(value, dict):
        raise WorkspaceRecoveryError("RECOVERY_MANIFEST_INVALID", "Recovery manifest must be a JSON object.")
    return value


def _journal_payload_base(journal: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in journal.items() if key != "contentFingerprint"}


def _write_recovery_journal(path: Path, journal: dict[str, Any]) -> None:
    payload = _journal_payload_base(journal)
    payload["contentFingerprint"] = _fingerprint(payload)
    journal.clear()
    journal.update(payload)
    _atomic_json(path, payload)


def _read_recovery_journal(path: Path) -> dict[str, Any]:
    journal = _read_json_file(path)
    fingerprint = str(journal.get("contentFingerprint") or "")
    if not fingerprint or fingerprint != _fingerprint(_journal_payload_base(journal)):
        raise WorkspaceRecoveryError(
            "RECOVERY_JOURNAL_INTEGRITY_FAILED",
            "Recovery journal content fingerprint is missing or invalid.",
        )
    return journal


def _recovery_operation_base(receipt: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in receipt.items() if key != "contentFingerprint"}


def _read_recovery_operation(path: Path) -> dict[str, Any]:
    receipt = _read_json_file(path)
    fingerprint = str(receipt.get("contentFingerprint") or "")
    if not fingerprint or fingerprint != _fingerprint(_recovery_operation_base(receipt)):
        raise WorkspaceRecoveryError(
            "RECOVERY_OPERATION_INTEGRITY_FAILED",
            "Recovery operation receipt content fingerprint is missing or invalid.",
        )
    return receipt


def _workspace_bucket(workspace_id: str) -> str:
    return f"workspace_{hashlib.sha256(workspace_id.encode('utf-8')).hexdigest()[:24]}"


def _workspace_root(root: Path, workspace_id: str, *, create: bool) -> Path:
    base = _ensure_root(root, create=create)
    directory = _safe_child(base, _workspace_bucket(workspace_id))
    if create:
        directory.mkdir(parents=False, exist_ok=True)
        _assert_not_symlink(directory, label="Workspace recovery directory")
    return directory


def recovery_point_duckdb_catalogs(
    recovery_root: Path,
    *,
    workspace_id: str | None = None,
) -> list[Path]:
    """Return persisted catalogues that can reference one workspace's CAS keys."""

    root = _ensure_root(_absolute(recovery_root), create=False)
    if not root.exists():
        return []
    catalogs: list[Path] = []
    expected_bucket = _workspace_bucket(_workspace_id(workspace_id)) if workspace_id is not None else None
    for workspace_directory in root.iterdir():
        if not WORKSPACE_BUCKET_PATTERN.fullmatch(workspace_directory.name):
            continue
        if expected_bucket is not None and workspace_directory.name != expected_bucket:
            continue
        _assert_not_symlink(workspace_directory, label="Workspace recovery directory")
        if not workspace_directory.is_dir():
            raise WorkspaceRecoveryError(
                "RECOVERY_WORKSPACE_DIRECTORY_INVALID",
                "Workspace recovery entry is not a directory.",
            )
        for point_directory in workspace_directory.iterdir():
            if not RECOVERY_KEY_PATTERN.fullmatch(point_directory.name):
                continue
            _assert_not_symlink(point_directory, label="Recovery point directory")
            if not point_directory.is_dir():
                raise WorkspaceRecoveryError(
                    "RECOVERY_POINT_INVALID",
                    "Recovery point entry is not a directory.",
                )
            catalog = _safe_child(point_directory, DUCKDB_ARTIFACT)
            if catalog.exists():
                _assert_regular_file(catalog)
                catalogs.append(catalog)
    return sorted(catalogs, key=lambda path: os.fspath(path).casefold())


def _nearest_existing_parent(path: Path) -> Path:
    current = path
    while not current.exists() and current != current.parent:
        current = current.parent
    return current


def _available_bytes(root: Path) -> int:
    parent = _nearest_existing_parent(_absolute(root))
    return int(shutil.disk_usage(parent).free)


def _ensure_disk_capacity(root: Path, estimated_bytes: int) -> None:
    required = max(MIN_FREE_BYTES, int(estimated_bytes * 1.15) + MIN_FREE_BYTES)
    available = _available_bytes(root)
    if available < required:
        raise WorkspaceRecoveryError(
            "RECOVERY_DISK_SPACE_INSUFFICIENT",
            "Not enough free space to create a verified recovery point.",
            "Free local disk space and run the preview again.",
        )


def _table_names(connection: sqlite3.Connection) -> list[str]:
    return [
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    ]


def _table_columns(connection: sqlite3.Connection, table_name: str, schema: str = "main") -> list[str]:
    return [
        str(row[1])
        for row in connection.execute(
            f"PRAGMA {schema}.table_info({_quote_identifier(table_name)})"
        ).fetchall()
    ]


def _table_exists(connection: sqlite3.Connection, table_name: str, schema: str = "main") -> bool:
    return connection.execute(
        f"SELECT 1 FROM {schema}.sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone() is not None


def _workspace_physical_tables(connection: sqlite3.Connection, workspace_id: str) -> list[str]:
    if not _table_exists(connection, "table_registry"):
        return []
    rows = connection.execute(
        "SELECT physical_table FROM table_registry WHERE workspace_id = ? ORDER BY table_key",
        (workspace_id,),
    ).fetchall()
    values = [str(row[0]) for row in rows if str(row[0] or "").strip()]
    if len(values) != len(set(values)):
        raise WorkspaceRecoveryError("RECOVERY_PHYSICAL_TABLE_COLLISION", "Workspace contains duplicate physical table bindings.")
    return values


def _all_physical_table_bindings(connection: sqlite3.Connection) -> dict[str, set[str]]:
    bindings: dict[str, set[str]] = {}
    if not _table_exists(connection, "table_registry"):
        return bindings
    for workspace_id, physical_table in connection.execute(
        "SELECT workspace_id, physical_table FROM table_registry ORDER BY workspace_id, table_key"
    ).fetchall():
        name = str(physical_table or "")
        if name:
            bindings.setdefault(name, set()).add(str(workspace_id or ""))
    return bindings


def _assert_workspace_exists(connection: sqlite3.Connection, workspace_id: str) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM workspaces WHERE id = ?", (workspace_id,)).fetchone()
    if row is None:
        raise WorkspaceRecoveryError("RECOVERY_WORKSPACE_NOT_FOUND", "Workspace does not exist.")
    return row


def _row_order_clause(connection: sqlite3.Connection, table_name: str) -> str:
    info = connection.execute(f"PRAGMA table_info({_quote_identifier(table_name)})").fetchall()
    primary = [str(row[1]) for row in sorted((row for row in info if int(row[5] or 0)), key=lambda row: int(row[5]))]
    if primary:
        return " ORDER BY " + ", ".join(_quote_identifier(column) for column in primary)
    return " ORDER BY rowid"


def _hash_query_rows(digest: Any, cursor: sqlite3.Cursor) -> None:
    while rows := cursor.fetchmany(512):
        for row in rows:
            digest.update(_canonical_json(list(row)).encode("utf-8"))
            digest.update(b"\n")


def _sqlite_workspace_fingerprint(connection: sqlite3.Connection, workspace_id: str) -> tuple[str, dict[str, int], list[str]]:
    _assert_workspace_exists(connection, workspace_id)
    physical_tables = _workspace_physical_tables(connection, workspace_id)
    legacy_tables = [name for name in physical_tables if _table_exists(connection, name)]
    if legacy_tables:
        raise WorkspaceRecoveryError(
            "RECOVERY_LEGACY_BUSINESS_STORAGE_UNSUPPORTED",
            "Dataset v2 recovery does not snapshot business rows from SQLite.",
            "Re-import the source into the Parquet data plane before creating a recovery point.",
        )
    all_physical_tables = set(_all_physical_table_bindings(connection))
    digest = hashlib.sha256()
    row_counts: dict[str, int] = {}
    for table_name in _table_names(connection):
        columns = _table_columns(connection, table_name)
        is_workspace_metadata = (
            "workspace_id" in columns
            and table_name not in all_physical_tables
            and table_name in RESTORABLE_WORKSPACE_TABLES
        )
        include = table_name == "workspaces" or is_workspace_metadata
        if not include:
            continue
        digest.update(table_name.encode("utf-8"))
        digest.update(_canonical_json(columns).encode("utf-8"))
        where = " WHERE id = ?" if table_name == "workspaces" else " WHERE workspace_id = ?" if is_workspace_metadata else ""
        params: tuple[Any, ...] = (workspace_id,) if where else ()
        count = int(connection.execute(
            f"SELECT COUNT(*) FROM {_quote_identifier(table_name)}{where}", params
        ).fetchone()[0])
        row_counts[table_name] = count
        try:
            order = _row_order_clause(connection, table_name)
            cursor = connection.execute(f"SELECT * FROM {_quote_identifier(table_name)}{where}{order}", params)
        except sqlite3.OperationalError:
            cursor = connection.execute(f"SELECT * FROM {_quote_identifier(table_name)}{where}", params)
        _hash_query_rows(digest, cursor)
    return digest.hexdigest(), row_counts, physical_tables


def _duckdb_module() -> Any:
    try:
        import duckdb  # type: ignore
    except Exception as error:
        raise WorkspaceRecoveryError(
            "RECOVERY_DUCKDB_UNAVAILABLE",
            "DuckDB is required to verify the workspace dataset catalog.",
            "Install the reviewed local runtime dependency and retry.",
        ) from error
    return duckdb


def _duckdb_table_exists(connection: Any, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = current_schema() AND table_name = ?",
        [table_name],
    ).fetchone()
    return row is not None


def _duckdb_relation_kind(connection: Any, table_name: str, *, catalog: str | None = None) -> str | None:
    catalog_clause = "AND table_catalog = ?" if catalog else "AND table_catalog = current_database()"
    params = [table_name, catalog] if catalog else [table_name]
    row = connection.execute(
        "SELECT table_type FROM information_schema.tables "
        f"WHERE table_schema = 'main' AND table_name = ? {catalog_clause}",
        params,
    ).fetchone()
    return str(row[0]).upper() if row else None


def _manifest_object_paths(object_keys_value: Any, object_hashes_value: Any) -> list[Path]:
    try:
        object_keys = json.loads(str(object_keys_value or "[]"))
        object_hashes = json.loads(str(object_hashes_value or "[]"))
    except json.JSONDecodeError as error:
        raise WorkspaceRecoveryError("RECOVERY_DUCKDB_MANIFEST_DRIFT", "Dataset manifest object bindings are invalid.") from error
    if not isinstance(object_keys, list) or not isinstance(object_hashes, list) or not object_keys or len(object_keys) != len(object_hashes):
        raise WorkspaceRecoveryError("RECOVERY_DUCKDB_MANIFEST_DRIFT", "Dataset manifest object bindings are invalid.")
    paths: list[Path] = []
    for raw_key, raw_hash in zip(object_keys, object_hashes, strict=True):
        object_hash = str(raw_hash).lower()
        try:
            path = resolve_object_key(str(raw_key))
        except (PermissionError, ValueError) as error:
            raise WorkspaceRecoveryError("RECOVERY_DUCKDB_MANIFEST_DRIFT", "Dataset manifest object key is invalid.") from error
        if path.name != f"{object_hash}.parquet":
            raise WorkspaceRecoveryError("RECOVERY_DUCKDB_MANIFEST_DRIFT", "Dataset manifest object key and hash disagree.")
        if not path.is_file() or path.is_symlink():
            raise WorkspaceRecoveryError("RECOVERY_DATASET_OBJECT_MISSING", "A versioned Parquet object required by recovery is unavailable.")
        if file_sha256(path) != object_hash:
            raise WorkspaceRecoveryError("RECOVERY_DATASET_OBJECT_DRIFT", "A versioned Parquet object failed its integrity check.")
        paths.append(path)
    return paths


def _parquet_view_source(paths: list[Path]) -> str:
    values = ", ".join(_quote_duckdb_literal(path.as_posix()) for path in paths)
    return f"read_parquet([{values}], union_by_name = true)"


def _duckdb_workspace_fingerprint(path: Path, physical_tables: list[str]) -> tuple[str | None, list[dict[str, Any]]]:
    if not path.exists():
        if physical_tables:
            raise WorkspaceRecoveryError(
                "RECOVERY_DUCKDB_MANIFEST_MISSING",
                "Active dataset versions have not been published to the DuckDB catalog.",
            )
        return _fingerprint({"schema": "aibi-duckdb-workspace-datasets/v2", "rows": []}), []
    _assert_not_symlink(path, label="DuckDB database")
    duckdb = _duckdb_module()
    with duckdb.connect(str(path), read_only=True) as connection:
        if not _duckdb_table_exists(connection, "__aibi_replica_manifest"):
            drifted = [name for name in physical_tables if _duckdb_table_exists(connection, name)]
            if drifted:
                raise WorkspaceRecoveryError(
                    "RECOVERY_DUCKDB_MANIFEST_MISSING",
                    "DuckDB contains workspace relations without a replica manifest.",
                )
            return _fingerprint({"schema": "aibi-duckdb-workspace-datasets/v2", "rows": []}), []
        description = [str(item[0]) for item in connection.execute("DESCRIBE __aibi_replica_manifest").fetchall()]
        required = {
            "manifest_version", "logical_table", "source_version", "version_id",
            "object_keys_json", "object_paths_json", "object_hashes_json",
            "schema_fingerprint", "content_fingerprint", "row_count", "published_at",
        }
        if not required.issubset(description):
            raise WorkspaceRecoveryError("RECOVERY_DUCKDB_MANIFEST_V2_REQUIRED", "DuckDB dataset manifest is not version 2.")
        if not physical_tables:
            return _fingerprint({"schema": "aibi-duckdb-workspace-datasets/v2", "rows": []}), []
        placeholders = ", ".join("?" for _ in physical_tables)
        records = connection.execute(
            f"SELECT * FROM __aibi_replica_manifest WHERE logical_table IN ({placeholders}) ORDER BY logical_table",
            physical_tables,
        ).fetchall()
        rows = [dict(zip(description, record, strict=True)) for record in records]
        missing = sorted(set(physical_tables) - {str(item.get("logical_table") or "") for item in rows})
        if missing:
            raise WorkspaceRecoveryError(
                "RECOVERY_DUCKDB_MANIFEST_DRIFT",
                "DuckDB is missing an active dataset binding required by recovery.",
            )
        for item in rows:
            logical_table = str(item.get("logical_table") or "")
            if int(item.get("manifest_version") or 0) != 2 or _duckdb_relation_kind(connection, logical_table) != "VIEW":
                raise WorkspaceRecoveryError("RECOVERY_DUCKDB_MANIFEST_DRIFT", "DuckDB dataset manifest points to a missing logical view.")
            _manifest_object_paths(item.get("object_keys_json"), item.get("object_hashes_json"))
        return _fingerprint({"schema": "aibi-duckdb-workspace-datasets/v2", "rows": rows}), rows


def _workspace_state(connection: sqlite3.Connection, workspace_id: str, duckdb_path: Path) -> dict[str, Any]:
    sqlite_fingerprint, row_counts, physical_tables = _sqlite_workspace_fingerprint(connection, workspace_id)
    duckdb_fingerprint, replica_rows = _duckdb_workspace_fingerprint(duckdb_path, physical_tables)
    workspace = _assert_workspace_exists(connection, workspace_id)
    current_source_run = str(workspace["current_source_run_id"] or "") if "current_source_run_id" in workspace.keys() else ""
    schema_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    payload = {
        "workspaceId": workspace_id,
        "sqliteSchemaVersion": schema_version,
        "currentSourceRunId": current_source_run or None,
        "sqliteFingerprint": sqlite_fingerprint,
        "duckdbFingerprint": duckdb_fingerprint,
        "metadataRowCounts": row_counts,
        "physicalTableCount": len(physical_tables),
        "replicaCount": len(replica_rows),
    }
    payload["fingerprint"] = _fingerprint({"schema": "aibi-workspace-recovery-state/v2", **payload})
    return payload


def _estimate_bytes(sqlite_path: Path, duckdb_path: Path) -> int:
    total = 0
    for path in (sqlite_path, duckdb_path):
        if path.exists() and path.is_file():
            total += int(path.stat().st_size)
    return max(total, MIN_FREE_BYTES)


def _create_sqlite_snapshot(connection: sqlite3.Connection, target: Path, workspace_id: str) -> None:
    if target.exists():
        raise WorkspaceRecoveryError("RECOVERY_STAGING_COLLISION", "Recovery staging artifact already exists.")
    legacy_tables = [name for name in _workspace_physical_tables(connection, workspace_id) if _table_exists(connection, name)]
    if legacy_tables:
        raise WorkspaceRecoveryError(
            "RECOVERY_LEGACY_BUSINESS_STORAGE_UNSUPPORTED",
            "Dataset v2 recovery cannot copy SQLite business tables.",
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(target)) as snapshot:
        connection.backup(snapshot)
        snapshot.row_factory = sqlite3.Row
        bindings = _all_physical_table_bindings(snapshot)
        for table_name, owners in bindings.items():
            if workspace_id in owners and len(owners) > 1:
                raise WorkspaceRecoveryError(
                    "RECOVERY_PHYSICAL_TABLE_COLLISION",
                    "A physical table is shared across workspaces; recovery cannot isolate it safely.",
                )
        target_physical = {name for name, owners in bindings.items() if owners == {workspace_id}}
        workspace_row = snapshot.execute(
            "SELECT current_source_run_id FROM workspaces WHERE id = ?",
            (workspace_id,),
        ).fetchone()
        current_source_run_id = str(workspace_row[0] or "") if workspace_row is not None else ""
        snapshot.execute("PRAGMA foreign_keys = OFF")
        snapshot.execute("BEGIN IMMEDIATE")
        for table_name in _table_names(snapshot):
            if table_name in bindings and table_name not in target_physical:
                snapshot.execute(f"DROP TABLE IF EXISTS {_quote_identifier(table_name)}")
                continue
            if table_name in target_physical or table_name in {"workspaces", "system_flags"}:
                continue
            if table_name == "dataset_versions":
                snapshot.execute(
                    "DELETE FROM dataset_versions WHERE workspace_id <> ? OR version_id NOT IN ("
                    "SELECT active_version_id FROM table_registry "
                    "WHERE workspace_id = ? AND active_version_id <> ''"
                    ")",
                    (workspace_id, workspace_id),
                )
                continue
            if table_name == "dataset_version_files":
                snapshot.execute(
                    "DELETE FROM dataset_version_files WHERE version_id NOT IN ("
                    "SELECT active_version_id FROM table_registry "
                    "WHERE workspace_id = ? AND active_version_id <> ''"
                    ")",
                    (workspace_id,),
                )
                continue
            if table_name == "source_runs":
                if current_source_run_id:
                    snapshot.execute(
                        "DELETE FROM source_runs WHERE workspace_id <> ? OR id <> ?",
                        (workspace_id, current_source_run_id),
                    )
                else:
                    snapshot.execute("DELETE FROM source_runs")
                continue
            columns = _table_columns(snapshot, table_name)
            if "workspace_id" in columns:
                snapshot.execute(
                    f"DELETE FROM {_quote_identifier(table_name)} WHERE workspace_id <> ?",
                    (workspace_id,),
                )
            else:
                # Global configuration is outside a workspace recovery boundary.
                # Keep its schema for compatibility inspection, but never its rows.
                snapshot.execute(f"DELETE FROM {_quote_identifier(table_name)}")
        snapshot.execute("DELETE FROM workspaces WHERE id <> ?", (workspace_id,))
        if _table_exists(snapshot, "system_flags"):
            flag_columns = set(_table_columns(snapshot, "system_flags"))
            snapshot.execute("DELETE FROM system_flags")
            if {"key", "value"}.issubset(flag_columns):
                if "updated_at" in flag_columns:
                    snapshot.execute(
                        "INSERT INTO system_flags(key, value, updated_at) VALUES('active_workspace_id', ?, ?)",
                        (workspace_id, _utc_now()),
                    )
                else:
                    snapshot.execute(
                        "INSERT INTO system_flags(key, value) VALUES('active_workspace_id', ?)",
                        (workspace_id,),
                    )
        if snapshot.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_sequence'").fetchone():
            snapshot.execute("DELETE FROM sqlite_sequence")
        snapshot.commit()
        snapshot.execute("VACUUM")
        snapshot.commit()
    _fsync_file(target)
    _validate_sqlite_snapshot(target, workspace_id)


def _validate_sqlite_snapshot(path: Path, workspace_id: str) -> None:
    _assert_regular_file(path)
    uri = f"file:{path.resolve().as_posix()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        workspaces = [str(row[0]) for row in connection.execute("SELECT id FROM workspaces ORDER BY id").fetchall()]
        if workspaces != [workspace_id]:
            raise WorkspaceRecoveryError("RECOVERY_WORKSPACE_MISMATCH", "SQLite recovery artifact is not isolated to the requested workspace.")
        required_dataset_tables = {"dataset_versions", "dataset_version_files", "source_runs", "table_registry"}
        if not all(_table_exists(connection, table_name) for table_name in required_dataset_tables):
            raise WorkspaceRecoveryError(
                "RECOVERY_SQLITE_SNAPSHOT_INVALID",
                "Dataset v2 recovery snapshot is missing its version or lineage catalogue.",
            )
        dangling_active_version = connection.execute(
            """
            SELECT 1
            FROM table_registry AS registry
            LEFT JOIN dataset_versions AS version
              ON version.version_id = registry.active_version_id
             AND version.workspace_id = registry.workspace_id
             AND version.table_key = registry.table_key
            WHERE registry.workspace_id = ?
              AND registry.active_version_id <> ''
              AND version.version_id IS NULL
            LIMIT 1
            """,
            (workspace_id,),
        ).fetchone()
        incomplete_version = connection.execute(
            """
            SELECT 1
            FROM dataset_versions AS version
            LEFT JOIN dataset_version_files AS file ON file.version_id = version.version_id
            WHERE version.workspace_id = ?
            GROUP BY version.version_id
            HAVING COUNT(file.version_id) <> 1
            LIMIT 1
            """,
            (workspace_id,),
        ).fetchone()
        orphan_file = connection.execute(
            """
            SELECT 1
            FROM dataset_version_files AS file
            LEFT JOIN dataset_versions AS version ON version.version_id = file.version_id
            WHERE version.version_id IS NULL OR version.workspace_id <> ?
            LIMIT 1
            """,
            (workspace_id,),
        ).fetchone()
        inactive_version = connection.execute(
            """
            SELECT 1
            FROM dataset_versions AS version
            LEFT JOIN table_registry AS registry
              ON registry.workspace_id = version.workspace_id
             AND registry.table_key = version.table_key
             AND registry.active_version_id = version.version_id
            WHERE version.workspace_id = ? AND registry.active_version_id IS NULL
            LIMIT 1
            """,
            (workspace_id,),
        ).fetchone()
        if (
            dangling_active_version is not None
            or incomplete_version is not None
            or orphan_file is not None
            or inactive_version is not None
        ):
            raise WorkspaceRecoveryError(
                "RECOVERY_SQLITE_SNAPSHOT_INVALID",
                "Dataset v2 recovery snapshot contains an incomplete version manifest.",
            )
        for object_key, object_hash in connection.execute(
            "SELECT object_key, object_hash FROM dataset_version_files ORDER BY version_id, ordinal"
        ).fetchall():
            expected_hash = str(object_hash or "").lower()
            try:
                object_path = resolve_object_key(str(object_key or ""))
            except (PermissionError, ValueError) as error:
                raise WorkspaceRecoveryError(
                    "RECOVERY_SQLITE_SNAPSHOT_INVALID",
                    "Dataset v2 recovery snapshot contains an invalid object binding.",
                ) from error
            if (
                object_path.name != f"{expected_hash}.parquet"
                or not object_path.is_file()
                or object_path.is_symlink()
                or file_sha256(object_path) != expected_hash
            ):
                raise WorkspaceRecoveryError(
                    "RECOVERY_DATASET_OBJECT_INTEGRITY_FAILED",
                    "Recovery snapshot references a missing or invalid immutable dataset object.",
                )
        workspace_row = connection.execute(
            "SELECT current_source_run_id FROM workspaces WHERE id = ?",
            (workspace_id,),
        ).fetchone()
        current_source_run_id = str(workspace_row[0] or "") if workspace_row is not None else ""
        lineage_rows = connection.execute(
            "SELECT id FROM source_runs WHERE workspace_id = ? ORDER BY id",
            (workspace_id,),
        ).fetchall()
        lineage_ids = [str(row[0]) for row in lineage_rows]
        expected_lineage_ids = [current_source_run_id] if current_source_run_id else []
        if lineage_ids != expected_lineage_ids:
            raise WorkspaceRecoveryError(
                "RECOVERY_SQLITE_SNAPSHOT_INVALID",
                "Recovery snapshot must contain exactly the current source lineage binding.",
            )
        physical_tables = set(_workspace_physical_tables(connection, workspace_id))
        if any(_table_exists(connection, table_name) for table_name in physical_tables):
            raise WorkspaceRecoveryError(
                "RECOVERY_SQLITE_SNAPSHOT_INVALID",
                "Dataset v2 recovery snapshots must not contain business-row tables.",
            )
        for table_name in _table_names(connection):
            columns = _table_columns(connection, table_name)
            if "workspace_id" not in columns or table_name in physical_tables:
                continue
            foreign = connection.execute(
                f"SELECT 1 FROM {_quote_identifier(table_name)} WHERE workspace_id <> ? LIMIT 1",
                (workspace_id,),
            ).fetchone()
            if foreign is not None:
                raise WorkspaceRecoveryError("RECOVERY_WORKSPACE_MISMATCH", "SQLite recovery artifact contains another workspace.")


def _create_duckdb_snapshot(source_path: Path, target: Path, physical_tables: list[str]) -> bool:
    if not source_path.exists():
        return False
    _assert_not_symlink(source_path, label="DuckDB database")
    duckdb = _duckdb_module()
    target.parent.mkdir(parents=True, exist_ok=True)
    source_literal = _quote_duckdb_literal(str(source_path.resolve()))
    with duckdb.connect(str(target)) as connection:
        connection.execute(f"ATTACH {source_literal} AS source_db (READ_ONLY)")
        source_tables = {
            str(row[0])
            for row in connection.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_catalog = 'source_db' AND table_schema = 'main'"
            ).fetchall()
        }
        if "__aibi_schema_metadata" in source_tables:
            connection.execute(
                "CREATE TABLE __aibi_schema_metadata AS SELECT * FROM source_db.main.__aibi_schema_metadata"
            )
        if "__aibi_replica_manifest" not in source_tables:
            relations = [name for name in physical_tables if name in source_tables]
            if relations:
                raise WorkspaceRecoveryError(
                    "RECOVERY_DUCKDB_MANIFEST_MISSING",
                    "DuckDB contains workspace relations without a replica manifest.",
                )
            connection.execute("DETACH source_db")
            connection.execute("CHECKPOINT")
            _fsync_file(target)
            return True
        connection.execute(
            "CREATE TABLE __aibi_replica_manifest AS "
            "SELECT * FROM source_db.main.__aibi_replica_manifest WHERE 1 = 0"
        )
        for logical_table in physical_tables:
            description = [str(item[0]) for item in connection.execute("DESCRIBE source_db.main.__aibi_replica_manifest").fetchall()]
            record = connection.execute(
                "SELECT * FROM source_db.main.__aibi_replica_manifest WHERE logical_table = ?",
                [logical_table],
            ).fetchone()
            if record is None:
                raise WorkspaceRecoveryError(
                    "RECOVERY_DUCKDB_MANIFEST_DRIFT",
                    "DuckDB is missing an active dataset binding required by recovery.",
                )
            item = dict(zip(description, record, strict=True))
            if int(item.get("manifest_version") or 0) != 2 or _duckdb_relation_kind(connection, logical_table, catalog="source_db") != "VIEW":
                raise WorkspaceRecoveryError(
                    "RECOVERY_DUCKDB_MANIFEST_DRIFT",
                    "DuckDB dataset manifest points to a missing workspace view.",
                )
            paths = _manifest_object_paths(item.get("object_keys_json"), item.get("object_hashes_json"))
            connection.execute(
                "INSERT INTO __aibi_replica_manifest "
                "SELECT * FROM source_db.main.__aibi_replica_manifest WHERE logical_table = ?",
                [logical_table],
            )
            connection.execute(
                f"CREATE VIEW {_quote_identifier(logical_table)} AS "
                f"SELECT * FROM {_parquet_view_source(paths)}"
            )
        connection.execute("DETACH source_db")
        connection.execute("CHECKPOINT")
    _fsync_file(target)
    return True


def _manifest_base(manifest: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in manifest.items() if key not in {"contentFingerprint", "verified", "totalBytes"}}


def unfinished_recovery_fences(recovery_root: Path) -> list[dict[str, str]]:
    """Return persistent restore fences without exposing local artifact paths."""
    root = _ensure_root(_absolute(recovery_root), create=False)
    if not root.exists():
        return []
    fences: list[dict[str, str]] = []
    for workspace_root in sorted(root.iterdir(), key=lambda path: path.name):
        _assert_not_symlink(workspace_root, label="Workspace recovery directory")
        if not workspace_root.is_dir() or not workspace_root.name.startswith("workspace_"):
            continue
        operation_root = _safe_child(workspace_root, ".operations")
        if not operation_root.exists():
            continue
        _assert_not_symlink(operation_root, label="Recovery operation directory")
        for journal_path in sorted(operation_root.glob("journal_*.json"), key=lambda path: path.name):
            _assert_regular_file(journal_path)
            journal = _read_recovery_journal(journal_path)
            workspace_id = _workspace_id(journal.get("workspaceId"))
            if workspace_root.name != _workspace_bucket(workspace_id) or journal.get("schema") != RECOVERY_JOURNAL_SCHEMA:
                raise WorkspaceRecoveryError("RECOVERY_JOURNAL_INVALID", "Recovery journal failed workspace validation.")
            status = str(journal.get("status") or "")
            if status in {"prepared", "applying", "applied", "needs_attention"}:
                fences.append({
                    "workspaceId": workspace_id,
                    "status": status,
                    "recoveryAction": "workspace-recovery-reconcile",
                })
        for receipt_path in sorted(operation_root.glob("workspace-delete_*.json"), key=lambda path: path.name):
            _assert_regular_file(receipt_path)
            receipt = _read_recovery_operation(receipt_path)
            workspace_id = _workspace_id(receipt.get("workspaceId"))
            if (
                workspace_root.name != _workspace_bucket(workspace_id)
                or receipt.get("schema") != RECOVERY_OPERATION_SCHEMA
                or receipt.get("operation") != "workspace-delete"
            ):
                raise WorkspaceRecoveryError("RECOVERY_OPERATION_RECEIPT_INVALID", "Workspace delete receipt failed validation.")
            status = str(receipt.get("status") or "")
            if status in {"prepared", "duckdb_deleted", "sqlite_deleted", "needs_attention"}:
                fences.append({
                    "workspaceId": workspace_id,
                    "status": status,
                    "recoveryAction": "workspace-recovery-reconcile",
                })
    return fences


def _public_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    files = [
        {
            "kind": str(item.get("kind") or ""),
            "bytes": int(item.get("bytes") or 0),
            "sha256": str(item.get("sha256") or ""),
        }
        for item in manifest.get("files", [])
        if isinstance(item, dict)
    ]
    return {
        "schema": manifest.get("schema"),
        "workspaceId": manifest.get("workspaceId"),
        "recoveryPointKey": manifest.get("recoveryPointKey"),
        "createdAt": manifest.get("createdAt"),
        "reason": manifest.get("reason"),
        "status": manifest.get("status"),
        "contentFingerprint": manifest.get("contentFingerprint"),
        "workspaceStateFingerprint": manifest.get("workspaceStateFingerprint"),
        "sqliteSchemaVersion": manifest.get("sqliteSchemaVersion"),
        "duckdbSchemaVersion": manifest.get("duckdbSchemaVersion"),
        "currentSourceRunId": manifest.get("currentSourceRunId"),
        "sourceVersions": manifest.get("sourceVersions", []),
        "files": files,
        "totalBytes": sum(item["bytes"] for item in files),
        "verified": manifest.get("verified", False),
    }


class WorkspaceRecoveryService:
    def __init__(
        self,
        *,
        open_db: Callable[[], sqlite3.Connection],
        sqlite_path: Path,
        duckdb_path: Path,
        recovery_root: Path,
    ) -> None:
        self.open_db = open_db
        self.sqlite_path = _absolute(sqlite_path)
        self.duckdb_path = _absolute(duckdb_path)
        self.recovery_root = _absolute(recovery_root)

    def _workspace_root(self, workspace_id: str, *, create: bool) -> Path:
        return _workspace_root(self.recovery_root, workspace_id, create=create)

    def reconcile_unfinished_restores(self) -> dict[str, Any]:
        """Roll unfinished restore journals back to their verified safety points."""
        root = _ensure_root(self.recovery_root, create=False)
        if not root.exists():
            return {"ok": True, "reconciled": [], "needsAttention": [], "count": 0}
        reconciled: list[dict[str, Any]] = []
        needs_attention: list[dict[str, Any]] = []
        for workspace_root in sorted(root.iterdir(), key=lambda path: path.name):
            _assert_not_symlink(workspace_root, label="Workspace recovery directory")
            if not workspace_root.is_dir() or not workspace_root.name.startswith("workspace_"):
                continue
            operation_root = _safe_child(workspace_root, ".operations")
            if not operation_root.exists():
                continue
            _assert_not_symlink(operation_root, label="Recovery operation directory")
            for journal_path in sorted(operation_root.glob("journal_*.json"), key=lambda path: path.name):
                _assert_regular_file(journal_path)
                journal = _read_recovery_journal(journal_path)
                workspace_id = _workspace_id(journal.get("workspaceId"))
                if workspace_root.name != _workspace_bucket(workspace_id) or journal.get("schema") != RECOVERY_JOURNAL_SCHEMA:
                    raise WorkspaceRecoveryError("RECOVERY_JOURNAL_INVALID", "Recovery journal failed workspace validation.")
                status = str(journal.get("status") or "")
                if status in {"applied", "completed"} and isinstance(journal.get("result"), dict):
                    try:
                        result = dict(journal["result"])
                        intent_fingerprint = str(journal.get("intentFingerprint") or "")
                        request_key_fingerprint = str(journal.get("requestKeyFingerprint") or "")
                        receipt_name = str(journal.get("operationReceiptName") or "")
                        expected_state = str((result.get("restored") or {}).get("restoredStateFingerprint") or "")
                        if (
                            not intent_fingerprint
                            or not re.fullmatch(r"restore_[a-f0-9]{32}\.json", receipt_name)
                            or not re.fullmatch(r"[a-f0-9]{64}", request_key_fingerprint)
                            or not re.fullmatch(r"[a-f0-9]{64}", expected_state)
                            or self._state(workspace_id)["fingerprint"] != expected_state
                        ):
                            raise WorkspaceRecoveryError(
                                "RECOVERY_APPLIED_STATE_MISMATCH",
                                "Applied restore journal does not match the current workspace state.",
                            )
                        self._write_operation_at(
                            _safe_child(operation_root, receipt_name),
                            workspace_id=workspace_id,
                            operation="restore",
                            request_key_fingerprint=request_key_fingerprint,
                            intent_fingerprint=intent_fingerprint,
                            status="completed",
                            result=result,
                        )
                        journal.update({
                            "status": "completed",
                            "receiptRepairedAfterRestart": True,
                            "updatedAt": _utc_now(),
                        })
                        _write_recovery_journal(journal_path, journal)
                        reconciled.append({"workspaceId": workspace_id, "status": "completed", "receiptRepaired": True})
                        continue
                    except Exception:
                        # The verified safety point remains the only trustworthy
                        # state if an allegedly applied restore cannot be proven.
                        status = "applying"
                if status not in {"prepared", "applying", "needs_attention"}:
                    continue
                safety_key = _recovery_key(journal.get("safetyRecoveryPointKey"))
                try:
                    safety_manifest = self._load_manifest(workspace_id, safety_key, verify=True)
                    rollback = self._apply_point(workspace_id, safety_manifest)
                    journal.update({
                        "status": "rolled_back",
                        "rollback": rollback,
                        "reconciledAfterRestart": True,
                        "updatedAt": _utc_now(),
                    })
                    _write_recovery_journal(journal_path, journal)
                    reconciled.append({"workspaceId": workspace_id, "safetyRecoveryPointKey": safety_key, "status": "rolled_back"})
                except Exception as error:
                    journal.update({
                        "status": "needs_attention",
                        "rollbackErrorCode": getattr(error, "code", "RECOVERY_ROLLBACK_FAILED"),
                        "updatedAt": _utc_now(),
                    })
                    _write_recovery_journal(journal_path, journal)
                    needs_attention.append({
                        "workspaceId": workspace_id,
                        "safetyRecoveryPointKey": safety_key,
                        "status": "needs_attention",
                        "errorCode": journal["rollbackErrorCode"],
                    })
            for receipt_path in sorted(operation_root.glob("delete_*.json"), key=lambda path: path.name):
                _assert_regular_file(receipt_path)
                receipt = _read_recovery_operation(receipt_path)
                if receipt.get("schema") != RECOVERY_OPERATION_SCHEMA or receipt.get("operation") != "delete":
                    raise WorkspaceRecoveryError("RECOVERY_OPERATION_RECEIPT_INVALID", "Delete recovery receipt failed validation.")
                if receipt.get("status") != "prepared":
                    continue
                workspace_id = _workspace_id(receipt.get("workspaceId"))
                result = receipt.get("result") if isinstance(receipt.get("result"), dict) else {}
                plan = result.get("recoveryPlan") if isinstance(result.get("recoveryPlan"), dict) else {}
                recovery_point_key = _recovery_key(plan.get("recoveryPointKey"))
                request_key_fingerprint = str(receipt.get("requestKeyFingerprint") or "")
                if not re.fullmatch(r"[a-f0-9]{64}", request_key_fingerprint):
                    raise WorkspaceRecoveryError("RECOVERY_OPERATION_RECEIPT_INVALID", "Delete recovery receipt request fingerprint is invalid.")
                try:
                    self._finish_prepared_delete(
                        workspace_id,
                        recovery_point_key,
                        request_key=None,
                        request_key_fingerprint=request_key_fingerprint,
                        intent_fingerprint=str(receipt.get("intentFingerprint") or ""),
                        result=result,
                        receipt_path=receipt_path,
                    )
                    reconciled.append({"workspaceId": workspace_id, "status": "delete_completed", "recoveryPointKey": recovery_point_key})
                except Exception as error:
                    needs_attention.append({
                        "workspaceId": workspace_id,
                        "status": "delete_needs_attention",
                        "recoveryPointKey": recovery_point_key,
                        "errorCode": getattr(error, "code", "RECOVERY_DELETE_RECONCILE_FAILED"),
                    })
            for receipt_path in sorted(operation_root.glob("workspace-delete_*.json"), key=lambda path: path.name):
                _assert_regular_file(receipt_path)
                receipt = _read_recovery_operation(receipt_path)
                if receipt.get("schema") != RECOVERY_OPERATION_SCHEMA or receipt.get("operation") != "workspace-delete":
                    raise WorkspaceRecoveryError("RECOVERY_OPERATION_RECEIPT_INVALID", "Workspace delete receipt failed validation.")
                workspace_id = _workspace_id(receipt.get("workspaceId"))
                status = str(receipt.get("status") or "")
                if status == "completed":
                    continue
                if status == "needs_attention":
                    result = receipt.get("result") if isinstance(receipt.get("result"), dict) else {}
                    resumable_final_gc = (
                        str(result.get("resumeFromStatus") or "") == "sqlite_deleted"
                        or (
                            not result.get("resumeFromStatus")
                            and isinstance(result.get("deletedCounts"), dict)
                        )
                    )
                    if not resumable_final_gc:
                        needs_attention.append({
                            "workspaceId": workspace_id,
                            "status": "workspace_delete_needs_attention",
                            "errorCode": str(result.get("errorCode") or "WORKSPACE_DELETE_NEEDS_ATTENTION"),
                        })
                        continue
                try:
                    from workspace_command_service import reconcile_workspace_delete_receipt

                    result = reconcile_workspace_delete_receipt(self, receipt_path)
                    reconciled.append({
                        "workspaceId": workspace_id,
                        "status": "workspace_delete_completed",
                        "recoveryPointKey": str((result.get("auditRecoveryPoint") or {}).get("recoveryPointKey") or ""),
                    })
                except Exception as error:
                    from workspace_command_service import mark_workspace_delete_needs_attention

                    marked = mark_workspace_delete_needs_attention(self, receipt_path, error)
                    needs_attention.append({
                        "workspaceId": workspace_id,
                        "status": "workspace_delete_needs_attention",
                        "errorCode": str(marked.get("errorCode") or "WORKSPACE_DELETE_RECONCILE_FAILED"),
                    })
        return {"ok": not needs_attention, "reconciled": reconciled, "needsAttention": needs_attention, "count": len(reconciled) + len(needs_attention)}

    def _point_directory(self, workspace_id: str, recovery_point_key: str, *, must_exist: bool = False) -> Path:
        workspace_root = self._workspace_root(workspace_id, create=False)
        return _safe_child(workspace_root, _recovery_key(recovery_point_key), must_exist=must_exist)

    def _operation_file(self, workspace_id: str, operation: str, request_key: str, *, create: bool) -> Path:
        workspace_root = self._workspace_root(workspace_id, create=create)
        operation_root = _safe_child(workspace_root, ".operations")
        if create:
            operation_root.mkdir(exist_ok=True)
            _assert_not_symlink(operation_root, label="Recovery operation directory")
        request_fingerprint = _fingerprint({"workspaceId": workspace_id, "operation": operation, "requestKey": request_key})
        return _safe_child(operation_root, f"{operation}_{request_fingerprint[:32]}.json")

    def _operation_replay(
        self,
        workspace_id: str,
        operation: str,
        request_key: str,
        intent_fingerprint: str,
    ) -> dict[str, Any] | None:
        path = self._operation_file(workspace_id, operation, request_key, create=False)
        if not path.exists():
            return None
        receipt = _read_recovery_operation(path)
        if receipt.get("schema") != RECOVERY_OPERATION_SCHEMA or receipt.get("workspaceId") != workspace_id:
            raise WorkspaceRecoveryError("RECOVERY_OPERATION_RECEIPT_INVALID", "Recovery operation receipt failed validation.")
        if receipt.get("intentFingerprint") != intent_fingerprint:
            raise WorkspaceRecoveryError(
                "RECOVERY_REQUEST_KEY_CONFLICT",
                "requestKey was already used with different recovery inputs.",
                "Generate a new requestKey and preview the operation again.",
            )
        if receipt.get("status") != "completed" or not isinstance(receipt.get("result"), dict):
            return None
        return {**receipt["result"], "changed": False, "idempotentReplay": True}

    def _operation_receipt(self, workspace_id: str, operation: str, request_key: str) -> dict[str, Any] | None:
        path = self._operation_file(workspace_id, operation, request_key, create=False)
        if not path.exists():
            return None
        receipt = _read_recovery_operation(path)
        if (
            receipt.get("schema") != RECOVERY_OPERATION_SCHEMA
            or receipt.get("workspaceId") != workspace_id
            or receipt.get("operation") != operation
        ):
            raise WorkspaceRecoveryError("RECOVERY_OPERATION_RECEIPT_INVALID", "Recovery operation receipt failed validation.")
        return receipt

    def _write_operation(
        self,
        workspace_id: str,
        operation: str,
        request_key: str,
        intent_fingerprint: str,
        status: str,
        result: dict[str, Any],
    ) -> None:
        path = self._operation_file(workspace_id, operation, request_key, create=True)
        self._write_operation_at(
            path,
            workspace_id=workspace_id,
            operation=operation,
            request_key_fingerprint=hashlib.sha256(request_key.encode("utf-8")).hexdigest(),
            intent_fingerprint=intent_fingerprint,
            status=status,
            result=result,
        )

    def _write_operation_at(
        self,
        path: Path,
        *,
        workspace_id: str,
        operation: str,
        request_key_fingerprint: str,
        intent_fingerprint: str,
        status: str,
        result: dict[str, Any],
    ) -> None:
        payload = {
            "schema": RECOVERY_OPERATION_SCHEMA,
            "workspaceId": workspace_id,
            "operation": operation,
            "requestKeyFingerprint": request_key_fingerprint,
            "intentFingerprint": intent_fingerprint,
            "status": status,
            "updatedAt": _utc_now(),
            "result": result,
        }
        payload["contentFingerprint"] = _fingerprint(payload)
        _atomic_json(path, payload)

    def _delete_tombstone(self, workspace_id: str, recovery_point_key: str, request_key_fingerprint: str) -> Path:
        workspace_root = self._workspace_root(workspace_id, create=False)
        suffix = request_key_fingerprint[:20]
        return _safe_child(workspace_root, f".deleting-{recovery_point_key}-{suffix}")

    def _finish_prepared_delete(
        self,
        workspace_id: str,
        recovery_point_key: str,
        request_key: str | None,
        request_key_fingerprint: str,
        intent_fingerprint: str,
        result: dict[str, Any],
        receipt_path: Path | None = None,
        fail_at: str = "",
    ) -> dict[str, Any]:
        completed_result = dict(result)
        gc_candidates = [
            dict(item)
            for item in completed_result.pop("_datasetObjectGcCandidates", [])
            if isinstance(item, dict)
        ]
        directory = self._point_directory(workspace_id, recovery_point_key, must_exist=False)
        tombstone = self._delete_tombstone(workspace_id, recovery_point_key, request_key_fingerprint)
        if directory.exists() and tombstone.exists():
            raise WorkspaceRecoveryError(
                "RECOVERY_DELETE_STATE_AMBIGUOUS",
                "Both the recovery point and its delete tombstone exist.",
            )
        if directory.exists():
            os.replace(directory, tombstone)
            _fsync_directory(directory.parent)
        if fail_at == "after_delete_rename":
            raise RuntimeError("Injected recovery delete interruption after tombstone rename")
        if tombstone.exists():
            _assert_not_symlink(tombstone, label="Recovery delete tombstone")
            shutil.rmtree(tombstone)
            _fsync_directory(tombstone.parent)
        with closing(self.open_db()) as connection:
            completed_result["datasetObjectGc"] = collect_unreferenced_dataset_objects(
                connection,
                candidates=gc_candidates,
                duckdb_paths=[
                    self.duckdb_path,
                    *recovery_point_duckdb_catalogs(self.recovery_root, workspace_id=workspace_id),
                ],
            )
        if request_key is not None:
            self._write_operation(
                workspace_id,
                "delete",
                request_key,
                intent_fingerprint,
                "completed",
                completed_result,
            )
        elif receipt_path is not None:
            self._write_operation_at(
                receipt_path,
                workspace_id=workspace_id,
                operation="delete",
                request_key_fingerprint=request_key_fingerprint,
                intent_fingerprint=intent_fingerprint,
                status="completed",
                result=completed_result,
            )
        else:
            raise WorkspaceRecoveryError("RECOVERY_DELETE_RECEIPT_MISSING", "Delete reconciliation receipt is missing.")
        return completed_result

    def _state(self, workspace_id: str) -> dict[str, Any]:
        with closing(self.open_db()) as connection:
            connection.row_factory = sqlite3.Row
            return _workspace_state(connection, workspace_id, self.duckdb_path)

    def _assert_no_active_import(self, workspace_id: str) -> None:
        """Recovery must never snapshot or replace a workspace owned by an import worker."""
        with closing(self.open_db()) as connection:
            connection.row_factory = sqlite3.Row
            active_lease = None
            unfinished_activation = None
            if _table_exists(connection, "import_workspace_leases"):
                active_lease = connection.execute(
                    "SELECT job_key FROM import_workspace_leases WHERE workspace_id = ? AND active = 1 LIMIT 1",
                    (workspace_id,),
                ).fetchone()
            if _table_exists(connection, "source_activation_journals"):
                unfinished_activation = connection.execute(
                    "SELECT job_key FROM source_activation_journals WHERE workspace_id = ? AND phase <> 'finalized' LIMIT 1",
                    (workspace_id,),
                ).fetchone()
        if active_lease is not None or unfinished_activation is not None:
            raise WorkspaceRecoveryError(
                "RECOVERY_WORKSPACE_BUSY",
                "Workspace recovery is blocked while an import activation owns the workspace.",
                "Wait for the import job to finish or reconcile it before retrying recovery.",
            )

    def _source_versions(self, connection: sqlite3.Connection, workspace_id: str) -> list[dict[str, Any]]:
        columns = set(_table_columns(connection, "table_registry")) if _table_exists(connection, "table_registry") else set()
        if not columns:
            return []
        requested = [name for name in ("table_key", "data_version", "updated_at") if name in columns]
        if not requested:
            return []
        rows = connection.execute(
            f"SELECT {', '.join(_quote_identifier(name) for name in requested)} "
            "FROM table_registry WHERE workspace_id = ? ORDER BY table_key",
            (workspace_id,),
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(zip(requested, row, strict=True))
            result.append({
                "tableKey": str(item.get("table_key") or ""),
                "dataVersion": int(item.get("data_version") or 0),
                "updatedAt": str(item.get("updated_at") or ""),
            })
        return result

    def _plan(
        self,
        operation: str,
        workspace_id: str,
        request_key: str,
        *,
        reason: str = "",
        manifest: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        state = self._state(workspace_id)
        intent = {
            "operation": operation,
            "workspaceId": workspace_id,
            "reason": reason or None,
            "recoveryPointKey": manifest.get("recoveryPointKey") if manifest else None,
            "recoveryPointFingerprint": manifest.get("contentFingerprint") if manifest else None,
        }
        intent_fingerprint = _fingerprint({"schema": RECOVERY_PLAN_SCHEMA, **intent})
        plan_input = {
            **intent,
            "requestKeyFingerprint": hashlib.sha256(request_key.encode("utf-8")).hexdigest(),
            "intentFingerprint": intent_fingerprint,
            "currentWorkspaceStateFingerprint": state["fingerprint"],
        }
        input_fingerprint = _fingerprint(plan_input)
        plan = {
            "schema": RECOVERY_PLAN_SCHEMA,
            "status": "waiting-confirmation",
            "operation": operation,
            "workspaceId": workspace_id,
            "requestKeyFingerprint": plan_input["requestKeyFingerprint"],
            "intentFingerprint": intent_fingerprint,
            "inputFingerprint": input_fingerprint,
            "planFingerprint": _fingerprint({"schema": RECOVERY_PLAN_SCHEMA, "inputFingerprint": input_fingerprint}),
            "currentWorkspaceStateFingerprint": state["fingerprint"],
            "recoveryPointKey": manifest.get("recoveryPointKey") if manifest else f"rp_{input_fingerprint[:24]}",
            "recoveryPointFingerprint": manifest.get("contentFingerprint") if manifest else None,
            "estimatedBytes": _estimate_bytes(self.sqlite_path, self.duckdb_path) if operation == "create" else int(manifest.get("totalBytes") or 0) if manifest else 0,
            "writesBusinessState": operation == "restore",
            "requiresSafetyPoint": operation == "restore",
            "invalidationKeys": ["workspace-status", "workbench", "dashboards", "query-freshness"] if operation == "restore" else ["workspace-recovery"],
        }
        return plan

    @staticmethod
    def _require_plan(expected_plan_fingerprint: str, plan: dict[str, Any]) -> None:
        expected = str(expected_plan_fingerprint or "").strip()
        if not expected or expected != str(plan.get("planFingerprint") or ""):
            raise WorkspaceRecoveryError(
                "RECOVERY_PLAN_STALE",
                "Confirmation requires the exact fingerprint from the latest dry-run.",
                "Preview the operation again before confirming.",
            )

    def preview_create(self, workspace_id: str, reason: str, request_key: str) -> dict[str, Any]:
        workspace_id = _workspace_id(workspace_id)
        reason = _reason(reason)
        request_key = _request_key(request_key)
        plan = self._plan("create", workspace_id, request_key, reason=reason)
        return {
            "ok": True,
            "dryRun": True,
            "requiresConfirmation": True,
            "workspaceId": workspace_id,
            "recoveryPlan": plan,
        }

    def _create_confirmed(
        self,
        workspace_id: str,
        reason: str,
        request_key: str,
        expected_plan_fingerprint: str,
        *,
        fail_at: str = "",
    ) -> dict[str, Any]:
        plan = self._plan("create", workspace_id, request_key, reason=reason)
        replay = self._operation_replay(workspace_id, "create", request_key, str(plan["intentFingerprint"]))
        if replay is not None:
            return replay
        self._require_plan(expected_plan_fingerprint, plan)
        self._assert_no_active_import(workspace_id)
        _ensure_disk_capacity(self.recovery_root, int(plan["estimatedBytes"]))
        workspace_root = self._workspace_root(workspace_id, create=True)
        recovery_point_key = str(plan["recoveryPointKey"])
        final_directory = _safe_child(workspace_root, recovery_point_key)
        if final_directory.exists():
            manifest = self._load_manifest(workspace_id, recovery_point_key, verify=True)
            if manifest.get("requestKeyFingerprint") != plan["requestKeyFingerprint"]:
                raise WorkspaceRecoveryError("RECOVERY_POINT_COLLISION", "Recovery point key collides with different inputs.")
            result = {
                "ok": True,
                "confirmed": True,
                "changed": False,
                "workspaceId": workspace_id,
                "recoveryPlan": plan,
                "recoveryPoint": _public_manifest(manifest),
                "invalidationKeys": ["workspace-recovery"],
            }
            self._write_operation(workspace_id, "create", request_key, str(plan["intentFingerprint"]), "completed", result)
            return result
        staging = _safe_child(workspace_root, f".staging-{recovery_point_key}-{uuid.uuid4().hex}")
        staging.mkdir(exist_ok=False)
        try:
            with closing(self.open_db()) as connection:
                connection.row_factory = sqlite3.Row
                state = _workspace_state(connection, workspace_id, self.duckdb_path)
                if state["fingerprint"] != plan["currentWorkspaceStateFingerprint"]:
                    raise WorkspaceRecoveryError("RECOVERY_PLAN_STALE", "Workspace changed after recovery preview.")
                sqlite_artifact = staging / SQLITE_ARTIFACT
                _create_sqlite_snapshot(connection, sqlite_artifact, workspace_id)
                source_versions = self._source_versions(connection, workspace_id)
                physical_tables = _workspace_physical_tables(connection, workspace_id)
            if fail_at == "after_sqlite_snapshot":
                raise RuntimeError("Injected recovery creation interruption after SQLite snapshot")
            duckdb_artifact = staging / DUCKDB_ARTIFACT
            duckdb_created = _create_duckdb_snapshot(self.duckdb_path, duckdb_artifact, physical_tables)
            if fail_at == "after_duckdb_snapshot":
                raise RuntimeError("Injected recovery creation interruption after DuckDB snapshot")
            snapshot_uri = f"file:{sqlite_artifact.resolve().as_posix()}?mode=ro"
            with closing(sqlite3.connect(snapshot_uri, uri=True)) as snapshot_connection:
                snapshot_connection.row_factory = sqlite3.Row
                snapshot_state = _workspace_state(snapshot_connection, workspace_id, duckdb_artifact)
            if snapshot_state["fingerprint"] != state["fingerprint"]:
                raise WorkspaceRecoveryError(
                    "RECOVERY_SNAPSHOT_STATE_MISMATCH",
                    "Recovery artifacts do not match the workspace state frozen by the preview.",
                )
            files: list[dict[str, Any]] = []
            for kind, path in (("sqlite-control", sqlite_artifact), ("duckdb-catalog", duckdb_artifact)):
                if not path.exists():
                    continue
                metadata = _assert_regular_file(path)
                files.append({"kind": kind, "file": path.name, "bytes": metadata.st_size, "sha256": _sha256_file(path)})
            manifest = {
                "schema": RECOVERY_POINT_SCHEMA,
                "workspaceId": workspace_id,
                "recoveryPointKey": recovery_point_key,
                "createdAt": _utc_now(),
                "reason": reason,
                "status": "ready",
                "requestKeyFingerprint": plan["requestKeyFingerprint"],
                "inputFingerprint": plan["inputFingerprint"],
                "workspaceStateFingerprint": state["fingerprint"],
                "sqliteSchemaVersion": state["sqliteSchemaVersion"],
                "duckdbSchemaVersion": 2 if duckdb_created else None,
                "currentSourceRunId": state["currentSourceRunId"],
                "sourceVersions": source_versions,
                "files": files,
                "excludes": ["other workspaces", "source files", "environment secrets", "absolute paths"],
            }
            manifest["contentFingerprint"] = _fingerprint(_manifest_base(manifest))
            manifest["verified"] = True
            _atomic_json(staging / MANIFEST_FILE, manifest)
            _fsync_directory(staging)
            if fail_at == "before_publish":
                raise RuntimeError("Injected recovery creation interruption before publish")
            if self._state(workspace_id)["fingerprint"] != plan["currentWorkspaceStateFingerprint"]:
                raise WorkspaceRecoveryError(
                    "RECOVERY_PLAN_STALE",
                    "Workspace changed while the recovery point was being prepared.",
                    "Preview the create operation again.",
                )
            os.replace(staging, final_directory)
            _fsync_directory(workspace_root)
            verified = self._load_manifest(workspace_id, recovery_point_key, verify=True)
            result = {
                "ok": True,
                "confirmed": True,
                "changed": True,
                "workspaceId": workspace_id,
                "recoveryPlan": plan,
                "recoveryPoint": _public_manifest(verified),
                "invalidationKeys": ["workspace-recovery"],
            }
            self._write_operation(workspace_id, "create", request_key, str(plan["intentFingerprint"]), "completed", result)
            return result
        except Exception:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
            raise

    def create(
        self,
        workspace_id: str,
        reason: str,
        request_key: str,
        *,
        confirm: bool = False,
        expected_plan_fingerprint: str = "",
        fail_at: str = "",
    ) -> dict[str, Any]:
        workspace_id = _workspace_id(workspace_id)
        reason = _reason(reason)
        request_key = _request_key(request_key)
        if not confirm:
            return self.preview_create(workspace_id, reason, request_key)
        return self._create_confirmed(
            workspace_id,
            reason,
            request_key,
            expected_plan_fingerprint,
            fail_at=fail_at,
        )

    def _load_manifest(self, workspace_id: str, recovery_point_key: str, *, verify: bool) -> dict[str, Any]:
        directory = self._point_directory(workspace_id, recovery_point_key, must_exist=True)
        _assert_not_symlink(directory, label="Recovery point directory")
        if not directory.is_dir():
            raise WorkspaceRecoveryError("RECOVERY_POINT_INVALID", "Recovery point is not a directory.")
        manifest = _read_json_file(_safe_child(directory, MANIFEST_FILE, must_exist=True))
        if manifest.get("schema") != RECOVERY_POINT_SCHEMA or manifest.get("status") != "ready":
            raise WorkspaceRecoveryError("RECOVERY_MANIFEST_INVALID", "Recovery point manifest schema or status is invalid.")
        if manifest.get("workspaceId") != workspace_id or manifest.get("recoveryPointKey") != recovery_point_key:
            raise WorkspaceRecoveryError("RECOVERY_WORKSPACE_MISMATCH", "Recovery point does not belong to the current workspace.")
        stored_fingerprint = str(manifest.get("contentFingerprint") or "")
        if len(stored_fingerprint) != 64 or stored_fingerprint != _fingerprint(_manifest_base(manifest)):
            raise WorkspaceRecoveryError("RECOVERY_MANIFEST_HASH_MISMATCH", "Recovery manifest fingerprint does not match its content.")
        files = manifest.get("files")
        if not isinstance(files, list) or not files:
            raise WorkspaceRecoveryError("RECOVERY_MANIFEST_INVALID", "Recovery point has no verified artifacts.")
        seen: set[str] = set()
        if verify:
            for entry in files:
                if not isinstance(entry, dict):
                    raise WorkspaceRecoveryError("RECOVERY_MANIFEST_INVALID", "Recovery manifest file entry is invalid.")
                name = str(entry.get("file") or "")
                kind = str(entry.get("kind") or "")
                if name not in {SQLITE_ARTIFACT, DUCKDB_ARTIFACT} or name in seen or Path(name).name != name:
                    raise WorkspaceRecoveryError("RECOVERY_MANIFEST_INVALID", "Recovery manifest contains an unsupported artifact path.")
                if kind not in {"sqlite-control", "duckdb-catalog"}:
                    raise WorkspaceRecoveryError("RECOVERY_MANIFEST_INVALID", "Recovery manifest contains an unsupported artifact kind.")
                seen.add(name)
                path = _safe_child(directory, name, must_exist=True)
                metadata = _assert_regular_file(path)
                if metadata.st_size != int(entry.get("bytes") or -1) or _sha256_file(path) != str(entry.get("sha256") or ""):
                    raise WorkspaceRecoveryError(
                        "RECOVERY_ARTIFACT_HASH_MISMATCH",
                        "Recovery artifact failed its SHA-256 or size check.",
                        "Use a different verified recovery point; do not confirm this restore.",
                    )
            if SQLITE_ARTIFACT not in seen:
                raise WorkspaceRecoveryError("RECOVERY_MANIFEST_INVALID", "Recovery point is missing its SQLite control snapshot.")
            _validate_sqlite_snapshot(_safe_child(directory, SQLITE_ARTIFACT, must_exist=True), workspace_id)
            if DUCKDB_ARTIFACT in seen:
                try:
                    verify_duckdb_manifest_objects(
                        [_safe_child(directory, DUCKDB_ARTIFACT, must_exist=True)]
                    )
                except (FileNotFoundError, OSError, RuntimeError, ValueError) as error:
                    raise WorkspaceRecoveryError(
                        "RECOVERY_DATASET_OBJECT_INTEGRITY_FAILED",
                        "Recovery point references a missing or invalid immutable dataset object.",
                        "Use a different verified recovery point; do not confirm this restore.",
                    ) from error
        manifest = dict(manifest)
        manifest["verified"] = bool(verify)
        manifest["totalBytes"] = sum(int(item.get("bytes") or 0) for item in files if isinstance(item, dict))
        return manifest

    def list(self, workspace_id: str, *, limit: int = 5, verify: bool = False) -> dict[str, Any]:
        workspace_id = _workspace_id(workspace_id)
        with closing(self.open_db()) as connection:
            connection.row_factory = sqlite3.Row
            _assert_workspace_exists(connection, workspace_id)
        workspace_root = self._workspace_root(workspace_id, create=False)
        if not workspace_root.exists():
            return {
                "ok": True,
                "schema": RECOVERY_COLLECTION_SCHEMA,
                "workspaceId": workspace_id,
                "health": "empty",
                "recoveryPoints": [],
                "count": 0,
            }
        requested_limit = max(1, min(int(limit or 5), 100))
        manifests: list[dict[str, Any]] = []
        invalid_count = 0
        for item in workspace_root.iterdir():
            if item.name.startswith("."):
                continue
            if not RECOVERY_KEY_PATTERN.fullmatch(item.name):
                invalid_count += 1
                continue
            try:
                manifests.append(self._load_manifest(workspace_id, item.name, verify=verify))
            except WorkspaceRecoveryError:
                invalid_count += 1
        manifests.sort(key=lambda item: str(item.get("createdAt") or ""), reverse=True)
        points = [_public_manifest(item) for item in manifests[:requested_limit]]
        return {
            "ok": True,
            "schema": RECOVERY_COLLECTION_SCHEMA,
            "workspaceId": workspace_id,
            "health": "attention" if invalid_count else "ready" if manifests else "empty",
            "recoveryPoints": points,
            "count": len(manifests),
            "invalidCount": invalid_count,
            "verified": verify,
        }

    def inspect(self, workspace_id: str, recovery_point_key: str, *, verify: bool = True) -> dict[str, Any]:
        workspace_id = _workspace_id(workspace_id)
        recovery_point_key = _recovery_key(recovery_point_key)
        manifest = self._load_manifest(workspace_id, recovery_point_key, verify=verify)
        return {
            "ok": True,
            "workspaceId": workspace_id,
            "recoveryPoint": _public_manifest(manifest),
            "verified": bool(verify),
        }

    def compare(self, workspace_id: str, recovery_point_key: str) -> dict[str, Any]:
        """Compare current table versions with one verified point without exposing rows."""
        workspace_id = _workspace_id(workspace_id)
        recovery_point_key = _recovery_key(recovery_point_key)
        manifest = self._load_manifest(workspace_id, recovery_point_key, verify=True)
        with closing(self.open_db()) as connection:
            connection.row_factory = sqlite3.Row
            _assert_workspace_exists(connection, workspace_id)
            current_versions = self._source_versions(connection, workspace_id)
        target_versions = manifest.get("sourceVersions") if isinstance(manifest.get("sourceVersions"), list) else []
        current_by_key = {str(item.get("tableKey") or ""): item for item in current_versions if isinstance(item, dict) and item.get("tableKey")}
        target_by_key = {str(item.get("tableKey") or ""): item for item in target_versions if isinstance(item, dict) and item.get("tableKey")}
        changes: list[dict[str, Any]] = []
        for table_key in sorted(set(current_by_key) | set(target_by_key)):
            current = current_by_key.get(table_key)
            target = target_by_key.get(table_key)
            current_version = int(current.get("dataVersion") or 0) if current else None
            target_version = int(target.get("dataVersion") or 0) if target else None
            if current is None:
                change = "restore"
            elif target is None:
                change = "remove"
            elif current_version != target_version:
                change = "version-change"
            else:
                change = "unchanged"
            changes.append({
                "tableKey": table_key,
                "change": change,
                "currentDataVersion": current_version,
                "targetDataVersion": target_version,
            })
        changed = [item for item in changes if item["change"] != "unchanged"]
        current_state = self._state(workspace_id)
        return {
            "ok": True,
            "schema": RECOVERY_COMPARISON_SCHEMA,
            "workspaceId": workspace_id,
            "recoveryPointKey": recovery_point_key,
            "verified": True,
            "currentWorkspaceStateFingerprint": current_state["fingerprint"],
            "targetWorkspaceStateFingerprint": str(manifest.get("workspaceStateFingerprint") or ""),
            "currentSourceRunId": current_state.get("currentSourceRunId"),
            "targetSourceRunId": manifest.get("currentSourceRunId"),
            "changes": changes,
            "changedCount": len(changed),
            "unchangedCount": len(changes) - len(changed),
            "summary": {
                "restore": sum(1 for item in changed if item["change"] == "restore"),
                "remove": sum(1 for item in changed if item["change"] == "remove"),
                "versionChange": sum(1 for item in changed if item["change"] == "version-change"),
            },
            "exposesBusinessRows": False,
        }

    def _restore_duckdb(self, snapshot_path: Path | None, current_physical: list[str]) -> dict[str, Any]:
        if not self.duckdb_path.exists() and snapshot_path is None:
            return {"changed": False, "restoredDatasets": 0, "removedDatasets": 0}
        duckdb = _duckdb_module()
        self.duckdb_path.parent.mkdir(parents=True, exist_ok=True)
        with duckdb.connect(str(self.duckdb_path)) as connection:
            snapshot_tables: set[str] = set()
            attached = False
            if snapshot_path is not None:
                _assert_regular_file(snapshot_path)
                alias_literal = _quote_duckdb_literal(str(snapshot_path.resolve()))
                connection.execute(f"ATTACH {alias_literal} AS recovery_snapshot (READ_ONLY)")
                attached = True
                snapshot_tables = {
                    str(row[0])
                    for row in connection.execute(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_catalog = 'recovery_snapshot' AND table_schema = 'main'"
                    ).fetchall()
                }
            connection.execute("BEGIN TRANSACTION")
            try:
                manifest_exists = _duckdb_table_exists(connection, "__aibi_replica_manifest")
                removed = 0
                for logical_table in current_physical:
                    relation = connection.execute(
                        "SELECT table_type FROM information_schema.tables WHERE table_schema = current_schema() AND table_name = ?",
                        [logical_table],
                    ).fetchone()
                    if relation and str(relation[0]).upper() == "VIEW":
                        connection.execute(f"DROP VIEW {_quote_identifier(logical_table)}")
                    elif relation:
                        connection.execute(f"DROP TABLE {_quote_identifier(logical_table)}")
                    if manifest_exists:
                        connection.execute("DELETE FROM __aibi_replica_manifest WHERE logical_table = ?", [logical_table])
                    if relation:
                        removed += 1
                restored = 0
                if snapshot_path is not None:
                    if "__aibi_replica_manifest" in snapshot_tables:
                        if not manifest_exists:
                            connection.execute(
                                "CREATE TABLE __aibi_replica_manifest AS "
                                "SELECT * FROM recovery_snapshot.main.__aibi_replica_manifest WHERE 1 = 0"
                            )
                            manifest_exists = True
                        description = [
                            str(item[0])
                            for item in connection.execute(
                                "DESCRIBE recovery_snapshot.main.__aibi_replica_manifest"
                            ).fetchall()
                        ]
                        required = {
                            "manifest_version", "logical_table", "source_version", "version_id",
                            "object_keys_json", "object_paths_json", "object_hashes_json",
                            "schema_fingerprint", "content_fingerprint", "row_count", "published_at",
                        }
                        if not required.issubset(description):
                            raise WorkspaceRecoveryError(
                                "RECOVERY_DUCKDB_MANIFEST_V2_REQUIRED",
                                "Recovery DuckDB dataset manifest is not version 2.",
                            )
                        rows = connection.execute(
                            "SELECT * FROM recovery_snapshot.main.__aibi_replica_manifest ORDER BY logical_table"
                        ).fetchall()
                        for raw_record in rows:
                            record = dict(zip(description, raw_record, strict=True))
                            logical_name = str(record.get("logical_table") or "")
                            if int(record.get("manifest_version") or 0) != 2:
                                raise WorkspaceRecoveryError(
                                    "RECOVERY_DUCKDB_MANIFEST_V2_REQUIRED",
                                    "Recovery DuckDB dataset manifest is not version 2.",
                                )
                            paths = _manifest_object_paths(record.get("object_keys_json"), record.get("object_hashes_json"))
                            relation = _duckdb_relation_kind(connection, logical_name)
                            if relation == "VIEW":
                                connection.execute(f"DROP VIEW {_quote_identifier(logical_name)}")
                            elif relation:
                                connection.execute(f"DROP TABLE {_quote_identifier(logical_name)}")
                            connection.execute(
                                "DELETE FROM __aibi_replica_manifest WHERE logical_table = ?",
                                [logical_name],
                            )
                            connection.execute(
                                "INSERT INTO __aibi_replica_manifest "
                                "SELECT * FROM recovery_snapshot.main.__aibi_replica_manifest WHERE logical_table = ?",
                                [logical_name],
                            )
                            connection.execute(
                                f"CREATE OR REPLACE VIEW {_quote_identifier(logical_name)} AS "
                                f"SELECT * FROM {_parquet_view_source(paths)}"
                            )
                            restored += 1
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
            finally:
                if attached:
                    try:
                        connection.execute("DETACH recovery_snapshot")
                    except Exception:
                        pass
            connection.execute("CHECKPOINT")
        _fsync_file(self.duckdb_path)
        return {"changed": True, "restoredDatasets": restored, "removedDatasets": removed}

    def _restore_sqlite(self, snapshot_path: Path, workspace_id: str) -> dict[str, Any]:
        _validate_sqlite_snapshot(snapshot_path, workspace_id)
        with closing(self.open_db()) as connection:
            connection.row_factory = sqlite3.Row
            _assert_workspace_exists(connection, workspace_id)
            current_physical = _workspace_physical_tables(connection, workspace_id)
            registered_physical = set(_all_physical_table_bindings(connection))
            connection.execute("PRAGMA foreign_keys = OFF")
            connection.execute("ATTACH DATABASE ? AS recovery_snapshot", (str(snapshot_path.resolve()),))
            try:
                snapshot_physical = [
                    str(row[0])
                    for row in connection.execute(
                        "SELECT physical_table FROM recovery_snapshot.table_registry WHERE workspace_id = ? ORDER BY table_key",
                        (workspace_id,),
                    ).fetchall()
                ] if _table_exists(connection, "table_registry", "recovery_snapshot") else []
                snapshot_dataset_version_ids = [
                    str(row[0])
                    for row in connection.execute(
                        "SELECT version_id FROM recovery_snapshot.dataset_versions "
                        "WHERE workspace_id = ? ORDER BY version_id",
                        (workspace_id,),
                    ).fetchall()
                ]
                snapshot_workspace = connection.execute(
                    "SELECT current_source_run_id FROM recovery_snapshot.workspaces WHERE id = ?",
                    (workspace_id,),
                ).fetchone()
                snapshot_source_run_id = str(snapshot_workspace[0] or "") if snapshot_workspace is not None else ""
                physical_union = registered_physical | set(snapshot_physical)
                connection.execute("BEGIN IMMEDIATE")
                target_tables = _table_names(connection)
                for table_name in target_tables:
                    if table_name in physical_union or table_name in {"dataset_versions", "dataset_version_files", "source_runs"}:
                        continue
                    columns = _table_columns(connection, table_name)
                    if "workspace_id" in columns and table_name in RESTORABLE_WORKSPACE_TABLES:
                        connection.execute(
                            f"DELETE FROM main.{_quote_identifier(table_name)} WHERE workspace_id = ?",
                            (workspace_id,),
                        )
                connection.execute(
                    "DELETE FROM main.dataset_version_files WHERE version_id IN ("
                    "SELECT version_id FROM main.dataset_versions WHERE workspace_id = ?"
                    ")",
                    (workspace_id,),
                )
                connection.execute("DELETE FROM main.dataset_versions WHERE workspace_id = ?", (workspace_id,))
                connection.execute("DELETE FROM main.workspaces WHERE id = ?", (workspace_id,))
                workspace_columns = _table_columns(connection, "workspaces")
                snapshot_workspace_columns = _table_columns(connection, "workspaces", "recovery_snapshot")
                shared_workspace_columns = [column for column in snapshot_workspace_columns if column in workspace_columns]
                workspace_columns_sql = ", ".join(_quote_identifier(column) for column in shared_workspace_columns)
                connection.execute(
                    f"INSERT INTO main.workspaces ({workspace_columns_sql}) "
                    f"SELECT {workspace_columns_sql} FROM recovery_snapshot.workspaces WHERE id = ?",
                    (workspace_id,),
                )
                restored_metadata_rows = 0
                for table_name in ("dataset_versions", "dataset_version_files"):
                    destination_columns = _table_columns(connection, table_name)
                    snapshot_columns = _table_columns(connection, table_name, "recovery_snapshot")
                    if destination_columns != snapshot_columns:
                        raise WorkspaceRecoveryError(
                            "RECOVERY_SQLITE_SNAPSHOT_INVALID",
                            "Dataset version catalogue schema does not match the active control database.",
                        )
                    columns_sql = ", ".join(_quote_identifier(column) for column in destination_columns)
                    if table_name == "dataset_versions":
                        where_sql = "workspace_id = ?"
                    else:
                        where_sql = (
                            "version_id IN (SELECT version_id FROM recovery_snapshot.dataset_versions "
                            "WHERE workspace_id = ?)"
                        )
                    cursor = connection.execute(
                        f"INSERT INTO main.{_quote_identifier(table_name)} ({columns_sql}) "
                        f"SELECT {columns_sql} FROM recovery_snapshot.{_quote_identifier(table_name)} WHERE {where_sql}",
                        (workspace_id,),
                    )
                    restored_metadata_rows += max(0, int(cursor.rowcount or 0))
                if snapshot_source_run_id:
                    destination_columns = _table_columns(connection, "source_runs")
                    snapshot_columns = _table_columns(connection, "source_runs", "recovery_snapshot")
                    if destination_columns != snapshot_columns:
                        raise WorkspaceRecoveryError(
                            "RECOVERY_SQLITE_SNAPSHOT_INVALID",
                            "Source lineage schema does not match the active control database.",
                        )
                    columns_sql = ", ".join(_quote_identifier(column) for column in destination_columns)
                    cursor = connection.execute(
                        f"INSERT OR IGNORE INTO main.source_runs ({columns_sql}) "
                        f"SELECT {columns_sql} FROM recovery_snapshot.source_runs "
                        "WHERE workspace_id = ? AND id = ?",
                        (workspace_id, snapshot_source_run_id),
                    )
                    restored_metadata_rows += max(0, int(cursor.rowcount or 0))
                for table_name in target_tables:
                    if (
                        table_name in physical_union
                        or table_name in {"dataset_versions", "dataset_version_files", "source_runs"}
                        or not _table_exists(connection, table_name, "recovery_snapshot")
                    ):
                        continue
                    destination_columns = _table_columns(connection, table_name)
                    if "workspace_id" not in destination_columns or table_name not in RESTORABLE_WORKSPACE_TABLES:
                        continue
                    snapshot_columns = _table_columns(connection, table_name, "recovery_snapshot")
                    shared_columns = [column for column in snapshot_columns if column in destination_columns]
                    if "workspace_id" not in shared_columns:
                        continue
                    columns_sql = ", ".join(_quote_identifier(column) for column in shared_columns)
                    cursor = connection.execute(
                        f"INSERT INTO main.{_quote_identifier(table_name)} ({columns_sql}) "
                        f"SELECT {columns_sql} FROM recovery_snapshot.{_quote_identifier(table_name)} WHERE workspace_id = ?",
                        (workspace_id,),
                    )
                    restored_metadata_rows += max(0, int(cursor.rowcount or 0))
                incomplete_binding = connection.execute(
                    """
                    SELECT 1
                    FROM main.table_registry AS registry
                    LEFT JOIN main.dataset_versions AS version
                      ON version.version_id = registry.active_version_id
                     AND version.workspace_id = registry.workspace_id
                     AND version.table_key = registry.table_key
                    LEFT JOIN main.dataset_version_files AS file ON file.version_id = version.version_id
                    WHERE registry.workspace_id = ?
                      AND registry.active_version_id <> ''
                    GROUP BY registry.workspace_id, registry.table_key, registry.active_version_id
                    HAVING version.version_id IS NULL OR COUNT(file.version_id) <> 1
                    LIMIT 1
                    """,
                    (workspace_id,),
                ).fetchone()
                restored_source_run = (
                    connection.execute(
                        "SELECT 1 FROM main.source_runs WHERE workspace_id = ? AND id = ?",
                        (workspace_id, snapshot_source_run_id),
                    ).fetchone()
                    if snapshot_source_run_id
                    else True
                )
                if incomplete_binding is not None or restored_source_run is None:
                    raise WorkspaceRecoveryError(
                        "RECOVERY_SQLITE_SNAPSHOT_INVALID",
                        "Recovery would leave a dataset version or current source lineage pointer incomplete.",
                    )
                if any(_table_exists(connection, physical_table, "recovery_snapshot") for physical_table in snapshot_physical):
                    raise WorkspaceRecoveryError(
                        "RECOVERY_SQLITE_SNAPSHOT_INVALID",
                        "Dataset v2 recovery snapshots must not contain business-row tables.",
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                try:
                    connection.execute("DETACH DATABASE recovery_snapshot")
                except sqlite3.Error:
                    pass
        return {
            "changed": True,
            "restoredMetadataRows": restored_metadata_rows,
            "restoredDatasetPointers": len(snapshot_physical),
            "restoredDatasetVersions": len(snapshot_dataset_version_ids),
            "restoredCurrentSourceRun": bool(snapshot_source_run_id),
        }

    def _apply_point(self, workspace_id: str, manifest: dict[str, Any], *, fail_at: str = "") -> dict[str, Any]:
        directory = self._point_directory(workspace_id, str(manifest["recoveryPointKey"]), must_exist=True)
        sqlite_artifact = _safe_child(directory, SQLITE_ARTIFACT, must_exist=True)
        duckdb_entry = next(
            (entry for entry in manifest.get("files", []) if isinstance(entry, dict) and entry.get("file") == DUCKDB_ARTIFACT),
            None,
        )
        duckdb_artifact = _safe_child(directory, DUCKDB_ARTIFACT, must_exist=True) if duckdb_entry else None
        with closing(self.open_db()) as connection:
            connection.row_factory = sqlite3.Row
            current_physical = _workspace_physical_tables(connection, workspace_id)
        duckdb_result = self._restore_duckdb(duckdb_artifact, current_physical)
        if fail_at == "after_duckdb_restore":
            raise RuntimeError("Injected recovery interruption after DuckDB restore")
        sqlite_result = self._restore_sqlite(sqlite_artifact, workspace_id)
        if fail_at == "after_sqlite_restore":
            raise RuntimeError("Injected recovery interruption after SQLite restore")
        restored_state = self._state(workspace_id)
        if restored_state["fingerprint"] != manifest.get("workspaceStateFingerprint"):
            raise WorkspaceRecoveryError(
                "RECOVERY_RESTORED_STATE_MISMATCH",
                "Restored workspace did not match the verified recovery state.",
            )
        return {"sqlite": sqlite_result, "duckdb": duckdb_result, "restoredStateFingerprint": restored_state["fingerprint"]}

    def preview_restore(self, workspace_id: str, recovery_point_key: str, request_key: str) -> dict[str, Any]:
        workspace_id = _workspace_id(workspace_id)
        recovery_point_key = _recovery_key(recovery_point_key)
        request_key = _request_key(request_key)
        prior = self._operation_receipt(workspace_id, "restore", request_key)
        if prior is not None:
            prior_result = prior.get("result") if isinstance(prior.get("result"), dict) else {}
            prior_plan = prior_result.get("recoveryPlan") if isinstance(prior_result.get("recoveryPlan"), dict) else {}
            if prior_plan.get("recoveryPointKey") != recovery_point_key:
                raise WorkspaceRecoveryError(
                    "RECOVERY_REQUEST_KEY_CONFLICT",
                    "requestKey was already used to restore a different recovery point.",
                )
            if prior.get("status") == "completed":
                return {**prior_result, "changed": False, "idempotentReplay": True}
        manifest = self._load_manifest(workspace_id, recovery_point_key, verify=True)
        plan = self._plan("restore", workspace_id, request_key, manifest=manifest)
        return {
            "ok": True,
            "dryRun": True,
            "requiresConfirmation": True,
            "workspaceId": workspace_id,
            "recoveryPlan": plan,
            "recoveryPoint": _public_manifest(manifest),
        }

    def restore(
        self,
        workspace_id: str,
        recovery_point_key: str,
        request_key: str,
        *,
        confirm: bool = False,
        expected_plan_fingerprint: str = "",
        fail_at: str = "",
    ) -> dict[str, Any]:
        workspace_id = _workspace_id(workspace_id)
        recovery_point_key = _recovery_key(recovery_point_key)
        request_key = _request_key(request_key)
        prior = self._operation_receipt(workspace_id, "restore", request_key)
        if prior is not None:
            prior_result = prior.get("result") if isinstance(prior.get("result"), dict) else {}
            prior_plan = prior_result.get("recoveryPlan") if isinstance(prior_result.get("recoveryPlan"), dict) else {}
            if prior_plan.get("recoveryPointKey") != recovery_point_key:
                raise WorkspaceRecoveryError(
                    "RECOVERY_REQUEST_KEY_CONFLICT",
                    "requestKey was already used to restore a different recovery point.",
                )
            if prior.get("status") == "completed":
                return {**prior_result, "changed": False, "idempotentReplay": True}
        manifest = self._load_manifest(workspace_id, recovery_point_key, verify=True)
        plan = self._plan("restore", workspace_id, request_key, manifest=manifest)
        if not confirm:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "workspaceId": workspace_id,
                "recoveryPlan": plan,
                "recoveryPoint": _public_manifest(manifest),
            }
        replay = self._operation_replay(workspace_id, "restore", request_key, str(plan["intentFingerprint"]))
        if replay is not None:
            return replay
        self._require_plan(expected_plan_fingerprint, plan)
        self._assert_no_active_import(workspace_id)
        safety_material = f"{request_key}\0{plan['inputFingerprint']}"
        safety_request_key = f"safety:{hashlib.sha256(safety_material.encode('utf-8')).hexdigest()}"
        safety_reason = f"Automatic safety point before restoring {recovery_point_key}"
        safety_preview = self.preview_create(workspace_id, safety_reason, safety_request_key)
        safety_plan = safety_preview["recoveryPlan"]
        safety_result = self._create_confirmed(
            workspace_id,
            safety_reason,
            safety_request_key,
            str(safety_plan["planFingerprint"]),
        )
        safety_point = safety_result["recoveryPoint"]
        safety_key = str(safety_point["recoveryPointKey"])
        safety_manifest = self._load_manifest(workspace_id, safety_key, verify=True)
        journal_path = self._operation_file(workspace_id, "journal", request_key, create=True)
        operation_receipt_path = self._operation_file(workspace_id, "restore", request_key, create=True)
        journal = {
            "schema": RECOVERY_JOURNAL_SCHEMA,
            "workspaceId": workspace_id,
            "operation": "restore",
            "targetRecoveryPointKey": recovery_point_key,
            "safetyRecoveryPointKey": safety_key,
            "requestKeyFingerprint": str(plan["requestKeyFingerprint"]),
            "intentFingerprint": str(plan["intentFingerprint"]),
            "operationReceiptName": operation_receipt_path.name,
            "status": "prepared",
            "createdAt": _utc_now(),
            "updatedAt": _utc_now(),
        }
        _write_recovery_journal(journal_path, journal)
        try:
            journal["status"] = "applying"
            journal["updatedAt"] = _utc_now()
            _write_recovery_journal(journal_path, journal)
            restored = self._apply_point(workspace_id, manifest, fail_at=fail_at)
        except Exception as error:
            try:
                rollback = self._apply_point(workspace_id, safety_manifest)
                journal["status"] = "rolled_back"
                journal["rollback"] = rollback
                journal["errorCode"] = getattr(error, "code", "RECOVERY_RESTORE_INTERRUPTED")
                journal["updatedAt"] = _utc_now()
                _write_recovery_journal(journal_path, journal)
            except Exception as rollback_error:
                journal["status"] = "needs_attention"
                journal["errorCode"] = getattr(error, "code", "RECOVERY_RESTORE_INTERRUPTED")
                journal["rollbackErrorCode"] = getattr(rollback_error, "code", "RECOVERY_ROLLBACK_FAILED")
                journal["updatedAt"] = _utc_now()
                _write_recovery_journal(journal_path, journal)
                raise WorkspaceRecoveryError(
                    "RECOVERY_RESTORE_NEEDS_ATTENTION",
                    "Restore and automatic rollback did not complete.",
                    f"Keep safety point {safety_key} and retry its verified restore before other writes.",
                ) from error
            raise WorkspaceRecoveryError(
                "RECOVERY_RESTORE_ROLLED_BACK",
                "Restore did not complete; the pre-restore safety point was applied successfully.",
                f"Workspace is back at safety point {safety_key}. Preview the requested restore again.",
            ) from error
        result = {
            "ok": True,
            "confirmed": True,
            "changed": True,
            "workspaceId": workspace_id,
            "recoveryPlan": plan,
            "recoveryPoint": _public_manifest(manifest),
            "safetyRecoveryPoint": safety_point,
            "restored": restored,
            "invalidationKeys": list(plan["invalidationKeys"]),
        }
        # Persist a proof-complete applied journal before the separate receipt.
        # A hard crash in either following window can now be repaired exactly.
        journal["status"] = "applied"
        journal["result"] = result
        journal["updatedAt"] = _utc_now()
        _write_recovery_journal(journal_path, journal)
        if fail_at == "after_applied_journal":
            raise RuntimeError("Injected recovery interruption after applied journal")
        self._write_operation(workspace_id, "restore", request_key, str(plan["intentFingerprint"]), "completed", result)
        journal["status"] = "completed"
        journal["updatedAt"] = _utc_now()
        _write_recovery_journal(journal_path, journal)
        return result

    def preview_delete(self, workspace_id: str, recovery_point_key: str, request_key: str) -> dict[str, Any]:
        workspace_id = _workspace_id(workspace_id)
        recovery_point_key = _recovery_key(recovery_point_key)
        request_key = _request_key(request_key)
        manifest = self._load_manifest(workspace_id, recovery_point_key, verify=True)
        plan = self._plan("delete", workspace_id, request_key, manifest=manifest)
        return {
            "ok": True,
            "dryRun": True,
            "requiresConfirmation": True,
            "workspaceId": workspace_id,
            "recoveryPlan": plan,
            "recoveryPoint": _public_manifest(manifest),
        }

    def delete(
        self,
        workspace_id: str,
        recovery_point_key: str,
        request_key: str,
        *,
        confirm: bool = False,
        expected_plan_fingerprint: str = "",
        fail_at: str = "",
    ) -> dict[str, Any]:
        workspace_id = _workspace_id(workspace_id)
        recovery_point_key = _recovery_key(recovery_point_key)
        request_key = _request_key(request_key)
        prior = self._operation_receipt(workspace_id, "delete", request_key)
        if prior is not None:
            prior_result = prior.get("result") if isinstance(prior.get("result"), dict) else {}
            prior_plan = prior_result.get("recoveryPlan") if isinstance(prior_result.get("recoveryPlan"), dict) else {}
            if prior_plan.get("recoveryPointKey") != recovery_point_key:
                raise WorkspaceRecoveryError(
                    "RECOVERY_REQUEST_KEY_CONFLICT",
                    "requestKey was already used to delete a different recovery point.",
                )
            if prior.get("status") == "completed":
                return {**prior_result, "changed": False, "idempotentReplay": True}
            if prior.get("status") == "prepared":
                completed = self._finish_prepared_delete(
                    workspace_id,
                    recovery_point_key,
                    request_key=request_key,
                    request_key_fingerprint=str(prior.get("requestKeyFingerprint") or hashlib.sha256(request_key.encode("utf-8")).hexdigest()),
                    intent_fingerprint=str(prior.get("intentFingerprint") or ""),
                    result=prior_result,
                )
                return {**completed, "changed": False, "idempotentReplay": True}
        manifest = self._load_manifest(workspace_id, recovery_point_key, verify=True)
        plan = self._plan("delete", workspace_id, request_key, manifest=manifest)
        if not confirm:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "workspaceId": workspace_id,
                "recoveryPlan": plan,
                "recoveryPoint": _public_manifest(manifest),
            }
        replay = self._operation_replay(workspace_id, "delete", request_key, str(plan["intentFingerprint"]))
        if replay is not None:
            return replay
        self._require_plan(expected_plan_fingerprint, plan)
        self._assert_no_active_import(workspace_id)
        self._point_directory(workspace_id, recovery_point_key, must_exist=True)
        point_catalog = self._point_directory(workspace_id, recovery_point_key, must_exist=True) / DUCKDB_ARTIFACT
        result = {
            "ok": True,
            "confirmed": True,
            "changed": True,
            "workspaceId": workspace_id,
            "recoveryPlan": plan,
            "deletedRecoveryPointKey": recovery_point_key,
            "invalidationKeys": ["workspace-recovery"],
            "_datasetObjectGcCandidates": duckdb_manifest_object_references([point_catalog]),
        }
        self._write_operation(workspace_id, "delete", request_key, str(plan["intentFingerprint"]), "prepared", result)
        return self._finish_prepared_delete(
            workspace_id,
            recovery_point_key,
            request_key=request_key,
            request_key_fingerprint=hashlib.sha256(request_key.encode("utf-8")).hexdigest(),
            intent_fingerprint=str(plan["intentFingerprint"]),
            result=result,
            fail_at=fail_at,
        )


def configured_recovery_root(project_root: Path) -> Path:
    configured = str(os.environ.get("AIBI_WORKSPACE_RECOVERY_ROOT") or "").strip()
    if configured:
        value = Path(configured)
        return _absolute(value if value.is_absolute() else project_root / value)
    return _absolute(project_root / "data" / "local" / "workspace-recovery")


def _command_workspace(
    connection: sqlite3.Connection,
    args: argparse.Namespace,
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> str:
    active = _workspace_id(active_workspace_id(connection))
    requested = str(getattr(args, "workspace", "") or "").strip()
    if requested and requested != active:
        raise WorkspaceRecoveryError(
            "RECOVERY_WORKSPACE_MISMATCH",
            "Workspace Recovery v1 only operates on the active workspace.",
        )
    return active


def _command_service(
    *,
    open_db: Callable[[], sqlite3.Connection],
    sqlite_path: Path,
    duckdb_path: Path,
    recovery_root: Path,
) -> WorkspaceRecoveryService:
    return WorkspaceRecoveryService(
        open_db=open_db,
        sqlite_path=sqlite_path,
        duckdb_path=duckdb_path,
        recovery_root=recovery_root,
    )


def _resolve_command_workspace(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> str:
    with closing(open_db()) as connection:
        connection.row_factory = sqlite3.Row
        return _command_workspace(connection, args, active_workspace_id)


def _run_recovery_command(action: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return action()
    except WorkspaceRecoveryError as error:
        return {
            "ok": False,
            "code": error.code,
            "error": str(error),
            "recoveryAction": error.recovery_action or None,
            "dryRun": False,
            "requiresConfirmation": False,
        }


def workspace_recovery_list_command(args: argparse.Namespace, **dependencies: Any) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        workspace_id = _resolve_command_workspace(args, open_db=dependencies["open_db"], active_workspace_id=dependencies["active_workspace_id"])
        service = _command_service(**{key: dependencies[key] for key in ("open_db", "sqlite_path", "duckdb_path", "recovery_root")})
        return service.list(workspace_id, limit=int(getattr(args, "limit", 5) or 5), verify=bool(getattr(args, "verify", False)))
    return _run_recovery_command(run)


def workspace_recovery_reconcile_command(args: argparse.Namespace, **dependencies: Any) -> dict[str, Any]:
    del args
    def run() -> dict[str, Any]:
        service = _command_service(**{key: dependencies[key] for key in ("open_db", "sqlite_path", "duckdb_path", "recovery_root")})
        return service.reconcile_unfinished_restores()
    return _run_recovery_command(run)


def workspace_recovery_inspect_command(args: argparse.Namespace, **dependencies: Any) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        workspace_id = _resolve_command_workspace(args, open_db=dependencies["open_db"], active_workspace_id=dependencies["active_workspace_id"])
        service = _command_service(**{key: dependencies[key] for key in ("open_db", "sqlite_path", "duckdb_path", "recovery_root")})
        return service.inspect(workspace_id, str(args.recovery_point), verify=True)
    return _run_recovery_command(run)


def workspace_recovery_compare_command(args: argparse.Namespace, **dependencies: Any) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        workspace_id = _resolve_command_workspace(args, open_db=dependencies["open_db"], active_workspace_id=dependencies["active_workspace_id"])
        service = _command_service(**{key: dependencies[key] for key in ("open_db", "sqlite_path", "duckdb_path", "recovery_root")})
        return service.compare(workspace_id, str(args.recovery_point))
    return _run_recovery_command(run)


def workspace_recovery_create_command(args: argparse.Namespace, **dependencies: Any) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        workspace_id = _resolve_command_workspace(args, open_db=dependencies["open_db"], active_workspace_id=dependencies["active_workspace_id"])
        service = _command_service(**{key: dependencies[key] for key in ("open_db", "sqlite_path", "duckdb_path", "recovery_root")})
        return service.create(
            workspace_id,
            str(args.reason),
            str(args.request_key),
            confirm=bool(getattr(args, "yes", False)),
            expected_plan_fingerprint=str(getattr(args, "expected_plan", "") or ""),
        )
    return _run_recovery_command(run)


def workspace_recovery_restore_command(args: argparse.Namespace, **dependencies: Any) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        workspace_id = _resolve_command_workspace(args, open_db=dependencies["open_db"], active_workspace_id=dependencies["active_workspace_id"])
        service = _command_service(**{key: dependencies[key] for key in ("open_db", "sqlite_path", "duckdb_path", "recovery_root")})
        return service.restore(
            workspace_id,
            str(args.recovery_point),
            str(args.request_key),
            confirm=bool(getattr(args, "yes", False)),
            expected_plan_fingerprint=str(getattr(args, "expected_plan", "") or ""),
        )
    return _run_recovery_command(run)


def workspace_recovery_delete_command(args: argparse.Namespace, **dependencies: Any) -> dict[str, Any]:
    def run() -> dict[str, Any]:
        workspace_id = _resolve_command_workspace(args, open_db=dependencies["open_db"], active_workspace_id=dependencies["active_workspace_id"])
        service = _command_service(**{key: dependencies[key] for key in ("open_db", "sqlite_path", "duckdb_path", "recovery_root")})
        return service.delete(
            workspace_id,
            str(args.recovery_point),
            str(args.request_key),
            confirm=bool(getattr(args, "yes", False)),
            expected_plan_fingerprint=str(getattr(args, "expected_plan", "") or ""),
        )
    return _run_recovery_command(run)
