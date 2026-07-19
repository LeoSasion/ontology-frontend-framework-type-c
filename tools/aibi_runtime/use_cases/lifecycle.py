"""CLI lifecycle dependencies shared after command dispatch."""

from analysis_unit_service import attach_analysis_unit
from bi_cli_core import dump, now_iso
from bi_cli_envelope import enrich_cli_output, error_output
from bi_cli_schema import active_workspace_id, open_db
