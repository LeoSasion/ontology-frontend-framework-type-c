import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const verifyDir = mkdtempSync(join(tmpdir(), "aibi-analysis-runs-"));
const env = {
  ...process.env,
  AIBI_HYBRID_DB_PATH: join(verifyDir, "runtime.sqlite"),
  AIBI_HYBRID_DUCKDB_PATH: join(verifyDir, "runtime.duckdb"),
  AIBI_EVIDENCE_BUNDLE_ROOT: join(verifyDir, "evidence"),
  PYTHONIOENCODING: "utf-8",
};

function run(label, args, expectedStatus = 0) {
  const result = spawnSync("python", ["tools/aibi_cli.py", "--json", ...args], { cwd: process.cwd(), env, encoding: "utf8", windowsHide: true });
  let parsed = null;
  try { parsed = JSON.parse(result.stdout.trim()); } catch { parsed = null; }
  return { label, ok: result.status === expectedStatus && (expectedStatus !== 0 || parsed?.ok === true), status: result.status, parsed, stderr: result.stderr, stdout: result.stdout };
}

try {
  const checks = [
    run("import", ["import-commit", "validation-inputs/orders.csv", "--table", "orders", "--name", "Orders", "--mode", "create", "--yes"]),
    run("dashboard", ["business-dashboard", "--op", "create", "--table", "orders", "--name", "Trajectory verification", "--limit", "1", "--yes"]),
  ];
  const root = run("root-analysis", ["ask", "请用net_sales按channel生成柱状图"]);
  checks.push(root);
  const rootRunKey = root.parsed?.analysisRun?.run_key;
  const rootActionKey = root.parsed?.actionDraft?.actionKey;
  checks.push({
    label: "root-links-receipt-and-action",
    ok: root.parsed?.analysisRun?.status === "pending_confirmation"
      && root.parsed?.analysisRun?.query_receipt_key === root.parsed?.queryPlanReceipt?.receiptKey
      && root.parsed?.analysisRun?.action_key === rootActionKey,
  });
  const premature = run("premature-branch-blocked", ["ask", "--parent-run", rootRunKey, "--branch-label", "分类比较", "换成按category比较"], 1);
  checks.push(premature);
  checks.push({ label: "branch-requires-confirmed-parent", ok: premature.parsed?.ok === false && /confirmed/i.test(String(premature.parsed?.error ?? "")) });
  const draftsBefore = run("no-extra-draft-after-block", ["action-drafts", "--limit", "10"]);
  checks.push(draftsBefore);
  checks.push({ label: "blocked-branch-has-no-side-effect", ok: draftsBefore.parsed?.pendingCount === 1 });

  checks.push(run("confirm-root-chart", ["confirm-action", rootActionKey, "--yes"]));
  const confirmedRoot = run("confirmed-root", ["analysis-runs", "--run", rootRunKey]);
  checks.push(confirmedRoot);
  checks.push({ label: "chart-confirmation-confirms-run", ok: confirmedRoot.parsed?.analysisRun?.status === "confirmed" });

  const branch = run("create-branch", ["ask", "--parent-run", rootRunKey, "--branch-label", "分类比较", "请用net_sales按category生成柱状图"]);
  checks.push(branch);
  const branchRunKey = branch.parsed?.analysisRun?.run_key;
  checks.push({
    label: "branch-links-parent",
    ok: branch.parsed?.analysisRun?.parent_run_key === rootRunKey
      && branch.parsed?.analysisRun?.branch_label === "分类比较"
      && branch.parsed?.analysisRun?.status === "pending_confirmation",
  });
  const tree = run("parent-with-branches", ["analysis-runs", "--run", rootRunKey]);
  checks.push(tree);
  checks.push({ label: "branch-is-listable", ok: tree.parsed?.branches?.length === 1 && tree.parsed?.branches?.[0]?.run_key === branchRunKey });
  checks.push(run("reject-branch", ["confirm-action", branch.parsed?.actionDraft?.actionKey, "--reject", "--yes"]));
  const rejected = run("rejected-branch", ["analysis-runs", "--run", branchRunKey]);
  checks.push(rejected);
  checks.push({ label: "rejection-updates-run", ok: rejected.parsed?.analysisRun?.status === "rejected" });

  const blocked = run("blocked-root", ["ask", "请用不存在字段生成柱状图"]);
  checks.push(blocked);
  checks.push({ label: "blocked-analysis-is-recorded", ok: blocked.parsed?.analysisRun?.status === "blocked" && blocked.parsed?.analysisRun?.parent_run_key == null });

  const failedChecks = checks.filter((check) => !check.ok);
  console.log(JSON.stringify({
    ok: failedChecks.length === 0,
    schema: "aibi-analysis-runs-verify/v1",
    generatedBy: "scripts/verify-analysis-runs.mjs",
    checks: checks.map((check) => ({ label: check.label, ok: check.ok, status: check.status })),
    failedChecks: failedChecks.map((check) => ({ label: check.label, status: check.status, parsed: check.parsed, stderr: check.stderr, stdout: check.stdout?.slice(-1600) })),
  }, null, 2));
  if (failedChecks.length) process.exitCode = 1;
} finally {
  rmSync(verifyDir, { recursive: true, force: true });
}
