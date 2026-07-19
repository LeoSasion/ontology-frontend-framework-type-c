"""Query and delivery application use cases."""

from contextlib import closing

from bi_cli_core import now_iso, quote_relationship_identifier
from bi_cli_dashboard_commands import (
    add_or_set_filter_command,
    clear_filters_command,
    create_index_command,
    dashboards_command,
    list_filters_command,
    recommend_indexes_command,
    remove_filter_command,
    remove_stale_filters_command,
)
from bi_cli_misc_commands import update_field_command
from bi_cli_query_view_commands import (
    copy_view_command,
    delete_view_command,
    list_views_command,
    query_command,
    query_table_command,
    save_view_command,
)
from bi_cli_relationship_formula_commands import (
    action_drafts_command,
    dashboard_operation_command,
    delete_formula_command,
    formula_preview_command,
    list_formulas_command,
    list_relationships_command,
    query_relationship_command,
    recommend_relationships_command,
    relationship_preview_command,
    relationship_save_command,
    remove_relationship_command,
    save_formula_command,
)
from bi_cli_schema import active_workspace_id, open_db, table_columns
from query_plan_receipt_service import create_query_plan_receipt
from relationship_command_service import relationship_rows_for_chart as relationship_rows_for_chart_service
from relationship_tools import build_relationship_query
from semantic_query_execution import execute_workspace_semantic_query

from .agent_interaction import ask_command, confirm_action_command
