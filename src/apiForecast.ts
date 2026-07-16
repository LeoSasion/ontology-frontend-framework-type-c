import { fetchJson } from "./apiClient";
import type { ForecastReadiness } from "./types";

export type ForecastReadinessPayload = {
  ok: boolean;
  readyForEvaluation?: boolean;
  forecastReadiness?: ForecastReadiness;
  error?: string;
};

export function getForecastReadiness(unitKey: string, horizon: number) {
  const query = new URLSearchParams({ unit: unitKey, horizon: String(horizon) });
  return fetchJson<ForecastReadinessPayload>(`/api/forecast-readiness?${query}`, {
    ok: false,
    error: "Local forecast readiness service is unavailable",
  });
}
