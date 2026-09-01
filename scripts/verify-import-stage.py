from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from import_stage_service import (  # noqa: E402
    create_import_stage,
    iter_import_stage_rows,
    load_import_stage_manifest,
    read_import_stage,
    validate_import_stage_for_confirmation,
)


def check(checks: list[dict[str, object]], label: str, condition: bool, detail: object = None) -> None:
    checks.append({"label": label, "ok": bool(condition)})
    if not condition:
        raise AssertionError(json.dumps({"label": label, "detail": detail}, ensure_ascii=False, default=str))


class CountingRows:
    def __init__(self, rows: list[dict[str, str]]) -> None:
        self.rows = rows
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        if self.iterations > 1:
            raise AssertionError("source rows were parsed more than once")
        yield from self.rows


def main() -> None:
    checks: list[dict[str, object]] = []
    previous_root = os.environ.get("AIBI_IMPORT_STAGE_ROOT")
    previous_ttl = os.environ.get("AIBI_IMPORT_STAGE_TTL_SECONDS")
    previous_quota = os.environ.get("AIBI_IMPORT_STAGE_MAX_BYTES")
    try:
        with tempfile.TemporaryDirectory(prefix="aibi-import-stage-") as temp_dir:
            temp_root = Path(temp_dir)
            stage_root = temp_root / "staging"
            os.environ["AIBI_IMPORT_STAGE_ROOT"] = str(stage_root)
            os.environ["AIBI_IMPORT_STAGE_TTL_SECONDS"] = "3600"
            os.environ["AIBI_IMPORT_STAGE_MAX_BYTES"] = str(1024 * 1024)

            source = temp_root / "orders.csv"
            source.write_text("id,amount\n1,10\n2,20\n", encoding="utf-8")
            rows = CountingRows([{"id": "1", "amount": "10"}, {"id": "2", "amount": "20"}])
            profile = {
                "rowCount": 2,
                "columnCount": 2,
                "fields": [
                    {"field": "id", "role": "identity_key", "uniqueCount": 2, "nonEmpty": 2},
                    {"field": "amount", "role": "measure", "uniqueCount": 2, "nonEmpty": 2},
                ],
            }
            stage = create_import_stage(
                source_path=source,
                workspace_id="workspace-a",
                headers=["id", "amount"],
                rows=rows,
                profile=profile,
                root=stage_root,
            )
            check(checks, "source-records-are-consumed-exactly-once", rows.iterations == 1, rows.iterations)
            check(
                checks,
                "public-stage-summary-is-sealed-and-path-free",
                stage.get("sealed") is True
                and stage.get("rowCount") == 2
                and str(source.resolve()) not in json.dumps(stage, ensure_ascii=False),
                stage,
            )

            source.write_text("id,amount\n1,999\n", encoding="utf-8")
            headers, staged_rows, staged_profile, replay_summary = read_import_stage(
                stage_key=str(stage["stageKey"]),
                workspace_id="workspace-a",
                root=stage_root,
            )
            check(
                checks,
                "sealed-stage-is-independent-from-later-source-changes",
                headers == ["id", "amount"]
                and staged_rows == [{"id": "1", "amount": "10"}, {"id": "2", "amount": "20"}]
                and staged_profile.get("rowCount") == profile["rowCount"]
                and staged_profile.get("columnCount") == profile["columnCount"]
                and [item.get("field") for item in staged_profile.get("fields") or []] == ["id", "amount"]
                and replay_summary["contentFingerprint"] == stage["contentFingerprint"],
                staged_rows,
            )
            batches = list(
                iter_import_stage_rows(
                    stage_key=str(stage["stageKey"]),
                    workspace_id="workspace-a",
                    root=stage_root,
                    batch_size=1,
                )
            )
            check(checks, "stage-reader-honors-bounded-batches", [len(batch) for batch in batches] == [1, 1], batches)

            cross_workspace_blocked = False
            try:
                load_import_stage_manifest(
                    stage_key=str(stage["stageKey"]),
                    workspace_id="workspace-b",
                    root=stage_root,
                )
            except (FileNotFoundError, PermissionError):
                cross_workspace_blocked = True
            check(checks, "stage-cannot-cross-workspaces", cross_workspace_blocked)

            expired_source = temp_root / "expired.csv"
            expired_source.write_text("id\n1\n", encoding="utf-8")
            expired = create_import_stage(
                source_path=expired_source,
                workspace_id="workspace-a",
                headers=["id"],
                rows=[{"id": "1"}],
                profile={"rowCount": 1, "columnCount": 1, "fields": []},
                root=stage_root,
                timestamp=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            )
            expired_blocked = False
            try:
                validate_import_stage_for_confirmation(
                    stage_key=str(expired["stageKey"]),
                    workspace_id="workspace-a",
                    root=stage_root,
                )
            except ValueError as error:
                expired_blocked = "expired" in str(error).lower()
            check(checks, "expired-stage-cannot-authorize-a-new-job", expired_blocked)
            expired_rows = read_import_stage(
                stage_key=str(expired["stageKey"]),
                workspace_id="workspace-a",
                root=stage_root,
            )[1]
            check(checks, "already-bound-job-can-still-read-an-expired-stage", expired_rows == [{"id": "1"}], expired_rows)

            parquet = next(stage_root.rglob(f"{stage['stageKey']}/data.parquet"))
            with parquet.open("ab") as stream:
                stream.write(b"tamper")
            tamper_blocked = False
            try:
                load_import_stage_manifest(
                    stage_key=str(stage["stageKey"]),
                    workspace_id="workspace-a",
                    root=stage_root,
                )
            except ValueError as error:
                tamper_blocked = "integrity" in str(error).lower()
            check(checks, "tampered-stage-fails-closed", tamper_blocked)

            invalid_key_blocked = False
            try:
                load_import_stage_manifest(
                    stage_key="stage_zzzzzzzzzzzzzzzzzzzzzzzz",
                    workspace_id="workspace-a",
                    root=stage_root,
                )
            except ValueError:
                invalid_key_blocked = True
            check(checks, "stage-key-is-strictly-validated", invalid_key_blocked)

            expanded = temp_root / "expanded.csv"
            expanded.write_text("value\nsmall\n", encoding="utf-8")
            expanded_quota_blocked = False
            try:
                create_import_stage(
                    source_path=expanded,
                    workspace_id="workspace-a",
                    headers=["value"],
                    rows=[{"value": "x" * (2 * 1024 * 1024)}],
                    profile={"rowCount": 1, "columnCount": 1, "fields": []},
                    root=stage_root,
                )
            except OSError as error:
                expanded_quota_blocked = "quota" in str(error).lower()
            check(
                checks,
                "stage-quota-covers-expanded-parquet-size-and-cleans-temporaries",
                expanded_quota_blocked and not list(stage_root.rglob("*.tmp")),
                list(stage_root.rglob("*.tmp")),
            )

            oversized = temp_root / "oversized.csv"
            oversized.write_bytes(b"x" * (1024 * 1024 + 1))
            quota_blocked = False
            try:
                create_import_stage(
                    source_path=oversized,
                    workspace_id="workspace-a",
                    headers=["value"],
                    rows=[{"value": "x"}],
                    profile={"rowCount": 1, "columnCount": 1, "fields": []},
                    root=stage_root,
                )
            except OSError as error:
                quota_blocked = "quota" in str(error).lower()
            check(checks, "stage-quota-is-enforced-before-publish", quota_blocked)
    finally:
        if previous_root is None:
            os.environ.pop("AIBI_IMPORT_STAGE_ROOT", None)
        else:
            os.environ["AIBI_IMPORT_STAGE_ROOT"] = previous_root
        if previous_ttl is None:
            os.environ.pop("AIBI_IMPORT_STAGE_TTL_SECONDS", None)
        else:
            os.environ["AIBI_IMPORT_STAGE_TTL_SECONDS"] = previous_ttl
        if previous_quota is None:
            os.environ.pop("AIBI_IMPORT_STAGE_MAX_BYTES", None)
        else:
            os.environ["AIBI_IMPORT_STAGE_MAX_BYTES"] = previous_quota

    print(
        json.dumps(
            {
                "ok": True,
                "schema": "aibi-import-stage-verify/v1",
                "generatedBy": "scripts/verify-import-stage.py",
                "checks": checks,
                "failedChecks": [item["label"] for item in checks if not item["ok"]],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
