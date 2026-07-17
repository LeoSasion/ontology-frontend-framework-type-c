from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from restricted_workflow_graph_service import (  # noqa: E402
    GRAPH_SCHEMA,
    OPERATORS,
    REVIEW_SCHEMA,
    ROLES,
    build_restricted_agent_workflow_graph,
    execute_restricted_agent_workflow,
    operator_registry,
    validate_restricted_workflow_graph,
    validate_workflow_join,
)


checks: list[dict[str, object]] = []


def check(label: str, ok: bool, detail: object = None) -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": detail})


def fixture() -> tuple[dict[str, object], dict[str, object]]:
    plan = {
        "schema": "aibi-agent-evidence-plan/v1",
        "workspaceId": "workflow-fixture",
        "turnKey": "turn-fixture",
        "planVersion": 2,
        "fingerprint": "p" * 64,
        "steps": [
            {"kind": "semantic", "capabilityId": "agent.semantic.plan", "mutationMode": "read-only"},
            {"kind": "query", "capabilityId": "agent.query.execute", "mutationMode": "runtime-receipt"},
            {"kind": "draft", "capabilityId": "agent.action.draft", "mutationMode": "action-draft"},
        ],
    }
    answer = {
        "workspaceId": "workflow-fixture",
        "intentFrame": {"unresolved": []},
        "semanticPlan": {"status": "ready"},
        "semanticContext": {"fingerprint": "c" * 64},
        "queryPlanReceipt": {
            "receiptKey": "receipt-workflow-fixture",
            "status": "executed",
            "source": {"dataFingerprint": "d" * 64},
            "domainPackFingerprint": "k" * 64,
            "unresolved": [],
        },
        "actionDraft": {"status": "draft", "actionKey": "draft-workflow-fixture"},
        "answerCard": {"evidenceRefs": [{"type": "queryRuntime"}]},
    }
    return plan, answer


registry = operator_registry()
check("fixed-operator-registry-is-exact", set(OPERATORS) == {"context", "resolve", "clarify", "query", "validate", "unit", "chart", "explain", "export", "branch", "join"}, list(OPERATORS))
check("fixed-role-registry-is-exact", set(ROLES) == {"Orchestrator", "Planner", "Semantic Reviewer", "Evidence Reviewer", "Narrator"}, list(ROLES))
check("only-orchestrator-can-submit-capabilities", all(item["canSubmitCapability"] is (item["role"] == "Orchestrator") for item in registry["roles"]), registry["roles"])
check("all-experts-have-zero-tool-permissions", all(item["toolPermissions"] == "none" for item in registry["roles"] if item["role"] != "Orchestrator"))

plan, answer = fixture()
graph = build_restricted_agent_workflow_graph(plan=plan, answer=answer)
validation = validate_restricted_workflow_graph(graph)
check("fixture-graph-is-valid-and-version-bound", graph["schema"] == GRAPH_SCHEMA and graph["planVersion"] == 2 and validation["status"] == "passed", validation)
check("graph-binds-data-and-pack-fingerprints", graph["dataFingerprint"] == "d" * 64 and graph["domainPackFingerprint"] == "k" * 64)
check("capabilities-belong-only-to-orchestrator-nodes", all(not node["capabilityId"] or node["role"] == "Orchestrator" for node in graph["nodes"]))
parallel = validation["parallelReadOnlyGroups"]
check("independent-reviewers-are-one-parallel-readonly-group", any({"node-080-semantic-review", "node-081-evidence-review"}.issubset(set(group)) for group in parallel), parallel)
check("write-and-receipt-nodes-are-serial", validation["checks"]["statefulNodesSerial"] is True)

cycle = copy.deepcopy(graph)
cycle["nodes"][0]["dependsOn"] = [cycle["nodes"][-1]["nodeKey"]]
check("cycles-are-blocked", "workflow-cycle" in validate_restricted_workflow_graph(cycle)["blockers"])

unknown = copy.deepcopy(graph)
unknown["nodes"][0]["operator"] = "python"
check("unknown-operator-is-blocked", validate_restricted_workflow_graph(unknown)["checks"]["operatorsAllowlisted"] is False)

executable = copy.deepcopy(graph)
executable["nodes"][0]["code"] = "print('forbidden')"
check("arbitrary-operator-implementation-is-blocked", validate_restricted_workflow_graph(executable)["checks"]["declarationOnly"] is False)

parallel_writes = copy.deepcopy(graph)
query_node = next(node for node in parallel_writes["nodes"] if node["nodeKey"] == "node-050-query")
draft_node = next(node for node in parallel_writes["nodes"] if node["nodeKey"] == "node-070-draft")
draft_node["dependsOn"] = list(query_node["dependsOn"])
check("parallel-stateful-steps-are-blocked", validate_restricted_workflow_graph(parallel_writes)["checks"]["statefulNodesSerial"] is False)

common = {"workspaceId": "workflow-fixture", "planVersion": 2, "dataFingerprint": "d" * 64, "domainPackFingerprint": "k" * 64}
parents = [
    {**common, "evidenceRefs": []},
    {**common, "evidenceRefs": ["receipt-workflow-fixture"]},
]
joined = validate_workflow_join(parents=parents, workspace_id="workflow-fixture", plan_version=2, data_fingerprint="d" * 64, pack_fingerprint="k" * 64, required_evidence=["receipt-workflow-fixture"])
check("join-validates-complete-parent-contract", joined["status"] == "passed", joined)
for label, key, value in [
    ("join-blocks-workspace-mismatch", "workspaceId", "other-workspace"),
    ("join-blocks-plan-version-mismatch", "planVersion", 3),
    ("join-blocks-data-fingerprint-mismatch", "dataFingerprint", "x" * 64),
    ("join-blocks-pack-fingerprint-mismatch", "domainPackFingerprint", "x" * 64),
]:
    drifted = copy.deepcopy(parents)
    drifted[0][key] = value
    result = validate_workflow_join(parents=drifted, workspace_id="workflow-fixture", plan_version=2, data_fingerprint="d" * 64, pack_fingerprint="k" * 64, required_evidence=["receipt-workflow-fixture"])
    check(label, result["status"] == "blocked", result["blockers"])
missing_evidence = validate_workflow_join(parents=[{**common, "evidenceRefs": []}], workspace_id="workflow-fixture", plan_version=2, data_fingerprint="d" * 64, pack_fingerprint="k" * 64, required_evidence=["receipt-workflow-fixture"])
check("join-blocks-incomplete-evidence", missing_evidence["checks"]["evidenceComplete"] is False)


def delayed_reviewer(role: str, _: dict[str, object]) -> dict[str, object]:
    time.sleep(0.02 if role == "Semantic Reviewer" else 0.001)
    return {
        "schema": REVIEW_SCHEMA,
        "role": role,
        "decision": "pass",
        "blockers": [],
        "revisions": [],
        "evidenceRefs": ["receipt-workflow-fixture"] if role == "Evidence Reviewer" else [],
        "toolCalls": [],
        "canSubmitCapability": False,
    }


execution_a = execute_restricted_agent_workflow(graph=graph, plan=plan, answer=answer, reviewer_runner=delayed_reviewer)
execution_b = execute_restricted_agent_workflow(graph=graph, plan=plan, answer=answer, reviewer_runner=delayed_reviewer)
review_event_roles = [item["role"] for item in execution_a["events"] if item["eventType"] == "expert-review-completed"]
check("parallel-completion-does-not-change-public-event-order", execution_a["events"] == execution_b["events"] and review_event_roles == ["Semantic Reviewer", "Evidence Reviewer"], execution_a["events"])
check("parallel-experts-never-submit-capability-or-tools", execution_a["reviewerCapabilitySubmissionCount"] == 0 and execution_a["reviewerToolCallCount"] == 0)
check("all-four-experts-produce-structured-role-views", [item["role"] for item in execution_a["roleViews"]] == ["Planner", "Semantic Reviewer", "Evidence Reviewer", "Narrator"] and all(item["schema"] == REVIEW_SCHEMA and item["canSubmitCapability"] is False for item in execution_a["roleViews"]))


def failing_reviewer(role: str, _: dict[str, object]) -> dict[str, object]:
    if role == "Evidence Reviewer":
        raise RuntimeError("reviewer unavailable")
    return delayed_reviewer(role, {})


fallback = execute_restricted_agent_workflow(graph=graph, plan=plan, answer=answer, reviewer_runner=failing_reviewer)
check("expert-failure-degrades-to-single-orchestrator", fallback["mode"] == "single-orchestrator-fallback" and fallback["status"] == "completed", fallback)
check("fallback-review-remains-structured-and-tool-free", any(item["degraded"] for item in fallback["reviews"]) and all(item["toolCalls"] == [] for item in fallback["reviews"]))


def malicious_reviewer(role: str, _: dict[str, object]) -> dict[str, object]:
    return {"schema": REVIEW_SCHEMA, "role": role, "decision": "pass", "toolCalls": [{"tool": "shell"}]}


contained = execute_restricted_agent_workflow(graph=graph, plan=plan, answer=answer, reviewer_runner=malicious_reviewer)
check("reviewer-tool-attempt-is-contained-by-fallback", contained["mode"] == "single-orchestrator-fallback" and all(item["toolCalls"] == [] for item in contained["reviews"]))

with tempfile.TemporaryDirectory(prefix="aibi-c-restricted-workflow-") as temp_dir:
    env = os.environ.copy()
    env["AIBI_HYBRID_DB_PATH"] = str(Path(temp_dir) / "workflow.sqlite")
    env["AIBI_HYBRID_DUCKDB_PATH"] = str(Path(temp_dir) / "workflow.duckdb")

    def cli(*args: str) -> tuple[int, dict[str, object]]:
        completed = subprocess.run([sys.executable, "tools/aibi_cli.py", "--json", *args], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
        try:
            payload = json.loads(completed.stdout or completed.stderr or "{}")
        except json.JSONDecodeError:
            payload = {}
        return completed.returncode, payload

    operator_code, operator_payload = cli("restricted-workflow-operators")
    check("cli-exposes-fixed-operator-registry", operator_code == 0 and len(operator_payload.get("operators") or []) == 11)
    turn_code, turn_payload = cli("agent-turn-run", "说明当前工作区可回答的问题", "--workspace", "default", "--read-only")
    evidence_plan = turn_payload.get("evidencePlan") or {}
    persisted_graph = evidence_plan.get("workflowGraph") or {}
    persisted_execution = evidence_plan.get("workflowExecution") or {}
    check("agent-turn-persists-restricted-workflow-graph", turn_code == 0 and persisted_graph.get("schema") == GRAPH_SCHEMA, persisted_graph)
    check("agent-turn-completion-validates-workflow", (turn_payload.get("validation") or {}).get("checks", {}).get("workflowGraphValid") is True)
    event_types = [item.get("eventType") for item in turn_payload.get("events") or []]
    check("agent-turn-publishes-deterministic-expert-and-join-events", event_types.index("expert-review-completed") < event_types.index("workflow-join-completed") < event_types.index("validation-completed"), event_types)
    turn_key = str((turn_payload.get("turn") or {}).get("turnKey") or "")
    inspect_code, inspect_payload = cli("agent-workflow-graph", "--turn", turn_key, "--workspace", "default")
    check("persisted-graph-is-inspectable", inspect_code == 0 and inspect_payload.get("workflowExecution", {}).get("fingerprint") == persisted_execution.get("fingerprint"))
    _, created_workspace = cli("workspace-create", "--name", "隔离工作区", "--yes")
    other_workspace_id = str((created_workspace.get("workspace") or {}).get("id") or created_workspace.get("workspaceId") or "missing-workspace")
    cross_code, _ = cli("agent-workflow-graph", "--turn", turn_key, "--workspace", other_workspace_id)
    check("workflow-graph-is-workspace-isolated", cross_code != 0)

failed = [item for item in checks if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-restricted-workflow-graph-verify/v1",
    "checks": checks,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
