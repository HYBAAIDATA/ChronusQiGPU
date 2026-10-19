# EUCLID Cognition: the integrated primary intelligence loop

`euclid.cognition` makes the merged v16 engine, the governed runtime and the
learning/memory stack operate as **one executable cognitive cycle**, wired
into `EuclidRuntime` via `runtime.enable_intelligence()`.

## Composition

`EuclidRuntime.enable_intelligence()` constructs a `CognitiveService` that:

* registers the governed `euclid-engine` organ (`analyze` / `probe` /
  `search`, PROPOSE authority) with creator-scoped dispatch rights;
* hydrates episodic memory from sealed episodes, restores the learned
  program world model and the strategy policy from durable state;
* exposes `service.solve(problem)` running the canonical loop:

`represent -> retrieve -> analogy -> abduce -> deduce -> discriminate ->
hypothesis update -> strategy -> plan -> compose -> imagine -> rank ->
execute -> compare -> metacontrol (replan?) -> learn -> consolidate ->
terminate`

Every transition lands in the episode's hash-linked ledger and the runtime's
shared `EvidenceChain` (`cognition-<phase>` kinds).  Terminal outcomes are
explicit: `solved` / `stalled` / `aborted` / `unexecuted`.

## Domain grounding

The world state is program structure (`program_signature`: relational AST
features, never identifier vocabulary); actions are real operator
applications or bounded strategy executions behind the sandbox; the world
model (`ProgramWorldModel`) learns (structure-class, operator) -> measured
fitness-delta buckets and persists across restart with a sealed payload.

## Discipline enforced in code

* Imagined rollouts never carry observed standing (`EvidenceItem`).
* Execution is fail-closed: revoke the rights grant and dispatch raises.
* Abduction keeps competing hypotheses (including a null hypothesis) until
  a discriminating sandbox intervention separates them.
* Strategy preference never crosses problem classes without per-class
  evidence (negative-transfer guard).
* Objective weights are recorded on every ranked candidate.
* Wall-clock telemetry is excluded from the sealed, replay-deterministic
  episode core (recorded in the timestamped evidence chain instead).

## φ position

`phi_schedule.phi_order` remains `exploratory-parametric` per the Lucas/Pisot
precision contract; in the elevated path φ is a diagnostic column, never the
objective and never a promotion criterion by itself.

## Non-claims

No AGI/ASI, consciousness, quantum advantage, production authority, mining
authority, or external superiority is claimed.  Internal benchmark deltas
are internal measured results only.

## Acceptance

```bash
python scripts/check_intelligence_elevation.py
```

## v17: integrated adaptive intelligence

`euclid.cognition.integrated` supplies specialists that make the same
`GeneralIntelligenceCore` operate as one adaptive system over interactive
hidden-mechanism worlds (`euclid.cognition.worlds`):

```python
from euclid.cognition.worlds import generate_task, MechanismWorld, WorldExecutor
from euclid.cognition.integrated import IntegratedAgent

spec, truth = generate_task("causal-circuit", seed=7, partition="evaluation")
agent = IntegratedAgent.for_system("integrated")        # or "v16.4-reference", "minus-…"
result = agent.solve(spec, WorldExecutor(MechanismWorld(spec, truth)))
```

Inside a governed runtime use `EuclidRuntime.compose_adaptive_intelligence()`
and `runtime.solve_task(spec, executor)`: every probe and submission is a
Delegator dispatch with a creator-granted, then revoked, right; knowledge is
sealed and persisted; restart is verified in the reachability matrix.

Loop additions (each its own transition): strategy-first selection,
VOI-governed evidence gathering with sequential expected-information-gain
probes, likelihood-based hypothesis updates, analogy refresh against the
evolving representation, measured representation restructuring, plan repair,
metacognitive control (`repair_model`, `abandon_transfer`, `change_strategy`,
`change_representation`, `adjust_plan_depth`), proxy-objective auditing, and
end-of-episode consolidation (semantic priors, causal/procedural/episodic/
strategy memory, skill discovery, transfer ledger).

Discipline: hidden truth is reachable only through the executor; imagined
rollouts are labelled predictions; held-out evaluation runs on frozen
knowledge whose digest is checked before and after; φ machinery is ablated
at its source with neutral twins.  The research programme is
`scripts/run_euclid_v17_research.py`; results are in `reports/euclid_v17/`.
