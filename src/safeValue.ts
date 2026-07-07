export function numberValue(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

export function objectRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

export function recordArray(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.map(objectRecord).filter(Boolean) as Array<Record<string, unknown>> : [];
}

export function stringValue(value: unknown) {
  return typeof value === "string" ? value : "";
}
