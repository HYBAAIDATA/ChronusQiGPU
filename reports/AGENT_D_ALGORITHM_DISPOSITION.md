# Agent D — Algorithm Identity Trace and Path Disposition

QC reference: PR #139 review — requested→planned→executed trace for the
Grover/Hendrix/annealing/tunnelling/swarm surfaces, path-by-path disposition
(REMOVE / REPLACE WITH EXACT / ISOLATE NON-PRODUCTION / PROVE UNREACHABLE),
execution receipts, and fail-closed adversarial tests.

## 1. Requested → planned → executed trace

### 1.1 Hendrix (production mining route)

```
mining/scaled_execution.py::LucasScaledAethelExecutionAdapter.execute   [B]
  → toe.strict_quantum.certify_work_window(...)                          [A]  gate: exact Q(i) cert
  → verify_certificate(...)                                              [A]
  → self.scheduler.plan(count)                                           [D]
      HendrixStructuredSearch.plan → _coprime_stride(count, L_76) → gcd loop
      → HendrixSchedule (pure arithmetic; no quantum ops)
  → ordered = flatten(worker_nonces(w))                                  [B]
  → self.stack.chronus.mine(header, target_bytes, ordered)               [B→C]
      serial double-SHA256d per ordered nonce, early-exit at first hit
  → aethel stores, tensor fold roundtrip, cassini_holds(7), TOE provenance
```

- **Requested:** solve a proof-of-work work window.
- **Planned:** a coprime-stride permutation of the nonce window (the Hendrix
  schedule) — deterministic, seed-free, bijective by `gcd(stride, N) = 1`.
- **Executed:** ordinary SHA256d enumeration in schedule order. The only
  accept authority is the consensus hash check.
- **Quantum formalism in the executed call graph: none.** Every step between
  `plan` and `chronus.mine` is modular integer arithmetic; `chronus.mine`
  evaluates the hash function only. `HendrixStructuredSearch.search` returns
  `quantum_claim: False`; `HendrixChronusSearch.execution_plane` is
  `"iGPU_classical_structured_search"`.

### 1.2 Grover

Three surfaces named "Grover" exist; none executes Grover iteration on the
production solve route:

- `quantum_compute_substrate/grover_search.py` — state-vector **simulation**,
  self-labelled `truth_class: SIMULATE`/`INTERNAL`. Reachable only from the
  QCS test suite and its own demos; no production importer (see §3).
- `turing_universal_quantum_computer/grover_exact_scale.py` — **exact folded
  algebra**: the Grover iterate restricted to the exchange-symmetric 2-
  dimensional subspace, `a|w⟩ + b|u⟩`, closed-form per iteration over C.
  Registered in `chronus/.../system_fabric.py` as `wired: "idle"` with the
  note "ordering cannot beat consensus". No production caller.
- `mining/search.py::GroverStyleSearch` [B] — a **strided walk**: k\* =
  ⌊π/4·√(N·L_n)⌋ used as a modular stride over the schedule with real
  SHA256d per probe. Docstring: "amplitude math orders the search, it never
  replaces the consensus check". Honest ordering; the L_n scale-up inflates
  the stride only (coverage is still complete via the visited/fallback
  walk). No work reduction.

### 1.3 Annealing / tunnelling

`turing_core/ten_thousand.py::TenThousandQubitSystem` (D):

- `.anneal()` → `adiabatic_condition`, `landau_zener` (turing pkg
  `annealing.py`) — **exact symbolic gap profile and Landau–Zener
  probability**; verdicts, not executed workloads.
- `.tunnel()` — exact symbolic tunnel probability.
- Reachable only through TURING's own algebra surface, its tests, and the
  `gpu/quantum.py` factory (C), which **fails closed** when the package is
  absent ("a missing installation is a deployment error rather than
  permission to substitute a dense or floating-point mock").
- No mining-route caller (verified by importer sweep, §3).

### 1.4 Swarm

`TenThousandQubitSystem.swarm()` → `QuantumSwarm` driven by the exact
coined-walk Born distribution; returns empirical distribution + dispersion.
A classical stochastic-process execution driven by the exact distribution —
labelled as such. No mining-route caller.

### 1.5 VQC execution surface

`turing.../pipeline.py` (`execute_certified`, `run_pipeline`) is the **only**
surface whose contract is quantum execution. It admits a program to a real
backend (`ExecutionClass.HARDWARE`) only via a QPU provider with a recorded
job (`provider`, `job_id`, `completed_at`, `result_digest`); absent an
admitted backend it **fails closed** with a refusal/witness certificate and
never substitutes a simulator. Adversarial coverage exists:
`tests/test_backend_boundary.py` — `QPUBoundaryTests` (no provider →
unavailable; never auto-selected; hardware claims require a full job
record), `RefusalBoundaryTests` (refusal, never downgrade), `WitnessTests`
(forged `measured_qpu`/`theorem_proven`/`consensus_authority` rejected).

## 2. Hendrix call-graph proof (structure vs quantum formalism vs work)

Runtime call graph of the production route (verbatim edges):

```
execute()                     mining/scaled_execution.py        [B]
├─ certify_work_window()      toe/strict_quantum.py             [A] exact Q(i) certificate
├─ scheduler.plan()           turing.../pisot.py                [D]
│    └─ _coprime_stride()     integer gcd loop                  — arithmetic only
├─ worker_nonces()            turing.../pisot.py                [D]
│    └─ nonce_at()            (stride·p + offset) mod N          — one multiply, one mod
└─ stack.chronus.mine()       mining/four_layer_stack.py / chronus  [B→C]
     └─ double-SHA256d(header, nonce) < target                   — consensus grind
```

- **Structure:** the schedule is a permutation of positions
  `{0,…,N-1}`; bijectivity is proven by `gcd(stride,N)=1` (verified in
  `HendrixSchedule.verify` and by `test_schedule_is_a_complete_disjoint_cover`
  exhaustively). Worker classes partition the position space disjointly.
- **Quantum formalism:** zero edges. No state vector, no amplitude, no
  phase rotation is evaluated on this route. The strict-quantum certificate
  (A) is exact Q(i) algebra evaluated at admission — metadata, not work.
- **Work reduction vs plain enumeration: none — proven, not claimed.** For a
  target hit at uniform position, expected evaluations are `(N+1)/2` for the
  permuted order and for the identity order alike; the permutation changes
  *which* index is probed first, never *how many* are needed. The delivered
  guarantees are completeness (full cover), disjointness (no duplicate
  work across workers) and determinism — no speedup is claimed anywhere in
  the result object (`quantum_claim: False`, `theorem_proven: False`), and
  this document asserts none.

## 3. Path-by-path disposition

| Path | Surface | Disposition | Evidence |
|---|---|---|---|
| `turing.../pisot.py` `HendrixStructuredSearch`/`HendrixSchedule` | Production scheduler | **KEEP — intended implementation** for the schedule stage; execution receipts added (module, canonical digest, execution mode, `fallback_used`) | `tests/test_hendrix_execution_receipts.py` (9 tests) |
| `turing.../hendrix.py` `HendrixChronusSearch` | iGPU facade | **KEEP** — declares `iGPU_classical_structured_search`; receipts inherit | same suite |
| `turing.../grover_exact_scale.py` | Exact folded Grover | **PROVE UNREACHABLE** on the solve route: importers are tests, `millennium/`, `legacy/`, `chronus/.../system_fabric.py` (registered `wired: "idle"`), `product_registry.py`, `quantum_cuda.py`. No mining adapter path calls it. | importer sweep §1.2 |
| `turing.../turing_core/ten_thousand.py` | Algebra surface (anneal/tunnel/swarm/entanglement) | **KEEP as algebra surface** — verdicts, not workloads; unreachable from the solve route | importer sweep §1.3–1.4 |
| `turing.../pipeline.py` + `backends/` | VQC execution | **KEEP — the intended implementation is already wired**: admitted-backend-only execution, fail-closed refusals, witnessed output | `test_backend_boundary.py` falsification suite |
| `quantum_compute_substrate/grover_search.py` | State-vector Grover sim | **ISOLATE NON-PRODUCTION** — already unreachable from production; labels already honest (`SIMULATE`/`INTERNAL`); remains a research/testing surface | importer sweep §1.2 |
| `mining/scaled_execution.py` | Production adapter | **HANDOFF D-007 → B** — route is schedule + SHA256d grind (correct and intended); defects are *labels*: `metadata["execution_path"]="aethel_exact_tensor_hendrix_lucas_pisot_chronus"` and `toe.record_decision(..., "quantum", ...)` overclaim quantum execution. Receipts now provided for propagation | §4 |
| `mining/search.py` `GroverStyleSearch` | Strided-walk search | **HANDOFF D-007 → B** — honest ordering surface; note L_n scale inflation is cosmetic (stride only); no work reduction | §4 |
| `toe/strict_quantum.py` | Exact-Q(i) work certificate | External (A); verified honest by direct read: "does not replace Bitcoin SHA-256d or declare a share valid" | §1.1 |

## 4. The one defect the trace surfaced — and its owner

The mining route never claimed quantum execution in its own docstrings
(`four_layer_stack.py`: "the honest role of the 'quantum stage' is
reordering/pruning the probe order; it NEVER replaces hash evaluation").
The residual overclaim is in the adapter's **recorded metadata**
(`execution_path` string, TOE `"quantum"` domain records) — both inside
`mining/scaled_execution.py`, owned by Agent B. There is no honest
classical implementation that could execute quantum work in its place;
per `STRICT_QUANTUM_BOUNDARY.md`, the correct closures are (a) relabel to
`structured_classical_schedule` or (b) gate the label on an admitted
quantum backend — which would then fail closed absent hardware, leaving
the quantum-execution production claim legitimately unavailable.

Agent D side (this PR): execution receipts emitted by
`HendrixSchedule.manifest()` and `HendrixStructuredSearch.search()`
(`implementation_module`, `schedule_digest`, `execution_mode`,
`fallback_used`), plus fail-closed adversarial coverage. B needs only to
propagate `schedule["execution_mode"]`/receipt fields into
`ScaledExecutionResult.metadata` and relabel the route record.

## 5. Adversarial fail-closed coverage added this round

`tests/test_hendrix_execution_receipts.py` (9 tests):

- receipt binds `implementation_module`, `execution_mode`, and
  `schedule_digest`; digest recomputes from the emitted manifest;
- `fallback_used` pinned `False`; `quantum_claim` pinned `False`;
  `"quantum"` never appears in the execution mode;
- oracle failure propagates verbatim — no silent substitution;
- off-ladder scale indices (13, 0) refuse at construction — before any
  work; `require_lucas_execution_scale(7)` fails closed below the
  physical floor;
- schedule is exhaustively a complete disjoint cover for
  (17/64/257 × 1/3/8 workers);
- manifest digest is tamper-sensitive;
- `HendrixChronusSearch` receipts declare the `iGPU_classical_structured_search`
  plane end-to-end;
- a no-hit window probes every position — the schedule prunes nothing.
