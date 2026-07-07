import { biText } from "./components/Bilingual";
import type { SourceSwitchAnalysis } from "./dashboardCanvasSourceSwitchModel";

export type SourceSwitchViewItem = {
  key: string;
  label: string;
};

export type DashboardSourceSwitchViewModel = {
  changed: boolean;
  cleanupCount: number;
  showStaleList: boolean;
  impactItems: SourceSwitchViewItem[];
  staleItems: SourceSwitchViewItem[];
};

export function buildDashboardSourceSwitchViewModel(analysis: SourceSwitchAnalysis): DashboardSourceSwitchViewModel {
  const impactedWidgetCount = analysis.impactedWidgets.length;
  const filterCleanupCount = analysis.filterCleanup.length;
  const staleWidgetRefCount = analysis.staleWidgetRefs.length;
  return {
    changed: analysis.changed,
    cleanupCount: analysis.cleanupCount,
    showStaleList: analysis.changed && analysis.cleanupCount > 0,
    impactItems: [
      {
        key: "impacted-widgets",
        label: biText(`${impactedWidgetCount} 个组件跟随默认源`, `${impactedWidgetCount} widgets follow default source`),
      },
      {
        key: "filter-cleanup",
        label: biText(`${filterCleanupCount} 条全局筛选需清理`, `${filterCleanupCount} global filters to clean`),
      },
      {
        key: "stale-widget-refs",
        label: biText(`${staleWidgetRefCount} 个组件字段需替换`, `${staleWidgetRefCount} widget fields to replace`),
      },
    ],
    staleItems: [
      ...analysis.filterCleanup.slice(0, 3).map((filter) => ({
        key: `filter-${filter.id}`,
        label: `${biText("筛选", "Filter")}: ${filter.field}`,
      })),
      ...analysis.staleWidgetRefs.slice(0, 4).map((ref) => ({
        key: `${ref.widgetKey}-${ref.kind}-${ref.field}`,
        label: `${ref.title}: ${ref.field}`,
      })),
    ],
  };
}
