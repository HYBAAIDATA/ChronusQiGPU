# Publishing HYBA Software Limited packages

Naming authority: [HYBA_PUBLICATION_CATALOG.md](HYBA_PUBLICATION_CATALOG.md)
and `publication_catalog.json`. **Naming approval is not registry ownership,
upload authorisation or release qualification.** Verify the new namespaces and
configure trusted publishers before any upload. First public version: **1.0.0**.

## KELLOGG / TURING same-artifact publication

| Product | Distribution | Workflow (unchanged path) |
|---|---|---|
| KELLOGG Tensor | `hyba-kellogg-tensor==1.0.0` | `.github/workflows/kellogg-tensor.yml` |
| TURING VQC | `hyba-turing-vqc==1.0.0` | `.github/workflows/turing-release.yml` |

TURING consumes `hyba-kellogg-tensor>=1.0`. Python imports and existing CLIs
are unchanged. New archive names and metadata are not interchangeable with
old `kellogg-tensor` / `turing-universal-quantum-computer` qualification.

For each product, the canonical workflow performs both registries in one
`publish=pypi` dispatch:

```text
frozen rc_sha
→ mandatory current-source product qualification
→ build and retain wheel + sdist with digests
→ TestPyPI upload
→ clean installed/import/entry-point/smoke/replay matrix
→ digest-verified promotion of the SAME archives through PyPI OIDC
→ clean PyPI execution
→ evidence-linked GitHub release
```

`publish=none` requests qualification without uploading. `publish=testpypi`
stops before production. Registry version existence is not executed TestPyPI
verification. A different commit or distribution name requires fresh artifact
qualification. Never copy historical pass receipts or rebuild between verified
TestPyPI artifacts and PyPI promotion.

### Owner/deployment actions

1. Verify namespace ownership/history on PyPI and TestPyPI. Availability has
   not been independently established by the branding change.
2. Configure trusted publishers for each new distribution, owner
   `QuantumPhiRedux`, repository `PhiMiner`, the corresponding workflow above,
   and environments `testpypi` / `pypi`. The old name's publisher registration
   does not authorise a new name.
3. Configure reviewer-gated GitHub environments. Use short-lived OIDC; do not
   place permanent registry passwords/tokens in code, evidence or logs.
4. Freeze a clean RC commit after necessary fixes and run KELLOGG's full suite
   with zero skips plus installed artifact, custody/replay, benchmark and
   cross-version gates. Historical `a4df7dc...` evidence cannot qualify the RC.
5. Run KELLOGG publication with the frozen full `rc_sha`; preserve both registry
   execution receipts, archive digests and the release/run links.
6. Run TURING with the same full `rc_sha` and the completed same-RC
   `kellogg_release_run_id`. It reuses that run's exact KELLOGG archive and
   requires the producer's executed registry receipts, not metadata existence.
7. Preserve run URLs, source SHA, wheel/sdist hashes, TestPyPI and PyPI clean
   execution logs, custody/replay records, registry URLs and GitHub release.

Current Actions execution and registry uploads have **not** been verified for
the branding commit. Existing frozen-RC notes describe their original names
and SHA; they are historical, not renamed-package qualification.

## Remaining products

THESEUS (`hyba-theseus-storage`) and OVID (`hyba-ovid-data-organisation`) have
preparation workflows, owner naming records and unexecuted publication gate
requirements. OVID consumes THESEUS `==1.0.0`. No publisher is enabled by this
change. Execute canonical product suites, installed composition, isolation,
custody and fresh-process replay before designing/using the registry promotion.

TOE (`hyba-toe-intelligence`) depends on KELLOGG. Its existing publication
workflow still needs an executed TestPyPI **same-artifact promotion** protocol;
registry existence must not satisfy production publication. Treat that as a
missing action/evidence requirement, not as a closed gate.

EUCLID (`hyba-euclid-intelligence==1.0.0`) is a research-package candidate,
containing generation 17.0.0. Its duplicate legacy metadata definition is not a
second package. Research claims and bundled cross-product dependencies remain
bounded and disclosed; neither artifact existence nor naming certifies production.

CHRONOS/CHRONUS, SALAMANDER and PYTHIA retain separate qualification tracks.
Four canonical development metadata versions still need first-public version
reconciliation; do not upload 0.x/3.x as their first public releases. Planned
CHRONUS splits require scaffolds and ownership review before qualification.

## Truth boundary

Standalone package publication and whole-platform production qualification are
separate evidence tracks; neither inherits readiness from the other. A qualified
TURING software VQC does not establish iGPU closure, physical QPU execution,
mining hashrate or pool acceptance. Absence of runtime/custody/gate evidence
stays unavailable, not green. No upload or production readiness is asserted here.
