import type { AgentAskResult, WorkbenchPayload, WorkspaceStatus } from "./types";
import type { AnalysisJob } from "./typesJobs";
import type { AppSection } from "./appSections";
import { biText } from "./components/Bilingual";
import { buildWorkspaceJourney, type WorkspaceJourneyModel } from "./workspaceJourneyModel";

export type TrustedAnswerStage = "connect" | "understand" | "recover" | "ask" | "clarify" | "review" | "confirm";
export type TrustedAnswerActionKey =
  | "connect-data"
  | "wait-for-understanding"
  | "retry-understanding"
  | "ask-question"
  | "answer-clarification"
  | "review-answer"
  | "review-draft";

export type TrustedAnswerRecommendation = {
  stage: TrustedAnswerStage;
  actionKey: TrustedAnswerActionKey;
  label: string;
  detail: string;
  target: AppSection;
  enabled: boolean;
  reasonCode: string;
};

export type TrustedAnswerCoordinator = {
  schema: "aibi-first-trusted-answer/v1";
  journey: WorkspaceJourneyModel;
  recommendation: TrustedAnswerRecommendation;
};

function activeClarification(agent: AgentAskResult) {
  return Boolean(
    agent.businessUnderstanding?.clarification?.active
    || agent.businessUnderstanding?.activeClarification
    || agent.clarification?.required,
  );
}

export function buildTrustedAnswerCoordinator(options: {
  status: WorkspaceStatus;
  workbench: WorkbenchPayload;
  agent: AgentAskResult;
  sourceIntelligenceJobs?: AnalysisJob[];
  pendingDraftCount?: number;
}): TrustedAnswerCoordinator {
  const journey = buildWorkspaceJourney(options);
  let recommendation: TrustedAnswerRecommendation;

  if (!journey.hasData) {
    recommendation = {
      stage: "connect", actionKey: "connect-data",
      label: biText("接入一份真实数据", "Connect a real dataset"),
      detail: biText("先预检来源，再由你确认是否写入。", "Preview the source first, then confirm any write."),
      target: "sources", enabled: true, reasonCode: "workspace-empty",
    };
  } else if (journey.activeJob) {
    recommendation = {
      stage: "understand", actionKey: "wait-for-understanding",
      label: biText("等待系统完成数据理解", "Wait for data understanding"),
      detail: biText("任务在后台持久运行，可以安全切换页面。", "The durable task continues in the background; you may switch pages."),
      target: "sources", enabled: false, reasonCode: "source-intelligence-active",
    };
  } else if (!journey.hasCurrentEvidence) {
    const recovery = journey.understanding.state === "failed" || journey.understanding.state === "stale";
    recommendation = {
      stage: recovery ? "recover" : "understand", actionKey: "retry-understanding",
      label: recovery
        ? biText("修复并重新理解数据", "Recover and understand the data again")
        : biText("生成可核对的数据理解", "Build reviewable data understanding"),
      detail: recovery
        ? biText("旧证据不会被继续使用；重试不会改写原始数据。", "Stale evidence will not be reused; retrying does not alter source data.")
        : biText("系统会检查字段、关系和可执行口径。", "The system checks fields, relationships, and executable definitions."),
      target: "sources", enabled: true,
      reasonCode: recovery ? `understanding-${journey.understanding.state}` : "evidence-missing",
    };
  } else if (journey.hasPendingDraft) {
    recommendation = {
      stage: "confirm", actionKey: "review-draft",
      label: biText("核对等待确认的修改", "Review the pending change"),
      detail: biText("确认前不会发生真实写入。", "No real write occurs before confirmation."),
      target: "agent", enabled: true, reasonCode: "write-confirmation-pending",
    };
  } else if (activeClarification(options.agent)) {
    recommendation = {
      stage: "clarify", actionKey: "answer-clarification",
      label: biText("回答一个最高价值澄清", "Answer one highest-value clarification"),
      detail: biText("只补充当前计算缺少的条件，不重新开始。", "Provide only the missing condition; the analysis context is preserved."),
      target: "agent", enabled: true, reasonCode: "clarification-required",
    };
  } else if (journey.hasAnswer) {
    recommendation = {
      stage: "review", actionKey: "review-answer",
      label: journey.resultState === "blocked"
        ? biText("查看被阻断的分析", "Review the blocked analysis")
        : biText("核对首个可信答案", "Review the first trusted answer"),
      detail: journey.resultState === "blocked"
        ? biText("系统没有发布未经证实的数字。", "The system did not publish an unverified number.")
        : biText("核对结论、口径、来源和查询回执。", "Review the conclusion, definition, sources, and query receipt."),
      target: "agent", enabled: true, reasonCode: `answer-${journey.resultState}`,
    };
  } else {
    recommendation = {
      stage: "ask", actionKey: "ask-question",
      label: biText("提出第一个业务问题", "Ask the first business question"),
      detail: biText("系统会匹配证据；不明确时只问一个关键问题。", "The system matches evidence and asks only one key question when needed."),
      target: "agent", enabled: true, reasonCode: "ready-for-question",
    };
  }

  return { schema: "aibi-first-trusted-answer/v1", journey, recommendation };
}
