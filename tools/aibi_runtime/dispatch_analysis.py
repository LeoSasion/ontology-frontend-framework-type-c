from __future__ import annotations

from .use_cases import analysis as runtime


COMMANDS = frozenset({
    'analysis-runs',
    'analysis-snapshot-create',
    'analysis-snapshot-delete',
    'analysis-snapshot-refresh',
    'analysis-snapshot-replace',
    'analysis-snapshots',
    'analysis-unit-build',
    'analysis-unit-verify',
    'analysis-units',
    'chart-adapt',
    'confirm-query',
    'confirmed-plans',
    'confirmed-queries',
    'exploration-anchor-add',
    'exploration-board-set',
    'exploration-thread-create',
    'exploration-threads',
    'export-analysis',
    'export-evidence',
    'forecast-readiness',
    'job-cancel',
    'job-process-exit',
    'job-recover',
    'jobs',
    'metric-monitor-create',
    'metric-monitor-delete',
    'metric-monitor-replace',
    'metric-monitor-run',
    'metric-monitors',
    'query-receipts',
    'recall-receipts',
    'research-run-create',
    'research-run-finalize',
    'research-run-observe',
    'research-run-revise',
    'research-runs',
    'source-intelligence-job-create',
    'source-intelligence-job-run',
})


def dispatch(args, parser):
    if args.command == 'query-receipts':
        result = runtime.query_receipts_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'export-evidence':
        result = runtime.export_evidence_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, root=runtime.ROOT, now_iso=runtime.now_iso)
    elif args.command == 'export-analysis':
        result = runtime.export_analysis_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, root=runtime.ROOT)
    elif args.command == 'confirmed-queries':
        result = runtime.confirmed_queries_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'confirmed-plans':
        result = runtime.confirmed_plans_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'recall-receipts':
        result = runtime.recall_receipts_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'confirm-query':
        result = runtime.confirm_query_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'analysis-runs':
        result = runtime.analysis_runs_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'exploration-threads':
        result = runtime.exploration_threads_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'exploration-thread-create':
        result = runtime.exploration_thread_create_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'exploration-anchor-add':
        result = runtime.exploration_anchor_add_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'exploration-board-set':
        result = runtime.exploration_board_set_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'research-runs':
        result = runtime.research_runs_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'research-run-create':
        result = runtime.research_run_create_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'research-run-revise':
        result = runtime.research_run_revise_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'research-run-observe':
        result = runtime.research_run_observe_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'research-run-finalize':
        result = runtime.research_run_finalize_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'analysis-unit-build':
        result = runtime.analysis_unit_build_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'analysis-units':
        result = runtime.analysis_units_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'analysis-snapshots':
        result = runtime.analysis_snapshots_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'analysis-snapshot-create':
        result = runtime.analysis_snapshot_create_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'analysis-snapshot-refresh':
        result = runtime.analysis_snapshot_refresh_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'analysis-snapshot-replace':
        result = runtime.analysis_snapshot_replace_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'analysis-snapshot-delete':
        result = runtime.analysis_snapshot_delete_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'metric-monitors':
        result = runtime.metric_monitors_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'metric-monitor-create':
        result = runtime.metric_monitor_create_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'metric-monitor-replace':
        result = runtime.metric_monitor_replace_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'metric-monitor-delete':
        result = runtime.metric_monitor_delete_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'metric-monitor-run':
        result = runtime.metric_monitor_run_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'analysis-unit-verify':
        result = runtime.analysis_unit_verify_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'forecast-readiness':
        result = runtime.forecast_readiness_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'chart-adapt':
        result = runtime.chart_adapt_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'jobs':
        result = runtime.jobs_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id)
    elif args.command == 'job-cancel':
        result = runtime.job_cancel_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'job-recover':
        result = runtime.job_recover_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'source-intelligence-job-create':
        result = runtime.source_intelligence_job_create_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'source-intelligence-job-run':
        result = runtime.source_intelligence_job_run_command(args, source_intelligence_command=runtime.source_intelligence_command, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    elif args.command == 'job-process-exit':
        result = runtime.job_process_exit_command(args, open_db=runtime.open_db, active_workspace_id=runtime.active_workspace_id, now_iso=runtime.now_iso)
    else:
        raise ValueError(f'Command is not registered in analysis: {args.command}')
    return result
