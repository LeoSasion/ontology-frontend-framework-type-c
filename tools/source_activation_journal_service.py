from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Callable, Iterable

from bi_cli_core import ROOT
from dataset_version_store import collect_unreferenced_dataset_objects, file_sha256, resolve_object_key
from workspace_recovery_service import configured_recovery_root, recovery_point_duckdb_catalogs


JOURNAL_SCHEMA = "aibi-source-activation-journal/v1"
JOURNAL_EVENT_SCHEMA = "aibi-source-activation-journal-event/v1"

PHASE_PREPARED = "prepared"
PHASE_COMMIT_STARTED = "commit_started"
PHASE_REPLICA_PUBLISHED = "replica_published"
PHASE_SOURCE_SELECTION_COMMITTED = "source_selection_committed"
PHASE_FINALIZED = "finalized"

PHASES = (
    PHASE_PREPARED,
    PHASE_COMMIT_STARTED,
    PHASE_REPLICA_PUBLISHED,
    PHASE_SOURCE_SELECTION_COMMITTED,
    PHASE_FINALIZED,
)
ALLOWED_PHASE_TRANSITIONS = {
    PHASE_PREPARED: frozenset({PHASE_COMMIT_STARTED, PHASE_FINALIZED}),
    PHASE_COMMIT_STARTED: frozenset({PHASE_REPLICA_PUBLISHED, PHASE_FINALIZED}),
    PHASE_REPLICA_PUBLISHED: frozenset({PHASE_SOURCE_SELECTION_COMMITTED, PHASE_FINALIZED}),
    PHASE_SOURCE_SELECTION_COMMITTED: frozenset({PHASE_FINALIZED}),
    PHASE_FINALIZED: frozenset(),
}


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _load_json(value: Any, fallback: Any) -> Any:
    if value in (None, ""):
        return fallback
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def stable_fingerprint(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


_ACTIVATION_REQUIRED_COLUMNS = {
    "analysis_jobs": frozenset({"workspace_id", "kind", "request_key"}),
    "source_activation_journals": frozenset(
        {
            "journal_key",
            "workspace_id",
            "job_key",
            "phase",
            "plan_fingerprint",
            "parent_source_run_id",
            "target_source_run_id",
            "table_keys_json",
            "expected_manifest_json",
            "rollback_manifest_json",
            "outcome",
            "warning_json",
            "created_at",
            "updated_at",
            "finalized_at",
        }
    ),
    "import_workspace_leases": frozenset(
        {
            "workspace_id",
            "job_key",
            "lease_token",
            "lease_epoch",
            "active",
            "acquired_at",
            "updated_at",
            "released_at",
        }
    ),
    "source_activation_journal_events": frozenset(
        {
            "event_sequence",
            "workspace_id",
            "journal_key",
            "job_key",
            "phase",
            "event_type",
            "payload_json",
            "created_at",
        }
    ),
}


def assert_activation_journal_schema(connection: sqlite3.Connection) -> None:
    """Fail closed when the clean-v18 activation contract is incomplete."""

    table_names = tuple(_ACTIVATION_REQUIRED_COLUMNS)
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
    for table_name, required_columns in _ACTIVATION_REQUIRED_COLUMNS.items():
        missing_columns = sorted(required_columns - actual_by_table[table_name])
        if missing_columns:
            raise RuntimeError(
                f"AIBI-C clean v18 activation schema is incomplete; {table_name} "
                "is missing columns: "
                + ", ".join(missing_columns)
            )


def claim_import_workspace(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    job_key: str,
    lease_token: str,
    now_iso: Callable[[], str],
) -> int | None:
    token = str(lease_token or "").strip()
    if len(token) < 16 or len(token) > 200:
        raise ValueError("Import worker lease token is invalid.")
    row = connection.execute(
        "SELECT job_key, lease_token, lease_epoch, active FROM import_workspace_leases WHERE workspace_id = ?",
        (workspace_id,),
    ).fetchone()
    timestamp = now_iso()
    if row is None:
        connection.execute(
            """
            INSERT INTO import_workspace_leases(
              workspace_id, job_key, lease_token, lease_epoch, active, acquired_at, updated_at, released_at
            ) VALUES(?, ?, ?, 1, 1, ?, ?, NULL)
            """,
            (workspace_id, job_key, token, timestamp, timestamp),
        )
        return 1
    if int(row["active"] or 0) == 1:
        if str(row["job_key"]) == job_key and str(row["lease_token"] or "") == token:
            return int(row["lease_epoch"] or 0)
        return None
    next_epoch = int(row["lease_epoch"] or 0) + 1
    cursor = connection.execute(
        """
        UPDATE import_workspace_leases
        SET job_key = ?, lease_token = ?, lease_epoch = ?, active = 1,
            acquired_at = ?, updated_at = ?, released_at = NULL
        WHERE workspace_id = ? AND active = 0 AND lease_epoch = ?
        """,
        (job_key, token, next_epoch, timestamp, timestamp, workspace_id, int(row["lease_epoch"] or 0)),
    )
    return next_epoch if cursor.rowcount == 1 else None


def assert_import_workspace(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    job_key: str,
    lease_token: str,
    lease_epoch: int,
) -> None:
    row = connection.execute(
        """
        SELECT 1 FROM import_workspace_leases
        WHERE workspace_id = ? AND job_key = ? AND lease_token = ? AND lease_epoch = ? AND active = 1
        """,
        (workspace_id, job_key, lease_token, int(lease_epoch)),
    ).fetchone()
    if row is None:
        raise RuntimeError("Import worker lease was fenced by recovery or another owner.")


def release_import_workspace(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    job_key: str,
    lease_token: str,
    lease_epoch: int,
    now_iso: Callable[[], str],
) -> bool:
    timestamp = now_iso()
    cursor = connection.execute(
        """
        UPDATE import_workspace_leases
        SET active = 0, updated_at = ?, released_at = ?
        WHERE workspace_id = ? AND job_key = ? AND lease_token = ? AND lease_epoch = ? AND active = 1
        """,
        (timestamp, timestamp, workspace_id, job_key, lease_token, int(lease_epoch)),
    )
    return cursor.rowcount > 0


def revoke_import_workspace_leases(
    connection: sqlite3.Connection,
    *,
    now_iso: Callable[[], str],
    workspace_id: str | None = None,
    job_key: str | None = None,
    lease_token: str | None = None,
) -> list[dict[str, Any]]:
    """Fence active owners before reconciliation; an old owner can no longer mutate or release a newer lease."""
    where = ["active = 1"]
    params: list[Any] = []
    if workspace_id:
        where.append("workspace_id = ?")
        params.append(workspace_id)
    if job_key:
        where.append("job_key = ?")
        params.append(job_key)
    if lease_token:
        where.append("lease_token = ?")
        params.append(lease_token)
    rows = connection.execute(
        f"SELECT workspace_id, job_key, lease_token, lease_epoch FROM import_workspace_leases WHERE {' AND '.join(where)}",
        tuple(params),
    ).fetchall()
    timestamp = now_iso()
    revoked: list[dict[str, Any]] = []
    for row in rows:
        cursor = connection.execute(
            """
            UPDATE import_workspace_leases
            SET active = 0, lease_epoch = lease_epoch + 1, updated_at = ?, released_at = ?
            WHERE workspace_id = ? AND job_key = ? AND lease_token = ? AND lease_epoch = ? AND active = 1
            """,
            (
                timestamp,
                timestamp,
                row["workspace_id"],
                row["job_key"],
                row["lease_token"],
                int(row["lease_epoch"] or 0),
            ),
        )
        if cursor.rowcount == 1:
            revoked.append({
                "workspaceId": str(row["workspace_id"]),
                "jobKey": str(row["job_key"]),
                "leaseEpoch": int(row["lease_epoch"] or 0),
            })
    return revoked


def _journal_row(connection: sqlite3.Connection, workspace_id: str, journal_key: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM source_activation_journals WHERE workspace_id = ? AND journal_key = ?",
        (workspace_id, journal_key),
    ).fetchone()
    if row is None:
        raise ValueError(f"Unknown source activation journal in active workspace: {journal_key}")
    return row


def journal_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "schema": JOURNAL_SCHEMA,
        "journalKey": row["journal_key"],
        "workspaceId": row["workspace_id"],
        "jobKey": row["job_key"],
        "phase": row["phase"],
        "planFingerprint": row["plan_fingerprint"],
        "parentSourceRunId": row["parent_source_run_id"],
        "targetSourceRunId": row["target_source_run_id"],
        "tableKeys": _load_json(row["table_keys_json"], []),
        "expectedManifest": _load_json(row["expected_manifest_json"], []),
        "rollbackManifest": _load_json(row["rollback_manifest_json"], []),
        "outcome": row["outcome"] or None,
        "warning": _load_json(row["warning_json"], None),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "finalizedAt": row["finalized_at"],
    }


def event_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "schema": JOURNAL_EVENT_SCHEMA,
        "sequence": int(row["event_sequence"]),
        "workspaceId": row["workspace_id"],
        "journalKey": row["journal_key"],
        "jobKey": row["job_key"],
        "phase": row["phase"],
        "type": row["event_type"],
        "payload": _load_json(row["payload_json"], {}),
        "createdAt": row["created_at"],
    }


def _append_event(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    journal_key: str,
    job_key: str,
    phase: str,
    event_type: str,
    payload: dict[str, Any] | None,
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO source_activation_journal_events(
          workspace_id, journal_key, job_key, phase, event_type, payload_json, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?)
        """,
        (workspace_id, journal_key, job_key, phase, event_type, _json(payload or {}), created_at),
    )


def prepare_activation(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    job_key: str,
    plan_fingerprint: str,
    parent_source_run_id: str | None,
    table_keys: Iterable[str],
    expected_manifest: list[dict[str, Any]],
    rollback_manifest: list[dict[str, Any]],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    assert_activation_journal_schema(connection)
    existing = connection.execute(
        """
        SELECT * FROM source_activation_journals
        WHERE workspace_id = ? AND job_key = ? AND phase <> ?
        ORDER BY created_at DESC, journal_key DESC
        LIMIT 1
        """,
        (workspace_id, job_key, PHASE_FINALIZED),
    ).fetchone()
    if existing is not None:
        payload = journal_payload(existing)
        if payload["planFingerprint"] != plan_fingerprint:
            raise ValueError("Import job is already bound to a different activation plan.")
        return payload
    competing = connection.execute(
        """
        SELECT job_key, journal_key, phase FROM source_activation_journals
        WHERE workspace_id = ? AND phase <> ?
        ORDER BY created_at, journal_key
        LIMIT 1
        """,
        (workspace_id, PHASE_FINALIZED),
    ).fetchone()
    if competing is not None:
        raise RuntimeError(
            "Workspace already has an unfinished source activation "
            f"({competing['job_key']} at {competing['phase']})."
        )
    timestamp = now_iso()
    journal_key = f"activation_{uuid.uuid4().hex[:20]}"
    normalized_table_keys = sorted({str(item).strip() for item in table_keys if str(item).strip()})
    try:
        connection.execute(
            """
            INSERT INTO source_activation_journals(
              journal_key, workspace_id, job_key, phase, plan_fingerprint,
              parent_source_run_id, target_source_run_id, table_keys_json,
              expected_manifest_json, rollback_manifest_json, outcome, warning_json,
              created_at, updated_at, finalized_at
            ) VALUES(?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, '', 'null', ?, ?, NULL)
            """,
            (
                journal_key,
                workspace_id,
                job_key,
                PHASE_PREPARED,
                plan_fingerprint,
                parent_source_run_id,
                _json(normalized_table_keys),
                _json(expected_manifest),
                _json(rollback_manifest),
                timestamp,
                timestamp,
            ),
        )
    except sqlite3.IntegrityError as exc:
        if "source_activation_journals.workspace_id" not in str(exc):
            raise
        raise RuntimeError("Workspace already has an unfinished source activation.") from exc
    _append_event(
        connection,
        workspace_id=workspace_id,
        journal_key=journal_key,
        job_key=job_key,
        phase=PHASE_PREPARED,
        event_type="activation_prepared",
        payload={"tableKeys": normalized_table_keys, "planFingerprint": plan_fingerprint},
        created_at=timestamp,
    )
    return journal_payload(_journal_row(connection, workspace_id, journal_key))


def transition_activation(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    journal_key: str,
    phase: str,
    now_iso: Callable[[], str],
    target_source_run_id: str | None = None,
    expected_manifest: list[dict[str, Any]] | None = None,
    outcome: str | None = None,
    warning: dict[str, Any] | None = None,
    event_type: str | None = None,
) -> dict[str, Any]:
    if phase not in PHASES:
        raise ValueError(f"Unknown source activation phase: {phase}")
    row = _journal_row(connection, workspace_id, journal_key)
    current_phase = str(row["phase"])
    if phase == current_phase:
        return journal_payload(row)
    if phase not in ALLOWED_PHASE_TRANSITIONS[current_phase]:
        raise ValueError(f"Invalid source activation transition: {current_phase} -> {phase}")
    timestamp = now_iso()
    connection.execute(
        """
        UPDATE source_activation_journals
        SET phase = ?, target_source_run_id = ?, expected_manifest_json = ?,
            outcome = ?, warning_json = ?, updated_at = ?, finalized_at = ?
        WHERE workspace_id = ? AND journal_key = ?
        """,
        (
            phase,
            target_source_run_id if target_source_run_id is not None else row["target_source_run_id"],
            _json(expected_manifest) if expected_manifest is not None else row["expected_manifest_json"],
            outcome if outcome is not None else row["outcome"],
            _json(warning) if warning is not None else row["warning_json"],
            timestamp,
            timestamp if phase == PHASE_FINALIZED else row["finalized_at"],
            workspace_id,
            journal_key,
        ),
    )
    _append_event(
        connection,
        workspace_id=workspace_id,
        journal_key=journal_key,
        job_key=str(row["job_key"]),
        phase=phase,
        event_type=event_type or f"activation_{phase}",
        payload={"fromPhase": current_phase, "toPhase": phase, "outcome": outcome},
        created_at=timestamp,
    )
    return journal_payload(_journal_row(connection, workspace_id, journal_key))


def activation_for_job(connection: sqlite3.Connection, *, workspace_id: str, job_key: str) -> dict[str, Any] | None:
    assert_activation_journal_schema(connection)
    row = connection.execute(
        """
        SELECT * FROM source_activation_journals
        WHERE workspace_id = ? AND job_key = ?
        ORDER BY created_at DESC, journal_key DESC
        LIMIT 1
        """,
        (workspace_id, job_key),
    ).fetchone()
    return journal_payload(row) if row is not None else None


def unfinished_activations(
    connection: sqlite3.Connection,
    *,
    workspace_id: str | None = None,
) -> list[dict[str, Any]]:
    assert_activation_journal_schema(connection)
    params: list[Any] = []
    where = "phase <> ?"
    params.append(PHASE_FINALIZED)
    if workspace_id:
        where += " AND workspace_id = ?"
        params.append(workspace_id)
    rows = connection.execute(
        f"SELECT * FROM source_activation_journals WHERE {where} ORDER BY created_at, journal_key",
        tuple(params),
    ).fetchall()
    return [journal_payload(row) for row in rows]


def _relation_kind(duck_connection: Any, name: str) -> str | None:
    row = duck_connection.execute(
        "SELECT table_type FROM information_schema.tables WHERE table_schema = current_schema() AND table_name = ?",
        [name],
    ).fetchone()
    return str(row[0]) if row else None


def _quote_identifier(name: str) -> str:
    return '"' + str(name).replace('"', '""') + '"'


def _ensure_duck_manifest(duck_connection: Any) -> None:
    duck_connection.execute(
        """
        CREATE TABLE IF NOT EXISTS __aibi_replica_manifest (
          manifest_version INTEGER NOT NULL,
          logical_table VARCHAR PRIMARY KEY,
          source_version VARCHAR NOT NULL,
          version_id VARCHAR NOT NULL,
          object_keys_json VARCHAR NOT NULL,
          object_paths_json VARCHAR NOT NULL,
          object_hashes_json VARCHAR NOT NULL,
          schema_fingerprint VARCHAR NOT NULL,
          content_fingerprint VARCHAR NOT NULL,
          row_count BIGINT NOT NULL,
          published_at TIMESTAMP NOT NULL DEFAULT current_timestamp
        )
        """
    )
    columns = {str(row[0]) for row in duck_connection.execute("DESCRIBE __aibi_replica_manifest").fetchall()}
    required = {
        "manifest_version", "logical_table", "source_version", "version_id",
        "object_keys_json", "object_paths_json", "object_hashes_json",
        "schema_fingerprint", "content_fingerprint", "row_count", "published_at",
    }
    if not required.issubset(columns):
        raise RuntimeError("Dataset manifest v2 is required.")


def _manifest_snapshot(columns: list[str], row: tuple[Any, ...] | None, logical_table: str) -> dict[str, Any]:
    if row is None:
        return {"logicalTable": logical_table, "present": False}
    record = dict(zip(columns, row, strict=True))
    if int(record.get("manifest_version") or 0) != 2:
        raise RuntimeError("Dataset manifest v2 is required.")
    try:
        object_keys = json.loads(str(record.get("object_keys_json") or "[]"))
        object_hashes = json.loads(str(record.get("object_hashes_json") or "[]"))
    except json.JSONDecodeError as error:
        raise RuntimeError("Dataset manifest object binding is invalid.") from error
    return {
        "logicalTable": logical_table,
        "present": True,
        "sourceVersion": str(record.get("source_version") or ""),
        "versionId": str(record.get("version_id") or ""),
        "objectKeys": [str(value) for value in object_keys],
        "objectHashes": [str(value) for value in object_hashes],
        "schemaFingerprint": str(record.get("schema_fingerprint") or ""),
        "contentFingerprint": str(record.get("content_fingerprint") or ""),
        "rowCount": int(record.get("row_count") or 0),
    }


def _verified_object_paths(object_keys: Iterable[str], object_hashes: Iterable[str], *, logical_table: str) -> list[Path]:
    keys = [str(value) for value in object_keys]
    hashes = [str(value).lower() for value in object_hashes]
    if not keys or len(keys) != len(hashes):
        raise RuntimeError(f"Rollback dataset binding is invalid for {logical_table}.")
    paths: list[Path] = []
    for object_key, object_hash in zip(keys, hashes, strict=True):
        path = resolve_object_key(object_key)
        if path.name != f"{object_hash}.parquet":
            raise RuntimeError(f"Rollback dataset object key/hash mismatch for {logical_table}.")
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"Rollback dataset object is missing for {logical_table}.")
        if file_sha256(path) != object_hash:
            raise RuntimeError(f"Rollback dataset object integrity check failed for {logical_table}.")
        paths.append(path)
    return paths


def capture_replica_manifest(duckdb_path: Path, logical_tables: Iterable[str]) -> list[dict[str, Any]]:
    tables = sorted({str(item).strip() for item in logical_tables if str(item).strip()})
    if not tables or not duckdb_path.exists():
        return [{"logicalTable": table, "present": False} for table in tables]
    try:
        import duckdb  # type: ignore
    except Exception as exc:  # pragma: no cover - environment-specific
        raise RuntimeError(f"DuckDB runtime is unavailable: {exc}") from exc
    snapshots: list[dict[str, Any]] = []
    with duckdb.connect(str(duckdb_path), read_only=True) as connection:
        manifest_exists = _relation_kind(connection, "__aibi_replica_manifest") is not None
        if not manifest_exists:
            return [{"logicalTable": table, "present": False} for table in tables]
        columns = [str(row[0]) for row in connection.execute("DESCRIBE __aibi_replica_manifest").fetchall()]
        placeholders = ", ".join("?" for _ in tables)
        rows = connection.execute(
            f"SELECT * FROM __aibi_replica_manifest WHERE logical_table IN ({placeholders})",
            tables,
        ).fetchall()
        by_table = {
            str(dict(zip(columns, row, strict=True)).get("logical_table") or ""): row
            for row in rows
        }
        for table in tables:
            snapshot = _manifest_snapshot(columns, by_table.get(table), table)
            snapshot["relationKind"] = _relation_kind(connection, table)
            snapshots.append(snapshot)
    return snapshots


def replica_manifest_matches(duckdb_path: Path, expected_manifest: Iterable[dict[str, Any]]) -> bool:
    expected = [dict(item) for item in expected_manifest]
    if not expected or not duckdb_path.exists():
        return False
    try:
        import duckdb  # type: ignore
    except Exception:
        return False
    with duckdb.connect(str(duckdb_path), read_only=True) as connection:
        manifest_exists = _relation_kind(connection, "__aibi_replica_manifest") is not None
        columns = [str(row[0]) for row in connection.execute("DESCRIBE __aibi_replica_manifest").fetchall()] if manifest_exists else []
        tables = [str(item.get("logicalTable") or "") for item in expected]
        if any(not table for table in tables):
            return False
        placeholders = ", ".join("?" for _ in tables)
        rows = connection.execute(
            f"SELECT * FROM __aibi_replica_manifest WHERE logical_table IN ({placeholders})",
            tables,
        ).fetchall() if manifest_exists else []
        actual = {
            str(dict(zip(columns, row, strict=True)).get("logical_table") or ""):
            _manifest_snapshot(columns, row, str(dict(zip(columns, row, strict=True)).get("logical_table") or ""))
            for row in rows
        }
        for item in expected:
            logical_table = str(item.get("logicalTable") or "")
            record = actual.get(logical_table)
            relation_kind = _relation_kind(connection, logical_table)
            if item.get("present") is False:
                if record is not None or relation_kind is not None:
                    return False
                continue
            if not record or _relation_kind(connection, logical_table) != "VIEW":
                return False
            for expected_key, actual_key in (
                ("sourceVersion", "sourceVersion"),
                ("versionId", "versionId"),
                ("schemaFingerprint", "schemaFingerprint"),
                ("contentFingerprint", "contentFingerprint"),
            ):
                if str(record.get(actual_key) or "") != str(item.get(expected_key) or ""):
                    return False
            if int(record.get("rowCount") or 0) != int(item.get("rowCount") or 0):
                return False
            expected_hashes = item.get("objectHashes")
            if isinstance(expected_hashes, list) and list(record.get("objectHashes") or []) != [str(value) for value in expected_hashes]:
                return False
    return True


def restore_replica_manifest(duckdb_path: Path, snapshots: Iterable[dict[str, Any]]) -> None:
    items = [dict(item) for item in snapshots]
    if not items:
        return
    try:
        import duckdb  # type: ignore
    except Exception as exc:  # pragma: no cover - environment-specific
        raise RuntimeError(f"DuckDB runtime is unavailable: {exc}") from exc
    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(duckdb_path)) as connection:
        _ensure_duck_manifest(connection)
        connection.execute("BEGIN TRANSACTION")
        try:
            for item in items:
                logical_table = str(item.get("logicalTable") or "")
                if not logical_table:
                    raise ValueError("Rollback manifest contains an empty logical table.")
                current_kind = _relation_kind(connection, logical_table)
                if current_kind == "VIEW":
                    connection.execute(f"DROP VIEW {_quote_identifier(logical_table)}")
                elif current_kind:
                    raise RuntimeError(
                        f"Dataset v2 logical relation must be a VIEW, found {current_kind}: {logical_table}"
                    )
                if item.get("present") is True:
                    object_keys = [str(value) for value in item.get("objectKeys") or []]
                    object_hashes = [str(value) for value in item.get("objectHashes") or []]
                    paths = _verified_object_paths(object_keys, object_hashes, logical_table=logical_table)
                    path_sql = ", ".join("'" + path.as_posix().replace("'", "''") + "'" for path in paths)
                    connection.execute(
                        f"CREATE VIEW {_quote_identifier(logical_table)} AS "
                        f"SELECT * FROM read_parquet([{path_sql}], union_by_name = true)"
                    )
                    connection.execute(
                        """
                        INSERT INTO __aibi_replica_manifest(
                          manifest_version, logical_table, source_version, version_id,
                          object_keys_json, object_paths_json, object_hashes_json,
                          schema_fingerprint, content_fingerprint, row_count, published_at
                        )
                        VALUES(2, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
                        ON CONFLICT(logical_table) DO UPDATE SET
                          manifest_version = excluded.manifest_version,
                          source_version = excluded.source_version,
                          version_id = excluded.version_id,
                          object_keys_json = excluded.object_keys_json,
                          object_paths_json = excluded.object_paths_json,
                          object_hashes_json = excluded.object_hashes_json,
                          schema_fingerprint = excluded.schema_fingerprint,
                          content_fingerprint = excluded.content_fingerprint,
                          row_count = excluded.row_count,
                          published_at = excluded.published_at
                        """,
                        [
                            logical_table,
                            str(item.get("sourceVersion") or ""),
                            str(item.get("versionId") or ""),
                            _json(object_keys),
                            _json([path.as_posix() for path in paths]),
                            _json(object_hashes),
                            str(item.get("schemaFingerprint") or ""),
                            str(item.get("contentFingerprint") or ""),
                            int(item.get("rowCount") or 0),
                        ],
                    )
                else:
                    connection.execute(
                        "DELETE FROM __aibi_replica_manifest WHERE logical_table = ?",
                        [logical_table],
                    )
            connection.execute("COMMIT")
        except Exception:
            connection.execute("ROLLBACK")
            raise


def cleanup_stale_replicas(duckdb_path: Path) -> list[str]:
    if not duckdb_path.exists():
        return []
    try:
        import duckdb  # type: ignore
    except Exception as exc:  # pragma: no cover - environment-specific
        raise RuntimeError(f"DuckDB runtime is unavailable: {exc}") from exc
    with duckdb.connect(str(duckdb_path)) as connection:
        if _relation_kind(connection, "__aibi_replica_manifest") is None:
            return []
        _ensure_duck_manifest(connection)
    # Immutable Parquet objects are reclaimed by a separate version-retention
    # policy; activation never drops content-addressed files or copies tables.
    return []


def reconcile_activation(
    connection: sqlite3.Connection,
    *,
    journal: dict[str, Any],
    duckdb_path: Path,
    now_iso: Callable[[], str],
    protected_duckdb_paths: Iterable[Path] | None = None,
) -> dict[str, Any]:
    """Reconcile one interrupted activation. The operation is intentionally idempotent."""
    workspace_id = str(journal["workspaceId"])
    journal_key = str(journal["journalKey"])
    current = connection.execute(
        "SELECT current_source_run_id FROM workspaces WHERE id = ?",
        (workspace_id,),
    ).fetchone()
    if current is None:
        return {"ok": False, "action": "blocked", "code": "workspace-missing", "journal": journal}
    current_source_run_id = str(current["current_source_run_id"] or "") or None
    target_source_run_id = str(journal.get("targetSourceRunId") or "") or None
    parent_source_run_id = str(journal.get("parentSourceRunId") or "") or None
    expected = journal.get("expectedManifest") if isinstance(journal.get("expectedManifest"), list) else []

    if str(journal.get("jobKey") or "").startswith("source-delete-v2:"):
        if str(journal.get("phase") or "") == PHASE_FINALIZED:
            return {"ok": True, "action": "unchanged", "journal": journal}
        table_keys = [str(value) for value in journal.get("tableKeys") or []]
        placeholders = ", ".join("?" for _ in table_keys)
        registry_rows = connection.execute(
            f"SELECT table_key FROM table_registry WHERE workspace_id = ? AND table_key IN ({placeholders})",
            (workspace_id, *table_keys),
        ).fetchall() if table_keys else []
        if registry_rows:
            restore_replica_manifest(duckdb_path, journal.get("rollbackManifest") or [])
            finalized = transition_activation(
                connection,
                workspace_id=workspace_id,
                journal_key=journal_key,
                phase=PHASE_FINALIZED,
                outcome="rolled_back",
                event_type="source_delete_reconciled_rollback",
                now_iso=now_iso,
            )
            return {"ok": True, "action": "rolled_back", "committed": False, "resumable": True, "journal": finalized}

        restore_replica_manifest(duckdb_path, expected)
        current_phase = str(journal.get("phase") or "")
        if current_phase == PHASE_PREPARED:
            journal = transition_activation(connection, workspace_id=workspace_id, journal_key=journal_key, phase=PHASE_COMMIT_STARTED, now_iso=now_iso)
            current_phase = PHASE_COMMIT_STARTED
        if current_phase == PHASE_COMMIT_STARTED:
            journal = transition_activation(connection, workspace_id=workspace_id, journal_key=journal_key, phase=PHASE_REPLICA_PUBLISHED, expected_manifest=expected, now_iso=now_iso)
            current_phase = PHASE_REPLICA_PUBLISHED
        if current_phase == PHASE_REPLICA_PUBLISHED:
            journal = transition_activation(connection, workspace_id=workspace_id, journal_key=journal_key, phase=PHASE_SOURCE_SELECTION_COMMITTED, expected_manifest=expected, now_iso=now_iso)
        candidates = [
            dict(candidate)
            for item in expected if isinstance(item, dict)
            for candidate in item.get("gcCandidates") or [] if isinstance(candidate, dict)
        ]
        recovery_catalogs = (
            list(protected_duckdb_paths)
            if protected_duckdb_paths is not None
            else recovery_point_duckdb_catalogs(configured_recovery_root(ROOT), workspace_id=workspace_id)
        )
        gc_result = collect_unreferenced_dataset_objects(
            connection,
            candidates=candidates,
            duckdb_paths=[duckdb_path, *recovery_catalogs],
        )
        finalized = transition_activation(
            connection,
            workspace_id=workspace_id,
            journal_key=journal_key,
            phase=PHASE_FINALIZED,
            outcome="committed",
            warning={"datasetObjectGc": gc_result},
            event_type="source_delete_reconciled_committed",
            now_iso=now_iso,
        )
        return {"ok": True, "action": "finalized", "committed": True, "datasetObjectGc": gc_result, "journal": finalized}

    if str(journal.get("jobKey") or "").startswith("layout-v2:"):
        table_keys = [str(value) for value in journal.get("tableKeys") or []]
        target_versions = {
            str(item.get("logicalTable") or ""): str(item.get("versionId") or "")
            for item in expected
            if isinstance(item, dict)
        }
        placeholders = ", ".join("?" for _ in table_keys)
        rows = connection.execute(
            f"SELECT table_key, physical_table, active_version_id FROM table_registry "
            f"WHERE workspace_id = ? AND table_key IN ({placeholders})",
            (workspace_id, *table_keys),
        ).fetchall() if table_keys else []
        pointers = {str(row["physical_table"]): str(row["active_version_id"] or "") for row in rows}
        target_active = bool(target_versions) and all(pointers.get(table) == version for table, version in target_versions.items())
        if target_active:
            if not replica_manifest_matches(duckdb_path, expected):
                return {"ok": False, "action": "blocked", "code": "committed-layout-catalog-mismatch", "journal": journal}
            current_phase = str(journal.get("phase") or "")
            if current_phase == PHASE_PREPARED:
                journal = transition_activation(connection, workspace_id=workspace_id, journal_key=journal_key, phase=PHASE_COMMIT_STARTED, now_iso=now_iso)
                current_phase = PHASE_COMMIT_STARTED
            if current_phase == PHASE_COMMIT_STARTED:
                journal = transition_activation(connection, workspace_id=workspace_id, journal_key=journal_key, phase=PHASE_REPLICA_PUBLISHED, expected_manifest=expected, now_iso=now_iso)
                current_phase = PHASE_REPLICA_PUBLISHED
            if current_phase == PHASE_REPLICA_PUBLISHED:
                journal = transition_activation(connection, workspace_id=workspace_id, journal_key=journal_key, phase=PHASE_SOURCE_SELECTION_COMMITTED, expected_manifest=expected, now_iso=now_iso)
            finalized = transition_activation(
                connection,
                workspace_id=workspace_id,
                journal_key=journal_key,
                phase=PHASE_FINALIZED,
                outcome="committed",
                event_type="layout_activation_reconciled_committed",
                now_iso=now_iso,
            )
            return {"ok": True, "action": "finalized", "committed": True, "journal": finalized}
        rollback_versions = {
            str(item.get("logicalTable") or ""): str(item.get("versionId") or "")
            for item in journal.get("rollbackManifest") or []
            if isinstance(item, dict) and item.get("present") is True
        }
        rollback_active = bool(rollback_versions) and all(
            pointers.get(table) == version for table, version in rollback_versions.items()
        )
        if not rollback_active:
            return {"ok": False, "action": "blocked", "code": "layout-version-pointer-diverged", "journal": journal}
        restore_replica_manifest(duckdb_path, journal.get("rollbackManifest") or [])
        finalized = transition_activation(
            connection,
            workspace_id=workspace_id,
            journal_key=journal_key,
            phase=PHASE_FINALIZED,
            outcome="rolled_back",
            event_type="layout_activation_reconciled_rollback",
            now_iso=now_iso,
        )
        return {"ok": True, "action": "rolled_back", "committed": False, "resumable": True, "journal": finalized}

    if journal.get("phase") == PHASE_FINALIZED:
        return {"ok": True, "action": "unchanged", "journal": journal}
    if target_source_run_id and current_source_run_id == target_source_run_id:
        if not replica_manifest_matches(duckdb_path, expected):
            return {
                "ok": False,
                "action": "blocked",
                "code": "committed-source-replica-mismatch",
                "journal": journal,
            }
        current_phase = str(journal.get("phase") or "")
        if current_phase == PHASE_PREPARED:
            journal = transition_activation(
                connection,
                workspace_id=workspace_id,
                journal_key=journal_key,
                phase=PHASE_COMMIT_STARTED,
                now_iso=now_iso,
            )
            current_phase = PHASE_COMMIT_STARTED
        if current_phase == PHASE_COMMIT_STARTED:
            journal = transition_activation(
                connection,
                workspace_id=workspace_id,
                journal_key=journal_key,
                phase=PHASE_REPLICA_PUBLISHED,
                expected_manifest=expected,
                now_iso=now_iso,
            )
            current_phase = PHASE_REPLICA_PUBLISHED
        if current_phase == PHASE_REPLICA_PUBLISHED:
            journal = transition_activation(
                connection,
                workspace_id=workspace_id,
                journal_key=journal_key,
                phase=PHASE_SOURCE_SELECTION_COMMITTED,
                target_source_run_id=target_source_run_id,
                expected_manifest=expected,
                now_iso=now_iso,
            )
        finalized = transition_activation(
            connection,
            workspace_id=workspace_id,
            journal_key=journal_key,
            phase=PHASE_FINALIZED,
            outcome="committed",
            event_type="activation_reconciled_committed",
            now_iso=now_iso,
        )
        return {"ok": True, "action": "finalized", "committed": True, "journal": finalized}
    if current_source_run_id == parent_source_run_id:
        restore_replica_manifest(duckdb_path, journal.get("rollbackManifest") or [])
        finalized = transition_activation(
            connection,
            workspace_id=workspace_id,
            journal_key=journal_key,
            phase=PHASE_FINALIZED,
            outcome="rolled_back",
            event_type="activation_reconciled_rollback",
            now_iso=now_iso,
        )
        return {"ok": True, "action": "rolled_back", "committed": False, "resumable": True, "journal": finalized}
    return {
        "ok": False,
        "action": "blocked",
        "code": "source-selection-diverged",
        "currentSourceRunId": current_source_run_id,
        "journal": journal,
    }
