from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import ExitStack, closing
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from decision_framework_service import (  # noqa: E402
    build_decision_framework_publication_plan,
    create_decision_framework_draft,
    ensure_decision_framework_schema,
    export_decision_framework,
    get_decision_framework,
    list_decision_frameworks,
    publish_decision_framework,
    save_decision_framework_draft,
)


NOW = "2026-08-13T12:00:00Z"


def main() -> int:
    checks: list[dict[str, Any]] = []

    def check(label: str, ok: object, detail: Any = None) -> None:
        checks.append({"label": label, "ok": bool(ok), "detail": detail})

    def expect_error(label: str, callback: Callable[[], Any], expected: str) -> None:
        try:
            callback()
        except Exception as error:
            check(label, expected.casefold() in str(error).casefold(), str(error))
        else:
            check(label, False, "operation unexpectedly succeeded")

    with ExitStack() as stack:
        temp_dir = stack.enter_context(tempfile.TemporaryDirectory(prefix="aibi-decision-framework-"))
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
        cli("business-dashboard", "--op", "create", "--table", "orders", "--name", "Decision framework", "--limit", "1", "--yes")
        answer = cli("ask", "请将net_sales按channel合计并生成柱状图")
        action_key = str(answer.get("actionDraft", {}).get("actionKey") or "")
        unit_key = str(answer.get("analysisUnit", {}).get("unitKey") or "")
        action = cli("confirm-action", action_key, "--yes")
        query_key = str(action.get("confirmedQueryCandidate", {}).get("query_key") or "")
        promoted = cli("confirm-query", "--query", query_key, "--yes")
        memory_key = str(promoted.get("confirmedPlanMemory", {}).get("memoryKey") or "")
        check("fixture-has-current-executed-evidence-and-confirmed-memory", bool(unit_key and memory_key), {"unitKey": unit_key, "memoryKey": memory_key})

        connection = stack.enter_context(closing(sqlite3.connect(db_path)))
        connection.row_factory = sqlite3.Row
        ensure_decision_framework_schema(connection)
        connection.commit()

        connection.execute("BEGIN IMMEDIATE")
        draft = create_decision_framework_draft(
            connection,
            workspace_id="default",
            unit_key=unit_key,
            framework_type="swot",
            title="Channel evidence SWOT",
            request_key="framework-request-001",
            now_iso=lambda: NOW,
        )
        connection.commit()
        check(
            "default-creation-produces-only-structure-and-current-evidence-candidates",
            draft["status"] == "draft"
            and draft["claims"] == []
            and [section["key"] for section in draft["structure"]["sections"]] == ["strength", "weakness", "opportunity", "threat"]
            and len(draft["evidenceCandidates"]) >= 1
            and all(item["claimKind"] == "evidence_fact" and item["status"] == "candidate" for item in draft["evidenceCandidates"]),
            draft,
        )
        check(
            "default-candidates-do-not-invent-opportunity-threat-cause-or-action",
            all(item["category"] == "unassigned" for item in draft["evidenceCandidates"])
            and all(not any(token in item["text"].casefold() for token in ["opportunity", "threat", "because", "should", "机会", "威胁", "因为", "建议"]) for item in draft["evidenceCandidates"]),
        )

        connection.execute("BEGIN IMMEDIATE")
        duplicate = create_decision_framework_draft(
            connection,
            workspace_id="default",
            unit_key=unit_key,
            framework_type="swot",
            title="Channel evidence SWOT",
            request_key="framework-request-001",
            now_iso=lambda: NOW,
        )
        connection.commit()
        check(
            "same-request-key-and-input-is-idempotent",
            duplicate["frameworkKey"] == draft["frameworkKey"]
            and connection.execute("SELECT COUNT(*) FROM decision_frameworks").fetchone()[0] == 1,
        )
        connection.execute("BEGIN IMMEDIATE")
        process_draft = create_decision_framework_draft(
            connection,
            workspace_id="default",
            unit_key=unit_key,
            framework_type="process",
            title="Observed decision process",
            request_key="framework-request-002",
            now_iso=lambda: NOW,
        )
        connection.commit()
        check(
            "process-framework-has-an-empty-non-causal-structure",
            [section["key"] for section in process_draft["structure"]["sections"]] == ["input", "observation", "decision"]
            and process_draft["claims"] == []
            and all(item["category"] == "unassigned" for item in process_draft["evidenceCandidates"]),
            process_draft["structure"],
        )
        connection.execute("BEGIN IMMEDIATE")
        expect_error(
            "same-request-key-with-different-input-conflicts",
            lambda: create_decision_framework_draft(
                connection,
                workspace_id="default",
                unit_key=unit_key,
                framework_type="process",
                title="Different input",
                request_key="framework-request-001",
                now_iso=lambda: NOW,
            ),
            "conflicts",
        )
        connection.rollback()

        candidate = draft["evidenceCandidates"][0]
        claims = [
            {**candidate, "category": "strength"},
            {
                "claimKey": "claim_local_judgment",
                "category": "weakness",
                "text": "The operator considers this concentration material.",
                "claimKind": "user_judgment",
                "evidenceRefs": [{"type": "queryPlanReceipt", "receiptKey": "must-be-removed"}],
                "author": "local-user",
                "status": "user_asserted",
                "verificationRequirement": "",
            },
            {
                "claimKey": "claim_local_hypothesis",
                "category": "opportunity",
                "text": "A different channel mix may improve the outcome.",
                "claimKind": "hypothesis",
                "evidenceRefs": [],
                "author": "local-user",
                "status": "needs_validation",
                "verificationRequirement": "Run a controlled channel-level comparison on a new current period.",
            },
        ]
        connection.execute("BEGIN IMMEDIATE")
        saved = save_decision_framework_draft(
            connection,
            workspace_id="default",
            framework_key=draft["frameworkKey"],
            title=draft["title"],
            claims=claims,
            expected_content_fingerprint=draft["contentFingerprint"],
            now_iso=lambda: NOW,
        )
        connection.commit()
        check(
            "claims-are-separated-and-content-fingerprinted",
            saved["claimCounts"] == {"evidenceFact": 1, "userJudgment": 1, "hypothesis": 1}
            and saved["claims"][0]["status"] == "supported"
            and saved["claims"][1]["evidenceRefs"] == []
            and saved["claims"][2]["verificationRequirement"]
            and all(len(item["contentFingerprint"]) == 64 for item in saved["claims"])
            and len(saved["contentFingerprint"]) == 64,
            saved["claims"],
        )

        connection.execute("BEGIN IMMEDIATE")
        expect_error(
            "evidence-fact-cannot-be-rewritten-beyond-generated-current-candidate",
            lambda: save_decision_framework_draft(
                connection,
                workspace_id="default",
                framework_key=draft["frameworkKey"],
                title=draft["title"],
                claims=[{**candidate, "category": "strength", "text": "Unsupported invented fact 999999"}],
                expected_content_fingerprint=saved["contentFingerprint"],
                now_iso=lambda: NOW,
            ),
            "current generated evidence candidate",
        )
        connection.rollback()
        connection.execute("BEGIN IMMEDIATE")
        expect_error(
            "evidence-fact-without-current-receipt-reference-is-rejected",
            lambda: save_decision_framework_draft(
                connection,
                workspace_id="default",
                framework_key=draft["frameworkKey"],
                title=draft["title"],
                claims=[{**candidate, "category": "strength", "evidenceRefs": []}],
                expected_content_fingerprint=saved["contentFingerprint"],
                now_iso=lambda: NOW,
            ),
            "current executed Query Receipt",
        )
        connection.rollback()

        plan = build_decision_framework_publication_plan(
            connection,
            workspace_id="default",
            framework_key=draft["frameworkKey"],
        )
        check(
            "publication-preview-wraps-reviewed-publication-with-one-stable-fingerprint",
            plan["requiresConfirmation"] is True
            and len(plan["planFingerprint"]) == 64
            and plan["reviewedPublicationPlan"]["requiresConfirmation"] is True
            and plan["frameworkContentFingerprint"] == saved["contentFingerprint"],
            plan,
        )
        connection.execute("BEGIN IMMEDIATE")
        expect_error(
            "publication-rejects-a-different-preview-fingerprint",
            lambda: publish_decision_framework(
                connection,
                plan=plan,
                expected_plan_fingerprint="0" * 64,
                now_iso=lambda: NOW,
            ),
            "confirmation fingerprint",
        )
        connection.rollback()
        connection.execute("BEGIN IMMEDIATE")
        published = publish_decision_framework(
            connection,
            plan=plan,
            expected_plan_fingerprint=plan["planFingerprint"],
            now_iso=lambda: NOW,
        )
        connection.commit()
        check(
            "confirmed-publication-uses-reviewed-publication-ledger-and-freezes-draft",
            published["framework"]["status"] == "published"
            and published["framework"]["canEdit"] is False
            and published["framework"]["canPublish"] is False
            and published["framework"]["publication"]["canSupportCurrentDecision"] is True
            and str(published["publication"]["schema"]) == "aibi-reviewed-publication/v1"
            and published.get("ledgerEntry", {}).get("sequence") == 1,
            published,
        )
        connection.execute("BEGIN IMMEDIATE")
        expect_error(
            "published-framework-cannot-be-edited-in-place",
            lambda: save_decision_framework_draft(
                connection,
                workspace_id="default",
                framework_key=draft["frameworkKey"],
                title="Rewrite",
                claims=claims,
                expected_content_fingerprint=saved["contentFingerprint"],
                now_iso=lambda: NOW,
            ),
            "immutable",
        )
        connection.rollback()

        current_export = export_decision_framework(
            connection,
            workspace_id="default",
            framework_key=draft["frameworkKey"],
        )
        check(
            "current-export-is-a-current-decision-basis",
            current_export["currentDecisionBasis"] is True
            and current_export["staleEvidenceFactsUnloaded"] is False,
        )

        connection.execute("SAVEPOINT framework_tamper")
        tampered_claims = json.loads(connection.execute(
            "SELECT claims_json FROM decision_frameworks WHERE workspace_id = 'default' AND framework_key = ?",
            (draft["frameworkKey"],),
        ).fetchone()[0])
        tampered_claims[0]["text"] = "tampered evidence 999999"
        connection.execute(
            "UPDATE decision_frameworks SET claims_json = ? WHERE workspace_id = 'default' AND framework_key = ?",
            (json.dumps(tampered_claims), draft["frameworkKey"]),
        )
        tampered = get_decision_framework(connection, workspace_id="default", framework_key=draft["frameworkKey"])
        check(
            "local-framework-content-tamper-fails-integrity-and-unloads-fact",
            tampered["status"] == "integrity_failed"
            and "framework-content-integrity-failed" in tampered["freshness"]["blockers"]
            and next(item for item in tampered["claims"] if item["claimKind"] == "evidence_fact")["text"] == "",
            tampered,
        )
        connection.execute("ROLLBACK TO framework_tamper")
        connection.execute("RELEASE framework_tamper")

        connection.execute("UPDATE table_registry SET data_version = data_version + 1 WHERE workspace_id = 'default' AND table_key = 'orders'")
        connection.commit()
        stale = get_decision_framework(
            connection,
            workspace_id="default",
            framework_key=draft["frameworkKey"],
        )
        fact = next(item for item in stale["claims"] if item["claimKind"] == "evidence_fact")
        judgment = next(item for item in stale["claims"] if item["claimKind"] == "user_judgment")
        check(
            "drift-immediately-unloads-old-fact-text-and-numbers",
            stale["status"] == "stale"
            and stale["freshness"]["evidenceFactsUnloaded"] is True
            and fact["text"] == ""
            and fact["numberUnloaded"] is True
            and stale["evidenceCandidates"] == []
            and judgment["text"] == "The operator considers this concentration material.",
            stale,
        )
        stale_export = export_decision_framework(
            connection,
            workspace_id="default",
            framework_key=draft["frameworkKey"],
        )
        serialized_stale = json.dumps(stale_export, ensure_ascii=False)
        check(
            "ordinary-stale-export-does-not-leak-unloaded-evidence-number",
            stale_export["currentDecisionBasis"] is False
            and stale_export["staleEvidenceFactsUnloaded"] is True
            and candidate["text"] not in serialized_stale,
        )
        check(
            "list-is-bounded-and-returns-summary-without-claim-payload",
            len(list_decision_frameworks(connection, workspace_id="default", unit_key=unit_key, limit=1)) == 1
            and "claims" not in list_decision_frameworks(connection, workspace_id="default", unit_key=unit_key, limit=1)[0],
        )
        check(
            "cross-workspace-read-does-not-return-framework",
            get_decision_framework(connection, workspace_id="other", framework_key=draft["frameworkKey"]) is None,
        )
    failed = [item for item in checks if not item["ok"]]
    print(json.dumps({
        "ok": not failed,
        "schema": "aibi-decision-framework-verify/v1",
        "generatedBy": "scripts/verify-decision-framework.py",
        "checks": checks,
        "failedChecks": failed,
    }, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
