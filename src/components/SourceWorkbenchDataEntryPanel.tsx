import type { SourceIntelligenceRunSummary } from "../types";
import type { SourceIntelligenceRunOptions } from "../sourceIntelligenceRunModel";
import { sourceProfileBusinessStatus, sourceProfileRecovery, sourceProfileSummary } from "../sourceWorkbenchModel";
import { Bilingual, biText } from "./Bilingual";
import { Icon } from "./Icons";

type SourceWorkbenchDataEntryPanelProps = {
  sourceIntelligenceRuns: SourceIntelligenceRunSummary[];
  sourceProfileInputs: string;
  sourceProfileLabel: string;
  sourceProfileResult: Record<string, unknown> | null;
  sourceProfileError: string;
  sourceProfileRunning: boolean;
  sourceProfileRunningLabel: string;
  setSourceProfileInputs: (value: string) => void;
  setSourceProfileLabel: (value: string) => void;
  sourceProfileOptions: () => SourceIntelligenceRunOptions;
  runSourceProfile: (label: string, options: SourceIntelligenceRunOptions) => Promise<void>;
  onAsk: (prompt: string) => Promise<void>;
};

export function SourceWorkbenchDataEntryPanel({
  sourceIntelligenceRuns,
  sourceProfileInputs,
  sourceProfileLabel,
  sourceProfileResult,
  sourceProfileError,
  sourceProfileRunning,
  sourceProfileRunningLabel,
  setSourceProfileInputs,
  setSourceProfileLabel,
  sourceProfileOptions,
  runSourceProfile,
  onAsk,
}: SourceWorkbenchDataEntryPanelProps) {
  const sourceRecovery = sourceProfileError ? sourceProfileRecovery(sourceProfileError, sourceProfileInputs) : null;

  return (
    <article className="workbenchPanel widePanel sourceProfilePanel">
      <div className="tileHeader">
        <h3><Bilingual zh="证据摘要" en="Evidence summary" /></h3>
        <span>{sourceIntelligenceRuns.length}</span>
      </div>
      <div className="sourceProfileControl" data-testid="source-intelligence-folder-entry">
        <div className="formGrid sourceProfileForm">
          <label className="wideField">
            <span>{biText("本地文件夹或文件", "Local folders or files")}</span>
            <textarea
              rows={2}
              value={sourceProfileInputs}
              onChange={(event) => setSourceProfileInputs(event.target.value)}
              placeholder={biText("粘贴本地文件或文件夹路径", "Paste local file or folder paths")}
            />
          </label>
          <label>
            <span>{biText("摘要名称", "Summary label")}</span>
            <input value={sourceProfileLabel} onChange={(event) => setSourceProfileLabel(event.target.value)} />
          </label>
        </div>
        <div className="sourceProfileActions">
          <span className="quietText">
            {biText("可粘贴一个文件夹，也可用换行或逗号分隔多个路径；只读扫描，证据写入当前项目。", "Paste one folder, or separate multiple paths with new lines or commas. Scans are read-only and evidence is saved in this project.")}
          </span>
          <div className="buttonRow tight">
            <button
              className="primaryButton compactAction"
              data-testid="source-intelligence-custom-run-button"
              disabled={sourceProfileRunning}
              onClick={() => runSourceProfile("source-intelligence", sourceProfileOptions())}
              type="button"
            >
              <Icon name="agent" />
              <Bilingual zh="生成摘要" en="Create summary" />
            </button>
            <button
              className="miniButton"
              data-testid="source-intelligence-open-import-button"
              disabled={sourceProfileRunning}
              onClick={() => setSourceProfileInputs("")}
              type="button"
            >
              {biText("清空路径", "Clear paths")}
            </button>
          </div>
        </div>
        {sourceProfileRunning ? (
          <div className="sourceProfileRunState running" data-testid="source-intelligence-progress">
            <span className="runPulse" aria-hidden="true" />
            <div>
              <strong>{sourceProfileRunningLabel}</strong>
              <span>{biText("正在读取文件并整理可回答问题、业务连接和证据回执；完成前不会写入外部源目录。", "Reading files and summarizing answerable questions, business links, and evidence receipts. External source folders are never written.")}</span>
            </div>
          </div>
        ) : null}
        {sourceProfileError ? (
          <div className="sourceProfileRunState error" data-testid="source-intelligence-error">
            <div className="sourceProfileRecovery" data-testid="source-intelligence-recovery">
              <div className="sourceProfileRecoveryHeader">
                <strong>{sourceRecovery?.title ?? biText("画像失败", "Profiling failed")}</strong>
                <span>{sourceRecovery?.summary ?? biText("先检查路径和文件格式，再重新运行。", "Check the path and file format, then run again.")}</span>
              </div>
              <div className="sourceProfileBusinessHint" data-testid="source-intelligence-recovery-business-hint">
                <strong>{biText("没有写坏数据", "No data was changed")}</strong>
                <span>{biText("这一步只读生成证据回执。先确认路径、权限和文件格式，再决定是否让 Agent 帮你定位缺口。", "This step only creates a read-only evidence receipt. Check path, permission, and file format before asking Agent to locate the gap.")}</span>
              </div>
              <ol className="sourceProfileRecoverySteps" data-testid="source-intelligence-recovery-steps">
                {(sourceRecovery?.steps ?? []).map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
              <div className="sourceProfileRecoveryActions">
                <button className="secondaryButton" disabled={sourceProfileRunning} onClick={() => runSourceProfile("source-intelligence", sourceProfileOptions())} type="button">
                  <Icon name="query" />
                  <span><Bilingual zh="按当前路径重试" en="Retry current paths" /></span>
                </button>
                <button
                  className="secondaryButton"
                  onClick={() => onAsk(biText(
                    `证据摘要生成失败：${sourceProfileError}。请基于当前工作区说明最可能原因和下一步，不要创建任何草案。`,
                    `Evidence summary failed: ${sourceProfileError}. Explain the likely cause and next steps from the current workspace, and do not create any draft.`,
                  ))}
                  type="button"
                >
                  <Icon name="agent" />
                  <span><Bilingual zh="让 Agent 看看" en="Ask Agent" /></span>
                </button>
              </div>
              <details className="sourceProfileTechnicalError" data-testid="source-intelligence-technical-details">
                <summary>{biText("技术错误", "Technical error")}</summary>
                <span>{sourceProfileError}</span>
              </details>
            </div>
          </div>
        ) : null}
        {sourceProfileResult ? (
          <div className="sourceProfileRunState ok" data-testid="source-intelligence-result">
            <span className="runPulse ok" aria-hidden="true" />
            <div className="sourceProfileSuccessBody">
              {(() => {
                const businessStatus = sourceProfileBusinessStatus(sourceProfileResult);
                return (
                  <>
                    <strong>{businessStatus.title}</strong>
                    <span data-testid="source-intelligence-business-impact">{businessStatus.impact}</span>
                    <small data-testid="source-intelligence-next-step">{businessStatus.nextStep}</small>
                  </>
                );
              })()}
              <details className="sourceProfileTechnicalError sourceProfileTechnicalResult" data-testid="source-intelligence-result-technical-details">
                <summary>{biText("查看证据摘要回执", "View evidence summary receipt")}</summary>
                <span>{sourceProfileSummary(sourceProfileResult)}</span>
                <span>{biText("回执", "Receipt")}: {String(sourceProfileResult.runKey ?? sourceProfileResult.outputDir ?? biText("未返回", "Not returned"))}</span>
              </details>
            </div>
          </div>
        ) : null}
      </div>
      {sourceIntelligenceRuns.length ? (
        <ul className="metricList">
          {sourceIntelligenceRuns.slice(0, 4).map((run) => {
            const coverage = run.fileCoverage;
            const filesBySourceGroup = coverage?.filesBySourceGroup ?? [];
            return (
              <li className="sourceCoverageItem" data-testid="source-coverage-item" key={run.run_key}>
                <div className="sourceCoverageTopline">
                  <strong>{run.label}</strong>
                  <span className={run.isInternal ? "statusBadge neutral" : coverage?.complete ? "statusBadge ok" : "statusBadge warn"}>
                    {run.isInternal
                      ? biText("系统检查", "System check")
                      : coverage?.complete ? biText("文件覆盖完整", "Complete coverage") : biText("需要复核", "Needs review")}
                  </span>
                </div>
                <span>
                  {biText("文件", "files")}: {coverage?.sourceFileCount ?? run.source_count}/{coverage?.manifestSourceCount ?? run.source_count} · {biText("表", "tables")}: {run.table_count} · {biText("业务连接", "business links")}: {run.relationship_count} · {biText("可用问题", "answerable questions")}: {run.metric_sql_executable_count}
                </span>
                {filesBySourceGroup.length ? (
                  <div className="sourceCoverageMonths" data-testid="source-coverage-groups">
                    {filesBySourceGroup.map((item) => (
                      <span key={item.group}>{item.group}: {item.count}</span>
                    ))}
                  </div>
                ) : null}
                {coverage?.skippedTableCount ? (
                  <span className="sourceCoverageWarning">
                    {biText("跳过表", "skipped tables")}: {coverage.skippedTableCount}
                  </span>
                ) : null}
              </li>
            );
          })}
        </ul>
      ) : (
        <p className="quietText">
          {biText("尚未生成证据摘要；点击上方按钮后，系统会只读扫描文件并在当前项目保存证据。", "No evidence summary yet. Use the button above to scan files read-only and save evidence in this project.")}
        </p>
      )}
    </article>
  );
}
