import type { AgentAskResult, EvidenceFocus, WorkbenchPayload } from "./types";
import { latestUsableSourceIntelligenceRun } from "./workspaceFlowModel";

export type ProductSignal = {
  key: string;
  tone: "ok" | "warn" | "info" | "muted";
  title: string;
  detail: string;
  value?: string;
};

export type EvidenceNarrative = {
  title: string;
  summary: string;
  calculationSteps: ProductSignal[];
  trustChecks: ProductSignal[];
};

function latestSourceRun(workbench: WorkbenchPayload) {
  return latestUsableSourceIntelligenceRun(
    Array.isArray(workbench.sourceIntelligenceRuns) ? workbench.sourceIntelligenceRuns : [],
  );
}

function sourceRunFromRefs(refs: string[] | undefined, workbench: WorkbenchPayload) {
  const key = refs?.find((ref) => ref.startsWith("source-intelligence:"))?.replace("source-intelligence:", "");
  return key ? workbench.sourceIntelligenceRuns.find((run) => run.run_key === key) : undefined;
}

export function buildEvidenceNarrative(
  focus: EvidenceFocus | null | undefined,
  agent: AgentAskResult,
  workbench: WorkbenchPayload,
): EvidenceNarrative {
  const run = sourceRunFromRefs(focus?.refs, workbench) ?? latestSourceRun(workbench);
  const refs = focus?.refs?.length ? focus.refs : agent.ontology.evidenceFiles;
  return {
    title: focus?.title || agent.answerCard?.title?.zh || "当前数字说明书",
    summary: run
      ? `这组证据来自 ${run.source_count} 个源文件，${run.metric_sql_executable_count}/${run.metric_sql_plan_count} 个指标问题可执行。`
      : "尚未生成完整证据摘要，当前只能解释已知引用和动作边界。",
    calculationSteps: [
      { key: "source", tone: run ? "ok" : "warn", title: "1. 定位来源", detail: run ? run.label : "等待 Source Intelligence 运行" },
      { key: "metric", tone: run?.metric_sql_executable_count ? "ok" : "info", title: "2. 匹配口径", detail: run ? `${run.metric_sql_executable_count} 条可执行指标 SQL` : "需要字段语义和指标定义" },
      { key: "query", tone: refs.includes("query-runtime") ? "ok" : "info", title: "3. 运行查询", detail: refs.includes("query-runtime") ? "已有查询回执" : "当前证据可继续补查询回执" },
      { key: "action", tone: "ok", title: "4. 写入边界", detail: "导入、看板、关系和公式写入前均需确认" },
    ],
    trustChecks: [
      { key: "coverage", tone: run?.fileCoverage?.complete ? "ok" : "warn", title: "覆盖", detail: run?.fileCoverage?.complete ? "源文件覆盖完整" : "覆盖需复核或重新画像" },
      { key: "relationship", tone: (run?.relationship_count ?? 0) > 0 ? "ok" : "info", title: "关系", detail: `${run?.relationship_count ?? 0} 条关系证据` },
      { key: "refs", tone: refs.length ? "ok" : "muted", title: "引用", detail: `${refs.length} 条证据引用` },
    ],
  };
}
