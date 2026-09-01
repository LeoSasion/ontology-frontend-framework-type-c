from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
import re
import sqlite3
from typing import Any, Callable

from aibi_contracts import core_semantic_runtime, source_pipeline_contract
from agent_evidence_plan_service import AGENT_CAPABILITIES
from analytical_skill_service import analytical_skill_runtime_context
from bi_cli_core import DUCKDB_PATH
from connector_adapter_service import adapter_contracts
from context_pack_service import context_pack_snapshot, workspace_data_fingerprint, workspace_schema_fingerprint
from domain_pack_service import domain_pack_runtime_context, domain_pack_set_fingerprint
from evidence_run_store import list_source_intelligence_runs
from query_runtime import SAFE_AGGREGATIONS, duckdb_status
from relationship_command_service import relationship_record_payload


WORKSPACE_MANIFEST_SCHEMA = "aibi-workspace-manifest/v1"
RUNTIME_CATALOG_SCHEMA = "aibi-runtime-catalog/v1"
BUSINESS_FIELD_PROFILE_SCHEMA = "aibi-business-field-profile/v1"
PROFILE_ALGORITHM_VERSION = "2.0.0"
PROFILE_SAMPLE_LIMIT = 500

_NUMBER_PATTERN = re.compile(r"^-?(?:\d+(?:\.\d+)?|\.\d+)$")
_EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_PHONE_PATTERN = re.compile(r"^(?:\+?\d[\d\s()\-]{7,}\d)$")
_IDENTITY_PATTERN = re.compile(r"^(?:\d{15}|\d{17}[\dXx])$")
_LONG_ACCOUNT_PATTERN = re.compile(r"^\d{12,19}$")
_BOOLEAN_VALUES = {"0", "1", "true", "false", "yes", "no", "y", "n", "是", "否", "有", "无"}


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    return bool(connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone())


def _path_like(value: str) -> bool:
    text = str(value or "").strip()
    return bool(
        re.match(r"^[A-Za-z]:[\\/]", text)
        or text.startswith("\\\\")
        or text.casefold().startswith("file://")
    )


def _safe_reference(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if _path_like(text):
        return f"redacted-ref:{hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]}"
    return text[:512]


def _empty_context_snapshot(connection: sqlite3.Connection, workspace_id: str) -> dict[str, Any]:
    schema_fingerprint = workspace_schema_fingerprint(connection, workspace_id)
    material = {"terms": [], "rules": [], "schemaFingerprint": schema_fingerprint}
    return {
        "schema": "aibi-context-pack/v1",
        "workspaceId": workspace_id,
        "version": _fingerprint(material)[:16],
        "schemaFingerprint": schema_fingerprint,
        "counts": {"terms": 0, "confirmedTerms": 0, "rules": 0, "confirmedRules": 0},
        "terms": [],
        "rules": [],
    }


def _compact_context_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    def term(item: dict[str, Any]) -> dict[str, Any]:
        evidence = sorted(_safe_reference(value) for value in item.get("evidenceRefs") or [] if _safe_reference(value))
        return {
            "termKey": str(item.get("term_key") or item.get("termKey") or ""),
            "canonicalName": str(item.get("canonical_name") or item.get("canonicalName") or ""),
            "aliases": sorted(str(value) for value in item.get("aliases") or []),
            "definition": str(item.get("definition") or ""),
            "scopeType": str(item.get("scope_type") or item.get("scopeType") or "workspace"),
            "scopeRef": _safe_reference(item.get("scope_ref") or item.get("scopeRef")),
            "status": str(item.get("status") or "draft"),
            "source": str(item.get("source") or "manual"),
            "evidenceRefCount": len(evidence),
            "evidenceFingerprint": _fingerprint(evidence),
        }

    def rule(item: dict[str, Any]) -> dict[str, Any]:
        evidence = sorted(_safe_reference(value) for value in item.get("evidenceRefs") or [] if _safe_reference(value))
        return {
            "ruleKey": str(item.get("rule_key") or item.get("ruleKey") or ""),
            "title": str(item.get("title") or ""),
            "statement": str(item.get("statement") or ""),
            "ruleType": str(item.get("rule_type") or item.get("ruleType") or "other"),
            "appliesTo": sorted(str(value) for value in item.get("appliesTo") or []),
            "status": str(item.get("status") or "draft"),
            "source": str(item.get("source") or "manual"),
            "evidenceRefCount": len(evidence),
            "evidenceFingerprint": _fingerprint(evidence),
        }

    terms = [term(item) for item in snapshot.get("terms") or [] if isinstance(item, dict)]
    rules = [rule(item) for item in snapshot.get("rules") or [] if isinstance(item, dict)]
    return {
        "schema": str(snapshot.get("schema") or "aibi-context-pack/v1"),
        "workspaceId": str(snapshot.get("workspaceId") or ""),
        "version": str(snapshot.get("version") or ""),
        "schemaFingerprint": str(snapshot.get("schemaFingerprint") or ""),
        "counts": snapshot.get("counts") if isinstance(snapshot.get("counts"), dict) else {},
        "terms": sorted(terms, key=lambda item: item["termKey"]),
        "rules": sorted(rules, key=lambda item: item["ruleKey"]),
    }


def _context_snapshot(connection: sqlite3.Connection, workspace_id: str) -> dict[str, Any]:
    if not (_table_exists(connection, "context_terms") and _table_exists(connection, "context_rules")):
        return _empty_context_snapshot(connection, workspace_id)
    return _compact_context_snapshot(context_pack_snapshot(connection, workspace_id))


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _json_value(value: Any, default: Any) -> Any:
    if isinstance(value, type(default)):
        return value
    if value in (None, ""):
        return default
    try:
        parsed = json.loads(str(value))
    except (json.JSONDecodeError, TypeError, ValueError):
        return default
    return parsed if isinstance(parsed, type(default)) else default


def _quoted_identifier(value: str) -> str:
    return '"' + str(value).replace('"', '""') + '"'


def _workspace_id(
    connection: sqlite3.Connection,
    args: argparse.Namespace,
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> str:
    workspace_id = str(getattr(args, "workspace", "") or active_workspace_id(connection)).strip()
    if not connection.execute("SELECT 1 FROM workspaces WHERE id = ?", (workspace_id,)).fetchone():
        raise ValueError(f"Unknown workspace: {workspace_id}")
    return workspace_id


def _normalized_scalar(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _parsed_datetime(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    normalized = text.replace("年", "-").replace("月", "-").replace("日", "")
    normalized = normalized.replace("/", "-")
    candidates = [normalized, normalized.replace("Z", "+00:00")]
    for candidate in candidates:
        try:
            parsed = datetime.fromisoformat(candidate)
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
        except ValueError:
            pass
        try:
            return datetime.combine(date.fromisoformat(candidate[:10]), datetime.min.time())
        except ValueError:
            pass
    return None


def _logical_type(values: list[str]) -> tuple[str, dict[str, int], list[datetime]]:
    counts = {"numeric": 0, "temporal": 0, "boolean": 0, "text": 0}
    parsed_times: list[datetime] = []
    for value in values:
        folded = value.casefold()
        parsed_time = _parsed_datetime(value)
        if folded in _BOOLEAN_VALUES:
            counts["boolean"] += 1
        elif _NUMBER_PATTERN.fullmatch(value.replace(",", "")):
            counts["numeric"] += 1
        elif parsed_time is not None:
            counts["temporal"] += 1
            parsed_times.append(parsed_time)
        else:
            counts["text"] += 1
    total = len(values)
    if total == 0:
        return "empty", counts, parsed_times
    dominant, dominant_count = max(counts.items(), key=lambda item: (item[1], item[0]))
    if dominant_count / total >= 0.9:
        return {"numeric": "number", "temporal": "datetime", "boolean": "boolean", "text": "string"}[dominant], counts, parsed_times
    if counts["text"] == total:
        return "string", counts, parsed_times
    return "mixed", counts, parsed_times


def _sealed_logical_type(storage_type: str) -> str:
    normalized = " ".join(str(storage_type or "VARCHAR").upper().split())
    if normalized == "BOOLEAN":
        return "boolean"
    if normalized.startswith(("DATE", "TIME", "TIMESTAMP")):
        return "datetime"
    if normalized.startswith((
        "TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT",
        "UTINYINT", "USMALLINT", "UINTEGER", "UBIGINT",
        "DECIMAL", "NUMERIC", "REAL", "FLOAT", "DOUBLE",
    )):
        return "number"
    if normalized in {"BLOB", "BYTEA"}:
        return "binary"
    return "string"


def _sensitivity(field_name: str, values: list[str]) -> dict[str, Any]:
    normalized = re.sub(r"[\s.\-]+", "_", field_name.casefold())
    name_rules = {
        "email": ("email", "e_mail", "mail_address", "邮箱", "邮件地址"),
        "phone": ("phone", "mobile", "telephone", "tel_no", "手机号", "手机号码", "电话", "联系方式"),
        "address": ("address", "street_address", "住址", "地址"),
        "person-name": ("full_name", "first_name", "last_name", "user_name", "customer_name", "contact_name", "姓名", "联系人"),
        "government-id": ("id_card", "identity_card", "passport", "身份证", "证件号", "护照"),
        "financial-account": ("bank_account", "account_no", "card_number", "银行卡", "账户号", "卡号"),
        "secret": ("password", "passwd", "secret", "api_key", "access_token", "密码", "密钥", "令牌"),
    }
    reasons: list[str] = []
    for category, tokens in name_rules.items():
        if any(token in normalized for token in tokens):
            reasons.append(f"name:{category}")
    value_reasons: set[str] = set()
    for value in values[:100]:
        compact = re.sub(r"[\s\-()]", "", value)
        if _EMAIL_PATTERN.fullmatch(value):
            value_reasons.add("shape:email")
        if _PHONE_PATTERN.fullmatch(value):
            value_reasons.add("shape:phone")
        if _IDENTITY_PATTERN.fullmatch(value):
            value_reasons.add("shape:government-id")
        if _LONG_ACCOUNT_PATTERN.fullmatch(compact):
            value_reasons.add("shape:long-account-number")
    reasons.extend(sorted(value_reasons))
    likely = any(reason.startswith("shape:") for reason in reasons) or "name:secret" in reasons
    level = "likely" if likely else "possible" if reasons else "none"
    return {
        "level": level,
        "reasonCodes": sorted(set(reasons)),
        "rawValuesExposed": False,
        "outboundPolicy": "statistics-only",
    }


def _table_columns(schema_json: Any) -> list[dict[str, Any]]:
    parsed = _json_value(schema_json, [])
    columns: list[dict[str, Any]] = []
    for item in parsed if isinstance(parsed, list) else []:
        if isinstance(item, str):
            name = item
            storage_type = "VARCHAR"
            internal = name.startswith("__aibi_")
            not_null = False
        elif isinstance(item, dict):
            name = str(item.get("name") or item.get("field") or "")
            storage_type = str(item.get("type") or item.get("physicalType") or "VARCHAR").upper()
            internal = bool(item.get("internal")) or name.startswith("__aibi_")
            not_null = bool(item.get("notNull") or item.get("notnull"))
        else:
            continue
        if name and not internal:
            columns.append({
                "field": name,
                "storageType": storage_type,
                "notNull": not_null,
                "primaryKey": False,
            })
    return columns


def _latest_source_profiles(
    connection: sqlite3.Connection,
    workspace_id: str,
    table_keys: list[str],
) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    if not _table_exists(connection, "source_runs"):
        return {}
    normalized_keys = sorted({str(value) for value in table_keys if str(value)})
    if not normalized_keys:
        return {}
    placeholders = ", ".join("?" for _ in normalized_keys)
    rows = connection.execute(
        f"""
        WITH ranked AS (
          SELECT table_key, id, status, row_count, column_count, profile_json, created_at,
                 ROW_NUMBER() OVER (
                   PARTITION BY table_key ORDER BY created_at DESC, id DESC
                 ) AS source_rank
          FROM source_runs
          WHERE workspace_id = ? AND table_key IN ({placeholders})
        )
        SELECT table_key, id, status, row_count, column_count, profile_json, created_at
        FROM ranked
        WHERE source_rank = 1
        ORDER BY table_key
        """,
        (workspace_id, *normalized_keys),
    ).fetchall()
    latest: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for row in rows:
        payload = dict(row)
        current_table_key = str(payload.pop("table_key"))
        profile = _json_value(payload.pop("profile_json"), {})
        latest[current_table_key] = (profile, payload)
    return latest


def _field_profile_lookup(source_profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("field")): item
        for item in source_profile.get("fields", [])
        if isinstance(item, dict) and str(item.get("field") or "").strip()
    }


def _field_bindings(connection: sqlite3.Connection, workspace_id: str) -> tuple[dict[tuple[str, str], list[str]], dict[tuple[str, str], list[dict[str, Any]]], dict[tuple[str, str], list[str]]]:
    metrics: dict[tuple[str, str], list[str]] = {}
    if _table_exists(connection, "metric_definitions"):
        for row in connection.execute(
            "SELECT * FROM metric_definitions WHERE workspace_id = ? AND enabled = 1 ORDER BY metric_key",
            (workspace_id,),
        ).fetchall():
            item = dict(row)
            for field in {str(item.get("measure") or ""), str(item.get("dimension") or ""), str(item.get("time_field") or "")} - {"", "*"}:
                metrics.setdefault((str(item.get("table_key") or ""), field), []).append(str(item.get("metric_key") or ""))

    relationships: dict[tuple[str, str], list[dict[str, Any]]] = {}
    rows = connection.execute(
        "SELECT * FROM relationships WHERE workspace_id = ? ORDER BY relation_key",
        (workspace_id,),
    ).fetchall() if _table_exists(connection, "relationships") else []
    for row in rows:
        payload = relationship_record_payload(row)
        validation = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
        for mapping in payload.get("fieldMappings") or []:
            left = (str(payload["left_table_key"]), str(mapping.get("leftField") or ""))
            right = (str(payload["right_table_key"]), str(mapping.get("rightField") or ""))
            edge = {
                "relationshipKey": str(payload["relation_key"]),
                "validationStatus": str(validation.get("status") or "unvalidated"),
                "otherTableKey": right[0],
                "otherField": right[1],
            }
            relationships.setdefault(left, []).append(edge)
            relationships.setdefault(right, []).append({**edge, "otherTableKey": left[0], "otherField": left[1]})

    formulas: dict[tuple[str, str], list[str]] = {}
    if _table_exists(connection, "calculated_fields"):
        for row in connection.execute(
            "SELECT * FROM calculated_fields WHERE workspace_id = ? AND enabled = 1 ORDER BY field_key",
            (workspace_id,),
        ).fetchall():
            item = dict(row)
            for dependency in _json_value(item.get("dependencies_json"), []):
                field = str(dependency or "").strip()
                if field:
                    formulas.setdefault((str(item.get("table_key") or ""), field), []).append(str(item.get("field_key") or ""))
    return metrics, relationships, formulas


def build_business_field_profiles(
    connection: sqlite3.Connection,
    workspace_id: str,
    *,
    table_key: str = "",
    field_name: str = "",
) -> list[dict[str, Any]]:
    params: list[Any] = [workspace_id]
    where = "workspace_id = ?"
    if table_key:
        where += " AND table_key = ?"
        params.append(table_key)
    registries = connection.execute(
        f"""
        SELECT table_key, display_name, physical_table, row_count, column_count, data_version, updated_at,
               active_version_id, schema_json, schema_fingerprint, content_fingerprint
        FROM table_registry
        WHERE {where}
        ORDER BY table_key
        """,
        tuple(params),
    ).fetchall()
    metric_bindings, relationship_bindings, formula_bindings = _field_bindings(connection, workspace_id)
    registry_keys = [str(registry["table_key"]) for registry in registries]
    source_profiles = _latest_source_profiles(connection, workspace_id, registry_keys)
    semantics_by_table: dict[str, dict[str, dict[str, Any]]] = {}
    if registry_keys and _table_exists(connection, "field_semantics"):
        placeholders = ", ".join("?" for _ in registry_keys)
        semantic_rows = connection.execute(
            f"SELECT * FROM field_semantics WHERE workspace_id = ? "
            f"AND table_key IN ({placeholders}) ORDER BY table_key, field_name",
            (workspace_id, *registry_keys),
        ).fetchall()
        for row in semantic_rows:
            semantics_by_table.setdefault(str(row["table_key"]), {})[str(row["field_name"])] = dict(row)
    profiles: list[dict[str, Any]] = []
    for registry in registries:
        current_table_key = str(registry["table_key"])
        columns = _table_columns(registry["schema_json"])
        source_profile, source_run = source_profiles.get(current_table_key, ({}, None))
        source_fields = _field_profile_lookup(source_profile)
        semantics = semantics_by_table.get(current_table_key, {})
        source_shape_current = bool(
            source_run
            and int(source_run.get("row_count") or 0) == int(registry["row_count"] or 0)
            and int(source_run.get("column_count") or 0) == int(registry["column_count"] or 0)
        )
        for column in columns:
            current_field = str(column["field"])
            if field_name and current_field != field_name:
                continue
            semantic = semantics.get(current_field, {})
            imported = source_fields.get(current_field, {})
            raw_samples = imported.get("sampleValues") if isinstance(imported.get("sampleValues"), list) else []
            values = [normalized[:512] for value in raw_samples[:100] if (normalized := _normalized_scalar(value))]
            sampled_type, type_counts, parsed_times = _logical_type(values)
            logical_type = _sealed_logical_type(column["storageType"])
            sensitivity = _sensitivity(current_field, values)
            row_count = int(registry["row_count"] or 0)
            non_null = int(imported.get("nonEmpty") if imported.get("nonEmpty") is not None else len(values))
            non_null = max(0, min(row_count, non_null))
            unique_count = int(imported.get("uniqueCount") if imported.get("uniqueCount") is not None else len(set(values)))
            unique_count = max(0, min(row_count, unique_count))
            role = str(semantic.get("role") or imported.get("role") or "unknown")
            usage = str(semantic.get("usage") or imported.get("usage") or "unknown")
            confidence = float(semantic.get("confidence") or imported.get("confidence") or 0)
            source = str(semantic.get("source") or "auto")
            confirmed = source in {"manual", "reviewed"}
            imported_role = str(imported.get("role") or "").strip()
            role_candidates = []
            if imported_role:
                role_candidates.append({
                    "role": imported_role,
                    "usage": str(imported.get("usage") or ""),
                    "confidence": round(float(imported.get("confidence") or 0), 4),
                    "source": "import-profile-heuristic",
                    "confirmed": False,
                })
            if semantic and not confirmed and not any(item["role"] == role for item in role_candidates):
                role_candidates.append({
                    "role": role,
                    "usage": usage,
                    "confidence": round(confidence, 4),
                    "source": "saved-auto-semantic",
                    "confirmed": False,
                })
            blockers: list[str] = []
            warnings: list[str] = []
            if not source_run:
                blockers.append("missing-source-profile")
            elif not source_shape_current:
                blockers.append("source-profile-shape-mismatch")
            if not semantic:
                warnings.append("business-meaning-unreviewed")
            elif not confirmed:
                warnings.append("business-meaning-candidate-only")
            if sampled_type == "mixed":
                warnings.append("mixed-value-types")
            if sensitivity["level"] != "none":
                warnings.append("sensitive-field-statistics-only")
            relationship_edges = sorted(
                relationship_bindings.get((current_table_key, current_field), []),
                key=lambda item: (item["relationshipKey"], item["otherTableKey"], item["otherField"]),
            )
            if any(edge["validationStatus"] != "validated" for edge in relationship_edges):
                warnings.append("relationship-review-required")
            freshness_status = "current" if source_shape_current else "unknown" if not source_run else "stale"
            status = "stale" if freshness_status == "stale" else "blocked" if blockers else "ambiguous" if warnings else "ready"
            time_coverage = None
            if parsed_times:
                time_coverage = {
                    "minimum": min(parsed_times).isoformat(),
                    "maximum": max(parsed_times).isoformat(),
                    "basis": "bounded-local-sample",
                }
            profile = {
                "schema": BUSINESS_FIELD_PROFILE_SCHEMA,
                "profileAlgorithmVersion": PROFILE_ALGORITHM_VERSION,
                "fieldRef": {
                    "workspaceId": workspace_id,
                    "tableKey": current_table_key,
                    "fieldName": current_field,
                },
                "tableLabel": str(registry["display_name"]),
                "dataVersion": int(registry["data_version"] or 1),
                "activeVersionId": str(registry["active_version_id"] or ""),
                "schemaFingerprint": str(registry["schema_fingerprint"] or ""),
                "contentFingerprint": str(registry["content_fingerprint"] or ""),
                "observedShape": {
                    "storageType": column["storageType"],
                    "logicalType": logical_type,
                    "rowCount": row_count,
                    "nonNullCount": non_null,
                    "nullCount": max(0, row_count - non_null),
                    "nullRate": round((row_count - non_null) / row_count, 6) if row_count else 0.0,
                    "uniqueCount": unique_count,
                    "uniqueRatio": round(unique_count / row_count, 6) if row_count else 0.0,
                    "boundedSampleSize": len(values),
                    "typeEvidence": type_counts,
                    "timeCoverage": time_coverage,
                },
                "semantic": {
                    "savedRole": role,
                    "savedUsage": usage,
                    "confidence": round(confidence, 4),
                    "authority": f"{source}-confirmed" if confirmed else "saved-auto-candidate" if semantic else "import-candidate-only",
                    "confirmedSemanticRef": f"field-semantic:{current_table_key}.{current_field}" if confirmed else None,
                    "roleCandidates": sorted(role_candidates, key=lambda item: (-item["confidence"], item["role"])),
                    "statusCandidates": {
                        "observedDistinctCount": unique_count if role in {"status", "dimension"} else 0,
                        "rawValuesWithheld": True,
                        "authority": "statistics-only-no-raw-values",
                    },
                    "tags": _json_value(semantic.get("tags_json"), []),
                    "notePresent": bool(str(semantic.get("note") or "").strip()) if confirmed else False,
                    "noteFingerprint": _fingerprint(str(semantic.get("note") or "")) if confirmed and str(semantic.get("note") or "").strip() else None,
                },
                "sensitivity": sensitivity,
                "bindings": {
                    "metricKeys": sorted(metric_bindings.get((current_table_key, current_field), [])),
                    "calculatedFieldKeys": sorted(formula_bindings.get((current_table_key, current_field), [])),
                    "relationshipEdges": relationship_edges,
                    "grainCandidate": role in {"identity_key", "identifier"} and row_count > 0 and non_null == row_count and unique_count == row_count,
                },
                "freshness": {
                    "status": freshness_status,
                    "sourceRunId": str(source_run.get("id") or "") if source_run else None,
                    "sourceRunCreatedAt": str(source_run.get("created_at") or "") if source_run else None,
                    "tableUpdatedAt": str(registry["updated_at"] or ""),
                    "usableForPlanning": not blockers,
                    "planningAuthority": "confirmed-business-meaning" if confirmed else "shape-and-candidate-only",
                },
                "status": status,
                "blockers": sorted(set(blockers)),
                "warnings": sorted(set(warnings)),
                "evidenceRefs": sorted(
                    [
                        *([f"source-run:{source_run['id']}"] if source_run else []),
                        *([f"field-semantic:{current_table_key}.{current_field}"] if semantic else []),
                        *[f"metric:{key}" for key in metric_bindings.get((current_table_key, current_field), [])],
                        *[f"relationship:{item['relationshipKey']}" for item in relationship_edges],
                    ]
                ),
            }
            profile["fingerprint"] = _fingerprint(profile)
            profiles.append(profile)
    return sorted(profiles, key=lambda item: (item["fieldRef"]["tableKey"], item["fieldRef"]["fieldName"]))


def _metric_catalog(connection: sqlite3.Connection, workspace_id: str) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    if not _table_exists(connection, "metric_definitions"):
        return metrics
    rows = connection.execute(
        "SELECT * FROM metric_definitions WHERE workspace_id = ? ORDER BY metric_key",
        (workspace_id,),
    ).fetchall()
    for row in rows:
        item = dict(row)
        material = {
            "metricKey": str(item["metric_key"]),
            "label": str(item["label"]),
            "tableKey": str(item["table_key"]),
            "measure": str(item["measure"]),
            "aggregation": str(item["aggregation"]),
            "dimension": item.get("dimension"),
            "timeField": item.get("time_field"),
            "valueFormat": str(item.get("value_format") or "auto"),
            "metricType": str(item.get("metric_type") or "basic"),
            "dependencies": _json_value(item.get("dependencies_json"), []),
            "filters": _json_value(item.get("filters_json"), []),
            "source": str(item.get("source") or "auto"),
            "enabled": bool(item.get("enabled", 1)),
        }
        material["definitionFingerprint"] = _fingerprint({**material, "formula": str(item.get("formula_text") or ""), "ast": _json_value(item.get("formula_ast_json"), {})})
        metrics.append(material)
    return metrics


def _calculated_field_catalog(connection: sqlite3.Connection, workspace_id: str) -> list[dict[str, Any]]:
    formulas: list[dict[str, Any]] = []
    if not _table_exists(connection, "calculated_fields"):
        return formulas
    for row in connection.execute(
        "SELECT * FROM calculated_fields WHERE workspace_id = ? ORDER BY field_key",
        (workspace_id,),
    ).fetchall():
        item = dict(row)
        payload = {
            "fieldKey": str(item["field_key"]),
            "tableKey": str(item["table_key"]),
            "name": str(item["name"]),
            "mode": str(item["mode"]),
            "dependencies": _json_value(item.get("dependencies_json"), []),
            "valueFormat": str(item.get("value_format") or "auto"),
            "source": str(item.get("source") or "manual"),
            "enabled": bool(item.get("enabled", 1)),
        }
        payload["definitionFingerprint"] = _fingerprint({**payload, "formula": str(item.get("formula_text") or ""), "ast": _json_value(item.get("formula_ast_json"), {})})
        formulas.append(payload)
    return formulas


def _relationship_catalog(connection: sqlite3.Connection, workspace_id: str) -> list[dict[str, Any]]:
    relationships: list[dict[str, Any]] = []
    if not _table_exists(connection, "relationships"):
        return relationships
    for row in connection.execute(
        "SELECT * FROM relationships WHERE workspace_id = ? ORDER BY relation_key",
        (workspace_id,),
    ).fetchall():
        item = relationship_record_payload(row)
        validation = item.get("validation") if isinstance(item.get("validation"), dict) else {}
        payload = {
            "relationshipKey": str(item["relation_key"]),
            "name": str(item.get("name") or item.get("relation_key") or ""),
            "leftTableKey": str(item["left_table_key"]),
            "rightTableKey": str(item["right_table_key"]),
            "fieldMappings": item.get("fieldMappings") or [],
            "joinType": str(item["join_type"]),
            "confidence": round(float(item.get("confidence") or 0), 4),
            "validationStatus": str(validation.get("status") or "unvalidated"),
            "blockers": sorted(str(value) for value in validation.get("blockers") or []),
            "filterCount": len(item.get("filters") or []),
            "preaggregation": item.get("preaggregation") or {},
        }
        payload["definitionFingerprint"] = _fingerprint({**payload, "filters": item.get("filters") or [], "validation": validation})
        relationships.append(payload)
    return relationships


def workspace_planning_binding(
    connection: sqlite3.Connection,
    workspace_id: str,
    *,
    profiles: list[dict[str, Any]] | None = None,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the stable subset that must remain equal before a saved plan is reused."""
    profiles = profiles if profiles is not None else build_business_field_profiles(connection, workspace_id)
    metrics = catalog["metrics"] if catalog is not None else _metric_catalog(connection, workspace_id)
    calculated_fields = catalog["calculatedFields"] if catalog is not None else _calculated_field_catalog(connection, workspace_id)
    relationships = catalog["relationships"] if catalog is not None else _relationship_catalog(connection, workspace_id)
    knowledge = catalog["knowledge"] if catalog is not None else _context_snapshot(connection, workspace_id)
    if catalog is not None:
        domain_packs = catalog["domainPacks"]
        analytical_skills = catalog["analyticalSkills"]
    else:
        try:
            domain_packs = _compact_domain_packs(domain_pack_runtime_context(connection, workspace_id))
        except sqlite3.OperationalError:
            domain_packs = {"schema": "", "coreApiVersion": None, "available": [], "enabled": [], "fingerprint": _fingerprint([])}
        try:
            analytical_skills = _compact_analytical_skills(analytical_skill_runtime_context(connection, workspace_id))
        except sqlite3.OperationalError:
            analytical_skills = {"schema": "", "available": [], "enabled": [], "fingerprint": _fingerprint([])}
    profile_refs = [
        {
            "fieldRef": item["fieldRef"],
            "fingerprint": item["fingerprint"],
            "status": item["status"],
            "usableForPlanning": item["freshness"]["usableForPlanning"],
        }
        for item in profiles
    ]
    components = {
        "schema": workspace_schema_fingerprint(connection, workspace_id),
        "data": workspace_data_fingerprint(connection, workspace_id),
        "fieldProfiles": _fingerprint(profile_refs),
        "metrics": _fingerprint(metrics),
        "calculatedFields": _fingerprint(calculated_fields),
        "relationships": _fingerprint(relationships),
        "context": _fingerprint(knowledge),
        "domainPacks": str(domain_packs.get("fingerprint") or ""),
        "analyticalSkills": str(analytical_skills.get("fingerprint") or ""),
    }
    binding = {
        "schema": "aibi-workspace-planning-binding/v1",
        "workspaceId": workspace_id,
        "componentFingerprints": components,
        "profileCount": len(profile_refs),
        "candidateCanAuthorizeJoin": False,
    }
    binding["fingerprint"] = _fingerprint(binding)
    return binding


def _compact_domain_packs(runtime: dict[str, Any]) -> dict[str, Any]:
    def compact(item: dict[str, Any]) -> dict[str, Any]:
        name = item.get("displayName") if isinstance(item.get("displayName"), dict) else {}
        return {
            "packId": str(item.get("packId") or ""),
            "version": str(item.get("version") or ""),
            "fingerprint": str(item.get("fingerprint") or ""),
            "displayName": {"zh": str(name.get("zh") or ""), "en": str(name.get("en") or "")},
            "capabilities": sorted(str(value) for value in item.get("capabilities") or []),
            "compatible": bool(item.get("compatible", True)),
            "enabled": bool(item.get("enabled", True)),
            "builtIn": bool(item.get("builtIn", False)),
        }
    available = [compact(item) for item in runtime.get("availableDomainPacks") or [] if isinstance(item, dict)]
    enabled_ids = {str(item.get("packId") or "") for item in runtime.get("enabledDomainPacks") or [] if isinstance(item, dict)}
    return {
        "schema": str(runtime.get("schema") or ""),
        "coreApiVersion": runtime.get("coreApiVersion"),
        "available": sorted(available, key=lambda item: item["packId"]),
        "enabled": sorted([item for item in available if item["packId"] in enabled_ids], key=lambda item: item["packId"]),
        "fingerprint": domain_pack_set_fingerprint(runtime),
    }


def _compact_analytical_skills(runtime: dict[str, Any]) -> dict[str, Any]:
    def compact(item: dict[str, Any]) -> dict[str, Any]:
        display_name = item.get("displayName") if isinstance(item.get("displayName"), dict) else {}
        return {
            "skillId": str(item.get("skillId") or ""),
            "version": str(item.get("version") or ""),
            "fingerprint": str(item.get("fingerprint") or ""),
            "displayName": {"zh": str(display_name.get("zh") or ""), "en": str(display_name.get("en") or "")},
            "skillKind": str(item.get("skillKind") or "analysis"),
            "taskTypes": sorted(str(value) for value in item.get("taskTypes") or []),
            "requiredRoles": sorted(str(value) for value in item.get("requiredRoles") or []),
            "requiredDomainPacks": sorted(str(value) for value in item.get("requiredDomainPacks") or []),
            "allowedCapabilities": sorted(str(value) for value in item.get("allowedCapabilities") or []),
            "enabled": bool(item.get("enabled", True)),
            "sourceType": str(item.get("sourceType") or "builtin"),
        }
    available = [compact(item) for item in runtime.get("availableAnalyticalSkills") or [] if isinstance(item, dict)]
    enabled_ids = {str(item.get("skillId") or "") for item in runtime.get("enabledAnalyticalSkills") or [] if isinstance(item, dict)}
    return {
        "schema": str(runtime.get("schema") or ""),
        "available": sorted(available, key=lambda item: item["skillId"]),
        "enabled": sorted([item for item in available if item["skillId"] in enabled_ids], key=lambda item: item["skillId"]),
        "fingerprint": str(runtime.get("fingerprint") or ""),
    }


def _capability_catalog(command_capabilities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "capabilityId": str(item.get("capabilityId") or ""),
            "command": str(item.get("command") or ""),
            "domain": str(item.get("domain") or ""),
            "mutationMode": str(item.get("mutationMode") or "read-only"),
            "entrypoints": sorted(str(value) for value in item.get("entrypoints") or []),
            "permissions": item.get("permissions") if isinstance(item.get("permissions"), dict) else {},
            "confirmation": item.get("confirmation") if isinstance(item.get("confirmation"), dict) else {},
        }
        for item in sorted(command_capabilities, key=lambda value: str(value.get("capabilityId") or ""))
    ]


def build_runtime_catalog(
    connection: sqlite3.Connection,
    workspace_id: str,
    *,
    command_capabilities: list[dict[str, Any]],
    profiles: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    profiles = profiles if profiles is not None else build_business_field_profiles(connection, workspace_id)
    tables = [
        {
            "tableKey": str(row["table_key"]),
            "displayName": str(row["display_name"]),
            "rowCount": int(row["row_count"] or 0),
            "columnCount": int(row["column_count"] or 0),
            "dataVersion": int(row["data_version"] or 1),
            "updatedAt": str(row["updated_at"] or ""),
        }
        for row in connection.execute(
            "SELECT table_key, display_name, row_count, column_count, data_version, updated_at FROM table_registry WHERE workspace_id = ? ORDER BY table_key",
            (workspace_id,),
        ).fetchall()
    ]
    fields = [
        {
            "fieldRef": profile["fieldRef"],
            "savedRole": profile["semantic"]["savedRole"],
            "savedUsage": profile["semantic"]["savedUsage"],
            "semanticAuthority": profile["semantic"]["authority"],
            "profileStatus": profile["status"],
            "profileFingerprint": profile["fingerprint"],
            "sensitivity": profile["sensitivity"]["level"],
            "usableForPlanning": profile["freshness"]["usableForPlanning"],
        }
        for profile in profiles
    ]
    metrics = _metric_catalog(connection, workspace_id)
    calculated_fields = _calculated_field_catalog(connection, workspace_id)
    relationships = _relationship_catalog(connection, workspace_id)
    context = _context_snapshot(connection, workspace_id)
    domain_packs = _compact_domain_packs(domain_pack_runtime_context(connection, workspace_id))
    analytical_skills = _compact_analytical_skills(analytical_skill_runtime_context(connection, workspace_id))
    selected_row = connection.execute(
        "SELECT profile_id, updated_at FROM workspace_agent_runtime_profiles WHERE workspace_id = ?",
        (workspace_id,),
    ).fetchone()
    selected_profile_id = str(selected_row["profile_id"] if selected_row else "deterministic")
    query_runtime = duckdb_status(DUCKDB_PATH)
    connectors = [
        {
            "connectorKey": str(row["connector_key"]),
            "name": str(row["name"]),
            "connectorType": str(row["connector_type"]),
            "provider": str(row["provider"]),
            "status": str(row["status"]),
            "lastSyncAt": row["last_sync_at"],
            "lastSyncStatus": row["last_sync_status"],
        }
        for row in connection.execute(
            "SELECT connector_key, name, connector_type, provider, status, last_sync_at, last_sync_status FROM data_connectors WHERE workspace_id = ? ORDER BY connector_key",
            (workspace_id,),
        ).fetchall()
    ]
    adapters = [
        {
            "schema": item["schema"],
            "adapterId": item["adapterId"],
            "connectorType": item["connectorType"],
            "available": bool(item["available"]),
            "operations": list(item.get("operations") or []),
            "permissions": item.get("permissions") or {},
            "limits": item.get("limits") or {},
            "credentialMode": str((item.get("credentials") or {}).get("mode") or "none"),
            "credentialValuesInReceipts": False,
        }
        for item in adapter_contracts()
    ]
    core = core_semantic_runtime()
    pipeline = source_pipeline_contract()
    capabilities = _capability_catalog(command_capabilities)
    catalog = {
        "schema": RUNTIME_CATALOG_SCHEMA,
        "workspaceId": workspace_id,
        "tables": tables,
        "fields": fields,
        "metrics": metrics,
        "calculatedFields": calculated_fields,
        "relationships": relationships,
        "knowledge": context,
        "domainPacks": domain_packs,
        "analyticalSkills": analytical_skills,
        "agentRuntime": {
            "selectedProfileId": selected_profile_id,
            "selectionUpdatedAt": selected_row["updated_at"] if selected_row else None,
            "businessSemanticAuthority": "deterministic-local-bi",
            "providerCanWrite": False,
            "toolPermissions": [],
        },
        "queryRuntime": {
            "engine": str(query_runtime.get("engine") or "duckdb"),
            "available": bool(query_runtime.get("available")),
            "fallbackEngine": None,
            "queryAvailability": str(query_runtime.get("queryAvailability") or "blocked"),
            "reasonCode": query_runtime.get("reasonCode"),
        },
        "connectors": connectors,
        "connectorAdapters": adapters,
        "capabilities": capabilities,
        "agentCapabilities": [
            {"capabilityId": capability_id, "mutationMode": AGENT_CAPABILITIES[capability_id]}
            for capability_id in sorted(AGENT_CAPABILITIES)
        ],
        "contracts": {
            "coreSemantic": {
                "version": core.get("version"),
                "coreSemanticId": core.get("coreSemanticId"),
                "ontologyDomain": core.get("ontologyDomain"),
                "summary": core.get("summary"),
                "fingerprint": _fingerprint(core),
            },
            "sourcePipeline": {
                "version": pipeline.get("version"),
                "status": pipeline.get("status"),
                "stageIds": [str(item.get("id") or "") for item in pipeline.get("stages") or []],
                "fingerprint": _fingerprint(pipeline),
            },
            "businessFieldProfile": BUSINESS_FIELD_PROFILE_SCHEMA,
            "workspaceManifest": WORKSPACE_MANIFEST_SCHEMA,
        },
        "formulaDsl": {
            "allowedFunctions": ["ABS", "AVG", "COALESCE", "CONCAT", "COUNT", "COUNT_DISTINCT", "IF", "MAX", "MIN", "ROUND", "SAFE_DIVIDE", "SUM"],
            "safeAggregations": sorted(SAFE_AGGREGATIONS),
            "acceptsSql": False,
        },
        "guardrails": {
            "businessSemanticAuthority": "confirmed-local-facts",
            "candidateCanAuthorizeJoin": False,
            "providerCanWrite": False,
            "arbitrarySql": "forbidden",
            "arbitraryCode": "forbidden",
            "otherAibiRepositories": "forbidden",
            "credentialsInPayload": False,
        },
    }
    catalog["fingerprint"] = _fingerprint(catalog)
    return catalog


def _evidence_snapshot(connection: sqlite3.Connection, workspace_id: str) -> dict[str, Any]:
    runs = list_source_intelligence_runs(connection, workspace_id=workspace_id, limit=1)
    latest = runs[0] if runs else None
    if not latest:
        return {"latestSourceIntelligenceRun": None, "status": "missing", "usableForPlanning": False}
    freshness = latest.get("freshness") if isinstance(latest.get("freshness"), dict) else {}
    return {
        "latestSourceIntelligenceRun": {
            "runKey": str(latest.get("run_key") or ""),
            "label": str(latest.get("label") or ""),
            "status": str(latest.get("status") or ""),
            "createdAt": str(latest.get("created_at") or ""),
            "counts": {
                "sources": int(latest.get("source_count") or 0),
                "tables": int(latest.get("table_count") or 0),
                "fieldCandidates": int(latest.get("field_candidate_count") or 0),
                "relationships": int(latest.get("relationship_count") or 0),
                "metricPlans": int(latest.get("metric_sql_plan_count") or 0),
                "executableMetricPlans": int(latest.get("metric_sql_executable_count") or 0),
            },
            "freshness": {
                "status": str(freshness.get("status") or "unknown"),
                "usableForPlanning": bool(freshness.get("usableForPlanning")),
                "missingFingerprints": sorted(str(value) for value in freshness.get("missingFingerprints") or []),
                "mismatches": sorted(str(value) for value in freshness.get("mismatches") or []),
            },
        },
        "status": str(freshness.get("status") or "unknown"),
        "usableForPlanning": bool(freshness.get("usableForPlanning")),
    }


def build_workspace_manifest(
    connection: sqlite3.Connection,
    workspace_id: str,
    *,
    command_capabilities: list[dict[str, Any]],
) -> dict[str, Any]:
    workspace = connection.execute(
        "SELECT id, name, current_source_run_id, created_at FROM workspaces WHERE id = ?",
        (workspace_id,),
    ).fetchone()
    if not workspace:
        raise ValueError(f"Unknown workspace: {workspace_id}")
    profiles = build_business_field_profiles(connection, workspace_id)
    catalog = build_runtime_catalog(connection, workspace_id, command_capabilities=command_capabilities, profiles=profiles)
    planning_binding = workspace_planning_binding(connection, workspace_id, profiles=profiles, catalog=catalog)
    evidence = _evidence_snapshot(connection, workspace_id)
    table_refs = [
        {
            "tableKey": item["tableKey"],
            "displayName": item["displayName"],
            "rowCount": item["rowCount"],
            "columnCount": item["columnCount"],
            "dataVersion": item["dataVersion"],
        }
        for item in catalog["tables"]
    ]
    profile_refs = [
        {
            "fieldRef": item["fieldRef"],
            "status": item["status"],
            "fingerprint": item["fingerprint"],
            "usableForPlanning": item["freshness"]["usableForPlanning"],
            "businessMeaningConfirmed": item["semantic"]["authority"] in {"manual-confirmed", "reviewed-confirmed"},
        }
        for item in profiles
    ]
    component_fingerprints = {
        **planning_binding["componentFingerprints"],
        "runtime": _fingerprint({
            "agentRuntime": catalog["agentRuntime"],
            "queryRuntime": catalog["queryRuntime"],
            "capabilities": catalog["capabilities"],
            "agentCapabilities": catalog["agentCapabilities"],
            "connectorAdapters": catalog["connectorAdapters"],
        }),
        "runtimeCatalog": catalog["fingerprint"],
        "evidence": _fingerprint(evidence),
    }
    profile_status_counts = {
        status: sum(item["status"] == status for item in profiles)
        for status in ("ready", "ambiguous", "blocked", "stale")
    }
    blockers: list[str] = []
    warnings: list[str] = []
    if not table_refs:
        blockers.append("workspace-has-no-source-tables")
    if profile_status_counts["stale"]:
        blockers.append("business-field-profile-stale")
    if profile_status_counts["blocked"]:
        blockers.append("business-field-profile-blocked")
    if evidence["status"] == "stale":
        warnings.append("source-intelligence-stale")
    elif evidence["status"] in {"missing", "unknown"}:
        warnings.append("source-intelligence-not-current")
    status = "stale" if any(value.endswith("stale") for value in blockers) else "incomplete" if blockers else "current"
    manifest = {
        "schema": WORKSPACE_MANIFEST_SCHEMA,
        "workspaceId": workspace_id,
        "workspace": {
            "id": str(workspace["id"]),
            "name": str(workspace["name"]),
            "currentSourceRunId": workspace["current_source_run_id"],
            "createdAt": str(workspace["created_at"]),
        },
        "sourceSnapshot": {
            "tables": table_refs,
            "tableCount": len(table_refs),
            "rowCount": sum(item["rowCount"] for item in table_refs),
            "fieldCount": len(profile_refs),
            "dataFingerprint": component_fingerprints["data"],
            "schemaFingerprint": component_fingerprints["schema"],
        },
        "semanticSnapshot": {
            "fieldProfiles": profile_refs,
            "profileStatusCounts": profile_status_counts,
            "confirmedBusinessMeanings": sum(item["businessMeaningConfirmed"] for item in profile_refs),
            "metricCount": len(catalog["metrics"]),
            "calculatedFieldCount": len(catalog["calculatedFields"]),
            "relationshipCount": len(catalog["relationships"]),
            "validatedRelationshipCount": sum(item["validationStatus"] == "validated" for item in catalog["relationships"]),
            "contextCounts": catalog["knowledge"]["counts"],
        },
        "runtimeSnapshot": {
            "runtimeCatalogRef": {"schema": RUNTIME_CATALOG_SCHEMA, "fingerprint": catalog["fingerprint"]},
            "planningBindingRef": {"schema": planning_binding["schema"], "fingerprint": planning_binding["fingerprint"]},
            "selectedAgentProfileId": catalog["agentRuntime"]["selectedProfileId"],
            "enabledDomainPackCount": len(catalog["domainPacks"]["enabled"]),
            "enabledAnalyticalSkillCount": len(catalog["analyticalSkills"]["enabled"]),
            "registeredCapabilityCount": len(catalog["capabilities"]),
            "providerCanWrite": False,
        },
        "evidenceSnapshot": evidence,
        "planningBinding": planning_binding,
        "componentFingerprints": component_fingerprints,
        "status": status,
        "usableForPlanning": status == "current",
        "blockers": sorted(set(blockers)),
        "warnings": sorted(set(warnings)),
        "guardrails": catalog["guardrails"],
    }
    manifest["fingerprint"] = _fingerprint(manifest)
    return manifest


def business_field_profiles_command(
    args: argparse.Namespace,
    *,
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        table_key = str(getattr(args, "table", "") or "").strip()
        field_name = str(getattr(args, "field", "") or "").strip()
        profiles = build_business_field_profiles(
            connection,
            workspace_id,
            table_key=table_key,
            field_name=field_name,
        )
    request_scope = {"tableKey": table_key or None, "fieldName": field_name or None}
    return {
        "ok": True,
        "schema": "aibi-business-field-profile-collection/v1",
        "workspaceId": workspace_id,
        "requestScope": request_scope,
        "profiles": profiles,
        "count": len(profiles),
        "fingerprint": _fingerprint({
            "workspaceId": workspace_id,
            "requestScope": request_scope,
            "profiles": [item["fingerprint"] for item in profiles],
        }),
        "rawSampleValuesExposed": False,
    }


def runtime_catalog_command(
    args: argparse.Namespace,
    *,
    command_capabilities: list[dict[str, Any]],
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        catalog = build_runtime_catalog(connection, workspace_id, command_capabilities=command_capabilities)
    return {"ok": True, "runtimeCatalog": catalog}


def workspace_manifest_command(
    args: argparse.Namespace,
    *,
    command_capabilities: list[dict[str, Any]],
    open_db: Callable[[], sqlite3.Connection],
    active_workspace_id: Callable[[sqlite3.Connection], str],
) -> dict[str, Any]:
    with open_db() as connection:
        workspace_id = _workspace_id(connection, args, active_workspace_id)
        manifest = build_workspace_manifest(connection, workspace_id, command_capabilities=command_capabilities)
    return {"ok": True, "workspaceManifest": manifest}
