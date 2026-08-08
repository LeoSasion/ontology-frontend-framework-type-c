import type { ReactNode } from "react";

type Receipt = {
  detail: string;
  nextStep: string;
  title: string;
  tone: string;
};

type OperationReceiptProps = {
  className?: string;
  receipt: Receipt;
  role?: "alert" | "status";
  summary: string;
  technical: ReactNode;
  testId: string;
  technicalTestId: string;
};

export function OperationReceipt({ className = "operationReceipt", receipt, role, summary, technical, testId, technicalTestId }: OperationReceiptProps) {
  return (
    <div aria-live={role === "status" ? "polite" : undefined} className={`${className} ${receipt.tone}`} data-testid={testId} role={role}>
      <div>
        <strong>{receipt.title}</strong>
        <span>{receipt.detail}</span>
        <small>{receipt.nextStep}</small>
      </div>
      <details data-testid={technicalTestId}>
        <summary>{summary}</summary>
        {technical}
      </details>
    </div>
  );
}
