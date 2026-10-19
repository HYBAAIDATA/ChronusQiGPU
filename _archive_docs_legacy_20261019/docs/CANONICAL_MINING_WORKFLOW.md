# Canonical PYTHIA Mining Workflow

## Status

This document defines the production mining composition in `QuantumPhi2/PhiMiner`.
It is an authority and wiring contract, not a performance claim. Runtime state,
physical execution, pool acceptance, and hashrate remain evidence-bound.

## Authorities

| Responsibility | Canonical owner | Boundary |
| --- | --- | --- |
| Mining composition, predictive/causal mining intelligence, search topology | **PYTHIA** | Directs mining work; never substitutes for Bitcoin proof |
| Enterprise intelligence orchestration | **EUCLID** | Wider orchestration/advice; not the mining identity |
| Exact 600-position Hilbert traversal/ranking | **Turing** | Search-order mathematics only; not SHA256d proof |
| Physical execution | **Chronus** | Executes the exact nonce batches authorised by PYTHIA |
| Healing and bounded optimisation | **Salamander** | Detect, recover, reprobe, retain/rollback; never proof authority |
| Work identity, SHA256d, negotiated target, freshness | **Stratum proof boundary** | Sole local Bitcoin proof authority |
| Share acceptance/rejection | **Pool response** | Literal `mining.submit` response only |

Chronus is its own execution architecture. CUDA, OpenCL, Metal, remote GPU,
ASIC, and composite transports may appear only as capability-proven physical
adapters beneath the Chronus execution contract. They do not define Chronus,
its search model, its scheduler, or its authority.

## Search structure used by Hendrix

The supporting structured-search substrate is prepared before pool work begins and is consumed by the default Hendrix traversal:

```text
dodecahedron / icosahedron dual overlay
        ↓
32 coarse search directions
        ↓
phi-weighted 11D Poincaré manifold
        ↓
H4 600-cell / dual 120-cell construction
        ↓
600 high-resolution logical search vertices
        ↓
Turing exact 600-position Hilbert traversal
        ↓
coverage-preserving nonce shards / Cassini schedules
```

The 600 vertices are **logical search-work vertices**, not a claim that 600
physical devices exist. Physical execution capacity may be one device or a
fleet; telemetry must report what actually executed.

The search architecture may rank or reorder a complete nonce lease. It may not
remove nonce coverage, replace SHA256d, replace the negotiated target, or infer
pool acceptance.

## End-to-end production path

```text
configured allowlisted pool
  → TCP/TLS Stratum connection
  → mining.subscribe
  → mining.authorize
  → mining.set_target / mining.set_difficulty
  → mining.notify
  → immutable WorkIdentity
       (pool session + generation + job fingerprint)
  → AgenticMiningController
  → exclusive generation-scoped nonce lease
  → PYTHIA canonical 600-vertex / 11D / Hilbert itinerary
  → Chronus physical execution contract
  → measured ExecutionRecord
  → independent host SHA256d + target recheck
  → stale / epoch recheck
  → submission approval bound to current endpoint + worker
  → serialized mining.submit
  → literal pool boolean acknowledgement
  → durable causal/evidence surfaces
  → operator API
  → frontend evidence projection
  → next cycle
```

## Agentic workflow

`AgenticMiningController` owns bounded precomputation and exclusive nonce
leases. It does not own work identity or proof.

A plan is valid only for the exact live Stratum session, generation, and job
fingerprint for which it was created. Clean jobs and identity changes
invalidate queued work. Leases are disjoint and generation-scoped.

The production composition root binds every plan to the canonical PYTHIA
search architecture and its startup precompute digest before execution.

## Chronus sustained execution contract

Chronus receives only authorised work. Its production responsibilities are:

- consume the exact ordered nonce batch selected by PYTHIA;
- execute on a capability-proven physical adapter or fail closed;
- preserve the nonce membership and lease boundaries supplied by PYTHIA;
- report the physical backend and device separately from the Hendrix search identity;
- report measured launch/work evidence rather than device-presence claims;
- allow stale identity to cancel further batch execution;
- participate in Salamander reprobe/restart without inventing successful recovery;
- expose enough evidence for aggregate hashrate to be computed from completed work and measured wall time.

Vendor/runtime route names that remain in lower-level compatibility code are
adapter details only. Operator-facing architecture must preserve the explicit
`PYTHIA → Chronus → SHA256d/Stratum` authority chain.

## Proof and submission boundary

A candidate can reach the pool only when all of the following are true:

1. it came from the currently leased work identity;
2. its returned nonce/digest is independently rechecked on the host;
3. its SHA256d satisfies the currently negotiated share target;
4. the work identity is still current after execution;
5. live submission is explicitly enabled and bound to the connected pool endpoint and worker;
6. the candidate has not already been submitted;
7. `mining.submit` is serialized through the single coordinator writer.

An exception after the network write does **not** become rejection or
acceptance. It remains outcome-unknown unless a literal response was received.

## Evidence states

The evidence boundary is deliberately stronger than status labels:

- **SOFTWARE_VERIFIED** — software contract executed; no physical-device claim.
- **DEVICE_AVAILABLE** — capability exists; presence is not execution.
- **HARDWARE_EXECUTED** — measured physical launch and completed work exist.
- **POOL_CONFIRMED** — a literal accepted pool acknowledgement exists.

Rejected, stale, shadow, unavailable, or unknown states may never be promoted
into a stronger class.

The frontend must show unavailable values as unavailable. It must not convert
configured topology, targets, device presence, or historical measurements into
current runtime evidence.

## Salamander closed loop

For mining, Salamander surrounds execution rather than replacing it:

```text
observe measured execution / device state
  → detect fault, degradation, stale work, queue pressure
  → diagnose and propose bounded action
  → RecoveryGovernor authorises the action
  → apply restart / reprobe / throttle / other permitted repair
  → observe the next real execution
  → retain the change only when measured recovery evidence supports it
  → otherwise fail closed / rollback
```

Recovery state and recovery effects are part of mining evidence. A log message
saying `HEALTHY` is not sufficient evidence by itself.

## Deployment acceptance gates

Before classifying this workflow as production-verified, execute at least:

```bash
pytest -q tests/test_native_production_routing.py
pytest -q chronus/mla1517_platform/python/test_canonical_mining_workflow_e2e.py
pytest -q chronus/mla1517_platform/python/test_agentic_voyages.py
pytest -q chronus/mla1517_platform/python/test_live_submission.py
pytest -q chronus/mla1517_platform/python/test_pool_only_mining.py
pytest -q chronus/mla1517_platform/python/test_execution_loop.py
npm --prefix frontend test -- --run
```

Then run the existing production Chronus/mining repository gates and, where a
physical Chronus substrate is bound, collect physical execution evidence.
Live-pool classification additionally requires an authorised live pool run and
literal pool acknowledgement. CI jobs that never receive a runner or execute
zero steps are **not** passing evidence.
