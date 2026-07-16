from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CHECKS: list[dict[str, Any]] = []


def check(label: str, ok: bool, detail: Any = None) -> None:
    CHECKS.append({"label": label, "ok": bool(ok), "detail": None if ok else detail})


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


def logical_state(path: Path) -> dict[str, list[list[Any]]]:
    with closing(sqlite3.connect(path)) as connection:
        return {
            table: [list(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY 1, 2").fetchall()]
            for table in ("data_connectors", "table_registry", "field_semantics", "relationships")
        }


def run(args: list[str], env: dict[str, str], expected: int = 0) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, "tools/bi_cli.py", "--json", *args],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    try:
        payload = json.loads(completed.stdout or completed.stderr or "{}")
    except json.JSONDecodeError:
        payload = {"parseError": True, "stdout": completed.stdout, "stderr": completed.stderr}
    check(f"cli:{args[0]}", completed.returncode == expected and isinstance(payload, dict), payload)
    return payload


def proof_args(*, filters: list[dict[str, str]] | None = None, max_sources: int = 4) -> list[str]:
    return [
        "federation-proof",
        "--connectors", "orders_connector,customers_connector",
        "--projections", json.dumps({"orders_connector": ["id", "amount"], "customers_connector": ["id", "segment"]}),
        "--relationships", "orders-customers",
        "--grain", "orders_table",
        "--entity-key", "orders_table.id",
        "--filters", json.dumps(filters or []),
        "--max-sources", str(max_sources),
    ]


with tempfile.TemporaryDirectory(prefix="aibi-c-federation-") as temp_name:
    temp = Path(temp_name)
    sqlite_path = temp / "runtime.sqlite"
    duckdb_path = temp / "runtime.duckdb"
    orders = temp / "orders.csv"
    customers = temp / "customers.csv"
    orders.write_text("id,amount\nO-1,10\nO-2,20\n", encoding="utf-8-sig")
    customers.write_text("id,segment\nO-1,A\nO-2,B\n", encoding="utf-8-sig")
    env = {
        **os.environ,
        "AIBI_HYBRID_DB_PATH": str(sqlite_path),
        "AIBI_HYBRID_DUCKDB_PATH": str(duckdb_path),
        "PYTHONIOENCODING": "utf-8",
    }

    run(["status"], env)
    for key, name, source, target in (
        ("orders_connector", "Orders", orders, "orders_table"),
        ("customers_connector", "Customers", customers, "customers_table"),
    ):
        run([
            "save-connector", "--connector", key, "--name", name, "--type", "file",
            "--status", "active", "--endpoint", str(source), "--target-table", target,
            "--import-mode", "create", "--yes",
        ], env)
        synced = run(["sync-connector", "--connector", key, "--yes"], env)
        check(f"sync:{key}", synced.get("confirmed") is True, synced)

    with closing(sqlite3.connect(sqlite_path)) as connection:
        connection.row_factory = sqlite3.Row
        versions = {
            str(row["table_key"]): int(row["data_version"])
            for row in connection.execute(
                "SELECT table_key, data_version FROM table_registry WHERE workspace_id = 'default'"
            ).fetchall()
        }
        identity_roles = {
            str(row["table_key"]): str(row["role"])
            for row in connection.execute(
                "SELECT table_key, role FROM field_semantics WHERE workspace_id = 'default' AND field_name = 'id'"
            ).fetchall()
        }
        validation = json.dumps({
            "status": "validated",
            "blockers": [],
            "dataVersions": versions,
            "metrics": {"overlapKeys": 2, "confidence": 1.0},
        }, separators=(",", ":"))
        connection.execute(
            """
            INSERT INTO relationships(
              relation_key, workspace_id, name, left_table_key, right_table_key,
              left_field, right_field, mappings_json, filters_json, preaggregation_json,
              join_type, confidence, validation_json, created_at, updated_at
            ) VALUES(?, 'default', ?, ?, ?, 'id', 'id', ?, '[]', '{}', 'left', 1.0, ?, ?, ?)
            """,
            (
                "orders-customers", "Orders to customers", "orders_table", "customers_table",
                json.dumps([{"leftField": "id", "rightField": "id"}]), validation,
                "2026-07-17T00:00:00Z", "2026-07-17T00:00:00Z",
            ),
        )
        connection.commit()
    check("fixture-entity-semantics-are-identifiers", identity_roles == {"orders_table": "identity_key", "customers_table": "identity_key"}, identity_roles)

    metadata_before = logical_state(sqlite_path)
    duckdb_before = digest(duckdb_path)
    source_before = {"orders": digest(orders), "customers": digest(customers)}
    proof = run(proof_args(), env)
    check("two-source-plan-is-provable", proof.get("status") == "provable" and proof.get("provable") is True, proof)
    check("every-proof-gate-passes", all(item.get("status") == "passed" for item in (proof.get("gates") or {}).values()), proof.get("gates"))
    check(
        "proof-never-grants-execution-materialization-or-write",
        proof.get("permissions") == {"execution": False, "materialization": False, "write": False}
        and (proof.get("sideEffects") or {}).get("crossSourceQuery") is False
        and (proof.get("sideEffects") or {}).get("rowCopy") is False,
        proof,
    )
    serialized = json.dumps(proof, ensure_ascii=False).casefold()
    check(
        "proof-exposes-neither-rows-credentials-nor-source-paths",
        all(token not in serialized for token in ("o-1", "o-2", "credentialref", str(temp).casefold()))
        and all(source.get("credentialValuesExposed") is False and source.get("businessRowsExposed") is False for source in proof.get("sources") or []),
        serialized[:2000],
    )
    check(
        "proof-is-read-only-for-metadata-business-storage-and-sources",
        metadata_before == logical_state(sqlite_path)
        and duckdb_before == digest(duckdb_path)
        and source_before == {"orders": digest(orders), "customers": digest(customers)},
        {"metadataChanged": metadata_before != logical_state(sqlite_path), "duckdb": [duckdb_before, digest(duckdb_path)]},
    )
    replay = run(proof_args(), env)
    check("proof-fingerprint-is-deterministic", replay.get("proofFingerprint") == proof.get("proofFingerprint"), replay)

    unsafe_filter = run(proof_args(filters=[{"connectorKey": "orders_connector", "field": "amount", "operator": "sql"}]), env)
    check(
        "arbitrary-filter-language-is-fail-closed",
        unsafe_filter.get("status") == "blocked"
        and "filter-operator-not-allowlisted:sql" in (unsafe_filter.get("blockers") or []),
        unsafe_filter,
    )
    tight_budget = run(proof_args(max_sources=1), env)
    check("budget-overrun-is-fail-closed", "source-budget-exceeded" in (tight_budget.get("blockers") or []), tight_budget)

    duplicate_sources = run([
        *proof_args()[:2], "orders_connector,orders_connector",
        *proof_args()[3:],
    ], env)
    check("duplicate-source-identities-are-fail-closed", "connector-keys-must-be-unique" in (duplicate_sources.get("blockers") or []), duplicate_sources)

    with closing(sqlite3.connect(sqlite_path)) as connection:
        connection.execute("UPDATE data_connectors SET status = 'paused' WHERE workspace_id = 'default' AND connector_key = 'orders_connector'")
        connection.commit()
    hidden_orders = orders.with_suffix(".hidden")
    orders.rename(hidden_orders)
    paused = run(proof_args(), env)
    hidden_orders.rename(orders)
    with closing(sqlite3.connect(sqlite_path)) as connection:
        connection.execute("UPDATE data_connectors SET status = 'active' WHERE workspace_id = 'default' AND connector_key = 'orders_connector'")
        connection.commit()
    check(
        "inactive-connector-blocks-before-external-resource-read",
        "connector-not-active:orders_connector" in (paused.get("blockers") or [])
        and "adapter-unavailable:orders_connector" not in (paused.get("blockers") or [])
        and next(source for source in paused.get("sources") or [] if source.get("connectorKey") == "orders_connector").get("networkRead") is False,
        paused,
    )

    orders.write_text("id,amount\nO-1,99\nO-2,20\n", encoding="utf-8-sig")
    changed = run(proof_args(), env)
    check(
        "changed-source-fingerprint-blocks-proof",
        changed.get("status") == "blocked"
        and "source-fingerprint-changed:orders_connector" in (changed.get("blockers") or []),
        changed,
    )
    orders.write_text("id,amount\nO-1,10\nO-2,20\n", encoding="utf-8-sig")

    with closing(sqlite3.connect(sqlite_path)) as connection:
        connection.execute("UPDATE table_registry SET data_version = data_version + 1 WHERE workspace_id = 'default' AND table_key = 'customers_table'")
        connection.commit()
    stale = run(proof_args(), env)
    check(
        "stale-relationship-version-blocks-proof",
        stale.get("status") == "blocked"
        and "relationship-version-stale:orders-customers" in (stale.get("blockers") or []),
        stale,
    )

    isolated = run(["workspace-create", "--name", "federation-isolated", "--yes"], env)
    isolated_proof = run(proof_args(), env)
    check(
        "active-workspace-isolation-hides-other-workspace-connectors",
        bool((isolated.get("created") or {}).get("id"))
        and isolated_proof.get("workspaceId") == (isolated.get("created") or {}).get("id")
        and "unknown-connector:orders_connector" in (isolated_proof.get("blockers") or []),
        isolated_proof,
    )

    contract = run(["cli-contract"], env)
    commands = {item.get("name"): item for item in ((contract.get("contract") or {}).get("commands") or [])}
    federation_contract = commands.get("federation-proof") or {}
    check(
        "cli-contract-declares-federation-proof-read-only",
        federation_contract.get("mutationMode") == "read-only"
        and federation_contract.get("requiresYes") is False
        and federation_contract.get("writesBusinessState") is False,
        federation_contract,
    )
    capability = proof.get("capability") or {}
    check(
        "capability-declares-bounded-adapter-read-permissions",
        (capability.get("permissions") or {}).get("filesystem") == "read"
        and (capability.get("permissions") or {}).get("network") == "allowlisted-read-only"
        and (capability.get("permissions") or {}).get("database") == "read-only",
        capability,
    )


failed = [item for item in CHECKS if not item["ok"]]
print(json.dumps({
    "ok": not failed,
    "schema": "aibi-federation-proof-verify/v1",
    "generatedBy": "scripts/verify-federation-proof.py",
    "checks": CHECKS,
    "failedChecks": failed,
}, ensure_ascii=False, indent=2))
raise SystemExit(1 if failed else 0)
