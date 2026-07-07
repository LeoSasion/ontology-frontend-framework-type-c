export interface DashboardWidget {
  widget_key: string;
  dashboard_key: string;
  widget_type: "metric" | "bar" | "line" | "table" | string;
  title: string;
  table_key: string;
  config: Record<string, unknown>;
  sort_order: number;
}

export interface DashboardFilterRule {
  id: string;
  field: string;
  operator: "contains" | "equals" | "in" | "between" | "notEquals" | "gt" | "gte" | "lt" | "lte" | "empty" | "notEmpty" | string;
  value: string;
  enabled: boolean;
  scope?: string;
  createdAt?: string;
  updatedAt?: string;
}

export interface DashboardPage {
  dashboard_key: string;
  name: string;
  workspace_id: string;
  default_table_key: string;
  created_by: string;
  agent_managed: number;
  layout: Record<string, unknown>;
  widgets: DashboardWidget[];
}

export interface DashboardPayload {
  ok: boolean;
  dashboards: DashboardPage[];
}

export interface NavigationModule {
  moduleKey: string;
  name: string;
  type: "table" | "view" | "dashboard" | string;
  tableKey?: string;
  dashboardKey?: string;
  sort: number;
  createdBy?: "manual" | "agent" | "system" | string;
  agentManaged?: boolean;
  enabled?: boolean;
  createdAt?: string;
  updatedAt?: string;
}

export interface DashboardFilterPayload {
  ok: boolean;
  dashboard?: {
    dashboard_key: string;
    name: string;
    default_table_key?: string;
  };
  filters?: DashboardFilterRule[];
  availableFields?: Array<{
    field_name: string;
    role: string;
    usage: string;
    confidence: number;
  }>;
  operators?: string[];
  dryRun?: boolean;
  requiresConfirmation?: boolean;
  proposed?: DashboardFilterRule;
  current?: DashboardFilterRule | null;
  removed?: DashboardFilterRule;
  filtersAfter?: DashboardFilterRule[];
  confirmed?: boolean;
  operation?: string;
}
