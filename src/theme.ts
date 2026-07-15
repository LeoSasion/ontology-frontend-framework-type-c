import { defaultThemePalettes, defaultUserPreferences } from "./defaultThemeData";
import type { ThemePaletteConfig, UserPreferencesConfig, WorkbenchPayload } from "./types";

export const DEFAULT_USER_PREFERENCES: UserPreferencesConfig = defaultUserPreferences;
const themeSnapshotStorageKey = "aibiHybrid.themeSnapshot";

const cssTokenMap: Record<string, string[]> = {
  bg: ["--bg", "--bi-bg"],
  surface: ["--surface", "--bi-surface"],
  panel: ["--surface-2", "--bi-panel"],
  border: ["--line", "--bi-border", "--bi-border-soft"],
  text: ["--text", "--bi-text"],
  muted: ["--muted", "--soft", "--bi-muted"],
  primary: ["--accent", "--bi-accent"],
  primaryHover: ["--accent-strong", "--bi-accent-strong"],
  selected: ["--accent-soft", "--bi-accent-tint"],
  soft: ["--bi-accent-soft"],
  railTop: ["--bi-rail-top"],
  railMid: ["--bi-rail-mid"],
  railBottom: ["--bi-rail-bottom"],
  railActive: ["--bi-rail-active"],
};

function hexToRgb(hex: string | undefined) {
  const normalized = hex?.trim().replace(/^#/, "");
  if (!normalized) return null;
  const value = normalized.length === 3
    ? normalized.split("").map((part) => part + part).join("")
    : normalized;
  if (!/^[0-9a-f]{6}$/i.test(value)) return null;
  const parsed = Number.parseInt(value, 16);
  return {
    r: (parsed >> 16) & 255,
    g: (parsed >> 8) & 255,
    b: parsed & 255,
  };
}

function relativeLuminance(color: { r: number; g: number; b: number }) {
  const channel = (value: number) => {
    const normalized = value / 255;
    return normalized <= 0.03928
      ? normalized / 12.92
      : Math.pow((normalized + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * channel(color.r) + 0.7152 * channel(color.g) + 0.0722 * channel(color.b);
}

export function getUserPreferences(workbench: WorkbenchPayload): UserPreferencesConfig {
  return {
    ...DEFAULT_USER_PREFERENCES,
    ...(workbench.preferences ?? {}),
  };
}

export function resolveThemePalette(
  workbench: WorkbenchPayload,
  preferences = getUserPreferences(workbench),
): ThemePaletteConfig {
  const palettes = Array.isArray(workbench.themePalettes) && workbench.themePalettes.length
    ? workbench.themePalettes
    : defaultThemePalettes;
  return palettes.find((palette) => palette.themeKey === preferences.themeKey && palette.enabled)
    ?? palettes.find((palette) => palette.themeKey === DEFAULT_USER_PREFERENCES.themeKey)
    ?? palettes[0];
}

export function hasStoredThemeSnapshot() {
  if (typeof window === "undefined") return false;
  try {
    return Boolean(window.localStorage.getItem(themeSnapshotStorageKey));
  } catch {
    return false;
  }
}

export function applyThemePalette(theme: ThemePaletteConfig | undefined) {
  if (!theme || typeof document === "undefined") {
    return;
  }
  const root = document.documentElement;
  root.dataset.themeKey = theme.themeKey;
  root.dataset.themeMode = theme.mode;
  root.style.colorScheme = theme.mode === "dark" ? "dark" : "light";
  for (const [token, value] of Object.entries(theme.tokens ?? {})) {
    const variables = cssTokenMap[token] ?? [`--bi-theme-${token}`];
    for (const variable of variables) {
      root.style.setProperty(variable, value);
    }
  }
  const primary = hexToRgb(theme.tokens?.primaryHover ?? theme.tokens?.primary);
  const onAccent = primary && relativeLuminance(primary) > 0.48 ? "#062b33" : "#ffffff";
  const borderToken = theme.tokens?.border ?? "#d7e0ec";
  const textToken = theme.tokens?.text ?? "#172033";
  const strongBorder = `color-mix(in srgb, ${borderToken} 72%, ${textToken} 28%)`;
  root.style.setProperty("--on-accent", onAccent);
  root.style.setProperty("--bi-on-accent", onAccent);
  root.style.setProperty("--line-strong", strongBorder);
  root.style.setProperty("--bi-border-strong", strongBorder);
  root.style.setProperty("--border", borderToken);
  root.style.setProperty("--border-soft", `color-mix(in srgb, ${borderToken} 74%, transparent)`);
  root.style.setProperty("--text-muted", theme.tokens?.muted ?? "#5f6b7b");
  root.style.setProperty("--ink-muted", theme.tokens?.muted ?? "#5f6b7b");
  const activeRail = hexToRgb(theme.tokens?.railActive);
  const activeRailText = activeRail && relativeLuminance(activeRail) < 0.45
    ? "#ffffff"
    : theme.tokens?.primaryHover ?? theme.tokens?.primary ?? "#116A82";
  const railSurface = hexToRgb(theme.tokens?.railMid) ?? hexToRgb(theme.tokens?.railTop) ?? hexToRgb(theme.tokens?.railBottom);
  const mutedToken = theme.tokens?.muted ?? "#5f6b7b";
  const railMuted = railSurface && relativeLuminance(railSurface) < 0.45
    ? `color-mix(in srgb, #ffffff 78%, ${theme.tokens?.railMid ?? theme.tokens?.railTop ?? "#0f2d37"})`
    : `color-mix(in srgb, ${mutedToken} 58%, ${textToken})`;
  root.style.setProperty("--bi-rail-active-text", activeRailText);
  root.style.setProperty("--bi-rail-muted", railMuted);
  if (typeof window !== "undefined") {
    try {
      window.localStorage.setItem(themeSnapshotStorageKey, JSON.stringify({
        themeKey: theme.themeKey,
        mode: theme.mode,
        tokens: theme.tokens ?? {},
        onAccent,
        strongBorder,
        railActiveText: activeRailText,
        railMuted,
      }));
    } catch {
      // Theme still applies even when storage is blocked.
    }
  }
}

export function themeIsSystem(theme: ThemePaletteConfig | undefined) {
  return theme?.createdBy === "system";
}

export function makeThemeCopy(theme: ThemePaletteConfig, suffix = "copy"): ThemePaletteConfig {
  const key = `${theme.themeKey.toLowerCase()}_${suffix}_${Date.now().toString(36)}`;
  return {
    ...theme,
    themeKey: key,
    name: `${theme.name} copy`,
    createdBy: "user",
    sortOrder: (theme.sortOrder ?? 100) + 1,
    tokens: { ...(theme.tokens ?? {}) },
  };
}
