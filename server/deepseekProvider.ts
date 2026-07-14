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
  baseUrl: "https://api.deepseek.com";
  model: string;
  enabled: boolean;
  timeoutMs: number;
  maxTokens: number;
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

function parseNarrative(content: string, context: GroundedAgentContext): AgentProviderNarrative | null {
  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(content) as Record<string, unknown>;
  } catch {
    return null;
  }
  const summary = typeof parsed.summary === "string" ? parsed.summary.trim().slice(0, 600) : "";
  if (!summary) return null;
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
  const narrative: AgentProviderNarrative = {
    summary,
    rationale: stringArray(parsed.rationale, 4, 260),
    clarification,
    nextActions: stringArray(parsed.nextActions, 3, 220),
    citedEvidence: stringArray(parsed.citedEvidence, 6, 80).filter((item) => knownEvidence.has(item)),
    certainty,
  };
  const serializedContext = JSON.stringify(context);
  const groundedNumbers = new Set(serializedContext.match(/-?\d+(?:\.\d+)?/g) ?? []);
  const outputNumbers = JSON.stringify(narrative).match(/-?\d+(?:\.\d+)?/g) ?? [];
  if (outputNumbers.some((number) => !groundedNumbers.has(number))) return null;
  if (/(?:已|已经)(?:执行|写入|删除|发布|导入|保存)|(?:执行|写入|删除|发布|导入|保存)(?:完成|成功)/.test(JSON.stringify(narrative))) return null;
  return narrative;
}

function providerErrorCode(error: unknown) {
  if (error instanceof Error && error.name === "AbortError") return "provider_timeout";
  return "provider_network_error";
}

export function createDeepSeekProvider({ config, fetchImpl = fetch }: DeepSeekProviderOptions): AgentProvider {
  return {
    status(): AgentProviderStatus {
      return {
        provider: "deepseek",
        model: config.model,
        configured: Boolean(config.apiKey),
        enabled: config.enabled && Boolean(config.apiKey),
        mode: config.enabled && config.apiKey ? "provider" : "deterministic",
        baseUrl: config.baseUrl,
      };
    },

    async generate(context: GroundedAgentContext): Promise<AgentProviderRun> {
      const startedAt = Date.now();
      const runId = randomUUID();
      const requestHash = createHash("sha256").update(JSON.stringify(context)).digest("hex");
      if (!config.enabled || !config.apiKey) {
        return {
          ok: false,
          provider: "deepseek",
          model: config.model,
          runId,
          attempts: 0,
          durationMs: Date.now() - startedAt,
          requestHash,
          usage: null,
          narrative: null,
          errorCode: config.apiKey ? "provider_disabled" : "provider_not_configured",
        };
      }

      let lastErrorCode = "provider_failed";
      let lastUsage: AgentProviderUsage | null = null;
      let attemptsMade = 0;
      for (let attempt = 1; attempt <= 2; attempt += 1) {
        attemptsMade = attempt;
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), config.timeoutMs);
        try {
          const response = await fetchImpl(`${config.baseUrl}/chat/completions`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${config.apiKey}`,
            },
            body: JSON.stringify({
              model: config.model,
              messages: [
                { role: "system", content: SYSTEM_PROMPT },
                { role: "user", content: `Explain this evidence context as JSON:\n${JSON.stringify(context)}` },
              ],
              response_format: { type: "json_object" },
              temperature: 0.1,
              max_tokens: config.maxTokens,
              stream: false,
            }),
            signal: controller.signal,
          });
          const payload = await response.json().catch(() => ({})) as Record<string, unknown>;
          lastUsage = usageFrom(payload);
          const content = choiceContent(payload);
          const narrative = response.ok && content ? parseNarrative(content, context) : null;
          if (response.ok && narrative) {
            return {
              ok: true,
              provider: "deepseek",
              model: config.model,
              runId,
              attempts: attempt,
              durationMs: Date.now() - startedAt,
              requestHash,
              usage: lastUsage,
              narrative,
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
        provider: "deepseek",
        model: config.model,
        runId,
        attempts: attemptsMade,
        durationMs: Date.now() - startedAt,
        requestHash,
        usage: lastUsage,
        narrative: null,
        errorCode: lastErrorCode,
      };
    },
  };
}

export function deepSeekProviderForProject(projectRoot: string, fetchImpl?: typeof fetch) {
  return createDeepSeekProvider({ config: loadDeepSeekProviderConfig(projectRoot), fetchImpl });
}
