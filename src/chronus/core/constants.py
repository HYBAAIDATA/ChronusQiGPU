"""Immutable reference constants for the Chronus elevation roadmap (Tier 0.6).

Axiom 5: these constants are immutable. Any override creates a labelled
simulation context and never changes these values.
"""

from __future__ import annotations

# Frozen Lucas/Pisot ladder rungs (Axiom 4).  Any effective-capacity value is
# clamped to the frozen rungs; an override creates a labelled simulation
# context and never mutates the frozen ladder.
LUCAS_LADDER_RUNGS: tuple[int, ...] = (2, 3, 4, 7, 11, 18, 29, 47, 76, 123, 199)

# Immutable reference constants  (Axiom 5)
SPMD_DEFAULT_LANES: int = 32
SPMD_ROADMAP_MAX_LANES: int = 64
CU_POOL_CURRENT_SMS: int = 8
CU_POOL_ROADMAP_MID_SMS: int = 20
CU_POOL_ROADMAP_MAX_SMS: int = 64

# Consortium projected envelope  (§1)
# Only DESIGN_ENVELOPE and MEASURED labels may enter capacity math.
CONSORTIUM_PROJECTION_DICT: dict[str, dict[str, object]] = {
    "hilbert_dimension": {
        "label": "ROADMAP_TARGET",
        "evidence_class": "THEORETICAL",
        "projection_value": "2^640 = (2^64)^10",
        "honest_mapping": (
            "dim=32 per pad; multipad state is tensor product only when pads "
            "execute jointly"
        ),
    },
    "institutions": {
        "label": "ROADMAP_TARGET",
        "evidence_class": "THEORETICAL",
        "projection_value": "7",
        "honest_mapping": "consortium member count; not a Chronus capacity number",
    },
    "pads": {
        "label": "ROADMAP_TARGET",
        "evidence_class": "THEORETICAL",
        "projection_value": "10",
        "honest_mapping": (
            "roadmap target; single-machine cluster currently deploys 4 pads"
        ),
    },
    "pad_edges": {
        "label": "ROADMAP_TARGET",
        "evidence_class": "THEORETICAL",
        "projection_value": "45",
        "honest_mapping": "full mesh on 10 pads; edge count is combinatorial C(10,2)",
    },
    "interconnect_pbs": {
        "label": "DESIGN_ENVELOPE",
        "evidence_class": "MEASURED",
        "projection_value": "1.2 PB/s aggregate (per-adapter measured)",
        "honest_mapping": "per-adapter bandwidth declared in capabilities; aggregate = sum(adapter_bw)",
    },
    "cern_trigger_pbs": {
        "label": "ROADMAP_TARGET",
        "evidence_class": "THEORETICAL",
        "projection_value": "10 PBS",
        "honest_mapping": "CERN trigger pipeline budget; projected not measured",
    },
    "memory_EB": {
        "label": "ROADMAP_TARGET",
        "evidence_class": "PROJECTED",
        "projection_value": "1 EB",
        "honest_mapping": "1 EB remote tier; external, projected",
    },
    "dram_pool_TB": {
        "label": "DESIGN_ENVELOPE",
        "evidence_class": "MEASURED",
        "projection_value": "20 TB",
        "honest_mapping": "20 TB shared dram pool",
    },
    "pad_HBM_TB": {
        "label": "DESIGN_ENVELOPE",
        "evidence_class": "MEASURED",
        "projection_value": "2 TB HBM per pad",
        "honest_mapping": "2 TB HBM per pad",
    },
    "cpu_cores": {
        "label": "ROADMAP_TARGET",
        "evidence_class": "THEORETICAL",
        "projection_value": "204 cores",
        "honest_mapping": "roadmap target for collective CPU estate",
    },
    "gpu_cores": {
        "label": "ROADMAP_TARGET",
        "evidence_class": "THEORETICAL",
        "projection_value": "480 cores",
        "honest_mapping": "roadmap target for collective GPU estate",
    },
    "photonic_cores": {
        "label": "ROADMAP_TARGET",
        "evidence_class": "THEORETICAL",
        "projection_value": "100 cores",
        "honest_mapping": "theoretical photonic tensor core count; TURING domain",
    },
    "neural_engine_cores": {
        "label": "ROADMAP_TARGET",
        "evidence_class": "THEORETICAL",
        "projection_value": "384 cores",
        "honest_mapping": "roadmap target neural engine cores",
    },
    "ghz_pads": {
        "label": "ROADMAP_TARGET",
        "evidence_class": "THEORETICAL",
        "projection_value": "10 GHZ pads",
        "honest_mapping": "GHZ pads on roadmap; TURING domain only",
    },
    "rdma_tbps": {
        "label": "DESIGN_ENVELOPE",
        "evidence_class": "DESIGN_ENVELOPE",
        "projection_value": "1.2 TB/s",
        "honest_mapping": "RDMA interconnect throughput, design envelope",
    },
}

# Tier 0.8 — Axiom registry (§5)
# Each elevation check references these axioms.
AXIOM_REGISTRY: dict[str, str] = {
    "A1_REPRESENTATION_TRUTH": "Every capacity report names physical units + ladder index + envelope",
    "A2_EVIDENCE_SEPARATION": "Measured is not design envelope or speculative projection",
    "A3_VALIDITY_AUTHORITY": "SHA256d oracle unchanged; routing never overrides proof of work",
    "A4_FINITE_RESOURCE_ACCOUNTING": "Effective capacity is a maths-bounded Lucas ratio",
    "A5_IMMUTABLE_REFERENCE_CONSTANTS": "Lucas rungs frozen; overrides create labelled simulation contexts",
    "A6_DETERMINISTIC_PROVENANCE": "Per-device evidence digest chains input/config/execution",
    "A7_COMPLETE_FALLBACK": "CPU emulator remains; no adapter hides failures via silent fallback",
    "A8_MEASUREMENT_BEFORE_PROMOTION": "Capacity increases only after conformance tests pass",
}
