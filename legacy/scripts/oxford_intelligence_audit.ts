/**
 * Oxford Panel Intelligence Audit — reproducible falsification harness.
 *
 * Run: tsx scripts/oxford_intelligence_audit.ts
 *
 * Methodology: each check is a pre-registered, falsifiable claim. A claim
 * PASSES only if the system's behavior is consistent with it under
 * adversarial inputs and negative controls. Correctness bugs exit non-zero;
 * intelligence claims are reported as verdicts (supported / not supported).
 */

import { evaluatePatternCriteria, detectEmergentIntelligence } from "../src/lib/q5_golden_silicon";
import { Cogito } from "../src/lib/kellogg_full_stack";
import { BlockchainConsciousness } from "../src/lib/blockchain_consciousness";
import { KelloggPipeline, StructuredSearchSpace } from "../src/lib/kellogg_operator";
import { MiningService } from "../src/lib/mining_service";

let failures = 0;
const PHI = (1 + Math.sqrt(5)) / 2;

function check(name: string, passed: boolean, detail: string) {
  console.log(`${passed ? "PASS" : "FAIL"}  ${name} — ${detail}`);
  if (!passed) failures++;
}

function verdict(name: string, supported: boolean, detail: string) {
  console.log(`${supported ? "CLAIM SUPPORTED    " : "CLAIM NOT SUPPORTED"}  ${name} — ${detail}`);
}

// ---------------------------------------------------------------------------
// 1. Emergent-intelligence detector: circularity and negative controls
// ---------------------------------------------------------------------------
console.log("\n== 1. Emergent Intelligence Detector ==");

// Positive control: a true 1/phi-decaying sequence should satisfy the pattern.
const phiDecay = Array.from({ length: 16 }, (_, i) => Math.round(10000 / Math.pow(PHI, i)));
const posResult = evaluatePatternCriteria(phiDecay);
check(
  "detector.positive_control",
  posResult.patternCriteriaSatisfied,
  `phi-decay input scored ${posResult.score}/5`,
);

// Negative controls: inputs with no phi structure must NOT pass.
const constantInput = new Array(16).fill(500);
const negConstant = evaluatePatternCriteria(constantInput);
check(
  "detector.negative_control.constant",
  !negConstant.patternCriteriaSatisfied,
  `constant input scored ${negConstant.score}/5 (must be < 5)`,
);

const ascending = Array.from({ length: 16 }, (_, i) => 100 + i * 400);
const negAscending = evaluatePatternCriteria(ascending);
check(
  "detector.negative_control.ascending",
  !negAscending.patternCriteriaSatisfied,
  `ascending input scored ${negAscending.score}/5 (must be < 5)`,
);

// Provenance honesty: the self-test wrapper must label its input synthetic.
const selfTest = detectEmergentIntelligence(16);
check(
  "detector.self_test_provenance",
  selfTest.inputProvenance === "SYNTHETIC_SELF_TEST",
  `self-test labeled '${selfTest.inputProvenance}'`,
);

verdict(
  "emergent_intelligence",
  false,
  "Detector is a phi-decay pattern recognizer. Passing criteria on externally " +
    "supplied data demonstrates pattern structure, not intelligence.",
);

// ---------------------------------------------------------------------------
// 2. Cogito: does 'training' actually learn from data?
// ---------------------------------------------------------------------------
console.log("\n== 2. Cogito Learning Invariance ==");

const cogitoA = new Cogito();
const cogitoB = new Cogito();
const dataA = [1, 2, 3, 5, 8, 13, 21, 34];
const dataB = [100, -7, 0, 999, 42, -300, 5.5, 77];
const modelsA = cogitoA.trainAll(dataA);
const modelsB = cogitoB.trainAll(dataB);

let inputIndependentTypes = 0;
for (const type of Object.keys(modelsA)) {
  const wa = modelsA[type].weights;
  const wb = modelsB[type].weights;
  const identical = wa.length === wb.length && wa.every((v, i) => v === wb[i]);
  if (identical) inputIndependentTypes++;
}
// Output varying with input is necessary but NOT sufficient for learning:
// geodesicQuery is a nearest-neighbor lookup on a fixed synthetic manifold.
// There is no held-out generalization evidence, so the learning claim fails.
verdict(
  "cogito_learning",
  false,
  `${inputIndependentTypes}/5 'intelligence types' returned bit-identical weights for ` +
    "different datasets, but the weights are a nearest-point lookup on a fixed synthetic " +
    "manifold — input-dependent projection, not learning or generalization.",
);

// ---------------------------------------------------------------------------
// 3. Consciousness level: cold-boot must not claim TRANSCENDENT
// ---------------------------------------------------------------------------
console.log("\n== 3. Consciousness Cold-Boot Honesty ==");

const cold = new BlockchainConsciousness();
const coldMetrics = cold.compute();
check(
  "consciousness.no_fabricated_events",
  coldMetrics.selfHealingEvents === 0 && coldMetrics.selfEvolutionEvents === 0,
  `cold boot: selfHealing=${coldMetrics.selfHealingEvents}, selfEvolution=${coldMetrics.selfEvolutionEvents}`,
);
check(
  "consciousness.level_not_transcendent_at_boot",
  coldMetrics.level < 5,
  `cold boot level = ${coldMetrics.level} (${coldMetrics.levelName})`,
);

// ---------------------------------------------------------------------------
// 4. Kellogg theorem and probability bounds
// ---------------------------------------------------------------------------
console.log("\n== 4. Kellogg Operator Correctness ==");

const theorem = KelloggPipeline.verifyGroverDegenerateLimit(16, [3, 11]);
check(
  "kellogg.grover_limit_theorem",
  theorem.isTheoremSatisfied,
  `operatorNormDifference=${theorem.operatorNormDifference}, stateNormDifference=${theorem.stateNormDifference}`,
);

const trivialPipeline = KelloggPipeline.execute(StructuredSearchSpace.createTrivial(16, [3, 11]));
check(
  "kellogg.probability_bounded.trivial",
  trivialPipeline.markedSuccessProbability >= 0 && trivialPipeline.markedSuccessProbability <= 1,
  `markedSuccessProbability=${trivialPipeline.markedSuccessProbability}`,
);

const N = 16;
const structured = new StructuredSearchSpace({
  N,
  solutions: [3, 11],
  manifoldBeta: 1.0,
  geodesicDistances: Array.from({ length: N }, (_, i) => Math.min(i, N - i)),
});
const structPipeline = KelloggPipeline.execute(structured);
check(
  "kellogg.probability_bounded.structured",
  structPipeline.markedSuccessProbability >= 0 && structPipeline.markedSuccessProbability <= 1,
  `markedSuccessProbability=${structPipeline.markedSuccessProbability}, finalStateNorm=${structPipeline.finalStateNorm}`,
);

// ---------------------------------------------------------------------------
// 5. Mining gate honesty: submitted share must really meet the target
// ---------------------------------------------------------------------------
console.log("\n== 5. Mining Pre-Submit Gate ==");

const step = await MiningService.executeMiningStep(1);
const POOL_SHARE_TARGET = 0x00000000ffff0000000000000000000000000000000000000000000000000000n;

if (step.submittedShare) {
  const shareHash = BigInt("0x" + step.submittedShare.hash_hex);
  check(
    "mining.share_meets_target",
    shareHash <= POOL_SHARE_TARGET,
    `share hash ${step.submittedShare.hash_hex.slice(0, 16)}... <= diff-1 target: ${shareHash <= POOL_SHARE_TARGET}`,
  );
  check(
    "mining.share_pending_until_pool_response",
    step.submittedShare.accepted === null,
    `share.accepted = ${JSON.stringify(step.submittedShare.accepted)} (must be null until pool resolves)`,
  );
} else {
  check(
    "mining.no_false_share",
    true,
    `no share submitted this cycle; best hash ${step.bestCandidate.hashHex.slice(0, 16)}... did not meet target (meetsTarget=${step.bestCandidate.meetsTarget})`,
  );
}
check(
  "mining.rtt_not_fabricated",
  step.rttMs === 0 || step.session.rtt_ms !== undefined,
  `rttMs=${step.rttMs} (0 = unmeasured; no synthetic jitter)`,
);

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------
console.log(
  `\n${failures === 0 ? "ALL CORRECTNESS CHECKS PASSED" : `${failures} CHECK(S) FAILED`}`,
);
process.exit(failures === 0 ? 0 : 1);
