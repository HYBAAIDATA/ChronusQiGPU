# TOE Propagator Cold-Start — Before / After

Measured on this machine (Windows, CPython 3.12, `PYTHIA-main`), fresh
Python processes, `time.perf_counter()`. All numbers are measurements,
not estimates.

## What changed

`toe/bridge.py` (the canonical implementation; `Intelligence/toe_bridge.py`
is an identity alias resolving to the same module object). The six
forecast propagators U(t) = exp(−iHt/ℏ), t ∈ {0.5, 1.0, 1.5, 2.0, 2.5,
3.0}, over the fixed default Hamiltonian (dim=32, ℏ=1.0, m=1.0, ω=0.5)
are data-independent and now live in the module-level

    _U_TABLE: dict[float, ComplexMatrix]   # {t: U(t)}

— the single source of truth for default-parameter propagators. It is
populated exactly once at import by `_seed_default_propagator_store()`:

- **fast path**: `toe/default_propagators.json` — a checked-in artifact
  carrying H and the six U(t), verified against a canonical-JSON
  SHA-256 fingerprint (regenerate with
  `python scripts/regenerate_toe_propagators.py`, which uses the same
  compute path);
- **fallback**: `_build_propagator_table()` — a pure function (no
  instance state, no module state, no IO) computing the table via
  `ComplexMatrix.matrix_exp_unitary`;
- `TOE_SKIP_PROPAGATOR_SEED=1` disables seeding entirely.

`TOEBridge._propagator(t)` serves `_U_TABLE[t]` when the instance's
(dim, ℏ, m, ω) equals the defaults and t is on the forecast grid; any
other configuration or off-grid time falls through to the lazy
class-level `_U_STORE`/`_H_STORE` (unchanged semantics, e.g.
`TOEBridge({"omega": 1.0})` computes its own propagators — verified:
22.5 s first predict, correct and disjoint from `_U_TABLE`).

Debug guard: `TOE_DEBUG_PROPAGATOR=1` makes `predict_trajectory`
recompute a sentinel propagator and compare it element-wise against the
shared table — verified to fire on mutation
(`shared propagator U(0.5) corrupted at [0][0]: 999 != recomputed -0.838`),
zero cost on the default path.

## Measured numbers

| Metric | Before (no seed) | After (seeded) |
|---|---|---|
| `TOEBridge()` + first `predict_trajectory` | **20,173 ms** (6 matrix exponentials paid lazily on first call) | **170 ms** |
| Fresh ctor + all six `_propagator(t)` lookups, post-import | ~20 s on first predict | **0.062 ms** |
| Warm `predict_trajectory` (per call) | ~193 ms | ~193 ms (unchanged — real per-call math) |
| `import toe.bridge` (propagator contribution) | 0 ms (lazy) | **77 ms** (artifact load + verify) |
| `import toe.bridge` (total, incl. `toe/__init__` → engine/expansion/system) | ~4.3–6.8 s | ~4.3–6.8 s (dominated by sibling submodules, not this path) |

Prior revision reference point: on the pre-Kellogg bridge, the same
cold measurement was 7,612 ms (import 1.67 s, warm predict 882 ms).
The current tensor's `matrix_exp_unitary` is heavier (~3.4 s per 32×32
exponential), which is why the unseeded first call now measures ~20 s.

## Per-call latency after warm import

Six consecutive `predict_trajectory` calls on the same dummy input:
147, 164, 124, 206, 152, 174 ms. This is data-dependent work — state
encoding, six `U|ψ⟩` applications, seven `⟨H⟩` expectations, six QFI
evaluations over 32-dim matrices in pure-Python complex arithmetic
(~237k calls/call). It cannot reach < 1 ms without changing the
numerical method or memoizing predictions, both out of scope.

## Honest note on the <1 ms criterion

The review's success criterion ("fresh `TOEBridge()` + one
`predict_trajectory` < 1 ms") conflates the propagator cost (data-
independent, now seeded: **0.062 ms** post-import) with the full
prediction's per-call quantum math (**~150 ms**, irreducible). The
propagator path — the subject of this change — meets the bound with
three orders of magnitude of headroom; the enclosing call does not and
cannot under the stated constraints.

## Tests

`tests/test_toe_propagator_cache.py` — 4 tests, all pass (~4 s):

- `test_import_time_build` — importing via `Intelligence.toe_bridge`
  (identity alias) leaves `_U_TABLE` populated with exactly the six
  default times and `_H_STORE` with the default Hamiltonian.
- `test_artifact_integrity` — `default_propagators.json` verifies
  (format, params, times, SHA-256) and matches `_U_TABLE` element-wise.
- `test_cold_start_propagator_lookup_under_1ms` — subprocess: ctor +
  six lookups < 1 ms, each `is` the `_U_TABLE` object; one
  `predict_trajectory` < 3 s (proves the seeded path served it —
  unseeded would cost ~20 s).
- `test_shared_across_instances` — two instances receive the same
  `_U_TABLE[t]`/`H` objects (`is` identity), no per-instance
  duplication.
