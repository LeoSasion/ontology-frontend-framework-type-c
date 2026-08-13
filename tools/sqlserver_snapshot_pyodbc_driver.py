from __future__ import annotations

import time
from typing import Any, Callable, Iterator, Mapping, Sequence

from sqlserver_snapshot_adapter_service import SqlServerAdapterError


def _identifier(value: Any) -> str:
    text = str(value or "")
    if not text or len(text) > 128 or any(ord(char) < 32 for char in text):
        raise SqlServerAdapterError("SQLSERVER_IDENTIFIER_INVALID", "SQL Server returned an invalid identifier.")
    return "[" + text.replace("]", "]]" ) + "]"


def _runtime_check(deadline: float, cancelled: Callable[[], bool]) -> None:
    if cancelled():
        raise SqlServerAdapterError("SQLSERVER_OPERATION_CANCELED", "The SQL Server operation was canceled.")
    if time.monotonic() > deadline:
        raise SqlServerAdapterError("SQLSERVER_OPERATION_TIMEOUT", "The SQL Server operation timed out.")


def _odbc_value(value: Any) -> str:
    return "{" + str(value).replace("}", "}}") + "}"


class PyodbcSqlServerSession:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def peer_address(self) -> str:
        row = self.connection.cursor().execute(
            "SELECT CONVERT(varchar(48), local_net_address) "
            "FROM sys.dm_exec_connections WHERE session_id = @@SPID"
        ).fetchone()
        if not row or not row[0]:
            raise SqlServerAdapterError(
                "SQLSERVER_PEER_ADDRESS_UNVERIFIED",
                "The SQL Server peer address could not be verified; snapshot access remains blocked.",
            )
        return str(row[0])

    def verify_read_only(self) -> Mapping[str, Any]:
        row = self.connection.cursor().execute(
            "SELECT "
            "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'SELECT'), "
            "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'INSERT'), "
            "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'UPDATE'), "
            "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'DELETE'), "
            "HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'EXECUTE')"
        ).fetchone()
        if not row:
            return {"readOnly": False, "evidence": []}
        read_only = bool(row[0]) and not any(bool(value) for value in row[1:])
        return {
            "readOnly": read_only,
            "evidence": ["select-permission-present", "insert-update-delete-execute-permissions-absent"] if read_only else [],
        }

    def discover_catalog(
        self,
        *,
        max_tables: int,
        max_columns_per_table: int,
        deadline: float,
        cancelled: Callable[[], bool],
    ) -> Sequence[Mapping[str, Any]]:
        _runtime_check(deadline, cancelled)
        cursor = self.connection.cursor()
        resources = cursor.execute(
            f"SELECT TOP {int(max_tables) + 1} s.name, o.name, "
            "CASE WHEN o.type = 'V' THEN 'view' ELSE 'table' END, "
            "COALESCE(SUM(CASE WHEN p.index_id IN (0,1) THEN p.rows ELSE 0 END), 0) "
            "FROM sys.objects o "
            "JOIN sys.schemas s ON s.schema_id = o.schema_id "
            "LEFT JOIN sys.partitions p ON p.object_id = o.object_id "
            "WHERE o.type IN ('U','V') AND o.is_ms_shipped = 0 "
            "GROUP BY s.name, o.name, o.type ORDER BY s.name, o.name"
        ).fetchall()
        result: list[dict[str, Any]] = []
        for schema_name, name, resource_type, row_estimate in resources:
            _runtime_check(deadline, cancelled)
            columns = cursor.execute(
                f"SELECT TOP {int(max_columns_per_table) + 1} c.name, t.name, c.is_nullable, c.column_id "
                "FROM sys.columns c JOIN sys.types t ON t.user_type_id = c.user_type_id "
                "JOIN sys.objects o ON o.object_id = c.object_id "
                "JOIN sys.schemas s ON s.schema_id = o.schema_id "
                "WHERE s.name = ? AND o.name = ? ORDER BY c.column_id",
                str(schema_name), str(name),
            ).fetchall()
            key_rows = cursor.execute(
                "SELECT i.name, ic.key_ordinal, c.name "
                "FROM sys.indexes i "
                "JOIN sys.objects o ON o.object_id = i.object_id "
                "JOIN sys.schemas s ON s.schema_id = o.schema_id "
                "JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id "
                "JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id "
                "WHERE s.name = ? AND o.name = ? AND i.is_unique = 1 AND ic.key_ordinal > 0 "
                "ORDER BY i.name, ic.key_ordinal",
                str(schema_name), str(name),
            ).fetchall()
            keys: dict[str, list[str]] = {}
            for key_name, _ordinal, column_name in key_rows:
                keys.setdefault(str(key_name), []).append(str(column_name))
            result.append({
                "schema": str(schema_name),
                "name": str(name),
                "type": str(resource_type),
                "rowEstimate": int(row_estimate or 0),
                "columns": [
                    {"name": str(column[0]), "dataType": str(column[1]), "nullable": bool(column[2]), "ordinal": int(column[3])}
                    for column in columns
                ],
                "keyCandidates": list(keys.values()),
            })
        return result

    def preview_statistics(
        self,
        resource: Mapping[str, Any],
        *,
        columns: Sequence[str],
        sample_rows: int,
        deadline: float,
        cancelled: Callable[[], bool],
    ) -> Mapping[str, Any]:
        _runtime_check(deadline, cancelled)
        table = f"{_identifier(resource.get('schemaName'))}.{_identifier(resource.get('name'))}"
        cursor = self.connection.cursor()
        sampled_count = cursor.execute(f"SELECT COUNT_BIG(*) FROM (SELECT TOP {int(sample_rows)} 1 AS n FROM {table}) q").fetchone()[0]
        type_by_name = {str(item.get("name")): str(item.get("dataType") or "").casefold() for item in resource.get("columns") or []}
        comparable = {
            "bigint", "date", "datetime", "datetime2", "datetimeoffset", "decimal", "int", "numeric",
            "real", "smallint", "smalldatetime", "time", "timestamp", "tinyint", "uniqueidentifier",
        }
        result: list[dict[str, Any]] = []
        for name in columns:
            _runtime_check(deadline, cancelled)
            quoted = _identifier(name)
            aggregate = f"COUNT_BIG(*) - COUNT({quoted}), COUNT_BIG(DISTINCT {quoted})"
            if type_by_name.get(name) in comparable:
                aggregate += f", MIN({quoted}), MAX({quoted})"
            row = cursor.execute(
                f"SELECT {aggregate} FROM (SELECT TOP {int(sample_rows)} {quoted} FROM {table}) q"
            ).fetchone()
            item: dict[str, Any] = {"name": name, "nullCount": int(row[0]), "distinctEstimate": int(row[1])}
            if len(row) > 2:
                item.update({"min": row[2], "max": row[3]})
            result.append(item)
        return {"sampledRows": int(sampled_count), "columns": result}

    def describe_resources(
        self,
        resource_keys: Sequence[str],
        *,
        max_columns_per_table: int,
        deadline: float,
        cancelled: Callable[[], bool],
    ) -> Sequence[Mapping[str, Any]]:
        cursor = self.connection.cursor()
        result: list[dict[str, Any]] = []
        for resource_key in resource_keys:
            _runtime_check(deadline, cancelled)
            schema_name, separator, name = str(resource_key).partition(".")
            if not separator:
                raise SqlServerAdapterError("SQLSERVER_SELECTION_INVALID", "The selected SQL Server resource is invalid.")
            resource_row = cursor.execute(
                "SELECT CASE WHEN o.type = 'V' THEN 'view' ELSE 'table' END, "
                "COALESCE(SUM(CASE WHEN p.index_id IN (0,1) THEN p.rows ELSE 0 END), 0) "
                "FROM sys.objects o JOIN sys.schemas s ON s.schema_id = o.schema_id "
                "LEFT JOIN sys.partitions p ON p.object_id = o.object_id "
                "WHERE o.type IN ('U','V') AND o.is_ms_shipped = 0 AND s.name = ? AND o.name = ? "
                "GROUP BY o.type",
                schema_name, name,
            ).fetchone()
            if not resource_row:
                continue
            columns = cursor.execute(
                f"SELECT TOP {int(max_columns_per_table) + 1} c.name, t.name, c.is_nullable, c.column_id "
                "FROM sys.columns c JOIN sys.types t ON t.user_type_id = c.user_type_id "
                "JOIN sys.objects o ON o.object_id = c.object_id "
                "JOIN sys.schemas s ON s.schema_id = o.schema_id "
                "WHERE s.name = ? AND o.name = ? ORDER BY c.column_id",
                schema_name, name,
            ).fetchall()
            key_rows = cursor.execute(
                "SELECT i.name, ic.key_ordinal, c.name FROM sys.indexes i "
                "JOIN sys.objects o ON o.object_id = i.object_id "
                "JOIN sys.schemas s ON s.schema_id = o.schema_id "
                "JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id "
                "JOIN sys.columns c ON c.object_id = ic.object_id AND c.column_id = ic.column_id "
                "WHERE s.name = ? AND o.name = ? AND i.is_unique = 1 AND ic.key_ordinal > 0 "
                "ORDER BY i.name, ic.key_ordinal",
                schema_name, name,
            ).fetchall()
            keys: dict[str, list[str]] = {}
            for key_name, _ordinal, column_name in key_rows:
                keys.setdefault(str(key_name), []).append(str(column_name))
            result.append({
                "schema": schema_name,
                "name": name,
                "type": str(resource_row[0]),
                "rowEstimate": int(resource_row[1] or 0),
                "columns": [
                    {"name": str(column[0]), "dataType": str(column[1]), "nullable": bool(column[2]), "ordinal": int(column[3])}
                    for column in columns
                ],
                "keyCandidates": list(keys.values()),
            })
        return result

    def iter_snapshot(
        self,
        selection: Mapping[str, Any],
        *,
        max_rows: int,
        page_size: int,
        deadline: float,
        cancelled: Callable[[], bool],
    ) -> Iterator[Mapping[str, Any]]:
        _runtime_check(deadline, cancelled)
        resource_key = str(selection.get("resourceKey") or "")
        schema_name, separator, name = resource_key.partition(".")
        if not separator:
            raise SqlServerAdapterError("SQLSERVER_SELECTION_INVALID", "The selected SQL Server resource is invalid.")
        columns = [str(item) for item in selection.get("columns") or []]
        order_by = [str(item) for item in selection.get("orderBy") or []]
        projection = ", ".join(_identifier(item) for item in columns)
        ordering = ", ".join(_identifier(item) for item in order_by)
        table = f"{_identifier(schema_name)}.{_identifier(name)}"
        where = ""
        params: list[Any] = []
        watermark = selection.get("watermark")
        if isinstance(watermark, Mapping) and watermark.get("after") is not None:
            watermark_column = _identifier(watermark.get("column"))
            tie_breakers = [str(item) for item in watermark.get("tieBreakers") or []]
            after_ties = list(watermark.get("afterTieBreakers") or [])
            clauses = [f"{watermark_column} > ?"]
            params.append(watermark.get("after"))
            equality = f"{watermark_column} = ?"
            params.append(watermark.get("after"))
            nested: list[str] = []
            for index, field in enumerate(tie_breakers):
                prefix = " AND ".join(f"{_identifier(tie_breakers[item])} = ?" for item in range(index))
                nested.append((prefix + " AND " if prefix else "") + f"{_identifier(field)} > ?")
                params.extend(after_ties[:index])
                params.append(after_ties[index])
            clauses.append(f"({equality} AND ({' OR '.join(nested)}))")
            where = " WHERE " + " OR ".join(clauses)
        cursor = self.connection.cursor()
        cursor.arraysize = max(1, int(page_size))
        cursor.execute(
            f"SELECT TOP {int(max_rows)} {projection} FROM {table}{where} ORDER BY {ordering}",
            *params,
        )
        names = [str(item[0]) for item in cursor.description]
        while True:
            _runtime_check(deadline, cancelled)
            batch = cursor.fetchmany(max(1, int(page_size)))
            if not batch:
                return
            for row in batch:
                yield dict(zip(names, row))

    def close(self) -> None:
        self.connection.close()


class PyodbcSqlServerDriver:
    name = "pyodbc-sqlserver/v1"

    def __init__(self) -> None:
        try:
            import pyodbc  # type: ignore
        except ImportError as error:
            raise SqlServerAdapterError(
                "SQLSERVER_DRIVER_UNAVAILABLE",
                "The optional pyodbc SQL Server driver is not installed; AIBI-C will not install it automatically.",
            ) from error
        self.pyodbc = pyodbc

    def available(self) -> bool:
        return True

    def connect(
        self,
        *,
        host: str,
        port: int,
        database: str,
        credential: Mapping[str, str],
        timeout_seconds: int,
        encryption: str,
    ) -> PyodbcSqlServerSession:
        drivers = [item for item in self.pyodbc.drivers() if "ODBC Driver" in item and "SQL Server" in item]
        if not drivers:
            raise SqlServerAdapterError("SQLSERVER_ODBC_DRIVER_UNAVAILABLE", "No supported Microsoft SQL Server ODBC driver is installed.")
        driver_name = sorted(drivers)[-1]
        connection_string = ";".join([
            f"DRIVER={{{driver_name}}}",
            f"SERVER={_odbc_value(f'tcp:{host},{int(port)}')}",
            f"DATABASE={_odbc_value(database)}",
            f"UID={_odbc_value(credential['username'])}",
            f"PWD={_odbc_value(credential['password'])}",
            "Encrypt=yes" if encryption == "required" else "Encrypt=no",
            "TrustServerCertificate=no",
            "ApplicationIntent=ReadOnly",
            "MARS_Connection=no",
        ])
        connection = self.pyodbc.connect(connection_string, timeout=int(timeout_seconds), autocommit=False)
        connection.timeout = int(timeout_seconds)
        return PyodbcSqlServerSession(connection)
