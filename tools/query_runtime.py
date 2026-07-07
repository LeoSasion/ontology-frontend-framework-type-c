from __future__ import annotations

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


def cursor_rows(cursor: Any) -> list[dict[str, Any]]:
    columns = [column[0] for column in cursor.description or []]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def sqlite_rows(connection: Any, physical_table: str, columns: list[str]) -> list[list[Any]]:
    select_sql = ", ".join(quote_identifier(column) for column in columns)
    rows = connection.execute(f"SELECT {select_sql} FROM {quote_identifier(physical_table)}").fetchall()
    return [[row[column] for column in columns] for row in rows]


def sync_table_to_duckdb(sqlite_connection: Any, duck_connection: Any, physical_table: str, columns: list[str]) -> int:
    duck_connection.execute(f"DROP TABLE IF EXISTS {quote_identifier(physical_table)}")
    column_sql = ", ".join(f"{quote_identifier(column)} VARCHAR" for column in columns)
    duck_connection.execute(f"CREATE TABLE {quote_identifier(physical_table)} ({column_sql})")
    rows = sqlite_rows(sqlite_connection, physical_table, columns)
    if rows:
        placeholders = ", ".join("?" for _ in columns)
        insert_sql = f"INSERT INTO {quote_identifier(physical_table)} VALUES ({placeholders})"
        duck_connection.executemany(insert_sql, rows)
    return len(rows)


def compile_aggregate_sql(
    *,
    physical_table: str,
    group: str | None,
    measure: str,
    aggregation: str,
    limit: int,
) -> str:
    if aggregation not in SAFE_AGGREGATIONS:
        raise QueryRuntimeError(f"Unsupported aggregation: {aggregation}")
    if aggregation == "count":
        select_measure = "COUNT(*) AS value"
    elif aggregation == "count-distinct":
        select_measure = f"COUNT(DISTINCT {quote_identifier(measure)}) AS value"
    else:
        select_measure = f"{aggregation.upper()}({numeric_sql(quote_identifier(measure))}) AS value"
    if group:
        safe_limit = max(1, min(int(limit), 500))
        group_sql = quote_identifier(group)
        return (
            f"SELECT {group_sql} AS label, {select_measure} "
            f"FROM {quote_identifier(physical_table)} "
            f"GROUP BY {group_sql} "
            f"ORDER BY value DESC NULLS LAST "
            f"LIMIT {safe_limit}"
        )
    return f"SELECT {select_measure} FROM {quote_identifier(physical_table)}"


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
    )
    try:
        with duckdb.connect(str(duckdb_path)) as duck_connection:
            synced_rows = sync_table_to_duckdb(sqlite_connection, duck_connection, physical_table, columns)
            cursor = duck_connection.execute(sql)
            rows = cursor_rows(cursor)
    except Exception as exc:
        raise QueryRuntimeError(str(exc)) from exc
    return {
        "engine": "duckdb",
        "database": str(duckdb_path),
        "compiledSql": sql,
        "syncedRows": synced_rows,
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
) -> dict[str, Any]:
    if aggregation == "count":
        select_measure = "COUNT(*) AS value"
    elif aggregation == "count-distinct":
        select_measure = f"COUNT(DISTINCT {quote_identifier(measure)}) AS value"
    else:
        select_measure = (
            f"{aggregation.upper()}(CAST(NULLIF(REPLACE({quote_identifier(measure)}, ',', ''), '') AS REAL)) AS value"
        )
    if group:
        sql = (
            f"SELECT {quote_identifier(group)} AS label, {select_measure} "
            f"FROM {quote_identifier(physical_table)} "
            f"GROUP BY {quote_identifier(group)} "
            "ORDER BY value DESC LIMIT ?"
        )
        rows = sqlite_cursor_rows(sqlite_connection.execute(sql, (limit,)))
    else:
        sql = f"SELECT {select_measure} FROM {quote_identifier(physical_table)}"
        rows = sqlite_cursor_rows(sqlite_connection.execute(sql))
    return {
        "engine": "sqlite",
        "database": "metadata-store",
        "compiledSql": sql,
        "syncedRows": None,
        "rows": rows,
    }
