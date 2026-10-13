# Intelligence & Agent Capability Ownership Register

> **Canonical Principle**: Substrate-agnostic intelligence with strict domain boundary ownership.
> No third-party proprietary client SDKs (e.g. Claude) exist in the codebase.
> External capabilities, patterns, and cookbook recipes are native mathematical and operational implementations assigned to named agents based on functional authority.
> **Default Invariant**: Where no specialized domain agent has explicit ownership, authority resides in **EUCLID** (Overall Intelligence Owner).

---

## 1. Named Agents & Architectural Authorities

| Named Agent | Architectural Domain | Presumed Capability Scope |
|:---|:---|:---|
| **EUCLID** | Overall Intelligence & CNS | Central Nervous System of the autonomous organism. High-level cognitive task planning, decision arbitration, multimodal representation, operator compilation (`compile_operator`), multi-agent orchestration, and **universal fallback owner**. |
| **AL HARAS** | Security, Gatekeeping & Assurance | Sovereign control, cryptographic enforcement (CEDR), no-float guards, anti-tamper, zero-trust admission control, audit trails, and security boundary enforcement. |
| **SALAMANDER** | Autonomic Self-Healing & Self-Optimisation | Continuous autonomic telemetry, fault detection, closed-loop runtime repair, recovery governor, discovery optimization, and dynamic latency/budget Pareto adjustments. |
| **PYTHIA** | Predictive Guidance & Knowledge Memory | Manifold search strategy, learned plan generation, prime memory and PVSNP store, active learning replaying measured outcomes, and RAG over structured historical state. |
| **CHRONUS** | Hardware Substrate Acceleration | Heterogeneous GPU/iGPU OpenCL acceleration, tile/ladder kernel dispatch, ISA emulation, ASIC protocol adapter, and physical execution latency profiling. |
| **TURING** | Exact Mathematical & Quantum Foundations | Exact algebraic arithmetic ($Z[\phi]$, Lucas sequences, Binet, Cassini), complex Hilbert space linear algebra, group character decomposition, and exact amplitude rotation. |
| **OVID & THESEUS** | Storage Isolation & Causal Provenance | Tenant admission, causal Pearl receipts, HMAC cryptographic provenance, replay verification, and durable storage recovery. |
| **HENDRIX** | Resonant Search & Mining Traversal | Geodesic 32-face frame orientation, coprime step traversal, and non-redundant search manifold routing. |

---

## 2. Cookbook Patterns & Capability Mapping Matrix

External patterns (such as multi-agent collaboration, tool integration, and prompt optimization recipes) are mapped directly to their specialized named agents. All general/unassigned capabilities fall back to EUCLID:

```
                                    ┌────────────────────────────────────────────────────────┐
                                    │                     EUCLID                             │
                                    │     Overall Intelligence Owner (Central Nervous System) │
                                    └──────────────────────────┬─────────────────────────────┘
                                                               │
                 ┌──────────────────┬──────────────────────────┼──────────────────────────┬──────────────────┐
                 ▼                  ▼                          ▼                          ▼                  ▼
          ┌─────────────┐    ┌──────────────┐           ┌──────────────┐           ┌─────────────┐    ┌──────────────┐
          │  AL HARAS   │    │  SALAMANDER  │           │    PYTHIA    │           │   CHRONUS   │    │    TURING    │
          │  (Security) │    │(Self-Healing)│           │ (Knowledge)  │           │ (Execution) │    │   (Quantum)  │
          └─────────────┘    └──────────────┘           └──────────────┘           └─────────────┘    └──────────────┘
```

### Detailed Capability Assignment

| Cookbook Recipe / Capability Pattern | Owning Agent | Rationale & Codebase Alignment |
|:---|:---|:---|
| **Multi-Agent Teams & Team Swarms** | **EUCLID** | Coordinates multi-agent collaboration, task division, and shared context across the organism (`euclid/runtime.py`, `euclid/task_orchestrator.py`). |
| **Coordinator-Worker Pattern** | **EUCLID** | High-level cognitive planning model directing specialized execution units (`euclid/delegation.py`). |
| **Sub-Agent Delegation** | **EUCLID** | Spawning and managing sub-agents with bounded scopes (`euclid/agents/`, `Intelligence/agentic_controller.py`). |
| **Moderation & Safety Filters** | **AL HARAS** | Fail-closed input/output verification, policy checks, and sovereign admission control (`al_haras/guardian.py`, `al_haras/no_float_guard.py`). |
| **Token, Rate & Budget Limits** | **AL HARAS** | Hard resource boundaries, privilege quotas, and anti-abuse gates (`al_haras/entitlements.py`). |
| **Self-Healing & Auto-Recovery Loops** | **SALAMANDER** | Closed-loop error detection, state rollbacks, and self-correcting retries (`salamander/runtime.py`, `salamander/discovery_optimisation.py`). |
| **Latency & Cost Pareto Optimization** | **SALAMANDER** | Dynamic governor adjusting compute intensity under latency pressure (`salamander/control_plane.py`). |
| **Structured RAG & Domain Knowledge** | **PYTHIA** | Vector/topological indexing over prime memory and historical search states (`Intelligence/pythia_memory.py`, `Intelligence/pythia_knowledge.py`). |
| **Prompt Caching & Trajectory Reuse** | **PYTHIA** | Replay of verified trajectory snapshots avoiding redundant re-planning (`Intelligence/pythia_store.py`). |
| **Exact Calculator Tool Integration** | **TURING** | Deterministic fixed-point and ring arithmetic without floating point approximations (`turing_universal_quantum_computer/`, `lucas/core.py`). |
| **High-Throughput Batch Inference** | **CHRONUS** | SIMD/OpenCL execution pipeline and tile dispatcher (`chronus/`, `gpu/`). |
| **Audit Logging & Causal Receipts** | **OVID / THESEUS** | Immutable cryptographic provenance and causal trail (`hyba_db/theseus_registry.py`, `al_haras/witness.py`). |
| **Cognitive Classification & Summarization** | **EUCLID** | *(No specialized domain owner)* Resides in overall intelligence (`euclid/cognition/`). |
| **Multimodal Vision & Chart Interpretation** | **EUCLID** | *(No specialized domain owner)* Resides in overall intelligence (`euclid/cognition/`). |
| **Tool Calling & Agent Action Dispatch** | **EUCLID** | *(No specialized domain owner)* Action routing and tool dispatch (`Intelligence/pythia_tools.py`, `euclid/runtime.py`). |
| **Automated Evaluations & Benchmarking** | **EUCLID** (with Agent H) | Intelligence benchmark execution and evaluation harnesses (`Intelligence/agentic_mining_evals.py`, `tests/`). |

---

## 3. The Euclid Fallback Invariant

> **Rule**: If a new capability, tool, pattern, or recipe is introduced and cannot be unambiguously claimed by AL HARAS (Security), SALAMANDER (Self-Healing/Optimization), PYTHIA (Memory/Learning), CHRONUS (Hardware), TURING (Math/Quantum), or OVID/THESEUS (Storage/Provenance), it **MUST** be placed under `euclid/` or `Intelligence/` under the direct stewardship of **EUCLID** (Agent A).
