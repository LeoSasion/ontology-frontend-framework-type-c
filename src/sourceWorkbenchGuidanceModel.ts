import type { FieldConfig, ImportPreview, SourceIntelligenceRunSummary, WorkbenchTable } from "./types";
import { biText } from "./components/Bilingual";

export type RecommendedPrimaryAction = "check-file" | "import-data" | "refresh-profile" | "start-analysis";

export type BeginnerPlanItem = {
  key: string;
  state: string;
  title: string;
  detail: string;
};

type BuildSourceWorkbenchGuidanceOptions = {
  busy: string | null;
  preview: ImportPreview;
  tables: WorkbenchTable[];
  fields: FieldConfig[];
  latestSourceProfile?: SourceIntelligenceRunSummary;
};

export function buildSourceWorkbenchGuidance({
  busy,
  preview,
  tables,
  fields,
  latestSourceProfile,
}: BuildSourceWorkbenchGuidanceOptions) {
  const sourceProfileAvailable = Boolean(latestSourceProfile);
  const sourceProfileComplete = Boolean(latestSourceProfile?.fileCoverage?.complete);
  const previewReadable = Boolean(preview.ok && preview.profile.rowCount > 0 && preview.profile.columnCount > 0);
  const hasImportedTables = tables.length > 0;
  const sourceProfileRunning = busy === "source-intelligence";
  const sourceProfileRunningLabel = biText("正在只读扫描本地路径", "Scanning local paths read-only");
  const recommendedPrimaryAction: RecommendedPrimaryAction = hasImportedTables
    ? sourceProfileAvailable
      ? "start-analysis"
      : "refresh-profile"
    : previewReadable
      ? "import-data"
      : "check-file";
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
      state: sourceProfileComplete
        ? biText("证据完整", "Evidence complete")
        : sourceProfileAvailable
          ? biText("可分析 · 建议更新", "Ready · refresh suggested")
          : biText("尚需准备", "Preparation needed"),
      title: biText("证据摘要", "Evidence profile"),
      detail: latestSourceProfile
        ? `${latestSourceProfile.source_count} ${biText("文件", "files")} · ${latestSourceProfile.relationship_count} ${biText("关系", "relations")} · ${latestSourceProfile.metric_sql_executable_count}/${latestSourceProfile.metric_sql_plan_count} ${biText("可执行问题", "answerable questions")}`
        : biText("导入或选择本地路径后生成真实证据摘要。", "Import or choose local paths to build a real evidence summary."),
    },
  ];
  return {
    sourceProfileAvailable,
    sourceProfileComplete,
    sourceProfileRunning,
    sourceProfileRunningLabel,
    recommendedPrimaryAction,
    beginnerPlan,
  };
}
