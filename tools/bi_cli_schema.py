from __future__ import annotations

import json
import sqlite3
import time
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


CURRENT_SQLITE_SCHEMA_VERSION = 6
CURRENT_DUCKDB_SCHEMA_VERSION = 1


def sqlite_schema_version(connection: sqlite3.Connection) -> int:
    row = connection.execute("PRAGMA user_version").fetchone()
    return int(row[0] if row is not None else 0)


def assert_sqlite_schema_compatible(connection: sqlite3.Connection) -> int:
    version = sqlite_schema_version(connection)
    if version > CURRENT_SQLITE_SCHEMA_VERSION:
        raise RuntimeError(
            f"AIBI-C metadata schema v{version} is newer than this runtime "
            f"(max v{CURRENT_SQLITE_SCHEMA_VERSION}); no changes were made."
        )
    return version


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
    if version is not None and version > CURRENT_DUCKDB_SCHEMA_VERSION:
        raise RuntimeError(
            f"AIBI-C analytics schema v{version} is newer than this runtime "
            f"(max v{CURRENT_DUCKDB_SCHEMA_VERSION}); no changes were made."
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


def table_columns(connection: sqlite3.Connection, physical_table: str) -> list[str]:
    return [row["name"] for row in connection.execute(f"PRAGMA table_info({quote_identifier(physical_table)})")]


def ensure_column(connection: sqlite3.Connection, table_name: str, column_name: str, definition: str) -> None:
    if column_name not in table_columns(connection, table_name):
        connection.execute(f"ALTER TABLE {quote_identifier(table_name)} ADD COLUMN {quote_identifier(column_name)} {definition}")


def primary_key_columns(connection: sqlite3.Connection, table_name: str) -> list[str]:
    rows = connection.execute(f"PRAGMA table_info({quote_identifier(table_name)})").fetchall()
    return [row["name"] for row in sorted((row for row in rows if int(row["pk"] or 0)), key=lambda row: int(row["pk"]))]


def has_unique_index(connection: sqlite3.Connection, table_name: str, columns: list[str]) -> bool:
    expected = list(columns)
    for index_row in connection.execute(f"PRAGMA index_list({quote_identifier(table_name)})").fetchall():
        if not int(index_row["unique"] or 0):
            continue
        index_name = str(index_row["name"])
        actual = [row["name"] for row in connection.execute(f"PRAGMA index_info({quote_identifier(index_name)})").fetchall()]
        if actual == expected:
            return True
    return False


def rebuild_table(connection: sqlite3.Connection, table_name: str, create_sql: str) -> None:
    legacy_name = f"{table_name}_legacy_{int(time.time() * 1000)}"
    existing_columns = table_columns(connection, table_name)
    connection.execute(f"ALTER TABLE {quote_identifier(table_name)} RENAME TO {quote_identifier(legacy_name)}")
    connection.execute(create_sql)
    next_columns = table_columns(connection, table_name)
    common_columns = [column for column in next_columns if column in existing_columns]
    if common_columns:
        column_sql = ", ".join(quote_identifier(column) for column in common_columns)
        connection.execute(
            f"INSERT OR IGNORE INTO {quote_identifier(table_name)} ({column_sql}) "
            f"SELECT {column_sql} FROM {quote_identifier(legacy_name)}"
        )
    connection.execute(f"DROP TABLE {quote_identifier(legacy_name)}")


def migrate_workspace_scoped_constraints(connection: sqlite3.Connection) -> None:
    desired_tables = {
        "table_registry": (
            ["workspace_id", "table_key"],
            """
            CREATE TABLE table_registry (
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
              PRIMARY KEY(workspace_id, table_key)
            )
            """,
        ),
        "navigation_modules": (
            ["workspace_id", "module_key"],
            """
            CREATE TABLE navigation_modules (
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
            )
            """,
        ),
        "metric_definitions": (
            ["workspace_id", "metric_key"],
            """
            CREATE TABLE metric_definitions (
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
            )
            """,
        ),
        "data_connectors": (
            ["workspace_id", "connector_key"],
            """
            CREATE TABLE data_connectors (
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
            )
            """,
        ),
        "calculated_fields": (
            ["workspace_id", "field_key"],
            """
            CREATE TABLE calculated_fields (
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
            )
            """,
        ),
        "relationships": (
            ["workspace_id", "relation_key"],
            """
            CREATE TABLE relationships (
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
            )
            """,
        ),
        "import_policies": (
            ["workspace_id", "table_key"],
            """
            CREATE TABLE import_policies (
              table_key TEXT NOT NULL,
              workspace_id TEXT NOT NULL DEFAULT 'default',
              unique_fields_json TEXT NOT NULL,
              conflict_rule TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              PRIMARY KEY(workspace_id, table_key)
            )
            """,
        ),
        "saved_views": (
            ["workspace_id", "view_key"],
            """
            CREATE TABLE saved_views (
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
            )
            """,
        ),
        "dashboards": (
            ["workspace_id", "dashboard_key"],
            """
            CREATE TABLE dashboards (
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
            )
            """,
        ),
        "dashboard_widgets": (
            ["workspace_id", "widget_key"],
            """
            CREATE TABLE dashboard_widgets (
              widget_key TEXT NOT NULL,
              workspace_id TEXT NOT NULL DEFAULT 'default',
              dashboard_key TEXT NOT NULL,
              widget_type TEXT NOT NULL,
              title TEXT NOT NULL,
              table_key TEXT,
              config_json TEXT NOT NULL,
              sort_order INTEGER NOT NULL,
              PRIMARY KEY(workspace_id, widget_key)
            )
            """,
        ),
    }
    for table_name, (pk_columns, create_sql) in desired_tables.items():
        if primary_key_columns(connection, table_name) != pk_columns:
            rebuild_table(connection, table_name, create_sql)
    if not has_unique_index(connection, "field_semantics", ["workspace_id", "table_key", "field_name"]):
        rebuild_table(
            connection,
            "field_semantics",
            """
            CREATE TABLE field_semantics (
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
            )
            """,
        )


def physical_table_for_workspace(workspace_id: str, table_key: str) -> str:
    if workspace_id == "default":
        return f"data_{table_key}"
    return f"data_{slug(workspace_id)[:28]}_{slug(table_key)[:48]}"[:96]


def registry_for_table(connection: sqlite3.Connection, table_key: str) -> sqlite3.Row | None:
    return connection.execute("SELECT * FROM table_registry WHERE table_key = ? AND workspace_id = ?", (table_key, active_workspace_id(connection))).fetchone()


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
    database_existed = DB_PATH.exists()
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    try:
        version = assert_sqlite_schema_compatible(connection)
        existing_tables = int(connection.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchone()[0])
        if database_existed and existing_tables and version < CURRENT_SQLITE_SCHEMA_VERSION:
            raise RuntimeError(
                f"AIBI-C metadata schema v{version} requires a guarded migration to "
                f"v{CURRENT_SQLITE_SCHEMA_VERSION}. Stop local services, run `npm run migrate:local`, "
                "review the preview, then rerun with `-- --confirm`."
            )
        assert_duckdb_schema_compatible()
        ensure_schema(connection)
        ensure_navigation_modules(connection)
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


def ensure_schema(connection: sqlite3.Connection) -> None:
    previous_version = assert_sqlite_schema_compatible(connection)
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
          PRIMARY KEY(workspace_id, table_key)
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
        CREATE TABLE IF NOT EXISTS analysis_jobs (
          job_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          parent_job_key TEXT,
          kind TEXT NOT NULL,
          capability_id TEXT NOT NULL DEFAULT '',
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
        UPDATE workspaces
        SET name = 'AIBI-C 工作区'
        WHERE id = 'default' AND name IN ('AIBI Hybrid Workspace', 'AIBI 工作区')
        """
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO system_flags(key, value, updated_at)
        VALUES('active_workspace_id', 'default', ?)
        """,
        (now_iso(),),
    )
    connection.execute(
        """
        UPDATE action_drafts
        SET status = 'read-only-legacy'
        WHERE kind = 'analysis.plan' AND status = 'draft'
        """
    )
    ensure_column(connection, "field_semantics", "tags_json", "TEXT NOT NULL DEFAULT '[]'")
    ensure_column(connection, "table_registry", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    ensure_column(connection, "table_registry", "data_version", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(connection, "table_registry", "updated_at", "TEXT NOT NULL DEFAULT ''")
    ensure_column(connection, "field_semantics", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    ensure_column(connection, "field_semantics", "usage_json", "TEXT NOT NULL DEFAULT '{}'")
    ensure_column(connection, "field_semantics", "source", "TEXT NOT NULL DEFAULT 'auto'")
    ensure_column(connection, "field_semantics", "note", "TEXT NOT NULL DEFAULT ''")
    ensure_column(connection, "field_semantics", "updated_at", "TEXT NOT NULL DEFAULT ''")
    ensure_column(connection, "metric_definitions", "filters_json", "TEXT NOT NULL DEFAULT '[]'")
    ensure_column(connection, "metric_definitions", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    ensure_column(connection, "metric_definitions", "description", "TEXT NOT NULL DEFAULT ''")
    ensure_column(connection, "metric_definitions", "source", "TEXT NOT NULL DEFAULT 'auto'")
    ensure_column(connection, "metric_definitions", "enabled", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(connection, "metric_definitions", "updated_at", "TEXT NOT NULL DEFAULT ''")
    ensure_column(connection, "metric_definitions", "formula_text", "TEXT NOT NULL DEFAULT ''")
    ensure_column(connection, "metric_definitions", "formula_ast_json", "TEXT NOT NULL DEFAULT '{}'")
    ensure_column(connection, "metric_definitions", "dependencies_json", "TEXT NOT NULL DEFAULT '[]'")
    ensure_column(connection, "metric_definitions", "metric_type", "TEXT NOT NULL DEFAULT 'basic'")
    ensure_column(connection, "calculated_fields", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    ensure_column(connection, "relationships", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    ensure_column(connection, "relationships", "mappings_json", "TEXT NOT NULL DEFAULT '[]'")
    ensure_column(connection, "relationships", "filters_json", "TEXT NOT NULL DEFAULT '[]'")
    ensure_column(connection, "relationships", "preaggregation_json", "TEXT NOT NULL DEFAULT '{}'")
    ensure_column(connection, "relationships", "validation_json", "TEXT NOT NULL DEFAULT '{}'")
    ensure_column(connection, "relationships", "updated_at", "TEXT NOT NULL DEFAULT ''")
    ensure_column(connection, "navigation_modules", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    ensure_column(connection, "dashboards", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    ensure_column(connection, "dashboard_widgets", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    ensure_column(connection, "import_jobs", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    ensure_column(connection, "import_policies", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    connector_workspace_missing = "workspace_id" not in table_columns(connection, "data_connectors")
    ensure_column(connection, "data_connectors", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    if connector_workspace_missing:
        connection.execute("UPDATE data_connectors SET workspace_id = ?", (active_workspace_id(connection),))
    ensure_column(connection, "action_drafts", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    ensure_column(connection, "source_intelligence_runs", "workspace_id", "TEXT NOT NULL DEFAULT 'default'")
    ensure_column(connection, "analysis_jobs", "capability_id", "TEXT NOT NULL DEFAULT ''")
    migrate_workspace_scoped_constraints(connection)
    for relationship in connection.execute(
        """
        SELECT workspace_id, relation_key, left_field, right_field
        FROM relationships
        WHERE mappings_json IS NULL OR mappings_json = '' OR mappings_json = '[]'
        """
    ).fetchall():
        connection.execute(
            "UPDATE relationships SET mappings_json = ? WHERE workspace_id = ? AND relation_key = ?",
            (
                json.dumps(
                    [{"leftField": str(relationship["left_field"]), "rightField": str(relationship["right_field"])}],
                    ensure_ascii=False,
                ),
                relationship["workspace_id"],
                relationship["relation_key"],
            ),
        )
    connection.execute("UPDATE relationships SET updated_at = created_at WHERE updated_at IS NULL OR updated_at = ''")
    connection.execute("UPDATE table_registry SET data_version = 1 WHERE data_version IS NULL OR data_version < 1")
    connection.execute("UPDATE table_registry SET updated_at = created_at WHERE updated_at IS NULL OR updated_at = ''")
    ensure_default_preferences_and_themes(connection)
    if previous_version < CURRENT_SQLITE_SCHEMA_VERSION:
        connection.execute(f"PRAGMA user_version = {CURRENT_SQLITE_SCHEMA_VERSION}")
    connection.commit()


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


def next_navigation_sort(connection: sqlite3.Connection, module_type: str) -> int:
    base = {"table": 100, "view": 400, "dashboard": 700}.get(module_type, 900)
    workspace_id = active_workspace_id(connection)
    row = connection.execute(
        """
        SELECT COALESCE(MAX(sort_order), ?) AS max_sort
        FROM navigation_modules
        WHERE module_type = ? AND workspace_id = ?
        """,
        (base, module_type, workspace_id),
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
) -> None:
    now = now_iso()
    workspace_id = active_workspace_id(connection)
    existing = connection.execute(
        "SELECT * FROM navigation_modules WHERE module_key = ? AND workspace_id = ?",
        (module_key, workspace_id),
    ).fetchone()
    if existing:
        connection.execute(
            """
            UPDATE navigation_modules
            SET table_key = ?,
                dashboard_key = ?,
                updated_at = ?
            WHERE module_key = ? AND workspace_id = ?
            """,
            (table_key or None, dashboard_key or None, now, module_key, workspace_id),
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
            workspace_id,
            name,
            module_type,
            table_key or None,
            dashboard_key or None,
            next_navigation_sort(connection, module_type),
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


