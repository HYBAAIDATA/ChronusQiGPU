# Chronus change ledger

This ledger records every change introduced by the Chronus enterprise
production-hardening branch and its effect on capability.

| Change | Purpose | Capacity / behaviour impact |
|---|---|---|
| Add `chronus/measurement/workload/device_tensor.py` | Measure physical Chronus OpenCL tensor throughput and verify numerics independently | Additive measurement only; no existing execution path replaced |
| Add `chronus/measurement/workload/native_device_tensor.py` | Measure physical CUDA/Metal Chronus tensor throughput with the same independent numerical verification boundary | Additive measurement for native substrates; OpenCL and host measurements retained |
| Add `chronus/measurement/system/execution.py` | Bind measured work to the physical execution-device fingerprint rather than confusing it with logical contract identity | Evidence/provenance only; no routing change |
| Extend execution-device binding with unique-backend evidence | Bind native runtimes whose API label differs from the system chipset label only when the census contains exactly one physical device for that declared backend | Evidence matching expands without guessing across multiple devices; match method is recorded explicitly |
| Extend `build_artifact(..., device_fingerprint=...)` | Allow production evidence to bind an explicitly proven execution fingerprint while preserving historical caller behaviour | Backward-compatible API extension |
| Add `chronus/measurement/production.py` | Layer physical tensor evidence and provenance on top of the existing measurement stack | Additive entry point; existing `measure_chronus` unchanged |
| Make the production physical-device gate substrate-neutral | Preserve the historical OpenCL stage and add CUDA/Metal stages; `--require-device` accepts any verified OpenCL/CUDA/Metal tensor execution | Expands valid Chronus hardware reach; does not remove or deprioritise OpenCL |
| Add tensor-specific device binding gate | Prevent unrelated mining/hashrate device provenance from satisfying the physical tensor acceptance condition | Tightens evidence semantics only; no compute/runtime effect |
| Add persistent-attestation status/CLI gate | Distinguish durable client-grade HMAC evidence from ephemeral local signing and allow hardware acceptance to require the former | Evidence-policy only; no compute/runtime effect |
| Strengthen `EvidenceStore.load` | Recompute persisted artifact digest instead of accepting presence of a digest field | Evidence validation only; no compute effect |
| Extend hardware acceptance workflow | Retain existing strict hardware gate, add Chronus production measurement, require a durable attestation key, upload evidence even on failure, fail at end if either gate failed | Gate becomes stricter and more observable; execution capacity is unchanged |
| Add `chronus/delivery.py` | Codify Embedded and Cloud Instance as two explicit first-class delivery methods | Descriptive/provisioning layer; no automatic cross-mode routing/fallback |
| Make Embedded delivery substrate-neutral | Probe local OpenCL, CUDA, and Metal tensor execution surfaces independently instead of equating Embedded Chronus with OpenCL | Capability visibility expands; existing injected OpenCL probe contract preserved |
| Add `chronus/native_tensor.py` | Add native CUDA and Metal tensor execution paths beneath Chronus | Additive compute capability; existing OpenCL executor unchanged |
| Add Chronus-owned CUDA tensor kernels | Execute `matmul`, `add`, `scale`, `kron`, and `hadamard` through CUDA without OpenCL; explicit kernel registry includes separate rank-1/rank-2 Kronecker kernels | Adds an independent CUDA physical-device path; no OpenCL or CPU path removed |
| Add MLX/Metal tensor runtime | Execute the same float32 tensor operation set on Apple GPU through MLX/Metal | Adds an independent Metal physical-device path; no OpenCL or CPU path removed |
| Add `tensor/backends/chronus_native_backend.py` | Expose `chronus-cuda` and `chronus-metal` through the existing tensor backend contract | Additive backend registration; both fail closed and never internally fall back |
| Extend `tensor.router.default_registry()` | Register CUDA and Metal without changing NumPy/OpenCL priority ordering | Backend reach expands; existing default preference remains unchanged |
| Add native-backend and substrate-neutral delivery tests | Protect explicit CUDA/Metal routing, no-OpenCL dependency, dtype boundary, fail-closed probes, exact CUDA kernel registry, and local delivery visibility | Test-only |
| Extend production-measurement tests | Verify native CUDA numerical measurement, native physical-device binding, substrate-neutral acceptance and preservation of host/OpenCL evidence | Test-only |
| Clarify `docker-compose.cuda.yml` | Record that NVIDIA device reservation is not proof every workload has a CUDA implementation and that native tensor execution needs a compatible CuPy binding | Documentation/comment only; compose reservation behaviour unchanged |
| Update `docs/CHRONUS.md` | Document delivery methods, native tensor substrates, deployment binding requirements, physical measurement semantics and the remaining mining boundary | Documentation only |
| Add/update `docs/CHRONUS_DELIVERY_MATRIX.md` | Record current evidence-backed capabilities for Embedded and Cloud Instance delivery | Documentation only; does not rank or limit either mode |
| Update Phase 5 threshold wording | Make clear the Phase 5 exahash-scale throughput threshold is a promotion threshold, not a measured result by itself | Documentation truth-boundary only |
| Extend import-audit gate evidence output | Persist findings and include rendered details in the gate reason | Same pass/fail criterion; adds diagnostic evidence |
| Add production-hardening documentation and this ledger | Make the branch's design, limitations and impacts explicit | Documentation only |

## Explicitly not changed

- No existing Chronus OpenCL kernel was removed or replaced.
- No supported tensor operation was removed.
- No mining scan path was disabled or throttled.
- No host benchmark was suppressed.
- No CPU/OpenCL/CUDA/Metal execution substrate was removed by this branch.
- Existing OpenCL backend priority was not lowered by the native tensor addition.
- No automatic Embedded-to-Cloud or Cloud-to-Embedded fallback was added.
- No native tensor backend silently falls back to OpenCL or CPU.
- No measured performance value was replaced by a theoretical value.
- No remote Chronus endpoint was removed or narrowed.
- The generic container was not pinned to an assumed CUDA generation.

## Current known parity boundaries

The existing `remote_opencl_v1` cloud agent advertises `ladder` and `sha256d`.
Embedded Chronus now has OpenCL, CUDA, and Metal tensor execution surfaces when
the corresponding physical runtime is present. The cloud wire protocol does
not yet expose tensor execution.

The mining SHA-256d execution path has not been relabelled as native CUDA or
Metal by this work. It retains the existing OpenCL/explicit-CPU implementation
until a separate native mining kernel is implemented and independently checked
by the repository's host acceptance authority. This branch does not infer that
capability from the presence of CUDA or Metal hardware.

CUDA native tensor execution currently requires a CuPy build compatible with
the CUDA runtime provided by that deployment. The repository deliberately does
not pin a CUDA-generation-specific wheel without deployment evidence. Apple
native tensor execution uses the existing MLX optional dependency.

## Validation state

Software contract tests have been added for all new routing, measurement and
provenance semantics. Physical CUDA/Metal throughput is not claimed until those
paths execute on corresponding hardware and emit attested measurements.

The branch's `AL HARAS Evidence Gates` GitHub Actions job is currently failing
before workflow steps/logs are exposed. That unresolved runner/workflow-start
failure is recorded separately from code-test results and is not treated as a
successful or failed execution of the Python test suite.
