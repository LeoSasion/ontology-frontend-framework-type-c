from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from agent_evidence_plan_service import build_evidence_plan, finalize_evidence_plan  # noqa: E402


checks: list[dict[str, object]] = []


def check(label: str, ok: bool, detail: object = None) -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": None if ok else detail})


answer = {
    "workspaceId": "default",
    "intentFrame": {
        "schema": "aibi-agent-intent-frame/v1",
        "unresolved": [{"kind": "field-binding", "mention": "site_id", "reason": "multiple-field-candidates"}],
    },
    "semanticPlan": {"status": "needs-clarification"},
    "semanticContext": {"schema": "aibi-semantic-context-bundle/v1", "stale": False, "fingerprint": "c" * 64},
    "queryPlanReceipt": {
        "receiptKey": "receipt-blocker-test",
        "status": "blocked",
        "source": {"dataFingerprint": "d" * 64},
        "domainPackFingerprint": "k" * 64,
        "unresolved": [
            {"reason": "multiple-field-candidates", "mention": "site_id", "kind": "field-binding", "candidates": [{"tableKey": "sites"}]},
            {"kind": "compound-analysis-definition", "mention": "conversion_rate", "reason": "missing-numerator-denominator"},
        ],
    },
    "actionDraft": {"status": "read-only"},
    "answerCard": {"evidenceRefs": []},
}

plan = build_evidence_plan(workspace_id="default", turn_key="turn-blocker-test", answer=answer)
query_step = next(step for step in plan["steps"] if step["capabilityId"] == "agent.query.execute")
check("new-query-blockers-are-strings", all(isinstance(item, str) for item in query_step["blockers"]), query_step["blockers"])
check(
    "known-unresolved-objects-have-stable-readable-summaries",
    query_step["blockers"] == [
        "field-binding · site_id · multiple-field-candidates",
        "compound-analysis-definition · conversion_rate · missing-numerator-denominator",
    ],
    query_step["blockers"],
)

finalized = finalize_evidence_plan(plan, {
    "status": "failed",
    "safeToPresent": False,
    "fingerprint": "f" * 64,
    "blockers": [{"code": "legacy-validation-blocker", "message": "review required"}],
})
validation_step = next(step for step in finalized["steps"] if step["capabilityId"] == "agent.completion.verify")
check("finalization-also-normalizes-abnormal-blockers", validation_step["blockers"] == ["legacy-validation-blocker · review required"], validation_step["blockers"])
check("persistable-plan-never-contains-object-object", "[object Object]" not in json.dumps(finalized, ensure_ascii=False), finalized)

failed = [item for item in checks if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-agent-evidence-plan-blocker-verify/v1",
    "checks": checks,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
