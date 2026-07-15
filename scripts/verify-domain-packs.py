from __future__ import annotations

import json
import hashlib
import hmac
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


def write_external_pack(path: Path, version: str, secret: str, *, migration: bool = False) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "guide.md").write_text(f"# External pack {version}\n", encoding="utf-8")
    manifest: dict[str, object] = {
        "schema": "aibi-domain-pack/v1",
        "packId": "verified-external",
        "version": version,
        "displayName": {"zh": "签名外部包", "en": "Signed external pack"},
        "description": {"zh": "用于验证外部 SDK 生命周期。", "en": "Verifies the external SDK lifecycle."},
        "coreCompatibility": {"min": 1, "max": 1},
        "capabilities": ["agentKnowledge"],
        "source": {"publisher": "AIBI-C verifier", "reference": "urn:aibi-c:verified-external"},
        "artifacts": {"guide": "guide.md"},
        "conflicts": ["platform-commerce"],
        "uiContributions": [{
            "kind": "info-card",
            "title": {"zh": "外部知识", "en": "External knowledge"},
            "body": {"zh": "由签名静态包提供。", "en": "Provided by a signed static package."},
        }],
    }
    if migration:
        manifest["migrations"] = [{"from": "1.0.0", "to": version, "kind": "compatible"}]
    canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    manifest["signature"] = {
        "algorithm": "hmac-sha256",
        "keyId": "verify-key",
        "value": hmac.new(secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest(),
    }
    (path / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


with tempfile.TemporaryDirectory(prefix="aibi-c-domain-packs-") as temp_dir:
    env = os.environ.copy()
    env["AIBI_HYBRID_DB_PATH"] = str(Path(temp_dir) / "metadata.sqlite")
    env["AIBI_HYBRID_DUCKDB_PATH"] = str(Path(temp_dir) / "analytics.duckdb")
    env["AIBI_DOMAIN_PACK_ROOT"] = str(Path(temp_dir) / "installed-packs")
    trust_secret = "verify-domain-pack-secret"
    env["AIBI_DOMAIN_PACK_TRUST_KEYS"] = json.dumps({"verify-key": trust_secret})

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

    package_v1 = Path(temp_dir) / "package-v1"
    package_v2 = Path(temp_dir) / "package-v2"
    write_external_pack(package_v1, "1.0.0", trust_secret)
    write_external_pack(package_v2, "1.1.0", trust_secret, migration=True)
    linted = run(["domain-pack-lint", "--package", str(package_v1)], env)
    install_preview = run(["domain-pack-install", "--package", str(package_v1)], env)
    installed = run(["domain-pack-install", "--package", str(package_v1), "--yes"], env)
    check(
        "signed-static-package-lints-and-installs-with-confirmation",
        linted.get("ok") is True
        and linted.get("manifest", {}).get("signature", {}).get("verified") == "true"
        and install_preview.get("requiresConfirmation") is True
        and installed.get("confirmed") is True
        and installed.get("installedDomainPack", {}).get("builtIn") is False,
        {"lint": linted, "preview": install_preview, "installed": installed},
    )
    run(["domain-pack-set", "--workspace", "default", "--pack", "platform-commerce", "--state", "enabled", "--yes"], env)
    conflict = run(["domain-pack-set", "--workspace", "default", "--pack", "verified-external", "--state", "enabled", "--yes"], env)
    check(
        "external-pack-conflicts-are-enforced-before-write",
        conflict.get("ok") is False and "conflicts with enabled packs" in str(conflict.get("error")),
        conflict,
    )
    run(["domain-pack-set", "--workspace", "default", "--pack", "platform-commerce", "--state", "disabled", "--yes"], env)
    external_enabled = run(["domain-pack-set", "--workspace", "default", "--pack", "verified-external", "--state", "enabled", "--yes"], env)
    upgraded = run(["domain-pack-install", "--package", str(package_v2), "--yes"], env)
    after_upgrade = run(["domain-packs", "--workspace", "default"], env)
    check(
        "declared-compatible-upgrade-preserves-workspace-enablement",
        external_enabled.get("confirmed") is True
        and upgraded.get("change", {}).get("operation") == "upgrade"
        and upgraded.get("change", {}).get("preserveWorkspaceEnablement") is True
        and after_upgrade.get("enabledDomainPacks", [{}])[0].get("version") == "1.1.0"
        and after_upgrade.get("availableDomainPacks", [])[-1].get("uiContributions", [{}])[0].get("kind") == "info-card",
        {"upgrade": upgraded, "runtime": after_upgrade},
    )
    run(["domain-pack-set", "--workspace", "default", "--pack", "verified-external", "--state", "disabled", "--yes"], env)
    uninstall_preview = run(["domain-pack-uninstall", "--pack", "verified-external"], env)
    uninstalled = run(["domain-pack-uninstall", "--pack", "verified-external", "--yes"], env)
    final_runtime = run(["domain-packs", "--workspace", "default"], env)
    check(
        "disabled-external-pack-uninstalls-and-preserves-lifecycle-receipt",
        uninstall_preview.get("requiresConfirmation") is True
        and uninstalled.get("confirmed") is True
        and all(item.get("packId") != "verified-external" for item in final_runtime.get("availableDomainPacks", []))
        and (Path(env["AIBI_DOMAIN_PACK_ROOT"]) / "lifecycle-receipts.jsonl").is_file(),
        {"preview": uninstall_preview, "uninstalled": uninstalled},
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
