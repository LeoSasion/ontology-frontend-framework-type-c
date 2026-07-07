import { Bilingual, biText } from "./Bilingual";

export type AgentCanAnswerSuggestion = {
  key: string;
  label: string;
  prompt: { zh: string; en: string };
  detail: string;
};

type AgentCanAnswerPanelProps = {
  executableMetricCount?: number;
  isAsking: boolean;
  suggestions: AgentCanAnswerSuggestion[];
  onAskSuggestion: (prompt: { zh: string; en: string }) => void;
};

export function AgentCanAnswerPanel({ executableMetricCount, isAsking, suggestions, onAskSuggestion }: AgentCanAnswerPanelProps) {
  return (
    <article className="agentCanAnswerPanel" data-testid="agent-can-answer-panel">
      <div className="agentCanAnswerHeader">
        <div>
          <span className="storyMode"><Bilingual zh="现在可以问" en="Can answer now" /></span>
          <h3><Bilingual zh="从证据出发，而不是从配置出发" en="Start from evidence, not configuration" /></h3>
        </div>
        <span>
          {typeof executableMetricCount === "number"
            ? biText(`${executableMetricCount} 个可执行指标`, `${executableMetricCount} executable metrics`)
            : biText("等待画像", "Waiting for profile")}
        </span>
      </div>
      <div className="agentCanAnswerGrid" data-testid="agent-can-answer-suggestions">
        {suggestions.slice(0, 4).map((item) => (
          <button
            data-testid={`agent-can-answer-${item.key}`}
            disabled={isAsking}
            key={item.key}
            onClick={() => onAskSuggestion(item.prompt)}
            type="button"
          >
            <strong>{item.label}</strong>
            <span>{biText(item.prompt.zh, item.prompt.en)}</span>
            <small>{item.detail}</small>
          </button>
        ))}
      </div>
    </article>
  );
}
