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
};

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
