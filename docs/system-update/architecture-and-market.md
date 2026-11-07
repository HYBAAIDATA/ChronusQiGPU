# Chronus Architecture and Market Model

## 1. Product thesis

Chronus starts from the mathematical substrate, not the accelerator. Where a workload has exploitable exact structure, represent and operate on that structure directly rather than expanding it into a conventional dense form by default. Lucas/Pisot–Vijayaraghavan (PV) identities and the field \(Q(\sqrt5)\) are foundational examples in the current code. The strategic objective is a hardware-agnostic system that can execute independently and then extend suitable work into a client's accelerator or fleet.

The claim is deliberately about a different execution model—not a blanket assertion that every workload compresses, has constant memory cost, or outperforms conventional hardware. Compact inputs and symbolic structure can coexist with outputs whose exact materialization grows with the requested computation.

## 2. System architecture today

```text
Client / Python SDK
        │ bearer-authenticated HTTP + base64-safe payload
        ▼
Chronus API ─── tenant-scoped workload records (SQLite)
        │
        ├── Native reference mode ── Python exact-math backend
        │
        └── Remote adapter mode ─── compatible execution-service API
                                      (deployment supplied)
```

### Mathematical workload layer

`NativeMathReferenceBackend` implements:

- Exact rational coefficient arithmetic \(a+b\sqrt5\), with add, subtract, multiply, and divide.
- Lucas/PV and Fibonacci evaluation using exact fast doubling and \(L_n=2F_{n+1}-F_n\).
- Input validation, a 1 MiB native-backend request limit, and a 100,000 Lucas-index limit.
- Decimal-string outputs so large exact integers remain JSON-safe.

The operation count for fast doubling grows logarithmically in the index, but big-integer arithmetic and output length grow with the values. The code does not establish \(O(1)\) total storage or runtime.

### Execution and integration layer

`ExecutionBackend` defines a backend protocol; `ExecutionRouter` registers and selects implementations by declared workload support. The default registry contains only `python-math-reference`; an experimental OpenCL GPU backend is opt-in. A service can instead forward submissions to `CHRONUS_EXECUTION_BASE_URL`, which must implement the compatible readiness and workload endpoints.

This is the designed extension seam for independent execution and accelerator extension. The experimental OpenCL path discovers GPU-reported devices, compiles a kernel and checks exact parity, but has not been exercised on physical hardware in this environment. It is not a validated CUDA/ROCm/NPU fleet scheduler. The remote adapter's actual device and execution claims are those of the separately deployed service and require independent evidence.

### Service and customer boundary

The FastAPI service provides bearer-token authentication from `CHRONUS_TENANT_TOKENS`, workload submission, tenant-checked retrieval/listing/cancellation, health/readiness, metrics, and receipt endpoints. The SDK supports HTTP submission/retrieval, base64-safe binary framing, explicit timeouts, and retry behavior that avoids replaying non-idempotent workload submissions.

Workload lifecycle records are persisted to a configurable SQLite file and survive process restart on one node. SQLite is not a distributed database, regional replication layer, or high-availability design. Receipt objects and Ed25519 keys remain in process memory and are lost on restart.

## 3. Execution modes and claim boundaries

| Mode | What it means | Evidence in this checkout |
|---|---|---|
| Native reference execution | Mathematical workload executes locally in the Python reference backend. | Implemented and exercised through unit/API/SDK tests for the two supported workload families. |
| Registered backend | An implementation satisfying the backend protocol can be registered and selected by name. | Interface/router implemented; only native backend is registered by default. |
| Remote service adapter | Chronus forwards to a configured API-compatible execution service. | HTTP client integration implemented; no deployed adapter or physical-device outcome is asserted here. |
| Client/fleet accelerator execution | Work reaches a client-owned or fleet accelerator with measured device use. | Product direction; not implemented or demonstrated by this checkout. |
| Simulation/emulation | A non-physical path models an accelerator or system behavior. | Historical repository materials describe simulations; these must not be reported as physical execution. |

No evidence in this repository establishes performance superiority, energy savings, constant-memory scaling, quantum-device execution, formal soundness, post-quantum signatures, regulatory approval, or production qualification.

## 4. Market and operating model

The stated operating footprint is **Dubai/DIFC headquarters** and a **London go-to-market office**, with a global customer base that includes **sovereign clients in the GCC**. Chronus's intended commercial differentiation is the mathematical execution substrate plus the ability to scale across hardware boundaries—not dependence on owning a fixed accelerator fleet.

The technical and commercial motions align as follows:

| Customer context | Chronus proposition | Required proof before committing |
|---|---|---|
| Enterprise | Run structurally suitable workloads through a controlled API/SDK journey. | Customer-selected workload, result correctness, tenancy, service levels, and measured value. |
| Cloud/fleet operators | Route workloads across heterogeneous accelerator capacity through backend adapters. | A real adapter, device telemetry, scheduler behavior, workload portability, and repeatable benchmarks. |
| Sovereign/GCC | Deploy under customer-defined data, residency, access, and operational controls. | Target-country requirements, key custody, residency topology, independent security review, recovery, and applicable authorizations. |

These are market segments and design goals, not verified customer deployments, market-size forecasts, certifications, or commitments.

## 5. Immediate system boundary

The native service is a real vertical slice for the supported exact-math workloads: submit → validate → execute → persist → retrieve, with bearer authentication and tenant isolation checks. It is not yet a production platform for global sovereign workloads. Before making that leap, the work must add and validate physical accelerator integrations, deployment-specific identity/key management, shared durable storage, regional controls, service operations, and customer acceptance evidence.

For code-level implementation status and actual test outcomes, see the [current-state assessment](current-state-assessment.md) and [test evidence](test-evidence.md).
