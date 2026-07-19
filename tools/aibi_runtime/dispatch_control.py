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
    'status',
    'workflow-plan',
    'workspace-manifest',
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
    else:
        raise ValueError(f'Command is not registered in control: {args.command}')
    return result
