from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Callable, Iterable


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


def ensure_activation_journal_schema(connection: sqlite3.Connection) -> None:
    """Install additive W1/W3 storage without creating a second job center."""
    job_columns = {
        str(row[1]) for row in connection.execute("PRAGMA table_info(analysis_jobs)").fetchall()
    }
    if "request_key" not in job_columns:
        connection.execute("ALTER TABLE analysis_jobs ADD COLUMN request_key TEXT NOT NULL DEFAULT ''")
    connection.executescript(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_jobs_workspace_kind_request
          ON analysis_jobs(workspace_id, kind, request_key)
          WHERE request_key <> '';

        CREATE TABLE IF NOT EXISTS source_activation_journals (
          journal_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          job_key TEXT NOT NULL,
          phase TEXT NOT NULL,
          plan_fingerprint TEXT NOT NULL,
          parent_source_run_id TEXT,
          target_source_run_id TEXT,
          table_keys_json TEXT NOT NULL,
          expected_manifest_json TEXT NOT NULL,
          rollback_manifest_json TEXT NOT NULL,
          outcome TEXT NOT NULL,
          warning_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          finalized_at TEXT,
          PRIMARY KEY(workspace_id, journal_key)
        );
        CREATE INDEX IF NOT EXISTS idx_source_activation_workspace_phase
          ON source_activation_journals(workspace_id, phase, updated_at);
        CREATE INDEX IF NOT EXISTS idx_source_activation_workspace_job
          ON source_activation_journals(workspace_id, job_key, created_at);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_source_activation_one_active_workspace
          ON source_activation_journals(workspace_id)
          WHERE phase <> 'finalized';

        CREATE TABLE IF NOT EXISTS import_workspace_leases (
          workspace_id TEXT PRIMARY KEY,
          job_key TEXT NOT NULL UNIQUE,
          lease_token TEXT NOT NULL DEFAULT '',
          lease_epoch INTEGER NOT NULL DEFAULT 0,
          active INTEGER NOT NULL DEFAULT 1,
          acquired_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          released_at TEXT
        );

        CREATE TABLE IF NOT EXISTS source_activation_journal_events (
          event_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
          workspace_id TEXT NOT NULL,
          journal_key TEXT NOT NULL,
          job_key TEXT NOT NULL,
          phase TEXT NOT NULL,
          event_type TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_source_activation_events_journal
          ON source_activation_journal_events(workspace_id, journal_key, event_sequence);
        """
    )
    lease_columns = {
        str(row[1]) for row in connection.execute("PRAGMA table_info(import_workspace_leases)").fetchall()
    }
    if "lease_token" not in lease_columns:
        connection.execute("ALTER TABLE import_workspace_leases ADD COLUMN lease_token TEXT NOT NULL DEFAULT ''")
    if "lease_epoch" not in lease_columns:
        connection.execute("ALTER TABLE import_workspace_leases ADD COLUMN lease_epoch INTEGER NOT NULL DEFAULT 0")
    if "active" not in lease_columns:
        connection.execute("ALTER TABLE import_workspace_leases ADD COLUMN active INTEGER NOT NULL DEFAULT 1")
    if "released_at" not in lease_columns:
        connection.execute("ALTER TABLE import_workspace_leases ADD COLUMN released_at TEXT")


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
    ensure_activation_journal_schema(connection)
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
    ensure_activation_journal_schema(connection)
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
    ensure_activation_journal_schema(connection)
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
          logical_table VARCHAR PRIMARY KEY,
          source_version VARCHAR NOT NULL,
          replica_table VARCHAR NOT NULL,
          row_count BIGINT NOT NULL,
          published_at TIMESTAMP DEFAULT current_timestamp
        )
        """
    )


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
        for table in tables:
            row = connection.execute(
                "SELECT source_version, replica_table, row_count FROM __aibi_replica_manifest WHERE logical_table = ?",
                [table],
            ).fetchone() if manifest_exists else None
            snapshots.append({
                "logicalTable": table,
                "present": row is not None,
                "sourceVersion": str(row[0]) if row else None,
                "replicaTable": str(row[1]) if row else None,
                "rowCount": int(row[2]) if row else None,
                "relationKind": _relation_kind(connection, table),
            })
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
        if _relation_kind(connection, "__aibi_replica_manifest") is None:
            return False
        for item in expected:
            logical_table = str(item.get("logicalTable") or "")
            row = connection.execute(
                "SELECT source_version, replica_table, row_count FROM __aibi_replica_manifest WHERE logical_table = ?",
                [logical_table],
            ).fetchone()
            if not row:
                return False
            if str(row[0]) != str(item.get("sourceVersion") or ""):
                return False
            if str(row[1]) != str(item.get("replicaTable") or ""):
                return False
            if int(row[2]) != int(item.get("rowCount") or 0):
                return False
            if _relation_kind(connection, logical_table) != "VIEW":
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
                    connection.execute(f"DROP TABLE {_quote_identifier(logical_table)}")
                if item.get("present") is True:
                    replica_table = str(item.get("replicaTable") or "")
                    if not replica_table or _relation_kind(connection, replica_table) is None:
                        raise RuntimeError(f"Rollback replica is missing for {logical_table}.")
                    connection.execute(
                        f"CREATE VIEW {_quote_identifier(logical_table)} AS SELECT * FROM {_quote_identifier(replica_table)}"
                    )
                    connection.execute(
                        """
                        INSERT INTO __aibi_replica_manifest(logical_table, source_version, replica_table, row_count, published_at)
                        VALUES(?, ?, ?, ?, current_timestamp)
                        ON CONFLICT(logical_table) DO UPDATE SET
                          source_version = excluded.source_version,
                          replica_table = excluded.replica_table,
                          row_count = excluded.row_count,
                          published_at = excluded.published_at
                        """,
                        [
                            logical_table,
                            str(item.get("sourceVersion") or ""),
                            replica_table,
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
    removed: list[str] = []
    with duckdb.connect(str(duckdb_path)) as connection:
        if _relation_kind(connection, "__aibi_replica_manifest") is None:
            return []
        active = {
            str(row[0])
            for row in connection.execute("SELECT replica_table FROM __aibi_replica_manifest").fetchall()
        }
        candidates = connection.execute(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = current_schema()
              AND table_name LIKE '__aibi_replica_%'
              AND table_name <> '__aibi_replica_manifest'
            """
        ).fetchall()
        for row in candidates:
            table = str(row[0])
            if table in active:
                continue
            connection.execute(f"DROP TABLE IF EXISTS {_quote_identifier(table)}")
            removed.append(table)
    return sorted(removed)


def reconcile_activation(
    connection: sqlite3.Connection,
    *,
    journal: dict[str, Any],
    duckdb_path: Path,
    now_iso: Callable[[], str],
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
