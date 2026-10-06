import { describe, expect, it } from "vitest";
import { evidenceRows, type MiningEvidence } from "@/lib/evidence";

const byKey = (evidence: MiningEvidence) =>
  Object.fromEntries(evidenceRows(evidence).map((row) => [row.key, row]));

describe("canonical PYTHIA mining evidence", () => {
  it("keeps PYTHIA, Chronus, Turing and Salamander roles explicit", () => {
    const evidence: MiningEvidence = {
      schema: "pythia.mining_evidence/1",
      evidence_available: true,
      worker_live: true,
      pythia_search_precompute: {
        architecture_id: "pythia_dual32_11d_h4_600_hilbert",
        state: "READY",
        dual_vertices: 600,
        manifold_dimension: 11,
        hilbert_qubits: 11,
      },
      pythia_agentic_workforce: {
        composition_root: "PYTHIA",
        enterprise_orchestrator: "EUCLID",
        roles: [
          { role: "physical_execution", owner: "Chronus", authority: "execute authorised nonce batches" },
          { role: "hilbert_walk", owner: "Turing", authority: "exact traversal ranking" },
          { role: "healing_and_optimisation", owner: "Salamander", authority: "bounded recovery" },
        ],
      },
      execution_backend: {
        backend: "adapter:test",
        device: "contract-device",
        route: "opencl_m32",
      },
      last_execution: {
        executed: true,
        executed_route: "opencl_m32",
        evidence_class: "HARDWARE_EXECUTED",
        pool_outcome: "ACCEPTED",
      },
      recovery: { mode: "NORMAL" },
    };

    const rows = byKey(evidence);
    expect(rows.composition_root).toMatchObject({ value: "PYTHIA", truth: "live" });
    expect(rows.search_vertices).toMatchObject({ value: 600, truth: "live" });
    expect(rows.manifold_dimension.value).toBe("11D");
    expect(rows.hilbert_qubits.value).toBe("11 qubits");
    expect(rows.execution_authority.value).toBe("Chronus");
    expect(rows.healing_authority.value).toBe("Salamander");
    expect(rows.backend.value).toBe("contract-device");
    expect(rows.route.value).toBe("opencl_m32");
    expect(rows.pool_outcome).toMatchObject({ value: "ACCEPTED", truth: "measured" });
  });

  it("does not invent canonical topology when the miner did not publish it", () => {
    const rows = byKey({ evidence_available: true, worker_live: true });
    expect(rows.search_vertices).toMatchObject({ value: null, truth: "unavailable" });
    expect(rows.execution_authority).toMatchObject({ value: null, truth: "unavailable" });
  });
});
