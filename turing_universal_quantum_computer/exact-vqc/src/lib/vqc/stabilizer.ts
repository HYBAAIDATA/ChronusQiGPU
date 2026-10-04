/**
 * Exact CHP stabilizer tableau.
 * Port of `turing_universal_quantum_computer/stabilizer.py` (bitmasks as bigint,
 * so n = 10_000 stays exact).
 */

export class StabilizerDomainError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "StabilizerDomainError";
  }
}

function popcount(x: bigint): number {
  let c = 0;
  let v = x;
  while (v) {
    let limb = Number(v & 0xffffffffn);
    limb = limb - ((limb >>> 1) & 0x55555555);
    limb = (limb & 0x33333333) + ((limb >>> 2) & 0x33333333);
    limb = (limb + (limb >>> 4)) & 0x0f0f0f0f;
    c += (limb * 0x01010101) >>> 24;
    v >>= 32n;
  }
  return c;
}

function gsum(x1: bigint, z1: bigint, x2: bigint, z2: bigint): number {
  const iy = x1 & z1;
  const ix = x1 & ~z1;
  const iz = ~x1 & z1;
  return (
    popcount(z2 & iy) -
    popcount(x2 & iy) +
    (popcount(ix & x2 & z2) - popcount(ix & ~x2 & z2)) +
    (popcount(iz & x2 & ~z2) - popcount(iz & x2 & z2))
  );
}

export class StabilizerState {
  readonly n: number;
  private _x: bigint[];
  private _z: bigint[];
  private _r: number[];

  constructor(nQubits: number) {
    if (!Number.isInteger(nQubits) || nQubits < 1) throw new Error("n_qubits must be >= 1");
    this.n = nQubits;
    const rows = 2 * nQubits;
    this._x = new Array(rows).fill(0n);
    this._z = new Array(rows).fill(0n);
    this._r = new Array(rows).fill(0);
    for (let i = 0; i < nQubits; i++) {
      const bit = 1n << BigInt(i);
      this._x[i] = bit;
      this._z[nQubits + i] = bit;
    }
  }

  clone(): StabilizerState {
    const s = Object.create(StabilizerState.prototype) as StabilizerState;
    Object.assign(s, { n: this.n, _x: this._x.slice(), _z: this._z.slice(), _r: this._r.slice() });
    return s;
  }

  private qubit(q: number): void {
    if (!Number.isInteger(q) || q < 0 || q >= this.n) throw new RangeError(`qubit ${q} out of range [0,${this.n})`);
  }

  private rowsum(h: number, i: number): void {
    const g = gsum(this._x[i], this._z[i], this._x[h], this._z[h]);
    const p = 2 * this._r[i] + 2 * this._r[h] + g;
    const mod = ((p % 4) + 4) % 4;
    if (mod === 0) this._r[h] = 0;
    else if (mod === 2) this._r[h] = 1;
    else throw new StabilizerDomainError("rowsum produced an imaginary Pauli product");
    this._x[h] ^= this._x[i];
    this._z[h] ^= this._z[i];
  }

  h(q: number): this {
    this.qubit(q);
    const bit = 1n << BigInt(q);
    for (let i = 0; i < 2 * this.n; i++) {
      const xb = Number((this._x[i] >> BigInt(q)) & 1n);
      const zb = Number((this._z[i] >> BigInt(q)) & 1n);
      this._r[i] ^= xb & zb;
      const m = (this._x[i] ^ this._z[i]) & bit;
      this._x[i] ^= m;
      this._z[i] ^= m;
    }
    return this;
  }

  s(q: number): this {
    this.qubit(q);
    const bit = 1n << BigInt(q);
    for (let i = 0; i < 2 * this.n; i++) {
      const xb = Number((this._x[i] >> BigInt(q)) & 1n);
      const zb = Number((this._z[i] >> BigInt(q)) & 1n);
      this._r[i] ^= xb & zb;
      this._z[i] ^= this._x[i] & bit;
    }
    return this;
  }

  sdg(q: number): this {
    this.qubit(q);
    const bit = 1n << BigInt(q);
    for (let i = 0; i < 2 * this.n; i++) {
      const xb = Number((this._x[i] >> BigInt(q)) & 1n);
      const zb = Number((this._z[i] >> BigInt(q)) & 1n);
      this._r[i] ^= xb & (zb ^ 1);
      this._z[i] ^= this._x[i] & bit;
    }
    return this;
  }

  x(q: number): this {
    this.qubit(q);
    for (let i = 0; i < 2 * this.n; i++) this._r[i] ^= Number((this._z[i] >> BigInt(q)) & 1n);
    return this;
  }

  y(q: number): this {
    this.qubit(q);
    for (let i = 0; i < 2 * this.n; i++) {
      this._r[i] ^= Number((this._x[i] >> BigInt(q)) & 1n) ^ Number((this._z[i] >> BigInt(q)) & 1n);
    }
    return this;
  }

  z(q: number): this {
    this.qubit(q);
    for (let i = 0; i < 2 * this.n; i++) this._r[i] ^= Number((this._x[i] >> BigInt(q)) & 1n);
    return this;
  }

  cnot(c: number, t: number): this {
    this.qubit(c);
    this.qubit(t);
    if (c === t) throw new Error("CNOT requires distinct qubits");
    const cm = 1n << BigInt(c);
    const tm = 1n << BigInt(t);
    for (let i = 0; i < 2 * this.n; i++) {
      const xc = (this._x[i] & cm) !== 0n;
      const zt = (this._z[i] & tm) !== 0n;
      const xt = (this._x[i] & tm) !== 0n;
      const zc = (this._z[i] & cm) !== 0n;
      const phase = xc && zt && (Number(xt) ^ Number(zc) ^ 1) ? 1 : 0;
      this._r[i] ^= phase;
      if (xc) this._x[i] ^= tm;
      if (zt) this._z[i] ^= cm;
    }
    return this;
  }

  cz(a: number, b: number): this {
    return this.h(b).cnot(a, b).h(b);
  }

  swap(a: number, b: number): this {
    return this.cnot(a, b).cnot(b, a).cnot(a, b);
  }

  measurementProbabilities(q: number): [FracLike, FracLike] {
    this.qubit(q);
    for (let p = this.n; p < 2 * this.n; p++) {
      if ((this._x[p] >> BigInt(q)) & 1n) return [half, half];
    }
    const bit = this.deterministicOutcome(q);
    return bit ? [zeroF, oneF] : [oneF, zeroF];
  }

  expectationZ(q: number): string {
    const [p0, p1] = this.measurementProbabilities(q);
    if (p0.n === 1n && p0.d === 2n) return "0";
    if (p0.n === 1n && p1.n === 0n) return "1";
    return "-1";
  }

  measure(q: number, outcome: 0 | 1): { outcome: 0 | 1; random: boolean } {
    this.qubit(q);
    const [p0, p1] = this.measurementProbabilities(q);
    const random = p0.n === p1.n && p0.d === p1.d;
    let anticommuting: number | null = null;
    for (let p = this.n; p < 2 * this.n; p++) {
      if ((this._x[p] >> BigInt(q)) & 1n) {
        anticommuting = p;
        break;
      }
    }
    if (anticommuting !== null) {
      const p = anticommuting;
      for (let i = 0; i < 2 * this.n; i++) {
        if (i !== p && (this._x[i] >> BigInt(q)) & 1n) this.rowsum(i, p);
      }
      this._x[p - this.n] = this._x[p];
      this._z[p - this.n] = this._z[p];
      this._r[p - this.n] = this._r[p];
      this._x[p] = 0n;
      this._z[p] = 1n << BigInt(q);
      this._r[p] = outcome;
      return { outcome, random };
    }
    const actual = this.deterministicOutcome(q) as 0 | 1;
    if (outcome !== actual) {
      throw new Error(`deterministic measurement outcome is ${actual}; cannot force ${outcome}`);
    }
    return { outcome: actual, random: false };
  }

  private deterministicOutcome(q: number): number {
    let sx = 0n;
    let sz = 0n;
    let sr = 0;
    for (let i = 0; i < this.n; i++) {
      if ((this._x[i] >> BigInt(q)) & 1n) {
        const g = gsum(this._x[this.n + i], this._z[this.n + i], sx, sz);
        const p = 2 * this._r[this.n + i] + 2 * sr + g;
        const mod = ((p % 4) + 4) % 4;
        if (mod !== 0 && mod !== 2) throw new StabilizerDomainError("deterministic measurement produced imaginary phase");
        sr = mod === 2 ? 1 : 0;
        sx ^= this._x[this.n + i];
        sz ^= this._z[this.n + i];
      }
    }
    return sr;
  }

  /** S(A) = |A| − (n − rank of stabilizers restricted to the complement). */
  entanglementEntropy(subset: Iterable<number>): number {
    const A = new Set<number>();
    for (const q of subset) {
      this.qubit(q);
      A.add(q);
    }
    if (A.size === 0 || A.size === this.n) throw new Error("subset must be a proper nonempty subset");
    const rows: bigint[] = [];
    const shift = BigInt(this.n);
    for (let i = this.n; i < 2 * this.n; i++) {
      let xb = this._x[i];
      let zb = this._z[i];
      for (const q of A) {
        const bit = 1n << BigInt(q);
        xb &= ~bit;
        zb &= ~bit;
      }
      rows.push(xb | (zb << shift));
    }
    const rankB = gf2Rank(rows);
    return A.size - (this.n - rankB);
  }

  stabilizerLabel(index: number, maxChars = 10_000): string {
    const row = this.n + index;
    const sign = this._r[row] ? "-" : "+";
    let body = "";
    const limit = Math.min(this.n, maxChars);
    for (let q = 0; q < limit; q++) {
      const xv = Number((this._x[row] >> BigInt(q)) & 1n);
      const zv = Number((this._z[row] >> BigInt(q)) & 1n);
      body += xv && zv ? "Y" : xv ? "X" : zv ? "Z" : "I";
    }
    const full = sign + body;
    if (this.n > maxChars) return full.slice(0, 41) + "...";
    return full;
  }
}

type FracLike = { n: bigint; d: bigint };
const zeroF: FracLike = { n: 0n, d: 1n };
const oneF: FracLike = { n: 1n, d: 1n };
const half: FracLike = { n: 1n, d: 2n };

function bitLength(v: bigint): number {
  let n = 0;
  let x = v;
  while (x) {
    x >>= 32n;
    n += 32;
  }
  if (n === 0) return 0;
  x = v >> BigInt(n - 32);
  let limb = Number(x);
  let extra = 0;
  while (limb) {
    limb >>>= 1;
    extra++;
  }
  return n - 32 + extra;
}

function gf2Rank(rows: bigint[]): number {
  const pivots = new Map<number, bigint>();
  for (const row of rows) {
    let v = row;
    while (v) {
      const b = bitLength(v) - 1;
      const p = pivots.get(b);
      if (p === undefined) {
        pivots.set(b, v);
        break;
      }
      v ^= p;
    }
  }
  return pivots.size;
}
