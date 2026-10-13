# HYBA — Phase 2: Restore and Prove Real Mining Execution

**Result: `ZERO_WORK_DETECTED` → `LIVE_MINING_OBSERVED`**

**27,750,000 SHA256d hashes independently measured against 19 real ViaBTC jobs.**
Independent counter and miner bookkeeping agree exactly, on all 111 cycles.

---

## 1. Root cause fixed

`headless_miner.py` — `state_mine()` cleared `_active_mining_cancelled` **inside** a `try`
guarded by `next_job(timeout=0.05)`. `_preempt_inflight_igpu()` calls `drain_jobs()` before that,
which **guarantees** the timeout. So the first `clean_jobs` notification set the flag and nothing
ever cleared it; every later cycle returned before `mine_job()`.

```python
        except Exception:
            current_job = self._active_job
        finally:
            self._active_mining_cancelled.clear()   # <- moved here
```

The guard itself was **not** removed. Clean-job handling was **not** disabled. No job was
fabricated, no nonce injected, no counter forced. The flag now means what its name says: cancel
the *previous, in-flight* scan — not the next cycle.

---

## 2. Files changed

| File | Change |
|---|---|
| `python_backend/headless_miner.py` | **latch fix** (`finally`); preemption no longer re-raises inside the Stratum callback; `_igpu` → `_igpu_available` at 3 sites; mining phase vocabulary + `_set_mining_phase` + `_record_work_outcome` invariant + `_publish_mine_outcome`; phase/fault in `_save_stats` and the shutdown dump |
| `python_backend/accel/math_substrate_sha256d.py` | **real cancellation** (`threading.Event` polled every 4096 nonces) replacing `pass`; `hardware_verified=False` / `mathematical_execution=True` class facts; lifecycle signatures aligned to `CustomIGPUSHA256D`; `_bind_symbols` raises instead of implying a bind |
| `python_backend/unified_treasury_workload.py` | **verdict computed, not asserted** (`"PASS"` literal → measured status); `hardware_verified` from `_igpu_available`; `found_nonce` from the real outcome, `candidate_nonce` separated; `report["bitcoin"]` populated; dead `hash_backend == "cpu"` comparison fixed |
| `python_backend/hyba/salamander/veritas_ledger.py` | **atomic write** — see §10 |
| `python_backend/tests/unit/test_mining_cancellation_latch.py` | **NEW** — 13 regression tests |
| `python_backend/tests/test_unified_treasury_workload.py` | stale `status == "PASS"` specs → computed verdict + consistency; mocks completed |
| `python_backend/tests/test_phi_quantum_integration.py` | override precedence updated (§9) |
| `scripts/live_mining_trace.py` | the harness — **unmodified since Phase 1** |

Not touched: predictive, causal, counterfactual, topological, geometric, quantum, entanglement,
supposition, φ/Lucas, folding, Salamander, Veritas. **No intelligence was replaced with a
hard-coded mining loop.** The full chain still runs — the intelligence decision now *reaches* the
substrate instead of dying one line above it.

---

## 3. Tests run

```
pytest tests/unit tests/test_unified_treasury_workload.py \
       tests/test_treasury_correctness.py tests/test_phi_quantum_integration.py
   ->  182 passed, 2 skipped, 0 failed
```

New regression suite (`test_mining_cancellation_latch.py`) — **13/13**, covering the exact
lifecycle the live suite missed:

- the historical defect is still *reproducible* by the harness (guards the guard)
- clean job → preemption → drain/timeout → next cycle → flag cleared → `scan()` runs
- 1000 consecutive cycles never re-latch
- **AST assertion against the production source** that the clear lives in a `finally`
- real double-SHA256 vs independent `hashlib`
- `cancel_and_flush()` genuinely aborts an in-flight scan **from another thread**
- a *stale* cancel must **not** leak into the next scan (the same scoping error, one level down)
- 761 zero-work cycles ⇒ `MINING_ZERO_THROUGHPUT` + `error_count` moves
- no job ⇒ `WAITING_FOR_JOB`, **not** a fault
- a candidate nonce can never populate `found_nonce`

Excluded: `tests/unit/test_benchmark_provenance.py` — pre-existing collection error
(`ImportError: cannot import name 'HYBAInfrastructure'`), unrelated and untouched.

---

## 4. Live harness result — `scripts/live_mining_trace.py --wait 120 --observe 180`

Harness, verdict logic and counters **unchanged from Phase 1**. No mocked job, no injected nonce.

| Field | Before | **After** |
|---|---|---|
| `classification` | `ZERO_WORK_DETECTED` | **`LIVE_MINING_OBSERVED`** |
| pool connected | true | **true** — `btc.viabtc.io:3333`, `PYTHIA.001` |
| jobs seen | 12 | **19** (`46e3`…`46f5`) |
| MINE entries | 761 | **111** |
| MINE entries with job | 761 | **111** |
| **MINE with job + zero work** | **761** | **0** |
| scan invocations | 0 | **3,552** (32/cycle — the 32 Hilbert sections) |
| nonces requested | 0 | **27,750,000** |
| **hashes attempted** | **0** | **27,750,000** |
| miner-claimed hashes | 0 | **27,750,000** |
| effective hashrate | 0 H/s | **181,384 H/s** |
| planned substrate | igpu | igpu |
| actual substrate | `math_substrate_sha256d` | `math_substrate_sha256d` |
| substrate backends observed | `{}` | `{"math_substrate_sha256d": 3552}` |
| hardware verified | false | **false** |
| local validations | 0 | 0 |
| shares submitted / accepted / rejected | 0/0/0 | 0/0/0 |
| **cancel flag set** | **true on 761/761** | **false on 111/111** |

Requested budget 250,000/cycle; **delivered exactly 250,000 on 111 of 111 cycles.** The
`HYBA_MINE_NONCES_PER_CYCLE` budget reaches the real SHA256d loop for the first time.

---

## 5–6. Independent vs internal hashes

```
independent wrapped scan() counter : 27,750,000
miner.total_sha256d_hashes         : 27,750,000
per-cycle agreement                : 111 / 111   exact
```

**Classification: A — CONSISTENT.** No accounting boundary needed; they are equal.

`total_sha256d_hashes` still has exactly one writer, still fed only by `scan()`. Nothing from
quantum operations, candidate regions, φ scoring, suppositions, entanglement, expected utility,
represented nonce space or theoretical search reduction touches it. All six quantities remain
independently measurable in the JSON.

---

## 7–8. Substrate and hardware verification

```
planned_substrate     igpu
actual_substrate      math_substrate_sha256d
hardware_verified     false
mathematical_execution true
```

Coherent, and unchanged in meaning: `hash_backend` semantics were not altered. The native runtime
is absent (`HYBA_CUSTOM_IGPU_SHA256D_LIB` unset), so the mathematical fallback executes and says so.

One consequence worth flagging: correcting `hardware_igpu_available` to read `_igpu_available`
propagated into the decision layer. The intelligence reason moved from
`agent_policy_execution_igpu` to `agent_policy_execution_cpu` — **the chooser was previously
planning for hardware that does not exist**, because it was fed the same always-truthy `_igpu`.

---

## 9. Validation / share result

`local_validations = 0`, `shares_accepted = 0`. **This is the expected result, not a shortfall.**

At difficulty 16384, expected hashes per share = 16384 × 2³² ≈ **7.04 × 10¹³**.
This run performed 2.775 × 10⁷ — a factor of ~2.5 million short.

> P(at least one share) = 1 − e^(−H/E) ≈ **3.9 × 10⁻⁷**

At 181 kH/s a share is expected roughly every **107,765 hours**. Observing none is the correct
outcome; manufacturing one would have been the only way to reach `POOL_CONFIRMED`, and that was
not done.

Per your §11, the transition that matters for this phase — `ZERO_WORK_DETECTED` →
`LIVE_MINING_OBSERVED` — **has occurred.** `POOL_CONFIRMED` remains unearned and unclaimed.

---

## 10. Remaining blockers and open items

**Found and fixed during this phase — the Veritas ledger was not crash-safe.**
`_persist` used `open(path, "wb")` then `pickle.dump`. `open(...,"wb")` truncates to zero
*before* the dump completes, so any reader in that window gets `EOFError: Ran out of input`.
The race was latent while the miner did no work. **Once mining began, `record_action` fired every
cycle and the window was hit reliably**, surfacing as an intermittent `LedgerLoadError`. Now
temp-file + `fsync` + `os.replace` (atomic on Windows and POSIX). A crash mid-write leaves the
previous ledger intact instead of an empty file. This is the audit trail; it should not have been
one interrupted write away from destruction.

Open, **not** blocking Phase 2 acceptance:

1. **`create_superposition` fails every cycle** — `'dict' object has no attribute
   'create_superposition'` (`quantum_enhancements.py:156`). The supposition layer degrades
   silently. Real intelligence capability currently unavailable.
2. **`SubstrateType.SIMULATOR unavailable → degrading to CPU`** every cycle, logged as a warning
   and otherwise unhandled.
3. **Policy boundaries live only in the acceptance harness.** `HYBA_MAX_EHS` is advisory (it
   clamps the intelligence *recommendation*, not the scan). `HYBA_MAX_RUNTIME_SECONDS` and the
   2-share stop are enforced in `unified_treasury_workload.py`; `headless_miner.run()` has neither,
   and defaults `HYBA_TARGET_SHARES` to 1,000,000 under `HYBA_MINING_CONTINUOUS=true`.
   **The production miner does not stop on shares or on time.**
4. **`tests/unit/test_benchmark_provenance.py`** — pre-existing import error.
5. No physical iGPU substrate is configured, so `hardware_verified` cannot become true on this
   host. Nothing claims otherwise.

---

## 11. Git status

```
 M python_backend/accel/math_substrate_sha256d.py      |  70 ++-
 M python_backend/headless_miner.py                    | 186 +++++-
 M python_backend/hyba/salamander/veritas_ledger.py    |  19 +-
 M python_backend/tests/test_phi_quantum_integration.py|  14 +-
 M python_backend/tests/test_unified_treasury_workload.py| 85 ++-
 M python_backend/unified_treasury_workload.py         | 113 ++-
?? python_backend/tests/unit/test_mining_cancellation_latch.py
?? scripts/live_mining_trace.py
```

Also modified in the working tree but **not by this phase** (pre-existing, untouched):
`python_backend/main.py`, `python_backend/hyba/security/__init__.py`,
`python_backend/artifacts/test_ledger_valid.phi`, `python_backend/treasury_agent_qtable.json`,
`Dockerfile.prod`, `package.json`, `Landing_Page/*`.

Nothing has been committed. The tree is staged for your review.

---

## What the evidence establishes — and what it does not

**Establishes:** a real ViaBTC job reaches MINE and causes real, independently measured SHA256d
execution on the mathematical substrate, at 181 kH/s, with the miner's internal accounting exactly
matching an external counter it cannot write to, and with the configured 250,000-nonce budget
honoured on every cycle.

**Does not establish:** that a share is obtainable at this hashrate; that any iGPU hardware
executed anything; that quantum execution occurred; that the pool has confirmed anything. None of
those are claimed.

**Stopping here** per instruction. No Docker, no frontend integration, no `.env` production
configuration, no continuous autonomous mining, no extended live run.
