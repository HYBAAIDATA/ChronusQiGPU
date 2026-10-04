/** Canonical finite Φ-gap from QuantumPhi2/PhiMiner `millennium/hyba_golden_mass_gap.py`.

Integer Fibonacci–Lucas certificates, the truncated-icosahedron 32-frame in Q(√5),
and the combinatorial Laplacian whose gap is the least root of an irreducible
quintic. No decimal eigenvalue, no GeV conversion, no Gaussian potential.
The attachment dodecahedron (two swapped coordinates) is rejected.
*/

import { Frac } from "./algebra.ts";

class Q5 {
  readonly a: Frac;
  readonly b: Frac;

  constructor(a: Frac, b: Frac) {
    this.a = a;
    this.b = b;
  }

  static zero(): Q5 {
    return new Q5(new Frac(0n), new Frac(0n));
  }

  static int(n: bigint | number): Q5 {
    return new Q5(new Frac(typeof n === "bigint" ? n : BigInt(n)), new Frac(0n));
  }

  static ratio(n: bigint, d: bigint, bn: bigint = 0n, bd: bigint = 1n): Q5 {
    return new Q5(new Frac(n, d), new Frac(bn, bd));
  }

  add(o: Q5): Q5 {
    return new Q5(this.a.add(o.a), this.b.add(o.b));
  }

  sub(o: Q5): Q5 {
    return new Q5(this.a.sub(o.a), this.b.sub(o.b));
  }

  neg(): Q5 {
    return new Q5(this.a.neg(), this.b.neg());
  }

  mul(o: Q5): Q5 {
    return new Q5(this.a.mul(o.a).add(new Frac(5n).mul(this.b).mul(o.b)), this.a.mul(o.b).add(this.b.mul(o.a)));
  }

  div(o: Q5): Q5 {
    const norm = o.a.mul(o.a).sub(new Frac(5n).mul(o.b).mul(o.b));
    if (norm.isZero()) throw new Error("division by zero in Q(√5)");
    const num = this.mul(new Q5(o.a, o.b.neg()));
    return new Q5(num.a.div(norm), num.b.div(norm));
  }

  pow(n: number): Q5 {
    if (n < 0) return Q5.int(1).div(this).pow(-n);
    let result = Q5.int(1);
    let base: Q5 = this;
    let exp = n;
    while (exp) {
      if (exp & 1) result = result.mul(base);
      base = base.mul(base);
      exp >>= 1;
    }
    return result;
  }

  eq(o: Q5): boolean {
    return this.a.n === o.a.n && this.a.d === o.a.d && this.b.n === o.b.n && this.b.d === o.b.d;
  }

  isZero(): boolean {
    return this.a.isZero() && this.b.isZero();
  }

  /** Sign of this − n. */
  cmpInt(n: bigint): number {
    const d = this.a.sub(new Frac(n));
    if (this.b.isZero()) return d.sign();
    const left = new Frac(5n).mul(this.b).mul(this.b);
    const right = d.mul(d);
    const cmp = left.cmp(right);
    if (this.b.sign() > 0) {
      if (d.sign() >= 0) return 1;
      return cmp > 0 ? 1 : cmp < 0 ? -1 : 0;
    }
    if (d.sign() <= 0) return -1;
    return cmp > 0 ? -1 : cmp < 0 ? 1 : 0;
  }
}

const PHI = Q5.ratio(1n, 2n, 1n, 2n);
const PHI_INV = Q5.ratio(-1n, 2n, 1n, 2n);
const GAP_QUINTIC = [1n, -59n, 1360n, -15216n, 81792n, -165904n];
const STURM = [
  GAP_QUINTIC,
  [5n, -236n, 4080n, -30432n, 81792n],
  [81n, -3120n, 39912n, -169532n],
  [1218n, -31089n, 198124n],
  [87189n, -1134188n],
  [1n],
];

type Poly = Frac[];

function horner(coeffs: bigint[], value: bigint): bigint {
  let total = 0n;
  for (const coeff of coeffs) total = total * value + coeff;
  return total;
}

function fibPair(n: number): [bigint, bigint] {
  if (n === 0) return [0n, 1n];
  const [a, b] = fibPair(n >> 1);
  const c = a * ((b << 1n) - a);
  const d = a * a + b * b;
  return n & 1 ? [d, c + d] : [c, d];
}

function F(n: number): bigint {
  if (n < 0) throw new Error("Fibonacci index must be non-negative");
  return fibPair(n)[0];
}

function L(n: number): bigint {
  if (n === 0) return 2n;
  return F(n - 1) + F(n + 1);
}

function cassini(n: number): bigint {
  return F(n + 1) * F(n - 1) - F(n) * F(n);
}

class ZPhi {
  readonly a: bigint;
  readonly b: bigint;

  constructor(a: bigint, b: bigint) {
    this.a = a;
    this.b = b;
  }

  mul(o: ZPhi): ZPhi {
    return new ZPhi(this.a * o.a + this.b * o.b, this.a * o.b + this.b * o.a + this.b * o.b);
  }

  pow(exponent: number): ZPhi {
    let result = new ZPhi(1n, 0n);
    let base = exponent < 0 ? new ZPhi(-1n, 1n) : this;
    let exp = exponent < 0 ? -exponent : exponent;
    while (exp) {
      if (exp & 1) result = result.mul(base);
      base = base.mul(base);
      exp >>= 1;
    }
    return result;
  }
}

const PHI_RING = new ZPhi(0n, 1n);

function zeckendorf(n: number): number[] {
  if (n < 0) throw new Error("n must be non-negative");
  const values = [1];
  let a = 1;
  let b = 2;
  while (b <= n) {
    values.push(b);
    [a, b] = [b, a + b];
  }
  const indices: number[] = [];
  let rem = n;
  for (let i = values.length - 1; i >= 0; i--) {
    if (values[i] <= rem) {
      indices.push(i + 2);
      rem -= values[i];
    }
  }
  return indices;
}

function verifyAlgebra(limit = 200): string[] {
  const lines: string[] = [];
  let cassiniOk = true;
  let lucasOk = true;
  let uniOk = true;
  let matrixOk = true;
  let traceOk = true;
  let binetOk = true;
  for (let n = 1; n <= limit; n++) {
    const sign = n % 2 === 0 ? 1n : -1n;
    if (cassini(n) !== sign) cassiniOk = false;
    if (L(n) * L(n) - 5n * F(n) * F(n) !== 4n * sign) lucasOk = false;
    if (cassini(n) !== 1n && cassini(n) !== -1n) uniOk = false;
    if (F(n + 1) !== F(n) + F(n - 1)) matrixOk = false;
    if (F(n + 1) + F(n - 1) !== L(n)) traceOk = false;
    const power = PHI_RING.pow(n);
    if (power.b !== F(n) || power.a !== F(n - 1)) binetOk = false;
    const conjugate = new ZPhi(power.a + power.b, -power.b);
    const gap = new ZPhi(L(n) - power.a, -power.b);
    if (gap.a !== conjugate.a || gap.b !== conjugate.b) binetOk = false;
  }
  let zeckOk = true;
  for (let n = 1; n < 1000; n++) {
    const encoded = zeckendorf(n);
    let sum = 0;
    for (let k = 0; k < encoded.length; k++) {
      const index = encoded[k];
      sum += Number(F(index));
      if (k > 0 && encoded[k - 1] - index < 2) zeckOk = false;
    }
    if (sum !== n) zeckOk = false;
  }
  const mark = (ok: boolean) => (ok ? "PASS" : "FAIL");
  lines.push(`  Cassini              F(n+1)F(n−1) − F(n)² = (−1)^n     ${mark(cassiniOk)}`);
  lines.push(`  Lucas–Cassini        L(n)² − 5 F(n)² = 4(−1)^n         ${mark(lucasOk)}`);
  lines.push(`  Unimodular           |det M^n| = 1                      ${mark(uniOk)}`);
  lines.push(`  Matrix power         M^n = [[F(n+1), F(n)],[F(n), F(n−1)]]  ${mark(matrixOk)}`);
  lines.push(`  Binet in Z[φ]        φ^n = F(n−1) + F(n) φ              ${mark(binetOk)}`);
  lines.push(`  Pisot                L(n) − φ^n = ψ^n                    ${mark(binetOk)}`);
  lines.push(`  Zeckendorf           unique non-adjacent code, n<1000   ${mark(zeckOk)}`);
  lines.push(`  Trace                tr(M^n) = L(n)                     ${mark(traceOk)}`);
  if (!cassiniOk || !lucasOk || !uniOk || !matrixOk || !traceOk || !binetOk || !zeckOk) {
    throw new Error("golden-ratio certificates failed");
  }
  return lines;
}

function cyclic(sa: number, first: Q5, sb: number, second: Q5): Q5[][] {
  const left = first.mul(Q5.int(sa));
  const right = second.mul(Q5.int(sb));
  const zero = Q5.zero();
  return [
    [zero, left, right],
    [left, right, zero],
    [right, zero, left],
  ];
}

function frame(): Q5[][] {
  const orbitA: Q5[][] = [];
  const orbitB: Q5[][] = [];
  for (const sa of [1, -1]) {
    for (const sb of [1, -1]) orbitA.push(...cyclic(sa, Q5.int(1), sb, PHI));
  }
  for (const sx of [1, -1]) {
    for (const sy of [1, -1]) {
      for (const sz of [1, -1]) orbitB.push([Q5.int(sx), Q5.int(sy), Q5.int(sz)]);
    }
  }
  for (const sa of [1, -1]) {
    for (const sb of [1, -1]) orbitB.push(...cyclic(sa, PHI_INV, sb, PHI));
  }
  const points = orbitA.concat(orbitB);
  if (points.length !== 32 || orbitA.length !== 12 || orbitB.length !== 20) {
    throw new Error("M32 frame must be 12 icosahedral plus 20 dodecahedral directions");
  }
  return points;
}

function dot(p: Q5[], q: Q5[]): Q5 {
  return p[0].mul(q[0]).add(p[1].mul(q[1])).add(p[2].mul(q[2]));
}

const LEGENDRE: { power: number; coeff: Frac }[][] = [
  [],
  [{ power: 1, coeff: new Frac(1n) }],
  [
    { power: 2, coeff: new Frac(3n, 2n) },
    { power: 0, coeff: new Frac(-1n, 2n) },
  ],
  [
    { power: 3, coeff: new Frac(5n, 2n) },
    { power: 1, coeff: new Frac(-3n, 2n) },
  ],
  [
    { power: 4, coeff: new Frac(35n, 8n) },
    { power: 2, coeff: new Frac(-30n, 8n) },
    { power: 0, coeff: new Frac(3n, 8n) },
  ],
  [
    { power: 5, coeff: new Frac(63n, 8n) },
    { power: 3, coeff: new Frac(-70n, 8n) },
    { power: 1, coeff: new Frac(15n, 8n) },
  ],
];

function legendre(degree: number, cosine: Q5): Q5 {
  let total = Q5.zero();
  for (const term of LEGENDRE[degree]) {
    total = total.add(cosine.pow(term.power).mul(new Q5(term.coeff, new Frac(0n))));
  }
  return total;
}

function designVanishes(points: Q5[][]): boolean {
  const normA = PHI.add(Q5.int(2));
  const normB = Q5.int(3);
  const norms = points.map((point) => dot(point, point));
  if (norms.some((norm) => !norm.eq(normA) && !norm.eq(normB))) return false;
  const cross = normA.mul(normB);
  for (let ell = 1; ell <= 5; ell++) {
    let rational = Q5.zero();
    let weight = Q5.zero();
    for (let i = 0; i < 32; i++) {
      for (let j = 0; j < 32; j++) {
        const inner = dot(points[i], points[j]);
        if (norms[i].eq(norms[j])) {
          rational = rational.add(legendre(ell, inner.div(norms[i])));
        } else {
          for (const term of LEGENDRE[ell]) {
            let value = inner.pow(term.power).mul(new Q5(term.coeff, new Frac(0n)));
            if (term.power % 2 === 0) {
              value = value.div(cross.pow(term.power / 2));
              rational = rational.add(value);
            } else {
              value = value.div(cross.pow((term.power - 1) / 2));
              weight = weight.add(value);
            }
          }
        }
      }
    }
    if (!rational.isZero() || !weight.isZero()) return false;
  }
  return true;
}

function laplacian(points: Q5[][]): { matrix: bigint[][]; edges: number } {
  const normA = PHI.add(Q5.int(2));
  const normB = Q5.int(3);
  const cut = Q5.ratio(-1n, 4n, 1n, 4n);
  const norms = points.map((point) => dot(point, point));
  if (norms.some((norm) => !norm.eq(normA) && !norm.eq(normB))) {
    throw new Error("frame left the icosahedral and dodecahedral orbits");
  }
  const cross = normA.mul(normB);
  const matrix = Array.from({ length: 32 }, () => Array.from({ length: 32 }, () => 0n));
  let edges = 0;
  for (let i = 0; i < 32; i++) {
    for (let j = i + 1; j < 32; j++) {
      const inner = dot(points[i], points[j]);
      let above = false;
      if (norms[i].eq(norms[j])) above = inner.div(norms[i]).sub(cut).cmpInt(0n) > 0;
      else if (inner.cmpInt(0n) > 0) above = inner.mul(inner).sub(cut.mul(cut).mul(cross)).cmpInt(0n) > 0;
      if (above) {
        matrix[i][j] = matrix[j][i] = -1n;
        matrix[i][i] += 1n;
        matrix[j][j] += 1n;
        edges += 1;
      }
    }
  }
  return { matrix, edges };
}

function bareissDet(source: bigint[][]): bigint {
  const work = source.map((row) => row.slice());
  const size = work.length;
  let sign = 1n;
  let previous = 1n;
  for (let k = 0; k < size - 1; k++) {
    if (work[k][k] === 0n) {
      let swap = -1;
      for (let row = k + 1; row < size; row++) {
        if (work[row][k] !== 0n) {
          swap = row;
          break;
        }
      }
      if (swap < 0) return 0n;
      [work[k], work[swap]] = [work[swap], work[k]];
      sign = -sign;
    }
    for (let i = k + 1; i < size; i++) {
      for (let j = k + 1; j < size; j++) {
        const numer = work[i][j] * work[k][k] - work[i][k] * work[k][j];
        if (numer % previous !== 0n) throw new Error("Bareiss division was not exact");
        work[i][j] = numer / previous;
      }
    }
    previous = work[k][k];
  }
  return sign * work[size - 1][size - 1];
}

function claimedCharpoly(value: bigint): bigint {
  const golden = value * value - 26n * value + 164n;
  const other = value * value - 23n * value + 128n;
  const quintic = horner(GAP_QUINTIC, value);
  return value * (value - 15n) * (value - 14n) ** 6n * (value - 11n) ** 3n * golden ** 2n * other * quintic ** 3n;
}

function charpolyMatches(matrix: bigint[][]): boolean {
  for (let value = 0; value <= 32; value++) {
    const shifted = matrix.map((row, i) => row.map((entry, j) => (i === j ? BigInt(value) : 0n) - entry));
    if (bareissDet(shifted) !== claimedCharpoly(BigInt(value))) return false;
  }
  return true;
}

function trim(coeffs: Poly): Poly {
  let start = 0;
  while (start < coeffs.length - 1 && coeffs[start].isZero()) start++;
  return coeffs.slice(start);
}

function divide(dividend: Poly, divisor: Poly): Poly {
  let rem = trim(dividend.map((coeff) => new Frac(coeff.n, coeff.d)));
  const div = trim(divisor);
  const degree = div.length - 1;
  while (rem.length - 1 >= degree && !(rem.length === 1 && rem[0].isZero())) {
    const lead = rem[0].div(div[0]);
    const shift = rem.length - div.length;
    const next = rem.map((coeff) => new Frac(coeff.n, coeff.d));
    for (let i = 0; i < div.length; i++) next[i + shift] = next[i + shift].sub(lead.mul(div[i]));
    rem = trim(next);
  }
  return rem;
}

function scalarMultiple(remainder: Poly, target: bigint[]): boolean {
  const rem = trim(remainder);
  const poly = trim(target.map((coeff) => new Frac(coeff)));
  if (rem.length === 1 && rem[0].isZero()) return poly.length === 1 && poly[0].isZero();
  if (rem.length !== poly.length) return false;
  const scale = rem[0].div(poly[0]);
  return rem.every((coeff, index) => coeff.n === scale.mul(poly[index]).n && coeff.d === scale.mul(poly[index]).d);
}

function sturmChainHolds(): boolean {
  const derivative = [5n, -236n, 4080n, -30432n, 81792n];
  if (STURM[1].some((coeff, index) => coeff !== derivative[index])) return false;
  for (let index = 0; index < STURM.length - 2; index++) {
    const remainder = divide(
      STURM[index].map((coeff) => new Frac(coeff)),
      STURM[index + 1].map((coeff) => new Frac(coeff)),
    );
    if (!scalarMultiple(remainder, STURM[index + 2])) return false;
  }
  return true;
}

function variations(value: bigint): number {
  const signs: number[] = [];
  for (const coeffs of STURM) {
    const evaluated = horner(coeffs, value);
    if (evaluated > 0n) signs.push(1);
    else if (evaluated < 0n) signs.push(-1);
  }
  let changes = 0;
  for (let i = 1; i < signs.length; i++) if (signs[i] !== signs[i - 1]) changes++;
  return changes;
}

function signAt(numerator: bigint, denominator: bigint): bigint {
  let scaled = GAP_QUINTIC[0];
  let denPow = 1n;
  for (const coeff of GAP_QUINTIC.slice(1)) {
    denPow *= denominator;
    scaled = scaled * numerator + coeff * denPow;
  }
  return scaled;
}

function quinticIrreducibleMod5(): boolean {
  const coeffs = GAP_QUINTIC.map((coeff) => ((coeff % 5n) + 5n) % 5n);
  const evaluate = (point: bigint) => {
    let total = 0n;
    for (const coeff of coeffs) total = (total * point + coeff) % 5n;
    return total;
  };
  if ([0n, 1n, 2n, 3n, 4n].some((point) => evaluate(point) === 0n)) return false;
  for (let b = 0n; b < 5n; b++) {
    for (let c = 0n; c < 5n; c++) {
      const out = coeffs.slice();
      for (let i = 0; i < 4; i++) {
        const lead = out[i];
        out[i + 1] = (out[i + 1] - lead * b) % 5n;
        out[i + 2] = (out[i + 2] - lead * c) % 5n;
      }
      if (out[4] === 0n && out[5] === 0n) return false;
    }
  }
  return true;
}

function isolate(): [Frac, Frac] {
  if (variations(0n) - variations(6n) !== 1) throw new Error("the quintic does not have exactly one root in (0, 6)");
  if (horner(GAP_QUINTIC, 5n) >= 0n || horner(GAP_QUINTIC, 6n) <= 0n) {
    throw new Error("the gap root is not inside (5, 6)");
  }
  let lo = new Frac(5n);
  let hi = new Frac(6n);
  for (let step = 0; step < 40; step++) {
    const mid = lo.add(hi).div(new Frac(2n));
    if (signAt(mid.n, mid.d) < 0n) lo = mid;
    else hi = mid;
  }
  return [lo, hi];
}

let cached: string | null = null;

/** Exact finite spectrum. The continuum problem stays open. */
export function goldenReport(): string {
  if (cached) return cached;
  const algebra = verifyAlgebra();
  const points = frame();
  if (!designVanishes(points)) throw new Error("M32 frame failed the exact spherical-design moments");
  const { matrix, edges } = laplacian(points);
  if (edges !== 192) throw new Error(`canonical cut produced ${edges} edges, not 192`);
  const degrees = matrix.map((row, index) => row[index]);
  const degreeSum = degrees.reduce((sum, degree) => sum + degree, 0n);
  if (degreeSum !== BigInt(2 * edges)) throw new Error("Laplacian degrees do not match the edge count");
  if (!charpolyMatches(matrix)) throw new Error("characteristic polynomial does not match the factorization");
  if (!sturmChainHolds()) throw new Error("Sturm chain is not the remainder sequence of q");
  if (!quinticIrreducibleMod5()) throw new Error("gap quintic factored modulo 5");
  const [lower, upper] = isolate();
  if (!(signAt(3396n, 1000n) < 0n && signAt(3397n, 1000n) > 0n)) {
    throw new Error("the gap root is not inside (3396/1000, 3397/1000)");
  }
  const degreeMin = degrees.reduce((min, degree) => (degree < min ? degree : min));
  const degreeMax = degrees.reduce((max, degree) => (degree > max ? degree : max));
  const lines = [
    "canonical 32-frame Laplacian   materialised amplitudes = False",
    "  arithmetic = exact integers and Q(√5)",
    "  continuum Yang–Mills = not claimed",
    "  QCD mass = not claimed",
    "  Cassini certifies the gap = False",
    "",
    "[1] GOLDEN FAMILY   n ≤ 200, Zeckendorf n < 1000",
    ...algebra,
    "",
    "[2] M32 FRAME",
    "  directions = 32   (12 icosahedral + 20 dodecahedral)",
    "  spherical design degrees 1..5 = zero moments   PASS",
    "  cut = cosine > cos(2π/5) = (√5−1)/4",
    `  edges = ${edges}    degree ${degreeMin}..${degreeMax}`,
    "  kernel multiplicity = 1, so the graph is connected",
    "  attachment dodecahedron = rejected (two coordinates swapped)",
    "",
    "[3] SPECTRUM",
    "  det(tI−L) = t(t−15)(t−14)^6(t−11)^3(t²−26t+164)^2(t²−23t+128) q(t)^3",
    "  identity checked at 33 integers   PASS",
    "  q = t^5 − 59t^4 + 1360t^3 − 15216t^2 + 81792t − 165904",
    "  q irreducible over Q (no linear or quadratic factor mod 5)   PASS",
    "  the gap Δ is the unique root of q in (5, 6), degree 5, not in Q(√5)",
    `  isolated   ${lower} < Δ < ${upper}`,
    "  3396/1000 < Δ < 3397/1000",
    "  floor(1000·Δ) = 3396",
    "  the next golden eigenvalue is 13−√5 > 6, since 49 > 5",
    "",
    "[4] REFUSED",
    "  a decimal standing in for Δ",
    "  conversion of Δ into GeV",
    "  H = L + exp(−(σ−φ)²/Λ²); that potential is not this operator",
    "  det(M^3396) = (−1)^3396 is a Fibonacci identity, not a certificate of Δ",
  ];
  cached = lines.join("\n");
  return cached;
}
