from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from dataclasses import replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from semantic_query_planner import build_workspace_semantic_plan  # noqa: E402
from semantic_query_execution import (  # noqa: E402
    build_semantic_query_execution_plan,
    execute_workspace_semantic_query as execute_workspace_semantic_query_runtime,
)
from relationship_tools import build_relationship_query  # noqa: E402
from context_pack_service import workspace_schema_fingerprint  # noqa: E402
from query_runtime_test_support import (  # noqa: E402
    FixtureTable,
    fixture_table_columns,
    initialize_fixture_control_plane,
    publish_fixture_tables_to_duckdb,
)


TEST_REPLICA_ROOT = tempfile.TemporaryDirectory(prefix="aibi-c-semantic-plan-")
TEST_REPLICA_PATH = Path(TEST_REPLICA_ROOT.name) / "analysis.duckdb"
FIXTURE_STATES: dict[int, dict[str, FixtureTable]] = {}


INITIAL_FIXTURES = (
    FixtureTable(
        workspace_id="default",
        table_key="orders",
        physical_table="orders",
        columns=(("order_id", "VARCHAR"), ("channel", "VARCHAR"), ("month", "VARCHAR"), ("amount", "DOUBLE"), ("status", "VARCHAR")),
        rows=(("O1", "Douyin", "2026-07", 100.0, "paid"), ("O1", "Douyin", "2026-07", 200.0, "paid"), ("O2", "Tmall", "2026-07", 150.0, "paid")),
        display_name="订单表",
    ),
    FixtureTable(
        workspace_id="default",
        table_key="items",
        physical_table="items",
        columns=(("order_id", "VARCHAR"), ("item_id", "VARCHAR")),
        rows=(("O1", "I1"), ("O2", "I3")),
        display_name="订单明细表",
    ),
    FixtureTable(
        workspace_id="default",
        table_key="refunds",
        physical_table="refunds",
        columns=(("order_id", "VARCHAR"), ("item_id", "VARCHAR"), ("amount", "DOUBLE"), ("refund_amount", "DOUBLE"), ("status", "VARCHAR")),
        rows=(("O1", "I1", 10.0, 10.0, "success"), ("O2", "I3", 5.0, 5.0, "pending")),
        display_name="退款表",
    ),
)


def fixture_tables(connection: sqlite3.Connection) -> list[FixtureTable]:
    return list(FIXTURE_STATES[id(connection)].values())


def replace_fixture_rows(connection: sqlite3.Connection, table_key: str, rows: tuple[tuple[object, ...], ...]) -> None:
    current = FIXTURE_STATES[id(connection)][table_key]
    FIXTURE_STATES[id(connection)][table_key] = replace(current, rows=rows)


def execute_workspace_semantic_query(connection: sqlite3.Connection, *args: object, **kwargs: object) -> dict[str, object]:
    publish_fixture_tables_to_duckdb(connection, TEST_REPLICA_PATH, fixture_tables(connection), reset=True)
    return execute_workspace_semantic_query_runtime(
        connection,
        *args,
        **kwargs,
        duckdb_path=TEST_REPLICA_PATH,
    )


def create_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    initialize_fixture_control_plane(connection)
    connection.executescript(
        """
        INSERT INTO field_semantics(workspace_id, table_key, field_name, role, usage, confidence) VALUES
          ('default', 'orders', 'order_id', 'identity_key', 'fixture', 0.98),
          ('default', 'orders', 'channel', 'dimension', 'fixture', 0.95),
          ('default', 'orders', 'month', 'event_time', 'fixture', 0.92),
          ('default', 'orders', 'amount', 'measure', 'fixture', 0.88),
          ('default', 'orders', 'status', 'status', 'fixture', 0.91),
          ('default', 'items', 'order_id', 'identity_key', 'fixture', 0.96),
          ('default', 'items', 'item_id', 'identity_key', 'fixture', 0.96),
          ('default', 'refunds', 'item_id', 'identity_key', 'fixture', 0.96),
          ('default', 'refunds', 'amount', 'measure', 'fixture', 0.90),
          ('default', 'refunds', 'refund_amount', 'measure', 'fixture', 0.97),
          ('default', 'refunds', 'status', 'status', 'fixture', 0.91);
        INSERT INTO metric_definitions(
          metric_key, workspace_id, label, table_key, measure, aggregation,
          dimension, time_field, value_format, created_at
        ) VALUES
          ('orders-channel', 'default', '渠道', 'orders', 'amount', 'sum', 'channel', 'month', 'number', '2026-07-13T00:00:00Z'),
          ('orders-month', 'default', '月份', 'orders', 'amount', 'sum', 'month', 'month', 'number', '2026-07-13T00:00:00Z'),
          ('refund-amount', 'default', '退款金额', 'refunds', 'refund_amount', 'sum', NULL, NULL, 'number', '2026-07-13T00:00:00Z');
        INSERT INTO relationships(
          relation_key, workspace_id, name, left_table_key, right_table_key,
          left_field, right_field, mappings_json, join_type, confidence,
          validation_json, filters_json, preaggregation_json, created_at, updated_at
        ) VALUES
          ('orders-items', 'default', 'orders-items', 'orders', 'items', 'order_id', 'order_id', '[{"leftField":"order_id","rightField":"order_id"}]', 'inner', 0.91, '{"status":"validated","dataVersions":{"orders":1,"items":1},"metrics":{"rowExpansion":1}}', '[]', '{}', '2026-07-13T00:00:00Z', '2026-07-13T00:00:00Z'),
          ('items-refunds', 'default', 'items-refunds', 'items', 'refunds', 'item_id', 'item_id', '[{"leftField":"item_id","rightField":"item_id"}]', 'inner', 0.89, '{"status":"validated","dataVersions":{"items":1,"refunds":1},"metrics":{"rowExpansion":1}}', '[]', '{}', '2026-07-13T00:00:00Z', '2026-07-13T00:00:00Z');
        """
    )
    FIXTURE_STATES[id(connection)] = {table.table_key: table for table in INITIAL_FIXTURES}
    publish_fixture_tables_to_duckdb(connection, TEST_REPLICA_PATH, fixture_tables(connection), reset=True)
    return connection


checks: list[dict[str, object]] = []


def check(label: str, ok: bool, detail: object) -> None:
    checks.append({"label": label, "ok": ok, "detail": detail if not ok else ""})


connection = create_connection()
ambiguous = build_workspace_semantic_plan(connection, "default", "看 amount", table_columns=fixture_table_columns)
check(
    "same-name-field-needs-table-clarification",
    ambiguous["status"] == "needs-clarification" and len(ambiguous["fieldResolution"]["unresolved"]) == 1,
    ambiguous,
)

explicit = build_workspace_semantic_plan(connection, "default", "看退款表的 amount", table_columns=fixture_table_columns)
check(
    "explicit-table-resolves-same-name-field",
    explicit["status"] == "ready" and explicit["fieldResolution"]["selected"][0]["tableKey"] == "refunds",
    explicit,
)

combined_ambiguity = build_workspace_semantic_plan(connection, "default", "看 amount 和 status", table_columns=fixture_table_columns)
check(
    "multiple-ambiguous-fields-return-one-combined-bundle",
    combined_ambiguity["status"] == "needs-clarification"
    and len(combined_ambiguity["fieldResolution"]["unresolved"]) == 2
    and {item["mention"] for item in combined_ambiguity["fieldResolution"]["unresolved"]} == {"amount", "status"},
    combined_ambiguity,
)
combined_explicit = build_workspace_semantic_plan(connection, "default", "看订单表的 amount 和退款表的 status", table_columns=fixture_table_columns)
check(
    "combined-table-field-bindings-resolve-before-path-safety-validation",
    combined_explicit["status"] == "needs-validation"
    and len(combined_explicit["fieldResolution"]["unresolved"]) == 0
    and all(binding["reason"] == "explicit-table-field" for binding in combined_explicit["fieldResolution"]["bindings"])
    and combined_explicit["joinPlan"]["rootTable"] == "refunds"
    and "missing-reverse-row-expansion-evidence" in combined_explicit["joinPlan"]["targets"][0]["selectedPath"]["risks"],
    combined_explicit,
)

selected_context = build_workspace_semantic_plan(
    connection,
    "default",
    "筛选 channel=Douyin",
    selected_table_key="orders",
    table_columns=fixture_table_columns,
)
check(
    "selected-object-context-resolves-same-name-field",
    selected_context["status"] == "ready"
    and selected_context["fieldResolution"]["selected"][0]["tableKey"] == "orders"
    and selected_context["fieldResolution"]["bindings"][0]["reason"] == "selected-object-context",
    selected_context,
)

multi_hop = build_workspace_semantic_plan(connection, "default", "按 channel 和 month 看退款金额", table_columns=fixture_table_columns)
selected_path = multi_hop["joinPlan"]["targets"][0]["selectedPath"] if multi_hop["joinPlan"]["targets"] else None
check(
    "multi-dimension-two-hop-plan",
    multi_hop["status"] == "ready"
    and len(multi_hop["grain"]["dimensions"]) >= 2
    and len(multi_hop["grain"]["measures"]) >= 1
    and selected_path
    and len(selected_path["hops"]) == 2,
    multi_hop,
)

connection.execute("DELETE FROM relationships")
missing = build_workspace_semantic_plan(connection, "default", "按 channel 看退款金额", table_columns=fixture_table_columns)
check("missing-relationship-blocks-plan", missing["status"] == "needs-relationship", missing)

connection.execute(
    """INSERT INTO relationships(
      relation_key, workspace_id, name, left_table_key, right_table_key,
      left_field, right_field, mappings_json, join_type, confidence,
      validation_json, filters_json, preaggregation_json, created_at, updated_at
    ) VALUES (
      'orders-refunds-low', 'default', 'orders-refunds-low', 'orders', 'refunds',
      'order_id', 'item_id', '[{\"leftField\":\"order_id\",\"rightField\":\"item_id\"}]', 'inner', 0.2,
      '{\"status\":\"validated\",\"dataVersions\":{\"orders\":1,\"refunds\":1},\"metrics\":{\"rowExpansion\":1}}',
      '[]', '{}', '2026-07-13T00:00:00Z', '2026-07-13T00:00:00Z'
    )"""
)
low_confidence = build_workspace_semantic_plan(connection, "default", "按 channel 看退款金额", table_columns=fixture_table_columns)
check("low-confidence-path-needs-validation", low_confidence["status"] == "needs-validation", low_confidence)
check(
    "semantic-plan-never-auto-executes",
    all(plan["autoExecutable"] is False for plan in [ambiguous, explicit, selected_context, multi_hop, missing, low_confidence]),
    {},
)

execution_connection = create_connection()
execution_connection.execute("DELETE FROM relationships")
execution_connection.execute(
    """
    INSERT INTO relationships(
      relation_key, workspace_id, name, left_table_key, right_table_key,
      left_field, right_field, mappings_json, join_type, confidence,
      validation_json, filters_json, preaggregation_json, created_at, updated_at
    ) VALUES(
      'orders-refunds', 'default', 'orders-refunds', 'orders', 'refunds', 'order_id', 'order_id',
      '[{"leftField":"order_id","rightField":"order_id"}]', 'left', 0.96,
      '{"status":"validated","dataVersions":{"orders":1,"refunds":1},"metrics":{"rowExpansion":1}}',
      '[]', '{"side":"right","groupFields":["order_id"],"measures":[{"field":"refund_amount","aggregation":"sum"}]}',
      '2026-07-13T00:00:00Z', '2026-07-13T00:00:00Z'
    )
    """
)
single_hop_semantic = build_workspace_semantic_plan(execution_connection, "default", "按 channel 看退款金额", table_columns=fixture_table_columns)
single_hop_execution = build_semantic_query_execution_plan(single_hop_semantic)
check(
    "validated-single-hop-builds-hashed-execution-plan",
    single_hop_execution["status"] == "ready"
    and single_hop_execution["autoExecutable"] is True
    and len(single_hop_execution["planHash"]) == 64
    and single_hop_execution["measure"]["aggregation"] == "sum",
    single_hop_execution,
)
executed = execute_workspace_semantic_query(
    execution_connection,
    "default",
    "按 channel 看退款金额",
    limit=20,
    table_columns=fixture_table_columns,
    quote_identifier=lambda value: f'"{str(value).replace(chr(34), chr(34) * 2)}"',
    build_relationship_query=build_relationship_query,
)
execution_rows = executed.get("relationshipQuery", {}).get("rows", [])
execution_metric = executed.get("relationshipQuery", {}).get("metricName")
execution_values = {row.get("左表.channel"): row.get(execution_metric) for row in execution_rows}
check(
    "validated-single-hop-executes-whitelist-query",
    executed["executed"] is True
    and float(execution_values.get("Douyin") or 0) == 10
    and float(execution_values.get("Tmall") or 0) == 5,
    executed,
)
replace_fixture_rows(
    execution_connection,
    "orders",
    (("O1", "Douyin", "2026-07", 100.0, "paid"), ("O1", "Other", "2026-07", 200.0, "paid"), ("O2", "Tmall", "2026-07", 150.0, "paid")),
)
unsafe_grain = execute_workspace_semantic_query(
    execution_connection,
    "default",
    "按 channel 看退款金额",
    limit=20,
    table_columns=fixture_table_columns,
    quote_identifier=lambda value: f'"{str(value).replace(chr(34), chr(34) * 2)}"',
    build_relationship_query=build_relationship_query,
)
check(
    "non-functional-left-group-blocks-right-measure-execution",
    unsafe_grain["executed"] is False
    and "left-group-not-functionally-dependent-on-join-key" in unsafe_grain["executionPlan"]["blockers"],
    unsafe_grain,
)
replace_fixture_rows(
    execution_connection,
    "orders",
    (("O1", "Douyin", "2026-07", 100.0, "paid"), ("O1", "Douyin", "2026-07", 200.0, "paid"), ("O2", "Tmall", "2026-07", 150.0, "paid")),
)
two_hop_connection = create_connection()
two_hop_plan = build_workspace_semantic_plan(two_hop_connection, "default", "按 channel 和 month 看退款金额", table_columns=fixture_table_columns)
two_hop_execution = build_semantic_query_execution_plan(two_hop_plan)
two_hop_result = execute_workspace_semantic_query(
    two_hop_connection,
    "default",
    "按 channel 和 month 看退款金额",
    limit=20,
    table_columns=fixture_table_columns,
    quote_identifier=lambda value: f'"{str(value).replace(chr(34), chr(34) * 2)}"',
    build_relationship_query=build_relationship_query,
    semantic_plan=two_hop_plan,
)
two_hop_rows = two_hop_result.get("relationshipQuery", {}).get("rows", [])
two_hop_metric = two_hop_result.get("relationshipQuery", {}).get("metricName")
two_hop_values = {row.get("orders.channel"): row.get(two_hop_metric) for row in two_hop_rows}
check(
    "validated-two-hop-executes-with-root-grain-deduplication",
    two_hop_execution["status"] == "ready"
    and len(two_hop_execution["relationships"]) == 2
    and two_hop_result["executed"] is True
    and two_hop_result["relationshipQuery"]["rootDeduplicated"] is True
    and float(two_hop_values.get("Douyin") or 0) == 10
    and float(two_hop_values.get("Tmall") or 0) == 5,
    two_hop_result,
)
changed_connection = create_connection()
changed_plan = build_workspace_semantic_plan(changed_connection, "default", "按 channel 和 month 看退款金额", table_columns=fixture_table_columns)
changed_connection.execute("DELETE FROM relationships WHERE relation_key = 'items-refunds'")
changed_result = execute_workspace_semantic_query(
    changed_connection,
    "default",
    "按 channel 和 month 看退款金额",
    limit=20,
    table_columns=fixture_table_columns,
    quote_identifier=lambda value: f'"{str(value).replace(chr(34), chr(34) * 2)}"',
    build_relationship_query=build_relationship_query,
    semantic_plan=changed_plan,
)
check(
    "relationship-change-between-plan-and-execution-blocks",
    changed_result["executed"] is False and "semantic-plan-changed-before-execution" in changed_result["executionPlan"]["blockers"],
    changed_result,
)
filtered_two_hop = json.loads(json.dumps(two_hop_plan))
filtered_two_hop["joinPlan"]["targets"][0]["selectedPath"]["hops"][0]["filters"] = [{"phase": "pre", "side": "left", "field": "channel", "operator": "equals", "value": "Douyin"}]
filtered_two_hop_execution = build_semantic_query_execution_plan(filtered_two_hop)
check(
    "two-hop-filter-pushdown-is-part-of-canonical-plan",
    filtered_two_hop_execution["status"] == "ready"
    and filtered_two_hop_execution["relationships"][0]["filters"][0]["tableKey"] == "orders",
    filtered_two_hop_execution,
)
execution_connection.execute(
    "UPDATE relationships SET validation_json = '{\"status\":\"stale\",\"dataVersions\":{\"orders\":1,\"refunds\":1},\"metrics\":{\"rowExpansion\":1}}' WHERE relation_key = 'orders-refunds'"
)
stale_semantic = build_workspace_semantic_plan(execution_connection, "default", "按 channel 看退款金额", table_columns=fixture_table_columns)
check("stale-relationship-blocks-before-execution", stale_semantic["status"] == "needs-validation" and "stale-relationship" in stale_semantic["joinPlan"]["targets"][0]["selectedPath"]["risks"], stale_semantic)

fingerprint_connection = create_connection()
fingerprint_before = workspace_schema_fingerprint(fingerprint_connection, "default", "orders")
fingerprint_connection.execute("UPDATE relationships SET filters_json = '[{\"phase\":\"pre\",\"side\":\"left\",\"field\":\"channel\",\"operator\":\"equals\",\"value\":\"Douyin\"}]', updated_at = '2026-07-13T01:00:00Z' WHERE relation_key = 'orders-items'")
fingerprint_after_relationship = workspace_schema_fingerprint(fingerprint_connection, "default", "orders")
fingerprint_connection.execute("UPDATE table_registry SET data_version = 2, updated_at = '2026-07-13T02:00:00Z' WHERE table_key = 'orders'")
fingerprint_after_data = workspace_schema_fingerprint(fingerprint_connection, "default", "orders")
check(
    "confirmed-query-fingerprint-includes-relationship-and-data-versions",
    fingerprint_before != fingerprint_after_relationship and fingerprint_after_relationship != fingerprint_after_data,
    {"before": fingerprint_before, "afterRelationship": fingerprint_after_relationship, "afterData": fingerprint_after_data},
)

failed = [item for item in checks if not item["ok"]]
payload = {
    "ok": not failed,
    "schema": "aibi-semantic-query-planning-verify/v1",
    "checks": checks,
    "failedChecks": failed,
}
print(json.dumps(payload, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
