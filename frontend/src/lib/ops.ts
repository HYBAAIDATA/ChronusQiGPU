/** Canonical operational-telemetry contract (pythia.ops_telemetry/1).
 *
 * Every field mirrors the backend document. ``available: false`` plus a
 * ``reason`` means the backend has no truth for that section — the UI must
 * render it as unavailable, never substitute a value (spec §2).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { apiFetch, apiUrl } from "./api";
import type { StratumStatus, WorkerPublic } from "./status";

export type PoolEndpointTopo = {
  index: number;
  name: string;
  endpoint: string;
  tls: boolean;
  extranonce_subscribe: boolean;
  worker: string | null;
  active: boolean;
};

export type PoolTopology = {
  schema?: string;
  endpoints: PoolEndpointTopo[];
  endpoint_index: number | null;
  active: string | null;
  connect_attempts: number;
  last_error: string | null;
  last_selected: {
    at?: number;
    event?: string;
    pool?: string;
    endpoint?: string;
    index?: number;
    attempt?: number;
    previous_failures?: string[];
  } | null;
  history: Array<Record<string, unknown>>;
};

export type ConfiguredPool = {
  endpoint?: string;
  worker?: string;
  enabled?: boolean;
  password_committed?: boolean;
};

export type HashingSample = {
  hashrate_hs?: number | null;
  hashes_total?: number | null;
  hashes_in_span?: number | null;
  span_s?: number | null;
  executions_total?: number | null;
  shares_accepted?: number | null;
  stale_candidates_dropped?: number | null;
  backend?: string | null;
};

export type ShareLogEntry = {
  job_id?: string | null;
  block_hash?: string | null;
  submission_id?: string | null;
  sent_at?: number | null;
  outcome?: boolean | null;
  state?: string | null;
} & Record<string, unknown>;

export type StoreEvidence = {
  path: string | null;
  exists: boolean;
  size_bytes: number | null;
  modified_at: string | null;
  reason?: string;
};

export type StratumEvent = {
  seq?: number;
  at?: number;
  kind?: string;
} & Record<string, unknown>;

export type OpsTelemetry = {
  schema: string;
  generated_at: string;
  sources?: Record<string, string>;
  system: {
    supervisor_started_at?: string;
    uptime_s?: number;
    ready_to_mine: boolean;
    ready_reason?: string;
    workers?: Record<string, WorkerPublic>;
  };
  pool: {
    available: boolean;
    state?: string | null;
    primary?: StratumStatus["primary"];
    lifecycle?: {
      transport_connected?: boolean;
      subscribed?: boolean;
      authorized?: boolean;
      job_available?: boolean;
      target_available?: boolean;
      mining_active?: boolean;
      submission_ready?: boolean;
      submission_permitted?: boolean;
    } | null;
    topology?: PoolTopology | null;
    session_id?: string | null;
    protocol?: string | null;
    configured?: ConfiguredPool[];
  };
  job: {
    available: boolean;
    reason?: string | null;
    active?: boolean;
    generation?: number | null;
    invalidated_generation?: number | null;
    job_id?: string | null;
    fingerprint?: string | null;
    received_at?: number | null;
    age_ms?: number | null;
    clean_jobs?: boolean | null;
    difficulty?: string | number | null;
    difficulty_source?: string | null;
    difficulty_received_at?: number | null;
    share_target?: string | null;
    target_generation?: number | null;
    prevhash?: string | null;
    version?: string | null;
    nbits?: string | null;
    ntime?: string | null;
    extranonce1?: string | null;
    extranonce2_size?: number | null;
    merkle_branch?: string[] | null;
    coinb1?: string | null;
    coinb2?: string | null;
    block_height?: number | null;
  };
  execution: {
    device: { bound: boolean; mmio_bridge_configured: boolean; execution_device?: string | null; reason?: string | null };
    backend?: Record<string, unknown> | null;
    hashing: HashingSample | null;
  };
  shares: {
    counters?: StratumStatus["counters"] | null;
    outcomes?: {
      candidate_total?: number;
      accepted_ratio?: number | null;
      rejected_ratio?: number | null;
      unknown_ratio?: number | null;
      stale_ratio?: number | null;
      stale_dropped?: number;
    } | null;
    submission?: StratumStatus["submission"] & {
      rtt_ms?: { last?: number; mean?: number; p95?: number; samples?: number };
    };
    session: { available: boolean; state?: string | null; share_count?: number | null; share_log?: ShareLogEntry[] };
  };
  events: {
    available: boolean;
    reason?: string | null;
    last_seq?: number | null;
    totals?: Record<string, number> | null;
    events: StratumEvent[];
  };
  healing: {
    autonomous_supervisor?: Record<string, unknown>;
    recovery?: Record<string, unknown> | null;
    /** The Salamander engine's measured step() result — absent unless the
        worker is actually reporting. */
    salamander?: Record<string, unknown> | null;
    workers?: Record<string, { state: string; liveness: boolean; readiness: boolean }>;
  };
  security: {
    available?: boolean;
    reason?: string;
    /** Evaluated gate answer an unauthenticated caller provably sees. */
    gate?: {
      allowed?: boolean;
      reason?: string;
      policy_version?: string;
      evaluated_at?: number;
      available?: boolean;
    };
  } & Record<string, unknown>;
  history: {
    telemetry_history: StoreEvidence & { record_tail?: HistoryRecord[] };
    causal_ledger: StoreEvidence;
    mining_session: StoreEvidence & { share_count?: number | null };
  };
};

export type HistoryRecord = {
  seq?: number;
  at?: number;
  kind?: string;
  data?: Record<string, unknown>;
};

export type CausalTail = {
  schema?: string;
  available: boolean;
  reason?: string | null;
  store?: StoreEvidence;
  count?: number;
  records?: Array<{
    seq?: number;
    at?: number;
    kind?: string;
    coordinate?: Record<string, unknown>;
    detail?: Record<string, unknown>;
    software_revision?: string;
  }>;
};

export type TelemetryHistory = {
  schema?: string;
  available: boolean;
  reason?: string | null;
  store?: StoreEvidence;
  count?: number;
  records?: HistoryRecord[];
};

export type MiningSessionDoc = {
  schema?: string;
  available: boolean;
  reason?: string | null;
  store?: StoreEvidence;
  state?: string | null;
  cycles?: number | null;
  history?: string[] | null;
  last_block_hash?: string | null;
  share_count?: number | null;
  share_log?: ShareLogEntry[];
  pending?: Record<string, unknown> | null;
};

export type OpsTransport = "sse" | "poll" | "unreachable";

export type OpsFeed = {
  ops: OpsTelemetry | null;
  transport: OpsTransport;
  /** ms since the last frame/fetch completed; null before the first update. */
  ageMs: number | null;
  /** True once the feed has gone quiet past the freshness bound. */
  stale: boolean;
};

const POLL_MS = 3000;
const STALE_MS = 9000;

/**
 * Live ops telemetry: the SSE channel when the control plane answers it,
 * bounded polling otherwise. The consumer sees `ageMs`/`stale` so a dead
 * feed is visibly stale rather than silently frozen (spec §11).
 */
export function useOpsTelemetry(): OpsFeed {
  const [ops, setOps] = useState<OpsTelemetry | null>(null);
  const [transport, setTransport] = useState<OpsTransport>("poll");
  const [lastAt, setLastAt] = useState<number | null>(null);
  const [ageMs, setAgeMs] = useState<number | null>(null);
  const lastAtRef = useRef<number | null>(null);

  const mark = useCallback((doc: OpsTelemetry) => {
    setOps(doc);
    lastAtRef.current = Date.now();
    setLastAt(Date.now());
    setAgeMs(0);
  }, []);

  const poll = useCallback(async () => {
    try {
      const res = await apiFetch("/api/v1/telemetry/ops");
      if (res.ok) {
        mark((await res.json()) as OpsTelemetry);
        setTransport((t) => (t === "sse" ? t : "poll"));
      }
    } catch {
      setTransport((t) => (ops === null ? "unreachable" : t));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mark]);

  useEffect(() => {
    let source: EventSource | null = null;
    let closed = false;
    try {
      source = new EventSource(apiUrl("/api/v1/telemetry/stream"));
      source.onmessage = (msg) => {
        try {
          const frame = JSON.parse(msg.data) as { ops?: OpsTelemetry };
          if (frame?.ops) {
            mark(frame.ops);
            setTransport("sse");
          }
        } catch {
          // A malformed frame is dropped, never replaced by a value.
        }
      };
      source.onerror = () => {
        // The stream closes by design every ~3 minutes (bounded lifetime);
        // EventSource reconnects itself. If the endpoint is gone entirely
        // the poll loop still keeps the projection honest.
        setTransport((t) => (t === "sse" ? "poll" : t));
      };
    } catch {
      source = null;
    }
    void poll();
    const pollTimer = window.setInterval(() => {
      const last = lastAtRef.current;
      // Skip the fetch while the SSE frame cadence is healthy.
      if (transport === "sse" && last !== null && Date.now() - last < STALE_MS) return;
      void poll();
    }, POLL_MS);
    const ageTimer = window.setInterval(() => {
      const last = lastAtRef.current;
      setAgeMs(last === null ? null : Date.now() - last);
    }, 1000);
    return () => {
      closed = true;
      source?.close();
      window.clearInterval(pollTimer);
      window.clearInterval(ageTimer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    ops,
    transport,
    ageMs,
    stale: ageMs !== null && ageMs > STALE_MS,
  };
}
