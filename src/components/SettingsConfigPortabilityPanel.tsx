import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";

const configMigrationSteps = [
  {
    key: "validate",
    tone: "ok",
    labelZh: "先校验",
    labelEn: "Validate first",
    detailZh: "检查当前工作区配置引用，发现错误时不要恢复。",
    detailEn: "Check current workspace references; do not restore when errors exist.",
  },
  {
    key: "export",
    tone: "ok",
    labelZh: "再导出",
    labelEn: "Export next",
    detailZh: "只导出元数据配置，不包含业务表行、本地库或凭据。",
    detailEn: "Export metadata only, excluding business rows, local databases, and secrets.",
  },
  {
    key: "dry-run",
    tone: "warn",
    labelZh: "恢复前预览",
    labelEn: "Preview restore",
    detailZh: "恢复 JSON 先生成计划，确认前不覆盖当前工作区。",
    detailEn: "Restore JSON creates a plan first; nothing overwrites before confirmation.",
  },
  {
    key: "confirm",
    tone: "warn",
    labelZh: "最后确认覆盖",
    labelEn: "Confirm overwrite last",
    detailZh: "只有确认后才应用配置，并保留本地备份和校验结果。",
    detailEn: "Apply config only after confirmation, with local backup and validation result.",
  },
] as const;

const configMigrationScopes = [
  { zh: "偏好", en: "preferences" },
  { zh: "主题", en: "themes" },
  { zh: "字段/指标/公式", en: "fields/metrics/formulas" },
  { zh: "关系", en: "relationships" },
  { zh: "视图", en: "views" },
  { zh: "看板", en: "dashboards" },
  { zh: "连接器元数据", en: "connector metadata" },
] as const;

type SettingsConfigPortabilityPanelProps = {
  busyKey: string | null;
  configInput: string;
  configResult: Record<string, unknown> | null;
  onApplyConfig: (options: { input: string; confirm?: boolean }) => Promise<Record<string, unknown>>;
  onConfigInputChange: (value: string) => void;
  onExportConfig: () => Promise<Record<string, unknown>>;
  onRunConfigAction: (key: string, action: () => Promise<Record<string, unknown>>) => void;
  onValidateConfig: () => Promise<Record<string, unknown>>;
};

function resultSummary(result: Record<string, unknown> | null) {
  if (!result) {
    return "";
  }
  if (typeof result.exported === "string") {
    return result.exported;
  }
  if (Array.isArray(result.errors) && result.errors.length === 0) {
    return biText("配置校验通过", "Config validation passed");
  }
  if (result.dryRun === true) {
    return biText("恢复预演已生成，未覆盖配置", "Restore dry-run created; no config overwritten");
  }
  if (result.confirmed === true) {
    return biText("配置已恢复并完成校验", "Config restored and validated");
  }
  return typeof result.error === "string" ? result.error : biText("已完成", "Done");
}

function stringList(value: unknown) {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function tableCountTotal(result: Record<string, unknown>) {
  const tableCounts = result.tableCounts;
  if (!tableCounts || typeof tableCounts !== "object" || Array.isArray(tableCounts)) {
    return 0;
  }
  return Object.values(tableCounts).reduce((total, value) => total + (typeof value === "number" ? value : 0), 0);
}

function friendlyConfigWarning(warning: string) {
  const connectorMatch = warning.match(/Connector target table not imported yet:\s*(.+?)\s*->\s*(.+)$/);
  if (connectorMatch) {
    return biText(
      `连接器 ${connectorMatch[1]} 还没有同步成数据表 ${connectorMatch[2]}。`,
      `Connector ${connectorMatch[1]} has not been synced into table ${connectorMatch[2]} yet.`,
    );
  }
  return warning;
}

function configResultMessage(result: Record<string, unknown>) {
  const errors = stringList(result.errors);
  const warnings = stringList(result.warnings);
  const checkedCount = tableCountTotal(result);

  if (result.ok === false || errors.length) {
    return {
      tone: "warn",
      title: biText("需要先处理", "Needs attention"),
      summary: biText(
        `发现 ${errors.length || 1} 个配置问题，先不要恢复或覆盖配置。`,
        `${errors.length || 1} config issue found. Do not restore or overwrite config yet.`,
      ),
      next: biText("查看详情后修复配置，再重新校验。", "Review details, fix the config, then validate again."),
    };
  }

  if (result.dryRun === true) {
    return {
      tone: "ok",
      title: biText("恢复预演完成", "Restore preview ready"),
      summary: biText("系统只生成恢复计划，没有写入工作区。", "A restore plan was created without writing to the workspace."),
      next: biText("确认内容无误后，再点击确认覆盖。", "If the plan looks right, use confirm overwrite next."),
    };
  }

  if (result.confirmed === true) {
    return {
      tone: "ok",
      title: biText("配置已恢复", "Config restored"),
      summary: biText("配置已写入当前工作区，并完成基础校验。", "Config was written to the current workspace and passed basic validation."),
      next: biText("建议打开数据源和仪表盘做一次抽查。", "Open sources and dashboards for a quick spot check."),
    };
  }

  if (typeof result.exported === "string") {
    return {
      tone: "ok",
      title: biText("安全备份已导出", "Safe backup exported"),
      summary: biText("备份只包含工作区配置，不包含真实源文件或本地业务库。", "The backup contains workspace config only, not source files or local business databases."),
      next: result.exported,
    };
  }

  if (warnings.length) {
    return {
      tone: "caution",
      title: biText("可以继续使用，有待同步项", "Usable, with sync items"),
      summary: biText(
        `核心配置通过；还有 ${warnings.length} 个连接或引用需要后续同步。`,
        `Core config passed; ${warnings.length} connector or reference item still needs follow-up sync.`,
      ),
      next: friendlyConfigWarning(warnings[0]),
    };
  }

  return {
    tone: "ok",
    title: biText("配置可放心使用", "Config is ready"),
    summary: checkedCount
      ? biText(`已检查 ${checkedCount} 个配置项，没有发现阻断问题。`, `${checkedCount} config records checked with no blocking issue.`)
      : resultSummary(result),
    next: biText("可以继续导入、建模、编辑看板或让 Agent 生成待确认修改。", "Continue importing, modeling, editing dashboards, or asking Agent to create pending changes."),
  };
}

export function SettingsConfigPortabilityPanel({
  busyKey,
  configInput,
  configResult,
  onApplyConfig,
  onConfigInputChange,
  onExportConfig,
  onRunConfigAction,
  onValidateConfig,
}: SettingsConfigPortabilityPanelProps) {
  const configMessage = configResult ? configResultMessage(configResult) : null;
  const errors = configResult ? stringList(configResult.errors) : [];
  const warnings = configResult ? stringList(configResult.warnings) : [];

  return (
    <section className="settingsCard configPortabilityCard" aria-labelledby="config-portability-title">
      <div className="settingsCardHeader">
        <div>
          <span className="eyebrow"><Bilingual zh="配置迁移" en="Config portability" /></span>
          <h3 id="config-portability-title"><Bilingual zh="备份和恢复设置" en="Back up and restore settings" /></h3>
        </div>
      </div>
      <div className="configSafetyPlan" data-testid="settings-config-safety-plan">
        <div className="configSafetyLead">
          <span className="storyMode"><Bilingual zh="安全迁移顺序" en="Safe migration order" /></span>
          <strong><Bilingual zh="配置可以迁移，业务数据和密钥不跟着走" en="Config can move; business data and secrets do not" /></strong>
          <p>
            <Bilingual
              zh="这一步适合备份工作区设置、主题、字段口径和看板定义。恢复配置时必须先预览影响，再显式确认覆盖。"
              en="Use this for workspace settings, themes, field semantics, and dashboard definitions. Restore requires an impact preview before explicit overwrite confirmation."
            />
          </p>
        </div>
        <div className="configMigrationSteps" data-testid="settings-config-migration-steps">
          {configMigrationSteps.map((item) => (
            <div className={item.tone} key={item.key}>
              <span><Bilingual zh={item.labelZh} en={item.labelEn} /></span>
              <small><Bilingual zh={item.detailZh} en={item.detailEn} /></small>
            </div>
          ))}
        </div>
        <div className="configMigrationScope" data-testid="settings-config-migration-scope">
          {configMigrationScopes.map((item) => <span key={item.en}><Bilingual zh={item.zh} en={item.en} /></span>)}
        </div>
      </div>
      <div className="configActionGrid">
        <button className="secondaryButton" disabled={busyKey === "validate-config"} onClick={() => onRunConfigAction("validate-config", onValidateConfig)} type="button">
          <Icon name="check" />
          <span><Bilingual zh="检查当前设置" en="Check settings" /></span>
        </button>
        <button className="primaryButton" disabled={busyKey === "export-config"} onClick={() => onRunConfigAction("export-config", onExportConfig)} type="button">
          <Icon name="copy" />
          <span><Bilingual zh="备份工作区设置" en="Back up workspace settings" /></span>
        </button>
      </div>
      {configResult && configMessage ? (
        <div className={`configResult ${configMessage.tone}`} data-testid="settings-config-friendly-result">
          <div className="configResultHeader">
            <span className="configResultStatus">{configMessage.title}</span>
            <strong>{configMessage.summary}</strong>
          </div>
          <p className="configResultSummary">{configMessage.next}</p>
          <div className="configResultFacts" data-testid="settings-config-result-facts">
            <span>{biText(`错误 ${errors.length}`, `Errors ${errors.length}`)}</span>
            <span>{biText(`提醒 ${warnings.length}`, `Warnings ${warnings.length}`)}</span>
            <span>{biText(`配置项 ${tableCountTotal(configResult)}`, `Config records ${tableCountTotal(configResult)}`)}</span>
          </div>
          {errors.length || warnings.length ? (
            <details className="configResultDetails" data-testid="settings-config-result-technical">
              <summary>{biText("查看配置检查明细", "View config check details")}</summary>
              <ul>
                {[...errors, ...warnings].slice(0, 4).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </details>
          ) : null}
        </div>
      ) : null}
      <details className="advancedDetails compactAdvanced configRestoreDetails" data-testid="settings-config-restore-guard">
        <summary>{biText("需要恢复备份时展开", "Open only when restoring a backup")}</summary>
        <div className="configRestoreForm">
          <p className="quietText">
            <Bilingual
              zh="恢复只应用配置元数据。先检查影响范围，确认无误后再覆盖当前工作区设置。"
              en="Restore applies metadata only. Preview impact first, then overwrite workspace settings only after confirmation."
            />
          </p>
          <label>
            <span><Bilingual zh="备份文件路径" en="Backup file path" /></span>
            <input value={configInput} onChange={(event) => onConfigInputChange(event.target.value)} placeholder="data/local/config_exports/aibi_config_YYYYMMDD_HHMMSS.json" />
          </label>
          <div className="settingsActions" data-testid="settings-config-restore-actions">
            <button disabled={!configInput || busyKey === "apply-config-dry"} onClick={() => onRunConfigAction("apply-config-dry", () => onApplyConfig({ input: configInput }))} type="button">
              <Icon name="query" />
              <span><Bilingual zh="检查恢复影响" en="Preview restore impact" /></span>
            </button>
            <button className="dangerButton" disabled={!configInput || busyKey === "apply-config-confirm"} onClick={() => onRunConfigAction("apply-config-confirm", () => onApplyConfig({ input: configInput, confirm: true }))} type="button">
              <Icon name="lock" />
              <span><Bilingual zh="确认覆盖" en="Confirm overwrite" /></span>
            </button>
          </div>
        </div>
      </details>
    </section>
  );
}
