import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  deprecateReviewedPublication,
  exportReviewedPublication,
  getReviewedPublication,
  getReviewedPublications,
} from "../apiReviewedPublications";
import type { ReviewedPublication, ReviewedPublicationPayload } from "../typesReviewedPublication";
import { biText } from "./Bilingual";
import "./evidenceReviewedPublications.css";

type PendingDeprecation = {
  expectedHeadHash: string;
  publicationKey: string;
  reason: string;
};

function errorMessage(error: unknown) {
  return error instanceof Error && error.message
    ? error.message
    : biText("审核制品操作失败。", "Reviewed publication operation failed.");
}

function localDate(value?: string | null) {
  if (!value) return "—";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(parsed);
}

function displayStatus(publication: ReviewedPublication) {
  if (publication.status === "stale") return { key: "drifted", label: biText("已漂移", "Drifted") };
  if (publication.status === "integrity_failed") return { key: "integrity_failed", label: biText("完整性失败", "Integrity failed") };
  if (publication.status === "deprecated") return { key: "deprecated", label: biText("已停用", "Deprecated") };
  return { key: "current", label: biText("当前有效", "Current") };
}

function ensureWorkspace(payload: ReviewedPublicationPayload, workspaceId: string) {
  if (payload.workspaceId !== workspaceId) {
    throw new Error(biText("审核制品响应与当前工作区不一致。", "Reviewed publication response does not match the active workspace."));
  }
}

function downloadJson(filename: string, value: Record<string, unknown>) {
  const blob = new Blob([JSON.stringify(value, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function EvidenceReviewedPublicationsPanel({ workspaceId }: { workspaceId: string }) {
  const [publications, setPublications] = useState<ReviewedPublication[]>([]);
  const [selectedKey, setSelectedKey] = useState("");
  const [selected, setSelected] = useState<ReviewedPublication | null>(null);
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState<PendingDeprecation | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const listRequestRef = useRef<AbortController | null>(null);
  const detailRequestRef = useRef<AbortController | null>(null);
  const actionRequestRef = useRef<AbortController | null>(null);
  const workspaceRef = useRef(workspaceId);
  workspaceRef.current = workspaceId;

  const loadList = useCallback(async (preferredKey = "", successMessage = "") => {
    listRequestRef.current?.abort();
    const controller = new AbortController();
    listRequestRef.current = controller;
    const expectedWorkspace = workspaceId;
    setBusy("list");
    try {
      const payload = await getReviewedPublications(workspaceId, controller.signal);
      if (controller.signal.aborted || workspaceRef.current !== expectedWorkspace) return;
      ensureWorkspace(payload, expectedWorkspace);
      const next = payload.reviewedPublications ?? [];
      setPublications(next);
      setSelectedKey((current) => {
        if (preferredKey && next.some((item) => item.publicationKey === preferredKey)) return preferredKey;
        if (current && next.some((item) => item.publicationKey === current)) return current;
        return next[0]?.publicationKey ?? "";
      });
      setNotice(successMessage);
    } catch (error) {
      if (!controller.signal.aborted && workspaceRef.current === expectedWorkspace) setNotice(errorMessage(error));
    } finally {
      if (!controller.signal.aborted && workspaceRef.current === expectedWorkspace) setBusy(null);
    }
  }, [workspaceId]);

  useEffect(() => {
    listRequestRef.current?.abort();
    detailRequestRef.current?.abort();
    actionRequestRef.current?.abort();
    setPublications([]);
    setSelectedKey("");
    setSelected(null);
    setReason("");
    setPending(null);
    setNotice("");
    void loadList();
    return () => {
      listRequestRef.current?.abort();
      detailRequestRef.current?.abort();
      actionRequestRef.current?.abort();
    };
  }, [loadList, workspaceId]);

  const refreshSelected = useCallback(async (successMessage = "") => {
    if (!selectedKey) return;
    detailRequestRef.current?.abort();
    const controller = new AbortController();
    detailRequestRef.current = controller;
    const expectedWorkspace = workspaceId;
    const expectedKey = selectedKey;
    setBusy("detail");
    setPending(null);
    try {
      const payload = await getReviewedPublication(workspaceId, selectedKey, controller.signal);
      if (controller.signal.aborted || workspaceRef.current !== expectedWorkspace) return;
      ensureWorkspace(payload, expectedWorkspace);
      const publication = payload.reviewedPublication;
      if (!publication || publication.publicationKey !== expectedKey || publication.workspaceId !== expectedWorkspace) {
        throw new Error(biText("详情没有返回当前选中的审核制品。", "The selected reviewed publication was not returned."));
      }
      setSelected(publication);
      setPublications((current) => current.map((item) => item.publicationKey === publication.publicationKey ? publication : item));
      setNotice(successMessage);
    } catch (error) {
      if (!controller.signal.aborted && workspaceRef.current === expectedWorkspace) {
        setSelected(null);
        setNotice(errorMessage(error));
      }
    } finally {
      if (!controller.signal.aborted && workspaceRef.current === expectedWorkspace) setBusy(null);
    }
  }, [selectedKey, workspaceId]);

  useEffect(() => {
    setSelected(null);
    setReason("");
    setPending(null);
    if (selectedKey) void refreshSelected();
  }, [refreshSelected, selectedKey]);

  async function exportSelected() {
    if (!selected) return;
    actionRequestRef.current?.abort();
    const controller = new AbortController();
    actionRequestRef.current = controller;
    const expectedWorkspace = workspaceId;
    setBusy("export");
    setNotice("");
    try {
      const payload = await exportReviewedPublication(workspaceId, selected.publicationKey, controller.signal);
      if (controller.signal.aborted || workspaceRef.current !== expectedWorkspace) return;
      ensureWorkspace(payload, expectedWorkspace);
      if (!payload.reviewedPublicationExport || payload.reviewedPublicationExport.workspaceId !== expectedWorkspace) {
        throw new Error(biText("安全导出没有返回当前工作区制品。", "Safe export did not return an artifact for the active workspace."));
      }
      downloadJson(`${selected.publicationKey}.json`, payload.reviewedPublicationExport as unknown as Record<string, unknown>);
      setNotice(biText("已导出脱敏 JSON 和证据链。", "Redacted JSON and its evidence ledger were exported."));
    } catch (error) {
      if (!controller.signal.aborted && workspaceRef.current === expectedWorkspace) setNotice(errorMessage(error));
    } finally {
      if (!controller.signal.aborted && workspaceRef.current === expectedWorkspace) setBusy(null);
    }
  }

  async function previewDeprecation() {
    if (!selected || !reason.trim()) return;
    actionRequestRef.current?.abort();
    const controller = new AbortController();
    actionRequestRef.current = controller;
    const expectedWorkspace = workspaceId;
    setBusy("preview-deprecate");
    setPending(null);
    setNotice("");
    try {
      const payload = await deprecateReviewedPublication({
        workspaceId,
        publicationKey: selected.publicationKey,
        reason: reason.trim(),
      }, controller.signal);
      if (controller.signal.aborted || workspaceRef.current !== expectedWorkspace) return;
      ensureWorkspace(payload, expectedWorkspace);
      if (!payload.requiresConfirmation || !payload.expectedHeadHash || payload.publicationKey !== selected.publicationKey) {
        throw new Error(biText("停用预演没有返回精确证据链头。", "Deprecation preview did not return the exact ledger head."));
      }
      setPending({ expectedHeadHash: payload.expectedHeadHash, publicationKey: selected.publicationKey, reason: reason.trim() });
    } catch (error) {
      if (!controller.signal.aborted && workspaceRef.current === expectedWorkspace) setNotice(errorMessage(error));
    } finally {
      if (!controller.signal.aborted && workspaceRef.current === expectedWorkspace) setBusy(null);
    }
  }

  async function confirmDeprecation() {
    if (!pending || pending.publicationKey !== selectedKey) return;
    actionRequestRef.current?.abort();
    const controller = new AbortController();
    actionRequestRef.current = controller;
    const expectedWorkspace = workspaceId;
    setBusy("confirm-deprecate");
    setNotice("");
    try {
      const payload = await deprecateReviewedPublication({
        workspaceId,
        publicationKey: pending.publicationKey,
        reason: pending.reason,
        confirm: true,
        expectedHeadHash: pending.expectedHeadHash,
      }, controller.signal);
      if (controller.signal.aborted || workspaceRef.current !== expectedWorkspace) return;
      ensureWorkspace(payload, expectedWorkspace);
      if (
        !payload.confirmed
        || !payload.publication
        || payload.publication.workspaceId !== expectedWorkspace
        || payload.publication.publicationKey !== pending.publicationKey
      ) {
        throw new Error(biText("审核制品未完成停用，请重新预演。", "The reviewed publication was not deprecated; preview it again."));
      }
      setSelected(payload.publication);
      setPublications((current) => current.map((item) => (
        item.publicationKey === payload.publication?.publicationKey ? payload.publication : item
      )));
      setPending(null);
      setReason("");
      await loadList(pending.publicationKey, biText("已追加停用记录；历史证据链未被改写。", "A deprecation entry was appended; evidence history was not rewritten."));
    } catch (error) {
      if (!controller.signal.aborted && workspaceRef.current === expectedWorkspace) {
        setPending(null);
        setNotice(errorMessage(error));
      }
    } finally {
      if (!controller.signal.aborted && workspaceRef.current === expectedWorkspace) setBusy(null);
    }
  }

  const status = selected ? displayStatus(selected) : null;
  const blockers = useMemo(() => selected ? [
    ...selected.ledger.blockers.map((code) => ({ kind: biText("完整性", "Integrity"), code })),
    ...selected.ledger.evidenceBlockers.map((code) => ({ kind: biText("证据", "Evidence"), code })),
    ...selected.drift.reasonCodes.map((code) => ({ kind: biText("漂移", "Drift"), code })),
  ] : [], [selected]);
  const canDeprecate = Boolean(selected && selected.status !== "deprecated" && selected.ledger.ok);

  return (
    <section className="reviewedPublicationsPanel" data-testid="evidence-reviewed-publications-panel" aria-labelledby="reviewed-publications-title">
      <header className="reviewedPublicationsHeader">
        <div>
          <span>{biText("审核制品 · 证据链", "Reviewed artifacts · evidence ledger")}</span>
          <strong id="reviewed-publications-title">{biText("已发布结论的有效性", "Validity of published conclusions")}</strong>
          <small>{biText("只展示当前工作区的已审核制品；这里不能创建新发布。", "Shows reviewed publications from the active workspace only; new publications cannot be created here.")}</small>
        </div>
        <button className="miniButton secondary" disabled={busy !== null} onClick={() => void loadList(selectedKey, biText("制品列表已刷新。", "Publication list refreshed."))} type="button">
          {busy === "list" ? biText("读取中…", "Loading…") : biText("刷新列表", "Refresh list")}
        </button>
      </header>

      {publications.length ? (
        <label className="reviewedPublicationSelector">
          <span>{biText("选择审核制品", "Select reviewed publication")}</span>
          <select disabled={busy !== null} onChange={(event) => setSelectedKey(event.target.value)} value={selectedKey}>
            {publications.map((publication) => (
              <option key={publication.publicationKey} value={publication.publicationKey}>
                {publication.title} · {displayStatus(publication).label}
              </option>
            ))}
          </select>
        </label>
      ) : <p className="reviewedPublicationEmpty">{busy === "list" ? biText("正在读取审核制品…", "Loading reviewed publications…") : biText("当前工作区尚无审核制品。", "The active workspace has no reviewed publications.")}</p>}

      {selected && status ? (
        <article className={`reviewedPublicationDetail ${status.key}`} data-publication-status={status.key}>
          <div className="reviewedPublicationTitle">
            <div>
              <span>{status.label}</span>
              <h4>{selected.title}</h4>
              <small>{localDate(selected.reviewedAt ?? selected.createdAt)} · {selected.publicationKey}</small>
            </div>
            <button className="miniButton secondary" disabled={busy !== null} onClick={() => void refreshSelected(biText("已重新校验制品、证据链和漂移状态。", "Publication, ledger, and drift status revalidated."))} type="button">
              {busy === "detail" ? biText("校验中…", "Verifying…") : biText("刷新校验", "Revalidate")}
            </button>
          </div>

          <dl className="reviewedPublicationTrustGrid">
            <div><dt>{biText("证据链完整性", "Ledger integrity")}</dt><dd>{selected.ledger.ok ? biText("通过", "Passed") : biText("失败", "Failed")}</dd></div>
            <div><dt>{biText("证据当前性", "Evidence currency")}</dt><dd>{selected.ledger.currentEvidence ? biText("当前", "Current") : biText("受阻", "Blocked")}</dd></div>
            <div><dt>{biText("证据链条目", "Ledger entries")}</dt><dd>{selected.ledger.entryCount}</dd></div>
            <div><dt>{biText("可支持当前决策", "Current decision basis")}</dt><dd>{selected.canSupportCurrentDecision ? biText("是", "Yes") : biText("否", "No")}</dd></div>
          </dl>

          <div className="reviewedPublicationHead">
            <span>{biText("Ledger head", "Ledger head")}</span>
            <code>{selected.ledgerHeadHash}</code>
          </div>

          <section className="reviewedPublicationBlockers" aria-labelledby="reviewed-publication-blockers-title">
            <strong id="reviewed-publication-blockers-title">{biText("完整性与漂移阻塞项", "Integrity and drift blockers")}</strong>
            {blockers.length ? (
              <ul>{blockers.map((item, index) => <li key={`${item.kind}-${item.code}-${index}`}><span>{item.kind}</span><code>{item.code}</code></li>)}</ul>
            ) : <p>{biText("没有阻塞项，制品仍绑定当前证据。", "No blockers; this publication remains bound to current evidence.")}</p>}
          </section>

          <div className="reviewedPublicationActions">
            <button className="miniButton secondary" disabled={busy !== null || selected.status === "integrity_failed"} onClick={() => void exportSelected()} type="button">
              {busy === "export" ? biText("导出中…", "Exporting…") : biText("安全导出 JSON", "Safe JSON export")}
            </button>
          </div>

          {selected.status !== "deprecated" ? (
            <fieldset className="reviewedPublicationDeprecation" disabled={busy !== null || !selected.ledger.ok}>
              <legend>{biText("停用审核制品", "Deprecate reviewed publication")}</legend>
              <label>
                <span>{biText("停用原因", "Reason")}</span>
                <textarea maxLength={500} onChange={(event) => { setReason(event.target.value); setPending(null); }} rows={2} value={reason} />
              </label>
              <button className="miniButton secondary danger" disabled={!canDeprecate || !reason.trim()} onClick={() => void previewDeprecation()} type="button">
                {busy === "preview-deprecate" ? biText("预演中…", "Previewing…") : biText("预演停用", "Preview deprecation")}
              </button>
              {!selected.ledger.ok ? <small role="alert">{biText("证据链损坏时禁止追加；请先处理完整性故障。", "A damaged ledger cannot be appended; resolve the integrity failure first.")}</small> : null}
            </fieldset>
          ) : <p className="reviewedPublicationDeprecatedReason">{biText("停用原因", "Deprecation reason")}: {selected.deprecationReason || "—"}</p>}

          {pending ? (
            <section className="reviewedPublicationConfirmation" data-testid="reviewed-publication-deprecation-confirmation" role="status">
              <div>
                <strong>{biText("等待精确证据链头确认", "Exact ledger-head confirmation required")}</strong>
                <span>{pending.reason}</span>
                <code>{pending.expectedHeadHash}</code>
              </div>
              <button className="miniButton danger" disabled={busy !== null} onClick={() => void confirmDeprecation()} type="button">
                {busy === "confirm-deprecate" ? biText("确认中…", "Confirming…") : biText("确认停用", "Confirm deprecation")}
              </button>
              <button className="miniButton secondary" disabled={busy !== null} onClick={() => setPending(null)} type="button">{biText("取消", "Cancel")}</button>
            </section>
          ) : null}
        </article>
      ) : null}

      {notice ? <p className="reviewedPublicationNotice" role="status">{notice}</p> : null}
    </section>
  );
}
