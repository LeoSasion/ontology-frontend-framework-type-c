import type { WorkspaceStatus } from "./types";
import { biText } from "./components/Bilingual";

export type ProductReadinessKey = "service-ready" | "needs-data" | "needs-evidence" | "ready-to-analyze" | "pending-confirmation";

export type ProductReadiness = {
  key: ProductReadinessKey;
  label: string;
  tone: "ok" | "warn" | "neutral";
};

export function buildProductReadiness(status: WorkspaceStatus, overrides: Partial<{ hasData: boolean; hasEvidence: boolean; hasPendingDraft: boolean }> = {}): ProductReadiness {
  const hasData = overrides.hasData ?? status.counts.tables > 0;
  const hasEvidence = overrides.hasEvidence ?? Number(status.counts.sourceIntelligenceRuns || 0) > 0;
  const hasPendingDraft = overrides.hasPendingDraft ?? status.counts.actionDrafts > 0;
  if (!status.health.ok) return { key: "service-ready", label: biText("服务待检查", "Service needs review"), tone: "warn" };
  if (hasPendingDraft) return { key: "pending-confirmation", label: biText("待确认", "Pending approval"), tone: "warn" };
  if (!hasData) return { key: "needs-data", label: biText("待接入", "Connect data"), tone: "neutral" };
  if (!hasEvidence) return { key: "needs-evidence", label: biText("待生成证据", "Create evidence"), tone: "neutral" };
  return { key: "ready-to-analyze", label: biText("可分析", "Ready to analyze"), tone: "ok" };
}
