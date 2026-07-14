import type { BiDashboardWidget } from "./biDashboardModel";

export type WidgetReadingPurpose = {
  title: { zh: string; en: string };
  detail: { zh: string; en: string };
  action: { zh: string; en: string };
};

export const B_WIDGET_READING_PURPOSES: Record<BiDashboardWidget["type"], WidgetReadingPurpose> = {
  metric: {
    title: { zh: "先看总量", en: "Start with totals" },
    detail: { zh: "指标卡回答现在是多少、是否值得继续看。", en: "Metric cards answer how much it is and whether to continue." },
    action: { zh: "点明细查看口径", en: "Open detail for scope" },
  },
  bar: {
    title: { zh: "再看排行", en: "Compare ranks" },
    detail: { zh: "柱状图找出分类或对象之间的差距。", en: "Bar charts expose gaps across categories or objects." },
    action: { zh: "点柱子下钻", en: "Click a bar to drill down" },
  },
  line: {
    title: { zh: "确认趋势", en: "Check movement" },
    detail: { zh: "折线图判断变化是不是持续、反弹或异常。", en: "Line charts show whether changes persist, rebound, or spike." },
    action: { zh: "按时间顺序读", en: "Read in time order" },
  },
  pie: {
    title: { zh: "看构成", en: "Read composition" },
    detail: { zh: "环形图说明谁贡献了主要占比。", en: "Donut charts show who contributes the largest share." },
    action: { zh: "点扇区看来源", en: "Click a segment for source" },
  },
  table: {
    title: { zh: "落到明细", en: "Inspect rows" },
    detail: { zh: "明细表保留可核对的行级证据。", en: "Tables keep row-level evidence for review." },
    action: { zh: "保存成视图", en: "Save as a view" },
  },
  text: {
    title: { zh: "读结论", en: "Read the note" },
    detail: { zh: "文本卡承接 Agent 或证据摘要，不替代数据。", en: "Text cards hold Agent or evidence notes without replacing data." },
    action: { zh: "查看证据引用", en: "Review evidence refs" },
  },
  slicer: {
    title: { zh: "最后筛选", en: "Filter last" },
    detail: { zh: "切片器用熟悉的条件联动其他组件。", en: "Slicers apply familiar filters across widgets." },
    action: { zh: "点选即联动", en: "Select to cross-filter" },
  },
};

export const B_WIDGET_ACCEPTANCE_ITEMS = [
  {
    key: "metric",
    label: { zh: "看总量", en: "Read totals" },
    detail: { zh: "先确认核心数字、数值格式和证据口径。", en: "Confirm the core number, value format, and evidence scope first." },
    technical: { zh: "指标卡：总量、均值、最大/最小、数值格式和证据口径。", en: "Metric widget: totals, averages, min/max, value formats, and evidence scope." },
  },
  {
    key: "bar",
    label: { zh: "看排行", en: "Compare ranks" },
    detail: { zh: "找出分类或对象之间的差距。", en: "Find gaps across categories or objects." },
    technical: { zh: "柱状图：分类排行、横/纵方向、排序、标签和配色。", en: "Bar widget: category ranking, orientation, sort, labels, and palette." },
  },
  {
    key: "line",
    label: { zh: "看趋势", en: "Check trends" },
    detail: { zh: "判断变化是持续、反弹还是异常。", en: "Decide whether movement is sustained, rebounding, or abnormal." },
    technical: { zh: "折线图：趋势、平滑线、面积填充、坐标轴和时间口径。", en: "Line widget: trend, smoothing, area fill, axes, and time scope." },
  },
  {
    key: "pie",
    label: { zh: "看构成", en: "Read composition" },
    detail: { zh: "确认主要贡献来自哪些对象。", en: "Confirm which objects contribute the largest share." },
    technical: { zh: "饼图：构成占比、环形/饼形、图例和数据标签。", en: "Pie widget: composition, donut/pie mode, legend, and data labels." },
  },
  {
    key: "table",
    label: { zh: "查明细", en: "Inspect rows" },
    detail: { zh: "保留可核对的行级证据，并能保存成视图。", en: "Keep row-level evidence and save it as a view when needed." },
    technical: { zh: "明细表：分页明细、列数、排序、保存视图和行级证据。", en: "Table widget: paged detail, columns, sort, saved views, and row evidence." },
  },
  {
    key: "text",
    label: { zh: "读结论", en: "Read notes" },
    detail: { zh: "承接 Agent 或证据摘要，不替代数据。", en: "Carry Agent or evidence notes without replacing the data." },
    technical: { zh: "文本卡：结论说明、备注和 Agent 证据摘要。", en: "Text widget: narrative notes and Agent evidence summaries." },
  },
  {
    key: "slicer",
    label: { zh: "快速筛选", en: "Filter quickly" },
    detail: { zh: "用熟悉的筛选条件联动其他结果卡片。", en: "Use familiar filter choices to update other result cards." },
    technical: { zh: "切片器：列表、下拉、范围、多选和跨组件联动。", en: "Slicer widget: list, dropdown, range, multi-select, and cross-widget linking." },
  },
  {
    key: "relationship",
    label: { zh: "跨表分析", en: "Analyze across tables" },
    detail: { zh: "用推荐关系或已保存关系驱动跨表排行和明细。", en: "Use recommended or saved relationships for cross-table ranking and detail." },
    technical: { zh: "关系组件：relationship data mode、关系推荐、跨表排行和明细。", en: "Relationship widget: relationship data mode, recommendations, cross-table ranking, and detail." },
  },
  {
    key: "filter",
    label: { zh: "限定范围", en: "Limit scope" },
    detail: { zh: "全局筛选、局部筛选和切片联动都能清楚生效。", en: "Global filters, local filters, and slicers all apply predictably." },
    technical: { zh: "筛选：全局筛选、组件局部筛选、切片联动和清空。", en: "Filters: global filters, widget filters, slicer linking, and clear actions." },
  },
  {
    key: "drilldown",
    label: { zh: "追到原始记录", en: "Open source rows" },
    detail: { zh: "点击图形点位打开明细，并可先预览再保存视图。", en: "Click chart points for detail, then preview before saving a view." },
    technical: { zh: "下钻：点位筛选、受控明细查询、预览保存视图。", en: "Drilldown: point filters, controlled detail query, preview save view." },
  },
  {
    key: "copy-delete",
    label: { zh: "维护组件", en: "Maintain widgets" },
    detail: { zh: "复制和删除都保留预览与确认边界。", en: "Copy and delete keep preview and confirmation boundaries." },
    technical: { zh: "复制/删除：copy-widget、remove-widget、预演与确认。", en: "Copy/delete: copy-widget, remove-widget, preview, and confirmation." },
  },
  {
    key: "style",
    label: { zh: "调整呈现", en: "Tune presentation" },
    detail: { zh: "坐标轴、图例、标签、色板、小数位和展示形态集中调整。", en: "Tune axes, legend, labels, palette, decimals, and display mode together." },
    technical: { zh: "样式设置：坐标轴、图例、标签、色板、小数位和展示形态。", en: "Style settings: axes, legend, labels, palette, decimals, and display mode." },
  },
] as const;
