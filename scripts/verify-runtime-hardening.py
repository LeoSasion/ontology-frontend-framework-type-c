from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any

import duckdb


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from bi_cli_evidence_bundles import artifact_ref, write_evidence_bundle

CHECKS: list[dict[str, Any]] = []


def check(label: str, ok: bool, detail: Any = None) -> None:
    CHECKS.append({"label": label, "ok": bool(ok), "detail": None if ok else detail})


def cli(env: dict[str, str], *args: str, expected: int = 0) -> dict[str, Any]:
    completed = subprocess.run(
        ["python", "tools/aibi_cli.py", "--json", *args],
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {"ok": False, "stdout": completed.stdout, "stderr": completed.stderr}
    payload["processExitCode"] = completed.returncode
    check(f"cli-{'-'.join(args[:2])}", completed.returncode == expected, payload)
    return payload


with tempfile.TemporaryDirectory(prefix="aibi-runtime-hardening-") as temp_name:
    temp = Path(temp_name)
    source = temp / "orders.csv"
    shutil.copy2(ROOT / "validation-inputs" / "orders.csv", source)
    db_path = temp / "runtime.sqlite"
    duck_path = temp / "runtime.duckdb"
    env = {
        **os.environ,
        "AIBI_HYBRID_DB_PATH": str(db_path),
        "AIBI_HYBRID_DUCKDB_PATH": str(duck_path),
        "AIBI_EVIDENCE_BUNDLE_ROOT": str(temp / "evidence"),
        "PYTHONIOENCODING": "utf-8",
    }

    created_workspace = cli(env, "workspace-create", "--name", "Runtime hardening", "--yes")
    workspace_id = str((created_workspace.get("created") or {}).get("id") or "")
    check("runtime-hardening-workspace-created", bool(workspace_id), created_workspace)

    preview = cli(env, "preview-import", str(source))
    plan = str(preview.get("planFingerprint") or "")
    options = preview.get("commitOptions") if isinstance(preview.get("commitOptions"), dict) else {}
    check(
        "single-file-preview-is-version-bound",
        len(plan) == 64
        and len(str(preview.get("contentHash") or "")) == 64
        and options.get("mode") == "create",
        preview,
    )

    source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    drifted = cli(
        env,
        "import-commit", str(source),
        "--table", str(options.get("table") or "orders"),
        "--name", str(options.get("name") or "Orders"),
        "--mode", str(options.get("mode") or "create"),
        "--expected-plan", plan,
        "--require-plan",
        "--yes",
        expected=1,
    )
    tables_after_drift = cli(env, "list-tables")
    check(
        "single-file-drift-blocks-before-write",
        "changed after preview" in str(drifted.get("error") or "")
        and not (tables_after_drift.get("tables") or []),
        {"drifted": drifted, "tables": tables_after_drift.get("tables")},
    )

    refreshed = cli(env, "preview-import", str(source))
    refreshed_options = refreshed.get("commitOptions") if isinstance(refreshed.get("commitOptions"), dict) else {}
    committed = cli(
        env,
        "import-commit", str(source),
        "--table", str(refreshed_options.get("table") or "orders"),
        "--name", str(refreshed_options.get("name") or "Orders"),
        "--mode", str(refreshed_options.get("mode") or "create"),
        "--expected-plan", str(refreshed.get("planFingerprint") or ""),
        "--require-plan",
        "--yes",
    )
    check("single-file-bound-plan-commits", committed.get("committed") is True, committed)

    table_key = str((committed.get("result") or {}).get("tableKey") or refreshed_options.get("table") or "orders")
    query_args = ("query", "--table", table_key, "--measure", "*", "--agg", "count")
    first_query = cli(env, *query_args)
    second_query = cli(env, *query_args)
    first_runtime = (first_query.get("query") or {}).get("runtime") or {}
    second_runtime = (second_query.get("query") or {}).get("runtime") or {}
    check(
        "duckdb-replica-publishes-once-then-reuses-version",
        first_runtime.get("replicaStatus") == "published"
        and int(first_runtime.get("syncedRows") or 0) > 0
        and second_runtime.get("replicaStatus") == "current"
        and int(second_runtime.get("syncedRows") or 0) == 0
        and first_runtime.get("sourceVersion") == second_runtime.get("sourceVersion"),
        {"first": first_runtime, "second": second_runtime},
    )

    source.write_text(source.read_text(encoding="utf-8").replace("1200", "1201", 1), encoding="utf-8")
    replaced = cli(
        env,
        "import-commit", str(source),
        "--table", table_key,
        "--name", str(refreshed_options.get("name") or "Orders"),
        "--mode", "replace",
        "--yes",
    )
    third_query = cli(env, *query_args)
    third_runtime = (third_query.get("query") or {}).get("runtime") or {}
    check(
        "new-data-version-atomically-publishes-new-replica",
        (replaced.get("result") or {}).get("dataVersion") == 2
        and third_runtime.get("replicaStatus") == "published"
        and third_runtime.get("sourceVersion") != second_runtime.get("sourceVersion"),
        {"replace": replaced, "runtime": third_runtime},
    )

    manifest_rows: list[tuple[Any, ...]] = []
    current_relation = None
    if duck_path.is_file():
        with duckdb.connect(str(duck_path), read_only=True) as connection:
            manifest_exists = connection.execute(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_name = '__aibi_replica_manifest'"
            ).fetchone()[0]
            if manifest_exists:
                manifest_rows = connection.execute("SELECT logical_table, source_version, replica_table FROM __aibi_replica_manifest").fetchall()
                current_relation = connection.execute(
                    "SELECT table_type FROM information_schema.tables WHERE table_name = ?",
                    [str(manifest_rows[0][0]) if manifest_rows else ""],
                ).fetchone()
    check(
        "duckdb-manifest-points-at-versioned-physical-copy",
        len(manifest_rows) == 1
        and str(manifest_rows[0][2]).startswith("__aibi_replica_")
        and current_relation is not None
        and str(current_relation[0]) == "VIEW",
        {"manifest": manifest_rows, "relation": current_relation, "duckdbExists": duck_path.is_file(), "runtime": third_runtime},
    )

    selected_default = cli(env, "workspace-select", "default", "--yes")
    deleted_workspace = cli(env, "workspace-delete", workspace_id, "--yes")
    remaining_relations: list[tuple[Any, ...]] = []
    remaining_manifest: list[tuple[Any, ...]] = []
    if duck_path.is_file():
        with duckdb.connect(str(duck_path), read_only=True) as connection:
            remaining_relations = connection.execute(
                "SELECT table_name, table_type FROM information_schema.tables WHERE table_name = ? OR table_name LIKE '__aibi_replica_%'",
                [str(manifest_rows[0][0]) if manifest_rows else ""],
            ).fetchall()
            remaining_manifest = connection.execute(
                "SELECT logical_table, replica_table FROM __aibi_replica_manifest WHERE logical_table = ?",
                [str(manifest_rows[0][0]) if manifest_rows else ""],
            ).fetchall()
    check(
        "workspace-delete-removes-logical-view-and-versioned-replica",
        selected_default.get("workspace", {}).get("id") == "default"
        and deleted_workspace.get("confirmed") is True
        and not remaining_manifest
        and all(str(row[0]) == "__aibi_replica_manifest" for row in remaining_relations),
        {"deleted": deleted_workspace, "relations": remaining_relations, "manifest": remaining_manifest},
    )

    evidence_file = temp / "evidence-source.txt"
    evidence_file.write_text("stable evidence\n", encoding="utf-8")
    evidence_args = {
        "command": "runtime-hardening",
        "workspace_id": "test-workspace",
        "title": "Deterministic receipt",
        "status": "verified",
        "summary": {"rows": 10},
        "payload": {"result": "same"},
        "artifacts": [artifact_ref("source", evidence_file)],
    }
    first_evidence = write_evidence_bundle(**evidence_args)
    second_evidence = write_evidence_bundle(**evidence_args)
    changed_evidence = write_evidence_bundle(**{**evidence_args, "payload": {"result": "changed"}})
    manifest = json.loads(Path(first_evidence["manifestPath"]).read_text(encoding="utf-8"))
    check(
        "evidence-bundles-use-deterministic-content-addresses",
        first_evidence["bundleKey"] == second_evidence["bundleKey"]
        and first_evidence["contentAddress"] == second_evidence["contentAddress"]
        and first_evidence["contentAddress"] != changed_evidence["contentAddress"]
        and str(first_evidence["contentAddress"]).startswith("sha256:")
        and manifest.get("contentAddress") == first_evidence["contentAddress"]
        and manifest.get("artifacts", [{}])[0].get("sha256") == artifact_ref("source", evidence_file)["sha256"],
        {"first": first_evidence, "second": second_evidence, "changed": changed_evidence, "manifest": manifest},
    )

failed = [item for item in CHECKS if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-runtime-hardening-verify/v1",
    "generatedBy": "scripts/verify-runtime-hardening.py",
    "checks": CHECKS,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2, default=str))
raise SystemExit(1 if failed else 0)
