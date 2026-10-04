# Tensor production boundaries

This record defines the production gate added after the repository rebuild.
It complements `docs/TENSOR_ARCHITECTURE.md`; executable code and tests remain
the authority when prose is stale.

## Ownership

- `tensor/` owns backend-neutral contracts, policy, routing, measurement and
  provenance.
- `chronus/` owns physical tensor execution. OpenCL, CUDA and Metal paths are
  explicit and fail closed; their hardware claims require device-bound
  evidence.
- `toe/poincare_golden_11d.py` owns the 11-D mathematics and transport codecs.
- `millennium/poincare_golden_11d.py` is now a compatibility re-export, not a
  second implementation.
- Kellogg/Turing own exact algebra. PULVINI owns reversible fold semantics.
  Neither is duplicated in `tensor/`.

## 11-D precision gate

The 11-D substrate is authoritative Float64 for `structural` and `certifying`
roles. Those roles run through the host/reference path until a distinct FP64
Chronus implementation has:

1. an explicit FP64 kernel and ABI (not merely an advertised device extension),
2. numerical comparison against the Float64 reference corpus,
3. adversarial boundary and residual-collapse tests,
4. device-bound provenance and durable evidence, and
5. an acceptance threshold recorded in the capability manifest.

`decorative` and `parametric` roles may use Float32 only when the caller:

- explicitly selects Float32,
- sets `allow_lossy=True`,
- declares a finite maximum absolute residual, and
- accepts the measured residual computed before dispatch.

`tensor.poincare11d.prepare_poincare11d_transport()` enforces this contract.
No automatic downcast or cross-backend fallback is permitted.

## Rebuild safety correction

The rebuilt repository contained two copies of the 11-D module. The canonical
`toe` copy had the correct fail-closed role policy, while the `millennium` copy
still exposed an unconditional Float32 conversion. The compatibility namespace
now re-exports the canonical module, closing that bypass and preventing future
mathematical or policy drift.

## Remaining external gates

- Merge the prerequisite Chronus dispatch-validation change that proves output
  shapes and uint32 addressing bounds before allocation/launch.
- Run the focused Tensor and 11-D suites in CI.
- Certify OpenCL/CUDA/Metal numerical agreement on physical devices and bind the
  evidence to the actual tensor device fingerprint.
- Keep physical compression, HBM elimination, energy and performance claims
  unasserted until matched hardware measurements exist.
