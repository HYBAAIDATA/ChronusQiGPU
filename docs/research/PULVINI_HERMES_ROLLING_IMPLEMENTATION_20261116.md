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

---

## Additional rolling artifacts recovered and cross-checked — 16 November 2026

The November **owner handoff**, discovered in the user's ChatGPT Library rather
than assumed absent, was opened and SHA-256 verified:

- `HYBA_PULVINI_V3_OWNER_RESEARCH_HANDOFF_20261115.zip` SHA-256:
  `561d0b9cec7aa4ae80117f9267f44abc53328ecfe46445c51123261e846032cc`.
- Its protected formal, interop, package `__init__`, research-lock test,
  source lock verifier, and research guard workflow have **exact Git blob IDs
  equal to main**. They were already integrated; this PR does **not** overwrite
  or duplicate those paths.
- The handoff's `OWNER_CLOSEOUT.md` cites [PR #97](https://github.com/HYBAAIDATA/ChronusQiGPU/pull/97)
  and [issue #98](https://github.com/HYBAAIDATA/ChronusQiGPU/issues/98):
  earlier research seams were not the full enterprise migration. CODEOWNERS
  and a source SHA guard alone do not constitute immutable branch rulesets.

Additional source fingerprints:
- July Geodesic extended ZIP: SHA-256
  `43d4d3a39fd13fb525bf3acf0b822af1ef55c6b801616aeb9bf326a76dcfa44b`;
  3 original source/test files; archived tests 115/115, **historical**.
- Chronos iGPU v3.10 resident-projection ZIP: SHA-256
  `33f807d0a12e9b7f72f7a84c29258974dad0db70031c011db5fbc7251601b428`;
  357 entries including older tensor and execution evidence. This is a
  separately dated lineage, not automatically modern ChronusQiGPU main.
- The Notion [Artifact Repository](https://app.notion.com/p/2539733ebb7848c9a84ae4e3d7429822)
  includes `pulvini_v3_phases_11_13_14_20260724.zip`: reference and signed
  source location resolved, **original bytes not inspected**, no merge asserted.

## Further code elevation now in PR #138

- `src/chronus/pulvini/operator_calculus.py` reintroduces bounded full-state
  fold matrices, induced metric, condition certificates, linear operator lift
  and action verification from the 24 July Enterprise `operator_calculus.py`,
  delegating to the locked original `PhiRecursiveOperator`. It rejects
  nonrepresentable integer inputs and nonfinite/overflowed lifts.
- `src/chronus/pulvini/linear_arithmetic.py` performs genuine linear
  combinations on **both the folded and retained-kernel channels**. It does
  not reimplement the formal fold. Every input is verified before use and the
  result is checked against a separately evaluated NumPy reference. **This is
  CPU/NumPy reference folded-channel arithmetic, not a GPU or cost advantage.**
- `FoldedTensorExecutor.execute_folded_linear` exposes the new route without
  replacing old array-dispatch semantics. The complete state remains retained.
- Precision regression: NumPy 2.3 can classify int64→float64 as a safe dtype
  cast even when individual values above 2**53 lose bits. The new update path
  checks each converted value by round-trip to its original dtype, and lift
  preflights numeric representability.
- Custody provenance: the source SHA embedded in a reconstructible fold is
  **unsigned operator-declared metadata**, not independent source attestation.
  Both encoded artifacts and decoded operands now expose the unverified status.

The locally reconstructed equivalent modules, including new calculus and
linear operation tests, passed **71/71 isolated tests**. This is not a
complete exact-current-repository CI pass or a live THESEUS restart certificate.

### Second real-public-data measurement (same algorithms; different local run)

The same SHA-pinned UCI observed arrays were rerun on the isolated CPU worker,
using a 64-element selected read, 61 alternating measurements and depth 4.
Index compilation/full verification is recorded separately.

| Dataset | Index compile | Selected median | Full reconstruction + slice | Complete retained/original |
| --- | ---: | ---: | ---: | ---: |
| UCI wine | 0.232 ms | 113.287 µs | 97.684 µs | 1.527× |
| UCI breast-cancer | 0.356 ms | 161.108 µs | 258.752 µs | 1.528× |
| UCI digits | 1.254 ms | 119.186 µs | 1,095.766 µs | 1.528× |

The wine regression is retained. No general performance superiority is
claimed, and index construction, input validation, full retained kernels,
storage and custody are part of true total cost. Timings are single-host
microbenchmarks and must not be presented as hardware performance evidence.

## Historical Enterprise V3 module-to-authority reconciliation

These 19 historical package files and their present disposition have been
compared. `REQUIRES CONTRACT MATCH` is not an assertion that modern code
lacks all corresponding functionality.

| July module | Modern owner / relevant area | Disposition this PR |
| --- | --- | --- |
| `formal.py` | PULVINI | SHA-identical protected implementation; preserved |
| `operator_calculus.py` | PULVINI | Bounded full-state matrix/action subset implemented and tested |
| `ledger.py` | THESEUS | Do not install competing ledger; canonical Triad custody adapter implemented |
| `service.py` | CHRONUS service + OVID | Complete-fold codec adapter implemented; historical API not yet mapped |
| `backends.py` | CHRONUS tensor hardware | REQUIRES CONTRACT MATCH; no physical device measurement |
| `neural.py` | CHRONUS tensor / optional PyTorch | REQUIRES CONTRACT MATCH to folded inference and adjoint gradient |
| `cloud.py` | CHRONUS service | REQUIRES CONTRACT MATCH to deployed connectors and IAM |
| `api.py` | CHRONUS service | REQUIRES CONTRACT MATCH to existing routers, not duplicate API |
| `verifier.py` | PULVINI / AL HARAS evidence | Receipt/reconstruction checks implemented; attestation unverified |
| `gap_closure.py` | CHRONUS tensor / TURING | REQUIRES CONTRACT MATCH to exact MPS/MPO/TT paths |
| `formal_contracts.py` | PULVINI | Current source-lock tests + matrix calculus, not entire old suite |
| `reproducibility.py` | CHRONUS benchmarks/Theseus | Local proof provenance added; CI/deployment unverified |
| `quantum_formalism.py` | TURING independent VQC | Historical only, **do not** import into Chronus quantum identity |
| `benchmarking.py` | CHRONUS evaluation | Real UCI benchmarks, no old numerical claim promotion |
| `regenerative.py` | SALAMANDER | Historical reference; **do not** steal self-healing authority |
| `pulvini_objects.py` | PULVINI representation | REQUIRES CONTRACT MATCH for remaining object-level semantics |
| `extended_benchmarks.py` | CHRONUS evaluation | Public-data slices measured, not complete archival coverage |
| `hamiltonian.py` | CHRONUS tensor / TURING scope | REQUIRES CONTRACT MATCH to modern Hamiltonian implementation |
| `__init__.py` | PULVINI | Protected existing interface preserved |

**Scope boundary:** The table records actual ported components and explicit
unmapped contracts. It does not declare the remaining enterprise components
done, does not assume a 357-file historic archive should overwrite modern
source, and does not convert local tests into production qualification.


### Additional Library provenance and later Notion cross-reference

Three further uploaded Library bundles were examined, not blindly imported:

| Archive SHA-256 | Contents and disposition |
| --- | --- |
| `5816687967f6f07ae489086936b56dd709160b59424fea57a80b286039f78add` — `hyba_data.zip` | 38 entries, chiefly old M32 manifold/oracle/search and deployment YAML; historical Geodesic/CHRONUS lineage, not replacement for current PULVINI formal fold |
| `5194a4be8ca6fd7a46eaa30299969d261cca530bd75a3dd5271ea9785fc93460` — `pulvini.zip` | 14 entries, old M32 search/manifold names; a different provenance family from July protected Enterprise V3 numerical folding |
| `94d267ee63c0136ed14282d4a3bc402de065bb3ad495c55599649bf7d48cf069` — `enterprise-triad-release-gates.zip` | 21 entries, historical Aethel enterprise custody/release gate contracts; compare against existing OVID/THESEUS/AL HARAS gates, do not install a duplicate custody authority |

Further Notion records read and reconciled:

- [HYBA DATA Code Elevation Pack](https://app.notion.com/p/080cf1c058b14a8692d9431695ed928f):
  historic data-class gate, claim withholding and unmeasured-fee zero policy.
- [HYBA Data Pilot Measurement Protocol](https://app.notion.com/p/9c56caf52be040a28f37da830164758e):
  requires named production(-like) deployment, matched baseline, observed
  compute/memory costs, signed customer measurement and agreed gain-share.
- [HYBA Data Capabilities (Evidence-Tiered)](https://app.notion.com/p/31c54504aec9464eab78699130b7e654):
  historic M1/M2/M3 evidence-class separation; a physical GPU or customer
  capacity multiplier cannot be derived from φ-depth alone.
- [Independent Verification (2 Aug)](https://app.notion.com/p/17a3c7e9be7540ffaf1082d87f680b3b):
  historically falsified several repository claims; do not promote paper
  ratios without same-implementation measured effective results.
- [Integrated Deployment Package](https://app.notion.com/p/0f9aedc5b415479cb34a9b1646f006b4):
  references `HYBA_DATA_WITH_AUTH.zip` and
  `HYBA_TESTIMONY_WITH_AUTH.zip`; original attached bytes have not been
  recovered into this code checkout. Their integration is **UNVERIFIED**.
- [Artifact Store](https://app.notion.com/p/a14577d2b8c64735b0344bdcf9c80c38):
  lists `HYBA_DATA_ENTERPRISE_BENCHMARKS_P8.zip`,
  `HYBA_DATA_ENTERPRISE_TRIAL.zip` and additional historical products.
  These pointers are not proof of deployment on the present release SHA.

Latest adversarial fixes on this PR: checked exact replacement value
round-trips (rather than NumPy's permissive int64→float64 dtype label),
explicit last-fold-extent checks, oversized matrix-result preflight,
unsupported rank rejection before custody, unsigned-source origin labelling,
integer lifting overflow/nonfinite protection, nonnumeric matrix rejection,
direct folded-channel arithmetic with every residual kernel, plus durable
POSIX evidence publication. The recorded **71/71 isolated locally
reconstructed-source tests** exclude the real production Triad integration
and do not represent GitHub CI.
