import React, { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  CircleDot,
  Database,
  GitBranch,
  HeartPulse,
  History,
  Layers,
  Radio,
  Server,
  ShieldCheck,
} from "lucide-react";
import { apiFetch } from "../lib/api";
import {
  useOpsTelemetry,
  type CausalTail,
  type OpsTelemetry,
  type PoolEndpointTopo,
  type ShareLogEntry,
} from "../lib/ops";

const NA = "Unavailable";

/** Render a value or the honest unavailable marker — never a substitute. */
const val = (v: unknown, suffix = ""): string => {
  if (v === null || v === undefined) return NA;
  if (typeof v === "number" && !Number.isFinite(v)) return NA;
  if (typeof v === "string" && v === "") return NA;
  return `${v}${suffix}`;
};

const fmtHs = (v: number | null | undefined): string => {
  if (v == null || !Number.isFinite(v) || v < 0) return NA;
  const units = ["H/s", "kH/s", "MH/s", "GH/s", "TH/s"];
  let x = v;
  let i = 0;
  while (x >= 1000 && i < units.length - 1) {
    x /= 1000;
    i++;
  }
  return `${x.toFixed(x >= 100 ? 0 : 2)} ${units[i]}`;
};

const fmtAge = (ms: number | null | undefined): string => {
  if (ms == null || !Number.isFinite(ms)) return NA;
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  return `${(ms / 60_000).toFixed(1)}min`;
};

const fmtTs = (v: number | string | null | undefined): string => {
  if (v == null) return NA;
  if (typeof v === "string") return v.slice(11, 19);
  return new Date(v * 1000).toISOString().slice(11, 19);
};

const truncate = (v: string | null | undefined, n = 24): string => {
  if (v == null || v === "") return NA;
  return v.length > n ? `${v.slice(0, n)}…` : v;
};

const JOB_FRESH_MS = 120_000;

const Row: React.FC<{ k: string; v: React.ReactNode; warn?: boolean }> = ({ k, v, warn }) => (
  <div className="flex justify-between gap-3">
    <dt className="text-[#6b7c93] shrink-0">{k}</dt>
    <dd
      className={`text-right break-all ${v === NA ? "text-[#8898aa] italic" : warn ? "text-[#b45309]" : "text-[#0a2540]"}`}
    >
      {v}
    </dd>
  </div>
);

const Card: React.FC<{
  icon: React.ReactNode;
  title: string;
  status?: React.ReactNode;
  children: React.ReactNode;
}> = ({ icon, title, status, children }) => (
  <div className="console-surface-inset p-4">
    <header className="flex items-center justify-between">
      <p className="text-[10px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93] flex items-center gap-2">
        <span className="text-[#635bff]">{icon}</span>
        {title}
      </p>
      {status}
    </header>
    <div className="mt-3">{children}</div>
  </div>
);

const BoolChip: React.FC<{ on: boolean | undefined | null; label: string }> = ({ on, label }) => (
  <span
    className={`px-1.5 py-0.5 rounded text-[9px] font-telemetry-mono uppercase tracking-wider ${
      on === true
        ? "bg-[#e4f5e9] text-[#1a7f37]"
        : on === false
          ? "bg-[#f1e5e5] text-[#b42318]"
          : "bg-[#eceef1] text-[#8898aa]"
    }`}
  >
    {label}: {on === true ? "yes" : on === false ? "no" : "n/a"}
  </span>
);

/* ── Pool card ─────────────────────────────────────────────────────────── */

const stageState = (done: boolean | undefined | null) =>
  done === true ? "complete" : done === false ? "blocked" : "idle";

export const PoolCard: React.FC<{ ops: OpsTelemetry }> = ({ ops }) => {
  const pool = ops.pool;
  const topo = pool.topology;
  const lc = pool.lifecycle ?? {};
  const primary = pool.primary ?? {};
  const stages: Array<{ label: string; state: string }> = [
    { label: "configured", state: (pool.configured ?? []).length > 0 || topo ? "complete" : "blocked" },
    { label: "connected", state: stageState(lc.transport_connected) },
    { label: "subscribed", state: stageState(lc.subscription_confirmed) },
    { label: "authorized", state: stageState(lc.authorized) },
    { label: "receiving work", state: stageState(lc.job_active) },
    {
      label: "submitting",
      state: stageState(lc.submission_ready ?? (primary as Record<string, unknown>).submitting as boolean),
    },
    {
      label: "acknowledged",
      state: stageState((ops.shares.counters?.accepted ?? 0) > 0 ? true : lc.submission_ready === true ? false : null),
    },
  ];

  return (
    <Card
      icon={<Server className="w-3.5 h-3.5" />}
      title="Pool — connection & failover"
      status={
        <span
          className={`text-[9px] font-telemetry-mono uppercase tracking-wider ${pool.available ? "text-[#1a7f37]" : "text-[#8898aa]"}`}
        >
          {pool.available ? val(pool.state) : "Not connected"}
        </span>
      }
    >
      <div className="flex flex-wrap gap-1 mb-3">
        {stages.map((s) => (
          <span
            key={s.label}
            className={`px-1.5 py-0.5 rounded text-[9px] font-telemetry-mono uppercase tracking-wider ${
              s.state === "complete"
                ? "bg-[#e4f5e9] text-[#1a7f37]"
                : s.state === "blocked"
                  ? "bg-[#f1e5e5] text-[#b42318]"
                  : "bg-[#eceef1] text-[#8898aa]"
            }`}
          >
            {s.label}
          </span>
        ))}
      </div>
      <dl className="space-y-1.5 text-[12px] font-telemetry-mono">
        <Row k="active pool" v={val(topo?.active)} />
        <Row
          k="endpoint"
          v={val(topo?.endpoints?.find((e) => e.active)?.endpoint ?? primary.endpoint)}
        />
        <Row k="protocol" v={val(pool.protocol)} />
        <Row k="session" v={truncate(pool.session_id, 18)} />
        <Row k="worker" v={val(primary.worker)} />
        <Row k="connect attempts" v={topo ? val(topo.connect_attempts) : NA} />
        <Row k="last error" v={val(topo?.last_error)} warn />
        <Row k="state" v={val(pool.state)} />
      </dl>
      {(topo?.endpoints ?? []).length > 0 && (
        <table className="mt-3 w-full text-[11px] font-telemetry-mono">
          <thead>
            <tr className="text-left text-[#8898aa] uppercase text-[9px] tracking-wider">
              <th className="pr-2 py-1">order</th>
              <th className="pr-2 py-1">pool</th>
              <th className="pr-2 py-1">endpoint</th>
              <th className="pr-2 py-1">tls</th>
              <th className="py-1 text-right">active</th>
            </tr>
          </thead>
          <tbody>
            {(topo?.endpoints ?? []).map((ep: PoolEndpointTopo) => (
              <tr key={ep.index} className={ep.active ? "text-[#0a2540]" : "text-[#6b7c93]"}>
                <td className="pr-2 py-0.5">{ep.index}</td>
                <td className="pr-2 py-0.5">{ep.name}</td>
                <td className="pr-2 py-0.5">{ep.endpoint}</td>
                <td className="pr-2 py-0.5">{ep.tls ? "yes" : "no"}</td>
                <td className="py-0.5 text-right">{ep.active ? "●" : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {(topo?.history ?? []).length > 0 && (
        <div className="mt-3 max-h-32 overflow-y-auto space-y-1">
          {[...(topo?.history ?? [])].reverse().map((h, i) => (
            <div key={i} className="text-[11px] font-telemetry-mono text-[#6b7c93]">
              <span className="text-[#8898aa]">{fmtTs(h.at as number)}</span>{" "}
              <span className={h.event === "refused" ? "text-[#b42318]" : "text-[#1a7f37]"}>
                {String(h.event)}
              </span>{" "}
              {String(h.pool ?? "")}
              {h.stage ? <span> · {String(h.stage)}</span> : null}
              {h.error ? <span className="text-[#8898aa]"> · {truncate(String(h.error), 60)}</span> : null}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
};

/* ── Job card ──────────────────────────────────────────────────────────── */

export const JobCard: React.FC<{ ops: OpsTelemetry }> = ({ ops }) => {
  const job = ops.job;
  const stale =
    job.available && job.age_ms != null && job.age_ms > JOB_FRESH_MS;
  const invalidated = job.invalidated_generation != null;
  return (
    <Card
      icon={<Layers className="w-3.5 h-3.5" />}
      title="Current job — work in flight"
      status={
        !job.available ? (
          <span className="text-[9px] font-telemetry-mono uppercase tracking-wider text-[#8898aa]">
            {job.reason ?? "No current job"}
          </span>
        ) : stale ? (
          <span className="text-[9px] font-telemetry-mono uppercase tracking-wider bg-[#fef3c7] text-[#b45309] px-1.5 py-0.5 rounded">
            stale — {fmtAge(job.age_ms)}
          </span>
        ) : (
          <span className="text-[9px] font-telemetry-mono uppercase tracking-wider text-[#1a7f37]">
            fresh — {fmtAge(job.age_ms)}
          </span>
        )
      }
    >
      <dl className="space-y-1.5 text-[12px] font-telemetry-mono">
        <Row k="job id" v={val(job.job_id)} />
        <Row k="generation" v={val(job.generation)} />
        <Row k="invalidated gen" v={val(job.invalidated_generation)} warn={invalidated} />
        <Row k="fingerprint" v={truncate(job.fingerprint, 20)} />
        <Row k="received" v={fmtTs(job.received_at)} />
        <Row k="age" v={val(job.age_ms, "ms")} warn={stale} />
        <Row k="clean_jobs" v={job.clean_jobs == null ? NA : job.clean_jobs ? "true" : "false"} />
        <Row k="difficulty" v={val(job.difficulty)} />
        <Row k="difficulty source" v={truncate(job.difficulty_source, 28)} />
        <Row k="share target" v={truncate(job.share_target, 26)} />
        <Row k="prevhash" v={truncate(job.prevhash, 26)} />
        <Row k="version / nbits" v={job.version || job.nbits ? `${job.version ?? "?"} / ${job.nbits ?? "?"}` : NA} />
        <Row k="ntime" v={val(job.ntime)} />
        <Row
          k="extranonce"
          v={job.extranonce1 ? `${job.extranonce1} (+${job.extranonce2_size ?? "?"}B)` : NA}
        />
        <Row
          k="merkle branch"
          v={job.merkle_branch ? `${job.merkle_branch.length} nodes` : NA}
        />
        <Row k="coinbase" v={job.coinb1 && job.coinb2 ? `${truncate(job.coinb1, 10)}…${truncate(job.coinb2, 10)}` : NA} />
        <Row k="block height" v={val(job.block_height)} />
      </dl>
    </Card>
  );
};

/* ── Execution card ────────────────────────────────────────────────────── */

export const ExecutionCard: React.FC<{ ops: OpsTelemetry }> = ({ ops }) => {
  const dev = ops.execution.device;
  const hashing = ops.execution.hashing;
  // Executing = the worker published a measured non-zero hashrate on the
  // declared device — not inferred from configuration (§5).
  const executing = hashing != null && (hashing.hashrate_hs ?? 0) > 0;
  return (
    <Card
      icon={<CircleDot className="w-3.5 h-3.5" />}
      title="Execution substrate — declared ≠ bound ≠ executing"
      status={
        <span className="text-[9px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93]">
          {dev.bound ? (executing ? "executing" : "bound") : "Not running"}
        </span>
      }
    >
      <div className="flex flex-wrap gap-1 mb-3">
        <BoolChip on={dev.mmio_bridge_configured || !!dev.execution_device} label="declared" />
        <BoolChip on={dev.bound} label="bound" />
        <BoolChip on={dev.bound ? executing : null} label="executing" />
      </div>
      <dl className="space-y-1.5 text-[12px] font-telemetry-mono">
        <Row k="execution device" v={val(dev.execution_device)} />
        <Row k="mmio bridge" v={dev.mmio_bridge_configured ? "configured" : "not configured"} />
        <Row k="reason" v={val(dev.reason)} warn />
        <Row
          k="backend"
          v={
            ops.execution.backend
              ? val(
                  (ops.execution.backend.backend ?? ops.execution.backend.route) as
                    | string
                    | null
                    | undefined
                )
              : NA
          }
        />
        <Row k="hashrate (measured)" v={fmtHs(hashing?.hashrate_hs)} />
        <Row k="hashes in span" v={val(hashing?.hashes_in_span)} />
        <Row k="stale candidates dropped" v={val(hashing?.stale_candidates_dropped)} />
        <Row k="hashes total" v={hashing?.hashes_total?.toLocaleString() ?? NA} />
        <Row k="executions" v={val(hashing?.executions_total)} />
        <Row k="window" v={val(hashing?.span_s, "s")} />
      </dl>
    </Card>
  );
};

/* ── Share pipeline card ───────────────────────────────────────────────── */

export const ShareCard: React.FC<{ ops: OpsTelemetry }> = ({ ops }) => {
  const c = ops.shares.counters ?? {};
  const o = ops.shares.outcomes ?? {};
  const sub = ops.shares.submission ?? {};
  const session = ops.shares.session;
  const log = [...(session.share_log ?? [])].reverse().slice(0, 8);
  const funnel: Array<{ label: string; n: number | null | undefined }> = [
    { label: "candidates verified", n: o.candidate_total ?? null },
    { label: "submitted", n: c.submitted ?? null },
    { label: "accepted", n: c.accepted ?? null },
    { label: "rejected", n: c.rejected ?? null },
    { label: "unknown", n: c.unknown ?? null },
    { label: "stale dropped", n: o.stale_dropped ?? null },
  ];
  return (
    <Card
      icon={<ArrowRight className="w-3.5 h-3.5" />}
      title="Share pipeline — candidate → pool verdict"
      status={
        <span className="text-[9px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93]">
          {val(sub.state)}
        </span>
      }
    >
      <dl className="space-y-1.5 text-[12px] font-telemetry-mono">
        {funnel.map((f) => (
          <Row key={f.label} k={f.label} v={val(f.n)} />
        ))}
        <Row k="last result" v={val(sub.last_result)} warn={sub.last_result === "REJECTED"} />
        <Row k="submit rtt last/mean" v={sub.rtt_ms ? `${val(sub.rtt_ms.last)} / ${val(sub.rtt_ms.mean)} ms` : NA} />
        <Row k="share log (persisted)" v={session.available ? val(session.share_count) : NA} />
      </dl>
      {log.length > 0 && (
        <div className="mt-3 max-h-32 overflow-y-auto space-y-1">
          {log.map((s: ShareLogEntry, i: number) => (
            <div key={i} className="text-[11px] font-telemetry-mono text-[#6b7c93]">
              <span className="text-[#8898aa]">{fmtTs(s.sent_at)}</span>{" "}
              <span>{truncate(s.job_id, 12)}</span>{" "}
              <span
                className={
                  s.state === "ACCEPTED"
                    ? "text-[#1a7f37]"
                    : s.state === "REJECTED"
                      ? "text-[#b42318]"
                      : "text-[#b45309]"
                }
              >
                {s.state ?? (s.outcome === true ? "ACCEPTED" : s.outcome === false ? "REJECTED" : "OUTCOME_UNKNOWN")}
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
};

/* ── Systems map card ──────────────────────────────────────────────────── */

export const SystemsCard: React.FC<{ ops: OpsTelemetry }> = ({ ops }) => {
  const workers = ops.system.workers ?? {};
  const healingWorkers = ops.healing.workers ?? {};
  const guardian = ops.security;
  const supervisor = ops.healing.autonomous_supervisor ?? {};
  const rows: Array<{ name: string; state: string; live: boolean | null; ready: boolean | null }> = [];
  for (const [name, w] of Object.entries(workers)) {
    rows.push({ name, state: w.state, live: w.liveness, ready: w.readiness });
  }
  for (const [name, w] of Object.entries(healingWorkers)) {
    if (!rows.some((r) => r.name === name)) {
      rows.push({ name, state: w.state, live: w.liveness, ready: w.readiness });
    }
  }
  return (
    <Card
      icon={<GitBranch className="w-3.5 h-3.5" />}
      title="System map — supervisors & gates"
    >
      <table className="w-full text-[11px] font-telemetry-mono">
        <thead>
          <tr className="text-left text-[#8898aa] uppercase text-[9px] tracking-wider">
            <th className="pr-2 py-1">component</th>
            <th className="pr-2 py-1">state</th>
            <th className="pr-2 py-1">live</th>
            <th className="py-1">ready</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.name} className="text-[#0a2540]">
              <td className="pr-2 py-0.5">{r.name}</td>
              <td className="pr-2 py-0.5">{r.state}</td>
              <td className="pr-2 py-0.5">{r.live === null ? NA : r.live ? "yes" : "no"}</td>
              <td className="py-0.5">{r.ready === null ? NA : r.ready ? "yes" : "no"}</td>
            </tr>
          ))}
          <tr className="text-[#0a2540]">
            <td className="pr-2 py-0.5">autonomous-supervisor</td>
            <td className="pr-2 py-0.5">{(supervisor.running as boolean) ? "running" : "stopped"}</td>
            <td className="pr-2 py-0.5">{supervisor.running === undefined ? NA : supervisor.running ? "yes" : "no"}</td>
            <td className="py-0.5">cycles {val(supervisor.cycle_count as number | undefined)}</td>
          </tr>
          <tr className="text-[#0a2540]">
            <td className="pr-2 py-0.5">al-haras guardian</td>
            <td className="pr-2 py-0.5">
              {guardian.available === false
                ? "unavailable"
                : guardian.allowed === false
                  ? `gate closed — ${String(guardian.reason ?? "denied").toLowerCase()}`
                  : guardian.allowed === true
                    ? "gate open"
                    : val((guardian.policy_version ?? guardian.status) as string)}
            </td>
            <td className="pr-2 py-0.5">{guardian.available === false ? "no" : "yes"}</td>
            <td className="py-0.5">{truncate(String(guardian.policy_version ?? guardian.reason ?? "—"), 24)}</td>
          </tr>
        </tbody>
      </table>
    </Card>
  );
};

/* ── Healing card ──────────────────────────────────────────────────────── */

export const HealingCard: React.FC<{ ops: OpsTelemetry }> = ({ ops }) => {
  const recovery = (ops.healing.recovery ?? {}) as Record<string, unknown>;
  const salamander = (ops.healing.salamander ?? null) as Record<string, unknown> | null;
  const salamanderState = (salamander?.state ?? null) as Record<string, unknown> | null;
  return (
    <Card
      icon={<HeartPulse className="w-3.5 h-3.5" />}
      title="Salamander — healing & recovery authority"
      status={
        <span className="text-[9px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93]">
          {val((recovery.mode ?? salamander?.mode) as string | undefined)}
        </span>
      }
    >
      <dl className="space-y-1.5 text-[12px] font-telemetry-mono">
        <Row k="authority mode" v={val(recovery.mode as string | undefined)} />
        <Row
          k="freezes speculation"
          v={recovery.freezes_speculation == null ? NA : recovery.freezes_speculation ? "true" : "false"}
          warn={recovery.freezes_speculation === true}
        />
        <Row k="faulted" v={recovery.faulted == null ? NA : recovery.faulted ? "true" : "false"} warn={recovery.faulted === true} />
        <Row k="active recovery" v={truncate(recovery.active_recovery_id as string | undefined, 24)} />
        <Row k="open recoveries" v={val((recovery.open as unknown[] | undefined)?.length)} />
        <Row k="salamander" v={salamander ? "reporting" : "Not running"} />
        {salamander && (
          <>
            <Row k="sal. mode/arm" v={salamander.mode != null || salamander.current_arm != null ? `${val(salamander.mode as string | undefined)} / arm ${val(salamander.current_arm as string | undefined)}` : NA} />
            <Row k="sal. faults" v={val(salamanderState?.faults as number | undefined)} warn={(salamanderState?.faults as number | undefined) != null && (salamanderState!.faults as number) > 0} />
            <Row k="sal. stratum drops" v={val(salamanderState?.stratum_drops as number | undefined)} warn={(salamanderState?.stratum_drops as number | undefined) != null && (salamanderState!.stratum_drops as number) > 0} />
            <Row k="sal. tests/hashes" v={salamanderState?.total_tests != null || salamanderState?.hashes_tested != null ? `${val(salamanderState?.total_tests as number | undefined)} / ${val(salamanderState?.hashes_tested as number | undefined)}` : NA} />
          </>
        )}
      </dl>
    </Card>
  );
};

/* ── Causal + history card ─────────────────────────────────────────────── */

export const EventCard: React.FC<{ ops: OpsTelemetry }> = ({ ops }) => {
  const [causal, setCausal] = useState<CausalTail | null>(null);
  useEffect(() => {
    let live = true;
    const load = async () => {
      try {
        const res = await apiFetch("/api/v1/telemetry/causal?n=24");
        if (res.ok && live) setCausal((await res.json()) as CausalTail);
      } catch {
        /* stale read is honest */
      }
    };
    void load();
    const timer = window.setInterval(load, 10_000);
    return () => {
      live = false;
      window.clearInterval(timer);
    };
  }, []);
  const events = [...ops.events.events].reverse().slice(0, 12);
  const causalRecords = [...(causal?.records ?? [])].reverse();
  const historyRecords = ops.history.telemetry_history.record_tail ?? [];

  return (
    <Card
      icon={<History className="w-3.5 h-3.5" />}
      title="Causal timeline & persisted history"
      status={
        <span className="text-[9px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93]">
          live {ops.events.available ? `seq ${ops.events.last_seq}` : "unavailable"}
        </span>
      }
    >
      <p className="text-[9px] font-telemetry-mono uppercase tracking-wider text-[#8898aa] mb-1">
        Stratum events (live)
      </p>
      <div className="max-h-36 overflow-y-auto space-y-1 mb-3">
        {events.length === 0 ? (
          <p className="text-[11px] font-telemetry-mono text-[#6b7c93]">
            {ops.events.reason ?? "Waiting for telemetry"}
          </p>
        ) : (
          events.map((e, i) => (
            <div key={i} className="text-[11px] font-telemetry-mono text-[#6b7c93]">
              <span className="text-[#8898aa]">#{e.seq}</span>{" "}
              <span className="text-[#8898aa]">{fmtTs(e.at)}</span>{" "}
              <span className="text-[#0a2540]">{e.kind}</span>
              {e.job_id ? <span> · {truncate(String(e.job_id), 14)}</span> : null}
              {e.detail ? (
                <span className="text-[#8898aa]"> · {truncate(JSON.stringify(e.detail), 60)}</span>
              ) : null}
            </div>
          ))
        )}
      </div>
      <p className="text-[9px] font-telemetry-mono uppercase tracking-wider text-[#8898aa] mb-1 flex items-center gap-1">
        <Database className="w-3 h-3" /> Causal ledger (persisted)
      </p>
      <div className="max-h-36 overflow-y-auto space-y-1 mb-3">
        {causalRecords.length === 0 ? (
          <p className="text-[11px] font-telemetry-mono text-[#6b7c93]">
            {causal?.reason ?? "No evidence"}
          </p>
        ) : (
          causalRecords.map((e, i) => (
            <div key={i} className="text-[11px] font-telemetry-mono text-[#6b7c93]">
              <span className="text-[#8898aa]">#{e.seq}</span>{" "}
              <span className="text-[#8898aa]">{fmtTs(e.at)}</span>{" "}
              <span className="text-[#0a2540]">{e.kind}</span>
              {e.detail && Object.keys(e.detail).length > 0 ? (
                <span className="text-[#8898aa]"> · {truncate(JSON.stringify(e.detail), 70)}</span>
              ) : null}
            </div>
          ))
        )}
      </div>
      <p className="text-[9px] font-telemetry-mono uppercase tracking-wider text-[#8898aa] mb-1">
        Telemetry history (persisted)
      </p>
      <dl className="space-y-1.5 text-[12px] font-telemetry-mono">
        <Row
          k="history store"
          v={ops.history.telemetry_history.exists ? `${ops.history.telemetry_history.path} · ${val(ops.history.telemetry_history.size_bytes)}B` : NA}
        />
        <Row
          k="history modified"
          v={val(ops.history.telemetry_history.modified_at)}
        />
        <Row
          k="causal ledger"
          v={ops.history.causal_ledger.exists ? `${ops.history.causal_ledger.path} · ${val(ops.history.causal_ledger.size_bytes)}B` : NA}
        />
        <Row
          k="session store"
          v={ops.history.mining_session.exists ? `${ops.history.mining_session.path} · ${val(ops.history.mining_session.share_count)} shares` : NA}
        />
      </dl>
      {historyRecords.length > 0 && (
        <div className="mt-2 max-h-28 overflow-y-auto space-y-1">
          {[...historyRecords].reverse().slice(0, 10).map((r, i) => (
            <div key={i} className="text-[11px] font-telemetry-mono text-[#6b7c93]">
              <span className="text-[#8898aa]">#{r.seq}</span>{" "}
              <span className="text-[#8898aa]">{fmtTs(r.at)}</span>{" "}
              <span className="text-[#0a2540]">{r.kind}</span>
              {r.kind === "hashrate" && r.data ? (
                <span> · {fmtHs(r.data.hashrate_hs as number)}</span>
              ) : null}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
};

/* ── The view ──────────────────────────────────────────────────────────── */

const TRANSPORT_LABEL: Record<string, string> = {
  sse: "live stream",
  poll: "poll",
  unreachable: "unreachable",
};

export const ObservabilityView: React.FC = () => {
  const { ops, transport, ageMs, stale } = useOpsTelemetry();

  return (
    <section className="console-surface mt-6">
      <header className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-[rgba(10,37,64,0.10)]">
        <h2 className="text-[11px] font-telemetry-mono uppercase tracking-[0.2em] text-[#42566f] flex items-center gap-2">
          <span className="text-[#635bff]">
            <Activity className="w-4 h-4" />
          </span>
          Operational observability — backend truth made visible
        </h2>
        <div className="flex items-center gap-2 text-[10px] font-telemetry-mono">
          <span className="text-[#6b7c93] flex items-center gap-1">
            <Radio className="w-3 h-3" />
            {TRANSPORT_LABEL[transport] ?? transport}
          </span>
          {ageMs !== null && (
            <span
              className={`px-1.5 py-0.5 rounded uppercase tracking-wider ${
                stale ? "bg-[#fef3c7] text-[#b45309]" : "bg-[#eceef1] text-[#6b7c93]"
              }`}
            >
              {stale ? `stale ${fmtAge(ageMs)}` : `${fmtAge(ageMs)} ago`}
            </span>
          )}
        </div>
      </header>

      {!ops ? (
        <p className="p-5 text-[12px] font-telemetry-mono text-[#6b7c93]">
          Waiting for telemetry — the control plane has not answered yet.
        </p>
      ) : (
        <div className="p-5 space-y-4">
          {stale && (
            <p className="text-[11px] font-telemetry-mono text-[#b45309] bg-[#fef3c7] rounded px-3 py-2 flex items-center gap-2">
              <AlertTriangle className="w-3.5 h-3.5" />
              Updates stopped {fmtAge(ageMs)} ago — values below are stale, not live.
            </p>
          )}
          <div className="grid gap-4 lg:grid-cols-2">
            <PoolCard ops={ops} />
            <JobCard ops={ops} />
            <ExecutionCard ops={ops} />
            <ShareCard ops={ops} />
            <SystemsCard ops={ops} />
            <HealingCard ops={ops} />
          </div>
          <EventCard ops={ops} />
          <p className="text-[10px] font-telemetry-mono text-[#8898aa]">
            schema {ops.schema} · generated {ops.generated_at}
          </p>
        </div>
      )}
    </section>
  );
};
