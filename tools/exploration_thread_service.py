from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from typing import Any, Callable

from analysis_run_service import get_analysis_run
from analysis_unit_service import analysis_unit_consumer_state, get_analysis_unit
from query_plan_receipt_service import get_query_receipt, query_receipt_binding_fingerprint


THREAD_SCHEMA = "aibi-exploration-thread/v1"
ANCHOR_SCHEMA = "aibi-exploration-anchor/v1"
BOARD_SCHEMA = "aibi-exploration-result-board/v1"
PLAN_SCHEMA = "aibi-exploration-mutation-plan/v1"
ELIGIBLE_RUN_STATUSES = {"executed", "confirmed"}
MAX_TITLE_LENGTH = 120
MAX_LABEL_LENGTH = 80


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _clean(value: Any, fallback: str, limit: int) -> str:
    return " ".join(str(value or fallback).split())[:limit] or fallback


def _thread_key(workspace_id: str, run_key: str) -> str:
    return f"exploration_thread_{_hash({'workspaceId': workspace_id, 'rootRunKey': run_key})[:20]}"


def _anchor_key(thread_key: str, run_key: str) -> str:
    return f"exploration_anchor_{_hash({'threadKey': thread_key, 'runKey': run_key})[:20]}"


def _board_item_key(thread_key: str, anchor_key: str) -> str:
    return f"exploration_board_{_hash({'threadKey': thread_key, 'anchorKey': anchor_key})[:20]}"


def _run_fingerprint(run: dict[str, Any]) -> str:
    return _hash({
        "runKey": run.get("run_key"),
        "parentRunKey": run.get("parent_run_key"),
        "branchLabel": run.get("branch_label"),
        "question": run.get("question"),
        "status": run.get("status"),
        "queryReceiptKey": run.get("query_receipt_key"),
        "actionKey": run.get("action_key"),
        "result": run.get("result"),
    })


def _unit_fingerprint(unit: dict[str, Any]) -> str:
    return _hash({
        "unitKey": unit.get("unitKey"),
        "queryReceiptKey": unit.get("queryReceiptKey"),
        "kind": unit.get("kind"),
        "status": unit.get("status"),
        "definitionFingerprint": unit.get("definitionFingerprint"),
        "resultFingerprint": unit.get("resultFingerprint"),
        "chartInputFingerprint": (unit.get("chartAdapter") or {}).get("inputFingerprint"),
    })


def _load_json(value: Any) -> dict[str, Any]:
    try:
        result = json.loads(str(value or "{}"))
    except (TypeError, json.JSONDecodeError):
        return {}
    return result if isinstance(result, dict) else {}


def _result_run_key(result: dict[str, Any]) -> str:
    run = result.get("analysisRun") if isinstance(result.get("analysisRun"), dict) else {}
    return str(run.get("run_key") or run.get("runKey") or "")


def _validate_turn_binding(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    run_key: str,
    session_key: str,
    turn_key: str,
) -> dict[str, str]:
    if bool(session_key) != bool(turn_key):
        raise ValueError("Exploration context requires both session and turn, or neither.")
    if not session_key:
        return {"sessionKey": "", "turnKey": "", "turnContextFingerprint": ""}
    session = connection.execute(
        "SELECT * FROM agent_sessions WHERE workspace_id = ? AND session_key = ?",
        (workspace_id, session_key),
    ).fetchone()
    if not session:
        raise ValueError("Exploration Session does not exist in the active workspace.")
    turn = connection.execute(
        "SELECT * FROM agent_turns WHERE workspace_id = ? AND turn_key = ? AND session_key = ?",
        (workspace_id, turn_key, session_key),
    ).fetchone()
    if not turn:
        raise ValueError("Exploration Turn does not belong to the selected Session in the active workspace.")
    if str(turn["status"]) != "completed":
        raise ValueError("Exploration Anchor requires a completed Agent Turn.")
    if _result_run_key(_load_json(turn["result_json"])) != run_key:
        raise ValueError("Exploration Turn does not reference the selected Analysis Run.")
    return {
        "sessionKey": session_key,
        "turnKey": turn_key,
        "turnContextFingerprint": str(turn["context_fingerprint"] or ""),
    }


def _resolve_current_unit(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    receipt_key: str,
    unit_key: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if unit_key:
        unit = get_analysis_unit(connection, workspace_id, unit_key)
        if not unit:
            raise ValueError("Unknown Analysis Unit in the active workspace.")
        candidates = [unit]
    else:
        rows = connection.execute(
            "SELECT unit_key FROM analysis_units WHERE workspace_id = ? AND query_receipt_key = ? ORDER BY updated_at DESC",
            (workspace_id, receipt_key),
        ).fetchall()
        candidates = [
            unit
            for row in rows
            if (unit := get_analysis_unit(connection, workspace_id, str(row["unit_key"]))) is not None
        ]
        if len(candidates) != 1:
            raise ValueError("Exploration Anchor requires one explicit Analysis Unit when the Receipt has zero or multiple Units.")
    unit = candidates[0]
    if str(unit.get("queryReceiptKey") or "") != receipt_key:
        raise ValueError("Analysis Unit is not bound to the Analysis Run Receipt.")
    freshness = analysis_unit_consumer_state(connection, workspace_id, unit)
    if str(unit.get("status") or "") != "ready" or not freshness.get("usable"):
        blockers = ", ".join(str(item) for item in freshness.get("blockers") or ["analysis-unit-not-ready"])
        raise ValueError(f"Exploration Anchor requires a current ready Analysis Unit: {blockers}")
    return unit, freshness


def _anchor_material(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    thread_key: str,
    parent_anchor_key: str | None,
    run_key: str,
    unit_key: str,
    session_key: str,
    turn_key: str,
    label: str,
) -> dict[str, Any]:
    run = get_analysis_run(connection, workspace_id, run_key)
    if not run:
        raise ValueError("Unknown Analysis Run in the active workspace.")
    if str(run.get("status") or "") not in ELIGIBLE_RUN_STATUSES:
        raise ValueError("Exploration Anchor requires an executed or confirmed Analysis Run.")
    receipt_key = str(run.get("query_receipt_key") or "")
    receipt = get_query_receipt(connection, workspace_id, receipt_key)
    if not receipt or str(receipt.get("status") or "") != "executed":
        raise ValueError("Exploration Anchor requires an executed Query Plan Receipt.")
    unit, unit_freshness = _resolve_current_unit(
        connection,
        workspace_id=workspace_id,
        receipt_key=receipt_key,
        unit_key=unit_key,
    )
    turn_binding = _validate_turn_binding(
        connection,
        workspace_id=workspace_id,
        run_key=run_key,
        session_key=session_key,
        turn_key=turn_key,
    )
    run_fp = _run_fingerprint(run)
    receipt_fp = query_receipt_binding_fingerprint(receipt)
    unit_fp = _unit_fingerprint(unit)
    result_fp = str(unit.get("resultFingerprint") or "")
    chart_fp = str((unit.get("chartAdapter") or {}).get("inputFingerprint") or "")
    refs = {
        "threadKey": thread_key,
        "parentAnchorKey": parent_anchor_key,
        "analysisRunKey": run_key,
        "queryReceiptKey": receipt_key,
        "analysisUnitKey": unit.get("unitKey"),
        "sessionKey": turn_binding["sessionKey"] or None,
        "turnKey": turn_binding["turnKey"] or None,
        "runFingerprint": run_fp,
        "receiptFingerprint": receipt_fp,
        "unitFingerprint": unit_fp,
        "resultFingerprint": result_fp,
        "chartInputFingerprint": chart_fp,
        "turnContextFingerprint": turn_binding["turnContextFingerprint"],
    }
    binding_fp = _hash(refs)
    shape = unit.get("shape") if isinstance(unit.get("shape"), dict) else {}
    grain = unit.get("grain") if isinstance(unit.get("grain"), dict) else {}
    chart = unit.get("chartAdapter") if isinstance(unit.get("chartAdapter"), dict) else {}
    dimension_columns, measure_column = _business_columns(unit)
    return {
        "schema": ANCHOR_SCHEMA,
        "anchorKey": _anchor_key(thread_key, run_key),
        "workspaceId": workspace_id,
        "threadKey": thread_key,
        "parentAnchorKey": parent_anchor_key,
        "label": _clean(label, str(run.get("branch_label") or run.get("question") or "分析结果"), MAX_LABEL_LENGTH),
        **refs,
        "bindingFingerprint": binding_fp,
        "preview": {
            "question": str(run.get("question") or ""),
            "runStatus": str(run.get("status") or ""),
            "unitKind": str(unit.get("kind") or ""),
            "unitTitle": str(unit.get("title") or ""),
            "dimensionColumns": dimension_columns,
            "measureColumn": measure_column,
            "sourceTableKeys": list(grain.get("sourceTableKeys") or []),
            "chartType": chart.get("chartType"),
            "unitUsable": bool(unit_freshness.get("usable")),
            "rowsCopiedToThread": False,
        },
    }


def _thread_row(connection: sqlite3.Connection, workspace_id: str, thread_key: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM exploration_threads WHERE workspace_id = ? AND thread_key = ?",
        (workspace_id, thread_key),
    ).fetchone()


def _anchor_row(connection: sqlite3.Connection, workspace_id: str, anchor_key: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM exploration_anchors WHERE workspace_id = ? AND anchor_key = ?",
        (workspace_id, anchor_key),
    ).fetchone()


def _plan_payload(kind: str, workspace_id: str, proposed: dict[str, Any], already_exists: bool = False) -> dict[str, Any]:
    stable = {
        "schema": PLAN_SCHEMA,
        "kind": kind,
        "workspaceId": workspace_id,
        "proposed": proposed,
        "alreadyExists": already_exists,
        "providerCanMutate": False,
        "businessRowsCopied": False,
    }
    return {**stable, "planFingerprint": _hash(stable)}


def _require_expected_plan(args: argparse.Namespace, plan: dict[str, Any]) -> None:
    expected = str(getattr(args, "expected_plan", "") or "").strip()
    if not expected:
        raise ValueError("Confirmation requires --expected-plan from the dry-run receipt.")
    if expected != str(plan.get("planFingerprint") or ""):
        raise ValueError("Exploration mutation plan changed after preview; run the dry-run again.")


def _insert_anchor(connection: sqlite3.Connection, material: dict[str, Any], created_at: str) -> None:
    connection.execute(
        """
        INSERT INTO exploration_anchors(
          anchor_key, workspace_id, thread_key, parent_anchor_key, label,
          analysis_run_key, query_receipt_key, analysis_unit_key, session_key, turn_key,
          run_fingerprint, receipt_fingerprint, unit_fingerprint, result_fingerprint,
          chart_input_fingerprint, turn_context_fingerprint, binding_fingerprint, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            material["anchorKey"], material["workspaceId"], material["threadKey"], material["parentAnchorKey"], material["label"],
            material["analysisRunKey"], material["queryReceiptKey"], material["analysisUnitKey"], material["sessionKey"], material["turnKey"],
            material["runFingerprint"], material["receiptFingerprint"], material["unitFingerprint"], material["resultFingerprint"],
            material["chartInputFingerprint"], material["turnContextFingerprint"], material["bindingFingerprint"], created_at,
        ),
    )


def _insert_board_item(connection: sqlite3.Connection, *, workspace_id: str, thread_key: str, anchor_key: str, position: int, now: str) -> str:
    item_key = _board_item_key(thread_key, anchor_key)
    connection.execute(
        """
        INSERT INTO exploration_board_items(board_item_key, workspace_id, thread_key, anchor_key, position, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(workspace_id, thread_key, anchor_key) DO UPDATE SET
          position = excluded.position, updated_at = excluded.updated_at
        """,
        (item_key, workspace_id, thread_key, anchor_key, position, now, now),
    )
    return item_key


def _business_columns(unit: dict[str, Any]) -> tuple[list[str], str | None]:
    """Prefer source-bound business fields over transient result aliases."""
    grain = unit.get("grain") if isinstance(unit.get("grain"), dict) else {}
    shape = unit.get("shape") if isinstance(unit.get("shape"), dict) else {}
    dimensions = [
        str(item.get("field"))
        for item in (grain.get("dimensions") or [])
        if isinstance(item, dict) and item.get("field")
    ]
    measures = [
        str(item.get("field"))
        for item in (grain.get("measures") or [])
        if isinstance(item, dict) and item.get("field")
    ]
    if not dimensions:
        dimensions = list(shape.get("dimensionColumns") or ([shape.get("dimensionColumn")] if shape.get("dimensionColumn") else []))
    measure = measures[0] if measures else shape.get("measureColumn")
    return dimensions, str(measure) if measure else None


def exploration_thread_create_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    with open_db() as connection:
        if connection.in_transaction:
            connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        workspace_id = active_workspace_id(connection)
        run_key = str(args.run)
        thread_key = _thread_key(workspace_id, run_key)
        existing = _thread_row(connection, workspace_id, thread_key)
        material = _anchor_material(
            connection,
            workspace_id=workspace_id,
            thread_key=thread_key,
            parent_anchor_key=None,
            run_key=run_key,
            unit_key=str(getattr(args, "unit", "") or ""),
            session_key=str(getattr(args, "session", "") or ""),
            turn_key=str(getattr(args, "turn", "") or ""),
            label=str(getattr(args, "label", "") or ""),
        )
        run = get_analysis_run(connection, workspace_id, run_key) or {}
        if run.get("parent_run_key"):
            raise ValueError("Exploration Thread root must be an Analysis Run without a parent.")
        proposed = {
            "threadKey": thread_key,
            "title": str(existing["title"]) if existing else _clean(getattr(args, "title", ""), str(run.get("question") or "探索线程"), MAX_TITLE_LENGTH),
            "rootAnchor": material,
            "initialBoardPosition": 1,
        }
        plan = _plan_payload("thread-create", workspace_id, proposed, already_exists=existing is not None)
        if not bool(getattr(args, "yes", False)):
            connection.rollback()
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "workspaceId": workspace_id, "explorationPlan": plan}
        _require_expected_plan(args, plan)
        if existing:
            connection.rollback()
            return {"ok": True, "confirmed": True, "changed": False, "workspaceId": workspace_id, "explorationPlan": plan, "threadKey": thread_key}
        now = now_iso()
        connection.execute(
            "INSERT INTO exploration_threads(thread_key, workspace_id, title, status, root_anchor_key, current_anchor_key, created_at, updated_at) VALUES(?, ?, ?, 'active', ?, ?, ?, ?)",
            (thread_key, workspace_id, proposed["title"], material["anchorKey"], material["anchorKey"], now, now),
        )
        _insert_anchor(connection, material, now)
        _insert_board_item(connection, workspace_id=workspace_id, thread_key=thread_key, anchor_key=material["anchorKey"], position=1, now=now)
        connection.commit()
    return {"ok": True, "confirmed": True, "changed": True, "workspaceId": workspace_id, "explorationPlan": plan, "threadKey": thread_key, "anchorKey": material["anchorKey"]}


def exploration_anchor_add_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    with open_db() as connection:
        if connection.in_transaction:
            connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        workspace_id = active_workspace_id(connection)
        thread_key = str(args.thread)
        thread = _thread_row(connection, workspace_id, thread_key)
        if not thread:
            raise ValueError("Unknown Exploration Thread in the active workspace.")
        parent_anchor_key = str(getattr(args, "parent_anchor", "") or thread["current_anchor_key"])
        parent = _anchor_row(connection, workspace_id, parent_anchor_key)
        if not parent or str(parent["thread_key"]) != thread_key:
            raise ValueError("Parent Anchor does not belong to the Exploration Thread.")
        material = _anchor_material(
            connection,
            workspace_id=workspace_id,
            thread_key=thread_key,
            parent_anchor_key=parent_anchor_key,
            run_key=str(args.run),
            unit_key=str(getattr(args, "unit", "") or ""),
            session_key=str(getattr(args, "session", "") or ""),
            turn_key=str(getattr(args, "turn", "") or ""),
            label=str(getattr(args, "label", "") or ""),
        )
        run = get_analysis_run(connection, workspace_id, str(args.run)) or {}
        if str(run.get("parent_run_key") or "") != str(parent["analysis_run_key"]):
            raise ValueError("Analysis Run parent does not match the selected Exploration Anchor.")
        existing = connection.execute(
            "SELECT * FROM exploration_anchors WHERE workspace_id = ? AND thread_key = ? AND analysis_run_key = ?",
            (workspace_id, thread_key, str(args.run)),
        ).fetchone()
        next_position = int(connection.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 FROM exploration_board_items WHERE workspace_id = ? AND thread_key = ?",
            (workspace_id, thread_key),
        ).fetchone()[0])
        proposed = {
            "threadKey": thread_key,
            "parentAnchorKey": parent_anchor_key,
            "anchor": material,
            "boardPosition": next_position,
        }
        plan = _plan_payload("anchor-add", workspace_id, proposed, already_exists=existing is not None)
        if not bool(getattr(args, "yes", False)):
            connection.rollback()
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "workspaceId": workspace_id, "explorationPlan": plan}
        _require_expected_plan(args, plan)
        if existing:
            connection.rollback()
            return {"ok": True, "confirmed": True, "changed": False, "workspaceId": workspace_id, "explorationPlan": plan, "threadKey": thread_key, "anchorKey": str(existing["anchor_key"])}
        now = now_iso()
        _insert_anchor(connection, material, now)
        _insert_board_item(connection, workspace_id=workspace_id, thread_key=thread_key, anchor_key=material["anchorKey"], position=next_position, now=now)
        connection.execute(
            "UPDATE exploration_threads SET current_anchor_key = ?, updated_at = ? WHERE workspace_id = ? AND thread_key = ?",
            (material["anchorKey"], now, workspace_id, thread_key),
        )
        connection.commit()
    return {"ok": True, "confirmed": True, "changed": True, "workspaceId": workspace_id, "explorationPlan": plan, "threadKey": thread_key, "anchorKey": material["anchorKey"]}


def exploration_board_set_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    with open_db() as connection:
        if connection.in_transaction:
            connection.commit()
        connection.execute("BEGIN IMMEDIATE")
        workspace_id = active_workspace_id(connection)
        thread_key = str(args.thread)
        if not _thread_row(connection, workspace_id, thread_key):
            raise ValueError("Unknown Exploration Thread in the active workspace.")
        anchor_key = str(args.anchor)
        anchor = _anchor_row(connection, workspace_id, anchor_key)
        if not anchor or str(anchor["thread_key"]) != thread_key:
            raise ValueError("Result Board Anchor does not belong to the Exploration Thread.")
        existing = connection.execute(
            "SELECT * FROM exploration_board_items WHERE workspace_id = ? AND thread_key = ? AND anchor_key = ?",
            (workspace_id, thread_key, anchor_key),
        ).fetchone()
        state = str(args.state)
        requested_position = int(getattr(args, "position", 0) or 0)
        position = requested_position if requested_position > 0 else int(existing["position"]) if existing else int(connection.execute(
            "SELECT COALESCE(MAX(position), 0) + 1 FROM exploration_board_items WHERE workspace_id = ? AND thread_key = ?",
            (workspace_id, thread_key),
        ).fetchone()[0])
        proposed = {
            "threadKey": thread_key,
            "anchorKey": anchor_key,
            "state": state,
            "position": position,
            "anchorHistoryDeleted": False,
        }
        already_applied = (state == "removed" and existing is None) or (state == "pinned" and existing is not None and int(existing["position"]) == position)
        plan = _plan_payload("board-set", workspace_id, proposed, already_exists=already_applied)
        if not bool(getattr(args, "yes", False)):
            connection.rollback()
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "workspaceId": workspace_id, "explorationPlan": plan}
        _require_expected_plan(args, plan)
        now = now_iso()
        changed = not already_applied
        if not changed:
            connection.rollback()
            return {"ok": True, "confirmed": True, "changed": False, "workspaceId": workspace_id, "explorationPlan": plan, "threadKey": thread_key, "anchorKey": anchor_key}
        if state == "removed":
            connection.execute(
                "DELETE FROM exploration_board_items WHERE workspace_id = ? AND thread_key = ? AND anchor_key = ?",
                (workspace_id, thread_key, anchor_key),
            )
        else:
            _insert_board_item(connection, workspace_id=workspace_id, thread_key=thread_key, anchor_key=anchor_key, position=position, now=now)
        connection.execute(
            "UPDATE exploration_threads SET updated_at = ? WHERE workspace_id = ? AND thread_key = ?",
            (now, workspace_id, thread_key),
        )
        connection.commit()
    return {"ok": True, "confirmed": True, "changed": changed, "workspaceId": workspace_id, "explorationPlan": plan, "threadKey": thread_key, "anchorKey": anchor_key}


def _anchor_freshness(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    row: sqlite3.Row,
    anchors_by_key: dict[str, sqlite3.Row],
) -> tuple[dict[str, Any], dict[str, Any]]:
    blockers: list[str] = []
    missing: list[str] = []
    run = get_analysis_run(connection, workspace_id, str(row["analysis_run_key"]))
    receipt = get_query_receipt(connection, workspace_id, str(row["query_receipt_key"]))
    unit = get_analysis_unit(connection, workspace_id, str(row["analysis_unit_key"]))
    if not run:
        missing.append("analysis-run")
        blockers.append("exploration-analysis-run-missing")
    if not receipt:
        missing.append("query-receipt")
        blockers.append("exploration-query-receipt-missing")
    if not unit:
        missing.append("analysis-unit")
        blockers.append("exploration-analysis-unit-missing")
    if run:
        if str(run.get("status") or "") not in ELIGIBLE_RUN_STATUSES:
            blockers.append("exploration-analysis-run-not-eligible")
        if str(run.get("query_receipt_key") or "") != str(row["query_receipt_key"]):
            blockers.append("exploration-run-receipt-binding-drifted")
        if _run_fingerprint(run) != str(row["run_fingerprint"]):
            blockers.append("exploration-analysis-run-drifted")
    unit_state = None
    if receipt:
        if str(receipt.get("status") or "") != "executed":
            blockers.append("exploration-query-receipt-not-executed")
        if query_receipt_binding_fingerprint(receipt) != str(row["receipt_fingerprint"]):
            blockers.append("exploration-query-receipt-binding-drifted")
    if unit:
        unit_state = analysis_unit_consumer_state(connection, workspace_id, unit)
        if not unit_state.get("usable"):
            blockers.extend(str(item) for item in unit_state.get("blockers") or [])
        if str(unit.get("queryReceiptKey") or "") != str(row["query_receipt_key"]):
            blockers.append("exploration-unit-receipt-binding-drifted")
        if _unit_fingerprint(unit) != str(row["unit_fingerprint"]):
            blockers.append("exploration-analysis-unit-drifted")
        if str(unit.get("resultFingerprint") or "") != str(row["result_fingerprint"]):
            blockers.append("exploration-result-fingerprint-drifted")
        if str((unit.get("chartAdapter") or {}).get("inputFingerprint") or "") != str(row["chart_input_fingerprint"]):
            blockers.append("exploration-chart-input-drifted")
    session_key = str(row["session_key"] or "")
    turn_key = str(row["turn_key"] or "")
    if session_key or turn_key:
        session = connection.execute(
            "SELECT 1 FROM agent_sessions WHERE workspace_id = ? AND session_key = ?",
            (workspace_id, session_key),
        ).fetchone()
        turn = connection.execute(
            "SELECT * FROM agent_turns WHERE workspace_id = ? AND turn_key = ? AND session_key = ?",
            (workspace_id, turn_key, session_key),
        ).fetchone()
        if not session:
            missing.append("agent-session")
            blockers.append("exploration-agent-session-missing")
        if not turn:
            missing.append("agent-turn")
            blockers.append("exploration-agent-turn-missing")
        elif _result_run_key(_load_json(turn["result_json"])) != str(row["analysis_run_key"]):
            blockers.append("exploration-turn-run-binding-drifted")
        elif str(turn["context_fingerprint"] or "") != str(row["turn_context_fingerprint"] or ""):
            blockers.append("exploration-turn-context-drifted")
    parent_anchor_key = str(row["parent_anchor_key"] or "")
    if parent_anchor_key:
        parent = anchors_by_key.get(parent_anchor_key)
        if not parent:
            missing.append("parent-anchor")
            blockers.append("exploration-parent-anchor-missing")
        elif run and str(run.get("parent_run_key") or "") != str(parent["analysis_run_key"]):
            blockers.append("exploration-parent-run-lineage-drifted")
    elif run and run.get("parent_run_key"):
        blockers.append("exploration-root-run-has-parent")
    current_refs = {
        "threadKey": str(row["thread_key"]),
        "parentAnchorKey": str(row["parent_anchor_key"]) if row["parent_anchor_key"] else None,
        "analysisRunKey": str(row["analysis_run_key"]),
        "queryReceiptKey": str(row["query_receipt_key"]),
        "analysisUnitKey": str(row["analysis_unit_key"]),
        "sessionKey": session_key or None,
        "turnKey": turn_key or None,
        "runFingerprint": _run_fingerprint(run) if run else "",
        "receiptFingerprint": query_receipt_binding_fingerprint(receipt) if receipt else "",
        "unitFingerprint": _unit_fingerprint(unit) if unit else "",
        "resultFingerprint": str(unit.get("resultFingerprint") or "") if unit else "",
        "chartInputFingerprint": str((unit.get("chartAdapter") or {}).get("inputFingerprint") or "") if unit else "",
        "turnContextFingerprint": str(row["turn_context_fingerprint"] or ""),
    }
    if not missing and _hash(current_refs) != str(row["binding_fingerprint"]):
        blockers.append("exploration-anchor-binding-drifted")
    blockers = list(dict.fromkeys(blockers))
    status = "missing" if missing else "stale" if blockers else "current"
    freshness = {
        "schema": "aibi-exploration-anchor-freshness/v1",
        "status": status,
        "usableForContinuation": not blockers,
        "missingRefs": list(dict.fromkeys(missing)),
        "blockers": blockers,
        "staleFallbackUsed": False,
        "unitFreshness": unit_state,
    }
    return freshness, {"run": run, "receipt": receipt, "unit": unit}


def _anchor_payload(row: sqlite3.Row, freshness: dict[str, Any], objects: dict[str, Any]) -> dict[str, Any]:
    run = objects.get("run") or {}
    unit = objects.get("unit") or {}
    shape = unit.get("shape") if isinstance(unit.get("shape"), dict) else {}
    grain = unit.get("grain") if isinstance(unit.get("grain"), dict) else {}
    chart = unit.get("chartAdapter") if isinstance(unit.get("chartAdapter"), dict) else {}
    dimension_columns, measure_column = _business_columns(unit)
    return {
        "schema": ANCHOR_SCHEMA,
        "anchorKey": row["anchor_key"],
        "workspaceId": row["workspace_id"],
        "threadKey": row["thread_key"],
        "parentAnchorKey": row["parent_anchor_key"],
        "label": row["label"],
        "analysisRunKey": row["analysis_run_key"],
        "queryReceiptKey": row["query_receipt_key"],
        "analysisUnitKey": row["analysis_unit_key"],
        "sessionKey": row["session_key"],
        "turnKey": row["turn_key"],
        "bindingFingerprint": row["binding_fingerprint"],
        "createdAt": row["created_at"],
        "freshness": freshness,
        "summary": {
            "question": str(run.get("question") or ""),
            "runStatus": str(run.get("status") or "missing"),
            "unitKind": str(unit.get("kind") or ""),
            "unitTitle": str(unit.get("title") or ""),
            "dimensionColumns": dimension_columns,
            "measureColumn": measure_column,
            "sourceTableKeys": list(grain.get("sourceTableKeys") or []),
            "chartType": chart.get("chartType") if freshness.get("usableForContinuation") else None,
            "allowedChartTypes": list(chart.get("allowedChartTypes") or []),
            "rowCount": shape.get("rowCount"),
            "rowsIncluded": False,
        },
    }


def _thread_payload(connection: sqlite3.Connection, workspace_id: str, row: sqlite3.Row) -> dict[str, Any]:
    anchor_rows = connection.execute(
        "SELECT * FROM exploration_anchors WHERE workspace_id = ? AND thread_key = ? ORDER BY created_at, anchor_key",
        (workspace_id, row["thread_key"]),
    ).fetchall()
    anchors_by_key = {str(item["anchor_key"]): item for item in anchor_rows}
    anchors: list[dict[str, Any]] = []
    for anchor_row in anchor_rows:
        freshness, objects = _anchor_freshness(
            connection,
            workspace_id=workspace_id,
            row=anchor_row,
            anchors_by_key=anchors_by_key,
        )
        anchors.append(_anchor_payload(anchor_row, freshness, objects))
    anchor_payload_by_key = {str(item["anchorKey"]): item for item in anchors}
    board_rows = connection.execute(
        "SELECT * FROM exploration_board_items WHERE workspace_id = ? AND thread_key = ? ORDER BY position, created_at, board_item_key",
        (workspace_id, row["thread_key"]),
    ).fetchall()
    board_items = [
        {
            "boardItemKey": item["board_item_key"],
            "anchorKey": item["anchor_key"],
            "position": int(item["position"]),
            "anchor": anchor_payload_by_key.get(str(item["anchor_key"])),
            "createdAt": item["created_at"],
            "updatedAt": item["updated_at"],
        }
        for item in board_rows
    ]
    current = anchor_payload_by_key.get(str(row["current_anchor_key"]))
    root = anchor_payload_by_key.get(str(row["root_anchor_key"]))
    missing_thread_refs = [name for name, value in (("root-anchor", root), ("current-anchor", current)) if value is None]
    current_usable = bool(current and current.get("freshness", {}).get("usableForContinuation"))
    return {
        "schema": THREAD_SCHEMA,
        "threadKey": row["thread_key"],
        "workspaceId": row["workspace_id"],
        "title": row["title"],
        "storedStatus": row["status"],
        "status": "missing" if missing_thread_refs else "current" if current_usable else "stale",
        "rootAnchorKey": row["root_anchor_key"],
        "currentAnchorKey": row["current_anchor_key"],
        "currentAnchorUsable": current_usable,
        "missingRefs": missing_thread_refs,
        "anchors": anchors,
        "anchorCount": len(anchors),
        "resultBoard": {
            "schema": BOARD_SCHEMA,
            "items": board_items,
            "itemCount": len(board_items),
            "businessRowsCopied": False,
        },
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def get_exploration_thread(
    connection: sqlite3.Connection,
    workspace_id: str,
    thread_key: str,
) -> dict[str, Any] | None:
    """Return one thread with live Anchor freshness and no stale fallback."""
    row = _thread_row(connection, workspace_id, thread_key)
    return _thread_payload(connection, workspace_id, row) if row else None


def get_exploration_anchor(
    connection: sqlite3.Connection,
    workspace_id: str,
    thread_key: str,
    anchor_key: str,
) -> dict[str, Any] | None:
    """Resolve one Anchor only inside its owning thread, including live freshness."""
    thread = get_exploration_thread(connection, workspace_id, thread_key)
    if not thread:
        return None
    return next(
        (anchor for anchor in thread.get("anchors") or [] if str(anchor.get("anchorKey") or "") == anchor_key),
        None,
    )


def exploration_threads_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        thread_key = str(getattr(args, "thread", "") or "")
        if thread_key:
            row = _thread_row(connection, workspace_id, thread_key)
            if not row:
                raise ValueError("Unknown Exploration Thread in the active workspace.")
            thread = get_exploration_thread(connection, workspace_id, thread_key)
            return {"ok": True, "schema": "aibi-exploration-thread-list/v1", "workspaceId": workspace_id, "explorationThread": thread}
        rows = connection.execute(
            "SELECT * FROM exploration_threads WHERE workspace_id = ? ORDER BY updated_at DESC, thread_key LIMIT ?",
            (workspace_id, max(1, min(int(getattr(args, "limit", 30) or 30), 100))),
        ).fetchall()
        threads = [_thread_payload(connection, workspace_id, row) for row in rows]
    return {"ok": True, "schema": "aibi-exploration-thread-list/v1", "workspaceId": workspace_id, "explorationThreads": threads, "count": len(threads)}
