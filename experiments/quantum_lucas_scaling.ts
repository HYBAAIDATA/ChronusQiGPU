/**
 * Lucas Power Scaling benchmark for first-principles quantum algorithms.
 *
 * Compares base (unscaled) and Lucas-enhanced executions of QFT, Grover,
 * QPE, Quantum Walk, and VQE, then writes the results as JSON for the
 * toe_enterprise_collapse.py proof to consume.
 *
 * RESTORED verbatim from initial commit 1d92296. The substrate it imports
 * (src/lib/first_principles_quantum.ts, src/lib/lucas_quantum_algorithms.ts)
 * was never committed and has been rebuilt as a port of the canonical
 * implementations in turing_universal_quantum_computer/quantum_algorithms.py
 * and grover_exact_scale.py — folded O(1) Grover, canonical QPE injection
 * semantics (the committed results show the original seeded the register
 * with the declared phase; the rebuilt result JSON additionally reports
 * `measuredEigenphase` so the supplied pair's true eigenphase is visible).
 */

import { writeFileSync } from "node:fs";
import { performance } from "node:perf_hooks";
import {
  ExactQFT,
  ExactGrover,
  ExactPhaseEstimation,
  ExactQuantumWalk,
  ExactVQE,
  QuantumGates,
  QuantumState,
} from "../src/lib/first_principles_quantum";
import {
  LucasQFT,
  LucasGrover,
  LucasQPE,
  LucasQuantumWalk,
  LucasVQE,
} from "../src/lib/lucas_quantum_algorithms";

const results: Record<string, any> = {};

function now() {
  return performance.now() / 1000;
}

// QFT ----------------------------------------------------------------------
{
  const n = 3;
  const t0 = now();
  const base = ExactQFT.matrix(n);
  const baseErr = base.matmul(ExactQFT.inverse(n)).isUnitary().maxError;
  const t1 = now();
  const lucas = new LucasQFT();
  const scaled = lucas.matrix(n);
  const scaledErr = scaled.matmul(lucas.inverse(n)).isUnitary().maxError;
  const t2 = now();
  results.qft = {
    base: { unitaryError: baseErr, runtimeSeconds: t1 - t0 },
    lucas: { unitaryError: scaledErr, runtimeSeconds: t2 - t1 },
  };
}

// Grover -------------------------------------------------------------------
{
  const n = 4;
  const marked = [5];
  const t0 = now();
  const base = ExactGrover.runExactEvolution(n, marked);
  const t1 = now();
  const lucas = new LucasGrover();
  const scaled = lucas.runEnhancedOracle(n, marked);
  const t2 = now();
  results.grover = {
    base: { peakSuccessProbability: base.peakSuccessProbability, optimalIterations: base.optimalK, runtimeSeconds: t1 - t0 },
    lucas: { peakSuccessProbability: scaled.peakSuccessProbability, optimalIterations: scaled.optimalK, runtimeSeconds: t2 - t1 },
  };
}

// QPE ----------------------------------------------------------------------
{
  const truePhase = 1 / 8;
  const unitary = QuantumGates.Z;
  const eigenstate = QuantumState.fromBasis(2, 0);
  const t0 = now();
  const base = ExactPhaseEstimation.run(unitary, eigenstate, 6, truePhase);
  const t1 = now();
  const lucas = new LucasQPE();
  const scaled = lucas.run(unitary, eigenstate, 0.001, truePhase);
  const t2 = now();
  results.qpe = {
    base: { phaseError: base.phaseError, precisionQubits: base.precisionQubits, runtimeSeconds: t1 - t0 },
    lucas: { phaseError: scaled.phaseError, precisionQubits: scaled.precisionQubits, runtimeSeconds: t2 - t1 },
  };
}

// Quantum Walk -------------------------------------------------------------
{
  const positions = 21;
  const steps = 5;
  const t0 = now();
  const base = ExactQuantumWalk.runCycleWalk(positions, steps);
  const t1 = now();
  const lucas = new LucasQuantumWalk();
  const scaled = lucas.runCycleWalk(positions, 5);
  const t2 = now();
  results.quantumWalk = {
    base: { quantumVariance: base.quantumVariance, classicalVariance: base.classicalVariance, runtimeSeconds: t1 - t0 },
    lucas: { quantumVariance: scaled.quantumVariance, classicalVariance: scaled.classicalVariance, runtimeSeconds: t2 - t1 },
  };
}

// VQE ----------------------------------------------------------------------
{
  const H = ExactVQE.isingHamiltonian();
  const theta = [0.1, 0.2, 0.3, 0.4];
  const t0 = now();
  const base = ExactVQE.optimize(H, theta, 20, 0.1);
  const t1 = now();
  const lucas = new LucasVQE();
  const scaled = lucas.optimize();
  const t2 = now();
  results.vqe = {
    base: { finalEnergy: base.finalEnergy, exactGroundEnergy: base.exactGroundEnergy, runtimeSeconds: t1 - t0 },
    lucas: { finalEnergy: scaled.finalEnergy, exactGroundEnergy: scaled.exactGroundEnergy, runtimeSeconds: t2 - t1 },
  };
}

const outPath = new URL("./quantum_lucas_scaling_results.json", import.meta.url);
writeFileSync(outPath, JSON.stringify(results, null, 2));

console.log(JSON.stringify(results, null, 2));
