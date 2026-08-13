from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Callable, Protocol, Sequence

from query_plan_receipt_service import (
    current_query_receipt_source_state,
    get_query_receipt,
    query_receipt_binding_fingerprint,
)


EVIDENCE_RETRIEVAL_RECEIPT_SCHEMA = "aibi-evidence-retrieval-receipt/v1"
RETRIEVAL_EVALUATION_SCHEMA = "aibi-evidence-retrieval-evaluation/v1"
RETRIEVAL_POLICY_SCHEMA = "aibi-evidence-retrieval-policy/v1"
RETRIEVAL_MODES = {"hybrid_rrf", "lexical_degraded"}
DEFAULT_LEXICAL_THRESHOLD = 0.55
DEFAULT_VECTOR_THRESHOLD = 0.65
DEFAULT_RRF_K = 60
MAX_PROVIDER_TEXT_CHARS = 600
MAX_CONFIRMED_SUMMARY_CHARS = 240


class EmbeddingProvider(Protocol):
    """Provider-neutral local embedding boundary.

    Implementations receive only the already-sanitized strings produced by this
    module. They never receive database rows, plans, evidence bodies, paths, or
    credentials.
    """

    @property
    def signature(self) -> str: ...

    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...


@dataclass(frozen=True)
class RetrievalPolicy:
    explicit_vector_opt_in: bool = False
    lexical_threshold: float = DEFAULT_LEXICAL_THRESHOLD
    vector_threshold: float = DEFAULT_VECTOR_THRESHOLD
    rrf_k: int = DEFAULT_RRF_K
    max_candidates: int = 8


_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.I)
_PHONE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
_CN_ID = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_LONG_NUMBER = re.compile(r"(?<!\d)\d{13,19}(?!\d)")
_SECRET = re.compile(r"(?:bearer\s+[A-Za-z0-9._~+/-]+=*|(?:password|passwd|secret|token|api[_-]?key)\s*[:=]|\bsk-[A-Za-z0-9_-]{12,})", re.I)
_ABSOLUTE_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|(?<!:)//[^/\s]+/|(?<!:)\\\\[^\\\s]+\\)")
_URL = re.compile(r"\b(?:https?|ftp)://", re.I)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _canonical_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def stable_json(value: Any) -> str:
    return json.dumps(_canonical_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def privacy_findings(text: str) -> list[str]:
    value = str(text or "")
    findings: list[str] = []
    for code, pattern in (
        ("email", _EMAIL),
        ("phone", _PHONE),
        ("national-id", _CN_ID),
        ("long-number", _LONG_NUMBER),
        ("credential", _SECRET),
        ("absolute-path", _ABSOLUTE_PATH),
        ("url", _URL),
    ):
        if pattern.search(value):
            findings.append(code)
    return findings


def _provider_signature(provider: EmbeddingProvider | None) -> str:
    if provider is None:
        return ""
    signature = str(getattr(provider, "signature", "") or "").strip()
    if not signature or len(signature) > 160:
        raise ValueError("Embedding Provider signature must contain 1-160 characters")
    if privacy_findings(signature) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/@+-]*", signature):
        raise ValueError("Embedding Provider signature must be stable and must not contain paths or secrets")
    return signature


def _evaluation_gate_valid(gate: dict[str, Any] | None, provider_signature: str) -> bool:
    if not isinstance(gate, dict):
        return False
    stored_fingerprint = str(gate.get("evaluationFingerprint") or "")
    material = {key: value for key, value in gate.items() if key != "evaluationFingerprint"}
    zero_tolerance = gate.get("zeroTolerance") if isinstance(gate.get("zeroTolerance"), dict) else {}
    privacy = gate.get("privacy") if isinstance(gate.get("privacy"), dict) else {}
    return (
        gate.get("schema") == RETRIEVAL_EVALUATION_SCHEMA
        and gate.get("status") == "passed"
        and gate.get("providerSignature") == provider_signature
        and stored_fingerprint == fingerprint(material)
        and all(value is True for value in zero_tolerance.values())
        and zero_tolerance
        and privacy.get("rawRowCount") == 0
        and privacy.get("piiFindingCount") == 0
        and gate.get("thresholdsPassed") is True
    )


def ensure_evidence_retrieval_schema(connection: sqlite3.Connection) -> None:
    statements = (
        """
        CREATE TABLE IF NOT EXISTS evidence_retrieval_receipts (
          receipt_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          request_hash TEXT NOT NULL,
          status TEXT NOT NULL,
          mode TEXT NOT NULL,
          provider_signature TEXT NOT NULL,
          corpus_fingerprint TEXT NOT NULL,
          receipt_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, receipt_key)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_evidence_retrieval_workspace_created ON evidence_retrieval_receipts(workspace_id, created_at)",
        """
        CREATE TABLE IF NOT EXISTS retrieval_evaluation_runs (
          evaluation_key TEXT NOT NULL,
          workspace_id TEXT NOT NULL,
          provider_signature TEXT NOT NULL,
          status TEXT NOT NULL,
          evaluation_json TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY(workspace_id, evaluation_key)
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_retrieval_evaluation_workspace_created ON retrieval_evaluation_runs(workspace_id, created_at)",
    )
    for statement in statements:
        connection.execute(statement)


def _text_features(value: str) -> tuple[set[str], set[str]]:
    folded = str(value or "").casefold()
    words = set(re.findall(r"[a-z0-9_]+", folded))
    cjk = "".join(re.findall(r"[\u3400-\u9fff]", folded))
    grams = {cjk[index:index + 2] for index in range(max(0, len(cjk) - 1))}
    if len(cjk) == 1:
        grams.add(cjk)
    return words, grams


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _signature_values(signature: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for key in ("tables", "fields", "groups", "aliases"):
        for value in signature.get(key) or []:
            normalized = str(value or "").strip().casefold()
            if normalized:
                values.add(f"{key}:{normalized}")
    for key in ("measure", "aggregation", "knowledgeRule"):
        normalized = str(signature.get(key) or "").strip().casefold()
        if normalized:
            values.add(f"{key}:{normalized}")
    return values


def current_signature(semantic_plan: dict[str, Any] | None, explicit_table_key: str | None) -> dict[str, Any]:
    semantic = semantic_plan if isinstance(semantic_plan, dict) else {}
    resolution = semantic.get("fieldResolution") if isinstance(semantic.get("fieldResolution"), dict) else {}
    selected = resolution.get("selected") if isinstance(resolution.get("selected"), list) else []
    result: dict[str, Any] = {
        "tables": sorted({
            str(item.get("tableKey") or "").strip()
            for item in selected
            if isinstance(item, dict) and str(item.get("tableKey") or "").strip()
        }),
        "fields": sorted({
            f"{str(item.get('tableKey') or '').strip()}.{str(item.get('field') or '').strip()}".strip(".")
            for item in selected
            if isinstance(item, dict) and str(item.get("field") or "").strip()
        }),
        "measure": "",
        "groups": [],
        "aggregation": "",
        "knowledgeRule": "",
    }
    if explicit_table_key and explicit_table_key not in result["tables"]:
        result["tables"].append(explicit_table_key)
        result["tables"].sort()
    for item in selected:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "")
        field = str(item.get("field") or "").strip()
        if role == "measure" and field and not result["measure"]:
            result["measure"] = field
        if role == "dimension" and field:
            result["groups"].append(field)
    result["groups"] = sorted(set(result["groups"]))
    return result


def _lexical_scores(prompt: str, signature: dict[str, Any], question: str) -> dict[str, float]:
    prompt_folded = str(prompt or "").casefold().strip()
    prompt_words, prompt_grams = _text_features(prompt)
    question_folded = str(question or "").casefold().strip()
    memory_words, memory_grams = _text_features(question)
    for item in _signature_values(signature):
        memory_words.add(item.split(":", 1)[-1])
    sequence_score = 1.0 if question_folded == prompt_folded else SequenceMatcher(None, prompt_folded, question_folded).ratio()
    lexical_score = max(sequence_score, _jaccard(prompt_words, memory_words))
    if prompt_folded and (prompt_folded in question_folded or question_folded in prompt_folded):
        lexical_score = max(lexical_score, 0.85)
    return {
        "lexical": round(lexical_score, 6),
        "characterNgram": round(_jaccard(prompt_grams, memory_grams), 6),
    }


def _baseline_score(channels: dict[str, float], structured_score: float, has_structure: bool) -> float:
    active = [(0.5, channels["lexical"]), (0.2, channels["characterNgram"])]
    if has_structure:
        active.append((0.3, structured_score))
    total = sum(weight for weight, _value in active)
    return sum(weight * value for weight, value in active) / total


def _embedding_text(question: str, signature: dict[str, Any]) -> str:
    summary = str(question or "").strip()[:MAX_CONFIRMED_SUMMARY_CHARS]
    allowed = {
        "questionSummary": summary,
        "tables": [str(item) for item in signature.get("tables") or []],
        "fieldLabels": [str(item) for item in signature.get("fields") or []],
        "metricLabel": str(signature.get("measure") or ""),
        "groupLabels": [str(item) for item in signature.get("groups") or []],
        "aliases": [str(item) for item in signature.get("aliases") or []],
    }
    text = stable_json(allowed)
    if len(text) > MAX_PROVIDER_TEXT_CHARS:
        raise ValueError("Embedding input exceeds the bounded metadata limit")
    return text


def _cosine(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or len(left) != len(right):
        raise ValueError("Embedding vectors must have one stable non-zero dimension")
    left_values = [float(item) for item in left]
    right_values = [float(item) for item in right]
    if not all(math.isfinite(item) for item in [*left_values, *right_values]):
        raise ValueError("Embedding vectors must contain finite values")
    left_norm = math.sqrt(sum(item * item for item in left_values))
    right_norm = math.sqrt(sum(item * item for item in right_values))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return max(-1.0, min(1.0, sum(a * b for a, b in zip(left_values, right_values)) / (left_norm * right_norm)))


def _candidate_public(row: sqlite3.Row, signature: dict[str, Any]) -> dict[str, Any]:
    plan = _json_object(row["plan_json"])
    return {
        "memoryKey": row["memory_key"],
        "queryKey": row["query_key"],
        "queryReceiptKey": row["query_receipt_key"],
        "question": str(row["question"] or ""),
        "status": str(row["status"] or ""),
        "signature": signature,
        "planFingerprint": fingerprint(plan),
        "bindingFingerprint": str(row["binding_fingerprint"] or ""),
        "confirmedAt": row["confirmed_at"],
        "canAuthorizeSelection": False,
        "canBypassAmbiguity": False,
    }


def _hard_filtered_candidates(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    explicit_table_key: str | None,
    permission_filter: Callable[[dict[str, Any]], bool] | None,
    receipt_lookup: Callable[[sqlite3.Connection, str, str], dict[str, Any] | None],
    source_state_resolver: Callable[[sqlite3.Connection, str, dict[str, Any]], dict[str, Any]],
    binding_fingerprint_resolver: Callable[[dict[str, Any]], str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows = connection.execute(
        "SELECT * FROM confirmed_plan_memories WHERE workspace_id = ? AND status = 'confirmed' ORDER BY confirmed_at DESC",
        (workspace_id,),
    ).fetchall()
    accepted: list[dict[str, Any]] = []
    excluded = {
        "notExecuted": 0,
        "notCurrent": 0,
        "bindingDrifted": 0,
        "wrongExplicitTable": 0,
        "permissionDenied": 0,
    }
    for row in rows:
        signature = _json_object(row["signature_json"])
        candidate = _candidate_public(row, signature)
        receipt = receipt_lookup(connection, workspace_id, candidate["queryReceiptKey"])
        if not receipt or str(receipt.get("status") or "") != "executed":
            excluded["notExecuted"] += 1
            continue
        source_state = source_state_resolver(connection, workspace_id, receipt)
        if not source_state.get("matchesReceipt"):
            excluded["notCurrent"] += 1
            continue
        if candidate["bindingFingerprint"] != binding_fingerprint_resolver(receipt):
            excluded["bindingDrifted"] += 1
            continue
        tables = {str(item) for item in signature.get("tables") or []}
        if explicit_table_key and explicit_table_key not in tables:
            excluded["wrongExplicitTable"] += 1
            continue
        if permission_filter is not None and permission_filter(candidate) is not True:
            excluded["permissionDenied"] += 1
            continue
        accepted.append(candidate)
    return accepted, excluded


def _degradation_reason(
    *,
    policy: RetrievalPolicy,
    provider: EmbeddingProvider | None,
    provider_signature: str,
    evaluation_gate: dict[str, Any] | None,
    confirmed_question_summary: str | None,
) -> str | None:
    if not policy.explicit_vector_opt_in:
        return "provider-disabled"
    if provider is None:
        return "provider-unavailable"
    if not _evaluation_gate_valid(evaluation_gate, provider_signature):
        return "evaluation-gate-not-passed"
    if not str(confirmed_question_summary or "").strip():
        return "confirmed-question-summary-missing"
    if len(str(confirmed_question_summary)) > MAX_CONFIRMED_SUMMARY_CHARS:
        return "confirmed-question-summary-too-long"
    if privacy_findings(str(confirmed_question_summary)):
        return "confirmed-question-summary-sensitive"
    return None


def retrieve_confirmed_evidence(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    prompt: str,
    explicit_table_key: str | None,
    semantic_plan: dict[str, Any] | None,
    planning_binding_fingerprint: str,
    now_iso: Callable[[], str],
    policy: RetrievalPolicy | None = None,
    provider: EmbeddingProvider | None = None,
    evaluation_gate: dict[str, Any] | None = None,
    confirmed_question_summary: str | None = None,
    permission_filter: Callable[[dict[str, Any]], bool] | None = None,
    receipt_lookup: Callable[[sqlite3.Connection, str, str], dict[str, Any] | None] | None = None,
    source_state_resolver: Callable[[sqlite3.Connection, str, dict[str, Any]], dict[str, Any]] | None = None,
    binding_fingerprint_resolver: Callable[[dict[str, Any]], str] | None = None,
    persist_receipt: bool = True,
    limit: int = 3,
) -> dict[str, Any]:
    policy = policy or RetrievalPolicy()
    if not 0 <= policy.lexical_threshold <= 1 or not 0 <= policy.vector_threshold <= 1:
        raise ValueError("Retrieval thresholds must be between 0 and 1")
    if not 1 <= int(policy.max_candidates) <= 100 or not 1 <= int(policy.rrf_k) <= 10_000:
        raise ValueError("Retrieval candidate and RRF limits are invalid")
    prompt = str(prompt or "").strip()
    if not prompt or len(prompt) > 2_000:
        raise ValueError("Retrieval prompt must contain 1-2000 characters")
    if planning_binding_fingerprint and not _SHA256.fullmatch(str(planning_binding_fingerprint)):
        raise ValueError("Planning binding fingerprint must be a lowercase SHA-256 value")

    candidates, hard_filter_counts = _hard_filtered_candidates(
        connection,
        workspace_id=workspace_id,
        explicit_table_key=explicit_table_key,
        permission_filter=permission_filter,
        receipt_lookup=receipt_lookup or get_query_receipt,
        source_state_resolver=source_state_resolver or current_query_receipt_source_state,
        binding_fingerprint_resolver=binding_fingerprint_resolver or query_receipt_binding_fingerprint,
    )
    query_signature = current_signature(semantic_plan, explicit_table_key)
    query_values = _signature_values(query_signature)
    for candidate in candidates:
        channels = _lexical_scores(prompt, candidate["signature"], candidate["question"])
        structured = _jaccard(query_values, _signature_values(candidate["signature"]))
        candidate["matchChannels"] = {
            **channels,
            "structuredPlan": round(structured, 6),
            "freshness": 1.0,
        }
        candidate["baselineScore"] = round(_baseline_score(channels, structured, bool(query_values)), 6)

    candidates.sort(key=lambda item: (-item["baselineScore"], str(item["memoryKey"])))
    provider_signature = _provider_signature(provider) if provider is not None else ""
    degraded_reason = _degradation_reason(
        policy=policy,
        provider=provider,
        provider_signature=provider_signature,
        evaluation_gate=evaluation_gate,
        confirmed_question_summary=confirmed_question_summary,
    )
    provider_inputs: list[str] = []
    vector_eligible: list[dict[str, Any]] = []
    vector_excluded = 0
    if degraded_reason is None:
        for candidate in candidates[: policy.max_candidates]:
            try:
                text = _embedding_text(candidate["question"], candidate["signature"])
            except ValueError:
                vector_excluded += 1
                continue
            if privacy_findings(text):
                vector_excluded += 1
                continue
            provider_inputs.append(text)
            vector_eligible.append(candidate)
        if not vector_eligible:
            degraded_reason = "no-safe-vector-candidates"

    vector_error = ""
    provider_attempted = False
    if degraded_reason is None:
        query_input = _embedding_text(str(confirmed_question_summary), query_signature)
        if privacy_findings(query_input):
            degraded_reason = "confirmed-question-summary-sensitive"
        else:
            try:
                provider_attempted = True
                vectors = list(provider.embed([query_input, *provider_inputs])) if provider is not None else []
                if len(vectors) != len(provider_inputs) + 1:
                    raise ValueError("Embedding Provider returned an unexpected vector count")
                query_vector = vectors[0]
                for candidate, vector in zip(vector_eligible, vectors[1:]):
                    candidate["matchChannels"]["vector"] = round(_cosine(query_vector, vector), 6)
            except Exception as error:  # Provider failure must never disable the deterministic path.
                vector_error = type(error).__name__
                degraded_reason = "provider-error"
                for candidate in candidates:
                    candidate["matchChannels"].pop("vector", None)

    mode = "hybrid_rrf" if degraded_reason is None else "lexical_degraded"
    lexical_rank = {item["memoryKey"]: index for index, item in enumerate(candidates, start=1)}
    vector_rank: dict[str, int] = {}
    if mode == "hybrid_rrf":
        vector_order = sorted(
            vector_eligible,
            key=lambda item: (-float(item["matchChannels"].get("vector") or 0), str(item["memoryKey"])),
        )
        vector_rank = {item["memoryKey"]: index for index, item in enumerate(vector_order, start=1)}
    for candidate in candidates:
        if mode == "hybrid_rrf" and candidate["memoryKey"] in vector_rank:
            raw_rrf = (
                1 / (policy.rrf_k + lexical_rank[candidate["memoryKey"]])
                + 1 / (policy.rrf_k + vector_rank[candidate["memoryKey"]])
            )
            maximum = 2 / (policy.rrf_k + 1)
            candidate["rrfScore"] = round(raw_rrf / maximum, 6)
            candidate["matchScore"] = candidate["rrfScore"]
        else:
            candidate["rrfScore"] = None
            candidate["matchScore"] = candidate["baselineScore"]
        candidate["reasonCodes"] = [
            name
            for name, value in (
                ("lexical-question", candidate["matchChannels"]["lexical"]),
                ("multilingual-character-overlap", candidate["matchChannels"]["characterNgram"]),
                ("structured-plan-overlap", candidate["matchChannels"]["structuredPlan"]),
                ("provider-vector", candidate["matchChannels"].get("vector", 0)),
            )
            if float(value or 0) > 0
        ] + ["hard-filters-passed", "current-evidence-binding", "candidate-only"]

    candidates.sort(key=lambda item: (-float(item["matchScore"]), str(item["memoryKey"])))
    inspected = candidates[: policy.max_candidates]
    returned = [
        candidate
        for candidate in candidates
        if (
            candidate["baselineScore"] >= policy.lexical_threshold
            or (
                mode == "hybrid_rrf"
                and float(candidate["matchChannels"].get("vector") or 0) >= policy.vector_threshold
            )
        )
    ][: max(1, min(int(limit), 10))]
    status = "candidates" if returned else "no-match"
    corpus_material = [
        {
            "memoryKey": item["memoryKey"],
            "questionFingerprint": hashlib.sha256(item["question"].encode("utf-8")).hexdigest(),
            "planFingerprint": item["planFingerprint"],
            "bindingFingerprint": item["bindingFingerprint"],
            "signature": item["signature"],
        }
        for item in candidates
    ]
    corpus_fingerprint = fingerprint({
        "schema": "aibi-evidence-retrieval-corpus/v1",
        "workspaceId": workspace_id,
        "candidates": corpus_material,
    })
    timestamp = now_iso()
    request_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    receipt_material = {
        "workspaceId": workspace_id,
        "requestHash": request_hash,
        "mode": mode,
        "providerSignature": provider_signature,
        "corpusFingerprint": corpus_fingerprint,
        "planningBindingFingerprint": planning_binding_fingerprint,
        "candidateKeys": [item["memoryKey"] for item in inspected],
        "createdAt": timestamp,
    }
    receipt_key = f"evidence_retrieval_{fingerprint(receipt_material)[:20]}"
    public_candidates = []
    for item in inspected:
        public_item = {key: value for key, value in item.items() if key not in {"signature", "question"}}
        public_item["questionFingerprint"] = hashlib.sha256(item["question"].encode("utf-8")).hexdigest()
        public_candidates.append(public_item)
    public_returned_keys = {item["memoryKey"] for item in returned}
    public_returned = [item for item in public_candidates if item["memoryKey"] in public_returned_keys]
    receipt = {
        "schema": EVIDENCE_RETRIEVAL_RECEIPT_SCHEMA,
        "receiptKey": receipt_key,
        "workspaceId": workspace_id,
        "requestHash": request_hash,
        "status": status,
        "mode": mode,
        "policy": {
            "schema": RETRIEVAL_POLICY_SCHEMA,
            "strategy": "rrf" if mode == "hybrid_rrf" else "deterministic-baseline",
            "channels": ["lexical", "characterNgram", "structuredPlan", "freshness"]
            + (["vector"] if mode == "hybrid_rrf" else []),
            "adoption": "candidate-only",
            "canAuthorizeExecution": False,
            "canBypassTableFilter": False,
            "canBypassRelationshipValidation": False,
            "canBypassFreshness": False,
            "lexicalThreshold": policy.lexical_threshold,
            "vectorThreshold": policy.vector_threshold,
            "rrfK": policy.rrf_k,
        },
        "providerSignature": provider_signature,
        "corpusFingerprint": corpus_fingerprint,
        "planningBindingFingerprint": planning_binding_fingerprint,
        "degradationReason": degraded_reason,
        "providerErrorClass": vector_error or None,
        "hardFilterCounts": hard_filter_counts,
        "candidates": public_candidates,
        "returnedCandidates": public_returned,
        "privacy": {
            "rawRowCount": 0,
            "rawRowsSent": False,
            "piiFindingCount": 0,
            "providerAttempted": provider_attempted,
            "providerInputCount": (len(provider_inputs) + 1) if provider_attempted else 0,
            "vectorExcludedCandidateCount": vector_excluded,
            "providerInputContract": "confirmed-summary-and-schema-labels-only",
        },
        "createdAt": timestamp,
    }
    if persist_receipt:
        if not connection.in_transaction:
            raise RuntimeError("Evidence Retrieval Receipt writes require the caller to hold BEGIN IMMEDIATE")
        ensure_evidence_retrieval_schema(connection)
        connection.execute(
            """
            INSERT OR REPLACE INTO evidence_retrieval_receipts(
              receipt_key, workspace_id, request_hash, status, mode, provider_signature,
              corpus_fingerprint, receipt_json, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                receipt_key,
                workspace_id,
                request_hash,
                status,
                mode,
                provider_signature,
                corpus_fingerprint,
                stable_json(receipt),
                timestamp,
            ),
        )
    return {"candidates": public_returned, "receipt": receipt}


def list_evidence_retrieval_receipts(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        "SELECT receipt_json FROM evidence_retrieval_receipts WHERE workspace_id = ? ORDER BY created_at DESC LIMIT ?",
        (workspace_id, max(1, min(int(limit), 200))),
    ).fetchall()
    return [_json_object(row["receipt_json"]) for row in rows]
