# PYTHIA — Canonical Mining Product Status

## Product boundary

PYTHIA has one function: operate the mining system, measure real device and
pool outcomes, and sustain HYBA while Enterprise reaches market. Enterprise
PRIME-DB, treasury, storage, and customer-product implementation are separate
and are not imported, tested, or described as part of this product.

## Canonical implementation

The only active MLA1517 implementation is `chronus/mla1517_platform`:

- exact Python reference and control plane;
- C/C++ host, MMIO, shared-memory transport, telemetry, and persistence;
- exact OpenCL payload with the declared ladder `10, 12, 15, 18, 20, 31, 50, 76`;
- progressive mining and negotiated Stratum coordination;
- fail-closed device, proof, overflow, support, and invariant gates;
- Salamander safety boundary and measured-only actuation.

The TypeScript application is the PYTHIA operator UI, control API, and Stratum
surface. It observes and controls the canonical engine; it does not implement
a second GPU, quantum, topology, or storage runtime.

## Acceptance rule

Every explicit or implied capability named in the PYTHIA implementation
materials is an engineering requirement. It is either implemented and tested,
or it is an open defect. No active path may label an unimplemented capability
as research, optional, simulated success, or future work.

A missing OpenCL device, Docker daemon, HDL toolchain, Rust compiler, pool
credential, or negotiated external proof adapter is an explicit deployment
failure boundary. It cannot be converted into a pass or into a claimed result.

## Measurement and proof

- Hashrate is reported only from executed work or accepted pool shares.
- A CPU execution is never labelled iGPU execution.
- A Cassini seal is an internal MLA1517 invariant, not external proof-of-work.
- Stratum acceptance requires a real negotiated job, credentials, and the
  pool's independent acknowledgement.
- Unsupported translation, absent approval, overflow, torn state, or invariant
  failure fails closed.
- Traceability is not behavioural proof; executable tests are required.

## Verification boundary

The canonical package contains the executable storage, transport, ABI,
seqlock, overflow, failover, measured-transition, exact-ring, no-float, and
OpenCL verification paths. Hardware-dependent gates must be run on the target
host. A host without the required device must report the gate as unavailable
or failed closed; it must never fabricate a pass.

The active repository contains no compatibility shim for the retired M3/iGPU
models, projected topology claims, synthetic fabric registries, or unrelated
quantum-walk paths. The `legacy/` manifest records the boundary. Remaining
legacy files are not production imports and must be removed or explicitly
blocked before release if they are found on the active path.
