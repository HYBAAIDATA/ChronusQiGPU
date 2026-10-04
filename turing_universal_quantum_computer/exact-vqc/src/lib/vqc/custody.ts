/** Custody of an integer, and the Lucas cure for a long walk.

Zeckendorf and Binet fold it. Fibonacci and Cassini store it.
Lucas and Pisot scale it. A long recurrence is not walked: it is doubled,
by the same identities that compute L_n. A decimal is refused.
*/

import { Frac } from "./algebra.ts";
import { LADDER, authorise, cassiniHolds, cassiniSeal, fibonacci, lucas } from "./lucas-scale.ts";

type Ring = { a: bigint; b: bigint };

function mul(p: Ring, q: Ring): Ring {
  return { a: p.a * q.a + p.b * q.b, b: p.a * q.b + p.b * q.a + p.b * q.b };
}

function phiPower(n: number): Ring {
  let result: Ring = { a: 1n, b: 0n };
  let base: Ring = { a: 0n, b: 1n };
  let exp = n;
  while (exp > 0) {
    if (exp & 1) result = mul(result, base);
    base = mul(base, base);
    exp >>= 1;
  }
  return result;
}

function zeckendorf(payload: bigint): number[] {
  if (payload < 0n) throw new Error("a fold payload must be non-negative");
  if (payload === 0n) return [];
  let hi = 2;
  while (fibonacci(hi) <= payload) {
    hi += 1;
    if (hi > 20000) throw new Error("payload is above the exact fold index");
  }
  const indices: number[] = [];
  let remaining = payload;
  for (let index = hi - 1; index >= 2 && remaining > 0n; index--) {
    const limb = fibonacci(index);
    if (limb <= remaining) {
      indices.push(index);
      remaining -= limb;
    }
  }
  if (remaining !== 0n) throw new Error("Zeckendorf did not exhaust the payload");
  for (let i = 1; i < indices.length; i++) {
    if (indices[i - 1] - indices[i] < 2) throw new Error("Zeckendorf produced an adjacent code");
  }
  return indices;
}

function showCode(indices: number[]): string {
  if (!indices.length) return "0";
  return indices.map((index) => `F_${index}`).join(" + ");
}

function showLimbs(indices: number[]): string {
  return indices.map((index) => fibonacci(index).toString()).join(" + ");
}

export function foldReport(payload = lucas(15)): string {
  if (payload < 0n) return "REFUSED: a fold payload must be a non-negative integer";
  const indices = zeckendorf(payload);
  const rebuilt = indices.reduce((sum, index) => sum + fibonacci(index), 0n);
  if (rebuilt !== payload) throw new Error("Zeckendorf sum left the payload");
  const n = 15;
  const folded = phiPower(n);
  if (folded.a !== fibonacci(n - 1) || folded.b !== fibonacci(n)) throw new Error("Binet fold left Z[φ]");
  const conjugateA = fibonacci(n + 1);
  const conjugateB = -fibonacci(n);
  const lucasFromPair = folded.a + conjugateA;
  if (lucasFromPair !== lucas(n) || conjugateB !== -folded.b) throw new Error("Pisot conjugate left the Lucas integer");
  for (const rung of LADDER) {
    const code = zeckendorf(lucas(rung));
    const expect = [rung + 1, rung - 1];
    if (code.length !== 2 || code[0] !== expect[0] || code[1] !== expect[1]) {
      throw new Error(`Lucas rung ${rung} did not fold onto the Cassini pair`);
    }
    if (!cassiniHolds(rung)) throw new Error(`Cassini store failed at ${rung}`);
  }
  const gate = authorise(15, 17);
  if (!gate.accepted || !gate.ratio) throw new Error("the scale transition left the ladder");
  const det = fibonacci(n + 1) * fibonacci(n - 1) - fibonacci(n) * fibonacci(n);
  if (det !== cassiniSeal(n)) throw new Error("the stored matrix determinant left Cassini");
  const lines = [
    "custody",
    "  fold  = Zeckendorf + Binet",
    "  store = Fibonacci + Cassini",
    "  scale = Lucas + Pisot",
    "  theorem_proven = False",
    "",
    "[store]",
    `  Fibonacci word at 15    F_15 = ${fibonacci(n)}`,
    `  Cassini seal at 15      F_16 F_14 − F_15² = ${det < 0n ? "−1" : "+1"}`,
    `  matrix M^15 = [[${fibonacci(n + 1)}, ${fibonacci(n)}], [${fibonacci(n)}, ${fibonacci(n - 1)}]]`,
    "  the seal is ±1, so the store inverts",
    "",
    "[fold]",
    `  payload ${payload}`,
    `  Zeckendorf = ${showCode(indices)}`,
    `  limbs = ${showLimbs(indices)}`,
    "  sums back = True    non-adjacent = True",
    `  every ladder Lucas number folds as L_n = F_(n+1) + F_(n−1)`,
    `  Binet    φ^15 = ${fibonacci(n - 1)} + ${fibonacci(n)}φ`,
    "  the power is those two stored Fibonacci words",
    "",
    "[scale]",
    `  Lucas    L_15 = ${lucas(n)}    L_17 = ${gate.lucasTarget}`,
    `  ratio = ${gate.ratio.toString()}`,
    `  Pisot    ψ^15 = ${conjugateA} − ${fibonacci(n)}φ`,
    "  L_15 = φ^15 + ψ^15    the conjugate is kept",
    "  4 < 5 < 9, so 2 < √5 < 3, so 1 < φ < 2, so |ψ| < 1",
    "  an adjacent Fibonacci code is not a fold",
    "  a decimal Binet value is refused",
  ];
  if (new Frac(gate.lucasTarget, gate.lucasSource).toString() !== gate.ratio.toString()) {
    throw new Error("scale ratio left the Lucas integers");
  }
  return lines.join("\n");
}

type M2 = [Frac, Frac, Frac, Frac];

function isqrt(value: bigint): bigint {
  if (value < 0n) throw new Error("integer square root of a negative");
  if (value < 2n) return value;
  let x = 1n << BigInt((value.toString(2).length + 1) >> 1);
  for (;;) {
    const next = (x + value / x) >> 1n;
    if (next >= x) return x;
    x = next;
  }
}

function stepMatrix(total: bigint, marked: bigint): M2 {
  const denominator = new Frac(total);
  const diagonal = new Frac(total - 2n * marked).div(denominator);
  return [diagonal, new Frac(2n * (total - marked)).div(denominator), new Frac(-2n * marked).div(denominator), diagonal];
}

function mul2(left: M2, right: M2): M2 {
  return [
    left[0].mul(right[0]).add(left[1].mul(right[2])),
    left[0].mul(right[1]).add(left[1].mul(right[3])),
    left[2].mul(right[0]).add(left[3].mul(right[2])),
    left[2].mul(right[1]).add(left[3].mul(right[3])),
  ];
}

function apply2(matrix: M2, markedAmp: Frac, otherAmp: Frac): [Frac, Frac] {
  return [matrix[0].mul(markedAmp).add(matrix[1].mul(otherAmp)), matrix[2].mul(markedAmp).add(matrix[3].mul(otherAmp))];
}

function pow2(matrix: M2, exponent: number): { matrix: M2; multiplies: number } {
  let result: M2 = [new Frac(1n), new Frac(0n), new Frac(0n), new Frac(1n)];
  let base = matrix;
  let exp = exponent;
  let multiplies = 0;
  while (exp > 0) {
    if (exp & 1) {
      result = mul2(result, base);
      multiplies += 1;
    }
    exp >>= 1;
    if (exp > 0) {
      base = mul2(base, base);
      multiplies += 1;
    }
  }
  return { matrix: result, multiplies };
}

function markedAt(matrix: M2, total: bigint, marked: bigint, steps: number): Frac {
  const powered = pow2(matrix, steps);
  const [amplitude] = apply2(powered.matrix, new Frac(1n), new Frac(1n));
  return new Frac(marked).mul(amplitude).mul(amplitude).div(new Frac(total));
}

function doubledPeak(total: bigint, marked: bigint): { k: number; probability: Frac; multiplies: number; ceiling: bigint } {
  const ceiling = isqrt(total / marked);
  if (ceiling > 1_000_000n) throw new Error("the exact peak is above the doubling ceiling");
  const matrix = stepMatrix(total, marked);
  let lo = 0;
  let hi = Number(ceiling);
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    const here = markedAt(matrix, total, marked, mid);
    const next = markedAt(matrix, total, marked, mid + 1);
    if (next.cmp(here) > 0) lo = mid + 1;
    else hi = mid;
  }
  const powered = pow2(matrix, lo);
  const [amplitude, other] = apply2(powered.matrix, new Frac(1n), new Frac(1n));
  const invariant = new Frac(marked).mul(amplitude).mul(amplitude).add(new Frac(total - marked).mul(other).mul(other));
  if (invariant.cmp(new Frac(total)) !== 0) throw new Error("doubled Grover left the norm");
  return {
    k: lo,
    probability: new Frac(marked).mul(amplitude).mul(amplitude).div(new Frac(total)),
    multiplies: powered.multiplies,
    ceiling,
  };
}

function lucasByAddition(index: number): { value: bigint; additions: number } {
  if (index === 0) return { value: 2n, additions: 0 };
  if (index === 1) return { value: 1n, additions: 0 };
  let previous = 2n;
  let current = 1n;
  for (let n = 2; n <= index; n++) {
    const next = previous + current;
    previous = current;
    current = next;
  }
  return { value: current, additions: index - 1 };
}

function walkAgrees(total: bigint, marked: bigint, steps: number, expected: Frac): boolean {
  const matrix = stepMatrix(total, marked);
  let amplitude = new Frac(1n);
  let other = new Frac(1n);
  for (let step = 0; step < steps; step++) {
    [amplitude, other] = apply2(matrix, amplitude, other);
  }
  const probability = new Frac(marked).mul(amplitude).mul(amplitude).div(new Frac(total));
  return probability.toString() === expected.toString();
}

let cureCached: string | null = null;

export function cureReport(): string {
  if (cureCached) return cureCached;
  const slowLucas = lucasByAddition(76);
  const fastLucas = lucas(76);
  if (slowLucas.value !== fastLucas) throw new Error("Lucas doubling disagreed with the recurrence");
  const cured = doubledPeak(10000n, 1n);
  if (!walkAgrees(10000n, 1n, cured.k, cured.probability)) throw new Error("the walk and the doubling disagree");
  if (cured.k <= 64) throw new Error("this example does not get past the slow walk cap");
  cureCached = [
    "cure",
    "  slow path = one addition, or one Grover step, at a time",
    "  Lucas cure = doubling",
    "  theorem_proven = False",
    "",
    "[Lucas]",
    `  recurrence to L_76 uses ${slowLucas.additions} additions`,
    "  doubling returns the same integer",
    `  L_76 = ${fastLucas}`,
    "",
    "[Grover]",
    "  N = 10000    M = 1",
    "  a fixed walk of 64 steps does not own this peak",
    `  ceiling = isqrt(N/M) = ${cured.ceiling}`,
    `  doubling multiplications = ${cured.multiplies}`,
    `  k = ${cured.k}`,
    `  P(marked) = ${cured.probability}`,
    "  the walk, run once, returns the same probability",
    "  a sine is not used",
    "  a decimal probability is refused",
  ].join("\n");
  return cureCached;
}
