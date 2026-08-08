from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable


SAFE_AGGREGATIONS = {"count", "count-distinct", "sum", "avg", "min", "max"}


class DuckDBUnavailable(RuntimeError):
    pass


class QueryRuntimeError(RuntimeError):
    pass


def duckdb_status(database_path: Path) -> dict[str, Any]:
    try:
        import duckdb  # type: ignore  # noqa: F401

        available = True
        error = None
    except Exception as exc:  # pragma: no cover - depends on local Python env
        available = False
        error = str(exc)
    return {
        "engine": "duckdb",
        "available": available,
        "database": str(database_path),
        "fallbackEngine": None if available else "sqlite",
        "error": error,
    }


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def numeric_sql(expression: str) -> str:
    return f"TRY_CAST(NULLIF(REPLACE(TRIM(CAST({expression} AS VARCHAR)), ',', ''), '') AS DOUBLE)"


def sql_literal(value: Any) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def compile_filter_sql(filters: list[dict[str, Any]] | None, *, dialect: str) -> str:
    clauses: list[str] = []
    for item in filters or []:
        field = quote_identifier(str(item.get("field") or ""))
        operator = str(item.get("operator") or "")
        value = sql_literal(item.get("value"))
        if not field or field == '""':
            raise QueryRuntimeError("Filter field is required")
        if operator == "equals":
            clauses.append(f"CAST({field} AS VARCHAR) = {value}")
        elif operator == "not-equals":
            clauses.append(f"CAST({field} AS VARCHAR) <> {value}")
        elif operator == "contains":
            clauses.append(f"CAST({field} AS VARCHAR) LIKE '%' || {value} || '%'")
        elif operator == "not-contains":
            clauses.append(f"CAST({field} AS VARCHAR) NOT LIKE '%' || {value} || '%'")
        elif operator in {"gt", "gte", "lt", "lte"}:
            comparison = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[operator]
            if dialect == "duckdb":
                clauses.append(f"{numeric_sql(field)} {comparison} TRY_CAST({value} AS DOUBLE)")
            elif dialect == "sqlite":
                clauses.append(f"CAST(NULLIF(REPLACE({field}, ',', ''), '') AS REAL) {comparison} CAST({value} AS REAL)")
            else:
                raise QueryRuntimeError(f"Unsupported filter dialect: {dialect}")
        elif operator in {"date-gte", "date-lt"}:
            comparison = ">=" if operator == "date-gte" else "<"
            if dialect == "duckdb":
                clauses.append(f"TRY_CAST({field} AS TIMESTAMP) {comparison} TRY_CAST({value} AS TIMESTAMP)")
            elif dialect == "sqlite":
                clauses.append(f"datetime({field}) {comparison} datetime({value})")
            else:
                raise QueryRuntimeError(f"Unsupported filter dialect: {dialect}")
        else:
            raise QueryRuntimeError(f"Unsupported filter operator: {operator}")
    return " AND ".join(clauses)


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


def sync_table_to_duckdb(
    sqlite_connection: Any,
    duck_connection: Any,
    physical_table: str,
    columns: list[str],
    *,
    source_version: str,
) -> dict[str, Any]:
    _ensure_manifest(duck_connection)
    current = duck_connection.execute(
        "SELECT source_version, replica_table, row_count FROM __aibi_replica_manifest WHERE logical_table = ?",
        [physical_table],
    ).fetchone()
    if current and str(current[0]) == source_version and _relation_kind(duck_connection, physical_table) == "VIEW":
        return {
            "syncedRows": 0,
            "replicaStatus": "current",
            "replicaTable": str(current[1]),
            "rowCount": int(current[2] or 0),
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
) -> str:
    if aggregation not in SAFE_AGGREGATIONS:
        raise QueryRuntimeError(f"Unsupported aggregation: {aggregation}")
    if aggregation == "count":
        select_measure = "COUNT(*) AS value"
    elif aggregation == "count-distinct":
        select_measure = f"COUNT(DISTINCT {quote_identifier(measure)}) AS value"
    else:
        select_measure = f"{aggregation.upper()}({numeric_sql(quote_identifier(measure))}) AS value"
    where_sql = compile_filter_sql(filters, dialect="duckdb")
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
            f"LIMIT {safe_limit}"
        )
    return f"SELECT {select_measure} FROM {quote_identifier(physical_table)} {where_clause}".strip()


def run_duckdb_aggregate_query(
    *,
    sqlite_connection: Any,
    duckdb_path: Path,
    physical_table: str,
    columns: list[str],
    group: str | None,
    measure: str,
    aggregation: str,
    limit: int,
    filters: list[dict[str, Any]] | None = None,
    source_version: str | None = None,
) -> dict[str, Any]:
    try:
        import duckdb  # type: ignore
    except Exception as exc:  # pragma: no cover - depends on local Python env
        raise DuckDBUnavailable(str(exc)) from exc

    duckdb_path.parent.mkdir(parents=True, exist_ok=True)
    sql = compile_aggregate_sql(
        physical_table=physical_table,
        group=group,
        measure=measure,
        aggregation=aggregation,
        limit=limit,
        filters=filters,
    )
    try:
        with duckdb.connect(str(duckdb_path)) as duck_connection:
            version = str(source_version or f"legacy:{physical_table}:{len(columns)}")
            replica = sync_table_to_duckdb(
                sqlite_connection,
                duck_connection,
                physical_table,
                columns,
                source_version=version,
            )
            cursor = duck_connection.execute(sql)
            rows = cursor_rows(cursor)
    except Exception as exc:
        raise QueryRuntimeError(str(exc)) from exc
    return {
        "engine": "duckdb",
        "database": str(duckdb_path),
        "compiledSql": sql,
        "syncedRows": replica["syncedRows"],
        "sourceVersion": version,
        "replicaStatus": replica["replicaStatus"],
        "replicaTable": replica["replicaTable"],
        "replicaRowCount": replica["rowCount"],
        "rows": rows,
    }


def sqlite_cursor_rows(rows: Iterable[Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def run_sqlite_aggregate_query(
    *,
    sqlite_connection: Any,
    physical_table: str,
    group: str | None,
    measure: str,
    aggregation: str,
    limit: int,
    filters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if aggregation == "count":
        select_measure = "COUNT(*) AS value"
    elif aggregation == "count-distinct":
        select_measure = f"COUNT(DISTINCT {quote_identifier(measure)}) AS value"
    else:
        select_measure = (
            f"{aggregation.upper()}(CAST(NULLIF(REPLACE({quote_identifier(measure)}, ',', ''), '') AS REAL)) AS value"
        )
    where_sql = compile_filter_sql(filters, dialect="sqlite")
    where_clause = f"WHERE {where_sql} " if where_sql else ""
    if group:
        sql = (
            f"SELECT {quote_identifier(group)} AS label, {select_measure} "
            f"FROM {quote_identifier(physical_table)} "
            f"{where_clause}"
            f"GROUP BY {quote_identifier(group)} "
            "ORDER BY value DESC LIMIT ?"
        )
        rows = sqlite_cursor_rows(sqlite_connection.execute(sql, (limit,)))
    else:
        sql = f"SELECT {select_measure} FROM {quote_identifier(physical_table)} {where_clause}".strip()
        rows = sqlite_cursor_rows(sqlite_connection.execute(sql))
    return {
        "engine": "sqlite",
        "database": "metadata-store",
        "compiledSql": sql,
        "syncedRows": None,
        "rows": rows,
    }
