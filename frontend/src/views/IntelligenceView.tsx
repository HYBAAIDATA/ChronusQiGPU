import React, { useCallback, useEffect, useState } from "react";
import { ArrowUpRight, BrainCircuit, FlaskConical, Play, RefreshCw, Square, Wrench } from "lucide-react";
import { apiFetch } from "../lib/api";
import { TruthChip } from "../components/TruthChip";
import type {
  AgenticStatus,
  IntelligenceStatus,
  MaintenanceStatus,
  RepoEngineerStatus,
  SelftestStatus,
} from "../lib/status";

type SelftestReport = Record<string, { passed?: boolean } & Record<string, unknown>>;

/** Intelligence substrate — self-test detail, agentic run, orchestrator state. */
export const IntelligenceView: React.FC = () => {
  const [selftest, setSelftest] = useState<SelftestStatus | null>(null);
  const [agentic, setAgentic] = useState<AgenticStatus | null>(null);
  const [intel, setIntel] = useState<IntelligenceStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [maintenance, setMaintenance] = useState<MaintenanceStatus | null>(null);
  const [maintenanceBusy, setMaintenanceBusy] = useState(false);
  const [maintenanceError, setMaintenanceError] = useState<string | null>(null);
  const [engineer, setEngineer] = useState<RepoEngineerStatus | null>(null);
  const [engineerPrompt, setEngineerPrompt] = useState("");
  const [engineerBusy, setEngineerBusy] = useState(false);
  const [engineerError, setEngineerError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const pulls: Array<[string, (v: unknown) => void]> = [
      ["/api/v1/intelligence/selftest", (v) => setSelftest(v as SelftestStatus)],
      ["/api/v1/agentic/status", (v) => setAgentic(v as AgenticStatus)],
      ["/api/v1/intelligence/status", (v) => setIntel(v as IntelligenceStatus)],
      ["/api/v1/intelligence/maintenance", (v) => setMaintenance(v as MaintenanceStatus)],
      ["/api/v1/intelligence/engineer/status", (v) => setEngineer(v as RepoEngineerStatus)],
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

  const controlMaintenance = async (action: "run" | "start" | "stop") => {
    setMaintenanceBusy(true);
    setMaintenanceError(null);
    try {
      const response = await apiFetch(`/api/v1/intelligence/maintenance/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { error?: string };
        setMaintenanceError(payload.error ?? `request failed (${response.status})`);
      }
    } catch (error) {
      setMaintenanceError(error instanceof Error ? error.message : String(error));
    } finally {
      setMaintenanceBusy(false);
      refresh();
    }
  };

  const askEngineer = async () => {
    const prompt = engineerPrompt.trim();
    if (!prompt || prompt.length > 2_000) return;
    setEngineerBusy(true);
    setEngineerError(null);
    try {
      const response = await apiFetch("/api/v1/intelligence/engineer/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as {
          error?: string;
          readiness?: RepoEngineerStatus;
        };
        if (payload.readiness) setEngineer(payload.readiness);
        setEngineerError(payload.error ?? `request failed (${response.status})`);
      } else {
        setEngineerPrompt("");
      }
    } catch (error) {
      setEngineerError(error instanceof Error ? error.message : String(error));
    } finally {
      setEngineerBusy(false);
      refresh();
    }
  };

  const summary = selftest?.summary;
  const report = (selftest?.result as { report?: SelftestReport } | undefined)?.report;
  const reportEntries = report ? Object.entries(report) : [];
  const agenticResult = agentic?.result as Record<string, unknown> | undefined;
  const phases = (agenticResult?.phases ?? {}) as Record<string, unknown>;
  const cognition = intel?.euclid_cognition;
  const cognitionCapabilities = cognition?.capabilities ?? {};
  const cognitionOpenGates = cognition?.open_gates ?? [];
  const maintenancePhase =
    typeof maintenance?.progress?.phase === "string"
      ? maintenance.progress.phase
      : maintenance?.state ?? "loading";
  const maintenanceTruth =
    maintenance?.state === "running"
      ? "live"
      : maintenance?.state === "done"
        ? "measured"
        : "unavailable";
  const engineerResult = engineer?.runner?.result as
    | { text?: string; tool_calls?: Array<{ tool: string; ok: boolean }> }
    | undefined;

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

      <section className="console-surface">
        <header className="flex flex-wrap items-center justify-between gap-3 px-5 pt-4 pb-3 border-b border-[rgba(10,37,64,0.10)]">
          <h2 className="text-[11px] font-telemetry-mono uppercase tracking-[0.2em] text-[#42566f] flex items-center gap-2">
            <BrainCircuit className="w-4 h-4 text-[#067647]" />
            Repository engineer
          </h2>
          <div className="flex items-center gap-2 text-[10px] font-telemetry-mono text-[#6b7c93]">
            <TruthChip value={engineer?.ready ? "live" : "unavailable"} />
            <span>{engineer?.provider ?? "agent"} · {engineer?.model ?? "not configured"}</span>
          </div>
        </header>
        <div className="grid gap-5 p-5 lg:grid-cols-[minmax(0,1fr)_220px]">
          <div className="min-w-0">
            <form
              onSubmit={(event) => {
                event.preventDefault();
                askEngineer();
              }}
              className="space-y-2"
            >
              <textarea
                value={engineerPrompt}
                onChange={(event) => setEngineerPrompt(event.target.value.slice(0, 2_000))}
                rows={3}
                maxLength={2_000}
                placeholder="Ask for a grounded repo improvement or investigation"
                aria-label="Repository engineering task"
                className="w-full resize-y rounded-[3px] border border-[rgba(10,37,64,0.16)] bg-white/70 px-3 py-2 text-sm text-[#0a2540] placeholder:text-[#8898aa] focus:outline-none focus:border-[rgba(4,120,87,0.55)]"
              />
              <div className="flex items-center justify-between gap-3">
                <p className="text-[10px] font-telemetry-mono text-[#6b7c93]">
                  {engineer?.runner?.state ?? "idle"} · read-only tools · no changes applied
                </p>
                <button
                  type="submit"
                  disabled={!engineer?.ready || engineerBusy || engineer?.runner?.state === "running" || !engineerPrompt.trim()}
                  title="Ask the repo-aware engineering agent"
                  className="inline-flex items-center gap-2 rounded-[3px] border border-[rgba(4,120,87,0.35)] bg-[rgba(4,120,87,0.08)] px-3 py-1.5 text-[11px] font-telemetry-mono uppercase tracking-wider text-[#067647] hover:bg-[rgba(4,120,87,0.15)] disabled:opacity-40"
                >
                  <ArrowUpRight className="h-3.5 w-3.5" />
                  {engineer?.runner?.state === "running" ? "working" : "ask"}
                </button>
              </div>
            </form>
            {!engineer?.ready && (
              <p className="mt-3 text-[11px] leading-5 font-telemetry-mono text-[#6b7c93]">
                The in-repo engineer has not reported ready; check the control API log. Asking it needs EUCLID_ADMIN_API_KEY.
              </p>
            )}
            {(engineerError || engineer?.runner?.error) && (
              <p className="mt-3 text-[11px] font-telemetry-mono text-[#df1b41]">
                {engineerError ?? engineer?.runner?.error}
              </p>
            )}
            {engineerResult?.text && (
              <pre className="mt-4 max-h-[30rem] overflow-auto whitespace-pre-wrap rounded-[3px] border border-[rgba(10,37,64,0.10)] bg-white/60 p-4 text-[12px] leading-5 text-[#0a2540]">
                {engineerResult.text}
              </pre>
            )}
          </div>
          <aside className="border-t border-[rgba(10,37,64,0.10)] pt-4 text-[10px] font-telemetry-mono lg:border-t-0 lg:border-l lg:pt-0 lg:pl-5">
            <p className="uppercase tracking-wider text-[#42566f]">Repository grounding</p>
            <p className="mt-3 text-[#6b7c93]">
              {engineer?.context_files?.length ?? 0} architecture and engineering documents loaded at startup.
            </p>
            <ul className="mt-3 space-y-1 text-[#0a2540]">
              {(engineer?.tools ?? []).map((tool) => <li key={tool}>{tool}</li>)}
            </ul>
            {engineerResult?.tool_calls && engineerResult.tool_calls.length > 0 && (
              <p className="mt-4 text-[#067647]">
                inspected with {engineerResult.tool_calls.map((call) => call.tool).join(", ")}
              </p>
            )}
          </aside>
        </div>
      </section>

      <section className="console-surface">
        <header className="flex flex-wrap items-center justify-between gap-3 px-5 pt-4 pb-3 border-b border-[rgba(10,37,64,0.10)]">
          <h2 className="text-[11px] font-telemetry-mono uppercase tracking-[0.2em] text-[#42566f] flex items-center gap-2">
            <Wrench className="w-4 h-4 text-[#067647]" />
            Codebase maintenance
          </h2>
          <div className="flex items-center gap-2">
            <TruthChip value={maintenanceTruth} />
            <button
              className="px-3 py-1 rounded-md border border-[rgba(4,120,87,0.35)] bg-[rgba(4,120,87,0.08)] text-[11px] font-telemetry-mono uppercase tracking-wider text-[#067647] hover:bg-[rgba(4,120,87,0.15)] disabled:opacity-40 transition-colors"
              disabled={maintenanceBusy}
              onClick={() => controlMaintenance("run")}
              title="Run a diagnosis now or queue one after the active cycle"
            >
              <Play className="w-3 h-3 inline mr-1" />
              run now
            </button>
            {maintenance?.state === "running" ? (
              <button
                className="px-3 py-1 rounded-md border border-[rgba(223,27,65,0.3)] text-[11px] font-telemetry-mono uppercase tracking-wider text-[#df1b41] hover:bg-[rgba(223,27,65,0.06)] disabled:opacity-40 transition-colors"
                disabled={maintenanceBusy || maintenance.progress?.stop_requested === true}
                onClick={() => controlMaintenance("stop")}
                title="Stop after the current full diagnosis cycle"
              >
                <Square className="w-3 h-3 inline mr-1" />
                {maintenance.progress?.stop_requested === true ? "pausing" : "pause loop"}
              </button>
            ) : (
              <button
                className="px-3 py-1 rounded-md border border-[rgba(10,37,64,0.18)] text-[11px] font-telemetry-mono uppercase tracking-wider text-[#42566f] hover:bg-[rgba(10,37,64,0.04)] disabled:opacity-40 transition-colors"
                disabled={maintenanceBusy}
                onClick={() => controlMaintenance("start")}
                title="Start the supervised maintenance loop"
              >
                <Play className="w-3 h-3 inline mr-1" />
                start loop
              </button>
            )}
          </div>
        </header>
        <div className="grid gap-4 p-5 md:grid-cols-[minmax(0,1fr)_auto]">
          <div className="min-w-0">
            <p className="text-sm font-telemetry-mono text-[#0a2540]">
              {maintenancePhase}
              {maintenance?.interval_s
                ? ` · next cycle every ${Math.round(maintenance.interval_s / 3600)}h`
                : " · one-shot"}
            </p>
            {maintenance?.result?.summary ? (
              <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap rounded-[3px] border border-[rgba(10,37,64,0.10)] bg-white/60 p-3 text-[11px] leading-5 font-telemetry-mono text-[#42566f]">
                {maintenance.result.summary}
              </pre>
            ) : (
              <p className="mt-2 text-[11px] font-telemetry-mono text-[#6b7c93]">
                No completed diagnosis recorded yet.
              </p>
            )}
            {(maintenance?.error || maintenanceError) && (
              <p className="mt-2 text-[11px] font-telemetry-mono text-[#df1b41]">
                {maintenanceError ?? maintenance?.error}
              </p>
            )}
          </div>
          <dl className="grid grid-cols-2 gap-x-5 gap-y-2 self-start text-[10px] font-telemetry-mono md:min-w-48">
            <dt className="text-[#6b7c93]">failures</dt>
            <dd className="text-right text-[#0a2540]">{maintenance?.result?.failure_count ?? "—"}</dd>
            <dt className="text-[#6b7c93]">proposals</dt>
            <dd className="text-right text-[#0a2540]">{maintenance?.result?.proposal_count ?? "—"}</dd>
            <dt className="text-[#6b7c93]">LLM gate</dt>
            <dd className="text-right text-[#0a2540]">{maintenance?.llm_enabled ? "on" : "off"}</dd>
            <dt className="text-[#6b7c93]">apply gate</dt>
            <dd className="text-right text-[#0a2540]">
              {maintenance?.auto_apply_enabled ? "verified" : "review only"}
            </dd>
          </dl>
        </div>
      </section>

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
            <div className="mt-3 flex items-center justify-between gap-2">
              <span className="text-[#6b7c93]">EUCLID cognition</span>
              <TruthChip value={cognition?.available ? "live" : "unavailable"} />
            </div>
            <p className="mt-2 text-[11px] leading-5 text-[#6b7c93]">
              {cognition?.available
                ? `${Object.values(cognitionCapabilities).filter(Boolean).length}/${Object.keys(cognitionCapabilities).length} declared cognition capabilities active · ${cognitionOpenGates.length} open evidence gates`
                : "canonical cognition runtime unavailable"}
            </p>
            {cognition?.authority_boundary && (
              <p className="mt-2 text-[10px] leading-4 text-[#6b7c93]">
                EUCLID: {cognition.authority_boundary.EUCLID ?? "cognition"} · PYTHIA: {cognition.authority_boundary.PYTHIA ?? "mining authority"}
              </p>
            )}
            <p className="mt-3 text-[11px] leading-5 text-[#6b7c93]">
              Runtime intelligence is reported from the canonical EUCLID composition root;
              unavailable evidence remains unavailable.
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
