# Independent QC assignment — CHRONUS × TURING × Tensor/Kellogg

**Owner appointment (28 October 2026): ChatGPT is the independent QC owner, with [QC tracker #94](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/94). This is NOT a GitHub account assignment. Implementation agent assignees remain for the repository owner to allocate. The final gate is actual representative workload correctness/parity and recovery, NOT a benchmark. Only separately approved external comparisons with genuine competitors count as benchmarking. Read [08_OWNER_DIRECTIVE_PRODUCTION_PARITY.md](08_OWNER_DIRECTIVE_PRODUCTION_PARITY.md).**

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

## Mandatory QC conclusion for each subsystem

For each profile independently: record agent PR and SHA, installed artifact digest, exact real input, independently computed expected result, exact/stochastic/numeric parity rule and result, operational bounds/telemetry, custody semantic restore/replay, security/negative tests and outstanding findings. Issue `QC_PASS` only when all mandatory gates are met; otherwise `QC_HOLD`. Compare to a competitor only under a separate owner-approved competitive benchmark protocol. Operational timing/resources are service-safety observations, not comparative benchmarks. [CHRONUS #91](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/91), [TURING #92](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/92), [Tensor #93](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/93) must each be independently assessed, then owner approval may promote `PRODUCTION_READY` for the proved profile.

## Agent assignments and delivery lanes — owner decision (28 October 2026)

| Lane | Named executing agent | Tracking | Completion requirement |
| --- | --- | --- | --- |
| CHRONUS | **Perplexity** | [#91](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/91) | Implementation through independently verified production qualification |
| TURING | **Sider** | [#92](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/92) | Implementation through independently verified production qualification |
| Tensor/Kellogg | **Copilot** | [#93](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/93) | Implementation through independently verified production qualification |
| Repository-wide CI | **GitHub Copilot** | [#96](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/96) | All required workflows execute and pass, with exact-head evidence |
| Independent QC | **ChatGPT** | [#94](https://github.com/HYBAAIENTERPRISE/HYBAEnterprise/issues/94) | Review source and exact artifacts, real-workload parity, security, recovery; owner decision remains final |

**Copilot on Tensor/Kellogg and GitHub Copilot on CI are separate responsibility lanes.** These are the owner's named AI agents; no GitHub usernames, notification deliveries or authenticated GitHub assignments have been inferred. Green CI is a necessary shared engineering gate but not a substitute for correctness, real workloads or QC. [CI workflow instructions](09_GITHUB_COPILOT_CI_GREEN.md).


**Independent QC rule:** a `GREEN` result requires verified executed CI jobs, not an absent or blocked runner. No agent can self-certify its own product, even if it fixes the CI system. QC verdict remains per profile at the actual tested SHA/artifact.
