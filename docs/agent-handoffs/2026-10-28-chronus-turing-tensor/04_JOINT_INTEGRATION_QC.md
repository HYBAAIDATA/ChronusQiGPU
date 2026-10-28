# Independent QC assignment — CHRONUS × TURING × Tensor/Kellogg

**Role:** Independent integrator, adversarial reviewer and release-gate verifier. Do not implement the three subsystems' own core changes and then mark your own work certified. Audit the candidate PR heads against the shared governing Notion architecture, the pinned implementation manifests and the exact released installed artifacts. Preserve owner approval control.

## Source hierarchy

Owner-approved [architecture register](https://app.notion.com/p/3f0bcc6fa49981c68659c178cbb72a19) plus [CHRONUS manual](https://app.notion.com/p/3f0bcc6fa49981ef9b12f67cab2d5f21), [TURING manual](https://app.notion.com/p/3f0bcc6fa4998196a609f81164e73565) and [THESEUS manual](https://app.notion.com/p/3f0bcc6fa4998106bbd3f0438cfa393e). Notion governs ownership; code and independently reproducible tests govern implementation truth. If source contradicts owner-controlled docs, issue an explicit decision request rather than silently changing authority. Include retrieval date, page revisions and code SHAs.

## Required cross-component execution trace

1. Instantiate the real approved deployment composition (not direct component method calls exclusively) with AL HARAS authorization and tenant admission.
2. Issue a typed Tensor operation using Kellogg exact algebra. Execute through CHRONUS independent native mode without physical GPU. Independently recompute mathematical result; commit signed/content-addressed evidence in THESEUS; restart in a fresh process and replay; prove semantic invariance, identity and tenant separation.
3. Where a physical backend exists, repeat on the **actual** bound device with recorded fingerprints/driver/kernel, timed synchronization and differential to reference. Without one, mark UNAVAILABLE; do not simulate it and label hardware measured.
4. Issue a TURING Bell/GHZ and a bounded exact-MPS VQC program through the public VQC pipeline, with exact measurement semantics; prove representation/backend adapters and optional CHRONUS dispatch execute rather than merely probe. Check that missing requested outputs or mandatory differential evidence fail closed. Replay checkpoint/results from THESEUS in a separate process.
5. Exercise an OVID reversible/declared transform in each supported workload (with original input digest, transform version, residual/invertibility contract, independent reconstruction) and show THESEUS retains authoritative lineage; search projections, if any, are Geodesic-owned and rebuildable.
6. Exercise PYTHIA-issued sealed Hendrix M32→φ11D→H4/600 resident batch with CHRONUS SHA-256d CPU/software verification and stale-work cancellation, without allowing Tensor or TURING to choose mining semantics or invent pool acceptance.
7. Inject AL HARAS denial, expired tenant credentials, cross-tenant object read/write, missing THESEUS service, corrupted receipt, OVID tampering, backend substitution, partial write, cancellation, device loss and restart/version mismatch. Require refusal or safe recovery with custody of negative evidence.

## Cross-project contract checks

- Exactly one identified semantic owner for each API, algorithm, state representation, transform, execution receipt, access decision, durable record and search projection.
- No package file path collisions in clean installed environments; stable imports, tests of intentional compatibility bridges, exhaustive source-to-package mapping.
- No `Production/Stable`, `passed`, `hardware measured`, physical QPU, quantum speedup, GPU uplift, accepted mining share, or 8K/60fps claim without a verifiable source SHA, artifact and relevant exact-head evidence.
- Mathematical semantics and precision explicit at every boundary; fallback only when permitted by declared policy, never silent CPU substitution when physical execution requested.
- Output/routing/custody evidence shares correlation IDs: source commit, package digests, producer version, request ID, tenant, backend/version/device where applicable, timestamp, validation and replay identity.

## Independent release ladder

- P0: authority map and implementation ownership reconciled, including corrections to erroneous historical or in-repo `COMPLETED_AND_VERIFIED` summaries.
- P1: exact-source current-head unit, property, reference differential, attack and adversarial API tests pass, with baseline-identical vs new failures separated.
- P2: installed package qualification (fresh virtual environment; no editable installs as final evidence), wheel/sdist contents, license, SBOM, lockfile and dependency/version collision check.
- P3: complete composed journey, separate-process restart/replay and tenant/security fault injection.
- P4: backend-specific hardware measurement/certification only when real device exists, and quality/performance benchmarks only for matched work/semantics/baselines.
- P5: owner-controlled change/release/deployment/production-claim decision; **no automatic promotion**.

## Required output

`HYBA_CHRONUS_TURING_TENSOR_QC_VERDICT.md`: each obligation with owner, implementation path, pinned source SHA, exact command, pass/fail/gated, raw evidence, device/custody identity and next fix. State `RELEASE_HOLD` until every mandatory check for the targeted profile is satisfied; available software-only profiles and unavailable physical-lane certifications should remain distinct. Record conflicts requiring explicit owner choice; no unapproved merge, package publication, production declaration or Notion change.
