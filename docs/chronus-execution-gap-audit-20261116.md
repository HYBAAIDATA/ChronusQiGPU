# Chronus execution and sovereign gap audit — 16 November 2026

**Disposition: NOT QUALIFIED for sovereign production.** This change closes
verified software gaps and supplies a candidate execution surface; it cannot
replace target-host evidence or owner admission.

Baseline: `HYBAAIDATA/ChronusQiGPU`, `main`,
`55ce7bd5ea81b4bb54f2603f5a4a8340bce52a42`, initially clean.
Candidate: `codex/chronus-execution-authority-20261116`; the PR identifies its SHA.

## Governing records consulted

- [CHRONUS canonical manual](https://app.notion.com/p/3f0bcc6fa49981ef9b12f67cab2d5f21), fetched with content as of 15 Nov 2026.
- [Architecture authority register](https://app.notion.com/p/3f0bcc6fa49981c68659c178cbb72a19), effective 5 Oct 2026.
- [Workload admission](https://app.notion.com/p/3f0bcc6fa49981a191bcc8a423e28d79) and [deployment admission](https://app.notion.com/p/3f0bcc6fa49981e1bfc2cbeb5144f068).
- [THESEUS custody constitution](https://app.notion.com/p/3f0bcc6fa4998106bbd3f0438cfa393e).
- [15 Nov reconciliation](https://app.notion.com/p/419bcc6fa49981cf9e6cecfa7a838b70).
- [Geodesic Tensor/PULVINI record](https://app.notion.com/p/ffd11e5552144c30ad38a5aaab0b5fcb) and [consolidation](https://app.notion.com/p/c2f8e65369cb440996f6f3532f08bfb1).
- [Enterprise native substrates/delivery modes](https://app.notion.com/p/7cbb9c98216248c4b6bb7b348b2d98e5).
- Four user-supplied drafts: enterprise sovereign/fleet sketch, FIX-001–019,
  FIX-I1–I6 integration sketch, and the platform-elevation roadmap.

The selected Library directory contained no files, and no Library retrieval tool
was available. Connected Notion content was read directly. Historical counts and
attached archive claims were not substituted for current execution evidence.
Canonical ownership is unchanged: Chronus executes, OVID transforms, THESEUS
preserves, AL HARAS governs security; Geodesic Tensor remains inside Chronus.

## Source reconciliation

The supplied `chronus_execution_authority.py`, MLA1517 `control_api.py` /
`system_fabric.py`, `hybaMiningRuntime.ts` and `HybaMiningEngine` are absent from
this repository revision. The active API is FastAPI, not ThreadingHTTPServer.
A TypeScript HTTP client now exists, but bridging an absent mining engine remains
unavailable. No duplicate legacy control server or separate Tensor product was
created.

The four Geodesic primitives, `MetricTensor`, `PhiGPU`, `HybridGPU`, true
`ExactFoldState.unfold_partial`, folded inference and native tensor adapters were
already present. The older requirement map's MISSING statements are historical
baseline findings, not current source inventory. Existing migration and folded
state tests were run before adding integration changes.

## Closure matrix

| Requirement | Implemented change / evidence | Remaining boundary |
| --- | --- | --- |
| Synchronous execution, wall deadline, concurrency | `execution/authority.py`; spawned workers, shared POSIX slot locks, fixed CPU/memory/output limits; timeout/reaping and multiprocess tests | Host-local, POSIX; OS/service supervisor must handle host crashes |
| Durable receipts / status / forensic replay | Admission and terminal records in durable THESEUS; authenticated tenant-scoped API; AES-GCM customer keys; fresh-process loopback recovery | Custody replay is not recomputation; WORM/replication/retention are deployment gates |
| TS → Python | `frontend/lib/execution-authority.ts`; real local HTTP execution and restart recovery | Absent TS mining engine cannot be claimed integrated |
| FIX-001–003, 006 | Both gateway write methods verify SHA-256d/current work and local AL HARAS policy; endpoint allowlist; default disarm; target-capacity reservation and literal-ack auto-disarm | Synthetic loopback acceptance only; no real pool evidence |
| FIX-004 / I1–I3 / GAP-1 | Existing canonical mining entry point uses its existing Turing scheduler composed with GeodesicScheduler, PhiMemoryHierarchy and partial reads; exact permutation enforced | No `phi_evolve` symbol or dense-state quantum mining is inferred |
| FIX-005 | Existing Hamiltonian MPO now represents declared nonuniform terms, Pauli Y, zero/single-site cases; independent dense differential and Hermiticity tests | Unsupported symmetry/long-range approximation fails closed; general Hamiltonians need not be PSD |
| FIX-007 | Named Yang–Mills module and claimed symmetric-wedge defect absent | A commutator is antisymmetric in its arguments, not generally under matrix transpose; draft test is mathematically invalid for arbitrary matrices |
| FIX-008 | Active `Polychoron600Cell` correctly has 120 vertices | A 120-cell would have 600; changing the existing 600-cell count is not a fix |
| FIX-009 | Corrected 20 icosahedron faces in traversal labels and scheduler evidence | No hardware topology inferred |
| FIX-010 / I2 | Explicit CPU reference route; existing OpenCL/CUDA/Metal tensor adapters retained | Device-bound iGPU mining execution remains unavailable |
| FIX-011 | TS request bytes bound by SHA-256 and checked against Python receipt | No `.pv` artifact producer / requested TS EvidenceRecord in this source path |
| FIX-012 | Cancellation token checked in live CPU search; stale work rejected | No unmeasured 2 ms guarantee or hard real-time claim |
| FIX-013–014 | Existing durable store reused; encrypted execution receipts/replay and mining authorisation/ack journals | No parallel THESEUS implementation or file-existence durability claim |
| FIX-015–016 / GAP-3 | No empty E8/Leech stubs introduced | Research requirements, not implemented production capabilities |
| FIX-017–019 | Property/adversarial/integration tests retained and extended; real local HTTP exercised | No claimed 100% coverage or external pool share acceptance |
| I4 | Existing integrity gate now enforces dtype/finite values without integer overflow; lane reconstruction checked | Tensor tolerance does not replace exact SHA-256d verification |
| I5 | Existing exact PV scale ladder retained and tested | Scalar phi powers do not establish faster convergence or hashrate |
| I6 / GAP-7 | No new semantic authority assigned to healing/intelligence | No actual imported RegenerativeCompute/TOE provider contract verified; research integration remains unverified |
| GAP-2 | Existing software memory hierarchy now enforces configurable tier byte budgets and reports measured residency counters | No fabricated SRAM/HBM capacities, 95% hit rate, 96 GB soak or 4.24× compression claim |
| GAP-4 | Formal source inspected; unresolved placeholders retained as research evidence | `lake` unavailable; univalence statement links arbitrary independent values and cannot be accepted as proven |
| GAP-5–6 | Existing fleet/frontend retained | 1,000-node deployment, 99.99% SLA and new interactive scientific UI are not established by this change |

## Additional release defects fixed

- Replaced custom 192-byte placeholder ML-DSA with cryptography/OpenSSL provider
  support for ML-DSA-44/65/87, public-only verification and explicit key import.
  Legacy placeholder signatures/keys are intentionally incompatible. Provider
  support is not a FIPS module certificate or hardware key-custody claim.
- The attestation evaluator now actually verifies and consumes the separately
  supplied product-gate artifact and binds its profile, revision and run identity.
  Software-base evidence cannot promote sovereign deployment claims.
- The legacy manifest generator no longer produces a public-hardcoded-key HMAC
  or reports unmeasured counters/checks as passing; local diagnostics remain
  NOT_QUALIFIED. The compatibility orchestrator respects an explicit output path
  instead of overwriting a tracked release manifest.
- Corrected a baseline test syntax error, stale expected-failure entries that
  actually passed, the SDK test's double gzip-decoding bridge, recursive wording
  audit discovery, active lint errors and a misplaced SQL-scan suppression on an
  existing whitelist-validated table query.
- Purity scanning still checks exact execution paths; scalar configuration and
  telemetry conversion in the three named throttle/admin modules is explicitly
  distinguished from exact arithmetic. New authority deadlines use nanosecond
  counters; no floating-point target-membership rule was introduced.

## Evidence and deployment

See the PR verification results and the accompanying local evidence packet for
exact commands, raw outputs, artifact hashes and candidate source revision.
Local CPU execution, synthetic protocol tests, source checks, physical-device
execution, CI, deployment and owner admission are separate evidence levels.
See [the candidate runbook](../deploy/execution-authority/README.md) for the exact
service entry point, configuration, API semantics and remaining admission steps.

Unresolved admissions require a named workload/input/output contract, workload
owner, jurisdiction, target backend/host, approved immutable artifact, device
certificate where relevant, security review, anchored immutable audit retention,
backup/recovery and rollback rehearsals, sustained measurements and explicit
owner approval. The uploaded draft's reused GCM nonce, simulated HSM/attestation,
in-memory immutable-log claims and invented fleet measurements were not ported.
