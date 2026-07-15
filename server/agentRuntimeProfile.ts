import { createHash, randomUUID } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { AgentProvider, AgentProviderRun, AgentProviderStatus, GroundedAgentContext } from "./agentProvider";
import { createDeepSeekProvider, loadDeepSeekProviderConfig } from "./deepseekProvider";

export type AgentRuntimeProfile = AgentProviderStatus & {
  schema: "aibi-agent-runtime-profile/v1";
  selected: boolean;
  version: 1;
  businessSemanticAuthority: "deterministic-local-bi";
  toolPermissions: [];
  outboundFields: string[];
};

function envForProject(projectRoot: string) {
  const path = resolve(projectRoot, ".env");
  if (!existsSync(path)) return process.env;
  const local = Object.fromEntries(
    readFileSync(path, "utf8")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith("#") && line.includes("="))
      .map((line) => {
        const at = line.indexOf("=");
        return [line.slice(0, at).trim(), line.slice(at + 1).trim().replace(/^['"]|['"]$/g, "")];
      }),
  );
  return { ...local, ...process.env };
}

function fingerprint(profileId: string, value: Record<string, unknown>) {
  return createHash("sha256").update(JSON.stringify({ schema: "aibi-agent-runtime-profile/v1", profileId, ...value })).digest("hex");
}

function bounded(value: string | undefined, fallback: number, min: number, max: number) {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  return Number.isInteger(parsed) ? Math.max(min, Math.min(max, parsed)) : fallback;
}

function localEndpoint(value: string | undefined) {
  if (!value) return null;
  try {
    const url = new URL(value);
    const host = url.hostname.toLowerCase();
    if (!(["127.0.0.1", "localhost", "::1"].includes(host) && ["http:", "https:"].includes(url.protocol))) return null;
    return url.href.replace(/\/$/, "");
  } catch {
    return null;
  }
}

function deterministicProvider(): AgentProvider {
  const profileFingerprint = fingerprint("deterministic", { provider: "deterministic", model: "local-bi-runtime", version: 1 });
  const status: AgentProviderStatus = {
    profileId: "deterministic",
    profileFingerprint,
    provider: "deterministic",
    model: "local-bi-runtime",
    configured: true,
    enabled: false,
    mode: "deterministic",
    baseUrl: "",
    wireApi: "none",
    structuredOutput: "native-contract",
    contextWindow: 0,
    reasoningBudget: "none",
    maxOutputTokens: 0,
    retries: 0,
    stages: ["intent", "context", "plan", "execute", "validate", "explain"],
    outboundPolicy: "deterministic-only",
  };
  return {
    status: () => ({ ...status }),
    async generate(): Promise<AgentProviderRun> {
      return {
        ok: false,
        provider: status.provider,
        model: status.model,
        runId: randomUUID(),
        attempts: 0,
        durationMs: 0,
        requestHash: "",
        usage: null,
        estimatedCostUsd: 0,
        profileId: status.profileId,
        profileFingerprint: status.profileFingerprint,
        validation: { status: "not-run", checks: {} },
        narrative: null,
        errorCode: "deterministic_profile",
      };
    },
  };
}

function profileFromProvider(provider: AgentProvider, selectedProfileId: string): AgentRuntimeProfile {
  const status = provider.status();
  return {
    schema: "aibi-agent-runtime-profile/v1",
    ...status,
    selected: status.profileId === selectedProfileId,
    version: 1,
    businessSemanticAuthority: "deterministic-local-bi",
    toolPermissions: [],
    outboundFields: status.outboundPolicy === "grounded-context-v1"
      ? ["question", "workspaceId", "answer", "matched", "knowledgeRules", "queryReceipt", "analysisUnit", "actionBoundary", "contextBudget"]
      : [],
  };
}

export function agentRuntimeRegistryForProject(projectRoot: string, selectedProfileId = "deterministic") {
  const env = envForProject(projectRoot);
  const deterministic = deterministicProvider();
  const deepSeekConfig = loadDeepSeekProviderConfig(projectRoot);
  const deepseek = createDeepSeekProvider({
    config: {
      ...deepSeekConfig,
      enabled: selectedProfileId === "deepseek",
      profileId: "deepseek",
      profileFingerprint: fingerprint("deepseek", {
        provider: "deepseek",
        model: deepSeekConfig.model,
        contextWindow: deepSeekConfig.contextWindow,
        maxTokens: deepSeekConfig.maxTokens,
        retries: deepSeekConfig.retries,
      }),
    },
  });
  const baseUrl = localEndpoint(env.AIBI_LOCAL_PROVIDER_BASE_URL);
  const model = /^[A-Za-z0-9._:/-]{1,160}$/.test(String(env.AIBI_LOCAL_PROVIDER_MODEL ?? ""))
    ? String(env.AIBI_LOCAL_PROVIDER_MODEL)
    : "local-model";
  const localProfileFingerprint = fingerprint("local-openai", {
    provider: "local-openai-compatible",
    model,
    baseUrl: baseUrl ?? "not-configured",
    contextWindow: bounded(env.AIBI_LOCAL_PROVIDER_CONTEXT_WINDOW, 32_768, 2_048, 1_000_000),
    maxTokens: bounded(env.AIBI_LOCAL_PROVIDER_MAX_TOKENS, 600, 128, 4_000),
    retries: bounded(env.AIBI_LOCAL_PROVIDER_RETRIES, 1, 0, 3),
  });
  const local = createDeepSeekProvider({
    config: {
      apiKey: baseUrl && env.AIBI_LOCAL_PROVIDER_API_KEY ? String(env.AIBI_LOCAL_PROVIDER_API_KEY) : null,
      baseUrl: baseUrl ?? "http://127.0.0.1",
      model,
      enabled: selectedProfileId === "local-openai" && Boolean(baseUrl),
      timeoutMs: bounded(env.AIBI_LOCAL_PROVIDER_TIMEOUT_MS, 20_000, 250, 60_000),
      maxTokens: bounded(env.AIBI_LOCAL_PROVIDER_MAX_TOKENS, 600, 128, 4_000),
      profileId: "local-openai",
      profileFingerprint: localProfileFingerprint,
      provider: "local-openai-compatible",
      structuredOutput: env.AIBI_LOCAL_PROVIDER_STRUCTURED_OUTPUT === "prompt-contract" ? "prompt-contract" : "json-object",
      contextWindow: bounded(env.AIBI_LOCAL_PROVIDER_CONTEXT_WINDOW, 32_768, 2_048, 1_000_000),
      reasoningBudget: "low",
      retries: bounded(env.AIBI_LOCAL_PROVIDER_RETRIES, 1, 0, 3),
      promptCostPerMillion: 0,
      completionCostPerMillion: 0,
      apiKeyRequired: false,
      endpointConfigured: Boolean(baseUrl),
    },
  });
  const providers = new Map<string, AgentProvider>([
    ["deterministic", deterministic],
    ["deepseek", deepseek],
    ["local-openai", local],
  ]);
  const selected = providers.get(selectedProfileId) ?? deterministic;
  return {
    schema: "aibi-agent-runtime-registry/v1" as const,
    selectedProfileId: providers.has(selectedProfileId) ? selectedProfileId : "deterministic",
    provider: selected,
    providers,
    profiles: Array.from(providers.values()).map((provider) => profileFromProvider(provider, selectedProfileId)),
    rejectedRemoteProviders: "all-unregistered-remote-providers",
    businessSemanticAuthority: "deterministic-local-bi" as const,
  };
}

export async function shadowEvaluateProviders(
  projectRoot: string,
  profileIds: string[],
  context: GroundedAgentContext,
) {
  const selectedIds = Array.from(new Set(profileIds)).filter((profileId) => ["deepseek", "local-openai"].includes(profileId));
  const runs = await Promise.all(selectedIds.map(async (profileId) => {
    const registry = agentRuntimeRegistryForProject(projectRoot, profileId);
    const shadowProvider = registry.provider;
    const status = shadowProvider.status();
    const run = status.configured ? await shadowProvider.generate(context) : null;
    return run ? { ...run, shadow: true, providerCanWrite: false, receiptMutationCount: 0, draftMutationCount: 0 } : null;
  }));
  return {
    schema: "aibi-agent-provider-shadow-evaluation/v1",
    deterministicAuthority: true,
    providerCanWrite: false,
    runs: runs.filter((run): run is NonNullable<typeof run> => run !== null),
  };
}
