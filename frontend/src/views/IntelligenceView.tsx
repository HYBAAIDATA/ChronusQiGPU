import React, { useCallback, useEffect, useState } from "react";
import { BrainCircuit, FlaskConical, RefreshCw } from "lucide-react";
import { apiFetch } from "../lib/api";
import { TruthChip } from "../components/TruthChip";
import type { AgenticStatus, RunnerStatus, SelftestStatus } from "../lib/status";

type SelftestReport = Record<string, { passed?: boolean } & Record<string, unknown>>;

/** Intelligence substrate — self-test detail, agentic run, orchestrator state. */
export const IntelligenceView: React.FC = () => {
  const [selftest, setSelftest] = useState<SelftestStatus | null>(null);
  const [agentic, setAgentic] = useState<AgenticStatus | null>(null);
  const [intel, setIntel] = useState<RunnerStatus | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    const pulls: Array<[string, (v: unknown) => void]> = [
      ["/api/v1/intelligence/selftest", (v) => setSelftest(v as SelftestStatus)],
      ["/api/v1/agentic/status", (v) => setAgentic(v as AgenticStatus)],
      ["/api/v1/intelligence/status", (v) => setIntel(v as RunnerStatus)],
    ];
    for (const [path, setter] of pulls) {
      try {
        const res = await apiFetch(path);
        if (res.ok) setter(await res.json());
      } catch {
        /* keep last snapshot */
      }
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = window.setInterval(refresh, 4000);
    return () => window.clearInterval(t);
  }, [refresh]);

  const startSelftest = async () => {
    setBusy(true);
    try {
      await apiFetch("/api/v1/intelligence/selftest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
    } finally {
      setBusy(false);
      refresh();
    }
  };

  const summary = selftest?.summary;
  const report = (selftest?.result as { report?: SelftestReport } | undefined)?.report;
  const reportEntries = report ? Object.entries(report) : [];
  const agenticResult = agentic?.result as Record<string, unknown> | undefined;
  const phases = (agenticResult?.phases ?? {}) as Record<string, unknown>;

  return (
    <div className="space-y-6 pt-8">
      <div>
        <p className="text-[11px] font-telemetry-mono uppercase tracking-[0.28em] text-[#635bff]">
          Intelligence substrate
        </p>
        <h1 className="font-serif-display mt-3 text-4xl sm:text-5xl font-semibold tracking-tight text-[#0a2540]">
          Self-test, agentic runs, orchestrator — measured or unavailable.
        </h1>
        <p className="mt-4 max-w-2xl text-sm leading-relaxed text-[#42566f]">
          The 45-module registry self-test and the agentic mining workflow run
          on the Python control plane. Results below are the supervisor's own
          record — nothing is inferred in the browser.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Self-test */}
        <section className="console-surface lg:col-span-2">
          <header className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-[rgba(10,37,64,0.10)]">
            <h2 className="text-[11px] font-telemetry-mono uppercase tracking-[0.2em] text-[#42566f] flex items-center gap-2">
              <FlaskConical className="w-4 h-4 text-[#635bff]" />
              Intelligence self-test
            </h2>
            <div className="flex items-center gap-2">
              <TruthChip value={summary?.passed === true ? "measured" : "unavailable"} />
              <button
                className="px-3 py-1 rounded-md border border-[rgba(99,91,255,0.35)] bg-[rgba(99,91,255,0.10)] text-[11px] font-telemetry-mono uppercase tracking-wider text-[#635bff] hover:bg-[rgba(99,91,255,0.18)] disabled:opacity-40 transition-colors"
                disabled={busy || selftest?.state === "running"}
                onClick={startSelftest}
              >
                <RefreshCw className="w-3 h-3 inline mr-1" />
                {selftest?.state === "running" ? "running" : "run"}
              </button>
            </div>
          </header>
          <div className="p-5">
            {summary ? (
              <p className="text-sm font-telemetry-mono text-[#0a2540]">
                {summary.passed === true ? "passed" : "failed"} —{" "}
                {summary.checks?.passed ?? "?"}/{summary.checks?.total ?? "?"} checks
                {selftest?.state === "running" ? " · running" : ""}
              </p>
            ) : (
              <p className="text-sm font-telemetry-mono text-[#6b7c93]">
                self-test not run — press run to execute the registry check on the backend
              </p>
            )}
            {reportEntries.length > 0 && (
              <div className="mt-4 grid gap-1.5 sm:grid-cols-2 xl:grid-cols-3">
                {reportEntries.map(([name, r]) => (
                  <div
                    key={name}
                    className="flex items-center justify-between gap-2 rounded-[3px] border border-[rgba(10,37,64,0.10)] px-2.5 py-1.5"
                  >
                    <span className="min-w-0 truncate text-[11px] font-telemetry-mono text-[#0a2540]">
                      {name}
                    </span>
                    <span
                      className={`px-1.5 py-0.5 rounded-[2px] border text-[9px] font-telemetry-mono uppercase shrink-0 ${
                        r?.passed
                          ? "text-[#067647] border-[rgba(4,120,87,0.3)]"
                          : "text-[#df1b41] border-[rgba(223,27,65,0.3)]"
                      }`}
                    >
                      {r?.passed ? "pass" : "fail"}
                    </span>
                  </div>
                ))}
              </div>
            )}
            {summary?.failures && summary.failures.length > 0 && (
              <p className="mt-3 text-[11px] font-telemetry-mono text-[#df1b41]">
                failures: {summary.failures.join(", ")}
              </p>
            )}
          </div>
        </section>

        {/* Orchestrator */}
        <section className="console-surface">
          <header className="px-5 pt-4 pb-3 border-b border-[rgba(10,37,64,0.10)]">
            <h2 className="text-[11px] font-telemetry-mono uppercase tracking-[0.2em] text-[#42566f]">
              Orchestrator
            </h2>
          </header>
          <div className="p-5 space-y-2 font-telemetry-mono text-[12px]">
            <p className="flex justify-between">
              <span className="text-[#6b7c93]">state</span>
              <span className="text-[#0a2540]">{intel?.state ?? "unavailable"}</span>
            </p>
            <p className="flex justify-between">
              <span className="text-[#6b7c93]">error</span>
              <span className="text-[#df1b41]">{intel?.error ?? "none"}</span>
            </p>
            <p className="mt-3 text-[11px] leading-5 text-[#6b7c93]">
              The intelligence orchestrator loads lazily on the control plane;
              substrate availability is reported, never assumed.
            </p>
          </div>
        </section>
      </div>

      {/* Agentic detail */}
      <section className="console-surface">
        <header className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-[rgba(10,37,64,0.10)]">
          <h2 className="text-[11px] font-telemetry-mono uppercase tracking-[0.2em] text-[#42566f] flex items-center gap-2">
            <BrainCircuit className="w-4 h-4 text-[#635bff]" />
            Last agentic run
          </h2>
          <span className="text-[10px] font-telemetry-mono text-[#6b7c93]">
            {agentic?.state ?? "idle"}
          </span>
        </header>
        <div className="p-5">
          {Object.keys(phases).length === 0 ? (
            <p className="text-sm font-telemetry-mono text-[#6b7c93]">
              no agentic run recorded — start one from Operations → system fabric
            </p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {Object.keys(phases).map((p) => (
                <span
                  key={p}
                  className="px-2 py-1 rounded-[2px] border border-[rgba(99,91,255,0.25)] bg-[rgba(99,91,255,0.08)] text-[10px] font-telemetry-mono uppercase tracking-wider text-[#635bff]"
                >
                  {p}
                </span>
              ))}
            </div>
          )}
          {agentic?.error && (
            <p className="mt-3 text-[11px] font-telemetry-mono text-[#df1b41]">{agentic.error}</p>
          )}
        </div>
      </section>
    </div>
  );
};
