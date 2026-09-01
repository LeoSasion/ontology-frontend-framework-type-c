from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import nullcontext
from pathlib import Path
from typing import Any

from bi_cli_core import quote_identifier
from bi_cli_core import DUCKDB_PATH
from bi_cli_schema import table_columns as dataset_columns
from query_runtime import cursor_rows, open_validated_duckdb_query, replica_expectation
from trusted_query_service import current_source_run_binding


APPAREL_MAPPING_SCHEMA = "aibi-apparel-entity-mapping-proof/v1"
ENTITY_ALIASES: dict[str, tuple[str, ...]] = {
    "style_spu": ("style_spu", "spu", "款式", "款号", "款式编码", "stylecode", "styleno"),
    "product_id": ("product_id", "productid", "item_id", "goods_id", "商品id", "商品编号", "链接商品id"),
    "product_link": ("product_link", "producturl", "item_url", "商品链接", "宝贝链接", "链接"),
    "merchant_sku": ("merchant_sku", "merchantsku", "sku_id", "skuid", "商家sku", "商家编码", "规格编码", "货品编码"),
    "color": ("color", "colour", "颜色", "色号", "色系"),
    "size": ("size", "尺码", "码数", "规格尺码"),
    "barcode": ("barcode", "条码", "商品条码", "国际条码", "ean", "upc"),
}
AMBIGUOUS_SKU_ALIASES = {"sku", "商品编码", "货号", "规格"}
SCOPE_FIELD_TOKENS = ("平台", "渠道", "店铺", "shop", "store", "channel", "platform")
PII_FIELD_TOKENS = ("姓名", "手机", "电话", "地址", "邮箱", "身份证", "收件人", "联系人", "phone", "mobile", "email")
MAX_SCOPE_FIELDS = 4
MAX_SCOPE_VALUES_PER_FIELD = 100
MAX_TIME_FIELDS = 2


def _normalized(value: Any) -> str:
    return re.sub(r"[\s_\-./]+", "", str(value or "")).casefold()


def classify_apparel_field(field: str) -> dict[str, Any]:
    normalized = _normalized(field)
    if normalized in {_normalized(alias) for alias in AMBIGUOUS_SKU_ALIASES}:
        return {"entity": None, "attributeOf": None, "confidence": 0.0, "ambiguous": True, "reason": "generic-sku-is-not-a-grain"}
    for entity, aliases in ENTITY_ALIASES.items():
        if normalized in {_normalized(alias) for alias in aliases}:
            attribute_of = "merchant_sku" if entity in {"color", "size", "barcode"} else None
            return {"entity": entity, "attributeOf": attribute_of, "confidence": 1.0, "ambiguous": False, "reason": "exact-apparel-alias"}
    return {"entity": None, "attributeOf": None, "confidence": 0.0, "ambiguous": False, "reason": "not-an-apparel-entity-field"}


def _fingerprint(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _registry(connection: sqlite3.Connection, workspace_id: str, table_key: str) -> sqlite3.Row | None:
    return connection.execute(
        "SELECT * FROM table_registry WHERE workspace_id = ? AND table_key = ?",
        (workspace_id, table_key),
    ).fetchone()


def _apparel_domain_enabled(connection: sqlite3.Connection, workspace_id: str) -> bool:
    row = connection.execute(
        """
        SELECT enabled FROM workspace_domain_packs
        WHERE workspace_id = ? AND pack_id = 'platform-commerce'
        """,
        (workspace_id,),
    ).fetchone()
    return bool(row and int(row["enabled"] or 0) == 1)


def _sql_literal(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _scope_snapshot(connection: Any, registry: sqlite3.Row, columns: list[str]) -> dict[str, Any]:
    fields = [
        field for field in columns
        if any(token.casefold() in field.casefold() for token in SCOPE_FIELD_TOKENS)
    ]
    selected = fields[:MAX_SCOPE_FIELDS]
    values: dict[str, list[str]] = {field: [] for field in selected}
    if selected:
        exploded_values = ", ".join(
            f"({_sql_literal(field)}, CAST(t.{quote_identifier(field)} AS VARCHAR))"
            for field in selected
        )
        rows = cursor_rows(connection.execute(f"""
            WITH exploded AS MATERIALIZED (
              SELECT field_name, TRIM(value) AS value
              FROM {quote_identifier(registry['physical_table'])} AS t
              CROSS JOIN LATERAL (VALUES {exploded_values}) AS fields(field_name, value)
              WHERE value IS NOT NULL AND TRIM(value) <> ''
            ),
            distinct_values AS (
              SELECT field_name, value FROM exploded GROUP BY field_name, value
            ),
            ranked AS (
              SELECT
                field_name,
                value,
                ROW_NUMBER() OVER (PARTITION BY field_name ORDER BY value) AS value_rank
              FROM distinct_values
            )
            SELECT field_name, value
            FROM ranked
            WHERE value_rank <= {MAX_SCOPE_VALUES_PER_FIELD}
            ORDER BY field_name, value
        """))
        for row in rows:
            values[str(row["field_name"])].append(str(row["value"]))
    return {"fields": fields, "values": values, "proven": bool(fields)}


def _time_snapshot(
    control_connection: sqlite3.Connection,
    analysis_connection: Any,
    workspace_id: str,
    registry: sqlite3.Row,
    columns: list[str],
) -> dict[str, Any]:
    rows = control_connection.execute(
        """
        SELECT field_name FROM field_semantics
        WHERE workspace_id = ? AND table_key = ? AND role IN ('event_time', 'time')
        ORDER BY confidence DESC, field_name
        """,
        (workspace_id, registry["table_key"]),
    ).fetchall()
    fields = [str(row["field_name"]) for row in rows if str(row["field_name"]) in columns]
    windows: dict[str, dict[str, Any]] = {}
    selected = fields[:MAX_TIME_FIELDS]
    if selected:
        select_parts: list[str] = []
        for index, field in enumerate(selected):
            timestamp = f"TRY_CAST({quote_identifier(field)} AS TIMESTAMP)"
            select_parts.extend([
                f"MIN({timestamp}) AS {quote_identifier(f'__start_{index}')}",
                f"MAX({timestamp}) AS {quote_identifier(f'__end_{index}')}",
                f"COUNT({timestamp})::BIGINT AS {quote_identifier(f'__parsed_{index}')}",
            ])
        summary = cursor_rows(analysis_connection.execute(
            f"SELECT {', '.join(select_parts)} FROM {quote_identifier(registry['physical_table'])}"
        ))[0]
        for index, field in enumerate(selected):
            start = summary[f"__start_{index}"]
            end = summary[f"__end_{index}"]
            windows[field] = {
                "startAt": str(start) if start is not None else None,
                "endAt": str(end) if end is not None else None,
                "parsedRows": int(summary[f"__parsed_{index}"] or 0),
            }
    return {"fields": fields, "windows": windows, "proven": any(item["parsedRows"] > 0 for item in windows.values())}


def _privacy_snapshot(columns: list[str], mappings: list[dict[str, str]], side: str) -> dict[str, Any]:
    sensitive = [field for field in columns if any(token.casefold() in field.casefold() for token in PII_FIELD_TOKENS)]
    key_name = "leftField" if side == "left" else "rightField"
    mapped_sensitive = [mapping[key_name] for mapping in mappings if mapping.get(key_name) in sensitive]
    return {
        "classification": "restricted" if sensitive else "internal",
        "sensitiveFields": sensitive,
        "mappedSensitiveFields": mapped_sensitive,
        "mappingAllowed": not mapped_sensitive,
    }


def _scope_overlap(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_values = {value for values in left.get("values", {}).values() for value in values}
    right_values = {value for values in right.get("values", {}).values() for value in values}
    overlap = sorted(left_values & right_values)
    if not left_values and not right_values:
        status = "unproven"
    elif left_values and right_values and overlap:
        status = "overlap-proven"
    else:
        status = "scope-mismatch"
    return {
        "status": status,
        "leftDistinctValues": len(left_values),
        "rightDistinctValues": len(right_values),
        "overlapValues": overlap[:20],
    }


def _time_overlap(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_windows = [item for item in left.get("windows", {}).values() if item.get("startAt") and item.get("endAt")]
    right_windows = [item for item in right.get("windows", {}).values() if item.get("startAt") and item.get("endAt")]
    if not left_windows and not right_windows:
        return {"status": "unproven", "overlap": None}
    if not left_windows or not right_windows:
        return {"status": "one-sided-only", "overlap": None}
    latest_start = max(str(item["startAt"]) for item in [*left_windows, *right_windows])
    earliest_end = min(str(item["endAt"]) for item in [*left_windows, *right_windows])
    overlap = latest_start <= earliest_end
    return {"status": "overlap-proven" if overlap else "no-overlap", "overlap": overlap, "startAt": latest_start, "endAt": earliest_end}


def build_apparel_entity_mapping_proof(
    connection: sqlite3.Connection,
    *,
    workspace_id: str,
    left_table_key: str,
    right_table_key: str,
    mappings: list[dict[str, str]],
    relationship_preview: dict[str, Any],
    duckdb_path: Path = DUCKDB_PATH,
    writer_profiling_connection: Any | None = None,
) -> dict[str, Any]:
    left_registry = _registry(connection, workspace_id, left_table_key)
    right_registry = _registry(connection, workspace_id, right_table_key)
    if not left_registry or not right_registry:
        return {"schema": APPAREL_MAPPING_SCHEMA, "applicable": False, "status": "blocked", "blockers": ["mapping-table-missing"]}
    if not _apparel_domain_enabled(connection, workspace_id):
        return {
            "schema": APPAREL_MAPPING_SCHEMA,
            "applicable": False,
            "status": "not-applicable",
            "reason": "platform-commerce-domain-pack-disabled",
            "blockers": [],
        }
    left_columns = dataset_columns(connection, left_registry["physical_table"])
    right_columns = dataset_columns(connection, right_registry["physical_table"])
    mapping_proofs = []
    apparel_signal = False
    blockers: list[str] = []
    for mapping in mappings:
        left = classify_apparel_field(str(mapping.get("leftField") or ""))
        right = classify_apparel_field(str(mapping.get("rightField") or ""))
        mapping_apparel_signal = bool(left.get("entity") or right.get("entity") or left.get("ambiguous") or right.get("ambiguous"))
        apparel_signal = apparel_signal or mapping_apparel_signal
        if mapping_apparel_signal and (not left.get("entity") or not right.get("entity")):
            blockers.append("apparel-entity-grain-unresolved")
        if left.get("attributeOf") or right.get("attributeOf"):
            blockers.append("sku-attribute-cannot-be-promoted-to-entity")
        mapping_proofs.append({"mapping": mapping, "left": left, "right": right})
    if not apparel_signal:
        return {"schema": APPAREL_MAPPING_SCHEMA, "applicable": False, "status": "not-applicable", "blockers": []}

    metrics = relationship_preview.get("metrics") if isinstance(relationship_preview.get("metrics"), dict) else {}
    left_unique = int(metrics.get("leftDuplicateKeyGroups") or 0) == 0
    right_unique = int(metrics.get("rightDuplicateKeyGroups") or 0) == 0
    cardinality = "one-to-one" if left_unique and right_unique else "one-to-many" if left_unique else "many-to-one" if right_unique else "many-to-many"
    if int(metrics.get("overlapKeys") or 0) <= 0:
        blockers.append("apparel-key-values-do-not-overlap")
    if cardinality == "many-to-many":
        blockers.append("apparel-many-to-many-requires-preaggregation")

    analysis_context = (
        nullcontext(writer_profiling_connection)
        if writer_profiling_connection is not None
        else open_validated_duckdb_query(
            duckdb_path,
            [replica_expectation(left_registry), replica_expectation(right_registry)],
        )
    )
    with analysis_context as analysis_connection:
        left_scope = _scope_snapshot(analysis_connection, left_registry, left_columns)
        right_scope = _scope_snapshot(analysis_connection, right_registry, right_columns)
        left_time = _time_snapshot(connection, analysis_connection, workspace_id, left_registry, left_columns)
        right_time = _time_snapshot(connection, analysis_connection, workspace_id, right_registry, right_columns)
    scope_overlap = _scope_overlap(left_scope, right_scope)
    if scope_overlap["status"] in {"unproven", "scope-mismatch"}:
        blockers.append("apparel-platform-shop-scope-unproven")
    time_overlap = _time_overlap(left_time, right_time)
    if time_overlap["status"] in {"no-overlap", "one-sided-only"}:
        blockers.append("apparel-time-coverage-incompatible")
    elif time_overlap["status"] == "unproven":
        blockers.append("apparel-time-coverage-unproven")
    left_privacy = _privacy_snapshot(left_columns, mappings, "left")
    right_privacy = _privacy_snapshot(right_columns, mappings, "right")
    if not left_privacy["mappingAllowed"] or not right_privacy["mappingAllowed"]:
        blockers.append("apparel-pii-cannot-be-relationship-key")
    source_binding = current_source_run_binding(connection, workspace_id, [left_table_key, right_table_key])
    blockers.extend(source_binding["blockers"])
    blockers = list(dict.fromkeys(blockers))
    material = {
        "workspaceId": workspace_id,
        "sourceRunId": source_binding.get("currentSourceRunId"),
        "tables": {
            left_table_key: int(left_registry["data_version"] or 1),
            right_table_key: int(right_registry["data_version"] or 1),
        },
        "mappings": mapping_proofs,
        "relationshipMetrics": metrics,
        "cardinality": cardinality,
        "scope": {"left": left_scope, "right": right_scope, "overlap": scope_overlap},
        "timeCoverage": {"left": left_time, "right": right_time, "overlap": time_overlap},
        "privacy": {"left": left_privacy, "right": right_privacy},
    }
    return {
        "schema": APPAREL_MAPPING_SCHEMA,
        "applicable": True,
        "status": "validated" if not blockers else "review-required",
        "workspaceId": workspace_id,
        "sourceRunBinding": source_binding,
        "tableDataVersions": material["tables"],
        "mappingProofs": mapping_proofs,
        "cardinality": cardinality,
        "grainTransition": [mapping["left"].get("entity") for mapping in mapping_proofs] + [mapping["right"].get("entity") for mapping in mapping_proofs],
        "relationshipMetrics": metrics,
        "scope": material["scope"],
        "timeCoverage": material["timeCoverage"],
        "privacy": material["privacy"],
        "proofFingerprint": _fingerprint(material),
        "blockers": blockers,
    }
