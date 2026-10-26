# CI exactness readiness repair

Status: scoped repairs validated locally; repository-wide CI and publication remain unqualified.

## Branch reconciliation

Prepared against `176edece8dae4976aa081c1542ad83becf2882dc`, then reconciled with
`37680f194c404944aafd7bcc1c3386602a311f32` (the merged #17 controller-budget repair).
The latter's `GroverControllerBudgetError`, `optimal_iterations(max_stages=1024)`
admission behavior and new tests are preserved. No main rewrite or forced push.

## Implemented changes

- `GroverExact.certified_peak_iterations()` is an additional compact exact selector,
  not a replacement for #17's bounded default controller. Rational enclosure
  certificates plus integer square roots determine a single integer, without a
  numerical angle, tolerance or approximate quantum output. At 64 qubits it
  certifies 3373259426; 128- and 1024-qubit count requests also terminate in the
  bounded regression subprocess. This does not materialize their amplitudes.
- Exact rational materialization has a declared execution envelope: 4096 iterates
  and estimated `(k+1)*n_qubits <= 2**20` coefficient-bit work. Full register or
  per-basis distribution export is capped at 4096 states. Oversized requests
  refuse before recurrence/register work; no truncation or approximate fallback.
  These are implementation resource contracts, not restrictions on quantum maths.
- Metallic cross-field multiplication raises `ArithmeticError`; the regression
  expectation is updated. Unsupported operand types still return `NotImplemented`.
- Removed two unused facade imports responsible for changed-file F401 failures;
  the catalogue now discloses the rational materialization budget.
- The mandatory conformance producer no longer unconditionally returns `SKIP`.
  It executes the actual canonical register and independent Clifford tableau
  algorithms on 8 fixed vectors in all local X/Y/Z joint measurement bases:
  138 exact distribution comparisons. Every outcome branch is explicitly
  conditioned; no random draw, sampling, float comparison or tolerance occurs.
  Phases, interference, Bell correlations, GHZ and an entangling chain are covered.
  Source-file SHA256 digests and the finite coverage scope are recorded in
  `results/conformance-execution.json` through the existing commit-bound runner.
  Missing implementations raise (runner ERROR); mismatches/partial coverage FAIL.
  This is finite Clifford implementation conformance, not independent institutional
  review, universal algorithm certification or production-composition acceptance.
- `make release-gate` now invokes the supported rollup CLI. The obsolete
  `--require-no-skip` argument was rejected by argparse. The rollup already rejects
  every mandatory SKIP/NOT_RUN, missing, malformed, stale, failed or duplicated
  result unconditionally; that invariant has not been relaxed.

## Exact selector certificate

For N=2**n and theta=asin(1/sqrt(N)), successive success probabilities differ by
`sin(4*(k+1)*theta)*sin(2*theta)`. The first peak is floor(pi/(4*theta)); the N=2
tie chooses zero. For N>=4 the boundary is not an integer: rational cos(2*theta)
at a rational multiple of pi can only be 0, +/-1/2 or +/-1. N=4 has boundary 3/2;
N>=8 has none of those rational cosine values.

Machin's identity `pi=16*atan(1/5)-4*atan(1/239)` supplies alternating rational
bounds. Write asin(1/sqrt(N))=S(1/N)/sqrt(N), where
`c[0]=1`, `c[j+1]/c[j]=(2*j+1)**2/(2*(j+1)*(2*j+3))` and every c[j]<=1.
After J terms the remainder is bounded by `z**J/(1-z)`, z=1/N. Integer floors
of the two enclosures are computed by `isqrt(floor(N*r*r))`; returning only when
both floors agree certifies the exact count. Finite enclosure calculations are
proof witnesses, not approximate returned amplitudes. Widths 1..16 are also
checked against an independent exact recurrence; small register tests remain.

## Local evidence and limits

Python 3.13, real retrieved canonical modules in isolated namespace packages.
**108 passed, 3 deselected**, pytest exit 0. flake8 with the repository's `.flake8`,
ruff E9/F, and compileall pass for the restored/scoped repair files. The run
includes the concurrently merged controller tests, foundation tests, exact
operator tests, existing non-registry facade tests, new conformance/entrypoint
checks and five hermetic rollup-integrity tests.

Three backend-registry integration cases are explicitly deselected because the
complete registry/package checkout is unavailable locally. No CI skip/filter
was added. Root package initializers, repository conftest, full root tests,
installed artifact tests, native/Node/Lean/hardware gates, and the complete
assurance rollup have NOT been qualified. Negative tests deliberately inject
phase/probability faults or incomplete inventories; those executions are never
used to issue a positive conformance receipt. Protocol fixtures are not
production readiness evidence. See the adjacent JSON for source hashes and scope.

## Still required before publication

1. Read all actual CI/check job logs on the latest commit. The GitHub MCP check-run
   endpoint returned HTTP 403; status-only access cannot establish all jobs green.
   The old 41b997 head had a failing mandatory assurance status; the observed
   176edece head had no statuses (pending), not a green verdict.
2. Execute all mandatory producers in a clean checkout, retain their artifacts,
   validate the complete commit-bound rollup and publish its truthful verdict.
   Hardware-only evidence is insufficient for the full assurance manifest.
3. Provide approved signing credentials through the protected execution environment:
   `privileged-path-audit` requires a genuine `MEDIATION_MANIFEST_KEY`. Its absence
   is a FAIL, not a reason to generate a throwaway key or accept unsigned evidence.
   Presence/validity in the real CI environment has not been inspected.
4. Pass complete package/backend/certificate suites and installed wheel/sdist checks,
   formal/native/frontend gates, dependency/provenance and release-candidate checks.
5. Confirm package identity, protected OIDC environments and explicit release approval.
   No package publication, merge, deployment or mining activation was performed.
