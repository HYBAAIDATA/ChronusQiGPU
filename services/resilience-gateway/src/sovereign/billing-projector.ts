import type { StoredCommandEvent } from "./event-store.js";

export type MetricBoundary = "physical" | "theoretical" | "outcome";

export interface UsageRecord {
  eventId: string;
  tenantId: string;
  boundary: MetricBoundary;
  metric: string;
  quantity: number;
  billable: boolean;
  evidenceHash: string;
}

const ALLOWED_METRICS: Record<MetricBoundary, ReadonlySet<string>> = {
  physical: new Set(["energy_joules", "gpu_seconds", "cpu_seconds"]),
  theoretical: new Set(["quantum_iterations", "heuristic_depth"]),
  outcome: new Set(["verified_solution", "accepted_share", "settled_command"]),
};

/**
 * Out-of-band projector: call from an isolated worker reading the immutable
 * event journal. Application request handlers must never increment invoices.
 */
export function projectUsage(event: StoredCommandEvent): UsageRecord | null {
  if (event.type !== "EXECUTION_MEASURED" && event.type !== "OUTCOME_VERIFIED") {
    return null;
  }
  const boundary = event.payload.boundary;
  const metric = event.payload.metric;
  const quantity = event.payload.quantity;
  if (
    (boundary !== "physical" &&
      boundary !== "theoretical" &&
      boundary !== "outcome") ||
    typeof metric !== "string" ||
    typeof quantity !== "number" ||
    !Number.isFinite(quantity) ||
    quantity < 0 ||
    !ALLOWED_METRICS[boundary].has(metric)
  ) {
    throw new Error("invalid usage event boundary");
  }
  return {
    eventId: event.eventId,
    tenantId: event.tenantId,
    boundary,
    metric,
    quantity,
    billable: boundary === "outcome" && event.type === "OUTCOME_VERIFIED",
    evidenceHash: event.eventHash,
  };
}