"""Analysis application use cases."""

from analysis_export_service import export_analysis_command
from analysis_run_service import analysis_runs_command
from analysis_snapshot_service import (
    analysis_snapshot_create_command,
    analysis_snapshot_delete_command,
    analysis_snapshot_refresh_command,
    analysis_snapshot_replace_command,
    analysis_snapshots_command,
)
from analysis_unit_service import analysis_unit_build_command, analysis_unit_verify_command, analysis_units_command, chart_adapt_command
from bi_cli_core import ROOT, now_iso
from bi_cli_schema import active_workspace_id, open_db
from bi_cli_source_commands import source_intelligence_command
from confirmed_query_service import (
    confirm_query_command,
    confirmed_plans_command,
    confirmed_queries_command,
    recall_receipts_command,
)
from evidence_export_service import export_evidence_command
from reviewed_evidence_commands import (
    evidence_retrieval_evaluate_command,
    evidence_retrieval_receipts_command,
    evidence_retrieval_status_command,
    reviewed_publication_deprecate_command,
    reviewed_publication_export_command,
    reviewed_publication_plan_command,
    reviewed_publication_publish_command,
    reviewed_publications_command,
)
from decision_framework_service import (
    decision_framework_create_command,
    decision_framework_export_command,
    decision_framework_publish_command,
    decision_framework_save_command,
    decision_frameworks_command,
)
from exploration_thread_service import (
    exploration_anchor_add_command,
    exploration_board_set_command,
    exploration_thread_create_command,
    exploration_threads_command,
)
from forecast_readiness_service import forecast_readiness_command
from job_command_service import job_cancel_command, job_recover_command, jobs_command
from limited_research_run_service import (
    research_run_create_command,
    research_run_finalize_command,
    research_run_observe_command,
    research_run_revise_command,
    research_runs_command,
)
from metric_monitor_service import (
    metric_monitor_create_command,
    metric_monitor_delete_command,
    metric_monitor_replace_command,
    metric_monitor_run_command,
    metric_monitors_command,
)
from query_plan_receipt_service import query_receipts_command
from source_intelligence_job_service import (
    job_process_exit_command,
    source_intelligence_job_create_command,
    source_intelligence_job_run_command,
)
