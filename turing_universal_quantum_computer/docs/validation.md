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

## Capability-boundary delta

Inspection baseline: PR #96 head `356ab419dae197f407989da82feaa2f149da08e7`.
The canonical engine, native adapter, typed mathematical contracts, optimizer,
Kellogg import fix and package dependency declarations are unchanged by this
follow-up. The only runtime change is the EUCLID credential-provider seam:
translate `(tenant, actor)` to Salamander's `ActionRequest`, and avoid fetching a
credential before the canonical authorizer fetches/handles it itself.

Local evidence, Python 3.13.14 / Linux, source-archive overlay (`development_only`):

- Before that runtime fix: new targeted suite **8 passed, 2 failed**. The real
  authorised heal failed with `TOKEN_PROVIDER_ERROR:TypeError`; a provider outage
  escaped as `OSError` before authorizer handling. This is a reproduced defect,
  not an inferred integration claim.
- After the fix: **20 selected real-component tests passed**, no skips/errors.
  Ten new cases cover actual guarded TURING exact execution and identity,
  missing/expired/cross-tenant credentials, one-use dispatch, closed healing
  without a provider, real authorised requalification, one provider call, evidence
  credential exclusion, and unavailable/invalid/cross-tenant actuation refusal.
  The other ten reuse four canonical Salamander authorization/recovery cases,
  one EUCLID real-guardian case and five shared-custody/handoff/tamper cases.
- The 14 new-boundary/canonical-Salamander cases also pass in TURING's existing
  locked research environment, without adding runtime dependencies. The workflow
  runs these cases and retains their JUnit report on each configured Python
  version; remote outcomes remain unverified.
- Four tests in `euclid/tests/test_actuation_authority.py` fail both before and
  after this runtime fix: their replacement `salamander.authority` module lacks
  the canonical `ALHarasActionAuthorizer` now imported by the real control plane.
  The other two tests pass. These fixtures are NOT accepted proof of authorized
  production healing, nor silently skipped. Their migration remains a broader
  qualification blocker; the new positive evidence uses real authority code.
- New test source passes focused Ruff checks. The full legacy EUCLID runtime has
  an existing unrelated unused `json` import; this delta does not advertise a
  clean whole-module lint result or remove unrelated code to obtain one.

Reproduce the narrow locked check from the monorepo root after the documented
locked environment installation:

```bash
turing_universal_quantum_computer/.venv/bin/python -m pytest -q \
  tests/test_turing_capability_boundaries.py \
  salamander/tests/test_agent_f_closure.py
```

The additional existing regressions selected for the 20-case local run are:

- `euclid/tests/test_runtime_integrity.py::RuntimeLifecycleTests::test_real_al_haras_allow_denial_cross_tenant_and_expiry`
- `tests/test_shared_system_relations_production.py::test_al_haras_real_allowed_verdict_is_custodied_without_moving_authority`
- `tests/test_shared_system_relations_production.py::test_turing_real_pipeline_uses_shared_custody_not_private_theseus`
- `tests/test_shared_system_relations_production.py::test_turing_boundary_replay_rejects_foreign_certificate`
- `tests/test_shared_system_relations_production.py::test_turing_boundary_replay_rejects_result_payload_substitution`
- `tests/test_shared_system_relations_production.py::test_euclid_turing_specialist_is_guarded_and_handoff_enters_turing_custody`

That run used the available monorepo environment (NumPy 2.5.3, SymPy 1.14.0,
pytest 9.1.1), not a freshly installed enterprise distribution. The locked
14-case run used NumPy 2.5.4. Neither establishes deployed identity policy,
cross-customer isolation, a hard cancellation deadline, active default-root
healing, full certificate acceptance of every EUCLID dispatch, or dependency
supply-chain approval. Preserve prior artifact results for their tested revision;
they do not certify a newly built artifact containing these documentation changes.
