import type { UserPreferencesConfig } from "../types";
import { Bilingual } from "./Bilingual";
import { Icon } from "./Icons";

const settingsSandboxItems = [
  {
    key: "source-readonly",
    tone: "ok",
    icon: "lock",
    labelZh: "外部源目录只读",
    labelEn: "External source folders are read-only",
    detailZh: "当前项目只吸收可验证能力，不会改动原始 AIBI 或财务报表目录。",
    detailEn: "This workspace can reference and copy selected code, but it does not mutate the original AIBI or finance-report folders.",
  },
  {
    key: "data-excluded",
    tone: "ok",
    icon: "source",
    labelZh: "业务数据不导出",
    labelEn: "Business data is excluded from exports",
    detailZh: "配置备份只覆盖偏好、主题、字段、指标、关系和看板定义，不携带真实源表和本地库。",
    detailEn: "Config backups include preferences, themes, fields, metrics, relationships, and dashboards, not source files or local databases.",
  },
  {
    key: "write-confirm",
    tone: "warn",
    icon: "check",
    labelZh: "写入先预演，再确认",
    labelEn: "Preview writes before confirmation",
    detailZh: "导入、覆盖、恢复配置、删除和 Agent 待确认修改都必须预演或显式确认后才执行。",
    detailEn: "Imports, overwrites, config restores, deletes, and Agent pending changes require preview or explicit confirmation.",
  },
  {
    key: "manual-assets",
    tone: "warn",
    icon: "settings",
    labelZh: "手动资产默认受保护",
    labelEn: "Manual assets stay protected by default",
    detailZh: "只有打开高权限开关时，Agent 才能管理人工创建的仪表盘、视图和配置。",
    detailEn: "Agent can manage manually created dashboards, views, and config only when the high-trust switch is enabled.",
  },
] as const;

type SettingsSandboxBoundaryPanelProps = {
  busyKey: string | null;
  draftPreferences: UserPreferencesConfig;
  onExportConfig: () => Promise<Record<string, unknown>>;
  onRunConfigAction: (key: string, action: () => Promise<Record<string, unknown>>) => Promise<void>;
  onValidateConfig: () => Promise<Record<string, unknown>>;
};

export function SettingsSandboxBoundaryPanel({
  busyKey,
  draftPreferences,
  onExportConfig,
  onRunConfigAction,
  onValidateConfig,
}: SettingsSandboxBoundaryPanelProps) {
  return (
    <section className="settingsCard settingsSandboxCard" aria-labelledby="settings-sandbox-title" data-testid="settings-sandbox-boundary">
      <div className="settingsCardHeader">
        <div>
          <span className="eyebrow"><Bilingual zh="工作区沙箱" en="Workspace sandbox" /></span>
          <h3 id="settings-sandbox-title"><Bilingual zh="数据和写入边界" en="Data and write boundaries" /></h3>
        </div>
        <span className={draftPreferences.agentCanManageManualAssets ? "settingsSandboxBadge warn" : "settingsSandboxBadge"}>
          <Bilingual
            zh={draftPreferences.agentCanManageManualAssets ? "手动资产已授权" : "手动资产受保护"}
            en={draftPreferences.agentCanManageManualAssets ? "Manual assets authorized" : "Manual assets protected"}
          />
        </span>
      </div>
      <p className="settingsSandboxLead">
        <Bilingual
          zh="用户可以放心导入、预览和让 Agent 起草方案；真正覆盖配置或删除资产仍需要明确确认。"
          en="Users can import, preview, and let Agent prepare changes safely; destructive or overwriting actions still require explicit confirmation."
        />
      </p>
      <div className="settingsSandboxGrid" data-testid="settings-sandbox-grid">
        {settingsSandboxItems.map((item) => (
          <article className={`settingsSandboxItem ${item.tone}`} data-testid={`settings-sandbox-${item.key}`} key={item.key}>
            <span className="settingsSandboxIcon"><Icon name={item.icon} /></span>
            <div>
              <strong><Bilingual zh={item.labelZh} en={item.labelEn} /></strong>
              <small><Bilingual zh={item.detailZh} en={item.detailEn} /></small>
            </div>
          </article>
        ))}
      </div>
      <div className="settingsSandboxActions">
        <button className="secondaryButton" disabled={busyKey === "validate-config"} onClick={() => onRunConfigAction("validate-config", onValidateConfig)} type="button">
          <Icon name="check" />
          <span><Bilingual zh="立即校验边界" en="Validate boundaries" /></span>
        </button>
        <button className="secondaryButton" disabled={busyKey === "export-config"} onClick={() => onRunConfigAction("export-config", onExportConfig)} type="button">
          <Icon name="copy" />
          <span><Bilingual zh="导出安全配置" en="Export safe config" /></span>
        </button>
      </div>
    </section>
  );
}
