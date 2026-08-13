from __future__ import annotations

import time
from copy import deepcopy
from typing import Any, Callable, Iterator, Mapping, Sequence


class FakeSqlServerSession:
    def __init__(
        self,
        *,
        peer: str,
        catalog: Sequence[Mapping[str, Any]],
        rows: Mapping[str, Sequence[Mapping[str, Any]]],
        read_only: bool,
        fail_on_resource: str | None,
        delay_seconds: float,
    ) -> None:
        self._peer = peer
        self._catalog = deepcopy(list(catalog))
        self._rows = deepcopy(dict(rows))
        self._read_only = read_only
        self._fail_on_resource = fail_on_resource
        self._delay_seconds = delay_seconds
        self.closed = False
        self.operations: list[str] = []

    def peer_address(self) -> str:
        return self._peer

    def verify_read_only(self) -> Mapping[str, Any]:
        self.operations.append("verify_read_only")
        return {
            "readOnly": self._read_only,
            "evidence": ["application-intent-read-only", "credential-has-no-write-permissions"],
        }

    def _check(self, deadline: float, cancelled: Callable[[], bool]) -> None:
        if self._delay_seconds:
            time.sleep(self._delay_seconds)
        if cancelled():
            from sqlserver_snapshot_adapter_service import SqlServerAdapterError

            raise SqlServerAdapterError("SQLSERVER_OPERATION_CANCELED", "The fake SQL Server operation was canceled.")
        if time.monotonic() > deadline:
            from sqlserver_snapshot_adapter_service import SqlServerAdapterError

            raise SqlServerAdapterError("SQLSERVER_OPERATION_TIMEOUT", "The fake SQL Server operation timed out.")

    def discover_catalog(
        self,
        *,
        max_tables: int,
        max_columns_per_table: int,
        deadline: float,
        cancelled: Callable[[], bool],
    ) -> Sequence[Mapping[str, Any]]:
        self.operations.append("discover_catalog")
        self._check(deadline, cancelled)
        result = deepcopy(self._catalog[: max_tables + 1])
        for resource in result:
            resource["columns"] = list(resource.get("columns") or [])[: max_columns_per_table + 1]
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
        self.operations.append("preview_statistics")
        self._check(deadline, cancelled)
        resource_key = str(resource.get("resourceKey") or f"{resource.get('schemaName')}.{resource.get('name')}")
        sampled = list(self._rows.get(resource_key) or [])[:sample_rows]
        column_stats: list[dict[str, Any]] = []
        for name in columns:
            values = [row.get(name) for row in sampled]
            present = [value for value in values if value is not None]
            item: dict[str, Any] = {
                "name": name,
                "nullCount": len(values) - len(present),
                "distinctEstimate": len({repr(value) for value in present}),
            }
            if present:
                try:
                    item["min"] = min(present)
                    item["max"] = max(present)
                except TypeError:
                    pass
            column_stats.append(item)
        return {"sampledRows": len(sampled), "columns": column_stats}

    def describe_resources(
        self,
        resource_keys: Sequence[str],
        *,
        max_columns_per_table: int,
        deadline: float,
        cancelled: Callable[[], bool],
    ) -> Sequence[Mapping[str, Any]]:
        self.operations.append("describe_resources")
        self._check(deadline, cancelled)
        selected = set(resource_keys)
        result = []
        for resource in self._catalog:
            resource_key = f"{resource.get('schema')}.{resource.get('name')}"
            if resource_key in selected:
                item = deepcopy(resource)
                item["columns"] = list(item.get("columns") or [])[: max_columns_per_table + 1]
                result.append(item)
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
        del page_size
        self.operations.append("iter_snapshot")
        resource_key = str(selection.get("resourceKey") or "")
        if resource_key == self._fail_on_resource:
            raise RuntimeError("fake partial table failure")
        rows = list(self._rows.get(resource_key) or [])
        order_by = [str(item) for item in selection.get("orderBy") or []]
        rows.sort(key=lambda item: tuple((item.get(field) is None, item.get(field)) for field in order_by))
        watermark = selection.get("watermark")
        if isinstance(watermark, Mapping) and watermark.get("after") is not None:
            boundary = (watermark.get("after"), *list(watermark.get("afterTieBreakers") or []))
            fields = [str(watermark.get("column") or ""), *[str(item) for item in watermark.get("tieBreakers") or []]]
            rows = [row for row in rows if tuple(row.get(field) for field in fields) > boundary]
        columns = [str(item) for item in selection.get("columns") or []]
        for index, row in enumerate(rows):
            self._check(deadline, cancelled)
            if index >= max_rows:
                break
            yield {column: row.get(column) for column in columns}

    def close(self) -> None:
        self.closed = True


class FakeSqlServerDriver:
    name = "aibi-fake-sqlserver/v1"

    def __init__(
        self,
        *,
        peer: str,
        catalog: Sequence[Mapping[str, Any]],
        rows: Mapping[str, Sequence[Mapping[str, Any]]],
        installed: bool = True,
        read_only: bool = True,
        fail_on_resource: str | None = None,
        delay_seconds: float = 0.0,
    ) -> None:
        self.peer = peer
        self.catalog = deepcopy(list(catalog))
        self.rows = deepcopy(dict(rows))
        self.installed = installed
        self.read_only = read_only
        self.fail_on_resource = fail_on_resource
        self.delay_seconds = delay_seconds
        self.connect_count = 0
        self.last_session: FakeSqlServerSession | None = None
        self.connection_arguments: list[dict[str, Any]] = []

    def available(self) -> bool:
        return self.installed

    def connect(
        self,
        *,
        host: str,
        port: int,
        database: str,
        credential: Mapping[str, str],
        timeout_seconds: int,
        encryption: str,
    ) -> FakeSqlServerSession:
        self.connect_count += 1
        self.connection_arguments.append({
            "host": host,
            "port": port,
            "database": database,
            "credentialPresent": bool(credential.get("username") and credential.get("password")),
            "timeoutSeconds": timeout_seconds,
            "encryption": encryption,
        })
        session = FakeSqlServerSession(
            peer=self.peer,
            catalog=self.catalog,
            rows=self.rows,
            read_only=self.read_only,
            fail_on_resource=self.fail_on_resource,
            delay_seconds=self.delay_seconds,
        )
        self.last_session = session
        return session
