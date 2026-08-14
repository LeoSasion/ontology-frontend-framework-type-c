"""Control-plane application use cases."""

from agent_runtime_profile_service import (
    agent_provider_evaluation_record_command,
    agent_provider_evaluations_command,
    agent_runtime_profile_set_command,
    agent_runtime_profiles_command,
)
from agent_session_service import (
    agent_context_compact_command,
    agent_session_create_command,
    agent_session_fork_command,
    agent_session_resume_command,
    agent_sessions_command,
)
from agent_turn_service import agent_turns_command, cancel_agent_turn_command, run_agent_turn_command
from analysis_unit_service import attach_analysis_unit
from bi_cli_core import DB_PATH, DUCKDB_PATH, ROOT, now_iso
from bi_cli_schema import active_workspace_id, open_db
from bi_cli_system_commands import cli_contract_command, list_commands_command, quality_doctor_command, status_command
from capability_contract_service import capability_registry
from context_pack_service import context_pack_command, context_rule_command, context_term_command
from plan_quality_service import business_expression_cases_command, plan_quality_evaluate_command, plan_quality_scorecards_command
from restricted_workflow_graph_service import (
    agent_workflow_graph_command,
    restricted_workflow_operators_command,
    restricted_workflow_validate_command,
)
from semantic_patch_service import (
    knowledge_source_adapters_command,
    knowledge_sources_command,
    semantic_patch_proposals_command,
    semantic_patch_propose_command,
    semantic_patch_review_command,
)
from semantic_release_service import (
    semantic_release_preview_command,
    semantic_release_publish_command,
    semantic_release_rollback_command,
    semantic_releases_command,
)
from workflow_command_service import capability_contracts_command, context_budget_command, workflow_plan_command
from workflow_recipe_service import workflow_recipe_plan_command, workflow_recipe_preview_command, workflow_recipe_publish_command, workflow_recipes_command
from workspace_manifest_service import business_field_profiles_command, runtime_catalog_command, workspace_manifest_command
from workspace_recovery_service import (
    configured_recovery_root,
    workspace_recovery_compare_command,
    workspace_recovery_create_command,
    workspace_recovery_delete_command,
    workspace_recovery_inspect_command,
    workspace_recovery_list_command,
    workspace_recovery_reconcile_command,
    workspace_recovery_restore_command,
)

from .agent_interaction import ask_command


WORKSPACE_RECOVERY_ROOT = configured_recovery_root(ROOT)
