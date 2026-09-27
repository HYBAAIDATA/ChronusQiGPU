import { createFileRoute } from "@tanstack/react-router";
import { useEffect } from "react";
import { Shell } from "@/components/shell";
import { Metric, TruthChip } from "@/components/truth";
import { Button } from "@/components/ui/button";
import { Card, CardKicker, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatHps } from "@/lib/pythia/math";
import { useBackend } from "@/lib/pythia/backend-store";

export const Route = createFileRoute("/console")({ component: ConsolePage });

function ConsolePage() {
  const b = useBackend();

  useEffect(() => {
    b.startPolling();
    return () => b.stopPolling();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stratum = b.status?.stratum;
  const engine = b.status?.canonicalEngine;
  const tel = b.telemetry;
  const workers = b.status?.workers ?? {};
  const workerList = Object.entries(workers);

  return (
    <Shell>
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-muted-foreground">
            Mining console
          </p>
          <h1 className="mt-3 font-display text-4xl font-medium tracking-tight">
            Search, check, hold.
          </h1>
          <p className="mt-3 max-w-xl text-sm leading-6 text-muted-foreground">
            All operations executed by the Python mining backend via Stratum.
            SHA-256d is the sole accept authority.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button onClick={() => void b.startMining()} disabled={!b.health.ok}>
            Start mining
          </Button>
          <Button variant="secondary" onClick={() => void b.stopMining()} disabled={!b.health.ok}>
            Stop mining
          </Button>
          <Button
            variant="secondary"
            onClick={() => void b.refresh()}
            disabled={b.loading}
          >
            {b.loading ? "Refreshing…" : "Refresh"}
          </Button>
        </div>
      </div>

      <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric
          label="Stratum"
          value={stratum?.status ?? (stratum?.connected ? "connected" : "disconnected")}
          truth={stratum?.connected ? "measured" : "unavailable"}
        />
        <Metric
          label="Backend"
          value={engine?.backend ?? "—"}
          truth={b.health.ok ? "measured" : "unavailable"}
        />
        <Metric
          label="Hashrate"
          value={
            tel?.hashrate != null ? formatHps(Number(tel.hashrate)) : engine?.hashrate ?? "—"
          }
          truth={b.health.ok ? "measured" : "unavailable"}
        />
        <Metric
          label="Uptime"
          value={tel?.uptime_s != null ? `${tel.uptime_s.toLocaleString()} s` : "—"}
          truth={b.health.ok ? "measured" : "unavailable"}
        />
      </div>

      <div className="mt-8 grid gap-4 lg:grid-cols-[1.15fr_0.85fr]">
        {/* Fabric subsystems */}
        <Card className="overflow-hidden p-0">
          <div className="p-5">
            <CardKicker>System fabric</CardKicker>
            <CardTitle>Wired subsystems</CardTitle>
          </div>
          {b.fabricMap?.subsystems && b.fabricMap.subsystems.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[500px] text-left text-sm">
                <thead className="border-y border-border text-[11px] uppercase tracking-widest text-muted-foreground">
                  <tr>
                    <th className="px-5 py-2 font-medium">Key</th>
                    <th className="px-5 py-2 font-medium">Name</th>
                    <th className="px-5 py-2 font-medium">Wired</th>
                    <th className="px-5 py-2 font-medium">Present</th>
                  </tr>
                </thead>
                <tbody>
                  {b.fabricMap.subsystems.map((sub) => (
                    <tr key={sub.key} className="border-b border-border/70">
                      <td className="px-5 py-3 font-mono text-xs">{sub.key}</td>
                      <td className="px-5 py-3 text-sm">{sub.name}</td>
                      <td className="px-5 py-3 font-mono text-xs">{sub.wired}</td>
                      <td className="px-5 py-3">
                        <Badge tone={sub.present ? "live" : "default"}>
                          {sub.present ? "yes" : "no"}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="px-5 pb-5 text-sm text-muted-foreground">
              {b.health.ok ? "No subsystem data yet." : "Backend offline."}
            </p>
          )}
        </Card>

        {/* Engine + controls */}
        <Card>
          <CardKicker>Engine</CardKicker>
          <CardTitle>Execution path</CardTitle>
          {engine ? (
            <dl className="mt-5 space-y-3 text-sm">
              <Row k="product" v={engine.product} />
              <Row k="backend" v={engine.backend} />
              <Row k="execution" v={engine.execution} />
              <Row k="hashrate" v={engine.hashrate} />
              <Row k="fallback" v={engine.fallback ? "yes" : "no"} />
              <Row k="ladder" v={`[${engine.ladder.join(", ")}]`} />
            </dl>
          ) : (
            <p className="mt-5 text-sm text-muted-foreground">
              {b.health.ok ? "Awaiting response." : "Backend offline."}
            </p>
          )}
        </Card>
      </div>

      {/* Workers */}
      <Card className="mt-8 overflow-hidden p-0">
        <div className="flex items-center justify-between p-5">
          <div>
            <CardKicker>Workers</CardKicker>
            <CardTitle>Live arm status from Python backend</CardTitle>
          </div>
          <TruthChip value={b.health.ok ? "measured" : "unavailable"} />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-y border-border text-[11px] uppercase tracking-widest text-muted-foreground">
              <tr>
                <th className="px-5 py-2 font-medium">Worker</th>
                <th className="px-5 py-2 font-medium">State</th>
                <th className="px-5 py-2 font-medium">Hashrate</th>
                <th className="px-5 py-2 font-medium">Shares</th>
                <th className="px-5 py-2 font-medium">Liveness</th>
                <th className="px-5 py-2 font-medium">Last error</th>
              </tr>
            </thead>
            <tbody>
              {workerList.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-5 py-8 text-muted-foreground">
                    {b.health.ok
                      ? "No workers reported. Start mining to spawn arms."
                      : "Backend offline — start Python backend to see live workers."}
                  </td>
                </tr>
              ) : (
                workerList.map(([name, w]) => (
                  <tr key={name} className="border-b border-border/70">
                    <td className="px-5 py-3 font-mono text-xs">{name}</td>
                    <td className="px-5 py-3">{w.state}</td>
                    <td className="px-5 py-3 font-mono tabular-nums text-xs">
                      {formatHps(w.effectiveness.hashrate)}
                    </td>
                    <td className="px-5 py-3 tabular-nums">{w.effectiveness.shares_accepted}</td>
                    <td className="px-5 py-3">
                      <Badge tone={w.liveness ? "live" : "default"}>
                        {w.liveness ? "live" : "dead"}
                      </Badge>
                    </td>
                    <td className="px-5 py-3 font-mono text-xs text-muted-foreground">
                      {w.last_error ? `${w.last_error.kind}: ${w.last_error.message}` : "—"}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </Shell>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex min-w-0 items-baseline justify-between gap-3">
      <dt className="shrink-0 text-muted-foreground">{k}</dt>
      <dd className="min-w-0 break-all font-mono text-xs text-foreground">{v}</dd>
    </div>
  );
}
