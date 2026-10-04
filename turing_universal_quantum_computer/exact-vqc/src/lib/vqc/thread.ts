/** Finite SU(2) thread: φ → icosians → 2I → Σ(2,3,5) → gap.

Exact integer quaternion arithmetic. The class-function Laplacian is a 9×9
rational matrix. Its characteristic polynomial is computed by exact division,
then factored. No float diagonalization and no tolerance recognition.
Continuum Yang–Mills is not claimed.
*/

import { Frac } from "./algebra.ts";
import { fibonacci, lucas } from "./lucas-scale.ts";

type Pair = [number, number];
type Quat = [Pair, Pair, Pair, Pair];

const Z: Pair = [0, 0];
const ONE: Pair = [4, 0];
const IDENTITY: Quat = [ONE, Z, Z, Z];
/** g = (1/(2φ), 0, −φ/2, 1/2). */
const GOLDEN: Quat = [
  [-1, 1],
  [0, 0],
  [-1, -1],
  [2, 0],
];

function prod(x: Pair, y: Pair): Pair {
  return [x[0] * y[0] + 5 * x[1] * y[1], x[0] * y[1] + x[1] * y[0]];
}

function neg(x: Pair): Pair {
  return [-x[0], -x[1]];
}

function sumRed(terms: Pair[]): Pair {
  let p = 0;
  let q = 0;
  for (const term of terms) {
    p += term[0];
    q += term[1];
  }
  if (p % 4 !== 0 || q % 4 !== 0) throw new Error(`icosian sum not divisible by 4: ${p}, ${q}`);
  return [p / 4, q / 4];
}

function qmul(a: Quat, b: Quat): Quat {
  const [a1, a2, a3, a4] = a;
  const [b1, b2, b3, b4] = b;
  return [
    sumRed([prod(a1, b1), neg(prod(a2, b2)), neg(prod(a3, b3)), neg(prod(a4, b4))]),
    sumRed([prod(a1, b2), prod(a2, b1), prod(a3, b4), neg(prod(a4, b3))]),
    sumRed([prod(a1, b3), neg(prod(a2, b4)), prod(a3, b1), prod(a4, b2)]),
    sumRed([prod(a1, b4), prod(a2, b3), neg(prod(a3, b2)), prod(a4, b1)]),
  ];
}

function qinv(a: Quat): Quat {
  return [a[0], neg(a[1]), neg(a[2]), neg(a[3])];
}

function key(a: Quat): string {
  return a.map((pair) => `${pair[0]},${pair[1]}`).join(";");
}

function same(a: Quat, b: Quat): boolean {
  return key(a) === key(b);
}

function norm2(a: Quat): Pair {
  let p = 0;
  let q = 0;
  for (const part of a) {
    p += part[0] * part[0] + 5 * part[1] * part[1];
    q += 2 * part[0] * part[1];
  }
  return [p, q];
}

function isUnit(a: Quat): boolean {
  const [p, q] = norm2(a);
  return p === 16 && q === 0;
}

function orderOf(element: Quat): number {
  let acc = element;
  let order = 1;
  while (!same(acc, IDENTITY)) {
    acc = qmul(acc, element);
    order += 1;
    if (order > 200) throw new Error("element order exceeded 200");
  }
  return order;
}

function tetrahedral(): Quat[] {
  const elements: Quat[] = [];
  for (const sign of [1, -1]) {
    const axis: Pair = [sign * 4, 0];
    elements.push([axis, Z, Z, Z], [Z, axis, Z, Z], [Z, Z, axis, Z], [Z, Z, Z, axis]);
  }
  for (const s1 of [1, -1]) {
    for (const s2 of [1, -1]) {
      for (const s3 of [1, -1]) {
        for (const s4 of [1, -1]) elements.push([[2 * s1, 0], [2 * s2, 0], [2 * s3, 0], [2 * s4, 0]]);
      }
    }
  }
  return elements;
}

function closeGroup(generators: Quat[]): Quat[] {
  const have = new Map<string, Quat>([[key(IDENTITY), IDENTITY]]);
  const frontier = [IDENTITY];
  while (frontier.length) {
    const current = frontier.pop()!;
    for (const generator of generators) {
      const product = qmul(current, generator);
      const id = key(product);
      if (!have.has(id)) {
        have.set(id, product);
        frontier.push(product);
      }
    }
  }
  return [...have.values()];
}

function classesOf(elements: Quat[]): Quat[][] {
  const remaining = new Set(elements.map(key));
  const byKey = new Map(elements.map((element) => [key(element), element]));
  const classes: Quat[][] = [];
  for (const element of elements) {
    if (!remaining.has(key(element))) continue;
    const found: Quat[] = [];
    for (const conjugator of elements) {
      const image = qmul(qmul(conjugator, element), qinv(conjugator));
      const id = key(image);
      if (remaining.has(id)) {
        remaining.delete(id);
        found.push(byKey.get(id)!);
      }
    }
    classes.push(found);
  }
  return classes;
}

function zeckendorfOk(): boolean {
  for (let n = 1; n < 1000; n++) {
    const values: number[] = [1];
    let a = 1;
    let b = 2;
    while (b <= n) {
      values.push(b);
      [a, b] = [b, a + b];
    }
    let rem = n;
    let previous = 100;
    for (let i = values.length - 1; i >= 0; i--) {
      if (values[i] <= rem) {
        const index = i + 2;
        if (previous - index < 2) return false;
        previous = index;
        rem -= values[i];
      }
    }
    if (rem !== 0) return false;
  }
  return true;
}

function goldenFamily(): boolean {
  for (let n = 1; n <= 200; n++) {
    const sign = n % 2 === 0 ? 1n : -1n;
    const f = fibonacci(n);
    const prev = fibonacci(n - 1);
    const next = fibonacci(n + 1);
    if (next * prev - f * f !== sign) return false;
    const l = lucas(n);
    if (l * l - 5n * f * f !== 4n * sign) return false;
    if (next + prev !== l) return false;
  }
  return zeckendorfOk();
}

function bareiss(source: bigint[][]): bigint {
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

function characteristic(matrix: bigint[][]): bigint[] {
  const degree = matrix.length;
  const values: bigint[] = [];
  for (let point = 0; point <= degree; point++) {
    const shifted = matrix.map((row, i) => row.map((entry, j) => (i === j ? BigInt(point) : 0n) - entry));
    values.push(bareiss(shifted));
  }
  const diffs: bigint[][] = [values.slice()];
  for (let order = 1; order <= degree; order++) {
    const previous = diffs[order - 1];
    diffs.push(previous.slice(1).map((value, index) => value - previous[index]));
  }
  const stirling: bigint[][] = [[1n]];
  for (let n = 1; n <= degree; n++) {
    const row = Array.from({ length: n + 1 }, () => 0n);
    for (let k = 1; k <= n; k++) row[k] = stirling[n - 1][k - 1] - BigInt(n - 1) * (stirling[n - 1][k] ?? 0n);
    stirling.push(row);
  }
  const coeffs = Array.from({ length: degree + 1 }, () => 0n);
  let factorial = 1n;
  for (let m = 0; m <= degree; m++) {
    if (m > 0) factorial *= BigInt(m);
    if (diffs[m][0] % factorial !== 0n) throw new Error("characteristic polynomial left the integers");
    const scale = diffs[m][0] / factorial;
    for (let power = 0; power <= m; power++) coeffs[power] += scale * stirling[m][power];
  }
  return coeffs;
}

function polyToString(coeffs: bigint[]): string {
  const terms: string[] = [];
  for (let power = coeffs.length - 1; power >= 0; power--) {
    const coeff = coeffs[power];
    if (coeff === 0n) continue;
    const body = power === 0 ? `${coeff}` : power === 1 ? "t" : `t^${power}`;
    const shown = coeff === 1n && power > 0 ? body : coeff === -1n && power > 0 ? `-${body}` : `${coeff}${power > 0 ? body : ""}`;
    terms.push(shown);
  }
  return terms.join(" + ").replaceAll("+ -", "- ");
}

type Alg = { a: bigint; b: bigint; d: bigint };

function gcdPair(left: bigint, right: bigint): bigint {
  let a = left < 0n ? -left : left;
  let b = right < 0n ? -right : right;
  while (b) {
    const next = a % b;
    a = b;
    b = next;
  }
  return a || 1n;
}

function alg(a: bigint, b: bigint, d: bigint): Alg {
  if (d < 0n) return alg(-a, -b, -d);
  const divisor = gcdPair(gcdPair(a, b), d);
  return { a: a / divisor, b: b / divisor, d: d / divisor };
}

function cmpAlg(left: Alg, right: Alg): number {
  const rational = left.a * right.d - right.a * left.d;
  const radical = left.b * right.d - right.b * left.d;
  if (radical === 0n) return rational > 0n ? 1 : rational < 0n ? -1 : 0;
  const squares = 5n * radical * radical;
  const other = rational * rational;
  if (radical > 0n) {
    if (rational >= 0n) return 1;
    return squares > other ? 1 : squares < other ? -1 : 0;
  }
  if (rational <= 0n) return -1;
  return squares > other ? -1 : squares < other ? 1 : 0;
}

function positive(value: Alg): boolean {
  return cmpAlg(value, alg(0n, 0n, 1n)) > 0;
}

function show(value: Alg): string {
  if (value.b === 0n) return value.d === 1n ? value.a.toString() : `${value.a}/${value.d}`;
  let body = value.a.toString();
  if (value.b > 0n) body += value.b === 1n ? " + √5" : ` + ${value.b}√5`;
  if (value.b < 0n) body += value.b === -1n ? " - √5" : ` - ${-value.b}√5`;
  return value.d === 1n ? body : `(${body})/${value.d}`;
}

function rootsOf(factor: bigint[]): Alg[] {
  if (factor.length === 2 && factor[1] === 1n) return [alg(-factor[0], 0n, 1n)];
  if (factor.length === 3 && factor[2] === 1n) {
    const sum = -factor[1];
    const [square, radical] = squareSplit(sum * sum - 4n * factor[0]);
    if (radical === 1n) return [alg(sum + square, 0n, 2n), alg(sum - square, 0n, 2n)];
    if (radical !== 5n) throw new Error(`eigenvalue discriminant left Q(√5): ${radical}`);
    return [alg(sum, square, 2n), alg(sum, -square, 2n)];
  }
  throw new Error(`unfactored spectrum factor ${polyToString(factor)}`);
}

function divideLow(dividend: bigint[], factor: bigint[]): bigint[] | null {
  const out = dividend.slice();
  const degree = factor.length - 1;
  const lead = factor[degree];
  if (lead === 0n) return null;
  const quotient = Array.from({ length: out.length - degree }, () => 0n);
  for (let power = out.length - 1; power >= degree; power--) {
    if (out[power] % lead !== 0n) return null;
    const scale = out[power] / lead;
    quotient[power - degree] = scale;
    for (let i = 0; i <= degree; i++) out[power - degree + i] -= scale * factor[i];
  }
  if (out.slice(0, degree).some((coeff) => coeff !== 0n)) return null;
  return quotient;
}

function divisors(value: bigint): bigint[] {
  const magnitude = value < 0n ? -value : value;
  const found: bigint[] = [];
  for (let trial = 1n; trial * trial <= magnitude; trial++) {
    if (magnitude % trial === 0n) {
      found.push(trial);
      const other = magnitude / trial;
      if (other !== trial) found.push(other);
    }
  }
  return found;
}

function squareSplit(value: bigint): [bigint, bigint] {
  if (value < 0n) throw new Error("negative discriminant");
  let square = 1n;
  let rest = value;
  for (let prime = 2n; prime * prime <= rest; prime++) {
    let count = 0n;
    while (rest % prime === 0n) {
      rest /= prime;
      count++;
    }
    if (count >= 2n) square *= prime ** (count / 2n);
    if (count % 2n === 1n) rest *= prime;
  }
  return [square, rest];
}

function factorInteger(coeffs: bigint[]): bigint[][] {
  let current = coeffs.slice();
  while (current.length > 1 && current[current.length - 1] === 0n) current.pop();
  if (current[current.length - 1] < 0n) current = current.map((coeff) => -coeff);
  const factors: bigint[][] = [];
  while (current.length > 1 && current[0] === 0n) {
    factors.push([0n, 1n]);
    current = current.slice(1);
  }
  let progressed = true;
  while (progressed && current.length > 2) {
    progressed = false;
    for (const divisor of divisors(current[0])) {
      for (const root of [divisor, -divisor]) {
        const quotient = divideLow(current, [-root, 1n]);
        if (!quotient) continue;
        factors.push([-root, 1n]);
        current = quotient;
        progressed = true;
        break;
      }
      if (progressed) break;
    }
  }
  factors.push(...splitQuadratic(current));
  return factors;
}

function splitQuadratic(coeffs: bigint[]): bigint[][] {
  if (coeffs.length <= 3) return [coeffs];
  if (coeffs[coeffs.length - 1] !== 1n) return [coeffs];
  for (const divisor of divisors(coeffs[0])) {
    for (const constant of [divisor, -divisor]) {
      for (let linear = -80n; linear <= 80n; linear++) {
        const factor = [constant, linear, 1n];
        const quotient = divideLow(coeffs, factor);
        if (!quotient || quotient[quotient.length - 1] !== 1n) continue;
        return [...splitQuadratic(factor), ...splitQuadratic(quotient)];
      }
    }
  }
  return [coeffs];
}

class Fld {
  readonly a: Frac;
  readonly b: Frac;

  constructor(a: Frac, b: Frac) {
    this.a = a;
    this.b = b;
  }

  static q(n: bigint | Frac = 0n, s: bigint | Frac = 0n): Fld {
    return new Fld(n instanceof Frac ? n : new Frac(n), s instanceof Frac ? s : new Frac(s));
  }

  add(o: Fld): Fld {
    return new Fld(this.a.add(o.a), this.b.add(o.b));
  }

  sub(o: Fld): Fld {
    return new Fld(this.a.sub(o.a), this.b.sub(o.b));
  }

  neg(): Fld {
    return new Fld(this.a.neg(), this.b.neg());
  }

  mul(o: Fld): Fld {
    return new Fld(this.a.mul(o.a).add(new Frac(5n).mul(this.b).mul(o.b)), this.a.mul(o.b).add(this.b.mul(o.a)));
  }

  div(o: Fld): Fld {
    const norm = o.a.mul(o.a).sub(new Frac(5n).mul(o.b).mul(o.b));
    if (norm.isZero()) throw new Error("division by zero in Q(√5)");
    const num = this.mul(new Fld(o.a, o.b.neg()));
    return new Fld(num.a.div(norm), num.b.div(norm));
  }

  isZero(): boolean {
    return this.a.isZero() && this.b.isZero();
  }

  eq(o: Fld): boolean {
    return this.a.n === o.a.n && this.a.d === o.a.d && this.b.n === o.b.n && this.b.d === o.b.d;
  }
}

function intMatMul(left: bigint[][], right: bigint[][]): bigint[][] {
  const n = left.length;
  return left.map((row) =>
    right[0].map((_, col) => row.reduce((sum, entry, k) => sum + entry * right[k][col], 0n)),
  );
}

function intMatAdd(left: bigint[][], right: bigint[][], scale = 1n): bigint[][] {
  return left.map((row, i) => row.map((entry, j) => entry + scale * right[i][j]));
}

function applyQuadratic(constant: bigint, linear: bigint, matrix: bigint[][]): bigint[][] {
  const square = intMatMul(matrix, matrix);
  const n = matrix.length;
  return square.map((row, i) =>
    row.map((entry, j) => entry + linear * matrix[i][j] + (i === j ? constant : 0n)),
  );
}

function nullBasis(source: Fld[][]): Fld[][] {
  const rows = source.map((row) => row.map((entry) => new Fld(entry.a, entry.b)));
  const height = rows.length;
  const width = rows[0].length;
  const pivotCol: number[] = [];
  let pivotRow = 0;
  for (let col = 0; col < width && pivotRow < height; col++) {
    let selected = -1;
    for (let row = pivotRow; row < height; row++) {
      if (!rows[row][col].isZero()) {
        selected = row;
        break;
      }
    }
    if (selected < 0) continue;
    [rows[pivotRow], rows[selected]] = [rows[selected], rows[pivotRow]];
    const pivot = rows[pivotRow][col];
    for (let col2 = col; col2 < width; col2++) rows[pivotRow][col2] = rows[pivotRow][col2].div(pivot);
    for (let row = 0; row < height; row++) {
      if (row === pivotRow || rows[row][col].isZero()) continue;
      const factor = rows[row][col];
      for (let col2 = col; col2 < width; col2++) rows[row][col2] = rows[row][col2].sub(factor.mul(rows[pivotRow][col2]));
    }
    pivotCol.push(col);
    pivotRow++;
  }
  const used = new Set(pivotCol);
  const basis: Fld[][] = [];
  for (let col = 0; col < width; col++) {
    if (used.has(col)) continue;
    const vector = Array.from({ length: width }, () => Fld.q());
    vector[col] = Fld.q(1n);
    for (let index = 0; index < pivotCol.length; index++) vector[pivotCol[index]] = rows[index][col].neg();
    basis.push(vector);
  }
  return basis;
}

function matVec(matrix: bigint[][], vector: Fld[]): Fld[] {
  return matrix.map((row) => row.reduce((sum, entry, index) => sum.add(vector[index].mul(Fld.q(entry))), Fld.q()));
}

function eigenvalueAlong(matrix: bigint[][], vector: Fld[]): Fld {
  const image = matVec(matrix, vector);
  for (let index = 0; index < vector.length; index++) {
    if (vector[index].isZero()) continue;
    const value = image[index].div(vector[index]);
    for (let other = 0; other < vector.length; other++) {
      if (!image[other].eq(value.mul(vector[other]))) throw new Error("class matrix did not act by a scalar");
    }
    return value;
  }
  throw new Error("zero eigenvector");
}

function integerSquare(value: bigint): bigint | null {
  if (value < 0n) return null;
  let lo = 0n;
  let hi = value;
  while (lo < hi) {
    const mid = (lo + hi + 1n) >> 1n;
    if (mid * mid <= value) lo = mid;
    else hi = mid - 1n;
  }
  return lo * lo === value ? lo : null;
}

type Irrep = { degree: bigint; omega: Fld[]; character: Fld[]; lambda: Alg };

function charactersOf(elements: Quat[], classes: Quat[][], classOf: Map<string, number>, edgeClass: number): Irrep[] {
  const count = classes.length;
  const reps = classes.map((members) => members[0]);
  const structure = Array.from({ length: count }, () => Array.from({ length: count }, () => Array.from({ length: count }, () => 0n)));
  for (let i = 0; i < count; i++) {
    for (let j = 0; j < count; j++) {
      for (const left of classes[i]) {
        for (const right of classes[j]) {
          const product = qmul(left, right);
          const slot = classOf.get(key(product));
          if (slot === undefined || !same(product, reps[slot])) continue;
          structure[i][j][slot] += 1n;
        }
      }
    }
  }
  const matrices = structure.map((slice) =>
    Array.from({ length: count }, (_, row) => Array.from({ length: count }, (_, col) => slice[col][row])),
  );
  const trials: bigint[][] = [
    [1n, 2n, 3n, 4n, 5n, 6n, 7n, 8n, 9n],
    [1n, 0n, 0n, 0n, 0n, 0n, 0n, 0n, 0n],
    [0n, 1n, 0n, 0n, 0n, 0n, 0n, 0n, 0n],
    [1n, 1n, 1n, 1n, 1n, 1n, 1n, 1n, 1n],
    [1n, 3n, 5n, 7n, 9n, 2n, 4n, 6n, 8n],
    [2n, 3n, 5n, 7n, 11n, 13n, 17n, 19n, 23n],
  ];
  let split: { matrix: bigint[][]; factors: bigint[][] } | null = null;
  for (const weights of trials) {
    let combined = matrices[0].map((row) => row.map(() => 0n));
    weights.forEach((weight, index) => {
      combined = intMatAdd(combined, matrices[index], weight);
    });
    const factors = factorInteger(characteristic(combined));
    const keys = factors.map((factor) => factor.join(","));
    const degrees = factors.reduce((sum, factor) => sum + factor.length - 1, 0);
    if (degrees === count && factors.every((factor) => factor.length <= 3) && new Set(keys).size === keys.length) {
      split = { matrix: combined, factors };
      break;
    }
  }
  if (!split) throw new Error("class algebra did not split into linears and quadratics");
  const irreps: Irrep[] = [];
  for (const factor of split.factors) {
    const spaces: Fld[][] = [];
    if (factor.length === 2) {
      const root = -factor[0];
      const shifted = split.matrix.map((row, i) => row.map((entry, j) => Fld.q(i === j ? entry - root : entry)));
      spaces.push(...nullBasis(shifted));
      if (spaces.length !== 1) throw new Error(`rational class eigenvalue has multiplicity ${spaces.length}`);
    } else {
      const kernel = applyQuadratic(factor[0], factor[1], split.matrix).map((row) => row.map((entry) => Fld.q(entry)));
      const basis = nullBasis(kernel);
      if (basis.length !== 2) throw new Error(`quadratic class block has dimension ${basis.length}`);
      const coordinates = [0, 1].map((col) => express(basis, matVec(split.matrix, basis[col])));
      const trace = coordinates[0][0].add(coordinates[1][1]);
      const det = coordinates[0][0].mul(coordinates[1][1]).sub(coordinates[1][0].mul(coordinates[0][1]));
      const disc = trace.mul(trace).sub(Fld.q(4n).mul(det));
      const halfTrace = trace.div(Fld.q(2n));
      const step = sqrtFld(disc).div(Fld.q(2n));
      for (const sign of [1n, -1n]) {
        const theta = halfTrace.add(sign > 0n ? step : step.neg());
        spaces.push(liftEigenvector(basis, coordinates, theta));
      }
    }
    for (const vector of spaces) {
      const omega = matrices.map((matrix) => eigenvalueAlong(matrix, vector));
      let sum = Fld.q();
      omega.forEach((value, index) => {
        sum = sum.add(value.mul(value).div(Fld.q(BigInt(classes[index].length))));
      });
      const ratio = Fld.q(120n).div(sum);
      if (!ratio.b.isZero()) throw new Error("irrep degree left Q");
      const degreeSquaredNum = ratio.a.n;
      const degreeSquaredDen = ratio.a.d;
      if (degreeSquaredDen !== 1n || integerSquare(degreeSquaredNum) === null) {
        throw new Error(`degree ratio ${ratio.a.n}/${ratio.a.d} + ${ratio.b.n}/${ratio.b.d}√5`);
      }
      const degree = integerSquare(degreeSquaredNum)!;
      const character = omega.map((value, index) => value.mul(Fld.q(degree)).div(Fld.q(BigInt(classes[index].length))));
      const edge = character[edgeClass].div(Fld.q(degree));
      irreps.push({ degree, omega, character, lambda: subtractFromOne(edge) });
    }
  }
  if (irreps.length !== count) throw new Error(`found ${irreps.length} irreps, expected ${count}`);
  return irreps;
}

function express(basis: Fld[][], vector: Fld[]): Fld[] {
  const aug = vector.map((_, index) => [...basis.map((column) => column[index]), vector[index]]);
  return rrefAugment(aug);
}

function liftEigenvector(basis: Fld[][], coordinates: Fld[][], theta: Fld): Fld[] {
  const diagonal = coordinates[0][0];
  const right = coordinates[1][0];
  const below = coordinates[0][1];
  if (!right.isZero()) {
    const weight = theta.sub(diagonal);
    return basis[0].map((entry, index) => entry.mul(right).add(basis[1][index].mul(weight)));
  }
  if (!below.isZero()) {
    const weight = theta.sub(coordinates[1][1]);
    return basis[0].map((entry, index) => entry.mul(weight).add(basis[1][index].mul(below)));
  }
  return theta.eq(diagonal) ? basis[0] : basis[1];
}

function rrefAugment(rows: Fld[][]): Fld[] {
  const height = rows.length;
  const width = rows[0].length - 1;
  let pivotRow = 0;
  const value = Array.from({ length: width }, () => Fld.q());
  const pivotCol: number[] = [];
  for (let col = 0; col < width && pivotRow < height; col++) {
    let selected = -1;
    for (let row = pivotRow; row < height; row++) {
      if (!rows[row][col].isZero()) {
        selected = row;
        break;
      }
    }
    if (selected < 0) continue;
    [rows[pivotRow], rows[selected]] = [rows[selected], rows[pivotRow]];
    const pivot = rows[pivotRow][col];
    for (let col2 = col; col2 < width + 1; col2++) rows[pivotRow][col2] = rows[pivotRow][col2].div(pivot);
    for (let row = 0; row < height; row++) {
      if (row === pivotRow || rows[row][col].isZero()) continue;
      const factor = rows[row][col];
      for (let col2 = col; col2 < width + 1; col2++) rows[row][col2] = rows[row][col2].sub(factor.mul(rows[pivotRow][col2]));
    }
    pivotCol.push(col);
    pivotRow++;
  }
  for (let index = 0; index < pivotCol.length; index++) value[pivotCol[index]] = rows[index][width];
  return value;
}

function sqrtFld(value: Fld): Fld {
  if (!value.b.isZero()) throw new Error("square root of a non-rational class discriminant");
  if (value.a.n < 0n) throw new Error("negative class discriminant");
  const [square, radical] = squareSplit(value.a.n * value.a.d);
  if (radical === 1n) return Fld.q(new Frac(square, value.a.d));
  if (radical !== 5n) throw new Error(`class discriminant radical ${radical} is outside Q(√5)`);
  return Fld.q(new Frac(0n), new Frac(square, value.a.d));
}

function subtractFromOne(value: Fld): Alg {
  const gap = Fld.q(1n).sub(value);
  return alg(gap.a.n * gap.b.d, gap.b.n * gap.a.d, gap.a.d * gap.b.d);
}

let cached: string | null = null;

export function threadReport(): string {
  if (cached) return cached;
  if (!goldenFamily()) throw new Error("golden-ratio family failed");
  if (orderOf(GOLDEN) !== 5 || !isUnit(GOLDEN)) throw new Error("golden icosian is not a unit of order 5");
  const elements = closeGroup([...tetrahedral(), GOLDEN]);
  if (elements.length !== 120) throw new Error(`|2I| = ${elements.length}, expected 120`);
  if (!elements.every(isUnit)) throw new Error("2I contains a non-unit");
  const keys = new Set(elements.map(key));
  for (const left of elements) {
    if (!keys.has(key(qinv(left)))) throw new Error("2I is not closed under inverse");
    for (const right of elements) if (!keys.has(key(qmul(left, right)))) throw new Error("2I is not closed under product");
  }
  const classes = classesOf(elements);
  if (classes.length !== 9) throw new Error(`2I has ${classes.length} conjugacy classes, expected 9`);
  const sizes = classes.map((item) => item.length);
  if (sizes.reduce((sum, size) => sum + size, 0) !== 120) throw new Error("class sizes do not cover 2I");
  const classOf = new Map<string, number>();
  classes.forEach((members, index) => members.forEach((element) => classOf.set(key(element), index)));
  const adjacency: number[][] = Array.from({ length: 120 }, () => []);
  for (let i = 0; i < 120; i++) {
    for (let j = i + 1; j < 120; j++) {
      const real = qmul(qinv(elements[i]), elements[j])[0];
      if (real[0] === 1 && real[1] === 1) {
        adjacency[i].push(j);
        adjacency[j].push(i);
      }
    }
  }
  if (adjacency.some((row) => row.length !== 12)) throw new Error("a 600-cell vertex does not have 12 neighbours");
  const edges = adjacency.reduce((sum, row) => sum + row.length, 0) / 2;
  const adjacent = adjacency.map((row) => new Set(row));
  let triangleMarks = 0;
  for (let i = 0; i < 120; i++) {
    const row = adjacency[i];
    for (let a = 0; a < row.length; a++) {
      for (let b = a + 1; b < row.length; b++) if (adjacent[row[a]].has(row[b])) triangleMarks += 1;
    }
  }
  if (triangleMarks % 3 !== 0) throw new Error("triangle count is not divisible by 3");
  const faces = triangleMarks / 3;
  let cellMarks = 0;
  for (let i = 0; i < 120; i++) {
    const row = adjacency[i];
    for (let a = 0; a < row.length; a++) {
      for (let b = a + 1; b < row.length; b++) {
        const j = row[a];
        const l = row[b];
        if (j > i || l > i || !adjacent[j].has(l)) continue;
        let commons = 0;
        for (const vertex of adjacency[i]) {
          if (vertex !== j && vertex !== l && adjacent[j].has(vertex) && adjacent[l].has(vertex)) commons += 1;
        }
        if (commons !== 2) throw new Error("a triangular face does not meet exactly two tetrahedra");
        cellMarks += 1;
      }
    }
  }
  if (cellMarks !== faces) throw new Error("face count changed between passes");
  const cells = (faces * 2) / 4;
  const euler = 120 - edges + faces - cells;
  if (euler !== 0) throw new Error(`Euler characteristic ${euler}, expected 0`);
  const edgeClass = classOf.get(
    key(elements.find((element) => element[0][0] === 1 && element[0][1] === 1)!),
  )!;
  const generators = classes[edgeClass];
  if (generators.length !== 12) throw new Error("the edge class is not the 12-neighbour class");
  const irreps = charactersOf(elements, classes, classOf, edgeClass).sort((left, right) => {
    if (left.degree !== right.degree) return left.degree < right.degree ? -1 : 1;
    return cmpAlg(left.lambda, right.lambda);
  });
  const degreeSum = irreps.reduce((sum, irrep) => sum + irrep.degree * irrep.degree, 0n);
  if (degreeSum !== 120n) throw new Error(`sum of squares of degrees is ${degreeSum}`);
  for (let rho = 0; rho < irreps.length; rho++) {
    for (let sigma = 0; sigma < irreps.length; sigma++) {
      let inner = Fld.q();
      for (let slot = 0; slot < classes.length; slot++) {
        inner = inner.add(Fld.q(BigInt(classes[slot].length)).mul(irreps[rho].character[slot]).mul(irreps[sigma].character[slot]));
      }
      const expected = rho === sigma ? Fld.q(120n) : Fld.q();
      if (!inner.eq(expected)) throw new Error("character orthogonality failed");
    }
  }
  if (!generators.every((element) => generators.some((other) => same(other, qinv(element))))) {
    throw new Error("the generating class is not inverse-closed");
  }
  const counts = classes.map((members) => {
    const tally = Array.from({ length: 9 }, () => 0);
    for (const step of generators) {
      const image = classOf.get(key(qmul(members[0], step)));
      if (image === undefined) throw new Error("product left 2I");
      tally[image] += 1;
    }
    return tally;
  });
  const operator = counts.map((row, i) => row.map((count, j) => (i === j ? 12n : 0n) - BigInt(count)));
  const polynomial = characteristic(operator);
  const factors = factorInteger(polynomial);
  const eigenvalues = factors.flatMap(rootsOf).filter(positive).sort(cmpAlg);
  const fromCharacters = irreps
    .map((irrep) => {
      const scaled = Fld.q(12n).mul(Fld.q(new Frac(irrep.lambda.a, irrep.lambda.d), new Frac(irrep.lambda.b, irrep.lambda.d)));
      return alg(scaled.a.n * scaled.b.d, scaled.b.n * scaled.a.d, scaled.a.d * scaled.b.d);
    })
    .filter(positive)
    .sort(cmpAlg);
  if (fromCharacters.length !== eigenvalues.length || fromCharacters.some((value, index) => cmpAlg(value, eigenvalues[index]) !== 0)) {
    throw new Error("character eigenvalues do not match the Laplacian polynomial");
  }
  const least = eigenvalues[0];
  const gap = alg(least.a, least.b, least.d * 12n);
  const expected = alg(3n, -1n, 4n);
  if (cmpAlg(gap, expected) !== 0) throw new Error(`computed gap ${show(gap)} is not (3 - √5)/4`);
  cached = [
    "one thread   finite subgroup 2I < SU(2)   continuum Yang–Mills = not claimed",
    "  arithmetic = exact icosian integers   float spectrum = refused",
    "",
    "[0] GOLDEN FAMILY",
    "  Cassini, Lucas–Cassini, trace, Zeckendorf   PASS",
    "",
    "[1] GOLDEN ICOSIAN",
    "  g = ((−1,1), (0,0), (−1,−1), (2,0)) = (1/(2φ), 0, −φ/2, 1/2)",
    "  unit = True    order = 5",
    "",
    "[2] BINARY ICOSAHEDRAL GROUP",
    "  |2I| = 120",
    "  units = True    closed under product = True    closed under inverse = True",
    "",
    "[3] POINCARE HOMOLOGY SPHERE",
    `  conjugacy classes = 9    sizes = ${[...sizes].sort((a, b) => a - b).join(" ")}`,
    "  sum = 120    π₁ = 2I",
    "",
    "[4] 600-CELL",
    `  V = 120    E = ${edges}    F = ${faces}    C = ${cells}`,
    "  Euler = 0",
    "  each vertex has 12 neighbours at real part (1+√5)/4 = φ/2",
    "",
    "[5] CHARACTER TABLE",
    "  structure constants of the class algebra, then the common eigenvalues",
    `  dimensions = ${irreps.map((irrep) => irrep.degree.toString()).join(" ")}`,
    "  sum d^2 = 120",
    "  orthogonality = True",
    "",
    "[6] LAPLACE EIGENVALUES",
    "  λ = 1 - χ(edge)/d, matched to the roots of the characteristic polynomial",
    ...irreps.map((irrep) => `  d = ${irrep.degree}    λ = ${show(irrep.lambda)}`),
    "  multiplicity of λ on C[2I] = d^2",
    "",
    "[7] CLASS-FUNCTION LAPLACIAN",
    "  H = I - (1/12) sum R_s on class functions, s running over the edge class",
    `  characteristic polynomial of 12H = ${polyToString(polynomial)}`,
    `  factors = ${factors.map(polyToString).join(" · ")}`,
    `  positive eigenvalues of 12H = ${eigenvalues.map(show).join(", ")}`,
    "  least positive = 9 - 3√5, because 81 > 45 and it is below every other root",
    "  Δ = (9 - 3√5)/12 = (3 - √5)/4",
    "  (3 - √5)/4 = 1 - (1 + √5)/4 = 1 - φ/2",
    "  (3 - √5)/4 = 1/(3 + √5) = 1/(2φ²)",
    "  the gap is the least positive root, not a stored constant",
    "",
    "[8] REFUSED",
    "  a decimal eigenvalue",
    "  recognising an algebraic number by a float tolerance",
    "  continuum Yang-Mills on R^4",
  ].join("\n");
  return cached;
}
