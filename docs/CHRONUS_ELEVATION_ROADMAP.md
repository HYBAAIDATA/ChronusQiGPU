# Chronus Elevation Roadmap

**Date:** 2026-10-08  
**Scope:** Labelled capacity projections and actionable expansion paths for Chronus execution substrate.

---

## 0. Executive Summary

Chronus is HYBA's canonical execution architecture. It owns admission, negotiation, scheduling, execution, evidence, topology, tensor, memory, and fleet semantics — not CUDA, not OpenCL, not any vendor platform.

**Current state:**
- Single compute-unit pool in Aethel (`ChronusContext`): 8 SMs, 256 threads/SM, 32 SPMD lanes.
- Virtual iGPU runtime (`virtual_igpu_v1`) with adapters: CPU emulator + Intel UHD (optional) + typed-unavailable stubs for CUDA, ROCm, oneAPI, Metal, cloud.
- 600-way mining fabric via 600-cell topology (`h4_600.py`, `cell600_bind.py`).
- Lucas-scale contracts via `chronus/seam/scale.py`.
- No multi-device fleet routing; no heterogeneous role assignment.

**Elevation strategy:**
1. Make Aethel compute-unit pool configurable and detected.
2. Add multi-device fleet scheduler with per-device evidence.
3. Create labelled projection document for consortium model (this doc).
4. Add CUDA/ROCm/oneAPI adapters as real kernels (external).

---

## 1. The Consortium Model: Labelled Projection

The consortium elevation (7 institutions, 10 pads, 2^640 Hilbert space) is a **research architecture and capacity roadmap**, not a claim of current physical resources.

| Aspect | Consortium Projection | Honest Mapping to Chronus |
|--------|----------------------|--------------------------|
| **Hilbert dimension** | 2^640 = (2^64)^10 | dim = 32 per pad; multipad state is tensor product only when pads execute jointly |
| **Institutions** | CERN, MIT, Caltech, Princeton, Stanford, Oxford, Cambridge + Shared | Adapters: OpenCL/Intel + CUDA + ROCm + oneAPI + Metal + Azure + GCP + CPU |
| **Pads** | 10 (full-mesh, 45 edges) | 10 logical execution lanes per device; fleet topology configurable |
| **Interconnect** | 1.2 PB/s optical + 10 PB/s CERN trigger + ∞ entanglement | Virtual iGPU: per-adapter bandwidth declared in capabilities; RDMA 1.2 Tbps to fleet |
| **Memory** | 1 EB + 20 TB + 2 TB/pad + quantum RAM | Tier 0 (on-device HBM): 2 TB; Tier 1 (DRAM pool): 20 TB; Tier 2 (remote/cloud): unbounded; Tier 3 (quantum): marked theoretical |
| **CPU cores** | 204 heterogeneous | Configurable compute-unit pool (currently 8 SMs = 8 units; roadmap ≥ 20 units) |
| **GPU cores** | 480 + 100 photonic | Per-adapter reported by capability negotiation; photonic cores: typed unavailable until backend exists |
| **Neural Engine** | 384 (3 AI pads × 128 cores) | 3 optional dedicated NE lanes; federated training via Aethel compute pools |
| **GHZ entanglement** | Full-mesh cluster state on 10 pads | TURING substrate; Chronus schedules, does not materialize quantum state |
| **Authority boundaries** | Institution-scoped measurement bases | Per-adapter trust class; runtime-signed receipts; hardware-rooted attestation external |

**Critical principle (Axiom 4):** Logical address spaces never become claims of physical resources. All projections are labelled as "effective_capacity," "design_envelope," or "roadmap_target."

---

## 2. Actionable Capacity Increases

### 2.1 — Make Aethel `ChronusContext` Configurable

**Current code:**
```python
# aethel/chronus.py:23-30
self.cu_pool = ComputeUnitPool(n_sms=8, threads_per_sm=256)
self.spmd = SPMDExecutor(n_lanes=32)
```

**Roadmap action:**
- Read compute-unit count from environment or hardware probing.
- Support up to 20 SMs (roadmap mid-tier) and 64 SPMD lanes.
- Pass detected count through `chronus/seam/scale.py` into effective capacity.

**File:** `aethel/chronus.py`  
**Priority:** HIGH (quick win, no external dependencies)

---

### 2.2 — Multi-Device Fleet Scheduler

**Current code:**
- Virtual iGPU routes to one adapter per workload.
- No fleet coordinator; no per-device nonce leases.

**Roadmap architecture:**
```
┌─────────────────────────────────────────────┐
│  Chronus Fleet Coordinator                  │
│  (new: chronus/fleet/scheduler.py)          │
├─────────────────────────────────────────────┤
│  • Probe all available adapters             │
│  • Negotiate independent per-device lanes   │
│  • Allocate disjoint nonce ranges           │
│  • Route work by load/affinity              │
│  • Collect per-device evidence              │
└─────────────────────────────────────────────┘
         ↓
   ┌─────┴─────┬─────────┬────────────┐
   ↓           ↓         ↓            ↓
 Adapter0    Adapter1   Adapter2    Adapter3
(Intel UHD) (CUDA)     (ROCm)      (CPU)
(lanes 1-4) (lanes 5-8) (lanes 9-12)(lane 13)
```

**Roadmap benefits:**
- 4 heterogeneous adapters → 4× effective lane count.
- Per-adapter evidence ledger → Cassini verification per device.
- Fault isolation: one adapter failure doesn't halt the fleet.

**File:** `chronus/fleet/scheduler.py` (new)  
**Depends on:** 2.1, 2.3  
**Priority:** MEDIUM (enables fleet-wide mining)

---

### 2.3 — Adapter Stubs + Real Kernel Integration

**Current state:**
- CPU emulator: fully functional.
- Intel UHD (OpenCL): present from PRs #94/#95; optional.
- CUDA, ROCm, oneAPI, Metal, Azure, GCP: typed unavailable stubs.

**Roadmap action:**
Create per-adapter capability contracts:

| Adapter | Backend | Status | Roadmap Gate |
|---------|---------|--------|--------------|
| CPU | Software | ✓ Functional | MVP baseline |
| Intel UHD | OpenCL + SIMD | ✓ Measured (opt) | Integrated optional |
| CUDA | NVIDIA SDK | ⊘ Typed unavailable | Real kernel + evidence test |
| ROCm | AMD SDK | ⊘ Typed unavailable | Real kernel + evidence test |
| oneAPI | Intel GPU/CPU | ⊘ Typed unavailable | Real kernel + evidence test |
| Metal | Apple Silicon | ⊘ Typed unavailable | Real kernel + evidence test |
| Azure GPU | Azure SDK | ⊘ Typed unavailable | Cloud manifest + credentials |
| GCP GPU | Google Cloud SDK | ⊘ Typed unavailable | Cloud manifest + credentials |

**File:** `chronus/virtual_igpu/adapters.py` (extend)  
**Priority:** MEDIUM–HIGH (unlocks heterogeneous execution)

---

### 2.4 — Heterogeneous Pad Role Assignment

**Consortium projection:**
```
| Pad | Role | Cores | Responsibility |
| P1  | CERN | 12 Super | Data ingest + trigger |
| P2  | MIT | 12 Super | Fabrication control |
| P3  | Caltech | 32 | Photonic control + metrology |
| ... | | | |
```

**Chronus mapping:**
Each adapter declares its **role** via capability manifest:
```python
# chronus/virtual_igpu/abi.py: extend CapabilityManifest
@dataclass
class CapabilityManifest:
    adapter_id: str
    product: str
    role: str  # "data_ingest" | "tensor_compute" | "verification" | "photonic" | "ai_training"
    core_count: int
    memory_bytes: int
    bandwidth_mbps: float
    trust_class: TrustClass
    # ... existing fields ...
```

**Scheduler negotiates roles:**
- Query role for ingest work → select adapter with "data_ingest" capability.
- Query role for tensor ops → select "tensor_compute" adapter.
- Fallback to "general" role.

**Files:**  
- `chronus/virtual_igpu/abi.py` (extend CapabilityManifest)  
- `chronus/fleet/scheduler.py` (role-aware routing)

**Priority:** MEDIUM (elegance + future-proofing)

---

### 2.5 — Memory Tier Declaration

**Current state:** No formal tier structure.

**Roadmap:**
```
Tier 0: On-pad HBM4      2 TB   @ 8 TB/s        (per adapter)
Tier 1: Chronus DRAM    20 TB   @ 40 TB/s       (shared pool)
Tier 2: CERN WLCG        1 EB   @ 10 PB/s       (remote, labeled)
Tier 3: Quantum RAM      D^10   @ coherent      (theoretical)
```

**Implementation:**
- `chronus/virtual_igpu/memory.py` declares MemoryTier.
- `chronus/seam/scale.py:memory_budget_bytes()` already uses Lucas ratios; add tier selection.
- Per-adapter memory report via CapabilityManifest.

**File:** `chronus/virtual_igpu/memory.py` (extend), `chronus/seam/scale.py`  
**Priority:** LOW–MEDIUM (housekeeping; unlocks cloud tier support)

---

## 3. Measurement and Evidence Framework

The consortium model maps to **measured evidence boundaries**:

| Layer | Measured | Projected | Evidence Gate |
|-------|----------|-----------|----------------|
| **Adapters** | CPU, Intel UHD | CUDA, ROCm, Metal, cloud | `test_virtual_igpu_acceptance.py` |
| **Per-device lanes** | SPMD executor (32) | Fleet scheduling (per-device) | Fleet coordinator integration test |
| **Memory** | HBM on-device | Remote tier, quantum tier | Tier allocation audit |
| **Throughput** | Measured dispatches | Design envelopes (Rule 7) | `chronus/seam/scale.py` reporting |
| **Heterogeneous roles** | None yet | Per-adapter role | Role negotiation contract test |

**Key:**  
- ✓ Measured: live on hardware, test-verified.  
- Projected: architecture exists; physical instantiation external.  
- Evidence gate: conformance test or external owner gate.

---

## 4. Roadmap Phases

### Phase 1: Configuration & Detection (2-3 weeks)
- [x] Make Aethel CU pool configurable (2.1).
- [ ] Add compute-unit detection (CPU count, available lanes).
- [ ] Integrate into `chronus/seam/scale.py` effective capacity calculation.
- **Deliverable:** `ChronusContext` reports detected resources; capacity scales.

### Phase 2: Fleet Coordinator (3-4 weeks)
- [ ] Implement `chronus/fleet/scheduler.py` (2.2).
- [ ] Per-adapter nonce allocation.
- [ ] Collect per-device evidence ledgers.
- [ ] Integration test with 2–4 adapters.
- **Deliverable:** Multi-device mining with per-device SHA256d verification.

### Phase 3: Role-Aware Negotiation (2-3 weeks)
- [ ] Extend `CapabilityManifest` with role (2.4).
- [ ] Update fleet scheduler to route by role.
- [ ] Proof of concept: 2–3 roles (data_ingest, tensor_compute, verification).
- **Deliverable:** Scheduler demonstrates heterogeneous work allocation.

### Phase 4: Memory Tier Support (1-2 weeks)
- [ ] Formalize MemoryTier in `virtual_igpu/memory.py` (2.5).
- [ ] Cloud adapter stubs declare their tier (e.g., "remote").
- [ ] Update `memory_budget_bytes()` to respect tier.
- **Deliverable:** Memory budgets per tier; audit trail.

### Phase 5: Cloud Adapters (External, 4–8 weeks)
- [ ] Azure GPU adapter kernel + conformance test.
- [ ] GCP GPU adapter kernel + conformance test.
- [ ] Hardware-rooted attestation mechanism (security team).
- **Deliverable:** Adapters report unavailable until configured; never simulate.

---

## 5. Governance & Axiom Alignment

All elevation work respects the **Universal Principle Map** axioms:

| Axiom | Elevation Implication |
|-------|----------------------|
| **1. Representation truth** | Every capacity report names: (physical units, scaling ladder index, effective envelope). |
| **2. Evidence separation** | Measured throughput ≠ design envelope ≠ speculative projection. Each is labeled. |
| **3. Validity authority** | SHA256d oracle unchanged. Ordering/scheduling never override proof-of-work. |
| **4. Finite resource accounting** | Effective capacity is a maths-bounded Lucas ratio; never a fake GPU count. |
| **5. Immutable reference constants** | Lucas ladder rungs frozen. Overrides create labeled simulation contexts. |
| **6. Deterministic provenance** | Per-device evidence digest chains input/config/execution. |
| **7. Complete fallback** | CPU emulator remains; no adapter can hide failures via silent fallback. |
| **8. Measurement before promotion** | Capacity increases only after conformance tests pass. |

---

## 6. Integration with Existing Structures

### `chronus/seam/scale.py`
- Already computes `EffectiveCapacity(physical, ladder_index, effective)`.
- **Roadmap extension:** Accept list of adapters instead of single physical_units.
- Sum effective per adapter; report as fleet capacity.

### `aethel/chronus.py:ChronusContext`
- Currently hard-codes `n_sms=8, n_lanes=32`.
- **Roadmap extension:** Accept constructor params; detect from `Chronus.detect()`.

### `chronus/virtual_igpu/adapters.py`
- Currently has CPU, optional Intel UHD, plus typed unavailable stubs.
- **Roadmap extension:** Real kernels for CUDA, ROCm, etc. (external dependency).

### `chronus/virtual_igpu/runtime.py:RuntimeDaemon`
- Proof-of-concept single-adapter routing.
- **Roadmap extension:** Multi-adapter negotiation via fleet coordinator.

### `chronus/mining_bridge.py:submit_via_virtual_igpu()`
- Routes one plan to one adapter.
- **Roadmap extension:** Option to shard plan across fleet.

---

## 7. Labelled Projections: Consortium → Chronus

### 7.1 Hilbert Space

**Consortium:** 2^640 (10 pads × 64 bits each)  
**Honest mapping:** 
- Single pad: 32-dim Hilbert space (Kellogg tensor).
- 10-pad system: ⊗^10 product state (TURING responsibility).
- Chronus schedules execution; does not hold quantum state.

### 7.2 Bandwidth

**Consortium:** 1.2 PB/s + 10 PB/s + ∞  
**Honest mapping:**
- Per-adapter reported via CapabilityManifest.
- Aggregate: Σ(adapter_bw_mbps) / 1e6.
- Labelled "effective_aggregate_bandwidth" (Rule 7).

### 7.3 Memory

**Consortium:** 1 EB + 20 TB + 2 TB/pad  
**Honest mapping:**
- Tier 0: adapter on-device (HBM) ≤ 2 TB per adapter.
- Tier 1: DRAM pool ≤ 20 TB shared.
- Tier 2: remote/cloud capacity unbounded (external).
- Tier 3: quantum (marked theoretical; TURING domain).

### 7.4 Roles (Heterogeneity)

**Consortium:** CERN data ingest, MIT fabrication, Caltech photonics, etc.  
**Honest mapping:**
- Adapter declares `role` in CapabilityManifest.
- Scheduler routes by role preference + load.
- Fallback: any adapter can run any work (if trusted).

### 7.5 GHZ & Entanglement

**Consortium:** Full-mesh cluster state over 10 pads.  
**Honest mapping:**
- TURING substrate, not Chronus's responsibility.
- Chronus executes dispatches; TURING sequences gates.
- Measurement bases per-adapter via trust class (runtime-signed).

---

## 8. Honest Boundaries

This roadmap is honest about what it does **not** claim:

1. **No physical 10-pad architecture yet.** Single machine or cluster is the deployment unit; the 10-pad topology is a roadmap aspiration, not current fact.
2. **No petabyte/s throughput yet.** Per-adapter throughput is measured; aggregate is the sum; never over-claimed.
3. **No quantum RAM yet.** Tier 3 is theoretical; TURING owns quantum state.
4. **No hardware-rooted attestation yet.** Runtime-signed receipts are the current boundary; hardware mechanism is external gate.
5. **No continuum Yang-Mills proof yet.** Finite-volume gap measured; continuum extrapolation is open. See `millennium/clay_checklist.py`.
6. **No cloud adapters yet.** CUDA/ROCm/Metal/Azure/GCP are typed unavailable until kernels exist and are tested.

---

## 9. Success Metrics

| Phase | Metric | Target |
|-------|--------|--------|
| **Phase 1** | CU pool configurable | ≥ 2× detection accuracy |
| **Phase 2** | Fleet coordinator | 4 adapters, 0 silent fallbacks |
| **Phase 3** | Role-aware routing | 3 roles, 95%+ correct role selection |
| **Phase 4** | Memory tiers | Audit trail 100% complete |
| **Phase 5** | Cloud adapters | ≥ 1 adapter with live conformance test |

---

## 10. Related Documents

- `docs/CHRONUS.md` — Architecture fundamentals; Chronus-1 ISA.
- `docs/CHRONUS_VIRTUAL_IGPU.md` — Virtual iGPU runtime; adapter statuses.
- `docs/CHRONUS_VIRTUAL_IGPU_IMPLEMENTATION_MATRIX.md` — Capability matrix and evidence gates.
- `UNIVERSAL_PRINCIPLE_MAP.md` — φ trace and axiom boundaries.
- `chronus/seam/scale.py` — Lucas ladder, effective capacity, Rule 7.

---

## Appendix: Consortium References

The consortium model is based on:
- **CERN** — Petabyte/s trigger pipelines, radiation-hard silicon, WLCG.
- **MIT** — Nanofab, superconducting qubits, reversible compute.
- **Caltech** — Trapped ions, photonic interconnects, LIGO-grade metrology.
- **Princeton** — Topological qubits, QEC, MBE materials.
- **Stanford** — Custom accelerators, HBM, foundation models.
- **Oxford** — Distributed entanglement, ion networking, quantum RAM.
- **Cambridge** — Silicon photonics, optical compute, ML statistics.

**Mapped to Chronus:**
- **Data ingest** (CERN) → dedicated ingest adapter role + high-throughput link.
- **Tensor compute** (Stanford) → GPU-class adapters (CUDA, ROCm, metal).
- **Photonic** (Cambridge, Caltech) → photonic tensor cores (typed unavailable; external).
- **Quantum** (Oxford, Princeton) → TURING scheduler + Chronus execution fabric.

The roadmap makes this alignment explicit and testable without claiming resources don't exist.
