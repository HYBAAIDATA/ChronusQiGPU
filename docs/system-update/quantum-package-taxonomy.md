# Quantum package taxonomy and release boundary

## Executive position

**TURING is the first-principles quantum-mathematics package for HYBA Data.** Existing quantum-labelled Chronus code is legacy computational research and must not be represented as equivalent to TURING, physical quantum mechanics, a hardware simulator, or a production quantum capability. Quantum remains a HYBA Data capability—not a separate company or market.

## Package map

| Package / code | Classification | Appropriate description | Not established by the code alone |
|---|---|---|---|
| `packages/turing` | New standalone mathematical library | Finite-dimensional complex-Hilbert-space states, linear operators, tensor products, gates, Born probabilities, and projective measurement | Hardware execution, noise/device simulation, quantum advantage, product qualification, or independent review |
| `src/chronus/quantum` | Legacy finite-field/algebraic research namespace | Algebraic search and state-like models, including F_257 arithmetic and proxy constructions | Conventional complex-Hilbert-space quantum semantics, Born-rule measurement, hardware execution, physical fidelity, or demonstrated speedup |
| `tests/test_quantum_state_engine.py` / referenced engine | Classical ML, based on the reviewed alias to `PredictiveEngine` | Classical predictive model; call it classical/ML | Quantum computation because of its historic test/module label |

The legacy namespace contains `statevector.py`, `grover.py`, `metallic_search.py`, `extension_search.py`, `subspace.py`, `entanglement.py`, and `geometric_polychoron.py`. The package-level detail is in [`src/chronus/quantum/README.md`](../../src/chronus/quantum/README.md).

## TURING scope

TURING's initial implementation models normalized vectors in finite-dimensional complex spaces; conjugate-linear-first inner products; complex linear maps, adjoints, Hermitian and unitary checks; tensor products; standard example gates; Born-rule probabilities; and complete projective measurements with collapse. It uses Python double-precision complex arithmetic with explicit numerical tolerances. It is not a symbolic algebra system, quantum circuit simulator, hardware SDK, noise model, or performance claim. Density matrices, mixed states, general POVMs, backends, and physical devices are outside the initial scope.

TURING is packaged independently under `packages/turing`; it does not replace the root Chronus package or change the identity of Chronus as a HYBA Data product. The distribution name `hyba-turing` and Python import name `turing` are provisional until package-name, namespace, license, ownership, and release checks are approved. The repository's existing license must not be assumed to govern this package without owner confirmation.

## Evidence boundary

This taxonomy records a static source review of the repository snapshot `f335ca137c28d8848f4070107bf00bfb84804cae`. It did **not** execute the repository suite, independently validate all mathematical definitions, run builds, execute hardware, or establish a commit-linked release result. TURING's focused local unit tests are useful development checks, not independent validation or release qualification. Its package wheel/build remains unverified where the build backend is unavailable.

Before publishing TURING, confirm the distribution/import names, license, maintainer and release ownership, supported Python versions, API stability, build and artifact contents, CI results tied to the exact commit, documentation, and security/provenance requirements. State clearly which checks ran, their raw outputs, and which did not.

## Naming and communication rules

- Say **TURING quantum mathematics** for the library's implemented mathematical scope. Do not imply physical quantum hardware, operational advantage, or customer-ready capability.
- Describe legacy Chronus algorithms as finite-field, algebraic, simulated, quantum-inspired, or classical only as supported by their actual implementation. Do not call a module “classical dressed as quantum” as a substitute for documenting the actual model.
- Never infer correctness or release readiness from a name, test count, demo, workflow file, or repository description.
- Link every material technical claim to the exact source, check, commit, raw result, limitations, and reviewer.

## Update 2026-11-11: one TURING distribution

The exact cyclotomic library formerly at `src/turing` (a second top-level
package also named `turing`, which collided with `packages/turing`) now lives
inside the TURING distribution as `turing.exact`
(packages/turing/src/turing/exact). Its tests (tests/test_turing.py) are
unchanged apart from the import path. TURING remains the foundation layer and
does not import `chronus`; Chronus depends on TURING, never the reverse.
