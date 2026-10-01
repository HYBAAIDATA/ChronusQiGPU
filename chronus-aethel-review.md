# GPU implementation + aethel review — PYTHIPhiMiner

Review of the GPU path (`chronus/`, `mining/`, `Intelligence/unified_punch.py`, `mla1517` GPU surface), the `aethel` package, and the attached bridge-spec message. No code was changed; findings only. Environment note: this box has no pyopencl/OpenCL device, so all OpenCL paths were exercised through their documented CPU fallbacks; 149 GPU/aethel-scoped tests pass, 7 skip cleanly on missing pyopencl/device.

## Verdict

The GPU stack is unusually honest engineering: `last_dispatch_backend` names what actually ran, unsupported punch opcodes fail closed rather than fabricating, device-reported SHA-256d hits are re-verified with hashlib, the hasher self-checks its kernel at init, and the report surfaces explicitly separate *physical GPU availability* from the *logical substrate* (`theorem_proven: False`, `CLAIM_BOUNDARY`, MEASURED/DECLARED/UNVERIFIED labelling in `aethel/CONTRACT.md`). Three real defects found, plus a tautological gate and assorted dead code.

## Findings (ordered)

### 1. MEDIUM — `chronus/engine.py`: resident buffers silently wrong on non-fp64 devices
`_ResidentBase._build_options()` compiles the cgemv kernels with `acc_t = float` when the device lacks `cl_khr_fp64` (`chronus/engine.py:112-115,557-558`), but `_as_square`/`_as_vector` always cast host arrays to `np.float64` and every buffer is sized `dim*8` (`:521-531,586-588,637-640`). On an fp32-only device the kernel reads the buffers as `float*` — every element count doubles and the reads land mid-double — and `y` is written as `float*` into a 8-byte-per-element buffer whose readback is `float64`. Silent garbage on exactly the iGPU class this targets. Also `_CL_SOURCE` never emits `#pragma OPENCL EXTENSION cl_khr_fp64 : enable`, so the fp64 build can itself fail on drivers requiring the pragma. Fix: cast arrays to float32 and size buffers `*4` when `uses_fp64` is False — or fail closed.

### 2. MEDIUM — `aethel/gpu.py`: `project_and_collapse_pv` crashes against `OpenClPunchHost`
It dispatches punch 0x15 unconditionally whenever `gpu_active and pv_base == PHI` (`aethel/gpu.py:54-61`), but `OpenClPunchHost.SUPPORTED_PUNCHES = (0x02, 0x1C)` and raises `PunchUnsupported` for 0x15 (`chronus/opencl_host.py:366-381`). Verified live: `PunchUnsupported: punch opcode 0x15 has no reference implementation`. `aethel/punch.py` explicitly selects `OpenClPunchHost` as its last-resort resolution and returns it regardless of `use_opencl`, so a deployment where `toe.unified_punch`/`Intelligence.unified_punch` can't import hits a hard crash on the ingest path instead of the documented "identical NumPy computation" fallback. Fix: catch `PunchUnsupported` (or probe a supported-opcode set) and run the CPU path.

### 3. MEDIUM — `aethel/manifold.py`: `GeodesicNavigator` hop budget is cumulative, never reset
`self.hop_count` is created once in `__init__` and never reset (`aethel/manifold.py:169-184`); `max_hops = 1000` inside `query()` is therefore a *lifetime* budget, not a per-query bound. Verified: payload ingested at anchor 66 returns correctly on first query (8 hops); after `hop_count` reaches 1000 the same query cannot leave the root node and returns `None`. Every long-lived manifold degrades to un-queryable. Fix: `self.hop_count = 0` at the top of `query()` (or make it a local).

### 4. LOW — `CassiniVerifier.verify(n)` is a tautology, presented as a gate
`verify()` recomputes `L_n² − 5F_n²` from its own `lucas()`/`fibonacci()` and compares to `4(−1)ⁿ` (`aethel/cassini.py:33-39`) — an identity that holds for every n (verified n∈[0,200)). Consequences: `manifold.py:373` `"Cassini validation failed"` is unreachable; `SelfHealingSubstrate._find_nearest_valid` (`manifold.py:158-163`) always accepts the first candidate it probes, making the "nearest *valid*" framing cosmetic. Contrast: `aethel/storage.py`'s `cassini_holds(entry.quadruple)` is a *real* gate — it verifies stored values that can actually be corrupted. The useful forms here are `verify_with_values`/`verify_matrix`; `verify(n)` should be renamed or used only on untrusted values.

### 5. LOW — dead/unreachable code
- `aethel/punch.py:65-67`: `if getattr(host, "use_opencl", False): return host` / `return host` — identical branches.
- `aethel/manifold.py:373-374`: unreachable `raise RuntimeError("Cassini validation failed")` per finding 4.
- `aethel/zeckendorf.py:214-216`: `encode(n)` never raises for any uint64 (max < F94), so the `encode_7byte_chunk` fallback is dead.
- `chronus/kernels/unified_punch_kernel.cl`: quantum punches 0x12–0x14 are implemented (classically simulated) but absent from the host's `PUNCH_IDS`, so unreachable.
- `chronus/seam/kernel.py:177`: non-sha256 kernels return `digest_of(kernel.value)[:16]` — a placeholder output, not a computation (structured honestly, but callers should not read it as a result).

### 6. INFO — float32/float64 anchor divergence between backends
The GPU path computes `norm_sq` in float32 (kernel `phi_weight`, matched bit-for-bit by `UnifiedPunchHost._norm_sq_f32`); the CPU path in `aethel/gpu.py:67-68` and `manifold._project_to_pv_lattice` uses Python float64. Near rounding boundaries the two backends can produce different anchors for the same input — `stage_evidence` records which ran (honest), but anchors are not bit-reproducible across backends.

### 7. INFO — naming vs physics
`ChronusContext`, `VirtualSM`, `SPMDExecutor`, `RTCoreMicroKernel` are ThreadPoolExecutor-based virtual machines — the "GPU" is a logical substrate. Consistent with the logical/physical split from PR #1 and reported honestly via `gpu_active`/`projection_backend`, but worth keeping in mind when reading "GPU execution required" error strings. `aethel/device.py` also silently ignores `require_gpu` in nested mode (`require_gpu and mode == "standalone"`).

## aethel package — strengths

- `fibonacci.py` is genuinely rigorous: fast doubling plus an exact Q(√5) Binet cross-check — a real two-algorithm verification, not a tautology.
- `storage.py` `CassiniLedger` is a real integrity gate: monotonic per-writer index, Fibonacci index↔value binding, quadruple checks on *stored* data, gap detection before reads. `CONTRACT.md` correctly scopes it as address-stream (not payload) integrity; payload integrity is per-entry SHA-256.
- `encoding.py`/`zeckendorf.py`: lossless fold/unfold, `MAX_FOLD_LEN` fails closed, stored masks verified non-adjacent.
- `shm.py`: faithful seqlock ABI v1 port — magic/version/slot-count verified, `attach()` fails closed with `SegmentMissing`, torn records never surfaced.
- `manifold.py`: digest-pinned reads with exactly one verified self-heal attempt, then `None` rather than corrupt bytes; `stage_evidence` records the physical backend per stage.
- `geodesic.py`: real adapter — `retrieve()` requires the position to appear in the engine's own coverage order; it reuses engine invariants instead of reimplementing them.
- `primes.py`: works correctly for round-trips, but the "Galois-field composite key" is storage dressing — `_encode` is just 7-byte chunking and the composite is only a dict bucket key; no security or compression properties follow from the primes.
- Test suite: 149 pass / 7 clean skips for missing pyopencl — consistent with the strict-hardware-gate rule.

## Ancillary message assessment (bridge spec, `pasted-1790662208461.txt`)

It is a *prior session's proposal document* for a golden↔Fourier "bridge" layer plus governance configuration — well-structured (EXACT/BOUNDED_RESIDUAL/APPROXIMATE/REJECT modes, residual accounting, refusal recording, lineage, per-profile policies, a test suite, an honest blockers list).

- **For this repo it is ~85% aspirational API names.** Verified by search: `Rational5`, `GoldenValue`, `FourierValue`, `proof.certify`, `verify_proof`, `guardian`, `witness`, `services.core.lineage`, `ResultEnvelopeV2`, `PROFILE_DEFAULTS`, `best_rational5_approx`, `is_golden_grid_compatible`, `governance/roles.yaml`, `scripts/configure_protected_environments.py`, `PROMOTION_SIGNING_KEY` — none exist here. The doc itself says the primitives "already exist… on your side" — i.e. the other codebase it was written for.
- **Closest in-repo substrates** if the bridge were ported here: `kellogg/exact_tensor.py` `Qsqrt2`/`F4` (exact Q(√2)+iQ(√2) over `Fraction` — same shape as `Rational5`/`GoldenValue` but √2, not √5); `aethel/fibonacci._phi_power_exact` (exact Q(√5) powers, internal); `chronus/seam/types.attest` (≈ proof links); `aethel/storage.CassiniLedger` (append-only verified log ≈ lineage); `chronus.seam` `Result`/`Err` (≈ `BridgeResult`/`BridgeRefused`); `chronus.mla1517.store.PrimeDB` exists but has `put()`, not `register_type`/`register_index`.
- **Internal logic bug in the spec itself:** `golden_to_fourier.can_bridge_exact` checks `is_rational` on `Rational5`'s a/b components, which are `Fraction`s by construction — always true → `BOUNDED_RESIDUAL` unreachable, `encode_bounded` dead code (it calls `encode_exact` which asserts exactness). Its own test vector `g2f_sqrt5_bounded` expects `BOUNDED_RESIDUAL`, contradicting the spec's control flow.
- §79 governance items are admin-side pseudocode (roles, protected environments, signing key, runner labels) — nothing to implement in code; actionable only by repo admins.

## Suggested priority

1. Fix `chronus/engine.py` resident-buffer dtype (cast to float32 or fail closed) — silent wrong results on the target iGPU class.
2. Catch `PunchUnsupported` in `project_and_collapse_pv` (or probe supported opcodes) — hard crash on the fallback host path.
3. Reset `GeodesicNavigator.hop_count` per query — cumulative budget silently disables retrieval.
4. Either drop `CassiniVerifier.verify` at call sites that imply a gate, or switch them to `verify_with_values` over untrusted data.
5. Prune dead branches listed under finding 5.
