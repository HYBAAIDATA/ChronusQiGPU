/**
 * RETIRED: in-browser MiningEngine.
 *
 * The previous implementation ran a requestAnimationFrame SHA-256d loop against
 * a mock://in-process pool, DEMO_TARGET, genesis templates, and Lucas-scaled
 * theoreticalHps. That dual path is eradicated.
 *
 * Live mining is executed exclusively by the Python backend
 * (control_api → mla1517 / stratum bridge / OpenCL). The operator UI talks only
 * to `/api/v1/*` via `backend.ts` / `backend-store.ts`.
 *
 * Algebra helpers (Lucas, Q[√5], Grover demo) live in `./math` and `./pow`
 * for the Algebra and Audit pages — they are not a mining path.
 */

export type TruthClass =
  | "measured"
  | "simulated"
  | "theoretical"
  | "historical"
  | "unavailable";

/** The pool-lifecycle gates the pipeline row renders from backend evidence. */
export type EvidenceGate =
  | "connected"
  | "authorized"
  | "job_received"
  | "candidate_found"
  | "submitted"
  | "accepted";

/** Pool labels for display only — sockets open on the Python side. */
export const POOLS = [
  {
    id: "braiins",
    label: "Braiins",
    endpoint: "stratum+ssl://stratum.braiins.com:3333",
    role: "primary",
    executable: false,
  },
  {
    id: "viabtc",
    label: "ViaBTC",
    endpoint: "stratum+ssl://btc.viabtc.io:3333",
    role: "secondary",
    executable: false,
  },
] as const;

export const SUBSTRATES = [
  "Predictive",
  "Causal",
  "Topological",
  "Geometric",
  "Counterfactual",
  "Yang-Mills",
  "Millennium",
  "MDMemory",
  "Tensor",
  "Quantum",
  "iGPU",
  "Storage",
  "Physics",
] as const;

export const INTELLIGENCE_NAMES = [
  "Causal",
  "Geometric",
  "Plastic",
  "Counterfactual",
  "Quantum",
] as const;

/** @deprecated Browser mining removed. Use POST /api/v1/mining/start via useBackend. */
export class MiningEngine {
  constructor() {
    throw new Error(
      "MiningEngine is retired. Operator mining runs on the Python backend only.",
    );
  }
}
