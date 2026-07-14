import type { BusinessDashboardOptions } from "../dashboardCanvasContracts";
import { buildErpGapUnlocks, collectNeededFieldsFromErpHints, neededFieldsForErpHint } from "../erpUnitLibraryViewModel";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";

type DashboardBusinessTemplatePanelProps = {
  busy: string | null;
  dashboardKey: string;
  defaultTableKey: string;
  businessDraft: Record<string, unknown> | null;
  businessCategories: Array<Record<string, unknown>>;
  businessTemplateCount: number;
  erpPackEnabled: boolean;
  savedDashboardKey?: unknown;
  savedDashboardModules?: unknown;
  savedTemplateCount?: unknown;
  onBusinessTemplate: (label: string, options: BusinessDashboardOptions) => void;
};

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : null;
}

function asRecordArray(value: unknown): Array<Record<string, unknown>> {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => Boolean(asRecord(item))) : [];
}

function numberValue(value: unknown, fallback = 0) {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value) ? value.map((item) => String(item)).filter(Boolean) : [];
}

function summarizeMatchedFields(value: unknown) {
  const fields = asRecord(value);
  if (!fields) return "";
  return Object.entries(fields)
    .slice(0, 4)
    .map(([role, field]) => `${role}: ${String(field)}`)
    .join(" · ");
}

export function DashboardBusinessTemplatePanel({
  busy,
  dashboardKey,
  defaultTableKey,
  businessDraft,
  businessCategories,
  businessTemplateCount,
  erpPackEnabled,
  savedDashboardKey,
  savedDashboardModules,
  savedTemplateCount,
  onBusinessTemplate,
}: DashboardBusinessTemplatePanelProps) {
  const erpUnitLibrary = asRecord(businessDraft?.erpUnitLibrary);
  const erpWidgets = asRecordArray(businessDraft?.widgets)
    .filter((widget) => widget.erpUnitKey || widget.matchedFields)
    .slice(0, 4);
  const erpSources = asRecordArray(erpUnitLibrary?.selectedSources).slice(0, 5);
  const allOmittedUnitHints = asRecordArray(erpUnitLibrary?.omittedUnitHints);
  const omittedUnitHints = allOmittedUnitHints.slice(0, 4);
  const omittedNeededFields = collectNeededFieldsFromErpHints(allOmittedUnitHints);
  const gapUnlocks = buildErpGapUnlocks(allOmittedUnitHints);
  const categoryCoverage = asRecordArray(erpUnitLibrary?.categoryCoverage).slice(0, 6);
  const selectedUnitCount = numberValue(erpUnitLibrary?.selectedUnitCount, erpWidgets.length);
  const availableUnitCount = numberValue(erpUnitLibrary?.availableUnitCount);
  const referenceCount = numberValue(erpUnitLibrary?.referenceCount);
  const candidateUnitCount = numberValue(erpUnitLibrary?.candidateUnitCount);
  const notSelectedUnitCount = numberValue(erpUnitLibrary?.notSelectedUnitCount);
  const unavailableUnitCount = numberValue(erpUnitLibrary?.unavailableUnitCount);
  const selectedSourceIds = stringList(erpUnitLibrary?.selectedSourceIds);
  const hasErpSelection = Boolean(erpUnitLibrary);

  return (
    <article className="widgetActionPanel businessTemplatePanel" data-testid="business-template-panel">
      <div className="tileHeader compact">
        <h3><Bilingual zh="分析模板" en="Analysis templates" /></h3>
        <span>{defaultTableKey}</span>
      </div>
      <p className="emptyFilterHint">
        <Bilingual
          zh={erpPackEnabled ? "按字段证据与已启用的 ERP 单元组合看板。先预演，再选择新建或覆盖。" : "按当前字段证据组合通用总览、趋势、结构、筛选和明细组件。先预演，再选择新建或覆盖。"}
          en={erpPackEnabled ? "Build from field evidence and the enabled ERP unit pack. Preview before creating or overwriting." : "Build generic overview, trend, breakdown, filter, and detail widgets from current field evidence. Preview before creating or overwriting."}
        />
      </p>
      <div className="dashboardOps">
        <button
          className="secondaryButton"
          data-testid="business-dashboard-preview"
          disabled={busy === "business-template-preview"}
          onClick={() => onBusinessTemplate("business-template-preview", { op: "draft", table: defaultTableKey, limit: 10 })}
          type="button"
        >
          <Icon name="evidence" />
          <Bilingual zh="预演模板" en="Preview" />
        </button>
        {erpPackEnabled ? <button
          className="secondaryButton"
          data-testid="erp-unit-dashboard-preview"
          disabled={busy === "erp-unit-template-preview"}
          onClick={() => onBusinessTemplate("erp-unit-template-preview", { op: "draft", table: defaultTableKey, template: "erp-units", limit: 24 })}
          type="button"
        >
          <Icon name="evidence" />
          <Bilingual zh="ERP 单元" en="ERP units" />
        </button> : null}
        <button
          className="primaryButton"
          data-testid="business-dashboard-create"
          disabled={busy === "business-template-create"}
          onClick={() => onBusinessTemplate("business-template-create", { op: "create", table: defaultTableKey, limit: 10, confirm: true })}
          type="button"
        >
          <Icon name="dashboard" />
          <Bilingual zh="新建看板" en="Create" />
        </button>
        <button
          className="secondaryButton dangerSoft"
          data-testid="business-dashboard-overwrite"
          disabled={busy === "business-template-overwrite"}
          onClick={() => onBusinessTemplate("business-template-overwrite", { op: "overwrite", dashboardKey, table: defaultTableKey, limit: 10, confirm: true })}
          type="button"
        >
          <Icon name="check" />
          <Bilingual zh="覆盖当前" en="Overwrite" />
        </button>
      </div>
      {businessDraft ? (
        <div className={hasErpSelection ? "businessTemplateResult erpTemplateResult" : "businessTemplateResult"} data-testid="business-template-result">
          <div className="businessTemplateResultHeader">
            <div>
              <strong>
                {hasErpSelection
                  ? biText(`${selectedUnitCount} 个 ERP 单元已匹配`, `${selectedUnitCount} ERP units matched`)
                  : biText(`${businessTemplateCount} 个模板`, `${businessTemplateCount} templates`)}
              </strong>
              <span>
                {hasErpSelection
                  ? biText(
                    "Agent 会按当前字段证据挑选组件，未命中的单元不会渲染。",
                    "Agent selects widgets from current field evidence; unmatched units are omitted.",
                  )
                  : String(businessDraft.defaultTableKey ?? defaultTableKey)}
              </span>
            </div>
            <em>{String(businessDraft.defaultTableKey ?? defaultTableKey)}</em>
          </div>
          <div className="businessTemplateTags">
            {businessCategories.map((category) => (
              <em key={String(category.category)}>{String(category.category)} · {String(category.count)}</em>
            ))}
          </div>
          {hasErpSelection ? (
            <div className="erpTemplateEvidence" data-testid="erp-unit-selection-evidence">
              <div className="erpTemplateStats">
                <span><strong>{selectedUnitCount}</strong><small>{biText("已选单元", "Selected")}</small></span>
                <span><strong>{candidateUnitCount}</strong><small>{biText("候选单元", "Candidates")}</small></span>
                <span><strong>{availableUnitCount}</strong><small>{biText("单元库", "Library")}</small></span>
                <span><strong>{referenceCount}</strong><small>{biText("公开案例", "References")}</small></span>
              </div>
              {omittedUnitHints.length || notSelectedUnitCount || unavailableUnitCount ? (
                <div className="erpOmittedUnitPanel" data-testid="erp-unit-omitted-hints">
                  <div className="erpOmittedUnitHeader">
                    <strong>{biText("没生成的方向", "Omitted directions")}</strong>
                    <span>
                      {biText(
                        `字段不足单元 ${unavailableUnitCount} 个，数量上限延后 ${notSelectedUnitCount} 个。`,
                        `${unavailableUnitCount} units need more fields; ${notSelectedUnitCount} held by the display limit.`,
                      )}
                    </span>
                  </div>
                  <p>
                    {biText(
                      "系统不会伪造缺字段图表；补齐这些字段后，Agent 会自动把对应单元纳入候选。",
                      "The system will not fake missing-field charts. Add these fields and Agent can bring the matching units into the candidate set.",
                    )}
                  </p>
                  {omittedNeededFields.length ? (
                    <div className="erpMissingFieldChips" data-testid="erp-unit-missing-field-chips">
                      <strong>{biText("建议补充字段", "Suggested fields")}</strong>
                      <div>
                        {omittedNeededFields.map((field) => (
                          <span key={field}>{field}</span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {gapUnlocks.length ? (
                    <div className="erpGapUnlockList" data-testid="erp-unit-gap-unlocks">
                      <strong>{biText("补齐后优先解锁", "Unlock next")}</strong>
                      <div>
                        {gapUnlocks.map((unlock) => (
                          <span key={unlock.category}>
                            <b>{unlock.category}</b>
                            <small>
                              {biText(
                                `${unlock.count} 个方向 · ${unlock.fields.join("、") || unlock.examples.join("、")}`,
                                `${unlock.count} directions · ${unlock.fields.join(", ") || unlock.examples.join(", ")}`,
                              )}
                            </small>
                          </span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {omittedUnitHints.length ? (
                    <div className="erpOmittedUnitList">
                      {omittedUnitHints.map((hint) => {
                        const neededFields = neededFieldsForErpHint(hint);
                        return (
                          <article key={String(hint.key ?? hint.title)} className="erpOmittedUnitItem">
                            <div>
                              <strong>{String(hint.title ?? hint.key)}</strong>
                              <span>{String(hint.category ?? hint.type ?? "")}</span>
                            </div>
                            <small>
                              {neededFields.length
                                ? biText(`需要字段：${neededFields.join("、")}`, `Needs: ${neededFields.join(", ")}`)
                                : biText("需要更多业务字段", "Needs more business fields")}
                            </small>
                          </article>
                        );
                      })}
                    </div>
                  ) : null}
                  {categoryCoverage.length ? (
                    <div className="erpCoveragePills" data-testid="erp-unit-category-coverage">
                      {categoryCoverage.map((item) => (
                        <span key={String(item.category)}>
                          {String(item.category)}
                          <small>{biText(`${numberValue(item.selected)} 选 / ${numberValue(item.unavailable)} 缺`, `${numberValue(item.selected)} selected / ${numberValue(item.unavailable)} missing`)}</small>
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
              ) : null}
              {erpSources.length ? (
                <div className="erpSourceRail" data-testid="erp-unit-selected-sources">
                  <strong>{biText("命中案例", "Matched references")}</strong>
                  <div>
                    {erpSources.map((source) => (
                      <span key={String(source.id)}>
                        {String(source.vendor ?? source.domain ?? source.id)}
                        <small>{String(source.title ?? source.id)}</small>
                      </span>
                    ))}
                    {selectedSourceIds.length > erpSources.length ? (
                      <span>
                        +{selectedSourceIds.length - erpSources.length}
                        <small>{biText("更多来源", "more sources")}</small>
                      </span>
                    ) : null}
                  </div>
                </div>
              ) : null}
              {erpWidgets.length ? (
                <div className="erpUnitPreviewList" data-testid="erp-unit-widget-preview">
                  <strong>{biText("将渲染的看板单元", "Widgets to render")}</strong>
                  {erpWidgets.map((widget) => {
                    const matchedFields = summarizeMatchedFields(widget.matchedFields);
                    return (
                      <article key={String(widget.id ?? widget.erpUnitKey ?? widget.title)} className="erpUnitPreviewItem">
                        <div>
                          <strong>{String(widget.title ?? widget.erpUnitKey ?? widget.type)}</strong>
                          <span>{String(widget.type ?? "widget")} · {String(widget.category ?? widget.subtitle ?? "")}</span>
                        </div>
                        <small>
                          {matchedFields
                            ? biText(`字段命中：${matchedFields}`, `Matched fields: ${matchedFields}`)
                            : String(widget.reason ?? widget.subtitle ?? "")}
                        </small>
                      </article>
                    );
                  })}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : savedDashboardKey ? (
        <div className="businessTemplateResult" data-testid="business-template-result">
          <div className="businessTemplateResultHeader">
            <div>
              <strong>{biText("分析看板已生成", "Analysis dashboard generated")}</strong>
              <span>{String(savedDashboardKey)}</span>
            </div>
          </div>
          <div className="businessTemplateTags"><em>{String(savedDashboardModules ?? savedTemplateCount ?? 0)} {biText("个组件", "widgets")}</em></div>
        </div>
      ) : null}
    </article>
  );
}
