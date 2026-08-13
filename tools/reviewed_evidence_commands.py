from __future__ import annotations

"""Thin, fail-closed command facade for reviewed publications and retrieval evidence.

The public parser, registry, dispatcher, schema migration, HTTP routes, and UI
mounts intentionally live outside this module.  In particular, an offline
embedding evaluation is evidence for a later adoption decision; it never turns
the vector channel on by itself.
"""

import argparse
import json
import re
import sqlite3
from contextlib import closing
from typing import Any, Callable, Protocol

from evidence_retrieval_service import (
    EmbeddingProvider,
    list_evidence_retrieval_receipts,
)
from retrieval_evaluation_service import evaluate_embedding_provider
from reviewed_publication_service import (
    PUBLICATION_STATUSES,
    build_reviewed_publication_plan,
    deprecate_reviewed_publication,
    evaluate_reviewed_publication,
    list_reviewed_publications,
    publish_reviewed_artifact,
    reviewed_publication_export,
)


LEXICAL_DEGRADED_MODE = "lexical_degraded"
RETRIEVAL_STATUS_SCHEMA = "aibi-evidence-retrieval-status/v1"
RETRIEVAL_EVALUATION_COMMAND_SCHEMA = "aibi-evidence-retrieval-evaluation-command/v1"

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SAFE_PROFILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:+-]{0,79}$")
_EMAIL = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+", re.I)
_PHONE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
_CN_ID = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
_LONG_NUMBER = re.compile(r"(?<!\d)\d{13,19}(?!\d)")
_SECRET_VALUE = re.compile(
    r"(?:bearer\s+[A-Za-z0-9._~+/-]+=*|(?:password|passwd|secret|token|api[_-]?key)\s*[:=]|\bsk-[A-Za-z0-9_-]{12,})",
    re.I,
)
_ABSOLUTE_PATH = re.compile(r"(?:[A-Za-z]:[\\/]|(?<!:)//[^/\s]+/|(?<!:)\\\\[^\\\s]+\\)")
_FORBIDDEN_OUTPUT_KEYS = {
    "absolutepath",
    "apikey",
    "authorization",
    "connectionstring",
    "credential",
    "credentialref",
    "filepath",
    "password",
    "privatekey",
    "rawrow",
    "rawrows",
    "secret",
    "token",
}
_ZERO_DISCLOSURE_KEYS = {"rawrowcount", "rawrowssent"}


class ApprovedProviderResolver(Protocol):
    """Resolve a server-owned profile to an already approved local provider."""

    def __call__(self, profile: str) -> EmbeddingProvider | None: ...


def _argument(args: argparse.Namespace, name: str, default: Any = None) -> Any:
    return getattr(args, name, default)


def _json_object(value: Any, *, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} must be a JSON object") from error
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must be a JSON object")
    return parsed


def _optional_sha256(value: Any, *, label: str) -> str | None:
    normalized = str(value or "").strip()
    if not normalized:
        return None
    if not _SHA256.fullmatch(normalized):
        raise ValueError(f"{label} must be a lowercase SHA-256 value")
    return normalized


def _required_sha256(value: Any, *, label: str) -> str:
    normalized = _optional_sha256(value, label=label)
    if normalized is None:
        raise ValueError(f"{label} is required")
    return normalized


def _begin_immediate(connection: sqlite3.Connection) -> None:
    if connection.in_transaction:
        connection.commit()
    connection.execute("BEGIN IMMEDIATE")


def _safe_zero_disclosure(key: str, value: Any) -> bool:
    if key == "rawrowcount":
        return isinstance(value, (int, float)) and not isinstance(value, bool) and value == 0
    if key == "rawrowssent":
        return value is False
    return False


def _assert_public_output(value: Any, *, path: str = "result") -> None:
    """Reject accidental row, path, PII, or secret disclosure at the facade."""

    if isinstance(value, dict):
        for key, item in value.items():
            normalized_key = re.sub(r"[^a-z0-9]", "", str(key).casefold())
            if normalized_key in _ZERO_DISCLOSURE_KEYS:
                if not _safe_zero_disclosure(normalized_key, item):
                    raise ValueError(f"Public command output violates zero-disclosure proof at {path}.{key}")
            elif normalized_key in _FORBIDDEN_OUTPUT_KEYS or any(
                token in normalized_key
                for token in (
                    "apikey",
                    "authorization",
                    "password",
                    "privatekey",
                    "secret",
                    "credential",
                    "connectionstring",
                    "accesstoken",
                    "refreshtoken",
                    "rawrow",
                    "absolutepath",
                    "filepath",
                )
            ):
                raise ValueError(f"Public command output contains a forbidden field at {path}.{key}")
            _assert_public_output(item, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _assert_public_output(item, path=f"{path}[{index}]")
        return
    if not isinstance(value, str):
        return
    if _SHA256.fullmatch(value):
        return
    if _ABSOLUTE_PATH.search(value):
        raise ValueError(f"Public command output contains an absolute path at {path}")
    if _SECRET_VALUE.search(value):
        raise ValueError(f"Public command output contains a credential-like value at {path}")
    if _EMAIL.search(value) or _PHONE.search(value) or _CN_ID.search(value) or _LONG_NUMBER.search(value):
        raise ValueError(f"Public command output contains potential PII at {path}")


def _public_result(value: dict[str, Any]) -> dict[str, Any]:
    _assert_public_output(value)
    return value


def reviewed_publication_plan_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    content = _json_object(_argument(args, "content_json"), label="content-json")
    skill_fingerprint = _optional_sha256(
        _argument(args, "skill_fingerprint"),
        label="skill-fingerprint",
    )
    with closing(open_db()) as connection:
        workspace_id = active_workspace_id(connection)
        plan = build_reviewed_publication_plan(
            connection,
            workspace_id=workspace_id,
            memory_key=str(_argument(args, "memory") or ""),
            unit_key=str(_argument(args, "unit") or ""),
            title=str(_argument(args, "title") or ""),
            content=content,
            skill_fingerprint=skill_fingerprint,
        )
    return _public_result({
        "ok": True,
        "dryRun": True,
        "requiresConfirmation": True,
        "reviewedPublicationPlan": plan,
    })


def reviewed_publication_publish_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    content = _json_object(_argument(args, "content_json"), label="content-json")
    skill_fingerprint = _optional_sha256(
        _argument(args, "skill_fingerprint"),
        label="skill-fingerprint",
    )
    confirmed = bool(_argument(args, "yes", False))
    expected_plan = (
        _required_sha256(_argument(args, "expected_plan"), label="expected-plan")
        if confirmed
        else None
    )
    with closing(open_db()) as connection:
        if confirmed:
            _begin_immediate(connection)
        workspace_id = active_workspace_id(connection)
        plan = build_reviewed_publication_plan(
            connection,
            workspace_id=workspace_id,
            memory_key=str(_argument(args, "memory") or ""),
            unit_key=str(_argument(args, "unit") or ""),
            title=str(_argument(args, "title") or ""),
            content=content,
            skill_fingerprint=skill_fingerprint,
        )
        if not confirmed:
            return _public_result({
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "reviewedPublicationPlan": plan,
            })
        result = publish_reviewed_artifact(
            connection,
            plan=plan,
            expected_plan_fingerprint=str(expected_plan),
            now_iso=now_iso,
        )
        connection.commit()
    return _public_result({"ok": True, "confirmed": True, **result})


def reviewed_publications_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    skill_fingerprint = _optional_sha256(
        _argument(args, "skill_fingerprint"),
        label="skill-fingerprint",
    )
    requested_status = str(_argument(args, "status") or "").strip() or None
    if requested_status and requested_status not in PUBLICATION_STATUSES:
        raise ValueError(f"Unsupported reviewed publication status: {requested_status}")
    publication_key = str(_argument(args, "publication") or "").strip()
    limit = max(1, min(int(_argument(args, "limit", 100)), 200))
    with closing(open_db()) as connection:
        workspace_id = active_workspace_id(connection)
        if publication_key:
            publication = evaluate_reviewed_publication(
                connection,
                workspace_id=workspace_id,
                publication_key=publication_key,
                current_skill_fingerprint=skill_fingerprint,
            )
            return _public_result({"ok": True, "reviewedPublication": publication})
        stored = list_reviewed_publications(
            connection,
            workspace_id=workspace_id,
            status=None,
            limit=200,
        )
        evaluated = [
            evaluate_reviewed_publication(
                connection,
                workspace_id=workspace_id,
                publication_key=str(item["publicationKey"]),
                current_skill_fingerprint=skill_fingerprint,
            )
            for item in stored
        ]
        if requested_status:
            evaluated = [item for item in evaluated if item.get("status") == requested_status]
        evaluated = evaluated[:limit]
    return _public_result({
        "ok": True,
        "reviewedPublications": evaluated,
        "count": len(evaluated),
    })


def reviewed_publication_deprecate_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    confirmed = bool(_argument(args, "yes", False))
    expected_head = (
        _required_sha256(_argument(args, "expected_head"), label="expected-head")
        if confirmed
        else None
    )
    publication_key = str(_argument(args, "publication") or "").strip()
    with closing(open_db()) as connection:
        if confirmed:
            _begin_immediate(connection)
        workspace_id = active_workspace_id(connection)
        current = evaluate_reviewed_publication(
            connection,
            workspace_id=workspace_id,
            publication_key=publication_key,
        )
        if not confirmed:
            return _public_result({
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "publicationKey": publication_key,
                "expectedHeadHash": current["ledgerHeadHash"],
                "currentStatus": current["status"],
                "canDeprecate": current["status"] != "deprecated",
            })
        result = deprecate_reviewed_publication(
            connection,
            workspace_id=workspace_id,
            publication_key=publication_key,
            expected_head_hash=str(expected_head),
            reason=str(_argument(args, "reason") or ""),
            now_iso=now_iso,
        )
        connection.commit()
    return _public_result({"ok": True, "confirmed": True, **result})


def reviewed_publication_export_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    skill_fingerprint = _optional_sha256(
        _argument(args, "skill_fingerprint"),
        label="skill-fingerprint",
    )
    with closing(open_db()) as connection:
        workspace_id = active_workspace_id(connection)
        exported = reviewed_publication_export(
            connection,
            workspace_id=workspace_id,
            publication_key=str(_argument(args, "publication") or ""),
            current_skill_fingerprint=skill_fingerprint,
            forensic=bool(_argument(args, "forensic", False)),
        )
    return _public_result({"ok": True, "reviewedPublicationExport": exported})


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone()
    return row is not None


def _latest_evaluation_summary(connection: sqlite3.Connection, workspace_id: str) -> dict[str, Any] | None:
    if not _table_exists(connection, "retrieval_evaluation_runs"):
        return None
    row = connection.execute(
        """
        SELECT evaluation_json
        FROM retrieval_evaluation_runs
        WHERE workspace_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (workspace_id,),
    ).fetchone()
    if row is None:
        return None
    raw = row["evaluation_json"] if isinstance(row, sqlite3.Row) else row[0]
    try:
        evaluation = json.loads(str(raw or "{}"))
    except json.JSONDecodeError:
        return {"status": "invalid", "thresholdsPassed": False, "integrity": "unreadable"}
    if not isinstance(evaluation, dict):
        return {"status": "invalid", "thresholdsPassed": False, "integrity": "unreadable"}
    return {
        "evaluationKey": evaluation.get("evaluationKey"),
        "providerSignature": evaluation.get("providerSignature"),
        "status": evaluation.get("status"),
        "thresholdsPassed": evaluation.get("thresholdsPassed") is True,
        "evaluationFingerprint": evaluation.get("evaluationFingerprint"),
        "createdAt": evaluation.get("createdAt"),
        "informationalOnly": True,
    }


def evidence_retrieval_status_command(
    _args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with closing(open_db()) as connection:
        workspace_id = active_workspace_id(connection)
        latest = _latest_evaluation_summary(connection, workspace_id)
        receipt_storage_available = _table_exists(connection, "evidence_retrieval_receipts")
        evaluation_storage_available = _table_exists(connection, "retrieval_evaluation_runs")
    return _public_result({
        "ok": True,
        "evidenceRetrievalStatus": {
            "schema": RETRIEVAL_STATUS_SCHEMA,
            "workspaceId": workspace_id,
            "mode": LEXICAL_DEGRADED_MODE,
            "embeddingAdopted": False,
            "degradationReason": "approved-provider-not-adopted",
            "enabledChannels": ["lexical", "characterNgram", "structuredPlan", "freshness"],
            "latestEvaluation": latest,
            "evaluationCanSelfEnableEmbedding": False,
            "storage": {
                "receiptStoreAvailable": receipt_storage_available,
                "evaluationStoreAvailable": evaluation_storage_available,
            },
        },
    })


def evidence_retrieval_receipts_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    limit = max(1, min(int(_argument(args, "limit", 100)), 200))
    with closing(open_db()) as connection:
        workspace_id = active_workspace_id(connection)
        receipts = (
            list_evidence_retrieval_receipts(
                connection,
                workspace_id=workspace_id,
                limit=limit,
            )
            if _table_exists(connection, "evidence_retrieval_receipts")
            else []
        )
    return _public_result({
        "ok": True,
        "mode": LEXICAL_DEGRADED_MODE,
        "embeddingAdopted": False,
        "evidenceRetrievalReceipts": receipts,
        "count": len(receipts),
    })


def evidence_retrieval_evaluate_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
    resolve_approved_provider: ApprovedProviderResolver | None = None,
) -> dict[str, Any]:
    profile = str(_argument(args, "provider_profile") or "").strip()
    if profile and not _SAFE_PROFILE.fullmatch(profile):
        raise ValueError("provider-profile must be a server-owned identifier without paths or credentials")

    with closing(open_db()) as connection:
        workspace_id = active_workspace_id(connection)
        provider_resolution_error = ""
        try:
            provider = resolve_approved_provider(profile) if profile and resolve_approved_provider else None
        except Exception as error:  # The resolver is a trusted boundary, but its details are not public.
            provider = None
            provider_resolution_error = type(error).__name__
        if provider is None:
            result = {
                "ok": True,
                "evidenceRetrievalEvaluation": {
                    "schema": RETRIEVAL_EVALUATION_COMMAND_SCHEMA,
                    "workspaceId": workspace_id,
                    "profile": profile or None,
                    "mode": LEXICAL_DEGRADED_MODE,
                    "evaluationPerformed": False,
                    "embeddingAdopted": False,
                    "degradationReason": (
                        "approved-provider-resolution-failed"
                        if provider_resolution_error
                        else "approved-provider-unavailable"
                    ),
                    "providerResolutionErrorClass": provider_resolution_error or None,
                    "adoptionStatus": "not-enabled",
                    "evaluationCanSelfEnableEmbedding": False,
                    "evaluation": None,
                },
            }
            return _public_result(result)

        _begin_immediate(connection)
        evaluation = evaluate_embedding_provider(
            provider=provider,
            workspace_id=workspace_id,
            now_iso=now_iso,
            connection=connection,
            persist=True,
        )
        connection.commit()

    passed = evaluation.get("status") == "passed" and evaluation.get("thresholdsPassed") is True
    return _public_result({
        "ok": True,
        "evidenceRetrievalEvaluation": {
            "schema": RETRIEVAL_EVALUATION_COMMAND_SCHEMA,
            "workspaceId": workspace_id,
            "profile": profile,
            "mode": LEXICAL_DEGRADED_MODE,
            "evaluatedCandidateMode": "hybrid_rrf" if passed else None,
            "evaluationPerformed": True,
            "embeddingAdopted": False,
            "degradationReason": "embedding-not-adopted" if passed else "evaluation-gate-not-passed",
            "adoptionStatus": "eligible-for-explicit-review" if passed else "rejected",
            "evaluationCanSelfEnableEmbedding": False,
            "evaluation": evaluation,
        },
    })
