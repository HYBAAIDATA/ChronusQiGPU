import { createFileRoute } from "@tanstack/react-router";
import { useEffect } from "react";
import { Shell } from "@/components/shell";
import { ManifoldView } from "@/components/manifold-view";
import { Card, CardKicker, CardTitle } from "@/components/ui/card";
import { TruthChip } from "@/components/truth";
import { Badge } from "@/components/ui/badge";
import { useBackend } from "@/lib/pythia/backend-store";

export const Route = createFileRoute("/manifold")({ component: ManifoldPage });

function ManifoldPage() {
  const b = useBackend();

  useEffect(() => {
    b.startPolling();
    return () => b.stopPolling();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Derive current face from backend worker attempt counts (mod 32 approximation)
  const workers = b.status?.workers ?? {};
  const totalAttempts = Object.values(workers).reduce(
    (sum, w) => sum + w.attempts_total,
    0,
  );
  const face = totalAttempts % 32;
  const isLive = b.health.ok;

  return (
    <Shell>
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-muted-foreground">
            Poincaré · Cassini · 32 faces
          </p>
          <h1 className="mt-3 max-w-3xl font-display text-4xl font-medium tracking-tight">
            A map of the search order, not a shortcut through SHA-256.
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-muted-foreground">
            The 32-face frame partitions the nonce word (5 bits face, 27 bits local). The
            Cassini oval and golden Weyl walk choose which face to visit next. The digest
            is still SHA-256d — this engine asserts no mining advantage.
          </p>
        </div>
        <Badge tone={isLive ? "live" : "default"} className="shrink-0">
          {isLive ? "live" : "offline"}
        </Badge>
      </div>

      <Card className="mt-8 overflow-hidden p-0">
        <div className="flex items-center justify-between p-5">
          <div>
            <CardKicker>Traversal</CardKicker>
            <CardTitle>B_φ¹¹ projected to the disk</CardTitle>
          </div>
          <TruthChip value="simulated" />
        </div>
        <ManifoldView height={440} />
      </Card>

      <div className="mt-6 grid gap-4 sm:grid-cols-3">
        <Card>
          <CardKicker>Current face</CardKicker>
          <p className="mt-2 font-mono text-3xl tabular-nums">{String(face).padStart(2, "0")}</p>
          <p className="mt-2 text-xs text-muted-foreground">
            {isLive ? "derived from backend attempt count" : "offline — showing last known"}
          </p>
        </Card>
        <Card>
          <CardKicker>Metric</CardKicker>
          <p className="mt-2 font-display text-2xl">ds² = (dx² + dy²) / y²</p>
          <p className="mt-2 text-xs text-muted-foreground">Poincaré upper half-plane, drawn as a disk.</p>
        </Card>
        <Card>
          <CardKicker>Attractor</CardKicker>
          <p className="mt-2 font-display text-2xl">|z−c₁| · |z−c₂| = a²</p>
          <p className="mt-2 text-xs text-muted-foreground">Cassini oval. Internal correctness, not proof-of-work.</p>
        </Card>
      </div>

      {/* Backend total attempts */}
      {isLive && (
        <Card className="mt-6">
          <CardKicker>Backend traversal</CardKicker>
          <CardTitle>Total attempts across all arms</CardTitle>
          <p className="mt-3 font-mono text-3xl tabular-nums">
            {totalAttempts.toLocaleString()}
          </p>
          <p className="mt-2 text-xs text-muted-foreground">
            Sum of attempts_total across all live workers reported by control_api.py.
            Each attempt is a real SHA-256d invocation.
          </p>
        </Card>
      )}
    </Shell>
  );
}
