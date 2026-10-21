import React from "react";
import type { ConsoleStatus } from "../lib/console";
import { Alert, Empty, Source, Field } from "./ConsolePrimitives";
const LENSES = {
  observability: { title: "What is the runtime reporting?", keys: ["telemetry", "fabric"] },
  algebra: { title: "What has the backend verified?", keys: ["verification", "selftest"] },
  intelligence: { title: "What is intelligence reporting?", keys: ["intelligence", "cognition"] },
  manifold: { title: "What is the system topology?", keys: ["fabric", "agentic"] },
  audit: { title: "What evidence is available?", keys: ["audit"] },
} as const;
export function BackendLens({ view, status, offline }: { view: keyof typeof LENSES; status: ConsoleStatus | null; offline: boolean }) {
  const lens = LENSES[view];
  return <div className="space-y-6 pt-8"><h1 className="text-2xl font-semibold">{lens.title}</h1>
    <Source endpoint="/api/v1/mla1517/status" timestamp={status?.generated_at} />
    {offline && <Alert>Control API offline — current evidence unavailable.</Alert>}
    {view === "audit" && <Alert>Tenant-scoped export is unavailable until the backend supplies an authorized tenant-scoped audit contract. Local calculations are not runtime receipts.</Alert>}
    {lens.keys.map(key => <section className="console-surface p-5" key={key}><h2 className="console-label">{key}</h2>
      {status?.console?.[key] ? <dl className="mt-4">{Object.entries(status.console[key]!).map(([name, value]) => <Field label={name.replaceAll("_", " ")} key={name}>{value == null ? <Empty /> : typeof value === "object" ? <details><summary>Inspect backend document</summary><pre className="console-json">{JSON.stringify(value, null, 2)}</pre></details> : String(value)}</Field>)}</dl> : <p className="mt-4"><Empty /></p>}
      {status?.console?.unavailable?.[key] && <p className="console-source">{status.console.unavailable[key]}</p>}
    </section>)}
  </div>;
}
