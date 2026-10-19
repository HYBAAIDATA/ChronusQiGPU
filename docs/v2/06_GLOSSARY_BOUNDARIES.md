# Epistemic Glossary, Truth Classes & Operational Boundaries

**Source**: `toe/intelligences/authority_boundary.py` | `chronus/readiness.py:165` | `AGENTS.md:1.2`  
**Commit**: `07c563e8` | **Seeds**: `[1337, 42, 2026]` | **Status**: **MEASURED**  

---

## 1. Truth Classes & Scientific Status

To maintain total scientific integrity and prevent cognitive drift, all claims, metrics, and code artifacts in this repository belong strictly to one of three Truth Classes:

### 1.1 MEASURED
- **Definition**: Empirically observed, bit-exact, and verified on actual executing hardware (CPU registers, physical silicon, network interfaces) via automated assertions and logged execution traces.
- **Examples**:
  - Split-flight reflex latency $p_{50} = 4.95\text{ ms} < 200\text{ ms}$.
  - Bitmask XOR shard cut capacity $C(M) = 0.5625$ ($10.82\times$ over $0.0520$ baseline).
  - Analytical Golden Ricci flow convergence in $k \le 8$ discrete steps.
  - Double-SHA256 consensus check satisfying bit-exact reference vectors in `test_hash_pipeline.py`.

### 1.2 SIMULATED
- **Definition**: Algebraic or algorithmic models running on classical substrates that represent mathematical transformations without physical realization of the modeled phenomena.
- **Examples**:
  - Gottesman-Knill Clifford stabilizer vector simulation of multi-qubit Bell states on symplectic spaces $\mathbb{F}_2^{2n}$.
  - Unitary matrix-vector evolution modeling 2-qubit Grover rotation on classical 64-bit float registers.
  - Discrete hyperbolic Poincaré metric geodesics.

### 1.3 HYPOTHESIS
- **Definition**: Theoretical conjectures, analogies, or category-theoretic mappings that establish conceptual frameworks but do not claim empirical proof or universal truth.
- **Examples**:
  - The cross-domain functor mapping between software session token leaks and CTCF insulator boundary loss.
  - The hypothesis that higher integrated information ($\Phi$) correlates with meta-learning adaptation speed.

---

## 2. Hardware & Execution Boundaries

### 2.1 NOT_RUN vs PASS
- In accordance with [`chronus/readiness.py:165`](file:///c:/Users/leonn/OneDrive/Desktop/PhiEnterprise-main/chronus/readiness.py#L165):
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
- **Finite Probes are NOT Theorems**: Finite point counting on congruent number curves $y^2 = x^3 - d^2x$ constitutes numerical exploration, NOT a mathematical theorem or proof of the Birch and Swinnerton-Dyer Millennium Prize problem.
- **Substrate vs Physics**: Quantum mechanics in this repository is defined exclusively as linear algebra over complex Hilbert spaces. It does not imply or require cryogenic apparatus, laser cavities, or physical qubits.

---

## 4. Locked Non-Claims & Myth-Busting Boundaries

Per `lucas/scaling_research.py` and the master elevation harness, the following non-claims are locked by unit tests and cannot be weakened:

1. **`mining advantage`**: Lucas and Pisot scaling reweights deterministic budget allocations and defines pre-image search order. It does **not** reduce the number of double-SHA256 hashes required to satisfy a consensus target on an unstructured random oracle. Restricted unconditional cost equals unrestricted cost bit-identically ($|\text{mean}_{\text{base}} - \text{mean}_{\text{all}}| < 10^{-9}$).
2. **`scheduling advantage`**: Coprime strides ($\gcd(s, W) = 1$) prove complete estate bijection and zero duplicate nonces across threads. They do not accelerate queue transit or pipeline scheduling.
3. **`hardware speedup`**: Mathematical algorithms running on classical CPU registers maintain exact unitarity, but simulating an $N$-dimensional Grover state on classical silicon costs $\mathcal{O}(N \sqrt{N}) = \mathcal{O}(N^{1.5})$ operations, which is asymptotically slower than classical $\mathcal{O}(N)$ brute force. Physical speedup claims require `silicon_status()["device_run"] == PASS` with bit-identical hash verification.
4. **`production qualification`**: Numerical simulations, metallic walks, and finite prime checks demonstrate algebraic consistency, but do not qualify physical hardware ASICs or claim solutions to Clay Millennium Prize problems.
5. **`mining is internal capability`**: Mining authority belongs exclusively to PYTHIA (`toe/intelligences/authority_boundary.py`). EUCLID advises search plans, but never issues shares, manages credentials, or exposes mining as a public product API.

