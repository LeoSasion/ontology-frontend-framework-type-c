import type { DataConnectorConfig } from "./types";
import { biText } from "./components/Bilingual";
import { splitCsv } from "./sourceWorkbenchModel";

export type WorkbenchOperationReceipt = {
  title: string;
  detail: string;
  nextStep: string;
  technical: string;
  tone: "ok" | "warn";
};

type ImportPreviewReceiptOptions = {
  filePath: string;
  targetTable: string;
  importMode: string;
  uniqueFields: string;
  conflictRule: string;
};

type DurableImportQueuedReceiptOptions = {
  jobKey: string;
  planFingerprint: string;
  importKind: "single" | "folder";
  fileCount?: number;
  tableCount?: number;
};

type ImportPolicyReceiptOptions = {
  confirm: boolean;
  targetTable: string;
  uniqueFields: string;
  conflictRule: string;
};

type ConnectorSaveReceiptOptions = {
  confirm: boolean;
  connectorName: string;
  connectorTargetTable: string;
  connectorEndpoint: string;
  connectorImportMode: string;
  connectorUniqueFields: string;
  connectorConflictRule: string;
};

export function buildImportPreviewReceipt({
  filePath,
  targetTable,
  importMode,
  uniqueFields,
  conflictRule,
}: ImportPreviewReceiptOptions): WorkbenchOperationReceipt {
  return {
    title: biText("文件检查已完成", "File check completed"),
    detail: biText("下方会显示能否读取、会新建还是合并，以及确认后大约影响多少行。", "The summary below shows readability, create-or-merge target, and expected row impact after confirmation."),
    nextStep: biText("先看影响摘要；没有重复键和空键时再预演或确认导入。", "Review the impact summary first. Preview or confirm import once duplicate and empty keys are clear."),
    technical: `${filePath} -> ${targetTable}; mode=${importMode}; unique=${splitCsv(uniqueFields).join(",") || "auto"}; conflict=${conflictRule}`,
    tone: "ok",
  };
}

export function buildDurableImportQueuedReceipt({
  jobKey,
  planFingerprint,
  importKind,
  fileCount = 0,
  tableCount = 0,
}: DurableImportQueuedReceiptOptions): WorkbenchOperationReceipt {
  const folder = importKind === "folder";
  return {
    title: folder
      ? biText("文件夹导入已进入持久队列", "Folder import entered the durable queue")
      : biText("导入任务已进入持久队列", "Import job entered the durable queue"),
    detail: folder
      ? biText(`计划包含 ${fileCount} 个文件、${tableCount} 张业务表。`, `The plan contains ${fileCount} files and ${tableCount} business tables.`)
      : biText("可以查看阶段进度或取消；完成前不会把部分结果标记为成功。", "Track stages or cancel; partial work is never reported as successful."),
    nextStep: folder
      ? biText("阶段进度会在下方更新；需要人工处理时不会自动重试写入。", "Stage progress updates below; writes do not auto-retry when attention is required.")
      : biText("任务完成后只刷新当前工作区的数据源状态。", "Only active-workspace source state refreshes after completion."),
    technical: `job=${jobKey}; plan=${planFingerprint}`,
    tone: "ok",
  };
}

export function buildImportPolicyReceipt({
  confirm,
  targetTable,
  uniqueFields,
  conflictRule,
}: ImportPolicyReceiptOptions): WorkbenchOperationReceipt {
  return {
    title: confirm ? biText("导入策略已保存", "Import policy saved") : biText("导入策略预演完成", "Import policy preview ready"),
    detail: confirm
      ? biText(`后续导入 ${targetTable} 会默认使用这套唯一键和冲突规则。`, `Future imports into ${targetTable} will use this unique-key and conflict rule by default.`)
      : biText("这次只检查策略影响，不会改默认规则。", "This only checks policy impact and does not change defaults."),
    nextStep: biText("继续检查文件，确认这套策略是否能正确处理重复行。", "Continue with file check and confirm whether this policy handles duplicate rows correctly."),
    technical: `table=${targetTable}; unique=${splitCsv(uniqueFields).join(",") || "auto"}; conflict=${conflictRule}; confirm=${confirm}`,
    tone: confirm ? "ok" : "warn",
  };
}

export function buildConnectorSaveReceipt({
  confirm,
  connectorName,
  connectorTargetTable,
  connectorEndpoint,
  connectorImportMode,
  connectorUniqueFields,
  connectorConflictRule,
}: ConnectorSaveReceiptOptions): WorkbenchOperationReceipt {
  return {
    title: confirm ? biText("连接配置已保存", "Connection saved") : biText("连接保存预演完成", "Connection save preview ready"),
    detail: confirm
      ? biText(`已保存“${connectorName}”，同步时会把来源写入 ${connectorTargetTable || "目标表"}。`, `"${connectorName}" is saved. Sync writes the source into ${connectorTargetTable || "the target table"}.`)
      : biText("这次只检查连接配置，不会创建或覆盖数据。", "This only checks the connection setup and does not create or overwrite data."),
    nextStep: confirm ? biText("下一步先预演同步，再确认写入。", "Next, preview sync before confirming writes.") : biText("确认配置无误后再保存连接。", "Save the connection after the setup looks right."),
    technical: `endpoint=${connectorEndpoint}; table=${connectorTargetTable}; mode=${connectorImportMode}; unique=${splitCsv(connectorUniqueFields).join(",") || "auto"}; conflict=${connectorConflictRule}; confirm=${confirm}`,
    tone: confirm ? "ok" : "warn",
  };
}

export function buildConnectorSyncReceipt(connector: DataConnectorConfig, confirm: boolean, result: Record<string, unknown> = {}): WorkbenchOperationReceipt {
  const target = String(connector.config?.targetTableKey ?? "-");
  const syncPlan = result.syncPlan && typeof result.syncPlan === "object" && !Array.isArray(result.syncPlan)
    ? result.syncPlan as Record<string, unknown>
    : null;
  const connectorSync = result.connectorSync && typeof result.connectorSync === "object" && !Array.isArray(result.connectorSync)
    ? result.connectorSync as Record<string, unknown>
    : null;
  const adapter = connectorSync?.adapter && typeof connectorSync.adapter === "object" && !Array.isArray(connectorSync.adapter)
    ? connectorSync.adapter as Record<string, unknown>
    : null;
  const adapterId = String(syncPlan?.adapterId ?? adapter?.adapterId ?? "-");
  const planFingerprint = String(result.planFingerprint ?? adapter?.planFingerprint ?? "");
  const resource = syncPlan?.resource && typeof syncPlan.resource === "object" && !Array.isArray(syncPlan.resource)
    ? syncPlan.resource as Record<string, unknown>
    : null;
  return {
    title: confirm ? biText("同步已确认", "Sync confirmed") : biText("同步影响已预演", "Sync impact previewed"),
    detail: confirm
      ? biText(`连接“${connector.name}”会写入 ${target}，完成后可继续生成证据摘要。`, `Connection "${connector.name}" writes into ${target}. Create an evidence summary after it completes.`)
      : biText(`连接“${connector.name}”已通过只读 Adapter 检查；确认前不会写入 ${target}。`, `Connection "${connector.name}" passed the read-only Adapter check. Nothing writes to ${target} before confirmation.`),
    nextStep: confirm ? biText("同步后检查数据表，再更新看板或证据摘要。", "After sync, check the table, then refresh dashboards or evidence summaries.") : biText("确认来源和目标表正确后再同步。", "Confirm source and target table before syncing."),
    technical: `connector=${connector.connectorKey}; target=${target}; confirm=${confirm}; status=${connector.status}; adapter=${adapterId}; source=${String(resource?.label ?? "-")}; plan=${planFingerprint.slice(0, 12) || "-"}`,
    tone: confirm ? "ok" : "warn",
  };
}

export function buildConnectorRemoveReceipt(connector: DataConnectorConfig): WorkbenchOperationReceipt {
  return {
    title: biText("连接删除已确认", "Connection delete confirmed"),
    detail: biText(`已删除连接“${connector.name}”；这不会删除外部源目录里的文件。`, `Connection "${connector.name}" was removed. This does not delete files in external source folders.`),
    nextStep: biText("如需重新同步，请新建连接并先预演。", "Create a new connection and preview sync if you need it again."),
    technical: `connector=${connector.connectorKey}; confirm=true`,
    tone: "warn",
  };
}
