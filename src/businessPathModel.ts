import type { AppSection } from "./appSections";

export type BusinessPathStepKey = "data" | "chart" | "evidence" | "confirm";

export type BusinessPathIcon = "source" | "dashboard" | "evidence" | "check";

export type BusinessPathStep = {
  key: BusinessPathStepKey;
  section: AppSection;
  icon: BusinessPathIcon;
  zh: string;
  en: string;
  actionZh: string;
  actionEn: string;
};

export const businessPathSteps: BusinessPathStep[] = [
  {
    key: "data",
    section: "sources",
    icon: "source",
    zh: "接入数据",
    en: "Connect data",
    actionZh: "去数据源",
    actionEn: "Open sources",
  },
  {
    key: "chart",
    section: "dashboards",
    icon: "dashboard",
    zh: "生成图表",
    en: "Create chart",
    actionZh: "去仪表盘",
    actionEn: "Open dashboards",
  },
  {
    key: "evidence",
    section: "evidence",
    icon: "evidence",
    zh: "核对证据",
    en: "Review evidence",
    actionZh: "去证据页",
    actionEn: "Open evidence",
  },
  {
    key: "confirm",
    section: "agent",
    icon: "check",
    zh: "确认写入",
    en: "Approve writes",
    actionZh: "去 AI 助手",
    actionEn: "Open AI",
  },
];

export function businessSectionForStep(stepKey: BusinessPathStepKey): AppSection {
  return businessPathSteps.find((step) => step.key === stepKey)?.section ?? "home";
}

export function businessStepForSection(section: AppSection): BusinessPathStepKey | null {
  if (section === "sources") return "data";
  if (section === "views" || section === "dashboards") return "chart";
  if (section === "evidence") return "evidence";
  if (section === "agent") return "confirm";
  return null;
}
