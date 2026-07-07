from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Callable

from dashboard_module_orchestration import dashboard_module_widget_from_payload, namespaced_dashboard_widget_id
from dashboard_save_transactions import save_dashboard_with_widgets
from erp_dashboard_unit_library import (
    ERP_UNIT_LIBRARY_TEMPLATE_KEY,
    build_erp_dashboard_unit_templates,
    prompt_prefers_erp_unit_library,
)

BUSINESS_TEMPLATE_KEY = "business"
COST_MONITOR_TEMPLATE_KEY = "cost-monitor"
COST_MONITOR_FUNDS_FIELDS = {"动账时间", "动账方向", "动账金额", "动账场景"}
COST_MONITOR_POLICY_FIELDS = {"下单时间", "支付保费"}
COST_MONITOR_INCOME_FORMULA = (
    "SUM(COALESCE([订单实付应结],0) + COALESCE([实际平台补贴_运费],0) + "
    "COALESCE([实际平台补贴],0) + COALESCE([其他平台补贴],0) + "
    "COALESCE([以旧换新抵扣],0) + COALESCE([政府补贴平台垫资],0) + "
    "COALESCE([实际达人补贴],0) + COALESCE([实际抖音支付补贴],0) + "
    "COALESCE([实际抖音月付营销补贴],0) + COALESCE([银行补贴],0) + "
    "COALESCE([订单退款],0))"
)


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _field_name(field: dict[str, Any]) -> str:
    return str(field.get("fieldName") or field.get("name") or field.get("column") or "").strip()


def source_profile_table_inputs(connection: sqlite3.Connection, workspace_id: str) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    try:
        row = connection.execute(
            """
            SELECT output_dir, manifest_json
            FROM source_intelligence_runs
            WHERE workspace_id = ?
            ORDER BY created_at DESC, run_key DESC
            LIMIT 1
            """,
            (workspace_id,),
        ).fetchone()
    except sqlite3.Error:
        return [], {}
    if not row:
        return [], {}
    try:
        manifest = json.loads(str(row["manifest_json"] or "{}"))
    except json.JSONDecodeError:
        manifest = {}
    outputs = manifest.get("outputs") if isinstance(manifest.get("outputs"), dict) else {}
    profile_name = str(outputs.get("sourceProfile") or "source-profile-generic.json")
    profile = _read_json_file(Path(str(row["output_dir"])) / profile_name)
    tables = profile.get("tables") if isinstance(profile.get("tables"), list) else []
    table_rows: list[dict[str, Any]] = []
    fields_by_key: dict[str, dict[str, Any]] = {}
    for table in tables:
        if not isinstance(table, dict):
            continue
        table_key = str(table.get("tableKey") or table.get("table_key") or "").strip()
        if not table_key:
            continue
        raw_fields = table.get("fields") if isinstance(table.get("fields"), list) else []
        fields = [field for field in raw_fields if isinstance(field, dict) and _field_name(field)]
        columns = [_field_name(field) for field in fields]
        measures = [
            _field_name(field)
            for field in fields
            if str(field.get("usage") or "").lower() == "aggregatable"
            or str(field.get("role") or "").lower() == "measure"
            or str(field.get("type") or "").lower() in {"number", "numeric", "integer", "float"}
        ]
        dimensions = [
            _field_name(field)
            for field in fields
            if str(field.get("usage") or "").lower() in {"groupable", "filterable", "join_key"}
            or str(field.get("role") or "").lower() in {"dimension", "identity", "identity_key"}
        ]
        filterable = [
            _field_name(field)
            for field in fields
            if str(field.get("usage") or "").lower() in {"groupable", "filterable", "join_key"}
            or str(field.get("role") or "").lower() in {"dimension", "identity", "identity_key"}
        ]
        dates = [
            _field_name(field)
            for field in fields
            if str(field.get("role") or "").lower() == "event_time"
            or str(field.get("type") or "").lower() in {"date", "datetime", "time"}
            or str(field.get("semantic") or "").lower() in {"paid_at", "refund_at", "created_at", "date"}
        ]
        table_rows.append({
            "table_key": table_key,
            "display_name": str(table.get("label") or table.get("displayName") or table_key),
            "source_file": str(table.get("sourcePath") or ""),
            "row_count": int(table.get("rowCount") or 0),
            "column_count": int(table.get("columnCount") or len(columns)),
            "workspace_id": workspace_id,
            "physical_table": "",
        })
        fields_by_key[table_key] = {
            "columns": columns,
            "measures": measures,
            "dimensions": dimensions,
            "filterable": filterable,
            "dates": dates,
            "measure": measures[0] if measures else "",
            "dimension": dimensions[0] if dimensions else (filterable[0] if filterable else (columns[0] if columns else "")),
            "date": dates[0] if dates else "",
        }
    table_rows.sort(key=lambda item: (-int(item.get("row_count") or 0), str(item.get("table_key") or "")))
    return table_rows, fields_by_key
COST_MONITOR_NET_FORMULA = "SUM(IF([动账方向]=\"出账\",-ABS([动账金额]),IF([动账方向]=\"入账\",ABS([动账金额]),[动账金额])))"


def template_widget_layout(widget_type: str, index: int) -> dict[str, Any]:
    sizes = {
        "metric": {"w": 3, "h": 2, "minW": 2, "minH": 2},
        "bar": {"w": 4, "h": 4, "minW": 3, "minH": 3},
        "line": {"w": 5, "h": 4, "minW": 3, "minH": 3},
        "pie": {"w": 4, "h": 4, "minW": 3, "minH": 3},
        "table": {"w": 7, "h": 5, "minW": 5, "minH": 4},
        "text": {"w": 5, "h": 3, "minW": 3, "minH": 3},
        "slicer": {"w": 4, "h": 3, "minW": 3, "minH": 3},
    }
    size = sizes.get(widget_type, sizes["bar"])
    return {
        "x": (index % 3) * 4,
        "y": (index // 3) * 4,
        **size,
    }


def table_template_fields(
    connection: sqlite3.Connection,
    table_key: str,
    *,
    registry_for_table: Callable[[sqlite3.Connection, str], sqlite3.Row | None],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    field_names_by_usage: Callable[[sqlite3.Connection, str, str], list[str]],
    field_names_by_role: Callable[[sqlite3.Connection, str, str], list[str]],
) -> dict[str, Any]:
    registry = registry_for_table(connection, table_key)
    columns = table_columns(connection, registry["physical_table"]) if registry else []
    measures = [field for field in field_names_by_usage(connection, table_key, "aggregatable") if field in columns]
    dimensions = [field for field in field_names_by_usage(connection, table_key, "groupable") if field in columns]
    filterable = [field for field in field_names_by_usage(connection, table_key, "filterable") if field in columns]
    dates = [field for field in field_names_by_role(connection, table_key, "event_time") if field in columns]
    return {
        "columns": columns,
        "measures": measures,
        "dimensions": dimensions,
        "filterable": filterable,
        "dates": dates,
        "measure": measures[0] if measures else "",
        "dimension": dimensions[0] if dimensions else (filterable[0] if filterable else (columns[0] if columns else "")),
        "date": dates[0] if dates else "",
    }


def _table_fields_by_key(
    connection: sqlite3.Connection,
    table_rows: list[dict[str, Any]],
    table_template_fields: Callable[[sqlite3.Connection, str], dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {row["table_key"]: table_template_fields(connection, row["table_key"]) for row in table_rows}


def _find_table_by_fields(
    table_rows: list[dict[str, Any]],
    fields_by_key: dict[str, dict[str, Any]],
    required_fields: set[str],
    preferred_table_key_value: str = "",
) -> dict[str, Any] | None:
    if preferred_table_key_value:
        preferred = next((row for row in table_rows if row["table_key"] == preferred_table_key_value), None)
        if preferred and required_fields.issubset(set(fields_by_key.get(preferred["table_key"], {}).get("columns", []))):
            return preferred
    return next(
        (
            row
            for row in table_rows
            if required_fields.issubset(set(fields_by_key.get(row["table_key"], {}).get("columns", [])))
        ),
        None,
    )


def _cost_monitor_widget(
    *,
    item_id: str,
    category: str,
    table: dict[str, Any],
    widget_type: str,
    title: str,
    reason: str,
    options: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": f"cost_monitor_{item_id}",
        "category": category,
        "type": widget_type,
        "title": title,
        "reason": reason,
        "tableKey": table["table_key"],
        "tableName": table["display_name"],
        "preset": {
            "type": widget_type,
            "title": title,
            "tableKey": table["table_key"],
            "subtitle": options.pop("subtitle", f"{category} · {table['display_name']}"),
            "valueFormat": "currency",
            "decimalPlaces": 2,
            "crossFilter": True,
            "drillDown": widget_type != "text",
            **options,
        },
    }


def build_cost_monitor_templates(
    connection: sqlite3.Connection,
    table_key: str | None = None,
    limit: int = 24,
    *,
    active_workspace_id: Callable[[sqlite3.Connection], str],
    rows_to_dicts: Callable[[Any], list[dict[str, Any]]],
    preferred_table_key: Callable[[sqlite3.Connection, str | None], str],
    table_template_fields: Callable[[sqlite3.Connection, str], dict[str, Any]],
) -> dict[str, Any]:
    workspace_id = active_workspace_id(connection)
    table_rows = rows_to_dicts(
        connection.execute(
            "SELECT * FROM table_registry WHERE workspace_id = ? ORDER BY row_count DESC, table_key",
            (workspace_id,),
        )
    )
    fields_by_key = _table_fields_by_key(connection, table_rows, table_template_fields)
    preferred = preferred_table_key(connection, table_key) if table_key else ""
    funds_table = _find_table_by_fields(table_rows, fields_by_key, COST_MONITOR_FUNDS_FIELDS, preferred)
    policy_table = _find_table_by_fields(table_rows, fields_by_key, COST_MONITOR_POLICY_FIELDS)
    missing_requirements: list[dict[str, Any]] = []
    if not funds_table:
        missing_requirements.append({
            "table": "资金",
            "requiredFields": sorted(COST_MONITOR_FUNDS_FIELDS),
            "reason": "费用监控看板需要资金流水字段才能生成平台服务费、佣金、动账净额和场景拆分。",
        })
    if not policy_table:
        missing_requirements.append({
            "table": "保单明细",
            "requiredFields": sorted(COST_MONITOR_POLICY_FIELDS),
            "reason": "支付保费指标需要保单明细表。",
        })
    if not funds_table:
        return {
            "templates": [],
            "categories": [],
            "tableCount": len(table_rows),
            "templateKey": COST_MONITOR_TEMPLATE_KEY,
            "missingRequirements": missing_requirements,
        }

    templates: list[dict[str, Any]] = []

    def add_metric(item_id: str, title: str, measure: str, *, category: str = "费用指标", field: str = "", value: str = "", formula: str = "", table: dict[str, Any] | None = None) -> None:
        filters = [{"field": field, "operator": "contains", "value": value, "enabled": True}] if field and value else []
        templates.append(_cost_monitor_widget(
            item_id=item_id,
            category=category,
            table=table or funds_table,
            widget_type="metric",
            title=title,
            reason="基于当前工作区字段证据生成的费用监控口径。",
            options={
                "dimension": "动账时间" if (table or funds_table) == funds_table else "下单时间",
                "measure": measure,
                "aggregation": "sum",
                "filters": filters,
                "metricFormulaText": formula,
                "metricFormulaName": title if formula else "",
            },
        ))

    templates.append(_cost_monitor_widget(
        item_id="note",
        category="说明",
        table=funds_table,
        widget_type="text",
        title="监控说明",
        reason="把口径和缺口直接放在看板首屏，降低入门用户理解成本。",
        options={
            "subtitle": "费用监控看板",
            "textContent": "本看板基于当前工作区字段证据生成费用监控口径。资金表使用动账净额：入账为正，出账为负。支付保费来自保单明细。导入对应源文件后，每个指标都可打开证据查看来源表、字段和筛选条件。",
            "dataMode": "table",
            "measure": "",
            "aggregation": "count",
            "valueFormat": "auto",
            "crossFilter": False,
            "drillDown": False,
        },
    ))
    if policy_table:
        add_metric("policy_fee", "支付保费", "支付保费", category="费用指标", table=policy_table)
    add_metric("platform_fee", "平台服务费", "平台服务费")
    add_metric("commission", "佣金", "佣金")
    add_metric("external_promotion", "站外推广费", "站外推广费")
    add_metric("recruit_service", "招商服务费", "招商服务费")
    add_metric("small_transfer", "小额打款", "动账净额", field="动账场景", value="小额打款", formula=COST_MONITOR_NET_FORMULA)
    add_metric("consumer_comp", "消费者赔付", "动账净额", field="动账场景", value="消费者赔付", formula=COST_MONITOR_NET_FORMULA)
    add_metric("pickup_freight", "上门取件运费", "动账净额", field="动账场景", value="上门取件运费", formula=COST_MONITOR_NET_FORMULA)
    add_metric("month_pay_joint", "抖音月付与商家联合贴息活动", "动账净额", field="动账场景", value="抖音月付与商家联合贴息活动", formula=COST_MONITOR_NET_FORMULA)
    add_metric("month_pay", "抖音月付联合贴息", "动账净额", field="动账场景", value="抖音月付联合贴息", formula=COST_MONITOR_NET_FORMULA)
    add_metric("platform_cashback_recover", "平台返现/返券活动追缴用户退回平台", "动账净额", field="动账场景", value="平台返现/返券活动追缴用户退回平台", formula=COST_MONITOR_NET_FORMULA)
    add_metric("review_gift_deposit", "评价有礼保证金扣款", "动账净额", field="动账场景", value="评价有礼保证金扣款", formula=COST_MONITOR_NET_FORMULA)
    add_metric("qianchuan_topup", "划扣电商货款充值巨量千川", "动账净额", field="备注", value="划扣电商货款充值巨量千川", formula=COST_MONITOR_NET_FORMULA)
    add_metric("income", "收入", "收入", formula=COST_MONITOR_INCOME_FORMULA)
    add_metric("income_agent", "收入", "收入", formula=COST_MONITOR_INCOME_FORMULA)
    add_metric("income_xiaoyue", "收入 - 小月", "动账金额", field="达人ID", value="15826892886764")
    add_metric("order_refund", "订单退款", "订单退款")
    add_metric("refund", "退款", "订单退款", field="动账场景", value="平台返现/返券活动追缴用户退回平台")
    add_metric("withdraw", "提现", "动账金额", field="动账场景", value="提现")
    add_metric("checkin_cash", "签到领现金", "动账净额", field="备注", value="签到领", formula=COST_MONITOR_NET_FORMULA)

    templates.append(_cost_monitor_widget(
        item_id="net_trend",
        category="趋势",
        table=funds_table,
        widget_type="line",
        title="动账净额月度趋势",
        reason="按月查看入账为正、出账为负后的净额波动。",
        options={
            "dimension": "动账时间",
            "timeGrain": "month",
            "measure": "动账净额",
            "aggregation": "sum",
            "metricFormulaText": COST_MONITOR_NET_FORMULA,
            "metricFormulaName": "动账净额",
            "sortDirection": "desc",
            "topN": 12,
            "areaFill": True,
            "colorPalette": "fresh",
        },
    ))
    templates.append(_cost_monitor_widget(
        item_id="scene_bar",
        category="拆分",
        table=funds_table,
        widget_type="bar",
        title="动账场景净额拆分",
        reason="按动账场景汇总动账净额，优先定位最大费用来源。",
        options={
            "dimension": "动账场景",
            "measure": "动账净额",
            "aggregation": "sum",
            "metricFormulaText": COST_MONITOR_NET_FORMULA,
            "metricFormulaName": "动账净额",
            "sortDirection": "asc",
            "topN": 12,
            "barOrientation": "horizontal",
            "colorPalette": "contrast",
        },
    ))

    selected = templates[: max(1, min(limit, 24))]
    categories: dict[str, int] = {}
    for template in selected:
        categories[template["category"]] = categories.get(template["category"], 0) + 1
    return {
        "templates": selected,
        "categories": [{"category": key, "count": value} for key, value in categories.items()],
        "tableCount": len(table_rows),
        "templateKey": COST_MONITOR_TEMPLATE_KEY,
        "defaultTableKey": funds_table["table_key"],
        "matchedTables": {
            "funds": funds_table,
            "policy": policy_table,
        },
        "missingRequirements": missing_requirements,
    }


def build_business_analysis_templates(
    connection: sqlite3.Connection,
    table_key: str | None = None,
    limit: int = 12,
    *,
    active_workspace_id: Callable[[sqlite3.Connection], str],
    rows_to_dicts: Callable[[Any], list[dict[str, Any]]],
    preferred_table_key: Callable[[sqlite3.Connection, str | None], str],
    slug: Callable[[str], str],
    table_template_fields: Callable[[sqlite3.Connection, str], dict[str, Any]],
    template_key: str = BUSINESS_TEMPLATE_KEY,
) -> dict[str, Any]:
    if template_key == COST_MONITOR_TEMPLATE_KEY:
        return build_cost_monitor_templates(
            connection,
            table_key,
            limit,
            active_workspace_id=active_workspace_id,
            rows_to_dicts=rows_to_dicts,
            preferred_table_key=preferred_table_key,
            table_template_fields=table_template_fields,
        )
    workspace_id = active_workspace_id(connection)
    table_rows = rows_to_dicts(
        connection.execute(
            "SELECT * FROM table_registry WHERE workspace_id = ? ORDER BY row_count DESC, table_key",
            (workspace_id,),
        )
    )
    fields_by_key = _table_fields_by_key(connection, table_rows, table_template_fields)
    if template_key == ERP_UNIT_LIBRARY_TEMPLATE_KEY:
        if not table_rows:
            table_rows, fields_by_key = source_profile_table_inputs(connection, workspace_id)
        preferred = ""
        if table_key:
            try:
                preferred = preferred_table_key(connection, table_key)
            except ValueError:
                if any(row.get("table_key") == table_key for row in table_rows):
                    preferred = table_key
                else:
                    raise
        return build_erp_dashboard_unit_templates(
            table_rows,
            fields_by_key,
            preferred_table_key_value=preferred,
            limit=limit,
            slug=slug,
        )
    if table_key:
        table_rows = [row for row in table_rows if row["table_key"] == preferred_table_key(connection, table_key)]
    templates: list[dict[str, Any]] = []

    def add_template(category: str, table: dict[str, Any], widget_type: str, title: str, reason: str, options: dict[str, Any]) -> None:
        templates.append({
            "id": f"biz_{slug(table['table_key'])}_{widget_type}_{slug(title)}",
            "category": category,
            "type": widget_type,
            "title": title,
            "reason": reason,
            "tableKey": table["table_key"],
            "tableName": table["display_name"],
            "preset": {
                "type": widget_type,
                "title": title,
                "tableKey": table["table_key"],
                "subtitle": f"{category} · {table['display_name']}",
                **options,
            },
        })

    for table in table_rows:
        fields = table_template_fields(connection, table["table_key"])
        measure = fields["measure"]
        dimension = fields["dimension"]
        date_field = fields["date"]
        columns = fields["columns"]
        if measure:
            add_template("经营总览", table, "metric", f"{measure} 核心读数", "把主要金额或数量指标放到第一屏，先确认业务规模。", {
                "measure": measure,
                "aggregation": "sum",
                "valueFormat": "compact",
                "topN": 1,
            })
        if date_field and measure:
            add_template("经营趋势", table, "line", f"{measure} 趋势", "按时间维度观察波动，先发现异常月份或日期。", {
                "dimension": date_field,
                "timeGrain": "month",
                "measure": measure,
                "aggregation": "sum",
                "sortDirection": "asc",
                "topN": 24,
                "valueFormat": "compact",
                "colorPalette": "fresh",
                "areaFill": True,
            })
        if dimension and measure:
            add_template("结构拆解", table, "bar", f"{dimension} {measure} 排行", "用分类排行定位贡献最高或问题最集中的对象。", {
                "dimension": dimension,
                "measure": measure,
                "aggregation": "sum",
                "topN": 12,
                "valueFormat": "compact",
                "barOrientation": "horizontal",
                "colorPalette": "contrast",
                "showDataLabel": True,
            })
            add_template("结构拆解", table, "pie", f"{dimension} 构成", "用占比快速判断是否过度集中。", {
                "dimension": dimension,
                "measure": measure,
                "aggregation": "sum",
                "topN": 8,
                "valueFormat": "compact",
                "pieShape": "donut",
                "colorPalette": "fresh",
                "showDataLabel": True,
            })
            add_template("交互筛选", table, "slicer", f"{dimension} 切片器", "点击分类后联动同页组件，减少手工筛选步骤。", {
                "dimension": dimension,
                "aggregation": "count",
                "topN": 10,
                "valueFormat": "plain",
                "slicerDisplay": "list",
                "slicerMultiSelect": True,
                "globalFilterTarget": True,
                "drillDown": False,
            })
        if columns:
            add_template("明细核查", table, "table", f"{table['display_name']} 明细核查", "保留可下钻明细，避免看板结论脱离原始记录。", {
                "columns": columns[:8],
                "aggregation": "count",
                "topN": 100,
                "tableColumnLimit": min(8, max(2, len(columns[:8]))),
            })

    templates.insert(0, {
        "id": "biz_text_decision_notes",
        "category": "经营总览",
        "type": "text",
        "title": "经营复盘结论",
        "reason": "把结论、异常和下一步动作留在看板里，方便入门用户按结果行动。",
        "tableKey": table_rows[0]["table_key"] if table_rows else "",
        "tableName": table_rows[0]["display_name"] if table_rows else "",
        "preset": {
            "type": "text",
            "title": "经营复盘结论",
            "subtitle": "说明口径、异常和下一步动作",
            "textContent": "先看核心读数和趋势，再拆分类排行、构成占比和明细记录。发现异常后，用切片器联动或明细下钻回到原始证据。",
            "dataMode": "table",
            "crossFilter": False,
            "drillDown": False,
        },
    })
    selected = templates[: max(1, min(limit, 24))]
    categories: dict[str, int] = {}
    for template in selected:
        categories[template["category"]] = categories.get(template["category"], 0) + 1
    return {
        "templates": selected,
        "categories": [{"category": key, "count": value} for key, value in categories.items()],
        "tableCount": len(table_rows),
        "templateKey": BUSINESS_TEMPLATE_KEY,
    }


def build_business_dashboard_payload(
    connection: sqlite3.Connection,
    table_key: str | None = None,
    limit: int = 10,
    *,
    build_business_analysis_templates: Callable[..., dict[str, Any]],
    preferred_table_key: Callable[[sqlite3.Connection, str | None], str],
    template_key: str = BUSINESS_TEMPLATE_KEY,
) -> dict[str, Any]:
    draft = build_business_analysis_templates(connection, table_key, limit, template_key=template_key)
    widgets: list[dict[str, Any]] = []
    layout: list[dict[str, Any]] = []
    default_table_key = str(draft.get("defaultTableKey") or next((template["tableKey"] for template in draft["templates"] if template.get("tableKey")), ""))
    if not default_table_key:
        try:
            default_table_key = preferred_table_key(connection, table_key)
        except ValueError:
            default_table_key = str(table_key or "")
    for index, template in enumerate(draft["templates"]):
        preset = dict(template["preset"])
        widget_type = str(preset.get("type") or template["type"])
        widget_key = f"{template['id']}_{index + 1}"
        item_layout = {"i": widget_key, **template_widget_layout(widget_type, index)}
        layout.append(item_layout)
        widgets.append({
            "id": widget_key,
            "type": widget_type,
            "title": preset.get("title") or template["title"],
            "tableKey": preset.get("tableKey") or default_table_key,
            **preset,
            "layout": item_layout,
        })
    return {
        **draft,
        "widgets": widgets,
        "layout": layout,
        "defaultTableKey": default_table_key,
        "templateKey": template_key,
    }


def write_business_dashboard(
    connection: sqlite3.Connection,
    dashboard_key: str,
    dashboard_name: str,
    default_table_key: str,
    widgets: list[dict[str, Any]],
    layout_items: list[dict[str, Any]],
    *,
    active_workspace_id: Callable[[sqlite3.Connection], str],
    preferred_table_key: Callable[[sqlite3.Connection, str | None], str],
    table_display_name: Callable[[sqlite3.Connection, str], str],
    unique_key: Callable[[str], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    id_map: dict[str, str] = {}
    proposed_payload_widgets: list[dict[str, Any]] = []
    for index, item in enumerate(widgets):
        if not isinstance(item, dict):
            continue
        original_id = str(item.get("widget_key") or item.get("widgetKey") or item.get("id") or f"widget_{index + 1}")
        next_id = namespaced_dashboard_widget_id(dashboard_key, original_id, index)
        id_map[original_id] = next_id
        next_item = dict(item)
        next_item["id"] = next_id
        next_item["widgetKey"] = next_id
        if isinstance(next_item.get("config"), dict):
            next_config = dict(next_item["config"])
            next_config["widgetKey"] = next_id
            next_item["config"] = next_config
        proposed_payload_widgets.append(next_item)
    next_layout_items: list[dict[str, Any]] = []
    for item in layout_items:
        if not isinstance(item, dict):
            continue
        original_id = str(item.get("i") or "")
        next_item = dict(item)
        if original_id in id_map:
            next_item["i"] = id_map[original_id]
        next_layout_items.append(next_item)
    layout_by_id = {str(item.get("i") or ""): item for item in next_layout_items if isinstance(item, dict)}
    workspace_id = active_workspace_id(connection)
    proposed_widgets = [
        dashboard_module_widget_from_payload(
            connection,
            dashboard_key,
            widget,
            index,
            default_table_key,
            layout_by_id,
            workspace_id=workspace_id,
            preferred_table_key=preferred_table_key,
            table_display_name=table_display_name,
            unique_key=unique_key,
        )
        for index, widget in enumerate(proposed_payload_widgets)
        if isinstance(widget, dict)
    ]
    now = now_iso()
    layout = {
        "version": 1,
        "grid": "12-col",
        "widgets": [widget["widget_key"] for widget in proposed_widgets],
        "widgetLayout": next_layout_items,
        "canvasWidthMode": "stretch",
        "globalFilters": [],
    }
    save_dashboard_with_widgets(
        connection,
        workspace_id=workspace_id,
        dashboard_key=dashboard_key,
        dashboard_name=dashboard_name,
        default_table_key=default_table_key,
        layout=layout,
        widgets=proposed_widgets,
        now=now,
    )
    return {
        "dashboardKey": dashboard_key,
        "dashboardName": dashboard_name,
        "defaultTableKey": default_table_key,
        "savedDashboardModules": len(proposed_widgets),
    }


def run_business_dashboard_command(
    *,
    op: str,
    dashboard_key: str | None,
    table_key: str | None,
    template_key: str,
    limit: int,
    name: str | None,
    confirm: bool,
    open_db: Callable[[], Any],
    build_business_dashboard_payload: Callable[..., dict[str, Any]],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    unique_key: Callable[[str], str],
    write_business_dashboard: Callable[[sqlite3.Connection, str, str, str, list[dict[str, Any]], list[dict[str, Any]]], dict[str, Any]],
    ensure_navigation_modules: Callable[[sqlite3.Connection], None],
) -> dict[str, Any]:
    with open_db() as connection:
        payload = build_business_dashboard_payload(connection, table_key, limit, template_key=template_key)
        if op == "draft":
            return {"ok": True, "draft": payload, "templateCount": len(payload["templates"])}
        if not payload["widgets"]:
            raise ValueError("No business dashboard templates are available for current sources.")
        mode = op
        workspace_id = active_workspace_id(connection)
        resolved_dashboard_key = dashboard_key or ("default" if workspace_id == "default" else unique_key("dashboard"))
        if mode == "create":
            resolved_dashboard_key = unique_key("dashboard_biz")
        dashboard_name = name or ("经营分析看板" if mode == "create" else "经营分析看板")
        if mode == "overwrite":
            row = connection.execute(
                "SELECT name FROM dashboards WHERE dashboard_key = ? AND workspace_id = ?",
                (resolved_dashboard_key, workspace_id),
            ).fetchone()
            if not row:
                raise ValueError(f"Unknown dashboard: {resolved_dashboard_key}")
            dashboard_name = name or row["name"]
        proposed = {
            "op": mode,
            "dashboardKey": resolved_dashboard_key,
            "dashboardName": dashboard_name,
            "defaultTableKey": payload["defaultTableKey"],
            "templateCount": len(payload["templates"]),
            "templateKey": template_key,
            "widgetCount": len(payload["widgets"]),
            "categories": payload["categories"],
            "missingRequirements": payload.get("missingRequirements", []),
        }
        if not confirm:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "proposed": proposed,
                "draft": payload,
            }
        saved = write_business_dashboard(
            connection,
            resolved_dashboard_key,
            dashboard_name,
            payload["defaultTableKey"],
            payload["widgets"],
            payload["layout"],
        )
        connection.commit()
        ensure_navigation_modules(connection)
    return {
        "ok": True,
        "confirmed": True,
        "op": mode,
        "createdDashboardKey": resolved_dashboard_key if mode == "create" else None,
        "savedDashboardKey": resolved_dashboard_key,
        "templateCount": len(payload["templates"]),
        "templateKey": template_key,
        **saved,
    }


def build_agent_dashboard_create_draft(
    connection: sqlite3.Connection,
    table_key: str | None,
    prompt: str,
    limit: int = 8,
    template_key: str = BUSINESS_TEMPLATE_KEY,
    *,
    build_business_dashboard_payload: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    if template_key == BUSINESS_TEMPLATE_KEY and prompt_prefers_erp_unit_library(prompt):
        template_key = ERP_UNIT_LIBRARY_TEMPLATE_KEY
    payload = build_business_dashboard_payload(connection, table_key, limit, template_key=template_key)
    erp_unit_library = payload.get("erpUnitLibrary") if isinstance(payload.get("erpUnitLibrary"), dict) else None
    preview_widgets: list[dict[str, Any]] = []
    for widget in payload.get("widgets", [])[:limit]:
        if not isinstance(widget, dict):
            continue
        preview_widgets.append(
            {
                "id": widget.get("id") or widget.get("widgetKey") or widget.get("widget_key"),
                "type": widget.get("type") or widget.get("widget_type"),
                "title": widget.get("title"),
                "tableKey": widget.get("tableKey") or payload.get("defaultTableKey"),
                "dimension": widget.get("dimension") or widget.get("group") or widget.get("timeField"),
                "measure": widget.get("measure") or widget.get("metricName") or widget.get("metricKey"),
                "aggregation": widget.get("aggregation") or widget.get("agg"),
            }
        )
    widget_count = len(payload.get("widgets", []))
    default_table_key = payload.get("defaultTableKey") or table_key or "current source"
    if erp_unit_library:
        selected_units = int(erp_unit_library.get("selectedUnitCount") or widget_count)
        reference_count = int(erp_unit_library.get("referenceCount") or 0)
        confirmation_summary = {
            "zh": f"确认后将按当前字段证据，从 {reference_count} 个公开 ERP 案例沉淀的单元库中创建 {selected_units} 个可编辑看板组件。",
            "en": f"After confirmation, Agent will create {selected_units} editable widgets from the ERP unit library scored against current fields and {reference_count} public references.",
        }
    else:
        confirmation_summary = {
            "zh": f"确认后将基于 {default_table_key} 创建可编辑经营看板，包含 {widget_count} 个组件。",
            "en": f"After confirmation, Agent will create an editable business dashboard from {default_table_key} with {widget_count} widgets.",
        }
    evidence = ["source-profile", "metric-definition", "query-runtime", "dashboard-widget-catalog"]
    if erp_unit_library:
        evidence.append("erp-unit-library")
    return {
        "source": "business-dashboard",
        "dashboardName": "Agent 经营复盘",
        "defaultTableKey": default_table_key,
        "templateCount": len(payload.get("templates", [])),
        "templateKey": payload.get("templateKey", template_key),
        "widgetCount": widget_count,
        "categories": payload.get("categories", []),
        "missingRequirements": payload.get("missingRequirements", []),
        "erpUnitLibrary": erp_unit_library,
        "widgets": payload.get("widgets", []),
        "layout": payload.get("layout", []),
        "previewWidgets": preview_widgets,
        "prompt": prompt,
        "evidence": evidence,
        "confirmationSummary": confirmation_summary,
    }
