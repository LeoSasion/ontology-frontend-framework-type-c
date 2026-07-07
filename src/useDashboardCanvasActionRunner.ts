import { useState } from "react";

type PlanResult = Record<string, unknown>;

export function useDashboardCanvasActionRunner() {
  const [busy, setBusy] = useState<string | null>(null);
  const [widgetPlan, setWidgetPlan] = useState<PlanResult | null>(null);

  async function runVoidAction(label: string, action: () => Promise<void>) {
    setBusy(label);
    try {
      await action();
    } finally {
      setBusy(null);
    }
  }

  async function runPlanAction(label: string, action: () => Promise<PlanResult>) {
    setBusy(label);
    try {
      const result = await action();
      setWidgetPlan(result);
    } finally {
      setBusy(null);
    }
  }

  return {
    busy,
    widgetPlan,
    runVoidAction,
    runPlanAction,
  };
}
