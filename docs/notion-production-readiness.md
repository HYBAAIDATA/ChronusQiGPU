# Notion → ChronusQiGPU production-readiness map

Review date: 2026-11-16
Repository: `HYBAAIDATA/ChronusQiGPU`
Main baseline reviewed: `3f30f61d490ee78ca6c8b0bdf1b3df84b1b6a0c1`
Closing branch: [`codex/production-readiness-20261116`](https://github.com/HYBAAIDATA/ChronusQiGPU/tree/codex/production-readiness-20261116)
Closing PR: [#136](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/136)

## Release decision

**NOT QUALIFIED.** This file makes the Notion requirements inspectable from the repository; it does not turn source presence or a green synthetic test into production evidence. Historical qualification manifests and benchmark reports remain provenance only. The current release artifact is deliberately fail-closed until the external evidence packet and owner approval exist.

Status vocabulary used here:

- **SOURCE-PRESENT** — an active source path was found.
- **TEST-PRESENT** — a focused test or replay exists.
- **CI-OBSERVED** — a GitHub Actions run produced the result named below.
- **SOURCE-ONLY** — code exists, but no device/release evidence was supplied.
- **MISSING** — the required implementation or artifact was not found in the active tree.
- **UNAVAILABLE** — the evidence could not be observed in this review.
- **GATED** — intentionally typed-unavailable or held by an explicit release gate.

## Governing Notion records

- [ChronusQiGPU — Mining Production Readiness & Chronos/Tensor Reconciliation — 15 Nov 2026](https://app.notion.com/p/419bcc6fa49981cf9e6cecfa7a838b70?pvs=204)
- [CHRONUS — Canonical Operations Manual & Production Constitution](https://app.notion.com/p/3f0bcc6fa49981ef9b12f67cab2d5f21?pvs=204)
- [Workflow 02 — Hardware & Accelerator Certification](https://app.notion.com/p/3f0bcc6fa49981cfb54ecce36cab9a70?pvs=204)
- [Workflow 03 — Benchmark & Claim Promotion](https://app.notion.com/p/3f0bcc6fa49981f9a501c3ddbeb65507?pvs=204)
- [Workflow 04 — Release, Artifact & Provenance](https://app.notion.com/p/3f0bcc6fa49981e7ad37f18235679bb0?pvs=204)

Notion is the requirements and decision source. It is not a substitute for the repository commit, CI run, device certificate, benchmark raw output, pool acknowledgement, or signed release artifact.

## 16 November 2026 source reconciliation

The July 2026 Geodesic Tensor Engine source is retrievable from the ChatGPT Library and Notion engineering record. The four previously labelled missing symbols are now present in the maintained Python package; **do not copy the monolithic legacy engine into the active tree**. See [the archive reconciliation audit](audits/2026-11-16-source-archive-reconciliation.md) for source paths, archive SHA-256 values, scope and outstanding evidence.

The historical PYTHIA TypeScript mining audit is a separate source lineage. Its routes, singleton state machines and RFX instructions do not exist as literal current-repository paths. Reproduce each risk against the maintained Python Stratum and security boundaries instead of treating an old line number as a current defect.

## 16 November implementation closeout

The review branch closes the reproducible source blockers found on the current
main baseline without weakening the fail-closed release boundary:

- `src/chronus/execution/mining_scheduler.py` now emits the expected Geodesic
  evidence packet for the maintained scheduler, memory and integrity surfaces.
- The clean-checkout qualification runner adds `packages/turing/src` to its
  import path; the exact HYBA Mine workflow and macOS setup install the local
  TURING distribution before Chronus and HYBA Mine. Without that seam,
  `chronus.execution.mining_scheduler` fails with `ModuleNotFoundError` in a
  production-style environment.
- Test fixtures now authenticate tenant-capacity reads, create rollback roots,
  and keep the existing security checks intact. Unused imports and the exact
  mathematical claim-token policy are corrected.
- The frontend dependency graph is refreshed to remove the audited Tailwind /
  PostCSS transitive advisories (local `pnpm audit`: zero findings), and the
  acceptance harness starts the checked-in Next binary directly.

Local exact-current evidence is `2340 passed, 38 skipped, 1 xfailed` on Python
3.12.14, plus the focused package, acceleration, storage, build, Bandit,
purity and mutation checks. The PR's hosted Actions jobs fail before usable
steps/logs are retained (`BlobNotFound` on sampled log downloads), so hosted CI
is **UNAVAILABLE**, not green. The generated qualification and sovereignty
artifacts therefore remain explicitly `NOT_QUALIFIED` / software-evidence-only.

## Requirement-to-repository map

| Notion requirement | Repository implementation and tests | Evidence state |
| --- | --- | --- |
| Exact Chronus math, Lucas/PV and Fibonacci reference workloads | `src/chronus/math/`, `src/chronus/stratum/`, `src/chronus/execution/`; tests under `tests/test_*.py`; `packages/turing/docs/SPECIFICATION.md` | SOURCE-PRESENT; CI result must be tied to the release SHA |
| EnhancedTensorRepresentation v2 and tensor API | `src/chronus/tensor/enhanced_representation.py`, `src/chronus/igpu/tensor.py`, `tests/test_enhanced_tensor_representation_v2.py`, `tests/test_repository_layout.py` | SOURCE-PRESENT + TEST-PRESENT; no physical-backend evidence |
| Exact MPS/TT/MPO surfaces | `src/chronus/tensor/exact_mps.py`, `src/chronus/quantum/ring_mps.py`, `src/chronus/tensor/network.py`, `src/chronus/tensor/types.py`; `tools/compare_product_mps.py` and `benchmarks/acceleration/ring_mps_benchmark.py` | SOURCE-PRESENT; the named “Kellogg” contract is not an active symbol match, so that requirement remains MISSING until mapped |
| PhiTensorCore / GeodesicScheduler / PhiMemoryHierarchy / TopologicalIntegrityGate | `src/chronus/tensor/geodesic.py` now defines all four; `src/chronus/tensor/__init__.py` exports them; `src/chronus/execution/mining_scheduler.py` imports the scheduling/integrity surfaces; `tests/test_geodesic_tensor_migration.py` exercises them | SOURCE-PRESENT + TEST-PRESENT on inspected current main (16 Nov 2026). Historical 24 July implementation and test totals are archive provenance, not current execution evidence; interface-by-interface equivalence, full current-head CI and hardware qualification remain unverified. |
| Partial unfold and folded inference | `tests/test_folded_state.py`, `src/chronus/tensor/`, `src/chronus/opencl_folded_adapter.py` | TEST-PRESENT for folded-state surfaces; exact `unfold_partial*` contract is not proven active |
| Typed tensor contracts, backend router and capability manifest | `src/chronus/tensor/types.py`, `src/chronus/fleet/adapters.py`, `src/chronus/fleet/backends.py`, `src/chronus/fleet/canonical.py`, `src/chronus/igpu/adapters.py`; `tests/test_fleet_adapters.py`, `tests/test_fleet_backends.py` | SOURCE-PRESENT + TEST-PRESENT; physical capability certification is separate |
| OpenCL coverage and fail-closed behavior | `src/chronus/fleet/opencl.py`, `src/chronus/backends/opencl_pv.py`, `src/chronus/execution/opencl_sha256d.py`, `tests/test_opencl_kernel.py`, `tests/test_opencl_miner.py`, CI job `opencl-reference` | CI-OBSERVED on a CPU reference runtime only; physical GPU is UNAVAILABLE |
| Honest CUDA / Metal / ROCm / oneAPI states | `src/chronus/fleet/backends.py`, `src/chronus/fleet/cuda.py`, `src/chronus/igpu/adapters.py` | Typed-unavailable paths are GATED; no device certificate for any of these backends |
| Stratum mining proof boundary | `src/chronus/stratum/`, `src/chronus/execution/mining_entrypoint.py`, `src/chronus/stratum/gatekeeper.py`, `tests/test_mining_readiness.py`, `tests/test_stratum_*.py` | SOURCE-PRESENT + TEST-PRESENT; no live pool acknowledgement artifact |
| Mining evidence packet | `deploy/hyba-mine/READINESS.md`, `deploy/hyba-mine/control.env`, `hyba-mine/` historical run evidence | The owner hold is preserved; device, soak/recovery, pool acknowledgement, SBOM/provenance and approval are MISSING |
| ML-DSA and receipt signing | Maintained provider API in `src/chronus/crypto/signers.py`; explicit provider tests in `tests/test_signers.py`; experimental non-conformant module remains in `src/chronus/security/signers.py` | TEST-PRESENT for provider behavior; FIPS/HSM production custody is not established |
| Benchmarks and claim promotion | Runners in `benchmarks/` and `scripts/benchmarks/benchmark_gatekeeper.py`; withdrawn report `docs/reports/chronus_gpiu_v36_benchmark.md` | Runners are SOURCE-PRESENT; no current immutable, device-bound claim packet |
| Release chain | `.github/workflows/ci.yml`, `.github/workflows/packages.yml`, `.github/workflows/chronus-evidence-qualification.yml`, `.github/workflows/storage-reference.yml`, `scripts/ci/manifest.py` | CI is observable; release qualification remains GATED by external evidence |

## 16 November: durable receipts and AL HARAS mining controls

- **SOURCE-PRESENT / TEST-PRESENT, no runtime certificate:** `src/chronus/security/durable_receipts.py`
  now preserves signed receipt chains in the existing THESEUS journal and verifies
  integrity, tenant separation, replay and key binding after a new service instance
  opens the same store. Gate G2 in `src/chronus/core/facade.py` uses this path
  rather than relying on an in-memory chain. See
  `tests/test_durable_signed_receipts.py`.
- **SOURCE-PRESENT / TEST-PRESENT, controls not deployed:** All nine mutating and
  two read-only `/v1/mining/admin` routes use
  `get_mining_admin_operator`. A verified system-admin JWT,
  explicit subject and tenant configuration, stable signing secret and successful
  THESEUS admission journal are mandatory. Static tenant bearer tokens do not
  acquire global mining authority. See `tests/test_mining_admin_admission.py`.
- **SOURCE-PRESENT:** Both Kubernetes manifests use `/health/ready` in place
  of global mining telemetry, eliminating the static-token readiness probe.
- **ARCHIVE-DIGEST VERIFIED:** The original November PULVINI handoff matches
  maintained source, test, integrity guard and workflow Git blobs. The protected
  research document contains later changes and is not overwritten. GitHub
  ruleset enforcement and executed CI remain separate required evidence.
- **UNAVAILABLE:** Historical Kellogg source implementation itself is not in
  the examined archived ZIP inventories or accessible through the connected
  old GitHub repository; its exact semantics are not represented as restored
  without matching source and tests.
- **OUTSTANDING:** Legacy `access_control.py` authority integration, distributed
  receipt append, real HSM/KMS custody, accepted live shares, actual hardware
  execution, soak/rollback and current-head CI remain unverified.

## Required mining packet

The Notion page requires one immutable packet for the exact release commit:

1. commit, branch and clean/dirty state;
2. Python/toolchain/dependency versions;
3. clean package build and SHA-256 digests;
4. full CI URL, commands and raw outputs;
5. focused Stratum, scheduler, elevation, SHA-256d, stale-work, restart and submission tests;
6. tensor contract/router/fold/inference/advisor tests;
7. device census, fingerprint and backend certificate;
8. reference-vs-device differential;
9. sustained execution and failure/recovery evidence;
10. measured work, latency/throughput, memory/bytes moved and instrumented power;
11. live Stratum job receipt and literal pool acknowledgement;
12. receipt/provenance hashes;
13. SBOM, signed provenance and rollback artifact;
14. explicit owner approval.

The repository currently supplies source and synthetic/CPU-reference tests for several rows, but not items 7–14. That is why the status cannot be promoted.

## CI observations used for this closing pass

The historical main baseline had concrete failures, not a qualification result:

- CI run [43669370042](https://github.com/HYBAAIDATA/ChronusQiGPU/actions/runs/43669370042): Python test, lint/compile/package, static-security and purity failures.
- Packages run [43669369942](https://github.com/HYBAAIDATA/ChronusQiGPU/actions/runs/43669369942): wheel checks passed; hygiene and packaging checks exposed stale temporary workflow and source errors.
- Chronus evidence run [43669370018](https://github.com/HYBAAIDATA/ChronusQiGPU/actions/runs/43669370018): test extra/evaluator artifact failures.
- Storage run [43669370069](https://github.com/HYBAAIDATA/ChronusQiGPU/actions/runs/43669370069): claim-token script could not import the source package.

PR #71 records an earlier remediation attempt. PR #136 is the current closing
branch and contains the exact-current fixes listed above. Its latest hosted
Actions attempts (`43844663572`, `43844663589`, `43844663557`, `43844663725`,
`43844663665`, `43844663583`) fail before usable job steps/logs are retained;
the CI run `43844663637` was still partly queued when observed. Sampled log
downloads return Azure `BlobNotFound`; no hosted result is promoted to
qualification.

## Promotion rule

Do not change this file or `manifests/historical/PRODUCTION_QUALIFIED.json` to “qualified” because a README, test count, dispatch, device presence, or single benchmark is green. Promotion requires the exact Workflow 01–04 sequence, the evidence packet above, and owner approval. Failed attempts remain traceable.
