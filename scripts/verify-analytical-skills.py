from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from agent_policy_hook_service import evaluate_agent_policy_hooks
from analytical_skill_service import analytical_skill_runtime_context, builtin_analytical_skills, match_analytical_skills, validate_analytical_skill_manifest
from config_command_service import CONFIG_TABLES


checks: list[dict[str, object]] = []


def check(label: str, ok: bool, detail: object = "") -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": "" if ok else detail})


def run_cli(env: dict[str, str], *args: str) -> tuple[int, dict]:
    completed = subprocess.run([sys.executable, "tools/bi_cli.py", "--json", *args], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", timeout=60)
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {"stdout": completed.stdout, "stderr": completed.stderr}
    return completed.returncode, payload


def external_manifest(skill_id: str = "external-demo") -> dict:
    return {
        "schema": "aibi-analytical-skill/v1",
        "skillId": skill_id,
        "version": "1.0.0",
        "displayName": {"zh": "外部声明示例", "en": "External declaration example"},
        "description": {"zh": "验证安全的声明式扩展。", "en": "Verify a safe declarative extension."},
        "taskTypes": ["comparison"],
        "requiredRoles": ["measure"],
        "requiredDomainPacks": [],
        "allowedCapabilities": ["agent.semantic.plan", "agent.answer.compose"],
        "stepTemplate": ["resolve-measure", "verify-evidence", "compose-answer"],
        "requiredEvidence": ["field-provenance"],
        "blockingRules": ["unresolved-measure"],
        "outputSchema": "aibi-agent-answer/v1",
        "confirmationMode": "read-only",
        "resourceLimits": {"maxSteps": 8, "maxRows": 100},
    }


LEGACY_FINGERPRINT_KEYS = (
    "schema", "skillId", "version", "displayName", "description", "taskTypes",
    "requiredRoles", "requiredDomainPacks", "allowedCapabilities", "stepTemplate",
    "requiredEvidence", "blockingRules", "outputSchema", "confirmationMode",
    "resourceLimits", "sourceType",
)


def legacy_fingerprint(manifest: dict) -> str:
    material = {key: manifest[key] for key in LEGACY_FINGERPRINT_KEYS}
    canonical = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


builtins = builtin_analytical_skills()
check("thirteen-neutral-builtins", len(builtins) == 13 and len({item["skillId"] for item in builtins}) == 13, [item["skillId"] for item in builtins])
check("analysis-and-understanding-skills-are-declarative", sum(item["skillKind"] == "analysis" for item in builtins) == 7 and sum(item["skillKind"] == "understanding" for item in builtins) == 6, [(item["skillId"], item["skillKind"]) for item in builtins])
check("builtins-use-registered-capabilities", all(capability.startswith("agent.") for item in builtins for capability in item["allowedCapabilities"]), builtins)

overview_raw = json.loads((ROOT / "analytical-skills" / "overview.json").read_text(encoding="utf-8"))
legacy_overview = validate_analytical_skill_manifest(overview_raw, source_type="builtin")
normalized_overview = {key: value for key, value in legacy_overview.items() if key not in {"fingerprint", "sourceType"}}
round_tripped_overview = validate_analytical_skill_manifest(normalized_overview, source_type="builtin")
check(
    "legacy-overview-default-extensions-preserve-fingerprint",
    legacy_overview["fingerprint"] == legacy_fingerprint(legacy_overview)
    and round_tripped_overview["fingerprint"] == legacy_overview["fingerprint"],
    {
        "legacy": legacy_overview["fingerprint"],
        "expected": legacy_fingerprint(legacy_overview),
        "roundTripped": round_tripped_overview["fingerprint"],
    },
)

tie_runtime = {"fingerprint": "t" * 64, "enabledAnalyticalSkills": [
    {"skillId": skill_id, "version": "1.0.0", "fingerprint": skill_id.ljust(64, "0"), "taskTypes": ["overview"], "requiredRoles": [], "requiredDomainPacks": [], "allowedCapabilities": ["agent.answer.compose"], "stepTemplate": ["compose-answer"], "requiredEvidence": [], "blockingRules": [], "outputSchema": "aibi-agent-answer/v1", "confirmationMode": "read-only", "resourceLimits": {"maxSteps": 4, "maxRows": 10}}
    for skill_id in ("tie-one", "tie-two")
]}
tie_match = match_analytical_skills(tie_runtime, task_type="overview", roles=[], enabled_domain_packs=[])
check("equal-skill-evidence-requires-explicit-selection", tie_match["status"] == "needs-selection" and tie_match["selected"] is None, tie_match)

supporting_runtime = {"fingerprint": "s" * 64, "enabledAnalyticalSkills": [
    {"skillId": "overview-analysis", "version": "1.0.0", "fingerprint": "a" * 64, "skillKind": "analysis", "taskTypes": ["overview"], "requiredRoles": [], "requiredDomainPacks": [], "allowedCapabilities": ["agent.semantic.plan", "agent.answer.compose"], "stepTemplate": ["compose-answer"], "requiredEvidence": ["query-plan-receipt"], "blockingRules": [], "semanticGuards": [], "compatibleContracts": ["aibi-agent-evidence-plan/v1"], "outputSchema": "aibi-agent-answer/v1", "confirmationMode": "read-only", "resourceLimits": {"maxSteps": 8, "maxRows": 100}},
    {"skillId": "ratio-understanding", "version": "1.0.0", "fingerprint": "u" * 64, "skillKind": "understanding", "taskTypes": ["overview"], "requiredRoles": [], "requiredDomainPacks": [], "allowedCapabilities": ["agent.context.route"], "stepTemplate": ["resolve-ratio"], "requiredEvidence": ["metric-definition"], "blockingRules": ["implicit-denominator"], "triggerSignals": ["ratio-request"], "slotRules": [{"whenAny": ["ratio-request"], "requireAll": ["numerator", "denominator"]}], "semanticGuards": ["no-implicit-denominator"], "compatibleContracts": ["aibi-business-understanding-frame/v1"], "outputSchema": "aibi-business-understanding-frame/v1", "confirmationMode": "read-only", "resourceLimits": {"maxSteps": 4, "maxRows": 1}},
]}
supporting_match = match_analytical_skills(
    supporting_runtime,
    task_type="overview",
    roles=[],
    enabled_domain_packs=[],
    business_signals=["ratio-request"],
    intent_slots={"numerator": {"status": "missing"}, "denominator": {"status": "missing"}},
)
check("understanding-skill-supports-without-replacing-analysis-skill", supporting_match["selected"]["skillId"] == "overview-analysis" and supporting_match["supporting"][0]["skillId"] == "ratio-understanding" and supporting_match["supporting"][0]["missingSlots"] == ["denominator", "numerator"], supporting_match)

for label, mutation in (
    ("reject-python", {"script": "python -c pass"}),
    ("reject-sql", {"description": {"zh": "SELECT x FROM y", "en": "unsafe"}}),
    ("reject-url", {"description": {"zh": "https://example.com", "en": "unsafe"}}),
    ("reject-tool", {"tools": ["shell"]}),
    ("reject-unregistered-capability", {"allowedCapabilities": ["agent.shell.execute"]}),
):
    candidate = external_manifest(f"unsafe-{label}")
    candidate.update(mutation)
    try:
        validate_analytical_skill_manifest(candidate)
        rejected = False
    except ValueError:
        rejected = True
    check(label, rejected, candidate)

with tempfile.TemporaryDirectory(prefix="aibi-analytical-skill-") as temp:
    root = Path(temp)
    env = dict(os.environ)
    env["AIBI_HYBRID_DB_PATH"] = str(root / "metadata.sqlite")
    env["AIBI_HYBRID_DUCKDB_PATH"] = str(root / "analytics.duckdb")
    env["PYTHONIOENCODING"] = "utf-8"
    manifest_path = root / "external-demo.json"
    manifest_path.write_text(json.dumps(external_manifest(), ensure_ascii=False), encoding="utf-8")

    status_code, _ = run_cli(env, "status")
    fixture_code, fixture = run_cli(
        env,
        "import-commit", str(ROOT / "validation-inputs" / "orders.csv"),
        "--table", "orders", "--name", "Orders", "--mode", "create", "--yes",
    )
    business_gap_code, business_gap = run_cli(env, "ask", "看看数据")
    ratio_gap_code, ratio_gap = run_cli(env, "ask", "请计算退款率")
    catalog_code, catalog = run_cli(env, "analytical-skills")
    lint_code, linted = run_cli(env, "analytical-skill-lint", "--manifest", str(manifest_path))
    preview_code, preview = run_cli(env, "analytical-skill-install", "--manifest", str(manifest_path))
    install_code, installed = run_cli(env, "analytical-skill-install", "--manifest", str(manifest_path), "--yes")
    disabled_catalog_code, disabled_catalog = run_cli(env, "analytical-skills")
    set_preview_code, set_preview = run_cli(env, "analytical-skill-set", "--skill", "external-demo", "--state", "enabled")
    set_code, configured = run_cli(env, "analytical-skill-set", "--skill", "external-demo", "--state", "enabled", "--yes")
    match_code, matched = run_cli(env, "analytical-skill-match", "--task-type", "comparison", "--role", "measure", "--skill", "external-demo")
    workspace_code, workspace = run_cli(env, "workspace-create", "--name", "Isolated Skill Workspace", "--yes")
    isolated_id = str((workspace.get("created") or workspace.get("workspace") or workspace.get("proposed") or {}).get("id") or "")
    isolated_code, isolated = run_cli(env, "analytical-skills", "--workspace", isolated_id)
    export_path = root / "config.json"
    export_code, exported = run_cli(env, "export-config", str(export_path))
    turn_code, turn = run_cli(env, "agent-turn-run", "--read-only", "比较本月指标")

    connection = sqlite3.connect(env["AIBI_HYBRID_DB_PATH"])
    connection.row_factory = sqlite3.Row
    try:
        schema_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        configured_rows = int(connection.execute("SELECT COUNT(*) FROM workspace_analytical_skills").fetchone()[0])
        stored_external = connection.execute("SELECT manifest_json, fingerprint FROM analytical_skills WHERE skill_id = 'external-demo'").fetchone()
        stored_manifest = json.loads(str(stored_external["manifest_json"])) if stored_external else {}
        stored_round_trip = validate_analytical_skill_manifest(stored_manifest, source_type="external") if stored_manifest else {}
        connection.execute("UPDATE analytical_skills SET fingerprint = ? WHERE skill_id = 'external-demo'", ("0" * 64,))
        connection.commit()
        try:
            analytical_skill_runtime_context(connection, "default")
            tampered_fingerprint_error: Exception | None = None
        except Exception as error:
            tampered_fingerprint_error = error
    finally:
        connection.close()

    config_payload = json.loads(export_path.read_text(encoding="utf-8")) if export_path.exists() else {}
    enabled_external = [item for item in (configured.get("runtime") or {}).get("enabledAnalyticalSkills", []) if item.get("skillId") == "external-demo"]
    isolated_external = [item for item in (isolated.get("enabledAnalyticalSkills") or []) if item.get("skillId") == "external-demo"]

    check("schema-v9-bootstrap", status_code == 0 and schema_version == 9, schema_version)
    check("business-gap-fixture-imported", fixture_code == 0 and fixture.get("ok") is True, fixture)
    check(
        "underspecified-question-blocks-execution-and-draft",
        business_gap_code == 0
        and (business_gap.get("businessUnderstanding") or {}).get("status") == "needs-clarification"
        and (business_gap.get("answerCard") or {}).get("kind") == "clarification"
        and (business_gap.get("queryPlanReceipt") or {}).get("status") == "blocked"
        and business_gap.get("executionPlan") is None
        and business_gap.get("requiresConfirmation") is False
        and (business_gap.get("actionDraft") or {}).get("status") == "read-only"
        and len((business_gap.get("clarification") or {}).get("items") or []) == 1,
        business_gap,
    )
    check(
        "ratio-without-components-never-falls-through-to-count",
        ratio_gap_code == 0
        and (ratio_gap.get("businessUnderstanding") or {}).get("status") == "needs-clarification"
        and {"numerator", "denominator"}.issubset(set((ratio_gap.get("businessUnderstanding") or {}).get("missingSlots") or []))
        and (ratio_gap.get("queryPlanReceipt") or {}).get("status") == "blocked"
        and not (ratio_gap.get("answerCard") or {}).get("query")
        and (ratio_gap.get("answerCard") or {}).get("rows") == [],
        ratio_gap,
    )
    check("builtin-runtime-defaults", catalog_code == 0 and len(catalog.get("enabledAnalyticalSkills") or []) == 13, catalog)
    check("lint-contract", lint_code == 0 and linted.get("valid") is True and len((linted.get("manifest") or {}).get("fingerprint") or "") == 64, linted)
    check("install-requires-confirmation", preview_code == 0 and preview.get("requiresConfirmation") is True and preview.get("dryRun") is True, preview)
    check("confirmed-install-disabled-by-default", install_code == 0 and installed.get("confirmed") is True and disabled_catalog_code == 0 and not any(item.get("skillId") == "external-demo" for item in disabled_catalog.get("enabledAnalyticalSkills") or []), disabled_catalog)
    check(
        "normalized-legacy-external-manifest-round-trips-fingerprint",
        bool(stored_external)
        and stored_round_trip.get("fingerprint") == stored_external["fingerprint"]
        and stored_external["fingerprint"] == (installed.get("change") or {}).get("fingerprint"),
        {"stored": dict(stored_external) if stored_external else None, "roundTrip": stored_round_trip, "installed": installed},
    )
    check(
        "tampered-persisted-fingerprint-raises-runtime-error",
        isinstance(tampered_fingerprint_error, RuntimeError)
        and "fingerprint drifted" in str(tampered_fingerprint_error),
        {"type": type(tampered_fingerprint_error).__name__ if tampered_fingerprint_error else None, "message": str(tampered_fingerprint_error or "")},
    )
    check("workspace-set-requires-confirmation", set_preview_code == 0 and set_preview.get("requiresConfirmation") is True, set_preview)
    check("confirmed-workspace-enable", set_code == 0 and len(enabled_external) == 1 and configured_rows == 1, configured)
    check("deterministic-skill-match", match_code == 0 and (matched.get("match") or {}).get("selected", {}).get("skillId") == "external-demo" and (matched.get("match") or {}).get("status") == "ready", matched)
    check("workspace-isolation", workspace_code == 0 and isolated_code == 0 and isolated_id and not isolated_external, isolated)
    check("config-portability-includes-skill-catalog-and-state", export_code == 0 and "analytical_skills" in (config_payload.get("tables") or {}) and "workspace_analytical_skills" in (config_payload.get("tables") or {}) and len(config_payload["tables"]["analytical_skills"]) == 1 and len(config_payload["tables"]["workspace_analytical_skills"]) == 1, exported)
    check("agent-turn-carries-skill-and-policy", turn_code == 0 and bool((turn.get("evidencePlan") or {}).get("skillRefs")) and (turn.get("validation") or {}).get("policyHooks", {}).get("status") == "passed", turn)

dummy_plan = {"workspaceId": "default", "steps": [{"capabilityId": "agent.intent.resolve", "requiredEvidence": []}], "fingerprint": "x" * 64}
malicious_match = {"selected": {"allowedCapabilities": ["agent.intent.resolve"], "resourceLimits": {"maxSteps": 2}, "script": "unsafe"}}
policy = evaluate_agent_policy_hooks(workspace_id="default", plan=dummy_plan, skill_match=malicious_match)
check("policy-hook-blocks-injected-executable-field", policy["status"] == "blocked" and "declaration-only-skill" in policy["blockers"], policy)
valid_plan = {
    "workspaceId": "default",
    "steps": [{"capabilityId": "agent.context.route", "mutationMode": "read-only", "requiredEvidence": ["metric-definition"]}],
    "fingerprint": "p" * 64,
}
supporting_policy = evaluate_agent_policy_hooks(workspace_id="default", plan=valid_plan, skill_match=supporting_match)
check("policy-validates-primary-and-supporting-skill-declarations", supporting_policy["status"] == "passed" and supporting_policy["details"]["skillCount"] == 2 and all(item["declarationValid"] and item["capabilitiesValid"] and item["resourcesValid"] and item["compatibleContractsValid"] for item in supporting_policy["details"]["skillChecks"]), supporting_policy)
unsafe_supporting = json.loads(json.dumps(supporting_match))
unsafe_supporting["supporting"][0]["allowedCapabilities"] = ["agent.shell.execute"]
unsafe_supporting["supporting"][0]["compatibleContracts"] = ["external-contract/v9"]
unsafe_policy = evaluate_agent_policy_hooks(workspace_id="default", plan=valid_plan, skill_match=unsafe_supporting)
check("supporting-skill-cannot-elevate-capabilities-or-contracts", unsafe_policy["status"] == "blocked" and "registered-capabilities-only" in unsafe_policy["blockers"] and "skill-compatible-contracts" in unsafe_policy["blockers"], unsafe_policy)
check("config-tables-registered", "analytical_skills" in CONFIG_TABLES and "workspace_analytical_skills" in CONFIG_TABLES, CONFIG_TABLES)

failed = [item for item in checks if not item["ok"]]
print(json.dumps({"ok": not failed, "schema": "aibi-analytical-skills-verify/v1", "checks": checks, "failedChecks": failed}, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
