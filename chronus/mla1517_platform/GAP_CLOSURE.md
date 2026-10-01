# MLA1517 / PRIME-DB v3.0 — Production Gap Closure

This release incorporates the ten blocking defects identified in the session review.

## Data integrity and persistence

- `PRIME-DB` owns a versioned 256-byte cursor ABI at `/dev/shm/primedb_cursors`; the twenty cursors are the shared source of truth and are recovered from persistent vertex headers on reopen.
- Vertex files grow by sparse `ftruncate` plus remap, up to `MLA1517_PRIME_DB_MAX_BYTES`. A capacity failure is reported as an explicit storage error; it is never treated as a successful write.
- Query scans revalidate D10 Cassini and increment `query_cassini_faults` for corrupt persisted records.
- The native storage regression covers routing, reopen recovery, growth, and query-time corruption filtering. A sparse boundary test seeds the exact 16,777,216-slot boundary, commits the next state, and verifies cursor 16,777,217 after remap without requiring 16 million redundant writes.

## No-drop ingestion

The producer uses a primary SPSC ring followed by a 64 MiB spill ring. Ring overflow and catastrophic backpressure are separate telemetry counters. When both rings are full, the producer stops consuming the hardware vault rather than dropping a record.

## ABI and telemetry

Telemetry is a fixed 960-byte version-3 ABI. It has explicit offsets for per-lane tests, Cassini faults, query faults, ring overflows, and catastrophic overflows. Python calls the C seqlock snapshot function; it never reads a live read-only mmap. `scripts/abi_check.py` is a build gate.

## Deployment

All four services mount the same named tmpfs at `/dev/shm`; `ipc: service:` is not treated as sufficient by itself. `scripts/docker_shm_smoke.py` statically verifies the mount contract. Docker execution remains a deployment step because Docker is unavailable in this build environment.

## Salamander and measured control

Salamander reads the shared cursor ABI, uses the chi-square imbalance threshold 43.8 after a minimum sample count, and requests failover through an acknowledged Unix-domain control socket with cooldown and dwell. The coordinator applies failover only after acknowledging the request. The measured agent now exposes `record_transition` and `record_observed_result`; no synthetic forward model or simulation is introduced.

## Verification

- `make test`: PASS
- `make release-gate`: PASS
- Python regression: 55 tests PASS
- Requirements audit: 35 checks PASS
- Telemetry ABI: 960 bytes / 11 offset checks PASS
- Native PRIME-DB: growth, cursor recovery, and query Cassini recheck PASS
- Rust, HDL simulator, Docker: unavailable in this sandbox and recorded as explicit boundaries

This release does not claim physical ASIC/FPGA execution, universal acceleration, unlimited capacity, or valid public-pool shares without a negotiated algorithm adapter.

## Exact-math completion pass

The independent layer audit identified four additional gaps, now addressed in v3.1:

- `chronus/mla1517/rings.py` provides exact integer-coordinate `ZPhi`, `ZRho`, `ZPsi`, and `ZTau` quotient-ring types with addition, multiplication, powers, and integer norms.
- `nth_prime` now uses `math.isqrt`, eliminating the floating square-root bound from the exact core.
- `scripts/no_float_in_math_core.py` is an AST release gate for the exact Python math core.
- The C++ progressive/SIMT paths now use exact Padovan recurrence state for D3, exact Lucas state for D6, and deterministic indexed prime addresses for D7 instead of `mix64` placeholders.

The extended root-estimation module remains explicitly an evidence/hypothesis layer; the production exact ring layer does not depend on floating roots.

## Canonical exact quantum subsystem

The repository now has one canonical exact quantum boundary:

- `chronus/mla1517/quantum.py` stores amplitudes in `Q(sqrt(2)) + iQ(sqrt(2))` using rational coordinates.
- `chronus/mla1517/accelerator.py` is the single execution entry point.
- Tensor products, Pauli/Hadamard/S/T gates, CNOT, exact normalization, and declared Pauli-Z quarter-turn evolution are implemented without floating arithmetic.
- Unsupported arbitrary Hamiltonian exponentials and unavailable hardware exact kernels fail closed.
- No CPU approximation is used when the `mla1517_chronus` quantum backend is explicitly requested.

The existing CPU reference connector remains for the non-quantum MLA1517 conformance path and is not used as a quantum fallback.
