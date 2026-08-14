from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence
from uuid import uuid4

from bi_cli_core import DB_PATH, now_iso
from workspace_mutation_lock_service import workspace_mutation_lock


IMPORT_STAGE_SCHEMA = "aibi-import-stage/v1"
IMPORT_STAGE_PARSER_VERSION = "table-file-v1"
DEFAULT_STAGE_TTL_SECONDS = 7 * 24 * 60 * 60
DEFAULT_STAGE_QUOTA_BYTES = 2 * 1024 * 1024 * 1024
STAGE_TABLE = "stage_rows"


def _canonical_fingerprint(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _bounded_int(value: str | int | None, fallback: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value or fallback)
    except (TypeError, ValueError):
        parsed = fallback
    return max(minimum, min(parsed, maximum))


def configured_import_stage_root(database_path: Path = DB_PATH) -> Path:
    configured = str(os.environ.get("AIBI_IMPORT_STAGE_ROOT") or "").strip()
    return Path(configured).expanduser().resolve() if configured else (database_path.parent / "import-staging").resolve()


def _workspace_bucket(workspace_id: str) -> str:
    return hashlib.sha256(workspace_id.encode("utf-8")).hexdigest()[:24]


def _stage_paths(root: Path, workspace_id: str, stage_key: str) -> tuple[Path, Path]:
    suffix = stage_key[6:] if stage_key.startswith("stage_") else ""
    if len(stage_key) != 30 or len(suffix) != 24 or any(character not in "0123456789abcdef" for character in suffix):
        raise ValueError("Import stage key is invalid.")
    bucket = (root / _workspace_bucket(workspace_id)).resolve()
    if root != bucket and root not in bucket.parents:
        raise PermissionError("Import stage escaped the configured root.")
    database = bucket / f"{stage_key}.sqlite"
    return database, database.with_suffix(".sha256")


def _quote_identifier(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _manifest_material(manifest: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in manifest.items() if key != "contentFingerprint"}


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _expires_at(created_at: str, ttl_seconds: int) -> str:
    return (_parse_iso(created_at) + timedelta(seconds=ttl_seconds)).astimezone(timezone.utc).isoformat()


def _stage_summary(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": IMPORT_STAGE_SCHEMA,
        "stageKey": manifest["stageKey"],
        "workspaceId": manifest["workspaceId"],
        "contentHash": manifest["contentHash"],
        "contentFingerprint": manifest["contentFingerprint"],
        "parserVersion": manifest["parserVersion"],
        "sourceName": manifest["sourceName"],
        "sourceBytes": manifest["sourceBytes"],
        "rowCount": manifest["rowCount"],
        "columnCount": manifest["columnCount"],
        "createdAt": manifest["createdAt"],
        "expiresAt": manifest["expiresAt"],
        "sealed": True,
    }


def _root_usage(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(path.stat().st_size for path in root.rglob("*.sqlite") if path.is_file() and not path.is_symlink())


def _write_rows(
    connection: sqlite3.Connection,
    headers: Sequence[str],
    rows: Iterable[dict[str, Any]],
) -> tuple[int, str]:
    columns_sql = ", ".join(f"{_quote_identifier(header)} TEXT" for header in headers)
    connection.execute(f"CREATE TABLE {_quote_identifier(STAGE_TABLE)} (__row_index INTEGER PRIMARY KEY, {columns_sql})")
    placeholders = ", ".join("?" for _ in headers)
    insert_sql = (
        f"INSERT INTO {_quote_identifier(STAGE_TABLE)} (__row_index, "
        f"{', '.join(_quote_identifier(header) for header in headers)}) VALUES (?, {placeholders})"
    )
    digest = hashlib.sha256()
    batch: list[list[str | int]] = []
    row_count = 0
    for row_count, row in enumerate(rows, start=1):
        values = [str(row.get(header, "") if row.get(header, "") is not None else "") for header in headers]
        digest.update(json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        digest.update(b"\n")
        batch.append([row_count, *values])
        if len(batch) >= 1000:
            connection.executemany(insert_sql, batch)
            batch.clear()
    if batch:
        connection.executemany(insert_sql, batch)
    return row_count, digest.hexdigest()


def create_import_stage(
    *,
    source_path: str | Path,
    workspace_id: str,
    headers: Sequence[str],
    rows: Iterable[dict[str, Any]],
    profile: dict[str, Any],
    root: Path | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    resolved_source = Path(source_path).resolve()
    if not resolved_source.is_file():
        raise FileNotFoundError(resolved_source)
    normalized_workspace = str(workspace_id or "").strip()
    if not normalized_workspace:
        raise ValueError("Import stage requires a workspace.")
    normalized_headers = [str(header) for header in headers]
    if not normalized_headers or len(set(normalized_headers)) != len(normalized_headers):
        raise ValueError("Import stage requires unique source headers.")

    stage_root = (root or configured_import_stage_root()).resolve()
    if stage_root.exists() and stage_root.is_symlink():
        raise PermissionError("Import stage root cannot be a symbolic link.")
    source_bytes = resolved_source.stat().st_size
    content_hash = _file_sha256(resolved_source)
    stage_key = "stage_" + hashlib.sha256(
        f"{normalized_workspace}\0{content_hash}\0{IMPORT_STAGE_PARSER_VERSION}".encode("utf-8")
    ).hexdigest()[:24]
    database_path, digest_path = _stage_paths(stage_root, normalized_workspace, stage_key)
    quota_lock = stage_root / ".aibi-import-stage-quota.lock"
    with workspace_mutation_lock(quota_lock, timeout_seconds=30.0):
        if database_path.exists() and digest_path.exists():
            manifest = load_import_stage_manifest(
                stage_key=stage_key,
                workspace_id=normalized_workspace,
                root=stage_root,
                allow_expired=False,
            )
            return _stage_summary(manifest)

        quota = _bounded_int(os.environ.get("AIBI_IMPORT_STAGE_MAX_BYTES"), DEFAULT_STAGE_QUOTA_BYTES, 1024 * 1024, 100 * 1024 * 1024 * 1024)
        current_usage = _root_usage(stage_root)
        if source_bytes > quota or current_usage + source_bytes > quota:
            raise OSError("Import stage quota would be exceeded.")

        database_path.parent.mkdir(parents=True, exist_ok=True)
        if database_path.parent.is_symlink():
            raise PermissionError("Import stage workspace bucket cannot be a symbolic link.")
        temp_database = database_path.with_name(f".{database_path.name}.{uuid4().hex}.tmp")
        temp_digest = digest_path.with_name(f".{digest_path.name}.{uuid4().hex}.tmp")
        created_at = timestamp or now_iso()
        ttl_seconds = _bounded_int(os.environ.get("AIBI_IMPORT_STAGE_TTL_SECONDS"), DEFAULT_STAGE_TTL_SECONDS, 60, 30 * 24 * 60 * 60)
        try:
            connection = sqlite3.connect(temp_database)
            try:
                connection.execute("PRAGMA journal_mode=DELETE")
                connection.execute("PRAGMA synchronous=FULL")
                connection.execute("CREATE TABLE stage_metadata (key TEXT PRIMARY KEY, value_json TEXT NOT NULL)")
                row_count, row_digest = _write_rows(connection, normalized_headers, rows)
                if int(profile.get("rowCount") or 0) != row_count:
                    raise ValueError("Import stage row count does not match its profile.")
                manifest = {
                    "schema": IMPORT_STAGE_SCHEMA,
                    "stageKey": stage_key,
                    "workspaceId": normalized_workspace,
                    "contentHash": content_hash,
                    "parserVersion": IMPORT_STAGE_PARSER_VERSION,
                    "sourceName": resolved_source.name,
                    "sourceBytes": source_bytes,
                    "headers": normalized_headers,
                    "rowCount": row_count,
                    "columnCount": len(normalized_headers),
                    "rowDigest": row_digest,
                    "profile": profile,
                    "createdAt": created_at,
                    "expiresAt": _expires_at(created_at, ttl_seconds),
                }
                manifest["contentFingerprint"] = _canonical_fingerprint(_manifest_material(manifest))
                connection.execute(
                    "INSERT INTO stage_metadata(key, value_json) VALUES('manifest', ?)",
                    (json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")),),
                )
                connection.commit()
            finally:
                connection.close()

            stage_bytes = temp_database.stat().st_size
            if stage_bytes > quota or current_usage + stage_bytes > quota:
                raise OSError("Import stage quota would be exceeded by the parsed stage.")
            temp_digest.write_text(_file_sha256(temp_database), encoding="ascii")
            os.replace(temp_database, database_path)
            os.replace(temp_digest, digest_path)
        finally:
            temp_database.unlink(missing_ok=True)
            temp_digest.unlink(missing_ok=True)
        return _stage_summary(manifest)


def load_import_stage_manifest(
    *,
    stage_key: str,
    workspace_id: str,
    root: Path | None = None,
    allow_expired: bool = True,
) -> dict[str, Any]:
    stage_root = (root or configured_import_stage_root()).resolve()
    database_path, digest_path = _stage_paths(stage_root, workspace_id, stage_key)
    if database_path.is_symlink() or digest_path.is_symlink():
        raise PermissionError("Import stage files cannot be symbolic links.")
    if not database_path.is_file() or not digest_path.is_file():
        raise FileNotFoundError(f"Import stage is unavailable: {stage_key}")
    expected_digest = digest_path.read_text(encoding="ascii").strip().lower()
    if len(expected_digest) != 64 or _file_sha256(database_path) != expected_digest:
        raise ValueError("Import stage integrity verification failed.")
    connection = sqlite3.connect(f"file:{database_path.as_posix()}?mode=ro", uri=True)
    try:
        row = connection.execute("SELECT value_json FROM stage_metadata WHERE key = 'manifest'").fetchone()
        if row is None:
            raise ValueError("Import stage manifest is missing.")
        manifest = json.loads(str(row[0]))
        if manifest.get("schema") != IMPORT_STAGE_SCHEMA:
            raise ValueError("Import stage schema is unsupported.")
        if manifest.get("stageKey") != stage_key or manifest.get("workspaceId") != workspace_id:
            raise PermissionError("Import stage does not belong to the requested workspace.")
        if _canonical_fingerprint(_manifest_material(manifest)) != manifest.get("contentFingerprint"):
            raise ValueError("Import stage manifest integrity verification failed.")
        actual_rows = int(connection.execute(f"SELECT COUNT(*) FROM {_quote_identifier(STAGE_TABLE)}").fetchone()[0])
        if actual_rows != int(manifest.get("rowCount") or 0):
            raise ValueError("Import stage row count drifted.")
    finally:
        connection.close()
    if not allow_expired and _parse_iso(str(manifest["expiresAt"])) <= datetime.now(timezone.utc):
        raise ValueError("Import stage expired; run the preview again.")
    return manifest


def iter_import_stage_rows(
    *,
    stage_key: str,
    workspace_id: str,
    root: Path | None = None,
    batch_size: int = 1000,
) -> Iterator[list[dict[str, str]]]:
    manifest = load_import_stage_manifest(stage_key=stage_key, workspace_id=workspace_id, root=root)
    stage_root = (root or configured_import_stage_root()).resolve()
    database_path, _ = _stage_paths(stage_root, workspace_id, stage_key)
    headers = [str(header) for header in manifest["headers"]]
    connection = sqlite3.connect(f"file:{database_path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        cursor = connection.execute(
            f"SELECT {', '.join(_quote_identifier(header) for header in headers)} "
            f"FROM {_quote_identifier(STAGE_TABLE)} ORDER BY __row_index"
        )
        while rows := cursor.fetchmany(max(1, min(batch_size, 10_000))):
            yield [{header: str(row[header] or "") for header in headers} for row in rows]
    finally:
        connection.close()


def read_import_stage(
    *,
    stage_key: str,
    workspace_id: str,
    root: Path | None = None,
) -> tuple[list[str], list[dict[str, str]], dict[str, Any], dict[str, Any]]:
    manifest = load_import_stage_manifest(stage_key=stage_key, workspace_id=workspace_id, root=root)
    rows = [row for batch in iter_import_stage_rows(stage_key=stage_key, workspace_id=workspace_id, root=root) for row in batch]
    return list(manifest["headers"]), rows, dict(manifest["profile"]), _stage_summary(manifest)


def validate_import_stage_for_confirmation(
    *,
    stage_key: str,
    workspace_id: str,
    root: Path | None = None,
) -> dict[str, Any]:
    """Require a sealed, current stage before accepting a new durable job.

    An already accepted job may continue after expiry because it is bound to
    immutable bytes. Expiry only removes the authority to create a new job.
    """

    manifest = load_import_stage_manifest(
        stage_key=stage_key,
        workspace_id=workspace_id,
        root=root,
        allow_expired=False,
    )
    return _stage_summary(manifest)
