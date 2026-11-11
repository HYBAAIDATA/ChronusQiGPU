# Legacy Chronus quantum-labelled modules

> **Status: legacy computational research. This namespace is not TURING and is not a validated implementation of conventional quantum mechanics.**

The name `chronus.quantum` is historical. The modules here combine finite-field and algebraic search constructions with proxy measures. They should not be presented as physical quantum computation, hardware execution, device simulation, cryptographic conformance, or demonstrated quantum advantage. See the [package taxonomy](../../../docs/system-update/quantum-package-taxonomy.md).

## Current classification

| Existing code | Accurate description | What this does not establish |
|---|---|---|
| `statevector.py` | State-like vectors and evolution over the finite field F_257 | A complex Hilbert space, Born-rule probabilities, or physical quantum states |
| `grover.py`, `metallic_search.py`, `extension_search.py`, `subspace.py` | Algebraic/finite-field search constructions and algorithmic experiments | Conventional gate-model execution or a quantum speedup |
| `entanglement.py` | Algebraic entanglement-inspired constructions and proxy measures | Standard physical entanglement measures or validated quantum correlations |
| `geometric_polychoron.py` | Finite-field/cyclotomic geometric and tensor-like research models | A validated physical quantum-geometric-tensor implementation |
| `tests/test_quantum_state_engine.py` | The named engine resolves to a classical predictive/ML engine | Any quantum execution or quantum algorithm |

This is a source-level classification of the reviewed implementation, not a claim that the complete repository test suite was run or that every mathematical result has been independently verified. Update the table only after reviewing the relevant source and tests.

## Migration and use

- Use [`TURING`](../../../packages/turing/README.md) for the explicitly scoped complex-Hilbert-space quantum mathematics foundation.
- Do not silently rebrand or route these legacy APIs through TURING. Keep compatibility changes explicit and preserve historical behavior where needed.
- Keep this namespace only for existing research or compatibility until maintainers decide whether to deprecate, rename, or remove it.
- Any future claim about physical semantics, correctness, performance, security, or release readiness requires a defined check, exact source commit, reproducible raw result, exceptions, and reviewer.
