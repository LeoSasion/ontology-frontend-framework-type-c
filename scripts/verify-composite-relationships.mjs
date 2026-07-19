import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const root = process.cwd();
const verifyDir = mkdtempSync(join(tmpdir(), "aibi-composite-relationship-"));
const ordersFile = join(verifyDir, "orders.csv");
const refundsFile = join(verifyDir, "refunds.csv");
const refundsChangedFile = join(verifyDir, "refunds-changed.csv");
const databaseFile = join(verifyDir, "verify.sqlite");
writeFileSync(ordersFile, "order_id,item_id,channel,net_sales\nO1,I1,Douyin,100\nO1,I2,Douyin,200\nO2,I1,Tmall,150\n", "utf8");
writeFileSync(refundsFile, "order_id,item_id,refund_amount\nO1,I1,10\nO1,I2,20\nO2,I1,5\nO2,I2,7\n", "utf8");
writeFileSync(refundsChangedFile, "order_id,item_id,refund_total\nO1,I1,10\nO1,I2,20\nO2,I1,5\n", "utf8");

const env = {
  ...process.env,
  AIBI_HYBRID_DB_PATH: databaseFile,
  AIBI_HYBRID_DUCKDB_PATH: join(verifyDir, "verify.duckdb"),
  PYTHONIOENCODING: "utf-8",
};

function run(label, args) {
  const result = spawnSync("python", ["tools/aibi_cli.py", "--json", ...args], {
    cwd: root,
    encoding: "utf8",
    env,
    windowsHide: true,
  });
  let parsed = null;
  try {
    parsed = JSON.parse(result.stdout.trim());
  } catch {
    parsed = null;
  }
  return { label, status: result.status, parsed, stdout: result.stdout, stderr: result.stderr };
}

function bindCurrentBatch(label, batchId, tableKeys) {
  const script = [
    "import json, sqlite3, sys",
    "db = sqlite3.connect(sys.argv[1])",
    "batch = sys.argv[2]",
    "keys = sys.argv[3:]",
    "placeholders = ','.join('?' for _ in keys)",
    "rows = db.execute(f\"SELECT table_key, data_version, row_count FROM table_registry WHERE workspace_id = 'default' AND table_key IN ({placeholders})\", keys).fetchall()",
    "db.execute(\"INSERT INTO source_runs(id, workspace_id, table_key, name, status, source_file, row_count, column_count, profile_json, evidence_json, created_at) VALUES(?, 'default', '__batch__', ?, 'ready', 'fixture-batch', ?, 0, '{}', '[]', '2026-07-19T12:00:00Z')\", (batch, batch, sum(int(row[2] or 0) for row in rows)))",
    "db.executemany(\"INSERT INTO source_run_tables(source_run_id, workspace_id, table_key, data_version, row_count, created_at) VALUES(?, 'default', ?, ?, ?, '2026-07-19T12:00:00Z')\", [(batch, row[0], int(row[1] or 0), int(row[2] or 0)) for row in rows])",
    "db.execute(\"UPDATE workspaces SET current_source_run_id = ? WHERE id = 'default'\", (batch,))",
    "db.commit()",
    "print(json.dumps({'ok': len(rows) == len(keys), 'tableKeys': sorted(row[0] for row in rows)}))",
  ].join("; ");
  const result = spawnSync("python", ["-c", script, databaseFile, batchId, ...tableKeys], {
    cwd: root,
    encoding: "utf8",
    env,
    windowsHide: true,
  });
  let parsed = null;
  try {
    parsed = JSON.parse(result.stdout.trim());
  } catch {
    parsed = null;
  }
  return { label, status: result.status, parsed, stdout: result.stdout, stderr: result.stderr };
}

const results = [];
try {
  const apiMapping = spawnSync("node", ["--import", "tsx", "-e", "import('./server/modelRoutes.ts').then(({appendRelationshipMappingArgs,appendRelationshipFilterArgs,appendRelationshipPreaggregationArg}) => { const args=[]; const body={fieldMappings:[{leftField:'order_id',rightField:'order_id'},{leftField:'item_id',rightField:'item_id'}],filters:[{phase:'pre',side:'right',field:'refund_amount',operator:'gt',value:'5'}],preaggregation:{side:'right',groupFields:['order_id'],measures:[{field:'refund_amount',aggregation:'sum'}]}}; appendRelationshipMappingArgs(args,body); appendRelationshipFilterArgs(args,body); appendRelationshipPreaggregationArg(args,body); console.log(JSON.stringify({ok:args.filter((item)=>item==='--map-json').length===2&&args.includes('--filter-json')&&args.includes('--preaggregate-json'),args})); })"], { cwd: root, encoding: "utf8", windowsHide: true });
  results.push({ label: "api-mapping", status: apiMapping.status, parsed: JSON.parse(apiMapping.stdout.trim()), stdout: apiMapping.stdout, stderr: apiMapping.stderr });
  const uiPayload = spawnSync("node", ["--import", "tsx", "-e", "import('./src/dashboardCanvasRelationshipModel.ts').then(({buildRelationshipSavePayload}) => { const payload=buildRelationshipSavePayload({leftTableKey:'orders',rightTableKey:'refunds',fieldMappings:[{leftField:'order_id',rightField:'order_id'},{leftField:'item_id',rightField:'item_id'}],joinType:'left'},false); console.log(JSON.stringify({ok:payload?.fieldMappings?.length===2,payload})); })"], { cwd: root, encoding: "utf8", windowsHide: true });
  results.push({ label: "ui-payload", status: uiPayload.status, parsed: JSON.parse(uiPayload.stdout.trim()), stdout: uiPayload.stdout, stderr: uiPayload.stderr });
  results.push(run("initialize", ["status"]));
  const legacySetup = spawnSync("python", ["-c", [
    "import sqlite3, sys",
    "db = sqlite3.connect(sys.argv[1])",
    "db.execute('DROP TABLE relationships')",
    "db.execute(\"CREATE TABLE relationships(relation_key TEXT NOT NULL, workspace_id TEXT NOT NULL DEFAULT 'default', name TEXT NOT NULL, left_table_key TEXT NOT NULL, right_table_key TEXT NOT NULL, left_field TEXT NOT NULL, right_field TEXT NOT NULL, join_type TEXT NOT NULL, confidence REAL NOT NULL, created_at TEXT NOT NULL, PRIMARY KEY(workspace_id, relation_key))\")",
    "db.execute(\"INSERT INTO relationships VALUES('legacy_rel', 'default', 'legacy', 'legacy_left', 'legacy_right', 'id', 'id', 'inner', 0.9, '2026-01-01T00:00:00Z')\")",
    "db.commit()",
  ].join(";"), databaseFile], { cwd: root, encoding: "utf8", windowsHide: true });
  results.push({ label: "legacy-setup", status: legacySetup.status, parsed: null, stdout: legacySetup.stdout, stderr: legacySetup.stderr });
  results.push(run("legacy-list", ["list-relationships"]));
  results.push(run("import-orders", ["import-commit", ordersFile, "--table", "orders", "--name", "订单", "--mode", "create", "--yes"]));
  results.push(run("import-refunds", ["import-commit", refundsFile, "--table", "refunds", "--name", "退款", "--mode", "create", "--yes"]));
  results.push(bindCurrentBatch("bind-current-source-run-batch", "composite-relationship-fixture-batch", ["orders", "refunds"]));
  results.push(run("single-preview", ["relationship-preview", "--left-table", "orders", "--right-table", "refunds", "--map", "order_id:order_id"]));
  results.push(run("single-save", ["relationship-save", "--left-table", "orders", "--right-table", "refunds", "--map", "order_id:order_id", "--yes"]));
  results.push(run("single-query-blocked", ["query-relationship", "--relationship", "orders_refunds_order_id_order_id", "--group", "left:channel", "--measure", "right:refund_amount", "--agg", "sum"]));
  results.push(run("composite-preview", ["relationship-preview", "--left-table", "orders", "--right-table", "refunds", "--map", "order_id:order_id", "--map", "item_id:item_id"]));
  results.push(run("composite-save-dry-run", ["relationship-save", "--left-table", "orders", "--right-table", "refunds", "--map", "order_id:order_id", "--map", "item_id:item_id"]));
  results.push(run("composite-save", ["relationship-save", "--left-table", "orders", "--right-table", "refunds", "--map", "order_id:order_id", "--map", "item_id:item_id", "--yes"]));
  results.push(run("list", ["list-relationships"]));
  results.push(run("composite-query", ["query-relationship", "--relationship", "orders_refunds_order_id_order_id_item_id_item_id", "--group", "left:channel", "--measure", "right:refund_amount", "--agg", "sum", "--sort-direction", "asc"]));
  const persistedFilter = JSON.stringify({ phase: "pre", side: "right", field: "refund_amount", operator: "gt", value: "5" });
  const rightPreaggregation = JSON.stringify({ side: "right", groupFields: ["order_id"], measures: [{ field: "refund_amount", aggregation: "sum" }] });
  results.push(run("preaggregation-preview", ["relationship-preview", "--left-table", "orders", "--right-table", "refunds", "--map", "order_id:order_id", "--filter-json", persistedFilter, "--preaggregate-json", rightPreaggregation]));
  results.push(run("preaggregation-save", ["relationship-save", "--left-table", "orders", "--right-table", "refunds", "--map", "order_id:order_id", "--filter-json", persistedFilter, "--preaggregate-json", rightPreaggregation, "--yes"]));
  results.push(run("preaggregation-list", ["list-relationships"]));
  results.push(run("preaggregation-query", ["query-relationship", "--relationship", "orders_refunds_order_id_order_id", "--group", "left:channel", "--measure", "left:net_sales", "--agg", "sum", "--sort-direction", "asc"]));
  results.push(run("remove-composite-before-semantic", ["remove-relationship", "--relationship", "orders_refunds_order_id_order_id_item_id_item_id", "--yes"]));
  results.push(run("semantic-single-hop-query", ["semantic-query", "按 channel 看 refund_amount", "--table", "orders", "--limit", "20"]));
  results.push(run("agent-semantic-single-hop", ["ask", "订单 按 channel 看 refund_amount", "--read-only"]));
  results.push(run("replace-refunds", ["import-commit", refundsChangedFile, "--table", "refunds", "--name", "退款", "--mode", "replace", "--yes"]));
  results.push(run("list-after-source-change", ["list-relationships"]));
  results.push(run("inspect-refunds-after-source-change", ["inspect-table", "refunds"]));
  results.push(run("stale-preaggregation-query", ["query-relationship", "--relationship", "orders_refunds_order_id_order_id", "--group", "left:channel", "--measure", "left:net_sales", "--agg", "sum"]));

  const byLabel = Object.fromEntries(results.map((item) => [item.label, item]));
  const compositeSaved = byLabel["composite-save"].parsed?.saved;
  const listedComposite = byLabel.list.parsed?.relationships?.find((item) => item.relation_key === compositeSaved?.relation_key);
  const queryRows = byLabel["composite-query"].parsed?.relationshipQuery?.rows ?? [];
  const queryMetricName = byLabel["composite-query"].parsed?.relationshipQuery?.metricName;
  const queryValues = Object.fromEntries(queryRows.map((row) => [row["左表.channel"], row[queryMetricName]]));
  const listedLegacy = byLabel["legacy-list"].parsed?.relationships?.find((item) => item.relation_key === "legacy_rel");
  const preaggregatedSaved = byLabel["preaggregation-save"].parsed?.saved;
  const listedPreaggregated = byLabel["preaggregation-list"].parsed?.relationships?.find((item) => item.relation_key === "orders_refunds_order_id_order_id");
  const preaggregationRows = byLabel["preaggregation-query"].parsed?.relationshipQuery?.rows ?? [];
  const preaggregationMetric = byLabel["preaggregation-query"].parsed?.relationshipQuery?.metricName;
  const preaggregationValues = Object.fromEntries(preaggregationRows.map((row) => [row["左表.channel"], row[preaggregationMetric]]));
  const semanticRows = byLabel["semantic-single-hop-query"].parsed?.relationshipQuery?.rows ?? [];
  const semanticMetric = byLabel["semantic-single-hop-query"].parsed?.relationshipQuery?.metricName;
  const semanticValues = Object.fromEntries(semanticRows.map((row) => [row["左表.channel"], row[semanticMetric]]));
  const agentSemanticRows = byLabel["agent-semantic-single-hop"].parsed?.answerCard?.rows ?? [];
  const agentSemanticValues = Object.fromEntries(agentSemanticRows.map((row) => [row.label, row.value]));
  const stalePreaggregation = byLabel["list-after-source-change"].parsed?.relationships?.find((item) => item.relation_key === "orders_refunds_order_id_order_id");
  const checks = [
    {
      label: "api-and-ui-preserve-composite-mappings",
      ok: byLabel["api-mapping"].status === 0
        && byLabel["api-mapping"].parsed?.ok === true
        && byLabel["ui-payload"].status === 0
        && byLabel["ui-payload"].parsed?.ok === true,
    },
    {
      label: "legacy-single-field-row-migrates-without-data-loss",
      ok: byLabel["legacy-setup"].status === 0
        && listedLegacy?.fieldMappings?.length === 1
        && listedLegacy?.fieldMappings?.[0]?.leftField === "id"
        && listedLegacy?.fieldMappings?.[0]?.rightField === "id",
    },
    {
      label: "multi-table-fixture-is-one-current-source-run",
      ok: byLabel["bind-current-source-run-batch"].status === 0
        && byLabel["bind-current-source-run-batch"].parsed?.ok === true
        && byLabel["bind-current-source-run-batch"].parsed?.tableKeys?.join(",") === "orders,refunds",
    },
    {
      label: "single-key-preview-detects-inflation",
      ok: byLabel["single-preview"].parsed?.relationshipPreview?.metrics?.rowExpansion === 2,
    },
    {
      label: "single-key-validation-blocks-query",
      ok: byLabel["single-save"].parsed?.saved?.validation?.status === "review-required"
        && byLabel["single-query-blocked"].status !== 0,
    },
    {
      label: "composite-preview-removes-inflation",
      ok: byLabel["composite-preview"].parsed?.relationshipPreview?.metrics?.rowExpansion === 1
        && byLabel["composite-preview"].parsed?.relationship?.fieldMappings?.length === 2,
    },
    {
      label: "composite-save-preserves-all-mappings-and-validation",
      ok: byLabel["composite-save-dry-run"].parsed?.requiresConfirmation === true
        && compositeSaved?.fieldMappings?.length === 2
        && compositeSaved?.validation?.status === "validated"
        && listedComposite?.fieldMappings?.length === 2
        && listedComposite?.validation?.status === "validated",
    },
    {
      label: "saved-composite-query-uses-complete-key",
      ok: byLabel["composite-query"].status === 0
        && queryRows.length === 2
        && Number(queryValues.Douyin) === 30
        && Number(queryValues.Tmall) === 5,
    },
    {
      label: "pre-filter-and-right-preaggregation-remove-expansion",
      ok: byLabel["preaggregation-preview"].status === 0
        && byLabel["preaggregation-preview"].parsed?.relationshipPreview?.metrics?.rightRowsBeforeFilters === 4
        && byLabel["preaggregation-preview"].parsed?.relationshipPreview?.metrics?.rightRows === 2
        && byLabel["preaggregation-preview"].parsed?.relationshipPreview?.metrics?.rowExpansion === 1,
    },
    {
      label: "saved-relationship-persists-filter-and-preaggregation",
      ok: preaggregatedSaved?.filters?.[0]?.phase === "pre"
        && preaggregatedSaved?.preaggregation?.groupFields?.[0] === "order_id"
        && listedPreaggregated?.filters?.[0]?.field === "refund_amount"
        && listedPreaggregated?.preaggregation?.measures?.[0]?.aggregation === "sum"
        && listedPreaggregated?.validation?.status === "validated",
    },
    {
      label: "saved-preaggregation-query-avoids-left-measure-inflation",
      ok: byLabel["preaggregation-query"].status === 0
        && Number(preaggregationValues.Douyin) === 300
        && Number(preaggregationValues.Tmall) === 150,
    },
    {
      label: "semantic-test-has-one-explicit-business-path",
      ok: byLabel["remove-composite-before-semantic"].status === 0
        && byLabel["remove-composite-before-semantic"].parsed?.confirmed === true,
    },
    {
      label: "semantic-plan-executes-saved-single-hop-safety-policy",
      ok: byLabel["semantic-single-hop-query"].status === 0
        && byLabel["semantic-single-hop-query"].parsed?.executed === true
        && byLabel["semantic-single-hop-query"].parsed?.executionPlan?.status === "ready"
        && byLabel["semantic-single-hop-query"].parsed?.executionPlan?.planHash?.length === 64
        && Number(semanticValues.Douyin) === 30
        && Number(semanticValues.Tmall) === 7,
    },
    {
      label: "agent-reuses-semantic-execution-plan-and-receipt",
      ok: byLabel["agent-semantic-single-hop"].status === 0
        && byLabel["agent-semantic-single-hop"].parsed?.answerCard?.kind === "semantic-relationship-analysis"
        && byLabel["agent-semantic-single-hop"].parsed?.queryPlanReceipt?.status === "executed"
        && byLabel["agent-semantic-single-hop"].parsed?.queryPlanReceipt?.selection?.executionPlan?.planHash?.length === 64
        && byLabel["agent-semantic-single-hop"].parsed?.queryPlanReceipt?.runtime?.executionPlanHash?.length === 64
        && Number(agentSemanticValues.Douyin) === 30
        && Number(agentSemanticValues.Tmall) === 7,
    },
    {
      label: "source-change-increments-version-and-auto-revalidates",
      ok: byLabel["replace-refunds"].status === 0
        && byLabel["replace-refunds"].parsed?.result?.dataVersion === 2
        && byLabel["replace-refunds"].parsed?.result?.relationshipRevalidations?.some((item) =>
          item.relationKey === "orders_refunds_order_id_order_id" && item.status === "stale"
        )
        && byLabel["inspect-refunds-after-source-change"].parsed?.table?.data_version === 2,
    },
    {
      label: "failed-auto-revalidation-blocks-stale-query",
      ok: stalePreaggregation?.validation?.status === "stale"
        && stalePreaggregation?.validation?.blockers?.includes("revalidation-failed")
        && byLabel["stale-preaggregation-query"].status !== 0,
    },
  ];
  const failedChecks = checks.filter((check) => !check.ok);
  console.log(JSON.stringify({
    ok: failedChecks.length === 0,
    schema: "aibi-composite-relationship-verify/v1",
    checks,
    failedChecks: failedChecks.map((check) => ({
      ...check,
      results: Object.fromEntries(results.map((item) => [item.label, { status: item.status, parsed: item.parsed, stderr: item.stderr.slice(-1000) }])),
    })),
  }, null, 2));
  process.exitCode = failedChecks.length ? 1 : 0;
} finally {
  rmSync(verifyDir, { recursive: true, force: true });
}
