<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:7dc6cf3e7515e70a14a0256cfb47b08430f82fa5d0b1b82dec1e2a1fbf95bd4e -->

# The Octopus — head, 600 solvers, and the LPV sweep

Deliverable package **A (wiring diagram) + B (interface contracts) + component ledger**.
This is the starting point for `dispatch` (C), the `LPV` sweep harness (D), the 600-admission test (E), and the end-to-end octopus test (F). Nothing is added to C or D until A and B are reviewed.

It is a **no-fabrication** document: every named component is marked `EXISTS` (pointed at its live module) or `REFUSING STUB` (with the explicit refusal it will answer with). Nothing is silently described as implemented.

---

## 0. Component-existence ledger (live tree `chronus-quantum-igpu`)

A component is `EXISTS` only if a live `.py` module(s) is present and importable, or is a storage/substrate layer confirmed by tests. A component is `STUB` if the required capability is not present; it must answer `REFUSED — not implemented`.

| # | Component (as named) | Solver class? | Live location | EXISTS / STUB | Notes |
|---|----------------------|---------------|---------------|---------------|-------|
| 1 | **HENDRIX** | YES — `structured-search` | `src/chronus/hendrix/` (`galois.py`, `oracles.py`, `structured.py`) | **EXISTS** | Exact finite-field structured search; exact lookup backend. |
| 2 | **O(1) GALOIS** | YES — `exact-search` | — | **STUB** | Exact search with a one-off table build cost / per-query cost / break-even table size is **not** present in the live tree. Refuse jobs with `REFUSED — not implemented (O(1) GALOIS exact-search)`. |
| 3 | **RIEMANN** | YES — `riemann` | — | **STUB** | Riemann capability is not defined in the live code. Refuse jobs with `REFUSED — not implemented (RIEMANN)`. |
| 4 | **Seven Millennium constructions (AL HARAS)** | YES — seven solver classes | `src/chronus/security/al_haras/` (`millennium_security.py`, `millennium_unification.py`, …) | **EXISTS (wire as 7 instances)** | Millennium modules exist; each becomes one solver instance, each with its own self-test and receipt. |
| 5 | **Quantum library** | YES — `quantum-math` | `src/chronus/quantum/` (`ring_codec.py`, `subspace.py`, `entanglement.py`, …) | **EXISTS (partial)** | Some entry points exist. The following are **not** in the live tree and must be `REFUSED — not implemented`: noise/decay, partial trace, circuit format, gate scheduler, checkpoint/replay. |
| 6 | **Folded store (Cassini/Fibonacci rimes; THESEUS + OVID)** | NOT a solver — head storage layer | `src/chronus/storage/` (`theseus.py`, `phyllotaxis.py`), `src/chronus/security/ovid.py` | **EXISTS (storage)** | Data folded once, stored folded, searched folded, unfolded only at the boundary. |
| 7 | **LPV** | Not a solver — scaling parameter object | `src/chronus/backends/` (`lattice_workload.py`, `opencl_pv.py`), `src/chronus/config.py` (`max_pv_order=360`, `max_lucas_index=100000`) | **EXISTS (parameter)** | `lucas_order` and `pv_degree` are the sweep coordinates. |
| 8 | **Capacity (five numbers)** | Not a solver — head metric log | head-managed; config bounds source | **HEAD-MANAGED** | `theoretical_peak`, `discovered`, `available`, `allocated`, `measured`. Measured rate replaces fixed peak. No fixed peak assumed. |
| 9 | **iGPU fleet + lane module** | Solver execution substrate | `src/chronus/igpu/` (`tensor.py`, `__init__.py`) | **EXISTS (substrate)** | Lanes self-validate against host reference before use (per stated code). |



## A. Wiring diagram (head → classes → instances → storage → substrate)

```
                        +----------------------------------------------------------+
                        |                     THE HEAD (one process)                  |
                        |   classify job  ->  fan-out  ->  agreement  ->  receipt    |
                        |   no mathematics of its own; routes only                    |
                        +----------------------------------------------------------+
                                     |  classify(name)
                                     |  fan-out(lucas_order, pv_degree)
                                     v
  +------------------+      +------------------+      +------------------+      +------------------+
  | HENDRIX          |      | O(1) GALOIS      |      | RIEMANN          |      | MILLENNIUM x7     |
  | (structured-     |      | (exact-search)   |      | (riemann)        |      | (seven classes)   |
  | search)          |      | exact-lookup     |      | refusing stub    |      | seven instances   |
  | instances        |      | instances        |      | "not implemented"  |      | self-test + receipt |
  +----+-------------+      +--------+---------+      +--------+---------+      +--------+---------+
       | run                         ^ run                         ^ run                    ^ run
       |                             |                             |                        |
       v                             v                             v                        v
  +----+-------------+          +----+----------+          +----------+          +----------+-----+
  |  O(1) GALOIS    |<----------|  O(1) GALOIS  |<----------|  RIEMANN |----------|  MILLENNIUM |
  |  structured     |(exact-     |  lookup       |          |  stub    |          |  x7         |
  |  search         |  lookup)   |  backend      |          |          |          |             |
  +----------------+          +-------------+---+          +----------+          +------------+
  ^         ^                      |  ^                      |  ^                      |
  |         |                      |  |                      |  |                      |
  |  exact  |                      |  |                      |  |                      |
  |  lookup |                      |  |                      |  |                      |
  |  backend|                      |  |                      |  |                      |
  |  (hendrix) |                     |  |                      |  |                      |
  +----------+                     |  |                      |  |                      |
                                   |  |                      |  |                      |
                                   v  v                      v  v                      v
  +---------------------------------------------------------------+
  |                   THE FOLDED STORE (head's storage layer)     |
  |   THESEUS (prime-codec / golden-ratio lanes)                  |
  |   + OVID (content-addressed, Ed25519 receipts)                |
  |   Data: fold once -> store folded -> search folded            |
  |   -> unfold only at the boundary.                             |
  +---------------------------------------------------------------+
                                     |
                                     v
  +----------------------------------------------------------+
  |                   EXECUTION SUBSTRATE                     |
  |   iGPU fleet (heterogeneous workers, lanes)              |
  |   self-validate lanes against host reference             |
  |   LPV-scaled route: lucas_order, pv_degree               |
  +----------------------------------------------------------+
```

**Legend (every arrow labelled with the interface it uses):**



## B. Interface contracts per solver class

Every contract is a schema on: `input`, `output`, `refusal`, and `receipt`. They are **interfaces only** — they define shape, not meaning.

### B.1 Common envelope (used by all solvers)

```
input = {
  "job_type":      str,                 # e.g. "structured_search"
  "payload":       object,              # class-specific
  "lucas_order":   int | None,          # LPV sweep coordinate
  "pv_degree":     int | None,          # LPV sweep coordinate
  "input_digest":  str,                 # sha256 of B.1 envelope fields except input_digest
  "solver_id":     str,                 # chosen by the head / client
}
```

For this proposed interface, `input_digest` is the lowercase hexadecimal SHA-256
of the UTF-8 bytes of RFC 8785 (JCS) canonical JSON for exactly
`job_type`, `payload`, `lucas_order`, `pv_degree`, and `solver_id`.
`input_digest` itself is excluded. Include both sweep coordinates, using JSON
`null` when absent. Payloads must be representable as I-JSON/JCS values;
non-JSON objects and non-finite numbers require a separately specified adapter.
This specifies the interface encoding; it does not assert that current solver
implementations already construct or verify this envelope.

```
receipt = {
  "solver_id": str,
  "job_type": str,
  "lucas_order": int,
  "pv_degree": int,
  "capacity": {
     "theoretical_peak": ...,
     "discovered": ...,
     "available": ...,
     "allocated": ...,
     "measured": ...,          # measured rate replaces any fixed peak
  },
  "result_digest": str,        # sha256 of the returned result bytes
  "input_digest": str,
  "duration_ms": float,
  "status": "AGREED" | "DISAGREEMENT" | "REFUSED",
  "signature": str,            # Ed25519 / HMAC over the above fields; named "signed receipt"
}
```

```
refusal = {
  "refused": True,
  "solver_id": str,
  "job_type": str,
  "reason": "not implemented" | "bound exceeded",
  "message": "<explicit refusal text, e.g. 'RIEMANN not implemented; refusing jobs of type riemann'>",
}
```

`not implemented` identifies an unavailable implementation. `bound exceeded`
identifies a field or domain outside the responding solver's declared bounds.

### B.2 HENDRIX — class `structured-search`

```
input = B.1 common envelope with job_type="structured_search" and
  payload={"query": ..., "field": ..., "domain_size": int}
output = {
  "solver_id": str,
  "job_type": "structured_search",
  "lucas_order": int,
  "pv_degree": int,
  "result": object,              # exact finite-field structured-search result
  "result_digest": str,
  "duration_ms": float,
  "status": "AGREED" | "DISAGREEMENT",
  "receipt": receipt,
}
refusal = refusal schema (B.1), reason="bound exceeded" for bound violations. Able to refuse if field/domain exceeds a declared bound (Hendrix refuses fields above 2^20).
```

### B.3 O(1) GALOIS — class `exact-search`

```
input = B.1 common envelope with job_type="exact_search" and
  payload={"table_key": ...}
output = {
  "solver_id": str,
  "job_type": "exact_search",
  "lucas_order": int,
  "pv_degree": int,
  "result": object,
  "result_digest": str,
  "duration_ms": float,
  "status": "AGREED" | "DISAGREEMENT",
  "report": {
     "one_off_table_build_cost_ms": float,
     "per_query_cost_ms": float,
     "table_size_at_which_O1_breaks": int | None,   # empirical, measured by harness D
  },
  "receipt": receipt,
}
refusal = refusal schema. This class is a STUB today; it must answer:
  {"refused": true, "solver_id": "<responding solver_id from input>", "job_type": "exact_search", "reason": "not implemented", "message": "O(1) GALOIS exact-search not implemented; refusing"}
```

### B.4 RIEMANN — class `riemann`

```
input = B.1 common envelope with job_type="riemann" and payload={...}
output = {}                      # only if it were implemented
refusal = {
  "refused": True,
  "solver_id": "<id>",
  "job_type": "riemann",
  "reason": "not implemented",
  "message": "RIEMANN not implemented; refusing jobs of type riemann",
}
```

### B.5 Millennium — seven solver classes

```
input = B.1 common envelope with job_type="<one of the seven Millennium problems>"
  and payload={...}
output = {
  "solver_id": str,
  "job_type": "<problem_name>",
  "lucas_order": int,
  "pv_degree": int,
  "result": object,              # problem-specific (e.g. verifiable invariant object)
  "result_digest": str,
  "duration_ms": float,
  "status": "AGREED" | "DISAGREEMENT",
  "receipt": receipt,
}
refusal = refusal schema; each of the seven classes must self-test on a known case before admission.
```

All class inputs extend B.1: `solver_id` and `input_digest` are required,
and `lucas_order` and `pv_degree` remain at the top level. Only the
class-specific payload fields and job type differ.

## Arrow contracts

| Arrow | Interface / contract |
|-------|----------------------|
| HEAD → HENDRIX | `run(job, lpv)`: classifies by `workload_type="structured_search"`; HENDRIX returns `(result, receipt)` |
| HEAD → O(1) GALOIS | `run(job, lpv)`: `workload_type="exact_search"`; if not implemented → `REFUSED — not implemented (O(1) GALOIS)` |
| HEAD → RIEMANN | `run(job, lpv)`: `workload_type="riemann"` → `REFUSED — not implemented (RIEMANN)` |
| HEAD → Millennium×7 | `run(job, lpv)`: `workload_type` = one of the seven Millennium problems; each returns `(result, receipt)` or refusal |
| HENDRIX → O(1) GALOIS | exact-lookup backend interface: O(1) GALOIS is currently a refusing STUB; HENDRIX's oracle table is built locally by `PrimeField` in `chronus.hendrix.galois`; the interface output is a digest-verified lookup result |
| Storage → ALL | `fold(payload) -> folded_sha256` ; `store(object_id, folded) -> receipt` ; `retrieve(object_id) -> folded bytes` (THESEUS + OVID) |
| Head → Storage | `store(result, lpv, capacity)` before returning any final output |
| Storage → Substrate | data persists folded in THESEUS/OVID; the substrate does not read another solver's state |
| iGPU fleet → HEAD | `probe_silicon()` / self-validation report; then the head may fan LPV-scanned work to lanes |
| HEAD → iGPU | job is fan-out eligible only after the head's classification and the substrate's self-validation |

**Class authority rule** (per job type): no single solver word is final unless that solver class declares itself authoritative for that job type. Unimplemented classes are refusing stubs and have no authority.


<!-- /coderabbit-ai-generated:v1 -->