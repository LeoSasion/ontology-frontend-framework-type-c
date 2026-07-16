from __future__ import annotations

import argparse

from connector_command_service import VALID_CONNECTOR_STATUSES, VALID_CONNECTOR_TYPES
from dashboard_widget_contracts import (
    B_BAR_ORIENTATIONS,
    B_COLOR_PALETTES,
    B_DASHBOARD_FILTER_OPERATORS,
    B_PIE_SHAPES,
    B_RANKING_MODES,
    B_RELATIONSHIP_WIDGET_TYPES,
    B_SLICER_DISPLAYS,
    B_SORT_BY,
    B_VALUE_FORMATS,
    B_WIDGET_TYPES,
)
from erp_dashboard_unit_library import ERP_UNIT_LIBRARY_TEMPLATE_KEY
from query_runtime import SAFE_AGGREGATIONS

def add_widget_style_arguments(command_parser: argparse.ArgumentParser) -> None:
    command_parser.add_argument("--sort-by", choices=B_SORT_BY)
    command_parser.add_argument("--sort-direction", choices=["asc", "desc"])
    command_parser.add_argument("--decimal-places", type=int)
    command_parser.add_argument("--table-column-limit", type=int)
    command_parser.add_argument("--slicer-display", choices=B_SLICER_DISPLAYS)
    command_parser.add_argument("--ranking-mode", choices=B_RANKING_MODES)
    command_parser.add_argument("--color-palette", choices=B_COLOR_PALETTES)
    command_parser.add_argument("--bar-orientation", choices=B_BAR_ORIENTATIONS)
    command_parser.add_argument("--pie-shape", choices=B_PIE_SHAPES)
    command_parser.add_argument("--x-axis-title")
    command_parser.add_argument("--y-axis-title")
    command_parser.add_argument("--legend-title")
    for enabled_flag, disabled_flag, dest in [
        ("--slicer-multi-select", "--single-select", "slicer_multi_select"),
        ("--slicer-searchable", "--no-slicer-search", "slicer_searchable"),
        ("--show-legend", "--hide-legend", "show_legend"),
        ("--show-axis", "--hide-axis", "show_axis"),
        ("--show-data-label", "--hide-data-label", "show_data_label"),
        ("--line-smooth", "--line-straight", "line_smooth"),
        ("--area-fill", "--no-area-fill", "area_fill"),
        ("--cross-filter", "--no-cross-filter", "cross_filter"),
        ("--drill-down", "--no-drill-down", "drill_down"),
        ("--global-filter-target", "--no-global-filter-target", "global_filter_target"),
    ]:
        group = command_parser.add_mutually_exclusive_group()
        group.add_argument(enabled_flag, dest=dest, action="store_true", default=None)
        group.add_argument(disabled_flag, dest=dest, action="store_false")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AIBI-C local BI CLI")
    parser.add_argument("--json", action="store_true", help="Output JSON. Kept for compatibility; JSON is always used.")
    sub = parser.add_subparsers(dest="command", required=True)

    cli_contract = sub.add_parser("cli-contract")
    cli_contract.add_argument("--format", choices=["json", "markdown"], default="json")
    cli_contract.add_argument("--output", default="")
    cli_contract.add_argument("--command", dest="command_name", default="")

    list_commands = sub.add_parser("list-commands")
    list_commands.add_argument("--domain")
    list_commands.add_argument("--mutation-mode")
    list_commands.add_argument("--writes", choices=["yes", "no", "any"], default="any")

    capability_contracts = sub.add_parser("capability-contracts", description="List deterministic capability, permission, confirmation, job, and evidence contracts.")
    capability_contracts.add_argument("--command", dest="command_name", default="")
    capability_contracts.add_argument("--domain", default="")

    workflow_plan = sub.add_parser("workflow-plan", description="Build one deterministic workflow stage for a registered capability.")
    workflow_plan.add_argument("target_command")
    workflow_plan.add_argument("--entrypoint", choices=["cli", "api", "agent", "job"], default="cli")
    workflow_plan.add_argument("--workspace", required=True)
    workflow_plan.add_argument("--input-json", default="{}")
    workflow_plan.add_argument("--confirmed", action="store_true")

    context_budget = sub.add_parser("context-budget", description="Compact context while preserving critical evidence references.")
    context_budget.add_argument("--segments-json", required=True)
    context_budget.add_argument("--max-chars", type=int, default=12_000)

    sub.add_parser("restricted-workflow-operators", description="List the fixed Operator and read-only expert role registry.")

    restricted_workflow_validate = sub.add_parser("restricted-workflow-validate", description="Validate one declaration-only restricted workflow graph without executing it.")
    restricted_workflow_validate.add_argument("--graph-json", required=True)
    restricted_workflow_validate.add_argument("--workspace", default="")

    agent_workflow_graph = sub.add_parser("agent-workflow-graph", description="Inspect the persisted restricted workflow graph for one Agent Turn.")
    agent_workflow_graph.add_argument("--turn", required=True)
    agent_workflow_graph.add_argument("--workspace", default="")

    agent_turn_run = sub.add_parser("agent-turn-run", description="Run one evidence-planned Agent turn and persist its public event stream.")
    agent_turn_run.add_argument("prompt")
    agent_turn_run.add_argument("--workspace", default="")
    agent_turn_run.add_argument("--parent-turn", default="")
    agent_turn_run.add_argument("--parent-run", default="")
    agent_turn_run.add_argument("--branch-label", default="")
    agent_turn_run.add_argument("--session", default="")
    agent_turn_run.add_argument("--review-stale-context", action="store_true")
    agent_turn_run.add_argument("--read-only", action="store_true")

    agent_turns = sub.add_parser("agent-turns", description="List or inspect workspace Agent turns and events.")
    agent_turns.add_argument("--workspace", default="")
    agent_turns.add_argument("--turn", default="")
    agent_turns.add_argument("--after-sequence", type=int, default=0)
    agent_turns.add_argument("--limit", type=int, default=30)

    agent_turn_cancel = sub.add_parser("agent-turn-cancel", description="Cancel a non-terminal Agent turn.")
    agent_turn_cancel.add_argument("turn")
    agent_turn_cancel.add_argument("--workspace", default="")

    agent_session_create = sub.add_parser("agent-session-create", description="Create one workspace-bound durable Agent Session.")
    agent_session_create.add_argument("--title", default="新分析会话")
    agent_session_create.add_argument("--workspace", default="")

    agent_sessions = sub.add_parser("agent-sessions", description="List or inspect durable Agent Sessions and their safe context snapshots.")
    agent_sessions.add_argument("--session", default="")
    agent_sessions.add_argument("--workspace", default="")
    agent_sessions.add_argument("--limit", type=int, default=30)

    agent_session_resume = sub.add_parser("agent-session-resume", description="Resume one Agent Session after checking preserved object references for staleness.")
    agent_session_resume.add_argument("session")
    agent_session_resume.add_argument("--workspace", default="")

    agent_session_fork = sub.add_parser("agent-session-fork", description="Fork one Agent Session from a parent Turn without mutating the parent chain.")
    agent_session_fork.add_argument("session")
    agent_session_fork.add_argument("--from-turn", default="")
    agent_session_fork.add_argument("--title", default="")
    agent_session_fork.add_argument("--workspace", default="")

    agent_context_compact = sub.add_parser("agent-context-compact", description="Create an evidence-preserving context snapshot without deleting Turn history.")
    agent_context_compact.add_argument("--session", required=True)
    agent_context_compact.add_argument("--level", type=int, required=True, choices=[1, 2, 3, 4])
    agent_context_compact.add_argument("--workspace", default="")

    agent_runtime_profiles = sub.add_parser("agent-runtime-profiles", description="List workspace Agent Runtime Profiles and the selected provider boundary.")
    agent_runtime_profiles.add_argument("--workspace", default="")

    agent_runtime_profile_set = sub.add_parser("agent-runtime-profile-set", description="Preview or confirm the workspace Agent Runtime Profile selection.")
    agent_runtime_profile_set.add_argument("--profile", required=True, choices=["deterministic", "deepseek", "local-openai"])
    agent_runtime_profile_set.add_argument("--workspace", default="")
    agent_runtime_profile_set.add_argument("--yes", action="store_true")

    agent_provider_evaluations = sub.add_parser("agent-provider-evaluations", description="List the redacted workspace Provider evaluation dashboard.")
    agent_provider_evaluations.add_argument("--workspace", default="")
    agent_provider_evaluations.add_argument("--limit", type=int, default=30)

    business_expression_cases = sub.add_parser("business-expression-cases", description="List the immutable deterministic Business Expression Case catalog.")

    plan_quality_evaluate = sub.add_parser("plan-quality-evaluate", description="Run the local deterministic planning benchmark and persist one redacted Scorecard.")
    plan_quality_evaluate.add_argument("--workspace", default="")

    plan_quality_scorecards = sub.add_parser("plan-quality-scorecards", description="List bounded workspace Plan Quality Scorecards with live freshness.")
    plan_quality_scorecards.add_argument("--workspace", default="")
    plan_quality_scorecards.add_argument("--limit", type=int, default=20)

    agent_provider_evaluation_record = sub.add_parser("agent-provider-evaluation-record", description="Record one redacted terminal Provider evaluation receipt.")
    agent_provider_evaluation_record.add_argument("--workspace", default="")
    agent_provider_evaluation_record.add_argument("--profile", required=True, choices=["deterministic", "deepseek", "local-openai"])
    agent_provider_evaluation_record.add_argument("--profile-fingerprint", default="")
    agent_provider_evaluation_record.add_argument("--provider", required=True)
    agent_provider_evaluation_record.add_argument("--model", required=True)
    agent_provider_evaluation_record.add_argument("--request-fingerprint", default="")
    agent_provider_evaluation_record.add_argument("--context-fingerprint", default="")
    agent_provider_evaluation_record.add_argument("--status", required=True, choices=["passed", "fallback", "blocked", "failed", "skipped"])
    agent_provider_evaluation_record.add_argument("--validation-status", default="not-run")
    agent_provider_evaluation_record.add_argument("--duration-ms", type=int, default=0)
    agent_provider_evaluation_record.add_argument("--prompt-tokens", type=int)
    agent_provider_evaluation_record.add_argument("--completion-tokens", type=int)
    agent_provider_evaluation_record.add_argument("--total-tokens", type=int)
    agent_provider_evaluation_record.add_argument("--estimated-cost-usd", type=float, default=0)
    agent_provider_evaluation_record.add_argument("--attempts", type=int, default=0)
    agent_provider_evaluation_record.add_argument("--fallback-reason", default="")
    agent_provider_evaluation_record.add_argument("--shadow", action="store_true")
    agent_provider_evaluation_record.add_argument("--audit-json", default="{}")

    sub.add_parser("status")

    workspace_manifest = sub.add_parser("workspace-manifest", description="Build the deterministic read-only manifest for one workspace.")
    workspace_manifest.add_argument("--workspace", default="")

    runtime_catalog = sub.add_parser("runtime-catalog", description="List the workspace-scoped semantic and execution catalog without credentials or raw rows.")
    runtime_catalog.add_argument("--workspace", default="")

    business_field_profiles = sub.add_parser("business-field-profiles", description="Derive bounded field-shape evidence without promoting candidates to confirmed semantics.")
    business_field_profiles.add_argument("--workspace", default="")
    business_field_profiles.add_argument("--table", default="")
    business_field_profiles.add_argument("--field", default="")

    sub.add_parser("quality-doctor")

    sub.add_parser("context-pack")

    context_term = sub.add_parser("context-term")
    context_term.add_argument("--term", default="")
    context_term.add_argument("--name", required=True)
    context_term.add_argument("--definition", required=True)
    context_term.add_argument("--alias", action="append", default=[])
    context_term.add_argument("--scope-type", default="workspace", choices=["workspace", "source", "table", "field", "metric"])
    context_term.add_argument("--scope-ref", default="")
    context_term.add_argument("--status", default="draft", choices=["draft", "confirmed", "deprecated"])
    context_term.add_argument("--source", default="manual")
    context_term.add_argument("--evidence", action="append", default=[])
    context_term.add_argument("--yes", action="store_true")

    context_rule = sub.add_parser("context-rule")
    context_rule.add_argument("--rule", default="")
    context_rule.add_argument("--title", required=True)
    context_rule.add_argument("--statement", required=True)
    context_rule.add_argument("--type", default="other", choices=["definition", "enum", "unit", "null", "default_filter", "canonical_source", "aggregation", "other"])
    context_rule.add_argument("--applies-to", action="append", default=[])
    context_rule.add_argument("--status", default="draft", choices=["draft", "confirmed", "deprecated"])
    context_rule.add_argument("--source", default="manual")
    context_rule.add_argument("--evidence", action="append", default=[])
    context_rule.add_argument("--yes", action="store_true")

    sub.add_parser("knowledge-source-adapters", description="List declaration-only local knowledge source adapters and their safety boundary.")

    knowledge_sources = sub.add_parser("knowledge-sources", description="List redacted immutable knowledge source snapshots for one workspace.")
    knowledge_sources.add_argument("--workspace", default="")
    knowledge_sources.add_argument("--limit", type=int, default=50)

    semantic_patch_propose = sub.add_parser("semantic-patch-propose", description="Preview or persist reviewable semantic patches from a bounded source or structured user correction.")
    semantic_patch_propose.add_argument("--workspace", default="")
    semantic_patch_propose.add_argument("--input", default="")
    semantic_patch_propose.add_argument("--adapter", default="auto", choices=["auto", "knowledge-json-v1", "knowledge-markdown-v1", "user-correction-v1"])
    semantic_patch_propose.add_argument("--source-type", default="", choices=["", "data-dictionary", "documentation", "user-correction"])
    semantic_patch_propose.add_argument("--source-name", default="")
    semantic_patch_propose.add_argument("--kind", default="", choices=["", "term", "rule", "field-semantic"])
    semantic_patch_propose.add_argument("--term", default="")
    semantic_patch_propose.add_argument("--name", default="")
    semantic_patch_propose.add_argument("--definition", default="")
    semantic_patch_propose.add_argument("--alias", action="append", default=[])
    semantic_patch_propose.add_argument("--scope-type", default="workspace", choices=["workspace", "source", "table", "field", "metric"])
    semantic_patch_propose.add_argument("--scope-ref", default="")
    semantic_patch_propose.add_argument("--rule", default="")
    semantic_patch_propose.add_argument("--title", default="")
    semantic_patch_propose.add_argument("--statement", default="")
    semantic_patch_propose.add_argument("--type", default="other", choices=["definition", "enum", "unit", "null", "default_filter", "canonical_source", "aggregation", "other"])
    semantic_patch_propose.add_argument("--applies-to", action="append", default=[])
    semantic_patch_propose.add_argument("--table", default="")
    semantic_patch_propose.add_argument("--field", default="")
    semantic_patch_propose.add_argument("--role", default="")
    semantic_patch_propose.add_argument("--usage", action="append", default=[])
    semantic_patch_propose.add_argument("--tag", action="append", default=[])
    semantic_patch_propose.add_argument("--confidence", type=float, default=1.0)
    semantic_patch_propose.add_argument("--note", default="")
    semantic_patch_propose.add_argument("--yes", action="store_true")

    semantic_patch_proposals = sub.add_parser("semantic-patch-proposals", description="List or inspect workspace-scoped semantic patch proposals with live freshness checks.")
    semantic_patch_proposals.add_argument("--workspace", default="")
    semantic_patch_proposals.add_argument("--proposal", default="")
    semantic_patch_proposals.add_argument("--status", default="", choices=["", "pending", "accepted", "rejected", "stale"])
    semantic_patch_proposals.add_argument("--limit", type=int, default=100)

    semantic_patch_review = sub.add_parser("semantic-patch-review", description="Preview or confirm acceptance or rejection of one current semantic patch proposal.")
    semantic_patch_review.add_argument("--workspace", default="")
    semantic_patch_review.add_argument("--proposal", required=True)
    semantic_patch_review.add_argument("--decision", required=True, choices=["accept", "reject"])
    semantic_patch_review.add_argument("--note", default="")
    semantic_patch_review.add_argument("--yes", action="store_true")

    query_receipts = sub.add_parser("query-receipts")
    query_receipts.add_argument("--receipt", default="")
    query_receipts.add_argument("--limit", type=int, default=20)

    export_evidence = sub.add_parser("export-evidence")
    export_evidence.add_argument("--receipt", required=True)
    export_evidence.add_argument("--output", default="")

    export_analysis = sub.add_parser("export-analysis", description="Export one receipt-bound Analysis Unit as deterministic Excel and report artifacts without requerying.")
    export_analysis.add_argument("--receipt", required=True)
    export_analysis.add_argument("--unit", required=True)
    export_analysis.add_argument("--output", default="")

    confirmed_queries = sub.add_parser("confirmed-queries")
    confirmed_queries.add_argument("--status", default="", choices=["", "candidate", "confirmed", "stale", "deprecated"])
    confirmed_queries.add_argument("--limit", type=int, default=20)

    confirmed_plans = sub.add_parser("confirmed-plans", description="List evidence-bound plan memories explicitly promoted in the active workspace.")
    confirmed_plans.add_argument("--status", default="", choices=["", "confirmed", "stale", "deprecated"])
    confirmed_plans.add_argument("--limit", type=int, default=20)

    recall_receipts = sub.add_parser("recall-receipts", description="List bounded hybrid-recall receipts without exposing raw data rows.")
    recall_receipts.add_argument("--receipt", default="")
    recall_receipts.add_argument("--limit", type=int, default=20)

    confirm_query = sub.add_parser("confirm-query")
    confirm_query.add_argument("--query", required=True)
    confirm_query.add_argument("--status", default="confirmed", choices=["confirmed", "deprecated"])
    confirm_query.add_argument("--yes", action="store_true")

    analysis_runs = sub.add_parser("analysis-runs")
    analysis_runs.add_argument("--run", default="")
    analysis_runs.add_argument("--limit", type=int, default=30)

    exploration_threads = sub.add_parser("exploration-threads", description="List or inspect workspace Exploration Threads with live Anchor freshness.")
    exploration_threads.add_argument("--thread", default="")
    exploration_threads.add_argument("--limit", type=int, default=30)

    exploration_thread_create = sub.add_parser("exploration-thread-create", description="Preview or confirm one root Exploration Thread from a current verified result.")
    exploration_thread_create.add_argument("--run", required=True)
    exploration_thread_create.add_argument("--unit", default="")
    exploration_thread_create.add_argument("--session", default="")
    exploration_thread_create.add_argument("--turn", default="")
    exploration_thread_create.add_argument("--title", default="")
    exploration_thread_create.add_argument("--label", default="")
    exploration_thread_create.add_argument("--expected-plan", default="")
    exploration_thread_create.add_argument("--yes", action="store_true")

    exploration_anchor_add = sub.add_parser("exploration-anchor-add", description="Preview or confirm one immutable child Anchor whose Run follows the selected parent lineage.")
    exploration_anchor_add.add_argument("--thread", required=True)
    exploration_anchor_add.add_argument("--parent-anchor", default="")
    exploration_anchor_add.add_argument("--run", required=True)
    exploration_anchor_add.add_argument("--unit", default="")
    exploration_anchor_add.add_argument("--session", default="")
    exploration_anchor_add.add_argument("--turn", default="")
    exploration_anchor_add.add_argument("--label", default="")
    exploration_anchor_add.add_argument("--expected-plan", default="")
    exploration_anchor_add.add_argument("--yes", action="store_true")

    exploration_board_set = sub.add_parser("exploration-board-set", description="Preview or confirm pinning, reordering, or removing one existing Anchor on the Result Board.")
    exploration_board_set.add_argument("--thread", required=True)
    exploration_board_set.add_argument("--anchor", required=True)
    exploration_board_set.add_argument("--state", required=True, choices=["pinned", "removed"])
    exploration_board_set.add_argument("--position", type=int, default=0)
    exploration_board_set.add_argument("--expected-plan", default="")
    exploration_board_set.add_argument("--yes", action="store_true")

    analysis_unit_build = sub.add_parser("analysis-unit-build", description="Freeze a bounded verified result snapshot against an existing Query Receipt.")
    analysis_unit_build.add_argument("--receipt", required=True)
    analysis_unit_build.add_argument("--kind", default="auto", choices=["auto", "metric", "comparison", "trend", "composition", "ranking", "anomaly"])
    analysis_unit_build.add_argument("--rows-json", required=True)
    analysis_unit_build.add_argument("--title", default="")
    analysis_unit_build.add_argument("--preferred-chart", default="", choices=["", "metric", "bar", "line", "pie", "table"])

    analysis_units = sub.add_parser("analysis-units", description="List or inspect workspace-scoped Analysis Units.")
    analysis_units.add_argument("--unit", default="")
    analysis_units.add_argument("--receipt", default="")
    analysis_units.add_argument("--limit", type=int, default=30)

    analysis_unit_verify = sub.add_parser("analysis-unit-verify", description="Recalculate an Analysis Unit from its frozen snapshot and compare fingerprints.")
    analysis_unit_verify.add_argument("--unit", required=True)

    chart_adapt = sub.add_parser("chart-adapt", description="Choose a whitelisted chart from a validated Analysis Unit shape.")
    chart_adapt.add_argument("--unit", required=True)
    chart_adapt.add_argument("--preferred-chart", default="", choices=["", "metric", "bar", "line", "pie", "table"])

    jobs = sub.add_parser("jobs", description="List durable analysis jobs and ordered runtime events.")
    jobs.add_argument("--job", default="")
    jobs.add_argument("--status", action="append", default=[])
    jobs.add_argument("--limit", type=int, default=50)
    jobs.add_argument("--include-events", action="store_true")
    jobs.add_argument("--events-after", type=int, default=0)
    jobs.add_argument("--event-limit", type=int, default=200)

    job_cancel = sub.add_parser("job-cancel", description="Request cooperative cancellation for an active analysis job.")
    job_cancel.add_argument("job")
    job_cancel.add_argument("--reason", default="user-requested")
    job_cancel.add_argument("--yes", action="store_true")

    job_recover = sub.add_parser("job-recover", description="Close interrupted jobs after a confirmed local runtime restart.")
    job_recover.add_argument("--all", action="store_true")
    job_recover.add_argument("--yes", action="store_true")

    source_job_create = sub.add_parser(
        "source-intelligence-job-create",
        description="Create a durable, queued Source Intelligence job.",
    )
    source_job_create.add_argument("inputs", nargs="+")
    source_job_create.add_argument("--workspace", default="")
    source_job_create.add_argument("--output-dir")
    source_job_create.add_argument("--label")

    source_job_run = sub.add_parser(
        "source-intelligence-job-run",
        description="Run one previously queued Source Intelligence job.",
    )
    source_job_run.add_argument("--job", required=True)
    source_job_run.add_argument("--workspace", default="")

    job_process_exit = sub.add_parser(
        "job-process-exit",
        description="Reconcile an owned worker process exit with durable job state.",
    )
    job_process_exit.add_argument("--job", required=True)
    job_process_exit.add_argument("--workspace", default="")
    job_process_exit.add_argument("--exit-code", type=int)
    job_process_exit.add_argument("--signal", default="")

    workspace_create = sub.add_parser("workspace-create")
    workspace_create.add_argument("--name", required=True)
    workspace_create.add_argument("--yes", action="store_true")

    workspace_select = sub.add_parser("workspace-select")
    workspace_select.add_argument("workspace")
    workspace_select.add_argument("--yes", action="store_true")

    workspace_rename = sub.add_parser("workspace-rename")
    workspace_rename.add_argument("workspace")
    workspace_rename.add_argument("--name", required=True)
    workspace_rename.add_argument("--yes", action="store_true")

    workspace_delete = sub.add_parser("workspace-delete")
    workspace_delete.add_argument("workspace")
    workspace_delete.add_argument("--yes", action="store_true")

    domain_packs = sub.add_parser("domain-packs", description="List validated Domain Packs and the current workspace activation state.")
    domain_packs.add_argument("--workspace", default="")

    domain_pack_set = sub.add_parser("domain-pack-set", description="Preview or confirm one workspace-scoped Domain Pack state change.")
    domain_pack_set.add_argument("--pack", required=True)
    domain_pack_set.add_argument("--state", required=True, choices=["enabled", "disabled"])
    domain_pack_set.add_argument("--workspace", default="")
    domain_pack_set.add_argument("--yes", action="store_true")

    domain_pack_lint = sub.add_parser("domain-pack-lint", description="Validate an external static Domain Pack package and its server-trusted signature.")
    domain_pack_lint.add_argument("--package", required=True)

    domain_pack_install = sub.add_parser("domain-pack-install", description="Preview or confirm installation or upgrade of a signed external Domain Pack.")
    domain_pack_install.add_argument("--package", required=True)
    domain_pack_install.add_argument("--yes", action="store_true")

    domain_pack_uninstall = sub.add_parser("domain-pack-uninstall", description="Preview or confirm uninstall of an external Domain Pack.")
    domain_pack_uninstall.add_argument("--pack", required=True)
    domain_pack_uninstall.add_argument("--yes", action="store_true")

    analytical_skills = sub.add_parser("analytical-skills", description="List declaration-only Analytical Skills and workspace activation state.")
    analytical_skills.add_argument("--workspace", default="")

    analytical_skill_lint = sub.add_parser("analytical-skill-lint", description="Validate one declaration-only Analytical Skill manifest.")
    analytical_skill_lint.add_argument("--manifest", required=True)

    analytical_skill_install = sub.add_parser("analytical-skill-install", description="Preview or confirm installation or upgrade of one declaration-only Analytical Skill.")
    analytical_skill_install.add_argument("--manifest", required=True)
    analytical_skill_install.add_argument("--yes", action="store_true")

    analytical_skill_uninstall = sub.add_parser("analytical-skill-uninstall", description="Preview or confirm removal of an external Analytical Skill.")
    analytical_skill_uninstall.add_argument("--skill", required=True)
    analytical_skill_uninstall.add_argument("--yes", action="store_true")

    analytical_skill_set = sub.add_parser("analytical-skill-set", description="Preview or confirm one workspace-scoped Analytical Skill state change.")
    analytical_skill_set.add_argument("--skill", required=True)
    analytical_skill_set.add_argument("--state", required=True, choices=["enabled", "disabled"])
    analytical_skill_set.add_argument("--workspace", default="")
    analytical_skill_set.add_argument("--yes", action="store_true")

    analytical_skill_match = sub.add_parser("analytical-skill-match", description="Match enabled Analytical Skills against a resolved task type and semantic roles.")
    analytical_skill_match.add_argument("--task-type", required=True, choices=["overview", "comparison", "trend", "composition", "ranking", "anomaly", "reconciliation", "diagnosis"])
    analytical_skill_match.add_argument("--role", action="append", choices=["measure", "dimension", "time", "identity", "attribute"], default=[])
    analytical_skill_match.add_argument("--domain-pack", action="append", default=[])
    analytical_skill_match.add_argument("--skill", default="")
    analytical_skill_match.add_argument("--workspace", default="")

    source_run = sub.add_parser("source-run")
    source_run.add_argument("source_run_id")

    sub.add_parser("list-tables")

    inspect_table = sub.add_parser("inspect-table")
    inspect_table.add_argument("table")

    rename_source = sub.add_parser("rename-source")
    rename_source.add_argument("source")
    rename_source.add_argument("--name", required=True)
    rename_source.add_argument("--yes", action="store_true")

    delete_source = sub.add_parser("delete-source")
    delete_source.add_argument("source")
    delete_source.add_argument("--yes", action="store_true")

    source_intelligence_run = sub.add_parser("source-intelligence")
    source_intelligence_run.add_argument("inputs", nargs="*")
    source_intelligence_run.add_argument("--workspace", default="")
    source_intelligence_run.add_argument("--output-dir")
    source_intelligence_run.add_argument("--label")

    source_intelligence_runs = sub.add_parser("source-intelligence-runs")
    source_intelligence_runs.add_argument("--limit", type=int, default=10)
    source_intelligence_runs.add_argument("--all", action="store_true")

    source_dashboard_draft = sub.add_parser("source-dashboard-draft")
    source_dashboard_draft.add_argument("--run", default="")
    source_dashboard_draft.add_argument("--name", default="")
    source_dashboard_draft.add_argument("--limit", type=int, default=4)

    workbench = sub.add_parser("workbench")
    workbench.add_argument("--limit", type=int, default=12)

    list_navigation = sub.add_parser("list-navigation")
    list_navigation.add_argument("--all", action="store_true")

    navigation_op = sub.add_parser("navigation-op")
    navigation_op.add_argument("--module", required=True)
    navigation_op.add_argument("--op", required=True, choices=["rename", "move", "hide", "show"])
    navigation_op.add_argument("--name", default="")
    navigation_op.add_argument("--sort", type=int, default=0)
    navigation_op.add_argument("--yes", action="store_true")

    sub.add_parser("dashboard-widget-catalog")
    sub.add_parser("cli-capabilities")

    recommend_widgets = sub.add_parser("recommend-widgets")
    recommend_widgets.add_argument("--table")
    recommend_widgets.add_argument("--all", action="store_true")
    recommend_widgets.add_argument("--limit", type=int, default=7)

    add_recommended_widgets = sub.add_parser("add-recommended-widgets")
    add_recommended_widgets.add_argument("--dashboard", default="default")
    add_recommended_widgets.add_argument("--table")
    add_recommended_widgets.add_argument("--limit", type=int, default=4)
    add_recommended_widgets.add_argument("--allow-duplicates", action="store_true")
    add_recommended_widgets.add_argument("--yes", action="store_true")

    save_dashboard_modules = sub.add_parser("save-dashboard-modules")
    save_dashboard_modules.add_argument("--dashboard", default="default")
    save_dashboard_modules.add_argument("--name", default="")
    save_dashboard_modules.add_argument("--default-table", default="")
    save_dashboard_modules.add_argument("--canvas-width-mode", default="stretch", choices=["stretch", "center"])
    save_dashboard_modules.add_argument("--widgets-json", default="[]")
    save_dashboard_modules.add_argument("--layout-json", default="[]")
    save_dashboard_modules.add_argument("--filters-json", default="[]")
    save_dashboard_modules.add_argument("--yes", action="store_true")

    business_dashboard = sub.add_parser("business-dashboard")
    business_dashboard.add_argument("--op", default="draft", choices=["draft", "create", "overwrite"])
    business_dashboard.add_argument("--dashboard", default="default")
    business_dashboard.add_argument("--name", default="")
    business_dashboard.add_argument("--table")
    business_dashboard.add_argument("--template", default="business", choices=["business", ERP_UNIT_LIBRARY_TEMPLATE_KEY])
    business_dashboard.add_argument("--limit", type=int, default=10)
    business_dashboard.add_argument("--yes", action="store_true")

    erp_unit_library = sub.add_parser("erp-unit-library")
    erp_unit_library.add_argument("--table")
    erp_unit_library.add_argument("--limit", type=int, default=24)
    erp_unit_library.add_argument("--select", action="store_true")
    erp_unit_library.add_argument("--summary", action="store_true")

    add_widget = sub.add_parser("add-widget")
    add_widget.add_argument("--dashboard", default="default")
    add_widget.add_argument("--widget")
    add_widget.add_argument("--type", default="bar", choices=B_WIDGET_TYPES)
    add_widget.add_argument("--table")
    add_widget.add_argument("--view")
    add_widget.add_argument("--title")
    add_widget.add_argument("--subtitle")
    add_widget.add_argument("--dimension")
    add_widget.add_argument("--measure")
    add_widget.add_argument("--agg", choices=sorted(SAFE_AGGREGATIONS))
    add_widget.add_argument("--top-n", type=int, default=12)
    add_widget.add_argument("--value-format", default="auto", choices=B_VALUE_FORMATS)
    add_widget.add_argument("--text-content")
    add_widget_style_arguments(add_widget)
    add_widget.add_argument("--yes", action="store_true")

    add_relationship_widget = sub.add_parser("add-relationship-widget")
    add_relationship_widget.add_argument("--dashboard", default="default")
    add_relationship_widget.add_argument("--widget")
    add_relationship_widget.add_argument("--relationship", default="")
    add_relationship_widget.add_argument("--type", default="bar", choices=B_RELATIONSHIP_WIDGET_TYPES)
    add_relationship_widget.add_argument("--title")
    add_relationship_widget.add_argument("--subtitle")
    add_relationship_widget.add_argument("--group")
    add_relationship_widget.add_argument("--measure")
    add_relationship_widget.add_argument("--agg", default="count", choices=sorted(SAFE_AGGREGATIONS))
    add_relationship_widget.add_argument("--top-n", type=int, default=12)
    add_relationship_widget.add_argument("--value-format", default="auto", choices=B_VALUE_FORMATS)
    add_widget_style_arguments(add_relationship_widget)
    add_relationship_widget.add_argument("--yes", action="store_true")

    set_widget = sub.add_parser("set-widget")
    set_widget.add_argument("--widget", required=True)
    set_widget.add_argument("--type", choices=B_WIDGET_TYPES)
    set_widget.add_argument("--table")
    set_widget.add_argument("--view")
    set_widget.add_argument("--title")
    set_widget.add_argument("--subtitle")
    set_widget.add_argument("--dimension")
    set_widget.add_argument("--measure")
    set_widget.add_argument("--agg", choices=sorted(SAFE_AGGREGATIONS))
    set_widget.add_argument("--top-n", type=int)
    set_widget.add_argument("--value-format", choices=B_VALUE_FORMATS)
    set_widget.add_argument("--text-content")
    add_widget_style_arguments(set_widget)
    set_widget.add_argument("--filter", action="append", default=[])
    set_widget.add_argument("--clear-filters", action="store_true")
    set_widget.add_argument("--yes", action="store_true")

    copy_widget = sub.add_parser("copy-widget")
    copy_widget.add_argument("--widget", required=True)
    copy_widget.add_argument("--dashboard")
    copy_widget.add_argument("--title")
    copy_widget.add_argument("--clear-filters", action="store_true")
    copy_widget.add_argument("--yes", action="store_true")

    remove_widget = sub.add_parser("remove-widget")
    remove_widget.add_argument("--widget", required=True)
    remove_widget.add_argument("--yes", action="store_true")

    set_import_policy = sub.add_parser("set-import-policy")
    set_import_policy.add_argument("--table", required=True)
    set_import_policy.add_argument("--unique-fields", required=True)
    set_import_policy.add_argument("--conflict-rule", default="overwrite", choices=["overwrite", "fill-empty", "skip-existing"])
    set_import_policy.add_argument("--yes", action="store_true")

    preview = sub.add_parser("preview-import")
    preview.add_argument("file")
    preview.add_argument("--table")
    preview.add_argument("--unique-fields")
    preview.add_argument("--conflict-rule", choices=["overwrite", "fill-empty", "skip-existing"])

    commit = sub.add_parser("import-commit")
    commit.add_argument("file")
    commit.add_argument("--table")
    commit.add_argument("--name")
    commit.add_argument("--mode", default="create", choices=["create", "merge", "replace"])
    commit.add_argument("--unique-fields")
    commit.add_argument("--conflict-rule", choices=["overwrite", "fill-empty", "skip-existing"])
    commit.add_argument("--yes", action="store_true")

    preview_folder = sub.add_parser("preview-import-folder")
    preview_folder.add_argument("path")
    preview_folder.add_argument("--limit", type=int, default=200)
    preview_folder.add_argument("--no-recursive", action="store_true")

    import_folder = sub.add_parser("import-folder")
    import_folder.add_argument("path")
    import_folder.add_argument("--limit", type=int, default=200)
    import_folder.add_argument("--no-recursive", action="store_true")
    import_folder.add_argument("--yes", action="store_true")

    list_import_jobs = sub.add_parser("list-import-jobs")
    list_import_jobs.add_argument("--table")
    list_import_jobs.add_argument("--status")
    list_import_jobs.add_argument("--search")
    list_import_jobs.add_argument("--limit", type=int, default=20)

    remove_import_job = sub.add_parser("remove-import-job")
    remove_import_job.add_argument("--job", required=True)
    remove_import_job.add_argument("--yes", action="store_true")

    list_connectors = sub.add_parser("list-connectors")
    list_connectors.add_argument("--type", choices=sorted(VALID_CONNECTOR_TYPES))
    list_connectors.add_argument("--status", choices=sorted(VALID_CONNECTOR_STATUSES))
    list_connectors.add_argument("--search")

    save_connector = sub.add_parser("save-connector")
    save_connector.add_argument("--connector")
    save_connector.add_argument("--name", required=True)
    save_connector.add_argument("--type", default="file", choices=sorted(VALID_CONNECTOR_TYPES))
    save_connector.add_argument("--provider", default="")
    save_connector.add_argument("--status", default="draft", choices=sorted(VALID_CONNECTOR_STATUSES))
    save_connector.add_argument("--endpoint", default="")
    save_connector.add_argument("--resource", default="")
    save_connector.add_argument("--page-param", default="")
    save_connector.add_argument("--page-size-param", default="")
    save_connector.add_argument("--page-size", type=int, default=100)
    save_connector.add_argument("--max-pages", type=int, default=1)
    save_connector.add_argument("--import-mode", default="auto", choices=["auto", "create", "replace", "merge"])
    save_connector.add_argument("--target-table", default="")
    save_connector.add_argument("--unique-fields", default="")
    save_connector.add_argument("--conflict-rule", default="overwrite", choices=["overwrite", "fill-empty", "skip-existing"])
    save_connector.add_argument("--schedule", default="manual")
    save_connector.add_argument("--notes", default="")
    save_connector.add_argument("--credential-ref", default=None)
    save_connector.add_argument("--yes", action="store_true")

    sync_connector = sub.add_parser("sync-connector")
    sync_connector.add_argument("--connector", required=True)
    sync_connector.add_argument("--allow-paused", action="store_true")
    sync_connector.add_argument("--yes", action="store_true")

    remove_connector = sub.add_parser("remove-connector")
    remove_connector.add_argument("--connector", required=True)
    remove_connector.add_argument("--yes", action="store_true")

    sub.add_parser("list-connector-adapters")

    discover_connector = sub.add_parser("discover-connector")
    discover_connector.add_argument("--connector", required=True)

    preview_connector = sub.add_parser("preview-connector")
    preview_connector.add_argument("--connector", required=True)
    preview_connector.add_argument("--limit", type=int, default=20)

    plan_connector_sync = sub.add_parser("plan-connector-sync")
    plan_connector_sync.add_argument("--connector", required=True)

    infer_semantics = sub.add_parser("infer-semantics")
    infer_semantics.add_argument("--table", default="")
    infer_semantics.add_argument("--overwrite-manual", action="store_true")
    infer_semantics.add_argument("--yes", action="store_true")

    list_semantics = sub.add_parser("list-semantics")
    list_semantics.add_argument("--table", default="")

    set_semantic = sub.add_parser("set-semantic")
    set_semantic.add_argument("table")
    set_semantic.add_argument("field")
    set_semantic.add_argument("--role", required=True, choices=["event_time", "time", "measure", "dimension", "identity_key", "identifier", "status", "text"])
    set_semantic.add_argument("--tag", action="append", default=[])
    set_semantic.add_argument("--usage", action="append", default=[])
    set_semantic.add_argument("--confidence", type=float, default=1.0)
    set_semantic.add_argument("--note", default="")
    set_semantic.add_argument("--yes", action="store_true")

    infer_metrics = sub.add_parser("infer-metrics")
    infer_metrics.add_argument("--table", default="")
    infer_metrics.add_argument("--yes", action="store_true")

    list_metrics = sub.add_parser("list-metrics")
    list_metrics.add_argument("--table", default="")
    list_metrics.add_argument("--all", action="store_true")

    add_metric = sub.add_parser("add-metric")
    add_metric.add_argument("--id", default="")
    add_metric.add_argument("--name", required=True)
    add_metric.add_argument("--table", required=True)
    add_metric.add_argument("--field", default="*")
    add_metric.add_argument("--agg", default="count", choices=sorted(SAFE_AGGREGATIONS))
    add_metric.add_argument("--dimension", default="")
    add_metric.add_argument("--time-field", default="")
    add_metric.add_argument("--filter", action="append", default=[])
    add_metric.add_argument("--value-format", default="auto", choices=B_VALUE_FORMATS)
    add_metric.add_argument("--description", default="")
    add_metric.add_argument("--yes", action="store_true")

    list_formulas = sub.add_parser("list-formulas")
    list_formulas.add_argument("--table", default="")
    list_formulas.add_argument("--all", action="store_true")

    save_formula = sub.add_parser("save-formula")
    save_formula.add_argument("--id", default="")
    save_formula.add_argument("--name", required=True)
    save_formula.add_argument("--table", required=True)
    save_formula.add_argument("--expression", required=True)
    save_formula.add_argument("--mode", default="aggregate", choices=["row", "aggregate"])
    save_formula.add_argument("--dimension", default="")
    save_formula.add_argument("--time-field", default="")
    save_formula.add_argument("--value-format", default="auto", choices=B_VALUE_FORMATS)
    save_formula.add_argument("--description", default="")
    save_formula.add_argument("--yes", action="store_true")

    delete_formula = sub.add_parser("delete-formula")
    delete_formula.add_argument("formula")
    delete_formula.add_argument("--yes", action="store_true")

    query_metric = sub.add_parser("query-metric")
    query_metric.add_argument("metric")
    query_metric.add_argument("--group", action="append", default=[])
    query_metric.add_argument("--filter", action="append", default=[])
    query_metric.add_argument("--sort", default="")
    query_metric.add_argument("--limit", type=int, default=50)

    preferences = sub.add_parser("preferences")
    preferences.add_argument("--theme-key")
    preferences.add_argument("--require-delete-name-confirmation", choices=["true", "false"])
    preferences.add_argument("--auto-save-dashboard-on-switch", choices=["true", "false"])
    preferences.add_argument("--agent-can-manage-generated-assets", choices=["true", "false"])
    preferences.add_argument("--agent-can-manage-manual-assets", choices=["true", "false"])
    preferences.add_argument("--yes", action="store_true")

    theme_palettes = sub.add_parser("theme-palettes")
    theme_palettes.add_argument("--action", default="list", choices=["list", "save", "upsert", "delete"])
    theme_palettes.add_argument("--theme-key")
    theme_palettes.add_argument("--name", default="")
    theme_palettes.add_argument("--mode", default="light", choices=["light", "dark"])
    theme_palettes.add_argument("--tokens-json", default="")
    theme_palettes.add_argument("--sort", type=int, default=0)
    theme_palettes.add_argument("--yes", action="store_true")

    sub.add_parser("validate-config")

    export_config = sub.add_parser("export-config")
    export_config.add_argument("output", nargs="?")

    apply_config = sub.add_parser("apply-config")
    apply_config.add_argument("input")
    apply_config.add_argument("--yes", action="store_true")

    query = sub.add_parser("query")
    query.add_argument("--table", required=True)
    query.add_argument("--group")
    query.add_argument("--measure", default="*")
    query.add_argument("--agg", default="count")
    query.add_argument("--limit", type=int, default=20)
    query.add_argument("--request", default="")

    query_table = sub.add_parser("query-table")
    query_table.add_argument("--table")
    query_table.add_argument("--view")
    query_table.add_argument("--mode", default="detail", choices=["detail", "aggregate"])
    query_table.add_argument("--column", action="append")
    query_table.add_argument("--filter", action="append", default=[])
    query_table.add_argument("--sort", action="append", default=[])
    query_table.add_argument("--search")
    query_table.add_argument("--offset", type=int, default=0)
    query_table.add_argument("--limit", type=int, default=50)
    query_table.add_argument("--group", action="append", default=[])
    query_table.add_argument("--measure", default="")
    query_table.add_argument("--agg", default="count", choices=sorted(SAFE_AGGREGATIONS))

    list_views = sub.add_parser("list-views")
    list_views.add_argument("--table")

    save_view = sub.add_parser("save-view")
    save_view.add_argument("--view")
    save_view.add_argument("--table", required=True)
    save_view.add_argument("--name", required=True)
    save_view.add_argument("--tag")
    save_view.add_argument("--mode", default="detail", choices=["detail", "aggregate"])
    save_view.add_argument("--columns", default="")
    save_view.add_argument("--filter", action="append", default=[])
    save_view.add_argument("--sort", action="append", default=[])
    save_view.add_argument("--search", default="")
    save_view.add_argument("--agent", action="store_true")
    save_view.add_argument("--yes", action="store_true")

    copy_view = sub.add_parser("copy-view")
    copy_view.add_argument("--view", required=True)
    copy_view.add_argument("--name")
    copy_view.add_argument("--tag")
    copy_view.add_argument("--yes", action="store_true")

    delete_view = sub.add_parser("delete-view")
    delete_view.add_argument("--view", required=True)
    delete_view.add_argument("--yes", action="store_true")

    dashboards = sub.add_parser("dashboards")
    dashboards.add_argument("--dashboard")

    list_filters = sub.add_parser("list-filters")
    list_filters.add_argument("--dashboard", default="default")

    add_filter = sub.add_parser("add-filter")
    add_filter.add_argument("--dashboard", default="default")
    add_filter.add_argument("--field", required=True)
    add_filter.add_argument("--operator", default="equals", choices=B_DASHBOARD_FILTER_OPERATORS)
    add_filter.add_argument("--value", default="")
    add_filter.add_argument("--disabled", action="store_true")
    add_filter.add_argument("--yes", action="store_true")

    set_filter = sub.add_parser("set-filter")
    set_filter.add_argument("--dashboard", default="default")
    set_filter.add_argument("--filter", required=True)
    set_filter.add_argument("--field", required=True)
    set_filter.add_argument("--operator", default="equals", choices=B_DASHBOARD_FILTER_OPERATORS)
    set_filter.add_argument("--value", default="")
    set_filter.add_argument("--disabled", action="store_true")
    set_filter.add_argument("--yes", action="store_true")

    remove_filter = sub.add_parser("remove-filter")
    remove_filter.add_argument("--dashboard", default="default")
    remove_filter.add_argument("--filter", required=True)
    remove_filter.add_argument("--yes", action="store_true")

    remove_stale_filters = sub.add_parser("remove-stale-filters")
    remove_stale_filters.add_argument("--dashboard", default="default")
    remove_stale_filters.add_argument("--yes", action="store_true")

    clear_filters = sub.add_parser("clear-filters")
    clear_filters.add_argument("--dashboard", default="default")
    clear_filters.add_argument("--yes", action="store_true")

    recommend_indexes = sub.add_parser("recommend-indexes")
    recommend_indexes.add_argument("--table")
    recommend_indexes.add_argument("--limit", type=int, default=12)

    create_index = sub.add_parser("create-index")
    create_index.add_argument("--table", required=True)
    create_index.add_argument("--field", required=True)
    create_index.add_argument("--index", default="")
    create_index.add_argument("--yes", action="store_true")

    dashboard_op = sub.add_parser("dashboard-op")
    dashboard_op.add_argument("--op", required=True, choices=["create", "copy", "rename", "delete"])
    dashboard_op.add_argument("--dashboard")
    dashboard_op.add_argument("--source")
    dashboard_op.add_argument("--name")
    dashboard_op.add_argument("--table")
    dashboard_op.add_argument("--yes", action="store_true")

    field_update = sub.add_parser("field-update")
    field_update.add_argument("--table", required=True)
    field_update.add_argument("--field", required=True)
    field_update.add_argument("--role", required=True, choices=["identity_key", "event_time", "dimension", "measure", "status"])
    field_update.add_argument("--usage", required=True, choices=["joinable", "filterable", "groupable", "aggregatable"])
    field_update.add_argument("--confidence", type=float, default=0.9)
    field_update.add_argument("--yes", action="store_true")

    relationship = sub.add_parser("relationship-preview")
    relationship.add_argument("--workspace", default="")
    relationship.add_argument("--left-table", required=True)
    relationship.add_argument("--right-table", required=True)
    relationship.add_argument("--left-field", default="")
    relationship.add_argument("--right-field", default="")
    relationship.add_argument("--map", action="append", default=[])
    relationship.add_argument("--map-json", action="append", default=[])
    relationship.add_argument("--filter", action="append", default=[])
    relationship.add_argument("--filter-json", action="append", default=[])
    relationship.add_argument("--preaggregate-json", default="")
    relationship.add_argument("--join-type", default="left", choices=["left", "inner"])
    relationship.add_argument("--limit", type=int, default=20)

    relationship_save = sub.add_parser("relationship-save")
    relationship_save.add_argument("--workspace", default="")
    relationship_save.add_argument("--left-table", required=True)
    relationship_save.add_argument("--right-table", required=True)
    relationship_save.add_argument("--left-field", default="")
    relationship_save.add_argument("--right-field", default="")
    relationship_save.add_argument("--map", action="append", default=[])
    relationship_save.add_argument("--map-json", action="append", default=[])
    relationship_save.add_argument("--filter", action="append", default=[])
    relationship_save.add_argument("--filter-json", action="append", default=[])
    relationship_save.add_argument("--preaggregate-json", default="")
    relationship_save.add_argument("--join-type", default="left", choices=["left", "inner"])
    relationship_save.add_argument("--limit", type=int, default=20)
    relationship_save.add_argument("--yes", action="store_true")

    recommend_relationships = sub.add_parser("recommend-relationships")
    recommend_relationships.add_argument("--limit", type=int, default=12)

    list_relationships = sub.add_parser("list-relationships")

    remove_relationship = sub.add_parser("remove-relationship")
    remove_relationship.add_argument("--relationship", required=True)
    remove_relationship.add_argument("--yes", action="store_true")

    query_relationship = sub.add_parser("query-relationship")
    query_relationship.add_argument("--relationship", default="")
    query_relationship.add_argument("--left-table")
    query_relationship.add_argument("--right-table")
    query_relationship.add_argument("--left-field")
    query_relationship.add_argument("--right-field")
    query_relationship.add_argument("--map", action="append", default=[])
    query_relationship.add_argument("--map-json", action="append", default=[])
    query_relationship.add_argument("--join-type", default="left", choices=["left", "inner"])
    query_relationship.add_argument("--group", action="append", default=[])
    query_relationship.add_argument("--measure", default="")
    query_relationship.add_argument("--agg", default="count", choices=sorted(SAFE_AGGREGATIONS))
    query_relationship.add_argument("--filter", action="append", default=[])
    query_relationship.add_argument("--filter-json", action="append", default=[])
    query_relationship.add_argument("--preaggregate-json", default="")
    query_relationship.add_argument("--limit", type=int, default=50)
    query_relationship.add_argument("--sort-by", default="metric", choices=["metric", "dimension"])
    query_relationship.add_argument("--sort-direction", default="desc", choices=["asc", "desc"])

    semantic_query = sub.add_parser("semantic-query")
    semantic_query.add_argument("prompt", nargs="+")
    semantic_query.add_argument("--table", default="")
    semantic_query.add_argument("--limit", type=int, default=50)

    formula = sub.add_parser("formula-preview")
    formula.add_argument("expression")
    formula.add_argument("--table")
    formula.add_argument("--mode", default="aggregate", choices=["row", "aggregate"])

    ask = sub.add_parser("ask")
    ask.add_argument("--read-only", action="store_true")
    ask.add_argument("--parent-run", default="")
    ask.add_argument("--branch-label", default="")
    ask.add_argument("--workspace", default="")
    ask.add_argument("prompt", nargs="+")

    confirm = sub.add_parser("confirm-action")
    confirm.add_argument("action_key")
    confirm.add_argument("--reject", action="store_true")
    confirm.add_argument("--yes", action="store_true")
    confirm.add_argument("--workspace", default="")

    drafts = sub.add_parser("action-drafts")
    drafts.add_argument("--limit", type=int, default=12)
    drafts.add_argument("--all", action="store_true")
    return parser
