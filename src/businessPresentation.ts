import { biText } from "./components/Bilingual";

export function businessIdentifier(value: unknown, fallback: string) {
  const text = typeof value === "string" ? value.trim() : "";
  if (!text || /^(source|run|action|workspace)_[a-z0-9_-]+$/i.test(text)) return fallback;
  const labels: Record<string, string> = {
    chart_preview: biText("图表生成规则", "Chart generation rule"),
    ontology: biText("业务模型规则", "Business model rule"),
    "query-runtime": biText("查询回执", "Query receipt"),
  };
  return labels[text] ?? text;
}

export function formatBusinessValue(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(value);
  }
  if (typeof value === "string" && /^-?\d+(?:\.\d+)?$/.test(value.trim())) {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 }).format(parsed);
  }
  return value === null || typeof value === "undefined" || value === "" ? "-" : String(value);
}
