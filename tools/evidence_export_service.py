from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Callable

from query_plan_receipt_service import get_query_receipt


SENSITIVE_KEY_PARTS = {"password", "secret", "token", "credential", "api_key", "apikey"}


def _safe_value(value: Any, key: str = "") -> Any:
    key_folded = key.casefold()
    if any(part in key_folded for part in SENSITIVE_KEY_PARTS):
        return "[redacted]"
    if isinstance(value, dict):
        return {str(item_key): _safe_value(item, str(item_key)) for item_key, item in value.items()}
    if isinstance(value, list):
        return [_safe_value(item, key) for item in value]
    if isinstance(value, str):
        text = value.strip()
        if text and (Path(text).is_absolute() or (len(text) > 2 and text[1:3] in {":\\", ":/"})):
            return f"[local-path-redacted]/{Path(text).name}"
        return value
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return str(value)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_safe_value(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _answer_markdown(receipt: dict[str, Any]) -> str:
    source = receipt.get("source") if isinstance(receipt.get("source"), dict) else {}
    selection = receipt.get("selection") if isinstance(receipt.get("selection"), dict) else {}
    runtime = receipt.get("runtime") if isinstance(receipt.get("runtime"), dict) else {}
    unresolved = receipt.get("unresolved") if isinstance(receipt.get("unresolved"), list) else []
    unresolved_text = "\n".join(f"- {json.dumps(_safe_value(item), ensure_ascii=False)}" for item in unresolved) or "- None"
    return "\n".join([
        "# AIBI-C Evidence-backed Result",
        "",
        f"- Request: {receipt.get('request', '')}",
        f"- Status: {receipt.get('status', '')}",
        f"- Source table: {source.get('tableKey') or '-'}",
        f"- Measure: {selection.get('measure') or '-'}",
        f"- Group: {selection.get('group') or '-'}",
        f"- Aggregation: {selection.get('aggregation') or '-'}",
        f"- Runtime: {runtime.get('engine') or '-'}",
        "",
        "## Unresolved",
        unresolved_text,
        "",
        "## Trust boundary",
        "The result uses a whitelist query plan. Source files remain read-only and business writes require confirmation.",
        "",
    ])


def export_evidence_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    root: Path,
    now_iso: Callable[[], str],
) -> dict[str, Any]:
    receipt_key = str(args.receipt or "").strip()
    if not receipt_key:
        raise ValueError("receipt is required")
    with open_db() as connection:
        workspace_id = active_workspace_id(connection)
        receipt = get_query_receipt(connection, workspace_id, receipt_key)
        if not receipt:
            raise ValueError(f"Unknown query receipt in active workspace: {receipt_key}")
        source = receipt.get("source") if isinstance(receipt.get("source"), dict) else {}
        table_key = str(source.get("tableKey") or "")
        registry = connection.execute(
            "SELECT table_key, display_name, source_file, row_count, column_count FROM table_registry WHERE workspace_id = ? AND table_key = ?",
            (workspace_id, table_key),
        ).fetchone() if table_key else None
        semantics = [
            dict(row)
            for row in connection.execute(
                """
                SELECT field_name, role, usage, confidence, tags_json, source, note, updated_at
                FROM field_semantics
                WHERE workspace_id = ? AND table_key = ?
                ORDER BY field_name
                """,
                (workspace_id, table_key),
            ).fetchall()
        ] if table_key else []
        action_key = str(receipt.get("actionKey") or "")
        action = connection.execute(
            "SELECT kind, label, status, payload_json, evidence_json, confirmed_at FROM action_drafts WHERE workspace_id = ? AND action_key = ?",
            (workspace_id, action_key),
        ).fetchone() if action_key else None

    export_root_value = str(os.environ.get("AIBI_EXPORT_ROOT") or "").strip()
    export_root = Path(export_root_value).expanduser() if export_root_value else root / "data" / "local" / "exports"
    export_root.mkdir(parents=True, exist_ok=True)
    archive_path = Path(str(args.output or "").strip()).expanduser() if str(args.output or "").strip() else export_root / f"aibi-result-{receipt_key}.zip"
    if archive_path.suffix.casefold() != ".zip":
        archive_path = archive_path.with_suffix(".zip")
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    staging = Path(tempfile.mkdtemp(prefix="aibi-evidence-export-", dir=export_root))
    try:
        _write_json(staging / "query-plan.json", receipt)
        (staging / "answer.md").write_text(_answer_markdown(receipt), encoding="utf-8")
        _write_json(staging / "evidence" / "source-summary.json", {
            "tableKey": registry["table_key"] if registry else table_key,
            "displayName": registry["display_name"] if registry else table_key,
            "sourceFile": Path(registry["source_file"]).name if registry else None,
            "rowCount": registry["row_count"] if registry else None,
            "columnCount": registry["column_count"] if registry else None,
            "schemaFingerprint": source.get("schemaFingerprint"),
        })
        _write_json(staging / "evidence" / "semantic-summary.json", {"tableKey": table_key, "fields": semantics})
        _write_json(staging / "evidence" / "quality-gaps.json", {
            "status": receipt.get("status"),
            "unresolved": receipt.get("unresolved", []),
            "validation": receipt.get("validation", {}),
        })
        if action:
            payload = json.loads(action["payload_json"])
            _write_json(staging / "chart-spec.json", {
                "actionKind": action["kind"],
                "actionLabel": action["label"],
                "actionStatus": action["status"],
                "confirmedAt": action["confirmed_at"],
                "chart": payload.get("options") if isinstance(payload, dict) else None,
                "evidenceRefs": json.loads(action["evidence_json"]),
            })
        (staging / "README.txt").write_text(
            "AIBI-C evidence export. Files are reconstructed from the stored query receipt and workspace metadata.\n"
            "No credentials, database files, unselected raw data, or private model reasoning are included.\n",
            encoding="utf-8",
        )
        files = sorted(path for path in staging.rglob("*") if path.is_file())
        manifest = {
            "schema": "aibi-evidence-export/v1",
            "generatedAt": now_iso(),
            "receiptKey": receipt_key,
            "workspace": hashlib.sha256(workspace_id.encode("utf-8")).hexdigest()[:16],
            "status": receipt.get("status"),
            "files": [
                {"path": path.relative_to(staging).as_posix(), "sizeBytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in files
            ],
            "exclusions": ["credentials", "database files", "unselected raw data", "private model reasoning", "absolute local paths"],
        }
        _write_json(staging / "manifest.json", manifest)
        with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(item for item in staging.rglob("*") if item.is_file()):
                archive.write(path, path.relative_to(staging).as_posix())
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    return {
        "ok": True,
        "evidenceExport": {
            "schema": "aibi-evidence-export/v1",
            "archivePath": str(archive_path),
            "receiptKey": receipt_key,
            "fileCount": len(manifest["files"]) + 1,
            "manifest": manifest,
        },
        "artifacts": [{"label": "evidence-export", "path": str(archive_path)}],
        "evidence": [{"type": "queryPlanReceipt", "receiptKey": receipt_key}],
    }
