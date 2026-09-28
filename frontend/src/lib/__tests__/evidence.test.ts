import { describe, expect, it } from "vitest";
import { evidenceAlert, evidenceRows, type MiningEvidence } from "@/lib/evidence";

function value(evidence: MiningEvidence, key: string) {
  return evidenceRows(evidence).find((item) => item.key === key);
}

const HARDWARE: MiningEvidence = {
  schema: "pythia.mining_evidence/1",
  evidence_available: true,
  worker_live: true,
  execution_backend: { backend: "opencl:gpu", device: "Intel(R) UHD Graphics 620", route: "opencl_m32" },
  last_execution: {
    executed: true,
    plan_source: "AGENTIC_PRECOMPUTED",
    executed_route: "opencl_m32",
    evidence_class: "HARDWARE_EXECUTED",
    generation: 7,
    lease_id: "lease-1",
    pool_outcome: "ACCEPTED",
  },
  agentic: { lookahead: 2, lookahead_max: 3, precompute_waste_ratio: 0.25 },
  recovery: { mode: "NORMAL" },
  session: { state: "SEARCHING" },
};

describe("mining evidence", () => {
  it("shows nothing when the miner has not published", () => {
    const absent: MiningEvidence = { evidence_available: false, reason: "not published" };
    expect(evidenceRows(absent)).toEqual([]);
    expect(evidenceAlert(absent)).toBe("MINING EVIDENCE UNAVAILABLE");
  });

  it("marks hardware execution as measured and keeps device names literal", () => {
    expect(value(HARDWARE, "executed_route")).toMatchObject({ value: "opencl_m32", truth: "measured" });
    expect(value(HARDWARE, "backend")?.value).toBe("Intel(R) UHD Graphics 620");
    expect(value(HARDWARE, "waste")?.value).toBe("25.0%");
    expect(evidenceAlert(HARDWARE)).toBeNull();
  });

  it("never turns an unknown into zero", () => {
    const sparse: MiningEvidence = { evidence_available: true, agentic: { precompute_waste_ratio: null } };
    expect(value(sparse, "waste")).toMatchObject({ value: null, truth: "unavailable" });
    expect(value(sparse, "pool_outcome")).toMatchObject({ value: null, truth: "unavailable" });
  });

  it("surfaces recovery, route fallback and blocked precompute", () => {
    expect(evidenceAlert({ ...HARDWARE, recovery: { mode: "RECOVERING" } })).toBe("SALAMANDER RECOVERING");
    expect(evidenceAlert({ ...HARDWARE, recovery: { mode: "FAULTED" } })).toMatch(/FAULTED/);
    expect(
      evidenceAlert({
        ...HARDWARE,
        last_execution: { ...HARDWARE.last_execution, route_fallback_reason: "OPENCL_UNAVAILABLE" },
      }),
    ).toBe("ROUTE FALLBACK: OPENCL_UNAVAILABLE");
    expect(evidenceAlert({ ...HARDWARE, worker_live: false })).toMatch(/NOT LIVE/);
  });
});
