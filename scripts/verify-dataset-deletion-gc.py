from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import duckdb  # type: ignore  # noqa: E402

from bi_cli_schema import initialize_schema  # noqa: E402
from dataset_version_store import (  # noqa: E402
    assert_dataset_version_schema,
    collect_unreferenced_dataset_objects,
    dataset_object_candidates,
    delete_dataset_versions,
    object_key_for,
    resolve_object_key,
)
from source_activation_journal_service import (  # noqa: E402
    PHASE_COMMIT_STARTED,
    PHASE_REPLICA_PUBLISHED,
    capture_replica_manifest,
    prepare_activation,
    reconcile_activation,
    replica_manifest_matches,
    restore_replica_manifest,
    transition_activation,
)
import source_management_command_service  # noqa: E402
from workspace_recovery_service import _workspace_bucket  # noqa: E402


def put_object(root: Path, workspace_id: str, payload: bytes) -> dict[str, str]:
    payload_text = payload.decode("ascii")
    stage = root.parent / f"{payload_text}.stage.parquet"
    with duckdb.connect(":memory:") as writer:
        stage_sql = "'" + str(stage).replace("'", "''") + "'"
        payload_sql = "'" + payload_text.replace("'", "''") + "'"
        writer.execute(
            f"COPY (SELECT 1::BIGINT AS __aibi_row_id, {payload_sql}::VARCHAR AS value) TO {stage_sql} (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
    payload = stage.read_bytes()
    object_hash = hashlib.sha256(payload).hexdigest()
    object_key = object_key_for(workspace_id, object_hash)
    path = resolve_object_key(object_key, root=root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {"objectKey": object_key, "objectHash": object_hash}


def add_version(
    connection: sqlite3.Connection,
    *,
    version_id: str,
    workspace_id: str,
    table_key: str,
    object_ref: dict[str, str],
) -> None:
    connection.execute(
        "INSERT INTO dataset_versions VALUES(?, ?, ?, 1, 1, '[]', ?, ?, '', '2026-01-01T00:00:00Z')",
        (version_id, workspace_id, table_key, "s" * 64, version_id),
    )
    path = resolve_object_key(object_ref["objectKey"])
    connection.execute(
        "INSERT INTO dataset_version_files VALUES(?, 0, ?, ?, 1, ?)",
        (version_id, object_ref["objectKey"], object_ref["objectHash"], path.stat().st_size),
    )


with tempfile.TemporaryDirectory(prefix="aibi-dataset-delete-gc-") as directory:
    temp_root = Path(directory)
    object_root = temp_root / "objects"
    os.environ["AIBI_DATASET_OBJECT_ROOT"] = str(object_root)
    catalog = temp_root / "catalog.duckdb"
    with duckdb.connect(str(catalog)) as writer:
        writer.execute("CREATE TABLE __aibi_schema_metadata(key VARCHAR PRIMARY KEY, value VARCHAR NOT NULL)")
        writer.execute("INSERT INTO __aibi_schema_metadata VALUES ('schema_version', '2')")

    control = sqlite3.connect(":memory:")
    control.row_factory = sqlite3.Row
    initialize_schema(control)
    assert_dataset_version_schema(control)
    target_only = put_object(object_root, "workspace", b"target-only")
    shared = put_object(object_root, "workspace", b"shared")
    manifest_only = put_object(object_root, "workspace", b"manifest-only")
    add_version(control, version_id="version_" + "1" * 24, workspace_id="workspace", table_key="target", object_ref=target_only)
    add_version(control, version_id="version_" + "2" * 24, workspace_id="workspace", table_key="target", object_ref=shared)
    add_version(control, version_id="version_" + "3" * 24, workspace_id="workspace", table_key="other", object_ref=shared)
    control.commit()

    restore_replica_manifest(catalog, [{
        "logicalTable": "target_view",
        "present": True,
        "sourceVersion": "workspace:target:1:1",
        "versionId": "version_" + "1" * 24,
        "objectKeys": [target_only["objectKey"]],
        "objectHashes": [target_only["objectHash"]],
        "schemaFingerprint": "s" * 64,
        "contentFingerprint": "c" * 64,
        "rowCount": 1,
    }])
    rollback = capture_replica_manifest(catalog, ["target_view"])
    assert rollback[0]["present"] is True
    absent = [{"logicalTable": "target_view", "present": False}]
    restore_replica_manifest(catalog, absent)
    assert replica_manifest_matches(catalog, absent)

    candidates = dataset_object_candidates(control, workspace_id="workspace", table_keys=["target"])
    deleted = delete_dataset_versions(control, workspace_id="workspace", table_keys=["target"])
    control.commit()
    assert deleted == {"dataset_version_files": 2, "dataset_versions": 2}
    gc_result = collect_unreferenced_dataset_objects(
        control,
        candidates=candidates,
        duckdb_paths=[catalog],
        root=object_root,
    )
    assert gc_result["deletedCount"] == 1 and gc_result["retainedCount"] == 1
    assert not resolve_object_key(target_only["objectKey"], root=object_root).exists()
    assert resolve_object_key(shared["objectKey"], root=object_root).is_file()

    restore_replica_manifest(catalog, [{
        "logicalTable": "manifest_only_view",
        "present": True,
        "sourceVersion": "workspace:manifest-only:1:1",
        "versionId": "version_" + "4" * 24,
        "objectKeys": [manifest_only["objectKey"]],
        "objectHashes": [manifest_only["objectHash"]],
        "schemaFingerprint": "s" * 64,
        "contentFingerprint": "d" * 64,
        "rowCount": 1,
    }])
    retained = collect_unreferenced_dataset_objects(
        control,
        candidates=[manifest_only],
        duckdb_paths=[catalog],
        root=object_root,
    )
    assert retained["deletedCount"] == 0 and retained["retainedCount"] == 1
    restore_replica_manifest(catalog, [{"logicalTable": "manifest_only_view", "present": False}])
    collected = collect_unreferenced_dataset_objects(
        control,
        candidates=[manifest_only],
        duckdb_paths=[catalog],
        root=object_root,
    )
    assert collected["deletedCount"] == 1

    transient = put_object(object_root, "workspace", b"transient-unlink")
    transient_path = resolve_object_key(transient["objectKey"], root=object_root)
    real_unlink = Path.unlink
    unlink_attempts = [0]

    def transient_unlink(path: Path, missing_ok: bool = False) -> None:
        if path == transient_path and unlink_attempts[0] < 2:
            unlink_attempts[0] += 1
            error = PermissionError(13, "Parquet reader still owns the file")
            error.winerror = 32
            raise error
        if path == transient_path:
            unlink_attempts[0] += 1
        real_unlink(path, missing_ok=missing_ok)

    with patch.object(Path, "unlink", transient_unlink):
        transient_gc = collect_unreferenced_dataset_objects(
            control,
            candidates=[transient],
            duckdb_paths=[catalog],
            root=object_root,
        )
    assert transient_gc["deletedCount"] == 1 and unlink_attempts[0] == 3
    assert not transient_path.exists()

    source_catalog = temp_root / "source-delete.duckdb"
    with duckdb.connect(str(source_catalog)) as writer:
        writer.execute("CREATE TABLE __aibi_schema_metadata(key VARCHAR PRIMARY KEY, value VARCHAR NOT NULL)")
        writer.execute("INSERT INTO __aibi_schema_metadata VALUES ('schema_version', '2')")
    source_object = put_object(object_root, "workspace", b"source-delete")
    source_control = sqlite3.connect(":memory:")
    source_control.row_factory = sqlite3.Row
    initialize_schema(source_control)
    source_control.execute(
        "INSERT INTO workspaces(id, name, current_source_run_id, created_at) VALUES(?, ?, ?, ?)",
        ("workspace", "Workspace", "run-target", "2026-01-01T00:00:00Z"),
    )
    source_control.execute(
        """
        INSERT INTO table_registry(
          workspace_id, table_key, display_name, physical_table, source_file,
          row_count, column_count, created_at, data_version, updated_at,
          active_version_id, schema_json, schema_fingerprint, content_fingerprint
        ) VALUES(?, ?, ?, ?, ?, 1, 1, ?, 1, ?, ?, '[]', ?, ?)
        """,
        (
            "workspace",
            "target",
            "Target",
            "target_view",
            "target.csv",
            "2026-01-01T00:00:00Z",
            "2026-01-01T00:00:00Z",
            "version_" + "a" * 24,
            "s" * 64,
            "c" * 64,
        ),
    )
    source_control.execute(
        """
        INSERT INTO source_runs(
          id, workspace_id, table_key, name, status, source_file, row_count,
          column_count, profile_json, evidence_json, created_at
        ) VALUES(?, ?, ?, ?, 'active', ?, 1, 1, '{}', '[]', ?)
        """,
        ("run-target", "workspace", "target", "Target", "target.csv", "2026-01-01T00:00:00Z"),
    )
    assert_dataset_version_schema(source_control)
    add_version(
        source_control,
        version_id="version_" + "a" * 24,
        workspace_id="workspace",
        table_key="target",
        object_ref=source_object,
    )
    source_control.commit()
    source_live_snapshot = {
        "logicalTable": "target_view",
        "present": True,
        "sourceVersion": "workspace:target:1:1",
        "versionId": "version_" + "a" * 24,
        "objectKeys": [source_object["objectKey"]],
        "objectHashes": [source_object["objectHash"]],
        "schemaFingerprint": "s" * 64,
        "contentFingerprint": "c" * 64,
        "rowCount": 1,
    }
    restore_replica_manifest(source_catalog, [source_live_snapshot])
    recovery_root = temp_root / "workspace-recovery"
    persisted_point = (
        recovery_root
        / _workspace_bucket("workspace")
        / ("rp_" + "2" * 24)
    )
    persisted_point.mkdir(parents=True)
    shutil.copy2(source_catalog, persisted_point / "analytics.duckdb")
    os.environ["AIBI_WORKSPACE_RECOVERY_ROOT"] = str(recovery_root)
    source_management_command_service.DUCKDB_PATH = source_catalog

    def source_plan(_connection, registry):
        return {
            "source": {"tableKey": registry["table_key"]},
            "impact": {},
            "affectedWidgets": [],
            "affectedDashboards": [],
            "affectedRelationshipKeys": [],
            "affectedConnectors": [],
            "nextDefaultTableKey": "",
        }

    try:
        source_management_command_service.delete_source_command(
            type("Args", (), {"source": "target", "yes": True, "fail_at": "after_replica_published"})(),
            open_db=lambda: source_control,
            active_workspace_id=lambda _connection: "workspace",
            resolve_table_registry=lambda connection, _source: connection.execute(
                "SELECT * FROM table_registry WHERE workspace_id = 'workspace' AND table_key = 'target'"
            ).fetchone(),
            build_delete_source_plan=source_plan,
        )
    except RuntimeError as error:
        assert "Injected source delete interruption" in str(error)
    else:
        raise AssertionError("Source delete failure injection must interrupt the command")
    assert source_control.execute("SELECT COUNT(*) FROM table_registry").fetchone()[0] == 1
    assert replica_manifest_matches(source_catalog, [source_live_snapshot])
    assert source_control.execute(
        "SELECT COUNT(*) FROM source_activation_journals WHERE phase <> 'finalized'"
    ).fetchone()[0] == 0
    source_control.execute(
        "UPDATE table_registry SET content_fingerprint = ? WHERE workspace_id = 'workspace' AND table_key = 'target'",
        ("d" * 64,),
    )
    source_control.commit()

    result = source_management_command_service.delete_source_command(
        type("Args", (), {"source": "target", "yes": True})(),
        open_db=lambda: source_control,
        active_workspace_id=lambda _connection: "workspace",
        resolve_table_registry=lambda connection, _source: connection.execute(
            "SELECT * FROM table_registry WHERE workspace_id = 'workspace' AND table_key = 'target'"
        ).fetchone(),
        build_delete_source_plan=source_plan,
    )
    assert result["datasetObjectGc"]["deletedCount"] == 0
    assert result["datasetObjectGc"]["retainedCount"] == 1
    assert source_control.execute("SELECT COUNT(*) FROM table_registry").fetchone()[0] == 0
    assert source_control.execute("SELECT COUNT(*) FROM dataset_versions").fetchone()[0] == 0
    assert source_control.execute(
        "SELECT COUNT(*) FROM source_activation_journals WHERE phase <> 'finalized'"
    ).fetchone()[0] == 0
    assert replica_manifest_matches(source_catalog, [{"logicalTable": "target_view", "present": False}])
    assert resolve_object_key(source_object["objectKey"], root=object_root).is_file()
    shutil.rmtree(recovery_root)
    final_source_gc = collect_unreferenced_dataset_objects(
        source_control,
        candidates=[source_object],
        duckdb_paths=[source_catalog],
        root=object_root,
    )
    assert final_source_gc["deletedCount"] == 1
    assert not resolve_object_key(source_object["objectKey"], root=object_root).exists()
    source_control.close()

    recovery_catalog = temp_root / "source-delete-recovery.duckdb"
    with duckdb.connect(str(recovery_catalog)) as writer:
        writer.execute("CREATE TABLE __aibi_schema_metadata(key VARCHAR PRIMARY KEY, value VARCHAR NOT NULL)")
        writer.execute("INSERT INTO __aibi_schema_metadata VALUES ('schema_version', '2')")
    recovery_object = put_object(object_root, "recovery-workspace", b"delete-recovery")
    recovery_control = sqlite3.connect(":memory:")
    recovery_control.row_factory = sqlite3.Row
    initialize_schema(recovery_control)
    recovery_control.execute(
        "INSERT INTO workspaces(id, name, current_source_run_id, created_at) VALUES(?, ?, ?, ?)",
        ("recovery-workspace", "Recovery Workspace", "run-1", "2026-01-01T00:00:00Z"),
    )
    recovery_control.execute(
        """
        INSERT INTO table_registry(
          workspace_id, table_key, display_name, physical_table, source_file,
          row_count, column_count, created_at, data_version, updated_at,
          active_version_id, schema_json, schema_fingerprint, content_fingerprint
        ) VALUES(?, ?, ?, ?, '', 1, 1, ?, 1, ?, ?, '[]', ?, ?)
        """,
        (
            "recovery-workspace",
            "target",
            "Target",
            "recovery_view",
            "2026-01-01T00:00:00Z",
            "2026-01-01T00:00:00Z",
            "version_" + "b" * 24,
            "s" * 64,
            "e" * 64,
        ),
    )
    assert_dataset_version_schema(recovery_control)
    add_version(
        recovery_control,
        version_id="version_" + "b" * 24,
        workspace_id="recovery-workspace",
        table_key="target",
        object_ref=recovery_object,
    )
    recovery_control.commit()
    live_snapshot = {
        "logicalTable": "recovery_view",
        "present": True,
        "sourceVersion": "recovery-workspace:target:1:1",
        "versionId": "version_" + "b" * 24,
        "objectKeys": [recovery_object["objectKey"]],
        "objectHashes": [recovery_object["objectHash"]],
        "schemaFingerprint": "s" * 64,
        "contentFingerprint": "e" * 64,
        "rowCount": 1,
    }
    restore_replica_manifest(recovery_catalog, [live_snapshot])
    absent_with_gc = [{
        "logicalTable": "recovery_view",
        "present": False,
        "gcCandidates": [recovery_object],
    }]
    recovery_journal = prepare_activation(
        recovery_control,
        workspace_id="recovery-workspace",
        job_key="source-delete-v2:rollback-test",
        plan_fingerprint="f" * 64,
        parent_source_run_id="run-1",
        table_keys=["target"],
        expected_manifest=absent_with_gc,
        rollback_manifest=[live_snapshot],
        now_iso=lambda: "2026-01-01T00:00:00Z",
    )
    recovery_control.commit()
    transition_activation(
        recovery_control,
        workspace_id="recovery-workspace",
        journal_key=recovery_journal["journalKey"],
        phase=PHASE_COMMIT_STARTED,
        now_iso=lambda: "2026-01-01T00:00:01Z",
    )
    recovery_control.commit()
    restore_replica_manifest(recovery_catalog, absent_with_gc)
    rolled_back = reconcile_activation(
        recovery_control,
        journal=recovery_journal | {"phase": PHASE_COMMIT_STARTED},
        duckdb_path=recovery_catalog,
        now_iso=lambda: "2026-01-01T00:00:02Z",
    )
    recovery_control.commit()
    assert rolled_back["action"] == "rolled_back"
    assert replica_manifest_matches(recovery_catalog, [live_snapshot])
    assert resolve_object_key(recovery_object["objectKey"], root=object_root).is_file()
    crash_recovery_point = recovery_root / _workspace_bucket("recovery-workspace") / ("rp_" + "4" * 24)
    crash_recovery_point.mkdir(parents=True)
    shutil.copy2(recovery_catalog, crash_recovery_point / "analytics.duckdb")

    committed_journal = prepare_activation(
        recovery_control,
        workspace_id="recovery-workspace",
        job_key="source-delete-v2:commit-test",
        plan_fingerprint="a" * 64,
        parent_source_run_id="run-1",
        table_keys=["target"],
        expected_manifest=absent_with_gc,
        rollback_manifest=[live_snapshot],
        now_iso=lambda: "2026-01-01T00:00:03Z",
    )
    recovery_control.commit()
    committed_journal = transition_activation(
        recovery_control,
        workspace_id="recovery-workspace",
        journal_key=committed_journal["journalKey"],
        phase=PHASE_COMMIT_STARTED,
        now_iso=lambda: "2026-01-01T00:00:04Z",
    )
    recovery_control.commit()
    restore_replica_manifest(recovery_catalog, absent_with_gc)
    committed_journal = transition_activation(
        recovery_control,
        workspace_id="recovery-workspace",
        journal_key=committed_journal["journalKey"],
        phase=PHASE_REPLICA_PUBLISHED,
        expected_manifest=absent_with_gc,
        now_iso=lambda: "2026-01-01T00:00:05Z",
    )
    recovery_control.execute("DELETE FROM table_registry WHERE workspace_id = 'recovery-workspace'")
    delete_dataset_versions(recovery_control, workspace_id="recovery-workspace", table_keys=["target"])
    recovery_control.commit()
    finalized = reconcile_activation(
        recovery_control,
        journal=committed_journal,
        duckdb_path=recovery_catalog,
        now_iso=lambda: "2026-01-01T00:00:06Z",
    )
    recovery_control.commit()
    assert finalized["action"] == "finalized" and finalized["datasetObjectGc"]["retainedCount"] == 1
    assert resolve_object_key(recovery_object["objectKey"], root=object_root).is_file()
    shutil.rmtree(recovery_root)
    recovered_gc = collect_unreferenced_dataset_objects(
        recovery_control,
        candidates=[recovery_object],
        duckdb_paths=[recovery_catalog],
        root=object_root,
    )
    assert recovered_gc["deletedCount"] == 1
    assert not resolve_object_key(recovery_object["objectKey"], root=object_root).exists()
    recovery_control.close()

    source_code = (ROOT / "tools" / "source_management_command_service.py").read_text(encoding="utf-8")
    workspace_code = (ROOT / "tools" / "workspace_command_service.py").read_text(encoding="utf-8")
    assert "DROP TABLE IF EXISTS {quote_identifier(registry['physical_table'])}" not in source_code
    assert "DROP TABLE IF EXISTS {quote_identifier(physical_table)}" not in workspace_code
    control.close()

print(json.dumps({"ok": True, "checks": 23}, ensure_ascii=False))
