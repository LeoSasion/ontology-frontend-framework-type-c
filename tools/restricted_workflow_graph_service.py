from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from typing import Any, Callable
import argparse
import sqlite3


GRAPH_SCHEMA = "aibi-agent-workflow-graph/v1"
EXECUTION_SCHEMA = "aibi-agent-workflow-execution/v1"
REVIEW_SCHEMA = "aibi-agent-expert-review/v1"
JOIN_SCHEMA = "aibi-agent-workflow-join/v1"

OPERATORS: dict[str, dict[str, Any]] = {
    "context": {"mutationMode": "read-only", "purpose": "bind current workspace context"},
    "resolve": {"mutationMode": "read-only", "purpose": "resolve deterministic intent or semantics"},
    "clarify": {"mutationMode": "read-only", "purpose": "surface one structured clarification"},
    "query": {"mutationMode": "runtime-receipt", "purpose": "reference an orchestrator-owned deterministic query"},
    "validate": {"mutationMode": "read-only", "purpose": "validate plans, evidence, or completion"},
    "unit": {"mutationMode": "read-only", "purpose": "inspect a receipt-bound Analysis Unit"},
    "chart": {"mutationMode": "read-only", "purpose": "inspect a deterministic Chart Adapter"},
    "explain": {"mutationMode": "read-only", "purpose": "compose an evidence-bound explanation"},
    "export": {"mutationMode": "artifact-export", "purpose": "reference an explicitly requested deterministic export"},
    "branch": {"mutationMode": "read-only", "purpose": "select a fixed graph branch without arbitrary code"},
    "join": {"mutationMode": "read-only", "purpose": "join parent evidence after fingerprint validation"},
}

ROLES: dict[str, dict[str, Any]] = {
    "Orchestrator": {"canSubmitCapability": True, "toolPermissions": "registered-capabilities-only", "outputSchema": "aibi-agent-orchestrator-view/v1"},
    "Planner": {"canSubmitCapability": False, "toolPermissions": "none", "outputSchema": REVIEW_SCHEMA},
    "Semantic Reviewer": {"canSubmitCapability": False, "toolPermissions": "none", "outputSchema": REVIEW_SCHEMA},
    "Evidence Reviewer": {"canSubmitCapability": False, "toolPermissions": "none", "outputSchema": REVIEW_SCHEMA},
    "Narrator": {"canSubmitCapability": False, "toolPermissions": "none", "outputSchema": REVIEW_SCHEMA},
}


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _fingerprints(answer: dict[str, Any]) -> tuple[str, str]:
    receipt = _record(answer.get("queryPlanReceipt"))
    source = _record(receipt.get("source"))
    data = str(source.get("dataFingerprint") or answer.get("semanticContext", {}).get("fingerprint") or "missing")
    packs = str(receipt.get("domainPackFingerprint") or answer.get("semanticContext", {}).get("fingerprint") or "missing")
    return data, packs


def operator_registry() -> dict[str, Any]:
    return {
        "ok": True,
        "schema": "aibi-agent-workflow-operator-registry/v1",
        "operators": [{"operator": name, **contract, "arbitraryImplementation": False} for name, contract in OPERATORS.items()],
        "roles": [{"role": name, **contract} for name, contract in ROLES.items()],
        "unknownOperator": "blocked",
        "cycles": "blocked",
        "reviewerToolAccess": "forbidden",
    }


def _node(
    key: str,
    *,
    operator: str,
    role: str,
    depends_on: list[str],
    input_refs: list[str],
    capability_id: str | None = None,
    mutation_mode: str | None = None,
) -> dict[str, Any]:
    if operator not in OPERATORS:
        raise ValueError(f"Unknown restricted workflow operator: {operator}")
    if role not in ROLES:
        raise ValueError(f"Unknown restricted workflow role: {role}")
    if capability_id and not ROLES[role]["canSubmitCapability"]:
        raise ValueError(f"Role {role} cannot submit Capability requests")
    return {
        "nodeKey": key,
        "operator": operator,
        "role": role,
        "dependsOn": list(depends_on),
        "inputRefs": list(input_refs),
        "capabilityId": capability_id,
        "mutationMode": mutation_mode or OPERATORS[operator]["mutationMode"],
        "canSubmitCapability": bool(ROLES[role]["canSubmitCapability"]),
        "toolPermissions": ROLES[role]["toolPermissions"],
        "outputSchema": ROLES[role]["outputSchema"],
    }


def _topological_layers(nodes: list[dict[str, Any]]) -> tuple[list[list[str]], list[str]]:
    by_key = {str(node.get("nodeKey")): node for node in nodes}
    if len(by_key) != len(nodes) or "" in by_key:
        return [], ["duplicate-or-empty-node-key"]
    unknown = sorted({dep for node in nodes for dep in node.get("dependsOn") or [] if dep not in by_key})
    if unknown:
        return [], [f"unknown-dependency:{item}" for item in unknown]
    remaining = set(by_key)
    completed: set[str] = set()
    layers: list[list[str]] = []
    while remaining:
        ready = sorted(key for key in remaining if set(by_key[key].get("dependsOn") or []).issubset(completed))
        if not ready:
            return [], ["workflow-cycle"]
        layers.append(ready)
        completed.update(ready)
        remaining.difference_update(ready)
    return layers, []


def validate_restricted_workflow_graph(graph: dict[str, Any]) -> dict[str, Any]:
    nodes = list(graph.get("nodes") or [])
    layers, blockers = _topological_layers(nodes)
    by_key = {str(node.get("nodeKey")): node for node in nodes}
    checks = {
        "schema": graph.get("schema") == GRAPH_SCHEMA,
        "workspaceBound": bool(graph.get("workspaceId")),
        "planVersion": int(graph.get("planVersion") or 0) > 0,
        "operatorsAllowlisted": all(node.get("operator") in OPERATORS for node in nodes),
        "rolesAllowlisted": all(node.get("role") in ROLES for node in nodes),
        "capabilityAuthority": all(not node.get("capabilityId") or node.get("role") == "Orchestrator" for node in nodes),
        "reviewerToolsForbidden": all(node.get("toolPermissions") == "none" for node in nodes if node.get("role") != "Orchestrator"),
        "acyclic": not blockers,
        "fingerprintsBound": len(str(graph.get("dataFingerprint") or "")) > 0 and len(str(graph.get("domainPackFingerprint") or "")) > 0,
        "declarationOnly": not any(
            str(key).casefold() in {"code", "script", "command", "tool", "tools", "sql", "handler", "endpoint", "url"}
            for node in nodes if isinstance(node, dict) for key in node
        ),
    }
    # Any stateful node must be ordered after the previous stateful node.
    stateful = [node for layer in layers for key in layer for node in [by_key[key]] if node.get("mutationMode") != "read-only"]
    serial = True
    for previous, current in zip(stateful, stateful[1:]):
        ancestors = set(current.get("dependsOn") or [])
        frontier = list(ancestors)
        while frontier:
            parent = frontier.pop()
            for item in by_key.get(parent, {}).get("dependsOn") or []:
                if item not in ancestors:
                    ancestors.add(item)
                    frontier.append(item)
        if previous.get("nodeKey") not in ancestors:
            serial = False
            break
    checks["statefulNodesSerial"] = serial
    blockers.extend(key for key, value in checks.items() if not value)
    parallel_groups = [
        layer for layer in layers
        if len(layer) > 1 and all(by_key[key].get("mutationMode") == "read-only" for key in layer)
    ]
    return {
        "schema": "aibi-agent-workflow-graph-validation/v1",
        "status": "passed" if not blockers else "blocked",
        "checks": checks,
        "blockers": list(dict.fromkeys(blockers)),
        "topologicalLayers": layers,
        "parallelReadOnlyGroups": parallel_groups,
        "deterministicEventOrder": [key for layer in layers for key in layer],
    }


def build_restricted_agent_workflow_graph(*, plan: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any]:
    workspace_id = str(plan.get("workspaceId") or answer.get("workspaceId") or "")
    plan_version = int(plan.get("planVersion") or 1)
    data_fingerprint, pack_fingerprint = _fingerprints(answer)
    steps = list(plan.get("steps") or [])
    semantic_capability = next((str(step.get("capabilityId")) for step in steps if step.get("kind") == "semantic"), "agent.semantic.plan")
    query_step = next((step for step in steps if step.get("kind") == "query"), None)
    draft_step = next((step for step in steps if step.get("kind") == "draft"), None)
    nodes = [
        _node("node-010-resolve", operator="resolve", role="Orchestrator", depends_on=[], input_refs=["turn.prompt"], capability_id="agent.intent.resolve"),
        _node("node-020-planner", operator="branch", role="Planner", depends_on=["node-010-resolve"], input_refs=["intentFrame"]),
        _node("node-025-business", operator="context", role="Orchestrator", depends_on=["node-010-resolve"], input_refs=["intentFrame", "businessUnderstanding"], capability_id="agent.context.route"),
        _node("node-030-context", operator="context", role="Orchestrator", depends_on=["node-025-business"], input_refs=["intentFrame", "businessUnderstanding"], capability_id="agent.context.route"),
        _node("node-040-semantic", operator="resolve", role="Orchestrator", depends_on=["node-020-planner", "node-030-context"], input_refs=["semanticContext"], capability_id=semantic_capability),
    ]
    last_orchestrator = "node-040-semantic"
    clarification = _record(answer.get("clarification"))
    if clarification.get("required") is True:
        nodes.append(_node("node-045-clarify", operator="clarify", role="Orchestrator", depends_on=[last_orchestrator], input_refs=["clarification"] ))
        last_orchestrator = "node-045-clarify"
    if query_step:
        nodes.append(_node("node-050-query", operator="query", role="Orchestrator", depends_on=[last_orchestrator], input_refs=["semanticPlan"], capability_id=str(query_step.get("capabilityId")), mutation_mode=str(query_step.get("mutationMode") or "runtime-receipt")))
        last_orchestrator = "node-050-query"
    if answer.get("analysisUnit"):
        nodes.append(_node("node-060-unit", operator="unit", role="Orchestrator", depends_on=[last_orchestrator], input_refs=["analysisUnit"] ))
        nodes.append(_node("node-061-chart", operator="chart", role="Orchestrator", depends_on=["node-060-unit"], input_refs=["chartAdapter"] ))
        last_orchestrator = "node-061-chart"
    if draft_step:
        nodes.append(_node("node-070-draft", operator="branch", role="Orchestrator", depends_on=[last_orchestrator], input_refs=["actionDraft"], capability_id=str(draft_step.get("capabilityId")), mutation_mode=str(draft_step.get("mutationMode") or "action-draft")))
        last_orchestrator = "node-070-draft"
    nodes.extend([
        _node("node-080-semantic-review", operator="validate", role="Semantic Reviewer", depends_on=[last_orchestrator], input_refs=["intentFrame", "semanticPlan"]),
        _node("node-081-evidence-review", operator="validate", role="Evidence Reviewer", depends_on=[last_orchestrator], input_refs=["queryPlanReceipt", "answerCard.evidenceRefs"]),
        _node("node-090-join", operator="join", role="Orchestrator", depends_on=["node-080-semantic-review", "node-081-evidence-review"], input_refs=["expertReviews"]),
        _node("node-100-completion", operator="validate", role="Orchestrator", depends_on=["node-090-join"], input_refs=["evidencePlan", "expertReviews"], capability_id="agent.completion.verify"),
        _node("node-110-narrator", operator="explain", role="Narrator", depends_on=["node-100-completion"], input_refs=["answerCard", "expertReviews"]),
    ])
    material = {
        "workspaceId": workspace_id,
        "planVersion": plan_version,
        "dataFingerprint": data_fingerprint,
        "domainPackFingerprint": pack_fingerprint,
        "nodes": nodes,
    }
    graph = {
        "schema": GRAPH_SCHEMA,
        **material,
        "operatorRegistry": list(OPERATORS),
        "roleRegistry": list(ROLES),
        "orchestratorOnlyCapabilitySubmission": True,
        "fingerprint": _hash(material),
    }
    graph["validation"] = validate_restricted_workflow_graph(graph)
    return graph


def _review(role: str, *, decision: str, blockers: list[str], revisions: list[str], evidence_refs: list[str], metadata: dict[str, Any], degraded: bool = False) -> dict[str, Any]:
    return {
        "schema": REVIEW_SCHEMA,
        "role": role,
        "decision": decision if decision in {"pass", "block", "revise"} else "revise",
        "blockers": blockers,
        "revisions": revisions,
        "evidenceRefs": evidence_refs,
        "canSubmitCapability": False,
        "toolCalls": [],
        "degraded": degraded,
        **metadata,
    }


def validate_workflow_join(*, parents: list[dict[str, Any]], workspace_id: str, plan_version: int, data_fingerprint: str, pack_fingerprint: str, required_evidence: list[str]) -> dict[str, Any]:
    evidence = sorted({str(ref) for parent in parents for ref in parent.get("evidenceRefs") or [] if ref})
    checks = {
        "parentsPresent": len(parents) > 0,
        "workspaceMatch": all(parent.get("workspaceId") == workspace_id for parent in parents),
        "planVersionMatch": all(int(parent.get("planVersion") or 0) == plan_version for parent in parents),
        "dataFingerprintMatch": all(parent.get("dataFingerprint") == data_fingerprint for parent in parents),
        "packFingerprintMatch": all(parent.get("domainPackFingerprint") == pack_fingerprint for parent in parents),
        "evidenceComplete": all(item in evidence for item in required_evidence),
    }
    blockers = [key for key, value in checks.items() if not value]
    return {
        "schema": JOIN_SCHEMA,
        "status": "passed" if not blockers else "blocked",
        "checks": checks,
        "blockers": blockers,
        "evidenceRefs": evidence,
        "fingerprint": _hash({"parents": parents, "checks": checks}),
    }


def execute_restricted_agent_workflow(
    *,
    graph: dict[str, Any],
    plan: dict[str, Any],
    answer: dict[str, Any],
    reviewer_runner: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    validation = validate_restricted_workflow_graph(graph)
    if validation["status"] != "passed":
        return {"schema": EXECUTION_SCHEMA, "status": "blocked", "mode": "single-orchestrator", "blockers": validation["blockers"], "reviews": [], "events": [], "providerCanWrite": False}
    workspace_id = str(graph["workspaceId"])
    plan_version = int(graph["planVersion"])
    data_fingerprint = str(graph["dataFingerprint"])
    pack_fingerprint = str(graph["domainPackFingerprint"])
    receipt = _record(answer.get("queryPlanReceipt"))
    receipt_key = str(receipt.get("receiptKey") or "")
    common = {"workspaceId": workspace_id, "planVersion": plan_version, "dataFingerprint": data_fingerprint, "domainPackFingerprint": pack_fingerprint}

    def built_in(role: str, _: dict[str, Any]) -> dict[str, Any]:
        semantic_status = str(answer.get("semanticPlan", {}).get("status") or "not-applicable")
        unresolved = list(answer.get("intentFrame", {}).get("unresolved") or [])
        if role == "Semantic Reviewer":
            passed = semantic_status in {"ready", "not-applicable"} and not unresolved
            return _review(role, decision="pass" if passed else "block", blockers=[] if passed else [f"semantic:{semantic_status}"], revisions=[] if passed else ["resolve-semantic-gap"], evidence_refs=[], metadata=common)
        passed = receipt.get("status") == "executed" or bool(receipt.get("unresolved"))
        return _review(role, decision="pass" if passed else "revise", blockers=[] if passed else ["missing-query-receipt-state"], revisions=[] if passed else ["rebuild-evidence-plan"], evidence_refs=[receipt_key] if receipt_key else [], metadata=common)

    runner = reviewer_runner or built_in
    roles = ["Semantic Reviewer", "Evidence Reviewer"]
    planner_view = _review(
        "Planner",
        decision="pass" if plan.get("status") in {"ready", "blocked"} else "revise",
        blockers=[] if plan.get("status") in {"ready", "blocked"} else ["plan-state-invalid"],
        revisions=[] if plan.get("status") in {"ready", "blocked"} else ["rebuild-fixed-plan"],
        evidence_refs=[],
        metadata=common,
    )
    reviews: list[dict[str, Any]] = []
    degraded = False
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="aibi-readonly-review") as pool:
        futures = {pool.submit(runner, role, {"plan": plan, "answer": answer}): role for role in roles}
        for future in as_completed(futures):
            role = futures[future]
            try:
                review = future.result()
                if not isinstance(review, dict) or review.get("schema") != REVIEW_SCHEMA or review.get("role") != role or review.get("decision") not in {"pass", "block", "revise"} or review.get("toolCalls") not in ([], None):
                    raise ValueError("invalid-review-contract")
                review = {**review, **common, "canSubmitCapability": False, "toolCalls": [], "degraded": bool(review.get("degraded", False))}
            except Exception as error:
                degraded = True
                review = _review(role, decision="revise", blockers=[type(error).__name__], revisions=["orchestrator-performs-fixed-review"], evidence_refs=[receipt_key] if receipt_key else [], metadata=common, degraded=True)
            reviews.append(review)
    reviews.sort(key=lambda item: roles.index(str(item["role"])))
    required_evidence = [receipt_key] if receipt_key and receipt.get("status") == "executed" else []
    joined = validate_workflow_join(parents=reviews, workspace_id=workspace_id, plan_version=plan_version, data_fingerprint=data_fingerprint, pack_fingerprint=pack_fingerprint, required_evidence=required_evidence)
    narrator_view = _review(
        "Narrator",
        decision="pass" if joined["status"] == "passed" else "block",
        blockers=list(joined["blockers"]),
        revisions=[] if joined["status"] == "passed" else ["resolve-join-blockers"],
        evidence_refs=list(joined["evidenceRefs"]),
        metadata=common,
    )
    role_views = [planner_view, *reviews, narrator_view]
    events = [{"eventType": "expert-view-completed", "nodeKey": "node-020-planner", "role": "Planner", "status": planner_view["decision"]}] + [
        {"eventType": "expert-review-completed", "nodeKey": "node-080-semantic-review" if review["role"] == "Semantic Reviewer" else "node-081-evidence-review", "role": review["role"], "status": review["decision"]}
        for review in reviews
    ] + [
        {"eventType": "workflow-join-completed", "nodeKey": "node-090-join", "role": "Orchestrator", "status": joined["status"]},
        {"eventType": "expert-view-completed", "nodeKey": "node-110-narrator", "role": "Narrator", "status": narrator_view["decision"]},
    ]
    material = {"graph": graph.get("fingerprint"), "reviews": reviews, "join": joined, "mode": "single-orchestrator-fallback" if degraded else "orchestrated-readonly-experts"}
    return {
        "schema": EXECUTION_SCHEMA,
        "status": "completed" if joined["status"] == "passed" else "blocked",
        "mode": material["mode"],
        "parallelReadOnlyGroups": validation["parallelReadOnlyGroups"],
        "deterministicEventOrder": validation["deterministicEventOrder"],
        "reviews": reviews,
        "roleViews": role_views,
        "join": joined,
        "events": events,
        "providerCanWrite": False,
        "reviewerCapabilitySubmissionCount": 0,
        "reviewerToolCallCount": 0,
        "fingerprint": _hash(material),
    }


def bind_restricted_workflow(*, plan: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any]:
    graph = build_restricted_agent_workflow_graph(plan=plan, answer=answer)
    execution = execute_restricted_agent_workflow(graph=graph, plan=plan, answer=answer)
    bound = json.loads(json.dumps(plan))
    bound["workflowGraph"] = graph
    bound["workflowExecution"] = execution
    bound["fingerprint"] = _hash({"evidencePlan": plan.get("fingerprint"), "workflowGraph": graph.get("fingerprint"), "workflowExecution": execution.get("fingerprint")})
    return bound


def restricted_workflow_operators_command(_: argparse.Namespace) -> dict[str, Any]:
    return operator_registry()


def restricted_workflow_validate_command(args: argparse.Namespace) -> dict[str, Any]:
    try:
        graph = json.loads(str(args.graph_json or "{}"))
    except json.JSONDecodeError as error:
        raise ValueError("graph-json must be one JSON object") from error
    if not isinstance(graph, dict):
        raise ValueError("graph-json must be one JSON object")
    expected_workspace = str(args.workspace or "")
    validation = validate_restricted_workflow_graph(graph)
    if expected_workspace and graph.get("workspaceId") != expected_workspace:
        validation["checks"]["requestedWorkspaceMatch"] = False
        validation["blockers"].append("requestedWorkspaceMatch")
        validation["status"] = "blocked"
    return {"ok": validation["status"] == "passed", "schema": "aibi-agent-workflow-graph-validation-result/v1", "validation": validation}


def agent_workflow_graph_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = str(args.workspace or active_workspace_id(connection))
        row = connection.execute(
            "SELECT turn_key, plan_json FROM agent_turns WHERE workspace_id = ? AND turn_key = ?",
            (workspace_id, str(args.turn or "")),
        ).fetchone()
        if not row:
            raise ValueError(f"Unknown Agent Turn in workspace {workspace_id}: {args.turn}")
        plan = json.loads(row["plan_json"] or "{}")
        graph = _record(plan.get("workflowGraph"))
        execution = _record(plan.get("workflowExecution"))
        if not graph:
            raise ValueError("Agent Turn does not contain a restricted workflow graph")
        return {
            "ok": True,
            "schema": "aibi-agent-workflow-graph-inspection/v1",
            "workspaceId": workspace_id,
            "turnKey": row["turn_key"],
            "workflowGraph": graph,
            "workflowExecution": execution,
        }
