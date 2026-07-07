import type { QueryResult, SourceIntelligenceRunSummary } from "./types";
import { biText } from "./components/Bilingual";

export type DashboardSummaryRow = {
  label: string;
  value: number;
};

export type DashboardSummaryModel = {
  queryRows: QueryResult["rows"];
  rankedRows: DashboardSummaryRow[];
  topRow: DashboardSummaryRow | null;
  totalValue: number;
  currentGroupLabel: string;
  currentScopeDetail: string;
  evidenceCoverageValue: string;
  evidenceCoverageDetail: string;
  totalDetail: string;
};

export function buildDashboardSummaryModel({
  query,
  defaultTableKey,
  latestRun,
}: {
  query: QueryResult;
  defaultTableKey: string;
  latestRun?: SourceIntelligenceRunSummary | null;
}): DashboardSummaryModel {
  const queryRows = Array.isArray(query.rows) ? query.rows : [];
  const rankedRows = queryRows
    .map((row) => ({ label: String(row.label ?? "value"), value: Number(row.value) || 0 }))
    .sort((left, right) => right.value - left.value);
  const topRow = rankedRows[0] ?? null;
  const measureLabel = query.query?.measure ?? "value";

  return {
    queryRows,
    rankedRows,
    topRow,
    totalValue: rankedRows.reduce((sum, row) => sum + row.value, 0),
    currentGroupLabel: query.query?.group ?? biText("推荐分组", "recommended group"),
    currentScopeDetail: `${query.query?.table ?? defaultTableKey} · ${measureLabel}`,
    evidenceCoverageValue: latestRun ? `${latestRun.source_count}/${latestRun.table_count}` : "-",
    evidenceCoverageDetail: latestRun
      ? biText(
          `${latestRun.metric_sql_executable_count} 个可执行指标`,
          `${latestRun.metric_sql_executable_count} executable metrics`,
        )
      : biText("等待画像", "waiting for profile"),
    totalDetail: `${query.query?.aggregation ?? biText("聚合", "aggregation")}(${measureLabel})`,
  };
}
