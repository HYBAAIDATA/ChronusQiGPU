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
