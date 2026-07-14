import type { WorkspaceDomainPackRuntime } from "../types";
import { Bilingual, biText } from "./Bilingual";

type SettingsDomainPackPanelProps = {
  busyKey: string | null;
  result: Record<string, unknown> | null;
  runtime?: WorkspaceDomainPackRuntime;
  onSetDomainPack: (options: {
    packId: string;
    state: "enabled" | "disabled";
    workspaceId?: string;
    confirm?: boolean;
  }) => Promise<void>;
};

function resultChange(result: Record<string, unknown> | null) {
  const change = result?.change;
  return change && typeof change === "object" && !Array.isArray(change)
    ? change as Record<string, unknown>
    : null;
}

export function SettingsDomainPackPanel({ busyKey, onSetDomainPack, result, runtime }: SettingsDomainPackPanelProps) {
  const pendingChange = resultChange(result);
  const pendingWorkspace = String(pendingChange?.workspaceId ?? "");
  const pendingPack = String(pendingChange?.packId ?? "");
  const pendingState = String(pendingChange?.to ?? "") as "enabled" | "disabled";
  const canConfirm = result?.requiresConfirmation === true
    && pendingWorkspace === runtime?.workspaceId
    && Boolean(pendingPack)
    && ["enabled", "disabled"].includes(pendingState);

  return (
    <details className="progressiveDetails settingsProgressiveDetails" data-testid="settings-domain-packs-details" open>
      <summary><Bilingual zh="领域能力包" en="Domain Packs" /></summary>
      <div className="progressiveDetailsBody single">
        <section className="settingsDomainPackPanel" data-testid="settings-domain-packs-panel">
          <div className="tileHeader">
            <div>
              <h3><Bilingual zh="按工作区启用领域知识" en="Enable domain knowledge per workspace" /></h3>
              <p className="quietText">
                <Bilingual
                  zh="新工作区默认不启用任何领域能力。启停只影响后续规划，不会静默改写历史结果。"
                  en="New workspaces start with no domain knowledge. Changes affect future planning and never silently reinterpret historical results."
                />
              </p>
            </div>
            <span>{runtime?.enabledDomainPacks.length ?? 0}/{runtime?.availableDomainPacks.length ?? 0}</span>
          </div>
          <div className="domainPackList">
            {(runtime?.availableDomainPacks ?? []).map((pack) => {
              const nextState = pack.enabled ? "disabled" : "enabled";
              const busy = busyKey === `domain-pack-${pack.packId}-${nextState}`;
              return (
                <article className={pack.enabled ? "domainPackCard enabled" : "domainPackCard"} key={pack.packId}>
                  <div>
                    <strong>{biText(pack.displayName.zh, pack.displayName.en)}</strong>
                    <span>{pack.packId} · v{pack.version}</span>
                    <p>{biText(pack.description.zh, pack.description.en)}</p>
                    <div className="domainPackCapabilities">
                      {pack.capabilities.map((capability) => <small key={capability}>{capability}</small>)}
                    </div>
                  </div>
                  <div className="buttonRow tight">
                    <span className={pack.enabled ? "statusBadge ready" : "statusBadge"}>
                      {pack.enabled ? biText("已启用", "Enabled") : biText("未启用", "Disabled")}
                    </span>
                    <button
                      className="miniButton"
                      data-testid={`domain-pack-preview-${pack.packId}`}
                      disabled={busy || !pack.compatible}
                      onClick={() => onSetDomainPack({
                        packId: pack.packId,
                        state: nextState,
                        workspaceId: runtime?.workspaceId,
                        confirm: false,
                      })}
                      type="button"
                    >
                      {pack.enabled ? biText("预演停用", "Preview disable") : biText("预演启用", "Preview enable")}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
          {canConfirm ? (
            <div className="domainPackConfirmation" data-testid="domain-pack-confirmation">
              <span>{biText(`待确认：${pendingPack} → ${pendingState === "enabled" ? "启用" : "停用"}`, `Pending: ${pendingPack} → ${pendingState}`)}</span>
              <button
                className="primaryButton"
                data-testid={`domain-pack-confirm-${pendingPack}`}
                disabled={busyKey === `domain-pack-${pendingPack}-${pendingState}`}
                onClick={() => onSetDomainPack({
                  packId: pendingPack,
                  state: pendingState,
                  workspaceId: runtime?.workspaceId,
                  confirm: true,
                })}
                type="button"
              >
                <Bilingual zh="确认应用" en="Confirm change" />
              </button>
            </div>
          ) : null}
        </section>
      </div>
    </details>
  );
}
