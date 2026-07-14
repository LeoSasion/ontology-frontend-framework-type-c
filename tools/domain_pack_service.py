from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
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


def _artifact_paths(value: Any, manifest_path: Path) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError(f"Domain Pack artifacts must be an object: {manifest_path.name}")
    artifacts: dict[str, str] = {}
    root = ROOT.resolve()
    for key, raw_path in value.items():
        artifact_key = str(key).strip()
        relative = Path(str(raw_path).strip())
        if not artifact_key or not str(relative) or relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"Unsafe Domain Pack artifact path in {manifest_path.name}: {raw_path}")
        resolved = (ROOT / relative).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as error:
            raise ValueError(f"Domain Pack artifact escapes AIBI-C: {raw_path}") from error
        if not resolved.is_file():
            raise ValueError(f"Domain Pack artifact does not exist: {raw_path}")
        artifacts[artifact_key] = relative.as_posix()
    return artifacts


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


def validate_domain_pack_manifest(raw: Any, manifest_path: Path) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"Domain Pack manifest must be an object: {manifest_path.name}")
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
    manifest = {
        "schema": DOMAIN_PACK_SCHEMA,
        "packId": pack_id,
        "version": version,
        "displayName": _localized_text(raw.get("displayName"), "displayName"),
        "description": _localized_text(raw.get("description"), "description"),
        "coreCompatibility": {"min": minimum, "max": maximum},
        "capabilities": capabilities,
        "artifacts": _artifact_paths(raw.get("artifacts"), manifest_path),
        "contributions": _contributions(raw.get("contributions"), manifest_path),
        "manifestPath": manifest_path.relative_to(ROOT).as_posix(),
    }
    manifest["compatible"] = minimum <= CORE_DOMAIN_API_VERSION <= maximum
    manifest["fingerprint"] = _manifest_fingerprint({key: value for key, value in manifest.items() if key != "fingerprint"})
    return manifest


def discover_domain_packs() -> list[dict[str, Any]]:
    if not PACK_ROOT.is_dir():
        return []
    discovered: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for manifest_path in sorted(PACK_ROOT.glob("*.json")):
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = validate_domain_pack_manifest(raw, manifest_path)
        identity = (manifest["packId"], manifest["version"])
        if identity in seen:
            raise ValueError(f"Duplicate Domain Pack identity: {identity[0]}@{identity[1]}")
        seen.add(identity)
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
