# Epistemic Glossary, Truth Classes & Operational Boundaries

**Source**: `toe/intelligences/authority_boundary.py` | `chronus/readiness.py:165` | `AGENTS.md:1.2`  
**Commit**: `07c563e8` | **Seeds**: `[1337, 42, 2026]` | **Status**: **MEASURED**  

---

## 1. Truth Classes & Scientific Status

To maintain total scientific integrity and prevent cognitive drift, all claims, metrics, and code artifacts in this repository belong strictly to one of three Truth Classes:

### 1.1 MEASURED
- **Definition**: Empirically observed, bit-exact, and verified on actual executing hardware (CPU registers, physical silicon, network interfaces) via automated assertions and logged execution traces.
- **Examples**:
  - Split-flight reflex latency p_50 = 4.95 ms < 200 ms.
  - Bitmask XOR shard cut capacity C(M) = 0.5625 (10.82x over 0.0520 baseline).
  - Analytical Golden Ricci flow convergence in k <= 8 discrete steps.
  - Double-SHA256 consensus check satisfying bit-exact reference vectors in `test_hash_pipeline.py`.

### 1.2 SIMULATED
- **Definition**: Algebraic or algorithmic models running on classical substrates that represent mathematical transformations without physical realization of the modeled phenomena.
- **Examples**:
  - Gottesman-Knill Clifford stabilizer vector simulation of multi-qubit Bell states on symplectic spaces F_2^{2n}.
  - Unitary matrix-vector evolution modeling 2-qubit Grover rotation on classical 64-bit float registers.
  - Discrete hyperbolic Poincaré metric geodesics.

### 1.3 HYPOTHESIS
- **Definition**: Theoretical conjectures, analogies, or category-theoretic mappings that establish conceptual frameworks but do not claim empirical proof or universal truth.
- **Examples**:
  - The cross-domain functor mapping between software session token leaks and CTCF insulator boundary loss.
  - The hypothesis that higher integrated information (Phi) correlates with meta-learning adaptation speed.

---

## 2. Hardware & Execution Boundaries

### 2.1 NOT_RUN vs PASS
- In accordance with `chronus/readiness.py:165`:
  - A hardware performance or hashrate metric must NEVER be declared mathematically.
  - If a physical ASIC or accelerator is not actively executing, the status defaults strictly to **`NOT_RUN`**.
  - A **`PASS`** status is granted ONLY upon successful live hardware execution and validation of reference proof-of-work digests against the Bitcoin consensus target.

### 2.2 CPU vs Device Execution (Route Provenance)
- In accordance with the execution provenance contract:
  - Every acceleration request tracks `{requested_route, executed_route, fallback_reason}`.
  - A CPU execution fallback is explicitly recorded and must NEVER be reported as hardware acceleration or device execution.

---

## 3. Mathematical & Theoretical Boundaries

### 3.1 Hypothesis vs Theorem
- **Finite Probes are NOT Theorems**: Finite point counting on congruent number curves y^2 = x^3 - d^2x constitutes numerical exploration, NOT a mathematical theorem or proof of the Birch and Swinnerton-Dyer Millennium Prize problem.
- **Substrate vs Physics**: Quantum mechanics in this repository is defined exclusively as linear algebra over complex Hilbert spaces. It does not imply or require cryogenic apparatus, laser cavities, or physical qubits.
