from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from typing import Any, Callable

from bi_cli_core import DUCKDB_PATH, slug
from dataset_version_store import schema_field_types
from query_runtime import ValidatedDuckDBQuery, cursor_rows, open_validated_duckdb_query, replica_expectation
from saved_view_query_service import parse_query_filter


def parse_json_object(value: Any, default: Any | None = None) -> Any:
    if value in (None, ""):
        return {} if default is None else default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return {} if default is None else default


def json_contains_string(value: Any, needle: str) -> bool:
    if not needle:
        return False
    if isinstance(value, str):
        return value == needle or f"[{needle}]" in value
    if isinstance(value, dict):
        return any(json_contains_string(item, needle) for item in value.values())
    if isinstance(value, list):
        return any(json_contains_string(item, needle) for item in value)
    return False


def metric_key_for(table_key: str, label: str, measure: str, aggregation: str) -> str:
    return slug(f"{table_key}_{label}_{measure or 'rows'}_{aggregation}")[:72]


def formula_key_for(table_key: str, name: str, mode: str) -> str:
    base = slug(f"{table_key}_{name}_{mode}_formula")
    name_hash = hashlib.sha1(name.encode("utf-8")).hexdigest()[:8]
    generic_base = slug(f"{table_key}_{mode}_formula")
    if not base or base == generic_base:
        return f"{slug(table_key)[:40]}_{name_hash}_{mode}_formula"[:72]
    return base[:72]


def metric_row_to_payload(row: sqlite3.Row, table_name: str | None = None) -> dict[str, Any]:
    row_data = dict(row)
    return {
        "metricKey": row_data["metric_key"],
        "label": row_data["label"],
        "tableKey": row_data["table_key"],
        "tableName": table_name or row_data["table_key"],
        "measure": row_data["measure"],
        "aggregation": row_data["aggregation"],
        "dimension": row_data["dimension"],
        "timeField": row_data["time_field"],
        "valueFormat": row_data["value_format"],
        "filters": parse_json_object(row_data.get("filters_json"), []),
        "description": row_data.get("description", ""),
        "source": row_data.get("source", "auto"),
        "enabled": bool(row_data.get("enabled", 1)),
        "formulaText": row_data.get("formula_text", ""),
        "formulaAst": parse_json_object(row_data.get("formula_ast_json"), {}),
        "dependencies": parse_json_object(row_data.get("dependencies_json"), []),
        "metricType": row_data.get("metric_type", "basic"),
        "createdAt": row_data["created_at"],
        "updatedAt": row_data.get("updated_at", ""),
    }


def calculated_field_row_to_payload(row: sqlite3.Row) -> dict[str, Any]:
    row_data = dict(row)
    return {
        "fieldKey": row_data["field_key"],
        "tableKey": row_data["table_key"],
        "name": row_data["name"],
        "mode": row_data["mode"],
        "formulaText": row_data["formula_text"],
        "formulaAst": parse_json_object(row_data["formula_ast_json"], {}),
        "dependencies": parse_json_object(row_data["dependencies_json"], []),
        "valueFormat": row_data["value_format"],
        "description": row_data["description"],
        "source": row_data["source"],
        "enabled": bool(row_data["enabled"]),
        "createdAt": row_data["created_at"],
        "updatedAt": row_data["updated_at"],
    }


def metric_filters_from_cli(raw_filters: list[str]) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = []
    for raw in raw_filters:
        filters.append(parse_query_filter(raw))
    return filters


def upsert_metric_definition(
    connection: sqlite3.Connection,
    metric: dict[str, Any],
    *,
    resolve_table_registry: Callable[[sqlite3.Connection, str], sqlite3.Row],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
    safe_aggregations: set[str],
) -> dict[str, Any]:
    registry = resolve_table_registry(connection, str(metric["tableKey"]))
    columns = table_columns(connection, registry["physical_table"])
    measure = str(metric.get("measure") or "*")
    aggregation = str(metric.get("aggregation") or "count")
    if aggregation not in safe_aggregations:
        raise ValueError(f"Unsupported aggregation: {aggregation}")
    if measure != "*" and measure not in columns:
        raise ValueError(f"Unknown metric measure: {measure}")
    for optional in ("dimension", "timeField"):
        value = str(metric.get(optional) or "")
        if value and value not in columns:
            raise ValueError(f"Unknown metric field: {value}")
    metric_key = str(metric.get("metricKey") or metric_key_for(registry["table_key"], str(metric.get("label") or "metric"), measure, aggregation))
    workspace_id = active_workspace_id(connection)
    now = now_iso()
    current = connection.execute("SELECT created_at FROM metric_definitions WHERE metric_key = ? AND workspace_id = ?", (metric_key, workspace_id)).fetchone()
    connection.execute(
        """
        INSERT INTO metric_definitions(
          metric_key, workspace_id, label, table_key, measure, aggregation, dimension, time_field, value_format,
          created_at, filters_json, description, source, enabled, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        ON CONFLICT(workspace_id, metric_key) DO UPDATE SET
          label = excluded.label,
          table_key = excluded.table_key,
          measure = excluded.measure,
          aggregation = excluded.aggregation,
          dimension = excluded.dimension,
          time_field = excluded.time_field,
          value_format = excluded.value_format,
          filters_json = excluded.filters_json,
          description = excluded.description,
          source = excluded.source,
          enabled = excluded.enabled,
          updated_at = excluded.updated_at
        """,
        (
            metric_key,
            workspace_id,
            str(metric.get("label") or metric_key),
            registry["table_key"],
            measure,
            aggregation,
            str(metric.get("dimension") or "") or None,
            str(metric.get("timeField") or "") or None,
            str(metric.get("valueFormat") or "auto"),
            current["created_at"] if current else now,
            json.dumps(metric.get("filters") if isinstance(metric.get("filters"), list) else [], ensure_ascii=False),
            str(metric.get("description") or ""),
            str(metric.get("source") or "manual"),
            now,
        ),
    )
    saved = connection.execute(
        """
        SELECT m.*, COALESCE(t.display_name, m.table_key) AS table_name
        FROM metric_definitions m
        LEFT JOIN table_registry t ON t.table_key = m.table_key AND t.workspace_id = m.workspace_id
        WHERE m.metric_key = ? AND m.workspace_id = ?
        """,
        (metric_key, workspace_id),
    ).fetchone()
    return metric_row_to_payload(saved, saved["table_name"])


def build_metric_add_plan(
    connection: sqlite3.Connection,
    table_key: str,
    label: str,
    measure: str,
    aggregation: str,
    dimension: str = "",
    time_field: str = "",
    filters: list[dict[str, Any]] | None = None,
    value_format: str = "auto",
    description: str = "",
    metric_key: str = "",
    *,
    resolve_table_registry: Callable[[sqlite3.Connection, str], sqlite3.Row],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    safe_aggregations: set[str],
) -> dict[str, Any]:
    registry = resolve_table_registry(connection, table_key)
    columns = table_columns(connection, registry["physical_table"])
    measure_value = measure or "*"
    if measure_value != "*" and measure_value not in columns:
        raise ValueError(f"Unknown metric measure: {measure_value}")
    if aggregation not in safe_aggregations:
        raise ValueError(f"Unsupported metric aggregation: {aggregation}")
    for optional_field, value in [("dimension", dimension), ("timeField", time_field)]:
        if value and value not in columns:
            raise ValueError(f"Unknown metric {optional_field}: {value}")
    metric_label = label or f"{measure_value} {aggregation}"
    normalized_filters = filters if isinstance(filters, list) else []
    return {
        "metricKey": metric_key or metric_key_for(registry["table_key"], metric_label, measure_value, aggregation),
        "label": metric_label,
        "tableKey": registry["table_key"],
        "tableName": registry["display_name"],
        "measure": measure_value,
        "aggregation": aggregation,
        "dimension": dimension or None,
        "timeField": time_field or None,
        "valueFormat": value_format or "auto",
        "filters": normalized_filters,
        "description": description,
        "source": "manual",
    }


def calculated_field_usage(
    connection: sqlite3.Connection,
    table_key: str,
    field_name: str,
    field_key: str = "",
    *,
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> list[dict[str, str]]:
    workspace_id = active_workspace_id(connection)
    refs: list[dict[str, str]] = []

    def add_ref(kind: str, key: str, label: str, reason: str) -> None:
        ref = {"kind": kind, "key": key, "label": label, "reason": reason}
        if ref not in refs:
            refs.append(ref)

    for row in connection.execute(
        """
        SELECT metric_key, label, measure, dimension, time_field, filters_json, dependencies_json, metric_type
        FROM metric_definitions
        WHERE table_key = ? AND workspace_id = ? AND enabled = 1
        """,
        (table_key, workspace_id),
    ).fetchall():
        dependencies = parse_json_object(row["dependencies_json"], [])
        filters = parse_json_object(row["filters_json"], [])
        metric_key = str(row["metric_key"])
        label = str(row["label"] or metric_key)
        if field_name in {str(row["measure"] or ""), str(row["dimension"] or ""), str(row["time_field"] or "")}:
            add_ref("metric", metric_key, label, "metric-field")
        if isinstance(dependencies, list) and field_name in [str(item) for item in dependencies]:
            add_ref("metric", metric_key, label, "formula-dependency")
        if json_contains_string(filters, field_name):
            add_ref("metric", metric_key, label, "metric-filter")

    for row in connection.execute(
        """
        SELECT field_key, name, dependencies_json
        FROM calculated_fields
        WHERE table_key = ? AND workspace_id = ? AND enabled = 1
        """,
        (table_key, workspace_id),
    ).fetchall():
        current_key = str(row["field_key"])
        if current_key == field_key or str(row["name"] or "") == field_name:
            continue
        dependencies = parse_json_object(row["dependencies_json"], [])
        if isinstance(dependencies, list) and field_name in [str(item) for item in dependencies]:
            add_ref("calculated_field", current_key, str(row["name"] or current_key), "formula-dependency")

    for row in connection.execute(
        "SELECT view_key, name, config_json FROM saved_views WHERE table_key = ? AND workspace_id = ?",
        (table_key, workspace_id),
    ).fetchall():
        config = parse_json_object(row["config_json"], {})
        if json_contains_string(config, field_name):
            add_ref("saved_view", str(row["view_key"]), str(row["name"] or row["view_key"]), "view-config")

    for row in connection.execute(
        "SELECT dashboard_key, name, layout_json FROM dashboards WHERE default_table_key = ? AND workspace_id = ?",
        (table_key, workspace_id),
    ).fetchall():
        layout = parse_json_object(row["layout_json"], {})
        if json_contains_string(layout.get("globalFilters", []), field_name):
            add_ref("dashboard", str(row["dashboard_key"]), str(row["name"] or row["dashboard_key"]), "dashboard-filter")

    for row in connection.execute(
        """
        SELECT w.widget_key, w.title, w.config_json
        FROM dashboard_widgets w
        JOIN dashboards d ON d.dashboard_key = w.dashboard_key AND d.workspace_id = w.workspace_id
        WHERE w.table_key = ? AND d.workspace_id = ?
        """,
        (table_key, workspace_id),
    ).fetchall():
        config = parse_json_object(row["config_json"], {})
        if json_contains_string(config, field_name):
            add_ref("widget", str(row["widget_key"]), str(row["title"] or row["widget_key"]), "widget-config")
        formula_text = str(config.get("metricFormulaText") or config.get("formulaText") or "")
        if formula_text and f"[{field_name}]" in formula_text:
            add_ref("widget", str(row["widget_key"]), str(row["title"] or row["widget_key"]), "widget-formula")

    return refs


def compile_formula_for_table(
    connection: sqlite3.Connection,
    table_key: str,
    expression: str,
    mode: str,
    *,
    resolve_table_registry: Callable[[sqlite3.Connection, str], sqlite3.Row],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    parse_and_validate_formula: Callable[..., dict[str, Any]],
    ast_dependencies: Callable[[dict[str, Any]], list[str]],
    ast_to_sql: Callable[..., str],
    quote_identifier: Callable[[str], str],
) -> dict[str, Any]:
    registry = resolve_table_registry(connection, table_key)
    available_fields = set(table_columns(connection, registry["physical_table"]))
    ast = parse_and_validate_formula(expression, mode=mode, available_fields=available_fields)
    return {
        "registry": registry,
        "ast": ast,
        "dependencies": ast_dependencies(ast),
        "compiledSql": ast_to_sql(ast, mode=mode, resolve_field=quote_identifier),
    }


def build_formula_save_plan(
    connection: sqlite3.Connection,
    table: str,
    name: str,
    expression: str,
    mode: str = "aggregate",
    dimension: str = "",
    time_field: str = "",
    value_format: str = "auto",
    description: str = "",
    formula_key: str = "",
    *,
    compile_formula_for_table: Callable[[sqlite3.Connection, str, str, str], dict[str, Any]],
) -> dict[str, Any]:
    compiled = compile_formula_for_table(connection, table, expression, mode)
    registry = compiled["registry"]
    key = formula_key or formula_key_for(registry["table_key"], name, mode)
    return {
        "formulaKey": key,
        "name": name,
        "tableKey": registry["table_key"],
        "mode": mode,
        "formulaText": expression,
        "formulaAst": compiled["ast"],
        "compiledSql": compiled["compiledSql"],
        "dependencies": compiled["dependencies"],
        "dimension": dimension or None,
        "timeField": time_field or None,
        "valueFormat": value_format,
        "description": description,
    }


def execute_formula_save_plan(
    connection: sqlite3.Connection,
    proposed: dict[str, Any],
    *,
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    now = now_iso()
    workspace_id = active_workspace_id(connection)
    mode = str(proposed["mode"])
    key = str(proposed["formulaKey"])
    table_key = str(proposed["tableKey"])
    name = str(proposed["name"])
    expression = str(proposed["formulaText"])
    value_format = str(proposed.get("valueFormat") or "auto")
    description = str(proposed.get("description") or "")
    dimension = str(proposed.get("dimension") or "") or None
    time_field = str(proposed.get("timeField") or "") or None
    formula_ast = proposed.get("formulaAst") if isinstance(proposed.get("formulaAst"), dict) else {}
    dependencies = proposed.get("dependencies") if isinstance(proposed.get("dependencies"), list) else []
    if mode == "aggregate":
        current = connection.execute(
            "SELECT created_at FROM metric_definitions WHERE metric_key = ? AND workspace_id = ?",
            (key, workspace_id),
        ).fetchone()
        connection.execute(
            """
            INSERT INTO metric_definitions(
              metric_key, workspace_id, label, table_key, measure, aggregation, dimension, time_field, value_format,
              created_at, filters_json, description, source, enabled, updated_at,
              formula_text, formula_ast_json, dependencies_json, metric_type
            )
            VALUES(?, ?, ?, ?, '', 'formula', ?, ?, ?, ?, '[]', ?, 'manual-formula', 1, ?, ?, ?, ?, 'formula')
            ON CONFLICT(workspace_id, metric_key) DO UPDATE SET
              label = excluded.label,
              table_key = excluded.table_key,
              measure = excluded.measure,
              aggregation = excluded.aggregation,
              dimension = excluded.dimension,
              time_field = excluded.time_field,
              value_format = excluded.value_format,
              description = excluded.description,
              source = excluded.source,
              enabled = excluded.enabled,
              updated_at = excluded.updated_at,
              formula_text = excluded.formula_text,
              formula_ast_json = excluded.formula_ast_json,
              dependencies_json = excluded.dependencies_json,
              metric_type = excluded.metric_type
            """,
            (
                key,
                workspace_id,
                name,
                table_key,
                dimension,
                time_field,
                value_format,
                current["created_at"] if current else now,
                description,
                now,
                expression,
                json.dumps(formula_ast, ensure_ascii=False),
                json.dumps(dependencies, ensure_ascii=False),
            ),
        )
        saved_row = connection.execute(
            """
            SELECT m.*, COALESCE(t.display_name, m.table_key) AS table_name
            FROM metric_definitions m
            LEFT JOIN table_registry t
              ON t.table_key = m.table_key
             AND t.workspace_id = m.workspace_id
            WHERE m.metric_key = ? AND m.workspace_id = ?
            """,
            (key, workspace_id),
        ).fetchone()
        return metric_row_to_payload(saved_row, saved_row["table_name"])
    current = connection.execute(
        "SELECT created_at FROM calculated_fields WHERE field_key = ? AND workspace_id = ?",
        (key, workspace_id),
    ).fetchone()
    connection.execute(
        """
        INSERT INTO calculated_fields(
          field_key, workspace_id, table_key, name, mode, formula_text, formula_ast_json, dependencies_json,
          value_format, description, source, enabled, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual-formula', 1, ?, ?)
        ON CONFLICT(workspace_id, field_key) DO UPDATE SET
          table_key = excluded.table_key,
          name = excluded.name,
          mode = excluded.mode,
          formula_text = excluded.formula_text,
          formula_ast_json = excluded.formula_ast_json,
          dependencies_json = excluded.dependencies_json,
          value_format = excluded.value_format,
          description = excluded.description,
          source = excluded.source,
          enabled = excluded.enabled,
          updated_at = excluded.updated_at
        """,
        (
            key,
            workspace_id,
            table_key,
            name,
            mode,
            expression,
            json.dumps(formula_ast, ensure_ascii=False),
            json.dumps(dependencies, ensure_ascii=False),
            value_format,
            description,
            current["created_at"] if current else now,
            now,
        ),
    )
    saved_row = connection.execute(
        "SELECT * FROM calculated_fields WHERE field_key = ? AND workspace_id = ?",
        (key, workspace_id),
    ).fetchone()
    return calculated_field_row_to_payload(saved_row)


def build_formula_metric_query(
    connection: sqlite3.Connection,
    analysis_connection: ValidatedDuckDBQuery,
    row: sqlite3.Row,
    args: argparse.Namespace,
    *,
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    normalize_filters: Callable[[list[str], Any], list[dict[str, Any]]],
    where_sql: Callable[[list[dict[str, Any]], list[str], str], tuple[str, list[Any]]],
    parse_and_validate_formula: Callable[..., dict[str, Any]],
    ast_to_sql: Callable[..., str],
    quote_identifier: Callable[[str], str],
) -> dict[str, Any]:
    columns = table_columns(connection, row["physical_table"])
    groups = args.group or ([row["dimension"]] if row["dimension"] else [])
    for group in groups:
        if group not in columns:
            raise ValueError(f"Unknown group field: {group}")
    filters = normalize_filters(columns, [*parse_json_object(row["filters_json"], []), *metric_filters_from_cli(args.filter)])
    schema_json = None
    try:
        schema_json = row["schema_json"]
    except (IndexError, KeyError):
        pass
    where, params = where_sql(
        filters,
        [column for column in columns if not column.startswith("__aibi_")],
        "",
        field_types=schema_field_types(schema_json),
    )
    ast = parse_and_validate_formula(row["formula_text"], mode="aggregate", available_fields=set(columns))
    metric_sql = ast_to_sql(ast, mode="aggregate", resolve_field=quote_identifier)
    metric_name = "formula_value"
    select_parts = [f"{quote_identifier(group)} AS {quote_identifier(group)}" for group in groups]
    select_parts.append(f"{metric_sql} AS {quote_identifier(metric_name)}")
    group_sql = f" GROUP BY {', '.join(quote_identifier(group) for group in groups)}" if groups else ""
    order_sql = f" ORDER BY {quote_identifier(metric_name)} DESC" if groups else ""
    limit = max(1, min(int(args.limit or 50), 500))
    sql = f"SELECT {', '.join(select_parts)} FROM {quote_identifier(row['physical_table'])}{where}{group_sql}{order_sql} LIMIT ?"
    query_params = [*params, limit]
    rows = cursor_rows(analysis_connection.execute(sql, query_params))
    return {
        "mode": "aggregate",
        "columns": [*groups, metric_name],
        "rows": rows,
        "groups": groups,
        "measure": row["metric_key"],
        "aggregation": "formula",
        "metricName": metric_name,
        "filters": filters,
        "limit": limit,
        "runtime": analysis_connection.runtime(compiled_sql=sql, params=query_params),
    }


def add_metric_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    metric_filters_from_cli: Callable[[list[str]], list[dict[str, Any]]],
    build_metric_add_plan: Callable[[sqlite3.Connection, str, str, str, str, str, str, list[dict[str, Any]], str, str, str], dict[str, Any]],
    execute_metric_add_plan: Callable[[sqlite3.Connection, dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    filters = metric_filters_from_cli(args.filter)
    with open_db() as connection:
        metric = build_metric_add_plan(
            connection,
            args.table,
            args.name,
            args.field or "*",
            args.agg,
            args.dimension or "",
            args.time_field or "",
            filters,
            args.value_format,
            args.description or "",
            args.id or "",
        )
        if not args.yes:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "proposedMetric": metric}
        saved = execute_metric_add_plan(connection, metric)
        connection.commit()
    return {"ok": True, "confirmed": True, "savedMetric": saved}


def query_metric_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    metric_row_to_payload: Callable[[sqlite3.Row, str | None], dict[str, Any]],
    build_formula_metric_query: Callable[[sqlite3.Connection, ValidatedDuckDBQuery, sqlite3.Row, argparse.Namespace], dict[str, Any]],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    metric_filters_from_cli: Callable[[list[str]], list[dict[str, Any]]],
    parse_query_sort: Callable[[str], dict[str, str]],
    build_table_query: Callable[[sqlite3.Connection, str, list[str], dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = str(getattr(args, "workspace", "") or "").strip() or active_workspace_id(connection)
        row = connection.execute(
            """
            SELECT m.*, COALESCE(t.display_name, m.table_key) AS table_name, t.physical_table,
                   t.data_version, t.row_count, t.active_version_id, t.schema_json,
                   t.schema_fingerprint, t.content_fingerprint
            FROM metric_definitions m
            LEFT JOIN table_registry t
              ON t.table_key = m.table_key
             AND t.workspace_id = m.workspace_id
            WHERE m.workspace_id = ? AND (m.metric_key = ? OR m.label = ?)
            ORDER BY CASE WHEN m.metric_key = ? THEN 0 ELSE 1 END
            LIMIT 1
            """,
            (workspace_id, args.metric, args.metric, args.metric),
        ).fetchone()
        if not row:
            raise ValueError(f"Unknown metric: {args.metric}")
        metric = metric_row_to_payload(row, row["table_name"])
        if not row["physical_table"]:
            raise ValueError(f"Metric table is missing: {metric['tableKey']}")
        columns = table_columns(connection, row["physical_table"])
        with open_validated_duckdb_query(DUCKDB_PATH, [replica_expectation(row)]) as analysis_connection:
            if metric.get("metricType") == "formula" or metric.get("formulaText"):
                result = build_formula_metric_query(connection, analysis_connection, row, args)
                return {
                    "ok": True,
                    "metric": metric,
                    "tableQuery": result,
                    "rows": result["rows"],
                    "sqlIntent": "Formula metric whitelist query; formula DSL compiled locally, no user SQL accepted",
                }
            groups = args.group or ([metric["dimension"]] if metric.get("dimension") else [])
            filters = list(metric.get("filters") or [])
            filters.extend(metric_filters_from_cli(args.filter))
            sort = []
            if args.sort:
                sort.append(parse_query_sort(args.sort))
            payload = {
                "tableKey": metric["tableKey"],
                "mode": "aggregate",
                "groupFields": groups,
                "measure": "" if metric["measure"] == "*" else metric["measure"],
                "aggregation": metric["aggregation"],
                "filters": filters,
                "sort": sort,
                "limit": args.limit,
            }
            result = build_table_query(
                connection,
                analysis_connection,
                row["physical_table"],
                columns,
                payload,
            )
    return {
        "ok": True,
        "metric": metric,
        "tableQuery": result,
        "rows": result["rows"],
        "sqlIntent": "Saved metric whitelist query; no user SQL accepted",
    }


def formula_preview_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    all_available_fields: Callable[[sqlite3.Connection, str | None], set[str]],
    parse_and_validate_formula: Callable[..., dict[str, Any]],
    ast_dependencies: Callable[[dict[str, Any]], list[str]],
    ast_to_sql: Callable[..., str],
    quote_identifier: Callable[[str], str],
    formula_error_type: type[Exception],
) -> dict[str, Any]:
    errors: list[str] = []
    ast: dict[str, Any] | None = None
    compiled_sql = ""
    dependencies: list[str] = []
    with open_db() as connection:
        available_fields = all_available_fields(connection, args.table)
        try:
            ast = parse_and_validate_formula(args.expression, mode=args.mode, available_fields=available_fields)
            dependencies = ast_dependencies(ast)
            compiled_sql = ast_to_sql(ast, mode=args.mode, resolve_field=quote_identifier)
        except formula_error_type as error:
            errors.append(str(error))
    return {
        "ok": not errors,
        "dryRun": True,
        "expression": args.expression,
        "formulaDsl": {
            "mode": args.mode,
            "allowedFunctions": sorted({"SAFE_DIVIDE", "SUM", "AVG", "MIN", "MAX", "COUNT", "COUNT_DISTINCT", "ABS", "ROUND", "COALESCE", "CONCAT", "IF"}),
            "fieldReference": "[field_name]",
            "acceptsSql": False,
        },
        "dependencies": dependencies,
        "formulaAst": ast,
        "compiledSql": compiled_sql,
        "errors": errors,
    }


def save_formula_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    build_formula_save_plan: Callable[[sqlite3.Connection, str, str, str, str, str, str, str, str, str], dict[str, Any]],
    execute_formula_save_plan: Callable[[sqlite3.Connection, dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    with open_db() as connection:
        proposed = build_formula_save_plan(
            connection,
            args.table,
            args.name,
            args.expression,
            args.mode,
            args.dimension,
            args.time_field,
            args.value_format,
            args.description,
            args.id,
        )
        if not args.yes:
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "proposedFormula": proposed}
        saved = execute_formula_save_plan(connection, proposed)
        connection.commit()
    return {"ok": True, "confirmed": True, "savedFormula": saved}


def delete_formula_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    calculated_field_row_to_payload: Callable[[sqlite3.Row], dict[str, Any]],
    metric_row_to_payload: Callable[[sqlite3.Row, str | None], dict[str, Any]],
    calculated_field_usage: Callable[[sqlite3.Connection, str, str, str], list[dict[str, str]]],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        row_formula = connection.execute(
            """
            SELECT *
            FROM calculated_fields
            WHERE (field_key = ? OR name = ?) AND workspace_id = ?
            """,
            (args.formula, args.formula, workspace_id),
        ).fetchone()
        metric_formula = connection.execute(
            """
            SELECT *
            FROM metric_definitions
            WHERE (metric_key = ? OR label = ?)
              AND workspace_id = ?
              AND (metric_type = 'formula' OR formula_text <> '')
            """,
            (args.formula, args.formula, workspace_id),
        ).fetchone()
        if not row_formula and not metric_formula:
            raise ValueError(f"Unknown formula: {args.formula}")
        target = calculated_field_row_to_payload(row_formula) if row_formula else metric_row_to_payload(metric_formula, None)
        references: list[dict[str, str]] = []
        if row_formula:
            references = calculated_field_usage(
                connection,
                str(row_formula["table_key"]),
                str(row_formula["name"] or ""),
                str(row_formula["field_key"] or ""),
            )
        if not args.yes:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "targetFormula": target,
                "references": references,
                "blockedByReferences": bool(references),
            }
        if references:
            return {
                "ok": False,
                "confirmed": False,
                "error": "Calculated field is in use and cannot be deleted.",
                "targetFormula": target,
                "references": references,
                "blockedByReferences": True,
                "source": "calculated_field_usage deletion guard adapted to workspace assets",
            }
        if row_formula:
            connection.execute(
                "DELETE FROM calculated_fields WHERE field_key = ? AND workspace_id = ?",
                (row_formula["field_key"], workspace_id),
            )
        if metric_formula:
            connection.execute(
                "DELETE FROM metric_definitions WHERE metric_key = ? AND workspace_id = ?",
                (metric_formula["metric_key"], workspace_id),
            )
        connection.commit()
    return {"ok": True, "confirmed": True, "deletedFormula": target}
