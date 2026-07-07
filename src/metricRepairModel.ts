import type { FieldConfig, WorkbenchPayload } from "./types";
import { numberValue, objectRecord, recordArray, stringValue } from "./safeValue";

type MetricSqlRecord = Record<string, unknown>;

export type SemanticBindingDraft = {
  semantic: string;
  impactCount: number;
  tableKey: string;
  tableName: string;
  fieldName: string;
  confidence: number;
  tone: "ok" | "warn" | "info";
  reason: string;
  status: string;
  riskLevel: "low" | "medium" | "high";
  riskReason: string;
  requiresPreview: boolean;
};

export type EvidenceGapItem = {
  key: string;
  title: string;
  detail: string;
  missingSemantics: string[];
  severity: "warn" | "info";
};

export type MetricRepairPlan = {
  planned: number;
  executable: number;
  blocked: number;
  rate: number;
  currentRunLabel: string;
  rerunInputs: string[];
  bindingDrafts: SemanticBindingDraft[];
  evidenceGaps: EvidenceGapItem[];
  nextSteps: string[];
  summary: string;
  benefitSummary: string;
};

const semanticAliases: Record<string, string[]> = {
  paid_gmv: ["paid_gmv", "gmv", "paid", "payment", "pay", "amount", "sales", "revenue", "实付", "支付", "付款", "成交", "销售额", "金额"],
  inventory_qty: ["inventory", "stock", "qty", "quantity", "库存", "结存", "数量", "件数"],
  customer_id: ["customer", "buyer", "member", "user", "client", "客户", "买家", "会员", "用户"],
  order_date: ["order_date", "date", "time", "day", "month", "日期", "时间", "月份", "订单日期"],
  cost_amount: ["cost", "expense", "fee", "amount", "成本", "费用", "支出", "金额"],
  refund_amount: ["refund", "return", "amount", "退款", "退货", "退费", "金额"],
  sku_id: ["sku", "product", "item", "goods", "商品", "货品", "款号", "编码"],
  shop_id: ["shop", "store", "seller", "店铺", "门店", "商家"],
};

const semanticRiskTerms: Record<string, string[]> = {
  paid_gmv: ["net_sales", "estimated_net_sales", "refund", "return", "net_", "净销售", "净额", "退款", "售后"],
  refund_amount: ["paid_gmv", "gmv", "gross", "sales", "成交", "销售额"],
  cost_amount: ["paid_gmv", "gmv", "sales", "revenue", "收入", "销售额"],
};

function textBag(field: FieldConfig) {
  return [
    field.field_name,
    field.role,
    field.usage,
    field.tags_json,
    field.usage_json,
    field.note,
  ].filter(Boolean).join(" ").toLowerCase();
}

function aliasesForSemantic(semantic: string) {
  return semanticAliases[semantic] ?? semantic.split(/[_\s.-]+/).filter(Boolean);
}

function tableNameFor(workbench: WorkbenchPayload, tableKey: string) {
  return workbench.tables.find((table) => table.table_key === tableKey)?.display_name || tableKey || "待确认表";
}

function scoreFieldForSemantic(field: FieldConfig, semantic: string) {
  const bag = textBag(field);
  const fieldName = field.field_name.toLowerCase();
  const aliases = aliasesForSemantic(semantic);
  const directSemantic = bag.includes(semantic.toLowerCase()) ? 5 : 0;
  const aliasScore = aliases.reduce((score, alias) => {
    const normalizedAlias = alias.toLowerCase();
    if (!normalizedAlias) return score;
    if (fieldName === normalizedAlias) return score + 5;
    if (fieldName.includes(normalizedAlias)) return score + 3;
    if (bag.includes(normalizedAlias)) return score + 2;
    return score;
  }, 0);
  const usageScore = ["measure", "dimension", "identity", "time"].some((role) => bag.includes(role)) ? 1 : 0;
  return directSemantic + aliasScore + usageScore + Math.min(1, Math.max(0, field.confidence || 0));
}

function riskForSemantic(field: FieldConfig, semantic: string) {
  const bag = textBag(field);
  const fieldName = field.field_name.toLowerCase();
  const exactSemantic = fieldName === semantic.toLowerCase() || bag.includes(` ${semantic.toLowerCase()} `);
  const riskyTerms = semanticRiskTerms[semantic] ?? [];
  const matchedRisk = exactSemantic ? "" : riskyTerms.find((term) => bag.includes(term.toLowerCase()));
  if (matchedRisk) {
    return {
      level: "high" as const,
      penalty: 2.5,
      reason: `候选字段包含 ${matchedRisk}，可能是净额、退款或派生指标，确认前必须先预演。`,
    };
  }
  const derivedTerms = ["ratio", "rate", "mom", "yoy", "delta", "estimated", "calc", "同比", "环比", "比率", "差额", "估算"];
  const derivedTerm = derivedTerms.find((term) => bag.includes(term));
  if (derivedTerm && !exactSemantic) {
    return {
      level: "medium" as const,
      penalty: 1.2,
      reason: `候选字段带有 ${derivedTerm} 特征，可能不是原始业务字段。`,
    };
  }
  return {
    level: "low" as const,
    penalty: 0,
    reason: "字段名和用途没有明显冲突。",
  };
}

function bestBindingDraft(semantic: string, impactCount: number, fields: FieldConfig[], workbench: WorkbenchPayload): SemanticBindingDraft {
  const ranked = fields
    .map((field) => {
      const risk = riskForSemantic(field, semantic);
      return { field, risk, score: scoreFieldForSemantic(field, semantic) - risk.penalty };
    })
    .sort((left, right) => right.score - left.score || (right.field.confidence || 0) - (left.field.confidence || 0));
  const winner = ranked[0];
  if (!winner || winner.score < 2.5) {
    return {
      semantic,
      impactCount,
      tableKey: "",
      tableName: "待确认表",
      fieldName: "待选择字段",
      confidence: 0,
      tone: "warn",
      reason: "没有找到足够接近的字段名或用途，需要用户确认真实业务字段。",
      status: "needs-human-confirmation",
      riskLevel: "medium",
      riskReason: "未找到足够可信的候选字段。",
      requiresPreview: true,
    };
  }
  const rawConfidence = Math.max(0.35, (winner.score / 10) + (winner.field.confidence || 0) * 0.35 - (winner.risk.level === "high" ? 0.18 : 0));
  const riskConfidenceCap = winner.risk.level === "high" ? 0.68 : winner.risk.level === "medium" ? 0.76 : 0.98;
  const confidence = Math.min(riskConfidenceCap, rawConfidence);
  const requiresPreview = winner.risk.level !== "low" || confidence < 0.72;
  return {
    semantic,
    impactCount,
    tableKey: winner.field.table_key,
    tableName: tableNameFor(workbench, winner.field.table_key),
    fieldName: winner.field.field_name,
    confidence,
    tone: !requiresPreview && confidence >= 0.72 ? "ok" : "warn",
    reason: winner.risk.level !== "low"
      ? winner.risk.reason
      : confidence >= 0.72
      ? "字段名、用途或已有置信度与缺失语义匹配，可作为确认草案。"
      : "存在相似字段，但置信度不足，确认前不写入指标 SQL。",
    status: requiresPreview ? "preview-required" : "draft-only",
    riskLevel: winner.risk.level,
    riskReason: winner.risk.reason,
    requiresPreview,
  };
}

export function buildMetricRepairPlan(qualityDoctorResult: MetricSqlRecord | null, workbench: WorkbenchPayload): MetricRepairPlan {
  const doctor = objectRecord(qualityDoctorResult);
  const metricSql = objectRecord(doctor?.metricSql) ?? {};
  const latestRun = objectRecord(doctor?.latestSourceIntelligenceRun);
  const planned = numberValue(metricSql.planned);
  const executable = numberValue(metricSql.executable);
  const blocked = numberValue(metricSql.blocked);
  const rate = typeof metricSql.rate === "number" && Number.isFinite(metricSql.rate) ? metricSql.rate : executable / Math.max(1, planned);
  const missingSemantics = recordArray(metricSql.missingSemantics);
  const failedSamples = recordArray(metricSql.failedSamples);
  const fields = Array.isArray(workbench.fields) ? workbench.fields : [];
  const bindingDrafts = missingSemantics.slice(0, 6).map((item) => bestBindingDraft(
    stringValue(item.semantic),
    numberValue(item.count),
    fields,
    workbench,
  )).filter((item) => item.semantic);
  const evidenceGaps = failedSamples.slice(0, 8).map((sample, index) => {
    const missing = Array.isArray(sample.missingSemantics) ? sample.missingSemantics.map(String) : [];
    return {
      key: stringValue(sample.analysisId) || `gap-${index}`,
      title: stringValue(sample.label) || stringValue(sample.analysisId) || "未命名指标问题",
      detail: stringValue(sample.reason) || stringValue(sample.agentInstruction) || "缺少可执行 SQL 或字段语义确认。",
      missingSemantics: missing,
      severity: missing.length ? "warn" as const : "info" as const,
    };
  });
  const summary = blocked > 0
    ? `${blocked} 个指标问题先卡在字段语义，确认 ${bindingDrafts.slice(0, 3).map((item) => item.semantic).join("、") || "关键字段"} 后再重跑画像。`
    : "当前指标 SQL 没有发现字段语义阻塞。";
  const latestWorkbenchRun = workbench.sourceIntelligenceRuns?.[0];
  const doctorInputs = Array.isArray(latestRun?.inputRoots) ? latestRun.inputRoots.map(String) : [];
  const manifestInputs = Array.isArray(latestRun?.manifestInputRoots) ? latestRun.manifestInputRoots.map(String) : [];
  const workbenchInputs = Array.isArray(latestWorkbenchRun?.inputRoots) ? latestWorkbenchRun.inputRoots.map(String) : [];
  const rerunInputs = doctorInputs.length ? doctorInputs : manifestInputs.length ? manifestInputs : workbenchInputs;
  const currentRunLabel = stringValue(latestRun?.label) || latestWorkbenchRun?.label || "当前画像";
  const bestDraft = bindingDrafts.find((item) => item.tableKey && item.fieldName !== "待选择字段");
  const benefitSummary = bestDraft
    ? `确认 ${bestDraft.semantic} 最多影响 ${bestDraft.impactCount} 个指标问题；重跑后以可执行率变化为准。`
    : blocked > 0
      ? "还没有足够可信的候选字段，先到字段面板确认真实业务字段。"
      : "当前没有需要修复的指标 SQL 阻塞。";
  return {
    planned,
    executable,
    blocked,
    rate,
    currentRunLabel,
    rerunInputs,
    bindingDrafts,
    evidenceGaps,
    summary,
    benefitSummary,
    nextSteps: [
      "先确认字段语义，不直接改原始表。",
      "确认后重跑 Source Intelligence，让指标 SQL 重新编译。",
      "仍不可执行的问题留在证据缺口，不推入看板结果。",
    ],
  };
}
