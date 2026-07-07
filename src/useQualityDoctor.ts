import { useEffect, useMemo, useState } from "react";
import { getQualityDoctor } from "./api";
import type { WorkbenchPayload } from "./types";

export type QualityDoctorResult = Record<string, unknown> | null;

function buildQualityDoctorRefreshKey(workbench: WorkbenchPayload) {
  const tables = workbench.tables
    .map((table) => [table.table_key, table.row_count, table.column_count, table.created_at ?? ""].join(":"))
    .join("|");
  const fields = workbench.fields
    .map((field) => [field.table_key, field.field_name, field.role, field.usage, field.confidence, field.source ?? "", field.updated_at ?? ""].join(":"))
    .join("|");
  const metrics = workbench.metrics
    .map((metric) => [
      metric.metric_key,
      metric.table_key,
      metric.measure,
      metric.aggregation,
      metric.dimension ?? "",
      metric.time_field ?? "",
      metric.enabled ?? "",
      metric.updated_at ?? "",
    ].join(":"))
    .join("|");
  const relationships = workbench.relationships
    .map((relationship) => [
      relationship.relation_key,
      relationship.left_table_key,
      relationship.right_table_key,
      relationship.left_field,
      relationship.right_field,
      relationship.join_type,
      relationship.confidence,
    ].join(":"))
    .join("|");
  const sourceRuns = workbench.sourceIntelligenceRuns
    .map((run) => [
      run.run_key,
      run.status,
      run.source_count,
      run.table_count,
      run.field_candidate_count,
      run.relationship_count,
      run.metric_sql_plan_count,
      run.metric_sql_executable_count,
      run.created_at,
    ].join(":"))
    .join("|");

  return [tables, fields, metrics, relationships, sourceRuns].join("::");
}

export function useQualityDoctor(enabled: boolean, workbench: WorkbenchPayload): QualityDoctorResult {
  const [result, setResult] = useState<QualityDoctorResult>(null);
  const refreshKey = useMemo(() => buildQualityDoctorRefreshKey(workbench), [workbench]);

  useEffect(() => {
    if (!enabled) {
      setResult(null);
      return;
    }

    let cancelled = false;
    getQualityDoctor()
      .then((nextResult) => {
        if (!cancelled) setResult(nextResult);
      })
      .catch(() => {
        if (!cancelled) setResult(null);
      });

    return () => {
      cancelled = true;
    };
  }, [enabled, refreshKey]);

  return result;
}
