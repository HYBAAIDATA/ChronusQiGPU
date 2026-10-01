# Hybrid Solver Fleet — EHS Task Reconciliation

Audit of `hyba/hybrid/` against the EHS hasher prompt's T1–T11 task list.
Every row is verified against the tree at the time of writing; nothing is
fabricated. Verdicts: **present** | **absent** | **renamed/relocated**.

| EHS task | Verdict | Evidence |
|---|---|---|
| T1 — 11D manifold navigator | **present (relocated)** | `toe/poincare_golden_11d.py` — canonical Klein–Poincaré diffeomorphism on the φ-weighted 11-ball (`HYBA-SPEC-POINCARE-11D-GOLDEN-001`). Not inside `hyba/hybrid/`; it lives in the canonical `toe/` package. |
| T2 — 32-face frame builder | **present (relocated)** | `kellogg.quantum_tensor.dual_overlay_frame` (20 icosa + 12 dodeca normals) consumed by `kellogg/traversal.py`; independent exact-copy in `chronus/mla1517/mining/geometry.py::truncated_icosahedron_frame` (spherical-5-design-verified). |
| T3 — geodesic partitioner | **present** | `hyba/hybrid/lucas_partition.py::partition` — 32-face winding partition with Lucas weights from `kellogg.scales` (exact integers), largest-remainder span assignment. |
| T4 — NonceScheduler protocol | **present** | `hyba/hybrid/nonce_scheduler.py` — `NonceScheduler` Protocol, `NonceWindow`, `DeviceCapability`, `DispatchHandle`, `Share`, `verify_share` (double-SHA256). |
| T5 — GPUSolver | **present** | `hyba/hybrid/gpu_solver.py::GPUSolver` — dispatch/poll/cancel, `hashed_count`, attestation per event. |
| T6 — ASICSolver | **present** | `hyba/hybrid/asic_solver.py::ASICSolver` — fail-closed on absent device (`ASICNotPresent`), dispatch attestation. |
| T7 — coordinator | **present** | `hyba/hybrid/coordinator.py::HybridCoordinator` — `StratumJob`/`JobResult`, even + Lucas strategies. |
| T8 — benchmark | **present (renamed)** | `scripts/benchmark_hybrid.py` — paired bootstrap 95% CIs, wall-clock + nonces-to-first-share, `harness_trustworthy` verdict. Name drifted from `benchmark_ehs`; function is intact. |
| T9 — falsification / negative control | **present** | `tests/test_hybrid_signal.py` — T7a negative control (easy target, no traversal may differ), T7b positive control; benchmark also emits `harness_trustworthy`. |
| T10 — Docker/cloud packaging | **present** | `Dockerfile.hybrid` (OpenCL ICDs incl. PoCL for real CPU-device fallback; ASIC stays fail-closed via `HYBRID_ASIC_*` opt-in), `docker-compose.hybrid.yml` (reports volume + device passthrough), `hybrid-fleet` job in `.github/workflows/pythia-ci.yml` (offline signal gates + benchmark smoke + packaging check). |
| T11 — attribution/telemetry | **present** | `ExecutionAttestation` + `AttestationRegistry` in `nonce_scheduler.py`; per-event attestations (`dispatch`, `share`, `exhausted`, `cancelled`) with digests and device time. |

## Coverage certificate per job

**Present.** `lucas_partition.py::CoverageCertificate` carries span
assignments, per-face digests, and `_certificate_digest(cert)`; the
benchmark records `cert_digest` per trial (`asic_only:no_partition` for
the unpartitioned arm).

## Reports

- `reports/hybrid_benchmark.md` — produced by `scripts/benchmark_hybrid.py`
  (see that file for the run verdict).
- `reports/hybrid_falsification.md` — produced by the same run.
- The original prompt asked for `reports/ehs_benchmark.md` /
  `reports/ehs_falsification.md`; names drifted to `hybrid_*`. Declared
  here so the rename is auditable.

## Honest summary

The manifold framing was **not dropped** — it was relocated into the
canonical packages (`toe/` for the 11-D navigator, `kellogg/` for the
frame + traversal). `hyba/hybrid/` contains the solver fleet, the
partitioner, and the coordinator that consume those substrates. T10 was
the only absent item at the time of the original audit and has since
landed: `Dockerfile.hybrid`, `docker-compose.hybrid.yml`, and a
`hybrid-fleet` CI job.
