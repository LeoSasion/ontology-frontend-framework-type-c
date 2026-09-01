from __future__ import annotations

import argparse
import hashlib
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


def check(checks: list[dict[str, Any]], label: str, ok: bool, detail: Any = None) -> None:
    item: dict[str, Any] = {"label": label, "ok": bool(ok)}
    if not ok and detail is not None:
        item["detail"] = detail
    checks.append(item)


def write_csv(path: Path, rows: list[list[str]]) -> None:
    path.write_text("\n".join(",".join(row) for row in rows) + "\n", encoding="utf-8")


def main() -> None:
    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="aibi-c-durable-import-") as raw_temp:
        temp_root = Path(raw_temp)
        sqlite_path = temp_root / "runtime.sqlite"
        duckdb_path = temp_root / "runtime.duckdb"
        os.environ["AIBI_HYBRID_DB_PATH"] = str(sqlite_path)
        os.environ["AIBI_HYBRID_DUCKDB_PATH"] = str(duckdb_path)
        os.environ["AIBI_EVIDENCE_BUNDLE_ROOT"] = str(temp_root / "evidence")

        from atomic_import_plan_service import bind_single_import_plan
        from bi_cli_core import now_iso
        from bi_cli_schema import active_workspace_id, open_db as raw_open_db, physical_table_for_workspace
        from bi_cli_source_commands import build_import_preview, execute_import_commit
        import import_command_service as import_command_runtime
        from import_command_service import build_folder_import_plan, execute_folder_import_plan
        import import_job_service as import_job_runtime
        from import_job_service import (
            import_job_create_command,
            import_job_process_exit_command,
            import_job_resume_command,
            import_job_run_command,
            recover_import_jobs,
        )
        from job_runtime_service import (
            STATUS_CANCELED,
            STATUS_NEEDS_ATTENTION,
            STATUS_RUNNING,
            get_job,
            request_job_cancel,
            transition_job,
        )
        from source_activation_journal_service import (
            PHASE_COMMIT_STARTED,
            PHASE_REPLICA_PUBLISHED,
            PHASE_SOURCE_SELECTION_COMMITTED,
            activation_for_job,
            capture_replica_manifest,
            prepare_activation,
            reconcile_activation,
            transition_activation,
            claim_import_workspace,
            release_import_workspace,
        )

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

        source_path = temp_root / "订单.csv"
        write_csv(source_path, [
            ["订单号", "渠道", "金额", "日期"],
            ["o-1", "线上", "100.50", "2026-05-01"],
            ["o-2", "门店", "200", "2026-05-02"],
            ["o-3", "线上", "", "2026-05-03"],
        ])
        with open_db() as connection:
            preview = build_import_preview(connection, source_path, "orders", None, None)
            plan = bind_single_import_plan(preview, source_path, current_source_run_id=None)

        create_args = argparse.Namespace(
            import_kind="single",
            path=str(source_path),
            request_key="durable-import-order-1",
            expected_plan=plan["planFingerprint"],
            table="orders",
            name="订单",
            mode="create",
            unique_fields="",
            conflict_rule="overwrite",
            no_recursive=False,
            limit=200,
            label="订单导入",
            workspace="default",
        )
        create_dependencies = {
            "open_db": open_db,
            "active_workspace_id": active_workspace_id,
            "build_import_preview": build_import_preview,
            "build_folder_import_plan": build_folder_import_plan,
            "now_iso": now_iso,
        }
        created = import_job_create_command(create_args, **create_dependencies)
        replayed = import_job_create_command(create_args, **create_dependencies)
        job_key = str(created["job"]["jobKey"])
        check(
            checks,
            "request-key-replay-reuses-one-import-job",
            created["job"]["schema"] == "aibi-import-job/v1"
            and created["job"]["status"] == "queued"
            and replayed["replayed"] is True
            and replayed["job"]["jobKey"] == job_key,
            {"created": created, "replayed": replayed},
        )
        public_job_text = json.dumps(created["job"], ensure_ascii=False)
        check(
            checks,
            "public-import-job-redacts-absolute-path",
            str(temp_root) not in public_job_text and created["job"]["input"]["sourceName"] == source_path.name,
            created["job"],
        )
        check(
            checks,
            "public-import-job-hashes-request-key",
            "requestKey" not in created["job"]
            and "requestKey" not in created["job"].get("input", {})
            and created["job"].get("requestKeyFingerprint")
            == hashlib.sha256(create_args.request_key.encode("utf-8")).hexdigest(),
            created["job"],
        )
        conflict_args = argparse.Namespace(**{**vars(create_args), "name": "不同名称"})
        conflict = ""
        try:
            import_job_create_command(conflict_args, **create_dependencies)
        except ValueError as error:
            conflict = str(error)
        check(checks, "request-key-different-input-conflicts", "different job input" in conflict, conflict)

        run_dependencies = {
            "open_db": open_db,
            "active_workspace_id": active_workspace_id,
            "build_import_preview": build_import_preview,
            "build_folder_import_plan": build_folder_import_plan,
            "execute_import_commit": execute_import_commit,
            "execute_folder_import_plan": execute_folder_import_plan,
            "physical_table_for_workspace": physical_table_for_workspace,
            "duckdb_path": duckdb_path,
            "mutation_lock_path": temp_root / ".aibi-cross-engine-writer.lock",
            "recovery_root": temp_root / "workspace-recovery",
            "now_iso": now_iso,
        }
        completed = import_job_run_command(
            argparse.Namespace(job=job_key, workspace="default"),
            **run_dependencies,
        )
        with open_db() as connection:
            persisted = get_job(connection, workspace_id="default", job_key=job_key, event_limit=100)
            current_source_run_id = connection.execute(
                "SELECT current_source_run_id FROM workspaces WHERE id = 'default'"
            ).fetchone()[0]
            journal = activation_for_job(connection, workspace_id="default", job_key=job_key)
            stages = [str(item["stage"]) for item in persisted["events"]]
        check(
            checks,
            "durable-import-publishes-and-switches-once",
            completed["ok"] is True
            and persisted["status"] == "succeeded"
            and persisted["progress"] == 100
            and current_source_run_id == persisted["sourceRunId"]
            and journal is not None
            and journal["phase"] == "finalized"
            and journal["outcome"] == "committed",
            {"job": persisted, "journal": journal, "currentSourceRunId": current_source_run_id},
        )
        check(
            checks,
            "import-job-stages-are-monotonic-and-complete",
            all(stage in stages for stage in ["validate_plan", "stage_source", "publish_replica", "switch_source_run", "postprocess"])
            and [event["progress"] for event in persisted["events"]] == sorted(event["progress"] for event in persisted["events"]),
            stages,
        )
        explicit_target_path = temp_root / "same-schema-new-table.csv"
        write_csv(explicit_target_path, [
            ["订单号", "渠道", "金额", "日期"],
            ["o-4", "门店", "300", "2026-05-04"],
        ])
        performance_calls = {"quality": 0, "merge": 0}
        original_quality = import_command_runtime.analyze_unique_key_quality_parquet_v2
        original_merge = import_command_runtime.preview_merge_plan_parquet_v2

        def counted_quality(*args: Any, **kwargs: Any) -> dict[str, Any]:
            performance_calls["quality"] += 1
            return original_quality(*args, **kwargs)

        def counted_merge(*args: Any, **kwargs: Any) -> dict[str, Any]:
            performance_calls["merge"] += 1
            return original_merge(*args, **kwargs)

        with open_db() as connection:
            connection.execute(
                "UPDATE table_registry SET display_name = '000-orders' "
                "WHERE workspace_id = 'default' AND table_key = 'orders'"
            )
            for index in range(100):
                connection.execute(
                    """
                    INSERT INTO table_registry(
                      table_key, workspace_id, display_name, physical_table, source_file,
                      row_count, column_count, created_at, data_version, updated_at,
                      active_version_id, schema_json, schema_fingerprint, content_fingerprint
                    )
                    SELECT ?, workspace_id, ?, ?, 'complexity-fixture', 0, column_count,
                           created_at, 1, updated_at, '', schema_json, schema_fingerprint,
                           content_fingerprint
                    FROM table_registry
                    WHERE workspace_id = 'default' AND table_key = 'orders'
                    """,
                    (f"same_schema_{index:03d}", f"same-schema-{index:03d}", f"same_schema_{index:03d}"),
                )
            import_command_runtime.analyze_unique_key_quality_parquet_v2 = counted_quality
            import_command_runtime.preview_merge_plan_parquet_v2 = counted_merge
            try:
                explicit_target_preview = build_import_preview(
                    connection,
                    explicit_target_path,
                    "same_schema_new_table",
                    None,
                    None,
                    workspace_id="default",
                    mode_value="create",
                )
                explicit_create_calls = dict(performance_calls)
                performance_calls.update({"quality": 0, "merge": 0})
                auto_target_preview = build_import_preview(
                    connection,
                    explicit_target_path,
                    None,
                    None,
                    None,
                    workspace_id="default",
                    mode_value="auto",
                )
                auto_discovery_calls = dict(performance_calls)
            finally:
                import_command_runtime.analyze_unique_key_quality_parquet_v2 = original_quality
                import_command_runtime.preview_merge_plan_parquet_v2 = original_merge
        check(
            checks,
            "explicit-create-target-does-not-bind-same-schema-table",
            explicit_target_preview["suggestedTableKey"] == "same_schema_new_table"
            and explicit_target_preview["matchedTable"] is None
            and explicit_target_preview["mergePolicyPreview"]["mode"] == "create"
            and explicit_create_calls["merge"] == 0
            and explicit_create_calls["quality"] <= 1,
            {"preview": explicit_target_preview, "calls": explicit_create_calls},
        )
        check(
            checks,
            "auto-discovery-profiles-only-the-selected-target",
            auto_target_preview["matchedTable"]["table_key"] == "orders"
            and len(auto_target_preview["matches"]) == 101
            and auto_discovery_calls == {"quality": 1, "merge": 1},
            {"preview": auto_target_preview, "calls": auto_discovery_calls},
        )
        with open_db() as connection:
            missing_merge_preview = build_import_preview(
                connection,
                explicit_target_path,
                "missing_merge_target",
                None,
                None,
                workspace_id="default",
                mode_value="merge",
            )
            missing_merge_error = ""
            try:
                execute_import_commit(
                    connection,
                    explicit_target_path,
                    "missing_merge_target",
                    "Missing merge target",
                    "merge",
                    workspace_id="default",
                )
            except ValueError as error:
                missing_merge_error = str(error)
            missing_merge_created = connection.execute(
                "SELECT 1 FROM table_registry WHERE workspace_id = 'default' AND table_key = 'missing_merge_target'"
            ).fetchone()
        check(
            checks,
            "explicit-merge-missing-target-is-blocked-before-write",
            missing_merge_preview["readyToCommit"] is False
            and missing_merge_preview["mergePolicyPreview"]["mode"] == "merge"
            and "merge-target-missing" in missing_merge_preview["blockers"]
            and "merge-target-missing" in missing_merge_error
            and missing_merge_created is None,
            {"preview": missing_merge_preview, "error": missing_merge_error},
        )
        injected_path = r"C:\Users\Analyst\private\orders.csv"
        injected_email = "analyst@example.com"
        injected_secret = "Bearer local-super-secret-token"
        with open_db() as connection:
            connection.execute(
                """
                UPDATE analysis_jobs
                SET result_json = ?, error_json = ?, evidence_refs_json = ?
                WHERE workspace_id = 'default' AND job_key = ?
                """,
                (
                    json.dumps({"diagnostic": injected_path, "owner": injected_email}),
                    json.dumps({"message": injected_secret, "token": "raw-token-value"}),
                    json.dumps([{"path": injected_path, "contact": injected_email}]),
                    job_key,
                ),
            )
            connection.execute(
                """
                INSERT INTO analysis_job_events(
                  workspace_id, job_key, event_type, status, progress, stage,
                  message, payload_json, created_at
                ) VALUES('default', ?, 'diagnostic', 'succeeded', 100, 'postprocess', ?, ?, ?)
                """,
                (
                    job_key,
                    f"{injected_path} {injected_email} {injected_secret}",
                    json.dumps({"requestKey": "event-request-key", "password": "event-password"}),
                    now_iso(),
                ),
            )
            connection.commit()
            redacted_job = get_job(connection, workspace_id="default", job_key=job_key, event_limit=100)
        redacted_text = json.dumps(redacted_job, ensure_ascii=False)
        check(
            checks,
            "public-job-dto-redacts-path-email-secret-and-request-key",
            injected_path not in redacted_text
            and injected_email not in redacted_text
            and injected_secret not in redacted_text
            and "raw-token-value" not in redacted_text
            and "event-password" not in redacted_text
            and "event-request-key" not in redacted_text
            and "[local-path]" in redacted_text
            and "[email]" in redacted_text
            and "[redacted]" in redacted_text,
            redacted_job,
        )
        import duckdb  # type: ignore

        def workspace_fingerprint(workspace_id: str, physical_table: str) -> str:
            snapshot: dict[str, Any] = {"workspaceId": workspace_id, "sqlite": {}, "duckdb": {}}
            with open_db() as connection:
                table_names = [
                    str(row[0])
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
                    )
                ]
                for table_name in table_names:
                    columns = [str(row[1]) for row in connection.execute(f'PRAGMA table_info("{table_name}")')]
                    if "workspace_id" not in columns:
                        continue
                    safe_name = table_name.replace('"', '""')
                    rows = [
                        dict(row)
                        for row in connection.execute(
                            f'SELECT * FROM "{safe_name}" WHERE workspace_id = ?',
                            (workspace_id,),
                        )
                    ]
                    snapshot["sqlite"][table_name] = sorted(
                        rows,
                        key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True, default=str),
                    )
            with duckdb.connect(str(duckdb_path), read_only=True) as duck_connection:
                snapshot["duckdb"]["manifest"] = duck_connection.execute(
                    """
                    SELECT logical_table, source_version, version_id,
                           object_hashes_json, schema_fingerprint,
                           content_fingerprint, row_count
                    FROM __aibi_replica_manifest WHERE logical_table = ?
                    """,
                    [physical_table],
                ).fetchall()
                snapshot["duckdb"]["rows"] = duck_connection.execute(
                    f'SELECT * FROM "{physical_table.replace(chr(34), chr(34) * 2)}" ORDER BY ALL'
                ).fetchall()
            canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
            return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

        with duckdb.connect(str(duckdb_path), read_only=True) as duck_connection:
            dataset = duck_connection.execute(
                "SELECT source_version, version_id, row_count FROM __aibi_replica_manifest WHERE logical_table = 'data_orders'"
            ).fetchone()
            dataset_rows = duck_connection.execute("SELECT COUNT(*) FROM data_orders").fetchone()[0]
        check(
            checks,
            "duckdb-versioned-dataset-is-current",
            bool(dataset) and bool(dataset[1]) and int(dataset[2]) == 3 and int(dataset_rows) == 3,
            {"manifest": dataset, "rows": dataset_rows},
        )
        response_lost_replay = import_job_create_command(create_args, **create_dependencies)
        check(
            checks,
            "response-loss-replay-returns-completed-job",
            response_lost_replay["replayed"] is True
            and response_lost_replay["job"]["jobKey"] == job_key
            and response_lost_replay["job"]["status"] == "succeeded",
            response_lost_replay,
        )

        workspace_a = "workspace-a"
        workspace_b = "workspace-b"
        shared_table = "shared_orders"
        source_a = temp_root / "workspace-a-orders.csv"
        source_b = temp_root / "workspace-b-orders.csv"
        write_csv(source_a, [["id", "amount"], ["a-1", "10"], ["a-2", "20"]])
        write_csv(source_b, [["id", "amount"], ["b-1", "99"]])
        with open_db() as connection:
            connection.executemany(
                "INSERT INTO workspaces(id, name, current_source_run_id, created_at) VALUES(?, ?, NULL, ?)",
                [
                    (workspace_a, "Workspace A", now_iso()),
                    (workspace_b, "Workspace B", now_iso()),
                ],
            )
            connection.execute(
                "UPDATE system_flags SET value = ?, updated_at = ? WHERE key = 'active_workspace_id'",
                (workspace_b, now_iso()),
            )
            preview_b = build_import_preview(
                connection,
                source_b,
                shared_table,
                None,
                None,
                workspace_id=workspace_b,
            )
            plan_b = bind_single_import_plan(preview_b, source_b, current_source_run_id=None)
            connection.commit()
        args_b = argparse.Namespace(**{
            **vars(create_args),
            "path": str(source_b),
            "request_key": "durable-import-workspace-b-seed",
            "expected_plan": plan_b["planFingerprint"],
            "table": shared_table,
            "name": "Shared Orders B",
            "mode": plan_b["commitOptions"]["mode"],
            "workspace": workspace_b,
        })
        created_b = import_job_create_command(args_b, **create_dependencies)
        completed_b = import_job_run_command(
            argparse.Namespace(job=created_b["job"]["jobKey"], workspace=workspace_b),
            **run_dependencies,
        )
        with open_db() as connection:
            connection.execute(
                "UPDATE system_flags SET value = ?, updated_at = ? WHERE key = 'active_workspace_id'",
                (workspace_a, now_iso()),
            )
            preview_a = build_import_preview(
                connection,
                source_a,
                shared_table,
                None,
                None,
                workspace_id=workspace_a,
            )
            plan_a = bind_single_import_plan(preview_a, source_a, current_source_run_id=None)
            connection.commit()
        args_a = argparse.Namespace(**{
            **vars(create_args),
            "path": str(source_a),
            "request_key": "durable-import-workspace-a-after-switch",
            "expected_plan": plan_a["planFingerprint"],
            "table": shared_table,
            "name": "Shared Orders A",
            "mode": plan_a["commitOptions"]["mode"],
            "workspace": workspace_a,
        })
        created_a = import_job_create_command(args_a, **create_dependencies)
        with open_db() as connection:
            connection.execute(
                "UPDATE system_flags SET value = ?, updated_at = ? WHERE key = 'active_workspace_id'",
                (workspace_b, now_iso()),
            )
            connection.commit()
        physical_a = physical_table_for_workspace(workspace_a, shared_table)
        physical_b = physical_table_for_workspace(workspace_b, shared_table)
        fingerprint_b_before = workspace_fingerprint(workspace_b, physical_b)
        completed_a = import_job_run_command(
            argparse.Namespace(job=created_a["job"]["jobKey"], workspace=workspace_a),
            **run_dependencies,
        )
        fingerprint_b_after = workspace_fingerprint(workspace_b, physical_b)
        with open_db() as connection:
            active_after_a = active_workspace_id(connection)
            workspace_a_current = connection.execute(
                "SELECT current_source_run_id FROM workspaces WHERE id = ?",
                (workspace_a,),
            ).fetchone()[0]
            workspace_a_registry = connection.execute(
                "SELECT row_count, physical_table FROM table_registry WHERE workspace_id = ? AND table_key = ?",
                (workspace_a, shared_table),
            ).fetchone()
            connection.execute(
                "UPDATE system_flags SET value = 'default', updated_at = ? WHERE key = 'active_workspace_id'",
                (now_iso(),),
            )
            connection.commit()
        with duckdb.connect(str(duckdb_path), read_only=True) as duck_connection:
            workspace_a_manifest = duck_connection.execute(
                "SELECT row_count FROM __aibi_replica_manifest WHERE logical_table = ?",
                [physical_a],
            ).fetchone()
            workspace_a_dataset_rows = duck_connection.execute(
                f'SELECT id, amount FROM "{physical_a}" ORDER BY __aibi_row_id'
            ).fetchall()
        check(
            checks,
            "durable-job-freezes-workspace-across-active-switch",
            completed_b.get("ok") is True
            and completed_a.get("ok") is True
            and completed_a.get("result", {}).get("workspaceId") == workspace_a
            and active_after_a == workspace_b
            and workspace_a_current == completed_a["job"]["sourceRunId"]
            and tuple(workspace_a_registry or ()) == (2, physical_a)
            and [tuple(row) for row in workspace_a_dataset_rows] == [("a-1", 10), ("a-2", 20)]
            and tuple(workspace_a_manifest or ()) == (2,)
            and len(workspace_a_dataset_rows) == 2,
            {
                "workspaceAResult": completed_a,
                "activeWorkspace": active_after_a,
                "workspaceACurrent": workspace_a_current,
                "workspaceARegistry": tuple(workspace_a_registry or ()),
            },
        )
        check(
            checks,
            "active-switch-cannot-mutate-peer-workspace",
            fingerprint_b_before == fingerprint_b_after,
            {"before": fingerprint_b_before, "after": fingerprint_b_after},
        )
        with open_db() as connection:
            current_source = connection.execute(
                "SELECT current_source_run_id FROM workspaces WHERE id = 'default'"
            ).fetchone()[0]
            rollback_manifest = capture_replica_manifest(duckdb_path, ["data_orders"])
            exclusive = prepare_activation(
                connection,
                workspace_id="default",
                job_key="verify-exclusive-one",
                plan_fingerprint="exclusive-one",
                parent_source_run_id=current_source,
                table_keys=["orders"],
                expected_manifest=[],
                rollback_manifest=rollback_manifest,
                now_iso=now_iso,
            )
            competing_error = ""
            try:
                prepare_activation(
                    connection,
                    workspace_id="default",
                    job_key="verify-exclusive-two",
                    plan_fingerprint="exclusive-two",
                    parent_source_run_id=current_source,
                    table_keys=["orders"],
                    expected_manifest=[],
                    rollback_manifest=rollback_manifest,
                    now_iso=now_iso,
                )
            except RuntimeError as error:
                competing_error = str(error)
            prepared_reconcile = reconcile_activation(
                connection,
                journal=exclusive,
                duckdb_path=duckdb_path,
                now_iso=now_iso,
            )
            prepared_reconcile_again = reconcile_activation(
                connection,
                journal=prepared_reconcile["journal"],
                duckdb_path=duckdb_path,
                now_iso=now_iso,
            )
            connection.commit()
        check(
            checks,
            "one-unfinished-activation-per-workspace",
            "unfinished source activation" in competing_error,
            competing_error,
        )
        check(
            checks,
            "prepared-crash-rolls-back-idempotently",
            prepared_reconcile["action"] == "rolled_back"
            and prepared_reconcile["journal"]["outcome"] == "rolled_back"
            and prepared_reconcile_again["action"] == "unchanged",
            {"first": prepared_reconcile, "second": prepared_reconcile_again},
        )

        with open_db() as connection:
            commit_started = prepare_activation(
                connection,
                workspace_id="default",
                job_key="verify-commit-started",
                plan_fingerprint="commit-started",
                parent_source_run_id=current_source,
                table_keys=["orders"],
                expected_manifest=[],
                rollback_manifest=rollback_manifest,
                now_iso=now_iso,
            )
            commit_started = transition_activation(
                connection,
                workspace_id="default",
                journal_key=commit_started["journalKey"],
                phase=PHASE_COMMIT_STARTED,
                now_iso=now_iso,
            )
            connection.commit()
            commit_reconcile = reconcile_activation(
                connection,
                journal=commit_started,
                duckdb_path=duckdb_path,
                now_iso=now_iso,
            )
            connection.commit()
        check(
            checks,
            "commit-started-crash-rolls-back",
            commit_reconcile["action"] == "rolled_back"
            and commit_reconcile["journal"]["phase"] == "finalized",
            commit_reconcile,
        )

        injected_manifest = [{**rollback_manifest[0], "sourceVersion": "verify-injected-version"}]
        with open_db() as connection:
            replica_phase = prepare_activation(
                connection,
                workspace_id="default",
                job_key="verify-replica-published",
                plan_fingerprint="replica-published",
                parent_source_run_id=current_source,
                table_keys=["orders"],
                expected_manifest=injected_manifest,
                rollback_manifest=rollback_manifest,
                now_iso=now_iso,
            )
            replica_phase = transition_activation(
                connection,
                workspace_id="default",
                journal_key=replica_phase["journalKey"],
                phase=PHASE_COMMIT_STARTED,
                now_iso=now_iso,
            )
            connection.commit()
        with duckdb.connect(str(duckdb_path)) as duck_connection:
            duck_connection.execute(
                "UPDATE __aibi_replica_manifest SET source_version = ?, published_at = current_timestamp "
                "WHERE logical_table = 'data_orders'",
                ["verify-injected-version"],
            )
        with open_db() as connection:
            replica_phase = transition_activation(
                connection,
                workspace_id="default",
                journal_key=replica_phase["journalKey"],
                phase=PHASE_REPLICA_PUBLISHED,
                target_source_run_id="source-run-not-selected",
                expected_manifest=injected_manifest,
                now_iso=now_iso,
            )
            connection.commit()
            replica_reconcile = reconcile_activation(
                connection,
                journal=replica_phase,
                duckdb_path=duckdb_path,
                now_iso=now_iso,
            )
            connection.commit()
        with duckdb.connect(str(duckdb_path), read_only=True) as duck_connection:
            restored_manifest = duck_connection.execute(
                "SELECT source_version, version_id, row_count FROM __aibi_replica_manifest WHERE logical_table = 'data_orders'"
            ).fetchone()
        check(
            checks,
            "replica-published-without-source-switch-rolls-back",
            replica_reconcile["action"] == "rolled_back"
            and bool(restored_manifest)
            and str(restored_manifest[0]) == str(rollback_manifest[0]["sourceVersion"])
            and str(restored_manifest[1]) == str(rollback_manifest[0]["versionId"]),
            {"reconcile": replica_reconcile, "manifest": restored_manifest},
        )

        with open_db() as connection:
            committed_phase = prepare_activation(
                connection,
                workspace_id="default",
                job_key="verify-source-selection-committed",
                plan_fingerprint="source-selection-committed",
                parent_source_run_id=current_source,
                table_keys=["orders"],
                expected_manifest=rollback_manifest,
                rollback_manifest=rollback_manifest,
                now_iso=now_iso,
            )
            committed_phase = transition_activation(
                connection,
                workspace_id="default",
                journal_key=committed_phase["journalKey"],
                phase=PHASE_COMMIT_STARTED,
                now_iso=now_iso,
            )
            committed_phase = transition_activation(
                connection,
                workspace_id="default",
                journal_key=committed_phase["journalKey"],
                phase=PHASE_REPLICA_PUBLISHED,
                target_source_run_id=current_source,
                expected_manifest=rollback_manifest,
                now_iso=now_iso,
            )
            committed_phase = transition_activation(
                connection,
                workspace_id="default",
                journal_key=committed_phase["journalKey"],
                phase=PHASE_SOURCE_SELECTION_COMMITTED,
                target_source_run_id=current_source,
                expected_manifest=rollback_manifest,
                now_iso=now_iso,
            )
            connection.commit()
            committed_reconcile = reconcile_activation(
                connection,
                journal=committed_phase,
                duckdb_path=duckdb_path,
                now_iso=now_iso,
            )
            committed_reconcile_again = reconcile_activation(
                connection,
                journal=committed_reconcile["journal"],
                duckdb_path=duckdb_path,
                now_iso=now_iso,
            )
            connection.commit()
        check(
            checks,
            "source-selection-crash-finalizes-committed-idempotently",
            committed_reconcile.get("committed") is True
            and committed_reconcile["journal"]["outcome"] == "committed"
            and committed_reconcile_again["action"] == "unchanged",
            {"first": committed_reconcile, "second": committed_reconcile_again},
        )

        cancel_path = temp_root / "取消.csv"
        write_csv(cancel_path, [["id", "value"], ["1", "cancel-me"]])
        with open_db() as connection:
            cancel_preview = build_import_preview(connection, cancel_path, "cancel_table", None, None)
            parent = connection.execute(
                "SELECT current_source_run_id FROM workspaces WHERE id = 'default'"
            ).fetchone()[0]
            cancel_plan = bind_single_import_plan(cancel_preview, cancel_path, current_source_run_id=parent)
        cancel_args = argparse.Namespace(**{
            **vars(create_args),
            "path": str(cancel_path),
            "request_key": "durable-import-cancel-1",
            "expected_plan": cancel_plan["planFingerprint"],
            "table": "cancel_table",
            "name": "取消表",
        })
        cancel_created = import_job_create_command(cancel_args, **create_dependencies)
        cancel_key = cancel_created["job"]["jobKey"]
        with open_db() as connection:
            canceled = request_job_cancel(
                connection,
                workspace_id="default",
                job_key=cancel_key,
                reason="verify-cancel-before-commit",
                now_iso=now_iso,
            )
            connection.commit()
        unchanged = import_job_run_command(
            argparse.Namespace(job=cancel_key, workspace="default"),
            **run_dependencies,
        )
        with open_db() as connection:
            canceled_table = connection.execute(
                "SELECT 1 FROM table_registry WHERE workspace_id = 'default' AND table_key = 'cancel_table'"
            ).fetchone()
        check(
            checks,
            "cancel-before-commit-does-not-write",
            canceled["status"] == STATUS_CANCELED
            and unchanged["changed"] is False
            and canceled_table is None,
            {"job": canceled, "table": canceled_table},
        )

        file_drift_path = temp_root / "文件漂移.csv"
        write_csv(file_drift_path, [["id", "staged_value"], ["1", "before"]])
        with open_db() as connection:
            file_drift_preview = build_import_preview(connection, file_drift_path, "file_drift_table", None, None)
            parent = connection.execute(
                "SELECT current_source_run_id FROM workspaces WHERE id = 'default'"
            ).fetchone()[0]
            file_drift_plan = bind_single_import_plan(
                file_drift_preview,
                file_drift_path,
                current_source_run_id=parent,
            )
        file_drift_args = argparse.Namespace(**{
            **vars(create_args),
            "path": str(file_drift_path),
            "request_key": "durable-import-file-drift-1",
            "expected_plan": file_drift_plan["planFingerprint"],
            "table": "file_drift_table",
            "name": "文件漂移",
        })
        file_drift_created = import_job_create_command(file_drift_args, **create_dependencies)
        write_csv(file_drift_path, [["id", "staged_value"], ["1", "after"]])
        file_drift_result = import_job_run_command(
            argparse.Namespace(job=file_drift_created["job"]["jobKey"], workspace="default"),
            **run_dependencies,
        )
        with open_db() as connection:
            file_drift_table = connection.execute(
                "SELECT physical_table FROM table_registry WHERE workspace_id = 'default' AND table_key = 'file_drift_table'"
            ).fetchone()
        staged_value = None
        if file_drift_table is not None:
            with duckdb.connect(str(duckdb_path), read_only=True) as duck_connection:
                staged_value = duck_connection.execute(
                    f'SELECT staged_value FROM "{str(file_drift_table[0]).replace(chr(34), chr(34) * 2)}" WHERE id = ?',
                    ["1"],
                ).fetchone()
        check(
            checks,
            "accepted-stage-is-immutable-after-source-drift",
            file_drift_result["job"]["status"] == "succeeded"
            and file_drift_table is not None
            and staged_value is not None
            and staged_value[0] == "before",
            {"result": file_drift_result, "value": staged_value[0] if staged_value else None},
        )

        parent_drift_path = temp_root / "父版本漂移.csv"
        write_csv(parent_drift_path, [["id", "parent_only"], ["1", "parent"]])
        with open_db() as connection:
            parent_drift_preview = build_import_preview(
                connection,
                parent_drift_path,
                "parent_drift_table",
                None,
                None,
                mode_value="create",
            )
            parent_before_drift = connection.execute(
                "SELECT current_source_run_id FROM workspaces WHERE id = 'default'"
            ).fetchone()[0]
            parent_drift_plan = bind_single_import_plan(
                parent_drift_preview,
                parent_drift_path,
                current_source_run_id=parent_before_drift,
            )
        parent_drift_args = argparse.Namespace(**{
            **vars(create_args),
            "path": str(parent_drift_path),
            "request_key": "durable-import-parent-drift-1",
            "expected_plan": parent_drift_plan["planFingerprint"],
            "table": "parent_drift_table",
            "name": "父版本漂移",
        })
        parent_drift_created = import_job_create_command(parent_drift_args, **create_dependencies)
        with open_db() as connection:
            connection.execute(
                "UPDATE workspaces SET current_source_run_id = NULL WHERE id = 'default'"
            )
            connection.commit()
        parent_drift_result = import_job_run_command(
            argparse.Namespace(job=parent_drift_created["job"]["jobKey"], workspace="default"),
            **run_dependencies,
        )
        with open_db() as connection:
            parent_drift_table = connection.execute(
                "SELECT 1 FROM table_registry WHERE workspace_id = 'default' AND table_key = 'parent_drift_table'"
            ).fetchone()
            connection.execute(
                "UPDATE workspaces SET current_source_run_id = ? WHERE id = 'default'",
                (parent_before_drift,),
            )
            connection.commit()
        check(
            checks,
            "parent-version-drift-fails-before-business-write",
            parent_drift_result["job"]["status"] == "failed"
            and parent_drift_table is None
            and parent_drift_result["job"].get("error", {}).get("code") == "import-job-failed"
            and parent_drift_result["job"].get("error", {}).get("recoveryAction") == "re-preview",
            {"result": parent_drift_result, "table": parent_drift_table},
        )

        publish_failure_path = temp_root / "发布失败.csv"
        write_csv(publish_failure_path, [["id", "value"], ["1", "rollback"]])
        with open_db() as connection:
            publish_failure_preview = build_import_preview(connection, publish_failure_path, "publish_failure_table", None, None)
            parent_before_failure = connection.execute(
                "SELECT current_source_run_id FROM workspaces WHERE id = 'default'"
            ).fetchone()[0]
            publish_failure_plan = bind_single_import_plan(
                publish_failure_preview,
                publish_failure_path,
                current_source_run_id=parent_before_failure,
            )
        publish_failure_args = argparse.Namespace(**{
            **vars(create_args),
            "path": str(publish_failure_path),
            "request_key": "durable-import-publish-failure-1",
            "expected_plan": publish_failure_plan["planFingerprint"],
            "table": "publish_failure_table",
            "name": "发布失败",
        })
        publish_failure_created = import_job_create_command(publish_failure_args, **create_dependencies)
        original_publish = import_job_runtime._publish_current_replicas

        def fail_replica_publish(*_args, **_kwargs):
            raise RuntimeError("injected-duckdb-publication-failure")

        import_job_runtime._publish_current_replicas = fail_replica_publish
        try:
            publish_failure_result = import_job_run_command(
                argparse.Namespace(job=publish_failure_created["job"]["jobKey"], workspace="default"),
                **run_dependencies,
            )
        finally:
            import_job_runtime._publish_current_replicas = original_publish
        with open_db() as connection:
            publish_failure_table = connection.execute(
                "SELECT 1 FROM table_registry WHERE workspace_id = 'default' AND table_key = 'publish_failure_table'"
            ).fetchone()
            current_after_failure = connection.execute(
                "SELECT current_source_run_id FROM workspaces WHERE id = 'default'"
            ).fetchone()[0]
            publish_failure_journal = activation_for_job(
                connection,
                workspace_id="default",
                job_key=publish_failure_created["job"]["jobKey"],
            )
        check(
            checks,
            "duckdb-publication-failure-rolls-back-sqlite-and-journal",
            publish_failure_result["job"]["status"] == "failed"
            and publish_failure_table is None
            and current_after_failure == parent_before_failure
            and publish_failure_journal is not None
            and publish_failure_journal["outcome"] == "rolled_back",
            {
                "result": publish_failure_result,
                "table": publish_failure_table,
                "current": current_after_failure,
                "journal": publish_failure_journal,
            },
        )

        cleanup_warning_path = temp_root / "后处理告警.csv"
        write_csv(cleanup_warning_path, [["id", "value"], ["1", "committed"]])
        with open_db() as connection:
            cleanup_warning_preview = build_import_preview(connection, cleanup_warning_path, "cleanup_warning_table", None, None)
            cleanup_parent = connection.execute(
                "SELECT current_source_run_id FROM workspaces WHERE id = 'default'"
            ).fetchone()[0]
            cleanup_warning_plan = bind_single_import_plan(
                cleanup_warning_preview,
                cleanup_warning_path,
                current_source_run_id=cleanup_parent,
            )
        cleanup_warning_args = argparse.Namespace(**{
            **vars(create_args),
            "path": str(cleanup_warning_path),
            "request_key": "durable-import-cleanup-warning-1",
            "expected_plan": cleanup_warning_plan["planFingerprint"],
            "table": "cleanup_warning_table",
            "name": "后处理告警",
        })
        cleanup_warning_created = import_job_create_command(cleanup_warning_args, **create_dependencies)
        original_cleanup = import_job_runtime.cleanup_stale_replicas

        def fail_cleanup(*_args, **_kwargs):
            raise RuntimeError("injected-postprocess-cleanup-failure")

        import_job_runtime.cleanup_stale_replicas = fail_cleanup
        try:
            cleanup_warning_result = import_job_run_command(
                argparse.Namespace(job=cleanup_warning_created["job"]["jobKey"], workspace="default"),
                **run_dependencies,
            )
        finally:
            import_job_runtime.cleanup_stale_replicas = original_cleanup
        with open_db() as connection:
            cleanup_warning_journal = activation_for_job(
                connection,
                workspace_id="default",
                job_key=cleanup_warning_created["job"]["jobKey"],
            )
        check(
            checks,
            "postprocess-cleanup-failure-preserves-committed-success",
            cleanup_warning_result["job"]["status"] == "succeeded"
            and cleanup_warning_result["warning"]["code"] == "activation-cleanup-deferred"
            and cleanup_warning_journal is not None
            and cleanup_warning_journal["outcome"] == "committed",
            {"result": cleanup_warning_result, "journal": cleanup_warning_journal},
        )

        resume_path = temp_root / "恢复.csv"
        write_csv(resume_path, [["id", "value"], ["1", "resume-me"]])
        with open_db() as connection:
            resume_preview = build_import_preview(connection, resume_path, "resume_table", None, None)
            parent = connection.execute(
                "SELECT current_source_run_id FROM workspaces WHERE id = 'default'"
            ).fetchone()[0]
            resume_plan = bind_single_import_plan(resume_preview, resume_path, current_source_run_id=parent)
        resume_args = argparse.Namespace(**{
            **vars(create_args),
            "path": str(resume_path),
            "request_key": "durable-import-resume-1",
            "expected_plan": resume_plan["planFingerprint"],
            "table": "resume_table",
            "name": "恢复表",
            "mode": resume_plan["commitOptions"]["mode"],
        })
        resume_created = import_job_create_command(resume_args, **create_dependencies)
        resume_key = resume_created["job"]["jobKey"]
        with open_db() as connection:
            transition_job(
                connection,
                workspace_id="default",
                job_key=resume_key,
                status=STATUS_RUNNING,
                progress=5,
                stage="validate_plan",
                now_iso=now_iso,
            )
            recovered = recover_import_jobs(
                connection,
                workspace_id="default",
                duckdb_path=duckdb_path,
                now_iso=now_iso,
            )
            recovered_job = get_job(connection, workspace_id="default", job_key=resume_key)
            connection.commit()
        resumed = import_job_resume_command(
            argparse.Namespace(job=resume_key, workspace="default"),
            open_db=open_db,
            active_workspace_id=active_workspace_id,
            build_import_preview=build_import_preview,
            build_folder_import_plan=build_folder_import_plan,
            now_iso=now_iso,
        )
        check(
            checks,
            "runtime-restart-requires-explicit-current-resume",
            any(item["jobKey"] == resume_key for item in recovered)
            and recovered_job["status"] == STATUS_NEEDS_ATTENTION
            and resumed["job"]["status"] == "queued",
            {"recovered": recovered_job, "resumed": resumed},
        )

        # A stale child exit must not revoke or reconcile the same job after a
        # newer worker token has taken ownership.
        token_a = "worker-token-a-0000000000000001"
        token_b = "worker-token-b-0000000000000002"
        with open_db() as connection:
            connection.execute("BEGIN IMMEDIATE")
            epoch_a = claim_import_workspace(
                connection,
                workspace_id="default",
                job_key=resume_key,
                lease_token=token_a,
                now_iso=now_iso,
            )
            release_import_workspace(
                connection,
                workspace_id="default",
                job_key=resume_key,
                lease_token=token_a,
                lease_epoch=int(epoch_a or 0),
                now_iso=now_iso,
            )
            epoch_b = claim_import_workspace(
                connection,
                workspace_id="default",
                job_key=resume_key,
                lease_token=token_b,
                now_iso=now_iso,
            )
            before_late_exit = get_job(connection, workspace_id="default", job_key=resume_key, event_limit=200)
            connection.commit()
        late_exit = import_job_process_exit_command(
            argparse.Namespace(job=resume_key, workspace="default", lease_token=token_a),
            open_db=open_db,
            active_workspace_id=active_workspace_id,
            duckdb_path=duckdb_path,
            now_iso=now_iso,
        )
        with open_db() as connection:
            active_owner = connection.execute(
                "SELECT lease_token, lease_epoch, active FROM import_workspace_leases WHERE workspace_id = 'default'"
            ).fetchone()
            after_late_exit = get_job(connection, workspace_id="default", job_key=resume_key, event_limit=200)
        check(
            checks,
            "late-worker-exit-cannot-reconcile-newer-lease",
            epoch_b is not None
            and late_exit["leaseRevoked"] is False
            and late_exit["leaseMatched"] is False
            and late_exit["changed"] is False
            and late_exit["safeToDrain"] is False
            and tuple(active_owner or ()) == (token_b, epoch_b, 1)
            and before_late_exit == after_late_exit,
            {"lateExit": late_exit, "activeOwner": tuple(active_owner or ())},
        )
        with open_db() as connection:
            release_import_workspace(
                connection,
                workspace_id="default",
                job_key=resume_key,
                lease_token=token_b,
                lease_epoch=int(epoch_b or 0),
                now_iso=now_iso,
            )
            connection.commit()
        current_exit = import_job_process_exit_command(
            argparse.Namespace(job=resume_key, workspace="default", lease_token=token_b),
            open_db=open_db,
            active_workspace_id=active_workspace_id,
            duckdb_path=duckdb_path,
            now_iso=now_iso,
        )
        check(
            checks,
            "released-current-worker-exit-still-reconciles",
            current_exit["leaseMatched"] is True
            and current_exit["job"]["status"] == STATUS_NEEDS_ATTENTION
            and current_exit["safeToDrain"] is False,
            current_exit,
        )

    failed = [item for item in checks if not item["ok"]]
    print(json.dumps({
        "schema": "aibi-durable-import-runtime-verify/v1",
        "ok": not failed,
        "checks": checks,
        "summary": {"passed": len(checks) - len(failed), "failed": len(failed), "total": len(checks)},
    }, ensure_ascii=False, indent=2, default=str))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
