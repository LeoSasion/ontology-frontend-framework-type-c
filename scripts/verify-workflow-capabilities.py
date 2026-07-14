from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from bi_cli_envelope import enrich_cli_output
from bi_cli_parser import build_parser
from capability_contract_service import build_capability_contract, capability_registry, validate_capability_invocation
from context_budget_service import compact_context_segments
from workflow_stage_service import build_workflow_stage


checks: list[dict[str, object]] = []


def check(label: str, ok: bool, detail: object = None) -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": detail})


parser = build_parser()
registry = capability_registry(parser)
commands = [item["command"] for item in registry]
check("registry-covers-every-command-once", len(commands) == len(set(commands)) and len(commands) >= 90, len(commands))

worker = build_capability_contract("source-intelligence-job-run", {
    "domain": "job",
    "mutationMode": "evidence-receipt",
    "requiresYes": False,
    "writesEvidence": True,
    "writesBusinessState": False,
})
check(
    "owned-worker-capability-is-explicit",
    worker["permissions"]["process"] == "owned-worker"
    and worker["permissions"]["otherAibiRepositories"] == "forbidden"
    and worker["job"]["restartPolicy"] == "fail-explicitly",
)
check(
    "disallowed-entrypoint-is-blocked",
    validate_capability_invocation(worker, entrypoint="agent", confirmed=False, workspace_id="default") == ["entrypoint-not-allowed"],
)

stage_a = build_workflow_stage(
    command="query",
    args={"table": "orders", "group": "channel", "limit": 10},
    result={"ok": True, "evidence": [{"type": "query-receipt", "key": "receipt-1"}]},
)
stage_b = build_workflow_stage(
    command="query",
    args={"limit": 10, "group": "channel", "table": "orders"},
    result={"ok": True, "evidence": [{"key": "receipt-1", "type": "query-receipt"}]},
)
check(
    "stage-fingerprints-are-canonical",
    stage_a["inputFingerprint"] == stage_b["inputFingerprint"]
    and stage_a["evidenceFingerprint"] == stage_b["evidenceFingerprint"],
)

enriched = enrich_cli_output(
    {"ok": True, "evidence": [{"type": "query-receipt", "key": "receipt-1"}]},
    argparse.Namespace(command="query", json=True),
    parser,
)
check(
    "unified-envelope-carries-capability-and-stage",
    enriched["capability"]["capabilityId"] == "cli.query"
    and enriched["workflowStage"]["capabilityId"] == "cli.query"
    and enriched["workflowStage"]["status"] == "completed",
)

segments = [
    {"id": "decision", "priority": "critical", "content": {"status": "blocked", "reason": "ambiguous-field"}},
    {"id": "receipt", "priority": "evidence", "content": {"receiptKey": "receipt-1"}, "evidenceRefs": ["receipt-1"]},
    {"id": "diagnostic", "priority": "diagnostic", "content": {"trace": "x" * 2_000}},
]
compacted = compact_context_segments(segments, 512)
check(
    "context-budget-drops-diagnostic-first",
    compacted["status"] == "compacted"
    and compacted["keptIds"] == ["decision", "receipt"]
    and compacted["droppedIds"] == ["diagnostic"],
)
check(
    "required-evidence-reference-is-preserved",
    compacted["requiredEvidenceRefs"] == ["receipt-1"] and compacted["missingRequiredEvidenceRefs"] == [],
)

overflow = compact_context_segments([
    {"id": "required", "priority": "critical", "content": {"definition": "x" * 1_000}, "evidenceRefs": ["receipt-critical"]},
], 256)
check(
    "required-overflow-blocks-without-dropping",
    overflow["status"] == "blocked"
    and overflow["keptIds"] == ["required"]
    and overflow["blockers"] == ["required-context-exceeds-budget"],
)

failed = [item for item in checks if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-workflow-capability-verify/v1",
    "generatedBy": "scripts/verify-workflow-capabilities.py",
    "checks": checks,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
