from __future__ import annotations

"""Immutable, content-addressed dataset versions for the AIBI-C data plane.

SQLite owns only the version catalogue and the active-version pointer.  Business
rows live in typed Parquet objects and are consumed by DuckDB.  Paths returned
by public functions are always workspace-scoped relative object keys; absolute
paths are resolved only inside this module.
"""

import hashlib
import errno
import gc
import json
import os
import re
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from uuid import uuid4

from bi_cli_core import DB_PATH, now_iso
from workspace_mutation_lock_service import workspace_mutation_lock


DATASET_VERSION_SCHEMA = "aibi-dataset-version/v2"
DATASET_OBJECT_SCHEMA = "aibi-dataset-object/v1"
INTERNAL_ROW_ID = "__aibi_row_id"
INTERNAL_SCHEMA_FIELDS = ({"name": INTERNAL_ROW_ID, "type": "BIGINT"},)
DATASET_VERSION_ID_RE = re.compile(r"version_[a-f0-9]{24}")
OBJECT_HASH_RE = re.compile(r"[a-f0-9]{64}")
_GC_UNLINK_RETRY_DELAYS = (0.0, 0.025, 0.05, 0.1, 0.2, 0.4, 0.8, 1.0)


def canonical_fingerprint(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _sql_literal(value: str | Path) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _validate_parquet_contract(
    parquet_path: Path,
    *,
    schema_fields: Sequence[Mapping[str, str]],
    row_count: int,
) -> None:
    """Bind a prepared manifest to the actual typed Parquet object before CAS publication."""

    resolved = parquet_path.resolve()
    if not resolved.is_file() or resolved.is_symlink():
        raise ValueError("Prepared dataset object is unavailable or unsafe.")
    try:
        import duckdb  # type: ignore
    except ImportError as error:  # pragma: no cover - deployment contract
        raise RuntimeError("DuckDB is required to seal dataset versions.") from error
    connection = duckdb.connect(":memory:")
    relation = f"read_parquet({_sql_literal(resolved)})"
    try:
        description = connection.execute(f"DESCRIBE SELECT * FROM {relation}").fetchall()
        actual_fields = [{"name": str(item[0]), "type": str(item[1]).upper()} for item in description]
        public_fields = [item for item in actual_fields if not item["name"].startswith("__aibi_")]
        internal_fields = [item for item in actual_fields if item["name"].startswith("__aibi_")]
        if public_fields != list(schema_fields):
            raise ValueError("Dataset manifest schema does not match the prepared Parquet object.")
        if internal_fields != list(INTERNAL_SCHEMA_FIELDS):
            raise ValueError("Prepared Parquet does not satisfy the internal row-id contract.")
        actual_count, distinct_row_ids, minimum_row_id, maximum_row_id = connection.execute(
            f"SELECT count(*), count(DISTINCT \"{INTERNAL_ROW_ID}\"), "
            f"min(\"{INTERNAL_ROW_ID}\"), max(\"{INTERNAL_ROW_ID}\") FROM {relation}"
        ).fetchone()
        if int(actual_count) != row_count:
            raise ValueError("Dataset manifest row count does not match the prepared Parquet object.")
        expected_minimum = 1 if row_count else None
        expected_maximum = row_count if row_count else None
        if (
            int(distinct_row_ids) != row_count
            or minimum_row_id != expected_minimum
            or maximum_row_id != expected_maximum
        ):
            raise ValueError("Prepared Parquet row ids are not the expected stable 1-based sequence.")
    finally:
        connection.close()


def configured_dataset_object_root(database_path: Path = DB_PATH) -> Path:
    configured = str(os.environ.get("AIBI_DATASET_OBJECT_ROOT") or "").strip()
    return Path(configured).expanduser().resolve() if configured else (database_path.parent / "dataset-objects-v2").resolve()


def workspace_bucket(workspace_id: str) -> str:
    normalized = str(workspace_id or "").strip()
    if not normalized or len(normalized) > 160:
        raise ValueError("Dataset version requires a bounded workspace id.")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


def _normalized_schema_fields(schema_fields: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    fields: list[dict[str, str]] = []
    names: set[str] = set()
    for raw in schema_fields:
        name = str(raw.get("name") or raw.get("field") or "").strip()
        data_type = str(raw.get("type") or raw.get("duckdbType") or raw.get("inferredType") or "VARCHAR").strip().upper()
        if not name or name.startswith("__aibi_") or name in names:
            if name in names:
                raise ValueError(f"Dataset schema contains a duplicate field: {name}")
            continue
        names.add(name)
        fields.append({"name": name, "type": data_type or "VARCHAR"})
    if not fields:
        raise ValueError("Dataset version requires at least one public field.")
    return fields


def schema_columns(schema_json: str | Sequence[Mapping[str, Any]] | Mapping[str, Any] | None) -> list[str]:
    """Return public columns from registry/version schema metadata."""

    if schema_json is None:
        return []
    payload: Any = schema_json
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as error:
            raise ValueError("Dataset registry schema_json is invalid.") from error
    if isinstance(payload, Mapping):
        payload = payload.get("fields") or payload.get("schemaFields") or []
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError("Dataset registry schema_json must contain a field list.")
    if not payload:
        return []
    return [field["name"] for field in _normalized_schema_fields(payload)]


def schema_field_types(schema_json: str | Sequence[Mapping[str, Any]] | Mapping[str, Any] | None) -> dict[str, str]:
    """Return the sealed DuckDB type for each public field."""

    if schema_json is None:
        return {}
    payload: Any = schema_json
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as error:
            raise ValueError("Dataset registry schema_json is invalid.") from error
    if isinstance(payload, Mapping):
        payload = payload.get("fields") or payload.get("schemaFields") or []
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes, bytearray)):
        raise ValueError("Dataset registry schema_json must contain a field list.")
    if not payload:
        return {}
    return {field["name"]: field["type"] for field in _normalized_schema_fields(payload)}


def registry_columns(connection: sqlite3.Connection, physical_table: str) -> list[str]:
    """Resolve logical table columns without creating a SQLite schema proxy."""

    columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(table_registry)").fetchall()}
    if "schema_json" not in columns:
        raise RuntimeError("Dataset v2 table_registry schema metadata is not installed.")
    row = connection.execute(
        "SELECT schema_json FROM table_registry WHERE physical_table = ?",
        (str(physical_table),),
    ).fetchone()
    if row is None:
        return []
    value = row["schema_json"] if isinstance(row, sqlite3.Row) else row[0]
    return schema_columns(value)


_DATASET_VERSION_REQUIRED_COLUMNS = {
    "dataset_versions": frozenset(
        {
            "version_id",
            "workspace_id",
            "table_key",
            "row_count",
            "column_count",
            "schema_json",
            "schema_fingerprint",
            "content_fingerprint",
            "source_file",
            "created_at",
        }
    ),
    "dataset_version_files": frozenset(
        {"version_id", "ordinal", "object_key", "object_hash", "row_count", "byte_size"}
    ),
}


def assert_dataset_version_schema(connection: sqlite3.Connection) -> None:
    """Fail closed when the clean-v18 dataset catalogue contract is incomplete."""

    table_names = tuple(_DATASET_VERSION_REQUIRED_COLUMNS)
    placeholders = ", ".join("?" for _ in table_names)
    actual_by_table = {table_name: set() for table_name in table_names}
    for row in connection.execute(
        f"""
        SELECT schema_table.name, table_column.name
        FROM sqlite_master AS schema_table
        JOIN pragma_table_info(schema_table.name) AS table_column
        WHERE schema_table.type = 'table'
          AND schema_table.name IN ({placeholders})
        """,
        table_names,
    ):
        actual_by_table[str(row[0])].add(str(row[1]))
    for table_name, required_columns in _DATASET_VERSION_REQUIRED_COLUMNS.items():
        missing_columns = sorted(required_columns - actual_by_table[table_name])
        if missing_columns:
            raise RuntimeError(
                f"AIBI-C clean v18 dataset catalogue is incomplete; {table_name} "
                "is missing columns: "
                + ", ".join(missing_columns)
            )


def object_key_for(workspace_id: str, object_hash: str) -> str:
    if not OBJECT_HASH_RE.fullmatch(str(object_hash or "")):
        raise ValueError("Dataset object hash is invalid.")
    return f"workspaces/{workspace_bucket(workspace_id)}/objects/{object_hash[:2]}/{object_hash}.parquet"


def resolve_object_key(object_key: str, *, root: Path | None = None) -> Path:
    object_root = (root or configured_dataset_object_root()).resolve()
    normalized = str(object_key or "").replace("\\", "/").strip("/")
    parts = Path(normalized).parts
    if not normalized or Path(normalized).is_absolute() or any(part in {"", ".", ".."} for part in parts):
        raise PermissionError("Dataset object key must be a safe relative path.")
    resolved = (object_root / Path(*parts)).resolve()
    if resolved != object_root and object_root not in resolved.parents:
        raise PermissionError("Dataset object escaped the configured root.")
    return resolved


def _fsync_file(path: Path) -> None:
    with path.open("r+b") as stream:
        os.fsync(stream.fileno())


def _fsync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _publish_object(source: Path, *, workspace_id: str, root: Path | None = None) -> dict[str, Any]:
    resolved_source = source.resolve()
    if not resolved_source.is_file() or resolved_source.is_symlink():
        raise ValueError("Prepared dataset object is unavailable or unsafe.")
    object_hash = file_sha256(resolved_source)
    object_key = object_key_for(workspace_id, object_hash)
    destination = resolve_object_key(object_key, root=root)
    object_root = (root or configured_dataset_object_root()).resolve()
    lock_path = object_root / ".aibi-dataset-object.lock"
    with workspace_mutation_lock(lock_path, timeout_seconds=60.0):
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.parent.is_symlink():
            raise PermissionError("Dataset object directory cannot be a symbolic link.")
        if destination.exists():
            if destination.is_symlink() or file_sha256(destination) != object_hash:
                raise RuntimeError("Content-addressed dataset object failed integrity verification.")
        else:
            temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
            try:
                shutil.copyfile(resolved_source, temporary)
                _fsync_file(temporary)
                if file_sha256(temporary) != object_hash:
                    raise RuntimeError("Dataset object changed while it was being published.")
                os.replace(temporary, destination)
                _fsync_directory(destination.parent)
            finally:
                temporary.unlink(missing_ok=True)
    return {
        "schema": DATASET_OBJECT_SCHEMA,
        "ordinal": 0,
        "objectKey": object_key,
        "objectHash": object_hash,
        "byteSize": int(destination.stat().st_size),
    }


def prepare_dataset_version(
    *,
    workspace_id: str,
    table_key: str,
    parquet_path: str | Path,
    schema_fields: Sequence[Mapping[str, Any]],
    row_count: int,
    source_file: str,
    object_root: Path | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Publish immutable bytes and return a safe, not-yet-active version manifest."""

    normalized_workspace = str(workspace_id or "").strip()
    normalized_table = str(table_key or "").strip()
    if not normalized_table or len(normalized_table) > 128:
        raise ValueError("Dataset version requires a bounded table key.")
    workspace_bucket(normalized_workspace)
    normalized_schema = _normalized_schema_fields(schema_fields)
    normalized_rows = int(row_count)
    if normalized_rows < 0:
        raise ValueError("Dataset version row count cannot be negative.")
    resolved_parquet = Path(parquet_path)
    _validate_parquet_contract(
        resolved_parquet,
        schema_fields=normalized_schema,
        row_count=normalized_rows,
    )
    published = _publish_object(resolved_parquet, workspace_id=normalized_workspace, root=object_root)
    published["rowCount"] = normalized_rows
    schema_fingerprint = canonical_fingerprint({"fields": normalized_schema})
    content_material = {
        "schema": DATASET_VERSION_SCHEMA,
        "workspaceId": normalized_workspace,
        "tableKey": normalized_table,
        "rowCount": normalized_rows,
        "schemaFingerprint": schema_fingerprint,
        "internalColumns": list(INTERNAL_SCHEMA_FIELDS),
        "files": [
            {
                "ordinal": 0,
                "objectKey": published["objectKey"],
                "objectHash": published["objectHash"],
                "rowCount": normalized_rows,
                "byteSize": published["byteSize"],
            }
        ],
    }
    content_fingerprint = canonical_fingerprint(content_material)
    version_id = "version_" + canonical_fingerprint({
        "workspaceId": normalized_workspace,
        "tableKey": normalized_table,
        "contentFingerprint": content_fingerprint,
    })[:24]
    return {
        "schema": DATASET_VERSION_SCHEMA,
        "status": "prepared",
        "versionId": version_id,
        "workspaceId": normalized_workspace,
        "tableKey": normalized_table,
        "rowCount": normalized_rows,
        "columnCount": len(normalized_schema),
        "schemaFields": normalized_schema,
        "internalColumns": list(INTERNAL_SCHEMA_FIELDS),
        "schemaFingerprint": schema_fingerprint,
        "contentFingerprint": content_fingerprint,
        "sourceFile": str(source_file or ""),
        "createdAt": created_at or now_iso(),
        "files": content_material["files"],
    }


def _version_material(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "schema": manifest.get("schema"),
        "workspaceId": manifest.get("workspaceId"),
        "tableKey": manifest.get("tableKey"),
        "rowCount": int(manifest.get("rowCount") or 0),
        "schemaFingerprint": manifest.get("schemaFingerprint"),
        "internalColumns": list(manifest.get("internalColumns") or []),
        "files": [
            {
                "ordinal": int(item.get("ordinal") or 0),
                "objectKey": item.get("objectKey"),
                "objectHash": item.get("objectHash"),
                "rowCount": int(item.get("rowCount") or 0),
                "byteSize": int(item.get("byteSize") or 0),
            }
            for item in manifest.get("files") or []
            if isinstance(item, Mapping)
        ],
    }


def validate_dataset_version_manifest(manifest: Mapping[str, Any]) -> None:
    if manifest.get("schema") != DATASET_VERSION_SCHEMA:
        raise ValueError("Dataset version schema is unsupported.")
    version_id = str(manifest.get("versionId") or "")
    if not DATASET_VERSION_ID_RE.fullmatch(version_id):
        raise ValueError("Dataset version id is invalid.")
    schema_fields = _normalized_schema_fields(list(manifest.get("schemaFields") or []))
    schema_fingerprint = canonical_fingerprint({"fields": schema_fields})
    if schema_fingerprint != manifest.get("schemaFingerprint"):
        raise ValueError("Dataset schema fingerprint is invalid.")
    if list(manifest.get("internalColumns") or []) != list(INTERNAL_SCHEMA_FIELDS):
        raise ValueError("Dataset version internal row id contract is invalid.")
    material = _version_material(manifest)
    if canonical_fingerprint(material) != manifest.get("contentFingerprint"):
        raise ValueError("Dataset content fingerprint is invalid.")
    expected_version = "version_" + canonical_fingerprint({
        "workspaceId": manifest.get("workspaceId"),
        "tableKey": manifest.get("tableKey"),
        "contentFingerprint": manifest.get("contentFingerprint"),
    })[:24]
    if version_id != expected_version:
        raise ValueError("Dataset version binding is invalid.")
    files = list(manifest.get("files") or [])
    if len(files) != 1:
        raise ValueError("Dataset version currently requires one sealed Parquet object.")
    file_entry = files[0]
    if not isinstance(file_entry, Mapping) or not OBJECT_HASH_RE.fullmatch(str(file_entry.get("objectHash") or "")):
        raise ValueError("Dataset object manifest is invalid.")
    if str(file_entry.get("objectKey") or "") != object_key_for(str(manifest.get("workspaceId") or ""), str(file_entry.get("objectHash") or "")):
        raise ValueError("Dataset object is outside its workspace namespace.")


def publish_dataset_version(connection: sqlite3.Connection, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Persist a prepared manifest.  This does not switch the active pointer."""

    validate_dataset_version_manifest(manifest)
    assert_dataset_version_schema(connection)
    version_id = str(manifest["versionId"])
    existing = connection.execute("SELECT * FROM dataset_versions WHERE version_id = ?", (version_id,)).fetchone()
    if existing is not None:
        if str(existing["content_fingerprint"]) != str(manifest["contentFingerprint"]):
            raise RuntimeError("Dataset version id collides with different content.")
        replayed = dataset_version(connection, version_id)
        if replayed is None:
            raise RuntimeError("Dataset version catalogue is incomplete.")
        return {**replayed, "status": "published", "idempotentReplay": True}
    connection.execute(
        """
        INSERT INTO dataset_versions(
          version_id, workspace_id, table_key, row_count, column_count, schema_json,
          schema_fingerprint, content_fingerprint, source_file, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            version_id,
            str(manifest["workspaceId"]),
            str(manifest["tableKey"]),
            int(manifest["rowCount"]),
            int(manifest["columnCount"]),
            json.dumps(list(manifest["schemaFields"]), ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            str(manifest["schemaFingerprint"]),
            str(manifest["contentFingerprint"]),
            str(manifest.get("sourceFile") or ""),
            str(manifest["createdAt"]),
        ),
    )
    for item in manifest.get("files") or []:
        connection.execute(
            """
            INSERT INTO dataset_version_files(version_id, ordinal, object_key, object_hash, row_count, byte_size)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                version_id,
                int(item["ordinal"]),
                str(item["objectKey"]),
                str(item["objectHash"]),
                int(item["rowCount"]),
                int(item["byteSize"]),
            ),
        )
    return {**dict(manifest), "status": "published", "idempotentReplay": False}


def activate_dataset_version(connection: sqlite3.Connection, manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Switch the metadata pointer; the caller must hold the activation transaction."""

    validate_dataset_version_manifest(manifest)
    published = connection.execute(
        "SELECT content_fingerprint FROM dataset_versions WHERE version_id = ?",
        (str(manifest["versionId"]),),
    ).fetchone()
    published_fingerprint = (
        str(published["content_fingerprint"])
        if isinstance(published, sqlite3.Row)
        else str(published[0]) if published is not None else ""
    )
    if published_fingerprint != str(manifest["contentFingerprint"]):
        raise RuntimeError("Dataset version must be published before activation.")
    registry_columns = {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(table_registry)").fetchall()
    }
    required = {"active_version_id", "schema_json", "schema_fingerprint", "content_fingerprint"}
    if not required.issubset(registry_columns):
        raise RuntimeError("Dataset v2 table_registry columns are not installed.")
    cursor = connection.execute(
        """
        UPDATE table_registry
        SET active_version_id = ?, schema_json = ?, schema_fingerprint = ?, content_fingerprint = ?
        WHERE workspace_id = ? AND table_key = ?
        """,
        (
            str(manifest["versionId"]),
            json.dumps(list(manifest["schemaFields"]), ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            str(manifest["schemaFingerprint"]),
            str(manifest["contentFingerprint"]),
            str(manifest["workspaceId"]),
            str(manifest["tableKey"]),
        ),
    )
    if int(cursor.rowcount or 0) != 1:
        raise RuntimeError("Dataset version activation target is missing.")
    return {**dict(manifest), "status": "active"}


def dataset_version(connection: sqlite3.Connection, version_id: str) -> dict[str, Any] | None:
    assert_dataset_version_schema(connection)
    row = connection.execute("SELECT * FROM dataset_versions WHERE version_id = ?", (version_id,)).fetchone()
    if row is None:
        return None
    files = connection.execute(
        "SELECT ordinal, object_key, object_hash, row_count, byte_size "
        "FROM dataset_version_files WHERE version_id = ? ORDER BY ordinal",
        (version_id,),
    ).fetchall()
    payload = {
        "schema": DATASET_VERSION_SCHEMA,
        "status": "published",
        "versionId": str(row["version_id"]),
        "workspaceId": str(row["workspace_id"]),
        "tableKey": str(row["table_key"]),
        "rowCount": int(row["row_count"]),
        "columnCount": int(row["column_count"]),
        "schemaFields": json.loads(str(row["schema_json"])),
        "internalColumns": list(INTERNAL_SCHEMA_FIELDS),
        "schemaFingerprint": str(row["schema_fingerprint"]),
        "contentFingerprint": str(row["content_fingerprint"]),
        "sourceFile": str(row["source_file"]),
        "createdAt": str(row["created_at"]),
        "files": [
            {
                "ordinal": int(item["ordinal"]),
                "objectKey": str(item["object_key"]),
                "objectHash": str(item["object_hash"]),
                "rowCount": int(item["row_count"]),
                "byteSize": int(item["byte_size"]),
            }
            for item in files
        ],
    }
    validate_dataset_version_manifest(payload)
    return payload


def active_dataset_version(connection: sqlite3.Connection, workspace_id: str, table_key: str) -> dict[str, Any] | None:
    columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(table_registry)").fetchall()}
    if "active_version_id" not in columns:
        return None
    row = connection.execute(
        "SELECT active_version_id FROM table_registry WHERE workspace_id = ? AND table_key = ?",
        (workspace_id, table_key),
    ).fetchone()
    version_id = str(row["active_version_id"] or "") if row is not None else ""
    return dataset_version(connection, version_id) if version_id else None


def dataset_object_candidates(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    table_keys: Iterable[str] | None = None,
) -> list[dict[str, str]]:
    """Return the immutable objects owned by dataset versions in one delete scope."""

    normalized_keys = sorted({str(value).strip() for value in table_keys or [] if str(value).strip()})
    if table_keys is not None and not normalized_keys:
        return []
    params: list[Any] = [str(workspace_id)]
    table_clause = ""
    if normalized_keys:
        placeholders = ", ".join("?" for _ in normalized_keys)
        table_clause = f" AND versions.table_key IN ({placeholders})"
        params.extend(normalized_keys)
    rows = connection.execute(
        f"""
        SELECT DISTINCT files.object_key, files.object_hash
        FROM dataset_version_files AS files
        JOIN dataset_versions AS versions ON versions.version_id = files.version_id
        WHERE versions.workspace_id = ?{table_clause}
        ORDER BY files.object_key, files.object_hash
        """,
        params,
    ).fetchall()
    return [
        {"objectKey": str(row[0]), "objectHash": str(row[1]).lower()}
        for row in rows
    ]


def delete_dataset_versions(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    table_keys: Iterable[str] | None = None,
) -> dict[str, int]:
    """Delete version catalogue rows inside the caller's SQLite transaction."""

    normalized_keys = sorted({str(value).strip() for value in table_keys or [] if str(value).strip()})
    if table_keys is not None and not normalized_keys:
        return {"dataset_version_files": 0, "dataset_versions": 0}
    params: list[Any] = [str(workspace_id)]
    table_clause = ""
    if normalized_keys:
        placeholders = ", ".join("?" for _ in normalized_keys)
        table_clause = f" AND table_key IN ({placeholders})"
        params.extend(normalized_keys)
    version_rows = connection.execute(
        f"SELECT version_id FROM dataset_versions WHERE workspace_id = ?{table_clause}",
        params,
    ).fetchall()
    version_ids = [str(row[0]) for row in version_rows]
    if not version_ids:
        return {"dataset_version_files": 0, "dataset_versions": 0}
    placeholders = ", ".join("?" for _ in version_ids)
    files_cursor = connection.execute(
        f"DELETE FROM dataset_version_files WHERE version_id IN ({placeholders})",
        version_ids,
    )
    versions_cursor = connection.execute(
        f"DELETE FROM dataset_versions WHERE version_id IN ({placeholders})",
        version_ids,
    )
    return {
        "dataset_version_files": int(files_cursor.rowcount or 0),
        "dataset_versions": int(versions_cursor.rowcount or 0),
    }


def _duckdb_manifest_object_references(paths: Iterable[Path]) -> set[tuple[str, str]]:
    catalog_paths = sorted({Path(value).resolve() for value in paths if Path(value).exists()}, key=str)
    if not catalog_paths:
        return set()
    try:
        import duckdb  # type: ignore
    except ImportError as error:  # pragma: no cover - deployment contract
        raise RuntimeError("DuckDB is required for dataset object garbage collection.") from error
    references: set[tuple[str, str]] = set()
    for catalog_path in catalog_paths:
        if not catalog_path.is_file() or catalog_path.is_symlink():
            raise RuntimeError("Dataset manifest catalogue is unavailable or unsafe.")
        with duckdb.connect(str(catalog_path), read_only=True) as catalog:
            manifest_exists = catalog.execute(
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = current_schema() AND table_name = '__aibi_replica_manifest'"
            ).fetchone()
            if not manifest_exists:
                continue
            rows = catalog.execute(
                "SELECT object_keys_json, object_hashes_json FROM __aibi_replica_manifest"
            ).fetchall()
            for keys_json, hashes_json in rows:
                try:
                    keys = [str(value) for value in json.loads(str(keys_json or "[]"))]
                    hashes = [str(value).lower() for value in json.loads(str(hashes_json or "[]"))]
                except (TypeError, ValueError, json.JSONDecodeError) as error:
                    raise RuntimeError("Dataset manifest object references are invalid.") from error
                if not keys or len(keys) != len(hashes):
                    raise RuntimeError("Dataset manifest object references are incomplete.")
                references.update(zip(keys, hashes, strict=True))
    return references


def duckdb_manifest_object_references(paths: Iterable[Path]) -> list[dict[str, str]]:
    """Return stable CAS key/hash pairs referenced by DuckDB replica manifests."""

    return [
        {"objectKey": object_key, "objectHash": object_hash}
        for object_key, object_hash in sorted(_duckdb_manifest_object_references(paths))
    ]


def verify_duckdb_manifest_objects(
    paths: Iterable[Path],
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    """Verify every immutable object referenced by one or more DuckDB catalogues."""

    catalog_paths = [Path(value).resolve() for value in paths]
    references = _duckdb_manifest_object_references(catalog_paths)
    for object_key, object_hash in sorted(references):
        if not OBJECT_HASH_RE.fullmatch(object_hash):
            raise RuntimeError("Dataset manifest contains an invalid object hash.")
        path = resolve_object_key(object_key, root=root)
        if path.name != f"{object_hash}.parquet":
            raise RuntimeError("Dataset manifest object key/hash binding is invalid.")
        if not path.is_file() or path.is_symlink():
            raise FileNotFoundError(f"Dataset object is unavailable: {object_key}")
        if file_sha256(path) != object_hash:
            raise RuntimeError("Dataset object integrity verification failed.")
    return {"catalogCount": len(set(catalog_paths)), "objectCount": len(references)}


def _is_transient_dataset_object_unlink_error(error: OSError) -> bool:
    """Return whether a CAS unlink failed because a reader still owns a handle."""

    return (
        isinstance(error, PermissionError)
        or getattr(error, "winerror", None) in {32, 33}
        or error.errno in {errno.EACCES, errno.EBUSY, errno.EPERM}
    )


def _unlink_dataset_object(path: Path) -> None:
    """Unlink a verified CAS object after bounded transient-reader retries."""

    for attempt, delay_seconds in enumerate(_GC_UNLINK_RETRY_DELAYS):
        if delay_seconds:
            time.sleep(delay_seconds)
        try:
            path.unlink()
            return
        except OSError as error:
            final_attempt = attempt == len(_GC_UNLINK_RETRY_DELAYS) - 1
            if final_attempt or not _is_transient_dataset_object_unlink_error(error):
                raise
            # CPython wrappers and DuckDB result objects can be the last owners
            # of a Windows Parquet handle after a connection has closed.
            gc.collect()


def collect_unreferenced_dataset_objects(
    connection: sqlite3.Connection,
    *,
    candidates: Iterable[Mapping[str, Any]],
    duckdb_paths: Iterable[Path],
    root: Path | None = None,
) -> dict[str, Any]:
    """Unlink verified CAS objects only when no live version or manifest references them."""

    normalized: set[tuple[str, str]] = set()
    for item in candidates:
        object_key = str(item.get("objectKey") or "")
        object_hash = str(item.get("objectHash") or "").lower()
        if not object_key or not OBJECT_HASH_RE.fullmatch(object_hash):
            raise ValueError("Dataset object garbage-collection candidate is invalid.")
        if resolve_object_key(object_key, root=root).name != f"{object_hash}.parquet":
            raise ValueError("Dataset object garbage-collection key/hash binding is invalid.")
        normalized.add((object_key, object_hash))
    if not normalized:
        return {
            "candidateCount": 0,
            "deletedCount": 0,
            "retainedCount": 0,
            "missingCount": 0,
            "deletedObjectKeys": [],
            "missingObjectKeys": [],
        }

    version_references = {
        (str(row[0]), str(row[1]).lower())
        for row in connection.execute(
            "SELECT DISTINCT object_key, object_hash FROM dataset_version_files"
        ).fetchall()
    }
    manifest_references = _duckdb_manifest_object_references(duckdb_paths)
    referenced = version_references | manifest_references
    deleted: list[str] = []
    missing: list[str] = []
    object_root = (root or configured_dataset_object_root()).resolve()
    lock_path = object_root / ".aibi-dataset-object.lock"
    with workspace_mutation_lock(lock_path, timeout_seconds=60.0):
        for object_key, object_hash in sorted(normalized):
            if (object_key, object_hash) in referenced:
                continue
            path = resolve_object_key(object_key, root=root)
            if not path.exists():
                missing.append(object_key)
                continue
            if not path.is_file() or path.is_symlink():
                raise RuntimeError("Dataset object garbage collection refused an unsafe path.")
            if file_sha256(path) != object_hash:
                raise RuntimeError("Dataset object garbage collection refused an integrity mismatch.")
            _unlink_dataset_object(path)
            _fsync_directory(path.parent)
            deleted.append(object_key)
    return {
        "candidateCount": len(normalized),
        "deletedCount": len(deleted),
        "retainedCount": len(normalized) - len(deleted) - len(missing),
        "missingCount": len(missing),
        "deletedObjectKeys": deleted,
        "missingObjectKeys": missing,
    }


def resolve_dataset_object_paths(manifest: Mapping[str, Any], *, root: Path | None = None, verify: bool = True) -> list[Path]:
    validate_dataset_version_manifest(manifest)
    paths: list[Path] = []
    for item in manifest.get("files") or []:
        path = resolve_object_key(str(item["objectKey"]), root=root)
        if not path.is_file() or path.is_symlink():
            raise FileNotFoundError(f"Dataset object is unavailable: {item['objectKey']}")
        if verify and file_sha256(path) != str(item["objectHash"]):
            raise RuntimeError("Dataset object integrity verification failed.")
        paths.append(path)
    return paths


def duckdb_parquet_relation(paths: Iterable[Path]) -> str:
    literals = ["'" + str(Path(path).resolve()).replace("'", "''") + "'" for path in paths]
    if not literals:
        raise ValueError("Dataset relation requires at least one Parquet object.")
    return f"read_parquet([{', '.join(literals)}], union_by_name = true)"
