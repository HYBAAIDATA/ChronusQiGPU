import { describe, expect, it } from "vitest";
import {
  evidenceAlert,
  evidenceRows,
  intelligenceRows,
  lossBreakdown,
  type MiningEvidence,
} from "@/lib/evidence";

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

  it("shows the operating intelligence with its reasons and measured inputs", () => {
    const withIntel: MiningEvidence = {
      ...HARDWARE,
      intelligence: {
        policy_mode: "model",
        window_ceiling: 1_346_269,
        world: {
          invalidation_rate: { per_hour_mean: 6.2 },
          routes: { opencl_m32: { overhead_ms: 0.812, hash_rate_hs: 26_000_000, method: "direct" } },
        },
        decision: { window: 1_346_240, lookahead: 2, source: "model", reason: "min expected loss 0.0010" },
        loss: {
          fractions: { useful_hashing: 0.9, window_overhead: 0.05, stale_hashing: 0, other: 0.05, recovery: null },
          time_to_first_hash_ms: { p50: 12.34, p90: 20, samples: 9 },
        },
        memory: { backend: "aethel", ledger_verified: true, entries: 12 },
        audit: { audits: 21, disagreements: 0, vqc_available: true, last: { agree: true, digest: "416b371e4bcf8c6d" } },
      },
    };
    const rows = Object.fromEntries(intelligenceRows(withIntel).map((r) => [r.key, r]));
    expect(rows.policy_window).toMatchObject({ value: 1_346_240, truth: "computed" });
    expect(rows.overhead.value).toBe("0.812 ms (direct)");
    expect(rows.hash_rate.value).toBe("26.00 MH/s");
    expect(rows.first_hash.value).toBe("12.3 ms");
    expect(rows.memory.value).toBe("verified · 12 entries");
    expect(rows.audit.value).toBe("21 audits · 0 disagreements · 416b371e4bcf");
    const losses = lossBreakdown(withIntel);
    expect(losses.map((l) => l.key)).toEqual(["useful_hashing", "window_overhead", "other"]);
  });

  it("reports an unlearned route as not reported, never zero", () => {
    const early: MiningEvidence = {
      ...HARDWARE,
      intelligence: { decision: { window: 96, source: "legacy", reason: "insufficient evidence" }, world: { routes: {} } },
    };
    const rows = Object.fromEntries(intelligenceRows(early).map((r) => [r.key, r]));
    expect(rows.overhead).toMatchObject({ value: null, truth: "unavailable" });
    expect(rows.policy_window.truth).toBe("live");
    expect(lossBreakdown(early)).toEqual([]);
    expect(intelligenceRows({ evidence_available: false })).toEqual([]);
  });
});
