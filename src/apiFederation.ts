import { fetchJsonStrict } from "./apiClient";
import type { FederationProof, FederationProofRequest } from "./typesFederation";

export function proveFederationPlan(options: FederationProofRequest, signal?: AbortSignal) {
  return fetchJsonStrict<FederationProof>("/api/connectors/federation-proof", {
    method: "POST",
    body: JSON.stringify(options),
    signal,
  });
}
