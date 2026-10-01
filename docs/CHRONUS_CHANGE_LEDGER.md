# Chronus change ledger

This ledger records every change introduced by the Chronus enterprise
production-hardening branch and its effect on capability.

| Change | Purpose | Capacity / behaviour impact |
|---|---|---|
| Add `chronus/measurement/workload/device_tensor.py` | Measure physical Chronus OpenCL tensor throughput and verify numerics independently | Additive measurement only; no existing execution path replaced |
| Add `chronus/measurement/system/execution.py` | Bind measured work to the physical execution-device fingerprint rather than confusing it with logical contract identity | Evidence/provenance only; no routing change |
| Extend `build_artifact(..., device_fingerprint=...)` | Allow production evidence to bind an explicitly proven execution fingerprint while preserving historical caller behaviour | Backward-compatible API extension |
| Add `chronus/measurement/production.py` | Layer physical tensor evidence and provenance on top of the existing measurement stack | Additive entry point; existing `measure_chronus` unchanged |
| Add persistent-attestation status/CLI gate | Distinguish durable client-grade HMAC evidence from ephemeral local signing and allow hardware acceptance to require the former | Evidence-policy only; no compute/runtime effect |
| Strengthen `EvidenceStore.load` | Recompute persisted artifact digest instead of accepting presence of a digest field | Evidence validation only; no compute effect |
| Extend hardware acceptance workflow | Retain existing strict hardware gate, add Chronus production measurement, require a durable attestation key, upload evidence even on failure, fail at end if either gate failed | Gate becomes stricter and more observable; execution capacity is unchanged |
| Add `chronus/delivery.py` | Codify Embedded and Cloud Instance as two explicit first-class delivery methods | Descriptive/provisioning layer; no automatic routing/fallback |
| Add delivery, attestation-policy and production-measurement tests | Protect evidence semantics, device binding, durable attestation, no cross-delivery fallback, and numerical verification | Test-only |
| Update `docs/CHRONUS.md` | Document the two delivery methods and evidence boundary | Documentation only |
| Add `docs/CHRONUS_DELIVERY_MATRIX.md` | Record current evidence-backed capabilities for Embedded and Cloud Instance delivery | Documentation only; does not rank or limit either mode |
| Update Phase 5 threshold wording | Make clear the 10 EH/s threshold is a promotion threshold, not a measured result by itself | Documentation truth-boundary only |
| Extend import-audit gate evidence output | Persist findings and include rendered details in the gate reason | Same pass/fail criterion; adds diagnostic evidence |
| Add production-hardening documentation and this ledger | Make the branch's design, limitations and impacts explicit | Documentation only |

## Explicitly not changed

- No Chronus kernel was removed or replaced.
- No supported tensor operation was removed.
- No mining scan path was disabled or throttled.
- No host benchmark was suppressed.
- No CPU/OpenCL/CUDA/Metal execution substrate was removed by this branch.
- No automatic Embedded-to-Cloud or Cloud-to-Embedded fallback was added.
- No measured performance value was replaced by a theoretical value.
- No remote Chronus endpoint was removed or narrowed.

## Current known parity boundary

The existing `remote_opencl_v1` cloud agent advertises `ladder` and `sha256d`.
The local Chronus runtime additionally has tensor execution. This branch does
not falsely advertise remote tensor execution. Closing that parity gap requires
an additive verified wire surface and corresponding tests; the existing cloud
paths remain intact meanwhile.
