import React from "react";
import {
  Activity,
  CheckCircle2,
  CircuitBoard,
  Circle,
  Cpu,
  Fingerprint,
  Gauge,
  Layers,
  LoaderCircle,
  Network,
  ShieldAlert,
  Waypoints,
  XCircle,
} from "lucide-react";
import type { MlaStatus, ReadyToMine, WorkerPublic } from "../lib/status";
import { stratumAlert, stratumStages } from "../lib/stratum";
import { RuntimeControlPanel } from "./RuntimeControlPanel";
import { SystemFabricPanel } from "./SystemFabricPanel";
import { TelemetryPanel } from "./TelemetryPanel";

const NOT_REPORTED = "not reported";

const Card: React.FC<{
  title: string;
  icon: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}> = ({ title, icon, children, className = "" }) => (
  <section className={`console-surface ${className}`}>
    <header className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-[rgba(10,37,64,0.10)]">
      <h2 className="text-[11px] font-telemetry-mono uppercase tracking-[0.2em] text-[#42566f] flex items-center gap-2">
        <span className="text-[#635bff]">{icon}</span>
        {title}
      </h2>
    </header>
    <div className="p-5">{children}</div>
  </section>
);

const Field: React.FC<{ label: string; children: React.ReactNode }> = ({ label, children }) => (
  <div className="flex items-start justify-between gap-4 py-2 border-b border-[rgba(10,37,64,0.07)] last:border-0">
    <span className="text-[11px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93] pt-0.5">
      {label}
    </span>
    <span className="text-right text-[13px] font-telemetry-mono text-[#0a2540] break-all">
      {children}
    </span>
  </div>
);

const Empty = () => <span className="text-[#6b7c93] lowercase">{NOT_REPORTED}</span>;

const StratumOperationalPanel: React.FC<{ status: MlaStatus["stratum"] }> = ({ status }) => {
  const primary = status?.primary;
  const job = status?.job;
  const submission = status?.submission;
  const alert = stratumAlert(status);
  const stages = stratumStages(status);
  const target = job?.share_target;
  const age = job?.age_ms;

  return (
    <Card title="Stratum operations" icon={<Network className="w-4 h-4" />}>
      {alert ? (
        <div className="mb-4 flex items-center gap-2 border-l-2 border-[#df1b41] bg-[rgba(223,27,65,0.06)] px-3 py-2 text-[11px] font-telemetry-mono text-[#b4233c]">
          <ShieldAlert className="h-4 w-4 shrink-0" />
          {alert}
        </div>
      ) : null}

      <div className="grid grid-cols-2 gap-x-5 lg:grid-cols-4">
        <Field label="State">{status?.state ?? <Empty />}</Field>
        <Field label="Transport">{primary?.transport ?? <Empty />}</Field>
        <Field label="Subscription">{primary?.subscribed === true ? "confirmed" : <Empty />}</Field>
        <Field label="Authorization">
          {primary?.authorized === true ? "confirmed" : <Empty />}
        </Field>
        <Field label="Generation">
          {job?.generation != null ? `#${job.generation}` : <Empty />}
        </Field>
        <Field label="Job age">
          {typeof age === "number" ? `${(age / 1000).toFixed(1)}s` : <Empty />}
        </Field>
        <Field label="Difficulty">
          {job?.difficulty != null ? String(job.difficulty) : <Empty />}
        </Field>
        <Field label="Submission">{submission?.state ?? <Empty />}</Field>
        <Field label="Job ID">{job?.job_id ?? <Empty />}</Field>
        <Field label="Fingerprint">
          {job?.fingerprint ? job.fingerprint.slice(0, 16) : <Empty />}
        </Field>
        <Field label="Target generation">
          {job?.target_generation != null ? `#${job.target_generation}` : <Empty />}
        </Field>
        <Field label="Share target">
          {target ? (
            <span title={target}>{`${target.slice(0, 12)}...${target.slice(-8)}`}</span>
          ) : (
            <Empty />
          )}
        </Field>
      </div>

      <div className="mt-5 grid grid-cols-4 gap-px border border-[rgba(10,37,64,0.10)] bg-[rgba(10,37,64,0.08)] sm:grid-cols-8">
        {stages.map((stage) => {
          const Icon =
            stage.state === "complete"
              ? CheckCircle2
              : stage.state === "active"
                ? LoaderCircle
                : stage.state === "blocked"
                  ? XCircle
                  : Circle;
          const tone =
            stage.state === "complete"
              ? "text-[#067647]"
              : stage.state === "active"
                ? "text-[#b45309]"
                : stage.state === "blocked"
                  ? "text-[#df1b41]"
                  : "text-[#9aa8b8]";
          return (
            <div
              key={stage.key}
              className="flex min-h-16 flex-col items-center justify-center gap-1 bg-white px-1.5 py-2 text-center"
            >
              <Icon className={`h-4 w-4 ${tone}`} />
              <span className="text-[9px] font-telemetry-mono uppercase text-[#42566f] sm:text-[10px]">
                {stage.label}
              </span>
            </div>
          );
        })}
      </div>

      <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1 text-[11px] font-telemetry-mono text-[#6b7c93]">
        <span>submitted {status?.counters?.submitted ?? 0}</span>
        <span className="text-[#067647]">accepted {status?.counters?.accepted ?? 0}</span>
        <span className="text-[#df1b41]">rejected {status?.counters?.rejected ?? 0}</span>
        <span className="text-[#b45309]">unknown {status?.counters?.unknown ?? 0}</span>
        <span>disconnects {status?.counters?.disconnects ?? 0}</span>
      </div>
    </Card>
  );
};

const WorkerRow: React.FC<{ name: string; worker: WorkerPublic }> = ({ name, worker }) => {
  const stateTone =
    worker.state === "running"
      ? "text-[#067647] border-[rgba(4,120,87,0.35)] bg-[rgba(4,120,87,0.08)]"
      : worker.state === "failed" || worker.state === "stopped"
        ? "text-[#df1b41] border-[rgba(223,27,65,0.35)] bg-[rgba(223,27,65,0.08)]"
        : "text-[#b45309] border-[rgba(180,83,9,0.35)] bg-[rgba(180,83,9,0.08)]";
  const hashrate = worker.effectiveness?.hashrate ?? null;
  const shares = worker.effectiveness?.shares_accepted ?? 0;
  return (
    <div className="console-surface-inset px-4 py-3">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3 min-w-0">
          <span className={`beacon ${worker.liveness ? "beacon-green" : "beacon-dim"}`} />
          <span className="font-telemetry-mono text-sm text-[#0a2540] truncate">{name}</span>
          <span
            className={`px-2 py-0.5 rounded-[2px] border text-[10px] font-telemetry-mono uppercase tracking-wider ${stateTone}`}
          >
            {worker.state}
          </span>
        </div>
        <div className="flex items-center gap-4 text-[11px] font-telemetry-mono text-[#42566f]">
          <span title="liveness">
            live {worker.liveness ? <span className="text-[#067647]">·</span> : "—"}
          </span>
          <span title="readiness">
            rdy {worker.readiness ? <span className="text-[#067647]">·</span> : "—"}
          </span>
          <span title="attempts">attempts {worker.attempts_total}</span>
        </div>
      </div>
      <div className="mt-2 flex items-center gap-4 text-[12px] font-telemetry-mono">
        <span className="text-[#6b7c93]">
          hashrate{" "}
          {hashrate != null ? (
            <span className="text-[#0a2540]">{hashrate.toLocaleString()} H/s</span>
          ) : (
            <Empty />
          )}
        </span>
        <span className="text-[#6b7c93]">
          shares {shares > 0 ? <span className="text-[#0a2540]">{shares}</span> : <Empty />}
        </span>
      </div>
      {worker.last_error ? (
        <p className="mt-2 text-[11px] font-telemetry-mono text-[#df1b41]">
          {worker.last_error.kind}: {worker.last_error.message}
        </p>
      ) : null}
    </div>
  );
};

interface PanelProps {
  status: MlaStatus | null;
  ready: ReadyToMine | null;
  offline: boolean;
  onConfigChanged?: () => void;
}

/** Observability console for the canonical Python/C/OpenCL miner. */
export const Mla1517MiningPanel: React.FC<PanelProps> = ({
  status,
  ready,
  offline,
  onConfigChanged,
}) => {
  const engine = status?.canonicalEngine;
  const identity = status?.host?.stratum ?? null;
  const workers = status?.workers ?? {};
  const workerNames = Object.keys(workers);
  const devices = status?.device?.devices ?? [];
  const readyToMine = ready?.ready === true;
  const readyReason = ready?.reason ?? (ready === null ? "not reported" : "unknown");

  return (
    <div className="space-y-6">
      {/* Hero readiness band */}
      <section className="relative overflow-hidden border-b border-[rgba(10,37,64,0.13)] -mx-4 sm:-mx-6 lg:-mx-8 px-4 sm:px-6 lg:px-8 pt-12 pb-10">
        <div className="hero-grid absolute inset-0 pointer-events-none" />
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              "radial-gradient(ellipse 60% 80% at 12% 0%, rgba(99,91,255,0.10), transparent 65%), radial-gradient(ellipse 45% 70% at 85% 20%, rgba(37,99,235,0.07), transparent 70%)",
          }}
        />
        <div className="relative">
          <p className="text-[11px] font-telemetry-mono uppercase tracking-[0.28em] text-[#635bff]">
            Operational mining console
          </p>
          <h1 className="font-serif-display mt-3 text-4xl sm:text-5xl font-semibold tracking-tight text-[#0a2540]">
            {offline
              ? "Control plane unreachable."
              : readyToMine
                ? "Ready to mine."
                : "Standing by."}
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-relaxed text-[#42566f]">
            {offline
              ? "The Python control API is not answering. Mining state cannot be read — nothing below is live."
              : readyToMine
                ? "Every supervised worker is alive, heartbeat-ready, and producing measured work against the resolved pool."
                : `Readiness gate reports ${readyReason}. The console shows measured state only — no synthetic or projected figures.`}
          </p>
          <div className="mt-6 flex flex-wrap items-center gap-x-6 gap-y-2 text-[11px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93]">
            <span className="flex items-center gap-2">
              <Fingerprint className="w-3.5 h-3.5 text-[#635bff]" />
              identity {identity?.identity_commit ? identity.identity_commit.slice(0, 12) : "—"}
            </span>
            <span className="flex items-center gap-2">
              <Waypoints className="w-3.5 h-3.5 text-[#635bff]" />
              pool {identity ? `${identity.host}:${identity.port}` : "—"}
            </span>
            <span className="flex items-center gap-2">
              <Activity className="w-3.5 h-3.5 text-[#635bff]" />
              polled {status?.generated_at ?? "—"}
            </span>
          </div>
        </div>
      </section>

      <StratumOperationalPanel status={status?.stratum} />

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Stratum identity */}
        <Card title="Stratum identity" icon={<Fingerprint className="w-4 h-4" />}>
          {identity ? (
            <div>
              <Field label="Profile">{identity.profile}</Field>
              <Field label="Endpoint">
                {identity.host}:{identity.port}
              </Field>
              <Field label="Worker">{identity.user_redacted}</Field>
              <Field label="Password">
                {identity.password_committed ? "committed (HMAC)" : <Empty />}
              </Field>
              <Field label="Pool link">
                {status?.stratum?.primary?.transport === "CONNECTED" ? (
                  <span className="text-[#067647]">connected</span>
                ) : (
                  <span className="text-[#b45309]">
                    {status?.stratum?.state ?? "not connected"}
                  </span>
                )}
              </Field>
            </div>
          ) : (
            <p className="text-sm text-[#6b7c93]">
              Identity {NOT_REPORTED} — the control API resolves it at boot.
            </p>
          )}
        </Card>

        {/* Canonical engine */}
        <Card title="Canonical MLA1517 engine" icon={<Layers className="w-4 h-4" />}>
          <div>
            <Field label="Product">{engine?.product ?? <Empty />}</Field>
            <Field label="Path">{engine?.path ?? <Empty />}</Field>
            <Field label="Backend">{engine?.backend ?? <Empty />}</Field>
            <Field label="Execution">
              <span className="text-[#b45309]">{engine?.execution ?? <Empty />}</span>
            </Field>
            <Field label="Hashrate basis">
              <span className="text-[#42566f]">{engine?.hashrate ?? <Empty />}</span>
            </Field>
          </div>
          <div className="mt-4">
            <p className="text-[10px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93]">
              Exact ladder
            </p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {(engine?.ladder ?? []).length > 0 ? (
                engine?.ladder?.map((rung) => (
                  <span
                    key={rung}
                    className="px-2 py-1 rounded-[2px] bg-[rgba(99,91,255,0.10)] border border-[rgba(99,91,255,0.25)] text-[11px] font-telemetry-mono text-[#635bff]"
                  >
                    L{rung}
                  </span>
                ))
              ) : (
                <Empty />
              )}
            </div>
          </div>
        </Card>
      </div>

      {/* Solver manifold — one brain, N independent arms */}
      {status?.solvers ? (
        <Card title="Solver manifold" icon={<Waypoints className="w-4 h-4" />}>
          <div>
            <Field label="Arms">
              {status.solvers.arms} independent solver{status.solvers.arms === 1 ? "" : "s"}
            </Field>
            <Field label="Lanes per arm">{status.solvers.lanes_per_arm}</Field>
            <Field label="Total solvers">
              {status.solvers.arms * status.solvers.lanes_per_arm}
            </Field>
            <Field label="Nonce partition">
              <span className="text-[#42566f]">{status.solvers.nonce_partition}</span>
            </Field>
            <Field label="Hashrate basis">
              <span className="text-[#42566f]">{status.solvers.hashrate}</span>
            </Field>
          </div>
        </Card>
      ) : null}

      {/* System fabric — forensic subsystem map + supervised runners */}
      <SystemFabricPanel />

      {/* Operator runtime control — pools, arms, hashrate, live submit */}
      <RuntimeControlPanel onChanged={onConfigChanged} />

      {/* Telemetry — live aggregates, session counters, audit history */}
      <TelemetryPanel />

      {/* Workers */}
      <Card title="Supervised workers" icon={<Gauge className="w-4 h-4" />}>
        {workerNames.length === 0 ? (
          <p className="text-sm text-[#6b7c93]">No workers supervised — {NOT_REPORTED}.</p>
        ) : (
          <div className="grid gap-3">
            {workerNames.map((name) => (
              <WorkerRow key={name} name={name} worker={workers[name]} />
            ))}
          </div>
        )}
      </Card>

      {/* Devices */}
      <Card title="OpenCL device surface" icon={<Cpu className="w-4 h-4" />}>
        {status?.device?.available && devices.length > 0 ? (
          <div className="grid gap-2 sm:grid-cols-2">
            {devices.map((d, i) => (
              <div key={i} className="console-surface-inset px-4 py-3 flex items-center gap-3">
                <CircuitBoard className="w-4 h-4 text-[#635bff] shrink-0" />
                <div className="min-w-0">
                  <p className="text-[13px] font-telemetry-mono text-[#0a2540] truncate">
                    {d.device}
                  </p>
                  <p className="text-[11px] font-telemetry-mono text-[#6b7c93] truncate">
                    {d.vendor} · {d.platform}
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-[#6b7c93]">
            {status === null
              ? `Device surface ${NOT_REPORTED} — waiting on control plane.`
              : "No OpenCL device discovered. The canonical engine fails closed on hardware absence by design."}
          </p>
        )}
      </Card>

      {/* Measurement honesty line */}
      <p className="text-[11px] font-telemetry-mono text-[#6b7c93] flex items-center gap-2">
        <ShieldAlert className="w-3.5 h-3.5 text-[#b45309]" />
        {status?.measurement ?? "no synthetic result; no measurement until a real run"}
      </p>
    </div>
  );
};
