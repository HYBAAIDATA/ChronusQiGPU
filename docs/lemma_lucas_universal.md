# Lemma U — lucas_universal_scaling

Statement: every Chronus-owned quantity envelope classified in
`docs/lucas_scaling_audit.md` as `LUCAS_BOUNDED`, `LUCAS_SCALED`, or
`LUCAS_ORDERED` is governed by the Lucas scale contract. No quantity
outside those classes is scaled; every `OUT_OF_SCOPE` surface there is
named with its reason.

## The three classes

Attribution: **Lucas scales by power; Pisot does not scale.** The scale
index `n` is a power dial — raising `n` raises the envelope by the exact
ratio `L_n/L_ref`. Pisot names the convergence witness (`phi^n ≈ L_n`
because the conjugate `|(1-sqrt5)/2|^n` vanishes), not a scaling factor.
Two ladders: the algebraic ladder `(7,10,12,15,18,20,31,50,76)` includes
index 7 (`L_7 = 29`, the algebraic base in `LucasPisotScale.budget`); the
execution ladder `CHRONUS_SCALE_RUNGS = (10,...,76)` excludes it —
physical dispatch may not admit index 7 (`require_lucas_execution_scale`
in `turing_universal_quantum_computer.pisot`).

1. **LUCAS_BOUNDED** — the quantity is bounded by an exact Lucas value
   `L_n`, computed by fast doubling over the Q[sqrt5] recurrence
   (`lucas.core.lucas`, `L_0=2`, `L_1=1`, `L_n=L_{n-1}+L_{n-2}`). Example:
   mining window candidates drawn from `lucas_ladder`, rung budgets
   `budget <= lucas(rung)`, `lucas_order_covering` plan capacity.

2. **LUCAS_SCALED** — the quantity is a logical envelope over a physical
   anchor, either `effective = physical * L_n // L_10`
   (`compute_effective_capacity`, reference rung `L_10 = 123`) or an
   envelope snapped to a ladder stop (`n = k*r` for a rung index
   `r` in `CHRONUS_SCALE_RUNGS = (10,12,15,18,20,31,50,76)`; membership by
   `is_ladder_index`, snap by `nearest_ladder_index` /
   `snap_work_items`, seam ceiling `MAX_WORK_ITEMS = 65536`).

3. **LUCAS_ORDERED** — the quantity is a deterministic ordering or
   permutation derived from the golden/Lucas structure
   (`golden_stride_walk`, `hendrix_schedule`, `poincare_11d_order`,
   phi-geodesic metric, M32 lane phyllotaxis). Ordering covers and
   sequences; it asserts nothing about hash output.

## The anchor rule

`physical` units are measured facts and are never rewritten.
`zero physical -> zero effective`. Reference rung `n = 10` yields the
identity envelope (`L_10 // L_10 = 1`). A scaled quantity is a contract
envelope — it carries the physical count alongside, unmodified.

## Envelope boundary rule

Chronus-owned envelopes snap to ladder stops: queue depths, retention
capacities, window/span defaults, audit cadences, memoization bounds,
search-effort budgets. Bounds that an operator or caller explicitly
declares are honored unchanged — caller authority outranks the snap.
Envelope *selection* scales; *exact arithmetic* (tiling a declared span,
allocating requested bytes, quorum majorities, counting measured events)
does not.

## Out of scope (declared, not silent)

- measured/physical quantities: device census, `measured_hps`, telemetry
  counters, benchmark `iterations`, evidence sample minima;
- consensus and wire invariants: `2^32` nonce space, targets, pool
  protocol fields;
- topology invariants: M32 lane width, 600-cell/H4 geometry,
  work-group geometry bounds;
- exact operations: `partition_window` tiling, `buffer.allocate` bytes,
  quorum arithmetic;
- scientific simulation parameters under `v33/` that are physics inputs,
  not Chronus work envelopes.

## What this lemma does not claim

- not measured hashrate, throughput, or speedup;
- not a GPU count or any hardware fabrication — scaling cannot create
  devices;
- not a prediction about sha256d output; the accept predicate is
  unchanged: `sha256d <= target`;
- not quantum advantage, not P vs NP, not any Millennium problem;
- not a proof that scaling produces intelligence or performance —
  envelopes are a contract, measured evidence decides outcomes.

## Scope guard

Runtime guards remain the existing ones: `use_lemma` /
`use_ordering_lemma` (`hyba/operating_model/lemma.py`) raise
`ScopeViolation` for unauthorized uses; `scale_job`/`snap_work_items`
reject non-positive or out-of-domain inputs. Any new LUCAS_* surface
must cite this lemma's class in its docstring or a scope-guarded call.

## Verification record

- `tests/test_chronus_lucas_universal.py` executes the contract on every
  wired surface: each new default is a ladder stop; `n=10` identity;
  `zero physical -> zero effective`; out-of-scope pins unchanged
  (`partition_window` exact coverage, `MIN_SAMPLES`, `LANE_ALIGN`,
  quorum floor).
- `tests/test_chronus_scale_math_independent.py`,
  `tests/test_chronus_scale_paradigm.py`,
  `packages/chronos-one-igpu/tests/test_lucas_scaling.py`,
  `chronus/mla1517_platform/python/test_measure_lucas_scaling.py`
  re-execute the pre-existing contract (138 tests).

## Signoff (executed checks, not names)

- mathematician — ladder stops are multiples of rung indices; identity
  at `n=10`; monotonic `L_n` over the ladder
- systems — scaled envelopes retain physical anchors unchanged; no
  measured quantity is multiplied
- qi_physicist — no quantum claim anywhere in scope
- security — quorum and consensus arithmetic untouched

theorem_proven: False — a verified scope contract, signed off as a
bounded claim, not a proven theorem.
