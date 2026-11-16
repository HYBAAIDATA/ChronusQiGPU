# ChronusQiGPU — Notion research reconciliation and storage/fold closeout

Date: 16 November 2026. Baseline main commit: 55ce7bd5ea81b4bb54f2603f5a4a8340bce52a42.
Classification: internal engineering / review branch. No product claim is promoted; no live deployment is implied.

## Source-of-truth research consulted

- [Canonical authority register](https://app.notion.com/p/3f0bcc6fa49981c68659c178cbb72a19) — current subsystem boundaries.
- [Data Folding Standard](https://app.notion.com/p/5700504f17b64fdca2e0926196110c47) — fold power describes active working set.
- [Fold Never Truncate doctrine](https://app.notion.com/p/186f3044516b4abcb70f0b806ee21313) — kernels must be retained.
- [Phi-power test and fix](https://app.notion.com/p/36b8e3d5002d427791863e417addf262) — theory versus measured discrete active channel.
- [23 July structured-data lab](https://app.notion.com/p/cef5bd03509e43dcbb399517dfb5a4f9) — tensor-train flattening defect, no proven net compression.
- [24 July Geodesic and PULVINI V3](https://app.notion.com/p/ffd11e5552144c30ad38a5aaab0b5fcb) — archived numerical tests, not current physical GPU evidence.
- [Phi compression and falsification](https://app.notion.com/p/944d676ba5814d6ea6cc48a8ff105ea0) — invertibility does not establish DFT/codec superiority.
- [Sealed claims register](https://app.notion.com/p/42c1ea4eace4410f902e428df5f71ef9) — claim release constraints.
- [Historic thousand-qubit engineering record](https://app.notion.com/p/4af52dc709194c5ea68e6d08736a9863) — uncompressed tableau, PULVINI checkpoint, validation limits.
- [Benchmark and promotion workflow](https://app.notion.com/p/3f0bcc6fa49981f9a501c3ddbeb65507) — immutable source, comparator, raw data, quality and owner approval.

Research provenance is recorded above; source pages are evidence of prior experiments, not present deployment. The research is not copied wholesale into this repository, and protected PULVINI V3 source code remains untouched.

## Explicit and implicit questions answered

| Question or implied gap | Repository location | Answer / remaining gate |
| --- | --- | --- |
| Is phyllotaxis storage specified or implemented? | src/chronus/storage/phyllotaxis.py; durable.py | Implemented as deterministic **logical** coordinates + SQLite/WAL-backed custody. Physical sunflower-sector placement is **not** implemented. |
| Fibonacci as disk address? F(n-1), F(n), F(n+1) adjacency? | phyllotaxis_coordinate | F64/F66 rational convergent determines logical golden-turn position. No physical Fibonacci offsets or device locality demonstration. |
| Cassini as validation or actual error correction? | fibonacci_cassini_witness; execution/structural.py M15 | Exact identity and reversible determinant. This PR also verifies durable logical coordinates and journals. Neither a determinant nor a SHA digest repairs erased data; genuine ECC remains unimplemented. |
| Prime-indexed physical addressing? p-adic? | prime_codec.py; prime_product.py | Bounded reversible prime-product **secondary label address** now implemented as standalone primitive, distinct from prime-symbol codec. No p-adic/physical allocator and no durable secondary-index integration. |
| Can all valid payloads be recovered? | ovid/transform.py; tensor/folded_state.py; pulvini/interop.py | M15 byte-pair mapping is mathematically invertible and bit exact. PULVINI numerical folding is reversible **within a tolerance** and retains every kernel; it is not globally bit exact. |
| Is 11.5x ratio a depth, throughput or retained-capacity claim? | claims/register.json RS-WORK; docs/IGPU_MANIFESTO.md | Claim **held**; historical wording alone cannot identify a fully measured comparator. Never infer phi^11.5, physical compression, acceleration or net retained bytes. |
| Depth 20 / error 4.053385325984003e-16? | Notion thousand-qubit record; pulvini/formal.py | Historic checkpoint result; reproducibility on exact current SHA requires a fresh run with input and seed. Run controlled reference harness here; no claim promotion from that controlled input. |
| Active versus retained versus serialized size? | scripts/benchmarks/storage_closeout.py | Separate **original/active**, **original/(active + all kernels)** and **original/complete-serialized-bytes**. Record all chronological shape/dtype metadata. |
| Unfold latency and cost? | scripts/benchmarks/storage_closeout.py | Times fold and full reconstruction as separate operations on the current runner; report workload, source SHA, numeric tolerance and environment. No unobserved timings supplied. |
| IOPS and NVMe vs SSD? | scripts/benchmarks/storage_closeout.py | Application SQLite WAL call latency with p50/p95/p99; block device IOPS, direct NVMe/SSD comparison, cold cache and sustained throughput remain **unavailable**. |
| Durability, corruption, crash and power-loss recovery? | storage/durable.py; tests/test_triad_production.py; tests/test_storage_research_closeout.py | Fresh-service reopen, WAL FULL, digest and journal checks, concurrency, and new coordinate-tamper rejection. No physical power-loss or disaster-recovery test. |
| Independent storage verification? | CI artifact to be produced by workflow | Repository/runner-local evidence only until a separate target-device and reviewer attestation exists. |
| Thousand-qubit machine and tableau memory? | packages/turing/src/turing/algorithms/clifford.py and tests | CURRENT packed representation: 2n(2n+1) **bits**, 4,002,000 bits at n=1000. HISTORIC Notion tableau: 4,002,000 **bytes**. Do not conflate implementations. |
| GHZ evidence discriminating or 32-coin-flip? | packages/turing/tests/test_turing_clifford.py | Current test validates stabilizer rank, global X, local ZZ, support and both measurement-collapse branches; not just sampled correlations. Still classical exact Clifford evaluation, not experimental entanglement. |
| T and Shor? | packages/turing/src/turing/algorithms/shor.py; cpp/src/quantum_superposition.cpp | Separate exact small-input Shor distribution and finite-field T-labelled path exist; neither proves scalable non-Clifford complex-Hilbert execution or quantum advantage. |

## Implemented review-branch changes

1. Exact Cassini integer witness, explicit scope: proof/check only, not error correction.
2. THESEUS fail-closed verification of stored Fibonacci/golden-angle coordinate, lane, record size and journal geometry on reopen and retrieval. Source and metadata are checked against the original content-address inputs; changing the lane-count configuration intentionally fails closed.
3. Bounded reversible prime-product encoding of unique label sets with invalid-factor rejection. No unauthorised migration of authoritative storage, no physical-disk claims.
4. Adversarial tests for angle/lane/journal tampering, Cassini validity, prime-product invalid inputs and healthy restart.
5. Reproducible controlled reference harness emitting raw observed application-call latency, complete PULVINI kernel and serialized-state accounting, fold/unfold timing, source SHA and explicit unavailable fields.
6. CI workflow to run the tests and upload fresh current-commit reference output.

## Acceptance gates that cannot be closed by repository work alone

- P0: Green mandatory CI for proposed PR/head SHA, and owner approval of a review-only merge; previous main failed multiple CI workflows.
- P0: Enforced branch ruleset/CODEOWNERS for protected PULVINI and release-critical paths. A digest check or AGENTS instructions without ruleset enforcement is insufficient.
- P1: Actual 11.5x **verified work** experiment: fixed task, named data class, baseline and equal correctness; include index/preparation, full retention, serialization, reconstruction, and cold/warm controls. Claim remains held until owner-approved promotion.
- P1: Hardware-bound device identity and independent NVMe/SSD latency/IOPS, throughput, raw counters, sustained-load and crash/power-loss evidence. CI runners are not a substitute.
- P1: For true Cassini-associated correction, specify fault model and introduce actual redundancy/parity plus a recovery algorithm, then run corrupt/erase fault injection; current identity is detection, not ECC.
- P1: Durable prime secondary-index integration only after tenant, query, collision, security, migration and performance contracts are approved.
- P1: PULVINI tensor-train axis-aware or TT-core-first research requires a separately tested owner-authorized change. Do not silently modify protected formal.py.
- P2: TURING Clifford and exact cyclotomic algorithm classifications must remain separate from hardware/universal computation claims.

## Ownership, release and evidence posture

Chronus executes; TURING supplies the independent exact mathematical VQC substrate; OVID owns transformation contracts/materialisation; THESEUS owns durable custody and replay in the current production triad; EUCLID orchestrates; PYTHIA remains internal mining/prediction; Salamander heals only through bounded, authorised remediation; AL HARAS governs access and security. Historical Notion mining-only proposals with different custody authority were not used to silently change the current triad.

**Verdict:** This change is implementation plus falsifiable source/test instrumentation, not proof of physical storage placement, independent system qualification, an 11.5x economic benefit, full quantum universality or production-readiness. Do not merge on narrative.
