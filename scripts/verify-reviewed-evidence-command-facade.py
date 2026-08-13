from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import reviewed_evidence_commands as facade  # noqa: E402


NOW = "2026-08-13T09:00:00Z"
SHA = "a" * 64


class SyntheticSemanticProvider:
    signature = "local:facade-fixture-v1"

    @staticmethod
    def _vector(text: str) -> list[float]:
        value = text.casefold()

        def has(*tokens: str) -> float:
            return 1.0 if any(token.casefold() in value for token in tokens) else 0.0

        return [
            has("revenue", "turnover", "sales", "营业额", "销售额"),
            has("region", "territor", "地区", "regional"),
            has("profit", "margin"),
            has("product", "merchandise"),
            has("customer", "buyer"),
            has("country", "nation"),
            has("month", "monthly", "trend"),
            has("order"),
        ]

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        return [self._vector(text) for text in texts]


def main() -> int:
    checks: list[dict[str, Any]] = []

    def check(label: str, ok: Any, detail: Any = None) -> None:
        checks.append({"label": label, "ok": bool(ok), "detail": None if ok else detail})

    def expect_error(label: str, callback, fragment: str) -> None:
        try:
            callback()
        except Exception as error:  # noqa: BLE001 - contract test records stable public failure.
            check(label, fragment.casefold() in str(error).casefold(), str(error))
        else:
            check(label, False, "expected an exception")

    with tempfile.TemporaryDirectory(prefix="aibi-c-reviewed-evidence-facade-") as temp_dir:
        db_path = Path(temp_dir) / "facade.sqlite"

        def open_db() -> sqlite3.Connection:
            connection = sqlite3.connect(db_path)
            connection.row_factory = sqlite3.Row
            return connection

        def active_workspace_id(_connection: sqlite3.Connection) -> str:
            return "default"

        def now_iso() -> str:
            return NOW

        missing_provider = facade.evidence_retrieval_evaluate_command(
            SimpleNamespace(provider_profile=""),
            open_db=open_db,
            active_workspace_id=active_workspace_id,
            now_iso=now_iso,
        )
        missing_payload = missing_provider["evidenceRetrievalEvaluation"]
        check(
            "missing-approved-provider-is-explicitly-lexical-degraded",
            missing_payload["mode"] == "lexical_degraded"
            and missing_payload["evaluationPerformed"] is False
            and missing_payload["embeddingAdopted"] is False
            and missing_payload["degradationReason"] == "approved-provider-unavailable",
            missing_payload,
        )
        resolver_failure = facade.evidence_retrieval_evaluate_command(
            SimpleNamespace(provider_profile="fixture-failure"),
            open_db=open_db,
            active_workspace_id=active_workspace_id,
            now_iso=now_iso,
            resolve_approved_provider=lambda _profile: (_ for _ in ()).throw(RuntimeError("private resolver detail")),
        )["evidenceRetrievalEvaluation"]
        check(
            "provider-resolution-failure-degrades-without-leaking-detail",
            resolver_failure["mode"] == "lexical_degraded"
            and resolver_failure["degradationReason"] == "approved-provider-resolution-failed"
            and resolver_failure["providerResolutionErrorClass"] == "RuntimeError"
            and "private resolver detail" not in json.dumps(resolver_failure, ensure_ascii=False),
            resolver_failure,
        )

        resolved_profiles: list[str] = []

        def resolve_approved_provider(profile: str):
            resolved_profiles.append(profile)
            return SyntheticSemanticProvider() if profile == "fixture-v1" else None

        evaluated = facade.evidence_retrieval_evaluate_command(
            SimpleNamespace(provider_profile="fixture-v1"),
            open_db=open_db,
            active_workspace_id=active_workspace_id,
            now_iso=now_iso,
            resolve_approved_provider=resolve_approved_provider,
        )
        evaluation_payload = evaluated["evidenceRetrievalEvaluation"]
        check(
            "approved-profile-is-resolved-only-by-server-owned-callback",
            resolved_profiles == ["fixture-v1"],
            resolved_profiles,
        )
        check(
            "passing-evaluation-cannot-self-enable-embedding",
            evaluation_payload["evaluation"]["status"] == "passed"
            and evaluation_payload["mode"] == "lexical_degraded"
            and evaluation_payload["embeddingAdopted"] is False
            and evaluation_payload["evaluationCanSelfEnableEmbedding"] is False
            and evaluation_payload["adoptionStatus"] == "eligible-for-explicit-review",
            evaluation_payload,
        )
        check(
            "evaluation-retains-zero-disclosure-proof",
            evaluation_payload["evaluation"]["privacy"]["rawRowCount"] == 0
            and evaluation_payload["evaluation"]["privacy"]["piiFindingCount"] == 0
            and all(evaluation_payload["evaluation"]["zeroTolerance"].values()),
            evaluation_payload["evaluation"],
        )

        status = facade.evidence_retrieval_status_command(
            SimpleNamespace(),
            open_db=open_db,
            active_workspace_id=active_workspace_id,
        )["evidenceRetrievalStatus"]
        check(
            "status-reports-persisted-evaluation-as-informational-not-adoption",
            status["mode"] == "lexical_degraded"
            and status["embeddingAdopted"] is False
            and status["latestEvaluation"]["status"] == "passed"
            and status["latestEvaluation"]["informationalOnly"] is True,
            status,
        )

        safe_receipt = {
            "schema": "aibi-evidence-retrieval-receipt/v1",
            "receiptKey": "safe-receipt",
            "workspaceId": "default",
            "mode": "lexical_degraded",
            "requestHash": SHA,
            "candidates": [],
            "returnedCandidates": [],
            "privacy": {"rawRowCount": 0, "rawRowsSent": False, "piiFindingCount": 0},
            "createdAt": NOW,
        }
        with closing(open_db()) as connection:
            connection.execute(
                """
                INSERT INTO evidence_retrieval_receipts(
                  receipt_key, workspace_id, request_hash, status, mode,
                  provider_signature, corpus_fingerprint, receipt_json, created_at
                ) VALUES(?, 'default', ?, 'no-match', 'lexical_degraded', '', ?, ?, ?)
                """,
                ("safe-receipt", SHA, SHA, json.dumps(safe_receipt), NOW),
            )
            connection.commit()
        receipts = facade.evidence_retrieval_receipts_command(
            SimpleNamespace(limit=10),
            open_db=open_db,
            active_workspace_id=active_workspace_id,
        )
        check(
            "receipt-list-remains-degraded-and-does-not-return-question-text",
            receipts["mode"] == "lexical_degraded"
            and receipts["embeddingAdopted"] is False
            and receipts["count"] == 1
            and "question" not in json.dumps(receipts, ensure_ascii=False).casefold(),
            receipts,
        )

        malicious_receipt = {
            **safe_receipt,
            "receiptKey": "unsafe-receipt",
            "rawRows": [{"email": "analyst@example.com"}],
        }
        with closing(open_db()) as connection:
            connection.execute(
                """
                INSERT INTO evidence_retrieval_receipts(
                  receipt_key, workspace_id, request_hash, status, mode,
                  provider_signature, corpus_fingerprint, receipt_json, created_at
                ) VALUES(?, 'default', ?, 'no-match', 'lexical_degraded', '', ?, ?, ?)
                """,
                ("unsafe-receipt", SHA, SHA, json.dumps(malicious_receipt), "2026-08-13T09:01:00Z"),
            )
            connection.commit()
        expect_error(
            "stored-receipt-cannot-smuggle-raw-evidence-or-pii-through-facade",
            lambda: facade.evidence_retrieval_receipts_command(
                SimpleNamespace(limit=10),
                open_db=open_db,
                active_workspace_id=active_workspace_id,
            ),
            "forbidden field",
        )
        with closing(open_db()) as connection:
            connection.execute(
                "DELETE FROM evidence_retrieval_receipts WHERE receipt_key = 'unsafe-receipt'"
            )
            connection.commit()

        originals = {
            "build": facade.build_reviewed_publication_plan,
            "publish": facade.publish_reviewed_artifact,
            "list": facade.list_reviewed_publications,
            "evaluate": facade.evaluate_reviewed_publication,
            "deprecate": facade.deprecate_reviewed_publication,
            "export": facade.reviewed_publication_export,
        }
        calls: list[str] = []

        def fake_plan(connection: sqlite3.Connection, **kwargs):
            calls.append("plan")
            return {
                "schema": "aibi-reviewed-publication-plan/v1",
                "workspaceId": kwargs["workspace_id"],
                "publicationKey": "publication-safe",
                "memoryKey": kwargs["memory_key"],
                "unitKey": kwargs["unit_key"],
                "title": kwargs["title"],
                "content": kwargs["content"],
                "planFingerprint": SHA,
                "requiresConfirmation": True,
            }

        def fake_publish(connection: sqlite3.Connection, **kwargs):
            calls.append("publish")
            if not connection.in_transaction:
                raise AssertionError("publish must hold BEGIN IMMEDIATE")
            if kwargs["expected_plan_fingerprint"] != SHA:
                raise AssertionError("confirmation fingerprint mismatch")
            return {"publication": {"publicationKey": "publication-safe", "status": "current"}, "created": True}

        def fake_list(_connection: sqlite3.Connection, **_kwargs):
            calls.append("list")
            return [{"publicationKey": "publication-safe"}]

        def fake_evaluate(_connection: sqlite3.Connection, **kwargs):
            calls.append("evaluate")
            return {
                "publicationKey": kwargs["publication_key"],
                "workspaceId": kwargs["workspace_id"],
                "status": "current",
                "ledgerHeadHash": SHA,
                "canSupportCurrentDecision": True,
            }

        def fake_deprecate(connection: sqlite3.Connection, **kwargs):
            calls.append("deprecate")
            if not connection.in_transaction:
                raise AssertionError("deprecate must hold BEGIN IMMEDIATE")
            return {"publication": {"publicationKey": kwargs["publication_key"], "status": "deprecated"}, "deprecated": True}

        def fake_export(_connection: sqlite3.Connection, **kwargs):
            calls.append("export")
            return {
                "schema": "aibi-reviewed-publication-export/v1",
                "workspaceId": kwargs["workspace_id"],
                "publication": {"publicationKey": kwargs["publication_key"], "status": "current"},
                "ledgerEntries": [],
                "currentDecisionBasis": True,
                "forensic": kwargs["forensic"],
            }

        facade.build_reviewed_publication_plan = fake_plan
        facade.publish_reviewed_artifact = fake_publish
        facade.list_reviewed_publications = fake_list
        facade.evaluate_reviewed_publication = fake_evaluate
        facade.deprecate_reviewed_publication = fake_deprecate
        facade.reviewed_publication_export = fake_export
        try:
            common = {
                "memory": "memory-safe",
                "unit": "unit-safe",
                "title": "Reviewed result",
                "content_json": json.dumps({"summary": "Current reviewed result"}),
                "skill_fingerprint": "",
            }
            plan_result = facade.reviewed_publication_plan_command(
                SimpleNamespace(**common),
                open_db=open_db,
                active_workspace_id=active_workspace_id,
            )
            publish_result = facade.reviewed_publication_publish_command(
                SimpleNamespace(**common, expected_plan=SHA, yes=True),
                open_db=open_db,
                active_workspace_id=active_workspace_id,
                now_iso=now_iso,
            )
            list_result = facade.reviewed_publications_command(
                SimpleNamespace(publication="", status="", limit=10, skill_fingerprint=""),
                open_db=open_db,
                active_workspace_id=active_workspace_id,
            )
            deprecate_preview = facade.reviewed_publication_deprecate_command(
                SimpleNamespace(publication="publication-safe", expected_head="", reason="superseded", yes=False),
                open_db=open_db,
                active_workspace_id=active_workspace_id,
                now_iso=now_iso,
            )
            deprecate_result = facade.reviewed_publication_deprecate_command(
                SimpleNamespace(publication="publication-safe", expected_head=SHA, reason="superseded", yes=True),
                open_db=open_db,
                active_workspace_id=active_workspace_id,
                now_iso=now_iso,
            )
            export_result = facade.reviewed_publication_export_command(
                SimpleNamespace(publication="publication-safe", skill_fingerprint="", forensic=False),
                open_db=open_db,
                active_workspace_id=active_workspace_id,
            )
            check(
                "w4-facade-covers-plan-publish-list-deprecate-and-export",
                plan_result["dryRun"] is True
                and publish_result["confirmed"] is True
                and list_result["count"] == 1
                and deprecate_preview["expectedHeadHash"] == SHA
                and deprecate_result["publication"]["status"] == "deprecated"
                and export_result["reviewedPublicationExport"]["currentDecisionBasis"] is True
                and {"plan", "publish", "list", "evaluate", "deprecate", "export"}.issubset(calls),
                {"calls": calls},
            )

            facade.evaluate_reviewed_publication = lambda *_args, **_kwargs: {
                "publicationKey": "publication-unsafe",
                "status": "current",
                "summary": "Contact analyst@example.com",
            }
            expect_error(
                "w4-underlying-service-output-cannot-leak-pii",
                lambda: facade.reviewed_publications_command(
                    SimpleNamespace(publication="publication-unsafe", status="", limit=10, skill_fingerprint=""),
                    open_db=open_db,
                    active_workspace_id=active_workspace_id,
                ),
                "potential pii",
            )
            expect_error(
                "w4-list-rejects-unknown-status-before-query",
                lambda: facade.reviewed_publications_command(
                    SimpleNamespace(publication="", status="invented", limit=10, skill_fingerprint=""),
                    open_db=open_db,
                    active_workspace_id=active_workspace_id,
                ),
                "unsupported reviewed publication status",
            )
        finally:
            facade.build_reviewed_publication_plan = originals["build"]
            facade.publish_reviewed_artifact = originals["publish"]
            facade.list_reviewed_publications = originals["list"]
            facade.evaluate_reviewed_publication = originals["evaluate"]
            facade.deprecate_reviewed_publication = originals["deprecate"]
            facade.reviewed_publication_export = originals["export"]

        expect_error(
            "provider-profile-cannot-be-a-path-or-credential",
            lambda: facade.evidence_retrieval_evaluate_command(
                SimpleNamespace(provider_profile="C:\\private\\provider"),
                open_db=open_db,
                active_workspace_id=active_workspace_id,
                now_iso=now_iso,
                resolve_approved_provider=resolve_approved_provider,
            ),
            "server-owned identifier",
        )
        expect_error(
            "direct-output-guard-rejects-absolute-paths",
            lambda: facade._assert_public_output({"value": "C:\\Users\\private\\data.csv"}),
            "absolute path",
        )
        expect_error(
            "direct-output-guard-rejects-secrets",
            lambda: facade._assert_public_output({"value": "password=hunter2"}),
            "credential-like",
        )
        expect_error(
            "direct-output-guard-rejects-secret-bearing-field-names",
            lambda: facade._assert_public_output({"apiKey": "redacted"}),
            "forbidden field",
        )
        expect_error(
            "direct-output-guard-rejects-raw-evidence-rows",
            lambda: facade._assert_public_output({"rawRows": [{"value": 1}]}),
            "forbidden field",
        )

    failed = [item for item in checks if not item["ok"]]
    print(json.dumps({
        "ok": not failed,
        "schema": "aibi-reviewed-evidence-command-facade-verify/v1",
        "generatedBy": "scripts/verify-reviewed-evidence-command-facade.py",
        "checks": checks,
        "failedChecks": failed,
    }, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
