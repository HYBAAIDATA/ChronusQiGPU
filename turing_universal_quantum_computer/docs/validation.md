# Package-change validation record

This record covers the package-organization/typed-facade change, not a new
approved release or completed research publication. The canonical engine and
existing publication workflow remain authoritative for their own scopes.

Local validation on Python 3.13.14:

- 228 focused source tests passed, with 63 passing subtests: new API and
  organization suites, product/backend boundaries, tableau measurement,
  production-release checks, root production-pipeline/release-packaging checks,
  and affected Kellogg canonical/evidence-boundary checks.
- 79 API tests passed against installed wheels outside the checkout, without
  source-path injection; the installed `TuringPipeline` example completed.
- The TURING wheel and source distribution built successfully. The source
  distribution includes the lock, examples, experiment scripts, documentation,
  citation metadata, and manuscript scaffold.
- The actual three-case experiment ran with three repetitions (nine
  measurements), validated the exact analytic references, and regenerated CSV
  and TeX from its manifest. Because the local input was an unversioned source
  archive, its evidence is explicitly `development_only`, not commit-bound.
- The new CI workflow repeats focused checks on Python 3.11/3.12/3.13 and
  generates fresh commit-bound artifacts. Its remote outcome must be checked
  after the branch is pushed; local success is not a claim that CI passed.

The broader existing release suite was not re-qualified by this focused change.
Earlier archive-wide checks exposed separate Lucas vendor-parity and phi-ranker
expectation mismatches, plus acceptance tests needing a real Git commit and a
shared production-root Salamander assertion. These were not hidden, weakened,
or presented as solved here. No public release, DOI, publication, performance
advantage, or external-device experiment is certified by this work.

GitHub's targeted secret-scan endpoint was unavailable because Advanced Security
is not enabled on the repository. A local targeted credential-pattern check
found no matches in the staged files; that is not a full security audit.

## Extended software qualification (same local Python 3.13.14 environment)

The follow-up adds explicit mathematical/compatibility contracts, migration and
operations guidance, a release decision ledger, generated API signatures, strict
contract checks, generative tests, targeted mutations and an artifact qualifier.

- Final focused regression run: 268 tests plus 63 subtests passed.
- Strict mypy checks passed for all definitions in the five explicitly listed
  contract/configuration/protocol/exception/optimizer modules. Ruff source lint
  and generated API reference drift checks passed. This is not a claim of 100%
  type coverage for the legacy engine or an SAST/security audit.
- An unmutated control passed; all three explicit disposable-copy mutations
  (parameter identity, exact ordering, exact normalization) were detected by
  test failures without collection/infrastructure errors. This is not a
  whole-project mutation score.
- The exact candidate wheel and the wheel independently rebuilt from the sdist
  each passed 114 installed consumer tests in separate external environments,
  plus dependency consistency checks and the installed example. All wheel file
  contents matched; wheel bytes also matched under a controlled local
  SOURCE_DATE_EPOCH fixture of 1704067200. That fixture is a build experiment,
  not a claimed source-commit timestamp. CI derives the epoch from its actual
  candidate commit. This result does not assert universal build reproducibility.
- Artifact qualification records source state, hashes, dependency-resolution
  hash, lock hash, step outcomes and JUnit hashes. Local evidence remains
  `development_only` because it was produced from the source archive.

No release approval follows from these checks alone. Remaining work includes
full existing-engine/shared-enterprise qualification, remote/platform and minimum
version evidence, long-duration soak/resource baselines, required security and
license scans, named owner/maintainer sign-off, rollback rehearsal, registry
candidate validation and post-publication verification. See
`../TURING-qualification.md`; outstanding items are not silently marked complete.
