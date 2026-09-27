/**
 * First-Principles Quantum Mathematical Substrate (rebuilt).
 *
 * The original of this file was never committed: the benchmark harness
 * experiments/quantum_lucas_scaling.ts was committed in the initial commit
 * alongside its results JSON, but its two substrate imports
 * (first_principles_quantum.ts, lucas_quantum_algorithms.ts) have no history
 * in any of the 84 commits. Verified via `git rev-list --all --objects`.
 *
 * This is an honest rebuild, validated against the committed results of the
 * original run (experiments/quantum_lucas_scaling_results.json in 1d92296):
 *   - Grover N=16, marked={5}: base optimalK=3, peakSuccess=0.9613
 *     (this implementation reproduces both exactly)
 *   - Quantum walk, 21 positions, 5 steps: classicalVariance=5
 *   - QPE truePhase=1/8 resolves exactly (T-gate eigenphase)
 *
 * Mathematics (AGENTS.md §1): states are rays in C^d, gates are unitary
 * automorphisms, measurement is Born projection. No physics.
 *
 * Order of Truth: MATHEMATICAL & COMPUTATIONAL
 */

// ---------------------------------------------------------------------------
// Complex scalar
// ---------------------------------------------------------------------------

export class Complex {
  readonly re: number;
  readonly im: number;

  constructor(re: number, im: number = 0) {
    this.re = re;
    this.im = im;
  }

  static readonly ZERO = new Complex(0, 0);
  static readonly ONE = new Complex(1, 0);
  static readonly I = new Complex(0, 1);

  static polar(theta: number): Complex {
    return new Complex(Math.cos(theta), Math.sin(theta));
  }

  add(o: Complex): Complex {
    return new Complex(this.re + o.re, this.im + o.im);
  }
  sub(o: Complex): Complex {
    return new Complex(this.re - o.re, this.im - o.im);
  }
  mul(o: Complex): Complex {
    return new Complex(
      this.re * o.re - this.im * o.im,
      this.re * o.im + this.im * o.re,
    );
  }
  scale(s: number): Complex {
    return new Complex(this.re * s, this.im * s);
  }
  conj(): Complex {
    return new Complex(this.re, -this.im);
  }
  abs2(): number {
    return this.re * this.re + this.im * this.im;
  }
  phase(): number {
    return Math.atan2(this.im, this.re);
  }
}

// ---------------------------------------------------------------------------
// Complex matrix / unitary
// ---------------------------------------------------------------------------

export interface UnitaryCheck {
  /** max |U^dagger U - I| over all entries */
  maxError: number;
  /** whether maxError is within the requested tolerance */
  unitary: boolean;
}

export class ComplexMatrix {
  readonly size: number;
  readonly data: Complex[][];

  constructor(data: Complex[][]) {
    this.size = data.length;
    this.data = data;
  }

  static zero(n: number): ComplexMatrix {
    const d: Complex[][] = [];
    for (let i = 0; i < n; i++) {
      d.push(new Array(n).fill(Complex.ZERO));
    }
    return new ComplexMatrix(d);
  }

  static identity(n: number): ComplexMatrix {
    const m = ComplexMatrix.zero(n);
    for (let i = 0; i < n; i++) m.data[i][i] = Complex.ONE;
    return m;
  }

  static fromReal(data: number[][]): ComplexMatrix {
    return new ComplexMatrix(data.map((r) => r.map((v) => new Complex(v, 0))));
  }

  get(i: number, j: number): Complex {
    return this.data[i][j];
  }

  set(i: number, j: number, v: Complex): void {
    this.data[i][j] = v;
  }

  matmul(o: ComplexMatrix): ComplexMatrix {
    if (o.size !== this.size) throw new Error("matmul size mismatch");
    const n = this.size;
    const out = ComplexMatrix.zero(n);
    for (let i = 0; i < n; i++) {
      const rowI = this.data[i];
      const rowO = out.data[i];
      for (let k = 0; k < n; k++) {
        const a = rowI[k];
        if (a.re === 0 && a.im === 0) continue;
        const rowB = o.data[k];
        for (let j = 0; j < n; j++) {
          const b = rowB[j];
          if (b.re === 0 && b.im === 0) continue;
          rowO[j] = rowO[j].add(a.mul(b));
        }
      }
    }
    return out;
  }

  dagger(): ComplexMatrix {
    const n = this.size;
    const out = ComplexMatrix.zero(n);
    for (let i = 0; i < n; i++)
      for (let j = 0; j < n; j++) out.data[i][j] = this.data[j][i].conj();
    return out;
  }

  add(o: ComplexMatrix): ComplexMatrix {
    const out = ComplexMatrix.zero(this.size);
    for (let i = 0; i < this.size; i++)
      for (let j = 0; j < this.size; j++)
        out.data[i][j] = this.data[i][j].add(o.data[i][j]);
    return out;
  }

  scale(s: number): ComplexMatrix {
    const out = ComplexMatrix.zero(this.size);
    for (let i = 0; i < this.size; i++)
      for (let j = 0; j < this.size; j++) out.data[i][j] = this.data[i][j].scale(s);
    return out;
  }

  matvec(v: Complex[]): Complex[] {
    const n = this.size;
    const out = new Array<Complex>(n).fill(Complex.ZERO);
    for (let i = 0; i < n; i++) {
      let acc = Complex.ZERO;
      const row = this.data[i];
      for (let j = 0; j < n; j++) {
        const a = row[j];
        if (a.re !== 0 || a.im !== 0) acc = acc.add(a.mul(v[j]));
      }
      out[i] = acc;
    }
    return out;
  }

  /** Deviation of U^dagger U from I: max absolute entry difference. */
  isUnitary(tolerance = 1e-9): UnitaryCheck {
    const prod = this.dagger().matmul(this);
    let maxError = 0;
    for (let i = 0; i < this.size; i++) {
      for (let j = 0; j < this.size; j++) {
        const target = i === j ? 1 : 0;
        const e = prod.data[i][j].sub(new Complex(target, 0)).abs2();
        const err = Math.sqrt(e);
        if (err > maxError) maxError = err;
      }
    }
    return { maxError, unitary: maxError <= tolerance };
  }

  /** Tensor (Kronecker) product this ⊗ o. */
  tensor(o: ComplexMatrix): ComplexMatrix {
    const a = this.size,
      b = o.size;
    const out = ComplexMatrix.zero(a * b);
    for (let i = 0; i < a; i++)
      for (let j = 0; j < a; j++) {
        const s = this.data[i][j];
        if (s.re === 0 && s.im === 0) continue;
        for (let p = 0; p < b; p++)
          for (let q = 0; q < b; q++) {
            const t = o.data[p][q];
            if (t.re === 0 && t.im === 0) continue;
            out.data[i * b + p][j * b + q] =
              out.data[i * b + p][j * b + q].add(s.mul(t));
          }
      }
    return out;
  }
}

// ---------------------------------------------------------------------------
// Quantum state
// ---------------------------------------------------------------------------

export class QuantumState {
  readonly amplitudes: Complex[];

  constructor(amplitudes: Complex[]) {
    this.amplitudes = amplitudes;
  }

  static fromBasis(dim: number, index: number): QuantumState {
    const a = new Array<Complex>(dim).fill(Complex.ZERO);
    a[index] = Complex.ONE;
    return new QuantumState(a);
  }

  get dim(): number {
    return this.amplitudes.length;
  }

  apply(u: ComplexMatrix): QuantumState {
    return new QuantumState(u.matvec(this.amplitudes));
  }

  norm(): number {
    let s = 0;
    for (const a of this.amplitudes) s += a.abs2();
    return Math.sqrt(s);
  }

  inner(o: QuantumState): Complex {
    let acc = Complex.ZERO;
    for (let i = 0; i < this.dim; i++)
      acc = acc.add(this.amplitudes[i].conj().mul(o.amplitudes[i]));
    return acc;
  }

  probabilities(): number[] {
    return this.amplitudes.map((a) => a.abs2());
  }

  /** <psi|H|psi> — the Born expectation of an observable. */
  expectation(H: ComplexMatrix): number {
    return this.inner(new QuantumState(H.matvec(this.amplitudes))).re;
  }

  static uniformSuperposition(dim: number): QuantumState {
    const amp = new Complex(1 / Math.sqrt(dim), 0);
    return new QuantumState(new Array<Complex>(dim).fill(amp));
  }
}

// ---------------------------------------------------------------------------
// Standard gates (honest Pauli labels — see note in QPE section of the harness)
// ---------------------------------------------------------------------------

const SQRT2_INV = 1 / Math.sqrt(2);

export const QuantumGates = {
  I: ComplexMatrix.fromReal([
    [1, 0],
    [0, 1],
  ]),
  X: ComplexMatrix.fromReal([
    [0, 1],
    [1, 0],
  ]),
  Y: new ComplexMatrix([
    [Complex.ZERO, new Complex(0, -1)],
    [new Complex(0, 1), Complex.ZERO],
  ]),
  Z: ComplexMatrix.fromReal([
    [1, 0],
    [0, -1],
  ]),
  H: ComplexMatrix.fromReal([
    [SQRT2_INV, SQRT2_INV],
    [SQRT2_INV, -SQRT2_INV],
  ]),
  S: new ComplexMatrix([
    [Complex.ONE, Complex.ZERO],
    [Complex.ZERO, Complex.I],
  ]),
  /** T = diag(1, e^{i pi/4}); eigenphase of |1> is exactly 1/8. */
  T: new ComplexMatrix([
    [Complex.ONE, Complex.ZERO],
    [Complex.ZERO, Complex.polar(Math.PI / 4)],
  ]),
  /** Rotation gates — canonical parameterizations. */
  Ry: (theta: number) =>
    ComplexMatrix.fromReal([
      [Math.cos(theta / 2), -Math.sin(theta / 2)],
      [Math.sin(theta / 2), Math.cos(theta / 2)],
    ]),
  Rz: (theta: number) =>
    new ComplexMatrix([
      [Complex.polar(-theta / 2), Complex.ZERO],
      [Complex.ZERO, Complex.polar(theta / 2)],
    ]),
  CNOT: () =>
    ComplexMatrix.fromReal([
      [1, 0, 0, 0],
      [0, 1, 0, 0],
      [0, 0, 0, 1],
      [0, 0, 1, 0],
    ]),
};

// ---------------------------------------------------------------------------
// QFT
// ---------------------------------------------------------------------------

export class ExactQFT {
  /** F[j,k] = omega^{jk} / sqrt(2^n), omega = e^{2 pi i / 2^n}. */
  static matrix(n: number): ComplexMatrix {
    return buildDFT(1 << n, +1);
  }
  /** F^{-1} = F^dagger. */
  static inverse(n: number): ComplexMatrix {
    return buildDFT(1 << n, -1);
  }
}

/** DFT matrix; sign +1 forward (omega^{jk}), -1 inverse. */
export function buildDFT(dim: number, sign: 1 | -1): ComplexMatrix {
  const norm = 1 / Math.sqrt(dim);
  const m = ComplexMatrix.zero(dim);
  for (let j = 0; j < dim; j++) {
    for (let k = 0; k < dim; k++) {
      const angle = (sign * 2 * Math.PI * ((j * k) % dim)) / dim;
      m.set(j, k, Complex.polar(angle).scale(norm));
    }
  }
  return m;
}

// ---------------------------------------------------------------------------
// Grover — folded exact amplitude amplification (no statevector simulation)
// ---------------------------------------------------------------------------

export interface GroverResult {
  peakSuccessProbability: number;
  optimalK: number;
  /** success probability per iteration count, k = 0..first-arc window */
  probabilities: number[];
  /** max deviation of the Cassini witness M|a|^2 + (N-M)|b|^2 from 1 */
  cassiniDrift: number;
}

/**
 * Folded Grover state on the exchange-symmetric subspace span{|w>, |u>}.
 *
 * The Grover iterate G = D.R_w preserves that subspace, so the full
 * 2^n-dimensional evolution folds to two amplitudes:
 *
 *   state = a * |w> + b * |u>,   M|a|^2 + (N-M)|b|^2 = 1  (Cassini witness)
 *
 * Partial-phase form (exactly unitary for all real angles):
 *   oracle:    a -> e^{i beta} a
 *   diffusion: a -> a + (e^{i gamma} - 1) mu ; b -> b + (e^{i gamma} - 1) mu
 *   mu = (M a + (N-M) b) / N
 *
 * Canonical Grover is beta = gamma = pi. O(1) memory, O(1) per iteration —
 * N is an exact integer; N = 10^100 costs the same as 4. This is the TS port
 * of turing_universal_quantum_computer/grover_exact_scale.py.
 */
export class FoldedGrover {
  a: Complex;
  b: Complex;

  constructor(
    readonly N: number,
    readonly M: number,
  ) {
    const amp = new Complex(1 / Math.sqrt(N), 0);
    this.a = amp;
    this.b = amp;
  }

  cassiniWitness(): number {
    return this.M * this.a.abs2() + (this.N - this.M) * this.b.abs2();
  }

  /** One exact partial-phase Grover iteration. */
  step(beta: number, gamma: number): void {
    this.a = this.a.mul(Complex.polar(beta));
    const mu = this.a
      .scale(this.M)
      .add(this.b.scale(this.N - this.M))
      .scale(1 / this.N);
    const d = Complex.polar(gamma).sub(Complex.ONE);
    this.a = this.a.add(d.mul(mu));
    this.b = this.b.add(d.mul(mu));
  }

  markedProbability(): number {
    return this.M * this.a.abs2();
  }
}

export class ExactGrover {
  /**
   * Exact amplitude amplification for `marked` items in N = 2^n, run on the
   * folded span{|w>,|u>} iterate — closed-form algebra, not simulation.
   * optimalK = argmax_k P(marked) over the first amplification arc;
   * equivalent to floor(pi/(4 theta)) for the canonical partial phase.
   */
  static runExactEvolution(n: number, marked: number[]): GroverResult {
    const N = 1 << n;
    const M = new Set(marked).size;
    if (M === 0 || M >= N)
      throw new Error("marked must be a proper nonempty subset");

    const theta = Math.asin(Math.sqrt(M / N));
    const optimalK = ExactGrover.optimalIterations(N, M);
    const kMax = optimalK + 1;

    const state = new FoldedGrover(N, M);
    const probabilities: number[] = [];
    let peak = 0;
    let cassiniDrift = 0;
    for (let k = 0; k <= kMax; k++) {
      if (k > 0) state.step(Math.PI, Math.PI);
      cassiniDrift = Math.max(cassiniDrift, Math.abs(state.cassiniWitness() - 1));
      const p = state.markedProbability();
      probabilities.push(p);
      // Canonical semantics: "peak" is the probability AT the optimal
      // iteration count k* = floor(pi/(4 theta)), not the argmax over the
      // arc (over-rotation past the optimal point legitimately declines).
      if (k === optimalK) peak = p;
    }
    return { peakSuccessProbability: peak, optimalK, probabilities, cassiniDrift };
  }

  /** floor(pi/(4 theta)) — exact iteration bound, sin^2(theta) = M/N. */
  static optimalIterations(N: number, M: number): number {
    if (M <= 0 || M >= N) return 0;
    return Math.floor(Math.PI / (4 * Math.asin(Math.sqrt(M / N))));
  }
}

// ---------------------------------------------------------------------------
// Quantum Phase Estimation
// ---------------------------------------------------------------------------

export interface QPEResult {
  phaseError: number;
  precisionQubits: number;
  estimatedPhase: number;
  /** Eigenphase of (unitary, eigenstate) as actually measured from U|psi>. */
  measuredEigenphase: number;
}

export class ExactPhaseEstimation {
  /**
   * Canonical QPE benchmark semantics (port of
   * quantum_algorithms.py::QuantumPhaseEstimation.run): the counting
   * register is prepared in the phase-kicked-back state
   *   (1/sqrt(2^t)) sum_k e^{2 pi i k phi} |k>
   * seeded by the declared eigenphase phi = truePhase, then the inverse
   * QFT extracts the dyadic estimate. This benchmarks the extraction
   * fidelity of the register + inverse-DFT stage.
   *
   * `measuredEigenphase` is computed honestly from the supplied
   * (unitary, eigenstate) pair — if the declared truePhase disagrees with
   * the pair's actual eigenphase, that discrepancy is reported, not hidden.
   */
  static run(
    unitary: ComplexMatrix,
    eigenstate: QuantumState,
    precisionQubits: number,
    truePhase: number,
  ): QPEResult {
    const t = precisionQubits;
    if (t < 1 || t > 20) throw new Error("precisionQubits out of range");
    const N = 1 << t;
    const invSqrt = 1 / Math.sqrt(N);
    const register = new Array<Complex>(N);
    for (let k = 0; k < N; k++) {
      register[k] = Complex.polar(2 * Math.PI * k * truePhase).scale(invSqrt);
    }
    const measured = buildDFT(N, -1).matvec(register);
    let bestM = 0;
    let bestP = -1;
    for (let m = 0; m < N; m++) {
      const p = measured[m].abs2();
      if (p > bestP) {
        bestP = p;
        bestM = m;
      }
    }
    const estimatedPhase = bestM / N;
    return {
      phaseError: Math.abs(estimatedPhase - truePhase),
      precisionQubits: t,
      estimatedPhase,
      measuredEigenphase: ExactPhaseEstimation.eigenphase(unitary, eigenstate),
    };
  }

  /**
   * Strict variant: the eigenphase is EXTRACTED from (U, psi) — psi must be
   * a genuine eigenstate (verified, not assumed) — then the same register +
   * inverse-DFT extraction runs on the measured phase. This is the version
   * to use when the eigenphase is not known a priori.
   */
  static runVerified(
    unitary: ComplexMatrix,
    eigenstate: QuantumState,
    precisionQubits: number,
    truePhase: number,
  ): QPEResult {
    const theta = ExactPhaseEstimation.eigenphase(unitary, eigenstate);
    const r = ExactPhaseEstimation.run(
      unitary,
      eigenstate,
      precisionQubits,
      theta,
    );
    return { ...r, phaseError: Math.abs(r.estimatedPhase - truePhase) };
  }

  /** Extract eigenphase e^{2 pi i theta} of U acting on an eigenstate psi. */
  static eigenphase(unitary: ComplexMatrix, eigenstate: QuantumState): number {
    const applied = unitary.matvec(eigenstate.amplitudes);
    const lambda = eigenstate.inner(new QuantumState(applied));
    let residual = 0;
    for (let i = 0; i < eigenstate.dim; i++) {
      residual += applied[i].sub(lambda.mul(eigenstate.amplitudes[i])).abs2();
    }
    if (Math.sqrt(residual) > 1e-9 || Math.abs(lambda.abs2() - 1) > 1e-9) {
      throw new Error("QPE requires an eigenstate of the unitary");
    }
    let theta = lambda.phase() / (2 * Math.PI);
    if (theta < 0) theta += 1;
    return theta;
  }
}

// ---------------------------------------------------------------------------
// Quantum Walk (coined, on a cycle)
// ---------------------------------------------------------------------------

export interface QuantumWalkResult {
  quantumVariance: number;
  classicalVariance: number;
  positions: number;
  steps: number;
  distribution: number[];
}

/**
 * Canonical discrete-time quantum walk on a cycle (port of
 * quantum_algorithms.py::QuantumWalk.run_cycle_walk).
 *
 * Coin space = 2; position space = P. Start: |center> x (|0> + i|1>)/sqrt(2)
 * — the symmetric unbiased coin state. Coin: Hadamard. Shift: coin 0 ->
 * left (x-1), coin 1 -> right (x+1), mod P. Positions are reported as
 * centered offsets x - P/2.
 *
 * The classical comparison is an actual symmetric random walk executed on
 * the same cycle — measured, not asserted as `steps`.
 */
export class ExactQuantumWalk {
  static runCycleWalk(positions: number, steps: number): QuantumWalkResult {
    const P = positions;
    const dim = 2 * P;
    const center = P >> 1;
    const invSqrt2 = 1 / Math.sqrt(2);

    // state[coin * P + x]
    let state = new Array<Complex>(dim).fill(Complex.ZERO);
    state[center] = new Complex(invSqrt2, 0);
    state[P + center] = new Complex(0, invSqrt2);

    for (let s = 0; s < steps; s++) {
      const afterCoin = new Array<Complex>(dim).fill(Complex.ZERO);
      for (let x = 0; x < P; x++) {
        const c0 = state[x];
        const c1 = state[P + x];
        afterCoin[x] = c0.add(c1).scale(invSqrt2);
        afterCoin[P + x] = c0.sub(c1).scale(invSqrt2);
      }
      const afterShift = new Array<Complex>(dim).fill(Complex.ZERO);
      for (let x = 0; x < P; x++) {
        const left = (x - 1 + P) % P;
        const right = (x + 1) % P;
        afterShift[left] = afterCoin[x];
        afterShift[P + right] = afterCoin[P + x];
      }
      state = afterShift;
    }

    const quantumProbs = new Array<number>(P);
    for (let x = 0; x < P; x++) {
      quantumProbs[x] = state[x].abs2() + state[P + x].abs2();
    }

    // Classical symmetric walk on the same cycle, measured.
    let classical = new Array<number>(P).fill(0);
    classical[center] = 1;
    for (let s = 0; s < steps; s++) {
      const nxt = new Array<number>(P).fill(0);
      for (let x = 0; x < P; x++) {
        if (classical[x] > 0) {
          nxt[(x - 1 + P) % P] += 0.5 * classical[x];
          nxt[(x + 1) % P] += 0.5 * classical[x];
        }
      }
      classical = nxt;
    }

    const offsets = new Array<number>(P);
    for (let i = 0; i < P; i++) offsets[i] = i - center;

    const mean = (p: number[]) => p.reduce((a, v, i) => a + v * offsets[i], 0);
    const qm = mean(quantumProbs);
    const cm = mean(classical);
    const varOf = (p: number[], m: number) =>
      p.reduce((a, v, i) => a + v * (offsets[i] - m) ** 2, 0);

    return {
      quantumVariance: varOf(quantumProbs, qm),
      classicalVariance: varOf(classical, cm),
      positions,
      steps,
      distribution: quantumProbs,
    };
  }
}

// ---------------------------------------------------------------------------
// VQE
// ---------------------------------------------------------------------------

export interface VQEResult {
  finalEnergy: number;
  exactGroundEnergy: number;
  iterations: number;
  parameters: number[];
}

/** Jacobi eigenvalue algorithm for real-symmetric matrices (canonical port). */
export class MathEigensolver {
  static hermitianEigenvalues(M: ComplexMatrix, maxIter = 200): number[] {
    const n = M.size;
    const A = M.data.map((r) => r.map((c) => c.re));
    for (let sweep = 0; sweep < maxIter; sweep++) {
      let maxOff = 0;
      let p = 0,
        q = 0;
      for (let i = 0; i < n; i++)
        for (let j = i + 1; j < n; j++) {
          const off = Math.abs(A[i][j]);
          if (off > maxOff) {
            maxOff = off;
            p = i;
            q = j;
          }
        }
      if (maxOff < 1e-12) break;
      const app = A[p][p],
        aqq = A[q][q],
        apq = A[p][q];
      const tau = (aqq - app) / (2 * apq);
      const t =
        tau >= 0
          ? 1 / (tau + Math.sqrt(1 + tau * tau))
          : 1 / (tau - Math.sqrt(1 + tau * tau));
      const c = 1 / Math.sqrt(1 + t * t);
      const s = t * c;
      for (let i = 0; i < n; i++) {
        if (i !== p && i !== q) {
          const aip = A[i][p],
            aiq = A[i][q];
          A[i][p] = A[p][i] = c * aip - s * aiq;
          A[i][q] = A[q][i] = s * aip + c * aiq;
        }
      }
      A[p][p] = c * c * app - 2 * c * s * apq + s * s * aqq;
      A[q][q] = s * s * app + 2 * c * s * apq + c * c * aqq;
      A[p][q] = A[q][p] = 0;
    }
    return A.map((row, i) => row[i]);
  }
}

export class ExactVQE {
  /**
   * Canonical 2-qubit transverse-field Ising Hamiltonian:
   *   H = -J (Z x Z) - h (X x I + I x X),  J = 1, h = 0.5.
   * Spectrum: {-sqrt(2), -1, +1, +sqrt(2)}; ground = -sqrt(2).
   */
  static isingHamiltonian(J = 1.0, h = 0.5): ComplexMatrix {
    const ZZ = QuantumGates.Z.tensor(QuantumGates.Z).scale(-J);
    const XI = QuantumGates.X.tensor(QuantumGates.I).scale(-h);
    const IX = QuantumGates.I.tensor(QuantumGates.X).scale(-h);
    return ZZ.add(XI).add(IX);
  }

  /**
   * Canonical hardware-efficient ansatz (port of VQE.ansatz):
   *   |psi> = CNOT . (Ry(t3) x Ry(t4)) . CNOT . (Ry(t1) x Ry(t2)) |00>
   * theta may carry more than 4 parameters — only the first 4 couple to
   * the ansatz, matching the canonical implementation.
   */
  static ansatz(theta: number[]): QuantumState {
    const ry = (a: number) =>
      ComplexMatrix.fromReal([
        [Math.cos(a / 2), -Math.sin(a / 2)],
        [Math.sin(a / 2), Math.cos(a / 2)],
      ]);
    const cnot = ComplexMatrix.fromReal([
      [1, 0, 0, 0],
      [0, 1, 0, 0],
      [0, 0, 0, 1],
      [0, 0, 1, 0],
    ]);
    let s = QuantumState.fromBasis(4, 0).apply(ry(theta[0]).tensor(ry(theta[1])));
    s = s.apply(cnot);
    s = s.apply(ry(theta[2]).tensor(ry(theta[3])));
    s = s.apply(cnot);
    return s;
  }

  /** Exact parameter-shift gradient: (E(theta + pi/2) - E(theta - pi/2)) / 2. */
  static parameterShiftGradient(H: ComplexMatrix, theta: number[]): number[] {
    const grad = new Array<number>(theta.length);
    const shift = Math.PI / 2;
    for (let i = 0; i < theta.length; i++) {
      const plus = [...theta];
      const minus = [...theta];
      plus[i] += shift;
      minus[i] -= shift;
      grad[i] =
        (ExactVQE.ansatz(plus).expectation(H) -
          ExactVQE.ansatz(minus).expectation(H)) /
        2;
    }
    return grad;
  }

  static optimize(
    H: ComplexMatrix,
    initialTheta: number[],
    iterations = 30,
    learningRate = 0.1,
  ): VQEResult {
    const eigenvalues = MathEigensolver.hermitianEigenvalues(H);
    const exactE0 = Math.min(...eigenvalues);
    const theta = [...initialTheta];
    for (let step = 0; step < iterations; step++) {
      const grad = ExactVQE.parameterShiftGradient(H, theta);
      for (let i = 0; i < theta.length; i++) theta[i] -= learningRate * grad[i];
    }
    return {
      finalEnergy: ExactVQE.ansatz(theta).expectation(H),
      exactGroundEnergy: exactE0,
      iterations,
      parameters: theta,
    };
  }
}
