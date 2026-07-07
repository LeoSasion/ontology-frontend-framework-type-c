import type { FieldConfig, NavigationModule, WorkbenchTable } from "./types";

export type FieldDraft = Pick<FieldConfig, "role" | "usage">;
export type FieldDrafts = Record<string, FieldDraft>;
export type NavigationOperation = "rename" | "move" | "hide" | "show";

export type NavigationOperationOptions = {
  moduleKey: string;
  op: NavigationOperation;
  name?: string;
  sort?: number;
  confirm?: boolean;
};

export function fieldDraftKey(field: Pick<FieldConfig, "table_key" | "field_name">) {
  return `${field.table_key}.${field.field_name}`;
}

export function readFieldDraft(fieldDrafts: FieldDrafts, field: FieldConfig): FieldDraft {
  return fieldDrafts[fieldDraftKey(field)] ?? { role: field.role, usage: field.usage };
}

export function applyFieldDraftPatch(fieldDrafts: FieldDrafts, field: FieldConfig, patch: Partial<FieldDraft>): FieldDrafts {
  return {
    ...fieldDrafts,
    [fieldDraftKey(field)]: { ...readFieldDraft(fieldDrafts, field), ...patch },
  };
}

export function managedSourceDisplayName(tables: WorkbenchTable[], tableKey: string) {
  return tables.find((item) => item.table_key === tableKey)?.display_name ?? tableKey;
}

export function buildNavigationOperationOptions({
  activeNavigationModule,
  navigationModuleKey,
  op,
  navigationName,
  navigationSort,
  confirm = false,
}: {
  activeNavigationModule?: NavigationModule;
  navigationModuleKey: string;
  op: NavigationOperation;
  navigationName: string;
  navigationSort: string;
  confirm?: boolean;
}): NavigationOperationOptions {
  return {
    moduleKey: activeNavigationModule?.moduleKey ?? navigationModuleKey,
    op,
    name: navigationName,
    sort: Number(navigationSort || activeNavigationModule?.sort || 0),
    confirm,
  };
}
