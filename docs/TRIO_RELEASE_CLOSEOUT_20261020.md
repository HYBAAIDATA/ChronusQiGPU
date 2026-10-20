# KELLOGG / TURING / CHRONUS close-out — 20 October 2026

**Disposition: implementation corrections prepared; product qualification, mining integration and publication remain blocked.**

Inspected source: `main` at `de152d4b7cf1274b72b1a6a75bb326a0f4a861e0`.
This record does not replace TURING-qualification.md, waive gates, approve a
release, or assert any registry upload. All subsequent evidence must bind the
actual final candidate SHA and exact wheel/sdist hashes.

## Corrections in this change

- Replace legacy repository URLs in the three canonical manifests and their
  relevant builders with `PhiEnterprise1/EuclidPhiEnterprise`. TURING/KELLOGG
  metadata verifiers are changed together with the manifests; both historical
  repository identities remain rejected by those checks.
- Correct KELLOGG staging: the live `../../kellogg` source mapping must become
  `kellogg` **only in the staged manifest**. Otherwise it points outside the
  self-contained build/sdist tree. The live import mapping, catalog interface
  fingerprints, dynamic version and numpy-only hard dependency are unchanged.
- Add an offline wheel ownership checker. It rejects shared install paths even
  for identical bytes, duplicate distributions, unsafe archive paths and
  consumer-bundle/singular-wheel mixtures. It normalizes `.data/purelib` and
  `.data/platlib` paths. This is not dependency resolution, installed consumer
  verification, a supply-chain scan, or mining performance evidence.
- Add ten focused regression tests. Synthetic staging/wheel fixtures test the
  tooling only; they are not built product artifacts or installed acceptance.

## Corrected canonical identities

| Product | Manifest | Actual hard dependencies |
| --- | --- | --- |
| KELLOGG | `packaging/kellogg-tensor/pyproject.toml` | `numpy>=1.26,<3` |
| TURING | `turing_universal_quantum_computer/pyproject.toml` | numpy, sympy, `hyba-kellogg-tensor>=1.0` |
| CHRONUS execution | `chronus/packaging/chronus-igpu/pyproject.toml` | numpy, `hyba-chronos-mathematics>=1.0`, `hyba-kellogg-tensor>=1.0`, `hyba-chronos-one-igpu>=1.0` |

KELLOGG source declares `__version__ = "1.0.0"`; installed metadata, tag and
archive verification are still required. TURING and CHRONUS manifests declare
1.0.0. CHRONUS requires Python >=3.12. The old 3.3.0 / 3.11.3rc2 floors and
unprefixed `chronos-one-igpu` name are not the canonical live dependency graph.
CHRONUS does **not** currently declare TURING as a hard dependency. The requested
KELLOGG → TURING → CHRONUS sequence is a valid operational sequence, but CHRONUS
also needs the separately qualified mathematics and CHRONOS ONE prerequisites.

## 1. KELLOGG — outstanding

- [ ] Run `python packaging/kellogg-tensor/build_and_verify.py` on the final SHA;
  retain wheel/sdist hashes, rebuilt-sdist checks and installed imports.
- [ ] Run `python packaging/kellogg-tensor/run_release_gate.py`.
- [ ] Review the complete declared interpreter matrix from
  `.github/workflows/kellogg-tensor.yml`, not just a local import.
- [ ] Review security/provenance, authorize the immutable candidate, and execute
  TestPyPI smoke followed by same-bytes PyPI promotion through the existing
  controlled workflow. Verify registry downloads and retain receipts.

Direct `pip install ./packaging/kellogg-tensor` is not a substitute for the
staged wheel/sdist and independent installed checks.

## 2. TURING — outstanding

- [ ] Run the product registry verification, quick benchmark and complete
  standalone suite from `turing_universal_quantum_computer/`.
- [ ] Run `python packaging/turing/build_wheel.py` from repository root and
  independent installed artifact qualification against the exact KELLOGG wheel.
- [ ] Close all eight gates in `turing_universal_quantum_computer/TURING-qualification.md`:
  mathematical validity; compatibility; integration; reliability;
  distribution integrity; security/provenance; operational readiness;
  release approval. Focused tests do not close them automatically.
- [ ] Retain remote matrix evidence, lock/resolution records, independent
  artifact installs, security results, soak/resource measurements and rollback
  rehearsal; obtain actual named reviewer/owner approvals.
- [ ] Preserve Mining in `product_registry.CARVED_OUT`; no TURING hashrate,
  SHA-256d throughput, physical-QPU or pool-acceptance claim is added here.
- [ ] Publish only after the existing controlled release gate approves the
  final artifact tuple and the target registry resolves its dependencies.

## 3. CHRONUS — outstanding

- [ ] Run `python packaging/check_publication_catalog.py` and
  `python -m unittest discover -s tests -p test_publication_catalog.py`.
- [ ] Build and qualify KELLOGG, mathematics and CHRONOS ONE prerequisite wheels
  from their canonical paths. Do not reuse arbitrary `/tmp` or stale dist files
  as final-candidate evidence.
- [ ] Run `python chronus/packaging/chronus-igpu/build_and_verify.py`.
- [ ] Verify clean imports, installed dependency closure, absent mining modules,
  honest umbrella-bound failures, wheel/sdist parity and unique file owners.
- [ ] Review final matrix, security/provenance, operational and release-owner
  approvals. No hardware or external-pool acceptance is implied by CPU smoke.

## 4. Mining integration — real blocker, not a dependency-only edit

The live root `hyba-pythia-mining` manifest already depends on TURING and
KELLOGG, but does not depend on `hyba-chronus-igpu`. It still bundles `chronus`,
its execution subpackages, `chronus.v33` and `lucas` in its explicit package
list. Adding a CHRONUS dependency without removing the overlapping ownership
is not a safe integration fix. Metadata source mappings alone do not establish
which final wheel paths are present: audit the actual built wheel RECORDs.

- [ ] Make the mining artifact own mining surfaces (including `chronus.mla1517`)
  rather than duplicate execution/mathematics/Lucas surfaces.
- [ ] Add the CHRONUS dependency in that same reviewed boundary change; retain
  the existing TURING/KELLOGG dependencies. Reconcile any affected catalog
  interface fingerprints explicitly; never silently waive the checker.
- [ ] Build the complete selected candidate wheel closure; run:
  `python packaging/check_wheel_ownership.py <explicit candidate wheel paths>`.
  This checker examines exactly the provided set; supply all relevant wheels.
- [ ] Install into a fresh external venv, run `pip check`, and exercise real
  installed mining consumers of Hendrix/Lucas/exact tensors/CHRONUS seams.
- [ ] Independently omit required dependencies and prove refusal before mining
  effects; test uninstall/reinstall ownership and deterministic certificate
  behavior. Do not introduce an automatic fallback success path.
- [ ] Keep `hyba-pythia-consumer` out of the singular-wheel environment.
- [ ] Keep hashrate/capacity/SHA-256d/pool claims and evidence owned by Mining;
  do not infer hardware throughput or pool acceptance from a packaging pass.

## Evidence and access boundary for this preparation

GitHub MCP supplied the selected real source files. A complete checkout was
attempted with `git clone --depth 1` but failed with exit 128 because HTTPS
Git credentials were unavailable. No complete repository was obtained. Product
builds, full suites, installed runtime tests, remote matrix/security results,
registry publication and mining hardware execution were **not performed**.

Local preparation ran only the ten focused unittest regressions against the
selected-source tree and synthetic fixtures. No fabricated commit binding,
release verdict, approval owner or publication receipt is supplied. A complete
checkout (or supplied source archive, accurately classified) and access to
Actions evidence are needed to continue. Required release/security/operational
approvals must come from the actual accountable people.
