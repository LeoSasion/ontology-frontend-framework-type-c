import "./settingsPanel.css";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { getUserPreferences, makeThemeCopy, resolveThemePalette } from "../theme";
import type { ThemePaletteConfig, UserPreferencesConfig, WorkbenchPayload, WorkspaceStatus } from "../types";
import { Bilingual } from "./Bilingual";
import { SettingsConfigPortabilityPanel } from "./SettingsConfigPortabilityPanel";
import { SettingsSandboxBoundaryPanel } from "./SettingsSandboxBoundaryPanel";
import { SettingsThemePreferencePanel, ThemeSwatches } from "./SettingsThemePreferencePanel";

const TrustContextSettingsPanel = lazy(() => import("./TrustContextSettingsPanel"));
const SettingsDomainPackPanel = lazy(() => import("./SettingsDomainPackPanel").then((module) => ({ default: module.SettingsDomainPackPanel })));

type SettingsPanelProps = {
  workbench: WorkbenchPayload;
  status: WorkspaceStatus;
  onSavePreferences: (options: { preferences: Partial<UserPreferencesConfig>; confirm?: boolean }) => Promise<void>;
  onSaveThemePalette: (options: { action?: "save" | "upsert" | "delete"; theme?: Partial<ThemePaletteConfig>; themeKey?: string; confirm?: boolean }) => Promise<void>;
  onValidateConfig: () => Promise<Record<string, unknown>>;
  onExportConfig: () => Promise<Record<string, unknown>>;
  onApplyConfig: (options: { input: string; confirm?: boolean }) => Promise<Record<string, unknown>>;
  onSetDomainPack: (options: { packId: string; state: "enabled" | "disabled"; workspaceId?: string; confirm?: boolean }) => Promise<Record<string, unknown>>;
};

export function SettingsPanel({ workbench, status, onSavePreferences, onSaveThemePalette, onValidateConfig, onExportConfig, onApplyConfig, onSetDomainPack }: SettingsPanelProps) {
  const preferences = useMemo(() => getUserPreferences(workbench), [workbench]);
  const palettes = useMemo(() => Array.isArray(workbench.themePalettes) ? workbench.themePalettes.filter((theme) => theme.enabled) : [], [workbench.themePalettes]);
  const activeTheme = useMemo(() => resolveThemePalette(workbench, preferences), [preferences, workbench]);
  const [draftPreferences, setDraftPreferences] = useState<UserPreferencesConfig>(preferences);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [configInput, setConfigInput] = useState("");
  const [configResult, setConfigResult] = useState<Record<string, unknown> | null>(null);
  const [domainPackResult, setDomainPackResult] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    setDraftPreferences(preferences);
  }, [preferences]);

  const preferenceChanged = useMemo(
    () => draftPreferences.requireDeleteNameConfirmation !== preferences.requireDeleteNameConfirmation ||
      draftPreferences.autoSaveDashboardOnSwitch !== preferences.autoSaveDashboardOnSwitch ||
      draftPreferences.agentCanManageGeneratedAssets !== preferences.agentCanManageGeneratedAssets ||
      draftPreferences.agentCanManageManualAssets !== preferences.agentCanManageManualAssets,
    [draftPreferences, preferences],
  );

  async function savePreferenceDraft() {
    setBusyKey("preferences");
    try {
      await onSavePreferences({ preferences: draftPreferences, confirm: true });
    } finally {
      setBusyKey(null);
    }
  }

  async function applyTheme(themeKey: string) {
    setBusyKey(`theme-${themeKey}`);
    try {
      await onSavePreferences({ preferences: { themeKey }, confirm: true });
    } finally {
      setBusyKey(null);
    }
  }

  async function copyTheme(theme: ThemePaletteConfig) {
    const copied = makeThemeCopy(theme, "custom");
    setBusyKey(`copy-${theme.themeKey}`);
    try {
      await onSaveThemePalette({ action: "save", theme: copied, confirm: true });
      await onSavePreferences({ preferences: { themeKey: copied.themeKey }, confirm: true });
    } finally {
      setBusyKey(null);
    }
  }

  async function deleteTheme(theme: ThemePaletteConfig) {
    setBusyKey(`delete-${theme.themeKey}`);
    try {
      await onSaveThemePalette({ action: "delete", themeKey: theme.themeKey, confirm: true });
      if (preferences.themeKey === theme.themeKey) {
        await onSavePreferences({ preferences: { themeKey: "L1" }, confirm: true });
      }
    } finally {
      setBusyKey(null);
    }
  }

  async function runConfigAction(key: string, action: () => Promise<Record<string, unknown>>) {
    setBusyKey(key);
    try {
      setConfigResult(await action());
    } finally {
      setBusyKey(null);
    }
  }

  async function setDomainPackState(options: { packId: string; state: "enabled" | "disabled"; workspaceId?: string; confirm?: boolean }) {
    const key = `domain-pack-${options.packId}-${options.state}`;
    setBusyKey(key);
    try {
      setDomainPackResult(await onSetDomainPack(options));
    } finally {
      setBusyKey(null);
    }
  }

  return (
    <section className="mainPanel settingsPanel" aria-labelledby="settings-title">
      <div className="settingsHeader">
        <div>
          <p className="kicker"><Bilingual zh="工作台偏好" en="Workbench preferences" /></p>
          <h2 id="settings-title"><Bilingual zh="工作区设置" en="Workspace settings" /></h2>
          <p>
            <Bilingual
              zh="这里管理外观、写入保护和 Agent 权限。Agent 仍只通过待确认修改和显式确认写入。"
              en="Manage appearance, write protection, and Agent permissions here. Agent still writes only through pending changes and explicit confirmation."
            />
          </p>
        </div>
        <div className="activeThemeBadge">
          <ThemeSwatches theme={activeTheme} />
          <strong>{activeTheme.name}</strong>
          <span>{activeTheme.mode}</span>
        </div>
      </div>

      <div className="settingsGrid">
        <SettingsThemePreferencePanel
          busyKey={busyKey}
          draftPreferences={draftPreferences}
          onApplyTheme={applyTheme}
          onCopyTheme={copyTheme}
          onDeleteTheme={deleteTheme}
          onPreferenceToggle={(key, checked) => setDraftPreferences((current) => ({ ...current, [key]: checked }))}
          onSavePreferenceDraft={savePreferenceDraft}
          palettes={palettes}
          preferenceChanged={preferenceChanged}
          preferences={preferences}
        />

        <Suspense fallback={<div className="settingsLoading"><Bilingual zh="正在加载领域包设置…" en="Loading domain pack settings…" /></div>}>
          <SettingsDomainPackPanel
            busyKey={busyKey}
            onSetDomainPack={setDomainPackState}
            result={domainPackResult}
            runtime={status.domainPacks}
          />
        </Suspense>

        <details className="progressiveDetails settingsProgressiveDetails" data-testid="settings-sandbox-details">
          <summary><Bilingual zh="写入保护和沙盒边界" en="Write protection and sandbox boundaries" /></summary>
          <div className="progressiveDetailsBody single">
            <SettingsSandboxBoundaryPanel
              busyKey={busyKey}
              draftPreferences={draftPreferences}
              onExportConfig={onExportConfig}
              onRunConfigAction={runConfigAction}
              onValidateConfig={onValidateConfig}
            />
          </div>
        </details>

        <details className="progressiveDetails settingsProgressiveDetails" data-testid="settings-trust-context-details">
          <summary><Bilingual zh="业务术语、规则和确认问法" en="Business terms, rules, and confirmed queries" /></summary>
          <div className="progressiveDetailsBody single">
            <Suspense fallback={null}><TrustContextSettingsPanel /></Suspense>
          </div>
        </details>

        <details className="progressiveDetails settingsProgressiveDetails" data-testid="settings-config-portability-details">
          <summary><Bilingual zh="配置导入、导出和迁移" en="Config import, export, and migration" /></summary>
          <div className="progressiveDetailsBody single">
            <SettingsConfigPortabilityPanel
              busyKey={busyKey}
              configInput={configInput}
              configResult={configResult}
              onApplyConfig={onApplyConfig}
              onConfigInputChange={setConfigInput}
              onExportConfig={onExportConfig}
              onRunConfigAction={runConfigAction}
              onValidateConfig={onValidateConfig}
            />
          </div>
        </details>
      </div>
    </section>
  );
}
