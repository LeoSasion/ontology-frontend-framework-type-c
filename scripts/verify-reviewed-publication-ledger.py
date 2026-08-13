from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from query_plan_receipt_service import get_query_receipt, query_receipt_binding_fingerprint  # noqa: E402
from reviewed_publication_service import (  # noqa: E402
    DRIFT_REASONS,
    build_reviewed_publication_plan,
    deprecate_reviewed_publication,
    ensure_reviewed_publication_schema,
    evaluate_reviewed_publication,
    list_evidence_ledger,
    publish_reviewed_artifact,
    reviewed_publication_export,
    tombstone_reviewed_publication,
    verify_evidence_ledger,
)


NOW = "2026-08-13T09:00:00Z"
SKILL_V1 = "1" * 64
SKILL_V2 = "2" * 64


def main() -> int:
    checks: list[dict[str, Any]] = []

    def check(label: str, ok: object, detail: Any = None) -> None:
        checks.append({"label": label, "ok": bool(ok), "detail": detail})

    def expect_error(label: str, callback, expected: str) -> None:
        try:
            callback()
        except Exception as error:
            check(label, expected.casefold() in str(error).casefold(), str(error))
        else:
            check(label, False, "operation unexpectedly succeeded")

    with tempfile.TemporaryDirectory(prefix="aibi-reviewed-publication-") as temp_dir:
        db_path = Path(temp_dir) / "runtime.sqlite"
        env = {
            **os.environ,
            "AIBI_HYBRID_DB_PATH": str(db_path),
            "AIBI_HYBRID_DUCKDB_PATH": str(Path(temp_dir) / "runtime.duckdb"),
            "AIBI_EVIDENCE_BUNDLE_ROOT": str(Path(temp_dir) / "evidence"),
            "PYTHONIOENCODING": "utf-8",
        }

        def cli(*args: str) -> dict[str, Any]:
            result = subprocess.run(
                [sys.executable, "tools/aibi_cli.py", "--json", *args],
                cwd=ROOT,
                env=env,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            try:
                payload = json.loads(result.stdout.strip())
            except json.JSONDecodeError as error:
                raise AssertionError(f"CLI returned invalid JSON for {args}: {result.stderr}\n{result.stdout}") from error
            if result.returncode != 0 or payload.get("ok") is not True:
                raise AssertionError(f"CLI failed for {args}: {result.stderr}\n{result.stdout}")
            return payload

        imported = cli("import-commit", "validation-inputs/orders.csv", "--table", "orders", "--name", "Orders", "--mode", "create", "--yes")
        check(
            "fixture-import-uses-durable-activation-lifecycle",
            imported.get("committed") is True
            and bool(imported.get("activationJournalKey"))
            and imported.get("durableJob", {}).get("status") == "succeeded",
            {
                "activationJournalKey": imported.get("activationJournalKey"),
                "jobKey": imported.get("durableJob", {}).get("jobKey"),
            },
        )
        cli("business-dashboard", "--op", "create", "--table", "orders", "--name", "Reviewed publication", "--limit", "1", "--yes")
        answer = cli("ask", "请将net_sales按channel合计并生成柱状图")
        action_key = str(answer.get("actionDraft", {}).get("actionKey") or "")
        unit_key = str(answer.get("analysisUnit", {}).get("unitKey") or "")
        action = cli("confirm-action", action_key, "--yes")
        candidate_key = str(action.get("confirmedQueryCandidate", {}).get("query_key") or "")
        promoted = cli("confirm-query", "--query", candidate_key, "--yes")
        memory_key = str(promoted.get("confirmedPlanMemory", {}).get("memoryKey") or "")
        check(
            "fixture-uses-real-executed-unit-and-explicit-confirmed-plan-memory",
            bool(action_key and unit_key and candidate_key and memory_key),
            {"unitKey": unit_key, "memoryKey": memory_key},
        )

        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        ensure_reviewed_publication_schema(connection)
        connection.commit()
        content = {
            "summary": "Regional channel performance reviewed by an operator.",
            "claims": [{"text": "The executed result is suitable for the approved chart.", "evidence": "analysis-unit"}],
        }
        plan = build_reviewed_publication_plan(
            connection,
            workspace_id="default",
            memory_key=memory_key,
            unit_key=unit_key,
            title="Reviewed channel performance",
            content=content,
            skill_fingerprint=SKILL_V1,
        )
        count_before = connection.execute("SELECT COUNT(*) FROM reviewed_publications").fetchone()[0]
        check(
            "preview-freezes-content-and-complete-input-contract-without-writing",
            count_before == 0
            and plan["requiresConfirmation"] is True
            and len(plan["planFingerprint"]) == 64
            and all(plan["inputContract"].get(key) is not None for key in [
                "sourceFingerprint",
                "dataFingerprint",
                "schemaFingerprint",
                "relationshipFingerprint",
                "domainPackFingerprint",
                "skillFingerprint",
                "queryReceiptFingerprint",
                "resultFingerprint",
            ]),
            plan,
        )
        expect_error(
            "confirmation-rejects-a-different-preview-fingerprint",
            lambda: publish_reviewed_artifact(
                connection,
                plan=plan,
                expected_plan_fingerprint="0" * 64,
                now_iso=lambda: NOW,
            ),
            "confirmation fingerprint",
        )
        changed_plan = {**plan, "content": {"summary": "changed after preview"}}
        expect_error(
            "confirmation-rejects-content-mutated-after-preview",
            lambda: publish_reviewed_artifact(
                connection,
                plan=changed_plan,
                expected_plan_fingerprint=plan["planFingerprint"],
                now_iso=lambda: NOW,
            ),
            "plan content changed",
        )
        expect_error(
            "public-content-contract-rejects-secrets-paths-and-raw-row-fields",
            lambda: build_reviewed_publication_plan(
                connection,
                workspace_id="default",
                memory_key=memory_key,
                unit_key=unit_key,
                title="Unsafe",
                content={"rawRows": [{"password": "never"}]},
            ),
            "forbidden field",
        )
        expect_error(
            "cross-workspace-references-fail-closed",
            lambda: build_reviewed_publication_plan(
                connection,
                workspace_id="another-workspace",
                memory_key=memory_key,
                unit_key=unit_key,
                title="Cross scope",
                content={"summary": "must fail"},
            ),
            "active workspace",
        )

        connection.execute("BEGIN IMMEDIATE")
        saved = publish_reviewed_artifact(
            connection,
            plan=plan,
            expected_plan_fingerprint=plan["planFingerprint"],
            now_iso=lambda: NOW,
        )
        connection.commit()
        publication_key = saved["publication"]["publicationKey"]
        current = evaluate_reviewed_publication(
            connection,
            workspace_id="default",
            publication_key=publication_key,
            current_skill_fingerprint=SKILL_V1,
        )
        check(
            "explicit-publication-creates-a-current-genesis-ledger",
            saved["created"] is True
            and current["status"] == "current"
            and current["canSupportCurrentDecision"] is True
            and current["ledger"]["ok"] is True
            and current["ledger"]["currentEvidence"] is True
            and current["ledger"]["entryCount"] == 1,
            current,
        )
        exported = reviewed_publication_export(
            connection,
            workspace_id="default",
            publication_key=publication_key,
            current_skill_fingerprint=SKILL_V1,
        )
        check(
            "current-export-carries-ledger-and-current-decision-label",
            exported["currentDecisionBasis"] is True
            and exported["forensic"] is False
            and len(exported["ledgerEntries"]) == 1,
        )
        duplicate = publish_reviewed_artifact(
            connection,
            plan=plan,
            expected_plan_fingerprint=plan["planFingerprint"],
            now_iso=lambda: NOW,
        )
        check(
            "same-reviewed-material-is-idempotent",
            duplicate["created"] is False
            and connection.execute("SELECT COUNT(*) FROM reviewed_publications").fetchone()[0] == 1
            and len(list_evidence_ledger(connection, workspace_id="default", publication_key=publication_key)) == 1,
        )
        skill_drift = evaluate_reviewed_publication(
            connection,
            workspace_id="default",
            publication_key=publication_key,
            current_skill_fingerprint=SKILL_V2,
        )
        check(
            "skill-drift-is-a-stable-explained-reason",
            skill_drift["status"] == "stale"
            and skill_drift["drift"]["reasonCodes"] == ["skill-changed"],
            skill_drift["drift"],
        )

        memory_row = connection.execute(
            "SELECT query_receipt_key, binding_fingerprint FROM confirmed_plan_memories WHERE workspace_id = 'default' AND memory_key = ?",
            (memory_key,),
        ).fetchone()
        receipt = get_query_receipt(connection, "default", memory_row["query_receipt_key"])
        full_binding = query_receipt_binding_fingerprint(receipt)
        legacy_binding = str(receipt.get("source", {}).get("schemaFingerprint") or "")
        connection.execute(
            "UPDATE confirmed_plan_memories SET binding_fingerprint = ? WHERE workspace_id = 'default' AND memory_key = ?",
            (legacy_binding, memory_key),
        )
        legacy_plan = build_reviewed_publication_plan(
            connection,
            workspace_id="default",
            memory_key=memory_key,
            unit_key=unit_key,
            title="Explicit legacy review",
            content={"summary": "Legacy memory was explicitly reviewed against current evidence."},
        )
        check(
            "legacy-schema-binding-can-only-be-upgraded-by-explicit-current-review",
            legacy_plan["requiresConfirmation"] is True
            and legacy_plan["inputContract"]["queryReceiptBindingFingerprint"] == full_binding,
        )
        connection.execute(
            "UPDATE confirmed_plan_memories SET binding_fingerprint = ? WHERE workspace_id = 'default' AND memory_key = ?",
            (full_binding, memory_key),
        )

        connection.execute("SAVEPOINT source_drift")
        connection.execute(
            "UPDATE table_registry SET data_version = data_version + 1 WHERE workspace_id = 'default' AND table_key = 'orders'"
        )
        source_drift = evaluate_reviewed_publication(
            connection,
            workspace_id="default",
            publication_key=publication_key,
            current_skill_fingerprint=SKILL_V1,
        )
        check(
            "source-data-drift-unloads-current-decision-authority",
            source_drift["status"] == "stale"
            and source_drift["canSupportCurrentDecision"] is False
            and source_drift["ledger"]["currentEvidence"] is False
            and any(code in source_drift["drift"]["reasonCodes"] for code in ["data-changed", "source-changed", "source-run-changed"]),
            source_drift["drift"],
        )
        connection.execute("ROLLBACK TO source_drift")
        connection.execute("RELEASE source_drift")

        connection.execute("SAVEPOINT content_tamper")
        connection.execute(
            "UPDATE reviewed_publications SET content_json = ? WHERE workspace_id = 'default' AND publication_key = ?",
            (json.dumps({"summary": "tampered"}), publication_key),
        )
        content_tamper = evaluate_reviewed_publication(connection, workspace_id="default", publication_key=publication_key)
        check(
            "content-tamper-marks-publication-integrity-failed-and-read-only",
            content_tamper["status"] == "integrity_failed"
            and content_tamper["canSupportCurrentDecision"] is False
            and "content-changed" in content_tamper["drift"]["reasonCodes"]
            and "ledger-integrity-failed" in content_tamper["drift"]["reasonCodes"],
            content_tamper,
        )
        connection.execute("ROLLBACK TO content_tamper")
        connection.execute("RELEASE content_tamper")

        connection.execute("SAVEPOINT hash_tamper")
        connection.execute(
            "UPDATE evidence_ledger_entries SET entry_hash = ? WHERE workspace_id = 'default' AND publication_key = ? AND sequence = 1",
            ("0" * 64, publication_key),
        )
        hash_tamper = verify_evidence_ledger(connection, workspace_id="default", publication_key=publication_key)
        check(
            "ledger-entry-hash-tamper-is-detected",
            hash_tamper["ok"] is False
            and "ledger-entry-hash-mismatch" in hash_tamper["blockers"],
            hash_tamper,
        )
        connection.execute("ROLLBACK TO hash_tamper")
        connection.execute("RELEASE hash_tamper")

        head = current["ledgerHeadHash"]
        if not connection.in_transaction:
            connection.execute("BEGIN IMMEDIATE")
        expect_error(
            "append-requires-the-current-ledger-head",
            lambda: deprecate_reviewed_publication(
                connection,
                workspace_id="default",
                publication_key=publication_key,
                expected_head_hash="f" * 64,
                reason="superseded",
                now_iso=lambda: NOW,
            ),
            "ledger head changed",
        )
        deprecated = deprecate_reviewed_publication(
            connection,
            workspace_id="default",
            publication_key=publication_key,
            expected_head_hash=head,
            reason="Superseded by a new reviewed analysis.",
            now_iso=lambda: NOW,
        )
        connection.commit()
        check(
            "deprecation-appends-instead-of-rewriting-history",
            deprecated["deprecated"] is True
            and deprecated["publication"]["status"] == "deprecated"
            and len(list_evidence_ledger(connection, workspace_id="default", publication_key=publication_key)) == 2,
        )

        connection.execute("SAVEPOINT middle_delete")
        connection.execute(
            "DELETE FROM evidence_ledger_entries WHERE workspace_id = 'default' AND publication_key = ? AND sequence = 1",
            (publication_key,),
        )
        deleted_middle = verify_evidence_ledger(connection, workspace_id="default", publication_key=publication_key)
        check(
            "deleting-an-intermediate-ledger-entry-is-detected",
            deleted_middle["ok"] is False
            and "ledger-sequence-gap" in deleted_middle["blockers"]
            and "ledger-previous-hash-mismatch" in deleted_middle["blockers"],
            deleted_middle,
        )
        connection.execute("ROLLBACK TO middle_delete")
        connection.execute("RELEASE middle_delete")
        if not connection.in_transaction:
            connection.execute("BEGIN IMMEDIATE")
        tombstoned = tombstone_reviewed_publication(
            connection,
            workspace_id="default",
            publication_key=publication_key,
            expected_head_hash=deprecated["publication"]["ledgerHeadHash"],
            reason="workspace lifecycle retention marker",
            now_iso=lambda: NOW,
        )
        connection.commit()
        check(
            "workspace-lifecycle-tombstone-is-appended-without-erasing-history",
            tombstoned["tombstoned"] is True
            and tombstoned["publication"]["deprecationReason"].startswith("Tombstoned:")
            and len(list_evidence_ledger(connection, workspace_id="default", publication_key=publication_key)) == 3,
        )
        connection.close()

        cli("domain-pack-set", "--pack", "platform-commerce", "--state", "enabled", "--yes")
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        pack_drift = evaluate_reviewed_publication(connection, workspace_id="default", publication_key=publication_key)
        check(
            "domain-pack-drift-remains-visible-on-a-deprecated-publication",
            pack_drift["status"] == "deprecated"
            and "domain-pack-changed" in pack_drift["drift"]["reasonCodes"]
            and pack_drift["canSupportCurrentDecision"] is False,
            pack_drift["drift"],
        )
        connection.close()

    check(
        "drift-reason-registry-covers-source-relationship-pack-skill-and-integrity",
        {"source-changed", "relationship-changed", "domain-pack-changed", "skill-changed", "ledger-integrity-failed"}.issubset(DRIFT_REASONS),
    )
    failed = [item for item in checks if not item["ok"]]
    print(json.dumps({
        "ok": not failed,
        "schema": "aibi-reviewed-publication-ledger-verify/v1",
        "generatedBy": "scripts/verify-reviewed-publication-ledger.py",
        "checks": checks,
        "failedChecks": failed,
    }, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
