# Capability report — experimental and incomplete

**NOT COMPLETE OR RELEASE QUALIFIED.** This report records bounded observations, not a general proof, customer result, security assurance or performance claim. CI is unverified; check-runs access returned 403. All tests below ran locally on partial source exports, not a full checkout.

| Observation | Artifact | SHA-256 |
| --- | --- | --- |
| Substrate: seven focused tests, 49% full-file coverage in this run | [artifact](../evidence/cyclotomic/substrate-coverage.txt) | `46a895c6d3c351c30333fb7dd1a520ceb49a000810cf401f7ab22a0aff4a96f4` |
| RTL: exactness counterexample, simulation fails | [artifact](../evidence/cyclotomic/rtl-overflow-output.txt) | `264fb1581529bac535ba768476808e4756ab0a066ec09f025c4148a594aea68e` |
| Exact MPS: isolated tests, 38/39 statements | [artifact](../evidence/cyclotomic/exact-mps-tests.txt) | `7470ceb546f69e61f37f6a577d7dbc21a591a3fe1e6f1d6882a503915147d7f8` |
| MPS: synthetic product-state comparison depths 1–13 | [artifact](../evidence/cyclotomic/product-mps-comparison.json) | `24878c156f6428f61dd6d699cb43dd5babcd8cf74abe74435cfdd9dc03ad33ed` |
| Prime codec: synthetic access-log measurement | [artifact](../evidence/cyclotomic/prime-codec-synthetic-log.json) | `66217744c41e3f76ad356d6ba11940a086e4a0703589398586fbff1353ba22c4` |
| Zeckendorf reference: accumulation measurement | [artifact](../evidence/cyclotomic/zeckendorf-accumulation.json) | `4f078e73ae868318a2f6a5f5ce30510c02641aa88dc715ee4430bde1e12752f8` |

The listed artifacts were checked by comparing local Git blob IDs with GitHub directory listings at `cb14321021f1f31aadd9a2d9ff73d080b7dcce1b`, and computing the SHA-256 values over those same local bytes. Verify after checkout with `sha256sum` on the listed paths. The report itself cannot contain the hash or SHA of the commit introducing itself; use `git log --diff-filter=A -- capabilities/substrate_report.md`.

## Scope and boundaries

- Substrate: [coverage gate and scope](../evidence/cyclotomic/substrate-blocked.md); [original isolated ring tests](../evidence/cyclotomic/isolation-review.md). Separately, another commit reports [100% branch-inclusive source-file coverage](../evidence/acceleration/ring-test-report.md) in a different isolated suite; neither run establishes a full customer journey, F/R matrices or pentagon identity.
- Hardware: [counterexample and target requirements](../evidence/cyclotomic/rtl-overflow-finding.md). No target-specific timing has been measured. The test intentionally fails on the current RTL.
- Tensor: [prototype test scope](../evidence/cyclotomic/exact-mps-prototype.md), [comparison methodology and commands](../evidence/cyclotomic/product-mps-comparison.md). The ring expansion is unnormalised; the existing floating-point path normalises. The comparison is not a like-for-like timing or equal-task fold-depth advantage. A bounded synthetic product state is not a solved many-body problem or a customer deployment.
- Data: [reference codec measurement](../evidence/cyclotomic/prime-codec-synthetic-log.md) measures a synthetic log class, bit-for-bit round-trip and logical application bytes. The codec expands this class and is not ring-backed. Physical write amplification and failure recovery were not measured; clean reopen is not crash recovery.
- Compute: [reference accumulation measurement](../evidence/cyclotomic/zeckendorf-accumulation.md) is a software Fibonacci-representation comparison at one precision-boundary workload, not a ring-backed or physical ALU demonstration.

## Remaining gates

Full-tree testing and compatibility; seven substantive release test classes and >=90% coverage per requested module; explicit qubit semantics, R/F/pentagon verification; a closed or overflow-aware hardware interface and target-specific timing; equal-task tensor drift/depth/timing; ring-backed storage and ALU integration; representative data, device write amplification and fault recovery; evidence signatures and independent verification; customer-facing materials and review. Unknown or unmeasured results are not assumed successful. For commands and input specifications, follow each linked evidence report.
