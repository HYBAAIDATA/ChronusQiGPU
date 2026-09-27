import React, { useCallback, useEffect, useRef, useState } from "react";
import { BrainCircuit, Layers3, Octagon, Play, ShieldCheck, Square } from "lucide-react";
import { apiFetch } from "../lib/api";
import type {
  AgenticStatus,
  CampaignPhaseRecord,
  CampaignStatus,
  FabricMap,
  SelftestStatus,
  VerificationStatus,
} from "../lib/status";

const inputCls =
  "w-full bg-[rgba(255,255,255,0.85)] border border-[rgba(10,37,64,0.18)] rounded-md px-3 py-1.5 text-[12px] font-telemetry-mono text-[#0a2540] placeholder:text-[#8898aa] focus:outline-none focus:border-[rgba(99,91,255,0.5)]";
const btnCls =
  "px-3 py-1.5 rounded-md border border-[rgba(99,91,255,0.35)] bg-[rgba(99,91,255,0.10)] text-[11px] font-telemetry-mono uppercase tracking-wider text-[#635bff] hover:bg-[rgba(99,91,255,0.18)] disabled:opacity-40 disabled:pointer-events-none transition-colors";
const btnDangerCls =
  "px-3 py-1.5 rounded-md border border-[rgba(223,27,65,0.35)] text-[11px] font-telemetry-mono uppercase tracking-wider text-[#df1b41] hover:bg-[rgba(223,27,65,0.10)] disabled:opacity-40 disabled:pointer-events-none transition-colors";

const WIRED_TONE: Record<string, string> = {
  production: "text-[#067647] border-[rgba(4,120,87,0.35)] bg-[rgba(4,120,87,0.08)]",
  fabric: "text-[#635bff] border-[rgba(99,91,255,0.35)] bg-[rgba(99,91,255,0.08)]",
  orchestrator: "text-[#2563eb] border-[rgba(37,99,235,0.35)] bg-[rgba(37,99,235,0.08)]",
  idle: "text-[#42566f] border-[rgba(107,124,147,0.35)] bg-[rgba(107,124,147,0.08)]",
  parked: "text-[#42566f] border-[rgba(107,124,147,0.35)] bg-[rgba(107,124,147,0.08)]",
  stub: "text-[#df1b41] border-[rgba(223,27,65,0.35)] bg-[rgba(223,27,65,0.08)]",
};

const RunnerCard: React.FC<{
  title: string;
  state?: string;
  meta?: string;
  running?: boolean;
  onStart?: () => void;
  onStop?: () => void;
  busy?: boolean;
  children?: React.ReactNode;
}> = ({ title, state, meta, running, onStart, onStop, busy, children }) => (
  <div className="console-surface-inset p-4 space-y-2">
    <div className="flex items-center justify-between gap-3">
      <p className="text-[10px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93]">
        {title}
      </p>
      <span
        className={`px-2 py-0.5 rounded-[2px] border text-[10px] font-telemetry-mono uppercase tracking-wider ${
          running
            ? "text-[#635bff] border-[rgba(99,91,255,0.4)]"
            : state === "error"
              ? "text-[#df1b41] border-[rgba(223,27,65,0.4)]"
              : "text-[#42566f] border-[rgba(10,37,64,0.25)]"
        }`}
      >
        {state ?? "offline"}
      </span>
    </div>
    {meta ? <p className="text-[11px] font-telemetry-mono text-[#42566f]">{meta}</p> : null}
    {children}
    <div className="flex items-center gap-2 pt-1">
      {onStart ? (
        <button className={btnCls} disabled={busy || running} onClick={onStart}>
          <Play className="w-3 h-3 inline mr-1" /> start
        </button>
      ) : null}
      {onStop ? (
        <button className={btnDangerCls} disabled={busy || !running} onClick={onStop}>
          <Square className="w-3 h-3 inline mr-1" /> stop
        </button>
      ) : null}
    </div>
  </div>
);

/** Forensic subsystem map + supervised intelligence runs (verify/selftest/agentic/campaign). */
export const SystemFabricPanel: React.FC = () => {
  const [map, setMap] = useState<FabricMap | null>(null);
  const [verify, setVerify] = useState<VerificationStatus | null>(null);
  const [selftest, setSelftest] = useState<SelftestStatus | null>(null);
  const [agentic, setAgentic] = useState<AgenticStatus | null>(null);
  const [campaign, setCampaign] = useState<CampaignStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    const endpoints: Array<[string, (v: unknown) => void]> = [
      ["/api/v1/system/map", (v) => setMap(v as FabricMap)],
      ["/api/v1/system/verify", (v) => setVerify(v as VerificationStatus)],
      ["/api/v1/intelligence/selftest", (v) => setSelftest(v as SelftestStatus)],
      ["/api/v1/agentic/status", (v) => setAgentic(v as AgenticStatus)],
      ["/api/v1/campaign/status", (v) => setCampaign(v as CampaignStatus)],
    ];
    for (const [path, setter] of endpoints) {
      try {
        const res = await apiFetch(path);
        if (res.ok) setter(await res.json());
      } catch {
        /* control plane offline — keep last snapshot */
      }
    }
  }, []);

  useEffect(() => {
    refresh();
    timer.current = window.setInterval(refresh, 4000);
    return () => {
      if (timer.current !== null) window.clearInterval(timer.current);
    };
  }, [refresh]);

  const post = useCallback(
    async (path: string, body?: Record<string, unknown>) => {
      setBusy(true);
      setError(null);
      try {
        const res = await apiFetch(path, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body ?? {}),
        });
        const payload = await res.json().catch(() => ({}));
        if (!res.ok) setError(payload?.error ?? `${path} rejected (${res.status})`);
        else if (payload?.ok === false)
          setError(payload?.reason ?? payload?.error ?? `${path} declined`);
        refresh();
      } catch (e) {
        setError(e instanceof Error ? e.message : `${path} failed`);
      } finally {
        setBusy(false);
      }
    },
    [refresh]
  );

  const subsystems = map?.subsystems ?? [];
  const running =
    verify?.state === "running" ||
    selftest?.state === "running" ||
    agentic?.state === "running" ||
    campaign?.state === "running";
  const verifyStages = verify?.stages ? Object.entries(verify.stages) : [];
  const campaignPhases =
    (campaign?.result as { phases?: CampaignPhaseRecord[] } | undefined)?.phases ?? [];
  const agenticPhase = (agentic?.progress?.current_phase as string | undefined) ?? null;
  const selfSummary = selftest?.summary;

  return (
    <section className="console-surface">
      <header className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-[rgba(10,37,64,0.10)]">
        <h2 className="text-[11px] font-telemetry-mono uppercase tracking-[0.2em] text-[#42566f] flex items-center gap-2">
          <span className="text-[#635bff]">
            <Octagon className="w-4 h-4" />
          </span>
          System fabric — one brain, every subsystem mapped
        </h2>
        <span className="text-[10px] font-telemetry-mono text-[#6b7c93]">
          {running ? "supervisor active" : "idle"} · polled every 4s
        </span>
      </header>
      <div className="p-5 space-y-5">
        {/* Runner supervisors */}
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <RunnerCard
            title="Chain verification"
            state={verify?.state}
            running={verify?.state === "running"}
            busy={busy}
            onStart={() => post("/api/v1/system/verify")}
            meta={
              verify?.ready === true
                ? `ready — ${verify.overlay?.faces_total ?? 32}-face overlay`
                : verify?.ready === false
                  ? "not ready"
                  : `${verifyStages.length} stages ${verify?.state === "done" ? "checked" : "idle"}`
            }
          >
            {verifyStages.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {verifyStages.map(([name, s]) => (
                  <span
                    key={name}
                    title={s?.detail ?? name}
                    className={`px-1.5 py-0.5 rounded-[2px] border text-[9px] font-telemetry-mono ${
                      s?.ok
                        ? "text-[#067647] border-[rgba(4,120,87,0.3)]"
                        : "text-[#df1b41] border-[rgba(223,27,65,0.3)]"
                    }`}
                  >
                    {name}
                  </span>
                ))}
              </div>
            )}
          </RunnerCard>

          <RunnerCard
            title="Intelligence self-test"
            state={selftest?.state}
            running={selftest?.state === "running"}
            busy={busy}
            onStart={() => post("/api/v1/intelligence/selftest")}
            meta={
              selfSummary?.passed === true
                ? `passed ${selfSummary.checks?.passed}/${selfSummary.checks?.total} checks`
                : selfSummary?.passed === false
                  ? `failed — ${selfSummary.failures?.join(", ") ?? "see report"}`
                  : "45-module registry smoke test"
            }
          />

          <RunnerCard
            title="Agentic workflow"
            state={agentic?.state}
            running={agentic?.state === "running"}
            busy={busy}
            onStart={() => post("/api/v1/agentic/start", { count: 128, cycles: 3 })}
            onStop={() => post("/api/v1/agentic/stop")}
            meta={
              agenticPhase
                ? `phase: ${agenticPhase}`
                : "cold start → precompute → submit → steady → cool down"
            }
          />

          <RunnerCard
            title="Pool campaign"
            state={campaign?.state}
            running={campaign?.state === "running"}
            busy={busy}
            onStart={() => post("/api/v1/campaign/start")}
            onStop={() => post("/api/v1/campaign/stop")}
            meta={
              campaignPhases.length > 0
                ? `${campaignPhases.length} phase(s) executed`
                : "runs config.campaign.phases — per-phase pool + rate bound"
            }
          >
            {campaignPhases.length > 0 && (
              <div className="space-y-1">
                {campaignPhases.map((p) => (
                  <p key={p.index} className="text-[10px] font-telemetry-mono text-[#42566f]">
                    p{p.index} {p.worker ?? p.pool} @ {p.endpoint ?? ""} ·{" "}
                    {p.measured_hs_avg != null
                      ? `${(p.measured_hs_avg / 1e18).toFixed(3)} EH/s avg`
                      : "not measured"}{" "}
                    · shares {p.shares_accepted ?? 0}
                  </p>
                ))}
              </div>
            )}
          </RunnerCard>
        </div>

        {/* Subsystem map */}
        <div className="console-surface-inset p-4">
          <p className="text-[10px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93] flex items-center gap-2">
            <Layers3 className="w-3.5 h-3.5 text-[#635bff]" /> Forensic subsystem map
          </p>
          {subsystems.length === 0 ? (
            <p className="mt-2 text-[12px] font-telemetry-mono text-[#6b7c93]">
              map not reported — control plane offline or endpoint missing
            </p>
          ) : (
            <>
              <div className="mt-2 flex flex-wrap gap-2 text-[10px] font-telemetry-mono">
                {(["production", "fabric", "orchestrator", "idle", "parked", "stub"] as const).map((k) =>
                  map?.summary?.[k] ? (
                    <span key={k} className={`px-2 py-0.5 rounded-[2px] border ${WIRED_TONE[k]}`}>
                      {k} {map.summary[k]}
                    </span>
                  ) : null
                )}
              </div>
              <div className="mt-3 grid gap-1.5 md:grid-cols-2 xl:grid-cols-3">
                {subsystems.map((s) => (
                  <div
                    key={s.key}
                    title={`${s.module} — ${s.detail ?? ""}`}
                    className="flex items-center justify-between gap-2 rounded-[3px] border border-[rgba(10,37,64,0.10)] px-2.5 py-1.5"
                  >
                    <span className="min-w-0 truncate text-[11px] font-telemetry-mono text-[#0a2540]">
                      {s.name}
                    </span>
                    <span className="flex items-center gap-1.5 shrink-0">
                      {s.gate_state === "closed" && (
                        <span className="text-[9px] font-telemetry-mono uppercase text-[#b45309]">
                          gated:{s.gate}
                        </span>
                      )}
                      <span
                        className={`px-1.5 py-0.5 rounded-[2px] border text-[9px] font-telemetry-mono uppercase ${WIRED_TONE[s.wired] ?? WIRED_TONE.idle}`}
                      >
                        {s.wired}
                      </span>
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Mining verbs — config-bounded */}
        <div className="console-surface-inset p-4">
          <p className="text-[10px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93] flex items-center gap-2">
            <BrainCircuit className="w-3.5 h-3.5 text-[#635bff]" /> Mining verbs
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button className={btnCls} disabled={busy} onClick={() => post("/api/v1/mining/start")}>
              start
            </button>
            <button
              className={btnDangerCls}
              disabled={busy}
              onClick={() => post("/api/v1/mining/stop")}
            >
              stop
            </button>
            <PoolSwitch onPick={(v) => post("/api/v1/mining/switch", { pool: v })} busy={busy} />
            <VerbField
              label="elevate"
              placeholder="target H/s"
              busy={busy}
              onGo={(v) => post("/api/v1/mining/elevate", { target_hs: Number(v) })}
            />
            <VerbField
              label="escalate"
              placeholder="arms 1–600"
              busy={busy}
              onGo={(v) => post("/api/v1/mining/escalate", { arms: Number(v) })}
            />
          </div>
          <p className="mt-2 text-[11px] font-telemetry-mono text-[#42566f]">
            start/stop spawn and retire the supervised arms · switch selects the configured pool ·
            elevate/escalate write through the config bounds
          </p>
        </div>
      </div>
      {error && (
        <p className="px-5 pb-4 text-[11px] font-telemetry-mono text-[#df1b41]">{error}</p>
      )}
      <p className="px-5 pb-4 text-[11px] font-telemetry-mono text-[#6b7c93] flex items-center gap-2">
        <ShieldCheck className="w-3.5 h-3.5 text-[#635bff]" />
        every runner reports measured state only — sha256d remains the sole accept authority
      </p>
    </section>
  );
};

const PoolSwitch: React.FC<{ onPick: (v: string) => void; busy: boolean }> = ({
  onPick,
  busy,
}) => {
  const [pools, setPools] = useState<Array<{ endpoint: string; worker: string }>>([]);
  useEffect(() => {
    apiFetch("/api/v1/config")
      .then((r) => (r.ok ? r.json() : null))
      .then((cfg) => setPools(cfg?.pools ?? []))
      .catch(() => setPools([]));
  }, []);
  if (pools.length === 0) return null;
  return (
    <select
      className={inputCls + " w-auto"}
      disabled={busy}
      defaultValue=""
      onChange={(e) => e.target.value && onPick(e.target.value)}
    >
      <option value="" disabled>
        switch pool…
      </option>
      {pools.map((p) => (
        <option key={`${p.endpoint}|${p.worker}`} value={p.worker}>
          {p.worker} @ {p.endpoint}
        </option>
      ))}
    </select>
  );
};

const VerbField: React.FC<{
  label: string;
  placeholder: string;
  busy: boolean;
  onGo: (v: string) => void;
}> = ({ label, placeholder, busy, onGo }) => {
  const [v, setV] = useState("");
  return (
    <span className="flex items-center gap-1.5">
      <input
        className={inputCls + " w-32"}
        placeholder={placeholder}
        value={v}
        onChange={(e) => setV(e.target.value)}
      />
      <button
        className={btnCls}
        disabled={busy || !v.trim()}
        onClick={() => {
          onGo(v);
          setV("");
        }}
      >
        {label}
      </button>
    </span>
  );
};
