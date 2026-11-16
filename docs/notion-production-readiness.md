# Notion → ChronusQiGPU production-readiness map

Review date: 2026-11-15  
Repository: `HYBAAIDATA/ChronusQiGPU`  
Main baseline reviewed: `dc920a82c38ee408fb9698d3206631139f9d0d97`  
Closing branch: [`codex/production-readiness-20261115`](https://github.com/HYBAAIDATA/ChronusQiGPU/tree/codex/production-readiness-20261115)  
Closing PR: [#71](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/71)

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

## Requirement-to-repository map

| Notion requirement | Repository implementation and tests | Evidence state |
| --- | --- | --- |
| Exact Chronus math, Lucas/PV and Fibonacci reference workloads | `src/chronus/math/`, `src/chronus/stratum/`, `src/chronus/execution/`; tests under `tests/test_*.py`; `packages/turing/docs/SPECIFICATION.md` | SOURCE-PRESENT; CI result must be tied to the release SHA |
| EnhancedTensorRepresentation v2 and tensor API | `src/chronus/tensor/enhanced_representation.py`, `src/chronus/igpu/tensor.py`, `tests/test_enhanced_tensor_representation_v2.py`, `tests/test_repository_layout.py` | SOURCE-PRESENT + TEST-PRESENT; no physical-backend evidence |
| Exact MPS/TT/MPO surfaces | `src/chronus/tensor/exact_mps.py`, `src/chronus/quantum/ring_mps.py`, `src/chronus/tensor/network.py`, `src/chronus/tensor/types.py`; `tools/compare_product_mps.py` and `benchmarks/acceleration/ring_mps_benchmark.py` | SOURCE-PRESENT; the named “Kellogg” contract is not an active symbol match, so that requirement remains MISSING until mapped |
| PhiTensorCore / GeodesicScheduler / PhiMemoryHierarchy / TopologicalIntegrityGate | No active-tree symbol match was found for these four names by the repository search at the baseline | MISSING / port check required; archive or prose is not an implementation |
| Partial unfold and folded inference | `tests/test_folded_state.py`, `src/chronus/tensor/`, `src/chronus/opencl_folded_adapter.py` | TEST-PRESENT for folded-state surfaces; exact `unfold_partial*` contract is not proven active |
| Typed tensor contracts, backend router and capability manifest | `src/chronus/tensor/types.py`, `src/chronus/fleet/adapters.py`, `src/chronus/fleet/backends.py`, `src/chronus/fleet/canonical.py`, `src/chronus/igpu/adapters.py`; `tests/test_fleet_adapters.py`, `tests/test_fleet_backends.py` | SOURCE-PRESENT + TEST-PRESENT; physical capability certification is separate |
| OpenCL coverage and fail-closed behavior | `src/chronus/fleet/opencl.py`, `src/chronus/backends/opencl_pv.py`, `src/chronus/execution/opencl_sha256d.py`, `tests/test_opencl_kernel.py`, `tests/test_opencl_miner.py`, CI job `opencl-reference` | CI-OBSERVED on a CPU reference runtime only; physical GPU is UNAVAILABLE |
| Honest CUDA / Metal / ROCm / oneAPI states | `src/chronus/fleet/backends.py`, `src/chronus/fleet/cuda.py`, `src/chronus/igpu/adapters.py` | Typed-unavailable paths are GATED; no device certificate for any of these backends |
| Stratum mining proof boundary | `src/chronus/stratum/`, `src/chronus/execution/mining_entrypoint.py`, `src/chronus/stratum/gatekeeper.py`, `tests/test_mining_readiness.py`, `tests/test_stratum_*.py` | SOURCE-PRESENT + TEST-PRESENT; no live pool acknowledgement artifact |
| Mining evidence packet | `deploy/hyba-mine/READINESS.md`, `deploy/hyba-mine/control.env`, `hyba-mine/` historical run evidence | The owner hold is preserved; device, soak/recovery, pool acknowledgement, SBOM/provenance and approval are MISSING |
| ML-DSA and receipt signing | Maintained provider API in `src/chronus/crypto/signers.py`; explicit provider tests in `tests/test_signers.py`; experimental non-conformant module remains in `src/chronus/security/signers.py` | TEST-PRESENT for provider behavior; FIPS/HSM production custody is not established |
| Benchmarks and claim promotion | Runners in `benchmarks/` and `scripts/benchmarks/benchmark_gatekeeper.py`; withdrawn report `docs/reports/chronus_gpiu_v36_benchmark.md` | Runners are SOURCE-PRESENT; no current immutable, device-bound claim packet |
| Release chain | `.github/workflows/ci.yml`, `.github/workflows/packages.yml`, `.github/workflows/chronus-evidence-qualification.yml`, `.github/workflows/storage-reference.yml`, `scripts/ci/manifest.py` | CI is observable; release qualification remains GATED by external evidence |

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

The main baseline had concrete failures, not a qualification result:

- CI run [43669370042](https://github.com/HYBAAIDATA/ChronusQiGPU/actions/runs/43669370042): Python test, lint/compile/package, static-security and purity failures.
- Packages run [43669369942](https://github.com/HYBAAIDATA/ChronusQiGPU/actions/runs/43669369942): wheel checks passed; hygiene and packaging checks exposed stale temporary workflow and source errors.
- Chronus evidence run [43669370018](https://github.com/HYBAAIDATA/ChronusQiGPU/actions/runs/43669370018): test extra/evaluator artifact failures.
- Storage run [43669370069](https://github.com/HYBAAIDATA/ChronusQiGPU/actions/runs/43669370069): claim-token script could not import the source package.

PR #71 records the historical HYBA Mine artifact first, then fixes the syntax, signer test contract, test extra, import path, exact Stratum difficulty type, dynamic-query security finding, merge-artifact files and temporary/blank workflows. The checks on the latest head are still running; their result must be recorded by SHA before any merge.

## Promotion rule

Do not change this file or `PRODUCTION_QUALIFIED.json` to “qualified” because a README, test count, dispatch, device presence, or single benchmark is green. Promotion requires the exact Workflow 01–04 sequence, the evidence packet above, and owner approval. Failed attempts remain traceable.
