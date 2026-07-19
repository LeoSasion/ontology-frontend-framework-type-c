import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const verifyDir = mkdtempSync(join(tmpdir(), "aibi-c-semantic-cli-p2-"));
const env = {
  ...process.env,
  AIBI_HYBRID_DB_PATH: join(verifyDir, "runtime.sqlite"),
  AIBI_HYBRID_DUCKDB_PATH: join(verifyDir, "runtime.duckdb"),
  AIBI_EVIDENCE_BUNDLE_ROOT: join(verifyDir, "evidence"),
  PYTHONIOENCODING: "utf-8",
};
const checks = [];

function check(label, ok, detail = null) {
  checks.push({ label, ok: Boolean(ok), detail });
}

function run(label, args, expectedStatus = 0) {
  const result = spawnSync("python", ["tools/aibi_cli.py", "--json", ...args], {
    cwd: process.cwd(), env, encoding: "utf8", windowsHide: true,
  });
  let parsed = null;
  try { parsed = JSON.parse(result.stdout.trim()); } catch { parsed = null; }
  check(label, result.status === expectedStatus && Boolean(parsed), {
    status: result.status,
    stderr: result.stderr?.slice(-800),
    stdout: result.stdout?.slice(-1200),
  });
  return parsed;
}

function bindCurrentBatch(tableKeys) {
  const script = `
import json, sqlite3, sys
database, raw_keys = sys.argv[1], sys.argv[2]
keys = json.loads(raw_keys)
connection = sqlite3.connect(database)
try:
    placeholders = ", ".join("?" for _ in keys)
    rows = connection.execute(
        f"SELECT table_key, data_version, row_count FROM table_registry WHERE workspace_id = 'default' AND table_key IN ({placeholders})",
        keys,
    ).fetchall()
    batch_id = "fixture-batch-current"
    connection.execute(
        "INSERT INTO source_runs(id, workspace_id, table_key, name, status, source_file, row_count, column_count, profile_json, evidence_json, created_at) VALUES(?, 'default', '__batch__', ?, 'ready', 'fixture-batch', ?, 0, '{}', '[]', '2026-07-19T12:00:00Z')",
        (batch_id, batch_id, sum(int(row[2] or 0) for row in rows)),
    )
    for table_key, data_version, row_count in rows:
        connection.execute(
            "INSERT INTO source_run_tables(source_run_id, workspace_id, table_key, data_version, row_count, created_at) VALUES(?, 'default', ?, ?, ?, '2026-07-19T12:00:00Z')",
            (batch_id, table_key, int(data_version or 0), int(row_count or 0)),
        )
    connection.execute("UPDATE workspaces SET current_source_run_id = ? WHERE id = 'default'", (batch_id,))
    connection.commit()
finally:
    connection.close()
`;
  const result = spawnSync("python", ["-c", script, env.AIBI_HYBRID_DB_PATH, JSON.stringify(tableKeys)], {
    cwd: process.cwd(), env, encoding: "utf8", windowsHide: true,
  });
  check("bind-current-source-run-batch", result.status === 0, {
    status: result.status,
    stderr: result.stderr?.slice(-800),
  });
}

try {
  const files = {
    regions: "region_id,region_name\nr1,North\nr2,South\n",
    sites: "site_id,region_id\ns1,r1\ns2,r2\n",
    assets: "asset_id,site_id,asset_type\na1,s1,sensor\na2,s1,pump\na3,s2,sensor\na4,s2,idle\n",
    observations: "observation_id,asset_id,observation_value\no1,a1,10\no2,a1,8\no3,a2,40\no4,a3,26\n",
  };
  for (const [table, contents] of Object.entries(files)) {
    const file = join(verifyDir, `${table}.csv`);
    writeFileSync(file, contents, "utf8");
    const imported = run(`import-${table}`, ["import-commit", file, "--table", table, "--name", table, "--mode", "create", "--yes"]);
    check(`import-${table}-committed`, imported?.ok === true && imported?.committed === true && imported?.result?.tableKey === table, imported);
  }
  bindCurrentBatch(Object.keys(files));

  const relationships = [
    ["regions", "sites", "region_id"],
    ["sites", "assets", "site_id"],
    ["assets", "observations", "asset_id"],
  ];
  for (const [left, right, field] of relationships) {
    const saved = run(`save-${left}-${right}`, [
      "relationship-save", "--left-table", left, "--right-table", right,
      "--left-field", field, "--right-field", field, "--join-type", "left", "--yes",
    ]);
    check(`save-${left}-${right}-validated`, saved?.ok === true && saved?.saved?.validation?.status === "validated", saved);
  }

  const semantic = run("semantic-query-three-hop", [
    "semantic-query", "按 region_name 和 asset_type 汇总 observation_value", "--table", "regions",
  ]);
  const proof = semantic?.relationshipPathProof;
  const receipt = semantic?.queryPlanReceipt;
  const rows = semantic?.rows ?? [];
  const rowValues = new Map(rows.map((row) => [String(row.label), Number(row.value)]));
  check("semantic-query-executes-three-hop", semantic?.executed === true && semantic?.executionPlan?.status === "ready", semantic?.executionPlan);
  check("three-hop-results-are-exact", rowValues.get("North / pump") === 40 && rowValues.get("North / sensor") === 18 && rowValues.get("South / sensor") === 26, rows);
  check("runtime-proof-verifies-every-hop", proof?.status === "verified" && proof?.hopProofs?.length === 3 && proof.hopProofs.every((hop) => hop.proofStatus === "verified"), proof);
  check("receipt-binds-all-four-sources", receipt?.status === "executed" && receipt?.source?.tableKeys?.join(",") === "regions,sites,assets,observations" && receipt?.source?.tables?.length === 4, receipt?.source);
  check(
    "receipt-binds-runtime-path-proof",
    receipt?.selection?.relationshipPathProof?.length === 3
      && receipt.selection.relationshipPathProof.every((hop) => typeof hop.proofFingerprint === "string" && hop.proofFingerprint.length === 64)
      && receipt?.selection?.executionPlan?.relationshipPathProof?.fingerprint === proof?.fingerprint
      && typeof receipt?.source?.relationshipPathFingerprint === "string"
      && receipt.source.relationshipPathFingerprint.length === 64,
    receipt?.selection,
  );
  check("analysis-unit-binds-receipt-and-grain", semantic?.analysisUnit?.status === "ready" && semantic?.analysisUnit?.queryReceiptKey === receipt?.receiptKey && semantic?.analysisUnit?.grain?.dimensions?.length === 2 && semantic?.analysisUnit?.grain?.sourceTableKeys?.length === 4, semantic?.analysisUnit);
  check(
    "analysis-unit-preserves-independent-dimension-columns",
    semantic?.analysisUnit?.shape?.dimensionColumns?.join(",") === "regions.region_name,assets.asset_type"
      && semantic?.analysisUnit?.grain?.dimensions?.map((item) => item.resultColumn).join(",") === "regions.region_name,assets.asset_type"
      && semantic?.analysisUnit?.rows?.every((row) => "regions.region_name" in row && "assets.asset_type" in row),
    semantic?.analysisUnit,
  );

  const nullPrompt = "按 asset_type 看 observation_value，asset_type=idle";
  const nullSemantic = run("semantic-left-join-null", ["semantic-query", nullPrompt, "--table", "assets"]);
  check(
    "semantic-left-join-preserves-null-through-receipt-and-analysis-unit",
    nullSemantic?.executed === true
      && nullSemantic?.rows?.length === 1
      && nullSemantic.rows[0]?.label === "idle"
      && nullSemantic.rows[0]?.value === null
      && nullSemantic?.queryPlanReceipt?.status === "executed"
      && nullSemantic?.queryPlanReceipt?.resultBinding?.rowCount === 1
      && nullSemantic?.analysisUnit?.status === "blocked"
      && nullSemantic?.analysisUnit?.rows?.[0]?.value === null
      && nullSemantic?.analysisUnit?.resultFingerprint === nullSemantic?.queryPlanReceipt?.resultBinding?.resultFingerprint
      && nullSemantic?.analysisUnit?.validation?.blockers?.includes("numeric-measure-not-found"),
    nullSemantic,
  );

  const nullAgent = run("agent-left-join-null", ["ask", nullPrompt]);
  check(
    "agent-labels-null-as-no-data-without-inventing-zero",
    nullAgent?.executionPlan?.status === "ready"
      && nullAgent?.answerCard?.rows?.length === 1
      && nullAgent.answerCard.rows[0]?.value === null
      && nullAgent?.answerCard?.metrics?.[0]?.rawValue === null
      && nullAgent?.answerCard?.metrics?.[0]?.value === "无数据 / No data"
      && String(nullAgent?.answerCard?.summary?.zh ?? "").includes("暂无可聚合数据")
      && String(nullAgent?.answerCard?.summary?.en ?? "").includes("no data")
      && nullAgent?.queryPlanReceipt?.status === "executed"
      && nullAgent?.analysisUnit?.rows?.[0]?.value === null,
    nullAgent,
  );

  const unitKey = semantic?.analysisUnit?.unitKey ?? "missing";
  const current = run("analysis-unit-current", ["analysis-unit-verify", "--unit", unitKey]);
  check("analysis-unit-is-current-before-drift", current?.ok === true && current?.sourceCurrent === true, current);

  const changedSites = join(verifyDir, "sites-changed.csv");
  writeFileSync(changedSites, "site_id,region_id\ns1,r1\ns2,r2\ns3,r1\n", "utf8");
  run("replace-intermediate-source", ["import-commit", changedSites, "--table", "sites", "--name", "sites", "--mode", "replace", "--yes"]);
  const drifted = run("analysis-unit-drifted", ["analysis-unit-verify", "--unit", unitKey], 1);
  check("intermediate-source-drift-blocks-analysis-unit", drifted?.ok === false && drifted?.sourceCurrent === false && drifted?.blockers?.includes("analysis-unit-source-drifted"), drifted);
} finally {
  rmSync(verifyDir, { recursive: true, force: true });
}

const failedChecks = checks.filter((item) => !item.ok);
console.log(JSON.stringify({
  ok: failedChecks.length === 0,
  schema: "aibi-semantic-query-cli-p2-verify/v1",
  generatedBy: "scripts/verify-semantic-query-cli-p2.mjs",
  checks: checks.map(({ label, ok }) => ({ label, ok })),
  failedChecks,
}, null, 2));
if (failedChecks.length) process.exitCode = 1;
