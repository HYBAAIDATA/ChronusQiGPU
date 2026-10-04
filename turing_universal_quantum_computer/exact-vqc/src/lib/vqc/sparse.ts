/** Sparse exact register over Q(√2)+iQ(√2). Nonzero amplitudes only.

Qubit 0 is the least significant bit of the basis index. A phase outside
this field is not representable here and is not approximated. An operation
that would pass the support bound is refused.
*/

import { Exact, HALF_SQRT2, I, ONE, Q2, ZERO } from "./algebra.ts";

export class SupportExceededError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "SupportExceededError";
  }
}

const INV_SQRT2 = new Exact(HALF_SQRT2, Q2.zero());

export class SparseRegister {
  readonly nQubits: number;
  readonly maxAmplitudes: number;
  amplitudes: Map<bigint, Exact>;

  constructor(nQubits: number, basis = 0n, maxAmplitudes = 1 << 16) {
    if (!Number.isInteger(nQubits) || nQubits < 1) throw new Error("n_qubits must be >= 1");
    if (!Number.isInteger(maxAmplitudes) || maxAmplitudes < 1) throw new Error("max_amplitudes must be >= 1");
    const dim = 1n << BigInt(nQubits);
    if (basis < 0n || basis >= dim) throw new Error("basis index out of range");
    this.nQubits = nQubits;
    this.maxAmplitudes = maxAmplitudes;
    this.amplitudes = new Map([[basis, ONE]]);
  }

  private requireQubit(q: number): void {
    if (!Number.isInteger(q) || q < 0 || q >= this.nQubits) throw new Error(`qubit ${q} outside 0..${this.nQubits - 1}`);
  }

  private checkSupport(extra: number): void {
    if (this.amplitudes.size + extra > this.maxAmplitudes) {
      throw new SupportExceededError(
        `sparse state would exceed ${this.maxAmplitudes} nonzero amplitudes (n_qubits=${this.nQubits}); refused, not truncated`,
      );
    }
  }

  applyH(q: number): void {
    this.requireQubit(q);
    this.checkSupport(this.amplitudes.size);
    const mask = 1n << BigInt(q);
    const seen = new Set<bigint>();
    for (const i of [...this.amplitudes.keys()]) {
      const base = i & ~mask;
      if (seen.has(base)) continue;
      seen.add(base);
      const j = base | mask;
      const a = this.amplitudes.get(base) ?? ZERO;
      const b = this.amplitudes.get(j) ?? ZERO;
      const sum = a.add(b).mul(INV_SQRT2);
      const diff = a.sub(b).mul(INV_SQRT2);
      if (sum.isZero()) this.amplitudes.delete(base);
      else this.amplitudes.set(base, sum);
      if (diff.isZero()) this.amplitudes.delete(j);
      else this.amplitudes.set(j, diff);
    }
  }

  applyX(q: number): void {
    this.requireQubit(q);
    const mask = 1n << BigInt(q);
    const seen = new Set<bigint>();
    const next = new Map<bigint, Exact>();
    for (const i of this.amplitudes.keys()) {
      const base = i & ~mask;
      if (seen.has(base)) continue;
      seen.add(base);
      const j = base | mask;
      const a = this.amplitudes.get(base);
      const b = this.amplitudes.get(j);
      if (b) next.set(base, b);
      if (a) next.set(j, a);
    }
    for (const [i, amp] of this.amplitudes) {
      const base = i & ~mask;
      if (!seen.has(base)) next.set(i, amp);
    }
    this.amplitudes = next;
  }

  applyZ(q: number): void {
    this.requireQubit(q);
    const mask = 1n << BigInt(q);
    for (const [i, amp] of this.amplitudes) {
      if (i & mask) this.amplitudes.set(i, amp.neg());
    }
  }

  applyS(q: number): void {
    this.requireQubit(q);
    const mask = 1n << BigInt(q);
    for (const [i, amp] of this.amplitudes) {
      if (i & mask) this.amplitudes.set(i, amp.mul(I));
    }
  }

  applyT(q: number): void {
    this.requireQubit(q);
    const phase = new Exact(HALF_SQRT2, HALF_SQRT2);
    const mask = 1n << BigInt(q);
    for (const [i, amp] of this.amplitudes) {
      if (i & mask) this.amplitudes.set(i, amp.mul(phase));
    }
  }

  applyCnot(control: number, target: number): void {
    this.requireQubit(control);
    this.requireQubit(target);
    if (control === target) throw new Error("control and target must differ");
    const cm = 1n << BigInt(control);
    const tm = 1n << BigInt(target);
    const seen = new Set<bigint>();
    const next = new Map<bigint, Exact>();
    for (const i of this.amplitudes.keys()) {
      if ((i & cm) === 0n) {
        next.set(i, this.amplitudes.get(i)!);
        continue;
      }
      const base = i & ~tm;
      if (seen.has(base)) continue;
      seen.add(base);
      const j = base | tm;
      const a = this.amplitudes.get(base);
      const b = this.amplitudes.get(j);
      if (b) next.set(base, b);
      if (a) next.set(j, a);
    }
    this.amplitudes = next;
  }

  normSquared(): Q2 {
    let total = Q2.zero();
    for (const amp of this.amplitudes.values()) total = total.add(amp.normSq());
    return total;
  }

  distribution(): Map<bigint, Q2> {
    const out = new Map<bigint, Q2>();
    for (const [i, amp] of this.amplitudes) {
      const p = amp.normSq();
      if (!p.isZero()) out.set(i, p);
    }
    return out;
  }
}

export type CyclePosition = { x: number; probability: Q2 };

export type CycleReport = {
  text: string;
  positions: CyclePosition[];
  mean: Q2;
  variance: Q2;
};

function mod(value: bigint, modulus: bigint): bigint {
  const r = value % modulus;
  return r < 0n ? r + modulus : r;
}

/** Hadamard-coin walk on a cycle. Shift is a permutation of basis states. */
export function coinedCycle(numPositions: number, steps = 3, maxAmplitudes = 1 << 16): CycleReport {
  if (!Number.isInteger(numPositions) || numPositions < 2) throw new Error("cycle needs at least 2 positions");
  if (!Number.isInteger(steps) || steps < 0) throw new Error("steps must be an integer >= 0");
  const reachable = 2 * Math.min(numPositions, steps + 1);
  if (reachable > maxAmplitudes) {
    throw new SupportExceededError(
      `coined cycle support bound ${reachable} exceeds ${maxAmplitudes} amplitudes; refused, not truncated`,
    );
  }
  const posBits = (numPositions - 1).toString(2).length;
  const coin = posBits;
  const center = Math.floor(numPositions / 2);
  const register = new SparseRegister(posBits + 1, 0n, maxAmplitudes);
  register.applyH(coin);
  register.applyS(coin);
  for (let q = 0; q < posBits; q++) {
    if ((center >> q) & 1) register.applyX(q);
  }
  const posMask = (1n << BigInt(posBits)) - 1n;
  const modulus = BigInt(numPositions);
  for (let step = 0; step < steps; step++) {
    register.applyH(coin);
    const next = new Map<bigint, Exact>();
    for (const [idx, amp] of register.amplitudes) {
      const x = idx & posMask;
      const c = (idx >> BigInt(coin)) & 1n;
      const x2 = c === 1n ? mod(x + 1n, modulus) : mod(x - 1n, modulus);
      const moved = x2 | (c << BigInt(coin));
      const prev = next.get(moved);
      const sum = prev ? prev.add(amp) : amp;
      if (sum.isZero()) next.delete(moved);
      else next.set(moved, sum);
    }
    register.amplitudes = next;
  }
  const folded = new Map<number, Q2>();
  for (const [idx, amp] of register.amplitudes) {
    const x = Number(idx & posMask);
    const p = amp.normSq();
    const prev = folded.get(x);
    const sum = prev ? prev.add(p) : p;
    if (!sum.isZero()) folded.set(x, sum);
  }
  const positions = [...folded.entries()]
    .map(([x, probability]) => ({ x, probability }))
    .sort((a, b) => a.x - b.x);
  let total = Q2.zero();
  let mean = Q2.zero();
  const distance = new Map<number, number>();
  for (const { x, probability } of positions) {
    total = total.add(probability);
    const forward = (x - center + numPositions) % numPositions;
    const d = Math.min(forward, (center - x + numPositions) % numPositions);
    distance.set(x, d);
    mean = mean.add(new Q2(d, 0).mul(probability));
  }
  if (!total.eq(Q2.one())) throw new Error(`coined cycle left the unit sphere: ∑ P = ${total}`);
  let variance = Q2.zero();
  for (const { x, probability } of positions) {
    const delta = new Q2(distance.get(x) ?? 0, 0).sub(mean);
    variance = variance.add(probability.mul(delta.mul(delta)));
  }
  const lines = [
    `coined cycle walk   N = ${numPositions}   steps = ${steps}   materialised = True`,
    "  field = Q(√2)+iQ(√2)",
    "  coin = Hadamard    shift = exact basis permutation",
    `  centre = ${center}    nonzero amplitudes = ${register.amplitudes.size}`,
    "  position Born distribution:",
  ];
  for (const { x, probability } of positions) lines.push(`    x = ${x}    ${probability}`);
  lines.push("  ∑ P = 1");
  lines.push(`  E[d] = ${mean}`);
  lines.push(`  Var[d] = ${variance}`);
  lines.push("  d is the toroidal distance from the centre; both moments are exact");
  return { text: lines.join("\n"), positions, mean, variance };
}
