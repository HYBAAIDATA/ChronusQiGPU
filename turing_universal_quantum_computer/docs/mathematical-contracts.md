# Mathematical contracts and reproducibility

## Authority and domains

The native dense path represents admitted amplitudes exactly in the existing
algebraic field; stabilizer execution represents its admitted Clifford states
exactly. Representation admission precedes evolution. A memory/domain refusal
is not an approximate result. No angle rounding, truncation or covert fallback
may turn a different computation into the requested one.

`Program` is the existing native gate IR. `CircuitIR` snapshots its operations.
Compilation validates native gates, arity, distinct/in-range qubits, configured
resource envelope and representation compatibility; its v1 layout is identity.
It does not execute or silently introduce routing/optimization transformations.

`ParameterSpec` declares a nonempty finite numeric domain, with optional finite
bounds. `ParameterBindings` identifies values by the exact schema name/order.
Missing, reordered, duplicate, non-finite or out-of-domain values are invalid.
Values are finite float identifiers for explicitly materialized native programs,
not arbitrary rotation angles and not arbitrary-precision parameter identities.
Do not use integers beyond float's distinguishable range as distinct labels.
The materialization budget must be admitted before invoking a family builder.

## Preconditions / postconditions

| Operation | Preconditions | Postconditions / invariant |
| --- | --- | --- |
| `compile` | Valid native program or explicitly bound finite family, compatible configuration | No execution; target, source/schema/config/layout and implementation fingerprints retained |
| `submit` / `run` | Artifact revalidates against this backend/configuration; explicit valid readout if sampling | Typed job/result; source and target match; canonical PASS/certificate/witness required |
| `estimate` | Explicit supported in-range Pauli Z observable | Analytic exact coefficients or labelled sampled estimate; measurement definition and uncertainty method retained |
| `run_vqe` | Declared finite family, named initial point, positive evaluation budget, analytic estimation | All members admitted first; exact ordering; exhaustion proves a minimum only within this declared family |

The exact Z expectation is `a + b*sqrt(2)` with rational coefficients. Analytic
normalization is checked exactly. Exact candidate ordering compares rational
squares/signs rather than rounded display energies. Ties retain the first
candidate in the deterministic evaluation order (initial point first).
An iteration limit returns `converged=False`; operational failures raise typed
exceptions and are not reinterpreted as ordinary nonconvergence.

## Exact versus diagnostic values

- Exact amplitude coordinates, expectation coefficients and exact comparisons
  require equality, not floating tolerances.
- Float energy displays are conversions, not authoritative certificates. Small
  fixture display comparisons use explicit absolute tolerance where necessary.
- Sampled Z uses the declared seed/readout/shots. The empirical standard error
  is `sqrt((1 - mean**2)/(shots - 1))` for at least two shots. It is not a
  confidence interval, hardware fidelity estimate, or proof of convergence.
- Identical exact inputs/settings/implementation must reproduce mathematical
  payloads. Job IDs, timings and envelope-specific notes need not be identical.
- Seeded sampling is tested under a fixed supported environment. Cross-version
  bitstream identity is not promised unless independently demonstrated.

## Independent evidence

The qualification suite uses analytic basis-state parity, gate/inverse identities,
Bell and radical cases, independently ordered SymPy algebraic expressions,
generated invalid domains, and direct canonical-versus-facade comparisons.
These check different error classes: differential agreement alone cannot prove
that two paths do not share a defect. Generated examples are deterministic and
bounded; they are not a formal proof, universal complexity result or quantum
advantage experiment. Targeted corrupted-evidence tests are fault injection. A separate disposable-copy
runner verifies three explicit mutants (parameter identity, exact ordering and
normalization) after an unmutated control passes. This is not a completed
whole-project mutation-testing campaign or a general mutation score.

Ill-conditioned floating algorithms elsewhere in the engine need their own
conditioning, tolerance and stability studies. Exact-field tests do not certify
the numerical behavior of every algorithm in the broader package.
