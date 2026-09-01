from __future__ import annotations

from contextlib import closing
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
    if not ok:
        item["detail"] = detail
    checks.append(item)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="aibi-c-semantic-patch-") as raw_temp:
        temp_root = Path(raw_temp)
        sqlite_path = temp_root / "metadata.sqlite"
        duckdb_path = temp_root / "query.duckdb"
        env = {
            **os.environ,
            "AIBI_HYBRID_DB_PATH": str(sqlite_path),
            "AIBI_HYBRID_DUCKDB_PATH": str(duckdb_path),
            "AIBI_DATASET_OBJECT_ROOT": str(temp_root / "dataset-objects-v2"),
            "AIBI_IMPORT_STAGE_ROOT": str(temp_root / "import-stages-v2"),
            "AIBI_EVIDENCE_BUNDLE_ROOT": str(temp_root / "evidence"),
            "AIBI_WORKSPACE_RECOVERY_ROOT": str(temp_root / "workspace-recovery"),
            "AIBI_AGENT_PROVIDER": "deterministic",
            "DEEPSEEK_API_KEY": "",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONHASHSEED": "0",
        }

        def cli_result(arguments: list[str]) -> tuple[int, dict[str, Any]]:
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
                payload = json.loads((completed.stdout or completed.stderr or "{}").strip())
            except json.JSONDecodeError:
                payload = {"stdout": completed.stdout, "stderr": completed.stderr}
            return completed.returncode, payload if isinstance(payload, dict) else {}

        def cli(arguments: list[str]) -> dict[str, Any]:
            status, payload = cli_result(arguments)
            if status != 0:
                raise RuntimeError(f"CLI failed ({status}): {' '.join(arguments)}\n{json.dumps(payload, ensure_ascii=False)}")
            return payload

        sales_path = temp_root / "sales.csv"
        sales_path.write_text(
            "order_id,amount,status\n"
            "o1,10.5,paid\n"
            "o2,7.0,refunded\n",
            encoding="utf-8",
        )
        status = cli(["status"])
        imported = cli([
            "import-commit",
            str(sales_path),
            "--table",
            "sales",
            "--name",
            "Sales",
            "--mode",
            "create",
            "--yes",
        ])
        with closing(sqlite3.connect(sqlite_path)) as connection:
            schema_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
            registry = connection.execute(
                "SELECT row_count, column_count, active_version_id, schema_json "
                "FROM table_registry WHERE workspace_id = 'default' AND table_key = 'sales'"
            ).fetchone()
            sqlite_business_table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sales_physical'"
            ).fetchone()
            baseline_authority_counts = (
                connection.execute("SELECT COUNT(*) FROM context_terms").fetchone()[0],
                connection.execute("SELECT COUNT(*) FROM context_rules").fetchone()[0],
                connection.execute("SELECT COUNT(*) FROM field_semantics").fetchone()[0],
            )
        check(
            "schema-v18-bootstrap",
            status.get("ok") is True
            and imported.get("ok") is True
            and schema_version == 18
            and registry is not None
            and registry[0:2] == (2, 3)
            and bool(registry[2])
            and len(json.loads(registry[3])) == 3
            and sqlite_business_table is None,
            {"schemaVersion": schema_version, "registry": list(registry) if registry else None},
        )

        adapters_one = cli(["knowledge-source-adapters"])
        adapters_two = cli(["knowledge-source-adapters"])
        adapter_ids = [item.get("adapterId") for item in adapters_one.get("adapters", [])]
        check("adapter-registry-is-deterministic-and-declaration-only", adapters_one.get("adapters") == adapters_two.get("adapters") and adapter_ids == ["knowledge-json-v1", "knowledge-markdown-v1", "user-correction-v1"] and all(item.get("permissions") == {"network": False, "sql": False, "code": False, "rawRows": False} for item in adapters_one.get("adapters", [])), adapter_ids)

        document = {
            "schema": "aibi-knowledge-source/v1",
            "source": {"name": "Sales dictionary", "version": "2026.1", "type": "data-dictionary"},
            "terms": [{"canonicalName": "净销售", "aliases": ["净收入"], "definition": "确认收入扣除退款后的金额", "scopeType": "workspace", "confidence": 0.97}],
            "rules": [{"title": "退款过滤规则", "statement": "退款记录只在状态明确时纳入退款分析", "ruleType": "default_filter", "appliesTo": ["sales.status"], "confidence": 0.91}],
            "fieldSemantics": [{"tableKey": "sales", "fieldName": "amount", "role": "measure", "usage": ["aggregatable", "sortable"], "tags": ["currency"], "confidence": 0.96, "note": "已核对数据字典"}],
        }
        json_path = temp_root / "sales-knowledge.json"
        json_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")

        preview = cli(["semantic-patch-propose", "--input", str(json_path), "--adapter", "knowledge-json-v1"])
        with closing(sqlite3.connect(sqlite_path)) as connection:
            dry_counts = (connection.execute("SELECT COUNT(*) FROM knowledge_sources").fetchone()[0], connection.execute("SELECT COUNT(*) FROM semantic_patch_proposals").fetchone()[0])
        check("file-proposal-is-dry-run-by-default", preview.get("dryRun") is True and preview.get("requiresConfirmation") is True and dry_counts == (0, 0), {"dryCounts": dry_counts})

        persisted = cli(["semantic-patch-propose", "--input", str(json_path), "--adapter", "knowledge-json-v1", "--yes"])
        proposals = cli(["semantic-patch-proposals"])["proposals"]
        by_type = {proposal["patchType"]: proposal for proposal in proposals}
        with closing(sqlite3.connect(sqlite_path)) as connection:
            authority_counts = (
                connection.execute("SELECT COUNT(*) FROM context_terms").fetchone()[0],
                connection.execute("SELECT COUNT(*) FROM context_rules").fetchone()[0],
                connection.execute("SELECT COUNT(*) FROM field_semantics").fetchone()[0],
            )
        check(
            "confirmed-ingest-persists-only-pending-proposals",
            persisted.get("inserted") == 3
            and set(by_type) == {"term", "rule", "field-semantic"}
            and all(item["status"] == "pending" for item in proposals)
            and authority_counts == baseline_authority_counts,
            {
                "baselineAuthorityCounts": baseline_authority_counts,
                "authorityCounts": authority_counts,
            },
        )

        term_key = by_type["term"]["proposalKey"]
        accept_preview = cli(["semantic-patch-review", "--proposal", term_key, "--decision", "accept"])
        with closing(sqlite3.connect(sqlite_path)) as connection:
            term_count_after_preview = connection.execute("SELECT COUNT(*) FROM context_terms").fetchone()[0]
        check("accept-review-is-dry-run-by-default", accept_preview.get("dryRun") is True and term_count_after_preview == 0, term_count_after_preview)
        accepted = cli(["semantic-patch-review", "--proposal", term_key, "--decision", "accept", "--note", "字典已人工核对", "--yes"])
        with closing(sqlite3.connect(sqlite_path)) as connection:
            term_row = connection.execute("SELECT source, status, evidence_json FROM context_terms").fetchone()
        check("confirmed-accept-applies-reviewed-term-with-evidence", accepted.get("applied") is True and term_row and term_row[0] == "reviewed" and term_row[1] == "confirmed" and "semantic-patch:" in term_row[2] and "knowledge-source:" in term_row[2], list(term_row) if term_row else None)

        rule_key = by_type["rule"]["proposalKey"]
        rejected = cli(["semantic-patch-review", "--proposal", rule_key, "--decision", "reject", "--yes"])
        with closing(sqlite3.connect(sqlite_path)) as connection:
            rule_count = connection.execute("SELECT COUNT(*) FROM context_rules").fetchone()[0]
        check("rejection-closes-proposal-without-applying", rejected["proposal"]["status"] == "rejected" and rejected.get("applied") is False and rule_count == 0, rule_count)

        field_key = by_type["field-semantic"]["proposalKey"]
        cli(["semantic-patch-review", "--proposal", field_key, "--decision", "accept", "--yes"])
        cli(["infer-semantics", "--table", "sales", "--overwrite-manual", "--yes"])
        with closing(sqlite3.connect(sqlite_path)) as connection:
            field_row = connection.execute("SELECT role, source, note FROM field_semantics WHERE workspace_id='default' AND table_key='sales' AND field_name='amount'").fetchone()
        profiles = cli(["business-field-profiles", "--table", "sales", "--field", "amount"])["profiles"]
        check("reviewed-field-semantic-is-confirmed-and-auto-inference-protected", field_row == ("measure", "reviewed", "已核对数据字典") and profiles[0]["semantic"]["authority"] == "reviewed-confirmed", {"field": field_row, "authority": profiles[0]["semantic"]["authority"]})

        reingested = cli(["semantic-patch-propose", "--input", str(json_path), "--adapter", "knowledge-json-v1", "--yes"])
        preserved_statuses = {item["patchType"]: item["status"] for item in reingested["proposals"]}
        check("identical-reingest-is-idempotent-and-preserves-review-decisions", reingested.get("idempotentReingest") is True and preserved_statuses == {"term": "accepted", "rule": "rejected", "field-semantic": "accepted"}, preserved_statuses)

        markdown_path = temp_root / "business-notes.md"
        raw_only_marker = "RAW_PROSE_MUST_NOT_BE_PERSISTED_3917"
        markdown_path.write_text(
            f"# Notes\n{raw_only_marker}\n\n```aibi-knowledge\n" + json.dumps({
                "schema": "aibi-knowledge-source/v1",
                "source": {"name": "Business notes", "version": "1", "type": "documentation"},
                "terms": [{"canonicalName": "有效订单", "aliases": [], "definition": "满足已确认业务规则的订单", "scopeType": "workspace"}],
                "rules": [], "fieldSemantics": [],
            }, ensure_ascii=False) + "\n```\n",
            encoding="utf-8",
        )
        markdown_result = cli(["semantic-patch-propose", "--input", str(markdown_path), "--adapter", "knowledge-markdown-v1", "--yes"])
        with closing(sqlite3.connect(sqlite_path)) as connection:
            database_text = "\n".join(str(value) for row in connection.execute("SELECT * FROM knowledge_sources").fetchall() for value in row) + "\n" + "\n".join(str(value) for row in connection.execute("SELECT * FROM semantic_patch_proposals").fetchall() for value in row)
            locator_refs = [str(row[0]) for row in connection.execute("SELECT locator_ref FROM knowledge_sources").fetchall()]
        check("markdown-adapter-stores-normalized-patches-not-raw-document-or-path", markdown_result.get("inserted") == 1 and raw_only_marker not in database_text and str(temp_root) not in database_text and all(ref.startswith(("local-file:", "inline:")) for ref in locator_refs), locator_refs)

        stale_created = cli(["semantic-patch-propose", "--kind", "term", "--name", "客单价", "--definition", "销售金额除以有效订单数", "--yes"])
        stale_proposal = stale_created["proposals"][0]
        target_ref = stale_proposal["targetRef"]
        cli(["context-term", "--term", target_ref, "--name", "客单价", "--definition", "另一份人工定义", "--status", "confirmed", "--evidence", "isolated-test", "--yes"])
        stale_view = cli(["semantic-patch-proposals", "--proposal", stale_proposal["proposalKey"]])["proposal"]
        stale_accept_status, stale_accept = cli_result(["semantic-patch-review", "--proposal", stale_proposal["proposalKey"], "--decision", "accept", "--yes"])
        stale_reject = cli(["semantic-patch-review", "--proposal", stale_proposal["proposalKey"], "--decision", "reject", "--yes"])
        check("target-drift-marks-stale-blocks-accept-and-still-allows-reject", stale_view["status"] == "stale" and "target-changed" in stale_view["freshness"]["mismatches"] and stale_accept_status != 0 and "stale" in str(stale_accept.get("error", "")).lower() and stale_reject["proposal"]["status"] == "rejected", stale_view["freshness"])

        schema_drift_created = cli(["semantic-patch-propose", "--kind", "field-semantic", "--table", "sales", "--field", "status", "--role", "status", "--yes"])
        schema_drift_key = schema_drift_created["proposals"][0]["proposalKey"]
        sales_path.write_text(
            "order_id,amount,status,region\n"
            "o1,10.5,paid,east\n"
            "o2,7.0,refunded,north\n",
            encoding="utf-8",
        )
        cli([
            "import-commit",
            str(sales_path),
            "--table",
            "sales",
            "--name",
            "Sales",
            "--mode",
            "replace",
            "--confirm-schema-change",
            "--yes",
        ])
        schema_stale = cli(["semantic-patch-proposals", "--proposal", schema_drift_key])["proposal"]
        check("workspace-schema-drift-invalidates-pending-proposal", schema_stale["status"] == "stale" and "workspace-schema-changed" in schema_stale["freshness"]["mismatches"], schema_stale["freshness"])
        cli(["semantic-patch-review", "--proposal", schema_drift_key, "--decision", "reject", "--yes"])

        cli(["workspace-create", "--name", "Review sandbox", "--yes"])
        sandbox = cli(["semantic-patch-propose", "--workspace", "review_sandbox", "--kind", "term", "--name", "沙盒术语", "--definition", "仅属于沙盒", "--yes"])
        cli(["workspace-select", "default", "--yes"])
        default_keys = {item["proposalKey"] for item in cli(["semantic-patch-proposals", "--workspace", "default"])["proposals"]}
        sandbox_keys = {item["proposalKey"] for item in cli(["semantic-patch-proposals", "--workspace", "review_sandbox"])["proposals"]}
        check("semantic-review-state-is-workspace-isolated", sandbox["proposals"][0]["proposalKey"] not in default_keys and sandbox["proposals"][0]["proposalKey"] in sandbox_keys, {"default": len(default_keys), "sandbox": len(sandbox_keys)})
        delete_request_key = "semantic-review-sandbox-workspace-delete"
        delete_preview = cli([
            "workspace-delete", "review_sandbox",
            "--request-key", delete_request_key,
        ])
        deletion = cli([
            "workspace-delete", "review_sandbox",
            "--request-key", delete_request_key,
            "--expected-plan", str((delete_preview.get("deletePlan") or {}).get("planFingerprint") or ""),
            "--yes",
        ])
        check("workspace-delete-removes-source-and-proposal-state", deletion["deletedCounts"].get("knowledge_sources") == 1 and deletion["deletedCounts"].get("semantic_patch_proposals") == 1, deletion["deletedCounts"])

        config_path = temp_root / "portable-config.json"
        exported = cli(["export-config", str(config_path)])
        config_payload = json.loads(config_path.read_text(encoding="utf-8"))
        serialized_config = json.dumps(config_payload, ensure_ascii=False)
        required_config_tables = {"context_terms", "context_rules", "knowledge_sources", "semantic_patch_proposals"}
        check("config-portability-includes-review-state-without-raw-paths", exported.get("ok") is True and required_config_tables.issubset(config_payload["tables"]) and str(temp_root) not in serialized_config and raw_only_marker not in serialized_config, sorted(config_payload["tables"]))

        forbidden_path = temp_root / "forbidden.json"
        forbidden_document = dict(document)
        forbidden_document["sql"] = "DROP TABLE sales"
        forbidden_path.write_text(json.dumps(forbidden_document, ensure_ascii=False), encoding="utf-8")
        before_forbidden = len(cli(["semantic-patch-proposals"])["proposals"])
        forbidden_status, forbidden_result = cli_result(["semantic-patch-propose", "--input", str(forbidden_path), "--yes"])
        after_forbidden = len(cli(["semantic-patch-proposals"])["proposals"])
        check("executable-fields-are-rejected-without-partial-write", forbidden_status != 0 and "forbidden" in str(forbidden_result.get("error", "")).lower() and before_forbidden == after_forbidden, forbidden_result)

        fake_other_repo = temp_root / "AIBI-D"
        fake_other_repo.mkdir()
        other_repo_path = fake_other_repo / "dictionary.json"
        other_repo_path.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        isolation_status, isolation_result = cli_result(["semantic-patch-propose", "--input", str(other_repo_path), "--yes"])
        check("other-aibi-repository-paths-are-rejected", isolation_status != 0 and "another AIBI repository" in str(isolation_result.get("error", "")), isolation_result)

        sources = cli(["knowledge-sources"])
        check("knowledge-source-list-is-redacted-and-bounded", sources.get("rawDocumentsIncluded") is False and all("snapshot" in item and "locatorRef" in item and "path" not in item for item in sources["sources"]), sources.get("count"))


try:
    main()
except Exception as error:
    checks.append({"label": "verifier-completed", "ok": False, "detail": traceback.format_exc()})

failed = [item for item in checks if not item["ok"]]
print(json.dumps({"ok": not failed, "schema": "aibi-semantic-patch-verify/v1", "checks": checks, "failedChecks": failed}, ensure_ascii=False, indent=2))
if failed:
    raise SystemExit(1)
