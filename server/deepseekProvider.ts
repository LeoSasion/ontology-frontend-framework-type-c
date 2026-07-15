import { createHash, randomUUID } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import type {
  AgentProvider,
  AgentProviderNarrative,
  AgentProviderRun,
  AgentProviderStatus,
  AgentProviderUsage,
  GroundedAgentContext,
} from "./agentProvider";

export type DeepSeekProviderConfig = {
  apiKey: string | null;
  baseUrl: string;
  model: string;
  enabled: boolean;
  timeoutMs: number;
  maxTokens: number;
  profileId?: string;
  profileFingerprint?: string;
  provider?: string;
  structuredOutput?: "json-object" | "prompt-contract";
  contextWindow?: number;
  reasoningBudget?: "none" | "low" | "medium";
  retries?: number;
  promptCostPerMillion?: number;
  completionCostPerMillion?: number;
  apiKeyRequired?: boolean;
  endpointConfigured?: boolean;
};

type DeepSeekProviderOptions = {
  config: DeepSeekProviderConfig;
  fetchImpl?: typeof fetch;
};

const SYSTEM_PROMPT = `You are the grounded explanation layer for AIBI-C.
Return one JSON object only. Never invent numbers, fields, tables, evidence, or completed actions.
The local deterministic BI runtime is authoritative. You may explain its result, identify one missing definition, and suggest read-only next steps.
Never output SQL. Never claim data, dashboards, files, or settings were changed.
Use this JSON shape exactly:
{"summary":"string","rationale":["string"],"clarification":null,"nextActions":["string"],"citedEvidence":["string"],"certainty":"grounded"}
certainty must be either grounded or needs_clarification. If answer.blocked is true, use needs_clarification.`;

function parseEnvFile(path: string) {
  if (!existsSync(path)) return {};
  return Object.fromEntries(
    readFileSync(path, "utf8")
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter((line) => line && !line.startsWith("#") && line.includes("="))
      .map((line) => {
        const separator = line.indexOf("=");
        const key = line.slice(0, separator).trim();
        const value = line.slice(separator + 1).trim().replace(/^['"]|['"]$/g, "");
        return [key, value];
      }),
  ) as Record<string, string>;
}

function boundedInteger(value: string | undefined, fallback: number, min: number, max: number) {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  return Number.isInteger(parsed) ? Math.max(min, Math.min(max, parsed)) : fallback;
}

export function loadDeepSeekProviderConfig(projectRoot: string): DeepSeekProviderConfig {
  const localEnv = parseEnvFile(resolve(projectRoot, ".env"));
  const configuredMode = String(process.env.AIBI_AGENT_PROVIDER ?? localEnv.AIBI_AGENT_PROVIDER ?? "auto").trim().toLowerCase();
  const keyFile = process.env.DEEPSEEK_API_KEY_FILE ?? localEnv.DEEPSEEK_API_KEY_FILE;
  const fileKey = keyFile && existsSync(keyFile)
    ? readFileSync(keyFile, "utf8").split(/\r?\n/).map((line) => line.trim()).find(Boolean) ?? null
    : null;
  const apiKey = process.env.DEEPSEEK_API_KEY ?? localEnv.DEEPSEEK_API_KEY ?? fileKey ?? null;
  const requestedModel = String(process.env.DEEPSEEK_MODEL ?? localEnv.DEEPSEEK_MODEL ?? "deepseek-v4-flash").trim();
  const model = /^deepseek-[a-z0-9._-]+$/i.test(requestedModel) ? requestedModel : "deepseek-v4-flash";
  return {
    apiKey,
    baseUrl: "https://api.deepseek.com",
    model,
    enabled: configuredMode === "deepseek" || (configuredMode === "auto" && Boolean(apiKey)),
    timeoutMs: boundedInteger(process.env.DEEPSEEK_TIMEOUT_MS ?? localEnv.DEEPSEEK_TIMEOUT_MS, 20_000, 3_000, 60_000),
    maxTokens: boundedInteger(process.env.DEEPSEEK_MAX_TOKENS ?? localEnv.DEEPSEEK_MAX_TOKENS, 600, 128, 2_000),
    profileId: "deepseek",
    provider: "deepseek",
    structuredOutput: "json-object",
    contextWindow: boundedInteger(process.env.DEEPSEEK_CONTEXT_WINDOW ?? localEnv.DEEPSEEK_CONTEXT_WINDOW, 64_000, 4_096, 1_000_000),
    reasoningBudget: "low",
    retries: boundedInteger(process.env.DEEPSEEK_RETRIES ?? localEnv.DEEPSEEK_RETRIES, 1, 0, 3),
    promptCostPerMillion: Number(process.env.DEEPSEEK_PROMPT_COST_PER_MILLION ?? localEnv.DEEPSEEK_PROMPT_COST_PER_MILLION ?? 0) || 0,
    completionCostPerMillion: Number(process.env.DEEPSEEK_COMPLETION_COST_PER_MILLION ?? localEnv.DEEPSEEK_COMPLETION_COST_PER_MILLION ?? 0) || 0,
  };
}

function usageFrom(payload: Record<string, unknown>): AgentProviderUsage | null {
  const usage = payload.usage && typeof payload.usage === "object" ? payload.usage as Record<string, unknown> : null;
  if (!usage) return null;
  return {
    promptTokens: typeof usage.prompt_tokens === "number" ? usage.prompt_tokens : null,
    completionTokens: typeof usage.completion_tokens === "number" ? usage.completion_tokens : null,
    totalTokens: typeof usage.total_tokens === "number" ? usage.total_tokens : null,
  };
}

function choiceContent(payload: Record<string, unknown>) {
  const choices = Array.isArray(payload.choices) ? payload.choices : [];
  const choice = choices[0] && typeof choices[0] === "object" ? choices[0] as Record<string, unknown> : null;
  const message = choice?.message && typeof choice.message === "object" ? choice.message as Record<string, unknown> : null;
  return typeof message?.content === "string" ? message.content.trim() : "";
}

function stringArray(value: unknown, maxItems: number, maxLength: number) {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string" && Boolean(item.trim()))
      .slice(0, maxItems)
      .map((item) => item.trim().slice(0, maxLength))
    : [];
}

function parseNarrative(content: string, context: GroundedAgentContext): { narrative: AgentProviderNarrative | null; checks: Record<string, boolean> } {
  const checks: Record<string, boolean> = {
    jsonObject: false,
    exactSchema: false,
    scalarTypes: false,
    evidenceRefs: false,
    numbersGrounded: false,
    noActionClaims: false,
    noCapabilityOrFieldClaims: false,
  };
  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(content) as Record<string, unknown>;
  } catch {
    return { narrative: null, checks };
  }
  checks.jsonObject = Boolean(parsed) && typeof parsed === "object" && !Array.isArray(parsed);
  const allowedKeys = ["summary", "rationale", "clarification", "nextActions", "citedEvidence", "certainty"];
  checks.exactSchema = Object.keys(parsed).length === allowedKeys.length && Object.keys(parsed).every((key) => allowedKeys.includes(key));
  const summary = typeof parsed.summary === "string" ? parsed.summary.trim().slice(0, 600) : "";
  checks.scalarTypes = Boolean(summary)
    && Array.isArray(parsed.rationale)
    && (parsed.clarification === null || typeof parsed.clarification === "string")
    && Array.isArray(parsed.nextActions)
    && Array.isArray(parsed.citedEvidence)
    && ["grounded", "needs_clarification"].includes(String(parsed.certainty ?? ""));
  if (!checks.exactSchema || !checks.scalarTypes) return { narrative: null, checks };
  const clarification = typeof parsed.clarification === "string" && parsed.clarification.trim()
    ? parsed.clarification.trim().slice(0, 360)
    : null;
  const certainty = context.answer.blocked || parsed.certainty === "needs_clarification"
    ? "needs_clarification"
    : "grounded";
  const knownEvidence = new Set([
    "queryPlanReceipt",
    "knowledgeRule",
    ...context.queryReceipt.evidenceTypes,
  ]);
  const requestedEvidence = stringArray(parsed.citedEvidence, 6, 80);
  checks.evidenceRefs = requestedEvidence.every((item) => knownEvidence.has(item));
  const narrative: AgentProviderNarrative = {
    summary,
    rationale: stringArray(parsed.rationale, 4, 260),
    clarification,
    nextActions: stringArray(parsed.nextActions, 3, 220),
    citedEvidence: requestedEvidence,
    certainty,
  };
  const serializedContext = JSON.stringify(context);
  const groundedNumbers = new Set(serializedContext.match(/-?\d+(?:\.\d+)?/g) ?? []);
  const outputNumbers = JSON.stringify(narrative).match(/-?\d+(?:\.\d+)?/g) ?? [];
  checks.numbersGrounded = !outputNumbers.some((number) => !groundedNumbers.has(number));
  checks.noActionClaims = !/(?:已|已经)(?:执行|写入|删除|发布|导入|保存)|(?:执行|写入|删除|发布|导入|保存)(?:完成|成功)/.test(JSON.stringify(narrative));
  checks.noCapabilityOrFieldClaims = !/(?:capability|tool|sql|字段绑定|字段候选|执行器)\s*[:=]/i.test(JSON.stringify(narrative));
  return {
    narrative: Object.values(checks).every(Boolean) ? narrative : null,
    checks,
  };
}

function providerErrorCode(error: unknown) {
  if (error instanceof Error && error.name === "AbortError") return "provider_timeout";
  return "provider_network_error";
}

export function createDeepSeekProvider({ config, fetchImpl = fetch }: DeepSeekProviderOptions): AgentProvider {
  const providerName = config.provider ?? "deepseek";
  const profileId = config.profileId ?? "deepseek";
  const profileFingerprint = config.profileFingerprint ?? createHash("sha256").update(`aibi-agent-runtime-profile/v1:${profileId}`).digest("hex");
  const retries = Math.max(0, Math.min(config.retries ?? 1, 3));
  const credentialReady = config.endpointConfigured !== false && (config.apiKeyRequired === false || Boolean(config.apiKey));
  return {
    status(): AgentProviderStatus {
      return {
        profileId,
        profileFingerprint,
        provider: providerName,
        model: config.model,
        configured: credentialReady,
        enabled: config.enabled && credentialReady,
        mode: config.enabled && credentialReady ? "provider" : "deterministic",
        baseUrl: config.baseUrl,
        wireApi: "openai-chat-completions",
        structuredOutput: config.structuredOutput ?? "json-object",
        contextWindow: config.contextWindow ?? 64_000,
        reasoningBudget: config.reasoningBudget ?? "low",
        maxOutputTokens: config.maxTokens,
        retries,
        stages: ["explain", "completion-review", "shadow-evaluation"],
        outboundPolicy: "grounded-context-v1",
      };
    },

    async generate(context: GroundedAgentContext): Promise<AgentProviderRun> {
      const startedAt = Date.now();
      const runId = randomUUID();
      const requestHash = createHash("sha256").update(JSON.stringify(context)).digest("hex");
      if (!config.enabled || !credentialReady) {
        return {
          ok: false,
          provider: providerName,
          model: config.model,
          runId,
          attempts: 0,
          durationMs: Date.now() - startedAt,
          requestHash,
          usage: null,
          estimatedCostUsd: 0,
          profileId,
          profileFingerprint,
          validation: { status: "not-run", checks: {} },
          narrative: null,
          errorCode: credentialReady ? "provider_disabled" : "provider_not_configured",
        };
      }

      let lastErrorCode = "provider_failed";
      let lastUsage: AgentProviderUsage | null = null;
      let attemptsMade = 0;
      let lastValidation: AgentProviderRun["validation"] = { status: "not-run", checks: {} };
      for (let attempt = 1; attempt <= retries + 1; attempt += 1) {
        attemptsMade = attempt;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), config.timeoutMs);
        try {
          const response = await fetchImpl(`${config.baseUrl}/chat/completions`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...(config.apiKey ? { Authorization: `Bearer ${config.apiKey}` } : {}),
            },
            body: JSON.stringify({
              model: config.model,
              messages: [
                { role: "system", content: SYSTEM_PROMPT },
                { role: "user", content: `Explain this evidence context as JSON:\n${JSON.stringify(context)}` },
              ],
              ...(config.structuredOutput === "prompt-contract" ? {} : { response_format: { type: "json_object" } }),
              temperature: 0.1,
              max_tokens: config.maxTokens,
              stream: false,
            }),
            signal: controller.signal,
          });
          const payload = await response.json().catch(() => ({})) as Record<string, unknown>;
          lastUsage = usageFrom(payload);
          const content = choiceContent(payload);
          const parsedNarrative = response.ok && content ? parseNarrative(content, context) : { narrative: null, checks: {} };
          lastValidation = content
            ? { status: parsedNarrative.narrative ? "passed" : "failed", checks: parsedNarrative.checks }
            : { status: "not-run", checks: {} };
          if (response.ok && parsedNarrative.narrative) {
            const promptTokens = lastUsage?.promptTokens ?? 0;
            const completionTokens = lastUsage?.completionTokens ?? 0;
            const estimatedCostUsd = (promptTokens * (config.promptCostPerMillion ?? 0) + completionTokens * (config.completionCostPerMillion ?? 0)) / 1_000_000;
            return {
              ok: true,
              provider: providerName,
              model: config.model,
              runId,
              attempts: attempt,
              durationMs: Date.now() - startedAt,
              requestHash,
              usage: lastUsage,
              estimatedCostUsd,
              profileId,
              profileFingerprint,
              validation: lastValidation,
              narrative: parsedNarrative.narrative,
              errorCode: null,
            };
          }
          lastErrorCode = response.ok
            ? content ? "provider_invalid_grounding" : "provider_empty_response"
            : `provider_http_${response.status}`;
          const retryable = response.ok || response.status === 429 || response.status >= 500;
          if (!retryable) break;
        } catch (error) {
          lastErrorCode = providerErrorCode(error);
        } finally {
          clearTimeout(timeout);
        }
      }
      return {
        ok: false,
        provider: providerName,
        model: config.model,
        runId,
        attempts: attemptsMade,
        durationMs: Date.now() - startedAt,
        requestHash,
        usage: lastUsage,
        estimatedCostUsd: 0,
        profileId,
        profileFingerprint,
        validation: lastValidation,
        narrative: null,
        errorCode: lastErrorCode,
      };
    },
  };
}

export function deepSeekProviderForProject(projectRoot: string, fetchImpl?: typeof fetch) {
  return createDeepSeekProvider({ config: loadDeepSeekProviderConfig(projectRoot), fetchImpl });
}
