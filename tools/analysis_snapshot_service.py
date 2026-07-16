from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from contextlib import closing
from typing import Any, Callable

from analysis_unit_service import MAX_RESULT_ROWS, analysis_unit_consumer_state, get_analysis_unit
from query_plan_receipt_service import get_query_receipt, query_receipt_binding_fingerprint


ANALYSIS_SNAPSHOT_SCHEMA = "aibi-analysis-snapshot/v1"
ANALYSIS_SNAPSHOT_PLAN_SCHEMA = "aibi-analysis-snapshot-plan/v1"
ANALYSIS_SNAPSHOT_CONTENT_SCHEMA = "aibi-analysis-snapshot-content/v1"
SNAPSHOT_OPERATIONS = {"create", "refresh", "replace"}


def _canonical_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonical_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_canonical_value(item) for item in value]
    if isinstance(value, tuple):
        return [_canonical_value(item) for item in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _canonical_json(value: Any) -> str:
    return json.dumps(_canonical_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or "{}"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _semantic_joins(value: Any) -> list[Any]:
    result: list[Any] = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            result.append(_canonical_value(item))
            continue
        result.append({
            key: item.get(key)
            for key in (
                "relationKey", "leftTable", "rightTable", "fromTable", "toTable",
                "joinType", "direction", "fieldMappings", "traversalMappings",
                "filters", "preaggregation", "tableKey", "field", "role",
            )
            if key in item
        })
    return result


def _semantic_fingerprint(unit: dict[str, Any], receipt: dict[str, Any]) -> str:
    shape = unit.get("shape") if isinstance(unit.get("shape"), dict) else {}
    grain = unit.get("grain") if isinstance(unit.get("grain"), dict) else {}
    selection = receipt.get("selection") if isinstance(receipt.get("selection"), dict) else {}
    return _fingerprint({
        "schema": "aibi-analysis-snapshot-semantics/v1",
        "kind": unit.get("kind"),
        "grain": {
            "dimensions": grain.get("dimensions") or [],
            "measures": grain.get("measures") or [],
            "sourceTableKey": grain.get("sourceTableKey"),
            "sourceTableKeys": grain.get("sourceTableKeys") or [],
        },
        "shape": {
            "columns": shape.get("columns") or [],
            "dimensionColumn": shape.get("dimensionColumn"),
            "dimensionColumns": shape.get("dimensionColumns") or [],
            "measureColumn": shape.get("measureColumn"),
            "temporalDimension": bool(shape.get("temporalDimension")),
        },
        "selection": {
            "group": selection.get("group"),
            "groups": selection.get("groups") or [],
            "measure": selection.get("measure"),
            "aggregation": selection.get("aggregation"),
            "filters": selection.get("filters") or [],
            "joins": _semantic_joins(selection.get("joins")),
        },
    })


def _binding_payload(unit: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    source = receipt.get("source") if isinstance(receipt.get("source"), dict) else {}
    manifest = receipt.get("workspaceManifest") if isinstance(receipt.get("workspaceManifest"), dict) else {}
    table_keys = [str(item) for item in source.get("tableKeys") or [] if str(item).strip()]
    if not table_keys and source.get("tableKey"):
        table_keys = [str(source["tableKey"])]
    return {
        "schema": "aibi-analysis-snapshot-binding/v1",
        "workspaceId": unit.get("workspaceId"),
        "unitKey": unit.get("unitKey"),
        "queryReceiptKey": unit.get("queryReceiptKey"),
        "unitDefinitionFingerprint": unit.get("definitionFingerprint"),
        "resultFingerprint": unit.get("resultFingerprint"),
        "receiptBindingFingerprint": query_receipt_binding_fingerprint(receipt),
        "source": {
            "tableKeys": sorted(dict.fromkeys(table_keys)),
            "schemaFingerprint": source.get("schemaFingerprint"),
            "dataFingerprint": source.get("dataFingerprint"),
            "relationshipPathFingerprint": source.get("relationshipPathFingerprint"),
            "sourceFingerprint": source.get("sourceFingerprint"),
        },
        "domainPackFingerprint": receipt.get("domainPackFingerprint"),
        "workspaceManifestFingerprint": manifest.get("fingerprint"),
    }


def _content_payload(unit: dict[str, Any], row_limit: int) -> dict[str, Any]:
    rows = unit.get("rows") if isinstance(unit.get("rows"), list) else []
    bounded_rows = rows[:row_limit]
    return {
        "schema": ANALYSIS_SNAPSHOT_CONTENT_SCHEMA,
        "unit": {
            "kind": unit.get("kind"),
            "title": unit.get("title"),
            "grain": unit.get("grain") if isinstance(unit.get("grain"), dict) else {},
            "shape": unit.get("shape") if isinstance(unit.get("shape"), dict) else {},
            "rows": bounded_rows,
            "calculation": unit.get("calculation") if isinstance(unit.get("calculation"), dict) else {},
            "validation": unit.get("validation") if isinstance(unit.get("validation"), dict) else {},
            "chartAdapter": unit.get("chartAdapter") if isinstance(unit.get("chartAdapter"), dict) else {},
        },
        "rowLimit": row_limit,
        "rowCount": len(bounded_rows),
        "truncated": len(rows) > len(bounded_rows),
    }


def _row_payload(row: sqlite3.Row, *, include_content: bool = False) -> dict[str, Any]:
    binding = _json_object(row["binding_json"])
    content = _json_object(row["content_json"])
    unit_content = content.get("unit") if isinstance(content.get("unit"), dict) else {}
    shape = unit_content.get("shape") if isinstance(unit_content.get("shape"), dict) else {}
    payload: dict[str, Any] = {
        "schema": ANALYSIS_SNAPSHOT_SCHEMA,
        "snapshotKey": row["snapshot_key"],
        "workspaceId": row["workspace_id"],
        "parentSnapshotKey": row["parent_snapshot_key"],
        "operation": row["operation"],
        "storedStatus": row["status"],
        "reason": row["reason"],
        "unitKey": row["unit_key"],
        "queryReceiptKey": row["query_receipt_key"],
        "semanticFingerprint": row["semantic_fingerprint"],
        "bindingFingerprint": row["binding_fingerprint"],
        "binding": binding,
        "rowLimit": int(row["row_limit"]),
        "rowCount": int(row["row_count"]),
        "contentHash": row["content_hash"],
        "inputFingerprint": row["input_fingerprint"],
        "createdAt": row["created_at"],
        "deletedAt": row["deleted_at"],
        "summary": {
            "kind": unit_content.get("kind"),
            "title": unit_content.get("title"),
            "columns": shape.get("columns") or [],
            "dimensionColumns": shape.get("dimensionColumns") or [],
            "measureColumn": shape.get("measureColumn"),
            "truncated": bool(content.get("truncated")),
            "rowsIncluded": False,
        },
    }
    if include_content:
        payload["content"] = content
    return payload


def get_analysis_snapshot(
    connection: sqlite3.Connection,
    workspace_id: str,
    snapshot_key: str,
    *,
    include_content: bool = False,
) -> dict[str, Any] | None:
    row = connection.execute(
        "SELECT * FROM analysis_snapshots WHERE workspace_id = ? AND snapshot_key = ?",
        (workspace_id, snapshot_key),
    ).fetchone()
    return _row_payload(row, include_content=include_content) if row else None


def analysis_snapshot_consumer_state(
    connection: sqlite3.Connection,
    workspace_id: str,
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    blockers: list[str] = []
    stored_status = str(snapshot.get("storedStatus") or "active")
    if stored_status == "deleted":
        blockers.append("analysis-snapshot-deleted")
    unit_key = str(snapshot.get("unitKey") or "")
    unit = get_analysis_unit(connection, workspace_id, unit_key) if unit_key else None
    unit_state = analysis_unit_consumer_state(connection, workspace_id, unit) if unit else None
    if not unit:
        blockers.append("analysis-snapshot-unit-missing")
    elif not unit_state or not unit_state.get("usable"):
        blockers.extend((unit_state or {}).get("blockers") or ["analysis-snapshot-unit-stale"])
    binding = snapshot.get("binding") if isinstance(snapshot.get("binding"), dict) else {}
    if unit:
        if str(binding.get("unitDefinitionFingerprint") or "") != str(unit.get("definitionFingerprint") or ""):
            blockers.append("analysis-snapshot-unit-definition-mismatch")
        if str(binding.get("resultFingerprint") or "") != str(unit.get("resultFingerprint") or ""):
            blockers.append("analysis-snapshot-result-fingerprint-mismatch")
        receipt = get_query_receipt(connection, workspace_id, str(unit.get("queryReceiptKey") or ""))
        if not receipt:
            blockers.append("analysis-snapshot-query-receipt-missing")
        elif str(binding.get("receiptBindingFingerprint") or "") != query_receipt_binding_fingerprint(receipt):
            blockers.append("analysis-snapshot-receipt-binding-mismatch")
    if "content" in snapshot:
        content = snapshot.get("content") if isinstance(snapshot.get("content"), dict) else {}
        if stored_status != "deleted" and _fingerprint(content) != str(snapshot.get("contentHash") or ""):
            blockers.append("analysis-snapshot-content-drifted")
    blockers = list(dict.fromkeys(str(item) for item in blockers if str(item).strip()))
    status = "deleted" if stored_status == "deleted" else "missing" if not unit else "stale" if blockers else "current"
    return {
        "schema": "aibi-analysis-snapshot-consumer-state/v1",
        "snapshotKey": snapshot.get("snapshotKey"),
        "status": status,
        "usableForPlanning": status == "current",
        "blockers": blockers,
        "staleFallbackUsed": False,
        "unitFreshness": unit_state,
    }


def _public_snapshot(connection: sqlite3.Connection, workspace_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    freshness = analysis_snapshot_consumer_state(connection, workspace_id, snapshot)
    public = {key: value for key, value in snapshot.items() if key != "content"}
    return {**public, "status": freshness["status"], "freshness": freshness}


def _require_expected_plan(args: argparse.Namespace, plan: dict[str, Any]) -> None:
    expected = str(getattr(args, "expected_plan", "") or "").strip()
    if not expected or expected != str(plan.get("planFingerprint") or ""):
        raise ValueError("Confirmation requires --expected-plan from the dry-run receipt.")


def _load_current_unit(
    connection: sqlite3.Connection,
    workspace_id: str,
    unit_key: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    unit = get_analysis_unit(connection, workspace_id, unit_key)
    if not unit:
        raise ValueError("Unknown Analysis Unit in the active workspace.")
    state = analysis_unit_consumer_state(connection, workspace_id, unit)
    if not state.get("usable") or str(unit.get("status") or "") != "ready":
        blockers = state.get("blockers") or (unit.get("validation") or {}).get("blockers") or ["analysis-unit-not-current-ready"]
        raise ValueError(f"Analysis Snapshot requires a current ready Analysis Unit: {', '.join(str(item) for item in blockers)}")
    receipt = get_query_receipt(connection, workspace_id, str(unit.get("queryReceiptKey") or ""))
    if not receipt:
        raise ValueError("Analysis Snapshot requires the Unit Query Receipt.")
    return unit, receipt


def _create_plan(
    *,
    operation: str,
    workspace_id: str,
    unit: dict[str, Any],
    receipt: dict[str, Any],
    parent: dict[str, Any] | None,
    reason: str,
    row_limit: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str, str, str]:
    binding = _binding_payload(unit, receipt)
    content = _content_payload(unit, row_limit)
    semantic_fingerprint = _semantic_fingerprint(unit, receipt)
    binding_fingerprint = _fingerprint(binding)
    content_hash = _fingerprint(content)
    requested = {
        "operation": operation,
        "workspaceId": workspace_id,
        "unitKey": unit.get("unitKey"),
        "queryReceiptKey": unit.get("queryReceiptKey"),
        "parentSnapshotKey": parent.get("snapshotKey") if parent else None,
        "reason": reason,
        "rowLimit": row_limit,
        "semanticFingerprint": semantic_fingerprint,
        "bindingFingerprint": binding_fingerprint,
        "contentHash": content_hash,
    }
    input_fingerprint = _fingerprint({"schema": ANALYSIS_SNAPSHOT_PLAN_SCHEMA, **requested})
    plan = {
        "schema": ANALYSIS_SNAPSHOT_PLAN_SCHEMA,
        "status": "waiting-confirmation",
        "operation": operation,
        "workspaceId": workspace_id,
        "requested": requested,
        "snapshotKey": f"analysis_snapshot_{input_fingerprint[:20]}",
        "inputFingerprint": input_fingerprint,
        "planFingerprint": _fingerprint({"schema": ANALYSIS_SNAPSHOT_PLAN_SCHEMA, "inputFingerprint": input_fingerprint}),
        "writesBusinessState": True,
        "businessRowsInResponse": 0,
    }
    return plan, binding, content, semantic_fingerprint, binding_fingerprint, content_hash


def _snapshot_create_like_command(
    args: argparse.Namespace,
    *,
    operation: str,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    if operation not in SNAPSHOT_OPERATIONS:
        raise ValueError(f"Unsupported Analysis Snapshot operation: {operation}")
    reason = str(getattr(args, "reason", "") or "").strip()
    if not reason:
        raise ValueError("Analysis Snapshot reason is required.")
    requested_limit = int(getattr(args, "row_limit", MAX_RESULT_ROWS) or MAX_RESULT_ROWS)
    if requested_limit < 1 or requested_limit > MAX_RESULT_ROWS:
        raise ValueError(f"row-limit must be between 1 and {MAX_RESULT_ROWS}.")
    with closing(open_db()) as connection:
        if connection.in_transaction:
            connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        workspace_id = active_workspace_id(connection)
        unit, receipt = _load_current_unit(connection, workspace_id, str(args.unit))
        parent_key = str(getattr(args, "snapshot", "") or "").strip()
        parent = get_analysis_snapshot(connection, workspace_id, parent_key) if parent_key else None
        if operation == "create" and parent_key:
            raise ValueError("Create does not accept a parent Snapshot; use refresh or replace.")
        if operation in {"refresh", "replace"} and not parent:
            raise ValueError("Refresh and replace require an existing parent Snapshot in the active workspace.")
        if parent and str(parent.get("storedStatus") or "") == "deleted":
            raise ValueError("A deleted Analysis Snapshot cannot be refreshed or replaced.")
        row_count = int((unit.get("shape") or {}).get("rowCount") or len(unit.get("rows") or []))
        row_limit = min(requested_limit, max(1, row_count))
        plan, binding, content, semantic_fingerprint, binding_fingerprint, content_hash = _create_plan(
            operation=operation,
            workspace_id=workspace_id,
            unit=unit,
            receipt=receipt,
            parent=parent,
            reason=reason,
            row_limit=row_limit,
        )
        if operation == "refresh" and parent and str(parent.get("semanticFingerprint") or "") != semantic_fingerprint:
            raise ValueError("Refresh requires the same metric, grain, filters, and result shape; use replace for a semantic change.")
        existing = get_analysis_snapshot(connection, workspace_id, str(plan["snapshotKey"]), include_content=True)
        plan["alreadyExists"] = existing is not None and str(existing.get("storedStatus") or "") != "deleted"
        if not bool(getattr(args, "yes", False)):
            connection.rollback()
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "workspaceId": workspace_id, "analysisSnapshotPlan": plan}
        _require_expected_plan(args, plan)
        if existing:
            if str(existing.get("storedStatus") or "") == "deleted":
                raise ValueError("The exact Analysis Snapshot input was deleted; use a new reason to create a new immutable record.")
            existing_state = analysis_snapshot_consumer_state(connection, workspace_id, existing)
            if existing_state.get("status") != "current":
                raise ValueError(
                    "The exact Analysis Snapshot input exists but failed current integrity checks: "
                    + ", ".join(str(item) for item in existing_state.get("blockers") or ["analysis-snapshot-not-current"])
                )
            connection.rollback()
            return {
                "ok": True,
                "confirmed": True,
                "changed": False,
                "workspaceId": workspace_id,
                "analysisSnapshotPlan": plan,
                "analysisSnapshot": _public_snapshot(connection, workspace_id, existing),
            }
        created_at = now_iso()
        connection.execute(
            """
            INSERT INTO analysis_snapshots(
              snapshot_key, workspace_id, parent_snapshot_key, operation, status, reason,
              unit_key, query_receipt_key, semantic_fingerprint, binding_fingerprint,
              binding_json, row_limit, row_count, content_hash, content_json,
              input_fingerprint, created_at, deleted_at
            ) VALUES(?, ?, ?, ?, 'active', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
            """,
            (
                plan["snapshotKey"], workspace_id, parent.get("snapshotKey") if parent else None, operation, reason,
                unit.get("unitKey"), unit.get("queryReceiptKey"), semantic_fingerprint, binding_fingerprint,
                _canonical_json(binding), row_limit, int(content["rowCount"]), content_hash, _canonical_json(content),
                plan["inputFingerprint"], created_at,
            ),
        )
        connection.commit()
        created = get_analysis_snapshot(connection, workspace_id, str(plan["snapshotKey"]))
        if not created:
            raise RuntimeError("Analysis Snapshot persistence failed.")
        return {
            "ok": True,
            "confirmed": True,
            "changed": True,
            "workspaceId": workspace_id,
            "analysisSnapshotPlan": plan,
            "analysisSnapshot": _public_snapshot(connection, workspace_id, created),
        }


def analysis_snapshot_create_command(args: argparse.Namespace, **dependencies: Any) -> dict[str, Any]:
    return _snapshot_create_like_command(args, operation="create", **dependencies)


def analysis_snapshot_refresh_command(args: argparse.Namespace, **dependencies: Any) -> dict[str, Any]:
    return _snapshot_create_like_command(args, operation="refresh", **dependencies)


def analysis_snapshot_replace_command(args: argparse.Namespace, **dependencies: Any) -> dict[str, Any]:
    return _snapshot_create_like_command(args, operation="replace", **dependencies)


def analysis_snapshot_delete_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    with closing(open_db()) as connection:
        if connection.in_transaction:
            connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        workspace_id = active_workspace_id(connection)
        snapshot = get_analysis_snapshot(connection, workspace_id, str(args.snapshot), include_content=True)
        if not snapshot:
            raise ValueError("Unknown Analysis Snapshot in the active workspace.")
        already_deleted = str(snapshot.get("storedStatus") or "") == "deleted"
        plan_input = {
            "operation": "delete",
            "workspaceId": workspace_id,
            "snapshotKey": snapshot.get("snapshotKey"),
            "contentHash": snapshot.get("contentHash"),
            "bindingFingerprint": snapshot.get("bindingFingerprint"),
            "alreadyDeleted": already_deleted,
        }
        plan = {
            "schema": ANALYSIS_SNAPSHOT_PLAN_SCHEMA,
            "status": "waiting-confirmation",
            **plan_input,
            "planFingerprint": _fingerprint({"schema": ANALYSIS_SNAPSHOT_PLAN_SCHEMA, **plan_input}),
            "writesBusinessState": True,
            "businessRowsInResponse": 0,
        }
        if not bool(getattr(args, "yes", False)):
            connection.rollback()
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "workspaceId": workspace_id, "analysisSnapshotPlan": plan}
        _require_expected_plan(args, plan)
        if already_deleted:
            connection.rollback()
            return {"ok": True, "confirmed": True, "changed": False, "workspaceId": workspace_id, "analysisSnapshotPlan": plan, "analysisSnapshot": _public_snapshot(connection, workspace_id, snapshot)}
        deleted_at = now_iso()
        connection.execute(
            """
            UPDATE analysis_snapshots
            SET status = 'deleted', content_json = '{}', row_count = 0, deleted_at = ?
            WHERE workspace_id = ? AND snapshot_key = ?
            """,
            (deleted_at, workspace_id, snapshot["snapshotKey"]),
        )
        connection.commit()
        deleted = get_analysis_snapshot(connection, workspace_id, str(snapshot["snapshotKey"]))
        return {
            "ok": True,
            "confirmed": True,
            "changed": True,
            "workspaceId": workspace_id,
            "analysisSnapshotPlan": plan,
            "analysisSnapshot": _public_snapshot(connection, workspace_id, deleted or snapshot),
        }


def analysis_snapshots_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with closing(open_db()) as connection:
        workspace_id = active_workspace_id(connection)
        snapshot_key = str(getattr(args, "snapshot", "") or "").strip()
        if snapshot_key:
            snapshot = get_analysis_snapshot(connection, workspace_id, snapshot_key, include_content=True)
            if not snapshot:
                raise ValueError("Unknown Analysis Snapshot in the active workspace.")
            return {"ok": True, "workspaceId": workspace_id, "analysisSnapshot": _public_snapshot(connection, workspace_id, snapshot)}
        clauses = ["workspace_id = ?"]
        params: list[Any] = [workspace_id]
        unit_key = str(getattr(args, "unit", "") or "").strip()
        if unit_key:
            clauses.append("unit_key = ?")
            params.append(unit_key)
        requested_limit = max(1, min(int(getattr(args, "limit", 30) or 30), 100))
        requested_status = str(getattr(args, "status", "") or "").strip()
        rows = connection.execute(
            f"SELECT * FROM analysis_snapshots WHERE {' AND '.join(clauses)} ORDER BY created_at DESC LIMIT ?",
            (*params, 100 if requested_status else requested_limit),
        ).fetchall()
        snapshots = [_public_snapshot(connection, workspace_id, _row_payload(row, include_content=True)) for row in rows]
        if requested_status:
            snapshots = [snapshot for snapshot in snapshots if snapshot.get("status") == requested_status][:requested_limit]
        return {
            "ok": True,
            "schema": "aibi-analysis-snapshots/v1",
            "workspaceId": workspace_id,
            "analysisSnapshots": snapshots,
            "count": len(snapshots),
            "businessRowsCopied": False,
            "staleFallbackUsed": False,
        }
