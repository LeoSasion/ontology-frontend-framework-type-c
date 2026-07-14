import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";

const root = process.cwd();
const verifyDir = mkdtempSync(join(tmpdir(), "aibi-c-source-job-"));
const env = {
  ...process.env,
  AIBI_HYBRID_DB_PATH: join(verifyDir, "runtime.sqlite"),
  AIBI_HYBRID_DUCKDB_PATH: join(verifyDir, "runtime.duckdb"),
  AIBI_EVIDENCE_BUNDLE_ROOT: join(verifyDir, "evidence"),
  PYTHONIOENCODING: "utf-8",
};

function run(args, expectedStatus = 0) {
  const result = spawnSync("python", ["tools/bi_cli.py", "--json", ...args], {
    cwd: root,
    env,
    encoding: "utf8",
    windowsHide: true,
  });
  let parsed = null;
  try { parsed = JSON.parse(result.stdout.trim()); } catch { parsed = null; }
  return { ok: result.status === expectedStatus, status: result.status, parsed, stderr: result.stderr };
}

try {
  const checks = [];
  checks.push({ label: "bootstrap", ...run(["status"]) });
  const outputDir = join(verifyDir, "source-output");
  const created = run([
    "source-intelligence-job-create",
    "--label", "M7 verification",
    "--output-dir", outputDir,
    resolve(root, "validation-inputs/orders.csv"),
  ]);
  checks.push({
    label: "job-created-and-queued",
    ok: created.ok && created.parsed?.job?.status === "queued" && created.parsed?.job?.kind === "source-intelligence" && created.parsed?.job?.capabilityId === "cli.source-intelligence-job-run",
  });
  const jobKey = created.parsed?.job?.jobKey;
  const workspaceId = created.parsed?.job?.workspaceId;
  const executed = run(["source-intelligence-job-run", "--job", jobKey, "--workspace", workspaceId]);
  checks.push({ label: "worker-completes", ok: executed.ok && executed.parsed?.job?.status === "succeeded" });
  const detail = run(["jobs", "--job", jobKey]);
  const eventTypes = detail.parsed?.job?.events?.map((event) => event.type) ?? [];
  checks.push({
    label: "terminal-state-and-ordered-events",
    ok: detail.ok && detail.parsed?.job?.progress === 100 &&
      ["job_created", "job_queued", "job_running", "job_progress", "job_succeeded"].every((type) => eventTypes.includes(type)),
  });
  checks.push({
    label: "artifacts-and-evidence-preserved",
    ok: detail.parsed?.job?.artifactRefs?.length > 0 &&
      detail.parsed?.job?.evidenceRefs?.length === 1 &&
      existsSync(detail.parsed.job.evidenceRefs[0].path),
  });
  checks.push({
    label: "source-run-linked",
    ok: String(detail.parsed?.job?.sourceRunId ?? "").startsWith("source_intelligence_"),
  });

  const stranded = run([
    "source-intelligence-job-create",
    "--label", "stranded worker",
    resolve(root, "validation-inputs/orders.csv"),
  ]);
  const reconciled = run([
    "job-process-exit",
    "--job", stranded.parsed?.job?.jobKey,
    "--workspace", stranded.parsed?.job?.workspaceId,
    "--exit-code", "9",
  ]);
  checks.push({
    label: "owned-worker-exit-reconciled",
    ok: reconciled.ok && reconciled.parsed?.job?.status === "failed" && reconciled.parsed?.job?.error?.code === "worker-exited",
  });

  const crossRepo = run([
    "source-intelligence-job-create",
    "C:/Users/Administrator/Documents/AIBI-D/forbidden.csv",
  ], 1);
  checks.push({
    label: "other-aibi-repository-rejected",
    ok: crossRepo.ok && crossRepo.parsed?.ok === false && /another AIBI repository/.test(String(crossRepo.parsed?.error ?? "")),
  });

  const failedChecks = checks.filter((check) => !check.ok);
  console.log(JSON.stringify({
    ok: failedChecks.length === 0,
    schema: "aibi-source-intelligence-job-verify/v1",
    generatedBy: "scripts/verify-source-intelligence-job.mjs",
    checks: checks.map(({ label, ok }) => ({ label, ok })),
    failedChecks,
  }, null, 2));
  process.exitCode = failedChecks.length ? 1 : 0;
} finally {
  rmSync(verifyDir, { recursive: true, force: true });
}
