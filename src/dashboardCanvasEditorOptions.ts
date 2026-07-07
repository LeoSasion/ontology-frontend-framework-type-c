import { biText } from "./components/Bilingual";
import type { WidgetDraft, WidgetToggleKey } from "./dashboardCanvasWidgetModel";

export const widgetTypes = ["metric", "bar", "line", "pie", "table", "text", "slicer"];
export const valueFormats = ["auto", "plain", "compact", "currency", "percent"];
export const colorPalettes = ["default", "fresh", "warm", "contrast", "mono"];
export const rankingModes = ["standard", "ranked"];
export const slicerDisplays = ["list", "dropdown", "range"];

export const dashboardAcceptanceItems = [
  { key: "metric", zh: "指标", en: "Metric" },
  { key: "bar", zh: "柱图", en: "Bar" },
  { key: "line", zh: "折线", en: "Line" },
  { key: "pie", zh: "饼图", en: "Pie" },
  { key: "table", zh: "表格", en: "Table" },
  { key: "text", zh: "文本", en: "Text" },
  { key: "slicer", zh: "切片器", en: "Slicer" },
  { key: "relationship", zh: "关系", en: "Relation" },
  { key: "filter", zh: "筛选", en: "Filter" },
  { key: "drilldown", zh: "下钻", en: "Drill" },
  { key: "copy-delete", zh: "复制/删除", en: "Copy/Delete" },
  { key: "style", zh: "样式", en: "Style" },
] as const;

export type WidgetToggleOption = {
  key: WidgetToggleKey;
  label: string;
  checked: boolean;
};

export function buildWidgetToggleOptions(widgetDraft: WidgetDraft): WidgetToggleOption[] {
  return [
    { key: "showLegend", label: biText("图例", "Legend"), checked: widgetDraft.showLegend },
    { key: "showAxis", label: biText("坐标轴", "Axis"), checked: widgetDraft.showAxis },
    { key: "showDataLabel", label: biText("数据标签", "Data labels"), checked: widgetDraft.showDataLabel },
    { key: "lineSmooth", label: biText("平滑折线", "Smooth line"), checked: widgetDraft.lineSmooth },
    { key: "areaFill", label: biText("面积填充", "Area fill"), checked: widgetDraft.areaFill },
    { key: "slicerMultiSelect", label: biText("多选切片", "Multi-select slicer"), checked: widgetDraft.slicerMultiSelect },
    { key: "slicerSearchable", label: biText("切片搜索", "Slicer search"), checked: widgetDraft.slicerSearchable },
    { key: "crossFilter", label: biText("联动筛选", "Cross-filter"), checked: widgetDraft.crossFilter },
    { key: "drillDown", label: biText("允许下钻", "Drilldown"), checked: widgetDraft.drillDown },
    { key: "globalFilterTarget", label: biText("接收全局筛选", "Global filter target"), checked: widgetDraft.globalFilterTarget },
  ];
}
