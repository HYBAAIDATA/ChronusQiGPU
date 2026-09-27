
## 8. Canonical virtual-qubit tensor

The virtual quantum computer is not represented by labels or symbolic qubit
placeholders. Its canonical register is `mtheory.hilbert.QuantumRegister`, an
exact sparse state vector with basis size \(2^n\). The platform profile is
`n=11`, therefore the mathematical tensor has exactly 2,048 basis amplitudes.

`legacy/src/euclid/pythagoras/quantum/quantum_tensor.py` exposes this register as
`QuantumTensor` and delegates every gate and measurement operation to the
canonical exact implementation:

- Hadamard, Pauli-X/Z, S, T, exact phase, and CNOT;
- exact Born distribution and explicit classical sampling boundary;
- exact QFT/inverse QFT;
- exact Grover oracle/diffusion;
- exact reduced density matrices and von Neumann entropy;
- exact normalization and dimension invariants on every mutation.

`to_pulvini_input()` is the only bridge into NumPy/PULVINI. It exports the full
2,048-component vector as a numerical execution tensor while preserving the
qubit count and recording that a finite-precision boundary was crossed.
Numerical arrays cannot be silently re-imported as exact qubits: `from_numpy`
is deliberately rejected because approximate values cannot establish exact
algebraic amplitudes after the fact.

## 9. Full Hilbert coverage and Lucas/Pisot execution scaling

The virtual register's coverage is \(2^n\), not a symbolic qubit count. For the
platform profile, 11 qubits means exactly 2,048 amplitudes. `plan_hilbert_coverage`
computes the full-rank state bytes (`2^n * bytes_per_amplitude`) and adds an
explicit data/payload reserve. It reports `fits=False` before any numerical
allocation or decomposition when the memory budget is insufficient. No lossy
rank truncation is used to hide a failed coverage plan.

All exact quantum operations emit a scale record through
`legacy/src/euclid/pythagoras/quantum/lucas_pisot.py`. Domain-specific rungs are
intentionally different: qubit gates use L12, QFT L15, Grover L18, CTQW L20,
AQO L31, memory L50, and structured search L76 by default. A caller may select
another supported rung explicitly. The Lucas value changes deterministic
budget/accounting and provenance; it does not multiply a unitary matrix or
claim extra physical qubits.

The Hendrix iGPU facade uses the L76 schedule to create a coprime affine
permutation of the nonce space and partitions permutation positions across
workers. `HendrixSchedule.verify()` proves full coverage and disjointness.
Hash evaluation and pool consensus remain classical/external execution
contracts; the schedule itself does not claim quantum hashing.
