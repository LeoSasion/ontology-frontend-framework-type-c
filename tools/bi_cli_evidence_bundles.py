from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from bi_cli_core import ROOT, now_iso, slug


EVIDENCE_BUNDLE_SCHEMA = "aibi-evidence-bundle/v1"


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _bounded(value: Any, *, max_chars: int = 120_000) -> Any:
    safe_value = _json_safe(value)
    text = json.dumps(safe_value, ensure_ascii=False, sort_keys=True)
    if len(text) <= max_chars:
        return safe_value
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    return {
        "truncated": True,
        "sha1": digest,
        "originalChars": len(text),
        "preview": text[: max_chars // 2],
    }


def _default_bundle_dir(command: str, bundle_key: str) -> Path:
    return ROOT / "data" / "local" / "evidence-bundles" / slug(command) / bundle_key


def artifact_ref(label: str, path: str | Path, *, kind: str = "file", role: str = "evidence") -> dict[str, Any]:
    artifact_path = Path(path)
    return {
        "label": label,
        "kind": kind,
        "role": role,
        "path": str(artifact_path),
        "exists": artifact_path.exists(),
        "sizeBytes": artifact_path.stat().st_size if artifact_path.exists() and artifact_path.is_file() else None,
    }


def write_evidence_bundle(
    *,
    command: str,
    workspace_id: str,
    title: str,
    status: str,
    summary: dict[str, Any],
    payload: dict[str, Any],
    artifacts: list[dict[str, Any]] | None = None,
    bundle_dir: str | Path | None = None,
) -> dict[str, Any]:
    fingerprint_source = {
        "command": command,
        "workspaceId": workspace_id,
        "title": title,
        "status": status,
        "summary": _bounded(summary, max_chars=20_000),
        "timeNs": time.time_ns(),
    }
    fingerprint = hashlib.sha1(json.dumps(fingerprint_source, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:12]
    bundle_key = f"{slug(command)}-{fingerprint}"
    root = Path(bundle_dir) if bundle_dir else _default_bundle_dir(command, bundle_key)
    artifacts_dir = root / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    payload_path = artifacts_dir / "payload.json"
    bounded_payload = _bounded(payload)
    payload_path.write_text(json.dumps(bounded_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    artifact_items = list(artifacts or [])
    artifact_items.append(artifact_ref("bounded-payload", payload_path, kind="json", role="bounded-command-payload"))

    generated_at = now_iso()
    summary_payload = {
        "schema": EVIDENCE_BUNDLE_SCHEMA,
        "bundleKey": bundle_key,
        "title": title,
        "status": status,
        "command": command,
        "workspaceId": workspace_id,
        "generatedAt": generated_at,
        **_json_safe(summary),
    }
    summary_path = root / "summary.json"
    summary_path.write_text(json.dumps(summary_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest_payload = {
        "schema": EVIDENCE_BUNDLE_SCHEMA,
        "bundleKey": bundle_key,
        "title": title,
        "status": status,
        "command": command,
        "workspaceId": workspace_id,
        "generatedAt": generated_at,
        "summaryPath": str(summary_path),
        "artifactsDir": str(artifacts_dir),
        "artifacts": artifact_items,
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "schema": EVIDENCE_BUNDLE_SCHEMA,
        "bundleKey": bundle_key,
        "bundleDir": str(root),
        "manifestPath": str(manifest_path),
        "summaryPath": str(summary_path),
        "artifactsDir": str(artifacts_dir),
        "artifactCount": len(artifact_items),
        "status": status,
    }
