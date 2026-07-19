from __future__ import annotations

from datetime import date, timedelta
import re
import sqlite3
from typing import Any


QUERY_INTENT_SCHEMA = "aibi-trusted-query-intent/v1"
EXECUTION_COVERAGE_SCHEMA = "aibi-query-execution-coverage/v1"
SOURCE_RUN_BINDING_SCHEMA = "aibi-current-source-run-binding/v1"
RESULT_STATES = {"executed", "draft", "blocked", "simulation", "stale"}

METHOD_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("business-role", ("爆款", "潜力款", "常销款", "滞销款", "引流款", "利润款")),
    ("abc", ("abc", "a类", "b类", "c类")),
    ("decile", ("十分位", "十等分", "decile")),
    ("pareto", ("pareto", "帕累托", "二八", "80/20", "80％", "80%")),
    ("concentration", ("集中度", "头部占比", "前20%", "前 20%", "top 20%")),
    ("ranking", ("排名", "排行", "top ", "bottom ", "前十", "前10", "前 10")),
    ("trend", ("趋势", "走势", "同比", "环比", "按月", "按周", "按日", "trend", "yoy", "mom")),
)

AGGREGATION_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("avg", ("平均", "均值", "avg", "average", "mean")),
    ("max", ("最大", "最高", "max")),
    ("min", ("最小", "最低", "min")),
    ("count-distinct", ("去重", "唯一", "distinct")),
    ("count", ("记录数", "行数", "条数", "数量", "count")),
    ("sum", ("合计", "总计", "总额", "汇总", "求和", "sum")),
)

FILTER_OPERATORS = {
    "=": "equals",
    "等于": "equals",
    "为": "equals",
    "是": "equals",
    "equal": "equals",
    "equals": "equals",
    "contain": "contains",
    "contains": "contains",
}

METHODS_REQUIRING_ENTITY = {"ranking", "concentration", "pareto", "decile", "abc", "business-role"}
METHODS_CLOSED_IN_V1 = {"abc", "business-role"}


def _compact(value: Any) -> str:
    return re.sub(r"[\s_\-.]+", "", str(value or "").strip()).casefold()


def _row_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _table_keys_for_source_run(
    connection: sqlite3.Connection,
    source_run: dict[str, Any] | None,
) -> list[str]:
    if not source_run:
        return []
    mapping_table = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'source_run_tables'"
    ).fetchone()
    if mapping_table:
        rows = connection.execute(
            "SELECT table_key FROM source_run_tables WHERE source_run_id = ? ORDER BY table_key",
            (source_run["id"],),
        ).fetchall()
        mapped = [str(row["table_key"]) for row in rows]
        if mapped:
            return mapped
    table_key = str(source_run.get("table_key") or "").strip()
    return [table_key] if table_key and table_key != "__batch__" else []


def current_source_run_binding(
    connection: sqlite3.Connection,
    workspace_id: str,
    table_keys: list[str] | tuple[str, ...] | None,
) -> dict[str, Any]:
    requested = list(dict.fromkeys(str(item).strip() for item in (table_keys or []) if str(item).strip()))
    available_tables = {
        str(row["name"])
        for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }
    if "workspaces" not in available_tables:
        return {
            "schema": SOURCE_RUN_BINDING_SCHEMA,
            "workspaceId": workspace_id,
            "currentSourceRunId": None,
            "sourceRun": None,
            "requestedTableKeys": requested,
            "sourceRunTableKeys": [],
            "missingTableKeys": requested,
            "matchesCurrent": False,
            "blockers": ["current-source-run-schema-missing"],
        }
    workspace = connection.execute(
        "SELECT id, current_source_run_id FROM workspaces WHERE id = ?",
        (workspace_id,),
    ).fetchone()
    current_source_run_id = str(workspace["current_source_run_id"] or "") if workspace else ""
    source_run = _row_dict(
        connection.execute(
            """
            SELECT id, workspace_id, table_key, name, status, source_file,
                   row_count, column_count, created_at
            FROM source_runs
            WHERE id = ? AND workspace_id = ?
            """,
            (current_source_run_id, workspace_id),
        ).fetchone()
    ) if current_source_run_id and "source_runs" in available_tables else None
    source_table_keys = _table_keys_for_source_run(connection, source_run)
    blockers: list[str] = []
    if not workspace:
        blockers.append("workspace-not-found")
    if not current_source_run_id:
        blockers.append("current-source-run-missing")
    elif source_run is None:
        blockers.append("current-source-run-not-found")
    elif str(source_run.get("status") or "").casefold() not in {"committed", "completed", "ready", "success"}:
        blockers.append("current-source-run-not-committed")
    missing_tables = [table_key for table_key in requested if table_key not in source_table_keys]
    if missing_tables:
        blockers.append("query-tables-not-in-current-source-run")
    return {
        "schema": SOURCE_RUN_BINDING_SCHEMA,
        "workspaceId": workspace_id,
        "currentSourceRunId": current_source_run_id or None,
        "sourceRun": source_run,
        "requestedTableKeys": requested,
        "sourceRunTableKeys": source_table_keys,
        "missingTableKeys": missing_tables,
        "matchesCurrent": not blockers,
        "blockers": blockers,
    }


def _method(prompt: str, task_type: str) -> str:
    lower = prompt.casefold()
    for method, patterns in METHOD_PATTERNS:
        if any(pattern.casefold() in lower for pattern in patterns):
            return method
    if task_type in {"ranking", "trend", "comparison", "composition"}:
        return "concentration" if task_type == "composition" else task_type
    return "overview"


def _explicit_aggregation(prompt: str) -> str | None:
    lower = prompt.casefold()
    for aggregation, patterns in AGGREGATION_PATTERNS:
        if any(pattern.casefold() in lower for pattern in patterns):
            return aggregation
    return None


def _metric_contract_aggregation(
    connection: sqlite3.Connection,
    workspace_id: str,
    table_key: str,
    measure: str,
    dimension: str | None,
) -> tuple[str | None, str | None]:
    if not measure or measure == "*":
        return None, None
    rows = connection.execute(
        """
        SELECT metric_key, aggregation
        FROM metric_definitions
        WHERE workspace_id = ? AND table_key = ? AND measure = ?
          AND COALESCE(dimension, '') = COALESCE(?, '')
        ORDER BY created_at DESC
        """,
        (workspace_id, table_key, measure, dimension),
    ).fetchall()
    aggregations = list(dict.fromkeys(str(row["aggregation"] or "") for row in rows if row["aggregation"]))
    if len(aggregations) == 1:
        metric_key = next(str(row["metric_key"]) for row in rows if str(row["aggregation"] or "") == aggregations[0])
        return aggregations[0], metric_key
    return None, None


def _resolve_column(expression: str, columns: list[str]) -> str | None:
    normalized = _compact(expression)
    exact = [column for column in columns if _compact(column) == normalized]
    if len(exact) == 1:
        return exact[0]
    contained = [column for column in columns if _compact(column) and _compact(column) in normalized]
    return contained[0] if len(contained) == 1 else None


def _resolve_filters(raw_filters: Any, columns: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    resolved: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for raw in raw_filters if isinstance(raw_filters, list) else []:
        item = raw if isinstance(raw, dict) else {}
        field_expression = str(item.get("fieldExpression") or item.get("field") or "").strip()
        field = _resolve_column(field_expression, columns)
        operator_token = str(item.get("operator") or "").strip().casefold()
        operator = FILTER_OPERATORS.get(operator_token)
        value = item.get("value")
        if field and operator and value is not None and str(value).strip():
            resolved.append({
                "field": field,
                "operator": operator,
                "value": value,
                "source": "explicit-prompt-filter",
            })
        else:
            unresolved.append({
                "kind": "filter-binding",
                "fieldExpression": field_expression,
                "operator": operator_token,
                "value": value,
                "reason": "filter-field-or-operator-unresolved",
            })
    return resolved, unresolved


def _time_window(scope: dict[str, Any] | None, *, today: date | None = None) -> tuple[str, str] | None:
    if not isinstance(scope, dict):
        return None
    parts = scope.get("parts") if isinstance(scope.get("parts"), dict) else {}
    year = str(parts.get("year") or "")
    month = str(parts.get("month") or "")
    if year and month:
        start = date(int(year), int(month), 1)
        end = date(start.year + (1 if start.month == 12 else 0), 1 if start.month == 12 else start.month + 1, 1)
        return start.isoformat(), end.isoformat()
    if year:
        return f"{int(year):04d}-01-01", f"{int(year) + 1:04d}-01-01"
    relative = str(parts.get("relative") or "").casefold()
    current = today or date.today()
    if relative in {"今天", "today"}:
        return current.isoformat(), (current + timedelta(days=1)).isoformat()
    if relative in {"昨日", "昨天", "yesterday"}:
        return (current - timedelta(days=1)).isoformat(), current.isoformat()
    if relative in {"本月", "this month"}:
        start = current.replace(day=1)
        end = date(start.year + (1 if start.month == 12 else 0), 1 if start.month == 12 else start.month + 1, 1)
        return start.isoformat(), end.isoformat()
    if relative in {"上月", "last month"}:
        this_month = current.replace(day=1)
        end = this_month
        start = date(end.year - (1 if end.month == 1 else 0), 12 if end.month == 1 else end.month - 1, 1)
        return start.isoformat(), end.isoformat()
    if relative in {"今年", "this year"}:
        return f"{current.year:04d}-01-01", f"{current.year + 1:04d}-01-01"
    if relative in {"去年", "last year"}:
        return f"{current.year - 1:04d}-01-01", f"{current.year:04d}-01-01"
    return None


def _time_filters(
    connection: sqlite3.Connection,
    workspace_id: str,
    table_key: str,
    time_scope: Any,
    columns: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str | None]:
    if not isinstance(time_scope, dict):
        return [], [], None
    rows = connection.execute(
        """
        SELECT field_name
        FROM field_semantics
        WHERE workspace_id = ? AND table_key = ? AND role IN ('event_time', 'time')
        ORDER BY confidence DESC, field_name
        """,
        (workspace_id, table_key),
    ).fetchall()
    fields = list(dict.fromkeys(str(row["field_name"]) for row in rows if str(row["field_name"]) in columns))
    window = _time_window(time_scope)
    if len(fields) != 1 or window is None:
        return [], [{
            "kind": "time-binding",
            "expression": time_scope.get("expression"),
            "candidateFields": fields,
            "reason": "time-field-or-window-unresolved",
        }], None
    start, end = window
    return [
        {"field": fields[0], "operator": "date-gte", "value": start, "source": "explicit-time-scope"},
        {"field": fields[0], "operator": "date-lt", "value": end, "source": "explicit-time-scope"},
    ], [], fields[0]


def _limit_intent(prompt: str, method: str) -> tuple[int | None, float | None, str]:
    percent_match = re.search(r"(?:前|top\s*)(\d+(?:\.\d+)?)\s*[%％]", prompt, re.IGNORECASE)
    if percent_match:
        return None, float(percent_match.group(1)) / 100.0, "entity-percent"
    number_match = re.search(r"(?:前|top\s*|bottom\s*)(\d+)\s*(?:名|个|条|位|组)?", prompt, re.IGNORECASE)
    if number_match:
        return max(1, min(int(number_match.group(1)), 500)), None, "entity-count"
    return (10 if method == "ranking" else None), None, "method-default" if method == "ranking" else "none"


def build_trusted_query_intent(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    prompt: str,
    table_key: str,
    columns: list[str],
    intent_frame: dict[str, Any] | None,
    measure: str,
    measure_confidence: str,
    dimension: str | None,
    dimension_confidence: str,
    suggested_aggregation: str,
    result_state: str = "executed",
) -> dict[str, Any]:
    frame = intent_frame if isinstance(intent_frame, dict) else {}
    task_type = str(frame.get("taskType") or "overview")
    method = _method(prompt, task_type)
    explicit_aggregation = _explicit_aggregation(prompt)
    metric_aggregation, metric_key = _metric_contract_aggregation(
        connection,
        workspace_id,
        table_key,
        measure,
        dimension,
    )
    if measure == "*":
        aggregation = "count"
        aggregation_source = "row-count"
    elif explicit_aggregation:
        aggregation = explicit_aggregation
        aggregation_source = "explicit-prompt"
    elif metric_aggregation:
        aggregation = metric_aggregation
        aggregation_source = "metric-definition"
    else:
        aggregation = suggested_aggregation
        aggregation_source = "unconfirmed-default"

    filters, filter_unresolved = _resolve_filters(frame.get("filters"), columns)
    time_filters, time_unresolved, time_field = _time_filters(
        connection,
        workspace_id,
        table_key,
        frame.get("timeScope"),
        columns,
    )
    filters.extend(time_filters)
    limit, top_percent, limit_kind = _limit_intent(prompt, method)
    sort_direction = "asc" if re.search(r"(?:最低|倒数|bottom)", prompt, re.IGNORECASE) else "desc"
    blockers: list[dict[str, Any] | str] = [*filter_unresolved, *time_unresolved]

    quantitative_method = method != "overview" or measure != "*" or bool(dimension)
    if quantitative_method and measure_confidence not in {"explicit", "recommended", "widget", "metric-definition"}:
        blockers.append("measure-not-explicitly-resolved")
    if measure != "*" and aggregation_source == "unconfirmed-default":
        blockers.append("aggregation-not-explicitly-resolved")
    if method in METHODS_REQUIRING_ENTITY and (not dimension or dimension_confidence not in {"explicit", "recommended", "widget"}):
        blockers.append("entity-grain-not-explicitly-resolved")
    if method in METHODS_CLOSED_IN_V1:
        blockers.append(f"method-closed-in-v1:{method}")
    if method == "trend" and not time_field and not frame.get("timeScope"):
        blockers.append("trend-time-field-not-resolved")
    if result_state not in RESULT_STATES:
        blockers.append("invalid-result-state")

    source_binding = current_source_run_binding(connection, workspace_id, [table_key])
    blockers.extend(source_binding["blockers"])
    requested_slots = {
        "method": method,
        "entity": dimension,
        "grain": dimension or "aggregate-result",
        "measure": measure,
        "aggregation": aggregation,
        "filters": list(frame.get("filters") or []),
        "timeRange": frame.get("timeScope"),
        "sort": sort_direction if dimension else None,
        "limit": limit,
        "topPercent": top_percent,
    }
    return {
        "schema": QUERY_INTENT_SCHEMA,
        "workspaceId": workspace_id,
        "sourceRunId": source_binding.get("currentSourceRunId"),
        "tableKeys": [table_key],
        "taskType": task_type,
        "method": method,
        "entity": {"field": dimension, "grain": dimension or "aggregate-result"},
        "measure": {"field": measure, "confidence": measure_confidence},
        "aggregation": {"function": aggregation, "source": aggregation_source, "metricKey": metric_key},
        "filters": filters,
        "timeRange": {
            "expression": frame.get("timeScope", {}).get("expression") if isinstance(frame.get("timeScope"), dict) else None,
            "field": time_field,
            "pushedFilters": time_filters,
        },
        "sort": {"field": "value", "direction": sort_direction} if dimension else None,
        "limit": {"count": limit, "percent": top_percent, "kind": limit_kind},
        "requestedSlots": requested_slots,
        "sourceRunBinding": source_binding,
        "requestedResultState": result_state,
        "blockers": list(dict.fromkeys(str(item) if not isinstance(item, dict) else repr(item) for item in blockers)),
        "blockerDetails": blockers,
        "ready": not blockers,
    }


def build_execution_coverage(
    query_intent: dict[str, Any],
    *,
    runtime: dict[str, Any] | None,
    result_rows: list[dict[str, Any]] | None,
    result_state: str,
) -> dict[str, Any]:
    runtime = runtime if isinstance(runtime, dict) else {}
    rows = result_rows if isinstance(result_rows, list) else []
    requested = query_intent.get("requestedSlots") if isinstance(query_intent.get("requestedSlots"), dict) else {}
    pushed_filters = list(query_intent.get("filters") or [])
    requested_filters = list(requested.get("filters") or [])
    requested_time = requested.get("timeRange")
    time_filters = list((query_intent.get("timeRange") or {}).get("pushedFilters") or [])
    slots = {
        "method": bool(query_intent.get("method")),
        "entity": not requested.get("entity") or bool((query_intent.get("entity") or {}).get("field")),
        "grain": bool((query_intent.get("entity") or {}).get("grain")),
        "measure": bool((query_intent.get("measure") or {}).get("field")),
        "aggregation": bool((query_intent.get("aggregation") or {}).get("function")),
        "filters": not requested_filters or len([item for item in pushed_filters if item.get("source") == "explicit-prompt-filter"]) == len(requested_filters),
        "timeRange": not requested_time or len(time_filters) == 2,
        "sort": not requested.get("sort") or bool(query_intent.get("sort")),
        "limit": requested.get("limit") is None or (query_intent.get("limit") or {}).get("count") == requested.get("limit"),
        "topPercent": requested.get("topPercent") is None or (query_intent.get("limit") or {}).get("percent") == requested.get("topPercent"),
    }
    blockers = list(query_intent.get("blockers") or [])
    blockers.extend(f"slot-not-pushed:{key}" for key, covered in slots.items() if not covered)
    if not runtime.get("compiledSql"):
        blockers.append("read-only-query-not-executed")
    if result_state == "executed" and not rows:
        blockers.append("executed-result-has-no-rows")
    blockers = list(dict.fromkeys(blockers))
    complete = not blockers and all(slots.values())
    can_support_business_conclusion = (
        result_state == "executed"
        and complete
        and len(rows) > 0
        and query_intent.get("sourceRunBinding", {}).get("matchesCurrent") is True
    )
    return {
        "schema": EXECUTION_COVERAGE_SCHEMA,
        "resultState": result_state,
        "slots": slots,
        "requested": requested,
        "pushed": {
            "filters": pushed_filters,
            "timeFilters": time_filters,
            "compiledSql": runtime.get("compiledSql"),
        },
        "rowCount": len(rows),
        "complete": complete,
        "canSupportBusinessConclusion": can_support_business_conclusion,
        "blockers": blockers,
    }


def build_semantic_query_contract(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    intent_frame: dict[str, Any] | None,
    execution_plan: dict[str, Any],
    relationship_query: dict[str, Any],
    runtime: dict[str, Any],
    result_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Bind an executed N-hop semantic plan to the same typed trust contract as single-table queries."""
    frame = intent_frame if isinstance(intent_frame, dict) else {}
    table_keys = [str(item) for item in execution_plan.get("pathTables") or [] if str(item).strip()]
    groups = [item for item in execution_plan.get("groups") or [] if isinstance(item, dict)]
    measure = execution_plan.get("measure") if isinstance(execution_plan.get("measure"), dict) else {}
    query_filters = [item for item in relationship_query.get("filters") or [] if isinstance(item, dict)]
    request_filters = [item for item in execution_plan.get("requestFilters") or [] if isinstance(item, dict)]
    requested_prompt_filters = [item for item in frame.get("filters") or [] if isinstance(item, dict)]
    requested_time = frame.get("timeScope") if isinstance(frame.get("timeScope"), dict) else None
    time_filters = [item for item in request_filters if item.get("source") == "request-time-scope"]
    prompt_filters = [item for item in request_filters if item.get("source") == "request"]
    source_binding = current_source_run_binding(connection, workspace_id, table_keys)
    proof = execution_plan.get("relationshipPathProof") if isinstance(execution_plan.get("relationshipPathProof"), dict) else {}

    def filter_signature(item: dict[str, Any]) -> tuple[str, str, str, str, str]:
        return (
            str(item.get("tableKey") or ""),
            str(item.get("field") or ""),
            str(item.get("operator") or ""),
            str(item.get("value") or ""),
            str(item.get("source") or ""),
        )

    pushed_signatures = {filter_signature(item) for item in query_filters}
    request_filters_pushed = all(filter_signature(item) in pushed_signatures for item in request_filters)
    entity_field = ""
    if groups:
        entity_field = ".".join(
            value for value in (str(groups[0].get("tableKey") or ""), str(groups[0].get("field") or "")) if value
        )
    measure_field = ".".join(
        value for value in (str(measure.get("tableKey") or ""), str(measure.get("field") or "")) if value
    )
    aggregation = str(measure.get("aggregation") or "")
    grain = list(execution_plan.get("finalGrain") or [])
    requested_slots = {
        "method": str(frame.get("taskType") or "comparison"),
        "entity": entity_field or None,
        "grain": grain or ["aggregate-result"],
        "measure": measure_field,
        "aggregation": aggregation,
        "filters": requested_prompt_filters,
        "timeRange": requested_time,
        "sort": None,
        "limit": None,
        "topPercent": None,
    }
    blockers: list[str] = [str(item) for item in source_binding.get("blockers") or []]
    if execution_plan.get("status") != "ready":
        blockers.append("semantic-execution-plan-not-ready")
    if proof.get("status") not in {"validated", "verified"} or proof.get("blockers"):
        blockers.append("semantic-relationship-path-not-validated")
    if not table_keys:
        blockers.append("semantic-source-tables-missing")
    if not measure_field or not aggregation:
        blockers.append("semantic-measure-or-aggregation-missing")
    if requested_prompt_filters and len(prompt_filters) != len(requested_prompt_filters):
        blockers.append("semantic-prompt-filters-not-resolved")
    if requested_time and not time_filters:
        blockers.append("semantic-time-range-not-resolved")
    if not request_filters_pushed:
        blockers.append("semantic-request-filters-not-pushed")
    if not runtime.get("compiledSql"):
        blockers.append("read-only-query-not-executed")
    if not result_rows:
        blockers.append("executed-result-has-no-rows")
    blockers = list(dict.fromkeys(blockers))
    slots = {
        "method": True,
        "entity": not requested_slots["entity"] or bool(entity_field),
        "grain": bool(grain or not groups),
        "measure": bool(measure_field),
        "aggregation": bool(aggregation),
        "filters": not requested_prompt_filters or len(prompt_filters) == len(requested_prompt_filters),
        "timeRange": not requested_time or bool(time_filters),
        "sort": True,
        "limit": True,
        "topPercent": True,
    }
    blockers.extend(f"slot-not-pushed:{key}" for key, covered in slots.items() if not covered)
    blockers = list(dict.fromkeys(blockers))
    complete = not blockers and all(slots.values())
    result_state = "executed" if complete else "blocked"
    typed_intent = {
        "schema": QUERY_INTENT_SCHEMA,
        "workspaceId": workspace_id,
        "sourceRunId": source_binding.get("currentSourceRunId"),
        "tableKeys": table_keys,
        "taskType": str(frame.get("taskType") or "comparison"),
        "method": str(frame.get("taskType") or "comparison"),
        "entity": {"field": entity_field or None, "grain": grain or ["aggregate-result"]},
        "measure": {"field": measure_field, "confidence": "validated-semantic-plan"},
        "aggregation": {"function": aggregation, "source": "validated-semantic-plan", "metricKey": None},
        "filters": query_filters,
        "timeRange": {"expression": requested_time.get("expression") if requested_time else None, "field": time_filters[0].get("field") if time_filters else None, "pushedFilters": time_filters},
        "sort": None,
        "limit": {"count": relationship_query.get("sqlShape", {}).get("limit"), "percent": None, "kind": "execution-safety-limit"},
        "requestedSlots": requested_slots,
        "sourceRunBinding": source_binding,
        "requestedResultState": "executed",
        "blockers": blockers,
        "blockerDetails": blockers,
        "ready": complete,
    }
    coverage = {
        "schema": EXECUTION_COVERAGE_SCHEMA,
        "resultState": result_state,
        "slots": slots,
        "requested": requested_slots,
        "pushed": {
            "filters": query_filters,
            "timeFilters": time_filters,
            "compiledSql": runtime.get("compiledSql"),
            "relationshipPathFingerprint": proof.get("fingerprint"),
        },
        "rowCount": len(result_rows),
        "complete": complete,
        "canSupportBusinessConclusion": complete and source_binding.get("matchesCurrent") is True,
        "blockers": blockers,
    }
    return typed_intent, coverage


def trusted_result_state(
    query_intent: dict[str, Any],
    *,
    runtime: dict[str, Any] | None,
    result_rows: list[dict[str, Any]] | None,
) -> tuple[str, dict[str, Any]]:
    requested = str(query_intent.get("requestedResultState") or "executed")
    preliminary = requested if requested in RESULT_STATES else "blocked"
    if query_intent.get("blockers"):
        preliminary = "blocked"
    coverage = build_execution_coverage(
        query_intent,
        runtime=runtime,
        result_rows=result_rows,
        result_state=preliminary,
    )
    if preliminary == "executed" and not coverage["canSupportBusinessConclusion"]:
        preliminary = "blocked"
        coverage = build_execution_coverage(
            query_intent,
            runtime=runtime,
            result_rows=result_rows,
            result_state=preliminary,
        )
    return preliminary, coverage
