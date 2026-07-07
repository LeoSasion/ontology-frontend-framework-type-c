function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item).trim()).filter(Boolean) : [];
}

function stringValue(value: unknown, fallback = ""): string {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

type ErpGapUnlockAccumulator = {
  category: string;
  count: number;
  fields: string[];
  examples: string[];
  seenFields: Set<string>;
  seenExamples: Set<string>;
};

export type ErpGapUnlock = {
  category: string;
  count: number;
  fields: string[];
  examples: string[];
};

export function neededFieldsForErpHint(hint: Record<string, unknown>): string[] {
  return stringList(hint.neededFields);
}

export function collectNeededFieldsFromErpHints(hints: Array<Record<string, unknown>>, limit = 10): string[] {
  const seen = new Set<string>();
  const fields: string[] = [];

  for (const hint of hints) {
    for (const field of neededFieldsForErpHint(hint)) {
      const key = field.toLowerCase();
      if (seen.has(key)) continue;
      seen.add(key);
      fields.push(field);
      if (fields.length >= limit) return fields;
    }
  }

  return fields;
}

export function buildErpGapUnlocks(hints: Array<Record<string, unknown>>, limit = 4): ErpGapUnlock[] {
  const byCategory = new Map<string, ErpGapUnlockAccumulator>();

  for (const hint of hints) {
    const category = stringValue(hint.category, "其他方向");
    const title = stringValue(hint.title, stringValue(hint.key, "未命名方向"));
    const bucket = byCategory.get(category) ?? {
      category,
      count: 0,
      fields: [],
      examples: [],
      seenFields: new Set<string>(),
      seenExamples: new Set<string>(),
    };

    bucket.count += 1;
    if (!bucket.seenExamples.has(title)) {
      bucket.seenExamples.add(title);
      bucket.examples.push(title);
    }

    for (const field of neededFieldsForErpHint(hint)) {
      const key = field.toLowerCase();
      if (bucket.seenFields.has(key)) continue;
      bucket.seenFields.add(key);
      bucket.fields.push(field);
    }

    byCategory.set(category, bucket);
  }

  return Array.from(byCategory.values())
    .sort((left, right) => right.count - left.count || left.category.localeCompare(right.category))
    .slice(0, limit)
    .map((bucket) => ({
      category: bucket.category,
      count: bucket.count,
      fields: bucket.fields.slice(0, 5),
      examples: bucket.examples.slice(0, 2),
    }));
}
