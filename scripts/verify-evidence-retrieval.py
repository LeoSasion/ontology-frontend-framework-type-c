from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from evidence_retrieval_service import (  # noqa: E402
    RetrievalPolicy,
    fingerprint,
    retrieve_confirmed_evidence,
)
from retrieval_evaluation_service import evaluate_embedding_provider  # noqa: E402


NOW = "2026-08-13T08:00:00Z"


class RecordingSemanticProvider:
    signature = "local:semantic-fixture-v1"

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

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
        self.calls.append(list(texts))
        return [self._vector(text) for text in texts]


class FailingProvider(RecordingSemanticProvider):
    signature = "local:failing-fixture-v1"

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        self.calls.append(list(texts))
        raise RuntimeError("simulated provider failure")


def memory(
    connection: sqlite3.Connection,
    *,
    key: str,
    receipt: str,
    question: str,
    tables: list[str],
    fields: list[str],
    measure: str,
    groups: list[str],
    binding: str,
) -> None:
    connection.execute(
        """
        INSERT INTO confirmed_plan_memories(
          memory_key, workspace_id, query_key, query_receipt_key, question, status,
          plan_json, signature_json, binding_fingerprint, evidence_json,
          created_at, updated_at, confirmed_at, stale_reason
        ) VALUES(?, 'default', ?, ?, ?, 'confirmed', '{}', ?, ?, '[]', ?, ?, ?, '')
        """,
        (
            key,
            f"query_{key}",
            receipt,
            question,
            json.dumps({"tables": tables, "fields": fields, "measure": measure, "groups": groups}, ensure_ascii=False),
            binding,
            NOW,
            NOW,
            NOW,
        ),
    )


def main() -> int:
    checks: list[dict[str, object]] = []

    def check(label: str, ok: object, detail: object = None) -> None:
        checks.append({"label": label, "ok": bool(ok), "detail": detail})

    provider = RecordingSemanticProvider()
    evaluation = evaluate_embedding_provider(
        provider=provider,
        workspace_id="default",
        now_iso=lambda: NOW,
    )
    check(
        "offline-evaluation-passes-fixed-quality-and-zero-tolerance-gates",
        evaluation["status"] == "passed"
        and evaluation["thresholdsPassed"] is True
        and evaluation["gains"]["recallAt3"] >= evaluation["thresholds"]["minimumRecallAt3Gain"]
        and evaluation["gains"]["mrr"] >= evaluation["thresholds"]["minimumMrrGain"]
        and all(evaluation["zeroTolerance"].values()),
        evaluation,
    )
    check(
        "offline-provider-inputs-contain-no-pii-or-raw-rows",
        evaluation["privacy"]["rawRowCount"] == 0
        and evaluation["privacy"]["piiFindingCount"] == 0
        and evaluation["privacy"]["privacyExcludedCandidateCount"] >= 1
        and all("analyst@example.com" not in text for call in provider.calls for text in call),
    )

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE confirmed_plan_memories (
          memory_key TEXT, workspace_id TEXT, query_key TEXT, query_receipt_key TEXT,
          question TEXT, status TEXT, plan_json TEXT, signature_json TEXT,
          binding_fingerprint TEXT, evidence_json TEXT, created_at TEXT,
          updated_at TEXT, confirmed_at TEXT, stale_reason TEXT
        );
        """
    )
    memory(
        connection,
        key="good",
        receipt="receipt-good",
        question="Revenue by region",
        tables=["orders"],
        fields=["orders.revenue", "orders.region"],
        measure="revenue",
        groups=["region"],
        binding="binding-good",
    )
    memory(
        connection,
        key="wrong-table",
        receipt="receipt-wrong-table",
        question="Revenue by region",
        tables=["customers"],
        fields=["customers.revenue", "customers.region"],
        measure="revenue",
        groups=["region"],
        binding="binding-wrong-table",
    )
    memory(
        connection,
        key="stale",
        receipt="receipt-stale",
        question="Regional turnover",
        tables=["orders"],
        fields=["orders.turnover", "orders.region"],
        measure="turnover",
        groups=["region"],
        binding="binding-stale",
    )
    memory(
        connection,
        key="binding-drifted",
        receipt="receipt-binding",
        question="Territory sales",
        tables=["orders"],
        fields=["orders.sales", "orders.territory"],
        measure="sales",
        groups=["territory"],
        binding="old-binding",
    )
    memory(
        connection,
        key="not-executed",
        receipt="receipt-draft",
        question="Draft revenue",
        tables=["orders"],
        fields=["orders.revenue"],
        measure="revenue",
        groups=[],
        binding="binding-draft",
    )
    memory(
        connection,
        key="denied",
        receipt="receipt-denied",
        question="Denied private revenue",
        tables=["orders"],
        fields=["orders.private_revenue"],
        measure="private_revenue",
        groups=[],
        binding="binding-denied",
    )
    receipts = {
        "receipt-good": {"status": "executed", "binding": "binding-good"},
        "receipt-wrong-table": {"status": "executed", "binding": "binding-wrong-table"},
        "receipt-stale": {"status": "executed", "binding": "binding-stale", "stale": True},
        "receipt-binding": {"status": "executed", "binding": "new-binding"},
        "receipt-draft": {"status": "draft", "binding": "binding-draft"},
        "receipt-denied": {"status": "executed", "binding": "binding-denied"},
    }

    def receipt_lookup(_connection: sqlite3.Connection, _workspace: str, receipt_key: str):
        return receipts.get(receipt_key)

    def source_state(_connection: sqlite3.Connection, _workspace: str, receipt: dict[str, object]):
        return {"matchesReceipt": receipt.get("stale") is not True}

    def binding(receipt: dict[str, object]) -> str:
        return str(receipt["binding"])

    common = {
        "connection": connection,
        "workspace_id": "default",
        "prompt": "Turnover across territories",
        "explicit_table_key": "orders",
        "semantic_plan": None,
        "planning_binding_fingerprint": "3" * 64,
        "now_iso": lambda: NOW,
        "receipt_lookup": receipt_lookup,
        "source_state_resolver": source_state,
        "binding_fingerprint_resolver": binding,
        "permission_filter": lambda item: item["memoryKey"] != "denied",
        "persist_receipt": False,
    }
    before_calls = len(provider.calls)
    degraded = retrieve_confirmed_evidence(**common)
    check(
        "default-is-lexical-degraded-and-never-calls-provider",
        degraded["receipt"]["mode"] == "lexical_degraded"
        and degraded["receipt"]["degradationReason"] == "provider-disabled"
        and len(provider.calls) == before_calls,
    )
    check(
        "hard-filters-run-before-any-vector-channel",
        degraded["receipt"]["hardFilterCounts"] == {
            "notExecuted": 1,
            "notCurrent": 1,
            "bindingDrifted": 1,
            "wrongExplicitTable": 1,
            "permissionDenied": 1,
        }
        and [item["memoryKey"] for item in degraded["receipt"]["candidates"]] == ["good"],
        degraded["receipt"],
    )
    hybrid = retrieve_confirmed_evidence(
        **common,
        policy=RetrievalPolicy(explicit_vector_opt_in=True),
        provider=provider,
        evaluation_gate=evaluation,
        confirmed_question_summary="Turnover across territories",
    )
    check(
        "passed-gate-enables-provider-neutral-rrf-with-candidate-only-policy",
        hybrid["receipt"]["mode"] == "hybrid_rrf"
        and hybrid["receipt"]["policy"]["strategy"] == "rrf"
        and hybrid["receipt"]["policy"]["canAuthorizeExecution"] is False
        and hybrid["receipt"]["returnedCandidates"][0]["memoryKey"] == "good"
        and hybrid["receipt"]["privacy"]["rawRowCount"] == 0,
        hybrid["receipt"],
    )
    runtime_inputs = provider.calls[-1]
    check(
        "provider-sees-only-hard-filtered-confirmed-summary-and-labels",
        all(token not in "\n".join(runtime_inputs) for token in ["private_revenue", "old-binding", "receipt-stale", "customers.revenue"])
        and all("rows" not in text.casefold() for text in runtime_inputs),
        runtime_inputs,
    )
    calls_before_pii = len(provider.calls)
    pii = retrieve_confirmed_evidence(
        **common,
        policy=RetrievalPolicy(explicit_vector_opt_in=True),
        provider=provider,
        evaluation_gate=evaluation,
        confirmed_question_summary="Turnover for analyst@example.com",
    )
    check(
        "pii-summary-fails-closed-to-lexical-without-provider-call",
        pii["receipt"]["mode"] == "lexical_degraded"
        and pii["receipt"]["degradationReason"] == "confirmed-question-summary-sensitive"
        and len(provider.calls) == calls_before_pii,
    )
    tampered_gate = {**evaluation, "thresholdsPassed": False}
    tampered = retrieve_confirmed_evidence(
        **common,
        policy=RetrievalPolicy(explicit_vector_opt_in=True),
        provider=provider,
        evaluation_gate=tampered_gate,
        confirmed_question_summary="Turnover across territories",
    )
    check(
        "tampered-evaluation-gate-cannot-enable-vector-channel",
        tampered["receipt"]["mode"] == "lexical_degraded"
        and tampered["receipt"]["degradationReason"] == "evaluation-gate-not-passed",
    )
    failing = FailingProvider()
    failing_evaluation = {**evaluation, "providerSignature": failing.signature}
    failing_evaluation["evaluationFingerprint"] = fingerprint({key: value for key, value in failing_evaluation.items() if key != "evaluationFingerprint"})
    failed_provider = retrieve_confirmed_evidence(
        **common,
        policy=RetrievalPolicy(explicit_vector_opt_in=True),
        provider=failing,
        evaluation_gate=failing_evaluation,
        confirmed_question_summary="Turnover across territories",
    )
    check(
        "provider-errors-degrade-without-losing-deterministic-results",
        failed_provider["receipt"]["mode"] == "lexical_degraded"
        and failed_provider["receipt"]["degradationReason"] == "provider-error"
        and failed_provider["receipt"]["providerErrorClass"] == "RuntimeError",
    )

    failed = [item for item in checks if not item["ok"]]
    print(json.dumps({
        "ok": not failed,
        "schema": "aibi-evidence-retrieval-verify/v1",
        "generatedBy": "scripts/verify-evidence-retrieval.py",
        "checks": checks,
        "failedChecks": failed,
    }, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
