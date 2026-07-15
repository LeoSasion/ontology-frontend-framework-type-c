from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from context_pack_service import workspace_data_fingerprint, workspace_schema_fingerprint  # noqa: E402
from query_plan_receipt_service import create_query_plan_receipt  # noqa: E402


checks: list[dict[str, object]] = []


def check(label: str, ok: bool, detail: object = None) -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": None if ok else detail})


connection = sqlite3.connect(":memory:")
connection.row_factory = sqlite3.Row
connection.executescript(
    """
    CREATE TABLE table_registry(
      workspace_id TEXT NOT NULL,
      table_key TEXT NOT NULL,
      display_name TEXT,
      physical_table TEXT NOT NULL,
      data_version INTEGER,
      row_count INTEGER,
      column_count INTEGER,
      updated_at TEXT,
      PRIMARY KEY(workspace_id, table_key)
    );
    CREATE TABLE field_semantics(
      workspace_id TEXT NOT NULL,
      table_key TEXT NOT NULL,
      field_name TEXT NOT NULL,
      role TEXT,
      usage TEXT,
      confidence REAL,
      tags_json TEXT,
      usage_json TEXT,
      source TEXT
    );
    CREATE TABLE relationships(
      workspace_id TEXT NOT NULL,
      relation_key TEXT NOT NULL,
      left_table_key TEXT NOT NULL,
      right_table_key TEXT NOT NULL,
      left_field TEXT,
      right_field TEXT,
      mappings_json TEXT,
      filters_json TEXT,
      preaggregation_json TEXT,
      join_type TEXT,
      confidence REAL,
      validation_json TEXT,
      updated_at TEXT,
      PRIMARY KEY(workspace_id, relation_key)
    );
    CREATE TABLE query_plan_receipts(
      receipt_key TEXT PRIMARY KEY,
      workspace_id TEXT NOT NULL,
      request_text TEXT NOT NULL,
      status TEXT NOT NULL,
      source_table_key TEXT,
      schema_fingerprint TEXT,
      plan_json TEXT NOT NULL,
      evidence_json TEXT,
      action_key TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    CREATE TABLE orders(order_id TEXT, channel TEXT);
    CREATE TABLE refunds(order_id TEXT, amount REAL);
    """
)
connection.executemany(
    """
    INSERT INTO table_registry(
      workspace_id, table_key, display_name, physical_table, data_version,
      row_count, column_count, updated_at
    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?)
    """,
    [
        ("default", "orders", "Orders", "orders", 1, 2, 2, "2026-07-16T08:00:00Z"),
        ("default", "refunds", "Refunds", "refunds", 1, 1, 2, "2026-07-16T08:00:00Z"),
    ],
)
connection.execute(
    """
    INSERT INTO relationships(
      workspace_id, relation_key, left_table_key, right_table_key, left_field,
      right_field, mappings_json, filters_json, preaggregation_json, join_type,
      confidence, validation_json, updated_at
    ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
    (
        "default",
        "orders-refunds",
        "orders",
        "refunds",
        "order_id",
        "order_id",
        "[]",
        "[]",
        "{}",
        "left",
        0.98,
        "{}",
        "2026-07-16T08:00:00Z",
    ),
)

legacy_schema_fingerprint = workspace_schema_fingerprint(connection, "default", "orders")
legacy_data_fingerprint = workspace_data_fingerprint(connection, "default", "orders")
legacy = create_query_plan_receipt(
    connection,
    workspace_id="default",
    request_text="按渠道统计订单",
    source_table_key="orders",
    status="executed",
    group="channel",
    aggregation="count",
    result_rows=[{"channel": "web", "value": 2}],
    domain_packs=[],
    now_iso=lambda: "2026-07-16T08:01:00Z",
)
check("legacy-single-table-key-is-preserved", legacy["source"]["tableKey"] == "orders", legacy["source"])
check("legacy-single-table-list-is-added", legacy["source"]["tableKeys"] == ["orders"], legacy["source"])
check(
    "legacy-single-table-schema-fingerprint-is-unchanged",
    legacy["source"]["schemaFingerprint"] == legacy_schema_fingerprint,
    legacy["source"],
)
check(
    "legacy-single-table-data-fingerprint-is-unchanged",
    legacy["source"]["dataFingerprint"] == legacy_data_fingerprint,
    legacy["source"],
)

relationship_proof = [{
    "relationKey": "orders-refunds",
    "fromTable": "orders",
    "toTable": "refunds",
    "fromField": "order_id",
    "toField": "order_id",
    "joinType": "left",
    "validationStatus": "passed",
    "proofStatus": "verified",
    "blockers": [],
    "dataVersions": {
        "expected": {"orders": 1, "refunds": 1},
        "current": {"orders": 1, "refunds": 1},
        "matches": True,
    },
}]
execution_plan = {
    "status": "ready",
    "rootTable": "orders",
    "relationships": relationship_proof,
}
multi = create_query_plan_receipt(
    connection,
    workspace_id="default",
    request_text="按渠道统计退款金额",
    source_table_key="orders->refunds",
    source_table_keys=["orders", "refunds"],
    relationship_path_proof=relationship_proof,
    status="executed",
    group="channel",
    measure="amount",
    aggregation="sum",
    joins=relationship_proof,
    execution_plan=execution_plan,
    result_rows=[{"channel": "web", "value": 10}],
    domain_packs=[],
    now_iso=lambda: "2026-07-16T08:02:00Z",
)
check("multi-table-path-has-canonical-root", multi["source"]["tableKey"] == "orders", multi["source"])
check("multi-table-source-list-is-explicit", multi["source"]["tableKeys"] == ["orders", "refunds"], multi["source"])
check(
    "multi-table-source-entries-are-registered",
    len(multi["source"]["tables"]) == 2 and all(item["registered"] for item in multi["source"]["tables"]),
    multi["source"]["tables"],
)
check(
    "multi-table-fingerprints-are-complete",
    all(len(str(multi["source"].get(key) or "")) == 64 for key in ("schemaFingerprint", "dataFingerprint", "sourceFingerprint")),
    multi["source"],
)
check(
    "multi-table-data-fingerprint-is-combined",
    multi["source"]["dataFingerprint"] not in {item["dataFingerprint"] for item in multi["source"]["tables"]},
    multi["source"],
)
proofs = multi["selection"]["relationshipPathProof"]
check(
    "relationship-path-proof-is-fingerprinted-per-hop",
    len(proofs) == 1 and proofs[0]["hopIndex"] == 0 and len(proofs[0]["proofFingerprint"]) == 64,
    proofs,
)
check("relationship-path-validation-passes", multi["validation"]["relationshipPathProven"] is True, multi["validation"])
strict_proof_variants = [
    (
        "planned-proof-fails-strict-validation",
        [{**relationship_proof[0], "proofStatus": "planned"}],
        "2026-07-16T08:02:10Z",
    ),
    (
        "blocked-proof-fails-strict-validation",
        [{**relationship_proof[0], "proofStatus": "blocked", "blockers": ["fan-out-after-measure-grain"]}],
        "2026-07-16T08:02:20Z",
    ),
    (
        "version-mismatch-proof-fails-strict-validation",
        [{
            **relationship_proof[0],
            "dataVersions": {
                "expected": {"orders": 1, "refunds": 1},
                "current": {"orders": 1, "refunds": 2},
                "matches": False,
            },
        }],
        "2026-07-16T08:02:30Z",
    ),
]
for label, proof_variant, timestamp in strict_proof_variants:
    strict_receipt = create_query_plan_receipt(
        connection,
        workspace_id="default",
        request_text=label,
        source_table_key="orders",
        source_table_keys=["orders", "refunds"],
        relationship_path_proof=proof_variant,
        status="executed",
        execution_plan=execution_plan,
        joins=relationship_proof,
        domain_packs=[],
        now_iso=lambda value=timestamp: value,
    )
    check(label, strict_receipt["validation"]["relationshipPathProven"] is False, strict_receipt["validation"])
stored = connection.execute(
    "SELECT source_table_key FROM query_plan_receipts WHERE receipt_key = ?",
    (multi["receiptKey"],),
).fetchone()
check("persisted-source-key-is-canonical-root", stored["source_table_key"] == "orders", dict(stored))

semantic_plan = {
    "status": "ready",
    "grain": {"tables": ["orders", "refunds"]},
    "joinPlan": {
        "rootTable": "orders",
        "targets": [{"selectedPath": {"hops": relationship_proof}}],
    },
}
derived = create_query_plan_receipt(
    connection,
    workspace_id="default",
    request_text="自动推导跨表来源",
    source_table_key="orders->refunds",
    status="executed",
    semantic_plan=semantic_plan,
    execution_plan=execution_plan,
    joins=relationship_proof,
    domain_packs=[],
    now_iso=lambda: "2026-07-16T08:03:00Z",
)
check("source-table-list-can-be-derived", derived["source"]["tableKeys"] == ["orders", "refunds"], derived["source"])
check("relationship-proof-can-be-derived", len(derived["selection"]["relationshipPathProof"]) == 1, derived["selection"])

verified_runtime_proof = {
    "schema": "aibi-relationship-path-proof/v1",
    "status": "verified",
    "hopProofs": [
        {**relationship_proof[0], "proofStatus": "verified", "ordinal": 1},
        {**relationship_proof[0], "proofStatus": "verified", "ordinal": 2},
    ],
    "fingerprint": "9" * 64,
}
runtime_derived = create_query_plan_receipt(
    connection,
    workspace_id="default",
    request_text="保留执行期逐跳证明",
    source_table_key="orders",
    source_table_keys=["orders", "refunds"],
    status="executed",
    execution_plan={
        **execution_plan,
        "relationships": [relationship_proof[0], relationship_proof[0]],
        "relationshipPathProof": verified_runtime_proof,
    },
    domain_packs=[],
    now_iso=lambda: "2026-07-16T08:03:30Z",
)
runtime_proofs = runtime_derived["selection"]["relationshipPathProof"]
check(
    "verified-execution-proof-is-preferred-and-keeps-repeated-hops",
    len(runtime_proofs) == 2
    and [item["hopIndex"] for item in runtime_proofs] == [0, 1]
    and all(item.get("proofStatus") == "verified" for item in runtime_proofs)
    and runtime_derived["validation"]["relationshipPathProven"] is True,
    runtime_proofs,
)

missing_proof = create_query_plan_receipt(
    connection,
    workspace_id="default",
    request_text="跨表来源缺少路径证明",
    source_table_key="orders",
    source_table_keys=["orders", "refunds"],
    status="blocked",
    domain_packs=[],
    now_iso=lambda: "2026-07-16T08:03:45Z",
)
check(
    "multi-table-source-without-proof-fails-path-validation",
    missing_proof["validation"]["relationshipPathProven"] is False,
    missing_proof["validation"],
)

before_source_fingerprint = multi["source"]["sourceFingerprint"]
before_data_fingerprint = multi["source"]["dataFingerprint"]
connection.execute(
    """
    UPDATE table_registry
    SET data_version = data_version + 1, row_count = row_count + 1, updated_at = ?
    WHERE workspace_id = ? AND table_key = ?
    """,
    ("2026-07-16T08:04:00Z", "default", "refunds"),
)
refreshed_relationship_proof = [{
    **relationship_proof[0],
    "dataVersions": {
        "expected": {"orders": 1, "refunds": 2},
        "current": {"orders": 1, "refunds": 2},
        "matches": True,
    },
}]
refreshed = create_query_plan_receipt(
    connection,
    workspace_id="default",
    request_text="数据更新后按渠道统计退款金额",
    source_table_key="orders",
    source_table_keys=["orders", "refunds"],
    relationship_path_proof=refreshed_relationship_proof,
    status="executed",
    execution_plan={**execution_plan, "relationships": refreshed_relationship_proof},
    joins=refreshed_relationship_proof,
    domain_packs=[],
    now_iso=lambda: "2026-07-16T08:05:00Z",
)
check(
    "any-source-data-change-invalidates-combined-data-fingerprint",
    refreshed["source"]["dataFingerprint"] != before_data_fingerprint,
    {"before": before_data_fingerprint, "after": refreshed["source"]["dataFingerprint"]},
)
check(
    "any-source-data-change-invalidates-source-fingerprint",
    refreshed["source"]["sourceFingerprint"] != before_source_fingerprint,
    {"before": before_source_fingerprint, "after": refreshed["source"]["sourceFingerprint"]},
)

failed = [item for item in checks if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-query-plan-receipt-multisource-verify/v1",
    "checks": checks,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
