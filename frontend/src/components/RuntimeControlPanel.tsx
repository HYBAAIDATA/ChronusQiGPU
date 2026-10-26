import React, { useCallback, useEffect, useState } from "react";
import { Plus, Power, Sliders, Trash2, Waypoints } from "lucide-react";
import { apiFetch } from "../lib/api";
import type { RuntimeConfig, RuntimePool } from "../lib/status";

const inputCls =
  "w-full bg-[rgba(255,255,255,0.85)] border border-[rgba(10,37,64,0.18)] rounded-md px-3 py-1.5 text-[12px] font-telemetry-mono text-[#0a2540] placeholder:text-[#8898aa] focus:outline-none focus:border-[rgba(99,91,255,0.5)]";
const btnCls =
  "px-3 py-1.5 rounded-md border border-[rgba(99,91,255,0.35)] bg-[rgba(99,91,255,0.10)] text-[11px] font-telemetry-mono uppercase tracking-wider text-[#635bff] hover:bg-[rgba(99,91,255,0.18)] disabled:opacity-40 disabled:pointer-events-none transition-colors";
const btnDangerCls =
  "px-2 py-1 rounded-md border border-[rgba(223,27,65,0.35)] text-[10px] font-telemetry-mono uppercase tracking-wider text-[#df1b41] hover:bg-[rgba(223,27,65,0.10)] transition-colors";

const formatHs = (v: number): string => {
  if (!v) return "physical max";
  if (v >= 1e18) return `${(v / 1e18).toFixed(2)} EH/s`;
  if (v >= 1e15) return `${(v / 1e15).toFixed(2)} PH/s`;
  if (v >= 1e12) return `${(v / 1e12).toFixed(2)} TH/s`;
  if (v >= 1e9) return `${(v / 1e9).toFixed(2)} GH/s`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(2)} MH/s`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(2)} kH/s`;
  return `${v} H/s`;
};

/** Config-bounded operator controls: pools, solver arms, hashrate pacing, live submit. */
export const RuntimeControlPanel: React.FC<{ config: RuntimeConfig | null; offline: boolean; onChanged?: () => void }> = ({ config, offline, onChanged }) => {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [endpoint, setEndpoint] = useState("");
  const [worker, setWorker] = useState("");
  const [password, setPassword] = useState("");
  const [hashrateInput, setHashrateInput] = useState("");
  const [armsInput, setArmsInput] = useState("");

  const put = useCallback(
    async (body: Record<string, unknown>) => {
      setBusy(true);
      setError(null);
      setNote(null);
      try {
        const res = await apiFetch("/api/v1/config", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        const payload = await res.json();
        if (!res.ok) {
          setError(payload?.error ?? `config rejected (${res.status})`);
          return;
        }
        // Only the next canonical status snapshot updates the read view.
        const applied = payload.applied ?? {};
        const bits = [
          applied.spawned?.length ? `+${applied.spawned.length} arm(s)` : null,
          applied.retired?.length ? `-${applied.retired.length} arm(s)` : null,
          applied.restarted?.length ? `${applied.restarted.length} restarted` : null,
          applied.note ?? null,
        ].filter(Boolean);
        setNote(bits.length ? bits.join(" · ") : "applied");
        onChanged?.();
      } catch (e) {
        setError(e instanceof Error ? e.message : "config write failed");
      } finally {
        setBusy(false);
      }
    },
    [onChanged]
  );

  const pools = config?.pools ?? [];
  const bounds = config?.bounds ?? {};
  const armRange = bounds.arms;
  const ceiling = bounds.hashrate_ceiling_hs;
  const live = config?.live_submit;

  const writePools = (next: RuntimePool[]) => put({ pools: next });

  const addPool = () => {
    if (!endpoint.trim() || !worker.trim() || !password) return;
    writePools([
      ...pools.map((p) => ({ ...p, enabled: false })),
      { endpoint: endpoint.trim(), worker: worker.trim(), password, enabled: true },
    ]);
    setEndpoint("");
    setWorker("");
    setPassword("");
  };

  const enablePool = (i: number) =>
    writePools(pools.map((p, j) => ({ ...p, password: "", enabled: j === i })));

  const removePool = (i: number) => writePools(pools.filter((_, j) => j !== i));

  const setTarget = () => {
    const v = Number(hashrateInput);
    if (!Number.isFinite(v) || v < 0) {
      setError("hashrate must be a non-negative number (H/s)");
      return;
    }
    if (ceiling == null) {
      setError("hashrate ceiling unavailable — refresh runtime configuration");
      return;
    }
    if (v > ceiling) {
      setError(`hashrate target must not exceed ${formatHs(ceiling)}`);
      return;
    }
    put({ hashrate: { target_hs: v, ceiling_hs: ceiling } });
    setHashrateInput("");
  };

  const setArms = () => {
    const v = Number(armsInput);
    if (!armRange || config?.solvers?.workers == null || !Number.isInteger(v) || v < armRange[0] || v > armRange[1]) {
      setError(`arms must be an integer in [${armRange?.[0]}, ${armRange?.[1]}]`);
      return;
    }
    put({ solvers: { arms: v, workers: config!.solvers!.workers } });
    setArmsInput("");
  };

  const toggleLive = () =>
    put({ live_submit: { enabled: !(live?.enabled ?? false) } });

  return (
    <fieldset disabled={offline || !config} className="min-w-0 border-0 p-0">
    <section className="console-surface">
      <header className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-[rgba(10,37,64,0.10)]">
        <h2 className="text-[11px] font-telemetry-mono uppercase tracking-[0.2em] text-[#42566f] flex items-center gap-2">
          <span className="text-[#635bff]">
            <Sliders className="w-4 h-4" />
          </span>
          Runtime control — configuration-bounded
        </h2>
      </header>
      <div className="p-5 grid gap-5 lg:grid-cols-2">
        {/* Pools */}
        <div className="console-surface-inset p-4 space-y-3">
          <p className="text-[10px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93] flex items-center gap-2">
            <Waypoints className="w-3.5 h-3.5 text-[#635bff]" /> Pools
          </p>
          {pools.length === 0 ? (
            <p className="text-[12px] font-telemetry-mono text-[#6b7c93]">
              runtime pools not reported; no pool identity is inferred
            </p>
          ) : (
            pools.map((p, i) => (
              <div
                key={`${p.endpoint}|${p.worker}`}
                className="flex items-center justify-between gap-3 text-[12px] font-telemetry-mono"
              >
                <span className="min-w-0 truncate text-[#0a2540]">
                  {p.worker} <span className="text-[#6b7c93]">@ {p.endpoint}</span>
                </span>
                <span className="flex items-center gap-2 shrink-0">
                  {p.enabled ? (
                    <span className="px-2 py-0.5 rounded-[2px] border border-[rgba(4,120,87,0.35)] text-[10px] uppercase text-[#067647]">
                      active
                    </span>
                  ) : (
                    <button className={btnCls} disabled={busy} onClick={() => enablePool(i)}>
                      use
                    </button>
                  )}
                  <button className={btnDangerCls} disabled={busy} onClick={() => removePool(i)}>
                    <Trash2 className="w-3 h-3" />
                  </button>
                </span>
              </div>
            ))
          )}
          <div className="grid gap-2 pt-1">
            <input
              className={inputCls}
              placeholder="endpoint host:port"
              value={endpoint}
              onChange={(e) => setEndpoint(e.target.value)}
            />
            <input
              className={inputCls}
              placeholder="worker account.worker"
              value={worker}
              onChange={(e) => setWorker(e.target.value)}
            />
            <input
              className={inputCls}
              type="password"
              placeholder="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <button className={btnCls} disabled={busy} onClick={addPool}>
              <Plus className="w-3 h-3 inline mr-1" /> add pool (enabled)
            </button>
          </div>
        </div>

        {/* Hashrate + solvers + live */}
        <div className="console-surface-inset p-4 space-y-4">
          <div>
            <p className="text-[10px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93]">
              Deterministic hashrate target
            </p>
            <div className="mt-2 flex items-center gap-2">
              <input
                className={inputCls}
                placeholder="H/s (0 = physical max)"
                value={hashrateInput}
                onChange={(e) => setHashrateInput(e.target.value)}
              />
              <button className={btnCls} disabled={busy || ceiling == null} onClick={setTarget}>
                set
              </button>
            </div>
            <p className="mt-1 text-[11px] font-telemetry-mono text-[#42566f]">
              current {config?.hashrate?.target_hs == null ? "not reported" : formatHs(config.hashrate.target_hs)} · ceiling{" "}
              {ceiling == null ? "Unavailable" : formatHs(ceiling)} · measured rate is reported separately
            </p>
          </div>

          <div>
            <p className="text-[10px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93]">
              Physical execution arms
            </p>
            <div className="mt-2 flex items-center gap-2">
              <input
                className={inputCls}
                placeholder={armRange ? `arms ${armRange[0]}–${armRange[1]}` : "arm bounds not reported"}
                value={armsInput}
                onChange={(e) => setArmsInput(e.target.value)}
              />
              <button className={btnCls} disabled={busy || !armRange || config?.solvers?.workers == null} onClick={setArms}>
                apply
              </button>
            </div>
            <p className="mt-1 text-[11px] font-telemetry-mono text-[#42566f]">
              configured {config?.solvers?.arms ?? "not reported"} · live{" "}
              {config?.live_arms?.length ?? "not reported"} · workers per arm {config?.solvers?.workers ?? "not reported"}
            </p>
          </div>

          <div className="flex items-center justify-between gap-3 border-t border-[rgba(10,37,64,0.07)] pt-3">
            <div>
              <p className="text-[10px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93] flex items-center gap-2">
                <Power className="w-3.5 h-3.5 text-[#b45309]" /> Live share submission
              </p>
              <p className="mt-1 text-[11px] font-telemetry-mono text-[#42566f]">
                {live?.enabled == null ? "not reported" : live.enabled
                  ? `armed — bound to ${pools.find((p) => p.enabled)?.endpoint ?? "enabled pool"}`
                  : "off — arms observe and grind, submit gate stays closed"}
              </p>
            </div>
            <button
              className={live?.enabled ? btnDangerCls : btnCls}
              disabled={busy || live?.enabled == null}
              onClick={toggleLive}
            >
              {live?.enabled ? "disarm" : "arm live"}
            </button>
          </div>
        </div>
      </div>
      {(error || note) && (
        <p
          className={`px-5 pb-4 text-[11px] font-telemetry-mono ${
            error ? "text-[#df1b41]" : "text-[#067647]"
          }`}
        >
          {error ?? note}
        </p>
      )}
    </section>
    </fieldset>
  );
};
