import { fetchJson } from "./apiClient";
import type { ThemePaletteConfig, UserPreferencesConfig } from "./types";

export function savePreferences(options: {
  preferences: Partial<UserPreferencesConfig>;
  confirm?: boolean;
}) {
  return fetchJson<Record<string, unknown>>("/api/preferences", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function saveThemePalette(options: {
  action?: "save" | "upsert" | "delete";
  theme?: Partial<ThemePaletteConfig>;
  themeKey?: string;
  confirm?: boolean;
}) {
  return fetchJson<Record<string, unknown>>("/api/theme-palettes", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function validateConfig() {
  return fetchJson<Record<string, unknown>>("/api/config/validate", { ok: false });
}

export function exportConfig(options: { output?: string } = {}) {
  return fetchJson<Record<string, unknown>>("/api/config/export", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}

export function applyConfig(options: { input: string; confirm?: boolean }) {
  return fetchJson<Record<string, unknown>>("/api/config/apply", { ok: false }, {
    method: "POST",
    body: JSON.stringify(options),
  });
}
