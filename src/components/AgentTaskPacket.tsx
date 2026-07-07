import type { ActionDraft } from "../types";
import {
  actionEvidenceChips,
  actionKindText,
  actionRiskText,
  actionTarget,
  dashboardWidgetLine,
  pairText,
  stringField,
} from "../agentPanelModel";
import { buildErpGapUnlocks, collectNeededFieldsFromErpHints, neededFieldsForErpHint } from "../erpUnitLibraryViewModel";
import { numberValue, objectRecord, recordArray } from "../safeValue";
import { Bilingual, biText } from "./Bilingual";

type AgentTaskPacketProps = {
  currentDraft?: ActionDraft;
  fallbackKind: string;
  dashboardDraft: Record<string, unknown> | null;
  dashboardDraftTable: string;
  dashboardDraftWidgets: Record<string, unknown>[];
};

export function AgentTaskPacket({ currentDraft, fallbackKind, dashboardDraft, dashboardDraftTable, dashboardDraftWidgets }: AgentTaskPacketProps) {
  const erpUnitLibrary = dashboardDraft ? objectRecord(dashboardDraft.erpUnitLibrary) : null;
  const erpSources = erpUnitLibrary ? recordArray(erpUnitLibrary.selectedSources).slice(0, 3) : [];
  const allErpGaps = erpUnitLibrary ? recordArray(erpUnitLibrary.omittedUnitHints) : [];
  const erpGaps = allErpGaps.slice(0, 3);
  const erpNeededFields = collectNeededFieldsFromErpHints(allErpGaps, 8);
  const erpGapUnlocks = buildErpGapUnlocks(allErpGaps, 3);
  const erpCoverage = erpUnitLibrary ? recordArray(erpUnitLibrary.categoryCoverage).slice(0, 5) : [];
  const erpSelectedCount = numberValue(erpUnitLibrary?.selectedUnitCount);
  const erpAvailableCount = numberValue(erpUnitLibrary?.availableUnitCount);
  const erpReferenceCount = numberValue(erpUnitLibrary?.referenceCount);
  const erpUnavailableCount = numberValue(erpUnitLibrary?.unavailableUnitCount);
  const erpNotSelectedCount = numberValue(erpUnitLibrary?.notSelectedUnitCount);

  return (
    <div className={`agentTaskPacket ${currentDraft ? "draft" : "readonly"}`} data-testid="agent-task-packet">
      <div className="agentTaskPacketMain">
        <span className="storyMode"><Bilingual zh="Agent 任务包" en="Agent task packet" /></span>
        <strong>{currentDraft ? actionKindText(currentDraft.kind) : actionKindText(fallbackKind)}</strong>
        <p data-testid="agent-task-packet-target">
          {currentDraft ? actionTarget(currentDraft) : biText("当前回答没有待写入目标。", "This answer has no write target.")}
        </p>
      </div>
      <div className="agentTaskPacketMeta">
        <span className={currentDraft ? "risk" : "safe"} data-testid="agent-task-packet-risk">{actionRiskText(currentDraft)}</span>
        <div className="agentTaskEvidence" data-testid="agent-task-packet-evidence">
          {actionEvidenceChips(currentDraft).map((chip) => (
            <span key={chip}>{chip}</span>
          ))}
        </div>
      </div>
      {dashboardDraft ? (
        <div className="agentDashboardDraftPreview" data-testid="agent-dashboard-draft-preview">
          <div className="agentDashboardDraftLead">
            <div>
              <span className="storyMode"><Bilingual zh="将创建的看板" en="Dashboard to create" /></span>
              <strong>{stringField(dashboardDraft, "dashboardName") || biText("Agent 经营复盘", "Agent business review")}</strong>
              <p>{pairText(dashboardDraft.confirmationSummary as { zh: string; en: string } | undefined)}</p>
            </div>
            <div className="agentDashboardDraftStats">
              <span>{dashboardDraftTable}</span>
              <span>{String(dashboardDraft.widgetCount ?? dashboardDraftWidgets.length)} {biText("组件", "widgets")}</span>
              <span>{String(dashboardDraft.templateCount ?? 0)} {biText("模板", "templates")}</span>
            </div>
          </div>
          <div className="agentDashboardDraftWidgets">
            {dashboardDraftWidgets.map((widget, index) => (
              <div key={`${stringField(widget, "id") || stringField(widget, "title") || index}-${index}`} data-testid="agent-dashboard-draft-widget">
                <strong>{stringField(widget, "title") || biText("未命名组件", "Untitled widget")}</strong>
                <span>{dashboardWidgetLine(widget)}</span>
              </div>
            ))}
          </div>
          {erpUnitLibrary ? (
            <div className="agentErpUnitSummary" data-testid="agent-erp-unit-summary">
              <div className="agentErpUnitLead">
                <div>
                  <strong><Bilingual zh="Agent 已按 ERP 单元库选组件" en="Agent selected ERP units" /></strong>
                  <span>
                    {biText(
                      `${erpSelectedCount} 个已选 / ${erpAvailableCount} 个可用单元 · ${erpReferenceCount} 个公开案例`,
                      `${erpSelectedCount} selected / ${erpAvailableCount} library units · ${erpReferenceCount} public references`,
                    )}
                  </span>
                </div>
                <em><Bilingual zh="按字段证据评分，只渲染有证据的单元" en="Evidence-scored units only" /></em>
              </div>
              {erpCoverage.length ? (
                <div className="agentErpCoverage" data-testid="agent-erp-category-coverage">
                  {erpCoverage.map((item) => (
                    <span key={String(item.category)}>
                      {String(item.category)}
                      <small>{biText(`${numberValue(item.selected)} 选 / ${numberValue(item.unavailable)} 缺`, `${numberValue(item.selected)} selected / ${numberValue(item.unavailable)} missing`)}</small>
                    </span>
                  ))}
                </div>
              ) : null}
              {erpGaps.length || erpUnavailableCount || erpNotSelectedCount ? (
                <div className="agentErpGapList" data-testid="agent-erp-gap-list">
                  <div>
                    <strong><Bilingual zh="没生成的方向" en="Omitted directions" /></strong>
                    <span>
                      {biText(
                        `字段不足单元 ${erpUnavailableCount} 个，因数量上限延后 ${erpNotSelectedCount} 个。`,
                        `${erpUnavailableCount} units need more fields; ${erpNotSelectedCount} held by display limit.`,
                      )}
                    </span>
                  </div>
                  {erpNeededFields.length ? (
                    <div className="erpMissingFieldChips agentErpMissingFields" data-testid="agent-erp-missing-field-chips">
                      <strong>{biText("建议补充字段", "Suggested fields")}</strong>
                      <div>
                        {erpNeededFields.map((field) => (
                          <span key={field}>{field}</span>
                        ))}
                      </div>
                    </div>
                  ) : null}
                  {erpGapUnlocks.length ? (
                    <div className="erpGapUnlockList agentErpGapUnlocks" data-testid="agent-erp-gap-unlocks">
                      <strong>{biText("补齐后优先解锁", "Unlock next")}</strong>
                      <div>
                        {erpGapUnlocks.map((unlock) => (
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
                  {erpGaps.map((gap) => {
                    const neededFields = neededFieldsForErpHint(gap);
                    return (
                      <article key={String(gap.key ?? gap.title)}>
                        <strong>{String(gap.title ?? gap.key)}</strong>
                        <span>
                          {neededFields.length
                            ? biText(`需要：${neededFields.join("、")}`, `Needs: ${neededFields.join(", ")}`)
                            : biText("需要更多业务字段", "Needs more business fields")}
                        </span>
                      </article>
                    );
                  })}
                </div>
              ) : null}
              {erpSources.length ? (
                <div className="agentErpSourceList" data-testid="agent-erp-source-list">
                  {erpSources.map((source) => (
                    <span key={String(source.id)}>
                      {String(source.vendor ?? source.domain ?? source.id)}
                      <small>{String(source.title ?? source.id)}</small>
                    </span>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
