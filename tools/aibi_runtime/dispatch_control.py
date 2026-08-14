from __future__ import annotations

from .use_cases import control as runtime


COMMANDS = frozenset({
    'agent-context-compact',
    'agent-provider-evaluation-record',
    'agent-provider-evaluations',
    'agent-runtime-profile-set',
    'agent-runtime-profiles',
    'agent-session-create',
    'agent-session-fork',
    'agent-session-resume',
    'agent-sessions',
    'agent-turn-cancel',
    'agent-turn-run',
    'agent-turns',
    'agent-workflow-graph',
    'business-expression-cases',
    'business-field-profiles',
    'capability-contracts',
    'cli-contract',
    'context-budget',
    'context-pack',
    'context-rule',
    'context-term',
    'knowledge-source-adapters',
    'knowledge-sources',
    'list-commands',
    'plan-quality-evaluate',
    'plan-quality-scorecards',
    'quality-doctor',
    'restricted-workflow-operators',
    'restricted-workflow-validate',
    'runtime-catalog',
    'semantic-patch-proposals',
    'semantic-patch-propose',
    'semantic-patch-review',
    'semantic-release-preview',
    'semantic-release-publish',
    'semantic-release-rollback',
    'semantic-releases',
    'status',
    'workflow-plan',
    'workflow-recipe-plan',
    'workflow-recipe-preview',
    'workflow-recipe-publish',
    'workflow-recipes',
    'workspace-manifest',
    'workspace-recovery-create',
    'workspace-recovery-compare',
    'workspace-recovery-delete',
    'workspace-recovery-inspect',
    'workspace-recovery-list',
    'workspace-recovery-reconcile',
    'workspace-recovery-restore',
})


def dispatch(args, parser):
    if args.command == 'cli-contract':
        result = runtime.cli_contract_command(args, parser)
    elif args.command == 'list-commands':
        result = runtime.list_commands_command(args, parser)
    elif args.command == 'capability-contracts':
        result = runtime.capability_contracts_command(args, parser)
    elif args.command == 'workflow-plan':
        result = runtime.workflow_plan_command(args, parser)
    elif args.command == 'workflow-recipe-preview':
        result = runtime.workflow_recipe_preview_command(args, parser=parser, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'workflow-recipe-publish':
        result = runtime.workflow_recipe_publish_command(args, parser=parser, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'workflow-recipes':
        result = runtime.workflow_recipes_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'workflow-recipe-plan':
        result = runtime.workflow_recipe_plan_command(args, parser=parser, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'context-budget':
        result = runtime.context_budget_command(args)
    elif args.command == 'restricted-workflow-operators':
        result = runtime.restricted_workflow_operators_command(args)
    elif args.command == 'restricted-workflow-validate':
        result = runtime.restricted_workflow_validate_command(args)
    elif args.command == 'agent-workflow-graph':
        result = runtime.agent_workflow_graph_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'agent-turn-run':
        result = runtime.run_agent_turn_command(args, ask_runner=runtime.ask_command, answer_enricher=lambda answer: runtime.attach_analysis_unit(answer, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso), open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'agent-turns':
        result = runtime.agent_turns_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'agent-turn-cancel':
        result = runtime.cancel_agent_turn_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'agent-session-create':
        result = runtime.agent_session_create_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'agent-sessions':
        result = runtime.agent_sessions_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'agent-session-resume':
        result = runtime.agent_session_resume_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'agent-session-fork':
        result = runtime.agent_session_fork_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'agent-context-compact':
        result = runtime.agent_context_compact_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'agent-runtime-profiles':
        result = runtime.agent_runtime_profiles_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'agent-runtime-profile-set':
        result = runtime.agent_runtime_profile_set_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'agent-provider-evaluations':
        result = runtime.agent_provider_evaluations_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'agent-provider-evaluation-record':
        result = runtime.agent_provider_evaluation_record_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'business-expression-cases':
        result = runtime.business_expression_cases_command(args)
    elif args.command == 'plan-quality-evaluate':
        result = runtime.plan_quality_evaluate_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'plan-quality-scorecards':
        result = runtime.plan_quality_scorecards_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'status':
        result = runtime.status_command(args)
    elif args.command == 'workspace-manifest':
        result = runtime.workspace_manifest_command(args, command_capabilities=runtime.capability_registry(parser), open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command in {
        'workspace-recovery-list',
        'workspace-recovery-compare',
        'workspace-recovery-reconcile',
        'workspace-recovery-inspect',
        'workspace-recovery-create',
        'workspace-recovery-restore',
        'workspace-recovery-delete',
    }:
        recovery_dependencies = {
            'open_db': runtime.open_db,
            'active_workspace_id': runtime.active_workspace_id,
            'sqlite_path': runtime.DB_PATH,
            'duckdb_path': runtime.DUCKDB_PATH,
            'recovery_root': runtime.WORKSPACE_RECOVERY_ROOT,
        }
        recovery_command = {
            'workspace-recovery-list': runtime.workspace_recovery_list_command,
            'workspace-recovery-compare': runtime.workspace_recovery_compare_command,
            'workspace-recovery-reconcile': runtime.workspace_recovery_reconcile_command,
            'workspace-recovery-inspect': runtime.workspace_recovery_inspect_command,
            'workspace-recovery-create': runtime.workspace_recovery_create_command,
            'workspace-recovery-restore': runtime.workspace_recovery_restore_command,
            'workspace-recovery-delete': runtime.workspace_recovery_delete_command,
        }[args.command]
        result = recovery_command(args, **recovery_dependencies)
    elif args.command == 'runtime-catalog':
        result = runtime.runtime_catalog_command(args, command_capabilities=runtime.capability_registry(parser), open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'business-field-profiles':
        result = runtime.business_field_profiles_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'quality-doctor':
        result = runtime.quality_doctor_command(args)
    elif args.command == 'context-pack':
        result = runtime.context_pack_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'context-term':
        result = runtime.context_term_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'context-rule':
        result = runtime.context_rule_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'knowledge-source-adapters':
        result = runtime.knowledge_source_adapters_command(args)
    elif args.command == 'knowledge-sources':
        result = runtime.knowledge_sources_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'semantic-patch-propose':
        result = runtime.semantic_patch_propose_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'semantic-patch-proposals':
        result = runtime.semantic_patch_proposals_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'semantic-patch-review':
        result = runtime.semantic_patch_review_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'semantic-release-preview':
        result = runtime.semantic_release_preview_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'semantic-release-publish':
        result = runtime.semantic_release_publish_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'semantic-releases':
        result = runtime.semantic_releases_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'semantic-release-rollback':
        result = runtime.semantic_release_rollback_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    else:
        raise ValueError(f'Command is not registered in control: {args.command}')
    return result
