# System Truth, Architectural Taxonomy & Authority Boundaries

**Source**: `toe/intelligences/authority_boundary.py:1-103` | `chronus/mla1517_platform/python/control_api.py:1-150` | `src/api/main.py:1-80`  
**Commit**: `07c563e8` | **Seeds**: `[1337, 42, 2026]` | **Status**: **MEASURED**  

---

## 1. What This Repository Is

`PhiEnterprise-main` is a substrate-agnostic mathematical computing and mining-search system operating across discrete algebraic manifolds. The codebase enforces strict separation of concerns across specialized autonomous intelligences. System state transitions follow a deterministic execution trajectory: `BOOT -> MINING -> RECOVERY`.

---

## 2. The Seven Canonical Authority Boundaries

Under `toe/intelligences/authority_boundary.py`, authority is partitioned into inviolable domain spheres. No intelligence is permitted to usurp the jurisdiction of another.

```mermaid
graph TD
    subgraph EUCLID ["EUCLID: Cognitive & Learning Domain"]
        C1[Predictive Intelligence]
        C2[Causal Reasoning]
        C3[Counterfactual Reasoning]
        C4[Topological Manifold]
        C5[Geometric Flow]
    end

    subgraph PYTHIA ["PYTHIA: Mining & Consensus Authority"]
        P1[Search Plan]
        P2[Nonce Estate Coverage]
        P3[SHA256d Consensus <= Target]
        P4[Share Validation & Pool Submission]
    end

    subgraph CHRONUS ["CHRONUS: Execution Delivery Plane"]
        CH1[Single-Backend Virtual iGPU]
        CH2[Matmul Tile Ladder]
        CH3[Route Fallback Tracking: CPU / Silicon]
    end

    subgraph AL_HARAS ["AL HARAS: Security & Quorum Authority"]
        AH1[Cognitive Shard Entanglement]
        AH2[HMAC 2-of-3 Quorum Gate]
        AH3[Stop Gate Execution Lock]
    end

    subgraph TURING ["TURING: Quantum Compute Plane"]
        T1[Gottesman-Knill Clifford Stabilizers]
        T2[Symplectic Linear Algebra F_2]
        T3[Exact Unitary Matrix Evolution]
    end

    subgraph SALAMANDER ["SALAMANDER: Autonomic Healing"]
        S1[Organ Identity Preservation]
        S2[Task Recomposition]
        S3[Fault Quarantine]
    end

    subgraph THESEUS ["THESEUS & OVID: Persistence & Custody"]
        TH1[State Persistence Receipts]
        TH2[Process Restart Replay]
        TH3[Adaptive State Boundary]
    end

    EUCLID -.->|Advises Only (No Execution)| PYTHIA
    PYTHIA -->|Dispatches Workloads| CHRONUS
    AL_HARAS -->|Guards Authority Boundary| EUCLID
    AL_HARAS -->|Guards Mining Integrity| PYTHIA
    THESEUS -->|Maintains Persistent Custody| CHRONUS
    SALAMANDER -->|Repairs Degraded Organs| CHRONUS
```

### 2.1 EUCLID Cognition
- **Canonical Intelligences** (`authority_boundary.py:14-20`): `predictive`, `causal`, `counterfactual`, `topological`, `geometric`.
- **Role**: High-dimensional state space navigation, Strange Loop meta-learning, discrete Ricci curvature smoothing, cross-domain analogy induction.
- **Inviolable Constraint** (`authority_boundary.py:41-52`): EUCLID is forbidden from touching mining headers, nonce semantics, SHA256d verification, consensus targets, or pool credentials (`EUCLID_FORBIDDEN_DOMAINS`).

### 2.2 PYTHIA Mining Truth
- **Final Authority** (`authority_boundary.py:27-39`): Owns `search-plan`, `nonce-estate-coverage`, `hendrix-traversal`, `sha256d`, `target`, `share-validation`, `submission`, `pool-acknowledgement`, and `credentials`.
- **Inviolable Constraint**: SHA256(SHA256(Header(N))) <= Target. Hashrate is measured on verified physical hardware; mathematical claims without silicon execution default strictly to `NOT_RUN`.

### 2.3 CHRONUS Execution Plane
- **Sole iGPU Engine** (`chronus/mla1517_platform/python/system_fabric.py:32`): Chronus is the sole execution delivery plane for accelerated matrix operations. Sibling adapters like `micro_tether.py` are reconciled as child dispatchers within Chronus, not an independent secondary iGPU.
- **Route Provenance** (`chronus/readiness.py:165`): Every execution reports `{requested_route, executed_route, fallback_reason}`. CPU fallback is never disguised as device execution.

### 2.4 TURING Quantum Compute Plane
- **Algebraic Engine** (`Intelligence/theoretical_foundations.py:120`): Operates exact Clifford stabilizer simulation over symplectic vector spaces F_2^{2n} and discrete unitary transformations over C. Physical qubits and quantum ASIC claims are rejected; amplitude amplification on flat search spaces is closed.

### 2.5 AL HARAS / L-HRAS Security Authority
- **Security & Quorum** (`Intelligence/security_swarm.py:81`): Owns cognitive shard entanglement (S_A, S_B bitwise XOR with mining entropy), tamper detection, and emergency 2-of-3 HMAC curator unlock.

### 2.6 THESEUS & OVID Custody
- **State Custody** (`chronus/readiness.py:280`): Manages process restart replay, adaptive state persistence, and cryptographic receipts across restarts.

### 2.7 SALAMANDER Autonomic Healing
- **Autonomic Recovery** (`core_engine/enhanced_resilience_layer.py:45`): Recomposes failed task organs and isolates faults while preserving unique organ identity across concurrent tasks.

---

## 3. System Entry Points

1. **Unified Cognitive Gateway**: `src/api/main.py`  
   Exposes `/api/v1/euclid/*` (voice stream, split-flight reflex, ERN spike injection, discrete Ricci reconciliation, and quorum unlock).
2. **Chronus Control & Mining Platform API**: `chronus/mla1517_platform/python/control_api.py`  
   Manages production workload orchestration, readiness probes, and hardware telemetry.
3. **Canonical Mining Dispatch**: `mining/production_miner.py`  
   Executes standard Bitcoin stratum work dispatch through `DoubleSHA256Pipeline`.
