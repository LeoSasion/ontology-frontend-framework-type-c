from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Callable

from atomic_import_plan_service import bind_single_import_plan, enrich_atomic_import_plan
from bi_cli_core import now_iso, parse_csv_list, slug, source_label, unique_key
from import_schema_change_service import build_import_schema_change_preview
from import_stage_service import create_import_stage, read_import_stage
from import_table_writer_service import revalidate_relationships_for_table

SUPPORTED_IMPORT_SUFFIXES = {".csv", ".xlsx", ".xlsm"}

DATE_SUFFIX_PATTERNS = [
    re.compile(r"[\s._-]*(?:19|20)\d{2}年?\d{1,2}月(?:\d{1,2}日?)?$", re.IGNORECASE),
    re.compile(r"[\s._-]*(?:19|20)\d{2}[\s._-]\d{1,2}[\s._-]\d{1,2}(?:[\s._-]\d{1,2}){0,3}$", re.IGNORECASE),
    re.compile(r"[\s._-]*(?:19|20)\d{2}[\s._-]\d{1,2}(?:[\s._-]\d{1,2})?$", re.IGNORECASE),
    re.compile(r"[\s._-]*(?:\d{1,2}|[一二三四五六七八九十]+)月$", re.IGNORECASE),
    re.compile(r"[\s._-]*\d{1,2}[\s._-]\d{1,2}月?$", re.IGNORECASE),
    re.compile(r"[\s._-]*(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)$", re.IGNORECASE),
    re.compile(r"[\s._-]*q[1-4]$", re.IGNORECASE),
    re.compile(r"^(?:19|20)\d{2}年?\d{1,2}月[\s._-]*", re.IGNORECASE),
    re.compile(r"^(?:19|20)\d{2}[\s._-]\d{1,2}(?:[\s._-]\d{1,2})?[\s._-]*", re.IGNORECASE),
    re.compile(r"^(?:\d{1,2}|[一二三四五六七八九十]+)月[\s._-]*", re.IGNORECASE),
    re.compile(r"^(?:jan|january|feb|february|mar|march|apr|april|may|jun|june|jul|july|aug|august|sep|sept|september|oct|october|nov|november|dec|december)[\s._-]*", re.IGNORECASE),
]


def _current_source_run_id(
    connection: sqlite3.Connection,
    workspace_id: str | None = None,
) -> str | None:
    if workspace_id is None:
        active = connection.execute(
            "SELECT value FROM system_flags WHERE key = 'active_workspace_id'"
        ).fetchone()
        workspace_id = str(active["value"] or "default") if active else "default"
    workspace = connection.execute(
        "SELECT current_source_run_id FROM workspaces WHERE id = ?",
        (workspace_id,),
    ).fetchone()
    return (str(workspace["current_source_run_id"] or "") or None) if workspace else None


def _trim_name_separators(value: str) -> str:
    return value.strip().strip(" ._-　")


def suggested_import_display_name(path: Path) -> str:
    stem = _trim_name_separators(path.stem)
    if not stem:
        return "数据源"
    current = stem
    changed = True
    while changed:
        changed = False
        for pattern in DATE_SUFFIX_PATTERNS:
            candidate = _trim_name_separators(pattern.sub("", current))
            if candidate != current and len(candidate) >= 2:
                current = candidate
                changed = True
                break
    return current


def suggested_import_table_key(path: Path, explicit_table: str | None = None) -> str:
    if explicit_table and explicit_table.strip():
        return slug(explicit_table)
    display_name = suggested_import_display_name(path)
    normalized = slug(display_name)
    if normalized != "source" and len(normalized) >= 3 and not normalized.isdigit():
        return normalized[:64]
    digest = hashlib.sha1(display_name.encode("utf-8")).hexdigest()[:8]
    prefix = normalized if normalized != "source" and not normalized.isdigit() else "source"
    if prefix != "source" and len(prefix) < 3:
        prefix = f"source_{prefix}"
    return f"{prefix}_{digest}"[:64].rstrip("_")


def discover_import_files(path: str | Path, *, recursive: bool = True, limit: int = 200) -> list[Path]:
    source_path = Path(path).resolve()
    if not source_path.exists():
        raise FileNotFoundError(source_path)
    if source_path.is_file():
        return [source_path] if source_path.suffix.lower() in SUPPORTED_IMPORT_SUFFIXES else []
    iterator = source_path.rglob("*") if recursive else source_path.glob("*")
    files = [
        item.resolve()
        for item in iterator
        if item.is_file() and item.suffix.lower() in SUPPORTED_IMPORT_SUFFIXES and not item.name.startswith("~$")
    ]
    return sorted(files, key=lambda item: str(item).lower())[: max(1, limit)]


def _preview_unique_key(preview: dict[str, Any]) -> list[str]:
    merge_policy = preview.get("mergePolicyPreview")
    if isinstance(merge_policy, dict):
        value = merge_policy.get("uniqueFields")
        if isinstance(value, list):
            return [str(item) for item in value if str(item).strip()]
    return []


def build_folder_import_plan(
    connection: sqlite3.Connection,
    path: str | Path,
    *,
    recursive: bool = True,
    limit: int = 200,
    unique_fields_value: str | None = None,
    conflict_rule_value: str | None = None,
    workspace_id: str | None = None,
    stage_bindings: dict[str, str] | None = None,
    build_import_preview: Callable[..., dict[str, Any]],
    read_table_file: Callable[[Path], tuple[list[str], list[dict[str, Any]]]],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    resolved_workspace_id = str(workspace_id or active_workspace_id(connection)).strip()
    if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (resolved_workspace_id,)).fetchone():
        raise ValueError(f"Unknown workspace: {resolved_workspace_id}")
    import_root = Path(path).resolve()
    files = discover_import_files(path, recursive=recursive, limit=limit)
    groups: dict[str, dict[str, Any]] = {}
    items: list[dict[str, Any]] = []
    planned_tables: set[str] = set()
    normalized_stage_bindings = {
        str(key): str(value)
        for key, value in (stage_bindings or {}).items()
        if str(key).strip() and str(value).strip()
    }
    for file_path in files:
        try:
            file_identity = file_path.relative_to(import_root if import_root.is_dir() else import_root.parent).as_posix()
        except ValueError:
            file_identity = file_path.name
        preview = build_import_preview(
            connection,
            file_path,
            None,
            unique_fields_value,
            conflict_rule_value,
            workspace_id=resolved_workspace_id,
            stage_key=normalized_stage_bindings.get(file_identity),
        )
        if str(preview.get("workspaceId") or "") != resolved_workspace_id:
            raise RuntimeError("Folder import preview escaped the requested workspace.")
        table_key = str(preview.get("suggestedTableKey") or suggested_import_table_key(file_path))
        display_name = str(preview.get("suggestedDisplayName") or suggested_import_display_name(file_path))
        matched_table = preview.get("matchedTable") if isinstance(preview.get("matchedTable"), dict) else None
        mode = "merge" if matched_table or table_key in planned_tables else "create"
        planned_tables.add(table_key)
        row_count = int((preview.get("profile") or {}).get("rowCount") or 0)
        column_count = int((preview.get("profile") or {}).get("columnCount") or 0)
        unique_fields = _preview_unique_key(preview)
        item = {
            "file": source_label(file_path),
            "fileIdentity": file_identity,
            "absolutePath": str(file_path),
            "tableKey": table_key,
            "displayName": display_name,
            "mode": mode,
            "rowCount": row_count,
            "columnCount": column_count,
            "uniqueFields": unique_fields,
            "matchedTable": matched_table,
            "keyAuthority": "owner_confirmed" if parse_csv_list(unique_fields_value) else "auto_candidate",
            "_preview": preview,
        }
        items.append(item)
        group = groups.setdefault(table_key, {
            "tableKey": table_key,
            "displayName": display_name,
            "fileCount": 0,
            "rowCount": 0,
            "columnCount": column_count,
            "uniqueFields": unique_fields,
            "modes": set(),
            "files": [],
        })
        group["fileCount"] += 1
        group["rowCount"] += row_count
        group["modes"].add(mode)
        group["files"].append(item["file"])
        if unique_fields and not group["uniqueFields"]:
            group["uniqueFields"] = unique_fields
    normalized_groups = []
    for group in groups.values():
        normalized_groups.append({
            **group,
            "modes": sorted(group["modes"]),
            "willMerge": group["fileCount"] > 1 or "merge" in group["modes"],
        })
    normalized_groups.sort(key=lambda item: str(item["displayName"]))
    workspace = connection.execute(
        "SELECT current_source_run_id FROM workspaces WHERE id = ?",
        (resolved_workspace_id,),
    ).fetchone()
    base_plan = {
        "ok": True,
        "dryRun": True,
        "requiresConfirmation": False,
        "workspaceId": resolved_workspace_id,
        "path": str(Path(path).resolve()),
        "fileCount": len(files),
        "tableCount": len(normalized_groups),
        "items": items,
        "groups": normalized_groups,
        "willWrite": False,
    }

    stages_by_path = {
        str(Path(item["absolutePath"]).resolve()): str(
            ((item.get("_preview") or {}).get("importStage") or {}).get("stageKey") or ""
        )
        for item in items
    }

    def read_sealed_plan_file(file_path: Path):
        stage_key = stages_by_path.get(str(Path(file_path).resolve()))
        if not stage_key:
            return read_table_file(file_path)
        headers, rows, _profile, _summary = read_import_stage(
            stage_key=stage_key,
            workspace_id=resolved_workspace_id,
        )
        return headers, rows

    return enrich_atomic_import_plan(
        base_plan,
        read_table_file=read_sealed_plan_file,
        current_source_run_id=(str(workspace["current_source_run_id"] or "") or None) if workspace else None,
    )


def build_import_preview(
    connection: sqlite3.Connection,
    file: str | Path,
    table: str | None = None,
    unique_fields_value: str | None = None,
    conflict_rule_value: str | None = None,
    *,
    workspace_id: str | None = None,
    mode_value: str | None = None,
    stage_key: str | None = None,
    read_table_file: Callable[[Path], tuple[list[str], list[dict[str, Any]]]],
    profile_rows: Callable[[list[str], list[dict[str, Any]]], dict[str, Any]],
    normalize_records_for_columns: Callable[[list[dict[str, Any]], list[str]], list[dict[str, Any]]],
    analyze_unique_key_quality: Callable[[list[dict[str, Any]], list[str]], dict[str, Any]],
    active_workspace_id: Callable[[sqlite3.Connection], str],
    saved_import_policy: Callable[..., dict[str, Any] | None],
    table_columns: Callable[[sqlite3.Connection, str], list[str]],
    registry_for_table: Callable[..., sqlite3.Row | None],
    preview_merge_plan: Callable[..., dict[str, Any]],
    sanitize_unique_fields: Callable[..., list[str]],
    quote_identifier: Callable[[str], str],
    source_pipeline_contract: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    resolved_workspace_id = str(workspace_id or active_workspace_id(connection)).strip()
    if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (resolved_workspace_id,)).fetchone():
        raise ValueError(f"Unknown workspace: {resolved_workspace_id}")
    requested_mode = str(mode_value or "auto").strip().lower()
    if requested_mode not in {"auto", "create", "merge", "replace"}:
        raise ValueError(f"Unsupported import preview mode: {requested_mode}")
    path = Path(file).resolve()
    if stage_key:
        headers, rows, profile, import_stage = read_import_stage(
            stage_key=str(stage_key),
            workspace_id=resolved_workspace_id,
        )
    else:
        if not path.exists():
            raise FileNotFoundError(path)
        headers, rows = read_table_file(path)
        profile = profile_rows(headers, rows)
        import_stage = create_import_stage(
            source_path=path,
            workspace_id=resolved_workspace_id,
            headers=headers,
            rows=rows,
            profile=profile,
        )
    table_key = suggested_import_table_key(path, table)
    suggested_display_name = suggested_import_display_name(path)
    matches: list[dict[str, Any]] = []
    unique_candidates = [field["field"] for field in profile["fields"] if field["role"] == "identity_key"]
    if not unique_candidates:
        unique_candidates = [
            field["field"]
            for field in profile["fields"]
            if rows and field["uniqueCount"] >= max(1, int(len(rows) * 0.9)) and field["nonEmpty"] == len(rows)
        ][:2]
    explicit_unique_fields = parse_csv_list(unique_fields_value)
    conflict_rule_arg = conflict_rule_value
    normalized_rows = normalize_records_for_columns(rows, headers)
    unique_quality = None
    merge_plan = None
    row = connection.execute(
        """
        SELECT table_key, display_name, row_count
        FROM table_registry
        WHERE table_key = ? AND workspace_id = ?
        """,
        (table_key, resolved_workspace_id),
    ).fetchone()
    existing = dict(row) if row else None
    import_policy = saved_import_policy(connection, table_key, workspace_id=resolved_workspace_id)
    selected_unique_fields = explicit_unique_fields or (import_policy["uniqueFields"] if import_policy else unique_candidates[:2])
    conflict_rule = conflict_rule_arg or (import_policy["conflictRule"] if import_policy else "overwrite")
    unique_quality = analyze_unique_key_quality(normalized_rows, selected_unique_fields) if selected_unique_fields else None
    for registry in connection.execute(
        "SELECT * FROM table_registry WHERE workspace_id = ? ORDER BY display_name",
        (resolved_workspace_id,),
    ):
        physical_columns = table_columns(connection, registry["physical_table"])
        same_count = len(headers) == len(physical_columns)
        same_fields = same_count and set(headers) == set(physical_columns)
        if not same_fields:
            continue
        registry_policy = saved_import_policy(
            connection,
            registry["table_key"],
            workspace_id=resolved_workspace_id,
        )
        registry_unique_fields = explicit_unique_fields or (registry_policy["uniqueFields"] if registry_policy else unique_candidates[:2])
        match_unique_fields = [field for field in registry_unique_fields if field in physical_columns]
        match_conflict_rule = conflict_rule_arg or (registry_policy["conflictRule"] if registry_policy else conflict_rule)
        match_merge_plan = None
        if match_unique_fields:
            match_records = normalize_records_for_columns(rows, physical_columns)
            match_merge_plan = preview_merge_plan(
                connection,
                registry["physical_table"],
                physical_columns,
                match_records,
                match_unique_fields,
                match_conflict_rule,
                quote_identifier,
            )
        item = {
            "tableKey": registry["table_key"],
            "displayName": registry["display_name"],
            "rowCount": registry["row_count"],
            "matchType": "exactOrder" if headers == physical_columns else "exactFields",
            "fieldCount": len(physical_columns),
            "matchedFieldCount": len(set(headers) & set(physical_columns)),
            "score": 100 if headers == physical_columns else 96,
            "policyUniqueFields": match_unique_fields,
            "policyConflictRule": match_conflict_rule,
            "savedPolicy": registry_policy,
            "policyQuality": analyze_unique_key_quality(
                normalize_records_for_columns(rows, physical_columns),
                match_unique_fields,
            ) if match_unique_fields else None,
            "policyMergePlan": match_merge_plan,
        }
        matches.append(item)
    if not existing and matches:
        best_match = sorted(matches, key=lambda item: (int(item["score"]), item["matchType"] == "exactOrder"), reverse=True)[0]
        existing = {
            "table_key": best_match["tableKey"],
            "display_name": best_match["displayName"],
            "row_count": best_match["rowCount"],
        }
        table_key = best_match["tableKey"]
        selected_unique_fields = list(best_match.get("policyUniqueFields") or [])
        conflict_rule = str(best_match.get("policyConflictRule") or conflict_rule)
        import_policy = best_match.get("savedPolicy")
        unique_quality = best_match.get("policyQuality")
        merge_plan = best_match.get("policyMergePlan")
    if existing and selected_unique_fields:
        registry = registry_for_table(connection, table_key, workspace_id=resolved_workspace_id)
        if registry:
            physical_columns = table_columns(connection, registry["physical_table"])
            if set(headers) == set(physical_columns):
                merge_plan = preview_merge_plan(
                    connection,
                    registry["physical_table"],
                    physical_columns,
                    normalize_records_for_columns(rows, physical_columns),
                    sanitize_unique_fields(selected_unique_fields, physical_columns, allow_empty=False),
                    conflict_rule,
                    quote_identifier,
                )
    effective_mode = "create"
    schema_compatible = True
    schema_change = None
    blockers: list[str] = []
    if existing:
        effective_mode = "replace" if requested_mode in {"create", "replace"} else "merge"
        registry = registry_for_table(connection, table_key, workspace_id=resolved_workspace_id)
        physical_columns = table_columns(connection, registry["physical_table"]) if registry else []
        schema_compatible = set(headers) == set(physical_columns)
        if effective_mode == "replace":
            schema_change = build_import_schema_change_preview(
                connection,
                workspace_id=resolved_workspace_id,
                table_key=table_key,
                incoming_fields=headers,
            )
        elif not schema_compatible:
            blockers.append("merge-schema-mismatch")
    return {
        "ok": True,
        "dryRun": True,
        "workspaceId": resolved_workspace_id,
        "file": source_label(path),
        "matchedTable": existing,
        "matches": matches,
        "suggestedTableKey": table_key,
        "suggestedDisplayName": suggested_display_name,
        "profile": profile,
        "importStage": import_stage,
        "uniqueKeyQuality": unique_quality,
        "schemaChange": schema_change,
        "blockers": blockers,
        "readyToCommit": not blockers,
        "mergePolicyPreview": {
            "mode": effective_mode,
            "uniqueFields": selected_unique_fields,
            "conflictRule": conflict_rule,
            "savedPolicy": import_policy,
            "mergePlan": merge_plan,
            "schemaCompatible": schema_compatible,
            "blockers": blockers,
            "willWrite": False,
        },
        "sourcePipelineContract": source_pipeline_contract(),
    }


def preview_import_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    build_import_preview: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    with open_db() as connection:
        preview = build_import_preview(
            connection,
            args.file,
            args.table,
            getattr(args, "unique_fields", None),
            getattr(args, "conflict_rule", None),
            workspace_id=(str(getattr(args, "workspace", "") or "").strip() or None),
            mode_value=getattr(args, "mode", None),
        )
        workspace_id = str(preview.get("workspaceId") or "")
        if not workspace_id:
            raise RuntimeError("Import preview did not bind a workspace.")
        return bind_single_import_plan(
            preview,
            Path(args.file),
            current_source_run_id=_current_source_run_id(connection, workspace_id),
        )


def execute_import_commit(
    connection: sqlite3.Connection,
    file: str | Path,
    table: str | None = None,
    name: str | None = None,
    mode: str = "create",
    unique_fields_value: str | None = None,
    conflict_rule_value: str | None = None,
    *,
    workspace_id: str | None = None,
    stage_key: str | None = None,
    build_import_preview: Callable[..., dict[str, Any]],
    merge_import_into_table: Callable[..., dict[str, Any]],
    import_csv_as_table: Callable[..., dict[str, Any]],
    upsert_navigation_module: Callable[..., None],
) -> dict[str, Any]:
    path = Path(file).resolve()
    table_key = suggested_import_table_key(path, table)
    default_display_name = suggested_import_display_name(path)
    preview = build_import_preview(
        connection,
        path,
        table,
        unique_fields_value,
        conflict_rule_value,
        workspace_id=workspace_id,
        mode_value=mode,
        stage_key=stage_key,
    )
    resolved_workspace_id = str(preview.get("workspaceId") or "")
    if not resolved_workspace_id or (workspace_id is not None and resolved_workspace_id != str(workspace_id)):
        raise RuntimeError("Import commit preview escaped the requested workspace.")
    if mode == "merge":
        unique_fields = parse_csv_list(unique_fields_value) or preview["mergePolicyPreview"]["uniqueFields"]
        conflict_rule = conflict_rule_value or preview["mergePolicyPreview"]["conflictRule"]
        result = merge_import_into_table(
            connection,
            path,
            table_key=table_key,
            unique_fields=unique_fields,
            conflict_rule=conflict_rule,
            display_name=name,
            workspace_id=resolved_workspace_id,
            stage_key=stage_key,
        )
    else:
        result = import_csv_as_table(
            connection,
            path,
            table_key=table_key,
            display_name=name or default_display_name,
            mode=mode,
            workspace_id=resolved_workspace_id,
            stage_key=stage_key,
        )
    if str(result.get("workspaceId") or "") != resolved_workspace_id:
        raise RuntimeError("Import writer escaped the requested workspace.")
    upsert_navigation_module(
        connection,
        module_key=f"table:{result['tableKey']}",
        name=result["displayName"],
        module_type="table",
        table_key=result["tableKey"],
        created_by="manual",
        agent_managed=1,
        workspace_id=resolved_workspace_id,
    )
    return result


def import_commit_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    build_import_preview: Callable[..., dict[str, Any]],
    execute_import_commit: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    with open_db() as connection:
        preview = build_import_preview(
            connection,
            args.file,
            args.table,
            args.unique_fields,
            args.conflict_rule,
            workspace_id=(str(getattr(args, "workspace", "") or "").strip() or None),
            mode_value=getattr(args, "mode", None),
        )
        workspace_id = str(preview.get("workspaceId") or "")
        if not workspace_id:
            raise RuntimeError("Import preview did not bind a workspace.")
        bound_plan = bind_single_import_plan(
            preview,
            Path(args.file),
            current_source_run_id=_current_source_run_id(connection, workspace_id),
        )
        if not args.yes:
            bound_plan["requiresConfirmation"] = True
            recommended_mode = str((bound_plan.get("commitOptions") or {}).get("mode") or args.mode)
            bound_plan["recommendedCommand"] = (
                f"python tools/aibi_cli.py --json import-commit {args.file} --mode {recommended_mode} "
                f"--expected-plan {bound_plan['planFingerprint']} --yes"
            )
            return bound_plan
        expected_plan = str(getattr(args, "expected_plan", "") or "").strip()
        if getattr(args, "require_plan", False) and not expected_plan:
            raise ValueError("Single-file import requires the plan fingerprint from the latest preview.")
        if expected_plan and expected_plan != str(bound_plan.get("planFingerprint") or ""):
            raise ValueError("Single-file import plan changed after preview; run preview-import again.")
        expected_mode = str((bound_plan.get("commitOptions") or {}).get("mode") or "")
        if expected_plan and str(args.mode or "") != expected_mode:
            raise ValueError(f"Import mode changed after preview; re-run preview-import for mode {args.mode}.")
        result = execute_import_commit(
            connection,
            args.file,
            args.table,
            args.name,
            args.mode,
            args.unique_fields,
            args.conflict_rule,
            workspace_id=workspace_id,
        )
        if str(result.get("workspaceId") or "") != workspace_id:
            raise RuntimeError("Import commit escaped the preview workspace.")
        connection.commit()
    return {"ok": True, "committed": True, "planFingerprint": bound_plan["planFingerprint"], "result": result}


def preview_import_folder_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    build_import_preview: Callable[..., dict[str, Any]],
    read_table_file: Callable[[Path], tuple[list[str], list[dict[str, Any]]]],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with open_db() as connection:
        return build_folder_import_plan(
            connection,
            args.path,
            recursive=not getattr(args, "no_recursive", False),
            limit=getattr(args, "limit", 200),
            unique_fields_value=getattr(args, "unique_fields", None),
            conflict_rule_value=getattr(args, "conflict_rule", None),
            workspace_id=(str(getattr(args, "workspace", "") or "").strip() or None),
            build_import_preview=build_import_preview,
            read_table_file=read_table_file,
            active_workspace_id=active_workspace_id,
        )


def execute_folder_import_plan(
    connection: sqlite3.Connection,
    plan: dict[str, Any],
    *,
    workspace_id: str | None = None,
    execute_import_commit: Callable[..., dict[str, Any]],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    """Apply an already revalidated folder plan inside the caller-owned transaction."""
    resolved_workspace_id = str(workspace_id or active_workspace_id(connection)).strip()
    if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (resolved_workspace_id,)).fetchone():
        raise ValueError(f"Unknown workspace: {resolved_workspace_id}")
    if str(plan.get("workspaceId") or "") != resolved_workspace_id:
        raise RuntimeError("Folder import plan does not belong to the requested workspace.")
    results = []
    for item in plan["items"]:
        mode = str(item.get("mode") or "create")
        unique_fields = list((item.get("keyDecision") or {}).get("uniqueFields") or [])
        result = execute_import_commit(
            connection,
            item["absolutePath"],
            item["tableKey"],
            item["displayName"],
            mode,
            ",".join(unique_fields),
            None,
            workspace_id=resolved_workspace_id,
            stage_key=str(item.get("stageKey") or "") or None,
        )
        if str(result.get("workspaceId") or "") != resolved_workspace_id:
            raise RuntimeError("Folder import item escaped the requested workspace.")
        results.append({
            "file": item["file"],
            "mode": mode,
            "tableKey": result.get("tableKey"),
            "displayName": result.get("displayName"),
            "rowCount": (result.get("profile") or {}).get("rowCount") if isinstance(result.get("profile"), dict) else None,
            "writeSummary": result.get("writeSummary"),
            "dataVersion": result.get("dataVersion"),
            "sourceRunId": result.get("sourceRunId"),
            "workspaceId": resolved_workspace_id,
        })
    batch_source_run_id = unique_key("source_run_batch")
    table_results: dict[str, dict[str, Any]] = {}
    for result in results:
        table_results[str(result.get("tableKey") or "")] = result
    connection.execute(
        """
        INSERT INTO source_runs(
          id, workspace_id, table_key, name, status, source_file, row_count,
          column_count, profile_json, evidence_json, created_at
        ) VALUES(?, ?, '__batch__', ?, 'ready', ?, ?, ?, ?, ?, ?)
        """,
        (
            batch_source_run_id,
            resolved_workspace_id,
            f"Atomic folder import: {Path(plan['path']).name}",
            source_label(Path(plan["path"])),
            sum(int(item.get("rowCount") or 0) for item in plan["items"]),
            sum(int(group.get("columnCount") or 0) for group in plan["groups"]),
            json.dumps({
                "schema": "aibi-atomic-source-run/v1",
                "planFingerprint": plan["planFingerprint"],
                "parentSourceRunId": plan.get("parentSourceRunId"),
                "tableKeys": sorted(table_results),
                "plan": plan,
            }, ensure_ascii=False),
            json.dumps([
                "atomic-import-plan",
                "content-hash-revalidated",
                "owner-key-gate",
                "all-logical-tables-committed",
            ], ensure_ascii=False),
            now_iso(),
        ),
    )
    for table_key, result in table_results.items():
        connection.execute(
            """
            INSERT INTO source_run_tables(
              source_run_id, workspace_id, table_key, data_version, row_count, created_at
            ) VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                batch_source_run_id,
                resolved_workspace_id,
                table_key,
                int(result.get("dataVersion") or 0),
                int((connection.execute(
                    "SELECT row_count FROM table_registry WHERE workspace_id = ? AND table_key = ?",
                    (resolved_workspace_id, table_key),
                ).fetchone() or {"row_count": 0})["row_count"]),
                now_iso(),
            ),
        )
    connection.execute(
        "UPDATE workspaces SET current_source_run_id = ? WHERE id = ?",
        (batch_source_run_id, resolved_workspace_id),
    )
    batch_relationship_revalidations = {
        table_key: revalidate_relationships_for_table(
            connection,
            workspace_id=resolved_workspace_id,
            table_key=table_key,
        )
        for table_key in table_results
    }
    return {
        "ok": True,
        "committed": True,
        "workspaceId": resolved_workspace_id,
        "path": plan["path"],
        "fileCount": plan["fileCount"],
        "tableCount": plan["tableCount"],
        "items": plan["items"],
        "groups": plan["groups"],
        "results": results,
        "sourceRunId": batch_source_run_id,
        "planFingerprint": plan["planFingerprint"],
        "atomic": True,
        "relationshipRevalidations": batch_relationship_revalidations,
    }


def import_folder_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], Any],
    build_import_preview: Callable[..., dict[str, Any]],
    execute_import_commit: Callable[..., dict[str, Any]],
    read_table_file: Callable[[Path], tuple[list[str], list[dict[str, Any]]]],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = str(getattr(args, "workspace", "") or active_workspace_id(connection)).strip()
        if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
            raise ValueError(f"Unknown workspace: {workspace_id}")
        plan = build_folder_import_plan(
            connection,
            args.path,
            recursive=not getattr(args, "no_recursive", False),
            limit=getattr(args, "limit", 200),
            unique_fields_value=getattr(args, "unique_fields", None),
            conflict_rule_value=getattr(args, "conflict_rule", None),
            workspace_id=workspace_id,
            build_import_preview=build_import_preview,
            read_table_file=read_table_file,
            active_workspace_id=active_workspace_id,
        )
        if not args.yes:
            return {
                **plan,
                "requiresConfirmation": True,
                "recommendedCommand": (
                    f"python tools/aibi_cli.py --json import-folder {args.path} "
                    f"--expected-plan {plan['planFingerprint']} --yes"
                ),
            }
        expected_plan = str(getattr(args, "expected_plan", "") or "").strip()
        if not expected_plan:
            raise ValueError("Atomic folder import requires --expected-plan from the latest preview.")
        if expected_plan != str(plan.get("planFingerprint") or ""):
            raise ValueError("Folder import plan changed after preview; run preview-import-folder again.")
        if plan.get("readyToCommit") is not True:
            raise ValueError(f"Folder import plan is blocked: {', '.join(plan.get('blockers') or ['owner-review-required'])}")
        result = execute_folder_import_plan(
            connection,
            plan,
            workspace_id=workspace_id,
            execute_import_commit=execute_import_commit,
            active_workspace_id=active_workspace_id,
        )
        connection.commit()
    return result
