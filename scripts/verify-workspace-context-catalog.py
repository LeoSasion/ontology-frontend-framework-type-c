from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import traceback
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PYTHON = os.environ.get("PYTHON", sys.executable)

checks: list[dict[str, Any]] = []


def check(label: str, ok: bool, detail: Any = None) -> None:
    item: dict[str, Any] = {"label": label, "ok": bool(ok)}
    if detail is not None and (not ok or isinstance(detail, (str, int, float, bool))):
        item["detail"] = detail
    checks.append(item)


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def database_digest(path: Path) -> str:
    """Hash all application-visible SQLite rows without relying on file metadata."""
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        tables = [
            str(row["name"])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
            # CLI startup refreshes system theme and derived navigation timestamps.
            # Neither table is a workspace semantic or business-data fact.
            if str(row["name"]) not in {"theme_palettes", "navigation_modules"}
        ]
        material: dict[str, list[str]] = {}
        for table in tables:
            quoted = '"' + table.replace('"', '""') + '"'
            rows = [canonical(dict(row)) for row in connection.execute(f"SELECT * FROM {quoted}").fetchall()]
            material[table] = sorted(rows)
        return hashlib.sha256(canonical(material).encode("utf-8")).hexdigest()
    finally:
        connection.close()


def write_csv(path: Path, rows: list[list[str]]) -> None:
    path.write_text("\n".join(",".join(row) for row in rows) + "\n", encoding="utf-8")


def manifest(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("workspaceManifest")
    if not isinstance(value, dict):
        raise RuntimeError(f"workspace-manifest returned no manifest: {payload}")
    return value


def catalog(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("runtimeCatalog")
    if not isinstance(value, dict):
        raise RuntimeError(f"runtime-catalog returned no catalog: {payload}")
    return value


def profile_map(payload: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    profiles = payload.get("profiles")
    if not isinstance(profiles, list):
        raise RuntimeError(f"business-field-profiles returned no profiles: {payload}")
    return {
        (str(item["fieldRef"]["tableKey"]), str(item["fieldRef"]["fieldName"])): item
        for item in profiles
        if isinstance(item, dict) and isinstance(item.get("fieldRef"), dict)
    }


def component_changed(before: dict[str, Any], after: dict[str, Any], key: str) -> bool:
    return str(before.get("componentFingerprints", {}).get(key) or "") != str(
        after.get("componentFingerprints", {}).get(key) or ""
    )


def component_stable(before: dict[str, Any], after: dict[str, Any], key: str) -> bool:
    return str(before.get("componentFingerprints", {}).get(key) or "") == str(
        after.get("componentFingerprints", {}).get(key) or ""
    )


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="aibi-c-workspace-context-") as raw_temp:
        temp_root = Path(raw_temp)
        sqlite_path = temp_root / "workspace-context.sqlite"
        duckdb_path = temp_root / "workspace-context.duckdb"
        evidence_root = temp_root / "evidence"
        env = {
            **os.environ,
            "AIBI_HYBRID_DB_PATH": str(sqlite_path),
            "AIBI_HYBRID_DUCKDB_PATH": str(duckdb_path),
            "AIBI_EVIDENCE_BUNDLE_ROOT": str(evidence_root),
            "AIBI_AGENT_PROVIDER": "deterministic",
            "DEEPSEEK_API_KEY": "",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONHASHSEED": "0",
        }

        def cli(arguments: list[str]) -> dict[str, Any]:
            completed = subprocess.run(
                [PYTHON, "tools/aibi_cli.py", "--json", *arguments],
                cwd=ROOT,
                env=env,
                text=True,
                encoding="utf-8",
                capture_output=True,
                check=False,
            )
            try:
                payload = json.loads(completed.stdout.strip() or completed.stderr.strip() or "{}")
            except json.JSONDecodeError as error:
                raise RuntimeError(
                    f"{arguments[0]} returned invalid JSON (exit {completed.returncode}): "
                    f"{completed.stdout[-1200:]} {completed.stderr[-1200:]}"
                ) from error
            if completed.returncode != 0 or payload.get("ok") is False:
                raise RuntimeError(
                    f"{arguments[0]} failed (exit {completed.returncode}): "
                    f"{canonical(payload)} {completed.stderr[-1200:]}"
                )
            return payload

        def bind_current_batch(batch_id: str, table_keys: list[str]) -> None:
            connection = sqlite3.connect(sqlite_path)
            connection.row_factory = sqlite3.Row
            try:
                placeholders = ", ".join("?" for _ in table_keys)
                rows = connection.execute(
                    f"SELECT table_key, data_version, row_count FROM table_registry "
                    f"WHERE workspace_id = 'default' AND table_key IN ({placeholders})",
                    table_keys,
                ).fetchall()
                connection.execute(
                    "INSERT INTO source_runs(id, workspace_id, table_key, name, status, source_file, "
                    "row_count, column_count, profile_json, evidence_json, created_at) "
                    "VALUES(?, 'default', '__batch__', ?, 'ready', 'fixture-batch', ?, 0, '{}', '[]', "
                    "'2026-07-19T12:00:00Z')",
                    (batch_id, batch_id, sum(int(row["row_count"] or 0) for row in rows)),
                )
                for row in rows:
                    connection.execute(
                        "INSERT INTO source_run_tables(source_run_id, workspace_id, table_key, data_version, "
                        "row_count, created_at) VALUES(?, 'default', ?, ?, ?, '2026-07-19T12:00:00Z')",
                        (batch_id, row["table_key"], int(row["data_version"] or 0), int(row["row_count"] or 0)),
                    )
                connection.execute(
                    "UPDATE workspaces SET current_source_run_id = ? WHERE id = 'default'",
                    (batch_id,),
                )
                connection.commit()
            finally:
                connection.close()

        customers_path = temp_root / "customers.csv"
        orders_path = temp_root / "orders.csv"
        isolated_path = temp_root / "isolated.csv"
        private_values = {
            "alice.private@example.com",
            "bob.private@example.com",
            "+8613800138000",
            "+8613900139000",
            "HIV-positive",
            "cancer",
        }
        write_csv(
            customers_path,
            [
                ["customer_id", "email", "phone", "status", "amount", "order_date", "zero_value", "boolean_flag", "mixed_time", "diagnosis"],
                ["c1", "alice.private@example.com", "+8613800138000", "active", "100.50", "2026-01-01", "0", "false", "2026-01-01T00:00:00Z", "HIV-positive"],
                ["c2", "bob.private@example.com", "+8613900139000", "inactive", "200.00", "2026-01-02", "0", "true", "2026-01-02", "cancer"],
                ["c3", "carol.private@example.com", "+8613700137000", "active", "50.00", "2026-01-03", "0", "false", "2026-01-03T08:00:00+08:00", "HIV-positive"],
            ],
        )
        write_csv(
            orders_path,
            [
                ["order_id", "customer_id", "order_status", "revenue"],
                ["o1", "c1", "paid", "100.50"],
                ["o2", "c1", "paid", "20.00"],
                ["o3", "c2", "refunded", "200.00"],
            ],
        )
        write_csv(
            isolated_path,
            [
                ["isolation_key", "isolated_value"],
                ["x1", "alpha"],
                ["x2", "beta"],
            ],
        )

        empty_first = manifest(cli(["workspace-manifest"]))
        empty_second = manifest(cli(["workspace-manifest"]))
        check(
            "empty-workspace-has-explicit-incomplete-contract",
            empty_first.get("schema") == "aibi-workspace-manifest/v1"
            and empty_first.get("status") == "incomplete"
            and empty_first.get("usableForPlanning") is False
            and "workspace-has-no-source-tables" in (empty_first.get("blockers") or [])
            and empty_first.get("sourceSnapshot", {}).get("tableCount") == 0,
            empty_first,
        )
        check(
            "empty-workspace-manifest-is-deterministic",
            empty_first.get("fingerprint") == empty_second.get("fingerprint")
            and empty_first.get("planningBinding", {}).get("fingerprint")
            == empty_second.get("planningBinding", {}).get("fingerprint"),
        )

        cli(["import-commit", str(customers_path), "--table", "customers", "--name", "Customers", "--mode", "create", "--yes"])
        after_customer_import = manifest(cli(["workspace-manifest", "--workspace", "default"]))
        check(
            "import-populates-field-context-and-changes-data-binding",
            after_customer_import.get("sourceSnapshot", {}).get("tableCount") == 1
            and after_customer_import.get("sourceSnapshot", {}).get("fieldCount") == 10
            and component_changed(empty_first, after_customer_import, "data")
            and after_customer_import.get("usableForPlanning") is True,
            after_customer_import,
        )

        imported_profiles_payload = cli(["business-field-profiles", "--workspace", "default", "--table", "customers"])
        imported_profiles = profile_map(imported_profiles_payload)
        customer_candidate = imported_profiles[("customers", "customer_id")]
        amount_candidate = imported_profiles[("customers", "amount")]
        zero_candidate = imported_profiles[("customers", "zero_value")]
        boolean_candidate = imported_profiles[("customers", "boolean_flag")]
        mixed_time_candidate = imported_profiles[("customers", "mixed_time")]
        check(
            "imported-semantics-remain-unconfirmed-candidates",
            imported_profiles_payload.get("requestScope") == {"tableKey": "customers", "fieldName": None}
            and customer_candidate.get("semantic", {}).get("authority") == "saved-auto-candidate"
            and amount_candidate.get("semantic", {}).get("authority") == "saved-auto-candidate"
            and all(
                candidate.get("confirmed") is False
                for candidate in customer_candidate.get("semantic", {}).get("roleCandidates", [])
            ),
            customer_candidate,
        )
        check(
            "sealed-types-win-while-bounded-sample-evidence-remains-available",
            zero_candidate.get("observedShape", {}).get("logicalType") != "empty"
            and zero_candidate.get("observedShape", {}).get("boundedSampleSize") == 3
            and boolean_candidate.get("observedShape", {}).get("logicalType") == "boolean"
            and boolean_candidate.get("observedShape", {}).get("boundedSampleSize") == 3
            and mixed_time_candidate.get("observedShape", {}).get("logicalType") == "string"
            and mixed_time_candidate.get("observedShape", {}).get("timeCoverage", {}).get("minimum") == "2026-01-01T00:00:00"
            and mixed_time_candidate.get("observedShape", {}).get("timeCoverage", {}).get("maximum") == "2026-01-03T00:00:00",
            {
                "zero": zero_candidate.get("observedShape"),
                "boolean": boolean_candidate.get("observedShape"),
                "mixedTime": mixed_time_candidate.get("observedShape"),
            },
        )

        before_manual = after_customer_import
        cli([
            "set-semantic",
            "customers",
            "customer_id",
            "--role",
            "identity_key",
            "--usage",
            "joinable",
            "--confidence",
            "1",
            "--note",
            "Confirmed customer grain",
            "--yes",
        ])
        cli([
            "set-semantic",
            "customers",
            "diagnosis",
            "--role",
            "dimension",
            "--usage",
            "filterable",
            "--confidence",
            "1",
            "--yes",
        ])
        after_manual = manifest(cli(["workspace-manifest", "--workspace", "default"]))
        manual_profiles_payload = cli(["business-field-profiles", "--workspace", "default", "--table", "customers"])
        manual_profiles = profile_map(manual_profiles_payload)
        manual_customer = manual_profiles[("customers", "customer_id")]
        still_candidate = manual_profiles[("customers", "amount")]
        check(
            "manual-semantic-has-authority-without-promoting-other-candidates",
            manual_customer.get("semantic", {}).get("authority") == "manual-confirmed"
            and manual_customer.get("semantic", {}).get("confirmedSemanticRef") == "field-semantic:customers.customer_id"
            and manual_customer.get("semantic", {}).get("savedRole") == "identity_key"
            and still_candidate.get("semantic", {}).get("authority") == "saved-auto-candidate",
            {"manual": manual_customer, "candidate": still_candidate},
        )
        check(
            "manual-semantic-changes-field-profile-binding-not-data",
            component_changed(before_manual, after_manual, "fieldProfiles")
            and component_stable(before_manual, after_manual, "data"),
        )

        privacy_payloads = [after_manual, catalog(cli(["runtime-catalog", "--workspace", "default"])), manual_profiles_payload]
        privacy_text = canonical(privacy_payloads)
        sensitive_profiles = [
            manual_profiles[("customers", "email")],
            manual_profiles[("customers", "phone")],
            manual_profiles[("customers", "diagnosis")],
        ]
        check(
            "business-context-never-exposes-raw-private-or-category-values",
            all(value not in privacy_text for value in private_values)
            and str(temp_root) not in privacy_text
            and "Confirmed customer grain" not in privacy_text
            and imported_profiles_payload.get("rawSampleValuesExposed") is False
            and all(item.get("sensitivity", {}).get("rawValuesExposed") is False for item in sensitive_profiles)
            and all(item.get("semantic", {}).get("statusCandidates", {}).get("rawValuesWithheld") is True for item in sensitive_profiles),
        )

        created = cli(["workspace-create", "--name", "Secondary Workspace", "--yes"])
        secondary_id = str((created.get("created") or {}).get("id") or "")
        if not secondary_id:
            raise RuntimeError(f"workspace-create returned no created workspace id: {created}")
        cli(["workspace-select", secondary_id, "--yes"])
        cli(["import-commit", str(isolated_path), "--table", "isolated", "--name", "Isolated", "--mode", "create", "--yes"])
        secondary_manifest = manifest(cli(["workspace-manifest", "--workspace", secondary_id]))
        default_manifest_during_isolation = manifest(cli(["workspace-manifest", "--workspace", "default"]))
        secondary_tables = {item["tableKey"] for item in secondary_manifest.get("sourceSnapshot", {}).get("tables", [])}
        default_tables = {item["tableKey"] for item in default_manifest_during_isolation.get("sourceSnapshot", {}).get("tables", [])}
        secondary_profiles = profile_map(cli(["business-field-profiles", "--workspace", secondary_id]))
        default_profiles = profile_map(cli(["business-field-profiles", "--workspace", "default"]))
        check(
            "workspace-context-is-strictly-isolated",
            secondary_tables == {"isolated"}
            and default_tables == {"customers"}
            and all(table == "isolated" for table, _field in secondary_profiles)
            and all(table == "customers" for table, _field in default_profiles)
            and secondary_manifest.get("workspaceId") == secondary_id
            and default_manifest_during_isolation.get("workspaceId") == "default",
            {"secondaryTables": sorted(secondary_tables), "defaultTables": sorted(default_tables)},
        )
        cli(["workspace-select", "default", "--yes"])

        cli(["import-commit", str(orders_path), "--table", "orders", "--name", "Orders", "--mode", "create", "--yes"])
        bind_current_batch("workspace-context-fixture-batch", ["customers", "orders"])
        before_metric = manifest(cli(["workspace-manifest", "--workspace", "default"]))
        cli([
            "add-metric",
            "--id",
            "verified_amount_sum",
            "--name",
            "Verified amount sum",
            "--table",
            "customers",
            "--field",
            "amount",
            "--agg",
            "sum",
            "--yes",
        ])
        after_metric = manifest(cli(["workspace-manifest", "--workspace", "default"]))
        check(
            "metric-definition-has-an-independent-fingerprint",
            component_changed(before_metric, after_metric, "metrics")
            and component_stable(before_metric, after_metric, "data")
            and after_metric.get("semanticSnapshot", {}).get("metricCount", 0)
            > before_metric.get("semanticSnapshot", {}).get("metricCount", 0),
        )

        before_relationship = after_metric
        cli([
            "relationship-save",
            "--left-table",
            "customers",
            "--right-table",
            "orders",
            "--left-field",
            "customer_id",
            "--right-field",
            "customer_id",
            "--join-type",
            "left",
            "--limit",
            "20",
            "--yes",
        ])
        after_relationship = manifest(cli(["workspace-manifest", "--workspace", "default"]))
        check(
            "relationship-definition-and-validation-change-only-relationship-binding",
            component_changed(before_relationship, after_relationship, "relationships")
            and component_stable(before_relationship, after_relationship, "data")
            and after_relationship.get("semanticSnapshot", {}).get("relationshipCount") == 1
            and after_relationship.get("semanticSnapshot", {}).get("validatedRelationshipCount") == 1,
            after_relationship.get("semanticSnapshot"),
        )

        catalog_before_pack = catalog(cli(["runtime-catalog", "--workspace", "default"]))
        available_packs = catalog_before_pack.get("domainPacks", {}).get("available") or []
        if not available_packs:
            raise RuntimeError("runtime-catalog exposed no Domain Packs for the state-fingerprint test")
        pack = next((item for item in available_packs if not item.get("enabled")), available_packs[0])
        pack_target = "enabled" if not pack.get("enabled") else "disabled"
        before_pack = after_relationship
        cli([
            "domain-pack-set",
            "--pack",
            str(pack["packId"]),
            "--state",
            pack_target,
            "--workspace",
            "default",
            "--yes",
        ])
        after_pack = manifest(cli(["workspace-manifest", "--workspace", "default"]))
        check(
            "domain-pack-state-has-an-independent-fingerprint",
            component_changed(before_pack, after_pack, "domainPacks")
            and component_stable(before_pack, after_pack, "data"),
            {"packId": pack.get("packId"), "target": pack_target},
        )

        catalog_before_skill = catalog(cli(["runtime-catalog", "--workspace", "default"]))
        available_skills = catalog_before_skill.get("analyticalSkills", {}).get("available") or []
        if not available_skills:
            raise RuntimeError("runtime-catalog exposed no Analytical Skills for the state-fingerprint test")
        skill = next((item for item in available_skills if item.get("enabled")), available_skills[0])
        skill_target = "disabled" if skill.get("enabled") else "enabled"
        before_skill = after_pack
        cli([
            "analytical-skill-set",
            "--skill",
            str(skill["skillId"]),
            "--state",
            skill_target,
            "--workspace",
            "default",
            "--yes",
        ])
        after_skill = manifest(cli(["workspace-manifest", "--workspace", "default"]))
        check(
            "analytical-skill-state-has-an-independent-fingerprint",
            component_changed(before_skill, after_skill, "analyticalSkills")
            and component_stable(before_skill, after_skill, "data"),
            {"skillId": skill.get("skillId"), "target": skill_target},
        )

        state_before_reads = database_digest(sqlite_path)
        deterministic_manifest_a = manifest(cli(["workspace-manifest", "--workspace", "default"]))
        deterministic_catalog_a = catalog(cli(["runtime-catalog", "--workspace", "default"]))
        deterministic_profiles_a = cli(["business-field-profiles", "--workspace", "default"])
        deterministic_manifest_b = manifest(cli(["workspace-manifest", "--workspace", "default"]))
        deterministic_catalog_b = catalog(cli(["runtime-catalog", "--workspace", "default"]))
        deterministic_profiles_b = cli(["business-field-profiles", "--workspace", "default"])
        state_after_reads = database_digest(sqlite_path)
        check(
            "derived-context-contracts-are-deterministic",
            deterministic_manifest_a.get("fingerprint") == deterministic_manifest_b.get("fingerprint")
            and deterministic_catalog_a.get("fingerprint") == deterministic_catalog_b.get("fingerprint")
            and deterministic_profiles_a.get("fingerprint") == deterministic_profiles_b.get("fingerprint"),
        )
        check(
            "workspace-context-commands-are-read-only",
            state_before_reads == state_after_reads,
            {"before": state_before_reads, "after": state_after_reads},
        )

        pre_query_manifest = deterministic_manifest_b
        query = cli([
            "query",
            "--table",
            "customers",
            "--group",
            "status",
            "--measure",
            "amount",
            "--agg",
            "sum",
            "--limit",
            "20",
            "--request",
            "Direct query receipt manifest binding verification",
        ])
        receipt = query.get("queryPlanReceipt")
        if not isinstance(receipt, dict):
            raise RuntimeError(f"direct query returned no Query Receipt: {query}")
        receipt_key = str(receipt.get("receiptKey") or "")
        stored_binding = receipt.get("workspaceManifest") if isinstance(receipt.get("workspaceManifest"), dict) else {}

        for key, value in env.items():
            if key.startswith("AIBI_") or key in {"DEEPSEEK_API_KEY", "PYTHONIOENCODING", "PYTHONHASHSEED"}:
                os.environ[key] = value
        tools_path = str(ROOT / "tools")
        if tools_path not in sys.path:
            sys.path.insert(0, tools_path)
        from query_plan_receipt_service import (  # noqa: PLC0415
            current_query_receipt_source_state,
            query_receipt_binding_fingerprint,
        )
        from workspace_manifest_service import _normalized_scalar, workspace_planning_binding  # noqa: PLC0415

        check(
            "scalar-normalization-preserves-zero-and-false",
            _normalized_scalar(0) == "0" and _normalized_scalar(False) == "False" and _normalized_scalar(None) == "",
        )

        traced_connection = sqlite3.connect(sqlite_path)
        traced_connection.row_factory = sqlite3.Row
        traced_statements: list[str] = []
        traced_connection.set_trace_callback(traced_statements.append)
        try:
            workspace_planning_binding(traced_connection, "default")
            physical_tables = [
                str(row["physical_table"])
                for row in traced_connection.execute(
                    "SELECT physical_table FROM table_registry WHERE workspace_id = ? ORDER BY table_key",
                    ("default",),
                ).fetchall()
            ]
        finally:
            traced_connection.close()
        business_table_reads = [
            statement
            for statement in traced_statements
            if any(f'FROM "{table}"' in statement for table in physical_tables)
        ]
        source_profile_reads = [statement for statement in traced_statements if "FROM source_runs" in statement]
        semantic_batch_reads = [
            statement
            for statement in traced_statements
            if "FROM field_semantics" in statement and "table_key IN" in statement
        ]
        check(
            "field-profiling-uses-batched-metadata-with-zero-business-samples",
            not business_table_reads
            and len(source_profile_reads) == 1
            and len(semantic_batch_reads) == 1,
            {
                "tableCount": len(physical_tables),
                "businessReadCount": len(business_table_reads),
                "sourceProfileReadCount": len(source_profile_reads),
                "semanticBatchReadCount": len(semantic_batch_reads),
            },
        )
        agent_interaction_source = (
            ROOT / "tools" / "aibi_runtime" / "use_cases" / "agent_interaction.py"
        ).read_text(encoding="utf-8")
        check(
            "ask-reuses-precomputed-planning-binding-for-receipt",
            "workspace_manifest_ref = workspace_planning_binding(connection, workspace_id)" in agent_interaction_source
            and "workspace_manifest=workspace_manifest_ref" in agent_interaction_source,
        )

        def receipt_state(value: dict[str, Any]) -> dict[str, Any]:
            connection = sqlite3.connect(sqlite_path)
            connection.row_factory = sqlite3.Row
            try:
                return current_query_receipt_source_state(connection, "default", value)
            finally:
                connection.close()

        current_state = receipt_state(receipt)
        binding_fingerprint = query_receipt_binding_fingerprint(receipt)
        after_query_manifest = manifest(cli(["workspace-manifest", "--workspace", "default"]))
        check(
            "direct-query-receipt-binds-current-workspace-manifest",
            stored_binding.get("schema") == "aibi-workspace-planning-binding/v1"
            and current_state.get("workspaceManifestBound") is True
            and current_state.get("workspaceManifestMatchesReceipt") is True
            and current_state.get("matchesReceipt") is True
            and stored_binding.get("fingerprint") == pre_query_manifest.get("planningBinding", {}).get("fingerprint")
            and stored_binding.get("fingerprint") == current_state.get("workspaceManifest", {}).get("fingerprint")
            and current_state.get("receiptBindingFingerprint") == binding_fingerprint
            and len(binding_fingerprint) == 64,
            {
                "receiptStatus": receipt.get("status"),
                "storedBinding": stored_binding,
                "currentState": current_state,
            },
        )
        agent = cli(["ask", "sum amount by customer status", "--workspace", "default"])
        agent_receipt_binding = (agent.get("queryPlanReceipt") or {}).get("workspaceManifest") or {}
        agent_context_binding = ((agent.get("semanticContext") or {}).get("sources") or {}).get("workspaceManifest") or {}
        check(
            "manifest-agent-context-and-receipt-share-one-planning-binding",
            agent_receipt_binding.get("fingerprint") == pre_query_manifest.get("planningBinding", {}).get("fingerprint")
            and agent_context_binding.get("fingerprint") == agent_receipt_binding.get("fingerprint")
            and agent_context_binding.get("workspaceId") == "default"
            and agent_receipt_binding.get("workspaceId") == "default",
            {
                "manifest": pre_query_manifest.get("planningBinding"),
                "agentContext": agent_context_binding,
                "agentReceipt": agent_receipt_binding,
            },
        )
        check(
            "receipt-write-does-not-change-the-semantic-manifest",
            pre_query_manifest.get("fingerprint") == after_query_manifest.get("fingerprint"),
        )

        write_csv(
            customers_path,
            [
                ["customer_id", "email", "phone", "status", "amount", "order_date", "zero_value", "boolean_flag", "mixed_time", "diagnosis"],
                ["c1", "alice.private@example.com", "+8613800138000", "active", "100.50", "2026-01-01", "0", "false", "2026-01-01T00:00:00Z", "HIV-positive"],
                ["c2", "bob.private@example.com", "+8613900139000", "inactive", "200.00", "2026-01-02", "0", "true", "2026-01-02", "cancer"],
                ["c3", "carol.private@example.com", "+8613700137000", "active", "50.00", "2026-01-03", "0", "false", "2026-01-03T08:00:00+08:00", "HIV-positive"],
                ["c4", "dave.private@example.com", "+8613600136000", "active", "75.00", "2026-01-04", "0", "true", "2026-01-04", "none"],
            ],
        )
        before_data_change = after_query_manifest
        cli(["import-commit", str(customers_path), "--table", "customers", "--name", "Customers", "--mode", "replace", "--yes"])
        after_data_change = manifest(cli(["workspace-manifest", "--workspace", "default"]))
        stale_state = receipt_state(receipt)
        stored_receipt = cli(["query-receipts", "--receipt", receipt_key]).get("queryReceipt") or {}
        check(
            "data-change-updates-data-and-field-profile-fingerprints",
            component_changed(before_data_change, after_data_change, "data")
            and component_changed(before_data_change, after_data_change, "fieldProfiles")
            and after_data_change.get("sourceSnapshot", {}).get("rowCount", 0)
            > before_data_change.get("sourceSnapshot", {}).get("rowCount", 0),
        )
        check(
            "direct-query-receipt-becomes-stale-after-data-change",
            stale_state.get("matchesReceipt") is False
            and stale_state.get("sourceTablesMatch") is False
            and stale_state.get("workspaceManifestMatchesReceipt") is False
            and "query-receipt-source-drifted" in (stale_state.get("blockers") or [])
            and "query-receipt-workspace-manifest-drifted" in (stale_state.get("blockers") or [])
            and (stored_receipt.get("workspaceManifest") or {}).get("fingerprint") == stored_binding.get("fingerprint"),
            stale_state,
        )


try:
    main()
except Exception as error:  # noqa: BLE001
    check(
        "workspace-context-catalog-scenario-completed",
        False,
        {
            "error": str(error),
            "traceback": traceback.format_exc()[-6000:],
        },
    )

failed_checks = [item for item in checks if not item["ok"]]
print(
    json.dumps(
        {
            "ok": not failed_checks,
            "schema": "aibi-workspace-context-catalog-verify/v1",
            "generatedBy": "scripts/verify-workspace-context-catalog.py",
            "checks": checks,
            "failedChecks": failed_checks,
        },
        ensure_ascii=False,
        indent=2,
    )
)
if failed_checks:
    raise SystemExit(1)
