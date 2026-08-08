import type { ReactNode } from "react";

type ObjectMissingStateProps = {
  badge: string;
  children: ReactNode;
  detail: string;
  testId: string;
  title: string;
};

export function ObjectMissingState({ badge, children, detail, testId, title }: ObjectMissingStateProps) {
  return (
    <section className="mainPanel objectMissingState" data-testid={testId} role="status">
      <span className="statusBadge warn">{badge}</span>
      <h2>{title}</h2>
      <p>{detail}</p>
      <div className="inlineActions">{children}</div>
    </section>
  );
}
