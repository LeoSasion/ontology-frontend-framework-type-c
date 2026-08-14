from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    checks: list[dict[str, Any]] = []

    def check(label: str, condition: bool, detail: Any = None) -> None:
        checks.append({"label": label, "ok": bool(condition)})
        if not condition:
            raise AssertionError(json.dumps({"label": label, "detail": detail}, ensure_ascii=False, default=str))

    with tempfile.TemporaryDirectory(prefix="aibi-workflow-recipes-") as temp_value:
        temp = Path(temp_value)
        database = temp / "runtime.sqlite"
        env = {
            **os.environ,
            "AIBI_HYBRID_DB_PATH": str(database),
            "AIBI_HYBRID_DUCKDB_PATH": str(temp / "runtime.duckdb"),
            "AIBI_WORKSPACE_RECOVERY_ROOT": str(temp / "recovery"),
            "PYTHONIOENCODING": "utf-8",
        }

        def run(*arguments: str, expected: int = 0) -> dict[str, Any]:
            completed = subprocess.run(
                [sys.executable, "tools/aibi_cli.py", "--json", *arguments],
                cwd=ROOT,
                env=env,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            payload = json.loads(completed.stdout.strip() or "{}")
            if completed.returncode != expected:
                raise AssertionError(json.dumps({"arguments": arguments, "status": completed.returncode, "payload": payload, "stderr": completed.stderr}, ensure_ascii=False))
            return payload

        run("status")
        request_key = "workflow-recipe-safe-change-v1"
        stages = [
            json.dumps({"label": "Inspect", "command": "status", "input": {}}, ensure_ascii=False),
            json.dumps({"label": "Recovery", "command": "workspace-recovery-create", "input": {"reason": "${reason}", "requestKey": "${requestKey}"}}, ensure_ascii=False),
        ]
        preview = run("workflow-recipe-preview", "--request-key", request_key, "--name", "Safe change", "--description", "Preview first", "--stage-json", stages[0], "--stage-json", stages[1])
        plan = preview.get("workflowRecipePlan") or {}
        check("preview-freezes-capability-order-and-confirmation-count", preview.get("dryRun") is True and len(plan.get("stages") or []) == 2 and plan.get("confirmationStageCount") == 1 and len(plan.get("planFingerprint") or "") == 64, preview)
        with closing(sqlite3.connect(database)) as connection:
            check("preview-writes-no-recipe", connection.execute("SELECT COUNT(*) FROM workflow_recipes").fetchone()[0] == 0)

        rejected = run("workflow-recipe-publish", "--request-key", request_key, "--name", "Safe change", "--description", "Preview first", "--stage-json", stages[0], "--stage-json", stages[1], "--expected-plan", "0" * 64, "--yes", expected=1)
        check("publish-rejects-stale-plan", rejected.get("ok") is False, rejected)
        published = run("workflow-recipe-publish", "--request-key", request_key, "--name", "Safe change", "--description", "Preview first", "--stage-json", stages[0], "--stage-json", stages[1], "--expected-plan", str(plan["planFingerprint"]), "--yes")
        recipe = published.get("workflowRecipe") or {}
        recipe_key = str(recipe.get("recipeKey") or "")
        check("publish-is-versioned-and-audited", published.get("changed") is True and recipe_key.startswith("recipe_") and recipe.get("stageCount") == 2, published)
        replay = run("workflow-recipe-publish", "--request-key", request_key, "--name", "Safe change", "--description", "Preview first", "--stage-json", stages[0], "--stage-json", stages[1], "--expected-plan", str(plan["planFingerprint"]), "--yes")
        check("response-loss-replay-is-idempotent", replay.get("changed") is False and replay.get("idempotentReplay") is True, replay)

        missing = run("workflow-recipe-plan", "--recipe", recipe_key)
        check("instantiation-never-executes-and-reports-missing-binding", missing.get("executesAutomatically") is False and missing.get("missingBindings") == ["reason", "requestKey"] and len(missing.get("stages") or []) == 2, missing)
        bound = run("workflow-recipe-plan", "--recipe", recipe_key, "--bindings-json", json.dumps({"reason": "Before semantic change", "requestKey": "fresh-workspace-recovery-key"}))
        check("bindings-produce-a-fresh-plan-not-an-authorization", bound.get("executesAutomatically") is False and bound.get("missingBindings") == [] and bound.get("confirmationStageCount") == 1 and bound.get("readyToProceed") is True, bound)
        check("fresh-request-key-is-fingerprinted-in-public-plan", "fresh-workspace-recovery-key" not in json.dumps(bound, ensure_ascii=False), bound)
        check("public-contract-does-not-expose-request-key", request_key not in json.dumps(published, ensure_ascii=False) and len(str(plan.get("requestKeyFingerprint") or "")) == 64, published)

        recursive = run("workflow-recipe-preview", "--request-key", "workflow-recursive-v1", "--name", "Recursive", "--stage-json", json.dumps({"command": "workflow-recipe-plan", "input": {}}), expected=1)
        check("recipes-cannot-recursively-execute-recipes", recursive.get("ok") is False, recursive)
        unknown_input = run("workflow-recipe-preview", "--request-key", "workflow-unknown-input-v1", "--name", "Unknown input", "--stage-json", json.dumps({"command": "status", "input": {"sql": "SELECT 1"}}), expected=1)
        check("recipe-rejects-unknown-sql-input-before-publish", unknown_input.get("ok") is False, unknown_input)
        literal_url = run("workflow-recipe-preview", "--request-key", "workflow-url-input-v1", "--name", "URL input", "--stage-json", json.dumps({"command": "workspace-recovery-create", "input": {"reason": "https://example.invalid", "requestKey": "${requestKey}"}}), expected=1)
        check("recipe-rejects-url-literals", literal_url.get("ok") is False, literal_url)
        frozen_request = run("workflow-recipe-preview", "--request-key", "workflow-frozen-key-v1", "--name", "Frozen key", "--stage-json", json.dumps({"command": "workspace-recovery-create", "input": {"reason": "${reason}", "requestKey": "stale-key"}}), expected=1)
        check("recipe-requires-fresh-placeholders-for-request-keys", frozen_request.get("ok") is False, frozen_request)
        other = run("workspace-create", "--name", "workflow isolation", "--yes")
        other_id = str((other.get("created") or {}).get("id") or "")
        isolated = run("workflow-recipes", "--workspace", other_id)
        check("recipes-are-workspace-isolated", bool(other_id) and isolated.get("count") == 0, isolated)

    print(json.dumps({"ok": True, "schema": "aibi-workflow-recipe-verify/v1", "generatedBy": "scripts/verify-workflow-recipes.py", "checks": checks, "failedChecks": []}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
