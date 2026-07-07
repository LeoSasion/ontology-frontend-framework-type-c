import type {
  DashboardFilterRule,
  DashboardPage,
  DashboardWidget,
  FieldConfig,
  RelationshipRecommendation,
} from "./types";
import type {
  BusinessDashboardOptions,
  DashboardFilterOperationOptions,
  DashboardModuleSaveOptions,
  DashboardOperationOptions,
  DashboardWidgetOperationOptions,
  RelationshipSaveOptions,
} from "./dashboardCanvasContracts";
import { buildRelationshipSavePayload } from "./dashboardCanvasRelationshipModel";
import { buildSourceSwitchModulePayload } from "./dashboardCanvasSourceSwitchModel";
import {
  buildDashboardModulePayload,
  buildWidgetSettingsPayload,
  type DashboardCanvasWidthMode,
  type WidgetDraft,
} from "./dashboardCanvasWidgetModel";
import { useDashboardCanvasActionRunner } from "./useDashboardCanvasActionRunner";

type DashboardCanvasActionsOptions = {
  canvasWidthMode: DashboardCanvasWidthMode;
  dashboard: DashboardPage;
  draftName: string;
  fields: FieldConfig[];
  filters: DashboardFilterRule[];
  onAsk: (prompt: string) => Promise<void>;
  onBusinessDashboardOperation: (options: BusinessDashboardOptions) => Promise<Record<string, unknown>>;
  onDashboardFilterOperation: (options: DashboardFilterOperationOptions) => Promise<void>;
  onDashboardModulesSave: (options: DashboardModuleSaveOptions) => Promise<Record<string, unknown>>;
  onDashboardOperation: (options: DashboardOperationOptions) => Promise<void>;
  onDashboardWidgetOperation: (options: DashboardWidgetOperationOptions) => Promise<Record<string, unknown>>;
  onRelationshipSave: (options: RelationshipSaveOptions) => Promise<Record<string, unknown>>;
  selectedWidgetKey?: string;
  sourceSwitchTableKey: string;
  widgetDraft: WidgetDraft;
  widgets: DashboardWidget[];
};

export function useDashboardCanvasActions({
  canvasWidthMode,
  dashboard,
  draftName,
  fields,
  filters,
  onAsk,
  onBusinessDashboardOperation,
  onDashboardFilterOperation,
  onDashboardModulesSave,
  onDashboardOperation,
  onDashboardWidgetOperation,
  onRelationshipSave,
  selectedWidgetKey,
  sourceSwitchTableKey,
  widgetDraft,
  widgets,
}: DashboardCanvasActionsOptions) {
  const { busy, widgetPlan, runVoidAction, runPlanAction } = useDashboardCanvasActionRunner();

  async function runDashboardOperation(label: string, options: DashboardOperationOptions) {
    await runVoidAction(label, () => onDashboardOperation(options));
  }

  async function runFilterOperation(label: string, options: DashboardFilterOperationOptions) {
    await runVoidAction(label, () => onDashboardFilterOperation(options));
  }

  async function runWidgetOperation(label: string, options: DashboardWidgetOperationOptions) {
    await runPlanAction(label, () => onDashboardWidgetOperation(options));
  }

  function dashboardModulePayload(confirm: boolean) {
    return buildDashboardModulePayload({
      dashboardKey: dashboard.dashboard_key,
      dashboardName: draftName || dashboard.name,
      defaultTableKey: dashboard.default_table_key,
      canvasWidthMode,
      widgets,
      filters,
      confirm,
    });
  }

  function sourceSwitchModulePayload(confirm: boolean) {
    return buildSourceSwitchModulePayload({
      dashboardKey: dashboard.dashboard_key,
      dashboardName: draftName || dashboard.name,
      defaultTableKey: dashboard.default_table_key,
      sourceSwitchTableKey,
      canvasWidthMode,
      widgets,
      filters,
      fields,
      confirm,
    });
  }

  async function runModuleSave(confirm: boolean) {
    const label = confirm ? "dashboard-modules-confirm" : "dashboard-modules-dry-run";
    await runPlanAction(label, () => onDashboardModulesSave(dashboardModulePayload(confirm)));
  }

  async function runSourceSwitch(confirm: boolean) {
    const label = confirm ? "dashboard-source-switch-confirm" : "dashboard-source-switch-preview";
    await runPlanAction(label, () => onDashboardModulesSave(sourceSwitchModulePayload(confirm)));
  }

  async function runBusinessTemplate(label: string, options: BusinessDashboardOptions) {
    await runPlanAction(label, () => onBusinessDashboardOperation(options));
  }

  async function runDashboardAsk(label: string, prompt: string) {
    await runVoidAction(label, () => onAsk(prompt));
  }

  async function runRelationshipSave(label: string, recommendation: RelationshipRecommendation, confirm: boolean) {
    const payload = buildRelationshipSavePayload(recommendation, confirm);
    if (!payload) return;
    await runPlanAction(label, () => onRelationshipSave(payload));
  }

  const widgetSettingsPayload = (confirm: boolean) => buildWidgetSettingsPayload({
    selectedWidgetKey,
    widgetDraft,
    confirm,
  });

  return {
    busy,
    runBusinessTemplate,
    runDashboardAsk,
    runDashboardOperation,
    runFilterOperation,
    runModuleSave,
    runRelationshipSave,
    runSourceSwitch,
    runWidgetOperation,
    widgetPlan,
    widgetSettingsPayload,
  };
}
