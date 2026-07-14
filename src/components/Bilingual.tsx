import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

export type UiLanguage = "zh" | "en";
export type LanguageMode = "auto" | UiLanguage;

type BilingualProps = {
  zh: ReactNode;
  en: ReactNode;
  className?: string;
  inline?: boolean;
};

type LanguageContextValue = {
  mode: LanguageMode;
  resolvedLanguage: UiLanguage;
  setMode: (mode: LanguageMode) => void;
  toggleLanguage: () => void;
};

const languageStorageKey = "aibiHybrid.languageMode";

function detectBrowserLanguage(): UiLanguage {
  if (typeof navigator === "undefined") {
    return "en";
  }

  const languages = navigator.languages?.length ? navigator.languages : [navigator.language];
  return languages.some((language) => language.toLowerCase().startsWith("zh")) ? "zh" : "en";
}

function readStoredLanguageMode(): LanguageMode {
  if (typeof window === "undefined") {
    return "auto";
  }

  try {
    const stored = window.localStorage.getItem(languageStorageKey);
    return stored === "zh" || stored === "en" || stored === "auto" ? stored : "auto";
  } catch {
    return "auto";
  }
}

function resolveLanguage(mode: LanguageMode): UiLanguage {
  return mode === "auto" ? detectBrowserLanguage() : mode;
}

let activeLanguage: UiLanguage = resolveLanguage(readStoredLanguageMode());

const LanguageContext = createContext<LanguageContextValue>({
  mode: "auto",
  resolvedLanguage: activeLanguage,
  setMode: () => undefined,
  toggleLanguage: () => undefined,
});

const nameTranslations: Record<string, { zh: string; en: string }> = {
  "AIBI-C 工作区": { zh: "AIBI-C 工作区", en: "AIBI-C Workspace" },
  "分析证据看板": { zh: "分析证据看板", en: "Evidence Dashboard" },
  "Agent 分析看板": { zh: "Agent 分析看板", en: "Agent Analysis Dashboard" },
  "证据合同检查": { zh: "证据合同检查", en: "Evidence Contract Check" },
  "生成看板草案": { zh: "生成看板草案", en: "Draft dashboard" },
  "生成分析计划": { zh: "生成分析计划", en: "Draft analysis plan" },
  "Generic tabular data / 通用表格数据": { zh: "通用表格数据", en: "Generic tabular data" },
};

const roleTranslations: Record<string, { zh: string; en: string }> = {
  identity_key: { zh: "身份键", en: "Key" },
  event_time: { zh: "时间", en: "Time" },
  dimension: { zh: "维度", en: "Dim." },
  measure: { zh: "指标", en: "Measure" },
  status: { zh: "状态", en: "Status" },
};

const usageTranslations: Record<string, { zh: string; en: string }> = {
  joinable: { zh: "可关联", en: "Join" },
  filterable: { zh: "可筛选", en: "Filter" },
  groupable: { zh: "可分组", en: "Group" },
  aggregatable: { zh: "可聚合", en: "Agg." },
};

const statusTranslations: Record<string, { zh: string; en: string }> = {
  draft: { zh: "草案", en: "Draft" },
  confirmed: { zh: "已确认", en: "Confirmed" },
  "read-only": { zh: "只读", en: "Read-only" },
  "read-only-legacy": { zh: "只读历史", en: "Read-only legacy" },
};

const noteTranslations: Record<string, { zh: string; en: string }> = {
  "No bundled data is loaded by default; import local files to begin analysis.": {
    zh: "默认不加载内置数据；请导入本地文件后开始分析。",
    en: "No bundled data is loaded by default; import local files to begin analysis.",
  },
  "No workspace data was read; start the local API or import data.": {
    zh: "未读到工作区数据；请启动本地 API 或导入数据。",
    en: "No workspace data was read; start the local API or import data.",
  },
  "Connecting to local data service...": {
    zh: "正在连接本地数据服务。",
    en: "Connecting to local data service.",
  },
};

const pipelineStageTranslations: Record<string, { zh: string; en: string }> = {
  Reader: { zh: "读取器", en: "Reader" },
  Profiler: { zh: "画像分析", en: "Profiler" },
  "Semantic scorer": { zh: "语义评分", en: "Semantic scorer" },
  "Relationship discovery": { zh: "关系发现", en: "Relationship discovery" },
  Diagnostics: { zh: "诊断", en: "Diagnostics" },
  "Metric compiler": { zh: "指标编译器", en: "Metric compiler" },
  "Query runtime": { zh: "查询运行时", en: "Query runtime" },
  "Confirmation overlay": { zh: "确认覆盖层", en: "Confirmation overlay" },
  "Artifact contract": { zh: "产物合同", en: "Artifact contract" },
};

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<LanguageMode>(() => readStoredLanguageMode());
  const [detectedLanguage, setDetectedLanguage] = useState<UiLanguage>(() => detectBrowserLanguage());

  useEffect(() => {
    if (typeof window === "undefined") {
      return undefined;
    }

    function refreshDetectedLanguage() {
      setDetectedLanguage(detectBrowserLanguage());
    }

    window.addEventListener("languagechange", refreshDetectedLanguage);
    return () => window.removeEventListener("languagechange", refreshDetectedLanguage);
  }, []);

  const resolvedLanguage = mode === "auto" ? detectedLanguage : mode;
  activeLanguage = resolvedLanguage;

  const value = useMemo<LanguageContextValue>(() => {
    function setMode(nextMode: LanguageMode) {
      setModeState(nextMode);
      if (typeof window !== "undefined") {
        try {
          window.localStorage.setItem(languageStorageKey, nextMode);
        } catch {
          // Language changes should still apply when storage is blocked.
        }
      }
    }

    function toggleLanguage() {
      setMode(resolvedLanguage === "zh" ? "en" : "zh");
    }

    return {
      mode,
      resolvedLanguage,
      setMode,
      toggleLanguage,
    };
  }, [mode, resolvedLanguage]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  return useContext(LanguageContext);
}

export function LanguageToggle() {
  const { mode, resolvedLanguage, setMode } = useLanguage();
  const options: Array<{ mode: LanguageMode; label: string; ariaLabel: string }> = [
    { mode: "auto", label: biText("自动", "Auto"), ariaLabel: biText("自动检测语言", "Auto-detect language") },
    { mode: "zh", label: "中文", ariaLabel: biText("切换到中文", "Switch to Chinese") },
    { mode: "en", label: "EN", ariaLabel: biText("切换到英文", "Switch to English") },
  ];

  return (
    <div
      className="languageToggle"
      role="group"
      aria-label={biText("界面语言", "Interface language")}
      title={biText(`当前: ${resolvedLanguage === "zh" ? "中文" : "英文"}`, `Current: ${resolvedLanguage === "zh" ? "Chinese" : "English"}`)}
    >
      {options.map((option) => (
        <button
          aria-label={option.ariaLabel}
          aria-pressed={mode === option.mode}
          className={mode === option.mode ? "languageOption active" : "languageOption"}
          key={option.mode}
          onClick={() => setMode(option.mode)}
          type="button"
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function Bilingual({ zh, en, className = "", inline = false }: BilingualProps) {
  const { resolvedLanguage } = useLanguage();
  const classNames = [inline ? "biInline" : "biStack", className].filter(Boolean).join(" ");
  return <span className={classNames}>{resolvedLanguage === "zh" ? zh : en}</span>;
}

export function biText(zh: string, en: string) {
  return activeLanguage === "zh" ? zh : en;
}

export function localizedText(value: string) {
  const separator = " / ";
  if (!value.includes(separator)) {
    return value;
  }

  const [zh, ...rest] = value.split(separator);
  const en = rest.join(separator);
  if (!zh || !en) {
    return value;
  }

  return biText(zh, en);
}

export function translateName(value: string) {
  return nameTranslations[value] ?? { zh: value, en: value };
}

export function translateRole(value: string) {
  return roleTranslations[value] ?? { zh: value, en: value };
}

export function translateUsage(value: string) {
  return usageTranslations[value] ?? { zh: value, en: value };
}

export function translateStatus(value: string) {
  return statusTranslations[value] ?? { zh: value, en: value };
}

export function translateNote(value: string) {
  return noteTranslations[value] ?? { zh: value, en: value };
}

export function translatePipelineStage(value: string) {
  return pipelineStageTranslations[value] ?? { zh: value, en: value };
}
