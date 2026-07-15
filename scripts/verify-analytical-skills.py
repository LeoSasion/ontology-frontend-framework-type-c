from __future__ import annotations

import json
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
from analytical_skill_service import builtin_analytical_skills, match_analytical_skills, validate_analytical_skill_manifest
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


builtins = builtin_analytical_skills()
check("seven-neutral-builtins", len(builtins) == 7 and len({item["skillId"] for item in builtins}) == 7, [item["skillId"] for item in builtins])
check("builtins-use-registered-capabilities", all(capability.startswith("agent.") for item in builtins for capability in item["allowedCapabilities"]), builtins)

tie_runtime = {"fingerprint": "t" * 64, "enabledAnalyticalSkills": [
    {"skillId": skill_id, "version": "1.0.0", "fingerprint": skill_id.ljust(64, "0"), "taskTypes": ["overview"], "requiredRoles": [], "requiredDomainPacks": [], "allowedCapabilities": ["agent.answer.compose"], "stepTemplate": ["compose-answer"], "requiredEvidence": [], "blockingRules": [], "outputSchema": "aibi-agent-answer/v1", "confirmationMode": "read-only", "resourceLimits": {"maxSteps": 4, "maxRows": 10}}
    for skill_id in ("tie-one", "tie-two")
]}
tie_match = match_analytical_skills(tie_runtime, task_type="overview", roles=[], enabled_domain_packs=[])
check("equal-skill-evidence-requires-explicit-selection", tie_match["status"] == "needs-selection" and tie_match["selected"] is None, tie_match)

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
    try:
        schema_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        configured_rows = int(connection.execute("SELECT COUNT(*) FROM workspace_analytical_skills").fetchone()[0])
    finally:
        connection.close()

    config_payload = json.loads(export_path.read_text(encoding="utf-8")) if export_path.exists() else {}
    enabled_external = [item for item in (configured.get("runtime") or {}).get("enabledAnalyticalSkills", []) if item.get("skillId") == "external-demo"]
    isolated_external = [item for item in (isolated.get("enabledAnalyticalSkills") or []) if item.get("skillId") == "external-demo"]

    check("schema-v6-bootstrap", status_code == 0 and schema_version == 6, schema_version)
    check("builtin-runtime-defaults", catalog_code == 0 and len(catalog.get("enabledAnalyticalSkills") or []) == 7, catalog)
    check("lint-contract", lint_code == 0 and linted.get("valid") is True and len((linted.get("manifest") or {}).get("fingerprint") or "") == 64, linted)
    check("install-requires-confirmation", preview_code == 0 and preview.get("requiresConfirmation") is True and preview.get("dryRun") is True, preview)
    check("confirmed-install-disabled-by-default", install_code == 0 and installed.get("confirmed") is True and disabled_catalog_code == 0 and not any(item.get("skillId") == "external-demo" for item in disabled_catalog.get("enabledAnalyticalSkills") or []), disabled_catalog)
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
check("config-tables-registered", "analytical_skills" in CONFIG_TABLES and "workspace_analytical_skills" in CONFIG_TABLES, CONFIG_TABLES)

failed = [item for item in checks if not item["ok"]]
print(json.dumps({"ok": not failed, "schema": "aibi-analytical-skills-verify/v1", "checks": checks, "failedChecks": failed}, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
