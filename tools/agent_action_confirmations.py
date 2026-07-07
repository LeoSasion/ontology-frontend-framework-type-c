from __future__ import annotations

import sqlite3
from typing import Any

from agent_action_draft_store import mark_action_confirmed, mark_action_rejected


def confirm_dry_run_response(action: sqlite3.Row, payload: dict[str, Any], **details: Any) -> dict[str, Any]:
    return {
        "ok": True,
        "dryRun": True,
        "requiresConfirmation": True,
        "decision": "confirm",
        "action": dict(action),
        "payload": payload,
        **details,
    }


def reject_dry_run_response(action: sqlite3.Row, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "dryRun": True,
        "requiresConfirmation": True,
        "decision": "reject",
        "action": dict(action),
        "payload": payload,
    }


def confirmed_response(action_key: str, **details: Any) -> dict[str, Any]:
    return {
        "ok": True,
        "confirmed": True,
        "decision": "confirm",
        "actionKey": action_key,
        **details,
    }


def rejected_response(action_key: str) -> dict[str, Any]:
    return {
        "ok": True,
        "confirmed": True,
        "decision": "reject",
        "actionKey": action_key,
    }
