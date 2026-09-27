import { createFileRoute, Link } from "@tanstack/react-router";
import { ArrowRight } from "lucide-react";
import { useEffect } from "react";
import { Shell } from "@/components/shell";
import { Pipeline } from "@/components/pipeline";
import { Metric } from "@/components/truth";
import { Button } from "@/components/ui/button";
import { Card, CardKicker, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatHps } from "@/lib/pythia/math";
import { useBackend } from "@/lib/pythia/backend-store";

export const Route = createFileRoute("/")({ component: Home });

function Home() {
  const b = useBackend();

  useEffect(() => {
    b.startPolling();
    return () => b.stopPolling();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stratum = b.status?.stratum;
  const engine = b.status?.canonicalEngine;
  const evidence = {
    connected: stratum?.connected ?? false,
    authorized: stratum?.connected ?? false,
    job_received: stratum?.connected ?? false,
    candidate_found: (b.telemetry?.shares_accepted ?? 0) > 0,
    submitted: (b.telemetry?.shares_accepted ?? 0) > 0,
    accepted: (b.telemetry?.shares_accepted ?? 0) > 0,
  };

  return (
    <Shell>
      <section className="max-w-3xl">
        <div className="flex items-center gap-3">
          <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-muted-foreground">
            HYBA · PYTHIA
          </p>
          <Badge tone={b.health.ok ? "live" : "default"}>
            {b.health.ok ? "backend online" : "backend offline"}
          </Badge>
        </div>
        <h1 className="mt-4 font-display text-4xl font-medium leading-[1.1] tracking-tight sm:text-5xl">
          The operator console that refuses to lie.
        </h1>
        <p className="mt-5 max-w-2xl text-base leading-7 text-muted-foreground">
          SHA-256d is the sole accept authority. Every figure carries a truth class.
          Mining is executed by the Python backend via a live Stratum connection.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          {b.health.ok ? (
            <>
              <Button onClick={() => void b.startMining()} className="min-w-40">
                Start mining
              </Button>
              <Button variant="secondary" onClick={() => void b.stopMining()}>
                Stop mining
              </Button>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              Start the Python backend:{" "}
              <code className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
                PYTHIA_PORT=3001 python main.py
              </code>
            </p>
          )}
          <Button variant="secondary" asChild>
            <Link to="/audit">
              Run the audit
              <ArrowRight />
            </Link>
          </Button>
        </div>
      </section>

      <section className="mt-12 min-w-0">
        <CardKicker>Evidence gates</CardKicker>
        <Pipeline evidence={evidence} />
        <p className="mt-3 text-xs leading-5 text-muted-foreground">
          Gates reflect the live Python backend state. Connected means a real Stratum
          socket is open. Accepted means the pool returned result=true after SHA-256d.
        </p>
      </section>

      <section className="mt-10 grid min-w-0 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric
          label="Stratum"
          value={stratum?.status ?? (stratum?.connected ? "connected" : "disconnected")}
          truth={stratum?.connected ? "measured" : "unavailable"}
          hint="Live pool connection state from the Python Stratum client."
        />
        <Metric
          label="Hashrate"
          value={
            b.telemetry?.hashrate != null
              ? formatHps(Number(b.telemetry.hashrate))
              : engine?.hashrate ?? "—"
          }
          truth={b.health.ok ? "measured" : "unavailable"}
          hint="Measured by the Python mining engine. Never Lucas-scaled."
        />
        <Metric
          label="Shares accepted"
          value={String(b.telemetry?.shares_accepted ?? "—")}
          truth={b.health.ok ? "measured" : "unavailable"}
          hint="Pool-acknowledged shares since process start."
        />
        <Metric
          label="Pool latency"
          value={
            b.telemetry?.pool_latency_ms != null
              ? `${b.telemetry.pool_latency_ms} ms`
              : "—"
          }
          truth={b.health.ok && b.telemetry?.pool_latency_ms != null ? "measured" : "unavailable"}
          hint="Round-trip to the pool measured by the Stratum layer."
        />
      </section>

      <section className="mt-10 grid min-w-0 gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <Card className="min-w-0 overflow-hidden p-0">
          <div className="p-5">
            <CardKicker>Workers</CardKicker>
            <CardTitle>Live arm status</CardTitle>
          </div>
          {b.status?.workers && Object.keys(b.status.workers).length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[420px] text-left text-sm">
                <thead className="border-y border-border text-[11px] uppercase tracking-widest text-muted-foreground">
                  <tr>
                    <th className="px-5 py-2 font-medium">Worker</th>
                    <th className="px-5 py-2 font-medium">State</th>
                    <th className="px-5 py-2 font-medium">H/s</th>
                    <th className="px-5 py-2 font-medium">Shares</th>
                    <th className="px-5 py-2 font-medium">Live</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(b.status.workers).map(([name, w]) => (
                    <tr key={name} className="border-b border-border/70">
                      <td className="px-5 py-3 font-mono text-xs">{name}</td>
                      <td className="px-5 py-3 text-sm">{w.state}</td>
                      <td className="px-5 py-3 font-mono tabular-nums text-xs">
                        {formatHps(w.effectiveness.hashrate)}
                      </td>
                      <td className="px-5 py-3 tabular-nums">{w.effectiveness.shares_accepted}</td>
                      <td className="px-5 py-3">
                        <Badge tone={w.liveness ? "live" : "default"}>
                          {w.liveness ? "live" : "dead"}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="px-5 pb-5 text-sm text-muted-foreground">
              {b.health.ok ? "No workers reported yet." : "Backend offline — no worker data."}
            </p>
          )}
        </Card>

        <Card className="min-w-0">
          <CardKicker>Engine</CardKicker>
          <CardTitle>{engine?.product ?? "—"}</CardTitle>
          {engine ? (
            <dl className="mt-5 space-y-3 text-sm">
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Backend</dt>
                <dd className="font-mono text-xs">{engine.backend}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Execution</dt>
                <dd className="font-mono text-xs">{engine.execution}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Fallback</dt>
                <dd>{engine.fallback ? "yes" : "no"}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt className="text-muted-foreground">Ladder</dt>
                <dd className="font-mono text-xs">[{engine.ladder.join(", ")}]</dd>
              </div>
            </dl>
          ) : (
            <p className="mt-5 text-sm text-muted-foreground">
              {b.health.ok ? "Awaiting first status response." : "Backend offline."}
            </p>
          )}
        </Card>
      </section>

      <section className="mt-10">
        <Card className="min-w-0">
          <CardKicker>Agentic controller</CardKicker>
          <CardTitle>Autonomous campaign management</CardTitle>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            The agentic controller runs pool selection, escalation, and campaign
            management. It reorders and prunes the search space — it never bypasses SHA-256d.
          </p>
          <div className="mt-5 flex flex-wrap gap-3">
            <Button
              variant="secondary"
              onClick={() => void b.startAgentic()}
              disabled={!b.health.ok}
            >
              Start agentic
            </Button>
            <Button
              variant="secondary"
              onClick={() => void b.stopAgentic()}
              disabled={!b.health.ok}
            >
              Stop agentic
            </Button>
            <Button
              variant="secondary"
              onClick={() => void b.runSelfTest()}
              disabled={!b.health.ok}
            >
              Run self-test
            </Button>
          </div>
        </Card>
      </section>
    </Shell>
  );
}
