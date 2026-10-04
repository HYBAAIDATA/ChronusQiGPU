/** Exact Q(√2) + i Q(√2), ported from the Turing VQC `exact_algebra` module. */

export class Frac {
  readonly n: bigint;
  readonly d: bigint;

  constructor(n: bigint | number, d: bigint | number = 1n) {
    let nn = typeof n === "bigint" ? n : BigInt(n);
    let dd = typeof d === "bigint" ? d : BigInt(d);
    if (dd === 0n) throw new Error("zero denominator");
    if (dd < 0n) {
      nn = -nn;
      dd = -dd;
    }
    const g = gcd(nn < 0n ? -nn : nn, dd);
    this.n = nn / g;
    this.d = dd / g;
  }

  static zero(): Frac {
    return new Frac(0n, 1n);
  }

  isZero(): boolean {
    return this.n === 0n;
  }

  isOne(): boolean {
    return this.n === 1n && this.d === 1n;
  }

  neg(): Frac {
    return new Frac(-this.n, this.d);
  }

  add(o: Frac): Frac {
    return new Frac(this.n * o.d + o.n * this.d, this.d * o.d);
  }

  sub(o: Frac): Frac {
    return new Frac(this.n * o.d - o.n * this.d, this.d * o.d);
  }

  mul(o: Frac): Frac {
    return new Frac(this.n * o.n, this.d * o.d);
  }

  div(o: Frac): Frac {
    if (o.n === 0n) throw new Error("division by zero");
    return new Frac(this.n * o.d, this.d * o.n);
  }

  cmp(o: Frac): number {
    const left = this.n * o.d;
    const right = o.n * this.d;
    return left < right ? -1 : left > right ? 1 : 0;
  }

  sign(): number {
    return this.n === 0n ? 0 : this.n > 0n ? 1 : -1;
  }

  approx(): number {
    return Number(this.n) / Number(this.d);
  }

  toString(): string {
    if (this.d === 1n) return this.n.toString();
    return `${this.n}/${this.d}`;
  }
}

function gcd(a: bigint, b: bigint): bigint {
  while (b) {
    const t = a % b;
    a = b;
    b = t;
  }
  return a || 1n;
}

export class Q2 {
  readonly p: Frac;
  readonly q: Frac;

  constructor(p: Frac | number | bigint = 0, q: Frac | number | bigint = 0) {
    this.p = p instanceof Frac ? p : new Frac(typeof p === "bigint" ? p : BigInt(Math.trunc(p)));
    this.q = q instanceof Frac ? q : new Frac(typeof q === "bigint" ? q : BigInt(Math.trunc(q)));
  }

  static zero(): Q2 {
    return new Q2(0, 0);
  }

  static one(): Q2 {
    return new Q2(1, 0);
  }

  add(o: Q2): Q2 {
    return new Q2(this.p.add(o.p), this.q.add(o.q));
  }

  sub(o: Q2): Q2 {
    return new Q2(this.p.sub(o.p), this.q.sub(o.q));
  }

  neg(): Q2 {
    return new Q2(this.p.neg(), this.q.neg());
  }

  mul(o: Q2): Q2 {
    // (p1 + q1√2)(p2 + q2√2) = p1 p2 + 2 q1 q2 + (p1 q2 + q1 p2)√2
    return new Q2(this.p.mul(o.p).add(new Frac(2).mul(this.q).mul(o.q)), this.p.mul(o.q).add(this.q.mul(o.p)));
  }

  inverse(): Q2 {
    const denom = this.p.mul(this.p).sub(new Frac(2).mul(this.q).mul(this.q));
    if (denom.isZero()) throw new Error("Q2 element is not invertible");
    return new Q2(this.p.div(denom), this.q.neg().div(denom));
  }

  div(o: Q2): Q2 {
    return this.mul(o.inverse());
  }

  isZero(): boolean {
    return this.p.isZero() && this.q.isZero();
  }

  eq(o: Q2): boolean {
    return this.p.n === o.p.n && this.p.d === o.p.d && this.q.n === o.q.n && this.q.d === o.q.d;
  }

  sign(): number {
    if (this.q.isZero()) return this.p.sign();
    if (this.p.isZero()) return this.q.sign();
    if (this.p.sign() > 0 && this.q.sign() > 0) return 1;
    if (this.p.sign() < 0 && this.q.sign() < 0) return -1;
    const t = this.p.mul(this.p).sub(new Frac(2).mul(this.q).mul(this.q));
    const tSign = t.sign();
    return this.p.sign() > 0 ? tSign : -tSign;
  }

  approx(): number {
    return this.p.approx() + this.q.approx() * Math.SQRT2;
  }

  toString(): string {
    if (this.q.isZero()) return term(this.p, false);
    if (this.p.isZero()) return term(this.q, true);
    if (this.q.sign() > 0) return `${term(this.p, false)} + ${term(this.q, true)}`;
    return `${term(this.p, false)} - ${term(this.q.neg(), true)}`;
  }
}

function term(coeff: Frac, radical: boolean): string {
  if (coeff.isOne()) return radical ? "√2" : "1";
  if (coeff.n === -1n && coeff.d === 1n) return radical ? "-√2" : "-1";
  return radical ? `${coeff}√2` : coeff.toString();
}

export class Exact {
  readonly re: Q2;
  readonly im: Q2;

  constructor(re: Q2 | number = 0, im: Q2 | number = 0) {
    this.re = re instanceof Q2 ? re : new Q2(re, 0);
    this.im = im instanceof Q2 ? im : new Q2(im, 0);
  }

  add(o: Exact): Exact {
    return new Exact(this.re.add(o.re), this.im.add(o.im));
  }

  sub(o: Exact): Exact {
    return new Exact(this.re.sub(o.re), this.im.sub(o.im));
  }

  neg(): Exact {
    return new Exact(this.re.neg(), this.im.neg());
  }

  mul(o: Exact): Exact {
    return new Exact(this.re.mul(o.re).sub(this.im.mul(o.im)), this.re.mul(o.im).add(this.im.mul(o.re)));
  }

  conjugate(): Exact {
    return new Exact(this.re, this.im.neg());
  }

  normSq(): Q2 {
    return this.re.mul(this.re).add(this.im.mul(this.im));
  }

  isZero(): boolean {
    return this.re.isZero() && this.im.isZero();
  }

  eq(o: Exact): boolean {
    return this.re.eq(o.re) && this.im.eq(o.im);
  }

  approx(): { re: number; im: number } {
    return { re: this.re.approx(), im: this.im.approx() };
  }

  toString(): string {
    if (this.im.isZero()) return this.re.toString();
    if (this.re.isZero()) {
      if (this.im.eq(Q2.one())) return "i";
      if (this.im.eq(Q2.one().neg())) return "-i";
      return `${this.im}i`;
    }
    if (this.im.sign() > 0) return `${this.re} + ${this.im}i`;
    return `${this.re} - ${this.im.neg()}i`;
  }
}

export const ZERO = new Exact(0, 0);
export const ONE = new Exact(Q2.one(), 0);
export const I = new Exact(0, Q2.one());
export const HALF_SQRT2 = new Q2(0, new Frac(1n, 2n));
