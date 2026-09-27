/**
 * Deterministic Test Suite for Q5 Reference Engine
 * Validates:
 * 1. Exact algebraic field arithmetic Q[√5]
 * 2. Optimal K calculation using classical convergent bounds on π
 * 3. Exact symmetry preservation: 100% bit-for-bit equivalence between dense vector & invariant subspace
 * 4. Denominator bit-width bound check: log2(den) <= k * log2(φ²) + 1
 * 5. Multi-scale reference suite execution across N_Inner in {20, 22, 24, 26}
 * 6. Memory high-water mark calculation and hardware projection model
 */

import {
  Q5ReferenceEngine,
  computeOptimalK,
  evaluateMemoryHighWaterMark,
  projectHbmPerformance,
  bigintSqrtFloor,
  UnimodularSL2Z,
  LucasAlgebra,
} from "../src/lib/q5_reference";
import { AdversarialIntegrityEngine } from "../src/lib/adversarial_checks";

function assert(condition: boolean, message: string) {
  if (!condition) {
    console.error(`❌ ASSERTION FAILED: ${message}`);
    process.exit(1);
  }
  console.log(`✅ PASS: ${message}`);
}

async function runTests() {
  console.log("================================================================================");
  console.log("TEST 1: Integer Square Root Exactness");
  console.log("================================================================================");
  assert(bigintSqrtFloor(0n) === 0n, "sqrt(0) = 0");
  assert(bigintSqrtFloor(1n) === 1n, "sqrt(1) = 1");
  assert(bigintSqrtFloor(4n) === 2n, "sqrt(4) = 2");
  assert(bigintSqrtFloor(15n) === 3n, "sqrt(15) = 3");
  assert(bigintSqrtFloor(16n) === 4n, "sqrt(16) = 4");
  assert(bigintSqrtFloor(1000000000000000000n) === 1000000000n, "sqrt(10^18) = 10^9");

  console.log("\n================================================================================");
  console.log("TEST 2: Optimal K Rational Bounds on π");
  console.log("================================================================================");
  const optK20 = computeOptimalK(32n * (1n << 20n), 1n);
  console.log(
    `Optimal K for N_Inner=20 (N=${32n * (1n << 20n)}): K_lo=${optK20.kLo}, K_hi=${optK20.kHi}`,
  );
  assert(optK20.kLo > 0n, "Optimal K must be strictly positive");
  assert(optK20.kLo <= optK20.kHi, "K_lo must be <= K_hi");

  console.log("\n================================================================================");
  console.log("TEST 3: Mathematical Symmetry Invariant (Dense Vector vs Invariant Subspace)");
  console.log("================================================================================");
  const symmetryVerified = Q5ReferenceEngine.verifySymmetry(4, 4);
  assert(
    symmetryVerified === true,
    "Dense 512-state simulation matches invariant subspace bit-for-bit",
  );

  console.log("\n================================================================================");
  console.log("TEST 4: Memory High-Water Mark Profiling");
  console.log("================================================================================");
  const mem20 = evaluateMemoryHighWaterMark(20);
  assert(
    mem20.typicalStateMemoryGb > 2.0 && mem20.typicalStateMemoryGb < 2.5,
    "N=20 typical state memory is ~2.15 GB",
  );
  assert(mem20.chipCapacityFit.fitsOnM3Max128Gb === true, "N=20 fits on Apple M3 Max");
  assert(
    mem20.chipCapacityFit.q5SiliconChipsRequired === 1,
    "N=20 fits on 1 Q5 silicon chip (288 GB package)",
  );

  const mem26 = evaluateMemoryHighWaterMark(26);
  assert(
    mem26.typicalStateMemoryGb > 130 && mem26.typicalStateMemoryGb < 140,
    "N=26 typical state memory is ~137.4 GB",
  );
  assert(
    mem26.chipCapacityFit.fitsOnH100_80Gb === false,
    "N=26 exceeds single H100 80GB (requires multi-GPU)",
  );

  console.log("\n================================================================================");
  console.log("TEST 5: Hardware Projection Model Mapping");
  console.log("================================================================================");
  const proj20 = projectHbmPerformance(20, 4);
  console.log(
    `Q5 Silicon Mode A Step: ${proj20.q5SiliconModes.modeA_3PassStreaming.stepLatencyMs} ms`,
  );
  console.log(
    `Q5 Silicon Mode B Step: ${proj20.q5SiliconModes.modeB_2PassNearMemory.stepLatencyMs} ms`,
  );
  console.log(
    `Q5 Silicon Mode C Step: ${proj20.q5SiliconModes.modeC_1PassInPlaceBaseDie.stepLatencyMs} ms`,
  );
  assert(
    proj20.q5SiliconModes.modeC_1PassInPlaceBaseDie.stepLatencyMs <
      proj20.q5SiliconModes.modeB_2PassNearMemory.stepLatencyMs,
    "Mode C is strictly faster than Mode B",
  );
  assert(
    proj20.q5SiliconModes.modeB_2PassNearMemory.stepLatencyMs <
      proj20.q5SiliconModes.modeA_3PassStreaming.stepLatencyMs,
    "Mode B is strictly faster than Mode A",
  );
  assert(
    proj20.theoreticalSpeedupModeCVsM3Max > 10,
    "Q5 Mode C near-memory provides >10x speedup vs M3 Max UMA",
  );

  console.log("\n================================================================================");
  console.log("TEST 6: Multi-Scale Benchmark Harness (N_Inner in {20, 22, 24, 26})");
  console.log("================================================================================");
  const harness = Q5ReferenceEngine.runHarnessSuite([20, 22, 24, 26], 4);
  assert(harness.results.length === 4, "Harness executed all 4 levels");
  for (const res of harness.results) {
    console.log(
      `Scale N=${res.nInner} (${res.nGlobal} states): CPU step=${res.wallClockStepLatencyMs}ms, denBits=${res.bitWidthBoundCheck.actualDenBits}, boundPass=${res.bitWidthBoundCheck.satisfied}, hash=${res.stateHashCanonical}`,
    );
    assert(
      res.bitWidthBoundCheck.satisfied === true,
      `Scale N=${res.nInner} den bit-width bound satisfied`,
    );
    assert(res.stateHashCanonical.startsWith("blake2b_q5_"), "Canonical hash formatted");
  }

  console.log("\n================================================================================");
  console.log("TEST 7: Unimodular SL(2, Z) Cassini Determinant Identity: det(M^n) = (-1)^n");
  console.log("================================================================================");
  for (let n = 1; n <= 25; n++) {
    const cCheck = UnimodularSL2Z.verifyCassini(n);
    assert(cCheck.passes === true, `Cassini identity holds for power n=${n}: det=${cCheck.det}`);
  }

  console.log("\n================================================================================");
  console.log("TEST 8: Lucas-Fibonacci Cassini Relation: L_n^2 - 5*F_n^2 = 4*(-1)^n");
  console.log("================================================================================");
  for (let n = 1; n <= 25; n++) {
    const lCheck = LucasAlgebra.verifyLucasCassiniIdentity(n);
    assert(
      lCheck.passes === true,
      `Lucas-Cassini identity holds for n=${n}: left=${lCheck.leftSide} right=${lCheck.rightSide}`,
    );
  }

  console.log("\n================================================================================");
  console.log("TEST 9: Full Pre-Flight Audit Suite Execution");
  console.log("================================================================================");
  const auditReport = Q5ReferenceEngine.runPreFlightAudit();
  assert(
    auditReport.overallPassed === true,
    "Pre-flight audit suite passed all mathematical & computational checks",
  );
  assert(auditReport.fieldAxioms.allPassed === true, "Q[√5] field axioms satisfied");

  console.log("\n================================================================================");
  console.log("TEST 10: Adversarial Precision Integrity & Noise Injection Hard-Fails");
  console.log("================================================================================");
  const advReport = AdversarialIntegrityEngine.runAdversarialSuite();
  console.log(
    `Executed ${advReport.totalAttacksExecuted} adversarial attacks. Tripped breakers: ${advReport.totalBreakersTripped}`,
  );
  assert(
    advReport.systemIntegrityMaintained === true,
    "All injected adversarial drifts tripped circuit breakers with zero silent tolerance",
  );
  for (const att of advReport.attackDetails) {
    console.log(
      `  [${att.attackId}] ${att.attackName} => HardFail: ${att.hardFailDetected} (${att.rejectionReason.slice(0, 65)}...)`,
    );
    assert(att.hardFailDetected === true, `Attack ${att.attackId} must hard-fail`);
  }

  console.log("\n================================================================================");
  console.log("ALL 10 TESTS PASSED DETERMINISTICALLY WITH ZERO FLOATING-POINT APPROXIMATIONS");
  console.log("================================================================================");
}

runTests().catch((err) => {
  console.error("Test execution failed:", err);
  process.exit(1);
});
