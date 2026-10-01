import React, { useEffect, useState } from "react";
import { Header } from "./components/Header";
import { Mla1517MiningPanel } from "./components/Mla1517MiningPanel";
import { MiningEvidencePanel } from "./components/MiningEvidencePanel";
import { apiFetch } from "./lib/api";
import type { MlaStatus, ReadyToMine } from "./lib/status";
import { AlgebraView } from "./views/AlgebraView";
import { AuditView } from "./views/AuditView";
import { IntelligenceView } from "./views/IntelligenceView";
import { ManifoldView } from "./views/ManifoldView";

type ViewKey = "operations" | "algebra" | "intelligence" | "manifold" | "audit";

const VIEWS: Array<{ key: ViewKey; label: string }> = [
  { key: "operations", label: "Operations" },
  { key: "algebra", label: "Algebra" },
  { key: "intelligence", label: "Intelligence" },
  { key: "manifold", label: "Manifold" },
  { key: "audit", label: "Audit" },
];

function viewFromHash(): ViewKey {
  const key = window.location.hash.replace(/^#\/?/, "").toLowerCase();
  return (VIEWS.find((v) => v.key === key)?.key ?? "operations") as ViewKey;
}

export default function App() {
  const [status, setStatus] = useState<MlaStatus | null>(null);
  const [ready, setReady] = useState<ReadyToMine | null>(null);
  const [offline, setOffline] = useState(false);
  const [view, setView] = useState<ViewKey>(viewFromHash);

  useEffect(() => {
    const onHash = () => setView(viewFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const poll = React.useCallback(async () => {
    try {
      // The status payload carries ready_to_mine. /ready-to-mine stays a
      // readiness probe that answers 503 until mining is ready, so the
      // dashboard reads the same verdict here instead of polling the probe.
      const statusResponse = await apiFetch("/api/v1/mla1517/status");
      if (statusResponse.ok) {
        const body = (await statusResponse.json()) as MlaStatus & {
          ready_to_mine?: ReadyToMine;
        };
        setStatus(body);
        setReady(body.ready_to_mine ?? null);
      }
      setOffline(false);
    } catch {
      setOffline(true);
    }
  }, []);

  useEffect(() => {
    void poll();
    const timer = window.setInterval(poll, 5000);
    return () => window.clearInterval(timer);
  }, [poll]);

  return (
    <div className="min-h-screen flex flex-col font-sans text-[#0a2540] bg-[#f5f7fa]">
      <Header status={status} ready={ready} offline={offline} />
      <nav className="border-b border-[rgba(10,37,64,0.10)] bg-[rgba(255,255,255,0.6)]">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex items-center gap-1 overflow-x-auto">
          {VIEWS.map((v) => (
            <a
              key={v.key}
              href={`#/${v.key}`}
              className={`px-3 py-2.5 text-[11px] font-telemetry-mono uppercase tracking-[0.18em] border-b-2 transition-colors whitespace-nowrap ${
                view === v.key
                  ? "border-[#635bff] text-[#635bff]"
                  : "border-transparent text-[#6b7c93] hover:text-[#42566f]"
              }`}
            >
              {v.label}
            </a>
          ))}
        </div>
      </nav>
      <main className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-10">
        {view === "operations" && (
          <>
            <Mla1517MiningPanel
              status={status}
              ready={ready}
              offline={offline}
              onConfigChanged={poll}
            />
            <MiningEvidencePanel />
          </>
        )}
        {view === "algebra" && <AlgebraView />}
        {view === "intelligence" && <IntelligenceView />}
        {view === "manifold" && <ManifoldView status={status} offline={offline} />}
        {view === "audit" && <AuditView status={status} />}
      </main>
      <footer className="border-t border-[rgba(10,37,64,0.13)] py-4">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-wrap items-center justify-between gap-3 text-[11px] font-telemetry-mono text-[#6b7c93]">
          <span className="uppercase tracking-widest text-[#42566f]">
            HYBA PYTHIA · Operational mining
          </span>
          <span>
            Python control plane · {status?.backend ?? "Python/C/OpenCL"} ·{" "}
            {status?.schema_version ?? "chronus.mla1517.status/1"}
          </span>
        </div>
      </footer>
    </div>
  );
}
