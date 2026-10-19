# Production closed-loop mining runtime

This document describes the authoritative mining control plane. Capability
names are not evidence: a component is treated as active only when the
production entry path can reach it and its runtime contract preserves external
pool/job truth.

## Canonical execution graph

```text
mining_runtime._main_async / pythia-mine
  -> resolve allowlisted primary/failover pools
  -> BackendRegistry capability probe + declared routing policy
  -> GeodesicProductionMiningCoordinator / IntelligentPoolCoordinator
  -> Stratum connect -> subscribe -> authorize -> target/difficulty -> notify
  -> immutable WorkIdentity (session + generation + job fingerprint)
  -> AgenticMiningController SearchPlan + exclusive nonce lease
  -> Chronus/Hendrix/M32/Poincare ordering where selected
  -> dispatch algebra certificate
  -> ExecutionRouter / ProductionExecutionRouter
       -> CPU
       -> OpenCL GPU
       -> native CUDA
       -> native Metal
       -> remote GPU
       -> ASIC
       -> SUPER ASIC
  -> independent host SHA256d + target + freshness verification
  -> current-session/current-work/duplicate submission gate
  -> serialized mining.submit
  -> literal pool acknowledgement, or OUTCOME_UNKNOWN after uncertain write
  -> DecisionJournal + CausalLedger + MiningSession + telemetry
  -> RecoveryGovernor/SelfHealingAgent and ClosedLoopOptimizer
  -> learning/knowledge retention
  -> next leased window
```

`chronus/mla1517_platform/python/mining_runtime.py` is the production
composition root. The historical `AutonomousExecutionLoop` under `legacy/` is
not a production entry point.

## Single-writer authority model

| Concern | Authoritative owner | Rule |
| --- | --- | --- |
| Worker process lifecycle | `control_api` + `autonomous_supervisor` | may revive a crashed mining worker; does not own mining state or tune mining parameters |
| Pool/session/job epoch | Stratum runtime + `StratumAdapter` | external network truth only |
| Planning and nonce leases | `AgenticMiningController` | bounded SearchPlans; non-overlapping generation-scoped leases |
| Search ordering | Chronus/Hendrix/M32/Poincare adapters | ordering/scheduling only; never proof authority |
| Backend availability | `BackendRegistry` | implementation plus successful capability/health probe required |
| Backend preference | explicit execution device or `PYTHIA_BACKEND_ORDER` | declared policy; no undeclared CPU fallback |
| Physical execution | `ExecutionRouter` / `ProductionExecutionRouter` | executes only the authorised leased range |
| Candidate verification | Stratum proof adapter + independent host rehash | SHA256d/target/header/extranonce/current epoch are mandatory |
| Share submission | `IntelligentPoolCoordinator` + `MiningSession` | one serialized submit authority with duplicate guard |
| Mining healing | `RecoveryGovernor` + `SelfHealingAgent` | detect -> isolate -> rebuild/reprobe -> verify or remain faulted |
| Mining optimisation | `ClosedLoopOptimizer` | one bounded measured trial at a time; retain or rollback |
| Learning | world model / knowledge fabric / intelligence memory | consumes measured outcomes; cannot bypass consensus/submission gates |

The outer `autonomous_supervisor` is deliberately observation-only for CUOP
and process-lifecycle recovery. It no longer owns a second mining-window
optimiser. That removes competing writers to the same mining parameter.

## Pool and job lifecycle

A connected socket is not a healthy mining session. Runtime truth separates:

```text
transport_connected
subscribed
authorised
target_available
job_available
mining_active
submission_ready
```

A `mining.notify` creates a new generation/fingerprint. Replacement or
`clean_jobs` semantics invalidate incompatible leases and queued plans. The
execution router re-checks freshness between chunks, and the submission gate
re-checks the current job/session before a share can leave the process.

A locally valid nonce is insufficient for submission. The runtime requires the
current job generation and target, valid header/extranonce construction,
independent SHA256d proof, non-stale work, configured pool/session identity and
submission policy approval.

Disconnect after a possible network write is recorded as `OUTCOME_UNKNOWN`;
the system does not infer acceptance and does not blindly duplicate-submit.

## Execution fabric

| Backend | Present | Production-routed | Availability authority | Evidence boundary |
| --- | --- | --- | --- | --- |
| CPU reference | yes | yes | known SHA256d vector/self-check | software execution evidence; throughput measured per run |
| OpenCL GPU | yes | yes | real device/program/kernel bind and self-check | physical execution only when a real OpenCL launch is measured |
| CUDA | yes | yes | CuPy/CUDA device + Chronus SHA256d self-check | physical backend remains labelled `cuda`; current evidence schema conservatively under-claims native launches until the hardware tier is substrate-general |
| Metal | yes | yes | MLX/Apple GPU + Chronus SHA256d self-check | physical backend remains labelled `metal`; same conservative native evidence rule |
| Remote GPU | yes | yes | configured endpoint + protocol/health attestation | remote execution evidence only from the responding agent |
| ASIC | yes | yes | configured responsive physical channel | unavailable stays unavailable; no documentation-only capacity |
| SUPER ASIC | yes | yes | composite of substrates that actually bind | reports the actual bound members; CPU-only composition is not ASIC-speed evidence |

The historical execution-route tokens are named `opencl_m32/opencl_range`, but
native CUDA/Metal use those tokens only as a shared traversal contract. Their
`device_backend` remains literally `cuda` or `metal`; they are never relabelled
as OpenCL to obtain a stronger-looking evidence class.

`PYTHIA_BACKEND_ORDER` may declare the `auto` preference order. Each concrete
lane is still probed by `BackendRegistry`. If the declared list is exhausted,
selection raises `BackendUnavailable`; CPU is not silently appended when the
operator intentionally omitted it. Explicit backend requests remain exact and
fail closed.

## Operational state machine

The cycle ledger is a guarded runtime FSM rather than decorative logging:

```text
STARTUP -> SCAN -> PLAN -> MINE -> VERIFY -> SUBMIT -> ACKNOWLEDGE
                                      \-> EVALUATE
failure -> HEAL -> NEXT_CYCLE
stale   -> EVALUATE -> NEXT_CYCLE
shutdown -> SHUTDOWN
```

Illegal transitions raise; failure does not silently fall through. Pool/session
lifecycle and durable share lifecycle remain separate state machines because
they have different truth authorities.

## Healing

```text
measured fault
  -> classify
  -> freeze affected admission/work
  -> RecoveryGovernor proposal
  -> SelfHealingAgent / execution-hasher factory
  -> rebuild and capability reprobe under the same backend policy
  -> swap only a successfully verified lane
  -> fresh execution observation
  -> return to service or remain FAILED/FAULTED
```

Covered classes include stale jobs, device exceptions, dead/stuck workers,
pool disconnect, queue pressure and invalid execution output. Process death is
handled by the outer lifecycle supervisor; once the process is alive, mining
recovery authority returns to the canonical coordinator.

## Optimisation

```text
completed measured ExecutionRecord
  -> baseline
  -> bounded candidate configuration
  -> production execution measurement
  -> useful completed work / elapsed time comparison
  -> retain or rollback
  -> cooldown / durable evidence
```

The production optimisation authority is `ClosedLoopOptimizer`. Safety
recovery and de-rate actions outrank optimisation. Device faults force
rollback/fail-closed handling. Internal phi scores are not treated as measured
production improvement.

## Decision, idempotency and persistence

`DecisionJournal` records decision identity, job/session generation,
observation, available actions, selected action, reason, execution target,
result/disposition, timestamp and software revision. Plans are journaled before
effect and resolved from measured outcomes.

Nonce leases prevent duplicate range dispatch. `MiningSession` plus the
submission lock prevent duplicate share writes and repeated acknowledgement
processing. Persistence retains configuration, health/optimisation history and
learning evidence, but restart does not restore a pool session, active job
epoch, extranonce state or unverified in-flight share as current external truth.

## Evidence-first telemetry

The runtime exposes observed connection/session flags, current job identity and
age, target/difficulty, backend/device, active work, completed hashes, measured
hashrate, locally valid candidates, submitted/accepted/rejected/stale shares,
backend faults, recovery actions, optimisation actions, latest decision and
latest literal pool acknowledgement. Missing measurements remain unavailable.

The control API currently recognises mapped `ceo` and `operator` control
principals. This document therefore does not claim CEO-only visibility of every
read-only mining telemetry surface. If CEO-only dashboard presentation remains
a product requirement, it requires its own entitlement test and must not be
inferred from mining-runtime authentication.

## End-to-end production-entry verification

`chronus/mla1517_platform/python/test_production_loop_e2e.py` invokes the real
`mining_runtime._main_async` entry path against an explicitly test-only local
Stratum peer and covers:

1. autonomous startup into SCAN/PLAN/MINE/VERIFY/EVALUATE;
2. deterministic locally valid result -> submission -> literal acknowledgement;
3. replacement-job invalidation while work is in flight;
4. dead primary -> configured failover;
5. backend failure -> governed healing/rerouting;
6. restart -> fresh external work;
7. duplicate-share prevention.

`test_execution_loop.py` exercises the closed loop and optimisation mechanics.
`test_backend_policy.py` proves declared backend ordering and no hidden CPU
fallback. `tests/test_autonomous_supervisor_production.py` proves the outer
supervisor cannot write mining configuration. `tests/test_native_production_routing.py`
proves CUDA/Metal route to their native callable without CPU substitution while
preserving truthful backend identity.

`scripts/production_mining_demo.py --seconds 20` is a bounded production-entry
demonstration against a labelled local fixture. Its default hard target is
expected to report zero shares; `--easy` is deterministic protocol-test
infrastructure and is never live-pool evidence.

## Production evidence boundaries

- Software tests can prove control flow and validation but cannot manufacture a
  live pool acceptance.
- Physical OpenCL/CUDA/Metal/ASIC/SUPER ASIC execution requires the exact
  deployment substrate; code presence or a probe implementation is not that
  evidence.
- Energy optimisation remains unavailable without a real power measurement.
- No accepted share, hashrate or accelerator performance figure may be
  populated from configuration, documentation or a scripted fixture.

## Status semantics

`ACTIVE` means reachable production software with an executable control path.
It does not mean the current deployment has the relevant physical device or has
found a share. `PRODUCTION-EVIDENCED` is a separate deployment-level judgement
and must stay partial until current CI/runtime/live-pool/hardware evidence is
available.
