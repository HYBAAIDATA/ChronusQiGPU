# HYBA publication catalog

**Naming:** `hyba-<system>-<capability>`. Owner-approved rebrand; no authority, import, CLI or API rename.

## How many packages?

- **13 distinct existing Python distribution candidates** from **14 Python manifests**.
- **1 additional planned CHRONUS split**: **14-package roadmap**, not 14 built packages.
- EUCLID has two definitions for one identity; use `packaging/euclid-engine/pyproject.toml` for the public wheel.
- Four private JavaScript applications are not public distributions. AL HARAS is bundled with SALAMANDER; it is not a separate package in this count.

| System | Public distribution | State | First public target |
|---|---|---|---|
| KELLOGG | `hyba-kellogg-tensor` | EXISTING_SCAFFOLD | `1.0.0` |
| TURING | `hyba-turing-vqc` | EXISTING_SCAFFOLD | `1.0.0` |
| THESEUS | `hyba-theseus-storage` | EXISTING_SCAFFOLD | `1.0.0` |
| OVID | `hyba-ovid-data-organisation` | EXISTING_SCAFFOLD | `1.0.0` |
| TOE | `hyba-toe-intelligence` | EXISTING_SCAFFOLD | `1.0.0` |
| EUCLID | `hyba-euclid-intelligence` | EXISTING_SCAFFOLD | `1.0.0` |
| SALAMANDER | `hyba-salamander-self-healing` | EXISTING_SCAFFOLD | `1.0.0` |
| CHRONOS | `hyba-chronos-mathematics` | EXISTING_SCAFFOLD | `1.0.0` |
| CHRONOS ONE | `hyba-chronos-one-igpu` | EXISTING_SCAFFOLD | `1.0.0` |
| PYTHIA | `hyba-pythia-mining` | EXISTING_SCAFFOLD | `1.0.0` |
| PYTHIA | `hyba-pythia-mining-runtime` | EXISTING_SCAFFOLD | `1.0.0` |
| PYTHIA | `hyba-pythia-consumer` | EXISTING_SCAFFOLD | `1.0.0` |
| CHRONUS | `hyba-chronus-igpu` | EXISTING_SCAFFOLD | `1.0.0` |
| CHRONUS | `hyba-chronus-tensor` | PLANNED_NOT_SCAFFOLDED | `1.0.0` |

The approved first-public version is **1.0.0 for each package** and is now reflected in every canonical manifest: development/research versions (root PYTHIA 0.1.0, MLA runtime 0.3.0, Chronos maths 3.3.0, ONE iGPU 3.11.x, consumer 0.1.0) were reconciled to the first-public identity, and `chronos-one-igpu` was renamed `hyba-chronos-one-igpu`. Only the EUCLID research/runtime manifest retains generation `17.0.0` by design — it is the research lineage, not the public wheel metadata (canonical EUCLID public metadata is already 1.0.0).

## Boundaries and compatibility

- THESEUS storage owns all unchanged `aethel/**`; OVID owns `hyba_db/**` and consumes `hyba-theseus-storage==1.0.0`. Do not split or duplicate the eager `aethel` initializer across wheels.
- `hyba-pythia-consumer` is a **bundle distribution**: it vendors `aethel`, `hyba_db` and `chronos_one_igpu` into one wheel at build time (`packages/pythia-consumer/build_bundle.py`) because the sibling distributions are not yet published. It is a separate consumer track — do **not** co-install it with the singular sibling wheels (top-level namespace collision), and do not treat the bundle as evidence of the singular wheels' qualification.
- KELLOGG is the tensor substrate; TURING VQC consumes it, as do TOE and EUCLID. Do not duplicate their implementation inside a dependent distribution.
- CHRONOS mathematics, CHRONOS ONE iGPU, the scaffolded CHRONUS execution split and the still-planned CHRONUS tensor split remain separate scopes. Module/file ownership must be reconciled before releasing overlapping namespaces.
- The PYTHIA monorepo and MLA runtime have different current package identities; count them separately, but do not infer co-installability or recommend installing the umbrella alongside overlapping split wheels until proven.
- Distribution renaming does not provide a PyPI alias. Legacy names are recorded for migration, not claimed as published compatibility packages. Before uploading, verify registry ownership/history and migrate supported installer/dependency/metadata consumers. Existing Python module names, CLI commands, gate IDs, schema IDs and repository paths stay unchanged.
- Historical reports, measurements, source hashes and frozen RC documents keep their original identities. They must not certify renamed artifacts.

## Publication order and remaining actions

1. Qualify/rebuild **KELLOGG Tensor**, then **TURING VQC**, on a frozen current RC. Publish TestPyPI → clean install/import/entry-point/smoke/replay → same archives via PyPI OIDC → clean PyPI execution → evidence-linked GitHub release.
2. Qualify **THESEUS Storage**, then **OVID Data Organisation**, including real-component composition, negative voyages and fresh-process custody/replay. Naming approval does not enable registry uploads.
3. **TOE Intelligence**, then **EUCLID Intelligence** after their dependencies and current-head qualification. EUCLID remains a research release, not platform production certification. TOE still needs same-artifact, executed TestPyPI promotion evidence rather than registry existence.
4. Keep **CHRONOS mathematics / ONE iGPU / CHRONUS splits**, **SALAMANDER**, and **PYTHIA** on their separate product qualification tracks. Do not borrow their scoped local results or unavailable composition evidence.

Every renamed distribution needs current-commit build/install/testing and digest-bound evidence. Registry namespace availability and OIDC trusted-publisher configuration have **not** been established by this change. The new names require publisher registrations to match. No registry upload, GitHub release, CI pass or production readiness is asserted.

## Reproduce identity/count validation

```bash
python packaging/check_publication_catalog.py
python -m unittest discover -s tests -p test_publication_catalog.py
python -m unittest discover -s tests -p test_registry_release_protocol.py
python -m unittest discover -s tests -p test_storage_publication_preparation.py
```

These are identity/guard tests, not real package qualification. `publication_inventory_baseline.json` binds the original 16 manifest records to the audited base SHA. The checker derives the count and rejects uncataloged/missing manifests, wrong names, duplicate product identities, legacy internal dependencies, CLI/import-ownership drift and private-app leakage. It returns `NOT_EVALUATED` for release qualification, never awards production readiness.

**Decision record:** Standalone package publication and whole-platform production qualification are separate evidence tracks; neither inherits readiness from the other.
