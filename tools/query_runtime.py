from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence


SAFE_AGGREGATIONS = {"count", "count-distinct", "sum", "avg", "min", "max"}


class DuckDBUnavailable(RuntimeError):
    pass


class QueryRuntimeError(RuntimeError):
    pass


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
    row_count: int


def replica_source_version(registry: Mapping[str, Any]) -> str:
    return (
        f"{registry['workspace_id']}:{registry['table_key']}:"
        f"{int(registry['data_version'] or 1)}:{int(registry['row_count'] or 0)}"
    )


def replica_expectation(registry: Mapping[str, Any]) -> ReplicaExpectation:
    return ReplicaExpectation(
        logical_table=str(registry["physical_table"]),
        source_version=replica_source_version(registry),
        row_count=int(registry["row_count"] or 0),
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
    """Open one read-only reader and fail closed unless every binding is current."""
    try:
        import duckdb  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local Python env
        raise DuckDBUnavailable("duckdb-unavailable") from exc
    if not duckdb_path.is_file():
        raise QueryRuntimeError("replica-database-missing")
    if not expectations:
        raise QueryRuntimeError("replica-expectations-required")
    try:
        duck_connection = duckdb.connect(str(duckdb_path), read_only=True)
    except Exception as exc:
        raise QueryRuntimeError("replica-database-open-failed") from exc
    try:
        try:
            replicas = [
                validate_replica_binding(
                    duck_connection,
                    logical_table=item.logical_table,
                    expected_source_version=item.source_version,
                    expected_row_count=item.row_count,
                )
                for item in expectations
            ]
        except QueryRuntimeError:
            raise
        except Exception as exc:
            raise QueryRuntimeError("replica-validation-failed") from exc
        # Consumer exceptions describe compile/business safety failures and must
        # retain their own stable semantics; only reader open/validation is wrapped.
        yield ValidatedDuckDBQuery(duck_connection, replicas)
    finally:
        duck_connection.close()


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def numeric_sql(expression: str) -> str:
    return f"TRY_CAST(NULLIF(REPLACE(TRIM(CAST({expression} AS VARCHAR)), ',', ''), '') AS DOUBLE)"


def compile_filter_sql(filters: list[dict[str, Any]] | None, *, dialect: str) -> tuple[str, list[Any]]:
    if dialect != "duckdb":
        raise QueryRuntimeError(f"Unsupported filter dialect: {dialect}")
    clauses: list[str] = []
    params: list[Any] = []
    for item in filters or []:
        field = quote_identifier(str(item.get("field") or ""))
        operator = str(item.get("operator") or "")
        value = item.get("value")
        if not field or field == '""':
            raise QueryRuntimeError("Filter field is required")
        if operator == "equals":
            clauses.append(f"CAST({field} AS VARCHAR) = ?")
            params.append(str(value))
        elif operator == "not-equals":
            clauses.append(f"CAST({field} AS VARCHAR) <> ?")
            params.append(str(value))
        elif operator == "contains":
            clauses.append(f"CAST({field} AS VARCHAR) LIKE '%' || ? || '%'")
            params.append(str(value))
        elif operator == "not-contains":
            clauses.append(f"CAST({field} AS VARCHAR) NOT LIKE '%' || ? || '%'")
            params.append(str(value))
        elif operator in {"gt", "gte", "lt", "lte"}:
            comparison = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[operator]
            clauses.append(f"{numeric_sql(field)} {comparison} TRY_CAST(? AS DOUBLE)")
            params.append(value)
        elif operator in {"date-gte", "date-lt"}:
            comparison = ">=" if operator == "date-gte" else "<"
            clauses.append(f"TRY_CAST({field} AS TIMESTAMP) {comparison} TRY_CAST(? AS TIMESTAMP)")
            params.append(value)
        else:
            raise QueryRuntimeError(f"Unsupported filter operator: {operator}")
    return " AND ".join(clauses), params


def cursor_rows(cursor: Any) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description or []]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def sqlite_rows(connection: Any, physical_table: str, columns: list[str]) -> list[list[Any]]:
    select_sql = ", ".join(quote_identifier(column) for column in columns)
    rows = connection.execute(f"SELECT {select_sql} FROM {quote_identifier(physical_table)}").fetchall()
    return [[row[column] for column in columns] for row in rows]


def replica_table_name(physical_table: str, source_version: str) -> str:
    digest = hashlib.sha256(f"{physical_table}:{source_version}".encode("utf-8")).hexdigest()[:16]
    return f"__aibi_replica_{digest}"


def _relation_kind(duck_connection: Any, name: str) -> str | None:
    row = duck_connection.execute(
        "SELECT table_type FROM information_schema.tables WHERE table_schema = current_schema() AND table_name = ?",
        [name],
    ).fetchone()
    return str(row[0]) if row else None


def _ensure_manifest(duck_connection: Any) -> None:
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


def validate_replica_binding(
    duck_connection: Any,
    *,
    logical_table: str,
    expected_source_version: str,
    expected_row_count: int | None = None,
) -> dict[str, Any]:
    """Fail closed when a published replica is missing, stale, or only half switched."""
    if _relation_kind(duck_connection, "__aibi_replica_manifest") is None:
        raise QueryRuntimeError("replica-manifest-missing")
    row = duck_connection.execute(
        "SELECT source_version, replica_table, row_count FROM __aibi_replica_manifest WHERE logical_table = ?",
        [logical_table],
    ).fetchone()
    if row is None:
        raise QueryRuntimeError(f"replica-binding-missing:{logical_table}")
    source_version = str(row[0])
    replica_table = str(row[1])
    row_count = int(row[2] or 0)
    if source_version != str(expected_source_version):
        raise QueryRuntimeError(f"replica-version-stale:{logical_table}")
    if expected_row_count is not None and row_count != int(expected_row_count):
        raise QueryRuntimeError(f"replica-row-count-drift:{logical_table}")
    if _relation_kind(duck_connection, replica_table) != "BASE TABLE":
        raise QueryRuntimeError(f"replica-table-missing:{logical_table}")
    if _relation_kind(duck_connection, logical_table) != "VIEW":
        raise QueryRuntimeError(f"replica-view-not-published:{logical_table}")
    physical_count = int(duck_connection.execute(
        f"SELECT COUNT(*) FROM {quote_identifier(replica_table)}"
    ).fetchone()[0] or 0)
    view_count = int(duck_connection.execute(
        f"SELECT COUNT(*) FROM {quote_identifier(logical_table)}"
    ).fetchone()[0] or 0)
    if physical_count != row_count or view_count != row_count:
        raise QueryRuntimeError(f"replica-content-drift:{logical_table}")
    return {
        "logicalTable": logical_table,
        "sourceVersion": source_version,
        "replicaTable": replica_table,
        "rowCount": row_count,
        "status": "current",
    }


def sync_table_to_duckdb(
    sqlite_connection: Any,
    duck_connection: Any,
    physical_table: str,
    columns: list[str],
    *,
    source_version: str,
    cleanup_stale: bool = True,
) -> dict[str, Any]:
    _ensure_manifest(duck_connection)
    current = duck_connection.execute(
        "SELECT source_version, replica_table, row_count FROM __aibi_replica_manifest WHERE logical_table = ?",
        [physical_table],
    ).fetchone()
    if current and str(current[0]) == source_version and _relation_kind(duck_connection, physical_table) == "VIEW":
        validated = validate_replica_binding(
            duck_connection,
            logical_table=physical_table,
            expected_source_version=source_version,
            expected_row_count=int(current[2] or 0),
        )
        return {
            "syncedRows": 0,
            "replicaStatus": "current",
            "replicaTable": str(validated["replicaTable"]),
            "rowCount": int(validated["rowCount"]),
        }

    replica_table = replica_table_name(physical_table, source_version)
    duck_connection.execute(f"DROP TABLE IF EXISTS {quote_identifier(replica_table)}")
    column_sql = ", ".join(f"{quote_identifier(column)} VARCHAR" for column in columns)
    duck_connection.execute(f"CREATE TABLE {quote_identifier(replica_table)} ({column_sql})")
    rows = sqlite_rows(sqlite_connection, physical_table, columns)
    if rows:
        placeholders = ", ".join("?" for _ in columns)
        insert_sql = f"INSERT INTO {quote_identifier(replica_table)} VALUES ({placeholders})"
        duck_connection.executemany(insert_sql, rows)
    duck_connection.execute("BEGIN TRANSACTION")
    try:
        relation_kind = _relation_kind(duck_connection, physical_table)
        if relation_kind == "VIEW":
            duck_connection.execute(f"DROP VIEW {quote_identifier(physical_table)}")
        elif relation_kind:
            duck_connection.execute(f"DROP TABLE {quote_identifier(physical_table)}")
        duck_connection.execute(
            f"CREATE VIEW {quote_identifier(physical_table)} AS SELECT * FROM {quote_identifier(replica_table)}"
        )
        duck_connection.execute(
            """
            INSERT INTO __aibi_replica_manifest (logical_table, source_version, replica_table, row_count, published_at)
            VALUES (?, ?, ?, ?, current_timestamp)
            ON CONFLICT (logical_table) DO UPDATE SET
              source_version = excluded.source_version,
              replica_table = excluded.replica_table,
              row_count = excluded.row_count,
              published_at = excluded.published_at
            """,
            [physical_table, source_version, replica_table, len(rows)],
        )
        duck_connection.execute("COMMIT")
    except Exception:
        duck_connection.execute("ROLLBACK")
        raise
    validate_replica_binding(
        duck_connection,
        logical_table=physical_table,
        expected_source_version=source_version,
        expected_row_count=len(rows),
    )
    if cleanup_stale:
        stale_replicas = duck_connection.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema() AND table_name LIKE '__aibi_replica_%' AND table_name NOT IN (?, '__aibi_replica_manifest')",
            [replica_table],
        ).fetchall()
        active_replicas = {
            str(row[0])
            for row in duck_connection.execute("SELECT replica_table FROM __aibi_replica_manifest").fetchall()
        }
        for stale in stale_replicas:
            stale_name = str(stale[0])
            if stale_name not in active_replicas:
                duck_connection.execute(f"DROP TABLE IF EXISTS {quote_identifier(stale_name)}")
    return {
        "syncedRows": len(rows),
        "replicaStatus": "published",
        "replicaTable": replica_table,
        "rowCount": len(rows),
    }


def compile_aggregate_sql(
    *,
    physical_table: str,
    group: str | None,
    measure: str,
    aggregation: str,
    limit: int,
    filters: list[dict[str, Any]] | None = None,
) -> tuple[str, list[Any]]:
    if aggregation not in SAFE_AGGREGATIONS:
        raise QueryRuntimeError(f"Unsupported aggregation: {aggregation}")
    if aggregation == "count":
        select_measure = "COUNT(*) AS value"
    elif aggregation == "count-distinct":
        select_measure = f"COUNT(DISTINCT {quote_identifier(measure)}) AS value"
    else:
        select_measure = f"{aggregation.upper()}({numeric_sql(quote_identifier(measure))}) AS value"
    where_sql, params = compile_filter_sql(filters, dialect="duckdb")
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
    expected_row_count: int,
) -> dict[str, Any]:
    sql, params = compile_aggregate_sql(
        physical_table=physical_table,
        group=group,
        measure=measure,
        aggregation=aggregation,
        limit=limit,
        filters=filters,
    )
    expectation = ReplicaExpectation(
        logical_table=physical_table,
        source_version=str(source_version),
        row_count=int(expected_row_count),
    )
    with open_validated_duckdb_query(duckdb_path, [expectation]) as query:
        rows = query.rows(sql, params)
        replica = query.replicas[0]
        runtime = query.runtime(compiled_sql=sql, params=params)
    return {
        **runtime,
        "syncedRows": 0,
        "sourceVersion": str(source_version),
        "replicaStatus": replica["status"],
        "replicaTable": replica["replicaTable"],
        "replicaRowCount": replica["rowCount"],
        "rows": rows,
    }
