# PULVINI/HERMES rolling project implementation closeout

**Repository:** HYBAAIDATA/ChronusQiGPU · **PR:** #138 · **Date:** 16 Nov 2026  
**Scope:** source recovery and bounded execution integration, not production admission.  
**Authority:** CHRONUS execution; PULVINI representations; OVID transformations; THESEUS custody; AL HARAS governance. TURING independent VQC; PYTHIA mining-only intelligence. No authority migration.

## Source inspection and provenance

- 24 July HERMES completion archive: SHA256 `a307f93ed32c1ba97ab6241b44f8789b16b33bab6f603e7bab1f9a0eef923277`, 17 files; `geodesic_tensor_engine.py` SHA256 `e627cd693452904bd1ba1145058a0504955e58d10ce88f0001ed8fdbb4b87525`. Source includes FoldState FMA, matmul, memory hierarchy, scheduler and an `unfold_partial` that **first unfolds full state**. It is a scientific historical record, not current code execution.
- 24 July PULVINI enterprise ZIP: SHA256 `00b79a99c01e88a4e02d458a76c2bea3af1f7cc0c7b1af3be43e0193a8bd038a`, 122 ZIP entries (some directories). Historical `pulvini_enterprise/formal.py` SHA256 `8d14a821b3dd8e8ad66ff380f6a5a40745a64b72eee2dbfa191c1550f9ee8586`, preserved in current `src/chronus/pulvini/formal.py`. The archive contains a standalone SQLite ledger, codec, API, cloud clients, tests and quantum-related modules. Those must not displace the current OVID/THESEUS/CHRONUS/TURING authorities.
- Independently measured UCI public-data ZIP: SHA256 `ae9aba3ac89440de4c59955c2977715f9452ab0505a7c2629c834bd1b8b7cbb1`. Includes SHA-pinned digits (1797×64), wine (178×13) and breast cancer diagnostic (569×30) real observed data. No synthetic inputs were used for public measurement.
- Notion rolling index: `docs/research/PULVINI_HERMES_NOTION_ROLLING_INDEX_20261116.json`. Nine searches identified 225 distinct hits, 112 related pages catalogued. Index is **discovery**, not an assertion all Notion pages/artifacts were downloaded or audited. A July phases 11/13/14 ZIP is found in Notion but is not yet bytes-inspected.

## Implemented and available in PR #138

| Capability | Source | Implementation | Runtime truth |
| --- | --- | --- | --- |
| PULVINI formal operator, preserved exactly | current `formal.py` | no modification | existing CPU-only implementation |
| HERMES FoldState inputs (add/hadamard/scale/FMA-style/matmul/sum) | July HERMES, current tensor core | `src/chronus/tensor/folded_compute.py` | measured isolated source/NumPy reference; no physical GPU |
| Window update | July bounded kernel region | `FoldedTensorExecutor.update_window` | full array reconstructed before update; complete refold; not selective-read savings |
| Complete kernel-preserving fold artifact | July enterprise service/codec; Notion ‘fold never truncate’ | `src/chronus/pulvini/custody.py` | encode/decode tested; canonical `ProductionTriad` restart test committed, not actually executed in current repo |
| True selective φ numerical inverse reads | July HERMES research target | `VerifiedFoldIndex` in `src/chronus/pulvini/partial.py` | one-time full verification + immutable kernel copy; subsequent reads access only requested inverse branches |
| Public observed-data measurement | UCI datasets | `scripts/benchmarks/measure_folded_inverse_public.py` | median measured locally; CPU reference; SHA input checked |
| Regression suites | historical contracts; novel selective inverse | three test files | local isolated equivalents 35/35; integrated CI UNVERIFIED |

## Measured observed data — newly recovered numerical selective inverse

Depth 4; 64 `float64` values, 61 alternating paired samples; one-time compile cost reported separately. Linux x86_64 CPU/NumPy 2.3.5. Not a matched application-level inference baseline.

| Dataset | Compiler/initial full verification | Median selected read | Median full unfold + slice | Effective retained state |
| --- | ---: | ---: | ---: | --- |
| Wine (178×13) | 0.130 ms | 110.142 µs | 92.757 µs | 1.527× original |
| Breast cancer (569×30) | 0.261 ms | 115.841 µs | 223.990 µs | 1.528× original |
| Digits (1797×64) | 20.541 ms | 124.273 µs | 1,111.119 µs | 1.528× original |

**Do not subtract the compile/verification cost, residual storage, tenant custody work, or source loading from real production total cost of ownership.** The row-wise read difference describes a narrow, amortized in-memory microbenchmark, not full GPU acceleration, physical bandwidth, memory compression or energy savings. Negative wine result is preserved. The archived `unfold_partial` did full reconstruction internally; our new index does not after compilation.

Other local measured data: the restored HERMES FoldState addition (including complete source recovery/verification/refold) on wine, 21 samples, median 533.367 µs vs direct NumPy add 1.913 µs; breast cancer, 1,226.941 µs vs 5.158 µs. Relative errors below 1e-15. **These are regressions compared with direct NumPy**, not speedups.

## Notion authority and unresolved integrations

- [Canonical architecture register (5 Oct)](https://app.notion.com/p/3f0bcc6fa49981c68659c178cbb72a19): OVID transformation and THESEUS durable custody. Older inverse descriptions are superseded.
- [PULVINI 23 Jul lab log](https://app.notion.com/p/cef5bd03509e43dcbb399517dfb5a4f9): depth-four active working set 6.85× smaller, but full retained kernels mean net storage expands. New measurements agree.
- [July 24 HERMES completion](https://app.notion.com/p/ffd11e5552144c30ad38a5aaab0b5fcb): 61/61 historical integration operations, 110/110 invariants and 122/122 unit tests; none are promoted to current release checks. Original FoldState-facing operations required restoration.
- [Folding Standard](https://app.notion.com/p/5700504f17b64fdca2e0926196110c47) and [Claims Register](https://app.notion.com/p/42c1ea4eace4410f902e428df5f71ef9): depth, working set, residual/state, original dtype, data class and SHA required for any ratio; no universal storage compression guarantee.
- [Data-first clarifications](https://app.notion.com/p/ee3a4d630691436f9c877496eb7e83fd): preserve closed IP; do not conflate Data evidence with mining or quantum claims.
- [Pilot protocol](https://app.notion.com/p/9c56caf52be040a28f37da830164758e): same workload, named host, full baseline cost and signed attribution required before gain-share.
- [Artifact shelf](https://app.notion.com/p/2539733ebb7848c9a84ae4e3d7429822): also identifies `pulvini_v3_phases_11_13_14_20260724.zip` — **DISCOVERED, BYTES UNAVAILABLE** in this implementation. Its uninspected contents must not be claimed as merged.

### Unclosed gates

1. Current-main/full-branch integration tests and production `ProductionTriad` restart have no GitHub runner success; source-only contract tests cannot replace those.
2. Original HERMES folded-domain accelerator and physical GPU execution: unavailable; restored HERMES-facing API delegates numerical work to NumPy reference.
3. Historical enterprise Hamiltonian/service/TT/MPS/MPO/ledger artifacts require per-capability mapping against existing `src/chronus/tensor`, current Turing/Kellogg boundaries and custody before porting. Not simply copying 19 modules.
4. Actual net memory, cost and energy advantage: unproven, cannot be inferred from active folded channel alone.
5. Physical device, customer authorization, isolation, replay, chaos recovery, deployment and release attestation: unverified; no release promotion.
6. The additional Notion phases ZIP remains not inspected; this registry is broad but not all workspace pages or all bytes.

No protected PULVINI formal source, mining acceptance authority, TURING, or canonical ownership was changed by this PR.