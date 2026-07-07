export type AppSection = "home" | "sources" | "views" | "dashboards" | "agent" | "evidence" | "settings";

export type AppSectionIcon = "source" | "dashboard" | "agent" | "evidence" | "settings";

export type LocalizedText = {
  zh: string;
  en: string;
};

export type AppSectionMeta = {
  key: AppSection;
  zh: string;
  en: string;
  shortZh: string;
  shortEn: string;
  icon: AppSectionIcon;
  role: "primary" | "utility";
  flowOrder?: number;
  headline: LocalizedText;
  loading: LocalizedText;
  loadingDetail: LocalizedText;
};

export const appSections: Record<AppSection, AppSectionMeta> = {
  home: {
    key: "home",
    zh: "起步",
    en: "Start",
    shortZh: "起步",
    shortEn: "Start",
    icon: "dashboard",
    role: "primary",
    flowOrder: 0,
    headline: {
      zh: "从业务问题开始，系统负责计算和留证",
      en: "Start from a business question. The system calculates and records evidence.",
    },
    loading: { zh: "正在打开工作区首页", en: "Opening workspace home" },
    loadingDetail: { zh: "工作区外壳已就绪，正在载入当前功能区。", en: "The workspace shell is ready. Loading the selected workspace module." },
  },
  sources: {
    key: "sources",
    zh: "数据源",
    en: "Sources",
    shortZh: "数据",
    shortEn: "Data",
    icon: "source",
    role: "primary",
    flowOrder: 1,
    headline: {
      zh: "治理原始数据源，确认后才写入",
      en: "Govern raw sources; write only after confirmation.",
    },
    loading: { zh: "正在打开数据源工作台", en: "Opening source workbench" },
    loadingDetail: { zh: "正在准备导入预检、字段口径、画像和安全写入入口。", en: "Preparing import checks, field semantics, profiling, and safe write controls." },
  },
  views: {
    key: "views",
    zh: "明细",
    en: "Details",
    shortZh: "明细",
    shortEn: "Details",
    icon: "source",
    role: "primary",
    flowOrder: 2,
    headline: {
      zh: "保存业务明细口径，用于查询、下钻和看板",
      en: "Save detail scopes for queries, drilldowns, and dashboards.",
    },
    loading: { zh: "正在打开视图工作台", en: "Opening view workbench" },
    loadingDetail: { zh: "正在载入可复用明细、白名单查询和下钻上下文。", en: "Loading reusable details, whitelist queries, and drilldown context." },
  },
  dashboards: {
    key: "dashboards",
    zh: "仪表盘",
    en: "Dashboards",
    shortZh: "看板",
    shortEn: "Board",
    icon: "dashboard",
    role: "primary",
    flowOrder: 3,
    headline: {
      zh: "阅读看板结果，在当前对象上起草修改",
      en: "Read dashboards, then draft changes on the selected object.",
    },
    loading: { zh: "正在打开看板工作台", en: "Opening dashboard workbench" },
    loadingDetail: { zh: "正在装配指标、筛选、组件和证据入口。", en: "Preparing metrics, filters, widgets, and evidence entry points." },
  },
  agent: {
    key: "agent",
    zh: "AI 助手",
    en: "AI",
    shortZh: "提问",
    shortEn: "Ask",
    icon: "agent",
    role: "primary",
    flowOrder: 4,
    headline: {
      zh: "用自然语言获得答案、计划和待确认修改",
      en: "Use language to get answers, plans, and confirmable changes.",
    },
    loading: { zh: "正在打开 Agent 面板", en: "Opening Agent panel" },
    loadingDetail: { zh: "正在载入当前工作区、匹配对象和待确认修改。", en: "Loading the active workspace, matched object, and pending changes." },
  },
  evidence: {
    key: "evidence",
    zh: "证据",
    en: "Evidence",
    shortZh: "证据",
    shortEn: "Proof",
    icon: "evidence",
    role: "primary",
    flowOrder: 5,
    headline: {
      zh: "核对结论背后的来源、口径和回执",
      en: "Trace each result to sources, definitions, and receipts.",
    },
    loading: { zh: "正在打开证据面板", en: "Opening evidence panel" },
    loadingDetail: { zh: "正在载入来源、指标口径、组件引用和执行回执。", en: "Loading sources, metric definitions, widget references, and receipts." },
  },
  settings: {
    key: "settings",
    zh: "系统",
    en: "System",
    shortZh: "系统",
    shortEn: "System",
    icon: "settings",
    role: "utility",
    headline: {
      zh: "系统管理：外观、权限和迁移边界",
      en: "System management: appearance, permissions, and migration boundaries.",
    },
    loading: { zh: "正在打开设置中心", en: "Opening settings" },
    loadingDetail: { zh: "正在准备外观、权限、配置迁移和只读边界。", en: "Preparing appearance, permissions, config portability, and read-only boundaries." },
  },
};

export const appSectionOrder: AppSection[] = ["home", "sources", "views", "dashboards", "agent", "evidence", "settings"];
export const primaryAppSections = appSectionOrder.filter((section) => appSections[section].role === "primary");
export const utilityAppSections = appSectionOrder.filter((section) => appSections[section].role === "utility");
export const flowAppSections = appSectionOrder.filter((section) => appSections[section].flowOrder !== undefined);

export function getAppSection(section: AppSection) {
  return appSections[section];
}

export function isAppSection(value: string | null): value is AppSection {
  return Boolean(value && Object.hasOwn(appSections, value));
}
