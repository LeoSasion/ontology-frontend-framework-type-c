from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sqlite3
from contextlib import closing
from typing import Any, Callable

from query_plan_receipt_service import current_query_receipt_source_state, get_query_receipt


ANALYSIS_UNIT_SCHEMA = "aibi-analysis-unit/v1"
CHART_ADAPTER_SCHEMA = "aibi-chart-adapter/v1"
UNIT_KINDS = {"auto", "metric", "comparison", "trend", "composition", "ranking", "anomaly"}
CHART_TYPES = {"metric", "bar", "line", "pie", "table"}
MAX_RESULT_ROWS = 500


def _canonical_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonical_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_canonical_value(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(_canonical_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _safe_rows(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise ValueError("Analysis Unit rows must be a JSON array")
    if len(rows) > MAX_RESULT_ROWS:
        raise ValueError(f"Analysis Unit rows exceed the {MAX_RESULT_ROWS} row snapshot limit")
    normalized: list[dict[str, Any]] = []
    for item in rows:
        if not isinstance(item, dict):
            raise ValueError("Analysis Unit rows must contain JSON objects")
        projected = {str(key): value for key, value in item.items() if not isinstance(value, (dict, list, tuple, set))}
        normalized.append(json.loads(json.dumps(projected, ensure_ascii=False, default=str)))
    return normalized


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        result = float(value)
        return result if math.isfinite(result) else None
    if isinstance(value, str) and re.fullmatch(r"[-+]?\d+(?:\.\d+)?", value.strip()):
        result = float(value)
        return result if math.isfinite(result) else None
    return None


def _looks_temporal(field: str, values: list[Any]) -> bool:
    if re.search(r"date|time|month|year|day|week|quarter|日期|时间|月份|年度|季度|周", field, re.I):
        return True
    present = [str(value).strip() for value in values if value not in (None, "")]
    if not present:
        return False
    pattern = re.compile(r"^(?:\d{4}[-/]\d{1,2}(?:[-/]\d{1,2})?|\d{4}Q[1-4]|\d{4}年\d{1,2}月)$", re.I)
    return all(pattern.fullmatch(value) for value in present)


def _columns(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({str(key) for row in rows for key in row})


def _numeric_columns(rows: list[dict[str, Any]], columns: list[str]) -> list[str]:
    result: list[str] = []
    for column in columns:
        present = [row.get(column) for row in rows if row.get(column) is not None]
        if present and all(_number(value) is not None for value in present):
            result.append(column)
    return result


def _measure_column(receipt: dict[str, Any], rows: list[dict[str, Any]], numeric: list[str]) -> str | None:
    selection = receipt.get("selection") if isinstance(receipt.get("selection"), dict) else {}
    measure = str(selection.get("measure") or "")
    aggregation = str(selection.get("aggregation") or "")
    candidates = [measure, f"{aggregation}_{measure}", "value", "metric_value"]
    for candidate in candidates:
        if candidate and candidate in numeric:
            return candidate
    group = str(selection.get("group") or "")
    return next((column for column in numeric if column != group), numeric[0] if numeric else None)


def _shape(receipt: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    columns = _columns(rows)
    numeric = _numeric_columns(rows, columns)
    selection = receipt.get("selection") if isinstance(receipt.get("selection"), dict) else {}
    group = str(selection.get("group") or "")
    dimension = group if group in columns else next((column for column in columns if column not in numeric), None)
    selected_group_columns = [
        str(item.get("outputName") or "")
        for item in selection.get("groups") or []
        if isinstance(item, dict) and item.get("outputName") in columns
    ]
    dimension_columns = list(dict.fromkeys(selected_group_columns or ([dimension] if dimension else [])))
    measure = _measure_column(receipt, rows, numeric)
    missing = {column: sum(1 for row in rows if row.get(column) is None) for column in columns}
    dimension_values = [row.get(dimension) for row in rows] if dimension else []
    return {
        "rowCount": len(rows),
        "columnCount": len(columns),
        "columns": columns,
        "numericColumns": numeric,
        "dimensionColumn": dimension,
        "dimensionColumns": dimension_columns,
        "measureColumn": measure,
        "temporalDimension": bool(dimension and _looks_temporal(dimension, dimension_values)),
        "missingByColumn": missing,
        "distinctDimensionCount": len({str(value) for value in dimension_values if value is not None}),
    }


def _infer_kind(requested: str, receipt: dict[str, Any], shape: dict[str, Any]) -> str:
    if requested and requested != "auto":
        return requested
    request = str(receipt.get("request") or "").lower()
    if re.search(r"异常|离群|anomal|outlier", request):
        return "anomaly"
    if re.search(r"排名|排行|top\s*\d*|rank", request):
        return "ranking"
    if re.search(r"占比|构成|份额|饼图|composition|share|pie", request):
        return "composition"
    if shape["temporalDimension"] or re.search(r"趋势|变化|折线|trend|line", request):
        return "trend"
    if not shape["dimensionColumn"]:
        return "metric"
    return "comparison"


def _validate(kind: str, receipt: dict[str, Any], shape: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    blockers: list[str] = []
    warnings: list[str] = []
    if str(receipt.get("status") or "") != "executed":
        blockers.append("query-receipt-not-executed")
    if not rows:
        blockers.append("empty-result")
    measure = shape["measureColumn"]
    dimension = shape["dimensionColumn"]
    if not measure:
        blockers.append("numeric-measure-not-found")
    if kind != "metric" and not dimension:
        blockers.append("dimension-not-found")
    if kind == "metric" and len(rows) != 1:
        blockers.append("metric-requires-one-row")
    if kind in {"comparison", "trend", "ranking", "composition"} and len(rows) < 2:
        blockers.append(f"{kind}-requires-at-least-two-rows")
    if kind == "trend" and not shape["temporalDimension"]:
        blockers.append("trend-requires-temporal-dimension")
    if kind == "composition" and not 2 <= len(rows) <= 12:
        blockers.append("composition-requires-2-to-12-slices")
    if kind == "anomaly" and len(rows) < 5:
        blockers.append("anomaly-requires-at-least-five-observations")
    if measure:
        missing = int(shape["missingByColumn"].get(measure, 0))
        if missing:
            if kind in {"composition", "anomaly"}:
                blockers.append("missing-measure-values")
            else:
                warnings.append("missing-measure-values")
        values = [_number(row.get(measure)) for row in rows]
        numbers = [value for value in values if value is not None]
        if kind == "composition" and any(value < 0 for value in numbers):
            blockers.append("composition-requires-nonnegative-values")
        if kind == "composition" and not sum(numbers):
            blockers.append("composition-requires-positive-total")
    return {
        "status": "blocked" if blockers else "ready",
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "checks": {
            "receiptExecuted": str(receipt.get("status") or "") == "executed",
            "hasRows": bool(rows),
            "hasNumericMeasure": bool(measure),
            "grainDeclared": bool(receipt.get("selection")),
            "snapshotWithinLimit": len(rows) <= MAX_RESULT_ROWS,
        },
    }


def _calculation(kind: str, shape: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    measure = shape.get("measureColumn")
    dimension = shape.get("dimensionColumn")
    points = [
        {"label": row.get(dimension) if dimension else measure, "value": _number(row.get(measure))}
        for row in rows
    ] if measure else []
    valid = [point for point in points if point["value"] is not None]
    values = [float(point["value"]) for point in valid]
    base: dict[str, Any] = {"pointCount": len(valid), "points": valid}
    if not values:
        return base
    if kind == "metric":
        base["value"] = values[0]
    elif kind == "comparison":
        minimum = min(valid, key=lambda point: (point["value"], str(point["label"])))
        maximum = max(valid, key=lambda point: (point["value"], str(point["label"])))
        base.update({"minimum": minimum, "maximum": maximum, "absoluteGap": maximum["value"] - minimum["value"]})
    elif kind == "trend":
        first, last = valid[0], valid[-1]
        change = last["value"] - first["value"]
        base.update({"first": first, "last": last, "absoluteChange": change, "percentChange": change / abs(first["value"]) if first["value"] else None})
    elif kind == "composition":
        total = sum(values)
        base.update({"total": total, "shares": [{**point, "share": point["value"] / total if total else None} for point in valid]})
    elif kind == "ranking":
        ordered = sorted(valid, key=lambda point: (-point["value"], str(point["label"])))
        base["ranks"] = [{**point, "rank": index + 1} for index, point in enumerate(ordered)]
    elif kind == "anomaly":
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        standard_deviation = math.sqrt(variance)
        scored = [{**point, "zScore": (point["value"] - mean) / standard_deviation if standard_deviation else 0.0} for point in valid]
        base.update({"mean": mean, "standardDeviation": standard_deviation, "anomalies": [point for point in scored if abs(point["zScore"]) >= 2.0], "scoredPoints": scored})
    return base


def adapt_chart(unit: dict[str, Any], preferred: str = "") -> dict[str, Any]:
    kind = str(unit.get("kind") or "")
    shape = unit.get("shape") if isinstance(unit.get("shape"), dict) else {}
    validation = unit.get("validation") if isinstance(unit.get("validation"), dict) else {}
    allowed = {
        "metric": ["metric", "table"],
        "comparison": ["bar", "table"],
        "trend": ["line", "table"],
        "composition": ["pie", "bar", "table"],
        "ranking": ["bar", "table"],
        "anomaly": ["line", "table"] if shape.get("temporalDimension") else ["table"],
    }.get(kind, ["table"])
    blockers = list(validation.get("blockers") or [])
    preferred = str(preferred or "").strip()
    if preferred and preferred not in CHART_TYPES:
        blockers.append("unknown-preferred-chart")
    elif preferred and preferred not in allowed:
        blockers.append("preferred-chart-incompatible")
    chart_type = preferred if preferred in allowed else allowed[0]
    status = "blocked" if blockers or validation.get("status") != "ready" else "ready"
    config: dict[str, Any] = {
        "dimension": shape.get("dimensionColumn"),
        "measure": shape.get("measureColumn"),
        "sortDirection": "desc" if kind == "ranking" else "asc" if kind == "trend" else None,
        "barOrientation": "horizontal" if kind == "ranking" else "vertical",
        "showLegend": kind == "composition",
    }
    return {
        "schema": CHART_ADAPTER_SCHEMA,
        "status": status,
        "unitKey": unit.get("unitKey"),
        "queryReceiptKey": unit.get("queryReceiptKey"),
        "chartType": chart_type if status == "ready" else None,
        "allowedChartTypes": allowed,
        "config": config if status == "ready" else {},
        "rationale": [f"analysis-kind:{kind}", f"rows:{shape.get('rowCount', 0)}", f"temporal:{str(bool(shape.get('temporalDimension'))).lower()}"],
        "blockers": sorted(set(blockers)),
        "inputFingerprint": _fingerprint({"unit": unit.get("definitionFingerprint"), "preferred": preferred, "allowed": allowed}),
    }


def create_analysis_unit(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    receipt: dict[str, Any],
    rows: Any,
    requested_kind: str = "auto",
    title: str = "",
    preferred_chart: str = "",
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    requested_kind = str(requested_kind or "auto")
    if requested_kind not in UNIT_KINDS:
        raise ValueError(f"Unsupported Analysis Unit kind: {requested_kind}")
    source = receipt.get("source") if isinstance(receipt.get("source"), dict) else {}
    if str(source.get("workspaceId") or "") != workspace_id:
        raise ValueError("Query Receipt belongs to a different workspace")
    if str(receipt.get("status") or "") == "executed":
        source_state = current_query_receipt_source_state(connection, workspace_id, receipt)
        if not source_state.get("matchesReceipt"):
            blockers = ", ".join(source_state.get("blockers") or ["query-receipt-drifted"])
            raise ValueError(f"Analysis Unit cannot consume a drifted Query Receipt: {blockers}")
    normalized_rows = _safe_rows(rows)
    result_binding = receipt.get("resultBinding") if isinstance(receipt.get("resultBinding"), dict) else None
    if not result_binding or not result_binding.get("resultFingerprint"):
        raise ValueError("Query Receipt does not contain a verified result fingerprint")
    supplied_fingerprint = _fingerprint(normalized_rows)
    if supplied_fingerprint != str(result_binding.get("resultFingerprint")):
        raise ValueError("Analysis Unit rows do not match the Query Receipt result fingerprint")
    shape = _shape(receipt, normalized_rows)
    kind = _infer_kind(requested_kind, receipt, shape)
    validation = _validate(kind, receipt, shape, normalized_rows)
    calculation = _calculation(kind, shape, normalized_rows)
    result_fingerprint = supplied_fingerprint
    selection = receipt.get("selection") if isinstance(receipt.get("selection"), dict) else {}
    selected_groups = [
        item
        for item in selection.get("groups") or []
        if isinstance(item, dict) and item.get("field")
    ]
    dimensions = [
        {
            "tableKey": item.get("tableKey"),
            "field": item.get("field"),
            "sourceResultColumn": item.get("outputName"),
            "resultColumn": (
                item.get("outputName")
                if item.get("outputName") in shape["columns"]
                else shape["dimensionColumn"]
            ),
        }
        for item in selected_groups
    ]
    if not dimensions and shape["dimensionColumn"]:
        dimensions = [{
            "field": selection.get("group"),
            "resultColumn": shape["dimensionColumn"],
        }]
    grain = {
        "dimensions": dimensions,
        "measures": [{
            "field": selection.get("measure"),
            "resultColumn": shape["measureColumn"],
            "aggregation": selection.get("aggregation"),
        }] if shape["measureColumn"] else [],
        "sourceTableKey": source.get("tableKey"),
        "sourceTableKeys": source.get("tableKeys") or ([source.get("tableKey")] if source.get("tableKey") else []),
        "schemaFingerprint": source.get("schemaFingerprint"),
        "relationshipPathFingerprint": source.get("relationshipPathFingerprint"),
    }
    definition = {
        "queryReceiptKey": receipt.get("receiptKey"),
        "kind": kind,
        "grain": grain,
        "shape": shape,
        "resultFingerprint": result_fingerprint,
    }
    definition_fingerprint = _fingerprint(definition)
    unit_key = f"analysis_unit_{definition_fingerprint[:20]}"
    created_at = now_iso()
    unit = {
        "schema": ANALYSIS_UNIT_SCHEMA,
        "unitKey": unit_key,
        "workspaceId": workspace_id,
        "queryReceiptKey": receipt.get("receiptKey"),
        "kind": kind,
        "status": validation["status"],
        "title": str(title or receipt.get("request") or kind),
        "definitionFingerprint": definition_fingerprint,
        "resultFingerprint": result_fingerprint,
        "grain": grain,
        "shape": shape,
        "rows": normalized_rows,
        "calculation": calculation,
        "validation": validation,
        "createdAt": created_at,
        "updatedAt": created_at,
    }
    chart_adapter = adapt_chart(unit, preferred_chart)
    unit["chartAdapter"] = chart_adapter
    existing = connection.execute(
        "SELECT created_at FROM analysis_units WHERE workspace_id = ? AND unit_key = ?",
        (workspace_id, unit_key),
    ).fetchone()
    if existing:
        unit["createdAt"] = existing["created_at"]
    connection.execute(
        """
        INSERT INTO analysis_units(
          unit_key, workspace_id, query_receipt_key, kind, status, title,
          definition_fingerprint, result_fingerprint, grain_json, shape_json,
          result_rows_json, calculation_json, validation_json, chart_adapter_json,
          created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(workspace_id, unit_key) DO UPDATE SET
          status = excluded.status,
          title = excluded.title,
          grain_json = excluded.grain_json,
          shape_json = excluded.shape_json,
          result_rows_json = excluded.result_rows_json,
          calculation_json = excluded.calculation_json,
          validation_json = excluded.validation_json,
          chart_adapter_json = excluded.chart_adapter_json,
          updated_at = excluded.updated_at
        """,
        (
            unit_key, workspace_id, receipt.get("receiptKey"), kind, unit["status"], unit["title"],
            definition_fingerprint, result_fingerprint, _canonical_json(grain), _canonical_json(shape),
            _canonical_json(normalized_rows), _canonical_json(calculation), _canonical_json(validation),
            _canonical_json(chart_adapter), unit["createdAt"], unit["updatedAt"],
        ),
    )
    return unit


def _row_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "schema": ANALYSIS_UNIT_SCHEMA,
        "unitKey": row["unit_key"],
        "workspaceId": row["workspace_id"],
        "queryReceiptKey": row["query_receipt_key"],
        "kind": row["kind"],
        "status": row["status"],
        "title": row["title"],
        "definitionFingerprint": row["definition_fingerprint"],
        "resultFingerprint": row["result_fingerprint"],
        "grain": json.loads(row["grain_json"]),
        "shape": json.loads(row["shape_json"]),
        "rows": json.loads(row["result_rows_json"]),
        "calculation": json.loads(row["calculation_json"]),
        "validation": json.loads(row["validation_json"]),
        "chartAdapter": json.loads(row["chart_adapter_json"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def get_analysis_unit(connection: sqlite3.Connection, workspace_id: str, unit_key: str) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM analysis_units WHERE workspace_id = ? AND unit_key = ?",
        (workspace_id, unit_key),
    ).fetchone()
    return _row_payload(row) if row else None


def analysis_unit_consumer_state(
    connection: sqlite3.Connection,
    workspace_id: str,
    unit: dict[str, Any],
) -> dict[str, Any]:
    receipt_key = str(unit.get("queryReceiptKey") or "")
    receipt = get_query_receipt(connection, workspace_id, receipt_key) if receipt_key else None
    blockers: list[str] = []
    source_state = None
    frozen_verification = verify_analysis_unit(unit)
    if not frozen_verification.get("ok"):
        blockers.append("analysis-unit-frozen-result-drifted")
    if not receipt:
        blockers.append("analysis-unit-query-receipt-missing")
    else:
        if str(receipt.get("status") or "") != "executed":
            blockers.append("analysis-unit-query-receipt-not-executed")
        source_state = current_query_receipt_source_state(connection, workspace_id, receipt)
        blockers.extend(source_state.get("blockers") or [])
        result_binding = receipt.get("resultBinding") if isinstance(receipt.get("resultBinding"), dict) else {}
        if str(result_binding.get("resultFingerprint") or "") != str(unit.get("resultFingerprint") or ""):
            blockers.append("analysis-unit-receipt-result-binding-mismatch")
    blockers = list(dict.fromkeys(blockers))
    return {
        "schema": "aibi-analysis-unit-consumer-state/v1",
        "unitKey": unit.get("unitKey"),
        "queryReceiptKey": receipt_key,
        "usable": not blockers,
        "blockers": blockers,
        "queryReceiptStatus": receipt.get("status") if receipt else "missing",
        "sourceState": source_state,
        "frozenVerification": frozen_verification,
    }


def _analysis_unit_consumer_view(unit: dict[str, Any], consumer_state: dict[str, Any]) -> dict[str, Any]:
    view = {**unit, "freshness": consumer_state}
    if consumer_state.get("usable"):
        return view
    stored_validation = unit.get("validation") if isinstance(unit.get("validation"), dict) else {}
    blockers = list(dict.fromkeys([
        *(stored_validation.get("blockers") or []),
        *(consumer_state.get("blockers") or []),
    ]))
    validation = {
        **stored_validation,
        "status": "blocked",
        "blockers": blockers,
    }
    stored_adapter = unit.get("chartAdapter") if isinstance(unit.get("chartAdapter"), dict) else {}
    adapter = {
        **stored_adapter,
        "status": "blocked",
        "chartType": None,
        "config": {},
        "blockers": list(dict.fromkeys([*(stored_adapter.get("blockers") or []), *blockers])),
    }
    return {**view, "status": "blocked", "validation": validation, "chartAdapter": adapter}


def analysis_unit_build_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    try:
        rows = json.loads(str(args.rows_json or "[]"))
    except json.JSONDecodeError as exc:
        raise ValueError("rows-json must be a JSON array") from exc
    with closing(open_db()) as connection:
        if connection.in_transaction:
            connection.commit()
        # Hold the same write-capable snapshot from the freshness proof through
        # persistence. Otherwise an import can commit after the guard and before
        # the Analysis Unit is stored, returning a unit that is already stale.
        connection.execute("BEGIN IMMEDIATE")
        workspace_id = active_workspace_id(connection)
        receipt = get_query_receipt(connection, workspace_id, args.receipt)
        if not receipt:
            raise ValueError(f"Unknown query receipt in active workspace: {args.receipt}")
        if str(receipt.get("status") or "") != "executed":
            raise ValueError("Analysis Unit build requires an executed Query Receipt")
        unit = create_analysis_unit(
            connection,
            workspace_id=workspace_id,
            receipt=receipt,
            rows=rows,
            requested_kind=args.kind,
            title=args.title,
            preferred_chart=args.preferred_chart,
            now_iso=now_iso,
        )
        connection.commit()
    return {"ok": unit["status"] == "ready", "analysisUnit": unit, "chartAdapter": unit["chartAdapter"]}


def analysis_units_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with closing(open_db()) as connection:
        workspace_id = active_workspace_id(connection)
        if args.unit:
            unit = get_analysis_unit(connection, workspace_id, args.unit)
            if not unit:
                raise ValueError(f"Unknown Analysis Unit in active workspace: {args.unit}")
            consumer_state = analysis_unit_consumer_state(connection, workspace_id, unit)
            return {
                "ok": bool(consumer_state["usable"]),
                "analysisUnit": _analysis_unit_consumer_view(unit, consumer_state),
                "freshness": consumer_state,
            }
        clauses = ["workspace_id = ?"]
        params: list[Any] = [workspace_id]
        if args.receipt:
            clauses.append("query_receipt_key = ?")
            params.append(args.receipt)
        params.append(max(1, min(int(args.limit), 200)))
        rows = connection.execute(
            f"SELECT * FROM analysis_units WHERE {' AND '.join(clauses)} ORDER BY updated_at DESC LIMIT ?",
            params,
        ).fetchall()
        units = []
        stale_count = 0
        for row in rows:
            unit = _row_payload(row)
            consumer_state = analysis_unit_consumer_state(connection, workspace_id, unit)
            view = _analysis_unit_consumer_view(unit, consumer_state)
            stale_count += 0 if consumer_state["usable"] else 1
            units.append({key: value for key, value in view.items() if key not in {"rows", "calculation"}})
    return {
        "ok": stale_count == 0,
        "analysisUnits": units,
        "count": len(units),
        "usableCount": len(units) - stale_count,
        "staleCount": stale_count,
    }


def analysis_unit_verify_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with closing(open_db()) as connection:
        workspace_id = active_workspace_id(connection)
        unit = get_analysis_unit(connection, workspace_id, args.unit)
        if not unit:
            raise ValueError(f"Unknown Analysis Unit in active workspace: {args.unit}")
        consumer_state = analysis_unit_consumer_state(connection, workspace_id, unit)
    verification = verify_analysis_unit(unit)
    source_state = consumer_state.get("sourceState")
    source_current = bool(consumer_state.get("usable"))
    verification["sourceCurrent"] = source_current
    verification["sourceState"] = source_state
    verification["freshness"] = consumer_state
    verification["ok"] = bool(verification["ok"] and source_current)
    if not source_current:
        verification["blockers"] = list(dict.fromkeys([
            "analysis-unit-source-drifted",
            *(consumer_state.get("blockers") or []),
        ]))
    return verification


def verify_analysis_unit(unit: dict[str, Any]) -> dict[str, Any]:
    recalculated = _calculation(unit["kind"], unit["shape"], unit["rows"])
    rows_match = _fingerprint(unit["rows"]) == unit["resultFingerprint"]
    calculation_match = _fingerprint(recalculated) == _fingerprint(unit["calculation"])
    return {
        "ok": rows_match and calculation_match,
        "schema": "aibi-analysis-unit-verification/v1",
        "unitKey": unit["unitKey"],
        "queryReceiptKey": unit["queryReceiptKey"],
        "rowsFingerprintMatches": rows_match,
        "calculationMatches": calculation_match,
        "recalculationFingerprint": _fingerprint(recalculated),
    }


def chart_adapt_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with closing(open_db()) as connection:
        workspace_id = active_workspace_id(connection)
        unit = get_analysis_unit(connection, workspace_id, args.unit)
        if not unit:
            raise ValueError(f"Unknown Analysis Unit in active workspace: {args.unit}")
        consumer_state = analysis_unit_consumer_state(connection, workspace_id, unit)
    adapter = adapt_chart(unit, args.preferred_chart)
    if not consumer_state["usable"]:
        adapter = {
            **adapter,
            "status": "blocked",
            "chartType": None,
            "config": {},
            "blockers": list(dict.fromkeys([
                *(adapter.get("blockers") or []),
                *(consumer_state.get("blockers") or []),
            ])),
        }
    return {
        "ok": adapter["status"] == "ready",
        "chartAdapter": adapter,
        "analysisUnitRef": {
            "unitKey": unit["unitKey"],
            "resultFingerprint": unit["resultFingerprint"],
            "freshness": consumer_state,
        },
    }


def attach_analysis_unit(
    result: dict[str, Any],
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    receipt = result.get("queryPlanReceipt")
    answer = result.get("answerCard") if isinstance(result.get("answerCard"), dict) else {}
    if not isinstance(receipt, dict):
        receipt = answer.get("queryPlanReceipt")
    rows = result.get("rows") if isinstance(result.get("rows"), list) else answer.get("rows")
    if not isinstance(receipt, dict) or not isinstance(rows, list):
        return result
    request = str(receipt.get("request") or "")
    preferred = ""
    for token, chart in (("柱状", "bar"), ("bar", "bar"), ("折线", "line"), ("line", "line"), ("饼图", "pie"), ("pie", "pie"), ("指标卡", "metric")):
        if token.lower() in request.lower():
            preferred = chart
            break
    with closing(open_db()) as connection:
        source = receipt.get("source") if isinstance(receipt.get("source"), dict) else {}
        workspace_id = str(source.get("workspaceId") or active_workspace_id(connection))
        unit = create_analysis_unit(
            connection,
            workspace_id=workspace_id,
            receipt=receipt,
            rows=rows,
            requested_kind="auto",
            preferred_chart=preferred,
            now_iso=now_iso,
        )
        business_understanding = result.get("businessUnderstanding") if isinstance(result.get("businessUnderstanding"), dict) else {}
        method_plan = business_understanding.get("methodPlan") if isinstance(business_understanding.get("methodPlan"), dict) else {}
        readiness = None
        if method_plan.get("skillId") == "forecast-readiness":
            slots = business_understanding.get("slots") if isinstance(business_understanding.get("slots"), dict) else {}
            horizon_slot = slots.get("forecast-horizon") if isinstance(slots.get("forecast-horizon"), dict) else {}
            cutoff_slot = slots.get("forecast-cutoff") if isinstance(slots.get("forecast-cutoff"), dict) else {}
            horizon_match = re.search(r"\d+", str(horizon_slot.get("value") or ""))
            if horizon_match:
                from forecast_readiness_service import assess_forecast_readiness
                readiness = assess_forecast_readiness(
                    unit,
                    freshness=analysis_unit_consumer_state(connection, workspace_id, unit),
                    horizon=int(horizon_match.group(0)),
                    declared_cutoff=cutoff_slot.get("value"),
                )
        connection.commit()
    result["analysisUnit"] = unit
    result["chartAdapter"] = unit["chartAdapter"]
    if readiness:
        result["forecastReadiness"] = readiness
    if isinstance(answer, dict):
        answer["analysisUnitRef"] = {
            "unitKey": unit["unitKey"],
            "kind": unit["kind"],
            "status": unit["status"],
            "resultFingerprint": unit["resultFingerprint"],
        }
        answer["chartAdapter"] = unit["chartAdapter"]
        if readiness:
            answer["forecastReadinessRef"] = {
                "status": readiness["status"],
                "fingerprint": readiness["fingerprint"],
                "canGenerateForecast": False,
            }
    return result
