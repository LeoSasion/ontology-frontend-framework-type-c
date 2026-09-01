from __future__ import annotations

import hashlib
import json
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterator, Mapping, Sequence

from dataset_version_store import file_sha256, resolve_object_key


SAFE_AGGREGATIONS = {"count", "count-distinct", "sum", "avg", "min", "max"}
DATASET_MANIFEST_TABLE = "__aibi_replica_manifest"
DATASET_MANIFEST_VERSION = 2
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
_NUMERIC_TYPE = re.compile(r"^(?:U?(?:TINY|SMALL|BIG|HUGE)?INT(?:EGER)?|DECIMAL(?:\(\d+(?:,\d+)?\))?|NUMERIC(?:\(\d+(?:,\d+)?\))?|REAL|FLOAT|DOUBLE)$")
_TEMPORAL_TYPE = re.compile(r"^(?:DATE|TIME(?:STAMP)?(?: WITH TIME ZONE)?|INTERVAL)$")


class DuckDBUnavailable(RuntimeError):
    pass


class QueryRuntimeError(RuntimeError):
    pass


def _acquire_duckdb_reader(duckdb: Any, database_path: Path) -> tuple[Any, str | None]:
    """Open one reader whose lifetime cannot outlive the cross-process read boundary."""
    return duckdb.connect(str(database_path), read_only=True), None


def _release_duckdb_reader(connection: Any, cache_key: str | None, *, discard: bool = False) -> None:
    del cache_key, discard
    try:
        connection.close()
    except Exception:
        pass


def close_cached_duckdb_readers() -> int:
    """Protocol hook retained for writer barriers; request-scoped readers leave no cache."""
    return 0


@contextmanager
def _open_duckdb_snapshot(duckdb_path: Path) -> Iterator[Any]:
    """Open or lease one reader and isolate exactly one request transaction."""
    try:
        import duckdb  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local Python env
        raise DuckDBUnavailable("duckdb-unavailable") from exc
    if not duckdb_path.is_file():
        raise QueryRuntimeError("replica-database-missing")
    try:
        connection, cache_key = _acquire_duckdb_reader(duckdb, duckdb_path)
    except Exception as exc:
        raise QueryRuntimeError("replica-database-open-failed") from exc
    transaction_started = False
    discard = False
    try:
        try:
            connection.execute("BEGIN TRANSACTION")
            transaction_started = True
        except Exception as exc:
            discard = True
            raise QueryRuntimeError("replica-transaction-start-failed") from exc
        yield connection
    finally:
        if transaction_started:
            try:
                connection.execute("ROLLBACK")
            except Exception:
                discard = True
        _release_duckdb_reader(connection, cache_key, discard=discard)


def duckdb_status(database_path: Path) -> dict[str, Any]:
    try:
        import duckdb  # type: ignore  # noqa: F401

        dependency_available = True
    except Exception:  # pragma: no cover - depends on local Python env
        dependency_available = False
    database_available = database_path.is_file()
    available = dependency_available and database_available
    reason_code = None
    if not dependency_available:
        reason_code = "duckdb-unavailable"
    elif not database_available:
        reason_code = "replica-database-missing"
    return {
        "engine": "duckdb",
        "available": available,
        "database": "analysis-replica",
        "fallbackEngine": None,
        "queryAvailability": "current" if available else "blocked",
        "reasonCode": reason_code,
        "error": reason_code,
    }


@dataclass(frozen=True)
class ReplicaExpectation:
    logical_table: str
    source_version: str
    version_id: str
    content_fingerprint: str
    schema_fingerprint: str
    row_count: int
    object_hashes: tuple[str, ...] = ()


def replica_source_version(registry: Mapping[str, Any]) -> str:
    return (
        f"{registry['workspace_id']}:{registry['table_key']}:"
        f"{int(registry['data_version'] or 1)}:{int(registry['row_count'] or 0)}"
    )


def _mapping_value(registry: Mapping[str, Any], key: str) -> Any:
    try:
        return registry[key]
    except (KeyError, IndexError):
        return None


def _required_registry_value(registry: Mapping[str, Any], key: str) -> str:
    value = str(_mapping_value(registry, key) or "").strip()
    if not value:
        raise QueryRuntimeError(f"dataset-binding-missing:{key}")
    return value


def replica_expectation(registry: Mapping[str, Any]) -> ReplicaExpectation:
    raw_hashes = _mapping_value(registry, "object_hashes")
    if raw_hashes is None:
        raw_hashes = _mapping_value(registry, "object_hashes_json")
    if isinstance(raw_hashes, str):
        try:
            raw_hashes = json.loads(raw_hashes)
        except json.JSONDecodeError:
            raw_hashes = []
    object_hashes = tuple(str(value) for value in raw_hashes) if isinstance(raw_hashes, (list, tuple)) else ()
    return ReplicaExpectation(
        logical_table=str(registry["physical_table"]),
        source_version=replica_source_version(registry),
        version_id=_required_registry_value(registry, "active_version_id"),
        content_fingerprint=_required_registry_value(registry, "content_fingerprint"),
        schema_fingerprint=_required_registry_value(registry, "schema_fingerprint"),
        row_count=int(registry["row_count"] or 0),
        object_hashes=object_hashes,
    )


class ValidatedDuckDBQuery:
    """A read-only DuckDB connection whose requested replicas were fully validated."""

    def __init__(self, connection: Any, replicas: Sequence[dict[str, Any]]):
        self.connection = connection
        self.replicas = [dict(item) for item in replicas]

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> Any:
        try:
            return self.connection.execute(sql, list(params or []))
        except Exception as exc:
            raise QueryRuntimeError("replica-query-failed") from exc

    def __getattr__(self, name: str) -> Any:
        # Query compilers accept a DB-API-like object; keep the wrapper visible
        # while forwarding read-only cursor metadata such as fetchone/fetchall.
        return getattr(self.connection, name)

    def rows(self, sql: str, params: Sequence[Any] | None = None) -> list[dict[str, Any]]:
        return cursor_rows(self.execute(sql, params))

    def runtime(self, *, compiled_sql: str, params: Sequence[Any] | None = None) -> dict[str, Any]:
        safe_params = list(params or [])
        return {
            "engine": "duckdb",
            "database": "analysis-replica",
            "queryAvailability": "current",
            "reasonCode": None,
            "compiledSql": compiled_sql,
            "parameterCount": len(safe_params),
            "parameterFingerprint": hashlib.sha256(
                json.dumps(safe_params, ensure_ascii=False, default=str, separators=(",", ":")).encode("utf-8")
            ).hexdigest(),
            "replicas": [dict(item) for item in self.replicas],
        }


@contextmanager
def open_validated_duckdb_query(
    duckdb_path: Path,
    expectations: Sequence[ReplicaExpectation],
) -> Iterator[ValidatedDuckDBQuery]:
    """Use one request snapshot and fail closed unless every binding is current."""
    if not expectations:
        raise QueryRuntimeError("replica-expectations-required")
    with _open_duckdb_snapshot(duckdb_path) as duck_connection:
        try:
            replicas = validate_replica_bindings(duck_connection, expectations)
        except QueryRuntimeError:
            raise
        except Exception as exc:
            raise QueryRuntimeError("replica-validation-failed") from exc
        # Consumer exceptions describe compile/business safety failures and must
        # retain their own stable semantics; only reader open/validation is wrapped.
        yield ValidatedDuckDBQuery(duck_connection, replicas)


@contextmanager
def open_batch_validated_duckdb_query(
    duckdb_path: Path,
    expectations: Sequence[ReplicaExpectation],
) -> Iterator[tuple[ValidatedDuckDBQuery, dict[str, str]]]:
    """Open one read-only reader and validate a batch in one metadata query.

    Unlike the single-query context, a batch keeps validation failures scoped to
    the affected logical table so one stale widget cannot hide otherwise valid
    widgets in the same render pass.  The returned ``errors`` map contains the
    stable replica error code for each failed logical table.
    """
    if not expectations:
        raise QueryRuntimeError("replica-expectations-required")
    with _open_duckdb_snapshot(duckdb_path) as duck_connection:
        validated, errors = validate_replica_bindings_batch(duck_connection, expectations)
        yield ValidatedDuckDBQuery(duck_connection, validated), errors


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def numeric_sql(expression: str) -> str:
    return f"TRY_CAST(NULLIF(REPLACE(TRIM(CAST({expression} AS VARCHAR)), ',', ''), '') AS DOUBLE)"


def _is_numeric_type(data_type: str) -> bool:
    return bool(_NUMERIC_TYPE.fullmatch(str(data_type or "").strip().upper()))


def _is_temporal_type(data_type: str) -> bool:
    return bool(_TEMPORAL_TYPE.fullmatch(str(data_type or "").strip().upper()))


def _is_string_type(data_type: str) -> bool:
    normalized = str(data_type or "").strip().upper()
    return normalized in {"VARCHAR", "TEXT", "STRING", "CHAR", "BPCHAR"} or normalized.startswith(("VARCHAR(", "CHAR("))


def _typed_parameter(data_type: str) -> str:
    normalized = str(data_type or "").strip().upper()
    if (_is_numeric_type(normalized) or _is_temporal_type(normalized) or normalized == "BOOLEAN") and re.fullmatch(r"[A-Z0-9_(), ]+", normalized):
        return f"TRY_CAST(? AS {normalized})"
    return "?"


def compile_filter_sql(
    filters: list[dict[str, Any]] | None,
    *,
    dialect: str,
    field_types: Mapping[str, str] | None = None,
) -> tuple[str, list[Any]]:
    if dialect != "duckdb":
        raise QueryRuntimeError(f"Unsupported filter dialect: {dialect}")
    clauses: list[str] = []
    params: list[Any] = []
    for item in filters or []:
        field_name = str(item.get("field") or "")
        field = quote_identifier(field_name)
        operator = str(item.get("operator") or "")
        value = item.get("value")
        data_type = str((field_types or {}).get(field_name) or "").upper()
        parameter_sql = _typed_parameter(data_type)
        if not field or field == '""':
            raise QueryRuntimeError("Filter field is required")
        if operator == "equals":
            clauses.append(f"{field} = {parameter_sql}" if data_type else f"CAST({field} AS VARCHAR) = ?")
            params.append(value if data_type else str(value))
        elif operator == "not-equals":
            clauses.append(f"{field} <> {parameter_sql}" if data_type else f"CAST({field} AS VARCHAR) <> ?")
            params.append(value if data_type else str(value))
        elif operator == "contains":
            clauses.append(f"{field if _is_string_type(data_type) else f'CAST({field} AS VARCHAR)'} LIKE '%' || ? || '%'")
            params.append(str(value))
        elif operator == "not-contains":
            clauses.append(f"{field if _is_string_type(data_type) else f'CAST({field} AS VARCHAR)'} NOT LIKE '%' || ? || '%'")
            params.append(str(value))
        elif operator in {"gt", "gte", "lt", "lte"}:
            comparison = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[operator]
            if _is_numeric_type(data_type) or _is_temporal_type(data_type):
                expression = field
                placeholder = parameter_sql
            else:
                expression = numeric_sql(field)
                placeholder = "TRY_CAST(? AS DOUBLE)"
            clauses.append(f"{expression} {comparison} {placeholder}")
            params.append(value)
        elif operator in {"date-gte", "date-lt"}:
            comparison = ">=" if operator == "date-gte" else "<"
            expression = field if _is_temporal_type(data_type) else f"TRY_CAST({field} AS TIMESTAMP)"
            placeholder = parameter_sql if _is_temporal_type(data_type) else "TRY_CAST(? AS TIMESTAMP)"
            clauses.append(f"{expression} {comparison} {placeholder}")
            params.append(value)
        else:
            raise QueryRuntimeError(f"Unsupported filter operator: {operator}")
    return " AND ".join(clauses), params


def cursor_rows(cursor: Any) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description or []]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _relation_kind(duck_connection: Any, name: str) -> str | None:
    row = duck_connection.execute(
        "SELECT table_type FROM information_schema.tables WHERE table_schema = current_schema() AND table_name = ?",
        [name],
    ).fetchone()
    return str(row[0]) if row else None


def _validated_fingerprint(value: str, label: str) -> str:
    normalized = str(value or "").strip().lower()
    if not _FINGERPRINT.fullmatch(normalized):
        raise QueryRuntimeError(f"dataset-{label}-invalid")
    return normalized


def _validated_object_key(value: str) -> str:
    normalized = str(value or "").strip().replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or path.is_absolute()
        or re.match(r"^[A-Za-z]:", normalized)
        or ".." in path.parts
        or "." in path.parts
    ):
        raise QueryRuntimeError("dataset-object-key-invalid")
    return path.as_posix()


def _sql_string(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _ensure_manifest_v2(duck_connection: Any) -> None:
    metadata_kind = _relation_kind(duck_connection, "__aibi_schema_metadata")
    if metadata_kind is None:
        duck_connection.execute(
            "CREATE TABLE __aibi_schema_metadata (key VARCHAR PRIMARY KEY, value VARCHAR NOT NULL)"
        )
        duck_connection.execute(
            "INSERT INTO __aibi_schema_metadata(key, value) VALUES ('schema_version', ?)",
            [str(DATASET_MANIFEST_VERSION)],
        )
    elif metadata_kind != "BASE TABLE":
        raise QueryRuntimeError("duckdb-schema-metadata-invalid")
    else:
        version = duck_connection.execute(
            "SELECT value FROM __aibi_schema_metadata WHERE key = 'schema_version'"
        ).fetchone()
        if version is None or int(version[0]) != DATASET_MANIFEST_VERSION:
            raise QueryRuntimeError("duckdb-schema-v2-required")
    kind = _relation_kind(duck_connection, DATASET_MANIFEST_TABLE)
    if kind is None:
        duck_connection.execute(
            f"""
            CREATE TABLE {quote_identifier(DATASET_MANIFEST_TABLE)} (
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
        return
    if kind != "BASE TABLE":
        raise QueryRuntimeError("replica-manifest-v2-required")
    columns = {
        str(row[0])
        for row in duck_connection.execute(
            f"DESCRIBE {quote_identifier(DATASET_MANIFEST_TABLE)}"
        ).fetchall()
    }
    required = {
        "manifest_version",
        "logical_table",
        "source_version",
        "version_id",
        "object_keys_json",
        "object_paths_json",
        "object_hashes_json",
        "schema_fingerprint",
        "content_fingerprint",
        "row_count",
        "published_at",
    }
    if not required.issubset(columns):
        raise QueryRuntimeError("replica-manifest-v2-required")


def publish_dataset_view(
    duck_connection: Any,
    *,
    logical_table: str,
    source_version: str,
    version_id: str,
    object_keys: Sequence[str],
    object_paths: Sequence[Path],
    object_hashes: Sequence[str],
    schema_fingerprint: str,
    content_fingerprint: str,
    row_count: int,
    object_root: Path | None = None,
) -> dict[str, Any]:
    """Atomically publish one immutable typed-Parquet dataset as a logical view.

    `object_keys` are repository-independent CAS keys safe to persist. Absolute
    `object_paths` are private inputs supplied by the dataset store and are
    embedded only in DuckDB's local view definition.
    """
    logical_name = str(logical_table or "").strip()
    source = str(source_version or "").strip()
    version = str(version_id or "").strip()
    if not logical_name:
        raise QueryRuntimeError("dataset-logical-table-required")
    if not version:
        raise QueryRuntimeError("dataset-version-id-required")
    if not source:
        raise QueryRuntimeError("dataset-source-version-required")
    keys = [_validated_object_key(value) for value in object_keys]
    supplied_paths = [Path(value) for value in object_paths]
    hashes = [_validated_fingerprint(value, "object-hash") for value in object_hashes]
    if not keys or len(keys) != len(supplied_paths) or len(keys) != len(hashes):
        raise QueryRuntimeError("dataset-object-binding-invalid")
    paths: list[Path] = []
    for object_key, supplied_path, object_hash in zip(keys, supplied_paths, hashes, strict=True):
        try:
            canonical_path = resolve_object_key(object_key, root=object_root)
        except (PermissionError, ValueError) as exc:
            raise QueryRuntimeError("dataset-object-key-invalid") from exc
        if supplied_path.is_symlink() or supplied_path.resolve() != canonical_path:
            raise QueryRuntimeError("dataset-object-path-mismatch")
        if canonical_path.name != f"{object_hash}.parquet":
            raise QueryRuntimeError("dataset-object-key-hash-mismatch")
        if not canonical_path.is_file() or canonical_path.is_symlink():
            raise QueryRuntimeError("dataset-object-missing")
        if file_sha256(canonical_path) != object_hash:
            raise QueryRuntimeError("dataset-object-hash-mismatch")
        paths.append(canonical_path)
    content_hash = _validated_fingerprint(content_fingerprint, "content-fingerprint")
    schema_hash = _validated_fingerprint(schema_fingerprint, "schema-fingerprint")
    expected_rows = int(row_count)
    if expected_rows < 0:
        raise QueryRuntimeError("dataset-row-count-invalid")
    keys_json = json.dumps(keys, ensure_ascii=False, separators=(",", ":"))
    paths_json = json.dumps([path.as_posix() for path in paths], ensure_ascii=False, separators=(",", ":"))
    hashes_json = json.dumps(hashes, separators=(",", ":"))
    parquet_paths = ", ".join(_sql_string(path.as_posix()) for path in paths)
    source_sql = f"read_parquet([{parquet_paths}], union_by_name = true)"
    _ensure_manifest_v2(duck_connection)
    duck_connection.execute("BEGIN TRANSACTION")
    try:
        duck_connection.execute(
            f"CREATE OR REPLACE VIEW {quote_identifier(logical_name)} AS SELECT * FROM {source_sql}"
        )
        duck_connection.execute(
            f"""
            INSERT INTO {quote_identifier(DATASET_MANIFEST_TABLE)} (
              manifest_version, logical_table, source_version, version_id,
              object_keys_json, object_paths_json, object_hashes_json,
              schema_fingerprint, content_fingerprint, row_count, published_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
            ON CONFLICT (logical_table) DO UPDATE SET
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
                DATASET_MANIFEST_VERSION,
                logical_name,
                source,
                version,
                keys_json,
                paths_json,
                hashes_json,
                schema_hash,
                content_hash,
                expected_rows,
            ],
        )
        duck_connection.execute("COMMIT")
    except Exception:
        duck_connection.execute("ROLLBACK")
        raise
    return {
        "logicalTable": logical_name,
        "sourceVersion": source,
        "versionId": version,
        "objectHashes": hashes,
        "schemaFingerprint": schema_hash,
        "contentFingerprint": content_hash,
        "rowCount": expected_rows,
        "status": "published",
    }


def _replica_validation_error(row: dict[str, Any], expected: ReplicaExpectation) -> str | None:
    logical_name = str(expected.logical_table)
    if row.get("manifest_version") is None:
        return f"replica-binding-missing:{logical_name}"
    if int(row["manifest_version"]) != DATASET_MANIFEST_VERSION:
        return f"replica-manifest-version-stale:{logical_name}"
    if str(row.get("source_version") or "") != str(row["expected_source_version"]):
        return f"replica-source-version-stale:{logical_name}"
    if str(row.get("version_id") or "") != str(row["expected_version_id"]):
        return f"replica-version-stale:{logical_name}"
    if str(row.get("content_fingerprint") or "") != str(row["expected_content_fingerprint"]):
        return f"replica-content-fingerprint-drift:{logical_name}"
    if str(row.get("schema_fingerprint") or "") != str(row["expected_schema_fingerprint"]):
        return f"replica-schema-drift:{logical_name}"
    if int(row.get("row_count") or 0) != int(row["expected_row_count"]):
        return f"replica-row-count-drift:{logical_name}"
    if str(row.get("table_type") or "").upper() != "VIEW":
        return f"replica-view-not-published:{logical_name}"
    try:
        object_hashes = tuple(str(value) for value in json.loads(str(row["object_hashes_json"])))
    except (json.JSONDecodeError, TypeError):
        return f"replica-object-hash-drift:{logical_name}"
    if not object_hashes or any(not _FINGERPRINT.fullmatch(value) for value in object_hashes):
        return f"replica-object-hash-drift:{logical_name}"
    if expected.object_hashes and object_hashes != expected.object_hashes:
        return f"replica-object-hash-drift:{logical_name}"
    return None


def _validated_replica_from_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "logicalTable": str(row["logical_table"]),
        "sourceVersion": str(row["source_version"]),
        "versionId": str(row["version_id"]),
        "objectHashes": [str(value) for value in json.loads(str(row["object_hashes_json"]))],
        "schemaFingerprint": str(row["schema_fingerprint"]),
        "contentFingerprint": str(row["content_fingerprint"]),
        "rowCount": int(row["row_count"]),
        "status": "current",
    }


def validate_replica_bindings_batch(
    duck_connection: Any,
    expectations: Sequence[ReplicaExpectation],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Validate a set of datasets with one metadata query and scoped errors.

    The normal query path remains fail-closed through ``validate_replica_bindings``.
    Batch consumers use this variant to keep one stale dataset from suppressing
    independent widgets that are still bound to current immutable versions.
    """
    requested = list(expectations)
    if not requested:
        raise QueryRuntimeError("replica-expectations-required")
    by_table: dict[str, ReplicaExpectation] = {}
    errors: dict[str, str] = {}
    conflicts: set[str] = set()
    for item in requested:
        current = by_table.get(item.logical_table)
        if current is not None and current != item:
            conflicts.add(item.logical_table)
            errors[item.logical_table] = f"replica-expectation-conflict:{item.logical_table}"
            continue
        by_table[item.logical_table] = item
    unique = [item for key, item in by_table.items() if key not in conflicts]
    placeholders = ", ".join("(?, ?, ?, ?, ?, ?, ?)" for _ in unique)
    params: list[Any] = []
    for ordinal, item in enumerate(unique):
        params.extend([
            item.logical_table,
            item.source_version,
            item.version_id,
            item.content_fingerprint,
            item.schema_fingerprint,
            int(item.row_count),
            ordinal,
        ])
    if unique:
        sql = f"""
            WITH expected(
              logical_table, source_version, version_id, content_fingerprint,
              schema_fingerprint, row_count, ordinal
            ) AS (VALUES {placeholders})
            SELECT
              e.logical_table,
              e.source_version AS expected_source_version,
              e.version_id AS expected_version_id,
              e.content_fingerprint AS expected_content_fingerprint,
              e.schema_fingerprint AS expected_schema_fingerprint,
              e.row_count AS expected_row_count,
              m.manifest_version,
              m.source_version,
              m.version_id,
              m.object_hashes_json,
              m.schema_fingerprint,
              m.content_fingerprint,
              m.row_count,
              relation.table_type
            FROM expected e
            LEFT JOIN {quote_identifier(DATASET_MANIFEST_TABLE)} m
              ON m.logical_table = e.logical_table
            LEFT JOIN information_schema.tables relation
              ON relation.table_catalog = current_database()
             AND relation.table_schema = current_schema()
             AND relation.table_name = e.logical_table
            ORDER BY e.ordinal
        """
        try:
            rows = cursor_rows(duck_connection.execute(sql, params))
        except Exception as exc:
            message = str(exc).casefold()
            if DATASET_MANIFEST_TABLE.casefold() in message and (
                "does not exist" in message or "not found" in message
            ):
                raise QueryRuntimeError("replica-manifest-missing") from exc
            raise QueryRuntimeError("replica-manifest-v2-required") from exc
    else:
        rows = []
    validated: dict[str, dict[str, Any]] = {}
    for row in rows:
        logical_name = str(row["logical_table"])
        expected = by_table[logical_name]
        error = _replica_validation_error(row, expected)
        if error:
            errors[logical_name] = error
            continue
        validated[logical_name] = _validated_replica_from_row(row)
    return [dict(validated[item.logical_table]) for item in requested if item.logical_table in validated], errors


def validate_replica_bindings(
    duck_connection: Any,
    expectations: Sequence[ReplicaExpectation],
) -> list[dict[str, Any]]:
    """Validate every requested dataset with one metadata-only DuckDB query."""
    requested = list(expectations)
    validated, errors = validate_replica_bindings_batch(duck_connection, requested)
    for item in requested:
        error = errors.get(item.logical_table)
        if error:
            raise QueryRuntimeError(error)
    by_table = {str(item["logicalTable"]): item for item in validated}
    return [dict(by_table[item.logical_table]) for item in requested]


def validate_replica_binding(
    duck_connection: Any,
    *,
    logical_table: str,
    expected_source_version: str,
    expected_version_id: str,
    expected_content_fingerprint: str,
    expected_schema_fingerprint: str,
    expected_row_count: int,
    expected_object_hashes: Sequence[str] = (),
) -> dict[str, Any]:
    return validate_replica_bindings(duck_connection, [ReplicaExpectation(
        logical_table=str(logical_table),
        source_version=str(expected_source_version),
        version_id=str(expected_version_id),
        content_fingerprint=str(expected_content_fingerprint),
        schema_fingerprint=str(expected_schema_fingerprint),
        row_count=int(expected_row_count),
        object_hashes=tuple(str(value) for value in expected_object_hashes),
    )])[0]


def compile_aggregate_sql(
    *,
    physical_table: str,
    group: str | None,
    measure: str,
    aggregation: str,
    limit: int,
    filters: list[dict[str, Any]] | None = None,
    field_types: Mapping[str, str] | None = None,
) -> tuple[str, list[Any]]:
    if aggregation not in SAFE_AGGREGATIONS:
        raise QueryRuntimeError(f"Unsupported aggregation: {aggregation}")
    if aggregation == "count":
        select_measure = "COUNT(*) AS value"
    elif aggregation == "count-distinct":
        select_measure = f"COUNT(DISTINCT {quote_identifier(measure)}) AS value"
    else:
        measure_sql = quote_identifier(measure) if _is_numeric_type(str((field_types or {}).get(measure) or "")) else numeric_sql(quote_identifier(measure))
        select_measure = f"{aggregation.upper()}({measure_sql}) AS value"
    where_sql, params = compile_filter_sql(filters, dialect="duckdb", field_types=field_types)
    where_clause = f"WHERE {where_sql} " if where_sql else ""
    if group:
        safe_limit = max(1, min(int(limit), 500))
        group_sql = quote_identifier(group)
        return (
            f"SELECT {group_sql} AS label, {select_measure} "
            f"FROM {quote_identifier(physical_table)} "
            f"{where_clause}"
            f"GROUP BY {group_sql} "
            f"ORDER BY value DESC NULLS LAST "
            f"LIMIT {safe_limit}",
            params,
        )
    return f"SELECT {select_measure} FROM {quote_identifier(physical_table)} {where_clause}".strip(), params


def run_duckdb_aggregate_query(
    *,
    duckdb_path: Path,
    physical_table: str,
    group: str | None,
    measure: str,
    aggregation: str,
    limit: int,
    filters: list[dict[str, Any]] | None = None,
    source_version: str,
    version_id: str,
    content_fingerprint: str,
    schema_fingerprint: str,
    expected_row_count: int,
    field_types: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    sql, params = compile_aggregate_sql(
        physical_table=physical_table,
        group=group,
        measure=measure,
        aggregation=aggregation,
        limit=limit,
        filters=filters,
        field_types=field_types,
    )
    expectation = ReplicaExpectation(
        logical_table=physical_table,
        source_version=str(source_version),
        version_id=str(version_id),
        content_fingerprint=str(content_fingerprint),
        schema_fingerprint=str(schema_fingerprint),
        row_count=int(expected_row_count),
    )
    with open_validated_duckdb_query(duckdb_path, [expectation]) as query:
        rows = query.rows(sql, params)
        replica = query.replicas[0]
        runtime = query.runtime(compiled_sql=sql, params=params)
    return {
        **runtime,
        "sourceVersion": str(source_version),
        "versionId": str(version_id),
        "contentFingerprint": str(content_fingerprint),
        "schemaFingerprint": str(schema_fingerprint),
        "catalogStatus": replica["status"],
        "objectHashes": replica["objectHashes"],
        "datasetRowCount": replica["rowCount"],
        "rows": rows,
    }
