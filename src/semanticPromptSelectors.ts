export type SemanticPromptSelectors = {
  basePrompt: string;
  rootTable: string | null;
  relationKeys: string[];
};

const semanticSelectorPattern = /[，,]\s*使用(根表|关系路径)\s+/g;

function normalizedSelectorValue(value: string) {
  return value.trim().replace(/[，,]\s*$/, "");
}

export function parseSemanticPromptSelectors(prompt: string): SemanticPromptSelectors {
  const normalizedPrompt = prompt.trim();
  const matches = Array.from(normalizedPrompt.matchAll(semanticSelectorPattern));
  if (!matches.length) {
    return { basePrompt: normalizedPrompt, rootTable: null, relationKeys: [] };
  }

  const basePrompt = normalizedPrompt
    .slice(0, matches[0].index)
    .trim()
    .replace(/[，,]\s*$/, "");
  let rootTable: string | null = null;
  let relationKeys: string[] = [];

  matches.forEach((match, index) => {
    const valueStart = (match.index ?? 0) + match[0].length;
    const valueEnd = matches[index + 1]?.index ?? normalizedPrompt.length;
    const value = normalizedSelectorValue(normalizedPrompt.slice(valueStart, valueEnd));
    if (match[1] === "根表") {
      rootTable = value.split(/\s+/)[0] || null;
      return;
    }
    relationKeys = value.split(">").map((item) => item.trim()).filter(Boolean);
  });

  return { basePrompt, rootTable, relationKeys };
}

function buildSemanticPrompt(selectors: SemanticPromptSelectors) {
  const parts = [selectors.basePrompt.trim()].filter(Boolean);
  if (selectors.rootTable) parts.push(`使用根表 ${selectors.rootTable}`);
  if (selectors.relationKeys.length) parts.push(`使用关系路径 ${selectors.relationKeys.join(" > ")}`);
  return parts.join("，");
}

export function withSemanticRootSelection(prompt: string, rootTable: string) {
  const current = parseSemanticPromptSelectors(prompt);
  return buildSemanticPrompt({
    ...current,
    rootTable: rootTable.trim(),
  });
}

export function withSemanticPathSelection(prompt: string, relationKeys: string[]) {
  const current = parseSemanticPromptSelectors(prompt);
  return buildSemanticPrompt({
    ...current,
    relationKeys: relationKeys.map((item) => item.trim()).filter(Boolean),
  });
}
