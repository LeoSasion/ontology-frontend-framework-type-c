import type { CheckedItem } from "../agentPanelModel";
import { Bilingual, biText } from "./Bilingual";

type LlmAuditItem = {
  key: string;
  label: string;
  tone: string;
  value: string;
};

type AgentEvidenceAuditPanelsProps = {
  checkedItems: CheckedItem[];
  fallbackReason?: string | null;
  llmAuditItems: LlmAuditItem[];
};

export function AgentEvidenceAuditPanels({ checkedItems, fallbackReason, llmAuditItems }: AgentEvidenceAuditPanelsProps) {
  return (
    <>
      <article className="agentCheckedPanel" data-testid="agent-checked-panel">
        <div>
          <span className="storyMode"><Bilingual zh="已检查" en="Checked" /></span>
          <h3><Bilingual zh="这次回答基于哪些工作区证据" en="What this response checked" /></h3>
        </div>
        <div className="agentCheckedGrid" data-testid="agent-checked-grid">
          {checkedItems.map((item) => (
            <div className={item.tone} data-testid={`agent-checked-${item.key}`} key={item.key}>
              <strong>{item.label}</strong>
              <span>{item.detail}</span>
            </div>
          ))}
        </div>
      </article>

      <article className="agentLlmAuditPanel" data-testid="agent-llm-audit-panel">
        <div className="agentLlmAuditLead">
          <span className="storyMode"><Bilingual zh="LLM 审计" en="LLM audit" /></span>
          <h3><Bilingual zh="模型只在当前工作区证据边界内工作" en="Model access stays inside the current evidence boundary" /></h3>
          <p>
            {fallbackReason
              ? biText("当前由本地规则和工作区证据生成回答；证据链、只读边界和确认流程仍然有效。", "This answer was generated from local rules and workspace evidence; evidence, read-only boundaries, and approvals still apply.")
              : biText("DeepSeek key 仅在本地服务端使用；前端只看到脱敏审计状态。", "The DeepSeek key is used only server-side; the frontend only sees a redacted audit state.")}
          </p>
          {fallbackReason ? (
            <details className="agentLlmAuditTechnical" data-testid="agent-llm-audit-technical">
              <summary>{biText("查看模型运行细节", "View model runtime detail")}</summary>
              <span>{fallbackReason}</span>
            </details>
          ) : null}
        </div>
        <div className="agentLlmAuditGrid" data-testid="agent-llm-audit-grid">
          {llmAuditItems.map((item) => (
            <div className={item.tone} data-testid={`agent-llm-audit-${item.key}`} key={item.key}>
              <strong>{item.label}</strong>
              <span>{item.value}</span>
            </div>
          ))}
        </div>
      </article>
    </>
  );
}
