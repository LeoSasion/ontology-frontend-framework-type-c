from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
CHECKS: list[dict[str, object]] = []


def check(label: str, ok: bool, detail: object = None) -> None:
    CHECKS.append({"label": label, "ok": bool(ok), "detail": detail})


def run(args: list[str], env: dict[str, str]) -> dict[str, object]:
    completed = subprocess.run(
        [sys.executable, "tools/bi_cli.py", "--json", *args],
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        payload = {"ok": False, "stdout": completed.stdout, "stderr": completed.stderr}
    payload["processExitCode"] = completed.returncode
    return payload


with tempfile.TemporaryDirectory(prefix="aibi-c-domain-packs-") as temp_dir:
    env = os.environ.copy()
    env["AIBI_HYBRID_DB_PATH"] = str(Path(temp_dir) / "metadata.sqlite")
    env["AIBI_HYBRID_DUCKDB_PATH"] = str(Path(temp_dir) / "analytics.duckdb")

    initial = run(["domain-packs"], env)
    available = initial.get("availableDomainPacks") if isinstance(initial.get("availableDomainPacks"), list) else []
    check(
        "validated-registry-discovers-owned-packs",
        initial.get("ok") is True
        and {item.get("packId") for item in available if isinstance(item, dict)} == {"platform-commerce", "erp-units"}
        and all(item.get("compatible") is True for item in available if isinstance(item, dict)),
        available,
    )
    check("new-workspace-defaults-to-no-domain-packs", initial.get("enabledDomainPacks") == [], initial.get("enabledDomainPacks"))

    preview = run(["domain-pack-set", "--pack", "platform-commerce", "--state", "enabled"], env)
    after_preview = run(["domain-packs"], env)
    check(
        "enable-requires-confirmation-and-preview-does-not-write",
        preview.get("dryRun") is True
        and preview.get("requiresConfirmation") is True
        and after_preview.get("enabledDomainPacks") == [],
        preview,
    )

    enabled = run(["domain-pack-set", "--pack", "platform-commerce", "--state", "enabled", "--yes"], env)
    status = run(["status"], env)
    enabled_refs = enabled.get("enabledDomainPacks") if isinstance(enabled.get("enabledDomainPacks"), list) else []
    check(
        "confirmed-enable-is-workspace-scoped-and-receipted",
        enabled.get("confirmed") is True
        and len(enabled_refs) == 1
        and enabled_refs[0].get("packId") == "platform-commerce"
        and isinstance(enabled_refs[0].get("fingerprint"), str)
        and enabled.get("receipt", {}).get("type") == "domain-pack-configuration"
        and status.get("workspace", {}).get("enabledDomainPacks", [{}])[0].get("packId") == "platform-commerce",
        enabled,
    )

    created = run(["workspace-create", "--name", "Neutral Lab", "--yes"], env)
    neutral = run(["domain-packs"], env)
    check(
        "workspace-pack-state-is-isolated",
        created.get("confirmed") is True and neutral.get("enabledDomainPacks") == [],
        {"created": created, "neutral": neutral},
    )

    disabled = run([
        "domain-pack-set", "--workspace", "default", "--pack", "platform-commerce", "--state", "disabled", "--yes"
    ], env)
    default_after_disable = run(["domain-packs", "--workspace", "default"], env)
    check(
        "confirmed-disable-removes-runtime-injection-without-deleting-manifest",
        disabled.get("confirmed") is True
        and default_after_disable.get("enabledDomainPacks") == []
        and len(default_after_disable.get("availableDomainPacks", [])) == 2,
        disabled,
    )

    unknown = run(["domain-pack-set", "--pack", "unknown-pack", "--state", "enabled", "--yes"], env)
    check(
        "unknown-pack-is-blocked-before-write",
        unknown.get("ok") is False and "Unknown Domain Pack" in str(unknown.get("error")),
        unknown,
    )

failed = [item for item in CHECKS if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-domain-pack-verify/v1",
    "generatedBy": "scripts/verify-domain-packs.py",
    "checks": CHECKS,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
