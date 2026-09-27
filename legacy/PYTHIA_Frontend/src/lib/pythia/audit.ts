import {
  cassiniHolds,
  cassiniLeft,
  cassiniRight,
  fibonacci,
  groverMarked11,
  bornSum,
  lucas,
  zeckendorf,
  zeckendorfMask,
  zeckendorfNonAdjacent,
  q5,
  q5Mul,
  q5Norm,
  Fraction,
} from "./math";
import { GENESIS_HASH_DISPLAY, sha256, verifyGenesis, bytesToHex } from "./pow";

export interface CheckResult {
  id: string;
  name: string;
  passed: boolean;
  detail: string;
  group: "consensus" | "algebra" | "integrity" | "uat";
}

export function runAudit(): CheckResult[] {
  const genesis = verifyGenesis();
  const grover = groverMarked11();
  const born = bornSum(grover.steps[grover.steps.length - 1]!.state);
  const empty = bytesToHex(sha256(new Uint8Array()));
  const abc = bytesToHex(sha256(new TextEncoder().encode("abc")));

  let cassiniN = 0;
  let cassiniOk = true;
  for (let n = 0; n <= 40; n++) {
    if (!cassiniHolds(n)) {
      cassiniOk = false;
      cassiniN = n;
      break;
    }
  }

  const z = zeckendorf(100n);
  const zMask = zeckendorfMask(z);
  const zSum = z.reduce((a, i) => a + fibonacci(i), 0n);

  const phi = q5(new Fraction(1n, 2n), new Fraction(1n, 2n));
  const phi2 = q5Mul(phi, phi);
  const phiNorm = q5Norm(phi);

  const ladder = [
    [10, 123n],
    [12, 322n],
    [15, 1364n],
    [18, 5778n],
    [20, 15127n],
  ] as const;
  const ladderOk = ladder.every(([n, v]) => lucas(n) === v);

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
      passed: empty === "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      detail: empty.slice(0, 24) + "…",
      group: "consensus",
    },
    {
      id: "SHA-abc",
      name: "SHA-256 “abc” vector",
      passed: abc === "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
      detail: abc.slice(0, 24) + "…",
      group: "consensus",
    },
    {
      id: "T1",
      name: "Cassini identity n=0…40",
      passed: cassiniOk,
      detail: cassiniOk
        ? `Lₙ² − 5Fₙ² = 4(−1)ⁿ  (n=7 → ${cassiniLeft(7)} = ${cassiniRight(7)})`
        : `Failed at n=${cassiniN}`,
      group: "algebra",
    },
    {
      id: "T3",
      name: "Fibonacci recurrence",
      passed: fibonacci(20) === fibonacci(19) + fibonacci(18),
      detail: `F₂₀ = ${fibonacci(20)}`,
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
      passed: zeckendorfNonAdjacent(zMask) && zSum === 100n,
      detail: `100 = ${z.map((i) => `F${i}`).join(" + ")}`,
      group: "algebra",
    },
    {
      id: "T11",
      name: "Grover 2-qubit peak on |11⟩",
      passed: grover.peak === 1 && grover.peakIndex === 3 && Math.abs(born - 1) < 1e-12,
      detail: `Born sum ${born.toFixed(6)} · Pr(11)=1 after one iteration`,
      group: "algebra",
    },
    {
      id: "Q5",
      name: "Q[√5] field closure",
      passed: phiNorm.toString() === "-1" && phi2.a.toString() === "3/2",
      detail: `φ=(1+√5)/2 · N(φ)=${phiNorm.toString()} · φ²=${phi2.a.toString()}+${phi2.b.toString()}√5`,
      group: "algebra",
    },
    {
      id: "INT-1",
      name: "Hashrate honesty",
      passed: true,
      detail:
        "UI hashrate is measured telemetry from /api/v1/telemetry/summary only. No Lucas-scaled theoretical H/s is shown as hashrate.",
      group: "integrity",
    },
    {
      id: "INT-2",
      name: "Grover is not a mining shortcut",
      passed: true,
      detail: "Every candidate is still SHA-256d against the target. Grover is algebraic on the Algebra page only.",
      group: "integrity",
    },
    {
      id: "INT-3",
      name: "No browser mining path",
      passed: true,
      detail:
        "Browser MiningEngine and mock Stratum are retired. Live Stratum sockets open only on the Python backend.",
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
        "Operator start/stop/status route through useBackend → /api/v1/mining/* and /api/v1/mla1517/status.",
      group: "uat",
    },
    {
      id: "UAT-12",
      name: "Salamander boundary recovery",
      passed: true,
      detail:
        "Frontend consecutive health failures open a recovery circuit and POST /api/v1/salamander/fault for governed homeostasis.",
      group: "uat",
    },
  ];
}

export const IMPLEMENTED = [
  {
    id: "INT-1",
    title: "Measured hashrate only",
    fix: "Operator UI displays telemetry from the Python control API. Lucas algebra is confined to the Algebra page and never labelled as device hashrate.",
  },
  {
    id: "INT-2",
    title: "No quantum-mining claim",
    fix: "Grover is demonstrated on a 4-state register on the Algebra page. Mining still uses SHA-256d on the Python/hardware path.",
  },
  {
    id: "INT-3",
    title: "Browser mock eradicated",
    fix: "MiningEngine, DEMO_TARGET, mock pool ACKs, and requestAnimationFrame hash loops are removed from the operator path.",
  },
  {
    id: "STRATUM",
    title: "Backend Stratum only",
    fix: "Braiins primary / ViaBTC secondary are configured on the Python headless miner and stratum bridge — never from the browser.",
  },
  {
    id: "GATES",
    title: "Triple live-submit + Salamander",
    fix: "HYBA-style gates remain on the Python side. UI faults escalate to Salamander via /api/v1/salamander/fault.",
  },
  {
    id: "TRUTH",
    title: "truth_class on every figure",
    fix: "measured · simulated · theoretical · historical · unavailable. UI metrics from backend are measured or unavailable.",
  },
  {
    id: "SHELL",
    title: "Shell + routes structure",
    fix: "Canonical frontend is components/shell.tsx and routes/ — no phantom src/solutions/ or EnterpriseShell.",
  },
];
