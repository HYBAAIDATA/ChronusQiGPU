# Lucas scaling audit — Chronus quantity surfaces

Audit of every quantity-bearing surface under `chronus/`. Purpose: state
precisely where the Lucas/Pisot scale contract reaches, classify each
quantity into exactly one contract class, and name the surfaces that fall
outside the claim instead of pretending they do not exist.

The canonical contract machinery already exists:

| Surface | Role |
|---|---|
| `lucas/core.py`, `lucas/ladder.py`, `lucas/bound.py`, `lucas/scaling_research.py` | exact Lucas substrate (Q[sqrt5] recurrence, fast doubling, Pisot bounds) |
| `Intelligence/lucas_scales.py` | canonical ladder (`LUCAS_SCALE_LADDER`), `CHRONUS_SCALE_RUNGS = (10,12,15,18,20,31,50,76)`, `is_ladder_index`, `nearest_ladder_index`, `next_ladder_index` |
| `chronus/seam/scale.py` | seam contract: `snap_work_items`, `scale_job`, `compute_effective_capacity`, `memory_budget_bytes`, `scale_report`, `MAX_WORK_ITEMS = 65536`, `REF_LUCAS_N = 10` |
| `chronus/mla1517/{scale,scaling,lucas_scale}.py` | platform-era scale contract (same formula family) |

Definitions used below:

- **Ladder stop** — a positive integer divisible by a rung index in
  `CHRONUS_SCALE_RUNGS` (`n = k·r`). `is_ladder_index` is the membership
  test; `nearest_ladder_index` is the snap (ties prefer the upward stop).
- **Rung value** — an exact Lucas number `L_n` computed from the Q[sqrt5]
  recurrence (`lucas.core.lucas`), used for bounds, never as a measured
  quantity.

## Classification

| Class | Meaning | Primitive |
|---|---|---|
| `LUCAS_BOUNDED` | quantity bounded by `L_n`, computed via fast doubling | `lucas.core.lucas`, `lucas.bound.*` kernels |
| `LUCAS_SCALED` | `physical * L_n // L_10` logical envelope over a physical anchor, or an envelope snapped to a ladder stop | `compute_effective_capacity`, `snap_work_items`, `nearest_ladder_index` |
| `LUCAS_ORDERED` | deterministic ordering/permutation derived from the golden/Lucas structure | `golden_stride_walk`, `hendrix_schedule`, `poincare_11d_order`, `MiningGeodesicMetric` (phi metric), lane phyllotaxis |
| `OUT_OF_SCOPE` | quantity must stay raw — reason stated per row | none |

Two scope rules applied throughout:

1. **Chronus-owned envelopes snap; caller-declared bounds are honored.**
   Constants and defaults the codebase itself declares (queue depths,
   retention limits, window defaults) become ladder stops. A bound that an
   operator or caller explicitly sets is that caller's authority and is
   passed through unchanged.
2. **Envelope selection scales; exact arithmetic does not.** Picking *how
   much* work/history/capacity is a scale-contract decision. Tiling a
   declared span exactly (`partition_window`), allocating the requested
   bytes (`buffer.allocate`), counting measured facts (`telemetry`), and
   quorum arithmetic (`threshold`) are exact operations — scaling them
   would falsify the value.

## Already in contract (no change)

| Module | Quantity | Class | Evidence |
|---|---|---|---|
| `chronus/seam/scale.py` | work items, memory bytes, capacity | LUCAS_SCALED | the contract itself |
| `chronus/seam/workflow.py` | `scale_job` on requested work | LUCAS_SCALED | consumer |
| `chronus/seam/toe_loop.py` | `scale_job` on requested work | LUCAS_SCALED | consumer |
| `chronus/hyba_offering.py` | `compute_effective_capacity`, `snap_work_items` | LUCAS_SCALED | consumer |
| `chronus/readiness.py` | scale-function readiness checks | LUCAS_SCALED | consumer |
| `chronus/fabric.py` | `chunk_size` via `nearest_ladder_index`, `epoch32` discipline, `scale_index` validated against `LUCAS_SCALE_LADDER`, `lucas_rung` attestation | LUCAS_SCALED | `_lucas_dispatch` |
| `chronus/mla1517/mining/operating_policy.py` | window candidates = `lucas_ladder` (Lucas values), lane-rounded | LUCAS_BOUNDED | `lucas_ladder()` |
| `chronus/mla1517/mining/coordinator.py` | rung budgets `lucas(rung)`, `_OBSERVED_WINDOW = 10*LANES = 320` (already a stop), hendrix/poincare orders | LUCAS_BOUNDED + LUCAS_ORDERED | `lucas(rung)` enforcement |
| `chronus/mla1517/mining/{solver,lane,turing_adapter,hendrix_order,poincare_11d_order}.py` | lane ordering, M32 phyllotaxis, golden schedules | LUCAS_ORDERED | ordering modules |
| `chronus/mla1517/mining/geodesic_nonce_planner.py` | window permutation by phi-scaled geodesic metric | LUCAS_ORDERED | `MiningGeodesicMetric(scale=PHI)` |
| `chronus/mla1517/mining/promotion.py` | `lucas_ladder` window candidates | LUCAS_BOUNDED | consumer |
| `chronus/mla1517/mining/scale_state.py` | plateau/scale-window state over measured evidence | LUCAS_SCALED | measured-window classifier |
| `chronus/mla1517/mining/choosers` (candidate budgets) | `budget=250_000` oracle cap — already a ladder stop (mult. of 50) | LUCAS_SCALED | compliant constant |
| `chronus/paradigm/schedules.py` | nonce schedules via `golden_stride_walk`, tiered phi ordering | LUCAS_ORDERED | ordering lemma scope |
| `chronus/virtual_igpu/planner.py` | `lucas_order_covering`, `capacity = lucas(n)` per plan | LUCAS_BOUNDED | planner contract |
| `chronus/v33/phi_scaling.py` | phi-tiered scaling of v33 quantities | LUCAS_SCALED | phi tiers |
| `chronus/mla1517/{scale,scaling,lucas_scale}.py` | platform contract surfaces | LUCAS_SCALED | contract definitions |

## Wiring targets — raw quantities that become ladder stops

| Module | Quantity | Current | Class | Target | Justification |
|---|---|---|---|---|---|
| `chronus/seam/store.py` | default queue `threshold` | `64` | LUCAS_SCALED | `snap_work_items(64)` = 62 | backpressure depth is a capacity envelope |
| `chronus/seam/hybrid.py` | `partition(span)` envelope | `1 << 20` default, caller span raw | LUCAS_SCALED | `span = snap_work_items(span)` at entry; job span = work envelope under `MAX_WORK_ITEMS` |
| `chronus/seam/fleet.py` | `route(job)` span | `job.get("span", 1<<20)` | LUCAS_SCALED | inherits `partition` snap | span is the job's work envelope |
| `chronus/seam/run.py` | `window` default | `4096` | LUCAS_SCALED | `snap_work_items` on resolved window | batch window envelope |
| `chronus/seam/workflow.py` | `window` default `4096`; `genetic_configure(generations=3, population_size=8)` | raw | LUCAS_SCALED | snap window; genetic budgets snap inside `evolve_mining_config` | window + search-effort envelopes |
| `chronus/seam/genetic_mining.py` | `generations`, `population_size` | `5`, `8` | LUCAS_SCALED | `nearest_ladder_index` within validated bounds (5->10, 8->10) | optimization-effort envelopes |
| `chronus/seam/probe.py` | `_measure_host_hps(work=1024)` | `1024` | LUCAS_SCALED | `snap_work_items(1024)` = 1023 | per-sample workload depth is a work envelope; `samples=3` stays raw (evidence minimum, not capacity) |
| `chronus/fabric.py` | `_DEFAULT_WORK_ITEMS` | `1 << 20` | LUCAS_SCALED | `nearest_ladder_index(1<<20, 1, 1<<20)` = 1048575 | default request envelope is a ladder stop (dispatch chunk already snaps) |
| `chronus/mla1517/mining/agentic_controller.py` | `_DEFAULT_QUEUE_DEPTH=3`, `_MAX_QUEUE_DEPTH=8`, `_ADAPT_WINDOW=32`, outcome history `deque(256)`, `_MAX_POLICIES=32`, `_MAX_POLICY_ID=64`, `MAX_STATE_BYTES=65536` | raw | LUCAS_SCALED | 10, 10, 31, 255, 31, 62, 65535 | bounded queue/retention/policy capacities; `_DEFAULT_LOOKAHEAD`, `_ADAPT_MIN_EVENTS`, `_STARVATION_EVENTS`, waste ratios stay raw (adaptive control parameters, policy-owned); `_LEAD_HISTORY_WINDOW=20` already a stop |
| `chronus/mla1517/mining/causal.py` | `capacity=4096` | raw | LUCAS_SCALED | 4095 | event-history retention envelope |
| `chronus/mla1517/mining/decision_journal.py` | `capacity=512` | raw | LUCAS_SCALED | 510 | decision-record retention envelope |
| `chronus/mla1517/mining/quality.py` | `window=64` rolling window | raw | LUCAS_SCALED | 62 | per-policy quality-history envelope |
| `chronus/mla1517/mining/closed_loop.py` | sample retention `deque(maxlen=32)`, history `deque(maxlen=64)` | raw | LUCAS_SCALED | 31, 62 | retention envelopes; `min_samples`, `cooldown_windows`, `max_attempts` stay raw (control/measurement protocol) |
| `chronus/mla1517/mining/recovery_effect.py` | `SPAN=16` | raw | LUCAS_SCALED | 15 | comparison span over retained windows |
| `chronus/mla1517/mining/self_healing_agent.py` | `max_pending=64` | raw | LUCAS_SCALED | 62 | recovery-queue capacity envelope |
| `chronus/mla1517/mining/nonce_lease.py` | `max_active=16`, `terminal_memory=512`, `_WORK_SPACE_MEMORY=8`, `_EXTRANONCE2_SKIP_LIMIT=64` | raw | LUCAS_SCALED | 15, 510, 10, 62 | lease-ledger retention/bounds; `LANE_ALIGN=32` stays raw (M32 topology) |
| `chronus/mla1517/mining/policy_audit.py` | `every=64` audit cadence | raw | LUCAS_SCALED | 62 | audit cadence is a work envelope |
| `chronus/mla1517/mining/hashrate_governor.py` | `lru_cache(maxsize=4096)` | raw | LUCAS_SCALED | 4095 | memoization capacity envelope |
| `chronus/mla1517/mining/cycle_fsm.py` | `history=256` | raw | LUCAS_SCALED | 255 | transition-history retention envelope |
| `chronus/mla1517/mining/production_transport.py` | `PYTHIA_STRATUM_OUTBOUND_QUEUE` default `256`, `_submit_rtt_ms deque(2048)` | raw | LUCAS_SCALED | 255, 2046 | outbound queue + RTT-history envelopes |
| `chronus/mla1517_platform/python/runtime_config.py` | `WINDOW_MAX = 1<<22` | raw | LUCAS_SCALED | floor-snap = 4194300 | operator window bound is Chronus-declared; `window` default 200000 and `WORKERS_MAX=600` are already stops |

## Out of scope — and why (the honest boundary)

| Module(s) | Quantity | Reason |
|---|---|---|
| `chronus/measurement/**` (~40 modules) | sample counts, windows, buffers, benchmark sizes | physical measurement methodology; Rule 7 forbids presenting envelopes as measurement. Workload *sizes* may snap at their own envelope boundaries, but evidence counts never scale |
| `chronus/gpu_capabilities.py`, `chronus/seam/probe.py` census fields, `chronus/detect.py`, `chronus/device.py` | `compute_units`, `memory_bytes`, `max_work_group`, device counts | the physical anchor itself — scaling the census falsifies it; `effective = physical * L_n // L_10` keeps `physical` raw |
| `chronus/engine.py`, `chronus/tensor_compute.py`, `chronus/native_*` | matmul dims, OpenCL work-group geometry, hardware batch bounds | operand shape and device-kernel contract, not envelopes |
| `chronus/telemetry.py`, `chronus/mla1517/telemetry*.py`, `chronus/mla1517/mining/{execution,loss_ledger,storage_recorder,telemetry_history,chain_observer}.py` | counters, seq numbers, observed spans | measured facts; the record is the evidence |
| `chronus/seam/buffer.py` | `size_bytes` | exact allocation — must equal the request |
| `chronus/seam/threshold.py`, `seam/{axioms,zk,invariants,signatures,bennett,attest_compose,contract}.py`, `chronus/mla1517_platform/python/al_haras_pythia.py` | quorum `k`, majority floors, verification levels | security/quorum arithmetic — exact majorities, never scaled |
| `chronus/one_igpu_mining.py` `partition_window`, `chronus/phi_gpu.py` `work_items=boundary.length` | span counts, boundary lengths | exact tiling of a caller-declared range; the *window choice* upstream is already Lucas |
| `chronus/mla1517/mining/{pow,verification,stratum_*,pool_chain,mining_bridge,production_integration}.py`, `chronus/client.py`, `chronus/production.py` | targets, extranonce2, wire fields, `2^32` nonce space | consensus/wire invariants — external protocol facts |
| `chronus/h4_600.py`, `h4_coverage.py`, `h4_group.py`, `cell600_bind.py`, `m32_geometry.py`, `exact_geometry.py`, `mining/geometry.py` (`LANES=32`), `self_optimizing_agent` `max_local_size`/`max_global_size` | 600-cell counts, lane width, work-group geometry | topology/device geometry invariants |
| `chronus/mla1517/mining/{world_model,capability surface,closed_loop control params,intelligence_controller,policy trigger thresholds}.py`, `chronus/seam/capability.py` (`MIN_SAMPLES=32`, `samples`, `warmup`) | sample minima, cooldowns, waste ratios, thermal limits | evidence methodology and control-theory guards — scaling them changes safety/evidence semantics, not capacity |
| `chronus/mla1517/mining/persistence.py` `BoundedPersistenceQueue`, `chronus/mla1517/mining/telemetry_history.py` `limit` | `max_pending`, read `limit` | caller-declared bounds — caller authority is honored, not rewritten |
| `chronus/runtime.py` | `iterations` | benchmark repetition protocol (measurement methodology) |
| `chronus/v33/**` (except `phi_scaling.py`), `chronus/mla1517/quantum.py` | evolution steps, lattice sizes, dt, scene params | scientific simulation parameters — physics inputs, not Chronus work envelopes |
| `chronus/seam/job_thermo.py`, `seam/reversible.py` | energy accounting, step counts | thermodynamic model parameters — physical model, not envelope |
| `chronus/{conformance,spec,report,delivery,consortium_push,detect,device,gpu_reference,m5_ultra}.py`, `chronus/seam/__main__.py`, `scripts/**` | vectors, manifests, CLI plumbing | conformance fixtures and operator tooling — not quantity envelopes |
| all `test_*.py`, `conftest.py`, `agentic_fixtures.py` | fixture sizes | test code — tests assert the contract, they are not it |

## Coverage summary

- `chronus/` contains 466 Python modules. 124 already touch the Lucas /
  golden / ladder substrate; of the remainder, the quantity-bearing
  production surfaces are enumerated above.
- After the wiring targets land, **every Chronus-owned bounded envelope**
  (queue depth, retention capacity, window default, span, audit cadence,
  memoization bound, policy capacity) is a ladder stop.
- What is deliberately *not* scaled: the physical census, measured
  throughput, quorum arithmetic, consensus/wire fields, exact tilings and
  allocations, topology invariants, evidence-methodology minima, and
  caller-declared operator bounds. Those boundaries are pinned by tests in
  `tests/test_chronus_lucas_universal.py`.

## Wiring plan (one commit per subsystem)

1. `seam`: queue threshold, partition/route span, run/workflow window
   defaults — LUCAS_SCALED.
2. `seam` genetic budgets: `evolve_mining_config` generations/population —
   LUCAS_SCALED.
3. `fabric`: `_DEFAULT_WORK_ITEMS` — LUCAS_SCALED.
4. `mining`: bounded capacities across `agentic_controller`, `causal`,
   `decision_journal`, `quality`, `closed_loop`, `recovery_effect`,
   `self_healing_agent`, `nonce_lease`, `policy_audit`, `hashrate_governor`,
   `cycle_fsm`, `production_transport` — LUCAS_SCALED.
5. `probe`: measurement workload depth — LUCAS_SCALED.
6. `platform`: `runtime_config.WINDOW_MAX` — LUCAS_SCALED.

`theorem_proven: False` everywhere. Accept predicate unchanged
(`sha256d <= target`). No throughput, hashrate, GPU-count, quantum, or
Millennium-problem claim is made anywhere in scope.
