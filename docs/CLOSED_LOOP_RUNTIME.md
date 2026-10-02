# Production healing and optimisation control loop

## Canonical execution graph

```text
mining_runtime._main_async
  -> GeodesicProductionMiningCoordinator / IntelligentPoolCoordinator
  -> Stratum + ExecutionRouter produces measured ExecutionRecord
  -> Salamander observation
       -> SelfHealingAgent (diagnosis/proposal, MMIO path)
       -> RecoveryGovernor (single recovery authority)
       -> MMIOControlSink or execution-device factory (actuation)
       -> fresh ExecutionRecord / telemetry observation (verification)
       -> KnowledgeFabric + CausalLedger + RecoveryEffects (retention)
  -> MiningWorldModel records completed measured work
  -> OperatingPolicy proposes bounded window/lookahead
  -> ClosedLoopOptimizer authorises one trial at a time
       -> ExecutionRouter runs the candidate without changing SHA256d truth
       -> completed useful-work/s is compared with the measured baseline
       -> accept candidate or restore baseline
       -> cooldown, attempt limit, durable state and telemetry
  -> continue
```

SHA256d verification, target truth, Stratum job identity, and literal pool
acknowledgement remain outside both controllers.

## Source inventory and status

| Component | Status | Evidence and role |
| --- | --- | --- |
| `mining_runtime.py` | WIRED, ACTIVE | Canonical production startup constructs the production coordinator, evidence/metrics sinks, durable state path, and bridge-free or MMIO loop. |
| `IntelligentPoolCoordinator` | WIRED, ACTIVE | Owns event-driven precompute, execution, outcome, healing, measurement and persistence hooks. |
| `SelfHealingAgent` | PRESENT, WIRED, ACTIVE on MMIO observations | Classifies stale jobs, hang risk, Cassini rejection and queue pressure into ordered proposals. It does not actuate. |
| `RecoveryGovernor` | WIRED, ACTIVE, TESTED | Single writer lifecycle: proposed, dispatched/deferred, acknowledged, verified or failed. Repeated unhealthy observations become `FAULTED`. |
| `SalamanderEngine` | PRESENT, WIRED for deployed MMIO service, INFRASTRUCTURE-DEPENDENT | Uses native telemetry and acknowledged CSR commits for lane retirement/readmission, mask trials and pool failover. Requires MLA1517 MMIO/telemetry. |
| Bridge-free device recovery | WIRED, ACTIVE | `ExecutionRecord.DEVICE_ERROR` opens `RESTART_LANE`; a configured hasher factory rebuilds/self-checks the device; a later healthy execution verifies recovery. Missing/failing factories fail closed. |
| Pool reconnect/failover | WIRED, ACTIVE | `ProductionMiningCoordinator` stops work on disconnect, closes the session, tries configured endpoints and applies bounded backoff. |
| Stale-work handling | WIRED, ACTIVE | Work identity changes drain plans/leases; in-flight routing checks freshness between chunks. |
| `MiningWorldModel` | WIRED, ACTIVE | Learns measured execution elapsed time, route throughput, invalidation rate and plan latency. |
| `OperatingPolicy` | WIRED, ACTIVE | Proposes window/lookahead only from measured evidence; missing evidence stays legacy/probe. |
| `ClosedLoopOptimizer` | WIRED by this change | Turns proposals into baseline/candidate trials, accepts measured gains, rolls back regressions/faults, persists results, and applies cooldown/attempt limits. |
| `TuningGate` / `SelfOptimizingTuner` | PRESENT, PARTIALLY WIRED | Thermal de-rate remains an immediate safety action. Scale-up recommendations no longer bypass the bounded-trial authority. |
| `ExecutionRouter` | WIRED, ACTIVE | Sole physical route authority; independent host rehash preserves consensus truth and exposes device faults. |
| `RecoveryEffects` | WIRED, ACTIVE when enough windows exist | Measures pre/post recovery hashrate; reports unmeasured when history is insufficient. |
| `IntelligenceMemory`, `KnowledgeFabric`, `CausalLedger` | WIRED | Retain world state, recovery outcomes and causal event evidence. |
| `autonomous_supervisor.py` | PRESENT, DUPLICATED AUTHORITY | Separate control-API worker/CUOP supervisor. It has active API callers, so it was not deleted. It does not own mining window trials after this change. |
| `Intelligence/self_healing/*` | PRESENT; mixed WIRED/DORMANT | Control-plane services and older general-purpose implementations. They are not treated as evidence that the mining loop acted. |
| legacy healing/resilience modules | SUPERSEDED | Kept under `legacy/`; not part of the production graph. |

## Autonomy boundaries

| Class | Current actions |
| --- | --- |
| `SAFE_AUTOMATIC` | reconnect configured pool, stop stale work, verified device restart, restore baseline after failed trial, thermal de-rate |
| `BOUNDED_EXPERIMENT` | one window-size trial with measured baseline/candidate windows |
| `REQUIRES_APPROVAL` | enabling live submission, adding endpoints/backends, changing credentials or hard resource bounds |
| `FORBIDDEN` | altering SHA256d, target/share validity, fabricating pool outcomes, unverified pruning, silent irreversible mutation |

## Healing matrix

| Failure | Detection | Action | Verification | Escalation |
| --- | --- | --- | --- | --- |
| Stale/new job | Stratum generation/fingerprint | invalidate leases, sever/flush MMIO lane | fresh identity and healthy observation | admission remains closed |
| Pool disconnect | client reader/writer/submit failure | stop bridge; close and reconnect/fail over | authorised connected client and resumed execution | bounded exponential retry |
| Device/accelerator error | `ExecutionRecord.DEVICE_ERROR` | rollback trial; rebuild configured hasher | later healthy execution | recovery `FAILED` / `FAULTED` |
| Hang/latency fault | measured latency or hardware status | sever, flush, restart | fresh healthy telemetry | `fail_after` unhealthy observations |
| Queue pressure | bounded recovery queue | throttle and drain without dropping records | fresh HOLD/healthy observation | speculation remains frozen |
| Cassini/corrupt record | seal error with record identity | quarantine, flush ring, reset cursor | fresh clean record | fail closed; no candidate submission |
| Lane faults | cumulative fault bucket | acknowledged mask retirement/readmission | probation self-tests | degraded mode at minimum lanes |
| Invalid checkpoint | integrity/JSON rejection | restore verified state | reload and health probe | remain faulted |

## Optimisation matrix

| Tunable | Baseline | Candidate | Evaluation | Retain / rollback |
| --- | --- | --- | --- | --- |
| Window / batch size | >=3 completed windows on the executed route | policy-proposed bounded window | completed work / wall-clock second; incomplete/stale/early windows excluded | >=2% measured gain retains; otherwise rollback |
| Precompute depth | measured plan latency, queue starvation and job churn | operating-policy depth | wait and discarded-planning cost | policy minimum within queue bounds |
| Thermal/latency load | measured bounds and probes | smaller next window | fresh execution health | safety de-rate immediately; recovery outranks optimisation |
| Execution route | actual router provenance | existing configured route only | measured completed route and host recheck | unavailable route falls back explicitly; no invented backend |
| Lane/polyhedral mask | measured lane faults/hashes | acknowledged one-at-a-time Salamander trial | dwell then measured fitness | accept or acknowledged revert |

The new controller does not use internal phi scores as production improvement.
Its acceptance metric is measured completed useful work per wall-clock second.

## Telemetry

`evidence_snapshot()["optimization"]` now exposes the current configuration,
trial, action class, baseline/candidate result, accept/rollback decision,
cooldown, last observation and evidence source. Missing values are
`"Unavailable"`. Recovery telemetry remains under `recovery` and measured
pre/post effect under `intelligence.recovery_effect` / the knowledge fabric.

## Remaining boundaries

- Live pool acceptance requires configured credentials, connectivity and an
  actual pool acknowledgement; software tests cannot manufacture it.
- MLA1517 lane repair and accelerator measurements require the physical device.
- Energy optimisation stays unavailable without a real power probe.
- The control-API autonomous supervisor remains a separate worker-lifecycle
  authority; it has callers and cannot safely be deleted in this change.
