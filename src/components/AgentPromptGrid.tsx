import { Icon } from "./Icons";

export type AgentPromptGridItem = {
  key: string;
  icon: "agent" | "evidence" | "dashboard";
  label: string;
  detail: string;
  prompt: string;
};

type AgentPromptGridProps<TPrompt extends AgentPromptGridItem> = {
  busy: string | null;
  disabled?: boolean;
  itemTestIdPrefix: string;
  items: TPrompt[];
  prefix: string;
  testId: string;
  onAsk: (prompt: string) => Promise<void>;
  runBusy: (label: string, action: () => Promise<void>) => Promise<void>;
};

export function AgentPromptGrid<TPrompt extends AgentPromptGridItem>({
  busy,
  disabled = false,
  itemTestIdPrefix,
  items,
  prefix,
  testId,
  onAsk,
  runBusy,
}: AgentPromptGridProps<TPrompt>) {
  return (
    <div className="agentPromptGrid" data-testid={testId}>
      {items.map((item) => (
        <button
          data-testid={`${itemTestIdPrefix}-${item.key}`}
          disabled={disabled || busy === `${prefix}-${item.key}`}
          key={item.key}
          onClick={() => runBusy(`${prefix}-${item.key}`, () => onAsk(item.prompt))}
          type="button"
        >
          <Icon name={item.icon} />
          <span>
            <strong>{item.label}</strong>
            <small>{item.detail}</small>
          </span>
        </button>
      ))}
    </div>
  );
}
