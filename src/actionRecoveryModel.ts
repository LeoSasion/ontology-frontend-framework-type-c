import type { AppSection } from "./appSections";

export type RecoveryText = {
  zh: string;
  en: string;
};

export type ActionRecoveryCategory =
  | "service"
  | "source"
  | "query"
  | "view"
  | "dashboard"
  | "agent"
  | "settings"
  | "unknown";

export type ActionRecovery = {
  action: string;
  category: ActionRecoveryCategory;
  title: RecoveryText;
  detail: RecoveryText;
  next: RecoveryText;
  safeState: RecoveryText;
  steps: RecoveryText[];
  targetSection: AppSection;
  evidence: string[];
  technical: string;
};

const baseEvidence = ["local-api-strict-mode", "no-sample-fallback-for-core-action"];

function text(zh: string, en: string): RecoveryText {
  return { zh, en };
}

export function errorMessage(error: unknown) {
  return error instanceof Error && error.message ? error.message : String(error || "Local API request failed");
}

function hasAny(value: string, fragments: string[]) {
  return fragments.some((fragment) => value.includes(fragment));
}

function categoryForAction(action: string, normalizedMessage: string): ActionRecoveryCategory {
  if (hasAny(normalizedMessage, ["failed to fetch", "networkerror", "econnrefused", "local api request failed", "fetch failed", "8787"])) {
    return "service";
  }
  if (hasAny(normalizedMessage, ["no csv/xlsx sources found", "no sources found", "permission denied", "access denied", "not found", "does not exist", "no such file", "enoent"])) {
    return "source";
  }
  if (action.includes("agent")) return "agent";
  if (action.includes("setting") || action.includes("config") || action.includes("theme") || action.includes("preference")) return "settings";
  if (action.includes("dashboard") || action.includes("widget") || action.includes("filter") || action.includes("business-dashboard")) return "dashboard";
  if (action.includes("query-table") || action.includes("view") || action.includes("drill")) return "view";
  if (action.includes("query") || action.includes("metric") || action.includes("formula") || action.includes("relationship") || hasAny(normalizedMessage, ["sql", "duckdb", "sqlite", "binder", "column"])) {
    return "query";
  }
  if (action.includes("source") || action.includes("import") || action.includes("connector")) return "source";
  return "unknown";
}

function recoveryByCategory(category: ActionRecoveryCategory): Omit<ActionRecovery, "action" | "category" | "technical"> {
  if (category === "service") {
    return {
      title: text("本地数据服务没有响应", "Local data service did not respond"),
      detail: text("页面已经停下等待，没有改动数据、看板或配置。通常是 API 服务未启动、端口被占用，或刚重启还没完成。", "The page stopped safely without changing data, dashboards, or settings. Usually the API is not running, the port is occupied, or startup is still in progress."),
      next: text("运行 npm run dev，等 8686/8787 都就绪后刷新当前页面。", "Run npm run dev, wait until both 8686 and 8787 are ready, then refresh this page."),
      safeState: text("未执行写入", "No write executed"),
      steps: [
        text("确认终端里 `npm run dev` 仍在运行。", "Confirm `npm run dev` is still running in the terminal."),
        text("如果提示端口冲突，先关闭占用 8686 或 8787 的旧服务。", "If a port conflict appears, stop the old service using 8686 or 8787."),
        text("刷新页面后重试；仍失败时让 Agent 解释当前服务状态。", "Refresh and retry; if it still fails, ask Agent to explain the current service state."),
      ],
      targetSection: "settings",
      evidence: [...baseEvidence, "service-recovery"],
    };
  }
  if (category === "source") {
    return {
      title: text("数据源没有准备好", "Source data is not ready"),
      detail: text("系统没有找到可读文件、路径或权限，已经停止在预检/画像阶段，没有写坏数据。", "The system could not read a file, path, or permission and stopped during preview/profiling without damaging data."),
      next: text("回到数据源页，选择一个明确的 CSV/XLSX 文件或文件夹跑通预检。", "Go back to Sources and first run preview with one explicit CSV/XLSX file or folder."),
      safeState: text("导入前停止", "Stopped before import"),
      steps: [
        text("从资源管理器复制完整路径；多路径时一行一个。", "Copy the full path from Explorer; use one path per line for multiple paths."),
        text("确认文件是 CSV/XLSX，且当前用户有读取权限。", "Confirm the files are CSV/XLSX and readable by this Windows user."),
        text("先跑只读 Source Intelligence，再决定是否确认导入或建看板。", "Run read-only Source Intelligence first, then decide whether to confirm import or create a dashboard."),
      ],
      targetSection: "sources",
      evidence: [...baseEvidence, "source-recovery"],
    };
  }
  if (category === "query") {
    return {
      title: text("查询口径没有跑通", "Query scope did not run"),
      detail: text("通常是字段、指标、公式、关系或 SQL 运行时不匹配。系统只返回失败回执，没有改动元数据。", "This usually means a field, metric, formula, relationship, or SQL runtime mismatch. The system only returned a failure receipt and did not change metadata."),
      next: text("回数据源页核对字段语义和指标口径，或让 Agent 说明缺哪个字段。", "Return to Sources to check field semantics and metric definitions, or ask Agent which field is missing."),
      safeState: text("只读查询失败", "Read-only query failed"),
      steps: [
        text("检查当前表里是否仍有被查询的字段。", "Check whether the queried fields still exist in the active table."),
        text("刷新字段语义、指标或公式预览，确认口径可执行。", "Refresh field semantics, metrics, or formula preview and confirm the definition is executable."),
        text("如果是关联查询，先在关系建模里预览匹配度。", "For relationship queries, preview the match quality in relationship modeling first."),
      ],
      targetSection: "sources",
      evidence: [...baseEvidence, "query-recovery"],
    };
  }
  if (category === "view") {
    return {
      title: text("明细视图没有刷新", "Detail view did not refresh"),
      detail: text("视图查询、分页、搜索或下钻范围没有成功返回。已有视图不会被覆盖。", "The view query, pagination, search, or drilldown scope did not return successfully. Existing views were not overwritten."),
      next: text("在明细页放宽筛选或搜索，再刷新；字段变更后先回数据源核对。", "In Details, relax filters or search and refresh; after field changes, check Sources first."),
      safeState: text("视图未覆盖", "View not overwritten"),
      steps: [
        text("清空搜索词或减少筛选条件。", "Clear the search term or reduce filters."),
        text("确认保存视图引用的字段仍在当前表中。", "Confirm the saved view fields still exist in the active table."),
        text("从看板下钻保存前，先预演保存视图。", "Before saving from dashboard drilldown, preview the view save first."),
      ],
      targetSection: "views",
      evidence: [...baseEvidence, "view-recovery"],
    };
  }
  if (category === "dashboard") {
    return {
      title: text("看板修改没有应用", "Dashboard change was not applied"),
      detail: text("组件、筛选、模板或看板写入没有完成；确认前不会更新画布。", "The widget, filter, template, or dashboard write did not complete; the canvas is not updated before confirmation."),
      next: text("回看板页先预演当前表的组件，再确认目标看板和字段。", "Return to Dashboards, preview widgets for the current table first, then confirm the target board and fields."),
      safeState: text("看板未写入", "Dashboard not written"),
      steps: [
        text("确认目标看板名称和当前表。", "Confirm the target dashboard name and active table."),
        text("先使用预览或 ERP 单元预演，检查会生成哪些组件。", "Use preview or ERP unit preview first to inspect proposed widgets."),
        text("缺字段时不要强行写入，先补数据或让 Agent 重新选择组件。", "When fields are missing, do not force a write; add data or ask Agent to reselect widgets."),
      ],
      targetSection: "dashboards",
      evidence: [...baseEvidence, "dashboard-recovery"],
    };
  }
  if (category === "agent") {
    return {
      title: text("Agent 没有完成回答", "Agent did not finish"),
      detail: text("Agent 回答或草案生成失败，但写入边界仍然有效，没有自动执行修改。", "The Agent answer or draft failed, but write guardrails remained active and no change was executed automatically."),
      next: text("换成只读问题重试，或先打开证据页查看当前能回答什么。", "Retry with a read-only question, or open Evidence to see what can be answered now."),
      safeState: text("没有自动执行草案", "No draft executed automatically"),
      steps: [
        text("先问“当前工作区能回答什么”，减少目标歧义。", "First ask what the current workspace can answer to reduce ambiguity."),
        text("如果需要创建看板，确认 Agent 先生成待确认草案。", "If creating a dashboard, confirm Agent creates a pending draft first."),
        text("没有外部 LLM key 时走确定性 fallback，不应阻塞本地验证。", "Without an external LLM key, deterministic fallback should keep local validation unblocked."),
      ],
      targetSection: "agent",
      evidence: [...baseEvidence, "agent-recovery"],
    };
  }
  if (category === "settings") {
    return {
      title: text("系统配置没有应用", "System configuration was not applied"),
      detail: text("偏好、主题或配置恢复没有完成。导入数据和看板不应被这次失败影响。", "Preferences, theme, or config restore did not finish. Imported data and dashboards should not be affected by this failure."),
      next: text("回系统页先做预演或校验，再决定是否确认应用。", "Return to System, run preview or validation first, then decide whether to apply."),
      safeState: text("配置未覆盖", "Config not overwritten"),
      steps: [
        text("先运行配置校验或导出备份。", "Run config validation or export a backup first."),
        text("恢复配置前确认目标工作区。", "Confirm the target workspace before restoring config."),
        text("失败后重新打开数据源和看板做一次抽查。", "After failure, reopen Sources and Dashboards for a quick spot check."),
      ],
      targetSection: "settings",
      evidence: [...baseEvidence, "settings-recovery"],
    };
  }
  return {
    title: text("动作没有完成", "Action did not finish"),
    detail: text("系统已停止在安全边界内，没有继续写入或覆盖。", "The system stopped inside the safety boundary and did not continue with a write or overwrite."),
    next: text("查看错误原文；如果不确定，直接让 Agent 解释下一步。", "View the raw error; if unsure, ask Agent to explain the next step."),
    safeState: text("保持原状", "State unchanged"),
    steps: [
      text("确认当前页面和目标对象是否正确。", "Confirm the current page and target object are correct."),
      text("先尝试预演或只读查询。", "Try preview or a read-only query first."),
      text("再让 Agent 根据证据生成下一步计划。", "Then ask Agent to generate the next plan from evidence."),
    ],
    targetSection: "agent",
    evidence: [...baseEvidence, "generic-recovery"],
  };
}

export function buildActionRecovery(action: string, error: unknown): ActionRecovery {
  const technical = errorMessage(error);
  const normalizedMessage = technical.toLowerCase();
  const category = categoryForAction(action.toLowerCase(), normalizedMessage);
  return {
    action,
    category,
    technical,
    ...recoveryByCategory(category),
  };
}

function isRecoveryText(value: unknown): value is RecoveryText {
  return Boolean(value && typeof value === "object" && typeof (value as RecoveryText).zh === "string" && typeof (value as RecoveryText).en === "string");
}

export function actionRecoveryFromResult(result: Record<string, unknown> | null): ActionRecovery | null {
  const recovery = result?.recovery;
  if (!recovery || typeof recovery !== "object") return null;
  const candidate = recovery as Partial<ActionRecovery>;
  if (
    typeof candidate.action === "string" &&
    typeof candidate.category === "string" &&
    isRecoveryText(candidate.title) &&
    isRecoveryText(candidate.detail) &&
    isRecoveryText(candidate.next) &&
    isRecoveryText(candidate.safeState) &&
    typeof candidate.targetSection === "string" &&
    typeof candidate.technical === "string" &&
    Array.isArray(candidate.steps)
  ) {
    return {
      action: candidate.action,
      category: candidate.category as ActionRecoveryCategory,
      title: candidate.title,
      detail: candidate.detail,
      next: candidate.next,
      safeState: candidate.safeState,
      steps: candidate.steps.filter(isRecoveryText),
      targetSection: candidate.targetSection as AppSection,
      evidence: Array.isArray(candidate.evidence) ? candidate.evidence.filter((item): item is string => typeof item === "string") : [],
      technical: candidate.technical,
    };
  }
  return null;
}

export function actionRecoveryFromError(error: unknown): ActionRecovery | null {
  if (!error || typeof error !== "object") return null;
  const payload = (error as { payload?: unknown }).payload;
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return null;
  return actionRecoveryFromResult(payload as Record<string, unknown>);
}
