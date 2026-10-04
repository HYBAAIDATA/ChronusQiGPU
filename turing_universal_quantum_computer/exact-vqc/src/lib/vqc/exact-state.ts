/** Exact Clifford+T statevector. Port of backends/reference.py. */

import { Exact, HALF_SQRT2, I, ONE, Q2, ZERO, Frac } from "./algebra.ts";

export class StatevectorTooLargeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "StatevectorTooLargeError";
  }
}

export class DomainError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "DomainError";
  }
}

export const DEFAULT_MAX_AMPLITUDES = 1 << 16;

const H = new Exact(HALF_SQRT2, 0);
type Gate2 = [Exact, Exact, Exact, Exact];

const GATES: Record<string, Gate2> = {
  i: [ONE, ZERO, ZERO, ONE],
  x: [ZERO, ONE, ONE, ZERO],
  y: [ZERO, new Exact(Q2.zero(), new Q2(-1, 0)), I, ZERO],
  z: [ONE, ZERO, ZERO, new Exact(new Q2(-1, 0), 0)],
  h: [H, H, H, H.neg()],
  s: [ONE, ZERO, ZERO, I],
  sdg: [ONE, ZERO, ZERO, I.neg()],
  t: [ONE, ZERO, ZERO, new Exact(HALF_SQRT2, HALF_SQRT2)],
  tdg: [ONE, ZERO, ZERO, new Exact(HALF_SQRT2, HALF_SQRT2.neg())],
};

export const GATE_NAMES = Object.keys(GATES);

export class ExactStatevector {
  readonly nQubits: number;
  readonly amplitudes: Exact[];

  constructor(nQubits: number, amplitudes?: Exact[], maxAmplitudes = DEFAULT_MAX_AMPLITUDES) {
    if (!Number.isInteger(nQubits) || nQubits < 1) throw new DomainError("n_qubits must be a positive integer");
    const dimension = 1 << nQubits;
    if (dimension > maxAmplitudes) {
      throw new StatevectorTooLargeError(
        `refused: ${nQubits} qubits needs ${dimension} exact amplitudes, exceeding the materialisation budget of ${maxAmplitudes}`,
      );
    }
    this.nQubits = nQubits;
    if (!amplitudes) {
      this.amplitudes = Array.from({ length: dimension }, () => ZERO);
      this.amplitudes[0] = ONE;
      return;
    }
    if (amplitudes.length !== dimension) throw new DomainError("amplitude count does not match 2**n");
    this.amplitudes = amplitudes;
  }

  private validate(q: number): void {
    if (!Number.isInteger(q) || q < 0 || q >= this.nQubits) throw new DomainError(`qubit index ${q} outside 0..${this.nQubits - 1}`);
  }

  apply(gate: string, target: number): this {
    this.validate(target);
    const matrix = GATES[gate];
    if (!matrix) throw new DomainError(`unknown gate ${gate}`);
    const [m00, m01, m10, m11] = matrix;
    const bit = 1 << target;
    const amps = this.amplitudes;
    for (let lo = 0; lo < amps.length; lo++) {
      if (lo & bit) continue;
      const hi = lo | bit;
      const aLo = amps[lo];
      const aHi = amps[hi];
      amps[lo] = m00.mul(aLo).add(m01.mul(aHi));
      amps[hi] = m10.mul(aLo).add(m11.mul(aHi));
    }
    return this;
  }

  applyControlled(gate: string, control: number, target: number): this {
    this.validate(control);
    this.validate(target);
    if (control === target) throw new DomainError("control and target must differ");
    const matrix = GATES[gate];
    if (!matrix) throw new DomainError(`unknown gate ${gate}`);
    const [m00, m01, m10, m11] = matrix;
    const cBit = 1 << control;
    const tBit = 1 << target;
    const amps = this.amplitudes;
    for (let lo = 0; lo < amps.length; lo++) {
      if (!(lo & cBit) || lo & tBit) continue;
      const hi = lo | tBit;
      const aLo = amps[lo];
      const aHi = amps[hi];
      amps[lo] = m00.mul(aLo).add(m01.mul(aHi));
      amps[hi] = m10.mul(aLo).add(m11.mul(aHi));
    }
    return this;
  }

  swap(a: number, b: number): this {
    this.validate(a);
    this.validate(b);
    if (a === b) return this;
    const aBit = 1 << a;
    const bBit = 1 << b;
    const amps = this.amplitudes;
    for (let lo = 0; lo < amps.length; lo++) {
      if (lo & aBit || !(lo & bBit)) continue;
      const hi = lo ^ (aBit | bBit);
      const tmp = amps[lo];
      amps[lo] = amps[hi];
      amps[hi] = tmp;
    }
    return this;
  }

  normSq(): Q2 {
    let total = Q2.zero();
    for (const amplitude of this.amplitudes) total = total.add(amplitude.normSq());
    return total;
  }

  isNormalised(): boolean {
    return this.normSq().eq(Q2.one());
  }

  probabilities(): Q2[] {
    const total = this.normSq();
    if (total.isZero()) throw new DomainError("the null state has no Born distribution");
    return this.amplitudes.map((amplitude) => amplitude.normSq().div(total));
  }

  support(): number[] {
    const out: number[] = [];
    this.amplitudes.forEach((amplitude, index) => {
      if (!amplitude.isZero()) out.push(index);
    });
    return out;
  }

  bitstring(index: number): string {
    return index.toString(2).padStart(this.nQubits, "0").split("").reverse().join("");
  }

  dirac(maxTerms = 8): string {
    const terms: string[] = [];
    for (const index of this.support()) {
      if (terms.length >= maxTerms) {
        terms.push("…");
        break;
      }
      terms.push(`(${this.amplitudes[index]})|${this.bitstring(index)}⟩`);
    }
    return terms.length ? terms.join(" + ") : "0";
  }

  marginalProbabilities(qubits: number[]): Map<string, Q2> {
    const subset = [...new Set(qubits)].sort((a, b) => a - b);
    for (const q of subset) this.validate(q);
    const probabilities = this.probabilities();
    const marginal = new Map<string, Q2>();
    for (let index = 0; index < probabilities.length; index++) {
      const key = subset.map((q) => ((index >> q) & 1).toString()).join("");
      const prev = marginal.get(key) ?? Q2.zero();
      marginal.set(key, prev.add(probabilities[index]));
    }
    return marginal;
  }

  entropyBits(qubits: number[]): number {
    let entropy = 0;
    for (const probability of this.marginalProbabilities(qubits).values()) {
      const value = probability.approx();
      if (value > 0) entropy -= value * Math.log2(value);
    }
    return entropy;
  }

  isProductState(qubits: number[]): boolean {
    const subset = [...new Set(qubits)].sort((a, b) => a - b);
    if (subset.length < 2) return true;
    const marginal = this.marginalProbabilities(subset);
    const singles = new Map(subset.map((q) => [q, this.marginalProbabilities([q])]));
    for (const [key, probability] of marginal) {
      let expected = Q2.one();
      subset.forEach((q, position) => {
        expected = expected.mul(singles.get(q)!.get(key[position]) ?? Q2.zero());
      });
      if (!probability.sub(expected).isZero()) return false;
    }
    return true;
  }

  sampleMarginal(shots: number, qubits: number[], seed: number | null): Map<string, number> {
    return sampleMarginalExact(this, shots, qubits, seed);
  }
}

function fracOf(n: bigint, d: bigint): Frac {
  return new Frac(n, d);
}

export function sampleMarginalExact(state: ExactStatevector, shots: number, qubits: number[], seed: number | null): Map<string, number> {
  if (shots < 1) throw new DomainError("shots must be >= 1");
  const marginal = state.marginalProbabilities(qubits);
  const keys = [...marginal.keys()].sort();
  const cumulative: Q2[] = [];
  let running = Q2.zero();
  for (const key of keys) {
    running = running.add(marginal.get(key)!);
    cumulative.push(running);
  }
  const rng = mulberry(seed ?? 0);
  const counts = new Map<string, number>();
  const resolution = 1n << 32n;
  for (let s = 0; s < shots; s++) {
    const drawQ = new Q2(fracOf(BigInt(rng.uint32()), resolution), 0);
    let chosen = keys[keys.length - 1];
    for (let index = 0; index < cumulative.length; index++) {
      if (cumulative[index].sub(drawQ).sign() > 0) {
        chosen = keys[index];
        break;
      }
    }
    counts.set(chosen, (counts.get(chosen) ?? 0) + 1);
  }
  return counts;
}

export function mulberry(seed: number): { uint32: () => number } {
  let a = seed >>> 0;
  return {
    uint32() {
      a |= 0;
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return (t ^ (t >>> 14)) >>> 0;
    },
  };
}

export function reducedBloch(state: ExactStatevector, qubit: number): { x: Exact; y: Exact; z: Exact; purity: Exact } {
  if (!Number.isInteger(qubit) || qubit < 0 || qubit >= state.nQubits) {
    throw new DomainError(`qubit index ${qubit} outside 0..${state.nQubits - 1}`);
  }
  const bit = 1 << qubit;
  let rho00 = ZERO;
  let rho11 = ZERO;
  let rho01 = ZERO;
  let rho10 = ZERO;
  state.amplitudes.forEach((amplitude, index) => {
    if (index & bit) {
      rho11 = rho11.add(amplitude.mul(amplitude.conjugate()));
      return;
    }
    rho00 = rho00.add(amplitude.mul(amplitude.conjugate()));
    const mate = state.amplitudes[index | bit];
    rho01 = rho01.add(amplitude.mul(mate.conjugate()));
    rho10 = rho10.add(mate.mul(amplitude.conjugate()));
  });
  const x = rho01.add(rho10);
  const y = new Exact(rho10.im, rho10.re.neg()).add(new Exact(rho01.im.neg(), rho01.re));
  const z = rho00.sub(rho11);
  const purity = rho00.mul(rho00).add(rho01.mul(rho10)).add(rho10.mul(rho01)).add(rho11.mul(rho11));
  return { x, y, z, purity };
}
