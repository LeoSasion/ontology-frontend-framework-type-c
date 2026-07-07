import type { SavedView } from "../types";
import type { ViewAgentPrompt } from "../viewWorkspaceModel";
import { biText } from "./Bilingual";
import { AgentPromptGrid } from "./AgentPromptGrid";

type ViewAgentTaskStripProps = {
  activeView?: SavedView;
  busy: string | null;
  onAsk: (prompt: string) => Promise<void>;
  runBusy: (label: string, action: () => Promise<void>) => Promise<void>;
  viewAgentPrompts: ViewAgentPrompt[];
};

export function ViewAgentTaskStrip({
  activeView,
  busy,
  onAsk,
  runBusy,
  viewAgentPrompts,
}: ViewAgentTaskStripProps) {
  return (
    <div className="viewAgentTaskStrip" data-testid="view-agent-task-strip">
      <div className="viewAgentLead">
        <strong>{biText("不用导出表格，直接问当前视图", "Ask this view without exporting")}</strong>
        <span>
          {biText(
            "Agent 会沿用当前视图、搜索、分页和证据口径；新增组件或改看板时仍先生成待确认修改。",
            "The Agent keeps the current view, search, page, and evidence scope. New widgets or dashboard edits still become pending changes first.",
          )}
        </span>
      </div>
      <AgentPromptGrid
        busy={busy}
        disabled={!activeView}
        itemTestIdPrefix="view-agent-prompt"
        items={viewAgentPrompts}
        onAsk={onAsk}
        prefix="view-agent"
        runBusy={runBusy}
        testId="view-agent-prompt-grid"
      />
    </div>
  );
}
