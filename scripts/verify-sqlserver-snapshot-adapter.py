from __future__ import annotations

import inspect
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from sqlserver_snapshot_adapter_service import (  # noqa: E402
    ADAPTER_ID,
    CAPABILITY_ACTIVE,
    CAPABILITY_READY_FOR_SNAPSHOT,
    CAPABILITY_READY_FOR_TEST,
    CAPABILITY_UNAVAILABLE,
    SqlServerAdapterError,
    active_capability,
    adapter_contract,
    build_snapshot_plan,
    discover_catalog,
    parse_target_policies,
    preview_statistics,
    resolve_network_binding,
    snapshot_to_staging,
    test_connection,
    validate_credential_reference,
    verify_catalog,
)
from sqlserver_snapshot_fake_driver import FakeSqlServerDriver  # noqa: E402


checks: list[dict[str, Any]] = []


def check(label: str, ok: bool, evidence: Any = None) -> None:
    checks.append({"label": label, "ok": bool(ok), "evidence": evidence})


def expect_error(label: str, code: str, action: Callable[[], Any]) -> SqlServerAdapterError | None:
    try:
        action()
    except SqlServerAdapterError as error:
        check(label, error.code == code, error.public_payload())
        return error
    except Exception as error:  # pragma: no cover - diagnostic path
        check(label, False, {"unexpected": type(error).__name__, "error": str(error)})
        return None
    check(label, False, {"error": "operation unexpectedly succeeded"})
    return None


POLICIES = {
    "finance": {
        "host": "sql.finance.internal",
        "ports": [1433],
        "databases": ["analytics"],
        "allowedCidrs": ["10.20.0.0/16"],
        "requireTls": True,
    }
}
CONFIG = {
    "workspaceId": "verify_sqlserver_workspace",
    "hostAlias": "finance",
    "port": 1433,
    "database": "analytics",
    "encryption": "required",
    "credentialRef": "env:AIBI_TEST_SQLSERVER_SECRET",
}
ENV = {
    "AIBI_TEST_SQLSERVER_SECRET": json.dumps({"username": "readonly_user", "password": "not-a-real-secret-value"}),
}
CATALOG_ROWS = [
    {
        "schema": "dbo",
        "name": "orders",
        "type": "table",
        "rowEstimate": 3,
        "columns": [
            {"name": "order_id", "dataType": "int", "nullable": False, "ordinal": 1},
            {"name": "changed_at", "dataType": "datetime2", "nullable": False, "ordinal": 2},
            {"name": "amount", "dataType": "decimal", "nullable": True, "ordinal": 3},
            {"name": "note", "dataType": "nvarchar", "nullable": True, "ordinal": 4},
        ],
        "keyCandidates": [["order_id"]],
    },
    {
        "schema": "dbo",
        "name": "customers",
        "type": "view",
        "rowEstimate": 2,
        "columns": [
            {"name": "customer_id", "dataType": "int", "nullable": False, "ordinal": 1},
            {"name": "segment", "dataType": "nvarchar", "nullable": True, "ordinal": 2},
        ],
        "keyCandidates": [["customer_id"]],
    },
]
BUSINESS_ROWS = {
    "dbo.orders": [
        {"order_id": 1, "changed_at": "2026-08-01T00:00:00", "amount": 10.0, "note": "VIP Alice"},
        {"order_id": 2, "changed_at": "2026-08-01T00:00:00", "amount": 20.0, "note": "VIP Bob"},
        {"order_id": 3, "changed_at": "2026-08-02T00:00:00", "amount": 30.0, "note": "VIP Carol"},
    ],
    "dbo.customers": [
        {"customer_id": 7, "segment": "North"},
        {"customer_id": 8, "segment": "South"},
    ],
}


def resolver(_host: str, _port: int) -> list[str]:
    return ["10.20.1.8"]


def driver(**overrides: Any) -> FakeSqlServerDriver:
    return FakeSqlServerDriver(
        peer=str(overrides.pop("peer", "10.20.1.8")),
        catalog=overrides.pop("catalog", CATALOG_ROWS),
        rows=overrides.pop("rows", BUSINESS_ROWS),
        **overrides,
    )


parsed_policy = parse_target_policies(json.dumps(POLICIES))
check("target-policy-requires-explicit-bounded-structure", parsed_policy == POLICIES, parsed_policy)
expect_error(
    "named-instance-implicit-discovery-is-blocked",
    "SQLSERVER_ALLOWLIST_INVALID",
    lambda: parse_target_policies(json.dumps({"finance": {**POLICIES["finance"], "host": "sqlhost\\instance"}})),
)
expect_error(
    "allowlist-collections-must-not-use-ambiguous-strings",
    "SQLSERVER_ALLOWLIST_INVALID",
    lambda: parse_target_policies(json.dumps({"finance": {**POLICIES["finance"], "databases": "analytics"}})),
)


missing_driver = driver(installed=False)
unavailable = adapter_contract(CONFIG, driver=missing_driver, policies=POLICIES, environ=ENV)
check(
    "optional-driver-missing-is-unavailable-without-install-or-fallback",
    unavailable["capability"] == CAPABILITY_UNAVAILABLE
    and unavailable["available"] is False
    and unavailable["permissions"]["fallback"] == "none",
    unavailable,
)

ready = adapter_contract(CONFIG, driver=driver(), policies=POLICIES, environ=ENV)
ready_text = json.dumps(ready, ensure_ascii=False)
check(
    "configured-driver-policy-and-secret-ref-are-ready-for-test",
    ready["adapterId"] == ADAPTER_ID
    and ready["capability"] == CAPABILITY_READY_FOR_TEST
    and ready["permissions"]["arbitrarySql"] is False
    and ready["credentials"]["valuesInReceipts"] is False
    and "readonly_user" not in ready_text
    and "not-a-real-secret-value" not in ready_text
    and "env:AIBI_TEST_SQLSERVER_SECRET" not in ready_text,
    ready,
)

expect_error(
    "literal-secret-is-rejected-before-network",
    "SQLSERVER_SECRET_REF_REQUIRED",
    lambda: validate_credential_reference("readonly_user:not-a-real-secret-value"),
)
expect_error(
    "unallowlisted-alias-is-blocked",
    "SQLSERVER_TARGET_NOT_ALLOWLISTED",
    lambda: resolve_network_binding({**CONFIG, "hostAlias": "unapproved"}, POLICIES, resolver=resolver),
)
expect_error(
    "resolved-address-outside-approved-cidr-is-rebinding-blocked",
    "SQLSERVER_DNS_REBINDING_BLOCKED",
    lambda: resolve_network_binding(CONFIG, POLICIES, resolver=lambda _host, _port: ["203.0.113.8"]),
)
expect_error(
    "loopback-address-is-blocked-even-if-policy-is-misconfigured",
    "SQLSERVER_NETWORK_CLASS_BLOCKED",
    lambda: resolve_network_binding(
        CONFIG,
        {"finance": {**POLICIES["finance"], "allowedCidrs": ["127.0.0.0/8"]}},
        resolver=lambda _host, _port: ["127.0.0.1"],
    ),
)

connection_receipt = test_connection(
    CONFIG,
    driver=driver(),
    policies=POLICIES,
    resolver=resolver,
    environ=ENV,
)
connection_text = json.dumps(connection_receipt, ensure_ascii=False)
check(
    "connection-test-verifies-peer-tls-and-read-only-without-secret-leak",
    connection_receipt["capability"] == CAPABILITY_READY_FOR_TEST
    and connection_receipt["readOnly"]["verified"] is True
    and connection_receipt["sideEffects"]["remoteWrite"] is False
    and "readonly_user" not in connection_text
    and "not-a-real-secret-value" not in connection_text,
    connection_receipt,
)
expect_error(
    "write-capable-credential-is-blocked",
    "SQLSERVER_CREDENTIAL_NOT_READ_ONLY",
    lambda: test_connection(CONFIG, driver=driver(read_only=False), policies=POLICIES, resolver=resolver, environ=ENV),
)


class RebindingResolver:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, _host: str, _port: int) -> list[str]:
        self.calls += 1
        return ["10.20.1.8"] if self.calls == 1 else ["10.20.1.9"]


expect_error(
    "dns-binding-change-during-connect-is-blocked",
    "SQLSERVER_DNS_REBINDING_BLOCKED",
    lambda: test_connection(CONFIG, driver=driver(), policies=POLICIES, resolver=RebindingResolver(), environ=ENV),
)

catalog = discover_catalog(
    CONFIG,
    driver=driver(),
    policies=POLICIES,
    resolver=resolver,
    environ=ENV,
    max_tables=4,
    max_columns_per_table=8,
)
catalog_text = json.dumps(catalog, ensure_ascii=False)
check(
    "catalog-is-bounded-fingerprinted-and-row-free",
    catalog["schema"] == "aibi-sqlserver-catalog/v1"
    and len(catalog["resources"]) == 2
    and len(catalog["catalogFingerprint"]) == 64
    and catalog["rawRowsReturned"] is False
    and "VIP Alice" not in catalog_text,
    catalog,
)
tampered_catalog = json.loads(json.dumps(catalog))
tampered_catalog["resources"][0]["columns"][0]["nullable"] = True
expect_error(
    "tampered-catalog-is-blocked-before-plan-or-preview",
    "SQLSERVER_CATALOG_FINGERPRINT_MISMATCH",
    lambda: verify_catalog(tampered_catalog),
)

preview = preview_statistics(
    CONFIG,
    catalog,
    ["dbo.orders"],
    driver=driver(),
    policies=POLICIES,
    resolver=resolver,
    environ=ENV,
)
preview_text = json.dumps(preview, ensure_ascii=False)
note_stats = next(item for item in preview["statistics"][0]["columns"] if item["name"] == "note")
amount_stats = next(item for item in preview["statistics"][0]["columns"] if item["name"] == "amount")
check(
    "preview-returns-only-bounded-statistics-and-redacts-string-values",
    preview["rawRowsReturned"] is False
    and "min" not in note_stats
    and "max" not in note_stats
    and amount_stats["min"] == 10.0
    and "VIP Alice" not in preview_text,
    preview,
)

SELECTIONS = [
    {
        "resourceKey": "dbo.orders",
        "columns": ["changed_at", "order_id", "amount", "note"],
        "orderBy": ["changed_at", "order_id"],
        "stableOrderingConfirmed": True,
        "watermark": {
            "column": "changed_at",
            "after": "2026-08-01T00:00:00",
            "tieBreakers": ["order_id"],
            "afterTieBreakers": [1],
        },
        "targetTableKey": "sql_orders",
    },
    {
        "resourceKey": "dbo.customers",
        "columns": ["customer_id", "segment"],
        "orderBy": ["customer_id"],
        "targetTableKey": "sql_customers",
    },
]

plan = build_snapshot_plan(
    CONFIG,
    catalog,
    SELECTIONS,
    request_key="sqlserver-verify-request-1",
    budget={"maxRowsPerTable": 10, "maxBytes": 1024 * 1024, "timeoutSeconds": 5, "pageSize": 2},
    created_at="2026-08-13T00:00:00Z",
)
same_plan = build_snapshot_plan(
    CONFIG,
    catalog,
    SELECTIONS,
    request_key="sqlserver-verify-request-1",
    budget={"maxRowsPerTable": 10, "maxBytes": 1024 * 1024, "timeoutSeconds": 5, "pageSize": 2},
    created_at="2026-08-13T00:00:00Z",
)
plan_text = json.dumps(plan, ensure_ascii=False)
check(
    "plan-freezes-catalog-ordering-watermark-budget-and-idempotent-fingerprint",
    plan["capability"] == CAPABILITY_READY_FOR_SNAPSHOT
    and plan["planFingerprint"] == same_plan["planFingerprint"]
    and plan["selections"][0]["watermark"]["afterTieBreakers"] == [1]
    and plan["activation"]["required"] is True
    and "credentialRef" not in plan_text
    and "not-a-real-secret-value" not in plan_text,
    plan,
)

expect_error(
    "selection-without-stable-order-is-blocked",
    "SQLSERVER_STABLE_ORDER_REQUIRED",
    lambda: build_snapshot_plan(
        CONFIG,
        catalog,
        [{"resourceKey": "dbo.orders", "columns": ["note"], "orderBy": ["note"], "targetTableKey": "unsafe"}],
        request_key="unstable",
    ),
)
expect_error(
    "incremental-boundary-without-tie-breaker-values-is-blocked",
    "SQLSERVER_WATERMARK_BOUNDARY_INVALID",
    lambda: build_snapshot_plan(
        CONFIG,
        catalog,
        [{
            "resourceKey": "dbo.orders",
            "columns": ["changed_at", "order_id"],
            "orderBy": ["changed_at", "order_id"],
            "stableOrderingConfirmed": True,
            "watermark": {"column": "changed_at", "after": "2026-08-01T00:00:00", "tieBreakers": ["order_id"]},
            "targetTableKey": "unsafe_incremental",
        }],
        request_key="unsafe-watermark",
    ),
)
expect_error(
    "estimated-row-budget-is-enforced-before-snapshot",
    "SQLSERVER_ROW_BUDGET_EXCEEDED",
    lambda: build_snapshot_plan(
        CONFIG,
        catalog,
        [{"resourceKey": "dbo.orders", "columns": ["order_id"], "orderBy": ["order_id"], "targetTableKey": "over_budget", "estimatedRows": 11}],
        request_key="over-budget",
        budget={"maxRowsPerTable": 10},
    ),
)

verify_root = Path(tempfile.mkdtemp(prefix="aibi-c-sqlserver-adapter-"))
try:
    success_driver = driver()
    snapshot = snapshot_to_staging(
        CONFIG,
        plan,
        driver=success_driver,
        policies=POLICIES,
        staging_root=verify_root,
        resolver=resolver,
        environ=ENV,
        now=lambda: "2026-08-13T00:01:00Z",
    )
    snapshot_text = json.dumps(snapshot, ensure_ascii=False)
    manifests = list(verify_root.rglob("manifest.json"))
    staged_parquet = list(verify_root.rglob("*.parquet"))
    check(
        "snapshot-is-stable-bounded-and-staged-before-activation",
        snapshot["capability"] == CAPABILITY_READY_FOR_SNAPSHOT
        and snapshot["totalRows"] == 4
        and snapshot["activation"]["status"] == "pending"
        and len(manifests) == 1
        and len(staged_parquet) == 2
        and all(item["sha256"] for item in snapshot["tables"])
        and str(verify_root) not in snapshot_text
        and "VIP Alice" not in snapshot_text
        and "not-a-real-secret-value" not in snapshot_text,
        snapshot,
    )
    replay = snapshot_to_staging(
        CONFIG,
        plan,
        driver=driver(),
        policies=POLICIES,
        staging_root=verify_root,
        resolver=resolver,
        environ=ENV,
    )
    check("same-plan-snapshot-is-idempotent", replay["idempotentReplay"] is True and replay["artifactKey"] == snapshot["artifactKey"], replay)

    active = active_capability(
        plan,
        snapshot,
        {
            "committed": True,
            "journal": {
                "workspaceId": CONFIG["workspaceId"],
                "journalKey": "activation_verify_sqlserver",
                "planFingerprint": plan["planFingerprint"],
                "phase": "finalized",
                "outcome": "committed",
            },
        },
    )
    check("active-requires-finalized-durable-activation", active["capability"] == CAPABILITY_ACTIVE, active)
    expect_error(
        "pending-activation-cannot-be-called-active",
        "SQLSERVER_ACTIVATION_NOT_FINALIZED",
        lambda: active_capability(plan, snapshot, {"journal": {"workspaceId": CONFIG["workspaceId"], "phase": "replica_published"}}),
    )

    byte_plan = build_snapshot_plan(
        CONFIG,
        catalog,
        [SELECTIONS[1]],
        request_key="sqlserver-byte-budget",
        budget={"maxRowsPerTable": 10, "maxBytes": 24, "timeoutSeconds": 5},
        created_at="2026-08-13T00:01:30Z",
    )
    expect_error(
        "byte-budget-is-enforced-on-sealed-parquet",
        "SQLSERVER_BYTE_BUDGET_EXCEEDED",
        lambda: snapshot_to_staging(
            CONFIG,
            byte_plan,
            driver=driver(),
            policies=POLICIES,
            staging_root=verify_root,
            resolver=resolver,
            environ=ENV,
        ),
    )
    check("over-byte-budget-snapshot-leaves-no-artifact", not any(path.name == byte_plan["staging"]["artifactKey"] for path in verify_root.rglob("*")))

    staged_parquet[0].write_bytes(staged_parquet[0].read_bytes() + b"tampered\n")
    expect_error(
        "idempotent-replay-revalidates-manifest-and-file-hashes",
        "SQLSERVER_ARTIFACT_INTEGRITY_FAILED",
        lambda: snapshot_to_staging(
            CONFIG,
            plan,
            driver=driver(),
            policies=POLICIES,
            staging_root=verify_root,
            resolver=resolver,
            environ=ENV,
        ),
    )

    failure_plan = build_snapshot_plan(
        CONFIG,
        catalog,
        SELECTIONS,
        request_key="sqlserver-partial-failure",
        budget={"maxRowsPerTable": 10, "maxBytes": 1024 * 1024, "timeoutSeconds": 5},
        created_at="2026-08-13T00:02:00Z",
    )
    expect_error(
        "partial-table-failure-leaves-no-publishable-artifact",
        "SQLSERVER_SNAPSHOT_PARTIAL_FAILURE",
        lambda: snapshot_to_staging(
            CONFIG,
            failure_plan,
            driver=driver(fail_on_resource="dbo.customers"),
            policies=POLICIES,
            staging_root=verify_root,
            resolver=resolver,
            environ=ENV,
        ),
    )
    failure_artifact = failure_plan["staging"]["artifactKey"]
    check(
        "partial-table-staging-is-cleaned",
        not any(path.name == failure_artifact for path in verify_root.rglob("*"))
        and not any(failure_artifact in path.name and path.name.endswith(".tmp") for path in verify_root.rglob("*")),
    )

    cancel_plan = build_snapshot_plan(
        CONFIG,
        catalog,
        SELECTIONS,
        request_key="sqlserver-cancel",
        budget={"maxRowsPerTable": 10, "maxBytes": 1024 * 1024, "timeoutSeconds": 5},
        created_at="2026-08-13T00:03:00Z",
    )
    cancel_calls = {"count": 0}

    def cancel_during_operation() -> bool:
        cancel_calls["count"] += 1
        return cancel_calls["count"] >= 8

    expect_error(
        "cancellation-is-cooperative-before-activation",
        "SQLSERVER_OPERATION_CANCELED",
        lambda: snapshot_to_staging(
            CONFIG,
            cancel_plan,
            driver=driver(),
            policies=POLICIES,
            staging_root=verify_root,
            resolver=resolver,
            environ=ENV,
            cancelled=cancel_during_operation,
        ),
    )
    check("canceled-snapshot-leaves-no-artifact", not any(path.name == cancel_plan["staging"]["artifactKey"] for path in verify_root.rglob("*")))

    timeout_plan = build_snapshot_plan(
        CONFIG,
        catalog,
        [SELECTIONS[1]],
        request_key="sqlserver-timeout",
        budget={"maxRowsPerTable": 10, "maxBytes": 1024 * 1024, "timeoutSeconds": 1},
        created_at="2026-08-13T00:03:30Z",
    )
    expect_error(
        "timeout-is-enforced-during-streaming-snapshot",
        "SQLSERVER_OPERATION_TIMEOUT",
        lambda: snapshot_to_staging(
            CONFIG,
            timeout_plan,
            driver=driver(delay_seconds=0.45),
            policies=POLICIES,
            staging_root=verify_root,
            resolver=resolver,
            environ=ENV,
        ),
    )
    check("timed-out-snapshot-leaves-no-artifact", not any(path.name == timeout_plan["staging"]["artifactKey"] for path in verify_root.rglob("*")))

    changed_catalog = json.loads(json.dumps(CATALOG_ROWS))
    changed_catalog[0]["columns"].append({"name": "new_remote_field", "dataType": "int", "nullable": True, "ordinal": 5})
    catalog_drift_plan = build_snapshot_plan(
        CONFIG,
        catalog,
        [SELECTIONS[0]],
        request_key="sqlserver-catalog-drift",
        created_at="2026-08-13T00:03:45Z",
    )
    expect_error(
        "selected-resource-schema-drift-is-blocked-before-staging-rows",
        "SQLSERVER_CATALOG_DRIFT",
        lambda: snapshot_to_staging(
            CONFIG,
            catalog_drift_plan,
            driver=driver(catalog=changed_catalog),
            policies=POLICIES,
            staging_root=verify_root,
            resolver=resolver,
            environ=ENV,
        ),
    )

    drift_plan = build_snapshot_plan(
        CONFIG,
        catalog,
        [SELECTIONS[1]],
        request_key="sqlserver-dns-drift",
        created_at="2026-08-13T00:04:00Z",
    )
    expect_error(
        "network-drift-after-plan-is-blocked-before-driver-connect",
        "SQLSERVER_PLAN_NETWORK_DRIFT",
        lambda: snapshot_to_staging(
            CONFIG,
            drift_plan,
            driver=driver(peer="10.20.1.9"),
            policies=POLICIES,
            staging_root=verify_root,
            resolver=lambda _host, _port: ["10.20.1.9"],
            environ=ENV,
        ),
    )
finally:
    shutil.rmtree(verify_root, ignore_errors=True)

signature_text = " ".join(str(inspect.signature(item)) for item in (
    test_connection, discover_catalog, preview_statistics, build_snapshot_plan, snapshot_to_staging,
))
module_source = (TOOLS / "sqlserver_snapshot_adapter_service.py").read_text(encoding="utf-8")
check(
    "adapter-public-surface-has-no-arbitrary-sql-or-auto-install-path",
    "query:" not in signature_text.casefold()
    and "sql:" not in signature_text.casefold()
    and "pip install" not in module_source.casefold()
    and "subprocess" not in module_source.casefold()
    and "_OPERATION_LOCK" in module_source
    and "SQLSERVER_ADAPTER_BUSY" in module_source,
    {"queryArgumentPresent": "query:" in signature_text.casefold(), "sqlArgumentPresent": "sql:" in signature_text.casefold()},
)

real_requested = os.environ.get("AIBI_SQLSERVER_REAL_TEST") == "1"
real_result: dict[str, Any] = {"requested": real_requested, "executed": False}
if real_requested:
    try:
        from sqlserver_snapshot_adapter_service import parse_target_policies
        from sqlserver_snapshot_pyodbc_driver import PyodbcSqlServerDriver

        real_config = json.loads(os.environ.get("AIBI_SQLSERVER_REAL_CONFIG_JSON") or "{}")
        real_receipt = test_connection(
            real_config,
            driver=PyodbcSqlServerDriver(),
            policies=parse_target_policies(),
        )
        real_result = {"requested": True, "executed": True, "ok": real_receipt.get("ok") is True}
        check("explicit-opt-in-real-sqlserver-read-only-test", real_result["ok"], real_result)
    except Exception as error:  # explicit integration failure should fail the gate
        real_result = {"requested": True, "executed": True, "ok": False, "error": type(error).__name__}
        check("explicit-opt-in-real-sqlserver-read-only-test", False, real_result)
else:
    check("real-sqlserver-test-is-explicit-opt-in", True, real_result)

failed = [item for item in checks if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-sqlserver-snapshot-adapter-verify/v1",
    "generatedBy": "scripts/verify-sqlserver-snapshot-adapter.py",
    "fakeDriverOnly": not real_requested,
    "realIntegration": real_result,
    "checks": checks,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
if failed:
    raise SystemExit(1)
