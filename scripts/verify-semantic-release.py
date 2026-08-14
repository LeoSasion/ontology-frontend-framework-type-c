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

    with tempfile.TemporaryDirectory(prefix="aibi-semantic-release-") as temp_value:
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
            result = subprocess.run(
                [sys.executable, "tools/aibi_cli.py", "--json", *arguments],
                cwd=ROOT,
                env=env,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            try:
                payload = json.loads(result.stdout.strip() or "{}")
            except json.JSONDecodeError:
                payload = {"stdout": result.stdout, "stderr": result.stderr}
            if result.returncode != expected:
                raise AssertionError(json.dumps({"arguments": arguments, "status": result.returncode, "payload": payload, "stderr": result.stderr}, ensure_ascii=False))
            return payload

        run("status")
        term = run(
            "semantic-patch-propose", "--adapter", "user-correction-v1", "--source-type", "user-correction",
            "--source-name", "Finance owner", "--kind", "term", "--name", "净收入",
            "--definition", "收入扣除退款后的金额", "--yes",
        )
        rule = run(
            "semantic-patch-propose", "--adapter", "user-correction-v1", "--source-type", "user-correction",
            "--source-name", "Finance owner", "--kind", "rule", "--title", "退款口径",
            "--statement", "退款发生时从确认收入中扣除", "--yes",
        )
        term_key = str((term.get("proposals") or [{}])[0].get("proposalKey") or "")
        rule_key = str((rule.get("proposals") or [{}])[0].get("proposalKey") or "")
        check("reviewable-proposals-exist-before-release", term_key.startswith("patch_") and rule_key.startswith("patch_"), {"term": term, "rule": rule})

        request_key = "semantic-release-finance-v1"
        preview = run(
            "semantic-release-preview", "--request-key", request_key, "--label", "Finance semantics v1",
            "--proposal", term_key, "--proposal", rule_key,
        )
        plan = preview.get("releasePlan") or {}
        check(
            "release-preview-is-bounded-read-only-and-exact",
            preview.get("dryRun") is True
            and plan.get("readyToPublish") is True
            and len(plan.get("planFingerprint") or "") == 64
            and plan.get("proposalKeys") == [term_key, rule_key]
            and len(plan.get("changes") or []) == 2,
            preview,
        )
        with closing(sqlite3.connect(database)) as connection:
            before_release = connection.execute("SELECT COUNT(*) FROM semantic_releases").fetchone()[0]
            pending_before = connection.execute("SELECT COUNT(*) FROM semantic_patch_proposals WHERE status='pending'").fetchone()[0]
        check("release-preview-writes-no-release-or-review-decision", before_release == 0 and pending_before == 2, {"releases": before_release, "pending": pending_before})

        missing_binding = run(
            "semantic-release-publish", "--request-key", request_key, "--expected-plan", "0" * 64,
            "--label", "Finance semantics v1", "--proposal", term_key, "--proposal", rule_key, "--yes",
            expected=1,
        )
        check("publish-refuses-a-different-plan-fingerprint", missing_binding.get("ok") is False)

        published = run(
            "semantic-release-publish", "--request-key", request_key,
            "--expected-plan", str(plan["planFingerprint"]), "--label", "Finance semantics v1",
            "--proposal", term_key, "--proposal", rule_key, "--yes",
        )
        release = published.get("release") or {}
        release_key = str(release.get("releaseKey") or "")
        check(
            "release-publishes-all-proposals-in-one-current-version",
            published.get("confirmed") is True
            and published.get("changed") is True
            and release_key.startswith("release_")
            and release.get("proposalCount") == 2
            and release.get("current") is True,
            published,
        )
        with closing(sqlite3.connect(database)) as connection:
            accepted = connection.execute("SELECT COUNT(*) FROM semantic_patch_proposals WHERE status='accepted'").fetchone()[0]
            trusted_terms = connection.execute("SELECT COUNT(*) FROM context_terms WHERE status='confirmed'").fetchone()[0]
            trusted_rules = connection.execute("SELECT COUNT(*) FROM context_rules WHERE status='confirmed'").fetchone()[0]
            events = connection.execute("SELECT event_type FROM semantic_release_events ORDER BY event_sequence").fetchall()
        check("atomic-release-applies-trusted-semantics-and-audit-event", accepted == 2 and trusted_terms == 1 and trusted_rules == 1 and events == [("published",)], {"accepted": accepted, "terms": trusted_terms, "rules": trusted_rules, "events": events})

        replay = run(
            "semantic-release-publish", "--request-key", request_key,
            "--expected-plan", str(plan["planFingerprint"]), "--label", "Finance semantics v1",
            "--proposal", term_key, "--proposal", rule_key, "--yes",
        )
        check("publish-response-loss-replay-is-idempotent", replay.get("changed") is False and replay.get("idempotentReplay") is True and (replay.get("release") or {}).get("releaseKey") == release_key, replay)
        check("public-release-redacts-the-request-key", request_key not in json.dumps(published, ensure_ascii=False) and len(str(release.get("requestKeyFingerprint") or "")) == 64, release)

        rollback_key = "semantic-release-finance-v1-rollback"
        rollback_preview = run("semantic-release-rollback", "--release", release_key, "--request-key", rollback_key)
        rollback_plan = rollback_preview.get("rollbackPlan") or {}
        check("rollback-is-a-separate-exact-preview", rollback_preview.get("dryRun") is True and rollback_plan.get("readyToRollback") is True and len(rollback_plan.get("planFingerprint") or "") == 64, rollback_preview)
        rolled_back = run(
            "semantic-release-rollback", "--release", release_key, "--request-key", rollback_key,
            "--expected-plan", str(rollback_plan["planFingerprint"]), "--yes",
        )
        with closing(sqlite3.connect(database)) as connection:
            remaining_targets = connection.execute("SELECT (SELECT COUNT(*) FROM context_terms) + (SELECT COUNT(*) FROM context_rules)").fetchone()[0]
            event_types = [row[0] for row in connection.execute("SELECT event_type FROM semantic_release_events ORDER BY event_sequence")]
        check("rollback-restores-the-pre-release-snapshot", (rolled_back.get("release") or {}).get("status") == "rolled_back" and remaining_targets == 0 and event_types == ["published", "rolled_back"], {"rollback": rolled_back, "targets": remaining_targets, "events": event_types})
        rollback_replay = run(
            "semantic-release-rollback", "--release", release_key, "--request-key", rollback_key,
            "--expected-plan", str(rollback_plan["planFingerprint"]), "--yes",
        )
        check("rollback-response-loss-replay-is-idempotent", rollback_replay.get("changed") is False and rollback_replay.get("idempotentReplay") is True, rollback_replay)

        drift_patch = run(
            "semantic-patch-propose", "--adapter", "user-correction-v1", "--source-type", "user-correction",
            "--source-name", "Ops owner", "--kind", "term", "--name", "有效订单",
            "--definition", "未取消且已确认的订单", "--yes",
        )
        drift_proposal = str((drift_patch.get("proposals") or [{}])[0].get("proposalKey") or "")
        drift_request = "semantic-release-ops-v1"
        drift_preview = run("semantic-release-preview", "--request-key", drift_request, "--label", "Ops semantics v1", "--proposal", drift_proposal)
        drift_plan = drift_preview.get("releasePlan") or {}
        drift_published = run(
            "semantic-release-publish", "--request-key", drift_request, "--expected-plan", str(drift_plan["planFingerprint"]),
            "--label", "Ops semantics v1", "--proposal", drift_proposal, "--yes",
        )
        drift_release_key = str((drift_published.get("release") or {}).get("releaseKey") or "")
        with closing(sqlite3.connect(database)) as connection:
            connection.execute("UPDATE context_terms SET definition='out-of-band drift' WHERE workspace_id='default'")
            connection.commit()
        stale = run("semantic-releases", "--release", drift_release_key)
        stale_release = stale.get("release") or {}
        blocked_rollback = run("semantic-release-rollback", "--release", drift_release_key, "--request-key", "drift-rollback")
        check("target-drift-marks-release-stale-and-blocks-rollback", stale_release.get("status") == "stale" and stale_release.get("current") is False and (blocked_rollback.get("rollbackPlan") or {}).get("readyToRollback") is False, {"stale": stale, "rollback": blocked_rollback})

        duplicate_a = run(
            "semantic-patch-propose", "--adapter", "user-correction-v1", "--source-type", "user-correction",
            "--source-name", "Owner A", "--kind", "term", "--name", "同一术语", "--definition", "定义 A", "--yes",
        )
        duplicate_b = run(
            "semantic-patch-propose", "--adapter", "user-correction-v1", "--source-type", "user-correction",
            "--source-name", "Owner B", "--kind", "term", "--name", "同一术语", "--definition", "定义 B", "--yes",
        )
        duplicate_keys = [str((item.get("proposals") or [{}])[0].get("proposalKey") or "") for item in (duplicate_a, duplicate_b)]
        duplicate_plan = run(
            "semantic-release-preview", "--request-key", "duplicate-target-release",
            "--proposal", duplicate_keys[0], "--proposal", duplicate_keys[1],
        ).get("releasePlan") or {}
        check("one-release-cannot-contain-conflicting-targets", duplicate_plan.get("readyToPublish") is False and any(str(item).startswith("duplicate-target:") for item in duplicate_plan.get("blockers") or []), duplicate_plan)

        other = run("workspace-create", "--name", "semantic isolation", "--yes")
        other_id = str((other.get("created") or {}).get("id") or "")
        isolated = run("semantic-releases", "--workspace", other_id)
        check("semantic-releases-are-workspace-isolated", bool(other_id) and isolated.get("count") == 0 and isolated.get("workspaceId") == other_id, isolated)

    print(json.dumps({
        "ok": True,
        "schema": "aibi-semantic-release-verify/v1",
        "generatedBy": "scripts/verify-semantic-release.py",
        "checks": checks,
        "failedChecks": [item["label"] for item in checks if not item["ok"]],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
