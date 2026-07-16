import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { addExplorationAnchor, createExplorationThread, getExplorationThreads, setExplorationBoardItem } from "../apiExploration";
import type { AgentAskResult, ExplorationMutationPayload, ExplorationThread } from "../types";
import { biText } from "./Bilingual";
import "./ExplorationThreadPanel.css";

const ResearchRunPanel = lazy(() => import("./ResearchRunPanel").then((module) => ({ default: module.ResearchRunPanel })));

type PendingMutation = {
  payload: ExplorationMutationPayload;
  confirm: () => Promise<ExplorationMutationPayload>;
};

type ExplorationThreadPanelProps = {
  result: AgentAskResult;
  canBranch: boolean;
  onAskBranch: (prompt: string, parentRunKey: string, branchLabel?: string) => Promise<void>;
};

function currentUnitKey(result: AgentAskResult) {
  return result.analysisUnit?.unitKey ?? result.answerCard?.analysisUnitRef?.unitKey ?? "";
}

function matchingThread(threads: ExplorationThread[], runKey: string, parentRunKey: string) {
  return threads.find((thread) => thread.anchors.some((anchor) => anchor.analysisRunKey === runKey))
    ?? threads.find((thread) => parentRunKey && thread.anchors.some((anchor) => anchor.analysisRunKey === parentRunKey))
    ?? null;
}

function mutationLabel(kind: string) {
  if (kind === "thread-create") return biText("建立探索线程", "Create exploration thread");
  if (kind === "anchor-add") return biText("加入分支锚点", "Add branch anchor");
  return biText("更新结果板", "Update result board");
}

export function ExplorationThreadPanel({ result, canBranch, onAskBranch }: ExplorationThreadPanelProps) {
  const workspaceId = result.workspaceId;
  const run = result.analysisRun;
  const runKey = run?.run_key ?? "";
  const parentRunKey = run?.parent_run_key ?? "";
  const unitKey = currentUnitKey(result);
  const sessionKey = result.agentSession?.sessionKey ?? "";
  const turnKey = result.agentTurn?.turnKey ?? "";
  const [threads, setThreads] = useState<ExplorationThread[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [pending, setPending] = useState<PendingMutation | null>(null);
  const [branchPrompt, setBranchPrompt] = useState("");
  const [branchLabel, setBranchLabel] = useState("");
  const requestRef = useRef(0);

  const thread = useMemo(() => matchingThread(threads, runKey, parentRunKey), [parentRunKey, runKey, threads]);
  const currentAnchor = thread?.anchors.find((anchor) => anchor.analysisRunKey === runKey) ?? null;
  const parentAnchor = thread?.anchors.find((anchor) => anchor.analysisRunKey === parentRunKey) ?? null;
  const boardAnchorKeys = new Set(thread?.resultBoard.items.map((item) => item.anchorKey) ?? []);
  const hiddenAnchors = thread?.anchors.filter((anchor) => !boardAnchorKeys.has(anchor.anchorKey)) ?? [];
  const storedRunIsEligible = run?.status === "executed" || run?.status === "confirmed";
  const canPreviewAnchor = Boolean(runKey && unitKey && (storedRunIsEligible || canBranch));

  async function refresh() {
    const requestId = ++requestRef.current;
    setLoading(true);
    try {
      const payload = await getExplorationThreads();
      if (requestRef.current !== requestId || payload.workspaceId !== workspaceId) return;
      setThreads(payload.explorationThreads ?? []);
    } catch (error) {
      if (requestRef.current === requestId) setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      if (requestRef.current === requestId) setLoading(false);
    }
  }

  useEffect(() => {
    setPending(null);
    setMessage("");
    void refresh();
    return () => {
      requestRef.current += 1;
    };
  }, [workspaceId, runKey]);

  async function runMutation(task: () => Promise<void>) {
    setBusy(true);
    setMessage("");
    try {
      await task();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }

  async function previewCurrentResult() {
    if (!runKey || !unitKey) return;
    await runMutation(async () => {
      if (!thread) {
        const request = {
          analysisRunKey: runKey,
          analysisUnitKey: unitKey,
          sessionKey,
          turnKey,
          title: run?.question || biText("探索线程", "Exploration thread"),
          label: run?.branch_label || run?.question || "",
        };
        const payload = await createExplorationThread(request);
        if (payload.workspaceId !== workspaceId) return;
        setPending({
          payload,
          confirm: () => createExplorationThread({ ...request, confirm: true, expectedPlanFingerprint: payload.explorationPlan.planFingerprint }),
        });
        return;
      }
      if (currentAnchor) {
        setMessage(biText("当前结果已经在这个探索线程中。", "This result is already in the exploration thread."));
        return;
      }
      if (!parentAnchor) {
        throw new Error(biText("当前分支找不到同线程父锚点，不能拼接无关结果。", "The branch has no matching parent Anchor in this thread."));
      }
      const request = {
        threadKey: thread.threadKey,
        parentAnchorKey: parentAnchor.anchorKey,
        analysisRunKey: runKey,
        analysisUnitKey: unitKey,
        sessionKey,
        turnKey,
        label: run?.branch_label || run?.question || "",
      };
      const payload = await addExplorationAnchor(request);
      if (payload.workspaceId !== workspaceId) return;
      setPending({
        payload,
        confirm: () => addExplorationAnchor({ ...request, confirm: true, expectedPlanFingerprint: payload.explorationPlan.planFingerprint }),
      });
    });
  }

  async function previewBoard(anchorKey: string, state: "pinned" | "removed") {
    if (!thread) return;
    await runMutation(async () => {
      const request = { threadKey: thread.threadKey, anchorKey, state };
      const payload = await setExplorationBoardItem(request);
      if (payload.workspaceId !== workspaceId) return;
      setPending({
        payload,
        confirm: () => setExplorationBoardItem({ ...request, confirm: true, expectedPlanFingerprint: payload.explorationPlan.planFingerprint }),
      });
    });
  }

  async function confirmPending() {
    if (!pending) return;
    await runMutation(async () => {
      const payload = await pending.confirm();
      if (payload.workspaceId !== workspaceId) return;
      setPending(null);
      setMessage(payload.changed === false
        ? biText("目标状态已经存在，没有重复写入。", "The requested state already exists; no duplicate was written.")
        : biText("探索上下文已保存。", "Exploration context saved."));
      await refresh();
    });
  }

  async function submitBranch() {
    if (!runKey || !branchPrompt.trim() || !canBranch) return;
    setBusy(true);
    setMessage("");
    try {
      await onAskBranch(branchPrompt.trim(), runKey, branchLabel.trim());
      setBranchPrompt("");
      setBranchLabel("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="explorationThreadPanel" data-testid="exploration-thread-panel">
      <div className="explorationThreadLead">
        <div>
          <span className="eyebrow">{biText("连续分析", "Continuous analysis")}</span>
          <strong>{thread?.title ?? biText("把当前结果变成可恢复的探索起点", "Turn this result into a recoverable exploration")}</strong>
          <small>
            {thread
              ? biText(`${thread.anchorCount} 个血缘锚点 · ${thread.resultBoard.itemCount} 个板上结果`, `${thread.anchorCount} lineage Anchors · ${thread.resultBoard.itemCount} board results`)
              : biText("只保存血缘引用和图表摘要，不复制业务结果行。", "Only lineage references and chart summaries are saved; business rows are not copied.")}
          </small>
        </div>
        <span className={`explorationStatus ${thread?.status ?? "idle"}`}>
          {loading ? biText("读取中", "Loading") : thread?.status === "current" ? biText("当前", "Current") : thread?.status === "stale" ? biText("需复核", "Review") : thread ? biText("引用缺失", "Missing refs") : biText("未建立", "Not created")}
        </span>
      </div>

      {!currentAnchor && canPreviewAnchor ? (
        <button className="secondaryButton" data-testid="exploration-preview-current" disabled={busy || loading} onClick={() => void previewCurrentResult()} type="button">
          {thread ? biText("预演加入当前分支", "Preview adding this branch") : biText("预演建立探索线程", "Preview exploration thread")}
        </button>
      ) : null}

      {pending ? (
        <div className="explorationConfirm" data-testid="exploration-confirmation">
          <div>
            <strong>{mutationLabel(pending.payload.explorationPlan.kind)}</strong>
            <span>{biText("目标与来源绑定已复核；确认只写本地探索元数据，不复制结果行。", "Target and source bindings are verified. Confirmation writes only local exploration metadata and copies no result rows.")}</span>
            <code>{pending.payload.explorationPlan.planFingerprint.slice(0, 16)}</code>
          </div>
          <div className="explorationConfirmActions">
            <button className="primaryButton" data-testid="exploration-confirm" disabled={busy} onClick={() => void confirmPending()} type="button">{biText("确认保存", "Confirm save")}</button>
            <button className="secondaryButton" disabled={busy} onClick={() => setPending(null)} type="button">{biText("取消", "Cancel")}</button>
          </div>
        </div>
      ) : null}

      {thread?.resultBoard.items.length ? (
        <div className="explorationBoard" data-testid="exploration-result-board">
          {thread.resultBoard.items.map((item, index) => {
            const anchor = item.anchor;
            if (!anchor) return null;
            return (
              <article className={`explorationCard ${anchor.freshness.status}`} key={item.boardItemKey}>
                <div className="explorationCardTopline">
                  <span>{index === 0 ? biText("起点", "Root") : `${biText("分支", "Branch")} ${index}`}</span>
                  <span>{anchor.freshness.status === "current" ? biText("可继续", "Usable") : anchor.freshness.status === "missing" ? biText("引用缺失", "Missing") : biText("已失效", "Stale")}</span>
                </div>
                <strong>{anchor.label}</strong>
                <p>{anchor.summary.question || anchor.summary.unitTitle}</p>
                <dl>
                  <div><dt>{biText("指标", "Measure")}</dt><dd>{anchor.summary.measureColumn || "-"}</dd></div>
                  <div><dt>{biText("维度", "Dimensions")}</dt><dd>{anchor.summary.dimensionColumns.join(" + ") || "-"}</dd></div>
                  <div><dt>{biText("图表", "Chart")}</dt><dd>{anchor.summary.chartType || "-"}</dd></div>
                </dl>
                {anchor.freshness.blockers.length ? <small className="explorationBlocker">{anchor.freshness.blockers.join(" · ")}</small> : null}
                <button className="miniButton" disabled={busy} onClick={() => void previewBoard(anchor.anchorKey, "removed")} type="button">{biText("预演移出结果板", "Preview remove")}</button>
              </article>
            );
          })}
        </div>
      ) : thread ? <div className="explorationEmpty">{biText("结果板为空；锚点历史仍保留。", "The board is empty; Anchor history is still preserved.")}</div> : null}

      {hiddenAnchors.length ? (
        <details className="advancedDetails compactAdvanced explorationHistory">
          <summary>{biText(`查看 ${hiddenAnchors.length} 个未固定锚点`, `View ${hiddenAnchors.length} unpinned Anchors`)}</summary>
          <div>
            {hiddenAnchors.map((anchor) => (
              <button className="miniButton" disabled={busy} key={anchor.anchorKey} onClick={() => void previewBoard(anchor.anchorKey, "pinned")} type="button">
                {biText("预演固定", "Preview pin")} · {anchor.label}
              </button>
            ))}
          </div>
        </details>
      ) : null}

      {thread ? <Suspense fallback={<p className="explorationMessage">{biText("正在载入有限研究…", "Loading finite research…")}</p>}><ResearchRunPanel thread={thread} /></Suspense> : null}

      <div className="agentBranchForm explorationBranchForm">
        <strong>{biText("从当前结果继续比较", "Compare from this result")}</strong>
        {canBranch ? (
          <>
            <label>
              <span>{biText("分支名称（可选）", "Branch label (optional)")}</span>
              <input placeholder={biText("例如：按地区比较", "For example: compare by region")} value={branchLabel} onChange={(event) => setBranchLabel(event.target.value)} />
            </label>
            <label>
              <span>{biText("下一项比较", "Next comparison")}</span>
              <textarea placeholder={biText("描述下一项比较", "Describe the next comparison")} value={branchPrompt} onChange={(event) => setBranchPrompt(event.target.value)} />
            </label>
            <button className="secondaryButton" disabled={busy || !branchPrompt.trim()} onClick={() => void submitBranch()} type="button">{busy ? biText("生成中", "Creating") : biText("创建血缘分支", "Create lineage branch")}</button>
          </>
        ) : <span>{biText("结果执行完成或图表确认后才开放分支，避免从未核对结果继续。", "Branches unlock after execution or chart confirmation, preventing continuation from an unverified result.")}</span>}
      </div>

      {message ? <p className="explorationMessage" role="status">{message}</p> : null}
    </section>
  );
}
