# Turing 1,000-Qubit Phi Machine Consolidation

**Status:** production integration branch  
**Source artifact:** `HYBA_1000_QUBIT_VQC_20260724.zip`  
**Source SHA-256:** `7b4ef03683de8bf03a189293bb72e4493c9a408c5722b38f4a1e2ca8f05e9038`  
**Target:** `turing_universal_quantum_computer`

## Decision

The July artifact is **combined with Turing, not copied wholesale**. Where the
live repository already has the stronger implementation, the live implementation
remains canonical and the July capability is adapted around it.

| July component | Existing repository capability | Consolidated decision |
|---|---|---|
| NumPy boolean `StabilizerRegister` | `stabilizer.StabilizerState`, integer-bitset Aaronson-Gottesman tableau, exact Clifford gates, fail-closed T/non-Clifford handling | **Existing wins.** Do not add a second tableau implementation. |
| `PhiQuantumCircuit` + OpenQASM subset | No single 1,000-qubit production facade | **Adopted** as `phi_quantum_machine.PhiQuantumCircuit`, extended with SDG/CZ/SWAP and fail-closed parsing. |
| Affine GF(2) sampler | Exact per-qubit stabilizer measurement | **Combined.** Fast affine sampling is retained for high-width GHZ/affine families; general sampling remains bounded and exact. |
| Float/PULVINI `PhiRecursiveOperator` checkpoint | Repository exact PULVINI pair fold (`python_backend.core_modules.math_folding`) | **Existing exact contract wins.** New checkpoint uses an exact recursive pair-sum/left-residual representation and cross-checks the canonical PULVINI transform when available. No physical-compression claim. |
| GHZ 32-shot correlation as evidence | Independent Aug-2026 finding says this is non-discriminating | **Replaced.** Production gate verifies signed-Pauli stabilizer-group membership, then separately reports shot correlation as diagnostic only. |
| 12 algorithm plan rows | Turing has multiple exact backends with different domains | **Retained as capability metadata with status.** QEC/Clifford is executable here; Shor is restricted on stabilizer; QFT/general algorithms are planned/backend-dependent; Grover is bounded on other exact Turing backends. |
| VQC nonce generator/ranker | Canonical miner already owns valid candidate windows and SHA256d authority | **Constrained.** `phi_vqc.PhiGroverVQC` can only reorder an input candidate set. It cannot synthesize a replacement nonce or change a proof field. |
| 32-face VQC Clifford skeleton | Existing Turing exact stabilizer backend | **Wired.** Skeleton executes through `PhiQuantumMachine` and checkpoint/restore is verified. |

## New canonical paths

- `turing_universal_quantum_computer/turing_universal_quantum_computer/phi_quantum_machine.py`
  - `PhiQuantumCircuit`
  - `PhiQuantumMachine`
  - `PhiQuantumMachine1000`
  - exact recursive PULVINI-compatible checkpoint/restore/regeneration
  - OpenQASM-2 bounded Clifford parser
  - algorithm capability/status reporting
- `turing_universal_quantum_computer/turing_universal_quantum_computer/phi_verification.py`
  - signed-Pauli group membership
  - basis-invariant GHZ verification
  - discriminating 1,000-qubit production gate
- `turing_universal_quantum_computer/turing_universal_quantum_computer/phi_vqc.py`
  - 32-face trainable ranking model
  - exact Clifford skeleton
  - candidate-set preservation invariant
- `turing_universal_quantum_computer/tests/test_phi_quantum_machine_consolidation.py`
  - QASM boundary
  - GHZ group verification and corruption detection
  - depth-20 checkpoint mutation/restore
  - algorithm claim boundaries
  - VQC candidate preservation
  - 32-face skeleton checkpoint
  - full 1,000-qubit production gate

All public symbols are lazy-exported through
`turing_universal_quantum_computer.__init__`; these are live Turing package
capabilities, not archival modules.

## 1,000-qubit evidence gate

`run_1000_qubit_verification()` passes only when:

1. the circuit-built GHZ state contains the canonical all-X stabilizer;
2. all 999 adjacent ZZ parity stabilizers are members of the produced signed
   Pauli stabilizer group;
3. the depth-20 exact checkpoint round-trips to the original SHA-256 state
   digest after deliberate mutation; and
4. checkpoint metadata is internally consistent.

Measurement correlation is still emitted because it is useful as a runtime
sanity diagnostic, but `measurement_correlation_is_evidence` is always `False`.

## Claim and execution boundary

The Turing stabilizer backend is exact Clifford algebra. Its compact polynomial
representation is a consequence of the Gottesman-Knill domain and is **not** a
quantum-advantage claim.

- **Executable on this backend:** H, S, S-dagger, X, Y, Z, CNOT, CZ, SWAP;
  exact stabilizer measurement/probabilities; Clifford QEC/stabilizer work;
  exact checkpoint/restore.
- **Other exact Turing backends:** bounded sparse/exact-tensor operations,
  including non-Clifford domains where those backends explicitly support them.
- **Restricted on stabilizer:** T/arbitrary phase, universal Shor/factoring,
  unrestricted QFT controlled phases, and any speedup/supremacy claim.

## Mining authority boundary

Nothing in this integration changes Bitcoin consensus semantics.

`PhiGroverVQC` has authority **only to reorder an already-valid candidate
window**. It does not own or alter:

- Stratum jobs;
- block-header construction;
- nonce validity/domain;
- SHA-256d;
- pool/network target;
- local proof verification;
- share submission; or
- pool acknowledgement/accounting.

The canonical mining coordinator and proof pipeline remain the sole authority
for those operations.

## Production invocation

```python
from turing_universal_quantum_computer import run_1000_qubit_verification

report = run_1000_qubit_verification(shots=2)
assert report["verification_pass"] is True
```

The full CI regression gate is:

```bash
pytest -q turing_universal_quantum_computer/tests/test_phi_quantum_machine_consolidation.py
```

The uploaded July logs remain historical evidence for that artifact. The live
repository's production truth after consolidation is the code and tests above;
old test counts are not automatically promoted to the current branch.
