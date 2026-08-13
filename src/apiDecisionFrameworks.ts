import { fetchJson } from "./apiClient";
import type {
  DecisionClaim,
  DecisionFrameworkPayload,
  DecisionFrameworkType,
} from "./typesDecisionFramework";

const unavailable = { ok: false, error: "Local decision framework service is unavailable" } satisfies DecisionFrameworkPayload;

export function getDecisionFrameworks(unitKey: string, signal?: AbortSignal) {
  const query = new URLSearchParams({ unit: unitKey, limit: "30" });
  return fetchJson<DecisionFrameworkPayload>(`/api/decision-frameworks?${query}`, unavailable, { signal });
}

export function getDecisionFramework(frameworkKey: string, signal?: AbortSignal) {
  return fetchJson<DecisionFrameworkPayload>(
    `/api/decision-frameworks/${encodeURIComponent(frameworkKey)}`,
    unavailable,
    { signal },
  );
}

export function createDecisionFramework(input: {
  unitKey: string;
  type: DecisionFrameworkType;
  title: string;
  requestKey: string;
}) {
  return fetchJson<DecisionFrameworkPayload>("/api/decision-frameworks/create", unavailable, {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export function saveDecisionFramework(input: {
  frameworkKey: string;
  title: string;
  claims: DecisionClaim[];
  expectedContentFingerprint: string;
}) {
  return fetchJson<DecisionFrameworkPayload>(
    `/api/decision-frameworks/${encodeURIComponent(input.frameworkKey)}`,
    unavailable,
    {
      method: "PUT",
      body: JSON.stringify({
        title: input.title,
        claims: input.claims,
        expectedContentFingerprint: input.expectedContentFingerprint,
      }),
    },
  );
}

export function publishDecisionFramework(input: {
  frameworkKey: string;
  confirm?: boolean;
  expectedPlanFingerprint?: string;
}) {
  return fetchJson<DecisionFrameworkPayload>(
    `/api/decision-frameworks/${encodeURIComponent(input.frameworkKey)}/publish`,
    unavailable,
    {
      method: "POST",
      body: JSON.stringify({
        confirm: input.confirm === true,
        expectedPlanFingerprint: input.expectedPlanFingerprint,
      }),
    },
  );
}

export function exportDecisionFramework(frameworkKey: string) {
  return fetchJson<DecisionFrameworkPayload>(
    `/api/decision-frameworks/${encodeURIComponent(frameworkKey)}/export`,
    unavailable,
  );
}
