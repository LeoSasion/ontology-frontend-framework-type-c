from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from typing import Any, Callable

from exploration_thread_service import get_exploration_anchor, get_exploration_thread


RUN_SCHEMA = "aibi-limited-research-run/v1"
REVISION_SCHEMA = "aibi-research-plan-revision/v1"
OBSERVATION_SCHEMA = "aibi-research-observation/v1"
TRACE_SCHEMA = "aibi-research-run-trace/v1"
MUTATION_PLAN_SCHEMA = "aibi-research-mutation-plan/v1"
CONCLUSION_SCHEMA = "aibi-research-run-conclusion/v1"

MAX_PLAN_STEPS = 12
MAX_DECLARED_CHECKS = 10
MAX_HYPOTHESES = 6
MAX_COUNTEREXAMPLES = 3
MAX_SENSITIVITIES = 3
MAX_OBSERVATIONS = 8
MAX_REVISIONS = 3
MAX_TEXT = 500


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _load(value: Any, fallback: Any) -> Any:
    try:
        result = json.loads(str(value or ""))
    except (TypeError, json.JSONDecodeError):
        return fallback
    return result if isinstance(result, type(fallback)) else fallback


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _clean(value: Any, *, required: bool = False, limit: int = MAX_TEXT) -> str:
    result = " ".join(str(value or "").split())[:limit]
    if required and not result:
        raise ValueError("A non-empty research value is required.")
    return result


def _clean_many(values: Any, *, limit: int) -> list[str]:
    items = [_clean(item, required=True) for item in (values or [])]
    items = list(dict.fromkeys(items))
    if len(items) > limit:
        raise ValueError(f"Research plan exceeds its fixed item budget ({limit}).")
    return items


def _ensure_plan_budget(hypotheses: list[str], counterexamples: list[str], sensitivities: list[str]) -> None:
    if len(hypotheses) > MAX_HYPOTHESES:
        raise ValueError(f"Research plan allows at most {MAX_HYPOTHESES} hypotheses.")
    if len(counterexamples) > MAX_COUNTEREXAMPLES:
        raise ValueError(f"Research plan allows at most {MAX_COUNTEREXAMPLES} counterexample checks.")
    if len(sensitivities) > MAX_SENSITIVITIES:
        raise ValueError(f"Research plan allows at most {MAX_SENSITIVITIES} sensitivity checks.")
    if len(hypotheses) + len(counterexamples) + len(sensitivities) > MAX_DECLARED_CHECKS:
        raise ValueError(f"Research plan allows at most {MAX_DECLARED_CHECKS} declared checks in total.")


def _plan_steps(hypotheses: list[str], counterexamples: list[str], sensitivities: list[str]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = [
        {"stepKey": "baseline", "kind": "baseline", "question": "Verify the immutable baseline Anchor.", "required": True}
    ]
    for prefix, kind, items in (
        ("hypothesis", "evidence", hypotheses),
        ("counterexample", "counterexample", counterexamples),
        ("sensitivity", "sensitivity", sensitivities),
    ):
        steps.extend(
            {"stepKey": f"{prefix}-{index}", "kind": kind, "question": item, "required": kind != "evidence"}
            for index, item in enumerate(items, 1)
        )
    steps.append({"stepKey": "conclusion", "kind": "conclusion", "question": "Reconcile evidence and state the bounded conclusion.", "required": True})
    if len(steps) > MAX_PLAN_STEPS:
        raise ValueError(f"Research plan allows at most {MAX_PLAN_STEPS} steps.")
    return steps


def _revision_material(
    *,
    research_key: str,
    revision_number: int,
    parent_revision_key: str | None,
    parent_fingerprint: str,
    goal: str,
    skill_ref: str,
    hypotheses: list[str],
    counterexamples: list[str],
    sensitivities: list[str],
    reason: str,
) -> dict[str, Any]:
    _ensure_plan_budget(hypotheses, counterexamples, sensitivities)
    stable = {
        "schema": REVISION_SCHEMA,
        "researchKey": research_key,
        "revisionNumber": revision_number,
        "parentRevisionKey": parent_revision_key,
        "parentFingerprint": parent_fingerprint,
        "goal": _clean(goal, required=True),
        "skillRef": _clean(skill_ref),
        "hypotheses": hypotheses,
        "counterexampleChecks": counterexamples,
        "sensitivityChecks": sensitivities,
        "steps": _plan_steps(hypotheses, counterexamples, sensitivities),
        "reason": _clean(reason, required=True),
        "capabilities": ["agent.context.route", "agent.semantic.plan", "agent.completion.verify", "agent.answer.compose"],
        "providerCanMutate": False,
        "businessRowsCopied": False,
    }
    fingerprint = _hash(stable)
    return {
        **stable,
        "revisionKey": f"research_revision_{_hash({'researchKey': research_key, 'revisionNumber': revision_number, 'fingerprint': fingerprint})[:20]}",
        "fingerprint": fingerprint,
    }


def _mutation_plan(kind: str, workspace_id: str, proposed: dict[str, Any]) -> dict[str, Any]:
    stable = {
        "schema": MUTATION_PLAN_SCHEMA,
        "kind": kind,
        "workspaceId": workspace_id,
        "proposed": proposed,
        "providerCanMutate": False,
        "businessRowsCopied": False,
    }
    return {**stable, "planFingerprint": _hash(stable)}


def _require_expected_plan(args: argparse.Namespace, plan: dict[str, Any]) -> None:
    expected = str(getattr(args, "expected_plan", "") or "").strip()
    if not expected:
        raise ValueError("Confirmation requires --expected-plan from the dry-run receipt.")
    if expected != str(plan.get("planFingerprint") or ""):
        raise ValueError("Research mutation plan changed after preview; run the dry-run again.")


def _require_expected_revision(args: argparse.Namespace, revision: dict[str, Any]) -> None:
    expected = str(getattr(args, "expected_revision", "") or "").strip()
    if not expected:
        raise ValueError("Research mutation requires --expected-revision from the current Research Run.")
    if expected != str(revision.get("fingerprint") or ""):
        raise ValueError("Research revision changed; reload the Research Run before continuing.")


def _research_row(connection: sqlite3.Connection, workspace_id: str, research_key: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM research_runs WHERE workspace_id = ? AND research_key = ?",
        (workspace_id, research_key),
    ).fetchone()


def _revision_row(connection: sqlite3.Connection, workspace_id: str, revision_key: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM research_plan_revisions WHERE workspace_id = ? AND revision_key = ?",
        (workspace_id, revision_key),
    ).fetchone()


def _revision_payload(row: sqlite3.Row) -> dict[str, Any]:
    plan = _load(row["plan_json"], {})
    return {
        **plan,
        "schema": REVISION_SCHEMA,
        "revisionKey": row["revision_key"],
        "workspaceId": row["workspace_id"],
        "researchKey": row["research_key"],
        "parentRevisionKey": row["parent_revision_key"],
        "revisionNumber": int(row["revision_number"]),
        "reason": row["reason"],
        "fingerprint": row["plan_fingerprint"],
        "createdAt": row["created_at"],
    }


def _current_revision(connection: sqlite3.Connection, workspace_id: str, run_row: sqlite3.Row) -> dict[str, Any]:
    row = _revision_row(connection, workspace_id, str(run_row["current_revision_key"] or ""))
    if not row:
        raise ValueError("Research Run current revision is missing.")
    return _revision_payload(row)


def _append_event(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    research_key: str,
    revision_key: str | None,
    event_type: str,
    status: str,
    summary: str,
    payload: dict[str, Any],
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO research_run_events(
          workspace_id, research_key, revision_key, event_type, status,
          public_summary, payload_json, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (workspace_id, research_key, revision_key, event_type, status, _clean(summary), _json(payload), created_at),
    )


def _insert_revision(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    research_key: str,
    revision: dict[str, Any],
    created_at: str,
) -> None:
    connection.execute(
        """
        INSERT INTO research_plan_revisions(
          revision_key, workspace_id, research_key, parent_revision_key,
          revision_number, reason, plan_json, plan_fingerprint, created_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            revision["revisionKey"], workspace_id, research_key, revision.get("parentRevisionKey"),
            revision["revisionNumber"], revision["reason"], _json(revision), revision["fingerprint"], created_at,
        ),
    )


def _observation_rows(connection: sqlite3.Connection, workspace_id: str, research_key: str) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT * FROM research_observations WHERE workspace_id = ? AND research_key = ? ORDER BY created_at, observation_key",
        (workspace_id, research_key),
    ).fetchall()


def _trace(connection: sqlite3.Connection, workspace_id: str, research_key: str) -> dict[str, Any]:
    rows = connection.execute(
        "SELECT * FROM research_run_events WHERE workspace_id = ? AND research_key = ? ORDER BY event_sequence",
        (workspace_id, research_key),
    ).fetchall()
    events = [
        {
            "sequence": int(row["event_sequence"]),
            "revisionKey": row["revision_key"],
            "eventType": row["event_type"],
            "status": row["status"],
            "summary": row["public_summary"],
            "payload": _load(row["payload_json"], {}),
            "createdAt": row["created_at"],
        }
        for row in rows
    ]
    return {"schema": TRACE_SCHEMA, "workspaceId": workspace_id, "researchKey": research_key, "events": events, "eventCount": len(events), "fingerprint": _hash(events)}


def _run_payload(connection: sqlite3.Connection, workspace_id: str, row: sqlite3.Row) -> dict[str, Any]:
    thread_key = str(row["thread_key"])
    baseline_anchor_key = str(row["baseline_anchor_key"])
    thread = get_exploration_thread(connection, workspace_id, thread_key)
    baseline = get_exploration_anchor(connection, workspace_id, thread_key, baseline_anchor_key) if thread else None
    blockers: list[str] = []
    missing: list[str] = []
    if not thread:
        missing.append("exploration-thread")
        blockers.append("research-exploration-thread-missing")
    if not baseline:
        missing.append("baseline-anchor")
        blockers.append("research-baseline-anchor-missing")
    elif not (baseline.get("freshness") or {}).get("usableForContinuation"):
        blockers.append("research-baseline-anchor-not-current")
        blockers.extend(str(item) for item in (baseline.get("freshness") or {}).get("blockers") or [])
    elif str(baseline.get("bindingFingerprint") or "") != str(row["baseline_binding_fingerprint"]):
        blockers.append("research-baseline-binding-drifted")

    revisions = [
        _revision_payload(item)
        for item in connection.execute(
            "SELECT * FROM research_plan_revisions WHERE workspace_id = ? AND research_key = ? ORDER BY revision_number",
            (workspace_id, row["research_key"]),
        ).fetchall()
    ]
    revision_by_key = {str(item["revisionKey"]): item for item in revisions}
    current_revision = revision_by_key.get(str(row["current_revision_key"]))
    if not current_revision:
        missing.append("current-revision")
        blockers.append("research-current-revision-missing")

    observations: list[dict[str, Any]] = []
    coverage = {"evidence": 0, "counterexample": 0, "sensitivity": 0}
    for item in _observation_rows(connection, workspace_id, str(row["research_key"])):
        anchor = get_exploration_anchor(connection, workspace_id, thread_key, str(item["anchor_key"])) if thread else None
        observation_blockers: list[str] = []
        if not anchor:
            observation_blockers.append("research-observation-anchor-missing")
        elif not (anchor.get("freshness") or {}).get("usableForContinuation"):
            observation_blockers.append("research-observation-anchor-not-current")
        elif str(anchor.get("bindingFingerprint") or "") != str(item["anchor_binding_fingerprint"]):
            observation_blockers.append("research-observation-binding-drifted")
        revision = revision_by_key.get(str(item["revision_key"]))
        if not revision or str(revision.get("fingerprint") or "") != str(item["revision_fingerprint"]):
            observation_blockers.append("research-observation-revision-drifted")
        kind = str(item["kind"])
        belongs_to_current_revision = str(item["revision_key"]) == str(row["current_revision_key"])
        if kind in coverage and belongs_to_current_revision and not observation_blockers:
            coverage[kind] += 1
        if observation_blockers and belongs_to_current_revision:
            blockers.extend(observation_blockers)
        observations.append({
            "schema": OBSERVATION_SCHEMA,
            "observationKey": item["observation_key"],
            "workspaceId": item["workspace_id"],
            "researchKey": item["research_key"],
            "revisionKey": item["revision_key"],
            "stepKey": item["step_key"],
            "kind": kind,
            "verdict": item["verdict"],
            "note": item["note"],
            "anchorKey": item["anchor_key"],
            "anchorBindingFingerprint": item["anchor_binding_fingerprint"],
            "revisionFingerprint": item["revision_fingerprint"],
            "freshness": {"status": "current" if not observation_blockers else "missing" if not anchor else "stale", "usableForPlanning": not observation_blockers, "blockers": observation_blockers},
            "anchorSummary": (anchor or {}).get("summary") or {},
            "businessRowsCopied": False,
            "createdAt": item["created_at"],
        })

    blockers = list(dict.fromkeys(blockers))
    freshness_status = "missing" if missing else "stale" if blockers else "current"
    stored_status = str(row["status"])
    effective_status = "blocked" if blockers else stored_status
    conclusion = _load(row["conclusion_json"], {})
    stable = {
        "researchKey": row["research_key"],
        "workspaceId": workspace_id,
        "threadKey": thread_key,
        "baselineAnchorKey": baseline_anchor_key,
        "baselineBindingFingerprint": row["baseline_binding_fingerprint"],
        "currentRevisionKey": row["current_revision_key"],
        "budget": _load(row["budget_json"], {}),
        "status": stored_status,
        "conclusion": conclusion,
    }
    return {
        "schema": RUN_SCHEMA,
        **stable,
        "goal": row["goal"],
        "storedStatus": stored_status,
        "status": effective_status,
        "freshness": {"status": freshness_status, "usableForPlanning": not blockers, "missingRefs": missing, "blockers": blockers, "staleFallbackUsed": False},
        "baseline": baseline,
        "revisions": revisions,
        "revisionCount": len(revisions),
        "currentRevision": current_revision,
        "observations": observations,
        "observationCount": len(observations),
        "coverage": coverage,
        "conclusion": conclusion or None,
        "trace": _trace(connection, workspace_id, str(row["research_key"])),
        "providerCanMutate": False,
        "businessRowsCopied": False,
        "fingerprint": _hash(stable),
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "completedAt": row["completed_at"],
    }


def research_runs_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        research_key = str(getattr(args, "research", "") or "")
        if research_key:
            row = _research_row(connection, workspace_id, research_key)
            if not row:
                raise ValueError("Unknown Research Run in the active workspace.")
            return {"ok": True, "schema": "aibi-limited-research-run-list/v1", "workspaceId": workspace_id, "researchRun": _run_payload(connection, workspace_id, row)}
        rows = connection.execute(
            "SELECT * FROM research_runs WHERE workspace_id = ? ORDER BY updated_at DESC, research_key LIMIT ?",
            (workspace_id, max(1, min(int(getattr(args, "limit", 30) or 30), 100))),
        ).fetchall()
        runs = [_run_payload(connection, workspace_id, row) for row in rows]
    return {"ok": True, "schema": "aibi-limited-research-run-list/v1", "workspaceId": workspace_id, "researchRuns": runs, "count": len(runs)}


def research_run_create_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        thread_key = str(args.thread)
        thread = get_exploration_thread(connection, workspace_id, thread_key)
        if not thread:
            raise ValueError("Unknown Exploration Thread in the active workspace.")
        anchor_key = str(getattr(args, "anchor", "") or thread.get("currentAnchorKey") or "")
        anchor = get_exploration_anchor(connection, workspace_id, thread_key, anchor_key)
        if not anchor or not (anchor.get("freshness") or {}).get("usableForContinuation"):
            raise ValueError("Research Run requires one current Exploration Anchor.")
        goal = _clean(args.goal, required=True)
        hypotheses = _clean_many(getattr(args, "hypothesis", None), limit=MAX_HYPOTHESES)
        counterexamples = _clean_many(getattr(args, "counterexample", None), limit=MAX_COUNTEREXAMPLES)
        sensitivities = _clean_many(getattr(args, "sensitivity", None), limit=MAX_SENSITIVITIES)
        _ensure_plan_budget(hypotheses, counterexamples, sensitivities)
        max_observations = int(getattr(args, "max_observations", MAX_OBSERVATIONS) or MAX_OBSERVATIONS)
        max_revisions = int(getattr(args, "max_revisions", MAX_REVISIONS) or MAX_REVISIONS)
        if not 1 <= max_observations <= MAX_OBSERVATIONS:
            raise ValueError(f"Research Run max observations must be between 1 and {MAX_OBSERVATIONS}.")
        if not 1 <= max_revisions <= MAX_REVISIONS:
            raise ValueError(f"Research Run max revisions must be between 1 and {MAX_REVISIONS}.")
        proposed = {
            "threadKey": thread_key,
            "baselineAnchorKey": anchor_key,
            "baselineBindingFingerprint": anchor.get("bindingFingerprint"),
            "goal": goal,
            "skillRef": _clean(getattr(args, "skill", "")),
            "hypotheses": hypotheses,
            "counterexampleChecks": counterexamples,
            "sensitivityChecks": sensitivities,
            "budget": {"maxPlanSteps": MAX_PLAN_STEPS, "maxObservations": max_observations, "maxRevisions": max_revisions},
        }
        plan = _mutation_plan("create", workspace_id, proposed)
        if not bool(getattr(args, "yes", False)):
            connection.rollback()
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "workspaceId": workspace_id, "researchPlan": plan}
        _require_expected_plan(args, plan)
        now = now_iso()
        research_key = f"research_run_{_hash({'workspaceId': workspace_id, 'threadKey': thread_key, 'anchorKey': anchor_key, 'goal': goal, 'createdAt': now})[:20]}"
        revision = _revision_material(
            research_key=research_key, revision_number=1, parent_revision_key=None, parent_fingerprint="",
            goal=goal, skill_ref=proposed["skillRef"], hypotheses=hypotheses,
            counterexamples=counterexamples, sensitivities=sensitivities, reason="initial-plan",
        )
        connection.execute(
            """
            INSERT INTO research_runs(
              research_key, workspace_id, thread_key, baseline_anchor_key,
              baseline_binding_fingerprint, goal, status, current_revision_key,
              budget_json, conclusion_json, created_at, updated_at, completed_at
            ) VALUES(?, ?, ?, ?, ?, ?, 'active', ?, ?, '{}', ?, ?, NULL)
            """,
            (research_key, workspace_id, thread_key, anchor_key, anchor.get("bindingFingerprint"), goal, revision["revisionKey"], _json(proposed["budget"]), now, now),
        )
        _insert_revision(connection, workspace_id=workspace_id, research_key=research_key, revision=revision, created_at=now)
        _append_event(connection, workspace_id=workspace_id, research_key=research_key, revision_key=revision["revisionKey"], event_type="research-created", status="active", summary="Finite Research Run created from a current Exploration Anchor.", payload={"threadKey": thread_key, "baselineAnchorKey": anchor_key, "revisionFingerprint": revision["fingerprint"]}, created_at=now)
        connection.commit()
        row = _research_row(connection, workspace_id, research_key)
        assert row is not None
        result = _run_payload(connection, workspace_id, row)
    return {"ok": True, "confirmed": True, "changed": True, "workspaceId": workspace_id, "researchPlan": plan, "researchRun": result}


def research_run_revise_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        row = _research_row(connection, workspace_id, str(args.research))
        if not row:
            raise ValueError("Unknown Research Run in the active workspace.")
        run = _run_payload(connection, workspace_id, row)
        if run.get("storedStatus") != "active" or not (run.get("freshness") or {}).get("usableForPlanning"):
            raise ValueError("Only a current active Research Run may be revised.")
        current = run["currentRevision"]
        _require_expected_revision(args, current)
        budget = run["budget"]
        if int(run["revisionCount"]) >= int(budget.get("maxRevisions") or 0):
            raise ValueError("Research Run revision budget is exhausted.")
        hypotheses = [] if args.clear_hypotheses else _clean_many(args.hypothesis, limit=MAX_HYPOTHESES) if args.hypothesis is not None else list(current.get("hypotheses") or [])
        counterexamples = [] if args.clear_counterexamples else _clean_many(args.counterexample, limit=MAX_COUNTEREXAMPLES) if args.counterexample is not None else list(current.get("counterexampleChecks") or [])
        sensitivities = [] if args.clear_sensitivities else _clean_many(args.sensitivity, limit=MAX_SENSITIVITIES) if args.sensitivity is not None else list(current.get("sensitivityChecks") or [])
        revision = _revision_material(
            research_key=str(row["research_key"]), revision_number=int(current["revisionNumber"]) + 1,
            parent_revision_key=str(current["revisionKey"]), parent_fingerprint=str(current["fingerprint"]),
            goal=_clean(args.goal) or str(current.get("goal") or row["goal"]),
            skill_ref=_clean(args.skill) if args.skill is not None else str(current.get("skillRef") or ""),
            hypotheses=hypotheses, counterexamples=counterexamples, sensitivities=sensitivities,
            reason=_clean(args.reason, required=True),
        )
        proposed = {"researchKey": row["research_key"], "parentRevisionKey": current["revisionKey"], "parentFingerprint": current["fingerprint"], "revision": revision}
        plan = _mutation_plan("revise", workspace_id, proposed)
        if not bool(getattr(args, "yes", False)):
            connection.rollback()
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "workspaceId": workspace_id, "researchPlan": plan}
        _require_expected_plan(args, plan)
        now = now_iso()
        _insert_revision(connection, workspace_id=workspace_id, research_key=str(row["research_key"]), revision=revision, created_at=now)
        connection.execute(
            "UPDATE research_runs SET goal = ?, current_revision_key = ?, updated_at = ? WHERE workspace_id = ? AND research_key = ?",
            (revision["goal"], revision["revisionKey"], now, workspace_id, row["research_key"]),
        )
        _append_event(connection, workspace_id=workspace_id, research_key=str(row["research_key"]), revision_key=revision["revisionKey"], event_type="plan-revised", status="active", summary="Research plan revision appended without replacing history.", payload={"parentRevisionKey": current["revisionKey"], "parentFingerprint": current["fingerprint"], "revisionFingerprint": revision["fingerprint"], "reason": revision["reason"]}, created_at=now)
        connection.commit()
        updated = _research_row(connection, workspace_id, str(row["research_key"]))
        assert updated is not None
        result = _run_payload(connection, workspace_id, updated)
    return {"ok": True, "confirmed": True, "changed": True, "workspaceId": workspace_id, "researchPlan": plan, "researchRun": result}


def research_run_observe_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        row = _research_row(connection, workspace_id, str(args.research))
        if not row:
            raise ValueError("Unknown Research Run in the active workspace.")
        run = _run_payload(connection, workspace_id, row)
        if run.get("storedStatus") != "active" or not (run.get("freshness") or {}).get("usableForPlanning"):
            raise ValueError("Only a current active Research Run may accept observations.")
        current = run["currentRevision"]
        _require_expected_revision(args, current)
        if int(run["observationCount"]) >= int(run["budget"].get("maxObservations") or 0):
            raise ValueError("Research Run observation budget is exhausted.")
        anchor = get_exploration_anchor(connection, workspace_id, str(row["thread_key"]), str(args.anchor))
        if not anchor or not (anchor.get("freshness") or {}).get("usableForContinuation"):
            raise ValueError("Research Observation requires a current Anchor in the owning Exploration Thread.")
        kind = str(args.kind)
        step_key = _clean(args.step, required=True, limit=120)
        plan_step = next((step for step in current.get("steps") or [] if str(step.get("stepKey") or "") == step_key), None)
        if not plan_step:
            raise ValueError("Research Observation step is not present in the current revision.")
        if kind != str(plan_step.get("kind") or "") and not (kind == "evidence" and str(plan_step.get("kind") or "") == "baseline"):
            raise ValueError("Research Observation kind must match the current revision step.")
        stable = {
            "researchKey": row["research_key"], "revisionKey": current["revisionKey"],
            "revisionFingerprint": current["fingerprint"], "stepKey": step_key, "kind": kind,
            "verdict": str(args.verdict), "note": _clean(args.note, required=True),
            "anchorKey": anchor["anchorKey"], "anchorBindingFingerprint": anchor["bindingFingerprint"],
            "businessRowsCopied": False,
        }
        observation_key = f"research_observation_{_hash(stable)[:20]}"
        existing = connection.execute(
            "SELECT 1 FROM research_observations WHERE workspace_id = ? AND observation_key = ?",
            (workspace_id, observation_key),
        ).fetchone()
        proposed = {**stable, "observationKey": observation_key, "alreadyExists": bool(existing)}
        plan = _mutation_plan("observe", workspace_id, proposed)
        if not bool(getattr(args, "yes", False)):
            connection.rollback()
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "workspaceId": workspace_id, "researchPlan": plan}
        _require_expected_plan(args, plan)
        if existing:
            connection.rollback()
            return {"ok": True, "confirmed": True, "changed": False, "workspaceId": workspace_id, "researchPlan": plan, "researchRun": run}
        now = now_iso()
        connection.execute(
            """
            INSERT INTO research_observations(
              observation_key, workspace_id, research_key, revision_key, step_key,
              kind, verdict, note, anchor_key, anchor_binding_fingerprint,
              revision_fingerprint, created_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (observation_key, workspace_id, row["research_key"], current["revisionKey"], step_key, kind, args.verdict, stable["note"], anchor["anchorKey"], anchor["bindingFingerprint"], current["fingerprint"], now),
        )
        connection.execute(
            "UPDATE research_runs SET updated_at = ? WHERE workspace_id = ? AND research_key = ?",
            (now, workspace_id, row["research_key"]),
        )
        _append_event(connection, workspace_id=workspace_id, research_key=str(row["research_key"]), revision_key=str(current["revisionKey"]), event_type="observation-adopted", status="active", summary=f"Current {kind} observation adopted from the owning Exploration Thread.", payload={"observationKey": observation_key, "anchorKey": anchor["anchorKey"], "stepKey": step_key, "kind": kind, "verdict": args.verdict}, created_at=now)
        connection.commit()
        updated = _research_row(connection, workspace_id, str(row["research_key"]))
        assert updated is not None
        result = _run_payload(connection, workspace_id, updated)
    return {"ok": True, "confirmed": True, "changed": True, "workspaceId": workspace_id, "researchPlan": plan, "researchRun": result}


def _conclusion(run: dict[str, Any]) -> dict[str, Any]:
    current_revision_key = str(run.get("currentRevisionKey") or "")
    current_observations = [
        item
        for item in run.get("observations") or []
        if str(item.get("revisionKey") or "") == current_revision_key
        and (item.get("freshness") or {}).get("usableForPlanning")
    ]
    counterexample_covered = any(item.get("kind") == "counterexample" for item in current_observations)
    sensitivity_covered = any(item.get("kind") == "sensitivity" for item in current_observations)
    verdicts = {str(item.get("verdict") or "") for item in current_observations}
    if not (counterexample_covered and sensitivity_covered):
        outcome = "inconclusive"
        blockers = [name for name, covered in (("counterexample-observation-required", counterexample_covered), ("sensitivity-observation-required", sensitivity_covered)) if not covered]
    elif "challenges" in verdicts and "supports" in verdicts:
        outcome = "mixed"
        blockers = []
    elif "challenges" in verdicts:
        outcome = "challenged"
        blockers = []
    elif "supports" in verdicts:
        outcome = "supported"
        blockers = []
    else:
        outcome = "inconclusive"
        blockers = ["decisive-observation-required"]
    stable = {
        "schema": CONCLUSION_SCHEMA,
        "outcome": outcome,
        "counterexampleCovered": counterexample_covered,
        "sensitivityCovered": sensitivity_covered,
        "observationKeys": [item["observationKey"] for item in current_observations],
        "blockers": blockers,
        "causalClaimAuthorized": False,
        "businessRowsCopied": False,
    }
    return {**stable, "fingerprint": _hash(stable)}


def research_run_finalize_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        row = _research_row(connection, workspace_id, str(args.research))
        if not row:
            raise ValueError("Unknown Research Run in the active workspace.")
        run = _run_payload(connection, workspace_id, row)
        stored_status = run.get("storedStatus")
        if stored_status not in {"active", "completed"}:
            raise ValueError("Only a current active Research Run may be finalized.")
        if stored_status == "active" and not (run.get("freshness") or {}).get("usableForPlanning"):
            raise ValueError("Only a current active Research Run may be finalized.")
        current = run.get("currentRevision")
        if not current:
            raise ValueError("Research Run current revision is missing.")
        _require_expected_revision(args, current)
        conclusion = run.get("conclusion") if stored_status == "completed" else _conclusion(run)
        if not conclusion:
            raise ValueError("Completed Research Run conclusion is missing.")
        proposed = {"researchKey": row["research_key"], "revisionKey": current["revisionKey"], "revisionFingerprint": current["fingerprint"], "conclusion": conclusion}
        plan = _mutation_plan("finalize", workspace_id, proposed)
        if not bool(getattr(args, "yes", False)):
            connection.rollback()
            return {"ok": True, "dryRun": True, "requiresConfirmation": True, "workspaceId": workspace_id, "researchPlan": plan}
        _require_expected_plan(args, plan)
        if stored_status == "completed":
            connection.rollback()
            return {"ok": True, "confirmed": True, "changed": False, "workspaceId": workspace_id, "researchPlan": plan, "researchRun": run}
        now = now_iso()
        connection.execute(
            "UPDATE research_runs SET status = 'completed', conclusion_json = ?, updated_at = ?, completed_at = ? WHERE workspace_id = ? AND research_key = ?",
            (_json(conclusion), now, now, workspace_id, row["research_key"]),
        )
        _append_event(connection, workspace_id=workspace_id, research_key=str(row["research_key"]), revision_key=str(current["revisionKey"]), event_type="research-finalized", status="completed", summary=f"Finite Research Run completed with outcome {conclusion['outcome']}.", payload={"outcome": conclusion["outcome"], "conclusionFingerprint": conclusion["fingerprint"], "blockers": conclusion["blockers"]}, created_at=now)
        connection.commit()
        updated = _research_row(connection, workspace_id, str(row["research_key"]))
        assert updated is not None
        result = _run_payload(connection, workspace_id, updated)
    return {"ok": True, "confirmed": True, "changed": True, "workspaceId": workspace_id, "researchPlan": plan, "researchRun": result}
