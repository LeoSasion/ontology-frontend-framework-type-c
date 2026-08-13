from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from relationship_tools import build_relationship_query  # noqa: E402
from relationship_command_service import relationship_rows_for_chart  # noqa: E402
from semantic_query_execution import (  # noqa: E402
    _build_base_source,
    _filter_clause,
    build_semantic_query_execution_plan,
    execute_workspace_semantic_query as execute_workspace_semantic_query_runtime,
)
from semantic_query_planner import (  # noqa: E402
    build_semantic_query_plan,
    build_workspace_semantic_plan,
    semantic_query_prompt_directives,
)
from query_runtime_test_support import publish_sqlite_fixture_to_duckdb  # noqa: E402


TEST_REPLICA_ROOT = tempfile.TemporaryDirectory(prefix="aibi-c-cross-table-plan-")
TEST_REPLICA_PATH = Path(TEST_REPLICA_ROOT.name) / "analysis.duckdb"


def execute_workspace_semantic_query(connection: sqlite3.Connection, *args: object, **kwargs: object) -> dict[str, object]:
    publish_sqlite_fixture_to_duckdb(connection, TEST_REPLICA_PATH)
    return execute_workspace_semantic_query_runtime(
        connection,
        *args,
        **kwargs,
        duckdb_path=TEST_REPLICA_PATH,
    )


def columns(connection: sqlite3.Connection, table: str) -> list[str]:
    return [str(row[1]) for row in connection.execute(f'PRAGMA table_info("{table}")')]


def quote(value: str) -> str:
    return f'"{str(value).replace(chr(34), chr(34) * 2)}"'


def validation(versions: dict[str, int], metrics: dict[str, object]) -> str:
    return json.dumps(
        {"status": "validated", "dataVersions": versions, "metrics": metrics},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def create_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(
        """
        CREATE TABLE table_registry(
          workspace_id TEXT, table_key TEXT, display_name TEXT, physical_table TEXT,
          data_version INTEGER, updated_at TEXT DEFAULT '', row_count INTEGER DEFAULT 0,
          column_count INTEGER DEFAULT 0
        );
        CREATE TABLE field_semantics(
          workspace_id TEXT, table_key TEXT, field_name TEXT, role TEXT, confidence REAL,
          usage TEXT DEFAULT '', tags_json TEXT DEFAULT '[]', usage_json TEXT DEFAULT '{}', source TEXT DEFAULT 'auto'
        );
        CREATE TABLE metric_definitions(
          workspace_id TEXT, table_key TEXT, label TEXT, measure TEXT,
          aggregation TEXT, dimension TEXT, time_field TEXT
        );
        CREATE TABLE relationships(
          workspace_id TEXT, relation_key TEXT, left_table_key TEXT, right_table_key TEXT,
          left_field TEXT, right_field TEXT, mappings_json TEXT DEFAULT '[]', join_type TEXT,
          confidence REAL, validation_json TEXT DEFAULT '{}', filters_json TEXT DEFAULT '[]',
          preaggregation_json TEXT DEFAULT '{}', updated_at TEXT DEFAULT ''
        );
        CREATE TABLE regions(region_id TEXT, region_name TEXT);
        CREATE TABLE sites(site_id TEXT, region_id TEXT);
        CREATE TABLE assets(asset_id TEXT, site_id TEXT, asset_type TEXT);
        CREATE TABLE observations(asset_id TEXT, event_id TEXT, status TEXT, value REAL);
        CREATE TABLE owners(owner_id TEXT, owner_quota REAL);
        CREATE TABLE devices(device_id TEXT, owner_id TEXT, device_type TEXT);
        INSERT INTO regions VALUES ('R1','North'),('R2','South');
        INSERT INTO sites VALUES ('S1','R1'),('S2','R1'),('S3','R2');
        INSERT INTO assets VALUES ('A1','S1','sensor'),('A2','S2','pump'),('A3','S3','sensor');
        INSERT INTO observations VALUES
          ('A1','E1','valid',10),('A1','E2','valid',8),('A1','E3','invalid',100),
          ('A2','E4','valid',40),('A3','E5','valid',20),('A3','E6','valid',6);
        INSERT INTO owners VALUES ('O1',100),('O2',200);
        INSERT INTO devices VALUES ('D1','O1','sensor'),('D2','O2','pump');
        INSERT INTO table_registry(workspace_id,table_key,display_name,physical_table,data_version,row_count,column_count) VALUES
          ('default','regions','Regions','regions',1,2,2),
          ('default','sites','Sites','sites',1,3,2),
          ('default','assets','Assets','assets',1,3,3),
          ('default','observations','Observations','observations',1,6,4),
          ('default','owners','Owners','owners',1,2,2),
          ('default','devices','Devices','devices',1,2,3);
        INSERT INTO field_semantics(workspace_id,table_key,field_name,role,confidence) VALUES
          ('default','regions','region_id','identity_key',0.99),
          ('default','regions','region_name','dimension',0.99),
          ('default','sites','site_id','identity_key',0.99),
          ('default','sites','region_id','foreign_key',0.99),
          ('default','assets','asset_id','identity_key',0.99),
          ('default','assets','site_id','foreign_key',0.99),
          ('default','assets','asset_type','dimension',0.99),
          ('default','observations','asset_id','foreign_key',0.99),
          ('default','observations','event_id','identity_key',0.99),
          ('default','observations','status','status',0.99),
          ('default','observations','value','measure',0.99),
          ('default','owners','owner_id','identity_key',0.99),
          ('default','owners','owner_quota','measure',0.99),
          ('default','devices','device_id','identity_key',0.99),
          ('default','devices','owner_id','foreign_key',0.99),
          ('default','devices','device_type','dimension',0.99);
        INSERT INTO metric_definitions VALUES
          ('default','observations','observation_value','value','sum',NULL,NULL),
          ('default','owners','quota','owner_quota','sum',NULL,NULL);
        """
    )
    relationships = [
        (
            "regions-sites", "regions", "sites", "region_id", "region_id",
            {"leftField": "region_id", "rightField": "region_id"},
            validation(
                {"regions": 1, "sites": 1},
                {
                    "rowExpansion": 1.5, "matchedRowExpansion": 1.5,
                    "reverseRowExpansion": 1, "reverseMatchedRowExpansion": 1,
                    "leftDuplicateKeyGroups": 0, "rightDuplicateKeyGroups": 1,
                },
            ),
            [], {},
        ),
        (
            "sites-assets", "sites", "assets", "site_id", "site_id",
            {"leftField": "site_id", "rightField": "site_id"},
            validation(
                {"sites": 1, "assets": 1},
                {
                    "rowExpansion": 1, "matchedRowExpansion": 1,
                    "reverseRowExpansion": 1, "reverseMatchedRowExpansion": 1,
                    "leftDuplicateKeyGroups": 0, "rightDuplicateKeyGroups": 0,
                },
            ),
            [], {},
        ),
        (
            "assets-observations", "assets", "observations", "asset_id", "asset_id",
            {"leftField": "asset_id", "rightField": "asset_id"},
            validation(
                {"assets": 1, "observations": 1},
                {
                    "rowExpansion": 1, "matchedRowExpansion": 1,
                    "reverseRowExpansion": 1, "reverseMatchedRowExpansion": 1,
                    "leftDuplicateKeyGroups": 0, "rightDuplicateKeyGroups": 0,
                },
            ),
            [{"phase": "pre", "side": "right", "field": "status", "operator": "equals", "value": "valid"}],
            {"side": "right", "groupFields": ["asset_id"], "measures": [{"field": "value", "aggregation": "sum"}]},
        ),
        (
            "owners-devices", "owners", "devices", "owner_id", "owner_id",
            {"leftField": "owner_id", "rightField": "owner_id"},
            validation(
                {"owners": 1, "devices": 1},
                {
                    "rowExpansion": 1, "matchedRowExpansion": 1,
                    "reverseRowExpansion": 1, "reverseMatchedRowExpansion": 1,
                    "leftDuplicateKeyGroups": 0, "rightDuplicateKeyGroups": 0,
                },
            ),
            [], {},
        ),
    ]
    for relation_key, left, right, left_field, right_field, mapping, snapshot, filters, preaggregation in relationships:
        connection.execute(
            """
            INSERT INTO relationships VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "default", relation_key, left, right, left_field, right_field,
                json.dumps([mapping]), "inner", 0.99, snapshot,
                json.dumps(filters), json.dumps(preaggregation), "2026-07-16T00:00:00Z",
            ),
        )
    return connection


checks: list[dict[str, object]] = []


def check(label: str, ok: bool, detail: object = "") -> None:
    checks.append({"label": label, "ok": bool(ok), "detail": "" if ok else detail})


connection = create_connection()

null_semantics = sqlite3.connect(":memory:")
null_semantics.row_factory = sqlite3.Row
null_semantics.executescript(
    "CREATE TABLE samples(group_key TEXT, value REAL);"
    "INSERT INTO samples VALUES ('missing',NULL),('zero',0),('positive',2);"
)
numeric_clause, numeric_params = _filter_clause(
    {"field": "value", "operator": "lte", "value": "0"},
    "s",
    quote,
)
numeric_filter_count = null_semantics.execute(
    f'SELECT COUNT(*) FROM samples AS s WHERE {numeric_clause}',
    numeric_params,
).fetchone()[0]
check(
    "numeric-filter-does-not-coerce-null-to-zero",
    numeric_filter_count == 1,
    numeric_filter_count,
)
count_source, count_source_params, _ = _build_base_source(
    "samples",
    ["group_key", "value"],
    [],
    {"groupFields": ["group_key"], "measures": [{"field": "value", "aggregation": "count"}]},
    quote_identifier=quote,
)
partial_counts = {
    str(row["group_key"]): int(row["value"])
    for row in null_semantics.execute(f"SELECT * FROM {count_source}", count_source_params)
}
check(
    "preaggregated-count-preserves-source-row-count-contract",
    partial_counts == {"missing": 1, "positive": 1, "zero": 1},
    partial_counts,
)
null_semantics.close()

null_projection_payload = {
    "metricName": "metric",
    "columns": ["group_key", "metric"],
    "groups": [{"outputName": "group_key"}],
    "rows": [{"group_key": "unmatched", "metric": None}],
}
null_aggregate_values = {
    aggregation: relationship_rows_for_chart({**null_projection_payload, "aggregation": aggregation})[0]["value"]
    for aggregation in ["sum", "avg", "min", "max"]
}
check(
    "non-count-null-projection-remains-no-data",
    all(value is None for value in null_aggregate_values.values()),
    null_aggregate_values,
)
count_projection = relationship_rows_for_chart({**null_projection_payload, "aggregation": "count"})
check(
    "count-null-projection-remains-zero",
    count_projection[0]["value"] == 0.0,
    count_projection,
)

direct_null = sqlite3.connect(":memory:")
direct_null.row_factory = sqlite3.Row
direct_null.executescript(
    "CREATE TABLE dimensions(item_id TEXT, group_key TEXT);"
    "CREATE TABLE facts(item_id TEXT, value REAL);"
    "INSERT INTO dimensions VALUES ('missing','unmatched');"
)
direct_null_query = build_relationship_query(
    direct_null,
    "dimensions",
    "facts",
    ["item_id", "group_key"],
    ["item_id", "value"],
    [{"leftField": "item_id", "rightField": "item_id"}],
    group_fields=[{"side": "left", "field": "group_key"}],
    measure={"side": "right", "field": "value"},
    aggregation="avg",
    join_type="left",
    quote_identifier=quote,
)
direct_null_rows = relationship_rows_for_chart(direct_null_query)
check(
    "direct-left-join-average-preserves-null-before-and-after-projection",
    direct_null_query["rows"][0][direct_null_query["metricName"]] is None
    and direct_null_rows[0]["value"] is None,
    {"query": direct_null_query, "projected": direct_null_rows},
)
direct_null.close()

prompt = "按 region_name 和 asset_type 看 observation_value"
semantic = build_workspace_semantic_plan(connection, "default", prompt, selected_table_key="regions", table_columns=columns)
execution = build_semantic_query_execution_plan(semantic)
check(
    "three-hop-and-intermediate-targets-merge-into-one-linear-path",
    semantic["status"] == "ready"
    and len(semantic["joinPlan"]["targets"]) == 2
    and execution["status"] == "ready"
    and execution["pathTables"] == ["regions", "sites", "assets", "observations"]
    and len(execution["relationships"]) == 3,
    {"semantic": semantic, "execution": execution},
)

natural_semantic = build_workspace_semantic_plan(connection, "default", prompt, table_columns=columns)
natural_result = execute_workspace_semantic_query(
    connection,
    "default",
    prompt,
    limit=20,
    table_columns=columns,
    quote_identifier=quote,
    build_relationship_query=build_relationship_query,
    semantic_plan=natural_semantic,
)
check(
    "natural-cross-table-prompt-selects-dimension-root-and-executes",
    natural_semantic["status"] == "ready"
    and natural_semantic["joinPlan"]["rootTable"] == "regions"
    and natural_result.get("executed") is True,
    {"semantic": natural_semantic, "result": natural_result},
)

result = execute_workspace_semantic_query(
    connection,
    "default",
    prompt,
    selected_table_key="regions",
    limit=20,
    table_columns=columns,
    quote_identifier=quote,
    build_relationship_query=build_relationship_query,
    semantic_plan=semantic,
)
rows = result.get("relationshipQuery", {}).get("rows", [])
metric = result.get("relationshipQuery", {}).get("metricName")
values = {
    (row.get("regions.region_name"), row.get("assets.asset_type")): float(row.get(metric) or 0)
    for row in rows
}
proof = result.get("relationshipPathProof") or {}
check(
    "three-hop-filter-and-preaggregation-return-exact-values",
    result.get("executed") is True
    and values == {("North", "sensor"): 18, ("North", "pump"): 40, ("South", "sensor"): 26},
    result,
)
check(
    "every-hop-has-runtime-grain-cardinality-fd-filter-preaggregation-and-version-proof",
    proof.get("status") == "verified"
    and len(proof.get("hopProofs") or []) == 3
    and all(
        hop.get("proofStatus") == "verified"
        and isinstance(hop.get("inputRows"), int)
        and isinstance(hop.get("outputRows"), int)
        and hop.get("functionDependencyProof", {}).get("status") in {"proven", "not-required"}
        and hop.get("dataVersions", {}).get("matches") is True
        for hop in proof.get("hopProofs") or []
    )
    and proof["hopProofs"][2]["filterProof"]["status"] == "applied"
    and proof["hopProofs"][2]["preaggregationProof"]["status"] == "applied"
    and len(str(proof.get("fingerprint") or "")) == 64,
    proof,
)

post_filter_fd_connection = create_connection()
post_filter_fd_connection.executescript(
    "DELETE FROM regions; DELETE FROM sites; DELETE FROM assets; DELETE FROM observations;"
    "INSERT INTO regions VALUES ('R1','active'),('R1','available');"
    "INSERT INTO sites VALUES ('S1','R1');"
    "INSERT INTO assets VALUES ('A1','S1','sensor');"
    "INSERT INTO observations VALUES ('A1','E1','valid',10);"
)
post_filter_fd_connection.execute(
    "UPDATE relationships SET filters_json = ? WHERE relation_key = 'regions-sites'",
    (json.dumps([{
        "phase": "post",
        "side": "left",
        "field": "region_name",
        "operator": "contains",
        "value": "a",
    }]),),
)
post_filter_fd_result = execute_workspace_semantic_query(
    post_filter_fd_connection,
    "default",
    "看 observation_value",
    selected_table_key="regions",
    limit=20,
    table_columns=columns,
    quote_identifier=quote,
    build_relationship_query=build_relationship_query,
)
post_filter_fd_proof = (
    post_filter_fd_result.get("executionPlan", {})
    .get("relationshipPathProof", {})
    .get("hopProofs", [{}])[0]
    .get("functionDependencyProof", {})
)
check(
    "post-filter-fields-participate-in-fd-proof-before-deduplication",
    post_filter_fd_result.get("executed") is False
    and "region_name" in post_filter_fd_proof.get("dependents", [])
    and post_filter_fd_proof.get("violations") == 1
    and "path-key-not-functionally-dependent:regions"
    in post_filter_fd_result.get("executionPlan", {}).get("blockers", []),
    post_filter_fd_result,
)

request_filter_prompt = "按 region_name 看 observation_value，asset_type=sensor"
request_filtered = execute_workspace_semantic_query(
    connection,
    "default",
    request_filter_prompt,
    selected_table_key="regions",
    limit=20,
    table_columns=columns,
    quote_identifier=quote,
    build_relationship_query=build_relationship_query,
)
request_rows = request_filtered.get("relationshipQuery", {}).get("rows", [])
request_metric = request_filtered.get("relationshipQuery", {}).get("metricName")
request_values = {row.get("regions.region_name"): float(row.get(request_metric) or 0) for row in request_rows}
check(
    "request-filter-is-bound-to-intermediate-table-and-pushed-before-join",
    request_filtered.get("executed") is True
    and request_values == {"North": 18, "South": 26}
    and request_filtered["executionPlan"]["requestFilters"][0]["tableKey"] == "assets",
    request_filtered,
)

group_and_filter_prompt = "按 asset_type 看 observation_value，asset_type=sensor"
group_and_filtered = execute_workspace_semantic_query(
    connection,
    "default",
    group_and_filter_prompt,
    selected_table_key="regions",
    limit=20,
    table_columns=columns,
    quote_identifier=quote,
    build_relationship_query=build_relationship_query,
)
group_and_filter_rows = group_and_filtered.get("relationshipQuery", {}).get("rows", [])
group_and_filter_metric = group_and_filtered.get("relationshipQuery", {}).get("metricName")
group_and_filter_values = {
    row.get("assets.asset_type"): float(row.get(group_and_filter_metric) or 0)
    for row in group_and_filter_rows
}
check(
    "dimension-used-by-grain-and-filter-remains-grouped",
    group_and_filtered.get("executed") is True
    and group_and_filter_values == {"sensor": 44}
    and group_and_filtered["executionPlan"]["groups"] == [{"tableKey": "assets", "field": "asset_type"}],
    group_and_filtered,
)

orphan_connection = create_connection()
orphan_connection.execute("INSERT INTO observations VALUES ('A4','E7','valid',50)")
orphan = execute_workspace_semantic_query(
    orphan_connection,
    "default",
    group_and_filter_prompt,
    selected_table_key="regions",
    limit=20,
    table_columns=columns,
    quote_identifier=quote,
    build_relationship_query=build_relationship_query,
)
check(
    "upstream-filter-never-hides-unmatched-terminal-facts",
    orphan.get("executed") is False
    and any("late-dimension-measure-rows-unmatched" in item for item in orphan["executionPlan"]["blockers"]),
    orphan,
)

intermediate_orphan_connection = create_connection()
intermediate_orphan_connection.execute("INSERT INTO sites VALUES ('S4','R404')")
intermediate_orphan_connection.execute("INSERT INTO assets VALUES ('A4','S4','sensor')")
intermediate_orphan_connection.execute("INSERT INTO observations VALUES ('A4','E7','valid',50)")
intermediate_orphan = execute_workspace_semantic_query(
    intermediate_orphan_connection,
    "default",
    prompt,
    selected_table_key="regions",
    limit=20,
    table_columns=columns,
    quote_identifier=quote,
    build_relationship_query=build_relationship_query,
)
check(
    "terminal-facts-must-be-reachable-from-root-across-the-whole-path",
    intermediate_orphan.get("executed") is False
    and intermediate_orphan.get("executionPlan", {}).get("relationshipPathProof", {}).get(
        "terminalReachabilityProof", {}
    ).get("unreachableRows") == 1
    and any(
        "terminal-measure-rows-unreachable-from-root" in item
        for item in intermediate_orphan.get("executionPlan", {}).get("blockers", [])
    ),
    intermediate_orphan,
)

count_connection = create_connection()
count_connection.execute(
    "INSERT INTO metric_definitions VALUES ('default','observations','event_count','event_id','count',NULL,NULL)"
)
count_connection.execute("INSERT INTO observations VALUES ('A1',NULL,'valid',1)")
count_connection.execute(
    "UPDATE relationships SET preaggregation_json = ? WHERE relation_key = 'assets-observations'",
    (json.dumps({
        "side": "right",
        "groupFields": ["asset_id"],
        "measures": [{"field": "event_id", "aggregation": "count"}],
    }),),
)
count_result = execute_workspace_semantic_query(
    count_connection,
    "default",
    "按 region_name 看 event_count",
    selected_table_key="regions",
    limit=20,
    table_columns=columns,
    quote_identifier=quote,
    build_relationship_query=build_relationship_query,
)
count_rows = count_result.get("relationshipQuery", {}).get("rows", [])
count_metric = count_result.get("relationshipQuery", {}).get("metricName")
count_values = {row.get("regions.region_name"): float(row.get(count_metric) or 0) for row in count_rows}
check(
    "preaggregated-count-rolls-up-by-sum-not-row-count",
    count_result.get("executed") is True
    and count_values == {"North": 4, "South": 2}
    and count_result["relationshipQuery"]["rollupAggregation"] == "sum"
    and count_result["relationshipPathProof"]["measureRollupProof"]["status"] == "verified",
    count_result,
)

unsafe_average_connection = create_connection()
unsafe_average_connection.execute(
    "INSERT INTO metric_definitions VALUES ('default','observations','observation_average','value','avg',NULL,NULL)"
)
unsafe_average_connection.execute(
    "UPDATE relationships SET preaggregation_json = ? WHERE relation_key = 'assets-observations'",
    (json.dumps({
        "side": "right",
        "groupFields": ["asset_id"],
        "measures": [{"field": "value", "aggregation": "avg"}],
    }),),
)
unsafe_average = execute_workspace_semantic_query(
    unsafe_average_connection,
    "default",
    "按 region_name 看 observation_average",
    selected_table_key="regions",
    limit=20,
    table_columns=columns,
    quote_identifier=quote,
    build_relationship_query=build_relationship_query,
)
check(
    "metric-alias-selects-its-own-aggregation-and-blocks-unsafe-rollup",
    unsafe_average.get("executed") is False
    and any(
        item.get("metricLabel") == "observation_average" and item.get("aggregation") == "avg"
        for item in unsafe_average["semanticPlan"]["fieldResolution"]["selected"]
    )
    and any("preaggregation-non-rollup-safe" in item for item in unsafe_average["executionPlan"]["blockers"]),
    unsafe_average,
)

left_count_connection = create_connection()
left_count_connection.execute(
    "INSERT INTO metric_definitions VALUES ('default','observations','event_count','event_id','count',NULL,NULL)"
)
left_count_connection.execute("INSERT INTO assets VALUES ('A4','S3','idle')")
left_count_connection.execute("INSERT INTO observations VALUES ('A1',NULL,'valid',1)")
left_count_connection.execute(
    "UPDATE relationships SET join_type = 'left', filters_json = '[]', preaggregation_json = '{}' "
    "WHERE relation_key = 'assets-observations'"
)
left_count = execute_workspace_semantic_query(
    left_count_connection,
    "default",
    "按 asset_type 看 event_count",
    selected_table_key="assets",
    limit=20,
    table_columns=columns,
    quote_identifier=quote,
    build_relationship_query=build_relationship_query,
)
left_count_rows = left_count.get("relationshipQuery", {}).get("rows", [])
left_count_metric = left_count.get("relationshipQuery", {}).get("metricName")
left_count_values = {row.get("左表.asset_type"): float(row.get(left_count_metric) or 0) for row in left_count_rows}
check(
    "left-join-count-preserves-nullable-fact-rows-without-inventing-empty-side-rows",
    left_count.get("executed") is True
    and left_count_values.get("sensor") == 6
    and left_count_values.get("idle") == 0,
    left_count,
)
left_count_connection.execute(
    "UPDATE relationships SET preaggregation_json = ? WHERE relation_key = 'assets-observations'",
    (json.dumps({
        "side": "right",
        "groupFields": ["asset_id"],
        "measures": [{"field": "event_id", "aggregation": "count"}],
    }),),
)
left_count_preaggregated = execute_workspace_semantic_query(
    left_count_connection,
    "default",
    "按 asset_type 看 event_count",
    selected_table_key="assets",
    limit=20,
    table_columns=columns,
    quote_identifier=quote,
    build_relationship_query=build_relationship_query,
)
left_count_preaggregated_rows = left_count_preaggregated.get("relationshipQuery", {}).get("rows", [])
left_count_preaggregated_metric = left_count_preaggregated.get("relationshipQuery", {}).get("metricName")
left_count_preaggregated_values = {
    row.get("左表.asset_type"): float(row.get(left_count_preaggregated_metric) or 0)
    for row in left_count_preaggregated_rows
}
left_count_preaggregated_idle = next(
    (row for row in left_count_preaggregated_rows if row.get("左表.asset_type") == "idle"),
    {},
)
check(
    "count-results-remain-stable-when-safe-preaggregation-is-enabled",
    left_count_preaggregated.get("executed") is True
    and left_count_preaggregated_values == left_count_values
    and left_count_preaggregated_idle.get(left_count_preaggregated_metric) == 0,
    {"plain": left_count, "preaggregated": left_count_preaggregated},
)

reverse_prompt = "按 device_type 看 quota"
reverse_semantic = build_workspace_semantic_plan(
    connection, "default", reverse_prompt, selected_table_key="devices", table_columns=columns,
)
reverse_result = execute_workspace_semantic_query(
    connection,
    "default",
    reverse_prompt,
    selected_table_key="devices",
    limit=20,
    table_columns=columns,
    quote_identifier=quote,
    build_relationship_query=build_relationship_query,
    semantic_plan=reverse_semantic,
)
reverse_rows = reverse_result.get("relationshipQuery", {}).get("rows", [])
reverse_metric = reverse_result.get("relationshipQuery", {}).get("metricName")
reverse_values = {row.get("右表.device_type"): float(row.get(reverse_metric) or 0) for row in reverse_rows}
check(
    "reverse-inner-path-normalizes-mappings-and-executes",
    reverse_result.get("executed") is True
    and reverse_result["executionPlan"]["relationships"][0]["direction"] == "reverse"
    and reverse_result["executionPlan"]["relationships"][0]["traversalMappings"][0] == {
        "fromField": "owner_id", "toField": "owner_id", "leftField": "owner_id", "rightField": "owner_id",
    }
    and reverse_values == {"sensor": 100, "pump": 200},
    reverse_result,
)

connection.execute(
    """
    UPDATE relationships
    SET validation_json = ?
    WHERE relation_key = 'sites-assets'
    """,
    (
        validation(
            {"sites": 1, "assets": 1},
            {
                "rowExpansion": 2, "matchedRowExpansion": 2,
                "reverseRowExpansion": 2, "reverseMatchedRowExpansion": 2,
                "leftDuplicateKeyGroups": 1, "rightDuplicateKeyGroups": 1,
            },
        ),
    ),
)
unsafe = build_workspace_semantic_plan(connection, "default", prompt, selected_table_key="regions", table_columns=columns)
check(
    "many-to-many-fanout-is-blocked-before-execution",
    unsafe["status"] == "needs-validation"
    and "many-to-many-row-expansion" in unsafe["joinPlan"]["targets"][-1]["selectedPath"]["risks"],
    unsafe,
)

triangle_catalog = [
    {"id": "a:segment", "tableKey": "a", "tableName": "A", "field": "segment", "role": "dimension", "confidence": 0.99},
    {"id": "b:category", "tableKey": "b", "tableName": "B", "field": "category", "role": "dimension", "confidence": 0.99},
    {"id": "facts:amount", "tableKey": "facts", "tableName": "Facts", "field": "amount", "role": "measure", "aggregation": "sum", "confidence": 0.99},
]


def planner_relationship(
    relation_key: str,
    left: str,
    right: str,
    *,
    join_type: str = "inner",
    field: str = "id",
) -> dict[str, object]:
    return {
        "relationKey": relation_key,
        "leftTableKey": left,
        "rightTableKey": right,
        "fieldMappings": [{"leftField": field, "rightField": field}],
        "joinType": join_type,
        "confidence": 0.99,
        "validationStatus": "validated",
        "validationMetrics": {"matchedRowExpansion": 1, "reverseMatchedRowExpansion": 1},
        "dataVersions": {left: 1, right: 1},
        "currentDataVersions": {left: 1, right: 1},
    }


dense_relationships = [
    planner_relationship(f"noise-{index:03d}", "R", "F", field=f"k{index}")
    for index in range(255)
]
dense_relationships.extend([
    planner_relationship("r-a", "R", "A"),
    planner_relationship("r-b", "R", "B"),
    planner_relationship("a-d", "A", "D"),
    planner_relationship("b-d", "B", "D"),
    planner_relationship("d-f", "D", "F"),
])
dense_catalog = [
    {"id": "D:region_name", "tableKey": "D", "tableName": "D", "field": "region_name", "role": "dimension", "confidence": 0.99},
    {"id": "F:amount", "tableKey": "F", "tableName": "F", "field": "amount", "aliases": ["total_amount"], "role": "measure", "aggregation": "sum", "confidence": 0.99},
]
dense_plan = build_semantic_query_plan(
    "按 region_name 汇总 total_amount",
    dense_catalog,
    dense_relationships,
    selected_table_key="R",
)
dense_execution = build_semantic_query_execution_plan(dense_plan)
dense_terminal = next(
    target for target in dense_plan["joinPlan"]["targets"]
    if target["targetTable"] == "F"
)
check(
    "truncated-dense-path-search-fails-closed-before-silent-selection",
    dense_plan["joinPlan"]["pathSearchTruncated"] is True
    and dense_plan["joinPlan"]["pathSearchIncomplete"] is True
    and dense_terminal["pathSearchTruncated"] is True
    and dense_terminal["selectedPath"] is None
    and dense_plan["status"] == "needs-clarification"
    and dense_execution["status"] == "blocked"
    and dense_execution["autoExecutable"] is False,
    {"semantic": dense_plan, "execution": dense_execution},
)

dense_explicit_plan = build_semantic_query_plan(
    "按 region_name 汇总 total_amount，使用关系路径 r-b > b-d > d-f",
    dense_catalog,
    dense_relationships,
    selected_table_key="R",
)
dense_explicit_execution = build_semantic_query_execution_plan(dense_explicit_plan)
check(
    "explicit-dense-path-bypasses-incomplete-general-enumeration-safely",
    dense_explicit_plan["joinPlan"]["pathSearchTruncated"] is True
    and dense_explicit_plan["joinPlan"]["pathSearchIncomplete"] is False
    and dense_explicit_plan["status"] == "ready"
    and dense_explicit_execution["status"] == "ready"
    and [
        relationship["relationKey"]
        for relationship in dense_explicit_execution["relationships"]
    ] == ["r-b", "b-d", "d-f"],
    {"semantic": dense_explicit_plan, "execution": dense_explicit_execution},
)


duplicate_safe_relationship = planner_relationship("root-facts-safe", "root", "facts")
duplicate_stale_relationship = {
    **planner_relationship("root-facts-stale", "root", "facts"),
    "validationStatus": "stale",
}
duplicate_relationship_plan = build_semantic_query_plan(
    "按 segment 看 amount",
    [
        {"id": "root:segment", "tableKey": "root", "tableName": "Root", "field": "segment", "role": "dimension", "confidence": 0.99},
        {"id": "facts:amount", "tableKey": "facts", "tableName": "Facts", "field": "amount", "role": "measure", "aggregation": "sum", "confidence": 0.99},
    ],
    [duplicate_safe_relationship, duplicate_stale_relationship],
    selected_table_key="root",
)
duplicate_selected_path = duplicate_relationship_plan["joinPlan"]["targets"][0]["selectedPath"]
check(
    "same-semantic-relationship-keeps-safest-current-path",
    duplicate_relationship_plan["status"] == "ready"
    and duplicate_selected_path["safeForPlanning"] is True
    and duplicate_selected_path["risks"] == []
    and duplicate_selected_path["hops"][0]["relationKey"] == "root-facts-safe",
    duplicate_relationship_plan,
)


triangle_relationships = [
    planner_relationship("a-b", "a", "b"),
    planner_relationship("b-facts", "b", "facts"),
    planner_relationship("a-facts", "a", "facts"),
]
triangle_natural = build_semantic_query_plan(
    "按 segment 和 category 看 amount",
    triangle_catalog,
    triangle_relationships,
    selected_table_key="a",
)
triangle_natural_execution = build_semantic_query_execution_plan(triangle_natural)
triangle_natural_path = next(
    target["selectedPath"]
    for target in triangle_natural["joinPlan"]["targets"]
    if target["targetTable"] == "facts"
)
check(
    "triangle-graph-selects-one-executable-linear-cover",
    triangle_natural["status"] == "ready"
    and triangle_natural_execution["status"] == "ready"
    and triangle_natural_execution["pathTables"] == ["a", "b", "facts"]
    and [hop["relationKey"] for hop in triangle_natural_path["hops"]] == ["a-b", "b-facts"],
    {"semantic": triangle_natural, "execution": triangle_natural_execution},
)

triangle_explicit = build_semantic_query_plan(
    "按 segment 和 category 看 amount，使用关系路径 a-b > b-facts",
    triangle_catalog,
    triangle_relationships,
    selected_table_key="a",
)
triangle_explicit_path = next(
    target["selectedPath"]
    for target in triangle_explicit["joinPlan"]["targets"]
    if target["targetTable"] == "facts"
)
check(
    "explicit-complete-linear-cover-can-be-longer-than-shortest-target-path",
    triangle_explicit["status"] == "ready"
    and triangle_explicit["joinPlan"]["explicitPathValid"] is True
    and triangle_explicit_path["tables"] == ["a", "b", "facts"]
    and triangle_explicit["joinPlan"]["targets"][-1]["selectedPathReason"] == "explicit-relationship-path",
    triangle_explicit,
)

triangle_ambiguous = build_semantic_query_plan(
    "按 segment 和 category 看 amount",
    triangle_catalog,
    [
        planner_relationship("a-b-primary", "a", "b", field="customer_id"),
        planner_relationship("a-b-secondary", "a", "b", field="owner_id"),
        planner_relationship("b-facts", "b", "facts"),
        planner_relationship("a-facts", "a", "facts"),
    ],
    selected_table_key="a",
)
triangle_ambiguous_target = next(
    target
    for target in triangle_ambiguous["joinPlan"]["targets"]
    if target["targetTable"] == "facts"
)
check(
    "equivalent-global-linear-covers-require-clarification",
    triangle_ambiguous["status"] == "needs-clarification"
    and triangle_ambiguous_target["selectedPath"] is None
    and {
        tuple(hop["relationKey"] for hop in path["hops"])
        for path in triangle_ambiguous_target["pathCandidates"]
    } == {("a-b-primary", "b-facts"), ("a-b-secondary", "b-facts")},
    triangle_ambiguous,
)

ambiguous_paths = build_semantic_query_plan(
    "按 segment 看 amount",
    [
        {"id": "root:segment", "tableKey": "root", "tableName": "Root", "field": "segment", "role": "dimension", "confidence": 0.99},
        {"id": "facts:amount", "tableKey": "facts", "tableName": "Facts", "field": "amount", "role": "measure", "aggregation": "sum", "confidence": 0.99},
    ],
    [
        {
            "relationKey": relation_key,
            "leftTableKey": left,
            "rightTableKey": right,
            "fieldMappings": [{"leftField": "id", "rightField": "id"}],
            "joinType": "inner",
            "confidence": 0.99,
            "validationStatus": "validated",
            "validationMetrics": {"matchedRowExpansion": 1, "reverseMatchedRowExpansion": 1},
            "dataVersions": {left: 1, right: 1},
            "currentDataVersions": {left: 1, right: 1},
        }
        for relation_key, left, right in (
            ("root-a", "root", "bridge_a"),
            ("a-facts", "bridge_a", "facts"),
            ("root-b", "root", "bridge_b"),
            ("b-facts", "bridge_b", "facts"),
        )
    ],
    selected_table_key="root",
)
check(
    "equally-safe-paths-require-explicit-clarification",
    ambiguous_paths["status"] == "needs-clarification"
    and ambiguous_paths["joinPlan"]["targets"][0]["selectedPath"] is None
    and len(ambiguous_paths["joinPlan"]["targets"][0]["pathCandidates"]) == 2,
    ambiguous_paths,
)

same_tables_different_join_semantics = build_semantic_query_plan(
    "按 segment 看 amount",
    [
        {"id": "root:segment", "tableKey": "root", "tableName": "Root", "field": "segment", "role": "dimension", "confidence": 0.99},
        {"id": "facts:amount", "tableKey": "facts", "tableName": "Facts", "field": "amount", "role": "measure", "aggregation": "sum", "confidence": 0.99},
    ],
    [
        {
            "relationKey": "root-facts-by-customer",
            "leftTableKey": "root",
            "rightTableKey": "facts",
            "fieldMappings": [{"leftField": "customer_id", "rightField": "customer_id"}],
            "joinType": "inner",
            "confidence": 0.99,
            "validationStatus": "validated",
            "validationMetrics": {"matchedRowExpansion": 1, "reverseMatchedRowExpansion": 1},
            "dataVersions": {"root": 1, "facts": 1},
            "currentDataVersions": {"root": 1, "facts": 1},
        },
        {
            "relationKey": "root-facts-by-owner",
            "leftTableKey": "root",
            "rightTableKey": "facts",
            "fieldMappings": [{"leftField": "owner_id", "rightField": "owner_id"}],
            "joinType": "inner",
            "confidence": 0.99,
            "validationStatus": "validated",
            "validationMetrics": {"matchedRowExpansion": 1, "reverseMatchedRowExpansion": 1},
            "dataVersions": {"root": 1, "facts": 1},
            "currentDataVersions": {"root": 1, "facts": 1},
        },
    ],
    selected_table_key="root",
)
check(
    "same-table-sequence-with-different-join-keys-requires-clarification",
    same_tables_different_join_semantics["status"] == "needs-clarification"
    and same_tables_different_join_semantics["joinPlan"]["targets"][0]["selectedPath"] is None
    and len(same_tables_different_join_semantics["joinPlan"]["targets"][0]["pathCandidates"]) == 2,
    same_tables_different_join_semantics,
)

explicit_join_semantics = build_semantic_query_plan(
    "按 segment 看 amount，使用关系路径 root-facts-by-owner",
    [
        {"id": "root:segment", "tableKey": "root", "tableName": "Root", "field": "segment", "role": "dimension", "confidence": 0.99},
        {"id": "facts:amount", "tableKey": "facts", "tableName": "Facts", "field": "amount", "role": "measure", "aggregation": "sum", "confidence": 0.99},
        # Relation selectors can contain field-like tokens. They must stay out
        # of ordinary field resolution.
        {"id": "root:owner_id", "tableKey": "root", "tableName": "Root", "field": "owner_id", "aliases": ["owner"], "role": "identity_key", "confidence": 0.99},
    ],
    [
        {
            "relationKey": "root-facts-by-customer",
            "leftTableKey": "root",
            "rightTableKey": "facts",
            "fieldMappings": [{"leftField": "customer_id", "rightField": "customer_id"}],
            "joinType": "inner",
            "confidence": 0.99,
            "validationStatus": "validated",
            "validationMetrics": {"matchedRowExpansion": 1, "reverseMatchedRowExpansion": 1},
            "dataVersions": {"root": 1, "facts": 1},
            "currentDataVersions": {"root": 1, "facts": 1},
        },
        {
            "relationKey": "root-facts-by-owner",
            "leftTableKey": "root",
            "rightTableKey": "facts",
            "fieldMappings": [{"leftField": "owner_id", "rightField": "owner_id"}],
            "joinType": "inner",
            "confidence": 0.99,
            "validationStatus": "validated",
            "validationMetrics": {"matchedRowExpansion": 1, "reverseMatchedRowExpansion": 1},
            "dataVersions": {"root": 1, "facts": 1},
            "currentDataVersions": {"root": 1, "facts": 1},
        },
    ],
    selected_table_key="root",
)
check(
    "explicit-relation-key-resolves-path-clarification-through-every-entry-point",
    explicit_join_semantics["status"] == "ready"
    and explicit_join_semantics["joinPlan"]["targets"][0]["selectedPathReason"] == "explicit-relationship-path"
    and explicit_join_semantics["joinPlan"]["targets"][0]["selectedPath"]["hops"][0]["relationKey"] == "root-facts-by-owner"
    and {item["field"] for item in explicit_join_semantics["fieldResolution"]["selected"]} == {"segment", "amount"},
    explicit_join_semantics,
)

parsed_directives = semantic_query_prompt_directives(
    "按 segment 看 amount，使用关系路径 root-facts-by-owner > owner-ledger，使用根表 root"
)
check(
    "planning-directives-are-separated-from-the-business-question",
    parsed_directives == {
        "basePrompt": "按 segment 看 amount",
        "relationshipPath": ["root-facts-by-owner", "owner-ledger"],
        "rootTable": "root",
    },
    parsed_directives,
)

prefix_relation_key_selection = build_semantic_query_plan(
    "按 segment 看 amount，使用关系路径 root-facts-by-owner-v2",
    [
        {"id": "root:segment", "tableKey": "root", "tableName": "Root", "field": "segment", "role": "dimension", "confidence": 0.99},
        {"id": "facts:amount", "tableKey": "facts", "tableName": "Facts", "field": "amount", "role": "measure", "aggregation": "sum", "confidence": 0.99},
    ],
    [
        {
            "relationKey": relation_key,
            "leftTableKey": "root",
            "rightTableKey": "facts",
            "fieldMappings": [{"leftField": left_field, "rightField": left_field}],
            "joinType": "inner",
            "confidence": 0.99,
            "validationStatus": "validated",
            "validationMetrics": {"matchedRowExpansion": 1, "reverseMatchedRowExpansion": 1},
            "dataVersions": {"root": 1, "facts": 1},
            "currentDataVersions": {"root": 1, "facts": 1},
        }
        for relation_key, left_field in (
            ("root-facts-by-owner", "owner_id"),
            ("root-facts-by-owner-v2", "delegated_owner_id"),
        )
    ],
    selected_table_key="root",
)
check(
    "explicit-path-matches-ordered-relation-keys-not-substrings",
    prefix_relation_key_selection["status"] == "ready"
    and prefix_relation_key_selection["joinPlan"]["explicitPathValid"] is True
    and prefix_relation_key_selection["joinPlan"]["targets"][0]["selectedPath"]["hops"][0]["relationKey"] == "root-facts-by-owner-v2",
    prefix_relation_key_selection,
)

missing_version_connection = create_connection()
missing_version_connection.execute(
    "UPDATE relationships SET validation_json = ? WHERE relation_key = 'sites-assets'",
    (json.dumps({
        "status": "validated",
        "metrics": {
            "matchedRowExpansion": 1,
            "reverseMatchedRowExpansion": 1,
            "leftDuplicateKeyGroups": 0,
            "rightDuplicateKeyGroups": 0,
        },
    }),),
)
missing_version_plan = build_workspace_semantic_plan(
    missing_version_connection,
    "default",
    prompt,
    selected_table_key="regions",
    table_columns=columns,
)
check(
    "validated-relationship-without-version-evidence-is-not-executable",
    missing_version_plan["status"] == "needs-validation"
    and any(
        "missing-relationship-version-evidence" in target.get("selectedPath", {}).get("risks", [])
        for target in missing_version_plan["joinPlan"]["targets"]
        if target.get("selectedPath")
    ),
    missing_version_plan,
)

connection = create_connection()
before_drift = build_workspace_semantic_plan(connection, "default", prompt, selected_table_key="regions", table_columns=columns)
connection.execute("UPDATE table_registry SET data_version = 2 WHERE table_key = 'assets'")
after_drift = build_workspace_semantic_plan(connection, "default", prompt, selected_table_key="regions", table_columns=columns)
check(
    "any-intermediate-data-version-drift-blocks-reuse",
    before_drift["status"] == "ready"
    and after_drift["status"] == "needs-validation"
    and any(
        "relationship-version-mismatch" in target["selectedPath"]["risks"]
        for target in after_drift["joinPlan"]["targets"]
        if target.get("selectedPath")
    ),
    after_drift,
)

failed = [item for item in checks if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-cross-table-planning-p2-verify/v1",
    "checks": checks,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
