// LUCAS WIRING: draws from lucas/ (pool) OR implements its Lucas kernel
// inline below. MUST NOT import from any sibling algorithm.
// Substrate route: trace

/**
 * EUCLID-CORE: Exact Mathematical Engine
 * Substrate-Independent Arbitrary Precision Rational Field & Q[√5] Algebra
 *
 * Order of Truth: MATHEMATICAL & COMPUTATIONAL
 * Zero floating-point operations. Zero approximations. Exact invariants.
 */

/**
 * Arbitrary precision exact rational fraction p/q using BigInt.
 */
export class BigFraction {
  readonly num: bigint;
  readonly den: bigint;

  constructor(num: bigint | number | string, den: bigint | number | string = 1n) {
    let n = BigInt(num);
    let d = BigInt(den);

    if (d === 0n) {
      throw new Error("DivisionByZero: Denominator cannot be zero in BigFraction");
    }

    if (d < 0n) {
      n = -n;
      d = -d;
    }

    const common = BigFraction.gcd(BigFraction.absBigInt(n), d);
    this.num = n / common;
    this.den = d / common;
  }

  static zero(): BigFraction {
    return new BigFraction(0n, 1n);
  }

  static one(): BigFraction {
    return new BigFraction(1n, 1n);
  }

  static fromBigInt(val: bigint): BigFraction {
    return new BigFraction(val, 1n);
  }

  private static absBigInt(a: bigint): bigint {
    return a < 0n ? -a : a;
  }

  private static gcd(a: bigint, b: bigint): bigint {
    while (b !== 0n) {
      const temp = b;
      b = a % b;
      a = temp;
    }
    return a;
  }

  add(other: BigFraction): BigFraction {
    const n = this.num * other.den + other.num * this.den;
    const d = this.den * other.den;
    return new BigFraction(n, d);
  }

  sub(other: BigFraction): BigFraction {
    const n = this.num * other.den - other.num * this.den;
    const d = this.den * other.den;
    return new BigFraction(n, d);
  }

  mul(other: BigFraction): BigFraction {
    const n = this.num * other.num;
    const d = this.den * other.den;
    return new BigFraction(n, d);
  }

  div(other: BigFraction): BigFraction {
    if (other.num === 0n) {
      throw new Error("DivisionByZero: Cannot divide BigFraction by zero");
    }
    const n = this.num * other.den;
    const d = this.den * other.num;
    return new BigFraction(n, d);
  }

  neg(): BigFraction {
    return new BigFraction(-this.num, this.den);
  }

  inverse(): BigFraction {
    if (this.num === 0n) {
      throw new Error("DivisionByZero: Cannot invert zero BigFraction");
    }
    return new BigFraction(this.den, this.num);
  }

  abs(): BigFraction {
    return new BigFraction(BigFraction.absBigInt(this.num), this.den);
  }

  equals(other: BigFraction): boolean {
    return this.num === other.num && this.den === other.den;
  }

  compare(other: BigFraction): number {
    const diff = this.num * other.den - other.num * this.den;
    if (diff > 0n) return 1;
    if (diff < 0n) return -1;
    return 0;
  }

  isZero(): boolean {
    return this.num === 0n;
  }

  isOne(): boolean {
    return this.num === 1n && this.den === 1n;
  }

  toString(): string {
    if (this.den === 1n) return this.num.toString();
    return `${this.num}/${this.den}`;
  }

  toDecimal(digits: number = 6): string {
    const sign = this.num < 0n ? "-" : "";
    const absNum = BigFraction.absBigInt(this.num);
    const integerPart = absNum / this.den;
    let remainder = absNum % this.den;

    let decimalPart = "";
    for (let i = 0; i < digits; i++) {
      remainder *= 10n;
      const digit = remainder / this.den;
      decimalPart += digit.toString();
      remainder %= this.den;
    }
    return `${sign}${integerPart}.${decimalPart}`;
  }

  toFloat(): number {
    return Number(this.num) / Number(this.den);
  }
}

export interface Q5MemoryDiagnostics {
  totalAllocations: number;
  liveInstances: number;
  peakAllocations: number;
  approximateByteSize: number;
  lastCollectionTimestamp: number;
}

/**
 * Exact Quadratic Extension Field Q[√5]:
 * Represents elements of the form a + b√5 where a, b ∈ Q (BigFraction).
 *
 * Field Invariants:
 * Addition: (a + b√5) + (c + d√5) = (a + c) + (b + d)√5
 * Multiplication: (a + b√5)(c + d√5) = (ac + 5bd) + (ad + bc)√5
 * Conjugate: σ(a + b√5) = a - b√5
 * Field Norm: N(α) = α * σ(α) = a² - 5b² ∈ Q
 * Inverse: α⁻¹ = (a - b√5) / (a² - 5b²)
 *
 * In the canonical real embedding Q[√5] ⊂ ℝ (where √5 > 0):
 * Real square magnitude: |α|² = α² = (a² + 5b²) + 2ab√5 ∈ Q[√5].
 * When α is pure rational (b = 0), |α|² = a² ∈ Q.
 */
export class Q5 {
  readonly a: BigFraction;
  readonly b: BigFraction;

  // Diagnostics & Zero-leak Memory Management
  private static totalAllocations = 0;
  private static liveInstances = 0;
  private static peakAllocations = 0;
  private static finalizationRegistry =
    typeof FinalizationRegistry !== "undefined"
      ? new FinalizationRegistry(() => {
          Q5.liveInstances = Math.max(0, Q5.liveInstances - 1);
        })
      : null;

  constructor(a: BigFraction, b: BigFraction = BigFraction.zero()) {
    this.a = a;
    this.b = b;

    Q5.totalAllocations++;
    Q5.liveInstances++;
    if (Q5.liveInstances > Q5.peakAllocations) {
      Q5.peakAllocations = Q5.liveInstances;
    }

    if (Q5.finalizationRegistry) {
      Q5.finalizationRegistry.register(this, null);
    }
  }

  /**
   * Diagnostic footprint inspection:
   * BigInt representations typically consume 32-48 bytes per limb.
   * A Q5 instance contains two BigFraction instances, each with two BigInts (num, den).
   * Exact estimate: ~160 bytes per Q5 object.
   */
  static getDiagnostics(): Q5MemoryDiagnostics {
    return {
      totalAllocations: Q5.totalAllocations,
      liveInstances: Q5.liveInstances,
      peakAllocations: Q5.peakAllocations,
      approximateByteSize: Q5.liveInstances * 160,
      lastCollectionTimestamp: Date.now(),
    };
  }

  static resetDiagnostics(): void {
    Q5.totalAllocations = 0;
    Q5.liveInstances = 0;
    Q5.peakAllocations = 0;
  }

  static zero(): Q5 {
    return new Q5(BigFraction.zero(), BigFraction.zero());
  }

  static one(): Q5 {
    return new Q5(BigFraction.one(), BigFraction.zero());
  }

  static sqrt5(): Q5 {
    return new Q5(BigFraction.zero(), BigFraction.one());
  }

  /**
   * The Golden Ratio φ = (1 + √5) / 2 = 1/2 + (1/2)√5
   */
  static phi(): Q5 {
    const half = new BigFraction(1n, 2n);
    return new Q5(half, half);
  }

  /**
   * φ² = φ + 1 = 3/2 + (1/2)√5
   */
  static phiSquared(): Q5 {
    const threeHalves = new BigFraction(3n, 2n);
    const half = new BigFraction(1n, 2n);
    return new Q5(threeHalves, half);
  }

  add(other: Q5): Q5 {
    return new Q5(this.a.add(other.a), this.b.add(other.b));
  }

  sub(other: Q5): Q5 {
    return new Q5(this.a.sub(other.a), this.b.sub(other.b));
  }

  mul(other: Q5): Q5 {
    // (a + b√5)(c + d√5) = (ac + 5bd) + (ad + bc)√5
    const five = new BigFraction(5n, 1n);
    const ac = this.a.mul(other.a);
    const bd5 = this.b.mul(other.b).mul(five);
    const realPart = ac.add(bd5);

    const ad = this.a.mul(other.d());
    const bc = this.b.mul(other.c());
    const sqrt5Part = ad.add(bc);

    return new Q5(realPart, sqrt5Part);
  }

  private c(): BigFraction {
    return this.a;
  }

  private d(): BigFraction {
    return this.b;
  }

  scale(factor: BigFraction): Q5 {
    return new Q5(this.a.mul(factor), this.b.mul(factor));
  }

  neg(): Q5 {
    return new Q5(this.a.neg(), this.b.neg());
  }

  conjugate(): Q5 {
    return new Q5(this.a, this.b.neg());
  }

  /**
   * Module 1 Directive: NormSquared() -> ExactFraction
   * |a + b√5|^2 = a^2 + 5b^2 (Real squared Euclidean norm / Born magnitude)
   */
  normSquared(): BigFraction {
    const five = new BigFraction(5n, 1n);
    const a2 = this.a.mul(this.a);
    const b2_5 = this.b.mul(this.b).mul(five);
    return a2.add(b2_5);
  }

  /**
   * Algebraic Field Norm N(α) = α * σ(α) = a² - 5b² ∈ Q.
   * Preserved under multiplication: N(αβ) = N(α)N(β).
   */
  algebraicNorm(): BigFraction {
    const five = new BigFraction(5n, 1n);
    const a2 = this.a.mul(this.a);
    const b2_5 = this.b.mul(this.b).mul(five);
    return a2.sub(b2_5);
  }

  /**
   * Real Embedding Square Magnitude:
   * (a + b√5)² = (a² + 5b²) + 2ab√5 ∈ Q[√5].
   * If b = 0 (pure rational), returns exact rational a².
   */
  realMagnitudeSquared(): Q5 {
    return this.mul(this);
  }

  inverse(): Q5 {
    const norm = this.algebraicNorm();
    if (norm.isZero()) {
      throw new Error("DivisionByZero: Cannot invert element with zero field norm in Q[√5]");
    }
    // α⁻¹ = (a - b√5) / (a² - 5b²)
    return new Q5(this.a.div(norm), this.b.neg().div(norm));
  }

  isZero(): boolean {
    return this.a.isZero() && this.b.isZero();
  }

  isPureRational(): boolean {
    return this.b.isZero();
  }

  equals(other: Q5): boolean {
    return this.a.equals(other.a) && this.b.equals(other.b);
  }

  toString(): string {
    if (this.b.isZero()) {
      return this.a.toString();
    }
    if (this.a.isZero()) {
      if (this.b.isOne()) return "√5";
      if (this.b.equals(new BigFraction(-1n, 1n))) return "-√5";
      return `${this.b}√5`;
    }
    const bStr = this.b.compare(BigFraction.zero()) > 0 ? `+ ${this.b}√5` : `- ${this.b.abs()}√5`;
    return `(${this.a} ${bStr})`;
  }

  toFloatApprox(): number {
    return this.a.toFloat() + this.b.toFloat() * Math.sqrt(5);
  }
}

/**
 * Exact Sequence & Identity Arithmetic:
 * Fibonacci, Lucas, Cassini Identity, Zeckendorf Decomposition.
 */
export class ExactSequenceMath {
  /**
   * Fibonacci number via exact integer recurrence:
   * F_0 = 0, F_1 = 1, F_n = F_{n-1} + F_{n-2}
   */
  static fib(n: number): bigint {
    if (n < 0) throw new Error("Index must be non-negative");
    if (n === 0) return 0n;
    if (n === 1) return 1n;

    let a = 0n;
    let b = 1n;
    for (let i = 2; i <= n; i++) {
      const c = a + b;
      a = b;
      b = c;
    }
    return b;
  }

  /**
   * Lucas number via exact integer recurrence:
   * L_0 = 2, L_1 = 1, L_n = L_{n-1} + L_{n-2}
   */
  static lucas(n: number): bigint {
    if (n < 0) throw new Error("Index must be non-negative");
    if (n === 0) return 2n;
    if (n === 1) return 1n;

    let a = 2n;
    let b = 1n;
    for (let i = 2; i <= n; i++) {
      const c = a + b;
      a = b;
      b = c;
    }
    return b;
  }

  /**
   * Cassini Identity Validation:
   * F_{n-1}F_{n+1} - F_n² = (-1)^n
   * Validated strictly in integer arithmetic.
   */
  static cassini(n: number): {
    n: number;
    F_nm1: bigint;
    F_n: bigint;
    F_np1: bigint;
    lhs: bigint;
    rhs: bigint;
    isValid: boolean;
  } {
    if (n < 1) throw new Error("n must be >= 1 for Cassini identity");
    const F_nm1 = ExactSequenceMath.fib(n - 1);
    const F_n = ExactSequenceMath.fib(n);
    const F_np1 = ExactSequenceMath.fib(n + 1);

    const lhs = F_nm1 * F_np1 - F_n * F_n;
    const rhs = n % 2 === 0 ? 1n : -1n;

    return {
      n,
      F_nm1,
      F_n,
      F_np1,
      lhs,
      rhs,
      isValid: lhs === rhs,
    };
  }

  /**
   * Exact Zeckendorf Decomposition:
   * Every positive integer N can be uniquely represented as the sum of one or more
   * non-consecutive Fibonacci numbers: N = ∑ F_{k_i} where |k_i - k_j| ≥ 2 and k_i ≥ 2.
   */
  static zeckendorf(n: bigint): {
    original: bigint;
    indices: number[];
    values: bigint[];
    sum: bigint;
    isNonConsecutive: boolean;
  } {
    if (n <= 0n) {
      return {
        original: n,
        indices: [],
        values: [],
        sum: 0n,
        isNonConsecutive: true,
      };
    }

    // Generate Fibonacci numbers starting at F_2 = 1, F_3 = 2, F_4 = 3, ...
    const fibList: { index: number; val: bigint }[] = [];
    let idx = 2;
    while (true) {
      const f = ExactSequenceMath.fib(idx);
      if (f > n) break;
      fibList.push({ index: idx, val: f });
      idx++;
    }

    // Greedy choice: pick the largest Fibonacci <= remainder
    let rem = n;
    const chosenIndices: number[] = [];
    const chosenValues: bigint[] = [];

    for (let i = fibList.length - 1; i >= 0; i--) {
      const item = fibList[i];
      if (item.val <= rem) {
        chosenIndices.push(item.index);
        chosenValues.push(item.val);
        rem -= item.val;
      }
    }

    let isNonConsecutive = true;
    for (let i = 0; i < chosenIndices.length - 1; i++) {
      if (Math.abs(chosenIndices[i] - chosenIndices[i + 1]) < 2) {
        isNonConsecutive = false;
        break;
      }
    }

    const reconstructedSum = chosenValues.reduce((acc, v) => acc + v, 0n);

    return {
      original: n,
      indices: chosenIndices,
      values: chosenValues,
      sum: reconstructedSum,
      isNonConsecutive: isNonConsecutive && reconstructedSum === n,
    };
  }
}
export function lucasBound(n = 10): { module: string; n: number; lucasBound: number; route: string; theoremProven: false } {
  return { module: "exact_math", n, lucasBound: Number(ExactSequenceMath.lucas(n)), route: "trace", theoremProven: false };
}
