/** Algorithms of the greats, executed only where the value stays exact.

Deutsch, Deutsch–Jozsa, Bernstein–Vazirani and Simon are Clifford, so their
amplitudes stay in Q(√2)+iQ(√2). The QFT is exact through dimension 8,
because that is Q(ζ₈). Shor's factoring of 15 uses that QFT. Grover's
two-dimensional iterate is an exact rational recurrence. A float angle,
a float iteration count, and any QFT past dimension 8 are refused.
*/

import { Exact, Frac, HALF_SQRT2, I, ONE, Q2, ZERO } from "./algebra.ts";
import { ExactStatevector } from "./exact-state.ts";

const Z8 = new Exact(HALF_SQRT2, HALF_SQRT2);

function modPow(base: bigint, exp: bigint, modulus: bigint): bigint {
  let result = 1n;
  let factor = base % modulus;
  let left = exp;
  while (left > 0n) {
    if (left & 1n) result = (result * factor) % modulus;
    factor = (factor * factor) % modulus;
    left >>= 1n;
  }
  return result;
}

function gcd(a: bigint, b: bigint): bigint {
  let x = a < 0n ? -a : a;
  let y = b < 0n ? -b : b;
  while (y) {
    const next = x % y;
    x = y;
    y = next;
  }
  return x;
}

function rational(value: Q2): string {
  if (!value.q.isZero()) throw new Error(`probability left the rationals: ${value}`);
  return value.p.toString();
}

function bitProbability(state: ExactStatevector, qubit: number, on: boolean): Q2 {
  let total = Q2.zero();
  state.amplitudes.forEach((amplitude, index) => {
    if (((index & (1 << qubit)) !== 0) === on) total = total.add(amplitude.normSq());
  });
  return total;
}

function rootOfUnity(nQubits: number): Exact {
  if (nQubits === 1) return new Exact(-1);
  if (nQubits === 2) return I;
  if (nQubits === 3) return Z8;
  throw new Error("QFT past dimension 8 is outside Q(ζ₈)");
}

function qftScale(nQubits: number): Exact {
  if (nQubits === 1) return new Exact(new Q2(0, new Frac(1n, 2n)));
  if (nQubits === 2) return new Exact(new Q2(new Frac(1n, 2n)));
  return new Exact(new Q2(0, new Frac(1n, 4n)));
}

function qft(input: Exact[], nQubits: number): Exact[] {
  const dimension = 1 << nQubits;
  if (input.length !== dimension) throw new Error("QFT input has the wrong dimension");
  const root = rootOfUnity(nQubits);
  const powers = [ONE];
  for (let i = 1; i < dimension; i++) powers.push(powers[i - 1].mul(root));
  const scale = qftScale(nQubits);
  return Array.from({ length: dimension }, (_, j) => {
    let sum = ZERO;
    for (let k = 0; k < dimension; k++) {
      if (input[k].isZero()) continue;
      sum = sum.add(input[k].mul(powers[(j * k) % dimension]));
    }
    return sum.mul(scale);
  });
}

function deutsch(): string[] {
  const run = (balanced: boolean) => {
    const state = new ExactStatevector(2);
    state.apply("x", 1).apply("h", 0).apply("h", 1);
    if (balanced) state.applyControlled("x", 0, 1);
    state.apply("h", 0);
    return rational(bitProbability(state, 0, true));
  };
  const constant = run(false);
  const balanced = run(true);
  if (constant !== "0" || balanced !== "1") throw new Error("Deutsch readout changed");
  return [
    "[Deutsch 1985]",
    "  constant f  →  P(q0 = 1) = 0",
    "  balanced f  →  P(q0 = 1) = 1",
  ];
}

function deutschJozsa(): string[] {
  const run = (balanced: boolean) => {
    const state = new ExactStatevector(3);
    state.apply("x", 2);
    for (let q = 0; q < 3; q++) state.apply("h", q);
    if (balanced) state.applyControlled("x", 0, 2);
    state.apply("h", 0).apply("h", 1);
    const zero = state.amplitudes[0].normSq().add(state.amplitudes[4].normSq());
    return rational(zero);
  };
  const constant = run(false);
  const balanced = run(true);
  if (constant !== "1" || balanced !== "0") throw new Error("Deutsch–Jozsa readout changed");
  return [
    "[Deutsch–Jozsa 1992]",
    "  constant f on 2 bits  →  P(00) = 1",
    "  balanced f = x0       →  P(00) = 0",
  ];
}

function bernsteinVazirani(): string[] {
  const secret = 0b101;
  const state = new ExactStatevector(4);
  state.apply("x", 3).apply("h", 3);
  for (let q = 0; q < 3; q++) state.apply("h", q);
  for (let q = 0; q < 3; q++) if ((secret & (1 << q)) !== 0) state.applyControlled("x", q, 3);
  for (let q = 0; q < 3; q++) state.apply("h", q);
  let hit = Q2.zero();
  state.amplitudes.forEach((amplitude, index) => {
    if ((index & 0b111) === secret) hit = hit.add(amplitude.normSq());
  });
  const text = rational(hit);
  if (text !== "1") throw new Error("Bernstein–Vazirani did not return the secret");
  return ["[Bernstein–Vazirani 1993]", "  secret s = 101", "  P(readout = 101) = 1"];
}

function simon(): string[] {
  const state = new ExactStatevector(4);
  state.apply("h", 0).apply("h", 1);
  state.applyControlled("x", 0, 2).applyControlled("x", 1, 2);
  state.apply("h", 0).apply("h", 1);
  const mass = new Map<number, Q2>();
  state.amplitudes.forEach((amplitude, index) => {
    const y = index & 0b11;
    mass.set(y, (mass.get(y) ?? Q2.zero()).add(amplitude.normSq()));
  });
  const lines = ["[Simon 1994]", "  hidden s = 11", "  f(x) = x0 ⊕ x1"];
  for (const y of [0, 1, 2, 3]) {
    const probability = mass.get(y) ?? Q2.zero();
    const dot = ((y & 1) ^ (y >> 1)) & 1;
    if (!probability.isZero() && dot !== 0) throw new Error("Simon returned a string outside s-perpendicular");
    lines.push(`  P(${y.toString(2).padStart(2, "0")}) = ${rational(probability)}    y·s = ${dot}`);
  }
  return lines;
}

function qftSection(nQubits = 3): string[] {
  if (!Number.isInteger(nQubits) || nQubits < 1) return ["REFUSED: QFT width must be a positive integer"];
  if (nQubits > 3) return [`REFUSED: QFT on ${nQubits} qubits leaves Q(ζ₈). It is not evaluated as a decimal.`];
  const dimension = 1 << nQubits;
  const input = Array.from({ length: dimension }, () => ZERO);
  if (nQubits < 3) {
    input[1] = ONE;
    const output = qft(input, nQubits);
    const flat = output.every((amplitude) => amplitude.normSq().eq(qftScale(nQubits).normSq()));
    if (!flat) throw new Error("QFT of a basis state is not flat");
    return [
      `[QFT]  n = ${nQubits}    dimension = ${dimension}`,
      `  QFT|1⟩ is flat    each P = ${rational(output[0].normSq())}`,
    ];
  }
  const half = new Exact(new Q2(new Frac(1n, 2n)));
  for (const index of [0, 2, 4, 6]) input[index] = half;
  const output = qft(input, 3);
  const lines = ["[QFT]  n = 3    dimension = 8    field = Q(ζ₈)", "  input (|0⟩+|2⟩+|4⟩+|6⟩)/2"];
  for (let j = 0; j < 8; j++) {
    const probability = output[j].normSq();
    if (!probability.isZero()) lines.push(`  P(${j}) = ${rational(probability)}    amplitude = ${output[j]}`);
  }
  if (rational(output[0].normSq()) !== "1/2" || rational(output[4].normSq()) !== "1/2") {
    throw new Error("the period-2 QFT did not peak at 0 and 4");
  }
  return lines;
}

function groverStep(total: bigint, marked: bigint, markedAmp: Frac, otherAmp: Frac): { markedAmp: Frac; otherAmp: Frac } {
  const flipped = markedAmp.neg();
  const mix = new Frac(marked).mul(flipped).add(new Frac(total - marked).mul(otherAmp));
  const shift = new Frac(2n).mul(mix).div(new Frac(total));
  return { markedAmp: shift.sub(flipped), otherAmp: shift.sub(otherAmp) };
}

function markedProbability(total: bigint, marked: bigint, markedAmp: Frac): Frac {
  return new Frac(marked).mul(markedAmp).mul(markedAmp).div(new Frac(total));
}

function groverFold(total: bigint, marked: bigint, cap = 64): { k: number; probability: Frac; reached: boolean } {
  if (total < 2n || marked < 1n || marked >= total) throw new Error("Grover needs 0 < M < N and N >= 2");
  let markedAmp = new Frac(1n);
  let otherAmp = new Frac(1n);
  let probability = markedProbability(total, marked, markedAmp);
  let bestK = 0;
  let best = probability;
  for (let k = 1; k <= cap; k++) {
    const next = groverStep(total, marked, markedAmp, otherAmp);
    const invariant = new Frac(marked).mul(next.markedAmp).mul(next.markedAmp).add(new Frac(total - marked).mul(next.otherAmp).mul(next.otherAmp));
    if (invariant.cmp(new Frac(total)) !== 0) throw new Error("Grover norm left N");
    const nextProbability = markedProbability(total, marked, next.markedAmp);
    if (nextProbability.cmp(probability) < 0) return { k: bestK, probability: best, reached: true };
    markedAmp = next.markedAmp;
    otherAmp = next.otherAmp;
    probability = nextProbability;
    best = probability;
    bestK = k;
    if (probability.cmp(new Frac(1n)) === 0) return { k, probability, reached: true };
  }
  return { k: cap, probability: best, reached: false };
}

function groverCircuitAgrees(): boolean {
  const state = new ExactStatevector(2);
  state.apply("h", 0).apply("h", 1);
  state.applyControlled("z", 0, 1);
  state.apply("h", 0).apply("h", 1);
  state.apply("x", 0).apply("x", 1);
  state.applyControlled("z", 0, 1);
  state.apply("x", 0).apply("x", 1);
  state.apply("h", 0).apply("h", 1);
  return state.amplitudes[3].normSq().eq(Q2.one()) && state.amplitudes.every((amplitude, index) => index === 3 || amplitude.isZero());
}

function groverSection(total?: bigint, marked?: bigint): string[] {
  if (total === undefined || marked === undefined) {
    const four = groverFold(4n, 1n);
    const eight = groverFold(8n, 1n);
    if (four.probability.toString() !== "1" || !groverCircuitAgrees()) throw new Error("exact Grover on 4 states failed");
    return [
      "[Grover 1996]",
      "  folded iterate over the rationals    a = A/√N, b = B/√N",
      `  N = 4  M = 1  k = ${four.k}  P(marked) = ${four.probability}`,
      "  two-qubit circuit agrees    P(|11⟩) = 1",
      `  N = 8  M = 1  k = ${eight.k}  P(marked) = ${eight.probability}`,
      "  floor(π √N / 4) is refused    it is not an exact iteration count",
    ];
  }
  const run = groverFold(total, marked);
  return [
    "[Grover 1996]",
    `  N = ${total}  M = ${marked}  k = ${run.k}  P(marked) = ${run.probability}`,
    run.reached ? "  peak reached by the exact recurrence" : "  REFUSED: the peak is beyond the exact iteration cap. A float estimate is not substituted.",
  ];
}

function shor15(): string[] {
  const dimension = 8;
  const root = rootOfUnity(3);
  const powers = [ONE];
  for (let i = 1; i < dimension; i++) powers.push(powers[i - 1].mul(root));
  const eighth = new Exact(new Q2(new Frac(1n, 8n)));
  const groups = new Map<bigint, number[]>();
  for (let k = 0; k < dimension; k++) {
    const image = modPow(7n, BigInt(k), 15n);
    const list = groups.get(image) ?? [];
    list.push(k);
    groups.set(image, list);
  }
  const lines = ["[Shor 1994]", "  N = 15    a = 7    phase register = 3 qubits    field = Q(ζ₈)"];
  const peaks: number[] = [];
  for (let j = 0; j < dimension; j++) {
    let probability = new Frac(0n);
    for (const indices of groups.values()) {
      let sum = ZERO;
      for (const k of indices) sum = sum.add(powers[(j * k) % dimension]);
      probability = probability.add(new Frac(sum.mul(eighth).normSq().p.n, sum.mul(eighth).normSq().p.d));
      if (!sum.mul(eighth).normSq().q.isZero()) throw new Error("Shor amplitude left Q(ζ₈) in its probability");
    }
    lines.push(`  P(phase = ${j}) = ${probability}`);
    if (!probability.isZero()) peaks.push(j);
  }
  const orders = new Set<bigint>();
  for (const j of peaks) {
    if (j === 0) continue;
    const denominator = new Frac(BigInt(j), 8n).d;
    if (modPow(7n, denominator, 15n) === 1n) orders.add(denominator);
  }
  if (!orders.has(4n)) throw new Error("continued-fraction denominators did not recover the order");
  const square = modPow(7n, 2n, 15n);
  const factor = gcd(square - 1n, 15n);
  const cofactor = gcd(square + 1n, 15n);
  if (factor * cofactor !== 15n) throw new Error("Shor did not factor 15");
  lines.push("  measured fractions j/8 have a convergent denominator 4");
  lines.push("  order of 7 modulo 15 = 4");
  lines.push(`  gcd(7^2 − 1, 15) = ${factor}`);
  lines.push(`  gcd(7^2 + 1, 15) = ${cofactor}`);
  lines.push(`  15 = ${factor} × ${cofactor}`);
  return lines;
}

function shorOther(value: bigint): string[] {
  return [
    "[Shor 1994]",
    `  REFUSED: factoring ${value} by a quantum period register needs a root of unity outside Q(ζ₈).`,
    "  The integer is not factored by a classical search and reported as Shor.",
  ];
}

let cached: string | null = null;

export function classicsReport(): string {
  if (cached) return cached;
  const lines = [
    "algorithms of the greats    exact where the field allows    theorem_proven = False",
    "",
    ...deutsch(),
    "",
    ...deutschJozsa(),
    "",
    ...bernsteinVazirani(),
    "",
    ...simon(),
    "",
    ...qftSection(3),
    "",
    ...groverSection(),
    "",
    ...shor15(),
    "",
    ...shorOther(21n),
    "",
    "[refused]",
    "  a QFT past dimension 8",
    "  a decimal Grover angle",
    "  a classical factorisation reported as Shor",
  ];
  cached = lines.join("\n");
  return cached;
}

export function qftReport(nQubits: number): string {
  return qftSection(nQubits).join("\n");
}

export function groverReport(total: bigint, marked: bigint): string {
  return groverSection(total, marked).join("\n");
}

export function shorReport(value: bigint): string {
  if (value === 15n) return shor15().join("\n");
  return shorOther(value).join("\n");
}
