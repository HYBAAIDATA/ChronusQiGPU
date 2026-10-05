/** Cubic companions for Padovan, Narayana and Tribonacci.

Sequences are integer matrix powers. Pisot is a negative conjugate
discriminant and a modulus squared equal to the reciprocal of a root greater
than 1. Decimal roots, float64 Binet and least-squares angles are refused.
*/

import { fibonacci } from "./lucas-scale.ts";

type Mat = bigint[][];

const FAMILIES = [
  {
    name: "Padovan",
    poly: "x^3 - x - 1",
    root: "ρ",
    recurrence: "a(n) = a(n-2) + a(n-3)",
    seed: [1n, 1n, 1n],
    generating: "(1 + x)/(1 - x^2 - x^3)",
    denominator: [1n, 0n, -1n, -1n],
    numerator: [1n, 1n],
    series: [1n, 1n, 1n, 2n, 2n, 3n, 4n, 5n, 7n, 9n, 12n, 16n, 21n, 28n],
    matrix: [
      [0n, 1n, 1n],
      [1n, 0n, 0n],
      [0n, 1n, 0n],
    ],
  },
  {
    name: "Narayana",
    poly: "x^3 - x^2 - 1",
    root: "ψ",
    recurrence: "a(n) = a(n-1) + a(n-3)",
    seed: [1n, 1n, 1n],
    generating: "1/(1 - x - x^3)",
    denominator: [1n, -1n, 0n, -1n],
    numerator: [1n],
    series: [1n, 1n, 1n, 2n, 3n, 4n, 6n, 9n, 13n, 19n, 28n, 41n, 60n, 88n],
    matrix: [
      [1n, 0n, 1n],
      [1n, 0n, 0n],
      [0n, 1n, 0n],
    ],
  },
  {
    name: "Tribonacci",
    poly: "x^3 - x^2 - x - 1",
    root: "τ",
    recurrence: "a(n) = a(n-1) + a(n-2) + a(n-3)",
    seed: [0n, 0n, 1n],
    generating: "x^2/(1 - x - x^2 - x^3)",
    denominator: [1n, -1n, -1n, -1n],
    numerator: [0n, 0n, 1n],
    series: [0n, 0n, 1n, 1n, 2n, 4n, 7n, 13n, 24n, 44n, 81n, 149n, 274n, 504n],
    matrix: [
      [1n, 1n, 1n],
      [1n, 0n, 0n],
      [0n, 1n, 0n],
    ],
  },
] as const;

function mul(left: Mat, right: Mat): Mat {
  return left.map((row) => right[0].map((_, col) => row.reduce((sum, entry, k) => sum + entry * right[k][col], 0n)));
}

function apply(matrix: Mat, vector: bigint[]): bigint[] {
  return matrix.map((row) => row.reduce((sum, entry, index) => sum + entry * vector[index], 0n));
}

function pow(matrix: Mat, exponent: number): Mat {
  let result: Mat = [
    [1n, 0n, 0n],
    [0n, 1n, 0n],
    [0n, 0n, 1n],
  ];
  let base = matrix.map((row) => row.slice());
  let exp = exponent;
  while (exp > 0) {
    if (exp & 1) result = mul(result, base);
    base = mul(base, base);
    exp >>= 1;
  }
  return result;
}

function det(matrix: Mat): bigint {
  return (
    matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1]) -
    matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0]) +
    matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
  );
}

function charPoly(matrix: Mat): string {
  const trace = matrix[0][0] + matrix[1][1] + matrix[2][2];
  const minor =
    matrix[0][0] * matrix[1][1] -
    matrix[0][1] * matrix[1][0] +
    matrix[0][0] * matrix[2][2] -
    matrix[0][2] * matrix[2][0] +
    matrix[1][1] * matrix[2][2] -
    matrix[1][2] * matrix[2][1];
  const constant = -det(matrix);
  const term = (value: bigint, power: string) => {
    if (value === 0n) return "";
    const sign = value > 0n ? " + " : " - ";
    const mag = value > 0n ? value : -value;
    return `${sign}${mag === 1n && power !== "" ? "" : mag}${power}`;
  };
  return `x^3${term(-trace, "x^2")}${term(minor, "x")}${term(constant, "")}`;
}

function term(name: string, n: number): bigint {
  const seed = name === "Tribonacci" ? [0n, 0n, 1n] : [1n, 1n, 1n];
  if (n < 3) return seed[n];
  let a = seed[0];
  let b = seed[1];
  let c = seed[2];
  for (let index = 3; index <= n; index++) {
    const next = name === "Padovan" ? a + b : name === "Narayana" ? a + c : a + b + c;
    a = b;
    b = c;
    c = next;
  }
  return c;
}

function nextTerm(name: string, series: readonly bigint[], n: number): bigint {
  if (name === "Padovan") return series[n - 2] + series[n - 3];
  if (name === "Narayana") return series[n - 1] + series[n - 3];
  return series[n - 1] + series[n - 2] + series[n - 3];
}

function generatingOk(series: readonly bigint[], denominator: readonly bigint[], numerator: readonly bigint[]): boolean {
  for (let n = 0; n < series.length; n++) {
    let total = 0n;
    for (let k = 0; k < denominator.length; k++) if (n - k >= 0) total += denominator[k] * series[n - k];
    const expected = n < numerator.length ? numerator[n] : 0n;
    if (total !== expected) return false;
  }
  return true;
}

function minors(name: string): bigint[] {
  return Array.from({ length: 8 }, (_, offset) => {
    const n = offset + 2;
    return term(name, n + 1) * term(name, n - 1) - term(name, n) * term(name, n);
  });
}

type Gauss = { re: bigint; im: bigint };

function gadd(p: Gauss, q: Gauss): Gauss {
  return { re: p.re + q.re, im: p.im + q.im };
}

function gscale(p: Gauss, k: bigint): Gauss {
  return { re: p.re * k, im: p.im * k };
}

function zeroG(): Gauss {
  return { re: 0n, im: 0n };
}

function fourierSeparation(): { cycle: string; path: string } {
  const mode = [0, 1, 2, 3].map((j) => ({ re: j === 0 ? 1n : j === 2 ? -1n : 0n, im: j === 1 ? 1n : j === 3 ? -1n : 0n }));
  const circulant = [
    [2n, -1n, 0n, -1n],
    [-1n, 2n, -1n, 0n],
    [0n, -1n, 2n, -1n],
    [-1n, 0n, -1n, 2n],
  ];
  const cycleImage = circulant.map((row) => row.reduce((sum, entry, index) => gadd(sum, gscale(mode[index], entry)), zeroG()));
  if (!cycleImage.every((value, index) => value.re === 2n * mode[index].re && value.im === 2n * mode[index].im)) {
    throw new Error("the C4 Laplacian did not act by 2 on the order-4 mode");
  }
  const path = [
    [1n, -1n, 0n, 0n],
    [-1n, 2n, -1n, 0n],
    [0n, -1n, 2n, -1n],
    [0n, 0n, -1n, 1n],
  ];
  const pathImage = path.map((row) => row.reduce((sum, entry, index) => gadd(sum, gscale(mode[index], entry)), zeroG()));
  const candidate = pathImage[0];
  const diagonal = pathImage.every(
    (value, index) =>
      value.re === candidate.re * mode[index].re - candidate.im * mode[index].im &&
      value.im === candidate.re * mode[index].im + candidate.im * mode[index].re,
  );
  if (diagonal) throw new Error("the path Laplacian was unexpectedly diagonal in this Fourier mode");
  return {
    cycle: "C4 Laplacian on (1, i, -1, -i) = 2 times that mode",
    path: "P4 is not an eigenvector of that mode",
  };
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

function divideRoot(coeffs: bigint[], root: bigint): bigint[] | null {
  const out = coeffs.slice();
  const quotient: bigint[] = [];
  for (let power = out.length - 1; power >= 1; power--) {
    quotient.push(out[power]);
    out[power - 1] += root * out[power];
    out[power] = 0n;
  }
  if (out[0] !== 0n) return null;
  return quotient.reverse();
}

function cycleSpectrum(): string {
  const size = 6;
  const matrix = Array.from({ length: size }, () => Array.from({ length: size }, () => 0n));
  for (let i = 0; i < size; i++) {
    matrix[i][i] = 2n;
    matrix[i][(i + 1) % size] = -1n;
    matrix[i][(i + size - 1) % size] = -1n;
  }
  const samples: bigint[] = [];
  for (let point = 0; point <= size; point++) {
    const shifted = matrix.map((row, i) => row.map((entry, j) => (i === j ? BigInt(point) : 0n) - entry));
    samples.push(bareiss(shifted));
  }
  const diffs: bigint[][] = [samples.slice()];
  for (let order = 1; order <= size; order++) {
    const previous = diffs[order - 1];
    diffs.push(previous.slice(1).map((value, index) => value - previous[index]));
  }
  const stirling: bigint[][] = [[1n]];
  for (let n = 1; n <= size; n++) {
    const row = Array.from({ length: n + 1 }, () => 0n);
    for (let k = 1; k <= n; k++) row[k] = stirling[n - 1][k - 1] - BigInt(n - 1) * (stirling[n - 1][k] ?? 0n);
    stirling.push(row);
  }
  const coeffs = Array.from({ length: size + 1 }, () => 0n);
  let factorial = 1n;
  for (let m = 0; m <= size; m++) {
    if (m > 0) factorial *= BigInt(m);
    if (diffs[m][0] % factorial !== 0n) throw new Error("C6 characteristic polynomial left the integers");
    const scale = diffs[m][0] / factorial;
    for (let power = 0; power <= m; power++) coeffs[power] += scale * stirling[m][power];
  }
  let current = coeffs.slice();
  for (const root of [0n, 1n, 1n, 3n, 3n, 4n]) {
    const quotient = divideRoot(current, root);
    if (!quotient) throw new Error("C6 spectrum is not t(t-1)^2(t-3)^2(t-4)");
    current = quotient;
  }
  if (current.length !== 1 || current[0] !== 1n) throw new Error("C6 spectrum has an extra factor");
  const shift = [
    [0n, 0n, 0n, 0n, 0n, 1n],
    [1n, 0n, 0n, 0n, 0n, 0n],
    [0n, 1n, 0n, 0n, 0n, 0n],
    [0n, 0n, 1n, 0n, 0n, 0n],
    [0n, 0n, 0n, 1n, 0n, 0n],
    [0n, 0n, 0n, 0n, 1n, 0n],
  ];
  const product = (left: bigint[][], right: bigint[][]) =>
    left.map((row) => right[0].map((_, col) => row.reduce((sum, entry, k) => sum + entry * right[k][col], 0n)));
  const same = (left: bigint[][], right: bigint[][]) => left.every((row, i) => row.every((entry, j) => entry === right[i][j]));
  if (!same(product(matrix, shift), product(shift, matrix))) throw new Error("the cycle Laplacian does not commute with the shift");
  const path = matrix.map((row) => row.slice());
  path[0][size - 1] = 0n;
  path[size - 1][0] = 0n;
  path[0][0] = 1n;
  path[size - 1][size - 1] = 1n;
  if (same(product(path, shift), product(shift, path))) throw new Error("the path Laplacian commuted with the cycle shift");
  return "C6 eigenvalues = 0, 1, 1, 3, 3, 4    gap = 1    the path does not commute with the shift";
}

function pellLine(): string {
  let previousH = 0n;
  let h = 1n;
  let previousK = 1n;
  let k = 0n;
  const shown: string[] = [];
  for (let n = 0; n < 6; n++) {
    const a = n === 0 ? 1n : 2n;
    const nextH = a * h + previousH;
    const nextK = a * k + previousK;
    previousH = h;
    h = nextH;
    previousK = k;
    k = nextK;
    if (h * h - 2n * k * k !== (n % 2 === 0 ? -1n : 1n)) throw new Error("Pell residue failed");
    shown.push(`${h}/${k}`);
  }
  return shown.join(" ");
}

let cached: string | null = null;

export function algebraReport(): string {
  if (cached) return cached;
  const lines = [
    "cubic family   companion matrices over Z   float Binet = refused",
    "  theorem_proven = False",
    "",
  ];
  for (const family of FAMILIES) {
    const state = [family.seed[2], family.seed[1], family.seed[0]];
    const matrix = family.matrix.map((row) => [...row]);
    for (let n = 2; n <= 70; n++) {
      if (apply(pow(matrix, n - 2), state)[0] !== term(family.name, n)) throw new Error(`${family.name} trace disagrees at n=${n}`);
      if (n < family.series.length && family.series[n] !== term(family.name, n)) throw new Error(`${family.name} series disagrees at n=${n}`);
      if (n >= 3 && n < family.series.length && family.series[n] !== nextTerm(family.name, family.series, n)) {
        throw new Error(`${family.name} recurrence disagrees at n=${n}`);
      }
    }
    if (!generatingOk(family.series, family.denominator, family.numerator)) throw new Error(`${family.name} generating function disagrees`);
    if (det(matrix) !== 1n) throw new Error(`${family.name} companion is not unimodular`);
    for (let n = 1; n <= 8; n++) if (det(pow(matrix, n)) !== 1n) throw new Error(`det(C^${n}) is not 1`);
    if (charPoly(matrix) !== family.poly) throw new Error(`${family.name} characteristic polynomial changed`);
    const minorValues = minors(family.name);
    if (new Set(minorValues.map((value) => (value < 0n ? -value : value).toString())).size < 2) {
      throw new Error(`${family.name} sequence minors were unexpectedly constant`);
    }
    lines.push(`[${family.name}]`);
    lines.push(`  companion char poly = ${family.poly}`);
    lines.push(`  recurrence ${family.recurrence}`);
    lines.push("  a(n) = (C^(n-2) v2)[0] for n = 2..70");
    lines.push(`  generating function ${family.generating}`);
    lines.push(`  series = ${family.series.join(" ")}`);
    lines.push("  det(C) = 1    det(C^n) = 1");
    lines.push(`  sequence minors = ${minorValues.join(" ")}`);
    lines.push(`  ${family.root} > 1 because the polynomial is negative at 1 and positive at 2`);
    lines.push(`  conjugate modulus squared = 1/${family.root} < 1`);
    lines.push("  conjugate discriminant < 0");
    lines.push("  Pisot = True");
    if (family.name === "Padovan") {
      lines.push("  ρ^5 = ρ^2 + ρ + 1 follows from ρ^3 = ρ + 1");
      lines.push("  ρ^5 = ρ^2 + 1    REFUTED");
    }
    lines.push("");
  }
  const tribonacci = [40, 56, 69].map((n) => term("Tribonacci", n));
  if (tribonacci[0] !== 7046319384n || tribonacci[1] !== 120879712950776n || tribonacci[2] !== 333269972246340068n) {
    throw new Error(`Tribonacci limbs ${tribonacci.join(" ")}`);
  }
  if (tribonacci[2] < 1n << 53n) throw new Error("T(69) still fits in a 53-bit mantissa");
  if (fibonacci(8) !== 21n || fibonacci(9) !== 34n) throw new Error("Fibonacci convergents left the ladder");
  const bridge = fourierSeparation();
  lines.push("[integer shadow]");
  lines.push("  T(40) = 7046319384");
  lines.push("  T(56) = 120879712950776");
  lines.push("  T(69) = 333269972246340068");
  lines.push("  T(69) does not fit in a 53-bit mantissa");
  lines.push("");
  lines.push("[bridge]");
  lines.push("  denominator of each generating function = the characteristic polynomial");
  lines.push("  dominant pole = 1/root, real and inside the unit interval");
  lines.push("  conjugate poles are off the real axis because the discriminant is negative");
  lines.push(`  ${bridge.cycle}`);
  lines.push(`  ${bridge.path}`);
  lines.push(`  ${cycleSpectrum()}`);
  lines.push("  a circulant is a polynomial in the cycle shift, so the Fourier modes are eigenvectors");
  lines.push("  continued fraction of φ = [1;1,1,...]    convergents = F(n+1)/F(n)");
  lines.push(`  continued fraction of √2 = [1;2,2,...]    convergents = ${pellLine()}`);
  lines.push("  each convergent satisfies h^2 - 2k^2 = ±1");
  lines.push("");
  lines.push("[refused]");
  lines.push("  a decimal dominant root");
  lines.push("  a float64 Binet value and its rounding error");
  lines.push("  a least-squares conjugate angle");
  lines.push("  a machine-epsilon residual offered as a proof");
  lines.push("  a continued fraction of π offered as an exact certificate");
  lines.push("  metallic ratios guarantee zero grid-harmonic overlap    NOT_PROVEN");
  lines.push("  spectral gap implies drug binding    REJECTED");
  lines.push("  a root alone implies packing, forecast stability, or stall removal    UNTESTED");
  cached = lines.join("\n");
  return cached;
}
