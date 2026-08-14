import { createServer } from "node:http";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { agentRuntimeRegistryForProject, shadowEvaluateProviders } from "../server/agentRuntimeProfile";
import { buildGroundedAgentContext, enrichAgentResultWithProvider, validateProviderOutboundContext } from "../server/agentProviderRuntime";

const root = resolve(import.meta.dirname, "..");
const tempRoot = mkdtempSync(join(tmpdir(), "aibi-c-runtime-profile-"));
const checks: Array<{ label: string; ok: boolean; detail?: string }> = [];
const check = (label: string, ok: boolean, detail = "") => checks.push({ label, ok, detail });
const baseEnv = {
  ...process.env,
  AIBI_HYBRID_DB_PATH: join(tempRoot, "runtime.sqlite"),
  AIBI_HYBRID_DUCKDB_PATH: join(tempRoot, "runtime.duckdb"),
  AIBI_AGENT_PROVIDER: "deterministic",
  DEEPSEEK_API_KEY: "",
};

function cli(args: string[], env = baseEnv) {
  const result = spawnSync(process.env.PYTHON ?? "python", ["tools/aibi_cli.py", "--json", ...args], {
    cwd: root,
    env,
    encoding: "utf8",
  });
  let payload: Record<string, unknown> = {};
  try { payload = JSON.parse(result.stdout || result.stderr || "{}"); } catch { /* surfaced through status */ }
  return { result, payload };
}

const deterministicResult = {
  ok: true,
  workspaceId: "default",
  answerCard: {
    kind: "comparison",
    confidence: "query-runtime",
    title: { zh: "结果", en: "Result" },
    summary: { zh: "指标为 12", en: "Metric is 12" },
    metrics: [{ label: { zh: "指标", en: "Metric" }, rawValue: 12, value: "12" }],
    rows: [{ forbiddenRawRow: "must-never-leave-local-runtime" }],
    evidenceRefs: [{ type: "queryRuntime" }],
  },
  matched: { table: { display_name: "业务表" }, dashboard: null },
  context: { knowledgeRules: [] },
  queryPlanReceipt: { receiptKey: "receipt-profile-fixture", status: "executed", selection: {}, unresolved: [] },
  analysisUnit: { unitKey: "unit-profile-fixture", status: "ready", validation: { status: "ready" } },
  actionDraft: { kind: "read-only", status: "read-only" },
  requiresConfirmation: false,
  llm: {},
};

let server: ReturnType<typeof createServer> | null = null;
try {
  const initial = cli(["agent-runtime-profiles"]);
  check("schema-v17-profile-catalog-boots", initial.result.status === 0 && initial.payload.selectedProfileId === "deterministic");
  check("registry-exposes-three-reviewed-profiles", Array.isArray(initial.payload.profiles) && initial.payload.profiles.length === 3);

  const preview = cli(["agent-runtime-profile-set", "--profile", "deepseek"]);
  const afterPreview = cli(["agent-runtime-profiles"]);
  check("profile-selection-is-dry-run-first", preview.payload.requiresConfirmation === true && afterPreview.payload.selectedProfileId === "deterministic");
  const confirm = cli(["agent-runtime-profile-set", "--profile", "deepseek", "--yes"]);
  const afterConfirm = cli(["agent-runtime-profiles"]);
  check("confirmed-profile-selection-persists", confirm.result.status === 0 && afterConfirm.payload.selectedProfileId === "deepseek");
  const configPath = join(tempRoot, "runtime-profile-config.json");
  const exported = cli(["export-config", configPath]);
  cli(["agent-runtime-profile-set", "--profile", "deterministic", "--yes"]);
  const applied = cli(["apply-config", configPath, "--yes"]);
  const afterRestore = cli(["agent-runtime-profiles"]);
  check("profile-selection-survives-config-export-restore", exported.result.status === 0 && applied.result.status === 0 && afterRestore.payload.selectedProfileId === "deepseek");

  const badAudit = cli([
    "agent-provider-evaluation-record", "--profile", "deepseek", "--provider", "deepseek", "--model", "test",
    "--status", "passed", "--audit-json", JSON.stringify({ prompt: "secret prompt" }),
  ]);
  check("evaluation-store-rejects-prompt-context-and-rows", badAudit.result.status !== 0);
  const recorded = cli([
    "agent-provider-evaluation-record", "--profile", "deepseek", "--provider", "deepseek", "--model", "test",
    "--status", "passed", "--validation-status", "passed", "--duration-ms", "9", "--total-tokens", "18",
    "--request-fingerprint", "a".repeat(64), "--context-fingerprint", "b".repeat(64),
    "--audit-json", JSON.stringify({ serverSideOnly: true, providerCanWrite: false }),
  ]);
  const dashboard = cli(["agent-provider-evaluations"]);
  const summary = dashboard.payload.summary as Record<string, unknown> | undefined;
  check("evaluation-dashboard-is-persistent-and-redacted", recorded.result.status === 0 && summary?.total === 1 && summary?.providerWriteCount === 0);

  process.env.AIBI_LOCAL_PROVIDER_BASE_URL = "https://example.com/v1";
  process.env.AIBI_LOCAL_PROVIDER_MODEL = "test-model";
  const rejectedRemote = agentRuntimeRegistryForProject(root, "local-openai");
  check("unreviewed-remote-openai-endpoint-is-rejected", rejectedRemote.provider.status().configured === false && rejectedRemote.provider.status().enabled === false);

  const context = buildGroundedAgentContext("指标是多少？", deterministicResult);
  const outbound = validateProviderOutboundContext(context);
  check("outbound-context-has-zero-raw-rows", outbound.ok && outbound.outboundRawRowCount === 0 && !JSON.stringify(context).includes("must-never-leave-local-runtime"));

  server = createServer(async (request, response) => {
    let body = "";
    for await (const chunk of request) body += String(chunk);
    check("local-provider-request-has-no-raw-rows", !body.includes("must-never-leave-local-runtime") && !body.includes('"rows"'));
    const narrative = JSON.stringify({
      summary: "本地证据显示指标为 12。",
      rationale: ["来自查询回执"],
      clarification: null,
      nextActions: ["核对证据"],
      citedEvidence: ["queryRuntime"],
      certainty: "grounded",
    });
    response.writeHead(200, { "content-type": "application/json" });
    response.end(JSON.stringify({ choices: [{ message: { content: narrative } }], usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 } }));
  });
  await new Promise<void>((resolveListen) => server!.listen(0, "127.0.0.1", resolveListen));
  const address = server.address();
  const port = address && typeof address === "object" ? address.port : 0;
  process.env.AIBI_LOCAL_PROVIDER_BASE_URL = `http://127.0.0.1:${port}`;
  process.env.AIBI_LOCAL_PROVIDER_MODEL = "test-model";
  const localRegistry = agentRuntimeRegistryForProject(root, "local-openai");
  check("explicit-loopback-openai-endpoint-is-enabled", localRegistry.provider.status().enabled && localRegistry.provider.status().baseUrl.includes(String(port)));
  const localResult = await enrichAgentResultWithProvider({ projectRoot: root, prompt: "指标是多少？", deterministicResult, provider: localRegistry.provider }) as Record<string, unknown>;
  check("provider-cannot-change-deterministic-receipt-or-boundary", JSON.stringify(localResult.queryPlanReceipt) === JSON.stringify(deterministicResult.queryPlanReceipt) && localResult.requiresConfirmation === deterministicResult.requiresConfirmation);
  const llm = localResult.llm as Record<string, unknown>;
  const audit = llm.audit as Record<string, unknown>;
  check("runtime-audit-binds-profile-validation-and-cost", audit.profileId === "local-openai" && (audit.validation as Record<string, unknown>)?.status === "passed" && audit.estimatedCostUsd === 0);

  const shadow = await shadowEvaluateProviders(root, ["local-openai"], context);
  check("shadow-evaluation-has-zero-receipt-and-draft-mutations", shadow.runs.length === 1 && shadow.runs[0].receiptMutationCount === 0 && shadow.runs[0].draftMutationCount === 0 && shadow.providerCanWrite === false);
} finally {
  if (server) await new Promise<void>((resolveClose) => server!.close(() => resolveClose()));
  delete process.env.AIBI_LOCAL_PROVIDER_BASE_URL;
  delete process.env.AIBI_LOCAL_PROVIDER_MODEL;
  rmSync(tempRoot, { recursive: true, force: true });
}

const failed = checks.filter((item) => !item.ok);
console.log(JSON.stringify({
  ok: failed.length === 0,
  schema: "aibi-agent-runtime-profile-verify/v1",
  fixedEvaluationSet: "provider-contract-core-v1",
  checks,
  failedChecks: failed,
}, null, 2));
if (failed.length) process.exitCode = 1;
