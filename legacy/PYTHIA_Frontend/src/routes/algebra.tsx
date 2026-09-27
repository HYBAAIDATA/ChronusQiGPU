import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { Shell } from "@/components/shell";
import { TruthChip } from "@/components/truth";
import { Card, CardKicker, CardTitle } from "@/components/ui/card";
import {
  born,
  cassiniHolds,
  cassiniLeft,
  cassiniRight,
  fibonacci,
  Fraction,
  groverMarked11,
  lucas,
  q5,
  q5Mul,
  q5Norm,
  q5ToString,
  zeckendorf,
} from "@/lib/pythia/math";

export const Route = createFileRoute("/algebra")({ component: AlgebraPage });

function AlgebraPage() {
  const [n, setN] = useState(15);
  const ln = lucas(n);
  const fn = fibonacci(n);
  const cassini = cassiniHolds(n);
  const z = zeckendorf(ln);
  const grover = useMemo(() => groverMarked11(), []);
  const phi = q5(new Fraction(1n, 2n), new Fraction(1n, 2n));
  const phi2 = q5Mul(phi, phi);

  return (
    <Shell>
      <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-muted-foreground">
        Exact substrate
      </p>
      <h1 className="mt-3 max-w-3xl font-display text-4xl font-medium tracking-tight">
        Q[√5], Lucas, Cassini, Grover — proved here, not advertised.
      </h1>
      <p className="mt-4 max-w-2xl text-sm leading-6 text-muted-foreground">
        Every identity on this page is evaluated with BigInt. The pocket-calculator Grover
        is exact on four amplitudes. None of it replaces SHA-256d.
      </p>

      <Card className="mt-10">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardKicker>Ladder</CardKicker>
            <CardTitle>n = {n}</CardTitle>
          </div>
          <TruthChip value="measured" />
        </div>
        <input
          type="range"
          min={0}
          max={40}
          value={n}
          onChange={(e) => setN(Number(e.target.value))}
          className="mt-6 w-full accent-accent"
        />
        <div className="mt-6 grid gap-4 sm:grid-cols-3">
          <Stat k="Lₙ" v={ln.toString()} />
          <Stat k="Fₙ" v={fn.toString()} />
          <Stat
            k="Cassini"
            v={cassini ? "holds" : "fails"}
            d={`L² − 5F² = ${cassiniLeft(n)} · 4(−1)ⁿ = ${cassiniRight(n)}`}
          />
        </div>
        <p className="mt-5 font-mono text-xs leading-6 text-muted-foreground">
          Zeckendorf(Lₙ) = {z.map((i) => `F${i}`).join(" + ") || "∅"}
        </p>
      </Card>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardKicker>Pocket calculator Grover</CardKicker>
          <CardTitle>N = 4, marked |11⟩, one iteration</CardTitle>
          <div className="mt-6 space-y-5">
            {grover.steps.map((step) => {
              const p = born(step.state);
              return (
                <div key={step.label}>
                  <p className="text-xs text-muted-foreground">{step.label}</p>
                  <div className="mt-2 grid grid-cols-4 gap-2">
                    {p.map((pr, i) => (
                      <div key={i} className="rounded-md bg-secondary p-2">
                        <div className="flex h-16 items-end">
                          <div
                            className="w-full rounded-sm bg-accent/80"
                            style={{ height: `${Math.max(4, pr * 100)}%` }}
                          />
                        </div>
                        <p className="mt-2 font-mono text-[10px] text-muted-foreground">
                          |{i.toString(2).padStart(2, "0")}⟩
                        </p>
                        <p className="font-mono text-xs tabular-nums">{pr.toFixed(2)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
        <Card>
          <CardKicker>Quadratic field</CardKicker>
          <CardTitle>φ = (1 + √5) / 2 ∈ Q[√5]</CardTitle>
          <dl className="mt-6 space-y-4 text-sm">
            <div>
              <dt className="text-muted-foreground">φ</dt>
              <dd className="mt-1 font-mono">{q5ToString(phi)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">φ²</dt>
              <dd className="mt-1 font-mono">{q5ToString(phi2)}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Field norm N(φ) = a² − 5b²</dt>
              <dd className="mt-1 font-mono">{q5Norm(phi).toString()}</dd>
            </div>
            <p className="text-xs leading-5 text-muted-foreground">
              Closed under addition and multiplication. The Pisot conjugate of φ is 1 − φ,
              which is why Lucas scaling is exact on integers rather than floats.
            </p>
          </dl>
        </Card>
      </div>
    </Shell>
  );
}

function Stat({ k, v, d }: { k: string; v: string; d?: string }) {
  return (
    <div className="rounded-lg bg-secondary/60 p-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">{k}</p>
      <p className="mt-2 break-all font-mono text-xl tabular-nums">{v}</p>
      {d ? <p className="mt-2 font-mono text-[11px] text-muted-foreground">{d}</p> : null}
    </div>
  );
}
