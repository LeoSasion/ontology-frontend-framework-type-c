from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from import_policy import record_unique_key


ATOMIC_IMPORT_PLAN_SCHEMA = "aibi-atomic-import-plan/v1"
PII_FIELD_TOKENS = (
    "姓名", "手机", "电话", "地址", "邮箱", "email", "phone", "mobile",
    "身份证", "idcard", "收件人", "联系人", "buyer", "customer",
)


def _canonical_fingerprint(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def file_content_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def bind_single_import_plan(
    preview: dict[str, Any],
    path: Path,
    *,
    current_source_run_id: str | None,
) -> dict[str, Any]:
    """Bind a single-file preview to the exact bytes and workspace parent version."""
    resolved_path = path.resolve()
    merge_preview = preview.get("mergePolicyPreview") if isinstance(preview.get("mergePolicyPreview"), dict) else {}
    matched_table = preview.get("matchedTable") if isinstance(preview.get("matchedTable"), dict) else None
    commit_options = {
        "table": str((matched_table or {}).get("table_key") or preview.get("suggestedTableKey") or ""),
        "name": str((matched_table or {}).get("display_name") or preview.get("suggestedDisplayName") or ""),
        "mode": "merge" if matched_table else "create",
        "uniqueFields": list(merge_preview.get("uniqueFields") or []),
        "conflictRule": str(merge_preview.get("conflictRule") or "overwrite"),
    }
    fingerprint_material = {
        "schema": ATOMIC_IMPORT_PLAN_SCHEMA,
        "kind": "single-file",
        "workspaceId": str(preview.get("workspaceId") or ""),
        "file": resolved_path.as_posix(),
        "contentHash": file_content_hash(resolved_path),
        "parentSourceRunId": current_source_run_id,
        "commitOptions": commit_options,
        "schemaDecision": [
            {
                "field": field.get("field"),
                "role": field.get("role"),
                "inferredType": field.get("inferredType"),
            }
            for field in (preview.get("profile") or {}).get("fields") or []
            if isinstance(field, dict)
        ],
        "rowImpact": merge_preview.get("mergePlan"),
    }
    return {
        **preview,
        "schema": ATOMIC_IMPORT_PLAN_SCHEMA,
        "contentHash": fingerprint_material["contentHash"],
        "parentSourceRunId": current_source_run_id,
        "commitOptions": commit_options,
        "planFingerprint": _canonical_fingerprint(fingerprint_material),
    }


def _source_identity(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _pii_classification(headers: list[str]) -> dict[str, Any]:
    sensitive = [
        field for field in headers
        if any(token.casefold() in field.casefold() for token in PII_FIELD_TOKENS)
    ]
    return {
        "classification": "restricted" if sensitive else "internal",
        "sensitiveFields": sensitive,
        "requiresReview": bool(sensitive),
    }


def _key_quality_blockers(quality: dict[str, Any] | None) -> list[str]:
    if not isinstance(quality, dict):
        return ["unique-key-quality-missing"]
    blockers: list[str] = []
    if int(quality.get("emptyKeyRows") or 0) > 0:
        blockers.append("unique-key-has-empty-rows")
    if int(quality.get("partialEmptyKeyRows") or 0) > 0:
        blockers.append("unique-key-has-partial-empty-rows")
    if int(quality.get("duplicateRowsInFile") or 0) > 0:
        blockers.append("unique-key-has-in-file-duplicates")
    return blockers


def _cross_file_key_stats(
    items: list[dict[str, Any]],
    unique_fields: list[str],
    read_table_file: Callable[[Path], tuple[list[str], list[dict[str, Any]]]],
) -> dict[str, Any]:
    if not unique_fields:
        return {
            "uniqueFields": [],
            "distinctKeys": 0,
            "duplicateKeyCount": 0,
            "duplicateRowsAcrossFiles": 0,
            "emptyKeyRows": 0,
            "partialEmptyKeyRows": 0,
        }
    key_files: dict[str, set[str]] = {}
    key_counts: dict[str, int] = {}
    empty_rows = 0
    partial_empty_rows = 0
    for item in items:
        path = Path(str(item["absolutePath"]))
        _headers, rows = read_table_file(path)
        for row in rows:
            values = [str(row.get(field) or "").strip() for field in unique_fields]
            if not values or all(not value for value in values):
                empty_rows += 1
                continue
            if any(not value for value in values):
                partial_empty_rows += 1
            key = record_unique_key(row, unique_fields)
            if key is None:
                continue
            key_files.setdefault(key, set()).add(str(item["fileIdentity"]))
            key_counts[key] = key_counts.get(key, 0) + 1
    cross_file_keys = [key for key, files in key_files.items() if len(files) > 1]
    return {
        "uniqueFields": unique_fields,
        "distinctKeys": len(key_counts),
        "duplicateKeyCount": len(cross_file_keys),
        "duplicateRowsAcrossFiles": sum(key_counts[key] - 1 for key in cross_file_keys),
        "emptyKeyRows": empty_rows,
        "partialEmptyKeyRows": partial_empty_rows,
    }


def enrich_atomic_import_plan(
    base_plan: dict[str, Any],
    *,
    read_table_file: Callable[[Path], tuple[list[str], list[dict[str, Any]]]],
    current_source_run_id: str | None,
) -> dict[str, Any]:
    root = Path(str(base_plan["path"])).resolve()
    item_by_table: dict[str, list[dict[str, Any]]] = {}
    enriched_items: list[dict[str, Any]] = []
    for raw in base_plan.get("items") or []:
        item = dict(raw)
        path = Path(str(item["absolutePath"])).resolve()
        preview = item.pop("_preview", {}) if isinstance(item.get("_preview"), dict) else {}
        profile = preview.get("profile") if isinstance(preview.get("profile"), dict) else {}
        headers, _rows = read_table_file(path)
        saved_policy = (preview.get("mergePolicyPreview") or {}).get("savedPolicy")
        unique_fields = list(item.get("uniqueFields") or [])
        key_authority = (
            "owner_confirmed"
            if unique_fields and (str(item.get("keyAuthority") or "") == "owner_confirmed" or isinstance(saved_policy, dict))
            else "auto_candidate" if unique_fields else "not_required"
        )
        merge_plan = (preview.get("mergePolicyPreview") or {}).get("mergePlan")
        row_impact = dict(merge_plan) if isinstance(merge_plan, dict) else {
            "beforeRows": 0,
            "incomingRows": int(item.get("rowCount") or 0),
            "insertRows": int(item.get("rowCount") or 0),
            "updateRows": 0,
            "skipRows": 0,
            "afterRowsEstimate": int(item.get("rowCount") or 0),
        }
        item.update({
            "fileIdentity": _source_identity(path, root if root.is_dir() else root.parent),
            "contentHash": file_content_hash(path),
            "schemaDecision": {
                "headers": headers,
                "fieldProfiles": [
                    {
                        "field": field.get("field"),
                        "role": field.get("role"),
                        "inferredType": field.get("inferredType"),
                    }
                    for field in profile.get("fields") or []
                    if isinstance(field, dict)
                ],
            },
            "keyDecision": {
                "uniqueFields": unique_fields,
                "authority": key_authority,
                "quality": preview.get("uniqueKeyQuality"),
            },
            "conflictPolicy": str((preview.get("mergePolicyPreview") or {}).get("conflictRule") or "overwrite"),
            "rowImpact": row_impact,
            "pii": _pii_classification(headers),
        })
        enriched_items.append(item)
        item_by_table.setdefault(str(item["tableKey"]), []).append(item)

    enriched_groups: list[dict[str, Any]] = []
    plan_blockers: list[str] = []
    for raw_group in base_plan.get("groups") or []:
        group = dict(raw_group)
        group_items = item_by_table.get(str(group["tableKey"]), [])
        unique_fields = list(group.get("uniqueFields") or [])
        authorities = {str((item.get("keyDecision") or {}).get("authority") or "") for item in group_items}
        key_authority = "owner_confirmed" if authorities == {"owner_confirmed"} else "auto_candidate" if unique_fields else "not_required"
        cross_file = _cross_file_key_stats(group_items, unique_fields, read_table_file)
        group_blockers: list[str] = []
        if group.get("willMerge"):
            if not unique_fields:
                group_blockers.append("merge-requires-unique-key")
            elif key_authority != "owner_confirmed":
                group_blockers.append("merge-key-requires-owner-confirmation")
            for item in group_items:
                group_blockers.extend(_key_quality_blockers((item.get("keyDecision") or {}).get("quality")))
            if int(cross_file.get("emptyKeyRows") or 0) > 0:
                group_blockers.append("cross-file-key-has-empty-rows")
            if int(cross_file.get("partialEmptyKeyRows") or 0) > 0:
                group_blockers.append("cross-file-key-has-partial-empty-rows")
        group_blockers = list(dict.fromkeys(group_blockers))
        group.update({
            "keyDecision": {"uniqueFields": unique_fields, "authority": key_authority},
            "crossFileKeyQuality": cross_file,
            "pii": {
                "classification": "restricted" if any(item.get("pii", {}).get("classification") == "restricted" for item in group_items) else "internal",
                "requiresReview": any(item.get("pii", {}).get("requiresReview") is True for item in group_items),
            },
            "blockers": group_blockers,
            "ready": not group_blockers,
        })
        enriched_groups.append(group)
        plan_blockers.extend(f"{group['tableKey']}:{blocker}" for blocker in group_blockers)

    fingerprint_material = {
        "schema": ATOMIC_IMPORT_PLAN_SCHEMA,
        "workspaceId": str(base_plan.get("workspaceId") or ""),
        "path": root.as_posix(),
        "parentSourceRunId": current_source_run_id,
        "items": [
            {
                "fileIdentity": item["fileIdentity"],
                "contentHash": item["contentHash"],
                "tableKey": item["tableKey"],
                "mode": item["mode"],
                "schemaDecision": item["schemaDecision"],
                "keyDecision": item["keyDecision"],
                "conflictPolicy": item["conflictPolicy"],
                "rowImpact": item["rowImpact"],
                "pii": item["pii"],
            }
            for item in sorted(enriched_items, key=lambda value: str(value["fileIdentity"]).casefold())
        ],
        "groups": [
            {
                "tableKey": group["tableKey"],
                "files": sorted(group.get("files") or []),
                "keyDecision": group["keyDecision"],
                "crossFileKeyQuality": group["crossFileKeyQuality"],
                "pii": group["pii"],
            }
            for group in sorted(enriched_groups, key=lambda value: str(value["tableKey"]))
        ],
    }
    plan_fingerprint = _canonical_fingerprint(fingerprint_material)
    return {
        **base_plan,
        "schema": ATOMIC_IMPORT_PLAN_SCHEMA,
        "parentSourceRunId": current_source_run_id,
        "items": enriched_items,
        "groups": enriched_groups,
        "planFingerprint": plan_fingerprint,
        "fingerprintMaterial": fingerprint_material,
        "blockers": list(dict.fromkeys(plan_blockers)),
        "readyToCommit": bool(enriched_items) and not plan_blockers,
        "requiresOwnerReview": bool(plan_blockers) or any(group.get("pii", {}).get("requiresReview") for group in enriched_groups),
    }
