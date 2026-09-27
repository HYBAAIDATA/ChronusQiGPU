import React, { useMemo, useState } from "react";
import { Sigma } from "lucide-react";
import { TruthChip } from "../components/TruthChip";
import { ExactSequenceMath, Q5 } from "../lib/exact_math";
import { ExactGrover } from "../lib/first_principles_quantum";

const Stat: React.FC<{ k: string; v: string; d?: string }> = ({ k, v, d }) => (
  <div className="console-surface-inset p-4">
    <p className="text-[10px] uppercase tracking-[0.16em] font-telemetry-mono text-[#6b7c93]">{k}</p>
    <p className="mt-2 break-all font-telemetry-mono text-xl tabular-nums text-[#0a2540]">{v}</p>
    {d ? <p className="mt-2 font-telemetry-mono text-[11px] text-[#42566f]">{d}</p> : null}
  </div>
);

/** Exact substrate playground — BigInt Lucas/Cassini/Zeckendorf, Q[√5], Grover. */
export const AlgebraView: React.FC = () => {
  const [n, setN] = useState(15);
  const ln = ExactSequenceMath.lucas(n);
  const fn = ExactSequenceMath.fib(n);
  const cassiniLhs = ln * ln - 5n * fn * fn;
  const cassiniRhs = 4n * (n % 2 === 0 ? 1n : -1n);
  const cassini = cassiniLhs === cassiniRhs;
  const z = ExactSequenceMath.zeckendorf(ln);
  const grover = useMemo(() => ExactGrover.runExactEvolution(2, [3]), []);
  const phi = Q5.phi();
  const phi2 = Q5.phiSquared();

  return (
    <div className="space-y-6 pt-8">
      <div>
        <p className="text-[11px] font-telemetry-mono uppercase tracking-[0.28em] text-[#635bff]">
          Exact substrate
        </p>
        <h1 className="font-serif-display mt-3 text-4xl sm:text-5xl font-semibold tracking-tight text-[#0a2540]">
          Q[√5], Lucas, Cassini, Grover — proved here, not advertised.
        </h1>
        <p className="mt-4 max-w-2xl text-sm leading-relaxed text-[#42566f]">
          Every identity on this page is evaluated with exact BigInt / rational
          arithmetic. Grover runs on the folded |w⟩|u⟩ span — closed-form
          algebra, not simulation. None of it replaces SHA-256d.
        </p>
      </div>

      <section className="console-surface">
        <header className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-[rgba(10,37,64,0.10)]">
          <h2 className="text-[11px] font-telemetry-mono uppercase tracking-[0.2em] text-[#42566f] flex items-center gap-2">
            <span className="text-[#635bff]">
              <Sigma className="w-4 h-4" />
            </span>
            Lucas ladder — n = {n}
          </h2>
          <TruthChip value="computed" />
        </header>
        <div className="p-5">
          <input
            type="range"
            min={0}
            max={40}
            value={n}
            onChange={(e) => setN(Number(e.target.value))}
            className="w-full accent-[#635bff]"
          />
          <div className="mt-5 grid gap-4 sm:grid-cols-3">
            <Stat k="Lₙ" v={ln.toString()} />
            <Stat k="Fₙ" v={fn.toString()} />
            <Stat
              k="Cassini"
              v={cassini ? "holds" : "fails"}
              d={`L² − 5F² = ${cassiniLhs} · 4(−1)ⁿ = ${cassiniRhs}`}
            />
          </div>
          <p className="mt-5 font-telemetry-mono text-xs leading-6 text-[#42566f]">
            Zeckendorf(Lₙ) = {z.indices.map((i) => `F${i}`).join(" + ") || "∅"}
          </p>
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        <section className="console-surface">
          <header className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-[rgba(10,37,64,0.10)]">
            <h2 className="text-[11px] font-telemetry-mono uppercase tracking-[0.2em] text-[#42566f]">
              Pocket-calculator Grover — N = 4, marked |11⟩
            </h2>
            <TruthChip value="computed" />
          </header>
          <div className="p-5 space-y-4">
            {grover.probabilities.map((p, k) => (
              <div key={k}>
                <p className="text-[11px] font-telemetry-mono text-[#6b7c93]">
                  iteration k = {k}
                  {k === grover.optimalK ? " · optimal" : ""}
                </p>
                <div className="mt-1.5 h-6 rounded-[3px] bg-[rgba(255,255,255,0.85)] border border-[rgba(10,37,64,0.14)] overflow-hidden">
                  <div
                    className="h-full bg-[rgba(99,91,255,0.55)] transition-all"
                    style={{ width: `${Math.max(2, p * 100)}%` }}
                  />
                </div>
                <p className="mt-1 font-telemetry-mono text-xs tabular-nums text-[#42566f]">
                  Pr(marked) = {p.toFixed(4)}
                </p>
              </div>
            ))}
            <p className="text-[11px] font-telemetry-mono leading-5 text-[#6b7c93]">
              Folded evolution on span{'{'}|w⟩, |u⟩{'}'} — Cassini witness drift{" "}
              {grover.cassiniDrift.toExponential(2)}. Marked |11⟩ reaches Pr = 1
              after the optimal single iteration.
            </p>
          </div>
        </section>

        <section className="console-surface">
          <header className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-[rgba(10,37,64,0.10)]">
            <h2 className="text-[11px] font-telemetry-mono uppercase tracking-[0.2em] text-[#42566f]">
              Quadratic field — φ = (1 + √5) / 2 ∈ Q[√5]
            </h2>
            <TruthChip value="computed" />
          </header>
          <div className="p-5">
            <dl className="space-y-4 text-sm">
              <div>
                <dt className="text-[11px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93]">φ</dt>
                <dd className="mt-1 font-telemetry-mono text-[#0a2540]">{phi.toString()}</dd>
              </div>
              <div>
                <dt className="text-[11px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93]">φ²</dt>
                <dd className="mt-1 font-telemetry-mono text-[#0a2540]">{phi2.toString()}</dd>
              </div>
              <div>
                <dt className="text-[11px] font-telemetry-mono uppercase tracking-wider text-[#6b7c93]">
                  Field norm N(φ) = a² − 5b²
                </dt>
                <dd className="mt-1 font-telemetry-mono text-[#0a2540]">
                  {phi.algebraicNorm().toString()}
                </dd>
              </div>
              <p className="text-[11px] font-telemetry-mono leading-5 text-[#6b7c93]">
                Closed under addition and multiplication. The Pisot conjugate of
                φ is 1 − φ, which is why Lucas scaling is exact on integers
                rather than floats.
              </p>
            </dl>
          </div>
        </section>
      </div>
    </div>
  );
};
