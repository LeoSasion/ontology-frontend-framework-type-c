from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Callable

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
COST_MONITOR_NET_FORMULA = "SUM(IF([动账方向]=\"出账\",-ABS([动账金额]),IF([动账方向]=\"入账\",ABS([动账金额]),[动账金额])))"


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


def table_fields_by_key(
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
    fields_by_key = table_fields_by_key(connection, table_rows, table_template_fields)
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
