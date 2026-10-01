# TOE Wiring Landed — face_bias and causal_throttle

Date: 2026-09-26
Scope: close the wiring gap where `TOECausalSignal` was defined but never
consumed by `M32SearchSolver` / `MiningIntelligenceChooser` /
`IntelligentPoolCoordinator`.

## Audit corrections vs. the assumed baseline

The two "assumed landed" preconditions are **not present in this tree**:

- `Intelligence/toe_bridge.py` has no module-level `_U_TABLE` (the bridge
  actually used by mining is `toe/bridge.py::TOEBridge`).
- No `tests/test_toe_consensus_boundary.py` exists, and `toe_signal.py`
  carries no boundary-attestation token. `TOECausalSignal.is_valid()`
  (coherence floor, face range, entropy ≥ 0) is the only existing gate.
- The wiring gap was larger than described: **no call site ever built a
  `TOECausalSignal`**. `build_toe_signal()` and `lucas_ladder_status()` had
  zero callers; the coordinator stored a `TOEMiningContext` and discarded it.

## TOECausalSignal fields now consumed

| Field | Consumer | Effect |
|---|---|---|
| `face_bias` (0–31) | `MiningIntelligenceChooser.choose()` → `solver.set_lane_start_offset()` | Cyclically rotates the solver's declared lane order so the sweep starts at that face. Never changes `m32_structured` vs `flat_exhaustive` lead selection. |
| `causal_throttle` | `IntelligentPoolCoordinator._apply_toe_signal()` | Latches `mining_intelligence.throttle = True` (propagates into `SearchDecision.throttle` → `work_throttled`) and halves the per-dispatch nonce window breadth (`_OBSERVED_WINDOW` 320 → 160). Emits a `PURITY_TORN` event record + log with the tomography snapshot (entropy, purity, face_bias). |
| `ladder` | Coordinator attaches via `dataclasses.replace(signal, ladder=lucas_ladder_status(candidate_window))` | Now actually populated and stored on `last_toe_signal`. |
| `coherence`, `entropy`, `job_id`, `node_id`, `sequence` | `is_valid()` gate + `PURITY_TORN` event payload | Audit/gating only. |

## Call sites changed

- `chronus/mla1517_platform/python/mla1517/mining/solver.py`
  - `M32SearchSolver.__init__` gains `self._lane_start_offset: int | None = None`.
  - New `set_lane_start_offset(preferred_face)` — validates `[0, 31]`, raises
    `ValueError` outside it (fail-closed), idempotent, stores only a start
    index; the 32-lane table is never mutated.
  - New `get_lane_start_offset() -> int`.
  - `candidates()` rotates `turing.lane_order(start_nonce)` to pivot on the
    offset when set; the start-lane alignment invariant now checks the
    rotated first lane.
- `chronus/mla1517_platform/python/mla1517/mining/chooser.py`
  - `choose()` accepts `toe_signal` and `solver` kwargs. When
    `isinstance(toe_signal, TOECausalSignal) and toe_signal.is_valid()` and a
    solver is supplied, it calls `solver.set_lane_start_offset(signal.face_bias)`
    before the decision is built, and emits
    `LOG.debug("TOE face_bias=%d applied to solver start lane")`.
    No-op when the signal is absent, invalid, or no solver is passed.
    `face_bias` never enters the lead-selection branches.
  - New `self.throttle` latch on `MiningIntelligenceChooser`; it feeds
    `SearchDecision.throttle` so a latched throttle gates dispatch.
- `chronus/mla1517_platform/python/mla1517/mining/coordinator.py`
  - New `_build_toe_signal()` — converts `last_toe_context` (the measured
    `TOEMiningContext` from `toe.analyse`) into a `TOECausalSignal`; returns
    `None` fail-closed when TOE is absent or conversion raises.
  - New `_apply_toe_signal()` — `causal_throttle=True` latches the chooser
    throttle, sets `_dispatch_breadth = _OBSERVED_WINDOW // 2`, and appends a
    `PURITY_TORN` event to `self.purity_torn_events` (also `LOG.warning`).
    `causal_throttle=False` leaves existing throttle state untouched.
  - `submit_record` now: builds the signal → applies the throttle gate →
    materialises the (possibly halved) candidate window → attaches the
    `LucasLadderStatus` → calls `choose(..., toe_signal=..., solver=self.solver)`.
  - `_observed_candidate_window()` reads `self._dispatch_breadth`.
  - `submit_candidate`'s `choose()` call is unchanged (no fresh signal there).

## Consensus boundary

Unchanged. `pow.py` (`sha256d`, `check_pow`, `compact_target`,
`build_header`), `BlockHeader` serialization, and the target comparison are
untouched. `test_throttle_does_not_touch_consensus` monkeypatches
`sha256d`/`check_pow`/`compact_target` to raise and runs the full throttled
`submit_record` path — no raise, proving the throttle path never reaches
consensus evaluation.

## Before/after on one representative Stratum job

Job base nonce `start_nonce = 0x1A2B3C4D` (natural first lane `13`),
`TOECausalSignal(face_bias=17, coherence=0.92, entropy=0.4)`:

```
BEFORE: (nonce, lane) = (439041101,13) (439041100,12) (439041099,11) ...
AFTER : (nonce, lane) = (439041105,17) (439041104,16) (439041103,15) ...
get_lane_start_offset() == 17
```

The sweep pivots to face 17; the remaining lanes follow the same declared
Turing order cyclically — coverage and candidate set are unchanged.

## Verification

- `python/test_toe_chooser_wiring.py`: 7 tests pass (the 5 required plus
  `test_valid_signal_sets_start_lane_without_changing_lead` and
  `test_no_signal_is_noop`).
- `python/test_toe_face_geometry.py`: 4 tests pass. Actual convention
  documented: first 12 frame entries are icosahedron-vertex directions
  (pentagon face centres, norm² = φ+2); last 20 are dodecahedron-vertex
  directions (hexagon face centres, norm² = 3).
- Regression: `test_m32_governance`, `test_toe_mining_integration`,
  `test_turing_mining_integration`, `test_control_plane_wiring`,
  `test_intelligence_controller` — 36 passed.

## Follow-up: consensus-boundary hardening (landed)

The two "assumed landed" preconditions were recreated/verified:

- `_U_TABLE` cold-start propagator table: already present in the worktree's
  `toe/bridge.py` (module-level table for t ∈ {0.5,…,3.0}, SHA-256-verified
  `default_propagators.json` artifact, `_propagator` fast path,
  `_verify_propagator_integrity` sentinel). Measured `TOEBridge()` cold start
  ≈ 0.01 ms; `tests/test_toe_propagator_cache.py` pins the contract.
- Boundary hardening in `chronus/mla1517/mining/toe_signal.py`:
  - `TOEConsensusBoundaryError` + `_assert_no_consensus_fields` —
    `build_toe_signal` recursively rejects any TOE result carrying
    consensus-domain keys (target, nonce, header, sha256d, share, ...) —
    fail-closed: refused, never sanitised. Verified clean against real
    `TOEBridge().predict` output.
  - `boundary_token` — every `TOECausalSignal` self-attests
    `TOE-BND-<sha256>` bound to its feed-forward payload under a
    domain-separated tag; `is_valid()` requires an exact match. `ladder`
    is excluded so the coordinator's `replace(signal, ladder=...)` stays
    valid.
  - `tests/test_toe_consensus_boundary.py` (7 tests) pins attestation,
    tamper fail-closed, vocabulary rejection (top-level and nested),
    no consensus fields on the dataclass, ladder compatibility, a
    monkeypatched-consensus full-pipeline run, and poisoned-result
    fallback.
- The soft gate (`PERMITTED_WITHOUT_TOE`, `_toe_or_declared_absent`,
  SOFT GATE docstring) was landed by the parallel session; my signal wiring
  composes with it — `submit_record` calls `_toe_or_declared_absent(
  "observe_record")` before `toe.analyse`.
- Retired alias modules (`Intelligence.toe_*`, `Intelligence.quantum_tensor`,
  `Intelligence.exact_tensor`, `Intelligence.intelligences.*`,
  `toe.{quantum_tensor,exact_tensor,exact_field,tensor_ml}`) remain deleted
  per `ToeNoShimsTests`; the `Intelligence/intelligences/` directory itself
  was removed so it no longer resolves as a namespace package.

## Note on file placement

The mission's `tests/test_*.py` paths assume a top-level `chronus/mla1517/` layout.
The real package is `chronus/mla1517_platform/python/mla1517/` and its test
convention is flat files in `python/` (pytest `testpaths` +
`make python-regression` unittest discovery), so the new test files live at
`chronus/mla1517_platform/python/test_toe_chooser_wiring.py` and
`.../test_toe_face_geometry.py` where CI actually collects them.
