from __future__ import annotations

import json
import sqlite3
from functools import lru_cache
from typing import Any, Iterable

from bi_cli_core import DB_PATH, DUCKDB_PATH, now_iso, quote_identifier, slug
from preferences_theme_command_service import (
    delete_theme_palette as delete_theme_palette_service,
    ensure_default_preferences_and_themes as ensure_default_preferences_and_themes_service,
    list_theme_palettes as list_theme_palettes_service,
    load_user_preferences as load_user_preferences_service,
    normalize_theme_palette as normalize_theme_palette_service,
    normalize_theme_tokens as normalize_theme_tokens_service,
    normalize_user_preferences as normalize_user_preferences_service,
    save_user_preferences as save_user_preferences_service,
    upsert_theme_palette as upsert_theme_palette_service,
    validate_theme_palette_payload as validate_theme_palette_payload_service,
)
from workspace_command_service import (
    active_workspace_id as active_workspace_id_service,
    get_system_flag as get_system_flag_service,
    set_system_flag as set_system_flag_service,
    workspace_records as workspace_records_service,
)
from decision_framework_service import ensure_decision_framework_schema
from evidence_retrieval_service import ensure_evidence_retrieval_schema
from reviewed_publication_service import ensure_reviewed_publication_schema
from sqlserver_snapshot_commands import SQLSERVER_SNAPSHOT_METADATA_DDL


CURRENT_SQLITE_SCHEMA_VERSION = 18
CURRENT_DUCKDB_SCHEMA_VERSION = 2

# The control database is a versioned v18 artifact.  It is initialized once
# from an empty file and then opened read-only with respect to schema state;
# feature tables are intentionally listed here so a partially-created v18
# file fails closed instead of being repaired implicitly on a hot path.
REQUIRED_CONTROL_TABLES = frozenset(
    {
        "workspaces",
        "system_flags",
        "table_registry",
        "dataset_versions",
        "dataset_version_files",
        "navigation_modules",
        "source_runs",
        "field_semantics",
        "metric_definitions",
        "calculated_fields",
        "relationships",
        "dashboards",
        "dashboard_widgets",
        "saved_views",
        "import_jobs",
        "import_policies",
        "data_connectors",
        "user_preferences",
        "theme_palettes",
        "action_drafts",
        "source_intelligence_runs",
        "source_run_tables",
        "workspace_domain_packs",
        "analytical_skills",
        "workspace_analytical_skills",
        "context_terms",
        "context_rules",
        "knowledge_sources",
        "semantic_patch_proposals",
        "semantic_releases",
        "semantic_release_events",
        "metric_contract_versions",
        "metric_contract_events",
        "workflow_recipes",
        "workflow_recipe_events",
        "query_plan_receipts",
        "confirmed_queries",
        "confirmed_plan_memories",
        "recall_receipts",
        "analysis_runs",
        "analysis_units",
        "analysis_snapshots",
        "metric_monitors",
        "metric_monitor_evaluations",
        "analysis_jobs",
        "analysis_job_events",
        "agent_sessions",
        "agent_turns",
        "agent_turn_events",
        "agent_context_snapshots",
        "workspace_agent_runtime_profiles",
        "agent_provider_evaluations",
        "plan_quality_scorecards",
        "exploration_threads",
        "exploration_anchors",
        "exploration_board_items",
        "research_runs",
        "research_plan_revisions",
        "research_observations",
        "research_run_events",
        "source_activation_journals",
        "import_workspace_leases",
        "source_activation_journal_events",
        "reviewed_publications",
        "evidence_ledger_entries",
        "evidence_retrieval_receipts",
        "retrieval_evaluation_runs",
        "decision_frameworks",
        "sqlserver_snapshot_catalogs",
        "sqlserver_snapshot_plans",
        "sqlserver_snapshot_receipts",
    }
)

def sqlite_schema_version(connection: sqlite3.Connection) -> int:
    row = connection.execute("PRAGMA user_version").fetchone()
    return int(row[0] if row is not None else 0)


def assert_sqlite_schema_compatible(connection: sqlite3.Connection) -> int:
    version = sqlite_schema_version(connection)
    if version != CURRENT_SQLITE_SCHEMA_VERSION:
        qualifier = "newer than" if version > CURRENT_SQLITE_SCHEMA_VERSION else "not the current"
        raise RuntimeError(
            f"AIBI-C metadata schema v{version} is {qualifier} clean "
            f"v{CURRENT_SQLITE_SCHEMA_VERSION}; no migration or repair is performed. "
            "Initialize a fresh v18 control database instead."
        )
    return version


def _control_database_state(connection: sqlite3.Connection) -> tuple[int, bool]:
    """Return the user_version and whether the file contains user tables."""
    version = sqlite_schema_version(connection)
    has_user_tables = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' LIMIT 1"
    ).fetchone() is not None
    return version, has_user_tables


def duckdb_schema_version(path=DUCKDB_PATH) -> int | None:
    if not path.exists():
        return None
    try:
        import duckdb  # type: ignore
    except ImportError as error:
        raise RuntimeError("DuckDB runtime is unavailable; local schema compatibility cannot be checked.") from error
    with duckdb.connect(str(path), read_only=True) as duck_connection:
        exists = duck_connection.execute(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '__aibi_schema_metadata'"
        ).fetchone()[0]
        if not exists:
            return 0
        row = duck_connection.execute(
            'SELECT value FROM "__aibi_schema_metadata" WHERE key = ?', ["schema_version"]
        ).fetchone()
        return int(row[0]) if row else 0


def assert_duckdb_schema_compatible(path=DUCKDB_PATH) -> int | None:
    version = duckdb_schema_version(path)
    if version is not None and version != CURRENT_DUCKDB_SCHEMA_VERSION:
        raise RuntimeError(
            f"AIBI-C analytics storage v{version} is incompatible with the clean "
            f"v{CURRENT_DUCKDB_SCHEMA_VERSION} data plane; no changes were made. "
            "Start with the v2 storage paths instead of migrating business rows."
        )
    return version


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]

def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _control_columns_by_table(connection: sqlite3.Connection) -> dict[str, frozenset[str]]:
    """Read every control-table column in one SQLite catalogue query."""

    columns: dict[str, set[str]] = {}
    for row in connection.execute(
        """
        SELECT schema_table.name AS table_name, table_column.name AS column_name
        FROM sqlite_master AS schema_table
        JOIN pragma_table_info(schema_table.name) AS table_column
        WHERE schema_table.type = 'table'
          AND schema_table.name NOT LIKE 'sqlite_%'
        ORDER BY schema_table.name, table_column.cid
        """
    ):
        table_name = str(row["table_name"] if isinstance(row, sqlite3.Row) else row[0])
        column_name = str(row["column_name"] if isinstance(row, sqlite3.Row) else row[1])
        columns.setdefault(table_name, set()).add(column_name)
    return {table_name: frozenset(names) for table_name, names in columns.items()}


@lru_cache(maxsize=1)
def _canonical_control_columns() -> tuple[tuple[str, frozenset[str]], ...]:
    """Derive the v18 contract once from the same initializer used for clean files."""

    canonical = sqlite3.connect(":memory:")
    try:
        _initialize_schema(canonical)
        columns = _control_columns_by_table(canonical)
    finally:
        canonical.close()
    missing_tables = sorted(REQUIRED_CONTROL_TABLES - columns.keys())
    if missing_tables:
        raise RuntimeError(
            "AIBI-C canonical v18 initializer is incomplete; missing tables: "
            + ", ".join(missing_tables)
        )
    return tuple(
        (table_name, columns[table_name]) for table_name in sorted(REQUIRED_CONTROL_TABLES)
    )


def assert_control_schema_invariants(connection: sqlite3.Connection) -> int:
    """Validate the current control schema without writes or external storage access."""
    version = assert_sqlite_schema_compatible(connection)
    actual_columns = _control_columns_by_table(connection)
    actual_tables = set(actual_columns)
    missing_tables = sorted(REQUIRED_CONTROL_TABLES - actual_tables)
    if missing_tables:
        raise RuntimeError(
            "AIBI-C clean v18 control schema is incomplete; missing tables: "
            + ", ".join(missing_tables)
        )
    for table_name, required_columns in _canonical_control_columns():
        missing_columns = sorted(required_columns - actual_columns[table_name])
        if missing_columns:
            raise RuntimeError(
                f"AIBI-C clean v18 control schema is incomplete; {table_name} "
                "is missing columns: "
                + ", ".join(missing_columns)
            )
    if connection.execute("SELECT 1 FROM workspaces WHERE id = 'default' LIMIT 1").fetchone() is None:
        raise RuntimeError("AIBI-C clean v18 control schema is missing the default workspace seed.")
    if connection.execute("SELECT 1 FROM system_flags WHERE key = 'active_workspace_id' LIMIT 1").fetchone() is None:
        raise RuntimeError("AIBI-C clean v18 control schema is missing the active workspace seed.")
    return version


def table_columns(connection: sqlite3.Connection, physical_table: str) -> list[str]:
    row = connection.execute(
        """
        SELECT schema_json
        FROM table_registry
        WHERE physical_table = ? AND active_version_id <> ''
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (physical_table,),
    ).fetchone()
    if row is None:
        raise ValueError(f"Dataset schema is unavailable for active relation: {physical_table}")
    try:
        schema = json.loads(str(row["schema_json"] or "[]"))
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError(f"Dataset schema metadata is invalid: {physical_table}") from error
    columns: list[str] = []
    for item in schema if isinstance(schema, list) else []:
        if isinstance(item, str):
            name = item
            internal = name.startswith("__aibi_")
        elif isinstance(item, dict):
            name = str(item.get("name") or item.get("field") or "")
            internal = bool(item.get("internal")) or name.startswith("__aibi_")
        else:
            continue
        if name and not internal and name not in columns:
            columns.append(name)
    if not columns:
        raise ValueError(f"Dataset schema has no public columns: {physical_table}")
    return columns


def physical_table_for_workspace(workspace_id: str, table_key: str) -> str:
    if workspace_id == "default":
        return f"data_{table_key}"
    return f"data_{slug(workspace_id)[:28]}_{slug(table_key)[:48]}"[:96]


def registry_for_table(
    connection: sqlite3.Connection,
    table_key: str,
    workspace_id: str | None = None,
) -> sqlite3.Row | None:
    resolved_workspace_id = str(workspace_id or active_workspace_id(connection))
    return connection.execute(
        "SELECT * FROM table_registry WHERE table_key = ? AND workspace_id = ?",
        (table_key, resolved_workspace_id),
    ).fetchone()


def all_available_fields(connection: sqlite3.Connection, table_key: str | None = None) -> set[str]:
    fields: set[str] = set()
    workspace_id = active_workspace_id(connection)
    params: tuple[Any, ...] = (table_key, workspace_id) if table_key else (workspace_id,)
    where = "WHERE table_key = ? AND workspace_id = ?" if table_key else "WHERE workspace_id = ?"
    for row in connection.execute(f"SELECT physical_table FROM table_registry {where}", params):
        fields.update(table_columns(connection, row["physical_table"]))
    for row in connection.execute("SELECT label, measure FROM metric_definitions WHERE workspace_id = ?", (workspace_id,)):
        fields.add(str(row["label"]))
        if row["measure"] and row["measure"] != "*":
            fields.add(str(row["measure"]))
    if table_exists(connection, "calculated_fields"):
        calc_where = "WHERE table_key = ? AND workspace_id = ? AND enabled = 1" if table_key else "WHERE workspace_id = ? AND enabled = 1"
        for row in connection.execute(f"SELECT name FROM calculated_fields {calc_where}", params):
            fields.add(str(row["name"]))
    return fields


def open_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        version, has_user_tables = _control_database_state(connection)
        if version == 0 and not has_user_tables:
            initialize_schema(connection)
        else:
            assert_control_schema_invariants(connection)
    except Exception:
        connection.close()
        raise
    return connection


def get_system_flag(connection: sqlite3.Connection, key: str, default: str = "") -> str:
    return get_system_flag_service(connection, key, default)


def set_system_flag(connection: sqlite3.Connection, key: str, value: str) -> None:
    set_system_flag_service(connection, key, value)


def active_workspace_id(connection: sqlite3.Connection) -> str:
    return active_workspace_id_service(connection)


def workspace_records(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    return workspace_records_service(connection, rows_to_dicts=rows_to_dicts)


def _initialize_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS workspaces (
          id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          current_source_run_id TEXT,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS system_flags (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS table_registry (
          table_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          display_name TEXT NOT NULL,
          physical_table TEXT NOT NULL,
          source_file TEXT NOT NULL,
          row_count INTEGER NOT NULL,
          column_count INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          data_version INTEGER NOT NULL DEFAULT 1,
          updated_at TEXT NOT NULL DEFAULT '',
          active_version_id TEXT NOT NULL DEFAULT '',
          schema_json TEXT NOT NULL DEFAULT '[]',
          schema_fingerprint TEXT NOT NULL DEFAULT '',
          content_fingerprint TEXT NOT NULL DEFAULT '',
          PRIMARY KEY(workspace_id, table_key)
        );
        CREATE TABLE IF NOT EXISTS dataset_versions (
          version_id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL,
          table_key TEXT NOT NULL,
          row_count INTEGER NOT NULL,
          column_count INTEGER NOT NULL,
          schema_json TEXT NOT NULL,
          schema_fingerprint TEXT NOT NULL,
          content_fingerprint TEXT NOT NULL,
          source_file TEXT NOT NULL,
          created_at TEXT NOT NULL,
          UNIQUE(workspace_id, table_key, content_fingerprint)
        );
        CREATE INDEX IF NOT EXISTS idx_dataset_versions_workspace_table_created
          ON dataset_versions(workspace_id, table_key, created_at);
        CREATE TABLE IF NOT EXISTS dataset_version_files (
          version_id TEXT NOT NULL,
          ordinal INTEGER NOT NULL,
          object_key TEXT NOT NULL,
          object_hash TEXT NOT NULL,
          row_count INTEGER NOT NULL,
          byte_size INTEGER NOT NULL,
          PRIMARY KEY(version_id, ordinal),
          FOREIGN KEY(version_id) REFERENCES dataset_versions(version_id) ON DELETE RESTRICT
        );
        CREATE TABLE IF NOT EXISTS navigation_modules (
          module_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          name TEXT NOT NULL,
          module_type TEXT NOT NULL,
          table_key TEXT,
          dashboard_key TEXT,
          sort_order INTEGER NOT NULL,
          created_by TEXT NOT NULL,
          agent_managed INTEGER NOT NULL,
          enabled INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, module_key)
        );
        CREATE TABLE IF NOT EXISTS source_runs (
          id TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL,
          table_key TEXT NOT NULL,
          name TEXT NOT NULL,
          status TEXT NOT NULL,
          source_file TEXT NOT NULL,
          row_count INTEGER NOT NULL,
          column_count INTEGER NOT NULL,
          profile_json TEXT NOT NULL,
          evidence_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS field_semantics (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          table_key TEXT NOT NULL,
          field_name TEXT NOT NULL,
          role TEXT NOT NULL,
          usage TEXT NOT NULL,
          confidence REAL NOT NULL,
          tags_json TEXT NOT NULL DEFAULT '[]',
          usage_json TEXT NOT NULL DEFAULT '{}',
          source TEXT NOT NULL DEFAULT 'auto',
          note TEXT NOT NULL DEFAULT '',
          updated_at TEXT NOT NULL DEFAULT '',
          UNIQUE(workspace_id, table_key, field_name)
        );
        CREATE TABLE IF NOT EXISTS metric_definitions (
          metric_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          label TEXT NOT NULL,
          table_key TEXT NOT NULL,
          measure TEXT NOT NULL,
          aggregation TEXT NOT NULL,
          dimension TEXT,
          time_field TEXT,
          value_format TEXT NOT NULL,
          created_at TEXT NOT NULL,
          filters_json TEXT NOT NULL DEFAULT '[]',
          description TEXT NOT NULL DEFAULT '',
          source TEXT NOT NULL DEFAULT 'auto',
          enabled INTEGER NOT NULL DEFAULT 1,
          updated_at TEXT NOT NULL DEFAULT '',
          formula_text TEXT NOT NULL DEFAULT '',
          formula_ast_json TEXT NOT NULL DEFAULT '{}',
          dependencies_json TEXT NOT NULL DEFAULT '[]',
          metric_type TEXT NOT NULL DEFAULT 'basic',
          PRIMARY KEY(workspace_id, metric_key)
        );
        CREATE TABLE IF NOT EXISTS calculated_fields (
          field_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          table_key TEXT NOT NULL,
          name TEXT NOT NULL,
          mode TEXT NOT NULL,
          formula_text TEXT NOT NULL,
          formula_ast_json TEXT NOT NULL,
          dependencies_json TEXT NOT NULL,
          value_format TEXT NOT NULL,
          description TEXT NOT NULL,
          source TEXT NOT NULL,
          enabled INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, field_key)
        );
        CREATE TABLE IF NOT EXISTS relationships (
          relation_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          name TEXT NOT NULL,
          left_table_key TEXT NOT NULL,
          right_table_key TEXT NOT NULL,
          left_field TEXT NOT NULL,
          right_field TEXT NOT NULL,
          mappings_json TEXT NOT NULL DEFAULT '[]',
          filters_json TEXT NOT NULL DEFAULT '[]',
          preaggregation_json TEXT NOT NULL DEFAULT '{}',
          join_type TEXT NOT NULL,
          confidence REAL NOT NULL,
          validation_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL DEFAULT '',
          PRIMARY KEY(workspace_id, relation_key)
        );
        CREATE TABLE IF NOT EXISTS dashboards (
          dashboard_key TEXT NOT NULL,
          name TEXT NOT NULL,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          default_table_key TEXT,
          layout_json TEXT NOT NULL,
          created_by TEXT NOT NULL,
          agent_managed INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, dashboard_key)
        );
        CREATE TABLE IF NOT EXISTS dashboard_widgets (
          widget_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          dashboard_key TEXT NOT NULL,
          widget_type TEXT NOT NULL,
          title TEXT NOT NULL,
          table_key TEXT,
          config_json TEXT NOT NULL,
          sort_order INTEGER NOT NULL,
          PRIMARY KEY(workspace_id, widget_key)
        );
        CREATE TABLE IF NOT EXISTS saved_views (
          view_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          name TEXT NOT NULL,
          tag_name TEXT NOT NULL,
          table_key TEXT NOT NULL,
          config_json TEXT NOT NULL,
          is_default INTEGER NOT NULL,
          sort_order INTEGER NOT NULL,
          created_by TEXT NOT NULL,
          agent_managed INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, view_key)
        );
        CREATE TABLE IF NOT EXISTS import_jobs (
          job_key TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          source_file TEXT NOT NULL,
          table_key TEXT,
          mode TEXT NOT NULL,
          status TEXT NOT NULL,
          row_count INTEGER NOT NULL,
          result_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS import_policies (
          table_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          unique_fields_json TEXT NOT NULL,
          conflict_rule TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, table_key)
        );
        CREATE TABLE IF NOT EXISTS data_connectors (
          connector_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          name TEXT NOT NULL,
          connector_type TEXT NOT NULL,
          provider TEXT NOT NULL,
          status TEXT NOT NULL,
          config_json TEXT NOT NULL,
          schedule_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          last_sync_at TEXT,
          last_sync_status TEXT,
          last_sync_result_json TEXT,
          PRIMARY KEY(workspace_id, connector_key)
        );
        CREATE TABLE IF NOT EXISTS user_preferences (
          preference_key TEXT PRIMARY KEY,
          preferences_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS theme_palettes (
          theme_key TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          mode TEXT NOT NULL,
          tokens_json TEXT NOT NULL,
          enabled INTEGER NOT NULL,
          sort_order INTEGER NOT NULL,
          created_by TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS action_drafts (
          action_key TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          kind TEXT NOT NULL,
          label TEXT NOT NULL,
          status TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          evidence_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          confirmed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS source_intelligence_runs (
          run_key TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL DEFAULT 'default',
          label TEXT NOT NULL,
          status TEXT NOT NULL,
          input_roots_json TEXT NOT NULL,
          output_dir TEXT NOT NULL,
          source_count INTEGER NOT NULL,
          table_count INTEGER NOT NULL,
          field_candidate_count INTEGER NOT NULL,
          relationship_count INTEGER NOT NULL,
          metric_sql_plan_count INTEGER NOT NULL,
          metric_sql_executable_count INTEGER NOT NULL,
          manifest_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS source_run_tables (
          source_run_id TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          table_key TEXT NOT NULL,
          data_version INTEGER NOT NULL,
          row_count INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY(source_run_id, table_key)
        );
        CREATE INDEX IF NOT EXISTS idx_source_run_tables_workspace_run
          ON source_run_tables(workspace_id, source_run_id);
        CREATE TABLE IF NOT EXISTS workspace_domain_packs (
          workspace_id TEXT NOT NULL,
          pack_id TEXT NOT NULL,
          version TEXT NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 0,
          enabled_at TEXT,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, pack_id)
        );
        CREATE INDEX IF NOT EXISTS idx_workspace_domain_packs_enabled
          ON workspace_domain_packs(workspace_id, enabled, pack_id);
        CREATE TABLE IF NOT EXISTS analytical_skills (
          skill_id TEXT PRIMARY KEY,
          version TEXT NOT NULL,
          manifest_json TEXT NOT NULL,
          fingerprint TEXT NOT NULL,
          source_type TEXT NOT NULL,
          installed_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS workspace_analytical_skills (
          workspace_id TEXT NOT NULL,
          skill_id TEXT NOT NULL,
          version TEXT NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 0,
          enabled_at TEXT,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, skill_id)
        );
        CREATE INDEX IF NOT EXISTS idx_workspace_analytical_skills_enabled
          ON workspace_analytical_skills(workspace_id, enabled, skill_id);
        CREATE TABLE IF NOT EXISTS context_terms (
          term_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          canonical_name TEXT NOT NULL,
          aliases_json TEXT NOT NULL,
          definition TEXT NOT NULL,
          scope_type TEXT NOT NULL,
          scope_ref TEXT NOT NULL,
          status TEXT NOT NULL,
          source TEXT NOT NULL,
          evidence_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          confirmed_at TEXT,
          PRIMARY KEY(workspace_id, term_key)
        );
        CREATE TABLE IF NOT EXISTS context_rules (
          rule_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          title TEXT NOT NULL,
          statement TEXT NOT NULL,
          rule_type TEXT NOT NULL,
          applies_to_json TEXT NOT NULL,
          status TEXT NOT NULL,
          source TEXT NOT NULL,
          evidence_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          confirmed_at TEXT,
          PRIMARY KEY(workspace_id, rule_key)
        );
        CREATE TABLE IF NOT EXISTS knowledge_sources (
          source_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          adapter_id TEXT NOT NULL,
          source_type TEXT NOT NULL,
          name TEXT NOT NULL,
          source_version TEXT NOT NULL,
          locator_ref TEXT NOT NULL,
          content_fingerprint TEXT NOT NULL,
          snapshot_json TEXT NOT NULL,
          status TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, source_key)
        );
        CREATE INDEX IF NOT EXISTS idx_knowledge_sources_workspace_status
          ON knowledge_sources(workspace_id, status, created_at);
        CREATE TABLE IF NOT EXISTS semantic_patch_proposals (
          proposal_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          source_key TEXT NOT NULL,
          patch_type TEXT NOT NULL,
          operation TEXT NOT NULL,
          target_ref TEXT NOT NULL,
          before_json TEXT NOT NULL,
          after_json TEXT NOT NULL,
          evidence_json TEXT NOT NULL,
          source_fingerprint TEXT NOT NULL,
          workspace_schema_fingerprint TEXT NOT NULL,
          target_fingerprint TEXT NOT NULL,
          confidence REAL NOT NULL,
          status TEXT NOT NULL,
          review_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          reviewed_at TEXT,
          PRIMARY KEY(workspace_id, proposal_key)
        );
        CREATE INDEX IF NOT EXISTS idx_semantic_patch_workspace_status
          ON semantic_patch_proposals(workspace_id, status, created_at);
        CREATE INDEX IF NOT EXISTS idx_semantic_patch_workspace_source
          ON semantic_patch_proposals(workspace_id, source_key, proposal_key);
        CREATE TABLE IF NOT EXISTS semantic_releases (
          release_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          request_key TEXT NOT NULL,
          label TEXT NOT NULL,
          status TEXT NOT NULL,
          proposal_keys_json TEXT NOT NULL,
          plan_json TEXT NOT NULL,
          plan_fingerprint TEXT NOT NULL,
          previous_snapshot_json TEXT NOT NULL,
          published_snapshot_json TEXT NOT NULL,
          published_fingerprint TEXT NOT NULL,
          rollback_request_key TEXT,
          rollback_plan_fingerprint TEXT,
          created_at TEXT NOT NULL,
          published_at TEXT NOT NULL,
          rolled_back_at TEXT,
          PRIMARY KEY(workspace_id, release_key),
          UNIQUE(workspace_id, request_key)
        );
        CREATE INDEX IF NOT EXISTS idx_semantic_releases_workspace_status
          ON semantic_releases(workspace_id, status, published_at);
        CREATE TABLE IF NOT EXISTS semantic_release_events (
          event_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
          workspace_id TEXT NOT NULL,
          release_key TEXT NOT NULL,
          event_type TEXT NOT NULL,
          status TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_semantic_release_events_release
          ON semantic_release_events(workspace_id, release_key, event_sequence);
        CREATE TABLE IF NOT EXISTS metric_contract_versions (
          contract_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          metric_key TEXT NOT NULL,
          version INTEGER NOT NULL,
          request_key TEXT NOT NULL,
          label TEXT NOT NULL,
          status TEXT NOT NULL,
          definition_json TEXT NOT NULL,
          definition_fingerprint TEXT NOT NULL,
          binding_json TEXT NOT NULL,
          binding_fingerprint TEXT NOT NULL,
          scenarios_json TEXT NOT NULL,
          plan_fingerprint TEXT NOT NULL,
          published_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, contract_key),
          UNIQUE(workspace_id, metric_key, version),
          UNIQUE(workspace_id, request_key)
        );
        CREATE INDEX IF NOT EXISTS idx_metric_contract_versions_metric
          ON metric_contract_versions(workspace_id, metric_key, version DESC);
        CREATE TABLE IF NOT EXISTS metric_contract_events (
          event_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
          workspace_id TEXT NOT NULL,
          contract_key TEXT NOT NULL,
          event_type TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_metric_contract_events_contract
          ON metric_contract_events(workspace_id, contract_key, event_sequence);
        CREATE TABLE IF NOT EXISTS workflow_recipes (
          recipe_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          name TEXT NOT NULL,
          description TEXT NOT NULL,
          version INTEGER NOT NULL,
          request_key TEXT NOT NULL,
          status TEXT NOT NULL,
          stages_json TEXT NOT NULL,
          plan_fingerprint TEXT NOT NULL,
          published_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, recipe_key),
          UNIQUE(workspace_id, name, version),
          UNIQUE(workspace_id, request_key)
        );
        CREATE TABLE IF NOT EXISTS workflow_recipe_events (
          event_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
          workspace_id TEXT NOT NULL,
          recipe_key TEXT NOT NULL,
          event_type TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_workflow_recipe_events_recipe
          ON workflow_recipe_events(workspace_id, recipe_key, event_sequence);
        CREATE TABLE IF NOT EXISTS query_plan_receipts (
          receipt_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          request_text TEXT NOT NULL,
          status TEXT NOT NULL,
          source_table_key TEXT,
          schema_fingerprint TEXT NOT NULL,
          plan_json TEXT NOT NULL,
          evidence_json TEXT NOT NULL,
          action_key TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, receipt_key)
        );
        CREATE TABLE IF NOT EXISTS confirmed_queries (
          query_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          question TEXT NOT NULL,
          status TEXT NOT NULL,
          query_receipt_key TEXT NOT NULL,
          source_table_key TEXT,
          schema_fingerprint TEXT NOT NULL,
          chart_spec_json TEXT NOT NULL,
          evidence_json TEXT NOT NULL,
          originating_action_key TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          confirmed_at TEXT,
          stale_reason TEXT NOT NULL,
          PRIMARY KEY(workspace_id, query_key)
        );
        CREATE TABLE IF NOT EXISTS confirmed_plan_memories (
          memory_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          query_key TEXT NOT NULL,
          query_receipt_key TEXT NOT NULL,
          question TEXT NOT NULL,
          status TEXT NOT NULL,
          plan_json TEXT NOT NULL,
          signature_json TEXT NOT NULL,
          binding_fingerprint TEXT NOT NULL,
          evidence_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          confirmed_at TEXT,
          stale_reason TEXT NOT NULL,
          PRIMARY KEY(workspace_id, memory_key)
        );
        CREATE INDEX IF NOT EXISTS idx_confirmed_plan_workspace_status
          ON confirmed_plan_memories(workspace_id, status, updated_at);
        CREATE INDEX IF NOT EXISTS idx_confirmed_plan_workspace_query
          ON confirmed_plan_memories(workspace_id, query_key);
        CREATE TABLE IF NOT EXISTS recall_receipts (
          receipt_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          request_hash TEXT NOT NULL,
          status TEXT NOT NULL,
          policy_json TEXT NOT NULL,
          candidates_json TEXT NOT NULL,
          returned_json TEXT NOT NULL,
          planning_binding_fingerprint TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, receipt_key)
        );
        CREATE INDEX IF NOT EXISTS idx_recall_receipts_workspace_created
          ON recall_receipts(workspace_id, created_at);
        CREATE TABLE IF NOT EXISTS analysis_runs (
          run_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          parent_run_key TEXT,
          branch_label TEXT NOT NULL,
          question TEXT NOT NULL,
          status TEXT NOT NULL,
          query_receipt_key TEXT NOT NULL,
          action_key TEXT,
          result_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, run_key)
        );
        CREATE TABLE IF NOT EXISTS analysis_units (
          unit_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          query_receipt_key TEXT NOT NULL,
          kind TEXT NOT NULL,
          status TEXT NOT NULL,
          title TEXT NOT NULL,
          definition_fingerprint TEXT NOT NULL,
          result_fingerprint TEXT NOT NULL,
          grain_json TEXT NOT NULL,
          shape_json TEXT NOT NULL,
          result_rows_json TEXT NOT NULL,
          calculation_json TEXT NOT NULL,
          validation_json TEXT NOT NULL,
          chart_adapter_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, unit_key)
        );
        CREATE INDEX IF NOT EXISTS idx_analysis_units_workspace_receipt
          ON analysis_units(workspace_id, query_receipt_key, updated_at);
        CREATE INDEX IF NOT EXISTS idx_analysis_units_workspace_kind
          ON analysis_units(workspace_id, kind, status, updated_at);
        CREATE TABLE IF NOT EXISTS analysis_snapshots (
          snapshot_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          parent_snapshot_key TEXT,
          operation TEXT NOT NULL,
          status TEXT NOT NULL,
          reason TEXT NOT NULL,
          unit_key TEXT NOT NULL,
          query_receipt_key TEXT NOT NULL,
          semantic_fingerprint TEXT NOT NULL,
          binding_fingerprint TEXT NOT NULL,
          binding_json TEXT NOT NULL,
          row_limit INTEGER NOT NULL,
          row_count INTEGER NOT NULL,
          content_hash TEXT NOT NULL,
          content_json TEXT NOT NULL,
          input_fingerprint TEXT NOT NULL,
          created_at TEXT NOT NULL,
          deleted_at TEXT,
          PRIMARY KEY(workspace_id, snapshot_key)
        );
        CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_workspace_unit
          ON analysis_snapshots(workspace_id, unit_key, created_at);
        CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_workspace_parent
          ON analysis_snapshots(workspace_id, parent_snapshot_key, created_at);
        CREATE INDEX IF NOT EXISTS idx_analysis_snapshots_workspace_input
          ON analysis_snapshots(workspace_id, input_fingerprint);
        CREATE TABLE IF NOT EXISTS metric_monitors (
          monitor_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          parent_monitor_key TEXT,
          operation TEXT NOT NULL,
          status TEXT NOT NULL,
          label TEXT NOT NULL,
          metric_key TEXT NOT NULL,
          cadence TEXT NOT NULL,
          comparison_strategy TEXT NOT NULL,
          direction TEXT NOT NULL,
          threshold_value REAL,
          threshold_source TEXT NOT NULL,
          warning_ratio REAL NOT NULL,
          semantic_fingerprint TEXT NOT NULL,
          baseline_snapshot_key TEXT NOT NULL,
          latest_snapshot_key TEXT,
          latest_evaluation_key TEXT,
          latest_status TEXT NOT NULL,
          capability_version TEXT NOT NULL,
          definition_fingerprint TEXT NOT NULL,
          input_fingerprint TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          deleted_at TEXT,
          PRIMARY KEY(workspace_id, monitor_key)
        );
        CREATE TABLE IF NOT EXISTS metric_monitor_evaluations (
          evaluation_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          monitor_key TEXT NOT NULL,
          evaluation_sequence INTEGER NOT NULL,
          status TEXT NOT NULL,
          baseline_snapshot_key TEXT NOT NULL,
          current_snapshot_key TEXT NOT NULL,
          baseline_value REAL,
          current_value REAL,
          absolute_change REAL,
          percent_change REAL,
          threshold_value REAL,
          threshold_source TEXT NOT NULL,
          blockers_json TEXT NOT NULL,
          trace_json TEXT NOT NULL,
          trace_fingerprint TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, evaluation_key),
          UNIQUE(workspace_id, monitor_key, evaluation_sequence)
        );
        CREATE INDEX IF NOT EXISTS idx_metric_monitors_workspace_status
          ON metric_monitors(workspace_id, status, updated_at);
        CREATE INDEX IF NOT EXISTS idx_metric_monitors_workspace_input
          ON metric_monitors(workspace_id, input_fingerprint);
        CREATE INDEX IF NOT EXISTS idx_metric_monitor_evaluations_workspace_monitor
          ON metric_monitor_evaluations(workspace_id, monitor_key, evaluation_sequence);
        CREATE TABLE IF NOT EXISTS analysis_jobs (
          job_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          parent_job_key TEXT,
          kind TEXT NOT NULL,
          capability_id TEXT NOT NULL DEFAULT '',
          request_key TEXT NOT NULL DEFAULT '',
          label TEXT NOT NULL,
          status TEXT NOT NULL,
          progress INTEGER NOT NULL,
          stage TEXT NOT NULL,
          cancel_requested INTEGER NOT NULL,
          input_fingerprint TEXT NOT NULL,
          input_json TEXT NOT NULL,
          result_json TEXT NOT NULL,
          error_json TEXT NOT NULL,
          artifact_refs_json TEXT NOT NULL,
          evidence_refs_json TEXT NOT NULL,
          query_receipt_key TEXT,
          analysis_run_key TEXT,
          source_run_id TEXT,
          created_at TEXT NOT NULL,
          queued_at TEXT,
          started_at TEXT,
          updated_at TEXT NOT NULL,
          finished_at TEXT,
          PRIMARY KEY(workspace_id, job_key)
        );
        CREATE TABLE IF NOT EXISTS analysis_job_events (
          event_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
          workspace_id TEXT NOT NULL,
          job_key TEXT NOT NULL,
          event_type TEXT NOT NULL,
          status TEXT NOT NULL,
          progress INTEGER NOT NULL,
          stage TEXT NOT NULL,
          message TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_analysis_jobs_workspace_status
          ON analysis_jobs(workspace_id, status, updated_at);
        CREATE INDEX IF NOT EXISTS idx_analysis_jobs_workspace_parent
          ON analysis_jobs(workspace_id, parent_job_key, created_at);
        CREATE INDEX IF NOT EXISTS idx_analysis_job_events_workspace_sequence
          ON analysis_job_events(workspace_id, event_sequence);
        CREATE INDEX IF NOT EXISTS idx_analysis_job_events_job_sequence
          ON analysis_job_events(workspace_id, job_key, event_sequence);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_analysis_jobs_workspace_kind_request
          ON analysis_jobs(workspace_id, kind, request_key)
          WHERE request_key <> '';
        CREATE TABLE IF NOT EXISTS source_activation_journals (
          journal_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          job_key TEXT NOT NULL,
          phase TEXT NOT NULL,
          plan_fingerprint TEXT NOT NULL,
          parent_source_run_id TEXT,
          target_source_run_id TEXT,
          table_keys_json TEXT NOT NULL,
          expected_manifest_json TEXT NOT NULL,
          rollback_manifest_json TEXT NOT NULL,
          outcome TEXT NOT NULL,
          warning_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          finalized_at TEXT,
          PRIMARY KEY(workspace_id, journal_key)
        );
        CREATE INDEX IF NOT EXISTS idx_source_activation_workspace_phase
          ON source_activation_journals(workspace_id, phase, updated_at);
        CREATE INDEX IF NOT EXISTS idx_source_activation_workspace_job
          ON source_activation_journals(workspace_id, job_key, created_at);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_source_activation_one_active_workspace
          ON source_activation_journals(workspace_id)
          WHERE phase <> 'finalized';
        CREATE TABLE IF NOT EXISTS import_workspace_leases (
          workspace_id TEXT PRIMARY KEY,
          job_key TEXT NOT NULL UNIQUE,
          lease_token TEXT NOT NULL DEFAULT '',
          lease_epoch INTEGER NOT NULL DEFAULT 0,
          active INTEGER NOT NULL DEFAULT 1,
          acquired_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          released_at TEXT
        );
        CREATE TABLE IF NOT EXISTS source_activation_journal_events (
          event_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
          workspace_id TEXT NOT NULL,
          journal_key TEXT NOT NULL,
          job_key TEXT NOT NULL,
          phase TEXT NOT NULL,
          event_type TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_source_activation_events_journal
          ON source_activation_journal_events(workspace_id, journal_key, event_sequence);
        CREATE TABLE IF NOT EXISTS agent_sessions (
          session_key TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL,
          title TEXT NOT NULL,
          status TEXT NOT NULL,
          current_turn_key TEXT,
          parent_session_key TEXT,
          forked_from_turn_key TEXT,
          runtime_profile_id TEXT,
          context_fingerprint TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS agent_turns (
          turn_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          session_key TEXT,
          parent_turn_key TEXT,
          prompt TEXT NOT NULL,
          status TEXT NOT NULL,
          intent_json TEXT NOT NULL,
          context_json TEXT NOT NULL,
          plan_json TEXT NOT NULL,
          result_json TEXT NOT NULL,
          validation_json TEXT NOT NULL,
          context_fingerprint TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          finished_at TEXT,
          PRIMARY KEY(workspace_id, turn_key)
        );
        CREATE TABLE IF NOT EXISTS agent_turn_events (
          event_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
          workspace_id TEXT NOT NULL,
          turn_key TEXT NOT NULL,
          step_key TEXT,
          event_type TEXT NOT NULL,
          status TEXT NOT NULL,
          public_summary TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS agent_context_snapshots (
          snapshot_key TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL,
          session_key TEXT NOT NULL,
          through_turn_key TEXT,
          compaction_level INTEGER NOT NULL,
          summary_json TEXT NOT NULL,
          preserved_refs_json TEXT NOT NULL,
          stale_refs_json TEXT NOT NULL,
          source_fingerprint TEXT NOT NULL,
          fingerprint TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_agent_sessions_workspace_updated
          ON agent_sessions(workspace_id, updated_at);
        CREATE INDEX IF NOT EXISTS idx_agent_context_snapshots_session_created
          ON agent_context_snapshots(workspace_id, session_key, created_at);
        CREATE INDEX IF NOT EXISTS idx_agent_turns_workspace_updated
          ON agent_turns(workspace_id, updated_at);
        CREATE INDEX IF NOT EXISTS idx_agent_turn_events_turn_sequence
          ON agent_turn_events(workspace_id, turn_key, event_sequence);
        CREATE TABLE IF NOT EXISTS workspace_agent_runtime_profiles (
          workspace_id TEXT PRIMARY KEY,
          profile_id TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS agent_provider_evaluations (
          evaluation_key TEXT PRIMARY KEY,
          workspace_id TEXT NOT NULL,
          profile_id TEXT NOT NULL,
          profile_fingerprint TEXT NOT NULL,
          provider TEXT NOT NULL,
          model TEXT NOT NULL,
          request_fingerprint TEXT NOT NULL,
          context_fingerprint TEXT NOT NULL,
          status TEXT NOT NULL,
          validation_status TEXT NOT NULL,
          duration_ms INTEGER NOT NULL,
          prompt_tokens INTEGER,
          completion_tokens INTEGER,
          total_tokens INTEGER,
          estimated_cost_usd REAL NOT NULL,
          attempts INTEGER NOT NULL,
          fallback_reason TEXT,
          shadow INTEGER NOT NULL DEFAULT 0,
          audit_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_agent_provider_evaluations_workspace_created
          ON agent_provider_evaluations(workspace_id, created_at);
        CREATE TABLE IF NOT EXISTS plan_quality_scorecards (
          scorecard_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          status TEXT NOT NULL,
          case_set_id TEXT NOT NULL,
          case_set_fingerprint TEXT NOT NULL,
          policy_fingerprint TEXT NOT NULL,
          runtime_fingerprint TEXT NOT NULL,
          scorecard_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, scorecard_key)
        );
        CREATE INDEX IF NOT EXISTS idx_plan_quality_scorecards_workspace_created
          ON plan_quality_scorecards(workspace_id, created_at);
        CREATE TABLE IF NOT EXISTS exploration_threads (
          thread_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          title TEXT NOT NULL,
          status TEXT NOT NULL,
          root_anchor_key TEXT NOT NULL,
          current_anchor_key TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, thread_key)
        );
        CREATE TABLE IF NOT EXISTS exploration_anchors (
          anchor_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          thread_key TEXT NOT NULL,
          parent_anchor_key TEXT,
          label TEXT NOT NULL,
          analysis_run_key TEXT NOT NULL,
          query_receipt_key TEXT NOT NULL,
          analysis_unit_key TEXT NOT NULL,
          session_key TEXT,
          turn_key TEXT,
          run_fingerprint TEXT NOT NULL,
          receipt_fingerprint TEXT NOT NULL,
          unit_fingerprint TEXT NOT NULL,
          result_fingerprint TEXT NOT NULL,
          chart_input_fingerprint TEXT NOT NULL,
          turn_context_fingerprint TEXT NOT NULL,
          binding_fingerprint TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, anchor_key),
          UNIQUE(workspace_id, thread_key, analysis_run_key)
        );
        CREATE TABLE IF NOT EXISTS exploration_board_items (
          board_item_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          thread_key TEXT NOT NULL,
          anchor_key TEXT NOT NULL,
          position INTEGER NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, board_item_key),
          UNIQUE(workspace_id, thread_key, anchor_key)
        );
        CREATE INDEX IF NOT EXISTS idx_exploration_threads_workspace_updated
          ON exploration_threads(workspace_id, updated_at);
        CREATE INDEX IF NOT EXISTS idx_exploration_anchors_thread_created
          ON exploration_anchors(workspace_id, thread_key, created_at);
        CREATE INDEX IF NOT EXISTS idx_exploration_board_thread_position
          ON exploration_board_items(workspace_id, thread_key, position, created_at);
        CREATE TABLE IF NOT EXISTS research_runs (
          research_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          thread_key TEXT NOT NULL,
          baseline_anchor_key TEXT NOT NULL,
          baseline_binding_fingerprint TEXT NOT NULL,
          goal TEXT NOT NULL,
          status TEXT NOT NULL,
          current_revision_key TEXT NOT NULL,
          budget_json TEXT NOT NULL,
          conclusion_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          completed_at TEXT,
          PRIMARY KEY(workspace_id, research_key)
        );
        CREATE TABLE IF NOT EXISTS research_plan_revisions (
          revision_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          research_key TEXT NOT NULL,
          parent_revision_key TEXT,
          revision_number INTEGER NOT NULL,
          reason TEXT NOT NULL,
          plan_json TEXT NOT NULL,
          plan_fingerprint TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, revision_key),
          UNIQUE(workspace_id, research_key, revision_number)
        );
        CREATE TABLE IF NOT EXISTS research_observations (
          observation_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          research_key TEXT NOT NULL,
          revision_key TEXT NOT NULL,
          step_key TEXT NOT NULL,
          kind TEXT NOT NULL,
          verdict TEXT NOT NULL,
          note TEXT NOT NULL,
          anchor_key TEXT NOT NULL,
          anchor_binding_fingerprint TEXT NOT NULL,
          revision_fingerprint TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, observation_key)
        );
        CREATE TABLE IF NOT EXISTS research_run_events (
          event_sequence INTEGER PRIMARY KEY AUTOINCREMENT,
          workspace_id TEXT NOT NULL,
          research_key TEXT NOT NULL,
          revision_key TEXT,
          event_type TEXT NOT NULL,
          status TEXT NOT NULL,
          public_summary TEXT NOT NULL,
          payload_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_research_runs_workspace_updated
          ON research_runs(workspace_id, updated_at);
        CREATE INDEX IF NOT EXISTS idx_research_revisions_run_number
          ON research_plan_revisions(workspace_id, research_key, revision_number);
        CREATE INDEX IF NOT EXISTS idx_research_observations_run_created
          ON research_observations(workspace_id, research_key, created_at);
        CREATE INDEX IF NOT EXISTS idx_research_events_run_sequence
          ON research_run_events(workspace_id, research_key, event_sequence);
        """
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO workspaces(id, name, current_source_run_id, created_at)
        VALUES('default', 'AIBI-C 工作区', NULL, ?)
        """,
        (now_iso(),),
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO system_flags(key, value, updated_at)
        VALUES('active_workspace_id', 'default', ?)
        """,
        (now_iso(),),
    )
    ensure_reviewed_publication_schema(connection)
    ensure_evidence_retrieval_schema(connection)
    ensure_decision_framework_schema(connection)
    connection.executescript(SQLSERVER_SNAPSHOT_METADATA_DDL)
    ensure_default_preferences_and_themes(connection)
    connection.execute(f"PRAGMA user_version = {CURRENT_SQLITE_SCHEMA_VERSION}")
    connection.commit()


def initialize_schema(connection: sqlite3.Connection) -> None:
    """Initialize a clean v18 control database; never migrate a populated file."""
    version, has_user_tables = _control_database_state(connection)
    if version != 0 or has_user_tables:
        raise RuntimeError(
            "AIBI-C control schema initialization requires an empty database; "
            "legacy and partial files are not migrated."
        )
    _initialize_schema(connection)
    assert_control_schema_invariants(connection)


def ensure_schema(connection: sqlite3.Connection) -> None:
    """Compatibility name for explicit fixtures, with no populated-file repair."""
    version, has_user_tables = _control_database_state(connection)
    if version == 0 and not has_user_tables:
        _initialize_schema(connection)
        assert_control_schema_invariants(connection)
        return
    assert_control_schema_invariants(connection)


def normalize_user_preferences(value: Any) -> dict[str, Any]:
    return normalize_user_preferences_service(value)


def normalize_theme_tokens(value: Any) -> dict[str, str]:
    return normalize_theme_tokens_service(value)


def normalize_theme_palette(value: dict[str, Any]) -> dict[str, Any]:
    return normalize_theme_palette_service(value)


def validate_theme_palette_payload(value: dict[str, Any]) -> dict[str, Any]:
    return validate_theme_palette_payload_service(value)


def ensure_default_preferences_and_themes(connection: sqlite3.Connection) -> None:
    ensure_default_preferences_and_themes_service(connection)


def load_user_preferences(connection: sqlite3.Connection) -> dict[str, Any]:
    return load_user_preferences_service(connection)


def save_user_preferences(connection: sqlite3.Connection, preferences: dict[str, Any]) -> dict[str, Any]:
    return save_user_preferences_service(connection, preferences)


def list_theme_palettes(connection: sqlite3.Connection, enabled_only: bool = True) -> list[dict[str, Any]]:
    return list_theme_palettes_service(connection, enabled_only=enabled_only)


def upsert_theme_palette(connection: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    return upsert_theme_palette_service(connection, payload)


def delete_theme_palette(connection: sqlite3.Connection, theme_key: str) -> dict[str, Any]:
    return delete_theme_palette_service(connection, theme_key)


def navigation_module_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "moduleKey": row["module_key"],
        "name": row["name"],
        "type": row["module_type"],
        "tableKey": row["table_key"] or "",
        "dashboardKey": row["dashboard_key"] or "",
        "sort": int(row["sort_order"] or 0),
        "createdBy": row["created_by"] or "system",
        "agentManaged": bool(row["agent_managed"]),
        "enabled": bool(row["enabled"]),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def next_navigation_sort(
    connection: sqlite3.Connection,
    module_type: str,
    workspace_id: str | None = None,
) -> int:
    base = {"table": 100, "view": 400, "dashboard": 700}.get(module_type, 900)
    resolved_workspace_id = str(workspace_id or active_workspace_id(connection))
    row = connection.execute(
        """
        SELECT COALESCE(MAX(sort_order), ?) AS max_sort
        FROM navigation_modules
        WHERE module_type = ? AND workspace_id = ?
        """,
        (base, module_type, resolved_workspace_id),
    ).fetchone()
    return int(row["max_sort"] or base) + 10


def upsert_navigation_module(
    connection: sqlite3.Connection,
    *,
    module_key: str,
    name: str,
    module_type: str,
    table_key: str = "",
    dashboard_key: str = "",
    created_by: str = "system",
    agent_managed: int = 1,
    workspace_id: str | None = None,
) -> None:
    now = now_iso()
    resolved_workspace_id = str(workspace_id or active_workspace_id(connection))
    existing = connection.execute(
        "SELECT * FROM navigation_modules WHERE module_key = ? AND workspace_id = ?",
        (module_key, resolved_workspace_id),
    ).fetchone()
    if existing:
        next_table_key = table_key or None
        next_dashboard_key = dashboard_key or None
        if existing["table_key"] == next_table_key and existing["dashboard_key"] == next_dashboard_key:
            return
        connection.execute(
            """
            UPDATE navigation_modules
            SET table_key = ?,
                dashboard_key = ?,
                updated_at = ?
            WHERE module_key = ? AND workspace_id = ?
            """,
            (next_table_key, next_dashboard_key, now, module_key, resolved_workspace_id),
        )
        return
    connection.execute(
        """
        INSERT INTO navigation_modules(
          module_key, workspace_id, name, module_type, table_key, dashboard_key, sort_order,
          created_by, agent_managed, enabled, created_at, updated_at
        )
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
        """,
        (
            module_key,
            resolved_workspace_id,
            name,
            module_type,
            table_key or None,
            dashboard_key or None,
            next_navigation_sort(connection, module_type, workspace_id=resolved_workspace_id),
            created_by,
            int(agent_managed),
            now,
            now,
        ),
    )


def ensure_navigation_modules(connection: sqlite3.Connection) -> None:
    workspace_id = active_workspace_id(connection)
    for row in connection.execute(
        "SELECT table_key, display_name FROM table_registry WHERE workspace_id = ? ORDER BY display_name",
        (workspace_id,),
    ).fetchall():
        upsert_navigation_module(
            connection,
            module_key=f"table:{row['table_key']}",
            name=row["display_name"],
            module_type="table",
            table_key=row["table_key"],
            created_by="system",
            agent_managed=1,
        )
    for row in connection.execute(
        "SELECT dashboard_key, name FROM dashboards WHERE workspace_id = ? ORDER BY created_at",
        (workspace_id,),
    ).fetchall():
        upsert_navigation_module(
            connection,
            module_key=f"dashboard:{row['dashboard_key']}",
            name=row["name"],
            module_type="dashboard",
            dashboard_key=row["dashboard_key"],
            created_by="system",
            agent_managed=1,
        )


def list_navigation_modules(connection: sqlite3.Connection, include_disabled: bool = False) -> list[dict[str, Any]]:
    ensure_navigation_modules(connection)
    workspace_id = active_workspace_id(connection)
    enabled_clause = "" if include_disabled else "AND n.enabled = 1"
    rows = connection.execute(
        f"""
        SELECT n.*
        FROM navigation_modules n
        LEFT JOIN table_registry t
          ON t.table_key = n.table_key
         AND t.workspace_id = ?
        LEFT JOIN dashboards d
          ON d.dashboard_key = n.dashboard_key
         AND d.workspace_id = ?
        WHERE n.workspace_id = ?
          AND (
          (n.module_type = 'table' AND t.table_key IS NOT NULL)
          OR (n.module_type = 'dashboard' AND d.dashboard_key IS NOT NULL)
          OR n.module_type = 'view'
        )
        {enabled_clause}
        ORDER BY sort_order, module_type, name
        """,
        (workspace_id, workspace_id, workspace_id),
    ).fetchall()
    return [navigation_module_payload(row) for row in rows]


