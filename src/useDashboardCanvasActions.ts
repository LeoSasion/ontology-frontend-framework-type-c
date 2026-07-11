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

function singleChartAgentPrompt(userPrompt: string, dashboard: DashboardPage, fields: FieldConfig[]) {
  const normalizedPrompt = userPrompt.toLocaleLowerCase();
  const matchedField = fields.find((field) => {
    const fieldName = field.field_name.trim().toLocaleLowerCase();
    return fieldName.length > 1 && normalizedPrompt.includes(fieldName);
  });
  const tableKey = matchedField?.table_key || dashboard.default_table_key;
  const tableScope = tableKey ? `基于 ${tableKey}，` : "基于当前数据，";
  return `${tableScope}用户想看「${userPrompt}」。起草一个仅包含一个图表的可确认看板；优先选择最符合字段证据的指标卡、折线图、柱状图或表格，说明字段、口径和证据，确认前不要写入。`;
}

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
    const routedPrompt = label === "dashboard-task-explain"
      ? singleChartAgentPrompt(prompt, dashboard, fields)
      : prompt;
    await runVoidAction(label, () => onAsk(routedPrompt));
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
