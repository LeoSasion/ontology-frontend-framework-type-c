import type { FieldConfig, ImportPreview, MetricDefinition, RelationshipRecord, SourceIntelligenceRunSummary, WorkbenchTable } from "./types";
import { biText } from "./components/Bilingual";

export type RecommendedPrimaryAction = "check-file" | "import-data" | "refresh-profile" | "draft-dashboard";

export type BeginnerPlanItem = {
  key: string;
  state: string;
  title: string;
  detail: string;
};

export type SourceAgentPrompt = {
  key: string;
  icon: "agent" | "evidence" | "dashboard";
  label: string;
  detail: string;
  prompt: string;
};

export type DashboardRecipeCard = {
  key: string;
  title: string;
  detail: string;
  state: string;
};

type BuildSourceWorkbenchGuidanceOptions = {
  busy: string | null;
  preview: ImportPreview;
  tables: WorkbenchTable[];
  fields: FieldConfig[];
  selectedFields: FieldConfig[];
  measureFields: FieldConfig[];
  groupFields: FieldConfig[];
  relationships: RelationshipRecord[];
  selectedMetrics: MetricDefinition[];
  latestSourceProfile?: SourceIntelligenceRunSummary;
  selectedTableKey: string;
};

export function buildSourceWorkbenchGuidance({
  busy,
  preview,
  tables,
  fields,
  selectedFields,
  measureFields,
  groupFields,
  relationships,
  selectedMetrics,
  latestSourceProfile,
  selectedTableKey,
}: BuildSourceWorkbenchGuidanceOptions) {
  const sourceProfileComplete = Boolean(latestSourceProfile?.fileCoverage?.complete);
  const previewReadable = Boolean(preview.ok && preview.profile.rowCount > 0 && preview.profile.columnCount > 0);
  const hasImportedTables = tables.length > 0;
  const sourceProfileRunning = busy === "source-intelligence";
  const sourceProfileRunningLabel = biText("正在只读扫描本地路径", "Scanning local paths read-only");
  const dashboardMeasureName = measureFields.find((field) => /sales|amount|revenue|销售|金额|实收|net/i.test(field.field_name))?.field_name ?? measureFields[0]?.field_name ?? "";
  const dashboardDimensionName = groupFields.find((field) => /channel|category|shop|渠道|分类|店铺|平台/i.test(field.field_name))?.field_name ?? groupFields[0]?.field_name ?? "";
  const dashboardTimeName = selectedFields.find((field) => field.role === "event_time" || /date|time|日期|时间/i.test(field.field_name))?.field_name ?? "";
  const dashboardRecipeReady = sourceProfileComplete && Boolean(dashboardMeasureName && dashboardDimensionName);
  const dashboardRecipeEvidenceCount = 3 + (latestSourceProfile ? 2 : 0) + (relationships.length ? 1 : 0) + Math.min(selectedMetrics.length, 2);
  const dashboardRecipeCards: DashboardRecipeCard[] = [
    {
      key: "metric",
      title: biText("核心读数", "KPI reading"),
      detail: dashboardMeasureName ? `sum(${dashboardMeasureName})` : biText("等待可聚合字段", "Waiting for a measure"),
      state: dashboardMeasureName ? biText("可生成", "Ready") : biText("缺指标", "Needs metric"),
    },
    {
      key: "ranking",
      title: biText("分类排行", "Ranking"),
      detail: dashboardDimensionName && dashboardMeasureName ? `${dashboardDimensionName} · ${dashboardMeasureName}` : biText("等待维度", "Waiting for dimension"),
      state: dashboardDimensionName ? biText("可下钻", "Drillable") : biText("需确认", "Needs review"),
    },
    {
      key: "trend",
      title: biText("趋势变化", "Trend"),
      detail: dashboardTimeName ? `${dashboardTimeName} · ${dashboardMeasureName}` : biText("未找到时间字段", "No time field yet"),
      state: dashboardTimeName ? biText("可生成", "Ready") : biText("可跳过", "Optional"),
    },
    {
      key: "detail",
      title: biText("明细核查", "Detail audit"),
      detail: `${Math.min(selectedFields.length || 6, 8)} ${biText("列", "columns")}`,
      state: selectedFields.length ? biText("可追溯", "Traceable") : biText("等待字段", "Waiting"),
    },
  ];
  const recommendedPrimaryAction: RecommendedPrimaryAction = !previewReadable
    ? "check-file"
    : !hasImportedTables
      ? "import-data"
      : !sourceProfileComplete
        ? "refresh-profile"
        : "draft-dashboard";
  const beginnerPlan: BeginnerPlanItem[] = [
    {
      key: "file",
      state: previewReadable ? biText("可读取", "Readable") : biText("待检查", "Check needed"),
      title: biText("文件预检", "File preflight"),
      detail: previewReadable
        ? `${preview.profile.rowCount.toLocaleString()} ${biText("行", "rows")} · ${preview.profile.columnCount} ${biText("字段", "fields")}`
        : biText("先确认文件能被读取，再考虑写入。", "Confirm the file can be read before any write."),
    },
    {
      key: "workspace",
      state: hasImportedTables ? biText("已入库", "In workspace") : biText("需确认", "Needs confirmation"),
      title: biText("工作区数据", "Workspace data"),
      detail: hasImportedTables
        ? `${tables.length} ${biText("张表", "tables")} · ${fields.length} ${biText("个字段", "fields")}`
        : biText("导入是确认动作，不会在预检时静默写入。", "Import is a confirmed action; preflight never writes silently."),
    },
    {
      key: "profile",
      state: sourceProfileComplete ? biText("证据完整", "Evidence ready") : biText("建议更新", "Refresh suggested"),
      title: biText("证据摘要", "Evidence profile"),
      detail: latestSourceProfile
        ? `${latestSourceProfile.source_count} ${biText("文件", "files")} · ${latestSourceProfile.relationship_count} ${biText("关系", "relations")} · ${latestSourceProfile.metric_sql_executable_count}/${latestSourceProfile.metric_sql_plan_count} ${biText("可执行问题", "answerable questions")}`
        : biText("导入或选择本地路径后生成真实证据摘要。", "Import or choose local paths to build a real evidence summary."),
    },
  ];
  const sourceAgentPrompts: SourceAgentPrompt[] = [
    {
      key: "can-answer",
      icon: "agent",
      label: biText("这份数据能回答什么", "What can this data answer"),
      detail: biText("先读证据，不创建草案", "Read evidence, no draft"),
      prompt: biText(
        `基于 ${selectedTableKey} 告诉我当前能回答哪些经营问题，列出证据、字段和缺口，不要创建任何草案`,
        `Using ${selectedTableKey}, tell me what business questions can be answered now, list evidence, fields, and gaps, and do not create any draft`,
      ),
    },
    {
      key: "find-gaps",
      icon: "evidence",
      label: biText("检查还缺什么", "Find missing pieces"),
      detail: biText("按字段、关系、指标说清楚", "Fields, relationships, metrics"),
      prompt: biText(
        `检查 ${selectedTableKey} 距离可用经营看板还缺什么字段、关系和指标，只给下一步建议`,
        `Check what fields, relationships, and metrics ${selectedTableKey} still needs for a usable business dashboard, and only give next-step recommendations`,
      ),
    },
    {
      key: "draft-dashboard",
      icon: "dashboard",
      label: biText("起草看板方案", "Draft dashboard plan"),
      detail: biText("草案确认制，不直接写入", "Draft approval, no direct write"),
      prompt: biText(
        `基于 ${selectedTableKey} 起草一个经营看板方案，说明会用哪些组件和证据，先不要直接写入`,
        `Draft a business dashboard plan from ${selectedTableKey}, explain widgets and evidence, and do not write directly`,
      ),
    },
  ];

  return {
    sourceProfileComplete,
    previewReadable,
    sourceProfileRunning,
    sourceProfileRunningLabel,
    dashboardMeasureName,
    dashboardDimensionName,
    dashboardTimeName,
    dashboardRecipeReady,
    dashboardRecipeEvidenceCount,
    dashboardRecipeCards,
    recommendedPrimaryAction,
    beginnerPlan,
    sourceAgentPrompts,
  };
}
