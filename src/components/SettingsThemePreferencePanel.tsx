import type { ThemePaletteConfig, UserPreferencesConfig } from "../types";
import { themeIsSystem } from "../theme";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";

type PreferenceKey = keyof Pick<
  UserPreferencesConfig,
  "requireDeleteNameConfirmation" | "autoSaveDashboardOnSwitch" | "agentCanManageGeneratedAssets" | "agentCanManageManualAssets"
>;

const preferenceRows: Array<{ key: PreferenceKey; zh: string; en: string; helpZh: string; helpEn: string }> = [
  {
    key: "requireDeleteNameConfirmation",
    zh: "删除前要求输入名称",
    en: "Require name before delete",
    helpZh: "删除数据源、仪表盘等高风险资产时保留二次确认。",
    helpEn: "Keep an extra confirmation for deleting sources, dashboards, and other risky assets.",
  },
  {
    key: "autoSaveDashboardOnSwitch",
    zh: "切换看板时自动保存",
    en: "Auto-save when switching dashboards",
    helpZh: "适合连续编辑；默认关闭，避免误保存。",
    helpEn: "Useful during editing; off by default to avoid accidental saves.",
  },
  {
    key: "agentCanManageGeneratedAssets",
    zh: "允许 Agent 管理自己生成的资产",
    en: "Let Agent manage generated assets",
    helpZh: "Agent 可更新它创建的待确认修改、视图和看板组件。",
    helpEn: "Agent may update pending changes, views, and widgets it created.",
  },
  {
    key: "agentCanManageManualAssets",
    zh: "允许 Agent 管理手动资产",
    en: "Let Agent manage manual assets",
    helpZh: "高权限开关；建议只在明确授权时打开。",
    helpEn: "High-trust switch; enable only when explicitly intended.",
  },
];

type SettingsThemePreferencePanelProps = {
  busyKey: string | null;
  draftPreferences: UserPreferencesConfig;
  onApplyTheme: (themeKey: string) => void;
  onCopyTheme: (theme: ThemePaletteConfig) => void;
  onDeleteTheme: (theme: ThemePaletteConfig) => void;
  onPreferenceToggle: (key: PreferenceKey, checked: boolean) => void;
  onSavePreferenceDraft: () => void;
  palettes: ThemePaletteConfig[];
  preferenceChanged: boolean;
  preferences: UserPreferencesConfig;
};

export function ThemeSwatches({ theme }: { theme: ThemePaletteConfig }) {
  const tokens = theme.tokens ?? {};
  const colors = [tokens.primary, tokens.selected, tokens.bg, tokens.surface, tokens.panel].filter(Boolean);
  return (
    <span className="themeSwatches" aria-hidden="true">
      {colors.map((color, index) => (
        <span key={`${theme.themeKey}-${color}-${index}`} style={{ background: color }} />
      ))}
    </span>
  );
}

export function SettingsThemePreferencePanel({
  busyKey,
  draftPreferences,
  onApplyTheme,
  onCopyTheme,
  onDeleteTheme,
  onPreferenceToggle,
  onSavePreferenceDraft,
  palettes,
  preferenceChanged,
  preferences,
}: SettingsThemePreferencePanelProps) {
  return (
    <>
      <section className="settingsCard themeSettingsCard" aria-labelledby="theme-settings-title" data-testid="settings-theme-palette-panel">
        <div className="settingsCardHeader">
          <div>
            <span className="eyebrow"><Bilingual zh="外观" en="Appearance" /></span>
            <h3 id="theme-settings-title"><Bilingual zh="主题调色板" en="Theme palettes" /></h3>
          </div>
          <span className="settingsHint"><Bilingual zh={`${palettes.length} 套`} en={`${palettes.length} palettes`} /></span>
        </div>
        <div className="themePaletteGrid">
          {palettes.map((theme) => {
            const active = theme.themeKey === preferences.themeKey;
            return (
              <article className={active ? "themePaletteCard active" : "themePaletteCard"} key={theme.themeKey}>
                <div className="themePaletteTop">
                  <ThemeSwatches theme={theme} />
                  <span>{theme.themeKey}</span>
                </div>
                <strong>{theme.name}</strong>
                <small>{theme.mode === "dark" ? biText("深色", "Dark") : biText("浅色", "Light")} · {theme.createdBy === "system" ? biText("系统", "System") : biText("自定义", "Custom")}</small>
                <div className="settingsActions">
                  <button disabled={active || busyKey === `theme-${theme.themeKey}`} onClick={() => onApplyTheme(theme.themeKey)} type="button">
                    <Icon name={active ? "check" : "settings"} />
                    <span>{active ? biText("已应用", "Active") : biText("应用", "Apply")}</span>
                  </button>
                  <button disabled={busyKey === `copy-${theme.themeKey}`} onClick={() => onCopyTheme(theme)} type="button">
                    <Icon name="copy" />
                    <span><Bilingual zh="复制" en="Copy" /></span>
                  </button>
                  {!themeIsSystem(theme) ? (
                    <button className="dangerButton" disabled={busyKey === `delete-${theme.themeKey}`} onClick={() => onDeleteTheme(theme)} type="button">
                      <Icon name="lock" />
                      <span><Bilingual zh="删除" en="Delete" /></span>
                    </button>
                  ) : null}
                </div>
              </article>
            );
          })}
        </div>
      </section>

      <section className="settingsCard" aria-labelledby="preference-settings-title" data-testid="settings-preference-switch-panel">
        <div className="settingsCardHeader">
          <div>
            <span className="eyebrow"><Bilingual zh="安全偏好" en="Safety preferences" /></span>
            <h3 id="preference-settings-title"><Bilingual zh="写入和 Agent 权限" en="Writes and Agent permissions" /></h3>
          </div>
          <button className="primaryButton" disabled={!preferenceChanged || busyKey === "preferences"} onClick={onSavePreferenceDraft} type="button">
            <Icon name="check" />
            <span><Bilingual zh="保存开关" en="Save switches" /></span>
          </button>
        </div>
        <div className="preferenceList">
          {preferenceRows.map((row) => (
            <label className="preferenceRow" key={row.key}>
              <span>
                <strong><Bilingual zh={row.zh} en={row.en} /></strong>
                <small><Bilingual zh={row.helpZh} en={row.helpEn} /></small>
              </span>
              <input
                checked={draftPreferences[row.key]}
                onChange={(event) => onPreferenceToggle(row.key, event.target.checked)}
                type="checkbox"
              />
            </label>
          ))}
        </div>
      </section>
    </>
  );
}
