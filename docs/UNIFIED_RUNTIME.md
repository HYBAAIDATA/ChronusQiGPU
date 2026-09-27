# PYTHIA Unified Runtime — Canonical MLA1517 Mining Path

## Scope

PYTHIA is the operational mining product. Its runtime has one active
accelerated implementation: `mla1517_platform_v3.4`. Enterprise PRIME-DB,
treasury, storage, and customer-service systems are separate products and are
not part of this runtime.

Every capability named here is an implementation requirement. The runtime
must implement it, verify it, or fail closed. It must not substitute a model,
heuristic, simulation, CPU masquerade, or compatibility shim for a required
hardware path.

## Process topology

```text
React/Vite operator UI
        ⇅
TypeScript Express control + Stratum API
        ⇅
mla1517_platform_v3.4
  Python exact reference/control
  C/C++ host, MMIO, transport, telemetry, persistence
  exact OpenCL payload and ladder
  negotiated Stratum adapter
```

The TypeScript layer owns operator presentation, authenticated control, and
pool protocol surfaces. The canonical package owns the mathematical execution
contract, device dispatch, native transport, persistence, and fail-closed
verification.

## Device and execution contract

The canonical OpenCL path must:

1. discover the requested real OpenCL device;
2. compile and dispatch the exact payload;
3. execute the declared ladder `10, 12, 15, 18, 20, 31, 50, 76`;
4. compare device output with the exact reference;
5. persist the verified tensor/invariant payload without truncation;
6. fail closed on device absence, arithmetic overflow, mismatch, or invariant
   failure.

A CPU reference run is a conformance oracle only. It is never reported as GPU
activity or as GPU hashrate.

## Mining and Stratum boundary

```text
negotiated pool job
      ↓
canonical MLA1517 work generation
      ↓
exact device execution and invariant validation
      ↓
independent consensus/proof validation
      ↓
real Stratum submission
      ↓
pool acknowledgement and measured telemetry
```

Internal algebraic seals do not become external proof-of-work by naming
convention. A submission is counted only after the real pool acknowledges it.
Missing credentials, missing jobs, unsupported proof translation, absent
approval, or a rejected share fails closed.

## Persistence and safety

The native path provides the bounded shared-memory transport, overflow
backpressure, telemetry ABI/seqlock, PRIME-DB vertex persistence, cursor
recovery, growth, query-time integrity checks, and Salamander safety veto
specified by the canonical package. Every boundary is executable-testable;
static presence checks are not sufficient evidence.

## Release acceptance

The ordinary release gate checks source contracts and deterministic reference
behaviour. The strict hardware gate additionally requires the actual OpenCL
device and target runtime. If that hardware is unavailable, the strict gate
must fail closed or report unavailable; it must not pass by sleeping, counting
synthetic shares, using projected multipliers, or falling back to CPU.

The only valid production claims are measured claims from the connected device,
real persistence path, and real pool protocol. No unlimited speed, storage,
quantum hardware, or universal acceleration claim is part of PYTHIA.
