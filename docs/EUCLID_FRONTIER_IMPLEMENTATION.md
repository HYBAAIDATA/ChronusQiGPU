# Euclid frontier-agent implementation contract

## Scope and fixed baseline

Owner-directed implementation, not a model-superiority certification. Repository:
`PhiEnterprise1/EuclidPhiEnterprise`; main baseline
`6688e83c22d36dc16dfd5516e9e7d81959c84438`; consolidated Salamander parent
`f63d478293fc962066dba1205d1432e81d40dc72`; feature branch
`feat/euclid-frontier-contract-20261014`.

`EUCLID_FRONTIER_OWNER_SPEC.md` preserves the revised attached brief. Subsequent
owner clarifications S1–S6, M1, T1, A1 and G1 govern the corrections below. This
implementation adds no alternate quantum backend and changes no protocol hashing,
SHA256d, signatures, target comparisons, mining acceptance, pools or release paths.

## Implemented executable surface

- `chronus.agent.FrontierAgent`: explicit host configuration, no automatic agent,
  provider, credentials, authority, training, network or deployment at import.
- `Intelligence.registry.ModuleRegistry.configure_frontier_agent(runtime)` retains
  one configured instance. `run_frontier_task(objective,cognition,plan)` dispatches
  through that same runtime. `instantiate_all()` exposes the retained instance.
  Registration without host configuration is unavailable, not a fabricated answer.
- Bounded problem representations, DAG decomposition checks, strategy ranking,
  graph search, exact likelihood updates for competing hypotheses, abstraction
  support/counterexample gates and impasse policy. Method generation, domain
  knowledge and model execution are explicit host ports, not supplied by enums.
- Scoped writable action execution, six-tuple permissions, aggregate quotas,
  pre-reserved action **and recovery** resources, mandatory external execution and
  rollback guards, fresh environment observations, verifier reports, global
  objective acceptance and observed rollback. No silent read-only restriction.
- Separate host qualification service: independently authenticated evaluation,
  task/artifact-bound assurance, target-level trust checks, direct-episode quorum,
  expiring signed authority snapshots, demotion/suspension and model-change reset.
- Learning evidence, independent-support memory validation, retained contested
  lessons, provenance-preserving fact/lesson adjudication and transitive staleness.
- Authenticated ledger, durable-before-act events, anchored provenance records,
  evidence custody/hash checks and actual byte comparisons for host-selected
  deterministic components. Stochastic model re-execution is not promised.

## Specification consistency decisions

1. **T5 first.** Certified assurance is reachable. The later owner's stricter tier
   mapping supersedes the attachment's weaker low-tier rule: T0 sandbox uses self
   assessment; T1/T2 require internal review; T3/T4 require external review; T5
   requires certification. Higher scoped authority can require more, never less.
   Assurance levels and authority are distinct typed axes.
2. **Two loops.** `operational_loop.py` has no qualification, promotion or signing
   call. The runtime holds no trust profile or governance signer. It consumes a
   host-issued scope, records evidence and stops. Qualification is a separate API.
   This is a code dependency boundary, **not process isolation**: the host must put
   governance keys/services outside the untrusted actor's address space.
3. **Guard before acting.** No default direct-execution path exists. The host must
   provide `execution_guard` and `rollback_guard`; resource reservations precede
   dispatch. Actual-cost receipts additionally detect reported overruns. A Python
   callback cannot forcibly preempt another callback: production CPU/memory/time,
   network, filesystem and spending enforcement belongs to the external executor.
4. **Observe the world.** Returned receipts are not environment evidence. Separate
   pre/post observations and global acceptance reports are required. Matching
   states are consistent with causation, not causal proof. Confirmed causal claims
   require host-attested interventional evidence; controlled replications support
   a weaker classification. A local file read is not universal side-effect coverage.
5. **Required is not achieved.** Candidate creation never fills achieved assurance
   from a required-level function. Integration verifies earned signatures and
   evaluator reports; a new task scope starts at OBSERVE and inherits no grants.
6. **STOP is control.** The legacy strategy enum label is rejected at registration;
   STOP plans have no primary executable strategy. Wait is a zero-spend strategy.
   Empty/one-strategy cases have an explicit fallback or absence reason.
7. **Novelty.** Authority/assurance gates precede execution ranking. Untested pairs
   use a pessimistic prior. Diverse novelty portfolios exclude a secondary with
   an identical failure-mode set; a checkpoint precedes consequential execution.
   Self-declared failure-mode diversity is not measured statistical independence.
8. **Frozen metrics.** Freeze means an approved version cannot be redefined within
   its qualification cycle. It does not prohibit using that approved version;
   the literal opposite reading would disable every gate for every cycle.
9. **Exact score meanings.** Reliability success_50/80/95/99 are conservative
   one-sided binomial lower coverage bounds, not quantiles of Bernoulli samples.
   Reliability's calibration diagnostic is Brier loss; fixed-bin ECE is separately
   implemented. Evidence scores/utility weights are policy assessments, not IQ,
   probabilities of truth or empirical proof of model superiority.

## Executable verification properties

| Requirement | Implementation | Focused verification |
| --- | --- | --- |
| S1 authority before strategy ranking | strategy | test_strategy: authority gating |
| S2 task/artifact-bound statistics; unknown pessimism | strategy, qualification_loop | test_strategy: stale/tampered/task-bound records |
| S3 independent pre-acting checkpoint | operational_loop | test_operational_loop: checkpoint cannot be skipped |
| S4 wait retained, STOP total control outcome | strategy | test_strategy: wait/stop, budget/evidence gates |
| S5 fallback or explicit reason; novelty portfolio | strategy | test_strategy: ambiguity/portfolio/fallback |
| S6 ordinary episodes cannot clear quarantine | strategy, qualification_loop | test_strategy; strategy-specific suite refusal |
| M1 uncalibrated meta-fields use pessimistic bounds | characterisation | test_characterisation: cold start and resolved calibration |
| T1 transfer cannot replace direct task evidence | qualification_loop | test_qualification_loop: direct quorum |
| A1 no unqualified weighted adjudication | world_model, memory | test_world_model: partial order, corpus admission |
| G1 plural families, frozen version, drift suspension | anti_goodhart, qualification_loop | test_anti_goodhart and actual qualification-path cycle test |
| Operational completion cannot promote | main, operational_loop | real temp-file write with identical before/after authority |
| Shared retry/iteration budget | control, operational_loop, main | successful-step counting; no second main retry |
| Failure must not masquerade as recovery | operational_loop | observed rollback; failed rollback stops runtime |
| Observed delta is not causal confirmation | perception | temporal/interventional/confounded classifications |
| Decision provenance without false determinism | audit | signed chain, anchor, custody, stochastic/byte tests |
| Permission dimensions and cumulative usage | permissions | parametrized six-tuple denials and aggregate quota |
| Catastrophic risk is not traded for value | value | high-value inadmissible action refusal |
| Independent-evidence ceiling/conflict retention | verification, memory, world_model | dependence cap, conflicting verifier, contested memory |
| No hidden authority from input origin | security | tool/web/file/third-party command refusal |
| Capability requires earned assurance | capability_creation | qualified scoped integration/retirement; missing-assurance refusal |
| Registry is actual runtime dispatch | Intelligence.registry | complete real registry module, retained runtime and real temp-file write |

The machine-readable capability manifest maps every module to its test file. Test
passes establish these bounded contract cases, not universal proofs about every
possible learned model, hostile process or real-world environment.

## Calibration and scientific evidence boundaries

- **M1:** Characterisation uses exact comparable feature distances, diverse
  interpretation-group reports, declared action-space reversibility and declared
  verifier membership tests. ECE is computed on resolved meta-history; missing or
  degraded fields become novel/ambiguous/irreversible/external-only/zero-budget.
  The supplied representation, independence labels and containment model still
  need qualified host provenance. This does not prove novelty detection infallible.
- **T1:** `predict_success()` implements a similarity/sample-size/recency-shrunk
  estimate with mean, lower bound and effective sample size, for one donor cohort
  at a time (avoids order-dependent repeated blends). It is a conservative utility
  primitive; automatic cross-class donor selection is **not** wired. Production
  strategy selection currently relies on signed direct class records or pessimism.
  No transfer estimate participates in authority qualification.
- **A1:** Weighted scoring requires externally verified calibration lineage with
  N_REF >= 200, accuracy >= 0.85, per-dimension results, weight intervals, frozen
  weight digest, expiry and MAX_DIM_SHARE <= 0.4. Uniform weights are required when
  their point lies within every reported interval. Otherwise the cold-start
  componentwise partial order is used, retaining unresolved contradictions.
  `qualify_adjudication_weights()` admits an independent review, not a fabricated
  corpus or an implemented statistical fitter. A real reference corpus, fitting,
  leave-one-dimension-out analysis and bootstrap CI are **not provided** here.
- **G1:** Three bounded gate metrics from >=2 declared families are signed;
  per-cycle version freeze, independent outcome sample admission, absolute proxy
  divergence, two-cycle suspension and optimization-objective disclosure exist.
  No automatic authority increase occurs on missing/out-of-date tracking evidence.
  Full conditional/rank/tail/subgroup/causal Goodhart diagnostics, independent real
  holdout outcomes, prospective metric replacement and monitoring-window magnitude
  bounds remain deployment qualification work, not demonstrated immunity.

## Reproduction and local scope

Run in a checkout with the new files and actual lazy `chronus/__init__.py`:

```bash
python -m pytest tests/frontier_agent -q --confcutdir=tests/frontier_agent
python -m black --check --line-length 100 chronus/agent tests/frontier_agent
python -m ruff check --select F chronus/agent tests/frontier_agent
python -m compileall -q chronus/agent tests/frontier_agent Intelligence/registry.py
```

The local validation used retrieved actual source files and the unchanged actual
Chronus parent initializer. No alternative quantum operators or namespace-package
replacement was used for Chronus. The registry contract executes its complete
actual module under an isolated module name; full heavy `Intelligence/__init__.py`
initialization is excluded. `--confcutdir` excludes ancestor repository conftests.
Tests use real temporary-file actuation/observations and observed restoration;
fixture evaluators/assurance identities, lenient thresholds and guard callbacks
are explicitly **unit-test contracts**, not independent reviewers, hidden benchmark
custody, certified sandboxes or production resource enforcement.

The validation JSON records versions, commands, statuses, source hashes, test
counts and exclusions. Hashes authenticate bytes, not truth or independent review.
Exact binomial work is bounded to 128 trials (32 per cohort, 96 protected trials
in the five-cohort evaluator); records are 64KiB, ledger imports 16MiB. These finite
limits may prevent stringent production thresholds being certified; they must not
be relaxed by silently relabelling insufficient evidence as success.

## Remaining release gates — not permission questions

1. Connect qualified model/method/experiment executors and the canonical backend
   through host ports; this work does not implement external vendor SDKs or claim
   all cookbook/workflow adapters are executable.
2. Deploy governance signers and live revocation outside actor processes. Qualify
   OS/network/filesystem/spending guards, hard cancellation and durable audit
   custody/anchors. Missing hosts are blocked, never replaced by permissive defaults.
3. Supply real protected evaluation tasks, isolation/exposure custody, independent
   reviewers, reference corpus and ground-truth outcome samples. Configure and
   empirically qualify release thresholds; unit fixture thresholds are not policy.
4. Run full repository/Chronus/TUQC/Intelligence imports, existing conftests,
   installed wheel/sdist, integration, security, provenance, CI, rollback and device
   qualification. These are not covered by focused source tests.
5. Resolve mandatory assurance evidence before merge. Parent PR #68 currently has
   failing `chronus/mla1517/gates`: incomplete or invalid mandatory assurance
   evidence. Do not bypass or relabel it; check-run access previously returned 403.

No main merge, release, deployment, provider call, mining/pool operation or claim
of AGI, ASI, mathematical prize proof, quantum speedup or leading-model superiority
is authorized by these local contract tests. Like-for-like model benchmarking
requires common tasks, budgets, graders, versions and independent measured results;
that benchmark has not run. This document distinguishes implementation completion
of bounded primitives from unavailable empirical qualification.
