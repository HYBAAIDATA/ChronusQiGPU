/**
 * Live mining evidence published by the miner itself (`/api/v1/mining/evidence`).
 *
 * Nothing here is synthesised: a missing value stays `null` and renders as
 * "not reported", never as zero. Each row carries the truth class of its source.
 */
import type { TruthClass } from "./truth";

export type EvidenceRecovery = {
  authority?: string;
  mode?: string;
  salamander_supervisor_alive?: boolean;
  open?: Array<{ recovery_id: string; state: string; commands: string[] }>;
  recent?: Array<{ recovery_id: string; state: string; failure?: string | null }>;
};

export type EvidenceExecution = {
  executed?: boolean;
  reason?: string | null;
  plan_source?: string;
  plan_id?: string | null;
  plan_fallback_reason?: string | null;
  lease_id?: string;
  generation?: number;
  pool_session_id?: string;
  execution_id?: string;
  candidate_id?: string | null;
  submission_id?: string | null;
  requested_route?: string | null;
  executed_route?: string | null;
  route_fallback_reason?: string | null;
  evidence_class?: string;
  completion_state?: string;
  device_name?: string | null;
  kernel_launch_count?: number;
  attempts?: number;
  pool_outcome?: string;
};

export type MiningEvidence = {
  schema?: string;
  evidence_available?: boolean;
  worker_live?: boolean;
  reason?: string;
  observed_at?: number;
  agentic?: {
    agentic_state?: string;
    admission_block_reason?: string | null;
    lookahead?: number;
    lookahead_max?: number;
    precompute_waste_ratio?: number | null;
    plans_created?: number;
    plans_consumed?: number;
    plans_invalidated?: number;
    work_identity?: { generation?: number; job_id?: string; pool_session_id?: string } | null;
  };
  last_execution?: EvidenceExecution | null;
  recovery?: EvidenceRecovery;
  execution_backend?: {
    backend?: string | null;
    device?: string | null;
    fallback_reason?: string | null;
    route?: string;
  };
  session?: { state?: string; share_log_tail?: Array<{ state?: string; submission_id?: string }> };
  intelligence?: EvidenceIntelligence;
};

export type EvidenceIntelligence = {
  policy_mode?: string;
  window_ceiling?: number;
  max_window_seconds?: number;
  world?: {
    invalidation_rate?: { per_hour_mean?: number; observed_events?: number };
    routes?: Record<
      string,
      { overhead_ms?: number | null; hash_rate_hs?: number | null; method?: string; fit_samples?: number }
    >;
  };
  decision?: {
    window?: number;
    lookahead?: number;
    source?: string;
    reason?: string;
    expected?: { loss?: number; legacy_loss?: number };
  } | null;
  loss?: {
    wall_seconds?: number;
    fractions?: Record<string, number | null>;
    time_to_first_hash_ms?: { p50?: number; p90?: number; samples?: number } | null;
  };
  memory?: { backend?: string; ledger_verified?: boolean; entries?: number; last_error?: string | null } | null;
};

const LOSS_LABELS: Record<string, string> = {
  useful_hashing: "Useful hashing",
  stale_hashing: "Stale hashing",
  window_overhead: "Window overhead",
  idle_no_plan: "Waiting for a plan",
  recovery: "Recovery",
  unattributed_execution: "Unattributed execution",
  other: "Outside execution",
};

export type LossShare = { key: string; label: string; fraction: number };

/** Where wall time went, largest first; unmeasured categories are omitted, not zeroed. */
export function lossBreakdown(evidence?: MiningEvidence | null): LossShare[] {
  const fractions = evidence?.intelligence?.loss?.fractions;
  if (!fractions) return [];
  return Object.entries(fractions)
    .filter((entry): entry is [string, number] => typeof entry[1] === "number" && entry[1] > 0)
    .map(([key, fraction]) => ({ key, label: LOSS_LABELS[key] ?? key, fraction }))
    .sort((a, b) => b.fraction - a.fraction);
}

const formatRate = (hs?: number | null): string | null => {
  if (hs == null) return null;
  if (hs >= 1e6) return `${(hs / 1e6).toFixed(2)} MH/s`;
  if (hs >= 1e3) return `${(hs / 1e3).toFixed(1)} kH/s`;
  return `${hs.toFixed(0)} H/s`;
};

export function intelligenceRows(evidence?: MiningEvidence | null): EvidenceRow[] {
  const intel = evidence?.intelligence;
  if (!evidence || evidence.evidence_available !== true || !intel) return [];
  const route = evidence.execution_backend?.route;
  const learned = route ? intel.world?.routes?.[route] : undefined;
  const decision = intel.decision ?? undefined;
  const firstHash = intel.loss?.time_to_first_hash_ms;
  const memory = intel.memory ?? undefined;
  const model = decision?.source === "model";
  return [
    row("policy_window", "Chosen window", decision?.window, model ? "computed" : "live"),
    row("policy_source", "Decision source", decision?.source, "live"),
    row("policy_reason", "Why", decision?.reason, "computed"),
    row("ceiling", "Window ceiling", intel.window_ceiling, "live"),
    row(
      "overhead",
      "Per-window overhead",
      learned?.overhead_ms == null ? null : `${learned.overhead_ms.toFixed(3)} ms (${learned.method})`,
      "measured",
    ),
    row("hash_rate", "Learned hash rate", formatRate(learned?.hash_rate_hs), "measured"),
    row(
      "invalidations",
      "Invalidations / hour",
      intel.world?.invalidation_rate?.per_hour_mean == null
        ? null
        : intel.world.invalidation_rate.per_hour_mean.toFixed(1),
      "measured",
    ),
    row(
      "first_hash",
      "Time to first hash (p50)",
      firstHash?.p50 == null ? null : `${firstHash.p50.toFixed(1)} ms`,
      "measured",
    ),
    row(
      "memory",
      "Aethel memory",
      memory == null
        ? null
        : memory.ledger_verified
          ? `verified · ${memory.entries ?? 0} entries`
          : `unverified${memory.last_error ? ` · ${memory.last_error}` : ""}`,
      "live",
    ),
  ];
}

export type EvidenceRow = {
  key: string;
  label: string;
  value: string | number | null;
  truth: TruthClass;
};

const missing = (value: unknown): boolean => value === undefined || value === null || value === "";

function row(
  key: string,
  label: string,
  value: string | number | null | undefined,
  truth: TruthClass,
): EvidenceRow {
  return { key, label, value: missing(value) ? null : (value as string | number), truth: missing(value) ? "unavailable" : truth };
}

export function evidenceRows(evidence?: MiningEvidence | null): EvidenceRow[] {
  if (!evidence || evidence.evidence_available !== true) return [];
  const exec = evidence.last_execution ?? undefined;
  const agentic = evidence.agentic;
  const backend = evidence.execution_backend;
  const hardware = exec?.evidence_class === "HARDWARE_EXECUTED";
  const waste = agentic?.precompute_waste_ratio;
  return [
    row("backend", "Execution backend", backend?.device ?? backend?.backend, "live"),
    row("route", "Planned route", backend?.route, "live"),
    row("executed_route", "Executed route", exec?.executed_route, hardware ? "measured" : "computed"),
    row("route_fallback", "Route fallback", exec?.route_fallback_reason, "measured"),
    row("evidence_class", "Evidence class", exec?.evidence_class, hardware ? "measured" : "computed"),
    row("plan_source", "Plan source", exec?.plan_source, "live"),
    row("plan_fallback", "Why no agentic plan", exec?.plan_fallback_reason, "live"),
    row("generation", "Stratum generation", exec?.generation ?? agentic?.work_identity?.generation, "live"),
    row("lease", "Nonce lease", exec?.lease_id, "live"),
    row("pool_outcome", "Pool outcome", exec?.pool_outcome, "live"),
    row("lookahead", "Lookahead", agentic?.lookahead != null ? `${agentic.lookahead} / ${agentic.lookahead_max ?? "?"}` : null, "computed"),
    row("waste", "Precompute waste", waste == null ? null : `${(waste * 100).toFixed(1)}%`, "measured"),
    row("recovery_mode", "Recovery mode", evidence.recovery?.mode, "live"),
    row("session", "Session state", evidence.session?.state, "live"),
  ];
}

export function evidenceAlert(evidence?: MiningEvidence | null): string | null {
  if (!evidence || evidence.evidence_available !== true) return "MINING EVIDENCE UNAVAILABLE";
  if (evidence.worker_live === false) return "MINER NOT LIVE — SHOWING LAST PUBLISHED EVIDENCE";
  const mode = evidence.recovery?.mode;
  if (mode === "FAULTED") return "RECOVERY FAILED — SALAMANDER FAULTED";
  if (mode && mode !== "NORMAL" && mode !== "DE_RATE") return `SALAMANDER ${mode}`;
  if (evidence.last_execution?.route_fallback_reason) {
    return `ROUTE FALLBACK: ${evidence.last_execution.route_fallback_reason}`;
  }
  if (evidence.agentic?.admission_block_reason) {
    return `PRECOMPUTE BLOCKED: ${evidence.agentic.admission_block_reason}`;
  }
  return null;
}
