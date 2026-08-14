from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from typing import Any, Callable

from semantic_patch_service import (
    _apply_patch,
    _canonical,
    _current_target,
    _fingerprint,
    _proposal_payload,
)


PLAN_SCHEMA = "aibi-semantic-release-plan/v1"
RELEASE_SCHEMA = "aibi-semantic-release/v1"
COLLECTION_SCHEMA = "aibi-semantic-release-collection/v1"
ROLLBACK_SCHEMA = "aibi-semantic-release-rollback-plan/v1"


def _workspace_id(
    connection: sqlite3.Connection,
    args: argparse.Namespace,
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> str:
    requested = str(getattr(args, "workspace", "") or "").strip()
    workspace_id = requested or active_workspace_id(connection)
    if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
        raise ValueError(f"Unknown workspace: {workspace_id}")
    return workspace_id


def _request_key(args: argparse.Namespace) -> str:
    value = str(getattr(args, "request_key", "") or "").strip()
    if not value or len(value) > 200:
        raise ValueError("Semantic release requires a bounded requestKey.")
    return value


def _proposal_keys(args: argparse.Namespace) -> list[str]:
    values = getattr(args, "proposal", []) or []
    if isinstance(values, str):
        values = [values]
    result: list[str] = []
    for value in values:
        for item in str(value or "").split(","):
            normalized = item.strip()
            if normalized and normalized not in result:
                result.append(normalized)
    if len(result) > 100:
        raise ValueError("Semantic release is limited to 100 proposals.")
    return result


def _selected_rows(connection: sqlite3.Connection, workspace_id: str, requested: list[str]) -> list[sqlite3.Row]:
    if requested:
        placeholders = ", ".join("?" for _ in requested)
        rows = connection.execute(
            f"SELECT * FROM semantic_patch_proposals WHERE workspace_id = ? AND proposal_key IN ({placeholders})",
            (workspace_id, *requested),
        ).fetchall()
        by_key = {str(row["proposal_key"]): row for row in rows}
        missing = [key for key in requested if key not in by_key]
        if missing:
            raise ValueError("Unknown semantic proposals: " + ", ".join(missing))
        return [by_key[key] for key in requested]
    return connection.execute(
        "SELECT * FROM semantic_patch_proposals WHERE workspace_id = ? AND status = 'pending' ORDER BY created_at, proposal_key LIMIT 100",
        (workspace_id,),
    ).fetchall()


def _release_plan(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    request_key: str,
    label: str,
    proposal_keys: list[str],
) -> tuple[dict[str, Any], list[sqlite3.Row]]:
    rows = _selected_rows(connection, workspace_id, proposal_keys)
    if not rows:
        raise ValueError("Semantic release requires at least one pending proposal.")
    proposals = [_proposal_payload(connection, row) for row in rows]
    blockers: list[str] = []
    targets: set[str] = set()
    for proposal in proposals:
        if proposal["storedStatus"] != "pending":
            blockers.append(f"proposal-not-pending:{proposal['proposalKey']}")
        if not proposal["freshness"]["usableForReview"]:
            blockers.extend(f"{proposal['proposalKey']}:{item}" for item in proposal["freshness"]["mismatches"])
        target = f"{proposal['patchType']}:{proposal['targetRef']}"
        if target in targets:
            blockers.append(f"duplicate-target:{target}")
        targets.add(target)
    material = {
        "schema": PLAN_SCHEMA,
        "workspaceId": workspace_id,
        "requestKeyFingerprint": hashlib.sha256(request_key.encode("utf-8")).hexdigest(),
        "label": label,
        "proposalKeys": [proposal["proposalKey"] for proposal in proposals],
        "changes": [
            {
                "proposalKey": proposal["proposalKey"],
                "patchType": proposal["patchType"],
                "operation": proposal["operation"],
                "targetRef": proposal["targetRef"],
                "before": proposal["before"],
                "after": proposal["after"],
                "sourceKey": proposal["sourceKey"],
            }
            for proposal in proposals
        ],
        "blockers": sorted(set(blockers)),
    }
    material["planFingerprint"] = _fingerprint(material)
    material["readyToPublish"] = not blockers
    return material, rows


def semantic_release_preview_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    request_key = _request_key(args)
    label = str(getattr(args, "label", "") or "Semantic release").strip()[:160]
    with open_db() as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        plan, _rows = _release_plan(
            connection,
            workspace_id=workspace_id,
            request_key=request_key,
            label=label,
            proposal_keys=_proposal_keys(args),
        )
    return {"ok": True, "dryRun": True, "requiresConfirmation": True, "releasePlan": plan}


def _release_key(workspace_id: str, request_key: str, plan_fingerprint: str) -> str:
    return "release_" + hashlib.sha256(f"{workspace_id}\0{request_key}\0{plan_fingerprint}".encode("utf-8")).hexdigest()[:20]


def _release_payload(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    proposal_keys = json.loads(str(row["proposal_keys_json"] or "[]"))
    published = json.loads(str(row["published_snapshot_json"] or "[]"))
    current = [
        {
            "patchType": item["patchType"],
            "targetRef": item["targetRef"],
            "value": _current_target(connection, str(row["workspace_id"]), item["patchType"], item["targetRef"]),
        }
        for item in published
    ]
    current_fingerprint = _fingerprint(current)
    stored_status = str(row["status"])
    drifted = stored_status == "published" and current_fingerprint != str(row["published_fingerprint"])
    return {
        "schema": RELEASE_SCHEMA,
        "releaseKey": str(row["release_key"]),
        "workspaceId": str(row["workspace_id"]),
        "requestKeyFingerprint": hashlib.sha256(str(row["request_key"]).encode("utf-8")).hexdigest(),
        "label": str(row["label"]),
        "status": "stale" if drifted else stored_status,
        "storedStatus": stored_status,
        "proposalKeys": proposal_keys,
        "proposalCount": len(proposal_keys),
        "planFingerprint": str(row["plan_fingerprint"]),
        "current": stored_status == "published" and not drifted,
        "freshness": {
            "status": "stale" if drifted else "current",
            "mismatches": ["published-targets-changed"] if drifted else [],
            "currentFingerprint": current_fingerprint,
            "publishedFingerprint": str(row["published_fingerprint"]),
        },
        "createdAt": str(row["created_at"]),
        "publishedAt": str(row["published_at"]),
        "rolledBackAt": row["rolled_back_at"],
    }


def semantic_release_publish_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    if not bool(getattr(args, "yes", False)):
        raise ValueError("Semantic release publish requires --yes after preview.")
    request_key = _request_key(args)
    expected = str(getattr(args, "expected_plan", "") or "").strip()
    if len(expected) != 64:
        raise ValueError("Semantic release publish requires the exact preview fingerprint.")
    label = str(getattr(args, "label", "") or "Semantic release").strip()[:160]
    with open_db() as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        existing = connection.execute(
            "SELECT * FROM semantic_releases WHERE workspace_id = ? AND request_key = ?",
            (workspace_id, request_key),
        ).fetchone()
        if existing:
            if str(existing["plan_fingerprint"]) != expected:
                raise ValueError("requestKey is already bound to a different semantic release plan.")
            return {"ok": True, "confirmed": True, "changed": False, "idempotentReplay": True, "release": _release_payload(connection, existing)}
        plan, rows = _release_plan(
            connection,
            workspace_id=workspace_id,
            request_key=request_key,
            label=label,
            proposal_keys=_proposal_keys(args),
        )
        if not plan["readyToPublish"]:
            raise ValueError("Semantic release is blocked: " + ", ".join(plan["blockers"]))
        if expected != plan["planFingerprint"]:
            raise ValueError("Semantic release changed after preview; preview it again.")
        timestamp = now_iso()
        release_key = _release_key(workspace_id, request_key, expected)
        previous = [
            {"patchType": proposal["patchType"], "targetRef": proposal["targetRef"], "value": proposal["before"]}
            for proposal in plan["changes"]
        ]
        for row in rows:
            proposal = _proposal_payload(connection, row)
            _apply_patch(connection, row, now_iso)
            review = {
                "decision": "accept",
                "reviewer": "semantic-release",
                "releaseKey": release_key,
                "proposalFingerprint": _fingerprint({"before": proposal["before"], "after": proposal["after"]}),
            }
            connection.execute(
                "UPDATE semantic_patch_proposals SET status = 'accepted', review_json = ?, updated_at = ?, reviewed_at = ? WHERE workspace_id = ? AND proposal_key = ? AND status = 'pending'",
                (_canonical(review), timestamp, timestamp, workspace_id, row["proposal_key"]),
            )
        published = [
            {
                "patchType": proposal["patchType"],
                "targetRef": proposal["targetRef"],
                "value": _current_target(connection, workspace_id, proposal["patchType"], proposal["targetRef"]),
            }
            for proposal in plan["changes"]
        ]
        published_fingerprint = _fingerprint(published)
        connection.execute(
            """
            INSERT INTO semantic_releases(
              release_key, workspace_id, request_key, label, status, proposal_keys_json,
              plan_json, plan_fingerprint, previous_snapshot_json, published_snapshot_json,
              published_fingerprint, rollback_request_key, rollback_plan_fingerprint,
              created_at, published_at, rolled_back_at
            ) VALUES(?, ?, ?, ?, 'published', ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, NULL)
            """,
            (
                release_key, workspace_id, request_key, label, _canonical(plan["proposalKeys"]),
                _canonical(plan), expected, _canonical(previous), _canonical(published),
                published_fingerprint, timestamp, timestamp,
            ),
        )
        connection.execute(
            "INSERT INTO semantic_release_events(workspace_id, release_key, event_type, status, payload_json, created_at) VALUES(?, ?, 'published', 'published', ?, ?)",
            (workspace_id, release_key, _canonical({"planFingerprint": expected, "proposalCount": len(rows)}), timestamp),
        )
        connection.commit()
        saved = connection.execute("SELECT * FROM semantic_releases WHERE workspace_id = ? AND release_key = ?", (workspace_id, release_key)).fetchone()
        payload = _release_payload(connection, saved)
    return {"ok": True, "confirmed": True, "changed": True, "idempotentReplay": False, "release": payload}


def semantic_releases_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        release_key = str(getattr(args, "release", "") or "").strip()
        if release_key:
            row = connection.execute("SELECT * FROM semantic_releases WHERE workspace_id = ? AND release_key = ?", (workspace_id, release_key)).fetchone()
            if not row:
                raise ValueError("Unknown semantic release")
            return {"ok": True, "schema": COLLECTION_SCHEMA, "workspaceId": workspace_id, "release": _release_payload(connection, row)}
        rows = connection.execute(
            "SELECT * FROM semantic_releases WHERE workspace_id = ? ORDER BY published_at DESC LIMIT ?",
            (workspace_id, max(1, min(int(getattr(args, "limit", 50) or 50), 200))),
        ).fetchall()
        releases = [_release_payload(connection, row) for row in rows]
    return {"ok": True, "schema": COLLECTION_SCHEMA, "workspaceId": workspace_id, "releases": releases, "count": len(releases)}


def _restore_target(connection: sqlite3.Connection, workspace_id: str, item: dict[str, Any], timestamp: str) -> None:
    patch_type = str(item["patchType"])
    target_ref = str(item["targetRef"])
    value = item.get("value")
    if value is None:
        if patch_type == "term":
            connection.execute("DELETE FROM context_terms WHERE workspace_id = ? AND term_key = ?", (workspace_id, target_ref))
        elif patch_type == "rule":
            connection.execute("DELETE FROM context_rules WHERE workspace_id = ? AND rule_key = ?", (workspace_id, target_ref))
        else:
            table_key, _separator, field_name = target_ref.partition(".")
            connection.execute("DELETE FROM field_semantics WHERE workspace_id = ? AND table_key = ? AND field_name = ?", (workspace_id, table_key, field_name))
        return
    if patch_type == "term":
        connection.execute(
            """INSERT INTO context_terms(term_key, workspace_id, canonical_name, aliases_json, definition, scope_type, scope_ref, status, source, evidence_json, created_at, updated_at, confirmed_at)
               VALUES(?, ?, ?, ?, ?, ?, ?, 'confirmed', 'release-rollback', '[]', ?, ?, ?)
               ON CONFLICT(workspace_id, term_key) DO UPDATE SET canonical_name=excluded.canonical_name, aliases_json=excluded.aliases_json, definition=excluded.definition, scope_type=excluded.scope_type, scope_ref=excluded.scope_ref, status='confirmed', source='release-rollback', updated_at=excluded.updated_at, confirmed_at=excluded.confirmed_at""",
            (target_ref, workspace_id, value["canonicalName"], _canonical(value.get("aliases") or []), value["definition"], value["scopeType"], value.get("scopeRef") or "", timestamp, timestamp, timestamp),
        )
    elif patch_type == "rule":
        connection.execute(
            """INSERT INTO context_rules(rule_key, workspace_id, title, statement, rule_type, applies_to_json, status, source, evidence_json, created_at, updated_at, confirmed_at)
               VALUES(?, ?, ?, ?, ?, ?, 'confirmed', 'release-rollback', '[]', ?, ?, ?)
               ON CONFLICT(workspace_id, rule_key) DO UPDATE SET title=excluded.title, statement=excluded.statement, rule_type=excluded.rule_type, applies_to_json=excluded.applies_to_json, status='confirmed', source='release-rollback', updated_at=excluded.updated_at, confirmed_at=excluded.confirmed_at""",
            (target_ref, workspace_id, value["title"], value["statement"], value["ruleType"], _canonical(value.get("appliesTo") or []), timestamp, timestamp, timestamp),
        )
    else:
        usage = value.get("usage") or {}
        primary_usage = "aggregatable" if usage.get("aggregatable") else "joinable" if usage.get("joinable") else "groupable" if usage.get("groupable") else "filterable"
        connection.execute(
            """INSERT INTO field_semantics(workspace_id, table_key, field_name, role, usage, confidence, tags_json, usage_json, source, note, updated_at)
               VALUES(?, ?, ?, ?, ?, ?, ?, ?, 'release-rollback', ?, ?)
               ON CONFLICT(workspace_id, table_key, field_name) DO UPDATE SET role=excluded.role, usage=excluded.usage, confidence=excluded.confidence, tags_json=excluded.tags_json, usage_json=excluded.usage_json, source='release-rollback', note=excluded.note, updated_at=excluded.updated_at""",
            (workspace_id, value["tableKey"], value["fieldName"], value["role"], primary_usage, float(value.get("confidence") or 0), _canonical(value.get("tags") or []), _canonical(usage), value.get("note") or "", timestamp),
        )


def semantic_release_rollback_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    request_key = _request_key(args)
    release_key = str(getattr(args, "release", "") or "").strip()
    if not release_key:
        raise ValueError("Semantic release rollback requires a release key.")
    with open_db() as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        row = connection.execute("SELECT * FROM semantic_releases WHERE workspace_id = ? AND release_key = ?", (workspace_id, release_key)).fetchone()
        if not row:
            raise ValueError("Unknown semantic release")
        if str(row["status"]) == "rolled_back":
            if str(row["rollback_request_key"] or "") != request_key:
                raise ValueError("Semantic release was rolled back by a different requestKey.")
            return {"ok": True, "confirmed": True, "changed": False, "idempotentReplay": True, "release": _release_payload(connection, row)}
        release = _release_payload(connection, row)
        blockers = list(release["freshness"]["mismatches"])
        previous = json.loads(str(row["previous_snapshot_json"] or "[]"))
        material = {
            "schema": ROLLBACK_SCHEMA,
            "workspaceId": workspace_id,
            "releaseKey": release_key,
            "requestKeyFingerprint": hashlib.sha256(request_key.encode("utf-8")).hexdigest(),
            "publishedFingerprint": str(row["published_fingerprint"]),
            "restoreFingerprint": _fingerprint(previous),
            "blockers": blockers,
        }
        material["planFingerprint"] = _fingerprint(material)
        material["readyToRollback"] = not blockers
        if not bool(getattr(args, "yes", False)):
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "rollbackPlan": material, "release": release}
        expected = str(getattr(args, "expected_plan", "") or "").strip()
        if expected != material["planFingerprint"]:
            raise ValueError("Semantic rollback changed after preview; preview it again.")
        if blockers:
            raise ValueError("Semantic release rollback is blocked: " + ", ".join(blockers))
        timestamp = now_iso()
        for item in reversed(previous):
            _restore_target(connection, workspace_id, item, timestamp)
        connection.execute(
            "UPDATE semantic_releases SET status='rolled_back', rollback_request_key=?, rollback_plan_fingerprint=?, rolled_back_at=? WHERE workspace_id=? AND release_key=? AND status='published'",
            (request_key, expected, timestamp, workspace_id, release_key),
        )
        connection.execute(
            "INSERT INTO semantic_release_events(workspace_id, release_key, event_type, status, payload_json, created_at) VALUES(?, ?, 'rolled_back', 'rolled_back', ?, ?)",
            (workspace_id, release_key, _canonical({"rollbackPlanFingerprint": expected}), timestamp),
        )
        connection.commit()
        saved = connection.execute("SELECT * FROM semantic_releases WHERE workspace_id = ? AND release_key = ?", (workspace_id, release_key)).fetchone()
        payload = _release_payload(connection, saved)
    return {"ok": True, "confirmed": True, "changed": True, "idempotentReplay": False, "release": payload}
