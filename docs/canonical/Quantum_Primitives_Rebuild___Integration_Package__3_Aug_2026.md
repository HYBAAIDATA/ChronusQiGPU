# Quantum Primitives Rebuild — Integration Package (3 Aug 2026)

<aside>
🧩

**Status: sandbox-verified, not yet merged.** The rebuilds below were implemented and proven correct in an isolated sandbox (no GitHub write access this session — `mcpServer_github` is disconnected; the read-only `github` connection cannot push commits). This page is the handover artifact: exact before/after code, file paths, and verification steps needed to elevate the shipped repositories to match the honest status now recorded on the [HYBA Data — Product Suite: From Verified Mathematics to Sovereign Security (McKinsey View)](../HYBA%20Data%20%E2%80%94%20Product%20Suite%20From%20Verified%20Mathematic%208f35848baf3c4bf39d151b7f7fdde01d.md) page.

</aside>

**Elevation rule applies:** code must be elevated to meet documentation. Until these patches land, the Product Suite page's PROVEN status for these primitives refers to the sandbox rebuild, not the code currently running in `HYBA_Unified_Backend` / `HYBA_Pythia_Prod`.

---

## Scope

| **Repo / file** | **Class / function** | **Bug (as shipped)** | **Fix** |
| --- | --- | --- | --- |
| HYBA_Unified_Backend — `al_haras/security/quantum_math_security.py` | `QuantumWalkSecurityAnalyzer` | Row-stochastic real adjacency matrix — a classical Markov chain, no complex phases, no interference | Real coin+shift unitary evolution (Hadamard-coined discrete quantum walk) on a ring topology; ballistic (~t²) variance verified |
| HYBA_Unified_Backend — `al_haras/security/quantum_math_security.py` | `QuantumTeleportationProtocol.teleport_state` | Applies a uniformly random Pauli directly to the original state post-hoc — not a Bell-measurement protocol; ~0.5 average fidelity | Genuine 3-qubit Bell-pair circuit: Bell-measure message+half-pair, apply correction keyed on the actual measurement bits; fidelity = 1.000000 in every branch |
| HYBA_Unified_Backend — `al_haras/security/quantum_math_security.py` | `QuantumHashFunction.hash` | Threshold `probabilities > 0.5` on a 256-dim probability vector (mean ≈ 0.0039) — no component can exceed 0.5, output is always all-zero | Phase-quadrant bit extraction (sign of real / imaginary part of the mixed amplitude) — deterministic, non-trivial, collision-free on tested inputs; disclosed non-cryptographic limitation (unitary mixing is distance-preserving, so it lacks true avalanche behaviour) |
| HYBA_Pythia_Prod — `core_engine/nobel_fields_quantum_entanglement.py` | `QuantumEntanglementIntelligence.quantum_teleportation` | Same pattern: random Pauli applied directly to `source_state`, no real Bell measurement; fidelity computed against a self-selected correction (tautological, not a real recovery test) | Wire to the same genuine `teleport()` circuit; report the deterministic fidelity it actually produces |
| HYBA_Pythia_Prod — `core_engine/enhanced_quantum_entanglement.py` | `EnhancedQuantumEntanglement.quantum_teleportation` | Hardcoded `"quantum_fidelity": 0.999` — never computed from any state; the function only computes a distance-based `success_probability` heuristic | Remove the fabricated fidelity field, or compute a real fidelity via `teleport()` on `entangled_state.state_vector` |

---

## 1. `al_haras/security/quantum_math_security.py` (HYBA_Unified_Backend)

### 1a. `QuantumWalkSecurityAnalyzer` — real quantum walk

**As shipped** (`step_walk`, `_build_security_graph`): the "coin operator" is just the row-normalized adjacency matrix — a real, row-stochastic matrix. That is a classical random walk / Markov chain by definition; there is no complex phase, so no interference is possible.

```python
# BEFORE (classical Markov chain mislabeled as a quantum walk)
def step_walk(self, steps: int = 1) -> np.ndarray:
    if self.walk_state is None:
        self.initialize_walk()
    for _ in range(steps):
        coin_operator = self.adjacency_matrix
        row_sums = coin_operator.sum(axis=1)
        row_sums[row_sums == 0] = 1
        coin_operator = coin_operator / row_sums[:, np.newaxis]
        self.walk_state = coin_operator @ self.walk_state
        norm = np.linalg.norm(self.walk_state)
        if norm > 1e-15:
            self.walk_state /= norm
    return np.abs(self.walk_state) ** 2
```

**Integration fix.** The sandbox-proven primitive (`RealDiscreteQuantumWalk`) uses a Hadamard coin + cyclic shift on a coin⊗position register and is verified to spread ballistically (σ² ~ t², not ~t). The minimal faithful integration is to give `QuantumWalkSecurityAnalyzer` a ring topology and this exact coin+shift step, replacing the adjacency-matrix-as-coin approach:

```python
# AFTER — real coin+shift unitary evolution
def _build_security_graph(self) -> np.ndarray:
    # Ring topology required for a well-defined coin+shift quantum walk.
    # (Irregular small-world graphs need a Szegedy-style walk — tracked
    # separately below as follow-on work, not yet verified.)
    adj = np.zeros((self.graph_size, self.graph_size))
    for i in range(self.graph_size):
        adj[i, (i + 1) % self.graph_size] = 1
        adj[i, (i - 1) % self.graph_size] = 1
    return adj

def initialize_walk(self, start_node: int = 0) -> None:
    # coin(0=L,1=R) x position register, complex128
    self.walk_state = np.zeros((2, self.graph_size), dtype=np.complex128)
    self.walk_state[0, start_node] = 1 / np.sqrt(2)
    self.walk_state[1, start_node] = 1j / np.sqrt(2)

def step_walk(self, steps: int = 1) -> np.ndarray:
    if self.walk_state is None:
        self.initialize_walk()
    H = np.array([[1, 1], [1, -1]], dtype=np.complex128) / np.sqrt(2)
    for _ in range(steps):
        coined = H @ self.walk_state
        shifted = np.zeros_like(coined)
        shifted[0, :-1] = coined[0, 1:]
        shifted[0, -1] = coined[0, 0]
        shifted[1, 1:] = coined[1, :-1]
        shifted[1, 0] = coined[1, -1]
        self.walk_state = shifted
        total_prob = np.sum(np.abs(self.walk_state) ** 2)
        assert abs(total_prob - 1.0) < 1e-9, f"unitarity violated: {total_prob}"
    return np.sum(np.abs(self.walk_state) ** 2, axis=0)  # position distribution
```

`analyze_pattern` needs no change — it already just calls `step_walk` and indexes into the returned distribution by node.

**Follow-on (not yet built):** generalizing this to the original irregular small-world security graph requires a Szegedy-type quantum walk (bipartite lift of the adjacency matrix), which is a larger, unverified change. Track separately; do not represent it as done until it is actually implemented and tested.

### 1b. `QuantumTeleportationProtocol` — real 3-qubit teleportation

**As shipped** (`teleport_state`): picks a uniformly random Pauli and applies it straight to the *original* state, then compares the result to the original. This is not a teleportation protocol — there is no Bell measurement, no shared entangled pair, and no correction that recovers anything. Average fidelity ≈ 0.5.

```python
# BEFORE
def teleport_state(self, state_to_teleport: np.ndarray) -> tuple[np.ndarray, int]:
    measurement_outcome = np.random.randint(0, 4)
    correction_operators = [np.eye(2), X, Z, Y]
    correction = correction_operators[measurement_outcome]
    teleported_state = correction @ state_to_teleport
    ...
    return teleported_state, measurement_outcome
```

**Integration fix** — genuine 3-qubit circuit (message qubit A; shared Bell pair B,C held by sender/receiver). Bell-measure A,B; the measurement bits are real outputs of that circuit, not drawn independently of it; the receiver's correction on C recovers the message with fidelity 1 in every branch:

```python
# AFTER — real Bell-pair teleportation circuit
I2 = np.eye(2, dtype=np.complex128)
X = np.array([[0, 1], [1, 0]], dtype=np.complex128)
Z = np.array([[1, 0], [0, -1]], dtype=np.complex128)
H = np.array([[1, 1], [1, -1]], dtype=np.complex128) / np.sqrt(2)

def _kron3(a, b, c):
    return np.kron(np.kron(a, b), c)

def _cnot(control, target, n=3):
    dim = 2 ** n
    U = np.zeros((dim, dim), dtype=np.complex128)
    for i in range(dim):
        bits = [(i >> (n - 1 - k)) & 1 for k in range(n)]
        if bits[control] == 1:
            bits[target] ^= 1
        j = 0
        for b in bits:
            j = (j << 1) | b
        U[j, i] = 1.0
    return U

def _single_qubit_gate(gate, qubit, n=3):
    ops = [I2] * n
    ops[qubit] = gate
    out = ops[0]
    for op in ops[1:]:
        out = np.kron(out, op)
    return out

def teleport_state(self, state_to_teleport: np.ndarray) -> tuple[np.ndarray, tuple[int, int]]:
    """Full circuit: prepares the Bell pair on B,C, Bell-measures A,B against
    the message state, and returns the receiver's corrected state on C plus
    the two real classical bits that would be sent over the classical channel."""
    zero = np.array([1, 0], dtype=np.complex128)
    full = _kron3(state_to_teleport, zero, zero)
    full = _single_qubit_gate(H, 1) @ full
    full = _cnot(1, 2) @ full
    full = _cnot(0, 1) @ full
    full = _single_qubit_gate(H, 0) @ full
    probs = np.abs(full) ** 2
    outcome_idx = int(np.random.choice(len(probs), p=probs / probs.sum()))
    m_A = (outcome_idx >> 2) & 1
    m_B = (outcome_idx >> 1) & 1
    c_amplitudes = np.array([full[(m_A << 2) | (m_B << 1) | c] for c in (0, 1)])
    norm = np.linalg.norm(c_amplitudes)
    c_state = c_amplitudes / norm if norm > 1e-12 else c_amplitudes
    corrected = c_state.copy()
    if m_B == 1:
        corrected = X @ corrected
    if m_A == 1:
        corrected = Z @ corrected
    return corrected, (m_A, m_B)
```

`verify_teleportation` needs no change — `fidelity(original, corrected)` will now genuinely equal 1.0 (up to floating point) in every branch, which is the actual defining correctness property of teleportation.

### 1c. `QuantumHashFunction` — fixed threshold bug

**As shipped** (`hash`): thresholds `probabilities > 0.5` where `probabilities` are the squared amplitudes of a 256-dimensional unit vector (mean ≈ 1/256 ≈ 0.0039). No single component can realistically exceed 0.5, so every input hashes to the same all-zero output.

```python
# BEFORE
hash_bits = (probabilities > 0.5).astype(np.uint8)
```

**Integration fix** — derive bits from the amplitude's phase quadrant (sign of real part, sign of imaginary part) instead of an unreachable magnitude threshold:

```python
# AFTER
mixed_state = self.mixing_unitary @ amplitudes
bits_re = (mixed_state.real > 0).astype(np.uint8)
bits_im = (mixed_state.imag > 0).astype(np.uint8)
hash_bits = np.concatenate([bits_re, bits_im])[: self.output_size]
hash_bytes = np.packbits(hash_bits)
return hash_bytes.tobytes().hex()[: self.output_size // 4]
```

**Disclosed limitation (must ship with this fix, not hidden):** `mixing_unitary` is unitary, i.e. distance-preserving (‖Ux−Uy‖ = ‖x−y‖). A real cryptographic hash needs a *nonlinear* mixing step to get avalanche behaviour; this fixed function is a legitimate deterministic, collision-resistant-on-tested-inputs **fingerprint**, not a drop-in replacement for SHA-256 and must not be marketed as one.

---

## 2. `core_engine/nobel_fields_quantum_entanglement.py` (HYBA_Pythia_Prod)

### `QuantumEntanglementIntelligence.quantum_teleportation` — same bug pattern

**As shipped:** draws `measurement_result` independently of any real measurement and applies a correction straight to `source_state`, then multiplies by `bell_pair.fidelity * self.teleportation_fidelity` (a hardcoded 0.99) — the reported fidelity is not derived from an actual protocol run.

```python
# BEFORE
measurement_result = np.random.randint(0, 4)
teleported_state = source_state.copy()
if measurement_result == 1:
    teleported_state = np.array([teleported_state[1], teleported_state[0]])
elif measurement_result == 2:
    teleported_state = np.array([teleported_state[0], -teleported_state[1]])
elif measurement_result == 3:
    teleported_state = np.array([-teleported_state[1], teleported_state[0]])
fidelity = np.abs(np.vdot(source_state, teleported_state)) ** 2
fidelity *= bell_pair.fidelity * self.teleportation_fidelity
```

**Integration fix** — call the same genuine circuit as §1b (import from the shared primitive rather than duplicating it), and report the fidelity it actually produces, scaled only by the real `bell_pair.fidelity` (drop the fabricated `self.teleportation_fidelity` constant unless it is replaced by a measured decoherence model):

```python
# AFTER
async def quantum_teleportation(
    self, source_state: np.ndarray, bell_pair: EntangledPair
) -> Tuple[np.ndarray, float]:
    corrected, (m_A, m_B) = teleport_state(source_state)  # shared circuit from §1b
    fidelity = np.abs(np.vdot(source_state, corrected)) ** 2
    fidelity *= bell_pair.fidelity  # only real, measured degradation — no fabricated constant
    logger.info(f"Teleportation completed with fidelity {fidelity:.6f}")
    return corrected, fidelity
```

---

## 3. `core_engine/enhanced_quantum_entanglement.py` (HYBA_Pythia_Prod)

### `EnhancedQuantumEntanglement.quantum_teleportation` — hardcoded fidelity

**As shipped:** the function never touches `entangled_state.state_vector` in any teleportation computation — it only derives a distance-based `success_probability` heuristic, then reports a flat, hardcoded `"quantum_fidelity": 0.999` regardless of input.

```python
# BEFORE
success_probability = np.exp(-distance / (1e6 * PLANCK_LENGTH))
return {
    ...
    "success_probability": success_probability,
    "entanglement_preserved": True,
    "quantum_fidelity": 0.999,
}
```

**Integration fix — option A (minimal, honest):** remove the fabricated field; keep only the metrics that are actually computed.

```python
return {
    ...
    "success_probability": success_probability,
    "entanglement_preserved": success_probability > 0.5,
}
```

**Integration fix — option B (fuller fix, recommended if this path is load-bearing):** actually run the real circuit against `entangled_state.state_vector` and report the fidelity it produces, same pattern as §2.

---

## Testing

- Sandbox verification scripts (source of the code above): `rebuilds.py` (quantum walk vs. classical random walk — variance scaling table), `rebuilds2.py` (500×4-branch teleportation fidelity sweep, hash determinism/avalanche/isometry checks).
- Before merging, port these into `tests/al_haras/test_quantum_math_security.py` (or equivalent) as pytest cases:
    - assert quantum-walk variance grows faster than linear in step count (ballistic signature)
    - assert teleportation fidelity == 1.0 (to floating-point tolerance) across all 4 measurement branches, for a spread of random input states
    - assert hash determinism, and explicitly assert (not just note) the isometry/avalanche limitation so it can't silently regress into a false security claim
- Re-run `AL HARAS` audit / claim-lane scanner after the patch lands, since these files sit under `al_haras/security/` and are in scope for `hyba_security_layer_v0.1.0`'s CI claim scanner.

---

## Rollout checklist

- [ ]  Reconnect `mcpServer_github` (or grant this agent write access) so patches can be opened as a PR directly, or apply the diffs above manually
- [ ]  Apply §1a–1c to `HYBA_Unified_Backend/al_haras/security/quantum_math_security.py`
- [ ]  Apply §2 to `HYBA_Pythia_Prod/core_engine/nobel_fields_quantum_entanglement.py`
- [ ]  Apply §3 (option A or B) to `HYBA_Pythia_Prod/core_engine/enhanced_quantum_entanglement.py`
- [ ]  Add the pytest cases described above
- [ ]  Update the Product Suite page's PROVEN status note to point at the merged commit/PR, not just the sandbox proof