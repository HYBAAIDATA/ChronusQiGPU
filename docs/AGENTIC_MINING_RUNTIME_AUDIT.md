# Agentic mining runtime — production control-plane audit

## Canonical execution graph

```text
pythia-mine / mining_runtime.main
→ configuration and pool endpoint policy
→ GeodesicProductionMiningCoordinator
→ Stratum connect / subscribe / authorize / notify
→ canonical WorkIdentity (pool session + generation + job fingerprint)
→ agentic SearchPlan and exclusive nonce lease
→ backend registry capability probe and declared-policy selection
→ ExecutionRouter
→ host SHA256d and target recheck
→ current-session/current-work submission gate
→ serialized mining.submit
→ literal pool acknowledgement
→ causal, session, telemetry and learning evidence
→ bounded measured optimisation or Salamander recovery
→ next leased window
```

`mining_runtime.py` is the production composition root. `GeodesicProductionMiningCoordinator` is the single owner of search, execution correlation and submission. Legacy and seam workflows are not production entry points.

## Ownership and role boundaries

| Role | Owner | Authority |
|---|---|---|
| Supervisor | production runtime + coordinator | lifecycle, signals, reconnect loop |
| Pool | canonical Stratum coordinator/client | transport, session, jobs, submission and acknowledgement |
| Planning | AgenticMiningController + chooser/Chronus adapters | SearchPlan, nonce leases, ordering and bounded routing advice |
| Execution | ExecutionRouter + capability-proven hasher | execute a leased window only |
| Verification | Stratum proof adapter + independent host checks | header, SHA256d, target and current-work validation |
| Recovery | RecoveryGovernor + Salamander agents | detect, isolate, bounded restart, verify or fault closed |
| Optimisation | ClosedLoopOptimizer | one-at-a-time measured trials; accept or rollback |

Agents exchange immutable identities, plans, leases, execution records and causal coordinates. Only the coordinator submits.

## Backend matrix

| Backend | PRESENT | WIRED | ACTIVE | TESTED | PRODUCTION-EVIDENCED | Limitation |
|---|---:|---:|---:|---:|---:|---|
| CPU | yes | yes | capability-dependent | registry unit tested; existing SHA256d tests | only when runtime evidence exists | reference throughput only |
| GPU/OpenCL | yes | yes | only after real bind/self-check | existing GPU suites plus registry rejection path | unavailable without a real device trace | explicit request fails closed; no CPU downgrade |
| Remote GPU | yes | yes | only with configured healthy endpoint | existing remote-hasher tests | unavailable without endpoint trace | explicit request fails closed |
| ASIC | named only | no | no | unavailable-path tested | no | no production transport implementation |
| SUPER ASIC | named only | no | no | unavailable-path tested | no | no production transport implementation |

The backend registry reports CPU/GPU/ASIC/SUPER_ASIC separately. Documentation or environment names do not make a backend available. `auto` follows `PYTHIA_BACKEND_ORDER`; an explicit lane never silently falls back.

## Pool workflow

| Phase | Status | Evidence boundary |
|---|---|---|
| connect / subscribe / authorize | WIRED | correlated Stratum responses |
| target / difficulty / notify | WIRED | adapter runtime state and immutable work identity |
| stale replacement | WIRED | identity refresh invalidates plans and freshness callback stops obsolete work |
| submit | WIRED, policy gated | proof adapter + chain/session/current-work + duplicate gates |
| acknowledge | WIRED | literal pool response only; disconnect after write is `OUTCOME_UNKNOWN` |
| reconnect / failover | WIRED | bounded exponential backoff over configured endpoints |

A connected socket alone is not an operational session. Submission remains unavailable until subscription, authorization, target, current job, valid extranonce/session identity and policy approval are all present.

## Healing and optimisation

```text
execution observation → classify → RecoveryGovernor proposal
→ isolate/freeze planning → bounded restart through configured factory
→ fresh health observation → return to service or FAULTED
```

```text
completed ExecutionRecord baseline → bounded candidate window
→ real useful-work/second measurements → threshold comparison
→ retain or rollback → cooldown and durable integrity-checked history
```

Trials do not restore in flight after restart. Job epochs, sessions, extranonce state and unverified shares are not durable recovery inputs.

## Component classification

| Component | Classification | Basis |
|---|---|---|
| Production entry point | PRESENT / WIRED / ACTIVE | `pythia-mine` → `mining_runtime.main` |
| AutonomousExecutionLoop under legacy papers | SUPERSEDED / DORMANT | legacy path, not production entry point |
| Stratum lifecycle | PRESENT / WIRED / TESTED | canonical coordinator and local-pool tests |
| Agentic planner and nonce leases | PRESENT / WIRED / ACTIVE / TESTED | plans affect real ExecutionRouter dispatch |
| Chronus/search ordering | PRESENT / WIRED | ordering/planning only; not a proof predicate |
| Local SHA256d verification | PRESENT / WIRED / ACTIVE / TESTED | proof adapter and host recheck |
| Duplicate submission protection | PRESENT / WIRED | MiningSession plus serialized submission lock |
| Salamander recovery | PRESENT / WIRED / PARTIAL | bridge and bridge-free recovery; real-device evidence environment-dependent |
| Closed-loop optimisation | PRESENT / WIRED / ACTIVE / TESTED | measured bounded trial controller |
| CPU backend | PRESENT / WIRED | capability probe and declared selection |
| GPU backend | PRESENT / WIRED / UNKNOWN at deployment | requires real device probe |
| ASIC / SUPER ASIC | DORMANT / NOT IMPLEMENTED | surfaced unavailable; never claimed active |
| CEO dashboard | UNKNOWN in this tranche | no access policy changed |

## Verification performed in this tranche

```text
PYTHONPATH=/data/PYTHIPhiMiner-direct python -m unittest -v tests.test_backend_registry
Ran 4 tests in 0.004s — OK

python -m py_compile \
  chronus/mla1517/mining/backend_registry.py \
  chronus/mla1517_platform/python/mining_runtime.py \
  tests/test_backend_registry.py
```

The focused tests prove declared-policy `auto` selection, explicit-GPU fail-closed behavior, unhealthy-backend rejection, durable decision evidence, and explicit unavailable ASIC/SUPER_ASIC states. Full repository CI and hardware/live-pool evidence remain separate acceptance gates.

## Remaining limitations and truthful final status

- **Software gaps:** no production ASIC or SUPER ASIC transport; full state-by-state timeout table remains distributed across existing contracts.
- **Unavailable backend:** availability depends on a successful runtime capability probe.
- **External infrastructure:** live credentials, pool availability, devices and chain observer are deployment inputs.
- **Discovered share:** none claimed by this change.
- **Live-pool evidence:** none newly generated by this change.

| Capability | Status |
|---|---|
| AGENTIC CONTROL | ACTIVE in canonical coordinator |
| AUTOMATED MINING | ACTIVE when a configured pool and capability-proven backend are present |
| POOL WORKFLOW | ACTIVE in code; deployment evidence external |
| EXECUTION FABRIC | PARTIAL — CPU/GPU/remote implemented, ASIC lanes unavailable |
| SHARE VERIFICATION | ACTIVE |
| SHARE SUBMISSION | ACTIVE only when explicitly enabled and all gates pass |
| SELF-HEALING | PARTIAL — recovery is wired, device-specific proof required |
| SELF-OPTIMISATION | ACTIVE for bounded window trials |
| PRODUCTION-EVIDENCED | PARTIAL |
