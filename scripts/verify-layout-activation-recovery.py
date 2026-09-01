from __future__ import annotations

from contextlib import closing
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def run() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="aibi-layout-recovery-v2-") as raw_temp:
        temp = Path(raw_temp)
        os.environ["AIBI_HYBRID_DB_PATH"] = str(temp / "control-v2.sqlite")
        os.environ["AIBI_HYBRID_DUCKDB_PATH"] = str(temp / "catalog-v2.duckdb")
        os.environ["AIBI_DATASET_OBJECT_ROOT"] = str(temp / "objects-v2")
        os.environ["PYTHONIOENCODING"] = "utf-8"
        tools = ROOT / "tools"
        if str(tools) not in sys.path:
            sys.path.insert(0, str(tools))

        environment = dict(os.environ)
        imported = subprocess.run(
            [
                sys.executable,
                "tools/aibi_cli.py",
                "--json",
                "import-commit",
                "validation-inputs/orders.csv",
                "--table",
                "orders",
                "--name",
                "Orders",
                "--mode",
                "create",
                "--yes",
            ],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        if imported.returncode != 0:
            raise RuntimeError(imported.stderr or imported.stdout)

        import duckdb  # type: ignore
        import bi_cli_dashboard_commands as layout_service  # type: ignore
        from bi_cli_core import DUCKDB_PATH  # type: ignore
        from bi_cli_schema import open_db  # type: ignore
        from source_activation_journal_service import reconcile_activation, unfinished_activations  # type: ignore

        def registry_version() -> str:
            with closing(open_db()) as connection:
                row = connection.execute(
                    "SELECT active_version_id FROM table_registry WHERE table_key = 'orders'"
                ).fetchone()
                return str(row["active_version_id"] or "") if row else ""

        with closing(open_db()) as connection:
            table_row = connection.execute(
                "SELECT physical_table FROM table_registry WHERE table_key = 'orders'"
            ).fetchone()
            physical_table = str(table_row["physical_table"] or "") if table_row else ""
        if not physical_table:
            raise RuntimeError("Imported orders table is missing.")

        def catalog_version() -> str:
            with duckdb.connect(str(DUCKDB_PATH), read_only=True) as connection:
                row = connection.execute(
                    "SELECT version_id FROM __aibi_replica_manifest WHERE logical_table = ?",
                    [physical_table],
                ).fetchone()
                return str(row[0] or "") if row else ""

        original_version = registry_version()
        checks: list[dict[str, Any]] = []

        original_publish = layout_service.publish_dataset_view

        def interrupt_after_catalog(*args: Any, **kwargs: Any) -> dict[str, Any]:
            original_publish(*args, **kwargs)
            raise SystemExit("simulated hard stop after catalog publish")

        layout_service.publish_dataset_view = interrupt_after_catalog
        try:
            with closing(open_db()) as connection:
                proposed, columns = layout_service.build_index_plan(connection, "orders", "channel")
                try:
                    layout_service.execute_index_plan(connection, proposed, columns)
                except SystemExit:
                    pass
        finally:
            layout_service.publish_dataset_view = original_publish

        with closing(open_db()) as connection:
            pending = unfinished_activations(connection, workspace_id="default")
            outcome = reconcile_activation(
                connection,
                journal=pending[0],
                duckdb_path=DUCKDB_PATH,
                now_iso=layout_service.now_iso,
            )
            connection.commit()
        checks.append({
            "label": "catalog-only-interruption-rolls-back",
            "ok": outcome.get("action") == "rolled_back"
            and registry_version() == original_version
            and catalog_version() == original_version,
        })

        original_transition = layout_service.transition_activation

        def interrupt_before_finalize(*args: Any, **kwargs: Any) -> dict[str, Any]:
            if kwargs.get("phase") == layout_service.PHASE_FINALIZED:
                raise SystemExit("simulated hard stop before journal finalization")
            return original_transition(*args, **kwargs)

        layout_service.transition_activation = interrupt_before_finalize
        try:
            with closing(open_db()) as connection:
                proposed, columns = layout_service.build_index_plan(connection, "orders", "channel")
                try:
                    layout_service.execute_index_plan(connection, proposed, columns)
                except SystemExit:
                    pass
        finally:
            layout_service.transition_activation = original_transition

        target_version = registry_version()
        with closing(open_db()) as connection:
            pending = unfinished_activations(connection, workspace_id="default")
            outcome = reconcile_activation(
                connection,
                journal=pending[0],
                duckdb_path=DUCKDB_PATH,
                now_iso=layout_service.now_iso,
            )
            connection.commit()
            remaining = unfinished_activations(connection, workspace_id="default")
        checks.append({
            "label": "pointer-committed-interruption-finalizes",
            "ok": bool(target_version)
            and target_version != original_version
            and outcome.get("action") == "finalized"
            and catalog_version() == target_version
            and not remaining,
        })
        with duckdb.connect(str(DUCKDB_PATH), read_only=True) as connection:
            row_count = int(connection.execute(f'SELECT COUNT(*) FROM "{physical_table.replace(chr(34), chr(34) * 2)}"').fetchone()[0])
        checks.append({"label": "reconciled-layout-remains-queryable", "ok": row_count > 0})
        failed = [item for item in checks if not item["ok"]]
        return {
            "ok": not failed,
            "schema": "aibi-layout-activation-recovery-verify/v1",
            "checks": checks,
            "failedChecks": failed,
        }


if __name__ == "__main__":
    try:
        result = run()
    except Exception as error:
        result = {
            "ok": False,
            "schema": "aibi-layout-activation-recovery-verify/v1",
            "error": f"{type(error).__name__}: {error}",
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result.get("ok") else 1)
