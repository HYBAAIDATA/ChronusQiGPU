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
