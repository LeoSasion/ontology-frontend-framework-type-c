from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def write_csv(path: Path, rows: list[list[str]]) -> None:
    path.write_text("\n".join(",".join(row) for row in rows) + "\n", encoding="utf-8")


def main() -> int:
    checks: list[dict[str, Any]] = []

    def check(label: str, ok: object, detail: Any = None) -> None:
        item: dict[str, Any] = {"label": label, "ok": bool(ok)}
        if not ok and detail is not None:
            item["detail"] = detail
        checks.append(item)

    with tempfile.TemporaryDirectory(prefix="aibi-import-schema-change-") as raw_temp:
        temp_root = Path(raw_temp)
        sqlite_path = temp_root / "runtime.sqlite"
        duckdb_path = temp_root / "runtime.duckdb"
        os.environ["AIBI_HYBRID_DB_PATH"] = str(sqlite_path)
        os.environ["AIBI_HYBRID_DUCKDB_PATH"] = str(duckdb_path)
        os.environ["AIBI_EVIDENCE_BUNDLE_ROOT"] = str(temp_root / "evidence")
        os.environ["AIBI_WORKSPACE_RECOVERY_ROOT"] = str(temp_root / "recovery")

        from atomic_import_plan_service import bind_single_import_plan
        from bi_cli_core import now_iso
        from bi_cli_schema import active_workspace_id, open_db as raw_open_db, physical_table_for_workspace, table_columns
        from bi_cli_source_commands import build_import_preview, execute_import_commit
        from dataset_version_store import activate_dataset_version, resolve_dataset_object_paths
        from import_command_service import build_folder_import_plan, execute_folder_import_plan
        from import_job_service import import_job_create_command, import_job_run_command
        from job_runtime_service import get_job
        from query_runtime import publish_dataset_view, replica_source_version
        from source_activation_journal_service import activation_for_job

        @contextmanager
        def open_db():
            connection = raw_open_db()
            try:
                yield connection
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

        old_path = temp_root / "orders-old.csv"
        new_path = temp_root / "orders-new.csv"
        write_csv(old_path, [
            ["id", "amount", "legacy"],
            ["o-1", "100", "old-a"],
            ["o-2", "200", "old-b"],
        ])
        write_csv(new_path, [
            ["id", "amount", "channel"],
            ["o-3", "300", "online"],
            ["o-4", "400", "store"],
        ])

        with open_db() as connection:
            seeded = execute_import_commit(
                connection,
                old_path,
                "orders",
                "Orders",
                "create",
                workspace_id="default",
            )
            seeded_version = dict(seeded["datasetVersion"])
            seeded_registry = connection.execute(
                "SELECT * FROM table_registry WHERE workspace_id = 'default' AND table_key = 'orders'"
            ).fetchone()
            seeded_files = [item for item in seeded_version.get("files") or [] if isinstance(item, dict)]
            import duckdb  # type: ignore
            with duckdb.connect(str(duckdb_path)) as duck_connection:
                publish_dataset_view(
                    duck_connection,
                    logical_table=str(seeded_registry["physical_table"]),
                    source_version=replica_source_version(seeded_registry),
                    version_id=str(seeded_version["versionId"]),
                    object_keys=[str(item["objectKey"]) for item in seeded_files],
                    object_paths=resolve_dataset_object_paths(seeded_version),
                    object_hashes=[str(item["objectHash"]) for item in seeded_files],
                    schema_fingerprint=str(seeded_version["schemaFingerprint"]),
                    content_fingerprint=str(seeded_version["contentFingerprint"]),
                    row_count=int(seeded_version["rowCount"]),
                )
            activate_dataset_version(connection, seeded_version)
            timestamp = now_iso()
            connection.execute(
                """
                INSERT INTO metric_definitions(
                  metric_key, workspace_id, label, table_key, measure, aggregation,
                  dimension, time_field, value_format, created_at, filters_json,
                  description, source, enabled, updated_at, formula_text,
                  formula_ast_json, dependencies_json, metric_type
                ) VALUES('legacy_total', 'default', 'Legacy total', 'orders', 'legacy', 'count',
                  '', '', 'number', ?, '[]', '', 'manual', 1, ?, '', '{}', '["legacy"]', 'basic')
                """,
                (timestamp, timestamp),
            )
            for index in range(25):
                connection.execute(
                    """
                    INSERT INTO metric_definitions(
                      metric_key, workspace_id, label, table_key, measure, aggregation,
                      dimension, time_field, value_format, created_at, filters_json,
                      description, source, enabled, updated_at, formula_text,
                      formula_ast_json, dependencies_json, metric_type
                    ) VALUES(?, 'default', ?, 'orders', 'legacy', 'count',
                      '', '', 'number', ?, '[]', '', 'manual', 1, ?, '', '{}', '["legacy"]', 'basic')
                    """,
                    (f"legacy_metric_{index:02d}", f"Legacy metric {index:02d}", timestamp, timestamp),
                )
            connection.execute(
                """
                INSERT INTO saved_views(
                  view_key, workspace_id, name, tag_name, table_key, config_json,
                  is_default, sort_order, created_by, agent_managed, created_at, updated_at
                ) VALUES('legacy_view', 'default', 'Legacy view', '', 'orders',
                  '{"columns":["id","legacy"]}', 0, 0, 'owner', 0, ?, ?)
                """,
                (timestamp, timestamp),
            )
            connection.execute(
                """
                INSERT INTO dashboard_widgets(
                  widget_key, workspace_id, dashboard_key, widget_type, title,
                  table_key, config_json, sort_order
                ) VALUES('legacy_widget', 'default', 'default', 'table', 'Legacy widget',
                  'orders', '{"dimension":"legacy"}', 0)
                """
            )
            connection.execute(
                """
                INSERT INTO field_semantics(
                  workspace_id, table_key, field_name, role, usage, confidence,
                  tags_json, usage_json, source, note, updated_at
                ) VALUES('default', 'orders', 'legacy', 'dimension', 'filterable', 1,
                  '[]', '{}', 'manual', '', ?)
                ON CONFLICT(workspace_id, table_key, field_name) DO UPDATE SET
                  role = excluded.role,
                  usage = excluded.usage,
                  source = excluded.source,
                  updated_at = excluded.updated_at
                """,
                (timestamp,),
            )
            connection.execute(
                """
                INSERT INTO relationships(
                  relation_key, workspace_id, name, left_table_key, right_table_key,
                  left_field, right_field, mappings_json, filters_json,
                  preaggregation_json, join_type, confidence, validation_json,
                  created_at, updated_at
                ) VALUES('legacy_relation', 'default', 'Legacy relation', 'orders', 'orders',
                  'legacy', 'id', '[]', '[]', '{}', 'left', 1, '{}', ?, ?)
                """,
                (timestamp, timestamp),
            )
            connection.commit()
            current_source_run_id = str(seeded.get("sourceRunId") or "") or None
            replace_preview = build_import_preview(
                connection,
                new_path,
                "orders",
                workspace_id="default",
                mode_value="replace",
            )
            replace_plan = bind_single_import_plan(
                replace_preview,
                new_path,
                current_source_run_id=current_source_run_id,
            )
            merge_preview = build_import_preview(
                connection,
                new_path,
                "orders",
                workspace_id="default",
                mode_value="merge",
            )
            merge_plan = bind_single_import_plan(
                merge_preview,
                new_path,
                current_source_run_id=current_source_run_id,
            )

        schema_change = replace_plan.get("schemaChange") or {}
        impact = schema_change.get("impact") or {}
        check(
            "replace-preview-reports-exact-field-diff",
            schema_change.get("addedFields") == ["channel"]
            and schema_change.get("removedFields") == ["legacy"]
            and schema_change.get("retainedFields") == ["id", "amount"]
            and schema_change.get("confirmationRequired") is True,
            schema_change,
        )
        check(
            "replace-preview-reports-complete-downstream-impact",
            int(impact.get("totalDependencies") or 0) >= 5
            and len(str(impact.get("fingerprint") or "")) == 64
            and [item.get("key") for item in impact.get("relationships", [])] == ["legacy_relation"]
            and "legacy_total" in [item.get("key") for item in impact.get("metrics", [])]
            and len(impact.get("metrics", [])) > 20
            and all(
                f"legacy_metric_{index:02d}" in [item.get("key") for item in impact.get("metrics", [])]
                for index in range(25)
            )
            and impact.get("truncated") is False
            and [item.get("key") for item in impact.get("savedViews", [])] == ["legacy_view"]
            and [item.get("key") for item in impact.get("dashboardWidgets", [])] == ["legacy_widget"]
            and [item.get("key") for item in impact.get("fieldSemantics", [])] == ["legacy"],
            impact,
        )
        check(
            "schema-mismatch-cannot-be-silently-merged",
            merge_plan.get("readyToCommit") is False
            and "merge-schema-mismatch" in (merge_plan.get("blockers") or [])
            and merge_plan.get("commitOptions", {}).get("mode") == "merge",
            merge_plan,
        )

        create_dependencies = {
            "open_db": open_db,
            "active_workspace_id": active_workspace_id,
            "build_import_preview": build_import_preview,
            "build_folder_import_plan": build_folder_import_plan,
            "now_iso": now_iso,
        }

        def create_args(*, request_key: str, plan: dict[str, Any], mode: str, confirm: bool) -> argparse.Namespace:
            return argparse.Namespace(
                import_kind="single",
                path=str(new_path),
                request_key=request_key,
                expected_plan=plan["planFingerprint"],
                workspace="default",
                label="Schema replacement",
                table="orders",
                name="Orders",
                mode=mode,
                confirm_schema_change=confirm,
                unique_fields="",
                conflict_rule="overwrite",
                limit=200,
                no_recursive=False,
            )

        with open_db() as connection:
            job_count_before = int(connection.execute("SELECT COUNT(*) FROM analysis_jobs").fetchone()[0])
        missing_confirmation_error = ""
        try:
            import_job_create_command(
                create_args(request_key="schema-no-confirm", plan=replace_plan, mode="replace", confirm=False),
                **create_dependencies,
            )
        except ValueError as error:
            missing_confirmation_error = str(error)
        with open_db() as connection:
            job_count_after_missing_confirmation = int(connection.execute("SELECT COUNT(*) FROM analysis_jobs").fetchone()[0])
        check(
            "backend-refuses-schema-replacement-without-explicit-confirmation",
            "IMPORT_SCHEMA_CHANGE_CONFIRMATION_REQUIRED" in missing_confirmation_error
            and job_count_after_missing_confirmation == job_count_before,
            {"error": missing_confirmation_error, "before": job_count_before, "after": job_count_after_missing_confirmation},
        )

        blocked_merge_error = ""
        try:
            import_job_create_command(
                create_args(request_key="schema-merge-blocked", plan=merge_plan, mode="merge", confirm=False),
                **create_dependencies,
            )
        except ValueError as error:
            blocked_merge_error = str(error)
        check(
            "backend-refuses-schema-mismatched-merge-even-with-a-frozen-plan",
            "merge-schema-mismatch" in blocked_merge_error,
            blocked_merge_error,
        )

        with open_db() as connection:
            connection.execute(
                "UPDATE metric_definitions SET label = 'Legacy total changed' WHERE workspace_id = 'default' AND metric_key = 'legacy_total'"
            )
            connection.commit()
        drift_error = ""
        try:
            import_job_create_command(
                create_args(request_key="schema-drift", plan=replace_plan, mode="replace", confirm=True),
                **create_dependencies,
            )
        except ValueError as error:
            drift_error = str(error)
        check(
            "dependency-drift-invalidates-the-reviewed-plan",
            "plan changed after preview" in drift_error,
            drift_error,
        )

        with open_db() as connection:
            current_source_run_id = str(connection.execute(
                "SELECT current_source_run_id FROM workspaces WHERE id = 'default'"
            ).fetchone()[0] or "") or None
            confirmed_preview = build_import_preview(
                connection,
                new_path,
                "orders",
                workspace_id="default",
                mode_value="replace",
            )
            confirmed_plan = bind_single_import_plan(
                confirmed_preview,
                new_path,
                current_source_run_id=current_source_run_id,
            )

        created = import_job_create_command(
            create_args(request_key="schema-confirmed", plan=confirmed_plan, mode="replace", confirm=True),
            **create_dependencies,
        )
        job_key = str(created.get("job", {}).get("jobKey") or "")
        public_change = created.get("job", {}).get("input", {}).get("schemaChange") or {}
        check(
            "confirmed-schema-change-creates-one-plan-bound-durable-job",
            bool(job_key)
            and created.get("job", {}).get("status") == "queued"
            and public_change.get("removedFieldCount") == 1
            and public_change.get("addedFieldCount") == 1
            and public_change.get("confirmationRequired") is True,
            created,
        )

        run_result = import_job_run_command(
            argparse.Namespace(job=job_key, workspace="default", lease_token=""),
            open_db=open_db,
            active_workspace_id=active_workspace_id,
            build_import_preview=build_import_preview,
            build_folder_import_plan=build_folder_import_plan,
            execute_import_commit=execute_import_commit,
            execute_folder_import_plan=execute_folder_import_plan,
            physical_table_for_workspace=physical_table_for_workspace,
            duckdb_path=duckdb_path,
            mutation_lock_path=temp_root / ".aibi-cross-engine-writer.lock",
            recovery_root=temp_root / "recovery",
            now_iso=now_iso,
        )
        with open_db() as connection:
            registry = connection.execute(
                "SELECT physical_table, row_count, data_version FROM table_registry WHERE workspace_id = 'default' AND table_key = 'orders'"
            ).fetchone()
            physical_table = str(registry["physical_table"])
            columns = table_columns(connection, physical_table)
            persisted = get_job(connection, workspace_id="default", job_key=job_key, event_limit=100)
            journal = activation_for_job(connection, workspace_id="default", job_key=job_key)
        import duckdb  # type: ignore
        duck_connection = duckdb.connect(str(duckdb_path), read_only=True)
        try:
            replica_rows = [tuple(row) for row in duck_connection.execute(
                f'SELECT "id", "amount", "channel" FROM "{physical_table}" ORDER BY "id"'
            ).fetchall()]
        finally:
            duck_connection.close()
        check(
            "confirmed-replacement-finishes-the-standard-activation-lifecycle",
            run_result.get("ok") is True
            and persisted.get("status") == "succeeded"
            and journal is not None
            and journal.get("phase") == "finalized"
            and journal.get("outcome") == "committed"
            and columns == ["id", "amount", "channel"]
            and replica_rows == [("o-3", 300, "online"), ("o-4", 400, "store")],
            {"job": persisted, "journal": journal, "columns": columns, "replicaRows": replica_rows},
        )

    failed = [item for item in checks if not item["ok"]]
    print(json.dumps({
        "ok": not failed,
        "schema": "aibi-import-schema-change-verify/v1",
        "generatedBy": "scripts/verify-import-schema-change.py",
        "checks": checks,
        "failedChecks": failed,
    }, ensure_ascii=False, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
