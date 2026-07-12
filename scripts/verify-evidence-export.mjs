import { existsSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const verifyDir = mkdtempSync(join(tmpdir(), "aibi-evidence-export-"));
const archivePath = join(verifyDir, "result.zip");
const env = {
  ...process.env,
  AIBI_HYBRID_DB_PATH: join(verifyDir, "runtime.sqlite"),
  AIBI_HYBRID_DUCKDB_PATH: join(verifyDir, "runtime.duckdb"),
  AIBI_EVIDENCE_BUNDLE_ROOT: join(verifyDir, "evidence-bundles"),
  AIBI_EXPORT_ROOT: join(verifyDir, "exports"),
  PYTHONIOENCODING: "utf-8",
};

function run(label, args) {
  const result = spawnSync("python", ["tools/bi_cli.py", "--json", ...args], { cwd: process.cwd(), env, encoding: "utf8", windowsHide: true });
  let parsed = null;
  try { parsed = JSON.parse(result.stdout.trim()); } catch { parsed = null; }
  return { label, ok: result.status === 0 && parsed?.ok === true, status: result.status, parsed, stderr: result.stderr, stdout: result.stdout };
}

function inspectArchive(path) {
  const code = [
    "import hashlib,json,sys,zipfile",
    "p=sys.argv[1]",
    "z=zipfile.ZipFile(p)",
    "names=sorted(z.namelist())",
    "manifest=json.loads(z.read('manifest.json'))",
    "payloads={n:z.read(n) for n in names}",
    "checksums={n:hashlib.sha256(payloads[n]).hexdigest() for n in names if n!='manifest.json'}",
    "print(json.dumps({'names':names,'manifest':manifest,'checksums':checksums,'combined':b'\\n'.join(payloads.values()).decode('utf-8','ignore')},ensure_ascii=False))",
  ].join(";");
  const result = spawnSync("python", ["-c", code, path], { cwd: process.cwd(), env, encoding: "utf8", windowsHide: true });
  return result.status === 0 ? JSON.parse(result.stdout) : { error: result.stderr || result.stdout };
}

try {
  const checks = [
    run("import", ["import-commit", "validation-inputs/orders.csv", "--table", "orders", "--name", "Orders", "--mode", "create", "--yes"]),
    run("dashboard", ["business-dashboard", "--op", "create", "--table", "orders", "--name", "Export verification", "--limit", "1", "--yes"]),
  ];
  const ask = run("ask", ["ask", "请用net_sales按channel生成柱状图"]);
  checks.push(ask);
  const actionKey = ask.parsed?.actionDraft?.actionKey;
  const receiptKey = ask.parsed?.queryPlanReceipt?.receiptKey;
  checks.push(run("confirm", ["confirm-action", actionKey, "--yes"]));
  const exported = run("export", ["export-evidence", "--receipt", receiptKey, "--output", archivePath]);
  checks.push(exported);
  checks.push({ label: "archive-created", ok: existsSync(archivePath) && exported.parsed?.evidenceExport?.schema === "aibi-evidence-export/v1" });
  const archive = inspectArchive(archivePath);
  const expectedFiles = ["README.txt", "answer.md", "chart-spec.json", "evidence/quality-gaps.json", "evidence/semantic-summary.json", "evidence/source-summary.json", "manifest.json", "query-plan.json"];
  checks.push({ label: "expected-files-only", ok: JSON.stringify(archive.names) === JSON.stringify(expectedFiles), parsed: archive.names });
  const manifestFiles = archive.manifest?.files ?? [];
  checks.push({
    label: "manifest-checksums-match",
    ok: manifestFiles.length === expectedFiles.length - 1
      && manifestFiles.every((item) => archive.checksums?.[item.path] === item.sha256),
  });
  const combined = String(archive.combined ?? "");
  checks.push({
    label: "export-excludes-sensitive-and-absolute-paths",
    ok: !combined.includes("C:\\Users\\")
      && !/[\"'](?:password|api[_-]?key|token|secret|credential)[\"']\s*:/i.test(combined)
      && !combined.includes("validation-inputs/orders.csv"),
  });
  checks.push({
    label: "export-reuses-query-receipt",
    ok: archive.manifest?.receiptKey === receiptKey
      && combined.includes(receiptKey)
      && combined.includes("net_sales")
      && combined.includes("channel")
      && combined.includes("whitelist aggregate query"),
  });

  const failedChecks = checks.filter((check) => !check.ok);
  console.log(JSON.stringify({
    ok: failedChecks.length === 0,
    schema: "aibi-evidence-export-verify/v1",
    generatedBy: "scripts/verify-evidence-export.mjs",
    checks: checks.map((check) => ({ label: check.label, ok: check.ok, status: check.status })),
    failedChecks: failedChecks.map((check) => ({ label: check.label, status: check.status, parsed: check.parsed, stderr: check.stderr, stdout: check.stdout?.slice(-1600) })),
  }, null, 2));
  if (failedChecks.length) process.exitCode = 1;
} finally {
  rmSync(verifyDir, { recursive: true, force: true });
}
