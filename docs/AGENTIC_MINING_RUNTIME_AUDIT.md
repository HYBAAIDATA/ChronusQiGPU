# Agentic mining runtime — production control-plane audit

## Canonical execution graph

```text
pythia-mine / mining_runtime.main
→ configuration + allowlisted pool/failover policy
→ capability-probed execution-lane selection
→ GeodesicProductionMiningCoordinator / IntelligentPoolCoordinator
→ Stratum connect → subscribe → authorize → difficulty/target → notify
→ immutable WorkIdentity (pool session + generation + job fingerprint)
→ AgenticMiningController SearchPlan + exclusive nonce lease
→ Chronus/Hendrix/M32/Poincaré ordering advice where selected
→ dispatch algebra certificate
→ ExecutionRouter
→ CPU | OpenCL | CUDA | Metal | remote GPU | ASIC | SUPER ASIC lane when capability-proven
→ independent host SHA256d / target / freshness recheck
→ current-session/current-work/duplicate submission gate
→ serialized mining.submit
→ literal pool acknowledgement (or OUTCOME_UNKNOWN after uncertain write)
→ DecisionJournal + CausalLedger + MiningSession + telemetry evidence
→ ClosedLoopOptimizer measured trial / RecoveryGovernor + SelfHealingAgent
→ learning / next leased window
```

`chronus/mla1517_platform/python/mining_runtime.py` is the production
composition root. `IntelligentPoolCoordinator` is the sole owner of mining
search/execution correlation and submission. The historical
`AutonomousExecutionLoop` under `legacy/` is not a production entry point.

## Authority and agent boundaries

| Responsibility | Authoritative owner | Boundary |
|---|---|---|
| Process lifecycle | `control_api` + `autonomous_supervisor` | may revive crashed worker processes; does not mutate mining parameters |
| Pool/session/job epochs | Stratum runtime + `StratumAdapter` | network truth only |
| Planning / nonce leases | `AgenticMiningController` | bounded SearchPlans and non-overlapping leases |
| Search ordering | Chronus/Hendrix/M32/Poincaré adapters | ordering/scheduling only; never proof authority |
| Backend availability | `BackendRegistry` | real capability probe required |
| Backend preference | `PYTHIA_BACKEND_ORDER` or explicit device policy | declared order; unavailable lanes refused; no undeclared CPU fallback |
| Execution | `ExecutionRouter` + capability-proven hasher | leased work only |
| Verification | proof adapter + independent host checks | SHA256d, target, epoch, freshness, header/extranonce |
| Submission | `IntelligentPoolCoordinator` + `MiningSession` | one serialized submit authority with duplicate guard |
| Mining recovery | `RecoveryGovernor` + `SelfHealingAgent` | detect/isolate/rebuild/reprobe/verify or fail closed |
| Mining optimisation | `ClosedLoopOptimizer` | measured, bounded retain/rollback trials only |
| Learning | learning ledger / knowledge fabric / intelligence memory | outcome evidence only; never bypasses proof gates |

The outer `autonomous_supervisor` is intentionally **not** a second mining
optimiser. CUOP is observation-only there; mining-window mutation belongs only
to `ClosedLoopOptimizer` in the canonical coordinator.

## Backend matrix

| Backend | PRESENT | WIRED | ACTIVE when probe passes | TESTED | Current production-evidence boundary |
|---|---:|---:|---:|---:|---|
| CPU reference | yes | yes | yes | yes | software/runtime evidence exists; throughput is measured per run |
| OpenCL GPU | yes | yes | yes | yes | requires a real bound OpenCL device + kernel self-check on deployment |
| Native CUDA | yes | yes | yes | yes | requires CuPy/CUDA device + Chronus kernel self-check on deployment |
| Native Metal | yes | yes | yes | yes | requires MLX/Apple GPU + kernel self-check on deployment |
| Remote GPU | yes | yes | yes | yes | requires configured healthy remote endpoint + wire attestation |
| ASIC | yes | yes | yes | yes | requires a configured responsive physical ASIC channel; absence is explicit |
| SUPER ASIC | yes | yes | yes | yes | real composite over substrates that actually bind; a CPU-only composition is labelled as such and is not evidence of ASIC speedup |

`BackendRegistry` is the capability authority. Documentation, environment
labels, or requested names do not make a lane available. Explicit lane
requests fail closed. For `auto`, an operator may declare
`PYTHIA_BACKEND_ORDER`; every listed lane is probed in order and CPU is not
silently appended if the operator omitted it.

## Pool lifecycle

| Phase | Production behaviour |
|---|---|
| connect | bounded transport, endpoint roster and failover evidence |
| subscribe | correlated Stratum response; separate lifecycle state |
| authorize | correlated response; auth failure is not session health |
| difficulty / target | captured independently from transport state |
| notify | creates/refreshes immutable work generation |
| replacement job | freshness callback invalidates obsolete execution; stale candidate cannot submit |
| submit | current session + job + target + header + extranonce + duplicate gates |
| acknowledge | only literal pool response becomes ACCEPTED/REJECTED |
| disconnect after possible write | recorded `OUTCOME_UNKNOWN`, never inferred accepted/rejected |
| reconnect/failover | bounded exponential backoff over configured endpoints |
| shutdown | cooperative signal cancellation and session close |

A connected socket alone is never treated as a healthy mining session.
Transport, subscription, authorization, target, job availability, mining
activity and submission readiness remain distinguishable runtime facts.

## Operational state machines

The mining-cycle ledger drives real transitions rather than decorative logs:

```text
SCAN → PLAN → MINE → VERIFY → SUBMIT → ACKNOWLEDGE
                                  ↘ EVALUATE
failure → HEAL → NEXT_CYCLE
stale   → EVALUATE → NEXT_CYCLE
```

`MiningSession` separately owns durable share lifecycle states, and the
Stratum runtime owns connection/session phases. Invalid transitions and stale
work fail closed; a new generation is never restored from persisted local
state as current external truth.

## Decision and idempotency evidence

`DecisionJournal` records decisions before effect and resolves them from
measured outcomes. Its contract includes decision id, pool session, job
generation/fingerprint, observation, available actions, selected action,
reason, execution target, result/disposition, timestamp and software
revision. No synthetic confidence field is required.

Nonce leases prevent overlapping dispatch. `MiningSession.already_submitted`
and the coordinator's submission lock prevent duplicate shares. A possible
network write followed by disconnect is not retried as if it were known safe;
it becomes `OUTCOME_UNKNOWN`.

## Healing

```text
execution observation
→ classify fault
→ freeze/admission gate
→ RecoveryGovernor proposal
→ SelfHealingAgent / execution-hasher factory
→ capability reprobe under the same declared backend policy
→ swap only a successfully rebuilt lane
→ fresh health observation
→ return to service or remain faulted/fail closed
```

Process death is a separate outer-layer concern: `autonomous_supervisor` may
restart the worker process through `control_api`, after which the canonical
mining recovery authority resumes ownership.

## Optimisation

```text
completed production ExecutionRecord
→ baseline
→ one bounded candidate window
→ real completed-work / elapsed-time measurement
→ threshold comparison
→ retain or rollback
→ durable optimisation evidence
```

A device fault forces rollback/fail-closed handling. The control-plane daemon
does not write the nonce window, preventing competing optimisation authorities.

## Evidence-first telemetry

The canonical worker publishes observed Stratum lifecycle, job identity,
target/difficulty, selected backend/device, hashes completed, measured
hashrate, executions, candidates/shares, pool outcomes, recovery state,
optimisation state, decision history and persisted evidence references. Missing
facts remain unavailable; pool acceptance is never inferred.

Control endpoints are authenticated and guardian-mediated according to the
control-plane policy. This audit does **not** claim that every read-only mining
telemetry surface is CEO-only: the current repository supports mapped `ceo`
and `operator` control principals. If product policy requires CEO-only viewing,
that is a separate presentation/entitlement gate and must be tested as such.

## Tests expected at the production gate

The repository contains executable coverage for:

- fresh-process production-entry startup against a scripted Stratum peer;
- connect / subscribe / authorize / notify / execution;
- deterministic local share verification → submission → literal acknowledgement;
- stale-job invalidation and freshness cancellation;
- reconnect and primary/failover behaviour;
- backend unavailability / fail-closed selection;
- duplicate submission prevention;
- bounded optimisation retain/rollback;
- recovery-governor and self-healing mechanics;
- restart/fresh external truth semantics;
- backend policy ordering and prohibition of undeclared CPU fallback;
- control-plane supervisor authority isolation from mining optimisation.

Live-pool shares and hardware throughput are deployment evidence and are never
manufactured by these tests.

## Remaining limitations

- Physical lane availability is deployment-specific; code presence is not
  production hardware evidence.
- A SUPER ASIC composition may legally bind only one real substrate; its
  backend label must be read literally.
- No new live-pool accepted share is claimed by this audit/update.
- No physical ASIC/CUDA/Metal/OpenCL trace is claimed unless a deployment run
  actually produced it.
- The current control API recognises both `ceo` and `operator` mapped control
  roles; CEO-only dashboard visibility is not asserted by this document.

## Final software status

| Capability | Status |
|---|---|
| AGENTIC CONTROL | ACTIVE in canonical coordinator |
| AUTOMATED MINING | ACTIVE when pool + capability-proven backend are configured |
| POOL WORKFLOW | ACTIVE in software; live deployment remains external evidence |
| EXECUTION FABRIC | ACTIVE in software, deployment-dependent per physical lane |
| SHARE VERIFICATION | ACTIVE |
| SHARE SUBMISSION | ACTIVE, policy gated and fail closed |
| SELF-HEALING | ACTIVE in software; device-specific production evidence varies |
| SELF-OPTIMISATION | ACTIVE with one canonical mining authority |
| PRODUCTION-EVIDENCED | PARTIAL until the exact deployment supplies current live-pool/hardware evidence |
