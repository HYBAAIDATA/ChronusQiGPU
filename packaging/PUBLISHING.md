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
8. Continue in dependency order (see `OWNER_CREDENTIALS.md` §4 for the wave
   table): THESEUS then OVID via `storage-publication-preparation.yml`, TOE via
   `toe-release.yml`, EUCLID last via `euclid-v17-release.yml`.
   `hyba-pythia-consumer` carries no registry-resolved HYBA dependencies and
   may dispatch in wave 1 via `consumer-publication.yml`.
9. After each wave, download the workflow's receipt artifacts into
   `release-evidence/` and re-run `portfolio_release_audit.py` — states must
   advance by evidence, and an `INCIDENT` means remediate (patch release),
   never re-dispatch or claim rollback.

Current Actions execution and registry uploads have **not** been verified for
the branding commit. Existing frozen-RC notes describe their original names
and SHA; they are historical, not renamed-package qualification.

## Local re-qualification before dispatch

Each publish-order product has an executed local gate; run all of them on the
frozen RC before any `publish=` dispatch. All seven passed at `bf7acb18`:

```bash
python packaging/kellogg-tensor/build_and_verify.py          # KELLOGG
python packaging/turing/build_wheel.py                        # TURING wheel+sdist
python packaging/storage-release/build_and_verify.py \
    --product all --source-tests                              # THESEUS + OVID
python packaging/toe/build_and_verify.py                      # TOE
python packaging/euclid-engine/build_and_verify.py            # EUCLID
python packages/pythia-consumer/verify_bundle.py              # consumer bundle
```

Then `python packaging/portfolio_release_audit.py --sha <rc> --offline` must
show every product `QUALIFIED` with zero stale evidence — that is the green
light to start `publish=testpypi` dispatches.

## Remaining products

THESEUS (`hyba-theseus-storage`) and OVID (`hyba-ovid-data-organisation`) have
owner naming records, executed preparation gates, and a complete OIDC publish
lane in `.github/workflows/storage-publication-preparation.yml` (dispatch
`publish=testpypi|pypi` with the frozen `rc_sha`). The lane composes
RC-bound release verdicts, uploads THESEUS to TestPyPI, runs a 4-interpreter
clean-registry custody voyage, then uploads OVID — whose
`hyba-theseus-storage==1.0.0` pin is required to resolve from the same
registry — and promotes the same digested bytes to PyPI before creating the
evidence-linked GitHub releases. Trusted publishers for both names must be
configured against `storage-publication-preparation.yml` with `testpypi` and
`pypi` environments; `upload_authorised` in the owner records stays `false`
evidence until that configuration exists — upload authorization is exercised
through the reviewer-gated environments, not the file.

TOE (`hyba-toe-intelligence`) depends on KELLOGG. `toe-release.yml` now carries
the full protocol — verdict → TestPyPI upload → smoke → same-bytes PyPI
promotion → PyPI smoke → evidence-linked release — gated on
`hyba-kellogg-tensor` presence on the target registry.

EUCLID (`hyba-euclid-intelligence==1.0.0`) is a research-package candidate,
containing generation 17.0.0. Its duplicate legacy metadata definition is not a
second package. Research claims and bundled cross-product dependencies remain
bounded and disclosed; neither artifact existence nor naming certifies production.
`euclid-v17-release.yml` carries the full OIDC lane and fails closed unless
`hyba-kellogg-tensor`, `hyba-toe-intelligence` and `hyba-theseus-storage`
`1.0.0` resolve on the target registry — dispatch it last.

PYTHIA consumer (`hyba-pythia-consumer`) runs `.github/workflows/consumer-
publication.yml`: bundled-wheel build + digests → 4-interpreter installed smoke
→ catalog/namespace verdict → OIDC TestPyPI → smoke → same-bytes PyPI → smoke →
evidence-linked release. The bundle vendors `aethel`/`hyba_db`/`chronos_one_igpu`
— it must not be co-installed with the singular sibling wheels, and its
qualification is not evidence for theirs. Local gate:
`python packages/pythia-consumer/verify_bundle.py` (requires `twine`).

## Portfolio release audit — the control plane

`packaging/portfolio_release_audit.py` derives one state per publish-order
product from the workflow contracts, local verdicts, executed receipts under
`release-evidence/` and live registry state:

```text
BLOCKED → QUALIFIED → TESTPYPI_VERIFIED → PYPI_VERIFIED → RELEASE_COMPLETE
                                                       + INCIDENT (reported)
```

```bash
python packaging/portfolio_release_audit.py            # latest evidence
python packaging/portfolio_release_audit.py --sha <frozen RC>   # strict RC audit
python packaging/portfolio_release_audit.py --receipts release-evidence --out verdict.json
```

Every state is evidence-derived. A PyPI presence without executed smoke
evidence is an incident requiring remediation, never a quiet success or a
claimed rollback. CI keeps the audit green via
`.github/workflows/portfolio-release-audit.yml`.

CHRONOS/CHRONUS, SALAMANDER and PYTHIA retain separate qualification tracks.
Canonical development metadata versions were reconciled to the approved
first-public 1.0.0 identity — that is a naming/version alignment, not release
qualification. `hyba-chronus-igpu` is scaffolded; `hyba-chronus-tensor`
remains planned and requires a scaffold plus ownership review before
qualification.

## Truth boundary

Standalone package publication and whole-platform production qualification are
separate evidence tracks; neither inherits readiness from the other. A qualified
TURING software VQC does not establish iGPU closure, physical QPU execution,
mining hashrate or pool acceptance. Absence of runtime/custody/gate evidence
stays unavailable, not green. No upload or production readiness is asserted here.
