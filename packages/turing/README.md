# TURING — HYBA Data quantum mathematics

TURING is HYBA Data's first-principles library for finite-dimensional quantum mathematics. It models states in complex Hilbert spaces and makes the inner product, linear operators, unitarity, tensor products, and Born-rule measurement explicit.

TURING is **not** a quantum hardware SDK, device simulator, noise simulator, or claim of quantum advantage. The initial implementation uses Python's built-in double-precision complex numbers; results are numerical and tolerance-checked, not exact symbolic arithmetic.

## Initial scope

- Normalized finite-dimensional state vectors over **C**.
- Conjugate-linear-first inner products and Born probabilities.
- Linear operators, adjoints, Hermitian and unitary checks, and expectation values.
- Tensor products of states and operators.
- Standard one- and two-qubit gates for mathematical examples.
- Complete projective measurements and post-measurement states.

The implementation does not execute circuits on physical quantum hardware, sample from a device, model noise, or demonstrate a speedup. It deliberately keeps mathematical definitions separate from simulator and backend concerns.

## Install from a checkout

```bash
python -m pip install ./packages/turing
```

The proposed distribution name is `hyba-turing`; verify namespace availability, approved licensing, package metadata, and release evidence before publishing. Version `0.1.0` is a development baseline, not a published release.

## Minimal example

```python
from turing import HADAMARD, QuantumState, born_probabilities

zero = QuantumState.basis(2, 0)
plus = HADAMARD.apply(zero)
print(born_probabilities(plus))  # (0.5, 0.5), up to floating-point precision
```

## Mathematical conventions

For vectors `a` and `b`, the inner product is `<a|b> = sum(conjugate(a_i) * b_i)`. States must be normalized. A projective outcome `j` has probability `<psi|P_j|psi>` and the post-measurement state is `P_j|psi> / sqrt(p_j)` when `p_j > 0`.

## Release gates

Before a public release, confirm the package name, license, API stability, supported Python versions, test/build results, documentation, provenance, and maintainer/release ownership. Do not market mathematical definitions as hardware capability or quantum advantage.

## Exact cyclotomic layer: `turing.exact`

Since 11 November 2026 this distribution also carries the exact cyclotomic
library that previously lived at `src/turing` as a second top-level package
named `turing` (the two collided on import). It is now `turing.exact`
(rings Z[zeta_p] and Q(zeta_p), exact states, unitaries, measurement,
entanglement measures and the qudit stabilizer tableau). Its tests are
tests/test_turing.py at the repository root.

TURING is the foundation layer: it never imports `chronus`. Chronus depends on
TURING, never the reverse. The distribution is internal (classifier
"Private :: Do Not Upload") and is not delivered to external participants.

## Specification

The build contract for the canonical algorithm suite (Deutsch–Jozsa, Bernstein–Vazirani, Simon, Grover, the quantum Fourier transform, quantum phase estimation and Shor's order finding) is [docs/SPECIFICATION.md](docs/SPECIFICATION.md).
