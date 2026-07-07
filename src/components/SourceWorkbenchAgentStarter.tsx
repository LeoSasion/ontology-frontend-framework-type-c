import { biText } from "./Bilingual";
import { AgentPromptGrid, type AgentPromptGridItem } from "./AgentPromptGrid";

export type SourceAgentPrompt = AgentPromptGridItem;

type SourceWorkbenchAgentStarterProps = {
  busy: string | null;
  sourceProfileComplete: boolean;
  sourceAgentPrompts: SourceAgentPrompt[];
  runBusy: (label: string, action: () => Promise<void>) => Promise<void>;
  onAsk: (prompt: string) => Promise<void>;
};

export function SourceWorkbenchAgentStarter({
  busy,
  sourceProfileComplete,
  sourceAgentPrompts,
  runBusy,
  onAsk,
}: SourceWorkbenchAgentStarterProps) {
  return (
    <div className="sourceAgentStarter" data-testid="source-agent-question-starter">
      <div className="sourceAgentStarterLead">
        <strong>{biText("不会问也没关系，直接点业务问题", "No need to know what to ask")}</strong>
        <span>
          {sourceProfileComplete
            ? biText("Agent 会基于当前工作区、画像和证据回答；涉及写入时仍走草案确认。", "The Agent answers from this workspace, profile, and evidence; writes still go through draft approval.")
            : biText("还没有完整画像时，先让 Agent 说明缺口和下一步。", "Without a complete profile, ask the Agent to explain gaps and next steps first.")}
        </span>
      </div>
      <AgentPromptGrid
        busy={busy}
        itemTestIdPrefix="source-agent-prompt"
        items={sourceAgentPrompts}
        onAsk={onAsk}
        prefix="source-agent"
        runBusy={runBusy}
        testId="source-agent-prompt-grid"
      />
    </div>
  );
}
