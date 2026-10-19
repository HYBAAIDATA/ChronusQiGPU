# Chronus portable computational acceleration substrate

Chronus converts workload intent into an evidence-bound execution on a capability-negotiated substrate. Intel OpenCL is the first physically evidenced adapter, not the product identity.

## Active transaction

```text
ABI admission and quota
→ capability manifests
→ representation candidates
→ folded-memory and geodesic cost
→ bounded Lucas–Pisot candidates
→ evidence-informed plan selection
→ fail-closed adapter execution
→ verification authority
→ Aethel custody
→ signed/content-addressed evidence ledger
→ persistent optimisation feedback
```

## Truth boundary

A capability is advertised only when its adapter reports available. CUDA, ROCm, oneAPI, Metal, cloud and ASIC identities remain unavailable until real execution and verification exist. Lucas–Pisot values generate bounded candidate geometry; measured execution decides promotion. SHA256d and target/pool validation remain mining authority.

## Evidence ledger

`EvidenceLedger` stores canonical JSON artifacts under `evidence/<sha256>.json` (the same content-addressed directory durable memory persistence uses) and query metadata in SQLite/WAL. Set `CHRONUS_EVIDENCE_HMAC_KEY` for authenticated chains. SHA-256 alone is tamper-evident, not identity-authenticated.

## Execution classes

`DENSE_NATIVE`, `FOLDED_NATIVE`, `PARTIAL_UNFOLD`, `STREAMED_FOLD`, `GEODESIC`, `SYMBOLIC`, and `HYBRID` are canonical planning classes. Adapters must not advertise classes they cannot execute.

## Bounded autonomy

`SAFE_AUTOMATIC` and `BOUNDED_EXPERIMENT` actions may execute automatically. `REQUIRES_APPROVAL` and `FORBIDDEN` actions fail closed. Trials require minimum observation windows, measured improvement, rollback, cooldown and attempt limits; learning persists in `optimizer-state.json`.

## OpenCL legality

Launches intersect device limits with compiled-kernel limits: maximum group size, per-dimension sizes, preferred multiple, device local memory, static kernel local memory, and dynamic local memory. Explicit platform/device/vendor selectors are mandatory; aliases are mandatory only when `HYBA_REQUIRE_HYBA=1` and otherwise act as preferences.
