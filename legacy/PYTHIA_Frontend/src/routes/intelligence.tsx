import { createFileRoute } from "@tanstack/react-router";
import { useEffect } from "react";
import { Shell } from "@/components/shell";
import { TruthChip } from "@/components/truth";
import { Card, CardKicker, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { SUBSTRATES } from "@/lib/pythia/engine";
import { useBackend } from "@/lib/pythia/backend-store";

export const Route = createFileRoute("/intelligence")({ component: IntelPage });

export function IntelPage() {
  const b = useBackend();

  useEffect(() => {
    b.startPolling();
    return () => b.stopPolling();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const intel = b.intelligenceStatus;
  const checks = intel?.summary?.checks;
  const failures = intel?.summary?.failures ?? [];

  return (
    <Shell>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-muted-foreground">
            Five authorities · thirteen substrates
          </p>
          <h1 className="mt-3 max-w-3xl font-display text-4xl font-medium tracking-tight">
            Intelligence reorders search. It never fakes a proof.
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-muted-foreground">
            The Python intelligence engine orchestrates pool selection, nonce ordering,
            and TOE tensor context. All decisions are functions of the live backend state.
            SHA-256d is never bypassed.
          </p>
        </div>
        <Badge tone={b.health.ok ? "live" : "default"} className="shrink-0">
          {b.health.ok ? "backend online" : "offline"}
        </Badge>
      </div>

      {/* Intelligence self-test status */}
      <Card className="mt-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <CardKicker>Self-test</CardKicker>
            <CardTitle>Intelligence engine verification</CardTitle>
          </div>
          <TruthChip value={b.health.ok ? "measured" : "unavailable"} />
        </div>
        {intel ? (
          <div className="mt-5 space-y-3">
            <div className="flex flex-wrap gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">State: </span>
                <span className="font-mono">{intel.state ?? "—"}</span>
              </div>
              {checks && (
                <div>
                  <span className="text-muted-foreground">Checks: </span>
                  <span className="font-mono">
                    {checks.passed}/{checks.total}
                  </span>
                </div>
              )}
              {intel.summary?.passed !== undefined && (
                <Badge tone={intel.summary.passed ? "live" : "default"}>
                  {intel.summary.passed ? "all passed" : "failures present"}
                </Badge>
              )}
            </div>
            {failures.length > 0 && (
              <ul className="mt-3 space-y-1 font-mono text-xs text-muted-foreground">
                {failures.map((f, i) => (
                  <li key={i} className="text-red-500">{f}</li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <p className="mt-5 text-sm text-muted-foreground">
            {b.health.ok
              ? "No self-test data. Run a test to populate."
              : "Backend offline. Start Python backend to see intelligence status."}
          </p>
        )}
        <div className="mt-5 flex gap-3">
          <Button
            variant="secondary"
            onClick={() => void b.runSelfTest()}
            disabled={!b.health.ok}
          >
            Run self-test
          </Button>
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
        </div>
      </Card>

      {/* Fabric map subsystem list */}
      {b.fabricMap?.subsystems && b.fabricMap.subsystems.length > 0 && (
        <Card className="mt-8 overflow-hidden p-0">
          <div className="p-5">
            <CardKicker>System fabric</CardKicker>
            <CardTitle>Wired intelligence subsystems</CardTitle>
          </div>
          <ul className="divide-y divide-border border-t border-border text-sm">
            {b.fabricMap.subsystems.map((sub) => (
              <li key={sub.key} className="grid grid-cols-[8rem_1fr_6rem_5rem] gap-3 px-5 py-3">
                <span className="font-mono text-xs text-muted-foreground">{sub.key}</span>
                <span>{sub.name}</span>
                <span className="font-mono text-xs">{sub.wired}</span>
                <Badge tone={sub.present ? "live" : "default"}>
                  {sub.present ? "present" : "absent"}
                </Badge>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {/* Substrate registry */}
      <Card className="mt-8">
        <CardKicker>Substrates</CardKicker>
        <CardTitle>Present as algebra, not as fabricated telemetry</CardTitle>
        <ul className="mt-5 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
          {SUBSTRATES.map((name) => (
            <li
              key={name}
              className="rounded-md px-3 py-3 text-sm shadow-[var(--shadow-border)]"
            >
              <p className="text-foreground">{name}</p>
              <p className="mt-1 text-[11px] uppercase tracking-widest text-muted-foreground">
                {name === "iGPU" ? "unavailable here" : name === "Quantum" ? "algebraic" : "wired"}
              </p>
            </li>
          ))}
        </ul>
      </Card>
    </Shell>
  );
}
