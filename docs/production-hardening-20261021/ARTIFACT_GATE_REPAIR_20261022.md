# Artifact qualification gate repair

## Scope and baseline

Baseline: `2d8db02db427cd066f1de129bb0680b7534d13bb` on `PhiEnterprise1/EuclidPhiEnterprise`.

The merged package verifier had lost its source-preflight, environment-isolation,
JUnit-validation and common installed-test helpers. A second definition of
`installed_unified_check` shadowed a damaged first definition, and the mandatory
unified scope duplicated tenancy while omitting production guardrail and other
regression modules. These are release-blocking defects, not evidence that the
product itself failed the installed tests: execution could not reach that stage.

## Changes

- Restore required helper functions and a single explicit installed-test dispatcher.
- Restore twelve unique unified suites, including authority, tenant qualification,
  atomic ingestion, promotion, production guardrails and fail-closed/security tests.
- Preserve observed JUnit counters on failing/skipped runs, while keeping the
  qualification verdict fail-closed. Counter retention is not acceptance.
- Replace the optional THESEUS-dependent suite in the **standalone artifact**
  profile with a no-skip in-process learning/unavailable-custody contract. Keep
  `test_toe_learning_persistence.py` in the source workflow. This is a scope split,
  not qualification of durable restart. No fake persistence backend is introduced.
- Add an explicit standalone qualification profile and unqualified production
  capabilities to the artifact verdict. Publication and certification stay blocked.
- Make orchestration fixtures derive their expected count from the actual suite
  list instead of a stale hard-coded four.
- Run harness regressions in the unified source job before product tests.
- Check out the exact PR head in both unified jobs. Add a data-only downstream
  evidence reporter that checks same-run artifact hashes, candidate commit,
  successful source/installed jobs, completed qualification, passing no-skip
  wheel/sdist test records and the non-production scope before commenting.
- The evidence writer never checks out or executes candidate code. Product/test
  jobs retain read-only permissions; only the isolated same-repository PR writer
  receives comment permission. Missing artifacts/permissions remain failures, not
  permission workarounds or pass evidence. Fork PRs do not receive this writer.

## Local evidence

A focused workspace was reconstructed from exact pinned GitHub file contents.
This was sufficient to execute the release-harness tests, not the full product.
Python 3.13 harness baseline: **24 failed, 6 passed** across the two existing gate
modules. After repair and reporter regression additions: **46 passed** across
`test_toe_package_qualification.py`, `test_toe_unified_installed_gate.py` and
`test_toe_ci_evidence_report.py` (`--noconftest`).

Those tests include fixture child processes, synthetic JUnit and synthetic artifact
JSON. They prove gate/reporter behavior only. They do **not** count as real TOE
wheel installs, product suite results, completed CI or recovery qualification.
The new standalone learning suite has not been executed locally against a built
artifact; the actual wheel and sdist jobs must run it from clean installations.

## Remaining release conditions

1. A fresh real full-checkout CI run must build and install the wheel and sdist,
   execute every mandatory installed suite without skips and retain exact hashes.
2. The readable evidence comment must show the tested candidate SHA and genuine
   job results; a workflow definition alone does not close CI access/evidence.
3. THESEUS durable restart/full-platform model rollback, external tenant/security
   review, live-vendor qualification and deployment load/SLA evidence remain
   separate mandatory deployment conditions. A data-only offline checkpoint or
   successful standalone package does not satisfy them.
4. The full repository suite, release workflow gates, owner/publication decisions
   and deployment approvals remain in force. Nothing here publishes or deploys.

Status: **not yet production-ready**. This change repairs qualification machinery;
it does not self-award a product, deployment or production-readiness verdict.
