# SALAMANDER package release preparation

## Reviewed baseline

Repository: QuantumPhiRedux/PhiMiner.
Reviewed main commit: `c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7`.
PR #143 is merged; its implementation is now in the integrated main lineage.
The existing distribution scaffold is `packaging/salamander`, not a new product.

The review is scoped to the standalone product boundary and its integration
seams. It is not an exhaustive audit of the whole PhiMiner project.

## Review findings and preparation

1. Package metadata said Production/Stable while the existing runtime reports
   unavailable production qualification. Use Alpha metadata and explicit limits.
2. The previous builder only produced a wheel, imported eight selected modules,
   and omitted source-head binding, sdist rebuild and complete module-import
   coverage. Add source-bound staged sdist → wheel → archive/Twine → clean install
   → every shipped module → installed boundary tests.
3. The prior discovery-refusal smoke result was recorded but not required by its
   final pass predicate. Require every boundary check, including discovery denial.
4. Current main had partial integration regressions: `_action_key` and
   `_record_circuit` were referenced but absent, recovery used an undefined key,
   and registry execution expected `consume_decision` while the adapter lacked it.
   A valid signed unit action failed before its actuator was called. Restore the
   missing #143 canonical methods and adapter handshake; do not build a second
   authority or replace an owning subsystem.
5. Include MIT notices and typed markers, exclude tests/caches/runtime state,
   record original source digests and check wheel/source equivalence. Keep all
   canonical product modules; do not drop capabilities to pass inspection.

## Publication contract

Planned first public identity: `hyba-salamander==1.0.0`.
This remains an unpublished release candidate, not a production declaration.
The distribution bundles the current `al_haras` namespace as the existing
scaffold intends. Before public upload, review co-installation with the broader
PYTHIA distribution: both distributions may own `salamander` and `al_haras` files.
Do not install overlapping products into one environment without an agreed
namespace/dependency ownership strategy.

The verification workflow runs on Python 3.11, 3.12 and 3.13. Local Python 3.13
results cannot substitute for the other matrix jobs. A job with no executed
steps is unavailable, not a pass; inaccessible check runs do not establish zero
steps. Full monorepo/frontend/hardware qualification is outside this package test.

Mandatory publication prerequisites:

- Exact candidate-source clean builds and passing wheel/sdist/import/boundary
  gates across the declared supported Python matrix.
- Production authority/custody/history/restart/learning/rollback/composition
  gates independently qualified for that exact source revision. Packaging tests
  are not those gates.
- Cross-tenant, fake-success, unavailable-verifier, rollback-failure, evidence
  corruption and recovery-budget adversarial/mutation qualification.
- Namespace ownership/co-installation review and PyPI name ownership confirmed.
- GitHub Actions operational; reviewer-controlled `testpypi` and `pypi`
  environments; owner-approved PyPI OIDC trusted publisher configuration.
- TestPyPI upload and clean index-install verification before production upload.
- Publication of the **same verified artefacts**, with SHA-256 checks; no rebuild
  in the upload job, no permanent PyPI token, and no upload from a pull request.

No publication job is enabled by this preparation. A future publishing lane must
consume independently verified production receipts and the recorded artefact
hashes. Neither a manual boolean nor a green unit suite may unlock it.

## Current production limitations

The default factory still uses a process-local ledger. Normal owner-wide
SystemDataPort wiring, proof producers, canonical durable safety history,
fresh-process replay, context-sensitive learned recovery and required real
mining/CHRONUS/TURING/custody voyages remain unqualified. The library's existing
`unqualified_readiness()` keeps production qualification unavailable.

The package builder computes publishability separately from installability.
A source-build failure produces a failure verdict; it cannot reuse stale output.
Local partial source materialisation is not a complete distribution build.
