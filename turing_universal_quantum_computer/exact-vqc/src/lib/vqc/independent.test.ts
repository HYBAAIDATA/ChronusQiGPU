/** Checks recomputed from the definitions, not from the report text.

A string match against a sentence this file also printed would let one
wrong formula confirm itself. These oracles are the recurrence, the
Grover mean, integer gcd, polynomial division, and an exhaustive bijection.
*/

import assert from "node:assert/strict";
import { test } from "node:test";
import { Exact, Frac, HALF_SQRT2, ONE, Q2, ZERO } from "./algebra.ts";
import { algebraReport } from "./algebra-family.ts";
import { cureReport, foldReport } from "./custody.ts";
import { advancesReport, hendrixReport } from "./hendrix.ts";
import { finaleReport } from "./finale.ts";
import { rankReport } from "./rank.ts";
import { ontologyReport } from "./ontology.ts";
import { signalReport } from "./signal.ts";
import { storeReport } from "./store.ts";
import { Triad, triadScript } from "./triad.ts";
import { keepData } from "./six.ts";
import { sha256Of } from "./sha256.ts";
import { fibonacci, lucas } from "./lucas-scale.ts";
import { qftReport, shorReport } from "./classics.ts";

function recurrence(length: number): { fib: bigint[]; lucas: bigint[] } {
  const fib = [0n, 1n];
  const luc = [2n, 1n];
  for (let n = 2; n < length; n++) {
    fib.push(fib[n - 1] + fib[n - 2]);
    luc.push(luc[n - 1] + luc[n - 2]);
  }
  return { fib, lucas: luc };
}

function zeckendorf(fib: bigint[], payload: bigint): number[] {
  let highest = fib.length - 1;
  while (highest > 2 && fib[highest] > payload) highest -= 1;
  const indices: number[] = [];
  let remaining = payload;
  for (let index = highest; index >= 2 && remaining > 0n; index--) {
    if (fib[index] <= remaining) {
      indices.push(index);
      remaining -= fib[index];
    }
  }
  assert.equal(remaining, 0n);
  return indices;
}

test("doubling matches the Lucas and Fibonacci recurrences", () => {
  const { fib, lucas: luc } = recurrence(81);
  assert.deepEqual(fib.slice(0, 8), [0n, 1n, 1n, 2n, 3n, 5n, 8n, 13n]);
  assert.deepEqual(luc.slice(0, 6), [2n, 1n, 3n, 4n, 7n, 11n]);
  for (let n = 0; n <= 80; n++) {
    assert.equal(fibonacci(n), fib[n], `F_${n}`);
    assert.equal(lucas(n), luc[n], `L_${n}`);
  }
});

test("Cassini is computed from the sequence, and it stores L_15", () => {
  const { fib, lucas: luc } = recurrence(20);
  for (let n = 1; n <= 16; n++) {
    const sign = n % 2 === 0 ? 1n : -1n;
    assert.equal(fib[n + 1] * fib[n - 1] - fib[n] * fib[n], sign);
    assert.equal(luc[n] * luc[n] - 5n * fib[n] * fib[n], 4n * sign);
  }
  const code = zeckendorf(fib, luc[15]);
  assert.deepEqual(code, [16, 14]);
  assert.equal(fib[16] + fib[14], luc[15]);
  assert.equal(fib[16] * fib[14] - fib[15] * fib[15], -1n);
  const fold = foldReport();
  assert.match(fold, /F_16 \+ F_14/);
  assert.match(fold, new RegExp(`limbs = ${fib[16]} \\+ ${fib[14]}`));
});

test("Binet in Z[φ] is the ring power, not a decimal", () => {
  const mul = (p: { a: bigint; b: bigint }, q: { a: bigint; b: bigint }) => ({
    a: p.a * q.a + p.b * q.b,
    b: p.a * q.b + p.b * q.a + p.b * q.b,
  });
  let value = { a: 1n, b: 0n };
  const phi = { a: 0n, b: 1n };
  for (let n = 1; n <= 15; n++) value = mul(value, phi);
  const { fib } = recurrence(16);
  assert.equal(value.a, fib[14]);
  assert.equal(value.b, fib[15]);
  assert.match(foldReport(), new RegExp(`φ\\^15 = ${fib[14]} \\+ ${fib[15]}φ`));
  assert.doesNotMatch(foldReport(), /\d\.\d/);
});

function groverOnce(total: bigint, marked: bigint, amplitude: Frac, other: Frac): [Frac, Frac] {
  const flipped = amplitude.neg();
  const mean = new Frac(marked).mul(flipped).add(new Frac(total - marked).mul(other)).div(new Frac(total));
  return [new Frac(2n).mul(mean).sub(flipped), new Frac(2n).mul(mean).sub(other)];
}

function walkPeak(total: bigint, marked: bigint): { k: number; probability: Frac } {
  let amplitude = new Frac(1n);
  let other = new Frac(1n);
  let probability = new Frac(marked).div(new Frac(total));
  let k = 0;
  for (;;) {
    const [nextAmplitude, nextOther] = groverOnce(total, marked, amplitude, other);
    const next = new Frac(marked).mul(nextAmplitude).mul(nextAmplitude).div(new Frac(total));
    if (next.cmp(probability) <= 0) return { k, probability };
    amplitude = nextAmplitude;
    other = nextOther;
    probability = next;
    k += 1;
    if (k > 200) throw new Error("the independent walk did not turn down");
  }
}

test("the Grover mean, on the full register, anchors the folded walk", () => {
  const scale = new Exact(new Q2(0, new Frac(1n, 4n)));
  let amplitudes = Array.from({ length: 8 }, () => scale);
  const diffuse = (state: Exact[]) => {
    const sum = state.reduce((total, amplitude) => total.add(amplitude), ZERO);
    const mean = sum.mul(new Exact(new Q2(new Frac(1n, 8n))));
    return state.map((amplitude) => mean.add(mean).sub(amplitude));
  };
  for (let step = 0; step < 2; step++) {
    amplitudes[7] = amplitudes[7].neg();
    amplitudes = diffuse(amplitudes);
  }
  const marked = amplitudes[7].normSq();
  assert.equal(marked.q.isZero(), true);
  assert.equal(marked.p.toString(), "121/128");
  const folded = walkPeak(8n, 1n);
  assert.equal(folded.k, 2);
  assert.equal(folded.probability.toString(), "121/128");
  assert.equal(walkPeak(4n, 1n).probability.toString(), "1");
});

test("doubling is checked against the walk, and a sine is not the oracle", () => {
  const walked = walkPeak(10000n, 1n);
  assert.equal(walked.k, 78);
  assert.notEqual(walked.k, 100);
  const cure = cureReport();
  const escaped = walked.probability.toString().replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  assert.match(cure, new RegExp(`k = ${walked.k}`));
  assert.match(cure, new RegExp(`P\\(marked\\) = ${escaped}`));
  assert.match(cure, /a sine is not used/);
  assert.doesNotMatch(cure, /\d\.\d/);
});

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

test("Shor's factorisation of 15 is the order and the gcd", () => {
  let order = 0n;
  for (let exp = 1n; exp <= 15n; exp++) {
    if (modPow(7n, exp, 15n) === 1n) {
      order = exp;
      break;
    }
  }
  assert.equal(order, 4n);
  const square = modPow(7n, order / 2n, 15n);
  const left = gcd(square - 1n, 15n);
  const right = gcd(square + 1n, 15n);
  assert.deepEqual([left, right].sort((a, b) => (a < b ? -1 : 1)), [3n, 5n]);
  assert.equal(left * right, 15n);
  const report = shorReport(15n);
  assert.match(report, new RegExp(`15 = ${left} × ${right}`));
  assert.match(report, /order of 7 modulo 15 = 4/);
  for (const phase of [1, 3, 5, 7]) assert.match(report, new RegExp(`P\\(phase = ${phase}\\) = 0`));
  for (const phase of [0, 2, 4, 6]) assert.match(report, new RegExp(`P\\(phase = ${phase}\\) = 1/4`));
});

test("the period-2 QFT peaks only at 0 and 4", () => {
  const root = new Exact(HALF_SQRT2, HALF_SQRT2);
  const powers = [ONE];
  for (let i = 1; i < 8; i++) powers.push(powers[i - 1].mul(root));
  const half = new Exact(new Q2(new Frac(1n, 2n)));
  const scale = new Exact(new Q2(0, new Frac(1n, 4n)));
  const support: number[] = [];
  for (let j = 0; j < 8; j++) {
    let sum = ZERO;
    for (const k of [0, 2, 4, 6]) sum = sum.add(half.mul(powers[(j * k) % 8]));
    const probability = sum.mul(scale).normSq();
    assert.equal(probability.q.isZero(), true);
    if (!probability.p.isZero()) {
      support.push(j);
      assert.equal(probability.p.toString(), "1/2");
    }
  }
  assert.deepEqual(support, [0, 4]);
  const report = qftReport(3);
  assert.match(report, /P\(0\) = 1\/2/);
  assert.match(report, /P\(4\) = 1\/2/);
  assert.doesNotMatch(report, /P\(2\)/);
  assert.match(qftReport(4), /REFUSED/);
});

function modPlastic(dividend: bigint[]): bigint[] {
  const current = dividend.slice();
  const divisor = [-1n, -1n, 0n, 1n];
  while (current.length >= 4) {
    const lead = current[current.length - 1];
    const degree = current.length - 4;
    for (let i = 0; i < divisor.length; i++) current[degree + i] -= lead * divisor[i];
    current.pop();
  }
  while (current.length && current[current.length - 1] === 0n) current.pop();
  return current;
}

test("ρ^5 = ρ^2 + 1 is a false reading of x^3 - x - 1", () => {
  assert.deepEqual(modPlastic([-1n, -1n, -1n, 0n, 0n, 1n]), []);
  assert.deepEqual(modPlastic([-1n, 0n, -1n, 0n, 0n, 1n]), [0n, 1n]);
  const report = algebraReport();
  assert.match(report, /ρ\^5 = ρ\^2 \+ 1 {4}REFUTED/);
  assert.match(report, /ρ\^5 = ρ\^2 \+ ρ \+ 1 follows/);
});

test("Hendrix is a bijection, and the uniform expectation does not move", () => {
  const count = 30n;
  let stride = lucas(76) % count;
  if (stride === 0n) stride = 1n;
  while (gcd(stride, count) !== 1n) stride = (stride + 1n) % count || 1n;
  const image = new Set<bigint>();
  for (let i = 0n; i < count; i++) image.add((i * stride) % count);
  assert.equal(image.size, Number(count));
  const report = hendrixReport();
  assert.match(report, new RegExp(`stride = ${stride}`));
  assert.match(report, /quantum_claim = False/);
  assert.match(report, /E\[probes\] = 31\/2/);
  assert.match(report, /ratio = 1/);
  assert.match(report, /630x = refused/);
  assert.doesNotMatch(report, /\d\.\d/);
});

test("the path Laplacian gap is the determinant, not a decimal eigenvalue", () => {
  const at = (lambda: bigint) => {
    const matrix = [
      [lambda - 1n, 1n, 0n],
      [1n, lambda - 2n, 1n],
      [0n, 1n, lambda - 1n],
    ];
    return (
      matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1]) -
      matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0]) +
      matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
    );
  };
  for (const root of [0n, 1n, 3n]) assert.equal(at(root), 0n);
  assert.notEqual(at(2n), 0n);
  const report = advancesReport();
  assert.match(report, /characteristic polynomial = λ\(λ−1\)\(λ−3\)/);
  assert.match(report, /gap = 1/);
  assert.match(report, /hardware = not a parameter/);
  assert.match(report, /product state = False/);
  assert.doesNotMatch(report, /\d\.\d/);
});

test("1/√5 is not the Grover peak", () => {
  const lattice = (total: bigint) => {
    let m = 0n;
    while (5n * (m + 1n) * (m + 1n) <= total) m += 1n;
    return m;
  };
  const at = (total: bigint, steps: number) => {
    let amplitude = new Frac(1n);
    let other = new Frac(1n);
    for (let step = 0; step < steps; step++) [amplitude, other] = groverOnce(total, 1n, amplitude, other);
    return new Frac(1n).mul(amplitude).mul(amplitude).div(new Frac(total));
  };
  const ratios: string[] = [];
  for (const total of [4n, 100n, 1000n, 10000n]) {
    const peak = walkPeak(total, 1n);
    const m = lattice(total);
    assert.ok(m < BigInt(peak.k));
    if (m > 0n) {
      assert.equal(at(total, Number(m)).cmp(peak.probability) < 0, true);
      ratios.push(new Frac(m, BigInt(peak.k)).toString());
    }
    const report = finaleReport();
    assert.match(report, new RegExp(`N = ${total} {4}k = ${peak.k} {4}5m² ≤ N gives m = ${m}`));
  }
  assert.equal(new Set(ratios).size, ratios.length);
  const report = finaleReport();
  assert.match(report, /verdict = REFUSED/);
  assert.match(report, /discriminant is −4\(N−1\)/);
  assert.match(report, /discriminant is 20/);
  assert.match(report, /not the same/);
  assert.match(report, /a decimal ratio of π\/4 to 1\/√5 is refused/);
  assert.doesNotMatch(report, /\d\.\d/);
});

test("the degrees are the rank of the power basis, not the printed sentence", () => {
  const evalAt = (poly: bigint[], x: bigint) => poly.reduce((total, coeff) => total * x + coeff, 0n);
  const tetranacci = [1n, -1n, -1n, -1n, -1n];
  assert.notEqual(evalAt(tetranacci, 1n), 0n);
  assert.notEqual(evalAt(tetranacci, -1n), 0n);
  const integerSquare = (n: bigint) => {
    if (n < 0n) return null;
    let x = 0n;
    while (x * x < n) x += 1n;
    return x * x === n ? x : null;
  };
  let factored = false;
  for (const q of [1n, -1n]) {
    const s = -1n / q;
    const product = -1n - q - s;
    const root = integerSquare(1n - 4n * product);
    if (root === null || (-1n + root) % 2n !== 0n) continue;
    const p = (-1n + root) / 2n;
    if (p * s + q * (-1n - p) === -1n) factored = true;
  }
  assert.equal(factored, false);
  const rankOf = (rows: Frac[][]) => {
    const a = rows.map((row) => row.map((entry) => new Frac(entry.n, entry.d)));
    let rank = 0;
    let col = 0;
    const width = a[0].length;
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
  };
  const degree = (dim: number, apply: (vector: Frac[]) => Frac[]) => {
    let vector = Array.from({ length: dim }, (_, index) => new Frac(index === 0 ? 1n : 0n));
    const rows = Array.from({ length: dim }, () => [] as Frac[]);
    let seen = 0;
    for (let power = 0; power <= dim; power++) {
      vector.forEach((entry, index) => rows[index].push(entry));
      const current = rankOf(rows);
      if (current === seen) return power;
      seen = current;
      vector = apply(vector);
    }
    throw new Error("the test basis had no relation");
  };
  const silverGolden = degree(4, (vector) => {
    const [a, b, c, d] = vector;
    const by2 = [new Frac(2n).mul(b), a, new Frac(2n).mul(d), c];
    const by5 = [new Frac(5n).mul(c), new Frac(5n).mul(d), a, b];
    return by2.map((entry, index) => entry.add(by5[index]));
  });
  const plasticGolden = degree(6, (vector) => {
    const [a, b, c, d, e, f] = vector;
    const byPhi = [b, a.add(b), d, c.add(d), f, e.add(f)];
    const byRho = [e, f, a.add(e), b.add(f), c, d];
    return byPhi.map((entry, index) => entry.add(byRho[index]));
  });
  assert.equal(silverGolden, 4);
  assert.equal(plasticGolden, 6);
  let primitive = false;
  for (let A = 0; A < 5; A++) {
    for (let C = 0; C < 5; C++) {
      if ((3 * A * A - C * C) % 5 === 0 && (A !== 0 || C !== 0)) primitive = true;
    }
  }
  assert.equal(primitive, false);
  assert.equal(-4n * 8n, -32n);
  const report = rankReport();
  assert.match(report, new RegExp(`computed degree of √2 \\+ √5 = ${silverGolden}`));
  assert.match(report, new RegExp(`computed degree of φ \\+ ρ = ${plasticGolden}`));
  assert.match(report, /10D = refused/);
  assert.match(report, /11D = refused/);
  assert.match(report, /E8 root lattice is not proved/);
  assert.match(report, /N = 9 was not the Grover obstruction/);
  assert.doesNotMatch(report, /\d\.\d/);
  const degrees = [2, 3, 4, silverGolden, plasticGolden, 8];
  assert.equal(degrees.includes(10), false);
  assert.equal(degrees.includes(11), false);
});

test("the order-5 cosine is golden and the order-8 cosine is not", () => {
  const mul = (p: { a: bigint; b: bigint }, q: { a: bigint; b: bigint }) => ({
    a: p.a * q.a + p.b * q.b,
    b: p.a * q.b + p.b * q.a + p.b * q.b,
  });
  const eta = { a: -1n, b: 1n };
  const square = mul(eta, eta);
  assert.equal(square.a + eta.a - 1n, 0n);
  assert.equal(square.b + eta.b, 0n);
  const det = (matrix: bigint[][]): bigint => {
    if (matrix.length === 1) return matrix[0][0];
    let total = 0n;
    for (let col = 0; col < matrix.length; col++) {
      const minor = matrix.slice(1).map((row) => row.filter((_, index) => index !== col));
      total += (col % 2 === 0 ? 1n : -1n) * matrix[0][col] * det(minor);
    }
    return total;
  };
  const resultant = det([
    [1n, -1n, -1n, 0n],
    [0n, 1n, -1n, -1n],
    [1n, 0n, -2n, 0n],
    [0n, 1n, 0n, -2n],
  ]);
  assert.notEqual(resultant, 0n);
  const report = ontologyReport();
  assert.match(report, /verdict = REFUSED/);
  assert.match(report, /η = φ − 1 = −1 \+ φ/);
  assert.match(report, new RegExp(`resultant of \\(x\\^2 − x − 1, x\\^2 − 2\\) = ${resultant}`));
  assert.match(report, /an amplitude of the QFT is not a golden integer/);
  assert.doesNotMatch(report, /\d\.\d/);
});

test("a Fibonacci window does not fold under the length-4 DFT", () => {
  const turn = (sample: bigint, power: number) => {
    const quadrant = ((power % 4) + 4) % 4;
    if (quadrant === 0) return { re: sample, im: 0n };
    if (quadrant === 1) return { re: 0n, im: sample };
    if (quadrant === 2) return { re: -sample, im: 0n };
    return { re: 0n, im: -sample };
  };
  const binsOf = (signal: bigint[]) =>
    [0, 1, 2, 3].map((bin) =>
      signal.reduce(
        (total, sample, index) => {
          const term = turn(sample, bin * index);
          return { re: total.re + term.re, im: total.im + term.im };
        },
        { re: 0n, im: 0n },
      ),
    );
  const occupied = (bins: { re: bigint; im: bigint }[]) => bins.filter((bin) => bin.re !== 0n || bin.im !== 0n).length;
  const fibonacci = [0n, 1n, 1n, 2n];
  assert.equal(occupied(binsOf(fibonacci)), 4);
  assert.equal(2n * 5n - 3n * 3n, 1n);
  const period = [1n, 0n, 1n, 0n];
  assert.equal(occupied(binsOf(period)), 2);
  assert.equal(period[3] === period[2] + period[1], false);
  const report = signalReport();
  assert.match(report, /verdict = SPLIT/);
  assert.match(report, /nonzero DFT bins = 4/);
  assert.match(report, /nonzero DFT bins = 2/);
  assert.match(report, /Cassini determinant F\(3\)F\(5\) − F\(4\)\^2 = 1/);
  assert.match(report, /neither one is better at the other's window/);
  assert.doesNotMatch(report, /\d\.\d/);
});

test("the prime address and the sunflower rank are not a Fourier bin count", () => {
  const modulus = (1n << 61n) - 1n;
  const lehmer = (exponent: number) => {
    const mersenne = (1n << BigInt(exponent)) - 1n;
    let state = 4n;
    for (let step = 0; step < exponent - 2; step++) state = (state * state - 2n) % mersenne;
    return state;
  };
  assert.equal(lehmer(7), 0n);
  assert.notEqual(lehmer(11), 0n);
  assert.equal(lehmer(61), 0n);
  const turn = (sample: bigint, power: number) => {
    const quadrant = ((power % 4) + 4) % 4;
    if (quadrant === 0) return { re: sample, im: 0n };
    if (quadrant === 1) return { re: 0n, im: sample };
    if (quadrant === 2) return { re: -sample, im: 0n };
    return { re: 0n, im: -sample };
  };
  const window = [0n, 1n, 1n, 2n];
  const bins = [0, 1, 2, 3].map((bin) =>
    window.reduce(
      (total, sample, index) => {
        const term = turn(sample, bin * index);
        return { re: total.re + term.re, im: total.im + term.im };
      },
      { re: 0n, im: 0n },
    ),
  );
  const kept = [bins[0], { re: 0n, im: 0n }, bins[2], { re: 0n, im: 0n }];
  const origin = kept.reduce(
    (total, bin, index) => {
      const term = turn(1n, -index);
      return { re: total.re + bin.re * term.re - bin.im * term.im, im: total.im + bin.re * term.im + bin.im * term.re };
    },
    { re: 0n, im: 0n },
  );
  assert.notEqual(origin.re, 0n);
  const fib = (n: number): bigint => (n < 2 ? BigInt(n) : fib(n - 1) + fib(n - 2));
  let remaining = 4n;
  let folded = 0n;
  for (let index = 6; index >= 2; index--) {
    const limb = fib(index);
    if (limb <= remaining) {
      folded += limb;
      remaining -= limb;
    }
  }
  assert.equal(folded, 4n);
  assert.equal(remaining, 0n);
  const chunk = 1n << 48n;
  assert.ok(chunk < modulus);
  let address = 1n;
  let factor = 2n;
  let cursor = chunk;
  while (cursor > 0n) {
    if (cursor & 1n) address = (address * factor) % modulus;
    factor = (factor * factor) % modulus;
    cursor >>= 1n;
  }
  const sign = (left: { a: bigint; b: bigint }, right: { a: bigint; b: bigint }) => {
    const da = left.a - right.a;
    const db = left.b - right.b;
    if (db === 0n) return da > 0n ? 1 : da < 0n ? -1 : 0;
    if (db > 0n) return da >= 0n ? 1 : 5n * db * db > da * da ? 1 : 5n * db * db < da * da ? -1 : 0;
    return da <= 0n ? -1 : da * da > 5n * db * db ? 1 : da * da < 5n * db * db ? -1 : 0;
  };
  const order = Array.from({ length: 32 }, (_, lane) => {
    const half = BigInt(lane);
    let lo = -2n;
    let hi = 80n;
    while (lo + 1n < hi) {
      const mid = (lo + hi) >> 1n;
      if (sign({ a: half, b: half }, { a: 2n * mid, b: 0n }) >= 0) lo = mid;
      else hi = mid;
    }
    return { lane, frac: { a: half - 2n * lo, b: half } };
  })
    .sort((left, right) => sign(left.frac, right.frac))
    .map((entry) => entry.lane);
  assert.equal(order[0], 0);
  assert.ok(order.indexOf(2) < order.indexOf(1));
  assert.equal(new Set(order).size, 32);
  let spiral = 0;
  for (let index = 1; index < order.length; index++) spiral += Math.abs(order[index] - order[index - 1]);
  const report = storeReport();
  assert.match(report, /Lucas-Lehmer residue = 0/);
  assert.match(report, /two bins dropped, inverse matches = False/);
  assert.match(report, /sum of those limbs = 4/);
  assert.match(report, new RegExp(`composite address = 2\\^\\(2\\^48\\) mod MODULUS_Q = ${address}`));
  assert.match(report, new RegExp(`insertion order = ${order.join(",")}`));
  assert.match(report, new RegExp(`sunflower miss cost = ${spiral}`));
  assert.match(report, /not a compression advantage/);
  assert.match(report, /the T is not a stabilizer update/);
  assert.match(report, /the float Vogel angle/);
  assert.doesNotMatch(report, /\d\.\d/);
});

test("the triad stores the fold and refuses the handoff", () => {
  const fib = (n: number): bigint => {
    let a = 0n;
    let b = 1n;
    for (let index = 0; index < n; index++) [a, b] = [b, a + b];
    return a;
  };
  const maskOf = (value: bigint) => {
    let hi = 2;
    while (fib(hi) <= value) hi += 1;
    let mask = 0n;
    let remaining = value;
    for (let index = hi - 1; index >= 2; index--) {
      if (fib(index) <= remaining) {
        mask |= 1n << BigInt(index - 2);
        remaining -= fib(index);
      }
    }
    assert.equal(remaining, 0n);
    assert.equal(mask & (mask << 1n), 0n);
    return mask;
  };
  assert.equal(maskOf(4n), 5n);
  const payloadMask = maskOf(1n << 56n);
  const modulus = (1n << 61n) - 1n;
  let address = 1n;
  let factor = 2n;
  let cursor = 1n << 48n;
  while (cursor > 0n) {
    if (cursor & 1n) address = (address * factor) % modulus;
    factor = (factor * factor) % modulus;
    cursor >>= 1n;
  }
  const digest = sha256Of(new Uint8Array([0x01]));
  const report = triadScript();
  assert.match(report, new RegExp(`working mask = ${payloadMask}`));
  assert.match(report, new RegExp(`digest = ${digest}`));
  assert.match(report, new RegExp(`prime address = ${address}`));
  assert.match(report, /sunflower slot = 0/);
  assert.match(report, /materialise = 01/);
  assert.match(report, /after damage = REFUSED/);
  assert.match(report, /restored from replica/);
  assert.match(report, /handoff = REFUSED/);
  assert.match(report, /Active Discovery Engine is a simulated twin/);
  assert.match(report, /11-D direction in the source is a float/);
  assert.doesNotMatch(report, /\d\.\d/);
  const triad = new Triad();
  const record = triad.put(new Uint8Array([0x01]));
  assert.equal(record.primary[0].mask, payloadMask);
  triad.damage(record.id);
  assert.throws(() => triad.get(record.id), /REFUSED/);
  assert.match(triad.heal(record.id), /restored/);
  assert.deepEqual(Array.from(triad.get(record.id)), [1]);
  assert.match(triad.handoff(), /not implemented inside Theseus/);
});

test("a folded integer sums back to itself", () => {
  const fib = (n: number): bigint => {
    let a = 0n;
    let b = 1n;
    for (let index = 0; index < n; index++) [a, b] = [b, a + b];
    return a;
  };
  const payload = 1000n;
  const indices: number[] = [];
  let remaining = payload;
  let hi = 2;
  while (fib(hi) <= payload) hi += 1;
  for (let index = hi - 1; index >= 2 && remaining > 0n; index--) {
    const limb = fib(index);
    if (limb <= remaining) {
      indices.push(index);
      remaining -= limb;
    }
  }
  assert.equal(remaining, 0n);
  assert.equal(indices.reduce((sum, index) => sum + fib(index), 0n), payload);
  const kept = keepData(payload);
  assert.deepEqual(kept.indices, indices);
  assert.equal(kept.restored, payload);
  const lucasAt = (n: number) => {
    if (n === 0) return 2n;
    if (n === 1) return 1n;
    let left = 2n;
    let right = 1n;
    for (let index = 2; index <= n; index++) [left, right] = [right, left + right];
    return right;
  };
  assert.equal(kept.allocated, (payload * lucasAt(17)) / lucasAt(15));
  assert.notEqual(kept.allocated, payload);
});










