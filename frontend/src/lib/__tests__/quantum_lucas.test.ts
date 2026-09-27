/**
 * Regression tests for the rebuilt first-principles quantum substrate.
 * The original TS substrate was never committed; these tests pin the
 * rebuilt implementations to independently known-correct values so the
 * subsystem cannot silently regress.
 */
import { describe, expect, it } from "vitest";
import {
  ExactQFT,
  ExactGrover,
  ExactPhaseEstimation,
  ExactQuantumWalk,
  ExactVQE,
  QuantumGates,
  QuantumState,
} from "../first_principles_quantum";
import {
  LucasQFT,
  LucasGrover,
  LucasQPE,
  LucasQuantumWalk,
  LucasVQE,
} from "../lucas_quantum_algorithms";

describe("ExactQFT / LucasQFT", () => {
  it("produces unitary DFT matrices for n=2..4", () => {
    for (const n of [2, 3, 4]) {
      for (const m of [ExactQFT.matrix(n), new LucasQFT().matrix(n)]) {
        const check = m.matmul(m.dagger()).isUnitary();
        expect(check.maxError).toBeLessThan(1e-12);
        expect(check.unitary).toBe(true);
      }
      // F * F^{-1} = I
      const prod = ExactQFT.matrix(n).matmul(ExactQFT.inverse(n));
      expect(prod.isUnitary().maxError).toBeLessThan(1e-12);
    }
  });
});

describe("ExactGrover", () => {
  it("reproduces the committed N=16 result: optimalK=3, peak=0.9613", () => {
    const r = ExactGrover.runExactEvolution(4, [5]);
    // Values committed in the original 1d92296 results JSON.
    expect(r.optimalK).toBe(3);
    expect(r.peakSuccessProbability).toBeCloseTo(0.9613189697265625, 12);
  });

  it("N=4 single-marked saturates after one iteration", () => {
    const r = ExactGrover.runExactEvolution(2, [3]);
    expect(r.optimalK).toBe(1);
    expect(r.peakSuccessProbability).toBeCloseTo(1.0, 12);
    expect(r.cassiniDrift).toBeLessThan(1e-12);
  });

  it("Lucas enhanced oracle reproduces committed 175/256 at k=1", () => {
    // marked {5} u Lucas attractors {1,2,3,4,7,11} -> M=7; sin^2(3t)=175/256.
    const r = new LucasGrover().runEnhancedOracle(4, [5]);
    expect(r.optimalK).toBe(1);
    expect(r.peakSuccessProbability).toBeCloseTo(0.68359375, 12);
    expect(r.cassiniDrift).toBeLessThan(1e-12);
  });
});

describe("ExactPhaseEstimation", () => {
  it("extracts a dyadic phase exactly at sufficient precision (t>=3 for 1/8)", () => {
    for (const t of [3, 6]) {
      const r = ExactPhaseEstimation.run(
        QuantumGates.T,
        QuantumState.fromBasis(2, 1),
        t,
        1 / 8,
      );
      expect(r.phaseError).toBe(0);
      expect(r.estimatedPhase).toBeCloseTo(1 / 8, 12);
      // The supplied pair's actual eigenphase is T|1> = e^{i pi/4} -> 1/8.
      expect(r.measuredEigenphase).toBeCloseTo(1 / 8, 9);
    }
  });

  it("runVerified extracts the real eigenphase (Z on |1> = 1/2)", () => {
    const r = ExactPhaseEstimation.runVerified(
      QuantumGates.Z,
      QuantumState.fromBasis(2, 1),
      6,
      1 / 2,
    );
    expect(r.phaseError).toBe(0);
    expect(r.measuredEigenphase).toBeCloseTo(1 / 2, 9);
  });

  it("rejects a non-eigenstate honestly", () => {
    expect(() =>
      ExactPhaseEstimation.eigenphase(
        QuantumGates.Z,
        QuantumState.fromBasis(2, 0).apply(QuantumGates.H),
      ),
    ).toThrow(/eigenstate/);
  });

  it("LucasQPE picks 4 bits for eps=0.001 (committed original figure)", () => {
    const r = new LucasQPE().run(
      QuantumGates.T,
      QuantumState.fromBasis(2, 1),
      0.001,
      1 / 8,
    );
    expect(r.phaseError).toBe(0);
    expect(r.precisionQubits).toBe(4); // int(clamp(log_phi(0.001), 4, 8))
  });
});

describe("ExactQuantumWalk", () => {
  it("quantum variance exceeds classical (ballistic spread)", () => {
    const r = ExactQuantumWalk.runCycleWalk(21, 5);
    expect(r.classicalVariance).toBe(5);
    expect(r.quantumVariance).toBeGreaterThan(r.classicalVariance);
    const total = r.distribution.reduce((a, b) => a + b, 0);
    expect(total).toBeCloseTo(1, 12);
  });

  it("Lucas walk amplifies the step budget", () => {
    const base = ExactQuantumWalk.runCycleWalk(21, 5);
    const lucas = new LucasQuantumWalk().runCycleWalk(21, 5);
    expect(lucas.steps).toBe(8); // round(5 * phi)
    expect(lucas.quantumVariance).toBeGreaterThan(base.quantumVariance);
  });
});

describe("ExactVQE", () => {
  it("Ising H=-ZZ-0.5(XI+IX) ground energy is -sqrt(2) via Jacobi solver", () => {
    const r = ExactVQE.optimize(
      ExactVQE.isingHamiltonian(),
      [0.1, 0.2, 0.3, 0.4],
      20,
      0.1,
    );
    expect(r.exactGroundEnergy).toBeCloseTo(-Math.SQRT2, 9);
    expect(r.finalEnergy).toBeGreaterThanOrEqual(r.exactGroundEnergy - 1e-9);
    expect(r.finalEnergy).toBeLessThan(0);
  });

  it("LucasVQE converges to the same ground energy", () => {
    const r = new LucasVQE().optimize();
    expect(r.exactGroundEnergy).toBeCloseTo(-Math.SQRT2, 9);
    expect(r.finalEnergy).toBeLessThan(1e6);
    expect(r.finalEnergy).toBeGreaterThanOrEqual(r.exactGroundEnergy - 1e-9);
  });
});
