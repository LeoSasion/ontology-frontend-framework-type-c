export function toStringValue(value: unknown, fallback = ""): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}
