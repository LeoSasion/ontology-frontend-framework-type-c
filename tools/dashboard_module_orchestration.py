from __future__ import annotations

import sqlite3
from typing import Any, Callable

from dashboard_widget_contracts import B_WIDGET_TYPES, widget_config_from_options


def dashboard_module_widget_from_payload(
    connection: sqlite3.Connection,
    dashboard_key: str,
    item: dict[str, Any],
    index: int,
    default_table_key: str,
    layout_by_id: dict[str, dict[str, Any]],
    *,
    workspace_id: str,
    preferred_table_key: Callable[[sqlite3.Connection, str | None], str],
    table_display_name: Callable[[sqlite3.Connection, str], str],
    unique_key: Callable[[str], str],
) -> dict[str, Any]:
    config = item.get("config") if isinstance(item.get("config"), dict) else {}
    widget_key = str(
        item.get("widget_key")
        or item.get("widgetKey")
        or item.get("id")
        or config.get("widgetKey")
        or unique_key("widget")
    ).strip()
    widget_type = str(item.get("widget_type") or item.get("type") or config.get("type") or "bar").strip()
    if widget_type not in B_WIDGET_TYPES:
        raise ValueError(f"Unsupported widget type in module save: {widget_type}")
    title = str(item.get("title") or config.get("title") or f"{widget_type} {index + 1}").strip()
    is_text_widget = widget_type == "text"
    raw_table_key = str(
        item.get("table_key")
        or item.get("tableKey")
        or config.get("tableKey")
        or default_table_key
        or ""
    ).strip()
    table_key = "" if is_text_widget else preferred_table_key(connection, raw_table_key or default_table_key or None)
    table_name = table_display_name(connection, table_key) if table_key else ""
    options: dict[str, Any] = {
        **config,
        "type": widget_type,
        "tableKey": table_key,
        "tableName": table_name,
    }
    for source_key, target_key in [
        ("subtitle", "subtitle"),
        ("textContent", "textContent"),
        ("dataMode", "dataMode"),
        ("viewKey", "viewKey"),
        ("relationship", "relationship"),
        ("dimension", "dimension"),
        ("group", "dimension"),
        ("timeGrain", "timeGrain"),
        ("measure", "measure"),
        ("metricKey", "metricKey"),
        ("metricName", "metricName"),
        ("metricFormulaText", "metricFormulaText"),
        ("metricFormulaName", "metricFormulaName"),
        ("metricFormulaDraftPrompt", "metricFormulaDraftPrompt"),
        ("aggregation", "aggregation"),
        ("agg", "aggregation"),
        ("sortBy", "sortBy"),
        ("sortDirection", "sortDirection"),
        ("topN", "topN"),
        ("valueFormat", "valueFormat"),
        ("decimalPlaces", "decimalPlaces"),
        ("tableColumnLimit", "tableColumnLimit"),
        ("slicerDisplay", "slicerDisplay"),
        ("slicerMultiSelect", "slicerMultiSelect"),
        ("slicerSearchable", "slicerSearchable"),
        ("filters", "filters"),
        ("showLegend", "showLegend"),
        ("showAxis", "showAxis"),
        ("showDataLabel", "showDataLabel"),
        ("rankingMode", "rankingMode"),
        ("xAxisTitle", "xAxisTitle"),
        ("yAxisTitle", "yAxisTitle"),
        ("legendTitle", "legendTitle"),
        ("sourceRunKey", "sourceRunKey"),
        ("sourceRunLabel", "sourceRunLabel"),
        ("sourceMode", "sourceMode"),
        ("analysisId", "analysisId"),
        ("chartTypeHint", "chartTypeHint"),
        ("requiredSemantics", "requiredSemantics"),
        ("sample", "sample"),
        ("evidenceRefs", "evidenceRefs"),
        ("colorPalette", "colorPalette"),
        ("barOrientation", "barOrientation"),
        ("lineSmooth", "lineSmooth"),
        ("areaFill", "areaFill"),
        ("pieShape", "pieShape"),
        ("crossFilter", "crossFilter"),
        ("drillDown", "drillDown"),
        ("globalFilterTarget", "globalFilterTarget"),
        ("columns", "columns"),
    ]:
        if source_key in item and item[source_key] is not None:
            options[target_key] = item[source_key]
    next_config = widget_config_from_options(options)
    for key in ["timeGrain", "metricKey", "metricName", "metricFormulaText", "metricFormulaName", "metricFormulaDraftPrompt", "relationship"]:
        if options.get(key) not in (None, ""):
            next_config[key] = options[key]
    if is_text_widget:
        next_config["dataMode"] = "table"
        next_config["filters"] = []
        next_config["crossFilter"] = False
        next_config["drillDown"] = False
        next_config["globalFilterTarget"] = False
    widget_layout = layout_by_id.get(widget_key) or layout_by_id.get(str(item.get("id") or ""))
    if widget_layout:
        next_config["layout"] = widget_layout
    elif isinstance(config.get("layout"), dict):
        next_config["layout"] = config["layout"]
    return {
        "widget_key": widget_key,
        "workspace_id": workspace_id,
        "dashboard_key": dashboard_key,
        "widget_type": widget_type,
        "title": title,
        "table_key": table_key,
        "config": next_config,
        "sort_order": (index + 1) * 10,
    }


def namespaced_dashboard_widget_id(dashboard_key: str, widget_id: Any, index: int) -> str:
    base = str(widget_id or f"widget_{index + 1}").strip()
    prefix = f"{dashboard_key}__"
    return base if base.startswith(prefix) else f"{prefix}{base}"
