# HYBA — Live Mining Truth Verification

**Phase:** read-only forensic verification. **No production code was modified.**
**Date:** 2026-08-19 · **Repo:** `HYBAENTERPRISE1/HYBA_Intelligence` @ `b39e43a` (+3 uncommitted files)
**Harness:** `scripts/live_mining_trace.py` (new, read-only; wraps live instances, never mocks)
**Artifacts:** `benchmarks/reports/live_mining_trace_1787133388.json` (canonical, `--wait 120 --observe 180`)
`benchmarks/reports/live_mining_trace_1787133077.json` (independent confirming run)

---

## 1. Executive Summary

**FINAL CLASSIFICATION: `BLOCKED — ZERO EXECUTION`**

When a real pool job arrives, **no SHA256d work occurs.** This is measured, not inferred.

Two independent live runs against ViaBTC, on a real authorised worker with real jobs at real
difficulty, produced **761/761 and 462/462 MINE entries with a live job and zero `scan()`
invocations.** The independent hash counter never left zero.

The causal chain is broken at exactly one line. `_preempt_inflight_igpu()` raises a cancellation
flag and drains the job queue; `state_mine()` only clears that flag inside a `try` block guarded
by a 50 ms `next_job()` call that the drain itself guarantees will time out. The flag is therefore
set once, on the first `clean_jobs` notification, and never cleared again. Every subsequent cycle
returns before `mine_job()`.

Two things must be said plainly about what this means for the evidence base:

1. **The `[STATE 2: MINE] Searching for 80-byte header…` log line prints on every one of those
   761 cycles.** It sits above the gate that kills the cycle. Any prior conclusion drawn from that
   message is void.
2. **The unit suite does not detect this.** `test_unified_treasury_workload.py::test_1_end_to_end_execution`
   passes while live throughput is zero.

Against that, three things are in better shape than expected and should not be disturbed:
the nonce-accounting semantics are honest, the miner's internal bookkeeping is *not* lying
(it correctly reports zero), and the substrate labelling is truthful.

---

## 2. Required Field Report

| Field | Value |
|---|---|
| **POOL** | `btc.viabtc.io:3333`, worker `PYTHIA.001`, handshake OK, latency 138.8 ms, **authorized** |
| **JOB** | 12 real jobs `45ce…45d9`; `clean_jobs=true`; difficulty `16384.0`; target `000000000003fffc…` |
| **MINE ENTERED** | 761 times — **761 of 761 with a valid live job** |
| **SCAN INVOCATIONS** | **0** |
| **NONCES REQUESTED** | **0** (against a configured budget of 250,000/cycle) |
| **HASHES ACTUALLY EXECUTED** | **0** |
| **MINER-CLAIMED HASHES** | **0** |
| **ACCOUNTING DELTA** | **0 — internal accounting is CONSISTENT** (see §4) |
| **ACTUAL SUBSTRATE** | `math_substrate_sha256d` (`MathSubstrateSHA256D`) |
| **HARDWARE VERIFIED** | **false** (`_igpu_available = False`) |
| **LOCAL VALIDATIONS** | 0 |
| **SHARES SUBMITTED** | 0 |
| **SHARES ACCEPTED** | 0 |
| **SALAMANDER STATUS** | HEALTHY throughout — `error_count = 0`, circuit CLOSED |
| **ZERO-THROUGHPUT DETECTION** | **ABSENT** — no invariant exists (see §7) |
| **SUPPOSITION ACTIVITY** | active every cycle; **failing**: `'dict' object has no attribute 'create_superposition'` |
| **ENTANGLEMENT ACTIVITY** | reported as intelligence telemetry only; **does not touch hash counters** (correct) |
| **FINAL CLASSIFICATION** | **`ZERO_WORK_DETECTED` → `BLOCKED — ZERO EXECUTION`** |

---

## 3. The Causal Chain — where it stops

```
REAL POOL CONNECTION      OK    btc.viabtc.io:3333, TLS=False, handshake OK
REAL STRATUM JOB          OK    12 jobs, clean_jobs=true, difficulty 16384
JOB CALLBACK              OK    _on_stratum_job fired 12x
ACTIVE JOB                OK    _active_job populated; has_job=true on 761/761 cycles
STATE 2: MINE             OK    entered 761x
INTELLIGENCE DECISION     OK    lead=quantum_lucas, reason=agent_policy_execution_igpu
SUBSTRATE SELECTION       OK    MathSubstrateSHA256D bound and callable
  ...header built, merkle root computed, target parsed, "Searching for..." logged...
scan()                    ####  *** CHAIN STOPS HERE — 0 invocations ***
SHA256d hashes executed    --    0
candidate/nonce result     --    candidate only, never hashed
local validation           --    0
share submission           --    0
pool response              --    0
treasury accounting        --    records 0 (honestly)
```

### Root cause — proven, not assumed (brief point 5)

`headless_miner.py`:

```python
# _on_stratum_job (L304)  -> clean_jobs -> _preempt_inflight_igpu()
def _preempt_inflight_igpu(self, job_id=None):
    self._active_mining_cancelled.set()   # L310  flag raised
    self.stratum.drain_jobs()             # L312  queue emptied

# state_mine (L606)
try:
    current_job = self._await_stratum(self.stratum.next_job(), timeout=0.05)
    self._active_job = current_job
    self._active_mining_cancelled.clear() # L609  <-- INSIDE the try
except Exception:
    current_job = self._active_job        # <-- the path actually taken, every time

...
logging.info("[STATE 2: MINE] Searching for %s | job=%s ...")   # L703  PRINTS
...
if self._active_mining_cancelled.is_set():
    return candidate_nonce_hex            # L734  *** returns here, always ***
result = self.agentic.mine_job(...)       # L750  NEVER REACHED
```

`drain_jobs()` empties the queue, so `next_job(timeout=0.05)` **must** raise. The `except` branch
skips `clear()`. The flag latches permanently on the first `clean_jobs` notification — which
ViaBTC sends with the very first job.

**Runtime proof:** `cancel_flag_set = true` on **761 of 761** cycles in the canonical run and
**462 of 462** in the confirming run. This is not a race or an intermittent condition.

**Git provenance:** introduced by `f0e8b5f "Refactor stratum iGPU mining pipeline"`
(`git log -S _preempt_inflight_igpu`). It predates both `91f5937` (budget 512→250,000) and
`3c381f5` (mathematical fallback). **Neither of those commits addressed this defect** — they are
genuine fixes to genuine problems that sat *downstream* of a gate nothing ever passes. That is why
raising the budget to 250,000 produced no measurable change.

---

## 4. Independent vs Internal Accounting (brief point 3)

**Classification: D — ZERO EXECUTION.** *Not* B (internal accounting error) and *not* C (ledger error).

| Source | Hashes |
|---|---|
| Independent wrapped `scan()` | 0 |
| `miner.total_sha256d_hashes` | 0 |
| Treasury ledger | 0 |

`hashes_claimed_by_miner == hashes_measured` on **all 761 cycles**. The bookkeeping is not lying.
It is faithfully reporting that nothing happened. **The defect is execution, not accounting.**

### One accounting defect does exist, and it is not a hash-count defect

`state_mine()` returns `candidate_nonce_hex` on every early-exit path. `unified_treasury_workload.py:233`
assigns that return straight into `cycle_data["outcome"]["found_nonce"]`. That is the origin of the
committed report's `"found_nonce": "070db6f9"` alongside `"hashes_done": 0`.

Measured: **761 distinct values returned across 761 cycles, `returned_is_found_nonce = false` on
all 761.** These are φ-guided *candidates*, never hashed. A field named `found_nonce` must never
be populated by a candidate.

---

## 5. Substrate Truth (brief point 4)

| | |
|---|---|
| `planned_substrate` | `igpu` (intelligence reason: `agent_policy_execution_igpu`) |
| `actual_substrate` / `miner.hash_backend` | `math_substrate_sha256d` |
| `type(miner.accel._igpu).__name__` | `MathSubstrateSHA256D` |
| `miner.accel._igpu_available` | **`False`** |
| `substrate_backends_observed` | `{}` — empty, because `scan()` never ran |

**The mathematical fallback is what is bound. The physical iGPU is not executing.** The native
runtime failed to initialise (`HYBA_CUSTOM_IGPU_SHA256D_LIB` unset) and `substrate.py:90` correctly
substituted `MathSubstrateSHA256D` and relabelled `hash_backend`. **That labelling is honest and
should be preserved.**

### The `hardware_verified` collapse — confirmed at source

`substrate.py` assigns the *fallback object* to `self._igpu` (L90) while maintaining a separate,
correct `self._igpu_available = False` (L81). Three call sites read the wrong attribute:

| Site | Code | Consequence |
|---|---|---|
| `unified_treasury_workload.py:264` | `"hardware_verified": bool(getattr(miner.accel, "_igpu", False))` | reports `true` on the mathematical fallback |
| `unified_treasury_workload.py:187` | `igpu_status = "available" if getattr(accel, "_igpu", None)` | `architecture.igpu: true` when no iGPU exists |
| `mining_preflight()` | same truthiness test | printed **`IGPU AVAILABLE`** in this run while `_igpu_available` was `False` |

`_igpu` is *always* truthy — it is either the native object or the fallback object. The correct
attribute (`_igpu_available`) already exists and is already correct. **This is a one-word read
error at three sites, not a design problem.**

---

## 6. Fallback Interface Audit (brief point 6) — documented, not fixed

| Method | Expected | Implemented | Invoked by prod | Failure consequence |
|---|---|---|---|---|
| `scan` | yes | yes, signature **matches** | **yes** | — |
| `cancel_and_flush` | yes | yes — **body is `pass`** | **yes** | **semantic failure, see below** |
| `alloc` | `(self, size)` | `(self)` — **arity mismatch** | no | latent `TypeError` |
| `h2d` | `(self, buf, payload)` | `(self, prefix)` — **mismatch** | no | latent `TypeError` |
| `d2h` | `(self, buf, size)` | `(self)` — **mismatch** | no | latent `TypeError` |
| `close` | yes | yes (`pass`) | no | benign |
| `_bind_symbols` | yes | yes (`pass`) | no | **falsely implies native symbols bound** |

Two findings:

- **On committed `main`, `cancel_and_flush` does not exist at all.** The six stub methods are in an
  **uncommitted** working-tree change to `accel/math_substrate_sha256d.py`. On `main`, the call at
  `headless_miner.py:318` raises `AttributeError`, and the handler at L320 **re-raises inside the
  Stratum listen callback**. The stubs suppress that crash — but they were not the cause of zero
  work, and they do not fix it. The latch is independent and predates them.
- **`cancel_and_flush()` returning `pass` is a silent lie.** `MathSubstrateSHA256D.scan()` is a
  synchronous `for` loop over the full budget with **no cancellation primitive anywhere in the
  module**. An in-flight mathematical scan is *not cancellable*. Preemption can only take effect
  after the scan returns. At 250,000 nonces this is a real latency, and the API currently claims a
  capability it does not have.

---

## 7. Salamander Health Semantics (brief point 7) — the missing invariant

**Salamander cannot currently distinguish `healthy + productive` from `healthy-looking + zero throughput`.**

`state_heal()` calls `self.salamander.heal(self.metrics["error_count"])`. `error_count` is
incremented **only** by a caught exception in `execute_cycle`. The zero-work path throws nothing —
it is a clean `return`. Across 761 zero-work cycles Salamander reported HEALTHY with `errors=0`.

**Exact missing invariant:**

```
MINE entered  AND  valid non-stale live job  AND  miner running
    =>  SHA256d attempts MUST increase
```

Nothing in the codebase expresses this. Confirmed: **zero throughput can persist indefinitely
while the system reports HEALTHY.** There is also no state vocabulary distinguishing
`NO_JOB / WAITING_FOR_JOB / MINING / MINING_ZERO_THROUGHPUT / HASHING / SUBMITTING /
POOL_ACCEPTED / POOL_REJECTED / STALE / RECOVERING` — `self.state["current_state"]` carries only
the coarse loop stage.

---

## 8. Nonce Accounting Semantics (brief points 8 & 10) — **PASS, do not disturb**

This is the part of the system that is already correct, and it deserves to be recorded as such.

`total_sha256d_hashes` has **exactly one writer** in the entire backend:

```python
headless_miner.py:763   self.total_sha256d_hashes += hashes_scanned   # <- result["hashes"] from scan()
```

No supposition, entanglement, quantum-walk, φ-resonance, Grover-ordering, folding or
candidate-region path writes to it. The three concepts stay separate:

| Concept | Source | Value this run |
|---|---|---|
| NONCES REPRESENTED (`logical_nonce_space`) | constant `2**32` | 4,294,967,296 |
| mathematical candidate regions | 32 gauge faces | 32 |
| NONCES REQUESTED FROM SUBSTRATE | summed `count` arg to `scan()` | **0** |
| HASHES ACTUALLY EXECUTED (`physical_candidates_evaluated`) | `total_sha256d_hashes` | **0** |
| HASHES VALIDATED | `validate_sha256d` calls | 0 |
| SHARES SUBMITTED / ACCEPTED | pool ACK only | 0 / 0 |

**No inflation path from mathematical inference into physical hashrate exists.** The `QOps`
throughput figures (~4–13 M QOps) logged by `[STATE 1.5: SEARCH]` are labelled as quantum
operations and are correctly never mixed into H/s.

---

## 9. Policy Boundaries (brief point 9) — enforced only in the harness

| Control | Status |
|---|---|
| `HYBA_MAX_EHS ≤ 10 EH/s` | **ADVISORY ONLY.** `headless_miner.py:728–747` clamps only the *intelligence recommendation* (`agent_action.target_hashrate`) and logs a warning. It does **not** bound `nonce_budget` or the scan. Not a live risk on CPU, but it is not a hard ceiling. |
| `HYBA_TARGET_SHARES = 2` | **Harness only.** `unified_treasury_workload.py:140` enforces 2. The production miner (`headless_miner.py:974`) defaults to `1000000` whenever `HYBA_MINING_CONTINUOUS=true` — which `_env_default` sets on by default. **The production miner never stops on shares.** |
| Non-consecutive share rule | **Correctly implemented, harness only.** `unified_treasury_workload.py:341` requires `cycle > last_share_cycle + 1`, and updates `last_share_cycle` on a rejected-for-consecutiveness share so the gap is measured from the most recent one. Counts `stratum.shares_accepted`, incremented **only on pool ACK** (`stratum_client.py:446`) — this is genuine pool-confirmed accounting. |
| `HYBA_MAX_RUNTIME_SECONDS = 600` | **Harness only.** `headless_miner.run()` has no runtime bound at all. |

All four controls live in the acceptance harness, none in the production loop.

---

## 10. Pool Evidence (brief point 11)

```
pool URL     btc.viabtc.io:3333        worker      PYTHIA.001 (authorized)
clean_jobs   true                      difficulty  16384.0
job IDs      45ce 45cf 45d0 45d1 45d2 45d3 45d4 45d5 45d6 45d7 45d8 45d9
target       000000000003fffc...       extranonce  assigned at subscribe
job age      fresh throughout; is_stale never triggered
submit_share() called    NO  (0 invocations — chain stops upstream)
pool response            none
POOL_CONFIRMED           NOT ESTABLISHED
```

Pool connectivity, subscription, authorisation, difficulty negotiation and job delivery **all work
correctly.** The pool side of the system is not the problem.

---

## 11. Git Investigation (brief point 12) — traced in code, not from messages

| Commit | Classification | Verdict |
|---|---|---|
| `f0e8b5f` Refactor stratum iGPU mining pipeline | **REGRESSION** | Introduced `_preempt_inflight_igpu` and the mis-scoped `clear()`. **This is the origin of zero execution.** |
| `91f5937` budget 512 → 250,000 | **REAL FIX, ineffective** | Correct and necessary. Downstream of a gate never passed, so it produced no measurable change. |
| `3c381f5` mathematical substrate fallback | **REAL FIX + telemetry** | Lets the miner construct at all and labels the backend honestly. Did not address the latch. |
| `b39e43a` merge | merge only | — |
| *uncommitted* `math_substrate_sha256d.py` (+6 stubs) | **SYMPTOM SUPPRESSION** | Silences an `AttributeError`; `cancel_and_flush` is a no-op that cannot cancel. Does not fix zero work. |
| *uncommitted* `headless_miner.py` (`default=str`) | benign | JSON serialisation guard. |

**No change since the zero-hash observation fixes the causal defect.** The current branch does
**not** contain a fix for it. No new execution regression was introduced.

---

## 12. Test Suite (brief point 13)

```
pytest tests/test_unified_treasury_workload.py tests/test_treasury_correctness.py \
       tests/test_phi_quantum_integration.py
   ->  12 passed, 1 failed in 25.30s
```

**FAILED** `test_phi_quantum_integration.py::test_intelligence_chooser_phi_override`
`assert 'supposition_override_S-f58eb1f6' == 'phi_resonance_override'` — the supposition layer now
outranks the φ-resonance override; the test still asserts the older precedence. **Test-spec drift,
not an execution defect.** Also logs the recurring
`Superposition creation failed: 'dict' object has no attribute 'create_superposition'`.

**Evidence classes:**

| Class | Result |
|---|---|
| SIMULATED / UNIT VERIFIED | 12/13 pass, including `test_1_end_to_end_execution` |
| LIVE / PHYSICAL OBSERVED | **ZERO_WORK_DETECTED** |

**`test_1_end_to_end_execution` passes while live throughput is zero.** The unit suite is blind to
this class of defect and must not be cited as mining evidence.

---

## 13. Verdict

### `BLOCKED — ZERO EXECUTION`

A real job reaches MINE and no SHA256d work occurs.

Against the readiness checklist:

| Criterion | Status |
|---|---|
| real pool connection | **PASS** |
| real job arrives | **PASS** |
| MINE receives the real job | **PASS** (761/761) |
| `scan()` executes | **FAIL — 0 invocations** |
| independent hash counter > 0 | **FAIL — 0** |
| internal accounting agrees | **PASS** (agrees at zero) |
| substrate identity truthful | **PASS** at `hash_backend`; **FAIL** at `hardware_verified` (3 sites) |
| validation works | **UNPROVEN** — never reached |
| share submission path works | **UNPROVEN** — never reached |
| Salamander detects zero throughput | **FAIL — invariant absent** |
| runtime / share / EH-s boundaries | **PARTIAL** — harness only, not production |

---

## 14. Smallest Causal Defect — for the next phase

Ranked. Only the first is required to answer *"does the counter move from zero?"*

1. **`headless_miner.py:609`** — move `self._active_mining_cancelled.clear()` out of the `try` and
   into a `finally`. **One line.** Cancellation is scoped to the *previous* in-flight scan, not to
   the cycle about to begin; the guards at L734/L767 still catch a preemption arriving *during* the
   cycle, which is all they were ever meant to catch.
2. **`headless_miner.py:320`** — stop re-raising inside the Stratum listen callback; record a fault.
3. **`unified_treasury_workload.py:264,187` + `mining_preflight()`** — read `_igpu_available`,
   not `_igpu`.
4. Add the throughput invariant + phase vocabulary; route it to Salamander via `error_count`.
5. Stop routing `state_mine()`'s candidate return into `found_nonce`.
6. Make `report["status"]` and `UNIFIED TREASURY ACCEPTANCE` **computed**, not literals
   (`build_report_shell` hardcodes `"PASS"`; the final print is unconditional).
7. Give `MathSubstrateSHA256D` a real cancellation primitive, or have `cancel_and_flush` state
   plainly that mathematical scans are not interruptible.

**Then re-run this same harness unchanged.** The verdict is computed from the counters; it cannot
be talked into `PASS`.

---

*Read-only verification. No production code modified. No job fabricated, no pool mocked, no nonce
injected, no counter forced.*
