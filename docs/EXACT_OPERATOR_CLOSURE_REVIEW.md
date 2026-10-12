# Exact operator closure — canonical TURING implementation patch

Owner direction governs the implementation target: first-principles quantum
mathematics, substrate- and hardware-agnostic; no simulations, approximations,
heuristic substitutes or capability demotion based on earlier reports.
This patch changes canonical operators, not just descriptions or truth labels.

Baseline main: `3365bb3c28fe1aeb672e2309556d5979cb8f5d71`.
Feature-branch parent: `99e0ef32f45907cf746242ca101d4a5e53fe3eb7`.

## Defects reproduced and repaired

| Site | Reproduced defect | Implemented correction |
| --- | --- | --- |
| `hilbert._frac`; facade `_turns` | Python floats, booleans and decimal strings were silently promoted to Fraction | Admit int, Fraction, SymPy Rational and integer/rational text only; reject inexact/untyped inputs |
| `QuantumRegister.apply_phase` | Literal nonunitary or float-containing factors could modify a state | Verify exact modulus one before applying a literal factor; rational values continue to mean turns |
| Register and gate domains | Out-of-range indices could escape the declared Hilbert space; booleans passed integer checks | Validate register/gate/control/target domains before mutation |
| Grover phase oracle | Late invalid indices were ignored; duplicate indices could invert a mark twice | Validate the full unique index set before changing any amplitude |
| `assert_normalized`; `verify_unitary` | `assert` statements disappeared under `python -O` | Explicit checks raise the existing AssertionError independently of interpreter optimization |
| `GroverExact.optimal_iterations` | Floating asin/sqrt/pi rounding selected the exact algorithm's iteration count | Select the first amplification peak by exact adjacent rational Born-probability comparisons |
| Facade Grover iterations | `int(iterations)` silently truncated noninteger requests | Require nonnegative exact integer iterations |

The exact gate/state arithmetic remains canonical. No replacement simulation
backend, mock, approximate operator, numerical optimizer or quantum-framework
import is introduced. Exact rationals are not inferred from binary floats.
Literal phase proof failures refuse before mutation; a rational `2` still
means two turns, whereas `ExactComplex(2)` is a nonunitary factor and is rejected.

## First-peak Grover contract

Let N=2^n, A and B be rational coefficients of marked and per-unmarked amplitudes
in units of 1/sqrt(N). With mean=((N-1)B-A)/N, each exact iterate is
A'=A+2*mean, B'=2*mean-B. Success probability is A^2/N.
The controller advances until A'^2 <= A^2, choosing the earlier index on a tie.
For n>=2, adjacent success probabilities increase until the first discrete peak;
n=1 is the exact 1/2 tie and returns zero iterations. This certifies the first
amplification peak, not the maximum over arbitrarily many later cycles.

Cost: O(sqrt(N)) rational recurrence stages with additional rational bit costs.
Removing numerical selection does not establish an asymptotic speedup for this
controller or an oracle cost model. Large-width controller benchmarking remains
an open gate. Explicit iteration requests continue to use exact evolution.

## Validation performed

An isolated environment installed SymPy 1.14.0, pytest 9.1.1 and Black 26.10.1.
The real pinned `hilbert.py`, `quantum_library.py`, `quantum_walk.py` and
`stabilizer.py` were retrieved through GitHub MCP and imported as a local namespace
package. No operator was mocked. Full package initialization, repository conftest
and backend/certificate integration were not included.

- Final new regression suite on baseline: **29 failed, 16 passed** (exit 1).
- Same 45 new cases on patched code: **45 passed**.
- Existing quantum-library family regressions: **14 passed**, including exact
  Bell/GHZ entropy, cycle/hypercube walks, Grover, dyadic/nondyadic QPE,
  QAOA triangle expectation and VQE variational checks.
- Combined patched run: **59 passed, 3 deselected**, exit 0.
- Three backend-registry-dependent existing cases were explicitly deselected,
  not claimed passed. The new suite executes normalization and unitary refusal
  in a fresh `python -O` subprocess and compares small register-level Grover
  evolution with the exact closed recurrence.

Commands and source hashes are recorded in
`docs/exact_operator_closure_local_validation.json`. New tests are formatted
with Black. Existing implementation files retain surrounding formatting rather
than receiving a wholesale formatting rewrite.

## Remaining work and review handoff

This is operator hardening, not completion of the entire requested substrate
family. Remaining exact-library surfaces need the same admission/closure audit:
QFT and density-matrix domains/resource mutation, remaining public int coercions,
opaque/text payload auditing, QSqrt radicand domains, sampling/export boundaries,
and full registry/certificate replay. Existing QAOA/VQE grid scans are classical
control over exact evaluations; this patch does not relabel them as globally exact
optimization or replace them with an unproved quantum optimization capability.

No historical test report is erased, and no simulation label is renamed to claim
an enhancement. Documentation conflicts require code-level resolution and accurate
explanation. D7 is recorded in OWNER_DECLARATIONS.md and traced in the canonical map.

Full TUQC/repository suites, installed wheels/sdists, CI, security, provenance,
benchmarks and release qualification have not run. No independent review is
self-issued; the owner's subsequent team reviews the actual commit, tests and
remaining gaps. No main push, merge, release, deployment or mining activation.
