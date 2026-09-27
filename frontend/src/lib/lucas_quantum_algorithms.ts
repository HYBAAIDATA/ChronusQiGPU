/**
 * Lucas-Scaled Quantum Algorithms (rebuilt).
 *
 * Rebuild of the never-committed substrate imported by
 * experiments/quantum_lucas_scaling.ts, ported from the canonical Python
 * semantics in
 *   turing_universal_quantum_computer/.../quantum_algorithms.py
 *   turing_universal_quantum_computer/.../grover_exact_scale.py
 *   mining/search.py
 *
 * The port is validated against the results JSON committed in 1d92296 —
 * it reproduces every committed Lucas figure exactly:
 *   grover lucas: optimalK=1, peak=0.68359375 = 175/256
 *                 (oracle expanded to marked u {L_i < N}: M=7 -> sin^2(3t))
 *   qpe lucas:    precisionQubits=4  (int(clamp(log_phi(eps), 4, 8)))
 *   walk lucas:   classicalVariance=8 (steps' = int(steps * phi) = int(8.09))
 *   vqe lucas:    lr = 0.1 * sqrt(phi), 32-parameter adaptive ansatz
 *
 * "Lucas" here means the repo's own doctrine: L_n is exact integer resource
 * scaling; psi = -1/phi is the Pisot conjugate; |psi|^n is the convergence
 * rate. No result is projected — every number is computed.
 *
 * NOTE: src/lib/lucas_pisot_separate.ts is NOT imported — it has a dead
 * dependency (./m3_igpu_scaler, never committed). PHI/PSI are derived here.
 *
 * Order of Truth: MATHEMATICAL & COMPUTATIONAL
 */

import { ExactSequenceMath } from "./exact_math";
import {
  Complex,
  ComplexMatrix,
  QuantumState,
  QuantumGates,
  ExactGrover,
  ExactPhaseEstimation,
  ExactQuantumWalk,
  ExactVQE,
  GroverResult,
  QPEResult,
  QuantumWalkResult,
  VQEResult,
} from "./first_principles_quantum";

export const PHI = (1 + Math.sqrt(5)) / 2;
export const PSI = (1 - Math.sqrt(5)) / 2;

/** Exact Lucas number L_n as a JS number (L_n = phi^n + psi^n). */
export function lucasNumber(n: number): number {
  return Number(ExactSequenceMath.lucas(n));
}

/**
 * Canonical LucasEngine.find_optimal_scaling_point: the ladder
 * {10, 12, 15, 18, 20} indexed by problem size, log2-based.
 */
export function optimalLucasPower(problemSize: number): number {
  const ladder = [10, 12, 15, 18, 20];
  const idx = Math.min(
    ladder.length - 1,
    Math.max(0, Math.floor(Math.log2(Math.max(problemSize, 2))) - 1),
  );
  return ladder[idx];
}

// ---------------------------------------------------------------------------
// Lucas QFT — exact phase-index arithmetic
// ---------------------------------------------------------------------------

/**
 * The QFT is a fixed unitary; Lucas scaling cannot change its math without
 * breaking unitarity. The Lucas variant changes the *evaluation path*:
 * phase indices jk mod 2^n are computed in exact BigInt arithmetic (the
 * Lucas integer substrate) rather than floating modular reduction. The
 * resulting matrix is the same DFT, so the measured unitary error is a
 * real check, not a restated identity.
 */
export class LucasQFT {
  matrix(n: number): ComplexMatrix {
    return this.dft(1 << n, +1);
  }
  inverse(n: number): ComplexMatrix {
    return this.dft(1 << n, -1);
  }

  private dft(dim: number, sign: 1 | -1): ComplexMatrix {
    const norm = 1 / Math.sqrt(dim);
    const big = BigInt(dim);
    const m = ComplexMatrix.zero(dim);
    for (let j = 0; j < dim; j++) {
      for (let k = 0; k < dim; k++) {
        // Exact integer residue: (j*k) mod dim in BigInt.
        const residue = (BigInt(j) * BigInt(k)) % big;
        const angle = (sign * 2 * Math.PI * Number(residue)) / dim;
        m.set(j, k, Complex.polar(angle).scale(norm));
      }
    }
    return m;
  }
}

// ---------------------------------------------------------------------------
// Lucas Grover — attractor-enhanced oracle
// ---------------------------------------------------------------------------

/**
 * Port of GroverSearch.lucas_enhanced_oracle: the oracle marks the requested
 * states AND the Lucas-attractor states {L_i : L_i < N}. Amplitude then
 * concentrates on the enlarged set — for N=16 the marked set grows to M=7
 * and the first-arc peak lands at k=1 with P = 175/256 exactly.
 * The evolution itself is the folded two-amplitude iterate — O(1) per
 * step, no statevector simulation.
 */
export class LucasGrover {
  runEnhancedOracle(n: number, marked: number[]): GroverResult {
    const N = 1 << n;
    const enhanced = new Set(marked);
    for (let i = 0; i < 32; i++) {
      const l = lucasNumber(i);
      if (l >= N) break;
      enhanced.add(l);
    }
    return ExactGrover.runExactEvolution(n, [...enhanced]);
  }
}

// ---------------------------------------------------------------------------
// Lucas QPE — Lucas-selected precision register
// ---------------------------------------------------------------------------

/**
 * Port of QuantumPhaseEstimation.lucas_precision_bits:
 *   bits = int(clamp(log_phi(epsilon), 4, 8))
 * For epsilon = 0.001 this yields 4 — the committed original figure.
 * Estimation itself is the canonical counting-register + inverse-DFT run.
 */
export class LucasQPE {
  run(
    unitary: ComplexMatrix,
    eigenstate: QuantumState,
    epsilon: number,
    truePhase: number,
  ): QPEResult {
    const lucasPower = Math.log(epsilon) / Math.log(PHI);
    const bits = Math.floor(Math.max(4, Math.min(8, lucasPower)));
    return ExactPhaseEstimation.run(unitary, eigenstate, bits, truePhase);
  }
}

// ---------------------------------------------------------------------------
// Lucas Quantum Walk — phi-scaled step budget
// ---------------------------------------------------------------------------

/**
 * Port of QuantumWalk.run_lucas / lucas_walk_steps:
 *   steps' = int(steps * phi)   (5 -> 8, the committed figure)
 * The walk dynamics are the canonical center-seeded Hadamard-coin walk;
 * only the resource budget is Lucas-scaled.
 */
export class LucasQuantumWalk {
  runCycleWalk(positions: number, steps: number): QuantumWalkResult {
    return ExactQuantumWalk.runCycleWalk(positions, Math.trunc(steps * PHI));
  }
}

// ---------------------------------------------------------------------------
// Lucas VQE — adaptive ansatz + phi^{1/2} learning rate
// ---------------------------------------------------------------------------

/**
 * Port of VQE.optimize_lucas:
 *   - ansatz parameters from lucas_adaptive_ansatz: min(power, 8) * 4 values
 *     0.1*(i+1) (power selected from the ladder by problem size; for a
 *     2-qubit problem the ladder gives power 10 -> 32 parameters, of which
 *     the 4-parameter ansatz consumes the first four: 0.1..0.4)
 *   - learning rate 0.1 * sqrt(phi)
 *   - 30 parameter-shift iterations on the canonical Ising Hamiltonian
 *     H = -ZZ - 0.5(XI + IX), exact ground energy -sqrt(2) from the Jacobi
 *     eigensolver.
 */
export class LucasVQE {
  optimize(problemSize = 2): VQEResult {
    const H = ExactVQE.isingHamiltonian();
    const power = optimalLucasPower(problemSize);
    const theta = Array.from(
      { length: Math.min(power, 8) * 4 },
      (_, i) => 0.1 * (i + 1),
    );
    const lr = 0.1 * Math.sqrt(PHI);
    return ExactVQE.optimize(H, theta, 30, lr);
  }
}

// Re-export shared types the harness consumes via these classes.
export {
  ExactGrover,
  ExactPhaseEstimation,
  ExactQuantumWalk,
  ExactVQE,
  QuantumGates,
  QuantumState,
};
