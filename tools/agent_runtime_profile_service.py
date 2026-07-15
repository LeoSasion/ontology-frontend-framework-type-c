from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import uuid
from typing import Any, Callable


PROFILE_SCHEMA = "aibi-agent-runtime-profile/v1"
EVALUATION_SCHEMA = "aibi-agent-provider-evaluation/v1"
PROFILE_IDS = ("deterministic", "deepseek", "local-openai")
TERMINAL_EVALUATION_STATUSES = {"passed", "fallback", "blocked", "failed", "skipped"}


def _profile_fingerprint(profile_id: str) -> str:
    return hashlib.sha256(f"{PROFILE_SCHEMA}:{profile_id}".encode("utf-8")).hexdigest()


def _workspace_id(connection: sqlite3.Connection, args: argparse.Namespace, active_workspace_id: Callable[[sqlite3.Connection], str]) -> str:
    workspace_id = str(getattr(args, "workspace", "") or active_workspace_id(connection))
    if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
        raise ValueError(f"Unknown workspace: {workspace_id}")
    return workspace_id


def _profile_catalog(selected_profile_id: str) -> list[dict[str, Any]]:
    definitions = {
        "deterministic": {
            "provider": "deterministic",
            "model": "local-bi-runtime",
            "wireApi": "none",
            "structuredOutput": "native-contract",
            "stages": ["intent", "context", "plan", "execute", "validate", "explain"],
        },
        "deepseek": {
            "provider": "deepseek",
            "model": "environment-configured",
            "wireApi": "openai-chat-completions",
            "structuredOutput": "json-object",
            "stages": ["explain", "completion-review", "shadow-evaluation"],
        },
        "local-openai": {
            "provider": "local-openai-compatible",
            "model": "environment-configured",
            "wireApi": "openai-chat-completions",
            "structuredOutput": "json-object-or-prompt-contract",
            "stages": ["explain", "completion-review", "shadow-evaluation"],
        },
    }
    return [
        {
            "schema": PROFILE_SCHEMA,
            "profileId": profile_id,
            **definitions[profile_id],
            "selected": profile_id == selected_profile_id,
            "businessSemantics": "deterministic-only",
            "toolPermissions": [],
            "fingerprint": _profile_fingerprint(profile_id),
        }
        for profile_id in PROFILE_IDS
    ]


def agent_runtime_profiles_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        row = connection.execute(
            "SELECT profile_id, updated_at FROM workspace_agent_runtime_profiles WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()
        selected = str(row["profile_id"] if row else "deterministic")
        if selected not in PROFILE_IDS:
            selected = "deterministic"
        profiles = _profile_catalog(selected)
        return {
            "ok": True,
            "schema": "aibi-agent-runtime-profile-catalog/v1",
            "workspaceId": workspace_id,
            "selectedProfileId": selected,
            "selectionUpdatedAt": row["updated_at"] if row else None,
            "profiles": profiles,
            "businessSemanticAuthority": "deterministic-local-bi",
            "providerCanWrite": False,
        }


def agent_runtime_profile_set_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    requested = str(args.profile or "").strip()
    if requested not in PROFILE_IDS:
        raise ValueError(f"Unsupported runtime profile: {requested}")
    with open_db() as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        current = connection.execute(
            "SELECT profile_id FROM workspace_agent_runtime_profiles WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()
        previous = str(current["profile_id"] if current else "deterministic")
        preview = {
            "workspaceId": workspace_id,
            "previousProfileId": previous,
            "selectedProfileId": requested,
            "profileFingerprint": _profile_fingerprint(requested),
            "providerCanWrite": False,
            "semanticContractChanged": False,
            "confirmationBoundaryChanged": False,
        }
        if not args.yes:
            return {
                "ok": True,
                "schema": "aibi-agent-runtime-profile-selection/v1",
                "dryRun": True,
                "requiresConfirmation": True,
                **preview,
            }
        connection.execute(
            """
            INSERT INTO workspace_agent_runtime_profiles(workspace_id, profile_id, updated_at)
            VALUES(?, ?, ?)
            ON CONFLICT(workspace_id) DO UPDATE SET profile_id = excluded.profile_id, updated_at = excluded.updated_at
            """,
            (workspace_id, requested, now_iso()),
        )
        connection.commit()
        return {
            "ok": True,
            "schema": "aibi-agent-runtime-profile-selection/v1",
            "dryRun": False,
            "requiresConfirmation": False,
            **preview,
        }


def _safe_audit_json(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value or "{}")
    except json.JSONDecodeError as error:
        raise ValueError("audit-json must be one JSON object") from error
    if not isinstance(parsed, dict):
        raise ValueError("audit-json must be one JSON object")
    serialized = json.dumps(parsed, ensure_ascii=False, sort_keys=True)
    if len(serialized) > 12_000:
        raise ValueError("audit-json exceeds the 12000 character limit")
    if re.search(r"(?:sk-|api[_-]?key|authorization|bearer\s+)[A-Za-z0-9._-]{6,}", serialized, re.I):
        raise ValueError("audit-json appears to contain a secret")
    if re.search(r"[A-Za-z]:\\", serialized):
        raise ValueError("audit-json must not contain local paths")
    if any(key in parsed for key in ("rows", "rawRows", "prompt", "context")):
        raise ValueError("audit-json must not contain prompts, contexts, or raw rows")
    return parsed


def agent_provider_evaluation_record_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    profile_id = str(args.profile or "").strip()
    if profile_id not in PROFILE_IDS:
        raise ValueError(f"Unsupported runtime profile: {profile_id}")
    status = str(args.status or "").strip()
    if status not in TERMINAL_EVALUATION_STATUSES:
        raise ValueError(f"Unsupported evaluation status: {status}")
    audit = _safe_audit_json(str(args.audit_json or "{}"))
    with open_db() as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        evaluation_key = f"provider_eval_{uuid.uuid4().hex[:20]}"
        created_at = now_iso()
        connection.execute(
            """
            INSERT INTO agent_provider_evaluations(
              evaluation_key, workspace_id, profile_id, profile_fingerprint, provider, model,
              request_fingerprint, context_fingerprint, status, validation_status, duration_ms,
              prompt_tokens, completion_tokens, total_tokens, estimated_cost_usd, attempts,
              fallback_reason, shadow, audit_json, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evaluation_key,
                workspace_id,
                profile_id,
                str(args.profile_fingerprint or _profile_fingerprint(profile_id)),
                str(args.provider or "deterministic"),
                str(args.model or "local-bi-runtime"),
                str(args.request_fingerprint or ""),
                str(args.context_fingerprint or ""),
                status,
                str(args.validation_status or "not-run"),
                max(0, int(args.duration_ms or 0)),
                args.prompt_tokens,
                args.completion_tokens,
                args.total_tokens,
                max(0.0, float(args.estimated_cost_usd or 0)),
                max(0, int(args.attempts or 0)),
                str(args.fallback_reason or "") or None,
                1 if args.shadow else 0,
                json.dumps(audit, ensure_ascii=False, sort_keys=True),
                created_at,
            ),
        )
        connection.commit()
        return {
            "ok": True,
            "schema": EVALUATION_SCHEMA,
            "evaluationKey": evaluation_key,
            "workspaceId": workspace_id,
            "profileId": profile_id,
            "status": status,
            "validationStatus": str(args.validation_status or "not-run"),
            "shadow": bool(args.shadow),
            "createdAt": created_at,
        }


def agent_provider_evaluations_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        limit = max(1, min(int(args.limit or 30), 200))
        rows = connection.execute(
            """
            SELECT * FROM agent_provider_evaluations
            WHERE workspace_id = ?
            ORDER BY created_at DESC, evaluation_key DESC
            LIMIT ?
            """,
            (workspace_id, limit),
        ).fetchall()
        evaluations = []
        for row in rows:
            item = dict(row)
            item["shadow"] = bool(item.pop("shadow"))
            item["audit"] = json.loads(item.pop("audit_json") or "{}")
            evaluations.append({
                "schema": EVALUATION_SCHEMA,
                **{key: item[key] for key in item},
            })
        passed = sum(1 for item in evaluations if item["status"] == "passed")
        fallbacks = sum(1 for item in evaluations if item["status"] == "fallback")
        return {
            "ok": True,
            "schema": "aibi-agent-provider-evaluation-dashboard/v1",
            "workspaceId": workspace_id,
            "summary": {
                "total": len(evaluations),
                "passed": passed,
                "fallbacks": fallbacks,
                "validationFailures": sum(1 for item in evaluations if item["validation_status"] not in {"passed", "not-run"}),
                "providerWriteCount": 0,
            },
            "evaluations": evaluations,
        }
