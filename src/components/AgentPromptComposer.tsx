import type { Dispatch, SetStateAction } from "react";
import { biText } from "./Bilingual";
import { Icon } from "./Icons";

type AgentPromptComposerProps = {
  isAsking: boolean;
  prompt: string;
  setPrompt: Dispatch<SetStateAction<string>>;
  setPromptTouched: Dispatch<SetStateAction<boolean>>;
  submit: () => Promise<void>;
};

export function AgentPromptComposer({ isAsking, prompt, setPrompt, setPromptTouched, submit }: AgentPromptComposerProps) {
  return (
    <div className="agentComposer" data-testid="agent-prompt-composer">
      <textarea
        aria-label={biText("Agent 提问", "Agent prompt")}
        placeholder={biText("例如：按月份比较各产品的收入变化，并标出异常月份", "For example: compare monthly revenue by product and flag unusual months")}
        value={prompt}
        onChange={(event) => {
          setPromptTouched(true);
          setPrompt(event.target.value);
        }}
      />
      <button className="primaryButton" disabled={isAsking || !prompt.trim()} onClick={() => void submit()} type="button">
        <Icon name="agent" />
        {isAsking ? biText("规划中", "Planning") : biText("提问", "Ask")}
      </button>
      <span aria-live="polite" className="srOnly" role="status">
        {isAsking ? biText("AI 正在生成只读回答或待确认草案", "AI is preparing a read-only answer or approval draft") : ""}
      </span>
    </div>
  );
}
