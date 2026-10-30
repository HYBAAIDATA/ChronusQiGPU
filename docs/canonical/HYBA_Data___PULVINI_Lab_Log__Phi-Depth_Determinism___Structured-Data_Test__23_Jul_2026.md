# HYBA Data — PULVINI Lab Log: Phi-Depth Determinism & Structured-Data Test (23 Jul 2026)

Company: HYBA Data · Parent: HYBA Software Ltd

Scope: First real-code verification of PULVINI's `src/euclid/pythagoras/quantum/` implementation (landed 23 Jul 2026), testing (1) whether fold depth scaling is deterministically tied to φ and its powers, and (2) whether TT compression differentiates structured vs. random data as claimed.

## Method

- Code under test: `PulviniOperator.fold_recursive` / `unfold_recursive` (`pulvini_scaling.py`), `TTPulviniHybrid` (`tensor_train.py`).
- Environment: no network access in this sandbox, so scipy/pytest could not be installed. A numpy-backed shim was substituted for the single scipy call used (`scipy.linalg.svd` → `numpy.linalg.svd`, same underlying LAPACK routine for dense arrays — not a functional difference).
- Script: `tests/euclid_dominance/lab_test_phi_depth_and_structured_data.py`
- Raw output: `LAB_TEST_PHI_DEPTH_RESULTS.json`

## Section 1 — φ-power depth determinism (dim = 10,648 vector)

| depth | folded size | visible ratio (dim/folded) | φ^depth | match | real net ratio (dim / (folded+kernels)) | roundtrip error |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 6,581 | 1.6180 | 1.6180 | yes | 0.8090 | 1.71e-18 |
| 2 | 4,067 | 2.6181 | 2.6180 | yes | 0.7236 | 2.53e-18 |
| 3 | 2,514 | 4.2355 | 4.2361 | yes | 0.6793 | 3.09e-18 |
| 4 | 1,554 | 6.8520 | 6.8541 | yes | 0.6545 | 3.47e-18 |
| 5 | 960 | 11.0917 | 11.0902 | yes | 0.6401 | 3.69e-18 |
| 6 | 593 | 17.9562 | 17.9443 | yes | 0.6315 | 3.86e-18 |
| 7 | 366 | 29.0929 | 29.0344 | yes | 0.6263 | 4.00e-18 |
| 8 | 226 | 47.1150 | 46.9787 | yes | 0.6232 | 4.05e-18 |

**Finding 1 (confirmed, real, deterministic):** the folded_tensor's size shrinks exactly as φ^depth — matching to within Fibonacci-integer-rounding noise (<0.4%) at every depth tested. This is a genuine, reproducible, deterministic property of the code — the claim that this is tied to the golden ratio and its powers holds for this quantity.

**Finding 2 (open engineering gap, not yet a compression win):** that φ^depth growth describes only the folded half of the data. Exact lossless reconstruction also requires storing the `projection_kernel` at every fold level. Once those are counted, real net storage ratio is below 1.0 at every depth tested and gets worse — not better — as depth increases: 0.809 at depth 1, sliding to 0.623 at depth 8. As currently coded, deeper φ-folding does not produce more real lossless compression; it produces less. Roundtrip reconstruction itself remains essentially exact (~1e-18) at every depth — this is a storage-accounting finding, not a correctness bug.

## Section 2 — Structured vs. random data (256×256 tensors, TT+PULVINI hybrid)

| data class | reconstruction error | reported TT ratio | real net ratio | orig floats | real stored floats |
| --- | --- | --- | --- | --- | --- |
| random (full rank) | 4.93e-19 | 1.000 | 0.809 | 65,536 | 81,007 |
| low-rank (r=3) | 6.27e-19 | 1.000 | 0.809 | 65,536 | 81,007 |
| low-rank (r=8) | 2.00e-18 | 1.000 | 0.809 | 65,536 | 81,007 |
| smooth sinusoidal | 2.61e-19 | 1.000 | 0.809 | 65,536 | 81,007 |

**Finding 3 (root cause identified):** all four data classes — including two deliberately low-rank matrices and a smooth structured signal — produced bit-identical ratios. Root cause: `TTPulviniHybrid.process()` reshapes the folded data to a column vector (`.reshape(-1, 1)`) before running Tensor-Train decomposition. That reshape discards the original tensor's multi-dimensional shape, which is the only thing TT decomposition can use to detect and exploit low-rank/structured correlations. As wired today, the TT stage cannot realize any structure-dependent compression gain, on any data class. Fix path: reshape the folded data back into its original (or a deliberately chosen multi-axis) shape before calling `TensorTrain(...)`, not into `(-1, 1)`.

## Verdict / claim lanes

- φ^depth determinism of folded-tensor size: **SEALED** (real, reproducible, machine-verified, deterministic).
- Net lossless compression via fold+kernel at any tested depth: **INTERNAL / not yet achieved** — do not state as an external compression ratio through this code path.
- 85.6% / 6.85× data-sheet figures: **unchanged provenance** — sourced from the M1 seal/harness, not reproduced by this fold/unfold code today. Needs its own dedicated re-test against this exact implementation before the two are equated.
- TT structure exploitation: **BLOCKED** (known root cause, fix identified, not yet applied).

## Round 2 (same day, post-fix re-test) — reshape bug fixed, deeper root cause found

Per Lab Protocol Rule 7 (re-test before re-stating), the TT reshape bug flagged in Finding 3 above was fixed and re-tested before writing anything further.

**Change made:** `TTPulviniHybrid.process()` no longer reshapes the folded array to `(-1, 1)`. It now reshapes into a real balanced 2D shape via a new `_pad_to_factorable()` helper (pads by at most 5% when needed so the length has a non-trivial factor pair), and truncates the reconstruction back to the exact original length afterward.

**Regression check:** `manual_verify_pulvini.py` still passes the same 33/38 checks after the fix — no new failures, roundtrip/Hamiltonian/MPO results unchanged.

**Honest result — the fix did not solve the problem.** Re-running Section 2 (random / low-rank r=3 / low-rank r=8 / smooth-sinusoidal, 256×256) after the fix:

| data class | recon error | reported TT ratio | real net ratio | stored floats |
| --- | --- | --- | --- | --- |
| random (full rank) | 7.29e-18 | 0.895 | 0.764 | 85,767 |
| low-rank (r=3) | 1.27e-17 | 0.895 | 0.764 | 85,767 |
| low-rank (r=8) | 2.05e-17 | 0.895 | 0.764 | 85,767 |
| smooth sinusoidal | 2.23e-18 | 0.895 | 0.764 | 85,767 |

Still bit-identical across all four data classes. Real net ratio is now slightly *worse* than before the fix (0.764 vs 0.809), because the padding needed for a real 2D shape adds a small real storage cost on top of a problem the fix didn't solve.

**Root cause, now correctly localized:** the problem is not in TT or in the reshape — it's upstream in `PulviniOperator.fold()`. `fold()` splits the tensor's **flattened 1D array** at a Fibonacci-proportional index computed from total length, not from the tensor's real axis boundaries. For a 256×256 input (65,536 elements) that split lands at index 40,497 — not a multiple of 256 — so it cuts through the middle of a row. The two halves `fold()` then blends elementwise are misaligned relative to the tensor's rows/columns, which scrambles row/column-correlated (low-rank) structure *before* it ever reaches TT. No reshape downstream of `fold()` can recover structure that `fold()` already destroyed.

**Fix path identified, not yet built (needs a design decision):** either (a) make the Fibonacci split axis-aware (split per-row/per-axis instead of on the flattened array), or (b) run TT decomposition before PULVINI folding and fold the resulting TT cores instead of the raw flattened tensor. Both are real, testable, and neither is claimed as working until it's written and re-verified.

**Updated verdict / claim lanes:**

- TT-stage rank-1 collapse bug (reshape to `(-1,1)`): **FIXED AND VERIFIED**.
- TT structure-dependent compression: **STILL NOT ACHIEVED** — root cause now correctly localized to `fold()`'s axis-unaware split, not TT. Open item, explicitly tracked, not dropped.
- φ^depth determinism (Section 1): **unaffected, still SEALED** — this round did not touch the core `fold_recursive` split logic, only `TTPulviniHybrid`'s downstream reshape.

## Round 3 (same day) — canonical `pulvini/` package created, and a note on an unverifiable external report

**1. Canonical package (per user request "give it a home"):** Created `pulvini/folding_engine/` and `pulvini/codecs/pulvini_byte_compression.py`, matching the target namespace already named in `reorganize_product_boundaries.py` (a real migration script in the repo). The real, tested code from `src/euclid/pythagoras/quantum/{operators,topology}/` now lives at this canonical path with relative imports fixed. The pre-existing `al_haras/pulvini_byte_compression.py` compatibility shim — previously dangling (`ModuleNotFoundError: No module named 'pulvini'`) — now resolves for real, verified via a byte-string compress/decompress roundtrip through the shim itself. Regression check: `manual_verify_pulvini.py` unchanged at 33/38 PASS; `lab_test_phi_depth_and_structured_data.py` unchanged (Section 1 SEALED, Section 2 still bit-identical, real_net_ratio 0.764). No source found anywhere (local disk or GitHub search of both connected repos) for the plan's other named sources (`phi_sdk`, `hyba_inference_memory_layer`, `src/pulvini` runtime, `pulvini_tier2`) — those remain open gaps, not silently completed.

**2. A genuine find, and a claim I cannot verify here.** A workspace search this round confirmed the "PHI-1 OS Design Document (v1.0)" page is real and pre-existing in this Notion workspace — that part of a pasted external report was correct, and an earlier answer in this thread should have surfaced it sooner. However, that same pasted report (signed "DeepSeek-V4", describing work on a file called `HYBA_DATA_FORMATTED_PRODUCTION_FINAL.zip` with a `python_backend/hyba_data/` + `python_backend/phi_folding_engine/` tree — `phi1_os.py`, `cf_tower_iir.py`, `hyperbolic_nd.py`, `holograph_*.py`, `zphi_exact.py`, `unitary_gpu.py` — plus claims of "20/20 PASS" and a page citation this system never issued) describes a different package, in a different tool session, that is not accessible from here. Local disk (`Midas_Data_Euclid-main.zip` as uploaded to this thread) and GitHub search of both connected repos turned up **no** `python_backend/` directory at all. Per Lab Protocol Rule 1, those specific pass/fail claims are recorded here as **unverified in this environment**, not as confirmed or as false — if that zip or its `HYBA_DATA_RESIDUAL_CLOSURE_DELTA.zip` patch is uploaded to this thread, the same tests can be run here for real.

## Artifacts

- `src/euclid/pythagoras/quantum/operators/pulvini_scaling.py`
- `src/euclid/pythagoras/quantum/operators/tensor_train.py`
- `src/euclid/pythagoras/quantum/operators/matrix_product_operator.py`
- `src/euclid/pythagoras/quantum/topology/orchestrator.py`
- `pulvini/folding_engine/` (pulvini_scaling.py, tensor_train.py, matrix_product_operator.py, orchestrator.py) — new canonical home
- `pulvini/codecs/pulvini_byte_compression.py` — new canonical codec, backing the `al_haras/` shim
- `tests/euclid_dominance/test_pulvini_tensor_networks.py`
- `tests/euclid_dominance/manual_verify_pulvini.py` (33/38 real checks passed)
- `tests/euclid_dominance/lab_test_phi_depth_and_structured_data.py`
- `LAB_TEST_PHI_DEPTH_RESULTS.json`