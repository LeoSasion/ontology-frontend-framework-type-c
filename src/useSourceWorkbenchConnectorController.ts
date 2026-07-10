import { useEffect, useState } from "react";
import type { DataConnectorConfig } from "./types";
import type { SourceWorkbenchProps } from "./sourceWorkbenchContracts";
import { buildConnectorOptions } from "./sourceWorkbenchCommandModel";
import {
  buildConnectorRemoveReceipt,
  buildConnectorSaveReceipt,
  buildConnectorSyncReceipt,
  type WorkbenchOperationReceipt,
} from "./sourceWorkbenchReceiptModel";

type ConnectorControllerOptions = Pick<
  SourceWorkbenchProps,
  "onSaveConnector" | "onSyncConnector" | "onRemoveConnector"
> & {
  firstTableKey: string;
  tableKeySet: ReadonlySet<string>;
};

export function useSourceWorkbenchConnectorController({
  firstTableKey,
  tableKeySet,
  onSaveConnector,
  onSyncConnector,
  onRemoveConnector,
}: ConnectorControllerOptions) {
  const [connectorEditingKey, setConnectorEditingKey] = useState("");
  const [connectorName, setConnectorName] = useState("文件同步");
  const [connectorType, setConnectorType] = useState("file");
  const [connectorProvider, setConnectorProvider] = useState("local-file");
  const [connectorStatus, setConnectorStatus] = useState("draft");
  const [connectorEndpoint, setConnectorEndpoint] = useState("");
  const [connectorImportMode, setConnectorImportMode] = useState("auto");
  const [connectorTargetTable, setConnectorTargetTable] = useState(firstTableKey);
  const [connectorUniqueFields, setConnectorUniqueFields] = useState("");
  const [connectorConflictRule, setConnectorConflictRule] = useState("overwrite");
  const [connectorNotes, setConnectorNotes] = useState("");
  const [connectorOperationReceipt, setConnectorOperationReceipt] = useState<WorkbenchOperationReceipt | null>(null);

  useEffect(() => {
    if (!firstTableKey) return;
    setConnectorTargetTable((current) => tableKeySet.has(current) ? current : firstTableKey);
  }, [firstTableKey, tableKeySet]);

  function connectorOptions(confirm = false) {
    return buildConnectorOptions({
      connectorEditingKey,
      connectorName,
      connectorType,
      connectorProvider,
      connectorStatus,
      connectorEndpoint,
      connectorImportMode,
      connectorTargetTable,
      connectorUniqueFields,
      connectorConflictRule,
      connectorNotes,
      confirm,
    });
  }

  function loadConnector(connector: DataConnectorConfig) {
    setConnectorEditingKey(connector.connectorKey);
    setConnectorName(connector.name);
    setConnectorType(connector.type || "file");
    setConnectorProvider(connector.provider || "");
    setConnectorStatus(connector.status || "draft");
    setConnectorEndpoint(String(connector.config?.endpoint ?? ""));
    setConnectorImportMode(String(connector.config?.importMode ?? "auto"));
    setConnectorTargetTable(String(connector.config?.targetTableKey ?? ""));
    setConnectorUniqueFields((connector.config?.uniqueFields ?? []).join(", "));
    setConnectorConflictRule(String(connector.config?.conflictRule ?? "overwrite"));
    setConnectorNotes(String(connector.config?.notes ?? ""));
  }

  function resetConnectorDraft() {
    setConnectorEditingKey("");
    setConnectorName("文件同步");
    setConnectorType("file");
    setConnectorProvider("local-file");
    setConnectorStatus("draft");
    setConnectorEndpoint("");
    setConnectorImportMode("auto");
    setConnectorTargetTable(firstTableKey);
    setConnectorUniqueFields("");
    setConnectorConflictRule("overwrite");
    setConnectorNotes("");
  }

  async function runConnectorSaveAction(confirm: boolean) {
    await onSaveConnector(connectorOptions(confirm));
    setConnectorOperationReceipt(buildConnectorSaveReceipt({
      confirm,
      connectorName,
      connectorTargetTable,
      connectorEndpoint,
      connectorImportMode,
      connectorUniqueFields,
      connectorConflictRule,
    }));
  }

  async function runConnectorSyncAction(connector: DataConnectorConfig, confirm: boolean) {
    await onSyncConnector({ connector: connector.connectorKey, confirm });
    setConnectorOperationReceipt(buildConnectorSyncReceipt(connector, confirm));
  }

  async function runConnectorRemoveAction(connector: DataConnectorConfig) {
    await onRemoveConnector({ connector: connector.connectorKey, confirm: true });
    setConnectorOperationReceipt(buildConnectorRemoveReceipt(connector));
  }

  return {
    connectorEditingKey,
    connectorName,
    connectorType,
    connectorProvider,
    connectorStatus,
    connectorEndpoint,
    connectorImportMode,
    connectorTargetTable,
    connectorUniqueFields,
    connectorConflictRule,
    connectorNotes,
    connectorOperationReceipt,
    setConnectorName,
    setConnectorType,
    setConnectorProvider,
    setConnectorStatus,
    setConnectorEndpoint,
    setConnectorImportMode,
    setConnectorTargetTable,
    setConnectorUniqueFields,
    setConnectorConflictRule,
    setConnectorNotes,
    resetConnectorDraft,
    loadConnector,
    runConnectorSaveAction,
    runConnectorSyncAction,
    runConnectorRemoveAction,
  };
}
