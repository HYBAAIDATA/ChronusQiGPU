> Current publication names are defined in [HYBA_PUBLICATION_CATALOG.md](HYBA_PUBLICATION_CATALOG.md). Historical candidate names/SHA evidence below are not qualification for the renamed packages.

> **2026-10-11 — naming reconciliation executed.** All canonical manifests now
> carry the approved `hyba-<system>-<capability>` identity and the first-public
> `1.0.0` version (`chronos-one-igpu` → `hyba-chronos-one-igpu`; the 0.x/3.x
> development versions were reconciled, not skipped). The catalog checker is
> green and `hyba-chronus-igpu` is registered as a scaffolded candidate.
> Local artifact gates re-verified on this head: `hyba-kellogg-tensor`,
> `hyba-chronos-mathematics`, `hyba-toe-intelligence` and `hyba-chronus-igpu`
> all produce `VERIFIED` artefacts via `packaging/*/build_and_verify.py`.
> **2026-10-11 (later same day):** `hyba-theseus-storage` and
> `hyba-ovid-data-organisation` now also produce `PASS` preparation verdicts
> (264 + 119 source tests, installed wheel/sdist, custody/restart/negative
> voyages) after two real defect fixes: `aethel` eagerly imported
> `chronus.seam.scale` (undeclared execution-plane dependency) and
> `test_hyba_ontology_store` lacked the custody wiring that `6844e66a` made
> mandatory. `storage-publication-preparation.yml` now carries the full OIDC
> publish lane (verdict → TestPyPI → smoke → same-bytes PyPI → release).
> `hyba-euclid-intelligence` passed `packaging/euclid-engine/build_and_verify.py`
> (11 v17 modules + 11 episodes from the installed wheel) and
> `euclid-v17-release.yml` now carries its publish lane with a fail-closed
> sibling-presence gate (kellogg/toe/theseus must resolve on the target
> registry first). `toe-release.yml` gained the PyPI smoke and
> evidence-linked release jobs it lacked. Every product in the documented
> publish order now has a complete OIDC publication workflow.
> **None of this is registry qualification or upload authorisation** — the
> commit-bound CI verdicts, trusted-publisher configuration and TestPyPI/PyPI
> execution receipts below remain the only publication evidence.

## Qualification status after integrated baseline review

Baseline audited: `c63ff4d7e9d25135b8e2ca17f84da6714d23d5b7`. KELLOGG's recorded
211-pass source result is from `a4df7dc...`, not this integrated head or the new
RC. TURING's former TestPyPI metadata-existence gate is repaired, but registry
execution/publication has not been observed for the repaired candidate. The
release workflows must be rerun on the frozen RC; no current production status
is awarded by these notes. Standalone package publication and whole-platform
qualification remain separate. CHRONUS/iGPU is NOT_CERTIFIED; SALAMANDER
production composition is UNAVAILABLE. See `docs/STANDALONE_RELEASE_RC_PLAN.md`.

TOE's approved first-public identity is `hyba-toe==1.0.0`. EUCLID's first-public
distribution candidate is `euclid-engine==1.0.0`, containing research/runtime
17.0.0 and the unchanged `euclid-v17-research` CLI. Neither statement is registry
publication evidence. Historical notes below are not a frozen-RC certificate.

## Portfolio release control plane (11 October 2026)

`packaging/portfolio_release_audit.py` now derives one evidence-backed state per
publish-order product — `BLOCKED → QUALIFIED → TESTPYPI_VERIFIED → PYPI_VERIFIED
→ RELEASE_COMPLETE` — from the six release workflows' declared contract, local
verdicts, executed receipts under `release-evidence/`, and live registry state.
No state is manually assigned. `--sha` performs a frozen-RC audit that rejects
evidence bound to any other commit; the default latest-evidence mode reports each
verdict's bound SHA and flags staleness against HEAD without discarding it.
Dependency gates require every declared `hyba-*` floor to satisfy its specifier
on the target registry; an immutable PyPI presence without executed smoke
evidence is reported as an incident (`published_without_executed_pypi_evidence`
/ `pypi_smoke_failure`) requiring remediation, not as a rollback or a success.
CI runs it via `.github/workflows/portfolio-release-audit.yml`; unit coverage in
`tests/test_portfolio_release_audit.py`.

Current derived state (latest-evidence mode, offline): all six products
`QUALIFIED` from real local gates; zero `TESTPYPI_VERIFIED`+ because no
publication receipts or registry presence exist yet. External prerequisites
remain: `testpypi`/`pypi` GitHub environments and per-product pending trusted
publishers on both indexes.

# Product release status

Last updated 7 October 2026 for the canonical repository
`QuantumPhiRedux/PhiMiner`.

HYBA Software Limited ships each subsystem as its own product. First public
releases use **1.0.0**. The publication order relevant here is **KELLOGG first,
then TURING**.

## KELLOGG — `kellogg-tensor` 1.0.0

KELLOGG is TURING's declared tensor dependency. The release tooling builds an
exact 1.0.0 wheel/sdist and verifies the installed package before TURING's
release gate is allowed to proceed. The metadata verifier accepts the PEP 639
`License-Expression: MIT` representation emitted by current setuptools as
well as the legacy `License` field.

Registry publication remains a separate owner-controlled action. TURING does
not vendor KELLOGG source or replace its dependency with a monorepo copy.

## TURING — `turing-universal-quantum-computer` 1.0.0

Release identity:

```text
repository: QuantumPhiRedux/PhiMiner
distribution: turing-universal-quantum-computer
version: 1.0.0
publisher: HYBA Software Limited
dependency: kellogg-tensor>=1.0
console: turing-vqc
```

The software VQC implementation is production-hardened: certificate-first
execution, fail-closed backend admission, deterministic effective-seed
provenance, explicit computation certificates and witnesses, first-class
certificate custody, cross-artifact replay verification, durable
THESEUS/OVID integration through production composition, and exact wide-state
representations including the bounded-Schmidt `mps_exact` path.

The release closure adds the publication-quality gates that were previously
missing:

- canonical repository URLs and supported Python 3.11/3.12/3.13 metadata;
- a staged wheel + sdist builder with `twine check`, archive manifests,
  boundary inspection, SHA-256 records, secret scanning and local-path checks;
- clean installed-wheel verification against the exact KELLOGG 1.0.0 wheel;
- installed KELLOGG alias-identity checks for `exact_tensor`,
  `quantum_tensor` and `exact_field`;
- deterministic cross-version fixtures and certificate/state-root equality;
- complete standalone tests plus production composition, custody, replay and
  acceptance regressions;
- full benchmark execution, including the canonical 10,000-qubit
  GHZ + T + S exact voyage;
- TURING-owned Lean verification;
- a machine-readable publication verdict;
- reviewer-gated TestPyPI/PyPI OIDC trusted publishing of the **same exact
  artefacts that passed verification**.

Mining's formal capacity theorem has been removed from TURING's release claim
set and preserved under `mining/formal/MiningCapacity.lean`. TURING's Lean
package now carries TURING-owned algebra only. The separate ONE iGPU / Kronos
workstream remains outside this release.

Canonical workflows:

- verification: `.github/workflows/turing-core.yml`;
- release closure/publication: `.github/workflows/turing-release.yml`.

The release workflow runs in non-publishing mode on the release PR. Publication
jobs are unreachable from pull requests and require an explicit
`workflow_dispatch` choice plus the configured reviewer-controlled
`testpypi` or `pypi` environment.

## Evidence authority

The final publication verdict is
`turing-release-verdict.json`, generated only after the exact candidate SHA
passes the release workflow. It records the wheel/sdist digests, supported
Python versions, product-registry/backend/certificate/custody/replay verdicts,
benchmark verdict, formal verdict, metadata/secret-scan verdicts and
publication state.

Do not infer a pass from source presence or from an older PR. Do not set
`publishable=true` unless the final candidate's mandatory software gates have
actually passed. Do not set `published=true` until a registry upload succeeds.

## Claim boundary

Software VQC evidence is distinct from physical-QPU evidence. The TURING
release does not claim physical quantum hardware, measured quantum speedup,
mining hashrate, cryptanalytic capability or pool acceptance. Mining capacity,
SHA-256d execution and mining thermodynamic semantics remain owned by Mining.

See `packaging/PUBLISHING.md` for the owner-controlled registry sequence.
