import type { FieldConfig } from "./types";

export type QueryMetricOptions = {
  metric: string;
  group?: string[];
  filters?: Array<{ field: string; operator: string; value?: string }>;
  sort?: string;
  limit?: number;
};

export type SemanticInferOptions = {
  table?: string;
  overwriteManual?: boolean;
  confirm?: boolean;
};

export type SemanticSetOptions = {
  table: string;
  field: string;
  role: string;
  tags?: string[];
  usage?: string[];
  confidence?: number;
  note?: string;
  confirm?: boolean;
};

export type MetricMutationOptions = {
  id?: string;
  name: string;
  table: string;
  field?: string;
  aggregation?: string;
  dimension?: string;
  timeField?: string;
  filters?: Array<{ field: string; operator: string; value?: string }>;
  valueFormat?: string;
  description?: string;
  confirm?: boolean;
};

export type FieldSemanticReadiness = {
  readyFields: FieldConfig[];
  relationshipFields: FieldConfig[];
  reviewFields: FieldConfig[];
  readyNames: string[];
  relationshipNames: string[];
  reviewNames: string[];
};
