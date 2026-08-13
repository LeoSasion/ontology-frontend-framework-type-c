from __future__ import annotations

import math
import time
from statistics import mean
from typing import Any, Callable, Sequence

from evidence_retrieval_service import (
    DEFAULT_LEXICAL_THRESHOLD,
    DEFAULT_RRF_K,
    DEFAULT_VECTOR_THRESHOLD,
    RETRIEVAL_EVALUATION_SCHEMA,
    EmbeddingProvider,
    _baseline_score,
    _cosine,
    _embedding_text,
    _lexical_scores,
    _provider_signature,
    _signature_values,
    _jaccard,
    ensure_evidence_retrieval_schema,
    fingerprint,
    privacy_findings,
    stable_json,
)


MIN_RECALL_AT_3_GAIN = 0.05
MIN_MRR_GAIN = 0.03
MAX_P95_LATENCY_MS = 250.0
MAX_VECTOR_BYTES = 64 * 1024 * 1024


# Fixed, domain-neutral, synthetic corpus. It contains labels and confirmed
# question summaries only; no fixture is copied from a user workspace.
OFFLINE_CORPUS: tuple[dict[str, Any], ...] = (
    {
        "memoryKey": "metric_revenue_region",
        "workspaceId": "evaluation",
        "status": "confirmed",
        "current": True,
        "relationshipSafe": True,
        "permissionAllowed": True,
        "question": "Revenue by region",
        "signature": {"tables": ["orders"], "fields": ["orders.revenue", "orders.region"], "measure": "revenue", "groups": ["region"]},
    },
    {
        "memoryKey": "metric_profit_product",
        "workspaceId": "evaluation",
        "status": "confirmed",
        "current": True,
        "relationshipSafe": True,
        "permissionAllowed": True,
        "question": "Profit by product",
        "signature": {"tables": ["orders"], "fields": ["orders.profit", "orders.product"], "measure": "profit", "groups": ["product"]},
    },
    {
        "memoryKey": "metric_customer_country",
        "workspaceId": "evaluation",
        "status": "confirmed",
        "current": True,
        "relationshipSafe": True,
        "permissionAllowed": True,
        "question": "Customer count by country",
        "signature": {"tables": ["customers"], "fields": ["customers.customer_id", "customers.country"], "measure": "customer_count", "groups": ["country"]},
    },
    {
        "memoryKey": "metric_orders_month",
        "workspaceId": "evaluation",
        "status": "confirmed",
        "current": True,
        "relationshipSafe": True,
        "permissionAllowed": True,
        "question": "Monthly order trend",
        "signature": {"tables": ["orders"], "fields": ["orders.order_id", "orders.month"], "measure": "order_count", "groups": ["month"]},
    },
    {
        "memoryKey": "stale_revenue_region",
        "workspaceId": "evaluation",
        "status": "confirmed",
        "current": False,
        "relationshipSafe": True,
        "permissionAllowed": True,
        "question": "Regional sales",
        "signature": {"tables": ["orders"], "fields": ["orders.sales", "orders.region"], "measure": "sales", "groups": ["region"]},
    },
    {
        "memoryKey": "foreign_revenue_region",
        "workspaceId": "another-workspace",
        "status": "confirmed",
        "current": True,
        "relationshipSafe": True,
        "permissionAllowed": True,
        "question": "Revenue by region",
        "signature": {"tables": ["orders"], "fields": ["orders.revenue", "orders.region"], "measure": "revenue", "groups": ["region"]},
    },
    {
        "memoryKey": "unsafe_cross_table_margin",
        "workspaceId": "evaluation",
        "status": "confirmed",
        "current": True,
        "relationshipSafe": False,
        "permissionAllowed": True,
        "question": "Margin by customer segment",
        "signature": {"tables": ["orders", "customers"], "fields": ["orders.margin", "customers.segment"], "measure": "margin", "groups": ["segment"]},
    },
    {
        "memoryKey": "denied_salary_department",
        "workspaceId": "evaluation",
        "status": "confirmed",
        "current": True,
        "relationshipSafe": True,
        "permissionAllowed": False,
        "question": "Salary by department",
        "signature": {"tables": ["employees"], "fields": ["employees.salary", "employees.department"], "measure": "salary", "groups": ["department"]},
    },
    {
        "memoryKey": "sensitive_contact_metric",
        "workspaceId": "evaluation",
        "status": "confirmed",
        "current": True,
        "relationshipSafe": True,
        "permissionAllowed": True,
        "question": "Sales for analyst@example.com",
        "signature": {"tables": ["contacts"], "fields": ["contacts.sales"], "measure": "sales", "groups": []},
    },
)


OFFLINE_CASES: tuple[dict[str, Any], ...] = (
    {
        "caseKey": "synonym-en",
        "category": "synonym",
        "questionSummary": "Turnover across territories",
        "explicitTable": "orders",
        "expectedMemoryKey": "metric_revenue_region",
    },
    {
        "caseKey": "cross-language-zh-en",
        "category": "cross-language",
        "questionSummary": "各地区营业额",
        "explicitTable": "orders",
        "expectedMemoryKey": "metric_revenue_region",
    },
    {
        "caseKey": "field-competition",
        "category": "field-competition",
        "questionSummary": "Which merchandise earns the most margin",
        "explicitTable": "orders",
        "expectedMemoryKey": "metric_profit_product",
    },
    {
        "caseKey": "cross-table-hard-filter",
        "category": "cross-table",
        "questionSummary": "Count buyers in every nation",
        "explicitTable": "customers",
        "expectedMemoryKey": "metric_customer_country",
    },
    {
        "caseKey": "stale-hard-filter",
        "category": "stale",
        "questionSummary": "Regional sales",
        "explicitTable": "orders",
        "expectedMemoryKey": "metric_revenue_region",
    },
    {
        "caseKey": "direct-baseline",
        "category": "direct",
        "questionSummary": "Monthly order trend",
        "explicitTable": "orders",
        "expectedMemoryKey": "metric_orders_month",
    },
    {
        "caseKey": "no-match",
        "category": "no-match",
        "questionSummary": "Warehouse shelf temperature",
        "explicitTable": "inventory",
        "expectedMemoryKey": None,
    },
    {
        "caseKey": "pii-corpus-exclusion",
        "category": "privacy",
        "questionSummary": "Contact sales overview",
        "explicitTable": "contacts",
        "expectedMemoryKey": None,
    },
)


def _hard_filter(case: dict[str, Any], candidate: dict[str, Any]) -> bool:
    tables = set(candidate.get("signature", {}).get("tables") or [])
    explicit_table = str(case.get("explicitTable") or "")
    return (
        candidate.get("workspaceId") == "evaluation"
        and candidate.get("status") == "confirmed"
        and candidate.get("current") is True
        and candidate.get("relationshipSafe") is True
        and candidate.get("permissionAllowed") is True
        and (not explicit_table or explicit_table in tables)
    )


def _baseline_rank(case: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    question = str(case["questionSummary"])
    ranked: list[dict[str, Any]] = []
    for candidate in candidates:
        channels = _lexical_scores(question, candidate["signature"], candidate["question"])
        score = _baseline_score(channels, 0.0, False)
        ranked.append({**candidate, "baselineScore": score, "channels": channels})
    ranked.sort(key=lambda item: (-item["baselineScore"], item["memoryKey"]))
    return [item for item in ranked if item["baselineScore"] >= DEFAULT_LEXICAL_THRESHOLD]


def _hybrid_rank(
    case: dict[str, Any],
    candidates: list[dict[str, Any]],
    provider: EmbeddingProvider,
) -> tuple[list[dict[str, Any]], float, int, int]:
    question = str(case["questionSummary"])
    if privacy_findings(question):
        raise ValueError("Offline evaluation question contains prohibited PII")
    baseline_all: list[dict[str, Any]] = []
    provider_candidates: list[dict[str, Any]] = []
    provider_inputs: list[str] = []
    privacy_excluded = 0
    for candidate in candidates:
        channels = _lexical_scores(question, candidate["signature"], candidate["question"])
        baseline_all.append({**candidate, "baselineScore": _baseline_score(channels, 0.0, False), "channels": channels})
        text = _embedding_text(candidate["question"], candidate["signature"])
        if privacy_findings(text):
            privacy_excluded += 1
            continue
        provider_candidates.append(candidate)
        provider_inputs.append(text)
    query_input = _embedding_text(question, {"tables": [case["explicitTable"]], "fields": [], "measure": "", "groups": []})
    started = time.perf_counter()
    vectors = list(provider.embed([query_input, *provider_inputs]))
    latency_ms = (time.perf_counter() - started) * 1_000
    if len(vectors) != len(provider_inputs) + 1:
        raise ValueError("Embedding Provider returned an unexpected vector count")
    vector_bytes = sum(len(vector) * 8 for vector in vectors)
    query_vector = vectors[0]
    vector_scores = {
        candidate["memoryKey"]: _cosine(query_vector, vector)
        for candidate, vector in zip(provider_candidates, vectors[1:])
    }
    baseline_all.sort(key=lambda item: (-item["baselineScore"], item["memoryKey"]))
    lexical_rank = {item["memoryKey"]: index for index, item in enumerate(baseline_all, start=1)}
    vector_order = sorted(vector_scores, key=lambda key: (-vector_scores[key], key))
    vector_rank = {key: index for index, key in enumerate(vector_order, start=1)}
    ranked: list[dict[str, Any]] = []
    maximum = 2 / (DEFAULT_RRF_K + 1)
    for item in baseline_all:
        key = item["memoryKey"]
        vector = vector_scores.get(key, 0.0)
        if key in vector_rank:
            rrf = (1 / (DEFAULT_RRF_K + lexical_rank[key]) + 1 / (DEFAULT_RRF_K + vector_rank[key])) / maximum
        else:
            rrf = item["baselineScore"]
        if item["baselineScore"] >= DEFAULT_LEXICAL_THRESHOLD or vector >= DEFAULT_VECTOR_THRESHOLD:
            ranked.append({**item, "vectorScore": vector, "hybridScore": rrf})
    ranked.sort(key=lambda item: (-item["hybridScore"], item["memoryKey"]))
    return ranked, latency_ms, vector_bytes, privacy_excluded


def _quality(case_results: list[dict[str, Any]], mode: str) -> dict[str, float]:
    eligible = [item for item in case_results if item["expectedMemoryKey"]]
    hits = 0
    reciprocal: list[float] = []
    for item in eligible:
        keys = item[f"{mode}Keys"]
        expected = item["expectedMemoryKey"]
        if expected in keys[:3]:
            hits += 1
        reciprocal.append(1 / (keys.index(expected) + 1) if expected in keys else 0.0)
    return {
        "recallAt3": hits / len(eligible) if eligible else 0.0,
        "mrr": mean(reciprocal) if reciprocal else 0.0,
    }


def evaluate_embedding_provider(
    *,
    provider: EmbeddingProvider,
    workspace_id: str,
    now_iso: Callable[[], str],
    connection: Any | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    provider_signature = _provider_signature(provider)
    cases: list[dict[str, Any]] = []
    latencies: list[float] = []
    vector_bytes = 0
    privacy_excluded = 0
    provider_error = ""
    for case in OFFLINE_CASES:
        candidates = [dict(item) for item in OFFLINE_CORPUS if _hard_filter(case, item)]
        baseline = _baseline_rank(case, candidates)
        try:
            hybrid, latency_ms, used_bytes, excluded = _hybrid_rank(case, candidates, provider)
        except Exception as error:
            provider_error = type(error).__name__
            hybrid, latency_ms, used_bytes, excluded = [], 0.0, 0, 0
        latencies.append(latency_ms)
        vector_bytes += used_bytes
        privacy_excluded += excluded
        cases.append({
            "caseKey": case["caseKey"],
            "category": case["category"],
            "expectedMemoryKey": case["expectedMemoryKey"],
            "explicitTable": case["explicitTable"],
            "baselineKeys": [item["memoryKey"] for item in baseline],
            "hybridKeys": [item["memoryKey"] for item in hybrid],
        })

    baseline_quality = _quality(cases, "baseline")
    hybrid_quality = _quality(cases, "hybrid")
    recall_gain = hybrid_quality["recallAt3"] - baseline_quality["recallAt3"]
    mrr_gain = hybrid_quality["mrr"] - baseline_quality["mrr"]
    sorted_latencies = sorted(latencies)
    latency_index = max(0, math.ceil(len(sorted_latencies) * 0.95) - 1)
    p95_latency = sorted_latencies[latency_index] if sorted_latencies else 0.0

    visible_keys = {item["memoryKey"]: item for item in OFFLINE_CORPUS}
    returned = [key for case in cases for key in case["hybridKeys"]]
    cross_workspace_hits = sum(1 for key in returned if visible_keys[key]["workspaceId"] != "evaluation")
    stale_hits = sum(1 for key in returned if visible_keys[key]["current"] is not True)
    unsafe_relationship_hits = sum(1 for key in returned if visible_keys[key]["relationshipSafe"] is not True)
    permission_leaks = sum(1 for key in returned if visible_keys[key]["permissionAllowed"] is not True)
    wrong_table_hits = 0
    no_match_false_positives = 0
    for case in cases:
        if case["expectedMemoryKey"] is None and case["hybridKeys"]:
            no_match_false_positives += len(case["hybridKeys"])
        for key in case["hybridKeys"]:
            if case["explicitTable"] not in set(visible_keys[key]["signature"].get("tables") or []):
                wrong_table_hits += 1
    zero_tolerance = {
        "workspaceIsolation": cross_workspace_hits == 0,
        "staleCandidateExclusion": stale_hits == 0,
        "wrongExplicitTableExclusion": wrong_table_hits == 0,
        "unsafeRelationshipExclusion": unsafe_relationship_hits == 0,
        "permissionIsolation": permission_leaks == 0,
        "noMatchSafety": no_match_false_positives == 0,
    }
    quality_passed = recall_gain >= MIN_RECALL_AT_3_GAIN and mrr_gain >= MIN_MRR_GAIN
    performance_passed = p95_latency <= MAX_P95_LATENCY_MS and vector_bytes <= MAX_VECTOR_BYTES
    privacy = {
        "rawRowCount": 0,
        "piiFindingCount": 0,
        "privacyExcludedCandidateCount": privacy_excluded,
        "providerInputContract": "fixed-confirmed-summary-and-schema-labels-only",
    }
    thresholds_passed = quality_passed and performance_passed and all(zero_tolerance.values()) and not provider_error
    created_at = now_iso()
    corpus_fingerprint = fingerprint({"corpus": OFFLINE_CORPUS, "cases": OFFLINE_CASES})
    evaluation_key = f"retrieval_evaluation_{fingerprint({'workspaceId': workspace_id, 'provider': provider_signature, 'corpus': corpus_fingerprint, 'createdAt': created_at})[:20]}"
    result = {
        "schema": RETRIEVAL_EVALUATION_SCHEMA,
        "evaluationKey": evaluation_key,
        "workspaceId": workspace_id,
        "providerSignature": provider_signature,
        "status": "passed" if thresholds_passed else "rejected",
        "thresholdsPassed": thresholds_passed,
        "thresholds": {
            "minimumRecallAt3Gain": MIN_RECALL_AT_3_GAIN,
            "minimumMrrGain": MIN_MRR_GAIN,
            "maximumP95LatencyMs": MAX_P95_LATENCY_MS,
            "maximumVectorBytes": MAX_VECTOR_BYTES,
        },
        "baseline": baseline_quality,
        "hybrid": hybrid_quality,
        "gains": {"recallAt3": recall_gain, "mrr": mrr_gain},
        "performance": {"p95LatencyMs": p95_latency, "vectorBytes": vector_bytes},
        "privacy": privacy,
        "zeroTolerance": zero_tolerance,
        "zeroToleranceCounts": {
            "crossWorkspaceHitCount": cross_workspace_hits,
            "staleCandidateHitCount": stale_hits,
            "wrongExplicitTableHitCount": wrong_table_hits,
            "unsafeRelationshipHitCount": unsafe_relationship_hits,
            "permissionLeakCount": permission_leaks,
            "noMatchFalsePositiveCount": no_match_false_positives,
        },
        "providerErrorClass": provider_error or None,
        "corpusFingerprint": corpus_fingerprint,
        "cases": cases,
        "createdAt": created_at,
    }
    result["evaluationFingerprint"] = fingerprint(result)
    if persist:
        if connection is None:
            raise ValueError("Persisting retrieval evaluation requires a workspace database connection")
        if not connection.in_transaction:
            raise RuntimeError("Retrieval evaluation writes require the caller to hold BEGIN IMMEDIATE")
        ensure_evidence_retrieval_schema(connection)
        connection.execute(
            """
            INSERT OR REPLACE INTO retrieval_evaluation_runs(
              evaluation_key, workspace_id, provider_signature, status, evaluation_json, created_at
            ) VALUES(?, ?, ?, ?, ?, ?)
            """,
            (evaluation_key, workspace_id, provider_signature, result["status"], stable_json(result), created_at),
        )
    return result
