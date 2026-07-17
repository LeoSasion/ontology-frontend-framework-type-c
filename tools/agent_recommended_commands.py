from __future__ import annotations

from pathlib import Path
from typing import Any

from agent_prompt_resolution import AgentPromptIntents


def action_value(action: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = action.get(key)
        if value:
            return str(value)
    return ""


def build_agent_recommended_commands(
    *,
    answer_card: dict[str, Any],
    selected_table: dict[str, Any] | None,
    selected_dashboard: dict[str, Any] | None,
    intents: AgentPromptIntents,
    read_only: bool,
    import_file: Path | None,
    relationship_action: dict[str, Any] | None,
    dashboard_filter_action: dict[str, Any] | None,
    widget_action: dict[str, Any] | None,
    dashboard_action: dict[str, Any] | None,
    index_field: str | None,
    formula_action: dict[str, Any] | None,
    view_action: dict[str, Any] | None,
    metric_action: dict[str, Any] | None,
    semantic_action: dict[str, Any] | None,
) -> list[str]:
    recommended: list[str] = [
        "python tools/aibi_cli.py --json status",
    ]
    if answer_card.get("query"):
        answer_query = answer_card["query"]
        group_arg = f" --group {answer_query['group']}" if answer_query.get("group") else ""
        recommended.append(
            "python tools/aibi_cli.py --json query "
            f"--table {answer_query['table']}{group_arg} --measure {answer_query['measure']} --agg {answer_query['aggregation']}"
        )
    elif selected_table:
        recommended.append(f"python tools/aibi_cli.py --json inspect-table --table {selected_table['table_key']}")
    if (not read_only) and intents.wants_import:
        if import_file:
            recommended.append(f"python tools/aibi_cli.py --json preview-import {import_file}")
    if (not read_only) and relationship_action:
        left_table = action_value(relationship_action, "leftTable", "leftTableKey")
        right_table = action_value(relationship_action, "rightTable", "rightTableKey")
        left_field = action_value(relationship_action, "leftField", "left_field")
        right_field = action_value(relationship_action, "rightField", "right_field")
        if all([left_table, right_table, left_field, right_field]):
            recommended.append(
                "python tools/aibi_cli.py --json relationship-preview "
                f"--left-table {left_table} --right-table {right_table} "
                f"--left-field {left_field} --right-field {right_field}"
            )
    if intents.wants_dashboard and selected_dashboard:
        recommended.append(f"python tools/aibi_cli.py --json dashboards --dashboard {selected_dashboard['dashboard_key']}")
    if (not read_only) and intents.wants_dashboard_filter and dashboard_filter_action:
        recommended.append(
            "python tools/aibi_cli.py --json add-filter "
            f"--dashboard {dashboard_filter_action['dashboardKey']} --field {dashboard_filter_action['field']} "
            f"--operator {dashboard_filter_action['operator']} --value \"{dashboard_filter_action['value']}\""
        )
    if (not read_only) and intents.wants_widget and widget_action:
        widget_options = widget_action.get("options", {})
        dimension_arg = f" --dimension {widget_options.get('dimension')}" if widget_options.get("dimension") else ""
        measure_arg = f" --measure {widget_options.get('measure')}" if widget_options.get("measure") else ""
        recommended.append(
            "python tools/aibi_cli.py --json add-widget "
            f"--dashboard {widget_action['dashboardKey']} --type {widget_action['widgetType']} --table {widget_action['tableKey']} "
            f"--title \"{widget_action['title']}\"{dimension_arg}{measure_arg} --agg {widget_options.get('aggregation', 'count')}"
        )
    if (not read_only) and dashboard_action:
        dashboard_op_command = f"python tools/aibi_cli.py --json dashboard-op --op {dashboard_action['op']} --dashboard {dashboard_action['dashboardKey']}"
        if dashboard_action.get("name"):
            dashboard_op_command += f" --name \"{dashboard_action['name']}\""
        recommended.append(dashboard_op_command)
    if (not read_only) and intents.wants_index and selected_table and index_field:
        recommended.append(f"python tools/aibi_cli.py --json create-index --table {selected_table['table_key']} --field {index_field}")
    if (not read_only) and intents.wants_formula and formula_action:
        recommended.append(
            "python tools/aibi_cli.py --json save-formula "
            f"--name \"{formula_action['name']}\" --table {formula_action['tableKey']} "
            f"--expression \"{formula_action['formulaText']}\" --mode {formula_action['mode']}"
        )
    if (not read_only) and intents.wants_view and view_action:
        filters_arg = " ".join(
            f"--filter {item['field']}:{item.get('operator', 'contains')}:{item.get('value', '')}"
            for item in view_action.get("config", {}).get("filters", [])
            if item.get("field")
        )
        columns_arg = ",".join(view_action.get("config", {}).get("columns", []))
        recommended.append(
            "python tools/aibi_cli.py --json save-view "
            f"--table {view_action['table_key']} --name \"{view_action['name']}\" --columns \"{columns_arg}\" {filters_arg}".strip()
        )
    if (not read_only) and intents.wants_metric and metric_action:
        dimension_arg = f" --dimension {metric_action['dimension']}" if metric_action.get("dimension") else ""
        recommended.append(
            "python tools/aibi_cli.py --json add-metric "
            f"--name \"{metric_action['label']}\" --table {metric_action['tableKey']} "
            f"--field {metric_action['measure']} --agg {metric_action['aggregation']}{dimension_arg}"
        )
    if (not read_only) and intents.wants_semantic and semantic_action:
        recommended.append(
            "python tools/aibi_cli.py --json set-semantic "
            f"{semantic_action['tableKey']} {semantic_action['field']} --role {semantic_action['role']}"
        )
    return recommended
