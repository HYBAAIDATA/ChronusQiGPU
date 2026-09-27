/**
 * Provenance / truth-class labels. Every number leaving the miner must carry one.
 * Never upgrade a class silently (theoretical → live, historical → live, etc.).
 */

export type TruthClass =
  | "live"
  | "measured"
  | "computed"
  | "simulated"
  | "theoretical"
  | "historical"
  | "unavailable"
  | "hypothesis";

export type ProvenanceEnvelope<T extends Record<string, unknown>> = T & {
  truth_class: TruthClass;
  source: string;
  timestamp: string;
};

export function provenanceWrap<T extends Record<string, unknown>>(
  payload: T,
  truthClass: TruthClass,
  source: string,
): ProvenanceEnvelope<T> {
  return {
    ...payload,
    truth_class: truthClass,
    source,
    timestamp: new Date().toISOString(),
  };
}
