import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { Shell } from "@/components/shell";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardKicker, CardTitle } from "@/components/ui/card";
import { IMPLEMENTED, runAudit, type CheckResult } from "@/lib/pythia/audit";
import { useBackend } from "@/lib/pythia/backend-store";

export const Route = createFileRoute("/audit")({ component: AuditPage });

function AuditPage() {
  const [results, setResults] = useState<CheckResult[] | null>(null);
  const b = useBackend();

  useEffect(() => {
    b.startPolling();
    return () => b.stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const passed = results?.filter((r) => r.passed).length ?? 0;

  const pack = useMemo(() => {
    const workers = b.status?.workers ?? {};
    const anyRunning = Object.values(workers).some(
      (w) => w.state === "running" || w.liveness,
    );
    return {
      product: "PYTHIA",
      generatedAt: new Date().toISOString(),
      posture: b.health.ok
        ? "live backend connected — evidence from control_api / telemetry"
        : "backend offline — algebra checks only",
      session: {
        backendOnline: b.health.ok,
        stratumConnected: b.status?.stratum?.connected ?? false,
        stratumStatus: b.status?.stratum?.status ?? null,
        engineBackend: b.status?.canonicalEngine?.backend ?? null,
        engineExecution: b.status?.canonicalEngine?.execution ?? null,
        hashrateMeasured: b.telemetry?.hashrate ?? null,
        sharesAccepted: b.telemetry?.shares_accepted ?? null,
        sharesRejected: b.telemetry?.shares_rejected ?? null,
        workersRunning: anyRunning,
        recoveryState: b.recovery.state,
        recoveryFault: b.recovery.lastFault,
        salamanderNotified: b.recovery.salamanderNotified,
      },
      checks: results,
      implemented: IMPLEMENTED.map((i) => i.id),
    };
  }, [results, b]);

  function download() {
    const blob = new Blob(
      [JSON.stringify(pack, (_, v) => (typeof v === "bigint" ? v.toString() : v), 2)],
      { type: "application/json" },
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `pythia-evidence-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <Shell>
      <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-muted-foreground">
        Evidence pack
      </p>
      <h1 className="mt-3 max-w-3xl font-display text-4xl font-medium tracking-tight">
        Suggestions, implemented. Claims, bounded.
      </h1>
      <p className="mt-4 max-w-2xl text-sm leading-6 text-muted-foreground">
        Algebra checks run locally with BigInt. Session evidence is taken from the live
        Python control API and measured telemetry — not from any browser mining simulator.
      </p>
      <div className="mt-8 flex flex-wrap gap-3">
        <Button onClick={() => setResults(runAudit())}>Run UAT</Button>
        <Button variant="secondary" onClick={download} disabled={!results}>
          Download evidence
        </Button>
        {results ? (
          <Badge tone={passed === results.length ? "live" : "danger"}>
            {passed}/{results.length} passed
          </Badge>
        ) : null}
        <Badge tone={b.health.ok ? "live" : "default"}>
          {b.health.ok ? "backend online" : "backend offline"}
        </Badge>
      </div>

      <div className="mt-10 space-y-3">
        {(results ?? runAudit()).map((r) => (
          <div
            key={r.id}
            className="flex flex-col gap-2 rounded-lg bg-card px-4 py-4 shadow-[var(--shadow-border)] sm:flex-row sm:items-center sm:justify-between"
          >
            <div>
              <p className="text-[11px] uppercase tracking-widest text-muted-foreground">
                {r.id} · {r.group}
              </p>
              <p className="mt-1 text-sm text-foreground">{r.name}</p>
              <p className="mt-1 text-xs leading-5 text-muted-foreground">{r.detail}</p>
            </div>
            <Badge tone={r.passed ? "live" : "danger"}>{r.passed ? "green" : "fail"}</Badge>
          </div>
        ))}
      </div>

      <Card className="mt-10">
        <CardKicker>Ledger</CardKicker>
        <CardTitle>What the audits asked for</CardTitle>
        <ul className="mt-6 space-y-5">
          {IMPLEMENTED.map((item) => (
            <li key={item.id} className="border-t border-border pt-5 first:border-0 first:pt-0">
              <p className="text-[11px] uppercase tracking-widest text-live">{item.id}</p>
              <p className="mt-1 text-sm text-foreground">{item.title}</p>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{item.fix}</p>
            </li>
          ))}
        </ul>
      </Card>
    </Shell>
  );
}
