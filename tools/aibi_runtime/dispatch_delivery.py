from __future__ import annotations

from . import kernel as runtime


COMMANDS = frozenset({
    'action-drafts',
    'add-filter',
    'ask',
    'clear-filters',
    'confirm-action',
    'copy-view',
    'create-index',
    'dashboard-op',
    'dashboards',
    'delete-formula',
    'delete-view',
    'field-update',
    'formula-preview',
    'list-filters',
    'list-formulas',
    'list-relationships',
    'list-views',
    'query',
    'query-relationship',
    'query-table',
    'recommend-indexes',
    'recommend-relationships',
    'relationship-preview',
    'relationship-save',
    'remove-filter',
    'remove-relationship',
    'remove-stale-filters',
    'save-formula',
    'save-view',
    'semantic-query',
    'set-filter',
})


def dispatch(args, parser):
    if args.command == 'query':
        result = runtime.query_command(args)
    elif args.command == 'query-table':
        result = runtime.query_table_command(args)
    elif args.command == 'list-views':
        result = runtime.list_views_command(args)
    elif args.command == 'save-view':
        result = runtime.save_view_command(args)
    elif args.command == 'copy-view':
        result = runtime.copy_view_command(args)
    elif args.command == 'delete-view':
        result = runtime.delete_view_command(args)
    elif args.command == 'dashboards':
        result = runtime.dashboards_command(args)
    elif args.command == 'list-filters':
        result = runtime.list_filters_command(args)
    elif args.command in {'add-filter', 'set-filter'}:
        result = runtime.add_or_set_filter_command(args)
    elif args.command == 'remove-filter':
        result = runtime.remove_filter_command(args)
    elif args.command == 'remove-stale-filters':
        result = runtime.remove_stale_filters_command(args)
    elif args.command == 'clear-filters':
        result = runtime.clear_filters_command(args)
    elif args.command == 'recommend-indexes':
        result = runtime.recommend_indexes_command(args)
    elif args.command == 'create-index':
        result = runtime.create_index_command(args)
    elif args.command == 'dashboard-op':
        result = runtime.dashboard_operation_command(args)
    elif args.command == 'field-update':
        result = runtime.update_field_command(args)
    elif args.command == 'relationship-preview':
        result = runtime.relationship_preview_command(args)
    elif args.command == 'relationship-save':
        result = runtime.relationship_save_command(args)
    elif args.command == 'recommend-relationships':
        result = runtime.recommend_relationships_command(args)
    elif args.command == 'list-relationships':
        result = runtime.list_relationships_command(args)
    elif args.command == 'remove-relationship':
        result = runtime.remove_relationship_command(args)
    elif args.command == 'query-relationship':
        result = runtime.query_relationship_command(args)
    elif args.command == 'semantic-query':
        args.prompt = ' '.join(args.prompt)
        with runtime.closing(runtime.open_db()) as connection:
            if connection.in_transaction:
                connection.commit()
            connection.execute('BEGIN IMMEDIATE')
            workspace_id = runtime.active_workspace_id(connection)
            result = runtime.execute_workspace_semantic_query(connection, workspace_id, str(args.prompt), selected_table_key=str(getattr(args, 'table', '') or ''), limit=int(getattr(args, 'limit', 50) or 50), table_columns=runtime.table_columns, quote_identifier=runtime.quote_relationship_identifier, build_relationship_query=runtime.build_relationship_query)
            result['workspaceId'] = workspace_id
            execution_plan = result.get('executionPlan') if isinstance(result.get('executionPlan'), dict) else {}
            query = result.get('query') if isinstance(result.get('query'), dict) else {}
            relationship_query = result.get('relationshipQuery') if isinstance(result.get('relationshipQuery'), dict) else {}
            result_rows = runtime.relationship_rows_for_chart_service(relationship_query) if result.get('executed') else []
            receipt = runtime.create_query_plan_receipt(connection, workspace_id=workspace_id, request_text=str(args.prompt), source_table_key=str(execution_plan.get('rootTable') or getattr(args, 'table', '') or '') or None, source_table_keys=list(execution_plan.get('pathTables') or query.get('tables') or []), relationship_path_proof=result.get('relationshipPathProof'), status='executed' if result.get('executed') else 'blocked', group=str(query.get('group') or '') or None, groups=list(query.get('groupRefs') or []), measure=str(query.get('measure') or '') or None, aggregation=str(query.get('aggregation') or '') or None, filters=list(query.get('filters') or []), joins=list(query.get('joins') or []), semantic_plan=result.get('semanticPlan'), execution_plan=execution_plan, runtime=query.get('runtime') if isinstance(query.get('runtime'), dict) else None, evidence_refs=[{'type': 'relationshipPathProof', 'fingerprint': result.get('relationshipPathProof', {}).get('fingerprint')}] if isinstance(result.get('relationshipPathProof'), dict) else [], unresolved=list(execution_plan.get('blockers') or []), result_rows=result_rows, now_iso=runtime.now_iso)
            connection.commit()
        result['queryPlanReceipt'] = receipt
        result['rows'] = result_rows
    elif args.command == 'formula-preview':
        result = runtime.formula_preview_command(args)
    elif args.command == 'list-formulas':
        result = runtime.list_formulas_command(args)
    elif args.command == 'save-formula':
        result = runtime.save_formula_command(args)
    elif args.command == 'delete-formula':
        result = runtime.delete_formula_command(args)
    elif args.command == 'ask':
        args.prompt = ' '.join(args.prompt)
        result = runtime.attach_analysis_unit(runtime.ask_command(args), open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'confirm-action':
        result = runtime.confirm_action_command(args)
        if not result.get('workspaceId'):
            with runtime.open_db() as connection:
                result['workspaceId'] = str(getattr(args, 'workspace', '') or runtime.active_workspace_id(connection))
    elif args.command == 'action-drafts':
        result = runtime.action_drafts_command(args)
    else:
        raise ValueError(f'Command is not registered in delivery: {args.command}')
    return result
