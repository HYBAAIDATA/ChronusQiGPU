# ChronusQiGPU checklist implementation reconciliation

Date: 16 November 2026. Branch: `fix/device-bound-storage-evidence-20261116`. Current base at assignment: `f0e12752ffa272fe171510e02e6e831e4953895e`. Scope: original production checklist and scientific frontier brief supplied on 16 November. The existing canonical code is reused, not replaced.

## Original implementation requests and actual disposition

| Original request | Maintained implementation and new work | Boundary |
| --- | --- | --- |
| Verify source SHA and package reproducible evidence | Existing attested release logic preserved. `scripts/generate_evidence_bundle.py` **new**; input SHA manifest, commit check, immutable ZIP and independent bundle checksum | Collection itself is not a signature or production verdict |
| 11.5× fold/verified-work check | Existing protected PULVINI and real-input benchmark reused. `benchmarks/verify_11_5_claim.py` **new** validates input hashes, correct arithmetic of all retained kernels and tolerance; status remains HELD | Verified useful work requires separate matched measured benchmark; active reduction is not 11.5x throughput |
| Storage latency, throughput, recovery | `benchmarks/qualify_storage_performance.py` **new** for true source-backed app-call timings on selected filesystem, fresh instance readback and current-source SHA, no fabricated values | Physical IOPS, sustained workload and actual power-loss not established |
| Cassini correction | Existing `fibonacci_cassini_witness` exact identity. `chronus.storage.erasure` **new** separate actual bounded XOR erasure correction and SHA-256 checking | No claim Cassini is a correcting code or physical redundancy |
| Prime labels | Existing `chronus.storage.prime_product` bounded reversible label primitive reused | No persistent second-index/physical p-adic mapping |
| True partial unfold | Existing `ExactFoldState.unfold_partial` pair-local reconstruction; PULVINI full kernel-accounted fold separately | PULVINI true local depth unfolding remains unproved |
| Geodesic discovery & metric flow | Reuse exact Fraction SPD metric learner and exact finite problem A/B. New `chronus.research.frontier` integrates bounded witnesses | Does not prove asymptotic logarithmic complexity or full Riemannian flow |
| Golden-angle physical storage | Existing logical coordinates, authoritative durable THESEUS. No device presence asserted | Physical bit placement cannot be implemented/verified from logical mapping alone |
| Exact quantum / stabilizer | TURING packed GF(2) code and tests retained | Mathematical Clifford computation is not a physical QPU or universal advantage |
| Science frontier documentation | `docs/PARADIGM_SHIFT.md` and `docs/CHALLENGE.md` added with falsifiable experiments and explicit limits | No physical results invented |

## Independent executed tests and limits

The new standalone `chronus.storage.erasure` single-erasure algorithm and the deterministic evidence bundler were exercised in an isolated local Python environment on 16 November: **9 positive and negative tests passed** (`test_erasure.py` five, `test_evidence_bundle.py` four). Source-byte inputs used here were explicit non-production correctness fixtures and were not promoted to product-performance evidence. The other maintained integration tests require a complete installed checkout; these modules were reviewed and added to the repository with contract tests but have **not** been independently executed in this environment. No runtime/physical result has been fabricated.

## Authority and acceptance

THESEUS retains durable custody, OVID transformations, Chronus execution, TURING quantum mathematical substrate, EUCLID cognition/orchestration, PYTHIA internal mining, Salamander bounded remediation and AL HARAS security. Research wrappers are *not* alternate runtimes. Protected PULVINI formal source remains unchanged.

Measured hardware energy, IOPS, physical device identity, power-loss fault trials, customer traffic, pool acknowledgement and claimed 11.5× verified-work result are expressly **UNAVAILABLE/UNVERIFIED** until actual source evidence exists. Continue software implementation and independent testing without confusing those external observation classes with code defects.
