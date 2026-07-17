from __future__ import annotations

from pathlib import Path
from typing import Any


B_WIDGET_TYPES = ["metric", "bar", "line", "pie", "table", "text", "slicer"]
B_RELATIONSHIP_WIDGET_TYPES = ["metric", "bar", "line", "pie", "table"]
B_VALUE_FORMATS = ["auto", "plain", "compact", "currency", "percent"]
B_SLICER_DISPLAYS = ["list", "dropdown", "range"]
B_COLOR_PALETTES = ["default", "fresh", "warm", "contrast", "mono"]
B_BAR_ORIENTATIONS = ["vertical", "horizontal"]
B_PIE_SHAPES = ["donut", "pie"]
B_SORT_BY = ["metric", "dimension"]
B_RANKING_MODES = ["standard", "ranked"]
B_DASHBOARD_FILTER_OPERATORS = ["contains", "equals", "in", "between", "notEquals", "gt", "gte", "lt", "lte", "empty", "notEmpty"]
B_DATA_MODES = ["table", "view", "relationship"]
B_DASHBOARD_WIDGET_CATALOG = [
    {
        "type": "metric",
        "label": {"zh": "指标卡", "en": "Metric"},
        "description": {"zh": "核心指标和汇总值", "en": "Core KPI and aggregate value"},
        "dataModes": ["table", "view", "relationship"],
        "supports": ["aggregation", "valueFormat", "filters", "crossFilter", "drillDown"],
        "defaultLayout": {"w": 3, "h": 4, "minW": 2, "minH": 4},
    },
    {
        "type": "bar",
        "label": {"zh": "柱状图", "en": "Bar"},
        "description": {"zh": "分类对比和排行", "en": "Category comparison and ranking"},
        "dataModes": ["table", "view", "relationship"],
        "supports": ["orientation", "rankingMode", "palette", "legend", "axis", "filters"],
        "defaultLayout": {"w": 6, "h": 7, "minW": 4, "minH": 5},
    },
    {
        "type": "line",
        "label": {"zh": "折线图", "en": "Line"},
        "description": {"zh": "趋势和波动", "en": "Trend and movement"},
        "dataModes": ["table", "view", "relationship"],
        "supports": ["timeGrain", "lineSmooth", "areaFill", "palette", "axis", "filters"],
        "defaultLayout": {"w": 6, "h": 7, "minW": 4, "minH": 5},
    },
    {
        "type": "pie",
        "label": {"zh": "环形图", "en": "Pie"},
        "description": {"zh": "构成占比分析", "en": "Composition analysis"},
        "dataModes": ["table", "view", "relationship"],
        "supports": ["pieShape", "palette", "legend", "dataLabel", "filters"],
        "defaultLayout": {"w": 6, "h": 7, "minW": 4, "minH": 5},
    },
    {
        "type": "table",
        "label": {"zh": "明细表", "en": "Table"},
        "description": {"zh": "筛选后的明细数据", "en": "Filtered detail data"},
        "dataModes": ["table", "view", "relationship"],
        "supports": ["columns", "pagination", "filters", "drillDown"],
        "defaultLayout": {"w": 8, "h": 8, "minW": 5, "minH": 6},
    },
    {
        "type": "text",
        "label": {"zh": "文本", "en": "Text"},
        "description": {"zh": "结论、说明和备注", "en": "Narrative note and annotation"},
        "dataModes": ["table"],
        "supports": ["textContent", "evidence"],
        "defaultLayout": {"w": 4, "h": 4, "minW": 3, "minH": 3},
    },
    {
        "type": "slicer",
        "label": {"zh": "切片器", "en": "Slicer"},
        "description": {"zh": "画布内筛选控件", "en": "Canvas filter control"},
        "dataModes": ["table", "view"],
        "supports": ["list", "dropdown", "range", "multiSelect", "search"],
        "defaultLayout": {"w": 4, "h": 5, "minW": 3, "minH": 4},
    },
]


def build_dashboard_widget_catalog_payload(
    *,
    metadata_store: Path,
    latest_source_intelligence_run: dict[str, Any] | None,
    workspace_counts: dict[str, int],
) -> dict[str, Any]:
    return {
        "ok": True,
        "source": {
            "project": "AIBI-C",
            "contractSource": [
                "src/types.ts DashboardWidget",
                "src/dashboardCanvasModel.ts widget restore/filter/layout helpers",
                "tools/aibi_cli.py add-widget/add-relationship-widget/query-table command surface",
            ],
        },
        "integration": {
            "project": "AIBI-C",
            "metadataStore": str(metadata_store),
            "queryRuntime": "DuckDB whitelist aggregate runtime with SQLite fallback",
            "agentPolicy": "ask returns plans and action drafts; writes require explicit confirmation",
            "latestSourceIntelligenceRun": latest_source_intelligence_run,
            "workspaceCounts": workspace_counts,
        },
        "widgetTypes": B_WIDGET_TYPES,
        "relationshipWidgetTypes": B_RELATIONSHIP_WIDGET_TYPES,
        "dataModes": B_DATA_MODES,
        "valueFormats": B_VALUE_FORMATS,
        "slicerDisplays": B_SLICER_DISPLAYS,
        "colorPalettes": B_COLOR_PALETTES,
        "barOrientations": B_BAR_ORIENTATIONS,
        "pieShapes": B_PIE_SHAPES,
        "sortBy": B_SORT_BY,
        "rankingModes": B_RANKING_MODES,
        "filterOperators": B_DASHBOARD_FILTER_OPERATORS,
        "catalog": B_DASHBOARD_WIDGET_CATALOG,
    }


def widget_config_from_options(options: dict[str, Any]) -> dict[str, Any]:
    widget_type = str(options.get("type") or "bar")

    def option_bool(key: str, default: bool) -> bool:
        value = options.get(key)
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    config = {
        "schemaVersion": 1,
        "dataMode": options.get("dataMode") or ("view" if options.get("viewKey") else "table"),
        "subtitle": options.get("subtitle") or options.get("tableName") or options.get("tableKey") or "",
        "dimension": options.get("dimension") or "",
        "measure": options.get("measure") or "",
        "aggregation": options.get("aggregation") or options.get("agg") or ("count" if widget_type in {"table", "slicer", "text"} else "sum"),
        "sortBy": options.get("sortBy") or "metric",
        "sortDirection": options.get("sortDirection") or ("asc" if widget_type == "line" else "desc"),
        "topN": int(options.get("topN") or (100 if widget_type == "table" else 12)),
        "valueFormat": options.get("valueFormat") or "auto",
        "decimalPlaces": int(options.get("decimalPlaces") or 2),
        "tableColumnLimit": int(options.get("tableColumnLimit") or 6),
        "slicerDisplay": options.get("slicerDisplay") or "list",
        "slicerMultiSelect": option_bool("slicerMultiSelect", False),
        "slicerSearchable": option_bool("slicerSearchable", True),
        "filters": options.get("filters") if isinstance(options.get("filters"), list) else [],
        "showLegend": option_bool("showLegend", True),
        "showAxis": option_bool("showAxis", True),
        "showDataLabel": option_bool("showDataLabel", False),
        "rankingMode": options.get("rankingMode") or "standard",
        "colorPalette": options.get("colorPalette") or "default",
        "barOrientation": options.get("barOrientation") or "vertical",
        "lineSmooth": option_bool("lineSmooth", True),
        "areaFill": option_bool("areaFill", False),
        "pieShape": options.get("pieShape") or "donut",
        "crossFilter": option_bool("crossFilter", widget_type != "text"),
        "drillDown": option_bool("drillDown", widget_type not in {"text", "slicer"}),
        "globalFilterTarget": option_bool("globalFilterTarget", False),
    }
    for key in [
        "viewKey",
        "columns",
        "textContent",
        "xAxisTitle",
        "yAxisTitle",
        "legendTitle",
        "sourceAction",
        "sourceRunKey",
        "sourceRunLabel",
        "sourceMode",
        "analysisId",
        "chartTypeHint",
        "requiredSemantics",
        "sample",
        "evidenceRefs",
    ]:
        if options.get(key) not in (None, ""):
            config[key] = options[key]
    return config


def widget_style_options_from_args(args: Any) -> dict[str, Any]:
    options: dict[str, Any] = {}
    for arg_name, config_key in [
        ("sort_by", "sortBy"),
        ("sort_direction", "sortDirection"),
        ("decimal_places", "decimalPlaces"),
        ("table_column_limit", "tableColumnLimit"),
        ("slicer_display", "slicerDisplay"),
        ("ranking_mode", "rankingMode"),
        ("color_palette", "colorPalette"),
        ("bar_orientation", "barOrientation"),
        ("pie_shape", "pieShape"),
        ("x_axis_title", "xAxisTitle"),
        ("y_axis_title", "yAxisTitle"),
        ("legend_title", "legendTitle"),
    ]:
        value = getattr(args, arg_name, None)
        if value is not None and value != "":
            options[config_key] = value
    for arg_name, config_key in [
        ("slicer_multi_select", "slicerMultiSelect"),
        ("slicer_searchable", "slicerSearchable"),
        ("show_legend", "showLegend"),
        ("show_axis", "showAxis"),
        ("show_data_label", "showDataLabel"),
        ("line_smooth", "lineSmooth"),
        ("area_fill", "areaFill"),
        ("cross_filter", "crossFilter"),
        ("drill_down", "drillDown"),
        ("global_filter_target", "globalFilterTarget"),
    ]:
        value = getattr(args, arg_name, None)
        if value is not None:
            options[config_key] = value
    return options
