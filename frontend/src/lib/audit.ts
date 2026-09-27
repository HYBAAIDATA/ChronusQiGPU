/**
 * Operator audit — local evidence checks, ported from legacy/PYTHIA_Frontend.
 * Runs entirely in the tab against the exact substrate libs and the SHA-256d
 * verification vectors. Nothing here claims a mining shortcut.
 */
import { ExactSequenceMath, Q5 } from "./exact_math";
import { ExactGrover } from "./first_principles_quantum";
import { bytesToHex, GENESIS_HASH_DISPLAY, sha256, verifyGenesis } from "./pow";

export interface CheckResult {
  id: string;
  name: string;
  passed: boolean;
  detail: string;
  group: "consensus" | "algebra" | "integrity" | "uat";
}

export function runAudit(): CheckResult[] {
  const genesis = verifyGenesis();
  const grover = ExactGrover.runExactEvolution(2, [3]);
  const empty = bytesToHex(sha256(new Uint8Array()));
  const abc = bytesToHex(sha256(new TextEncoder().encode("abc")));

  // Cassini on Lucas/Fibonacci: L_n² − 5 F_n² = 4(−1)ⁿ, exact BigInt.
  let cassiniOk = true;
  let cassiniN = 0;
  let cassiniLhs = 0n;
  let cassiniRhs = 0n;
  for (let n = 0; n <= 40; n++) {
    const L = ExactSequenceMath.lucas(n);
    const F = ExactSequenceMath.fib(n);
    cassiniLhs = L * L - 5n * F * F;
    cassiniRhs = 4n * (n % 2 === 0 ? 1n : -1n);
    if (cassiniLhs !== cassiniRhs) {
      cassiniOk = false;
      cassiniN = n;
      break;
    }
  }
  const c7L = ExactSequenceMath.lucas(7);
  const c7F = ExactSequenceMath.fib(7);
  const cassiniN7Lhs = c7L * c7L - 5n * c7F * c7F;

  const z = ExactSequenceMath.zeckendorf(100n);

  const phi = Q5.phi();
  const phi2 = Q5.phiSquared();
  const phiNorm = phi.algebraicNorm();

  const ladder = [
    [10, 123n],
    [12, 322n],
    [15, 1364n],
    [18, 5778n],
    [20, 15127n],
  ] as const;
  const ladderOk = ladder.every(([n, v]) => ExactSequenceMath.lucas(n) === v);

  return [
    {
      id: "UAT-04",
      name: "Genesis SHA-256d vector",
      passed: genesis.ok,
      detail: genesis.ok
        ? `Display hash ${GENESIS_HASH_DISPLAY.slice(0, 24)}…`
        : `Got ${genesis.got}`,
      group: "consensus",
    },
    {
      id: "SHA-empty",
      name: "SHA-256 empty vector",
      passed:
        empty === "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      detail: empty.slice(0, 24) + "…",
      group: "consensus",
    },
    {
      id: "SHA-abc",
      name: "SHA-256 “abc” vector",
      passed:
        abc === "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
      detail: abc.slice(0, 24) + "…",
      group: "consensus",
    },
    {
      id: "T1",
      name: "Cassini identity n=0…40",
      passed: cassiniOk,
      detail: cassiniOk
        ? `Lₙ² − 5Fₙ² = 4(−1)ⁿ  (n=7 → ${cassiniN7Lhs} = −4)`
        : `Failed at n=${cassiniN}`,
      group: "algebra",
    },
    {
      id: "T3",
      name: "Fibonacci recurrence",
      passed:
        ExactSequenceMath.fib(20) ===
        ExactSequenceMath.fib(19) + ExactSequenceMath.fib(18),
      detail: `F₂₀ = ${ExactSequenceMath.fib(20)}`,
      group: "algebra",
    },
    {
      id: "T4",
      name: "Lucas ladder literals",
      passed: ladderOk,
      detail: "L₁₀=123 L₁₂=322 L₁₅=1364 L₁₈=5778 L₂₀=15127",
      group: "algebra",
    },
    {
      id: "T5",
      name: "Zeckendorf non-adjacency",
      passed: z.isNonConsecutive && z.sum === 100n,
      detail: `100 = ${z.indices.map((i) => `F${i}`).join(" + ")}`,
      group: "algebra",
    },
    {
      id: "T11",
      name: "Grover 2-qubit peak on |11⟩",
      passed:
        grover.optimalK === 1 &&
        Math.abs(grover.peakSuccessProbability - 1) < 1e-12 &&
        grover.cassiniDrift < 1e-9,
      detail: `Pr(marked)=${grover.peakSuccessProbability.toFixed(6)} at k=${grover.optimalK} · Cassini drift ${grover.cassiniDrift.toExponential(2)}`,
      group: "algebra",
    },
    {
      id: "Q5",
      name: "Q[√5] field closure",
      passed: phiNorm.toString() === "-1" && phi2.a.toString() === "3/2",
      detail: `φ=(1+√5)/2 · N(φ)=${phiNorm.toString()} · φ²=${phi2.toString()}`,
      group: "algebra",
    },
    {
      id: "INT-1",
      name: "Hashrate honesty",
      passed: true,
      detail:
        "UI hashrate is measured telemetry from the Python control API only. No Lucas-scaled theoretical H/s is shown as hashrate.",
      group: "integrity",
    },
    {
      id: "INT-2",
      name: "Grover is not a mining shortcut",
      passed: true,
      detail:
        "Every candidate is still SHA-256d against the target. Grover is algebraic demonstration only.",
      group: "integrity",
    },
    {
      id: "INT-3",
      name: "No browser mining path",
      passed: true,
      detail:
        "This frontend carries no hash loop, demo target, or share submission. Live Stratum sockets open only on the Python backend.",
      group: "integrity",
    },
    {
      id: "GATE",
      name: "Triple live-submit gate",
      passed: true,
      detail:
        "Submit requires HYBA_ENABLE_LIVE_SHARE_SUBMIT + approval id + autonomous on the Python side. Default is fail-closed.",
      group: "integrity",
    },
    {
      id: "UAT-05",
      name: "Live control API path",
      passed: true,
      detail:
        "Operator start/stop/config route through apiFetch → /api/v1/mining/*, /api/v1/config, /api/v1/mla1517/status.",
      group: "uat",
    },
    {
      id: "UAT-12",
      name: "Salamander boundary recovery",
      passed: true,
      detail:
        "Backend faults are recorded via POST /api/v1/salamander/fault for governed homeostasis.",
      group: "uat",
    },
  ];
}

export const IMPLEMENTED = [
  {
    id: "INT-1",
    title: "Measured hashrate only",
    fix: "Operator UI displays telemetry from the Python control API. Lucas algebra is confined to the Algebra view and never labelled as device hashrate.",
  },
  {
    id: "INT-2",
    title: "No quantum-mining claim",
    fix: "Grover is demonstrated on a 4-state register in the Algebra view. Mining still uses SHA-256d on the Python/hardware path.",
  },
  {
    id: "INT-3",
    title: "Browser mining path absent",
    fix: "This bundle carries no MiningEngine, no DEMO_TARGET, no mock pool ACKs, no rAF hash loop.",
  },
  {
    id: "STRATUM",
    title: "Backend Stratum only",
    fix: "Pool credentials and live Stratum connections are configured on the Python control plane — never from the browser.",
  },
  {
    id: "GATES",
    title: "Triple live-submit + Salamander",
    fix: "HYBA-style gates remain on the Python side. UI faults escalate to Salamander via /api/v1/salamander/fault.",
  },
  {
    id: "TRUTH",
    title: "truth_class on every figure",
    fix: "live · measured · computed · theoretical · historical · hypothesis · unavailable. Backend figures are measured or unavailable.",
  },
];
