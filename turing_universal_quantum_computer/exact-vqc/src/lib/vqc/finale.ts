/** The proposed Lucas replacement for the Grover angle.

The claim substitutes 1/√5 for π/4 and reads a universal 43% reduction off those two decimals.
π is not in Q(√5), and the Grover invariant is a different quadratic form from the golden norm.
This report keeps only the integer comparison the recurrence can decide.
*/

import { Frac } from "./algebra.ts";

const SIZES = [4n, 100n, 1000n, 10000n];

function groverOnce(total: bigint, marked: bigint, amplitude: Frac, other: Frac): [Frac, Frac] {
  const flipped = amplitude.neg();
  const mean = new Frac(marked).mul(flipped).add(new Frac(total - marked).mul(other)).div(new Frac(total));
  return [new Frac(2n).mul(mean).sub(flipped), new Frac(2n).mul(mean).sub(other)];
}

function walk(total: bigint, marked: bigint): { k: number; probability: Frac; next: Frac } {
  let amplitude = new Frac(1n);
  let other = new Frac(1n);
  let probability = new Frac(marked).div(new Frac(total));
  let k = 0;
  for (;;) {
    const [nextAmplitude, nextOther] = groverOnce(total, marked, amplitude, other);
    const invariant = new Frac(marked).mul(nextAmplitude).mul(nextAmplitude).add(new Frac(total - marked).mul(nextOther).mul(nextOther));
    if (invariant.cmp(new Frac(total)) !== 0) throw new Error("Grover left the circle");
    const next = new Frac(marked).mul(nextAmplitude).mul(nextAmplitude).div(new Frac(total));
    if (next.cmp(probability) <= 0) return { k, probability, next };
    amplitude = nextAmplitude;
    other = nextOther;
    probability = next;
    k += 1;
    if (k > 500) throw new Error("the walk did not turn down");
  }
}

function probabilityAt(total: bigint, marked: bigint, steps: number): Frac {
  let amplitude = new Frac(1n);
  let other = new Frac(1n);
  for (let step = 0; step < steps; step++) [amplitude, other] = groverOnce(total, marked, amplitude, other);
  return new Frac(marked).mul(amplitude).mul(amplitude).div(new Frac(total));
}

/** Largest integer m with 5 m² ≤ N. This is the integer under √(N/5), with no root taken. */
function latticeBound(total: bigint): bigint {
  let m = 0n;
  while (5n * (m + 1n) * (m + 1n) <= total) m += 1n;
  return m;
}

let cached: string | null = null;

export function finaleReport(): string {
  if (cached) return cached;
  const lines = [
    "finale",
    "  claim = replace π/4 by 1/√5 inside Grover",
    "  verdict = REFUSED",
    "  theorem_proven = False",
    "",
    "[two forms]",
    "  Grover preserves M A² + (N−M) B² = N",
    "  for one marked state the form is A² + (N−1) B²",
    "  its discriminant is −4(N−1), which is negative",
    "  the form is definite: a circle",
    "  the golden norm is x² − 5 y²",
    "  its discriminant is 20, which is positive",
    "  the form is indefinite: a hyperbola",
    "  Cassini is that norm on the units, L² − 5 F² = 4(−1)^n",
    "  a definite form is not equivalent to an indefinite form",
    "  no change of basis turns the Grover step into a Lucas step",
    "",
    "[what the angle was never doing]",
    "  the exact iteration count is the first descent of the rational sequence",
    "  π is not an input",
    "  there is no transcendental term to strip",
    "  a decimal ratio of π/4 to 1/√5 is refused",
    "",
    "[the integer that 1/√5 would have picked]",
  ];
  const ratios: Frac[] = [];
  for (const total of SIZES) {
    const peak = walk(total, 1n);
    const bound = latticeBound(total);
    const early = probabilityAt(total, 1n, Number(bound));
    if (bound > 0n && early.cmp(peak.probability) >= 0) throw new Error("the lattice bound met the peak");
    if (peak.next.cmp(peak.probability) > 0) throw new Error("the recorded peak is not a descent");
    const ratio = bound === 0n ? null : new Frac(bound, BigInt(peak.k));
    if (ratio) ratios.push(ratio);
    lines.push(
      `  N = ${total}    k = ${peak.k}    5m² ≤ N gives m = ${bound}` +
        (ratio ? `    m/k = ${ratio}    P(m) < P(k) = True` : "    the bound takes no step") +
        "    one step past k descends = True",
    );
  }
  if (ratios.length < 2) throw new Error("not enough widths to test a universal ratio");
  const same = ratios.every((ratio) => ratio.toString() === ratios[0].toString());
  lines.push(`  the ratios m/k are ${same ? "the same" : "not the same"}`);
  lines.push("  a universal reduction is refuted by that disagreement");
  lines.push("  Lucas still scales a budget by L_target/L_source");
  lines.push("  it does not scale the Grover angle");
  cached = lines.join("\n");
  return cached;
}
