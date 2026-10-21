import React, { useEffect, useState } from "react";
import { Header } from "./components/Header";
import { Mla1517MiningPanel } from "./components/Mla1517MiningPanel";
import { MiningEvidencePanel } from "./components/MiningEvidencePanel";
import { ControlSession } from "./components/ControlSession";
import { BackendLens } from "./components/BackendLens";
import { Alert, Source } from "./components/ConsolePrimitives";
import { useConsole } from "./lib/useConsole";
const VIEWS = ["operations", "observability", "algebra", "intelligence", "manifold", "audit"] as const;
type ViewKey = typeof VIEWS[number];
const viewFromHash = (): ViewKey => VIEWS.find(v => v === window.location.hash.replace(/^#\/?/, "").toLowerCase()) ?? "operations";
export default function App() {
  const { access, status, evidence, evidenceError, offline, loading, refresh } = useConsole();
  const [view, setView] = useState<ViewKey>(viewFromHash);
  useEffect(() => { const onHash = () => setView(viewFromHash()); window.addEventListener("hashchange", onHash); return () => window.removeEventListener("hashchange", onHash); }, []);
  // Hide old payloads synchronously with the entitlement verdict.
  const visible = access.allowed && !offline ? status : null;
  return <div className="min-h-screen flex flex-col font-sans text-[#0a2540] bg-[#f5f7fa]">
    <a className="console-skip" href="#console-main">Skip to content</a>
    <Header status={visible} ready={visible?.ready_to_mine ?? null} offline={offline} miningAuthorized={access.allowed} />
    <nav aria-label="Console views" className="console-nav"><div>{VIEWS.map(v => <a key={v} href={`#/${v}`} aria-current={view === v ? "page" : undefined}>{v}</a>)}</div></nav>
    <main id="console-main" tabIndex={-1} className="flex-1 w-full max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-10">
      <ControlSession onChanged={refresh} />
      {!access.allowed ? <section className="console-surface mt-6 p-6"><h1 className="text-xl font-semibold">Mining dashboard unavailable</h1><p className="mt-3">A server-confirmed CEO session is required for this mining console. Other roles receive no mining telemetry.</p><p className="console-source">access: {access.reason}</p>{access.role && <p className="console-source">server role: {access.role} · non-mining workspace: unavailable in this console</p>}</section> : <>
        <Source endpoint="/api/v1/mla1517/status" timestamp={visible?.generated_at} />
        {loading && <div className="console-skeleton" role="status" aria-busy="true">Loading backend evidence…</div>}
        {offline && <Alert>Control API offline — current status and receipts cleared. No stale verdict is displayed.</Alert>}
        {view === "operations" ? <><h1 className="mt-6 text-2xl font-semibold">Operations</h1><Mla1517MiningPanel status={visible} ready={visible?.ready_to_mine ?? null} offline={offline} onConfigChanged={refresh} /><MiningEvidencePanel evidence={access.allowed && !offline ? evidence : null} offline={offline} error={evidenceError} /></> : <BackendLens view={view} status={visible} offline={offline} />}
      </>}
    </main><footer className="console-footer">HYBA · Python control plane · schema {visible?.schema_version ?? "not reported"} · publication HOLD</footer>
  </div>;
}
