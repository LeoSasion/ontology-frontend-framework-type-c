import type { SourceWorkbenchProps } from "../sourceWorkbenchContracts";
import { useSourceWorkbenchState } from "../useSourceWorkbenchState";
import { SourceWorkbenchView } from "./SourceWorkbenchView";

export function SourceWorkbench(props: SourceWorkbenchProps) {
  const state = useSourceWorkbenchState(props);
  return <SourceWorkbenchView {...props} {...state} />;
}
