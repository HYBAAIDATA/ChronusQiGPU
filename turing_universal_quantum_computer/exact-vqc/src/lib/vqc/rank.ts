/** Algebraic rank is the degree of the polynomial. It is not a Hilbert dimension,
and it is not a spacetime dimension.

A monic irreducible of degree d makes Z[α] a free Z-module of rank d.
Coprime degrees multiply. 10 and 11 are not degrees of this roster.
E8 is not identified. The Grover refusal was a definite form, not N = 9.
*/

import { Frac } from "./algebra.ts";

type Poly = bigint[];

const FAMILIES: { name: string; poly: Poly; written: string }[] = [
  { name: "golden", poly: [1n, -1n, -1n], written: "x^2 - x - 1" },
  { name: "silver", poly: [1n, -2n, -1n], written: "x^2 - 2x - 1" },
  { name: "plastic", poly: [1n, 0n, -1n, -1n], written: "x^3 - x - 1" },
  { name: "tribonacci", poly: [1n, -1n, -1n, -1n], written: "x^3 - x^2 - x - 1" },
  { name: "narayana", poly: [1n, -1n, 0n, -1n], written: "x^3 - x^2 - 1" },
  { name: "tetranacci", poly: [1n, -1n, -1n, -1n, -1n], written: "x^4 - x^3 - x^2 - x - 1" },
];

function integerSquare(n: bigint): bigint | null {
  if (n < 0n) return null;
  if (n < 2n) return n;
  let x = 1n << BigInt((n.toString(2).length + 1) >> 1);
  for (;;) {
    const next = (x + n / x) >> 1n;
    if (next >= x) return x * x === n ? x : null;
    x = next;
  }
}

function rationalRoot(poly: Poly): bigint | null {
  const constant = poly[poly.length - 1];
  const candidates = [1n, -1n];
  if (constant !== 1n && constant !== -1n) {
    let value = constant < 0n ? -constant : constant;
    for (let d = 1n; d * d <= value; d++) {
      if (value % d === 0n) candidates.push(d, -d, value / d, -(value / d));
    }
  }
  for (const root of candidates) {
    let total = 0n;
    for (const coeff of poly) total = total * root + coeff;
    if (total === 0n) return root;
  }
  return null;
}

function factorsAsQuadratics(poly: Poly): boolean {
  if (poly.length !== 5 || poly[0] !== 1n) return false;
  const [, a, b, c, d] = poly;
  const constant = d < 0n ? -d : d;
  const splits: bigint[] = [1n, -1n];
  for (let q = 1n; q * q <= constant; q++) {
    if (constant % q === 0n) splits.push(q, -q, constant / q, -(constant / q));
  }
  for (const q of splits) {
    if (d % q !== 0n) continue;
    const s = d / q;
    const product = b - q - s;
    const disc = a * a - 4n * product;
    const root = integerSquare(disc);
    if (root === null || (a + root) % 2n !== 0n) continue;
    const p = (a + root) / 2n;
    const r = a - p;
    if (p * s + q * r === c) return true;
  }
  return false;
}

function degreeOf(poly: Poly): number {
  if (rationalRoot(poly) !== null) throw new Error(`${poly.join(",")} has a rational root`);
  if (poly.length === 5 && factorsAsQuadratics(poly)) throw new Error("quartic factors");
  if (poly.length > 5) throw new Error("no irreducibility test for this degree");
  return poly.length - 1;
}

function gcd(a: number, b: number): number {
  let x = Math.abs(a);
  let y = Math.abs(b);
  while (y) [x, y] = [y, x % y];
  return x;
}

function compositum(left: number, right: number): number {
  if (gcd(left, right) !== 1) throw new Error("coprime-degree rule does not apply");
  return left * right;
}

function rankOf(rows: Frac[][]): number {
  const a = rows.map((row) => row.map((entry) => new Frac(entry.n, entry.d)));
  let rank = 0;
  let col = 0;
  const width = a[0]?.length ?? 0;
  while (rank < a.length && col < width) {
    let pivot = rank;
    while (pivot < a.length && a[pivot][col].isZero()) pivot += 1;
    if (pivot === a.length) {
      col += 1;
      continue;
    }
    [a[rank], a[pivot]] = [a[pivot], a[rank]];
    const lead = a[rank][col];
    for (let j = col; j < width; j++) a[rank][j] = a[rank][j].div(lead);
    for (let i = 0; i < a.length; i++) {
      if (i === rank || a[i][col].isZero()) continue;
      const factor = a[i][col];
      for (let j = col; j < width; j++) a[i][j] = a[i][j].sub(factor.mul(a[rank][j]));
    }
    rank += 1;
    col += 1;
  }
  return rank;
}

function operatorDegree(dim: number, apply: (vector: Frac[]) => Frac[]): number {
  let vector = Array.from({ length: dim }, (_, index) => new Frac(index === 0 ? 1n : 0n));
  const rows = Array.from({ length: dim }, () => [] as Frac[]);
  let rank = 0;
  for (let power = 0; power <= dim; power++) {
    vector.forEach((entry, index) => rows[index].push(entry));
    const current = rankOf(rows);
    if (current === rank) return power;
    rank = current;
    vector = apply(vector);
  }
  throw new Error("no relation inside the basis");
}

function silverGoldenDegree(): number {
  return operatorDegree(4, (vector) => {
    const [a, b, c, d] = vector;
    const byRoot2 = [b.mul(new Frac(2n)), a, d.mul(new Frac(2n)), c];
    const byRoot5 = [c.mul(new Frac(5n)), d.mul(new Frac(5n)), a, b];
    return byRoot2.map((entry, index) => entry.add(byRoot5[index]));
  });
}

function plasticGoldenDegree(): number {
  return operatorDegree(6, (vector) => {
    const [a, b, c, d, e, f] = vector;
    const byPhi = [b, a.add(b), d, c.add(d), f, e.add(f)];
    const byRho = [e, f, a.add(e), b.add(f), c, d];
    return byPhi.map((entry, index) => entry.add(byRho[index]));
  });
}

let cached: string | null = null;

export function rankReport(): string {
  if (cached) return cached;
  const control = factorsAsQuadratics([1n, -3n, 0n, 3n, 1n]);
  if (!control) throw new Error("the quadratic-factor test missed a reducible quartic");
  const ranks = FAMILIES.map((family) => ({ ...family, rank: degreeOf(family.poly) }));
  const goldenSilver = silverGoldenDegree();
  const plasticGolden = plasticGoldenDegree();
  if (plasticGolden !== compositum(2, 3)) throw new Error("the computed compositum disagreed with the coprime-degree count");
  if (goldenSilver !== 4) throw new Error("Q(√2, √5) did not have degree 4");
  const quaternionOverR = 4;
  const quaternionOverGolden = 4;
  const coordinateRank = quaternionOverR * 2;
  if (coordinateRank !== 8) throw new Error("golden quaternion rank left 8");
  const groverAt9 = -4n * (9n - 1n);
  if (groverAt9 >= 0n) throw new Error("the Grover form became indefinite");
  const lines = [
    "rank",
    "  rank = degree of the monic irreducible",
    "  one integer coordinate per power 1, α, …, α^(d−1)",
    "  theorem_proven = False",
    "",
    "[fields]",
  ];
  for (const family of ranks) {
    lines.push(`  ${family.name}    ${family.written}    rank = ${family.rank}`);
  }
  lines.push(
    "  a float root is not a coordinate",
    "",
    "[what may be multiplied]",
    "  Q(√5) and Q(√2) are both degree 2, so the coprime rule does not apply",
    `  computed degree of √2 + √5 = ${goldenSilver}`,
    "  basis 1, √2, √5, √10",
    "  Q(φ) ⊗ Q(φ) has dimension 4 and is not a field",
    "  the conjugate 1−φ lies in Q(φ), so the tensor splits",
    `  computed degree of φ + ρ = ${plasticGolden}`,
    "",
    "[what 4, 6 and 8 are, separately]",
    "  4 = degree of the tetranacci polynomial",
    "  4 = degree of Q(√2, √5)",
    "  4 = dimension of the quaternions over R, the 600-cell's sphere",
    "  6 = degree of Q(φ, ρ)",
    "  6 = 3 + 3, a 3D icosahedral matrix with entries in Q(√5) plus its conjugate",
    "  6 also occurs as an irrep degree of 2I in `thread`; that is not this compositum",
    `  8 = ${quaternionOverGolden} quaternion slots times the golden rank 2`,
    "  that is the Q-dimension of the golden quaternion algebra",
    "  identifying it with the E8 root lattice is not proved here",
    "",
    "[refused]",
    "  10D = refused    no polynomial of degree 10 is computed",
    "  11D = refused    no polynomial of degree 11 is computed",
    "  anomaly cancellation is not a calculation in this system",
    "  unitarity does not fail merely because a matrix entry lies in Q(√5)",
    `  N = 9 was not the Grover obstruction    discriminant −4(N−1) = ${groverAt9}`,
    "  the form stays definite for every N > 1",
    "  rank is not the dimension of a Hilbert space",
    "  a walk on a rank-d lattice has one basis state per site, not per degree",
  );
  cached = lines.join("\n");
  return cached;
}
