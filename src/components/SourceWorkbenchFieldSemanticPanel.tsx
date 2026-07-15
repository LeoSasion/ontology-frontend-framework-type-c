import type { Dispatch, SetStateAction } from "react";
import type { FieldConfig, SourceIntelligenceRunSummary, WorkbenchTable } from "../types";
import type { FieldSemanticReadiness, SemanticInferOptions, SemanticSetOptions } from "../sourceWorkbenchFieldMetricTypes";
import { confidencePercent } from "../sourceWorkbenchModel";
import { Bilingual, biText, translateRole, translateUsage } from "./Bilingual";
import { Icon } from "./Icons";

type SourceWorkbenchFieldSemanticPanelProps = {
  showAdvanced: boolean;
  busy: string | null;
  tables: WorkbenchTable[];
  selectedTableKey: string;
  selectedFields: FieldConfig[];
  fieldRoles: string[];
  fieldUsages: string[];
  fieldSemanticReadiness: FieldSemanticReadiness;
  latestSourceProfile?: SourceIntelligenceRunSummary;
  setActiveTableKey: Dispatch<SetStateAction<string>>;
  setSemanticMetricResult: Dispatch<SetStateAction<Record<string, unknown> | null>>;
  fieldDraft: (field: FieldConfig) => Pick<FieldConfig, "role" | "usage">;
  updateFieldDraft: (field: FieldConfig, patch: Partial<Pick<FieldConfig, "role" | "usage">>) => void;
  runBusy: (label: string, action: () => Promise<void>) => Promise<void>;
  onAsk: (prompt: string) => Promise<void>;
  onInferSemantics: (options: SemanticInferOptions) => Promise<Record<string, unknown>>;
  onSetSemantic: (options: SemanticSetOptions) => Promise<Record<string, unknown>>;
};

export function SourceWorkbenchFieldSemanticPanel({
  showAdvanced,
  busy,
  tables,
  selectedTableKey,
  selectedFields,
  fieldRoles,
  fieldUsages,
  fieldSemanticReadiness,
  latestSourceProfile,
  setActiveTableKey,
  setSemanticMetricResult,
  fieldDraft,
  updateFieldDraft,
  runBusy,
  onAsk,
  onInferSemantics,
  onSetSemantic,
}: SourceWorkbenchFieldSemanticPanelProps) {
  return (
    <article className={showAdvanced ? "workbenchPanel widePanel advancedPanel" : "workbenchPanel widePanel advancedPanel collapsed"}>
      <div className="tileHeader">
        <h3><Bilingual zh="检查字段用途" en="Check field usage" /></h3>
        <div className="buttonRow tight">
          <select aria-label={biText("选择要检查字段的表", "Choose a table for field review")} value={selectedTableKey} onChange={(event) => setActiveTableKey(event.target.value)}>
            {tables.map((table) => (
              <option key={table.table_key} value={table.table_key}>{table.display_name}</option>
            ))}
          </select>
          <button
            className="miniButton"
            data-testid="infer-semantics-dry-run-button"
            disabled={busy === "semantics-dry"}
            onClick={() => runBusy("semantics-dry", async () => {
              setSemanticMetricResult(await onInferSemantics({ table: selectedTableKey, confirm: false }));
            })}
            type="button"
          >
            {biText("预演识别", "Preview infer")}
          </button>
          <button
            className="miniButton"
            data-testid="infer-semantics-confirm-button"
            disabled={busy === "semantics-save"}
            onClick={() => runBusy("semantics-save", async () => {
              setSemanticMetricResult(await onInferSemantics({ table: selectedTableKey, confirm: true }));
            })}
            type="button"
          >
            {biText("应用识别", "Apply infer")}
          </button>
        </div>
      </div>
      <p className="quietText">{biText("默认让系统按字段名、数值特征和通用语义规则识别；只有口径不对时再改单个字段。", "Let the system infer fields from names, values, and general semantic rules first. Edit individual fields only when the meaning is wrong.")}</p>
      <div className="fieldSemanticReadiness" data-testid="field-semantic-readiness">
        <div className="fieldSemanticReadinessLead">
          <div>
            <span className="storyMode"><Bilingual zh="字段体检" en="Field readiness" /></span>
            <strong><Bilingual zh="先看哪些字段已经能支撑看板和 Agent" en="See which fields are already useful for dashboards and Agent" /></strong>
            <p>
              {latestSourceProfile
                ? biText(`结合 ${latestSourceProfile.label} 的证据摘要和通用字段语义规则。`, `Combines the ${latestSourceProfile.label} evidence summary with general field semantic rules.`)
                : biText("先生成证据摘要后，这里会把字段证据和语义信心合并展示。", "After an evidence summary is created, this combines field evidence and semantic confidence.")}
            </p>
          </div>
          <button
            className="miniButton"
            data-testid="field-semantic-agent-review"
            disabled={!selectedFields.length || busy === "field-semantic-agent-review"}
            onClick={() => runBusy("field-semantic-agent-review", () => onAsk(biText(
              `检查 ${selectedTableKey} 的字段用途：哪些字段可直接用于看板，哪些字段需要确认，必要时只生成待确认修改。`,
              `Review field usage for ${selectedTableKey}: which fields are dashboard-ready, which need confirmation, and only create pending changes if needed.`,
            )))}
            type="button"
          >
            <Icon name="agent" />
            <Bilingual zh="让 Agent 复核" en="Ask Agent to review" />
          </button>
        </div>
        <div className="fieldSemanticCards" data-testid="field-semantic-readiness-cards">
          <div className="fieldSemanticCard ready" data-testid="field-semantic-ready">
            <strong>{fieldSemanticReadiness.readyFields.length}</strong>
            <span><Bilingual zh="可直接用于看板" en="Dashboard-ready" /></span>
            <small>{fieldSemanticReadiness.readyNames.length ? fieldSemanticReadiness.readyNames.join(" · ") : biText("等待字段证据", "Waiting for field evidence")}</small>
          </div>
          <div className="fieldSemanticCard relationship" data-testid="field-semantic-relationship">
            <strong>{fieldSemanticReadiness.relationshipFields.length}</strong>
            <span><Bilingual zh="可做关系或下钻" en="Relationship or drilldown" /></span>
            <small>{fieldSemanticReadiness.relationshipNames.length ? fieldSemanticReadiness.relationshipNames.join(" · ") : biText("暂无候选键", "No key candidates yet")}</small>
          </div>
          <div className="fieldSemanticCard review" data-testid="field-semantic-review">
            <strong>{fieldSemanticReadiness.reviewFields.length}</strong>
            <span><Bilingual zh="建议人工确认" en="Review recommended" /></span>
            <small>{fieldSemanticReadiness.reviewNames.length ? fieldSemanticReadiness.reviewNames.join(" · ") : biText("目前没有低信心字段", "No low-confidence fields now")}</small>
          </div>
        </div>
      </div>
      <details className="advancedDetails compactAdvanced fieldSemanticTechnical" data-testid="field-semantic-technical-details">
        <summary>{biText("逐字段调整", "Tune fields one by one")}</summary>
        <div className="tableScroll">
          <table>
            <thead>
              <tr>
                <th><Bilingual zh="字段" en="Field" /></th>
                <th><Bilingual zh="业务角色" en="Business role" /></th>
                <th><Bilingual zh="使用方式" en="Use as" /></th>
                <th><Bilingual zh="信心" en="Confidence" /></th>
                <th><Bilingual zh="应用" en="Apply" /></th>
              </tr>
            </thead>
            <tbody>
              {selectedFields.map((field) => {
                const draft = fieldDraft(field);
                return (
                  <tr key={`${field.table_key}.${field.field_name}`}>
                    <td>{field.field_name}</td>
                    <td>
                      <select aria-label={biText(`${field.field_name} 的业务角色`, `Business role for ${field.field_name}`)} value={draft.role} onChange={(event) => updateFieldDraft(field, { role: event.target.value })}>
                        {fieldRoles.map((role) => {
                          const label = translateRole(role);
                          return <option key={role} value={role}>{biText(label.zh, label.en)}</option>;
                        })}
                      </select>
                    </td>
                    <td>
                      <select aria-label={biText(`${field.field_name} 的使用方式`, `Usage for ${field.field_name}`)} value={draft.usage} onChange={(event) => updateFieldDraft(field, { usage: event.target.value })}>
                        {fieldUsages.map((usage) => {
                          const label = translateUsage(usage);
                          return <option key={usage} value={usage}>{biText(label.zh, label.en)}</option>;
                        })}
                      </select>
                    </td>
                    <td>{confidencePercent(field.confidence)}</td>
                    <td>
                      <button
                        className="miniButton"
                        disabled={busy === `field-${field.field_name}`}
                        onClick={() => runBusy(`field-${field.field_name}`, async () => {
                          setSemanticMetricResult(await onSetSemantic({
                            table: field.table_key,
                            field: field.field_name,
                            role: draft.role,
                            usage: [draft.usage],
                            confidence: 0.92,
                            confirm: true,
                          }));
                        })}
                        type="button"
                      >
                        {biText("保存", "Save")}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </details>
    </article>
  );
}
