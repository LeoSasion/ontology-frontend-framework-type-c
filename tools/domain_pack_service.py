from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import tempfile
from typing import Any, Callable

from bi_cli_core import ROOT, now_iso


DOMAIN_PACK_SCHEMA = "aibi-domain-pack/v1"
DOMAIN_PACK_RUNTIME_SCHEMA = "aibi-domain-pack-runtime/v1"
CORE_DOMAIN_API_VERSION = 1
PACK_ROOT = ROOT / "domain-packs"
PACK_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{1,63}$")
VERSION_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
ALLOWED_CAPABILITIES = {
    "agentKnowledge",
    "dashboardUnits",
    "relationshipHints",
    "sourceIntelligence",
}
EXTERNAL_STATIC_SUFFIXES = {".json", ".md", ".txt", ".csv", ".yaml", ".yml"}
FORBIDDEN_REPOSITORY_PARTS = {"aibi-a", "aibi-b", "aibi-d", "aibi-e", "aibi项目杂交"}
MAX_EXTERNAL_PACKAGE_FILES = 64
MAX_EXTERNAL_PACKAGE_BYTES = 5 * 1024 * 1024


def installed_pack_root() -> Path:
    configured = str(os.environ.get("AIBI_DOMAIN_PACK_ROOT") or "").strip()
    return Path(configured).expanduser().resolve() if configured else (ROOT / "data" / "domain-packs").resolve()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _manifest_fingerprint(manifest: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(manifest).encode("utf-8")).hexdigest()


def _localized_text(value: Any, field: str) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ValueError(f"Domain Pack {field} must contain zh and en text.")
    zh = str(value.get("zh") or "").strip()
    en = str(value.get("en") or "").strip()
    if not zh or not en:
        raise ValueError(f"Domain Pack {field} must contain non-empty zh and en text.")
    return {"zh": zh, "en": en}


def _artifact_paths(value: Any, manifest_path: Path, package_root: Path, *, external: bool) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Domain Pack artifacts must be an object: {manifest_path.name}")
    artifacts: dict[str, str] = {}
    root = package_root.resolve()
    for key, raw_path in value.items():
        artifact_key = str(key).strip()
        relative = Path(str(raw_path).strip())
        if not artifact_key or not str(relative) or relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Unsafe Domain Pack artifact path in {manifest_path.name}: {raw_path}")
        resolved = (root / relative).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as error:
            raise ValueError(f"Domain Pack artifact escapes its package root: {raw_path}") from error
        if not resolved.is_file():
            raise ValueError(f"Domain Pack artifact does not exist: {raw_path}")
        if external and resolved.suffix.casefold() not in EXTERNAL_STATIC_SUFFIXES:
            raise ValueError(f"External Domain Pack artifacts must be static data or text: {raw_path}")
        artifacts[artifact_key] = relative.as_posix()
    return artifacts


def _ui_contributions(value: Any, manifest_path: Path) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 12:
        raise ValueError(f"Domain Pack uiContributions must be a bounded list: {manifest_path.name}")
    normalized: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict) or item.get("kind") not in {"info-card", "help-link"}:
            raise ValueError(f"Unsupported Domain Pack UI contribution: {manifest_path.name}")
        contribution = {
            "kind": str(item["kind"]),
            "title": _localized_text(item.get("title"), "uiContributions.title"),
            "body": _localized_text(item.get("body"), "uiContributions.body"),
        }
        if item.get("href") is not None:
            href = str(item.get("href") or "").strip()
            if not href.startswith(("https://", "http://127.0.0.1", "http://localhost")):
                raise ValueError(f"Domain Pack help link must use HTTPS or loopback HTTP: {manifest_path.name}")
            contribution["href"] = href
        normalized.append(contribution)
    return normalized


def _versioned_links(value: Any, field: str, manifest_path: Path) -> list[dict[str, str]]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 32:
        raise ValueError(f"Domain Pack {field} must be a bounded list: {manifest_path.name}")
    normalized: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"Invalid Domain Pack {field}: {manifest_path.name}")
        source = str(item.get("from") or "").strip()
        target = str(item.get("to") or "").strip()
        kind = str(item.get("kind") or "compatible").strip()
        if not VERSION_PATTERN.fullmatch(source) or not VERSION_PATTERN.fullmatch(target) or kind not in {"compatible", "breaking"}:
            raise ValueError(f"Invalid Domain Pack {field} entry: {manifest_path.name}")
        normalized.append({"from": source, "to": target, "kind": kind})
    return normalized


def _contributions(value: Any, manifest_path: Path) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Domain Pack contributions must be an object: {manifest_path.name}")
    aliases = value.get("semanticAliases") or {}
    roles = value.get("semanticRoles") or {}
    source_intelligence = value.get("sourceIntelligence") or {}
    if not isinstance(aliases, dict) or not isinstance(roles, dict) or not isinstance(source_intelligence, dict):
        raise ValueError(f"Invalid Domain Pack contribution shape: {manifest_path.name}")
    normalized_aliases: dict[str, list[str]] = {}
    for semantic, items in aliases.items():
        if not isinstance(items, list) or not all(isinstance(item, str) and item.strip() for item in items):
            raise ValueError(f"Invalid semantic aliases in {manifest_path.name}: {semantic}")
        normalized_aliases[str(semantic)] = sorted(set(item.strip() for item in items))
    normalized_roles: dict[str, list[str]] = {}
    for role, items in roles.items():
        if role not in {"identity", "measure", "time", "dimension", "attribute"}:
            raise ValueError(f"Invalid semantic role in {manifest_path.name}: {role}")
        if not isinstance(items, list) or not all(isinstance(item, str) and item.strip() for item in items):
            raise ValueError(f"Invalid semantic role members in {manifest_path.name}: {role}")
        normalized_roles[str(role)] = sorted(set(item.strip() for item in items))
    blocked = source_intelligence.get("blockedRequirements") or []
    if not isinstance(blocked, list):
        raise ValueError(f"Invalid blocked requirements in {manifest_path.name}")
    normalized_blocked: list[dict[str, Any]] = []
    for item in blocked:
        if not isinstance(item, dict):
            raise ValueError(f"Invalid blocked requirement in {manifest_path.name}")
        analysis_id = str(item.get("analysisId") or "").strip()
        label = str(item.get("label") or "").strip()
        required = item.get("required") or []
        if not PACK_ID_PATTERN.fullmatch(analysis_id.replace("_", "-")) or not label or not isinstance(required, list):
            raise ValueError(f"Invalid blocked requirement in {manifest_path.name}: {analysis_id}")
        normalized_blocked.append({
            "analysisId": analysis_id,
            "label": label,
            "required": [str(value).strip() for value in required if str(value).strip()],
        })
    return {
        "semanticAliases": normalized_aliases,
        "semanticRoles": normalized_roles,
        "sourceIntelligence": {"blockedRequirements": normalized_blocked},
    }


def validate_domain_pack_manifest(
    raw: Any,
    manifest_path: Path,
    *,
    package_root: Path | None = None,
    source_type: str = "builtin",
) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"Domain Pack manifest must be an object: {manifest_path.name}")
    allowed_fields = {
        "schema", "packId", "version", "displayName", "description", "coreCompatibility", "capabilities",
        "artifacts", "contributions", "uiContributions", "conflicts", "migrations", "signature", "source",
    }
    unknown_fields = sorted(set(raw) - allowed_fields)
    if unknown_fields:
        raise ValueError(f"Unknown Domain Pack manifest fields in {manifest_path.name}: {', '.join(unknown_fields)}")
    if raw.get("schema") != DOMAIN_PACK_SCHEMA:
        raise ValueError(f"Unsupported Domain Pack schema in {manifest_path.name}: {raw.get('schema')}")
    pack_id = str(raw.get("packId") or "").strip()
    version = str(raw.get("version") or "").strip()
    if not PACK_ID_PATTERN.fullmatch(pack_id):
        raise ValueError(f"Invalid Domain Pack id in {manifest_path.name}: {pack_id}")
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"Invalid Domain Pack version in {manifest_path.name}: {version}")
    compatibility = raw.get("coreCompatibility")
    if not isinstance(compatibility, dict):
        raise ValueError(f"Domain Pack coreCompatibility is required: {manifest_path.name}")
    minimum = int(compatibility.get("min") or 0)
    maximum = int(compatibility.get("max") or 0)
    if minimum < 1 or maximum < minimum:
        raise ValueError(f"Invalid Domain Pack coreCompatibility: {manifest_path.name}")
    capabilities = sorted({str(item) for item in raw.get("capabilities") or []})
    unknown_capabilities = sorted(set(capabilities) - ALLOWED_CAPABILITIES)
    if not capabilities or unknown_capabilities:
        raise ValueError(
            f"Invalid Domain Pack capabilities in {manifest_path.name}: {unknown_capabilities or capabilities}"
        )
    package_root = (package_root or ROOT).resolve()
    external = source_type == "external"
    raw_source = raw.get("source") if isinstance(raw.get("source"), dict) else {}
    publisher = str(raw_source.get("publisher") or ("AIBI-C" if not external else "")).strip()
    reference = str(raw_source.get("reference") or (manifest_path.name if not external else "")).strip()
    if external and (not publisher or not reference.startswith(("https://", "urn:"))):
        raise ValueError(f"External Domain Pack source requires publisher and HTTPS or URN reference: {manifest_path.name}")
    conflicts = sorted({str(item).strip() for item in raw.get("conflicts") or [] if str(item).strip()})
    if any(not PACK_ID_PATTERN.fullmatch(item) or item == pack_id for item in conflicts):
        raise ValueError(f"Invalid Domain Pack conflicts in {manifest_path.name}")
    manifest = {
        "schema": DOMAIN_PACK_SCHEMA,
        "packId": pack_id,
        "version": version,
        "displayName": _localized_text(raw.get("displayName"), "displayName"),
        "description": _localized_text(raw.get("description"), "description"),
        "coreCompatibility": {"min": minimum, "max": maximum},
        "capabilities": capabilities,
        "artifacts": _artifact_paths(raw.get("artifacts"), manifest_path, package_root, external=external),
        "contributions": _contributions(raw.get("contributions"), manifest_path),
        "uiContributions": _ui_contributions(raw.get("uiContributions"), manifest_path),
        "conflicts": conflicts,
        "migrations": _versioned_links(raw.get("migrations"), "migrations", manifest_path),
        "source": {"type": source_type, "publisher": publisher, "reference": reference},
        "builtIn": not external,
        "manifestPath": manifest_path.name if external else manifest_path.relative_to(ROOT).as_posix(),
    }
    manifest["compatible"] = minimum <= CORE_DOMAIN_API_VERSION <= maximum
    manifest["fingerprint"] = _manifest_fingerprint({key: value for key, value in manifest.items() if key != "fingerprint"})
    return manifest


def _external_trust_keys() -> dict[str, str]:
    raw = str(os.environ.get("AIBI_DOMAIN_PACK_TRUST_KEYS") or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("AIBI_DOMAIN_PACK_TRUST_KEYS must be a JSON object.") from error
    if not isinstance(parsed, dict):
        raise ValueError("AIBI_DOMAIN_PACK_TRUST_KEYS must be a JSON object.")
    return {str(key): str(value) for key, value in parsed.items() if str(key) and str(value)}


def _validate_external_signature(raw: dict[str, Any], manifest_path: Path) -> dict[str, str]:
    signature = raw.get("signature")
    if not isinstance(signature, dict) or signature.get("algorithm") != "hmac-sha256":
        raise ValueError(f"External Domain Pack requires an hmac-sha256 signature: {manifest_path.name}")
    key_id = str(signature.get("keyId") or "").strip()
    supplied = str(signature.get("value") or "").strip().casefold()
    secret = _external_trust_keys().get(key_id)
    if not secret:
        raise ValueError(f"External Domain Pack signature key is not trusted: {key_id or '-'}")
    unsigned = {key: value for key, value in raw.items() if key != "signature"}
    expected = hmac.new(secret.encode("utf-8"), _canonical_json(unsigned).encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied, expected):
        raise ValueError(f"External Domain Pack signature verification failed: {manifest_path.name}")
    return {"algorithm": "hmac-sha256", "keyId": key_id, "verified": "true"}


def _validate_external_package(package_path: Path) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    candidate = package_path.expanduser()
    candidate = candidate if candidate.is_absolute() else (ROOT / candidate)
    resolved = candidate.resolve()
    forbidden = {part.casefold() for part in resolved.parts}.intersection(FORBIDDEN_REPOSITORY_PARTS)
    if forbidden:
        raise ValueError(f"Domain Pack package belongs to a forbidden AIBI repository boundary: {sorted(forbidden)[0]}")
    if not resolved.is_dir():
        raise ValueError("External Domain Pack package must be a directory containing manifest.json.")
    files = sorted(path for path in resolved.rglob("*") if path.is_file())
    if not files or len(files) > MAX_EXTERNAL_PACKAGE_FILES:
        raise ValueError(f"External Domain Pack package must contain 1-{MAX_EXTERNAL_PACKAGE_FILES} files.")
    total_bytes = 0
    for path in files:
        if path.is_symlink() or path.suffix.casefold() not in EXTERNAL_STATIC_SUFFIXES:
            raise ValueError(f"External Domain Pack contains a forbidden executable or link: {path.name}")
        total_bytes += path.stat().st_size
    if total_bytes > MAX_EXTERNAL_PACKAGE_BYTES:
        raise ValueError(f"External Domain Pack exceeds {MAX_EXTERNAL_PACKAGE_BYTES} bytes.")
    manifest_path = resolved / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError("External Domain Pack package is missing manifest.json.")
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("External Domain Pack manifest must be an object.")
    signature = _validate_external_signature(raw, manifest_path)
    manifest = validate_domain_pack_manifest(raw, manifest_path, package_root=resolved, source_type="external")
    manifest["signature"] = signature
    manifest["packageFileCount"] = len(files)
    manifest["packageBytes"] = total_bytes
    return manifest, resolved, raw


def discover_domain_packs() -> list[dict[str, Any]]:
    discovered: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for manifest_path in sorted(PACK_ROOT.glob("*.json")) if PACK_ROOT.is_dir() else []:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = validate_domain_pack_manifest(raw, manifest_path)
        if manifest["packId"] in seen_ids:
            raise ValueError(f"Duplicate Domain Pack id: {manifest['packId']}")
        seen_ids.add(manifest["packId"])
        discovered.append(manifest)
    external_root = installed_pack_root()
    for manifest_path in sorted(external_root.glob("*/manifest.json")) if external_root.is_dir() else []:
        manifest, _root, _raw = _validate_external_package(manifest_path.parent)
        if manifest["packId"] in seen_ids:
            raise ValueError(f"External Domain Pack conflicts with an installed or built-in id: {manifest['packId']}")
        seen_ids.add(manifest["packId"])
        discovered.append(manifest)
    return sorted(discovered, key=lambda item: (item["packId"], item["version"]))


def _enabled_rows(connection: sqlite3.Connection, workspace_id: str) -> dict[str, dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT pack_id, version, enabled, enabled_at, updated_at
        FROM workspace_domain_packs
        WHERE workspace_id = ?
        ORDER BY pack_id
        """,
        (workspace_id,),
    ).fetchall()
    return {str(row["pack_id"]): dict(row) for row in rows}


def domain_pack_runtime_context(connection: sqlite3.Connection, workspace_id: str) -> dict[str, Any]:
    manifests = discover_domain_packs()
    state = _enabled_rows(connection, workspace_id)
    available: list[dict[str, Any]] = []
    enabled: list[dict[str, Any]] = []
    for manifest in manifests:
        row = state.get(manifest["packId"])
        is_enabled = bool(row and row["enabled"] and row["version"] == manifest["version"] and manifest["compatible"])
        item = {
            **manifest,
            "enabled": is_enabled,
            "configuredVersion": str(row["version"]) if row else None,
            "enabledAt": row["enabled_at"] if row else None,
            "updatedAt": row["updated_at"] if row else None,
        }
        available.append(item)
        if is_enabled:
            enabled.append({
                "packId": manifest["packId"],
                "version": manifest["version"],
                "fingerprint": manifest["fingerprint"],
                "capabilities": manifest["capabilities"],
            })
    return {
        "schema": DOMAIN_PACK_RUNTIME_SCHEMA,
        "coreApiVersion": CORE_DOMAIN_API_VERSION,
        "workspaceId": workspace_id,
        "enabledDomainPacks": enabled,
        "availableDomainPacks": available,
    }


def domain_pack_set_fingerprint(runtime: dict[str, Any]) -> str:
    enabled = [
        {
            "packId": str(item.get("packId") or ""),
            "version": str(item.get("version") or ""),
            "fingerprint": str(item.get("fingerprint") or ""),
        }
        for item in runtime.get("enabledDomainPacks", [])
        if isinstance(item, dict)
    ]
    material = json.dumps(sorted(enabled, key=lambda item: item["packId"]), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def is_domain_pack_enabled(
    connection: sqlite3.Connection,
    workspace_id: str,
    pack_id: str,
    capability: str | None = None,
) -> bool:
    runtime = domain_pack_runtime_context(connection, workspace_id)
    for item in runtime["enabledDomainPacks"]:
        if item["packId"] != pack_id:
            continue
        return capability is None or capability in item["capabilities"]
    return False


def _version_tuple(value: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in value.split("."))  # type: ignore[return-value]


def _write_sdk_receipt(receipt: dict[str, Any]) -> None:
    root = installed_pack_root()
    root.mkdir(parents=True, exist_ok=True)
    with (root / "lifecycle-receipts.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(_canonical_json(receipt) + "\n")


def domain_pack_lint_command(args: argparse.Namespace) -> dict[str, Any]:
    manifest, package_root, _raw = _validate_external_package(Path(str(args.package)))
    return {
        "ok": True,
        "operation": "domain-pack-lint",
        "readOnly": True,
        "package": {"label": package_root.name, "fileCount": manifest["packageFileCount"], "bytes": manifest["packageBytes"]},
        "manifest": manifest,
    }


def domain_pack_install_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
) -> dict[str, Any]:
    manifest, source_root, _raw = _validate_external_package(Path(str(args.package)))
    pack_id = str(manifest["packId"])
    builtins = {item["packId"]: item for item in discover_domain_packs() if item.get("builtIn")}
    if pack_id in builtins:
        raise ValueError(f"External Domain Pack cannot replace built-in pack: {pack_id}")
    destination = installed_pack_root() / pack_id
    current: dict[str, Any] | None = None
    if destination.is_dir():
        current, _current_root, _current_raw = _validate_external_package(destination)
        if current["packId"] != pack_id:
            raise ValueError(f"Installed Domain Pack directory identity mismatch: {pack_id}")
        if _version_tuple(manifest["version"]) < _version_tuple(current["version"]):
            raise ValueError(f"Domain Pack downgrade is forbidden: {current['version']} -> {manifest['version']}")
    migration = next(
        (
            item for item in manifest.get("migrations", [])
            if current and item.get("from") == current.get("version") and item.get("to") == manifest.get("version")
        ),
        None,
    )
    preserve_enablement = current is None or current["version"] == manifest["version"] or bool(migration and migration.get("kind") == "compatible")
    change = {
        "operation": "install" if current is None else "upgrade",
        "packId": pack_id,
        "fromVersion": current.get("version") if current else None,
        "toVersion": manifest["version"],
        "source": source_root.name,
        "signature": manifest["signature"],
        "preserveWorkspaceEnablement": preserve_enablement,
    }
    if not args.yes:
        return {
            "ok": True,
            "dryRun": True,
            "requiresConfirmation": True,
            "change": change,
            "impact": {
                "coreFilesModified": False,
                "executableCodeAccepted": False,
                "workspaceEnablementWillBeDisabled": bool(current and not preserve_enablement),
            },
        }
    install_root = installed_pack_root()
    install_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{pack_id}-", dir=install_root))
    backup = install_root / f".{pack_id}-backup"
    timestamp = now_iso()
    try:
        shutil.rmtree(staging)
        shutil.copytree(source_root, staging)
        staged_manifest, _staged_root, _staged_raw = _validate_external_package(staging)
        if staged_manifest["fingerprint"] != manifest["fingerprint"]:
            raise ValueError("Domain Pack changed while it was being installed.")
        if backup.exists():
            shutil.rmtree(backup)
        if destination.exists():
            destination.rename(backup)
        staging.rename(destination)
        shutil.rmtree(backup, ignore_errors=True)
        if current and not preserve_enablement:
            with open_db() as connection:
                connection.execute(
                    "UPDATE workspace_domain_packs SET enabled = 0, version = ?, updated_at = ? WHERE pack_id = ?",
                    (manifest["version"], timestamp, pack_id),
                )
                connection.commit()
        elif current:
            with open_db() as connection:
                connection.execute(
                    "UPDATE workspace_domain_packs SET version = ?, updated_at = ? WHERE pack_id = ?",
                    (manifest["version"], timestamp, pack_id),
                )
                connection.commit()
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        if backup.exists() and not destination.exists():
            backup.rename(destination)
        raise
    receipt = {"type": "domain-pack-lifecycle", **change, "confirmed": True, "updatedAt": timestamp}
    _write_sdk_receipt(receipt)
    return {"ok": True, "confirmed": True, "change": change, "receipt": receipt, "installedDomainPack": manifest}


def domain_pack_uninstall_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
) -> dict[str, Any]:
    pack_id = str(args.pack or "").strip()
    manifest = next((item for item in discover_domain_packs() if item["packId"] == pack_id), None)
    if not manifest:
        raise ValueError(f"Unknown Domain Pack: {pack_id}")
    if manifest.get("builtIn"):
        raise ValueError(f"Built-in Domain Pack cannot be uninstalled: {pack_id}")
    with open_db() as connection:
        enabled_workspaces = [
            str(row["workspace_id"])
            for row in connection.execute(
                "SELECT workspace_id FROM workspace_domain_packs WHERE pack_id = ? AND enabled = 1 ORDER BY workspace_id",
                (pack_id,),
            ).fetchall()
        ]
    change = {
        "operation": "uninstall",
        "packId": pack_id,
        "version": manifest["version"],
        "disableWorkspaceCount": len(enabled_workspaces),
    }
    if not args.yes:
        return {
            "ok": True,
            "dryRun": True,
            "requiresConfirmation": True,
            "change": change,
            "impact": {"workspaceEnablementWillBeDisabled": bool(enabled_workspaces), "historicalReceiptsPreserved": True},
        }
    timestamp = now_iso()
    with open_db() as connection:
        connection.execute(
            "UPDATE workspace_domain_packs SET enabled = 0, updated_at = ? WHERE pack_id = ?",
            (timestamp, pack_id),
        )
        connection.commit()
    destination = installed_pack_root() / pack_id
    if destination.is_dir():
        shutil.rmtree(destination)
    receipt = {"type": "domain-pack-lifecycle", **change, "confirmed": True, "updatedAt": timestamp}
    _write_sdk_receipt(receipt)
    return {"ok": True, "confirmed": True, "change": change, "receipt": receipt}


def domain_packs_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = str(args.workspace or "").strip() or active_workspace_id(connection)
        if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
            raise ValueError(f"Unknown workspace: {workspace_id}")
        return {"ok": True, **domain_pack_runtime_context(connection, workspace_id)}


def domain_pack_set_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    manifests = {item["packId"]: item for item in discover_domain_packs()}
    pack_id = str(args.pack or "").strip()
    manifest = manifests.get(pack_id)
    if not manifest:
        raise ValueError(f"Unknown Domain Pack: {pack_id}")
    if not manifest["compatible"]:
        raise ValueError(f"Domain Pack is incompatible with Core API v{CORE_DOMAIN_API_VERSION}: {pack_id}")
    target_enabled = args.state == "enabled"
    with open_db() as connection:
        workspace_id = str(args.workspace or "").strip() or active_workspace_id(connection)
        if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
            raise ValueError(f"Unknown workspace: {workspace_id}")
        current = _enabled_rows(connection, workspace_id).get(pack_id)
        current_enabled = bool(current and current["enabled"] and current["version"] == manifest["version"])
        if target_enabled:
            enabled_ids = {
                item["packId"] for item in domain_pack_runtime_context(connection, workspace_id)["enabledDomainPacks"]
                if item["packId"] != pack_id
            }
            direct_conflicts = enabled_ids.intersection(set(manifest.get("conflicts") or []))
            reverse_conflicts = {
                item["packId"]
                for item in manifests.values()
                if item["packId"] in enabled_ids and pack_id in set(item.get("conflicts") or [])
            }
            conflicts = sorted(direct_conflicts | reverse_conflicts)
            if conflicts:
                raise ValueError(f"Domain Pack conflicts with enabled packs: {', '.join(conflicts)}")
        change = {
            "workspaceId": workspace_id,
            "packId": pack_id,
            "version": manifest["version"],
            "from": "enabled" if current_enabled else "disabled",
            "to": args.state,
            "capabilities": manifest["capabilities"],
            "fingerprint": manifest["fingerprint"],
        }
        if not args.yes:
            return {
                "ok": True,
                "dryRun": True,
                "requiresConfirmation": True,
                "change": change,
                "impact": {
                    "newPlansOnly": True,
                    "historicalResultsReinterpreted": False,
                    "dependentObjectsRequireReviewOnDisable": not target_enabled,
                },
            }
        timestamp = now_iso()
        enabled_at = timestamp if target_enabled else (current["enabled_at"] if current else None)
        connection.execute(
            """
            INSERT INTO workspace_domain_packs(workspace_id, pack_id, version, enabled, enabled_at, updated_at)
            VALUES(?, ?, ?, ?, ?, ?)
            ON CONFLICT(workspace_id, pack_id) DO UPDATE SET
              version = excluded.version,
              enabled = excluded.enabled,
              enabled_at = excluded.enabled_at,
              updated_at = excluded.updated_at
            """,
            (workspace_id, pack_id, manifest["version"], 1 if target_enabled else 0, enabled_at, timestamp),
        )
        connection.commit()
        runtime = domain_pack_runtime_context(connection, workspace_id)
    return {
        "ok": True,
        "confirmed": True,
        "change": change,
        "receipt": {
            "type": "domain-pack-configuration",
            "workspaceId": workspace_id,
            "packId": pack_id,
            "version": manifest["version"],
            "state": args.state,
            "updatedAt": timestamp,
        },
        **runtime,
    }
