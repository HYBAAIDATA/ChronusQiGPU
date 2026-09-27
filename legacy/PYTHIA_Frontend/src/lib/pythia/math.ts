/** Exact Lucas / Fibonacci / Cassini / Zeckendorf / Grover substrate. */

export const PHI = (1 + Math.sqrt(5)) / 2;
export const INV_PHI = PHI - 1;
export const SQRT5 = Math.sqrt(5);

export const IGPU_SCALE_RUNGS = [10, 12, 15, 18, 20, 31, 50, 76] as const;
export const PISOT_EXACT_N = 76;

export const SCALE_NAMES: Record<number, string> = {
  10: "L₁₀ pattern",
  12: "L₁₂ structure",
  15: "L₁₅ coherence",
  18: "L₁₈ abstraction",
  20: "L₂₀ metacognition",
  31: "L₃₁ hardware",
  50: "L₅₀ projection",
  76: "L₇₆ Pisot collapse",
};

export function gcd(a: bigint, b: bigint): bigint {
  a = a < 0n ? -a : a;
  b = b < 0n ? -b : b;
  while (b !== 0n) {
    const t = a % b;
    a = b;
    b = t;
  }
  return a;
}

export class Fraction {
  n: bigint;
  d: bigint;
  constructor(n: bigint, d: bigint = 1n) {
    if (d === 0n) throw new Error("Division by zero");
    if (d < 0n) {
      n = -n;
      d = -d;
    }
    const g = gcd(n, d);
    this.n = n / g;
    this.d = d / g;
  }
  add(o: Fraction) {
    return new Fraction(this.n * o.d + o.n * this.d, this.d * o.d);
  }
  sub(o: Fraction) {
    return new Fraction(this.n * o.d - o.n * this.d, this.d * o.d);
  }
  mul(o: Fraction) {
    return new Fraction(this.n * o.n, this.d * o.d);
  }
  toString() {
    return this.d === 1n ? this.n.toString() : `${this.n}/${this.d}`;
  }
  toNumber() {
    return Number(this.n) / Number(this.d);
  }
}

/** Fast-doubling Fibonacci. Returns F(n). F(0)=0, F(1)=1. */
export function fibonacci(n: number): bigint {
  if (n < 0) {
    const f = fibonacci(-n);
    return n % 2 === 0 ? -f : f;
  }
  return fibPair(n)[0];
}

function fibPair(n: number): [bigint, bigint] {
  if (n === 0) return [0n, 1n];
  const [a, b] = fibPair(n >> 1);
  const c = a * (2n * b - a);
  const d = a * a + b * b;
  return n & 1 ? [d, c + d] : [c, d];
}

/** L(0)=2, L(1)=1, L(n)=2 F(n+1) − F(n). */
export function lucas(n: number): bigint {
  if (n < 0) {
    const l = lucas(-n);
    return n % 2 === 0 ? l : -l;
  }
  if (n === 0) return 2n;
  const [fn, fn1] = fibPair(n);
  return 2n * fn1 - fn;
}

export function cassiniLeft(n: number): bigint {
  const ln = lucas(n);
  const fn = fibonacci(n);
  return ln * ln - 5n * fn * fn;
}

export function cassiniRight(n: number): bigint {
  return 4n * (n % 2 === 0 ? 1n : -1n);
}

export function cassiniHolds(n: number): boolean {
  return cassiniLeft(n) === cassiniRight(n);
}

export function zeckendorf(n: bigint): number[] {
  if (n <= 0n) return [];
  const fibs: bigint[] = [1n, 2n];
  while (fibs[fibs.length - 1]! <= n) {
    const k = fibs.length;
    fibs.push(fibs[k - 1]! + fibs[k - 2]!);
  }
  const indices: number[] = [];
  let rem = n;
  for (let i = fibs.length - 1; i >= 0; i--) {
    if (fibs[i]! <= rem) {
      indices.push(i + 2);
      rem -= fibs[i]!;
      if (rem === 0n) break;
    }
  }
  return indices;
}

export function zeckendorfMask(indices: number[]): bigint {
  let mask = 0n;
  for (const i of indices) mask |= 1n << BigInt(i);
  return mask;
}

export function zeckendorfNonAdjacent(mask: bigint): boolean {
  return (mask & (mask << 1n)) === 0n;
}

export function isLadderIndex(n: number): boolean {
  return n > 0 && IGPU_SCALE_RUNGS.some((r) => n % r === 0);
}

export type Q5 = { a: Fraction; b: Fraction };

export function q5(a: Fraction, b: Fraction): Q5 {
  return { a, b };
}

export function q5Add(x: Q5, y: Q5): Q5 {
  return { a: x.a.add(y.a), b: x.b.add(y.b) };
}

export function q5Mul(x: Q5, y: Q5): Q5 {
  return {
    a: x.a.mul(y.a).add(x.b.mul(y.b).mul(new Fraction(5n))),
    b: x.a.mul(y.b).add(x.b.mul(y.a)),
  };
}

export function q5Norm(x: Q5): Fraction {
  return x.a.mul(x.a).sub(x.b.mul(x.b).mul(new Fraction(5n)));
}

export function q5ToString(x: Q5): string {
  const b = x.b.toString();
  const sign = x.b.n < 0n ? " − " : " + ";
  const absB = x.b.n < 0n ? new Fraction(-x.b.n, x.b.d).toString() : b;
  return `${x.a.toString()}${sign}${absB}√5`;
}

export type Amplitude = { re: number; im: number };

export function groverMarked11(): {
  steps: { label: string; state: Amplitude[] }[];
  peak: number;
  peakIndex: number;
} {
  const h = 0.5;
  const steps = [
    { label: "|ψ₀⟩ = |00⟩", state: amp(1, 0, 0, 0) },
    { label: "H⊗H superposition", state: amp(h, h, h, h) },
    { label: "Oracle R_w on |11⟩", state: amp(h, h, h, -h) },
    { label: "Diffusion D", state: amp(0, 0, 0, 1) },
  ];
  return { steps, peak: 1, peakIndex: 3 };
}

function amp(a: number, b: number, c: number, d: number): Amplitude[] {
  return [a, b, c, d].map((re) => ({ re, im: 0 }));
}

export function born(state: Amplitude[]): number[] {
  return state.map((s) => s.re * s.re + s.im * s.im);
}

export function bornSum(state: Amplitude[]): number {
  return born(state).reduce((a, b) => a + b, 0);
}

export function formatBig(n: bigint): string {
  if (n === 0n) return "0";
  const sign = n < 0n ? "-" : "";
  const s = (n < 0n ? -n : n).toString();
  if (s.length <= 6) return sign + s;
  const exp = s.length - 1;
  const frac = s.slice(1, 4).replace(/0+$/, "");
  const head = frac ? `${s[0]}.${frac}` : s[0]!;
  return `${sign}${head}×10${expToSup(exp)}`;
}

function expToSup(n: number): string {
  const map: Record<string, string> = {
    "0": "⁰",
    "1": "¹",
    "2": "²",
    "3": "³",
    "4": "⁴",
    "5": "⁵",
    "6": "⁶",
    "7": "⁷",
    "8": "⁸",
    "9": "⁹",
    "-": "⁻",
  };
  return String(n)
    .split("")
    .map((c) => map[c] ?? c)
    .join("");
}

export function formatHps(hps: number): string {
  if (!Number.isFinite(hps) || hps <= 0) return "0 H/s";
  const units = ["H/s", "kH/s", "MH/s", "GH/s", "TH/s", "PH/s", "EH/s", "ZH/s"];
  let v = hps;
  let i = 0;
  while (v >= 1000 && i < units.length - 1) {
    v /= 1000;
    i++;
  }
  const digits = v >= 100 ? 0 : v >= 10 ? 1 : 2;
  return `${v.toFixed(digits)} ${units[i]}`;
}
