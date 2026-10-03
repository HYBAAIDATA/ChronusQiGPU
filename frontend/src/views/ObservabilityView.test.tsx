import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { OpsTelemetry } from "@/lib/ops";
import {
  ExecutionCard,
  HealingCard,
  JobCard,
  PoolCard,
  ShareCard,
  SystemsCard,
} from "./ObservabilityView";

/** A complete ops document with every source reporting. */
const liveOps = (): OpsTelemetry => ({
  schema: "pythia.ops_telemetry/1",
  generated_at: "2026-10-03T14:00:00+00:00",
  system: {
    supervisor_started_at: "2026-10-03T13:00:00+00:00",
    uptime_s: 3600,
    ready_to_mine: true,
    workers: {
      "agentic-mining": {
        state: "running",
        since: "2026-10-03T13:00:00+00:00",
        attempts_total: 1,
        attempts_window: 1,
        last_heartbeat: "2026-10-03T14:00:00+00:00",
        liveness: true,
        readiness: true,
        effectiveness: { hashrate: 450_000, shares_accepted: 2 },
        last_error: null,
      },
      salamander: {
        state: "disabled",
        since: "2026-10-03T13:00:00+00:00",
        attempts_total: 0,
        attempts_window: 0,
        last_heartbeat: null,
        liveness: false,
        readiness: false,
        effectiveness: { hashrate: null, shares_accepted: 0 },
        last_error: null,
      },
    },
  },
  pool: {
    available: true,
    state: "READY",
    primary: {
      transport: "CONNECTED",
      subscribed: true,
      authorized: true,
      endpoint: "stratum.test:3333",
      worker: "ri***",
    },
    lifecycle: {
      transport_connected: true,
      subscription_confirmed: true,
      authorized: true,
      job_active: true,
      submission_ready: false,
    },
    session_id: "sess-1",
    protocol: "stratum_v1",
    topology: {
      endpoints: [
        { index: 0, name: "braiins", endpoint: "stratum.test:3333", tls: false, extranonce_subscribe: false, worker: "ri***", active: true },
        { index: 1, name: "viabtc", endpoint: "stratum2.test:443", tls: true, extranonce_subscribe: false, worker: "ri***", active: false },
      ],
      endpoint_index: 0,
      active: "braiins",
      connect_attempts: 2,
      last_error: null,
      last_selected: { pool: "braiins", index: 0, attempt: 2 },
      history: [
        { at: 1000, event: "refused", pool: "viabtc", stage: "connect", error: "viabtc: timed out" },
        { at: 1001, event: "selected", pool: "braiins", index: 0 },
      ],
    },
    configured: [{ endpoint: "stratum.test:3333", worker: "rig.telemetry", enabled: true }],
  },
  job: {
    available: true,
    active: true,
    generation: 7,
    job_id: "abc",
    fingerprint: "fp",
    received_at: 1_800_000_000,
    age_ms: 1500,
    clean_jobs: true,
    difficulty: 8192,
    difficulty_source: "mining.set_difficulty",
    share_target: "00ff",
    target_generation: 3,
    prevhash: "11".repeat(32),
    version: "20000000",
    nbits: "1d00ffff",
    ntime: "65abcdef",
    extranonce1: "01020304",
    extranonce2_size: 4,
    merkle_branch: ["cc", "dd"],
    coinb1: "01000000",
    coinb2: "ffffffff",
    block_height: 845_000,
  },
  execution: {
    device: { bound: true, mmio_bridge_configured: false, execution_device: "cpu", reason: null },
    backend: { backend: "cpu", route: "cpu_reference" },
    hashing: {
      hashrate_hs: 450_000,
      hashes_total: 1_000_000_000,
      hashes_in_span: 13_500_000,
      span_s: 30,
      executions_total: 40,
      shares_accepted: 2,
    },
  },
  shares: {
    counters: { jobs_received: 12, jobs_invalidated: 2, disconnects: 1, submitted: 3, accepted: 2, rejected: 1, unknown: 0 },
    outcomes: { candidate_total: 4, accepted_ratio: 0.5, rejected_ratio: 0.25, unknown_ratio: 0, stale_ratio: 0.25, stale_dropped: 1 },
    submission: { state: "IDLE", last_result: "ACCEPTED", rtt_ms: { last: 41.2, mean: 44, p95: 60, samples: 3 } },
    session: {
      available: true,
      state: "SEARCHING",
      share_count: 1,
      share_log: [{ job_id: "abc", block_hash: "00".repeat(32), submission_id: "sub-1", sent_at: 1_800_000_000, outcome: true, state: "ACCEPTED" }],
    },
  },
  events: {
    available: true,
    last_seq: 12,
    totals: { jobs_received: 12, submitted: 3, accepted: 2 },
    events: [{ seq: 12, at: 1_800_000_000, kind: "job", job_id: "abc" }],
  },
  healing: {
    autonomous_supervisor: { running: true, cycle_count: 4 },
    recovery: { mode: "NORMAL", freezes_speculation: false, faulted: false, active_recovery_id: null, open: [] },
    salamander: null,
    workers: {},
  },
  security: { available: true, status: "active" },
  history: {
    telemetry_history: { path: "telemetry_history.jsonl", exists: true, size_bytes: 1024, modified_at: "2026-10-03T14:00:00+00:00", record_tail: [{ seq: 1, at: 1_800_000_000, kind: "hashrate", data: { hashrate_hs: 450_000 } }] },
    causal_ledger: { path: "causal_ledger.jsonl", exists: true, size_bytes: 512, modified_at: "2026-10-03T14:00:00+00:00" },
    mining_session: { path: "mining_session.json", exists: true, size_bytes: 300, modified_at: "2026-10-03T14:00:00+00:00", share_count: 1 },
  },
});

const emptyOps = (): OpsTelemetry => ({
  schema: "pythia.ops_telemetry/1",
  generated_at: "2026-10-03T14:00:00+00:00",
  system: { ready_to_mine: false, ready_reason: "worker_unavailable" },
  pool: { available: false, state: null, configured: [] },
  job: { available: false, reason: "waiting for telemetry" },
  execution: {
    device: { bound: false, mmio_bridge_configured: false, execution_device: null, reason: "no mining device bound" },
    hashing: null,
  },
  shares: { session: { available: false } },
  events: { available: false, reason: "the mining worker has not published events yet", events: [] },
  healing: {},
  security: { available: false, reason: "guardian_dependency_unavailable" },
  history: {
    telemetry_history: { path: "telemetry_history.jsonl", exists: false, size_bytes: null, modified_at: null, reason: "no persisted records yet" },
    causal_ledger: { path: "causal_ledger.jsonl", exists: false, size_bytes: null, modified_at: null },
    mining_session: { path: "mining_session.json", exists: false, size_bytes: null, modified_at: null },
  },
});

describe("Observability surfaces (§17)", () => {
  it("renders 'Unavailable' fields when the backend has no truth", () => {
    const html = renderToStaticMarkup(
      <div>
        <PoolCard ops={emptyOps()} />
        <JobCard ops={emptyOps()} />
        <ExecutionCard ops={emptyOps()} />
        <ShareCard ops={emptyOps()} />
        <SystemsCard ops={emptyOps()} />
        <HealingCard ops={emptyOps()} />
      </div>,
    );
    expect(html).toContain("Not connected");
    expect(html).toContain("waiting for telemetry");
    expect(html).toContain("Unavailable");
    expect(html).toContain("Not running");
    // No fabricated values: nothing claims a rate, count, or endpoint.
    expect(html).not.toContain("H/s");
    expect(html).not.toContain("stratum.test");
  });

  it("projects live pool, job, and share truth verbatim", () => {
    const html = renderToStaticMarkup(
      <div>
        <PoolCard ops={liveOps()} />
        <JobCard ops={liveOps()} />
        <ExecutionCard ops={liveOps()} />
        <ShareCard ops={liveOps()} />
        <SystemsCard ops={liveOps()} />
        <HealingCard ops={liveOps()} />
      </div>,
    );
    expect(html).toContain("READY");
    expect(html).toContain("braiins");
    expect(html).toContain("stratum.test:3333");
    expect(html).toContain("stratum_v1");
    expect(html).toContain("sess-1");
    expect(html).toContain("450 kH/s");
    expect(html).toContain("8192");
    // Submitted ≠ accepted: the pipeline shows each stage separately.
    expect(html).toContain("candidates verified");
    expect(html).toContain("submitted");
    expect(html).toContain("stale dropped");
    // Failover history surfaces as events.
    expect(html).toContain("refused");
    expect(html).toContain("selected");
  });

  it("marks an old job visibly stale", () => {
    const ops = liveOps();
    ops.job.age_ms = 400_000;
    const html = renderToStaticMarkup(<JobCard ops={ops} />);
    expect(html).toContain("stale");
    expect(html).not.toContain("fresh");
  });

  it("distinguishes declared, bound, and executing substrates", () => {
    const idle = liveOps();
    // Bound device, measured hashrate zero — not executing.
    idle.execution.hashing = { hashrate_hs: 0, hashes_total: 10, span_s: 30 };
    const html = renderToStaticMarkup(<ExecutionCard ops={idle} />);
    expect(html).toContain("bound");
    expect(html).not.toContain(">executing<");

    const executing = liveOps();
    const htmlLive = renderToStaticMarkup(<ExecutionCard ops={executing} />);
    expect(htmlLive).toContain("executing");
  });

  it("never claims acceptance for an unacknowledged pipeline", () => {
    const ops = liveOps();
    ops.pool.lifecycle = {
      transport_connected: true,
      subscription_confirmed: true,
      authorized: true,
      job_active: true,
      submission_ready: false,
    };
    ops.shares.counters = { submitted: 0, accepted: 0, rejected: 0, unknown: 0 };
    const html = renderToStaticMarkup(<PoolCard ops={ops} />);
    // 'acknowledged' stage is idle — never marked complete by inference.
    expect(html).not.toMatch(/acknowledged[^<]*yes/i);
  });
});
